# MeetScribe 开发计划 v3

> 版本: v3.3
> 创建日期: 2026-06-01
> 最后更新: 2026-06-11
> 基于: DEVPLAN_V2.md (2026-05-29)
> 状态: 进行中

---

## 一、v2 → v3 变更摘要

### v2 成就

- ✅ 多进程架构（GUI 主进程 + 模型推理子进程）
- ✅ SenseVoice + CAM++ + ct-punc 转写管线
- ✅ 双轨录音（麦克风 + 系统音频 WASAPI Loopback）
- ✅ AI 摘要（MiMo 云端）+ LLM 纠错
- ✅ 发言人姓名自动识别（正则 + Ollama LLM）
- ✅ 多格式输出（llm-md / md / html / txt / srt / json）
- ✅ 合并转写 + 双轨合并
- ✅ 文件历史持久化

### v3 已完成

- ✅ 修复 dual 模式录音崩溃 bug（ERR-009）
- ✅ 修复 dual 模式"打开媒体文件"报错
- ✅ 重构 gui.py（107KB → 多模块）
- ✅ 优化轮询机制（100ms → 事件驱动）
- ✅ 添加转写进度条
- ✅ 添加单元测试框架（59 个测试）
- ✅ 转写完成弹窗提醒
- ✅ 列表宽度调整（图标化）
- ✅ 虚拟音频设备集成（VB-Audio Cable）
- ✅ 停止功能 + 弹窗确认
- ✅ 重新转写按钮
- ✅ UI 设计风格统一
- ✅ 转写队列管理
- ✅ 导出选项
- ✅ 系统通知
- ✅ Tooltip 悬停提示
- ✅ UI 日志过滤
- ✅ 打开文件夹
- ✅ 录音格式优化（16kHz）
- ✅ 音色库功能（声纹比对）
- ✅ 修复循环导入问题（gui/__init__.py 延迟导入）
- ✅ 修复暂停/继续按钮状态问题

### v3 待实现

- 📋 批量操作
- 📋 转写质量评分
- 📋 音频预览
- 📋 自适应列宽 + 折叠布局
- 📋 企业内网大模型对接
- 📋 拖拽上传
- 📋 转写任务队列管理优化（详见 docs/superpowers/specs/2026-06-03-transcription-queue-design.md）
- 📋 双轨合并调试日志增强
- 📋 双轨合并执行时机优化
- ✅ 音色库页面（将音色库加入侧边栏）
- ✅ 音色库数据编辑功能
- ✅ 手动新增语音库（录音朗读预设文本 → 提取声纹 → 保存）
- 📋 语音库音频处理（从已有录音文件提取声纹到音色库）
- ✅ 性能优化（按钮增量更新、防抖、异步 I/O、自适应轮询）
- ✅ 代码清理（死代码删除、类型统一、线程安全）
- ✅ 文件拆分（FileListView、RecordingBar、Formatters、ModelManager）

### v3.3 新增（2026-06-11）

- ✅ UI 优化第三轮：列头对齐、滚轮共存、高度自适应、关于区域、API Key
- ✅ 录音按钮状态修复（"启动中..."卡住）
- ✅ 文件列表滚轮修复（递归绑定子控件）
- ✅ 声纹嵌入向量持久化（重启后可恢复）
- ✅ 列权重调整（文件名缩窄、主题加宽）
- ✅ 主题截断移除
- ✅ 录音文件命名简化
- ✅ 文档体系重构（归档旧文档、新建核心文档、Agent 分区）

---

## 二、已知 Bug 跟踪

### ERR-009: dual 模式录音 SystemError 崩溃

- **首次出现**: 2026-05-29 18:04
- **错误信息**: `SystemError` at tkinter `__call__`
- **触发条件**: 使用 dual 模式录音，开始录音后几秒内 GUI 崩溃
- **复现率**: 高（日志中出现 4 次）
- **根因分析**:

  ```
  PyAudioWPatch 的音频回调（非主线程）→ 修改了 tkinter 变量或触发了 after() 回调
  → tkinter 不是线程安全的 → SystemError
  ```

  具体来说，`unified_recorder.py` 中的 `_audio_loop` 在后台线程运行 PyAudio，
  音频回调（`mic_cb` / `sys_cb`）也在这个线程中执行。虽然回调本身只往 queue 放数据，
  但 PyAudioWPatch 的内部实现可能在设备打开/关闭时触发了 tkinter 事件循环的干扰。

