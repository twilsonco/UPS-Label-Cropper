import io

import fitz
import pytest
from PIL import Image
from unittest.mock import MagicMock, patch
from ups_label_cropper.crop import (
    is_landscape,
    calculate_scale_factor,
    get_page_info,
    get_page_halves,
    detect_label_bbox,
    process_label,
    TARGET_WIDTH_PT,
    TARGET_HEIGHT_PT,
)


def _make_label_image(width=400, height=240, color=(20, 20, 20)):
    """Build a landscape PNG image (bytes) to embed as a fake label."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_pdf(pages_halves):
    """Create a temp multi-label PDF.

    ``pages_halves`` is a list (one entry per page) of tuples
    ``(has_top, has_bottom)``. Each True places a landscape image in that half.
    Returns a fitz.Document the caller must close.
    """
    doc = fitz.open()
    stream = _make_label_image()
    for has_top, has_bottom in pages_halves:
        page = doc.new_page(width=612, height=792)  # letter
        mid = 396
        if has_top:
            page.insert_image(fitz.Rect(40, 80, 520, 360), stream=stream)
        if has_bottom:
            page.insert_image(fitz.Rect(40, mid + 20, 520, mid + 300), stream=stream)
    return doc


class TestIsLandscape:
    def test_landscape_true(self):
        assert is_landscape(400, 300) is True

    def test_portrait_false(self):
        assert is_landscape(300, 400) is False

    def test_square_false(self):
        assert is_landscape(300, 300) is False


class TestCalculateScaleFactor:
    def test_scale_to_fit_width(self):
        result = calculate_scale_factor(200, 100)
        assert result == pytest.approx(1.4175)

    def test_scale_to_fit_height(self):
        result = calculate_scale_factor(100, 400)
        assert result == pytest.approx(1.063)

    def test_no_scaling_needed(self):
        result = calculate_scale_factor(283.5, 425.2)
        assert result == pytest.approx(1.0)


class TestGetPageInfo:
    def test_returns_dimensions(self):
        mock_page = MagicMock()
        mock_page.rect.width = 400
        mock_page.rect.height = 300

        width, height = get_page_info(mock_page)

        assert width == 400
        assert height == 300


class TestGetPageHalves:
    def test_splits_at_midpoint(self):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        top, bottom = get_page_halves(page)
        assert top.y0 == 0
        assert top.y1 == pytest.approx(396)
        assert bottom.y0 == pytest.approx(396)
        assert bottom.y1 == pytest.approx(792)
        assert top.width == pytest.approx(612)
        assert bottom.width == pytest.approx(612)
        doc.close()


class TestDetectLabelBbox:
    def test_finds_top_label(self):
        doc = _build_pdf([(True, False)])
        page = doc[0]
        top, bottom = get_page_halves(page)
        bbox = detect_label_bbox(page, top)
        assert bbox is not None
        assert bbox.y1 <= 396 + 1  # stays in top half
        doc.close()

    def test_skips_empty_bottom_half(self):
        doc = _build_pdf([(True, False)])
        page = doc[0]
        top, bottom = get_page_halves(page)
        assert detect_label_bbox(page, bottom) is None
        doc.close()

    def test_finds_bottom_only_label(self):
        doc = _build_pdf([(False, True)])
        page = doc[0]
        top, bottom = get_page_halves(page)
        assert detect_label_bbox(page, top) is None
        bbox = detect_label_bbox(page, bottom)
        assert bbox is not None
        assert bbox.y0 >= 396 - 1
        doc.close()

    def test_ignores_tiny_artifacts(self):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        # A tiny speck in the top half should not count as a label.
        page.draw_rect(fitz.Rect(100, 100, 110, 110), color=(0, 0, 0), fill=(0, 0, 0))
        top, _ = get_page_halves(page)
        assert detect_label_bbox(page, top) is None
        doc.close()


class TestProcessLabelMulti:
    def test_single_label_one_output_page(self, tmp_path):
        src = tmp_path / "single.pdf"
        out = tmp_path / "out.pdf"
        doc = _build_pdf([(True, False)])
        doc.save(str(src))
        doc.close()

        process_label(str(src), str(out))

        result = fitz.open(str(out))
        assert len(result) == 1
        assert result[0].rect.width == pytest.approx(TARGET_WIDTH_PT)
        assert result[0].rect.height == pytest.approx(TARGET_HEIGHT_PT)
        result.close()

    def test_multi_label_two_per_page(self, tmp_path):
        src = tmp_path / "multi.pdf"
        out = tmp_path / "out.pdf"
        doc = _build_pdf([(True, True)])
        doc.save(str(src))
        doc.close()

        process_label(str(src), str(out))

        result = fitz.open(str(out))
        assert len(result) == 2
        result.close()

    def test_multi_page_accumulates_all_labels(self, tmp_path):
        src = tmp_path / "multi.pdf"
        out = tmp_path / "out.pdf"
        # page1: 2 labels, page2: 2 labels, page3: 1 label (top only) -> 5
        doc = _build_pdf([(True, True), (True, True), (True, False)])
        doc.save(str(src))
        doc.close()

        process_label(str(src), str(out))

        result = fitz.open(str(out))
        assert len(result) == 5
        # Every output page should carry exactly one embedded image.
        for page in result:
            assert len(page.get_images()) == 1
        result.close()

    def test_raises_when_no_labels(self, tmp_path):
        src = tmp_path / "empty.pdf"
        out = tmp_path / "out.pdf"
        doc = fitz.open()
        doc.new_page(width=612, height=792)  # blank page
        doc.save(str(src))
        doc.close()

        with pytest.raises(ValueError):
            process_label(str(src), str(out))