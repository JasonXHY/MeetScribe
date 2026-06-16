# T-G9 — 音色库匹配注入摘要端到端

- **Tier**: 2
- **关联需求**: AI-006（音色库匹配结果注入摘要）
- **依赖**: 无（VPR-006 已实现；本任务补端到端串联与测试）
- **预估**: 0.5 天

## 背景
`src/ai_service.py:211 generate_summary(voiceprint_matches=...)` 会构建"已识别说话人"段落（`:229-234`），
调用方在 `transcription.py:519` 传入 `self._voiceprint_match_results`。
两半都存在，但**从未端到端串联测试**：`test_transcription.py:206` 只断言 `_voiceprint_match_results` 被填充，
摘要 E2E（`TestAISummary`）调 `generate_summary` 时**不传 `voiceprint_matches`**，注入段落从未被验证。

## Scope
1. 确认转写完成 → 声纹匹配（`_match_voiceprints`）→ 摘要生成（`_generate_summary`）链路中，`_voiceprint_match_results` 被正确传入 `generate_summary`。
2. 补端到端测试：匹配结果 → 注入 prompt → 摘要含"已识别说话人"段落（用 mock AIService 捕获传入的 `voiceprint_matches` 并断言 prompt 内容）。
3. 验证空匹配时不注入空段落、不报错。

## Out of Scope
- 声纹匹配算法本身（VPR-006 已覆盖）。

## Success Criteria
- [ ] 集成测试：构造 `_voiceprint_match_results = {0: {"name":"张三","confidence":"confirmed"}}`，触发摘要路径，断言 `generate_summary` 收到的 `voiceprint_matches` 含张三，且生成的 system/user prompt 含"已识别说话人"段落。
- [ ] 空匹配时 `voiceprint_matches` 为空，摘要正常生成且无空段落。
- [ ] 新增 `tests/test_transcription.py::TestSummaryVoiceprintInjection::test_matches_passed_to_summary`（mock AIService，不需网络）通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_transcription.py -q
```
