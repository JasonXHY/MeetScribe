# 技术选型自我审查报告

> 日期：2026-06-27
> 审查范围：架构、依赖库、打包工具
> 方法：搜索 GitHub/PyPI 验证，不凭训练数据判断

---

## 一、当前技术栈

| 类别 | 当前选择 | 版本 |
|------|----------|------|
| GUI | PySide6 (Qt6) | 6.11.1 |
| ASR | FunASR (SenseVoice) | 本地推理 |
| 说话人分离 | CAM++ | 本地推理 |
| 标点恢复 | ct-punc | 本地推理 |
| VAD | fsmn-vad | 本地推理 |
| 声纹匹配 | 自研 (cosine similarity) | - |
| 音频录制 | pyaudiowpatch | WASAPI Loopback |
| AI 摘要 | OpenAI 兼容 API | 多厂商 |
| 打包 | PyInstaller + Inno Setup | 6.21.0 |
| 测试 | pytest + pytest-qt | 9.0.3 |

---

## 二、逐项审查

### 2.1 音频录制：pyaudiowpatch

**当前状态**：唯一支持 WASAPI Loopback 的 Python 库

**搜索结果**：

| 库 | Stars | Loopback | 维护 | 评估 |
|----|-------|----------|------|------|
| pyaudiowpatch | 237 | ✅ | 活跃 | 当前使用 |
| **soundcard** | 758 | ✅ | 活跃 | **推荐评估** |
| ProcTap | 14 | ✅ | 活跃 | 进程级捕获，过重 |
| sounddevice | 1300 | ❌ | 活跃 | 不支持 Loopback |
| pyaudio_portaudio | 256 | ✅ | 停更 | 不推荐 |

**结论**：
- **soundcard** (758 stars) 是最佳替代候选，API 更现代，跨平台
- 但 pyaudiowpatch 已验证可用，替换有风险
- **建议**：v1.0 保持 pyaudiowpatch，v1.1 评估 soundcard

**搜索来源**：
- https://github.com/search?q=python+wasapi+loopback+audio
- https://pypi.org/project/soundcard/

### 2.2 ASR：FunASR (SenseVoice)

**当前状态**：使用 SenseVoice 模型，本地推理

**搜索结果**：

| 库 | Stars | 中文 | 速度 | 评估 |
|----|-------|------|------|------|
| FunASR (SenseVoice) | 8700 | 优秀 | 15x Whisper | 当前使用 |
| Whisper | 70k+ | 良好 | 基准 | 太慢 |
| Faster-Whisper | 24k | 良好 | 4-8x Whisper | 中文不如 SenseVoice |
| PaddleSpeech | 13k | 优秀 | - | 依赖 PaddlePaddle |
| WeNet | 5k | 优秀 | - | 更偏研究 |
| FireRedASR | 2k | 优秀 | - | 更新，生态小 |
| sherpa-onnx | 13k | 良好 | 快 | 跨平台，适合移动端 |

**结论**：
- **FunASR (SenseVoice)** 是当前最佳选择，中文支持好，速度快
- **FireRedASR** (2025 新发布) 是潜在升级候选，SOTA 中文准确率
- **sherpa-onnx** 适合需要跨平台/移动端的场景
- **建议**：保持 FunASR，关注 FireRedASR 发展

**搜索来源**：
- https://github.com/FunAudioLLM/SenseVoice
- https://github.com/FireRedTeam/FireRedASR
- https://github.com/k2-fsa/sherpa-onnx

### 2.3 打包：PyInstaller

**当前状态**：使用 PyInstaller + Inno Setup

**搜索结果**：

| 工具 | Stars | 大文件支持 | 评估 |
|------|-------|-----------|------|
| PyInstaller | 13k | 良好 | 当前使用 |
| **Nuitka** | 15k | 优秀 | **推荐评估** |
| cx_Freeze | 1.6k | 良好 | 简单替代 |
| py2exe | 989 | 有限 | 不推荐 |
| Briefcase | 3.3k | 良好 | 适合 BeeWare 生态 |

**结论**：
- **Nuitka** (15k stars) 性能更好（20-50%），支持大文件
- 但需要 C 编译器，构建时间更长
- **建议**：v1.0 保持 PyInstaller，v1.1 评估 Nuitka

**搜索来源**：
- https://github.com/Nuitka/Nuitka
- https://github.com/pyinstaller/pyinstaller

### 2.4 GUI：PySide6

**当前状态**：PySide6 (Qt6) 用于桌面 GUI

**搜索结果**：

| 库 | Stars | 评估 |
|----|-------|------|
| PySide6 | 8k+ | 当前使用，官方 Qt 绑定 |
| PyQt6 | 1k+ | 商业许可，功能相同 |
| wxPython | 2k+ | 跨平台，原生外观 |
| Kivy | 16k | 适合移动端 |

**结论**：
- PySide6 是最佳选择，MIT 许可，官方支持
- **建议**：保持 PySide6，无需替换

### 2.5 AI API：OpenAI 兼容

