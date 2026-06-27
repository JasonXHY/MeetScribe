# T-G1 — 双轨文件名与配对后缀统一

- **Tier**: 0（阻断性 Bug）
- **关联需求**: TRN-011（双轨合并转写）、SPK-008（双轨说话人解析）
- **依赖**: 无
- **预估**: 0.5 天

## 背景
录音器保存系统音频轨为 `{ts}会议_系统音频.wav`（`src/unified_recorder.py:230`），
但 `find_dual_track_pair` 只识别 `_sys` 后缀（`src/dual_track_merge.py:94,101`）。
两者不一致，导致**录制出的双轨文件永远无法自动配对**，TRN-011 / SPK-008 在真实录音场景下完全不生效。

## Scope
1. 统一双轨命名约定。选定一种后缀（推荐保留中文可读名 `_系统音频`，因为它已出现在用户可见文件名中），
   并让 `find_dual_track_pair` 与 `create_merged_group` 的配对逻辑识别该后缀。
2. 同步检查所有引用配对逻辑的位置：`src/gui/home_page.py:797-815`（`_start_transcription` 自动配对）、
   `src/gui/app.py:362`（`_handle_stop_complete` 创建合并组）。
3. 保持向后兼容：同时识别历史 `_sys` 后缀（若已有用户数据）。

## Out of Scope
- 时间戳合并算法本身的接线（见 T-G4）。
- 本地/远程标签生成（见 T-G5）。

## Success Criteria
- [ ] 给定一对真实录制文件 `250616xx会议.wav` + `250616xx会议_系统音频.wav`，`find_dual_track_pair("…会议.wav")` 返回该配对，`find_dual_track_pair("…会议_系统音频.wav")` 也返回同一配对。
- [ ] 双轨录音停止后，`FileManager` 中能看到一个合并组（`group_id` 非空，含两个 source）。
- [ ] 历史 `_sys` 后缀仍可被识别（向后兼容）。
- [ ] 新增单元测试 `tests/test_dual_track_merge.py::test_find_pair_chinese_suffix` 与 `::test_find_pair_legacy_sys_suffix` 均通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_dual_track_merge.py -q
```
- 不依赖 funasr/pyaudio（纯文件名/路径逻辑），可在干净环境运行。
