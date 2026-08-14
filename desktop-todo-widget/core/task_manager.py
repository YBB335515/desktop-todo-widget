"""Task data management: CRUD + persistence (multi-page workbook)."""
import json
import os
from calendar import monthrange
from datetime import datetime, timedelta

from utils.common_utils import BASE_DIR, DATA_DIR

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# 周一..周日 display names (index 0 = 周一)
_WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


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


def _default_workspace():
    """Default workspace: one page named 页面1."""
    return {"active_page": 0, "pages": [{"name": "页面1", "tasks": []}]}


def load_workspace():
    """Load full workspace dict. Auto-migrates legacy flat-array format."""
    _migrate_data()
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _default_workspace()

    # Legacy format: plain array of tasks → wrap into one page
    if isinstance(data, list):
        return {"active_page": 0, "pages": [{"name": "页面1", "tasks": data}]}

    # New format but missing keys → normalize
    if not isinstance(data, dict):
        return _default_workspace()
    if "pages" not in data or not isinstance(data["pages"], list):
        data["pages"] = [{"name": "页面1", "tasks": []}]
    for page in data["pages"]:
        page.setdefault("name", "页面")
        page.setdefault("tasks", [])
    data.setdefault("active_page", 0)
    if not data["pages"]:
        data["pages"] = [{"name": "页面1", "tasks": []}]
    data["active_page"] = max(0, min(data["active_page"], len(data["pages"]) - 1))
    return data


def save_workspace(ws):
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(ws, f, ensure_ascii=False, indent=2)


def get_pages():
    """Return list of page dicts [{name, tasks}, ...]."""
    return load_workspace()["pages"]


def get_active_page_index():
    return load_workspace()["active_page"]


def set_active_page(index):
    """Switch active page (persisted)."""
    ws = load_workspace()
    if 0 <= index < len(ws["pages"]):
        ws["active_page"] = index
        save_workspace(ws)
        return True
    return False


def add_page(name=None):
    """Add a new page named 页面N (or given name). Returns new page index."""
    ws = load_workspace()
    if not name:
        num = len(ws["pages"]) + 1
        name = f"页面{num}"
    ws["pages"].append({"name": name, "tasks": []})
    ws["active_page"] = len(ws["pages"]) - 1
    save_workspace(ws)
    return ws["active_page"]


def rename_page(index, new_name):
    ws = load_workspace()
    if 0 <= index < len(ws["pages"]):
        ws["pages"][index]["name"] = new_name
        save_workspace(ws)
        return True
    return False


def delete_page(index):
    """Delete a page. Keeps at least one page. Returns new active index."""
    ws = load_workspace()
    if len(ws["pages"]) <= 1:
        return ws["active_page"]
    if 0 <= index < len(ws["pages"]):
        del ws["pages"][index]
        if ws["active_page"] >= len(ws["pages"]):
            ws["active_page"] = len(ws["pages"]) - 1
        elif ws["active_page"] > index:
            ws["active_page"] -= 1
        save_workspace(ws)
    return ws["active_page"]


def load_tasks():
    """Return task list of the ACTIVE page."""
    ws = load_workspace()
    return ws["pages"][ws["active_page"]]["tasks"]


def save_tasks(tasks):
    """Save task list to the ACTIVE page."""
    ws = load_workspace()
    ws["pages"][ws["active_page"]]["tasks"] = tasks
    save_workspace(ws)


def load_all_tasks():
    """Return every task across all pages (for notifications)."""
    ws = load_workspace()
    result = []
    for page in ws["pages"]:
        result.extend(page["tasks"])
    return result


def find_task(task_id):
    """Locate a task by id across all pages.
    Returns (workspace, page_index, task) or None."""
    ws = load_workspace()
    for i, page in enumerate(ws["pages"]):
        for t in page["tasks"]:
            if t["id"] == task_id:
                return ws, i, t
    return None


