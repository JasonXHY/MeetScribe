# T-G8 — Ollama 本地 LLM 端到端 + 地址输入

- **Tier**: 2
- **关联需求**: AI-005（本地 LLM 支持）、SET-016（本地 LLM 配置：地址输入）
- **依赖**: T-G6（姓名提取接线，是 Ollama 的主要消费场景之一）
- **预估**: 1.5 天

## 背景
- `src/ai_service.py:91 ollama_client` 与 `extract_speaker_names` 的 Ollama 分支存在，但 `_get_ai_service`（`transcription.py:457`）**从不向 `AIService` 传 `ollama_url/ollama_model`**。
- 设置页只有"关闭 / Ollama 本地"开关 combo（`settings_page.py:254-258`），**没有地址输入框**（SET-016 要求"QCheckBox + 地址输入"）。
- 结果：Ollama 路径端到端不可用。

## Scope
1. 设置页新增 Ollama 配置：启用开关 + 服务地址输入框（默认 `http://localhost:11434/v1`）+ 模型名输入（默认 `qwen3:1.7b`）。保存/恢复进 config。
2. `_get_ai_service` 读取 config 中的 ollama 配置并透传给 `AIService(ollama_url=…, ollama_model=…)`。
3. 当用户选择"本地 LLM"模式时，纠错/姓名提取/（可选）摘要走 Ollama 客户端而非云端。
4. 未配置/不可达时给出明确日志与降级（不崩溃）。

## Out of Scope
- 摘要是否也走 Ollama 可作为可选项；最小交付覆盖 AI-003 姓名提取走 Ollama。

## Success Criteria
- [ ] 设置页存在 Ollama 地址输入框，保存后重启回填（roundtrip 测试）。
- [ ] `_get_ai_service` 在启用 Ollama 时构造的 `AIService` 的 `ollama_url/ollama_model` 等于 config 值（可用 mock 断言）。
- [ ] 选择本地 LLM 模式时，调用走 `ollama_client`（mock OpenAI 客户端，断言 base_url 指向 ollama 地址）。
- [ ] Ollama 不可达时记录 warning 并降级，不抛未捕获异常。
- [ ] 新增单元测试 `tests/test_ai_service.py::test_ollama_client_uses_configured_url` 与 `tests/test_settings_engine.py::test_ollama_address_save_restore` 通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_ai_service.py tests/test_settings_engine.py -q
```
