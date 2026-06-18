#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 工具函数

从 gui/transcription.py 中提取的独立工具函数，避免循环依赖。
"""

import os
import re
import logging

logger = logging.getLogger("MeetScribe")


def get_summary_path(transcript_path):
    """从转写结果路径推导对应的汇总文件路径"""
    if not transcript_path:
        return None
    result_dir = os.path.dirname(transcript_path)
    base = os.path.splitext(os.path.basename(transcript_path))[0]
    # 去掉 _transcript 后缀
    if "_transcript" in base:
        base = base.replace("_transcript", "")
    # 尝试多种命名模式
    candidates = [
        os.path.join(result_dir, f"{base}_summary.md"),
        os.path.join(result_dir, f"{base}_transcript_summary.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def apply_speaker_mapping(transcript_path, mapping):
    """将 Speaker N 或 本地-N/远程-N 替换为真实姓名"""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            content = f.read()

        for spk_id, name in mapping.items():
            if '-' in str(spk_id) and not str(spk_id).isdigit():
                content = content.replace(str(spk_id), name)
            else:
                content = re.sub(
                    rf'(?<!\w)Speaker\s+{spk_id}(?!\w)',
                    name, content)

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logger.warning(f"Failed to apply speaker mapping: {e}")


def extract_speaker_mapping_from_summary(summary_text):
    """从摘要中提取说话人映射

    支持多种格式：
      - [Speaker N] 姓名
      - [Speaker N]姓名
      - Speaker N → 姓名
    """
    mapping = {}
    # 优先匹配 [Speaker N] 姓名 格式
    pattern_bracket = re.compile(r'\[Speaker\s+(\d+)\]\s*(.+?)(?:\s*$|\s*\n)')
    for m in pattern_bracket.finditer(summary_text):
        speaker_id = int(m.group(1))
        name = m.group(2).strip()
        if name and name != f"Speaker {speaker_id}":
            mapping[speaker_id] = name

    # 如果没有匹配到，回退到纯 Speaker N 格式（保持向后兼容）
    if not mapping:
        pattern_plain = re.compile(r'Speaker\s+(\d+)')
        for m in pattern_plain.finditer(summary_text):
            speaker_id = int(m.group(1))
            mapping[speaker_id] = f"Speaker {speaker_id}"

    return mapping
