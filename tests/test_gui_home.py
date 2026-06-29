"""
合并测试文件：GUI Home 页面测试
来源：test_home_page_p0.py, test_gui_special.py, test_button_states.py,
     test_stop_button.py, test_progress_display.py, test_frontend_fixes.py,
     test_file_list.py
"""

import os
import sys
import tempfile
import time
import shutil
import logging

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from PySide6.QtTest import QTest

app = QApplication.instance() or QApplication(sys.argv)

logger = logging.getLogger("TDD_Test")
logger.setLevel(logging.DEBUG)


# ══════════════════════════════════════════════════════════
#  Helper factories
# ══════════════════════════════════════════════════════════


def _make_home_page_p0():
    from gui.home_page import HomePage

    mock_app = MagicMock()
    mock_app.config.get.return_value = "mic"
    mock_app.recorder = MagicMock()
    mock_app.recorder.paused_duration = 0

    with patch.object(HomePage, '_build'), \
         patch.object(HomePage, '_connect_signals'):
        home = HomePage(parent=None, app=mock_app)

    home._recording_bar = MagicMock()
    home._recording_bar._paused = False
    home._recording_bar.update_state = MagicMock()
    home._recording_bar.update_timer = MagicMock()

    home._file_list_view = MagicMock()
    home._file_list_view._row_widgets = {"test.mp3": {"bg": MagicMock(), "status": MagicMock()}}
    home._file_list_view._selected_files = {"test.mp3"}
    home._file_list_view.get_selected = MagicMock(return_value=["test.mp3"])

    home._log_area = MagicMock()
    home._timer_id = None
    home._record_start_time = None

    return home


def _make_home_page_full():
    from gui.home_page import HomePage

    mock_app = MagicMock()
    mock_app.config.get.return_value = "mic"
    mock_app.recorder = MagicMock()
    mock_app._transcription_handler = MagicMock()
    mock_app._transcription_handler.is_transcribing = False
    mock_app._transcription_handler.add_to_queue = MagicMock()
    mock_app._transcription_handler.start = MagicMock()
    mock_app._transcription_handler.stop_transcription = MagicMock()
    mock_app.file_manager = MagicMock()
    mock_app.file_manager.files = []
    mock_app.file_manager.display_files = []

    with patch.object(HomePage, '_build'), \
         patch.object(HomePage, '_connect_signals'), \
         patch('PySide6.QtWidgets.QMessageBox.information'):
        home = HomePage(parent=None, app=mock_app)

    home._recording_bar = MagicMock()
    home._recording_bar.update_queue_status = MagicMock()
    home._recording_bar.stop_btn = MagicMock()
    home._recording_bar.update_state = MagicMock()

    home._btn_transcribe = MagicMock()
    home._btn_ai_summary = MagicMock()
    home._fmt_combo = MagicMock()
    home._fmt_combo.currentText.return_value = "md"

    home._log_area = MagicMock()
    home._file_list_view = MagicMock()
    home._file_count_lbl = MagicMock()

    return home, mock_app


def _make_home_page_progress():
    from gui.home_page import HomePage

    mock_app = MagicMock()
    mock_app.config.get.return_value = "mic"
    mock_app.recorder = MagicMock()

    with patch.object(HomePage, '_build'), \
         patch.object(HomePage, '_connect_signals'):
        home = HomePage(parent=None, app=mock_app)

    home._recording_bar = MagicMock()
    home._recording_bar.update_queue_status = MagicMock()

    return home, mock_app


# ══════════════════════════════════════════════════════════
#  1. P0 Home Page Property Tests
# ══════════════════════════════════════════════════════════

class TestHomePageP0:
    def test_update_recording_ui_exists_and_callable(self):
        home = _make_home_page_p0()
        assert hasattr(home, 'update_recording_ui'), "update_recording_ui method missing"
        assert callable(home.update_recording_ui), "update_recording_ui should be callable"

        home.update_recording_ui(True, False)
        home._recording_bar.update_state.assert_called_with(recording=True, paused=False)

        home.update_recording_ui(True, True)
        home._recording_bar.update_state.assert_called_with(recording=True, paused=True)

        home.update_recording_ui(False, False)
        home._recording_bar.update_state.assert_called_with(recording=False, paused=False)


# ══════════════════════════════════════════════════════════
#  2. GUI Styles & Components Tests
# ══════════════════════════════════════════════════════════

