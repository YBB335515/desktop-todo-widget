import json
import os
import sys
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
