import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import win32print


def _get_sumatra_path() -> Path:
    """Resolve the path to the bundled SumatraPDF executable."""
    # __file__ is the path to this printer.py file
    current_dir = Path(__file__).resolve().parent
    sumatra_exe = current_dir / "bin" / "SumatraPDF.exe"
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
    sumatra_path = _get_sumatra_path()
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