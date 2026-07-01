# 双轨合并转写 v2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复双轨合并转写的核心问题：merge 参数未传递、嵌入向量覆盖、声纹匹配时机、标签格式、手动合并 UI。

**Architecture:** 7 个 Step 逐步实施：P0 修复 merge 传递 → P1 嵌入分组 → 标签格式统一 → P2 声纹匹配时机 → P3 AI 总结 → P4 写入逻辑 → Step 7 手动合并 UI。

**Tech Stack:** Python, PySide6, CAM++ 声纹, FunASR ASR

## Global Constraints

- 所有修改针对 `C:\侧耳倾听\`，`C:\MeetScribe\` 只读
- 先写方案→查证→实施→验证
- 跨轨匹配阈值：0.50（与 HIGH_CONFIDENCE 一致）
- 标签格式：统一使用 `本地-N`/`远程-N`

---

## Task 1: 修复 merge 参数传递（P0）

**Covers:** P0（合并未触发）

**Files:**
- Modify: `src/gui/home_page.py:848-870`（`_transcribe_single`）
- Modify: `src/gui/home_page.py:867-920`（`_start_transcription`）
- Test: `tests/test_gui_home.py`

**Interfaces:**
- Consumes: `handler.start(file_paths, fmt, speaker_names, out_dir, merge=True)`
- Produces: worker 收到 `merge=True` 后走合并分支

- [ ] **Step 1: 修改 `_transcribe_single()` 检测到双轨时传 `merge=True`**

```python
# home_page.py:866 修改为：
if pair:
    handler.start(files_to_transcribe, fmt, {}, "", merge=True)
else:
    handler.start(files_to_transcribe, fmt, {}, "")
```

- [ ] **Step 2: 修改 `_start_transcription()` 检测到双轨时传 `merge=True`**

```python
# home_page.py:913-914 修改为：
has_dual = any(find_dual_track_pair(fp) for fp in all_paths if fp not in processed)
handler.add_to_queue(all_paths)
handler.start(all_paths, fmt, {}, "", merge=has_dual)
```

- [ ] **Step 3: 运行测试验证**

Run: `python -m pytest tests/test_gui_home.py -x -q`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/gui/home_page.py tests/test_gui_home.py
git commit -m "fix: 检测到双轨时传 merge=True 触发合并分支"
```

---

## Task 2: 嵌入向量分组存储（P1）

**Covers:** P1（嵌入向量覆盖）

**Files:**
- Modify: `src/transcribe_worker.py:58-79`（`_send_embeddings`）
- Modify: `src/gui/transcription.py:254-261`（spk_embeddings 消息处理）
- Modify: `src/gui/transcription.py:537-546`（`_extract_speaker_embeddings`）
- Modify: `src/gui/transcription.py:373-414`（`_save_embeddings_to_disk`）
- Test: `tests/test_transcription.py`

**Interfaces:**
- Consumes: worker 发送 `("spk_embeddings", {"track": "mic"/"sys", "embeddings": {...}})`
- Produces: `self._speaker_embeddings = {"mic": {0: emb}, "sys": {0: emb}}`

- [ ] **Step 1: 修改 `_send_embeddings()` 附带 track 标记**

```python
# transcribe_worker.py:58-79 修改为：
def _send_embeddings(queue, transcriber, track="unknown"):
    """从 transcriber 提取说话人嵌入向量并发送到主进程"""
    try:
        embeddings = getattr(transcriber, "spk_embeddings", {})
        logger.debug(f"[WORKER] spk_embeddings count: {len(embeddings)}, track: {track}")
        if embeddings:
            queue.put(("spk_embeddings", {"track": track, "embeddings": dict(embeddings)}))
            logger.debug(f"[WORKER] Sent spk_embeddings for track={track}")
        else:
            logger.debug(f"[WORKER] No spk_embeddings to send for track={track}")
    except Exception as e:
        logger.error(f"[WORKER] Failed to send embeddings: {e}")
```

- [ ] **Step 2: 修改 worker 循环调用时传入 track**

