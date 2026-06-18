#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-G14 — 多格式输出测试（TRN-008: MD/TXT/SRT/JSON/HTML/CSV/VTT）。

覆盖两处实现来源：
- ``transcriber.Transcriber._fmt_*`` 与其 ``_format`` 分发（md/txt/json/html）。
- ``formatters.TranscriptFormatter.*``（srt/csv/vtt 委托来源）。

不依赖 funasr：``Transcriber(model_cache_dir=None)`` 不加载模型；
formatters 为纯函数。
"""

import json

import pytest

from formatters import TranscriptFormatter
from transcriber import Transcriber

pytestmark = pytest.mark.unit


# ── 固定测试数据 ─────────────────────────────────────────────

# 转写器内部格式：spk 键为说话人 ID，start/end 为毫秒。
SENTENCES = [
    {"start": 0, "end": 2000, "spk": 0, "text": "大家好，欢迎参加会议。"},
    {"start": 2500, "end": 5000, "spk": 1, "text": "今天讨论第三季度计划。"},
    {"start": 5500, "end": 8000, "spk": 0, "text": "好的，我先汇报数据。"},
]

# TranscriptFormatter 格式：speaker 键为索引，start/end 为毫秒。
SEGMENTS = [
    {"start": 0, "end": 2000, "speaker": 0, "text": "大家好，欢迎参加会议。"},
    {"start": 2500, "end": 5000, "speaker": 1, "text": "今天讨论第三季度计划。"},
    {"start": 5500, "end": 8000, "speaker": 0, "text": "好的，我先汇报数据。"},
]

SPEAKERS = ["张三", "李四"]
NAMES = {"0": "张三", "1": "李四"}


@pytest.fixture
def tr():
    """不加载模型的 Transcriber 实例（仅用其纯格式化方法）。"""
    return Transcriber(model_cache_dir=None)


# ── transcriber._fmt_* （md / txt / json / html） ─────────────


class TestTranscriberMarkdown:
    def test_md_has_title_and_speaker_labels(self, tr):
        out = tr._format(SENTENCES, "md", NAMES, "meeting.wav", 12.3)
        assert out.startswith("# Meeting Transcription")
        assert "张三" in out
        assert "李四" in out
        # 全部文本都应出现
        for s in SENTENCES:
            assert s["text"] in out


class TestTranscriberText:
    def test_txt_is_plain_and_contains_all_text(self, tr):
        out = tr._format(SENTENCES, "txt", NAMES, "meeting.wav", 1.0)
        # 纯文本不应含 markdown 标题或 HTML 标签
        assert "#" not in out
        assert "<" not in out
        for s in SENTENCES:
            assert s["text"] in out
        # 说话人名称随文本一起出现
        assert "张三" in out and "李四" in out


class TestTranscriberJson:
    def test_json_parses_and_segment_count_matches(self, tr):
        out = tr._format(SENTENCES, "json", NAMES, "meeting.wav", 9.9)
        data = json.loads(out)
        assert len(data["segments"]) == len(SENTENCES)
        assert data["speaker_count"] == 2
        assert data["segments"][0]["speaker"] == "张三"
        assert data["segments"][0]["text"] == SENTENCES[0]["text"]


class TestTranscriberHtml:
    def test_html_has_valid_tag_structure(self, tr):
        out = tr._format(SENTENCES, "html", NAMES, "meeting.wav", 3.3)
        assert out.lstrip().startswith("<!DOCTYPE html>")
        assert "<html" in out and "</html>" in out
        assert "<body>" in out and "</body>" in out
        assert "张三" in out

    def test_html_escapes_special_chars_in_text(self, tr):
        """TRN-008/HTML：正文中的 < > & 必须转义，避免破坏标签结构或 XSS。"""
        sentences = [
            {"start": 0, "end": 1000, "spk": 0,
             "text": "条件是 a < b && c > d <script>alert(1)</script>"},
        ]
        out = tr._format(sentences, "html", NAMES, "meeting.wav", 1.0)
        # 原始未转义的危险片段不得出现在输出中
        assert "<script>" not in out
        # 应以转义实体出现
        assert "&lt;script&gt;" in out
        assert "&amp;&amp;" in out


# ── formatters.TranscriptFormatter （srt / csv / vtt + 镜像） ──


class TestFormatterSrt:
    def test_srt_has_index_timecode_text(self, tr):
        out = tr._format(SENTENCES, "srt", NAMES, "meeting.wav", 1.0)
        lines = out.splitlines()
        assert lines[0] == "1"
        # SRT 时间码 HH:MM:SS,mmm --> HH:MM:SS,mmm
        assert "-->" in lines[1]
        assert "," in lines[1]
        assert SENTENCES[0]["text"] in out

    def test_srt_direct_formatter_numbering(self):
        out = TranscriptFormatter.format_srt(SEGMENTS)
        # 三段 → 序号 1/2/3 各出现
        assert "\n1\n" in "\n" + out
        assert "2" in out and "3" in out


class TestFormatterVtt:
    def test_vtt_has_webvtt_header_and_timecode(self, tr):
        out = tr._format(SENTENCES, "vtt", NAMES, "meeting.wav", 1.0)
        assert out.startswith("WEBVTT")
        # VTT 时间码用 . 分隔毫秒
        assert "-->" in out
        assert "." in out.split("-->")[0].splitlines()[-1]

    def test_vtt_direct_formatter(self):
        out = TranscriptFormatter.format_vtt(SEGMENTS, SPEAKERS)
        assert out.startswith("WEBVTT")
        assert SEGMENTS[0]["text"] in out


class TestFormatterCsv:
    def test_csv_has_header_and_row_per_segment(self, tr):
        out = tr._format(SENTENCES, "csv", NAMES, "meeting.wav", 1.0)
        rows = [r for r in out.splitlines() if r.strip()]
        # 1 表头 + 3 数据行
        assert len(rows) == 1 + len(SENTENCES)
        assert "序号" in rows[0]
        assert "内容" in rows[0]

    def test_csv_escapes_comma_and_quote(self):
        """CSV 特殊字符（逗号、引号）必须被正确转义/包裹。"""
        import csv as _csv
        import io

        segments = [
            {"start": 0, "end": 1000, "speaker": 0,
             "text": '他说："你好, 世界"'},
        ]
        out = TranscriptFormatter.format_csv(segments, ["张三"])
        # 用 csv 解析器读回，确认字段未被逗号/引号破坏
        reader = list(_csv.reader(io.StringIO(out)))
        assert reader[0][0] == "序号"  # 表头
        data_row = reader[1]
        # 含逗号和引号的文本应作为单个字段完整读回
        assert data_row[-1] == '他说："你好, 世界"'


# ── 边界条件 ─────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.parametrize("fmt", ["md", "txt", "json", "html", "srt", "csv", "vtt"])
    def test_empty_segments_does_not_crash(self, tr, fmt):
        out = tr._format([], fmt, {}, "empty.wav", 0.0)
        assert isinstance(out, str)

    @pytest.mark.parametrize("fmt", ["md", "txt", "json", "html", "srt", "csv", "vtt"])
    def test_single_segment(self, tr, fmt):
        one = [{"start": 0, "end": 1000, "spk": 0, "text": "只有一句话。"}]
        out = tr._format(one, fmt, NAMES, "one.wav", 1.0)
        assert "只有一句话。" in out

    def test_empty_json_is_valid(self, tr):
        out = tr._format([], "json", {}, "empty.wav", 0.0)
        data = json.loads(out)
        assert data["segments"] == []
        assert data["speaker_count"] == 0
