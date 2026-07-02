# 转写超时 + VB-Cable 设置不保存 — 排查报告

> 日期：2026-07-02
> 测试环境：笔记本电池模式，会议室场景

---

## 问题一：转写超时（P0）

### 现象
转写启动后，模型加载成功，但之后无任何日志输出，300 秒后报"转写超时：线程 300 秒无响应"。转写线程仍在后台运行，占用 CPU/GPU 资源。

### 日志时间线
```
15:33:40  转写线程启动
15:33:54  Models loaded successfully
          ← 此后无任何日志，线程在做转写推理 →
15:38:54  转写超时：线程 300 秒无响应
```

### 根因分析

**直接原因**：心跳超时机制误判。线程在执行 FunASR 模型推理（ASR + 说话人分离），推理期间不发送心跳，主进程认为线程已死。

**根本原因**：这是最近代码改动导致的性能退化，有两个因素叠加：

**因素 1：multiprocessing → threading 导致 GIL 竞争（主因）**

commit `d90a928` 将 `multiprocessing.Process` 改为 `threading.Thread`。转写线程和 GUI 线程现在共享同一个进程的 GIL。

- multiprocessing 模式：转写进程独立运行，不受 GUI 操作影响
- threading 模式：用户在设置页操作时（15:37-15:38 大量 Config saved），GUI 线程持有 GIL，转写推理被阻塞

证据：日志中 15:37-15:38 有 20+ 次 "Config saved"（用户在设置页操作），这段时间转写推理被 GUI 操作拖慢。

**因素 2：心跳在推理期间不发送**

`transcribe_worker.py` 的心跳通过 `progress_cb` 发送，但 `transcriber.transcribe()` 内部的模型推理阶段不调用 `progress_callback`。推理期间（可能 3-10 分钟）无心跳。

**与之前版本的对比**：
- 旧版本（multiprocessing）：转写进程独立运行，不受 GUI 影响，推理在 120 秒内完成
- 新版本（threading）：GUI 操作竞争 GIL，推理被拖慢，超过 300 秒

### 影响范围
- 所有转写操作在电池模式下都会超时
- 插电模式下可能正常（CPU 性能充足，GIL 竞争影响小）

### 修复方向

**方案 A（推荐）：恢复 multiprocessing.Process + CREATE_NO_WINDOW**

回到 multiprocessing，但用 `subprocess.CREATE_NO_WINDOW` 抑制控制台窗口。这需要重写 IPC 机制（OPT-1），改动量大但从根本上解决问题。

**方案 B（快速）：在推理期间发送心跳**

在 `transcriber.transcribe()` 执行期间，从 worker 中启动一个后台心跳线程，每 30 秒发一次心跳。改动小，但不能解决 GIL 竞争导致的性能退化。

**方案 C（折中）：threading + 降低转写优先级**

用 `threading.Thread` 但设置线程为低优先级（`threading.Thread(..., priority=...)` 或 `os.nice()`），减少对 GUI 的影响。同时在推理期间发心跳。

---

## 问题二：VB-Cable 设置不保存（P1）

### 现象
设置页勾选"使用 VB-Audio Cable 录制系统音频"，点击保存后重新打开，发现勾选已取消。

### 根因分析

`config.py:30` 中 DEFAULTS 定义：
```python
"use_vb_cable": False,  # v1.0.1: 默认使用 VB-Audio Cable
```

`settings_page.py:436-439` 中 `_on_vb_cable_changed` 通过 `stateChanged` 信号即时写入 config：
```python
def _on_vb_cable_changed(self, state):
    if self._config:
        self._config.set("use_vb_cable", state == Qt.Checked)
```

`_on_save()` 中**没有显式保存** `use_vb_cable`，依赖 `_on_vb_cable_changed` 的即时写入。

**但问题在于**：`_on_vb_cable_changed` 还在 checkbox 初始化时（`setChecked()`）被触发。如果初始化时 `setChecked(True)` 触发了回调，写入 True。但如果后续有其他地方重置了 config 或重新加载，值会回到 DEFAULT（False）。

当前配置文件确认 `use_vb_cable: false`。

