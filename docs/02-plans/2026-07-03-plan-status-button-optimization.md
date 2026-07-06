# 转写状态与操作按钮优化方案

> 日期：2026-07-03
> 问题：停止转写后状态和按钮不更新，重启后 PROCESSING 状态残留
> 待 Qoder 审核

---

## 一、问题分析

### 1.1 问题链路

```
用户点击"停止"按钮
  → home_page._stop_transcription(file_path)
    → transcription_handler.stop_transcription(file_path)
      → _transcribing = False
      → _cancel_event.set()
      → _thread.join(5)
      → file_status_changed.emit(file_path, PENDING)  ← 只发了信号
      → log_message.emit("转写已停止")
    → _recording_bar.set_transcribing(False)
    → refresh_file_list()  ← 重新读取 file_manager

file_manager.update_status() 从未被调用！
  → 状态未持久化到 file_history.json
  → 下次启动加载时，PROCESSING 状态原样恢复
  → 按钮永远显示"停止"，无法重新转写
```

### 1.2 根因

| 问题 | 根因 | 位置 |
|------|------|------|
| 停止后状态不更新 | `stop_transcription()` 只发信号，不调用 `file_manager.update_status()` | `transcription.py:1190-1210` |
| 重启后 PROCESSING 残留 | 启动时无恢复逻辑，直接加载 JSON 中的 PROCESSING 状态 | `file_manager.py:398-456` |
| 停止后按钮不更新 | 状态未持久化，`refresh_file_list()` 读到的还是旧状态 | `home_page.py:865-870` |
| 停止特定文件逻辑错误 | `file_path` 参数只处理一个文件，其余文件状态被忽略 | `transcription.py:1204-1208` |

### 1.3 当前 FileStatus 枚举

```python
class FileStatus(Enum):
    PENDING = "pending"       # 待处理
    PROCESSING = "processing" # 处理中
    DONE = "done"             # 已完成
    FAILED = "failed"         # 失败
    PAUSED = "paused"         # 已暂停（P1，未使用）
```

---

## 二、状态流转设计

### 2.1 完整状态机

```
                    ┌──────────────────────────────────────┐
                    │                                      │
    ┌──────────┐    │    ┌──────────────┐    ┌──────────┐  │
    │ PENDING  │───→│───→│ PROCESSING   │───→│  DONE    │  │
    └──────────┘    │    └──────────────┘    └──────────┘  │
         ↑          │           │                          │
         │          │           │ 超时/异常                 │
         │          │           ↓                          │
         │          │    ┌──────────────┐                  │
         │          │    │   FAILED     │                  │
         │          │    └──────────────┘                  │
         │          │           │                          │
         │          │           │ 用户点击"重试"            │
         │          │           ↓                          │
         │          │    ┌──────────────┐                  │
         │          │    │   PENDING    │←─────────────────┘
         │          │    └──────────────┘
         │          │
         │          │  用户点击"停止"
         │          │           │
         │          │           ↓
         │          │    ┌──────────────┐
         │          └────│   PENDING    │  ← 停止后回到待处理
         │               └──────────────┘
         │
         │  程序异常退出/被 kill
         │  （PROCESSING 残留）
         │           │
         │           ↓
         │    ┌──────────────┐
         └────│   PENDING    │  ← 启动时恢复
              └──────────────┘
```

### 2.2 各操作对应的状态变化

| 当前状态 | 用户操作 | 目标状态 | 持久化 | 按钮变化 |
|----------|---------|---------|--------|---------|
| PENDING | 点击"转写" | PROCESSING | 是 | 转写/删除 → 停止 |
| PENDING | 点击"删除" | （移除） | 是 | 从列表移除 |
| PROCESSING | 点击"停止" | PENDING | 是 | 停止 → 转写/删除 |
| PROCESSING | 转写完成 | DONE | 是 | 停止 → 预览/打开/发言人/重试/导出 |
| PROCESSING | 转写失败 | FAILED | 是 | 停止 → 重试 |
| PROCESSING | 程序异常退出 | PENDING | 启动时恢复 | 停止 → 转写/删除 |
| DONE | 点击"重试" | PROCESSING | 是 | 预览/... → 停止 |
| FAILED | 点击"重试" | PROCESSING | 是 | 重试 → 停止 |

