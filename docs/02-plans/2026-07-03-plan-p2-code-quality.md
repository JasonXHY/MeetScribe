# P2 代码质量改进方案

> 日期：2026-07-03
> 目的：逐项制定 P2 问题的修改方案，供 Qoder 审核确认后再实施
> 原则：每个改动都必须是低风险、行为不变的纯重构或防御性增强

---

## P2-1：ModelDownloadWorker 重复定义

### 当前代码

**settings_page.py:25-41**：
```python
class ModelDownloadWorker(QThread):
    finished = Signal(bool, str)
    progress = Signal(int, str)

    def __init__(self, model_manager, parent=None):
        super().__init__(parent)
        self._model_manager = model_manager

    def run(self):
        def _cb(msg):
            self.progress.emit(0, str(msg))
        success, msg = self._model_manager.download_all_missing(progress_callback=_cb)
        self.finished.emit(success, msg)
```

**first_launch.py:29-53**：
```python
class ModelDownloadWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, cache_dir):
        super().__init__()
        self._cache_dir = cache_dir

    def run(self):
        from transcriber import ModelManager
        manager = ModelManager(self._cache_dir)
        self.progress.emit(0, "正在检查模型...")
        success, message = manager.download_all_missing(progress_callback=_cb)
        self.progress.emit(100 if success else 0, message)
        self.finished.emit(success, message)
```

### 修改方案

创建 `src/gui/workers.py`，统一为一个类：

```python
# src/gui/workers.py
class ModelDownloadWorker(QThread):
    """模型下载工作线程"""
    finished = Signal(bool, str)
    progress = Signal(int, str)

    def __init__(self, model_manager, parent=None):
        super().__init__(parent)
        self._model_manager = model_manager

    def run(self):
        try:
            def _cb(msg):
                self.progress.emit(0, str(msg))
            self.progress.emit(0, "正在检查模型...")
            success, msg = self._model_manager.download_all_missing(progress_callback=_cb)
            self.progress.emit(100 if success else 0, msg)
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))
```

**settings_page.py**：删除 `ModelDownloadWorker` 类（line 25-41），改为 `from gui.workers import ModelDownloadWorker`。调用方式不变。

**first_launch.py**：删除 `ModelDownloadWorker` 类（line 29-53），改为 `from gui.workers import ModelDownloadWorker`。调用方式需要适配：
```python
# first_launch.py 中原来：
worker = ModelDownloadWorker(cache_dir)
# 改为：
from transcriber import ModelManager
manager = ModelManager(cache_dir)
worker = ModelDownloadWorker(manager)
```

### 风险评估

- **行为变化**：无。只是把两个类合并为一个，接口统一为接受 `model_manager` 对象
- **影响范围**：settings_page + first_launch 两处调用
- **测试覆盖**：现有的 model_registry 测试可验证

---

## P2-2：组件间深层属性链耦合

### 当前代码

voiceprint_page.py 两处跨 3 层访问：
```python
# line 793
self._app._home_page._log(f"已重命名说话人: {old_name} -> {new_name}")
# line 817
self._app._home_page._log(f"已删除说话人: {speaker_name}")
```

home_page.py 11 处跨 2 层访问：
```python
# 11 处类似：
handler = self._app._transcription_handler
```

### 修改方案

**app.py** 添加公共接口方法：
```python
def log_message(self, msg):
    """公共日志方法，供子页面调用"""
    if hasattr(self, '_home_page') and self._home_page:
        self._home_page._log(msg)

@property
def transcription_handler(self):
    """公共属性，供 home_page 调用"""
    return self._transcription_handler
```

**voiceprint_page.py**：两处改为 `self._app.log_message(...)`

**home_page.py**：11 处 `self._app._transcription_handler` 改为 `self._app.transcription_handler`

### 风险评估

- **行为变化**：无。只是添加了中间层，调用链不变
- **影响范围**：voiceprint_page 2 处 + home_page 11 处
- **测试覆盖**：现有 GUI 测试可验证

