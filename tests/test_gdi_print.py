"""Tests for the native GDI printing module (fully mocked).

pywin32 cannot be imported on macOS, so ``win32ui``/``win32print``/
``win32con``/``win32gui`` are injected into ``sys.modules`` and the gdi32
ctypes handle is replaced with a mock. The pure helpers (``_fit_dest_rect``,
``_build_bitmapinfo``, ``_render_page_to_dib``) run against real
PyMuPDF/Pillow output — the DIB byte-order checks are what catch the
colour-inversion (cyan label) bug, which fails silently on real hardware.
"""

import sys
import types
from unittest.mock import MagicMock

import fitz
import pytest

from ups_label_cropper import gdi_print, printer


# Real win32con values (stable Windows constants). The module under test only
# uses them as GetDeviceCaps indices / mode flags, so these exact values are
# for readability; the mock maps them to controlled device geometry.
WIN32CON = types.SimpleNamespace(
    LOGPIXELSX=88,
    LOGPIXELSY=90,
    HORZRES=8,
    VERTRES=10,
    PHYSICALOFFSETX=13,
    PHYSICALOFFSETY=14,
    MM_TEXT=1,
    HALFTONE=3,
)


def _make_pdf(tmp_path, pages=1, red=False, size=(283.5, 425.2)):
    """Write a real PDF with *pages* pages (optionally a red top-left square)."""
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=size[0], height=size[1])
        if red:
            page.draw_rect(fitz.Rect(0, 0, 10, 10), color=(1, 0, 0), fill=(1, 0, 0))
    path = tmp_path / "labels.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def win32(monkeypatch):
    """Patch sys.platform, the win32* modules, and the gdi32 handle.

    Mock device: 203 dpi, 800 x 1200 printable area, zero physical offsets.
    """
    monkeypatch.setattr(sys, "platform", "win32")

    win32print = MagicMock()
    win32print.GetDefaultPrinter.return_value = "System Default LP"
    win32print.EnumPrinters.return_value = [
        (1, "", "System Default LP", ""),
        (2, "", "Zebra ZD421", ""),
    ]
    win32print.PRINTER_ENUM_LOCAL = 2
    win32print.PRINTER_ENUM_CONNECTIONS = 4

    win32ui = MagicMock()
    dc = win32ui.CreateDC.return_value
    caps = {
        WIN32CON.LOGPIXELSX: 203,
        WIN32CON.LOGPIXELSY: 203,
        WIN32CON.HORZRES: 800,
        WIN32CON.VERTRES: 1200,
        WIN32CON.PHYSICALOFFSETX: 0,
        WIN32CON.PHYSICALOFFSETY: 0,
    }
    dc.GetDeviceCaps.side_effect = lambda idx: caps[idx]
    dc.GetSafeHdc.return_value = 0x1234

    win32gui = MagicMock()

    monkeypatch.setitem(sys.modules, "win32print", win32print)
    monkeypatch.setitem(sys.modules, "win32ui", win32ui)
    monkeypatch.setitem(sys.modules, "win32con", WIN32CON)
    monkeypatch.setitem(sys.modules, "win32gui", win32gui)

    gdi32 = MagicMock()
    gdi32.StretchDIBits.return_value = 1
    monkeypatch.setattr(gdi_print, "_get_gdi32", lambda: gdi32)

    return types.SimpleNamespace(
        win32print=win32print,
        win32ui=win32ui,
        win32gui=win32gui,
        dc=dc,
        gdi32=gdi32,
    )


class TestFitDestRect:
    def test_exact_fit_no_offsets(self):
        assert gdi_print._fit_dest_rect(800, 1200, 800, 1200, 0, 0) == (0, 0, 800, 1200)

    def test_downscale_centred_with_offsets(self):
        # 203 dpi 4x6 page on a device whose printable area is inset by 8 px.
        # scale = min(784/800, 1184/1200) = 0.98 -> 784 x 1176.
        dx, dy, dw, dh = gdi_print._fit_dest_rect(800, 1200, 784, 1184, 8, 8)
        assert (dw, dh) == (784, 1176)
        # Centred inside the printable area, then offset by the physical margins.
        assert dx == 8 + (784 - 784) // 2
        assert dy == 8 + (1184 - 1176) // 2

    def test_never_upscales(self):
        # Small image on a big device: scale capped at 1.0, centred.
        assert gdi_print._fit_dest_rect(100, 100, 800, 1200, 0, 0) == (350, 550, 100, 100)

    def test_wide_image_fits_portrait_device_aspect_preserved(self):
        dx, dy, dw, dh = gdi_print._fit_dest_rect(1200, 300, 800, 1200, 0, 0)
        assert (dw, dh) == (800, 200)  # width-limited, aspect 4:1 preserved
        assert (dx, dy) == (0, 500)
        assert dx + dw <= 800 and dy + dh <= 1200

    def test_rect_always_inside_printable_area(self):
        # Offset-heavy device: dest must stay within [offset, offset + res].
        dx, dy, dw, dh = gdi_print._fit_dest_rect(800, 1200, 700, 1100, 20, 30)
        assert 20 <= dx and dx + dw <= 20 + 700
        assert 30 <= dy and dy + dh <= 30 + 1100


