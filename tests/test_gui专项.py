"""
GUI 专项测试

测试 PySide6 GUI 组件的基本功能
"""

import sys
import os
import pytest

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestGUIImports:
    """测试 GUI 模块导入"""

    def test_styles_import(self):
        from gui.styles import C_BG, C_CARD, C_ACCENT, FONT_FAMILY, MAIN_STYLESHEET
        assert C_BG is not None
        assert C_CARD is not None
        assert C_ACCENT is not None
        assert FONT_FAMILY is not None
        assert MAIN_STYLESHEET is not None

    def test_app_import(self):
        from gui.app import MeetScribeApp, GUILogHandler
        assert MeetScribeApp is not None
        assert GUILogHandler is not None

    def test_dialogs_import(self):
        from gui.dialogs import (
            PreviewDialog, ExportDialog, SpeakerDialog,
            MergeOrderDialog, parse_speakers_from_result
        )
        assert PreviewDialog is not None
        assert ExportDialog is not None
        assert SpeakerDialog is not None
        assert MergeOrderDialog is not None
        assert parse_speakers_from_result is not None

    def test_transcription_import(self):
        from gui.transcription import TranscriptionHandler
        assert TranscriptionHandler is not None

    def test_home_page_import(self):
        from gui.home_page import HomePage
        assert HomePage is not None

    def test_settings_page_import(self):
        from gui.settings_page import SettingsPage
        assert SettingsPage is not None

    def test_voiceprint_page_import(self):
        from gui.voiceprint_page import VoiceprintPage
        assert VoiceprintPage is not None

    def test_file_list_view_import(self):
        from gui.file_list_view import FileListView
        assert FileListView is not None

    def test_recording_bar_import(self):
        from gui.recording_bar import RecordingBar
        assert RecordingBar is not None

    def test_topbar_import(self):
        from gui.topbar import TopBar
        assert TopBar is not None


class TestGUIComponents:
    """测试 GUI 组件创建"""

    def test_styles_constants(self):
        from gui.styles import (
            C_BG, C_CARD, C_BORDER, C_ACCENT, C_TXT1, C_TXT2, C_TXT3,
            SPEAKER_COLORS, ICON_STATUS, ICON_ACTION, OUTPUT_FORMATS
        )
        # 颜色常量
        assert C_BG.startswith("#")
        assert C_CARD.startswith("#")
        assert C_BORDER.startswith("#")
        assert C_ACCENT.startswith("#")

        # 列表常量
        assert len(SPEAKER_COLORS) > 0
        assert len(ICON_STATUS) > 0
        assert len(ICON_ACTION) > 0
        assert len(OUTPUT_FORMATS) > 0

    def test_speaker_colors_count(self):
        from gui.styles import SPEAKER_COLORS
        assert len(SPEAKER_COLORS) >= 10

    def test_output_formats(self):
        from gui.styles import OUTPUT_FORMATS
        assert "md" in OUTPUT_FORMATS.values()
        assert "txt" in OUTPUT_FORMATS.values()
        assert "srt" in OUTPUT_FORMATS.values()
        assert "json" in OUTPUT_FORMATS.values()


class TestParseSpeakers:
    """测试说话人解析函数"""

    def test_parse_speakers_from_result(self):
        from gui.dialogs import parse_speakers_from_result
        import tempfile
        import os

        # 创建测试文件
        content = """
**[00:00] Speaker 1**: 你好
**[00:05] Speaker 2**: 大家好
**[00:10] Speaker 1**: 今天开会
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            speakers = parse_speakers_from_result(temp_path)
            assert len(speakers) == 2
            assert speakers[0]['label'] == 'Speaker 1'
            assert speakers[1]['label'] == 'Speaker 2'
        finally:
            os.remove(temp_path)

    def test_parse_speakers_empty_file(self):
        from gui.dialogs import parse_speakers_from_result
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("没有说话人信息")
            temp_path = f.name

        try:
            speakers = parse_speakers_from_result(temp_path)
            assert len(speakers) == 0
        finally:
            os.remove(temp_path)

    def test_parse_speakers_with_saved_names(self):
        from gui.dialogs import parse_speakers_from_result
        import tempfile
        import os

        content = """
**[00:00] Speaker 1**: 你好
**[00:05] Speaker 2**: 大家好
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            saved_names = {"1": "张三", "2": "李四"}
            speakers = parse_speakers_from_result(temp_path, saved_names)
            assert len(speakers) == 2
            assert speakers[0]['name'] == '张三'
            assert speakers[1]['name'] == '李四'
        finally:
            os.remove(temp_path)


class TestTranscriptionHandler:
    """测试转写调度器"""

    def test_handler_creation(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        assert handler is not None
        assert handler.is_transcribing is False

    def test_queue_operations(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)

        # 添加到队列
        handler.add_to_queue(["file1.wav", "file2.wav"])
        assert len(handler.get_queue()) == 2

        # 获取队列位置
        assert handler.get_queue_position("file1.wav") == 1
        assert handler.get_queue_position("file2.wav") == 2
        assert handler.get_queue_position("file3.wav") == 0

        # 移除
        handler.remove_from_queue("file1.wav")
        assert len(handler.get_queue()) == 1

        # 队列状态文本
        status = handler.get_queue_status_text()
        assert "1 个文件" in status

    def test_queue_move(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)

        handler.add_to_queue(["file1.wav", "file2.wav", "file3.wav"])

        # 上移
        handler.move_up_in_queue("file2.wav")
        assert handler.get_queue()[0] == "file2.wav"

        # 下移
        handler.move_down_in_queue("file2.wav")
        assert handler.get_queue()[1] == "file2.wav"
