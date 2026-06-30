# 第7次打包后测试问题修复方案

> 日期：2026-06-29
> 来源：安装版测试 + 日志分析
> 状态：待 Qoder 审查

---

## [S1] 问题概览

| # | 问题 | 优先级 | 根因 |
|---|------|--------|------|
| A | 转写失败（子进程残留+卡死） | P0 | 第一次子进程卡死后未 terminate，第二次因资源占用也卡死；超时后未 terminate、未更新状态、未重置 UI |
| B | 停止按钮逻辑错误 | P1 | `_stop_recording()` 检查 `is_transcribing` 后停止转写 |
| C | 转写时停止按钮变色 | P1 | `_transcribe_single()` 和 `_start_transcription()` 启用了 stop_btn |
| D | 任务明细行停止后状态不变 | P1 | `_stop_transcription()` 未调用 `refresh_file_list()` |
| E | VB-Cable 未打包 | P1 | installer.iss 未包含 VB-Cable |
| F | 首次启动对话框 | P2 | 已修复（app_version 检测），待验证 |
| G | 超时后未 terminate 进程 | P2 | 超时只标记状态 |

---

## [S2] 问题 A：转写失败 — 子进程残留+卡死（P0）

### 根因分析

日志对比揭示了问题本质：

**失败案例 (062914会议.wav, 199秒)**：
```
14:49:02 [SUBPROCESS] Subprocess started  ← 第一次，卡死在模型加载前
14:55:49 [SUBPROCESS] Subprocess started  ← 第二次，用户再次点击
14:56:06 [SUBPROCESS] Loading models...
14:56:11 [SUBPROCESS] Models loaded successfully
14:58:11 转写超时：子进程 120 秒无响应
```

**成功案例 (062915会议.wav, 166秒)**：
```
15:18:37 [SUBPROCESS] Subprocess started
15:18:53 [SUBPROCESS] Loading models...
15:19:21 [SUBPROCESS] Models loaded successfully
15:19:59 [SUBPROCESS] [SPK-EMB-PER] Found 4 speakers
15:20:06 [SUBPROCESS] Transcription completed in 44.3s
15:20:32 [SUBPROCESS] Punctuation applied to 60 sentences
15:21:19 LLM 纠错完成
```

**关键发现**：
1. 第一次子进程（14:49:02）卡死后从未被 terminate，占用系统资源
2. 第二次子进程（14:55:49）虽然加载了模型，但 generate 阶段因资源占用卡死
3. 超时触发后只标记 `_transcribing = False`，未执行以下操作：
   - `self._process.terminate()` — 终止残留子进程
   - 文件状态更新为 `failed`
   - UI 按钮重置

### 修复方案

#### A1. 超时检测加 terminate（`transcription.py`）

在 `_poll()` 的超时检测分支中，终止子进程：

```python
# 心跳超时检测：进程存活但长时间无消息
elif self._process and self._process.is_alive() and self._last_heartbeat > 0:
    elapsed = time.time() - self._last_heartbeat
    if elapsed > self._heartbeat_timeout:
        logger.error(f"转写超时：子进程 {elapsed:.0f} 秒无响应")
        self.log_message.emit(f"转写超时：子进程 {elapsed:.0f} 秒无响应")
        # 终止残留子进程
        try:
            self._process.terminate()
            self._process.join(timeout=3)
        except Exception as e:
            logger.warning(f"终止超时子进程失败: {e}")
        self._transcribing = False
        self._poll_timer.stop()
        self._on_done()
```

#### A2. 超时后更新文件状态（`transcription.py`）

在 `_on_done()` 中，对所有 processing 状态的文件标记为 failed：

```python
def _on_done(self):
    """转写完成"""
    if self._done_called:
        return
    self._done_called = True
    self._transcribing = False
    self._poll_timer.stop()

    success_count = sum(1 for s in self._file_status.values() if s == "done")
    fail_count = sum(1 for s in self._file_status.values() if s == "failed")

    # 将未完成的 processing 文件标记为 failed
    if self._app and hasattr(self._app, 'file_manager'):
        for fp, status in self._file_status.items():
            if status == "processing":
                self._app.file_manager.update_status(fp, FileStatus.FAILED)
                self._file_status[fp] = "failed"
                fail_count += 1

    # ... 其余逻辑不变
```