```python
# transcribe_worker.py:174-182 修改为：
for idx, fp in enumerate(file_paths):
    # ... 转写逻辑 ...
    result = transcriber.transcribe(...)
    per_file_texts[fp] = result
    # 发送嵌入向量时附带轨道标记
    track = "mic" if idx == 0 else "sys"
    _send_embeddings(queue, transcriber, track=track)
    _send_sentences(queue, transcriber)
```

- [ ] **Step 3: 修改主进程接收嵌入向量时按轨分组存储**

```python
# transcription.py:254-261 修改为：
elif msg_type == "spk_embeddings":
    data = msg[1]
    track = data.get("track", "unknown")
    embeddings = data.get("embeddings", {})
    if track not in self._speaker_embeddings:
        self._speaker_embeddings[track] = {}
    for spk_id, emb_data in embeddings.items():
        if isinstance(emb_data, (tuple, list)) and len(emb_data) == 2 and isinstance(emb_data[1], (int, float)):
            embedding, quality = emb_data
            self._speaker_embeddings[track][spk_id] = embedding
            self._speaker_qualities[track] = self._speaker_qualities.get(track, {})
            self._speaker_qualities[track][spk_id] = quality
        else:
            self._speaker_embeddings[track][spk_id] = emb_data
```

- [ ] **Step 4: 修改 `_extract_speaker_embeddings()` 支持分组格式**

```python
# transcription.py:537-546 修改为：
def _extract_speaker_embeddings(self):
    """从接收到的嵌入向量中提取每个说话人的代表向量"""
    if not self._speaker_embeddings:
        return {}
    embeddings = {}
    # 支持两种格式：扁平 {spk_id: emb} 和分组 {"mic": {0: emb}, "sys": {0: emb}}
    for key, value in self._speaker_embeddings.items():
        if isinstance(value, dict):
            # 分组格式：展开为 track-spk_id 格式
            for spk_id, emb in value.items():
                if emb is not None:
                    embeddings[f"{key}-{spk_id}"] = emb
        elif value is not None:
            # 扁平格式（兼容）
            embeddings[int(key)] = value
    return embeddings
```

- [ ] **Step 5: 修改 `_save_embeddings_to_disk()` 支持分组格式**

```python
# transcription.py:373-414 修改为：
def _save_embeddings_to_disk(self):
    """将声纹嵌入向量保存到磁盘，程序重启后可恢复"""
    if not self._speaker_embeddings:
        return
    for fp in self._current_batch_paths:
        if not self._app or not hasattr(self._app, 'file_manager'):
            continue
        item = self._app.file_manager.get_file(fp)
        if not item or not item.result_path:
            continue
        result_dir = os.path.dirname(item.result_path)
        base = os.path.splitext(os.path.basename(item.result_path))[0]
        if base.endswith("_transcript"):
            base = base[:-len("_transcript")]
        emb_path = os.path.join(result_dir, f"{base}_embeddings.json")
        emb_data = {}
        for track, track_embeddings in self._speaker_embeddings.items():
            if not isinstance(track_embeddings, dict):
                continue
            for spk_id, embedding in track_embeddings.items():
                if hasattr(embedding, 'tolist'):
                    emb_data[f"{track}-{spk_id}"] = {
                        "vector": embedding.tolist(),
                        "quality": self._speaker_qualities.get(track, {}).get(spk_id, DEFAULT_SPK_QUALITY),
                        "track": track,
                    }
                else:
                    emb_data[f"{track}-{spk_id}"] = {
                        "vector": list(embedding) if embedding is not None else [],
                        "quality": self._speaker_qualities.get(track, {}).get(spk_id, DEFAULT_SPK_QUALITY),
                        "track": track,
                    }
        try:
            with open(emb_path, "w", encoding="utf-8") as f:
                json.dump(emb_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[EMBEDDINGS] 已保存到 {emb_path} ({len(emb_data)} 个说话人)")
        except Exception as e:
            logger.warning(f"[EMBEDDINGS] 保存失败: {e}")
```

- [ ] **Step 6: 运行测试验证**