---

## P2-3：apply_speaker_mapping 中文 ID 替换

### 当前代码

utils.py:59-61：
```python
if key_str.startswith("本地-") or key_str.startswith("远程-"):
    content = content.replace(key_str, name)
```

### 修改方案

```python
if key_str.startswith("本地-") or key_str.startswith("远程-"):
    content = re.sub(rf'(?<!\w){re.escape(key_str)}(?!\w)', name, content)
```

### 风险评估

- **行为变化**：极小。原始 `replace()` 会替换所有出现位置（包括文本内容中的），正则加了词边界后更精确
- **实际影响**：转写文本中包含 `本地-0` 这种精确格式的概率极低
- **测试覆盖**：现有 `TestDualTrackPairChineseSuffix` 测试可验证

---

## P2-4：设置保存时不验证路径

### 当前代码

settings_page.py:794-795：
```python
self._config.set("recording_dir", self._rec_dir_entry.text(), save=False)
self._config.set("transcript_dir", self._out_dir_entry.text(), save=False)
```

### 修改方案

在 `_on_save()` 开头添加路径校验：
```python
# 校验路径有效性
rec_dir = self._rec_dir_entry.text().strip()
out_dir = self._out_dir_entry.text().strip()

if not rec_dir:
    QMessageBox.warning(self, "错误", "录音目录不能为空")
    return
if not out_dir:
    QMessageBox.warning(self, "错误", "转写目录不能为空")
    return

# 尝试创建目录（验证可写性）
for dir_path, label in [(rec_dir, "录音目录"), (out_dir, "转写目录")]:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except OSError as e:
        QMessageBox.warning(self, "错误", f"{label}无效: {e}")
        return
```

### 风险评估

- **行为变化**：新增校验，无效路径会被拦截并提示用户
- **影响范围**：仅 `_on_save()` 入口
- **向后兼容**：有效路径不受影响

---

## P2-5：录音中关闭窗口无确认对话框

### 当前代码

app.py:530-549：
```python
def closeEvent(self, event):
    if self._recording:
        self.recorder.stop()
    # ... 保存配置 ...
    event.accept()
```

### 修改方案

```python
def closeEvent(self, event):
    if self._recording:
        reply = QMessageBox.question(
            self, "确认退出",
            "正在录音中，确定要退出吗？未保存的录音将丢失。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            event.ignore()
            return
        self.recorder.stop()
    # ... 保存配置 ...
    event.accept()
```

### 风险评估

- **行为变化**：录音中关闭窗口会弹出确认框，用户可选择取消
- **影响范围**：仅 closeEvent
- **向后兼容**：非录音状态不受影响

---

## P2-6：_delete_source_file 无路径校验

### 当前代码

file_manager.py:230-243：
```python
def _delete_source_file(self, item):
    paths = list(item.source_files) if item.source_files else [item.file_path]
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
```

### 修改方案

```python
def _delete_source_file(self, item):
    """删除条目对应的磁盘源文件，带路径安全校验。"""
    # 安全校验：只允许删除已知数据目录下的文件
    from utils import get_data_dir
    allowed_prefixes = [
        os.path.normpath(get_data_dir()),
        os.path.normpath(os.path.join(get_data_dir(), "recordings")),
        os.path.normpath(os.path.join(get_data_dir(), "transcripts")),
    ]

    paths = list(item.source_files) if item.source_files else [item.file_path]
    for path in paths:
        try:
            if not path:
                continue
            norm_path = os.path.normpath(path)
            if not any(norm_path.startswith(p) for p in allowed_prefixes):
                logger.warning(f"Path validation failed, skip delete: {path}")
                continue
            if os.path.exists(norm_path):
                os.remove(norm_path)
                logger.info(f"Source file deleted: {path}")
            else:
                logger.warning(f"Source file not found, skip delete: {path}")
        except OSError as e:
            logger.warning(f"Failed to delete source file {path}: {e}")
```

### 风险评估