class TestRenderPageToDib:
    def test_dib_is_topdown_bgrx_4bpp(self, tmp_path):
        """A red pixel must come out as BGRX (0, 0, 255, 0).

        Regression guard for the colour-inversion trap: passing PyMuPDF's
        RGB bytes straight to GDI renders labels cyan-tinted with no error.
        """
        path = _make_pdf(tmp_path, pages=1, red=True, size=(100, 100))
        doc = fitz.open(str(path))
        try:
            bits, w, h = gdi_print._render_page_to_dib(doc.load_page(0), 72, 72)
        finally:
            doc.close()
        assert (w, h) == (100, 100)
        assert len(bits) == w * h * 4  # 32-bit, rows aligned by construction
        assert tuple(bits[0:4]) == (0, 0, 255, 0)  # R=255,G=0,B=0 -> B,G,R,X

    def test_renders_at_printer_dpi_1_to_1(self, tmp_path):
        """203 dpi render of a 4x6in page is ~800 px wide (device units)."""
        path = _make_pdf(tmp_path, pages=1)
        doc = fitz.open(str(path))
        try:
            bits, w, h = gdi_print._render_page_to_dib(doc.load_page(0), 203, 203)
        finally:
            doc.close()
        assert abs(w - 800) <= 1
        assert abs(h - 1200) <= 1
        assert len(bits) == w * h * 4


class TestBuildBitmapinfo:
    def test_header_fields(self):
        import ctypes

        bmi = gdi_print._build_bitmapinfo(800, 1200, 800 * 1200 * 4)
        hdr = bmi.bmiHeader
        assert hdr.biSize == ctypes.sizeof(gdi_print._BITMAPINFOHEADER)
        assert hdr.biWidth == 800
        assert hdr.biHeight == -1200  # negative == top-down rows
        assert hdr.biPlanes == 1
        assert hdr.biBitCount == 32
        assert hdr.biCompression == 0  # BI_RGB
        assert hdr.biSizeImage == 800 * 1200 * 4


