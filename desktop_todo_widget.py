import json
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE = os.path.join(_BASE_DIR, "tasks.json")

COLORS = {
    "bg": "#1e1e2e",
    "surface": "#2a2a3c",
    "text": "#cdd6f4",
    "text_secondary": "#6c7086",
    "accent": "#89b4fa",
    "done": "#a6e3a1",
    "danger": "#f38ba8",
    "due": "#fab387",
    "overdue": "#f38ba8",
    "input_bg": "#313244",
    "scrollbar": "#45475a",
    "title_bar": "#1a1a2a",
    "notify_bg": "#1e1e2e",
    "notify_border": "#89b4fa",
}

FONT = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 8)
FONT_TITLE = ("Microsoft YaHei UI", 10, "bold")
FONT_HEADER = ("Microsoft YaHei UI", 9, "bold")
FONT_NOTIFY = ("Microsoft YaHei UI", 11)
FONT_NOTIFY_SMALL = ("Microsoft YaHei UI", 9)


def load_tasks():
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def parse_due_time(text):
    now = datetime.now()
    text = text.strip()
    if text.startswith("明天"):
        time_str = text[2:].strip()
        target_date = now.date() + timedelta(days=1)
    elif text.startswith("后天"):
        time_str = text[2:].strip()
        target_date = now.date() + timedelta(days=2)
    elif text.startswith("今天"):
        time_str = text[2:].strip()
        target_date = now.date()
    else:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            return dt.isoformat()
        except ValueError:
            pass
        time_str = text
        target_date = now.date()
    time_str = time_str.strip()
    try:
        hour, minute = map(int, time_str.split(":"))
    except Exception:
        raise ValueError("无法解析时间: " + text)
    target_dt = datetime(target_date.year, target_date.month, target_date.day,
                         hour, minute)
    return target_dt.isoformat()


def _cn_to_digits(text):
    """Convert Chinese number words in text to digits for parsing."""
    cn = [
        # compound: tens + ones (longest first, before components)
        ("五十九", "59"), ("五十八", "58"), ("五十七", "57"), ("五十六", "56"),
        ("五十五", "55"), ("五十四", "54"), ("五十三", "53"), ("五十二", "52"),
        ("五十一", "51"),
        ("四十九", "49"), ("四十八", "48"), ("四十七", "47"), ("四十六", "46"),
        ("四十五", "45"), ("四十四", "44"), ("四十三", "43"), ("四十二", "42"),
        ("四十一", "41"),
        ("三十九", "39"), ("三十八", "38"), ("三十七", "37"), ("三十六", "36"),
        ("三十五", "35"), ("三十四", "34"), ("三十三", "33"), ("三十二", "32"),
        ("三十一", "31"),
        ("二十九", "29"), ("二十八", "28"), ("二十七", "27"), ("二十六", "26"),
        ("二十五", "25"), ("二十四", "24"), ("二十三", "23"), ("二十二", "22"),
        ("二十一", "21"),
        ("二十", "20"),
        ("十九", "19"), ("十八", "18"), ("十七", "17"), ("十六", "16"),
        ("十五", "15"), ("十四", "14"), ("十三", "13"), ("十二", "12"),
        ("十一", "11"), ("十", "10"),
        ("九", "9"), ("八", "8"), ("七", "7"), ("六", "6"),
        ("五", "5"), ("四", "4"), ("三", "3"), ("二", "2"),
        ("两", "2"), ("一", "1"), ("零", "0"),
        # tens only
        ("五十", "50"), ("四十", "40"), ("三十", "30"),
    ]
    result = text
    for word, digit in cn:
        result = result.replace(word, digit)
    return result