---

## 三、修复方案

### 3.1 修复 1：stop_transcription() 持久化状态

**文件**：`src/gui/transcription.py`

**当前代码**（line 1190-1210）：
```python
def stop_transcription(self, file_path=None):
    """停止转写"""
    if not self._transcribing:
        return

    self._transcribing = False
    self._poll_timer.stop()
    self._cancel_event.set()

    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=5)

    # 更新文件状态
    if file_path:
        self.file_status_changed.emit(file_path, FileStatus.PENDING)
    else:
        for fp in self._file_status:
            self.file_status_changed.emit(fp, FileStatus.PENDING)

    self.log_message.emit("转写已停止")
```

**修改为**：
```python
def stop_transcription(self, file_path=None):
    """停止转写"""
    if not self._transcribing:
        return

    self._transcribing = False
    self._poll_timer.stop()
    self._cancel_event.set()

    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=5)

    # 更新文件状态（持久化到 file_manager）
    if file_path:
        # 停止特定文件：该文件回到 PENDING，其余不受影响
        if self._app and hasattr(self._app, 'file_manager'):
            self._app.file_manager.update_status(file_path, FileStatus.PENDING)
        self.file_status_changed.emit(file_path, FileStatus.PENDING)
        self._file_status[file_path] = "pending"
    else:
        # 停止全部：所有 processing 文件回到 PENDING
        for fp, status in list(self._file_status.items()):
            if status == "processing":
                if self._app and hasattr(self._app, 'file_manager'):
                    self._app.file_manager.update_status(fp, FileStatus.PENDING)
                self.file_status_changed.emit(fp, FileStatus.PENDING)
                self._file_status[fp] = "pending"

    self.log_message.emit("转写已停止")
```

### 3.2 修复 2：启动时恢复 PROCESSING 状态

**文件**：`src/file_manager.py`

在 `_load_from_file()` 末尾（line 448 之后），添加恢复逻辑：

```python
# 恢复 PROCESSING 状态为 PENDING（程序异常退出时的残留）
recovered_count = 0
for audio in self._files:
    if audio.status == FileStatus.PROCESSING:
        audio.status = FileStatus.PENDING
        recovered_count += 1
if recovered_count > 0:
    logger.info(f"Recovered {recovered_count} PROCESSING files to PENDING on startup")
    self._save_to_file()  # 持久化恢复结果
```

### 3.3 修复 3：_on_done() 区分手动停止和异常

**文件**：`src/gui/transcription.py`

当前 `_on_done()` 将所有未完成的 processing 文件标记为 FAILED（line 343-349）。但手动停止时应该回到 PENDING。

**方案**：利用 `_cancel_event` 区分：

```python
def _on_done(self):
    """转写完成"""
    if self._done_called:
        return
    self._done_called = True
    self._transcribing = False
    self._poll_timer.stop()

    # 区分手动停止和异常/正常结束
    was_cancelled = self._cancel_event.is_set()

    success_count = sum(1 for s in self._file_status.values() if s == "done")
    fail_count = sum(1 for s in self._file_status.values() if s == "failed")

    # 将未完成的 processing 文件标记为适当状态
    if self._app and hasattr(self._app, 'file_manager'):
        for fp, status in list(self._file_status.items()):
            if status == "processing":
                if was_cancelled:
                    # 手动停止：回到 PENDING
                    self._app.file_manager.update_status(fp, FileStatus.PENDING)
                    self._file_status[fp] = "pending"
                else:
                    # 异常/超时：标记为 FAILED
                    self._app.file_manager.update_status(fp, FileStatus.FAILED)
                    self._file_status[fp] = "failed"
                    fail_count += 1

    # ... 后续声纹匹配、姓名提取等逻辑不变
```

---

## 四、按钮状态完整矩阵

### 4.1 单文件操作按钮

