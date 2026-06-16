# T-G4 — 双轨按时间戳合并接入 worker

- **Tier**: 1（核心管线接线）
- **关联需求**: TRN-011（双轨合并转写）
- **依赖**: T-G1（文件名配对修好后才能拿到正确的双轨对）
- **预估**: 1.5 天

## 背景
`src/dual_track_merge.py:43 merge_dual_transcripts(mic_text, sys_text, ...)`（按时间戳排序合并、加本地/远程前缀）
**从未被任何代码调用**（grep 仅见定义）。当前合并转写分支（`src/transcribe_worker.py:129-174`）只是把多个文件的转写结果用 `## file` 拼接，**没有按时间戳交错合并，也没有区分双轨来源**。
因此 spec 的"两轨分别转写 → 自动按时间戳合并"在端到端流程里没有真正实现。

## Scope
1. 在转写流程中区分"双轨合并"与"普通多文件合并"两种合并语义：
   - 双轨（mic + system，来自同一次录音）→ 调用 `merge_dual_transcripts` 按时间戳交错合并。
   - 普通多文件合并 → 保留现有顺序拼接。
2. 将双轨对（来自 T-G1 的 `find_dual_track_pair` / merged group）正确传入 worker，分别转写 mic 轨与 system 轨，再调用 `merge_dual_transcripts(mic_text, sys_text, mic_label="本地", sys_label="远程")`。
3. 合并产物写入结果文件，并通过现有消息协议（`merge_done`）通知主进程。

## Out of Scope
- 本地-N/远程-N 编号标签的最终展示与说话人解析（见 T-G5，本任务只需产出带 `本地`/`远程` 前缀的合并文本）。

## Success Criteria
- [ ] 给定两段带时间戳的转写文本（mic + system），`merge_dual_transcripts` 被实际调用，输出按时间戳升序交错，且 mic 段前缀"本地"、system 段前缀"远程"。
- [ ] 双轨录音 → 转写后，结果文件内容是**时间戳交错**的合并文本，而非简单 `## file` 拼接。
- [ ] worker 合并分支对"双轨对"走 `merge_dual_transcripts`；对"普通多文件"仍走原拼接逻辑（两条路径都有测试）。
- [ ] 新增集成测试 `tests/test_dual_track_merge.py::test_merge_interleaves_by_timestamp` 与 `::test_worker_dual_branch_calls_merge`（可用 mock 转写文本，不需 funasr）通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_dual_track_merge.py -q
```
