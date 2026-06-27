# 模型下载失败排查报告

> 日期：2026-06-26
> 状态：已深入排查，待诊断脚本验证

---

## 问题描述

无论是首次引导还是设置页下载，模型完整性校验都不通过，用户无法使用转写功能。

## 第一轮排查：新老代码对比

### 下载核心逻辑：完全一致

以下文件的模型下载/检查基础设施代码逐字节相同：

- `src/transcriber.py`（第 44-313 行）：REQUIRED_MODELS、ModelManager、download_model、check_all_models、_setup_modelscope_cache、_resolve_model_path
- 下载 URL、模型 ID、snapshot_download 调用参数、完整性校验逻辑、文件大小校验、辅助文件检查、MODELSCOPE_CACHE 环境变量设置、错误处理、重试机制 —— **全部无差异**

### 仅有的两处差异（不影响下载）

| 文件 | 差异 | 影响 |
|------|------|------|
| `src/transcriber.py` 第 1069-1073 行 | 新版 CAM++ 加载增加本地路径解析（先查缓存再用别名） | 减少不必要的 ModelScope 重新下载 |
| `src/gui/styles.py` 第 116 行 | MODEL_CACHE_DIR 从双分支 if-else 简化为 `get_data_dir()` 单行调用 | 结果路径相同 |

**结论：新版代码在模型下载方面没有引入 bug。**

## 第二轮排查：下载链路深度分析

### ModelScope SDK 内部配置

SDK（v1.37.1）内部**已有**超时和重试机制：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `API_FILE_DOWNLOAD_TIMEOUT` | **60s** | 单次 socket 操作超时 |
| `API_FILE_DOWNLOAD_RETRY_TIMES` | **5** | 下载重试次数 |
| `backoff_factor` | 1 | 指数退避: 0s, 1s, 2s, 4s... |
| `MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB` | **500MB** | 超过此大小分块并行下载 |
| `MODELSCOPE_DOWNLOAD_PARALLELS` | **1** | 并行下载 workers 数 |
| `PART_SIZE` | **160MB** | 分块大小 |

**结论：SDK 不会无限挂起。** 60s 超时 + 5 次重试 = 单个文件最多等待 ~6 分钟。

### 项目代码下载流程

```
用户点击下载
  → QThread (ModelDownloadWorker)
    → ModelManager.download_all_missing()
      → for model_id in missing:        # 串行，非并行
          → download_model(model_id)
            → check_all_models()         # 下载前检查
            → snapshot_download()        # SDK 下载（60s 超时 + 5 次重试）
            → check_all_models()         # 下载后校验
```

**关键发现：**
1. **串行下载**：4 个模型逐个下载，不会并行争抢网络资源
2. **无项目级超时**：依赖 SDK 内部 60s 超时
3. **无项目级重试**：依赖 SDK 内部 5 次重试
4. **进度回调几乎无用**：first_launch 进度始终为 0，settings_page 直接吞掉回调

### 可能的失败场景

| 场景 | 可能性 | 表现 |
|------|--------|------|
| a) 网络中断导致部分文件写入 | 中 | 文件存在但大小不足 → 校验失败 |
| b) SDK 重试耗尽抛出 FileDownloadError | 中 | download_model 捕获异常 → 返回失败 |
| c) 辅助文件下载失败 | 低 | aux_missing 不为空 → 校验失败 |
| d) 缓存目录路径问题 | 低 | 中文路径/MAX_PATH → 写入失败 |
| e) configuration.json 解析失败 | 低 | fallback 到检查 model.pt 存在性 |
| f) 并发访问 models_cache | 低 | 转写中触发下载 → 文件锁冲突 |

### 代码层面的可靠性缺陷

| 问题 | 严重性 | 位置 |
|------|--------|------|
| 无项目级超时控制 | 低（SDK 有 60s） | `transcriber.py:251` |
| 无项目级重试逻辑 | 低（SDK 有 5 次） | `transcriber.py:278` |
| 完整性校验仅检查文件大小 | **中** | `transcriber.py:186-192` |
| 无 hash/checksum 校验 | **中** | `transcriber.py:186-192` |
| 无错误分类和用户提示 | 中 | `transcriber.py:263` |
| 进度回调无实际进度 | 低 | `first_launch.py:43`, `settings_page.py:36` |
| 无下载/转写并发保护 | 低 | 无锁机制 |

## 诊断工具

已创建独立诊断脚本：`scripts/diagnose_model_download.py`

运行方式：
```bash
python scripts/diagnose_model_download.py
```

测试内容：
1. SDK 内部配置检查（超时、重试常量）
2. 网络连通性
3. 小模型端到端下载 + ModelManager 校验
4. 完整性校验逻辑边界测试
5. 缓存目录路径和权限
6. 环境变量和并发安全

## 建议下一步

1. **运行诊断脚本**确认实际下载行为
2. 根据结果决定修复方向：
   - 如果下载正常但校验失败 → 完善完整性校验（加 hash）
   - 如果 SDK 重试耗尽 → 添加项目级重试 + 进度监控
   - 如果路径问题 → 修复缓存目录路径
3. 使用新版代码重新打包后测试