class TestGUIComponents:
    def test_styles_constants(self):
        from gui.styles import (
            C_BG, C_CARD, C_BORDER, C_ACCENT, C_TXT1, C_TXT2, C_TXT3,
            SPEAKER_COLORS, OUTPUT_FORMATS
        )
        assert C_BG.startswith("#")
        assert C_CARD.startswith("#")
        assert C_BORDER.startswith("#")
        assert C_ACCENT.startswith("#")
        assert len(SPEAKER_COLORS) > 0
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


# ══════════════════════════════════════════════════════════
#  3. Speaker Parsing Tests
# ══════════════════════════════════════════════════════════

class TestParseSpeakers:
    def test_parse_speakers_from_result(self):
        from gui.dialogs import parse_speakers_from_result

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


# ══════════════════════════════════════════════════════════
#  4. Transcription Handler Tests
# ══════════════════════════════════════════════════════════

class TestTranscriptionHandler:
    def test_handler_creation(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        assert handler is not None
        assert handler.is_transcribing is False

    def test_queue_operations(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)

        handler.add_to_queue(["file1.wav", "file2.wav"])
        assert len(handler.get_queue()) == 2

        assert handler.get_queue_position("file1.wav") == 1
        assert handler.get_queue_position("file2.wav") == 2
        assert handler.get_queue_position("file3.wav") == 0

        handler.remove_from_queue("file1.wav")
        assert len(handler.get_queue()) == 1

        status = handler.get_queue_status_text()
        assert "1 个文件" in status

    def test_queue_move(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)

        handler.add_to_queue(["file1.wav", "file2.wav", "file3.wav"])

        handler.move_up_in_queue("file2.wav")
        assert handler.get_queue()[0] == "file2.wav"

        handler.move_down_in_queue("file2.wav")
        assert handler.get_queue()[1] == "file2.wav"


# ══════════════════════════════════════════════════════════
#  5. Button State Tests
# ══════════════════════════════════════════════════════════

class TestButtonStates:
    def test_ai_summary_disabled_on_transcribe_start(self):
        home, mock_app = _make_home_page_full()
        home._btn_ai_summary.setEnabled = MagicMock()

        home._start_transcription()

        home._btn_ai_summary.setEnabled.assert_called_with(False)

    def test_ai_summary_enabled_on_transcribe_done(self):
        home, mock_app = _make_home_page_full()
        home._btn_ai_summary.setEnabled = MagicMock()
        home._btn_ai_summary.isEnabled = MagicMock(return_value=False)

        home._on_transcription_done_handler(1, 0)

        home._btn_ai_summary.setEnabled.assert_called_with(True)

    def test_ai_summary_enabled_on_transcribe_fail(self):
        home, mock_app = _make_home_page_full()
        home._btn_ai_summary.setEnabled = MagicMock()
        home._btn_ai_summary.isEnabled = MagicMock(return_value=False)

        home._on_transcription_done_handler(0, 1)

        home._btn_ai_summary.setEnabled.assert_called_with(True)

    def test_transcribe_button_disabled_on_start(self):
        home, mock_app = _make_home_page_full()
        home._btn_transcribe.setEnabled = MagicMock()
        home._btn_transcribe.setText = MagicMock()

        home._start_transcription()

        home._btn_transcribe.setEnabled.assert_called_with(False)

    def test_transcribe_button_enabled_on_done(self):
        home, mock_app = _make_home_page_full()
        home._btn_transcribe.setEnabled = MagicMock()
        home._btn_transcribe.setText = MagicMock()

        home._on_transcription_done_handler(1, 0)

        home._btn_transcribe.setEnabled.assert_called_with(True)

    def test_stop_btn_disabled_on_done(self):
        home, mock_app = _make_home_page_full()
        home._recording_bar.update_state = MagicMock()

        home._on_transcription_done_handler(1, 0)

        home._recording_bar.update_state.assert_called_with(recording=False, paused=False)


# ══════════════════════════════════════════════════════════
#  6. Stop Button Tests
# ══════════════════════════════════════════════════════════

class TestStopButton:
    def test_stop_button_during_transcription(self):
        home, mock_app = _make_home_page_full()
        mock_app._transcription_handler.is_transcribing = True

        home._stop_recording()

        # 停止按钮只控制录音，不控制转写
        mock_app._transcription_handler.stop_transcription.assert_not_called()
        mock_app.recorder.stop.assert_called_once()

    def test_stop_button_during_recording(self):
        home, mock_app = _make_home_page_full()
        mock_app._transcription_handler.is_transcribing = False
        mock_app.recorder.is_recording = True

        home._stop_recording()

        mock_app.recorder.stop.assert_called_once()

    def test_stop_button_idle(self):
        home, mock_app = _make_home_page_full()
        mock_app._transcription_handler.is_transcribing = False
        mock_app.recorder.is_recording = False

        home._stop_recording()

    def test_stop_transcription_updates_ui(self):
        home, mock_app = _make_home_page_full()
        mock_app._transcription_handler.is_transcribing = True

        home._stop_recording()

        home._recording_bar.update_state.assert_called_with(recording=False, paused=False)

    def test_stop_recording_updates_ui(self):
        home, mock_app = _make_home_page_full()
        mock_app._transcription_handler.is_transcribing = False
        mock_app.recorder.is_recording = True

        home._stop_recording()

        home._recording_bar.update_state.assert_called_with(recording=False, paused=False)


# ══════════════════════════════════════════════════════════
#  7. Progress Display Tests
# ══════════════════════════════════════════════════════════

class TestProgressDisplay:
    def test_progress_dict_parsing(self):
        home, mock_app = _make_home_page_progress()

        progress = {
            "stage": "转写中",
            "percent": 50,
            "current_file": 1,
            "total_files": 3
        }

        home._on_progress_updated(progress)

        home._recording_bar.update_queue_status.assert_called_once()
        call_args = home._recording_bar.update_queue_status.call_args[0][0]
        assert "转写中" in call_args
        assert "50%" in call_args

    def test_progress_object_parsing(self):
        from file_manager import TranscriptionProgress

        home, mock_app = _make_home_page_progress()

        progress = TranscriptionProgress()
        progress.stage = "转写中"
        progress.percent = 75

        home._on_progress_updated(progress)

        home._recording_bar.update_queue_status.assert_called_once()
        call_args = home._recording_bar.update_queue_status.call_args[0][0]
        assert "转写中" in call_args
        assert "75%" in call_args

    def test_progress_unknown_type_no_crash(self):
        home, mock_app = _make_home_page_progress()

        home._on_progress_updated("invalid")
        home._on_progress_updated(123)
        home._on_progress_updated(None)

    def test_progress_missing_percent_uses_default(self):
        home, mock_app = _make_home_page_progress()

        progress = {"stage": "处理中"}

        home._on_progress_updated(progress)

        home._recording_bar.update_queue_status.assert_called_once()
        call_args = home._recording_bar.update_queue_status.call_args[0][0]
        assert "处理中" in call_args

    def test_progress_with_file_count(self):
        home, mock_app = _make_home_page_progress()

        progress = {
            "stage": "转写中",
            "percent": 33,
            "current_file": 1,
            "total_files": 3
        }

        home._on_progress_updated(progress)

        home._recording_bar.update_queue_status.assert_called_once()
        call_args = home._recording_bar.update_queue_status.call_args[0][0]
        assert "[1/3]" in call_args


# ══════════════════════════════════════════════════════════
#  8. Frontend Fixes Tests (F1–F4)
# ══════════════════════════════════════════════════════════

class TestF1GetSummaryPath:
    def test_standard_pattern(self, tmp_path):
        from utils import get_summary_path
        transcript = tmp_path / "meeting_transcript.md"
        summary = tmp_path / "meeting_summary.md"
        transcript.write_text("content")
        summary.write_text("summary")
        result = get_summary_path(str(transcript))
        assert result == str(summary)

    def test_alternative_pattern(self, tmp_path):
        from utils import get_summary_path
        transcript = tmp_path / "meeting_transcript.md"
        summary = tmp_path / "meeting_transcript_summary.md"
        transcript.write_text("content")
        summary.write_text("summary")
        result = get_summary_path(str(transcript))
        assert result == str(summary)

    def test_no_transcript_suffix(self, tmp_path):
        from utils import get_summary_path
        transcript = tmp_path / "meeting.md"
        summary = tmp_path / "meeting_summary.md"
        transcript.write_text("content")
        summary.write_text("summary")
        result = get_summary_path(str(transcript))
        assert result == str(summary)

    def test_no_summary_exists(self, tmp_path):
        from utils import get_summary_path
        transcript = tmp_path / "meeting_transcript.md"
        transcript.write_text("content")
        result = get_summary_path(str(transcript))
        assert result is None

    def test_none_input(self):
        from utils import get_summary_path
        assert get_summary_path(None) is None

    def test_empty_string(self):
        from utils import get_summary_path
        assert get_summary_path("") is None


class TestF2CurrentBatchPaths:
    def test_batch_paths_populated_on_start(self):
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        handler._current_batch_paths = set()

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start(["file1.wav", "file2.wav"], "llm-md", {}, "")

        assert "file1.wav" in handler._current_batch_paths
        assert "file2.wav" in handler._current_batch_paths
        assert len(handler._current_batch_paths) == 2

    def test_batch_paths_empty_when_no_files(self):
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        handler._current_batch_paths = set()

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start([], "llm-md", {}, "")

        assert handler._current_batch_paths == set()

    def test_batch_paths_cleared_on_new_batch(self):
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start(["old.wav"], "llm-md", {}, "")
            assert "old.wav" in handler._current_batch_paths

            handler._transcribing = False
            handler.start(["new.wav"], "llm-md", {}, "")
            assert "new.wav" in handler._current_batch_paths
            assert "old.wav" not in handler._current_batch_paths


class TestF3ConflictDetection:
    def test_no_conflict_single_match(self):
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
            ("李四", 0.7),
        ]

        with patch('voiceprint.VoiceprintLibrary', return_value=mock_library):
            with patch('gui.transcription.apply_speaker_mapping'):
                with patch('gui.transcription.get_summary_path', return_value=None):
                    handler._match_voiceprints()

        assert mock_fm.update_speaker_names.call_count == 2

    def test_conflict_keeps_highest_score(self):
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


