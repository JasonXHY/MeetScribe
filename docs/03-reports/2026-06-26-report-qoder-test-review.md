# Qoder 测试审查指令

> 日期：2026-06-26
> 目的：请 Qoder 审查测试重构方案

---

## 背景

测试数量多（40 文件、6000 行）但质量低。大量测试只是检查类/方法是否存在（`assert hasattr`），不验证功能是否正确。今天修复了 get_data_dir() 路径问题，但没有任何测试覆盖。

---

## 需要 Qoder 审查的内容

### 1. 测试重构方案

文件位置：`docs/02-plans/2026-06-26-plan-test-refactor.md`

请审查：
- 删除列表是否合理？有没有遗漏需要保留的测试？
- 新增测试场景是否完整？
- 混合文件清理方案是否正确？

### 2. 具体审查要点

**删除文件检查**：
```
test_gui_startup.py (34行) - 是否全部是存在性检查？
test_home_page_p0.py (49行) - 是否全部是存在性检查？
test_infra.py (29行) - 是否全部是存在性检查？
test_optimization.py (27行) - 是否全部是存在性检查？
test_progress_display.py (87行) - 是否全部是存在性检查？
test_stop_button.py (80行) - 是否全部是存在性检查？
test_button_states.py (90行) - 是否全部是存在性检查？
test_embedding_save.py (117行) - 是否全部是存在性检查？
test_add_voice_dialog.py (48行) - 是否全部是存在性检查？
test_voiceprint_page.py (45行) - 是否全部是存在性检查？
test_voiceprint_page_e2e.py (43行) - 是否全部是存在性检查？
```

**混合文件检查**：
- test_bugfix_v10.py (395行) - 哪些测试有实际逻辑？哪些是存在性检查？
- test_async_integration.py (108行) - 同上
- test_async_postprocess.py (71行) - 同上
- test_settings_engine.py (204行) - 同上

### 3. 新增测试场景检查

请确认以下场景是否有遗漏：

**get_data_dir() 测试**：
- 开发模式返回项目目录
- 返回绝对路径
- 返回路径存在

**配置错误场景**：
- 配置文件损坏
- 配置文件缺失
- 配置文件为空

**转写核心流程**：
- 日志路径正确
- 双轨合并逻辑

**文件写入路径**：
- FileManager 默认路径
- VoiceprintLibrary 默认路径
- Config PROJECT_ROOT

---

## 审查格式

请按以下格式输出审查结果：

```
## 审查结论

### 删除文件确认
- [ ] test_gui_startup.py - 确认可删除 / 需保留（原因）
- [ ] test_home_page_p0.py - 确认可删除 / 需保留（原因）
...

### 混合文件分析
- test_bugfix_v10.py:
  - 有效测试：[列出]
  - 无效测试：[列出]

### 新增场景检查
- [ ] 场景1 - 完整 / 需补充
- [ ] 场景2 - 完整 / 需补充
...

### 遗漏场景
- [列出 Qoder 认为应该测试但方案中没有的场景]

### 建议
- [其他建议]
```

---

## 时间要求

请在 24 小时内完成审查。

---

## Qoder 审查结果

> 审查日期：2026-06-26
> 审查方法：逐个文件阅读源码，对每个测试函数分类为"功能测试"或"存在性检查"

### 审查结论摘要

**删除列表有严重问题：11 个文件中只有 3 个可以删除，其余 8 个包含 30 个有效功能测试，删除会丢失覆盖。**

**混合文件分析：test_transcription.py 的判断有误，该文件有 17 个有效功能测试，不是"纯存在性检查"。**

---

### 删除文件确认

| 文件 | 结论 | 原因 |
|------|------|------|
| test_gui_startup.py | 可删除 | 6 个测试全部是 `assert X is not None` |
| test_home_page_p0.py | **不可删除** | 2 个测试均为功能测试：验证属性返回类型、调用 update_recording_ui 并断言参数正确 |
| test_infra.py | **不可删除** | 3 个测试均为功能测试：验证 WAV 文件格式（channels/framerate/sampwidth）、fixture 去重、pytest marker 注册 |
| test_optimization.py | **不可删除** | 含 1 个功能测试 `test_model_directory_size`（检查模型目录 < 3GB），其余 2 个为存在性检查 |
| test_progress_display.py | **不可删除** | 5/7 为功能测试：验证 dict/object 进度解析、未知类型不崩溃、缺失字段兜底、文件计数格式化 |
| test_stop_button.py | **不可删除** | 5/6 为功能测试：验证转写中/录音中/空闲三种状态下停止按钮的分支逻辑和 UI 更新 |
| test_button_states.py | **不可删除** | 6/7 为功能测试：验证按钮完整生命周期（开始禁用→完成启用→失败启用） |
| test_embedding_save.py | **不可删除** | 6/7 为功能测试：验证 JSON 序列化、空 embedding 不保存、None 路径跳过、numpy 数组转换、质量默认值 |
| test_add_voice_dialog.py | **不可删除** | 5/7 为功能测试：实例化真实对话框并验证初始 UI 状态（按钮启用/禁用、占位文字、标签文字） |
| test_voiceprint_page.py | 可删除 | 7 个测试全部是 hasattr/is not None |
| test_voiceprint_page_e2e.py | 可删除 | 6 个测试全部是 hasattr/is not None |

**结论：只能删除 3 个文件（gui_startup、voiceprint_page、voiceprint_page_e2e），不是 11 个。**

对其余 8 个文件，正确做法是：保留功能测试，仅删除其中的存在性检查（共约 10 个 hasattr 测试函数）。

---

### 混合文件分析

