# 模型注册表更新方案

> 基于 2026 年 6 月各厂商官方公开信息整理，仅包含 2025-2026 年发布且仍在服务的模型。
> 
> **重要**：多数厂商的「按量计费」和「Token Plan」使用**不同的 Base URL 和 API Key**，代码中必须根据接入模式字段联动选择正确的 URL。

---

## 一、各厂商接入模式 URL 对照表

这是最关键的差异——同一个厂商，不同计费模式对应的 API 地址不同。

| 厂商 | 按量计费 Base URL | Token Plan / Coding Plan Base URL | API Key 是否共用 |
|------|------------------|-----------------------------------|----------------|
| 小米 MiMo | `https://api.xiaomimimo.com/v1` | `https://token-plan-cn.xiaomimimo.com/v1` | 不共用，Key 格式不同 (tp-xxx vs 普通) |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | `https://open.bigmodel.cn/api/coding/paas/v4` | 同 Key，Coding Plan 有独立 URL |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Token Plan: `https://token-plan.cn-beijing.maas.aliuncs.com/v1` | 不共用，Key 格式不同 (sk-xxx vs tp-xxx) |
| | | Coding Plan: `https://coding.dashscope.aliyuncs.com/v1` | 不共用 (sk-sp-xxx) |
| DeepSeek | `https://api.deepseek.com/v1` | 无 Token Plan | — |
| 腾讯混元 | `https://api.hunyuan.cloud.tencent.com/v1` | `https://api.lkeap.cloud.tencent.com/plan/v1` (OpenAI 兼容) | 不共用，Token Plan 在 TokenHub 控制台生成 |
| 百度千帆 | `https://qianfan.baidubce.com/v2` | Token 福利包共用同一 URL，使用不同 API Key | 不共用 |
| 月之暗面 | `https://api.moonshot.cn/v1` | Coding Plan: `https://api.kimi.com/coding/v1` | 不共用，Coding Plan 有独立 Key |
| 讯飞星火 | `https://spark-api-open.xf-yun.com/v1` | `https://maas-token-api.cn-huabei-1.xf-yun.com/v2` | 不共用，Token Plan 有独立 URL 和 Key |
| 百川智能 | `https://api.baichuan-ai.com/v1` | 无 Token Plan | — |
| MiniMax | `https://api.minimax.chat/v1/text/chatcompletion_v2` | 共用同一 URL，使用订阅 Key | 不共用 (订阅 Key vs 按量 Key) |

---

## 二、各厂商模型详情

### 1. 小米 MiMo

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| MiMo-V2.5-Pro | mimo-v2.5-pro | 128K | 3.0 | 6.0 | 旗舰推理模型 |
| MiMo-V2.5 | mimo-v2.5 | 128K | 1.0 | 2.0 | 标准模型 |

- **按量计费 Base URL**: `https://api.xiaomimimo.com/v1/chat/completions`
- **Token Plan Base URL**: `https://token-plan-cn.xiaomimimo.com/v1/chat/completions`
- **API Key 格式**: 按量计费为普通 API Key；Token Plan 为 `tp-` 开头的订阅 Key
- **兼容**: OpenAI SDK
- **废弃通知**: V2 系列 (mimo-v2-flash, mimo-v2-pro, mimo-v2-turbo) 将于 2026-06-30 停服
- **推荐**: mimo-v2.5-pro（性能最佳），mimo-v2.5（性价比）

---

### 2. 智谱 AI

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| GLM-5.1 | glm-5.1 | 128K | 待确认 | 待确认 | 2026 新旗舰 |
| GLM-5 | glm-5 | 128K | 待确认 | 待确认 | 主力模型 |
| GLM-5-Turbo | glm-5-turbo | 128K | 0 (限时免费) | 0 (限时免费) | 限时免费中 |
| GLM-4.7-Flash | glm-4.7-flash | 128K | 0 | 0 | 完全免费 |

- **按量计费 Base URL**: `https://open.bigmodel.cn/api/paas/v4/chat/completions`
- **Coding Plan Base URL**: `https://open.bigmodel.cn/api/coding/paas/v4/chat/completions`
- **API Key**: Coding Plan 使用相同 Key，但仅在支持的工具中可用
- **免费额度**: GLM-4.7-Flash 永久免费，GLM-5-Turbo 限时免费
- **推荐**: GLM-4.7-Flash（免费首选），GLM-5-Turbo（限时免费性能更好）

