import argparse
import logging
import sys

from ups_label_cropper.crop import main as crop_main


logger = logging.getLogger(__name__)


def run_watch_mode():
    # Import Config here to avoid circular imports and ensure we can resolve log path
    from ups_label_cropper.config import Config

    config = Config.load()
    log_path = Config.default_config_path().parent / "cropper.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        filename=str(log_path),
    )

    from ups_label_cropper.tray import run_tray

    logger.info(f"Starting UPS Label Cropper in watch mode...")
    logger.info(f"  Watch directory: {config.watched_directory}")
    if config.printer_name:
        logger.info(f"  Printer: {config.printer_name}")
    else:
        from ups_label_cropper.printer import get_system_default_printer
        default = get_system_default_printer()
        logger.info(f"  Printer: {default or 'system default'}")

    run_tray(config=config)


def main():
    parser = argparse.ArgumentParser(prog="ups-label-cropper")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run in watch mode, monitoring a directory for new PDFs",
    )
    parser.add_argument(
        "input_pdf",
        nargs="?",
        help="Input PDF file (CLI mode)",
    )
    parser.add_argument(
        "output_pdf",
        nargs="?",
        help="Output PDF file (CLI mode)",
    )

    args = parser.parse_args()

    if args.watch:
        run_watch_mode()
    else:
        sys.argv = [sys.argv[0], args.input_pdf, args.output_pdf]
        crop_main()


if __name__ == "__main__":
    main()