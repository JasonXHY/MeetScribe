"""pytest 配置: sys.path 设置、离屏 GUI、marker 注册与自动 skip、共享 fixtures。"""

import os
import sys
import wave
import struct
import math
from pathlib import Path

import pytest

# 将 src 目录加入 sys.path，供所有测试使用
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# GUI 测试默认离屏运行（无需真实显示器 / 不弹窗）。
# 必须在导入任何 PySide6 之前设置才生效。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_addoption(parser):
    parser.addoption("--run-heavy", action="store_true", default=False,
                     help="运行 e2e_heavy 测试（真实子进程 + 模型）")
    parser.addoption("--run-network", action="store_true", default=False,
                     help="运行 e2e_network 测试（真实 API 调用）")


def pytest_configure(config):
    config.addinivalue_line("markers", "gui: 标记需要图形界面环境的测试")
    config.addinivalue_line("markers", "timeout: 设置测试超时时间（秒）")
    config.addinivalue_line("markers", "unit: 纯单元测试，无外部依赖")
    config.addinivalue_line("markers", "integration: 需要 PySide6/qtbot，offscreen 可跑")
    config.addinivalue_line("markers", "e2e_heavy: 需要 funasr + 模型 + 真实音频 fixtures")
    config.addinivalue_line("markers", "e2e_network: 需要真实云端 API Key")


def _funasr_available():
    import importlib.util
    return importlib.util.find_spec("funasr") is not None


def _pyaudio_available():
    import importlib.util
    return importlib.util.find_spec("pyaudiowpatch") is not None or \
           importlib.util.find_spec("pyaudio") is not None


# 需要 funasr 的测试文件名模式
_FUNASR_TEST_PATTERNS = [
    "test_transcriber",
    "test_voiceprint_extraction",
    "test_voiceprint_fix",
    "test_voiceprint_threshold",
]

# 需要 pyaudiowpatch 的测试文件名模式
_PYAUDIO_TEST_PATTERNS = [
    "test_recorder",
]


def pytest_ignore_collect(collection_path, config):
    """在收集阶段（导入之前）跳过需要重型依赖的测试文件。

    此钩子在 pytest 尝试导入测试文件之前执行，
    因此可以避免因模块级导入失败导致的 Exit Code 3。
    """
    if not collection_path.is_file() or collection_path.suffix != ".py":
        return False

    filename = collection_path.stem

    if any(pattern in filename for pattern in _FUNASR_TEST_PATTERNS):
        if not _funasr_available():
            return True

    if any(pattern in filename for pattern in _PYAUDIO_TEST_PATTERNS):
        if not _pyaudio_available():
            return True

    return False


def pytest_collection_modifyitems(config, items):
    """对 heavy/network 用例在环境不满足时自动 skip（而非 error/fail）。

    - e2e_heavy: 需 funasr 已安装 + --run-heavy 标志。
    - e2e_network: 需 MEETSCRIBE_TEST_API_KEY 环境变量 + --run-network 标志。
    """
    heavy_skip = pytest.mark.skip(reason="需要 funasr + 模型（运行: pytest --run-heavy）")
    network_skip = pytest.mark.skip(reason="需要 API Key（运行: pytest --run-network）")

    funasr_ok = _funasr_available()
    api_key_ok = bool(os.environ.get("MEETSCRIBE_TEST_API_KEY"))
    run_heavy = config.getoption("--run-heavy", default=False)
    run_network = config.getoption("--run-network", default=False)

    for item in items:
        if "e2e_heavy" in item.keywords:
            if not run_heavy or not funasr_ok:
                item.add_marker(heavy_skip)
        if "e2e_network" in item.keywords:
            if not run_network or not api_key_ok:
                item.add_marker(network_skip)


@pytest.fixture
def app():
    """创建 QApplication 实例（模块级共享）"""
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def synthetic_wav(tmp_path):
    """生成小体积、合法的 16kHz 单声道 WAV，供轻量集成测试使用。

    返回工厂函数: make(name="x.wav", seconds=1.0, freq=440) -> 路径。
    不依赖 funasr——仅用于"加文件→状态流转→（mock 转写）"类集成测试，
    不要求 ASR 准确率。
    """
    def _make(name="synthetic.wav", seconds=1.0, freq=440.0, rate=16000):
        path = os.path.join(str(tmp_path), name)
        n = int(seconds * rate)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # PCM16
            wf.setframerate(rate)
            frames = bytearray()
            for i in range(n):
                val = int(32767.0 * 0.2 * math.sin(2 * math.pi * freq * i / rate))
                frames += struct.pack("<h", val)
            wf.writeframes(bytes(frames))
        return path
    return _make
