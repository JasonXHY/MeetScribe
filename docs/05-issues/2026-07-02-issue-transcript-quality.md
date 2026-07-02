# 转写质量问题排查报告

> 日期：2026-07-02
> 测试文件：`070117会议.wav` + `070117会议_系统音频.wav`（双轨，时长 341 秒）

---

## 问题一：预览显示中文本丢失

### 现象
用户点击预览按钮后，弹窗中只显示时间戳和说话人标签，实际文本内容不可见。

### 源文件路径
- 合并转写文件：`C:\侧耳倾听\transcripts\070117会议_merged_transcript.md`
- 原始备份：`C:\侧耳倾听\transcripts\070117会议_merged_transcript_raw.md`

### 实际文件内容（前 5 行）
```markdown
# Meeting Transcription

- **File**: 070117会议.wav
- **Duration**: 05:35
- **Transcribed**: 102.4s

[00:01] **本地-1**: 证号是四九幺
[00:02] **远程-1**: 尽量简化大家的工作嘛。嗯就等于我把各模块的按照这个场次的测试结果...
[00:14] **本地-3**: 这个流程，但是没有理看这个问会是按说这个流程
[00:26] **本地-2**: 要有个这个
```

文件内容完整，包含文件头、时间戳、说话人标签和实际文本。

### 根因分析

**PreviewDialog 渲染逻辑**（`dialogs.py:193-199`）：

```python
def _show_transcript(self):
    try:
        import markdown
        html = markdown.markdown(self._transcript_text)
        self._text_box.setHtml(html)
    except ImportError:
        self._text_box.setPlainText(self._transcript_text)
```

使用 `markdown` 库将 Markdown 转 HTML 后用 QTextBrowser 渲染。可能的问题：

1. **markdown 库未安装**：fallback 到 `setPlainText()`，纯文本显示应该正常
2. **QTextBrowser 渲染问题**：HTML 中的 `**本地-1**` 被转为 `<strong>本地-1</strong>`，如果 QTextBrowser 不支持某些 HTML 标签，可能截断内容
3. **字体/编码问题**：`Consolas` 字体（`dialogs.py:173`）可能不支持中文标点

### 修复方向
- 检查 `markdown` 库是否已安装
- 如果 fallback 到纯文本，确认显示是否正常
- QTextBrowser 的 `setFont(QFont("Consolas", 13))` 可能需要改为支持中文的字体

---

## 问题二：说话人识别过多（6 位）

### 现象
5 分 35 秒的会议录音识别出 10 个说话人标签（本地-1~6 + 远程-1~4），远超实际参会人数。

### 嵌入向量数据
`070117会议_merged_embeddings.json` 包含 10 个说话人的 192 维嵌入向量：

| 说话人 | 嵌入维度 | 来源轨道 |
|--------|----------|----------|
| mic-0 | 192 | 本地 |
| mic-1 | 192 | 本地 |
| mic-2 | 192 | 本地 |
| mic-3 | 192 | 本地 |
| mic-4 | 192 | 本地 |
| mic-5 | 192 | 本地 |
| sys-0 | 192 | 远程 |
| sys-1 | 192 | 远程 |
| sys-2 | 192 | 远程 |
| sys-3 | 192 | 远程 |

### 原始转写对比
`070117会议_merged_transcript_raw.md` 中，声纹匹配已成功识别部分发言人：

| 说话人 | 匹配结果 | 来源 |
|--------|----------|------|
| mic-0 | **刘家诚**（已确认） | 音色库匹配 |
| mic-2 | **宋琳琳**（已确认） | 音色库匹配 |
| mic-3 | 本地-3（未匹配） | — |
| mic-4 | **万斌**（已确认） | 音色库匹配 |
| sys-0 | **乔栋栋**（已确认） | 音色库匹配 |
| sys-2 | 远程-2（未匹配） | — |
| sys-3 | 远程-3（未匹配） | — |
| sys-4 | 远程-4（未匹配） | — |
| mic-5 | 本地-5（未匹配） | — |
| mic-6 | 本地-6（未匹配） | — |

