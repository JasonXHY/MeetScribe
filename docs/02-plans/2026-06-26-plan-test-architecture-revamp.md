# 测试架构重构方案

> 日期：2026-06-26
> 审查人：Qoder
> 状态：待用户确认后交 mimo 执行

---

## 一、现状问题

当前测试套件的核心矛盾是：**数量多、覆盖差、干扰大**。

| 指标 | 当前值 | 问题 |
|------|--------|------|
| 测试文件 | 42 个 | 大量重复，同一功能在多个文件中被测试 |
| 测试函数 | 461 个 | 约 130 个是纯存在性检查，毫无价值 |
| 有效功能测试 | ~130 个 | 分散在 42 个文件中，维护成本极高 |
| 360 弹窗触发 | test_tdd_flows.py 等 | 真实子进程、网络请求触发杀毒拦截 |
| 前端覆盖 | 0 | 全部后台跑脚本，GUI 业务逻辑从未被真正验证 |
| 真实音频基准 | 有但没用上 | fixtures/ 有 16min 和 34min 音频，但只在高风险测试中用到 |

### 360 弹窗的根因

排查了所有 42 个测试文件，触发 360 的源头只有一个：**test_tdd_flows.py 中的 TestTranscriptionWithRealAudio 和 TestAISummary**。这两个测试类会启动真实的子进程（multiprocessing.Process）跑 ML 推理，以及发起真实 HTTP 请求调用 AI API。其他测试文件要么已经 mock 掉了危险操作，要么通过 conftest.py 的自动跳过机制规避了。

所以解决 360 弹窗不需要大改，只需要把这两个测试类标记为手动运行，日常 pytest 不触发。

---

## 二、重构目标

| 指标 | 当前 | 目标 |
|------|------|------|
| 测试文件数 | 42 | **15** |
| 测试函数总数 | 461 | **~150**（全部有实际意义） |
| 存在性检查 | ~130 | **0** |
| 360 弹窗 | 每次跑测试都弹 | **日常运行零弹窗** |
| 前端场景覆盖 | 0% | **核心用户流程全覆盖** |
| 真实音频基准 | 未利用 | **1 条短音频 + 输出快照对比** |

---

## 三、新测试架构

### 3.1 文件结构（15 个测试文件）

按领域合并，每个文件负责一个明确的模块：

```
tests/
  conftest.py                      # 保留，增强 fixture
  fixtures/
    test_audio_short.wav         # 新增：30秒短音频（手动录制或裁剪）
    golden_transcript.json       # 新增：短音频的标准转写输出
    golden_summary.md            # 新增：标准 AI 摘要输出

  test_core.py                     # 核心工具函数（合并 utils + config + paths）
  test_file_manager.py             # 文件管理（保留）
  test_formatters.py               # 输出格式化（保留）
  test_voiceprint.py               # 声纹匹配全量（合并 voiceprint 5 文件）
  test_transcription.py            # 转写核心逻辑（保留 + 增强）
  test_transcription_queue.py      # 转写队列（保留）
  test_async_workers.py            # 异步处理（合并 async 3 文件）
  test_postprocess.py              # 后处理（保留 + 增强）
  test_speaker_namer.py            # 发言人命名（保留）
  test_ai_service.py               # AI 服务（保留）
  test_gui_config.py               # 配置页 GUI（合并 settings 3 文件）
  test_gui_home.py                 # 首页 GUI（合并 home 4 文件）
  test_gui_dialogs.py              # 对话框 GUI（合并 dialogs 4 文件）
  test_gui_recorder.py             # 录音模块（保留，全 mock）
  test_e2e_scenario.py             # 端到端场景测试（新建，核心）
```

### 3.2 合并映射表

| 新文件 | 合并来源 | 保留测试数 | 删除测试数 |
|--------|---------|-----------|-----------|
| test_core.py | test_utils, test_config, test_config_edge, test_file_write_paths, test_frozen_paths, test_infra, test_optimization | ~25 | ~15 |
| test_voiceprint.py | test_voiceprint, test_voiceprint_boundary, test_voiceprint_gui_flow | ~35 | ~5 |
| test_async_workers.py | test_async_integration, test_async_postprocess, test_bugfix_v10（异步部分） | ~15 | ~15 |
| test_postprocess.py | test_postprocess, test_bugfix_v10（后处理部分） | ~15 | ~5 |
| test_gui_config.py | test_settings_engine, test_settings_dialogs_g16, test_first_launch, test_model_registry | ~35 | ~20 |
| test_gui_home.py | test_home_page_p0, test_gui_special, test_button_states, test_stop_button, test_progress_display, test_frontend_fixes, test_file_list | ~30 | ~30 |
| test_gui_dialogs.py | test_dialogs_p0, test_add_voice_dialog, test_embedding_save, test_markdown_render, test_g12_spec_deviations | ~25 | ~20 |
| test_e2e_scenario.py | test_tdd_flows（功能部分）, test_dual_track_merge（功能部分） | ~15 | — |

