"""
G12 — 验收标准偏差批量校正：改代码项的回归测试。

覆盖：
  - REC-010: 录音文件命名 MMDDHH会议.wav（非 YYMMDDHH）
  - FILE-001: 文件对话框过滤包含 aac/wma
  - SPK-007: 中间片段取最长发言"中间 1/3"
  - UI-009:  死代码 TranscriptionCompleteDialog 已删除
  - UI-010:  MergeOrderDialog 副标题不再宣称拖拽
"""
import os
import sys
import datetime as _dt

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── REC-010: 录音命名 MMDDHH ────────────────────────────────
@pytest.mark.unit
class TestRecorderFilenameFormat:
    def test_stamp_is_mmddhh(self):
        from unified_recorder import _recording_filename_stamp
        fixed = _dt.datetime(2026, 6, 16, 14, 30, 0)
        stamp = _recording_filename_stamp(fixed)
        # MMDDHH -> 06 16 14
        assert stamp == "061614"
        assert len(stamp) == 6

    def test_stamp_has_no_year_prefix(self):
        from unified_recorder import _recording_filename_stamp
        fixed = _dt.datetime(2026, 1, 2, 3, 0, 0)
        stamp = _recording_filename_stamp(fixed)
        # 不再以 26 (YY) 开头；应为 010203
        assert stamp == "010203"


# ── FILE-001: 过滤包含 aac/wma ──────────────────────────────
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


# ── SPK-007: 中间 1/3 片段窗口 ──────────────────────────────
@pytest.mark.unit
class TestMiddleThirdWindow:
    def test_window_is_middle_third(self):
        from gui.dialogs import _middle_third_window
        # 发言段 [0, 9000] ms -> 中间 1/3 = [3000, 6000]
        start, end = _middle_third_window(0, 9000)
        assert start == 3000
        assert end == 6000

    def test_window_offset_segment(self):
        from gui.dialogs import _middle_third_window
        # [1000, 4000] -> 长度 3000，中间 1/3 = [2000, 3000]
        start, end = _middle_third_window(1000, 4000)
        assert start == 2000
        assert end == 3000


# ── UI-009: 死代码 TranscriptionCompleteDialog 已删除 ────────
@pytest.mark.unit
class TestDeadDialogRemoved:
    def test_transcription_complete_dialog_gone(self):
        import gui.dialogs as dialogs
        assert not hasattr(dialogs, "TranscriptionCompleteDialog")


# ── UI-010: 副标题不再宣称拖拽 ──────────────────────────────
@pytest.mark.unit
class TestMergeOrderSubtitle:
    def test_subtitle_no_drag_claim(self):
        import inspect
        from gui.dialogs import MergeOrderDialog
        src = inspect.getsource(MergeOrderDialog._build)
        assert "拖动" not in src
        assert "拖拽" not in src
        # 仍应描述按钮调整
        assert "按钮" in src
