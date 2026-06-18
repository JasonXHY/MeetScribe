# MeetScribe 差距修复任务索引

> 来源：`docs/specs/gap-analysis-and-spec.md`
> 排序：按依赖顺序（Tier 0 → 3）。请按此顺序执行。

每个任务文件包含：背景、范围（Scope）、不在范围内（Out of Scope）、成功标准（Success Criteria，可验证）、依赖、验收测试、预估工作量。

## Tier 0 — 基础设施 / 阻断性 Bug（先做）
| 任务 | 关联需求 | 标题 |
|---|---|---|
| [T-G1](T-G1-dual-track-filename.md) | TRN-011, SPK-008 | 双轨文件名与配对后缀统一 |
| [T-G2](T-G2-e2e-test-infra.md) | 全部 E2E | E2E 测试基础设施 |
| [T-G3](T-G3-set002-config-key.md) | SET-002 | 输出目录 save/restore 配置键统一 |

## Tier 1 — 核心管线接线
| 任务 | 关联需求 | 标题 | 依赖 |
|---|---|---|---|
| [T-G4](T-G4-dual-track-merge-wiring.md) | TRN-011 | 双轨按时间戳合并接入 worker | G1 |
| [T-G5](T-G5-spk008-local-remote-labels.md) | SPK-008 | 本地-N/远程-N 标注端到端 | G4 |
| [T-G6](T-G6-ai003-speaker-namer-wiring.md) | AI-003 | 发言人姓名提取接入管线 | — |
| [T-G7](T-G7-file004-incremental-update.md) | FILE-004 | 文件列表增量更新 | — |

## Tier 2 — 功能补全
| 任务 | 关联需求 | 标题 | 依赖 |
|---|---|---|---|
| [T-G8](T-G8-ai005-ollama.md) | AI-005, SET-016 | Ollama 本地 LLM 端到端 + 地址输入 | G6 |
| [T-G9](T-G9-ai006-voiceprint-injection.md) | AI-006 | 音色库匹配注入摘要端到端 | — |
| [T-G10](T-G10-file-delete-source-and-merge-badge.md) | FILE-002, FILE-006 | 删除源文件选项 + 📎 合并显示 | G7 |
| [T-G11](T-G11-ui011-first-launch.md) | UI-011 | 首次启动引导真实化 | — |
| [T-G12](T-G12-spec-deviation-fixes.md) | 多项 | 验收标准偏差批量校正 | — |

## Tier 3 — 测试覆盖补强 ✅ 已完成
| 任务 | 关联需求 | 标题 | 依赖 | 状态 |
|---|---|---|---|---|
| [T-G13](T-G13-rec-tests.md) | REC-001~010 | 录音链路单测 + E2E | G2 | ✅ `test_recorder.py` |
| [T-G14](T-G14-trn008-format-tests.md) | TRN-008 | 多格式输出测试 | G2 | ✅ `test_formatters.py` |
| [T-G15](T-G15-voiceprint-gui-tests.md) | VPR-002/003/004 | 声纹 GUI 流 E2E | G2 | ✅ `test_voiceprint_gui_flow.py` |
| [T-G16](T-G16-settings-ai-spk-tests.md) | SET-007/014, AI-002, SPK-* | 设置/纠错/发言人弹窗测试 | G2 | ✅ `test_settings_dialogs_g16.py` + `test_ai_service.py` |
| [T-G17](T-G17-fix-stale-tests.md) | 既有套件 | 修复 stale 测试 | G2 | ✅ 删除 `test_performance_optimization.py`（见 `tests/MIGRATION_*.md`） |
