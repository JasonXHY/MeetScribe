#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型注册表测试
"""

import pytest
from model_registry import (
    MODEL_REGISTRY,
    _VENDOR_ORDER,
    get_vendor_list,
    get_models_for_vendor,
    get_base_url,
    is_free_model,
)


class TestGetVendorList:
    """get_vendor_list 测试"""

    def test_vendor_count(self):
        """验证厂商数量为 10"""
        vendors = get_vendor_list()
        assert len(vendors) == 10

    def test_vendor_order(self):
        """验证厂商排序正确"""
        expected = [
            "小米 MiMo", "智谱 AI", "阿里巴巴", "DeepSeek", "腾讯混元",
            "百度文心", "月之暗面 Kimi", "讯飞星火", "百川智能", "MiniMax",
        ]
        assert get_vendor_list() == expected

    def test_returns_list(self):
        """验证返回类型为列表"""
        result = get_vendor_list()
        assert isinstance(result, list)

    def test_all_vendors_in_registry(self):
        """验证列表中所有厂商都在注册表中"""
        for vendor in get_vendor_list():
            assert vendor in MODEL_REGISTRY


class TestGetModelsForVendor:
    """get_models_for_vendor 测试"""

    def test_xiaomi_models(self):
        """验证小米厂商的模型列表"""
        models = get_models_for_vendor("小米 MiMo")
        assert "mimo-v2.5-pro" in models
        assert "mimo-v2.5" in models
        assert len(models) == 2

    def test_unknown_vendor(self):
        """验证未知厂商返回空列表"""
        models = get_models_for_vendor("不存在的厂商")
        assert models == []

    def test_returns_list(self):
        """验证返回类型为列表"""
        for vendor in _VENDOR_ORDER:
            models = get_models_for_vendor(vendor)
            assert isinstance(models, list)
            assert len(models) > 0


class TestGetBaseUrl:
    """get_base_url 测试"""

    def test_xiaomi_token_plan(self):
        """验证小米 Token Plan 端点"""
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "token_plan")
        assert url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_xiaomi_paygo(self):
        """验证小米按量计费端点"""
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "paygo")
        assert url == "https://api.xiaomimimo.com/v1"

    def test_zhipu_different_urls(self):
        """验证智谱两种模式使用不同端点"""
        url_tp = get_base_url("智谱 AI", "glm-4.7-flash", "token_plan")
        url_pg = get_base_url("智谱 AI", "glm-4.7-flash", "paygo")
        assert url_tp == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert url_pg == "https://open.bigmodel.cn/api/paas/v4"

    def test_unknown_vendor(self):
        """验证未知厂商返回空字符串"""
        url = get_base_url("不存在的厂商", "model", "token_plan")
        assert url == ""

    def test_unknown_model(self):
        """验证未知模型返回空字符串"""
        url = get_base_url("小米 MiMo", "不存在的模型", "token_plan")
        assert url == ""

    def test_fallback_to_token_plan(self):
        """验证未知访问模式回退到 token_plan"""
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "unknown_mode")
        assert url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_alibaba_url(self):
        """验证阿里端点"""
        url = get_base_url("阿里巴巴", "qwen3.7-max", "token_plan")
        assert url == "https://token-plan.cn-beijing.maas.aliuncs.com/v1"

    def test_deepseek_url(self):
        """验证 DeepSeek 端点"""
        url = get_base_url("DeepSeek", "deepseek-v4-flash", "token_plan")
        assert url == "https://api.deepseek.com/v1"


class TestIsFreeModel:
    """is_free_model 测试"""

    def test_free_models_detected(self):
        """验证免费模型检测"""
        assert is_free_model("glm-4.7-flash") is True
        assert is_free_model("glm-5-turbo") is True
        assert is_free_model("spark-lite") is True
        assert is_free_model("Baichuan-M3-Plus") is True

    def test_paid_models_not_free(self):
        """验证付费模型不被标记为免费"""
        assert is_free_model("mimo-v2.5-pro") is False
        assert is_free_model("glm-5") is False
        assert is_free_model("qwen3.7-max") is False

    def test_free_keyword(self):
        """验证模型名包含 free 关键字时识别为免费"""
        assert is_free_model("some-model-free") is True
        assert is_free_model("FREE-model") is True
