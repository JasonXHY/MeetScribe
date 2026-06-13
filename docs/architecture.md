# 侧耳倾听（MeetScribe）— 架构设计文档

> 版本：v3.0
> 日期：2026-06-14
> 状态：正式协作版
> 受众：开发者

---

## 一、系统架构概览

### 1.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         主进程 (GUI)                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  MeetScribeApp (gui/app.py)                                  │   │
│  │  ├── 窗口布局 (TopBar + QStackedWidget)                       │   │
│  │  ├── 录音控制 (start/stop/pause)                              │   │
│  │  ├── 文件列表管理 (add/delete/select/refresh)                  │   │
│  │  ├── 转写任务调度 (TranscriptionHandler)                       │   │
│  │  ├── AI 摘要/纠错/发言人管理                                   │   │
│  │  ├── 弹窗 (PreviewDialog/ExportDialog/SpeakerDialog)          │   │
│  │  └── 日志/状态栏                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │ multiprocessing.Queue (自适应轮询 50ms-500ms)           │
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  子进程 (transcribe_worker.py)                                │   │
│  │  ├── Transcriber (transcriber.py)                             │   │
│  │  │   ├── Stage 1: SenseVoice + fsmn-vad (ASR)                 │   │
│  │  │   ├── Stage 2: CAM++ (说话人分离)                           │   │
│  │  │   └── Stage 3: ct-punc (标点恢复 + 后处理)                  │   │
│  │  └── 转写结果 → JSON/MD 输出                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  录音模块 (unified_recorder.py)                               │   │
│  │  ├── PyAudioWPatch (WASAPI Loopback)                          │   │
│  │  ├── 后台线程采集音频                                          │   │
│  │  └── 支持 mic / system / dual 三种模式                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  业务逻辑模块                                                  │   │
│  │  ├── config.py (JSON 配置管理)                                 │   │
│  │  ├── file_manager.py (文件列表 + 历史)                          │   │
│  │  ├── ai_service.py (MiMo API / OpenAI 兼容)                    │   │
│  │  ├── speaker_namer.py (正则 + LLM 姓名提取)                    │   │
│  │  ├── voiceprint.py (声纹库管理)                                 │   │
│  │  ├── dual_track_merge.py (双轨合并)                             │   │
│  │  └── model_registry.py (模型注册表)                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 分层架构

```
┌─────────────────────────────────────────┐
│           表示层 (GUI)                    │
│  app.py, home_page.py, settings_page.py  │
│  voiceprint_page.py, dialogs.py          │
│  recording_bar.py, file_list_view.py     │
│  topbar.py, styles.py, first_launch.py   │
├─────────────────────────────────────────┤
│           调度层 (Bridge)                 │
│  transcription.py (QTimer轮询+信号)       │
├─────────────────────────────────────────┤
│           业务逻辑层 (Core)               │
│  config.py, file_manager.py              │
│  unified_recorder.py                     │
│  ai_service.py, voiceprint.py            │
│  speaker_namer.py                        │
│  dual_track_merge.py                     │
│  model_registry.py, formatters.py        │
├─────────────────────────────────────────┤
│           引擎层 (Engine)                 │
│  transcriber.py (核心转写引擎)            │
│  transcribe_worker.py (子进程工作函数)     │
│  transcription_queue.py (任务队列)         │
└─────────────────────────────────────────┘
```

---

## 二、模块职责详解

### 2.1 GUI 模块

#### gui/app.py — 主窗口

**职责**：应用入口，窗口管理，全局状态协调

**核心类**：`MeetScribeApp(QMainWindow)`

**关键方法**：
- `__init__()`: 初始化所有组件，连接信号
- `_on_navigate(page)`: 页面切换
- `_on_recorder_state_change()`: 录音状态回调
- `_on_recorder_save()`: 录音保存回调
- `_on_file_changed()`: 文件变更监听（防抖）
- `_on_transcription_done()`: 转写完成回调
- `_restore_config()`: 配置恢复
- `_save_config()`: 配置保存

