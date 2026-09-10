# Implementation task: native GDI printing + single-file installer

You are working in the `twilsonco/UPS-Label-Cropper` repo (Python 3.10+, `uv`, PyInstaller onedir build, GitHub Actions CI, release-please).

## 1. Goal

Two changes, in this order. Do them as separate commits.

**A. Replace SumatraPDF with native GDI printing.** Delete the bundled 20 MB `SumatraPDF.exe` and print directly via the Windows GDI print API using `pywin32` (already a dependency). Removes a third-party binary, its pinned-hash CI checks, and the last "bundled external executable" from the AV picture.

**B. Ship a single-file Inno Setup installer.** Users download one `UPS-Label-Cropper-Setup-<version>-windows-x64.exe`, double-click, and get a Start Menu entry. No `_internal` folder in their face.

---

## 2. Task A — native GDI printing

### Current flow

`watcher.py` → `process_label(in, out)` (crops/rotates each label onto its own 283.5 × 425.2 pt page using PyMuPDF, writes a PDF) → `print_pdf(processed_pdf, printer_name=...)` → SumatraPDF subprocess.

Keep `process_label` exactly as is. Only the printing changes.

### New module: `src/ups_label_cropper/gdi_print.py`

Windows-only. **All `win32ui` / `win32con` / `win32print` imports must be inside functions** (or guarded by `sys.platform == "win32"`), because the test suite runs on macOS and must be able to import this module. Follow the existing pattern in `printer.py`.

Public API: `print_pdf(pdf_path: Path, printer_name: str | None = None) -> bool` — **same signature as today**, since `watcher.py` and `__init__.py` already import it that way.

Algorithm per PDF page:

1. Open with `fitz`, iterate pages. Zero pages → raise `ValueError("PDF has no pages")`.
2. Resolve printer: `printer_name or win32print.GetDefaultPrinter()`; validate with the existing `_validate_printer()` and raise `ValueError(f"Printer not found: {printer_name}")` on failure (preserve current behaviour and messages).
3. `dc = win32ui.CreateDC()`, then `dc.CreatePrinterDC(printer_name)`.
4. Query device caps via `dc.GetDeviceCaps(...)`: `LOGPIXELSX`, `LOGPIXELSY`, `HORZRES`, `VERTRES`, `PHYSICALOFFSETX`, `PHYSICALOFFSETY`.
5. Render the page with PyMuPDF **at the printer's own DPI** so the mapping is 1:1 and there is no resampling blur: `page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)`. Pages are already exactly 4×6 in with the label centred by `crop.py`.
6. Compute destination rect: scale the rendered image to **fit** `HORZRES × VERTRES` preserving aspect ratio, centred, offset by `PHYSICALOFFSETX/Y` (the printable area is inset from the physical page). Never upscale beyond what fits; never draw outside the printable area.
7. `dc.StartDoc("UPS Label Cropper")` once per job; `dc.StartPage()` / `dc.EndPage()` per page; `dc.EndDoc()` at the end; `dc.AbortDoc()` if any page raises; `dc.DeleteDC()` in a `finally`.
8. Return `True`.

### The DIB — this is where this task will break if you're careless

`StretchDIBits` wants a Windows DIB, and PyMuPDF gives you RGB bytes. Two traps:

- **Row order.** GDI 24/32-bit DIBs are bottom-up by default. Use a **negative `biHeight`** for top-down, which matches PyMuPDF's top-down `pixmap.samples`.
- **Byte order and row padding.** BI_RGB DIB rows are BGR(-X) and each row must be padded to a 4-byte boundary. PyMuPDF gives unpadded RGB. Do **not** hand-roll the padding. Convert via Pillow to a **32-bit `BGRX` raw buffer**, which is 4 bytes/pixel and therefore always row-aligned by construction:

  ```python
  img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
  bits = img.tobytes("raw", "BGRX")   # 4 bytes/px -> rows auto-aligned, BGR for GDI
  ```

  Getting this wrong produces a colour-inverted (cyan) label rather than an error, so it will not fail loudly. Test it explicitly.

- pywin32's `BITMAPINFO` is a tuple-ish, not a class with kwargs. The working idiom is:

  ```python
  bmi = win32ui.BITMAPINFO(width, -height, 1, 32, win32con.BI_RGB, len(bits))
  bmi[0].setsubtype(win32con.DIB_RGB_COLORS)   # bmi[0] is the BITMAPINFOHEADER
  dc.StretchDIBits(dx, dy, dw, dh, 0, 0, width, height, bits, bmi,
                   win32con.DIB_RGB_COLORS, win32con.SRCCOPY)
  ```

  Verify these signatures against the installed `win32uii.pyi`/docs — they are easy to get subtly wrong and **cannot be smoke-tested on macOS** (see §5).

- Set `dc.SetMapMode(win32con.MM_TEXT)` and, before blitting, `dc.SetStretchBltMode(win32con.HALFTONE)` followed by `dc.SetBrushOrgEx(0, 0)` — without the brush-org reset, HALFTONE banding shifts the image on thermal printers.

### Deletions

- `src/ups_label_cropper/printer.py` → becomes the thin Windows façade: keep `print_pdf` (delegating to `gdi_print`), `_validate_printer`, `_get_printer_handle`, `get_system_default_printer`, and the non-Windows `OSError` branch. Delete `_sumatra_candidates`, `_resolve_print_binary`, `_SUMATRA_EXE_NAME`.
- Delete `src/ups_label_cropper/bin/` (the 20 MB `SumatraPDF.exe` and its README).
- `pyproject.toml`: remove the `[tool.hatch.build.targets.wheel.force-include]` entry for `src/ups_label_cropper/bin`.
- `UPS-Label-Cropper.spec`: drop the `src/ups_label_cropper/bin` entry from `datas`; add `win32ui` and `win32con` to `hiddenimports`.
- `.github/workflows/ci.yml`: remove **both** "Verify bundled SumatraPDF integrity" steps and the `Get-AuthenticodeSignature` line for SumatraPDF.
- `tests/test_printer_resolution.py`: delete (its subject no longer exists) and replace with the GDI tests in §5.
- Grep for `sumatra` case-insensitively across the repo afterwards and clean up every remaining mention, including `docs/README_DEV.md` ("Download the portable version of SumatraPDF…") and `README.md`.

