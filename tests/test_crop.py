import pytest
from unittest.mock import MagicMock, patch
from ups_label_cropper.crop import (
    is_landscape,
    calculate_scale_factor,
    get_page_info,
)


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