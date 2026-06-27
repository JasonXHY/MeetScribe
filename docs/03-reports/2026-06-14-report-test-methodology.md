# 侧耳倾听 v1.0 测试方法论

> 版本：v1.0
> 日期：2026-06-18
> 状态：生效

<!-- [QW-审核 2026-06-18] 整体评价：
分层策略合理，问题诊断准确。但存在三个系统性缺陷：
1. Layer 2/3 仍使用 offscreen 模式，与 §1 自相矛盾——offscreen 无法验证视觉问题（高亮、颜色、布局）
2. 测试场景覆盖率不足——缺少音色库页面、导出功能、右键菜单、错误恢复等场景
3. 缺少"offscreen 无法测试"的显式清单——Agent 必须知道哪些东西它测不了，需要标记为手动验证
-->

---

## 一、问题背景

之前的测试存在重大缺陷：
1. **Offscreen 模式**：`QT_QPA_PLATFORM=offscreen` 不渲染 UI，无法验证显示效果
2. **过度 Mock**：用 MagicMock 代替真实组件，绕过了实际逻辑
3. **只看返回值**：验证"代码没报错"而非"用户看到正确结果"
4. **缺少预期结果**：测试通过不代表功能正确

结果：录音后文件不显示、转写后主题不写入、发言人姓名传播链路断裂——这些用户可感知的严重问题全部漏测。

---

## 二、测试分层策略

### Layer 1: Unit Tests（纯逻辑，无 UI）

**目标**：验证算法和数据处理的正确性

**工具**：pytest（无 PySide6）

**范围**：
- `config.py` — 配置读写、空值过滤、向后兼容
- `utils.py` — apply_speaker_mapping、get_summary_path
- `speaker_namer.py` — 正则提取、姓名模式匹配
- `voiceprint.py` — 匹配评分、置信度判断
- `model_registry.py` — 厂商映射、URL 解析
- `formatters.py` — 各格式输出（MD/TXT/SRT/JSON/HTML/CSV/VTT）
- `file_manager.py` — 文件增删改查、状态流转

**验收标准**：
- 每个函数有明确输入/输出断言
- 边界情况覆盖（空值、None、越界、格式错误）
- 不依赖任何外部服务或文件系统状态

### Layer 2: Integration Tests（PySide6 offscreen）

**目标**：验证组件间信号槽连接和数据流

**工具**：pytest + pytest-qt（`QT_QPA_PLATFORM=offscreen`）

<!-- [QW-审核] offscreen 模式的关键限制（Agent 必须知道）：
- signal.receivers() 对 lambda 连接和 functools.partial 返回 0，不可靠
- widget.geometry() / widget.size() 返回 (0,0,0,0)，无法验证布局
- QSS 样式不生效（background、color、border 全无效），无法验证视觉问题
- enterEvent/leaveEvent 无法触发（鼠标事件在 offscreen 下不工作）
- 建议：验证信号连接改用 signal.connect() 后检查 slot 是否被调用，而非 receivers()
-->

**范围**：
- App 启动 → 页面切换 → 组件存在
- 信号触发 → 槽方法执行 → 状态变更
- 配置保存 → 重新加载 → 值一致
- 文件添加 → 列表更新 → 状态显示

**验收标准**：
- 检查 widget 的实际属性（`text()`, `isEnabled()`, `isVisible()`）
- 验证信号连接（`signal.receivers() > 0`）
- 验证数据模型变更（`file_manager.files` 长度、状态值）

### Layer 3: GUI 操作 Tests（前端交互验证）

**目标**：验证用户操作序列的正确性

**工具**：pytest-qt + QTest（`QT_QPA_PLATFORM=offscreen`）

<!-- [QW-审核] Layer 3 是最关键的一层，但当前场景严重不足。补充以下必测场景：