**问题**：mic-5 和 mic-6 可能是同一人的不同段发言被过度分割。

### 根因
FunASR CAM++ 模型的说话人分离（diarization）过度分割。这是模型行为，不是应用参数问题。

### 当前参数与调整建议

| 参数 | 当前值 | 建议调整 | 用途 | 安全性 |
|------|--------|---------|------|--------|
| `MATCH_THRESHOLD` | 0.31 | **0.35** | 音色库匹配最低阈值 | 同一人相似度 ~0.69，0.35 仍远低于 |
| `HIGH_CONFIDENCE` | 0.50 | **0.55** | 自动确认阈值 | 减少错误自动命名 |
| 跨轨匹配阈值 | 0.31 | **0.55** | 跨轨同一人检测 | 跨轨质量差异大，需更高阈值 |

**代码位置**：
- `voiceprint.py:23` — MATCH_THRESHOLD
- `voiceprint.py:24` — HIGH_CONFIDENCE
- `transcription.py:642` — 跨轨匹配阈值

---

## 问题三：测试场景未覆盖

### 当前测试状态
418 个单元测试全部通过，但缺少端到端业务场景测试。

### 需补充的测试场景

| 优先级 | 场景 | 测试步骤 | 预期结果 | 验证文件 |
|--------|------|---------|---------|---------|
| P0 | 双轨在线会议转写 | 录音→转写→合并→AI总结 | 合并文件有文件头、本地/远程标签、AI总结生成 | `*_merged_transcript.md` + `*_summary.md` |
| P0 | 单轨现场会议转写 | 录音→转写 | 正常转写，Speaker N 标签 | `*_transcript.md` |
| P0 | 转写+录音并行 | 转写中开始录音 | 录音正常，转写不中断 | 两个文件都完成 |
| P1 | 重试转写 | 失败后点重试 | 完整重新执行转写流程 | 文件状态恢复 |
| P1 | 发言人管理 | 打开弹窗、编辑姓名、保存 | 姓名写入转写文件和总结 | 文件内容更新 |
| P1 | 预览显示 | 点击预览按钮 | 转写内容和AI总结正确渲染 | 弹窗内容可读 |
| P1 | 设置持久化 | 修改设置→保存→重启 | 值保持不变 | config/settings.json |
| P2 | VB-Cable 设置 | 勾选→保存→重启 | 开关保持勾选状态 | config/settings.json |

---

## 修复优先级

| 问题 | 优先级 | 改动量 | 备注 |
|------|--------|--------|------|
| 说话人阈值调整 | P1 | 3 行 | 改 3 个数字 |
| 预览显示问题 | P1 | 需排查 | 可能是 markdown 渲染或字体问题 |
| 测试场景补充 | P2 | 新增测试文件 | P0 场景需用户配合手动测试 |

---

## [Qoder 审查意见] 2026-07-02

> 逐条对照源码验证文档中的 claim，评估修复方向可行性。

---

### 一、问题一（预览显示中文本丢失）— 根因判断有误

文档列了三个"可能的问题"，但经过代码验证，根因是确定的：

#### 1.1 根因：Consolas 字体不支持中文

`dialogs.py:173`：

```python
self._text_box.setFont(QFont("Consolas", 13))
```

**Consolas 是纯拉丁字体，不包含任何 CJK（中日韩）字形。** 当 QTextBrowser 使用 Consolas 渲染 HTML 时，中文字符无法在该字体中找到对应的 glyph，需要依赖系统的字体回退（font fallback）机制。在 `setHtml()` 模式下，Qt 的字体回退行为不如 `setPlainText()` 可靠，尤其在 Windows 上，markdown 转换后的 HTML 结构（`<p>`、`<strong>` 等标签嵌套）可能导致回退失败，中文字符渲染为空白或方块。

