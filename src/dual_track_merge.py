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

# 系统音频轨文件名后缀（与 unified_recorder 写出的命名保持一致）。
# 录音器保存系统音频轨为 "{ts}会议_系统音频.wav"，配对逻辑以此为准。
SYS_TRACK_SUFFIX = "_系统音频"
# 历史后缀（旧版数据兼容）。
LEGACY_SYS_TRACK_SUFFIX = "_sys"
_SYS_SUFFIXES = (SYS_TRACK_SUFFIX, LEGACY_SYS_TRACK_SUFFIX)

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


def _extract_header(text):
    """从转写文本中提取文件头（--- 分隔线之前的内容）"""
    lines = text.split('\n')
    header_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == '---':
            break
        header_lines.append(line)
    if not header_lines or len(header_lines) == len(lines):
        return ""
    return '\n'.join(header_lines).strip()


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


def is_dual_track_group(file_paths):
    """
    判断一组待合并文件是否构成"双轨对"（同一次录音的 mic + system 两轨）。

    仅当恰好两个文件、且 find_dual_track_pair 能将它们识别为
    (mic_path, sys_path) 配对时才视为双轨对。

    Args:
        file_paths: 文件路径列表

    Returns:
        (mic_path, sys_path) 若为双轨对，否则 None
    """
    if not file_paths or len(file_paths) != 2:
        return None
    pair = find_dual_track_pair(file_paths[0])
    if pair and set(pair) == set(file_paths):
        return pair
    return None


def build_merged_transcript(file_paths, per_file_texts,
                            mic_label="本地", sys_label="远程"):
    """
    根据待合并文件及其各自的转写文本，产出合并后的转写文本。

    区分两种合并语义：
      - 双轨对（mic + system，同一次录音）→ 调用 merge_dual_transcripts
        按时间戳交错合并，并加本地/远程前缀。
      - 普通多文件合并 → 保留原有 "## file" 顺序拼接逻辑。

    把这一判定与合并抽成纯函数，便于在无 funasr 环境下用 mock 文本单测，
    worker 只负责转写并把文本喂进来。

    Args:
        file_paths: 待合并文件路径列表（顺序即拼接顺序）
        per_file_texts: {file_path: transcript_text} 各文件转写结果
        mic_label: 麦克风轨发言人前缀（双轨时用）
        sys_label: 系统音频轨发言人前缀（双轨时用）

    Returns:
        (merged_text, is_dual)
        merged_text — 合并后的转写文本
        is_dual     — 是否按双轨时间戳合并
    """
    pair = is_dual_track_group(file_paths)
    if pair:
        mic_path, sys_path = pair
        mic_text = per_file_texts.get(mic_path, "")
        sys_text = per_file_texts.get(sys_path, "")
        merged = merge_dual_transcripts(
            mic_text, sys_text, mic_label=mic_label, sys_label=sys_label
        )
        # 从 mic 轨文本中提取文件头（--- 分隔线之前的内容）
        header = _extract_header(mic_text)
        if header:
            merged = header + "\n\n" + merged
        return merged, True

    # 普通多文件合并：按传入顺序拼接，加文件名小标题。
    blocks = []
    for fp in file_paths:
        fname = os.path.basename(fp)
        blocks.append(f"## {fname}\n\n{per_file_texts.get(fp, '')}")
    return "\n\n---\n\n".join(blocks), False


def find_dual_track_pair(file_path):
    """
    检查文件是否有对应的双轨配对

    Args:
        file_path: 文件路径

    Returns:
        (mic_path, sys_path) 或 None
    """
    base, ext = os.path.splitext(file_path)

    # 情况一：传入的是系统音频轨文件 → 反查麦克风轨
    # 同时识别新后缀 "_系统音频" 与历史后缀 "_sys"
    for suffix in _SYS_SUFFIXES:
        if base.endswith(suffix):
            mic_path = base[:-len(suffix)] + ext
            if os.path.exists(mic_path):
                return (mic_path, file_path)
            return None

    # 情况二：传入的是麦克风轨文件 → 查找对应系统音频轨
    # 优先新后缀，回退历史后缀
    for suffix in _SYS_SUFFIXES:
        sys_path = base + suffix + ext
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
