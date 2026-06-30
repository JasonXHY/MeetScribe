# 打包问题修复报告

> 日期：2026-06-28
> 目的：记录打包过程中发现的所有问题和修复方案，请 Qoder 审核
> 背景：两次打包均因代码路径问题失败，浪费约 1 小时构建时间

---

## 一、问题时间线

| 时间 | 操作 | 结果 |
|------|------|------|
| 第 1 次打包 | PyInstaller + Inno Setup | 安装成功，但模型找不到 |
| 排查 | 检查模型目录结构 | 发现目录结构不匹配 |
| 第 2 次打包 | 修复目录结构后重新打包 | VB-Cable 安装失败 + 模型仍找不到 |
| 全面审计 | 检查所有代码路径 | 发现 4 个问题 |

---

## 二、发现的问题及修复

### 问题 1（致命）：MODEL_CACHE_DIR frozen 模式路径错误

**现象**：安装后所有 4 个模型显示"缺失"

**根因**：
- `styles.py:116` 定义 `MODEL_CACHE_DIR = os.path.join(get_data_dir(), "models_cache")`
- `get_data_dir()` 在 frozen 模式下返回 `%LOCALAPPDATA%/MeetScribe`
- 所以 `MODEL_CACHE_DIR` = `%LOCALAPPDATA%/MeetScribe/models_cache`
- 但 `_get_model_dir()` 在 frozen 模式下返回 `<app>/models`
- 所有使用 `MODEL_CACHE_DIR` 的地方（settings_page、transcription、voiceprint）都指向了错误的目录

**影响范围**：
- `settings_page.py:61` — ModelManager 初始化使用错误路径
- `transcription.py:158` — 转写 worker 使用错误路径
- `voiceprint.py:307` — 声纹模块使用错误路径

**修复**：
```python
# styles.py 修改
if getattr(sys, 'frozen', False):
    MODEL_CACHE_DIR = os.path.join(os.path.dirname(sys.executable), 'models')
else:
    MODEL_CACHE_DIR = os.path.join(get_data_dir(), "models_cache")
```

**Qoder 审核点**：修复是否正确？是否有其他地方也使用了 `get_data_dir()` + `"models_cache"` 的组合？

---

### 问题 2（中等）：VB-Cable 安装参数不完整

**现象**：安装完成后 VB-Cable 未生效

**根因**：Inno Setup 的 `[Run]` 段缺少 `/INSTALL` 参数，VB-Cable 安装程序可能静默跳过驱动注册

**修复**：
```ini
; 修复前
Parameters: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"

; 修复后
Parameters: "/VERYSILENT /INSTALL /SUPPRESSMSGBOXES /NORESTART"
```

**Qoder 审核点**：VB-Cable 的 Inno Setup 安装程序是否确实需要 `/INSTALL` 参数？请验证官方文档。

---

### 问题 3（中等）：VB-Cable fallback 默认值不一致

**现象**：config 默认 `True`，但 app.py fallback 是 `False`

**根因**：
- `config.py:30` — `DEFAULTS["use_vb_cable"] = True`
- `app.py:132` — `self.config.get("use_vb_cable", False)` fallback 是 `False`
- 如果 config 损坏返回 None，app.py 会用 False，而 settings_page 用 True

**修复**：
```python
# app.py 修改
use_vb_cable=self.config.get("use_vb_cable", True),  # False → True
```

**Qoder 审核点**：是否还有其他地方有类似的 fallback 不一致？

---

### 问题 4（低）：me.spec 缺少 modelscope hiddenimport

**现象**：PyInstaller 可能漏掉 modelscope 模块

**根因**：`transcriber.py:283` 有 `from modelscope import snapshot_download` 动态导入，PyInstaller 静态分析可能检测不到

**修复**：
```python
# me.spec hiddenimports 添加
'modelscope',
```

**Qoder 审核点**：是否还有其他动态导入需要添加到 hiddenimports？

---

### 问题 5（已修复）：VB-Cable 目录复制不完整

**现象**：第 1 次打包 VB-Cable 安装失败，报 "Missing inf file"

**根因**：`installer.iss` 只复制了 `VBCABLE_Setup_x64.exe`，没有复制 `.inf` 驱动文件

