#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试音色库匹配阈值
使用 CAM++ 官方示例文件验证同一人/不同人的匹配效果
"""

import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from voiceprint import VoiceprintLibrary
from transcriber import Transcriber
from gui.styles import MODEL_CACHE_DIR

def extract_embedding_from_file(audio_path):
    """从音频文件提取嵌入向量"""
    import soundfile as sf
    from funasr import AutoModel

    # 读取音频
    audio_data, sample_rate = sf.read(audio_path)

    # 重采样到 16kHz
    if sample_rate != 16000:
        ratio = 16000 / sample_rate
        new_length = int(len(audio_data) * ratio)
        audio_data = np.interp(
            np.linspace(0, len(audio_data) - 1, new_length),
            np.arange(len(audio_data)),
            audio_data
        )

    # 确保单声道 float32
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)
    audio_data = audio_data.astype(np.float32)

    # 加载 CAM++ 并提取嵌入
    model = AutoModel(model="cam++", device="cpu", disable_update=True)
    result = model.inference(input=audio_data)

    if result and len(result) > 0:
        spk_emb = result[0].get("spk_embedding")
        if spk_emb is not None:
            if hasattr(spk_emb, "cpu"):
                spk_emb = spk_emb.cpu().numpy()
            if hasattr(spk_emb, "tolist"):
                spk_emb = np.array(spk_emb.tolist())
            if isinstance(spk_emb, list):
                spk_emb = np.array(spk_emb)
            if len(spk_emb.shape) > 1 and spk_emb.shape[0] == 1:
                spk_emb = spk_emb[0]
            return spk_emb
    return None

def cosine_similarity(a, b):
    """计算余弦相似度"""
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)

# CAM++ 官方示例文件路径
EXAMPLE_DIR = "models_cache/models/iic/speech_campplus_sv_zh-cn_16k-common/examples"
TEST_FILES = {
    "speaker1_a": f"{EXAMPLE_DIR}/speaker1_a_cn_16k.wav",
    "speaker1_b": f"{EXAMPLE_DIR}/speaker1_b_cn_16k.wav",
    "speaker2_a": f"{EXAMPLE_DIR}/speaker2_a_cn_16k.wav",
}

print("=" * 70)
print("音色库匹配阈值测试")
print("=" * 70)

# 1. 提取所有示例文件的嵌入
print("\n[Step 1] 提取示例文件的嵌入向量...")
print("-" * 70)
embeddings = {}
for name, path in TEST_FILES.items():
    print(f"  提取 {name}...")
    emb = extract_embedding_from_file(path)
    if emb is not None:
        embeddings[name] = emb
        print(f"    ✓ 成功 (dim={len(emb)}, norm={np.linalg.norm(emb):.4f})")
    else:
        print(f"    ✗ 失败")

if len(embeddings) < 2:
    print("\n❌ 无法提取足够的嵌入向量进行测试")
    sys.exit(1)

# 2. 计算相似度矩阵
print("\n[Step 2] 计算相似度矩阵...")
print("-" * 70)
names = list(embeddings.keys())
print(f"{'':20}", end="")
for name in names:
    print(f"{name:15}", end="")
print()

for name1 in names:
    print(f"{name1:20}", end="")
    for name2 in names:
        sim = cosine_similarity(embeddings[name1], embeddings[name2])
        print(f"{sim:15.4f}", end="")
    print()

# 3. 分析匹配效果
print("\n[Step 3] 分析匹配效果...")
print("-" * 70)

# 同一说话人不同录音
same_speaker_sim = cosine_similarity(embeddings["speaker1_a"], embeddings["speaker1_b"])
print(f"同一说话人 (speaker1_a vs speaker1_b): {same_speaker_sim:.4f}")

# 不同说话人
diff_speaker_sim = cosine_similarity(embeddings["speaker1_a"], embeddings["speaker2_a"])
print(f"不同说话人 (speaker1_a vs speaker2_a): {diff_speaker_sim:.4f}")

# 4. 测试不同阈值的效果
print("\n[Step 4] 测试不同阈值的效果...")
print("-" * 70)
print(f"{'阈值':>10} | {'正确匹配':>10} | {'漏识':>10} | {'误识':>10}")
print("-" * 70)

thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
for thr in thresholds:
    # 同一说话人应该匹配
    same_match = same_speaker_sim >= thr
    # 不同说话人应该不匹配
    diff_match = diff_speaker_sim >= thr

    correct = 1 if same_match else 0  # 正确匹配同一人
    miss = 0 if same_match else 1     # 漏识（同一人未匹配）
    false_accept = 1 if diff_match else 0  # 误识（不同人误匹配）

    print(f"{thr:>10.2f} | {'✓' if same_match else '✗':>10} | {'✗' if miss else '✓':>10} | {'✗' if false_accept else '✓':>10}")

# 5. 推荐阈值
print("\n[Step 5] 推荐阈值...")
print("-" * 70)

# 找到最佳阈值：能正确匹配同一人，同时不误匹配不同人
best_thr = None
for thr in thresholds:
    same_match = same_speaker_sim >= thr
    diff_match = diff_speaker_sim >= thr
    if same_match and not diff_match:
        best_thr = thr
        break

if best_thr:
    print(f"✓ 推荐匹配阈值: {best_thr}")
    print(f"  - 同一说话人相似度: {same_speaker_sim:.4f} >= {best_thr} → 匹配成功")
    print(f"  - 不同说话人相似度: {diff_speaker_sim:.4f} < {best_thr} → 匹配拒绝")
else:
    print("⚠ 无法找到完美阈值，建议进一步调整")
    print(f"  同一说话人相似度: {same_speaker_sim:.4f}")
    print(f"  不同说话人相似度: {diff_speaker_sim:.4f}")

# 6. 与音色库对比
print("\n[Step 6] 与现有音色库对比...")
print("-" * 70)

library = VoiceprintLibrary()
library._ensure_loaded()

print(f"音色库中的说话人: {list(library._speakers.keys())}")
for name, profile in library._speakers.items():
    lib_emb = profile.get_average_embedding()
    print(f"\n{name}:")
    for emb_name, emb in embeddings.items():
        sim = cosine_similarity(emb, lib_emb)
        print(f"  vs {emb_name}: {sim:.4f}")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
