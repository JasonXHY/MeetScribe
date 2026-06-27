#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 音色库模块
基于 CAM++ 声纹嵌入向量实现说话人识别
"""

import os
import json
import logging
import numpy as np
from datetime import datetime
from utils import get_data_dir

logger = logging.getLogger("MeetScribe")

# 匹配阈值
# 基于 CAM++ 官方示例测试结果：
# - 同一说话人不同录音相似度: ~0.69
# - 不同说话人相似度: ~0.00
# - 官方推荐阈值: 0.31（ModelScope 官方示例）
# - 直接使用官方推荐值
MATCH_THRESHOLD = 0.31
HIGH_CONFIDENCE = 0.50

# 每个说话人最多保留的嵌入向量数量（FIFO 淘汰）
MAX_EMBEDDINGS_PER_SPEAKER = 5

# 同源去重相似度阈值
DEDUP_THRESHOLD = 0.999

# 最低样本数（降低为 1，允许单次转写即可匹配）
MIN_SAMPLES_FOR_MATCH = 1

# 推荐录制内容
RECOMMENDED_RECORDING_SCRIPTS = [
    "你好，我是{name}，这是我的声纹样本。",
]


class SpeakerProfile:
    """说话人声纹档案"""

    def __init__(self, name):
        self.name = name
        self.embeddings = []  # [{"vector": [...], "source": "...", "quality": 0.85}]
        self.created_at = datetime.now().isoformat()
        self._avg_embedding = None

    def add_embedding(self, vector, source, quality=0.85):
        """添加声纹样本（带去重）

        Args:
            vector: 嵌入向量
            source: 来源标识（文件名或 "manual_recording"）
            quality: 质量分数 0~1

        Returns:
            True 已添加, False 重复跳过
        """
        new_vector = vector.tolist() if isinstance(vector, np.ndarray) else vector

        # 去重：同来源 + 余弦相似度 > DEDUP_THRESHOLD → 跳过
        for existing in self.embeddings:
            if existing["source"] != source:
                continue
            existing_vec = np.array(existing["vector"])
            new_vec = np.array(new_vector)
            if existing_vec.shape == new_vec.shape:
                similarity = np.dot(existing_vec, new_vec) / (
                    np.linalg.norm(existing_vec) * np.linalg.norm(new_vec) + 1e-8
                )
                if similarity > DEDUP_THRESHOLD:
                    logger.debug(f"跳过重复嵌入: source={source}, sim={similarity:.6f}")
                    return False

        self.embeddings.append({
            "vector": new_vector,
            "source": source,
            "quality": quality,
        })

        # 超过上限时淘汰最早的样本（FIFO）
        if len(self.embeddings) > MAX_EMBEDDINGS_PER_SPEAKER:
            removed = self.embeddings.pop(0)
            logger.debug(f"淘汰最早样本: source={removed['source']}, quality={removed['quality']}")

        self._avg_embedding = None
        return True

    def get_average_embedding(self):
        """获取平均声纹向量"""
        if self._avg_embedding is None:
            if not self.embeddings:
                return None
            vectors = [e["vector"] for e in self.embeddings]
            self._avg_embedding = np.mean(vectors, axis=0)
        return self._avg_embedding

    def get_weighted_embedding(self):
        """获取加权平均声纹向量（高质量样本权重更大）"""
        if not self.embeddings:
            return None
        vectors = [e["vector"] for e in self.embeddings]
        # 确保 quality > 0，避免零权重样本（防御脏数据）
        weights = [max(e.get("quality", 0.85), 0.01) for e in self.embeddings]
        return np.average(vectors, weights=weights, axis=0)

    def can_match(self):
        """是否可以进行匹配（至少需要 MIN_SAMPLES_FOR_MATCH 个样本）"""
        return len(self.embeddings) >= MIN_SAMPLES_FOR_MATCH

    def get_sample_count(self):
        """获取样本数量"""
        return len(self.embeddings)

    def to_dict(self):
        """转换为字典"""
        return {
            "name": self.name,
            "embeddings": self.embeddings,
            "created_at": self.created_at,
            "sample_count": len(self.embeddings),
        }

    @classmethod
    def from_dict(cls, data):
        """从字典创建"""
        profile = cls(data["name"])
        profile.embeddings = data.get("embeddings", [])
        profile.created_at = data.get("created_at", datetime.now().isoformat())
        return profile


class VoiceprintLibrary:
    """音色库管理器"""

    def __init__(self, library_path=None):
        self.library_path = library_path or os.path.join(
            get_data_dir(), "data", "voiceprint_library.json"
        )
        self._speakers = {}  # {name: SpeakerProfile}
        self._loaded = False

    def _ensure_loaded(self):
        """确保音色库已加载"""
        if not self._loaded:
            self._load_from_file()
            self._loaded = True

    def _load_from_file(self):
        """从文件加载音色库"""
        if not os.path.exists(self.library_path):
            self._speakers = {}
            return

        try:
            with open(self.library_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._speakers = {}
            for name, speaker_data in data.get("speakers", {}).items():
                self._speakers[name] = SpeakerProfile.from_dict(speaker_data)

            logger.info(f"Loaded voiceprint library: {len(self._speakers)} speakers")
        except Exception as e:
            logger.error(f"Failed to load voiceprint library: {e}")
            self._speakers = {}

    def _save_to_file(self):
        """保存音色库到文件"""
        os.makedirs(os.path.dirname(self.library_path), exist_ok=True)

        data = {
            "version": 1,
            "speakers": {name: profile.to_dict() for name, profile in self._speakers.items()},
        }

        try:
            with open(self.library_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved voiceprint library: {len(self._speakers)} speakers")
        except Exception as e:
            logger.error(f"Failed to save voiceprint library: {e}")

    def add_speaker(self, name, embedding, source, quality=0.85):
        """添加或更新说话人声纹（带去重）

        Returns:
            True 已添加, False 重复跳过
        """
        self._ensure_loaded()

        if name not in self._speakers:
            self._speakers[name] = SpeakerProfile(name)

        added = self._speakers[name].add_embedding(embedding, source, quality)
        if added:
            self._save_to_file()
            logger.info(f"Added embedding for {name} (total: {len(self._speakers[name].embeddings)})")
        else:
            logger.info(f"Skipped duplicate embedding for {name}")
        return added

    def remove_speaker(self, name):
        """删除说话人"""
        self._ensure_loaded()

        if name in self._speakers:
            del self._speakers[name]
            self._save_to_file()
            logger.info(f"Removed speaker: {name}")

    def rename_speaker(self, old_name, new_name):
        """
        重命名说话人

        Args:
            old_name: 旧姓名
            new_name: 新姓名

        Returns:
            bool: 是否成功
        """
        self._ensure_loaded()

        if old_name not in self._speakers:
            return False

        if new_name in self._speakers:
            return False

        # 获取旧的 profile
        profile = self._speakers[old_name]

        # 创建新的 profile
        new_profile = SpeakerProfile(new_name)
        new_profile.embeddings = profile.embeddings
        new_profile.created_at = profile.created_at

        # 删除旧的，添加新的
        del self._speakers[old_name]
        self._speakers[new_name] = new_profile
        self._save_to_file()

        logger.info(f"Renamed speaker: {old_name} -> {new_name}")
        return True

    def get_speakers(self):
        """获取所有说话人"""
        self._ensure_loaded()
        return dict(self._speakers)

    def match(self, embedding):
        """匹配最相似的说话人"""
        self._ensure_loaded()

        best_match = None
        best_score = 0

        for name, profile in self._speakers.items():
            if not profile.can_match():
                continue

            avg_embedding = profile.get_weighted_embedding()
            if avg_embedding is None:
                continue

            score = self._cosine_similarity(embedding, avg_embedding)

            if score > best_score:
                best_score = score
                best_match = name

        if best_match and best_score >= MATCH_THRESHOLD:
            return best_match, best_score
        return None, 0

    def match_with_confidence(self, embedding):
        """匹配并返回置信度级别"""
        name, score = self.match(embedding)

        if name is None:
            return None, "no_match"
        elif score >= HIGH_CONFIDENCE:
            return name, "confirmed"
        else:
            return name, "suggested"

    def extract_embedding_from_file(self, audio_path):
        """
        从音频文件提取声纹嵌入向量

        使用 CAM++ 模型的 inference() 方法直接提取全局嵌入向量。
        CAM++ 的 inference() 接受 numpy array / torch tensor，不接受文件路径字符串。

        Args:
            audio_path: 音频文件路径

        Returns:
            dict: {spk_id: embedding_vector} 或 None
        """
        try:
            import soundfile as sf
            import numpy as np
            from funasr import AutoModel
            from gui.styles import MODEL_CACHE_DIR

            # 1. 读取音频文件为 numpy array
            audio_data, sample_rate = sf.read(audio_path)

            # 2. 重采样到 16kHz（如果不是）
            if sample_rate != 16000:
                # 简单重采样
                ratio = 16000 / sample_rate
                new_length = int(len(audio_data) * ratio)
                audio_data = np.interp(
                    np.linspace(0, len(audio_data) - 1, new_length),
                    np.arange(len(audio_data)),
                    audio_data
                )

            # 3. 确保单声道 float32
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            audio_data = audio_data.astype(np.float32)

            # 4. 加载 CAM++ 并提取嵌入
            model = AutoModel(
                model="cam++",
                device="cpu",
                disable_update=True,
            )

            # 使用 inference() 获取嵌入向量（传入 numpy array）
            result = model.inference(input=audio_data)

            if result and isinstance(result, list) and len(result) > 0:
                # 提取 spk_embedding
                spk_emb = result[0].get("spk_embedding")
                if spk_emb is not None:
                    # 转换为 Python list
                    if hasattr(spk_emb, "cpu"):
                        spk_emb = spk_emb.cpu().numpy()
                    if hasattr(spk_emb, "tolist"):
                        spk_emb = spk_emb.tolist()
                    # 如果是嵌套的 list [[...]]，取第一个元素
                    if isinstance(spk_emb, list) and len(spk_emb) == 1 and isinstance(spk_emb[0], list):
                        spk_emb = spk_emb[0]
                    return {0: spk_emb}

            logger.warning("Failed to extract embedding: no spk_embedding in result")
            return None

        except Exception as e:
            logger.error(f"Failed to extract embedding from file: {e}")
            return None

    @staticmethod
    def _cosine_similarity(a, b):
        """计算余弦相似度"""
        a = np.array(a).flatten()
        b = np.array(b).flatten()

        # 维度校验：防止模型版本不匹配导致错误匹配
        if a.shape != b.shape:
            logger.warning(f"Embedding dimension mismatch: {a.shape} vs {b.shape}")
            return 0.0

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return np.dot(a, b) / (norm_a * norm_b)