**文档的其他猜测排除**：

1. "markdown 库未安装"：如果未安装，fallback 到 `setPlainText()` 应该正常显示。但如果 markdown 已安装，走 `setHtml()` 路径就会触发 Consolas 字体问题。
2. "QTextBrowser 不支持某些 HTML 标签"：QTextBrowser 支持基础 HTML 子集（`<p>`、`<strong>`、`<em>` 等），不会截断内容。
3. "字体/编码问题"：方向对了，但不是"不支持中文标点"，而是 **整个中文字符都无法渲染**。

#### 1.2 修复方案

将 Consolas 改为项目统一的 `FONT_FAMILY`（已在 `styles.py` 中定义，支持中文），2 行代码：

```python
# dialogs.py:173
# 原代码：
self._text_box.setFont(QFont("Consolas", 13))
# 改为：
self._text_box.setFont(QFont(FONT_FAMILY, 13))
```

需要确保 `dialogs.py` 顶部已导入 `FONT_FAMILY`。如果未导入，添加：

```python
from gui.styles import FONT_FAMILY
```

---

### 二、问题二（说话人识别过多）— 概念混淆，方案有误

文档将"说话人过多"归因于阈值参数，并建议调整 `MATCH_THRESHOLD`、`HIGH_CONFIDENCE` 和跨轨匹配阈值。**这是对两个不同概念的混淆。**

#### 2.1 概念澄清：说话人分离 vs 声纹匹配

| 概念 | 控制什么 | 在哪里执行 | 可调参数 |
|------|---------|-----------|---------|
| 说话人分离（Diarization） | 将音频切分为多少个说话人 | FunASR `model.generate()` 内部 | 当前代码未暴露任何参数 |
| 声纹匹配（Matching） | 将检测到的说话人与音色库中的已知人匹配 | `voiceprint.py` | `MATCH_THRESHOLD`、`HIGH_CONFIDENCE` |

**文档描述的"6 个本地说话人"是 FunASR 的说话人分离结果，不是声纹匹配的结果。** 调整 `MATCH_THRESHOLD` 不会改变 FunASR 检测到多少个说话人——它只影响"检测到的说话人能否匹配到音色库中的已知人"。

换句话说：即使把 `MATCH_THRESHOLD` 调到 0.99，FunASR 仍然会检测出 6 个本地说话人，只是可能一个都匹配不上音色库。

#### 2.2 说话人过多的真正原因

FunASR 的说话人分离在模型加载时配置 `spk_model="cam++"`（`transcriber.py:530`），推理时 `model.generate()` 只传了 `input`、`batch_size_s`、`language` 三个参数（`transcriber.py:700-705`），**没有任何聚类阈值、最小簇大小等参数**。说话人数量完全由 FunASR 内部默认的聚类算法决定。

如果要将说话人分离的聚类阈值暴露为可调参数，需要修改 `model.generate()` 调用，传入 FunASR 支持的聚类参数（如 `threshold`）。但这属于功能增强，不是简单的"改数字"。

#### 2.3 文档建议的阈值调整评估

**`MATCH_THRESHOLD` 从 0.31 调到 0.35 — 不建议**

- 0.31 是 ModelScope 官方推荐值，单轨匹配效果用户已确认"还可以"
- 调到 0.35 会拒绝相似度在 0.31-0.35 之间的匹配，降低匹配率
- 对"说话人过多"问题没有任何效果（这是分离问题，不是匹配问题）

**`HIGH_CONFIDENCE` 从 0.50 调到 0.55 — 不建议**

- 这只影响"已确认"vs"建议"的分级显示，不影响匹配行为本身
- 对"说话人过多"问题没有任何效果

**跨轨匹配阈值从 0.31 调到 0.55 — 严重回归**

