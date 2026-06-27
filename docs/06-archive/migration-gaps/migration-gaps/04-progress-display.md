# 深度排查：任务状态显示问题

> **用户决策（2026-06-25）**：做第一步（修复hasattr bug + 按钮状态管理）和第二步（增加后处理状态显示）。进度条（第三步）暂不做。

## 问题概述

用户的核心诉求不是进度条本身，而是**能实时看到任务状态**。当前点击"开始转写"或"重新转写"后，操作栏没有变化，用户无法判断任务是否正常进行。

## 排查发现：3个关键问题

### 问题1：`hasattr(dict, 'stage')` — 进度显示完全失效

**位置**：`home_page.py` 第600-603行

```python
def _on_progress_updated(self, progress):
    if hasattr(progress, 'stage') and hasattr(progress, 'percent'):
        self._recording_bar.update_queue_status(
            f"转写中: {progress.stage} ({progress.percent}%)"
        )
```

**Bug本质**：类型不匹配。

- Worker子进程通过 `multiprocessing.Queue` 发送的是 **plain dict**
- `_process_message` 将 dict 原样 emit 给信号
- `_on_progress_updated` 用 `hasattr(progress, 'stage')` 检查 — 对dict调用hasattr检查的是**属性**而非**键**
- Python中 `hasattr({'stage': 'xxx'}, 'stage')` 返回 **False**
- 结果：**条件永远为False，进度文本永远不会更新**

**同时**：`TranscriptionProgress` 类（`file_manager.py` 第66-73行）定义了 `stage`、`percent` 等属性，`TranscriptionHandler.__init__` 中也创建了实例 `self._progress = TranscriptionProgress()`，但**从未被赋值或使用**，是死代码。

### 问题2：停止按钮信号混淆

**位置**：`home_page.py` 第945行

转写开始时启用的是 `_recording_bar.stop_btn`，但它的 `clicked` 信号连接的是 `_stop_recording`（停止录音），而非停止转写。用户点击后实际触发的是停止录音，不是停止转写。

### 问题3：AI摘要按钮转写中未禁用

**位置**：`home_page.py` 第943-959行

转写开始时 `_btn_ai_summary` 未被禁用，用户可能在转写过程中误点AI摘要。旧版明确禁用了它：
```python
# 旧版 home_page.py:757-764
self._btn_ai_summary.configure(state="disabled")
```

## 当前按钮状态管理现状

| 触发时机 | 按钮 | 动作 | 位置 |
|---------|------|------|------|
| 点击"开始转写" | `_btn_transcribe` | `setEnabled(False)` + `setText("转写中...")` | 第943-944行 |
| 点击"开始转写" | `_recording_bar.stop_btn` | `setEnabled(True)` + 红色样式 | 第945-959行 |
| 转写完成 | `_btn_transcribe` | `setEnabled(True)` + `setText("开始转写")` | 第559-560行 |
| 转写完成 | `_recording_bar.stop_btn` | `setEnabled(False)` + 灰色样式 | 第561-579行 |
| 转写中 | `_btn_ai_summary` | ⚠️ **未管理** — 应该禁用但没有 | - |

## 进度信号完整传递链路

```
Worker子进程                    TranscriptionHandler              HomePage UI
    │                                │                               │
    │ queue.put(("progress", dict))  │                               │
    │───────────────────────────────>│                               │
    │                          _poll() 每50ms轮询                    │
    │                          _process_message()                    │
    │                          progress_updated.emit(dict)            │
    │                                │──────────────────────────────>│
    │                          _on_progress_updated(dict)            │
    │                          hasattr(dict, 'stage') → False ❌     │
    │                          进度永远不更新                         │
```

## 修复方案

### 第一步（P0）：修复hasattr bug + 恢复任务状态显示

**改接收端**（推荐，改动最小）：

```python
def _on_progress_updated(self, progress):
    """转写进度更新"""
    if isinstance(progress, dict):
        stage = progress.get('stage', '')
        percent = progress.get('percent', 0)
        current = progress.get('current_file', 0)
        total = progress.get('total_files', 0)
        
        # 更新操作栏状态文本
        text = f"转写中: {stage}"
        if percent:
            text += f" ({percent}%)"
        if total > 0:
            text += f" [{current}/{total}]"
        self._recording_bar.update_queue_status(text)
    elif hasattr(progress, 'stage'):
        # 兼容 TranscriptionProgress 对象
        self._recording_bar.update_queue_status(
            f"转写中: {progress.stage} ({progress.percent}%)"
        )
```

### 第二步（P0）：完善按钮状态管理

转写开始时：
```python
# 禁用转写按钮
self._btn_transcribe.setEnabled(False)
self._btn_transcribe.setText("转写中...")
# 禁用AI摘要按钮（防止误操作）
self._btn_ai_summary.setEnabled(False)
# 启用停止按钮
self._recording_bar.stop_btn.setEnabled(True)
```

转写完成时：
```python
# 恢复转写按钮
self._btn_transcribe.setEnabled(True)
self._btn_transcribe.setText("开始转写")
# 恢复AI摘要按钮
self._btn_ai_summary.setEnabled(True)
# 禁用停止按钮
self._recording_bar.stop_btn.setEnabled(False)
```

### 第三步（P1）：增加后处理状态显示

转写完成后进入后处理阶段（AI纠错/声纹/摘要），此时也应显示状态：

```python
# 在 transcription.py 中增加信号
post_process_status = Signal(str)  # 后处理状态文本

# 在每个后处理步骤前发射
self.post_process_status.emit("正在进行AI纠错...")
# ... 执行纠错 ...
self.post_process_status.emit("正在进行声纹匹配...")
# ... 执行匹配 ...
self.post_process_status.emit("正在生成摘要...")
# ... 执行摘要 ...
```

HomePage接收并显示：
```python
handler.post_process_status.connect(self._on_post_process_status)

def _on_post_process_status(self, text):
    self._recording_bar.update_queue_status(text)
```

### 第四步（P2）：进度条（可选）

进度条的实现相对复杂（需要worker端计算百分比），且当前阶段不是核心矛盾。建议：
- 保证进度相关代码不报错（修复hashtable bug即可）
- 如果实现简单，可以显示文件级进度（第几个文件/共几个）
- 复杂的百分比进度条和ETA作为后续优化

## 建议实施顺序

1. **立即修复**：hasattr bug + 按钮状态管理（~20行改动，立竿见影）
2. **短期补充**：后处理状态显示（~30行改动）
3. **后续优化**：进度条和ETA（改动较大，非紧急）
