# 测试用例优化方案

> 日期：2026-06-27
> 目标：从 429 个测试用例中清理低价值用例，保留行为测试
> 状态：待 Qoder 审核

---

## 现状

| 指标 | 数值 |
|------|------|
| 测试文件 | 18 个 `test_*.py` |
| 测试用例总数 | 429 |
| 有效行为测试（KEEP） | ~340 |
| 弱测试（WEAK） | ~50 |
| 冗余测试（REDUNDANT） | ~2 |
| 过时测试（STALE） | ~4 |
| **可清理用例** | **~56** |
| **预计剩余** | **~373** |

---

## WEAK 测试分类

### 类型 1：`hasattr` 存在性检查（~20 个）

```python
# 典型模式 — 测试 nothing
def test_method_exists(self):
    assert hasattr(SomeClass, '_some_method')
```

**问题**：Python 类的方法必然存在，除非语法错误（导入时就会失败）。紧随其后的测试已经调用了该方法。

| 文件 | 数量 | 示例 |
|------|------|------|
| test_gui_config.py | 5 | `test_punc_combo_exists`, `test_garble_combo_exists`, `test_vad_combo_exists`, `test_device_combo_exists`, `test_dialog_has_beta_notice_step` |
| test_gui_dialogs.py | 2 | `test_save_embeddings_to_disk_method_exists`, `test_preview_dialog_exists` |
| test_gui_home.py | 3 | `test_stop_recording_method_exists`, `test_progress_updated_signal_exists`, `test_on_progress_updated_method_exists` |
| test_voiceprint.py | 1 | `test_extract_embedding_from_file`（仅 hasattr） |
| test_async_workers.py | 9 | 多个 `test_*_exists` / `test_*_signal_exists` |

**处理**：全部删除。

### 类型 2：`isinstance` / 类型检查（~8 个）

```python
# 典型模式 — 测试 Python 本身
def test_returns_list(self):
    result = get_models_for_vendor("小米 MiMo")
    assert isinstance(result, list)
    assert len(result) > 0
```

| 文件 | 数量 | 示例 |
|------|------|------|
| test_gui_config.py | 2 | `test_returns_list`（VendorList / ModelsForVendor） |
| test_gui_home.py | 1 | `test_selected_files_property` |
| test_async_workers.py | 3 | `test_queue_returns_list`, `test_task_list_returns_list` |
| test_tdd_flows.py | 2 | `test_app_creation`（`config is not None`） |

**处理**：删除或合并到有行为断言的测试中。

### 类型 3：常量值检查（~5 个）

```python
# 典型模式 — 硬编码断言
def test_match_threshold_boundary(self):
    assert 0.3 <= MATCH_THRESHOLD <= 0.4
```

| 文件 | 数量 | 示例 |
|------|------|------|
| test_voiceprint.py | 3 | `test_match_threshold_boundary`, `test_dedup_threshold`, `test_max_embeddings_per_speaker` |
| test_ai_service.py | 1 | `test_ollama_defaults_when_none` |
| test_gui_config.py | 1 | `test_wizard_has_two_steps` |

**处理**：删除。常量变更时测试会自然失败（因为依赖该常量的行为测试会失败）。

### 类型 4：依赖外部数据的测试（~5 个）

```python
# 典型模式 — 不可复现
def test_voiceprint_library_loads(self):
    speakers = library.get_speakers()
    assert len(speakers) > 0  # 依赖磁盘上的真实数据
```

| 文件 | 数量 | 示例 |
|------|------|------|
| test_tdd_flows.py | 3 | `test_audio_files_valid`, `test_voiceprint_quality_scores`, `test_speaker_count_reasonable` |
| test_tdd_flows.py | 2 | `test_voiceprint_library_loads`, `test_voiceprint_match_in_transcription` |

**处理**：移除或改为 mock 数据。

### 类型 5：Skip + 未实现功能（~2 个）

```python
@pytest.mark.skip(reason="Ollama forwarding not yet implemented")
def test_get_ai_service_forwards_ollama_config(self):
    ...
```

| 文件 | 数量 | 示例 |
|------|------|------|
| test_transcription.py | 1 | `test_get_ai_service_forwards_ollama_config` |
| test_tdd_flows.py | 1 | `test_logging_on_failure`（仅 assert log 文件存在） |