| 状态 | 图标 | 按钮 1 | 按钮 2 | 按钮 3 | 按钮 4 | 按钮 5 |
|------|------|--------|--------|--------|--------|--------|
| PENDING | `[ ]` | 转写 | 删除 | — | — | — |
| PROCESSING | `[...]` | 停止 | — | — | — | — |
| DONE | `[OK]` | 预览 | 打开 | 发言人 | 重试 | 导出 |
| FAILED | `[ERR]` | 重试 | — | — | — | — |

### 4.2 状态提示文本

```python
def _get_status_text(self, status: str) -> str:
    return {
        "pending": "待转写",
        "processing": "转写中",
        "done": "已完成",
        "failed": "失败",
        "paused": "已暂停",
    }.get(status, "未知")
```

### 4.3 状态图标

```python
icons = {
    FileStatus.PENDING: "[ ]",
    FileStatus.PROCESSING: "[...]",
    FileStatus.DONE: "[OK]",
    FileStatus.FAILED: "[ERR]",
    FileStatus.PAUSED: "[||]",
}
```

---

## 五、边界情况处理

### 5.1 程序异常退出（kill -9 / 崩溃）

| 场景 | 当前行为 | 优化后行为 |
|------|---------|-----------|
| 转写中被 kill | PROCESSING 残留，按钮卡死 | 启动时恢复为 PENDING，显示"转写"按钮 |
| 录音中被 kill | 录音文件可能不完整 | 不在本次优化范围 |

### 5.2 多文件批量转写中停止

| 场景 | 当前行为 | 优化后行为 |
|------|---------|-----------|
| 3 个文件转写中，停止 | 所有文件发 PENDING 信号，但 file_manager 未更新 | 所有 processing 文件持久化为 PENDING |
| 3 个文件转写中，第 2 个失败 | _on_done 将剩余 processing 标为 FAILED | 不变（异常失败标 FAILED） |
| 3 个文件转写中，用户停止 | 同上 | 所有 processing 文件回到 PENDING |

### 5.3 停止后重新转写

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 转写 3 个文件 | 状态变为 PROCESSING，按钮显示"停止" |
| 2 | 点击停止 | 状态回到 PENDING，按钮显示"转写/删除" |
| 3 | 点击转写 | 重新开始转写，状态变为 PROCESSING |
| 4 | 关闭程序 | PROCESSING 文件持久化为 PENDING |
| 5 | 重新打开 | 显示"转写"按钮，可正常操作 |

---

## 六、改动量估算

| 文件 | 改动 | 行数 |
|------|------|------|
| `src/gui/transcription.py` | stop_transcription() 持久化 + _on_done() 区分取消 | ~15 行 |
| `src/file_manager.py` | 启动时恢复 PROCESSING 状态 | ~8 行 |
| **合计** | | **~23 行** |

---

## 七、待 Qoder 审核

1. **PAUSED 状态**：是否需要引入 PAUSED 状态区分"手动停止"和"待处理"？当前方案统一回到 PENDING，简单但丢失了"曾经转写过"的信息。
2. **停止特定文件**：当前 `stop_transcription(file_path)` 只处理一个文件，批量转写中停止一个文件是否需要特殊处理？
3. **_cancel_event 时序**：`_on_done()` 检查 `_cancel_event.is_set()` 是否可靠？是否有竞态条件？
4. **file_manager._save_to_file() 调用频率**：启动时恢复 N 个文件会触发 N 次保存，是否需要批量保存？

---

## [Qoder 审查意见] 2026-07-03

> 逐行对照源码验证方案中的 claim，发现 MiMo 抓到了核心 bug 但遗漏了一个同等严重的问题。

---

### 一、MiMo 方案验证

#### 1.1 正确的部分

| MiMo claim | 验证结果 |
|------------|---------|
| `stop_transcription()` 只发信号不调 `file_manager.update_status()` | **确认** — line 1204-1208 只 emit 信号，无 file_manager 调用 |
| 启动时不恢复 PROCESSING 状态 | **确认** — `_load_from_file()` line 427 原样恢复 JSON 中的 status |
| `refresh_file_list()` 读到旧状态 | **确认** — line 977 从 `file_manager.display_files` 读取，覆盖信号的效果 |
| `_on_done()` 将所有 processing 标为 FAILED | **确认** — line 343-349 不区分取消和异常 |
| 修复 1/2/3 的代码改动方向正确 | **确认** — 持久化、启动恢复、区分取消 |

