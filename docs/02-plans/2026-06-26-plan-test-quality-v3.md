# 测试质量持续改进方案 v3

> 日期：2026-06-26
> 基于：v2 方案部分执行后的实际状态
> 状态：待执行

---

## 现状

| 指标 | v2 方案时 | 当前实际 |
|------|-----------|----------|
| 测试文件数 | 40 | 42（删3+增5） |
| hasattr/is-not-None 总数 | 275 | **132** |
| 功能测试占比 | ~30% | ~55% |
| 已清理文件 | 0 | 3（test_async_integration、test_async_postprocess、test_optimization） |

### v2 方案执行状态

| 步骤 | 状态 | 说明 |
|------|------|------|
| 删除 3 个纯存在性文件 | DONE | test_gui_startup、test_voiceprint_page、test_voiceprint_page_e2e 已删除 |
| 新增 5 个测试文件 | DONE | test_utils、test_config_edge、test_frozen_paths、test_file_write_paths、test_voiceprint_boundary 已创建 |
| 清理混合文件 | **PARTIAL** | 3/11 文件已清理，8 个文件仍需处理 |

---

## 需清理的 8 个文件

### HIGH 优先级（存在性检查占比高）

| 文件 | hasattr 数 | 总测试数 | 比率 | 问题 |
|------|-----------|----------|------|------|
| `test_tdd_flows.py` | **33** | 27 | 1.22 | `test_all_components_exist` 单个方法含 10 个 hasattr 控件存在性检查 |
| `test_gui_special.py` | **20** | 19 | 1.05 | 前 7 个测试是纯 `assert X is not None` 导入检查 |
| `test_file_list.py` | **10** | 14 | 0.71 | 前 8 个测试是纯方法存在性检查 |

### MEDIUM 优先级

| 文件 | hasattr 数 | 总测试数 | 比率 | 问题 |
|------|-----------|----------|------|------|
| `test_settings_engine.py` | **17** | 29 | 0.59 | hasattr 与真实断言混合，部分可删部分需保留 |
| `test_file_manager.py` | **7** | 13 | 0.54 | `assert hasattr(FileManager, '__init__')` 等无意义检查 |

### LOW 优先级（hasattr 为辅助性质）

| 文件 | hasattr 数 | 总测试数 | 比率 | 问题 |
|------|-----------|----------|------|------|
| `test_bugfix_v10.py` | **8** | 28 | 0.29 | 多为 `if hasattr(...)` 守卫风格，嵌入在功能测试中 |
| `test_dialogs_p0.py` | **7** | 27 | 0.26 | 混入在功能测试中 |
| `test_voiceprint.py` | **4** | 23 | 0.17 | 偶发性 |

### 特殊文件

| 文件 | 说明 | 处理方式 |
|------|------|----------|
| `test_voiceprint_threshold.py` | **不是 pytest 文件**，是独立诊断脚本（`if __name__ == "__main__"`），无 `test_` 函数 | 移至 `scripts/` 或 `docs/` |

---

## 执行计划

### 第一步：移除非测试文件

将 `test_voiceprint_threshold.py` 移至 `scripts/diagnose_voiceprint_threshold.py`

### 第二步：清理 HIGH 优先级文件

**test_tdd_flows.py**：
- 删除 `test_all_components_exist` 方法（10 个 hasattr 控件检查）
- 保留其余功能测试

**test_gui_special.py**：
- 删除 `TestGUIImports` 类中纯导入检查（7 个 `assert X is not None`）
- 保留有实际断言的测试

**test_file_list.py**：
- 删除前 8 个纯方法存在性检查
- 保留实际调用方法的测试

### 第三步：清理 MEDIUM 优先级文件

**test_settings_engine.py**：
- 保留 hasattr + 真实断言的组合测试（如 hasattr 后紧跟 `assert page._punc_var.count() == 2`）
- 删除仅做 hasattr 检查的独立测试

**test_file_manager.py**：
- 删除 `assert hasattr(FileManager, '__init__')` 等无意义检查

### 第四步：清理 LOW 优先级文件（可选）

**test_bugfix_v10.py、test_dialogs_p0.py、test_voiceprint.py**：
- hasattr 为辅助性质（守卫或偶发），清理价值较低
- 可以跳过或仅清理明显的无意义检查

### 第五步：验证

```bash
pytest tests/ -v
```

确认：
- 所有测试通过
- hasattr 总数从 132 降至 ~60-70（剩余为合理的守卫式检查）

---

## 预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| hasattr 总数 | 132 | ~60-70 |
| 功能测试占比 | ~55% | ~70%+ |
| 纯存在性测试 | ~30 个 | 0 |
| 测试文件数 | 42 | 41（移出 1 个非测试文件） |

---

## 给 Qoder 的审查要点

1. HIGH 优先级 3 个文件的清理列表是否正确？
2. MEDIUM 优先级中 `test_settings_engine.py` 的 hasattr 是否确实可以删除（有些与真实断言混合）？
3. LOW 优先级是否建议跳过？
4. 是否有其他需要清理的文件未列出？