**处理**：删除 skip 测试，功能实现时再补。

---

## 按文件清理清单

### 高优先级（WEAK 占比 >15%）

| 文件 | 当前 | WEAK | 删除后 | 清理率 |
|------|------|------|--------|--------|
| test_async_workers.py | 37 | 15 | 22 | 41% |
| test_tdd_flows.py | 18 | 10 | 8 | 56% |
| test_gui_config.py | 58 | 8 | 50 | 14% |

### 中优先级（WEAK 5-10%）

| 文件 | 当前 | WEAK | 删除后 | 清理率 |
|------|------|------|--------|--------|
| test_voiceprint.py | 28 | 5 | 23 | 18% |
| test_gui_home.py | 63 | 4 | 59 | 6% |
| test_gui_dialogs.py | 40 | 3 | 37 | 8% |

### 低优先级（WEAK <5%）

| 文件 | 当前 | WEAK | 删除后 | 清理率 |
|------|------|------|--------|--------|
| test_ai_service.py | 9 | 1 | 8 | 11% |
| test_file_manager.py | 15 | 1 | 14 | 7% |
| test_formatters.py | 16 | 2 | 14 | 13% |
| test_speaker_namer.py | 14 | 1 | 13 | 7% |
| test_transcription.py | 16 | 2 | 14 | 13% |

### 无需清理

| 文件 | 当前 | WEAK | 说明 |
|------|------|------|------|
| test_recorder.py | 18 | 0 | 全部 KEEP |
| test_transcription_queue.py | 16 | 0 | 全部 KEEP |
| test_dual_track_merge.py | 18 | 0 | 1 REDUNDANT 但保留 |
| test_postprocess.py | — | — | 未分析，预估 WEAK <3 |

---

## 清理后预期

| 指标 | 清理前 | 清理后 | 变化 |
|------|--------|--------|------|
| 测试用例 | 429 | ~373 | -13% |
| WEAK 测试 | ~50 | ~0 | -100% |
| STALE 测试 | ~4 | 0 | -100% |
| 测试运行时间 | ~44s | ~38s | -14% |

---

## 执行步骤

1. **先跑全量**确认当前基线（已有 416 passed）
2. **按文件清理**：从 WEAK 占比最高的 `test_async_workers.py` 开始
3. **每删一批**跑一次 `pytest tests/ -v` 确认无误
4. **更新 MEMORY.md** 记录清理后用例数

---

## 不清理的内容

- `test_tdd_flows.py` 中的 E2E 测试（即使弱于单元测试，仍有集成价值）
- `_middle_third_window` 的跨文件测试（不同输入，非冗余）
- 所有带 `mock` 的行为测试（mock 是正确做法）
- `conftest.py` 中的 fixture（测试基础设施）

---

## Qoder 审查意见（2026-06-27）

> 逐项对照实际测试代码验证，核心结论：**WEAK 数量虚高约 22 个，如果按此方案执行会误删功能测试。**

### 一、总数统计错误

多个文件的测试总数与实际不符：

| 文件 | mimo 统计 | 实际数量 | 偏差 |
|------|-----------|----------|------|
| test_tdd_flows.py | 18 | **24** | 少算 6 个 |
| test_voiceprint.py | 28 | **37** | 少算 9 个 |
| test_gui_home.py | 63 | **55** | 多算 8 个 |
| test_async_workers.py | 37 | 37 | 正确 |
| test_gui_config.py | 58 | 58 | 正确 |

### 二、WEAK 数量逐文件核实

#### test_async_workers.py — mimo 报 15 WEAK，实际 6 WEAK

**mimo 多报了 9 个。** 以下被 mimo 标为 WEAK 的测试实际是功能测试：

| 被误判的测试 | 实际行为 |
|-------------|----------|
| `test_correction_worker_finished_signal_connected` | 调用 `_start_correction_async()`，断言 `connect.call_count >= 2`，验证信号连接行为 |
| `test_summary_worker_finished_signal_connected` | 同上，验证 summary 信号连接 |
| `test_names_applied_guard_blocks_second_call` | 设置 guard 后调用 `_apply_speaker_names()`，断言 AI 方法未被调用（防止重复调用） |
| `test_names_applied_resets_on_new_task` | 调用 `_execute_task()`，断言 guard 状态重置 |
| `test_h1_title` ~ `test_no_topic_format`（8 个） | 调用提取函数，断言不同输入格式的正确返回值 |

