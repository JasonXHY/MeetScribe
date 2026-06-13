# 侧耳倾听（MeetScribe）

> AI 会议录音转写助手

---

## 简介

侧耳倾听是一款本地 AI 会议录音转写工具，支持：
- 双轨录音（麦克风 + 系统音频）
- AI 语音转文字（FunASR SenseVoice + CAM++ 说话人分离）
- AI 摘要生成（MiMo 云端）
- 声纹识别与管理（音色库）
- 多格式输出（Markdown / HTML / SRT 字幕 / TXT / JSON）

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动程序
python src/main.py

# 或使用启动脚本
MeetScribe.bat
```

## 目录结构

```
C:\MeetScribe\
├── src/                    # 源代码
│   ├── main.py             # 入口
│   ├── gui/                # GUI 模块
│   │   ├── app.py          # 主窗口
│   │   ├── home_page.py    # 主页
│   │   ├── topbar.py       # 顶部导航栏
│   │   ├── settings_page.py # 设置页
│   │   ├── voiceprint_page.py # 音色库页面
│   │   ├── file_list_view.py # 文件列表组件
│   │   ├── recording_bar.py  # 录音控制栏
│   │   ├── dialogs.py      # 弹窗组件
│   │   ├── styles.py       # 样式常量
│   │   └── transcription.py # 转写调度
│   ├── transcriber.py      # 转写引擎
│   ├── transcribe_worker.py # 子进程工作函数
│   ├── unified_recorder.py # 录音模块
│   ├── ai_service.py       # AI 服务
│   ├── voiceprint.py       # 声纹库
│   ├── file_manager.py     # 文件管理
│   ├── config.py           # 配置管理
│   └── speaker_namer.py    # 说话人姓名提取
├── config/                 # 配置文件
├── data/                   # 数据文件（音色库）
├── models_cache/           # 模型缓存（~1.8GB）
├── recordings/             # 录音文件
├── transcripts/            # 转写输出
├── tests/                  # 单元测试
├── docs/                   # 文档
│   ├── README.md           # 本文档
│   ├── ARCHITECTURE.md     # 架构说明
│   ├── CHANGELOG.md        # 版本变更
│   ├── FILE_MAPPING.md     # 文件映射（重构前后对照）
│   ├── agents/             # Agent 工作区
│   ├── archive/            # 归档文档
│   └── superpowers/        # 设计文档
└── assets/                 # 图标资源
```

## 技术栈

- Python 3.12 + customtkinter（GUI）
- FunASR SenseVoice + CAM++ + ct-punc（语音转写）
- MiMo API（AI 摘要/纠错）
- PyAudioWPatch（双轨录音）
- VB-Audio Cable（虚拟音频设备）

## 文档导航

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 技术架构详解 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [ERROR_TRACKING.md](ERROR_TRACKING.md) | Bug 跟踪 |
| [FILE_MAPPING.md](docs/FILE_MAPPING.md) | 文件映射表 |
| [docs/user_manual.md](docs/user_manual.md) | 用户手册 |
| [docs/superpowers/TODO.md](docs/superpowers/TODO.md) | 当前待办 |

## Agent 协作

本项目由多个 AI Agent 协作开发：

| Agent | 角色 | 工作区 |
|-------|------|--------|
| MiMo Code | 主力开发、架构设计 | `docs/agents/mimo-code/` |
| QoderWork | UI/UX 设计、方案评审 | `docs/agents/qoderwork/` |
| Claude Code | 辅助开发、代码审查 | `docs/agents/claude-code/` |

详见 [docs/agents/README.md](docs/agents/README.md)

## 版本

当前版本：v0.9（开发版）
正式版名称：侧耳倾听 v1.0