#### A3. 超时后重置 UI（`transcription.py`）

在超时处理中，通过信号通知主线程重置 UI：

```python
# 在 _poll() 的超时分支中
self.transcription_done.emit(0, fail_count)  # 通知 UI 重置
```

#### A4. 转写前清理残留子进程（`transcription.py`）

在 `_execute_task()` 开始时，检查并清理残留子进程：

```python
def _execute_task(self, task):
    """执行转写任务"""
    # 清理残留子进程
    if self._process and self._process.is_alive():
        logger.warning("发现残留子进程，正在清理")
        try:
            self._process.terminate()
            self._process.join(timeout=3)
        except Exception:
            pass
        self._process = None

    self._transcribing = True
    # ... 其余逻辑不变
```

### 涉及文件
- `src/gui/transcription.py` — `_poll()`, `_on_done()`, `_execute_task()`

---

## [S3] 问题 B：停止按钮逻辑错误（P1）

### 根因分析

`home_page.py:382-400` 的 `_stop_recording()` 检查 `is_transcribing` 后直接调用 `stop_transcription()`，导致录音栏停止按钮也能停止转写。

```python
def _stop_recording(self):
    """停止录音或停止转写"""
    # 优先检查是否在转写中
    if self._app and hasattr(self._app, '_transcription_handler'):
        if self._app._transcription_handler.is_transcribing:
            self._app._transcription_handler.stop_transcription()  # ← 错误
            self._recording_bar.update_state(recording=False, paused=False)
            self._log("转写已停止")
            return
    # 否则停止录音
    ...
```

### 修复方案

删除对 `is_transcribing` 的检查，录音栏停止按钮只控制录音。转写停止由任务明细行的停止按钮处理：

```python
def _stop_recording(self):
    """停止录音"""
    try:
        if self._app and hasattr(self._app, 'recorder'):
            self._app.recorder.stop()
        self._recording_bar.update_state(recording=False, paused=False)
        self._stop_timer()
        self._log("录音已停止")
    except Exception as e:
        self._log(f"停止录音失败: {e}")
```

### 涉及文件
- `src/gui/home_page.py` — `_stop_recording()`

---

## [S4] 问题 C：转写时停止按钮变色（P1）

### 根因分析

`_transcribe_single()` (line 895-900) 和 `_start_transcription()` (line 960-968) 都启用了 `stop_btn` 并设为红色：

```python
self._recording_bar.stop_btn.setEnabled(True)
self._recording_bar.stop_btn.setStyleSheet(f"""
    QPushButton {{
        background-color: transparent;
        border: 1px solid {C_ERROR};
        ...
    }}
""")
```

这使得转写期间录音栏的停止按钮变成可点击状态，但点击后会触发错误的逻辑（问题 B）。

### 修复方案

转写期间不操作录音栏的 `stop_btn`。删除 `_transcribe_single()` 和 `_start_transcription()` 中对 `stop_btn` 的操作：

**`_transcribe_single()`** — 删除 stop_btn 相关代码：
```python
def _transcribe_single(self, file_path):
    """转写单个文件"""
    if self._app and hasattr(self._app, '_transcription_handler'):
        handler = self._app._transcription_handler
        if handler.is_transcribing:
            QMessageBox.information(self, "提示", "正在转写中，请等待完成")
            return
        fmt = self.get_selected_format()
        handler.start([file_path], fmt, {}, "")
        self._btn_transcribe.setEnabled(False)
        self._btn_transcribe.setText("转写中...")
        # 删除以下两行
        # self._recording_bar.stop_btn.setEnabled(True)
        # self._recording_bar.stop_btn.setStyleSheet(...)
        self._log(f"开始转写: {os.path.basename(file_path)}")
        self.refresh_file_list()
```

**`_start_transcription()`** — 同样删除 stop_btn 相关代码。