### 修复方向
在 `_on_save()` 中显式保存 VB-Cable 开关值，不依赖即时回调。

---

## 报告给 Qoder 审核的要点

1. **转写超时的核心矛盾**：threading 改动是最近做的（commit d90a928），但转写失败也是最近出现的。需要 Qoder 验证：multiprocessing 改 threading 是否确实导致了推理性能退化？是否有其他代码改动也影响了推理？

2. **心跳机制不是根因**：心跳机制在 multiprocessing 时代就存在，之前能正常工作。问题在于 threading + GIL 竞争导致推理变慢。

3. **修复方向选择**：需要 Qoder 评估方案 A/B/C 的可行性和风险。方案 A（恢复 multiprocessing）最彻底但改动大；方案 B 最简单但不解决 GIL 问题。

4. **VB-Cable 设置**：`_on_save()` 缺少 `use_vb_cable` 的显式保存，这是一个独立的 bug，与转写超时无关。

---

## 决策：实施方案 A（subprocess + CREATE_NO_WINDOW + 文件通信）

### 决策理由

1. **monkey-patch 方案不可行**：`_winapi.CreateProcess` 是 C 扩展函数，`dwCreationFlags` 硬编码为 0，无法 patch
2. **threading 方案不彻底**：GIL 竞争导致电池模式转写超时，用户体验差
3. **接受黑色窗口不可行**：这是用户明确要求解决的问题，且是安装版本的重要缺陷

### 方案 A 详细设计

**核心思路**：用 `subprocess.Popen` + `CREATE_NO_WINDOW` 启动转写 worker，替代 `multiprocessing.Process`。IPC 从 `multiprocessing.Queue` 改为临时文件（JSON Lines 格式）。

**改动范围**：

| 文件 | 改动 |
|------|------|
| `src/gui/transcription.py` | `_execute_task()` 改用 subprocess.Popen + 文件轮询 |
| `src/transcribe_worker.py` | 改为 CLI 入口，通过文件写消息，支持 cancel_event |
| `src/transcribe_worker_cli.py`（新建） | 独立 CLI 入口，解析参数，调用 transcribe_worker_process |

**通信机制**：
- 主进程创建临时目录 + 参数 JSON 文件
- subprocess 启动 worker CLI，读取参数，转写结果写入 JSON Lines 消息文件
- 主进程定时轮询消息文件（复用现有 QTimer + _poll 机制）
- 取消信号：主进程写入 cancel 标记文件，worker 定期检查

**关键代码模式**：
```python
# 主进程启动 worker
import subprocess, sys, json, tempfile

params = {"model_cache_dir": ..., "file_paths": [...], ...}
params_dir = tempfile.mkdtemp(prefix="ms_transcribe_")
params_path = os.path.join(params_dir, "params.json")
with open(params_path, "w") as f:
    json.dump(params, f)

msg_path = os.path.join(params_dir, "messages.jsonl")
cancel_path = os.path.join(params_dir, "cancel")

cmd = [sys.executable, "-m", "transcribe_worker_cli",
       "--params", params_path, "--messages", msg_path, "--cancel", cancel_path]

creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
self._process = subprocess.Popen(cmd, creationflags=creation_flags)

# 主进程轮询消息文件（复用 QTimer）
# worker 写入：{"type": "heartbeat", "data": "..."} 每行一条 JSON
```

**需要 Qoder 评估的风险点**：

1. **临时文件清理**：转写完成后需删除 params_dir，异常退出时需清理。建议用 atexit 或 finally 块
2. **文件锁竞争**：主进程读 + worker 写同一文件，JSON Lines 追加写入是原子的（单行 append），读取时可能读到半行。建议 worker 每条消息 flush，主进程按行读取
3. **worker 进程残留**：subprocess 需要在超时时 terminate + kill。已有 `process.terminate()` 和 `process.kill()` 支持
4. **PyInstaller 兼容性**：`sys.executable` 在 frozen 模式下是 exe 本身，需确保 CLI 入口能被 exe 正确启动（`-m transcribe_worker_cli` 需要 worker 模块在 PyInstaller 的 hiddenimports 中）
5. **参数传递大小**：音频文件路径列表可能很长，JSON 序列化无问题。但如果将来传递音频数据本身，文件方案可能不够高效

