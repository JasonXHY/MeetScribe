"""首次启动引导（v1.0 两步向导）集成测试。

覆盖：内测提醒+API选择 / 模型下载，以及跳过路径。
全程 mock ModelManager，不触发真实下载/网络访问。
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


# ── check_first_launch 入口兼容性 ──────────

def test_check_first_launch_defaults_true_when_no_config():
    from gui.first_launch import check_first_launch
    assert check_first_launch(None) is True


def test_check_first_launch_reads_config(fake_config):
    from gui.first_launch import check_first_launch
    assert check_first_launch(fake_config) is True
    fake_config.set("first_launch", False)
    assert check_first_launch(fake_config) is False


# ── 模型下载 worker ──────────────────────

def test_model_worker_calls_real_download_all_missing():
    """下载 worker 必须调用 ModelManager.download_all_missing。"""
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.download_all_missing.return_value = (True, "所有模型下载完成")

    with patch("transcriber.ModelManager", return_value=mock_mgr):
        worker = first_launch.ModelDownloadWorker("/tmp/models_cache")
        worker.run()

    mock_mgr.download_all_missing.assert_called_once()


def test_model_worker_emits_finished_on_success():
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.download_all_missing.return_value = (True, "完成")

    received = []
    with patch("transcriber.ModelManager", return_value=mock_mgr):
        worker = first_launch.ModelDownloadWorker("/tmp/mc")
        worker.finished.connect(lambda ok, msg: received.append((ok, msg)))
        worker.run()

    assert received and received[-1][0] is True


# ── 内测提醒步骤 ──────────────────────────

def test_dialog_has_beta_notice_step(fake_config, qtbot):
    """弹窗第一步应显示内测提醒。"""
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    assert dlg._stack.currentIndex() == 0


def test_builtin_api_button_sets_config(fake_config, qtbot):
    """点击"用开发者的API"应清空 user api key。"""
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._on_use_builtin()

    # 应该跳到第二步
    assert dlg._stack.currentIndex() == 1
    # user api key 应被清空
    assert fake_config.get("ai_user_api_key") == ""


# ── 完成/跳过后 first_launch=false ─────────

def test_finish_sets_first_launch_false(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._finish()

    assert fake_config.get("first_launch") is False


def test_skip_all_sets_first_launch_false(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._on_skip()

    assert fake_config.get("first_launch") is False


def test_show_first_launch_dialog_noop_when_not_first(fake_config):
    """非首次启动时不应弹窗。"""
    from gui import first_launch

    fake_config.set("first_launch", False)
    with patch.object(first_launch, "FirstLaunchDialog") as Dlg:
        first_launch.show_first_launch_dialog(None, fake_config)
        Dlg.assert_not_called()


# ── 向导结构 ──────────────────────────────

def test_wizard_has_two_steps(fake_config, qtbot):
    """v1.0 向导应有两步：内测提醒 + 模型下载。"""
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    assert dlg.step_count() == 2