> ⚠️ GLM-5.1 和 GLM-5 的按量计费价格需要在智谱官网确认最新数据。

---

### 3. 阿里巴巴 (通义千问)

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| Qwen3.7-Max | qwen3.7-max | 128K | 待确认 | 待确认 | 最新旗舰 |
| Qwen3.7-Plus | qwen3.7-plus | 128K | 待确认 | 待确认 | 均衡选择 |
| Qwen3.5-Plus | qwen3.5-plus | 128K | 待确认 | 待确认 | 上代均衡 |
| Qwen3.5-Flash | qwen3.5-flash | 128K | 待确认 | 待确认 | 快速版 |

- **按量计费 Base URL**: `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
- **Token Plan 团队版 Base URL**: `https://token-plan.cn-beijing.maas.aliuncs.com/v1/chat/completions`
- **Coding Plan Base URL**: `https://coding.dashscope.aliyuncs.com/v1/chat/completions`
- **API Key**: 三种模式互不相通，Key 格式不同
  - 按量计费: `sk-xxx`
  - Token Plan 团队版: `sk-xxx` (在百炼控制台生成)
  - Coding Plan: `sk-sp-xxx`
- **免费额度**: 新用户赠送额度
- **推荐**: qwen3.5-flash（轻量场景），qwen3.7-plus（主力）

> ⚠️ 阿里云百炼平台价格变动频繁，需要在 https://help.aliyun.com/zh/model-studio 确认最新价格。

---

### 4. DeepSeek

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| DeepSeek-V4-Pro | deepseek-v4-pro | 128K | 4.0 | 18.0 | 最新旗舰，深度推理 |
| DeepSeek-V4-Flash | deepseek-v4-flash | 128K | 1.0 | 4.0 | V4 快速版，高性价比 |
| ~~deepseek-chat~~ | deepseek-chat | 64K | 1.0 | 2.0 | ⚠️ 2026-07-24 停服 |
| ~~deepseek-reasoner~~ | deepseek-reasoner | 64K | 4.0 | 18.0 | ⚠️ 2026-07-24 停服 |

- **Base URL**: `https://api.deepseek.com/v1/chat/completions`（唯一，无 Token Plan）
- **兼容**: OpenAI SDK
- **免费额度**: 注册赠送额度
- **废弃通知**: deepseek-chat 和 deepseek-reasoner 将于 2026-07-24 停服
- **推荐**: deepseek-v4-flash（日常使用性价比极高），deepseek-v4-pro（复杂推理）

---

### 5. 腾讯混元

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| 混元 TurboS | hunyuan-turbos | 256K | 0.8 | 2.0 | 快思考旗舰，速度极快 |
| 混元 T1 | hunyuan-t1 | 256K | 1.0 | 4.0 | 深度推理模型 |
| 混元 T1-Vision | hunyuan-t1-vision | 256K | 3.0 | 9.0 | 多模态推理 |

- **按量计费 Base URL**: `https://api.hunyuan.cloud.tencent.com/v1/chat/completions`
- **Token Plan 个人版 Base URL**: `https://api.lkeap.cloud.tencent.com/plan/v1/chat/completions` (OpenAI 兼容)
- **API Key**: Token Plan Key 在腾讯云 TokenHub 控制台生成，与按量计费 Key 不同
- **免费额度**: 首次开通送免费调用额度
- **废弃通知**: 旧版模型 (hunyuan-standard, hunyuan-fast 等) 正在逐步切换升级
- **推荐**: hunyuan-turbos（快思考性价比极高），hunyuan-t1（复杂推理）

---

### 6. 百度 (文心大模型)

| 模型 | model_id | 上下文 | 输入价格 (¥/千token) | 输出价格 (¥/千token) | 备注 |
|------|----------|--------|---------------------|---------------------|------|
| ERNIE 5.0 | ernie-5.0 | 128K | 0.006 | 0.024 | 最新旗舰 |
| ERNIE 4.5 Turbo | ernie-4.5-turbo-128k-preview | 128K | 0.0008 | 0.0032 | 极致性价比 |
| ERNIE X1.1 | ernie-x1.1 | 128K | 0.001 | 0.004 | 推理模型 |

