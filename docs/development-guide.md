# 侧耳倾听（MeetScribe）— 开发协作指南

> 版本：v3.0
> 日期：2026-06-14
> 状态：正式协作版
> 受众：开发者

---

## 一、快速开始

### 1.1 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 推荐 3.12 |
| Git | 最新 | 版本控制 |
| Windows | 10/11 | 仅支持 Windows |
| FFmpeg | 最新 | 音频处理（可选，FunASR 已集成） |

### 1.2 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/JasonXHY/MeetScribe.git
cd MeetScribe

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key（复制模板并填入）
copy config\settings.json.example config\settings.json
# 编辑 config\settings.json，填入你的 MiMo API Key

# 5. 运行应用
python src\main.py
```

### 1.3 首次运行

1. 应用会自动检测并下载模型（约 2GB）
2. 如果需要双轨录音，会引导安装 VB-Audio Cable
3. 配置 AI API Key（如果需要 AI 摘要功能）
4. 进入主界面

---

## 二、项目结构

```
MeetScribe/
├── src/                        # 源代码
│   ├── gui/                    # GUI 模块（PySide6）
│   │   ├── __init__.py
│   │   ├── app.py              # 主窗口 (479行)
│   │   ├── home_page.py        # 主页 (887行)
│   │   ├── settings_page.py    # 设置页 (551行)
│   │   ├── voiceprint_page.py  # 音色库页 (641行)
│   │   ├── dialogs.py          # 弹窗组件 (1132行)
│   │   ├── recording_bar.py    # 录音控制栏 (403行)
│   │   ├── file_list_view.py   # 文件列表 (603行)
│   │   ├── topbar.py           # 顶部导航栏 (154行)
│   │   ├── styles.py           # 样式常量 (342行)
│   │   ├── transcription.py    # 转写调度 (438行)
│   │   └── first_launch.py     # 首次启动引导
│   │
│   ├── config.py               # 配置管理 (~150行)
│   ├── file_manager.py         # 文件管理 (~300行)
│   ├── unified_recorder.py     # 录音模块 (~400行)
│   ├── transcriber.py          # 转写引擎 (~1300行)
│   ├── transcribe_worker.py    # 子进程工作函数 (~200行)
│   ├── ai_service.py           # AI 服务 (~300行)
│   ├── voiceprint.py           # 声纹库 (~400行)
│   ├── speaker_namer.py        # 说话人命名 (~250行)
│   ├── dual_track_merge.py     # 双轨合并 (~150行)
│   ├── model_registry.py       # 模型注册表 (~200行)
│   ├── formatters.py           # 格式化器 (~300行)
│   ├── transcription_queue.py  # 转写队列 (~150行)
│   ├── model_manager.py        # 模型管理
│   ├── utils.py                # 工具函数 (~100行)
│   └── main.py                 # 入口
│
├── tests/                      # 测试文件
│   ├── conftest.py             # pytest 配置
│   ├── test_config.py          # 配置测试
│   ├── test_file_manager.py    # 文件管理测试
│   ├── test_voiceprint.py      # 声纹测试
│   ├── test_transcription.py   # 转写测试
│   ├── test_dialogs_p0.py      # 弹窗测试
│   ├── test_home_page_p0.py    # 主页测试
│   ├── test_gui_startup.py     # GUI 启动测试
│   └── ...                     # 其他测试
│
├── docs/                       # 文档
│   ├── requirements.md         # 需求规格文档
│   ├── architecture.md         # 架构设计文档
│   ├── development-guide.md    # 开发协作指南（本文件）
│   ├── FILE_MAPPING.md         # 文件映射表
│   └── archive/                # 归档文档
│
├── config/                     # 配置文件
│   └── settings.json           # 应用配置（不提交到Git）
│
├── data/                       # 运行时数据
│   ├── file_history.json       # 文件历史
│   └── voiceprint_library.json # 声纹库
│
├── models_cache/               # 模型缓存（不提交到Git）
├── recordings/                 # 录音文件
├── transcripts/                # 转写结果
├── logs/                       # 日志文件
│
├── requirements.txt            # Python 依赖
├── .gitignore                  # Git 忽略规则
├── LICENSE                     # 许可证 (Unlicense)
└── README.md                   # 项目说明
```

---

## 三、开发规范

### 3.1 代码风格

#### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `MeetScribeApp`, `TranscriptionHandler` |
| 函数/方法 | snake_case | `start_recording()`, `_on_state_change()` |
| 变量 | snake_case | `file_path`, `recording_mode` |
| 常量 | UPPER_SNAKE_CASE | `APP_VERSION`, `DEFAULT_SPK_QUALITY` |
| 私有成员 | 前缀下划线 | `_poll_timer`, `_log_area` |
| 信号 | snake_case | `log_message`, `transcription_done` |

#### 文件组织

```python
# 1. 标准库导入
import os
import sys
import logging
from datetime import datetime