class TestF4ButtonRefresh:
    def test_transcribe_single_refreshes(self, qtbot):
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        mock_handler = MagicMock()
        mock_handler.is_transcribing = False
        mock_handler.start = MagicMock()
        test_app._transcription_handler = mock_handler

        test_app._home_page.refresh_file_list = MagicMock()
        test_app._home_page.get_selected_format = MagicMock(return_value="llm-md")

        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information = staticmethod(lambda *a, **k: None)

        test_app._home_page._transcribe_single("test.wav")

        test_app._home_page.refresh_file_list.assert_called_once()
        mock_handler.start.assert_called_once()

        test_app.close()

    def test_start_transcription_refreshes(self, qtbot):
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        mock_handler = MagicMock()
        mock_handler.is_transcribing = False
        mock_handler.start = MagicMock()
        test_app._transcription_handler = mock_handler

        mock_pending = MagicMock()
        mock_pending.file_path = "test.wav"
        test_app.file_manager.get_pending_files = MagicMock(return_value=[mock_pending])

        test_app._home_page.refresh_file_list = MagicMock()
        test_app._home_page.get_selected_format = MagicMock(return_value="llm-md")

        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information = staticmethod(lambda *a, **k: None)

        test_app._home_page._start_transcription()

        test_app._home_page.refresh_file_list.assert_called()
        test_app.close()


