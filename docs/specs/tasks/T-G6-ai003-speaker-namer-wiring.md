# T-G6 — 发言人姓名提取接入管线

- **Tier**: 1
- **关联需求**: AI-003（发言人姓名提取：正则 + LLM 兜底）
- **依赖**: 无
- **预估**: 1 天

## 背景
`src/speaker_namer.py` 完整实现了正则提取（`extract_names_regex:90`）+ LLM 兜底（`extract_names:134` → `ai_service.extract_speaker_names:292`），
但 **grep 显示 `SpeakerNamer` / `extract_names` 在 `src/` 中除自身文件外没有任何调用方**——是死代码。
当前摘要靠 LLM prompt 顺带推断姓名，AI-003 的"正则 + LLM 兜底"独立能力在端到端流程中并未被使用，且零测试覆盖。

## Scope
1. 在转写后处理流程（`src/gui/transcription.py`，摘要/纠错附近）接入 `SpeakerNamer`：从转写文本提取 Speaker→真实姓名映射。
2. 将提取到的映射应用到转写结果与说话人映射（复用现有 `apply_speaker_mapping` / `file_manager.update_speaker_names`）。
3. 明确与声纹自动匹配（VPR-006）、摘要注入（AI-006）的优先级关系：声纹高置信匹配 > 姓名提取 > 保留 Speaker N。
4. 正则优先；正则无果且配置启用云端/Ollama 时走 LLM 兜底。

## Out of Scope
- Ollama 本身的接线（见 T-G8）；本任务只需保证"有可用 AIService 时能走 LLM 兜底"。

## Success Criteria
- [ ] `SpeakerNamer` 在转写完成路径被实际调用（grep 能看到 `transcription.py` 引用）。
- [ ] 给定含"我是张三/这位是李四"等线索的转写文本，正则路径能产出 `{Speaker N: 姓名}` 映射并应用到结果文件。
- [ ] 正则无果时，若配置了 AI 服务，则调用 `extract_speaker_names` 兜底；无 AI 服务时安全跳过（不报错）。
- [ ] 优先级正确：已被声纹 confirmed 命名的说话人不被姓名提取覆盖。
- [ ] 新增单元测试 `tests/test_speaker_namer.py`（正则用例，纯函数，不需 funasr）+ 集成测试验证管线接线（mock AIService）。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_speaker_namer.py tests/test_transcription.py -q
```