**依赖**：
- 导入 gui 模块：TopBar, HomePage, SettingsPage, VoiceprintPage, TranscriptionHandler
- 导入业务模块：Config, FileManager, UnifiedRecorder

**注意事项**：
- 所有 UI 操作必须在主线程
- 跨组件访问通过公共 API，不直接访问私有属性
- 录音回调在后台线程，需要用 QTimer.singleShot 转到主线程

---

#### gui/home_page.py — 主页

**职责**：录音控制、文件列表、日志显示

**核心类**：`HomePage(QWidget)`

**关键方法**：
- `_start_recording()`: 开始录音
- `_stop_recording()`: 停止录音
- `_pause_recording()`: 暂停录音
- `_add_files()`: 添加音频文件
- `_delete_selected()`: 删除选中文件
- `_clear_list()`: 清空列表
- `_transcribe_single()`: 转写单个文件
- `_start_transcription()`: 批量转写
- `_merge_transcribe()`: 合并转写
- `_refresh_file_list()`: 刷新文件列表
- `_preview_result()`: 预览转写结果
- `_export_result()`: 导出结果
- `_open_folder()`: 打开文件夹

**公共 API**：
- `get_log_area()`: 获取日志区域控件
- `get_recording_bar()`: 获取录音控制栏
- `set_format(fmt)`: 设置输出格式
- `get_format()`: 获取输出格式
- `refresh_file_list()`: 刷新文件列表（供外部调用）

**依赖**：
- 导入 gui 模块：RecordingBar, FileListView
- 导入业务模块：UnifiedRecorder（通过 app.recorder）
- 导入弹窗：PreviewDialog, ExportDialog, SpeakerDialog

---

#### gui/settings_page.py — 设置页

**职责**：应用配置管理

**核心类**：`SettingsPage(QWidget)`

**关键方法**：
- `_build_ui()`: 构建界面
- `_build_recording_section()`: 录音设置区
- `_build_engine_section()`: 引擎设置区
- `_build_ai_section()`: AI 设置区（⚠️ 当前不完整）
- `save_config()`: 保存配置
- `restore_config()`: 恢复配置

**信号**：
- `settings_changed`: 配置变更时发射

**依赖**：
- 导入业务模块：Config, ModelManager

---

#### gui/voiceprint_page.py — 音色库页

**职责**：声纹库管理

**核心类**：`VoiceprintPage(QWidget)`

**关键方法**：
- `_load_library()`: 加载声纹库
- `_add_voice()`: 添加音色（打开 AddVoiceDialog）
- `_delete_speaker()`: 删除说话人
- `_edit_speaker()`: 编辑说话人姓名
- `_play_sample()`: 播放声纹样本

**依赖**：
- 导入业务模块：VoiceprintLibrary
- 导入弹窗：AddVoiceDialog

---

#### gui/dialogs.py — 弹窗组件

**职责**：各种弹窗对话框

**核心类**：
- `PreviewDialog`: 转写结果预览
- `ExportDialog`: 导出格式选择
- `SpeakerDialog`: 发言人管理
- `MergeOrderDialog`: 合并排序
- `AddVoiceDialog`: 添加音色（录音朗读）
- `TranscriptionCompleteDialog`: 转写完成通知

---

#### gui/transcription.py — 转写调度器

**职责**：桥接 GUI 和转写子进程

**核心类**：`TranscriptionHandler(QObject)`

**关键方法**：
- `start(file_paths, output_dir, options)`: 启动转写
- `_poll()`: 轮询子进程消息（QTimer）
- `_process_message(msg)`: 处理子进程消息
- `_match_voiceprints()`: 声纹匹配（⚠️ 当前缺失）
- `_on_ai_correction()`: AI 纠错
- `_on_ai_summary()`: AI 摘要

**信号**：
- `log_message(str)`: 日志消息
- `status_changed(str)`: 状态变更
- `file_status_changed(int, str)`: 文件状态变更
- `transcription_done(dict)`: 转写完成

