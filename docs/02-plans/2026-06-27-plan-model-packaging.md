# 模型打包方案

> 日期：2026-06-27
> 状态：待 Qoder 审核
> 目标：将所需模型直接打包到安装包中，用户无需在线下载

---

## 一、现状分析

### 当前打包流程

```
PyInstaller (me.spec) → dist/侧耳倾听/ (~749MB)
    ↓
Inno Setup (installer.iss) → MeetScribe-1.0-Setup.exe (~750MB)
    ↓
用户安装 → 首次启动 → 从 ModelScope 下载 ~2GB 模型
```

### 当前 me.spec 分析

```python
# 入口
a = Analysis([os.path.join(ROOT, 'src', 'main.py')])

# 数据文件
datas=[
    (os.path.join(ROOT, 'assets'), 'assets'),           # 图标等
    (os.path.join(ROOT, 'src', 'config'), 'src/config'), # 配置文件
]

# 隐藏导入
hiddenimports=[
    'PySide6.QtWidgets', 'PySide6.QtCore', 'PySide6.QtGui',
    'soundfile', 'numpy', 'funasr', 'openai', 'pyaudiowpatch',
]
```

### 测试文件检查

**结论：项目测试文件未被打包。**

PyInstaller 只打包从 `main.py` 直接或间接导入的模块。`tests/` 目录不会被导入，因此不会进入 `dist/`。

dist 中发现的 test 文件来自第三方依赖（hydra、torch），不是项目代码。

### 当前 dist 内容

| 类别 | 大小 | 说明 |
|------|------|------|
| Python 运行时 | ~300MB | Python 3.12 + 标准库 |
| PySide6/Qt | ~200MB | GUI 框架 |
| FunASR/模型依赖 | ~150MB | ASR 运行时 |
| 其他依赖 | ~100MB | numpy, soundfile, openai 等 |
| 项目代码+资源 | ~50MB | src/ + assets/ |
| **合计** | **~750MB** | 不含模型 |

---

## 二、模型需求

### 必需模型（4 个）

| 模型 | 用途 | 大小 | 下载源 |
|------|------|------|--------|
| SenseVoiceSmall | 语音识别 (ASR) | ~900MB | ModelScope |
| ct-punc | 标点恢复 | ~1GB | ModelScope |
| cam++ | 说话人分离 | ~60MB | ModelScope |
| fsmn-vad | 语音端点检测 | ~2MB | ModelScope |
| **合计** | | **~2GB** | |

### 模型存储路径

当前运行时路径：`%LOCALAPPDATA%/MeetScribe/models_cache/models/iic/`

打包后建议路径：`{app}/models/`（与 exe 同目录）

---

## 三、打包方案

### 方案 A：模型打包到安装包（推荐）

```
PyInstaller → dist/侧耳倾听/ (~750MB)
    ↓
复制模型到 dist/侧耳倾听/models/ (~2GB)
    ↓
Inno Setup → MeetScribe-1.0-Setup.exe (~2.7GB)
    ↓
用户安装 → 直接可用，无需下载
```

**优点**：
- 用户体验最佳，安装即用
- 无需网络下载
- 模型版本可控

**缺点**：
- 安装包体积大（~2.7GB）
- 下载时间长
- 更新模型需重新打包

### 方案 B：模型打包到单独文件

```
PyInstaller → dist/侧耳倾听/ (~750MB)
    ↓
Inno Setup → MeetScribe-1.0-Setup.exe (~750MB)
    ↓
模型单独打包 → models.zip (~2GB)
    ↓
用户安装 exe + 解压 models.zip 到指定目录
```

**优点**：
- 安装包小
- 模型可独立更新

**缺点**：
- 用户需要手动操作
- 增加部署复杂度

### 方案 C：混合模式

```
PyInstaller → dist/侧耳倾听/ (~750MB)
    ↓
复制小模型（fsmn-vad, cam++, ~62MB）到 dist/
    ↓
大模型（SenseVoiceSmall, ct-punc）首次启动下载
    ↓
Inno Setup → MeetScribe-1.0-Setup.exe (~812MB)
```

