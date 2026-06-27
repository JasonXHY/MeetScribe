# 深度排查：转写后处理阻塞问题

> **用户决策（2026-06-25）**：采用方案A — 用QThread包装AI调用 + 每步状态更新。同时修复 `_apply_speaker_names()` 重复执行Bug。

## 问题概述

转写完成后的所有后处理操作（AI纠错、声纹匹配、姓名应用、AI摘要）都在主线程同步执行，导致UI完全冻结。总阻塞时间可达 **17-250秒**，用户在此期间无法进行任何操作，程序看起来像卡死了。

## 完整后处理调用链（按执行顺序）

### 第1步：AI纠错 — 阻塞 5~120秒

```
_process_message("auto_correction")
  → _generate_correction(raw_text, base, out_dir, transcript_path)
    → ai.generate_correction(raw_text)
      → for chunk in chunks:
          self.ai_client.chat.completions.create()  ← 同步HTTP请求！
```

- **阻塞类型**：同步网络I/O（OpenAI兼容API）
- **超时设置**：120秒
- **分块处理**：每4000字符一块，每块独立一次API调用
- **预估耗时**：每块5-30秒

### 第2步：声纹匹配 — 阻塞 0.1~0.5秒

```
_process_message("auto_summary")
  → _match_voiceprints()
    → VoiceprintLibrary()._load_from_file()     ← 磁盘读
    → for each speaker: library.match(embedding) ← numpy余弦相似度
    → for each match:
        → file_manager.update_speaker_names()    ← 磁盘写
        → apply_speaker_mapping(result_path)     ← 磁盘读+写
        → apply_speaker_mapping(summary_path)    ← 磁盘读+写
        → library.add_speaker()                  ← 磁盘写
```

- **阻塞类型**：磁盘I/O + CPU（numpy向量计算）
- **预估耗时**：50-500ms

### 第3步：姓名应用 — 阻塞 0.1~10秒

```
_apply_speaker_names()
  → for item in files:
    → open(result_path).read()                   ← 磁盘读
    → namer.extract_names()
      → extract_names_regex()                    ← CPU（很快）
      → [正则未覆盖时] ai_service.extract_speaker_names()
        → ollama_client.chat.completions.create() ← 同步网络I/O！
    → apply_speaker_mapping()                    ← 磁盘读+写
```

- **阻塞类型**：磁盘I/O + 可能的同步网络I/O（Ollama LLM兜底）
- **Ollama超时**：10秒
- **预估耗时**：正则部分<100ms；触发LLM兜底则+2-10秒

### 第4步：AI摘要 — 阻塞 10~120秒

```
_generate_summary(transcript, base, out_dir)
  → open(transcript_path).read()                 ← 磁盘读
  → ai.generate_summary(transcript, voiceprint_matches)
    → self.ai_client.chat.completions.create()   ← 同步HTTP请求！120s超时
  → open(summary_path, "w").write(summary)       ← 磁盘写
  → file_manager.update_topic()                  ← 磁盘写
  → apply_speaker_mapping() × 2                  ← 磁盘读+写
  → file_manager.update_speaker_names()          ← 磁盘写
```

- **阻塞类型**：同步网络I/O + 多次磁盘I/O
- **预估耗时**：网络10-120秒 + 磁盘100-500ms

### 第5步：`_on_done()` 中的重复处理

```
_on_done()
  → _match_voiceprints()     ← 有防重入标记，跳过 ✓
  → _apply_speaker_names()   ← ⚠️ 没有防重入保护，可能重复执行！
  → _process.terminate() + join(2s)
  → transcription_done.emit() → UI终于更新
```

**额外发现的Bug**：`_apply_speaker_names()` 在 `auto_summary` 消息中已执行一次，又在 `_on_done()` 中再次执行，且没有防重入保护。

## 完整时间线