- **Base URL**: `https://qianfan.baidubce.com/v2/chat/completions`（按量计费和 Token 福利包共用）
- **API Key**: Token 福利包使用不同的 API Key（在千帆控制台购买后生成）
- **兼容**: OpenAI SDK（v2 路径）
- **免费额度**: 新用户赠送
- **注意**: 百度价格单位是「元/千token」，换算成百万token 需乘以 1000
  - ERNIE 5.0: 输入 ¥6/百万token，输出 ¥24/百万token
  - ERNIE 4.5 Turbo: 输入 ¥0.8/百万token，输出 ¥3.2/百万token
- **推荐**: ERNIE 4.5 Turbo（性价比极高），ERNIE 5.0（最新旗舰）

---

### 7. 月之暗面 (Kimi)

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| Kimi K2.7 Code | kimi-k2.7-code | 256K | 待确认 | 待确认 | 最新代码模型 |
| Kimi K2.6 | kimi-k2.6 | 256K | 待确认 | 待确认 | 通用大模型 |
| Moonshot v1 | moonshot-v1-8k | 8K | 12.0 | 12.0 | 老模型，仍可用 |
| Moonshot v1 | moonshot-v1-32k | 32K | 24.0 | 24.0 | 老模型，仍可用 |
| Moonshot v1 | moonshot-v1-128k | 128K | 60.0 | 60.0 | 老模型，超长上下文 |

- **按量计费 Base URL**: `https://api.moonshot.cn/v1/chat/completions`
- **Coding Plan Base URL**: `https://api.kimi.com/coding/v1/chat/completions`
- **API Key**: Coding Plan 使用独立 Key，与按量计费 Key 不同
- **免费额度**: 注册赠送
- **推荐**: kimi-k2.6（通用首选），moonshot-v1-8k（轻量场景但价格偏高）

> ⚠️ Kimi K2.7 Code 和 K2.6 的具体价格需在 https://platform.kimi.com 确认。

---

### 8. 零一万物

- **状态**: ⚠️ 已转型，疑似停止模型 API 服务
- 零一万物已将预训练团队打包卖给阿里，转型做 AI Agent 应用
- **建议**: 从模型列表中移除零一万物

---

### 9. 讯飞 (星火大模型)

| 模型 | model_id | 上下文 | 价格 | 备注 |
|------|----------|--------|------|------|
| Spark Lite | spark-lite | 8K | 永久免费 | 轻量级，永久免费 |
| Spark Max | spark-max | 8K | 付费 | 标准商用 |
| Spark X1.5 | spark-4.0-ultra | 8K | 付费（较贵） | Ultra 升级至 X1.5 |

- **按量计费 Base URL**: `https://spark-api-open.xf-yun.com/v1/chat/completions`
- **Token Plan Base URL**: `https://maas-token-api.cn-huabei-1.xf-yun.com/v2/chat/completions`
- **API Key**: 两种模式使用不同的 API Key
- **免费额度**: spark-lite 永久免费
- **推荐**: spark-lite（免费首选），spark-max（需要更好效果时）

> ⚠️ 讯飞的 model_id 可能需要在实际调用中验证。Token Plan 的 URL 路径版本为 v2（不是 v1）。

---

### 10. 百川智能

| 模型 | model_id | 上下文 | 价格 | 备注 |
|------|----------|--------|------|------|
| Baichuan-M3 Plus | Baichuan-M3-Plus | 128K | 免费 | 医疗专精，幻觉率 2.6% |
| Baichuan-M3 | Baichuan-M3 | 128K | 付费 | 通用多模态 |

- **Base URL**: `https://api.baichuan-ai.com/v1/chat/completions`（唯一，无 Token Plan）
- **免费额度**: M3 Plus 面向医疗领域永久免费
- **推荐**: Baichuan-M3 Plus（免费），Baichuan-M3（需要通用能力时）

---

### 11. MiniMax

| 模型 | model_id | 上下文 | 输入价格 (¥/百万token) | 输出价格 (¥/百万token) | 备注 |
|------|----------|--------|----------------------|----------------------|------|
| MiniMax-M3 | MiniMax-M3 | 512K | 2.1 | 8.4 | 最新多模态旗舰 |
| MiniMax-M2.7 | abab7-chat | 1M | 2.1 | 8.4 | 超长上下文 |

