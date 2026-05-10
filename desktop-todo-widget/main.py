"""Desktop Todo Widget — 桌面待办小组件入口."""
import os
import sys

# Ensure project root is on path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import DesktopTodoWidget
from utils.common_utils import BASE_DIR

if __name__ == "__main__":
    try:
        app = DesktopTodoWidget()
        app.run()
    except Exception:
        import traceback
        log_path = os.path.join(BASE_DIR, "data", "_error.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        try:
            from tkinter import messagebox
            messagebox.showerror("启动失败", "程序异常退出，详情见:\n%s" % log_path)
        except Exception:
            pass
        sys.exit(1)
