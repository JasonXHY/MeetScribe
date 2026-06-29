# -*- mode: python ; coding: utf-8 -*-
# 侧耳倾听 PyInstaller 打包配置

import os
import sys

from PyInstaller.utils.hooks import collect_all

# 项目根目录
ROOT = r"C:/侧耳倾听"

# ── 收集 FunASR 及其依赖链（ASR 本地转写所需）─────────────────
# 关键：必须用 collect_all 把这些包作为「代码」收集（含子模块、数据文件、
# 原生二进制），而不是简单地把 funasr 目录当作 datas 拷进去——后者不会进入
# sys.path，运行时 `import funasr` 仍然失败（No module named 'funasr'）。
# FunASR 通过 tables.register 动态注册模型类、按字符串导入子模块，PyInstaller
# 的静态分析无法跟踪，因此手写 hiddenimports 列表必然不全。
# 同时 funasr 依赖 torch / torchaudio / modelscope / sentencepiece 等重型包，
# 缺一不可。
_collect_packages = [
    'funasr',
    'torch',
    'torchaudio',
    'modelscope',
    'sentencepiece',
    'kaldiio',
    'jieba',
]

_collected_datas = []
_collected_binaries = []
_collected_hiddenimports = []
for _pkg in _collect_packages:
    _d, _b, _h = collect_all(_pkg)
    _collected_datas += _d
    _collected_binaries += _b
    _collected_hiddenimports += _h

a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[ROOT, os.path.join(ROOT, 'src')],
    binaries=_collected_binaries,
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
        (os.path.join(ROOT, 'src', 'config'), 'src/config'),
    ] + _collected_datas,
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'soundfile',
        'numpy',
        'openai',
        'pyaudiowpatch',
        'markdown',
        'voiceprint',
        'dual_track_merge',
        'model_registry',
        'formatters',
        'speaker_namer',
        'ai_service',
        'gui.first_launch',
        'gui.dialogs',
        'gui.home_page',
        'gui.transcription',
        'gui.settings_page',
        'gui.voiceprint_page',
        'gui.topbar',
        'gui.recording_bar',
        'gui.file_list_view',
        'gui.styles',
        'gui.icons',
    ] + _collected_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'cv2',
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
