#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIService Ollama 本地 LLM 测试（AI-005 / SET-016）
"""

import pytest
from unittest.mock import patch, MagicMock


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
