# T-G7 — 文件列表增量更新

- **Tier**: 1
- **关联需求**: FILE-004（文件列表增量更新）
- **依赖**: 无
- **预估**: 1.5 天

## 背景
spec 要求"不全量重建，只更新变化部分"。但活动视图 `src/gui/file_list_view.py:193 _refresh_table`
每次 `setRowCount` + 重建所有行；`home_page.refresh_file_list:828` 每次调用都全量重建。
增量更新逻辑只存在于**未被引用的死文件** `src/gui/file_list_view_old.py:179`。
后果：列表大时刷新有可见卡顿/闪烁，且转写状态频繁变更时重复全量重建（与 FILE-008 异步时长、转写进度刷新叠加放大）。

## Scope
1. 在活动的 `file_list_view.py` 中实现按 `file_path` 主键的增量更新：
   - 新增文件 → 追加行；
   - 删除文件 → 移除对应行；
   - 状态/时长/主题变化 → 只更新该行的相关单元格与按钮可见性，不重建整表。
2. 维护 `file_path → row widgets` 映射；`refresh(files)` 计算 diff 后增量应用。
3. 复用（或从 `file_list_view_old.py` 移植后清理）已验证过的行级方法思路，但适配当前 PySide6 `QTableWidget` 结构。
4. 删除死文件 `file_list_view_old.py`（确认无引用后）。

## Out of Scope
- 📎 合并显示徽标（见 T-G10）。

## Success Criteria
- [ ] 连续两次 `refresh(files)`，若 files 未变，则**不重建任何行**（可通过记录控件 id 不变来断言）。
- [ ] 单个文件状态 PENDING→DONE 时，只该行按钮/状态文本更新，其它行控件实例保持不变。
- [ ] 新增/删除单个文件时，只对应行被加/删。
- [ ] `file_list_view_old.py` 被删除，且 `grep file_list_view_old src/` 无结果。
- [ ] 新增集成测试 `tests/test_file_list.py::test_incremental_update_keeps_unchanged_rows`（qtbot，不需 funasr）通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_file_list.py -q
```