### 涉及文件
- `src/gui/home_page.py` — `_transcribe_single()`, `_start_transcription()`

---

## [S5] 问题 D：任务明细行停止后状态不变（P1）

### 根因分析

`_stop_transcription()` (line 829-851) 只禁用了 `stop_btn`，没有刷新文件列表：

```python
def _stop_transcription(self, file_path):
    """停止转写"""
    if self._app and hasattr(self._app, '_transcription_handler'):
        self._app._transcription_handler.stop_transcription(file_path)
        self._recording_bar.stop_btn.setEnabled(False)
        self._recording_bar.stop_btn.setStyleSheet(...)
        # 缺少: self.refresh_file_list()
```

### 修复方案

在 `_stop_transcription()` 末尾加 `self.refresh_file_list()`：

```python
def _stop_transcription(self, file_path):
    """停止转写"""
    if self._app and hasattr(self._app, '_transcription_handler'):
        self._app._transcription_handler.stop_transcription(file_path)
        self._recording_bar.stop_btn.setEnabled(False)
        self._recording_bar.stop_btn.setStyleSheet(...)
        self.refresh_file_list()  # 新增：刷新文件列表更新状态
```

### 涉及文件
- `src/gui/home_page.py` — `_stop_transcription()`

---

## [S6] 问题 E：VB-Cable 未打包（P1）

### 根因分析

`installer.iss` 没有 `[Files]` 段包含 VB-Cable，也没有安装后提示。VB-Cable 安装包已在项目中（`drivers/VBCABLE_Driver_Pack45/VBCABLE_Setup_x64.exe`）。

### 修复方案

#### E1. installer.iss 添加 VB-Cable 打包

```ini
[Files]
; VB-Cable 安装包（供用户手动安装）
Source: "drivers\VBCABLE_Driver_Pack45\*"; DestDir: "{app}\drivers\VBCABLE_Driver_Pack45"; Flags: ignoreversion recursesubdirs createallsubdirs
```

#### E2. installer.iss 添加安装后提示

在 `[Code]` 段的 `CurStepChanged` 中，安装完成后弹窗提示：

```pascal
procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
  VBCableResult: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := ExpandConstant('{localappdata}\MeetScribe');
    if not DirExists(DataDir) then
    begin
      CreateDir(DataDir);
    end;
    SaveStringToFile(DataDir + '\install_path.txt', ExpandConstant('{app}'), False);
    SaveStringToFile(DataDir + '\data_dir.txt', DataDir, False);

    // VB-Cable 安装提示
    VBCableResult := MsgBox('是否安装 VB-Audio Cable？' + #13#10 +
      'VB-Audio Cable 是虚拟音频设备，用于录制线上会议的系统音频。' + #13#10 +
      '如果只需要录制麦克风音频，可以跳过。',
      mbConfirmation, MB_YESNO);
    if VBCableResult = IDYES then
    begin
      Exec(ExpandConstant('{app}\drivers\VBCABLE_Driver_Pack45\VBCABLE_Setup_x64.exe'), '', '', SW_SHOWNORMAL, ewWaitUntilTerminated, VBCableResult);
    end;
  end;
end;
```

#### E3. 首次启动对话框加一键安装按钮（`first_launch.py`）

在 VB-Cable 检测区域加"安装"按钮：

```python
self._vb_install_btn = QPushButton("一键安装")
self._vb_install_btn.setFixedHeight(24)
self._vb_install_btn.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 11px;
        padding: 0 8px;
    }}
    QPushButton:hover {{
        background-color: {C_BTN_HOVER};
    }}
""")
self._vb_install_btn.setCursor(Qt.PointingHandCursor)
self._vb_install_btn.clicked.connect(self._install_vbcable)
vb_layout.addWidget(self._vb_install_btn)
```

添加安装方法：

