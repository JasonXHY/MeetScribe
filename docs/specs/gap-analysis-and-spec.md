# MeetScribe — 需求实现 & 测试覆盖差距分析（Spec）

> 版本：v1.0
> 日期：2026-06-16
> 基准文档：`docs/requirements.md` v3.0
> 方法：逐条需求 × 代码实现（file:line）× 单元测试 × 端到端/集成测试 三维核对
> 审计范围：`src/`、`src/gui/`、`tests/`（E2E 基准为 `tests/test_tdd_flows.py`，qtbot + 真实音频 + 全流程）

---

## 0. E2E 测试的判定口径

本报告对"端到端/集成测试"采用**严格定义**：

- ✅ **算 E2E**：通过真实流程贯穿需求——`test_tdd_flows.py` 用 qtbot 驱动真实窗口/真实音频/真实多进程管线，或驱动真实 widget 的完整交互。
- ❌ **不算 E2E**：`hasattr(Class, 'method')`、`类是否存在`、纯 mock 的单元断言、读取源码文本做字符串断言。

> 重要前提：`tests/test_performance_optimization.py` 当前被**整文件 skip**（`pytestmark = pytest.mark.skip`，第 16 行），且其断言面向已被 PySide6 取代的旧 tkinter API（`_update_file_row`/`_format_duration`/旧 `_accept_suggestion` 签名）——**不计入有效覆盖**。`test_voiceprint_threshold.py` 是 `__main__` 诊断脚本，**无 pytest 用例**，不计入覆盖。

---

## 1. 问题一：每条需求是否都有对应的端到端集成测试？

**结论：否。80 条需求中，仅约 9 条具备严格意义的 E2E 覆盖（≈11%）。**

具备真实 E2E 覆盖的需求（全部来自 `test_tdd_flows.py`）：

| 需求 | E2E 证据 |
|---|---|
| TRN-001 单文件转写 | `test_transcription_16min` / `test_transcription_34min`（真实音频跑完整多进程管线） |
| TRN-009 说话人分离 | `test_verify_all_results`（断言真实输出含说话人标签） |
| TRN-012 多进程架构 | `test_transcription_16min`（真实 spawn 子进程 + 轮询） |
| FILE-001 添加文件 | `test_file_appears_after_recording` 等 |
| FILE-007 文件状态跟踪 | `test_file_appears_after_recording`（断言状态流转） |
| UI-001 顶部导航栏 | `test_page_navigation`（qtbot 驱动 `_on_navigate`） |
| UI-002 主页布局 | `test_all_components_exist`（qtbot 断言三区域组件） |
| UI-003 音色库页 | `test_voiceprint_page_loads` / `test_voiceprint_detail_view` |
| AI-001 AI 摘要（弱） | `test_ai_summary_after_transcription`（真实 API，但直调 `generate_summary`，未走 `_on_done` 自动触发路径） |

**部分 E2E（真实流程但只断言"无错误"或未断言需求本质）**：TRN-002（仅单文件批）、TRN-006（消费进度流但不断言百分比）、TRN-010（标点在管线内执行但不断言正确性）、VPR-006（`match()` 真实算分，但 `_match_voiceprints` 仅 mock 驱动）、SET-007/SET-013（qtbot 仅 `hasattr` 控件）。

> 即便是上述 9 条，多数仍依赖真实 funasr 模型 + `tests/fixtures/*.wav`（仓库中**缺失**）+ 真实云端 API Key，在 CI/无依赖环境无法稳定运行。**当前没有任何一条需求拥有"可在干净环境稳定运行的 E2E"。**

---

## 2. 问题二：每条需求是否都已实现？

**结论：否。** 统计（80 条）：

| 状态 | 数量 | 占比 | 说明 |
|---|---|---|---|
| ✅ 已实现 | 56 | 70% | 功能存在且符合验收要点 |
| 🟡 部分实现 / 与 spec 有偏差 | 17 | 21% | 实现存在但行为偏离验收标准，或关键路径未接线 |
| 🔴 未实现 / 静默失效 | 7 | 9% | 功能缺失或代码存在但从不被调用 |

### 🔴 未实现 / 静默失效（7）

