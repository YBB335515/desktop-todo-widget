"""Windows registry operations for autostart."""
import os
import sys


APP_NAME = "DesktopTodoWidget"


def _get_startup_command():
    """Return the command line string for autostart registration."""
    if getattr(sys, 'frozen', False):
        return '"%s"' % sys.executable
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py = os.path.join(base, "main.py")
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        return '"%s" "%s"' % (pythonw, main_py)


def set_autostart():
    """Add to Windows startup registry. Returns True on success."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_startup_command())
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def remove_autostart():
    """Remove from Windows startup registry. Returns True on success."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def is_autostart_enabled():
    """Check if autostart is currently enabled in registry."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def update_autostart_path():
    """Update registry entry if exe has moved. Returns True if updated."""
    if sys.platform != "win32":
        return False
    current_cmd = _get_startup_command()
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
        try:
            old_cmd, _ = winreg.QueryValueEx(key, APP_NAME)
            if old_cmd != current_cmd:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, current_cmd)
                winreg.CloseKey(key)
                return True
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass
    return False
