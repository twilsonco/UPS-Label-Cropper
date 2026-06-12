import sys
from pathlib import Path

import fitz

TARGET_WIDTH_PT = 283.5
TARGET_HEIGHT_PT = 425.2


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


def process_label(input_path: str, output_path: str) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)

    doc = fitz.open(str(input_path))
    if len(doc) == 0:
        raise ValueError("PDF has no pages")

    src_page = doc[0]
    width, height = get_page_info(src_page)

    rotate = 0
    if is_landscape(width, height):
        rotate = 270
        width, height = height, width

    scale_factor = calculate_scale_factor(width, height)
    final_width = width * scale_factor
    final_height = height * scale_factor

    dest_rect = fitz.Rect(0, 0, TARGET_WIDTH_PT, TARGET_HEIGHT_PT)
    clip_rect = fitz.Rect(0, 0, final_width, final_height)

    out_doc = fitz.open()
    out_page = out_doc.new_page(width=TARGET_WIDTH_PT, height=TARGET_HEIGHT_PT)

    out_page.show_pdf_page(
        dest_rect,
        doc,
        0,
        clip=clip_rect,
        rotate=rotate,
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