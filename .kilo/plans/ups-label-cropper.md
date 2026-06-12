# UPS Label Cropper Tool Plan

## Goal
Create a Python tool using `uv` that:
1. Reads a UPS label PDF
2. Auto-rotates if necessary (landscape → portrait)
3. Outputs a portrait PDF at **150mm high × 100mm wide** for thermal printer printing

---

## Technical Details

### Dimensions
- Target: Portrait orientation
- Width: 100mm = **283.5 points** (1mm = 2.834645669pt)
- Height: 150mm = **425.2 points**

### PDF Point Conversion
```
100mm × 283.46pt/mm = 283.5pt
150mm × 283.46pt/mm = 425.2pt
```

---

## Implementation Plan

### Step 1: Project Setup
- Initialize Python project with `uv`
- Add dependency: **PyMuPDF** (fitz) - handles PDF reading, rotation, and writing

### Step 2: Analyze Input PDF
- Read the input PDF using PyMuPDF
- Get page dimensions and content bounding box
- Detect if landscape vs portrait via page width/height comparison

### Step 3: Auto-Rotation Logic
- If page is landscape (width > height), rotate 90° counter-clockwise
- Use PyMuPDF `Page.rotate()` or matrix transformation

### Step 4: Scale to Target Dimensions
- Calculate scale factor to fit within 100mm × 150mm bounds while preserving aspect ratio
- Apply scaling via PyMuPDF transformation matrix

### Step 5: Output PDF
- Create new PDF with single page at target dimensions (283.5pt × 425.2pt)
- Embed the processed/rotated/scaled label content
- Save to output path

---

## File Structure
```
ups-label-cropper/
├── pyproject.toml          # uv project config
├── src/
│   └── ups_label_cropper/
│       ├── __init__.py
│       └── crop.py         # Main processing logic
└── tests/
    └── test_crop.py        # Unit tests
```

---

## CLI Interface
```bash
uv run python -m ups_label_cropper input.pdf output.pdf
```
Or via a Python API:
```python
from ups_label_cropper import process_label
process_label("input.pdf", "output.pdf")
```

---

## Questions / Clarifications Needed

1. **Tolerance**: Should the tool crop to exact dimensions or scale to fit within (allowing some margin)?
2. **Background**: If scaling creates empty space, should it be white background or transparent?
3. **Multiple labels**: The sample PDF has 1 page - should the tool handle multi-page PDFs (process each page)?

---

## Verification
- Test with `label.pdf` input to verify correct portrait output at 100×150mm