---

## Qoder 审查结果

> 审查日期：2026-06-26
> 审查方法：逐文件阅读源码，精确统计每个测试函数的 hasattr / is-not-None / 功能断言

### 数据修正

方案中的 hasattr 计数有多处偏差，以下为实际统计：

| 文件 | 方案计数 | 实际计数 | 偏差原因 |
|------|---------|---------|---------|
| test_tdd_flows.py | 33 | **32** | 差 1，可忽略 |
| test_gui_special.py | 20 | **0** | 该文件没有 hasattr，"20" 是 `is not None` 导入检查被误算为 hasattr |
| test_file_list.py | 10 | **10** | 正确 |
| test_settings_engine.py | 17 | **23** | 少算了，实际比方案估计的多 |
| test_file_manager.py | 7 | **1** | 严重多算，该文件只有 1 个 hasattr（`hasattr(FileManager, '__init__')`） |
| test_bugfix_v10.py | 8 | **3** | 多算了，实际只有 3 处 hasattr |
| test_dialogs_p0.py | 7 | **7** | 正确 |
| test_voiceprint.py | 4 | 未验证 | — |

### 对清理方案的逐项意见

**HIGH 优先级 — test_tdd_flows.py**

方案判断正确。`test_all_components_exist` 单个方法含 10 个 hasattr，应删除。`test_settings_page_loads` 和 `test_voiceprint_detail_view` 也是纯存在性检查，可一并删除。其余 24 个功能测试保留。

**HIGH 优先级 — test_gui_special.py**

方案方向正确，但描述有误。该文件不存在 hasattr，问题是 `TestGUIImports` 类中有 10 个（不是 7 个）纯 `assert X is not None` 的导入检查。应删除整个 `TestGUIImports` 类（10 个测试），保留 `TestGUIConstants` 和 `TestTranscriptionQueue` 等 9 个功能测试。

**HIGH 优先级 — test_file_list.py**

方案基本正确。前 8 个 `TestFileList` 方法 + 1 个 `test_file_manager_import` = 共 9 个存在性检查应删除。保留 `TestFileListIncrementalUpdate` 和 `TestMergedGroupBadge` 的 5 个功能测试。

**MEDIUM 优先级 — test_settings_engine.py**

方案判断正确。该文件有 7 个纯存在性测试可删除（`test_instantiate`、`test_model_manager_has_required_methods`、`test_ollama_address_field_exists`、`test_check_button_exists`、`test_download_button_exists`、`test_model_status_frame_exists`、`test_model_status_label_exists`）。另有 4 个混合测试（`test_punc_combo_exists` 等）中 hasattr 是冗余的——下一行已经访问了属性，hasattr 检查多余，可直接删掉 hasattr 行而保留真实断言。20 个功能测试全部保留。

**MEDIUM 优先级 — test_file_manager.py — 建议从清理列表中移除**

该文件只有 1 个 hasattr（`assert hasattr(FileManager, '__init__')`），不值得专门列入清理计划。如需处理，删掉 `test_file_manager_import` 这一个测试即可。其余 13 个测试全部是高质量功能测试。

**LOW 优先级 — 同意跳过**

test_bugfix_v10.py 只有 3 个 hasattr，test_dialogs_p0.py 的 7 个 hasattr 集中在一个类里，test_voiceprint.py 偶发。清理价值确实不高，可以跳过。

**特殊文件 — test_voiceprint_threshold.py**

同意移至 `scripts/diagnose_voiceprint_threshold.py`。该文件不含 pytest 测试函数，不会被 pytest 收集。

### 修正后的执行清单

| 步骤 | 操作 | 删除测试数 |
|------|------|-----------|
| 1 | 移出 test_voiceprint_threshold.py → scripts/ | 0 |
| 2 | test_tdd_flows.py：删 3 个存在性测试 | 3 |
| 3 | test_gui_special.py：删整个 TestGUIImports 类 | 10 |
| 4 | test_file_list.py：删前 8 个方法 + test_file_manager_import | 9 |
| 5 | test_settings_engine.py：删 7 个纯存在性 + 清理 4 个混合测试的 hasattr | 7+4 |
| 6 | test_file_manager.py：删 test_file_manager_import（可选） | 1 |

总计删除：约 34 个存在性检查测试。

### 回答审查要点

1. **HIGH 优先级 3 个文件**：方向正确，但 test_gui_special.py 的 hasattr 计数错误（实际为 0），应改为"10 个导入检查"。
2. **test_settings_engine.py 的混合 hasattr**：4 个 combo_exists 测试中的 hasattr 是冗余的，可以安全删除（删掉 hasattr 行，保留后面的真实断言），不会破坏测试逻辑。
3. **LOW 优先级**：建议跳过，理由充分。
4. **遗漏文件**：无其他需要清理的文件。当前方案已覆盖所有存在性检查集中的文件。