**消息协议**：
```python
("status", "转写中...")        # 状态更新
("log", "正在处理...")         # 日志输出
("processing", file_id)        # 文件状态更新
("file_done", path, spk_data)  # 转写完成
("merge_done", paths)          # 合并完成
("spk_embeddings", id, emb)    # 声纹嵌入
("sentences", id, sentences)   # 句子数据
("progress", file_id, pct)     # 进度更新
("auto_correction", path)      # AI 纠错完成
("auto_summary", path)         # AI 摘要完成
("error", msg)                 # 错误处理
("done",)                      # 全部完成
```

**注意事项**：
- QTimer 轮询间隔自适应（50-500ms）
- 子进程通过 multiprocessing.Queue 通信
- 声纹匹配逻辑当前缺失（F-1 问题）

---

### 2.2 业务逻辑模块

#### config.py — 配置管理

**职责**：JSON 配置文件读写

**核心类**：`Config`

**关键方法**：
- `get(key, default)`: 获取配置项
- `set(key, value)`: 设置配置项
- `save()`: 保存到文件
- `load()`: 从文件加载

**配置项**：
```json
{
  "recording_dir": "recordings",
  "transcript_dir": "transcripts",
  "output_format": "md",
  "recording_mode": "dual",
  "auto_correction": "转写后自动纠错",
  "auto_summary": "转写后自动生成",
  "mimo_api_key": "",
  "ai_model": "MiMo",
  "punctuation_recovery": true,
  "garbled_filter": true,
  "vad_sensitivity": "medium",
  "compute_device": "cpu"
}
```

**注意事项**：
- 配置文件路径：`config/settings.json`
- 配置文件不能提交到 Git（包含 API Key）
- 键名使用英文，值可以是中文字符串

---

#### file_manager.py — 文件管理

**职责**：文件列表管理和历史持久化

**核心类**：`FileManager`

**关键方法**：
- `add_file(path)`: 添加文件
- `remove_file(file_id)`: 删除文件
- `get_all_files()`: 获取所有文件
- `get_file(file_id)`: 获取单个文件
- `update_status(file_id, status)`: 更新文件状态
- `save_history()`: 保存历史
- `load_history()`: 加载历史
- `add_listener(callback)`: 添加变更监听
- `notify_listeners()`: 通知监听器

**数据结构**：
```python
@dataclass
class FileRecord:
    id: int
    path: str
    filename: str
    duration: float
    size: int
    status: FileStatus  # PENDING, PROCESSING, DONE, ERROR
    group_id: Optional[int]  # 双轨文件归组
    created_at: datetime
```

---

#### unified_recorder.py — 录音模块

**职责**：音频录制和保存

**核心类**：`UnifiedRecorder`

**关键方法**：
- `start(mode)`: 开始录音
  - `mode="mic"`: 仅麦克风
  - `mode="system"`: 仅系统音频
  - `mode="dual"`: 双轨录音
- `stop()`: 停止录音
- `pause()`: 暂停录音
- `resume()`: 继续录音

**回调**：
- `on_state_change(state)`: 录音状态变更
- `on_save(path)`: 录音保存完成
- `on_stop_complete()`: 录音完全停止

**技术细节**：
- 使用 PyAudioWPatch 支持 WASAPI Loopback
- 后台线程采集音频，不阻塞 GUI
- 输出格式：16kHz 单声道 WAV
- 双轨模式输出两个文件：`meeting_xxx.wav` + `meeting_xxx_sys.wav`

---

#### ai_service.py — AI 服务

**职责**：云端/本地 AI 功能

**核心类**：`AIService`

**关键方法**：
- `generate_correction(text)`: LLM 纠错
- `generate_summary(transcript)`: AI 摘要
- `extract_speaker_names(transcript)`: 发言人姓名提取

**支持厂商**（10+）：
- 小米 MiMo
- 百度文心
- 阿里通义
- 智谱 GLM
- 月之暗面 Kimi
- 字节豆包
- 腾讯混元
- 讯飞星火
- 零一万物
- MiniMax
- 本地 Ollama