| 需求 | 问题 | 证据 |
|---|---|---|
| **TRN-011 双轨合并转写** | 录音存 `{ts}会议_系统音频.wav`，但 `find_dual_track_pair` 只识别 `_sys` 后缀 → 录制的双轨**永远无法自动配对**；且 `merge_dual_transcripts`（按时间戳合并）**从未被 worker 调用**（worker 仅 `## file` 拼接） | `unified_recorder.py:230` vs `dual_track_merge.py:94,101`；`grep merge_dual_transcripts` 仅定义无调用 |
| **SPK-008 双轨说话人解析** | 依赖 TRN-011；`merge_dual_transcripts`/`get_speaker_names_from_merged` 无调用方，本地-N/远程-N 标注端到端不产出 | `dual_track_merge.py:43,108` 无 caller |
| **AI-003 发言人姓名提取** | `speaker_namer.py`（正则+LLM 兜底）完整实现，但**从未被管线导入/调用**——死代码 | `grep SpeakerNamer/extract_names` 在 `src/` 中除自身文件外无引用 |
| **AI-005 本地 LLM（Ollama）** | `_get_ai_service` 从不向 `AIService` 传 `ollama_url/ollama_model`；Ollama 路径依赖 AI-003（也未接线）；无地址输入 UI | `transcription.py:457` 未透传；`ai_service.py:91` 客户端无人调用 |
| **FILE-004 文件列表增量更新** | 活动视图 `file_list_view.py:193` 每次 `setRowCount` 全量重建；增量逻辑只在**未被引用**的 `file_list_view_old.py` | `home_page.py:27` 导入的是 `file_list_view.py` |
| **SET-016 本地 LLM 配置（地址输入）** | 只有 关闭/Ollama 开关 combo，**无地址输入框** | `settings_page.py:254-258` |
| **UI-011 首次启动引导（实际内容）** | 仅引导"模型下载"且**下载是 `time.sleep` 模拟**；未引导 VB-Cable 安装、未引导 API Key 配置（spec 要求） | `first_launch.py:52-57` 模拟 |

### 🟡 部分实现 / 偏离验收标准（17，摘要）

- **REC-010**：命名为 `YYMMDDHH会议.wav`（年月日时），spec 写 `MMDDHH会议.wav`。
- **SET-002**：保存写 `transcript_dir` 键，但恢复读 `output_dir` 键 → 保存的输出目录重启后不回填（**Bug**）。
- **SET-003/004/008/009**：spec 要求 QCheckBox，实现为 QComboBox。
- **SET-006**：CPU/CUDA 硬编码，无"自动检测可用设备"。
- **SET-011**：无 VB-Cable 安装状态自动检测。
- **FILE-002**：缺"可选删除源文件"，仅从列表移除。
- **FILE-006**：group_id 数据存在，但活动 UI 无 📎 前缀分组（只在死代码 old 视图）。
- **SPK-006**：spec=转写后自动保存**未命名**说话人；实现=累积 **confirmed/已知**说话人（语义偏离）。
- **SPK-007**：取最长发言**居中固定 5 秒**，spec 写"中间 1/3"。
- **AI-006**：`generate_summary(voiceprint_matches=...)` 已实现，但调用与匹配结果注入未端到端串联测试。
- **UI-006**：仅文件列表行有 tooltip，其余按钮无。
- **UI-009**：实际用 `QMessageBox`；专用 `TranscriptionCompleteDialog` 是死代码。
- **UI-010**：`MergeOrderDialog` 只有上移/下移按钮，副标题宣称拖拽但**无拖拽实现**。
- 其余：VPR-001/VPR-002（页面在，真实 audio→embedding 链路未 E2E）、TRN-003（合并模式未走真实管线）、SET-007/SET-013（仅 hasattr E2E）。

---

## 3. 问题三：未实现 / 未测试的需求清单（按依赖顺序）

依赖顺序原则：**先修使能性缺陷（阻断下游的 bug/接线）→ 再补功能 → 最后补测试基础设施与覆盖**。

### 依赖层级图

