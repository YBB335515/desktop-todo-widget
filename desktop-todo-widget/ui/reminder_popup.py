"""Notification popup that slides up from the bottom of the screen."""
import tkinter as tk

from utils.common_utils import COLORS, FONT_NOTIFY, FONT_NOTIFY_SMALL


def show_reminder_popup(parent, content, due_dt):
    """Show a notification popup for a due task. Auto-dismisses after 8 seconds."""
    popup = tk.Toplevel(parent)
    popup.title("")
    popup.configure(bg=COLORS["notify_bg"])
    popup.overrideredirect(True)
    popup.wm_attributes("-topmost", True)

    w, h = 300, 80
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

    tk.Label(inner, text="提醒: " + content, fg=COLORS["text"],
             bg=COLORS["notify_bg"], font=FONT_NOTIFY, anchor="w",
             justify=tk.LEFT, wraplength=270).pack(anchor="w")

    tk.Label(inner, text="到期时间: " + due_dt.strftime("%Y-%m-%d %H:%M"),
             fg=COLORS["due"], bg=COLORS["notify_bg"],
             font=FONT_NOTIFY_SMALL).pack(anchor="w", pady=(2, 0))

    def slide_up(step=0, steps=10):
        if step > steps:
            return
        y = int(start_y + (end_y - start_y) * step / steps)
        popup.geometry("%dx%d+%d+%d" % (w, h, x, y))
        popup.after(20, lambda: slide_up(step + 1, steps))

    def dismiss():
        popup.destroy()

    popup.bind("<Button-1>", lambda e: dismiss())
    inner.bind("<Button-1>", lambda e: dismiss())
    slide_up()
    popup.after(8000, dismiss)
