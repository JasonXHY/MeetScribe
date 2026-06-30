# MeetScribe v1.0 代码审查报告（终版）

> 审查日期：2026-06-27
> 审查范围：C:\侧耳倾听 全部源代码
> 审查方式：每项问题均通过实际读取上下文代码（30+ 行）验证，并对比老版代码（C:\MeetScribe）确认可复用修复
> 审查人：Qoder

---

## 一、审查总结

| 等级 | 数量 | 说明 |
|------|------|------|
| P1 严重 | 10 | 功能性 Bug，影响核心流程 |
| P2 中等 | 12 | 代码质量、健壮性问题 |
| P3 低 | 10 | 用户体验、可维护性改进 |
| 架构优化 | 4 | 中长期改进方向 |

**整体评价**：架构设计合理（四层分离 + 多进程转写），核心转写流水线质量较高。新版在模型下载（并发锁、重试、超时）和线程安全（Signal/Slot）方面已优于老版。主要问题集中在多线程回调安全、属性缺失导致的运行时崩溃、以及模型注册表兼容性。

**老版代码对比结论**：`unified_recorder.py` 和 `voiceprint_page.py` 两版逐字节一致，无修复可复用。唯一可复用的是老版 `config.py` 中 5 个缺失的默认配置键（见第十一节）。

---

## 二、P1 严重问题

### P1-1：录音状态回调从后台线程直接操作 GUI

**文件**：`src/gui/app.py` 第 378-384 行
**代码现状**：`_on_recorder_state_change` 被 `UnifiedRecorder._stop_and_save`（后台线程）直接调用，内部执行 `recording_bar.update_state()` 操作 QWidget 属性。`_on_recorder_stop_complete` 已正确使用 Signal（第 390-392 行），`_on_recorder_save` 仅做日志无线程问题。

**修复方案**：为 `on_state_change` 创建 Qt Signal，回调中 emit 而非直接操作 GUI：
```python
# app.py 增加 Signal
state_change_signal = Signal(bool, bool)
# __init__ 中连接
self.state_change_signal.connect(self.recording_bar.update_state)
# 回调改为
recorder.on_state_change = lambda r, p: self.state_change_signal.emit(r, p)
```

---

### P1-2：AddVoiceDialog 缺少 _voiceprint_lib 和 _temp_embedding 初始化

**文件**：`src/gui/voiceprint_page.py` 第 61-75 行（__init__）、第 248 行（使用处）
**代码现状**：`__init__` 未初始化 `self._voiceprint_lib`，第 248 行 `AudioProcessWorker(self._audio_path, self._voiceprint_lib, self)` 必然 AttributeError。同时 `__init__` 设置 `self._embedding = None` 但代码实际使用 `self._temp_embedding`（死代码）。

**修复方案**：在 `AddVoiceDialog.__init__` 中添加：
```python
self._voiceprint_lib = VoiceprintLibrary()
self._temp_embedding = None
self._temp_audio_path = None
```

---

### P1-3：_on_done 防护变量未生效

**文件**：`src/gui/transcription.py` 第 295-332 行
**代码现状**：`_done_called` 在第 57 行和第 136 行被初始化为 False，`_poll` 第 197 行检查了该变量，但 `_on_done()` 内部从未将其设为 True。当进程死亡检测和队列 "done" 消息同时到达时，`_on_done` 被调用两次。

**修复方案**：在 `_on_done()` 方法首行添加：
```python
if self._done_called:
    return
self._done_called = True
```

---

### P1-4：模型注册表大小写不匹配导致百川和 MiniMax 不可用

**文件**：`src/ai_service.py` 第 75 行、`src/model_registry.py` 第 140-161 行
**代码现状**：`_resolve_base_url()` 做 `self.model.lower()`，但注册表中 `"Baichuan-M3-Plus"`、`"Baichuan-M3"`、`"MiniMax-M3"` 使用混合大小写。`get_base_url` 用 `.get(model)` 精确匹配，导致这三个模型的 base_url 返回空字符串，API 调用完全失败。

**修复方案**：注册表中所有模型 key 统一为小写：
```python
"baichuan-m3-plus": { ... },
"baichuan-m3": { ... },
"minimax-m3": { ... },
```
同时在 `get_base_url` 内部对传入的 model 做 `.lower()` 确保匹配。

---

### P1-5：_safe_model_path 临时目录泄漏

**文件**：`src/transcriber.py` 第 422-445 行
**代码现状**：`_safe_model_path()` 用 `tempfile.mkdtemp(prefix="ms_model_")` 创建临时目录并复制完整模型文件，但全文件无 `shutil.rmtree` 调用。中文 Windows 路径下每次转写泄漏数百 MB 临时目录。

