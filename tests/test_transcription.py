"""
转写功能测试
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestTranscription:
    """转写相关测试"""

    def test_transcriber_class_exists(self):
        """测试 Transcriber 类存在"""
        from transcriber import Transcriber
        assert Transcriber is not None

    def test_transcriber_has_transcribe_staged(self):
        """测试 Transcriber 有 transcribe_staged 方法"""
        from transcriber import Transcriber
        assert hasattr(Transcriber, 'transcribe_staged')

    def test_transcriber_has_ensure_wav(self):
        """测试 Transcriber 有 _ensure_wav 方法"""
        from transcriber import Transcriber
        assert hasattr(Transcriber, '_ensure_wav')

    def test_transcriber_has_check_wav_format(self):
        """测试 Transcriber 有 _check_wav_format 方法"""
        from transcriber import Transcriber
        assert hasattr(Transcriber, '_check_wav_format')

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

    def test_transcription_handler_exists(self):
        """测试 TranscriptionHandler 类存在"""
        from gui.transcription import TranscriptionHandler
        assert TranscriptionHandler is not None

    def test_transcription_handler_has_poll(self):
        """测试 TranscriptionHandler 有 _poll 方法"""
        from gui.transcription import TranscriptionHandler
        assert hasattr(TranscriptionHandler, '_poll')

    def test_transcribe_worker_import(self):
        """测试 transcribe_worker 可以导入"""
        from transcribe_worker import transcribe_worker_process
        assert transcribe_worker_process is not None


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

    def test_get_ai_service_forwards_ollama_config(self):
        handler = self._create_handler()
        with patch('ai_service.AIService') as MockAIService:
            handler._get_ai_service()
            assert MockAIService.called
            _, kwargs = MockAIService.call_args
            assert kwargs.get("ollama_url") == "http://host:1234/v1"
            assert kwargs.get("ollama_model") == "llama3"