**API 兼容**：OpenAI 兼容接口

---

#### voiceprint.py — 声纹库

**职责**：声纹库管理和匹配

**核心类**：`VoiceprintLibrary`

**关键方法**：
- `add_speaker(name, embedding, source, quality)`: 添加说话人
- `match_with_confidence(embedding)`: 声纹匹配
- `get_all_speakers()`: 获取所有说话人
- `remove_speaker(speaker_id)`: 删除说话人
- `save()`: 保存到文件
- `load()`: 从文件加载

**匹配算法**：
- 余弦相似度计算
- 阈值 0.31（低置信度）
- 高置信度 0.50（自动命名）
- 同源去重：余弦 >0.999 跳过

**持久化**：
- 文件：`data/voiceprint_library.json`
- 嵌入向量：`data/{name}_embeddings.json`
- FIFO 淘汰：每说话人最多 5 个样本

---

#### speaker_namer.py — 说话人命名

**职责**：从转写文本中提取说话人姓名

**核心类**：`SpeakerNamer`

**关键方法**：
- `extract_names(text)`: 提取姓名
- `_regex_extract(text)`: 正则提取
- `_llm_extract(text)`: LLM 兜底提取

**策略**：
1. 优先正则匹配（"我是张三"、"这里是李四"等）
2. 正则失败时调用 LLM 提取
3. LLM 也失败时保持 "Speaker N" 标识

---

#### dual_track_merge.py — 双轨合并

**职责**：合并双轨转写结果

**核心函数**：
- `merge_dual_transcripts(mic_result, sys_result)`: 合并两轨结果
- `find_dual_track_pair(files)`: 查找双轨文件对

**合并策略**：
1. 按时间戳排序
2. 本地发言标注 "本地-N"
3. 远程发言标注 "远程-N"
4. 保持时间顺序

---

### 2.3 引擎模块

#### transcriber.py — 转写引擎（~1300行）

**职责**：核心转写流水线

**核心类**：`Transcriber`

**转写流水线**：
```python
def transcribe_staged(audio_path, options):
    # Stage 1: ASR (语音识别)
    segments = sensevoice_asr(audio_path)
    
    # Stage 2: Speaker Diarization (说话人分离)
    speakers = campp_diarization(audio_path)
    
    # Stage 3: Punctuation Recovery (标点恢复)
    punctuated = ct_punc(segments)
    
    # Stage 4: Post-processing (后处理)
    result = postprocess(punctuated, speakers)
    
    return result
```

**依赖模型**：
- SenseVoice (~900MB): 语音识别
- CAM++ (~27MB): 说话人分离
- ct-punc (~1GB): 标点恢复
- fsmn-vad: 语音端点检测

**模型管理**：
- 首次启动自动下载
- 缓存到 `models_cache/` 目录
- ModelManager 管理下载状态

---

#### transcribe_worker.py — 子进程工作函数

**职责**：在子进程中执行转写

**核心函数**：
- `transcribe_worker(input_queue, output_queue, options)`: 工作函数

**通信协议**：
- 输入队列：接收转写任务
- 输出队列：发送进度和结果
- 消息格式：元组 `(type, data...)`

---

## 三、数据存储设计

### 3.1 文件结构

```
C:\侧耳倾听\
├── config/
│   └── settings.json          # 应用配置（不提交到Git）
├── data/
│   ├── file_history.json      # 文件历史记录
│   └── voiceprint_library.json # 声纹库数据
├── recordings/                # 录音文件目录
│   ├── meeting_20260614.wav   # 麦克风录音
│   └── meeting_20260614_sys.wav # 系统音频录音
├── transcripts/               # 转写结果目录
│   ├── meeting_20260614_transcript.md
│   └── meeting_20260614_summary.md
├── models_cache/              # 模型缓存（不提交到Git）
│   └── models/
│       └── iic/
│           ├── SenseVoiceSmall/
│           ├── speech_campplus_sv_zh-cn_16k-common/
│           └── punc_ct-transformer_cn-en-common-vocab471067-large/
├── logs/                      # 日志文件
│   └── meetscribe.log
├── src/                       # 源代码
│   ├── gui/                   # GUI 模块
│   └── *.py                   # 业务逻辑模块
└── tests/                     # 测试文件
```