- **Base URL**: `https://api.minimax.chat/v1/text/chatcompletion_v2`（按量计费和 Token Plan 共用同一 URL）
- **API Key**: Token Plan 使用「订阅 Key」，按量计费使用「普通开放平台 API Key」，两者不同
- **免费额度**: 注册赠送
- **推荐**: MiniMax-M2.7（百万 token 超长上下文是核心优势）

---

## 三、代码修改方案

### 数据结构设计

接入模式不同 URL 也不同，因此每个模型需要存储两种 URL。建议数据结构如下：

```python
MODEL_REGISTRY = {
    "小米 MiMo": {
        "models": {
            "mimo-v2.5-pro": {
                "pricing": {"input": 3.0, "output": 6.0},
                "context_window": 128000,
                "free_tier": False,
            },
            "mimo-v2.5": {
                "pricing": {"input": 1.0, "output": 2.0},
                "context_window": 128000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
            "api_key_hint": "tp- 开头的 Token Plan 专属 Key",
        },
        "paygo": {
            "base_url": "https://api.xiaomimimo.com/v1/chat/completions",
            "api_key_hint": "小米 MiMo 开放平台普通 API Key",
        },
    },
    "智谱 AI": {
        "models": {
            "glm-4.7-flash": {
                "pricing": {"input": 0, "output": 0},
                "context_window": 128000,
                "free_tier": True,
            },
            "glm-5-turbo": {
                "pricing": {"input": 0, "output": 0},
                "context_window": 128000,
                "free_tier": True,  # 限时免费
            },
            "glm-5": {
                "pricing": {"input": None, "output": None},
                "context_window": 128000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions",
            "api_key_hint": "Coding Plan 使用与按量计费相同的 API Key",
        },
        "paygo": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            "api_key_hint": "智谱 AI 开放平台 API Key",
        },
    },
    "阿里巴巴": {
        "models": {
            "qwen3.7-max": {
                "pricing": {"input": None, "output": None},
                "context_window": 128000,
                "free_tier": False,
            },
            "qwen3.7-plus": {
                "pricing": {"input": None, "output": None},
                "context_window": 128000,
                "free_tier": False,
            },
            "qwen3.5-plus": {
                "pricing": {"input": None, "output": None},
                "context_window": 128000,
                "free_tier": False,
            },
            "qwen3.5-flash": {
                "pricing": {"input": None, "output": None},
                "context_window": 128000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://token-plan.cn-beijing.maas.aliuncs.com/v1/chat/completions",
            "api_key_hint": "sk- 开头的百炼 Token Plan 专属 Key",
        },
        "paygo": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "api_key_hint": "sk- 开头的百炼通用 API Key",
        },
    },
    "DeepSeek": {
        "models": {
            "deepseek-v4-pro": {
                "pricing": {"input": 4.0, "output": 18.0},
                "context_window": 128000,
                "free_tier": False,
            },
            "deepseek-v4-flash": {
                "pricing": {"input": 1.0, "output": 4.0},
                "context_window": 128000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://api.deepseek.com/v1/chat/completions",
            "api_key_hint": "DeepSeek 无独立 Token Plan，按量计费 URL 即可",
        },
        "paygo": {
            "base_url": "https://api.deepseek.com/v1/chat/completions",
            "api_key_hint": "DeepSeek API Key",
        },
    },
    "腾讯混元": {
        "models": {
            "hunyuan-turbos": {
                "pricing": {"input": 0.8, "output": 2.0},
                "context_window": 256000,
                "free_tier": False,
            },
            "hunyuan-t1": {
                "pricing": {"input": 1.0, "output": 4.0},
                "context_window": 256000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://api.lkeap.cloud.tencent.com/plan/v1/chat/completions",
            "api_key_hint": "TokenHub 控制台生成的 Token Plan 专属 Key",
        },
        "paygo": {
            "base_url": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
            "api_key_hint": "腾讯云 API 密钥",
        },
    },
    "百度文心": {
        "models": {
            "ernie-5.0": {
                "pricing": {"input": 6.0, "output": 24.0},
                "context_window": 128000,
                "free_tier": False,
            },
            "ernie-4.5-turbo-128k-preview": {
                "pricing": {"input": 0.8, "output": 3.2},
                "context_window": 128000,
                "free_tier": False,
            },
            "ernie-x1.1": {
                "pricing": {"input": 1.0, "output": 4.0},
                "context_window": 128000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://qianfan.baidubce.com/v2/chat/completions",
            "api_key_hint": "千帆控制台 Token 福利包专属 API Key（与按量计费 URL 相同，Key 不同）",
        },
        "paygo": {
            "base_url": "https://qianfan.baidubce.com/v2/chat/completions",
            "api_key_hint": "百度智能云千帆平台 API Key",
        },
    },
    "月之暗面 Kimi": {
        "models": {
            "kimi-k2.6": {
                "pricing": {"input": None, "output": None},
                "context_window": 256000,
                "free_tier": False,
            },
            "kimi-k2.7-code": {
                "pricing": {"input": None, "output": None},
                "context_window": 256000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://api.kimi.com/coding/v1/chat/completions",
            "api_key_hint": "Kimi Coding Plan 专属 API Key",
        },
        "paygo": {
            "base_url": "https://api.moonshot.cn/v1/chat/completions",
            "api_key_hint": "Kimi 开放平台 API Key",
        },
    },
    "讯飞星火": {
        "models": {
            "spark-lite": {
                "pricing": {"input": 0, "output": 0},
                "context_window": 8000,
                "free_tier": True,
            },
            "spark-max": {
                "pricing": {"input": None, "output": None},
                "context_window": 8000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://maas-token-api.cn-huabei-1.xf-yun.com/v2/chat/completions",
            "api_key_hint": "讯飞星辰 MaaS Token Plan 专属 Key",
        },
        "paygo": {
            "base_url": "https://spark-api-open.xf-yun.com/v1/chat/completions",
            "api_key_hint": "讯飞开放平台 API Key",
        },
    },
    "百川智能": {
        "models": {
            "Baichuan-M3-Plus": {
                "pricing": {"input": 0, "output": 0},
                "context_window": 128000,
                "free_tier": True,
            },
            "Baichuan-M3": {
                "pricing": {"input": None, "output": None},
                "context_window": 128000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://api.baichuan-ai.com/v1/chat/completions",
            "api_key_hint": "百川无独立 Token Plan，按量计费 URL 即可",
        },
        "paygo": {
            "base_url": "https://api.baichuan-ai.com/v1/chat/completions",
            "api_key_hint": "百川开放平台 API Key",
        },
    },
    "MiniMax": {
        "models": {
            "MiniMax-M3": {
                "pricing": {"input": 2.1, "output": 8.4},
                "context_window": 512000,
                "free_tier": False,
            },
            "abab7-chat": {
                "pricing": {"input": 2.1, "output": 8.4},
                "context_window": 1000000,
                "free_tier": False,
            },
        },
        "token_plan": {
            "base_url": "https://api.minimax.chat/v1/text/chatcompletion_v2",
            "api_key_hint": "MiniMax 订阅 Key（与按量计费 URL 相同，Key 不同）",
        },
        "paygo": {
            "base_url": "https://api.minimax.chat/v1/text/chatcompletion_v2",
            "api_key_hint": "MiniMax 开放平台 API Key",
        },
    },
}
```

