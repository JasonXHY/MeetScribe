# T-G17 — 修复 stale 测试

- **Tier**: 3
- **关联需求**: 既有测试套件健康度（可维护性需求 §4.4）
- **依赖**: T-G2
- **预估**: 1 天

## 背景
两处既有测试与当前 PySide6 代码脱节：
1. **`tests/test_performance_optimization.py`**：整文件 `pytestmark = pytest.mark.skip`（第 16 行）。其断言面向已被取代的旧 tkinter/ctk API（`home_page._update_file_row`、`FileListView._format_duration`、`_get_status_text(...)=="等待中"`、旧 `_accept_suggestion` 签名）。这些"覆盖"是虚假的——给人 60 个用例的错觉，实际一个都不跑。
2. **`tests/test_settings_engine.py::TestModelManagement::test_model_status_frame_exists`（第 200 行）**：断言 `_model_status_frame`，但代码里只有 `_model_status_label`（`settings_page.py`）——该用例会 **fail**。

## Scope
1. 审查 `test_performance_optimization.py` 的 60 个用例，逐类处理：
   - 仍有效的（如 `_get_embedding_by_id` 纯函数、FileManager 异步时长）→ 迁移到对应 active 测试文件并解除 skip。
   - 针对旧 tkinter API 的 → 重写为 PySide6 等价断言，或删除（功能已由其它任务覆盖，如 FILE-004 归 T-G7、formatters 归 T-G14、recorder 归 T-G13）。
   - 删除后在该文件留注释说明去向，避免"覆盖错觉"。
2. 修 `test_settings_engine.py::test_model_status_frame_exists`：改为断言真实存在的 `_model_status_label`（或补 `_model_status_frame` 若设计需要）。
3. 与 T-G7/G13/G14 协调，避免重复用例。

## Out of Scope
- 新增需求覆盖（属 T-G13~G16）；本任务只清理既有 stale 测试。

## Success Criteria
- [ ] `test_performance_optimization.py` 不再整文件 skip：要么删除（用例已迁移/被其它任务覆盖），要么其保留用例全部 active 且通过。
- [ ] 不再有"被 skip 但声称覆盖核心功能"的文件；任何故意 skip 都有 `reason` 且不掩盖真实需求缺口。
- [ ] `test_settings_engine.py::test_model_status_frame_exists` 通过（断言与代码一致）。
- [ ] `pytest -m "unit or integration"` 全绿，且 `pytest --collect-only` 不再统计到永不运行的虚假用例。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -m "unit or integration" -q
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_settings_engine.py -q
```