**修复方案**：在 `Transcriber` 类中记录临时目录路径，转写完成后清理：
```python
# __init__ 中
self._temp_model_dirs = []
# _safe_model_path 返回后
self._temp_model_dirs.append(os.path.dirname(sensevoice_path))
# 转写完成或 atexit 中
for d in self._temp_model_dirs:
    shutil.rmtree(d, ignore_errors=True)
```

---

### P1-6：SpeakerDialog 保存说话人时模型推理阻塞 GUI 线程

**文件**：`src/gui/dialogs.py` 第 551、578-590、673-730 行
**代码现状**：按钮点击 → `_save_to_library` → `_extract_middle_segment_embedding`，同步执行 `from funasr import AutoModel` + `AutoModel(model="cam++")` + `model.inference()`，全部在 GUI 主线程。加载模型 + CPU 推理可冻结界面 10 秒以上。

**修复方案**：将推理移入 QThread：
```python
class EmbeddingWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    def __init__(self, audio_path, spk_id):
        super().__init__()
        self._audio_path = audio_path
        self._spk_id = spk_id
    def run(self):
        try:
            emb = self._extract(self._audio_path, self._spk_id)
            self.finished.emit(emb)
        except Exception as e:
            self.error.emit(str(e))
```

---

### P1-7：ModelDownloadWorker parent 为设置页，页面销毁时崩溃风险

**文件**：`src/gui/settings_page.py` 第 684 行
**代码现状**：`ModelDownloadWorker(self._model_manager, self)` 以 SettingsPage 为 parent。模型下载耗时长，若用户切换页面或关闭窗口导致 SettingsPage 销毁，QThread 仍在运行，Qt 销毁带活跃子线程的 QObject 会崩溃。

**修复方案**：parent 改为主窗口或 QApplication，同时在 closeEvent 中安全终止下载：
```python
self._download_worker = ModelDownloadWorker(self._model_manager, self.window())
```

---

### P1-8：file_list_view_new.py 死代码，含缺失导入

**文件**：`src/gui/file_list_view_new.py` 第 20-24 行（导入）、第 247 行（调用）
**代码现状**：未导入 `icon_stop` 但第 247 行调用了 `icon_stop()`；缺少 `get_selected()` 方法（`home_page.py` 调用了该方法）。当前 `home_page.py` 导入的是 `file_list_view`（非 `_new`），文件未被使用。

**修复方案**：直接删除 `file_list_view_new.py`。

---

### P1-9：me.spec 硬编码绝对路径

**文件**：`me.spec` 第 8 行
**代码现状**：`ROOT = r"C:/侧耳倾听"` 字面绝对路径，其他机器或目录无法构建。老版也是硬编码 `C:/MeetScribe`。

**修复方案**：
```python
ROOT = os.path.dirname(os.path.abspath(SPECPATH))
```

---

### P1-10：日志文件无轮转

**文件**：`src/main.py` 第 44-48 行
**代码现状**：`logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")` 无大小限制，全项目零出现 `RotatingFileHandler`。DEBUG 级别日志无限追加。

**修复方案**：
```python
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(LOG_FILE, encoding="utf-8",
                                    maxBytes=5*1024*1024, backupCount=3)
```

---

## 三、P2 中等问题

### P2-1：ModelDownloadWorker 在两个文件中重复定义

**文件**：`src/gui/settings_page.py` 第 25-40 行、`src/gui/first_launch.py` 第 27-51 行
**代码现状**：两处各定义一个 `ModelDownloadWorker`，构造参数不同（一个接受 `model_manager` 对象，一个接受 `cache_dir` 字符串），信号接口不同（一个有 `progress` 信号，一个没有）。settings_page 版本的进度回调是空操作 `lambda m: None`。

**修复方案**：抽取到独立模块 `src/gui/workers.py`，统一为一个 Worker 类。

---

### P2-2：组件间深层属性链耦合

**文件**：`src/gui/voiceprint_page.py` 第 788-789、812-813 行；`src/gui/home_page.py` 11 处
**代码现状**：voiceprint_page 通过 `self._app._home_page._log()` 跨 3 层访问；home_page 在 11 处通过 `self._app._transcription_handler` 跨 2 层访问私有属性。

**修复方案**：短期在 app.py 提供公共接口方法（如 `app.log_message()`、`app.transcription_handler`），中期引入 EventBus。

---

### P2-3：apply_speaker_mapping 中文 ID 分支使用原始替换

**文件**：`src/utils.py` 第 45-62 行
**代码现状**：`Speaker N` 分支已正确使用正则词边界，但中文 ID 分支（`本地-0`、`远程-1`）使用 `content.replace(str(spk_id), name)` 原始替换。

