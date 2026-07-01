# 双轨合并 v2 本地测试问题记录

> 日期：2026-07-01
> 测试文件：070117会议（双轨：麦克风 + 系统音频，时长 341 秒）
> 测试方式：`python src/main.py` 启动开发版

---

## 问题 M1：转写显示格式错误

### 现象
合并后的转写内容格式与预期不符。

### 根因分析

**原始单文件转写格式**（`_fmt_llm_md` 输出）：
```
# Meeting Transcription

- **File**: 070117会议.wav
- **Duration**: 05:41
- **Transcribed**: 12.3s

---

[00:01] **Speaker 1**: 证号是491。
[00:02] **Speaker 2**: 尽量简化大家的工作嘛。
```

**合并后格式**（`merge_dual_transcripts` 输出）：
```
[00:01] **本地-1**: 证号是491。
[00:02] **远程-1**: 尽量简化大家的工作嘛。
```

**差异**：
1. 合并后缺少文件头信息（`# Meeting Transcription`、文件名、时长、转写耗时）
2. 合并后缺少 `---` 分隔线
3. 发言人标签从 `Speaker N` 变为 `本地-N`/`远程-N`（这是预期行为）

**技术细节**：
`merge_dual_transcripts()` 中 `parse_transcript_lines()` 只解析带时间戳的行（`[MM:SS]` 或 `[HH:MM:SS]`），文件头的 Markdown 行（`# Meeting Transcription`、`- **File**:` 等）没有时间戳，被过滤掉了。合并后的文本只有时间戳行。

### 修复方向
合并时保留原始文件头信息（至少保留文件名、时长），或在合并后重新生成文件头。

---

## 问题 M2：批量替换功能无意义

### 现象
SpeakerDialog 顶部的"批量替换"区域（选择发言人 → 输入新名称 → 点替换）操作繁琐，不如直接在下方发言人列表的输入框中编辑。

### 分析
- 用户可直接在每个发言人行的输入框中编辑姓名
- 保存时 `on_save` 回调会将所有修改写入转写文件和摘要
- 批量替换功能与直接编辑功能重复，且多一步操作

### 建议
删除 SpeakerDialog 中的批量替换区域（`batch_bar`）。

---

## 问题 M3：AI 总结未生成

### 现象
转写完成后没有生成 AI 摘要文件（`*_summary.md`），预览弹窗中没有"AI 摘要"标签。

### 日志关键行
```
[2026-07-01 18:04:17] ERROR   MeetScribe - AI summary failed: can only concatenate str (not "int") to str
```

### 根因

**出错位置**：`ai_service.py:236`

```python
known_lines.append(f"- Speaker {spk_id + 1} = {info['name']}（音色库匹配，置信度: {info['confidence']}）")
```

**原因**：`voiceprint_matches` 的 key 格式已从 `int`（如 `0`, `1`）变为 `str`（如 `"mic-0"`, `"sys-0"`）。`spk_id + 1` 在 `spk_id = "mic-0"` 时触发 `TypeError: can only concatenate str (not "int") to str`。

**调用链**：
1. `transcription.py:979` — `AISummaryWorker.__init__(ai, transcript, self._voiceprint_match_results)`
2. `transcription.py:1248` — `self._ai_service.generate_summary(transcript, voiceprint_matches=self._voiceprint_matches)`
3. `ai_service.py:236` — `f"- Speaker {spk_id + 1} = ..."` → **TypeError**

**`_voiceprint_match_results` 的 key 格式**（Task 4 修改后）：
```python
# _match_voiceprints() 中：
self._voiceprint_match_results["mic-0"] = {"name": "张三", "confidence": "confirmed"}
self._voiceprint_match_results["sys-0"] = {"name": "李四", "confidence": "suggested"}
```

`ai_service.py` 假设 key 是 int，实际是 `"mic-N"`/`"sys-N"` 字符串。

### 修复方案

修改 `ai_service.py:233-237`，支持 `int` 和 `"track-N"` 两种 key 格式：

```python
if voiceprint_matches:
    known_lines = []
    for spk_id, info in voiceprint_matches.items():
        # 兼容 int key（传统）和 "mic-N"/"sys-N" key（双轨）
        if isinstance(spk_id, str) and '-' in spk_id:
            label = spk_id.replace("mic-", "本地-").replace("sys-", "远程-")
        else:
            label = f"Speaker {int(spk_id) + 1}"
        known_lines.append(f"- {label} = {info['name']}（音色库匹配，置信度: {info['confidence']}）")
    known_speakers_section = "\n\n【已识别的说话人（音色库匹配结果，请在参会人员中使用这些姓名）】\n" + "\n".join(known_lines)
```

---

## 修复优先级

| 问题 | 优先级 | 修复难度 | 说明 |
|------|--------|----------|------|
| M3（AI 总结） | P0 | 低（3 行） | 阻断性 bug，AI 摘要完全不生成 |
| M1（显示格式） | P1 | 中（~20 行） | 合并后缺少文件头，用户体验差 |
| M2（批量替换） | P2 | 低（删除代码） | 功能冗余，用户明确要求删除 |

## 工作流程

先本地开发版测试修复 → 通过后 → 更新安装版本
