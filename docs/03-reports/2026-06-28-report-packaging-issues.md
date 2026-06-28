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