Run: `python -m pytest tests/test_transcription.py -x -q`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/transcribe_worker.py src/gui/transcription.py tests/test_transcription.py
git commit -m "fix: 嵌入向量按轨分组存储避免覆盖"
```

---

## Task 3: 标签格式统一 + 下游函数适配

**Covers:** 标签格式统一（第三节 vs 第五节）

**Files:**
- Modify: `src/gui/transcription.py:487-535`（`_apply_voiceprint_match`）
- Modify: `src/gui/transcription.py:552-638`（`_apply_speaker_names`）
- Test: `tests/test_transcription.py`

**Interfaces:**
- Consumes: `self._speaker_embeddings` 为分组格式
- Produces: 转写文本中使用 `本地-N`/`远程-N` 标签

- [ ] **Step 1: 修改 `_apply_voiceprint_match()` 支持 `本地-N`/`远程-N` 格式**

```python
# transcription.py:487-535 关键修改：
# speaker_id 现在是 "mic-0", "sys-1" 格式（从 _extract_speaker_embeddings 返回）
# apply_speaker_mapping 的 mapping key 需要改为 "本地-N" / "远程-N" 格式

def _apply_voiceprint_match(self, name, speaker_id, confidence, embedding, library):
    """将单个说话人的匹配结果写入文件"""
    # speaker_id 现在是 "mic-0" 或 "sys-1" 格式
    # 需要转换为 "本地-0" / "远程-0" 格式用于 apply_speaker_mapping
    if isinstance(speaker_id, str) and "-" in speaker_id:
        track, spk_num = speaker_id.rsplit("-", 1)
        label_map = {"mic": "本地", "sys": "远程"}
        display_label = f"{label_map.get(track, track)}-{spk_num}"
        numeric_id = int(spk_num) + 1  # 1-based for apply_speaker_mapping
    else:
        numeric_id = int(speaker_id) + 1
        display_label = f"Speaker {numeric_id}"

    # 记录匹配结果
    self._voiceprint_match_results[speaker_id] = {
        "name": name,
        "confidence": confidence,
    }
    try:
        if self._app and hasattr(self._app, 'file_manager'):
            for item in self._app.file_manager.files:
                if item.status == FileStatus.DONE and item.result_path:
                    if item.file_path not in self._current_batch_paths:
                        continue
                    str_mapping = item.speaker_names or {}
                    str_mapping[display_label] = name
                    self._app.file_manager.update_speaker_names(item.file_path, str_mapping)
                    if os.path.exists(item.result_path):
                        apply_speaker_mapping(item.result_path, {numeric_id: name})
                        summary_path = get_summary_path(item.result_path)
                        if summary_path and os.path.exists(summary_path):
                            apply_speaker_mapping(summary_path, {numeric_id: name})
                    self.log_message.emit(f"音色库匹配: {display_label} -> {name} ({confidence})")
                    if confidence == "confirmed":
                        track = speaker_id.split("-")[0] if isinstance(speaker_id, str) else "unknown"
                        spk_num = int(speaker_id.split("-")[1]) if isinstance(speaker_id, str) and "-" in speaker_id else 0
                        quality = self._speaker_qualities.get(track, {}).get(spk_num, DEFAULT_SPK_QUALITY)
                        source_name = getattr(item, 'file_name', 'auto_match')
                        library.add_speaker(name, embedding, source=source_name, quality=quality)
                        logger.info(f"自动添加声纹样本: {name}")
    except Exception as e:
        logger.error(f"Apply voiceprint match failed: {e}")
```

- [ ] **Step 2: 修改 `_apply_speaker_names()` 正则匹配支持 `本地-N`/`远程-N`**

```python
# transcription.py:552-638 关键修改：
# 正则从 Speaker\s+(\d+) 扩展为支持 本地-N / 远程-N / Speaker N
# 在 _speaker_names_to_list 中构建完整的标签列表

