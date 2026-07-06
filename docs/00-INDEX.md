# 文档索引

> 最后更新：2026-07-03
> 用途：AI Agent 文档导航入口

## 快速查找

| 类型 | 目录 | 用途 | Agent 何时读取 |
|------|------|------|---------------|
| 需求规格 | 01-specs/ | 了解项目需求和设计 | 做技术决策时 |
| 实施方案 | 02-plans/ | 查看执行计划 | 执行任务前 |
| 复盘报告 | 03-reports/ | 回顾已完成工作 | 总结进度时 |
| 开发指南 | 04-guides/ | 查看开发规范 | 新会话开始 |
| 问题记录 | 05-issues/ | 排查当前问题 | 排查 bug 时 |
| 历史归档 | 06-archive/ | 查看历史文档 | 需要参考时 |
| 原型文件 | 99-mockups/ | 查看 UI 原型 | UI 开发时 |

## 版本说明

本项目分两个大版本，文档通过文件名前缀区分：

| 版本 | 定位 | 文档前缀 | 说明 |
|------|------|---------|------|
| **v1.x** | 当前版本（PySide6 + 本地 FunASR） | 无前缀 | 维护模式，仅修 bug |
| **v2.0-C** | C 版（To C，轻量化，云端 ASR + 本地声纹） | `v2.0-c-` | 新架构，Tauri + 云端 API |
| **v2.0-B** | B 版（To B，企业内网，数据不出内网） | `v2.0-b-` | C/S 架构，FunASR Server |
| **v2.0-通用** | 两版共享的需求/资源 | `v2.0-` | 无 C/B 后缀 |

## 最近更新

| 日期 | 文件 | 版本 | 说明 |
|------|------|------|------|
| 2026-07-03 | 01-specs/2026-07-03-spec-v2.0-requirements.md | v2.0-通用 | v2.0 需求规格（C/B 双版本） |
| 2026-07-03 | 02-plans/2026-07-03-plan-v2.0-c-version-architecture.md | v2.0-C | C 版架构设计 |
| 2026-07-03 | 03-reports/2026-07-03-report-v2.0-tech-validation.md | v2.0-通用 | 技术路线验证（CAM++ ONNX、fbank Rust、MiMo ASR） |
| 2026-07-03 | 04-guides/2026-07-03-guide-v2.0-resources.md | v2.0-通用 | 相关资料索引（云端厂商、Rust 生态、模型资源） |
| 2026-07-03 | 02-plans/2026-07-03-plan-p2-code-quality.md | v1.x | P2 代码质量改进 8 项 |
| 2026-07-03 | 02-plans/2026-07-03-plan-scenario-testing.md | 业务场景自动化测试方案（23 个测试，S1-S8，含真实 FunASR E2E） |
| 2026-07-03 | 02-plans/2026-07-03-plan-status-button-optimization.md | 转写停止状态与按钮优化（4 个修复点） |
| 2026-07-03 | 04-guides/2026-07-03-guide-document-organization.md | 文档组织方法论（可跨项目复用） |
| 2026-07-03 | 05-issues/2026-07-03-issue-dual-track-merge-voiceprint.md | 双轨合并文本丢失 + 声纹误匹配排查 |
| 2026-07-02 | 02-plans/2026-07-02-plan-transcription-timeout-fix.md | 转写超时 5 项修复方案 |
| 2026-07-02 | 05-issues/2026-07-02-issue-transcript-quality.md | 转写质量问题排查报告 |

## 按任务查找

### 打包相关
- 交接文档（含审查意见）：`02-plans/2026-06-26-plan-qoder-handoff.md`
- 执行准则：`04-guides/2026-06-26-guide-execution-rules.md`
- 打包规则：见 MEMORY.md → domains/rules/packaging.md

### 权限问题
- Program Files 写入权限：见 MEMORY.md → domains/issues/active.md

### 记忆重构
- 记忆管理规范：见全局 MEMORY.md → 记忆文件管理规范

### UI 开发
- 设计系统：`01-specs/2026-06-11-spec-design-system.md`
- UI 重设计：`04-guides/2026-06-14-guide-ui-redesign.md`
- 原型文件：`99-mockups/`

### 测试相关
- 测试架构重构：`02-plans/2026-06-26-plan-test-architecture-revamp.md`
- 测试评估：`03-reports/2026-06-14-report-test-evaluation.md`
- 测试方法：`03-reports/2026-06-14-report-test-methodology.md`

### Bug 修复
- 全面代码审查：`03-reports/2026-06-27-review-full-code-audit.md`
- v1.0 Bug 修复：`02-plans/2026-06-14-plan-v1.0-bugfix.md`
- 修复记录：`05-issues/`

### v2.0 重构（C 版 / B 版）
- **项目总计划：** `02-plans/2026-07-03-plan-v2.0-c-version-project.md`（必读，含完整任务拆解和协作分工）
- 需求规格：`01-specs/2026-07-03-spec-v2.0-requirements.md`
- C 版架构设计：`02-plans/2026-07-03-plan-v2.0-c-version-architecture.md`
- 技术验证报告：`03-reports/2026-07-03-report-v2.0-tech-validation.md`
- 资料索引：`04-guides/2026-07-03-guide-v2.0-resources.md`

## 目录结构说明

```
docs/
├── 00-INDEX.md              # 本文件（Agent 入口）
├── 01-specs/                # 需求规格
│   ├── _index.md
│   └── 2026-06-11-spec-*.md
├── 02-plans/                # 实施方案
│   ├── _index.md
│   └── 2026-06-*-plan-*.md
├── 03-reports/              # 复盘报告
│   ├── _index.md
│   └── 2026-06-*-report-*.md
├── 04-guides/               # 开发指南
│   ├── _index.md
│   └── 2026-06-*-guide-*.md
├── 05-issues/               # 问题记录
│   ├── _index.md
│   └── 2026-06-*-fix-*.md
├── 06-archive/              # 历史归档
│   ├── migration-gaps/
│   ├── old-plans/
│   ├── old-reports/
│   └── specs/
└── 99-mockups/              # 原型文件
    └── mockup-*.html
```

## 文件命名规范

格式：`[日期]-[类型]-[简述].md`

类型代码：
- `spec` = 需求规格
- `plan` = 实施方案
- `report` = 复盘报告
- `guide` = 开发指南
- `issue` = 问题记录
- `fix` = 修复记录
- `review` = 代码审查

示例：
- `2026-06-26-plan-memory-restructure.md`
- `2026-06-26-report-packaging-review.md`
- `2026-06-26-issue-permission-error.md`