def get_next_id(tasks):
    """Next globally-unique task id (scans all pages)."""
    used = set()
    for t in tasks:
        used.add(t["id"])
    for page in get_pages():
        for t in page["tasks"]:
            used.add(t["id"])
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def reschedule_recurring(task):
    """If task has recurring spec, move its due to next occurrence.

    Supported formats:
      - "monthly:NN"  → next month's NNth day (e.g. "monthly:10" = every 10th)
      - "yearly:M-D"  → next year's M月D日  (e.g. "yearly:3-15" = every March 15th)
      - "weekly:W"    → next occurrence of weekday W (W=0 周一 .. 6 周日)
      - "biweekly:W"  → next occurrence of weekday W, skipping one week
      - "monthly_day1" (legacy) → treated as "monthly:1"
    Returns True if rescheduled, False otherwise."""
    if not task.get("due"):
        return False
    try:
        due_dt = datetime.fromisoformat(task["due"])
    except Exception:
        return False

    recurring = task.get("recurring", "")
    if not recurring:
        return False

    # Parse recurring spec
    if recurring == "monthly_day1":
        # Legacy format → upgrade
        task["recurring"] = "monthly:1"
        recurring = "monthly:1"

    if recurring.startswith("monthly:"):
        parts = recurring.split(":", 1)
        if len(parts) != 2:
            return False
        try:
            target_day = int(parts[1])
        except ValueError:
            return False
        if target_day < 1 or target_day > 31:
            return False

        # Next month
        year = due_dt.year
        month = due_dt.month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

        max_day = monthrange(year, month)[1]
        day = min(target_day, max_day)
        next_due = due_dt.replace(year=year, month=month, day=day)
        task["due"] = next_due.isoformat()
        return True

    elif recurring.startswith("yearly:"):
        parts = recurring.split(":", 1)
        if len(parts) != 2:
            return False
        date_parts = parts[1].split("-")
        if len(date_parts) != 2:
            return False
        try:
            target_month = int(date_parts[0])
            target_day = int(date_parts[1])
        except ValueError:
            return False
        if target_month < 1 or target_month > 12 or target_day < 1 or target_day > 31:
            return False

        # Next year
        year = due_dt.year + 1
        max_day = monthrange(year, target_month)[1]
        day = min(target_day, max_day)
        next_due = due_dt.replace(year=year, month=target_month, day=day)
        task["due"] = next_due.isoformat()
        return True

    elif recurring.startswith("weekly:"):
        parts = recurring.split(":", 1)
        if len(parts) != 2:
            return False
        try:
            weekday = int(parts[1])
        except ValueError:
            return False
        if weekday < 0 or weekday > 6:
            return False

        # Next occurrence of that weekday (1-7 days ahead, time of day kept)
        delta = (weekday - due_dt.weekday()) % 7
        if delta == 0:
            delta = 7
        next_due = due_dt + timedelta(days=delta)
        task["due"] = next_due.isoformat()
        return True

    elif recurring.startswith("biweekly:"):
        parts = recurring.split(":", 1)
        if len(parts) != 2:
            return False
        try:
            weekday = int(parts[1])
        except ValueError:
            return False
        if weekday < 0 or weekday > 6:
            return False

        # Skip one week: next occurrence 8-14 days ahead
        delta = (weekday - due_dt.weekday()) % 7
        if delta == 0:
            delta = 14
        else:
            delta += 7
        next_due = due_dt + timedelta(days=delta)
        task["due"] = next_due.isoformat()
        return True

    return False


def format_recurring_display(recurring):
    """Convert recurring spec to display string.
    Returns e.g. '🔁每月10号', '🔁每年3月15', or empty string.
    """
    if not recurring:
        return ""
    if recurring == "monthly_day1":
        return " 🔁每月1号"
    if recurring.startswith("monthly:"):
        parts = recurring.split(":", 1)
        if len(parts) == 2:
            try:
                day = int(parts[1])
                return f" 🔁每月{day}号"
            except ValueError:
                pass
    if recurring.startswith("yearly:"):
        parts = recurring.split(":", 1)
        if len(parts) == 2:
            date_parts = parts[1].split("-")
            if len(date_parts) == 2:
                return f" \U0001F501每年{int(date_parts[0])}月{int(date_parts[1])}号"
    if recurring.startswith("weekly:"):
        parts = recurring.split(":", 1)
        if len(parts) == 2:
            try:
                w = int(parts[1])
                if 0 <= w <= 6:
                    return f" \U0001F501每周{_WEEKDAY_CN[w]}"
            except ValueError:
                pass
    if recurring.startswith("biweekly:"):
        parts = recurring.split(":", 1)
        if len(parts) == 2:
            try:
                w = int(parts[1])
                if 0 <= w <= 6:
                    return f" \U0001F501每两周{_WEEKDAY_CN[w]}"
            except ValueError:
                pass
    return ""


def get_alert_page_indices():
    """Return list of page indices that have at least one un-done task
    whose due time has passed (drives red tab highlighting)."""
    ws = load_workspace()
    now = datetime.now()
    result = []
    for i, page in enumerate(ws["pages"]):
        for t in page["tasks"]:
            if t.get("done") or not t.get("due"):
                continue
            try:
                due_dt = datetime.fromisoformat(t["due"])
            except Exception:
                continue
            if due_dt <= now:
                result.append(i)
                break
    return result


# Import parse_recurring_from_text from natural_language for convenience
from core.natural_language import parse_recurring_from_text  # noqa: E402, F811
