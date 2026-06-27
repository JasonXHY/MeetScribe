# 前端状态与业务逻辑修复方案

> 版本：v1.1（QoderWork 审查合并）
> 日期：2026-06-16
> 状态：已审查，待实施
> 审查人：QoderWork

---

## 一、问题清单

### 问题 1：转写后 AI 摘要未显示在预览中（P0）

**现象**：转写完成后点击"预览"，弹窗中没有 AI 摘要内容。

**根因链路**：

```
worker 发送 ("auto_summary", base, out_dir)
  → 主进程 _poll() → _process_message()
  → 检查 config.auto_summary → 调用 _generate_summary()
  → _generate_summary() 调用 ai.generate_summary()（同步网络请求）
  → 摘要写入 {base}_summary.md
  → 用户点击预览 → _preview_result()
  → get_summary_path(item.result_path) → 检查 summary 文件是否存在
```

**断裂点**：

1. **时序问题**：`_generate_summary()` 是同步阻塞调用（网络请求），在 `_poll()` 的 QTimer 轮询中执行。如果 AI 响应慢，摘要文件可能在用户点击预览时尚未写入完成。
2. **路径推导不匹配**：`get_summary_path()` 从 `result_path` 推导摘要路径，逻辑为 `去掉 _transcript 后缀 → 拼接 _summary.md`。但 `_generate_summary()` 中写入的文件名是 `{base}_summary.md`，其中 `base` 来自 worker 的消息。如果 `base` 的计算方式与 `get_summary_path()` 不一致，路径会不匹配。
3. **get_summary_path() 只检查文件存在**：`utils.py:27` 的 `return summary_path if os.path.exists(summary_path) else None`，如果文件不存在直接返回 `None`，PreviewDialog 不会显示摘要按钮。

**修复方案**：

**F1-1**：`get_summary_path()` 增加多模式查找

```python
def get_summary_path(transcript_path):
    if not transcript_path:
        return None
    result_dir = os.path.dirname(transcript_path)
    base = os.path.splitext(os.path.basename(transcript_path))[0]
    # 去掉 _transcript 后缀
    if "_transcript" in base:
        base = base.replace("_transcript", "")
    # 尝试多种命名模式
    candidates = [
        os.path.join(result_dir, f"{base}_summary.md"),
        os.path.join(result_dir, f"{base}_transcript_summary.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None
```

**F1-2**：`_preview_result()` 增加摘要等待提示

```python
def _preview_result(self, file_path):
    item = self._app.file_manager.get_file(file_path)
    if item and item.result_path and os.path.exists(item.result_path):
        summary_path = get_summary_path(item.result_path)
        if summary_path is None:
            # 摘要不存在，检查是否刚转写完（60秒内）
            import time
            file_age = time.time() - os.path.getmtime(item.result_path)
            if file_age < 60:
                QMessageBox.information(self, "提示", "AI 摘要正在生成中，请稍后再预览")
                return
        dialog = PreviewDialog(self, item.file_name, item.result_path, summary_path)
        dialog.exec()
```

**F1-3**：确保 `auto_summary` 消息在 `file_done` 之后发送（worker 侧已有保证，无需修改）

---

### 问题 2：发言人未自动写入转写结果（P0）

**现象**：转写完成后，结果文件中仍是 `Speaker 1`、`Speaker 2`，音色库中已有的说话人名字没有自动替换。

**根因链路**：

```
worker 发送 ("spk_embeddings", embeddings)
  → 主进程 _process_message() → self._speaker_embeddings = embeddings
  → worker 发送 ("done",)
  → _on_done() → if self._speaker_embeddings: self._match_voiceprints()
  → _match_voiceprints() → library.match_with_confidence() → apply_speaker_mapping()
```

**断裂点**：

