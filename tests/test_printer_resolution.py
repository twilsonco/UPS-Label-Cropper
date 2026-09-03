"""Tests for the read-only SumatraPDF path resolution in printer.py.

Regression guard: pre-1.6 builds copied SumatraPDF out of the PyInstaller
one-file temp dir into %APPDATA% and swept %TEMP%. That dropper-shaped
behaviour triggered Defender ``Trojan:Win32/Wacatac.B!ml``. The resolver must
stay a pure lookup that never writes to disk.
"""

import sys
from pathlib import Path

import pytest

from ups_label_cropper import printer


SUMATRA = printer._SUMATRA_EXE_NAME


def _make_frozen(monkeypatch, tmp_path: Path, app_dir: Path):
    """Pretend we're a frozen one-dir build rooted at ``app_dir``."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "UPS-Label-Cropper.exe"), raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    # Redirect the legacy %APPDATA% fallback at a temp dir.
    fake_appdata = tmp_path / "AppData"
    import platformdirs

    monkeypatch.setattr(platformdirs, "user_data_dir", lambda *a, **k: str(fake_appdata))
    return app_dir, fake_appdata


class TestSumatraCandidates:
    def test_dev_layout_resolves_module_adjacent_bin(self):
        """Running from source, the bin/ next to printer.py is found."""
        resolved = printer._resolve_print_binary()
        assert resolved == Path(printer.__file__).resolve().parent / "bin" / SUMATRA
        assert resolved.exists()

    def test_frozen_onedir_internal_layout(self, tmp_path, monkeypatch):
        app_dir, _ = _make_frozen(monkeypatch, tmp_path, tmp_path / "app")
        target = app_dir / "_internal" / "ups_label_cropper" / "bin" / SUMATRA
        target.parent.mkdir(parents=True)
        target.write_bytes(b"MZ")

        assert printer._resolve_print_binary() == target

    def test_frozen_prefers_internal_over_legacy_appdata(self, tmp_path, monkeypatch):
        app_dir, fake_appdata = _make_frozen(monkeypatch, tmp_path, tmp_path / "app")
        internal = app_dir / "_internal" / "ups_label_cropper" / "bin" / SUMATRA
        internal.parent.mkdir(parents=True)
        internal.write_bytes(b"new")
        legacy = fake_appdata / "bin" / SUMATRA
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"old")

        assert printer._resolve_print_binary() == internal

    def test_frozen_falls_back_to_legacy_appdata_copy(self, tmp_path, monkeypatch):
        """Upgraders from <=1.5.0 keep printing via the old APPDATA copy."""
        _, fake_appdata = _make_frozen(monkeypatch, tmp_path, tmp_path / "app")
        legacy = fake_appdata / "bin" / SUMATRA
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"old")

        # Hide the dev module-adjacent bin from the candidate list tail by
        # asserting the legacy copy wins over it only if it exists first.
        candidates = printer._sumatra_candidates()
        assert legacy in candidates
        assert candidates.index(legacy) < len(candidates) - 1

    def test_frozen_missing_everywhere_raises_file_not_found(self, tmp_path, monkeypatch):
        _make_frozen(monkeypatch, tmp_path, tmp_path / "app")
        # Point the dev fallback at an empty dir too.
        monkeypatch.setattr(printer, "__file__", str(tmp_path / "printer.py"))

        with pytest.raises(FileNotFoundError):
            printer._resolve_print_binary()

    def test_resolution_never_writes_to_disk(self, tmp_path, monkeypatch):
        """The resolver must not create directories or copy executables."""
        app_dir, fake_appdata = _make_frozen(monkeypatch, tmp_path, tmp_path / "app")
        monkeypatch.setattr(printer, "__file__", str(tmp_path / "printer.py"))

        with pytest.raises(FileNotFoundError):
            printer._resolve_print_binary()

        assert not app_dir.exists() or list(app_dir.rglob("*")) == []
        assert not fake_appdata.exists()

    def test_dropper_helpers_are_gone(self):
        """Old copy/temp-sweep functions must not come back."""
        for name in ("ensure_sumatra_present", "cleanup_stale_temp_dirs", "_stable_bin_dir"):
            assert not hasattr(printer, name), f"printer.{name} was removed on purpose"
