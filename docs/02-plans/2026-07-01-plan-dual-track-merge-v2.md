# 双轨合并转写 v2 方案

> 日期：2026-07-01
> 背景：v1 的合并逻辑有多个设计缺陷，需要重新设计

---

## 一、当前问题总结

### P0：合并未触发
`handler.start()` 的 `merge` 参数传空字符串 `""`（falsy），worker 走了 else 分支（逐文件独立转写），`build_merged_transcript()` 从未被调用。

### P1：嵌入向量覆盖
worker 循环转写两个文件时，每个文件的嵌入向量通过 `_send_embeddings()` 发送到主进程，`self._speaker_embeddings[spk_id]` 用 spk_id（0, 1, 2...）做 key，第二个文件的 Speaker 0 会覆盖第一个文件的 Speaker 0。

### P2：声纹匹配时机
声纹匹配在 `_on_done()` → `_match_voiceprints()` 中执行，用的是 `self._speaker_embeddings`。由于 P1 的覆盖，只保留了最后一个文件的嵌入向量。

### P3：AI 总结基于合并文本
合并文本中发言人标签是 `本地-0`、`远程-0`，AI 总结时无法知道这是同一个人。且合并文本丢失了声纹匹配结果（匹配发生在合并之后）。

### P4：`_apply_voiceprint_match` 写入逻辑
匹配后写入文件时遍历 `file_manager.files` 中状态为 DONE 的文件。merge 模式下子文件和合并文件都标记为 DONE，可能导致名字被写入多个文件。

---

## 二、期望的正确流程

```
1. 两轨分别转写
   - 各自识别说话人（Speaker 0, 1, 2...）
   - 各自提取嵌入向量
   - 嵌入向量按轨分组存储（不覆盖）

2. 合并转写
   - 文本按时间戳交错
   - 发言人标签：保留原始 Speaker N，加轨道前缀（本地-N / 远程-N）
   - 保留时间戳信息

3. 声纹匹配（合并后）
   - 用两轨的所有嵌入向量一起去音色库匹配
   - 匹配结果应用到合并转写文件

4. 姓名提取（合并后）
   - 从合并转写文本中提取发言人姓名
   - 匹配结果优先级：声纹 confirmed > 姓名提取 > 保留 Speaker N

5. AI 总结
   - 基于声纹匹配 + 姓名应用后的合并转写文本生成
   - 总结中使用真实姓名（而非 Speaker N）

6. 手动合并（用户可选）
   - 用户在发言人管理中可以合并跨轨的同一人
   - 合并后转写文本和总结中的标签统一更新
```

---

## 三、嵌入向量分组存储

### 当前数据结构
```python
self._speaker_embeddings = {spk_id: embedding}  # spk_id: 0, 1, 2...
```

### 改为按轨分组
```python
self._speaker_embeddings = {
    "mic": {0: emb, 1: emb},    # 麦克风轨的嵌入向量
    "sys": {0: emb, 1: emb},    # 系统音频轨的嵌入向量
}
```

### worker 侧修改
```python
# transcribe_worker.py:179 之后
# 发送嵌入向量时附带轨道标记
queue.put(("spk_embeddings", {"track": "mic" if idx == 0 else "sys", "embeddings": embeddings}))
```

### 主进程侧修改
```python
# transcription.py:254-261
elif msg_type == "spk_embeddings":
    track = msg[1].get("track", "unknown")
    embeddings = msg[1].get("embeddings", {})
    if track not in self._speaker_embeddings:
        self._speaker_embeddings[track] = {}
    for spk_id, data in embeddings.items():
        self._speaker_embeddings[track][spk_id] = data
```

---

## 四、声纹匹配改为合并后执行

### 当前时序
```
worker: 转写A → 发嵌入 → 转写B → 发嵌入 → done
主进程: 收嵌入(覆盖) → _on_done() → _match_voiceprints() → _apply_speaker_names() → AI总结
```

### 改为
```
worker: 转写A → 发嵌入(带track) → 转写B → 发嵌入(带track) → merge文本 → done
主进程: 收嵌入(分组存储) → _on_done() → 合并嵌入向量 → _match_voiceprints() → _apply_speaker_names() → AI总结
```

### 合并嵌入向量逻辑
```python
def _merge_embeddings_for_matching(self):
    """将按轨分组的嵌入向量合并为扁平结构，用于声纹匹配"""
    merged = {}
    for track, embeddings in self._speaker_embeddings.items():
        for spk_id, emb in embeddings.items():
            # 用 track prefix 避免 ID 冲突
            merged[f"{track}-{spk_id}"] = emb
    return merged
```

### 声纹匹配修改
`_match_voiceprints()` 使用合并后的嵌入向量。匹配结果的 key 从 `spk_id`（int）改为 `track-spk_id`（string）。

---

## 五、发言人标签设计

### 合并转写中的标签格式
```
[00:01:23] **本地-0** (张三): 大家好
[00:01:25] **远程-0** (李四): 你好
[00:01:30] **本地-1** (王五): 我们开始吧
```

- `本地-N`：麦克风轨的 Speaker N
- `远程-N`：系统音频轨的 Speaker N
- `(姓名)`：声纹匹配或姓名提取后追加