- **日志证据**:
  ```
  [18:04:29] Loopback recording started: meeting_20260529_180429_sys.wav
  [18:04:29] 录音模式: dual
  [18:04:29] 录音已开始
  [18:04:29] CRITICAL - Unexpected error: SystemError
  ```

- **修复方案**:
  1. **方案 A（推荐）**: 在 `_audio_loop` 中，确保 PyAudio 的 `terminate()` 不在主线程调用
  2. **方案 B**: 使用 `multiprocessing` 替代 `threading` 做音频采集，彻底隔离 PyAudio 和 tkinter
  3. **方案 C**: 在打开 PyAudio stream 前，延迟 100ms 再触发 UI 更新（`self.after(100, ...)`）

- **状态**: 🔴 待修复

---

### ERR-010: dual 模式系统音频 Invalid device

- **首次出现**: 2026-05-29 18:18
- **错误信息**: `[Errno -9996] Invalid device`
- **触发条件**: dual 模式下，系统音频 stream 打开失败
- **复现率**: 中（日志中出现 2 次）
- **根因分析**:

  ```
  PyAudioWPatch 获取 loopback 设备 → 设备索引在 PyAudio 实例间不一致
  → stream 打开时设备已失效 → Invalid device
  ```

  日志显示：
  ```
  [18:18:32] Loopback device: 扬声器 (2- Realtek(R) Audio) [Loopback]
  [18:18:32] System stream error: [Errno -9996] Invalid device
  ```

  可能原因：
  1. PyAudio 实例在获取设备信息和打开 stream 之间，设备状态变化
  2. 多个 PyAudio 实例同时存在（麦克风和系统音频各一个 stream）
  3. Windows 音频会话管理冲突

- **修复方案**:
  1. **方案 A（推荐）**: 在 `_audio_loop` 中，先打开所有 stream 再 start，避免设备状态变化窗口期
  2. **方案 B**: 添加重试机制，失败后等待 200ms 重试 3 次
  3. **方案 C**: 在打开 stream 前，先 `p.get_default_output_device_info()` 确认设备可用

- **状态**: 🔴 待修复

---

### ERR-011: dual 模式"打开媒体文件"报错

- **首次出现**: 用户反馈
- **错误信息**: 待确认（可能是 `FileNotFoundError` 或 `PermissionError`）
- **触发条件**: dual 模式录音完成后，点击"打开结果"按钮
- **根因分析**:

  可能原因：
  1. **文件路径问题**: dual 模式生成两个文件（`meeting_xxx.wav` + `meeting_xxx_sys.wav`），
     但 `_on_recorder_save` 回调对每个文件单独调用，导致 file_manager 中有两个独立条目
  2. **结果路径为空**: `_handle_stop_complete` 只传递 `saved_files[0]` 给 `_ask_transcribe_after_record`，
     第二个文件（系统音频）可能没有正确关联 result_path
  3. **文件锁定**: 转写完成后，结果文件可能仍被子进程持有

- **修复方案**:
  1. 确保 dual 模式的两个文件都被正确添加到 file_manager
  2. 修改 `_handle_stop_complete` 处理多个文件的情况
  3. 添加文件存在性检查和错误提示

- **状态**: 🟡 待复现和修复

---

### ERR-012: 录音时 Media Player 打开报错

- **首次出现**: 用户反馈
- **错误信息**: 待确认
- **触发条件**: 录音过程中或录音后，用 Windows Media Player 打开音频文件
- **根因分析**:

  可能原因：
  1. **WASAPI 独占模式**: PyAudioWPatch 使用 WASAPI Loopback 录制系统音频时，
     可能与其他应用的音频会话冲突
  2. **文件格式问题**: 录音保存的 WAV 文件使用 16kHz 单声道 int16 格式，
     但 Media Player 可能期望 44.1kHz/48kHz
  3. **PyAudio 未 terminate**: `unified_recorder.py` 中故意不调用 `p.terminate()`，
     避免干扰系统音频，但这可能导致文件句柄未释放

