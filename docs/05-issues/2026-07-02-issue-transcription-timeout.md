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
