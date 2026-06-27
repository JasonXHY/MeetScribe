#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置页面 UI 测试和首次启动引导测试（提取自 test_gui_config.py）。"""

import os
import sys
import json
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config

pytestmark = pytest.mark.integration


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    """创建 QApplication 实例（模块级共享）"""
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def config():
    """创建临时 Config 实例"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{}')
        temp_path = f.name
    try:
        cfg = Config(temp_path)
        yield cfg
    finally:
        os.remove(temp_path)


def _create_settings_page(config):
    """辅助函数：创建 SettingsPage 实例"""
    from gui.settings_page import SettingsPage
    with patch('gui.settings_page.QMessageBox'):
        page = SettingsPage(config=config, log_callback=lambda msg: None)
    return page


# ═══════════════════════════════════════════════════════════════
# 1. 引擎参数 ComboBox（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestEngineComboBoxes:
    """引擎参数 ComboBox 存在且有正确选项"""

    def test_punc_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._punc_var.itemText(i) for i in range(page._punc_var.count())]
        assert "自动 (ct-punc)" in options
        assert "关闭" in options

    def test_garble_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._garble_var.itemText(i) for i in range(page._garble_var.count())]
        assert "开启 (中文模式)" in options
        assert "关闭" in options

    def test_vad_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._vad_var.itemText(i) for i in range(page._vad_var.count())]
        assert "适中 (推荐)" in options
        assert "高 (更多分段)" in options
        assert "低 (更少分段)" in options

    def test_device_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._device_var.itemText(i) for i in range(page._device_var.count())]
        assert "CPU" in options
        assert "CUDA (GPU)" in options


# ═══════════════════════════════════════════════════════════════
# 2. 保存配置（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestSaveConfig:
    """保存配置包含引擎参数 key"""

    def test_save_includes_punc_restore(self, config, app):
        page = _create_settings_page(config)
        page._punc_var.setCurrentText("关闭")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("punc_restore") == "关闭"

    def test_save_includes_garble_filter(self, config, app):
        page = _create_settings_page(config)
        page._garble_var.setCurrentText("关闭")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("garble_filter") == "关闭"

    def test_save_includes_vad_sensitivity(self, config, app):
        page = _create_settings_page(config)
        page._vad_var.setCurrentText("高 (更多分段)")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("vad_sensitivity") == "高 (更多分段)"

    def test_save_includes_device(self, config, app):
        page = _create_settings_page(config)
        page._device_var.setCurrentText("CUDA (GPU)")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("device") == "CUDA (GPU)"

    def test_save_includes_all_engine_keys(self, config, app):
        page = _create_settings_page(config)
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        d = config.as_dict()
        assert "punc_restore" in d
        assert "garble_filter" in d
        assert "vad_sensitivity" in d
        assert "device" in d


# ═══════════════════════════════════════════════════════════════
# 3. 恢复配置（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestRestoreConfig:
    """恢复配置能正确还原引擎参数"""

    def test_restore_punc(self, config, app):
        config.set("punc_restore", "关闭")
        page = _create_settings_page(config)
        assert page._punc_var.currentText() == "关闭"

    def test_restore_garble(self, config, app):
        config.set("garble_filter", "关闭")
        page = _create_settings_page(config)
        assert page._garble_var.currentText() == "关闭"

    def test_restore_vad(self, config, app):
        config.set("vad_sensitivity", "高 (更多分段)")
        page = _create_settings_page(config)
        assert page._vad_var.currentText() == "高 (更多分段)"

    def test_restore_device(self, config, app):
        config.set("device", "CUDA (GPU)")
        page = _create_settings_page(config)
        assert page._device_var.currentText() == "CUDA (GPU)"


# ═══════════════════════════════════════════════════════════════
# 4. Ollama 本地 LLM 配置（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestOllamaConfig:
    """Ollama 本地 LLM 地址 / 模型配置（SET-016）"""

    def test_ollama_address_default(self, config, app):
        page = _create_settings_page(config)
        assert page._ollama_url_entry.text() == "http://localhost:11434/v1"
        assert page._ollama_model_entry.text() == "qwen3:1.7b"

    def test_ollama_address_save_restore(self, config, app):
        page = _create_settings_page(config)
        page._ollama_url_entry.setText("http://host:1234/v1")
        page._ollama_model_entry.setText("llama3")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()

        assert config.get("ollama_url") == "http://host:1234/v1"
        assert config.get("ollama_model") == "llama3"

        page2 = _create_settings_page(config)
        assert page2._ollama_url_entry.text() == "http://host:1234/v1"
        assert page2._ollama_model_entry.text() == "llama3"


# ═══════════════════════════════════════════════════════════════
# 5. 转写输出目录 save/restore（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestOutputDirRoundtrip:
    """T-G3: 转写输出目录 save/restore 必须用同一个配置键。"""

    def test_output_dir_save_restore_roundtrip(self, config, app):
        page = _create_settings_page(config)
        page._out_dir_entry.setText("/custom/out/dir")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()

        page2 = _create_settings_page(config)
        assert page2._out_dir_entry.text() == "/custom/out/dir"

    def test_output_dir_saved_under_transcript_dir_key(self, config, app):
        """权威键为 transcript_dir（与 app.get_output_dir 一致）。"""
        page = _create_settings_page(config)
        page._out_dir_entry.setText("/custom/out/dir")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("transcript_dir") == "/custom/out/dir"


# ═══════════════════════════════════════════════════════════════
# 6. 首次启动引导（test_first_launch）
# ═══════════════════════════════════════════════════════════════


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


def test_check_first_launch_defaults_true_when_no_config():
    from gui.first_launch import check_first_launch
    assert check_first_launch(None) is True


def test_check_first_launch_reads_config(fake_config):
    from gui.first_launch import check_first_launch
    assert check_first_launch(fake_config) is True
    fake_config.set("first_launch", False)
    assert check_first_launch(fake_config) is False


def test_model_worker_calls_real_download_all_missing():
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


def test_dialog_has_beta_notice_step(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    assert dlg._stack.currentIndex() == 0


def test_builtin_api_button_sets_config(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._on_use_builtin()

    assert dlg._stack.currentIndex() == 1
    assert fake_config.get("ai_user_api_key") == ""


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
    from gui import first_launch

    fake_config.set("first_launch", False)
    with patch.object(first_launch, "FirstLaunchDialog") as Dlg:
        first_launch.show_first_launch_dialog(None, fake_config)
        Dlg.assert_not_called()


# ══════════════════════════════════════════════════════════
#  L7: 设置页持久化 (from test_tdd_flows.py)
# ══════════════════════════════════════════════════════════

class TestSettingsPersistence:
    """设置页保存与恢复验证"""

    def test_config_save_restore(self):
        """配置保存后可恢复"""
        import logging
        logger = logging.getLogger("TDD_Test")
        config_path = os.path.join(tempfile.gettempdir(), "test_settings.json")

        try:
            # 创建并保存
            config = Config(config_path)
            config.set("test_key", "test_value_12345", save=True)

            # 重新加载
            config2 = Config(config_path)
            assert config2.get("test_key") == "test_value_12345", \
                "Config should persist after save"

            logger.info("PASS: Config save/restore OK")
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)


# ══════════════════════════════════════════════════════════
#  config 空值过滤 (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestConfigEmptyFilter:
    """config 空字符串不应覆盖 DEFAULTS"""

    def test_empty_string_not_overwrite_default(self, tmp_path):
        config_path = tmp_path / "settings.json"
        config_path.write_text(json.dumps({
            "ai_vendor": "",
            "ai_model": "",
            "auto_correction": "",
        }))
        from config import Config
        config = Config(str(config_path))
        assert config.get("ai_vendor") == "小米 MiMo"
        assert config.get("ai_model") == "mimo-v2.5"
        assert config.get("auto_correction") == "关闭"

    def test_empty_string_allowed_when_default_empty(self):
        from config import Config, DEFAULTS
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "settings.json")
            empty_keys = [k for k, v in DEFAULTS.items() if v == ""]
            if not empty_keys:
                pytest.skip("No empty-string defaults to test")
            test_data = {empty_keys[0]: ""}
            with open(config_path, 'w') as f:
                json.dump(test_data, f)
            config = Config(config_path)
            assert config.get(empty_keys[0]) == ""

    def test_real_value_preserved(self):
        from config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "settings.json")
            with open(config_path, 'w') as f:
                json.dump({"ai_vendor": "自定义厂商"}, f)
            config = Config(config_path)
            assert config.get("ai_vendor") == "自定义厂商"


# ═══════════════════════════════════════════════════════════════
# GAP-12: first_launch 信号流测试
# ═══════════════════════════════════════════════════════════════


class TestFirstLaunchSignalFlow:
    """GAP-12: first_launch 信号流测试"""

    def test_setup_own_emits_go_to_settings(self, qtbot):
        """点击'我有 API Key'应触发 go_to_settings 信号"""
        from unittest.mock import MagicMock
        from gui.first_launch import FirstLaunchDialog
        from config import Config
        config = Config()
        config.set("first_launch", True)
        dialog = FirstLaunchDialog(None, config)
        mock_slot = MagicMock()
        dialog.go_to_settings.connect(mock_slot)
        dialog._on_setup_own()
        mock_slot.assert_called_once()

    def test_use_builtin_clears_api_key(self, qtbot):
        """点击'用开发者的 API'应清空用户 API Key"""
        from gui.first_launch import FirstLaunchDialog
        from config import Config
        config = Config()
        config.set("first_launch", True)
        config.set("ai_user_api_key", "test-key")
        dialog = FirstLaunchDialog(None, config)
        dialog._on_use_builtin()
        assert config.get("ai_user_api_key") == ""

    def test_finish_sets_first_launch_false(self, qtbot):
        """_finish() 应设置 first_launch=False"""
        from gui.first_launch import FirstLaunchDialog
        from config import Config
        config = Config()
        config.set("first_launch", True)
        dialog = FirstLaunchDialog(None, config)
        dialog._finish()
        assert config.get("first_launch") is False
