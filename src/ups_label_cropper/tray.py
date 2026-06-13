import logging
from io import BytesIO

from PIL import Image, ImageDraw
import pystray

from ups_label_cropper.config import Config
from ups_label_cropper.watcher import LabelWatcher


logger = logging.getLogger(__name__)


def _create_icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(0, 80, 160))
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 12, 56, 52), fill=(255, 255, 255))
    draw.rectangle((12, 16, 52, 48), fill=(200, 220, 255))
    draw.rectangle((18, 22, 46, 28), fill=(0, 60, 140))
    draw.rectangle((18, 30, 38, 36), fill=(0, 60, 140))
    draw.rectangle((18, 38, 32, 44), fill=(0, 60, 140))
    return img


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

    def on_open_config(icon, item):
        import subprocess
        config_path = Config.default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(__import__('sys'), 'platform') and __import__('sys').platform == "win32":
            subprocess.run(["explorer", str(config_path.parent)])
        else:
            subprocess.run(["xdg-open", str(config_path.parent)])

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
        pystray.MenuItem("Open Config Folder", on_open_config),
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