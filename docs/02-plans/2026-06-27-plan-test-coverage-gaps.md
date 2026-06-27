# 测试优化与覆盖补全综合方案

> 日期：2026-06-27
> 状态：v3 — 已整合 Qoder 两轮审核意见
> 范围：删减弱测试 + 补充覆盖缺口 + 文件归类

---

## 一、现状

| 指标 | 数值 |
|------|------|
| 测试文件 | 18 个 |
| 测试用例 | ~435 |
| 可删减（WEAK/STALE） | ~34 |
| 覆盖缺口需新增 | ~27 |
| **净变化** | **-7** |

---

## 二、删减清单（34 个）

### test_tdd_flows.py — 删 12

`test_audio_files_valid`、`test_ai_service_creation`、`test_voiceprint_library_loads`、`test_voiceprint_match_in_transcription`、`test_voiceprint_page_loads`、`test_add_voice_dialog_recording_flow`、`test_voiceprint_quality_scores`、`test_voiceprint_detail_view`、`test_speaker_count_reasonable`、`test_transcription_result_structure`、`test_summary_speaker_correspondence`、`test_logging_on_failure`

### test_async_workers.py — 删 6

`test_names_applied_default_false`、`test_all_vendor_mappings`、`test_unknown_vendor_passthrough`、`test_already_full_name`、`test_app_startup_with_fixed_config`、`test_settings_page_loads_correctly`

### test_gui_config.py — 删 6

4 个 `*_exists`（被 `*_options` 覆盖）、`test_wizard_has_two_steps`、`test_returns_list`（VendorList 版）

### test_voiceprint.py — 删 5

3 个常量阈值、`test_extract_embedding_from_file`（hasattr）、`test_fifo淘汰行为`（重复）

### test_gui_home.py — 删 5

`test_selected_files_property`、`test_ai_summary_button_exists`、`test_stop_recording_method_exists`、`test_progress_updated_signal_exists`、`test_on_progress_updated_method_exists`

---

## 三、覆盖缺口补全

> Qoder 两轮审核修正，共 27 个新测试。

### 高优先级（数据安全）

#### GAP-1：VoiceprintLibrary 损坏恢复（+1）

```python
def test_load_corrupted_json():
    """截断 JSON 应回退为空库"""
    path.write_text('{"speakers": {"张三": {"name": "张三", "embeddings": [')
    lib = VoiceprintLibrary(str(path))
    assert lib.get_speakers() == {}
```

> ~~`test_load_wrong_types`~~ 删除：`SpeakerProfile.from_dict` 无类型校验，`name=123` 不会抛异常，断言必定失败。需先给 `from_dict` 加 `isinstance(data["name"], str)` 校验再补此测试。

#### GAP-3：Transcription 错误恢复（+5）

```python
def test_on_done_mixed_results():
    """部分成功/失败时信号计数正确"""
    handler._file_status = {"a.wav": "done", "b.wav": "failed", "c.wav": "done"}
    handler._done_called = False
    with qtbot.waitSignal(handler.transcription_done, timeout=1000) as blocker:
        handler._on_done()
    assert blocker.args == [2, 1]

def test_on_done_process_cleanup():
    """_on_done 应清理子进程"""
    handler._process = MagicMock()
    handler._process.is_alive.return_value = True
    handler._on_done()
    handler._process.terminate.assert_called_once()
    assert handler._process is None

def test_on_done_clears_done_flag():
    """新任务应重置 _done_called"""
    handler._done_called = True
    handler._execute_task(mock_task)
    assert handler._done_called is False

def test_check_queue_executes_next():
    """_check_queue 应执行队列中下一个任务"""
    handler._task_queue = MagicMock()
    handler._task_queue.get_next_task.return_value = mock_task
    handler._check_queue()
    handler._execute_task.assert_called_once_with(mock_task)

def test_on_done_guard_prevents_double_call():
    """_done_called guard 应阻止重复调用"""
    handler._file_status = {"a.wav": "done"}
    handler._done_called = False
    handler._on_done()
    handler._file_status = {"a.wav": "done", "b.wav": "done"}
    handler._on_done()  # 第二次调用应为空操作
```

#### GAP-4：VoiceprintLibrary 并发（+1，标记 xfail）

```python
@pytest.mark.xfail(reason="VoiceprintLibrary 非线程安全，已知设计限制")
def test_concurrent_add_speakers():
    """并发添加暴露文件竞争（文档型测试）"""
    lib = VoiceprintLibrary(str(tmp_path / "lib.json"))
    errors = []
    def add_many(prefix):
        try:
            for i in range(20):
                lib.add_speaker(f"{prefix}_{i}", np.random.rand(512), "test")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=add_many, args=(f"T{j}",)) for j in range(3)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(errors) > 0  # 预期会出错，记录已知限制
```

### 中优先级（功能正确性）

