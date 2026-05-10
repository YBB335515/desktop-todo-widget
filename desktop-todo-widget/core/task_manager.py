"""Task data management: CRUD + persistence."""
import json
import os

from utils.common_utils import BASE_DIR, DATA_DIR

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")


def _migrate_data():
    """Migrate tasks.json from old location to data/ directory."""
    old_path = os.path.join(BASE_DIR, "tasks.json")
    if os.path.isfile(old_path) and not os.path.isfile(TASKS_FILE):
        try:
            import shutil
            os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
            shutil.copy2(old_path, TASKS_FILE)
        except Exception:
            pass


def load_tasks():
    _migrate_data()
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_tasks(tasks):
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def get_next_id(tasks):
    return max((t["id"] for t in tasks), default=0) + 1