---

## 3. Task B — Inno Setup installer

`installer/ups-label-cropper.iss`, compiled by Inno Setup 6 (**preinstalled on `windows-latest`** at `${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe` — do not add an install step, but do resolve the path defensively and fail loudly if absent).

Requirements:

- `#define AppVersion` from an env var (`UPS_LABEL_CROPPER_VERSION`, set by CI from the release tag), with a sane fallback for local builds.
- **A fixed `AppId` GUID, hardcoded and never regenerated.** Changing it breaks upgrade-in-place and leaves orphaned uninstall entries.
- `DefaultDirName={autopf}\UPS Label Cropper`, `ArchitecturesInstallIn64BitMode=x64compatible`, `OutputDir=dist`, `OutputBaseFilename=UPS-Label-Cropper-Setup-{#AppVersion}-windows-x64`.
- `PrivilegesRequired=lowest` with `PrivilegesRequiredOverridesAllowed=dialog`. Important: `autostart.py` writes `HKCU\...\CurrentVersion\Run`, which is per-user — a machine-wide install with a per-user Run key is inconsistent, so per-user default is the right call.
- Install the whole `dist/UPS-Label-Cropper/` tree (EXE + `_internal/`) via `[Files]` with `recursesubdirs`.
- `[Icons]` Start Menu entry (+ optional desktop via a `/TASKS` task), `[Run]` post-install launch checkbox, `[UninstallDelete]` for leftovers **but never delete the user's config** at `%APPDATA%\UPS-Label-Cropper\` — and remove the `UPSLabelCropper` Run key on uninstall so a removed app doesn't leave a dangling autostart entry.
- Also add the version metadata (`VersionList`/`UninstallDisplayName`) so the installer itself has real properties, not blanks.

CI (`build-windows-exe`): after the existing spec build, compile the installer and **upload the installer as the primary release asset**, keeping the ZIP as the workflow artifact for PR/manual testing. Update `README.md` install instructions to "download the Setup .exe and run it" (keep a line noting the ZIP exists for portable use), and note in `docs/README_DEV.md` that the installer is built from `installer/ups-label-cropper.iss`.

**Be honest in the README:** the installer is unsigned, so SmartScreen may still show "unknown publisher" on first run. That's a reputation warning, distinct from the `Wacatac.B!ml` heuristic that was fixed, and only code signing removes it. Do not claim the installer eliminates all warnings.

---

## 4. Hard constraints

- `print_pdf()`'s public signature and exception types must not change; `watcher.py` and `__init__.py` depend on them.
- No new runtime dependencies. `win32ui`/`win32con` ship inside `pywin32`, which is already a Windows-only dependency.
- No network access, no self-update, no runtime writes of executables — see §0.
- Don't touch `crop.py`'s geometry (`TARGET_WIDTH_PT`/`TARGET_HEIGHT_PT`, the 300/150 DPI capture, the 3 pt margin centring). Printing must consume whatever `crop.py` produced.
- Don't restructure CI's job graph (`needs: [test, release-please]` and the composite `if` gate are deliberate).
- `CHANGELOG.md` is generated by release-please — never edit it. Use Conventional Commit messages (`feat(printer): ...`, `feat(installer): ...`).

## 5. Verification — read carefully

**You are likely on macOS. `pywin32` cannot be installed or imported there, so the GDI path cannot be smoke-tested locally.** Do not claim it works because tests pass.

1. `uv run pytest` — existing suite must stay green (16 crop tests).
2. New `tests/test_gdi_print.py`, fully mocked (`unittest.mock`, matching the style in `tests/test_crop.py`). Patch `win32ui`/`win32print`/`win32con` into `sys.modules` so the module imports on macOS. Assert:
   - N pages → N `StartPage`/`EndPage` calls, exactly one `StartDoc`/`EndDoc`.
   - A mid-job failure → `AbortDoc` called, `DeleteDC` still called.
   - Unknown printer → `ValueError`, and no DC created.
   - `None` printer → default printer resolved and used.
   - Scaling math: a 4×6 page on a 203 dpi / 800×1200 printable device produces a dest rect that fits inside `HORZRES × VERTRES`, is centred, and preserves aspect ratio. Assert exact numbers.
   - **DIB correctness:** assert the buffer passed to `StretchDIBits` has length `w * h * 4`, that `biHeight` is negative, and that a known RGB pixel comes out BGR-reordered — this catches the colour-inversion bug.
   - `DeleteDC` runs even when `EndDoc` raises.
3. State plainly in your final report which parts are **unverified on real hardware**: actual GDI blitting, DPI/offset behaviour on a physical thermal printer, colour fidelity, and the Inno Setup compile. These need a Windows run.
4. On Windows / in CI, verify: `Get-Item dist\UPS-Label-Cropper\UPS-Label-Cropper.exe | Select -Expand VersionInfo` still shows populated metadata; the installer builds; and a real label prints correctly (single label, two-label sheet, landscape and portrait).

## 6. Out of scope

Code signing (no Azure subscription available), MSIX, Nuitka, DEVMODE/paper-size manipulation, changing the crop geometry, and any change to the onedir packaging decisions described in §0.
