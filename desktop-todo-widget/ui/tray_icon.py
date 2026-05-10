"""System tray icon using pystray — minimize to notification area."""
import threading
import tkinter as tk
from PIL import Image, ImageDraw

from utils.common_utils import COLORS

TRAY_ICON_SIZE = 32


def _create_tray_image():
    """Generate a simple tray icon image (rounded square with check mark)."""
    img = Image.new("RGBA", (TRAY_ICON_SIZE, TRAY_ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 3
    r = 6
    # Rounded rect background (blue)
    draw.rounded_rectangle(
        [margin, margin, TRAY_ICON_SIZE - margin, TRAY_ICON_SIZE - margin],
        radius=r, fill="#89b4fa")

    # Check mark
    cx, cy = TRAY_ICON_SIZE // 2, TRAY_ICON_SIZE // 2
    pts = [(cx - 7, cy), (cx - 2, cy + 6), (cx + 7, cy - 5)]
    draw.line(pts, fill="#1e1e2e", width=3, joint="curve")

    return img


class TrayIcon:
    """Manages the system tray icon via pystray in a background thread."""

    def __init__(self, root, on_restore, on_quit):
        self._root = root
        self._on_restore = on_restore
        self._on_quit = on_quit
        self._tray = None
        self._thread = None
        self._menu_items = None

    def show(self):
        """Create and show the tray icon."""
        import pystray

        if self._tray is not None:
            return

        def do_restore(icon, item=None):
            self._root.after(0, self._on_restore)

        def do_quit(icon, item=None):
            self._root.after(0, self._on_quit)

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", do_restore, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", do_quit),
        )

        self._tray = pystray.Icon(
            "todo_widget",
            _create_tray_image(),
            "待办事项",
            menu=menu,
        )

        self._thread = threading.Thread(target=self._tray.run, daemon=True)
        self._thread.start()

    def hide(self):
        """Remove the tray icon."""
        if self._tray is not None:
            self._tray.stop()
            self._tray = None
            self._thread = None
