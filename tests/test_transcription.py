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
        mock_library.match_with_confidence.return_value = ("张三", "confirmed")

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
        mock_library.match_with_confidence.return_value = ("张三", "suggested")

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
        mock_library.match_with_confidence.return_value = (None, "no_match")

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
        mock_library.match_with_confidence.return_value = ("张三", "confirmed")
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
