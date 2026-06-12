# UPS Label Cropper

Auto-rotates and scales UPS shipping labels for thermal printer printing.

## Target Dimensions

- **Width:** 100mm (283.5 points)
- **Height:** 150mm (425.2 points)
- **Orientation:** Portrait

## Installation

```bash
uv sync
```

## Usage

### CLI

```bash
uv run python -m ups_label_cropper.crop input.pdf output.pdf
```

### Python API

```python
from ups_label_cropper import process_label

process_label("input.pdf", "output.pdf")
```

## Features

- **Auto-detection:** Detects landscape content within PDFs and rotates accordingly
- **Content-aware:** Uses embedded image/drawing dimensions, not page size, for rotation decision
- **Aspect-preserving:** Scales content to fit within target bounds while maintaining aspect ratio
- **Centered output:** Places processed label in center of portrait page

## How It Works

1. Analyzes PDF content (images or drawings) to determine actual label dimensions
2. If content is landscape, rotates 90° counter-clockwise to portrait orientation
3. Scales content to fit within 100mm × 150mm bounds
4. Centers the processed label on a portrait page
5. Saves output as a new PDF at exactly 283.5pt × 425.2pt