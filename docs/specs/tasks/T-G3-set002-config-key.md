# T-G3 — 输出目录 save/restore 配置键统一

- **Tier**: 0（数据丢失类 Bug）
- **关联需求**: SET-002（转写输出目录）
- **依赖**: 无
- **预估**: 0.25 天

## 背景
设置页保存"转写输出目录"时写入配置键 `transcript_dir`（`src/gui/settings_page.py:712`），
但构建/恢复时该输入框默认值读取的是 `output_dir`（`settings_page.py:148`）。
两个键不一致 → 用户保存的输出目录在重启后**不会回填到输入框**（看起来设置丢失）。
注意 `app.get_output_dir()` 读的是 `transcript_dir`，所以功能上转写仍用新值，但 UI 显示与持久化语义不一致，易误导。

## Scope
1. 选定单一权威键（推荐 `transcript_dir`，与 `app.get_output_dir()` 及 `config.py` DEFAULTS 一致）。
2. 让设置页的输出目录输入框 **save 与 restore 使用同一个键**。
3. 全局检查 `output_dir` vs `transcript_dir` 的所有读写点，消除二义性；如需向后兼容旧配置，迁移逻辑放 `config.py`。

## Out of Scope
- 录音目录 SET-001（已正确，无需改）。

## Success Criteria
- [ ] 在设置页修改输出目录 → 保存 → 重建 SettingsPage（模拟重启）→ 输入框显示刚才保存的值。
- [ ] `config.get("transcript_dir")` 与设置页显示值一致；不存在"保存到 A 键、读取 B 键"的分裂。
- [ ] 新增/更新单元测试 `tests/test_settings_engine.py::test_output_dir_save_restore_roundtrip` 通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_settings_engine.py -q
```