### 3.3 移出 tests/ 的文件

以下文件不是 pytest 测试，移到 scripts/ 或直接删除：

| 文件 | 原因 | 处理 |
|------|------|------|
| test_voiceprint_threshold.py | 独立诊断脚本，无 test_ 函数 | scripts/diagnose_voiceprint_threshold.py |
| test_voiceprint_extraction.py | 独立诊断脚本，引用硬编码路径 | scripts/diagnose_voiceprint_extraction.py |
| test_voiceprint_fix.py | 独立修复脚本，核心测试已跳过 | scripts/diagnose_voiceprint_fix.py |
| _verify_state.py | 独立验证脚本 | scripts/verify_state.py |

---

## 四、360 弹窗解决方案

### 4.1 日常运行零弹窗

在 conftest.py 中增加全局策略：默认跳过所有可能触发 360 的测试。

```python
# conftest.py 增加
def pytest_collection_modifyitems(config, items):
    skip_heavy = pytest.mark.skip(reason="手动运行: pytest -m e2e_heavy")
    skip_network = pytest.mark.skip(reason="手动运行: pytest -m e2e_network")

    for item in items:
        if "e2e_heavy" in item.keywords and not config.getoption("--run-heavy", default=False):
            item.add_marker(skip_heavy)
        if "e2e_network" in item.keywords and not config.getoption("--run-network", default=False):
            item.add_marker(skip_network)
```

### 4.2 运行命令

```bash
# 日常开发：零弹窗，30 秒内跑完
pytest tests/ -v

# 手动跑完整测试（会触发 360，主动选择时机）
pytest tests/ -v --run-heavy --run-network -m "e2e_heavy or e2e_network"
```

### 4.3 触发源隔离

| 触发源 | 所在文件 | 隔离方式 |
|--------|---------|---------|
| multiprocessing.Process（真实子进程） | test_tdd_flows.py | @pytest.mark.e2e_heavy |
| HTTP API 调用 | test_tdd_flows.py | @pytest.mark.e2e_network |
| funasr 模型加载 | test_voiceprint_extraction.py 等 | 移出 tests/ |
| PyAudio 设备访问 | test_recorder.py | 已有 _FakePyAudio mock |

---

## 五、前端场景测试方案

### 5.1 当前问题

现有 GUI 测试的写法是：

```python
# 当前写法：检查控件是否存在，不验证用户行为
def test_transcribe_button_exists(self):
    assert hasattr(self.page, '_transcribe_btn')  # 永远通过
```

这不能发现任何前端 bug。按钮可能不存在、点击后可能崩溃、状态可能不更新，但测试全部通过。

### 5.2 改进写法：模拟用户操作

```python
def test_user_adds_file_and_clicks_transcribe(self, qtbot, tmp_path):
    """用户添加文件 - 点击转写 - 文件状态变为处理中"""
    app = MeetScribeApp()
    qtbot.addWidget(app)
    page = app._home_page

    # 添加文件
    test_file = tmp_path / "test.wav"
    create_synthetic_wav(test_file, duration_s=5)
    page._add_files([str(test_file)])

    # 验证：文件列表显示 1 个文件
    assert len(page._file_list_view.files) == 1

    # 操作：点击转写按钮（模拟，不真实启动子进程）
    with patch.object(page._transcription_handler, 'start') as mock_start:
        page._transcribe_selected()
        mock_start.assert_called_once()

    # 验证：文件状态变为 PROCESSING
    assert page._file_list_view.files[0].status == FileStatus.PROCESSING
```

### 5.3 核心场景测试清单（test_e2e_scenario.py）

这是最有价值的新文件，覆盖用户实际操作流程：

