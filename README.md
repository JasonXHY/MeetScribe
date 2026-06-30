# 侧耳倾听（MeetScribe）

> AI 会议录音转写助手 — 录音 → 转文字 → 识别谁在说话 → AI 生成会议纪要

---

## ⚠️ 重要规则（每次会话必读）

1. **工作目录**：所有修改针对 `C:\侧耳倾听\`，`C:\MeetScribe\` 只读参考
2. **打包前校验**：确认 me.spec 指向 `C:\侧耳倾听`，确认工具已安装
3. **决策先问**：技术选型、架构变更必须先问用户确认
4. **修改前确认**：编辑文件前打印完整路径

---

## 项目结构

```
C:\侧耳倾听\
├── src/                    # 源代码（唯一工作区）
│   ├── gui/                # GUI 模块（PySide6）
│   ├── config/             # 配置模块
│   ├── main.py             # 入口文件
│   ├── utils.py            # 工具函数（含 get_data_dir()）
│   └── *.py                # 业务逻辑模块
├── assets/                 # 图标等资源文件
├── config/                 # 配置模板
├── data/                   # 运行时数据
├── docs/                   # 所有文档（见下方文档索引）
├── tests/                  # 测试文件
├── scripts/                # 工具脚本
├── me.spec                 # PyInstaller 打包配置
├── installer.iss           # Inno Setup 安装包配置
├── CHANGELOG.md            # 版本变更记录
└── README.md               # 本文件（项目主线文档）
```

---

## 文档索引（Agent 入口）

**主线文档**：本文件（README.md）是项目单一真实来源

**详细文档**：见 `docs/00-INDEX.md`

| 类型 | 目录 | 用途 |
|------|------|------|
| 需求规格 | docs/01-specs/ | 了解项目需求和设计 |
| 实施方案 | docs/02-plans/ | 查看执行计划 |
| 复盘报告 | docs/03-reports/ | 回顾已完成工作 |
| 开发指南 | docs/04-guides/ | 查看开发规范 |
| 问题记录 | docs/05-issues/ | 排查当前问题 |
| 历史归档 | docs/06-archive/ | 查看历史文档 |
| 原型文件 | docs/99-mockups/ | 查看 UI 原型 |

**必读文档**：
- `docs/04-guides/2026-06-26-guide-execution-rules.md` - 执行准则
- `docs/00-INDEX.md` - 文档导航

---

## 核心功能

- **双轨录音**：支持麦克风 + 系统音频（WASAPI Loopback）
- **AI 转写**：FunASR SenseVoice + CAM++ 说话人分离 + ct-punc 标点恢复
- **AI 摘要**：云端大模型自动生成结构化会议纪要
- **声纹识别**：音色库管理，已知发言人自动命名
- **多格式输出**：Markdown / 纯文本 / SRT字幕 / JSON / HTML / CSV / VTT
- **多厂商支持**：小米 MiMo、百度、阿里、智谱等 10+ 国内大模型

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| GUI | PySide6 (Qt6) | 桌面界面，硬件加速 |
| 录音 | PyAudioWPatch | 支持 WASAPI Loopback |
| ASR | FunASR SenseVoice | 语音识别，中文优化 |
| 说话人分离 | CAM++ | 声纹识别，中文优化 |
| 标点恢复 | ct-punc | 标点恢复模型 |
| AI 摘要 | MiMo API | 云端大模型 |

---

## 快速开始

### 环境要求

- Windows 10/11
- Python 3.10+
- 4GB+ 内存

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/JasonXHY/MeetScribe.git
cd MeetScribe

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行应用
python src\main.py
```

### 首次运行

1. 应用会自动引导下载模型（约 2GB）
2. 配置 AI API Key（如需 AI 摘要功能）

---

## 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 运行指定测试
pytest tests/test_config.py

# 查看覆盖率
pytest --cov=src --cov-report=html
```

### 打包

```bash
# PyInstaller 打包
& "C:\侧耳倾听\venv_build\Scripts\pyinstaller.exe" --clean --noconfirm --distpath "C:\侧耳倾听\dist" --workpath "C:\侧耳倾听\build_spec" "C:\侧耳倾听\me.spec"

# ISCC 编译安装包
& "C:\Users\kingdee\AppData\Local\Programs\Inno Setup 6\ISCC.exe" "C:\侧耳倾听\installer.iss"
```

### 代码规范

- 遵循 PEP 8 风格
- 使用 type hints
- 添加必要的注释
- 编写测试用例

---

## 版本历史

见 [CHANGELOG.md](CHANGELOG.md)

---

## 许可证

本项目使用 [Unlicense](LICENSE) 许可证。

---

## 联系方式

- GitHub: [JasonXHY](https://github.com/JasonXHY)
- Issues: [GitHub Issues](https://github.com/JasonXHY/MeetScribe/issues)
