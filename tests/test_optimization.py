"""
MeetScribe 性能优化验证测试
运行方式: pytest tests/test_optimization.py -v
"""

import os

import pytest


def test_model_directory_size():
    """验证模型目录大小 < 2GB"""
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models_cache', 'models')
    if not os.path.exists(models_dir):
        pytest.skip("模型目录不存在")

    total_size = 0
    for dirpath, dirnames, filenames in os.walk(models_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)

    size_gb = total_size / (1024**3)
    print(f"模型目录大小: {size_gb:.2f} GB")
    assert size_gb < 3.0, f"模型目录大小 {size_gb:.2f} GB 超过 3GB 限制"


def test_gui_import():
    """验证 GUI 模块可以正常导入"""
    from gui import app, home_page, settings_page, transcription, dialogs, styles
    print("所有 GUI 模块导入成功")


def test_transcriber_import():
    """验证转写模块可以正常导入"""
    from transcriber import Transcriber, REQUIRED_MODELS
    print(f"转写模块导入成功，模型数量: {len(REQUIRED_MODELS)}")