def _speaker_names_to_list(self, speaker_names, sentences):
    """将说话人名称字典转换为列表格式"""
    # 支持 "本地-0", "远程-1", "Speaker 1" 等格式的 key
    spk_ids = set()
    for s in sentences:
        spk = s.get("spk", -1)
        if spk >= 0:
            spk_ids.add(spk)
    if not spk_ids:
        return []
    max_spk = max(spk_ids)
    return [
        speaker_names.get(str(i), "") or f"Speaker {i + 1}"
        for i in range(max_spk + 1)
    ]
```

- [ ] **Step 3: 运行测试验证**

Run: `python -m pytest tests/test_transcription.py -x -q`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/gui/transcription.py tests/test_transcription.py
git commit -m "fix: 标签格式统一为本地-N/远程-N，下游函数适配"
```

---

## Task 4: 声纹匹配改为合并后执行（P2）

**Covers:** P2（声纹匹配时机）

**Files:**
- Modify: `src/gui/transcription.py:420-485`（`_match_voiceprints`）
- Modify: `src/gui/transcription.py:327-340`（`_on_done`）
- Test: `tests/test_transcription.py`

**Interfaces:**
- Consumes: `self._speaker_embeddings` 为分组格式
- Produces: 跨轨匹配结果 `self._cross_track_pairs`

- [ ] **Step 1: 添加跨轨匹配方法**

```python
# transcription.py 新增方法：
def _match_cross_track_speakers(self):
    """跨轨声纹匹配：比较本地轨和远程轨的嵌入向量"""
    if "mic" not in self._speaker_embeddings or "sys" not in self._speaker_embeddings:
        return []
    mic_embs = self._speaker_embeddings["mic"]
    sys_embs = self._speaker_embeddings["sys"]
    if not mic_embs or not sys_embs:
        return []
    import numpy as np
    pairs = []
    used_sys = set()
    for mic_id, mic_emb in sorted(mic_embs.items()):
        mic_arr = np.array(mic_emb) if not isinstance(mic_emb, np.ndarray) else mic_emb
        best_sys_id = None
        best_score = 0
        for sys_id, sys_emb in sys_embs.items():
            if sys_id in used_sys:
                continue
            sys_arr = np.array(sys_emb) if not isinstance(sys_emb, np.ndarray) else sys_emb
            score = np.dot(mic_arr, sys_arr) / (np.linalg.norm(mic_arr) * np.linalg.norm(sys_arr))
            if score > best_score:
                best_score = score
                best_sys_id = sys_id
        # 阈值：跨轨音频质量差异大，用 HIGH_CONFIDENCE（0.50）
        if best_score >= HIGH_CONFIDENCE and best_sys_id is not None:
            pairs.append({
                "mic_id": mic_id,
                "sys_id": best_sys_id,
                "score": float(best_score),
                "mic_label": f"本地-{mic_id}",
                "sys_label": f"远程-{best_sys_id}",
            })
            used_sys.add(best_sys_id)
    return pairs
```

- [ ] **Step 2: 修改 `_on_done()` 先合并嵌入向量再匹配**

```python
# transcription.py:327-340 修改为：
def _on_done(self):
    """转写完成"""
    if self._done_called:
        return
    self._done_called = True
    self._transcribing = False
    self._poll_timer.stop()
    # ... 现有逻辑 ...
    # 合并嵌入向量后执行声纹匹配
    if self._speaker_embeddings:
        self._match_voiceprints()
        # 跨轨匹配（双轨模式）
        self._cross_track_pairs = self._match_cross_track_speakers()
    self._apply_speaker_names()
    # ... 清理资源 ...
```

- [ ] **Step 3: 运行测试验证**

