#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 双轨合并工具
将麦克风轨和系统音频轨的转写结果按时间戳合并
"""

import re
import os
import logging

logger = logging.getLogger("MeetScribe")

# 匹配时间戳格式: [HH:MM] 或 [HH:MM:SS]
TIMESTAMP_RE = re.compile(r'\[(\d{2}):(\d{2})(?::(\d{2}))?\]')


def parse_timestamp(line):
    """从行中解析时间戳，返回秒数"""
    m = TIMESTAMP_RE.search(line)
    if not m:
        return None
    h, m_, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return h * 3600 + m_ * 60 + s


def parse_transcript_lines(text):
    """
    解析转写文本，返回 [(timestamp_sec, line_text), ...]
    支持 md 和 llm-md 格式
    """
    lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        ts = parse_timestamp(line)
        if ts is not None:
            lines.append((ts, line))
    return lines


def merge_dual_transcripts(mic_text, sys_text, mic_label="本地", sys_label="远程"):
    """
    合并双轨转写结果

    Args:
        mic_text: 麦克风轨转写文本
        sys_text: 系统音频轨转写文本
        mic_label: 麦克风轨发言人前缀
        sys_label: 系统音频轨发言人前缀

    Returns:
        合并后的转写文本
    """
    mic_lines = parse_transcript_lines(mic_text)
    sys_lines = parse_transcript_lines(sys_text)

    # 给每行添加来源标记
    tagged_lines = []
    for ts, line in mic_lines:
        tagged_lines.append((ts, "mic", line))
    for ts, line in sys_lines:
        tagged_lines.append((ts, "sys", line))

    # 按时间戳排序
    tagged_lines.sort(key=lambda x: x[0])

    # 替换发言人标签
    merged_lines = []
    for ts, source, line in tagged_lines:
        if source == "mic":
            line = re.sub(r'Speaker\s+(\d+)', rf'{mic_label}-\1', line)
        else:
            line = re.sub(r'Speaker\s+(\d+)', rf'{sys_label}-\1', line)
        merged_lines.append(line)

    return '\n'.join(merged_lines)


def find_dual_track_pair(file_path):
    """
    检查文件是否有对应的双轨配对

    Args:
        file_path: 文件路径

    Returns:
        (mic_path, sys_path) 或 None
    """
    base, ext = os.path.splitext(file_path)

    # 检查是否是系统音频文件
    if base.endswith('_sys'):
        mic_path = base[:-4] + ext  # 去掉 _sys 后缀
        if os.path.exists(mic_path):
            return (mic_path, file_path)
        return None

    # 检查是否有对应的系统音频文件
    sys_path = base + '_sys' + ext
    if os.path.exists(sys_path):
        return (file_path, sys_path)

    return None


def get_speaker_names_from_merged(text):
    """
    从合并后的文本中提取发言人列表

    Returns:
        [(id, label), ...] 如 [(1, "本地-1"), (2, "远程-1"), ...]
    """
    speakers = set()
    # 匹配 本地-N 或 远程-N
    pattern = re.compile(r'(本地|远程)-(\d+)')
    for m in pattern.finditer(text):
        source = m.group(1)
        num = m.group(2)
        speakers.add((source, int(num), f"{source}-{num}"))

    # 排序：先本地后远程，按编号
    sorted_speakers = sorted(speakers, key=lambda x: (0 if x[0] == "本地" else 1, x[1]))
    return [(i+1, s[2]) for i, s in enumerate(sorted_speakers)]