- **修复方案**:
  1. 在 `_stop_and_save` 完成后，确保所有 PyAudio stream 正确关闭
  2. 添加 `p.terminate()` 调用（在确认所有 stream 关闭后）
  3. 录音完成后延迟 500ms 再允许打开文件

- **状态**: 🟡 待复现和修复

---

## 三、架构现状分析

### 3.1 当前架构图

```
┌─────────────────────────────────────────────────────────────┐
│  主进程 (GUI)                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MeetScribeApp (gui.py, 107KB, ~2700 行)              │   │
│  │  - 窗口布局 (sidebar + home + settings)               │   │
│  │  - 录音控制 (start/stop/pause)                        │   │
│  │  - 文件列表管理 (add/delete/select/refresh)           │   │
│  │  - 转写任务调度 (queue polling)                       │   │
│  │  - AI 摘要/纠错/发言人管理                            │   │
│  │  - 弹窗 (预览/发言人/合并排序)                        │   │
│  │  - 日志/状态栏                                        │   │
│  └──────────────────────────────────────────────────────┘   │
│           │ multiprocessing.Queue (100ms 轮询)               │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  子进程 (transcribe_worker.py)                         │   │
│  │  Transcriber (transcriber.py)                          │   │
│  │  - Stage 1: SenseVoice + VAD (ASR)                     │   │
│  │  - Stage 2: cam++ (说话人分离)                         │   │
│  │  - Stage 3: ct-punc (标点恢复, 后处理)                 │   │
│  │  - ~~可选: emotion2vec (情感识别)~~ [已移除]            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  录音模块 (unified_recorder.py)                        │   │
│  │  - PyAudioWPatch (WASAPI Loopback)                     │   │
│  │  - 后台线程采集音频                                    │   │
│  │  - 支持 mic / system / dual 三种模式                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  其他模块                                              │   │
│  │  - config.py (JSON 配置)                               │   │
│  │  - file_manager.py (文件列表 + 历史)                   │   │
│  │  - ai_service.py (MiMo API + Ollama)                   │   │
│  │  - speaker_namer.py (正则 + LLM 姓名提取)              │   │
│  │  - dual_track_merge.py (双轨合并)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 代码规模统计（2026-06-04 更新）

| 文件 | 行数 | 大小 | 职责 |
|------|------|------|------|
| gui/app.py | ~320 | 13KB | 主窗口 |
| gui/home_page.py | ~800 | 35KB | 主页（使用 FileListView + RecordingBar） |
| gui/sidebar.py | ~110 | 3.5KB | 侧边栏导航 |
| gui/settings_page.py | ~530 | 22KB | 设置页 |
| gui/dialogs.py | ~900 | 35KB | 弹窗组件 |
| gui/voiceprint_page.py | ~620 | 23KB | 音色库管理页 |
| gui/transcription.py | ~570 | 24KB | 转写调度器 |
| gui/file_list_view.py | ~150 | 5KB | 文件列表组件 |
| gui/recording_bar.py | ~100 | 4KB | 录音控制栏 |
| transcriber.py | ~1100 | 42KB | 转写引擎 |
| formatters.py | ~200 | 7KB | 输出格式化器 |
| model_manager.py | ~110 | 4KB | 模型管理器 |
| file_manager.py | ~400 | 14KB | 文件列表管理 |
| speaker_namer.py | ~358 | 14KB | 说话人姓名提取 |
| ai_service.py | ~390 | 17KB | AI 服务 |
| unified_recorder.py | ~420 | 14KB | 录音模块（线程安全） |
| transcribe_worker.py | ~200 | 8KB | 子进程工作函数 |
| dual_track_merge.py | ~100 | 3KB | 双轨合并 |
| config.py | ~110 | 3KB | 配置管理 |
| main.py | ~98 | 3KB | 入口 |
| **总计** | **~6700** | **~280KB** | |

### 3.3 关键问题清单

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | gui.py 单文件 2700 行 | 🔴 高 | 难维护、难测试、容易出错 |
| 2 | dual 模式 SystemError 崩溃 | 🔴 高 | dual 模式不可用 |
| 3 | dual 模式 Invalid device | 🔴 高 | 系统音频录制不稳定 |
| 4 | 100ms 轮询队列 | 🟡 中 | CPU 浪费（~1% idle） |
| 5 | 模型 3 次加载/卸载 | 🟡 中 | 转写速度慢 |
| 6 | 无转写进度条 | 🟡 中 | 用户体验差 |
| 7 | 无快捷键 | 🟡 中 | 操作效率低 |
| 8 | 无单元测试 | 🟡 中 | 回归风险高 |
| 9 | 样式硬编码 | 🟢 低 | 代码可读性差 |
| 10 | 缺少类型注解 | 🟢 低 | IDE 支持弱 |

---

## 四、v3 重构计划

### Phase 1: 修复 Dual 模式 Bug + 虚拟音频设备集成（优先级：P0）

#### 4.1.1 修复 ERR-009: SystemError 崩溃

**问题根因**: PyAudioWPatch 的音频回调与 tkinter 事件循环冲突

**修复方案**:
```python
# unified_recorder.py - _audio_loop 方法修改

