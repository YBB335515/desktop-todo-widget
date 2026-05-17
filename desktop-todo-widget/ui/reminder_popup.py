"""Notification popup that slides up from the bottom of the screen."""
import tkinter as tk
from datetime import timedelta

from utils.common_utils import COLORS, FONT_NOTIFY, FONT_NOTIFY_SMALL

_SLIDE_STEPS = 10
_SLIDE_INTERVAL = 20  # ms per step


def show_reminder_popup(parent, task_id, content, due_dt, on_snooze=None):
    """Show a notification popup for a due task. Auto-dismisses after 10 seconds."""

    popup = tk.Toplevel(parent)
    popup.title("")
    popup.configure(bg=COLORS["notify_bg"])
    popup.overrideredirect(True)
    popup.wm_attributes("-topmost", True)

    btn_row_h = 28 if on_snooze else 0
    w, h = 300, 80 + btn_row_h
    sw = parent.winfo_screenwidth()
    sh = parent.winfo_screenheight()
    x = sw - w - 20
    start_y = sh + 20
    end_y = sh - h - 60
    popup.geometry("%dx%d+%d+%d" % (w, h, x, start_y))

    popup.configure(highlightbackground=COLORS["notify_border"],
                    highlightcolor=COLORS["notify_border"],
                    highlightthickness=2)

    inner = tk.Frame(popup, bg=COLORS["notify_bg"])
    inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

    # header: content + x button
    header = tk.Frame(inner, bg=COLORS["notify_bg"])
    header.pack(fill=tk.X)

    tk.Label(header, text="提醒: " + content, fg=COLORS["text"],
             bg=COLORS["notify_bg"], font=FONT_NOTIFY, anchor="w",
             justify=tk.LEFT, wraplength=250).pack(side=tk.LEFT)

    tk.Label(inner, text="到期时间: " + due_dt.strftime("%Y-%m-%d %H:%M"),
             fg=COLORS["due"], bg=COLORS["notify_bg"],
             font=FONT_NOTIFY_SMALL).pack(anchor="w", pady=(2, 0))

    # ---- timer tracking (all after() IDs so _cancel_all can clean up) ----
    _slide_timers = []   # slide-up animation
    _chain_timers = []   # dismiss chain
    _dismiss_timer = None

    def _cancel_all():
        nonlocal _dismiss_timer
        for t in _slide_timers + _chain_timers:
            try:
                popup.after_cancel(t)
            except Exception:
                pass
        _slide_timers.clear()
        _chain_timers.clear()
        if _dismiss_timer is not None:
            try:
                popup.after_cancel(_dismiss_timer)
            except Exception:
                pass
            _dismiss_timer = None

    # ---- dismiss (no guard — every click retries; 3-step chain for event-loop) ----
    def _dismiss_now():
        _cancel_all()

        # 3-step chain: each after() gives the event loop a chance to process,
        # making destroy() reliable. First step sets alpha=0 for instant visual.
        def _step(n):
            if n <= 0:
                try:
                    popup.destroy()
                except tk.TclError:
                    pass
                return
            try:
                popup.wm_attributes("-alpha", 0)
            except tk.TclError:
                pass
            tid = popup.after(10, lambda: _step(n - 1))
            _chain_timers.append(tid)

        _step(3)

    # ---- snooze ----
    def _do_snooze(minutes):
        new_due = due_dt + timedelta(minutes=minutes)
        on_snooze(task_id, new_due.isoformat())
        _dismiss_now()

    # ---- x button ----
    def _on_x(e):
        _dismiss_now()
        return "break"

    x_btn = tk.Label(header, text=" ✕ ", fg=COLORS["text_secondary"],
                     bg=COLORS["notify_bg"], font=("Microsoft YaHei UI", 16, "bold"),
                     cursor="hand2")
    x_btn.pack(side=tk.RIGHT)
    x_btn.bind("<Button-1>", _on_x)

    # ---- snooze buttons ----
    if on_snooze:
        def _make_snooze_handler(minutes):
            def handler(e):
                _do_snooze(minutes)
                return "break"
            return handler

        btn_frame = tk.Frame(inner, bg=COLORS["notify_bg"])
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        for minutes, label in [(5, "延迟5分钟"), (10, "延迟10分钟"), (30, "延迟30分钟")]:
            btn = tk.Label(btn_frame, text=label, fg=COLORS["accent"],
                           bg=COLORS["notify_bg"], font=FONT_NOTIFY_SMALL,
                           cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 10))
            btn.bind("<Button-1>", _make_snooze_handler(minutes))

    # ---- slide-up animation (open) ----
    def _schedule_slide_up(step=0):
        if step > _SLIDE_STEPS:
            return
        y = int(start_y + (end_y - start_y) * step / _SLIDE_STEPS)
        popup.geometry("%dx%d+%d+%d" % (w, h, x, y))
        tid = popup.after(_SLIDE_INTERVAL, lambda: _schedule_slide_up(step + 1))
        _slide_timers.append(tid)

    popup.bind("<Button-1>", lambda e: _dismiss_now())
    _schedule_slide_up()
    _dismiss_timer = popup.after(10000, _dismiss_now)
