#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 模型注册表
支持多家国内大模型厂商的 API 端点管理

更新日期：2026-06-15
数据来源：docs/model-registry-update.md（基于各厂商官方公开信息整理）
"""

import logging

logger = logging.getLogger("MeetScribe")

# ── 厂商排序 ──────────────────────────────────────────────

_VENDOR_ORDER = [
    "小米 MiMo", "智谱 AI", "阿里巴巴", "DeepSeek", "腾讯混元",
    "百度文心", "月之暗面 Kimi", "讯飞星火", "百川智能", "MiniMax",
]

# ── 模型注册表 ────────────────────────────────────────────
# 每个模型包含 token_plan 和 paygo 两种 URL（不同接入模式对应不同端点）

MODEL_REGISTRY = {
    "小米 MiMo": {
        "models": {
            "mimo-v2.5-pro": {
                "token_plan": "https://token-plan-cn.xiaomimimo.com/v1",
                "paygo": "https://api.xiaomimimo.com/v1",
            },
            "mimo-v2.5": {
                "token_plan": "https://token-plan-cn.xiaomimimo.com/v1",
                "paygo": "https://api.xiaomimimo.com/v1",
            },
        },
    },
    "智谱 AI": {
        "models": {
            "glm-4.7-flash": {
                "token_plan": "https://open.bigmodel.cn/api/coding/paas/v4",
                "paygo": "https://open.bigmodel.cn/api/paas/v4",
            },
            "glm-5-turbo": {
                "token_plan": "https://open.bigmodel.cn/api/coding/paas/v4",
                "paygo": "https://open.bigmodel.cn/api/paas/v4",
            },
            "glm-5": {
                "token_plan": "https://open.bigmodel.cn/api/coding/paas/v4",
                "paygo": "https://open.bigmodel.cn/api/paas/v4",
            },
        },
    },
    "阿里巴巴": {
        "models": {
            "qwen3.7-max": {
                "token_plan": "https://token-plan.cn-beijing.maas.aliuncs.com/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "qwen3.7-plus": {
                "token_plan": "https://token-plan.cn-beijing.maas.aliuncs.com/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "qwen3.5-plus": {
                "token_plan": "https://token-plan.cn-beijing.maas.aliuncs.com/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "qwen3.5-flash": {
                "token_plan": "https://token-plan.cn-beijing.maas.aliuncs.com/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
        },
    },
    "DeepSeek": {
        "models": {
            "deepseek-v4-pro": {
                "token_plan": "https://api.deepseek.com/v1",
                "paygo": "https://api.deepseek.com/v1",
            },
            "deepseek-v4-flash": {
                "token_plan": "https://api.deepseek.com/v1",
                "paygo": "https://api.deepseek.com/v1",
            },
        },
    },
    "腾讯混元": {
        "models": {
            "hunyuan-turbos": {
                "token_plan": "https://api.lkeap.cloud.tencent.com/plan/v1",
                "paygo": "https://api.hunyuan.cloud.tencent.com/v1",
            },
            "hunyuan-t1": {
                "token_plan": "https://api.lkeap.cloud.tencent.com/plan/v1",
                "paygo": "https://api.hunyuan.cloud.tencent.com/v1",
            },
        },
    },
    "百度文心": {
        "models": {
            "ernie-5.0": {
                "token_plan": "https://qianfan.baidubce.com/v2",
                "paygo": "https://qianfan.baidubce.com/v2",
            },
            "ernie-4.5-turbo-128k-preview": {
                "token_plan": "https://qianfan.baidubce.com/v2",
                "paygo": "https://qianfan.baidubce.com/v2",
            },
            "ernie-x1.1": {
                "token_plan": "https://qianfan.baidubce.com/v2",
                "paygo": "https://qianfan.baidubce.com/v2",
            },
        },
    },
    "月之暗面 Kimi": {
        "models": {
            "kimi-k2.6": {
                "token_plan": "https://api.kimi.com/coding/v1",
                "paygo": "https://api.moonshot.cn/v1",
            },
            "kimi-k2.7-code": {
                "token_plan": "https://api.kimi.com/coding/v1",
                "paygo": "https://api.moonshot.cn/v1",
            },
        },
    },
    "讯飞星火": {
        "models": {
            "spark-lite": {
                "token_plan": "https://maas-token-api.cn-huabei-1.xf-yun.com/v2",
                "paygo": "https://spark-api-open.xf-yun.com/v1",
            },
            "spark-max": {
                "token_plan": "https://maas-token-api.cn-huabei-1.xf-yun.com/v2",
                "paygo": "https://spark-api-open.xf-yun.com/v1",
            },
        },
    },
    "百川智能": {
        "models": {
            "Baichuan-M3-Plus": {
                "token_plan": "https://api.baichuan-ai.com/v1",
                "paygo": "https://api.baichuan-ai.com/v1",
            },
            "Baichuan-M3": {
                "token_plan": "https://api.baichuan-ai.com/v1",
                "paygo": "https://api.baichuan-ai.com/v1",
            },
        },
    },
    "MiniMax": {
        "models": {
            "MiniMax-M3": {
                "token_plan": "https://api.minimax.chat/v1/text/chatcompletion_v2",
                "paygo": "https://api.minimax.chat/v1/text/chatcompletion_v2",
            },
            "abab7-chat": {
                "token_plan": "https://api.minimax.chat/v1/text/chatcompletion_v2",
                "paygo": "https://api.minimax.chat/v1/text/chatcompletion_v2",
            },
        },
    },
}


def get_vendor_list() -> list:
    """返回厂商列表（按自定义排序）"""
    return list(_VENDOR_ORDER)


def get_models_for_vendor(vendor: str) -> list:
    """
    返回指定厂商的模型名称列表

    Args:
        vendor: 厂商名称

    Returns:
        模型名称列表，如果厂商不存在返回空列表
    """
    vendor_data = MODEL_REGISTRY.get(vendor)
    if not vendor_data:
        return []
    return list(vendor_data["models"].keys())


def get_base_url(vendor: str, model: str, access_mode: str = "token_plan") -> str:
    """
    获取指定模型的 API 端点地址

    Args:
        vendor:      厂商名称
        model:       模型名称
        access_mode: 访问模式，"token_plan" 或 "paygo"（也接受中文显示名）

    Returns:
        API 端点 URL；如果厂商或模型不存在返回空字符串
    """
    vendor_data = MODEL_REGISTRY.get(vendor)
    if not vendor_data:
        return ""

    model_data = vendor_data["models"].get(model)
    if not model_data:
        return ""

    # Map Chinese display names / display names to registry keys
    mode_map = {
        "Token Plan": "token_plan",
        "token_plan": "token_plan",
        "按量计费": "paygo",
        "paygo": "paygo",
    }
    key = mode_map.get(access_mode, "token_plan")

    url = model_data.get(key, "")
    if not url:
        # 回退到 token_plan
        url = model_data.get("token_plan", "")
    return url


def is_free_model(model_name: str) -> bool:
    """
    判断模型是否为免费模型

    免费模型包含 "free" 关键字，或属于以下已知免费模型列表。
    """
    free_models = {
        "glm-4.7-flash",       # 智谱：永久免费
        "glm-5-turbo",         # 智谱：限时免费
        "spark-lite",          # 讯飞：永久免费
        "Baichuan-M3-Plus",   # 百川：医疗领域免费
    }
    if model_name in free_models:
        return True
    if "free" in model_name.lower():
        return True
    return False