- 这会把阈值设回 `HIGH_CONFIDENCE` 的水平，**直接重现"跨轨合并 UI 不显示"的 bug**（已在 `2026-07-01-issue-dual-track-v2-test.md` 中修复）
- 我们在 issue 文档中专门论证了跨轨匹配应该用 0.31（与单轨一致），因为 mic 和 sys 轨的音频质量差异导致相似度天然偏低
- 文档没有解释为什么现在又要调回 0.55，也没有提供跨轨相似度的实测数据支持

#### 2.4 建议的处理方式

"说话人识别过多"是 FunASR 模型行为，当前代码没有暴露聚类参数。有两个方向：

**方向 A（短期，不改代码）**：接受 FunASR 的分离结果，通过 SpeakerDialog 让用户手动合并多余的说话人。这是当前的设计思路，功能已具备。

**方向 B（中期，功能增强）**：在 `model.generate()` 调用中传入聚类阈值参数，让用户可以调节说话人分离的灵敏度。需要调研 FunASR CAM++ pipeline 支持的参数，属于新功能开发。

**不建议按文档方案调整 MATCH_THRESHOLD / HIGH_CONFIDENCE / 跨轨阈值。** 这些参数控制的是声纹匹配，不是说话人分离，调了也解决不了问题，还会引入回归。

---

### 三、问题三（测试场景）— 无问题

测试场景列表合理，覆盖了关键业务路径。P0 场景确实需要手动端到端测试，自动化价值有限。无修改意见。

---

### 四、文档数据一致性问题

文档中存在几处数据不一致，需修正：

1. **标题与内容不符**：标题写"说话人识别过多（6 位）"，但表格列出 10 个说话人（mic-0~5 + sys-0~3 = 6 本地 + 4 远程 = 10）。
2. **说话人编号混乱**：表格中 `sys-0` 对应"远程-1"，但原始转写对照表中出现 `sys-4`（对应"远程-4"），而嵌入向量表中只有 `sys-0~3`（4 个远程说话人）。如果 `sys-4` 存在，嵌入向量表应该有 5 个 sys 条目。
3. **预览内容与表格矛盾**：预览文件内容显示 `本地-1, 远程-1, 本地-3, 本地-2`，但表格中 mic-0~5 对应本地-1~6，编号体系需要统一说明。

建议核实实际数据后统一修正。

---

### 五、审查总结

| 问题 | 文档判断 | 审查结论 | 说明 |
|------|---------|---------|------|
| 预览中文不可见 | "可能是 markdown/编码问题" | **Consolas 字体不支持中文** | `dialogs.py:173` 使用纯拉丁字体，改 FONT_FAMILY 即可 |
| 说话人过多 | "调 MATCH_THRESHOLD / HIGH_CONFIDENCE" | **概念混淆** | 说话人数量由 FunASR 分离决定，不受匹配阈值影响 |
| 跨轨阈值调 0.55 | "建议调整" | **严重回归** | 会重现"跨轨 UI 不显示"的 bug |
| 测试场景 | 列表合理 | 无问题 | — |

**建议执行顺序**：

```
1. 预览字体修复    ← 1-2 行，确定性问题
2. 修正文档数据    ← 核实实际说话人数据，统一编号
3. 说话人过多      ← 短期用 SpeakerDialog 手动合并；中期调研 FunASR 聚类参数
```

不建议执行文档中提出的阈值调整方案。

---

### 六、声纹匹配调参建议 — 补充说明

> 用户反馈：音色库中有某人，但此人并未参加会议，系统却将其姓名写入转写结果。

#### 6.1 当前匹配流程与参数

完整链路（`voiceprint.py` + `transcription.py`）：

```
1. FunASR 检测出 N 个说话人，每个说话人有 192 维嵌入向量
2. 对每个说话人，调用 library.match(embedding)：
   - 遍历音色库所有成员，计算余弦相似度
   - 取最高分 best_score
   - 若 best_score >= MATCH_THRESHOLD (0.31) → 返回 (name, score)
   - 若 best_score < 0.31 → 返回 (None, 0)，不匹配
3. 匹配成功后判定置信度：
   - score >= HIGH_CONFIDENCE (0.50) → confidence = "confirmed"
   - score < 0.50                  → confidence = "suggested"
4. 无论 confirmed 还是 suggested，都写入转写文件（apply_speaker_mapping）
5. 仅 confirmed 级别触发自动追加声纹样本到音色库
```

