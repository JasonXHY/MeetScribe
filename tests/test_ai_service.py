#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIService Ollama 本地 LLM 测试（AI-005 / SET-016）
+ T-G16: generate_correction 纠错行为（AI-002）。
"""

import pytest
from unittest.mock import patch, MagicMock


def _mock_completion(text):
    """构造一个 chat.completions.create 的返回替身。"""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


@pytest.mark.unit
class TestOllamaClient:
    """Ollama 客户端使用构造函数传入的地址 / 模型"""

    def test_ollama_client_uses_configured_url(self):
        """ollama_client 应以配置的 base_url 构造 OpenAI 客户端"""
        from ai_service import AIService

        svc = AIService(ollama_url="http://host:1234/v1", ollama_model="m")
        assert svc.ollama_url == "http://host:1234/v1"
        assert svc.ollama_model == "m"

        with patch("ai_service.OpenAI") as MockOpenAI:
            client = svc.ollama_client
            assert client is MockOpenAI.return_value
            _, kwargs = MockOpenAI.call_args
            assert kwargs["base_url"] == "http://host:1234/v1"

    def test_ollama_defaults_when_none(self):
        """未传入时使用默认地址与模型"""
        from ai_service import (
            AIService,
            _OLLAMA_DEFAULT_URL,
            _OLLAMA_DEFAULT_MODEL,
        )

        svc = AIService()
        assert svc.ollama_url == _OLLAMA_DEFAULT_URL
        assert svc.ollama_model == _OLLAMA_DEFAULT_MODEL

    def test_extract_speaker_names_degrades_when_unreachable(self):
        """Ollama 不可达时返回空字典，不抛未捕获异常"""
        from ai_service import AIService

        svc = AIService(ollama_url="http://127.0.0.1:9/v1", ollama_model="m")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("connection refused")
        with patch.object(type(svc), "ollama_client", new=mock_client):
            result = svc.extract_speaker_names("text", [0, 1])
        assert result == {}


@pytest.mark.unit
class TestSplitTranscriptChunks:
    """AI-002：分块逻辑 _split_transcript_chunks"""

    def test_short_text_single_chunk(self):
        from ai_service import AIService
        chunks = AIService._split_transcript_chunks("短文本", max_chars=4000)
        assert chunks == ["短文本"]

    def test_long_text_splits_at_speaker_boundary(self):
        from ai_service import AIService
        # 说话人标签形如 "[00:00] **label**: ..."（llm-md 格式，行首为 [）。
        # 每段超过 max_chars*0.5，确保在下一个说话人标签处断块。
        seg = "[00:00] **Speaker 1**: " + ("内容句。" * 200) + "\n"
        seg2 = "[05:00] **Speaker 2**: " + ("另一段。" * 200) + "\n"
        text = seg + seg2
        chunks = AIService._split_transcript_chunks(text, max_chars=400)
        assert len(chunks) >= 2
        # 后续分块应以说话人标签起始（在边界断开）
        assert chunks[1].lstrip().startswith("[")


@pytest.mark.unit
class TestGenerateCorrection:
    """AI-002：generate_correction 行为"""

    def _service(self):
        from ai_service import AIService
        return AIService(vendor="小米", model="mimo-v2.5-pro", api_key="test-key")

    def test_corrects_and_preserves_speaker_labels(self):
        svc = self._service()
        original = "**[00:00] Speaker 1**\n领导师讲话呃完毕。"
        corrected_text = "**[00:00] Speaker 1**\n领导的讲话完毕。"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion(corrected_text)
        with patch.object(type(svc), "ai_client", new=mock_client):
            result = svc.generate_correction(original)

        assert result == corrected_text
        # 说话人标签与时间戳保留
        assert "Speaker 1" in result
        assert "[00:00]" in result

    def test_returns_none_without_api_key(self):
        from ai_service import AIService
        svc = AIService(vendor="小米", api_key="")  # 无 key
        assert svc.generate_correction("任意文本") is None

    def test_api_failure_falls_back_to_original(self):
        """API 抛错时不得向上抛出；分块保留原文。"""
        svc = self._service()
        original = "**[00:00] Speaker 1**\n一些文本。"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        with patch.object(type(svc), "ai_client", new=mock_client):
            # 不抛异常
            result = svc.generate_correction(original)
        # 所有分块失败保留原文 → 与原文相同 → 实现约定返回 None（无变化）
        assert result is None

    def test_multi_chunk_each_corrected(self):
        """分块后每块都送 LLM；返回拼接结果。

        generate_correction 内部硬编码 max_chars=4000，需让每段都足够长
        （> 2000 字）才能触发说话人边界换块。
        """
        svc = self._service()
        seg = "[00:00] **Speaker 1**: " + ("呃内容句。" * 600) + "\n"
        seg2 = "[05:00] **Speaker 2**: " + ("嗯另一段。" * 600) + "\n"
        original = seg + seg2

        mock_client = MagicMock()
        # 每次调用返回去掉填充词的"纠错版"
        mock_client.chat.completions.create.side_effect = \
            lambda **kw: _mock_completion(kw["messages"][1]["content"].replace("呃", "").replace("嗯", "") + "X")
        with patch.object(type(svc), "ai_client", new=mock_client):
            result = svc.generate_correction(original)

        # 多次调用（分块 >1）
        assert mock_client.chat.completions.create.call_count >= 2
        assert result is not None
        assert result != original