| 场景 | 测试内容 | 验证点 |
|------|---------|--------|
| 启动应用 | MeetScribeApp 初始化 | 窗口标题、尺寸、三个页面可切换 |
| 添加音频文件 | 拖拽或按钮添加 .wav 文件 | 文件列表出现、时长显示正确 |
| 点击转写 | 按钮点击 - handler.start() | 按钮变禁用、状态变为 PROCESSING |
| 转写完成回调 | 模拟 _on_transcription_done | 状态变 DONE、结果文件生成、按钮恢复 |
| 转写失败回调 | 模拟 _on_transcription_done(error) | 状态变 FAILED、错误消息显示、按钮恢复 |
| AI 摘要开关 | 设置页切换 AI 摘要选项 | 配置值正确保存和恢复 |
| 声纹库添加 | 添加说话人 - 匹配 | 声纹库更新、转写结果中名称替换 |
| 双轨合并 | 添加两个文件 - 合并转写 | 合并行出现、源文件列表正确 |
| 导出文件 | 选择格式导出 | 文件生成、内容格式正确 |
| 删除文件 | 删除已转写文件 | 列表更新、源文件可选保留/删除 |

### 5.4 视觉快照测试方案

**结论：mimo 可以实现，技术难度不高。**

调研了当前 PySide6/PyQt 生态的视觉测试方案，以下是成熟可行的技术路线：

**核心技术栈：**

| 组件 | 工具 | 作用 |
|------|------|------|
| 截图 | `QWidget.grab()` | PySide6 内置，返回 QPixmap，可直接保存为 PNG |
| 图像对比 | `scikit-image` SSIM | 结构相似性指数，容忍字体渲染和 DPI 差异 |
| pytest 集成 | `pytest-image-snapshot` | 自动管理基准图、生成差异图、阈值控制 |
| GUI 测试框架 | `pytest-qt` (qtbot) | 模拟用户操作 + offscreen 渲染 |

**实现步骤（mimo 可执行）：**

```python
from skimage.metrics import structural_similarity as ssim
from PIL import Image
import numpy as np

def compare_screenshot(current_path, baseline_path, threshold=0.95):
    """SSIM 对比，返回相似度 0~1"""
    img1 = np.array(Image.open(current_path).convert('RGB'))
    img2 = np.array(Image.open(baseline_path).convert('RGB'))
    # 尺寸不一致时 resize
    if img1.shape != img2.shape:
        return 0.0
    score, _ = ssim(img1, img2, full=True)
    return score

def test_home_page_visual(qtbot):
    """首页视觉回归测试"""
    app = MeetScribeApp()
    qtbot.addWidget(app)
    app.show()
    qtbot.wait(500)  # 等待渲染

    # 截图
    pixmap = app._home_page.grab()
    current = "tests/fixtures/snapshots/current_home.png"
    pixmap.save(current)

    # 对比
    baseline = "tests/fixtures/snapshots/golden_home.png"
    score = compare_screenshot(current, baseline)
    assert score > 0.95, f"视觉相似度 {score:.2%} < 95%"
```

**注意事项：**
- 首次运行需要生成基准图（golden snapshot），后续运行对比
- `QT_QPA_PLATFORM=offscreen` 模式下截图是确定性的（不受系统主题影响）
- DPI 缩放可能导致尺寸差异，建议固定 `QT_SCALE_FACTOR=1.0`
- 基准图更新命令：`pytest --update-snapshots`

