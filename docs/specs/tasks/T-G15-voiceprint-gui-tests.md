# T-G15 — 声纹 GUI 流 E2E

- **Tier**: 3
- **关联需求**: VPR-002（添加音色）、VPR-003（编辑姓名）、VPR-004（删除说话人）
- **依赖**: T-G2
- **预估**: 1 天

## 背景
- **VPR-003 改名**：只有 `hasattr(VoiceprintLibrary,'rename_speaker')` 烟雾检查（`test_voiceprint_page_e2e.py:44`）。`rename_speaker` 的实际逻辑（冲突检查、embedding/created_at 迁移、保存）**未测**。
- **VPR-004 删除**：库层 `test_voiceprint.py::test_remove_speaker` 有，但 **GUI 确认弹窗 → 删除**路径未测。
- **VPR-002 添加音色**：E2E 里 `_start_recording`/`_stop_recording` 被 mock，真实 record→extract→save 链路未端到端覆盖（提取需 CAM++，可对提取边界做 mock）。

## Scope
1. **VPR-003**：单元测试 `rename_speaker` 的三类行为——成功改名（embedding 迁移、created_at 保留、持久化）、目标名已存在（拒绝）、源名不存在（返回 False）；GUI 集成测试驱动 `_edit_speaker`（mock QInputDialog 返回新名）并断言列表更新。
2. **VPR-004**：GUI 集成测试驱动 `_delete_speaker`（mock QMessageBox 确认）→ 断言 `remove_speaker` 被调用且列表项消失。
3. **VPR-002**：GUI 集成测试驱动 AddVoiceDialog 的 record→extract→save 流程，对 embedding 提取（CAM++）用 mock 返回固定向量，断言最终 `add_speaker` 被以正确 source/quality 调用。

## Out of Scope
- 真实 CAM++ 声纹提取准确率（归 e2e_heavy，本任务用 mock 边界）。

## Success Criteria
- [ ] `rename_speaker` 三类行为各有 active 单测并通过（不依赖 funasr）。
- [ ] VPR-004 GUI 删除确认路径有 qtbot 集成测试，断言库调用 + 列表刷新。
- [ ] VPR-002 录入链路有 qtbot 集成测试（提取用 mock），断言 save 调用参数。
- [ ] 既有 `hasattr` 烟雾测试可保留，但每项需求新增至少一个**行为**测试。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_voiceprint.py tests/test_voiceprint_page.py tests/test_voiceprint_page_e2e.py -q
```
