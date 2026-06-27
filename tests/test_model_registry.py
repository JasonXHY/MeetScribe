#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型注册表相关功能测试。"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from model_registry import (
    MODEL_REGISTRY,
    _VENDOR_ORDER,
    get_vendor_list,
    get_models_for_vendor,
    get_base_url,
    is_free_model,
)

pytestmark = pytest.mark.integration


class TestGetVendorList:
    def test_vendor_count(self):
        vendors = get_vendor_list()
        assert len(vendors) == 10

    def test_vendor_order(self):
        expected = [
            "小米 MiMo", "智谱 AI", "阿里巴巴", "DeepSeek", "腾讯混元",
            "百度文心", "月之暗面 Kimi", "讯飞星火", "百川智能", "MiniMax",
        ]
        assert get_vendor_list() == expected

    def test_all_vendors_in_registry(self):
        for vendor in get_vendor_list():
            assert vendor in MODEL_REGISTRY


class TestGetModelsForVendor:
    def test_xiaomi_models(self):
        models = get_models_for_vendor("小米 MiMo")
        assert "mimo-v2.5-pro" in models
        assert "mimo-v2.5" in models
        assert len(models) == 2

    def test_unknown_vendor(self):
        models = get_models_for_vendor("不存在的厂商")
        assert models == []

    def test_returns_list(self):
        for vendor in _VENDOR_ORDER:
            models = get_models_for_vendor(vendor)
            assert isinstance(models, list)
            assert len(models) > 0


class TestGetBaseUrl:
    def test_xiaomi_token_plan(self):
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "token_plan")
        assert url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_xiaomi_paygo(self):
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "paygo")
        assert url == "https://api.xiaomimimo.com/v1"

    def test_zhipu_different_urls(self):
        url_tp = get_base_url("智谱 AI", "glm-4.7-flash", "token_plan")
        url_pg = get_base_url("智谱 AI", "glm-4.7-flash", "paygo")
        assert url_tp == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert url_pg == "https://open.bigmodel.cn/api/paas/v4"

    def test_unknown_vendor(self):
        url = get_base_url("不存在的厂商", "model", "token_plan")
        assert url == ""

    def test_unknown_model(self):
        url = get_base_url("小米 MiMo", "不存在的模型", "token_plan")
        assert url == ""

    def test_fallback_to_token_plan(self):
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "unknown_mode")
        assert url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_alibaba_url(self):
        url = get_base_url("阿里巴巴", "qwen3.7-max", "token_plan")
        assert url == "https://token-plan.cn-beijing.maas.aliuncs.com/v1"

    def test_deepseek_url(self):
        url = get_base_url("DeepSeek", "deepseek-v4-flash", "token_plan")
        assert url == "https://api.deepseek.com/v1"


class TestIsFreeModel:
    def test_free_models_detected(self):
        assert is_free_model("glm-4.7-flash") is True
        assert is_free_model("glm-5-turbo") is True
        assert is_free_model("spark-lite") is True
        assert is_free_model("Baichuan-M3-Plus") is True

    def test_paid_models_not_free(self):
        assert is_free_model("mimo-v2.5-pro") is False
        assert is_free_model("glm-5") is False
        assert is_free_model("qwen3.7-max") is False

    def test_free_keyword(self):
        assert is_free_model("some-model-free") is True
        assert is_free_model("FREE-model") is True


# ══════════════════════════════════════════════════════════
#  厂商名规范化 (vendor_map) (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestVendorNormalization:
    """厂商名规范化：旧版短名 → 新版全名"""

    def test_xiaomi_mapping(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d="": {
            "ai_vendor": "小米",
            "ai_user_api_key": "",
            "ai_default_api_key": "sk-test",
            "ai_model": "mimo-v2.5",
            "ai_access_mode": "按量计费",
        }.get(k, d)
        handler._app = mock_app
        with patch('ai_service.AIService') as MockAI:
            mock_ai = MagicMock()
            MockAI.return_value = mock_ai
            handler._get_ai_service()
            call_kwargs = MockAI.call_args
            assert call_kwargs[1]['vendor'] == '小米 MiMo' or call_kwargs[0][0] == '小米 MiMo'


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
        seg = "[00:00] **Speaker 1**: " + ("内容句。" * 200) + "\n"
        seg2 = "[05:00] **Speaker 2**: " + ("另一段。" * 200) + "\n"
        text = seg + seg2
        chunks = AIService._split_transcript_chunks(text, max_chars=400)
        assert len(chunks) >= 2
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
        assert "Speaker 1" in result
        assert "[00:00]" in result

    def test_returns_none_without_api_key(self):
        from ai_service import AIService
        svc = AIService(vendor="小米", api_key="")
        assert svc.generate_correction("任意文本") is None

    def test_api_failure_falls_back_to_original(self):
        """API 抛错时不得向上抛出；分块保留原文。"""
        svc = self._service()
        original = "**[00:00] Speaker 1**\n一些文本。"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        with patch.object(type(svc), "ai_client", new=mock_client):
            result = svc.generate_correction(original)
        assert result is None

    def test_multi_chunk_each_corrected(self):
        """分块后每块都送 LLM；返回拼接结果。"""
        svc = self._service()
        seg = "[00:00] **Speaker 1**: " + ("呃内容句。" * 600) + "\n"
        seg2 = "[05:00] **Speaker 2**: " + ("嗯另一段。" * 600) + "\n"
        original = seg + seg2

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = \
            lambda **kw: _mock_completion(kw["messages"][1]["content"].replace("呃", "").replace("嗯", "") + "X")
        with patch.object(type(svc), "ai_client", new=mock_client):
            result = svc.generate_correction(original)

        assert mock_client.chat.completions.create.call_count >= 2
        assert result is not None
        assert result != original
