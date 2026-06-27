# T-G2 — E2E 测试基础设施

- **Tier**: 0（基础设施）
- **关联需求**: 全部需要 E2E 覆盖的需求（是 Tier 3 所有测试任务的前置）
- **依赖**: 无
- **预估**: 2 天

## 背景
当前唯一的 E2E 套件 `tests/test_tdd_flows.py` 无法在干净环境稳定运行：
1. 引用 `tests/fixtures/test_meeting_16min.wav` / `test_meeting_34min.wav`，**仓库中不存在**（`FileNotFoundError`）。
2. 真实转写依赖 funasr + CAM++ 模型（约 2GB），CI 不具备。
3. AI 摘要 E2E 直连真实云端 API 且**硬编码 Key**（`test_tdd_flows.py:384`），不可重放、不安全。
4. 无 `pytest.ini` / CI 配置；GUI 测试需手动设 `QT_QPA_PLATFORM=offscreen`。

## Scope
1. **分层测试标记**：定义 pytest markers —
   - `unit`（无外部依赖，CI 必跑）
   - `integration`（需 PySide6/qtbot，offscreen 可跑，CI 跑）
   - `e2e_heavy`（需 funasr/模型/真实音频，默认 skip，本地手动跑）
   - `e2e_network`（需真实 API Key，默认 skip）
   在 `conftest.py` 注册，并对 heavy/network 用 `pytest.mark.skipif(env 未配置)`。
2. **测试音频 fixture**：提供小体积可生成的合成 WAV（如用 numpy 写 5 秒 16kHz 正弦/白噪），放 `tests/fixtures/` 或在 fixture 中按需生成，替代缺失的大文件。供"轻量集成"用（不要求 ASR 准确率）。
3. **可注入的转写后端**：为 `TranscriptionHandler` 提供可替换的 worker/AIService 注入点（或用 mock 边界），让管线流程（消息协议、状态流转、`_match_voiceprints`、`_on_done`）可在**不加载真实模型**下做集成测试。
4. **`pytest.ini`**：默认 `QT_QPA_PLATFORM=offscreen`、`addopts = -q -m "unit or integration"`、注册 markers。
5. **CI 骨架**：GitHub Actions workflow，在 PySide6 + 轻依赖环境跑 `unit + integration`，heavy/network 不跑。

## Out of Scope
- 具体需求的测试用例编写（见 Tier 3 各任务，它们消费本任务产出的 fixture/markers）。

## Success Criteria
- [ ] `pytest -m "unit or integration"` 在仅装 `PySide6 numpy soundfile openai pytest pytest-qt` 的干净环境下**全绿、不崩溃、不 FileNotFound**。
- [ ] `tests/test_tdd_flows.py` 中依赖真实音频/模型/网络的用例被正确标记，未配置环境时显示 `skipped` 而非 `failed`/`error`。
- [ ] 提供 `synthetic_wav` fixture，集成测试可用它驱动"加文件→状态流转→（mock 转写）→结果"流程而不需 funasr。
- [ ] 仓库新增 `pytest.ini` 与 `.github/workflows/ci.yml`（或等价 CI 配置），CI 在 PR 上自动运行 unit+integration。
- [ ] 移除 `test_tdd_flows.py` 中硬编码的 API Key，改从环境变量读取（缺失则 skip）。

## Verification
```bash
python3.12 -m venv /tmp/clean && /tmp/clean/bin/pip install PySide6 numpy soundfile openai pytest pytest-qt
QT_QPA_PLATFORM=offscreen /tmp/clean/bin/python -m pytest -m "unit or integration" -q   # 期望全绿
```
