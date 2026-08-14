"""Main floating window widget — task list, input, voice, notifications."""
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

from config.settings_manager import load_settings
from core.natural_language import parse_task_input
from core.reminder_service import (
    find_due_for_notification,
    find_expired_notification_flags,
    find_imminent_tasks,
    should_reset_recurring_after_notify,
)
from core.single_instance import release_instance
from core.task_manager import (
    add_page, delete_page, find_task, format_recurring_display,
    get_active_page_index, get_alert_page_indices, get_next_id, get_pages,
    load_all_tasks, load_tasks, rename_page, reschedule_recurring,
    save_tasks, save_workspace, set_active_page,
)
from core.voice_recognizer import VoiceRecognizer, voice_log, VOICE_LOG_FILE, \
    download_vosk_model, is_model_missing
from ui.close_dialog import show_close_dialog
from ui.edit_dialog import show_task_dialog
from ui.reminder_popup import show_reminder_popup
from ui.settings_dialog import show_settings_dialog
from ui.tray_icon import TrayIcon
from core.weather_checker import analyze_alerts, fetch_temps
from utils.common_utils import BASE_DIR, COLORS, DATA_DIR, FONT, FONT_HEADER, \
    FONT_SMALL, FONT_TITLE, FROZEN, ICONS, format_due


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
        self._click_job = None
        self._due_labels = {}
        self._refresh_count = 0
        self._weather_tick = 0
        self._weather_data = []          # cached temp snapshot
        self._weather_alert_date = ""    # YYYY-MM-DD, today's AI analysis done flag
        self._tray = TrayIcon(
            self.root,
            on_toggle=self._toggle_window,
            on_quit=self._quit_app,
        )
        self._tray.show()

        self._build_ui()
        self._refresh_task_list()
        self._update_weather_display()  # initial weather load
        self._periodic_check()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================== periodic / countdown ====================

    def _periodic_check(self):
        self._refresh_count += 1
        self._weather_tick += 1
        self._check_due_notifications()
        self._schedule_exact_notifications()
        self._update_countdowns()
        self._update_tab_alert_colors()

        if self._refresh_count % 30 == 0:
            self._refresh_task_list()
            self._refresh_count = 0

        # weather: update temp display every 30s
        if self._weather_tick % 30 == 0 and self._weather_bar_visible():
            self._update_weather_display()
        # weather AI analysis once (runs in bg thread, guards itself)
        if self._weather_tick % 30 == 0:
            self._maybe_weather_alert()
        if self._weather_tick >= 60:
            self._weather_tick = 0

        self.root.after(1000, self._periodic_check)

    def _weather_bar_visible(self):
        settings = load_settings()
        return settings.get("weather_enabled", True)

    def _update_weather_display(self):
        """Fetch weather in background thread to avoid blocking UI."""
        threading.Thread(target=self._do_weather_fetch, daemon=True).start()

    def _do_weather_fetch(self):
        """Background thread: fetch temps and schedule UI update."""
        try:
            settings = load_settings()
            if not settings.get("weather_enabled", True):
                self.root.after(0, lambda: (
                    self._weather_p1.configure(text="\u2600 \u5929\u6c14\u5df2\u5173\u95ed"),
                    self._weather_s1.configure(text=""),
                    self._weather_p2.configure(text=""),
                    self._weather_s2.configure(text="")))
                return
            temps = fetch_temps(settings)
            self.root.after(0, lambda: self._apply_weather_display(temps))
        except Exception:
            self.root.after(0, lambda: (
                self._weather_p1.configure(text="\u2600 \u83b7\u53d6\u5931\u8d25"),
                self._weather_s1.configure(text=""),
                self._weather_p2.configure(text=""),
                self._weather_s2.configure(text="")))

    def _apply_weather_display(self, temps):
        """Apply weather data to UI (main thread only) \u2014 4-row layout.

        Row layout per city:
          Primary:   "\U0001f324 Hefei 28\u00b0C Sunny"
          Secondary: "\U0001f327 \u5927\u96e8" (only during extreme weather, hidden otherwise)
        """
        self._weather_data = temps
        has_any_bad = False

        city_labels = [(self._weather_p1, self._weather_s1),
                       (self._weather_p2, self._weather_s2)]

        for idx, r in enumerate(temps):
            p_label, s_label = city_labels[idx] if idx < 2 else (None, None)
            if p_label is None:
                break

            desc = r.get("desc", "")
            desc_lower = desc.lower()

            # ---- Primary row: icon + city + temp ----
            icon_map = {"sunny": "\u2600", "clear": "\u2600", "partly cloudy": "\u26c5",
                        "cloudy": "\u2601", "overcast": "\u2601", "mist": "\U0001f32b",
                        "fog": "\U0001f32b", "rain": "\U0001f327", "light rain": "\U0001f326",
                        "heavy rain": "\U0001f327", "thunder": "\u26c8", "snow": "\u2744",
                        "light snow": "\U0001f328", "patchy rain": "\U0001f326",
                        "wind": "\U0001f4a8", "windy": "\U0001f4a8", "typhoon": "\U0001f300",
                        "gale": "\U0001f4a8", "squall": "\U0001f4a8"}
            icon = icon_map.get(desc_lower, "\U0001f324")

            # Short description for primary row
            desc_map = [
                ("sunny", "\u6674"), ("clear", "\u6674"),
                ("partly cloudy", "\u591a\u4e91"), ("cloudy", "\u591a\u4e91"), ("overcast", "\u9634"),
                ("mist", "\u96fe"), ("fog", "\u96fe"), ("haze", "\u973e"),
                ("rain", "\u96e8"), ("light rain", "\u5c0f\u96e8"), ("heavy rain", "\u5927\u96e8"),
                ("drizzle", "\u5c0f\u96e8"), ("patchy rain", "\u5c0f\u96e8"),
                ("thunder", "\u96f7\u9635\u96e8"), ("storm", "\u66b4\u98ce\u96e8"),
                ("snow", "\u96ea"), ("light snow", "\u5c0f\u96ea"), ("heavy snow", "\u5927\u96ea"),
                ("blizzard", "\u66b4\u96ea"), ("sleet", "\u96e8\u5939\u96ea"),
                ("wind", "\u5927\u98ce"), ("windy", "\u5927\u98ce"), ("gale", "\u5927\u98ce"),
                ("squall", "\u5927\u98ce"), ("typhoon", "\u53f0\u98ce"),
            ]
            short_desc = ""
            for keyword, cn in desc_map:
                if keyword in desc_lower:
                    short_desc = cn
                    break

            primary_text = f"{icon} {r['name']} {r['temp']}\u00b0C"
            if short_desc:
                primary_text += f" {short_desc}"
            p_label.configure(text=primary_text)

            # ---- Secondary row: extreme weather alerts ----
            is_bad = False
            secondary_text = ""

            # Priority 1: heavy/extreme rain
            if any(k in desc_lower for k in ["heavy rain", "torrential", "thunder", "storm"]):
                if "thunder" in desc_lower or "\u96f7" in desc:
                    secondary_text = "\u26c8 \u96f7\u9635\u96e8"
                else:
                    secondary_text = "\U0001f327 \u5927\u96e8"
                is_bad = True
            # Priority 2: moderate rain
            elif "moderate" in desc_lower or "\u4e2d\u96e8" in desc:
                secondary_text = "\U0001f326 \u4e2d\u96e8"
                is_bad = True
            # Priority 3: light rain
            elif any(k in desc_lower for k in ["light rain", "drizzle", "patchy rain", "\u5c0f\u96e8"]):
                secondary_text = "\U0001f326 \u5c0f\u96e8"
                is_bad = True
            # Priority 4: snow
            elif any(k in desc_lower for k in ["snow", "blizzard", "sleet"]):
                if "heavy" in desc_lower or "blizzard" in desc_lower:
                    secondary_text = "\u2744 \u5927\u96ea"
                else:
                    secondary_text = "\U0001f328 \u5c0f\u96ea"
                is_bad = True
            # Priority 5: typhoon
            elif "typhoon" in desc_lower:
                secondary_text = "\U0001f300 \u53f0\u98ce"
                is_bad = True
            # Priority 6: strong wind
            elif any(k in desc_lower for k in ["wind", "gale", "squall"]):
                secondary_text = "\U0001f4a8 \u5927\u98ce"
                is_bad = True
            # Priority 7: fog
            elif any(k in desc_lower for k in ["fog", "mist", "haze"]):
                secondary_text = "\U0001f32b \u96fe\u973e"
                is_bad = True
            # Priority 8: humidity or wind fallback
            else:
                humidity = r.get("humidity", "")
                if humidity and "%" in humidity:
                    try:
                        h_val = int(humidity.replace("%", "").strip())
                        if h_val >= 85:
                            secondary_text = "\U0001f4a7 \u9ad8\u6e7f"
                        elif h_val <= 20:
                            secondary_text = "\U0001f4a7 \u5e72\u71e5"
                    except ValueError:
                        pass
                if not secondary_text:
                    wind = r.get("wind", "")
                    if wind and "km/h" in wind:
                        try:
                            ws = int(wind.replace("km/h", "").strip())
                            if ws >= 30:
                                secondary_text = "\U0001f4a8 \u5927\u98ce"
                        except ValueError:
                            pass

            if is_bad:
                has_any_bad = True

            if secondary_text:
                s_label.configure(text=secondary_text, fg=COLORS["danger"] if is_bad else COLORS["text_secondary"])
            else:
                s_label.configure(text="")

        # Hide city2 frame if only 1 city
        if len(temps) < 2:
            self._city2_frame.pack_forget()
        else:
            self._city2_frame.pack(fill=tk.X, padx=10, pady=(2, 4))

        if has_any_bad:
            self.weather_bar.configure(bg="#1a2020")
        else:
            self.weather_bar.configure(bg=COLORS["title_bar"])

    def _maybe_weather_alert(self):
        """Once-daily AI analysis. Runs in background thread."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._weather_alert_date == today:
            return
        settings = load_settings()
        if not settings.get("weather_enabled", True):
            return

        self._weather_alert_date = today
        threading.Thread(target=self._do_weather_alert, daemon=True).start()

    def _do_weather_alert(self):
        """Background thread: fetch + AI analyze, notify if needed."""
        try:
            settings = load_settings()
            result = analyze_alerts(settings)
            temp_line = result.get("temp_line", "")

            if result.get("alerts"):
                worst = result["alerts"][0]
                alert_cities = "、".join(a["city"] for a in result["alerts"])
                title = worst.get("title", "天气提醒")
                body = f"{temp_line}\n{'、'.join(worst.get('reasons', []))}"
                self.root.after(0, lambda t=title, b=body: self._fire_weather_notification(t, b))
            else:
                # 天气正常，也推送温度速报
                self.root.after(0, lambda tl=temp_line: self._fire_weather_notification("每日天气速报", tl))
        except Exception as e:
            print(f"[天气] 分析失败: {e}")

    def _fire_weather_notification(self, title: str, body: str):
        """Show weather notification."""
        try:
            from plyer import notification
            notification.notify(title=title, message=body, app_name="待办天气", timeout=8)
        except Exception:
            pass

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
        tasks = load_all_tasks()
        imminent = find_imminent_tasks(tasks, self._notified_ids)
        for t, delay_ms in imminent:
            self.root.after(delay_ms,
                           lambda tid=t["id"], content=t["content"],
                           due=datetime.fromisoformat(t["due"]):
                           self._fire_notification(tid, content, due))

    # ==================== notification ====================

    def _check_due_notifications(self):
        tasks = load_all_tasks()
        for t in find_due_for_notification(tasks, self._notified_ids):
            due_dt = datetime.fromisoformat(t["due"])
            self._fire_notification(t["id"], t["content"], due_dt)

        for tid in find_expired_notification_flags(tasks, self._notified_ids):
            self._notified_ids.discard(tid)

    def _fire_notification(self, task_id, content, due_dt):
        self._notified_ids.add(task_id)
        show_reminder_popup(self.root, task_id, content, due_dt,
                           on_snooze=self._snooze_task)
        # Note: recurring tasks are NOT auto-rescheduled here.
        # User controls rescheduling by clicking "complete" in the task list.

    def _reschedule_if_recurring(self, task_id):
        """Reschedule a recurring task to next occurrence."""
        result = find_task(task_id)
        if result:
            ws, page_idx, t = result
            if should_reset_recurring_after_notify(t):
                if reschedule_recurring(t):
                    save_workspace(ws)
                    self._notified_ids.discard(task_id)
                    self._refresh_task_list()

    def _snooze_task(self, task_id, new_due_iso):
        result = find_task(task_id)
        if result:
            ws, page_idx, t = result
            t["due"] = new_due_iso
            save_workspace(ws)
            self._notified_ids.discard(task_id)
            self._refresh_task_list()

    # ==================== UI build ====================

    def _build_ui(self):
        # title bar
        self.title_bar = tk.Frame(self.root, bg=COLORS["title_bar"], height=28)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)

        self.title_label = tk.Label(
            self.title_bar, text="📋 待办事项", fg=COLORS["text"],
            bg=COLORS["title_bar"], font=FONT_HEADER)
        self.title_label.pack(side=tk.LEFT, padx=10, pady=2)

        btn_frame = tk.Frame(self.title_bar, bg=COLORS["title_bar"])
        btn_frame.pack(side=tk.RIGHT, padx=4)

        self.settings_btn = tk.Label(
            btn_frame, text=ICONS["settings"], fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.settings_btn.pack(side=tk.LEFT)
        self.settings_btn.bind("<Button-1>", self._open_settings)
        self._make_hover(self.settings_btn, COLORS["text_secondary"], COLORS["accent_light"])

        self.collapse_btn = tk.Label(
            btn_frame, text=ICONS["collapse"], fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.collapse_btn.pack(side=tk.LEFT)
        self.collapse_btn.bind("<Button-1>", self._toggle_collapse)
        self._make_hover(self.collapse_btn, COLORS["text_secondary"], COLORS["accent_light"])

        self.close_btn = tk.Label(
            btn_frame, text=ICONS["delete"], fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, cursor="hand2", padx=5)
        self.close_btn.pack(side=tk.LEFT)
        self.close_btn.bind("<Button-1>", lambda e: self._on_close())
        self._make_hover(self.close_btn, COLORS["text_secondary"], COLORS["danger"])

        # weather bar — 4 rows: city1_primary, city1_secondary, city2_primary, city2_secondary
        self.weather_bar = tk.Frame(self.root, bg=COLORS["title_bar"], height=96)
        self.weather_bar.pack(fill=tk.X, side=tk.TOP)
        self.weather_bar.pack_propagate(False)

        # City 1 frame
        self._city1_frame = tk.Frame(self.weather_bar, bg=COLORS["title_bar"])
        self._city1_frame.pack(fill=tk.X, padx=10, pady=(4, 0))
        self._weather_p1 = tk.Label(
            self._city1_frame, text="☀ 加载中...", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, anchor="w")
        self._weather_p1.pack(fill=tk.X)
        self._weather_s1 = tk.Label(
            self._city1_frame, text="", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_SMALL, anchor="w")
        self._weather_s1.pack(fill=tk.X)

        # City 2 frame
        self._city2_frame = tk.Frame(self.weather_bar, bg=COLORS["title_bar"])
        self._city2_frame.pack(fill=tk.X, padx=10, pady=(2, 4))
        self._weather_p2 = tk.Label(
            self._city2_frame, text="", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_TITLE, anchor="w")
        self._weather_p2.pack(fill=tk.X)
        self._weather_s2 = tk.Label(
            self._city2_frame, text="", fg=COLORS["text_secondary"],
            bg=COLORS["title_bar"], font=FONT_SMALL, anchor="w")
        self._weather_s2.pack(fill=tk.X)

        # Input area with card-like border
        # ==================== page tab bar (Excel-style) ====================
        self.tab_bar = tk.Frame(self.root, bg=COLORS["bg"])
        self.tab_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0), padx=2)
        self._tab_menu_index = None

        self.tab_menu = tk.Menu(self.root, tearoff=0, bg=COLORS["surface"],
                                fg=COLORS["text"],
                                activebackground=COLORS["accent"],
                                activeforeground=COLORS["bg"])
        self.tab_menu.add_command(label="重命名页面", command=self._ctx_rename_page)
        self.tab_menu.add_command(label="删除页面", command=self._ctx_delete_page)

        input_outer = tk.Frame(self.root, bg=COLORS["card"],
                               highlightbackground=COLORS["input_border"],
                               highlightthickness=1, padx=1, pady=1)
        input_outer.pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0), padx=2)

        input_frame = tk.Frame(input_outer, bg=COLORS["card"])
        input_frame.pack(fill=tk.X, padx=4, pady=3)

        self.entry = tk.Entry(
            input_frame, bg=COLORS["input_bg"], fg=COLORS["text"],
            insertbackground=COLORS["text"], font=FONT, relief="flat", bd=4)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.entry.bind("<Return>", self._quick_add_task)
        self.entry.configure(fg=COLORS["text_secondary"])
        self.entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry.bind("<FocusOut>", self._on_entry_focus_out)
        self._placeholder = "输入新任务，回车添加"
        self.entry.insert(0, self._placeholder)

        self.mic_btn = tk.Label(
            input_frame, text=ICONS["mic"], fg=COLORS["accent"], bg=COLORS["card"],
            font=FONT_SMALL, cursor="hand2", padx=4)
        self.mic_btn.pack(side=tk.RIGHT)
        self.mic_btn.bind("<Button-1>", self._start_voice_input)

        self.add_btn = tk.Label(
            input_frame, text=ICONS["add"], fg=COLORS["accent"], bg=COLORS["card"],
            font=("Microsoft YaHei UI", 16, "bold"), cursor="hand2", padx=6)
        self.add_btn.pack(side=tk.RIGHT)
        self.add_btn.bind("<Button-1>", self._add_task)
        self._make_hover(self.add_btn, COLORS["accent"], COLORS["accent_light"])


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
            activebackground=COLORS["accent"],
            highlightthickness=0, bd=0)
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


        # context menu
        self.ctx_menu = tk.Menu(self.root, tearoff=0, bg=COLORS["surface"],
                                fg=COLORS["text"],
                                activebackground=COLORS["accent"],
                                activeforeground=COLORS["bg"])
        self.ctx_menu.add_command(label="编辑", command=self._ctx_edit)
        self.ctx_menu.add_command(label="设置提醒", command=self._ctx_set_due)
        self.ctx_menu.add_command(label="标记完成/取消", command=self._ctx_toggle_done)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="仅完成本期 (循环任务)", command=self._ctx_complete_cycle)
        self.ctx_menu.add_command(label="永久取消循环提醒", command=self._ctx_cancel_recurring)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="删除", command=self._ctx_delete)

    # ==================== page tabs ====================

    def _render_tabs(self):
        """Render page tabs in tab_bar."""
        for w in self.tab_bar.winfo_children():
            w.destroy()
        self._tab_labels = []
        pages = get_pages()
        active = get_active_page_index()
        for i, page in enumerate(pages):
            if i == active:
                fg = COLORS["bg"]
                bg = COLORS["accent"]
                font = ("Microsoft YaHei UI", 9, "bold")
            else:
                fg = COLORS["text"]
                bg = COLORS["card"]
                font = FONT_SMALL
            tab = tk.Label(self.tab_bar, text=page["name"], fg=fg, bg=bg,
                           font=font, padx=8, pady=2, cursor="hand2")
            tab.pack(side=tk.LEFT, padx=(0, 3))
            tab.bind("<Button-1>", lambda e, idx=i: self._switch_page(idx))
            tab.bind("<Double-Button-1>", lambda e, idx=i: self._rename_page(idx))
            tab.bind("<Button-3>", lambda e, idx=i: self._show_tab_menu(e, idx))
            self._tab_labels.append(tab)
        plus = tk.Label(self.tab_bar, text="＋", fg=COLORS["accent"],
                        bg=COLORS["bg"], font=FONT_TITLE, cursor="hand2", padx=4)
        plus.pack(side=tk.LEFT)
        plus.bind("<Button-1>", lambda e: self._add_page())
        # Re-apply alert colors (labels were just rebuilt)
        self._last_tab_alert_state = None
        self._update_tab_alert_colors()

    def _update_tab_alert_colors(self):
        """Red-highlight inactive page tabs that have overdue reminders."""
        if not getattr(self, "_tab_labels", None):
            return
        active = get_active_page_index()
        alerts = set(get_alert_page_indices())
        if getattr(self, "_last_tab_alert_state", None) == (active, alerts):
            return
        self._last_tab_alert_state = (active, alerts)
        for i, tab in enumerate(self._tab_labels):
            if i == active:
                continue  # active tab keeps accent styling
            if i in alerts:
                tab.configure(fg=COLORS["danger"])
            else:
                tab.configure(fg=COLORS["text"])

    def _switch_page(self, index):
        if set_active_page(index):
            self._refresh_task_list()

    def _add_page(self):
        add_page()
        self._refresh_task_list()

    def _rename_page(self, index):
        try:
            import tkinter.simpledialog as sd
        except Exception:
            sd = None
        pages = get_pages()
        if not (0 <= index < len(pages)):
            return
        old = pages[index]["name"]
        if sd is not None:
            new = sd.askstring("重命名页面", "输入新名称:",
                               initialvalue=old, parent=self.root)
        else:
            new = None
        if new and new.strip():
            rename_page(index, new.strip())
            self._refresh_task_list()

    def _show_tab_menu(self, event, index):
        self._tab_menu_index = index
        try:
            self.tab_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tab_menu.grab_release()

    def _ctx_delete_page(self):
        if self._tab_menu_index is None:
            return
        delete_page(self._tab_menu_index)
        self._tab_menu_index = None
        self._refresh_task_list()

    def _ctx_rename_page(self):
        if self._tab_menu_index is None:
            return
        idx = self._tab_menu_index
        self._tab_menu_index = None
        self._rename_page(idx)

    # ---- helpers ----

    def _make_hover(self, widget, color_normal, color_hover):
        """Bind enter/leave to change fg color on hover."""
        widget.bind("<Enter>", lambda e, w=widget, c=color_hover: w.configure(fg=c))
        widget.bind("<Leave>", lambda e, w=widget, c=color_normal: w.configure(fg=c))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 40)), "units")

    def _bind_scroll_recursive(self, widget):
        """Recursively bind <MouseWheel> to widget and all its descendants."""
        try:
            widget.bind("<MouseWheel>", self._on_mousewheel)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

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
            self.collapse_btn.configure(text=ICONS["collapse"])
            self.collapsed = False
        else:
            self.normal_height = self.root.winfo_height()
            self.content.pack_forget()
            self.root.geometry(
                "%dx%d" % (self.root.winfo_width(), self.collapsed_height))
            self.collapse_btn.configure(text=ICONS["expand"])
            self.collapsed = True

    def _open_settings(self, event=None):
        self.root._weather_refresh_cb = self._update_weather_display
        show_settings_dialog(self.root)

    # ---- task operations ----

    def _quick_add_task(self, event=None):
        text = self.entry.get().strip()
        if not text or text == self._placeholder:
            return
        tasks = load_tasks()
        new_id = get_next_id(tasks)

        parsed_content, parsed_due, rec_spec = parse_task_input(text)
        new_task = {"id": new_id, "content": parsed_content, "done": False}
        if parsed_due:
            new_task["due"] = parsed_due
        if rec_spec:
            new_task["recurring"] = rec_spec
        tasks.append(new_task)

        save_tasks(tasks)
        self.entry.delete(0, tk.END)
        self.entry.configure(fg=COLORS["text"])
        self._suppress_if_past(new_id, parsed_due)
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
            on_save=lambda c, d, r="": self._do_add(c, d, r))

    def _do_add(self, content_text, due_iso, recurring=""):
        tasks = load_tasks()
        new_id = get_next_id(tasks)
        new_task = {"id": new_id, "content": content_text, "done": False}
        if due_iso:
            new_task["due"] = due_iso
        if recurring:
            new_task["recurring"] = recurring
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

    def _on_task_single_click(self, event, task_id):
        """Single-click: delay toggle so double-click can cancel it."""
        if self._click_job is not None:
            try:
                self.root.after_cancel(self._click_job)
            except Exception:
                pass
        self._click_job = self.root.after(
            200, lambda: self._do_click_toggle(task_id))

    def _on_task_double_click(self, event, task_id):
        """Double-click: cancel pending toggle, open editor instead."""
        if self._click_job is not None:
            try:
                self.root.after_cancel(self._click_job)
            except Exception:
                pass
            self._click_job = None
        self._edit_task(task_id)

    def _do_click_toggle(self, task_id):
        self._click_job = None
        self._toggle_task(task_id)

    def _toggle_task(self, task_id):
        """Toggle task completion. For recurring tasks: reschedule instead."""
        from datetime import datetime
        from core.task_manager import reschedule_recurring

        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, t = result

        rec = t.get("recurring", "")
        if rec and should_reset_recurring_after_notify(t):
            due_str = t.get("due")
            if due_str:
                try:
                    due_dt = datetime.fromisoformat(due_str)
                    if due_dt <= datetime.now():
                        # Only advance cycle if current due has arrived
                        if reschedule_recurring(t):
                            self._notified_ids.discard(task_id)
                except Exception:
                    pass
            # Recurring tasks NEVER toggle done
        else:
            # Non-recurring task
            # Overdue normal tasks cannot be marked done
            due_str = t.get("due")
            if due_str:
                try:
                    due_dt = datetime.fromisoformat(due_str)
                    if due_dt < datetime.now():
                        # Already overdue — do not toggle done
                        save_workspace(ws)
                        self._refresh_task_list()
                        return
                except Exception:
                    pass
            # Not overdue (or no due) → normal toggle
            t["done"] = not t["done"]
        save_workspace(ws)
        self._refresh_task_list()

    def _delete_task(self, task_id):
        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, t = result
        ws["pages"][page_idx]["tasks"] = [
            x for x in ws["pages"][page_idx]["tasks"] if x["id"] != task_id]
        save_workspace(ws)
        self._notified_ids.discard(task_id)
        self._refresh_task_list()

    def _edit_task(self, task_id):
        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, target = result
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
            recurring_val=target.get("recurring", ""),
            on_save=lambda c, d, r="": self._do_edit(task_id, c, d, r))

    def _do_edit(self, task_id, content_text, due_iso, recurring=""):
        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, t = result
        t["content"] = content_text
        if due_iso:
            t["due"] = due_iso
        else:
            t.pop("due", None)
        if recurring:
            t["recurring"] = recurring
        else:
            t.pop("recurring", None)
        save_workspace(ws)
        self._notified_ids.discard(task_id)
        self._suppress_if_past(task_id, due_iso)
        self._refresh_task_list()

    def _set_due(self, task_id):
        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, target = result
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
            recurring_val=target.get("recurring", ""),
            on_save=lambda c, d, r="": self._do_set_due(task_id, d, r),
            on_clear=lambda: self._do_clear_due(task_id))

    def _do_set_due(self, task_id, due_iso, recurring=""):
        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, t = result
        t["due"] = due_iso
        if recurring:
            t["recurring"] = recurring
        else:
            t.pop("recurring", None)
        save_workspace(ws)
        self._notified_ids.discard(task_id)
        self._suppress_if_past(task_id, due_iso)
        self._refresh_task_list()

    def _do_clear_due(self, task_id):
        result = find_task(task_id)
        if not result:
            return
        ws, page_idx, t = result
        t.pop("due", None)
        save_workspace(ws)
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

    def _ctx_complete_cycle(self):
        """仅完成本期 — delegates to _toggle_task."""
        if self._ctx_task_id is not None:
            self._toggle_task(self._ctx_task_id)

    def _ctx_cancel_recurring(self):
        """永久取消循环提醒 — clear recurring field."""
        if self._ctx_task_id is None:
            return
        result = find_task(self._ctx_task_id)
        if result:
            ws, page_idx, t = result
            t.pop("recurring", None)
            save_workspace(ws)
            self._refresh_task_list()

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
            self.mic_btn.configure(fg=COLORS["accent"], text=ICONS["mic"])
            self._recording = False
            return

        voice_log("=== 语音识别开始 (frozen=%s) ===" % FROZEN)
        self._recording = True
        self._stop_event = threading.Event()
        self.mic_btn.configure(fg=COLORS["danger"], text=ICONS["mic_recording"])
        self._voice_errors = []
        threading.Thread(target=self._do_voice_recognition, daemon=True).start()
        self.root.after(15000, self._voice_safety_timeout)

    def _voice_safety_timeout(self):
        if getattr(self, '_recording', False):
            self._stop_event.set()
            self.mic_btn.configure(fg=COLORS["accent"], text=ICONS["mic"])
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

                if is_model_missing():
                    # Model missing: skip Vosk (will fail) and Google (hangs in China).
                    # Go straight to SAPI, then offer download if SAPI also fails.
                    voice_log("Vosk 模型缺失，跳过 Vosk/Google，直接尝试 SAPI...")
                else:
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
        parsed_content, parsed_due, rec_spec = parse_task_input(text)
        voice_log("解析结果: content='%s', due=%s, recurring=%s" % (parsed_content, parsed_due, rec_spec))
        print("[语音] 解析结果: content='%s', due=%s, recurring=%s" % (parsed_content, parsed_due, rec_spec))
        self.root.after(0, lambda: self._on_voice_result(parsed_content, parsed_due, rec_spec))

    def _on_voice_result(self, content, due_iso, recurring=""):
        self.mic_btn.configure(fg=COLORS["accent"], text="mic")

        if due_iso:
            tasks = load_tasks()
            new_id = get_next_id(tasks)
            new_task = {"id": new_id, "content": content, "done": False, "due": due_iso}
            if recurring:
                new_task["recurring"] = recurring
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
        """Offer to download the Vosk speech model when it's missing.

        Shows a choice dialog first.  On "download now", opens a progress window
        with speed/ETA.  If the user closes the progress window, the download
        continues in background and a notification pops up when done.
        """
        # ---- Step 1: choice dialog ----
        choice_popup = tk.Toplevel(self.root)
        choice_popup.title("语音模型缺失")
        choice_popup.configure(bg=COLORS["bg"])
        choice_popup.transient(self.root)
        choice_popup.grab_set()
        choice_popup.resizable(False, False)
        choice_popup.geometry("400x200")

        choice_popup.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        choice_popup.geometry("+%d+%d" % (px, py))

        msg = tk.Label(
            choice_popup,
            text="未找到离线语音模型\n\n需要下载约 42MB 的语音识别模型\n才能使用语音功能。\n下载过程可能需要几分钟。",
            fg=COLORS["text"], bg=COLORS["bg"], font=FONT, justify=tk.CENTER)
        msg.pack(pady=(25, 20))

        btn_frame = tk.Frame(choice_popup, bg=COLORS["bg"])
        btn_frame.pack()

        user_choice = []

        def choose_download():
            user_choice.append("download")
            choice_popup.destroy()

        def choose_later():
            user_choice.append("later")
            choice_popup.destroy()

        later_btn = tk.Label(
            btn_frame, text="以后再说", fg=COLORS["text_secondary"],
            bg=COLORS["surface"], font=FONT, cursor="hand2",
            padx=24, pady=8)
        later_btn.pack(side=tk.LEFT, padx=(0, 16))
        later_btn.bind("<Button-1>", lambda e: choose_later())
        later_btn.bind("<Enter>", lambda e, lbl=later_btn: lbl.configure(fg=COLORS["text"]))
        later_btn.bind("<Leave>", lambda e, lbl=later_btn: lbl.configure(fg=COLORS["text_secondary"]))

        dl_btn = tk.Label(
            btn_frame, text="立即下载", fg=COLORS["bg"],
            bg=COLORS["accent"], font=FONT, cursor="hand2",
            padx=24, pady=8)
        dl_btn.pack(side=tk.LEFT)
        dl_btn.bind("<Button-1>", lambda e: choose_download())

        choice_popup.wait_window()

        if not user_choice or user_choice[0] == "later":
            return

        # ---- Step 2: progress window ----
        popup = tk.Toplevel(self.root)
        popup.title("下载语音模型")
        popup.configure(bg=COLORS["bg"])
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)

        # Determine size based on whether we show speed/eta row
        popup.geometry("400x170")
        popup.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 170) // 2
        popup.geometry("+%d+%d" % (px, py))

        status_label = tk.Label(
            popup, text="正在准备下载...", fg=COLORS["text"], bg=COLORS["bg"],
            font=FONT)
        status_label.pack(pady=(20, 8))

        import tkinter.ttk as ttk
        progress = ttk.Progressbar(
            popup, mode="determinate", length=360, maximum=100)
        progress.pack(pady=(0, 4))

        detail_label = tk.Label(
            popup, text="", fg=COLORS["text_secondary"], bg=COLORS["bg"],
            font=FONT_SMALL)
        detail_label.pack()

        # State shared with download thread
        state = {
            "popup_closed": False,
            "cancelled": False,
            "done": False,
            "result": None,  # True = success, Exception = failure
        }

        def update_progress(pct, status, extra=None):
            try:
                if state["popup_closed"]:
                    return
                progress["value"] = pct
                status_label.configure(text=status)
                if extra:
                    parts = []
                    speed = extra.get("speed", "")
                    eta = extra.get("eta", "")
                    if speed:
                        parts.append(speed)
                    if eta:
                        parts.append(eta)
                    detail_label.configure(text="  ".join(parts))
                popup.update_idletasks()
            except Exception:
                pass

        def check_cancel():
            return state["cancelled"]

        def on_popup_close():
            state["popup_closed"] = True
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_popup_close)

        def do_download():
            try:
                download_vosk_model(
                    progress_callback=update_progress,
                    cancel_check=check_cancel)
                state["result"] = True
            except Exception as e:
                state["result"] = e
            state["done"] = True

            if state["popup_closed"]:
                # Background download finished — show notification
                if state["result"] is True:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "语音模型就绪",
                        "语音识别模型已在后台下载完成！\n\n"
                        "现在可以使用语音功能了。",
                        parent=self.root))
                else:
                    err = str(state["result"])
                    if "用户取消" not in err:
                        self.root.after(0, lambda e=err: messagebox.showerror(
                            "下载失败",
                            "语音模型后台下载失败：\n%s\n\n"
                            "下次使用语音时会再次提示下载。" % e,
                            parent=self.root))
            else:
                # Popup still open — close it and show result
                def show_result():
                    try:
                        popup.destroy()
                    except Exception:
                        pass
                    if state["result"] is True:
                        messagebox.showinfo(
                            "下载完成",
                            "语音模型安装成功！\n\n请重新点击麦克风按钮开始语音输入。",
                            parent=self.root)
                    else:
                        err = str(state["result"])
                        if "用户取消" not in err:
                            messagebox.showerror(
                                "下载失败",
                                "模型下载失败：\n%s\n\n请检查网络连接后重试。\n"
                                "也可以手动下载 vosk-model-small-cn-0.22\n"
                                "解压到: %s" % (
                                    err, os.path.expanduser("~/.vosk-model-cn")),
                                parent=self.root)
                self.root.after(0, show_result)

        t = threading.Thread(target=do_download)
        t.daemon = True
        t.start()
        popup.wait_window()

        if not state["done"]:
            # User closed popup while download is still running
            state["popup_closed"] = True

    # ---- render ----

    def _refresh_task_list(self):
        self._due_labels.clear()

        for w in self.task_frame.winfo_children():
            w.destroy()

        tasks = load_tasks()
        tasks.sort(key=lambda t: (t.get("done", False), t.get("id", 0)))

        self.task_frame.configure(bg=COLORS["bg"])

        if not tasks:
            empty_frame = tk.Frame(self.task_frame, bg=COLORS["bg"])
            empty_frame.pack(pady=40)
            tk.Label(
                empty_frame, text="📝", fg=COLORS["text_secondary"],
                bg=COLORS["bg"], font=("Microsoft YaHei UI", 24)).pack()
            tk.Label(
                empty_frame,
                text="暂无待办事项",
                fg=COLORS["text_secondary"], bg=COLORS["bg"],
                font=("Microsoft YaHei UI", 11)).pack(pady=(8, 4))
            tk.Label(
                empty_frame,
                text="输入任务后回车添加  ·  右键编辑/设提醒",
                fg=COLORS["scrollbar"], bg=COLORS["bg"],
                font=FONT_SMALL).pack()
            return

        for idx, t in enumerate(tasks):
            # Card container with subtle border
            card = tk.Frame(self.task_frame, bg=COLORS["card"],
                           highlightbackground=COLORS["card_border"],
                           highlightthickness=1, padx=2, pady=2)
            card.pack(fill=tk.X, pady=(0 if idx == 0 else 2, 2), padx=2)

            row = tk.Frame(card, bg=COLORS["card"])
            row.pack(fill=tk.X, padx=6, pady=4)

            # Checkbox — circle style
            cb_text = ICONS["checkbox_done"] if t["done"] else ICONS["checkbox_undone"]
            cb_color = COLORS["done"] if t["done"] else COLORS["text_secondary"]
            cb_font = ("Microsoft YaHei UI", 12)
            cb = tk.Label(row, text=cb_text, fg=cb_color, bg=COLORS["card"],
                          font=cb_font, cursor="hand2", padx=2)
            cb.pack(side=tk.LEFT)
            cb.bind("<Button-1>", lambda e, tid=t["id"]: self._toggle_task(tid))

            # Content area
            text_fg = COLORS["text_secondary"] if t["done"] else COLORS["text"]
            text_font = ("Microsoft YaHei UI", 10, "overstrike") if t["done"] else ("Microsoft YaHei UI", 10)

            # Red highlight: only recurring tasks (每周/每两周/每月/每年) at the
            # moment they become due — within the 60s notification window.
            # Long-overdue tasks stay normal; the [已过期] badge handles them.
            is_due_recurring = False
            rec = t.get("recurring", "")
            if rec and not t.get("done") and should_reset_recurring_after_notify(t):
                due_str = t.get("due")
                if due_str:
                    try:
                        due_dt = datetime.fromisoformat(due_str)
                        delta = (datetime.now() - due_dt).total_seconds()
                        if 0 <= delta < 60:
                            is_due_recurring = True
                    except Exception:
                        pass

            text_frame = tk.Frame(row, bg=COLORS["card"])
            text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 4))
            # Click anywhere in content area = toggle (with double-click editor)
            text_frame.bind("<Button-1>",
                            lambda e, tid=t["id"]: self._on_task_single_click(e, tid))
            text_frame.bind("<Double-Button-1>",
                            lambda e, tid=t["id"]: self._on_task_double_click(e, tid))

            actual_fg = COLORS["danger"] if is_due_recurring else text_fg
            content_label = tk.Label(
                text_frame, text=t["content"], fg=actual_fg, bg=COLORS["card"],
                font=text_font, anchor="w", justify=tk.LEFT)
            content_label.pack(side=tk.LEFT)

            # Single-click on content = toggle; double-click = edit
            content_label.bind("<Button-1>",
                               lambda e, tid=t["id"]: self._on_task_single_click(e, tid))
            content_label.bind("<Double-Button-1>",
                               lambda e, tid=t["id"]: self._on_task_double_click(e, tid))
            cb.bind("<Double-Button-1>",
                    lambda e, tid=t["id"]: self._on_task_double_click(e, tid))

            # Due time badge
            due_str = format_due(t.get("due"))
            if due_str or t.get("due"):
                if not due_str:
                    due_str = ""
                is_overdue = "已过期" in due_str
                badge_bg = "#3d2030" if is_overdue else "#2a3020"
                badge_fg = COLORS["overdue"] if is_overdue else COLORS["due"]
                badge_text = f" {ICONS['due']} {due_str} " if due_str else ""
                due_label = tk.Label(
                    text_frame, text=badge_text, fg=badge_fg, bg=COLORS["card"],
                    font=FONT_SMALL, anchor="w")
                due_label.pack(side=tk.LEFT, padx=(8, 0))
                due_label.bind("<Double-Button-1>",
                               lambda e, tid=t["id"]: self._edit_task(tid))
                if not t.get("done"):
                    self._due_labels[t["id"]] = due_label

            # Recurring indicator
            rec_display = format_recurring_display(t.get("recurring"))
            if rec_display:
                recurring_label = tk.Label(
                    text_frame, text=rec_display, fg=COLORS["accent"],
                    bg=COLORS["card"], font=FONT_SMALL, anchor="w")
                recurring_label.pack(side=tk.LEFT, padx=(2, 0))

            # Delete button
            del_btn = tk.Label(row, text=ICONS["delete"], fg=COLORS["text_secondary"],
                               bg=COLORS["card"], font=FONT_SMALL,
                               cursor="hand2", padx=6)
            del_btn.pack(side=tk.RIGHT)
            del_btn.bind("<Button-1>",
                         lambda e, tid=t["id"]: self._delete_task(tid))
            self._make_hover(del_btn, COLORS["text_secondary"], COLORS["danger"])

            for child in (row, card, cb, content_label, text_frame):
                child.bind("<Button-3>",
                           lambda e, tid=t["id"]: self._show_context_menu(e, tid))

        # Bind mousewheel to all card widgets recursively
        self._bind_scroll_recursive(self.task_frame)

        # Refresh page tabs
        self._render_tabs()

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

    def _toggle_window(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        else:
            self.root.withdraw()

    def _quit_app(self):
        self._tray.hide()
        release_instance()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
