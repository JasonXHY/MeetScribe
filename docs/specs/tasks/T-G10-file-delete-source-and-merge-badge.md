# T-G10 — 删除源文件选项 + 📎 合并显示

- **Tier**: 2
- **关联需求**: FILE-002（删除文件：可选删源文件）、FILE-006（合并文件显示：📎 前缀 + group_id）
- **依赖**: T-G7（增量更新视图，徽标在新视图中实现）
- **预估**: 1 天

## 背景
- **FILE-002**：当前 `_delete_selected`/`_delete_single`（`home_page.py:475/582`）只从列表移除，**无"是否同时删除磁盘源文件"选项**（spec 要求"确认弹窗，可选是否删除源文件"）。
- **FILE-006**：`group_id` 数据模型已存在（`file_manager.py:270 create_merged_group`，`app.py:362` 调用），但活动视图**无 📎 前缀分组**——📎 只在死代码 `file_list_view_old.py:278,446`。

## Scope
1. **FILE-002**：删除确认弹窗增加复选框"同时删除磁盘源文件"。勾选则 `os.remove` 源文件（带异常保护：文件不存在/占用时记录并继续）；不勾选则仅移除列表项（现行为）。
2. **FILE-006**：在活动 `file_list_view.py` 中，对属于合并组（`group_id` 非空）的行显示 📎 前缀或视觉分组标识，使双轨/合并文件在视觉上归组。

## Out of Scope
- 合并组的拖拽重排（与 UI-010 相关，见 T-G12）。

## Success Criteria
- [ ] 删除确认弹窗含"删除磁盘源文件"复选框；勾选后源文件确实被删除，未勾选则源文件保留。
- [ ] 删除磁盘文件失败（不存在/占用）时不崩溃，记录日志，列表项仍被移除。
- [ ] 合并组文件在列表中带 📎（或等价分组视觉），`group_id` 相同的文件可辨识为一组。
- [ ] 新增单元测试 `tests/test_file_manager.py::test_remove_file_with_source_deletion` 与集成测试 `tests/test_file_list.py::test_merged_group_shows_badge`（qtbot）通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_file_manager.py tests/test_file_list.py -q
```
