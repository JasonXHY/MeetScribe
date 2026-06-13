# Agent 协作指南

> 本文档说明各 Agent 的角色分工和协作规则

---

## 角色分工

| Agent | 角色 | 主要职责 | 工作区 |
|-------|------|---------|--------|
| **MiMo Code** | 主力开发 | 架构设计、核心功能开发、Bug 修复、测试 | `docs/agents/mimo-code/` |
| **QoderWork** | UI/UX 设计 | 界面设计、交互方案、设计评审 | `docs/agents/qoderwork/` |
| **Claude Code** | 辅助开发 | 代码审查、文档编写、辅助功能 | `docs/agents/claude-code/` |

## 协作规则

### 1. 文件权限

| 区域 | MiMo Code | QoderWork | Claude Code |
|------|-----------|-----------|-------------|
| `src/` | ✅ 读写 | 📖 只读 | ✅ 读写 |
| `docs/` | ✅ 读写 | ✅ 读写 | ✅ 读写 |
| `tests/` | ✅ 读写 | 📖 只读 | ✅ 读写 |
| `docs/agents/mimo-code/` | ✅ 读写 | 📖 只读 | 📖 只读 |
| `docs/agents/qoderwork/` | 📖 只读 | ✅ 读写 | 📖 只读 |
| `docs/agents/claude-code/` | 📖 只读 | 📖 只读 | ✅ 读写 |
| `docs/superpowers/TODO.md` | ✅ 读写 | ✅ 读写 | ✅ 读写 |
| `docs/superpowers/specs/` | ✅ 读写 | ✅ 读写 | 📖 只读 |

### 2. 公共文件（任何 Agent 都可修改）

- `docs/superpowers/TODO.md` — 当前待办
- `docs/superpowers/specs/` — 设计方案
- `docs/bugs/INDEX.md` — Bug 清单
- `docs/features/INDEX.md` — 功能清单
- `ERROR_TRACKING.md` — Bug 跟踪

修改公共文件时，请在文件末尾的变更记录中署名。

### 3. 工作区用途

每个 Agent 的工作区用于：
- 存放自己的笔记、草稿、中间产物
- 记录自己负责模块的设计思路
- 其他 Agent 可以读取了解上下文

### 4. 提交规范

提交信息格式：
```
<type>(<scope>): <description>

类型:
- feat: 新功能
- fix: Bug 修复
- docs: 文档更新
- refactor: 重构
- test: 测试
- chore: 构建/工具

示例:
feat(voiceprint): 添加声纹嵌入向量持久化
fix(recording): 修复录音按钮状态不恢复
docs(architecture): 更新架构文档
```

## 通信协议

### 设计评审流程

1. QoderWork 编写设计方案 → `docs/superpowers/specs/`
2. MiMo Code 审阅 → 提出修改意见
3. 双方讨论达成一致
4. MiMo Code 实施

### Bug 修复流程

1. 发现 Bug → 记录到 `ERROR_TRACKING.md`
2. MiMo Code 修复 → 提交代码
3. 更新 `ERROR_TRACKING.md` 状态为 ✅

## 注意事项

1. **不要修改 `src/gui/styles.py` 中的常量**（除非确认影响所有 Agent）
2. **不要删除归档目录 `docs/archive/`**（历史记录）
3. **修改 `FILE_MAPPING.md` 时同步更新**（其他 Agent 需要定位文件）
4. **每次会话结束前更新 `docs/superpowers/TODO.md`**（保持状态同步）
