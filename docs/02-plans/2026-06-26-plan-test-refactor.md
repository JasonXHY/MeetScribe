# 测试重构方案

> 日期：2026-06-26
> 目的：删除无效测试，补充有效场景测试

---

## 一、现状分析

### 1.1 测试数量

| 指标 | 数值 |
|------|------|
| 测试文件 | 40 个 |
| 总行数 | ~6000 行 |
| hasattr 检查 | 275 个 |
| 实际功能测试 | 估约 30% |

### 1.2 问题诊断

**问题 1：存在性检查泛滥**

```python
# 这类测试占大量行数，价值为零
def test_stop_recording_method_exists(self):
    assert hasattr(HomePage, '_stop_recording')

def test_correction_worker_class_exists(self):
    assert hasattr(AICorrectionWorker, 'finished')
```

**问题 2：关键路径无测试**

- `get_data_dir()`：0 个测试
- 打包路径逻辑：0 个测试
- 错误恢复场景：极少

**问题 3：转写模块测试空洞**

`test_transcription.py` 289 行，但只检查类/方法/常量是否存在，不验证转写逻辑。

---

## 二、修正原则

### 2.1 什么该删

| 类型 | 处理 |
|------|------|
| `assert hasattr(X, 'method')` | 删除 |
| `assert X is not None` | 删除 |
| `assert hasattr(X, '__init__')` | 删除 |
| `test_xxx_exists` | 删除 |
| `test_xxx_import` | 删除 |

### 2.2 什么该留

| 类型 | 处理 |
|------|------|
| 测试具体输入输出 | 保留 |
| 测试边界条件 | 保留 |
| 测试错误处理 | 保留 |
| 测试数据持久化 | 保留 |
| 测试业务逻辑 | 保留 |

### 2.3 什么该补

| 场景 | 优先级 |
|------|--------|
| get_data_dir() 三种模式 | P0 |
| 配置文件损坏/缺失 | P0 |
| 转写核心流程 | P1 |
| 文件写入权限 | P1 |
- 音色库持久化 | P1

---

## 三、逐文件分析

### 3.1 可删除的文件（全部是存在性检查）

| 文件 | 行数 | 处理 |
|------|------|------|
| test_gui_startup.py | 34 | 删除 |
| test_home_page_p0.py | 49 | 删除 |
| test_infra.py | 29 | 删除 |
| test_optimization.py | 27 | 删除 |
| test_progress_display.py | 87 | 删除 |
| test_stop_button.py | 80 | 删除 |
| test_button_states.py | 90 | 删除 |
| test_embedding_save.py | 117 | 删除 |
| test_add_voice_dialog.py | 48 | 删除 |
| test_voiceprint_page.py | 45 | 删除 |
| test_voiceprint_page_e2e.py | 43 | 删除 |

**删除小计**：11 个文件，~650 行

### 3.2 需要重写的文件

| 文件 | 问题 | 处理 |
|------|------|------|
| test_transcription.py | 289 行但只检查存在 | 重写核心逻辑测试 |
| test_async_integration.py | 大量 hasattr | 删除无效，保留有效 |
| test_async_postprocess.py | 大量 hasattr | 删除无效，保留有效 |
| test_settings_engine.py | 大量 hasattr | 删除无效，保留有效 |
| test_bugfix_v10.py | 混合有效/无效 | 保留有效，删除无效 |

### 3.3 保留的文件（质量较好）

| 文件 | 说明 |
|------|------|
| test_config.py | 基础配置测试，可保留 |
| test_file_manager.py | 文件管理测试，可保留 |
| test_voiceprint.py | 音色库测试，质量较高 |
| test_voiceprint_threshold.py | 阈值测试，有实际逻辑 |
| test_dual_track_merge.py | 双轨合并测试，有逻辑 |
| test_recorder.py | 录音测试，有逻辑 |
| test_formatters.py | 格式化测试，有逻辑 |

### 3.4 需要新增的测试文件

| 文件 | 测试内容 |
|------|----------|
| test_utils.py | get_data_dir() 三种场景 |
| test_config_edge.py | 配置损坏/缺失/权限 |
| test_transcription_core.py | 转写核心流程（mock） |
| test_file_write_paths.py | 验证所有写入路径正确 |
| test打包_paths.py | 验证打包后路径逻辑 |

---

## 四、新增测试场景

### 4.1 get_data_dir() 测试