```
子进程                          主线程 (Qt Event Loop)
  |                                    |
  |--- ("auto_correction") ----------->|
  |                          🔴 BLOCK: AI纠错 (5-120s)
  |                                    |
  |--- ("auto_summary") ------------->|
  |                          🔴 BLOCK: 声纹匹配 (0.1-0.5s)
  |                          🔴 BLOCK: 姓名应用 (0.1-10s)
  |                          🔴 BLOCK: AI摘要 (10-120s)
  |                                    |
  |--- ("done") --------------------->|
  |                          🔴 BLOCK: _apply_speaker_names() 可能重复 (0.1-10s)
  |                          🔴 BLOCK: _process.terminate() + join(2s)
  |                          ✅ transcription_done.emit() → UI更新
```

**总阻塞时间：15.2 ~ 262.5秒**

## 串行/并行依赖关系

```
auto_correction ──(必须同步)──> auto_summary
                                    │
                              ┌─────┴─────┐
                              │ 声纹匹配   │ ← 必须先于姓名应用和摘要
                              └─────┬─────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ↓                               ↓
            姓名应用                          AI摘要生成
            (可与摘要并行)                   (可与姓名应用并行)
```

**必须保持的串行关系**：
1. AI纠错 → AI摘要（摘要需要纠错后的文本）
2. 声纹匹配 → 姓名应用（confirmed集合决定优先级）
3. 声纹匹配 → AI摘要（摘要prompt需要声纹信息）

**可以并行的关系**：
- 姓名应用 和 AI摘要 之间无严格依赖，可以在声纹匹配完成后并行执行

## 修复方案

### 方案A：QThread包装AI调用（推荐）

**核心思路**：把两个最耗时的AI操作（纠错和摘要）移入QThread，通过信号回调结果。

```python
# 示例：将AI纠错移入QThread
class AICorrectionWorker(QThread):
    finished = Signal(str)  # 返回纠错后的文本
    error = Signal(str)
    
    def __init__(self, ai_service, raw_text):
        super().__init__()
        self.ai_service = ai_service
        self.raw_text = raw_text
    
    def run(self):
        try:
            result = self.ai_service.generate_correction(self.raw_text)
            self.finished.emit(result or "")
        except Exception as e:
            self.error.emit(str(e))
```

**执行流程变为**：
```
转写完成 → 启动AICorrectionWorker线程 → UI保持响应
  → Worker完成 → 信号回调 → 保存纠错结果 → 启动声纹+姓名+摘要Worker
    → Worker完成 → 信号回调 → UI更新 → _on_done()
```

**优点**：
- UI完全不卡顿，用户可正常操作
- 改动集中在transcription.py，不涉及其他模块
- 符合Qt的线程模型

**缺点**：
- 需要处理线程生命周期（避免程序退出时线程还在跑）
- 需要增加"后处理中"状态显示

**预估改动量**：~80行新增代码，~20行修改

### 方案B：分步执行 + 状态更新

在方案A基础上，每个步骤完成后立即更新UI状态：

```
转写完成 → 显示"正在进行AI纠错..." → 纠错完成 → 显示"正在声纹匹配..."
→ 匹配完成 → 显示"正在生成摘要..." → 摘要完成 → 显示"处理完成"
```

**优点**：用户能看到每个步骤的进展，不会觉得程序卡死
**缺点**：比方案A多一些UI状态管理的代码

### 方案C：最小改动 — 仅防卡死

不改线程模型，只在每个长操作前调用 `QApplication.processEvents()` 让UI有机会刷新：

```python
def _process_message(self, msg):
    ...
    elif msg_type == "auto_correction":
        QApplication.processEvents()  # 让UI有机会刷新
        self._generate_correction(...)
        QApplication.processEvents()
```

**优点**：改动极小（加几行代码）
**缺点**：UI只是"不那么卡"而不是"不卡"，用户体验改善有限

## 额外修复项

### `_apply_speaker_names()` 重复执行Bug

在 `_on_done()` 中增加防重入标记：

```python
def _on_done(self):
    ...
    if not self._names_applied:
        self._apply_speaker_names()
        self._names_applied = True
    ...
```

## 建议

**实施方案A + 方案B**：用QThread包装AI调用，同时每步完成后更新UI状态。
同时修复 `_apply_speaker_names()` 的重复执行Bug。

这样既解决了卡死问题，又让用户能看到处理进展。总改动量约100行。
