"""
说话人姓名提取（AI-003）测试

覆盖：
- SpeakerNamer 正则路径（纯函数，不依赖 funasr）
- SpeakerNamer 在转写后处理管线中被实际调用（mock AIService，mock 文件 IO）

运行：
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_speaker_namer.py -p no:cacheprovider
"""

import pytest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════
#  单元测试：正则提取路径
# ══════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestExtractNamesRegex:
    """SpeakerNamer.extract_names_regex 正则路径"""

    def _namer(self):
        from speaker_namer import SpeakerNamer
        return SpeakerNamer()

    def test_self_intro_wo_shi(self):
        """'我是张三' 自报姓名"""
        transcript = "[00:00:01] Speaker 1: 大家好，我是张三，负责本次会议记录。"
        result = self._namer().extract_names_regex(transcript, ["1"])
        assert result.get("1") == "张三"

    def test_self_intro_jiao(self):
        """'大家好我叫王五'"""
        transcript = "[00:00:05] Speaker 2: 大家好，我叫王五。"
        result = self._namer().extract_names_regex(transcript, ["2"])
        assert result.get("2") == "王五"

    def test_title_reference(self):
        """他人称呼 'X老师/X部长' 这类带称呼线索"""
        transcript = (
            "[00:00:01] Speaker 3: 这个问题请李四老师来回答。\n"
            "[00:00:08] Speaker 4: 好的，我来说一下。李四老师讲得很对。\n"
        )
        result = self._namer().extract_names_regex(transcript, ["3", "4"])
        # 任意一行能匹配到 "李四" 即可（带或不带称呼后缀）
        names = set(result.values())
        assert any("李四" in n for n in names)

    def test_multiple_speakers(self):
        """多个说话人各自被识别"""
        transcript = (
            "[00:00:01] Speaker 1: 我是张三。\n"
            "[00:00:05] Speaker 2: 我叫王五。\n"
        )
        result = self._namer().extract_names_regex(transcript, ["1", "2"])
        assert result.get("1") == "张三"
        assert result.get("2") == "王五"

    def test_no_cue_returns_empty(self):
        """没有任何姓名线索时返回空映射"""
        transcript = (
            "[00:00:01] Speaker 1: 我们今天讨论一下项目进度。\n"
            "[00:00:05] Speaker 2: 好的，没有问题。\n"
        )
        result = self._namer().extract_names_regex(transcript, ["1", "2"])
        assert result == {}

    def test_cue_without_matching_speaker_skipped(self):
        """线索行的说话人不在 speaker_ids 列表中时应跳过"""
        transcript = "[00:00:01] Speaker 9: 我是张三。"
        result = self._namer().extract_names_regex(transcript, ["1", "2"])
        assert result == {}

    def test_empty_transcript(self):
        """空文本返回空映射"""
        result = self._namer().extract_names_regex("", ["1"])
        assert result == {}


@pytest.mark.unit
class TestExtractNamesFallback:
    """SpeakerNamer.extract_names 正则 + LLM 兜底"""

    def _namer(self):
        from speaker_namer import SpeakerNamer
        return SpeakerNamer()

    def test_regex_hit_skips_llm(self):
        """正则全部命中时不调用 LLM"""
        transcript = "[00:00:01] Speaker 1: 我是张三。"
        ai = MagicMock()
        result = self._namer().extract_names(transcript, ["1"], ai_service=ai)
        assert result.get("1") == "张三"
        ai.extract_speaker_names.assert_not_called()

    def test_llm_fallback_when_regex_misses(self):
        """正则无果且有 ai_service 时走 LLM 兜底"""
        transcript = "[00:00:01] Speaker 1: 我们开始吧。"
        ai = MagicMock()
        ai.extract_speaker_names.return_value = {"1": "赵六"}
        result = self._namer().extract_names(transcript, ["1"], ai_service=ai)
        ai.extract_speaker_names.assert_called_once()
        assert result.get("1") == "赵六"

    def test_no_ai_service_safe_skip(self):
        """正则无果且无 ai_service 时安全跳过，不报错"""
        transcript = "[00:00:01] Speaker 1: 我们开始吧。"
        result = self._namer().extract_names(transcript, ["1"], ai_service=None)
        assert result == {}


