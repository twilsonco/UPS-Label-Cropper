# Plan: Auto-Process & Print UPS Labels

## Overview

Add a background watcher mode that monitors a directory for incoming PDFs, auto-crops them using existing logic, prints to a thermal label printer via Windows Print API, and archives the source file. Includes system tray icon and config file.

---

## Tech Stack Additions

| Library | Purpose |
|---------|---------|
| `watchdog >= 3.0.0` | Cross-platform filesystem event monitoring |
| `pywin32` (`win32print`) | Windows Print API integration (no printer-specific SDK needed) |
| `pystray >= 0.19.0` | System tray icon with menu |
| `Pillow >= 10.0.0` | Image generation for tray icon |

---

## New Source Files

### `src/ups_label_cropper/config.py`
- Config path: `{user_data_dir}/UPS-Label-Cropper/config.json` (platformsdirs)
- Default config created on first run if missing
- Fields:
  - `watched_directory` (string) — folder to monitor for new PDFs
  - `printer_name` (string, optional) — printer name; uses system default if omitted
  - `processed_folder` (string) — subfolder within watched dir for archived source files after success
  - `poll_interval_seconds` (float, default 1.0) — how often to poll/check the directory
- CRUD read/write with JSON

### `src/ups_label_cropper/printer.py`
- `print_pdf(pdf_path: Path, printer_name: str | None = None) -> bool`
- Uses `win32api.ShellExecute` with `"print"` verb — defers to OS-assigned PDF handler and default/system-specified printer
- Returns True on success (non-zero return code from ShellExecute), raises on failure

### `src/ups_label_cropper/watcher.py`
- `LabelWatcher(config: Config) -> LabelWatcher`
- Wraps `watchdog.observers.Observer` with an event handler that:
  - Filters for `.pdf` files only
  - Debounces duplicate events (same file appearing twice rapidly)
  - Calls pipeline on each new PDF
- `start()` / `stop()` methods

### `src/ups_label_cropper/tray.py`
- Builds a `pystray.Icon` with a simple label icon (generated via Pillow)
- Right-click menu items:
  - **Status** (disabled, shows current state: "Watching {dir}" / "Paused" / "Idle")
  - **Pause/Resume Watching**
  - **Open Config Folder**
  - Separator
  - **Exit**
- Calls watcher.start()/stop() on menu actions

### `src/ups_label_cropper/__main__.py`
New entry point supporting two modes:

```bash
# Existing CLI mode (unchanged behavior)
python -m ups_label_cropper input.pdf output.pdf

# New watch mode
python -m ups_label_cropper --watch
```

- `--watch` flag launches watcher + tray icon, runs indefinitely
- Without `--watch`, falls through to existing `main()` behavior for backward compat

---

## Modified Files

### `src/ups_label_cropper/crop.py`
- No functional changes — only minor refactor to move magic constants into module-level `_constants` dict (for potential config override in watch mode)
- All existing exports (`process_label`, `main`) unchanged externally

### `pyproject.toml`
- Add new dependencies: `watchdog`, `pystray`, `Pillow`, `pywin32`, `platformdirs`
- New console script entry point: not needed — `--watch` handled by same module
- Optional: add `[project.scripts]` for `ups-label-cropper-watch = ups_label_cropper.__main__:run_watch_mode`

### `src/ups_label_cropper/__init__.py`
- Re-export `process_label` (unchanged)

---

## Pipeline (per file)

```
New PDF detected in watched_directory
  → Validate it's a real PDF (try open with fitz)
  → process_label(input_pdf, temp_output)
  → print_pdf(temp_output, printer_name=cfg.printer_name or None)
    → On print failure: log error, leave source file in place, skip archive step
    → On print success:
      → Move original to {watched_directory}/{processed_folder}/<original_name>
      → Delete temp_output
```

- Temp output uses `tempfile` module with `.pdf` suffix — cleaned up on exit regardless

---

## Windows Startup Registration

Separate install step (documented, not auto-applied):

```bash
# In an admin PowerShell prompt:
# Add to HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
Add-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" \
  -Name "UPSLabelCropper" `
  -Value '"C:\path\to\pythonw.exe" "C:\path\to\ups_label_cropper\__main__.py" --watch'
```

Or use Task Scheduler for delayed start (better for systems that boot fast).

A `--install-startup` flag on the CLI will handle this programmatically.

---

## Project Structure After Changes

```
src/ups_label_cropper/
├── __init__.py
├── crop.py          # unchanged external API
├── config.py        # NEW: JSON config management
├── printer.py       # NEW: Windows Print API wrapper
├── watcher.py       # NEW: watchdog integration + pipeline
├── tray.py          # NEW: pystray system tray UI
└── __main__.py      # MODIFIED: adds --watch mode entry point
```

---

## Testing Notes

- `test_crop.py` unchanged (unit tests only)
- Add `tests/test_config.py`, `tests/test_printer.py`, `tests/test_watcher.py`
- Watcher tests use a temp directory with fake PDF files created on-the-fly

---

## Implementation Order

1. `config.py` — config file read/write first; other modules depend on it
2. `printer.py` — simple print dispatch
3. `crop.py` refactor (move constants to module-level)
4. `watcher.py` — watchdog + pipeline orchestration
5. `tray.py` — system tray icon and menu
6. `__main__.py` update — wire `--watch` mode to watcher+tray
7. Update `pyproject.toml` with new dependencies
8. Add tests for new modules