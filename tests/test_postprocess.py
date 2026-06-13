#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Transcriber._postprocess_sentences()"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from transcriber import Transcriber


def _make_sentence(text, spk=0, start=0, end=1000):
    return {"text": text, "spk": spk, "start": start, "end": end}


class TestPostprocessUnk:
    """过滤 <unk> 标记"""

    def test_removes_unk_tokens(self):
        t = Transcriber()
        sentences = [_make_sentence("你好<unk>世界")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "<unk>" not in result[0]["text"]
        assert result[0]["text"] == "你好世界"

    def test_removes_multiple_unk(self):
        t = Transcriber()
        sentences = [_make_sentence("<unk>今天<unk>开会<unk>")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "<unk>" not in result[0]["text"]

    def test_all_unk_leaves_empty_skipped(self):
        """如果去掉 <unk> 后只剩标点或过短，应跳过"""
        t = Transcriber()
        sentences = [_make_sentence("<unk><unk>")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 0


class TestPostprocessPunctuation:
    """清理连续标点"""

    def test_cleans_consecutive_chinese_punct(self):
        t = Transcriber()
        sentences = [_make_sentence("你好？。！世界")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        # 连续中文标点应被替换为单个逗号
        assert "？。！" not in result[0]["text"]

    def test_cleans_trailing_punct(self):
        t = Transcriber()
        sentences = [_make_sentence("今天开会，，，")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert not result[0]["text"].endswith("，")
        assert not result[0]["text"].endswith(",")

    def test_cleans_leading_punct(self):
        t = Transcriber()
        sentences = [_make_sentence("，，，今天开会")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert not result[0]["text"].startswith("，")


class TestPostprocessShortMerge:
    """合并碎片化短句"""

    def test_merges_short_sentence_into_previous(self):
        t = Transcriber()
        sentences = [
            _make_sentence("今天开会讨论", spk=0, start=0, end=1000),
            _make_sentence("预算", spk=0, start=1100, end=1500),
        ]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "预算" in result[0]["text"]

    def test_does_not_merge_different_speakers(self):
        t = Transcriber()
        sentences = [
            _make_sentence("今天开会讨论", spk=0, start=0, end=1000),
            _make_sentence("预算", spk=1, start=1100, end=1500),
        ]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 2

    def test_does_not_merge_long_gap(self):
        t = Transcriber()
        sentences = [
            _make_sentence("今天开会讨论", spk=0, start=0, end=1000),
            _make_sentence("预算", spk=0, start=5000, end=6000),
        ]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 2


class TestPostprocessEdgeCases:
    """边界情况"""

    def test_empty_input(self):
        t = Transcriber()
        result = t._postprocess_sentences([])
        assert result == []

    def test_single_character_skipped(self):
        t = Transcriber()
        sentences = [_make_sentence("啊")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 0

    def test_normal_text_unchanged(self):
        t = Transcriber()
        sentences = [_make_sentence("今天下午三点开会讨论项目进度")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert result[0]["text"] == "今天下午三点开会讨论项目进度"

    def test_preserves_spk_and_timing(self):
        t = Transcriber()
        sentences = [_make_sentence("测试文本", spk=2, start=5000, end=8000)]
        result = t._postprocess_sentences(sentences)
        assert result[0]["spk"] == 2
        assert result[0]["start"] == 5000
        assert result[0]["end"] == 8000


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