Run: `python -m pytest tests/test_transcription.py -x -q`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add src/gui/transcription.py tests/test_transcription.py
git commit -m "fix: 声纹匹配改为合并后执行 + 跨轨声纹匹配"
```

---

## Task 5: AI 总结时机调整（P3）

**Covers:** P3（AI 总结基于合并文本）

**Files:**
- Modify: `src/gui/transcription.py:279-305`（auto_summary 消息处理）
- Test: `tests/test_transcription.py`

**Interfaces:**
- Consumes: 声纹匹配和姓名应用已完成
- Produces: AI 总结基于声纹匹配后的合并转写文本

- [ ] **Step 1: 确认 auto_summary 消息处理中声纹匹配已在前面执行**

当前代码 `transcription.py:283-288` 已经在 auto_summary 处理中调用了 `_match_voiceprints()` 和 `_apply_speaker_names()`。需要确认 `_on_done()` 中已经调用过，避免重复执行。

```python
# transcription.py:279-305 确认逻辑：
elif msg_type == "auto_summary":
    base, out_dir = msg[1], msg[2]
    # 声纹匹配已在 _on_done() 中执行，此处仅确保姓名应用
    if not self._names_applied:
        self._apply_speaker_names()
        self._names_applied = True
    # 读取合并后的转写文件（已包含真实姓名）
    auto_summary = self._app.config.get("auto_summary", True) if self._app else True
    should_summary = (
        auto_summary is True
        or auto_summary == "转写后自动生成"
        or auto_summary == "true"
    )
    if should_summary:
        self.log_message.emit(f"[AI摘要] 正在生成摘要...")
        transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
        if os.path.exists(transcript_path):
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript = f.read()
            self._start_summary_async(transcript, base, out_dir)
```

- [ ] **Step 2: 运行测试验证**

Run: `python -m pytest tests/test_transcription.py -x -q`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add src/gui/transcription.py
git commit -m "fix: AI总结确保在声纹匹配和姓名应用之后执行"
```

---

## Task 6: 写入逻辑优化（P4）

**Covers:** P4（`_apply_voiceprint_match` 写入逻辑）

**Files:**
- Modify: `src/gui/transcription.py:487-535`（`_apply_voiceprint_match`，已在 Task 3 中修改）

**说明**：Task 3 中已修改 `_apply_voiceprint_match`，需要确认 merge 模式下只写入合并文件。当前修改已遍历 `_current_batch_paths` 中的文件，merge 模式下子文件的 `result_path` 指向合并文件，所以写入逻辑是正确的。无需额外修改。

- [ ] **Step 1: 验证 merge 模式下写入逻辑**

确认 `merge_done` handler（transcription.py:246-251）将子文件的 `result_path` 指向合并文件，`_apply_voiceprint_match` 遍历时会正确写入。

- [ ] **Step 2: 提交（如需修改）**

---

## Task 7: 手动合并发言人 UI

**Covers:** 第六节（手动合并发言人 UI）

**Files:**
- Modify: `src/gui/dialogs.py:414-543`（SpeakerDialog）
- Modify: `src/gui/transcription.py:844-893`（`_on_summary_finished`）
- Test: `tests/test_gui_dialogs.py`

**Interfaces:**
- Consumes: `self._cross_track_pairs`（从 Task 4 传入）
- Produces: 合并规则存储在 `_metadata.json`

**原型图**：`docs/99-mockups/mockup-speaker-dialog.html`

- [ ] **Step 1: SpeakerDialog 增加跨轨合并区域**

在 `SpeakerDialog.__init__()` 中添加 `cross_track_pairs` 参数，在 `_build()` 中根据是否有双轨数据渲染合并区域。

```python
# dialogs.py:414-436 修改为：
class SpeakerDialog(QDialog):
    def __init__(self, parent, file_name, speakers, on_save=None,
                 speaker_embeddings=None, speaker_qualities=None,
                 audio_path=None, sentences=None, cross_track_pairs=None,
                 is_dual_track=False):
        super().__init__(parent)
        # ... 现有初始化 ...
        self._cross_track_pairs = cross_track_pairs or []
        self._is_dual_track = is_dual_track
        self._merge_rules = []  # 用户确认的合并规则
        self._build()
```

- [ ] **Step 2: 在 `_build()` 中添加跨轨合并区域**

