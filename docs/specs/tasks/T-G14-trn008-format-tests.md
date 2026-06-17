# T-G14 — 多格式输出测试（含 HTML/CSV/VTT）

- **Tier**: 3
- **关联需求**: TRN-008（多格式输出 MD/TXT/SRT/JSON/HTML/CSV/VTT）
- **依赖**: T-G2
- **预估**: 1 天

## 背景
TRN-008 要求 7 种格式。当前唯一的 formatter 测试 `test_performance_optimization.py::TestFormatters` 被整文件 skip，且仅覆盖 JSON/SRT/TXT/MD。
**HTML/CSV/VTT 三种格式没有任何测试**。注意：HTML 实际在 `transcriber.py:_fmt_html`，srt/csv/vtt 委托给 `formatters.py`，md/txt/json 在 `transcriber.py` 分发（`:1247-1255`）——测试需覆盖两处来源。

## Scope
1. 为全部 7 种格式各写 active 单元测试：给定固定 segments（含说话人、时间戳、中文文本），断言每种格式输出的结构正确：
   - MD：标题/说话人标签；TXT：纯文本含全部文字；SRT：序号+时间码+文本；VTT：`WEBVTT` 头+时间码；JSON：可解析、segments 数正确；HTML：合法标签结构；CSV：表头 + 行数。
2. 边界：空 segments、单 segment、含特殊字符（逗号/引号 for CSV、`<>&` for HTML）。
3. 覆盖两处实现来源（`transcriber._fmt_*` 与 `formatters.TranscriptFormatter.*`）。

## Out of Scope
- 真实转写产出（用固定 segments 即可，不需 funasr）。

## Success Criteria
- [ ] 7 种格式各 ≥1 个 active 测试，全部断言内容结构（非 hasattr）。
- [ ] HTML/CSV/VTT 三种**从无到有**获得测试覆盖。
- [ ] CSV 特殊字符转义、HTML 标签转义有专门断言。
- [ ] 测试不依赖 funasr，可在干净环境运行通过。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_formatters.py -q   # 新建/重建
```