### 3.2 配置文件格式

```json
{
  "recording_dir": "C:\\MeetScribe\\recordings",
  "transcript_dir": "C:\\MeetScribe\\transcripts",
  "output_format": "md",
  "recording_mode": "dual",
  "auto_correction": "转写后自动纠错",
  "auto_summary": "转写后自动生成",
  "mimo_api_key": "",
  "ai_model": "MiMo",
  "punctuation_recovery": true,
  "garbled_filter": true,
  "vad_sensitivity": "medium",
  "compute_device": "cpu",
  "use_vb_cable": false,
  "system_notification": true
}
```

### 3.3 文件历史格式

```json
{
  "files": [
    {
      "id": 1,
      "path": "C:\\MeetScribe\\recordings\\meeting_20260614.wav",
      "filename": "meeting_20260614.wav",
      "duration": 2732.5,
      "size": 87456000,
      "status": "DONE",
      "group_id": null,
      "created_at": "2026-06-14T10:30:00"
    }
  ]
}
```

### 3.4 声纹库格式

```json
{
  "speakers": [
    {
      "id": 1,
      "name": "张三",
      "source": "manual_recording",
      "quality": 0.92,
      "sample_count": 3,
      "created_at": "2026-06-14T10:35:00"
    }
  ]
}
```

---

## 四、线程模型

### 4.1 线程分布

```
主线程 (GUI)
├── Qt 事件循环
├── QTimer 轮询 (TranscriptionHandler._poll)
├── QTimer 轮询 (GUILogHandler._poll_queue)
└── UI 渲染

录音线程 (UnifiedRecorder._thread)
├── PyAudio 回调
└── 音频数据写入

子进程 (TranscribeWorker)
├── Transcriber 转写
├── CAM++ 说话人分离
└── ct-punc 标点恢复
```

### 4.2 线程安全规则

1. **UI 操作必须在主线程**：所有 Qt 控件操作必须在主线程
2. **耗时操作必须在子线程/子进程**：录音、转写、AI 处理
3. **跨线程通信使用 Signal/Slot**：Qt 的线程安全机制
4. **不使用裸 threading.Thread**：使用 QThread + Signal
5. **不直接操作跨线程 UI**：使用 QTimer.singleShot 转到主线程

### 4.3 进程间通信

```
主进程 ←──── multiprocessing.Queue ────→ 子进程
         (自适应轮询 50ms-500ms)

消息类型：
- status: 状态更新
- log: 日志输出
- processing: 文件处理中
- file_done: 转写完成
- merge_done: 合并完成
- error: 错误处理
- done: 全部完成
```

---

## 五、关键设计决策

### 5.1 为什么选择 PySide6 而不是 customtkinter

| 维度 | customtkinter | PySide6 |
|------|---------------|---------|
| UI 流畅度 | 一般 | 硬件加速，流畅 |
| 杀毒误报 | 经常 | 很少 |
| 跨平台 | 有限 | 完整支持 |
| 信号机制 | 回调函数 | Signal/Slot |
| 线程安全 | 差 | 好 |
| 生态 | 较小 | 完整 |

**决策**：选择 PySide6，主要考虑 UI 流畅度和线程安全。

### 5.2 为什么使用多进程而不是多线程

| 维度 | 多线程 | 多进程 |
|------|--------|--------|
| GIL 限制 | 受限 | 不受限 |
| 内存隔离 | 共享 | 隔离 |
| 崩溃影响 | 可能影响主进程 | 独立崩溃 |
| 通信 | 共享变量 | Queue |

**决策**：转写是 CPU 密集型任务，使用多进程避免 GIL 限制，同时隔离崩溃风险。