```
Tier 0（基础设施 / 阻断性 Bug，必须先做）
  ├─ G1  双轨文件名 ↔ 配对后缀不一致（阻断 TRN-011 / SPK-008）
  ├─ G2  E2E 测试基础设施缺失（缺 fixtures、依赖真实 API/模型、无 CI 骨架）
  └─ G3  SET-002 配置键 save/restore 不一致（数据丢失类 Bug）
        │
Tier 1（核心管线接线，依赖 Tier 0）
  ├─ G4  TRN-011 双轨按时间戳合并真正接入 worker（依赖 G1）
  ├─ G5  SPK-008 本地-N/远程-N 标注端到端产出（依赖 G4）
  ├─ G6  AI-003 发言人姓名提取接入管线（当前死代码）
  └─ G7  FILE-004 文件列表增量更新（替换全量重建）
        │
Tier 2（功能补全，依赖 Tier 1）
  ├─ G8  AI-005 + SET-016 Ollama 本地 LLM 端到端（依赖 G6）
  ├─ G9  AI-006 音色库匹配注入摘要 端到端串联
  ├─ G10 FILE-002 可选删除源文件 / FILE-006 📎 合并显示
  ├─ G11 UI-011 首次启动引导真实化（VB-Cable + API Key + 真实下载）
  └─ G12 SET/UI 验收偏差批量校正（REC-010 命名、SET-003/004/008/009 控件、UI-009/UI-010 等）
        │
Tier 3（测试覆盖补强，依赖功能稳定）
  ├─ G13 E2E 补齐：录音链路 REC-001~010（当前 0 有效单测/E2E）
  ├─ G14 E2E 补齐：转写多格式 TRN-008（HTML/CSV/VTT 无任何测试）
  ├─ G15 E2E 补齐：声纹 GUI 流（VPR-003 改名 / VPR-004 删除确认 / VPR-002 录入链路）
  ├─ G16 E2E 补齐：设置 SET-007/014 明文切换、AI-002 纠错行为、SPK-002/003/005/007 弹窗
  └─ G17 修复/重写 stale 测试（test_performance_optimization 全 skip、test_settings_engine::_model_status_frame 失败）
```

### 差距条目表（按 Tier / 依赖排序）

| GapID | Tier | 关联需求 | 类型 | 标题 | 依赖 | 任务文件 |
|---|---|---|---|---|---|---|
| G1 | 0 | TRN-011, SPK-008 | Bug | 双轨文件名与配对后缀统一 | — | `tasks/T-G1-dual-track-filename.md` |
| G2 | 0 | 全部 E2E | 基础设施 | E2E 测试基础设施（fixtures + mock + CI 骨架） | — | `tasks/T-G2-e2e-test-infra.md` |
| G3 | 0 | SET-002 | Bug | 输出目录 save/restore 配置键统一 | — | `tasks/T-G3-set002-config-key.md` |
| G4 | 1 | TRN-011 | 功能 | 双轨按时间戳合并接入 worker | G1 | `tasks/T-G4-dual-track-merge-wiring.md` |
| G5 | 1 | SPK-008 | 功能 | 本地-N/远程-N 标注端到端 | G4 | `tasks/T-G5-spk008-local-remote-labels.md` |
| G6 | 1 | AI-003 | 功能 | 发言人姓名提取接入管线 | — | `tasks/T-G6-ai003-speaker-namer-wiring.md` |
| G7 | 1 | FILE-004 | 功能 | 文件列表增量更新 | — | `tasks/T-G7-file004-incremental-update.md` |
| G8 | 2 | AI-005, SET-016 | 功能 | Ollama 本地 LLM 端到端 + 地址输入 | G6 | `tasks/T-G8-ai005-ollama.md` |
| G9 | 2 | AI-006 | 功能/测试 | 音色库匹配注入摘要端到端串联 | — | `tasks/T-G9-ai006-voiceprint-injection.md` |
| G10 | 2 | FILE-002, FILE-006 | 功能 | 删除源文件选项 + 📎 合并显示 | G7 | `tasks/T-G10-file-delete-source-and-merge-badge.md` |
| G11 | 2 | UI-011 | 功能 | 首次启动引导真实化 | — | `tasks/T-G11-ui011-first-launch.md` |
| G12 | 2 | REC-010, SET-003/004/008/009, SET-006/011, SPK-006/007, UI-009/010 | 校正 | 验收标准偏差批量校正 | — | `tasks/T-G12-spec-deviation-fixes.md` |
| G13 | 3 | REC-001~010 | 测试 | 录音链路单测 + E2E | G2 | `tasks/T-G13-rec-tests.md` |
| G14 | 3 | TRN-008 | 测试 | 多格式输出测试（含 HTML/CSV/VTT） | G2 | `tasks/T-G14-trn008-format-tests.md` |
| G15 | 3 | VPR-002/003/004 | 测试 | 声纹 GUI 流 E2E | G2 | `tasks/T-G15-voiceprint-gui-tests.md` |
| G16 | 3 | SET-007/014, AI-002, SPK-002/003/005/007 | 测试 | 设置/纠错/发言人弹窗测试 | G2 | `tasks/T-G16-settings-ai-spk-tests.md` |
| G17 | 3 | 既有套件 | 测试维护 | 修复 stale 测试 | G2 | `tasks/T-G17-fix-stale-tests.md` |

