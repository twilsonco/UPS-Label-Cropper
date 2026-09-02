import logging
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import win32print


logger = logging.getLogger(__name__)

# Name of the bundled executable.
_SUMATRA_EXE_NAME = "SumatraPDF.exe"


def _sumatra_candidates() -> list[Path]:
    """Return candidate paths for SumatraPDF, in priority order.

    All candidates are **read-only lookups**. Nothing here copies, writes, or
    deletes anything: the previous one-file build unpacked SumatraPDF out of
    ``%TEMP%\\_MEI*`` into ``%APPDATA%`` and executed it, a classic dropper
    shape for antivirus heuristics (Defender ``Trojan:Win32/Wacatac.B!ml``).
    The one-dir build ships SumatraPDF as a plain file inside the app folder,
    so runtime behaviour is now just "find the file that is already there".

    Order:
    1. Frozen one-dir bundle: ``<app dir>/_internal/ups_label_cropper/bin/``.
    2. Frozen one-dir variant: ``<app dir>/bin/`` (if datas are ever relocated).
    3. Legacy upgrade path: the ``%APPDATA%/UPS-Label-Cropper/bin/`` copy left
       behind by one-file builds <= 1.5.0. Read-only, so upgraders keep printing.
    4. Dev/source checkout: ``bin/`` next to this module.
    """
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
        candidates.append(app_dir / "_internal" / "ups_label_cropper" / "bin" / _SUMATRA_EXE_NAME)
        candidates.append(app_dir / "bin" / _SUMATRA_EXE_NAME)

        # Legacy copy from pre-one-dir releases (read-only fallback only).
        try:
            import platformdirs

            candidates.append(
                Path(platformdirs.user_data_dir("UPS-Label-Cropper")) / "bin" / _SUMATRA_EXE_NAME
            )
        except Exception:
            pass

    # Dev/source checkout (also the frozen last resort, harmless).
    candidates.append(Path(__file__).resolve().parent / "bin" / _SUMATRA_EXE_NAME)
    return candidates


def _resolve_print_binary() -> Path:
    """Resolve the SumatraPDF path to use for a print job (read-only)."""
    candidates = _sumatra_candidates()
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Bundled {_SUMATRA_EXE_NAME} not found. Looked in:\n  "
        + "\n  ".join(str(c) for c in candidates)
        + "\nPlease ensure SumatraPDF.exe is placed in the bin/ directory."
    )


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