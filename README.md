# UPS Label Cropper

Auto-rotates and scales UPS shipping labels for thermal printer printing.

## Features

- **Auto-detection** of landscape content within PDFs with automatic 90° counter-clockwise rotation
- **Content-aware scaling** using embedded image/drawing dimensions, not page size
- **Aspect-preserving** scale-to-fit within 100mm × 150mm bounds
- **Centered output** on a portrait page at exactly 283.5pt × 425.2pt (4" × 6")
- **Watch mode** — monitors a folder and auto-processes new PDFs with system tray control
- **Auto-printing** — sends cropped labels directly to a thermal printer via Windows Print API
- **Archive original files** after successful printing

## Target Dimensions

| Property | Value |
|----------|-------|
| Width | 100mm (283.5 points) |
| Height | 150mm (425.2 points) |
| Orientation | Portrait |

These dimensions match standard thermal label printer sizes (4" × 6" shipping labels).

---

## Installation

### Prerequisites

- Python **3.10+**
- [uv](https://github.com/astral-sh/uv) package manager
- On Windows: a PDF-capable printer installed and set as default (or specify by name in config)

```bash
git clone <repo-url>
cd UPS-Label-Cropper
uv sync
```

---

## Usage

### CLI — Single File Mode

Process one PDF and save the cropped output:

```bash
# Using uv run (recommended during dev)
uv run python -m ups_label_cropper.crop input.pdf output.pdf

# Or after installation via entry point:
ups-label-cropper input.pdf output.pdf
```

### Watch Mode — Auto-Process Directory

Run in background with a system tray icon. Monitors a configured directory for new PDFs, auto-processes and prints them:

```bash
uv run python -m ups_label_cropper.__main__ --watch

# Or via installed entry point:
ups-label-cropper-watch
```

A system tray icon will appear. Right-click it to see status, pause/resume watching, open the config folder, or exit.

### Python API

```python
from ups_label_cropper import process_label

process_label("input.pdf", "output.pdf")
```

For watch mode:

```python
from ups_label_cropper import Config, LabelWatcher, run_tray

config = Config.load()
run_tray(config=config)  # blocks indefinitely with tray icon
```

---

## Configuration

Config file location:
- **Windows:** `%APPDATA%\UPS-Label-Cropper\config.json`
- **macOS:** `~/Library/Application Support/UPS-Label-Cropper/config.json`
- **Linux:** `~/.local/share/UPS-Label-Cropper/config.json`

A default config is created automatically on first run if one doesn't exist.

### Config Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `watched_directory` | string | `~/UPSLabels` | Folder to monitor for new PDFs |
| `printer_name` | string or null | `null` (system default) | Exact name of printer to use; `null` uses OS default |
| `processed_folder` | string | `"processed"` | Subfolder within watched dir to archive source files after success |
| `poll_interval_seconds` | float | `1.0` | How often to check the directory |

### Example Config

```json
{
    "watched_directory": "C:\\Users\\YourName\\Documents\\UPSLabels",
    "printer_name": "DYMO LabelWriter 4XL",
    "processed_folder": "printed",
    "poll_interval_seconds": 1.0
}
```

To edit the config, either open the JSON file directly or right-click the system tray icon and choose **Open Config Folder**.

---

## Watch Mode Pipeline

When a new `.pdf` file appears in `watched_directory`:

```
New PDF detected
  → Validate with PyMuPDF (skip if invalid)
  → Crop using process_label() → temp file
  → Print cropped PDF via Windows Print API to configured printer
    → On failure: log error, leave source file untouched, skip archive
    → On success:
      → Move original PDF → {watched_directory}/{processed_folder}/
      → Delete temp cropped file
```

---

## System Tray

Right-click the tray icon for:

| Menu Item | Behavior |
|-----------|----------|
| **Status: Watching ...** | Disabled label showing current state (Watching / Paused / Idle) |
| **Pause / Resume** | Toggles directory monitoring on/off without exiting |
| **Open Config Folder** | Opens the folder containing `config.json` in Explorer/Finder |
| **Exit** | Stops watcher and closes tray icon |

---

## Windows Startup Registration

To start watch mode automatically when you log into Windows:

### Option 1: Registry (quick)

In an admin PowerShell prompt, run once:

```powershell
$pythonExe = "C:\path\to\your\venv\Scripts\pythonw.exe"
$scriptPath = "C:\path\to\UPS-Label-Cropper\src\ups_label_cropper\__main__.py"

Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" `
  -Name "UPSLabelCropper" `
  -Value "`"$pythonExe`" `"$scriptPath`" --watch"
```

To remove: `Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "UPSLabelCropper"`

### Option 2: Task Scheduler (recommended for delayed start)

Task Scheduler handles systems that boot before Python is ready:

1. Open **Task Scheduler** → Create Basic Task
2. Name it `UPS Label Cropper`, trigger on **Log on**
3. Action: Start a program
   - Program: `C:\path\to\pythonw.exe`
   - Arguments: `"C:\path\to\ups_label_cropper\__main__.py" --watch`
4. Finish — optionally check **Open Properties** and set **Run whether user is logged on or not**

---

## How It Works

1. Opens the input PDF with PyMuPDF, reading only page 1
2. Determines content dimensions using `page.get_image_info()` (images) → falls back to `page.get_drawings()` (vector graphics) → falls back to full page size
3. Detects landscape (`width > height`) and rotates 90° counter-clockwise if needed
4. Captures the content region at **300 DPI** for landscape sources, **150 DPI** for portrait
5. Scales to fit within target bounds with ~1mm margin on all sides (extra padding multipliers: `1.12` landscape, `1.05` portrait)
6. Centers and inserts into a new 283.5pt × 425.2pt portrait page
7. Saves the output PDF

---

## Project Structure

```
src/ups_label_cropper/
├── __init__.py      # Public API re-exports
├── crop.py          # Core cropping logic (PyMuPDF-based)
├── config.py        # JSON config read/write with dataclass interface
├── printer.py       # Windows Print API via win32api.ShellExecute
├── watcher.py       # watchdog Observer + label processing pipeline
├── tray.py          # pystray system tray icon and menu
└── __main__.py      # CLI entry point (--watch flag, argparser)
```