# ══════════════════════════════════════════════════════════════════
#  集成测试：SpeakerNamer 接入转写后处理管线
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestSpeakerNamerWiring:
    """验证 transcription.py 后处理路径实际调用 SpeakerNamer"""

    def _handler(self):
        from gui.transcription import TranscriptionHandler
        from file_manager import FileStatus

        mock_app = MagicMock()
        handler = TranscriptionHandler(mock_app)

        mock_item = MagicMock()
        mock_item.status = FileStatus.DONE
        mock_item.result_path = "/tmp/out/meeting_transcript.md"
        mock_item.speaker_names = {}
        mock_item.file_path = "/tmp/meeting.wav"
        mock_item.file_name = "meeting.wav"
        handler._app.file_manager.files = [mock_item]
        handler._current_batch_paths = {"/tmp/meeting.wav"}
        return handler, mock_item

    def test_apply_speaker_names_method_exists(self):
        """管线提供 _apply_speaker_names 接口"""
        from gui.transcription import TranscriptionHandler
        assert hasattr(TranscriptionHandler, "_apply_speaker_names")

    def test_regex_names_applied_to_results(self):
        """正则提取到的姓名应用到结果文件与说话人映射"""
        handler, mock_item = self._handler()
        transcript = "[00:00:01] Speaker 1: 大家好，我是张三。"

        m = MagicMock()
        m.read_data = transcript
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", new_callable=lambda: _mock_open(transcript)), \
             patch("gui.transcription.apply_speaker_mapping") as mock_apply:
            handler._apply_speaker_names()

        # apply_speaker_mapping 被调用并包含 Speaker 1 -> 张三
        assert mock_apply.called
        applied = {}
        for call in mock_apply.call_args_list:
            applied.update(call.args[1])
        assert applied.get(1) == "张三" or applied.get("1") == "张三"
        # file_manager.update_speaker_names 被调用
        assert handler._app.file_manager.update_speaker_names.called

    def test_confirmed_voiceprint_not_overwritten(self):
        """已被声纹 confirmed 命名的说话人不被姓名提取覆盖"""
        handler, mock_item = self._handler()
        # Speaker 1（0 基 id=0）已被声纹 confirmed 命名为 李四
        handler._voiceprint_match_results = {0: {"name": "李四", "confidence": "confirmed"}}
        transcript = "[00:00:01] Speaker 1: 大家好，我是张三。"

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", new_callable=lambda: _mock_open(transcript)), \
             patch("gui.transcription.apply_speaker_mapping") as mock_apply:
            handler._apply_speaker_names()

        # 不应把 Speaker 1 改成 张三（confirmed 优先）
        applied = {}
        for call in mock_apply.call_args_list:
            applied.update(call.args[1])
        assert 1 not in applied and "1" not in applied

    def test_no_ai_service_safe_skip(self):
        """无 AI 服务且正则无果时安全跳过，不报错"""
        handler, mock_item = self._handler()
        handler._app.config.get.return_value = ""  # 无 api key -> _get_ai_service 返回 None
        transcript = "[00:00:01] Speaker 1: 我们开始吧。"

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", new_callable=lambda: _mock_open(transcript)), \
             patch("gui.transcription.apply_speaker_mapping") as mock_apply:
            # 不应抛异常
            handler._apply_speaker_names()

        # 无姓名可应用
        assert not mock_apply.called


def _mock_open(read_data):
    """构造一个可读可写的 open mock，read() 返回指定内容。"""
    from unittest.mock import mock_open
    return mock_open(read_data=read_data)