**优点**：
- 安装包适中
- 大模型按需下载

**缺点**：
- 仍需下载 ~1.9GB
- 用户体验不完整

---

## 四、方案 A 实现步骤

### 步骤 1：修改 me.spec

```python
# me.spec 修改
import shutil

# 模型目录
MODEL_DIR = r"C:/侧耳倾听/models"
# VB-Cable 安装包
VB_CABLE_INSTALLER = r"C:/侧耳倾听/drivers/VBCABLE_Driver_Pack45/VBCABLE_Setup_x64.exe"

a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[ROOT, os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'assets'), 'assets'),
        (os.path.join(ROOT, 'src', 'config'), 'src/config'),
        # 添加模型文件
        (MODEL_DIR, 'models'),
        # 添加 VB-Cable 安装包
        (VB_CABLE_INSTALLER, 'drivers'),
    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'soundfile',
        'numpy',
        'funasr',
        'openai',
        'pyaudiowpatch',
    ],
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 'cv2', 'scipy', 'pandas',
        # 排除测试相关
        'pytest', 'unittest', 'mock', 'conftest',
    ],
    noarchive=False,
    optimize=1,
)
```

### 步骤 2：修改转写器路径

修改 `src/transcriber.py`，在 frozen 模式下使用打包的模型：

```python
import sys

def _get_model_dir():
    """获取模型目录"""
    if getattr(sys, 'frozen', False):
        # 打包模式：模型在 exe 同目录的 models/ 下
        return os.path.join(os.path.dirname(sys.executable), 'models')
    else:
        # 开发模式：使用缓存目录
        return os.path.join(get_data_dir(), 'models_cache')

MODEL_DIR = _get_model_dir()
```

### 步骤 3：修改 ModelManager

```python
class ModelManager:
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = _get_model_dir()
        self.cache_dir = cache_dir
        # ...
```

### 步骤 4：准备模型文件

```bash
# 从 ModelScope 下载模型到本地目录
# 或者从现有缓存复制
xcopy "%LOCALAPPDATA%\MeetScribe\models_cache\models" "C:\侧耳倾听\models\" /E /I
```

### 步骤 5：重新打包

```bash
# 清理旧构建
rmdir /s /q dist build

# PyInstaller 打包
pyinstaller me.spec

# 验证模型已包含
dir dist\侧耳倾听\models\

# Inno Setup 编译
iscc installer.iss
```

### 步骤 6：验证

1. 检查安装包大小（预期 ~2.7GB）
2. 安装后检查 `{app}/models/` 目录
3. 检查 VB-Cable 是否安装成功（音频设备列表中应出现 "CABLE Input"）
4. 运行程序，验证模型加载成功
5. 测试转写功能
6. 测试录音功能（确认使用 VB-Cable 录制系统音频）
7. 测试停止录音后媒体播放器是否继续播放

---

## 五、大小估算

| 组件 | 大小 |
|------|------|
| Python + 依赖 | ~750MB |
| SenseVoiceSmall | ~900MB |
| ct-punc | ~1GB |
| cam++ | ~60MB |
| fsmn-vad | ~2MB |
| VB-Cable 安装包 | ~1.3MB |
| **总计** | **~2.7GB** |

### 压缩后

| 压缩方式 | 预估大小 |
|----------|----------|
| LZMA2 (当前) | ~1.8GB |
| 不压缩 | ~2.7GB |

---

## 六、备选：模型排除方案

如果安装包过大，可排除部分模型：

| 排除模型 | 节省空间 | 影响 |
|----------|----------|------|
| ct-punc | ~1GB | 无标点恢复 |
| cam++ | ~60MB | 无说话人分离 |
| SenseVoiceSmall | ~900MB | **无法转写**（必须保留） |

**最小安装包**：仅 SenseVoiceSmall + fsmn-vad = ~1.7GB

---

## 七、VB-Cable 打包方案

### VB-Cable 简介

VB-Audio Virtual Cable 是一个虚拟音频设备，可以将系统音频输出重定向到录音输入。

**下载**：https://vb-audio.com/Cable/
**版本**：VBCABLE_Driver_Pack45（2024-10，支持 XP~Win11 32/64/Arm64）
**大小**：1.29 MB
**许可**：Donationware（个人使用免费，商业分发需许可）

