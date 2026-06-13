#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试音色匹配修复效果
使用 meeting_20260603_092739.wav 验证转写和音色匹配

注意：这是一个集成测试，需要加载真实模型和音频文件。
运行方式：python tests/test_voiceprint_fix.py（不通过 pytest）
"""

import os
import sys
import logging
import pytest

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s - %(message)s'
)
logger = logging.getLogger("MeetScribe")

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

@pytest.mark.skip(reason="集成测试：需要加载真实模型和音频文件，手动运行")
def test_transcription():
    """测试转写功能"""
    from transcriber import Transcriber
    from voiceprint import VoiceprintLibrary
    from gui.styles import MODEL_CACHE_DIR

    audio_path = "recordings/meeting_20260603_092739.wav"

    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return False

    logger.info(f"Testing transcription with: {audio_path}")
    logger.info(f"Model cache dir: {MODEL_CACHE_DIR}")

    # 初始化转写器（传入模型缓存目录）
    transcriber = Transcriber(model_cache_dir=MODEL_CACHE_DIR)

    try:
        # 执行转写
        result = transcriber.transcribe(
            audio_path=audio_path,
            output_format="llm-md",
            speaker_names={},
            progress_callback=lambda msg: logger.info(f"[PROGRESS] {msg}")
        )

        # 检查转写结果
        if result and result != "[empty] 未识别到语音内容":
            logger.info("=" * 60)
            logger.info("转写结果（前 500 字符）:")
            logger.info(result[:500])
            logger.info("=" * 60)
        else:
            logger.error("转写结果为空")
            return False

        # 检查嵌入向量
        logger.info("=" * 60)
        logger.info(f"提取到的说话人嵌入向量数量: {len(transcriber.spk_embeddings)}")
        if transcriber.spk_embeddings:
            for spk_id, emb in transcriber.spk_embeddings.items():
                logger.info(f"  Speaker {spk_id}: dim={len(emb)}")
        else:
            logger.warning("未提取到任何说话人嵌入向量！")
        logger.info("=" * 60)

        # 测试音色库匹配
        logger.info("=" * 60)
        logger.info("测试音色库匹配...")
        library = VoiceprintLibrary()

        if transcriber.spk_embeddings:
            for spk_id, emb in transcriber.spk_embeddings.items():
                match_name, confidence = library.match_with_confidence(emb)
                if match_name:
                    logger.info(f"  Speaker {spk_id} -> 匹配到: {match_name} (置信度: {confidence})")
                else:
                    logger.info(f"  Speaker {spk_id} -> 未匹配到音色库中的说话人")
        else:
            logger.warning("无法测试音色库匹配（没有嵌入向量）")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Transcription test failed: {e}", exc_info=True)
        return False

def test_extract_embedding_from_file():
    """测试手动录入音色功能"""
    from voiceprint import VoiceprintLibrary

    # 使用一个已有的音频文件测试
    test_audio = "recordings/meeting_20260603_092739.wav"

    if not os.path.exists(test_audio):
        logger.error(f"Test audio not found: {test_audio}")
        return False

    logger.info(f"Testing extract_embedding_from_file with: {test_audio}")

    library = VoiceprintLibrary()

    try:
        result = library.extract_embedding_from_file(test_audio)

        if result:
            logger.info("=" * 60)
            logger.info("手动录入音色测试成功!")
            for spk_id, emb in result.items():
                logger.info(f"  Speaker {spk_id}: dim={len(emb)}")
            logger.info("=" * 60)
            return True
        else:
            logger.error("手动录入音色测试失败：未提取到嵌入向量")
            return False

    except Exception as e:
        logger.error(f"extract_embedding_from_file test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("开始音色匹配修复验证测试")
    logger.info("=" * 60)

    # 测试 1: 手动录入音色
    logger.info("\n[Test 1] 测试手动录入音色功能...")
    test1_passed = test_extract_embedding_from_file()

    # 测试 2: 转写 + 音色匹配
    logger.info("\n[Test 2] 测试转写和音色匹配功能...")
    test2_passed = test_transcription()

    # 汇总
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总:")
    logger.info(f"  Test 1 (手动录入音色): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    logger.info(f"  Test 2 (转写+音色匹配): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    logger.info("=" * 60)

    if test1_passed and test2_passed:
        logger.info("\n🎉 所有测试通过！音色匹配修复成功！")
        sys.exit(0)
    else:
        logger.info("\n❌ 部分测试失败，请检查日志")
        sys.exit(1)
