"""pytest 配置: sys.path 设置、离屏 GUI、marker 注册与自动 skip、共享 fixtures。"""

import os
import sys
import wave
import struct
import math

import pytest

# 将 src 目录加入 sys.path，供所有测试使用
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# GUI 测试默认离屏运行（无需真实显示器 / 不弹窗）。
# 必须在导入任何 PySide6 之前设置才生效。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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


def pytest_collection_modifyitems(config, items):
    """对 heavy/network 用例在环境不满足时自动 skip（而非 error/fail）。

    - e2e_heavy: 需 funasr 已安装。
    - e2e_network: 需环境变量 MEETSCRIBE_TEST_API_KEY。
    """
    heavy_skip = pytest.mark.skip(reason="需要 funasr + 模型 + 真实音频（装 funasr 后运行）")
    network_skip = pytest.mark.skip(reason="需要 MEETSCRIBE_TEST_API_KEY 环境变量")

    funasr_ok = _funasr_available()
    api_key_ok = bool(os.environ.get("MEETSCRIBE_TEST_API_KEY"))

    for item in items:
        if "e2e_heavy" in item.keywords and not funasr_ok:
            item.add_marker(heavy_skip)
        if "e2e_network" in item.keywords and not api_key_ok:
            item.add_marker(network_skip)


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