#### GAP-5：match() 边界值（+2，用 512 维向量重写）

```python
def test_match_below_threshold():
    """低于阈值应返回 None"""
    base = np.random.rand(512).astype(np.float32)
    base /= np.linalg.norm(base)
    lib.add_speaker("张三", base, "test")

    # 构造 cosine ≈ 0.29 的向量（低于 MATCH_THRESHOLD=0.31）
    noise = np.random.rand(512).astype(np.float32)
    noise /= np.linalg.norm(noise)
    below = (base * 0.29 + noise * 0.71).astype(np.float32)
    name, score = lib.match(below)
    assert name is None

def test_match_confirmed_threshold():
    """达到 confirmed 阈值应返回 confirmed"""
    base = np.random.rand(512).astype(np.float32)
    base /= np.linalg.norm(base)
    lib.add_speaker("张三", base, "test")

    # 构造 cosine ≈ 0.51 的向量（高于 HIGH_CONFIDENCE=0.50）
    noise = np.random.rand(512).astype(np.float32)
    noise /= np.linalg.norm(noise)
    above = (base * 0.51 + noise * 0.49).astype(np.float32)
    name, score = lib.match(above)
    assert name == "张三"
    assert score >= 0.50
```

#### GAP-7：SpeakerDialog._do_save()（+1，优先级降低）

```python
def test_do_save_name_mapping():
    """_do_save 应正确映射 spk_id 到名称"""
    # 整数 spk_id: 0 → "1"，字符串 spk_id: "本地-0" → "本地-0"
    # fixture 成本高（需 QApplication + mock QLineEdit），优先级降低
    ...
```

#### GAP-8：ExportDialog 格式转换（+3）

```python
def test_strip_markdown():
    """去除 markdown 标记"""
    assert _strip_markdown("**bold** text") == "bold text"
    assert _strip_markdown("`code`") == "code"

def test_convert_to_srt():
    """SRT 时间戳计算"""
    srt = _convert_to_srt("Speaker 1: 你好\nSpeaker 2: 你好")
    assert "00:00:00,000 --> 00:00:03,000" in srt

def test_export_includes_summary():
    """导出应包含 AI 摘要"""
    # 创建临时 transcript + summary 文件，验证输出包含两者
    ...
```

#### GAP-9：file_manager 中文路径（+1）

```python
def test_chinese_path_handling():
    """中文路径应正确保存和加载"""
    chinese_dir = tmp_path / "测试录音"
    chinese_dir.mkdir()
    wav = chinese_dir / "会议记录.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 100)
    fm.add_file(str(wav))
    fm2 = FileManager(data_file=str(tmp_path / "files.json"))
    assert fm2.get_file(str(wav)) is not None
```

#### GAP-10：settings_page 厂商切换（+1）

```python
def test_vendor_change_updates_models():
    """切换厂商应更新模型列表"""
    page._vendor_combo.setCurrentText("智谱 AI")
    models = [page._model_combo.itemText(i) for i in range(page._model_combo.count())]
    assert "glm-4.7-flash" in models
```

#### GAP-A（新增）：_extract_speaker_mapping 多格式（+3）

```python
def test_extract_speaker_mapping_bracket_format():
    """[Speaker N] 姓名 格式（含角色过滤）"""
    summary = "## 参会人员\n- [Speaker 1] 张三\n- [Speaker 2] （项目负责人）\n- [Speaker 3] 李四"
    result = handler._extract_speaker_mapping_from_summary(summary)
    assert result == {1: "张三", 3: "李四"}

def test_extract_speaker_mapping_duplicate_names():
    """重复姓名过滤（如 '嘉诚 嘉诚' → '嘉诚'）"""
    summary = "## 参会人员\n- [Speaker 1] 嘉诚 嘉诚\n- [Speaker 2] 正常姓名"
    result = handler._extract_speaker_mapping_from_summary(summary)
    assert result == {1: "嘉诚", 2: "正常姓名"}

def test_extract_speaker_mapping_no_section():
    """无参会人员 section 时返回 None"""
    summary = "## 会议摘要\n本次会议讨论了..."
    result = handler._extract_speaker_mapping_from_summary(summary)
    assert result is None
```

#### GAP-B（新增）：_on_done guard 防重入（已含在 GAP-3 中）

见 GAP-3 的 `test_on_done_guard_prevents_double_call`。

#### GAP-C（新增）：声纹冲突解决边界（+2）

```python
def test_conflict_all_match_same_name():
    """所有说话人匹配同一音色库成员时，仅保留最高分"""
    # 3 个 speaker embedding 都匹配 "张三"，score 0.4/0.6/0.8
    # 预期：只有 score=0.8 的被映射为 "张三"

def test_conflict_loser_keeps_original_name():
    """冲突败出的 speaker 应保留原始 Speaker N 名称"""
    # Speaker 1 和 Speaker 3 都匹配 "张三"，Speaker 3 分更高
    # 预期：Speaker 3 → "张三"，Speaker 1 保持 "Speaker 1"
```