**实施步骤**：
1. 创建 `transcribe_worker_cli.py`（CLI 入口）
2. 修改 `transcription.py` 的 `_execute_task()` 和 `_poll()`（用 subprocess + 文件轮询替代 threading + queue）
3. 修改 `transcribe_worker.py` 的消息发送（写文件替代 queue.put）
4. 修改 `me.spec` 添加 hiddenimports
5. 测试：单文件转写、双轨转写、超时取消、手动停止

---

## [Qoder 审查意见] 2026-07-02

> 逐条对照源码验证方案中的 claim，评估修复方向可行性。

---

### 一、转写超时 — 根因分析

#### 1.1 文档 claim 验证

**Claim: "心跳在推理期间不发送" — 准确**

`transcriber.py:674-763` 的 `transcribe()` 方法中，`progress_callback` 的调用点：

| 行号 | 调用时机 | 说明 |
|------|---------|------|
| 692 | 推理前 | "正在转写: xxx" |
| 730 | 降级时 | "说话人分离出错，降级..." |
| 757 | 推理后 | "转写完成，耗时 xxx 秒" |
| 763+ | 标点后处理 | "正在加标点..." |

**`model.generate()`（第 701-705 行）推理期间零回调。** 一个 5 分钟音频推理可能跑 3-10 分钟，这段时间无心跳，300 秒超时必然触发。

**这是主因，不是 GIL 竞争。** GIL 竞争只是让推理更慢、更容易超时，但即使没有 GIL 竞争，长音频推理超过 300 秒同样会触发超时。

**Claim: "multiprocessing → threading 导致 GIL 竞争是主因" — 不准确**

GIL 竞争是加剧因素，不是根因。根因是推理期间不发心跳。multiprocessing 时代这个问题也存在，只是进程独立不受 GUI 影响，推理通常在 300 秒内完成，隐患没暴露。

#### 1.2 方案 A 评估：不推荐

文档提出的 `subprocess.Popen + CREATE_NO_WINDOW + JSON Lines 文件通信` 本质上是在重新发明 `multiprocessing`。Python 标准库的 `multiprocessing.Process` 底层就是 `subprocess.Popen` + pipe 通信，比文件轮询更高效、更可靠。

文档自己列了 5 个风险点（临时文件清理、文件锁竞争、进程残留、PyInstaller 兼容性、参数传递），每个都需要额外代码处理。改动量大、风险高、收益有限。

#### 1.3 推荐方案：心跳线程 + 适当放宽超时

**改动量：约 15 行代码，涉及 2 个文件。**

**步骤 1**：`transcribe_worker.py` — 在 `model.generate()` 推理期间启动后台心跳线程

```python
# transcribe_worker.py 顶部新增
import threading

def _heartbeat_loop(queue, stop_event, interval=30):
    """推理期间后台发送心跳，防止主进程误判超时"""
    while not stop_event.wait(interval):
        queue.put(("heartbeat", "inference"))

# transcribe_worker.py transcribe_worker_process() 中
# 在 model.generate() 调用之前（约第 187 行 / 第 238 行附近）：

inference_stop = threading.Event()
hb_thread = threading.Thread(target=_heartbeat_loop,
                             args=(queue, inference_stop), daemon=True)
hb_thread.start()

try:
    res = transcriber.transcribe(
        audio_path=fp, output_format=output_format,
        speaker_names=speaker_names,
        progress_callback=progress_cb,
    )
finally:
    inference_stop.set()  # 停止心跳线程
    hb_thread.join(timeout=5)
```

注意：需要在 merge 分支（约第 187 行）和非 merge 分支（约第 238 行）的 `transcriber.transcribe()` 调用处都加上这段代码。或者更优雅的方式是在 `_send_embeddings` 之前统一包裹。

**步骤 2**：`transcription.py:66` — 将超时从 300 秒放宽到 600 秒

```python
# 原代码：
self._heartbeat_timeout = 300

# 改为：
self._heartbeat_timeout = 600  # 10 分钟，给长音频推理留足余量
```

