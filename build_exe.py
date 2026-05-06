"""
Build helper: packages DesktopTodoWidget into a standalone .exe with PyInstaller.

Usage:
    python build_exe.py

Before building, download the Vosk Chinese model for offline recognition:
    https://alphacephei.com/vosk/models
    Download: vosk-model-small-cn-0.22.zip (~42 MB)
    Extract to: ./vosk-model-cn  (same directory as this script)

The model folder will be copied alongside the .exe automatically.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_SRC = os.path.join(ROOT, "vosk-model-cn")
DIST_DIR = os.path.join(ROOT, "dist")

def check_model():
    """Check if Vosk CN model exists."""
    marker = os.path.join(MODEL_SRC, "am", "final.mdl")
    if os.path.isfile(marker):
        print(f"[OK] Vosk 中文模型: {MODEL_SRC}")
        return True
    print(f"[WARN] Vosk 中文模型未找到: {MODEL_SRC}")
    print("  语音识别将使用 Windows 内置 SAPI 作为离线引擎（无需额外安装）")
    print("  如需更准确的离线识别，请下载 Vosk 模型:")
    print("    https://alphacephei.com/vosk/models")
    print("    下载 vosk-model-small-cn-0.22.zip")
    print(f"    解压到: {MODEL_SRC}")
    return False

def clean_dist():
    """Remove previous build."""
    dist = DIST_DIR
    if os.path.isdir(dist):
        try:
            print(f"[清理] 删除旧构建: {dist}")
            shutil.rmtree(dist)
        except PermissionError:
            print("[警告] 无法删除旧构建（exe 可能正在运行）")
            print("  请关闭 exe 后重试，或手动删除 dist 文件夹")
            sys.exit(1)

def run_pyinstaller():
    """Run PyInstaller with the spec file."""
    spec = os.path.join(ROOT, "desktop_todo_widget.spec")
    print("[构建] 运行 PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec, "--noconfirm"],
        cwd=ROOT, capture_output=False)
    if result.returncode != 0:
        print("[ERROR] PyInstaller 构建失败")
        sys.exit(1)
    print("[OK] PyInstaller 构建完成")

def copy_model():
    """Copy Vosk model alongside the exe."""
    if not os.path.isdir(MODEL_SRC):
        return
    target = os.path.join(DIST_DIR, "vosk-model-cn")
    if os.path.isdir(target):
        shutil.rmtree(target)
    print(f"[复制] Vosk 模型 -> {target}")
    shutil.copytree(MODEL_SRC, target)

def copy_tasks():
    """Copy existing tasks.json if present."""
    src = os.path.join(ROOT, "tasks.json")
    if os.path.isfile(src):
        # Don't overwrite user's tasks in dist
        dst = os.path.join(DIST_DIR, "tasks.json")
        if not os.path.isfile(dst):
            shutil.copy2(src, dst)
            print(f"[复制] tasks.json -> {dst}")

def main():
    print("=" * 50)
    print("DesktopTodoWidget - 构建工具")
    print("=" * 50)
    check_model()
    clean_dist()
    run_pyinstaller()
    copy_model()
    copy_tasks()
    print("=" * 50)
    print(f"[完成] exe 位于: {os.path.join(DIST_DIR, '桌面待办.exe')}")
    print()
    print("语音识别引擎（按优先级）:")
    print("  1. Vosk 离线识别（需 vosk-model-cn 文件夹与 exe 同目录）")
    print("  2. Windows SAPI 离线识别（系统内置，无需配置）")
    print("  3. Google 在线识别（需联网 + 科学上网）")
    print("=" * 50)

if __name__ == "__main__":
    main()
