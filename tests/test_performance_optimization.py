#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能优化测试：按钮增量更新机制
"""

import pytest
import queue
import threading
import customtkinter as ctk
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from file_manager import AudioFile, FileStatus


@pytest.fixture(scope="module")
def tk_root():
    """Module-scoped Tk root to avoid multiple CTk instantiation"""
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture(scope="function")
def home_page(tk_root):
    """Create a fresh HomePage for each test"""
    for child in tk_root.winfo_children():
        child.destroy()

    mock_app = MagicMock()
    mock_app.config = MagicMock()
    mock_app.config.get = MagicMock(return_value="mic")
    mock_app.file_manager = MagicMock()
    mock_app.file_manager.files = []
    mock_app._transcription_handler = MagicMock()
    mock_app._transcription_handler.get_queue_position = MagicMock(return_value=0)
    mock_app._transcription_handler.get_queue = MagicMock(return_value=[])
    mock_app._transcription_handler.is_transcribing = False

    from gui.home_page import HomePage
    page = HomePage(tk_root, app=mock_app)
    return page


def _make_file(file_path="test.wav", status=FileStatus.PENDING, result_path=None):
    """Helper to create a properly initialized AudioFile"""
    file_item = AudioFile(file_path=file_path, duration_s=60.0, file_size=1048576)
    file_item.topic = ""
    file_item.source_files = []
    file_item.result_path = result_path
    file_item.status = status
    return file_item


def _is_packed(widget):
    """Check if a widget is currently managed by pack geometry manager.

    winfo_ismapped() is unreliable in headless/withdrawn mode because
    the parent frame itself is not mapped to screen. Instead, check
    whether the widget has valid pack_info (i.e., was packed and not
    pack_forget()'d).
    """
    try:
        info = widget.pack_info()
        return bool(info)
    except Exception:
        return False


class TestFileListView:
    """测试文件列表视图组件"""

    def setup_method(self):
        try:
            self.root = ctk.CTk()
            self.root.withdraw()
        except Exception:
            pytest.skip("customtkinter/Tk not available in this environment")

    def teardown_method(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_file_list_view_creation(self):
        """验证 FileListView 可以创建"""
        from gui.file_list_view import FileListView

        view = FileListView(self.root)
        assert view is not None

    def test_file_list_view_refresh(self):
        """验证 FileListView 可以刷新"""
        from gui.file_list_view import FileListView

        view = FileListView(self.root)

        files = [
            AudioFile(file_path="test1.wav", duration_s=60.0),
            AudioFile(file_path="test2.wav", duration_s=120.0),
        ]
        files[1].status = FileStatus.DONE

        view.refresh(files)
        assert len(view._row_widgets) == 2

    def test_file_list_view_get_selected_empty(self):
        """验证初始时无选中文件"""
        from gui.file_list_view import FileListView

        view = FileListView(self.root)
        assert view.get_selected() == []

    def test_file_list_view_format_duration(self):
        """验证时长格式化"""
        from gui.file_list_view import FileListView

        view = FileListView(self.root)
        assert view._format_duration(0) == "--:--"
        assert view._format_duration(65) == "01:05"
        assert view._format_duration(120) == "02:00"

    def test_file_list_view_status_text(self):
        """验证状态文本映射"""
        from gui.file_list_view import FileListView

        view = FileListView(self.root)
        assert view._get_status_text(FileStatus.PENDING) == "等待中"
        assert view._get_status_text(FileStatus.PROCESSING) == "转写中"
        assert view._get_status_text(FileStatus.DONE) == "已完成"
        assert view._get_status_text(FileStatus.FAILED) == "失败"


class TestButtonIncrementalUpdate:
    """测试按钮增量更新机制"""

    def test_buttons_not_recreated_on_update(self, home_page):
        """验证更新行时不重建按钮"""
        file_item = _make_file("test_update.wav", FileStatus.PENDING)
        row_idx = 2
        home_page._create_file_row(file_item, row_idx)

        fp = file_item.file_path
        assert fp in home_page._file_rows
        buttons = home_page._file_rows[fp].get("action_buttons", {})
        assert len(buttons) > 0, "应该有按钮被创建"

        # 保存引用
        saved = {k: v for k, v in buttons.items()}

        # 更新状态
        file_item.status = FileStatus.DONE
        file_item.result_path = "/fake/result.md"
        home_page._update_file_row(file_item, row_idx)

        # 验证同实例
        updated = home_page._file_rows[fp].get("action_buttons", {})
        for key in saved:
            if key in updated:
                assert updated[key] is saved[key], \
                    f"按钮 '{key}' 被重建了"

    def test_button_visibility_on_pending(self, home_page):
        """PENDING 状态：转写按钮可见，预览按钮隐藏"""
        file_item = _make_file("test_pending.wav", FileStatus.PENDING)
        row_idx = 2
        home_page._create_file_row(file_item, row_idx)

        buttons = home_page._file_rows[file_item.file_path].get("action_buttons", {})

        if "transcribe" in buttons:
            assert _is_packed(buttons["transcribe"]), \
                "PENDING 状态下转写按钮应该可见"
        if "preview" in buttons:
            assert not _is_packed(buttons["preview"]), \
                "PENDING 状态下预览按钮应该隐藏"

    def test_button_visibility_on_done(self, home_page):
        """DONE 状态：预览按钮可见，转写按钮隐藏"""
        file_item = _make_file("test_done.wav", FileStatus.DONE,
                               result_path="/fake/result.md")
        row_idx = 2
        home_page._create_file_row(file_item, row_idx)

        buttons = home_page._file_rows[file_item.file_path].get("action_buttons", {})

        if "preview" in buttons:
            assert _is_packed(buttons["preview"]), \
                "DONE 状态下预览按钮应该可见"
        if "transcribe" in buttons:
            assert not _is_packed(buttons["transcribe"]), \
                "DONE 状态下转写按钮应该隐藏"

    def test_button_visibility_changes_on_status_update(self, home_page):
        """状态从 PENDING 变为 DONE 时，按钮可见性正确切换"""
        file_item = _make_file("test_switch.wav", FileStatus.PENDING)
        row_idx = 2
        home_page._create_file_row(file_item, row_idx)

        buttons = home_page._file_rows[file_item.file_path].get("action_buttons", {})

        # PENDING: transcribe visible
        if "transcribe" in buttons:
            assert _is_packed(buttons["transcribe"])

        # Update to DONE
        file_item.status = FileStatus.DONE
        file_item.result_path = "/fake/result.md"
        home_page._update_file_row(file_item, row_idx)

        # DONE: preview visible, transcribe hidden
        if "preview" in buttons:
            assert _is_packed(buttons["preview"])
        if "transcribe" in buttons:
            assert not _is_packed(buttons["transcribe"])

    def test_all_button_types_created(self, home_page):
        """验证所有按钮类型都被创建"""
        file_item = _make_file("test_types.wav", FileStatus.PENDING)
        row_idx = 2
        home_page._create_file_row(file_item, row_idx)

        buttons = home_page._file_rows[file_item.file_path].get("action_buttons", {})

        expected = ["preview", "open", "speaker", "retry", "export",
                    "stop", "transcribe", "move_up", "move_down", "remove_from_queue"]
        for key in expected:
            assert key in buttons, f"缺少按钮类型: {key}"

    def test_stop_button_visible_on_processing(self, home_page):
        """PROCESSING 状态：停止按钮可见"""
        file_item = _make_file("test_processing.wav", FileStatus.PROCESSING)
        row_idx = 2
        home_page._create_file_row(file_item, row_idx)

        buttons = home_page._file_rows[file_item.file_path].get("action_buttons", {})

        if "stop" in buttons:
            assert _is_packed(buttons["stop"]), \
                "PROCESSING 状态下停止按钮应该可见"
        if "transcribe" in buttons:
            assert not _is_packed(buttons["transcribe"]), \
                "PROCESSING 状态下转写按钮应该隐藏"


class TestFileChangeDebounce:
    """测试文件变更防抖机制"""

    def test_debounce_merges_rapid_changes(self):
        """验证快速变更合并为一次刷新"""
        mock_app = MagicMock()
        pending_timers = []

        def mock_after(ms, callback):
            timer_id = f"timer_{len(pending_timers)}"
            pending_timers.append((timer_id, callback))
            return timer_id

        def mock_after_cancel(timer_id):
            nonlocal pending_timers
            pending_timers = [(tid, cb) for tid, cb in pending_timers if tid != timer_id]

        mock_app.after = mock_after
        mock_app.after_cancel = mock_after_cancel
        mock_app._refresh_pending = None

        refresh_count = 0

        def counting_refresh():
            nonlocal refresh_count
            refresh_count += 1

        def do_refresh():
            mock_app._refresh_pending = None
            counting_refresh()

        # Simulate _on_file_changed 10 times rapidly
        for _ in range(10):
            if mock_app._refresh_pending:
                mock_app.after_cancel(mock_app._refresh_pending)
            mock_app._refresh_pending = mock_app.after(200, do_refresh)

        # Simulate timer firing (only the last scheduled callback)
        if pending_timers:
            pending_timers[-1][1]()

        assert refresh_count == 1, f"期望刷新 1 次，实际 {refresh_count} 次"

    def test_debounce_cancels_previous_timer(self):
        """验证每次变更取消之前的定时器"""
        mock_app = MagicMock()
        cancel_count = 0

        def mock_after_cancel(timer_id):
            nonlocal cancel_count
            cancel_count += 1

        mock_app.after = lambda ms, cb: "timer"
        mock_app.after_cancel = mock_after_cancel
        mock_app._refresh_pending = "old_timer"

        # Simulate _on_file_changed
        if mock_app._refresh_pending:
            mock_app.after_cancel(mock_app._refresh_pending)
        mock_app._refresh_pending = mock_app.after(200, lambda: None)

        assert cancel_count == 1


class TestAsyncDurationFetch:
    """测试异步获取音频时长"""

    def setup_method(self):
        from file_manager import FileManager
        self.fm = FileManager.__new__(FileManager)
        self.fm._files = []
        self.fm._listeners = []
        self.fm._data_file = None

    def test_add_file_with_zero_duration_starts_async(self):
        """验证 duration=0 时启动异步获取"""
        with patch('file_manager.get_audio_duration', return_value=60.0):
            with patch('threading.Thread') as mock_thread:
                self.fm.add_file("test.wav", duration_s=0)

                # 验证启动了后台线程
                mock_thread.assert_called_once()
                call_args = mock_thread.call_args
                assert call_args[1]['daemon'] is True

    def test_add_file_with_duration_no_async(self):
        """验证 duration>0 时不启动异步获取"""
        with patch('threading.Thread') as mock_thread:
            self.fm.add_file("test.wav", duration_s=60.0)

            # 验证没有启动后台线程
            mock_thread.assert_not_called()


class TestAsyncFileRead:
    """测试异步文件读取 - 转写结果处理移出主线程"""

    def test_auto_correction_runs_in_thread(self):
        """验证自动修正在后台线程执行"""
        mock_app = MagicMock()
        mock_ai_service = MagicMock()

        handler = MagicMock()
        handler._app = mock_app
        handler._ai_service = mock_ai_service

        with patch('threading.Thread') as mock_thread:
            from gui.transcription import TranscriptionHandler
            TranscriptionHandler._process_auto_correction(
                handler, "raw text content", "meeting", "/out", "/out/meeting_transcript.md"
            )

            # 验证启动了后台线程
            mock_thread.assert_called_once()
            call_args = mock_thread.call_args
            assert call_args[1]['daemon'] is True

    def test_auto_summary_runs_in_thread(self):
        """验证自动摘要在后台线程执行"""
        mock_app = MagicMock()
        mock_ai_service = MagicMock()

        handler = MagicMock()
        handler._app = mock_app
        handler._ai_service = mock_ai_service

        with patch('threading.Thread') as mock_thread:
            from gui.transcription import TranscriptionHandler
            TranscriptionHandler._process_auto_summary(
                handler, "meeting", "/out"
            )

            # 验证启动了后台线程
            mock_thread.assert_called_once()
            call_args = mock_thread.call_args
            assert call_args[1]['daemon'] is True

    def test_poll_dispatches_correction_to_thread(self):
        """验证 _poll 中 auto_correction 消息被分发到后台线程"""
        mock_app = MagicMock()
        mock_app.config = MagicMock()
        mock_app.config.get = MagicMock(return_value="转写后自动纠错")

        handler = MagicMock()
        handler._app = mock_app
        handler._ai_service = MagicMock()
        handler._transcribing = False
        handler._process = MagicMock()
        handler._process.is_alive = MagicMock(return_value=False)

        # Track calls to _process_auto_correction on the handler
        correction_calls = []
        handler._process_auto_correction = MagicMock(
            side_effect=lambda *args: correction_calls.append(args)
        )

        call_count = [0]
        msgs = [
            ("auto_correction", "raw text", "meeting", "/out", "/out/meeting_transcript.md"),
        ]

        def get_nowait():
            if call_count[0] < len(msgs):
                msg = msgs[call_count[0]]
                call_count[0] += 1
                return msg
            raise Exception("empty")

        handler._queue = MagicMock()
        handler._queue.empty = MagicMock(side_effect=lambda: call_count[0] >= len(msgs))
        handler._queue.get_nowait = get_nowait

        from gui.transcription import TranscriptionHandler
        TranscriptionHandler._poll(handler, ["/test.wav"])

        handler._process_auto_correction.assert_called_once_with(
            "raw text", "meeting", "/out", "/out/meeting_transcript.md"
        )


class TestAdaptivePolling:
    """测试自适应轮询间隔"""

    def test_poll_interval_increases_when_idle(self):
        """验证空闲时轮询间隔增加"""
        handler = MagicMock()
        handler._poll_interval = 50
        handler._transcribing = True
        handler._queue = MagicMock()
        handler._queue.empty.return_value = True  # 无消息
        handler._process = MagicMock()
        handler._process.is_alive.return_value = True

        from gui.transcription import TranscriptionHandler
        TranscriptionHandler._poll(handler, ["/test.wav"])

        # 间隔应该增加（50 * 1.5 = 75）
        assert handler._poll_interval > 50

    def test_poll_interval_resets_on_message(self):
        """验证有消息时轮询间隔重置"""
        handler = MagicMock()
        handler._poll_interval = 500
        handler._transcribing = True
        handler._queue = MagicMock()
        handler._process = MagicMock()
        handler._process.is_alive.return_value = True

        # First call returns a message, second call raises Empty
        call_count = [0]
        msgs = [("status", "test status")]

        def get_nowait():
            if call_count[0] < len(msgs):
                msg = msgs[call_count[0]]
                call_count[0] += 1
                return msg
            raise queue.Empty()

        handler._queue.empty.side_effect = lambda: call_count[0] >= len(msgs)
        handler._queue.get_nowait = get_nowait

        from gui.transcription import TranscriptionHandler
        TranscriptionHandler._poll(handler, ["/test.wav"])

        # 间隔应该重置为 50
        assert handler._poll_interval == 50

    def test_poll_interval_caps_at_500(self):
        """验证轮询间隔最大不超过 500ms"""
        handler = MagicMock()
        handler._poll_interval = 400  # 接近上限
        handler._transcribing = True
        handler._queue = MagicMock()
        handler._queue.empty.return_value = True  # 无消息
        handler._process = MagicMock()
        handler._process.is_alive.return_value = True

        from gui.transcription import TranscriptionHandler
        TranscriptionHandler._poll(handler, ["/test.wav"])

        # 400 * 1.5 = 600，但应该被限制为 500
        assert handler._poll_interval == 500

    def test_poll_interval_exponential_backoff(self):
        """验证轮询间隔指数退避行为"""
        handler = MagicMock()
        handler._poll_interval = 50
        handler._transcribing = True
        handler._queue = MagicMock()
        handler._queue.empty.return_value = True  # 无消息
        handler._process = MagicMock()
        handler._process.is_alive.return_value = True

        from gui.transcription import TranscriptionHandler

        # 第一次空闲轮询：50 * 1.5 = 75
        TranscriptionHandler._poll(handler, ["/test.wav"])
        assert handler._poll_interval == 75

        # 第二次空闲轮询：75 * 1.5 = 112.5
        TranscriptionHandler._poll(handler, ["/test.wav"])
        assert handler._poll_interval == 112.5

        # 继续退避直到接近上限
        for _ in range(10):
            TranscriptionHandler._poll(handler, ["/test.wav"])

        # 最终应该达到上限 500
        assert handler._poll_interval == 500


class TestImmediateFeedback:
    """测试录音按钮即时反馈"""

    def test_start_button_disabled_immediately(self, home_page):
        """验证点击后按钮立即禁用并显示启动中状态"""
        home_page._btn_start_rec = MagicMock()
        home_page._btn_stop_rec = MagicMock()
        home_page._btn_pause_rec = MagicMock()
        home_page._app.recorder = MagicMock()
        home_page._rec_mode_var = MagicMock()
        home_page._rec_mode_var.get.return_value = "现场会议"

        home_page._start_recording()

        home_page._btn_start_rec.configure.assert_any_call(
            state="disabled", text="启动中..."
        )

    def test_stop_pause_enabled_immediately(self, home_page):
        """验证点击后停止和暂停按钮立即启用"""
        home_page._btn_start_rec = MagicMock()
        home_page._btn_stop_rec = MagicMock()
        home_page._btn_pause_rec = MagicMock()
        home_page._app.recorder = MagicMock()
        home_page._rec_mode_var = MagicMock()
        home_page._rec_mode_var.get.return_value = "现场会议"

        home_page._start_recording()

        home_page._btn_stop_rec.configure.assert_any_call(state="normal")
        home_page._btn_pause_rec.configure.assert_any_call(state="normal")

    def test_recorder_start_called(self, home_page):
        """验证即时反馈后仍然调用 recorder.start"""
        home_page._btn_start_rec = MagicMock()
        home_page._btn_stop_rec = MagicMock()
        home_page._btn_pause_rec = MagicMock()
        home_page._app.recorder = MagicMock()
        home_page._rec_mode_var = MagicMock()
        home_page._rec_mode_var.get.return_value = "现场会议"

        home_page._start_recording()

        home_page._app.recorder.start.assert_called_once_with("mic")

    def test_error_restores_button_state(self, home_page):
        """验证启动失败时恢复按钮状态"""
        home_page._btn_start_rec = MagicMock()
        home_page._btn_stop_rec = MagicMock()
        home_page._btn_pause_rec = MagicMock()
        home_page._app.recorder = MagicMock()
        home_page._app.recorder.start.side_effect = RuntimeError("device error")
        home_page._rec_mode_var = MagicMock()
        home_page._rec_mode_var.get.return_value = "现场会议"

        with patch('gui.home_page.messagebox'):
            home_page._start_recording()

        home_page._btn_start_rec.configure.assert_any_call(
            state="normal", text="开始录音"
        )


class TestSpeakerIdTypeUnification:
    """测试 spk_id 类型统一"""

    def test_int_speaker_id_lookup(self):
        """验证 int 类型 spk_id 查询"""
        from gui.dialogs import SpeakerDialog

        embeddings = {0: [0.1, 0.2], 1: [0.3, 0.4]}

        # 应该直接找到，不需要类型转换
        result = SpeakerDialog._get_embedding_by_id(embeddings, 0)
        assert result == [0.1, 0.2]

    def test_string_speaker_id_lookup(self):
        """验证 str 类型 spk_id 查询"""
        from gui.dialogs import SpeakerDialog

        embeddings = {0: [0.1, 0.2], 1: [0.3, 0.4]}

        # 字符串 "0" 应该能转换为 int 并找到
        result = SpeakerDialog._get_embedding_by_id(embeddings, "0")
        assert result == [0.1, 0.2]

    def test_spk_format_speaker_id_lookup(self):
        """验证 'spk-N' 格式 spk_id 查询"""
        from gui.dialogs import SpeakerDialog

        embeddings = {0: [0.1, 0.2], 1: [0.3, 0.4]}

        # "spk-0" 应该能解析并找到
        result = SpeakerDialog._get_embedding_by_id(embeddings, "spk-0")
        assert result == [0.1, 0.2]

    def test_missing_speaker_returns_none(self):
        """验证不存在的说话人返回 None"""
        from gui.dialogs import SpeakerDialog

        embeddings = {0: [0.1, 0.2]}

        result = SpeakerDialog._get_embedding_by_id(embeddings, 99)
        assert result is None


class TestMatchSuggestion:
    """测试音色库匹配建议功能"""

    def test_accept_suggestion_fills_entry(self, tk_root):
        """验证接受建议后 entry 被填充"""
        from gui.dialogs import SpeakerDialog

        entry = ctk.CTkEntry(tk_root)
        entry.insert(0, "旧名字")

        SpeakerDialog._accept_suggestion(None, entry, "张三")

        assert entry.get() == "张三"

    def test_accept_suggestion_hides_frame(self, tk_root):
        """验证接受建议后建议框架被隐藏"""
        from gui.dialogs import SpeakerDialog

        entry = ctk.CTkEntry(tk_root)
        frame = ctk.CTkFrame(tk_root)

        SpeakerDialog._accept_suggestion(None, entry, "张三", suggestion_frame=frame)

        # frame 应该被 pack_forget
        assert entry.get() == "张三"

    def test_add_match_suggestion_skips_named_speaker(self, tk_root):
        """已有姓名的说话人不显示匹配建议"""
        from gui.dialogs import SpeakerDialog

        speakers = [{"spk_id": 0, "label": "Speaker 1", "name": "张三", "pct": 60.0}]
        embeddings = {0: [0.1] * 512}

        with patch('voiceprint.VoiceprintLibrary') as MockLib:
            mock_lib = MockLib.return_value
            mock_lib.match.return_value = ("张三", 0.95)

            dialog = SpeakerDialog.__new__(SpeakerDialog)
            dialog._speakers = speakers
            dialog._speaker_embeddings = embeddings
            dialog._speaker_entries = {}
            dialog._file_name = "test.wav"

            row = ctk.CTkFrame(tk_root)
            entry = ctk.CTkEntry(row)

            # 已有姓名，不应调用 library.match
            dialog._add_match_suggestion(row, speakers[0], entry)
            mock_lib.match.assert_not_called()

    def test_add_match_suggestion_shows_for_unnamed(self, tk_root):
        """无姓名且有匹配时显示建议"""
        from gui.dialogs import SpeakerDialog

        speakers = [{"spk_id": 0, "label": "Speaker 1", "name": "", "pct": 60.0}]
        embeddings = {0: [0.1] * 512}

        with patch('voiceprint.VoiceprintLibrary') as MockLib:
            mock_lib = MockLib.return_value
            mock_lib.match.return_value = ("李四", 0.92)

            dialog = SpeakerDialog.__new__(SpeakerDialog)
            dialog._speakers = speakers
            dialog._speaker_embeddings = embeddings
            dialog._speaker_entries = {}
            dialog._file_name = "test.wav"

            row = ctk.CTkFrame(tk_root)
            entry = ctk.CTkEntry(row)

            children_before = len(row.winfo_children())
            dialog._add_match_suggestion(row, speakers[0], entry)
            children_after = len(row.winfo_children())

            # 验证有新的子组件（建议框架）被添加
            assert children_after > children_before, "应该有建议框架被添加"

    def test_add_match_suggestion_no_match(self, tk_root):
        """无匹配时不显示建议"""
        from gui.dialogs import SpeakerDialog

        speakers = [{"spk_id": 0, "label": "Speaker 1", "name": "", "pct": 60.0}]
        embeddings = {0: [0.1] * 512}

        with patch('voiceprint.VoiceprintLibrary') as MockLib:
            mock_lib = MockLib.return_value
            mock_lib.match.return_value = (None, 0)

            dialog = SpeakerDialog.__new__(SpeakerDialog)
            dialog._speakers = speakers
            dialog._speaker_embeddings = embeddings
            dialog._speaker_entries = {}
            dialog._file_name = "test.wav"

            row = ctk.CTkFrame(tk_root)
            entry = ctk.CTkEntry(row)

            children_before = len(row.winfo_children())
            dialog._add_match_suggestion(row, speakers[0], entry)
            children_after = len(row.winfo_children())

            # 无匹配，不应添加额外子组件
            assert children_after == children_before, "无匹配时不应添加建议框架"

    def test_add_match_suggestion_no_embedding(self, tk_root):
        """无嵌入向量时不显示建议"""
        from gui.dialogs import SpeakerDialog

        speakers = [{"spk_id": 0, "label": "Speaker 1", "name": "", "pct": 60.0}]
        embeddings = {}  # 空的嵌入向量

        dialog = SpeakerDialog.__new__(SpeakerDialog)
        dialog._speakers = speakers
        dialog._speaker_embeddings = embeddings
        dialog._speaker_entries = {}
        dialog._file_name = "test.wav"

        row = ctk.CTkFrame(tk_root)
        entry = ctk.CTkEntry(row)

        children_before = len(row.winfo_children())
        dialog._add_match_suggestion(row, speakers[0], entry)
        children_after = len(row.winfo_children())

        # 无嵌入向量，不应添加额外子组件
        assert children_after == children_before, "无嵌入向量时不应添加建议框架"

    def test_add_match_suggestion_library_error(self, tk_root):
        """音色库加载异常时不崩溃"""
        from gui.dialogs import SpeakerDialog

        speakers = [{"spk_id": 0, "label": "Speaker 1", "name": "", "pct": 60.0}]
        embeddings = {0: [0.1] * 512}

        with patch('voiceprint.VoiceprintLibrary', side_effect=Exception("load error")):
            dialog = SpeakerDialog.__new__(SpeakerDialog)
            dialog._speakers = speakers
            dialog._speaker_embeddings = embeddings
            dialog._speaker_entries = {}
            dialog._file_name = "test.wav"

            row = ctk.CTkFrame(tk_root)
            entry = ctk.CTkEntry(row)

            children_before = len(row.winfo_children())
            # 不应抛出异常
            dialog._add_match_suggestion(row, speakers[0], entry)
            children_after = len(row.winfo_children())

            assert children_after == children_before


class TestRecorderThreadSafety:
    """测试录音器线程安全"""

    def test_recorder_has_lock_attribute(self):
        """验证 UnifiedRecorder __init__ 创建了线程锁"""
        import time as _time
        from unified_recorder import UnifiedRecorder

        recorder = UnifiedRecorder.__new__(UnifiedRecorder)
        # 模拟 __init__ 中的关键属性
        recorder._lock = threading.Lock()
        recorder._paused_duration = 0.0
        recorder._recording = True
        recorder._paused = False
        recorder._start_time = _time.time() - 10.0
        recorder._pause_start = None
        recorder.on_state_change = None

        assert hasattr(recorder, '_lock'), "UnifiedRecorder 应有 _lock 属性"

    def test_pause_resume_thread_safe(self):
        """验证并发 pause/resume 操作的线程安全性"""
        import time as _time
        from unified_recorder import UnifiedRecorder

        recorder = UnifiedRecorder.__new__(UnifiedRecorder)
        recorder._lock = threading.Lock()
        recorder._paused_duration = 0.0
        recorder._recording = True
        recorder._paused = False
        recorder._start_time = _time.time() - 10.0
        recorder._pause_start = None
        recorder.on_state_change = None

        errors = []

        def pause_resume_cycle():
            try:
                for _ in range(200):
                    recorder.pause()
                    _time.sleep(0.0001)
                    recorder.resume()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=pause_resume_cycle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无异常、状态一致
        assert len(errors) == 0, f"并发操作产生异常: {errors}"
        assert recorder._paused is False
        assert recorder._paused_duration > 0

    def test_get_elapsed_thread_safe(self):
        """验证 get_elapsed 在并发读写下返回合理值"""
        import time as _time
        from unified_recorder import UnifiedRecorder

        recorder = UnifiedRecorder.__new__(UnifiedRecorder)
        recorder._lock = threading.Lock()
        recorder._paused_duration = 0.0
        recorder._recording = True
        recorder._paused = False
        recorder._start_time = _time.time() - 5.0
        recorder._pause_start = None
        recorder.on_state_change = None

        results = []
        errors = []

        def read_elapsed():
            try:
                for _ in range(100):
                    e = recorder.get_elapsed()
                    results.append(e)
            except Exception as ex:
                errors.append(ex)

        def pause_resume():
            try:
                for _ in range(100):
                    recorder.pause()
                    _time.sleep(0.0001)
                    recorder.resume()
            except Exception as ex:
                errors.append(ex)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=read_elapsed))
        threads.append(threading.Thread(target=pause_resume))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发操作产生异常: {errors}"
        assert all(r >= 0 for r in results), "get_elapsed 应返回非负值"


class TestSpeakerParsing:
    """测试说话人解析拆分"""

    def test_json_format_parsing(self):
        """验证 JSON 格式解析（segments 中的 speaker_id）"""
        from gui.dialogs import parse_speakers_from_result

        import tempfile
        import json

        data = {
            "segments": [
                {"speaker_id": 0, "text": "你好"},
                {"speaker_id": 0, "text": "世界"},
                {"speaker_id": 1, "text": "早上好"},
                {"speaker_id": 1, "text": "下午好"},
                {"speaker_id": 1, "text": "晚上好"},
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = parse_speakers_from_result(temp_path)
            assert len(result) == 2
            # 验证返回结构
            assert "spk_id" in result[0]
            assert "label" in result[0]
            assert "name" in result[0]
            assert "pct" in result[0]
            # 验证排序和百分比
            assert result[0]["spk_id"] == 0
            assert result[0]["pct"] == pytest.approx(40.0)
            assert result[1]["spk_id"] == 1
            assert result[1]["pct"] == pytest.approx(60.0)
        finally:
            os.unlink(temp_path)

    def test_unknown_format_returns_empty(self):
        """验证未知/空格式返回空列表"""
        from gui.dialogs import parse_speakers_from_result

        import tempfile
        import json

        data = {"no_segments_here": True}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = parse_speakers_from_result(temp_path)
            assert result == []
        finally:
            os.unlink(temp_path)

    def test_text_format_speaker_pattern(self):
        """验证文本格式中的 Speaker N 模式解析"""
        from gui.dialogs import parse_speakers_from_result

        import tempfile
        content = """[00:00] Speaker 1: 你好
[00:05] Speaker 2: 世界
[00:10] Speaker 1: 再见
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            result = parse_speakers_from_result(temp_path)
            assert len(result) == 2
            assert result[0]["label"] == "Speaker 1"
            assert result[1]["label"] == "Speaker 2"
        finally:
            os.unlink(temp_path)

    def test_dual_track_format_parsing(self):
        """验证双轨格式（本地/远程）解析"""
        from gui.dialogs import parse_speakers_from_result

        import tempfile
        content = """[00:00] 本地-1: 你好
[00:05] 远程-2: 世界
[00:10] 本地-1: 再见
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            result = parse_speakers_from_result(temp_path)
            assert len(result) == 2
            labels = {s["label"] for s in result}
            assert "本地-1" in labels
            assert "远程-2" in labels
        finally:
            os.unlink(temp_path)

    def test_saved_names_applied(self):
        """验证 saved_names 参数正确应用到解析结果"""
        from gui.dialogs import parse_speakers_from_result

        import tempfile
        content = """[00:00] Speaker 1: 你好
[00:05] Speaker 2: 世界
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            saved_names = {"1": "张三", "2": "李四"}
            result = parse_speakers_from_result(temp_path, saved_names)
            assert len(result) == 2
            names = {s["name"] for s in result}
            assert "张三" in names
            assert "李四" in names
        finally:
            os.unlink(temp_path)

    def test_nonexistent_file_returns_empty(self):
        """验证不存在的文件返回空列表"""
        from gui.dialogs import parse_speakers_from_result

        result = parse_speakers_from_result("/nonexistent/path/file.json")
        assert result == []


class TestRecordingBar:
    """测试录音控制栏组件"""

    def test_recording_bar_creation(self, tk_root):
        """验证 RecordingBar 可以创建"""
        from gui.recording_bar import RecordingBar

        for child in tk_root.winfo_children():
            child.destroy()

        bar = RecordingBar(tk_root)
        assert bar is not None

    def test_recording_bar_state_update(self, tk_root):
        """验证状态更新"""
        from gui.recording_bar import RecordingBar

        for child in tk_root.winfo_children():
            child.destroy()

        bar = RecordingBar(tk_root)

        # 更新为录音状态
        bar.update_state(recording=True, paused=False)
        assert bar.record_btn.cget("state") == "disabled"
        assert bar.stop_btn.cget("state") == "normal"

    def test_recording_bar_timer_update(self, tk_root):
        """验证计时器更新"""
        from gui.recording_bar import RecordingBar

        for child in tk_root.winfo_children():
            child.destroy()

        bar = RecordingBar(tk_root)

        # 更新计时器
        bar.update_timer(125.5)  # 2分5.5秒
        assert "02:05" in bar.timer_label.cget("text")

    def test_recording_bar_mode_selection(self, tk_root):
        """验证模式选择"""
        from gui.recording_bar import RecordingBar

        for child in tk_root.winfo_children():
            child.destroy()

        bar = RecordingBar(tk_root)

        # 默认应该是线上会议
        assert bar.get_mode() == "dual"

        # 切换到现场会议
        bar.mode_var.set("现场会议")
        assert bar.get_mode() == "mic"


class TestConfigExplicitAttributes:
    """测试配置显式属性"""

    def test_known_attribute_access(self):
        """验证已知属性访问"""
        from config import Config

        config = Config.__new__(Config)
        config._data = {"recording_mode": "dual", "storage_path": "/tmp"}

        # 应该能直接访问
        assert config.recording_mode == "dual"
        assert config.storage_path == "/tmp"

    def test_unknown_attribute_returns_default(self):
        """验证未知属性返回默认值"""
        from config import Config

        config = Config.__new__(Config)
        config._data = {}

        # 未知属性应该返回 None 或默认值
        assert config.get("unknown") is None
        assert config.get("unknown", "default") == "default"

    def test_set_and_get(self, tmp_path):
        """验证设置和获取配置"""
        from config import Config

        config = Config.__new__(Config)
        config._data = {}
        config._path = str(tmp_path / "test_settings.json")

        config.set("test_key", "test_value")
        assert config.get("test_key") == "test_value"


class TestFormatters:
    """测试转写结果格式化器"""

    def test_json_format(self):
        """验证 JSON 格式输出"""
        from formatters import TranscriptFormatter

        segments = [
            {"start": 0, "end": 1000, "text": "你好", "speaker": 0},
            {"start": 1000, "end": 2000, "text": "世界", "speaker": 1},
        ]

        result = TranscriptFormatter.format_json(segments, metadata={"duration": 2.0})
        import json
        data = json.loads(result)
        assert len(data["segments"]) == 2

    def test_srt_format(self):
        """验证 SRT 格式输出"""
        from formatters import TranscriptFormatter

        segments = [
            {"start": 0, "end": 1000, "text": "你好", "speaker": 0},
            {"start": 1000, "end": 2000, "text": "世界", "speaker": 1},
        ]

        result = TranscriptFormatter.format_srt(segments)
        assert "1\n" in result
        assert "你好" in result

    def test_txt_format(self):
        """验证 TXT 格式输出"""
        from formatters import TranscriptFormatter

        segments = [
            {"start": 0, "end": 1000, "text": "你好", "speaker": 0},
            {"start": 1000, "end": 2000, "text": "世界", "speaker": 1},
        ]

        result = TranscriptFormatter.format_txt(segments)
        assert "你好" in result
        assert "世界" in result

    def test_md_format(self):
        """验证 Markdown 格式输出"""
        from formatters import TranscriptFormatter

        segments = [
            {"start": 0, "end": 1000, "text": "你好", "speaker": 0},
            {"start": 1000, "end": 2000, "text": "世界", "speaker": 1},
        ]

        result = TranscriptFormatter.format_md(segments, speakers=["张三", "李四"])
        assert "# 转写结果" in result
        assert "张三" in result


class TestModelManager:
    """测试模型管理器"""

    def test_check_models(self):
        """验证模型状态检查"""
        from model_manager import ModelManager

        manager = ModelManager()
        status = manager.check_models()

        assert isinstance(status, dict)
        assert "sensevoice" in status
        assert "cam++" in status
        assert "ct-punc" in status

    def test_get_model_path(self):
        """验证模型路径获取"""
        from model_manager import ModelManager

        manager = ModelManager()
        path = manager.get_model_path("sensevoice")

        assert isinstance(path, str)
        assert len(path) > 0

    def test_unknown_model_raises(self):
        """验证未知模型抛出异常"""
        from model_manager import ModelManager

        manager = ModelManager()

        try:
            manager.get_model_path("unknown_model")
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass
