# 文件映射表

> 本文档记录文档重构前后的文件位置对照，供其他 agent 快速定位文件。
> 重构日期：2026-06-11

---

## 归档文件（不再维护，仅历史参考）

| 原位置 | 归档位置 |
|--------|---------|
| `DEVPLAN_V2.md` | `docs/archive/DEVPLAN_V2.md` |
| `OPTIMIZATION_TODO.md` | `docs/archive/OPTIMIZATION_TODO.md` |
| `Function Comparison/` | `docs/archive/Function Comparison/` |
| `MeetScribe_用户手册.docx` | `docs/archive/` |
| `create_lnk.vbs` | `docs/archive/tools/` |
| `create_shortcut.ps1` | `docs/archive/tools/` |
| `generate_manual.js` | `docs/archive/tools/` |
| `结果.txt` | 已删除 |
| `models/` | 已删除（空目录） |
| `Screenshot file/` | 已删除（空目录） |
| `node_modules/` | 已删除 |
| `package.json` / `package-lock.json` | 已删除 |
| `MeetScribe.lnk` | 已删除 |
| `.pytest_cache/` | 已删除 |
| `.superpowers/` | 已删除 |
| `docs/specs/2026-06-01-performance-optimization-design.md` | `docs/archive/2026-06-01~04/specs/` |
| `docs/superpowers/specs/2026-06-02-*.md` | `docs/archive/2026-06-01~04/specs/` |
| `docs/superpowers/specs/2026-06-03-*.md` | `docs/archive/2026-06-01~04/specs/` |
| `docs/superpowers/specs/2026-06-04-*.md` | `docs/archive/2026-06-01~04/specs/` |
| `docs/superpowers/plans/2026-06-01~04-*.md` | `docs/archive/2026-06-01~04/plans/` |
| `docs/superpowers/specs/2026-06-09-*.md` | `docs/archive/2026-06-09~10/specs/` |
| `docs/superpowers/specs/2026-06-10-ai-settings-*.md` | `docs/archive/2026-06-09~10/specs/` |
| `docs/superpowers/specs/2026-06-10-ui-optimization-round2*.md` | `docs/archive/2026-06-09~10/specs/` |
| `docs/superpowers/specs/2026-06-10-*-review*.md` | `docs/archive/2026-06-09~10/specs/` |
| `docs/superpowers/plans/2026-06-09-*.md` | `docs/archive/2026-06-09~10/plans/` |
| `docs/superpowers/plans/2026-06-10-ui-optimization*.md` | `docs/archive/2026-06-09~10/plans/` |
| `docs/bugs/voiceprint-extraction-failed.md` | `docs/archive/2026-06-01~04/bugs/` |
| `docs/bugs/speaker-count-bug.md` | `docs/archive/2026-06-01~04/bugs/` |
| `docs/bugs/ui-log-duplicate-bug.md` | `docs/archive/2026-06-01~04/bugs/` |
| `docs/bugs/summary-preview-bug.md` | `docs/archive/2026-06-01~04/bugs/` |
| `docs/bugs/transcription-quality-and-voiceprint-matching.md` | `docs/archive/2026-06-01~04/bugs/` |
| `docs/bugs/问题排查记录.md` | `docs/archive/2026-06-01~04/bugs/` |
| `docs/features/voiceprint-*.md` | `docs/archive/2026-06-01~04/` |
| `docs/features/round*-optimization-plan.md` | `docs/archive/2026-06-01~04/` |
| `docs/features/function-comparison-report.md` | `docs/archive/2026-06-01~04/` |
| `docs/features/功能对比分析报告.md` | `docs/archive/2026-06-01~04/` |
| `docs/features/UI日志优化需求.md` | `docs/archive/2026-06-01~04/` |

## 移动文件（整理到正确位置）

| 原位置 | 新位置 |
|--------|--------|
| `test_voiceprint_extraction.py` | `tests/test_voiceprint_extraction.py` |
| `test_voiceprint_fix.py` | `tests/test_voiceprint_fix.py` |
| `test_voiceprint_threshold.py` | `tests/test_voiceprint_threshold.py` |

## 保留文件（当前活跃）

| 文件 | 用途 |
|------|------|
| `README.md` | 项目总览 |
| `ARCHITECTURE.md` | 技术架构 |
| `CHANGELOG.md` | 版本变更 |
| `DEVPLAN_V3.md` | 开发计划（v3） |
| `ERROR_TRACKING.md` | Bug 跟踪 |
| `TEST_REPORT.md` | 测试报告 |
| `docs/user_manual.md` | 用户手册 |
| `docs/vb-audio-cable-setup.md` | VB-Audio 配置 |
| `docs/bugs/INDEX.md` | 活跃 Bug 清单 |
| `docs/features/INDEX.md` | 功能清单 |
| `docs/superpowers/TODO.md` | 当前待办 |
| `docs/superpowers/specs/2026-06-11-ui-optimization-round3*.md` | UI 优化方案 |
| `docs/superpowers/specs/2026-06-10-restructuring-packaging-plan.md` | 打包方案 |
| `docs/superpowers/specs/2026-06-03-transcription-queue-design.md` | 队列设计 |

## Agent 工作区

| Agent | 目录 | 用途 |
|-------|------|------|
| MiMo Code | `docs/agents/mimo-code/` | 主力开发，架构设计 |
| QoderWork | `docs/agents/qoderwork/` | UI/UX 设计，方案评审 |
| Claude Code | `docs/agents/claude-code/` | 辅助开发，代码审查 |
