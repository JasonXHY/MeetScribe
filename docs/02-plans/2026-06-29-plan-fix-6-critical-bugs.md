# 第6次打包后关键问题修复方案

> 日期：2026-06-29
> 来源：用户验收测试 + Qoder 代码审查（2026-06-28 第六节）
> 状态：待用户确认

---

## [S1] 问题概览

### 验收测试发现（5 项，问题 6 已取消）

| # | 问题 | 优先级 | 修复方案 |
|---|------|--------|----------|
| 1 | 首次启动对话框消失 | P0 | config 中加 `app_version` 字段，版本变化时重置 |
| 2+3 | VB-Cable 缺少检测和提示 | P1 | 应用内轻量检测 + 警告回退（不阻止录音） |
| 4 | 转录子进程静默崩溃 | P0 | 开发环境先验证 + 心跳 + 120s 超时 |
| 5 | 停止按钮竞态条件 | P1 | 统一状态管理，消除重复设置 |
| ~~6~~ | ~~config 跨安装残留~~ | ~~P2~~ | ~~取消——与问题 1 冲突，版本检测已覆盖~~ |

### Qoder 审查遗留（2 项）

| # | 问题 | 优先级 | 修复方案 |
|---|------|--------|----------|
| 7 | `transcribe_worker.py` 内联路径 | 低 | 改为 `from utils import get_data_dir` |
| 8 | hiddenimports 缺少模块 | 低 | 补充 gui.transcription, gui.settings_page 等 |

> Qoder 审查中已修复的问题：pause_btn 样式、border-radius 6px、rec_card 最小高度、`_check_models_packaged()` 简化

---

## [S2] 问题 1：首次启动对话框消失（P0）

### 根因
`first_launch=false` 写入 AppData 后跨安装残留。Inno Setup 默认不清理 AppData。

### 方案：config 版本检测
在 config 中增加 `app_version` 字段。应用启动时比较当前版本与 config 中版本，版本变化时重置 `first_launch=True`。

**修改文件**：`src/config.py`, `src/gui/app.py`

**具体改动**：
1. `config.py` DEFAULTS 加 `"first_launch": True, "app_version": ""`
2. `app.py` 启动时检查：
   ```python
   saved_ver = self.config.get("app_version", "")
   if saved_ver != APP_VERSION:
       self.config.set("first_launch", True)
       self.config.set("app_version", APP_VERSION)
       self.config.save()
   ```
3. 首次启动对话框完成时写入 `app_version`

**优点**：重装新版时自动弹出引导，同版本重装不弹出
**缺点**：需要维护 APP_VERSION 常量（已在 `gui/styles.py` 中定义）

---

## [S3] 问题 2+3：VB-Cable 检测和提示（P1）

### 根因
- `first_launch.py` 已有 VB-Cable 文字提示和下载按钮（line 198, 346），但无设备检测
- `unified_recorder.py` 已有 WASAPI Loopback 回退逻辑（line 169），功能正确但无用户提示

### 约束（搜索确认）
- VB-Cable 的 `VBCABLE_Setup_x64.exe` 是自定义安装程序，**不支持任何 CLI 参数**
- 无静默安装方式，GitHub 搜索确认无开源项目集成

### 方案：轻量检测 + 警告回退（不阻止录音）

**核心原则**：当前 WASAPI Loopback 回退是正确行为，不要阻止录音。

#### 3a. 首次启动对话框加轻量检测
在 `first_launch.py` 的 VB-Cable 提示区域加设备检测（不初始化 PyAudio，用轻量方式）：
- 通过 PowerShell 或注册表检查 "CABLE Input" 设备是否存在
- 未安装：显示"未检测到 VB-Audio Cable" + "打开下载页面"按钮
- 已安装：显示"已检测到 VB-Audio Cable ✓"

#### 3b. 设置页 VB-Cable 区域增强
在 `settings_page.py` 的 VB-Cable 复选框旁加状态指示：
- 绿色 ✓ 已安装
- 红色 ✗ 未安装 + "安装指南"链接

#### 3c. 录音前警告回退
在 `unified_recorder.py` 中，VB-Cable 找不到时回退到 WASAPI Loopback，同时弹出警告：
```python
# 当前行为：静默回退
# 改为：回退 + 警告
logger.warning("VB-Cable 未检测到，已切换到 WASAPI Loopback 模式")
# 通过回调通知 UI 显示警告
```
**不抛异常，不阻止录音。**