def parse_voice_task(text):
    """Extract task content and due time from voice input.
    e.g. "今天下午三点提醒我出去玩" -> ("出去玩", iso_string today 15:00)
    e.g. "明天上午十点开会"       -> ("开会", iso_string tomorrow 10:00)
    Returns (content, due_iso) or (original_text, None) if no time found.
    """
    text = text.strip()
    now = datetime.now()

    # ---- normalize Chinese numbers to digits ----
    normalized = _cn_to_digits(text)

    # ---- figure out target date ----
    date_offset = 0
    for pattern, offset in [("今天", 0), ("明天", 1), ("后天", 2)]:
        if pattern in text:
            date_offset = offset
            break
    target_date = now.date() + timedelta(days=date_offset)

    # ---- figure out am/pm ----
    am_pm = 0
    for word, offset in [("上午", 0), ("中午", 12), ("下午", 12), ("晚上", 12),
                         ("早晨", 0), ("早上", 0)]:
        if word in text:
            am_pm = offset
            break

    # ---- extract hour and minute from normalized text ----
    hour = None
    minute = 0

    # "3点半" / "三点半" — half-past must be checked first
    tm = re.search(r'(\d{1,2})\s*[点:：时]?\s*半', normalized)
    if tm:
        hour = int(tm.group(1))
        minute = 30
    else:
        # "3点15分", "3:15", "3：15", "3点15", "3时15"
        tm = re.search(r'(\d{1,2})\s*[点:：时]\s*(\d{1,2})?\s*[分]?', normalized)
        if tm:
            hour = int(tm.group(1))
            minute = int(tm.group(2)) if tm.group(2) else 0
        else:
            # "15:30" or "3:30" (pure digits colon)
            tm = re.search(r'(\d{1,2}):(\d{2})', normalized)
            if tm:
                hour = int(tm.group(1))
                minute = int(tm.group(2))
            else:
                # bare "3点" or "3时" with nothing after
                tm = re.search(r'(\d{1,2})\s*[点:：时]', normalized)
                if tm:
                    hour = int(tm.group(1))
                    minute = 0

    if hour is None:
        return (text, None)

    # apply am/pm offset
    if am_pm and hour <= 12:
        if hour == 12:
            hour = 0 if am_pm == 0 else 12
        else:
            hour = hour + am_pm
    elif hour == 12 and am_pm == 0:
        hour = 0

    hour = hour % 24
    minute = minute % 60

    try:
        due_dt = datetime(target_date.year, target_date.month, target_date.day,
                          hour, minute)
        due_iso = due_dt.isoformat()
    except ValueError:
        return (text, None)

    # ---- extract content: strip date/time words and connector verbs ----
    content = text
    # remove date words
    content = re.sub(r'(今天|明天|后天)', '', content)
    # remove am/pm words
    content = re.sub(r'(上午|下午|中午|晚上|早晨|早上)', '', content)
    # remove Chinese-number time expression (十二点四十五, 三点半, etc.)
    cn_num = r'[零一二两三四五六七八九十廿卅]'
    content = re.sub(cn_num + r'+[点:：时]' + cn_num + r'*[分半]?', '', content)
    # remove digit time expression (12:41, 3点15分, 3点半, etc.)
    content = re.sub(r'\d{1,2}\s*[点:：时]\s*\d{0,2}\s*[分]?', '', content)
    content = re.sub(r'\d{1,2}点半', '', content)
    content = re.sub(r'\d{1,2}:\d{2}', '', content)
    # remove connector verbs
    content = re.sub(r'(提醒我|提醒|叫我|通知我|记住|记得|要|定个|设置|帮我|给我)', '', content)
    # remove standalone "我" if it became orphaned after connector removal
    content = re.sub(r'^我', '', content)
    # collapse whitespace
    content = re.sub(r'\s+', '', content)

    if not content:
        return (text, due_iso)

    return (content, due_iso)


class DesktopTodoWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("待办事项")
        self.root.configure(bg=COLORS["bg"])
        self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-toolwindow", True)
        except Exception:
            pass

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        w, h = 320, 450
        x = sw - w - 40
        y = 40
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(280, 300)

        self.collapsed = False
        self.normal_height = 450
        self.collapsed_height = 32
        self._ctx_task_id = None
        self._notified_ids = set()
        self._due_labels = {}   # task_id -> label widget for countdown update
        self._refresh_count = 0

        self._build_ui()
        self._refresh_task_list()
        self._periodic_check()

    # ==================== periodic / countdown ====================

    def _periodic_check(self):
        self._refresh_count += 1
        self._check_due_notifications()
        self._schedule_exact_notifications()
        self._update_countdowns()
        # full rebuild every 30 cycles to catch external file changes
        if self._refresh_count % 30 == 0:
            self._refresh_task_list()
            self._refresh_count = 0
        self.root.after(1000, self._periodic_check)

    def _update_countdowns(self):
        """Only update due-time label texts, no widget rebuild."""
        tasks = load_tasks()
        task_map = {t["id"]: t for t in tasks}
        # remove labels for deleted tasks
        gone = [tid for tid in self._due_labels if tid not in task_map]
        for tid in gone:
            del self._due_labels[tid]
        # update existing labels
        for tid, lbl in list(self._due_labels.items()):
            t = task_map.get(tid)
            if not t or t.get("done"):
                continue
            due_str = self._format_due(t.get("due"))
            if due_str:
                is_overdue = "已过期" in due_str
                lbl.configure(text=due_str,
                              fg=COLORS["overdue"] if is_overdue else COLORS["due"])
            else:
                lbl.configure(text="")

    def _schedule_exact_notifications(self):
        now = datetime.now()
        tasks = load_tasks()
        for t in tasks:
            if t.get("done"):
                continue
            due_str = t.get("due")
            if not due_str or t["id"] in self._notified_ids:
                continue
            try:
                due_dt = datetime.fromisoformat(due_str)
            except Exception:
                continue
            delta_ms = (due_dt - now).total_seconds() * 1000
            if 0 < delta_ms < 3000:
                self.root.after(int(delta_ms),
                                lambda tid=t["id"], content=t["content"],
                                due=due_dt:
                                self._fire_notification(tid, content, due))

    # ==================== notification ====================

    def _check_due_notifications(self):
        now = datetime.now()
        tasks = load_tasks()
        for t in tasks:
            if t.get("done"):
                continue
            due_str = t.get("due")
            if not due_str:
                continue
            try:
                due_dt = datetime.fromisoformat(due_str)
            except Exception:
                continue
            delta = (now - due_dt).total_seconds()
            if 0 <= delta < 60 and t["id"] not in self._notified_ids:
                self._fire_notification(t["id"], t["content"], due_dt)
            elif delta < 0:
                self._notified_ids.discard(t["id"])

    def _fire_notification(self, task_id, content, due_dt):
        self._notified_ids.add(task_id)
        self._show_notification(content, due_dt)

    def _show_notification(self, content, due_dt):
        popup = tk.Toplevel(self.root)
        popup.title("")
        popup.configure(bg=COLORS["notify_bg"])
        popup.overrideredirect(True)
        popup.wm_attributes("-topmost", True)

        w, h = 300, 80
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - w - 20
        start_y = sh + 20
        end_y = sh - h - 60
        popup.geometry(f"{w}x{h}+{x}+{start_y}")

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
            popup.geometry(f"{w}x{h}+{x}+{y}")
            popup.after(20, lambda: slide_up(step + 1, steps))

        def dismiss():
            popup.destroy()

        popup.bind("<Button-1>", lambda e: dismiss())
        inner.bind("<Button-1>", lambda e: dismiss())
        slide_up()
        popup.after(8000, dismiss)

    # ==================== UI build ====================

    def _build_ui(self):
        # title bar
        self.title_bar = tk.Frame(self.root, bg=COLORS["title_bar"], height=28)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)

        self.title_label = tk.Label(
            self.title_bar, text="待办事项", fg=COLORS["text"],
            bg=COLORS["title_bar"], font=FONT_HEADER)
        self.title_label.pack(side=tk.LEFT, padx=10, pady=2)

        btn_frame = tk.Frame(self.title_bar, bg=COLORS["title_bar"])
        btn_frame.pack(side=tk.RIGHT, padx=4)

        self.collapse_btn = tk.Label(
            btn_frame, text="_", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.collapse_btn.pack(side=tk.LEFT)
        self.collapse_btn.bind("<Button-1>", self._toggle_collapse)

        self.close_btn = tk.Label(
            btn_frame, text="X", fg=COLORS["danger"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.close_btn.pack(side=tk.LEFT)
        self.close_btn.bind("<Button-1>", lambda e: self.root.destroy())

        # content
        self.content = tk.Frame(self.root, bg=COLORS["bg"])
        self.content.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 4))

        list_container = tk.Frame(self.content, bg=COLORS["bg"])
        list_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            list_container, bg=COLORS["bg"], bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(
            list_container, orient=tk.VERTICAL, command=self.canvas.yview,
            bg=COLORS["scrollbar"], troughcolor=COLORS["bg"],
            activebackground=COLORS["accent"])
        self.task_frame = tk.Frame(self.canvas, bg=COLORS["bg"])

        self.task_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.task_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollbar.bind("<MouseWheel>", self._on_mousewheel)

        # input
        input_frame = tk.Frame(self.content, bg=COLORS["bg"])
        input_frame.pack(fill=tk.X, pady=(4, 0))

        self.entry = tk.Entry(
            input_frame, bg=COLORS["input_bg"], fg=COLORS["text"],
            insertbackground=COLORS["text"], font=FONT, relief="flat", bd=6)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.entry.bind("<Return>", self._quick_add_task)
        self.entry.configure(fg=COLORS["text_secondary"])
        self.entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry.bind("<FocusOut>", self._on_entry_focus_out)
        self._placeholder = "输入新任务，回车添加"
        self.entry.insert(0, self._placeholder)

        self.mic_btn = tk.Label(
            input_frame, text="mic", fg=COLORS["accent"], bg=COLORS["bg"],
            font=FONT_SMALL, cursor="hand2", padx=4)
        self.mic_btn.pack(side=tk.RIGHT)
        self.mic_btn.bind("<Button-1>", self._start_voice_input)

        self.add_btn = tk.Label(
            input_frame, text="+", fg=COLORS["accent"], bg=COLORS["bg"],
            font=("Microsoft YaHei UI", 14, "bold"), cursor="hand2", padx=6)
        self.add_btn.pack(side=tk.RIGHT)
        self.add_btn.bind("<Button-1>", self._add_task)

        # context menu
        self.ctx_menu = tk.Menu(self.root, tearoff=0, bg=COLORS["surface"],
                                fg=COLORS["text"],
                                activebackground=COLORS["accent"],
                                activeforeground=COLORS["bg"])
        self.ctx_menu.add_command(label="编辑", command=self._ctx_edit)
        self.ctx_menu.add_command(label="设置提醒", command=self._ctx_set_due)
        self.ctx_menu.add_command(label="标记完成/取消", command=self._ctx_toggle_done)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="删除", command=self._ctx_delete)

    # ---- helpers ----

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_entry_focus_in(self, event):
        if self.entry.get() == self._placeholder:
            self.entry.delete(0, tk.END)
            self.entry.configure(fg=COLORS["text"])

    def _on_entry_focus_out(self, event):
        if not self.entry.get().strip():
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=COLORS["text_secondary"])

    def _toggle_collapse(self, event=None):
        if self.collapsed:
            self.root.geometry(f"{self.root.winfo_width()}x{self.normal_height}")
            self.content.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 4))
            self.collapse_btn.configure(text="_")
            self.collapsed = False
        else:
            self.normal_height = self.root.winfo_height()
            self.content.pack_forget()
            self.root.geometry(f"{self.root.winfo_width()}x{self.collapsed_height}")
            self.collapse_btn.configure(text="O")
            self.collapsed = True

    # ---- dialog positioning ----

    def _dialog_position(self, dlg, dlg_w, dlg_h):
        """Position dialog so its right edge aligns with widget's right edge."""
        dlg.update_idletasks()
        root_rx = self.root.winfo_rootx()
        root_ry = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        x = root_rx + root_w - dlg_w
        y = root_ry + 60
        dlg.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")

    # ---- task operations ----

    def _quick_add_task(self, event=None):
        text = self.entry.get().strip()
        if not text or text == self._placeholder:
            return
        tasks = load_tasks()
        new_id = max((t["id"] for t in tasks), default=0) + 1
        tasks.append({"id": new_id, "content": text, "done": False})
        save_tasks(tasks)
        self.entry.delete(0, tk.END)
        self.entry.configure(fg=COLORS["text"])
        self._refresh_task_list()

    def _add_task(self, event=None):
        text = self.entry.get().strip()
        if text == self._placeholder:
            text = ""
        self._show_task_dialog(
            title="添加待办",
            save_label="添加",
            content_val=text,
            due_val="",
            on_save=lambda c, d: self._do_add(c, d))

    def _do_add(self, content_text, due_iso):
        tasks = load_tasks()
        new_id = max((t["id"] for t in tasks), default=0) + 1
        new_task = {"id": new_id, "content": content_text, "done": False}
        if due_iso:
            new_task["due"] = due_iso
        tasks.append(new_task)
        save_tasks(tasks)
        self.entry.delete(0, tk.END)
        self.entry.configure(fg=COLORS["text"])
        self._suppress_if_past(new_id, due_iso)
        self._refresh_task_list()

    def _suppress_if_past(self, task_id, due_iso):
        """If due time is already in the past, prevent re-notification."""
        if not due_iso:
            return
        try:
            due_dt = datetime.fromisoformat(due_iso)
            if due_dt < datetime.now():
                self._notified_ids.add(task_id)
        except Exception:
            pass

    def _toggle_task(self, task_id):
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["done"] = not t["done"]
                break
        save_tasks(tasks)
        self._refresh_task_list()

    def _delete_task(self, task_id):
        tasks = load_tasks()
        tasks = [t for t in tasks if t["id"] != task_id]
        save_tasks(tasks)
        self._notified_ids.discard(task_id)
        self._refresh_task_list()

    def _edit_task(self, task_id):
        tasks = load_tasks()
        target = next((t for t in tasks if t["id"] == task_id), None)
        if not target:
            return
        due_text = ""
        if target.get("due"):
            try:
                dt = datetime.fromisoformat(target["due"])
                due_text = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        self._show_task_dialog(
            title="编辑任务",
            save_label="保存",
            content_val=target["content"],
            due_val=due_text,
            on_save=lambda c, d: self._do_edit(task_id, c, d))

    def _do_edit(self, task_id, content_text, due_iso):
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["content"] = content_text
                if due_iso:
                    t["due"] = due_iso
                else:
                    t.pop("due", None)
                break
        save_tasks(tasks)
        self._notified_ids.discard(task_id)
        self._suppress_if_past(task_id, due_iso)
        self._refresh_task_list()

    def _set_due(self, task_id):
        tasks = load_tasks()
        target = next((t for t in tasks if t["id"] == task_id), None)
        if not target:
            return
        due_text = ""
        if target.get("due"):
            try:
                dt = datetime.fromisoformat(target["due"])
                due_text = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        self._show_task_dialog(
            title="设置提醒",
            save_label="保存",
            content_val=target["content"],
            due_val=due_text,
            content_readonly=True,
            show_clear=True,
            on_save=lambda c, d: self._do_set_due(task_id, d),
            on_clear=lambda: self._do_clear_due(task_id))

    def _do_set_due(self, task_id, due_iso):
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["due"] = due_iso
                break
        save_tasks(tasks)
        self._notified_ids.discard(task_id)
        self._suppress_if_past(task_id, due_iso)
        self._refresh_task_list()

    def _do_clear_due(self, task_id):
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t.pop("due", None)
                break
        save_tasks(tasks)
        self._notified_ids.discard(task_id)
        self._refresh_task_list()

    # ---- unified dialog ----

    def _show_task_dialog(self, title, save_label, content_val, due_val,
                          on_save, content_readonly=False, show_clear=False,
                          on_clear=None):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg=COLORS["surface"])
        dlg.resizable(False, False)
        dlg.transient(self.root)

        dlg_w, dlg_h = 370, 240
        self._dialog_position(dlg, dlg_w, dlg_h)

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

    # ---- context menu ----

    def _ctx_toggle_done(self):
        if self._ctx_task_id is not None:
            self._toggle_task(self._ctx_task_id)

    def _ctx_edit(self):
        if self._ctx_task_id is not None:
            self._edit_task(self._ctx_task_id)

    def _ctx_set_due(self):
        if self._ctx_task_id is not None:
            self._set_due(self._ctx_task_id)

    def _ctx_delete(self):
        if self._ctx_task_id is not None:
            self._delete_task(self._ctx_task_id)

    def _show_context_menu(self, event, task_id):
        self._ctx_task_id = task_id
        try:
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    # ---- formatting ----

    @staticmethod
    def _format_due(due_str):
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

    # ---- voice input ----

    def _start_voice_input(self, event=None):
        if getattr(self, '_recording', False):
            self._stop_event.set()
            self.mic_btn.configure(fg=COLORS["accent"], text="mic")
            self._recording = False
            return

        self._recording = True
        self._stop_event = threading.Event()
        self.mic_btn.configure(fg=COLORS["danger"], text="stop")
        threading.Thread(target=self._do_voice_recognition, daemon=True).start()
        self.root.after(15000, self._voice_safety_timeout)

    def _voice_safety_timeout(self):
        if getattr(self, '_recording', False):
            self._stop_event.set()
            self.mic_btn.configure(fg=COLORS["accent"], text="mic")
            self._recording = False

    def _do_voice_recognition(self):
        try:
            import pyaudio
        except ImportError as e:
            import traceback
            traceback.print_exc()
            self._recording = False
            self.root.after(0, lambda: self._on_voice_error(
                "请先安装依赖: pip install PyAudio\n" + str(e)))
            return

        CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 16000
        p = None
        stream = None
        frames = []

        try:
            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                           input=True, frames_per_buffer=CHUNK)
            print("[语音] 录音开始，点击 stop 或 15 秒后自动停止")
        except OSError as e:
            import traceback
            traceback.print_exc()
            self._recording = False
            self.root.after(0, lambda: self._on_voice_error(f"未检测到麦克风设备\n{str(e)}"))
            if p: p.terminate()
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._recording = False
            self.root.after(0, lambda: self._on_voice_error(f"录音设备初始化失败: {e}"))
            if p: p.terminate()
            return

        try:
            while not self._stop_event.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[语音] 录音循环异常: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            if p:
                p.terminate()

        self._recording = False
        print(f"[语音] 录音结束，采集 {len(frames)} 帧")

        if not frames:
            self.root.after(0, lambda: self.mic_btn.configure(fg=COLORS["accent"], text="mic"))
            return

        raw_data = b''.join(frames)
        duration_sec = len(raw_data) / (RATE * 2)
        print(f"[语音] 音频时长 {duration_sec:.1f}s")

        if duration_sec < 0.3:
            self.root.after(0, lambda: self._on_voice_error(f"录音时间太短 ({duration_sec:.1f}s)"))
            return

        # Save debug WAV in background
        self._save_debug_wav(raw_data, RATE, CHANNELS, FORMAT)

        # --- Try Vosk (offline, works in China) first ---
        text = self._recognize_vosk(raw_data, RATE)
        if text is None:
            # Fallback: try Google
            text = self._recognize_google(raw_data, RATE)

        if text is None:
            return

        parsed_content, parsed_due = parse_voice_task(text)
        print(f"[语音] 解析结果: content='{parsed_content}', due={parsed_due}")
        self.root.after(0, lambda: self._on_voice_result(parsed_content, parsed_due))

    def _recognize_vosk(self, raw_data, rate):
        try:
            import vosk
            import json
        except ImportError:
            print("[语音] Vosk 未安装，跳过")
            return None

        model_path = os.path.expanduser("~/.vosk-model-cn")
        if not os.path.isdir(model_path):
            model_path = os.path.join(_BASE_DIR, "vosk-model-cn")
        if not os.path.isdir(model_path):
            print(f"[语音] Vosk 模型未找到: {model_path}")
            return None

        try:
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, rate)
            rec.SetWords(True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[语音] Vosk 初始化失败: {e}")
            return None

        # Feed audio in chunks (Vosk needs small chunks for streaming)
        chunk_size = 4000  # bytes
        total = len(raw_data)
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            rec.AcceptWaveform(raw_data[start:end])

        result_json = rec.FinalResult()
        try:
            result = json.loads(result_json)
            text = result.get("text", "").strip()
        except Exception:
            text = ""

        print(f"[语音] Vosk 识别结果: '{text}'")
        if text:
            # Vosk returns space-separated Chinese, join properly
            text = text.replace(" ", "")
            return text
        else:
            self.root.after(0, lambda: self._on_voice_error("Vosk 未识别到语音内容"))
            return None

    def _recognize_google(self, raw_data, rate):
        try:
            import speech_recognition as sr
        except ImportError:
            print("[语音] speech_recognition 未安装")
            return None

        try:
            recognizer = sr.Recognizer()
            audio_data = sr.AudioData(raw_data, rate, 2)
            print("[语音] 尝试 Google 识别...")
            text = recognizer.recognize_google(audio_data, language="zh-CN")
            print(f"[语音] Google 识别结果: {text}")
            return text
        except sr.UnknownValueError:
            self.root.after(0, lambda: self._on_voice_error("未能识别语音内容，请重试"))
        except sr.RequestError as e:
            self.root.after(0, lambda: self._on_voice_error(f"语音识别服务不可用（需联网且国内可能被墙）: {e}"))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self._on_voice_error(f"识别失败: {e}"))
        return None

    def _save_debug_wav(self, raw_data, rate, channels, fmt):
        try:
            import wave
            wav_path = os.path.join(_BASE_DIR, "_voice_debug.wav")
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(rate)
                wf.writeframes(raw_data)
            print(f"[语音] 录音已保存: {wav_path}")
        except Exception:
            pass  # debug only, never block on this

    def _on_voice_result(self, content, due_iso):
        self.mic_btn.configure(fg=COLORS["accent"], text="mic")

        if due_iso:
            tasks = load_tasks()
            new_id = max((t["id"] for t in tasks), default=0) + 1
            new_task = {"id": new_id, "content": content, "done": False, "due": due_iso}
            tasks.append(new_task)
            save_tasks(tasks)
            self._suppress_if_past(new_id, due_iso)
            self._refresh_task_list()
            if self.entry.get() == self._placeholder:
                self.entry.delete(0, tk.END)
                self.entry.configure(fg=COLORS["text"])
            self.entry.delete(0, tk.END)
            self.entry.insert(0, f"已创建: {content}")
            self.root.after(2500, lambda: self._clear_entry_if_feedback())
        else:
            if self.entry.get() == self._placeholder:
                self.entry.delete(0, tk.END)
                self.entry.configure(fg=COLORS["text"])
            current = self.entry.get()
            if current:
                self.entry.insert(tk.END, " " + content)
            else:
                self.entry.insert(0, content)

    def _clear_entry_if_feedback(self):
        try:
            current = self.entry.get()
            if current.startswith("已创建:"):
                self.entry.delete(0, tk.END)
                self.entry.insert(0, self._placeholder)
                self.entry.configure(fg=COLORS["text_secondary"])
        except Exception:
            pass

    def _on_voice_error(self, msg):
        self.mic_btn.configure(fg=COLORS["accent"], text="mic")
        print(f"[语音] 错误: {msg}")
        messagebox.showwarning("语音识别", msg)

    # ---- render ----

    def _refresh_task_list(self):
        self._due_labels.clear()

        for w in self.task_frame.winfo_children():
            w.destroy()

        tasks = load_tasks()
        tasks.sort(key=lambda t: (t.get("done", False), t.get("id", 0)))

        if not tasks:
            empty_label = tk.Label(
                self.task_frame,
                text="暂无任务\n下方输入框添加，右键可编辑/设提醒",
                fg=COLORS["text_secondary"], bg=COLORS["bg"], font=FONT,
                justify=tk.CENTER)
            empty_label.pack(pady=30)
            return

        for t in tasks:
            row = tk.Frame(self.task_frame, bg=COLORS["bg"])
            row.pack(fill=tk.X, pady=1)

            cb_text = "[V]" if t["done"] else "[ ]"
            cb_color = COLORS["done"] if t["done"] else COLORS["text_secondary"]
            cb = tk.Label(row, text=cb_text, fg=cb_color, bg=COLORS["bg"],
                          font=FONT, cursor="hand2", padx=2)
            cb.pack(side=tk.LEFT)
            cb.bind("<Button-1>", lambda e, tid=t["id"]: self._toggle_task(tid))

            text_fg = COLORS["text_secondary"] if t["done"] else COLORS["text"]
            text_font = FONT
            if t["done"]:
                text_font = ("Microsoft YaHei UI", 10, "overstrike")

            text_frame = tk.Frame(row, bg=COLORS["bg"])
            text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            content_label = tk.Label(
                text_frame, text=t["content"], fg=text_fg, bg=COLORS["bg"],
                font=text_font, anchor="w", justify=tk.LEFT)
            content_label.pack(side=tk.LEFT)

            content_label.bind("<Double-Button-1>",
                               lambda e, tid=t["id"]: self._edit_task(tid))
            cb.bind("<Double-Button-1>",
                    lambda e, tid=t["id"]: self._edit_task(tid))

            due_str = self._format_due(t.get("due"))
            if due_str or t.get("due"):
                if not due_str:
                    due_str = ""
                is_overdue = "已过期" in due_str
                due_color = COLORS["overdue"] if is_overdue else COLORS["due"]
                due_label = tk.Label(
                    text_frame, text=due_str, fg=due_color, bg=COLORS["bg"],
                    font=FONT_SMALL, anchor="w")
                due_label.pack(side=tk.LEFT, padx=(8, 0))
                due_label.bind("<Double-Button-1>",
                               lambda e, tid=t["id"]: self._edit_task(tid))
                # store reference for countdown updates
                if not t.get("done"):
                    self._due_labels[t["id"]] = due_label

            del_btn = tk.Label(row, text="X", fg=COLORS["text_secondary"],
                               bg=COLORS["bg"], font=FONT_SMALL,
                               cursor="hand2", padx=4)
            del_btn.pack(side=tk.RIGHT)
            del_btn.bind("<Button-1>",
                         lambda e, tid=t["id"]: self._delete_task(tid))
            del_btn.bind("<Enter>",
                         lambda e, lbl=del_btn: lbl.configure(fg=COLORS["danger"]))
            del_btn.bind("<Leave>",
                         lambda e, lbl=del_btn: lbl.configure(fg=COLORS["text_secondary"]))

            for child in (row, cb, content_label, text_frame):
                child.bind("<Button-3>",
                           lambda e, tid=t["id"]: self._show_context_menu(e, tid))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = DesktopTodoWidget()
    app.run()
