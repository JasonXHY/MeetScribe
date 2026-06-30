# CJK 三个 Bug 修复方案

> 日期：2026-06-29
> 目的：修复 C（停止按钮变色）、J（黑色命令窗口）、K（双轨未转写）三个 bug
> 背景：代码已修复 8 项（A/B/D/E/F/G/H/I），剩余这 3 项需要方案

---

## 问题 C：转写时录音停止按钮变色可点击

### 问题描述

转写过程中，录音栏的停止按钮（红色）变为可点击状态。用户期望：转写时录音栏按钮全部禁用，停止转写应通过任务明细行右侧的停止按钮。

### 根因分析

**两个独立问题叠加：**

**问题 C-1：recorder 回调无条件更新录音栏**

`app.py:391` 的 `_on_recorder_state_change_safe()` 不检查转写状态，直接调用 `recording_bar.update_state()`：

```python
def _on_recorder_state_change_safe(self, is_recording, is_paused):
    self._recording = is_recording
    self._paused = is_paused
    recording_bar = self._home_page.get_recording_bar()
    if recording_bar:
        recording_bar.update_state(is_recording, is_paused)  # 无条件调用
```

如果 recorder 在转写期间触发了 `is_recording=True` 的回调（如先前录音的残留信号），录音栏会立即更新为"录音中"状态，stop_btn 变红可点击。

**问题 C-2：转写开始时录音栏未禁用**

`_start_transcription()` 和 `_transcribe_single()` 只禁用了转写按钮和AI摘要按钮，没有操作录音栏。录音栏保持"就绪"状态，用户可以随时点击开始录音。

### 修复方案

**文件：`src/gui/home_page.py`**

在 `_start_transcription()` 和 `_transcribe_single()` 中，转写开始时禁用录音栏：

```python
# 转写开始时
recording_bar = self.get_recording_bar()
if recording_bar:
    recording_bar.set_transcribing(True)
```

在 `_on_transcription_done_handler()` 和 `_stop_transcription()` 中恢复：

```python
# 转写结束/停止时
recording_bar = self.get_recording_bar()
if recording_bar:
    recording_bar.set_transcribing(False)
```

**文件：`src/gui/recording_bar.py`**

添加转写状态管理方法：

```python
def set_transcribing(self, transcribing):
    """设置转写状态，转写期间禁用所有录音按钮"""
    self._transcribing = transcribing
    if transcribing:
        self.record_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(...)  # 灰色样式
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet(...)  # 灰色样式
        self._combo.setEnabled(False)
    else:
        # 恢复到就绪状态
        self.update_state(self._recording, self._paused)
```

**文件：`src/gui/app.py`**

`_on_recorder_state_change_safe()` 添加转写状态守卫：

```python
def _on_recorder_state_change_safe(self, is_recording, is_paused):
    self._recording = is_recording
    self._paused = is_paused
    # 转写期间不更新录音栏
    if self._transcription_handler and self._transcription_handler.is_transcribing:
        return
    recording_bar = self._home_page.get_recording_bar()
    if recording_bar:
        recording_bar.update_state(is_recording, is_paused)
```

### 影响范围

- 仅影响 UI 状态管理，不涉及业务逻辑
- 转写期间录音栏完全禁用，转写结束后恢复
- recorder 回调在转写期间被跳过，不影响录音数据保存

---

## 问题 J：转写时弹出黑色命令窗口

### 问题描述

转写过程中会弹出黑色命令窗口（cmd 窗口），打断用户操作。这是安装版本的一个重要问题。

### 根因分析

`transcription.py:168` 使用 `multiprocessing.Process`：

```python
self._process = multiprocessing.Process(
    target=transcribe_worker_process,
    args=(...),
    daemon=True,
)
self._process.start()
```

**Windows + PyInstaller 下的 spawn 机制：**

1. `me.spec:100` 设置 `console=False`，主进程用 pythonw.exe 运行，不创建控制台
2. Windows 下 `multiprocessing.Process` 默认使用 **spawn** 启动方式
3. spawn 会创建新的 Python 解释器进程来执行子进程
4. 新进程从系统创建，**继承控制台行为**，导致黑色窗口闪现
5. 即使主进程是 pythonw.exe（无控制台），spawn 的子进程仍会创建控制台窗口

### 修复方案