1. **`_speaker_embeddings` 可能为空**：如果 CAM++ 模型未启用或 worker 未发送 `spk_embeddings` 消息，`_on_done()` 中的 `if self._speaker_embeddings` 为 False，匹配逻辑不会执行。
2. **`_match_voiceprints()` 在 `_on_done()` 中调用，但 `_on_done()` 可能在 `auto_summary` 消息处理之前执行**：`_poll()` 先处理队列中的所有消息（包括 `auto_summary`），然后检查进程状态调用 `_on_done()`。如果 `auto_summary` 的摘要生成耗时较长，`_on_done()` 会在摘要完成之前执行，导致发言人匹配在摘要之前完成——这不是问题，但说明时序是正确的。
3. **`apply_speaker_mapping()` 使用正则 `Speaker\s+{spk_id}`**：转写结果中 Speaker 的显示编号是 `spk_id + 1`（从 1 开始），但 `apply_speaker_mapping()` 传入的 mapping 是 `{speaker_id + 1: name}`。正则 `Speaker\s+{spk_id}` 中的 `spk_id` 是传入的 key（即 `speaker_id + 1`），所以正则应该匹配 `Speaker 1`（当 speaker_id=0 时）。**逻辑正确**。

**真正的问题**：`_match_voiceprints()` 依赖 `self._speaker_embeddings` 非空。如果 worker 发送了 `spk_embeddings` 消息但主进程在 `_poll()` 中还没处理到就执行了 `_on_done()`，嵌入向量会丢失。

<!-- [QW] 发现更严重的问题（P0 级 Bug）：

**`_current_batch_paths` 从未被填充！**

grep 全项目确认 `_current_batch_paths` 只有 3 处引用：
- `transcription.py:57` — `self._current_batch_paths = set()` （初始化为空集）
- `transcription.py:335` — `if item.file_path not in self._current_batch_paths: continue` （过滤条件）
- `transcription.py:373` — `if item.file_path in self._current_batch_paths:` （条件判断）

整个 `src` 目录中**没有任何代码**向 `_current_batch_paths` 添加元素（无 `.add()`、无 `.update()`、无非空赋值）。

这意味着 `_match_voiceprints()` 中的 `if item.file_path not in self._current_batch_paths: continue` **永远为 True**，所有文件都被 `continue` 跳过，**声纹匹配结果永远不会被写入任何文件**。

此 Bug 是问题 2（发言人未自动写入转写结果）的真正根因，比文档分析的"时序问题"严重得多。

**[QW] 修复建议**：需要在转写开始时填充 `_current_batch_paths`。例如在 `_execute_task()` 或 `start()` 方法中：
```python
self._current_batch_paths = set(task.file_paths)  # 或 handler.start() 中设置
```
-->

**修复方案**：

**F2-4（QW 新增，最高优先级）**：修复 `_current_batch_paths` 未填充

```python
# gui/transcription.py — 在 _execute_task() 或 start() 中填充
def start(self, file_paths, fmt, speaker_names, out_dir, merge=False):
    task = TranscriptionTask(file_paths=file_paths, fmt=fmt, ...)
    self._current_batch_paths = set(file_paths)  # ← 新增：填充批次路径
    # ...
```

**F2-3**：确保 worker 中 `spk_embeddings` 始终发送

在 `transcribe_worker.py` 中，`_send_embeddings()` 在每个文件转写完成后调用。如果 CAM++ 未启用（`disable_spk=True`），`transcriber.spk_embeddings` 为空，不会发送消息。需要在 worker 的 `done` 消息之前确保发送了 `spk_embeddings`（即使是空的）。

---

### 问题 3：多发言人同名冲突（P1）

**现象**：Speaker 1 和 Speaker 2 都匹配到音色库中的"张三"，结果文件中两个 Speaker 都被替换为"张三"。

**根因**：`_match_voiceprints()` 对每个说话人独立匹配，不检查冲突。

**当前逻辑**（`transcription.py:328-358`）：

```python
for speaker_id, embedding in speaker_embeddings.items():
    name, confidence = library.match_with_confidence(embedding)
    if name:
        # 直接写入映射，不检查其他说话人是否也映射到同一个人
        str_mapping[str_key] = name
```

