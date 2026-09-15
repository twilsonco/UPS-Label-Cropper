# UPS Label Cropper

Auto-rotates and scales UPS shipping labels for thermal printer printing.

> **Note:** This tool was built for Windows users. While the underlying code is cross-platform, the primary distribution method is a Windows Setup installer. The tool is designed for Windows thermal label printers (4" × 6" shipping labels).

## Features

- **Multi-label support** — handles UPS multi-box shipment PDFs with two labels per page (top and bottom halves), as well as single-label PDFs; each label is output on its own page
- **Auto-detection** of landscape content within PDFs with automatic 90° counter-clockwise rotation
- **Content-aware scaling** using embedded image/drawing dimensions, not page size
- **Aspect-preserving** scale-to-fit within 100mm × 150mm bounds (4" × 6")
- **Centered output** on a portrait page at exactly 283.5pt × 425.2pt
- **Watch mode** — monitors a folder and auto-processes new PDFs with system tray control
- **Auto-printing** — sends cropped labels straight to a thermal printer using **native Windows GDI
  printing**, with no third-party PDF viewer to install or bundle
- **Archive original files** after successful printing
- **No Python required** — download the Setup installer and run it

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

The **Setup installer is the only file published with each release** — always install from it,
rather than grabbing a bare `UPS-Label-Cropper.exe` out of an old release (those portable builds
are no longer published, and a loose EXE has no Start Menu entry, no uninstaller, and breaks
automatic upgrades).

1. Go to the [**Releases** page](https://github.com/twilsonco/UPS-Label-Cropper/releases) and download the latest `UPS-Label-Cropper-Setup-<version>-windows-x64.exe`
2. Run the Setup `.exe` and follow the prompts. It installs into your Programs folder
   (`%LOCALAPPDATA%\Programs\UPS Label Cropper`), creates a **Start Menu entry**
   ("UPS Label Cropper"), and needs **no administrator rights**. Optionally tick *Create a desktop
   icon*.
3. Launch it from the Start Menu (the installer offers to launch it for you when it finishes)
4. The program will start in watch mode and present you with settings on first run
5. To upgrade, just run the newer Setup `.exe` — it replaces the existing install in place
6. *Uninstall the app normally via **Settings → Apps***. Your config and log in
   `%APPDATA%\UPS-Label-Cropper\` are deliberately left alone

### Windows Security Warnings

Because neither the app nor the installer is **code-signed**, you may see a
Windows security prompt the first time you run it (SmartScreen "unknown
publisher" — this applies to the Setup `.exe` too). This is a reputation
warning, not a virus detection:

- Click **More info** → **Run anyway** to proceed
- The app is built from the public source in this repository and does not
  access the network
- If Windows Defender reports a **virus** (e.g. `Trojan:Win32/Wacatac.B!ml`),
  that is a known false positive with unsigned PyInstaller apps. Please open a
  [GitHub issue](https://github.com/twilsonco/UPS-Label-Cropper/issues) with the
  detection name and the file's SHA-256 hash so we can submit it to Microsoft:

  ```powershell
  Get-FileHash "$env:LOCALAPPDATA\Programs\UPS Label Cropper\UPS-Label-Cropper.exe"
  ```


### First Run

When you run the program for the first time:

1. A **settings window** will appear where you can configure:
   - **Watch Directory** — where to place UPS label PDFs for processing
   - **Printer Name** — which printer to use (leave blank for your system default)
   - **Processed Folder** — subfolder for archiving processed files
   - **Poll Interval (sec)** — how often to check the folder
   - **Start when computer boots** — optional; runs the watcher automatically at login

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
   - Detects new PDFs (and waits for the browser/downloader to release the file)
   - Crops and rotates them correctly
   - Prints to your configured printer via native GDI
   - Saves the cropped PDF in a `processed/` subfolder as `<name>_processed.pdf`, then
     archives the original alongside it

**System Tray** — the icon's hover text shows the current state (Watching / Paused). Right-click
the icon for:

| Option | Effect |
|--------|--------|
| **Settings** | Change watch directory, printer, archive folder, poll interval, and auto-start |
| **Show Logs** | Open `cropper.log` (next to `config.json`) in Notepad |
| **Quit** | Stop the watcher and close the program |

Double-clicking the icon opens **Settings**.

---

## Configuration

Settings are managed through the first-run wizard or by editing the config file:

- **Location:** `C:\Users\YourName\AppData\Roaming\UPS-Label-Cropper\config.json`
- **To edit:** Right-click the tray icon → **Settings** (recommended — it validates values and
  applies them immediately), or edit the JSON file directly and restart the app

### Available Settings

| Field | Default | Purpose |
|-------|---------|---------|
| `watched_directory` | `C:\Users\YourName\UPSLabels` | Folder where you place PDFs |
| `printer_name` | System default | Which printer to use (exact name required) |
| `processed_folder` | `processed` | Subfolder for archiving files after printing |
| `poll_interval_seconds` | `1.0` | How often to check for new PDFs |
| `start_with_computer` | `false` | Launch the watcher at Windows login (managed via the Settings dialog) |

---

## Testing Multi-Label Support

A sample multi-box shipment PDF is included at `demo/download.pdf` (two labels per page on some pages, a single label on the last). To verify multi-label handling from source:

```bash
# From the repository root (requires uv — see docs/README_DEV.md)
mkdir -p demo_out
uv run python -m ups_label_cropper.crop demo/download.pdf demo_out/download.pdf
```

Expected result: the output PDF contains **one page per detected label** — the sample produces 5 label pages (2 + 2 + 1), each exactly 100mm × 150mm (283.5pt × 425.2pt), rotated upright and centered. Halves of a page without a label are skipped automatically.

You can open `demo_out/download.pdf` in any PDF viewer to confirm each label fills its own page.

---

## Developers

If you want to run this from source, set up the development environment, build the executable, or contribute, see [**docs/README_DEV.md**](docs/README_DEV.md) for:

- Workspace setup and dependency installation
- Running from source
- Building the Windows installer (PyInstaller one-dir bundle + Inno Setup)
- Running tests
- Full technical documentation