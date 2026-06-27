# 迁移缺失问题汇总

> **状态**：所有问题已修复（2026-06-25），59个测试全部通过。

## 问题清单

| 编号 | 问题 | 严重度 | 状态 | 文档 |
|------|------|--------|------|------|
| 01 | `_save_embeddings_to_disk()` 未迁移 | 高 | ✅ 已修复 | [01-embeddings-save-missing.md](01-embeddings-save-missing.md) |
| 02 | `_merge_dual_track_results()` 实现方式变更 | 无 | ✅ 已处理 | [02-dual-track-merge.md](02-dual-track-merge.md) |
| 03 | AI纠错/摘要同步执行导致UI卡死 | 高 | ✅ 已修复 | [03-auto-correction-summary-sync.md](03-auto-correction-summary-sync.md) |
| 04 | 任务状态显示失效（hasattr bug） | 高 | ✅ 已修复 | [04-progress-display.md](04-progress-display.md) |
| 05 | sentences参数未传递 + 预览Markdown渲染 | 低 | ✅ 已修复 | [05-sentences-and-preview.md](05-sentences-and-preview.md) |

## 问题详情

### 01. `_save_embeddings_to_disk()` 未迁移

**问题**：新版代码缺少将声纹嵌入向量保存到磁盘的功能，导致程序重启后声纹匹配失效。

**影响**：
- 程序重启后，之前转写文件的声纹嵌入向量丢失
- 音色库识别无法工作
- 用户需要重新录音才能建立声纹库

**修复建议**：
- 方案A：完整迁移旧版逻辑
- 方案B：优化后的迁移（支持增量保存、重试机制）
- 方案C：架构优化（抽离到独立类，支持异步保存）

### 02. `_merge_dual_track_results()` 实现方式变更

**状态**：已处理，无需修改。

**说明**：新版实现方式更优（实时合并 vs 后置合并），保留此文档作为未来问题排查时的参考依据。

### 03. AI纠错/摘要从异步改为同步执行

**问题**：AI纠错和AI摘要生成从旧版的异步线程执行改为新版的同步执行，可能导致UI卡顿。

**影响**：
- AI操作期间UI会卡顿
- 用户无法继续操作
- 大文件处理时卡顿更明显

**分析**：
- 为什么改成同步：Qt信号槽机制限制、线程安全考虑、代码简化、功能需求变更
- 执行顺序：当前顺序（纠错 → 声纹 → 摘要）是合理的

**修复建议**：
- 方案A：恢复异步执行（使用QThread）
- 方案B：优化同步执行（显示进度、分段处理）
- 方案C：混合方案（纠错同步，摘要异步）

### 04. 转写进度显示功能简化

**问题**：转写进度显示从旧版的详细显示（stage + ETA + 文件行状态）简化为新版的简化显示（stage + percent）。

**影响**：
- 缺少ETA：用户无法预估剩余时间
- 文件行状态不更新：用户看不到每个文件的进度
- 进度显示位置分散

**修复建议**：
- 方案A：完整恢复旧版功能
- 方案B：简化恢复（推荐，只恢复ETA和文件行状态）
- 方案C：优化现有实现

### 05. sentences参数未传递 + 预览美观度优化

**问题**：
1. `_open_speaker_modal` 未传递 `sentences` 参数给 SpeakerDialog
2. 转写预览和AI摘要预览使用纯文本显示，缺少markdown格式化

**影响**：
- SpeakerDialog中无法显示逐句对齐信息
- AI摘要的markdown内容无法正确显示
- 用户体验下降

**修复建议**：
- 短期方案：恢复 sentences 传递 + 简单格式化
- 长期方案：使用 QTextBrowser + markdown 库 + 自定义样式

## 修复优先级

### P0（必须修复）
- 01. `_save_embeddings_to_disk()` 未迁移
- 04. 转写进度显示功能简化（ETA和文件行状态）

### P1（建议修复）
- 03. AI纠错/摘要同步执行（UI卡顿）
- 05. sentences参数未传递 + 预览美观度优化

### P2（可选优化）
- 03. AI纠错/摘要异步执行（完整恢复）
- 05. 预览美观度完整优化（使用QTextBrowser + markdown库）

## 相关代码位置

### 旧版代码（参考）
- `C:\Users\kingdee\Desktop\侧耳倾听-评审材料\src_old\transcription.py`
- `C:\Users\kingdee\Desktop\侧耳倾听-评审材料\src_old\home_page.py`

### 新版代码
- `C:\侧耳倾听\src\gui\transcription.py`
- `C:\侧耳倾听\src\gui\home_page.py`
- `C:\侧耳倾听\src\gui\dialogs.py`

## 参考资料

- Qt 线程文档：https://doc.qt.io/qtforpython-6/QtCore/QThread.html
- Python markdown 库：https://python-markdown.github.io/
- C:\NewProject markdown 样式：`C:\NewProject\src\styles\markdown-preview.css`
