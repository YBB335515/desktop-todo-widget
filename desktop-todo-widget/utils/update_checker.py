"""GitHub release check and auto-update."""
import json
import os
import sys
import threading
import urllib.request
import webbrowser

from utils.common_utils import BASE_DIR

VERSION = "1.0.0"
GITHUB_REPO = "YBB335515/desktop-todo-widget"
GITHUB_API = "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO
GITHUB_RELEASES = "https://github.com/%s/releases" % GITHUB_REPO


def _version_greater(v1, v2):
    """Compare semantic versions. Returns True if v1 > v2."""
    try:
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)
        return parts1 > parts2
    except Exception:
        return v1 != v2


def check_for_updates():
    """Check GitHub for newer version.

    Returns (has_update, latest_version, download_url, error_message).
    """
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={"Accept": "application/vnd.github.v3+json",
                     "User-Agent": "DesktopTodoWidget/%s" % VERSION})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get("tag_name", "").lstrip("v")
        if _version_greater(latest, VERSION):
            assets = data.get("assets", [])
            download_url = assets[0]["browser_download_url"] if assets else None
            return (True, latest, download_url, None)
        return (False, VERSION, None, None)
    except Exception as e:
        return (False, VERSION, None, str(e))


def open_releases_page():
    webbrowser.open(GITHUB_RELEASES)


def download_update(url, progress_callback=None, done_callback=None):
    """Download update in background thread.

    progress_callback(bytes_downloaded, total_bytes)
    done_callback(success, filepath_or_error_message)
    """
    def _download():
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "DesktopTodoWidget/%s" % VERSION})
            with urllib.request.urlopen(req, timeout=600) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunks = []
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
                data = b"".join(chunks)
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else BASE_DIR
            new_path = os.path.join(exe_dir, "桌面待办_new.exe")
            with open(new_path, "wb") as f:
                f.write(data)
            if done_callback:
                done_callback(True, new_path)
        except Exception as e:
            if done_callback:
                done_callback(False, str(e))

    threading.Thread(target=_download, daemon=True).start()


def apply_update_and_restart(new_exe_path):
    """Create a batch script to replace current exe and restart. Returns True if launched."""
    if not getattr(sys, 'frozen', False):
        return False

    current_exe = sys.executable
    bat_path = os.path.join(os.path.dirname(current_exe), "_update.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write('@echo off\n')
        f.write('chcp 65001 >nul\n')
        f.write('echo Updating DesktopTodoWidget...\n')
        f.write('timeout /t 2 /nobreak >nul\n')
        f.write('del /f "%s"\n' % current_exe)
        f.write('move /y "%s" "%s"\n' % (new_exe_path, current_exe))
        f.write('start "" "%s"\n' % current_exe)
        f.write('del /f "%s"\n' % bat_path)

    import subprocess
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        [bat_path],
        creationflags=CREATE_NO_WINDOW,
        shell=True,
    )
    return True