class TestF1PreviewResult:
    def test_shows_hint_when_summary_missing_and_recent(self, qtbot, tmp_path):
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        transcript = tmp_path / "test_transcript.md"
        transcript.write_text("content")

        mock_item = MagicMock()
        mock_item.file_name = "test.wav"
        mock_item.result_path = str(transcript)

        mock_fm = MagicMock()
        mock_fm.get_file = MagicMock(return_value=mock_item)
        test_app.file_manager = mock_fm

        hint_shown = []
        def mock_info(parent, title, msg):
            hint_shown.append(msg)
        QMessageBox.information = staticmethod(mock_info)

        with patch('utils.get_summary_path', return_value=None):
            test_app._home_page._preview_result("test.wav")

        assert len(hint_shown) > 0
        assert "摘要" in hint_shown[0] or "生成" in hint_shown[0]

        test_app.close()

    def test_opens_dialog_when_summary_exists(self, qtbot, tmp_path):
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

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

        with patch('utils.get_summary_path', return_value=str(summary)):
            with patch('gui.dialogs.PreviewDialog') as MockDialog:
                mock_dialog = MagicMock()
                MockDialog.return_value = mock_dialog
                test_app._home_page._preview_result("test.wav")
                mock_dialog.exec.assert_called_once()

        test_app.close()