# 2. 第三方库导入
from PySide6.QtWidgets import QMainWindow, QWidget
from PySide6.QtCore import Qt, QTimer

# 3. 本地模块导入
from gui.styles import C_BG, C_CARD
from gui.topbar import TopBar
from config import Config
```

#### 注释规范

```python
class MeetScribeApp(QMainWindow):
    """主窗口
    
    职责：应用入口，窗口管理，全局状态协调
    
    依赖：
    - gui 模块：TopBar, HomePage, SettingsPage, VoiceprintPage
    - 业务模块：Config, FileManager, UnifiedRecorder
    """
    
    def __init__(self):
        """初始化主窗口
        
        流程：
        1. 初始化业务逻辑（Config, FileManager, Recorder）
        2. 初始化 UI 组件（TopBar, Pages, StatusBar）
        3. 连接信号和槽
        4. 恢复配置
        """
        super().__init__()
        # ...
```

### 3.2 Git 工作流

#### 分支策略

```
main          ← 稳定版本，可随时部署
  └── dev     ← 开发分支，日常开发
       ├── feature/xxx  ← 功能分支
       ├── fix/xxx      ← 修复分支
       └── docs/xxx     ← 文档分支
```

#### 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type 类型**：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**scope 范围**：
- `gui`: GUI 模块
- `core`: 业务逻辑
- `transcribe`: 转写引擎
- `voiceprint`: 声纹库
- `ai`: AI 服务
- `config`: 配置管理

**示例**：
```
feat(gui): 添加 API Key 明文切换按钮

在 settings_page.py 中添加 👁 按钮，
点击可切换 API Key 的明文/密文显示。

Closes #42
```

#### 提交频率

- 每个独立功能/修复一个提交
- 不要提交半成品代码
- 提交前运行测试确保通过

### 3.3 代码审查

#### 审查清单

- [ ] 代码符合命名规范
- [ ] 没有硬编码的魔法数字/字符串
- [ ] 异常处理适当（不吞异常）
- [ ] 线程安全（UI 操作在主线程）
- [ ] 没有敏感信息（API Key、密码）
- [ ] 添加了必要的注释
- [ ] 测试覆盖核心逻辑

#### 审查流程

1. 提交 Pull Request
2. 自动运行测试
3. 至少一人审查通过
4. 合并到 dev 分支
5. 定期合并到 main 分支

---

## 四、开发任务流程

### 4.1 新功能开发

```
1. 需求确认
   ├── 阅读 docs/requirements.md 确认需求
   ├── 确认验收标准
   └── 确认优先级

2. 设计讨论
   ├── 在 GitHub Issues 中讨论方案
   ├── 确认技术选型
   └── 评估工作量

3. 开发实现
   ├── 从 dev 分支创建功能分支
   ├── 实现功能
   ├── 编写测试
   └── 运行测试确保通过

4. 代码审查
   ├── 提交 Pull Request
   ├── 至少一人审查
   └── 根据反馈修改

5. 合并部署
   ├── 合并到 dev 分支
   ├── 定期合并到 main 分支
   └── 打标签发布版本
