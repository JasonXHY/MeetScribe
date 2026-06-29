# 打包后无法调用 AI 转写模型 — 根因分析与解决方案

- 日期：2026-06-28
- 影响范围：通过 PyInstaller 打包并安装的发行版（开发模式不受影响）
- 现象：软件能正常启动、界面正常、云端摘要可用，但**点击转写时本地语音识别（FunASR / SenseVoice ASR）无法工作**

## 一、现象

从打包版本安装后启动软件，一旦执行语音转写，转写子进程立即失败。日志（`%LOCALAPPDATA%\MeetScribe\logs\meetscribe.log`）中反复出现：

```
ERROR MeetScribe [SUBPROCESS] - Failed to extract embedding from file: No module named 'funasr'
```

界面之所以能正常打开，是因为 `funasr` 是**懒加载**的——只有在真正转写时才导入：

- `src/transcriber.py` → `from funasr import AutoModel`
- `src/voiceprint.py` → `from funasr import AutoModel`

因此 GUI、设置、云端摘要（纯 `openai` / `httpx`，与 funasr 无关）都正常，唯独转写一启动就报 `No module named 'funasr'`，ASR 模型从未成功加载。

## 二、根本原因

打包产物中 **`funasr` 及其依赖树根本无法被 `import`**。原 `me.spec` 的处理方式在结构上是错误的：

1. **把 funasr 当作 `datas` 拷贝，而不是按「代码」收集。**
   原写法 `(.../site-packages/funasr, 'funasr')` 只是把目录作为数据文件复制进包里，
   这个目录不会进入 `sys.path`，所以运行时 `import funasr` 依然失败。
   Python 模块必须作为**代码**收集，不能当数据文件。

2. **手写的 `hiddenimports` 子模块列表必然不全。**
   FunASR 通过 `tables.register` 装饰器**动态注册**模型类，并按字符串在运行时
   导入大量子模块。PyInstaller 的静态分析无法跟踪这种动态导入，手列 7 个子模块
   远不足以覆盖。

3. **整条依赖链都缺失。**
   FunASR 依赖 `torch`、`torchaudio`、`modelscope`、`sentencepiece`、`kaldiio`、
   `jieba` 等重型包，而原 `me.spec` 中**完全没有**这些包（既无 `collect_all`，
   也无 torch 相关 hiddenimports）。即便 funasr 能导入，紧接着 `import torch`
   也会失败。

> 注：先前的修复提交 `36db900`（"add funasr to PyInstaller hiddenimports and datas"）
> 正是踩中了第 1、2 点，所以没能真正解决问题。

## 三、解决方案

用 PyInstaller 的 `collect_all()` 取代「手动 datas + 部分 hiddenimports」的做法。
`collect_all()` 会一次性收集一个包的**子模块、数据文件和原生二进制**，并对其依赖
逐个执行，从而完整地把 funasr 整条依赖链打进包里。

`me.spec` 顶部改为：

```python
from PyInstaller.utils.hooks import collect_all

_collect_packages = [
    'funasr', 'torch', 'torchaudio', 'modelscope',
    'sentencepiece', 'kaldiio', 'jieba',
]
_collected_datas, _collected_binaries, _collected_hiddenimports = [], [], []
for _pkg in _collect_packages:
    _d, _b, _h = collect_all(_pkg)
    _collected_datas += _d
    _collected_binaries += _b
    _collected_hiddenimports += _h
```

随后把这三个列表分别并入 `Analysis(...)` 的 `binaries` / `datas` / `hiddenimports`，
并删除原来手动拷贝 funasr 目录的那一行以及不完整的子模块列表。

同时从 `excludes` 中移除 `scipy`——FunASR 依赖 scipy，若继续排除会破坏 ASR 路径。

## 四、注意事项

- **`torch` 体积很大**，且必须在**真正安装了 funasr / torch 的 Windows 构建环境**中
  执行打包；否则 `collect_all('torch')` 收集不到任何东西。
- 本次改动在 macOS 上无法构建验证（产物为 Windows `.exe`，且该环境未安装这些重型依赖），
  因此这是「根因 + 针对性修复」，尚未经过构建验证。
- 重新打包后，验证方式：转写一个音频，日志中应出现 `Models loaded successfully`，
  而不再是 `No module named 'funasr'`。