```python
def _install_vbcable(self):
    """一键安装 VB-Cable"""
    import subprocess
    exe_path = os.path.join(os.path.dirname(sys.executable), 'drivers', 'VBCABLE_Driver_Pack45', 'VBCABLE_Setup_x64.exe')
    if not os.path.exists(exe_path):
        # 开发模式下查找
        exe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'drivers', 'VBCABLE_Driver_Pack45', 'VBCABLE_Setup_x64.exe')
    if os.path.exists(exe_path):
        subprocess.Popen([exe_path], shell=True)
        self._vb_status_lbl.setText("安装程序已启动，请按提示完成安装")
        self._vb_status_lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 11px; background: transparent; border: none;")
        self._vb_install_btn.setEnabled(False)
    else:
        self._vb_status_lbl.setText("未找到安装程序，请手动下载")
        self._vb_status_lbl.setStyleSheet(f"color: {C_ERROR}; font-size: 11px; background: transparent; border: none;")
```

### 涉及文件
- `installer.iss` — 添加 [Files] 和 [Code]
- `src/gui/first_launch.py` — 添加安装按钮和方法

---

## [S7] 问题 F：首次启动对话框（P2）

### 状态
已通过 `app_version` 版本检测修复（config.py + app.py + first_launch.py），待下次安装验证。

---

## [S8] 问题 G：超时后未 terminate 进程（P2）

### 根因分析

超时检测触发后只标记 `_transcribing = False`，没有 terminate 子进程。残留子进程继续占用资源。

### 修复方案

已在问题 A 的修复方案 A1 中包含：超时检测加 `self._process.terminate()`。

---

## [S9] 修复顺序

| 顺序 | 问题 | 原因 |
|------|------|------|
| 1 | A（转写失败） | P0 + 核心功能，且包含 G 的修复 |
| 2 | B + C（停止按钮） | P1 + 相关，一起修复 |
| 3 | D（状态更新） | P1 + 改动小 |
| 4 | E（VB-Cable 打包） | P1 + 改动中等 |
| 5 | F（首次启动验证） | P2 + 已修复待验证 |

---

## [S10] 验证计划

修复后需验证：
1. 全量测试 `pytest tests/ -v` 通过
2. 转写失败后：子进程被 terminate、文件状态变为 failed、UI 按钮正确重置
3. 连续转写：第一次失败后第二次能正常转写
4. 录音栏停止按钮：转写期间保持禁用
5. 任务明细行停止：文件状态正确更新
6. VB-Cable：安装包包含、安装后提示、首次启动一键安装
7. 安装后完整流程：启动 → 首次引导 → 录音 → 转写 → 停止

---

## [S11] Qoder 审查意见（2026-06-29 第二轮）

> 逐条对照当前代码（transcription.py、home_page.py、transcribe_worker.py、installer.iss）验证方案。

### 问题 A：转写失败 — 方案基本正确，A2 和 A3 需注意细节

**代码验证**：
- `transcription.py:204-212` 已有心跳超时检测，超时值 120 秒（第 65 行 `_heartbeat_timeout = 120`）
- `transcription.py:220-221` 已有 `"heartbeat"` 消息类型处理，更新 `_last_heartbeat`
- `transcribe_worker.py:126,139,168,213` 已发送 `("heartbeat", ...)` 消息
- `transcription.py:334-344` 的 `_on_done()` **已有** `process.terminate()` 逻辑（第 337-338 行）

**方案评价**：

1. **A1（超时加 terminate）**：当前超时分支（第 210-212 行）调用 `_on_done()`，而 `_on_done()` 第 337-338 行已有 `if self._process.is_alive(): self._process.terminate()`。所以 **terminate 已经在 `_on_done()` 中执行了**。A1 的改动是冗余的，但作为防御性编程可以接受——在超时分支显式 terminate 比依赖 `_on_done()` 的清理逻辑更清晰。

2. **A2（processing → failed）**：**正确且必要**。当前 `_on_done()` 只统计 done/failed 数量，不会把 processing 状态的文件标记为 failed。超时场景下文件会永远停留在 "processing" 状态。

3. **A3（emit transcription_done）**：**正确且必要**。当前超时分支只设了 `_transcribing = False` 和调用 `_on_done()`，但没有 emit `transcription_done` 信号。`home_page.py:565` 的 `_on_transcription_done_handler` 连接了这个信号来重置 UI。不 emit 这个信号，UI 按钮不会重置。