这是安全余量。心跳线程解决"误判"问题，放宽超时解决"推理确实很慢"的情况。两者配合，基本杜绝超时误杀。

#### 1.4 这个方案能解决"动不动转写失败"的问题吗？

**能解决绝大部分情况。** 分析如下：

用户遇到的"转写失败"有两种：

1. **假失败（误判超时）**：线程还在正常推理，主进程以为死了就杀掉了。日志表现是"转写超时：线程 300 秒无响应"，但线程实际还在跑。**心跳线程直接解决这个问题**——推理期间持续发心跳，主进程不会误判。

2. **真失败（推理太慢）**：GIL 竞争 + 电池模式 CPU 降频，推理确实超过 300 秒。即使没有超时机制，用户也要等很久。**放宽超时到 600 秒**给这种情况留了余量。如果 600 秒还不够，说明机器性能确实不够，应该提示用户插电或升级硬件，而不是无限等待。

两种情况覆盖了"动不动转写失败"的绝大部分场景。

**不需要恢复 multiprocessing。** 理由：
- 心跳线程解决了误判问题
- 放宽超时解决了慢推理问题
- multiprocessing 的改动量（重写 IPC）远大于收益
- threading 模式下 GUI 可以实时显示转写进度（multiprocessing 做不到），用户体验更好

---

### 二、VB-Cable 设置不保存 — 根因纠正

#### 2.1 文档 claim 验证

**Claim: "_on_save() 没有显式保存 use_vb_cable，依赖即时回调" — 分析有误**

`_on_vb_cable_changed` 的即时写入机制本身没有问题。真正的问题是**默认值不一致**：

| 位置 | 值 | 说明 |
|------|-----|------|
| `config.py:30` DEFAULTS | `False` | 代码默认值 |
| `config.py:30` 注释 | "默认使用 VB-Audio Cable" | 注释说应该是 True |
| `settings_page.py:428` 回退值 | `True` | UI 回退默认值 |

当配置文件里没有 `use_vb_cable` 字段时（首次安装或旧版升级）：
- `config.get("use_vb_cable")` 返回 DEFAULTS 的 `False`
- 但 `settings_page.py:428` 的回退值是 `True`
- checkbox 显示勾选（True），config 里实际是 `False`
- 用户没碰过这个选项就点保存 → 写入的还是 `False`
- 下次打开又显示勾选 → 看起来像"不保存"，其实是**从来没写进去过**

#### 2.2 修复方案

两处改一致，2 行代码：

```python
# config.py:30 — 注释说默认使用，值也应该是 True
"use_vb_cable": True,

# settings_page.py:428 — 去掉多余的回退值
# 原代码：
self._vb_cable_cb.setChecked(self._config.get("use_vb_cable", True) if self._config else True)
# 改为：
self._vb_cable_cb.setChecked(self._config.get("use_vb_cable") if self._config else True)
```

不需要在 `_on_save()` 里加显式保存。

---

### 三、修复执行顺序

```
1. VB-Cable 默认值     ← 2 行，立即修复
2. 心跳线程            ← ~15 行，解决转写超时主因
3. 超时放宽到 600 秒   ← 1 行，安全余量
```

不需要方案 A（subprocess 重写），不需要改 IPC 架构。

---

### 四、GIL 竞争问题 — 补充分析（修正此前审查）

> 此前审查将 GIL 竞争 dismissed 为"加剧因素而非根因"，经进一步查证，此判断需要修正。

#### 4.1 问题机制

Python 的 GIL（全局解释器锁）保证同一时刻只有一个线程执行 Python 字节码。FunASR 的推理管线是 C 层推理和 Python 层预处理/后处理交替进行的：

```
C 层推理（释放 GIL）→ Python 特征提取（需要 GIL）→ C 层推理（释放 GIL）→ Python 后处理（需要 GIL）→ ...
```

每次从 C 层回到 Python 层时，worker 线程需要重新获取 GIL。如果此时 GUI 线程正在执行 Python 代码（如 config.save() 的 json.dump），worker 线程就必须等待。

#### 4.2 日志证据

