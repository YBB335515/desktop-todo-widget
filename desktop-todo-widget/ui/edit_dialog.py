"""Task editing dialog — used for add, edit, and set-reminder operations."""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox

from core.natural_language import parse_due_time
from utils.common_utils import COLORS, FONT, FONT_SMALL, FONT_TITLE


def show_task_dialog(parent, title, save_label, content_val, due_val,
                     on_save, content_readonly=False, show_clear=False,
                     on_clear=None, recurring_val=""):
    """Unified dialog for adding, editing, and setting reminders on tasks.

    Args:
        parent: parent tk widget
        title: dialog title
        save_label: text for the save button
        content_val: initial task content text
        due_val: initial due time text
        on_save(content, due_iso, recurring): called when user clicks save
        content_readonly: if True, content field is not editable
        show_clear: if True, show a "clear reminder" button
        on_clear: called when user clicks clear reminder
        recurring_val: initial recurring type (e.g. "monthly_day1")
    """
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=COLORS["surface"])
    dlg.resizable(False, False)
    dlg.transient(parent)

    dlg_w, dlg_h = 370, 400
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
             text="明天15:00 / 后天9:30 / 下个月1号 9:00 / 明年3月15 / 每周五 9:00",
             fg=COLORS["text_secondary"], bg=COLORS["surface"],
             font=FONT_SMALL).pack(anchor="w")

    due_var = tk.StringVar(value=due_val)
    due_entry = tk.Entry(dlg, textvariable=due_var, font=FONT,
                         bg=COLORS["input_bg"], fg=COLORS["text"],
                         insertbackground=COLORS["text"],
                         relief="flat", bd=6)
    due_entry.pack(fill=tk.X, padx=12, pady=(2, 0), ipady=3)

    # quick buttons — row 1: short-term
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

    # quick buttons — row 2: month/year
    quick_frame2 = tk.Frame(dlg, bg=COLORS["surface"])
    quick_frame2.pack(fill=tk.X, padx=12, pady=(2, 0))

    def _next_month_first():
        if now.month == 12:
            return now.replace(year=now.year+1, month=1, day=1)
        return now.replace(month=now.month+1, day=1)

    nm = _next_month_first()
    for lbl, val in [
        ("下个月1号 9:00", nm.strftime("%Y-%m-%d") + " 09:00"),
        ("下个月1号 15:00", nm.strftime("%Y-%m-%d") + " 15:00"),
    ]:
        btn = tk.Label(quick_frame2, text=lbl, fg=COLORS["accent"],
                       bg=COLORS["surface"], font=FONT_SMALL,
                       cursor="hand2", padx=5)
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda e, v=val: due_var.set(v))

    # recurring type selector
    recurring_type_frame = tk.Frame(dlg, bg=COLORS["surface"])
    recurring_type_frame.pack(fill=tk.X, padx=12, pady=(4, 0))
    tk.Label(recurring_type_frame, text="循环:", fg=COLORS["text_secondary"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)

    # Determine initial type from recurring_val
    _init_type = "none"
    _init_mday = 1
    _init_ym = 1
    _init_yd = 1
    _init_wd = 1
    _init_bwd = 1
    if recurring_val and (recurring_val.startswith("monthly:") or recurring_val == "monthly_day1"):
        _init_type = "monthly"
        if recurring_val.startswith("monthly:"):
            try:
                _init_mday = int(recurring_val.split(":", 1)[1])
            except:
                pass
    elif recurring_val and recurring_val.startswith("yearly:"):
        _init_type = "yearly"
        try:
            parts = recurring_val.split(":", 1)[1].split("-")
            _init_ym = int(parts[0])
            _init_yd = int(parts[1])
        except:
            pass
    elif recurring_val and recurring_val.startswith("weekly:"):
        _init_type = "weekly"
        try:
            _init_wd = int(recurring_val.split(":", 1)[1]) + 1
        except:
            pass
    elif recurring_val and recurring_val.startswith("biweekly:"):
        _init_type = "biweekly"
        try:
            _init_bwd = int(recurring_val.split(":", 1)[1]) + 1
        except:
            pass

    recurring_type_var = tk.StringVar(value=_init_type)
    type_menu = tk.OptionMenu(recurring_type_frame, recurring_type_var, "none", "weekly", "biweekly", "monthly", "yearly")
    type_menu.configure(bg=COLORS["surface"], fg=COLORS["text"],
                        activebackground=COLORS["surface"],
                        activeforeground=COLORS["text"],
                        font=FONT_SMALL, bd=1, relief="flat",
                        highlightthickness=0)
    type_menu["menu"].configure(bg=COLORS["surface"], fg=COLORS["text"],
                                 activebackground=COLORS["accent"],
                                 activeforeground=COLORS["bg"],
                                 font=FONT_SMALL, bd=0)
    type_menu.pack(side=tk.LEFT, padx=(4, 0))
    # Rebuild menu with Chinese labels
    type_menu["menu"].delete(0, "end")
    for key, label in [("none", "不循环"), ("weekly", "每周"), ("biweekly", "每两周"),
                       ("monthly", "每月"), ("yearly", "每年")]:
        type_menu["menu"].add_command(label=label, command=lambda v=key: recurring_type_var.set(v))

    # Monthly day sub-frame
    monthly_sub = tk.Frame(dlg, bg=COLORS["surface"])
    monthly_day_var = tk.IntVar(value=_init_mday)
    tk.Label(monthly_sub, text="每月", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)
    tk.Spinbox(monthly_sub, from_=1, to=31, textvariable=monthly_day_var,
               width=3, bg=COLORS["input_bg"], fg=COLORS["text"],
               font=FONT_SMALL, bd=1, relief="flat",
               buttonbackground=COLORS["surface"]).pack(side=tk.LEFT, padx=(2, 0))
    tk.Label(monthly_sub, text="号", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)

    # Yearly date sub-frame
    yearly_sub = tk.Frame(dlg, bg=COLORS["surface"])
    yearly_month_var = tk.IntVar(value=_init_ym)
    yearly_day_var = tk.IntVar(value=_init_yd)
    tk.Label(yearly_sub, text="每年", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)
    tk.Spinbox(yearly_sub, from_=1, to=12, textvariable=yearly_month_var,
               width=3, bg=COLORS["input_bg"], fg=COLORS["text"],
               font=FONT_SMALL, bd=1, relief="flat",
               buttonbackground=COLORS["surface"]).pack(side=tk.LEFT, padx=(2, 0))
    tk.Label(yearly_sub, text="月", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)
    tk.Spinbox(yearly_sub, from_=1, to=31, textvariable=yearly_day_var,
               width=3, bg=COLORS["input_bg"], fg=COLORS["text"],
               font=FONT_SMALL, bd=1, relief="flat",
               buttonbackground=COLORS["surface"]).pack(side=tk.LEFT, padx=(2, 0))
    tk.Label(yearly_sub, text="号", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)

    # Weekly sub-frame
    weekly_sub = tk.Frame(dlg, bg=COLORS["surface"])
    weekly_var = tk.IntVar(value=_init_wd)  # 1..7 = 周一..周日
    tk.Label(weekly_sub, text="每周", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)
    weekly_menu = tk.OptionMenu(weekly_sub, weekly_var, *range(1, 8))
    weekly_menu.configure(bg=COLORS["surface"], fg=COLORS["text"],
                          activebackground=COLORS["surface"],
                          activeforeground=COLORS["text"],
                          font=FONT_SMALL, bd=1, relief="flat",
                          highlightthickness=0)
    weekly_menu["menu"].configure(bg=COLORS["surface"], fg=COLORS["text"],
                                  activebackground=COLORS["accent"],
                                  activeforeground=COLORS["bg"],
                                  font=FONT_SMALL, bd=0)
    weekly_menu["menu"].delete(0, "end")
    for wd_idx, wd_label in enumerate(["周一", "周二", "周三", "周四", "周五", "周六", "周日"], start=1):
        weekly_menu["menu"].add_command(label=wd_label,
                                        command=lambda v=wd_idx: weekly_var.set(v))
    weekly_menu.pack(side=tk.LEFT, padx=(2, 0))

    # Biweekly sub-frame
    biweekly_sub = tk.Frame(dlg, bg=COLORS["surface"])
    biweekly_var = tk.IntVar(value=_init_bwd)  # 1..7 = 周一..周日
    tk.Label(biweekly_sub, text="每两周", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.LEFT)
    biweekly_menu = tk.OptionMenu(biweekly_sub, biweekly_var, *range(1, 8))
    biweekly_menu.configure(bg=COLORS["surface"], fg=COLORS["text"],
                            activebackground=COLORS["surface"],
                            activeforeground=COLORS["text"],
                            font=FONT_SMALL, bd=1, relief="flat",
                            highlightthickness=0)
    biweekly_menu["menu"].configure(bg=COLORS["surface"], fg=COLORS["text"],
                                    activebackground=COLORS["accent"],
                                    activeforeground=COLORS["bg"],
                                    font=FONT_SMALL, bd=0)
    biweekly_menu["menu"].delete(0, "end")
    for wd_idx, wd_label in enumerate(["周一", "周二", "周三", "周四", "周五", "周六", "周日"], start=1):
        biweekly_menu["menu"].add_command(label=wd_label,
                                          command=lambda v=wd_idx: biweekly_var.set(v))
    biweekly_menu.pack(side=tk.LEFT, padx=(2, 0))

    def _toggle_sub_frames(*_):
        t = recurring_type_var.get()
        monthly_sub.pack_forget()
        yearly_sub.pack_forget()
        weekly_sub.pack_forget()
        biweekly_sub.pack_forget()
        if t == "monthly":
            monthly_sub.pack(fill=tk.X, padx=12, pady=(2, 0))
        elif t == "yearly":
            yearly_sub.pack(fill=tk.X, padx=12, pady=(2, 0))
        elif t == "weekly":
            weekly_sub.pack(fill=tk.X, padx=12, pady=(2, 0))
        elif t == "biweekly":
            biweekly_sub.pack(fill=tk.X, padx=12, pady=(2, 0))
    recurring_type_var.trace_add("write", _toggle_sub_frames)
    _toggle_sub_frames()

    # Auto-set type and day when due text changes
    def _on_due_recurring_changed(*_):
        import re
        val = due_var.get()
        _wd_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
        if "每月" in val:
            recurring_type_var.set("monthly")
            m = re.search(r'每月\s*(\d{1,2})\s*[号日]', val)
            if m:
                monthly_day_var.set(int(m.group(1)))
        elif "每年" in val:
            recurring_type_var.set("yearly")
            m = re.search(r'每年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]', val)
            if m:
                yearly_month_var.set(int(m.group(1)))
                yearly_day_var.set(int(m.group(2)))
        elif re.search(r'每(?:周|星期|礼拜)\s*([1-7](?![\uff1a:\d])|[一二三四五六日天])', val):
            recurring_type_var.set("weekly")
            m = re.search(r'每(?:周|星期|礼拜)\s*([1-7](?![\uff1a:\d])|[一二三四五六日天])', val)
            ch = m.group(1)
            weekly_var.set(int(ch) if ch.isdigit() else _wd_map.get(ch, 1))
        elif re.search(r'每(?:两|二|2)\s*周|每隔?一?周', val):
            recurring_type_var.set("biweekly")
            m = re.search(r'每(?:两|二|2)\s*周\s*([1-7](?![\uff1a:\d])|[一二三四五六日天])|每隔?一?周\s*([1-7](?![\uff1a:\d])|[一二三四五六日天])', val)
            ch = None
            if m:
                ch = m.group(1) or m.group(2)
            if ch:
                biweekly_var.set(int(ch) if ch.isdigit() else _wd_map.get(ch, 1))
        elif "下个月1号" in val or "下个月1日" in val:
            recurring_type_var.set("monthly")
            monthly_day_var.set(1)
    due_var.trace_add("write", _on_due_recurring_changed)

    # bottom buttons
    btn_frame = tk.Frame(dlg, bg=COLORS["surface"])
    btn_frame.pack(fill=tk.X, padx=12, pady=(8, 8))

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
        # Build recurring value from selector
        rtype = recurring_type_var.get()
        if rtype == "monthly":
            rec_val = f"monthly:{monthly_day_var.get()}"
        elif rtype == "yearly":
            rec_val = f"yearly:{yearly_month_var.get()}-{yearly_day_var.get()}"
        elif rtype == "weekly":
            rec_val = f"weekly:{(weekly_var.get() - 1) % 7}"
        elif rtype == "biweekly":
            rec_val = f"biweekly:{(biweekly_var.get() - 1) % 7}"
        else:
            rec_val = ""
        on_save(c, due_iso, rec_val)

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