def _audio_loop(self):
    """音频采集后台线程"""
    import pyaudiowpatch as pyaudio
    
    p = pyaudio.PyAudio()
    streams = []
    
    try:
        # 打开所有 stream（不立即 start）
        if self._mode in ("mic", "dual"):
            mic_stream = self._open_mic_stream(p)
            if mic_stream:
                streams.append(("mic", mic_stream))
        
        if self._mode in ("system", "dual"):
            sys_stream = self._open_system_stream(p)
            if sys_stream:
                streams.append(("sys", sys_stream))
        
        # 统一启动（减少设备状态变化窗口期）
        for name, stream in streams:
            stream.start_stream()
            logger.info(f"{name} stream started")
        
        # 等待停止信号
        while self._recording:
            time.sleep(0.1)
        
    except Exception as e:
        logger.error(f"Audio loop error: {e}")
    finally:
        # 按顺序关闭 stream
        for name, stream in reversed(streams):
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        
        # 延迟 terminate，避免干扰系统音频
        time.sleep(0.2)
        try:
            p.terminate()
        except Exception:
            pass
```

#### 4.1.2 修复 ERR-010: Invalid device

**修复方案**: 添加重试机制
```python
def _open_stream_with_retry(self, p, max_retries=3, **kwargs):
    """打开 PyAudio stream，失败时重试"""
    for attempt in range(max_retries):
        try:
            stream = p.open(**kwargs)
            return stream
        except Exception as e:
            if "Invalid device" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Stream open failed (attempt {attempt+1}), retrying...")
                time.sleep(0.2)
            else:
                raise
    return None
```

#### 4.1.3 修复 ERR-011: 打开媒体文件报错

**修复方案**: 修改 `_handle_stop_complete` 处理多文件
```python
def _handle_stop_complete(self, saved_files):
    for saved in saved_files:
        self._log(f"录音已保存: {os.path.basename(saved)}")
    
    if saved_files:
        if len(saved_files) == 2:
            self._log("双轨录音完成，转写时将自动合并")
            # 双轨模式：两个文件都添加到列表，但只询问第一个
        self.after(300, lambda: self._ask_transcribe_after_record(saved_files))
```

#### 4.1.4 修复 ERR-012: Media Player 打开报错

**修复方案**: 录音完成后确保资源释放
```python
def _stop_and_save(self):
    """后台线程：等待音频线程退出 → 保存文件 → 回调通知"""
    try:
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=10)
        
        # 等待 PyAudio 资源释放
        time.sleep(0.3)
        
        # 保存文件...
        
    except Exception as e:
        logger.error(f"Error in _stop_and_save: {e}")
```

#### 4.1.5 虚拟音频设备集成（VB-Audio Cable）

**问题**: WASAPI Loopback 关闭时会暂停媒体播放器

**方案**: A - VB-Audio Cable

**技术评估**:
```
优点:
- 性能影响极小（驱动级处理，CPU < 1%）
- 完全隔离音频流，不影响其他应用
- 成熟稳定，社区广泛使用

