"""首次启动引导（UI-011 / T-G11）集成测试。

覆盖三步向导：模型下载 / VB-Cable 检测 / API Key 配置，以及跳过路径。
全程 mock ModelManager 与 VB-Cable 检测，不触发真实下载/网络/设备访问。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)


class FakeConfig:
    """轻量内存版 Config，记录 set/save 调用，便于断言。"""

    def __init__(self, data=None):
        self._data = dict(data or {})
        self.saved = False

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, save=True):
        self._data[key] = value
        if save:
            self.save()

    def save(self):
        self.saved = True


@pytest.fixture
def fake_config():
    return FakeConfig({"first_launch": True})


# ── check_first_launch / show_first_launch_dialog 入口兼容性 ──────────

def test_check_first_launch_defaults_true_when_no_config():
    from gui.first_launch import check_first_launch
    assert check_first_launch(None) is True


def test_check_first_launch_reads_config(fake_config):
    from gui.first_launch import check_first_launch
    assert check_first_launch(fake_config) is True
    fake_config.set("first_launch", False)
    assert check_first_launch(fake_config) is False


# ── 步骤 1：模型下载调用真实 ModelManager（非 time.sleep 模拟） ──────

def test_model_worker_calls_real_download_all_missing():
    """下载 worker 必须调用 ModelManager.download_all_missing，而非 time.sleep 模拟。"""
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.download_all_missing.return_value = (True, "所有模型下载完成")

    with patch.object(first_launch, "ModelManager", return_value=mock_mgr) as MM, \
         patch("time.sleep") as mock_sleep:
        worker = first_launch.ModelDownloadWorker("/tmp/models_cache")
        # 直接同步执行 run()，不启动 QThread 事件循环
        worker.run()

    MM.assert_called_once_with("/tmp/models_cache")
    mock_mgr.download_all_missing.assert_called_once()
    # 进度回调应作为参数传入
    assert "progress_callback" in mock_mgr.download_all_missing.call_args.kwargs or \
        mock_mgr.download_all_missing.call_args.args, "应传入进度回调"
    mock_sleep.assert_not_called()


def test_model_worker_emits_finished_on_success():
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.download_all_missing.return_value = (True, "完成")

    received = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr):
        worker = first_launch.ModelDownloadWorker("/tmp/mc")
        worker.finished.connect(lambda ok, msg: received.append((ok, msg)))
        worker.run()

    assert received and received[-1][0] is True


# ── 步骤 2：VB-Cable 检测反映安装状态 ──────────────────────────────

def test_vb_cable_detection_function_exists():
    from gui import first_launch
    assert hasattr(first_launch, "detect_vb_cable")


def test_dialog_reflects_vb_cable_installed(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=True):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        assert dlg.is_vb_cable_installed() is True


def test_dialog_reflects_vb_cable_missing(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=False):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        assert dlg.is_vb_cable_installed() is False


# ── 步骤 3：API Key 写入 config ───────────────────────────────────

def test_api_key_saved_to_config(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=True):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        dlg.set_api_key_text("sk-test-12345")
        dlg.save_api_key()

    assert fake_config.get("ai_user_api_key") == "sk-test-12345"


def test_api_key_skip_leaves_unset(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=True):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        # 不填写直接保存（跳过），不应写入 key
        dlg.save_api_key()

    assert not fake_config.get("ai_user_api_key", "")


# ── 完成/跳过后 first_launch=false ────────────────────────────────

def test_finish_sets_first_launch_false(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=True):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        dlg.finish_wizard()

    assert fake_config.get("first_launch") is False


def test_skip_all_sets_first_launch_false(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = ["SenseVoiceSmall"]
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=False):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        dlg.skip_all()

    assert fake_config.get("first_launch") is False


def test_show_first_launch_dialog_noop_when_not_first(fake_config):
    """非首次启动时不应弹窗。"""
    from gui import first_launch

    fake_config.set("first_launch", False)
    with patch.object(first_launch, "FirstLaunchDialog") as Dlg:
        first_launch.show_first_launch_dialog(None, fake_config)
        Dlg.assert_not_called()


# ── 多步向导结构存在 ─────────────────────────────────────────────

def test_wizard_has_three_steps(fake_config, qtbot):
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.get_missing_models.return_value = []
    with patch.object(first_launch, "ModelManager", return_value=mock_mgr), \
         patch.object(first_launch, "detect_vb_cable", return_value=True):
        dlg = first_launch.FirstLaunchDialog(config=fake_config)
        qtbot.addWidget(dlg)
        assert dlg.step_count() >= 3
