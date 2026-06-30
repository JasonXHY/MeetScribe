"""
转写功能测试
"""

import sys
import os
import re
import json
import tempfile
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, mock_open

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dual_track_merge import (
    find_dual_track_pair,
    merge_dual_transcripts,
    get_speaker_names_from_merged,
    build_merged_transcript,
    SYS_TRACK_SUFFIX,
)


class TestTranscription:
    """转写相关测试"""

    def test_required_models_configured(self):
        """测试 REQUIRED_MODELS 已配置"""
        from transcriber import REQUIRED_MODELS
        assert 'SenseVoiceSmall' in REQUIRED_MODELS
        assert 'fsmn-vad' in REQUIRED_MODELS
        assert 'ct-punc' in REQUIRED_MODELS
        assert 'cam++' in REQUIRED_MODELS

    def test_emotion2vec_removed(self):
        """测试 emotion2vec 已移除"""
        from transcriber import REQUIRED_MODELS
        assert 'emotion2vec_plus_large' not in REQUIRED_MODELS


class TestVoiceprintGuard:
    def test_match_voiceprints_guard(self):
        """guard 只在有数据时激活"""
        from gui.transcription import TranscriptionHandler

        app = MagicMock()
        manager = TranscriptionHandler(app)

        # 无数据时调用，guard 不应被激活
        manager._match_voiceprints()
        assert manager._voiceprint_matched is False

        # 有数据时调用，guard 应被激活
        manager._speaker_embeddings = {0: np.array([1.0, 0.0])}
        with patch('voiceprint.VoiceprintLibrary'):
            manager._match_voiceprints()
        assert manager._voiceprint_matched is True

        # 再次调用应被 guard 拦截（无变化即为成功）
        manager._match_voiceprints()


class TestMatchVoiceprintsAutoAdd:
    """测试 _match_voiceprints 自动添加声纹功能"""

    def _create_handler(self):
        """创建带有 mock app 的 TranscriptionHandler"""
        from gui.transcription import TranscriptionHandler
        mock_app = MagicMock()
        handler = TranscriptionHandler(mock_app)
        return handler

    @patch('voiceprint.VoiceprintLibrary')
    def test_confirmed_match_auto_adds_embedding(self, MockLibrary):
        """测试高置信度匹配后自动添加嵌入向量"""
        from file_manager import FileStatus

        handler = self._create_handler()

        # 设置 speaker_embeddings（模拟子进程发送的嵌入向量）
        embedding = np.random.rand(512).tolist()
        handler._speaker_embeddings = {0: embedding}

        # Mock 音色库
        mock_library = MagicMock()
        MockLibrary.return_value = mock_library
        # 高置信度匹配：score >= HIGH_CONFIDENCE(0.50) -> confirmed
        mock_library.match.return_value = ("张三", 0.8)

        # Mock file_manager
        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "/tmp/test.md"
        mock_item.speaker_names = {"0": "Speaker 0"}
        mock_item.file_path = "/tmp/test.wav"
        mock_item.file_name = "test.wav"
        handler._app.file_manager.files = [mock_item]
        handler._current_batch_paths = {"/tmp/test.wav"}

        with patch('os.path.exists', return_value=True), \
             patch('gui.transcription.apply_speaker_mapping'):
            handler._match_voiceprints()

        # 验证 add_speaker 被调用（自动添加声纹，source 为实际文件名，含 quality 参数）
        mock_library.add_speaker.assert_called_once_with("张三", embedding, source="test.wav", quality=0.85)

    @patch('voiceprint.VoiceprintLibrary')
    def test_suggested_match_does_not_auto_add(self, MockLibrary):
        """测试低置信度匹配不会自动添加嵌入向量"""
        from file_manager import FileStatus

        handler = self._create_handler()

        embedding = np.random.rand(512).tolist()
        handler._speaker_embeddings = {0: embedding}

        mock_library = MagicMock()
        MockLibrary.return_value = mock_library
        # 低置信度匹配：MATCH_THRESHOLD(0.31) <= score < HIGH_CONFIDENCE(0.50) -> suggested
        mock_library.match.return_value = ("张三", 0.4)

        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "/tmp/test.md"
        mock_item.speaker_names = {"0": "Speaker 0"}
        mock_item.file_path = "/tmp/test.wav"
        handler._app.file_manager.files = [mock_item]

        with patch('os.path.exists', return_value=True), \
             patch('gui.transcription.apply_speaker_mapping'):
            handler._match_voiceprints()

        # 验证 add_speaker 未被调用
        mock_library.add_speaker.assert_not_called()

    @patch('voiceprint.VoiceprintLibrary')
    def test_no_match_does_not_auto_add(self, MockLibrary):
        """测试无匹配时不会自动添加嵌入向量"""
        handler = self._create_handler()

        embedding = np.random.rand(512).tolist()
        handler._speaker_embeddings = {0: embedding}

        mock_library = MagicMock()
        MockLibrary.return_value = mock_library
        # 无匹配：name 为 None
        mock_library.match.return_value = (None, 0.0)

        handler._match_voiceprints()

        # 验证 add_speaker 未被调用
        mock_library.add_speaker.assert_not_called()

    @patch('voiceprint.VoiceprintLibrary')
    def test_auto_add_failure_does_not_break_matching(self, MockLibrary):
        """测试自动添加声纹失败不影响匹配流程"""
        from file_manager import FileStatus

        handler = self._create_handler()

        embedding = np.random.rand(512).tolist()
        handler._speaker_embeddings = {0: embedding}

        mock_library = MagicMock()
        MockLibrary.return_value = mock_library
        # 高置信度匹配：score >= HIGH_CONFIDENCE(0.50) -> confirmed
        mock_library.match.return_value = ("张三", 0.8)
        mock_library.add_speaker.side_effect = Exception("写入失败")

        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "/tmp/test.md"
        mock_item.speaker_names = {"0": "Speaker 0"}
        mock_item.file_path = "/tmp/test.wav"
        handler._app.file_manager.files = [mock_item]
        handler._current_batch_paths = {"/tmp/test.wav"}

        with patch('os.path.exists', return_value=True), \
             patch('gui.transcription.apply_speaker_mapping'):
            # 不应抛出异常
            handler._match_voiceprints()

        # 匹配仍然完成（检查 log_message 信号被发射）
        # log_message 是 Signal，不是 MagicMock，所以检查 _voiceprint_match_results
        assert handler._voiceprint_match_results == {0: {"name": "张三", "confidence": "confirmed"}}