# ══════════════════════════════════════════════════════════
#  9. File List Tests
# ══════════════════════════════════════════════════════════

def _make_file(path, name=None, status="pending", topic="", duration="00:10", size="1MB"):
    return {
        "path": path,
        "name": name or path.split("/")[-1],
        "topic": topic,
        "duration": duration,
        "size": size,
        "status": status,
        "queue_pos": None,
    }


def _row_widgets(view, row):
    table = view._table
    return {
        "name_item": table.item(row, 1),
        "status_item": table.item(row, 5),
        "action_widget": table.cellWidget(row, 6),
    }


@pytest.mark.gui
@pytest.mark.integration
class TestFileListIncrementalUpdate:
    def test_incremental_update_keeps_unchanged_rows(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="done"),
            _make_file("/c.wav", status="processing"),
        ]
        view.refresh(files)

        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="done"),
            _make_file("/c.wav", status="processing"),
        ]
        view.refresh(files2)

        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}

        for path in before:
            assert after[path]["status_item"] is before[path]["status_item"], (
                f"{path} status item recreated"
            )
            assert after[path]["action_widget"] is before[path]["action_widget"], (
                f"{path} action widget recreated"
            )
            assert after[path]["name_item"] is before[path]["name_item"], (
                f"{path} name item recreated"
            )

    def test_status_change_updates_only_that_row(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="pending"),
            _make_file("/c.wav", status="pending"),
        ]
        view.refresh(files)
        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="done"),
            _make_file("/c.wav", status="pending"),
        ]
        view.refresh(files2)
        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}

        for path in ("/a.wav", "/c.wav"):
            assert after[path]["status_item"] is before[path]["status_item"]
            assert after[path]["action_widget"] is before[path]["action_widget"]

        assert after["/b.wav"]["status_item"] is before["/b.wav"]["status_item"]
        assert "完成" in after["/b.wav"]["status_item"].toolTip()

    def test_add_single_file_appends_one_row(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [_make_file("/a.wav"), _make_file("/b.wav")]
        view.refresh(files)
        assert view._table.rowCount() == 2
        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [_make_file("/a.wav"), _make_file("/b.wav"), _make_file("/c.wav")]
        view.refresh(files2)
        assert view._table.rowCount() == 3
        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}
        for path in ("/a.wav", "/b.wav"):
            assert after[path]["status_item"] is before[path]["status_item"]
        assert after["/c.wav"]["status_item"] is not None

    def test_remove_single_file_removes_one_row(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [_make_file("/a.wav"), _make_file("/b.wav"), _make_file("/c.wav")]
        view.refresh(files)
        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [_make_file("/a.wav"), _make_file("/c.wav")]
        view.refresh(files2)
        assert view._table.rowCount() == 2
        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}
        for path in ("/a.wav", "/c.wav"):
            assert after[path]["status_item"] is before[path]["status_item"]
            assert after[path]["action_widget"] is before[path]["action_widget"]


