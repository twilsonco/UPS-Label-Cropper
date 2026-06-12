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
    images = page.get_images(full=True)
    if images:
        for img in images:
            img_width, img_height = img[2], img[3]
            return img_width, img_height
    drawings = page.get_drawings()
    if drawings:
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), 0, 0
        for d in drawings:
            rect = d.get('rect')
            if rect:
                min_x = min(min_x, rect.x0)
                min_y = min(min_y, rect.y0)
                max_x = max(max_x, rect.x1)
                max_y = max(max_y, rect.y1)
        if min_x != float('inf'):
            return max_x - min_x, max_y - min_y
    width = page.rect.width
    height = page.rect.height
    return width, height


def is_landscape(width, height):
    return width > height


def calculate_scale_factor(content_width, content_height):
    scale_x = TARGET_WIDTH_PT / content_width
    scale_y = TARGET_HEIGHT_PT / content_height
    return min(scale_x, scale_y)


def process_label(input_path: str, output_path: str) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)

    doc = fitz.open(str(input_path))
    if len(doc) == 0:
        raise ValueError("PDF has no pages")

    src_page = doc[0]
    content_width, content_height = get_content_bounds(src_page)

    width, height = content_width, content_height
    rotate = is_landscape(content_width, content_height)
    if rotate:
        width, height = content_height, content_width

    scale_factor = calculate_scale_factor(width, height)
    final_width = width * scale_factor
    final_height = height * scale_factor

    offset_x = (TARGET_WIDTH_PT - final_width) / 2
    offset_y = (TARGET_HEIGHT_PT - final_height) / 2

    out_doc = fitz.open()
    out_page = out_doc.new_page(width=TARGET_WIDTH_PT, height=TARGET_HEIGHT_PT)

    if rotate:
        matrix = fitz.Matrix(0, scale_factor, -scale_factor, 0, 0, content_width * scale_factor)
    else:
        matrix = fitz.Matrix(scale_factor, 0, 0, scale_factor, offset_x, offset_y)

    pix = src_page.get_pixmap(matrix=matrix, alpha=True)
    out_page.insert_image(
        fitz.Rect(offset_x, offset_y, offset_x + final_width, offset_y + final_height),
        pixmap=pix,
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