**方案 A（推荐）：subprocess + CREATE_NO_WINDOW + 管道通信**

将 `multiprocessing.Process` 改为 `subprocess.Popen`，使用 `CREATE_NO_WINDOW` 标志。

**文件：`src/gui/transcription.py`**

```python
import subprocess
import sys
import json

# 替换 multiprocessing.Process
creation_flags = 0
if sys.platform == "win32":
    creation_flags = subprocess.CREATE_NO_WINDOW

cmd = [sys.executable, "-m", "transcribe_worker_cli"]
# 通过 JSON 文件传递参数（避免 pickle 限制）
params = {
    "queue_file": queue_file_path,
    "model_cache_dir": MODEL_CACHE_DIR,
    "device": device,
    "file_paths": task.file_paths,
    "output_format": task.fmt,
    "speaker_names": task.speaker_names,
    "output_dir": task.out_dir,
    "merge": task.merge,
}
# 写入临时参数文件
params_path = os.path.join(tempfile.gettempdir(), f"ms_transcribe_{os.getpid()}.json")
with open(params_path, "w", encoding="utf-8") as f:
    json.dump(params, f, ensure_ascii=False)

cmd.extend(["--params", params_path])
self._process = subprocess.Popen(
    cmd,
    creationflags=creation_flags,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

**文件：`src/transcribe_worker_cli.py`（新建）**

独立的 CLI 入口，替代 multiprocessing.Process 的 target 函数：

```python
#!/usr/bin/env python3
"""转写子进程 CLI 入口（subprocess 模式）"""
import sys
import json
import multiprocessing

def main():
    params_path = sys.argv[sys.argv.index("--params") + 1]
    with open(params_path, "r", encoding="utf-8") as f:
        params = json.load(f)

    queue = multiprocessing.Queue()
    # 调用现有的 transcribe_worker_process
    from transcribe_worker import transcribe_worker_process
    transcribe_worker_process(
        queue,
        params["model_cache_dir"],
        params["device"],
        params["file_paths"],
        params["output_format"],
        params["speaker_names"],
        params["output_dir"],
        params["merge"],
    )

if __name__ == "__main__":
    main()
```

**通信方式调整：**

原方案用 `multiprocessing.Queue` 做 IPC，但 subprocess 不能直接共享 Queue。需要改为文件通信：

```python
# 主进程轮询：读取子进程写入的 JSON Lines 文件
# 子进程每发一条消息，追加一行 JSON 到共享文件
```

**方案 B（更简单，风险较高）：threading.Thread**

直接用 `threading.Thread` 替代 `multiprocessing.Process`：

```python
self._thread = threading.Thread(
    target=transcribe_worker_process,
    args=(...),
    daemon=True,
)
self._thread.start()
```

**优势**：无进程创建 = 无控制台窗口；Queue 无需改动；代码改动最小

**风险**：
- FunASR 模型推理是 CPU 密集型，受 GIL 影响
- numpy/torch 的 C 扩展会释放 GIL，实际影响可能有限
- 如果转写期间 GUI 卡顿，用户体验下降

**方案 C：multiprocessing.freeze_support() + STARTUPINFO**

在 worker 入口添加 freeze_support，同时用 STARTUPINFO 隐藏窗口：

```python
if __name__ == "__main__":
    multiprocessing.freeze_support()
    # 但 freeze_support 只解决 frozen 模式兼容性，不隐藏窗口
```

freeze_support 不解决窗口问题。

### 推荐方案

**先试方案 B（threading），如果发现 GUI 卡顿再改方案 A（subprocess）。**

理由：
1. threading 改动最小（~5 行代码）
2. FunASR 的 numpy/torch 运算会释放 GIL，实际 GUI 影响有限
3. 转写本身是后台任务，即使偶尔卡顿也不影响录音
4. 如果方案 B 失败，方案 A 的文件通信机制较复杂，需要更多测试

### me.spec 影响

- 方案 B：me.spec 无需修改
- 方案 A：需要在 hiddenimports 中添加 `transcribe_worker_cli`

### 测试要点

1. 转写时无黑色窗口弹出
2. 转写正常完成，结果正确
3. 转写期间 GUI 无明显卡顿（方案 B）
4. 转写期间仍可操作文件列表、设置等

---

## 问题 K：在线会议系统音频未转写

### 问题描述

在线会议场景（腾讯会议等），转写结果只有麦克风录音，系统音频（腾讯会议声音）完全没有输出。

### 根因分析

`_transcribe_single()` 只转写单个文件，不检查双轨配对：

```python
def _transcribe_single(self, file_path):
    # ...
    handler.start([file_path], fmt, {}, "")  # 只传一个文件