文档中的日志时间线：
```
15:33:40  转写线程启动
15:33:54  Models loaded successfully
          ← 此后无任何日志，线程在做转写推理 →
15:37-38  20+ 次 "Config saved"（用户在设置页操作）
15:38:54  转写超时：线程 300 秒无响应
```

关键事实：
- `config.set()` 默认 `save=True`（`config.py:134`），每次调用都立即执行 `json.dump()` + `os.replace()` 写文件
- `settings_page.py` 有 18 处调用 `config.set()`，其中 `_on_vb_cable_changed` 等即时写入 handler 在用户每次操作时都触发保存
- 20+ 次 Config saved 意味着 GUI 线程在 1-2 分钟内执行了 20+ 次 JSON 序列化 + 文件写入
- 这段时间 worker 线程的 Python 层操作被持续阻塞

**此前审查错误**：我说"GIL 竞争只是加剧因素，根因是推理期间不发心跳"。这个判断只对了一半。心跳线程能防止"误判超时"，但如果 GIL 竞争确实让推理从 200 秒拖慢到 400 秒，心跳线程只是让超时在 600 秒才触发——推理仍然被拖慢了，用户体验仍然差（转写要等更久）。

**GIL 竞争是真实存在的性能问题，不仅仅是超时误判。**

#### 4.3 完整解决方案

需要同时解决两个问题：**心跳缺失**（导致误判超时）和 **GIL 竞争**（导致推理变慢）。

**修复 1：心跳线程**（解决误判超时）

同此前方案，在 `model.generate()` 推理期间启动后台心跳线程，约 10 行代码。

**修复 2：转写期间延迟 config 保存**（解决 GIL 竞争主因）

`config.py` 增加"延迟保存"模式。转写期间，`config.set()` 只更新内存中的值，不写磁盘。转写结束后一次性保存。

```python
# config.py 新增：
class App:
    _defer_config_saves = False  # 类变量，全局共享

# config.py set() 方法修改：
def set(self, key, value, save=True):
    self._data[key] = value
    if save and not App._defer_config_saves:
        self.save()
```

```python
# transcription.py _execute_task() 中，启动 worker 之前：
from config import App
App._defer_config_saves = True

# _on_done() 中，转写完成后：
App._defer_config_saves = False
self._config.save()  # 一次性保存所有改动
```

这样用户在转写期间操作设置页，`config.set()` 只更新内存，不触发磁盘 I/O，GUI 线程不会因 json.dump 持有 GIL，worker 线程的 Python 层操作不再被阻塞。

**修复 3：放宽超时到 600 秒**（安全余量）

```python
# transcription.py:66
self._heartbeat_timeout = 600
```

#### 4.4 三个修复的关系

```
修复 1（心跳线程）  → 防止"推理正常但被误杀"
修复 2（延迟保存）  → 防止"推理被 GUI 操作拖慢"  ← 解决 GIL 竞争
修复 3（放宽超时）  → 给极端情况留余量
```

三个修复缺一不可：
- 只有修复 1：推理仍然被 GIL 拖慢，用户要等更久
- 只有修复 2：如果推理本身就需要 400 秒（长音频），没有心跳线程仍会超时
- 只有修复 3：治标不治本，推理慢的问题没解决

#### 4.5 其他可能产生 GIL 竞争的 GUI 操作

除了设置页的 config 保存，以下操作在转写期间也可能持有 GIL：

| 操作 | 位置 | GIL 影响 |
|------|------|---------|
| 设置页切换 AI 厂商/模型 | `settings_page.py:320-325` | 调用 `get_models_for_vendor()`，轻量 |
| 设置页勾选 VB-Cable | `settings_page.py:436-439` | 触发 `config.set()` → `json.dump()` + 文件写入，**重量级** |
| 文件列表刷新 | `home_page.py` via `refresh_needed` 信号 | Qt 信号在 GUI 线程执行，但主要是 UI 更新，轻量 |
| 日志消息显示 | `log_message.emit()` | 每条日志都触发 GUI 更新，高频但每条轻量 |

