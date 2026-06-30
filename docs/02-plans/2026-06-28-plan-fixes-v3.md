# 安装后问题修复方案 v3

> 日期：2026-06-28
> 状态：待用户确认

---

## 一、排查结果

### 1. VB-Cable 静默安装

**事实**：
- `VBCABLE_Setup_x64.exe` 不是 Inno Setup 安装程序（已验证）
- VB-Cable readme 写明需要手动运行安装程序
- VB-Cable 是 Donationware，安装后强制跳转捐赠页面

**但用户说之前是静默安装的**。需要确认：
- 之前的安装是什么时候？用的哪个版本的安装包？
- 是否有可能是通过其他方式（如预装驱动、注册表导入）实现的？

### 2. UI 差异分析（截图实测，2026-06-28 更新）

对比两张截图（测试版 = C:\侧耳倾听 源码运行，安装版 = C:\Program Files\MeetScribe）：

| 元素 | 测试版 | 安装版 | 根因 |
|------|--------|--------|------|
| 状态指示点 | ● 圆形 | ■ 方形 | DPI 缩放导致 CSS border-radius 渲染差异 |
| 暂停按钮 | 灰色无边框 | **红色有边框** | **代码 Bug：update_state() 停止分支漏重置 pause_btn 样式** |
| 停止按钮 | 灰色无边框 | 灰色有边框 | 同上，stop_btn 被重置了所以正常 |
| 模式 | 现场会议 | 线上会议 | 用户配置不同，非 Bug |
| 按钮底部 | 完整显示 | 下边框被裁切 | rec_card setFixedHeight(56) 太紧 |
| 合并文件标记 | 📎 小纸夹 | **奇怪彩色图标** | emoji (U+1F4CE) 在安装版字体下渲染为彩色 glyph |

**代码验证**（git 比对 42043c2 打包提交 vs 当前 HEAD）：
- `recording_bar.py` 的 `update_state()` 在两个版本中**完全一致**
- `styles.py` 的按钮样式定义在两个版本中**完全一致**
- Qt 版本均为 6.11.1

**结论**：不是 Qt 渲染差异，是代码 Bug + 布局尺寸问题。

#### Bug 详情：pause_btn 样式未重置

`recording_bar.py` 的 `update_state()` 方法，在"已停止/就绪"分支（else 分支，约第 299-349 行）：

```python
else:
    # 已停止 / 就绪
    self.stop_btn.setEnabled(False)
    self.stop_btn.setStyleSheet(f"""...灰色样式...""")  # ✅ 重置了
    self.pause_btn.setEnabled(False)                    # ❌ 只禁用了，没重置样式！
    self.pause_btn.setText("暂停")
    # pause_btn 的 setStyleSheet 完全缺失！
```

**复现路径**：开始录音 → 两按钮都变红色 → 停止录音 → stop_btn 重置为灰色，pause_btn 保持红色 → 开始转写 → stop_btn 又变红色，pause_btn 还是红色。

测试版截图两按钮都是灰色，是因为测试时没有"先录音再停止"这个操作流程，pause_btn 从未被设为红色。

#### 状态点形状差异

两个版本 CSS 完全一致（`border-radius: 5px` on 10x10 QLabel）。差异来自 DPI 缩放——Qt 对小数像素的 border-radius 在不同缩放比例下渲染效果不同。测试版和安装版如果不在同一 DPI 设置下运行就会出现。

#### 按钮底部裁切

`home_page.py:127` `rec_card.setFixedHeight(56)` 太紧：
- 布局 = 上边距10 + 按钮32 + 下边距10 + 卡片边框2 = 54px
- 56px 几乎无余量，DPI 缩放或字体渲染差异就会导致裁切

### 3. 模型路径

**已确认**：模型应放在 `%LOCALAPPDATA%/MeetScribe/models/`

---

## 二、修复方案

### A. 模型路径改为 AppData

