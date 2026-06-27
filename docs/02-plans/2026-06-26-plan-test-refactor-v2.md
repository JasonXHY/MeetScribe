# 测试重构方案 v2

> 日期：2026-06-26
> 基于：Qoder 审查反馈修正
> 验证：MiMo Code 已验证 Qoder 反馈正确性

---

## Qoder 反馈摘要（已验证）

### Qoder 纠正的错误

| 原判断 | Qoder 纠正 | MiMo 验证 |
|--------|-----------|-----------|
| 删 11 个文件 | 只能删 3 个 | ✅ 正确。test_home_page_p0.py 等有功能测试 |
| test_transcription.py 纯存在性检查 | 有 13 个功能测试 | ✅ 正确。实测 13 个功能测试 + 7 个 hasattr |
| 删 11 个文件共 ~650 行 | 只能删 ~120 行 | ✅ 正确 |

### Qoder 补充的遗漏场景

1. utils.py 的 `extract_speaker_mapping()` 和 `apply_speaker_mapping()`
2. 打包模式模拟测试（mock `sys.frozen=True`）
3. 声纹匹配阈值边界测试

### Qoder 指出的命名问题

- `test打包_paths.py` → 应为 `test_frozen_paths.py`

---

## 修正说明

Qoder 审查发现原方案有重大错误：
1. 删除列表从 11 个文件修正为 3 个
2. test_transcription.py 不需要重写，保留 13 个功能测试
3. 补充遗漏的测试场景

---

## 一、删除文件（仅 3 个）

```bash
rm tests/test_gui_startup.py        # 34行，全部是 is not None
rm tests/test_voiceprint_page.py    # 45行，全部是 hasattr
rm tests/test_voiceprint_page_e2e.py # 43行，全部是 hasattr
```

**删除小计**：3 个文件，~120 行

---

## 二、清理存在性检查（从保留文件中删除）

| 文件 | 删除数量 | 保留数量 |
|------|----------|----------|
| test_optimization.py | 2 | 1 |
| test_progress_display.py | 2 | 5 |
| test_stop_button.py | 1 | 5 |
| test_button_states.py | 1 | 6 |
| test_embedding_save.py | 1 | 6 |
| test_add_voice_dialog.py | 2 | 5 |
| test_bugfix_v10.py | 2 | 26 |
| test_async_integration.py | 4 | 8 |
| test_async_postprocess.py | 9 | 3 |
| test_settings_engine.py | 8 | 16 |
| test_transcription.py | 7 | 17 |

**清理小计**：删除 ~39 个 hasattr 测试函数

---

## 三、新增测试文件（5 个）

### 1. test_utils.py（P0）

```python
def test_get_data_dir_returns_absolute_path():
    """返回绝对路径"""

def test_get_data_dir_dev_mode():
    """开发模式返回项目目录"""

def test_get_data_dir_contains_data_subdirs():
    """返回路径下有 config/data/logs 目录"""

def test_get_data_dir_frozen_mode():
    """打包模式返回 LOCALAPPDATA\MeetScribe（mock sys.frozen）"""

def test_get_data_dir_fallback_no_env():
    """LOCALAPPDATA 缺失时使用 HOME 兜底"""

def test_extract_speaker_mapping():
    """从摘要中提取 Speaker 映射"""

def test_apply_speaker_mapping():
    """应用 Speaker 映射到文本"""

def test_get_summary_path():
    """从转写路径推导汇总文件路径"""
```

### 2. test_config_edge.py（P0）

```python
def test_config_corrupted_json(tmp_path):
    """配置文件损坏时不崩溃"""

def test_config_missing_file(tmp_path):
    """配置文件不存在时使用默认值"""

def test_config_empty_file(tmp_path):
    """空配置文件使用默认值"""
```

### 3. test_frozen_paths.py（P0）

```python
def test_frozen_data_dir():
    """mock sys.frozen=True，验证数据目录"""

def test_frozen_assets_dir():
    """mock sys.frozen=True，验证资源目录"""

def test_frozen_model_cache():
    """mock sys.frozen=True，验证模型缓存目录"""
```

### 4. test_file_write_paths.py（P1）

```python
def test_file_manager_default_path():
    """FileManager 默认路径使用 get_data_dir"""

def test_voiceprint_default_path():
    """VoiceprintLibrary 默认路径使用 get_data_dir"""

def test_config_project_root():
    """Config PROJECT_ROOT 使用 get_data_dir"""
```

### 5. test_voiceprint_boundary.py（P1）

```python
def test_match_threshold_boundary():
    """匹配阈值边界测试（0.31 临界值）"""

def test_dedup_threshold():
    """同源去重测试（DEDUP_THRESHOLD = 0.999）"""

def test_fifo淘汰():
    """FIFO 淘汰测试（超过 MAX_EMBEDDINGS_PER_SPEAKER = 5）"""
```

---

## 四、执行顺序

### 第一步：删除 3 个纯存在性检查文件

### 第二步：清理 11 个混合文件中的存在性检查（~39 个函数）

### 第三步：新增 5 个测试文件（~20 个测试函数）

### 第四步：运行全量测试验证

```bash
pytest tests/ -v
```

---

## 五、预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| 测试文件数 | 40 | 42（删3+增5） |
| 存在性检查 | 275 | ~236（删39） |
| 功能测试 | ~130 | ~150（增20） |
| 关键路径覆盖 | 低 | 高 |

---

## 六、给 Qoder 的二次确认

请 Qoder 确认：
1. 修正后的删除列表是否正确
2. 新增测试场景是否完整
3. 是否有其他遗漏
