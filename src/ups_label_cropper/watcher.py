import logging
import tempfile
import time
from pathlib import Path

import fitz
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

from ups_label_cropper.config import Config
from ups_label_cropper.crop import process_label
from ups_label_cropper.printer import print_pdf


logger = logging.getLogger(__name__)


def _wait_for_file_unlock(path: Path, timeout: float = 10.0) -> bool:
    """Wait for a file to be released by the process that created it.

    On Windows, when a file is created (e.g., browser download), it may hold
    an exclusive write lock until the transfer completes. This function polls
    until the file is accessible or the timeout expires.

    Returns True if file is accessible, False if timeout occurred.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Attempt to open exclusively to check for locks
            path.rename(path)
            return True
        except OSError:
            time.sleep(0.5)
    return False


class LabelFileHandler(FileSystemEventHandler):
    def __init__(self, config: Config, pipeline: "LabelPipeline"):
        super().__init__()
        self.config = config
        self.pipeline = pipeline
        self._processing: set[str] = set()
        self._debounce_seconds = 1.0

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return

        path = Path(event.src_path)
        self._schedule_process(path)

    def _schedule_process(self, path: Path):
        key = str(path.resolve())
        if key in self._processing:
            return
        self._processing.add(key)
        try:
            time.sleep(self._debounce_seconds)
            if not path.exists():
                logger.warning(f"File disappeared before processing: {path.name}")
                return
            # Wait for file to be unlocked by originating process (e.g., browser download)
            if not _wait_for_file_unlock(path):
                logger.warning(f"File is locked, skipping: {path.name}")
                return
            logger.info(f"[WATCHER] New PDF detected: {path.name}")
            self.pipeline.run(path)
        except Exception as e:
            logger.error(f"[WATCHER] Failed to process {path}: {e}")
        finally:
            self._processing.discard(key)


class LabelPipeline:
    def __init__(self, config: Config):
        self.config = config
        self._temp_files: list[Path] = []

    def run(self, input_pdf: Path) -> bool:
        input_pdf = Path(input_pdf).resolve()
        if not input_pdf.exists():
            logger.warning(f"[PIPELINE] Input file no longer exists: {input_pdf}")
            return False

        try:
            fitz.open(str(input_pdf)).close()
        except Exception as e:
            logger.error(f"[PIPELINE] File is not a valid PDF: {input_pdf}: {e}")
            return False

        temp_output = Path(tempfile.gettempdir()) / f"ups_cropped_{int(time.time()*1000)}.pdf"
        self._temp_files.append(temp_output)

        try:
            logger.info(f"[PIPELINE] Cropping label...")
            process_label(str(input_pdf), str(temp_output))
        except Exception as e:
            logger.error(f"[PIPELINE] Crop failed for {input_pdf}: {e}")
            return False

        printer_desc = self.config.printer_name or "system default"
        try:
            logger.info(f"[PIPELINE] Sending to printer: {printer_desc}")
            print_pdf(temp_output, printer_name=self.config.printer_name)
            logger.info(f"[PIPELINE] Print job sent successfully")
        except Exception as e:
            logger.error(f"[PIPELINE] Print failed: {e}")
            return False

        self._cleanup_temp()
        self._archive_source(input_pdf)
        logger.info(f"[PIPELINE] Processing complete for {input_pdf.name}")
        return True

    def _archive_source(self, source: Path):
        try:
            processed_dir = self.config.get_processed_dir()
            dest = processed_dir / source.name
            counter = 1
            while dest.exists():
                stem = source.stem
                suffix = source.suffix
                dest = processed_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            source.rename(dest)
            logger.info(f"Archived to: {dest}")
        except Exception as e:
            logger.error(f"Failed to archive source file {source}: {e}")

    def _cleanup_temp(self):
        for tf in self._temp_files:
            try:
                if tf.exists():
                    tf.unlink()
            except Exception:
                pass
        self._temp_files.clear()


class LabelWatcher:
    def __init__(self, config: Config | None = None):
        if config is None:
            config = Config.load()
        self.config = config
        self.pipeline = LabelPipeline(config)
        self.event_handler = LabelFileHandler(config, self.pipeline)
        self.observer = Observer()

    def start(self):
        watch_dir = Path(self.config.watched_directory)
        if not watch_dir.exists():
            watch_dir.mkdir(parents=True, exist_ok=True)
        self.observer.schedule(self.event_handler, str(watch_dir), recursive=False)
        self.observer.start()
        logger.info(f"Watching directory: {watch_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join()

    @property
    def is_running(self) -> bool:
        return self.observer.is_alive()