### 打包优势

| 问题 | WASAPI Loopback | VB-Cable |
|------|-----------------|----------|
| 停止录音暂停播放器 | ❌ 会暂停 | ✅ 不会 |
| 需要额外安装 | ❌ 内置 | ✅ 需安装 |
| 音频质量 | ✅ 原生 | ✅ 虚拟设备 |
| 多应用支持 | ❌ 仅当前应用 | ✅ 全局生效 |

### 实现步骤

#### 步骤 1：下载 VB-Cable 安装包

```bash
# 下载 VB-Cable
mkdir C:\侧耳倾听\drivers\VBCABLE_Driver_Pack45
# 从 https://vb-audio.com/Cable/ 下载并解压
# 或直接使用静默安装版本
```

#### 步骤 2：Inno Setup 集成

修改 `installer.iss`，在安装完成后静默安装 VB-Cable：

```iss
[Files]
Source: "dist\侧耳倾听\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; VB-Cable 安装包
Source: "drivers\VBCABLE_Driver_Pack45\VBCABLE_Setup_x64.exe"; DestDir: "{tmp}\vbcable"; Flags: deleteafterinstall

[Run]
; 安装 VB-Cable（静默模式）
Filename: "{tmp}\vbcable\VBCABLE_Setup_x64.exe"; Parameters: "/S"; StatusMsg: "安装虚拟音频设备..."; Flags: waituntilterminated skipifsilent
; 安装完成后启动程序
Filename: "{app}\侧耳倾听.exe"; Parameters: "--data-dir ""{userappdata}\MeetScribe"""; Description: "安装完成后启动侧耳倾听"; Flags: nowait postinstall skipifsilent
```

#### 步骤 3：修改默认配置

修改 `src/config.py`，将 `use_vb_cable` 默认值改为 `True`：

```python
"use_vb_cable": True,  # v1.0.1: 默认使用 VB-Audio Cable
```

#### 步骤 4：恢复设置页 UI

修改 `src/gui/settings_page.py` 的 `_build_audio_section` 方法，添加 VB-Cable 开关：

```python
def _build_audio_section(self, layout):
    """音频设备设置"""
    group = self._create_group("音频设备", layout)

    # VB-Cable 开关
    self._vb_cable_cb = QCheckBox("使用 VB-Audio Cable 录制系统音频")
    self._vb_cable_cb.setChecked(self._config.get("use_vb_cable", True) if self._config else True)
    self._vb_cable_cb.stateChanged.connect(self._on_vb_cable_changed)
    group.layout().addWidget(self._vb_cable_cb)

    hint = QLabel("推荐开启：避免停止录音时暂停媒体播放器。需要管理员权限安装虚拟音频设备。")
    hint.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
    group.layout().addWidget(hint)

def _on_vb_cable_changed(self, state):
    """VB-Cable 开关变更"""
    if self._config:
        self._config.set("use_vb_cable", state == Qt.Checked)
```

### 注意事项

1. **管理员权限**：VB-Cable 安装需要管理员权限，Inno Setup 已请求 `PrivilegesRequired=admin`
2. **重启要求**：VB-Cable 安装后可能需要重启才能生效
3. **许可合规**：VB-Cable 是 Donationware，个人使用免费。如需商业分发，应联系 VB-Audio 获取许可
4. **静默安装**：VB-Cable 支持 `/S` 参数静默安装
5. **回退机制**：如果 VB-Cable 安装失败或未找到，程序会自动回退到 WASAPI Loopback

---

## 八、注意事项

1. **模型文件大**：PyInstaller 的 `datas` 对大文件处理较慢，打包时间可能增加 10-20 分钟
2. **Inno Setup 压缩**：LZMA2 对已压缩的模型文件压缩率很低
3. **磁盘空间**：构建时需要 ~5GB 临时空间
4. **网络带宽**：用户下载 1.8GB 安装包需要稳定网络
5. **更新机制**：模型更新需要重新打包分发

---

## 八、执行建议

