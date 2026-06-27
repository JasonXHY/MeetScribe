# T-G13 — 录音链路单测 + E2E

- **Tier**: 3（测试覆盖）
- **关联需求**: REC-001 ~ REC-010
- **依赖**: T-G2（测试基础设施）
- **预估**: 1.5 天

## 背景
录音链路当前**零有效覆盖**：所有 recorder 单测（lock、`get_elapsed`、pause/resume、即时反馈、模式切换）都在被整文件 skip 的 `test_performance_optimization.py` 里；E2E 里 `recorder.start` 被 mock（`test_tdd_flows.py:174`），`ask_transcribe_after_record` 也被 mock。没有任何测试断言 16kHz/mono/WAV 输出、计时器、模式、VB-Cable 回退。

## Scope
为 REC 各项建立可在干净环境运行的测试（用 T-G2 的合成 WAV + 对 pyaudio 的 mock 边界）：
1. **REC-001/008**：录音保存的 WAV 为 16kHz、单声道、PCM16（可对 `_stop_and_save` 写出的文件用 `soundfile`/`wave` 读回断言参数，pyaudio 采集用 mock 注入帧）。
2. **REC-002**：停止后文件完整、可读。
3. **REC-003**：pause/resume 线程安全 + 暂停期间不累加录音时长（从 skip 文件迁移这些已有用例并解除 skip）。
4. **REC-004**：`get_elapsed` 单调、`update_timer` 格式 MM:SS。
5. **REC-005/006**：mic 模式产出 1 个文件，dual 模式产出 2 个文件且命名符合 T-G1 约定。
6. **REC-007**：VB-Cable 优先、不存在时回退 WASAPI（mock 设备枚举，断言分支）。
7. **REC-009**：停止后触发"询问转写"（不 mock 掉该逻辑，断言弹窗被调用）。
8. **REC-010**：命名符合 T-G12 校正后的格式。

## Out of Scope
- 真实麦克风采集（CI 无设备）——用 mock 注入音频帧。

## Success Criteria
- [ ] REC-001~010 每项至少一个 active 测试（不在 skip 文件中），断言需求本质而非 hasattr。
- [ ] 测试在仅装轻依赖（PySide6+numpy+soundfile）的环境运行通过，对 pyaudio/pyaudiowpatch 用 mock。
- [ ] `test_performance_optimization.py` 中仍有效的 recorder 用例被迁移到 active 文件并通过（与 T-G17 协调）。
- [ ] 覆盖：VB-Cable 回退分支、双轨双文件、暂停不计时三个关键点各有专门断言。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_recorder.py -q   # 新建
```
