import logging
import subprocess
import sys
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
import pystray

from ups_label_cropper.config import Config
from ups_label_cropper.watcher import LabelWatcher
from ups_label_cropper.autostart import is_windows, set_autostart_enabled, set_autostart_disabled


logger = logging.getLogger(__name__)


def _get_log_path() -> Path:
    """Get the path to the log file."""
    from pathlib import Path
    config_path = Config.default_config_path()
    return config_path.parent / "cropper.log"


def _restart_watcher(watcher: LabelWatcher):
    """Restart the watcher with potentially new configuration."""
    try:
        # Stop existing observer
        if watcher.observer.is_alive():
            watcher.stop()

        # Recreate pipeline and event handler with updated config
        from ups_label_cropper.watcher import LabelPipeline, LabelFileHandler
        watcher.pipeline = LabelPipeline(watcher.config)
        watcher.event_handler = LabelFileHandler(watcher.config, watcher.pipeline)

        # Restart observer
        watch_dir = Path(watcher.config.watched_directory)
        if not watch_dir.exists():
            watch_dir.mkdir(parents=True, exist_ok=True)
        watcher.observer.schedule(watcher.event_handler, str(watch_dir), recursive=False)
        watcher.observer.start()
        logger.info(f"Watcher restarted with directory: {watch_dir}")
    except Exception as e:
        logger.error(f"Failed to restart watcher: {e}")


def _show_settings_dialog(icon: pystray.Icon, watcher: LabelWatcher):
    """Show a settings dialog using tkinter."""
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        logger.error("tkinter not available for settings dialog")
        return

    root = tk.Tk()
    root.title("UPS Label Cropper - Settings")
    root.geometry("500x420")
    root.resizable(False, False)

    # Make it appear on top of the system tray icon
    root.attributes("-topmost", True)

    config = watcher.config.copy() if hasattr(watcher, 'config') else Config.load()
    
    # Store original values for comparison
    original_config = asdict(config)
    
    # Create a frame with padding
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    title_label = ttk.Label(main_frame, text="Settings", font=("Segoe UI", 14, "bold"))
    title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

    # Watched Directory
    ttk.Label(main_frame, text="Watch Directory:").grid(row=1, column=0, sticky=tk.W, pady=8)
    watched_var = tk.StringVar(value=config.watched_directory)
    watched_entry = ttk.Entry(main_frame, textvariable=watched_var, width=40)
    watched_entry.grid(row=1, column=1, pady=8)

    def select_watch_directory():
        # Withdraw the root window to avoid focus issues with native file dialog on macOS
        root.withdraw()
        directory = filedialog.askdirectory(
            title="Select Watch Directory",
            initialdir=watched_var.get() or str(Path.home())
        )
        root.deiconify()
        if directory:
            watched_var.set(directory)

    ttk.Button(main_frame, text="Browse...", command=select_watch_directory).grid(row=1, column=2, pady=8, padx=(5, 0))

    # Printer Name
    ttk.Label(main_frame, text="Printer Name:").grid(row=2, column=0, sticky=tk.W, pady=8)
    printer_var = tk.StringVar(value=config.printer_name or "")
    printer_entry = ttk.Entry(main_frame, textvariable=printer_var, width=40)
    printer_entry.grid(row=2, column=1, columnspan=2, sticky=tk.W+tk.E, pady=8)

    # Processed Folder
    ttk.Label(main_frame, text="Processed Folder:").grid(row=3, column=0, sticky=tk.W, pady=8)
    processed_var = tk.StringVar(value=config.processed_folder)
    processed_entry = ttk.Entry(main_frame, textvariable=processed_var, width=40)
    processed_entry.grid(row=3, column=1, columnspan=2, sticky=tk.W+tk.E, pady=8)

    # Poll Interval
    ttk.Label(main_frame, text="Poll Interval (sec):").grid(row=4, column=0, sticky=tk.W, pady=8)
    poll_var = tk.StringVar(value=str(config.poll_interval_seconds))
    poll_entry = ttk.Entry(main_frame, textvariable=poll_var, width=10)
    poll_entry.grid(row=4, column=1, sticky=tk.W, pady=8)

    def validate_poll():
        try:
            val = float(poll_var.get())
            return 0.1 <= val <= 60.0
        except ValueError:
            return False

    # Start with Computer checkbox (Windows only)
    autostart_var = tk.BooleanVar(value=config.start_with_computer and is_windows())
    ttk.Checkbutton(
        main_frame,
        text="Start when computer boots",
        variable=autostart_var,
        state="normal" if is_windows() else "disabled"
    ).grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

    # Buttons frame at bottom
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.grid(row=7, column=0, columnspan=3, pady=(20, 0))

    def save_settings():
        # Validate poll interval
        try:
            poll_val = float(poll_var.get())
            if not (0.1 <= poll_val <= 60.0):
                root.withdraw()
                messagebox.showerror("Invalid Value", "Poll interval must be between 0.1 and 60 seconds.")
                root.deiconify()
                return
        except ValueError:
            root.withdraw()
            messagebox.showerror("Invalid Value", "Poll interval must be a number.")
            root.deiconify()
            return

        new_watched_dir = watched_var.get()
        restart_watcher = (
            new_watched_dir != watcher.config.watched_directory or
            poll_val != watcher.config.poll_interval_seconds
        )

        # Update config object
        watcher.config.watched_directory = new_watched_dir
        watcher.config.printer_name = printer_var.get() if printer_var.get() else None
        watcher.config.processed_folder = processed_entry.get()
        watcher.config.poll_interval_seconds = poll_val
        watcher.config.start_with_computer = autostart_var.get()

        # Handle Windows autostart registry
        if is_windows():
            try:
                exe_path = sys.executable
                if autostart_var.get():
                    set_autostart_enabled(exe_path)
                else:
                    set_autostart_disabled()
            except Exception as e:
                logger.warning(f"Failed to update autostart registry: {e}")

        # Save to disk
        try:
            watcher.config.save()
            logger.info("Settings saved successfully")

            # Restart watcher if directory or poll interval changed
            if restart_watcher and hasattr(watcher, '_running') and watcher._running:
                _restart_watcher(watcher)

            root.withdraw()
            messagebox.showinfo("Success", "Settings saved successfully.")
            root.destroy()
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            root.withdraw()
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            root.deiconify()

    def cancel():
        root.destroy()

    ttk.Button(buttons_frame, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)

    # Center the window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()