**用户要求的策略**：
- 多个说话人匹配到同一音色库成员时，只写入**置信度最高**的那个
- 其他说话人的匹配结果暂不写入，等用户后续确认

**修复方案**：

**F3-1**：重写 `_match_voiceprints()` 为两阶段匹配

```python
def _match_voiceprints(self):
    if not self._speaker_embeddings:
        return
    if self._voiceprint_matched:
        return
    self._voiceprint_matched = True

    try:
        from voiceprint import VoiceprintLibrary
        library = VoiceprintLibrary()
        speaker_embeddings = self._extract_speaker_embeddings()
        if not speaker_embeddings:
            return

        # 第一阶段：收集所有匹配结果
        all_matches = []  # [(speaker_id, name, confidence, score)]
        for speaker_id, embedding in speaker_embeddings.items():
            name, score = library.match(embedding)
            if name:
                from voiceprint import HIGH_CONFIDENCE
                confidence = "confirmed" if score >= HIGH_CONFIDENCE else "suggested"
                all_matches.append((speaker_id, name, confidence, score))

        # 第二阶段：冲突检测 — 对每个音色库成员，只保留 score 最高的
        best_by_name = {}  # {name: (speaker_id, confidence, score)}
        for speaker_id, name, confidence, score in all_matches:
            if name not in best_by_name or score > best_by_name[name][2]:
                best_by_name[name] = (speaker_id, confidence, score)

        # 第三阶段：写入映射
        for name, (speaker_id, confidence, score) in best_by_name.items():
            self._apply_voiceprint_match(name, speaker_id, confidence, library)

        # 记录未写入的匹配（供日志和后续确认）
        written_ids = {v[0] for v in best_by_name.values()}
        for speaker_id, name, confidence, score in all_matches:
            if speaker_id not in written_ids:
                logger.info(f"[VOICEPRINT] Skipped conflict: Speaker {speaker_id+1} -> {name} "
                          f"(score={score:.3f}, lower than best match)")

    except Exception as e:
        logger.error(f"Voiceprint matching failed: {e}")
```

**F3-2**：提取 `_apply_voiceprint_match()` 辅助方法

```python
def _apply_voiceprint_match(self, name, speaker_id, confidence, embedding, library):
    """将单个说话人的匹配结果写入文件"""
    try:
        if self._app and hasattr(self._app, 'file_manager'):
            for item in self._app.file_manager.files:
                if item.status == FileStatus.DONE and item.result_path:
                    if item.file_path not in self._current_batch_paths:
                        continue
                    str_mapping = item.speaker_names or {}
                    str_key = str(speaker_id + 1)
                    str_mapping[str_key] = name
                    self._app.file_manager.update_speaker_names(
                        item.file_path, str_mapping
                    )
                    if os.path.exists(item.result_path):
                        apply_speaker_mapping(item.result_path, {speaker_id + 1: name})
                        summary_path = get_summary_path(item.result_path)
                        if summary_path and os.path.exists(summary_path):
                            apply_speaker_mapping(summary_path, {speaker_id + 1: name})

                    self.log_message.emit(
                        f"音色库匹配: Speaker {speaker_id + 1} -> {name} ({confidence})"
                    )

                    # confirmed 级别自动追加声纹样本
                    if confidence == "confirmed":
                        quality = self._speaker_qualities.get(speaker_id, DEFAULT_SPK_QUALITY)
                        source_name = getattr(item, 'file_name', 'auto_match')
                        library.add_speaker(name, embedding,
                            source=source_name, quality=quality)
    except Exception as e:
        logger.error(f"Apply voiceprint match failed: {e}")
```

---

### 问题 4：按钮状态切换延迟（P1）

**现象**：点击行"转写"按钮后，行按钮没有立即变为"停止"状态，要等 worker 发送 `processing` 消息后才更新。

**老版本方案**（`MeetScribe/src/gui/file_list_view.py:525-589`）：