缺点:
- 需要用户安装驱动（一次性）
- 增加分发复杂度

性能评估:
- CPU 占用: < 1%（与 WASAPI Loopback 相当）
- 内存占用: ~5MB（驱动常驻）
- 延迟: < 10ms（几乎无感）
```

**实施步骤**:
1. 下载 VB-Audio Cable 安装包
2. 修改 unified_recorder.py，使用虚拟音频设备
3. 更新设置页面，添加虚拟音频设备配置选项
4. 测试验证

**状态**: ✅ 已确认

---

### Phase 2: 重构 gui.py（优先级：P0）

#### 4.2.1 目标文件结构

```
src/
├── main.py                    # 入口
├── gui/                       # GUI 模块包
│   ├── __init__.py
│   ├── app.py                 # MeetScribeApp 主窗口 (~300 行)
│   ├── sidebar.py             # 侧边栏导航 (~100 行)
│   ├── home_page.py           # 主页：录音条 + 文件列表 (~800 行)
│   ├── settings_page.py       # 设置页 (~400 行)
│   ├── dialogs.py             # 弹窗：预览/发言人/合并排序 (~500 行)
│   ├── file_list.py           # 文件列表组件 (~300 行)
│   ├── record_bar.py          # 录音控制条 (~200 行)
│   ├── styles.py              # 样式常量 (~100 行)
│   └── handlers.py            # 事件处理器 (~300 行)
├── transcriber/               # 转写引擎模块包
│   ├── __init__.py
│   ├── engine.py              # Transcriber 类 (~400 行)
│   ├── model_manager.py       # ModelManager 类 (~200 行)
│   ├── formatters.py          # 输出格式化器 (~300 行)
│   └── utils.py               # 工具函数 (~100 行)
├── transcribe_worker.py       # 子进程工作函数
├── unified_recorder.py        # 录音模块
├── dual_track_merge.py        # 双轨合并
├── config.py                  # 配置管理
├── file_manager.py            # 文件管理
├── ai_service.py              # AI 服务
└── speaker_namer.py           # 说话人姓名提取
```

#### 4.2.2 拆分步骤

**Step 1: 抽取样式常量** → `gui/styles.py`
```python
# gui/styles.py
"""MeetScribe GUI 样式常量"""

# 颜色
C_BG = "#F3F3F3"
C_SIDEBAR = "#FAFAFA"
C_CARD = "#FFFFFF"
C_BORDER = "#E5E5E5"
C_ACCENT = "#0067C0"
C_SUCCESS = "#0F7B0F"
C_ERROR = "#C42B1C"
# ...

# 字体
FONT_FAMILY = "Segoe UI"

# 布局
SIDEBAR_W = 170
MIN_WINDOW_SIZE = (880, 600)
```

**Step 2: 抽取弹窗** → `gui/dialogs.py`
```python
# gui/dialogs.py
"""MeetScribe 弹窗组件"""

class PreviewDialog(ctk.CTkToplevel):
    """转写结果预览弹窗"""
    def __init__(self, parent, file_path, result_path):
        ...

class SpeakerDialog(ctk.CTkToplevel):
    """发言人管理弹窗"""
    def __init__(self, parent, file_path, speakers):
        ...

class MergeOrderDialog(ctk.CTkToplevel):
    """合并转写排序弹窗"""
    def __init__(self, parent, items):
        ...
```

**Step 3: 抽取文件列表** → `gui/file_list.py`
```python
# gui/file_list.py
"""MeetScribe 文件列表组件"""

class FileListWidget(ctk.CTkScrollableFrame):
    """文件列表组件"""
    def __init__(self, parent, file_manager):
        ...
    
    def refresh(self):
        ...
    
    def _create_row(self, file_item, row_idx):
        ...
```

**Step 4: 抽取录音控制条** → `gui/record_bar.py`
```python
# gui/record_bar.py
"""MeetScribe 录音控制条"""

class RecordBar(ctk.CTkFrame):
    """录音控制条组件"""
    def __init__(self, parent, recorder, config):
        ...
    
    def start(self):
        ...
    
    def stop(self):
        ...
