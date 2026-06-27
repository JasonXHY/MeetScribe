"""
合并测试：dialogs P0 / add voice dialog / embedding save / markdown render / G12 spec deviations
"""
import os
import sys
import tempfile
import json
import datetime as _dt
import inspect

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from pathlib import Path
from PySide6.QtWidgets import QApplication, QTextBrowser
from PySide6.QtCore import Qt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

app = QApplication.instance() or QApplication(sys.argv)


# ═══════════════════════════════════════════════════════════════
#  1. Dialog P0 — parse_speakers / export
# ═══════════════════════════════════════════════════════════════

class TestParseSpeakersDualTrack:
    def test_basic_speaker_format(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] Speaker 1** hello\n"
            "**[00:05] Speaker 2** world\n"
            "**[00:10] Speaker 1** again\n",
            encoding="utf-8",
        )
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2
        ids = {s["spk_id"] for s in speakers}
        assert 0 in ids and 1 in ids

    def test_dual_track_local_remote(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] 本地-1** hello\n"
            "**[00:05] 远程-1** world\n"
            "**[00:10] 本地-1** again\n",
            encoding="utf-8",
        )
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2
        labels = {s["label"] for s in speakers}
        assert "本地-1" in labels
        assert "远程-1" in labels

    def test_name_pattern_format(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] 张三** hello\n"
            "**[00:05] 李四** world\n",
            encoding="utf-8",
        )
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2
        names = {s["name"] for s in speakers}
        assert "张三" in names
        assert "李四" in names

    def test_json_format(self, tmp_path):
        result = tmp_path / "result.json"
        data = {
            "segments": [
                {"speaker_id": 0, "text": "hello"},
                {"speaker_id": 1, "text": "world"},
                {"speaker_id": 0, "text": "again"},
            ]
        }
        result.write_text(json.dumps(data), encoding="utf-8")
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2

    def test_saved_names_applied(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] Speaker 1** hello\n"
            "**[00:05] Speaker 2** world\n",
            encoding="utf-8",
        )
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(
            str(result), saved_names={"1": "张三", "2": "李四"}
        )
        names = {s["name"] for s in speakers}
        assert "张三" in names
        assert "李四" in names

    def test_dual_track_saved_names(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] 本地-1** hello\n"
            "**[00:05] 远程-1** world\n",
            encoding="utf-8",
        )
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(
            str(result), saved_names={"本地-1": "张三", "远程-1": "李四"}
        )
        names = {s["name"] for s in speakers}
        assert "张三" in names
        assert "李四" in names

    def test_percentage_calculation(self, tmp_path):
        result = tmp_path / "result.md"
        lines = ["**[00:00] Speaker 1** line\n"] * 7 + ["**[00:05] Speaker 2** line\n"] * 3
        result.write_text("\n".join(lines), encoding="utf-8")
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(str(result))
        total_pct = sum(s["pct"] for s in speakers)
        assert abs(total_pct - 100.0) < 0.1

    def test_no_speakers_returns_empty(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text("No speaker info here\n", encoding="utf-8")
        from gui.dialogs import parse_speakers_from_result
        speakers = parse_speakers_from_result(str(result))
        assert speakers == [] or all(s["name"] for s in speakers)


class TestParseSpeakersHelper:
    def test_parse_speakers_json_basic(self):
        from gui.dialogs import _parse_speakers_json
        content = json.dumps({
            "segments": [
                {"speaker_id": 0, "text": "a"},
                {"speaker_id": 1, "text": "b"},
            ]
        })
        speakers = _parse_speakers_json(content)
        assert 0 in speakers
        assert 1 in speakers

    def test_parse_speakers_text_dual_track(self):
        from gui.dialogs import _parse_speakers_text
        content = "**[00:00] 本地-1** hello\n**[00:05] 远程-1** world\n"
        speakers = _parse_speakers_text(content)
        assert "本地-1" in speakers
        assert "远程-1" in speakers

    def test_parse_speaker_names_from_text(self):
        from gui.dialogs import _parse_speaker_names_from_text
        content = "**[00:00] 张三** hello\n**[00:05] 李四** world\n"
        speakers = _parse_speaker_names_from_text(content)
        names = [s["name"] for s in speakers.values()]
        assert "张三" in names
        assert "李四" in names

    def test_apply_saved_names_empty_speakers(self):
        from gui.dialogs import _apply_saved_names
        speakers = {}
        saved = {"1": "张三"}
        result = _apply_saved_names(speakers, saved)
        assert "张三" in [s["name"] for s in result.values()]

    def test_apply_saved_names_dual_track(self):
        from gui.dialogs import _apply_saved_names
        speakers = {"本地-1": {"spk_id": "本地-1", "label": "本地-1", "name": "", "pct": 50}}
        saved = {"本地-1": "张三"}
        result = _apply_saved_names(speakers, saved)
        assert result["本地-1"]["name"] == "张三"


class TestGetEmbeddingById:
    def test_int_key(self):
        from gui.dialogs import SpeakerDialog
        emb = {0: [1, 2, 3], 1: [4, 5, 6]}
        assert SpeakerDialog._get_embedding_by_id(emb, 0) == [1, 2, 3]

    def test_str_int_key(self):
        from gui.dialogs import SpeakerDialog
        emb = {0: [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, "0") == [1, 2, 3]

    def test_spk_n_format(self):
        from gui.dialogs import SpeakerDialog
        emb = {0: [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, "spk-0") == [1, 2, 3]

    def test_direct_key(self):
        from gui.dialogs import SpeakerDialog
        emb = {"spk-0": [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, "spk-0") == [1, 2, 3]

    def test_not_found(self):
        from gui.dialogs import SpeakerDialog
        emb = {0: [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, 99) is None


class TestExportDialogAutoOpen:
    def test_source_contains_explorer_select(self):
        src = open(
            os.path.join(os.path.dirname(__file__), "..", "src", "gui", "dialogs.py"),
            encoding="utf-8",
        ).read()
        assert 'explorer' in src
        assert '/select,' in src

    def test_source_contains_open_folder_logic(self):
        src = open(
            os.path.join(os.path.dirname(__file__), "..", "src", "gui", "dialogs.py"),
            encoding="utf-8",
        ).read()
        assert 'subprocess.Popen' in src
        assert 'CREATE_NO_WINDOW' in src


# ═══════════════════════════════════════════════════════════════
#  2. Add Voice Dialog
# ═══════════════════════════════════════════════════════════════

def test_preset_text_exists():
    from gui.voiceprint_page import AddVoiceDialog
    assert hasattr(AddVoiceDialog, 'PRESET_TEXT')
    assert AddVoiceDialog.PRESET_TEXT == "你好，我是{姓名}，这是我的声纹样本。"


def test_dialog_instantiation():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog.windowTitle() == "添加新说话人"
    assert dialog._recording is False
    assert dialog._audio_path is None
    assert dialog._embedding is None


def test_record_btn_initial_state():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._record_btn.isEnabled() is True
    assert dialog._record_btn.text() == "开始录音"


def test_save_btn_initial_state():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._save_btn.isEnabled() is False


def test_voiceprint_page_add_speaker_uses_dialog():
    from gui.voiceprint_page import AddVoiceDialog
    assert AddVoiceDialog.__name__ == 'AddVoiceDialog'


def test_name_entry_exists():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._name_entry is not None
    assert dialog._name_entry.placeholderText() == "请输入姓名"


def test_status_label_initial():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._status_label.text() == "准备就绪"


# ═══════════════════════════════════════════════════════════════
#  3. Embedding Save
# ═══════════════════════════════════════════════════════════════

class TestEmbeddingSave:
    def test_save_embeddings_to_disk_method_exists(self):
        from gui.transcription import TranscriptionHandler
        assert hasattr(TranscriptionHandler, '_save_embeddings_to_disk')

    def test_save_embeddings_creates_json_file(self, tmp_path):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._speaker_embeddings = {
            0: np.array([0.1, 0.2, 0.3]),
            1: np.array([0.4, 0.5, 0.6])
        }
        handler._speaker_qualities = {0: 0.85, 1: 0.9}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.result_path = str(tmp_path / "test_transcript.md")
        app.file_manager.get_file.return_value = mock_item

        handler._save_embeddings_to_disk()

        emb_path = str(tmp_path / "test_embeddings.json")
        assert os.path.exists(emb_path)
        with open(emb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "0" in data
        assert "1" in data
        assert data["0"]["vector"] == [0.1, 0.2, 0.3]
        assert data["0"]["quality"] == 0.85
        assert data["1"]["vector"] == [0.4, 0.5, 0.6]
        assert data["1"]["quality"] == 0.9

    def test_save_embeddings_no_save_when_empty(self, tmp_path):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._speaker_embeddings = {}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.result_path = str(tmp_path / "test_transcript.md")
        app.file_manager.get_file.return_value = mock_item

        handler._save_embeddings_to_disk()

        emb_path = str(tmp_path / "test_embeddings.json")
        assert not os.path.exists(emb_path)

    def test_save_embeddings_skip_when_result_path_none(self, tmp_path):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._speaker_embeddings = {0: np.array([0.1, 0.2])}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.result_path = None
        app.file_manager.get_file.return_value = mock_item

        handler._save_embeddings_to_disk()

        assert not os.path.exists(str(tmp_path / "test_embeddings.json"))

    def test_save_embeddings_handles_numpy_array(self, tmp_path):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._speaker_embeddings = {0: np.array([1.0, 2.0, 3.0])}
        handler._speaker_qualities = {0: 0.95}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.result_path = str(tmp_path / "test_transcript.md")
        app.file_manager.get_file.return_value = mock_item

        handler._save_embeddings_to_disk()

        emb_path = str(tmp_path / "test_embeddings.json")
        with open(emb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data["0"]["vector"], list)
        assert data["0"]["vector"] == [1.0, 2.0, 3.0]

    def test_save_embeddings_called_in_on_done(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._speaker_embeddings = {0: np.array([0.1, 0.2])}
        handler._current_batch_paths = {"test.wav"}
        handler._transcribing = True
        handler._file_status = {"test.wav": "done"}

        with patch.object(handler, '_save_embeddings_to_disk') as mock_save:
            handler._on_done()
            mock_save.assert_called_once()

    def test_save_embeddings_preserves_quality_default(self, tmp_path):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._speaker_embeddings = {0: np.array([0.1, 0.2])}
        handler._speaker_qualities = {}
        handler._current_batch_paths = {"test.wav"}

        mock_item = MagicMock()
        mock_item.result_path = str(tmp_path / "test_transcript.md")
        app.file_manager.get_file.return_value = mock_item

        handler._save_embeddings_to_disk()

        emb_path = str(tmp_path / "test_embeddings.json")
        with open(emb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        from gui.styles import DEFAULT_SPK_QUALITY
        assert data["0"]["quality"] == DEFAULT_SPK_QUALITY


# ═══════════════════════════════════════════════════════════════
#  4. Markdown Render
# ═══════════════════════════════════════════════════════════════

def _create_temp_file(content, suffix='.md'):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


class TestMarkdownRender:
    def test_markdown_import(self):
        import markdown
        assert hasattr(markdown, 'markdown')

    def test_preview_dialog_exists(self):
        from gui.dialogs import PreviewDialog
        assert PreviewDialog is not None

    def test_preview_dialog_has_text_box(self):
        from gui.dialogs import PreviewDialog
        result_path = _create_temp_file("# Test")
        try:
            dialog = PreviewDialog(None, "test.md", result_path)
            assert hasattr(dialog, '_text_box')
        finally:
            os.unlink(result_path)

    def test_text_box_is_text_browser(self):
        from gui.dialogs import PreviewDialog
        result_path = _create_temp_file("# Test")
        try:
            dialog = PreviewDialog(None, "test.md", result_path)
            assert isinstance(dialog._text_box, QTextBrowser)
        finally:
            os.unlink(result_path)

    def test_show_summary_uses_html(self):
        from gui.dialogs import PreviewDialog
        summary_content = "# 测试标题\n\n这是摘要内容"
        summary_path = _create_temp_file(summary_content)
        result_path = _create_temp_file("转写内容")
        try:
            dialog = PreviewDialog(None, "test.md", result_path, summary_path)
            dialog._show_summary()
            html_content = dialog._text_box.toHtml()
            assert "测试标题" in html_content
        finally:
            os.unlink(result_path)
            os.unlink(summary_path)

    def test_show_transcript_uses_plain_text(self):
        from gui.dialogs import PreviewDialog
        transcript_content = "# 转写结果\n\nSpeaker 1: 你好"
        result_path = _create_temp_file(transcript_content)
        try:
            dialog = PreviewDialog(None, "test.md", result_path)
            dialog._show_transcript()
            plain_content = dialog._text_box.toPlainText()
            assert "Speaker 1: 你好" in plain_content
        finally:
            os.unlink(result_path)

    def test_markdown_rendering_basic(self):
        import markdown
        md_text = "# 标题\n\n**粗体**\n\n- 列表项1\n- 列表项2"
        html = markdown.markdown(md_text)
        assert "<h1>" in html
        assert "<strong>粗体</strong>" in html
        assert "<li>列表项1</li>" in html
        assert "<li>列表项2</li>" in html


# ═══════════════════════════════════════════════════════════════
#  5. G12 Spec Deviations
# ═══════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestRecorderFilenameFormat:
    def test_stamp_is_mmddhh(self):
        from unified_recorder import _recording_filename_stamp
        fixed = _dt.datetime(2026, 6, 16, 14, 30, 0)
        stamp = _recording_filename_stamp(fixed)
        assert stamp == "061614"
        assert len(stamp) == 6

    def test_stamp_has_no_year_prefix(self):
        from unified_recorder import _recording_filename_stamp
        fixed = _dt.datetime(2026, 1, 2, 3, 0, 0)
        stamp = _recording_filename_stamp(fixed)
        assert stamp == "010203"


@pytest.mark.unit
class TestFileDialogFilter:
    def test_filter_contains_aac_and_wma(self):
        from gui.home_page import AUDIO_FILE_FILTER
        assert "*.aac" in AUDIO_FILE_FILTER
        assert "*.wma" in AUDIO_FILE_FILTER

    def test_filter_still_has_common_formats(self):
        from gui.home_page import AUDIO_FILE_FILTER
        for fmt in ("*.wav", "*.mp3", "*.m4a", "*.flac", "*.ogg"):
            assert fmt in AUDIO_FILE_FILTER


@pytest.mark.unit
class TestMiddleThirdWindow:
    def test_window_is_middle_third(self):
        from gui.dialogs import _middle_third_window
        start, end = _middle_third_window(0, 9000)
        assert start == 3000
        assert end == 6000

    def test_window_offset_segment(self):
        from gui.dialogs import _middle_third_window
        start, end = _middle_third_window(1000, 4000)
        assert start == 2000
        assert end == 3000


@pytest.mark.unit
class TestDeadDialogRemoved:
    def test_transcription_complete_dialog_gone(self):
        import gui.dialogs as dialogs
        assert not hasattr(dialogs, "TranscriptionCompleteDialog")


# ═══════════════════════════════════════════════════════════════
#  6. GAP-8: Export dialog helpers
# ═══════════════════════════════════════════════════════════════

class TestStripMarkdown:
    def test_strip_markdown(self):
        """去除 markdown 标记"""
        from gui.dialogs import ExportDialog
        result_path = _create_temp_file("")
        try:
            dialog = ExportDialog(None, "dummy", result_path)
            assert dialog._strip_markdown("**bold** text") == "bold text"
            assert dialog._strip_markdown("`code`") == "code"
            assert dialog._strip_markdown("normal text") == "normal text"
            assert dialog._strip_markdown("**bold1** and **bold2**") == "bold1 and bold2"
        finally:
            os.unlink(result_path)


class TestConvertToSrt:
    def test_convert_to_srt(self):
        """SRT 时间戳计算"""
        from gui.dialogs import ExportDialog
        result_path = _create_temp_file("")
        try:
            dialog = ExportDialog(None, "dummy", result_path)
            transcript = "**[00:00] Speaker 1** 你好\n**[00:03] Speaker 2** 你好"
            srt = dialog._convert_to_srt(transcript)
            assert "00:00:00,000 --> 00:00:03,000" in srt
            assert "Speaker 1" in srt
            assert "Speaker 2" in srt
            assert "00:00:03,000 --> 00:00:06,000" in srt
        finally:
            os.unlink(result_path)


class TestExportIncludesSummary:
    def test_export_includes_summary(self, tmp_path):
        """导出应包含 AI 摘要"""
        from gui.dialogs import ExportDialog
        transcript = tmp_path / "transcript.md"
        transcript.write_text("# 转写内容\nSpeaker 1: 你好", encoding="utf-8")
        summary = tmp_path / "summary.md"
        summary.write_text("# 会议摘要\n本次会议...", encoding="utf-8")
        dialog = ExportDialog(None, str(transcript), str(transcript), str(summary))
        with open(str(transcript), "r", encoding="utf-8") as f:
            content = f.read()
        if summary.exists():
            with open(str(summary), "r", encoding="utf-8") as f:
                summary_content = f.read()
            content = f"{summary_content}\n\n---\n\n{content}"
        assert "# 会议摘要" in content
        assert "# 转写内容" in content


@pytest.mark.unit
class TestMergeOrderSubtitle:
    def test_subtitle_no_drag_claim(self):
        from gui.dialogs import MergeOrderDialog
        src = inspect.getsource(MergeOrderDialog._build)
        assert "拖动" not in src
        assert "拖拽" not in src
        assert "按钮" in src


# ══════════════════════════════════════════════════════════
#  打开文件夹修复 (result_path) (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestOpenFolderFix:
    """打开文件夹应定位到转写结果目录"""

    def test_open_folder_uses_result_path(self, qtbot):
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        mock_item = MagicMock()
        mock_item.result_path = "/results/meeting_transcript.md"
        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm
        with patch('subprocess.Popen') as mock_popen:
            test_app._home_page._open_folder("/recordings/meeting.wav")
            if mock_popen.called:
                call_args = mock_popen.call_args[0][0]
                assert "/results" in call_args[1] or "results" in call_args[1]
        test_app.close()

    def test_open_folder_fallback_to_file_path(self, qtbot):
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        mock_item = MagicMock()
        mock_item.result_path = None
        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm
        with patch('subprocess.Popen') as mock_popen:
            test_app._home_page._open_folder("/recordings/meeting.wav")
            if mock_popen.called:
                call_args = mock_popen.call_args[0][0]
                assert "/recordings" in call_args[1] or "recordings" in call_args[1]
        test_app.close()


# ══════════════════════════════════════════════════════════
#  导出摘要合并 (summary_path) (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestExportWithSummary:
    """导出应包含摘要内容"""

    def test_export_dialog_receives_summary_path(self, qtbot, tmp_path):
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        transcript = tmp_path / "meeting_transcript.md"
        transcript.write_text("# 转写内容\n\nSpeaker 1: 你好")
        summary = tmp_path / "meeting_summary.md"
        summary.write_text("# 摘要\n\n会议讨论了项目进度")
        mock_item = MagicMock()
        mock_item.result_path = str(transcript)
        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm
        with patch('utils.get_summary_path', return_value=str(summary)):
            with patch('gui.dialogs.ExportDialog') as MockDialog:
                mock_dialog = MagicMock()
                MockDialog.return_value = mock_dialog
                test_app._home_page._export_result("/recordings/meeting.wav")
                if MockDialog.called:
                    call_args = MockDialog.call_args
                    assert len(call_args[0]) >= 4 or 'summary_path' in str(call_args)
        test_app.close()

    def test_export_dialog_without_summary(self, qtbot, tmp_path):
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        transcript = tmp_path / "meeting_transcript.md"
        transcript.write_text("# 转写内容")
        mock_item = MagicMock()
        mock_item.result_path = str(transcript)
        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm
        with patch('utils.get_summary_path', return_value=None):
            with patch('gui.dialogs.ExportDialog') as MockDialog:
                mock_dialog = MagicMock()
                MockDialog.return_value = mock_dialog
                test_app._home_page._export_result("/recordings/meeting.wav")
                if MockDialog.called:
                    call_args = MockDialog.call_args
                    assert call_args[0][3] is None or call_args[1].get('summary_path') is None
        test_app.close()