**修复方案**：中文 ID 分支也改用正则：`re.sub(rf'(?<!\w){re.escape(spk_id)}(?!\w)', name, content)`。

---

### P2-4：设置保存时不验证路径

**文件**：`src/gui/settings_page.py` 第 754-799 行（_on_save 方法）
**代码现状**：录音目录和转写目录直接 `config.set()` 保存，无 `os.path.exists()`、无空值检查、无可写性验证。

**修复方案**：保存前检查路径有效性，无效则提示用户。

---

### P2-5：录音中关闭窗口无确认对话框

**文件**：`src/gui/app.py` 第 514-533 行（closeEvent）
**代码现状**：`if self._recording: self.recorder.stop()` 后直接 `event.accept()`，无 QMessageBox 确认。

**修复方案**：录音中弹出确认对话框，选择"否"则 `event.ignore()`。

---

### P2-6：_delete_source_file 无路径校验

**文件**：`src/file_manager.py` 第 230-243 行
**代码现状**：从 `file_history.json` 读取路径直接 `os.remove()`，不检查路径是否在 `recording_dir` 或 `transcript_dir` 下。JSON 损坏时可能删除任意文件。

**修复方案**：添加路径前缀校验，只允许删除已知数据目录下的文件。

---

### P2-7：设置页 ComboBox 和标签固定宽度

**文件**：`src/gui/settings_page.py`
**代码现状**：8 个 ComboBox 全部 `setFixedWidth(200)`，`_form_row` 中标签 `setFixedWidth(100)`。长文本如 `"ernie-4.5-turbo-128k-preview"` 被裁切。

**修复方案**：改用 `setMinimumWidth`，或根据内容自适应。

---

### P2-8：录音设备拔出无恢复机制

**文件**：`src/unified_recorder.py` 第 257-314 行（_audio_loop）
**代码现状**：stream 打开一次后 `while self._recording: time.sleep(0.1)` 等待，无设备丢失检测。设备拔出时 callback 报错，录音静默中断，用户无感知。

**修复方案**：在 `_audio_loop` 中添加 stream 健康检查，设备丢失时通知用户。

---

### P2-9：转写队列无持久化

**文件**：`src/transcription_queue.py`（全文 134 行）
**代码现状**：`self._queue` 和 `self._history` 均为纯 Python list，无 JSON 文件读写，无序列化。程序崩溃后所有排队任务丢失。

**修复方案**：队列状态定期写入 JSON 文件，启动时恢复。

---

### P2-10：模型下载无真实进度显示

**文件**：`src/gui/first_launch.py` 第 37-51 行
**代码现状**：`ModelDownloadWorker.run()` 进度回调始终 emit `0`（`self.progress.emit(0, str(msg))`），UI 进度条全程 `setRange(0, 0)` 不确定模式。`_on_progress` 中 `if percent > 0` 永远不触发。

**修复方案**：短期改为文字提示 "正在下载 2/4: SenseVoice (~900MB)"；长期封装 SDK 下载过程获取字节级进度。

---

### P2-11：SpeakerDialog 重复创建 VoiceprintLibrary

**文件**：`src/gui/dialogs.py` 第 481、601、632、789 行
**代码现状**：4 个方法中各自 `VoiceprintLibrary()` 创建新实例。`_refresh_speaker_list` 中还会对每个说话人调用一次 `_add_match_suggestion`（内部又创建实例）。5 个说话人 = 6 次实例化。

**修复方案**：`SpeakerDialog.__init__` 中缓存 `self._library = VoiceprintLibrary()`。

---

### P2-12：后台下载 Worker 无 closeEvent 清理

**文件**：`src/gui/app.py` 第 264-306 行
**代码现状**：`ModelDownloadWorker` 无 Qt parent（`super().__init__()` 无参），生命周期依赖 `self._bg_download_worker` Python 引用。关闭窗口时 `closeEvent` 未检查/终止该 Worker，线程可能在窗口销毁后 emit 信号访问已销毁的 C++ 对象。

**修复方案**：closeEvent 中检查 `_bg_download_worker`，调用 `worker.quit()` + `worker.wait()`。

---

## 四、P3 低优先级问题