```

**Step 5: 抽取主页** → `gui/home_page.py`
```python
# gui/home_page.py
"""MeetScribe 主页"""

class HomePage(ctk.CTkFrame):
    """主页：录音条 + 文件列表 + 日志"""
    def __init__(self, parent, app):
        self.record_bar = RecordBar(...)
        self.file_list = FileListWidget(...)
        ...
```

**Step 6: 抽取设置页** → `gui/settings_page.py`
```python
# gui/settings_page.py
"""MeetScribe 设置页"""

class SettingsPage(ctk.CTkFrame):
    """设置页"""
    def __init__(self, parent, config):
        ...
```

**Step 7: 重构主窗口** → `gui/app.py`
```python
# gui/app.py
"""MeetScribe 主窗口"""

class MeetScribeApp(ctk.CTk):
    def __init__(self):
        self.config = Config()
        self.file_manager = FileManager()
        self.recorder = UnifiedRecorder(...)
        
        self._build_ui()
    
    def _build_ui(self):
        self.sidebar = Sidebar(self)
        self.home_page = HomePage(self._content, self)
        self.settings_page = SettingsPage(self._content, self.config)
```

---

### Phase 3: 性能优化（优先级：P1）

#### 4.3.1 优化轮询机制

**当前**: `self.after(100, self._poll_transcription_queue)` 每 100ms 轮询

**优化**: 使用 `threading.Event` 通知
```python
# gui/handlers.py
class TranscriptionHandler:
    def __init__(self):
        self._queue = multiprocessing.Queue()
        self._event = threading.Event()
        self._process = None
    
    def start(self, file_paths, fmt, speaker_names, out_dir):
        self._process = multiprocessing.Process(
            target=transcribe_worker_process,
            args=(self._queue, ..., file_paths, fmt, speaker_names, out_dir, ...),
            daemon=True,
        )
        self._process.start()
        # 启动轮询（只在进程运行时轮询）
        self._poll()
    
    def _poll(self):
        """轮询队列，处理消息"""
        try:
            while not self._queue.empty():
                msg = self._queue.get_nowait()
                self._handle_message(msg)
        except Exception:
            pass
        
        # 检查进程状态
        if self._process and self._process.is_alive():
            self._app.after(100, self._poll)
        else:
            self._on_done()
```

#### 4.3.2 优化模型加载

**当前**: `transcribe_staged()` 每次转写加载/卸载模型 3 次

**优化**: 复用已加载的模型实例
```python
# transcriber/engine.py
class Transcriber:
    def __init__(self, ...):
        self._asr_model = None
        self._punc_model = None
        self._models_loaded = False
    
    def _ensure_models_loaded(self):
        """确保模型已加载（复用实例）"""
        if self._models_loaded:
            return
        
        self._asr_model = AutoModel(
            model=sensevoice_path,
            vad_model=vad_path,
            spk_model="cam++",
            device=self.device,
        )
        # ct-punc 单独加载（避免说话人分离退化）
        self._punc_model = AutoModel(
            model=punc_path,
            device=self.device,
        )
        self._models_loaded = True
    
    def transcribe(self, audio_path, ...):
        self._ensure_models_loaded()
        # 使用已加载的模型
        ...
```

#### 4.3.3 添加转写进度条

```python
# gui/home_page.py
class HomePage(ctk.CTkFrame):
    def _build_progress_bar(self):
        """构建进度条"""
        self._progress_frame = ctk.CTkFrame(self, height=4)
        self._progress_bar = ctk.CTkProgressBar(self._progress_frame)
        self._progress_label = ctk.CTkLabel(self, text="")
    
    def _update_progress(self, value, text):
        """更新进度条"""
        self._progress_bar.set(value)
        self._progress_label.configure(text=text)
```

---

### Phase 4: 功能增强（优先级：P2）

#### 4.4.1 添加快捷键

```python
# gui/app.py
def _bind_shortcuts(self):
    """绑定快捷键"""
    self.bind("<F9>", lambda e: self.home_page.record_bar.start())
    self.bind("<F10>", lambda e: self.home_page.record_bar.stop())
    self.bind("<Control-o>", lambda e: self.home_page._add_files())
    self.bind("<Delete>", lambda e: self.home_page._delete_selected())
    self.bind("<Control-a>", lambda e: self.home_page._select_all())