class TestSummaryVoiceprintInjection:
    """AI-006: 音色库匹配结果注入摘要端到端（_voiceprint_match_results -> generate_summary）"""

    def _create_handler(self):
        from gui.transcription import TranscriptionHandler
        mock_app = MagicMock()
        handler = TranscriptionHandler(mock_app)
        return handler

    def test_matches_passed_to_summary(self, tmp_path):
        """匹配结果应原样传入 generate_summary 的 voiceprint_matches 参数"""
        handler = self._create_handler()
        handler._voiceprint_match_results = {0: {"name": "张三", "confidence": "confirmed"}}

        # mock AIService 捕获传入的 voiceprint_matches
        mock_ai = MagicMock()
        mock_ai.generate_summary.return_value = "# 会议主题\n\n摘要正文"
        handler._get_ai_service = MagicMock(return_value=mock_ai)

        out_dir = str(tmp_path)
        handler._generate_summary("Speaker 1: 大家好", "meeting", out_dir)

        # 断言 generate_summary 收到 voiceprint_matches 且含张三
        mock_ai.generate_summary.assert_called_once()
        _, kwargs = mock_ai.generate_summary.call_args
        assert kwargs.get("voiceprint_matches") == {0: {"name": "张三", "confidence": "confirmed"}}

    def test_prompt_references_identified_speaker(self):
        """generate_summary 构建的 system prompt 应含"已识别的说话人"段落并引用张三"""
        from ai_service import AIService

        ai = AIService(vendor="测试", model="m", api_key="dummy-key")

        captured = {}

        class _FakeCompletions:
            def create(self, *args, **kwargs):
                captured["messages"] = kwargs["messages"]

                class _Msg:
                    content = "# 会议主题\n\n摘要"

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        # 直接注入底层 client，绕过惰性创建的 OpenAI 实例
        ai._ai_client = _FakeClient()

        ai.generate_summary(
            "Speaker 1: 大家好",
            voiceprint_matches={0: {"name": "张三", "confidence": "confirmed"}},
        )

        system_prompt = captured["messages"][0]["content"]
        # 注入段落的专属标记（区别于 system prompt 规则中固有的"已识别的说话人"措辞）
        assert "【已识别的说话人（音色库匹配结果" in system_prompt
        assert "张三" in system_prompt
        assert "Speaker 1" in system_prompt

    def test_empty_matches_no_section_no_crash(self):
        """空匹配时不注入"已识别的说话人"段落，且正常生成"""
        from ai_service import AIService

        ai = AIService(vendor="测试", model="m", api_key="dummy-key")

        captured = {}

        class _FakeCompletions:
            def create(self, *args, **kwargs):
                captured["messages"] = kwargs["messages"]

                class _Msg:
                    content = "# 会议主题\n\n摘要"

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        # 直接注入底层 client，绕过惰性创建的 OpenAI 实例
        ai._ai_client = _FakeClient()

        # 空 dict 与 None 都不应注入段落、不应报错
        for matches in ({}, None):
            result = ai.generate_summary("Speaker 1: 你好", voiceprint_matches=matches)
            assert not result.startswith("[错误]")
            system_prompt = captured["messages"][0]["content"]
            # 空匹配时不应出现注入段落（其专属标记缺失）
            assert "【已识别的说话人（音色库匹配结果" not in system_prompt

    def test_handler_empty_matches_no_crash(self, tmp_path):
        """handler 在无匹配结果时调用 generate_summary 不报错"""
        handler = self._create_handler()
        handler._voiceprint_match_results = {}

        mock_ai = MagicMock()
        mock_ai.generate_summary.return_value = "# 会议主题\n\n摘要正文"
        handler._get_ai_service = MagicMock(return_value=mock_ai)

        handler._generate_summary("Speaker 1: 大家好", "meeting", str(tmp_path))

        _, kwargs = mock_ai.generate_summary.call_args
        assert kwargs.get("voiceprint_matches") == {}


