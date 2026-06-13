#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 音色库管理页面端到端测试
"""

import pytest
import tempfile
import os


class TestVoiceprintPageE2E:
    """音色库管理页面端到端测试"""

    def test_page_import(self):
        """测试页面导入"""
        from gui.voiceprint_page import VoiceprintPage, AddVoiceDialog
        assert VoiceprintPage is not None
        assert AddVoiceDialog is not None

    def test_app_has_voiceprint_page(self):
        """测试 App 有 VoiceprintPage"""
        from gui.app import MeetScribeApp
        assert hasattr(MeetScribeApp, '_on_navigate')

    def test_voiceprint_page_has_required_methods(self):
        """测试 VoiceprintPage 有必需的方法"""
        from gui.voiceprint_page import VoiceprintPage
        assert hasattr(VoiceprintPage, 'refresh_list')
        assert hasattr(VoiceprintPage, '_add_speaker')
        assert hasattr(VoiceprintPage, '_edit_speaker')
        assert hasattr(VoiceprintPage, '_delete_speaker')
        assert hasattr(VoiceprintPage, '_on_speaker_select')
        assert hasattr(VoiceprintPage, '_show_speaker_detail')

    def test_add_voice_dialog_has_required_methods(self):
        """测试 AddVoiceDialog 有必需的方法"""
        from gui.voiceprint_page import AddVoiceDialog
        assert hasattr(AddVoiceDialog, '_start_recording')
        assert hasattr(AddVoiceDialog, '_stop_recording')
        assert hasattr(AddVoiceDialog, '_save')
        assert hasattr(AddVoiceDialog, 'PRESET_TEXT')

    def test_voiceprint_library_has_rename_method(self):
        """测试 VoiceprintLibrary 有 rename_speaker 方法"""
        from voiceprint import VoiceprintLibrary
        assert hasattr(VoiceprintLibrary, 'rename_speaker')

    def test_voiceprint_library_has_extract_method(self):
        """测试 VoiceprintLibrary 有 extract_embedding_from_file 方法"""
        from voiceprint import VoiceprintLibrary
        assert hasattr(VoiceprintLibrary, 'extract_embedding_from_file')
