"""Task editing dialog — used for add, edit, and set-reminder operations."""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox

from core.natural_language import parse_due_time
from utils.common_utils import COLORS, FONT, FONT_SMALL, FONT_TITLE


def show_task_dialog(parent, title, save_label, content_val, due_val,
                     on_save, content_readonly=False, show_clear=False,
                     on_clear=None):
    """Unified dialog for adding, editing, and setting reminders on tasks.

    Args:
        parent: parent tk widget
        title: dialog title
        save_label: text for the save button
        content_val: initial task content text
        due_val: initial due time text
        on_save(content, due_iso): called when user clicks save
        content_readonly: if True, content field is not editable
        show_clear: if True, show a "clear reminder" button
        on_clear: called when user clicks clear reminder
    """
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=COLORS["surface"])
    dlg.resizable(False, False)
    dlg.transient(parent)

    dlg_w, dlg_h = 370, 240
    _dialog_position(parent, dlg, dlg_w, dlg_h)

    try:
        dlg.wm_attributes("-toolwindow", True)
    except Exception:
        pass

    # task content
    tk.Label(dlg, text="任务内容", fg=COLORS["text"], bg=COLORS["surface"],
             font=FONT).pack(padx=12, pady=(12, 2), anchor="w")

    state = "readonly" if content_readonly else "normal"
    entry_fg = COLORS["text_secondary"] if content_readonly else COLORS["text"]
    content_var = tk.StringVar(value=content_val)
    content_entry = tk.Entry(dlg, textvariable=content_var, font=FONT,
                             bg=COLORS["input_bg"], fg=entry_fg,
                             insertbackground=COLORS["text"],
                             relief="flat", bd=6, state=state)
    content_entry.pack(fill=tk.X, padx=12, ipady=3)
    if content_readonly:
        content_entry.configure(state="readonly")
    else:
        if content_val:
            content_entry.select_range(0, tk.END)
        content_entry.focus_set()

    # reminder time
    tk.Label(dlg, text="提醒时间 (可选)", fg=COLORS["text"], bg=COLORS["surface"],
             font=FONT).pack(padx=12, pady=(10, 2), anchor="w")

    hint_frame = tk.Frame(dlg, bg=COLORS["surface"])
    hint_frame.pack(fill=tk.X, padx=12)
    tk.Label(hint_frame,
             text="明天15:00 / 后天9:30 / 今天20:00 / 2026-05-05 10:00",
             fg=COLORS["text_secondary"], bg=COLORS["surface"],
             font=FONT_SMALL).pack(anchor="w")

    due_var = tk.StringVar(value=due_val)
    due_entry = tk.Entry(dlg, textvariable=due_var, font=FONT,
                         bg=COLORS["input_bg"], fg=COLORS["text"],
                         insertbackground=COLORS["text"],
                         relief="flat", bd=6)
    due_entry.pack(fill=tk.X, padx=12, pady=(2, 0), ipady=3)

    # quick buttons
    quick_frame = tk.Frame(dlg, bg=COLORS["surface"])
    quick_frame.pack(fill=tk.X, padx=12, pady=(4, 0))

    now = datetime.now()
    for lbl, val in [
        ("今天18:00", now.strftime("%Y-%m-%d") + " 18:00"),
        ("明天9:00", (now + timedelta(days=1)).strftime("%Y-%m-%d") + " 09:00"),
        ("明天15:00", (now + timedelta(days=1)).strftime("%Y-%m-%d") + " 15:00"),
        ("后天9:00", (now + timedelta(days=2)).strftime("%Y-%m-%d") + " 09:00"),
    ]:
        btn = tk.Label(quick_frame, text=lbl, fg=COLORS["accent"],
                       bg=COLORS["surface"], font=FONT_SMALL,
                       cursor="hand2", padx=5)
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda e, v=val: due_var.set(v))

    # bottom buttons
    btn_frame = tk.Frame(dlg, bg=COLORS["surface"])
    btn_frame.pack(fill=tk.X, padx=12, pady=(8, 12))

    if show_clear and on_clear:
        clear_btn = tk.Label(btn_frame, text="清除提醒", fg=COLORS["danger"],
                             bg=COLORS["surface"], font=FONT,
                             cursor="hand2", padx=10)
        clear_btn.pack(side=tk.LEFT)
        clear_btn.bind("<Button-1>", lambda e: (dlg.destroy(), on_clear()))

    def do_cancel():
        dlg.destroy()

    cancel_btn = tk.Label(btn_frame, text="取消", fg=COLORS["text_secondary"],
                          bg=COLORS["surface"], font=FONT,
                          cursor="hand2", padx=10)
    cancel_btn.pack(side=tk.RIGHT)
    cancel_btn.bind("<Button-1>", lambda e: do_cancel())

    def do_save():
        c = content_var.get().strip()
        if not c:
            return
        d = due_var.get().strip()
        due_iso = ""
        if d:
            try:
                due_iso = parse_due_time(d)
            except ValueError as e:
                messagebox.showwarning("格式错误", str(e), parent=dlg)
                return
        dlg.destroy()
        on_save(c, due_iso)

    save_btn = tk.Label(btn_frame, text=save_label, fg=COLORS["accent"],
                        bg=COLORS["surface"], font=FONT_TITLE,
                        cursor="hand2", padx=10)
    save_btn.pack(side=tk.RIGHT, padx=(0, 8))
    save_btn.bind("<Button-1>", lambda e: do_save())

    if not content_readonly:
        content_entry.bind("<Return>", lambda e: due_entry.focus_set())
    due_entry.bind("<Return>", lambda e: do_save())
    content_entry.bind("<Escape>", lambda e: do_cancel())
    due_entry.bind("<Escape>", lambda e: do_cancel())
    if not content_readonly:
        content_entry.focus_set()
    else:
        due_entry.focus_set()


def _dialog_position(parent, dlg, dlg_w, dlg_h):
    """Position dialog so its right edge aligns with parent's right edge."""
    dlg.update_idletasks()
    root_rx = parent.winfo_rootx()
    root_ry = parent.winfo_rooty()
    root_w = parent.winfo_width()
    x = root_rx + root_w - dlg_w
    y = root_ry + 60
    dlg.geometry("%dx%d+%d+%d" % (dlg_w, dlg_h, x, y))
