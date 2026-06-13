#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 模型注册表
支持多家国内大模型厂商的 API 端点管理
"""

import logging

logger = logging.getLogger("MeetScribe")

# ── 厂商排序 ──────────────────────────────────────────────

_VENDOR_ORDER = [
    "小米", "智谱", "阿里", "腾讯", "百度",
    "DeepSeek", "月之暗面", "零一万物", "讯飞", "百川", "MiniMax",
]

# ── 模型注册表 ────────────────────────────────────────────
# 每个厂商包含：
#   models: dict[model_name, {token_plan: url, paygo: url}]
#   is_same_url: bool — Token Plan 和按量计费使用相同端点

MODEL_REGISTRY = {
    "小米": {
        "models": {
            "mimo-v2.5-pro": {
                "token_plan": "https://api.xiaomimimo.com/v1",
                "paygo": "https://api.xiaomimimo.com/v1",
            },
            "mimo-v2.5": {
                "token_plan": "https://api.xiaomimimo.com/v1",
                "paygo": "https://api.xiaomimimo.com/v1",
            },
            "mimo-v2-flash": {
                "token_plan": "https://api.xiaomimimo.com/v1",
                "paygo": "https://api.xiaomimimo.com/v1",
            },
        },
        "is_same_url": True,
    },
    "智谱": {
        "models": {
            "glm-4-plus": {
                "token_plan": "https://open.bigmodel.cn/api/paas/v4",
                "paygo": "https://open.bigmodel.cn/api/paas/v4",
            },
            "glm-4-flash": {
                "token_plan": "https://open.bigmodel.cn/api/paas/v4",
                "paygo": "https://open.bigmodel.cn/api/paas/v4",
            },
            "glm-4-air": {
                "token_plan": "https://open.bigmodel.cn/api/paas/v4",
                "paygo": "https://open.bigmodel.cn/api/paas/v4",
            },
        },
        "is_same_url": True,
    },
    "阿里": {
        "models": {
            "qwen-max": {
                "token_plan": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "qwen-plus": {
                "token_plan": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "qwen-turbo": {
                "token_plan": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "paygo": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
        },
        "is_same_url": True,
    },
    "腾讯": {
        "models": {
            "hunyuan-pro": {
                "token_plan": "https://api.lkeap.cloud.tencent.com/v1",
                "paygo": "https://api.lkeap.cloud.tencent.com/v1",
            },
            "hunyuan-standard": {
                "token_plan": "https://api.lkeap.cloud.tencent.com/v1",
                "paygo": "https://api.lkeap.cloud.tencent.com/v1",
            },
            "hunyuan-lite": {
                "token_plan": "https://api.lkeap.cloud.tencent.com/v1",
                "paygo": "https://api.lkeap.cloud.tencent.com/v1",
            },
        },
        "is_same_url": True,
    },
    "百度": {
        "models": {
            "ernie-4.0-turbo-8k": {
                "token_plan": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
                "paygo": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
            },
            "ernie-3.5-8k": {
                "token_plan": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
                "paygo": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
            },
            "ernie-speed-8k": {
                "token_plan": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
                "paygo": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
            },
        },
        "is_same_url": True,
    },
    "DeepSeek": {
        "models": {
            "deepseek-chat": {
                "token_plan": "https://api.deepseek.com/v1",
                "paygo": "https://api.deepseek.com/v1",
            },
            "deepseek-reasoner": {
                "token_plan": "https://api.deepseek.com/v1",
                "paygo": "https://api.deepseek.com/v1",
            },
        },
        "is_same_url": True,
    },
    "月之暗面": {
        "models": {
            "moonshot-v1-8k": {
                "token_plan": "https://api.moonshot.cn/v1",
                "paygo": "https://api.moonshot.cn/v1",
            },
            "moonshot-v1-32k": {
                "token_plan": "https://api.moonshot.cn/v1",
                "paygo": "https://api.moonshot.cn/v1",
            },
            "moonshot-v1-128k": {
                "token_plan": "https://api.moonshot.cn/v1",
                "paygo": "https://api.moonshot.cn/v1",
            },
        },
        "is_same_url": True,
    },
    "零一万物": {
        "models": {
            "yi-large": {
                "token_plan": "https://api.lingyiwanwu.com/v1",
                "paygo": "https://api.lingyiwanwu.com/v1",
            },
            "yi-medium": {
                "token_plan": "https://api.lingyiwanwu.com/v1",
                "paygo": "https://api.lingyiwanwu.com/v1",
            },
            "yi-lightning": {
                "token_plan": "https://api.lingyiwanwu.com/v1",
                "paygo": "https://api.lingyiwanwu.com/v1",
            },
        },
        "is_same_url": True,
    },
    "讯飞": {
        "models": {
            "generalv3.5": {
                "token_plan": "https://spark-api-open.xf-yun.com/v1",
                "paygo": "https://spark-api-open.xf-yun.com/v1",
            },
            "generalv3": {
                "token_plan": "https://spark-api-open.xf-yun.com/v1",
                "paygo": "https://spark-api-open.xf-yun.com/v1",
            },
            "4.0Ultra": {
                "token_plan": "https://spark-api-open.xf-yun.com/v1",
                "paygo": "https://spark-api-open.xf-yun.com/v1",
            },
        },
        "is_same_url": True,
    },
    "百川": {
        "models": {
            "Baichuan4": {
                "token_plan": "https://api.baichuan-ai.com/v1",
                "paygo": "https://api.baichuan-ai.com/v1",
            },
            "Baichuan3-Turbo": {
                "token_plan": "https://api.baichuan-ai.com/v1",
                "paygo": "https://api.baichuan-ai.com/v1",
            },
            "Baichuan2-Turbo": {
                "token_plan": "https://api.baichuan-ai.com/v1",
                "paygo": "https://api.baichuan-ai.com/v1",
            },
        },
        "is_same_url": True,
    },
    "MiniMax": {
        "models": {
            "MiniMax-Text-01": {
                "token_plan": "https://api.minimax.chat/v1",
                "paygo": "https://api.minimax.chat/v1",
            },
            "abab6.5s-chat": {
                "token_plan": "https://api.minimax.chat/v1",
                "paygo": "https://api.minimax.chat/v1",
            },
            "abab5.5-chat": {
                "token_plan": "https://api.minimax.chat/v1",
                "paygo": "https://api.minimax.chat/v1",
            },
        },
        "is_same_url": True,
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
        "按量计费": "paygo",
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
        "mimo-v2-flash",
        "glm-4-flash",
        "qwen-turbo",
        "ernie-speed-8k",
        "deepseek-chat",
        "yi-lightning",
    }
    if model_name in free_models:
        return True
    if "free" in model_name.lower():
        return True
    return False
