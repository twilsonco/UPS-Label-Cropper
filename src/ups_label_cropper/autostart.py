import sys


def is_windows() -> bool:
    return sys.platform == "win32"


def set_autostart_enabled(exe_path: str) -> None:
    """Add registry entry for current user Run key.

    Note: writing the HKCU ...\\Run key is a persistence mechanism that
    antivirus heuristics watch closely. Here it is intentional, opt-in via the
    Settings dialog, and (with one-dir builds) points at a stable on-disk EXE
    path rather than a temp extraction. Do not call this without a user action.
    """
    if not is_windows():
        return
    import winreg
    key = winreg.HKEY_CURRENT_USER
    subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
        winreg.SetValueEx(reg_key, "UPSLabelCropper", 0, winreg.REG_SZ, exe_path)


def set_autostart_disabled() -> None:
    """Remove registry entry."""
    if not is_windows():
        return
    import winreg
    key = winreg.HKEY_CURRENT_USER
    subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.DeleteValue(reg_key, "UPSLabelCropper")
    except FileNotFoundError:
        pass
