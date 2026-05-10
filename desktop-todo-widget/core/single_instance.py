"""Single-instance enforcement via PID lock file + bring existing window to front.

The lock file is stored under %LOCALAPPDATA%/DesktopTodoWidget/ so that both
.bat (source) and .exe (frozen) launches share the same lock, regardless of
where the app is installed.
"""
import atexit
import ctypes
import os
import sys

WINDOW_TITLE = "待办事项"

_LOCK_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                         "DesktopTodoWidget")
LOCK_FILE = os.path.join(_LOCK_DIR, "_app.lock")


def _pid_is_running(pid: int) -> bool:
    """Check if a process with the given PID is still running (Windows)."""
    try:
        import ctypes.wintypes
        SYNCHRONIZE = 0x00100000
        PROCESS_QUERY_LIMITED_INFO = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFO | SYNCHRONIZE, False, pid)
        if not handle:
            return False
        exit_code = ctypes.wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == 259  # STILL_ACTIVE
    except Exception:
        return False


def _find_and_restore_window(title: str) -> bool:
    """Find a top-level window by title and bring it to the foreground."""
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if not hwnd:
            return False
        # SW_SHOWNORMAL = 1: activates and displays the window, restoring from
        # minimized or hidden state to its original size and position.
        ctypes.windll.user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def acquire_instance() -> bool:
    """Try to acquire the single-instance lock.

    Returns True if this is the only instance (proceed to start).
    Returns False if another instance is already running (should exit).
    """
    os.makedirs(_LOCK_DIR, exist_ok=True)

    if os.path.isfile(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if _pid_is_running(old_pid):
                _find_and_restore_window(WINDOW_TITLE)
                return False
            # Stale lock — remove it
            os.remove(LOCK_FILE)
        except (ValueError, OSError):
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        atexit.register(_release_lock)
        return True
    except OSError:
        return True  # If we can't write the lock, just run anyway


def _release_lock():
    """Remove the lock file on exit."""
    try:
        if os.path.isfile(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass


def release_instance():
    """Public API to release the lock (called on app quit)."""
    _release_lock()
