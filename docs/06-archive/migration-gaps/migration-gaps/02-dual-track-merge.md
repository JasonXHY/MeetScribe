# 缺失问题：`_merge_dual_track_results()` 实现方式变更

## 问题概述

双轨合并功能的实现方式从"后置合并"变更为"实时合并"，功能等价但实现方式不同。

## 状态标记

**已处理**：新版实现方式更优，无需修改。

**保留目的**：作为未来问题排查时的参考依据。

## 旧版实现（review材料 transcription.py:536-592）

### 调用位置
在 `_on_done()` 方法中调用（transcription.py:318-322）：

```python
# 双轨合并（在通知 app 之前执行）
try:
    self._merge_dual_track_results()
except Exception as e:
    self._app._log(f"双轨合并异常: {e}")
```

### 实现逻辑
```python
def _merge_dual_track_results(self):
    """合并双轨转写结果"""
    from dual_track_merge import find_dual_track_pair, merge_dual_transcripts

    done_files = self._app.file_manager.get_done_files()
    merged_pairs = set()

    self._app._log(f"开始检查双轨合并，已完成文件数: {len(done_files)}")

    for item in done_files:
        fp = item.file_path
        result_path = item.result_path

        if not result_path or not os.path.exists(result_path):
            continue

        pair = find_dual_track_pair(fp)
        if not pair:
            self._app._log(f"未找到双轨配对: {os.path.basename(fp)}")
            continue

        mic_path, sys_path = pair
        pair_key = (mic_path, sys_path)

        if pair_key in merged_pairs:
            self._app._log(f"已处理过此配对，跳过: {os.path.basename(mic_path)}")
            continue

        mic_item = self._app.file_manager.get_file(mic_path)
        sys_item = self._app.file_manager.get_file(sys_path)

        if not mic_item or not sys_item:
            self._app._log(f"双轨配对文件不存在: {os.path.basename(mic_path)} 或 {os.path.basename(sys_path)}")
            continue
        if mic_item.status != FileStatus.DONE or sys_item.status != FileStatus.DONE:
            self._app._log(f"双轨配对文件未完成: {os.path.basename(mic_path)} ({mic_item.status}) 或 {os.path.basename(sys_path)} ({sys_item.status})")
            continue
        if not mic_item.result_path or not sys_item.result_path:
            self._app._log(f"双轨配对文件无转写结果: {os.path.basename(mic_path)} 或 {os.path.basename(sys_path)}")
            continue

        try:
            with open(mic_item.result_path, "r", encoding="utf-8") as f:
                mic_text = f.read()
            with open(sys_item.result_path, "r", encoding="utf-8") as f:
                sys_text = f.read()

            merged_text = merge_dual_transcripts(mic_text, sys_text)

            with open(mic_item.result_path, "w", encoding="utf-8") as f:
                f.write(merged_text)

            self._app._log(f"双轨合并完成: {os.path.basename(mic_item.result_path)}")
            merged_pairs.add(pair_key)

        except Exception as e:
            self._app._log(f"双轨合并失败: {e}")
```

## 新版实现（transcribe_worker.py:135-159）

### 调用位置
在转写过程中实时调用：

```python
if merge:
    # 区分双轨对（mic + system 同一次录音）与普通多文件合并：
    # 双轨走 merge_dual_transcripts 按时间戳交错并加本地/远程前缀，
    # 普通多文件仍走 "## file" 顺序拼接。判定与合并都在
    # dual_track_merge.build_merged_transcript 这个纯函数里完成，
    # worker 只负责逐轨转写后把文本喂进去。
    from dual_track_merge import build_merged_transcript, is_dual_track_group

    is_dual = is_dual_track_group(file_paths) is not None
    mode_desc = "双轨" if is_dual else "多文件"
    queue.put(("log", f"合并模式（{mode_desc}）：将 {len(file_paths)} 个文件合并转写"))
```

## 实现方式对比

| 维度 | 旧版 | 新版 |
|------|------|------|
| **合并时机** | 转写完成后后置合并 | 转写过程中实时合并 |
| **合并逻辑** | 读取两个文件的转写结果，调用 `merge_dual_transcripts` | 在 worker 中调用 `build_merged_transcript` |
| **文件处理** | 先分别转写，再合并结果 | 转写时就合并 |
| **日志输出** | 详细日志（配对查找、跳过、完成） | 简化日志 |
| **错误处理** | try-catch 包裹，记录异常 | 依赖 worker 的错误处理 |

## 影响分析

### 正面影响

1. **性能更优**：实时合并避免了后置合并的文件读写开销
2. **逻辑更清晰**：合并逻辑集中在 worker 中，职责更明确
3. **用户体验更好**：不需要等待所有文件转写完成后再合并

### 潜在风险

1. **错误处理简化**：新版的错误处理不如旧版详细
2. **日志信息减少**：调试时可能缺少关键信息
3. **兼容性问题**：如果 `build_merged_transcript` 有 bug，可能影响整个转写流程

## 结论

新版实现方式更优，无需修改。保留此文档作为未来问题排查时的参考依据。

## 相关代码位置

### 旧版
- 合并实现：`transcription.py:536-592`（review材料）
- 合并调用：`transcription.py:318-322`（review材料）

### 新版
- 合并实现：`transcribe_worker.py:135-159`
- 合并工具：`dual_track_merge.py`

## 参考资料

- 旧版代码：`C:\Users\kingdee\Desktop\侧耳倾听-评审材料\src_old\transcription.py`
- 新版代码：`C:\侧耳倾听\src\gui\transcription.py`
- 双轨合并工具：`C:\侧耳倾听\src\dual_track_merge.py`
