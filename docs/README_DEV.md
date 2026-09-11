# UPS Label Cropper — Developer Guide

This guide covers setting up the development environment, running from source, building the Windows executable, and running tests.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Workspace Setup](#workspace-setup)
- [Running from Source](#running-from-source)
- [Configuration](#configuration)
- [Windows Startup Registration](#windows-startup-registration)
- [Building the Windows EXE](#building-the-windows-exe)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)

---

## Prerequisites

- **Python 3.10+** — [Download from python.org](https://www.python.org/downloads/)
- **uv** package manager — [Installation guide](https://github.com/astral-sh/uv)
- On Windows: a PDF-capable printer installed (or specify by name in config)
- Git (for cloning the repository)

---

## Workspace Setup

### Step 1: Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the **Download Python** button (you'll see something like "Python 3.12.x")
3. Run the downloaded `.exe` file
4. **Important:** On the first screen of the installer, check the box that says **"Add Python to PATH"**
5. Click **Install Now** (or Customize to change the install location)
6. Wait for installation to complete, then click **Close**

### Step 2: Verify Python Installation

Open a command prompt and run:
```
python --version
```

You should see something like `Python 3.12.x`. If you get an error, restart your computer and try again.

### Step 3: Install uv

In a command prompt, run:
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen your command prompt to refresh your PATH.

### Step 4: Clone the Repository

```bash
git clone https://github.com/twilsonco/UPS-Label-Cropper.git
cd UPS-Label-Cropper
```

Or download the ZIP from GitHub and extract it, then navigate to the folder.

### Step 5: Install Dependencies

In the project directory, run:
```
uv sync --dev
```

This installs all required libraries and development dependencies in an isolated virtual environment managed by `uv`.

---

## Running from Source

### CLI — Single File Mode

Process one PDF and save the cropped output:

```bash
uv run python -m ups_label_cropper.crop input.pdf output.pdf
```

### Watch Mode — Auto-Process Directory

Run in background with a system tray icon. Monitors a configured directory for new PDFs, auto-processes and prints them:

```bash
uv run python -m ups_label_cropper.__main__
```

This defaults to watch mode. A system tray icon will appear. Right-click it to see status, pause/resume watching, open the config folder, or exit.

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

## Windows Startup Registration

To start watch mode automatically when you log into Windows:

### Option 1: Registry (quick)

The VBScript file `ups-watch.vbs` in the project folder launches the watcher completely hidden — no command prompt window appears at all. In an admin PowerShell prompt, run:

```powershell
$vbsPath = "C:\path\to\UPS-Label-Cropper\ups-watch.vbs"

Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "UPSLabelCropper" -Value "$vbsPath"
```

To remove: `Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "UPSLabelCropper"`

### Option 2: Task Scheduler (recommended for delayed start)

Task Scheduler handles systems that boot before Python is ready:

1. Open **Task Scheduler** → Create Basic Task
2. Name it `UPS Label Cropper`, trigger on **Log on**
3. Action: Start a program
   - Program: `C:\path\to\UPS-Label-Cropper\ups-watch.vbs`
4. Finish — optionally check **Open Properties** and set **Run whether user is logged on or not**

---

## Building the Windows EXE

The build is defined in **`UPS-Label-Cropper.spec`** (PyInstaller spec file) and
produces a **one-folder** bundle, not a single `.exe`. This is deliberate:

- **One-folder, not one-file.** One-file EXEs self-extract to `%TEMP%\_MEIxxxxxx`
  and run from there, which Windows Defender's machine-learning heuristics flag
  as `Trojan:Win32/Wacatac.B!ml`. One-folder avoids that entirely.
- **Native GDI printing.** Printing uses `pywin32` + `gdi32` directly
  (`src/ups_label_cropper/gdi_print.py`) — no third-party PDF viewer binary
  ships in the bundle.
- **Version metadata.** `build/version_info.py` generates a VERSIONINFO resource
  so the EXE carries a real CompanyName/ProductVersion (unsigned binaries with
  blank metadata are flagged hardest). The version comes from the
  `UPS_LABEL_CROPPER_VERSION` env var (CI sets it from the release tag), falling
  back to the `pyproject.toml` version.
- **No UPX.** Compression is disabled in the spec — packed PEs are another AV trigger.

### Build Locally with PyInstaller

1. Make sure you have the full development environment set up (see [Workspace Setup](#workspace-setup))
2. Run:
   ```powershell
   uv sync --group build
   uv run pyinstaller --clean --noconfirm UPS-Label-Cropper.spec
   ```
3. The bundle is in `dist/UPS-Label-Cropper/` — the EXE plus its `_internal/`
   folder. For anything you hand to users, compile it into the installer
   (next section) — that is the only file CI publishes.

To verify the version metadata landed in the EXE:

```powershell
Get-Item .\dist\UPS-Label-Cropper\UPS-Label-Cropper.exe | Select-Object -ExpandProperty VersionInfo | Format-List ProductName, CompanyName, FileVersion
```

### Build the Installer with Inno Setup

The single-file installer is built from **`installer/ups-label-cropper.iss`**
(Inno Setup 6, **6.3+** required for `ArchitecturesInstallIn64BitMode=x64compatible`).
Run it *after* the PyInstaller build — the script packages
`dist/UPS-Label-Cropper/`:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installer\ups-label-cropper.iss
```

Output: `dist/UPS-Label-Cropper-Setup-<version>-windows-x64.exe`. The version
comes from `UPS_LABEL_CROPPER_VERSION` (CI sets it from the release tag),
falling back to `pyproject.toml`.

Two things never to change casually:

- **`AppId`** is a hardcoded GUID. Regenerating it breaks upgrade-in-place and
  leaves orphaned Add/Remove Programs entries.
- **The uninstaller never deletes `%APPDATA%\UPS-Label-Cropper\`** (the user's
  config and log live there); it *does* remove the `UPSLabelCropper` autostart
  Run key so a removed app can't leave a dangling entry.

Inno Setup is **not** preinstalled on `windows-latest` (GitHub dropped it from
the `windows-2025` image), so CI installs a pinned, SHA-256-verified copy —
see the "Install Inno Setup" step in `.github/workflows/ci.yml`.

### Automated Build via CI

The CI pipeline (see `.github/workflows/ci.yml`) builds and publishes on release:

1. Tests run first (`pytest`).
2. On a release, the spec build runs with `UPS_LABEL_CROPPER_VERSION` set to the
   release tag, then logs the EXE's version metadata and Authenticode status.
3. `installer/ups-label-cropper.iss` is compiled with a pinned Inno Setup into
   `dist/UPS-Label-Cropper-Setup-<version>-windows-x64.exe`.
4. The installer is uploaded as the **only release asset** — the one-dir tree
   it contains supersedes the old portable ZIP, which is no longer published.
   PRs and manual runs publish it as a workflow artifact instead.

### Reducing Antivirus False Positives

The unsigned build may still trigger SmartScreen "unknown publisher" warnings
(a *reputation* issue, distinct from the `Wacatac.B!ml` heuristic). Mitigations
in place: one-folder layout, version metadata, no UPX, and no runtime
unpack-and-execute behaviour. If a specific release is falsely flagged, submit
the exact file at <https://www.microsoft.com/en-us/wdsi/filesubmission>
(per-hash; a rebuild changes the hash). The permanent fix is an Authenticode
signature (e.g. Azure Trusted Signing or an OV cert), not yet configured.

---

## Running Tests

Run the test suite with pytest:

```bash
uv run pytest
```

To run tests with verbose output:

```bash
uv run pytest -v
```

To run a specific test file:

```bash
uv run pytest tests/test_crop.py -v
```

---

## Project Structure

```
UPS-Label-Cropper.spec   # PyInstaller build definition (one-dir, versioned)
build/
└── version_info.py      # Generates the EXE VERSIONINFO resource at build time

installer/
└── ups-label-cropper.iss # Inno Setup 6 installer script

src/ups_label_cropper/
├── __init__.py      # Public API re-exports
├── __main__.py      # CLI entry point (watch mode by default)
├── crop.py          # Core cropping logic (PyMuPDF-based)
├── config.py        # JSON config read/write with dataclass interface
├── printer.py       # Thin platform façade for print_pdf()
├── gdi_print.py     # Native Windows GDI printing (pywin32 + gdi32)
├── watcher.py       # watchdog Observer + label processing pipeline
└── tray.py          # infi.systray system tray icon and menu

tests/
├── __init__.py
├── test_crop.py                  # Unit tests for crop.py
└── test_gdi_print.py             # Mocked GDI printing tests

docs/
└── README_DEV.md    # This file

assets/
└── icon.ico         # Application icon for tray and EXE
```

---

## How It Works

### Cropping Pipeline

UPS multi-box shipments produce label sheets with **two labels per page**
(top half and bottom half), each printed sideways. The pipeline handles both
single-label and multi-label PDFs:

1. Opens the input PDF with PyMuPDF and iterates over **every page**
2. Splits each page into its **top and bottom halves** at the vertical midpoint
3. For each half, detects a label using:
   - `page.get_image_info()` (raster images), assigning each image to the half
     containing its vertical center
   - Falls back to `page.get_drawings()` (vector graphics) only for pages with
     no images
   - Halves with no content large enough to be a label are **skipped** (logged
     at DEBUG level)
4. For each detected label:
   - Detects landscape (`width > height`) and rotates 90° counter-clockwise if needed
   - Captures the content region at:
     - **300 DPI** for landscape sources
     - **150 DPI** for portrait
   - Scales to fit within target bounds (4" × 6" @ 283.5pt × 425.2pt) with a
     ~1mm margin, preserving aspect ratio
   - Centers and inserts into a new portrait page
5. Saves the output PDF containing **one label per page** (in reading order)

### Watch Mode Pipeline

When a new `.pdf` file appears in `watched_directory`:

```
New PDF detected
  → Validate with PyMuPDF (skip if invalid)
  → Crop using process_label() → temp file
  → Print cropped PDF via native Windows GDI to configured printer
    → On failure: log error, leave source file untouched, skip archive
    → On success:
      → Move original PDF → {watched_directory}/{processed_folder}/
      → Delete temp cropped file
```

### System Tray Menu

Right-click the tray icon for:

| Menu Item | Behavior |
|-----------|----------|
| **Status: Watching ...** | Disabled label showing current state (Watching / Paused / Idle) |
| **Pause / Resume** | Toggles directory monitoring on/off without exiting |
| **Open Config Folder** | Opens the folder containing `config.json` in Explorer/Finder |
| **Exit** | Stops watcher and closes tray icon |
