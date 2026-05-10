"""Settings persistence."""
import json
import os

from utils.common_utils import BASE_DIR, DATA_DIR

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "autostart": False,
    "close_action": "",
}


def _migrate_settings():
    """Migrate settings.json from old location to data/ directory."""
    old_path = os.path.join(BASE_DIR, "settings.json")
    if os.path.isfile(old_path) and not os.path.isfile(SETTINGS_FILE):
        try:
            import shutil
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            shutil.copy2(old_path, SETTINGS_FILE)
        except Exception:
            pass


def load_settings():
    _migrate_settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}
    return {**DEFAULT_SETTINGS, **settings}


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