**关键参数**：

| 参数 | 值 | 作用 | 位置 |
|------|-----|------|------|
| `MATCH_THRESHOLD` | 0.31 | 匹配门槛：低于此值不认为是同一人 | `voiceprint.py:23` |
| `HIGH_CONFIDENCE` | 0.50 | 分级门槛：区分"已确认"和"可能" | `voiceprint.py:24` |

#### 6.2 问题根因

**`MATCH_THRESHOLD = 0.31` 太低。** CAM++ 官方数据：同一人不同录音相似度约 0.69，不同人约 0.00。但实际会议场景中，由于录音设备差异（麦克风 vs 系统音频）、环境噪声、说话状态变化等因素，不同人的相似度可能达到 0.25-0.40。0.31 的门槛会将一部分"不在场但声纹相似"的人错误匹配。

**当前代码的 confirmed/suggested 分级只影响显示和自动追加样本，两者都会写入姓名。** 用户看到的转写文件中，suggested 匹配的人和 confirmed 匹配的人名字格式完全一样，无法区分。

#### 6.3 调参建议

**方案：提高匹配门槛 + suggested 不自动写入**

```python
# voiceprint.py — 参数调整
MATCH_THRESHOLD = 0.40    # 从 0.31 提高到 0.40，减少误匹配
HIGH_CONFIDENCE = 0.50    # 保持不变，confirmed 分级仍然有效
```

**理由**：
- 0.40 仍然远低于同一人的典型相似度（0.60-0.75），不会漏掉真正的匹配
- 0.40 可以有效过滤掉"声纹相似但不在场"的误匹配（这类通常在 0.25-0.38 之间）
- 如果实际测试中 0.40 仍然有误匹配，可以进一步提高到 0.45

**同时修改写入逻辑**：suggested 级别不自动写入姓名，只在 SpeakerDialog 中显示为建议：

```python
# transcription.py _apply_voiceprint_match() 中
# 原代码（约第 541 行）：无论 confirmed 还是 suggested 都写入
# 改为：仅 confirmed 自动写入，suggested 只记录不写入

if confidence == "confirmed":
    # 写入转写文件和摘要
    apply_speaker_mapping(item.result_path, {mapping_key: name})
    # ... 其他写入逻辑
    self.log_message.emit(f"音色库匹配: {display_label} -> {name} (已确认)")
else:
    # suggested 只记录到 _voiceprint_match_results，不写入文件
    self.log_message.emit(f"音色库疑似匹配: {display_label} -> {name} (待确认)")
```

这样用户在 SpeakerDialog 中可以看到 suggested 匹配，手动确认后才会写入。

#### 6.4 跨轨匹配阈值

当前跨轨匹配阈值（`transcription.py:645`）为 `0.31`，与 `MATCH_THRESHOLD` 保持一致。如果提高 `MATCH_THRESHOLD` 到 0.40，跨轨匹配阈值也应同步调整到 0.40。

**注意**：跨轨匹配（mic vs sys）的相似度通常低于同轨匹配，因为系统音频经过网络传输会有质量损失。如果 0.40 导致跨轨匹配率过低，可以单独设为 0.35。

---

### 七、说话人人数汇总逻辑 — 补充说明

#### 7.1 当前人数统计位置

| 位置 | 统计方式 | 说明 |
|------|---------|------|
| `transcriber.py:1449` | `len({s["spk"] for s in sentences})` | HTML 转写文件头部 "N 位说话人" |
| `dialogs.py:455` | `len(self._speakers)` | SpeakerDialog 副标题 "识别出 N 位说话人" |
| `ai_service.py:232-242` | 遍历 `voiceprint_matches` | 注入 AI 摘要 prompt 的"已识别说话人"列表 |