**真实 WEAK 仅 6 个**：`test_names_applied_default_false`（常量值）、`test_all_vendor_mappings` / `test_unknown_vendor_passthrough` / `test_already_full_name`（测试本地字典而非生产代码）、`test_app_startup_with_fixed_config`（常量断言）、`test_settings_page_loads_correctly`（条件 hasattr）。

#### test_tdd_flows.py — mimo 报 10 WEAK，实际 12 WEAK

mimo 少报了 2 个，同时漏算了 6 个测试函数。实际 24 个测试中：

**额外发现的 WEAK 测试**（mimo 遗漏）：
- `test_ai_service_creation` — 仅验证构造函数属性
- `test_voiceprint_page_loads` — 仅 `assert _speaker_list is not None`
- `test_add_voice_dialog_recording_flow` — mock 调用 mock，无真实逻辑
- `test_voiceprint_detail_view` — 仅 widget 可见性
- `test_transcription_result_structure` — 新建 App 实例文件列表必然为空，for 循环永远不执行
- `test_summary_speaker_correspondence` — 同上，永远跳过

#### test_gui_config.py — mimo 报 8 WEAK，实际 6 WEAK

**mimo 多报了 2 个：**
- `test_dialog_has_beta_notice_step` — 实际断言 `currentIndex() == 0`，验证向导初始状态，不是纯 hasattr
- `test_returns_list`（ModelsForVendor）— 实际遍历所有厂商并检查 `len > 0`，不只是 isinstance

#### test_voiceprint.py — mimo 报 5 WEAK / 28 总数，实际 5 WEAK / 37 总数

WEAK 数量正确，但总数少算了 9 个。

#### test_gui_home.py — mimo 报 4 WEAK / 63 总数，实际 5 WEAK / 55 总数

**mimo 漏报 1 个 WEAK**：`test_ai_summary_button_exists`（第 271 行）是纯 hasattr 检查，和其他 3 个 hasattr 测试同类。

### 三、修正后的清理清单

| 文件 | mimo 报 WEAK | 实际 WEAK | 可安全删除的测试 |
|------|-------------|-----------|-----------------|
| test_async_workers.py | 15 | **6** | `test_names_applied_default_false`, 3 个 vendor mapping 测试, `test_app_startup_with_fixed_config`, `test_settings_page_loads_correctly` |
| test_tdd_flows.py | 10 | **12** | `test_audio_files_valid`, `test_ai_service_creation`, `test_voiceprint_library_loads`, `test_voiceprint_match_in_transcription`, `test_voiceprint_page_loads`, `test_add_voice_dialog_recording_flow`, `test_voiceprint_quality_scores`, `test_voiceprint_detail_view`, `test_speaker_count_reasonable`, `test_transcription_result_structure`, `test_summary_speaker_correspondence`, `test_logging_on_failure` |
| test_gui_config.py | 8 | **6** | 4 个 `*_exists` 测试（被 `*_options` 覆盖）, `test_wizard_has_two_steps`, `test_returns_list`（VendorList 版本） |
| test_voiceprint.py | 5 | **5** | 3 个常量阈值测试, `test_extract_embedding_from_file`（hasattr only）, `test_fifo_eviction_behavior` 之前的常量检查 |
| test_gui_home.py | 4 | **5** | `test_selected_files_property`, `test_ai_summary_button_exists`, `test_stop_recording_method_exists`, `test_progress_updated_signal_exists`, `test_on_progress_updated_method_exists` |
| 其他文件 | ~14 | ~0 | 其余文件未详细验证，按 mimo 清单中 WEAK < 5% 的分类暂不处理 |

**修正后总计：约 34 个可清理测试（非 mimo 报告的 56 个），预计剩余 ~376 个测试。**

### 四、执行建议

1. **不要按 mimo 原始清单批量删除** — 会误删 22 个功能测试
2. **按上表逐文件执行** — 每删一个文件内的 WEAK 测试后跑 `pytest` 确认通过
3. **test_tdd_flows.py 可清理最多**（12 个），但保留其中带 `e2e_heavy` / `e2e_network` 标记的真实 E2E 测试
4. **test_async_workers.py 只删 6 个** — 信号连接测试、guard 测试、topic 提取测试全部保留