```python
# test_utils.py

def test_get_data_dir_returns_absolute_path():
    """返回绝对路径"""
    result = get_data_dir()
    assert os.path.isabs(result)

def test_get_data_dir_dev_mode():
    """开发模式返回项目目录"""
    result = get_data_dir()
    assert result.endswith('侧耳倾听') or result.endswith('MeetScribe')

def test_get_data_dir_contains_data_subdirs():
    """返回路径下有 config/data/logs 目录"""
    result = get_data_dir()
    # 开发模式下检查
    if not getattr(sys, 'frozen', False):
        assert os.path.exists(os.path.join(result, 'src'))
```

### 4.2 配置错误场景

```python
# test_config_edge.py

def test_config_corrupted_json(tmp_path):
    """配置文件损坏时不崩溃"""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json", encoding='utf-8')
    config = Config(str(bad_file))
    assert config.get("recording_mode") == "dual"  # 使用默认值

def test_config_missing_file(tmp_path):
    """配置文件不存在时使用默认值"""
    config = Config(str(tmp_path / "nonexistent.json"))
    assert config.get("recording_mode") == "dual"

def test_config_empty_file(tmp_path):
    """空配置文件使用默认值"""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}", encoding='utf-8')
    config = Config(str(empty_file))
    assert config.get("recording_mode") == "dual"
```

### 4.3 转写核心流程（mock）

```python
# test_transcription_core.py

def test_transcribe_worker_log_path():
    """转写子进程日志路径正确"""
    from transcribe_worker import _log_dir
    assert os.path.isabs(_log_dir)
    assert 'logs' in _log_dir

def test_build_merged_transcript():
    """双轨合并结果格式正确"""
    from transcribe_worker import build_merged_transcript
    files = ['a.wav', 'b.wav']
    texts = ['Hello', 'World']
    result, is_dual = build_merged_transcript(files, texts, 'mic', 'sys')
    assert isinstance(result, str)
    assert len(result) > 0
```

### 4.4 文件写入路径验证

```python
# test_file_write_paths.py

def test_file_manager_default_path():
    """FileManager 默认路径使用 get_data_dir"""
    from file_manager import FileManager
    from utils import get_data_dir
    expected = os.path.join(get_data_dir(), "data", "file_history.json")
    assert FileManager.DEFAULT_DATA_FILE == expected

def test_voiceprint_default_path():
    """VoiceprintLibrary 默认路径使用 get_data_dir"""
    from voiceprint import VoiceprintLibrary
    from utils import get_data_dir
    lib = VoiceprintLibrary()
    expected = os.path.join(get_data_dir(), "data", "voiceprint_library.json")
    assert lib.library_path == expected

def test_config_project_root():
    """Config PROJECT_ROOT 使用 get_data_dir"""
    from config import PROJECT_ROOT
    from utils import get_data_dir
    assert PROJECT_ROOT == get_data_dir()
```

---

## 五、执行计划

### 第一步：删除无效测试（11 个文件）

```bash
# 删除存在性检查文件
rm tests/test_gui_startup.py
rm tests/test_home_page_p0.py
rm tests/test_infra.py
rm tests/test_optimization.py
rm tests/test_progress_display.py
rm tests/test_stop_button.py
rm tests/test_button_states.py
rm tests/test_embedding_save.py
rm tests/test_add_voice_dialog.py
rm tests/test_voiceprint_page.py
rm tests/test_voiceprint_page_e2e.py
```

### 第二步：新增核心测试（5 个文件）

1. `test_utils.py` - get_data_dir() 测试
2. `test_config_edge.py` - 配置错误场景
3. `test_transcription_core.py` - 转写核心逻辑
4. `test_file_write_paths.py` - 写入路径验证
5. `test_frozen_paths.py` - 打包路径逻辑（mock）

### 第三步：清理混合文件

对 test_async_integration.py、test_async_postprocess.py、test_settings_engine.py 等文件：
- 保留有实际逻辑的测试
- 删除 hasattr 检查

### 第四步：验证

```bash
# 运行精简后的测试
pytest tests/ -v

# 确保数量减少但覆盖率提高
```

---

## 六、给 Qoder 的审查指令

请 Qoder 审查以下内容：

1. **删除列表是否合理**：
   - 检查 `docs/02-plans/2026-06-26-plan-test-refactor.md` 中的删除文件列表
   - 确认没有遗漏需要保留的测试

2. **新增测试场景是否完整**：
   - 检查新增测试文件的内容
   - 确认覆盖了关键路径

3. **混合文件清理方案**：
   - 对 test_bugfix_v10.py 等文件，确认保留/删除的边界

4. **测试质量标准**：
   - 确认"场景测试"的定义
   - 确认删除 hasattr 检查的合理性

---

## 七、预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| 测试文件数 | 40 | ~30 |
| 总行数 | ~6000 | ~4000 |
| hasattr 检查 | 275 | 0 |
| 场景测试覆盖 | 30% | 70% |
| 关键路径测试 | 0 | 10+ |
