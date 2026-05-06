# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DesktopTodoWidget.
Usage:
    pyinstaller desktop_todo_widget.spec
    Or just: python build_exe.py

Includes Vosk DLLs, PyAudio, and supports offline Windows SAPI fallback.
"""

import os
import sys

# ---- Collect Vosk DLLs (4 DLLs needed by libvosk) ----
_vosk_dir = None
try:
    import vosk
    _vosk_dir = os.path.dirname(vosk.__file__)
except ImportError:
    pass

_vosk_binaries = []
if _vosk_dir:
    for _f in os.listdir(_vosk_dir):
        if _f.lower().endswith('.dll'):
            _vosk_binaries.append((os.path.join(_vosk_dir, _f), 'vosk'))
    # Also grab the Python extension
    for _f in os.listdir(_vosk_dir):
        if _f.endswith('.pyd'):
            _vosk_binaries.append((os.path.join(_vosk_dir, _f), 'vosk'))

# ---- Collect PyAudio ----
_pyaudio_binaries = []
try:
    import pyaudio
    _py_dir = os.path.dirname(pyaudio.__file__)
    for _f in os.listdir(_py_dir):
        if _f.endswith('.pyd') or _f.lower().endswith('.dll'):
            _pyaudio_binaries.append((os.path.join(_py_dir, _f), 'pyaudio'))
except ImportError:
    pass

# ---- Build the Analysis ----
_block_cipher = None

a = Analysis(
    ['desktop_todo_widget.py'],
    pathex=[],
    binaries=_vosk_binaries + _pyaudio_binaries,
    datas=[],
    hiddenimports=[
        'vosk',
        'pyaudio',
        'speech_recognition',
        'json',
        'wave',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=_block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=_block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='桌面待办',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