class TestPrintPdfFlow:
    def test_two_pages_two_startpage_one_doc(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=2)

        assert gdi_print.print_pdf(path) is True

        dc = win32.dc
        assert dc.StartDoc.call_count == 1
        assert dc.StartDoc.call_args[0][0] == gdi_print.DOC_NAME
        assert dc.StartPage.call_count == 2
        assert dc.EndPage.call_count == 2
        assert dc.EndDoc.call_count == 1
        assert dc.AbortDoc.call_count == 0
        dc.DeleteDC.assert_called_once()

    def test_midjob_failure_aborts_but_deletes_dc(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=2)
        win32.gdi32.StretchDIBits.side_effect = [1, RuntimeError("blip failed")]

        with pytest.raises(RuntimeError):
            gdi_print.print_pdf(path)

        dc = win32.dc
        dc.AbortDoc.assert_called_once()
        dc.DeleteDC.assert_called_once()
        dc.EndDoc.assert_not_called()

    def test_startpage_failure_aborts_job(self, tmp_path, win32):
        """StartPage failing after StartDoc must abort the spooler job."""
        path = _make_pdf(tmp_path, pages=2)
        win32.dc.StartPage.side_effect = RuntimeError("startpage failed")

        with pytest.raises(RuntimeError):
            gdi_print.print_pdf(path)

        dc = win32.dc
        dc.AbortDoc.assert_called_once()
        dc.EndPage.assert_not_called()
        dc.EndDoc.assert_not_called()
        dc.DeleteDC.assert_called_once()

    def test_endpage_failure_aborts_job(self, tmp_path, win32):
        """EndPage failing after StartDoc must abort, not leave a partial job."""
        path = _make_pdf(tmp_path, pages=2)
        win32.dc.EndPage.side_effect = RuntimeError("endpage failed")

        with pytest.raises(RuntimeError):
            gdi_print.print_pdf(path)

        dc = win32.dc
        dc.AbortDoc.assert_called_once()
        dc.EndDoc.assert_not_called()
        dc.DeleteDC.assert_called_once()

    def test_enddoc_failure_also_aborts(self, tmp_path, win32):
        """A failing EndDoc (after all pages) still aborts exactly once."""
        path = _make_pdf(tmp_path, pages=1)
        win32.dc.EndDoc.side_effect = RuntimeError("spooler died")

        with pytest.raises(RuntimeError):
            gdi_print.print_pdf(path)

        win32.dc.AbortDoc.assert_called_once()

    def test_unknown_printer_raises_and_no_dc_created(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)

        with pytest.raises(ValueError, match="Printer not found: Nope"):
            gdi_print.print_pdf(path, printer_name="Nope")

        win32.win32ui.CreateDC.assert_not_called()

    def test_none_printer_resolves_default(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)

        assert gdi_print.print_pdf(path) is True

        win32.dc.CreatePrinterDC.assert_called_once_with("System Default LP")

    def test_explicit_printer_used(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)

        assert gdi_print.print_pdf(path, printer_name="Zebra ZD421") is True

        win32.dc.CreatePrinterDC.assert_called_once_with("Zebra ZD421")

    def test_no_default_printer_raises_oserror(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)
        win32.win32print.GetDefaultPrinter.side_effect = RuntimeError("no spooler")

        with pytest.raises(OSError, match="No printer specified"):
            gdi_print.print_pdf(path)

    def test_zero_pages_raises_valueerror(self, tmp_path, win32):
        # PyMuPDF refuses to save a zero-page doc, so hand-write a minimal
        # valid PDF whose page tree is empty.
        body = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        )
        xref_pos = len(body)
        xref = (
            b"xref\n0 3\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
            b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
        )
        path = tmp_path / "empty.pdf"
        path.write_bytes(body + xref)

        with pytest.raises(ValueError, match="PDF has no pages"):
            gdi_print.print_pdf(path)

        win32.win32ui.CreateDC.assert_not_called()

    def test_missing_file_raises_file_not_found(self, tmp_path, win32):
        with pytest.raises(FileNotFoundError):
            gdi_print.print_pdf(tmp_path / "nope.pdf")

    def test_delete_dc_runs_when_enddoc_raises(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)
        win32.dc.EndDoc.side_effect = RuntimeError("spooler died")

        with pytest.raises(RuntimeError):
            gdi_print.print_pdf(path)

        win32.dc.DeleteDC.assert_called_once()

    def test_halftone_mode_and_brush_org_reset(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)

        gdi_print.print_pdf(path)

        win32.dc.SetMapMode.assert_called_with(WIN32CON.MM_TEXT)
        win32.win32gui.SetStretchBltMode.assert_called_with(0x1234, WIN32CON.HALFTONE)
        win32.dc.SetBrushOrg.assert_called_with((0, 0))

    def test_dest_rect_fits_and_is_centred(self, tmp_path, win32):
        path = _make_pdf(tmp_path, pages=1)

        gdi_print.print_pdf(path)

        args = win32.gdi32.StretchDIBits.call_args[0]
        hdc, dx, dy, dw, dh, sx, sy, sw, sh = args[:9]
        assert hdc == 0x1234
        assert (sx, sy) == (0, 0)
        assert dw <= sw and dh <= sh  # fit, never upscale
        assert dw <= 800 and dh <= 1200  # inside HORZRES x VERTRES
        assert dx == (800 - dw) // 2  # centred, zero offsets
        assert dy == (1200 - dh) // 2

    def test_dib_passed_to_stretchdibits(self, tmp_path, win32):
        """End-to-end: the buffer GDI receives is 4bpp top-down BGRX."""
        path = _make_pdf(tmp_path, pages=1, red=True, size=(100, 100))
        # Re-aim the mock device at 72 dpi so the 100x100pt page is 100x100 px.
        caps = {
            WIN32CON.LOGPIXELSX: 72,
            WIN32CON.LOGPIXELSY: 72,
            WIN32CON.HORZRES: 800,
            WIN32CON.VERTRES: 1200,
            WIN32CON.PHYSICALOFFSETX: 0,
            WIN32CON.PHYSICALOFFSETY: 0,
        }
        win32.dc.GetDeviceCaps.side_effect = lambda idx: caps[idx]

        gdi_print.print_pdf(path)

        args = win32.gdi32.StretchDIBits.call_args[0]
        bits, bmi, usage, rop = args[9], args[10], args[11], args[12]
        w, h = bmi.bmiHeader.biWidth, -bmi.bmiHeader.biHeight
        assert (w, h) == (100, 100)
        assert bmi.bmiHeader.biHeight < 0  # top-down
        assert len(bits) == w * h * 4
        assert tuple(bits[0:4]) == (0, 0, 255, 0)  # red -> BGRX
        assert usage == 0  # DIB_RGB_COLORS
        assert rop == 0x00CC00CC  # SRCCOPY


class TestPrinterFacade:
    def test_non_windows_raises_oserror(self, tmp_path, monkeypatch):
        path = _make_pdf(tmp_path, pages=1)
        monkeypatch.setattr(sys, "platform", "darwin")

        with pytest.raises(OSError, match="only supported on Windows"):
            printer.print_pdf(path)

    def test_missing_file_raises_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")

        with pytest.raises(FileNotFoundError):
            printer.print_pdf(tmp_path / "nope.pdf")

    def test_delegates_to_gdi_print(self, tmp_path, monkeypatch):
        path = _make_pdf(tmp_path, pages=1)
        monkeypatch.setattr(sys, "platform", "win32")
        calls = []

        def fake_print_pdf(pdf_path, printer_name=None):
            calls.append((pdf_path, printer_name))
            return True

        monkeypatch.setattr(gdi_print, "print_pdf", fake_print_pdf)

        assert printer.print_pdf(path, printer_name="Zebra") is True
        assert calls == [(path, "Zebra")]

    def test_sumatra_helpers_are_gone(self):
        """The SumatraPDF subprocess path must not come back."""
        for name in ("_sumatra_candidates", "_resolve_print_binary", "_SUMATRA_EXE_NAME"):
            assert not hasattr(printer, name), f"printer.{name} was removed on purpose"