1. **下载 VB-Cable 安装包**：从 https://vb-audio.com/Cable/ 下载 VBCABLE_Driver_Pack45
2. **修改配置**：`config.py` 中 `use_vb_cable` 默认改为 `True`
3. **恢复设置页 UI**：`settings_page.py` 添加 VB-Cable 开关
4. **修改 me.spec**：添加 VB-Cable 安装包到 datas
5. **修改 installer.iss**：添加 VB-Cable 静默安装
6. **准备模型文件**：复制模型到 `C:\侧耳倾听\models\`
7. **修改 transcriber.py**：frozen 模式下使用打包的模型
8. **重新打包**：PyInstaller + Inno Setup
9. **测试安装**：在干净环境测试安装、VB-Cable 安装、模型加载

---

## 九、首次启动提醒调整

### 当前 first_launch.py 结构

首次启动对话框有 2 个步骤（`_stack` QStackedWidget）：
1. **Step 1**：API Key 配置（内置 Key / 自己配置）
2. **Step 2**：模型下载

### 打包模型后的调整

| 场景 | 调整 |
|------|------|
| 模型已打包 | 移除 Step 2（模型下载），仅保留 API Key 配置 |
| 模型未打包 | 保留 Step 2，但需要真实下载（非模拟） |
| 到期日提醒 | 保留，在 Step 1 中添加到期日显示 |
| 录音方式引导 | 可选添加：解释"现场会议" vs "线上会议"模式 |

### 建议的首次启动流程

```
Step 1: API Key 配置
├── 显示到期日（如适用）
├── 选项 A：使用内置 Key
└── 选项 B：自己配置

[如果模型已打包，直接完成]
[如果模型未打包，进入 Step 2]

Step 2: 模型下载（可选）
├── 显示下载进度
└── 下载完成后自动进入主界面
```

---

## 十、录音方式分析与对比

### 当前实现

**库**：pyaudiowpatch（PyAudio 的 WASAPI Loopback 补丁版）

**架构**：
```
麦克风 ──→ 16kHz mono WAV ──→ {ts}会议.wav
                                    ↓
系统音频 ──→ 48kHz stereo WAV → {ts}会议_系统音频.wav
                                    ↓
                          dual_track_merge.py（按时间戳合并转写结果）
