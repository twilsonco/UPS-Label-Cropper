"""Native Windows GDI printing (no third-party PDF viewer).

Replaces the old SumatraPDF subprocess: each PDF page is rendered with
PyMuPDF at the printer's own DPI and blitted onto the printer device
context with ``StretchDIBits``. One label per page, 1:1 pixel mapping,
no resampling blur, and no bundled external executable in the build.

Windows-only. ``pywin32`` cannot be imported on macOS, so every ``win32*``
import happens **inside functions**; this module and its pure helpers stay
importable everywhere so the test suite can run on macOS.

Implementation note on pywin32 (verified against the pywin32 source, not
from memory): ``win32ui``'s ``PyCDC`` exposes the DC/job lifecycle
(``CreatePrinterDC``, ``StartDoc``/``StartPage``/``EndPage``/``EndDoc``/
``AbortDoc``, ``GetDeviceCaps``, ``SetMapMode``, ``SetBrushOrg``, ...) but
does **not** expose ``StretchDIBits`` -- there is no DIB entry in the
``PyCDC`` method table and no ``win32ui.BITMAPINFO`` factory. The blit
therefore goes through ``ctypes`` to ``gdi32.StretchDIBits`` (stdlib; no
new runtime dependency). ``HALFTONE`` stretch mode is set via
``win32gui.SetStretchBltMode`` on the raw HDC, followed by
``dc.SetBrushOrg((0, 0))`` -- without the brush-origin reset, HALFTONE
banding shifts the image on thermal printers.
"""

import ctypes
import logging
import sys
from pathlib import Path

import fitz
from PIL import Image

logger = logging.getLogger(__name__)

DOC_NAME = "UPS Label Cropper"

# win32con constants duplicated as literals so the pure helpers stay
# importable (and testable) on macOS. Values verified against win32con.py:
# BI_RGB == 0, DIB_RGB_COLORS == 0, SRCCOPY == 0x00CC00CC.
_BI_RGB = 0
_DIB_RGB_COLORS = 0
_SRCCOPY = 0x00CC00CC


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class _BITMAPINFO(ctypes.Structure):
    # bmiColors is a union in the Win32 header; 3 DWORDs is the canonical
    # ctypes layout and is unused for 32-bit BI_RGB.
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]


_gdi32 = None


def _get_gdi32():
    """Lazily load gdi32 (Windows-only; ``ctypes.WinDLL`` does not exist elsewhere)."""
    global _gdi32
    if _gdi32 is None:
        lib = ctypes.WinDLL("gdi32", use_last_error=True)
        lib.StretchDIBits.argtypes = [
            ctypes.c_void_p,  # HDC
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,  # dest x, y, w, h
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,  # src x, y, w, h
            ctypes.c_void_p,  # lpBits (LPCVOID)
            ctypes.POINTER(_BITMAPINFO),  # lpBitsInfo
            ctypes.c_uint,  # iUsage
            ctypes.c_uint32,  # dwRop
        ]
        lib.StretchDIBits.restype = ctypes.c_int
        _gdi32 = lib
    return _gdi32


def _printer_exists(printer_name: str) -> bool:
    """Return True if *printer_name* is an installed printer (Windows only)."""
    import win32print

    try:
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return any(p[2] == printer_name for p in printers)
    except Exception:
        return False


def _fit_dest_rect(
    img_w: int,
    img_h: int,
    horz_res: int,
    vert_res: int,
    offset_x: int,
    offset_y: int,
) -> tuple[int, int, int, int]:
    """Compute the destination rect for a page image on the printable area.

    Fits the image inside the printable area (``horz_res`` x ``vert_res``)
    preserving aspect ratio, centred, then offsets by the device's physical
    margins (``offset_x``/``offset_y``) -- the printable area is inset from
    the physical page. Never upscales, and the result never extends outside
    the printable area.

    Returns ``(x, y, width, height)`` in device units (MM_TEXT).
    """
    scale = min(horz_res / img_w, vert_res / img_h, 1.0)
    dw = int(img_w * scale)
    dh = int(img_h * scale)
    dx = offset_x + (horz_res - dw) // 2
    dy = offset_y + (vert_res - dh) // 2
    return dx, dy, dw, dh


