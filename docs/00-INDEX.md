# 文档索引

> 最后更新：2026-06-27
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

## 最近更新

| 日期 | 文件 | 说明 |
|------|------|------|
| 2026-06-27 | 03-reports/2026-06-27-review-full-code-audit.md | 全面代码审查（P0×2 + P1×10 + P2×12 + P3×10 + 6 项架构优化） |
| 2026-06-26 | 02-plans/2026-06-26-plan-test-architecture-revamp.md | 测试架构重构方案（42→15 文件，360 弹窗解决，前端场景测试） |
| 2026-06-26 | 02-plans/2026-06-26-plan-qoder-handoff.md | 交接文档（含 Qoder 审查意见，打包路径修复方案） |
| 2026-06-26 | 04-guides/2026-06-26-guide-execution-rules.md | 创建执行准则指南 |
| 2026-06-26 | 00-INDEX.md | 重构文档目录结构 |

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