**修复**：
```ini
; 修复前
Source: "drivers\VBCABLE_Driver_Pack45\VBCABLE_Setup_x64.exe"; DestDir: "{tmp}\vbcable"

; 修复后
Source: "drivers\VBCABLE_Driver_Pack45\*"; DestDir: "{tmp}\vbcable"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall
```

**状态**：已修复，无需额外审核。

---

### 问题 6（已修复）：模型目录结构不匹配

**现象**：第 1 次打包模型找不到

**根因**：
- 代码期望：`cache_dir/models/iic/model_name`
- 实际复制：`cache_dir/model_name`

**修复**：
- 将模型复制到 `C:\侧耳倾听\models\models\iic\` 目录
- `installer.iss` 的 `[Files]` 段改为 `Source: "models\models\iic\*"`

**状态**：已修复，无需额外审核。

---

## 三、请 Qoder 审核的问题

### A. 路径一致性检查

请验证以下路径在所有代码中是否一致：

| 场景 | 预期路径 | 检查文件 |
|------|----------|----------|
| frozen 模式模型目录 | `<app>/models` | transcriber.py, styles.py, first_launch.py |
| frozen 模式 MODELSCOPE_CACHE | `<app>/models` | transcriber.py |
| 模型实际存放位置 | `<app>/models/models/iic/<name>` | installer.iss [Files] |
| VB-Cable 安装包位置 | `{tmp}\vbcable\` | installer.iss [Run] |

### B. 潜在遗漏检查

请检查以下是否还有问题：

1. **其他 `get_data_dir()` + 子目录的组合** — 是否还有地方用 `get_data_dir()` 拼接路径但未处理 frozen 模式？
2. **PyInstaller hiddenimports** — 除了 modelscope，是否还有其他动态导入需要添加？
3. **VB-Cable 安装后的重启逻辑** — 是否需要检测 VB-Cable 是否安装成功？
4. **首次启动对话框** — `_check_models_packaged()` 检查的路径是否与 `_get_model_dir()` 一致？

### C. 打包前最终检查清单

请确认以下项目：

- [ ] `styles.py` 的 `MODEL_CACHE_DIR` frozen 模式返回 `<app>/models`
- [ ] `transcriber.py` 的 `_get_model_dir()` 返回 `<app>/models`
- [ ] `first_launch.py` 的 `_check_models_packaged()` 检查 `<app>/models`
- [ ] `installer.iss` 的 `[Files]` 复制 `models\models\iic\*` 到 `{app}\models\models\iic`
- [ ] `installer.iss` 的 VB-Cable 安装包含 `/INSTALL` 参数
- [ ] `installer.iss` 的 VB-Cable 复制整个目录（含 .inf 文件）
- [ ] `me.spec` 的 hiddenimports 包含 `modelscope`
- [ ] `config.py` 的 `use_vb_cable` 默认值为 `True`
- [ ] `app.py` 的 fallback 默认值为 `True`
- [ ] `settings_page.py` 有 VB-Cable 开关 UI

---

## 四、修复后的代码变更清单

| 文件 | 变更 |
|------|------|
| `src/gui/styles.py` | `MODEL_CACHE_DIR` 添加 frozen 模式判断 |
| `src/gui/app.py` | `use_vb_cable` fallback `False` → `True` |
| `installer.iss` | VB-Cable 添加 `/INSTALL` 参数 |
| `installer.iss` | VB-Cable 复制整个目录 |
| `installer.iss` | 模型路径改为 `models\models\iic\*` |
| `me.spec` | hiddenimports 添加 `modelscope` |
| `src/config.py` | `use_vb_cable` 默认 `True`（之前已改） |
| `src/gui/settings_page.py` | 添加 VB-Cable 开关 UI（之前已改） |
| `src/transcriber.py` | 添加 `_get_model_dir()`（之前已改） |
| `src/gui/first_launch.py` | 模型已打包时跳过 Step 2（之前已改） |
| `LICENSE_CN.md` | 创建中文许可证（之前已改） |

---

## 五、Qoder 审核意见（2026-06-28）

> 逐条对照源码 + 网络搜索验证。上次审核不够细致导致打包踩坑，这次逐行核实。

### A. 逐条验证修复

#### 问题 1（MODEL_CACHE_DIR）— 修复正确 ✅

`styles.py:118-121` 已正确添加 frozen 分支。所有下游消费者（settings_page、transcription、voiceprint、first_launch）都通过 `from gui.styles import MODEL_CACHE_DIR` 获取路径，修改一处全局生效。

**额外确认**：全代码搜索了 14 处 `get_data_dir()` 调用，除 `models_cache` 外其余都是用户数据路径（config/、data/、recordings/、transcripts/、logs/），在 frozen 模式下正确指向 `%LOCALAPPDATA%\MeetScribe`，无需修改。

#### 问题 2（VB-Cable /INSTALL）— 修复存疑 ⚠️

经网络搜索，**VB-Cable 的 Inno Setup 安装程序不存在 `/INSTALL` 参数**。Inno Setup 的标准命令行参数只有 `/SILENT`、`/VERYSILENT`、`/SUPPRESSMSGBOXES`、`/NORESTART`、`/DIR=`、`/GROUP=`、`/NOICONS` 等。

来源：[Inno Setup - Setup Command Line Parameters](https://jrsoftware.org/ishelp/topic_setupcmdline.htm)

VB-Cable 安装失败的真实原因是**问题 5**（缺少 .inf 驱动文件），不是缺少 `/INSTALL` 参数。加上 `/INSTALL` 不会报错（Inno Setup 会忽略未知参数），但也不会产生任何效果。

**建议**：移除 `/INSTALL`，保留 `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` 即可。真正解决问题的是问题 5 的修复。

#### 问题 3（fallback 默认值）— 修复正确 ✅

`app.py:132` 已改为 `True`，与 `config.py` 的 DEFAULTS 一致。

#### 问题 4（modelscope hiddenimport）— 修复正确但不完整 ⚠️

`modelscope` 已添加到 hiddenimports，但搜索发现还有 **`markdown` 模块遗漏**：

```python
# src/gui/dialogs.py:195, 214
try:
    import markdown  # ← PyInstaller 无法静态检测
