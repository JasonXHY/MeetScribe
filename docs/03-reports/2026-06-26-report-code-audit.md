# 代码审查报告

> 审查日期：2026-06-26
> 审查范围：C:\侧耳倾听 全部源代码
> 审查目的：确保打包后能正常运行

## 审查结论

**严重问题**：3 个
**中等问题**：5 个
**低风险问题**：3 个

---

## 严重问题（必须修复）

### 1. 缺少 get_data_dir() 函数

**问题**：新版 `utils.py` 没有 `get_data_dir()` 函数，所有路径计算使用 `__file__`

**影响**：打包后 `__file__` 解析到 `_internal/`（只读），导致：
- 日志写入失败
- 配置文件写入失败
- 录音文件保存失败
- 转写结果保存失败
- 音色库保存失败

**涉及文件**：
- `src/gui/app.py`：config_path, recording_dir, transcripts
- `src/config.py`：PROJECT_ROOT, recording_dir, transcript_dir
- `src/file_manager.py`：DEFAULT_DATA_FILE
- `src/voiceprint.py`：library_path
- `src/transcribe_worker.py`：_log_dir

**修复方案**：
1. 在 `utils.py` 添加 `get_data_dir()` 函数
2. 所有写入路径改用 `get_data_dir()`

---

### 2. 缺少打包配置文件

**问题**：新版目录缺少 `me.spec` 和 `installer.iss`

**影响**：无法打包

**修复方案**：
1. 从 `C:\MeetScribe` 复制 `me.spec` 并修改 ROOT 路径
2. 从 `C:\MeetScribe` 复制 `installer.iss`

---

### 3. models_cache 路径问题

**问题**：`gui/styles.py` 中 `MODEL_CACHE_DIR` 使用 `__file__` 计算

**影响**：打包后模型缓存路径错误

**涉及代码**：
```python
# 当前代码
MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models_cache')
```

**修复方案**：改用 `get_data_dir()` + 'models_cache'

---

## 中等问题（建议修复）

### 4. config.py DEFAULTS 路径

**问题**：`PROJECT_ROOT` 使用 `__file__` 计算，用于 recording_dir 和 transcript_dir 默认值

**影响**：默认路径指向 `_internal/` 而非用户目录

**修复方案**：改用 `get_data_dir()`

---

### 5. gui/app.py config_path

**问题**：config_path 使用 `__file__` 计算

**影响**：配置文件路径错误

**修复方案**：改用 `get_data_dir()` + 'config/settings.json'

---

### 6. gui/app.py recording_dir

**问题**：recording_dir 默认值使用 `__file__` 计算

**影响**：录音文件保存路径错误

**修复方案**：改用 `get_data_dir()` + 'recordings'

---

### 7. gui/app.py transcripts

**问题**：transcripts 路径使用 `__file__` 计算

**影响**：转写结果保存路径错误

**修复方案**：改用 `get_data_dir()` + 'transcripts'

---

### 8. voiceprint.py library_path

**问题**：voiceprint_library.json 路径使用 `__file__` 计算

**影响**：音色库保存路径错误

**修复方案**：改用 `get_data_dir()` + 'data/voiceprint_library.json'

---

## 低风险问题（可选修复）

### 9. scripts/ 目录混乱

**问题**：scripts/ 目录有临时脚本和 archive 子目录

**修复方案**：清理或重组

---

### 10. data/ 目录文件

**问题**：data/ 目录有 file_history.json 和 voiceprint_library.json

**说明**：这些是运行时数据，位置正确

---

### 11. tests/ 目录测试文件

**问题**：tests/ 目录有大量测试文件

**说明**：测试文件位置正确，但命名可以优化

---

## 修复优先级

| 优先级 | 问题 | 影响 |
|--------|------|------|
| P0 | 缺少 get_data_dir() | 打包后无法运行 |
| P0 | 缺少 me.spec | 无法打包 |
| P0 | 缺少 installer.iss | 无法打包 |
| P1 | models_cache 路径 | 模型缓存失败 |
| P1 | config.py DEFAULTS | 默认路径错误 |
| P1 | gui/app.py 路径 | 配置/录音/转写路径错误 |
| P2 | voiceprint.py 路径 | 音色库路径错误 |

---

## 修复方案详情

### 方案一：完整修复（推荐）

1. 创建 `utils.py` 的 `get_data_dir()` 函数
2. 修改所有写入路径使用 `get_data_dir()`
3. 复制并修改 me.spec
4. 复制 installer.iss

### 方案二：最小修复

1. 只修复 P0 问题
2. 暂时忽略 P1/P2 问题

---

## 测试建议

修复后需要测试：
1. 开发模式运行：`python src/main.py`
2. 打包后运行：安装到 Program Files 测试
3. 功能测试：录音、转写、保存、音色库

---

## 审查文件清单

| 文件 | 问题 | 行号 |
|------|------|------|
| src/utils.py | 缺少 get_data_dir() | - |
| src/config.py | PROJECT_ROOT 使用 __file__ | 15 |
| src/gui/app.py | config_path 使用 __file__ | 120 |
| src/gui/app.py | recording_dir 使用 __file__ | 126 |
| src/gui/app.py | transcripts 使用 __file__ | 482 |
| src/gui/styles.py | MODEL_CACHE_DIR 使用 __file__ | 108 |
| src/file_manager.py | DEFAULT_DATA_FILE 使用 __file__ | 130 |
| src/voiceprint.py | library_path 使用 __file__ | 139 |
| src/transcribe_worker.py | _log_dir 使用 __file__ | 20 |
| me.spec | 缺失 | - |
| installer.iss | 缺失 | - |
