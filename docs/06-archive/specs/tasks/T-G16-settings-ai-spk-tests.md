# T-G16 — 设置/纠错/发言人弹窗测试

- **Tier**: 3
- **关联需求**: SET-007/SET-014（API Key 密码 + 明文切换）、AI-002（LLM 纠错行为）、SPK-002（批量替换）、SPK-003（音色库选择）、SPK-005（保存到音色库）、SPK-007（中间片段提取）
- **依赖**: T-G2
- **预估**: 1.5 天

## 背景
以下要么零测试、要么仅 hasattr：
- **SET-007/014**：明文/密文切换 `_toggle_api_key`（`settings_page.py:279`）**无测试**。
- **AI-002**：`generate_correction` 的纠错行为**无任何测试**，只有线程派发 mock。
- **SPK-002 批量替换**：`_do_batch_replace`（`dialogs.py:523`）**无测试**。
- **SPK-003/005/007**：仅 `hasattr`（`test_dialogs_p0.py`）。

## Scope
1. **SET-007/014**：集成测试驱动 `_toggle_api_key`，断言 `_api_key_entry.echoMode()` 在 Password ↔ Normal 间正确切换，图标随之变化。
2. **AI-002**：单元测试 `generate_correction`——用 mock OpenAI 客户端返回固定纠错文本，断言：分块逻辑（`_split_transcript_chunks`）、保留说话人标签/时间戳、空输入与 API 失败时安全返回（不抛）。
3. **SPK-002**：单元/集成测试 `_do_batch_replace`，断言选定旧名→新名后所有匹配条目被替换。
4. **SPK-003**：测试音色库下拉选择后 entry 被填充（`_on_voiceprint_select`）。
5. **SPK-005**：测试 `_save_to_library` 调用 `library.add_speaker`（mock library）。
6. **SPK-007**：测试 `_extract_middle_segment_embedding` 的片段选择逻辑（最长发言 + 居中窗口；与 T-G12 对 SPK-007 的决策一致）。

## Out of Scope
- 真实 API 调用（全部 mock）。

## Success Criteria
- [ ] 上述每项需求至少一个 active 行为测试通过（非 hasattr/源码文本读）。
- [ ] AI-002 纠错测试覆盖：分块、标签保留、失败降级三点。
- [ ] SET-014 明文切换测试断言 `echoMode` 实际翻转。
- [ ] SPK-002 批量替换测试断言多条目被替换。
- [ ] 全部不依赖网络/funasr，可在干净环境运行。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_settings_engine.py tests/test_ai_service.py tests/test_dialogs_p0.py -q
```