except ImportError:
    pass
```

这是 `try/except ImportError` 包裹的条件导入，PyInstaller 的模块图分析**不会跟踪它**。如果 markdown 模块未打包，预览对话框的 Markdown 渲染会静默失败（降级为纯文本）。

**需要添加到 hiddenimports**：

```python
hiddenimports=[
    # ... 现有 ...
    'markdown',  # gui/dialogs.py 条件导入
]
```

此外，以下本地模块仅在函数内部导入，PyInstaller 通常能找到但建议显式列出以防万一：

```python
'voiceprint',           # 多个 GUI 文件函数内导入
'dual_track_merge',     # app.py, home_page.py, transcribe_worker.py 函数内导入
'model_registry',       # settings_page.py 函数内导入
'gui.first_launch',     # app.py 函数内导入
'gui.dialogs',          # home_page.py 多处函数内导入
'gui.home_page',        # app.py 函数内导入
```

#### 问题 5（VB-Cable 目录）— 修复正确 ✅

`installer.iss` 已改为复制整个 `VBCABLE_Driver_Pack45\*` 目录（含 .inf 驱动文件）。这是 VB-Cable 安装失败的真实原因。

#### 问题 6（模型目录结构）— 修复正确 ✅

代码中 `transcriber.py:138` 的路径解析逻辑：
```python
local_path = os.path.join(cache_dir, "models", "iic", model_name)
```

frozen 模式下 `cache_dir = <exe_dir>/models`，所以完整路径是 `<exe_dir>/models/models/iic/<name>`。`installer.iss` 已正确将模型复制到 `{app}\models\models\iic`，路径匹配。

**注意**：`models/models/` 双层命名容易混淆。虽然功能正确，但建议将来重构时简化为单层。

### B. 报告未提及的新问题

#### 新问题 1：`--data-dir` 参数传入但从未解析

`installer.iss:51` 向 exe 传入了 `--data-dir "{userappdata}\MeetScribe"` 参数：

```ini
Filename: "{app}\侧耳倾听.exe"; Parameters: "--data-dir ""{userappdata}\MeetScribe"""
```

但 `main.py` 和 `app.py` 中**没有任何代码解析 `--data-dir` 参数**。`get_data_dir()` 在 frozen 模式下硬编码返回 `%LOCALAPPDATA%\MeetScribe`，恰好与 `{userappdata}\MeetScribe` 相同，所以功能不受影响。

**建议**：要么移除 installer.iss 中的 `--data-dir` 参数（避免误导），要么在 main.py 中添加参数解析。前者更简单。

#### 新问题 2：`SolidCompression=yes` 对 2GB 模型文件的影响

`installer.iss:20` 开启了 `SolidCompression=yes`。Solid 压缩会将所有文件视为一个连续数据流压缩，对大量小文件效果好，但对 2GB 的模型权重文件（本质上是接近随机数据的浮点数组），压缩率极低且**构建时间会非常长**。

根据 [Inno Setup 文档](https://jrsoftware.org/ishelp/topic_setup_compression.htm)，LZMA2 对不可压缩数据"expands about 0.005%"。

**建议**：考虑将 `SolidCompression` 改为 `no`，或者对模型文件单独使用 `nocompression` flag：

```ini
; 主程序用 solid 压缩
Source: "dist\侧耳倾听\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 模型文件不压缩（已经是压缩数据，再压缩浪费时间）
Source: "models\models\iic\*"; DestDir: "{app}\models\models\iic"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression
```

这样安装包体积几乎不变（模型压不了多少），但构建速度会快很多。

#### 新问题 3：`voiceprint.py` 导入了 `MODEL_CACHE_DIR` 但实际未使用

`voiceprint.py:307` 有 `from gui.styles import MODEL_CACHE_DIR`，但 `extract_embedding_from_file` 方法中 CAM++ 模型通过 `AutoModel(model="cam++")` 加载，使用的是 ModelScope 默认路径解析，**并不使用 `MODEL_CACHE_DIR`**。这是一个无害的未使用导入，但容易让人误以为声纹模块使用了正确的模型路径。

### C. 打包前最终检查清单（更新版）

- [x] `styles.py` 的 `MODEL_CACHE_DIR` frozen 模式返回 `<app>/models`
- [x] `transcriber.py` 的 `_get_model_dir()` 返回 `<app>/models`
- [x] `first_launch.py` 的 `_check_models_packaged()` 检查 `<app>/models`
- [x] `installer.iss` 的 `[Files]` 复制 `models\models\iic\*` 到 `{app}\models\models\iic`
- [ ] `installer.iss` 的 VB-Cable 安装参数**移除 `/INSTALL`**（不存在此参数）
- [x] `installer.iss` 的 VB-Cable 复制整个目录（含 .inf 文件）
- [x] `me.spec` 的 hiddenimports 包含 `modelscope`
- [ ] `me.spec` 的 hiddenimports **还需添加 `markdown`**
- [ ] `me.spec` 的 hiddenimports **建议添加本地模块**（voiceprint, dual_track_merge 等）
- [x] `config.py` 的 `use_vb_cable` 默认值为 `True`
- [x] `app.py` 的 fallback 默认值为 `True`
- [x] `settings_page.py` 有 VB-Cable 开关 UI
- [ ] `installer.iss` **移除 `--data-dir` 参数**或 main.py 添加解析
- [ ] `installer.iss` **考虑模型文件使用 `nocompression`**

### D. 上次审核反思

上次审核发现了 3 个高严重性问题（VB-Cable `/S` 参数、PyInstaller datas 打包模型、MODELSCOPE_CACHE 未设置），但遗漏了以下关键点：

1. **没有逐文件搜索 `get_data_dir()` 的所有调用点** — 如果搜索了，会发现 `MODEL_CACHE_DIR` 在 frozen 模式下的路径不一致问题。这次补上了。
2. **没有检查 `installer.iss` 的实际代码** — 如果看了 installer.iss，会发现 `--data-dir` 参数传入但未被解析。
3. **没有检查 hiddenimports 的完整性** — 只关注了 `modelscope`，遗漏了 `markdown` 和多个本地模块。

这些遗漏的根本原因是审核停留在"方案文档审查"层面，没有深入到实际代码和构建配置逐行核实。以后涉及打包部署的审核，必须同时审查 me.spec、installer.iss 和所有路径相关代码。
