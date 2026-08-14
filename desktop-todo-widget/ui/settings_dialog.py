"""Settings dialog: autostart toggle, update check, version info."""
import threading
import tkinter as tk
from tkinter import messagebox

from config.settings_manager import load_settings, save_settings
from utils.common_utils import COLORS, FONT, FONT_SMALL, FONT_TITLE
from utils.registry_utils import set_autostart, remove_autostart, is_autostart_enabled
from utils.update_checker import VERSION, check_for_updates, download_update, \
    apply_update_and_restart, open_releases_page


def _build_weather_section(dlg_frame, settings):
    """Add weather config rows to the settings frame.
    Uses dynamic city ordering: home_city fixed, second city auto-detected.
    """
    from core.weather_checker import fetch_temps

    home_default = settings.get("weather_home_city", "合肥")
    home_var = tk.StringVar(value=home_default)

    row1 = tk.Frame(dlg_frame, bg=COLORS["surface"])
    row1.pack(fill=tk.X, padx=16, pady=(4, 2))
    tk.Label(row1, text="家城市", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT).pack(side=tk.LEFT)
    tk.Entry(row1, textvariable=home_var, bg=COLORS["input_bg"],
             fg=COLORS["text"], font=FONT, relief="flat", bd=3, width=18).pack(side=tk.RIGHT)

    # Second city — manual input wins over auto detection
    manual_default = settings.get("weather_manual_city", "")
    manual_var = tk.StringVar(value=manual_default)
    row2 = tk.Frame(dlg_frame, bg=COLORS["surface"])
    row2.pack(fill=tk.X, padx=16, pady=(2, 2))
    tk.Label(row2, text="第二城市", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT).pack(side=tk.LEFT)
    tk.Entry(row2, textvariable=manual_var, bg=COLORS["input_bg"],
             fg=COLORS["text"], font=FONT, relief="flat", bd=3, width=18).pack(side=tk.RIGHT)
    tk.Label(row2, text="(留空则自动检测)", fg=COLORS["text_secondary"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(side=tk.RIGHT, padx=(4, 0))

    # API Key field
    api_key_var = tk.StringVar(value=settings.get("weather_api_key", ""))
    row_api = tk.Frame(dlg_frame, bg=COLORS["surface"])
    row_api.pack(fill=tk.X, padx=16, pady=(2, 2))
    tk.Label(row_api, text="API Key", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT).pack(side=tk.LEFT)
    tk.Entry(row_api, textvariable=api_key_var, bg=COLORS["input_bg"],
             fg=COLORS["text"], font=FONT, relief="flat", bd=3, width=18, show="*").pack(side=tk.RIGHT)

    has_bad = tk.BooleanVar(value=False)

    # Preview + refresh
    row3 = tk.Frame(dlg_frame, bg=COLORS["surface"])
    row3.pack(fill=tk.X, padx=16, pady=(4, 2))

    preview_lbl = tk.Label(row3, text="点击刷新预览", fg=COLORS["text_secondary"],
                           bg=COLORS["surface"], font=FONT_SMALL)
    preview_lbl.pack(side=tk.LEFT)

    refresh_btn = tk.Label(row3, text="刷新", fg=COLORS["accent"],
                           bg=COLORS["surface"], font=FONT_SMALL, cursor="hand2", padx=6)
    refresh_btn.pack(side=tk.RIGHT)

    def _refresh_preview():
        preview_lbl.configure(text="刷新中...")
        dlg = dlg_frame.winfo_toplevel()

        def _fetch():
            try:
                c1 = home_var.get().strip()
                cities = [c1] if c1 else []
                if not cities:
                    dlg.after(0, lambda: preview_lbl.configure(text="请填写家城市名"))
                    return
                manual_city = manual_var.get().strip()
                temps = fetch_temps({"weather_home_city": c1,
                                    "weather_manual_city": manual_city,
                                    "weather_enabled": True})
                parts = []
                _bad = False
                for r in temps:
                    if r["temp"] == "?":
                        _bad = True
                        parts.append(f"{r['name']} ⚠ 无数据")
                    else:
                        icon = {"sunny": "☀", "clear": "☀", "partly cloudy": "⛅",
                                "cloudy": "☁", "overcast": "☁", "mist": "🌫",
                                "fog": "🌫", "rain": "🌧", "light rain": "🌦",
                                "heavy rain": "🌧", "thunder": "⛈", "snow": "❄",
                                "light snow": "🌨", "patchy rain": "🌦"}.get(r.get("desc", "").lower(), "🌤")
                        parts.append(f"{icon} {r['name']} {r['temp']}°C")
                has_bad.set(_bad)
                dlg.after(0, lambda: preview_lbl.configure(text="  |  ".join(parts) if parts else "无数据"))
            except Exception:
                dlg.after(0, lambda: preview_lbl.configure(text="获取失败"))

        threading.Thread(target=_fetch, daemon=True).start()

    refresh_btn.bind("<Button-1>", lambda e: _refresh_preview())

    # Swap order checkbox
    swap_var = tk.BooleanVar(value=settings.get("weather_swap_order", False))
    swap_frame = tk.Frame(dlg_frame, bg=COLORS["surface"])
    swap_frame.pack(fill=tk.X, padx=16, pady=(2, 2))
    tk.Checkbutton(
        swap_frame, text="交换城市顺序", variable=swap_var,
        bg=COLORS["surface"], activebackground=COLORS["surface"],
        selectcolor=COLORS["input_bg"], fg=COLORS["text"],
        font=FONT_SMALL).pack(side=tk.LEFT)

    def save_into(target):
        home = home_var.get().strip()
        target["weather_home_city"] = home if home else "合肥"
        target["weather_enabled"] = True
        # Manual city override
        manual = manual_var.get().strip()
        target["weather_manual_city"] = manual
        target.pop("weather_cities", None)
        target.pop("weather_names", None)
        target["weather_swap_order"] = swap_var.get()
        target.pop("weather_city", None)
        target.pop("weather_extras", None)
        # Save API Key
        key = api_key_var.get().strip()
        if key:
            target["weather_api_key"] = key
        return target

    return save_into



def _refresh_weather(parent):
    """Try to refresh weather display on the parent window."""
    try:
        cb = getattr(parent, '_weather_refresh_cb', None)
        if cb:
            cb()
    except Exception:
        pass


def show_settings_dialog(parent):
    """Show settings dialog. Applies changes immediately on save."""
    settings = load_settings()

    dlg = tk.Toplevel(parent)
    dlg.title("设置")
    dlg.configure(bg=COLORS["surface"])
    dlg.resizable(False, False)
    dlg.transient(parent)

    dlg_w, dlg_h = 380, 480
    dlg.update_idletasks()
    root_rx = parent.winfo_rootx()
    root_ry = parent.winfo_rooty()
    root_w = parent.winfo_width()
    x = root_rx + root_w - dlg_w
    y = root_ry + 40
    dlg.geometry("%dx%d+%d+%d" % (dlg_w, dlg_h, x, y))

    try:
        dlg.wm_attributes("-toolwindow", True)
    except Exception:
        pass

    # version info
    ver_frame = tk.Frame(dlg, bg=COLORS["surface"])
    ver_frame.pack(fill=tk.X, padx=16, pady=(14, 6))

    tk.Label(ver_frame, text="版本: v%s" % VERSION,
             fg=COLORS["text_secondary"], bg=COLORS["surface"],
             font=FONT_SMALL).pack(side=tk.LEFT)

    check_btn = tk.Label(ver_frame, text="检查更新", fg=COLORS["accent"],
                         bg=COLORS["surface"], font=FONT_SMALL,
                         cursor="hand2", padx=6)
    check_btn.pack(side=tk.RIGHT)
    check_btn.bind("<Button-1>", lambda e: _do_check_update(dlg))

    # autostart
    auto_frame = tk.Frame(dlg, bg=COLORS["surface"])
    auto_frame.pack(fill=tk.X, padx=16, pady=(10, 6))

    tk.Label(auto_frame, text="开机自启动", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT).pack(side=tk.LEFT)

    auto_var = tk.BooleanVar(value=settings.get("autostart", False))
    cb = tk.Checkbutton(auto_frame, variable=auto_var,
                        bg=COLORS["surface"],
                        activebackground=COLORS["surface"],
                        selectcolor=COLORS["input_bg"],
                        fg=COLORS["text"])
    cb.pack(side=tk.RIGHT)

    # close action
    close_frame = tk.Frame(dlg, bg=COLORS["surface"])
    close_frame.pack(fill=tk.X, padx=16, pady=(6, 6))

    tk.Label(close_frame, text="点击X时", fg=COLORS["text"],
             bg=COLORS["surface"], font=FONT).pack(side=tk.LEFT)

    close_var = tk.StringVar(value=settings.get("close_action", ""))
    close_options = tk.Frame(close_frame, bg=COLORS["surface"])
    close_options.pack(side=tk.RIGHT)

    def select_close_action(val):
        close_var.set(val)

    ask_label = tk.Label(close_options, text="询问", fg=COLORS["text_secondary"],
                         bg=COLORS["surface"], font=FONT_SMALL, cursor="hand2", padx=4)
    ask_label.pack(side=tk.LEFT)
    ask_label.bind("<Button-1>", lambda e: select_close_action(""))

    min_label = tk.Label(close_options, text="最小化", fg=COLORS["text_secondary"],
                         bg=COLORS["surface"], font=FONT_SMALL, cursor="hand2", padx=4)
    min_label.pack(side=tk.LEFT)
    min_label.bind("<Button-1>", lambda e: select_close_action("minimize"))

    quit_label = tk.Label(close_options, text="关闭", fg=COLORS["text_secondary"],
                          bg=COLORS["surface"], font=FONT_SMALL, cursor="hand2", padx=4)
    quit_label.pack(side=tk.LEFT)
    quit_label.bind("<Button-1>", lambda e: select_close_action("quit"))

    def _update_close_style():
        for lbl, val in [(ask_label, ""), (min_label, "minimize"), (quit_label, "quit")]:
            if close_var.get() == val:
                lbl.configure(fg=COLORS["accent"], font=("Microsoft YaHei UI", 8, "bold"))
            else:
                lbl.configure(fg=COLORS["text_secondary"], font=FONT_SMALL)
    _update_close_style()

    def on_close_click(e, val):
        select_close_action(val)
        _update_close_style()

    for lbl, val in [(ask_label, ""), (min_label, "minimize"), (quit_label, "quit")]:
        lbl.unbind("<Button-1>")
        lbl.bind("<Button-1>", lambda e, v=val: on_close_click(e, v))

    # ── weather section ──
    sep = tk.Frame(dlg, bg=COLORS["surface"], height=1,
                   highlightbackground=COLORS["card_border"], highlightthickness=1)
    sep.pack(fill=tk.X, padx=16, pady=(8, 4))

    weather_frame = tk.Frame(dlg, bg=COLORS["surface"])
    weather_frame.pack(fill=tk.X, padx=0, pady=0)
    tk.Label(weather_frame, text="☀ 天气配置", fg=COLORS["accent"],
             bg=COLORS["surface"], font=FONT_SMALL).pack(anchor=tk.W, padx=16)

    weather_save = _build_weather_section(weather_frame, settings)

    # bottom buttons
    btn_frame = tk.Frame(dlg, bg=COLORS["surface"])
    btn_frame.pack(fill=tk.X, padx=16, pady=(10, 16))

    def do_cancel():
        dlg.destroy()

    cancel_btn = tk.Label(btn_frame, text="取消", fg=COLORS["text_secondary"],
                          bg=COLORS["surface"], font=FONT,
                          cursor="hand2", padx=10)
    cancel_btn.pack(side=tk.RIGHT)
    cancel_btn.bind("<Button-1>", lambda e: do_cancel())

    def do_save():
        try:
            settings["autostart"] = auto_var.get()
            settings["close_action"] = close_var.get()
            weather_save(settings)  # 直接修改 settings 字典，无需重新赋值
            save_settings(settings)
            if settings["autostart"]:
                set_autostart()
            else:
                remove_autostart()
        except Exception as e:
            messagebox.showerror("保存失败", f"设置保存出错:\n{e}", parent=dlg)
        finally:
            dlg.destroy()
            # 通知主窗口刷新天气显示
            try:
                parent.after(500, lambda: _refresh_weather(parent))
            except Exception:
                pass

    save_btn = tk.Label(btn_frame, text="保存", fg=COLORS["accent"],
                        bg=COLORS["surface"], font=FONT_TITLE,
                        cursor="hand2", padx=10)
    save_btn.pack(side=tk.RIGHT, padx=(0, 8))
    save_btn.bind("<Button-1>", lambda e: do_save())

    dlg.bind("<Escape>", lambda e: do_cancel())


def _do_check_update(parent):
    """Check for updates and show result dialog."""
    has_update, latest, download_url, error = check_for_updates()

    if error:
        messagebox.showwarning(
            "检查更新失败",
            "无法连接到 GitHub\n\n%s\n\n请检查网络连接后重试。" % error,
            parent=parent)
        return

    if not has_update:
        messagebox.showinfo(
            "检查更新",
            "当前版本 v%s 已经是最新版本。" % VERSION,
            parent=parent)
        return

    _show_update_dialog(parent, latest, download_url)


def _show_update_dialog(parent, latest_version, download_url):
    """Show dialog prompting user to update."""
    dlg = tk.Toplevel(parent)
    dlg.title("发现新版本")
    dlg.configure(bg=COLORS["surface"])
    dlg.resizable(False, False)
    dlg.transient(parent)

    dlg_w, dlg_h = 340, 160
    dlg.update_idletasks()
    rx = parent.winfo_rootx()
    ry = parent.winfo_rooty()
    rw = parent.winfo_width()
    x = rx + (rw - dlg_w) // 2
    y = ry + 80
    dlg.geometry("%dx%d+%d+%d" % (dlg_w, dlg_h, x, y))

    try:
        dlg.wm_attributes("-toolwindow", True)
    except Exception:
        pass

    tk.Label(dlg, text="发现新版本 v%s" % latest_version,
             fg=COLORS["accent"], bg=COLORS["surface"],
             font=FONT_TITLE).pack(pady=(16, 4))

    tk.Label(dlg, text="当前版本: v%s" % VERSION,
             fg=COLORS["text_secondary"], bg=COLORS["surface"],
             font=FONT_SMALL).pack()

    progress_var = tk.StringVar(value="")
    progress_label = tk.Label(dlg, textvariable=progress_var,
                              fg=COLORS["accent"], bg=COLORS["surface"],
                              font=FONT_SMALL)
    progress_label.pack(pady=(4, 0))

    btn_frame = tk.Frame(dlg, bg=COLORS["surface"])
    btn_frame.pack(fill=tk.X, padx=16, pady=(12, 16))

    def do_cancel():
        dlg.destroy()

    def do_open_browser():
        open_releases_page()
        dlg.destroy()

    def do_auto_download():
        if not download_url:
            messagebox.showinfo("提示", "未找到下载链接，请前往 GitHub 手动下载。", parent=dlg)
            return

        cancel_btn.configure(text="后台下载中...", fg=COLORS["text_secondary"])
        dl_btn.configure(text="", fg=COLORS["surface"])
        dl_btn.unbind("<Button-1>")

        def on_progress(downloaded, total):
            pct = downloaded * 100 // total if total > 0 else 0
            progress_var.set("下载中... %d%% (%d/%d MB)" % (
                pct, downloaded // 1048576, total // 1048576))

        def on_done(success, path_or_error):
            dlg.destroy()
            if success:
                from tkinter import messagebox as mb
                if apply_update_and_restart(path_or_error):
                    mb.showinfo("更新就绪",
                                "新版本已下载，程序将自动重启完成更新。",
                                parent=parent)
                    parent.quit()
                else:
                    mb.showinfo("更新就绪",
                                "新版本已下载到:\n%s\n\n请在开发模式下手动替换。" % path_or_error,
                                parent=parent)
            else:
                from tkinter import messagebox as mb
                mb.showerror("下载失败",
                             "下载更新失败。\n\n%s\n\n请前往 GitHub 手动下载。" % path_or_error,
                             parent=parent)

        progress_var.set("下载中...")
        download_update(download_url, progress_callback=on_progress, done_callback=on_done)

    cancel_btn = tk.Label(btn_frame, text="稍后", fg=COLORS["text_secondary"],
                          bg=COLORS["surface"], font=FONT,
                          cursor="hand2", padx=10)
    cancel_btn.pack(side=tk.LEFT)
    cancel_btn.bind("<Button-1>", lambda e: do_cancel())

    dl_btn = tk.Label(btn_frame, text="自动下载", fg=COLORS["accent"],
                      bg=COLORS["surface"], font=FONT_TITLE,
                      cursor="hand2", padx=10)
    dl_btn.pack(side=tk.RIGHT)
    dl_btn.bind("<Button-1>", lambda e: do_auto_download())

    browser_btn = tk.Label(btn_frame, text="手动下载", fg=COLORS["accent"],
                           bg=COLORS["surface"], font=FONT,
                           cursor="hand2", padx=10)
    browser_btn.pack(side=tk.RIGHT, padx=(0, 8))
    browser_btn.bind("<Button-1>", lambda e: do_open_browser())

    dlg.bind("<Escape>", lambda e: do_cancel())
