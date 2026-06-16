#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双轨合并测试（T-G1 文件名配对 + T-G4 时间戳合并接线）

纯路径/文本逻辑，不依赖 funasr/pyaudio，可在干净环境运行。
"""

import os
import pytest

from dual_track_merge import (
    find_dual_track_pair,
    merge_dual_transcripts,
    get_speaker_names_from_merged,
    SYS_TRACK_SUFFIX,
)


# ══════════════════════════════════════════════════════════
#  T-G1: 文件名 ↔ 配对后缀统一
# ══════════════════════════════════════════════════════════

class TestFindDualTrackPairChineseSuffix:
    """录音器实际写出 {ts}会议_系统音频.wav，配对必须识别该后缀。"""

    def test_find_pair_from_mic_file(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")

        pair = find_dual_track_pair(str(mic))
        assert pair == (str(mic), str(sys))

    def test_find_pair_from_sys_file(self, tmp_path):
        """从系统音频轨文件也能反查到配对。"""
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")

        pair = find_dual_track_pair(str(sys))
        assert pair == (str(mic), str(sys))

    def test_no_pair_when_sys_missing(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        mic.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(mic)) is None

    def test_suffix_constant_matches_recorder(self):
        """SYS_TRACK_SUFFIX 必须与 unified_recorder 写出的后缀一致。"""
        assert SYS_TRACK_SUFFIX == "_系统音频"

    def test_recorder_dual_filenames_are_pairable(self, tmp_path):
        """回归锁定：录音器生成的双轨文件名必须能被 find_dual_track_pair 配对。

        这是 G1 修复的核心 bug——录音器与配对逻辑此前后缀不一致。
        用录音器真实的命名规则构造文件名，验证可配对。
        """
        from unified_recorder import SYS_TRACK_SUFFIX as REC_SUFFIX
        ts = "25061612"
        mic = tmp_path / f"{ts}会议.wav"
        sys = tmp_path / f"{ts}会议{REC_SUFFIX}.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(mic)) == (str(mic), str(sys))


class TestFindDualTrackPairLegacySuffix:
    """向后兼容历史 _sys 后缀（旧数据）。"""

    def test_find_pair_legacy_sys_from_mic(self, tmp_path):
        mic = tmp_path / "meeting.wav"
        sys = tmp_path / "meeting_sys.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(mic)) == (str(mic), str(sys))

    def test_find_pair_legacy_sys_from_sys(self, tmp_path):
        mic = tmp_path / "meeting.wav"
        sys = tmp_path / "meeting_sys.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        assert find_dual_track_pair(str(sys)) == (str(mic), str(sys))


# ══════════════════════════════════════════════════════════
#  T-G4: 时间戳合并（本地/远程标签）
# ══════════════════════════════════════════════════════════

class TestMergeDualTranscripts:
    def test_merge_interleaves_by_timestamp(self):
        mic = "[00:01] Speaker 1: 你好\n[00:05] Speaker 1: 在的"
        sys = "[00:03] Speaker 1: 听得到吗\n[00:07] Speaker 2: 我也在"
        merged = merge_dual_transcripts(mic, sys)
        lines = merged.strip().split("\n")
        # 按时间戳升序交错：01(mic) 03(sys) 05(mic) 07(sys)
        assert "[00:01]" in lines[0] and "本地-1" in lines[0]
        assert "[00:03]" in lines[1] and "远程-1" in lines[1]
        assert "[00:05]" in lines[2] and "本地-1" in lines[2]
        assert "[00:07]" in lines[3] and "远程-2" in lines[3]

    def test_local_remote_labels(self):
        mic = "[00:01] Speaker 1: a"
        sys = "[00:02] Speaker 1: b"
        merged = merge_dual_transcripts(mic, sys)
        assert "本地-1" in merged
        assert "远程-1" in merged
        assert "Speaker" not in merged

    def test_get_speaker_names_from_merged(self):
        merged = "[00:01] 本地-1: a\n[00:02] 远程-1: b\n[00:03] 远程-2: c"
        names = get_speaker_names_from_merged(merged)
        labels = [label for _, label in names]
        assert "本地-1" in labels
        assert "远程-1" in labels
        assert "远程-2" in labels
