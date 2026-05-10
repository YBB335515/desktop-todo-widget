"""Settings dialog: autostart toggle, update check, version info."""
import threading
import tkinter as tk
from tkinter import messagebox

from config.settings_manager import load_settings, save_settings
from utils.common_utils import COLORS, FONT, FONT_SMALL, FONT_TITLE
from utils.registry_utils import set_autostart, remove_autostart, is_autostart_enabled
from utils.update_checker import VERSION, check_for_updates, download_update, \
    apply_update_and_restart, open_releases_page


def show_settings_dialog(parent):
    """Show settings dialog. Applies changes immediately on save."""
    settings = load_settings()

    dlg = tk.Toplevel(parent)
    dlg.title("设置")
    dlg.configure(bg=COLORS["surface"])
    dlg.resizable(False, False)
    dlg.transient(parent)

    dlg_w, dlg_h = 360, 290
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

    # bottom buttons
    btn_frame = tk.Frame(dlg, bg=COLORS["surface"])
    btn_frame.pack(fill=tk.X, padx=16, pady=(14, 16))

    def do_cancel():
        dlg.destroy()

    cancel_btn = tk.Label(btn_frame, text="取消", fg=COLORS["text_secondary"],
                          bg=COLORS["surface"], font=FONT,
                          cursor="hand2", padx=10)
    cancel_btn.pack(side=tk.RIGHT)
    cancel_btn.bind("<Button-1>", lambda e: do_cancel())

    def do_save():
        settings["autostart"] = auto_var.get()
        settings["close_action"] = close_var.get()
        save_settings(settings)
        if settings["autostart"]:
            set_autostart()
        else:
            remove_autostart()
        dlg.destroy()

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