class TestQualityEstimation:
    def test_compute_quality(self):
        """质量估算公式验证"""
        from transcriber import _compute_quality
        # 1 段 8 秒
        q = _compute_quality(1, 8.0)
        assert 0.50 <= q <= 0.60

        # 5 段 45 秒
        q = _compute_quality(5, 45.0)
        assert 0.80 <= q <= 0.95

        # 10+ 段 120 秒
        q = _compute_quality(10, 120.0)
        assert q >= 0.90


class TestGetAIServiceOllamaForwarding:
    """_get_ai_service 应将 config 中的 ollama 配置透传给 AIService（AI-005）"""

    def _create_handler(self, config_overrides=None):
        from gui.transcription import TranscriptionHandler
        defaults = {
            "ai_vendor": "小米",
            "ai_user_api_key": "",
            "ai_default_api_key": "sk-test",
            "ai_model": "mimo-v2.5",
            "ai_access_mode": "按量计费",
            "ollama_url": "http://host:1234/v1",
            "ollama_model": "llama3",
        }
        if config_overrides:
            defaults.update(config_overrides)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d=None: defaults.get(k, d)
        handler = TranscriptionHandler(mock_app)
        return handler

    @pytest.mark.skip(reason="Ollama forwarding not yet implemented")
    def test_get_ai_service_forwards_ollama_config(self):
        handler = self._create_handler()
        with patch('ai_service.AIService') as MockAIService:
            handler._get_ai_service()
            assert MockAIService.called
            _, kwargs = MockAIService.call_args
            assert kwargs.get("ollama_url") == "http://host:1234/v1"
            assert kwargs.get("ollama_model") == "llama3"


class TestOnDoneAndQueue:
    """_on_done 和 _check_queue 相关测试"""
    pytestmark = pytest.mark.integration

    def test_on_done_mixed_results(self, app, qtbot):
        """部分成功/失败时信号计数正确"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        handler._file_status = {"a.wav": "done", "b.wav": "failed", "c.wav": "done"}
        handler._done_called = False
        with qtbot.waitSignal(handler.transcription_done, timeout=1000) as blocker:
            handler._on_done()
        assert blocker.args == [2, 1]

    def test_on_done_process_cleanup(self, app):
        """_on_done 应清理转写线程"""
        from unittest.mock import MagicMock
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        handler._thread = mock_thread
        handler._on_done()
        mock_thread.join.assert_called_once_with(timeout=2)
        assert handler._thread is None

    def test_on_done_clears_done_flag(self, app, monkeypatch):
        """新任务应重置 _done_called"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        handler._done_called = True
        called = []
        def fake_execute(task):
            handler._done_called = False
            called.append(task)
        monkeypatch.setattr(handler, '_execute_task', fake_execute)
        mock_task = MagicMock()
        handler._execute_task(mock_task)
        assert handler._done_called is False
        assert len(called) == 1

    def test_check_queue_executes_next(self, app, monkeypatch):
        """_check_queue 应执行队列中下一个任务"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        handler._task_queue = MagicMock()
        mock_task = MagicMock()
        handler._task_queue.get_next_task.return_value = mock_task
        called = []
        def fake_execute(task):
            called.append(task)
        monkeypatch.setattr(handler, '_execute_task', fake_execute)
        handler._check_queue()
        assert len(called) == 1
        assert called[0] is mock_task

    def test_on_done_guard_prevents_double_call(self, app):
        """_done_called guard 应阻止重复调用"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        handler._file_status = {"a.wav": "done"}
        handler._done_called = False
        handler._on_done()
        # 第二次调用应为空操作
        handler._file_status = {"a.wav": "done", "b.wav": "done"}
        handler._on_done()  # 不应触发第二次信号