- **行为变化**：新增路径白名单校验，不在白名单内的文件不会被删除
- **影响范围**：仅 `_delete_source_file()`
- **向后兼容**：正常数据目录下的文件不受影响
- **安全提升**：防止 JSON 被篡改后删除任意文件

---

## P2-11：SpeakerDialog 重复创建 VoiceprintLibrary

### 当前代码

dialogs.py 4 处各创建一个 `VoiceprintLibrary()`：
- line 786：`library = self._get_library()`（已封装）
- line 921：`library = VoiceprintLibrary()`
- line 955：`library = VoiceprintLibrary()`
- line 1120：`library = VoiceprintLibrary()`

voiceprint_page.py 的 `_get_library()` 已有缓存机制。

### 修改方案

在 `SpeakerDialog.__init__` 中缓存实例：
```python
def __init__(self, ...):
    # ... 现有初始化 ...
    self._library = None  # 延迟初始化

def _get_library(self):
    """获取声纹库实例（缓存）"""
    if self._library is None:
        from voiceprint import VoiceprintLibrary
        self._library = VoiceprintLibrary()
    return self._library
```

4 处 `VoiceprintLibrary()` 调用改为 `self._get_library()`。

### 风险评估

- **行为变化**：无。只是缓存实例避免重复创建
- **影响范围**：SpeakerDialog 内部
- **性能提升**：减少 4-5 次 JSON 文件读取

---

## P2-12：后台下载 Worker 无 closeEvent 清理

### 当前代码

app.py:530-549 closeEvent 中无 `_bg_download_worker` 处理。

### 修改方案

在 closeEvent 的 `try` 块中添加：
```python
# 停止后台下载 Worker
if hasattr(self, '_bg_download_worker') and self._bg_download_worker:
    try:
        self._bg_download_worker.quit()
        self._bg_download_worker.wait(3000)  # 最多等 3 秒
    except Exception:
        pass
    self._bg_download_worker = None
```

### 风险评估

- **行为变化**：关闭窗口时终止后台下载线程
- **影响范围**：仅 closeEvent
- **向后兼容**：无后台下载时不触发

---

## 实施优先级

| 优先级 | 编号 | 改动量 | 风险 |
|--------|------|--------|------|
| 1 | P2-12 | +5 行 | 低（防止崩溃） |
| 2 | P2-6 | +8 行 | 低（安全增强） |
| 3 | P2-5 | +8 行 | 低（用户体验） |
| 4 | P2-4 | +10 行 | 低（输入校验） |
| 5 | P2-11 | +6 行 | 极低（缓存优化） |
| 6 | P2-1 | ~30 行 | 低（重构） |
| 7 | P2-2 | ~15 行 | 低（重构） |
| 8 | P2-3 | 1 行 | 极低（正则替换） |

**总改动量**：约 80 行代码，全部是低风险的防御性增强或重构。


---

## Qoder 审核意见 2026-07-03

### P2-1：ModelDownloadWorker 重复定义 — 通过，有一处细节需补充

方案整体可行。两个类的接口差异（model_manager vs cache_dir）已在方案中处理，first_launch.py 的适配代码正确。

补充：统一后的 `run()` 加了 try/except 包裹，这是好的改进。但 first_launch.py 原版（line 43-53）已经有 try/except 了，settings_page.py 原版反而没有。合并后统一有 try/except，行为对齐，没问题。

**结论：通过。**

---

### P2-2：组件间深层属性链耦合 — 通过，数据有小误差

方案中 home_page.py 的 `self._app._transcription_handler` 出现次数写的是 11 处，实际核查为 **9 处**（lines 355, 702, 857, 868, 875, 882, 889, 896, 931），另有 7 处 `hasattr` 守卫检查。改动量从 11 改为 9，不影响方案可行性。

另外，voiceprint_page.py 中 `self._app._home_page._log()` 的调用，其实可以直接改为 `self._app._log()`——app.py line 360 已经有 `_log` 方法。不过方案中新增 `log_message()` 作为公共接口更规范，两种方式都可以。

