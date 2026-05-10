"""Reminder service: due time checking, notification scheduling logic."""
from datetime import datetime


def find_due_for_notification(tasks, notified_ids, window_seconds=60):
    """Return tasks whose due time passed within window_seconds and haven't been notified."""
    result = []
    now = datetime.now()
    for t in tasks:
        if t.get("done") or not t.get("due") or t["id"] in notified_ids:
            continue
        try:
            due_dt = datetime.fromisoformat(t["due"])
        except Exception:
            continue
        delta = (now - due_dt).total_seconds()
        if 0 <= delta < window_seconds:
            result.append(t)
    return result


def find_expired_notification_flags(tasks, notified_ids):
    """Return task IDs whose notification flag should be reset (task re-scheduled or deleted)."""
    result = []
    now = datetime.now()
    for tid in list(notified_ids):
        t = next((t for t in tasks if t["id"] == tid), None)
        if not t or not t.get("due"):
            result.append(tid)
            continue
        try:
            due_dt = datetime.fromisoformat(t["due"])
        except Exception:
            result.append(tid)
            continue
        if due_dt > now:
            result.append(tid)
    return result


def find_imminent_tasks(tasks, notified_ids, window_ms=3000):
    """Return [(task, delay_ms), ...] for tasks due within window_ms."""
    result = []
    now = datetime.now()
    for t in tasks:
        if t.get("done") or not t.get("due") or t["id"] in notified_ids:
            continue
        try:
            due_dt = datetime.fromisoformat(t["due"])
        except Exception:
            continue
        delta_ms = (due_dt - now).total_seconds() * 1000
        if 0 < delta_ms < window_ms:
            result.append((t, int(delta_ms)))
    return result