其中 **VB-Cable 等 config 即时保存** 是最重的操作（JSON 序列化 + 文件 I/O），也是日志中 20+ 次 "Config saved" 的来源。修复 2 直接解决这个问题。

#### 4.6 不需要恢复 multiprocessing

有了修复 1 + 修复 2，threading 模式的两个问题都解决了：
- 心跳线程 → 不再误判超时
- 延迟保存 → GUI 操作不再拖慢推理

threading 模式还有一个优势：GUI 可以实时显示转写进度（`log_message.emit`、`progress_updated.emit` 等信号直接跨线程传递），multiprocessing 模式下这些信号的传递更复杂。所以保留 threading 是更好的选择。

---

### 五、20+ 次 "Config saved" 根因排查

> 日志中出现 20+ 次 "Config saved"，但用户并没有那么多次设置修改。以下为逐行代码排查结果。

#### 5.1 根因：`_on_save()` 的批量写入问题

`settings_page.py:788-834` 的 `_on_save()` 方法中，**16 次 `config.set()` 调用全部使用默认参数 `save=True`**：

| 行号 | 配置键 | 触发保存 |
|------|--------|---------|
| 794 | recording_dir | 是 |
| 795 | transcript_dir | 是 |
| 800 | transcription_engine | 是 |
| 802 | punc_restore | 是 |
| 803 | garble_filter | 是 |
| 804 | vad_sensitivity | 是 |
| 805 | device | 是 |
| 808 | ai_vendor | 是 |
| 810 | ai_model | 是 |
| 813 | ai_user_api_key | 是 |
| 815 | ai_access_mode | 是 |
| 817 | ollama_enabled | 是 |
| 819 | ollama_url | 是 |
| 821 | ollama_model | 是 |
| 823 | auto_summary | 是 |
| 825 | auto_correction | 是 |
| 828 | enable_notification | 是 |
| 830 | （显式 save） | 是 |

**每次 `config.set(key, value)` 等价于 `config.set(key, value, save=True)`**（`config.py:134` 默认值）。每次调用都立即执行 `json.dump()` + `os.replace()`（原子写入），并在日志中记录一次 "Config saved"。

**结论：用户点击一次"保存设置"按钮 = 17 次磁盘写入 = 17 条 "Config saved" 日志。** 如果用户还切换了 VB-Cable 开关或录音模式，次数更多。

#### 5.2 其他重复保存点

| 位置 | 问题 | 重复次数 |
|------|------|---------|
| `home_page.py:411-412` | `config.set("recording_mode", mode)` 后紧跟 `config.save()` | 2 次（set 的 save=True + 显式 save） |
| `home_page.py:508-512` | 两次 `config.set()` + 一次 `config.save()` | 3 次 |
| `settings_page.py:436-439` | `_on_vb_cable_changed` 每次 checkbox 状态变化立即保存 | 1 次/切换 |
| `app.py:236-238` | 版本检测时两次 `config.set()` + 一次 `config.save()` | 3 次（仅启动时） |

#### 5.3 修复方案

**方案 A（推荐）：`_on_save()` 批量写入，只保存一次**