#### 3.5 音色库页面（Bug A 就出在这里）
| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 切换到音色库页 | 列表显示所有已保存说话人 | 检查 QListWidget.count() |
| 2 | 点击说话人 | 右侧详情面板更新，**选中项有高亮** | 检查 SpeakerItemWidget._selected |
| 3 | 鼠标悬停 | **悬停项有视觉反馈** | 检查 enterEvent/leaveEvent 是否触发 |
| 4 | 查看详情面板 | 样本数、创建时间、质量评分正确显示 | 检查 QLabel.text() |
| 5 | 编辑说话人姓名 | 双击进入编辑，保存后列表和 JSON 同步更新 | 检查 voiceprint_library.json |
| 6 | 删除说话人 | 确认弹窗，删除后列表和 JSON 同步更新 | 检查 QListWidget.count() |

#### 3.6 导出功能（Bug F：导出缺少 AI 摘要）
| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 选择已完成文件 → 导出 | ExportDialog 正确打开 | 检查 ExportDialog 是否实例化 |
| 2 | 选择格式 → 导出 | 导出文件包含**转写内容 + AI 摘要** | 检查导出文件内容 |
| 3 | 选择不同格式 | 每种格式内容完整 | 检查 MD/TXT/HTML 内容 |

#### 3.7 文件列表右键菜单
| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 右键点击文件 | 显示上下文菜单 | 检查 QMenu.isVisible() |
| 2 | 选择"打开文件夹" | **打开结果文件所在目录**（非系统文档目录）| 检查 QDesktopServices 调用参数 |
| 3 | 选择"删除" | 确认弹窗，删除后列表更新 | 检查 rowCount() |
| 4 | 选择"重新转写" | 状态重置为 pending，按钮更新 | 检查状态列和按钮 |

#### 3.8 页面导航
| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 点击"主页"标签 | 主页显示 | 检查 stacked widget currentIndex |
| 2 | 点击"音色库"标签 | 音色库页显示，列表刷新 | 检查 QListWidget.count() |
| 3 | 点击"设置"标签 | 设置页显示，配置值加载 | 检查各 widget 值 |

#### 3.9 错误恢复
| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 转写失败（模型缺失） | 状态恢复，错误日志显示 | 检查状态列和日志 |
| 2 | 网络断开时调用 AI | 错误提示，不崩溃 | 检查 QMessageBox |
| 3 | 文件被删除后操作 | 优雅处理，不崩溃 | 检查异常处理 |
-->

**范围**：
- 按钮点击 → 信号触发 → 槽方法执行 → widget 状态更新
- ComboBox 选择 → 值变更 → 持久化到 config
- 文件列表右键菜单 → 操作执行 → 列表刷新
- 录音开始/暂停/停止 → 状态栏更新 → 文件出现
- 转写启动 → 进度更新 → 完成后状态/主题/发言人更新

**验收标准**：
- 使用 `QTest.mouseClick()` / `QTest.keyClick()` 模拟真实点击
- 操作后检查 widget 状态（而非 mock 返回值）
- 验证文件列表 `QTableWidget.item(row, col).text()` 的实际内容
- 验证配置文件的实际写入内容

### Layer 4: E2E Tests（真实环境）

**目标**：验证完整用户场景

**工具**：pytest-qt + 真实模型 + 真实音频

**范围**：
- 真实音频转写 → 结果文件生成 → 内容验证
- AI 摘要生成 → 主题提取 → 文件列表显示
- 声纹匹配 → 姓名注入 → 转写文件更新
- 录音 → 保存 → 文件列表显示 → 转写 → 结果验证

**验收标准**：
- 使用真实音频文件（`tests/fixtures/` 或用户指定文件）
- 验证文件系统实际产出（文件存在、内容非空、格式正确）
- 验证 UI 实际显示（文件列表行数、主题列内容、状态列内容）

---

## 三、核心测试场景（必测）

### 3.1 录音流程

| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 点击"开始录音" | 状态栏显示"录音已开始"，计时器启动 | 检查 recording_bar 状态 |
| 2 | 点击"暂停" | 状态栏显示"录音已暂停"，计时器暂停 | 检查 recording_bar 状态 |
| 3 | 点击"继续" | 状态栏显示"录音已继续"，计时器恢复 | 检查 recording_bar 状态 |
| 4 | 点击"停止" | 文件保存，弹窗询问是否转写 | 检查文件系统 + 弹窗 |
| 5 | 关闭弹窗 | **文件列表显示新录音文件** | 检查 QTableWidget 行数 |

### 3.2 转写流程

| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 选择文件 → 点击"转写" | 状态变为"processing" | 检查文件列表状态列 |
| 2 | 转写进行中 | 进度条更新 | 检查 progress_updated 信号 |
| 3 | 转写完成 | 状态变为"done"，**主题列显示会议主题** | 检查 QTableWidget 主题列 |
| 4 | AI 摘要生成 | **主题写入文件列表** | 检查 file_manager.item.topic |
| 5 | 查看转写结果 | 文件内容包含发言人姓名（非 Speaker N） | 检查结果文件内容 |

### 3.3 发言人管理

| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 点击"发言人管理" | 弹窗显示所有说话人 | 检查 SpeakerDialog 内容 |
| 2 | 查看匹配建议 | 显示"可能是 XXX (XX%)" | 检查 suggestion_label 文本 |
| 3 | 点击"接受" | 姓名填入输入框 | 检查 name_entry 内容 |
| 4 | 点击"保存" | **转写文件中 Speaker N 替换为姓名** | 检查结果文件内容 |
| 5 | 再次打开弹窗 | 显示已保存的姓名 | 检查 parse_speakers_from_result |

### 3.4 设置页

| 步骤 | 操作 | 预期结果 | 验证方式 |
|------|------|---------|---------|
| 1 | 切换到设置页 | 显示当前配置 | 检查 widget 值 |
| 2 | 修改厂商 | 模型列表更新 | 检查 model_combo 选项 |
| 3 | 填入 API Key | 显示"已配置自定义 Key" | 检查状态提示文字 |
| 4 | 关闭 Ollama | **转写时不调用 Ollama** | 检查日志无 Ollama 调用 |
| 5 | 保存设置 | config.json 写入正确 | 检查文件内容 |

---

## 四、测试文件规范

### 4.1 命名规范

```
tests/
├── test_unit_<module>.py       # Layer 1: 单元测试
├── test_integration_<flow>.py  # Layer 2: 集成测试
├── test_gui_<feature>.py       # Layer 3: GUI 操作测试
├── test_e2e_<scenario>.py      # Layer 4: 端到端测试
└── conftest.py                 # 共享 fixtures
```

### 4.2 测试用例规范

每个测试用例必须包含：
1. **清晰的测试目标**（docstring 第一行）
2. **明确的预期结果**（assert 断言具体值）
3. **实际的验证方式**（检查 widget 属性、文件内容、配置值）

**反模式（禁止）**：
```python
# ❌ 只检查不报错
def test_something():
    app.do_something()
    assert True  # 无意义

# ❌ Mock 绕过实际逻辑
def test_something():
    with patch('module.function', return_value=mock_value):
        result = app.do_something()
        assert result == mock_value  # 只验证了 mock
```

**正确模式**：
```python
# ✅ 验证实际 widget 状态
def test_file_appears_after_recording(qtbot):
    app = MeetScribeApp()
    qtbot.addWidget(app)
    
    # 模拟录音保存
    app._handle_stop_complete([test_file])
    QTest.qWait(500)
    
    # 验证文件列表实际显示
    table = app._home_page._file_list_view._table
    assert table.rowCount() >= 1
    assert table.item(0, 1).text() == "test_file.wav"  # 文件名列
    
    app.close()

# ✅ 验证配置文件实际写入
def test_config_saves_correctly(tmp_path):
    config_path = tmp_path / "settings.json"
    config = Config(str(config_path))
    config.set("ai_vendor", "小米 MiMo")
    
    # 重新加载验证
    config2 = Config(str(config_path))
    assert config2.get("ai_vendor") == "小米 MiMo"
    
    # 验证文件实际内容
    with open(config_path) as f:
        data = json.load(f)
    assert data["ai_vendor"] == "小米 MiMo"
```