```

**优点**：
- WASAPI Loopback 是 Windows 原生 API，无需额外驱动
- pyaudiowpatch 是唯一支持 Loopback 的 Python 库
- 双轨录制，后期合并灵活

**痛点**：
1. **停止录音会暂停媒体播放器** — Windows WASAPI Loopback 的已知行为
2. **VB-Cable 外部依赖** — 需用户手动安装，未打包
3. **无实时混音** — 两个独立文件，用户需要分别处理
4. **采样率不匹配** — 麦克风 16kHz，系统音频 48kHz
5. **大文件** — WAV PCM_16 格式，1 小时双轨 ~1GB

### 用户给的三个方案评估

| 方案 | 适用性 | 评估 |
|------|--------|------|
| **方案一：WebRTC** | ❌ 不适用 | 我们是 PySide6 桌面应用，不是 Web 应用 |
| **方案二：Electron** | ❌ 不适用 | 我们是 Python + Qt，不是 Electron |
| **方案三：原生 WASAPI** | ✅ 已在用 | 我们已经在用 WASAPI Loopback（通过 pyaudiowpatch） |

**结论**：用户给的三个方案都不太适合当前项目。方案三是我们已经在做的事情。

### 更好的替代方案

#### 方案 A：sounddevice（推荐评估）

**库**：`sounddevice`（基于 PortAudio，MIT 协议）

**GitHub**：https://github.com/spatialaudio/python-sounddevice
**PyPI**：https://pypi.org/project/sounddevice/
**版本**：0.5.5（2026-01-23 更新，活跃维护）
**Stars**：2000+

**特点**：
- 跨平台（Windows/macOS/Linux）
- 基于 PortAudio，API 更现代
- 支持 NumPy 数组直接录音
- 社区更活跃，文档更完善

**WASAPI Loopback 支持**：
- PortAudio 在 Windows 上支持 WASAPI
- 但 **Loopback 模式需要 PortAudio 2.0+**，标准 PortAudio 可能不支持
- 需要确认 `sounddevice` 的 Windows 构建是否包含 Loopback 支持

**评估**：
- 如果 Loopback 支持完整 → 可以替换 pyaudiowpatch
- 如果不支持 → 只能用于麦克风录制，系统音频仍需 pyaudiowpatch

#### 方案 B：soundcard（备选）

**库**：`soundcard`（基于 PortAudio，但封装更高级）

**GitHub**：https://github.com/bastibe/python-soundcard
**特点**：
- 更高级的 API（录音机模式）
- 支持 Loopback 设备枚举
- 但维护不如 sounddevice 活跃

#### 方案 C：保持 pyaudiowpatch + 优化

**现状**：pyaudiowpatch 是唯一可靠支持 WASAPI Loopback 的 Python 库

**优化方向**：
1. **打包 VB-Cable** — 将 VB-Audio Cable 驱动打包到安装包，自动安装
2. **添加重采样** — 将系统音频从 48kHz 重采样到 16kHz，统一格式
3. **实时混音** — 可选将两路音频混合为单文件
4. **停止录音不暂停播放器** — 研究 WASAPI 的 IAudioClient 优化

#### 方案 D：FFmpeg 混音（最简单）

**思路**：保持 pyaudiowpatch 录制，用 FFmpeg 做后期处理

**优点**：
- 不改录音代码
- FFmpeg 功能强大（重采样、混音、压缩）
- 可以将双轨合并为单文件

**缺点**：
- 需要打包 FFmpeg（~100MB）
- 增加处理时间

### 综合建议

| 优先级 | 方案 | 工作量 | 风险 |
|--------|------|--------|------|
| **1** | 保持 pyaudiowpatch + 优化（方案 C） | 中 | 低 |
| 2 | 评估 sounddevice Loopback 支持 | 小 | 中 |
| 3 | 添加 FFmpeg 后期混音 | 小 | 低 |

**建议 v1.0 保持现状**：
- pyaudiowpatch 虽然有痛点，但功能完整
- 替换录音库风险高，可能引入新问题
- v1.1 再评估 sounddevice 或其他方案

**v1.0 可做的优化**：
1. 打包 VB-Cable 驱动（如果技术可行）
2. 添加重采样（统一 16kHz）
3. 改进首次启动引导（解释录音模式）

---

## 十一、GitHub 开源项目参考

### 录音相关

| 项目 | Stars | 语言 | 特点 |
|------|-------|------|------|
| [tez3998/loopback-capture-sample](https://github.com/tez3998/loopback-capture-sample) | 63 | Python | WASAPI Loopback 示例 |
| [keisuke-okb/ez-sound-capture](https://github.com/keisuke-okb/ez-sound-capture) | 9 | Python | soundcard + Loopback GUI |
| [pme-rodrigues/PyRecorder](https://github.com/pme-rodrigues/PyRecorder) | 0 | Python | soundcard + Loopback 录音 |
| [Studio-Sadola/flexaudio](https://github.com/Studio-Sadola/flexaudio) | 0 | Rust | 跨平台音频捕获（Rust 核心） |

### 会议录音工具

| 项目 | 特点 |
|------|------|
| [otter.ai](https://otter.ai) | 商业方案，云端处理 |
| [Whisper](https://github.com/openai/whisper) | OpenAI 语音识别（我们已在用 FunASR，类似） |

### 结论

GitHub 上没有找到比 pyaudiowpatch 更好的 WASAPI Loopback Python 库。pyaudiowpatch 虽然小众，但是目前唯一可靠的选择。

---

## 十二、Qoder 审核意见（2026-06-28，含网络验证）

> 以下每条都经过网络搜索验证，不依赖训练数据。

### A. 事实性错误（必须修正）

#### 1. VB-Cable 静默安装参数错误

方案写的 `/S` 是 NSIS 安装器的静默参数。VB-Cable 的安装包是 Inno Setup 格式，正确的参数是 `/SILENT` 或 `/VERYSILENT`。

```iss
; 错误（NSIS 风格，VB-Cable 不识别）
Parameters: "/S"