```

#### 4.4.2 添加撤销功能

```python
# gui/undo.py
class UndoManager:
    def __init__(self, max_history=50):
        self._history = []
        self._redo_stack = []
    
    def push(self, action):
        self._history.append(action)
        self._redo_stack.clear()
    
    def undo(self):
        if self._history:
            action = self._history.pop()
            action.undo()
            self._redo_stack.append(action)
    
    def redo(self):
        if self._redo_stack:
            action = self._redo_stack.pop()
            action.redo()
            self._history.append(action)
```

#### 4.4.3 添加单元测试框架

```
tests/
├── __init__.py
├── conftest.py              # pytest fixtures
├── test_config.py           # 配置管理测试
├── test_file_manager.py     # 文件管理测试
├── test_speaker_namer.py    # 说话人姓名提取测试
├── test_dual_track_merge.py # 双轨合并测试
└── test_formatters.py       # 输出格式化测试
```

```python
# tests/conftest.py
import pytest
from config import Config
from file_manager import FileManager

@pytest.fixture
def config(tmp_path):
    return Config(config_path=str(tmp_path / "settings.json"))

@pytest.fixture
def file_manager(tmp_path):
    return FileManager(data_file=str(tmp_path / "file_history.json"))
```

---

## 五、开发规范（继承 v2 + 补充）

### 5.1 模块拆分规范

1. **单一职责**: 每个模块只负责一个功能领域
2. **依赖方向**: `gui/` → `transcriber/` → `utils/`，禁止反向依赖
3. **接口清晰**: 模块间通过明确的接口通信，不直接访问内部实现
4. **向后兼容**: 拆分过程中保持对外接口不变，避免影响其他模块

### 5.2 线程安全规范

1. **tkinter 主线程**: 所有 UI 操作必须在主线程执行
2. **`self.after()`**: 子线程更新 UI 必须通过 `self.after(0, ...)`
3. **PyAudio 回调**: 音频回调中只做数据采集，不触发 UI 更新
4. **multiprocessing**: 子进程通过 Queue 通信，不直接访问主进程内存

### 5.3 错误处理规范

1. **可选功能**: AI 摘要、情感识别等可选功能的异常不能阻断主流程
2. **用户提示**: 错误发生时，必须给用户清晰的提示信息
3. **日志记录**: 所有异常必须记录到日志文件
4. **资源清理**: 使用 `try/finally` 确保资源正确释放

### 5.4 测试规范

1. **核心模块**: config、file_manager、speaker_namer 等核心模块必须有单元测试
2. **边界条件**: 测试必须覆盖正常、异常、边界情况
3. **隔离性**: 测试之间不能相互依赖，每个测试独立运行
4. **覆盖率**: 核心模块测试覆盖率目标 > 80%

---

## 六、实施优先级

### P0 - 必须完成（影响可用性）

| # | 任务 | 预估工时 | 依赖 |
|---|------|---------|------|
| 1 | 修复 ERR-009: dual 模式 SystemError | 2h | 无 |
| 2 | 修复 ERR-010: Invalid device | 1h | 无 |
| 3 | 修复 ERR-011: 打开媒体文件报错 | 1h | 无 |
| 4 | 重构 gui.py → gui/ 包 | 4h | 1-3 |

### P1 - 应该完成（影响性能和质量）

| # | 任务 | 预估工时 | 依赖 |
|---|------|---------|------|
| 5 | 优化轮询机制 | 1h | 4 |
| 6 | 优化模型加载（复用实例） | 2h | 无 |
| 7 | 添加转写进度条 | 1h | 4 |
| 8 | 添加单元测试框架 | 2h | 4 |

### P2 - 可以完成（提升体验）

| # | 任务 | 预估工时 | 依赖 |
|---|------|---------|------|
| 9 | 添加快捷键 | 0.5h | 4 |
| 10 | 添加撤销功能 | 2h | 4 |
| 11 | 样式常量抽取 | 1h | 4 |
| 12 | 添加类型注解 | 2h | 4 |

**总预估工时**: ~19.5h

---

## 七、技术债务清单

| # | 债务 | 影响 | 偿还方式 |
|---|------|------|---------|
| 1 | gui.py 单文件 2700 行 | 难维护 | Phase 2 拆分 |
| 2 | transcribe_diarize.py 重复代码 | 维护成本 | 删除旧版本 |
| 3 | 100ms 轮询 | CPU 浪费 | Phase 3 优化 |
| 4 | 模型 3 次加载 | 速度慢 | Phase 3 优化 |
| 5 | 无类型注解 | IDE 支持弱 | Phase 4 补充 |
| 6 | 无单元测试 | 回归风险 | Phase 4 添加 |
| 7 | 样式硬编码 | 可读性差 | Phase 4 抽取 |
| 8 | PyAudio 未 terminate | 资源泄漏 | Phase 1 修复 |

---

## 八、测试验证清单

### 8.1 Dual 模式测试

- [ ] mic 模式录音正常
- [ ] system 模式录音正常
- [ ] dual 模式录音不崩溃
- [ ] dual 模式两个文件都正确保存
- [ ] dual 模式转写自动合并
- [ ] 录音后 Media Player 能打开文件

### 8.2 转写功能测试

- [ ] 单文件转写正常
- [ ] 批量转写正常
- [ ] 合并转写正常
- [ ] 转写进度条显示正确
- [ ] 转写失败后能重试

### 8.3 AI 功能测试

- [ ] AI 摘要生成正常
- [ ] LLM 纠错正常
- [ ] 发言人姓名提取正常
- [ ] 发言人映射反写正常

### 8.4 UI 测试

- [ ] 快捷键响应正常
- [ ] 文件列表刷新流畅
- [ ] 弹窗打开/关闭正常
- [ ] 窗口缩放布局正常

---

## 九、未来展望（v4+）

### 9.1 音色识别库

- 复用 CAM++ 嵌入向量做声纹比对
- 自动识别已注册的说话人
- 跨会议保持发言人一致性

### 9.2 实时流式转写

- 基于 FunASR streaming 模型
- 录音过程中实时显示转写结果
- 支持实时发言人识别

### 9.3 混合架构

- C# WPF 前端 + Python 后端
- 原生 UI 体验 + AI 生态优势
- 解决打包和杀毒误报问题

### 9.4 多平台支持

- macOS 版本（替换 PyAudioWPatch 为 PortAudio）
- Linux 版本（PulseAudio 录制系统音频）
- 跨平台 UI 框架（Electron / Tauri）

### 9.5 音色库管理页面（v3.1）— 已完成

- 独立的音色库管理页面
- 左右分栏布局（说话人列表 + 详情）
- 支持编辑、删除说话人
- 人工添加音色功能（录音朗读预设文本）
- 集成到侧边栏导航

### 9.6 性能优化（v3.2）— ✅ 已完成

**优化主题**：全盘盘点所有代码和调用，优化使用体验，保证流畅性，减少卡顿

**完成内容**：
- ✅ Phase 1: 性能优化（6 个任务）
  - 文件列表按钮增量更新
  - 文件管理器变更防抖（200ms）
  - FFprobe 异步获取时长
  - 转写结果文件读取移出主线程
  - 轮询间隔自适应（50ms→500ms）
  - 录音按钮即时反馈
- ✅ Phase 2: 代码清理（5 个任务）
  - 删除死代码、统一 spk_id 类型、线程安全锁
  - parse_speakers 拆分、Config 显式属性
- ✅ Phase 3: 适度拆分（4 个任务）
  - 提取 FileListView、RecordingBar、Formatters、ModelManager
- ✅ 审查问题修复（7 个问题）
  - CAM++ 回归、Config 遮蔽、.gitignore、日志降级
  - 组件集成、Formatters 集成、UUID 任务 ID

**测试结果**：147 个测试通过，23 个提交

**设计文档**：`docs/superpowers/specs/2026-06-04-overall-optimization-design.md`
**实施计划**：`docs/superpowers/plans/2026-06-04-overall-optimization.md`

---

*文档结束 — v3 开发时直接读取本文件恢复上下文*