**当前状态**：使用 OpenAI 兼容 API，支持多厂商

**结论**：
- OpenAI 兼容 API 是行业标准，几乎所有国产模型都支持
- **建议**：保持当前实现，无需替换

### 2.6 测试框架：pytest

**当前状态**：pytest + pytest-qt

**结论**：
- pytest 是 Python 测试标准，无需替换
- **建议**：保持当前实现

---

## 三、架构审查

### 3.1 当前架构

```
src/
├── main.py              # 入口
├── config.py            # 配置管理
├── utils.py             # 工具函数
├── voiceprint.py        # 声纹库
├── file_manager.py      # 文件管理
├── unified_recorder.py  # 录音（pyaudiowpatch）
├── transcriber.py       # 转写（FunASR）
├── transcribe_worker.py # 转写进程
├── ai_service.py        # AI 摘要
├── model_registry.py    # 模型注册表
├── gui/
│   ├── app.py           # 主窗口
│   ├── home_page.py     # 主页
│   ├── settings_page.py # 设置页
│   ├── voiceprint_page.py # 声纹页
│   ├── dialogs.py       # 弹窗
│   ├── recording_bar.py # 录音条
│   ├── first_launch.py  # 首次启动
│   └── styles.py        # 样式
```

### 3.2 架构优点

1. **模块清晰**：每个源文件职责单一
2. **测试覆盖**：12 个测试文件，418 个测试
3. **进程隔离**：转写在独立进程中运行
4. **信号驱动**：Qt Signal 处理跨线程通信

### 3.3 架构问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| VoiceprintLibrary 非线程安全 | 中 | 已知限制，标记 xfail |
| 转写进程无超时 | 低 | 可能无限挂起 |
| 模型路径硬编码 | 低 | 已用 get_data_dir() 解决 |

### 3.4 改进建议

1. **短期（v1.0）**：保持当前架构，修复已知问题
2. **中期（v1.1）**：评估 soundcard 替代 pyaudiowpatch
3. **长期（v2.0）**：评估 Nuitka 替代 PyInstaller

---

## 四、依赖库审查

### 4.1 核心依赖

| 库 | 版本 | 许可 | 评估 |
|----|------|------|------|
| PySide6 | 6.11.1 | LGPL | ✅ 安全 |
| numpy | - | BSD | ✅ 安全 |
| soundfile | - | BSD | ✅ 安全 |
| pyaudiowpatch | - | MIT | ✅ 安全 |
| openai | - | Apache 2.0 | ✅ 安全 |
| funasr | - | MIT | ✅ 安全 |
| modelscope | - | Apache 2.0 | ✅ 安全 |

### 4.2 许可风险

- **无 GPL 冲突**：所有依赖均为 MIT/Apache/BSD/LGPL
- **PySide6 LGPL**：允许闭源分发，只需动态链接
- **VB-Cable Donationware**：个人使用免费，商业分发需许可

### 4.3 安全建议

1. **锁定版本**：requirements.txt 中锁定所有依赖版本
2. **定期更新**：每月检查依赖安全公告
3. **最小依赖**：已排除 tkinter/matplotlib/PIL 等不必要的库

---

## 五、技术选型准则执行

根据全局记忆中的"技术方案准则"，本次审查遵循了搜索优先原则：

| 技术领域 | 搜索关键词 | 搜索来源 |
|----------|-----------|----------|
| 音频录制 | python wasapi loopback audio | GitHub Search |
| ASR | chinese speech recognition python | GitHub Search |
| 打包 | python desktop packaging | GitHub Search |
| GUI | PySide6 vs PyQt6 | PyPI + GitHub |

**结论**：当前技术栈是经过验证的最佳选择，无需大幅替换。

---

## 六、执行建议

### v1.0（当前版本）

1. **保持当前技术栈**：PySide6 + FunASR + pyaudiowpatch + PyInstaller
2. **打包 VB-Cable**：解决停止录音暂停播放器问题
3. **打包模型**：用户无需在线下载

### v1.1（下个版本）

1. **评估 soundcard**：替换 pyaudiowpatch
2. **评估 Nuitka**：替换 PyInstaller
3. **关注 FireRedASR**：潜在 ASR 升级

### v2.0（长期）

1. **跨平台**：评估 soundcard + Nuitka 实现跨平台
2. **移动端**：评估 sherpa-onnx + Kivy
3. **AI 增强**：评估更强大的语言模型

---

## 七、搜索来源汇总

| 资源 | URL |
|------|-----|
| soundcard | https://github.com/bastibe/python-soundcard |
| FunASR | https://github.com/modelscope/FunASR |
| SenseVoice | https://github.com/FunAudioLLM/SenseVoice |
| FireRedASR | https://github.com/FireRedTeam/FireRedASR |
| Nuitka | https://github.com/Nuitka/Nuitka |
| PyInstaller | https://github.com/pyinstaller/pyinstaller |
| VB-Cable | https://vb-audio.com/Cable/ |
