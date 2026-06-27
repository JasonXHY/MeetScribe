# T-G12 — 验收标准偏差批量校正

- **Tier**: 2
- **关联需求**: REC-010、SET-003/004/008/009、SET-006、SET-011、SPK-006、SPK-007、UI-009、UI-010、FILE-001(格式)
- **依赖**: 无（可与其它 Tier 2 并行）
- **预估**: 2 天

## 背景
一批需求"已实现但行为偏离 spec 验收标准"。每项偏差小，但累积影响一致性与可信度。
本任务集中校正，或——若决定接受偏差——更新 `docs/requirements.md` 使文档与实现一致（二选一，每项需明确决策）。

## Scope（逐项，标注【改代码】或【改文档】二选一）
1. **REC-010**：命名 `YYMMDDHH会议.wav`（`unified_recorder.py:217`）vs spec `MMDDHH会议.wav`。决策：统一格式。
2. **SET-003/004/008/009**：实现为 QComboBox，spec 写 QCheckBox。决策：要么改控件，要么把 spec 验收标准更新为 QComboBox（推荐后者，combo 表达力更强）。
3. **SET-006**：运算设备 CPU/CUDA 硬编码，spec 要"自动检测可用设备"。决策：加检测或降 spec。
4. **SET-011**：VB-Cable 开关无安装状态自动检测（spec 要）。
5. **SPK-006**：实现=累积 confirmed/已知说话人；spec=转写后自动保存**未命名**说话人。语义需对齐（改实现或改 spec）。
6. **SPK-007**：取最长发言**居中 5 秒**；spec="中间 1/3"。对齐算法或降 spec。
7. **UI-009**：实际用 `QMessageBox`；`TranscriptionCompleteDialog` 是死代码。决策：启用专用 dialog 或删除死类并更新 spec。
8. **UI-010**：`MergeOrderDialog` 副标题宣称拖拽但只有上移/下移按钮。决策：实现拖拽或修正副标题文案 + 降 spec。
9. **FILE-001**：文件对话框过滤缺 `aac/wma`（spec 列出）。决策：补格式或降 spec。

## Out of Scope
- SET-002（见 T-G3）、SET-016（见 T-G8）、FILE-002/006（见 T-G10）、UI-011（见 T-G11）。

## Success Criteria
- [ ] 上述 9 项每项有明确决策记录（改代码 or 改文档），并落地。
- [ ] 凡"改代码"项：行为与 spec 验收标准一致，且有对应测试或手动验证记录。
- [ ] 凡"改文档"项：`docs/requirements.md` 对应验收标准已更新，不再与实现冲突。
- [ ] 死代码 `TranscriptionCompleteDialog`（若决定不启用）被删除，无悬挂引用。
- [ ] 回归：`pytest -m "unit or integration"` 全绿。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -m "unit or integration" -q
```