### 低优先级（UI 状态）

| GAP | 测试 | 工作量 |
|-----|------|--------|
| GAP-11 RecordingBar 状态机 | 6 种组合 × 按钮状态断言 | 20min |
| GAP-12 first_launch 信号 | go_to_settings 信号触发 | 10min |
| GAP-13 批量操作 | 多选删除确认 | 15min |
| GAP-14 FIFO 策略确认 | 文档化当前行为 | 5min |

### 新增测试归属

| GAP | 归入文件 |
|-----|---------|
| GAP-1 | test_voiceprint.py |
| GAP-3 | test_transcription.py |
| GAP-4 | test_voiceprint.py |
| GAP-5 | test_voiceprint.py |
| GAP-7 | test_gui_dialogs.py |
| GAP-8 | test_gui_dialogs.py |
| GAP-9 | test_file_manager.py |
| GAP-10 | test_config.py（拆分后） |
| GAP-A | test_transcription.py |
| GAP-C | test_voiceprint.py |

---

## 四、文件归类（16 → 12）

> Qoder 第二轮审核：当前 3 个"垃圾桶文件"严重违反单一职责。

### 问题文件

| 文件 | 测试数 | 问题 |
|------|--------|------|
| test_gui_config.py | 58 | 混入模型注册表(18)、FirstLaunch(10)、声纹辅助(4)、中间窗口(2) |
| test_gui_home.py | 55 | 混入 TranscriptionHandler(3)、get_summary_path(6)、声纹冲突(3)、说话人解析(3) |
| test_async_workers.py | 37 | 万金油：主题提取(8)、guard(3)、厂商规范化(4)、配置过滤(3)、日志前缀(3) |

### 目标结构

| # | 文件 | 职责 | 预估测试数 |
|---|------|------|-----------|
| 1 | test_core.py | utils/paths/speaker_mapping 纯函数 | ~33 |
| 2 | test_config.py | Config 类 + 空值过滤 + 设置页 UI | ~36 |
| 3 | test_model_registry.py | 厂商列表/模型列表/BaseUrl/IsFreeModel | ~18 |
| 4 | test_voiceprint.py | SpeakerProfile + Library + GUI + 冲突检测 | ~42 |
| 5 | test_transcription.py | TranscriptionHandler 全部 | ~35 |
| 6 | test_file_manager.py | FileManager + 中文路径 + get_summary_path | ~14 |
| 7 | test_gui_dialogs.py | 弹窗 UI + 导出 + 预览 + 说话人解析 | ~28 |
| 8 | test_gui_home.py | 主页 GUI 专属（按钮/进度/文件列表） | ~28 |
| 9 | test_formatters.py | 7 种输出格式 | ~14 |
| 10 | test_recorder.py | 录音机 | ~18 |
| 11 | test_speaker_namer.py | SpeakerNamer（正则+LLM+guard） | ~14 |
| 12 | test_transcription_queue.py | 队列管理 | ~17 |

### 移入的文件

| 源文件 | 测试数 | 归入 |
|--------|--------|------|
| test_ai_service.py | 9 | test_model_registry.py |
| test_dual_track_merge.py | 18 | test_transcription.py |
| test_postprocess.py | 13 | test_transcription.py |
| test_tdd_flows.py | 12（删减后） | 有效测试归入各自模块文件 |

### 归类硬规则

1. **一个源模块 → 一个测试文件**
2. **GUI 测试文件只测 GUI**，不测业务逻辑
3. **新增测试不新增文件**（除非新增全新源模块）
4. **跨模块集成测试归入主模块**
5. **文件超过 80 个测试时拆分**

---

## 五、执行顺序

| 步骤 | 内容 | 工作量 |
|------|------|--------|
| 1 | 删减 34 个弱测试（现有文件结构） | 30min |
| 2 | 新增 GAP-1/3/4/5/8/9/A/C（现有文件结构） | 2h |
| 3 | 新增 GAP-7/10（需拆分文件后） | 30min |
| 4 | 文件归类迁移（纯 refactor，不改逻辑） | 1h |
| 5 | 新增 GAP-11~14 低优（可选） | 45min |

**总计**：~4.5h
**建议**：步骤 1-2 一个 commit，步骤 3-4 一个 commit，分开提交便于 review。

---

## 六、预期结果

| 指标 | 当前 | 优化后 | 变化 |
|------|------|--------|------|
| 测试文件 | 18 | 12 | -33% |
| 测试用例 | ~435 | ~401 | -8% |
| WEAK/STALE | ~34 | 0 | -100% |
| 覆盖缺口 | 14 | 0 | -100% |
| 运行时间 | ~44s | ~40s | -9% |