### 使用方式

代码中根据用户选择的「接入模式」字段联动获取 URL：

```python
def get_model_config(vendor: str, model_id: str, access_mode: str) -> dict:
    """
    获取模型配置
    
    Args:
        vendor: 厂商名称 (如 "小米 MiMo")
        model_id: 模型 ID (如 "mimo-v2.5-pro")
        access_mode: 接入模式 ("token_plan" 或 "paygo")
    
    Returns:
        dict with keys: base_url, api_key_hint, pricing, context_window, free_tier
    """
    vendor_data = MODEL_REGISTRY.get(vendor, {})
    model_info = vendor_data.get("models", {}).get(model_id, {})
    mode_config = vendor_data.get(access_mode, {})
    
    return {
        "base_url": mode_config.get("base_url"),
        "api_key_hint": mode_config.get("api_key_hint"),
        **model_info,
    }
```

### settings_page.py 中的联动逻辑

用户在设置页面选择厂商和接入模式后，URL 输入框应自动填充对应地址：

```python
def _on_access_mode_changed(self, mode: str):
    """接入模式切换时，更新 API Base URL"""
    vendor = self._vendor_combo.currentText()
    model = self._model_combo.currentText()
    config = get_model_config(vendor, model, mode)
    if config and config["base_url"]:
        self._url_entry.setText(config["base_url"])
```