**参考方案：**
- [pytest-image-snapshot](https://pypi.org/project/pytest-image-snapshot/)：pytest 插件，自动管理基准图和差异图
- [scikit-image SSIM](https://scikit-image.org/docs/0.25.x/api/skimage.metrics.html)：Python 生态最成熟的图像相似度算法
- Qt 官方示例：[PySide6 + scikit-image 集成](https://doc.qt.io/qtforpython-6/examples/example_external_scikit.html)

**建议执行顺序：** 先完成核心场景测试（test_e2e_scenario.py），稳定后再引入视觉快照。视觉快照不增加新功能覆盖，只是防止 UI 回归。

---

## 六、真实音频基准方案

### 6.1 基准音频

| 文件 | 时长 | 用途 | 来源 |
|------|------|------|------|
| test_audio_multispk.wav | 14.3 秒 | 快速冒烟测试 | 已创建：CAM++ 模型示例音频拼接（2 个说话人） |
| test_meeting_16min.wav | 16 分钟 | 完整转写基准 | 已有，保留 |
| test_meeting_34min.wav | 34 分钟 | 长音频压力测试 | 已有，保留 |

**test_audio_multispk.wav 详情：**
- 来源：CAM++ 声纹识别模型自带的中文示例音频（Apache 2.0 许可证）
- 组成：speaker1_a_cn_16k.wav (3.7s) + speaker1_b_cn_16k.wav (4.9s) + speaker2_a_cn_16k.wav (5.3s)，段间插入 200ms 静音
- 格式：16kHz 单声道 WAV，448 KB
- 路径：`tests/fixtures/test_audio_multispk.wav`（已生成）
- 优势：无需额外下载，使用模型自身示例数据，转写结果可预测

后续如需更长音频，可考虑从以下开源数据集中选取：
- [AISHELL-4](https://www.openslr.org/111/)：真实多人会议录音，CC BY-SA 4.0（数据集 51GB，仅下载 test 子集）
- [RealTalk-CN](https://modelscope.cn/datasets/BAAI/RealTalk-CN)：113 人真实对话，16kHz WAV，CC BY-NC-SA 4.0

### 6.2 输出快照（Golden File）

对短音频预生成标准输出：

```
tests/fixtures/
  test_audio_multispk.wav             # 基准音频（已生成）
  golden_multispk_transcript.json      # 标准转写结果（含说话人标记）
  golden_multispk_sentences.json       # 标准分句结果
  golden_multispk_summary.md           # 标准 AI 摘要
```

测试时对比实际输出与 golden file，差异超过阈值即失败。这比只检查"有没有输出"有意义得多。

### 6.3 对比逻辑

```python
def test_short_audio_transcription_output(self):
    """30秒音频转写结果与基准一致"""
    result = run_mock_transcription("fixtures/test_audio_short.wav")
    golden = json.load(open("fixtures/golden_short_transcript.json"))

    # 允许 5% 的文字差异（ASR 有随机性）
    similarity = text_similarity(result["text"], golden["text"])
    assert similarity > 0.95, f"转写相似度 {similarity:.2%} < 95%"

    # 说话人数量必须一致
    assert len(result["speakers"]) == len(golden["speakers"])
```

---

## 七、选择性测试运行 + 高风险自动触发方案

### 7.1 核心问题

461 个测试不可能每次都全跑，高风险测试（真实子进程、网络请求）又不想永远不跑。需要一个**智能调度策略**：日常只跑相关的，高风险在合适时机自动跑。

### 7.2 日常开发：只跑改过的

使用 [pytest-run-changed](https://pypi.org/project/pytest-run-changed/) 插件，基于 git diff 自动识别哪些源文件被修改了，只运行关联的测试：

```bash
# 日常开发（最常用）：只跑受影响的测试，秒级完成
pytest --changed

# 示例：改了 voiceprint.py → 只跑 test_voiceprint.py 相关测试
# 示例：改了 gui/home_page.py → 只跑 test_gui_home.py 相关测试
```

原理：首次运行建立「源文件 → 测试文件」映射关系，后续根据 `git status` 的修改文件自动筛选。

### 7.3 三层测试策略

| 层级 | 命令 | 耗时 | 触发时机 | 覆盖范围 |
|------|------|------|---------|---------|
| 快速冒烟 | `pytest --changed` | < 10 秒 | 每次改代码后 | 只跑受影响的 |
| 全量回归 | `pytest tests/ -v` | < 30 秒 | 合并/发版前 | 所有安全测试 |
| 高风险 E2E | `pytest -m "e2e_heavy or e2e_network" --run-heavy --run-network` | 2-5 分钟 | 见下方自动触发 | 真实子进程 + API |

### 7.4 高风险测试自动触发策略

高风险测试不应该永远不跑。设计三种自动触发场景：

**触发场景 1：打包前自动跑（推荐）**

在 `me.spec` 的打包脚本前加一个钩子，打包前自动跑一遍高风险测试。如果失败则中止打包：

```python
# scripts/pre_build_check.py
import subprocess, sys

def run_high_risk_tests():
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "-m", "e2e_heavy",
        "--run-heavy",
        "-x",  # 失败即停
        "-q"   # 简洁输出
    ], cwd=r"C:\侧耳倾听")

    if result.returncode != 0:
        print("高风险测试未通过，中止打包")
        sys.exit(1)
    print("高风险测试通过，继续打包")

if __name__ == "__main__":
    run_high_risk_tests()
```

**触发场景 2：核心文件变更时自动跑**

在 conftest.py 中加入逻辑：如果检测到关键文件（transcriber.py、transcription.py、voiceprint.py、ai_service.py）有未提交的修改，自动包含高风险测试：

```python
# conftest.py 增加
import subprocess

def pytest_collection_modifyitems(config, items):
    # 检查关键文件是否有未提交修改
    critical_files = [
        'src/transcriber.py', 'src/gui/transcription.py',
        'src/voiceprint.py', 'src/ai_service.py'
    ]

    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True, text=True, cwd=r'C:\侧耳倾听'
        )
        changed = set(result.stdout.strip().split('\n'))
        critical_changed = changed & set(critical_files)
    except Exception:
        critical_changed = set()

    for item in items:
        if "e2e_heavy" in item.keywords:
            if critical_changed:
                pass  # 关键文件改了，自动跑高风险测试
            elif not config.getoption("--run-heavy", default=False):
                item.add_marker(pytest.mark.skip(
                    reason="自动跳过（无 --run-heavy 且核心文件未修改）"))
        if "e2e_network" in item.keywords and not config.getoption("--run-network", default=False):
            item.add_marker(pytest.mark.skip(reason="手动运行: pytest --run-network"))
```

**触发场景 3：每周一早上自动跑（兜底）**

通过 QoderWork 定时任务，每周一早上 9 点自动运行全量测试（含高风险），结果输出到日志文件：

```
定时任务配置：
- cron: 0 9 * * 1（每周一 09:00）
- 命令: pytest tests/ -v --run-heavy --run-network > tests/weekly_report.txt 2>&1
- 失败通知: 如果 returncode != 0，提醒用户检查
```

### 7.5 总结：你日常只需要记住一个命令

```bash
# 改了代码就跑这个
pytest --changed
```

其他场景（打包前、核心文件修改、每周定时）都会自动处理，不需要手动操心。

---

## 八、执行计划

### 第一步：止血（立即，10 分钟）

1. 安装 pytest-run-changed：`pip install pytest-run-changed`
2. 在 conftest.py 中添加 e2e_heavy/e2e_network 自动跳过 + 核心文件变更自动触发逻辑
3. 验证 `pytest tests/ -v` 不再触发 360
4. 验证 `pytest --changed` 能正常运行

### 第二步：移出非测试文件（30 分钟）

1. 将 4 个独立脚本移到 scripts/
2. 验证 pytest 收集数量减少

### 第三步：清理存在性检查（2 小时）

按 v3 方案的修正后执行清单操作：
- 删除 3 个纯垃圾文件
- 从 8 个文件中删除 ~34 个存在性检查测试
- 验证所有保留的测试仍然通过

### 第四步：合并文件（4 小时）

按合并映射表逐个操作。每个合并完成后跑 pytest 验证。

### 第五步：新建场景测试（4 小时）

1. 基准音频已就绪：`tests/fixtures/test_audio_multispk.wav`（14.3 秒，双说话人）
2. 编写 test_e2e_scenario.py（10 个场景）
3. 生成 golden file（首次跑一遍真实转写，保存标准输出）
4. 验证所有场景测试通过

### 第六步：验证

```bash
# 日常：只跑改过的（秒级，零弹窗）
pytest --changed

# 发版前：全量安全测试（30 秒内，零弹窗）
pytest tests/ -v

# 打包前：含高风险（2-5 分钟，可能触发 360）
pytest tests/ -v --run-heavy --run-network
```

---

## 九、给用户的决策项

1. **基准音频** — 已解决。使用 CAM++ 模型示例拼接的 14.3 秒双说话人音频（`test_audio_multispk.wav`），已生成在 `tests/fixtures/` 下。后续如需更长音频可从 AISHELL-4 或 RealTalk-CN 开源数据集中选取。

2. **合并幅度** — 已确认为 42 到 15 个文件的激进合并方案。

3. **视觉快照** — 已调研确认可行，mimo 能实现（QWidget.grab() + scikit-image SSIM）。建议等核心场景测试稳定后（第五步完成）再引入，不作为首轮执行内容。

4. **高风险测试触发** — 采用三层策略：日常 `pytest --changed`、核心文件修改时自动触发、打包前自动验证。详见第七节。