def _get_base_path() -> Path:
    """Get the base path for bundled resources (works in dev and PyInstaller exe)."""
    if getattr(sys, '_MEIPASS', None):
        # Running as bundled PyInstaller exe
        return Path(sys._MEIPASS)
    # Running from source
    return Path(__file__).parent.parent.parent


def _create_icon_image() -> Image.Image:
    icon_path = _get_base_path() / "assets" / "icon.ico"
    return Image.open(icon_path)


def _build_menu(icon: pystray.Icon, watcher: LabelWatcher) -> pystray.Menu:
    def get_status() -> str:
        if not hasattr(watcher, "_running"):
            return "Idle"
        return f"Watching {watcher.config.watched_directory}" if watcher._running else "Paused"

    def on_pause_resume(icon, item):
        if getattr(watcher, "_running", False):
            watcher.stop()
            watcher._running = False
            icon.menu = _build_menu(icon, watcher)
            icon.update_title("UPS Label Cropper - Paused")
        else:
            watcher.start()
            watcher._running = True
            icon.menu = _build_menu(icon, watcher)
            icon.update_title("UPS Label Cropper")

    def on_settings(icon, item):
        _show_settings_dialog(icon, watcher)

    def on_show_logs(icon, item):
        log_path = _get_log_path()
        try:
            if sys.platform == "win32":
                # Use notepad.exe which is available on all Windows versions
                subprocess.run(["notepad.exe", str(log_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(log_path)])
        except Exception as e:
            logger.error(f"Failed to open log file: {e}")

    def on_exit(icon, item):
        icon.visible = False
        if getattr(watcher, "_running", False):
            watcher.stop()
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem("Status: " + get_status(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Pause" if getattr(watcher, "_running", True) else "Resume",
            on_pause_resume,
        ),
        pystray.MenuItem("Settings", on_settings),
        pystray.MenuItem("Show Logs", on_show_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )


def run_tray(config: Config | None = None, watcher: LabelWatcher | None = None):
    if config is None:
        config = Config.load()
    if watcher is None:
        watcher = LabelWatcher(config)

    try:
        watcher.start()
        watcher._running = True
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")
        return

    icon_image = _create_icon_image()

    def setup(icon):
        icon.menu = _build_menu(icon, watcher)
        icon.visible = True

    icon = pystray.Icon(
        "ups_label_cropper",
        icon_image,
        "UPS Label Cropper",
        menu=_build_menu(None, watcher),
    )

    try:
        icon.run(setup=setup)
    except Exception as e:
        logger.error(f"Tray error: {e}")
    finally:
        if getattr(watcher, "_running", False):
            watcher.stop()