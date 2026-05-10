# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DesktopTodoWidget.
Entry point: main.py (project root)
"""
import os
import sys

# Add project root to path so PyInstaller can resolve imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Collect Vosk DLLs ----
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

# ---- Collect data files ----
_datas = []
_data_dir = os.path.join(_project_root, "data")
if os.path.isdir(_data_dir):
    for _f in os.listdir(_data_dir):
        _src = os.path.join(_data_dir, _f)
        if os.path.isfile(_src):
            _datas.append((_src, 'data'))

_block_cipher = None

a = Analysis(
    [os.path.join(_project_root, 'main.py')],
    pathex=[_project_root],
    binaries=_vosk_binaries + _pyaudio_binaries,
    datas=_datas,
    hiddenimports=[
        'vosk',
        'pyaudio',
        'speech_recognition',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'json',
        'wave',
        'core',
        'core.task_manager',
        'core.reminder_service',
        'core.voice_recognizer',
        'core.natural_language',
        'ui',
        'ui.main_window',
        'ui.edit_dialog',
        'ui.settings_dialog',
        'ui.reminder_popup',
        'ui.close_dialog',
        'ui.tray_icon',
        'utils',
        'utils.common_utils',
        'utils.registry_utils',
        'utils.update_checker',
        'config',
        'config.settings_manager',
        'urllib.request',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
