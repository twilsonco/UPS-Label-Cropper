import logging
import sys
from pathlib import Path

if sys.platform == "win32":
    import win32print


logger = logging.getLogger(__name__)


def print_pdf(pdf_path: Path, printer_name: str | None = None) -> bool:
    """Print a PDF silently on Windows via the native GDI print API.

    Thin platform façade kept as the public entry point (``watcher.py`` and
    the package ``__init__`` import it). The actual work lives in
    :mod:`ups_label_cropper.gdi_print`; the Windows-only import happens
    inside this function so this module stays importable on macOS/Linux.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if sys.platform == "win32":
        from ups_label_cropper import gdi_print

        return gdi_print.print_pdf(pdf_path, printer_name)
    else:
        raise OSError(f"Printing is only supported on Windows. Current platform: {sys.platform}")


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