**修改文件**：`src/gui/first_launch.py`, `src/gui/settings_page.py`, `src/unified_recorder.py`

---

## [S5] 问题 4：转录子进程静默崩溃（P0）

### 根因
FunASR AutoModel 在 C++ 层段错误，Python try/except 无法捕获。子进程被 OS 杀死，主进程只能检测到进程死亡。

### 日志线索
```
17:49:15 [SUBPROCESS] Loading models...
17:49:15 [SUBPROCESS]   model: ...SenseVoiceSmall
17:49:19 [VOICEPRINT] No speaker embeddings received  ← 仅 4 秒，子进程已死
```
模型加载后无 "Models loaded successfully" 日志，说明崩溃发生在 AutoModel 初始化或首次 generate() 调用。

### 方案：心跳 + 超时 + 详细日志

#### 5a. 子进程心跳机制
在 `transcribe_worker.py` 的关键节点发送心跳消息：
```python
# 模型加载前
queue.put(("log", "正在加载模型..."))
# 模型加载后
queue.put(("log", "模型加载完成，开始转写..."))
# 每个文件转写前
queue.put(("status", f"正在转写: {fname}"))
```

#### 5b. 主进程超时检测
在 `transcription.py` 的 `_poll()` 中增加超时检测：
- 记录上次收到消息的时间戳
- 如果距上次心跳超过 **120 秒**，视为异常（模型加载在慢机器上可能需要 30-60 秒）
- 发送 `("error", "转写超时：子进程无响应")` 消息

#### 5c. 增强日志
在 `transcribe_worker.py` 的 try/except 中增加更详细的日志：
```python
except Exception as e:
    import traceback
    queue.put(("error", str(e)))
    queue.put(("log", f"转写失败: {e}\n{traceback.format_exc()}"))
```
当前已有此逻辑，但子进程在 C++ 层崩溃时无法触发。心跳机制可以帮助定位崩溃发生在哪个阶段。

#### 5d. 开发环境验证（必须最先执行）
在开发环境（非打包模式）运行一次完整转录，确认：
- 如果开发环境正常 → 问题出在 PyInstaller 打包的 funasr C++ 扩展
- 如果开发环境也崩溃 → 问题出在 FunASR 版本兼容性或模型文件

**修改文件**：`src/transcribe_worker.py`, `src/transcription.py`

---

## [S6] 问题 5：停止按钮竞态条件（P1）

### 根因
- `_stop_recording()` 检查 `is_transcribing` 后调用 `stop_transcription()`
- 如果子进程在检查和调用之间崩溃，`is_transcribing` 仍为 True
- `_on_done()` 和 `_stop_recording()` 都会操作 stop_btn 样式

### 方案：统一状态管理

#### 6a. stop_transcription() 加防护
```python
def stop_transcription(self, file_path=None):
    if not self._transcribing:
        return
    self._transcribing = False  # 立即置 False，防止重入
    # ... 其余逻辑
```

#### 6b. _on_transcription_done_handler 统一调用 update_state()
在 `home_page.py:565-593` 中，用 `update_state()` 替代手动设置 stop_btn 样式：
```python
def _on_transcription_done_handler(self, success_count, fail_count):
    self._btn_transcribe.setEnabled(True)
    self._btn_transcribe.setText("开始转写")
    self._btn_ai_summary.setEnabled(True)
    self._recording_bar.update_state(recording=False, paused=False)  # 统一状态
    self.refresh_file_list()
    # ... 日志
```

**修改文件**：`src/transcription.py`, `src/gui/home_page.py`

---

## [S7] 修复顺序建议（Qoder 调整后）

| 顺序 | 任务 | 原因 |
|------|------|------|
| 1 | **问题 4d：开发环境验证** | 先确定转录崩溃根因（打包 vs FunASR） |
| 2 | **问题 1：首次启动消失** | P0 + 改动小 |
| 3 | **问题 5：停止按钮竞态** | P1 + 改动小 |
| 4 | **问题 4abc：心跳+超时** | P0 + 需调整超时值 |
| 5 | **问题 2+3：VB-Cable 检测** | P1 + 需轻量检测方案 |
| 6 | **问题 7：内联路径** | 低 + 一行改动 |
| 7 | **问题 8：hiddenimports** | 低 + 打包前补充 |

---

## [S9] 问题 7：transcribe_worker.py 内联路径（低优先级）