def _render_page_to_dib(page: "fitz.Page", dpi_x: int, dpi_y: int) -> tuple[bytes, int, int]:
    """Render a PDF page to a Windows-ready DIB buffer.

    Renders at the printer's own DPI so the mapping onto the device is 1:1
    (no resampling blur). Pages produced by ``crop.py`` are already exactly
    4 x 6 in with the label centred.

    Returns ``(bits, width, height)`` where *bits* is a top-down 32-bit
    BGRX buffer: Pillow's ``BGRX`` raw encoder swaps RGB->BGR for GDI and,
    being 4 bytes/pixel, every row is 4-byte aligned by construction -- no
    hand-rolled row padding. The negative ``biHeight`` set in
    :func:`_build_bitmapinfo` matches this top-down row order.
    """
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi_x / 72, dpi_y / 72), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    bits = img.tobytes("raw", "BGRX")
    return bits, pix.width, pix.height


def _build_bitmapinfo(width: int, height: int, size_image: int) -> _BITMAPINFO:
    """Build a 32-bit BI_RGB BITMAPINFO for a top-down DIB.

    ``biHeight`` is **negative**: GDI 24/32-bit DIBs are bottom-up by
    default, while PyMuPDF's ``pixmap.samples`` (and therefore our BGRX
    buffer) is top-down.
    """
    bmi = _BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height  # negative == top-down rows
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = _BI_RGB
    bmi.bmiHeader.biSizeImage = size_image
    return bmi


def _blit_dib(
    hdc: int,
    x: int,
    y: int,
    width: int,
    height: int,
    bits: bytes,
    bmi: _BITMAPINFO,
) -> None:
    """Blit a DIB buffer onto the printer DC via gdi32.StretchDIBits."""
    gdi32 = _get_gdi32()
    src_w = bmi.bmiHeader.biWidth
    src_h = -bmi.bmiHeader.biHeight  # stored negative (top-down)
    drawn = gdi32.StretchDIBits(
        hdc,
        x, y, width, height,
        0, 0, src_w, src_h,
        bits,
        bmi,  # ctypes passes the address automatically for a POINTER argtype
        _DIB_RGB_COLORS,
        _SRCCOPY,
    )
    if drawn == 0:
        err = ctypes.get_last_error()
        raise OSError(f"StretchDIBits failed (gdi32 error {err})")


def print_pdf(pdf_path: Path, printer_name: str | None = None) -> bool:
    """Print every page of *pdf_path* via the Windows GDI print API.

    Same public contract as the old SumatraPDF-based printer: raises
    ``FileNotFoundError`` for a missing file, ``ValueError`` for an unknown
    printer or a page-less PDF, ``OSError`` off-Windows / when no printer
    can be resolved, and returns ``True`` once the job is spooled.
    """
    if sys.platform != "win32":
        raise OSError(f"Printing is only supported on Windows. Current platform: {sys.platform}")

    import win32con
    import win32gui
    import win32print
    import win32ui

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if printer_name is None:
        try:
            printer_name = win32print.GetDefaultPrinter()
        except Exception:
            printer_name = None
        if not printer_name:
            raise OSError("No printer specified and no default printer found")

    if not _printer_exists(printer_name):
        raise ValueError(f"Printer not found: {printer_name}")

    doc = fitz.open(str(pdf_path))
    try:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")

        dc = win32ui.CreateDC()
        try:
            dc.CreatePrinterDC(printer_name)

            dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX)
            dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)
            horz_res = dc.GetDeviceCaps(win32con.HORZRES)
            vert_res = dc.GetDeviceCaps(win32con.VERTRES)
            offset_x = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
            offset_y = dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)

            dc.SetMapMode(win32con.MM_TEXT)
            hdc = dc.GetSafeHdc()

            dc.StartDoc(DOC_NAME)
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                bits, img_w, img_h = _render_page_to_dib(page, dpi_x, dpi_y)
                dx, dy, dw, dh = _fit_dest_rect(img_w, img_h, horz_res, vert_res, offset_x, offset_y)
                bmi = _build_bitmapinfo(img_w, img_h, len(bits))

                dc.StartPage()
                try:
                    win32gui.SetStretchBltMode(hdc, win32con.HALFTONE)
                    dc.SetBrushOrg((0, 0))
                    _blit_dib(hdc, dx, dy, dw, dh, bits, bmi)
                except BaseException:
                    dc.AbortDoc()
                    raise
                dc.EndPage()
            dc.EndDoc()
        finally:
            dc.DeleteDC()

        logger.info(f"[GDI] Printed {doc.page_count} page(s) to '{printer_name}'")
        return True
    finally:
        doc.close()
