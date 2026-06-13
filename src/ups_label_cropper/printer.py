import sys
from pathlib import Path

if sys.platform == "win32":
    import win32api
    import win32print


def print_pdf(pdf_path: Path, printer_name: str | None = None) -> bool:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if sys.platform == "win32":
        return _print_windows(pdf_path, printer_name)
    else:
        raise OSError(f"Printing is only supported on Windows. Current platform: {sys.platform}")


def _print_windows(pdf_path: Path, printer_name: str | None) -> bool:
    if printer_name:
        printer = _get_printer_handle(printer_name)
        if printer:
            result = win32api.ShellExecute(
                0,
                "printto",
                str(pdf_path.resolve()),
                f'"{printer}"',
                ".",
                0,
            )
        else:
            raise ValueError(f"Printer not found: {printer_name}")
    else:
        result = win32api.ShellExecute(0, "print", str(pdf_path.resolve()), None, ".", 0)

    if result <= 2:
        raise RuntimeError(f"ShellExecute failed with code {result}")

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


def get_system_default_printer() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        default = win32print.GetDefaultPrinter()
        return default
    except Exception:
        return None