**修改文件**：
1. `src/gui/styles.py` — `MODEL_CACHE_DIR` frozen 模式返回 `%LOCALAPPDATA%/MeetScribe/models`
2. `src/transcriber.py` — `_get_model_dir()` frozen 模式返回 `%LOCALAPPDATA%/MeetScribe/models`
3. `src/gui/first_launch.py` — `_check_models_packaged()` 检查 AppData 目录
4. `installer.iss` — 模型复制到 `{userappdata}\MeetScribe\models\`

### B. VB-Cable 改为手动安装提示

**修改文件**：
1. `installer.iss` — 移除 VB-Cable 自动安装
2. `src/gui/first_launch.py` — 添加 VB-Cable 安装提示页面
3. `src/config.py` — `use_vb_cable` 默认改为 `False`

### C. UI 差异修复（3 个问题）

#### C1. pause_btn 样式未重置（Bug 修复）

**修改文件**：`src/gui/recording_bar.py`

在 `update_state()` 的 `else` 分支（约第 299 行），pause_btn 部分补充 setStyleSheet：

```python
# 已停止 / 就绪
self.record_btn.setEnabled(True)
self.record_btn.setText("开始录音")
self.stop_btn.setEnabled(False)
self.stop_btn.setStyleSheet(f"""...""")  # 已有
self.pause_btn.setEnabled(False)
self.pause_btn.setText("暂停")
# ↓↓↓ 新增以下 setStyleSheet ↓↓↓
self.pause_btn.setStyleSheet(f"""
    QPushButton {{
        background-color: transparent;
        border: 1px solid {C_TXT3};
        border-radius: 6px;
        padding: 6px 12px;
        font-family: {FONT_FAMILY};
        font-size: 12px;
        color: {C_TXT3};
    }}
    QPushButton:hover {{
        background-color: #F0F0F0;
    }}
    QPushButton:disabled {{
        border-color: {C_TXT3};
        color: {C_TXT3};
    }}
""")
```

#### C2. 状态指示点形状（DPI 兼容）

**修改文件**：`src/gui/recording_bar.py`

将 `_rec_dot` 的 `border-radius: 5px` 改为 `border-radius: 6px`（略大于半径，确保在任何 DPI 下都渲染为圆形）：

```python
# 第 70-74 行，初始化时
self._rec_dot.setStyleSheet(f"""
    background-color: {C_TXT3};
    border-radius: 6px;
    border: none;
""")

