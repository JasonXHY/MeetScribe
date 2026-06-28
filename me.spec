# -*- mode: python ; coding: utf-8 -*-
# 侧耳倾听 PyInstaller 打包配置

import os
import sys

# 项目根目录
ROOT = r"C:/侧耳倾听"

a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[ROOT, os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
        (os.path.join(ROOT, 'src', 'config'), 'src/config'),
    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'soundfile',
        'numpy',
        'funasr',
        'openai',
        'pyaudiowpatch',
        'modelscope',
        'markdown',
        'voiceprint',
        'dual_track_merge',
        'model_registry',
        'gui.first_launch',
        'gui.dialogs',
        'gui.home_page',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'cv2',
        'scipy',
        'pandas',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='侧耳倾听',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'assets', 'logo.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='侧耳倾听',
)
