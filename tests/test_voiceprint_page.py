#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 音色库管理页面单元测试
"""

import pytest
from unittest.mock import MagicMock, patch


class TestVoiceprintPage:
    """VoiceprintPage 类测试"""

    def test_import(self):
        """测试导入"""
        from gui.voiceprint_page import VoiceprintPage
        assert VoiceprintPage is not None

    def test_class_exists(self):
        """测试类存在"""
        from gui.voiceprint_page import VoiceprintPage
        assert hasattr(VoiceprintPage, '__init__')

    def test_has_required_methods(self):
        """测试必需的方法存在"""
        from gui.voiceprint_page import VoiceprintPage
        assert hasattr(VoiceprintPage, 'refresh_list')
        assert hasattr(VoiceprintPage, '_add_speaker')
        assert hasattr(VoiceprintPage, '_edit_speaker')
        assert hasattr(VoiceprintPage, '_delete_speaker')


class TestAddVoiceDialog:
    """AddVoiceDialog 类测试"""

    def test_import(self):
        """测试导入"""
        from gui.voiceprint_page import AddVoiceDialog
        assert AddVoiceDialog is not None

    def test_class_exists(self):
        """测试类存在"""
        from gui.voiceprint_page import AddVoiceDialog
        assert hasattr(AddVoiceDialog, '__init__')

    def test_has_preset_text(self):
        """测试预设文本存在"""
        from gui.voiceprint_page import AddVoiceDialog
        assert hasattr(AddVoiceDialog, 'PRESET_TEXT')
        assert isinstance(AddVoiceDialog.PRESET_TEXT, str)
        assert "声纹样本" in AddVoiceDialog.PRESET_TEXT

    def test_has_required_methods(self):
        """测试必需的方法存在"""
        from gui.voiceprint_page import AddVoiceDialog
        assert hasattr(AddVoiceDialog, '_start_recording')
        assert hasattr(AddVoiceDialog, '_stop_recording')
        assert hasattr(AddVoiceDialog, '_save')