# update_state() 中所有 _rec_dot.setStyleSheet 调用同样改为 6px
# 录音中（第 244 行）：border-radius: 6px
# 已暂停（第 273 行）：border-radius: 6px
# 已停止（第 324 行）：border-radius: 6px
```

#### C3. 按钮底部裁切

**修改文件**：`src/gui/home_page.py`

第 127 行，将 `setFixedHeight(56)` 改为 `setMinimumHeight(56)`，让布局自适应：

```python
# 改前
rec_card.setFixedHeight(56)
# 改后
rec_card.setMinimumHeight(56)
```

#### C4. 合并文件 emoji 渲染异常

**修改文件**：`src/gui/file_list_view.py`

`_display_name()` 方法使用 📎 (U+1F4CE) emoji 作为合并文件前缀，在安装版字体环境下被渲染为彩色图标 glyph（看起来像麦克风/文档图标），而非预期的小纸夹文本。

```python
# 改前
return f"📎 {name}"
# 改后
return f"[合并] {name}"
```

原因：emoji 是彩色字体 glyph，不同环境（系统字体、DPI、Qt 版本）渲染结果差异大。纯文本标记在所有环境下表现一致。

**已完成**：2026-06-28 直接修改。

---

## 三、执行步骤

1. 修改 `styles.py` 和 `transcriber.py` 的模型路径
2. 修改 `installer.iss`（模型路径 + 移除 VB-Cable + SolidCompression 评估）
3. 修改 `first_launch.py`（添加 VB-Cable 提示 + 调整 _check_models_packaged）
4. 修改 `config.py`（use_vb_cable 默认 False）
5. **修改 `recording_bar.py`**（C1: pause_btn 样式重置 + C2: border-radius 6px）
6. **修改 `home_page.py`**（C3: rec_card setMinimumHeight）
7. ~~修改 `file_list_view.py`~~（C4: emoji → 纯文本）**已完成**
8. 清理 build/dist 目录
9. 重新打包
10. 测试安装（重点：录音→停止→按钮颜色、状态点形状、按钮底部是否裁切、合并文件标记显示）

---

## 四、待用户确认

1. VB-Cable 是否改为手动安装提示？
2. SolidCompression 保持 `yes`（主程序压缩率好）还是改 `no`（构建更快）？
3. `PrivilegesRequired=admin` 是否保留？（v1.0 建议保留，v1.1 再考虑用户级安装）
4. `transcribe_worker.py` 的内联路径逻辑是否改为 import `get_data_dir()`？（低风险优化）

---

## 五、Qoder 审核意见（2026-06-28）

> 逐条对照当前代码（styles.py、transcriber.py、installer.iss、first_launch.py）+ 网络搜索验证。

### A. VB-Cable 改为手动提示 — 方向正确 ✅

经搜索验证，VB-Cable 官方文档只写了"Extract all files and Run Setup Program in administrator mode"，**没有任何命令行参数文档**。之前尝试的 `/VERYSILENT`、`/S`、`/INSTALL` 均无官方支持。VB-Cable 安装的是内核模式音频驱动，Windows 会弹出驱动信任提示，静默安装基本不可行。

来源：[VB-Audio Cable 官方页面](https://vb-audio.com/Cable/)、[VB-Cable Reference Manual](https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf)

**改为手动提示是正确的决策。** 但方案需要补充以下细节：

#### 需要补充 1：installer.iss 的具体改动

方案只说"移除 VB-Cable 自动安装"，但没列出具体要删哪些行。当前 installer.iss 中需要移除的内容：

```ini
; 第 39-40 行 — 删除 VB-Cable 文件复制
Source: "drivers\VBCABLE_Driver_Pack45\*"; DestDir: "{tmp}\vbcable"; ...

; 第 48-50 行 — 删除整个 [Run] 段（只有 VB-Cable 安装）
[Run]
Filename: "{tmp}\vbcable\VBCABLE_Setup_x64.exe"; ...
```

如果 [Run] 段只剩 VB-Cable 一项，整个 [Run] 段可以删除。但如果要保留"安装完成后启动程序"的功能，需要保留 [Run] 段并只删除 VB-Cable 那一行。

#### 需要补充 2：VB-Cable 手动安装提示放在哪里

方案说"添加 VB-Cable 安装提示页面"，但没说具体实现。建议：

- 在 first_launch.py 的 Step 1（API Key 配置）中添加一个可选提示："如果您需要录制线上会议的系统音频，建议安装 VB-Audio Cable 虚拟音频设备"
- 提供下载链接按钮（打开浏览器到 https://vb-audio.com/Cable/）
- 安装后检测按钮（检测 "CABLE Input" 音频设备是否存在）
- 检测通过后自动将 `use_vb_cable` 设为 True

#### 需要补充 3：`PrivilegesRequired=admin` 是否需要保留

当前 installer.iss:22 有 `PrivilegesRequired=admin`。移除 VB-Cable 自动安装后，安装程序本身不再需要管理员权限（模型复制到 AppData 不需要 admin）。但 `{autopf}\MeetScribe`（Program Files）的安装仍然需要 admin。如果保持默认安装路径不变，admin 权限仍需保留。

### B. 模型路径改为 AppData — 方向正确 ✅

将模型从 `<app>/models`（Program Files，需 admin 权限写入）改为 `%LOCALAPPDATA%/MeetScribe/models`（用户目录，可写）是正确的。原因：

1. ModelScope 的缓存机制需要写入 `model_status.json` 等状态文件，Program Files 下需要 admin 权限
2. 用户未来可能需要更新模型，不应要求 admin
3. 与 config/、data/、recordings/ 等其他用户数据目录保持一致

#### 需要注意 1：ModelScope 路径嵌套

代码中 `_resolve_model_path` 的路径拼接逻辑（`transcriber.py:138`）：

```python
local_path = os.path.join(cache_dir, "models", "iic", model_name)
```

如果 `cache_dir = %LOCALAPPDATA%/MeetScribe/models`，完整路径为：
`%LOCALAPPDATA%/MeetScribe/models/models/iic/SenseVoiceSmall`

installer.iss 需要对应：

```ini
; 源路径不变（构建目录），目标改为 AppData
Source: "models\models\iic\*"; DestDir: "{userappdata}\MeetScribe\models\models\iic"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression
```

**`models/models/` 双层命名仍然别扭**，但功能正确。将来重构时可以简化。

#### 需要注意 2：`_check_models_packaged()` 逻辑需调整

当前 `first_launch.py:78-83` 检查 `<exe_dir>/models` 是否存在。改为 AppData 后：

```python
def _check_models_packaged(self):
    if getattr(sys, 'frozen', False):
        # 改为检查 AppData 目录
        model_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'MeetScribe', 'models')
        return os.path.exists(model_dir)
    return False