**结论：通过，改数字 11 → 9。**

---

### P2-3：apply_speaker_mapping 中文 ID 替换 — 方案有 bug，需要修改

方案提出的正则 `(?<!\w){re.escape(key_str)}(?!\w)` **在 Python 3 中不生效**。原因：Python 3 的 `\w` 默认包含 Unicode 字符（含中文），`本`、`地`、`远`、`程` 都是 `\w` 字符。所以 `(?<!\w)` 在 "本地-1" 前面如果是中文（如 "我的本地-1"），lookbehind 会匹配到中文字符 `\w`，导致断言失败、替换不会执行。

**正确做法**：用显式的分隔符边界代替 `\w` 边界：

```python
# 方案 A：用显式分隔符 lookahead/lookbehind
content = re.sub(
    rf'(?<=[\s\[,，。：:]|^){re.escape(key_str)}(?=[\s\]，,。：:]|$)',
    name, content
)

# 方案 B（更简单）：只匹配作为独立 token 出现的模式
content = re.sub(rf'(?<!\S){re.escape(key_str)}(?!\S)', name, content)
```

方案 B 用 `(?<!\S)` 和 `(?!\S)` 等价于要求前后是空白或字符串边界，更简单可靠。

**结论：方案需修改正则为方案 B 后再实施。**

---

### P2-4：设置保存时不验证路径 — 通过，建议增加"目录不存在"提示

`os.makedirs(dir_path, exist_ok=True)` 的行为与 app.py line 129 启动时的逻辑一致，不会引入新问题。

建议：如果用户输入了一个不存在的路径（比如拼写错误 `D:\recodings`），`makedirs` 会静默创建它。建议在创建前检查是否存在，不存在时给用户一个确认提示："目录不存在，是否创建？"，避免拼写错误后静默创建了一个空目录。

**结论：通过，建议增加目录不存在时的确认提示。**

---

### P2-5：录音中关闭窗口无确认对话框 — 需补充转写中检查

两个问题：

1. **QMessageBox 未导入**：app.py 的 import 块（lines 10-13）没有 QMessageBox，需要加上。

2. **只检查了 `_recording`，遗漏了转写中状态**：`TranscriptionHandler` 有 `is_transcribing` 属性（transcription.py lines 69-71），转写进行中关闭窗口同样会丢失结果。closeEvent 应同时检查两种状态：

```python
def closeEvent(self, event):
    busy_reasons = []
    if self._recording:
        busy_reasons.append("正在录音中")
    if (hasattr(self, '_transcription_handler')
            and self._transcription_handler
            and self._transcription_handler.is_transcribing):
        busy_reasons.append("正在转写中")

    if busy_reasons:
        reply = QMessageBox.question(
            self, "确认退出",
            "，".join(busy_reasons) + "，确定要退出吗？未保存的数据将丢失。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            event.ignore()
            return

    # ... 原有清理逻辑 ...
    event.accept()
```

**结论：方案需补充转写中检查后再实施。**

---

### P2-6：_delete_source_file 无路径校验 — 白名单方案有缺陷，需重新设计

**核心问题**：白名单用 `get_data_dir()` 作为前缀，但 `recording_dir` 是用户可配置的（settings_page.py line 794），用户可以设为任意路径如 `D:\my_recordings`。此时文件的实际路径不在 `get_data_dir()` 下，白名单会**阻止合法删除**。

此外，用户还可以通过 UI 手动添加文件，这些文件路径也可能在任意位置。

**建议方案**：不用固定白名单，改为从 config 中读取当前配置的 recording_dir 和 transcript_dir 作为允许前缀：

