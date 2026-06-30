# 第7次打包后测试问题

> 日期：2026-06-29
> 来源：安装版测试
> 状态：待修复

## 问题 A：转写失败 — 子进程残留+卡死（P0）

### 现象
第一次子进程卡死后未 terminate，第二次子进程因资源占用也卡死。超时后未 terminate 进程、未更新文件状态、未重置 UI。

### 日志对比

**失败 (062914会议.wav, 199秒)**：
```
14:49:02 [SUBPROCESS] Subprocess started  ← 第一次，卡死
14:55:49 [SUBPROCESS] Subprocess started  ← 第二次，用户再次点击
14:56:06 [SUBPROCESS] Loading models...
14:56:11 [SUBPROCESS] Models loaded successfully
14:58:11 转写超时：子进程 120 秒无响应
```

**成功 (062915会议.wav, 166秒)**：
```
15:18:37 [SUBPROCESS] Subprocess started
15:18:53 [SUBPROCESS] Loading models...
15:19:21 [SUBPROCESS] Models loaded successfully
15:19:59 [SUBPROCESS] [SPK-EMB-PER] Found 4 speakers
15:20:06 [SUBPROCESS] Transcription completed in 44.3s
15:20:32 [SUBPROCESS] Punctuation applied to 60 sentences
15:21:19 LLM 纠错完成
```

### 根因
1. 第一次子进程卡死后从未被 terminate，占用资源
2. 第二次子进程因资源占用也卡死在 generate 阶段
3. 超时触发后只标记状态，未 terminate 进程、未更新文件状态、未重置 UI

### 修复方向
1. 超时检测加 `self._process.terminate()`
2. 超时后更新文件状态为 failed
3. 超时后调用 `update_state()` 重置 UI
4. 转写前检查是否有残留子进程并清理

### 涉及文件
- `src/transcriber.py` — `_ensure_wav()`, `generate()`, `_extract_per_speaker_embeddings()`
- `src/transcribe_worker.py` — 转写主流程

---

## 问题 B：停止按钮逻辑错误（P1）

### 现象
转写时点击录音栏的"停止"按钮，转写也会被停止。

### 期望
录音栏的停止按钮只控制录音。转写停止应该通过任务明细行右侧的操作按钮。

### 代码位置
`home_page.py:382-400` — `_stop_recording()` 检查 `is_transcribing` 后调用 `stop_transcription()`

---

## 问题 C：转写时停止按钮变色（P1）

### 现象
开始转写后，录音栏的停止按钮会变色变成可点击状态。

### 期望
转写期间录音栏停止按钮应该保持禁用/灰色。

### 代码位置
`home_page.py:900-918` — `_transcribe_single()` 启用 stop_btn
`home_page.py:960-980` — `_start_transcription()` 启用 stop_btn

---

## 问题 D：任务明细行停止后状态不变（P1）

### 现象
点击任务明细行的停止按钮后，文件状态没有更新（应该变回 pending）。

### 代码位置
`home_page.py:847-869` — `_stop_transcription()`

---

## 问题 E：VB-Cable 未打包（P1）

### 现象
安装包不包含 VB-Cable，首次启动只有文字提示。

### 期望
1. installer.iss 打包 VB-Cable 安装文件到安装目录
2. 安装完成后提示用户"是否安装 VB-Audio Cable？"
3. 首次启动对话框加"一键安装"按钮（调用本地 VBCABLE_Setup_x64.exe）

### 文件位置
- `drivers/VBCABLE_Driver_Pack45/VBCABLE_Setup_x64.exe` — 已存在
- `installer.iss` — 需添加 [Files] 和 [Run]
- `src/gui/first_launch.py` — 需添加安装按钮