#### 1.2 遗漏的严重问题：工具栏按钮不恢复

**MiMo 完全没有提到工具栏按钮的状态恢复。** 这是一个同等严重的 bug：

转写启动时，`home_page.py:912-964` 禁用了工具栏按钮：

```python
self._btn_transcribe.setEnabled(False)    # line 912/962
self._btn_transcribe.setText("转写中...")  # line 913
self._btn_ai_summary.setEnabled(False)     # line 964
```

这些按钮**只在** `_on_transcription_done_handler()` (line 556-566) 中恢复，而这个 handler 连接的是 `transcription_done` 信号。

**但 `stop_transcription()` 不发射 `transcription_done` 信号。**

结果：用户点击停止后，"开始转写"按钮仍然是禁用的，文本仍然显示"转写中..."。用户**无法从工具栏重新启动转写**。

这就是用户报告的"中途停止后再也无法重新启动转写"的**另一半原因**——不只是文件行按钮卡死，工具栏按钮也卡死了。

#### 1.3 其他遗漏

| 遗漏项 | 说明 |
|--------|------|
| **队列不推进** | `stop_transcription()` 不调用 `_on_done()`，因此 `_task_queue.complete_current_task()` 和 `_check_queue()` 都不会执行。如果队列中有后续任务，它们永远不会被执行 |
| **线程引用不清理** | `stop_transcription()` join 了线程但没有将 `_thread` 置 None、`_queue` 置 None。下次转写时 `_execute_task()` 的残留线程检查可能误判 |
| **`_file_status` 字典不清理** | 停止后 `_file_status` 仍保留旧条目。下次转写时 `_execute_task()` 在 line 146 重置了 `_file_status = {}`，所以不影响功能，但如果 stop 和 next-start 之间有时间窗口，状态可能不一致 |

---

### 二、完整修复方案

基于 MiMo 的方案补充遗漏项，共 4 个修复点（MiMo 提了 3 个，我补 1 个）。

#### 修复 1：`stop_transcription()` 完整清理（MiMo 方案 + 补充）

**文件**：`src/gui/transcription.py`

MiMo 的方案正确处理了 file_manager 持久化。需要补充的是：

```python
def stop_transcription(self, file_path=None):
    """停止转写"""
    if not self._transcribing:
        return

    self._transcribing = False
    self._poll_timer.stop()
    self._cancel_event.set()

    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=5)

    # === MiMo 方案（正确）：持久化状态到 file_manager ===
    if file_path:
        if self._app and hasattr(self._app, 'file_manager'):
            self._app.file_manager.update_status(file_path, FileStatus.PENDING)
        self.file_status_changed.emit(file_path, FileStatus.PENDING)
        self._file_status[file_path] = "pending"
    else:
        for fp, status in list(self._file_status.items()):
            if status == "processing":
                if self._app and hasattr(self._app, 'file_manager'):
                    self._app.file_manager.update_status(fp, FileStatus.PENDING)
                self.file_status_changed.emit(fp, FileStatus.PENDING)
                self._file_status[fp] = "pending"

    # === Qoder 补充：清理线程引用 ===
    self._thread = None
    self._queue = None

    # === Qoder 补充：推进队列（如果有下一个任务）===
    self._task_queue.complete_current_task()
    self._check_queue()

    # === Qoder 补充：发射完成信号（恢复工具栏按钮）===
    success_count = sum(1 for s in self._file_status.values() if s == "done")
    fail_count = sum(1 for s in self._file_status.values() if s == "failed")
    self.transcription_done.emit(success_count, fail_count)

    self.log_message.emit("转写已停止")
```

