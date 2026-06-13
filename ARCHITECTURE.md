# 技术架构

> 最后更新：2026-06-11

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  主进程 (GUI)                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MeetScribeApp (gui/app.py)                           │   │
│  │  - 窗口布局 (topbar + home + settings + voiceprint)    │   │
│  │  - 录音控制 (start/stop/pause)                        │   │
│  │  - 文件列表管理 (add/delete/select/refresh)           │   │
│  │  - 转写任务调度 (queue polling)                       │   │
│  │  - AI 摘要/纠错/发言人管理                            │   │
│  │  - 弹窗 (预览/发言人/合并排序)                        │   │
│  │  - 日志/状态栏                                        │   │
│  └──────────────────────────────────────────────────────┘   │
│           │ multiprocessing.Queue (自适应轮询)               │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  子进程 (transcribe_worker.py)                         │   │
│  │  Transcriber (transcriber.py)                          │   │
│  │  - Stage 1: SenseVoice + VAD (ASR)                     │   │
│  │  - Stage 2: cam++ (说话人分离)                         │   │
│  │  - Stage 3: ct-punc (标点恢复, 后处理)                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  录音模块 (unified_recorder.py)                        │   │
│  │  - PyAudioWPatch (WASAPI Loopback)                     │   │
│  │  - 后台线程采集音频                                    │   │
│  │  - 支持 mic / system / dual 三种模式                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  其他模块                                              │   │
│  │  - config.py (JSON 配置)                               │   │
│  │  - file_manager.py (文件列表 + 历史)                   │   │
│  │  - ai_service.py (MiMo API)                            │   │
│  │  - speaker_namer.py (正则 + LLM 姓名提取)              │   │
│  │  - voiceprint.py (声纹库管理)                          │   │
│  │  - dual_track_merge.py (双轨合并)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 数据流

```
录音 → WAV 文件 → 子进程转写 → 转写结果 JSON/MD
                      ↓
              说话人嵌入向量 → 声纹库匹配 → 自动命名
                      ↓
              AI 摘要生成 → 摘要 MD
                      ↓
              说话人姓名提取 → 映射回转写结果
```

## 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| GUI 主窗口 | `gui/app.py` | 窗口管理、模块协调 |
| 主页 | `gui/home_page.py` | 录音控制 + 文件列表 + 日志 |
| 设置页 | `gui/settings_page.py` | 配置管理 |
| 音色库页 | `gui/voiceprint_page.py` | 声纹库 CRUD |
| 文件列表 | `gui/file_list_view.py` | 文件展示、选中、操作 |
| 录音控制栏 | `gui/recording_bar.py` | 录音按钮、计时器、模式选择 |
| 弹窗 | `gui/dialogs.py` | 预览、发言人管理、导出 |
| 转写调度 | `gui/transcription.py` | 任务队列、进度、AI 后处理 |
| 转写引擎 | `transcriber.py` | FunASR 模型调用 |
| 子进程 | `transcribe_worker.py` | 独立进程执行转写 |
| 录音 | `unified_recorder.py` | PyAudio 录音、文件保存 |
| AI 服务 | `ai_service.py` | MiMo API 调用 |
| 声纹库 | `voiceprint.py` | 声纹存储、匹配、提取 |
| 文件管理 | `file_manager.py` | 文件列表持久化 |
| 配置 | `config.py` | JSON 配置读写 |
| 说话人命名 | `speaker_namer.py` | 正则 + LLM 姓名提取 |

## 关键设计决策

### 1. 多进程架构
- GUI 主进程 + 转写子进程
- 通过 `multiprocessing.Queue` 通信
- 自适应轮询（50ms-500ms），空闲时退避减少 CPU

### 2. 模型加载策略
- 所有模型在同一 AutoModel 实例中加载
- 一次 `generate()` 调用完成 ASR + 说话人分离 + 标点
- 子进程独立内存，不干扰 GUI

### 3. 双轨录音
- 麦克风 + 系统音频（WASAPI Loopback）同时录制
- 录音完成后自动合并
- VB-Audio Cable 作为虚拟音频设备

### 4. 声纹管理
- CAM++ 嵌入向量存储在 `data/voiceprint_library.json`
- 支持自动匹配（转写时）和手动录入（音色库页面）
- 嵌入向量持久化到磁盘（`*_embeddings.json`）

### 5. 配置管理
- JSON 配置文件 `config/settings.json`
- 支持向后兼容（旧版 mimo 配置自动迁移到新版 ai 格式）
- 多厂商 AI 服务支持（小米、百度、阿里等 11 家）
