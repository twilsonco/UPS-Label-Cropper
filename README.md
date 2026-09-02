# UPS Label Cropper

Auto-rotates and scales UPS shipping labels for thermal printer printing.

> **Note:** This tool was built for Windows users. While the underlying code is cross-platform, the primary distribution method is as a compiled Windows executable. The tool is designed for Windows thermal label printers (4" × 6" shipping labels).

## Features

- **Multi-label support** — handles UPS multi-box shipment PDFs with two labels per page (top and bottom halves), as well as single-label PDFs; each label is output on its own page
- **Auto-detection** of landscape content within PDFs with automatic 90° counter-clockwise rotation
- **Content-aware scaling** using embedded image/drawing dimensions, not page size
- **Aspect-preserving** scale-to-fit within 100mm × 150mm bounds (4" × 6")
- **Centered output** on a portrait page at exactly 283.5pt × 425.2pt
- **Watch mode** — monitors a folder and auto-processes new PDFs with system tray control
- **Auto-printing** — sends cropped labels directly to a thermal printer
- **Archive original files** after successful printing
- **No installation required** — just download and run the `.exe`

## Target Dimensions

| Property | Value |
|----------|-------|
| Width | 100mm (283.5 points) |
| Height | 150mm (425.2 points) |
| Orientation | Portrait |

These dimensions match standard thermal label printer sizes (4" × 6" shipping labels).

---

## Installation

### For Windows Users

1. Go to the [**Releases** page](https://github.com/twilsonco/UPS-Label-Cropper/releases) and download the latest `UPS-Label-Cropper.exe`
2. Run the `.exe` file
3. **You may see a Windows security warning** (because the executable isn't signed). Click **More info**, then **Run anyway** to proceed
4. The program will start in watch mode and present you with settings on first run

### First Run

When you run the program for the first time:

1. A **settings window** will appear where you can configure:
   - **Watch directory** — where to place UPS label PDFs for processing
   - **Printer** — which printer to use (defaults to your system printer)
   - **Auto-start with Windows** — optional; runs the watcher automatically at login
   - Other options like the subfolder for archiving processed files

2. A config file is created at:
   ```
   C:\Users\YourName\AppData\Roaming\UPS-Label-Cropper\config.json
   ```

3. A folder is created at:
   ```
   C:\Users\YourName\UPSLabels
   ```
   (or wherever you configured)

4. A **system tray icon** appears in the bottom-right corner (near the clock; you may need to click the `^` arrow to see it)

---

## Usage

### Watch Mode

Once running, the program monitors your configured folder for new PDF files:

1. Place UPS label PDFs in your watch directory (default: `C:\Users\YourName\UPSLabels`)
2. The program automatically:
   - Detects new PDFs
   - Crops and rotates them correctly
   - Prints to your configured printer
   - Archives the original in a `processed/` subfolder

**System Tray Menu** — Right-click the icon for:

| Option | Effect |
|--------|--------|
| **Status** | Shows current state (Watching / Paused / Idle) |
| **Pause / Resume** | Temporarily stop monitoring |
| **Open Config Folder** | Edit settings or printer name |
| **Exit** | Close the program |

---

## Configuration

Settings are managed through the first-run wizard or by editing the config file:

- **Location:** `C:\Users\YourName\AppData\Roaming\UPS-Label-Cropper\config.json`
- **To edit:** Right-click the tray icon → **Open Config Folder**

### Available Settings

| Field | Default | Purpose |
|-------|---------|---------|
| `watched_directory` | `C:\Users\YourName\UPSLabels` | Folder where you place PDFs |
| `printer_name` | System default | Which printer to use (exact name required) |
| `processed_folder` | `processed` | Subfolder for archiving files after printing |
| `poll_interval_seconds` | `1.0` | How often to check for new PDFs |

---

## Developers

If you want to run this from source, set up the development environment, build the executable, or contribute, see [**docs/README_DEV.md**](docs/README_DEV.md) for:

- Workspace setup and dependency installation
- Running from source
- Building the Windows `.exe` with PyInstaller
- Running tests
- Full technical documentation