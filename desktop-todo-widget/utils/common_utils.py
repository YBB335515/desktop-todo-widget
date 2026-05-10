"""Common utilities: paths, constants, formatting."""
import os
import sys
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = getattr(sys, 'frozen', False)
DATA_DIR = os.path.join(BASE_DIR, "data")
VOICE_LOG_FILE = os.path.join(DATA_DIR, "_voice_error.log")

COLORS = {
    "bg": "#1e1e2e",
    "surface": "#2a2a3c",
    "text": "#cdd6f4",
    "text_secondary": "#6c7086",
    "accent": "#89b4fa",
    "done": "#a6e3a1",
    "danger": "#f38ba8",
    "due": "#fab387",
    "overdue": "#f38ba8",
    "input_bg": "#313244",
    "scrollbar": "#45475a",
    "title_bar": "#1a1a2a",
    "notify_bg": "#1e1e2e",
    "notify_border": "#89b4fa",
}

FONT = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 8)
FONT_TITLE = ("Microsoft YaHei UI", 10, "bold")
FONT_HEADER = ("Microsoft YaHei UI", 9, "bold")
FONT_NOTIFY = ("Microsoft YaHei UI", 11)
FONT_NOTIFY_SMALL = ("Microsoft YaHei UI", 9)


def format_due(due_str):
    """Return human-readable countdown string for a due ISO datetime."""
    if not due_str:
        return ""
    try:
        dt = datetime.fromisoformat(due_str)
        now = datetime.now()
        secs = (dt - now).total_seconds()
        if secs < 0:
            return "[已过期]"
        h = int(secs) // 3600
        m = (int(secs) % 3600) // 60
        s = int(secs) % 60
        days = (dt.date() - now.date()).days
        if days == 0:
            if h > 0:
                return "[%dh%dm%ds]" % (h, m, s)
            elif m > 0:
                return "[%dm%ds]" % (m, s)
            else:
                return "[%ds]" % s
        elif days == 1:
            return "[明天 %s]" % dt.strftime("%H:%M")
        elif days == 2:
            return "[后天 %s]" % dt.strftime("%H:%M")
        else:
            return "[%s]" % dt.strftime("%m-%d %H:%M")
    except Exception:
        return ""