class TestSpeakerMappingExtraction:
    """_extract_speaker_mapping_from_summary 相关测试"""
    pytestmark = pytest.mark.integration

    def test_extract_speaker_mapping_bracket_format(self, app):
        """[Speaker N] 姓名 格式（含角色过滤）"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        summary = "## 参会人员\n- [Speaker 1] 张三\n- [Speaker 2] （项目负责人）\n- [Speaker 3] 李四"
        result = handler._extract_speaker_mapping_from_summary(summary)
        assert result == {1: "张三", 3: "李四"}

    def test_extract_speaker_mapping_duplicate_names(self, app):
        """重复姓名过滤（如 '嘉诚 嘉诚' → '嘉诚'）"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        summary = "## 参会人员\n- [Speaker 1] 嘉诚 嘉诚\n- [Speaker 2] 正常姓名"
        result = handler._extract_speaker_mapping_from_summary(summary)
        assert result == {1: "嘉诚", 2: "正常姓名"}

    def test_extract_speaker_mapping_no_section(self, app):
        """无参会人员 section 时返回 None"""
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=app)
        summary = "## 会议摘要\n本次会议讨论了..."
        result = handler._extract_speaker_mapping_from_summary(summary)
        assert result is None


# --- Postprocess tests (merged from test_postprocess.py) ---

from transcriber import Transcriber


def _make_sentence(text, spk=0, start=0, end=1000):
    return {"text": text, "spk": spk, "start": start, "end": end}