**关键补充**：
- `transcription_done.emit()` → 触发 `_on_transcription_done_handler()` → 恢复"开始转写"和"AI 摘要"按钮
- `_task_queue.complete_current_task()` + `_check_queue()` → 推进队列
- `_thread = None` + `_queue = None` → 清理线程引用

#### 修复 2：启动时恢复 PROCESSING 状态（MiMo 方案，无需修改）

MiMo 的方案完全正确，约 8 行代码，在 `file_manager.py` 的 `_load_from_file()` 末尾添加恢复逻辑。

#### 修复 3：`_on_done()` 区分取消和异常（MiMo 方案，需微调）

MiMo 的方案用 `_cancel_event.is_set()` 区分取消和异常，逻辑正确。但需要注意：修复 1 中 `stop_transcription()` 已经处理了状态恢复和队列推进，`_on_done()` 的修改主要是为了**超时和异常**场景的完整性。

#### 修复 4（新增）：`_stop_transcription()` 在 home_page 中恢复工具栏

**文件**：`src/gui/home_page.py`

当前代码（line 865-870）：
```python
def _stop_transcription(self, file_path):
    """停止转写"""
    if self._app and hasattr(self._app, '_transcription_handler'):
        self._app._transcription_handler.stop_transcription(file_path)
        self._recording_bar.set_transcribing(False)
        self.refresh_file_list()
```

由于修复 1 中 `stop_transcription()` 现在会发射 `transcription_done` 信号，而 `_on_transcription_done_handler()` 已经处理了工具栏恢复和 `refresh_file_list()`，所以 `_stop_transcription()` 中的 `set_transcribing(False)` 和 `refresh_file_list()` 变成了冗余调用。不会出错，但可以简化：

```python
def _stop_transcription(self, file_path):
    """停止转写"""
    if self._app and hasattr(self._app, '_transcription_handler'):
        self._app._transcription_handler.stop_transcription(file_path)
        # transcription_done 信号会触发 _on_transcription_done_handler()
        # 其中已包含 set_transcribing(False) 和 refresh_file_list()
```

---

### 三、完整状态转换矩阵（优化版）

MiMo 的矩阵缺少了工具栏按钮列。以下是完整版：

#### 3.1 文件行按钮

| 当前状态 | 触发操作 | 目标状态 | file_manager 持久化 | 文件行按钮变化 |
|----------|---------|---------|-------------------|--------------|
| PENDING | 点击"转写" | PROCESSING | 是 | 转写/删除 → 停止 |
| PENDING | 点击"删除" | （移除） | 是 | 从列表消失 |
| PROCESSING | 点击"停止" | PENDING | **是** | 停止 → 转写/删除 |
| PROCESSING | 转写完成 | DONE | 是 | 停止 → 预览/打开/发言人/重试/导出 |
| PROCESSING | 转写失败/超时 | FAILED | 是 | 停止 → 重试 |
| DONE | 点击"重试" | PROCESSING | 是 | 预览/... → 停止 |
| FAILED | 点击"重试" | PROCESSING | 是 | 重试 → 停止 |
| * | 程序异常退出 | PENDING | 启动时恢复 | 停止 → 转写/删除 |

#### 3.2 工具栏按钮

| 全局状态 | "开始转写" | "合并转写" | "AI 摘要" | "添加文件" | "清空列表" |
|---------|-----------|-----------|----------|-----------|-----------|
| 空闲，有待转写文件 | 启用 | 需选中 2+ | 启用 | 启用 | 需有文件 |
| **转写中** | **禁用（"转写中..."）** | **禁用** | **禁用** | 启用 | **禁用** |
| **停止后（修复前）** | **禁用（"转写中..."）← BUG** | **禁用 ← BUG** | **禁用 ← BUG** | 启用 | 禁用 |
| **停止后（修复后）** | **启用** | **需选中 2+** | **启用** | 启用 | 需有文件 |

#### 3.3 录音栏

| 事件 | 录音栏变化 |
|------|-----------|
| 转写开始 | `set_transcribing(True)` — 仅设置内部标志 |
| 转写完成 | `_on_transcription_done_handler()` → `set_transcribing(False)` |
| 转写停止 | `stop_transcription()` → `transcription_done` → handler → `set_transcribing(False)` |