```

### 4.2 Bug 修复

```
1. 问题复现
   ├── 确认问题存在
   ├── 记录复现步骤
   └── 确认影响范围

2. 问题分析
   ├── 定位问题代码
   ├── 分析根本原因
   └── 评估修复方案

3. 修复实现
   ├── 从 dev 分支创建修复分支
   ├── 实现修复
   ├── 编写回归测试
   └── 运行测试确保通过

4. 代码审查
   ├── 提交 Pull Request
   ├── 至少一人审查
   └── 根据反馈修改

5. 合并部署
   ├── 合并到 dev 分支
   ├── 定期合并到 main 分支
   └── 更新 CHANGELOG
```

### 4.3 文档更新

```
1. 确认需要更新的文档
   ├── 需求变更 → docs/requirements.md
   ├── 架构变更 → docs/architecture.md
   └── 使用变更 → README.md

2. 编写文档
   ├── 清晰准确
   ├── 包含示例
   └── 保持格式一致

3. 提交审查
   ├── 提交 Pull Request
   ├── 至少一人审查
   └── 根据反馈修改

4. 合并部署
   └── 合并到 dev 分支
```

---

## 五、测试指南

### 5.1 运行测试

```bash
# 运行所有测试
pytest

# 运行指定测试文件
pytest tests/test_config.py

# 运行指定测试函数
pytest tests/test_config.py::TestConfig::test_get

# 运行 P0 测试
pytest -k "p0"

# 查看详细输出
pytest -v

# 查看覆盖率
pytest --cov=src --cov-report=html
```

### 5.2 编写测试

#### 测试文件命名

```
test_<module>.py          # 单元测试
test_<module>_p0.py       # P0 功能测试
test_<module>_e2e.py      # 端到端测试
```

#### 测试函数命名

```python
def test_<功能>_<场景>_<预期结果>():
    """测试 <功能> 在 <场景> 下应该 <预期结果>"""
    # Arrange: 准备测试数据
    # Act: 执行被测试的操作
    # Assert: 验证结果
```

#### 测试示例

```python
import pytest
from config import Config

