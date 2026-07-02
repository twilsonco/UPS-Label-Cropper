import argparse
import logging
import sys

from ups_label_cropper.crop import main as crop_main


logger = logging.getLogger(__name__)


def run_watch_mode():
    # Import Config here to avoid circular imports and ensure we can resolve log path
    from ups_label_cropper.config import Config

    config = Config.load()
    config_path = Config.default_config_path()
    log_path = config_path.parent / "cropper.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        filename=str(log_path),
    )

    from ups_label_cropper.tray import run_tray
    from ups_label_cropper.printer import get_system_default_printer, _validate_printer

    # Determine printer and validate
    if config.printer_name:
        printer_display = config.printer_name
        printer_valid = _validate_printer(config.printer_name)
    else:
        default = get_system_default_printer()
        printer_display = f"system default ({default or 'none set'})"
        printer_valid = default is not None

    # Print startup banner
    print("\n" + "=" * 60)
    print("  UPS Label Cropper - Watch Mode")
    print("=" * 60)
    print(f"\n  Configuration:")
    print(f"    Config file:     {config_path}")
    print(f"    Log file:        {log_path}")
    print(f"\n  Folders:")
    print(f"    Watching:        {config.watched_directory}")
    processed_dir = config.get_processed_dir()
    print(f"    Archive (after successful print):")
    print(f"                 -> {processed_dir}/")
    print(f"\n  Printer:")
    if printer_valid:
        print(f"    Using:           {printer_display} [OK]")
    else:
        print(f"    Using:           {printer_display} [! NOT FOUND]")
    print("\n" + "-" * 60)
    print("  System tray icon is running in the background.")
    print("  Right-click it to change settings or exit.")
    print("-" * 60 + "\n")

    logger.info(f"Starting UPS Label Cropper in watch mode...")
    if config.printer_name:
        logger.info(f"  Printer configured: {config.printer_name} (valid: {printer_valid})")
    else:
        default = get_system_default_printer()
        logger.info(f"  Using system default printer: {default or 'none'}")

    run_tray(config=config)


def main():
    parser = argparse.ArgumentParser(prog="ups-label-cropper")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run in watch mode, monitoring a directory for new PDFs (default behavior if no input/output PDF is specified)",
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

    # If no input or output PDF is specified, run in watch mode
    if not args.input_pdf or not args.output_pdf:
        run_watch_mode()
    else:
        sys.argv = [sys.argv[0], args.input_pdf, args.output_pdf]
        crop_main()


if __name__ == "__main__":
    main()