### 根因
`transcribe_worker.py:21-25` 内联复制了 `get_data_dir()` 逻辑，而非 import 该函数。当前结果一致，但将来 `get_data_dir()` 修改时可能漏改导致路径不一致。

### 方案：改为 import
```python
# 改前（line 21-25）
if getattr(sys, 'frozen', False):
    _data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'MeetScribe')
else:
    _src_dir = os.path.dirname(os.path.abspath(__file__))
    _data_dir = os.path.dirname(_src_dir)

# 改后
from utils import get_data_dir
_data_dir = get_data_dir()
```

**修改文件**：`src/transcribe_worker.py`

---

## [S10] 问题 8：hiddenimports 缺少模块（低优先级）

### 根因
`me.spec` 的 hiddenimports 中列出了 `gui.first_launch`、`gui.dialogs`、`gui.home_page`，但缺少 `gui.transcription`、`gui.settings_page`、`gui.voiceprint_page`、`gui.topbar`、`gui.recording_bar`、`gui.file_list_view`、`gui.styles`。

### 风险
这些模块目前通过 `app.py` 的直接 import 被 PyInstaller 自动检测到，能正常工作。但如果有条件 import（`try/except`），可能被遗漏导致打包后报 `ModuleNotFoundError`。

### 方案：补充 hiddenimports
在 `me.spec` 的 hiddenimports 列表中补充：
```python
'gui.transcription',
'gui.settings_page',
'gui.voiceprint_page',
'gui.topbar',
'gui.recording_bar',
'gui.file_list_view',
'gui.styles',
'gui.icons',
'formatters',
'speaker_namer',
'ai_service',
```

**修改文件**：`me.spec`

---

## [S10] 验证计划

修复后需验证：
1. 全量测试 `pytest tests/ -v` 通过
2. 开发环境完整转录验证（19 分钟文件）— **问题 4 的前提**
3. 打包 + 安装 + 首次启动对话框显示
4. VB-Cable 检测 + 警告回退（不阻止录音）
5. 录音 → 转写 → 停止按钮状态正确
6. 卸载后重装，首次启动对话框重新显示（版本检测生效）
7. `transcribe_worker.py` 改为 import 后功能不变
8. 打包后所有 gui 模块正常加载（无 ModuleNotFoundError）

---

## [S12] Qoder 审查意见（2026-06-29）

> 逐条对照当前代码（config.py、first_launch.py、transcription.py、transcribe_worker.py、home_page.py、recording_bar.py、unified_recorder.py、installer.iss）验证方案可行性。

### 问题 1：首次启动对话框消失 — 方案可行 ✅，需补充细节

**代码验证**：
- `first_launch` 键**不在** `config.py` DEFAULTS 中（第 17-49 行无此字段）
- 它由 `first_launch.py:389-391` 的 `_finish()` 方法写入 `False`
- 由 `first_launch.py:399` 的 `check_first_launch()` 读取，默认值 `True`
- `app.py:234-235` 在 `__init__` 末尾检查并弹出对话框

**方案评价**：版本检测思路正确。但需注意：

1. **DEFAULTS 中需加 `"first_launch": True`**：当前 `first_launch` 不在 DEFAULTS 里，如果加了 `app_version` 但没加 `first_launch` 到 DEFAULTS，旧用户升级后 `config.get("first_launch", True)` 仍返回 True（因为键不存在），版本比较会重置为 True，逻辑上能工作但不够清晰。

2. **`app_version` 默认值应为空字符串**：旧用户没有此字段，`config.get("app_version", "")` 返回空，与当前 `APP_VERSION` 不匹配，触发重置。这是期望行为。

3. **边界情况**：如果用户从 v1.0 升级到 v1.0.1，对话框会重新弹出。这对内测阶段是合理的（每次更新都重新引导），但正式版可能需要更精细的策略（如只在 major.minor 变化时重置）。

**建议补充**：
```python
# config.py DEFAULTS 补充
"first_launch": True,
"app_version": "",
```

### 问题 2+3：VB-Cable 安装逻辑 — 方案部分冗余，需精简

**代码验证**：
- `first_launch.py:198-201` **已有** VB-Cable 提示文案（"如果需要录制线上会议系统音频，建议安装 VB-Audio Cable 虚拟音频设备"）
- `first_launch.py:346-348` **已有** `_open_vbcable_download()` 方法打开浏览器
- `unified_recorder.py:208-219` **已有** `_find_vb_cable()` 方法（遍历 PyAudio 设备列表查找 "VB-Audio" 或 "CABLE Input"）
- `unified_recorder.py:157-169` **已有** 回退逻辑：VB-Cable 找不到时自动回退到 WASAPI Loopback

