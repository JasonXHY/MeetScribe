"""
TDD 测试：前端修复 9 项验证
F1-1: get_summary_path 多模式查找
F1-2: _preview_result 摘要等待提示
F2-3: worker spk_embeddings 发送
F2-4: _current_batch_paths 填充
F3-1: 两阶段匹配+冲突检测
F3-2: _apply_voiceprint_match
F4-1~F4-3: 按钮即时刷新
"""

import os
import sys
import time
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ══════════════════════════════════════════════════════════
#  F1-1: get_summary_path 多模式查找
# ══════════════════════════════════════════════════════════

class TestF1GetSummaryPath:
    """F1-1: get_summary_path 应支持多种命名模式"""

    def test_standard_pattern(self, tmp_path):
        """标准模式：{base}_transcript.md → {base}_summary.md"""
        from utils import get_summary_path
        transcript = tmp_path / "meeting_transcript.md"
        summary = tmp_path / "meeting_summary.md"
        transcript.write_text("content")
        summary.write_text("summary")
        result = get_summary_path(str(transcript))
        assert result == str(summary)

    def test_alternative_pattern(self, tmp_path):
        """备选模式：{base}_transcript.md → {base}_transcript_summary.md"""
        from utils import get_summary_path
        transcript = tmp_path / "meeting_transcript.md"
        summary = tmp_path / "meeting_transcript_summary.md"
        transcript.write_text("content")
        summary.write_text("summary")
        result = get_summary_path(str(transcript))
        assert result == str(summary)

    def test_no_transcript_suffix(self, tmp_path):
        """无 _transcript 后缀：{base}.md → {base}_summary.md"""
        from utils import get_summary_path
        transcript = tmp_path / "meeting.md"
        summary = tmp_path / "meeting_summary.md"
        transcript.write_text("content")
        summary.write_text("summary")
        result = get_summary_path(str(transcript))
        assert result == str(summary)

    def test_no_summary_exists(self, tmp_path):
        """摘要文件不存在时返回 None"""
        from utils import get_summary_path
        transcript = tmp_path / "meeting_transcript.md"
        transcript.write_text("content")
        result = get_summary_path(str(transcript))
        assert result is None

    def test_none_input(self):
        """输入 None 返回 None"""
        from utils import get_summary_path
        assert get_summary_path(None) is None

    def test_empty_string(self):
        """空字符串返回 None"""
        from utils import get_summary_path
        assert get_summary_path("") is None


# ══════════════════════════════════════════════════════════
#  F2-4: _current_batch_paths 填充
# ══════════════════════════════════════════════════════════

class TestF2CurrentBatchPaths:
    """F2-4: start() 应填充 _current_batch_paths"""

    def test_batch_paths_populated_on_start(self):
        """start() 调用后 _current_batch_paths 应包含文件路径"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        handler._current_batch_paths = set()

        # Mock multiprocessing.Process 避免实际启动
        with patch('gui.transcription.multiprocessing.Process'):
            handler.start(["file1.wav", "file2.wav"], "llm-md", {}, "")

        assert "file1.wav" in handler._current_batch_paths
        assert "file2.wav" in handler._current_batch_paths
        assert len(handler._current_batch_paths) == 2

    def test_batch_paths_empty_when_no_files(self):
        """空文件列表时 _current_batch_paths 也应更新"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        handler._current_batch_paths = set()

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start([], "llm-md", {}, "")

        assert handler._current_batch_paths == set()

    def test_batch_paths_cleared_on_new_batch(self):
        """新批次应覆盖旧的 _current_batch_paths"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start(["old.wav"], "llm-md", {}, "")
            assert "old.wav" in handler._current_batch_paths

            # 模拟转写完成
            handler._transcribing = False
            handler.start(["new.wav"], "llm-md", {}, "")
            assert "new.wav" in handler._current_batch_paths
            assert "old.wav" not in handler._current_batch_paths


# ══════════════════════════════════════════════════════════
#  F3-1: 两阶段匹配+冲突检测
# ══════════════════════════════════════════════════════════

class TestF3ConflictDetection:
    """F3-1: 多发言人匹配同一音色库成员时，只写入最高置信度"""

    def test_no_conflict_single_match(self):
        """无冲突：每个说话人匹配不同的人"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler
        from file_manager import FileStatus

        handler = TranscriptionHandler(app=None)
        handler._speaker_embeddings = {0: [0.1] * 192, 1: [0.2] * 192}
        handler._speaker_qualities = {}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "test_transcript.md"
        mock_item.file_path = "test.wav"
        mock_item.speaker_names = {}

        mock_fm = MagicMock()
        mock_fm.files = [mock_item]

        mock_app = MagicMock()
        mock_app.file_manager = mock_fm
        handler._app = mock_app

        mock_library = MagicMock()
        mock_library.match.side_effect = [
            ("张三", 0.8),   # Speaker 0
            ("李四", 0.7),   # Speaker 1
        ]

        with patch('voiceprint.VoiceprintLibrary', return_value=mock_library):
            with patch('gui.transcription.apply_speaker_mapping'):
                with patch('gui.transcription.get_summary_path', return_value=None):
                    handler._match_voiceprints()

        assert mock_fm.update_speaker_names.call_count == 2

    def test_conflict_keeps_highest_score(self):
        """冲突：两个说话人匹配同一人，只保留最高分数的"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler
        from file_manager import FileStatus

        handler = TranscriptionHandler(app=None)
        handler._speaker_embeddings = {0: [0.1] * 192, 1: [0.2] * 192}
        handler._speaker_qualities = {}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "test_transcript.md"
        mock_item.file_path = "test.wav"
        mock_item.speaker_names = {}

        mock_fm = MagicMock()
        mock_fm.files = [mock_item]

        mock_app = MagicMock()
        mock_app.file_manager = mock_fm
        handler._app = mock_app

        mock_library = MagicMock()
        mock_library.match.side_effect = [
            ("张三", 0.8),
            ("张三", 0.6),
        ]

        with patch('voiceprint.VoiceprintLibrary', return_value=mock_library):
            with patch('gui.transcription.apply_speaker_mapping'):
                with patch('gui.transcription.get_summary_path', return_value=None):
                    handler._match_voiceprints()

        assert mock_fm.update_speaker_names.call_count == 1
        call_args = mock_fm.update_speaker_names.call_args
        mapping = call_args[0][1]
        assert mapping.get("1") == "张三"

    def test_no_match_when_below_threshold(self):
        """所有匹配分数低于阈值时不写入"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler
        from file_manager import FileStatus

        handler = TranscriptionHandler(app=None)
        handler._speaker_embeddings = {0: [0.1] * 192}
        handler._speaker_qualities = {}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "test_transcript.md"
        mock_item.file_path = "test.wav"

        mock_fm = MagicMock()
        mock_fm.files = [mock_item]

        mock_app = MagicMock()
        mock_app.file_manager = mock_fm
        handler._app = mock_app

        mock_library = MagicMock()
        mock_library.match.return_value = (None, 0)

        with patch('voiceprint.VoiceprintLibrary', return_value=mock_library):
            handler._match_voiceprints()

        assert mock_fm.update_speaker_names.call_count == 0