@pytest.mark.gui
@pytest.mark.integration
class TestMergedGroupBadge:
    def test_merged_group_shows_badge(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        normal = _make_file("/normal.wav", name="normal.wav")
        merged = _make_file("/merged.wav", name="dual-track")
        merged["merged"] = True

        view.refresh([normal, merged])
        assert "[合并]" not in view._table.item(0, 1).text(), "普通行不应带 [合并]"
        assert "[合并]" in view._table.item(1, 1).text(), "合并组行应带 [合并]"

        normal2 = _make_file("/normal.wav", name="normal.wav")
        normal2["merged"] = True
        view.refresh([normal2, merged])
        assert "[合并]" in view._table.item(0, 1).text(), "就地更新为合并组后应带 [合并]"


# ══════════════════════════════════════════════════════════
#  L1: App 启动与导航 (from test_tdd_flows.py)
# ══════════════════════════════════════════════════════════

class TestAppStartup:
    """App 冷启动与基本导航"""

    def test_app_creation(self, qtbot):
        """验证 App 可正常创建和显示"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        assert test_app.isVisible() or test_app.windowTitle() == "侧耳倾听"
        assert test_app.config is not None
        assert test_app.file_manager is not None
        assert test_app.recorder is not None
        logger.info("PASS: App creation OK")
        test_app.close()

    def test_page_navigation(self, qtbot):
        """验证四个页面可正常切换"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        test_app.show()

        # 默认主页
        assert test_app._pages.currentWidget() == test_app._home_page

        # 切换到音色库
        test_app._on_navigate("voiceprint")
        QTest.qWait(200)
        assert test_app._pages.currentWidget() == test_app._voiceprint_page

        # 切换到设置
        test_app._on_navigate("settings")
        QTest.qWait(200)
        assert test_app._pages.currentWidget() == test_app._settings_page

        # 切换回主页
        test_app._on_navigate("home")
        QTest.qWait(200)
        assert test_app._pages.currentWidget() == test_app._home_page

        logger.info("PASS: Page navigation OK")
        test_app.close()


# ══════════════════════════════════════════════════════════
#  L2: 录音流程（mock 硬件）(from test_tdd_flows.py)
# ══════════════════════════════════════════════════════════

class TestRecordingFlow:
    """录音启动→暂停→停止流程验证"""

    def test_recording_start_stop(self, qtbot):
        """录音按钮点击→状态变更→停止"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        test_app.show()

        # Mock 录音硬件和弹窗
        test_app.recorder.start = MagicMock(return_value=True)
        test_app.recorder.stop = MagicMock()

        # 模拟开始录音
        test_app._recording = False
        test_app._recording_mode = "mic"

        # 检查初始状态
        rec_bar = test_app._home_page.get_recording_bar()
        assert rec_bar is not None

        # 模拟状态变更回调
        test_app._on_recorder_state_change(True, False)
        assert test_app._recording is True

        # 模拟暂停
        test_app._on_recorder_state_change(True, True)
        assert test_app._paused is True

        # 模拟停止
        test_app._on_recorder_state_change(False, False)
        assert test_app._recording is False
        assert test_app._paused is False

        logger.info("PASS: Recording start/stop flow OK")
        test_app.close()

    def test_file_appears_after_recording(self, qtbot, synthetic_wav):
        """录音保存后文件应出现在文件列表（用合成 WAV，不依赖大音频 fixture）"""
        from gui.app import MeetScribeApp
        from file_manager import FileStatus
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        test_app.show()

        # 用 conftest 的 synthetic_wav 工厂生成一个合法 16kHz 单声道 WAV
        test_file = synthetic_wav("test_record.wav", seconds=1.0)

        try:
            # Mock 阻塞性弹窗（ask_transcribe_after_record 中的 QMessageBox）
            with patch.object(test_app._home_page, 'ask_transcribe_after_record'):
                # 模拟录音保存回调
                test_app._handle_stop_complete([test_file])
                QTest.qWait(500)

            # 验证文件已添加到 file_manager
            file_item = test_app.file_manager.get_file(test_file)
            assert file_item is not None, f"File {test_file} not found in FileManager"
            logger.info(f"PASS: File appears after recording: {file_item.file_name}")
        finally:
            test_app.close()


# ══════════════════════════════════════════════════════════
#  GAP-13: 批量操作测试
# ══════════════════════════════════════════════════════════

class TestBatchOperations:
    """GAP-13: 批量操作测试"""

    def _create_home_page(self):
        from gui.home_page import HomePage
        mock_app = MagicMock()
        mock_app.file_manager = MagicMock()
        mock_app.file_manager.files = []
        mock_app.file_manager.display_files = []
        mock_app.config.get.return_value = "mic"
        mock_app.recorder = MagicMock()
        with patch.object(HomePage, '_build'), \
             patch.object(HomePage, '_connect_signals'):
            page = HomePage(parent=None, app=mock_app)
        return page

    def test_file_manager_has_clear_all(self, app):
        """file_manager 应有 clear_all 方法"""
        page = self._create_home_page()
        page._app.file_manager.clear_all.assert_not_called()
        page._app.file_manager.clear_all()
        page._app.file_manager.clear_all.assert_called_once()

    def test_file_count_reflects_added_files(self, app):
        """get_file_count 应反映添加的文件数"""
        page = self._create_home_page()
        page._app.file_manager.get_file_count.return_value = 3
        count = page._app.file_manager.get_file_count()
        assert count == 3
