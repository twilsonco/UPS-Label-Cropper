import logging
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

# infi.systray is Windows-only and uses pywin32 to run tray in its own thread
try:
    from infi.systray import SysTrayIcon
except ImportError:
    SysTrayIcon = None

from ups_label_cropper.config import Config
from ups_label_cropper.watcher import LabelWatcher
from ups_label_cropper.autostart import is_windows, set_autostart_enabled, set_autostart_disabled


logger = logging.getLogger(__name__)

# Global reference to systray icon for updating menu
_systray_icon: "SysTrayIcon | None" = None
_watcher_ref: "LabelWatcher | None" = None

_was_quit: bool = False

def _get_log_path() -> Path:
    """Get the path to the log file."""
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


def _show_settings_dialog():
    """Show a settings dialog using tkinter."""
    global _systray_icon, _watcher_ref
    
    if not is_windows():
        logger.warning("Settings dialog only supported on Windows")
        return
    
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        logger.error("tkinter not available for settings dialog")
        return

    watcher = _watcher_ref
    
    root = tk.Tk()
    root.title("UPS Label Cropper - Settings")
    root.geometry("480x320")
    root.resizable(False, False)

    config = watcher.config.copy() if hasattr(watcher, 'config') else Config.load()

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
        restart_watcher_flag = (
            new_watched_dir != watcher.config.watched_directory or
            poll_val != watcher.config.poll_interval_seconds
        )

        # Update config object
        watcher.config.watched_directory = new_watched_dir
        watcher.config.printer_name = printer_var.get() if printer_var.get() else None
        watcher.config.processed_folder = processed_entry.get()
        watcher.config.poll_interval_seconds = poll_val
        watcher.config.start_with_computer = autostart_var.get()
        watcher.config.first_run = False

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

        # Save to disk and restart watcher if needed
        try:
            watcher.config.save()
            logger.info("Settings saved successfully")

            if restart_watcher_flag and hasattr(watcher, '_running') and watcher._running:
                _restart_watcher(watcher)

            root.withdraw()
            messagebox.showinfo("Success", "Settings saved successfully.")
            root.destroy()
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            root.withdraw()
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            root.deiconify()

    ttk.Button(buttons_frame, text="Save", command=save_settings).pack(side=tk.LEFT, padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=root.destroy).pack(side=tk.LEFT, padx=5)

    # Center the window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")

    # Ensure window is focused and interactive
    root.deiconify()
    root.focus_force()
    root.grab_set()

    root.mainloop()


def _show_logs():
    """Open the log file in notepad."""
    log_path = _get_log_path()
    try:
        subprocess.run(["notepad.exe", str(log_path)], check=False)
    except Exception as e:
        logger.error(f"Failed to open log file: {e}")


def _toggle_pause_resume(systray):
    """Toggle the watcher pause/resume state."""
    global _systray_icon, _watcher_ref
    
    if not _watcher_ref:
        return
        
    try:
        if getattr(_watcher_ref, "_running", False):
            _watcher_ref.stop()
            _watcher_ref._running = False
        else:
            _watcher_ref.start()
            _watcher_ref._running = True
        
        # Update the hover text to reflect current state
        status = "Paused" if not _watcher_ref._running else f"Watching {_watcher_ref.config.watched_directory}"
        systray.update(hover_text=f"UPS Label Cropper - {status}")
    except Exception as e:
        logger.error(f"Failed to toggle watcher: {e}")


def _get_status() -> str:
    """Get current watcher status."""
    global _watcher_ref
    if not _watcher_ref or not hasattr(_watcher_ref, "_running"):
        return "Idle"
    return f"Watching {_watcher_ref.config.watched_directory}" if _watcher_ref._running else "Paused"



def _on_quit(systray):
    """Handle quit action."""
    global _systray_icon, _watcher_ref
    
    # Stop the watcher first
    if _watcher_ref and getattr(_watcher_ref, "_running", False):
        try:
            _watcher_ref.stop()
            _watcher_ref._running = False
        except Exception as e:
            logger.error(f"Error stopping watcher: {e}")
    
    # Hide the icon and terminate gracefully — _destroy from systray handles
    # calling shutdown/join after this callback returns.
    systray.update(hover_text="")
    global _was_quit
    _was_quit = True


def _get_base_path() -> Path:
    """Get the base path for bundled resources (works in dev and PyInstaller exe)."""
    if getattr(sys, '_MEIPASS', None):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent.parent


def run_tray(config: Config | None = None, watcher: LabelWatcher | None = None):
    """Run the system tray icon using infi.systray (Windows-only)."""
    global _systray_icon, _watcher_ref
    
    if not is_windows():
        logger.warning("System tray requires Windows - use CLI mode instead")
        return
        
    if SysTrayIcon is None:
        logger.error("infi.systray not installed")
        return

    # Start the watcher
    try:
        if config is None:
            config = Config.load()
        if watcher is None:
            watcher = LabelWatcher(config)
        
        _watcher_ref = watcher
        
        watcher.start()
        watcher._running = True
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")
        return

    # Get icon path
    base_path = _get_base_path()
    icon_path = base_path / "assets" / "icon.ico"
    
    if not icon_path.exists():
        logger.warning(f"Icon not found at {icon_path}, using default")
        icon_path = None  # Will use system default

    status_text = f"UPS Label Cropper - {_get_status()}"

    def on_settings(systray):
        _show_settings_dialog()

    def on_show_logs(systray):
        _show_logs()

    menu_options = (
        ("Settings", None, on_settings),
        ("Show Logs", None, on_show_logs),
    )

    try:
        systray = SysTrayIcon(
            str(icon_path) if icon_path else None,
            status_text,
            menu_options,
            on_quit=_on_quit,
            default_menu_index=0
        )
        
        _systray_icon = systray
        
        # Start runs in its own thread - doesn't block
        with systray:
            # Block main thread while the tray icon runs
            # The SyTrayIcon message loop keeps this alive; clicking "Quit" terminates
            import time
            
            # if first_run, show settings dialog
            if _watcher_ref and _watcher_ref.config.first_run:
                _show_settings_dialog()
            
            while True:
                try:
                    if _was_quit:
                        break
                    time.sleep(1.0)
                except KeyboardInterrupt:
                    break
                
    except Exception as e:
        logger.error(f"Tray error: {e}")
    finally:
        if getattr(watcher, "_running", False):
            watcher.stop()
