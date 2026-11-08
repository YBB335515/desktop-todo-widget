"""Common utilities: paths, constants, formatting."""
import os
import sys
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = getattr(sys, 'frozen', False)

# 用户数据统一存放在 %LOCALAPPDATA%\DesktopTodoWidget\data —— 与源码/exe 所在
# 目录无关：exe 双击、开机自启、源码运行读写的是同一份数据，项目搬家也不会丢。
USER_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "DesktopTodoWidget")
DATA_DIR = os.path.join(USER_DIR, "data")
VOICE_LOG_FILE = os.path.join(DATA_DIR, "_voice_error.log")


def migrate_legacy_data():
    """把旧版 BASE_DIR/data 下的数据复制到统一数据目录（幂等，只补缺失文件）。"""
    legacy = os.path.join(BASE_DIR, "data")
    if os.path.normcase(os.path.abspath(legacy)) == os.path.normcase(os.path.abspath(DATA_DIR)):
        return
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        for name in ("tasks.json", "settings.json"):
            src = os.path.join(legacy, name)
            dst = os.path.join(DATA_DIR, name)
            if os.path.isfile(src) and not os.path.isfile(dst):
                import shutil
                shutil.copy2(src, dst)
    except Exception:
        pass

COLORS = {
    "bg": "#0f1a2e",
    "surface": "#152238",
    "card": "#1a2840",
    "card_border": "#253550",
    "text": "#e0e6f0",
    "text_secondary": "#8090b0",
    "accent": "#4da6ff",
    "accent_light": "#80c4ff",
    "done": "#4dc9a0",
    "danger": "#ff6b6b",
    "due": "#f0b860",
    "overdue": "#ff6b6b",
    "input_bg": "#0d1a2e",
    "input_border": "#253550",
    "scrollbar": "#203550",
    "scrollbar_hover": "#304560",
    "title_bar": "#0a1428",
    "notify_bg": "#0f1a2e",
    "notify_border": "#4da6ff",
    "hover": "#203050",
}

# Unicode icons — no image files needed, works everywhere
ICONS = {
    "checkbox_undone": "○",
    "checkbox_done": "◉",
    "delete": "✕",
    "edit": "✎",
    "due": "◷",
    "mic": "🎤",
    "mic_recording": "⏹",
    "add": "＋",
    "collapse": "─",
    "expand": "☰",
    "settings": "⚙",
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