**方案评价**：

1. **2a（首次启动加 VB-Cable 步骤）**：当前 Step 1 已有文字提示，但没有**设备检测**。方案要求加检测步骤，但 `_find_vb_cable()` 需要先初始化 PyAudio（`import pyaudiowpatch`），在首次启动对话框中做这个操作可能较慢（PyAudio 初始化需要扫描所有音频设备）。建议改为**轻量检测**：只检查系统中是否存在 "CABLE Input" 设备（通过 `subprocess` 调用 PowerShell 或读取注册表），不依赖 PyAudio。

2. **2b（设置页状态指示）**：合理，但优先级可以降低。当前设置页已有 VB-Cable 复选框，用户可以自己判断是否安装。

3. **2c（录音前检测）**：**与当前回退逻辑冲突**。当前代码在 VB-Cable 找不到时会**静默回退**到 WASAPI Loopback（`unified_recorder.py:169`），这其实是**正确的行为**——WASAPI Loopback 也能录制系统音频。方案要求抛出异常阻止录音，这过于激进。建议改为：回退时弹出警告对话框（"未检测到 VB-Cable，已自动切换到 WASAPI Loopback 模式"），但不阻止录音。

**建议**：问题 2 和 3 合并处理，但降低优先级到 P1。当前回退逻辑功能上是正确的，只是缺少用户提示。

### 问题 4：转录子进程静默崩溃 — 方案方向正确，超时值需调整

**代码验证**：
- `transcribe_worker.py:113` 子进程启动时发送日志消息
- `transcribe_worker.py:122` 发送 `("log", "模型检查通过，开始转写...")`
- `transcription.py:194-198` `_poll()` 已检测进程死亡：`if not self._process.is_alive(): self._on_done()`
- `transcription.py:283-291` 已处理 `"error"` 消息类型

**方案评价**：

1. **5a（心跳消息）**：当前代码已有部分心跳（`"log"` 消息），但不够细粒度。方案建议在模型加载前后、每个文件转写前发送心跳，这是合理的。但需要注意：心跳的主要作用是**诊断**（定位崩溃发生在哪个阶段），而不是**防止崩溃**。C++ 层段错误无法通过 Python 代码防止。

2. **5b（60 秒超时）**：**超时值过于激进**。根据日志线索，模型加载需要至少 4 秒（`17:49:15` 到 `17:49:19`），实际在慢机器上可能需要 30-60 秒。建议改为 **120 秒**，或者改为**自上次心跳起算**的超时（如 90 秒无消息视为异常）。

3. **5c（增强日志）**：当前 `transcribe_worker.py:241-244` 已有 `traceback` 日志，但 C++ 崩溃时不会触发 `except`。心跳消息可以帮助定位崩溃点，但无法捕获崩溃本身。

4. **5d（开发环境验证）**：这是**最重要的步骤**，应该在修复前就完成。如果开发环境正常，说明问题出在 PyInstaller 打包；如果开发环境也崩溃，说明是 FunASR 版本或模型问题。

**建议**：
- 先执行 5d（开发环境验证），确定问题根源
- 心跳机制可以实现，但超时值改为 120 秒或"自上次心跳 90 秒"
- 在 `_poll()` 中增加超时检测时，记录最后收到消息的时间戳

### 问题 5：停止按钮竞态条件 — 方案正确，但描述不够精确

**代码验证**：
- `recording_bar.py:299-340` 的 `update_state()` else 分支**已包含** pause_btn 样式重置（第 322-340 行），这是上次审查后修复的
- `transcription.py:971-990` 的 `stop_transcription()` 在第 988 行才设置 `self._transcribing = False`，**在 `process.terminate()` 和 `join()` 之后**
- `home_page.py:565-593` 的 `_on_transcription_done_handler` 手动设置 stop_btn 样式（第 570-588 行），**没有调用 `update_state()`**

**方案评价**：

1. **6a（stop_transcription 加防护）**：正确。当前代码在 `terminate()` 和 `join()` 之后才设置 `_transcribing = False`，如果用户快速点击两次停止按钮，可能触发两次 `stop_transcription()`。建议在方法开头立即设置 `self._transcribing = False`。

