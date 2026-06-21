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

- Python **3.10+** — [Download from python.org](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv) package manager
- On Windows: a PDF-capable printer installed (or specify by name in config)

---

### For Windows Users — Step-by-Step Setup

#### Step 1: Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the **Download Python** button (you'll see something like "Python 3.12.x")
3. Run the downloaded `.exe` file
4. **Important:** On the first screen of the installer, check the box that says **"Add Python to PATH"**
   - This makes it possible to run Python from any command prompt
5. Click **Install Now** (or Customize if you want to change the install location)
6. Wait for installation to complete, then click **Close**

#### Step 2: Verify Python Installation

1. Press `Win + R`, type `cmd`, press Enter
2. In the black window that appears, type:
   ```
   python --version
   ```
3. You should see something like `Python 3.12.x` — if you get an error, restart your computer and try again

#### Step 3: Install uv

1. In the same command prompt window, copy-paste this and press Enter:
   ```
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. Wait a few seconds — you'll see some progress dots
3. **Close that command prompt window** and open a new one (this refreshes your PATH with uv)

#### Step 4: Get the Software

1. Go to the repository on GitHub and click the green **Code** button, then **Download ZIP**
2. Or if you have Git installed, run:
   ```
   git clone <repo-url>
   ```
3. Extract the ZIP file to somewhere convenient (like your Desktop or Documents folder)
4. Open a new command prompt (`Win + R`, type `cmd`, Enter)
5. Navigate to the project folder by typing:
   ```
   cd C:\Users\YourName\Path\To\UPS-Label-Cropper
   ```
   (Tip: you can drag the folder from Explorer into the command prompt window to auto-fill the path)

#### Step 5: Install Dependencies

In the command prompt, run:
```
uv sync
```

You'll see some downloading progress — this installs all required libraries automatically.

---

## Usage

### CLI — Single File Mode

Process one PDF and save the cropped output:

```bash
# Using uv run (recommended during dev)
uv run python -m ups_label_cropper.crop input.pdf output.pdf
```

### Watch Mode — Auto-Process Directory

Run in background with a system tray icon. Monitors a configured directory for new PDFs, auto-processes and prints them:

```bash
uv run python -m ups_label_cropper.__main__ --watch
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

### What You'll See on First Run

When you first start watch mode (see above), a few things will happen:

1. **A default config file is created** at:
   ```
   C:\Users\YourName\AppData\Roaming\UPS-Label-Cropper\config.json
   ```

2. **A folder is created** at:
   ```
   C:\Users\YourName\UPSLabels
   ```
   This is where you'll put your UPS label PDFs to be processed.

3. **You'll see a startup summary** in the command prompt showing:
   - Where your config file is located
   - Where logs are saved
   - Which folder is being watched
   - Which printer will be used (and if it's found)

4. **A system tray icon appears** — look for a small UPS Label Cropper icon in the bottom-right corner of your screen (near the clock). Right-click it to access the menu.

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

The batch file `ups-watch.bat` in the project folder handles the path issues automatically. In an admin PowerShell prompt, run once:

```powershell
$batPath = "C:\path\to\UPS-Label-Cropper\ups-watch.bat"

Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" `
  -Name "UPSLabelCropper" `
  -Value "`"$batPath`""
```

To remove: `Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "UPSLabelCropper"`

### Option 2: Task Scheduler (recommended for delayed start)

Task Scheduler handles systems that boot before Python is ready:

1. Open **Task Scheduler** → Create Basic Task
2. Name it `UPS Label Cropper`, trigger on **Log on**
3. Action: Start a program
   - Program: `C:\path\to\UPS-Label-Cropper\ups-watch.bat`
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