```

但更根本的问题是：如果 installer.iss 总是把模型复制到 AppData，那 `_check_models_packaged()` 永远返回 True，Step 2（模型下载）永远不会显示。这个函数实际上变成了死代码。建议保留但简化为 `return getattr(sys, 'frozen', False)`——frozen 模式下模型总是已打包的。

#### 需要注意 3：`_setup_modelscope_cache` 环境变量

`transcriber.py:110-117` 的 `_setup_modelscope_cache(cache_dir)` 设置 `MODELSCOPE_CACHE` 环境变量。确保调用时传入的是新的 AppData 路径。当前 `ModelManager.__init__` 会调用 `_setup_modelscope_cache(self.cache_dir)`，只要 `cache_dir` 正确就没问题。

### C. 方案遗漏的问题

#### 遗漏 1：`SolidCompression=yes` 仍然存在

当前 installer.iss:20 仍是 `SolidCompression=yes`。上次审核已建议对模型文件使用 `nocompression` flag（已在第 38 行添加），但全局的 `SolidCompression=yes` 仍会影响其他文件的压缩行为。2GB 模型文件的 solid 压缩会导致**构建时间极长**。

**建议**：保持 `SolidCompression=yes` 用于主程序文件（压缩效果好），但确保模型文件行有 `nocompression` flag（当前已有）。如果构建仍然很慢，考虑改为 `SolidCompression=no`。

#### 遗漏 2：UI 差异分析不够深入 — 已解决 ✅

上次审核指出 UI 差异归因"Qt 渲染差异"过于草率。经截图实测 + 代码追踪，已确认根因：
- pause_btn 样式未重置（代码 Bug，见 C1）
- 状态点 border-radius DPI 兼容（见 C2）
- rec_card 固定高度裁切（见 C3）

#### 遗漏 3：`recording_bar.py` 的按钮样式 — 已解决 ✅

上次审核建议确认是否有条件样式逻辑。经代码验证，`update_state()` 的"已停止"分支确实缺少 pause_btn 的 setStyleSheet 调用，已补充修复方案（C1）。

### D. 执行步骤补充

方案的 7 步执行步骤需要调整：

| 步骤 | 内容 | 补充 |
|------|------|------|
| 1 | 修改 styles.py 模型路径 | `MODEL_CACHE_DIR` frozen 分支改为 `os.path.join(os.environ.get('LOCALAPPDATA', ''), 'MeetScribe', 'models')` |
| 2 | 修改 transcriber.py 模型路径 | `_get_model_dir()` frozen 分支同上 |
| 3 | 修改 installer.iss | 模型目标改为 `{userappdata}\MeetScribe\models\models\iic`；移除 VB-Cable [Files] 和 [Run]；评估 SolidCompression |
| 4 | 修改 first_launch.py | `_check_models_packaged()` 简化为 `return getattr(sys, 'frozen', False)`；添加 VB-Cable 手动安装提示 |
| 5 | 修改 config.py | `use_vb_cable` 默认改为 `False` |
| 6 | **修改 recording_bar.py** | C1: `update_state()` else 分支补充 pause_btn setStyleSheet；C2: 所有 `_rec_dot` border-radius 改为 6px |
| 7 | **修改 home_page.py** | C3: `rec_card.setFixedHeight(56)` 改为 `setMinimumHeight(56)` |
| 8 | 清理 build/dist | 同时删除 `dist\侧耳倾听\models\` 旧目录 |
| 9 | 重新打包 | |
| 10 | 测试安装 | 重点测试：模型加载、VB-Cable 提示、录音→停止按钮颜色、状态点形状、按钮底部 |

### E. 汇总

| # | 项目 | 评价 |
|---|------|------|
| 1 | VB-Cable 改手动提示 | ✅ 正确，静默安装不可行 |
| 2 | 模型路径改 AppData | ✅ 正确，但注意 `models/models/` 嵌套 |
| 3 | UI 差异归因 |  上次归因"Qt 渲染差异"错误，实为代码 Bug（pause_btn 样式未重置）+ 布局尺寸问题 |
| 4 | installer.iss 改动细节 | ️ 方案未列出具体改动行 |
| 5 | `_check_models_packaged()` | ⚠️ 逻辑需调整（永远 True 时简化） |
| 6 | app.py `use_vb_cable` fallback | ✅ 保持 True 不改（用户确认：VB-Cable 是录制在线会议音频必需的） |
| 7 | SolidCompression | ️ 保持 `yes`，主程序压缩率收益大于构建成本 |
| 8 | 首次启动 VB-Cable 提示 UI | ❌ 方案说"添加"但无实现细节 |
| 9 | **pause_btn 样式重置** |  原方案完全遗漏，本次新增（代码 Bug） |
| 10 | **状态点 border-radius** |  原方案完全遗漏，本次新增（DPI 兼容） |
| 11 | **rec_card 高度裁切** | ❌ 原方案完全遗漏，本次新增（布局尺寸） |
| 12 | **合并文件 emoji 渲染** |  原方案完全遗漏，本次新增并直接修复（emoji → 纯文本） |
| 13 | **运行时写入路径** | ✅ 全量审查通过，所有写入均指向 AppData |
| 14 | **PrivilegesRequired=admin** | v1.0 保留，v1.1 考虑用户级安装 |
| 15 | **models/models/ 嵌套** | v1.1 重构清理 |
| 16 | **transcribe_worker.py 内联路径** | 低优先级，建议改为 import |
| 17 | **安装程序版本号/卸载清理** | v1.1 补充 |

---

## 六、Program Files 安装限制与打包方案优化分析

> 2026-06-28 · 基于网络搜索 + 全量代码审查

### 1. Program Files 的写入限制

安装在 `C:\Program Files` 的程序，运行时的权限规则：

- **普通用户**：对 Program Files 目录**只有读和执行权限**，无法写入任何文件
- **管理员用户**：日常运行时也以**标准用户令牌**运行（UAC 虚拟化），程序不会自动获得 admin 权限，除非显式提权
- **写入后果**：如果程序试图在 Program Files 下创建/修改文件，普通用户会直接报 `PermissionError`；管理员用户可能触发 UAC 弹窗或被 UAC 虚拟化重定向

这是 Windows Vista 以来的安全机制，所有安装在 Program Files 的软件都必须遵守。

### 2. 当前代码审计结论：写入路径全部安全 ✅

对 `C:\侧耳倾听\src\` 下全部 27 个 Python 源文件做了逐文件审查，检查所有 `open('w')`、`os.makedirs`、`os.remove`、`shutil.copy/move` 操作的目标路径。

**结论：当前代码的所有文件写入操作都正确地指向 `%LOCALAPPDATA%\MeetScribe`（通过 `get_data_dir()`），没有任何写入会触及 Program Files 目录。**

具体分布：

| 写入目标 | 路径来源 | 涉及文件 |
|----------|----------|----------|
| `%LOCALAPPDATA%\MeetScribe\config\settings.json` | `get_data_dir()` | config.py |
| `%LOCALAPPDATA%\MeetScribe\logs\meetscribe.log` | `get_data_dir()` | main.py |
| `%LOCALAPPDATA%\MeetScribe\data\voiceprint_library.json` | `get_data_dir()` | voiceprint.py |
| `%LOCALAPPDATA%\MeetScribe\data\file_history.json` | `get_data_dir()` | file_manager.py |
| `%LOCALAPPDATA%\MeetScribe\recordings\` | config → `get_data_dir()` | unified_recorder.py |
| `%LOCALAPPDATA%\MeetScribe\transcripts\` | config → `get_data_dir()` | transcriber.py, transcription.py |
| `%TEMP%\` 临时文件 | `tempfile` 模块 | transcriber.py |
| 用户选择的导出路径 | `QFileDialog` | dialogs.py |

**只读操作**（安全）：
- `sys._MEIPASS\assets\` — 图标文件读取（styles.py）
- `sys._MEIPASS\` — Python 模块加载（PyInstaller 运行时）
- `__file__` — 仅用于 `sys.path` 设置和开发模式路径计算

**一个小瑕疵**：`transcribe_worker.py` 第 21-25 行内联复制了 `get_data_dir()` 的逻辑，而不是直接 import 该函数。当前结果一致，但如果将来 `get_data_dir()` 修改了，这里可能漏改导致路径不一致。建议改为直接 `from utils import get_data_dir`。

### 3. 安装程序（installer.iss）层面的问题

虽然运行时写入路径都正确，但安装程序本身有几个可以优化的地方：

#### P1. `PrivilegesRequired=admin` — 评估是否仍需保留

当前 installer.iss 第 22 行要求管理员权限安装。移除 VB-Cable 自动安装后，安装程序做的所有事情：
- 复制程序文件到 `{autopf}`（Program Files）→ 需要 admin
- 复制模型到 `{localappdata}` → 不需要 admin
- 创建 AppData 目录 → 不需要 admin

**如果保持默认安装到 Program Files**，`PrivilegesRequired=admin` 仍然需要保留，因为写 Program Files 本身就需要 admin。

**如果改为默认安装到 `{localappdata}\MeetScribe`**（类似 VS Code 的用户级安装），则可以完全去掉 admin 要求。这是更现代的做法，好处是：
- 普通用户也能安装，不需要 UAC 弹窗
- 更新/卸载不会有权限问题
- 与 Chrome、VS Code、Discord 等主流软件的做法一致

> **建议**：v1.0 正式版保持当前方案（Program Files + admin），v1.1 考虑提供"用户级安装"选项。

#### P2. `SolidCompression=yes` — 构建性能问题

当前第 20 行 `SolidCompression=yes` 把所有文件当作一个连续压缩流。虽然模型文件行（第 38 行）已有 `nocompression` flag 跳过压缩，但 Solid 模式仍会影响其他文件的压缩策略：

- **构建时**：Solid 压缩需要先收集所有文件再统一压缩，对大文件集（即使模型已排除）仍增加内存占用和构建时间
- **安装时**：Solid 压缩需要按顺序解压，无法并行，安装速度略慢
- **好处**：主程序文件（Python DLL、PySide6 等）有大量重复数据，Solid 压缩率明显更好

> **建议**：保持 `SolidCompression=yes`，主程序压缩率提升的收益大于构建时间的增加。如果后续模型更新频繁导致重新构建次数多，再考虑改为 `no`。

#### P3. 模型路径 `models/models/iic/` 双层嵌套

installer.iss 第 38 行的目标路径 `{localappdata}\MeetScribe\models\models\iic` 有双层 `models`，原因是代码中 `_resolve_model_path()` 会在 `cache_dir` 后拼接 `models/iic/model_name`。

当前功能正确，但路径结构不直观。将来重构时建议：
- 方案 A：installer 直接放到 `{localappdata}\MeetScribe\models\iic\`，代码中 `_resolve_model_path` 去掉多余的 `models/` 拼接
- 方案 B：保持现状，在代码注释中说明原因

> **建议**：v1.0 不改（功能正确，改动风险大于收益），v1.1 重构时统一清理。

#### P4. 安装程序缺少版本号和卸载清理

当前 installer.iss 的 `AppVersion=1.0` 是硬编码的。建议：
- 从文件读取版本号（Inno Setup 的 `#define` 预处理或 `[Code]` 段读取文件）
- 卸载时清理 `{localappdata}\MeetScribe` 中的模型目录（当前卸载只删除 Program Files 下的文件）