```

**调用路径：**
1. 录音完成后弹窗询问 → `ask_transcribe_after_record(saved_files[0])` → `_transcribe_single(麦克风文件)`
2. 文件列表右键菜单 → `_transcribe_single(选中文件)`
3. 重试按钮 → `_retry_transcription(file_path)` → `_transcribe_single(file_path)`

所有路径都只传入一个文件路径，系统音频文件被完全忽略。

**对比 `_start_transcription()` 的正确实现：**

```python
def _start_transcription(self):
    # ...
    from dual_track_merge import find_dual_track_pair
    all_paths = []
    processed = set()
    for fp in paths:
        pair = find_dual_track_pair(fp)
        if pair:
            mic_path, sys_path = pair
            all_paths.extend([mic_path, sys_path])
            # ...
        else:
            all_paths.append(fp)
    handler.start(all_paths, fmt, {}, "")
```

批量转写有双轨检测，单文件转写没有。

### 修复方案

**文件：`src/gui/home_page.py`**

修改 `_transcribe_single()`，添加双轨检测：

```python
def _transcribe_single(self, file_path):
    """转写单个文件（自动检测双轨配对）"""
    if self._app and hasattr(self._app, '_transcription_handler'):
        handler = self._app._transcription_handler
        if handler.is_transcribing:
            QMessageBox.information(self, "提示", "正在转写中，请等待完成")
            return
        fmt = self.get_selected_format()

        # 检测双轨配对
        from dual_track_merge import find_dual_track_pair
        pair = find_dual_track_pair(file_path)
        if pair:
            mic_path, sys_path = pair
            files_to_transcribe = [mic_path, sys_path]
            self._log(f"检测到双轨配对: {os.path.basename(mic_path)} + {os.path.basename(sys_path)}")
        else:
            files_to_transcribe = [file_path]

        handler.start(files_to_transcribe, fmt, {}, "")
        self._btn_transcribe.setEnabled(False)
        self._btn_transcribe.setText("转写中...")
        self._log(f"开始转写: {', '.join(os.path.basename(f) for f in files_to_transcribe)}")
        self.refresh_file_list()
```

**关键点：**

1. `find_dual_track_pair()` 是双向的：传入麦克风文件会查找系统音频，传入系统音频也会查找麦克风文件
2. 返回 `(mic_path, sys_path)` 元组，两个文件都传给 handler
3. `handler.start()` 接收多文件后，worker 中的 `is_dual_track_group()` 会自动识别并按时间戳合并
4. 无需修改 `app.py` 的录音完成流程，因为 `find_dual_track_pair()` 会自动在磁盘上查找配对文件

### 影响范围

- 仅修改 `_transcribe_single()` 一个方法，添加 6 行双轨检测代码
- 不影响批量转写（`_start_transcription()` 已有此逻辑）
- 不影响单文件转写（无配对时走原逻辑）
- 录音完成后的转写弹窗也会受益（调用 `_transcribe_single`）

### 测试要点

1. 录音完成后点击"是"转写 → 双轨文件都被转写并合并
2. 文件列表右键转写麦克风文件 → 自动检测并转写配对文件
3. 文件列表右键转写系统音频文件 → 自动检测并转写配对文件
4. 单文件转写（无配对）→ 正常转写单个文件
5. 转写结果包含"本地"和"远程"两个说话人来源

---

## 实施顺序

1. **K（P0）**：_transcribe_single() 添加双轨检测（6 行代码，风险最低）
2. **C（P1）**：recording_bar 添加转写状态管理（3 个文件，~30 行代码）
3. **J（P1）**：multiprocessing → threading（~5 行代码，先试最简方案）

## 打包验证清单

- [ ] K：在线会议录音后转写，确认双轨合并结果
- [ ] C：转写期间录音栏按钮全部禁用
- [ ] J：转写时无黑色命令窗口弹出
- [ ] 转写结果正确，无功能退化
- [ ] GUI 在转写期间保持响应