# ══════════════════════════════════════════════════════════
#  F4: 按钮即时刷新
# ══════════════════════════════════════════════════════════

class TestF4ButtonRefresh:
    """F4-1~F4-3: 转写按钮点击后应立即刷新文件列表"""

    def test_transcribe_single_refreshes(self, qtbot):
        """_transcribe_single 应调用 refresh_file_list"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.is_transcribing = False
        mock_handler.start = MagicMock()
        test_app._transcription_handler = mock_handler

        # Mock refresh
        test_app._home_page.refresh_file_list = MagicMock()

        # Mock get_selected_format
        test_app._home_page.get_selected_format = MagicMock(return_value="llm-md")

        # Mock QMessageBox
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information = staticmethod(lambda *a, **k: None)

        # 调用
        test_app._home_page._transcribe_single("test.wav")

        # 验证 refresh 被调用
        test_app._home_page.refresh_file_list.assert_called_once()
        # 验证 handler.start 被调用
        mock_handler.start.assert_called_once()

        test_app.close()

    def test_start_transcription_refreshes(self, qtbot):
        """_start_transcription 应调用 refresh_file_list"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.is_transcribing = False
        mock_handler.start = MagicMock()
        test_app._transcription_handler = mock_handler

        # Mock file_manager
        mock_pending = MagicMock()
        mock_pending.file_path = "test.wav"
        test_app.file_manager.get_pending_files = MagicMock(return_value=[mock_pending])

        # Mock refresh
        test_app._home_page.refresh_file_list = MagicMock()
        test_app._home_page.get_selected_format = MagicMock(return_value="llm-md")

        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information = staticmethod(lambda *a, **k: None)

        test_app._home_page._start_transcription()

        test_app._home_page.refresh_file_list.assert_called()
        test_app.close()


# ══════════════════════════════════════════════════════════
#  F1-2: _preview_result 摘要等待提示
# ══════════════════════════════════════════════════════════

class TestF1PreviewResult:
    """F1-2: 摘要文件不存在且刚转写完时应提示等待"""

    def test_shows_hint_when_summary_missing_and_recent(self, qtbot, tmp_path):
        """摘要不存在且文件刚修改（60秒内）时应显示提示"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        # 创建测试文件
        transcript = tmp_path / "test_transcript.md"
        transcript.write_text("content")

        # Mock file_manager
        mock_item = MagicMock()
        mock_item.file_name = "test.wav"
        mock_item.result_path = str(transcript)

        mock_fm = MagicMock()
        mock_fm.get_file = MagicMock(return_value=mock_item)
        test_app.file_manager = mock_fm

        # Mock QMessageBox
        from PySide6.QtWidgets import QMessageBox
        hint_shown = []
        def mock_info(parent, title, msg):
            hint_shown.append(msg)
        QMessageBox.information = staticmethod(mock_info)

        # Mock get_summary_path — it's imported inside _preview_result with `from utils import get_summary_path`
        with patch('utils.get_summary_path', return_value=None):
            test_app._home_page._preview_result("test.wav")

        # 应显示等待提示
        assert len(hint_shown) > 0
        assert "摘要" in hint_shown[0] or "生成" in hint_shown[0]

        test_app.close()

    def test_opens_dialog_when_summary_exists(self, qtbot, tmp_path):
        """摘要存在时应正常打开预览对话框"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        # 创建测试文件
        transcript = tmp_path / "test_transcript.md"
        transcript.write_text("content")
        summary = tmp_path / "test_summary.md"
        summary.write_text("summary")

        mock_item = MagicMock()
        mock_item.file_name = "test.wav"
        mock_item.result_path = str(transcript)

        mock_fm = MagicMock()
        mock_fm.get_file = MagicMock(return_value=mock_item)
        test_app.file_manager = mock_fm

        # Mock PreviewDialog and get_summary_path — imported inside _preview_result
        with patch('utils.get_summary_path', return_value=str(summary)):
            with patch('gui.dialogs.PreviewDialog') as MockDialog:
                mock_dialog = MagicMock()
                MockDialog.return_value = mock_dialog
                test_app._home_page._preview_result("test.wav")
                mock_dialog.exec.assert_called_once()

        test_app.close()