### 4.3 Fixtures 规范

```python
# conftest.py
@pytest.fixture
def app_with_recorded_file(qtbot, synthetic_wav):
    """创建已录音的 App 实例（用于测试文件列表显示）"""
    from gui.app import MeetScribeApp
    test_app = MeetScribeApp()
    qtbot.addWidget(test_app)
    
    test_file = synthetic_wav("test_record.wav", seconds=1.0)
    test_app._handle_stop_complete([test_file])
    QTest.qWait(500)
    
    yield test_app
    test_app.close()

@pytest.fixture
def app_with_transcribed_file(qtbot, synthetic_wav):
    """创建已转写文件的 App 实例（用于测试主题/发言人显示）"""
    # ... 类似逻辑
```

---

## 五、Offscreen 模式无法验证的清单（必须手动）

<!-- [QW-审核] 这是整个文档最重要的补充。
Agent 在 offscreen 下跑完所有自动化测试后，必须明确告知用户：以下项目我无法验证，请你手动检查。
-->

| 类别 | 具体项目 | 原因 |
|------|---------|------|
| **视觉样式** | QSS background/color/border 是否正确 | offscreen 不渲染样式 |
| **悬停效果** | enterEvent/leaveEvent 触发的高亮变化 | offscreen 无鼠标事件 |
| **选中高亮** | QListWidget::item:selected 的视觉效果 | offscreen 不渲染选中态 |
| **布局正确性** | widget 位置、大小、重叠、对齐 | offscreen geometry 全为 0 |
| **文本渲染** | 文字是否截断、换行是否正确、字体是否正确 | offscreen 不渲染文本 |
| **动画/过渡** | 进度条动画、状态切换过渡 | offscreen 无定时器驱动 |
| **窗口交互** | 窗口圆角（Win11 DWM）、窗口图标、任务栏显示 | offscreen 无窗口管理器 |
| **真实音频** | 录音音质、转写准确率、声纹匹配准确率 | 需要真实音频设备+模型 |

**Agent 工作流要求**：每次完成自动化测试后，输出报告必须包含两部分：
1. 自动化测试结果（通过/失败）
2. **手动验证提醒**：列出本次修改涉及的、offscreen 无法验证的项目

---

## 六、异步操作测试规范

<!-- [QW-审核] 原文档对异步测试着墨太少。这个项目的核心链路（转写、摘要、声纹匹配）全是异步的。
-->

### 6.1 短异步（< 1 秒）

使用 `QTest.qWait()` 或 `qtbot.waitSignal()`：

```python
# 录音保存后等待文件列表刷新
app._handle_stop_complete([test_file])
QTest.qWait(500)
assert table.rowCount() >= 1

# 等待信号触发
with qtbot.waitSignal(app.file_manager.file_status_changed, timeout=3000):
    app._start_transcription(file_path)
```

### 6.2 长异步（转写/摘要，可能数分钟）

**禁止** 在测试中真正等待模型推理。使用 mock + 模拟消息：

```python
# 模拟转写完成消息（不真正跑模型）
handler = TranscriptionHandler(...)
handler._process_message(("done", None))
QTest.qWait(200)

# 模拟摘要生成完成
handler._process_message(("auto_summary", {"summary": "...", "topic": "测试主题"}))
QTest.qWait(500)

# 验证 UI 更新
assert file_manager.get_topic(file_path) == "测试主题"
```

### 6.3 QTimer.singleShot 测试

多个 bug 涉及 `QTimer.singleShot(0, callback)` 的时序问题：

