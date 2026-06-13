#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SettingsPage 引擎参数 & 模型管理功能测试
"""

import os
import tempfile
import sys
import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config


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


class TestSettingsPageInstantiation:
    """SettingsPage 可以实例化"""

    def test_instantiate(self, config, app):
        page = _create_settings_page(config)
        assert page is not None
        assert hasattr(page, '_config')
        assert hasattr(page, '_model_manager')


class TestEngineComboBoxes:
    """引擎参数 ComboBox 存在且有正确选项"""

    def test_punc_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_punc_var')
        assert page._punc_var.count() == 2

    def test_punc_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._punc_var.itemText(i) for i in range(page._punc_var.count())]
        assert "自动 (ct-punc)" in options
        assert "关闭" in options

    def test_garble_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_garble_var')
        assert page._garble_var.count() == 2

    def test_garble_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._garble_var.itemText(i) for i in range(page._garble_var.count())]
        assert "开启 (中文模式)" in options
        assert "关闭" in options

    def test_vad_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_vad_var')
        assert page._vad_var.count() == 3

    def test_vad_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._vad_var.itemText(i) for i in range(page._vad_var.count())]
        assert "适中 (推荐)" in options
        assert "高 (更多分段)" in options
        assert "低 (更少分段)" in options

    def test_device_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_device_var')
        assert page._device_var.count() == 2

    def test_device_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._device_var.itemText(i) for i in range(page._device_var.count())]
        assert "CPU" in options
        assert "CUDA (GPU)" in options


class TestModelManager:
    """ModelManager 实例被创建"""

    def test_model_manager_created(self, config, app):
        page = _create_settings_page(config)
        assert page._model_manager is not None

    def test_model_manager_has_required_methods(self, config, app):
        page = _create_settings_page(config)
        mm = page._model_manager
        assert hasattr(mm, 'check_all_models')
        assert hasattr(mm, 'get_missing_models')
        assert hasattr(mm, 'download_all_missing')


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


class TestModelManagement:
    """模型管理按钮和状态"""

    def test_check_button_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_btn_check_models')

    def test_download_button_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_btn_download_models')

    def test_model_status_frame_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_model_status_frame')

    def test_model_status_label_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_model_status_label')