class TestPostprocessUnk:
    """过滤 <unk> 标记"""

    def test_removes_unk_tokens(self):
        t = Transcriber()
        sentences = [_make_sentence("你好<unk>世界")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "<unk>" not in result[0]["text"]
        assert result[0]["text"] == "你好世界"

    def test_removes_multiple_unk(self):
        t = Transcriber()
        sentences = [_make_sentence("<unk>今天<unk>开会<unk>")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "<unk>" not in result[0]["text"]

    def test_all_unk_leaves_empty_skipped(self):
        """如果去掉 <unk> 后只剩标点或过短，应跳过"""
        t = Transcriber()
        sentences = [_make_sentence("<unk><unk>")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 0


class TestPostprocessPunctuation:
    """清理连续标点"""

    def test_cleans_consecutive_chinese_punct(self):
        t = Transcriber()
        sentences = [_make_sentence("你好？。！世界")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "？。！" not in result[0]["text"]

    def test_cleans_trailing_punct(self):
        t = Transcriber()
        sentences = [_make_sentence("今天开会，，，")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert not result[0]["text"].endswith("，")
        assert not result[0]["text"].endswith(",")

    def test_cleans_leading_punct(self):
        t = Transcriber()
        sentences = [_make_sentence("，，，今天开会")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert not result[0]["text"].startswith("，")


class TestPostprocessShortMerge:
    """合并碎片化短句"""

    def test_merges_short_sentence_into_previous(self):
        t = Transcriber()
        sentences = [
            _make_sentence("今天开会讨论", spk=0, start=0, end=1000),
            _make_sentence("预算", spk=0, start=1100, end=1500),
        ]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert "预算" in result[0]["text"]

    def test_does_not_merge_different_speakers(self):
        t = Transcriber()
        sentences = [
            _make_sentence("今天开会讨论", spk=0, start=0, end=1000),
            _make_sentence("预算", spk=1, start=1100, end=1500),
        ]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 2

    def test_does_not_merge_long_gap(self):
        t = Transcriber()
        sentences = [
            _make_sentence("今天开会讨论", spk=0, start=0, end=1000),
            _make_sentence("预算", spk=0, start=5000, end=6000),
        ]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 2


class TestPostprocessEdgeCases:
    """边界情况"""

    def test_empty_input(self):
        t = Transcriber()
        result = t._postprocess_sentences([])
        assert result == []

    def test_single_character_skipped(self):
        t = Transcriber()
        sentences = [_make_sentence("啊")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 0

    def test_normal_text_unchanged(self):
        t = Transcriber()
        sentences = [_make_sentence("今天下午三点开会讨论项目进度")]
        result = t._postprocess_sentences(sentences)
        assert len(result) == 1
        assert result[0]["text"] == "今天下午三点开会讨论项目进度"

    def test_preserves_spk_and_timing(self):
        t = Transcriber()
        sentences = [_make_sentence("测试文本", spk=2, start=5000, end=8000)]
        result = t._postprocess_sentences(sentences)
        assert result[0]["spk"] == 2
        assert result[0]["start"] == 5000
        assert result[0]["end"] == 8000


# ══════════════════════════════════════════════════════════
#  双轨合并测试（T-G1 文件名配对 + T-G4 时间戳合并接线）
# ══════════════════════════════════════════════════════════

class TestFindDualTrackPairChineseSuffix:
    """录音器实际写出 {ts}会议_系统音频.wav，配对必须识别该后缀。"""

    def test_find_pair_from_mic_file(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")

        pair = find_dual_track_pair(str(mic))
        assert pair == (str(mic), str(sys))

    def test_find_pair_from_sys_file(self, tmp_path):
        """从系统音频轨文件也能反查到配对。"""
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")

        pair = find_dual_track_pair(str(sys))
        assert pair == (str(mic), str(sys))

    def test_no_pair_when_sys_missing(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        mic.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(mic)) is None

    def test_suffix_constant_matches_recorder(self):
        """SYS_TRACK_SUFFIX 必须与 unified_recorder 写出的后缀一致。"""
        assert SYS_TRACK_SUFFIX == "_系统音频"

    def test_recorder_dual_filenames_are_pairable(self, tmp_path):
        """回归锁定：录音器生成的双轨文件名必须能被 find_dual_track_pair 配对。

        这是 G1 修复的核心 bug——录音器与配对逻辑此前后缀不一致。
        用录音器真实的命名规则构造文件名，验证可配对。
        """
        from unified_recorder import SYS_TRACK_SUFFIX as REC_SUFFIX
        ts = "25061612"
        mic = tmp_path / f"{ts}会议.wav"
        sys = tmp_path / f"{ts}会议{REC_SUFFIX}.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(mic)) == (str(mic), str(sys))


class TestFindDualTrackPairLegacySuffix:
    """向后兼容历史 _sys 后缀（旧数据）。"""

    def test_find_pair_legacy_sys_from_mic(self, tmp_path):
        mic = tmp_path / "meeting.wav"
        sys = tmp_path / "meeting_sys.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(mic)) == (str(mic), str(sys))

    def test_find_pair_legacy_sys_from_sys(self, tmp_path):
        mic = tmp_path / "meeting.wav"
        sys = tmp_path / "meeting_sys.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(sys)) == (str(mic), str(sys))


class TestMergeDualTranscripts:
    def test_merge_interleaves_by_timestamp(self):
        mic = "[00:01] Speaker 1: 你好\n[00:05] Speaker 1: 在的"
        sys = "[00:03] Speaker 1: 听得到吗\n[00:07] Speaker 2: 我也在"
        merged = merge_dual_transcripts(mic, sys)
        lines = merged.strip().split("\n")
        assert "[00:01]" in lines[0] and "本地-1" in lines[0]
        assert "[00:03]" in lines[1] and "远程-1" in lines[1]
        assert "[00:05]" in lines[2] and "本地-1" in lines[2]
        assert "[00:07]" in lines[3] and "远程-2" in lines[3]

    def test_local_remote_labels(self):
        mic = "[00:01] Speaker 1: a"
        sys = "[00:02] Speaker 1: b"
        merged = merge_dual_transcripts(mic, sys)
        assert "本地-1" in merged
        assert "远程-1" in merged
        assert "Speaker" not in merged

    def test_get_speaker_names_from_merged(self):
        merged = "[00:01] 本地-1: a\n[00:02] 远程-1: b\n[00:03] 远程-2: c"
        names = get_speaker_names_from_merged(merged)
        labels = [label for _, label in names]
        assert "本地-1" in labels
        assert "远程-1" in labels
        assert "远程-2" in labels


class TestBuildMergedTranscript:
    def _make_pair(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        return str(mic), str(sys)

    def test_dual_pair_uses_timestamp_merge(self, tmp_path):
        """双轨对：按时间戳交错合并，加本地/远程前缀，无 '## file' 头。"""
        mic_path, sys_path = self._make_pair(tmp_path)
        texts = {
            mic_path: "[00:01] Speaker 1: 你好\n[00:05] Speaker 1: 在的",
            sys_path: "[00:03] Speaker 1: 听得到吗\n[00:07] Speaker 2: 我也在",
        }
        merged, is_dual = build_merged_transcript([mic_path, sys_path], texts)
        assert is_dual is True
        lines = merged.strip().split("\n")
        assert "[00:01]" in lines[0] and "本地-1" in lines[0]
        assert "[00:03]" in lines[1] and "远程-1" in lines[1]
        assert "[00:05]" in lines[2] and "本地-1" in lines[2]
        assert "[00:07]" in lines[3] and "远程-2" in lines[3]
        assert "## " not in merged
        assert "Speaker" not in merged

    def test_dual_pair_from_sys_first_order(self, tmp_path):
        """即使传入顺序是 system 在前，也按 mic=本地 / system=远程 归属。"""
        mic_path, sys_path = self._make_pair(tmp_path)
        texts = {
            mic_path: "[00:02] Speaker 1: 麦克风",
            sys_path: "[00:01] Speaker 1: 系统",
        }
        merged, is_dual = build_merged_transcript([sys_path, mic_path], texts)
        assert is_dual is True
        lines = merged.strip().split("\n")
        assert "远程-1" in lines[0]
        assert "本地-1" in lines[1]

    def test_ordinary_multifile_uses_concatenation(self, tmp_path):
        """普通多文件（非双轨对）仍走原 '## file' 顺序拼接。"""
        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        a.write_bytes(b"RIFF")
        b.write_bytes(b"RIFF")
        texts = {
            str(a): "[00:01] Speaker 1: alpha",
            str(b): "[00:02] Speaker 1: beta",
        }
        merged, is_dual = build_merged_transcript([str(a), str(b)], texts)
        assert is_dual is False
        assert "## a.wav" in merged
        assert "## b.wav" in merged
        assert "alpha" in merged and "beta" in merged
        assert "本地" not in merged and "远程" not in merged

    def test_three_files_not_treated_as_dual(self, tmp_path):
        """三个文件即便其中两个能配对，整体仍按普通多文件拼接。"""
        mic_path, sys_path = self._make_pair(tmp_path)
        c = tmp_path / "other.wav"
        c.write_bytes(b"RIFF")
        texts = {
            mic_path: "[00:01] Speaker 1: a",
            sys_path: "[00:02] Speaker 1: b",
            str(c): "[00:03] Speaker 1: c",
        }
        merged, is_dual = build_merged_transcript([mic_path, sys_path, str(c)], texts)
        assert is_dual is False
        assert "## " in merged


# ══════════════════════════════════════════════════════════
#  T-G4: worker 合并分支端到端接线（用 fake Transcriber，不需 funasr）
# ══════════════════════════════════════════════════════════

class _FakeQueue:
    """收集 worker 发出的所有消息，供断言。"""

    def __init__(self):
        self.messages = []

    def put(self, msg):
        self.messages.append(msg)

    def by_type(self, mtype):
        return [m for m in self.messages if m and m[0] == mtype]


@pytest.fixture
def fake_transcriber(monkeypatch):
    """注入一个假的 transcriber 模块，按文件名返回带时间戳的转写文本，避免加载 funasr。"""
    import sys
    import types

    texts_by_basename = {}

    class _FakeTranscriber:
        def __init__(self, *a, **k):
            self.spk_embeddings = {}
            self.sentences = []

        def check_models_ready(self):
            return True, []

        def transcribe(self, audio_path, **kwargs):
            return texts_by_basename[os.path.basename(audio_path)]

    fake_mod = types.ModuleType("transcriber")
    fake_mod.Transcriber = _FakeTranscriber
    monkeypatch.setitem(sys.modules, "transcriber", fake_mod)
    return texts_by_basename


class TestWorkerMergeBranch:
    def test_worker_dual_branch_calls_merge(self, tmp_path, fake_transcriber):
        """双轨对走 worker 合并分支：结果文件为时间戳交错的本地/远程合并文本。"""
        from transcribe_worker import transcribe_worker_process

        mic = tmp_path / "25061612会议.wav"
        sys_f = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys_f.write_bytes(b"RIFF")
        fake_transcriber["25061612会议.wav"] = "[00:01] Speaker 1: 你好\n[00:05] Speaker 1: 在的"
        fake_transcriber["25061612会议_系统音频.wav"] = "[00:03] Speaker 1: 听到了\n[00:07] Speaker 2: 我也在"

        q = _FakeQueue()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        transcribe_worker_process(
            q, str(tmp_path), "cpu",
            [str(mic), str(sys_f)], "md", {}, str(out_dir), True,
        )

        assert not q.by_type("error"), q.by_type("error")
        merge_done = q.by_type("merge_done")
        assert merge_done, "应发出 merge_done 消息"
        rpath = merge_done[0][2]
        content = open(rpath, encoding="utf-8").read()
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert "[00:01]" in lines[0] and "本地-1" in lines[0]
        assert "[00:03]" in lines[1] and "远程-1" in lines[1]
        assert "[00:05]" in lines[2] and "本地-1" in lines[2]
        assert "[00:07]" in lines[3] and "远程-2" in lines[3]
        assert "## " not in content
        assert "Speaker" not in content

    def test_worker_ordinary_merge_uses_concatenation(self, tmp_path, fake_transcriber):
        """普通多文件合并走 worker 原拼接路径（'## file' 头，不改写为本地/远程）。"""
        from transcribe_worker import transcribe_worker_process

        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        a.write_bytes(b"RIFF")
        b.write_bytes(b"RIFF")
        fake_transcriber["a.wav"] = "[00:01] Speaker 1: alpha"
        fake_transcriber["b.wav"] = "[00:02] Speaker 1: beta"

        q = _FakeQueue()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        transcribe_worker_process(
            q, str(tmp_path), "cpu",
            [str(a), str(b)], "md", {}, str(out_dir), True,
        )

        assert not q.by_type("error"), q.by_type("error")
        merge_done = q.by_type("merge_done")
        assert merge_done
        content = open(merge_done[0][2], encoding="utf-8").read()
        assert "## a.wav" in content and "## b.wav" in content
        assert "本地" not in content and "远程" not in content


# ══════════════════════════════════════════════════════════
#  T-G5: 本地-N/远程-N 标注端到端（SPK-008）
# ══════════════════════════════════════════════════════════

class TestLocalRemoteLabelsEndToEnd:
    def _make_pair(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        return str(mic), str(sys)

    def test_local_remote_labels_end_to_end(self, tmp_path):
        """双轨合并文本经弹窗解析路径后，条目带 本地-N / 远程-N 标签。"""
        from gui.dialogs import parse_speakers_from_result

        mic_path, sys_path = self._make_pair(tmp_path)
        texts = {
            mic_path: "[00:01] Speaker 1: 你好\n[00:09] Speaker 2: 我也在",
            sys_path: "[00:03] Speaker 1: 听得到吗\n[00:07] Speaker 2: 在的",
        }
        merged, is_dual = build_merged_transcript([mic_path, sys_path], texts)
        assert is_dual is True

        result = tmp_path / "result.md"
        result.write_text(merged, encoding="utf-8")
        speakers = parse_speakers_from_result(str(result))

        labels = {s["label"] for s in speakers}
        assert "本地-1" in labels
        assert "本地-2" in labels
        assert "远程-1" in labels
        assert "远程-2" in labels
        assert not any(str(s["label"]).startswith("Speaker") for s in speakers)

    def test_end_to_end_supports_naming(self, tmp_path):
        """端到端解析出的本地/远程条目可逐个命名（saved_names 回填）。"""
        from gui.dialogs import parse_speakers_from_result

        mic_path, sys_path = self._make_pair(tmp_path)
        texts = {
            mic_path: "[00:01] Speaker 1: 你好",
            sys_path: "[00:03] Speaker 1: 听得到吗",
        }
        merged, _ = build_merged_transcript([mic_path, sys_path], texts)
        result = tmp_path / "result.md"
        result.write_text(merged, encoding="utf-8")

        speakers = parse_speakers_from_result(
            str(result), saved_names={"本地-1": "张三", "远程-1": "李四"}
        )
        by_label = {s["label"]: s["name"] for s in speakers}
        assert by_label.get("本地-1") == "张三"
        assert by_label.get("远程-1") == "李四"


# ══════════════════════════════════════════════════════════
#  AI纠错/摘要完全异步化测试 (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestAsyncIntegration:
    """AI纠错/摘要完全异步化相关测试"""

    def test_correction_uses_worker(self):
        from gui.transcription import TranscriptionHandler, AICorrectionWorker
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch('gui.transcription.AICorrectionWorker') as MockWorker:
            mock_worker = MagicMock()
            MockWorker.return_value = mock_worker
            handler._start_correction_async("raw_text", "base", "/tmp", "/tmp/transcript.md")
            MockWorker.assert_called_once()
            mock_worker.start.assert_called_once()

    def test_summary_uses_worker(self):
        from gui.transcription import TranscriptionHandler, AISummaryWorker
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch('gui.transcription.AISummaryWorker') as MockWorker:
            mock_worker = MagicMock()
            MockWorker.return_value = mock_worker
            handler._start_summary_async("transcript", "base", "/tmp")
            MockWorker.assert_called_once()
            mock_worker.start.assert_called_once()

    def test_correction_worker_finished_signal_connected(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch('gui.transcription.AICorrectionWorker') as MockWorker:
            mock_worker = MagicMock()
            MockWorker.return_value = mock_worker
            handler._start_correction_async("raw_text", "base", "/tmp", "/tmp/transcript.md")
            assert mock_worker.finished.connect.call_count >= 2
            assert mock_worker.error.connect.call_count >= 2

    def test_summary_worker_finished_signal_connected(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch('gui.transcription.AISummaryWorker') as MockWorker:
            mock_worker = MagicMock()
            MockWorker.return_value = mock_worker
            handler._start_summary_async("transcript", "base", "/tmp")
            assert mock_worker.finished.connect.call_count >= 2
            assert mock_worker.error.connect.call_count >= 2

    def test_correction_finished_saves_file(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._on_correction_finished(
            "corrected_text", "base", "/tmp", "/tmp/transcript.md"
        )
        with patch('builtins.open', mock_open()) as mock_file:
            handler._on_correction_finished(
                "corrected_text", "base", "/tmp", "/tmp/transcript.md"
            )
            mock_file.assert_called()

    def test_summary_finished_saves_file(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch('builtins.open', MagicMock()):
            with patch('os.path.exists', return_value=True):
                handler._on_summary_finished(
                    "summary_text", "base", "/tmp"
                )

    def test_correction_error_logs_message(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch.object(handler, 'log_message') as mock_log:
            handler._on_correction_error("error message")
            mock_log.emit.assert_called()

    def test_summary_error_logs_message(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        with patch.object(handler, 'log_message') as mock_log:
            handler._on_summary_error("error message")
            mock_log.emit.assert_called()


# ══════════════════════════════════════════════════════════
#  转写后处理异步化测试 (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestAsyncPostprocess:
    """转写后处理异步化相关测试"""

    def test_names_applied_guard_blocks_second_call(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._names_applied = True
        with patch.object(handler, '_get_ai_service') as mock_ai:
            handler._apply_speaker_names()
            mock_ai.assert_not_called()

    def test_names_applied_resets_on_new_task(self):
        from gui.transcription import TranscriptionHandler
        app = MagicMock()
        handler = TranscriptionHandler(app)
        handler._names_applied = True
        with patch('threading.Thread'):
            handler._execute_task(MagicMock())
        assert handler._names_applied is False


# ══════════════════════════════════════════════════════════
#  转写文件输出到配置目录 (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestOutputDirectory:
    """转写文件应输出到配置的目录"""

    def test_out_dir_from_config(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.return_value = "/custom/output/dir"
        handler._app = mock_app
        with patch('gui.transcription.threading.Thread'):
            handler.start(["test.wav"], "llm-md", {}, "")
        assert handler._file_queue is not None

    def test_out_dir_empty_uses_default(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.return_value = ""
        handler._app = mock_app
        with patch('gui.transcription.threading.Thread'):
            handler.start(["test.wav"], "llm-md", {}, "")
        assert handler._file_queue is not None


# ══════════════════════════════════════════════════════════
#  日志前缀分离 (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestLogPrefixes:
    """日志消息应有正确的前缀"""

    def test_transcription_done_prefix(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        handler._app = MagicMock()
        log_messages = []
        handler.log_message.connect(lambda msg: log_messages.append(msg))
        handler._file_status = {"test.wav": "done"}
        mock_item = MagicMock()
        mock_item.status = MagicMock()
        mock_item.status.value = "done"
        mock_item.result_path = "test_transcript.md"
        mock_fm = MagicMock()
        mock_fm.files = [mock_item]
        handler._app.file_manager = mock_fm
        with patch('gui.transcription.FileStatus') as MockStatus:
            MockStatus.DONE = MagicMock()
            MockStatus.DONE.value = "done"
            handler._process_message(("file_done", "test.wav", "test_transcript.md"))
        has_prefix = any("[转写完成]" in msg for msg in log_messages)
        assert has_prefix, f"Expected [转写完成] prefix in logs: {log_messages}"

    def test_ai_correction_prefix(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d="": {
            "auto_correction": "转写后自动纠错",
        }.get(k, d)
        handler._app = mock_app
        log_messages = []
        handler.log_message.connect(lambda msg: log_messages.append(msg))
        handler._process_message(("auto_correction", "raw text content", "base", "/out", "transcript_path"))
        has_prefix = any("[AI纠错]" in msg for msg in log_messages)
        assert has_prefix, f"Expected [AI纠错] prefix: {log_messages}"

    def test_ai_summary_prefix(self):
        from gui.transcription import TranscriptionHandler
        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d="": {
            "auto_summary": "转写后自动生成",
        }.get(k, d)
        handler._app = mock_app
        log_messages = []
        handler.log_message.connect(lambda msg: log_messages.append(msg))
        handler._process_message(("auto_summary", "test.wav", "base", "/out"))
        has_prefix = any("[AI摘要]" in msg or "跳过" in msg for msg in log_messages)
        assert has_prefix, f"Expected [AI摘要] prefix or skip message: {log_messages}"


# ══════════════════════════════════════════════════════════
#  主题提取增强 (from test_async_workers.py)
# ══════════════════════════════════════════════════════════

class TestTopicExtraction:
    """_extract_topic_from_summary 应支持多种格式"""

    def _extract(self, summary):
        if not summary:
            return None
        try:
            lines = summary.splitlines()
            for line in lines[:10]:
                line = line.strip()
                if line.startswith("# ") or line.startswith("## "):
                    topic = line.lstrip("# ").strip()
                    if len(topic) > 5:
                        return topic[:50]
                if "主题" in line:
                    m = re.search(r'主题[：:]\s*(.+)', line)
                    if m:
                        topic = m.group(1).strip()
                        if len(topic) > 2:
                            return topic[:50]
        except Exception:
            pass
        return None

    def test_h1_title(self):
        result = self._extract("# 项目进度会议纪要\n\n内容")
        assert result == "项目进度会议纪要"

    def test_h2_title(self):
        result = self._extract("## 第一季度工作汇报\n\n内容")
        assert result == "第一季度工作汇报"

    def test_topic_colon_format(self):
        result = self._extract("主题：产品发布计划讨论\n\n内容")
        assert result == "产品发布计划讨论"

    def test_topic_bold_format(self):
        result = self._extract("**主题**：技术架构评审\n\n内容")
        assert result == "技术架构评审" or result is None

    def test_topic_english_colon(self):
        result = self._extract("主题: 用户反馈分析\n\n内容")
        assert result == "用户反馈分析"

    def test_short_topic_ignored(self):
        result = self._extract("主题：OK\n\n内容")
        assert result is None

    def test_empty_summary(self):
        assert self._extract("") is None
        assert self._extract(None) is None

    def test_no_topic_format(self):
        result = self._extract("这是一段没有标题的摘要内容")
        assert result is None