---

## 四、关键变更总结

| 操作 | 原模型 | 新模型 | 原因 |
|------|--------|--------|------|
| **替换** | mimo-v2-flash | mimo-v2.5 | V2 系列 2026-06-30 停服 |
| **替换** | mimo-v2-pro | mimo-v2.5-pro | V2 系列 2026-06-30 停服 |
| **替换** | mimo-v2-turbo | mimo-v2.5 | V2 系列 2026-06-30 停服 |
| **替换** | deepseek-chat | deepseek-v4-flash | 2026-07-24 停服 |
| **替换** | deepseek-reasoner | deepseek-v4-pro | 2026-07-24 停服 |
| **替换** | glm-4 | glm-4.7-flash | 更新至最新免费模型 |
| **替换** | glm-4-air | glm-5-turbo | 限时免费，性能更好 |
| **替换** | glm-4-airx | glm-5 | 更新至最新 |
| **替换** | glm-4-long | glm-5 | 统一为新系列 |
| **替换** | hunyuan-standard | hunyuan-turbos | 旧版正在切换升级 |
| **替换** | hunyuan-standard-256K | hunyuan-turbos | 旧版正在切换升级 |
| **替换** | hunyuan-lite | hunyuan-turbos | 旧版正在切换升级 |
| **替换** | ERNIE-4.0-8K | ernie-5.0 | 升级至最新 |
| **替换** | ERNIE-4.0-Turbo-8K | ernie-4.5-turbo-128k-preview | 升级至最新 |
| **替换** | ERNIE-3.5-8K | ernie-4.5-turbo-128k-preview | 老模型升级 |
| **替换** | moonshot-v1-8k | kimi-k2.6 | 升级至最新 |
| **替换** | spark-3.5 | spark-max | 更新至新版 |
| **替换** | Baichuan4-Turbo-128k | Baichuan-M3-Plus | 升级至最新且免费 |
| **替换** | abab6.5s-chat | abab7-chat (M2.7) | 升级至最新 |
| **替换** | abab6.5-chat | MiniMax-M3 | 升级至最新 |
| **移除** | Yi-Lightning, Yi-Large, Yi-Spark | — | 零一万物已转型 |
| **移除** | ernie-speed-8k, ernie-lite-8k | — | 轻量模型合并至 Turbo |

---

## 五、待确认事项

以下信息需要在实际接入时进一步验证：

1. **智谱 GLM-5.1 / GLM-5 的具体按量计费价格** — 官网未明确列出
2. **阿里 Qwen3.7 系列的具体价格** — 价格变动频繁，需查百炼平台
3. **月之暗面 Kimi K2.6 / K2.7 Code 的具体价格** — 定价页未列出
4. **讯飞 spark-4.0-ultra 升级 X1.5 后的 model_id 是否变更** — 需实际调用验证
5. **百川 M3 Plus 免费范围** — 是否仅限医疗领域
6. **MiniMax M3 / M2.7 的 model_id 格式** — 可能需要实际调用验证
7. **腾讯混元 model_id 格式** — hunyuan-turbos 大小写需验证
8. **百度 ERNIE 5.0 的 model_id** — 可能是 ernie-5.0-turbo 或其他格式

建议：先以免费模型（GLM-4.7-Flash、Spark Lite）为默认，让用户自行选择付费模型并填入 API Key。

---

## 六、废弃模型时间线

| 厂商 | 停服模型 | 停服日期 | 替代模型 |
|------|---------|---------|---------|
| 小米 | mimo-v2-flash, mimo-v2-pro, mimo-v2-turbo | 2026-06-30 | mimo-v2.5, mimo-v2.5-pro |
| DeepSeek | deepseek-chat, deepseek-reasoner | 2026-07-24 | deepseek-v4-flash, deepseek-v4-pro |
| 腾讯 | hunyuan-standard, hunyuan-fast 等旧版 | 逐步切换中 | hunyuan-turbos, hunyuan-t1 |