; 正确（Inno Setup 风格）
Parameters: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
```

来源：[Inno Setup 官方文档 - Setup Command Line Parameters](https://jrsoftware.org/ishelp/topic_setupcmdline.htm)

#### 2. VB-Cable 许可描述不完整

方案写"Donationware（个人使用免费，商业分发需许可）"过于简化。实际条款：

- **允许商业捆绑**：可以将标准 VB-Cable 打包到你的安装包中，但必须保留 Donationware 框架（用户可以看到官方网址并有机会捐赠）
- **企业部署**：如果部署到企业环境且员工无法自行捐赠，**分发方需支付批量许可费**
- **变体限制**：VB-Cable A+B 和 C+D **不允许捆绑分发**，只有标准版可以

来源：[VB-Audio Licensing](https://vb-audio.com/Services/licensing.htm)

#### 3. 安装包压缩估算偏高

方案写"LZMA2 → ~1.8GB"。根据 [Inno Setup 官方文档](https://jrsoftware.org/ishelp/topic_setup_compression.htm)，LZMA2 对不可压缩数据（模型权重文件本质上是大量浮点数，接近随机数据）"expands about 0.005%"。

实际压缩率：2GB 模型文件 → LZMA2 → 约 1.95~2.0GB（几乎没有压缩效果），加上 750MB 应用 → **总计约 2.7GB，非 1.8GB**。

### B. 技术方案问题（建议修正）

#### 4. PyInstaller datas 打包 2GB 模型是反模式

方案提议把 2GB 模型文件放入 PyInstaller 的 `datas` 字段。这是严重错误：

- **--onedir 模式**下，datas 会被复制到 `dist/侧耳倾听/` 目录中。这意味着模型文件只是被"复制"进 dist 文件夹，PyInstaller 不负责压缩或管理。这本身没问题，但方案混淆了"datas 打包"和"手动复制到 dist"
- **--onefile 模式**下，datas 会嵌入 exe 并在每次启动时解压到 `_MEIxxxxxx` 临时目录。2GB 模型解压需要数分钟，每次启动都要重复。**这是灾难性的用户体验**
- 当前项目用的是 `--onedir`（从 me.spec 分析），所以 datas 只是复制。但更规范的做法是：**不放进 datas，而是在 Inno Setup 的 [Files] 段直接复制模型目录**

**建议改为**：

```python
# me.spec 中不要放 models 到 datas
# 而是保持 models 作为独立目录

# Inno Setup 中直接复制：
[Files]
Source: "dist\侧耳倾听\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs
```

这样 PyInstaller 不碰模型文件，Inno Setup 直接复制到安装目录。构建更快、更可控。

#### 5. FunASR 模型加载路径未对齐

方案的 `_get_model_dir()` 返回 `{exe}/models/`，但 FunASR 的模型加载依赖 `MODELSCOPE_CACHE` 环境变量（见 `transcriber.py:95-100` 的 `_setup_modelscope_cache`）。仅仅修改 `_get_model_dir()` 不够，还需要确保：

```python
# 在 frozen 模式下，设置 MODELSCOPE_CACHE 指向打包的模型目录
if getattr(sys, 'frozen', False):
    model_dir = os.path.join(os.path.dirname(sys.executable), 'models')
    os.environ["MODELSCOPE_CACHE"] = model_dir
```

否则 FunASR 的 `AutoModel(model="SenseVoiceSmall")` 仍然会去默认的 `%LOCALAPPDATA%/MeetScribe/models_cache/` 找模型。

#### 6. soundcard 库被低估

方案把 soundcard 列为"方案 B 备选"，说"维护不如 sounddevice 活跃"。但经网络验证：

| 库 | WASAPI Loopback | API | 维护 | Stars |
|---|---|---|---|---|
| pyaudiowpatch | ✅ 原生支持 | PyAudio 风格 | v0.2.12.8（2026-01） | ~400 |
| soundcard | ✅ 原生支持 | 高级 Pythonic | v0.4.6（2026-04） | ~758 |
| sounddevice | ❌ 需重编译 PortAudio | 回调/流式 | 活跃 | ~2000 |

**soundcard 的实际 API 非常适合当前项目**：

```python
import soundcard as sc

