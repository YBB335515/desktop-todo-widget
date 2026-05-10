"""Main floating window widget — task list, input, voice, notifications."""
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings_manager import load_settings
from core.natural_language import parse_voice_task
from core.reminder_service import (
    find_due_for_notification,
    find_expired_notification_flags,
    find_imminent_tasks,
)
from core.single_instance import release_instance
from core.task_manager import get_next_id, load_tasks, save_tasks
from core.voice_recognizer import VoiceRecognizer, voice_log, VOICE_LOG_FILE, \
    download_vosk_model, is_model_missing
from ui.close_dialog import show_close_dialog
from ui.edit_dialog import show_task_dialog
from ui.reminder_popup import show_reminder_popup
from ui.settings_dialog import show_settings_dialog
from ui.tray_icon import TrayIcon
from utils.common_utils import BASE_DIR, COLORS, DATA_DIR, FONT, FONT_HEADER, FONT_SMALL, \
    FONT_TITLE, FROZEN, format_due


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
        self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
        self.root.minsize(280, 300)

        self.collapsed = False
        self.normal_height = 450
        self.collapsed_height = 32
        self._ctx_task_id = None
        self._notified_ids = set()
        self._due_labels = {}
        self._refresh_count = 0
        self._tray = TrayIcon(
            self.root,
            on_restore=self._restore_from_tray,
            on_quit=self._quit_app,
        )

        self._build_ui()
        self._refresh_task_list()
        self._periodic_check()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================== periodic / countdown ====================

    def _periodic_check(self):
        self._refresh_count += 1
        self._check_due_notifications()
        self._schedule_exact_notifications()
        self._update_countdowns()
        if self._refresh_count % 30 == 0:
            self._refresh_task_list()
            self._refresh_count = 0
        self.root.after(1000, self._periodic_check)

    def _update_countdowns(self):
        tasks = load_tasks()
        task_map = {t["id"]: t for t in tasks}
        gone = [tid for tid in self._due_labels if tid not in task_map]
        for tid in gone:
            del self._due_labels[tid]
        for tid, lbl in list(self._due_labels.items()):
            t = task_map.get(tid)
            if not t or t.get("done"):
                continue
            due_str = format_due(t.get("due"))
            if due_str:
                is_overdue = "已过期" in due_str
                lbl.configure(text=due_str,
                              fg=COLORS["overdue"] if is_overdue else COLORS["due"])
            else:
                lbl.configure(text="")

    def _schedule_exact_notifications(self):
        tasks = load_tasks()
        imminent = find_imminent_tasks(tasks, self._notified_ids)
        for t, delay_ms in imminent:
            self.root.after(delay_ms,
                           lambda tid=t["id"], content=t["content"],
                           due=datetime.fromisoformat(t["due"]):
                           self._fire_notification(tid, content, due))

    # ==================== notification ====================

    def _check_due_notifications(self):
        tasks = load_tasks()
        for t in find_due_for_notification(tasks, self._notified_ids):
            due_dt = datetime.fromisoformat(t["due"])
            self._fire_notification(t["id"], t["content"], due_dt)

        for tid in find_expired_notification_flags(tasks, self._notified_ids):
            self._notified_ids.discard(tid)

    def _fire_notification(self, task_id, content, due_dt):
        self._notified_ids.add(task_id)
        show_reminder_popup(self.root, content, due_dt)

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

        self.settings_btn = tk.Label(
            btn_frame, text="...", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.settings_btn.pack(side=tk.LEFT)
        self.settings_btn.bind("<Button-1>", self._open_settings)

        self.collapse_btn = tk.Label(
            btn_frame, text="_", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.collapse_btn.pack(side=tk.LEFT)
        self.collapse_btn.bind("<Button-1>", self._toggle_collapse)

        self.close_btn = tk.Label(
            btn_frame, text="X", fg=COLORS["danger"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.close_btn.pack(side=tk.LEFT)
        self.close_btn.bind("<Button-1>", lambda e: self._on_close())

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
            self.root.geometry(
                "%dx%d" % (self.root.winfo_width(), self.normal_height))
            self.content.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 4))
            self.collapse_btn.configure(text="_")
            self.collapsed = False
        else:
            self.normal_height = self.root.winfo_height()
            self.content.pack_forget()
            self.root.geometry(
                "%dx%d" % (self.root.winfo_width(), self.collapsed_height))
            self.collapse_btn.configure(text="O")
            self.collapsed = True

    def _open_settings(self, event=None):
        show_settings_dialog(self.root)

    # ---- task operations ----

    def _quick_add_task(self, event=None):
        text = self.entry.get().strip()
        if not text or text == self._placeholder:
            return
        tasks = load_tasks()
        new_id = get_next_id(tasks)

        parsed_content, parsed_due = parse_voice_task(text)
        if parsed_due:
            tasks.append({"id": new_id, "content": parsed_content, "done": False,
                         "due": parsed_due})
        else:
            tasks.append({"id": new_id, "content": text, "done": False})

        save_tasks(tasks)
        self.entry.delete(0, tk.END)
        self.entry.configure(fg=COLORS["text"])
        self._refresh_task_list()

    def _add_task(self, event=None):
        text = self.entry.get().strip()
        if text == self._placeholder:
            text = ""
        show_task_dialog(
            self.root,
            title="添加待办",
            save_label="添加",
            content_val=text,
            due_val="",
            on_save=lambda c, d: self._do_add(c, d))

    def _do_add(self, content_text, due_iso):
        tasks = load_tasks()
        new_id = get_next_id(tasks)
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
        show_task_dialog(
            self.root,
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
        show_task_dialog(
            self.root,
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

    # ---- voice input ----

    def _start_voice_input(self, event=None):
        if getattr(self, '_recording', False):
            self._stop_event.set()
            self.mic_btn.configure(fg=COLORS["accent"], text="mic")
            self._recording = False
            return

        voice_log("=== 语音识别开始 (frozen=%s) ===" % FROZEN)
        self._recording = True
        self._stop_event = threading.Event()
        self.mic_btn.configure(fg=COLORS["danger"], text="stop")
        self._voice_errors = []
        threading.Thread(target=self._do_voice_recognition, daemon=True).start()
        self.root.after(15000, self._voice_safety_timeout)

    def _voice_safety_timeout(self):
        if getattr(self, '_recording', False):
            self._stop_event.set()
            self.mic_btn.configure(fg=COLORS["accent"], text="mic")
            self._recording = False

    def _do_voice_recognition(self):
        rate = 16000
        voice_errors = []
        text = None

        voice_log("Step 1: 尝试 PyAudio 录音...")
        raw_data = VoiceRecognizer.capture_audio(rate, self._stop_event, voice_errors)

        self._recording = False

        if raw_data is not None:
            duration_sec = len(raw_data) / (rate * 2)
            voice_log("PyAudio 录音成功: %.1fs, %d bytes" % (duration_sec, len(raw_data)))
            print("[语音] 音频时长 %.1fs" % duration_sec)

            if duration_sec >= 0.3:
                VoiceRecognizer.save_debug_wav(raw_data, rate, 1, 8)

                voice_log("Step 2: 尝试 Vosk 离线识别...")
                text = VoiceRecognizer.recognize_vosk(raw_data, rate, voice_errors)
                if text is None:
                    voice_log("Vosk 失败，尝试 Google 在线识别...")
                    text = VoiceRecognizer.recognize_google(raw_data, rate, voice_errors)
            else:
                msg = "录音时间太短 (%.1fs)" % duration_sec
                voice_errors.append(msg)
                voice_log(msg)
        else:
            err_summary = "; ".join(voice_errors) if voice_errors else "未知原因"
            voice_log("PyAudio 录音失败: %s" % err_summary)

        if text is None:
            voice_log("PCM引擎未识别到内容，尝试 SAPI 系统引擎...")
            print("[语音] PCM引擎未识别到内容，尝试 SAPI...")
            text = VoiceRecognizer.recognize_sapi(voice_errors)

        if text is None:
            voice_log("所有识别引擎均失败")
            for e in voice_errors:
                voice_log("  - %s" % e)
            self.root.after(0, lambda: self.mic_btn.configure(
                fg=COLORS["accent"], text="mic"))
            if is_model_missing():
                self.root.after(0, lambda: self._offer_model_download(raw_data, rate))
            else:
                detail = "\n".join(voice_errors) if voice_errors else "所有识别引擎均失败"
                self.root.after(0, lambda: self._on_voice_error(
                    "语音识别失败\n%s" % detail))
            return

        voice_log("识别成功: '%s'" % text)
        parsed_content, parsed_due = parse_voice_task(text)
        voice_log("解析结果: content='%s', due=%s" % (parsed_content, parsed_due))
        print("[语音] 解析结果: content='%s', due=%s" % (parsed_content, parsed_due))
        self.root.after(0, lambda: self._on_voice_result(parsed_content, parsed_due))

    def _on_voice_result(self, content, due_iso):
        self.mic_btn.configure(fg=COLORS["accent"], text="mic")

        if due_iso:
            tasks = load_tasks()
            new_id = get_next_id(tasks)
            new_task = {"id": new_id, "content": content, "done": False, "due": due_iso}
            tasks.append(new_task)
            save_tasks(tasks)
            self._suppress_if_past(new_id, due_iso)
            self._refresh_task_list()
            if self.entry.get() == self._placeholder:
                self.entry.delete(0, tk.END)
                self.entry.configure(fg=COLORS["text"])
            self.entry.delete(0, tk.END)
            self.entry.insert(0, "已创建: %s" % content)
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
        print("[语音] 错误: %s" % msg)
        voice_log("最终错误: %s" % msg)
        full_msg = "%s\n\n详细错误日志已保存到:\n%s" % (msg, VOICE_LOG_FILE)
        messagebox.showwarning("语音识别", full_msg)

    def _offer_model_download(self, raw_data=None, rate=16000):
        """Offer to download the Vosk speech model when it's missing."""
        result = messagebox.askyesno(
            "语音模型缺失",
            "未找到离线语音模型（vosk-model-small-cn）。\n\n"
            "需要下载约 42MB 的语音识别模型才能使用语音功能。\n"
            "下载过程可能需要几分钟。\n\n"
            "是否立即下载？",
            parent=self.root)
        if not result:
            return

        # Build a progress popup
        popup = tk.Toplevel(self.root)
        popup.title("下载语音模型")
        popup.geometry("380x120")
        popup.configure(bg=COLORS["bg"])
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)

        # Center on parent
        popup.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 120) // 2
        popup.geometry("+%d+%d" % (px, py))

        status_label = tk.Label(
            popup, text="正在准备下载...", fg=COLORS["text"], bg=COLORS["bg"],
            font=FONT)
        status_label.pack(pady=(20, 10))

        import tkinter.ttk as ttk
        progress = ttk.Progressbar(
            popup, mode="determinate", length=340, maximum=100)
        progress.pack(pady=(0, 20))

        def update_progress(pct, status):
            try:
                progress["value"] = pct
                status_label.configure(text=status)
                popup.update_idletasks()
            except Exception:
                pass

        error_ref = []

        def do_download():
            try:
                download_vosk_model(progress_callback=update_progress)
                popup.after(0, lambda: popup.destroy())
                popup.after(0, lambda: messagebox.showinfo(
                    "下载完成",
                    "语音模型安装成功！\n\n请重新点击麦克风按钮开始语音输入。",
                    parent=self.root))
            except Exception as e:
                error_ref.append(str(e))
                popup.after(0, lambda: popup.destroy())
                popup.after(0, lambda: messagebox.showerror(
                    "下载失败",
                    "模型下载失败：\n%s\n\n请检查网络连接后重试。\n"
                    "也可以手动下载 vosk-model-small-cn-0.22\n"
                    "解压到: %s" % (error_ref[0],
                                    os.path.expanduser("~/.vosk-model-cn")),
                    parent=self.root))

        threading.Thread(target=do_download, daemon=True).start()
        popup.wait_window()

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

            due_str = format_due(t.get("due"))
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

    # ==================== close / tray ====================

    def _on_close(self, event=None):
        settings = load_settings()
        action = settings.get("close_action", "")
        if action == "minimize":
            self._minimize_to_tray()
        elif action == "quit":
            self._quit_app()
        else:
            result = show_close_dialog(
                self.root,
                on_minimize=lambda: self._minimize_to_tray(),
                on_quit=lambda: self._quit_app())
            if result == "minimize":
                self._minimize_to_tray()
            elif result == "quit":
                self._quit_app()

    def _minimize_to_tray(self):
        self.root.withdraw()
        self._tray.show()

    def _restore_from_tray(self):
        self._tray.hide()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_app(self):
        self._tray.hide()
        release_instance()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