4. **A4（转写前清理残留）**：**合理**。当前 `_execute_task()` 不检查残留进程。虽然正常流程中 `_on_done()` 会清理 `self._process = None`，但异常情况下可能有残留。

**建议**：A1-A4 全部实施。A1 虽然是冗余的防御性代码，但使逻辑更清晰。A2 和 A3 是真正修复 bug 的关键改动。

### 问题 B：停止按钮逻辑错误 — 方案正确 ✅（审查修正）

**代码验证**：
- `home_page.py:382-400` 的 `_stop_recording()` 先检查 `is_transcribing` 再调用 `stop_transcription()`
- 录音栏停止按钮与录音停止按钮是**同一个按钮**

**方案评价**：

**方案正确。** 一个停止按钮不应承载两个功能。场景分析：

- 转写进行中 → 用户开始新录音 → 录完想停止 → 点录音栏停止按钮 → **结果停掉了转写，录音还在继续**

这是功能冲突 bug。录音栏的停止按钮应只控制录音，转写停止由任务明细行操作列的"停止"按钮负责（`file_list_view.py:414` → `_stop_transcription()`）。

**补充**：`_stop_transcription()` 调用 `stop_transcription(file_path)`，后者虽然传了 `file_path`，但实际会 `terminate()` 整个子进程（`transcription.py:996-998`），所以任务明细行的停止按钮能终止整个转写任务，不存在"没有全局停止"的问题。

直接按方案实施，删除 `_stop_recording()` 中的 `is_transcribing` 检查。

### 问题 C：转写时停止按钮变色 — 方案正确 ✅（审查修正）

**代码验证**：
- `home_page.py:885-899`（`_transcribe_single`）和 `948-962`（`_start_transcription`）确实设置了 `stop_btn` 为红色
- 这使得录音栏停止按钮在转写期间变成可点击的红色，但点击后触发的是 `_stop_recording()` → 检查 `is_transcribing` → 停掉转写（问题 B 的 bug）

**方案评价**：

**方案正确。** 既然问题 B 确认录音栏停止按钮只控制录音，那转写期间就不应该操作这个按钮。删除 `_transcribe_single()` 和 `_start_transcription()` 中对 `stop_btn` 的 `setEnabled`/`setStyleSheet` 操作。

同理，`_on_transcription_done_handler`（第 570-588 行）中对 `stop_btn` 的样式重置也应删除——它不应该操作录音栏的按钮。

### 问题 D：任务明细行停止后状态不变 — 方案正确

**代码验证**：
- `home_page.py:829-851` 的 `_stop_transcription()` 确实没有调用 `refresh_file_list()`
- 对比 `_queue_move_up()`（第 853-858 行）和 `_queue_remove()`（第 867-872 行）都有 `refresh_file_list()`

**方案评价**：正确，直接实施。`_stop_transcription()` 和 `_stop_recording()` 都需要确保在操作后调用 `refresh_file_list()`。

### 问题 E：VB-Cable 未打包 — 方案可行，但有权限风险

**代码验证**：
- `installer.iss` 当前没有 VB-Cable 相关 [Files] 或 [Code]
- `drivers/VBCABLE_Driver_Pack45/` 目录存在（已验证）
- VB-Cable 安装程序是 `VBCABLE_Setup_x64.exe`

**方案评价**：