```python
# dialogs.py _build() 方法中，在 speaker_list 之后添加：
if self._is_dual_track and self._cross_track_pairs:
    merge_frame = QFrame()
    merge_frame.setStyleSheet(f"""
        QFrame {{ background-color: #FFFBEB; border: 1px solid #FDE68A;
            border-radius: 8px; padding: 14px 16px; }}
    """)
    merge_layout = QVBoxLayout(merge_frame)
    merge_title = QLabel("跨轨发言人合并")
    merge_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: #92400E;")
    merge_layout.addWidget(merge_title)
    merge_hint = QLabel("声纹匹配检测到以下发言人可能是同一人，确认后转写文本中的标签将统一更新")
    merge_hint.setStyleSheet(f"font-size: 11px; color: #B45309;")
    merge_layout.addWidget(merge_hint)
    for pair in self._cross_track_pairs:
        pair_row = QHBoxLayout()
        pair_row.addWidget(QLabel(f"{pair['mic_label']} = {pair['sys_label']} ({pair['score']:.0%})"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("统一姓名")
        name_input.setFixedWidth(120)
        pair_row.addWidget(name_input)
        confirm_btn = QPushButton("确认")
        confirm_btn.clicked.connect(lambda checked, p=pair, inp=name_input: self._confirm_merge(p, inp))
        pair_row.addWidget(confirm_btn)
        merge_layout.addLayout(pair_row)
    layout.addWidget(merge_frame)
```

- [ ] **Step 3: 添加 `_confirm_merge()` 方法**

```python
def _confirm_merge(self, pair, name_input):
    """确认跨轨合并规则"""
    name = name_input.text().strip()
    if not name:
        return
    self._merge_rules.append({
        "mic_label": pair["mic_label"],
        "sys_label": pair["sys_label"],
        "merged_name": name,
        "score": pair["score"],
    })
    # 预览：更新发言人列表中的姓名
    for spk_id, entry in self._speaker_entries.items():
        if spk_id in (pair["mic_label"], pair["sys_label"]):
            entry["name_input"].setText(name)
```

- [ ] **Step 4: 修改 `_do_save()` 保存合并规则**

```python
def _do_save(self):
    """保存所有修改"""
    # ... 现有保存逻辑 ...
    # 保存合并规则到元数据
    if self._merge_rules:
        metadata_path = self._get_metadata_path()
        metadata = self._load_metadata(metadata_path)
        metadata["speaker_merge_rules"] = self._merge_rules
        self._save_metadata(metadata_path, metadata)
        # 应用合并规则到转写文本
        self._apply_merge_rules()
    # ... 回调 ...
```

- [ ] **Step 5: 添加合并规则应用方法**

```python
def _apply_merge_rules(self):
    """应用跨轨合并规则到转写文本"""
    if not self._merge_rules or not self._app:
        return
    for item in self._app.file_manager.files:
        if item.status == FileStatus.DONE and item.result_path:
            if item.file_path not in self._current_batch_paths:
                continue
            if os.path.exists(item.result_path):
                with open(item.result_path, "r", encoding="utf-8") as f:
                    text = f.read()
                for rule in self._merge_rules:
                    text = text.replace(f"**{rule['mic_label']}**", f"**{rule['merged_name']}**")
                    text = text.replace(f"**{rule['sys_label']}**", f"**{rule['merged_name']}**")
                with open(item.result_path, "w", encoding="utf-8") as f:
                    f.write(text)
```

- [ ] **Step 6: 运行测试验证**

Run: `python -m pytest tests/test_gui_dialogs.py -x -q`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/gui/dialogs.py tests/test_gui_dialogs.py
git commit -m "feat: SpeakerDialog 增加跨轨发言人合并功能"
```

---

## Task 8: 集成测试 + 打包验证

**Covers:** 全部

**Files:**
- Test: `tests/test_gui_home.py`
- Test: `tests/test_transcription.py`
- Test: `tests/test_dual_track_merge.py`

- [ ] **Step 1: 运行全量测试**

Run: `python -m pytest tests/ -x -q`
Expected: PASS

- [ ] **Step 2: 提交**

```bash
git commit -m "test: 双轨合并 v2 集成测试通过"
```

- [ ] **Step 3: 打包验证（可选）**

如有打包环境，执行 PyInstaller + ISCC 打包验证。