**test_bugfix_v10.py**（521 行）：
- 有效功能测试：26 个（供应商名称归一化、输出目录配置、打开文件夹逻辑、导出摘要路径、空配置过滤、日志前缀、主题提取等）
- 存在性检查：2 个（`test_file_list_view_exists`、`test_recording_bar_exists`）
- 处理建议：保留全部 26 个功能测试，仅删除末尾 2 个存在性检查

**test_async_integration.py**（151 行）：
- 有效功能测试：8 个（Worker 创建启动、信号连接、文件写入、错误日志）
- 存在性检查：4 个（handler 方法 hasattr）
- 处理建议：保留 8 个功能测试，删除 4 个 hasattr 检查

**test_async_postprocess.py**（93 行）：
- 有效功能测试：3 个（names_applied 防重入守卫、默认值、任务重置）
- 存在性检查：9 个（类/信号/方法 hasattr）
- 处理建议：这个文件 75% 是垃圾。保留 3 个功能测试，删除 9 个 hasattr 检查

**test_settings_engine.py**（262 行）：
- 有效功能测试：16 个（下拉框选项验证、配置保存/恢复往返测试、Ollama 地址、输出目录）
- 存在性检查：8 个（控件 hasattr/is not None）
- 处理建议：保留 16 个功能测试，删除 8 个 hasattr 检查

**test_transcription.py**（380 行）— **方案判断有误**：
- 有效功能测试：17 个（声纹匹配守卫、自动添加 embedding 逻辑、摘要声纹注入、质量评分计算、模型配置验证）
- 存在性检查：7 个（类/方法 hasattr/is not None）
- 跳过：1 个
- 处理建议：**不可重写**。保留 17 个功能测试，仅删除开头 `TestTranscription` 类中的 7 个存在性检查。mimo 说"289 行纯存在性检查"是不准确的。

---

### 新增场景检查

| 场景 | 评估 | 说明 |
|------|------|------|
| get_data_dir() 三种模式 | 需补充 | 当前只有开发模式测试，缺少打包模式（mock `sys.frozen=True`）和 `LOCALAPPDATA` 环境变量缺失时的兜底测试 |
| 配置文件损坏/缺失/为空 | 完整 | 三个场景覆盖合理 |
| 转写核心流程 | 需补充 | 只有日志路径和双轨合并，缺少 speaker_mapping 提取/应用测试（utils.py 中的核心函数） |
| 文件写入路径 | 完整 | 三个路径覆盖合理 |

---

### 遗漏场景

以下是方案中没有覆盖但应该测试的场景：

1. **utils.py 工具函数测试**（P0）
   - `extract_speaker_mapping_from_summary()`：从摘要中提取 `[Speaker N] 姓名` 格式的映射，过滤角色推断
   - `apply_speaker_mapping()`：文本替换逻辑，含 `Speaker N` 和 `local-N/remote-N` 两种格式
   - `get_summary_path()`：从转写路径推导汇总文件路径

2. **voiceprint.py 声纹匹配逻辑测试**（P1）
   - 匹配阈值边界（0.31 临界值）
   - 同源去重（DEDUP_THRESHOLD = 0.999）
   - FIFO 淘汰（超过 MAX_EMBEDDINGS_PER_SPEAKER = 5）
   - 注意：test_voiceprint.py 已覆盖部分，但缺少阈值边界测试

3. **打包模式路径模拟测试**（P0，本次修复的核心）
   - mock `sys.frozen = True` + `sys._MEIPASS` 验证打包后资源路径（ASSETS_DIR）
   - mock `sys.frozen = True` + `LOCALAPPDATA` 验证数据目录

4. **AI 服务供应商归一化测试**（P1）
   - test_bugfix_v10.py 中已有 4 个（TestVendorNormalization），但应确认这些测试是否覆盖了所有当前支持的供应商

---

### 修正后的执行计划

**第一步：删除（仅 3 个文件）**
```
rm tests/test_gui_startup.py
rm tests/test_voiceprint_page.py
rm tests/test_voiceprint_page_e2e.py
```

**第二步：清理（从保留文件中删除存在性检查）**
- test_home_page_p0.py：删除 0 个（全保留）
- test_infra.py：删除 0 个（全保留）
- test_optimization.py：删除 2 个（`test_gui_import`、`test_transcriber_import`）
- test_progress_display.py：删除 2 个存在性检查
- test_stop_button.py：删除 1 个存在性检查
- test_button_states.py：删除 1 个存在性检查
- test_embedding_save.py：删除 1 个存在性检查
- test_add_voice_dialog.py：删除 2 个存在性检查
- test_bugfix_v10.py：删除 2 个存在性检查
- test_async_integration.py：删除 4 个 hasattr 检查
- test_async_postprocess.py：删除 9 个 hasattr 检查
- test_settings_engine.py：删除 8 个 hasattr 检查
- test_transcription.py：删除 7 个存在性检查（保留 17 个功能测试）

**第三步：新增（5 个文件，按方案执行，补充打包模式模拟）**

**第四步：验证**
```bash
pytest tests/ -v
```
确认：文件数减少、存在性检查归零、功能测试全部通过。

---

### 给 mimo 的特别说明

1. **不要一次性删除 11 个文件**。其中 8 个包含有效功能测试，删除会丢失覆盖。请按上方修正列表操作。

2. **test_transcription.py 不需要重写**。它的核心测试（声纹守卫、自动添加、摘要注入、质量评分）质量很高，只需要删除开头的 7 个 hasattr 检查。

3. **新增测试中 `test打包_paths.py` 命名不符合规范**。应改为 `test_frozen_paths.py`（方案第五节已用此名，但第四节示例中混用了中文名）。

4. 清理后的预计数据：
   - 删除文件：3 个（不是 11 个）
   - 删除存在性检查函数：约 39 个
   - 保留功能测试：约 130+ 个
   - 新增功能测试：约 15-20 个