```python
# 处理所有 pending 的 singleShot
from PySide6.QtWidgets import QApplication
QApplication.processEvents()  # 处理事件队列
QTest.qWait(100)              # 等待 singleShot 执行
```

---

## 七、手动验证清单（每次发版必做）

### 5.1 录音流程
- [ ] 启动应用，点击"开始录音"
- [ ] 录音 30 秒，点击"停止"
- [ ] **验证：文件列表显示新录音文件**
- [ ] 验证：弹窗询问是否转写
- [ ] 点击"否"，验证文件仍在列表中

### 5.2 转写流程
- [ ] 选择录音文件，点击"转写"
- [ ] 验证：状态变为"转写中"
- [ ] 验证：转写完成后状态变为"完成"
- [ ] **验证：主题列显示会议主题**
- [ ] 验证：点击"预览"可查看转写结果

### 5.3 发言人管理
- [ ] 点击"发言人管理"按钮
- [ ] 验证：弹窗显示所有说话人
- [ ] 验证：显示声纹匹配建议
- [ ] 手动输入姓名，点击"保存"
- [ ] **验证：转写文件中 Speaker N 替换为姓名**
- [ ] 再次打开弹窗，验证姓名已保存

### 5.4 设置页
- [ ] 切换到设置页
- [ ] 修改 AI 厂商，验证模型列表更新
- [ ] 填入 API Key，验证状态提示
- [ ] **验证：关闭 Ollama 后转写不调用 Ollama**
- [ ] 保存设置，重启应用，验证配置持久化

### 7.5 AI 摘要
- [ ] 转写完成后，验证 AI 摘要生成
- [ ] **验证：主题写入文件列表主题列**
- [ ] 验证：摘要文件包含参会人员信息
- [ ] 验证：参会人员姓名与转写文件一致

### 7.6 音色库页面
- [ ] 切换到音色库页，验证列表显示已保存的说话人
- [ ] 点击说话人，验证**右侧详情面板更新、选中项有高亮**
- [ ] 鼠标悬停，验证**悬停项有视觉反馈**（这是 Bug A 的核心）
- [ ] 验证质量评分显示正确（非全 1.00）
- [ ] 编辑说话人姓名，验证列表和 JSON 同步更新

### 7.7 导出功能
- [ ] 选择已完成文件，点击导出
- [ ] 选择 MD 格式，验证**导出内容包含 AI 摘要**（Bug F）
- [ ] 选择其他格式，验证内容完整

### 7.8 文件操作
- [ ] 右键文件 → "打开文件夹"，验证**打开的是结果文件目录**（Bug I）
- [ ] 右键文件 → "删除"，验证确认弹窗和列表更新
- [ ] 右键文件 → "重新转写"，验证状态重置和按钮更新（Bug G）

---

## 八、自动化测试运行

### 6.1 快速验证（每次修改后）

```bash
# Layer 1 + 2: 纯逻辑 + 集成测试（~30秒）
python -m pytest tests/ -m "unit or integration" -q --timeout=15
```

### 6.2 完整验证（每次发版前）

```bash
# Layer 1 + 2 + 3: 含 GUI 操作测试（~2分钟）
python -m pytest tests/ -m "unit or integration or gui" -q --timeout=30

# Layer 4: E2E 测试（需模型，~10分钟）
python -m pytest tests/ -m "e2e_heavy" -q --timeout=600
```

### 6.3 手动验证（每次发版必做）

按第五节清单逐项验证，记录结果。

---

## 九、测试责任

| 层级 | 谁做 | 频率 |
|------|------|------|
| Layer 1 Unit | 自动化 | 每次 commit |
| Layer 2 Integration | 自动化 | 每次 commit |
| Layer 3 GUI 操作 | 自动化 + 手动 | 每次发版 |
| Layer 4 E2E | 手动 | 每次发版 |
| 手动验证清单 | 手动 | 每次发版 |
