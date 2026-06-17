# `test_performance_optimization.py` 去向说明（T-G17）

该文件原本整文件 `pytestmark = pytest.mark.skip`（需 customtkinter 旧依赖），
60 个用例**从未真正运行**，造成"覆盖错觉"。去 skip 后实测：17 passed / 17 failed
/ 26 errors（errors 来自从未定义的 `home_page` / `tk_root` fixture 与 `ctk`）。

经核对，仍有效的用例均已被现有 active 测试覆盖，故删除原文件。各类去向：

| 原 class | 状态 | 去向 / 替代 |
|---|---|---|
| `TestFileListView` | error（旧 ctk API：`_format_duration`/`_get_status_text` 旧签名） | FILE-004 列表行为见 `test_file_list.py`（PySide6 `FileListView`） |
| `TestButtonIncrementalUpdate` | error（`home_page` fixture 未定义；`_create_file_row`/`_file_rows` 已不存在） | 已废弃 API，无对应需求 |
| `TestImmediateFeedback` | error（同上 + tkinter `configure`/`messagebox`） | 录音按钮反馈属 GUI，REC 链路见 `test_recorder.py` |
| `TestFileChangeDebounce` | failed | 防抖为旧 ctk 刷新实现，PySide6 不适用 |
| `TestAsyncDurationFetch` | failed（`FileManager.add_file` 异步实现已变） | 时长获取见 `test_file_manager.py` |
| `TestAsyncFileRead` / `TestAdaptivePolling` | failed（旧 `_poll` 协议） | 轮询/转写派发见 `test_transcription.py`、`test_transcription_queue.py` |
| `TestSpeakerIdTypeUnification` | **passed** | 已覆盖：`test_dialogs_p0.py::TestGetEmbeddingById` |
| `TestMatchSuggestion` | error（`tk_root` + ctk widget） | 匹配建议为 GUI；`_accept_suggestion`/`_add_match_suggestion` 行为见 `test_dialogs_p0.py` 与 `test_voiceprint_gui_flow.py` |
| `TestRecorderThreadSafety` | failed（手搓 `__new__` 构造） | **迁移**：`test_recorder.py::TestPauseResume`/`TestTimer`（真实实例 + 暂停不计时断言） |
| `TestSpeakerParsing` | **passed** | 已覆盖：`test_dialogs_p0.py::TestParseSpeakersHelper`/`TestParseSpeakersDualTrack` |
| `TestRecordingBar` | error（ctk `RecordingBar(tk_root)`） | PySide6 计时格式见 `test_recorder.py::TestTimer::test_update_timer_format_hhmmss` |
| `TestConfigExplicitAttributes` | **passed** | 已覆盖：`test_config.py::TestConfig`（`test_config_attr_access` 等） |
| `TestFormatters` | **passed**（仅 JSON/SRT/TXT/MD） | **取代并扩充**：`test_formatters.py`（7 种格式 + HTML/CSV/VTT + 转义） |
| `TestModelManager` | failed（`ModuleNotFound` 旧路径） | 模型注册见 `test_model_registry.py` |

结论：删除该文件不丢失任何真实覆盖，并消除 `--collect-only` 中 60 个永不运行的虚假用例。