class TestConfig:
    """配置管理测试"""
    
    def test_get_existing_key(self, tmp_path):
        """测试获取已存在的配置项"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{"key": "value"}')
        config = Config(str(config_file))
        
        # Act
        result = config.get("key")
        
        # Assert
        assert result == "value"
    
    def test_get_missing_key_with_default(self, tmp_path):
        """测试获取不存在的配置项时返回默认值"""
        # Arrange
        config_file = tmp_path / "settings.json"
        config_file.write_text('{}')
        config = Config(str(config_file))
        
        # Act
        result = config.get("missing", "default")
        
        # Assert
        assert result == "default"
```

### 5.3 GUI 测试

```python
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

@pytest.fixture
def app():
    """创建 QApplication 实例"""
    return QApplication.instance() or QApplication([])

def test_button_click(app):
    """测试按钮点击"""
    from gui.home_page import HomePage
    
    # Arrange
    page = HomePage(app=None)
    
    # Act
    QTest.mouseClick(page._start_btn, Qt.LeftButton)
    
    # Assert
    # 验证预期行为
```

### 5.4 测试注意事项

1. **不要修改 sys.stdout**：会导致 pytest 崩溃
2. **使用 mock 模拟外部依赖**：录音、转写、AI 服务
3. **测试隔离**：每个测试独立，不依赖其他测试的状态
4. **使用 tmp_path**：创建临时文件和目录
5. **设置 QT_QPA_PLATFORM=offscreen**：GUI 测试需要无头模式

---

## 六、调试指南

### 6.1 日志查看

```bash
# 查看应用日志
tail -f logs/meetscribe.log

# 查看特定级别日志
grep "ERROR" logs/meetscribe.log
grep "WARNING" logs/meetscribe.log
```

### 6.2 常见问题

#### 问题：应用启动失败

**可能原因**：
1. 依赖未安装：`pip install -r requirements.txt`
2. Python 版本不兼容：需要 3.10+
3. PySide6 安装问题：`pip install --upgrade PySide6`

**解决方法**：
```bash
# 重新安装依赖
pip install -r requirements.txt --force-reinstall

# 检查 Python 版本
python --version
```

#### 问题：录音失败

**可能原因**：
1. 麦克风权限未授予
2. PyAudioWPatch 未正确安装
3. VB-Audio Cable 未安装（双轨模式）

**解决方法**：
```bash
# 重新安装 PyAudioWPatch
pip install PyAudioWPatch --force-reinstall

# 检查麦克风权限
# Windows 设置 → 隐私 → 麦克风 → 允许应用访问
```

#### 问题：转写失败

**可能原因**：
1. 模型未下载：首次运行需要下载模型
2. 内存不足：转写需要 4GB+ 内存
3. FFmpeg 未安装：某些音频格式需要 FFmpeg

**解决方法**：
```bash
# 检查模型目录
dir models_cache\models\iic

# 安装 FFmpeg
winget install Gyan.FFmpeg
```

#### 问题：AI 摘要不工作

**可能原因**：
1. API Key 未配置
2. API Key 无效
3. 网络连接问题

**解决方法**：
```bash
# 检查配置文件
type config\settings.json

# 确认 API Key 已填入
# 确认网络连接正常
```

### 6.3 调试技巧

#### 使用 logging

```python
import logging

logger = logging.getLogger("MeetScribe")

# 不同级别
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 记录异常
try:
    # ...
except Exception as e:
    logger.exception("发生错误")
```

#### 使用断点

```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用 Python 3.7+ 语法
breakpoint()
```

#### 使用 Qt 调试

```python
# 打印 Qt 对象信息
print(widget.metaObject().className())
print(widget.geometry())

# 启用 Qt 调试输出
import os
os.environ["QT_DEBUG_PLUGINS"] = "1"
```

---

## 七、协作规范

### 7.1 GitHub 使用

#### Issue 管理

- **Bug 报告**：使用 Bug Report 模板
- **功能请求**：使用 Feature Request 模板
- **任务分配**：在 Issue 中指定负责人

#### Pull Request

- **标题**：简洁描述变更内容
- **描述**：详细说明变更原因和影响
- **关联 Issue**：`Closes #123`
- **审查**：至少一人审查通过

### 7.2 沟通方式

- **日常讨论**：GitHub Issues
- **代码审查**：Pull Request Review
- **紧急问题**：直接联系

### 7.3 文档更新

每次变更后，需要更新相关文档：

| 变更类型 | 需要更新的文档 |
|----------|----------------|
| 新功能 | requirements.md, architecture.md |
| 架构变更 | architecture.md |
| 使用方式变更 | README.md |
| API 变更 | architecture.md |
| Bug 修复 | CHANGELOG.md |

### 7.4 版本发布

```bash
# 1. 确保所有测试通过
pytest

# 2. 更新版本号
# 编辑 src/gui/styles.py 中的 APP_VERSION

# 3. 更新 CHANGELOG
# 编辑 CHANGELOG.md

# 4. 提交变更
git add .
git commit -m "chore: release v1.0.0"

# 5. 打标签
git tag v1.0.0

# 6. 推送到远程
git push origin main --tags
```

---

## 八、常见开发任务

### 8.1 添加新的 GUI 组件

```python
# 1. 创建新文件 gui/new_widget.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

class NewWidget(QWidget):
    """新组件说明"""
    
    # 定义信号
    value_changed = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        label = QLabel("新组件")
        layout.addWidget(label)
    
    def get_value(self):
        """获取值"""
        return 0
    
    def set_value(self, value):
        """设置值"""
        self.value_changed.emit(value)
```

```python
# 2. 在 app.py 中导入并使用

from gui.new_widget import NewWidget

class MeetScribeApp(QMainWindow):
    def __init__(self):
        # ...
        self._new_widget = NewWidget()
        main_layout.addWidget(self._new_widget)
```

### 8.2 添加新的业务逻辑模块

```python
# 1. 创建新文件 src/new_module.py

import logging
from typing import Optional

logger = logging.getLogger("MeetScribe")

class NewModule:
    """新模块说明
    
    职责：...
    
    依赖：...
    """
    
    def __init__(self, config):
        """初始化模块
        
        Args:
            config: 配置对象
        """
        self._config = config
        self._data = {}
    
    def process(self, input_data):
        """处理数据
        
        Args:
            input_data: 输入数据
            
        Returns:
            处理结果
        """
        try:
            # 处理逻辑
            result = input_data
            logger.info(f"处理完成: {result}")
            return result
        except Exception as e:
            logger.exception("处理失败")
            raise
```

### 8.3 添加新的测试

```python
# 1. 创建新文件 tests/test_new_module.py

import pytest
from new_module import NewModule

class TestNewModule:
    """新模块测试"""
    
    def test_process_success(self, tmp_path):
        """测试处理成功"""
        # Arrange
        config = {"key": "value"}
        module = NewModule(config)
        input_data = "test"
        
        # Act
        result = module.process(input_data)
        
        # Assert
        assert result == "test"
    
    def test_process_failure(self):
        """测试处理失败"""
        # Arrange
        module = NewModule({})
        
        # Act & Assert
        with pytest.raises(Exception):
            module.process(None)
```

---

## 九、性能优化

### 9.1 优化原则

1. **测量先行**：优化前先测量性能瓶颈
2. **二八法则**：80% 的性能问题来自 20% 的代码
3. **不要过早优化**：先让代码正确，再让代码快速

### 9.2 常见优化

#### UI 响应

```python
# 使用 QTimer.singleShot 避免阻塞 UI
from PySide6.QtCore import QTimer

def on_button_click():
    # 不要直接执行耗时操作
    # 而是使用 QTimer.singleShot
    QTimer.singleShot(0, self._do_heavy_work)
```

#### 文件列表更新

```python
# 使用增量更新而不是全量重建
def update_file_list(self, changed_files):
    for file_id, new_status in changed_files.items():
        # 只更新变化的行
        row = self._file_rows.get(file_id)
        if row:
            row.update_status(new_status)
```

#### 轮询间隔

```python
# 自适应轮询间隔
def _poll(self):
    if self._has_message:
        self._interval = max(50, self._interval * 0.8)
    else:
        self._interval = min(500, self._interval * 1.2)
    
    self._timer.start(self._interval)
```

### 9.3 性能测量

```python
import time
from contextlib import contextmanager

@contextmanager
def measure_time(label):
    """测量代码执行时间"""
    start = time.time()
    yield
    end = time.time()
    print(f"{label}: {end - start:.3f}s")

# 使用
with measure_time("转写耗时"):
    result = transcriber.transcribe(audio_path)
```

---

## 十、安全注意事项

### 10.1 敏感信息

- **API Key**：不提交到 Git，不硬编码
- **密码**：不存储明文密码
- **录音文件**：本地存储，不自动上传

### 10.2 代码安全

- **不使用 eval/exec**：避免代码注入
- **不执行用户输入**：避免命令注入
- **不暴露内部实现**：使用公共 API

### 10.3 网络安全

- **使用 HTTPS**：API 调用使用 HTTPS
- **验证证书**：不跳过 SSL 证书验证
- **超时设置**：网络请求设置超时

---

## 十一、资源链接

### 11.1 文档

- [需求规格文档](requirements.md)
- [架构设计文档](architecture.md)
- [开发协作指南](development-guide.md)（本文件）
- [文件映射表](FILE_MAPPING.md)

### 11.2 外部资源

- [PySide6 文档](https://doc.qt.io/qtforpython-6/)
- [FunASR 文档](https://github.com/modelscope/FunASR)
- [MiMo API 文档](https://platform.xiaomimimo.com/docs)

### 11.3 工具

- [GitHub Desktop](https://desktop.github.com/)
- [VS Code](https://code.visualstudio.com/)
- [PyCharm](https://www.jetbrains.com/pycharm/)
