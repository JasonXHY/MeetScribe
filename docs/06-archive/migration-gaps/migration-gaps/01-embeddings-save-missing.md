# 深度排查：声纹匹配重启丢失

> **用户决策（2026-06-25）**：采用方案A — 最小修复，恢复embedding保存和加载。

## 问题概述

用户反馈"重启程序后声纹匹配丢失"。经深度排查，这个问题的准确含义是：**转写完成后关闭程序再打开，之前通过声纹匹配确认的说话人embedding向量丢失，导致无法利用历史声纹数据进行跨文件匹配**。但需要注意：已确认的说话人姓名映射（`file_history.json`）和音色库（`voiceprint_library.json`）是正常持久化的，不受影响。

## 用户可见的症状

1. 转写文件A，声纹匹配到"张三"→ 关闭程序 → 重新打开 → 再转写文件B
2. 此时系统无法利用文件A中"张三"的声纹向量去匹配文件B中的相似声音
3. 音色库中已确认的成员仍然在，但新文件的embedding无法与之比对
4. 打开发言人管理弹窗，旧文件的embedding加载为空（因为从未保存到磁盘）

## 根因分析：4个数据流断裂点

### 断裂点1（根本原因）：Embedding从未保存到磁盘

| 项目 | 详情 |
|------|------|
| 位置 | `transcription.py` `_on_done()` (第287-321行) |
| 问题 | 旧版的 `_save_embeddings_to_disk()` 方法在迁移时整体丢失，新版从未实现 |
| 影响 | 每次转写产生的 `_speaker_embeddings` 仅存于内存，程序退出即丢失 |
| 证据 | `grep "_save_embeddings" transcription.py` 返回 0 结果 |

### 断裂点2：启动时不加载历史Embedding

| 项目 | 详情 |
|------|------|
| 位置 | `transcription.py` `__init__()` (第38-58行) |
| 问题 | `_speaker_embeddings` 初始化为空dict，无任何恢复逻辑 |
| 影响 | 即使磁盘上有embeddings文件（旧版遗留），启动后handler也不知道 |

### 断裂点3：重启后声纹匹配不会重新执行

| 项目 | 详情 |
|------|------|
| 位置 | `transcription.py` `_match_voiceprints()` (第333行) |
| 问题 | 声纹匹配仅在转写过程中触发（`auto_summary`消息和`_on_done`） |
| 影响 | 重启后即使手动加载了embeddings到SpeakerDialog，也不会自动匹配 |

### 断裂点4：加载路径仅限Speaker Dialog

| 项目 | 详情 |
|------|------|
| 位置 | `home_page.py` `_load_embeddings_from_disk()` (第742行) |
| 问题 | 仅在 `_open_speaker_modal()` 中调用，不在转写流程中使用 |
| 影响 | 转写新文件时无法利用旧文件的声纹数据进行跨文件匹配 |

## 完整数据流图

```
                    ┌─────────────────────────────────────────────┐
                    │            子进程 (transcribe_worker)         │
                    │                                             │
                    │  Transcriber._extract_per_speaker_embeddings │
                    │       ↓                                     │
                    │  transcriber.spk_embeddings                  │
                    │       ↓                                     │
                    │  _send_embeddings() → queue.put()           │
                    └──────────────┬──────────────────────────────┘
                                   │ multiprocessing.Queue
                                   ↓
                    ┌─────────────────────────────────────────────┐
                    │         主进程 (TranscriptionHandler)         │
                    │                                             │
                    │  _process_message("spk_embeddings")          │
                    │       ↓                                     │
                    │  self._speaker_embeddings  ←─── 仅存内存     │
                    │       ↓                                     │
                    │  _match_voiceprints()                        │
                    │       ↓                                     │
                    │  ├── VoiceprintLibrary.match() → 音色库匹配  │
                    │  ├── apply_speaker_mapping() → 写transcript  │
                    │  ├── update_speaker_names() → 写file_history │
                    │  └── library.add_speaker() → 写voiceprint_lib│
                    │                                             │
                    │  _on_done()                                  │
                    │       ↓                                     │
                    │  ❌ 缺少 _save_embeddings_to_disk() 调用     │
                    │       ↓                                     │
                    │  程序退出 → _speaker_embeddings 全部丢失     │
                    └─────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │              重启后                          │
                    │                                             │
                    │  file_history.json → speaker_names 恢复 ✓   │
                    │  _speaker_embeddings = {} → 空 ❌           │
                    │  voiceprint_library.json → 音色库恢复 ✓     │
                    │  {base}_embeddings.json → 旧文件有/新文件无  │
                    └─────────────────────────────────────────────┘
```

## 各持久化文件状态

| 文件 | 路径 | 保存是否正常 | 加载是否正常 |
|------|------|:----------:|:----------:|
| `file_history.json` | `data/file_history.json` | ✅ 正常 | ✅ 正常（启动时自动加载） |
| `voiceprint_library.json` | `data/voiceprint_library.json` | ✅ 正常 | ✅ 正常（懒加载） |
| `{base}_embeddings.json` | `transcripts/` 下 | ❌ **缺失** | ⚠️ 部分正常（仅旧文件有数据） |

## 修复方案

### 方案A：最小修复（推荐优先实施）

**目标**：恢复embedding的保存和加载，让声纹匹配在重启后仍能工作。

**改动点**：
1. 在 `transcription.py` 中恢复 `_save_embeddings_to_disk()` 方法
2. 在 `_on_done()` 中声纹匹配之后调用它
3. 在 `TranscriptionHandler.__init__()` 或 `start()` 中预加载历史embeddings

**优点**：改动最小，直接解决根因
**缺点**：保存操作在主线程执行（但embedding保存是纯JSON写入，耗时<50ms，可接受）

### 方案B：增强修复

在方案A基础上增加：
1. 每次转写完成立即保存（而非等 `_on_done`）
2. 转写新文件时自动加载所有历史embeddings用于跨文件匹配
3. 添加保存失败重试机制

**优点**：更健壮，支持跨文件声纹匹配
**缺点**：改动量较大，需要修改转写流程

### 方案C：架构重构

将声纹数据管理抽离为独立的 `VoiceprintStorage` 类，统一管理保存/加载/匹配。

**优点**：代码更清晰，职责分离
**缺点**：改动量大，当前阶段性价比不高

## 建议

**先实施方案A**，确保embedding不丢失。方案B的"跨文件匹配"作为后续优化。方案C暂不实施。
