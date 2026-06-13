# 侧耳倾听（MeetScribe）

> AI 会议录音转写助手 — 录音 → 转文字 → 识别谁在说话 → AI 生成会议纪要

---

## 功能特性

- **双轨录音**：支持麦克风 + 系统音频（VB-Audio Cable / WASAPI Loopback）
- **AI 转写**：FunASR SenseVoice + CAM++ 说话人分离 + ct-punc 标点恢复
- **AI 摘要**：云端大模型自动生成结构化会议纪要
- **声纹识别**：音色库管理，已知发言人自动命名
- **多格式输出**：Markdown / 纯文本 / SRT字幕 / JSON / HTML / CSV / VTT
- **多厂商支持**：小米 MiMo、百度、阿里、智谱等 10+ 国内大模型

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

1. 应用会自动下载模型（约 2GB）
2. 如需双轨录音，会引导安装 VB-Audio Cable
3. 配置 AI API Key（如需 AI 摘要功能）

## 项目结构

```
MeetScribe/
├── src/                    # 源代码
│   ├── gui/                # GUI 模块（PySide6）
│   └── *.py                # 业务逻辑模块
├── tests/                  # 测试文件
├── docs/                   # 文档
│   ├── requirements.md     # 需求规格文档
│   ├── architecture.md     # 架构设计文档
│   └── development-guide.md # 开发协作指南
├── config/                 # 配置文件
├── data/                   # 运行时数据
└── models_cache/           # 模型缓存
```

## 文档

- [需求规格文档](docs/requirements.md) - 完整功能需求和验收标准
- [架构设计文档](docs/architecture.md) - 系统架构和技术设计
- [开发协作指南](docs/development-guide.md) - 开发环境搭建和协作流程
- [代码评审报告](代码评审报告-v2.md) - 详细代码评审结果
- [文件映射表](docs/FILE_MAPPING.md) - 文件位置对照

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| GUI | PySide6 (Qt6) | 桌面界面，硬件加速 |
| 录音 | PyAudioWPatch | 支持 WASAPI Loopback |
| ASR | FunASR SenseVoice | 语音识别，中文优化 |
| 说话人分离 | CAM++ | 声纹识别，中文优化 |
| 标点恢复 | ct-punc | 标点恢复模型 |
| AI 摘要 | MiMo API | 云端大模型 |

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

### 代码规范

- 遵循 PEP 8 风格
- 使用 type hints
- 添加必要的注释
- 编写测试用例

## 贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

本项目使用 [Unlicense](LICENSE) 许可证。

## 联系方式

- GitHub: [JasonXHY](https://github.com/JasonXHY)
- Issues: [GitHub Issues](https://github.com/JasonXHY/MeetScribe/issues)