### 5.3 为什么声纹匹配使用余弦相似度

| 算法 | 优点 | 缺点 |
|------|------|------|
| 余弦相似度 | 简单快速 | 对向量长度不敏感 |
| 欧氏距离 | 直观 | 对向量长度敏感 |
| 曼哈顿距离 | 计算快 | 不适合高维 |

**决策**：声纹嵌入向量已经归一化，余弦相似度是最合适的度量方式。

### 5.4 为什么 AI 摘要使用云端而不是本地

| 方案 | 优点 | 缺点 |
|------|------|------|
| 云端 API | 效果好，无需本地资源 | 需要联网，有成本 |
| 本地 LLM | 离线可用 | 效果差，需要 GPU |

**决策**：优先云端 API（效果好），本地 LLM 作为可选方案（离线场景）。

---

## 六、扩展性设计

### 6.1 厂商扩展

`model_registry.py` 支持 10+ 厂商，新增厂商只需：
1. 在 `MODEL_REGISTRY` 字典中添加厂商配置
2. 实现 `AIService` 中的对应方法

### 6.2 格式扩展

`formatters.py` 支持 7 种输出格式，新增格式只需：
1. 在 `FORMATTERS` 字典中添加格式处理器
2. 实现 `format_transcript()` 方法

### 6.3 引擎扩展

`transcriber.py` 支持多种 ASR 引擎，新增引擎只需：
1. 在 `transcribe_staged()` 中添加引擎分支
2. 实现对应的转写方法

---

## 七、测试策略

### 7.1 测试分层

```
单元测试
├── test_config.py: 配置管理
├── test_file_manager.py: 文件管理
├── test_voiceprint.py: 声纹匹配
├── test_transcription_queue.py: 转写队列
└── test_model_registry.py: 模型注册表

集成测试
├── test_dialogs_p0.py: 弹窗 P0 功能
├── test_home_page_p0.py: 主页 P0 功能
└── test_settings_engine.py: 引擎设置

GUI 测试
├── test_gui_startup.py: GUI 启动
├── test_file_list.py: 文件列表
└── test_voiceprint_page.py: 音色库页

端到端测试
└── test_voiceprint_page_e2e.py: 音色库端到端
```

### 7.2 测试运行

```bash
# 运行所有测试
pytest

# 运行指定测试
pytest tests/test_config.py

# 运行 P0 测试
pytest -k "p0"

# 查看覆盖率
pytest --cov=src --cov-report=html
```

### 7.3 测试注意事项

1. **GUI 测试需要 offscreen 模式**：`QT_QPA_PLATFORM=offscreen`
2. **避免修改 sys.stdout**：会导致 pytest 崩溃
3. **mock 外部依赖**：录音、转写、AI 服务需要 mock
4. **测试隔离**：每个测试独立，不依赖其他测试的状态

---

## 八、部署和打包

### 8.1 开发环境

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
python src/main.py
```

### 8.2 打包分发

```bash
# 使用 PyInstaller 打包
pyinstaller --name 侧耳倾听 --windowed src/main.py

# 输出目录
dist/侧耳倾听/
├── 侧耳倾听.exe
├── _internal/
│   ├── src/
│   ├── models_cache/
│   └── ...
└── config/
    └── settings.json
```

### 8.3 首次启动

1. 检测模型是否已下载
2. 未下载则自动下载（约 2GB）
3. 引导安装 VB-Audio Cable（如果需要双轨录音）
4. 引导配置 AI API Key
5. 进入主界面

---

## 九、安全考虑

### 9.1 API Key 安全

- 配置文件不提交到 Git
- API Key 显示为密码模式
- 支持明文切换查看

### 9.2 录音文件安全

- 录音文件本地存储
- 不自动上传到云端
- 用户可选择删除

### 9.3 声纹数据安全

- 声纹嵌入本地存储
- 不上传到云端
- 用户可选择删除

### 9.4 代码安全

- 不硬编码密钥
- 不使用 eval/exec
- 不执行用户输入的代码