> 每个 GapID 对应一个独立任务文件（见 `docs/specs/tasks/`），含范围（Scope）、明确的成功标准（Success Criteria）、依赖、验收测试。

---

## 4. 附录：完整需求×实现×测试矩阵

图例：实现 ✅ 已实现 / 🟡 部分 / 🔴 无；测试 ✅ 有 / 🟡 弱(hasattr/mock) / ❌ 无；E2E 同口径。

### 3.1 录音 REC
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| REC-001 开始录音 16kHz mono | ✅ | ❌ | 🟡(recorder 被 mock) |
| REC-002 停止录音 | ✅ | ❌ | 🟡 |
| REC-003 暂停/继续 | ✅ | ❌(单测被 skip) | 🟡 |
| REC-004 录音计时器 | ✅ | ❌ | ❌ |
| REC-005 现场会议(mic) | ✅ | ❌ | ❌ |
| REC-006 线上会议(dual) | ✅ | ❌ | ❌ |
| REC-007 VB-Cable 回退 | ✅ | ❌ | ❌ |
| REC-008 录音格式优化 | ✅ | ❌ | ❌ |
| REC-009 完成后询问转写 | ✅ | ❌ | ❌(E2E 中被 mock) |
| REC-010 自动命名 | 🟡(YYMMDDHH≠MMDDHH) | ❌ | ❌ |

### 3.2 转写 TRN
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| TRN-001 单文件转写 | ✅ | 🟡 | ✅ |
| TRN-002 批量转写 | ✅ | ✅ | 🟡(仅单文件批) |
| TRN-003 合并转写 | ✅ | 🟡(数据模型) | ❌ |
| TRN-004 重试转写 | ✅ | ❌ | ❌ |
| TRN-005 停止转写 | ✅ | ❌ | ❌ |
| TRN-006 进度显示 | ✅ | ❌ | 🟡 |
| TRN-007 队列管理 | ✅ | ✅ | ❌ |
| TRN-008 多格式输出 | ✅ | ❌(全 skip;HTML/CSV/VTT 无) | ❌ |
| TRN-009 说话人分离 | ✅ | 🟡 | ✅ |
| TRN-010 标点恢复 | ✅ | 🟡 | 🟡 |
| TRN-011 双轨合并 | 🔴(配对 Bug+未接线) | ❌ | ❌ |
| TRN-012 多进程架构 | ✅ | 🟡 | ✅ |

### 3.3 AI
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| AI-001 AI 摘要 | ✅ | 🟡(真实API) | 🟡 |
| AI-002 LLM 纠错 | ✅ | ❌ | ❌ |
| AI-003 姓名提取 | 🔴(死代码) | ❌ | ❌ |
| AI-004 多厂商 | ✅ | ✅ | 🟡 |
| AI-005 本地 LLM | 🔴(未接线) | ❌ | ❌ |
| AI-006 匹配注入摘要 | ✅ | ❌ | ❌ |

### 3.4 声纹库 VPR
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| VPR-001 管理页面 | ✅ | 🟡 | ✅ |
| VPR-002 添加音色 | ✅ | 🟡 | 🟡(录制被 mock) |
| VPR-003 编辑姓名 | ✅ | 🟡(hasattr) | ❌ |
| VPR-004 删除说话人 | ✅ | ✅(lib) | ❌(GUI 确认未测) |
| VPR-005 持久化 | ✅ | ✅ | 🟡 |
| VPR-006 自动匹配 | ✅ | ✅(mock) | 🟡 |
| VPR-007 质量评分 | ✅ | ✅ | 🟡 |
| VPR-008 去重 | ✅ | ✅ | ❌ |
| VPR-009 FIFO 淘汰 | ✅ | ✅ | ❌ |