2. **6b（_on_transcription_done_handler 统一调用 update_state）**：正确。当前代码手动设置 stop_btn 样式，与 `recording_bar.py` 中的样式定义重复。改为 `self._recording_bar.update_state(recording=False, paused=False)` 更简洁，且能保证样式一致。

**建议**：方案正确，直接实施。

### 问题 6：config 跨安装残留 — 与问题 1 冲突，需二选一

**代码验证**：
- `installer.iss` 当前没有 `[UninstallDelete]` 段
- Inno Setup 默认不删除 AppData 目录

**方案评价**：

**与问题 1 冲突**：如果问题 1 采用版本检测方案（`app_version` 变化时重置 `first_launch=True`），那么卸载时删除 config 就**不是必需的**——因为即使 config 残留，版本检测也会触发重新引导。

两种方案的选择：
- **方案 A（版本检测）**：保留 config，只重置 `first_launch`。优点是用户配置（API Key、录音模式等）不丢失。
- **方案 B（卸载清理）**：删除 config 和 data。优点是干净，但用户需要重新配置。

**建议**：采用方案 A（版本检测），不实施问题 6 的 `[UninstallDelete]`。用户数据（录音、转写结果）不应在卸载时删除，config 也应保留以便升级后恢复设置。

### 问题 7：transcribe_worker.py 内联路径 — 正确，直接实施

**代码验证**：
- `transcribe_worker.py:21-25` 确实内联复制了 `get_data_dir()` 逻辑
- 当前结果与 `utils.py:get_data_dir()` 一致

**建议**：直接改为 `from utils import get_data_dir`。但需要注意：`transcribe_worker.py` 在子进程中运行，`utils.py` 必须能被正确导入。当前 `transcribe_worker.py:116-118` 已有 `sys.path.insert(0, src_dir)` 逻辑，所以导入没问题。

### 问题 8：hiddenimports 缺少模块 — 安全但非必需

**代码验证**：
- `me.spec:19-43` 的 hiddenimports 包含 `gui.first_launch`、`gui.dialogs`、`gui.home_page`
- 缺少 `gui.transcription`、`gui.settings_page`、`gui.voiceprint_page`、`gui.topbar`、`gui.recording_bar`、`gui.file_list_view`、`gui.styles`
- `gui/icons.py` 存在（已验证）

**方案评价**：
- 添加更多 hiddenimports 是安全的（PyInstaller 会忽略未使用的模块）
- 但这些模块通过 `app.py` 的直接 import 已被 PyInstaller 自动检测到
- 当前能正常打包运行，说明没有遗漏

**建议**：可以添加作为防御性措施，但优先级低。打包前验证一次即可。

### 汇总

| # | 问题 | 方案评价 | 建议 |
|---|------|----------|------|
| 1 | 首次启动消失 | ✅ 可行 | DEFAULTS 加 `first_launch: True` 和 `app_version: ""` |
| 2 | VB-Cable 安装逻辑 | ⚠️ 部分冗余 | 已有提示和下载按钮，加轻量检测即可 |
| 3 | VB-Cable 运行时检测 | ⚠️ 过于激进 | 不要阻止录音，改为警告+回退 |
| 4 | 转录子进程崩溃 | ✅ 方向正确 | 超时改 120 秒，先做开发环境验证 |
| 5 | 停止按钮竞态 | ✅ 正确 | `stop_transcription()` 开头立即置 `_transcribing=False` |
| 6 | config 跨安装残留 | ❌ 与问题 1 冲突 | 采用版本检测，不删除 config |
| 7 | 内联路径 | ✅ 正确 | 直接实施 |
| 8 | hiddenimports | ✅ 安全 | 防御性添加，优先级低 |

### 修复顺序建议（调整）

| 顺序 | 问题 | 原因 |
|------|------|------|
| 1 | **4d: 开发环境验证** | 先确定转录崩溃的根因（打包问题 vs FunASR 问题） |
| 2 | **1: 首次启动消失** | P0 + 改动小，5 分钟修复 |
| 3 | **5: 停止按钮竞态** | P1 + 改动小，10 分钟修复 |
| 4 | **4abc: 心跳+超时** | P0 + 需要仔细调整超时值 |
| 5 | **2+3: VB-Cable 检测** | P1 + 需要设计轻量检测方案 |
| 6 | **7: 内联路径** | 低 + 一行改动 |
| 7 | **8: hiddenimports** | 低 + 打包前补充 |
| ~~8~~ | ~~6: config 残留~~ | ~~不实施，与问题 1 冲突~~ |
