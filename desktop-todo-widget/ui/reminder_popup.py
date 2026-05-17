"""Notification popup that slides up from the bottom of the screen."""
import tkinter as tk
from datetime import timedelta

from utils.common_utils import COLORS, FONT_NOTIFY, FONT_NOTIFY_SMALL


def show_reminder_popup(parent, task_id, content, due_dt, on_snooze=None):
    """Show a notification popup for a due task. Auto-dismisses after 5 seconds."""

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

    # header: content + × button
    header = tk.Frame(inner, bg=COLORS["notify_bg"])
    header.pack(fill=tk.X)

    tk.Label(header, text="提醒: " + content, fg=COLORS["text"],
             bg=COLORS["notify_bg"], font=FONT_NOTIFY, anchor="w",
             justify=tk.LEFT, wraplength=250).pack(side=tk.LEFT)

    def _make_x_handler():
        def handler(e):
            _dismiss_now()
            return "break"
        return handler

    x_btn = tk.Label(header, text="×", fg=COLORS["text_secondary"],
                     bg=COLORS["notify_bg"], font=("Microsoft YaHei UI", 14),
                     cursor="hand2")
    x_btn.pack(side=tk.RIGHT)
    x_btn.bind("<Button-1>", _make_x_handler())

    tk.Label(inner, text="到期时间: " + due_dt.strftime("%Y-%m-%d %H:%M"),
             fg=COLORS["due"], bg=COLORS["notify_bg"],
             font=FONT_NOTIFY_SMALL).pack(anchor="w", pady=(2, 0))

    _dismiss_timer = None

    def _dismiss_now():
        nonlocal _dismiss_timer
        if _dismiss_timer is not None:
            popup.after_cancel(_dismiss_timer)
            _dismiss_timer = None
        try:
            popup.destroy()
        except tk.TclError:
            pass

    def _do_snooze(minutes):
        new_due = due_dt + timedelta(minutes=minutes)
        on_snooze(task_id, new_due.isoformat())
        _dismiss_now()

    def _make_snooze_handler(minutes):
        def handler(e):
            _do_snooze(minutes)
            return "break"
        return handler

    if on_snooze:
        btn_frame = tk.Frame(inner, bg=COLORS["notify_bg"])
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        for minutes, label in [(5, "延迟5分钟"), (10, "延迟10分钟"), (30, "延迟30分钟")]:
            btn = tk.Label(btn_frame, text=label, fg=COLORS["accent"],
                           bg=COLORS["notify_bg"], font=FONT_NOTIFY_SMALL,
                           cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 10))
            btn.bind("<Button-1>", _make_snooze_handler(minutes))

    def slide_up(step=0, steps=10):
        if step > steps:
            return
        y = int(start_y + (end_y - start_y) * step / steps)
        popup.geometry("%dx%d+%d+%d" % (w, h, x, y))
        popup.after(20, lambda: slide_up(step + 1, steps))

    popup.bind("<Button-1>", lambda e: _dismiss_now())
    slide_up()
    _dismiss_timer = popup.after(5000, _dismiss_now)
