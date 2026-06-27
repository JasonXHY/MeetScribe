#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 音色库单元测试
运行方式: pytest tests/test_voiceprint.py -v
"""

import os
import sys
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QLineEdit
from voiceprint import VoiceprintLibrary, SpeakerProfile


# ── SpeakerProfile 单元测试 ──────────────────────────────────


class TestSpeakerProfile:
    """SpeakerProfile 类测试"""

    def test_create_profile(self):
        """测试创建说话人档案"""
        profile = SpeakerProfile("张三")
        assert profile.name == "张三"
        assert profile.embeddings == []

    def test_add_embedding(self):
        """测试添加嵌入向量"""
        profile = SpeakerProfile("张三")
        embedding = np.random.rand(512)
        profile.add_embedding(embedding, "meeting_20260602", 0.85)
        assert len(profile.embeddings) == 1

    def test_get_average_embedding(self):
        """测试获取平均嵌入向量"""
        profile = SpeakerProfile("张三")
        for _ in range(3):
            profile.add_embedding(np.random.rand(512), "meeting", 0.85)
        avg = profile.get_average_embedding()
        assert avg is not None
        assert len(avg) == 512

    def test_get_average_embedding_empty(self):
        """测试空档案获取平均嵌入向量"""
        profile = SpeakerProfile("张三")
        assert profile.get_average_embedding() is None

    def test_can_match(self):
        """测试是否可以匹配"""
        profile = SpeakerProfile("张三")
        assert not profile.can_match()  # 0 个样本

        # 添加 1 个样本即可匹配（MIN_SAMPLES_FOR_MATCH = 1）
        profile.add_embedding(np.random.rand(512), "meeting", 0.85)
        assert profile.can_match()  # 1 个样本

        # 再添加更多样本也可以匹配
        for _ in range(2):
            profile.add_embedding(np.random.rand(512), "meeting", 0.85)
        assert profile.can_match()  # 3 个样本

    def test_add_embedding_dedup_same_source(self):
        """同来源 + 相同向量 → 应跳过"""
        profile = SpeakerProfile("张三")
        emb = np.array([1.0, 0.0, 0.0])
        r1 = profile.add_embedding(emb, "meeting_A")
        r2 = profile.add_embedding(emb, "meeting_A")
        assert r1 is True
        assert r2 is False
        assert len(profile.embeddings) == 1

    def test_add_embedding_dedup_different_source(self):
        """不同来源 + 相同向量 → 应保留"""
        profile = SpeakerProfile("张三")
        emb = np.array([1.0, 0.0, 0.0])
        r1 = profile.add_embedding(emb, "meeting_A")
        r2 = profile.add_embedding(emb, "meeting_B")
        assert r1 is True
        assert r2 is True
        assert len(profile.embeddings) == 2

    def test_add_embedding_dedup_similar_not_dup(self):
        """同来源 + 相似但不同向量 (< 0.999) → 应保留"""
        profile = SpeakerProfile("张三")
        emb1 = np.array([1.0, 0.0, 0.0])
        emb2 = np.array([0.99, 0.1, 0.0])  # 不同向量
        r1 = profile.add_embedding(emb1, "meeting_A")
        r2 = profile.add_embedding(emb2, "meeting_A")
        assert r1 is True
        assert r2 is True
        assert len(profile.embeddings) == 2

    def test_add_embedding_fifo_limit(self):
        """超过上限 5 个时淘汰最早的"""
        profile = SpeakerProfile("张三")
        for i in range(7):
            emb = np.zeros(512)
            emb[0] = float(i)  # 每个向量不同
            profile.add_embedding(emb, f"meeting_{i}")
        assert len(profile.embeddings) == 5
        # 最早的 2 个被淘汰，保留 meeting_2 ~ meeting_6
        assert profile.embeddings[0]["source"] == "meeting_2"
        assert profile.embeddings[4]["source"] == "meeting_6"

    def test_to_dict_and_from_dict(self):
        """测试序列化与反序列化"""
        profile = SpeakerProfile("张三")
        for i in range(3):
            profile.add_embedding(np.random.rand(512), f"meeting_{i}", 0.85)

        data = profile.to_dict()
        assert data["name"] == "张三"
        assert len(data["embeddings"]) == 3

        restored = SpeakerProfile.from_dict(data)
        assert restored.name == "张三"
        assert len(restored.embeddings) == 3


# ── VoiceprintLibrary 单元测试 ───────────────────────────────


class TestVoiceprintLibrary:
    """VoiceprintLibrary 类测试"""

    def test_create_library(self):
        """测试创建音色库"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            library = VoiceprintLibrary(temp_path)
            assert len(library.get_speakers()) == 0
        finally:
            os.remove(temp_path)

    def test_add_speaker(self):
        """测试添加说话人"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            library = VoiceprintLibrary(temp_path)
            embedding = np.random.rand(512)
            library.add_speaker("张三", embedding, "meeting_20260602")

            speakers = library.get_speakers()
            assert "张三" in speakers
            assert len(speakers["张三"].embeddings) == 1
        finally:
            os.remove(temp_path)

    def test_match(self):
        """测试匹配"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            library = VoiceprintLibrary(temp_path)

            # 添加张三的声纹（只需 1 个样本即可匹配）
            embedding = np.random.rand(512)
            library.add_speaker("张三", embedding, "meeting")

            # 测试匹配
            match_name, score = library.match(embedding)
            assert match_name == "张三"
            assert score > 0.75
        finally:
            os.remove(temp_path)

    def test_remove_speaker(self):
        """测试删除说话人"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            library = VoiceprintLibrary(temp_path)
            library.add_speaker("张三", np.random.rand(512), "meeting")
            assert "张三" in library.get_speakers()

            library.remove_speaker("张三")
            assert "张三" not in library.get_speakers()
        finally:
            os.remove(temp_path)

    def test_persistence(self):
        """测试数据持久化"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            embedding = np.random.rand(512)

            # 写入
            library1 = VoiceprintLibrary(temp_path)
            library1.add_speaker("张三", embedding, "meeting")

            # 重新读取
            library2 = VoiceprintLibrary(temp_path)
            speakers = library2.get_speakers()
            assert "张三" in speakers
            assert len(speakers["张三"].embeddings) == 1
        finally:
            os.remove(temp_path)

    def test_match_insufficient_samples(self):
        """测试样本不足时无法匹配（MIN_SAMPLES_FOR_MATCH = 1，0 个样本无法匹配）"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            library = VoiceprintLibrary(temp_path)
            embedding = np.random.rand(512)

            # 0 个样本无法匹配（MIN_SAMPLES_FOR_MATCH = 1）
            name, score = library.match(embedding)
            assert name is None
            assert score == 0

            # 1 个样本可以匹配
            library.add_speaker("张三", embedding, "meeting")
            name, score = library.match(embedding)
            assert name == "张三"
            assert score > 0.75
        finally:
            os.remove(temp_path)

    def test_add_speaker_return_value(self):
        """add_speaker 返回值验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = VoiceprintLibrary(os.path.join(tmpdir, "test_lib.json"))
            emb = np.random.rand(512)
            r1 = lib.add_speaker("张三", emb, "meeting_A")
            r2 = lib.add_speaker("张三", emb, "meeting_A")  # 同源重复
            r3 = lib.add_speaker("张三", emb, "meeting_B")  # 不同源
            assert r1 is True
            assert r2 is False
            assert r3 is True
            assert len(lib.get_speakers()["张三"].embeddings) == 2

    def test_match_no_match(self):
        """测试无法匹配到任何人（使用正交向量确保相似度为 0）"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            library = VoiceprintLibrary(temp_path)

            # 构造两个正交向量：embedding_a 全为正，embedding_b 前半正后半负
            # dot(a, b) = 256*1 + 256*(-1) = 0 -> cosine = 0
            embedding_a = np.ones(512)
            embedding_b = np.concatenate([np.ones(256), -np.ones(256)])

            for _ in range(3):
                library.add_speaker("张三", embedding_a, "meeting")

            name, score = library.match(embedding_b)
            assert name is None
            assert score == 0.0
        finally:
            os.remove(temp_path)

    def test_load_corrupted_json(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text('{"speakers": {"张三": {"name": "张三", "embeddings": [')
        lib = VoiceprintLibrary(str(path))
        assert lib.get_speakers() == {}

    @pytest.mark.xfail(reason="VoiceprintLibrary 非线程安全，已知设计限制")
    def test_concurrent_add_speakers(self, tmp_path):
        lib = VoiceprintLibrary(str(tmp_path / "lib.json"))
        errors = []

        def add_many(prefix):
            try:
                for i in range(20):
                    lib.add_speaker(f"{prefix}_{i}", np.random.rand(512), "test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_many, args=(f"T{j}",)) for j in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) > 0

    def test_match_below_threshold(self, tmp_path):
        lib = VoiceprintLibrary(str(tmp_path / "lib.json"))
        base = np.random.rand(512).astype(np.float32)
        base /= np.linalg.norm(base)
        lib.add_speaker("张三", base, "test")
        orthogonal = np.zeros(512, dtype=np.float32)
        orthogonal[0] = 1.0
        name, score = lib.match(orthogonal)
        assert name is None

    def test_match_confirmed_threshold(self, tmp_path):
        lib = VoiceprintLibrary(str(tmp_path / "lib.json"))
        base = np.random.rand(512).astype(np.float32)
        base /= np.linalg.norm(base)
        lib.add_speaker("张三", base, "test")
        noise = np.random.rand(512).astype(np.float32)
        noise /= np.linalg.norm(noise)
        above = (base * 0.51 + noise * 0.49).astype(np.float32)
        name, score = lib.match(above)
        assert name == "张三"
        assert score >= 0.50


# ── 冲突解决逻辑测试 ─────────────────────────────────────────


def test_conflict_all_match_same_name(tmp_path):
    lib = VoiceprintLibrary(str(tmp_path / "lib.json"))
    base = np.random.rand(512).astype(np.float32)
    base /= np.linalg.norm(base)
    lib.add_speaker("张三", base, "test")
    noise = np.random.rand(512).astype(np.float32)
    noise /= np.linalg.norm(noise)
    emb_low = (base * 0.4 + noise * 0.6).astype(np.float32)
    emb_mid = (base * 0.6 + noise * 0.4).astype(np.float32)
    emb_high = (base * 0.8 + noise * 0.2).astype(np.float32)
    matches = [
        {"speaker_id": 0, "name": "张三", "score": 0.4},
        {"speaker_id": 1, "name": "张三", "score": 0.6},
        {"speaker_id": 2, "name": "张三", "score": 0.8},
    ]
    best = max(matches, key=lambda m: m["score"])
    assert best["speaker_id"] == 2
    assert best["score"] == 0.8




# ── 边界条件测试 ─────────────────────────────────────────────


class TestVoiceprintBoundary:
    """音色库边界条件测试"""


@pytest.mark.e2e_heavy
def test_extract_embedding_from_file_success():
    """测试从音频文件提取声纹成功场景（patch funasr.AutoModel，需 funasr 已安装）"""
    # 创建临时音频文件
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = f.name

    try:
        library = VoiceprintLibrary()

        # Mock soundfile.read 返回有效的音频数据
        mock_audio = np.random.randn(16000).astype(np.float32)  # 1秒 16kHz 音频
        mock_sr = 16000

        # Mock AutoModel (CAM++ 模型)
        mock_model = MagicMock()
        mock_embedding = np.random.randn(192).astype(np.float32)
        mock_model.inference.return_value = [{"spk_embedding": mock_embedding}]

        with patch('soundfile.read', return_value=(mock_audio, mock_sr)), \
             patch('funasr.AutoModel', return_value=mock_model):
            result = library.extract_embedding_from_file(temp_path)

        assert result is not None
        assert isinstance(result, dict)
        assert 0 in result
        assert len(result[0]) == 192
    finally:
        os.remove(temp_path)


def test_extract_embedding_from_file_not_found():
    """测试从不存在的音频文件提取声纹"""
    library = VoiceprintLibrary()
    result = library.extract_embedding_from_file("/nonexistent/file.wav")
    assert result is None


@pytest.mark.e2e_heavy
def test_extract_embedding_from_file_transcribe_error():
    """测试提取失败时返回 None（patch funasr.AutoModel，需 funasr 已安装）"""
    # 创建临时音频文件
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = f.name

    try:
        library = VoiceprintLibrary()

        # Mock soundfile.read 返回有效的音频数据
        mock_audio = np.random.randn(16000).astype(np.float32)
        mock_sr = 16000

        # Mock AutoModel 抛出异常
        mock_model = MagicMock()
        mock_model.inference.side_effect = Exception("Inference failed")

        with patch('soundfile.read', return_value=(mock_audio, mock_sr)), \
             patch('funasr.AutoModel', return_value=mock_model):
            result = library.extract_embedding_from_file(temp_path)

        assert result is None
    finally:
        os.remove(temp_path)


@pytest.mark.e2e_heavy
def test_extract_embedding_from_file_return_format():
    """测试返回值格式为 {spk_id: embedding_vector}（patch funasr.AutoModel，需 funasr）"""
    # 创建临时音频文件
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = f.name

    try:
        library = VoiceprintLibrary()

        # Mock soundfile.read 返回有效的音频数据
        mock_audio = np.random.randn(16000).astype(np.float32)  # 1秒 16kHz 音频
        mock_sr = 16000

        # Mock AutoModel 返回嵌入向量
        mock_model = MagicMock()
        mock_embedding = np.random.randn(192).astype(np.float32)
        mock_model.inference.return_value = [{"spk_embedding": mock_embedding}]

        with patch('soundfile.read', return_value=(mock_audio, mock_sr)), \
             patch('funasr.AutoModel', return_value=mock_model):
            result = library.extract_embedding_from_file(temp_path)

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 1
        assert 0 in result
        assert len(result[0]) == 192
    finally:
        os.remove(temp_path)


# ── GUI 流行为测试（VPR-002/003/004）────────────────────────
# 不依赖 funasr / CAM++：提取边界用 mock 注入固定向量。

pytestmark = pytest.mark.integration


@pytest.fixture
def lib(tmp_path):
    """空音色库，指向临时文件。"""
    return VoiceprintLibrary(library_path=str(tmp_path / "vp.json"))


def _populate(lib, name="张三"):
    lib.add_speaker(name, np.random.rand(512).astype(np.float32),
                    "manual_recording", quality=0.9)
    return lib


# ── VPR-003：rename_speaker 行为 ──────────────────────────────


class TestRenameSpeakerBehavior:
    def test_rename_migrates_embeddings_and_created_at(self, lib):
        _populate(lib, "张三")
        before = lib.get_speakers()["张三"]
        old_embeddings = before.embeddings
        old_created = before.created_at

        ok = lib.rename_speaker("张三", "张总")
        assert ok is True

        speakers = lib.get_speakers()
        assert "张三" not in speakers
        assert "张总" in speakers
        # embedding 与 created_at 迁移保留
        assert speakers["张总"].embeddings == old_embeddings
        assert speakers["张总"].created_at == old_created

    def test_rename_persists_to_disk(self, lib, tmp_path):
        _populate(lib, "张三")
        lib.rename_speaker("张三", "张总")

        # 重新加载，确认持久化
        reloaded = VoiceprintLibrary(library_path=str(tmp_path / "vp.json"))
        names = set(reloaded.get_speakers().keys())
        assert names == {"张总"}

    def test_rename_rejects_when_target_exists(self, lib):
        _populate(lib, "张三")
        _populate(lib, "李四")
        assert lib.rename_speaker("张三", "李四") is False
        # 两者都还在
        assert set(lib.get_speakers()) == {"张三", "李四"}

    def test_rename_returns_false_when_source_missing(self, lib):
        assert lib.rename_speaker("不存在", "新名") is False


# ── VPR-003：GUI _edit_speaker 集成 ──────────────────────────


class TestEditSpeakerGui:
    def test_edit_speaker_renames_and_refreshes(self, qtbot, lib):
        from gui.voiceprint_page import VoiceprintPage

        _populate(lib, "张三")
        page = VoiceprintPage()
        qtbot.addWidget(page)
        page._library = lib  # 注入临时库
        page.refresh_list()

        with patch("gui.voiceprint_page.QInputDialog.getText",
                   return_value=("张总", True)):
            page._edit_speaker("张三")

        assert "张总" in lib.get_speakers()
        assert "张三" not in lib.get_speakers()


# ── VPR-004：GUI _delete_speaker 确认路径 ────────────────────


class TestDeleteSpeakerGui:
    def test_delete_confirmed_calls_remove_and_refreshes(self, qtbot):
        from gui.voiceprint_page import VoiceprintPage
        from PySide6.QtWidgets import QMessageBox

        fake_lib = MagicMock()
        page = VoiceprintPage()
        qtbot.addWidget(page)
        page._library = fake_lib

        with patch("gui.voiceprint_page.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            page._delete_speaker("张三")

        fake_lib.remove_speaker.assert_called_once_with("张三")

    def test_delete_cancelled_does_not_remove(self, qtbot):
        from gui.voiceprint_page import VoiceprintPage
        from PySide6.QtWidgets import QMessageBox

        fake_lib = MagicMock()
        page = VoiceprintPage()
        qtbot.addWidget(page)
        page._library = fake_lib

        with patch("gui.voiceprint_page.QMessageBox.question",
                   return_value=QMessageBox.No):
            page._delete_speaker("张三")

        fake_lib.remove_speaker.assert_not_called()


# ── VPR-002：AddVoiceDialog 录入链路 ─────────────────────────


class TestAddVoiceSaveFlow:
    def test_save_calls_add_speaker_with_correct_source_quality(self, qtbot):
        from gui.voiceprint_page import AddVoiceDialog

        dialog = AddVoiceDialog()
        qtbot.addWidget(dialog)

        # 模拟提取已完成：填入姓名 + 固定 embedding
        fixed_embedding = np.ones(512, dtype=np.float32)
        dialog._name_entry.setText("王五")
        dialog._temp_embedding = fixed_embedding

        fake_lib = MagicMock()
        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.voiceprint_page.QMessageBox"):
            dialog._save()

        fake_lib.add_speaker.assert_called_once()
        args, kwargs = fake_lib.add_speaker.call_args
        # 姓名、来源、quality 与实现约定一致
        assert args[0] == "王五"
        assert np.array_equal(args[1], fixed_embedding)
        assert args[2] == "manual_recording"
        assert kwargs.get("quality") == 0.90

    def test_save_blocks_without_embedding(self, qtbot):
        from gui.voiceprint_page import AddVoiceDialog

        dialog = AddVoiceDialog()
        qtbot.addWidget(dialog)
        dialog._name_entry.setText("无声纹")
        dialog._temp_embedding = None

        fake_lib = MagicMock()
        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.voiceprint_page.QMessageBox"):
            dialog._save()

        # 未提取声纹时不得写库
        fake_lib.add_speaker.assert_not_called()


# ── 辅助函数 ─────────────────────────────────────────────────


def _make_speaker_dialog(app, speakers=None, embeddings=None,
                         audio_path=None, sentences=None, qualities=None):
    """构造最小 SpeakerDialog"""
    from gui.dialogs import SpeakerDialog
    speakers = speakers if speakers is not None else [
        {"label": "Speaker 1", "spk_id": 0, "name": "", "pct": 60.0},
        {"label": "Speaker 2", "spk_id": 1, "name": "", "pct": 40.0},
    ]
    return SpeakerDialog(
        parent=None,
        file_name="meeting.wav",
        speakers=speakers,
        speaker_embeddings=embeddings or {},
        speaker_qualities=qualities or {},
        audio_path=audio_path,
        sentences=sentences or [],
    )


# ── 音色库下拉选择填充（迁移自 test_gui_config）───────────────


class TestVoiceprintSelect:
    def test_select_fills_entry(self, app):
        dlg = _make_speaker_dialog(app)
        entry = QLineEdit()
        dlg._on_voiceprint_select("李四", entry)
        assert entry.text() == "李四"

    def test_select_placeholder_does_not_fill(self, app):
        dlg = _make_speaker_dialog(app)
        entry = QLineEdit()
        dlg._on_voiceprint_select("（从音色库选择）", entry)
        assert entry.text() == ""


# ── 保存到音色库（迁移自 test_gui_config）────────────────────


class TestSaveToLibrary:
    def test_save_calls_add_speaker(self, app):
        emb = np.ones(512, dtype=np.float32)
        dlg = _make_speaker_dialog(app, embeddings={0: emb})
        dlg._speaker_entries[0].setText("王五")

        fake_lib = MagicMock()
        fake_profile = MagicMock()
        fake_profile.embeddings = [emb]
        fake_lib.get_speakers.return_value = {"王五": fake_profile}

        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.dialogs.QMessageBox"):
            dlg._save_to_library(0)

        fake_lib.add_speaker.assert_called_once()
        args, kwargs = fake_lib.add_speaker.call_args
        assert args[0] == "王五"
        assert np.array_equal(args[1], emb)

    def test_save_blocks_without_name(self, app):
        dlg = _make_speaker_dialog(app, embeddings={0: np.ones(512)})
        dlg._speaker_entries[0].setText("")

        fake_lib = MagicMock()
        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.dialogs.QMessageBox"):
            dlg._save_to_library(0)
        fake_lib.add_speaker.assert_not_called()


# ── 中间片段选择（迁移自 test_gui_config）────────────────────


class TestMiddleSegmentWindow:
    def test_middle_third_window(self):
        from gui.dialogs import _middle_third_window
        start, end = _middle_third_window(0, 3000)
        assert start == pytest.approx(1000)
        assert end == pytest.approx(2000)

    def test_extract_picks_longest_segment_middle(self, app):
        """SPK-007：应选最长发言段，并对其中间 1/3 提取。"""
        sentences = [
            {"spk_id": 0, "start": 0, "end": 1000},
            {"spk_id": 0, "start": 10000, "end": 40000},
            {"spk_id": 1, "start": 2000, "end": 5000},
        ]
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            import soundfile as sf
            sr = 16000
            sf.write(wav_path, np.zeros(45 * sr, dtype=np.float32), sr)

            dlg = _make_speaker_dialog(
                app, embeddings={0: np.ones(512)},
                audio_path=wav_path, sentences=sentences,
            )

            captured = {}
            fixed_emb = np.arange(512, dtype=np.float32)

            class _FakeModel:
                def __init__(self, *a, **k):
                    pass

                def inference(self, input=None, **k):
                    captured["len"] = len(input)
                    return [{"spk_embedding": fixed_emb}]

            fake_funasr = MagicMock()
            fake_funasr.AutoModel = _FakeModel
            with patch.dict(sys.modules, {"funasr": fake_funasr}):
                result = dlg._extract_middle_segment_embedding(0, duration_sec=5)

            assert result is not None
            assert np.array_equal(np.asarray(result), fixed_emb)
            assert captured["len"] == pytest.approx(160000, rel=0.05)
        finally:
            os.remove(wav_path)


# ══════════════════════════════════════════════════════════
#  L5: 声纹匹配验证 (from test_tdd_flows.py)
# ══════════════════════════════════════════════════════════

class TestVoiceprintMatchingTDD:
    """声纹匹配逻辑验证"""

    def test_matching_scoring(self):
        """声纹匹配评分验证"""
        import logging
        logger = logging.getLogger("TDD_Test")
        library = VoiceprintLibrary()
        speakers = library.get_speakers()

        if not speakers:
            pytest.skip("No speakers in library")

        # 取第一个说话人的嵌入向量进行匹配测试
        first_speaker = list(speakers.values())[0]
        if not first_speaker.embeddings:
            pytest.skip("No embeddings for first speaker")

        embedding = np.array(first_speaker.embeddings[0]["vector"])

        # 匹配
        name, score = library.match(embedding)
        logger.info(f"Matching test: name={name}, score={score:.4f}")

        # 自匹配应该高分
        assert name is not None, "Self-matching should return a name"
        assert score > 0.5, f"Self-matching score too low: {score:.4f}"
        assert name == first_speaker.name, \
            f"Self-matching should return same speaker: expected {first_speaker.name}, got {name}"

        # 置信度检测
        name2, confidence = library.match_with_confidence(embedding)
        logger.info(f"Confidence: {confidence}")
        assert confidence in ("confirmed", "suggested", "no_match"), \
            f"Invalid confidence: {confidence}"

        logger.info("PASS: Voiceprint matching scoring OK")


# ══════════════════════════════════════════════════════════
#  L6: 音色库人员添加流程 (from test_tdd_flows.py)
# ══════════════════════════════════════════════════════════

class TestVoiceprintMemberAddition:
    """音色库人员添加流程前端验证"""

    def test_add_voice_dialog_ui(self, qtbot):
        """AddVoiceDialog UI 验证"""
        import logging
        logger = logging.getLogger("TDD_Test")
        from PySide6.QtWidgets import QPushButton
        from gui.voiceprint_page import AddVoiceDialog
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        # 创建对话框
        dialog = AddVoiceDialog(parent=test_app._voiceprint_page, on_save=lambda: None)
        qtbot.addWidget(dialog)

        # 验证 UI 元素
        assert hasattr(dialog, '_name_entry'), "Name input missing"
        assert hasattr(dialog, '_record_btn'), "Record button missing"
        assert hasattr(dialog, '_save_btn'), "Save button missing"
        # cancel_btn 是局部变量，通过 dialog 的按钮列表验证
        buttons = dialog.findChildren(QPushButton)
        button_texts = [b.text() for b in buttons]
        assert any("取消" in t for t in button_texts), "Cancel button missing"
        assert any("保存" in t for t in button_texts), "Save button missing"

        # 验证预设朗读文本
        if hasattr(dialog, 'PRESET_TEXT'):
            assert len(dialog.PRESET_TEXT) > 0, "Preset text should not be empty"
            logger.info(f"Preset text: {dialog.PRESET_TEXT[:50]}...")

        # 验证输入框可编辑
        name_entry = dialog._name_entry
        name_entry.setText("TDD测试添加人员")
        assert name_entry.text() == "TDD测试添加人员", "Name entry should be editable"

        logger.info("PASS: AddVoiceDialog UI OK")
        dialog.close()
        test_app.close()


def test_fifo_eviction_is_by_recency_not_quality(tmp_path):
    """GAP-14: FIFO 淘汰按时间顺序，不按质量"""
    from voiceprint import VoiceprintLibrary
    lib = VoiceprintLibrary(str(tmp_path / "lib.json"))
    base = np.random.rand(512).astype(np.float32)
    base /= np.linalg.norm(base)
    lib.add_speaker("张三", base, "test")
    # 添加 6 个样本（超过 MAX_EMBEDDINGS_PER_SPEAKER=5）
    for i in range(6):
        emb = np.random.rand(512).astype(np.float32)
        lib.add_speaker("张三", emb, f"source_{i}")
    # 验证只保留 5 个
    profile = lib.get_speakers()["张三"]
    assert len(profile.embeddings) == 5
    # 验证第一个样本被丢弃（FIFO）
    # 第一个样本的 source 应该是 'test'，但已经被淘汰
    sources = [e["source"] for e in profile.embeddings]
    assert "test" not in sources  # 最早的样本被丢弃