```python
def _delete_source_file(self, item):
    """删除源文件，带路径安全校验。"""
    # 从 config 读取当前配置的目录
    rec_dir = os.path.normpath(self._config.get("recording_dir", ""))
    trans_dir = os.path.normpath(self._config.get("transcript_dir", ""))
    allowed_prefixes = [p for p in [rec_dir, trans_dir] if p]

    # 兜底：至少允许 get_data_dir() 下的文件
    data_dir = os.path.normpath(get_data_dir())
    allowed_prefixes.append(data_dir)

    paths = list(item.source_files) if item.source_files else [item.file_path]
    for path in paths:
        if not path:
            continue
        norm_path = os.path.normpath(path)
        if not any(norm_path.startswith(p) for p in allowed_prefixes):
            logger.warning(f"Path outside allowed dirs, skip delete: {path}")
            continue
        # ... 后续删除逻辑不变 ...
```

**结论：方案需修改白名单逻辑后再实施。**

---

### P2-11：SpeakerDialog 重复创建 VoiceprintLibrary — 通过，需注意缓存一致性

方案可行。每次 `VoiceprintLibrary()` 都会触发 `_ensure_loaded()` 从磁盘读取 JSON，4 次实例化 = 4 次磁盘读取。缓存后只读 1 次。

需要注意：当前每次新建实例都能读到磁盘上的最新数据（包括其他对话框写入的变更）。缓存后，如果在一个对话框中修改了声纹库，另一个对话框的缓存实例不会自动感知。不过 SpeakerDialog 是模态对话框，同一时间只有一个实例，所以这个问题实际不存在。

**结论：通过。**

---

### P2-12：后台下载 Worker 无 closeEvent 清理 — 需补充，且遗漏了其他线程

两个问题：

1. **`quit()` 无法中断阻塞下载**：ModelDownloadWorker 的 `run()` 中 `download_all_missing()` 是同步阻塞调用。`quit()` 只影响 Qt 事件循环，对阻塞的 `run()` 无效。应使用 `requestInterruption()` + `wait(timeout)`，但前提是下载代码内部需要周期性检查 `isInterruptionRequested()`。如果下载代码不支持中断检查，至少做到 `requestInterruption()` + `wait(3000)` + 日志记录。

2. **遗漏了更重要的线程清理**：closeEvent 中还有以下线程未清理：
   - `_transcription_handler`：有 `stop_transcription()` 方法（transcription.py line 1199），但 closeEvent 从未调用。转写进行中关闭窗口，转写线程会继续跑。
   - `_transcription_handler._active_workers`：AICorrectionWorker / AISummaryWorker 等 QThread，也未清理。

建议扩大 closeEvent 清理范围：

```python
def closeEvent(self, event):
    # ... 确认对话框（P2-5）...

    try:
        # 停止录音
        if self._recording:
            self.recorder.stop()

        # 停止转写
        if (hasattr(self, '_transcription_handler')
                and self._transcription_handler):
            self._transcription_handler.stop_transcription()

        # 停止后台下载
        if hasattr(self, '_bg_download_worker') and self._bg_download_worker:
            self._bg_download_worker.requestInterruption()
            self._bg_download_worker.wait(3000)
            self._bg_download_worker = None

        # ... 保存配置、文件历史等原有逻辑 ...
    except Exception as e:
        logger.debug(f"Cleanup error: {e}")
    event.accept()
```

**结论：方案需补充转写线程清理，并将 `quit()` 改为 `requestInterruption()` + `wait()`。**

---

### 审核汇总

| 编号 | 结论 | 需修改项 |
|------|------|----------|
| P2-1 | 通过 | 无 |
| P2-2 | 通过 | 数字 11 → 9 |
| P2-3 | **需修改** | 正则在 Python 3 中对中文无效，改用 `(?<!\S)..(?!\S)` |
| P2-4 | 通过 | 建议增加目录不存在确认 |
| P2-5 | **需修改** | 补充转写中检查 + 导入 QMessageBox |
| P2-6 | **需修改** | 白名单应读取 config 中的用户配置目录 |
| P2-11 | 通过 | 无 |
| P2-12 | **需修改** | quit() → requestInterruption()，补充转写线程清理 |

8 项中 4 项通过，4 项需修改后实施。