### 3.5 发言人管理 SPK
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| SPK-001 管理弹窗 | ✅ | 🟡(hasattr) | ❌ |
| SPK-002 批量替换 | ✅ | ❌ | ❌ |
| SPK-003 音色库选择 | ✅ | 🟡 | ❌ |
| SPK-004 匹配建议 | ✅ | 🟡(管线) | 🟡 |
| SPK-005 保存到音色库 | ✅ | 🟡(lib) | ❌ |
| SPK-006 自动保存音色 | 🟡(语义偏离) | 🟡 | ❌ |
| SPK-007 中间片段提取 | 🟡(5s≠1/3) | 🟡(hasattr) | ❌ |
| SPK-008 双轨解析 | 🔴(无 caller) | ✅(解析侧) | ❌ |

### 3.6 文件管理 FILE
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| FILE-001 添加文件 | ✅(缺aac/wma过滤) | ✅ | ✅ |
| FILE-002 删除文件 | 🟡(无删源) | ✅(列表) | ❌ |
| FILE-003 清空列表 | ✅ | ✅ | ❌ |
| FILE-004 增量更新 | 🔴(全量重建) | ❌ | ❌ |
| FILE-005 历史持久化 | ✅ | 🟡(无 round-trip) | ❌ |
| FILE-006 合并显示 | 🟡(无📎) | ❌ | ❌ |
| FILE-007 状态跟踪 | ✅ | ✅ | ✅ |
| FILE-008 异步时长 | ✅ | ✅ | ❌ |

### 3.7 设置 SET
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| SET-001 录音目录 | ✅ | ❌ | ❌ |
| SET-002 输出目录 | 🟡(键不一致Bug) | ❌ | ❌ |
| SET-003 标点开关 | 🟡(combo≠checkbox) | ✅ | ❌ |
| SET-004 乱码过滤 | 🟡(combo) | ✅ | ❌ |
| SET-005 VAD 灵敏度 | ✅ | ✅ | ❌ |
| SET-006 运算设备 | 🟡(无自动检测) | ✅ | ❌ |
| SET-007 API Key | ✅ | ❌ | 🟡(hasattr) |
| SET-008 摘要开关 | 🟡(combo) | ❌ | ❌ |
| SET-009 纠错开关 | 🟡(combo) | ❌ | ❌ |
| SET-010 模型管理 | ✅ | ✅ | ❌ |
| SET-011 VB-Cable | ✅(无检测) | 🟡 | ❌ |
| SET-012 通知开关 | ✅ | ❌ | ❌ |
| SET-013 厂商选择 | ✅ | ✅ | 🟡(hasattr) |
| SET-014 明文切换 | ✅ | ❌ | ❌ |
| SET-015 接入模式 | ✅ | ✅(URL路由) | ❌ |
| SET-016 Ollama 地址 | 🔴(无地址输入) | ❌ | ❌ |

### 3.8 UI
| 需求 | 实现 | 单测 | E2E |
|---|---|---|---|
| UI-001 顶部导航 | ✅ | ❌ | ✅ |
| UI-002 主页 | ✅ | 🟡 | ✅ |
| UI-003 音色库页 | ✅ | 🟡 | ✅ |
| UI-004 设置页 | ✅ | ✅(widget) | 🟡 |
| UI-005 状态栏 | ✅ | ❌ | ❌ |
| UI-006 Tooltip | 🟡(仅列表) | ❌ | ❌ |
| UI-007 结果预览 | ✅ | ❌ | 🟡(mock) |
| UI-008 导出功能 | ✅ | ❌(源码文本读) | ❌ |
| UI-009 完成弹窗 | 🟡(专用类死码) | ❌ | 🟡 |
| UI-010 合并排序 | 🟡(无拖拽) | ❌ | ❌ |
| UI-011 首次引导 | 🔴(模拟+缺内容) | ❌ | ❌ |
| UI-012 DWM 圆角 | ✅ | ❌ | ❌ |
| UI-013 日志过滤 | ✅ | ❌ | ❌ |
| UI-014 窗口图标 | ✅ | ❌ | 🟡 |

---

## 5. 文档导航

- 任务总览：本文件 §3 差距条目表
- 各任务详情：`docs/specs/tasks/T-*.md`（每条 Gap 一份，含 Scope / Success Criteria / 依赖 / 验收测试）
- 任务索引：`docs/specs/tasks/README.md`
