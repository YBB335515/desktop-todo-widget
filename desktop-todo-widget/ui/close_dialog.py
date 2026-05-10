"""Close confirmation dialog — minimize to tray vs quit."""
import tkinter as tk

from config.settings_manager import load_settings, save_settings
from utils.common_utils import COLORS, FONT, FONT_HEADER


def show_close_dialog(parent, on_minimize, on_quit):
    """Show a dialog asking whether to minimize to tray or quit."""
    dialog = tk.Toplevel(parent)
    dialog.title("")
    dialog.configure(bg=COLORS["surface"])
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    try:
        dialog.wm_attributes("-toolwindow", True)
    except Exception:
        pass

    w, h = 320, 170
    px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
    py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
    dialog.geometry("%dx%d+%d+%d" % (w, h, px, py))

    dialog.configure(highlightbackground=COLORS["accent"],
                     highlightcolor=COLORS["accent"],
                     highlightthickness=1)

    # title
    tk.Label(dialog, text="关闭选项", fg=COLORS["text"], bg=COLORS["surface"],
             font=FONT_HEADER).pack(pady=(14, 8))

    # message
    tk.Label(dialog, text="请选择关闭行为：", fg=COLORS["text_secondary"],
             bg=COLORS["surface"], font=FONT).pack()

    # remember checkbox
    remember_var = tk.BooleanVar(value=False)
    cb = tk.Checkbutton(dialog, text="记住我的选择，不再询问",
                        variable=remember_var,
                        fg=COLORS["text_secondary"], bg=COLORS["surface"],
                        selectcolor=COLORS["surface"],
                        activebackground=COLORS["surface"],
                        activeforeground=COLORS["text"],
                        font=("Microsoft YaHei UI", 8))
    cb.pack(pady=(6, 10))

    # buttons
    btn_frame = tk.Frame(dialog, bg=COLORS["surface"])
    btn_frame.pack()

    result = {"action": None}

    def do_minimize():
        if remember_var.get():
            s = load_settings()
            s["close_action"] = "minimize"
            save_settings(s)
        result["action"] = "minimize"
        dialog.destroy()

    def do_quit():
        if remember_var.get():
            s = load_settings()
            s["close_action"] = "quit"
            save_settings(s)
        result["action"] = "quit"
        dialog.destroy()

    def do_cancel():
        dialog.destroy()

    btn_style = {"font": FONT, "bd": 1, "relief": "flat", "padx": 12, "pady": 4,
                 "cursor": "hand2"}

    tk.Button(btn_frame, text="最小化到托盘", bg=COLORS["accent"],
              fg=COLORS["bg"], activebackground=COLORS["accent"],
              activeforeground=COLORS["bg"],
              command=do_minimize, **btn_style).pack(side=tk.LEFT, padx=4)

    tk.Button(btn_frame, text="直接关闭", bg=COLORS["danger"],
              fg=COLORS["bg"], activebackground=COLORS["danger"],
              activeforeground=COLORS["bg"],
              command=do_quit, **btn_style).pack(side=tk.LEFT, padx=4)

    tk.Button(btn_frame, text="取消", bg=COLORS["input_bg"],
              fg=COLORS["text"], activebackground=COLORS["input_bg"],
              activeforeground=COLORS["text"],
              command=do_cancel, **btn_style).pack(side=tk.LEFT, padx=4)

    dialog.protocol("WM_DELETE_WINDOW", do_cancel)

    parent.wait_window(dialog)
    return result["action"]