### 正则兼容
现有正则 `Speaker\s+(\d+)` 匹配 `Speaker N`。合并后标签变为 `本地-N` / `远程-N`，需要：
1. 合并时不做正则替换（保留原始 Speaker N）
2. 在 `_apply_voiceprint_match` 和 `_apply_speaker_names` 中处理带前缀的标签
3. 或者在最终输出时统一替换

**推荐方案**：合并文本保留 `Speaker N` 标签 + 轨道标记元数据，输出时再根据轨道标记生成 `本地-N` / `远程-N`。

---

## 六、手动合并发言人 UI

> **原型图**：`docs/99-mockups/mockup-speaker-dialog.html`（浏览器直接打开）
> **优先级**：v2 必须实现（不可推迟到后续版本），因为"保存到音色库"等基础功能依赖发言人管理弹窗在双轨模式下正常工作。

### 场景
- 本地 Speaker 0（张三）和远程 Speaker 0（李四）实际是同一个人
- 用户需要手动合并

### 行业调研：成熟产品的做法

**AssemblyAI**（[参考](https://www.assemblyai.com/blog/multichannel-speaker-diarization)）：多通道转录和说话人分离**互斥使用**。双通道音频（如客服+客户）直接按通道分配说话人标签，不需要额外的分离算法。输出结构为 `utterances[]`，每条包含 `text`、`speaker`、`channel`、`words[]`。核心思路：**通道本身就是最好的说话人分隔**。

**Otter.ai**（[参考](https://help.otter.ai/hc/en-us/articles/37817248501783-Best-Practices-to-Maximize-Speaker-Identification)）：聚焦会前声纹注册 + 会后手动修正。用户可在转写结果中直接点击说话人标签重命名，支持合并同一人的多个标签。最佳实践建议：会前让参会者注册声纹、确保麦克风距离均匀、会后立即修正说话人名称。

**WhisperX + pyannote**（[参考](https://github.com/SYSTRAN/faster-whisper/discussions/99)）：开源标准管线——先用 pyannote 做说话人分离（diarization），再用 Whisper 逐段转录，最后按时间戳对齐。多通道场景下每个通道独立处理。

**对 MeetScribe 的启示**：
1. **通道即说话人分组**：本地轨（麦克风）= 会议室参会者，远程轨（系统音频）= 线上参会者。这个分组信息应该在 UI 中保留，不要试图在合并后丢失。
2. **手动修正是刚需**：所有成熟产品都提供会后手动修正说话人名称的功能。自动识别只是起点，用户必须能方便地重命名、合并、保存。
3. **声纹库是长期价值**：Otter.ai 的会前注册模式值得借鉴。MeetScribe 的"保存到音色库"功能就是实现这个价值的关键——每次会议修正后保存声纹，下次会议自动匹配更准确。

### 声纹匹配：两轮匹配机制

现有 `_match_voiceprints()` 只做音色库匹配。双轨场景需要**两轮匹配**：

**第一轮：音色库匹配（现有逻辑，按轨分组后执行）**

```
mic 嵌入向量 → 音色库 → 本地-0=张三(confirmed), 本地-1=无匹配
sys 嵌入向量 → 音色库 → 远程-0=李四(suggested), 远程-1=无匹配
```

**第二轮：跨轨嵌入向量匹配（新增）**

```
mic 嵌入向量 ↔ sys 嵌入向量 → 余弦相似度矩阵
本地-0 vs 远程-0: 0.87 → 同一人（高置信）
本地-0 vs 远程-1: 0.23 → 不同人
本地-1 vs 远程-0: 0.31 → 不同人
本地-1 vs 远程-1: 0.82 → 同一人（高置信）
```

跨轨匹配不依赖音色库——即使两个人都不在音色库里，只要声纹相似就能识别。

### 跨轨匹配算法

```python
def _match_cross_track_speakers(self):
    """跨轨声纹匹配：比较本地轨和远程轨的嵌入向量"""
    if "mic" not in self._speaker_embeddings or "sys" not in self._speaker_embeddings:
        return []

    mic_embs = self._speaker_embeddings["mic"]  # {0: emb, 1: emb, ...}
    sys_embs = self._speaker_embeddings["sys"]

    import numpy as np
    pairs = []
    used_sys = set()

    # 对每个本地说话人，找最相似的远程说话人
    for mic_id, mic_emb in sorted(mic_embs.items()):
        mic_arr = np.array(mic_emb)
        best_sys_id = None
        best_score = 0

        for sys_id, sys_emb in sys_embs.items():
            if sys_id in used_sys:
                continue
            sys_arr = np.array(sys_emb)
            score = np.dot(mic_arr, sys_arr) / (
                np.linalg.norm(mic_arr) * np.linalg.norm(sys_arr)
            )
            if score > best_score:
                best_score = score
                best_sys_id = sys_id

        # 阈值：跨轨音频质量差异大，建议阈值 0.65（比音色库匹配的 0.75 低）
        if best_score >= 0.65 and best_sys_id is not None:
            pairs.append({
                "mic_id": mic_id,
                "sys_id": best_sys_id,
                "score": best_score,
                "mic_label": f"本地-{mic_id}",
                "sys_label": f"远程-{best_sys_id}",
            })
            used_sys.add(best_sys_id)

    return pairs
```

**阈值选择**：跨轨音频质量差异大（麦克风 vs 系统音频），建议阈值 0.65，低于音色库匹配的 HIGH_CONFIDENCE（0.75）。可通过配置调整。

### UI 设计

原型图见 `docs/99-mockups/mockup-speaker-dialog.html`，包含两个场景：
- **场景 1（双轨合并）**：发言人列表 + 声纹建议/接受 + 音色库选择 + 跨轨合并区域（智能预填）
- **场景 2（单轨转写）**：发言人列表 + 声纹建议/接受 + 音色库选择，无跨轨合并区域

#### 发言人列表（保留现有交互 + 双轨标签适配）

| 元素 | 说明 |
|------|------|
| 颜色标记 | 每个发言人一个颜色，与现有逻辑一致 |
| 标签 | 双轨模式显示 `本地-N`/`远程-N`，单轨模式显示 `Speaker N` |
| 姓名输入框 | 可直接编辑，回车确认 |
| 声纹建议 | 音色库匹配到但非 confirmed 时显示"可能是 XXX (37%)" + "接受"按钮（**现有逻辑保留**） |
| 从音色库选择 | 下拉框列出音色库所有成员，选择后填入姓名（**现有逻辑保留**） |
| 发言占比 | 该发言人在转写中的占比 |
| 保存到音色库 | 将嵌入向量保存到音色库（**双轨模式下需使用按轨分组的嵌入向量**） |

#### 跨轨合并区域（仅双轨模式显示）

```
─ 跨轨发言人合并 ──────────────────────────────────┐
│ 检测到以下发言人可能是同一人：                       │
│                                                    │
│ ● 本地-0 (张三) = 远程-0 (87%) → [张三____] [确认] │
│ ● 本地-1 = 远程-1 (82%) → [________] [确认]       │
│                                                    │
│ [+ 添加合并规则]                                    │
└────────────────────────────────────────────────────┘
```

**智能预填逻辑**：
1. 跨轨匹配到的对自动出现在合并区，带置信度百分比
2. 如果某一方已有姓名（音色库 confirmed 或用户已填写），预填为统一姓名
3. 如果双方都有姓名但不同（如本地-0=张三，远程-0=李四），预填为音色库 confirmed 的那一个，并标注"姓名冲突"
4. 用户点击"确认"后应用合并规则

**手动添加**：用户可以从下拉框选择本地和远程发言人，手动添加合并规则。

### 合并规则数据结构

```python
# 存储在转写结果的元数据中
speaker_merge_rules = [
    {
        "mic_id": 0, "sys_id": 0,
        "mic_label": "本地-0", "sys_label": "远程-0",
        "score": 0.87,  # 跨轨匹配置信度
        "merged_name": "张三"
    },
]
```

### 合并后文本更新

```python
def apply_speaker_merge(text, merge_rules):
    """应用跨轨发言人合并规则"""
    for rule in merge_rules:
        name = rule["merged_name"]
        mic_label = rule["mic_label"]   # "本地-0"
        sys_label = rule["sys_label"]   # "远程-0"
        # 将双方标签都替换为统一姓名
        text = text.replace(f"**{mic_label}**", f"**{name}**")
        text = text.replace(f"**{sys_label}**", f"**{name}**")
    return text
```

### 实现方式

1. **跨轨匹配在 `_on_done()` 中执行**：声纹匹配完成后，如果有双轨嵌入向量，自动执行跨轨匹配
2. **匹配结果传给 SpeakerDialog**：通过构造函数参数传入 `cross_track_pairs` 列表
3. **SpeakerDialog 渲染合并区**：根据 `cross_track_pairs` 自动填充，用户确认后应用
4. **合并规则存储**：写入转写元数据（`_metadata.json`），供后续加载时恢复
5. **保存到音色库适配**：双轨模式下使用按轨分组的嵌入向量（P1 修复后），保存时标注来源轨

---

## 七、AI 总结时机

### 当前问题
AI 总结在声纹匹配之前执行，总结中使用 `本地-0`、`远程-0` 这种无意义标签。

### 改为
```
合并转写 → 声纹匹配 → 姓名应用 → 读取合并后的转写文件 → AI 总结
```

### 代码修改
`transcription.py` 中 `auto_summary` 消息处理：
```python
elif msg_type == "auto_summary":
    base, out_dir = msg[1], msg[2]
    # 先执行声纹匹配和姓名应用
    if not self._voiceprint_matched and self._speaker_embeddings:
        self._match_voiceprints()
    self._apply_speaker_names()
    # 再读取合并后的转写文件（已包含真实姓名）
    transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
    # ... 生成 AI 总结
```

---

## 八、`_apply_voiceprint_match` 写入逻辑修改

### 当前问题
遍历 `file_manager.files` 中所有 DONE 状态的文件，可能写入多个文件。

### 改为
merge 模式下，只写入合并文件（`_merged_transcript.md`），不写入子文件。

```python
# transcription.py:502-521
for item in self._app.file_manager.files:
    if item.status == FileStatus.DONE and item.result_path:
        # merge 模式：只处理合并文件
        if "_merged_transcript" in os.path.basename(item.result_path):
            apply_speaker_mapping(item.result_path, mapping)
```

---

## 九、实施步骤

### Step 1：修复 merge 参数传递（P0）
- `_transcribe_single()` 和 `_start_transcription()` 检测到双轨时传 `merge=True`

### Step 2：嵌入向量分组存储（P1）
- worker 发送嵌入时附带 track 标记
- 主进程按轨分组存储

### Step 3：声纹匹配改为合并后执行（P2）
- `_on_done()` 中先合并嵌入向量，再执行匹配

### Step 4：合并转写文本设计（P3）
- `merge_dual_transcripts()` 保留原始 Speaker N 标签
- 添加轨道标记元数据

### Step 5：AI 总结时机调整（P3）
- 确保声纹匹配和姓名应用在 AI 总结之前完成

### Step 6：`_apply_voiceprint_match` 写入逻辑（P4）
- merge 模式下只写入合并文件

### Step 7：手动合并 UI（新功能）
- SpeakerDialog 增加跨轨合并区域
- 合并规则存储和应用

---

## 十、测试要点

1. 双轨转写：两个文件分别转写后合并成一份
2. 合并转写内容：按时间戳交错，本地/远程前缀正确
3. 声纹匹配：两轨的嵌入向量都参与匹配
4. 姓名应用：合并转写中使用真实姓名
5. AI 总结：基于合并后的转写内容生成
6. 手动合并：用户可以合并跨轨的同一人
7. 单文件转写：无配对时正常转写
8. 批量转写：多个文件混合双轨和单文件

---

## [S1] Qoder 审查意见（2026-07-01）

> 逐条对照当前代码（transcription.py、transcribe_worker.py、dual_track_merge.py、home_page.py、file_manager.py、utils.py）验证方案，并补充方案未覆盖的问题。

### 一、P0-P4 代码验证

**P0（合并未触发）— 准确，但描述需修正**

方案说"merge 参数传空字符串 `""`"，实际是 `_transcribe_single()` 和 `_start_transcription()` 调用 `handler.start()` 时**根本没传 merge 参数**（默认 `False`）。只有 `_merge_transcribe()`（home_page.py:815）显式传了 `merge=True`。

代码验证：
- `home_page.py:866` — `handler.start(files_to_transcribe, fmt, {}, "")` — 无 merge 参数 ✓
- `home_page.py:914` — `handler.start(all_paths, fmt, {}, "")` — 无 merge 参数 ✓
- `home_page.py:815` — `handler.start(paths, fmt, {}, "", merge=True)` — 仅此处传了 ✓

**P1（嵌入向量覆盖）— 准确**

`transcribe_worker.py:182` 在循环中每个文件后调用 `_send_embeddings(queue, transcriber)`，发送 `{spk_id: embedding}`。`spk_id` 是 0, 1, 2...，第二个文件的 Speaker 0 确实会覆盖第一个的。`transcription.py:254-261` 的接收端用 `self._speaker_embeddings[spk_id] = embedding` 直接覆盖 ✓

**P2（声纹匹配时机）— 准确**

`_match_voiceprints()` 在 `_on_done()`（transcription.py:338-339）和 `auto_summary` handler（transcription.py:284-285）中执行。由于 P1 覆盖，`self._speaker_embeddings` 只保留最后一个文件的数据 ✓

**P3（AI 总结基于合并文本）— 准确，但存在更严重的路径错误**

合并后标签为 `本地-N`/`远程-N`，AI 总结确实无法识别。但验证中发现 **AI 总结根本不会执行**（见下方 P5）。

**P4（`_apply_voiceprint_match` 写入逻辑）— 部分准确**

`transcription.py:502-521` 遍历 `file_manager.files` 中 `status == DONE` 且在 `_current_batch_paths` 中的文件。merge 模式下，`merge_done` handler（transcription.py:246-251）将所有源文件路径的 status 都更新为 DONE 且指向同一个 `rpath`。由于所有源文件都在 `_current_batch_paths` 中，`apply_speaker_mapping` 会对同一个文件执行多次。功能上无害（幂等操作），但确实是冗余的。

---

### 二、方案未覆盖的问题

#### P5（严重）：AI 摘要读取路径错误 — 合并模式下摘要永远不会生成

`transcription.py:301` 的 `auto_summary` handler 构造转写文件路径：

```python
transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
```

但 worker 在合并模式下写的文件是 `{base}_merged_transcript.md`（transcribe_worker.py:192-195），worker 发送的 `auto_summary` 消息中 `base` 不含 `_merged` 后缀。

结果：`transcript_path` 指向不存在的文件 → `os.path.exists()` 返回 False → AI 摘要被静默跳过。**用户永远不会得到合并转写的 AI 摘要。**

修复方案：worker 发送 `auto_summary` 时应传递实际的文件名或完整路径，而不是让主进程重新拼接：

```python
# transcribe_worker.py — 合并模式
queue.put(("auto_summary", base, output_dir, rname))  # 传递 rname

# transcription.py — auto_summary handler
elif msg_type == "auto_summary":
    base, out_dir = msg[1], msg[2]
    rname = msg[3] if len(msg) > 3 else f"{base}_transcript.md"  # 兼容非合并模式
    transcript_path = os.path.join(out_dir, rname)
```

#### P6：合并组被排除在批量转写之外

`file_manager.py` 的 `get_pending_files()` 过滤了 `merged_group`：

```python
return [f for f in self._files
        if f.status == FileStatus.PENDING and not f.merged_group]
```

录音完成后 `_handle_stop_complete()` 调用 `create_merged_group()`，合并显示行和子文件都被设了 `merged_group`。这意味着：

- 批量"开始转写"按钮**无法转写双轨录音**（合并行被过滤）
- 用户只能靠录音后弹窗（走 `_transcribe_single`）或手动选中文件合并转写（`_merge_transcribe`）

方案应明确：是否需要让批量转写支持合并组？如果是，需要修改 `get_pending_files()` 让合并显示行（有 `source_files` 的行）也返回。

#### P7：多组双轨批量合并未处理

方案 Step 1 说"检测到双轨时传 `merge=True`"。但 `_start_transcription()` 可能收集到多组双轨对（如 4 个文件 = 2 组），全部塞进一个 `handler.start()` 调用。worker 的 `is_dual_track_group()` 检查 `len(file_paths) != 2` 时返回 None（dual_track_merge.py:101），4 个文件会被当作"多文件合并"而非"两组双轨分别合并"。

方案需要明确以下二选一：
- **方案 A**：自动拆分——在 `_start_transcription()` 中将多组双轨拆分为多个独立任务
- **方案 B**：worker 支持——在 worker 中检测并拆分多组双轨

推荐方案 A（在主进程拆分），改动更小。

#### P8：摘要主题匹配失败

`_on_summary_finished()` 中（transcription.py）通过 `startswith(base_name + "_transcript")` 匹配文件来更新 topic。合并模式下 `base_name` 是原始 base，但 `result_path` 的文件名是 `{base}_merged_transcript.md`，`startswith` 不匹配（`{base}_merged_transcript` 不以 `{base}_transcript` 开头）。

修复：匹配条件改为同时检查 `_merged_transcript`。

---

### 三、设计一致性问题

#### 标签格式矛盾（第三节 vs 第五节）

**第三节**的方案是嵌入向量按轨分组、声纹匹配的 key 变为 `track-spk_id`（如 `mic-0`、`sys-1`），暗示合并文本中直接使用 `本地-N`/`远程-N` 标签。

**第五节**末尾的"推荐方案"却说："合并文本保留 `Speaker N` 标签 + 轨道标记元数据，输出时再根据轨道标记生成 `本地-N`/`远程-N`"。

但当前 `merge_dual_transcripts()`（dual_track_merge.py:79-82）**已经在替换** `Speaker N` 为 `本地-N`/`远程-N`。如果按第五节建议保留 `Speaker N`，需要修改 `merge_dual_transcripts()` 不做替换，并在元数据中记录每行的轨道来源。

**建议**：统一选择一种方案。考虑到下游处理（`_match_voiceprints`、`_apply_speaker_names`、`apply_speaker_mapping`）全部依赖 `Speaker N` 正则，保留 `Speaker N` 标签 + 轨道元数据的方案改动更大但更一致。如果选择继续使用 `本地-N`/`远程-N`，则需要修改所有下游处理函数以支持新格式。

无论选择哪种，以下函数需要同步修改：
- `_extract_speaker_embeddings()` — 当前用 `int(spk_id)` 做 key
- `_match_voiceprints()` — 遍历 `speaker_embeddings.items()`
- `_apply_voiceprint_match()` — 用 `speaker_id + 1` 构造 `Speaker N` 的 `apply_speaker_mapping`
- `_apply_speaker_names()` — 正则 `Speaker\s+(\d+)` 匹配
- `apply_speaker_mapping()`（utils.py）— 已支持 `-` 格式的 key，但 `Speaker N` 分支不匹配 `本地-N`
- `_save_embeddings_to_disk()` — 保存格式

#### 手动合并 UI（第六节）优先级建议

~~第六节的手动跨轨合并功能建议列为 v2.1 功能~~ **撤回此建议**。经用户指出，手动合并 UI 是 v2 必须的——"保存到音色库"等基础功能依赖发言人管理弹窗在双轨模式下正常工作。已补充行业调研和原型图（`docs/99-mockups/mockup-speaker-dialog.html`）。

---

### 四、实施顺序建议

方案第九节的实施顺序基本合理，建议调整：

1. **Step 1（P0）**：修复 merge 参数传递 — 同时解决 P6（合并组可批量转写）和 P7（多组拆分）
2. **Step 2（P1）**：嵌入向量分组存储 — 需要修改 `_send_embeddings` 签名，传入 track 信息
3. **Step 4（P3）**：先确定标签格式方案（统一第三节和第五节），再改 `merge_dual_transcripts()` 或下游处理
4. **Step 3（P2）**：声纹匹配改为合并后执行 — 依赖 Step 2
5. **Step 5（P3 + P5）**：AI 总结时机调整 — **P5 的路径错误应优先修复**，否则摘要永远不生成
6. **Step 6（P4）**：写入逻辑优化
7. **Step 7（手动合并 UI）**：v2 必须实现，参照原型图 `docs/99-mockups/mockup-speaker-dialog.html`

**P5 应并入 Step 1 或 Step 5 优先修复**，这是一个影响所有合并转写的阻断性 bug。

---

### 五、补充测试要点

9. 合并转写的 AI 摘要是否正确生成（P5）
10. 批量转写多个双轨录音（如 2 组 4 个文件）是否正确拆分为 2 个合并转写（P7）
11. 合并组的"开始转写"按钮是否可用（P6）
12. 摘要生成后 topic 是否正确关联到合并文件（P8）
13. 声纹匹配后，合并转写中的 `本地-N`/`远程-N` 是否被替换为真实姓名
14. 合并转写的纠错（auto_correction）是否正确写入合并文件（已验证正确 ✓）

---

### 六、总结

方案正确识别了 5 个核心问题（P0-P4），根因分析基本准确。但验证中发现 **P5（AI 摘要路径错误）是比 P0 更严重的阻断性 bug**——即使 P0 修复后合并成功触发，AI 摘要仍然不会生成。P6-P8 是方案未覆盖的关联问题。

设计层面最大的待决问题是**标签格式的统一**（第三节 vs 第五节），建议先确定格式再修改代码，避免反复返工。

**行业调研结论**已补充到第六节。核心启示：通道即说话人分组（AssemblyAI 做法）、手动修正是刚需（Otter.ai 做法）、声纹库是长期价值。原型图已制作：`docs/99-mockups/mockup-speaker-dialog.html`。

---

## MiMo Code 审查意见（2026-07-01）

### 一、Qoder P5（AI 摘要路径错误）— 分析有误，非阻断性 bug

**Qoder 的说法**：worker 发送 `("auto_summary", base, output_dir)` 时 `base` 不含 `_merged`，导致主进程构造的路径 `{base}_transcript.md` 与实际文件 `{base}_merged_transcript.md` 不匹配。

**代码验证**：

`transcribe_worker.py:159-160`:
```python
first_name = os.path.basename(file_paths[0])
base = os.path.splitext(first_name)[0] + "_merged"  # base = "062918会议_merged"
```

`transcribe_worker.py:202`:
```python
queue.put(("auto_summary", base, output_dir))  # base 已含 _merged
```

`transcription.py:281`:
```python
base, out_dir = msg[1], msg[2]  # base = "062918会议_merged"
```

`transcription.py:301`:
```python
transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
# = "062918会议_merged_transcript.md" ← 与实际文件名一致
```

**结论**：P5 不是 bug。`base` 在 worker 中已经包含 `_merged` 后缀，传递到主进程后路径构造正确。Qoder 误以为 `base` 是原始文件名。

### 二、Qoder P8（摘要 topic 匹配失败）— 分析有误

**Qoder 的说法**：`startswith(base_name + "_transcript")` 不匹配 `{base}_merged_transcript.md`。

**验证**：
- `base_name` = `"062918会议_merged"`（从 `auto_summary` 消息获取）
- `result_path` 的文件名 = `"062918会议_merged_transcript.md"`
- `"062918会议_merged_transcript.md".startswith("062918会议_merged_transcript")` → **True**

**结论**：P8 不是 bug。`startswith` 匹配正确。

### 三、Qoder P6（合并组被排除在批量转写之外）— 确认是问题

`file_manager.py:277`: `get_pending_files()` 过滤了 `merged_group`：
```python
return [f for f in self._files
        if f.status == FileStatus.PENDING and not f.merged_group]
```

录音完成后 `_handle_stop_complete()` 调用 `create_merged_group()`，合并显示行被设了 `merged_group`。批量"开始转写"按钮无法转写双轨录音。

**但实际影响有限**：用户录音后弹窗走 `_transcribe_single()`，或手动选中文件走 `_merge_transcribe()`。批量转写主要用于多个已存在文件的场景，双轨录音通常通过弹窗触发。

**建议**：v2 中暂不修改 `get_pending_files()`，保持现有行为。如果用户反馈批量转写需要支持双轨，再处理。

### 四、Qoder P7（多组双轨批量合并未处理）— 确认是问题

如果 `_start_transcription()` 收集到 4 个文件（2 组双轨），`is_dual_track_group()` 检查 `len(file_paths) != 2` 返回 None，4 个文件会被当作"多文件合并"。

**但实际场景罕见**：用户很少同时转写 2 组以上的双轨录音。`_start_transcription()` 从 `get_pending_files()` 获取文件，而双轨录音通常走 `_transcribe_single()`。

**建议**：v2 中暂不处理多组双轨拆分。如果需要，在 `_start_transcription()` 中按 `find_dual_track_pair()` 拆分为多个独立任务。

### 五、跨轨匹配阈值 0.65 — 需要查证

Qoder 建议跨轨匹配阈值 0.65，低于音色库匹配的 HIGH_CONFIDENCE（0.50）。

**当前代码中的阈值**：
- `MATCH_THRESHOLD = 0.31`（音色库匹配最低阈值）
- `HIGH_CONFIDENCE = 0.50`（确认匹配阈值）

**Qoder 的说法有问题**：
1. 说"音色库匹配的 HIGH_CONFIDENCE（0.75）"——实际是 0.50，不是 0.75
2. 跨轨阈值 0.65 高于 HIGH_CONFIDENCE（0.50），这意味着跨轨匹配比音色库匹配更严格，这可能不合理

**建议**：跨轨匹配阈值应与音色库匹配阈值保持一致或更低。建议 0.50（与 HIGH_CONFIDENCE 相同），而非 0.65。需要实际测试验证。

### 六、标签格式矛盾（第三节 vs 第五节）— 确认需要统一

第三节说"匹配结果的 key 从 `spk_id`（int）改为 `track-spk_id`（string）"，暗示直接使用 `本地-N`/`远程-N` 标签。

第五节末尾说"合并文本保留 `Speaker N` 标签 + 轨道标记元数据，输出时再生成 `本地-N`/`远程-N`"。

**推荐方案**：统一使用 `本地-N`/`远程-N` 标签（现有 `merge_dual_transcripts()` 已经在做替换）。理由：
1. 下游处理函数（`_match_voiceprints`、`_apply_speaker_names`）需要适配新格式，但改动量可控
2. 保留 `Speaker N` + 元数据的方案需要修改更多地方（存储、序列化、加载）
3. `本地-N`/`远程-N` 对用户更直观

### 七、Mockup 设计审核

原型图 `mockup-speaker-dialog.html` 设计合理：

**优点**：
1. 跨轨合并区域使用智能预填，减少用户操作
2. 姓名冲突标注清晰
3. 手动添加合并规则的入口明确
4. 单轨/双轨场景分离合理

**疑问**：
1. **确认按钮行为**：点击"确认"后立即应用合并规则到转写文本，还是保存时统一应用？如果立即应用，用户取消后如何回滚？
2. **保存按钮**：方案说"一次性保存所有修改"，但确认按钮说"立即应用"。需要明确：确认=预览，保存=持久化。

### 八、实施顺序建议

Qoder 建调的实施顺序基本合理，但 P5/P8 验证为非问题，可从原方案的 Step 1 开始：

1. **Step 1**：修复 merge 参数传递（P0）
2. **Step 2**：嵌入向量分组存储（P1）
3. **Step 3**：统一标签格式（确定用 `本地-N`/`远程-N`）
4. **Step 4**：声纹匹配改为合并后执行（P2）
5. **Step 5**：AI 总结时机调整（P3）
6. **Step 6**：写入逻辑优化（P4）
7. **Step 7**：手动合并 UI（新功能）

### 九、总结

Qoder 的审查发现了 P6（合并组批量转写）和 P7（多组双轨拆分）两个新问题，但 P5（AI 摘要路径）和 P8（topic 匹配）的分析有误，经代码验证确认不是 bug。跨轨匹配阈值需要调整（0.50 而非 0.65）。标签格式需要统一。Mockup 设计合理，需明确确认/保存的交互行为。


---

## [S2] Qoder 修正审查意见（2026-07-01）

> 经 MiMo 复审指出 [S1] 中多项判断有误，重新逐条对照源码验证。以下为修正结论，替代 [S1] 中对应条目的判断。

### 一、[S1] 错误判断纠正

#### P5（AI 摘要路径错误）— 撤回，非 bug

[S1] 称 worker 发送的 `base` 不含 `_merged` 后缀，导致主进程构造路径 `{base}_transcript.md` 与实际文件 `{base}_merged_transcript.md` 不匹配。

**实际代码**（transcribe_worker.py:159-160）：

```python
first_name = os.path.basename(file_paths[0])
base = os.path.splitext(first_name)[0] + "_merged"  # base = "062918会议_merged"
```

`base` 在 worker 中**已经包含 `_merged` 后缀**。传递到主进程后（transcription.py:281, 301）：

```python
base, out_dir = msg[1], msg[2]  # base = "062918会议_merged"
transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
# = "062918会议_merged_transcript.md" <- 与实际文件名一致
```

**结论**：MiMo 正确，P5 不是 bug。路径构造一致，AI 摘要可以正常生成。[S1] 误判根因是未仔细阅读 worker 中 `base` 的赋值逻辑。

#### P8（摘要 topic 匹配失败）— 撤回，非 bug

[S1] 称 `startswith(base_name + "_transcript")` 不匹配 `{base}_merged_transcript.md`。

**实际验证**：
- `base_name` = `"062918会议_merged"`（从 `auto_summary` 消息获取）
- `result_path` 文件名 = `"062918会议_merged_transcript.md"`
- `"062918会议_merged_transcript.md".startswith("062918会议_merged_transcript")` → **True**

**结论**：MiMo 正确，P8 不是 bug。匹配逻辑正确。

#### 跨轨匹配阈值 — 撤回 0.65 的建议

[S1] 称跨轨匹配阈值 0.65 低于"音色库匹配的 HIGH_CONFIDENCE（0.75）"。

**实际代码**（voiceprint.py:23-24）：

```python
MATCH_THRESHOLD = 0.31   # 音色库匹配最低阈值
HIGH_CONFIDENCE = 0.50   # 确认匹配阈值
```

HIGH_CONFIDENCE 实际是 **0.50**，不是 0.75。建议的跨轨阈值 0.65 反而**高于** HIGH_CONFIDENCE，意味着跨轨匹配比音色库确认更严格，这不合理。

**修正建议**：跨轨匹配阈值建议 **0.40-0.50** 区间。理由：
- 跨轨音频质量差异确实存在（麦克风 vs 系统音频），应比单轨匹配略宽松
- 但不应高于 HIGH_CONFIDENCE（0.50），否则用户手动合并的门槛比自动确认还高
- 建议初始值 0.45，可通过实际测试调整
- 在 UI 中以百分比显示置信度，让用户自行判断是否接受

---

### 二、[S1] 正确判断确认

以下 [S1] 中的判断经重新验证，确认正确：

| 问题 | 结论 | 代码位置 |
|------|------|----------|
| P0（合并未触发） | 确认是 bug | home_page.py:866, 914 未传 merge=True |
| P1（嵌入向量覆盖） | 确认是 bug | transcription.py:254-261 直接覆盖 |
| P2（声纹匹配时机） | 确认是 bug | 因 P1 导致只保留最后一轨数据 |
| P3（AI 总结标签无意义） | 确认是问题 | 合并后标签为本地-N/远程-N |
| P4（写入逻辑冗余） | 确认是问题 | 幂等但冗余 |
| P6（合并组排除批量转写） | 确认是问题 | file_manager.py:277 过滤 merged_group |
| P7（多组双轨未拆分） | 确认是问题 | is_dual_track_group 检查 len==2 |

---

### 三、P6 和 P7 的实际影响补充

MiMo 指出 P6 和 P7 实际影响有限，这个判断需要补充分析：

**P6**：`get_pending_files()` 过滤 `merged_group` 后，批量转写确实无法处理双轨录音。但用户录音后弹窗走 `_transcribe_single()`（自动检测双轨），手动选中文件走 `_merge_transcribe()`。批量转写的典型场景是导入多个已有音频文件，此时双轨录音通常已作为独立文件存在，不经过 `create_merged_group()`。因此 P6 的实际触发场景确实有限。

**P7**：`_start_transcription()` 收集所有 pending 文件后一次性传给 `handler.start()`，worker 收到 4+ 个文件时 `is_dual_track_group()` 返回 None，走多文件合并而非双轨合并。但这个路径本身因为 P0（未传 merge=True）就走不到合并分支，P0 修复后才会暴露 P7。MiMo 建议"v2 中暂不处理"可以接受，但应在方案中注明：P0 修复时，`_start_transcription()` 需要按双轨对拆分为多个独立 `handler.start()` 调用，否则多组双轨会被错误合并。

---

### 四、标签格式建议（统一第三节和第五节）

同意 MiMo 的分析：统一使用 `本地-N`/`远程-N` 标签。理由：

1. `merge_dual_transcripts()`（dual_track_merge.py:79-82）已经在做替换，保留 `Speaker N` + 元数据需要回退这个逻辑并增加元数据存储
2. 下游函数需要适配的数量可控：`_match_voiceprints`、`_apply_voiceprint_match`、`_apply_speaker_names`、`apply_speaker_mapping`
3. 对用户更直观

需要修改的函数清单（MiMo 确认）：
- `_extract_speaker_embeddings()`（transcription.py:537-546）：当前用 `int(spk_id)` 做 key，需支持 `本地-N` 格式
- `_match_voiceprints()`（transcription.py:420-485）：遍历 key 格式变化
- `_apply_voiceprint_match()`（transcription.py:487-535）：`speaker_id + 1` 构造 `Speaker N` 的逻辑需改为直接使用 `本地-N`/`远程-N`
- `_apply_speaker_names()`（transcription.py:552-638）：正则 `Speaker\s+(\d+)` 需扩展匹配 `本地-N`/`远程-N`
- `apply_speaker_mapping()`（utils.py）：已支持 `-` 格式 key，但 `Speaker N` 分支不匹配新格式
- `_save_embeddings_to_disk()`（transcription.py:373-414）：保存格式需适配

---

### 五、Mockup 交互行为澄清

回应 MiMo 的疑问：

1. **确认按钮行为**：跨轨合并区的"确认"按钮 = **预览应用**（修改转写文本的显示，但不持久化到磁盘）。最终的"保存"按钮 = **持久化**（写入 `_metadata.json` 并更新转写文件和摘要文件）。用户取消时，如果未点保存，预览修改不保留。
2. **保存按钮**：一次性将所有修改（姓名编辑 + 跨轨合并规则 + 音色库保存）持久化。

---

### 六、修正后的实施顺序

综合 MiMo 的复审意见，修正实施顺序：

1. **Step 1（P0）**：修复 merge 参数传递 — `_transcribe_single()` 检测到双轨时传 `merge=True`
2. **Step 2（P1）**：嵌入向量分组存储 — worker 发送时附带 track 标记
3. **Step 3（标签格式统一）**：确定使用 `本地-N`/`远程-N`，修改下游处理函数
4. **Step 4（P2）**：声纹匹配改为合并后执行 — 依赖 Step 2
5. **Step 5（P3）**：AI 总结时机调整 — 确保声纹匹配和姓名应用在摘要之前
6. **Step 6（P4）**：写入逻辑优化 — merge 模式只写入合并文件
7. **Step 7（手动合并 UI）**：参照原型图 `docs/99-mockups/mockup-speaker-dialog.html`

P5/P8 从实施列表中移除（非 bug）。P6/P7 视实际使用反馈决定是否处理。

---

### 七、总结

[S1] 审查中 P5（AI 摘要路径）和 P8（topic 匹配）的判断有误，根因是未仔细阅读 worker 中 `base` 的赋值（已含 `_merged` 后缀）。跨轨匹配阈值的参照值也有误（HIGH_CONFIDENCE = 0.50 非 0.75）。

方案正确识别的核心问题（P0-P4）经重新验证均成立。P6/P7 是真实问题但影响有限，MiMo 建议"暂不处理"可以接受，但 P0 修复时需同步考虑 P7 的拆分逻辑。标签格式需统一为 `本地-N`/`远程-N`。