> **建议**：v1.0 先不改，v1.1 补充。

### 4. me.spec（PyInstaller 打包）审查

| 项目 | 当前值 | 评价 |
|------|--------|------|
| `optimize=1` | 移除 docstring 和 assert | ✅ 合理，减小体积 |
| `noarchive=False` | 打包为 .pyz 归档 | ✅ 合理 |
| `upx=True` | 压缩 DLL/exe | ✅ 合理 |
| `console=False` | 无控制台窗口 | ✅ 正确 |
| `excludes` | tkinter/matplotlib/PIL/cv2/scipy/pandas | ✅ 排除不需要的库 |
| `hiddenimports` | 包含 funasr/modelscope/pyaudiowpatch 等 | ✅ 覆盖完整 |
| `datas` | assets + funasr 包 | ✅ 正确 |

**一个潜在风险**：`hiddenimports` 中列出了 `gui.first_launch`、`gui.dialogs`、`gui.home_page`，但没有列出 `gui.transcription`、`gui.settings_page`、`gui.voiceprint_page`、`gui.topbar`、`gui.recording_bar`、`gui.file_list_view`、`gui.styles`。这些模块可能是通过 `app.py` 的直接 import 被 PyInstaller 自动检测到的（不需要 hiddenimports），但如果有条件 import（如 `try/except`），就可能被遗漏。

> **建议**：下次打包后如果某个页面报 `ModuleNotFoundError`，优先检查这里。当前如果能正常启动就说明没问题。

### 5. 汇总建议

| # | 项目 | 优先级 | 建议 |
|---|------|--------|------|
| 1 | 运行时写入路径 | ✅ 无需改动 | 所有写入已正确指向 AppData |
| 2 | `PrivilegesRequired=admin` | v1.1 | 当前保留，将来考虑用户级安装 |
| 3 | `SolidCompression=yes` | 保留 | 主程序压缩率收益大于构建成本 |
| 4 | `models/models/` 嵌套 | v1.1 | 功能正确，将来统一清理 |
| 5 | `transcribe_worker.py` 内联路径 | 低 | 建议改为 import `get_data_dir()` |
| 6 | 安装程序版本号 | v1.1 | 改为动态读取 |
| 7 | 卸载清理 AppData | v1.1 | 补充卸载时删除模型目录 |
| 8 | hiddenimports 完整性 | 观察 | 当前能启动就没问题 |