| 编号 | 问题 | 文件 | 现状 | 修复建议 |
|------|------|------|------|----------|
| P3-1 | 无国际化支持 | 全部 GUI 文件 | 零 tr()/QTranslator 调用，全中文硬编码 | 短期不处理，新增代码用 tr() |
| P3-2 | 无键盘快捷键 | 全部 GUI 文件 | 零 QShortcut/QKeySequence | 核心操作添加 QShortcut |
| P3-3 | 无可访问性支持 | 全部 GUI 文件 | 零 accessibleName/Description | 关键控件添加 accessibleName |
| P3-4 | 图标无缓存 | `src/gui/icons.py` | create_icon 每次重建 SVG/Pixmap | 添加 lru_cache |
| P3-5 | HiDPI logo 模糊 | `src/gui/topbar.py` 第 52 行 | `scaled(22, 22)` 无 devicePixelRatio | 使用 devicePixelRatio 适配 |
| P3-6 | StatusBar 引擎名硬编码 | `src/gui/app.py` 第 206 行 | 固定 "SenseVoice + CAM++ + ct-punc" | 读取 config 动态更新 |
| P3-7 | QTimer 无 parent | `src/gui/app.py` 第 239、57 行 | `_safety_timer` 和 `_gui_log_handler._timer` 无 parent | 创建时传入 parent |
| P3-8 | 内测过期日期硬编码 | `src/gui/first_launch.py` 第 110、159 行 | "2026年7月31日" 出现在两处 | 提取为常量 |
| P3-9 | styles.py 路径计算脆弱 | `src/gui/styles.py` 第 11-15 行 | 三层 dirname 依赖文件位置，重复 utils.get_data_dir 逻辑 | 改用 utils.get_data_dir() |
| P3-10 | STATUS_COLORS 重复且不一致 | styles.py 第 34 行、icons.py 第 256 行 | pending 颜色值不同（`#9CA3AF` vs `#D1D5DB`） | 统一到 styles.py，icons.py 导入 |

---

## 五、架构优化建议

### 优化 1：移除 VB-Audio Cable 死代码

`unified_recorder.py` 中 `_find_vb_cable` 方法（第 208-219 行）和 `_open_loopback_stream` 中的 VB-Cable 分支（第 157-169 行）已不再使用（`config.py` 注释 "v1.0: 已移除"），但代码仍存在。删除约 30 行，简化录音分支逻辑。

### 优化 2：引入信号总线解耦组件通信

当前 home_page 在 11 处通过 `self._app._transcription_handler` 访问私有属性，voiceprint_page 通过 `self._app._home_page._log()` 跨 3 层调用。引入 EventBus（QObject + Signal 集合），各组件只依赖 EventBus 通信，消除深层耦合。建议 v1.1 实施。

### 优化 3：文件列表虚拟化

`file_list_view.py` 使用 QTableWidget，所有行同时在内存中。文件数量达数百时可能卡顿。改用 QTableView + QAbstractTableModel 实现虚拟滚动（只渲染可见行）。

### 优化 4：配置系统类型安全

`config.py` 基于 plain dict，`get()` 返回 Any 类型，key 拼写错误静默创建新条目。引入 Pydantic 或 dataclasses 定义 Schema，获得类型检查和默认值验证。

---

## 六、config.py 缺失的默认配置键（从老版复用）

老版 `C:\MeetScribe\src\config.py` 第 35-39 行有以下默认值，新版缺失：

```python
"transcription_engine": "funasr",
"punc_restore": "自动 (ct-punc)",
"garble_filter": "开启 (中文模式)",
"vad_sensitivity": "适中 (推荐)",
"device": "CPU",
```

**影响**：设置页读取这些键时 `config.get()` 返回 None，下拉框初始值可能异常。直接从老版复制即可，工作量 5 分钟。

---

## 七、修复优先级

| 优先级 | 编号 | 描述 | 工作量 |
|--------|------|------|--------|
| **v1.0.1** | P1-1 | `_on_recorder_state_change` 改用 Signal | 0.5h |
| **v1.0.1** | P1-2 | AddVoiceDialog 初始化 `_voiceprint_lib` | 10min |
| **v1.0.1** | P1-3 | `_on_done` 首行加 `_done_called = True` | 5min |
| **v1.0.1** | P1-4 | 注册表 key 统一小写 | 10min |
| **v1.0.1** | P1-9 | me.spec 改用 SPECPATH | 10min |
| **v1.0.1** | 第六节 | config.py 补充 5 个默认键 | 5min |
| **v1.0.2** | P1-5 | 临时目录清理 | 1h |
| **v1.0.2** | P1-6 | 推理移入 QThread | 2h |
| **v1.0.2** | P1-7 | Worker parent 改为主窗口 | 0.5h |
| **v1.0.2** | P1-8 | 删除 file_list_view_new.py | 5min |
| **v1.0.2** | P1-10 | 改用 RotatingFileHandler | 0.5h |
| **v1.1** | P2-* | 12 项代码质量改进 | 各 0.5-2h |
| **v1.1** | 优化1 | 移除 VB-Cable 死代码 | 0.5h |
| **v2.0** | 优化2-4 | 架构级改进 | 各 1-2 天 |
