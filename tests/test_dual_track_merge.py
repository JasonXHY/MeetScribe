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
    build_merged_transcript,
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


# ══════════════════════════════════════════════════════════
#  T-G4: worker 合并分支接线（build_merged_transcript 纯函数）
#
#  worker 把每个文件转写成文本后调用此辅助函数决定合并语义：
#   - 双轨对（mic + system，同一次录音）→ merge_dual_transcripts 时间戳交错
#   - 普通多文件合并 → 原 "## file" 顺序拼接
#  这样合并逻辑可在无 funasr 环境下用 mock 转写文本单测。
# ══════════════════════════════════════════════════════════

class TestBuildMergedTranscript:
    def _make_pair(self, tmp_path):
        mic = tmp_path / "25061612会议.wav"
        sys = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys.write_bytes(b"RIFF")
        return str(mic), str(sys)

    def test_dual_pair_uses_timestamp_merge(self, tmp_path):
        """双轨对：按时间戳交错合并，加本地/远程前缀，无 '## file' 头。"""
        mic_path, sys_path = self._make_pair(tmp_path)
        texts = {
            mic_path: "[00:01] Speaker 1: 你好\n[00:05] Speaker 1: 在的",
            sys_path: "[00:03] Speaker 1: 听得到吗\n[00:07] Speaker 2: 我也在",
        }
        merged, is_dual = build_merged_transcript([mic_path, sys_path], texts)
        assert is_dual is True
        lines = merged.strip().split("\n")
        assert "[00:01]" in lines[0] and "本地-1" in lines[0]
        assert "[00:03]" in lines[1] and "远程-1" in lines[1]
        assert "[00:05]" in lines[2] and "本地-1" in lines[2]
        assert "[00:07]" in lines[3] and "远程-2" in lines[3]
        # 双轨合并不应出现普通拼接的文件头
        assert "## " not in merged
        assert "Speaker" not in merged

    def test_dual_pair_from_sys_first_order(self, tmp_path):
        """即使传入顺序是 system 在前，也按 mic=本地 / system=远程 归属。"""
        mic_path, sys_path = self._make_pair(tmp_path)
        texts = {
            mic_path: "[00:02] Speaker 1: 麦克风",
            sys_path: "[00:01] Speaker 1: 系统",
        }
        merged, is_dual = build_merged_transcript([sys_path, mic_path], texts)
        assert is_dual is True
        # 时间戳 01(系统/远程) 在前，02(麦克风/本地) 在后
        lines = merged.strip().split("\n")
        assert "远程-1" in lines[0]
        assert "本地-1" in lines[1]

    def test_ordinary_multifile_uses_concatenation(self, tmp_path):
        """普通多文件（非双轨对）仍走原 '## file' 顺序拼接。"""
        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        a.write_bytes(b"RIFF")
        b.write_bytes(b"RIFF")
        texts = {
            str(a): "[00:01] Speaker 1: alpha",
            str(b): "[00:02] Speaker 1: beta",
        }
        merged, is_dual = build_merged_transcript([str(a), str(b)], texts)
        assert is_dual is False
        assert "## a.wav" in merged
        assert "## b.wav" in merged
        assert "alpha" in merged and "beta" in merged
        # 原拼接保留 Speaker 标签，不做本地/远程改写
        assert "本地" not in merged and "远程" not in merged

    def test_three_files_not_treated_as_dual(self, tmp_path):
        """三个文件即便其中两个能配对，整体仍按普通多文件拼接。"""
        mic_path, sys_path = self._make_pair(tmp_path)
        c = tmp_path / "other.wav"
        c.write_bytes(b"RIFF")
        texts = {
            mic_path: "[00:01] Speaker 1: a",
            sys_path: "[00:02] Speaker 1: b",
            str(c): "[00:03] Speaker 1: c",
        }
        merged, is_dual = build_merged_transcript([mic_path, sys_path, str(c)], texts)
        assert is_dual is False
        assert "## " in merged