# 枚举系统音频 loopback 设备
loopback_devices = sc.all_microphones(include_loopback=True)

# 录制系统音频
with loopback_devices[0].recorder(samplerate=48000) as capture:
    audio_chunk = capture.record(numframes=48000)
```

来源：[SoundCard 官方文档](https://soundcard.readthedocs.io/)、[GitHub](https://github.com/bastibe/SoundCard)

**但它确实不能替代 pyaudiowpatch**：soundcard 的 loopback 只能捕获系统音频输出，不支持麦克风录制。所以如果切换到 soundcard，仍然需要另一个库录麦克风，反而更复杂。**方案最终选择保持 pyaudiowpatch 是正确的。**

### C. sounddevice 方案确认为死路

方案中"方案 A：sounddevice（推荐评估）"建议 v1.1 评估。经网络验证，**此路不通**：

- python-sounddevice 的 Python API **没有原生 WASAPI loopback 支持**
- PortAudio 在 2021 年底合并了 loopback 实现，但 **默认预编译二进制不包含此功能**
- 需要用户自行重编译 PortAudio shared library
- 即使重编译成功，也**不支持自动重采样**，loopback 流的采样率固定为设备输出采样率
- 存在**间歇性静音丢帧**问题

来源：[python-sounddevice GitHub Issue #281](https://github.com/spatialaudio/python-sounddevice/issues/281)

**建议直接从评估列表中移除 sounddevice，避免后续浪费时间。**

### D. 其他建议

#### 7. 模型排除方案不完整

第六节说"如果安装包过大，可排除 ct-punc（~1GB）"。但 ct-punc 是标点恢复模型，去掉它会导致转写结果没有标点符号，可读性大幅下降。更实际的分层：

| 配置 | 大小 | 功能完整性 |
|------|------|-----------|
| 全部打包 | ~2.7GB | 完整 |
| 排除 ct-punc | ~1.7GB | 无标点（需 LLM 后处理补标点，成本更高） |
| 仅 SenseVoice + VAD | ~1.7GB | 能转写但无说话人分离无标点（基本不可用） |

**建议**：v1.0 全部打包，不做排除。2.7GB 的安装包在 2026 年是可以接受的（Zoom 安装包 600MB，Teams 800MB，但它们不需要 2GB 模型）。

#### 8. VB-Cable 安装后需重启

方案提到"可能需要重启"但没给出处理逻辑。实际上 VB-Cable 安装驱动后**几乎一定需要重启音频服务或重启系统**才能生效。建议在安装流程中：

- 如果 VB-Cable 安装成功但设备未检测到，提示用户重启
- 重启后首次启动时检测 VB-Cable 是否可用，如果可用则自动切换配置

#### 9. 首次启动流程简化建议

方案第九节建议保留 Step 2（模型下载）作为可选。如果模型已打包，Step 2 应该完全移除（不是"可选跳过"），否则用户会困惑为什么已安装还要下载。

### E. 汇总

| # | 类型 | 问题 | 严重性 |
|---|------|------|--------|
| 1 | 事实错误 | VB-Cable 静默安装参数 `/S` → `/VERYSILENT` | **高**（会导致安装失败） |
| 2 | 事实不完整 | VB-Cable 许可条款简化过度 | 中 |
| 3 | 估算偏差 | LZMA2 压缩 2.7GB → 1.8GB 不现实 | 中 |
| 4 | 技术方案 | PyInstaller datas 打包模型应改为 Inno Setup 直接复制 | **高** |
| 5 | 技术方案 | FunASR MODELSCOPE_CACHE 环境变量未设置 | **高**（模型找不到） |
| 6 | 评估偏差 | soundcard 被低估，但结论正确 | 低 |
| 7 | 死路确认 | sounddevice WASAPI loopback 不可用 | 低（避免浪费时间） |
| 8 | 流程缺失 | VB-Cable 安装后重启处理 | 中 |
| 9 | UX 建议 | 首次启动 Step 2 应完全移除 | 低 |