```python
# 所有按钮一次性创建，通过 pack()/pack_forget() 切换可见性
is_done = (status == FileStatus.DONE and has_result)
is_processing = (status == FileStatus.PROCESSING)

# DONE → 显示 preview/open/speaker/retry/export
# PROCESSING → 显示 stop
# PENDING → 显示 transcribe/delete
```

**新版本方案**（`侧耳倾听/src/gui/file_list_view.py`）：

```python
# set_files() 每次调用完全重建表格
# _create_action_buttons() 根据 status 字符串创建对应按钮
```

**问题**：`_transcribe_single()` 只更新主按钮（`setEnabled(False)` + `setText("转写中...")`），不触发文件列表刷新。行按钮要等 worker 发送 `("processing", fp)` 消息后，通过 `_on_file_status_changed()` → `refresh_file_list()` 才更新。

**修复方案**：

**F4-1**：`_transcribe_single()` 中添加即时刷新

```python
def _transcribe_single(self, file_path):
    if self._app and hasattr(self._app, '_transcription_handler'):
        handler = self._app._transcription_handler
        if handler.is_transcribing:
            QMessageBox.information(self, "提示", "正在转写中，请等待完成")
            return
        fmt = self.get_selected_format()
        handler.start([file_path], fmt, {}, "")
        self._btn_transcribe.setEnabled(False)
        self._btn_transcribe.setText("转写中...")
        self._log(f"开始转写: {os.path.basename(file_path)}")
        # 新增：立即刷新文件列表，让行按钮显示处理中状态
        self.refresh_file_list()
```

**F4-2**：`_start_transcription()` 批量转写同样添加即时刷新

```python
def _start_transcription(self):
    # ... 现有逻辑 ...
    handler.start(all_paths, fmt, {}, "")  # 注意：变量名是 all_paths，不是 paths
    self._btn_transcribe.setEnabled(False)
    self._btn_transcribe.setText("转写中...")
    self._log(f"开始批量转写: {len(all_paths)} 个文件")
    # 新增：立即刷新
    self.refresh_file_list()
```

**F4-3**：`_retry_transcription()` 同样添加即时刷新

```python
def _retry_transcription(self, file_path):
    self._log(f"重新转写: {os.path.basename(file_path)}")
    self._transcribe_single(file_path)  # 已包含 refresh_file_list()
```

---

## 二、改动汇总

| 编号 | 修复 | 文件 | 改动量 | 风险 |
|------|------|------|--------|------|
| F1-1 | get_summary_path 多模式查找 | utils.py | ~10行 | 低 |
| F1-2 | 预览时摘要等待提示（含时间检查） | home_page.py | ~8行 | 低 |
| ~~F2-1~~ | ~~_on_done 排空队列~~ | ~~gui/transcription.py~~ | ~~删除~~ | ~~QW-3: 与 _poll() 重复~~ |
| ~~F2-2~~ | ~~新增 _drain_queue 方法~~ | ~~gui/transcription.py~~ | ~~删除~~ | ~~QW-3: _poll() 已实现~~ |
| F2-3 | worker 确保发送 spk_embeddings | transcribe_worker.py | ~5行 | 低 |
| **F2-4** | **修复 `_current_batch_paths` 未填充** | **gui/transcription.py** | **~2行** | **低：在 start() 中赋值** |
| F3-1 | 两阶段匹配+冲突检测 | gui/transcription.py | ~40行 | 中：重写核心逻辑 |
| F3-2 | 提取 _apply_voiceprint_match | gui/transcription.py | ~30行 | 低：纯重构 |
| F4-1 | _transcribe_single 即时刷新 | home_page.py | ~2行 | 低 |
| F4-2 | _start_transcription 即时刷新 | home_page.py | ~2行 | 低 |
| F4-3 | _retry_transcription 即时刷新 | home_page.py | ~1行 | 低 |

---

## 三、验证方法

