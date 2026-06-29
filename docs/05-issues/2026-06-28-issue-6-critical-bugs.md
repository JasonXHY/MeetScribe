# 第6次打包后 6 个关键问题

> 日期：2026-06-28
> 来源：第6次打包后用户验收测试
> 状态：待修复

## 问题汇总

| # | 问题 | 优先级 | 根因 |
|---|------|--------|------|
| 1 | 首次启动对话框消失 | P0 | config 残留跨安装 |
| 2 | VB-Cable 安装逻辑丢失 | P0 | installer.iss 迭代中被覆盖 |
| 3 | VB-Cable 缺少运行时检测 | P1 | 无错误提示 |
| 4 | 转录子进程静默崩溃 | P0 | C++ 层段错误 |
| 5 | 停止按钮竞态条件 | P1 | 子进程死亡时 UI 不一致 |
| 6 | config 跨安装残留 | P2 | installer.iss 无 UninstallDelete |

---

## 问题 1：首次启动对话框消失

### 现象
重装后首次启动对话框不显示，Step 1（API Key 引导）和 Step 2（模型下载）全部消失。

### 根因
Inno Setup 默认不删除 `%LOCALAPPDATA%\MeetScribe`。重装时旧 `settings.json` 残留，其中 `first_launch=false`。

### 代码路径
- `app.py:234` — `if check_first_launch(self.config)` 检查 `config.get("first_launch", True)`
- `config.py` — 从 `%LOCALAPPDATA%\MeetScribe\config\settings.json` 加载
- `first_launch.py:390` — 对话框完成时设置 `first_launch=False`
- `installer.iss` — 无 `[UninstallDelete]` 段，AppData 目录残留

### 影响
- 新用户看不到 API Key 引导（不知道有内置 API 可用）
- 新用户看不到模型下载引导（如果模型未打包）
- VB-Cable 安装提示也在此对话框中，一并丢失

---

## 问题 2：VB-Cable 安装逻辑完全丢失

### 现象
installer.iss 中无任何 VB-Cable 相关内容，应用内也无 VB-Cable 安装检测或提示。

### 历史
- active.md 曾记录"installer.iss: 添加模型目录复制 + VB-Cable 静默安装"为"已完成"
- 但当前 installer.iss（65行）无 VB-Cable 任何痕迹
- 推测在第5-6次打包迭代中被覆盖或删除

### MEMORY.md 已知约束
- VB-Cable 的 `VBCABLE_Setup_x64.exe` 不支持 `/VERYSILENT` 或任何 CLI 参数
- 是自定义安装程序，必须手动交互，安装后强制跳转捐赠页面
- 没有静默安装方式，GitHub 搜索确认无开源项目集成

### 当前代码中 VB-Cable 相关逻辑
- `config.py:30` — `use_vb_cable: False`（默认关闭）
- `settings_page.py:426-439` — 复选框，但依赖 VB-Cable 已装好
- `unified_recorder.py:157-158` — `_find_vb_cable()` 只检测不安装
- `first_launch.py:198` — 仅一行文字 hint，无安装按钮
- `first_launch.py:346` — `_open_vbcable_download()` 打开浏览器（未被调用）

### 影响
- 线上会议录音（dual 模式）无法录制系统音频
- 用户不知道需要安装 VB-Cable
- 设置页复选框勾选后实际无法工作

---

## 问题 3：VB-Cable 缺少运行时检测和错误提示

### 现象
用户在 dual 模式下录音，如果 VB-Cable 未安装：
- `_find_vb_cable()` 找不到设备
- 录音可能静默降级为仅麦克风
- 或者直接报错但错误信息不明确

### 日志证据 (`meetscribe.log:116`)
```
VB-Cable 检测失败（视为未安装）: No module named 'pyaudio'
```
这只是启动时的一次性检测，之后不再检查。

### 代码位置
- `unified_recorder.py:157-158` — `if self._use_vb_cable: vb_index = self._find_vb_cable(p)`
- `unified_recorder.py:208` — `_find_vb_cable()` 遍历设备查找 "CABLE Output"

### 影响
- 用户不知道为什么系统音频录不到
- 没有弹窗提示"请安装 VB-Audio Cable"
- 录音结果可能缺少系统音频轨道

---

## 问题 4：转录子进程静默崩溃

### 现象
19分钟音频转录在 9 秒内"完成"，实际子进程崩溃。

### 日志证据 (`meetscribe.log:598-664`)
```
17:49:10 [SUBPROCESS] Subprocess started
17:49:15 [SUBPROCESS] Loading models...
17:49:15 [SUBPROCESS]   model: ...SenseVoiceSmall
17:49:15 [SUBPROCESS]   vad_model: ...speech_fsmn_vad
17:49:15 [SUBPROCESS]   spk_model: cam++
17:49:19 [VOICEPRINT] No speaker embeddings received  ← 主进程发现子进程已死
```

### 根因分析
- 子进程在 `AutoModel(**kwargs)` 或 `model.generate()` 时被 OS 杀死（段错误）
- Python 层 try/except 无法捕获 C++ 层崩溃
- `transcribe_worker.py:241-243` 的异常处理无法触发
- 主进程 `_poll()` 检测到进程死亡后调用 `_on_done()`，显示"转写完成: 成功 0 个"

### 涉及文件
- `transcriber.py:548` — `AutoModel(**kwargs)` 加载
- `transcriber.py:701-705` — `model.generate()` 转写
- `transcribe_worker.py:97-244` — 子进程主函数

### 已知线索
- `_patch_funasr_campplus` 成功（17:09:57 日志确认）
- 模型路径存在且正确（AppData/models/models/iic/）
- funasr 已打包到 PyInstaller（datas + hiddenimports）
- 早期构建有 `Failed to patch campplus utils: No such file or directory: version.txt`，最新构建已修复

### 排查方向
1. 在子进程的 try/except 外加 `signal.signal(SIGSEGV, ...)` 尝试捕获段错误
2. 在模型加载后、转写前发送心跳消息确认子进程存活
3. 检查 FunASR 版本与 CAM++ 模型的兼容性
4. 检查 `_safe_model_path` 复制模型到临时目录是否在子进程中正常完成

---

## 问题 5：停止按钮竞态条件

### 现象
用户报告停止按钮在停止后仍可点击。

### 代码分析
- `_stop_recording()` (`home_page.py:382-400`) 检查 `is_transcribing` 后调用 `stop_transcription()`
- 如果子进程在检查和调用之间崩溃，`is_transcribing` 仍为 True
- `terminate()` 对已死进程报错
- `_on_done()` 和 `_stop_recording()` 都会操作 stop_btn 样式，可能互相覆盖

### 涉及文件
- `home_page.py:382-400` — `_stop_recording()`
- `home_page.py:565-593` — `_on_transcription_done_handler()` 单独设置 stop_btn
- `recording_bar.py:205-367` — `update_state()` 状态管理
- `transcription.py:971-990` — `stop_transcription()`

---

## 问题 6：config 残留导致跨安装行为异常

### 现象
Inno Setup 不清理 AppData，导致：
- `first_launch=false` 跨安装残留（问题 1）
- `use_vb_cable` 旧值残留
- 旧模型文件残留占磁盘空间
- `file_history.json` 残留显示旧文件

### installer.iss 现状
- `[UninstallDelete]` 段不存在
- 只删除 `{app}` 目录（Program Files）
- AppData 目录完全保留