#### 7.2 双轨场景下的人数统计问题

在双轨合并场景中，跨轨匹配会将本地-0 和远程-0 识别为同一人。但当前的人数统计**没有考虑跨轨合并**：

- `transcriber.py:1449` 统计的是句子级别的 `spk` 字段（整数 ID），本地和远程说话人有不同的 ID，即使跨轨匹配为同一人也会被计为 2 个
- `dialogs.py:455` 的 `self._speakers` 来自 `parse_speakers_from_result()`，解析的是转写文件中的标签（本地-N / 远程-N），跨轨匹配后标签可能已被替换为姓名，但统计仍按原始标签数计算

**结果**：如果本地有 3 人、远程有 2 人，其中 1 人是跨轨匹配的同一人，实际参会 4 人，但系统显示"5 位说话人"。

#### 7.3 修复方向

在 SpeakerDialog 和转写头部的人数统计中，扣除跨轨匹配的对数：

```python
# dialogs.py:455 — 当前代码
subtitle = QLabel(f"文件: {self._file_name}  |  识别出 {len(self._speakers)} 位说话人")

# 改为：如果有跨轨匹配，显示合并后的人数
actual_count = len(self._speakers)
if self._merge_rules:
    # 每个 merge rule 表示两个说话人被合并为同一人
    merged_count = sum(len(v) for v in self._merge_rules.values())
    actual_count = len(self._speakers) - merged_count
subtitle = QLabel(f"文件: {self._file_name}  |  识别出 {actual_count} 位说话人")
```

对于转写文件头部的人数统计，需要在跨轨匹配完成后更新 `speaker_count`，或在 `_fmt_html()` 中读取跨轨匹配结果进行扣减。

---

## [MiMo 审查意见] 2026-07-02

### 一、Qoder 审查验证

**Q1：预览字体问题 — 确认正确**

`dialogs.py:173` 使用 `QFont("Consolas", 13)`，`styles.py:39` 定义 `FONT_FAMILY = "Microsoft YaHei, Segoe UI, sans-serif"`。Consolas 不含 CJK 字形，改用 FONT_FAMILY 可解决。代码验证通过。

**Q2：说话人分离 vs 声纹匹配概念混淆 — 确认正确**

我之前将"说话人过多"归因于阈值参数，但 FunASR 的说话人分离（diarization）和声纹匹配（matching）是两个独立环节。调整 MATCH_THRESHOLD 只影响匹配行为，不影响分离出多少个说话人。Qoder 的概念澄清完全正确。

**Q3：跨轨阈值 0.55 会回归 — 确认正确**

之前修复跨轨 UI 不显示时，专门将阈值从 0.50 降到 0.31。调回 0.55 会重现该 bug。

**Q4：文档数据不一致 — 确认正确**

标题写"6 位"但表格列了 10 个，编号体系混乱。需要核实实际数据统一修正。

**Q5：suggested 不自动写入 — 确认合理**

当前代码中 confirmed 和 suggested 都会写入转写文件。Qoder 建议 suggested 只显示建议不自动写入，让用户手动确认。这是更安全的设计。

### 二、修正后的方案

| 问题 | 方案 | 改动量 |
|------|------|--------|
| 预览字体 | Consolas → FONT_FAMILY | 2 行 |
| 说话人过多 | 短期用 SpeakerDialog 手动合并；中期调研 FunASR 聚类参数 | 0 行（短期）/ 新功能（中期） |
| 声纹误匹配 | MATCH_THRESHOLD 0.31→0.40，suggested 不自动写入 | ~10 行 |
| 文档数据 | 核实说话人数据统一修正 | 文档修改 |

**不执行原方案的阈值调整**（MATCH_THRESHOLD 0.35、HIGH_CONFIDENCE 0.55、跨轨 0.55）。