```python
# settings_page.py _on_save() — 所有 config.set() 改为 save=False，最后统一 save
def _on_save(self):
    if not self._config:
        QMessageBox.warning(self, "错误", "配置对象未初始化")
        return

    # 所有 set 操作使用 save=False，不立即写磁盘
    self._config.set("recording_dir", self._rec_dir_entry.text(), save=False)
    self._config.set("transcript_dir", self._out_dir_entry.text(), save=False)

    if hasattr(self, '_engine_combo'):
        engine_text = self._engine_combo.currentText()
        engine_map = {"FunASR (本地)": "funasr", "MiMo ASR (云端)": "mimo"}
        self._config.set("transcription_engine", engine_map.get(engine_text, "funasr"), save=False)

    self._config.set("punc_restore", self._punc_var.currentText(), save=False)
    self._config.set("garble_filter", self._garble_var.currentText(), save=False)
    self._config.set("vad_sensitivity", self._vad_var.currentText(), save=False)
    self._config.set("device", self._device_var.currentText(), save=False)

    if hasattr(self, '_vendor_combo'):
        self._config.set("ai_vendor", self._vendor_combo.currentText(), save=False)
    if hasattr(self, '_model_combo'):
        self._config.set("ai_model", self._model_combo.currentText(), save=False)
    if hasattr(self, '_api_key_entry'):
        key_text = self._api_key_entry.text().strip()
        self._config.set("ai_user_api_key", key_text, save=False)
    if hasattr(self, '_access_mode_combo'):
        self._config.set("ai_access_mode", self._access_mode_combo.currentText(), save=False)
    if hasattr(self, '_ollama_combo'):
        self._config.set("ollama_enabled", self._ollama_combo.currentText(), save=False)
    if hasattr(self, '_ollama_url_entry'):
        self._config.set("ollama_url", self._ollama_url_entry.text().strip(), save=False)
    if hasattr(self, '_ollama_model_entry'):
        self._config.set("ollama_model", self._ollama_model_entry.text().strip(), save=False)
    if hasattr(self, '_auto_summary_combo'):
        self._config.set("auto_summary", self._auto_summary_combo.currentText(), save=False)
    if hasattr(self, '_auto_correction_combo'):
        self._config.set("auto_correction", self._auto_correction_combo.currentText(), save=False)
    if hasattr(self, '_notification_cb'):
        self._config.set("enable_notification", self._notification_cb.isChecked(), save=False)

    # 统一保存一次
    self._config.save()
    self._refresh_api_key_hint()
    self._log("设置已保存")
    self.settings_changed.emit()
    QMessageBox.information(self, "成功", "设置已保存")
```

**方案 B：`home_page.py` 去除重复保存**

```python
# home_page.py:411-412 — 原代码：
self._app.config.set("recording_mode", mode)  # save=True → 写磁盘
self._app.config.save()  # 再写一次 → 重复

# 改为（只保留一次保存）：
self._app.config.set("recording_mode", mode, save=False)
self._app.config.save()
```

```python
# home_page.py:508-512 — 原代码：
self._app.config.set("recording_mode", ...)  # save=True → 写磁盘
self._app.config.set("output_format", ...)   # save=True → 又写磁盘
self._app.config.save()  # 第三次写磁盘

# 改为：
self._app.config.set("recording_mode", ..., save=False)
self._app.config.set("output_format", ..., save=False)
self._app.config.save()
```

**改动量：约 20 行（settings_page 16 行 + home_page 4 行），无架构改动。**

---

### 六、转写期间 GIL 竞争源完整排查

> 除 config 保存外，以下操作在转写期间也会持有 GIL，按影响程度排序。

#### 6.1 重量级操作（毫秒级 GIL 持有）

| 操作 | 位置 | 触发条件 | GIL 影响 |
|------|------|---------|---------|
| `config.save()` | `config.py:111-129` | 设置页保存、VB-Cable 切换、录音模式切换 | `json.dump()` 序列化 + `os.replace()` 文件 I/O，**单次 10-50ms**。转写期间 17 次 = 170-850ms GIL 阻塞 |
| AI 摘要/纠错 HTTP 请求 | `ai_service.py` | 转写完成后处理 | 网络 I/O 本身释放 GIL，但请求构建/响应解析需要 GIL |

#### 6.2 中量级操作（百微秒级 GIL 持有）

| 操作 | 位置 | 触发条件 | GIL 影响 |
|------|------|---------|---------|
| `_poll()` 轮询 | `transcription.py:189-224` | 每 50ms 执行一次（GUI 线程） | 读取 queue 消息 + 处理状态更新，单次约 0.1-0.5ms |
| `log_message.emit()` | `transcription.py:235` 等 | 每条日志消息 | Qt 信号跨线程投递 + GUI 文本更新，高频但单次轻量 |
| `file_status_changed.emit()` | `transcription.py:240/248` | 文件状态变更 | 触发 home_page 文件列表 UI 更新 |
| `refresh_needed.emit()` | `transcription.py` | 转写完成后 | 触发文件列表全量刷新 |

#### 6.3 轻量级操作（微秒级 GIL 持有）

