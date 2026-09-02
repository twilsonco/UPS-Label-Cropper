import io
import logging
import sys
from pathlib import Path

import fitz
from PIL import Image

logger = logging.getLogger(__name__)

TARGET_WIDTH_PT = 283.5
TARGET_HEIGHT_PT = 425.2

# A detected label must be at least this large (in points) to be considered a
# real label rather than a stray mark or artifact. Roughly 0.7" x 0.7".
MIN_LABEL_WIDTH_PT = 50.0
MIN_LABEL_HEIGHT_PT = 50.0


def get_page_info(page):
    width = page.rect.width
    height = page.rect.height
    return width, height


def is_landscape(width, height):
    return width > height


def calculate_scale_factor(content_width, content_height):
    scale_x = TARGET_WIDTH_PT / content_width
    scale_y = TARGET_HEIGHT_PT / content_height
    return min(scale_x, scale_y)


def get_page_halves(page):
    """Split a page into its top and bottom halves.

    Returns a tuple of (top_rect, bottom_rect) in page coordinates. UPS
    multi-label sheets place one label in each half, so each half is processed
    independently.
    """
    rect = page.rect
    mid_y = rect.height / 2.0
    top = fitz.Rect(rect.x0, rect.y0, rect.x1, mid_y)
    bottom = fitz.Rect(rect.x0, mid_y, rect.x1, rect.y1)
    return top, bottom


def _content_rects_for_half(page, clip):
    """Return content rectangles (page coords) belonging to the half in ``clip``.

    Each embedded image is assigned to the half that contains its vertical
    center, so a label that slightly crosses the midline is still captured in
    full rather than being sliced in two. Vector drawings are only consulted
    when the page contains no images at all.
    """
    mid_y = page.rect.height / 2.0
    clip_center_y = (clip.y0 + clip.y1) / 2.0
    is_top = clip_center_y < mid_y

    def belongs(rect):
        center_y = (rect.y0 + rect.y1) / 2.0
        return (center_y < mid_y) == is_top

    rects = []
    for info in page.get_image_info():
        bbox = info.get("bbox")
        if not bbox:
            continue
        rect = fitz.Rect(bbox) & page.rect
        if not rect.is_empty and belongs(rect):
            rects.append(rect)

    if rects:
        return rects

    # Pure-vector label fallback: only when the page has no images at all.
    if page.get_image_info():
        return []

    for d in page.get_drawings():
        rect = d.get("rect")
        if not rect:
            continue
        rect = fitz.Rect(rect) & page.rect
        if not rect.is_empty and belongs(rect):
            rects.append(rect)
    return rects


def detect_label_bbox(page, clip):
    """Detect the bounding box of a label contained within ``clip``.

    Returns a ``fitz.Rect`` (in page coordinates) covering the label content
    assigned to the half described by ``clip``, or ``None`` when that half has
    no label. Returning ``None`` lets callers skip blank halves.

    Regions smaller than ``MIN_LABEL_WIDTH_PT``/``MIN_LABEL_HEIGHT_PT`` are
    treated as noise and ignored.
    """
    clip = fitz.Rect(clip) & page.rect
    if clip.is_empty:
        return None

    rects = _content_rects_for_half(page, clip)
    if not rects:
        return None

    union = rects[0]
    for rect in rects[1:]:
        union |= rect

    if union.is_empty:
        return None
    if union.width < MIN_LABEL_WIDTH_PT or union.height < MIN_LABEL_HEIGHT_PT:
        return None
    return union


def _render_label_to_page(src_page, label_bbox, out_doc):
    """Render one detected label onto a new 4x6in page in ``out_doc``.

    The label region is captured at high DPI, rotated 90 degrees CCW when
    sideways (landscape), and centered on the output page with a ~1mm margin.
    """
    content_width = label_bbox.width
    content_height = label_bbox.height
    rotate = is_landscape(content_width, content_height)

    # Landscape labels are captured at higher DPI (source is typically ~96 DPI,
    # so capture above that to preserve detail).
    capture_dpi = 300 if rotate else 150
    capture_scale = capture_dpi / 72.0

    src_pix = src_page.get_pixmap(
        matrix=fitz.Matrix(capture_scale, capture_scale),
        clip=label_bbox,
        alpha=False,
    )

    out_page = out_doc.new_page(width=TARGET_WIDTH_PT, height=TARGET_HEIGHT_PT)

    if rotate:
        # Rotate the captured bitmap 90 degrees CCW with Pillow and embed it
        # upright; this keeps placement math simple and exact.
        img = Image.frombytes("RGB", [src_pix.width, src_pix.height], src_pix.samples)
        img = img.transpose(Image.ROTATE_90)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        stream = buf.getvalue()

        # After rotation the content occupies (height x width) points.
        place_w, place_h = content_height, content_width
    else:
        stream = None
        place_w, place_h = content_width, content_height

    # Scale to fit the target with a ~1mm margin on all sides, centered.
    MARGIN_PT = 3.0
    effective_w = TARGET_WIDTH_PT - 2 * MARGIN_PT
    effective_h = TARGET_HEIGHT_PT - 2 * MARGIN_PT
    scale_factor = min(effective_w / place_w, effective_h / place_h)

    final_w = place_w * scale_factor
    final_h = place_h * scale_factor
    offset_x = (TARGET_WIDTH_PT - final_w) / 2
    offset_y = (TARGET_HEIGHT_PT - final_h) / 2

    rect = fitz.Rect(offset_x, offset_y, offset_x + final_w, offset_y + final_h)
    if stream is not None:
        out_page.insert_image(rect, stream=stream)
    else:
        out_page.insert_image(rect, pixmap=src_pix)

    orientation = "landscape (rotated 90° CCW)" if rotate else "portrait"
    logger.info(
        f"    Label {content_width:.1f}x{content_height:.1f}pt -> "
        f"{orientation}, {capture_dpi} DPI, {final_w:.0f}x{final_h:.0f}pt"
    )


def process_label(input_path: str, output_path: str) -> None:
    """Process a UPS label PDF into one 4x6in label page per detected label.

    Handles single-label PDFs as well as multi-label sheets: every page is
    split into top and bottom halves, and each half that contains a label is
    cropped, rotated if sideways, and emitted as its own output page. Halves
    without a label are skipped.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    logger.info(f"Processing label: {input_path.name} -> {output_path}")

    doc = fitz.open(str(input_path))
    try:
        if len(doc) == 0:
            raise ValueError("PDF has no pages")

        out_doc = fitz.open()
        label_count = 0
        try:
            for page_idx, src_page in enumerate(doc):
                top_half, bottom_half = get_page_halves(src_page)
                for half_name, half in (("top", top_half), ("bottom", bottom_half)):
                    label_bbox = detect_label_bbox(src_page, half)
                    if label_bbox is None:
                        logger.debug(
                            f"  No label in page {page_idx + 1} {half_name} half, skipping"
                        )
                        continue
                    label_count += 1
                    logger.info(
                        f"  Found label {label_count} in page {page_idx + 1} {half_name} half"
                    )
                    _render_label_to_page(src_page, label_bbox, out_doc)

            if label_count == 0:
                raise ValueError("No UPS labels detected in PDF")

            out_doc.save(str(output_path))
        finally:
            out_doc.close()
    finally:
        doc.close()

    logger.info(f"  Saved {label_count} label(s): {output_path}")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.pdf> <output.pdf>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    process_label(input_path, output_path)
    print(f"Processed label saved to {output_path}")


if __name__ == "__main__":
    main()