# ══════════════════════════════════════════════════════════
#  T-G4: worker 合并分支端到端接线（用 fake Transcriber，不需 funasr）
# ══════════════════════════════════════════════════════════

class _FakeQueue:
    """收集 worker 发出的所有消息，供断言。"""

    def __init__(self):
        self.messages = []

    def put(self, msg):
        self.messages.append(msg)

    def by_type(self, mtype):
        return [m for m in self.messages if m and m[0] == mtype]


@pytest.fixture
def fake_transcriber(monkeypatch):
    """注入一个假的 transcriber 模块，按文件名返回带时间戳的转写文本，避免加载 funasr。"""
    import sys
    import types

    texts_by_basename = {}

    class _FakeTranscriber:
        def __init__(self, *a, **k):
            self.spk_embeddings = {}
            self.sentences = []

        def check_models_ready(self):
            return True, []

        def transcribe(self, audio_path, **kwargs):
            return texts_by_basename[os.path.basename(audio_path)]

    fake_mod = types.ModuleType("transcriber")
    fake_mod.Transcriber = _FakeTranscriber
    monkeypatch.setitem(sys.modules, "transcriber", fake_mod)
    return texts_by_basename


class TestWorkerMergeBranch:
    def test_worker_dual_branch_calls_merge(self, tmp_path, fake_transcriber):
        """双轨对走 worker 合并分支：结果文件为时间戳交错的本地/远程合并文本。"""
        from transcribe_worker import transcribe_worker_process

        mic = tmp_path / "25061612会议.wav"
        sys_f = tmp_path / "25061612会议_系统音频.wav"
        mic.write_bytes(b"RIFF")
        sys_f.write_bytes(b"RIFF")
        fake_transcriber["25061612会议.wav"] = "[00:01] Speaker 1: 你好\n[00:05] Speaker 1: 在的"
        fake_transcriber["25061612会议_系统音频.wav"] = "[00:03] Speaker 1: 听到了\n[00:07] Speaker 2: 我也在"

        q = _FakeQueue()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        transcribe_worker_process(
            q, str(tmp_path), "cpu",
            [str(mic), str(sys_f)], "md", {}, str(out_dir), True,
        )

        # 没有 error
        assert not q.by_type("error"), q.by_type("error")
        merge_done = q.by_type("merge_done")
        assert merge_done, "应发出 merge_done 消息"
        rpath = merge_done[0][2]
        content = open(rpath, encoding="utf-8").read()
        lines = [l for l in content.strip().split("\n") if l.strip()]
        # 时间戳交错 + 本地/远程前缀，且无普通拼接的 '## file' 头
        assert "[00:01]" in lines[0] and "本地-1" in lines[0]
        assert "[00:03]" in lines[1] and "远程-1" in lines[1]
        assert "[00:05]" in lines[2] and "本地-1" in lines[2]
        assert "[00:07]" in lines[3] and "远程-2" in lines[3]
        assert "## " not in content
        assert "Speaker" not in content

    def test_worker_ordinary_merge_uses_concatenation(self, tmp_path, fake_transcriber):
        """普通多文件合并走 worker 原拼接路径（'## file' 头，不改写为本地/远程）。"""
        from transcribe_worker import transcribe_worker_process

        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        a.write_bytes(b"RIFF")
        b.write_bytes(b"RIFF")
        fake_transcriber["a.wav"] = "[00:01] Speaker 1: alpha"
        fake_transcriber["b.wav"] = "[00:02] Speaker 1: beta"

        q = _FakeQueue()
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        transcribe_worker_process(
            q, str(tmp_path), "cpu",
            [str(a), str(b)], "md", {}, str(out_dir), True,
        )

        assert not q.by_type("error"), q.by_type("error")
        merge_done = q.by_type("merge_done")
        assert merge_done
        content = open(merge_done[0][2], encoding="utf-8").read()
        assert "## a.wav" in content and "## b.wav" in content
        assert "本地" not in content and "远程" not in content