1. **E1（打包 VB-Cable 到 `{app}\drivers\`）**：可行。VB-Cable 安装包约 2MB，对安装包体积影响很小。加 `nocompression` flag（已是压缩数据）。

2. **E2（安装后弹窗提示）**：可行。Inno Setup 以 admin 权限运行，`Exec()` 调用 VB-Cable 安装程序也会以 admin 权限运行，这正好是 VB-Cable 驱动安装所需的。`ewWaitUntilTerminated` 会等待安装完成再继续，这是正确的。

3. **E3（首次启动一键安装）**：**有权限风险**。`first_launch.py` 的 `_install_vbcable()` 使用 `subprocess.Popen([exe_path], shell=True)` 启动 VB-Cable 安装程序。但应用运行在**标准用户权限**下（从 Program Files 启动，无 admin），VB-Cable 安装需要 admin 权限来安装内核驱动。`subprocess.Popen` 不会触发 UAC 提权，VB-Cable 安装程序可能因权限不足而失败。

   **修复方案**：使用 `ctypes.windll.shell32.ShellExecuteW` 配合 `"runas"` 动词触发 UAC 提权：
   ```python
   def _install_vbcable(self):
       import ctypes
       exe_path = os.path.join(os.path.dirname(sys.executable), 'drivers', 'VBCABLE_Driver_Pack45', 'VBCABLE_Setup_x64.exe')
       if not os.path.exists(exe_path):
           exe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'drivers', 'VBCABLE_Driver_Pack45', 'VBCABLE_Setup_x64.exe')
       if os.path.exists(exe_path):
           # 使用 ShellExecuteW + "runas" 触发 UAC 提权
           ret = ctypes.windll.shell32.ShellExecuteW(
               0, "runas", exe_path, "", None, 1  # SW_SHOWNORMAL=1
           )
           if ret > 32:  # ShellExecute 返回值 > 32 表示成功
               self._vb_status_lbl.setText("安装程序已启动，请按提示完成安装")
           else:
               self._vb_status_lbl.setText("无法启动安装程序（可能需要管理员权限）")
       else:
           self._vb_status_lbl.setText("未找到安装程序，请手动下载")
   ```

**建议**：E1 和 E2 直接实施。E3 需要修改为使用 `ShellExecuteW` + `"runas"` 提权。

### 问题 F：首次启动对话框 — 已修复待验证

无审查意见。

### 问题 G：超时后未 terminate 进程 — 已包含在问题 A 中

**代码验证**：
- 当前超时分支（第 210-212 行）调用 `_on_done()`
- `_on_done()` 第 337-338 行已有 `if self._process.is_alive(): self._process.terminate()`

**方案评价**：问题 G 实际上**已经被 `_on_done()` 处理了**。超时 → `_on_done()` → `process.terminate()`。文档中的根因分析（"超时后未 terminate"）不完全准确——terminate 是执行了的，只是不够及时（需要等 `_on_done()` 执行到清理步骤）。A1 在超时分支显式 terminate 是好的防御性编程。

### 汇总

| # | 问题 | 方案评价 | 建议 |
|---|------|----------|------|
| A | 转写失败 | ✅ 基本正确 | A2（processing→failed）和 A3（emit done 信号）是关键修复 |
| B | 停止按钮逻辑 | ✅ 方案正确 | 一个按钮不该承载两个功能，删除 `is_transcribing` 检查 |
| C | 转写时停止按钮变色 | ✅ 方案正确 | 删除转写时对 `stop_btn` 的操作，含 `_on_transcription_done_handler` 中的样式重置 |
| D | 任务明细行状态 | ✅ 正确 | 直接加 `refresh_file_list()` |
| E | VB-Cable 打包 | ✅ 可行，E3 需修改 | E3 的 `subprocess.Popen` 无法提权，需改用 `ShellExecuteW` + `"runas"` |
| F | 首次启动 | ✅ 已修复待验证 | 无 |
| G | 超时未 terminate | ✅ 已包含在 A 中 | `_on_done()` 已有 terminate，A1 是防御性增强 |

### 修复顺序建议

| 顺序 | 问题 | 原因 |
|------|------|------|
| 1 | **A（转写失败）** | P0 + 核心功能，A2/A3 是关键修复 |
| 2 | **B + C（停止按钮）** | P1 + 相关，一起修复：B 删除 `is_transcribing` 检查，C 删除转写时 `stop_btn` 操作 |
| 3 | **D（状态更新）** | P1 + 一行改动 |
| 4 | **E（VB-Cable 打包）** | P1 + E3 需改用 `ShellExecuteW` 提权 |
| 5 | **F（首次启动验证）** | P2 + 已修复待验证 |
