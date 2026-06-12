import sys
from pathlib import Path

import fitz

TARGET_WIDTH_PT = 283.5
TARGET_HEIGHT_PT = 425.2


def get_page_info(page):
    width = page.rect.width
    height = page.rect.height
    return width, height


def get_content_bounds(page):
    """Get content dimensions in points (not pixels) for proper scaling."""
    # First try to get displayed image bounds from page info
    img_info = page.get_image_info()
    if img_info:
        bbox = img_info[0].get("bbox")
        if bbox:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            return width, height

    # Fallback: try drawings bounds
    drawings = page.get_drawings()
    if drawings:
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), 0, 0
        for d in drawings:
            rect = d.get("rect")
            if rect:
                min_x = min(min_x, rect.x0)
                min_y = min(min_y, rect.y0)
                max_x = max(max_x, rect.x1)
                max_y = max(max_y, rect.y1)
        if min_x != float("inf"):
            return max_x - min_x, max_y - min_y

    # Final fallback: use page dimensions
    return page.rect.width, page.rect.height


def is_landscape(width, height):
    return width > height


def calculate_scale_factor(content_width, content_height):
    scale_x = TARGET_WIDTH_PT / content_width
    scale_y = TARGET_HEIGHT_PT / content_height
    return min(scale_x, scale_y)


def get_content_bbox(page):
    """Get the bounding box of content in page coordinates."""
    img_info = page.get_image_info()
    if img_info:
        bbox = img_info[0].get("bbox")
        if bbox:
            return bbox

    drawings = page.get_drawings()
    if drawings:
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), 0, 0
        for d in drawings:
            rect = d.get("rect")
            if rect:
                min_x = min(min_x, rect.x0)
                min_y = min(min_y, rect.y0)
                max_x = max(max_x, rect.x1)
                max_y = max(max_y, rect.y1)
        if min_x != float("inf"):
            return (min_x, min_y, max_x, max_y)

    return (0, 0, page.rect.width, page.rect.height)


def process_label(input_path: str, output_path: str) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)

    doc = fitz.open(str(input_path))
    if len(doc) == 0:
        raise ValueError("PDF has no pages")

    src_page = doc[0]

    # Get content bounds and bbox
    content_width, content_height = get_content_bounds(src_page)
    content_bbox = get_content_bbox(src_page)

    rotate = is_landscape(content_width, content_height)

    out_doc = fitz.open()
    out_page = out_doc.new_page(width=TARGET_WIDTH_PT, height=TARGET_HEIGHT_PT)

    if rotate:
        # Landscape: capture content region at higher DPI for quality
        # Source content is typically ~96 DPI, so capture above that to preserve detail
        CAPTURE_DPI = 300   
        capture_scale = CAPTURE_DPI / 72.0

        clip_rect = fitz.Rect(content_bbox)
        src_pix = src_page.get_pixmap(
            matrix=fitz.Matrix(capture_scale, capture_scale),
            clip=clip_rect,
            alpha=True
        )

        # Calculate scale to fit rotated content within target bounds with ~1mm margin
        MARGIN_PT = 3.0  # ~1mm margin on all sides
        effective_w = TARGET_WIDTH_PT - 2 * MARGIN_PT
        effective_h = TARGET_HEIGHT_PT - 2 * MARGIN_PT

        rot_content_w = content_height
        rot_content_h = content_width

        scale_factor = min(effective_w / rot_content_w, effective_h / rot_content_h)
        scale_factor *= 1.12

        # Final dimensions after scaling
        final_rot_w = rot_content_w * scale_factor
        final_rot_h = rot_content_h * scale_factor

        # Center offsets for 90° CCW rotation placement
        offset_x = (TARGET_WIDTH_PT - final_rot_w) / 2
        offset_y = (TARGET_HEIGHT_PT - final_rot_h) / 2

        out_page.insert_image(
            fitz.Rect(offset_x, offset_y-65, offset_x + final_rot_w, offset_y + final_rot_h),
            pixmap=src_pix,
            rotate=90,
        )
    else:
        # Portrait: capture content region at higher DPI for quality
        CAPTURE_DPI = 150
        capture_scale = CAPTURE_DPI / 72.0

        clip_rect = fitz.Rect(content_bbox)
        src_pix = src_page.get_pixmap(
            matrix=fitz.Matrix(capture_scale, capture_scale),
            clip=clip_rect,
            alpha=True
        )

        # Scale captured content to fit with ~1mm margin
        MARGIN_PT = 3.0  # ~1mm margin on all sides
        effective_w = TARGET_WIDTH_PT - 2 * MARGIN_PT
        effective_h = TARGET_HEIGHT_PT - 2 * MARGIN_PT

        scale_factor = min(effective_w / content_width, effective_h / content_height)
        scale_factor *= 1.05

        final_width = content_width * scale_factor
        final_height = content_height * scale_factor

        offset_x = (TARGET_WIDTH_PT - final_width) / 2
        offset_y = (TARGET_HEIGHT_PT - final_height) / 2

        out_page.insert_image(
            fitz.Rect(offset_x, offset_y, offset_x + final_width, offset_y + final_height),
            pixmap=src_pix,
        )

    out_doc.save(str(output_path))
    doc.close()
    out_doc.close()


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