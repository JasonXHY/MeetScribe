# Qoder 交接文档

> 日期：2026-06-26
> 作者：MiMo Code
> 目的：向 Qoder 说明当前项目状态，请其审查修复方案

---

## 一、当前项目状态

### 1.1 代码位置
- **新版代码**：`C:\侧耳倾听\`（唯一工作目录）
- **旧版代码**：`C:\MeetScribe\`（只读参考，不可修改）

### 1.2 代码运行状态
- `C:\侧耳倾听\src\main.py` 启动正常，开发模式下功能正常
- **但打包后会有严重问题**（见下方）

### 1.3 今天完成的工作
1. 记忆文件分层重构（bonsai-memory 方式）
2. 文档目录整理（按类型分目录，统一命名规范）
3. 创建执行准则文档
4. 创建项目主线文档（README.md）
5. 全面代码审查

---

## 二、发现的关键问题

### 2.1 P0 问题（必须修复，否则打包后无法运行）

**问题 1：缺少 get_data_dir() 函数**

新版 `src/utils.py` 没有 `get_data_dir()` 函数。所有路径计算使用 `__file__`，在 PyInstaller 打包后会解析到 `_internal/`（只读目录），导致：
- 日志写入失败
- 配置文件写入失败
- 录音文件保存失败
- 转写结果保存失败
- 音色库保存失败

涉及文件（共 8 处）：
- `src/gui/app.py`：第 120、126、482 行
- `src/config.py`：第 15 行
- `src/file_manager.py`：第 130 行
- `src/voiceprint.py`：第 139 行
- `src/transcribe_worker.py`：第 20 行
- `src/gui/styles.py`：第 108 行

**问题 2：缺少 me.spec**

新版目录没有 PyInstaller 打包配置文件，无法打包。

**问题 3：缺少 installer.iss**

新版目录没有 Inno Setup 安装包配置文件，无法生成安装包。

### 2.2 P1 问题（建议修复）

| 文件 | 问题 |
|------|------|
| src/config.py | DEFAULTS 中 recording_dir、transcript_dir 使用 __file__ |
| src/gui/app.py | config_path、recording_dir、transcripts 路径使用 __file__ |
| src/gui/styles.py | MODEL_CACHE_DIR 使用 __file__ |
| src/voiceprint.py | library_path 使用 __file__ |
| src/file_manager.py | DEFAULT_DATA_FILE 使用 __file__ |

---

## 三、需要 Qoder 审查的内容

### 3.1 修复方案文档

请审查以下文档：

1. **代码审查报告**：`docs/03-reports/2026-06-26-report-code-audit.md`
   - 包含所有问题的详细分析
   - 包含修复优先级
   - 包含修复方案详情

2. **执行准则**：`docs/04-guides/2026-06-26-guide-execution-rules.md`
   - 包含打包前检查清单
   - 包含修改前检查清单

### 3.2 审查要点

请重点审查：

1. **修复方案的完整性**：
   - 是否遗漏了其他使用 __file__ 的地方？
   - 修复方案是否会影响现有功能？

2. **修复方案的正确性**：
   - get_data_dir() 的实现是否正确？
   - 路径替换是否完整？

3. **打包配置的正确性**：
   - me.spec 是否需要修改？
   - installer.iss 是否需要修改？

4. **测试建议**：
   - 修复后需要测试哪些功能？
   - 如何验证修复是否成功？

---

## 四、相关文件清单

### 4.1 源代码
- `src/utils.py` - 需要添加 get_data_dir()
- `src/config.py` - 需要修改路径计算
- `src/gui/app.py` - 需要修改路径计算
- `src/gui/styles.py` - 需要修改路径计算
- `src/file_manager.py` - 需要修改路径计算
- `src/voiceprint.py` - 需要修改路径计算
- `src/transcribe_worker.py` - 需要修改路径计算

### 4.2 配置文件
- `me.spec` - 需要从 C:\MeetScribe 复制并修改
- `installer.iss` - 需要从 C:\MeetScribe 复制

### 4.3 文档
- `docs/03-reports/2026-06-26-report-code-audit.md` - 代码审查报告
- `docs/04-guides/2026-06-26-guide-execution-rules.md` - 执行准则
- `docs/00-INDEX.md` - 文档索引
- `README.md` - 项目主线文档

---

## 五、下一步行动

### 5.1 优先级排序

1. **P0（必须）**：修复 get_data_dir() 和打包配置
2. **P1（建议）**：修复所有 __file__ 路径问题
3. **P2（可选）**：清理临时文件、优化测试文件命名

### 5.2 修复后验证

1. 开发模式测试：`python src/main.py`
2. 打包测试：PyInstaller + ISCC
3. 安装测试：安装到 Program Files 后运行
4. 功能测试：录音、转写、保存、音色库

---

## 六、联系方式

如有疑问，请联系用户 JasonXHY。

---

**请 Qoder 审查本文档和相关修复方案，确认无误后开始执行修复。**

---

## 七、Qoder 审查意见

> 审查日期：2026-06-26
> 审查人：Qoder
> 结论：问题定位基本准确，但有遗漏，以下为补充和修正

### 7.1 审查结论

原文档的问题定位方向正确，`get_data_dir()` 缺失确实是打包后的致命问题。但有以下遗漏需要补充：

**遗漏 1：`src/main.py` 也使用了 `__file__`（同为 P0）**

`main.py` 是程序入口，第 13-24 行用 `__file__` 计算 `PROJECT_ROOT`，并据此创建 logs、config、data、recordings、transcripts 五个目录。打包后这些目录会创建到 `_internal/` 下（只读），同样全部失败。修复时必须一并处理。

涉及行号：
- `src/main.py`：第 13 行（SRC_DIR）、第 18 行（PROJECT_ROOT）、第 21-24 行（目录创建）

**遗漏 2：`installer.iss` 的 `--data-dir` 参数未对接**

旧版 `installer.iss` 第 43 行会传 `--data-dir` 命令行参数给主程序，但新版 `main.py` 不解析命令行参数。需要在 `main.py` 中增加 `--data-dir` 参数解析，或者放弃此参数改为在代码中直接写死数据目录。

**遗漏 3：`src/gui/styles.py` 第 40 行 `ASSETS_DIR` 也使用了 `__file__`**

原文档只提了第 108 行的 `MODEL_CACHE_DIR`，但同文件第 40 行的 `ASSETS_DIR`（图标等资源目录）也用了 `__file__`，打包后图标加载也会失败。不过 `ASSETS_DIR` 指向的是打包时通过 `me.spec` 的 `datas` 打包进去的资源，属于只读资源，处理方式与可写数据目录不同——需要确认 PyInstaller 打包后 assets 的实际解压路径，可能需要用 `sys._MEIPASS` 而非 `get_data_dir()`。

### 7.2 修正后的完整修改清单

按执行顺序排列，共 3 步：

**第 1 步：添加 `get_data_dir()` 函数**

在 `src/utils.py` 中添加函数。直接复用旧版 `C:\MeetScribe\src\utils.py` 第 17-22 行的实现：

```python
def get_data_dir():
    """获取用户可写数据目录。打包模式用 %LOCALAPPDATA%\\MeetScribe，开发模式用项目目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'MeetScribe')
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

注意：需要在文件头部补充 `import sys`（当前 utils.py 没有导入 sys）。

**第 2 步：替换所有 `__file__` 路径计算**

逐个文件替换，每个文件改完后立即跑 `python src/main.py` 确认不报错：

| 文件 | 行号 | 当前写法 | 改为 |
|------|------|---------|------|
| `src/main.py` | L13,18,21-24 | `os.path.dirname(os.path.abspath(__file__))` | 导入 `from utils import get_data_dir`，用 `get_data_dir()` 替代 PROJECT_ROOT |
| `src/config.py` | L15 | `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` | `from utils import get_data_dir`，`PROJECT_ROOT = get_data_dir()` |
| `src/config.py` | L54 | 同上 | 同上 |
| `src/gui/app.py` | L120 | `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` | `from utils import get_data_dir`，用 `get_data_dir()` |
| `src/gui/app.py` | L126 | 同上 | 同上 |
| `src/gui/app.py` | L482 | 同上 | 同上 |
| `src/gui/styles.py` | L108 | 同上（4层 dirname） | `from utils import get_data_dir`，`MODEL_CACHE_DIR = os.path.join(get_data_dir(), 'models_cache')` |
| `src/file_manager.py` | L130 | `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` | `from utils import get_data_dir`，`get_data_dir()/data/file_history.json` |
| `src/voiceprint.py` | L139 | `os.path.dirname(os.path.dirname(__file__))` | `from utils import get_data_dir`，`get_data_dir()/data/voiceprint_library.json` |
| `src/transcribe_worker.py` | L20-21 | `os.path.dirname(os.path.abspath(__file__))` | 用 `get_data_dir()` 计算日志目录 |

**第 3 步：复制并修改打包配置**

- 从 `C:\MeetScribe\me.spec` 复制到 `C:\侧耳倾听\me.spec`，将 ROOT 改为 `r"C:/侧耳倾听"`
- 从 `C:\MeetScribe\installer.iss` 复制到 `C:\侧耳倾听\installer.iss`，确认路径引用正确
- `me.spec` 中 `hiddenimports` 可能需要补充 `pyaudiowpatch`、`soundfile` 相关依赖（打包时根据报错再调整）

### 7.3 关于 `ASSETS_DIR` 的特殊说明

`styles.py` 第 40 行的 `ASSETS_DIR` 指向 `assets/` 目录（图标、图片等资源）。这些资源在打包时通过 `me.spec` 的 `datas` 参数打进包内，运行时解压到临时目录 `sys._MEIPASS`。

所以 `ASSETS_DIR` 的修复方式与其他路径不同：
- 打包模式：`os.path.join(sys._MEIPASS, 'assets')`
- 开发模式：保持当前 `__file__` 计算方式即可

建议写一个 `get_assets_dir()` 函数统一处理，或者在 `ASSETS_DIR` 处直接加 `frozen` 判断。

### 7.4 关于数据目录的确认

当前旧版代码中 `get_data_dir()` 使用 `%LOCALAPPDATA%\MeetScribe`（本地目录，不跨机器同步）。旧版 `installer.iss` 使用 `%APPDATA%\MeetScribe`（漫游目录，跨机器同步）。两者不一致。

**建议统一使用 `%LOCALAPPDATA%\MeetScribe`**，理由：模型缓存和录音文件体积较大，不适合 roaming 同步。

### 7.5 验证计划（分两步，不要一步到位）

**第一步：开发模式验证（改完代码后立即做）**

1. 运行 `python src/main.py`，确认窗口正常显示
2. 测试录音功能（录一段 10 秒音频）
3. 测试转写功能（用录好的音频跑一次转写）
4. 检查 `data/voiceprint_library.json` 是否正常读写
5. 检查 `logs/meetscribe.log` 是否正常写入

**第二步：打包验证（第一步全部通过后才做）**

1. 运行 PyInstaller 打包
2. 到 `dist/侧耳倾听/` 目录下运行 `侧耳倾听.exe`
3. 确认 `%LOCALAPPDATA%\MeetScribe\` 目录被自动创建
4. 重复第一步的功能测试
5. 安装到 Program Files 后再次测试（验证写入权限）

### 7.6 迁移问题状态更新

之前记录的 5 个迁移问题（已归档至 `docs/06-archive/migration-gaps/`），当前状态：

| 问题 | 状态 | 说明 |
|------|------|------|
| 01-embeddings-save-missing | 已修复 | `transcription.py` L340 已实现 `_save_embeddings_to_disk()` |
| 02-dual-track-merge | 已处理 | 之前已确认 |
| 03-auto-correction-summary-sync | 待处理 | AI 同步阻塞问题，之前讨论过用 QThread 包裹，尚未实施 |
| 04-progress-display | 低优先级 | `hasattr(progress,'stage')` 在 home_page.py L622 仍在，但 dict 分支已能正常处理，仅为兜底死代码 |
| 05-sentences-and-preview | 已修复 | `PreviewDialog` 已改用 `QTextBrowser` 渲染 |

本次不处理 03 和 04，优先解决打包阻塞问题。
