import logging
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if sys.platform == "win32":
    import win32print


logger = logging.getLogger(__name__)

# Name of the bundled executable.
_SUMATRA_EXE_NAME = "SumatraPDF.exe"


def _stable_bin_dir() -> Path:
    """Return a stable (non-temp) directory to hold SumatraPDF.

    This lives under the app's user-data dir, alongside config.json, so it
    survives Windows' automatic cleanup of %TEMP% that deletes PyInstaller's
    one-file _MEIxxxxxx extraction folder out from under long-running apps.
    """
    import platformdirs

    return Path(platformdirs.user_data_dir("UPS-Label-Cropper")) / "bin"


def _bundled_sumatra_path() -> Path | None:
    """Return the path to SumatraPDF inside the PyInstaller one-file bundle.

    Returns None when not running from a frozen (onefile) build.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass) / "ups_label_cropper" / "bin" / _SUMATRA_EXE_NAME
    return None


def ensure_sumatra_present() -> bool:
    """Ensure a working copy of SumatraPDF exists in the stable location.

    When frozen, copies the bundled executable into the user-data dir if it is
    missing or looks different (size used as a cheap change proxy). Returns True
    if a usable copy is present afterwards.
    """
    dest_dir = _stable_bin_dir()
    dest = dest_dir / _SUMATRA_EXE_NAME

    # Already have a stable copy -> nothing to do.
    if dest.exists():
        return True

    bundled = _bundled_sumatra_path()
    if bundled is None or not bundled.exists():
        logger.warning("Not frozen and no stable SumatraPDF found; relying on source bin/")
        return False

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, dest)
        logger.info(f"Ensured stable copy of {_SUMATRA_EXE_NAME} at {dest}")
        return True
    except Exception as e:
        logger.warning(f"Could not ensure stable SumatraPDF copy: {e}")
        return False


def cleanup_stale_temp_dirs(max_age_hours: float = 24.0) -> None:
    """Remove leftover PyInstaller one-file _MEIxxxxxx temp folders.

    The bootloader normally cleans these up on exit, but crashes or forced
    termination leave them behind and they accumulate in %TEMP%. We sweep only
    folders that are (a) not our own active extraction dir and (b) older than
    ``max_age_hours``. In-use files are locked by Windows so rmtree simply skips
    them, making this safe even for other running one-file apps.
    """
    if not getattr(sys, "frozen", False):
        return

    active = {str(Path(getattr(sys, "_MEIPASS", "")).resolve())}
    cutoff = time.time() - max_age_hours * 3600
    tmp_root = Path(tempfile.gettempdir())

    try:
        for d in tmp_root.glob("_MEI*"):
            if not d.is_dir():
                continue
            resolved = str(d.resolve())
            if resolved in active:
                continue
            try:
                if d.stat().st_mtime > cutoff:
                    continue  # recently touched; possibly still in use
            except OSError:
                continue
            shutil.rmtree(d, ignore_errors=True)
    except Exception as e:  # never let housekeeping break startup
        logger.warning(f"Temp cleanup skipped: {e}")


def _resolve_print_binary() -> Path:
    """Resolve the SumatraPDF path to use for a print job.

    1. Prefer the stable non-temp copy (survives Windows temp cleanup).
       Re-ensure it from the bundle if missing (self-heal).
    2. Fall back to the bundled/source copy next to this module.
    """
    # Option 3 self-heal: make sure a stable copy exists before printing.
    if getattr(sys, "frozen", False):
        ensure_sumatra_present()
        stable = _stable_bin_dir() / _SUMATRA_EXE_NAME
        if stable.exists():
            return stable

    # Fallback: bundled (dev/source) or frozen bundle copy next to this module.
    current_dir = Path(__file__).resolve().parent
    sumatra_exe = current_dir / "bin" / _SUMATRA_EXE_NAME
    if not sumatra_exe.exists():
        raise FileNotFoundError(
            f"Bundled SumatraPDF not found at {sumatra_exe}. "
            "Please ensure SumatraPDF.exe is placed in the bin/ directory."
        )
    return sumatra_exe


def print_pdf(pdf_path: Path, printer_name: str | None = None) -> bool:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if sys.platform == "win32":
        return _print_windows(pdf_path, printer_name)
    else:
        raise OSError(f"Printing is only supported on Windows. Current platform: {sys.platform}")


def _print_windows(pdf_path: Path, printer_name: str | None) -> bool:
    if printer_name is None:
        printer_name = get_system_default_printer()
        if printer_name is None:
            raise OSError("No printer specified and no default printer found")
    else:
        # Validate printer exists before attempting to print
        if not _validate_printer(printer_name):
            raise ValueError(f"Printer not found: {printer_name}")

    # Use SumatraPDF for reliable silent printing (avoids ShellExecute issues
    # with Acrobat/Edge leaving ghost processes and stealing focus)
    sumatra_path = _resolve_print_binary()
    subprocess.run(
        [
            str(sumatra_path),
            "-print-to", printer_name,
            "-silent",
            str(pdf_path.resolve()),
        ],
        check=True,
    )
    return True


def _get_printer_handle(printer_name: str):
    try:
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        for p in printers:
            if p[2] == printer_name:
                return p[2]
        return None
    except Exception:
        return None


def _validate_printer(printer_name: str) -> bool:
    """Validate that a printer exists on the system."""
    return _get_printer_handle(printer_name) is not None


def get_system_default_printer() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        default = win32print.GetDefaultPrinter()
        return default
    except Exception:
        return None