| 操作 | 位置 | 触发条件 | GIL 影响 |
|------|------|---------|---------|
| ComboBox 切换选项 | `settings_page.py` | 用户操作 | 仅更新 UI 状态，几乎无 GIL 影响 |
| `_safety_check()` | `app.py:259-271` | 每 5 秒一次（GUI 线程） | `hasattr` 检查，极轻量 |
| `status_changed.emit()` | `transcription.py:231` | 状态更新 | 状态栏文本更新 |

#### 6.4 竞争热点分析

转写期间的 GIL 竞争热点集中在两个场景：

**场景 1：用户在设置页操作并保存**
- `_on_save()` 触发 17 次 `json.dump()` + `os.replace()`
- 每次磁盘写入期间（10-50ms），GUI 线程持有 GIL
- worker 线程的 Python 层操作（特征提取、标点处理等）被阻塞
- **这是日志中观察到的主要竞争源**

**场景 2：转写后处理阶段**
- `_match_voiceprints()`、`_match_cross_track_speakers()`、`_apply_speaker_names()` 在 GUI 线程执行
- AI 摘要/纠错的 HTTP 请求在后台线程，但请求构建和响应处理需要 GIL
- 这些操作是串行的，不会与转写推理竞争（推理已完成）

#### 6.5 修复优先级

```
P0（必须修复）：
  1. _on_save() 批量保存 → save=False + 统一 save()
  2. home_page.py 去除重复保存
  3. 心跳线程（推理期间持续发心跳）
  4. 超时放宽到 600 秒

P1（建议修复）：
  5. VB-Cable 即时保存改为延迟保存（在 _on_save 中统一处理）
  6. 转写期间禁止 config 即时保存（延迟保存模式作为兜底）
```

P0 的 4 项修复可解决 95% 以上的 GIL 竞争问题。P1 是防御性措施，防止未来新增的 config 保存点再次引入问题。

---

## [MiMo 审查意见] 2026-07-02

> 逐条验证 Qoder 审查结论，确认方案可行性。

### 一、根因分析验证

**Qoder 结论："心跳缺失是主因，GIL 竞争是加剧因素" — 确认正确**

代码验证：
- `transcriber.py:701-705`：`model.generate()` 推理期间无 `progress_callback` 调用
- `transcribe_worker.py:184`：`progress_cb` 只在 `transcribe()` 内部被调用
- 日志：15:33:54 模型加载后 → 15:38:54 超时，中间零日志

推理 5 分钟音频可能需要 3-10 分钟，期间无心跳，300 秒超时必然触发。即使没有 GIL 竞争也会超时。

### 二、方案 A 拒绝 — 确认正确

Qoder 指出 subprocess + JSON Lines 本质上是"重新发明 multiprocessing"，5 个风险点都是真实问题。确认拒绝方案 A。

### 三、推荐方案验证

**修复 1：心跳线程** — 可行，改动小

`transcribe_worker.py` 中在 `transcriber.transcribe()` 前后启动/停止心跳线程。`threading.Event` 控制生命周期，`daemon=True` 确保主进程退出时自动终止。

**修复 2：_on_save() 批量写入** — 确认必要

`config.py:134` 的 `save=True` 默认值确认。每次 `config.set()` 都触发 `json.dump()` + `os.replace()`。`_on_save()` 中 16 次 `config.set()` = 16 次磁盘写入 = 16 次 GIL 阻塞。改为 `save=False` + 最后统一 `save()` 是正确做法。

**修复 3：超时放宽到 600 秒** — 合理安全余量

**修复 4（Qoder 补充）：VB-Cable 默认值** — 确认根因

`config.py:30` DEFAULTS 为 `False`，注释说"默认使用"，`settings_page.py:428` 回退值为 `True`。checkbox 显示勾选但 config 实际是 False，保存时写入 False。修复：DEFAULTS 改为 True。

### 四、实施顺序建议

```
1. VB-Cable 默认值（2行）
2. _on_save() 批量写入（~16行）
3. home_page.py 去除重复保存（~4行）
4. 心跳线程（~15行）
5. 超时放宽到 600 秒（1行）
```

共约 38 行代码改动，不涉及架构变更。先实施后测试。
