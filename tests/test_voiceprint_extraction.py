#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声纹提取功能测试脚本
"""

import os
import sys

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def test_voiceprint_extraction():
    """测试声纹提取功能"""
    print("=" * 60)
    print("声纹提取功能测试")
    print("=" * 60)

    # 1. 测试 Transcriber
    print("\n[1] 测试 Transcriber...")
    try:
        from transcriber import Transcriber
        from gui.styles import MODEL_CACHE_DIR

        transcriber = Transcriber(model_cache_dir=MODEL_CACHE_DIR, device="cpu")
        print(f"  - MODEL_CACHE_DIR: {MODEL_CACHE_DIR}")

        # 检查模型
        ready, missing = transcriber.check_models_ready()
        print(f"  - Models ready: {ready}")
        if missing:
            print(f"  - Missing models: {missing}")
            return False

        # 加载模型
        print("  - Loading models...")
        transcriber.load_model()
        print("  - Models loaded successfully")

        # 2. 测试声纹提取
        print("\n[2] 测试声纹提取...")
        test_file = "C:/MeetScribe/recordings/meeting_20260528_013203.wav"
        if not os.path.exists(test_file):
            print(f"  - Test file not found: {test_file}")
            return False

        print(f"  - Test file: {test_file}")
        print(f"  - File size: {os.path.getsize(test_file)} bytes")

        # 使用 transcribe_staged 方法
        print("  - Running transcribe_staged...")
        result = transcriber.transcribe_staged(
            test_file,
            output_format="json",
            progress_callback=lambda msg: print(f"    {msg}"),
        )

        # 获取嵌入向量
        embeddings = transcriber.spk_embeddings
        print(f"  - Extracted embeddings: {embeddings}")
        print(f"  - Number of speakers: {len(embeddings)}")

        if embeddings:
            for spk_id, emb in embeddings.items():
                print(f"    Speaker {spk_id}: embedding dim = {len(emb)}")
            print("\n[SUCCESS] Voiceprint extraction works!")
            return True
        else:
            print("\n[FAILED] No embeddings extracted")
            return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_voiceprint_library():
    """测试音色库功能"""
    print("\n" + "=" * 60)
    print("音色库功能测试")
    print("=" * 60)

    try:
        from voiceprint import VoiceprintLibrary
        import numpy as np

        # 创建临时音色库
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        try:
            library = VoiceprintLibrary(temp_path)

            # 添加测试说话人
            test_embedding = np.random.rand(192).tolist()
            library.add_speaker("测试用户", test_embedding, "test_source")
            print("  - Added speaker: 测试用户")

            # 获取说话人
            speakers = library.get_speakers()
            print(f"  - Speakers: {list(speakers.keys())}")

            # 匹配测试
            match_name, score = library.match(test_embedding)
            print(f"  - Match result: {match_name}, score: {score}")

            if match_name == "测试用户" and score > 0.75:
                print("\n[SUCCESS] Voiceprint library works!")
                return True
            else:
                print("\n[FAILED] Voiceprint library match failed")
                return False

        finally:
            os.remove(temp_path)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success1 = test_voiceprint_extraction()
    success2 = test_voiceprint_library()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"声纹提取: {'✓ PASS' if success1 else '✗ FAIL'}")
    print(f"音色库: {'✓ PASS' if success2 else '✗ FAIL'}")

    if success1 and success2:
        print("\n所有测试通过！")
        sys.exit(0)
    else:
        print("\n测试失败！")
        sys.exit(1)