---

### 四、对 MiMo 待审问题的回答

| MiMo 问题 | 回答 |
|-----------|------|
| PAUSED 状态是否需要？ | **不需要。** 停止后回到 PENDING 足够。PAUSED 增加了状态机复杂度但没有实际功能（没有"恢复转写"的概念，每次都是重新转写） |
| 停止特定文件逻辑 | **当前架构不支持停止单个文件。** worker 是单线程顺序处理，`cancel_event` 取消整个任务。`file_path` 参数只用于标记哪个文件被用户点击，但实际停止的是整个任务。建议：保留参数但行为是停止全部，日志中说明 |
| `_cancel_event` 时序 | **无竞态。** `stop_transcription()` 先 `set()` cancel event，再 join 线程，再处理状态。`_on_done()` 在 join 之后检查 `is_set()`，时序是确定的 |
| `_save_to_file()` 调用频率 | **不是问题。** 恢复逻辑在内存中修改所有文件状态后，只调用一次 `_save_to_file()` |

---

### 五、改动量估算（修正版）

| 文件 | 改动 | 行数 |
|------|------|------|
| `src/gui/transcription.py` | `stop_transcription()` 持久化 + 线程清理 + 队列推进 + 信号发射 | ~20 行 |
| `src/gui/transcription.py` | `_on_done()` 区分取消和异常 | ~10 行 |
| `src/file_manager.py` | 启动时恢复 PROCESSING 状态 | ~8 行 |
| `src/gui/home_page.py` | `_stop_transcription()` 简化（去除冗余调用） | ~3 行 |
| **合计** | | **~41 行** |

---

### 六、执行顺序

```
1. file_manager.py 启动恢复     ← 8 行，独立修改，可单独验证
2. transcription.py stop 完整清理 ← 20 行，核心修复
3. transcription.py _on_done 区分 ← 10 行，异常场景完整性
4. home_page.py 简化             ← 3 行，去冗余
```

修复 1 可独立验证：启动程序 → 开始转写 → 停止 → 检查"开始转写"按钮是否恢复可用。
修复 2 可独立验证：转写中直接关闭程序（kill）→ 重启 → 检查文件状态是否为"待转写"。

---

## [MiMo 验证意见] 2026-07-03

### 一、Qoder 补充项验证

| Qoder claim | 验证结果 | 代码证据 |
|-------------|---------|---------|
| 工具栏按钮不恢复 | ✅ 确认 | `stop_transcription()` 不发 `transcription_done` 信号。只有 `_on_done()` (line 377) 才发。`_on_transcription_done_handler()` (line 556-566) 负责恢复 `_btn_transcribe` 和 `_btn_ai_summary` |
| 队列不推进 | ✅ 确认 | `stop_transcription()` 不调用 `_task_queue.complete_current_task()` 和 `_check_queue()`。只有 `_on_done()` (line 378-381) 才调用 |
| 线程引用不清理 | ✅ 确认 | `stop_transcription()` join 后不置 None。`_on_done()` (line 370-371) 才清理 `_thread = None` + `_queue = None` |
| `_file_status` 不清理 | ✅ 确认 | 但 `_execute_task()` (line 146) 会重置为 `{}`，影响不大 |

### 二、Qoder 方案安全性验证

| 检查项 | 结论 |
|--------|------|
| `transcription_done.emit()` 在 stop 中是否安全 | ✅ 安全。`_done_called` 防重入；stop 先 join 线程再 emit，`_on_done()` 不会再触发 |
| `_check_queue()` 是否会导致新任务立即启动 | ✅ 不会。`_check_queue()` → `_execute_task()` 检查 `_transcribing`（已 False），直接 return |
| 竞态条件 | ⚠️ 理论上存在极小窗口（用户点击 stop 和超时同时触发），但 `_done_called` 保护了 `_on_done()`，实际安全 |

### 三、结论

Qoder 方案正确且完整，比我原方案多解决了**工具栏按钮卡死**和**队列不推进**两个同等严重的问题。按 Qoder 方案实施。
