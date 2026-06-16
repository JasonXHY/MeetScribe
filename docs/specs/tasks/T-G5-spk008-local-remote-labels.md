# T-G5 — 本地-N/远程-N 标注端到端

- **Tier**: 1
- **关联需求**: SPK-008（双轨说话人解析）
- **依赖**: T-G4（依赖时间戳合并产出带本地/远程前缀的文本）
- **预估**: 1 天

## 背景
`src/dual_track_merge.py:108 get_speaker_names_from_merged` 与 SpeakerDialog 的双轨解析
（`src/gui/dialogs.py:1046 _parse_speakers_text`）能解析"本地-N / 远程-N"标签，
解析侧已有单测（`test_dialogs_p0.py::test_dual_track_local_remote` 等）。
但由于 T-G4 之前合并产物不带本地/远程语义，**端到端没有"本地-N/远程-N"标签产出**——解析能力没有可消费的输入。

## Scope
1. 确保双轨合并产物中，每个说话人被标注为 `本地-N`（用户麦克风轨）或 `远程-N`（系统音频轨），N 为该轨内的说话人序号。
2. 让发言人管理弹窗（SpeakerDialog）在双轨结果上正确解析并显示这些标签（复用现有 `_parse_speakers_text`）。
3. 文件列表/预览中显示的说话人标识与合并文本一致。

## Out of Scope
- 声纹库自动命名（VPR-006 已实现，独立）。

## Success Criteria
- [ ] 双轨合并结果中，mic 轨说话人显示为 `本地-1/本地-2…`，system 轨为 `远程-1/远程-2…`。
- [ ] 在双轨结果上打开发言人管理弹窗，能列出所有"本地-N/远程-N"条目并可逐个命名。
- [ ] 端到端：从（mock）双轨转写文本 → 合并 → 解析 → 弹窗条目，标签正确。
- [ ] 集成测试 `tests/test_dialogs_p0.py` 既有双轨解析用例仍通过，且新增 `tests/test_dual_track_merge.py::test_local_remote_labels_end_to_end` 通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_dialogs_p0.py tests/test_dual_track_merge.py -q
```