```bash
# 1. 基础测试（不依赖转写）
pytest tests/test_tdd_flows.py -v -k "not test_transcription_16min and not test_transcription_34min"

# 2. 转写+AI 摘要端到端测试
pytest tests/test_tdd_flows.py::TestTranscriptionWithRealAudio::test_transcription_16min -v --timeout=600 -s

# 3. 手动验证清单
# - 转写完成后点击"预览"，确认摘要区域有内容
# - 转写完成后检查结果文件，确认 Speaker N 已被替换为音色库中的名字
# - 多说话人场景下，确认同名冲突时只写入最高置信度的匹配
# - 点击行"转写"按钮后，行按钮立即显示为"停止"状态
```

---

## 四、注意事项

1. **F3-1 改动较大**：重写了 `_match_voiceprints()` 的核心逻辑，需要充分测试多说话人场景
2. **F2-2 的 `_drain_queue()`**：确保在 `_on_done()` 之前处理完所有队列消息，防止 `spk_embeddings` 丢失
3. **F1-1 的多模式查找**：向后兼容旧版本的摘要文件命名
4. **F4 的即时刷新**：可能导致短暂的 UI 闪烁（表格重建），但用户体验远好于延迟更新

---

## 五、QoderWork 审查汇总

> 审查日期：2026-06-16
> 审查方式：逐项对照源代码（gui/transcription.py、home_page.py、utils.py、transcribe_worker.py、voiceprint.py）+ 全项目 grep 验证

### 审查发现

| 编号 | 类型 | 位置 | 发现 | 严重性 |
|------|------|------|------|--------|
| QW-1 | **遗漏 Bug** | `_current_batch_paths` | 变量初始化为 `set()` 但全项目从未填充，导致 `_match_voiceprints()` 中所有文件被 `continue` 跳过，声纹匹配永远不写入。这是问题 2 的真正根因 | **P0** |
| QW-2 | **代码错误** | F3-1 written_ids | `best_by_name[n]` 返回 3 元组但解包为 4 变量，运行时抛 `ValueError` | **P0** |
| QW-3 | 冗余方案 | F2-1 / F2-2 | `_drain_queue()` 与 `_poll()` 第 166-173 行的 while 循环逻辑完全重复，`_poll()` 已实现排空 | 中：建议删除 |
| QW-4 | 逻辑盲区 | F1-2 | `is_transcribing` 在 `_on_done()` 中已为 False，但摘要可能仍在生成中，此时不会显示等待提示 | 中：补充时间检查 |
| QW-5 | 代码不匹配 | F4-2 伪代码 | `paths` → 实际为 `all_paths`；`merge=merge_needed` 参数在 `_start_transcription()` 中不存在 | 低：变量名差异 |
| QW-6 | 路径引用 | 多处 | 文档引用 `transcription.py`，实际路径为 `src/gui/transcription.py` | 低：标注不清 |
| QW-7 | 硬编码 | F3-1 第 191 行 | `score >= 0.50` 应引用 `voiceprint.HIGH_CONFIDENCE` 常量 | 低：一致性 |
| QW-8 | 性能 | F3-2 第 247 行 | `_extract_speaker_embeddings()` 在 `_apply_voiceprint_match()` 中重复调用，建议传参 | 低：效率优化 |

### 建议修改后的修复优先级

| 优先级 | 修复 | 说明 |
|--------|------|------|
| 1 | **F2-4（QW 新增）** | 修复 `_current_batch_paths` 未填充，在 `start()` 中赋值 `set(file_paths)` |
| 2 | **F3-1（修正）** | 两阶段匹配 + 冲突检测，修复 `written_ids` 解包错误，引用 `HIGH_CONFIDENCE` 常量 |
| 3 | **F1-1 + F1-2** | 摘要路径多模式查找 + 预览等待提示（补充时间检查） |
| 4 | **F4-1 ~ F4-3** | 按钮即时刷新（修正 F4-2 变量名） |
| 5 | **F2-3** | worker 端确保发送 `spk_embeddings` |
| ~~6~~ | ~~F2-1 / F2-2~~ | ~~删除：`_poll()` 已实现相同功能~~ |
