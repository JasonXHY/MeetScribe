#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 音色库单元测试
运行方式: pytest tests/test_voiceprint.py -v
"""

import os
import tempfile

import numpy as np
import pytest
from voiceprint import VoiceprintLibrary, SpeakerProfile


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


def test_extract_embedding_from_file():
    """测试从音频文件提取声纹"""
    from voiceprint import VoiceprintLibrary
    import tempfile
    import os

    # 创建临时音频文件（模拟）
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = f.name

    try:
        library = VoiceprintLibrary()
        # 这个方法应该存在但可能失败（因为没有真实音频）
        assert hasattr(library, 'extract_embedding_from_file')
    finally:
        os.remove(temp_path)


@pytest.mark.e2e_heavy
def test_extract_embedding_from_file_success():
    """测试从音频文件提取声纹成功场景（patch funasr.AutoModel，需 funasr 已安装）"""
    from voiceprint import VoiceprintLibrary
    from unittest.mock import patch, MagicMock
    import tempfile
    import os
    import numpy as np

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
    from voiceprint import VoiceprintLibrary

    library = VoiceprintLibrary()
    result = library.extract_embedding_from_file("/nonexistent/file.wav")
    assert result is None


@pytest.mark.e2e_heavy
def test_extract_embedding_from_file_transcribe_error():
    """测试提取失败时返回 None（patch funasr.AutoModel，需 funasr 已安装）"""
    from voiceprint import VoiceprintLibrary
    from unittest.mock import patch, MagicMock
    import tempfile
    import os
    import numpy as np

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
    from voiceprint import VoiceprintLibrary
    from unittest.mock import patch, MagicMock
    import tempfile
    import os
    import numpy as np

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
