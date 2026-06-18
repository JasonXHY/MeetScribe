#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-G13 — 录音链路单测（REC-001 ~ REC-010）。

策略：``UnifiedRecorder.__init__`` 不导入 pyaudio（懒加载），可直接构造真实实例。
- 音频采集（pyaudio 回调）用 mock 注入帧，或直接向内部队列塞 numpy 帧。
- 设备枚举（VB-Cable / WASAPI Loopback）用 mock 的 PyAudio 实例。
- WAV 参数用 soundfile 读回断言。

不依赖真实麦克风 / pyaudiowpatch。
"""

import os
import time
import threading

import numpy as np
import pytest
import soundfile as sf

from unified_recorder import UnifiedRecorder, _recording_filename_stamp
from dual_track_merge import SYS_TRACK_SUFFIX

pytestmark = pytest.mark.unit


@pytest.fixture
def rec(tmp_path):
    return UnifiedRecorder(save_dir=str(tmp_path), sample_rate=16000, channels=1)


def _put_frames(q, seconds=1.0, rate=16000, channels=1):
    """向队列塞入 float32 音频帧（模拟 pyaudio 回调产出）。"""
    n = int(seconds * rate)
    if channels == 1:
        data = (0.2 * np.sin(2 * np.pi * 440 * np.arange(n) / rate)).astype(np.float32)
    else:
        data = (0.2 * np.random.randn(n, channels)).astype(np.float32)
    q.put(data)


# ── REC-001 / REC-008：WAV 参数（16kHz / 单声道 / PCM16） ──────


class TestWavFormat:
    def test_saved_wav_is_16k_mono_pcm16(self, rec, tmp_path):
        out = os.path.join(str(tmp_path), "out.wav")
        _put_frames(rec._mic_queue, seconds=1.0, rate=16000, channels=1)
        rec._save_audio(rec._mic_queue, out, sample_rate=16000)

        info = sf.info(out)
        assert info.samplerate == 16000
        assert info.channels == 1
        assert info.subtype == "PCM_16"

    def test_multichannel_downmixed_to_mono(self, rec, tmp_path):
        """REC-001：多声道系统音频应混为单声道保存。"""
        out = os.path.join(str(tmp_path), "sys.wav")
        _put_frames(rec._sys_queue, seconds=0.5, rate=16000, channels=2)
        rec._save_audio(rec._sys_queue, out, sample_rate=16000)

        info = sf.info(out)
        assert info.channels == 1


# ── REC-002：停止后文件完整可读 ───────────────────────────────


class TestFileReadable:
    def test_saved_file_readable_and_nonempty(self, rec, tmp_path):
        out = os.path.join(str(tmp_path), "ok.wav")
        _put_frames(rec._mic_queue, seconds=1.0)
        path = rec._save_audio(rec._mic_queue, out, sample_rate=16000)

        assert path == out
        assert os.path.exists(out)
        data, sr = sf.read(out)
        assert sr == 16000
        assert len(data) == 16000  # 1 秒 @ 16kHz

    def test_empty_queue_returns_none(self, rec, tmp_path):
        out = os.path.join(str(tmp_path), "empty.wav")
        result = rec._save_audio(rec._mic_queue, out, sample_rate=16000)
        assert result is None
        assert not os.path.exists(out)


# ── REC-003：pause/resume 线程安全 + 暂停不累加录音时长 ────────


class TestPauseResume:
    def test_pause_does_not_count_toward_elapsed(self, rec):
        rec._recording = True
        rec._paused = False
        rec._start_time = time.time()
        rec._paused_duration = 0.0
        rec._pause_start = None

        rec.pause()
        time.sleep(0.2)  # 暂停期间经过 0.2s
        rec.resume()
        time.sleep(0.05)

        elapsed = rec.get_elapsed()
        # 暂停的 0.2s 不应计入；总 elapsed 应明显小于真实经过时间
        assert rec._paused_duration >= 0.18
        assert elapsed < 0.18

    def test_concurrent_pause_resume_no_error(self, rec):
        rec._recording = True
        rec._paused = False
        rec._start_time = time.time() - 10.0
        rec._paused_duration = 0.0
        rec._pause_start = None

        errors = []

        def cycle():
            try:
                for _ in range(200):
                    rec.pause()
                    rec.resume()
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=cycle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert rec._paused is False


# ── REC-004：get_elapsed 单调 + update_timer 格式 ─────────────


class TestTimer:
    def test_get_elapsed_monotonic(self, rec):
        rec._recording = True
        rec._paused = False
        rec._start_time = time.time()
        rec._paused_duration = 0.0
        rec._pause_start = None

        readings = [rec.get_elapsed() for _ in range(5)]
        for a, b in zip(readings, readings[1:]):
            assert b >= a
        assert all(r >= 0 for r in readings)

    def test_get_elapsed_after_stop_returns_nonneg(self, rec):
        rec._recording = False
        rec._paused_duration = 3.0
        assert rec.get_elapsed() == 3.0

    def test_update_timer_format_hhmmss(self, qtbot):
        from gui.recording_bar import RecordingBar

        bar = RecordingBar()
        qtbot.addWidget(bar)
        bar.update_timer(3661)  # 1h 1m 1s
        assert bar.timer_label.text() == "01:01:01"
        bar.update_timer(75)    # 1m 15s
        assert bar.timer_label.text() == "00:01:15"


# ── REC-005 / REC-006：mic 1 文件 / dual 2 文件 + 命名 ─────────


class TestFileCounts:
    def test_mic_mode_produces_single_file(self, rec):
        rec._mode = "mic"
        rec._mic_file = os.path.join(rec.save_dir, "061614会议.wav")
        rec._mic_rate = 16000
        _put_frames(rec._mic_queue, seconds=0.5)

        saved = []
        rec.on_stop_complete = saved.extend
        rec._stop_and_save()

        assert len(saved) == 1
        assert saved[0].endswith("会议.wav")

    def test_dual_mode_produces_two_files_with_suffix(self, rec):
        rec._mode = "dual"
        rec._mic_file = os.path.join(rec.save_dir, "061614会议.wav")
        rec._sys_file = os.path.join(rec.save_dir, f"061614会议{SYS_TRACK_SUFFIX}.wav")
        rec._mic_rate = 16000
        rec._sys_rate = 16000
        _put_frames(rec._mic_queue, seconds=0.3)
        _put_frames(rec._sys_queue, seconds=0.3)

        saved = []
        rec.on_stop_complete = saved.extend
        rec._stop_and_save()

        assert len(saved) == 2
        names = [os.path.basename(p) for p in saved]
        # 一个主轨、一个系统轨（含配对后缀）
        assert any(SYS_TRACK_SUFFIX in n for n in names)
        assert any(SYS_TRACK_SUFFIX not in n for n in names)


# ── REC-007：VB-Cable 优先，缺失时回退 WASAPI ─────────────────


class _FakePyAudio:
    """最小 PyAudio 替身，按设备列表回答枚举查询。"""

    def __init__(self, devices, loopback=None):
        self._devices = devices
        self._loopback = loopback or []

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, i):
        return self._devices[i]

    def get_loopback_device_info_generator(self):
        return iter(self._loopback)


class TestVbCableFallback:
    def test_find_vb_cable_returns_index_when_present(self, rec):
        p = _FakePyAudio([
            {"name": "Microphone", "maxInputChannels": 1, "defaultSampleRate": 16000},
            {"name": "VB-Audio Cable", "maxInputChannels": 2, "defaultSampleRate": 48000},
        ])
        assert rec._find_vb_cable(p) == 1

    def test_find_vb_cable_returns_none_when_absent(self, rec):
        p = _FakePyAudio([
            {"name": "Microphone", "maxInputChannels": 1, "defaultSampleRate": 16000},
            {"name": "Speakers", "maxInputChannels": 0, "defaultSampleRate": 44100},
        ])
        assert rec._find_vb_cable(p) is None

    def test_loopback_used_when_vb_cable_missing(self, tmp_path):
        """use_vb_cable=True 但设备不存在 → 回退到 WASAPI Loopback 设备。"""
        rec = UnifiedRecorder(save_dir=str(tmp_path), use_vb_cable=True)
        opened = {}

        class _Stream:
            pass

        loopback_dev = {"index": 5, "name": "Speakers (Loopback)",
                        "maxInputChannels": 2, "defaultSampleRate": 48000}
        p = _FakePyAudio(
            [{"name": "Microphone", "maxInputChannels": 1, "defaultSampleRate": 16000}],
            loopback=[loopback_dev],
        )

        def fake_open(**kwargs):
            opened.update(kwargs)
            return _Stream()
        p.open = fake_open

        class _FakeModule:
            paFloat32 = 1
            paContinue = 0
        stream = rec._open_loopback_stream(p, _FakeModule())

        assert stream is not None
        # 回退使用了 loopback 设备的采样率与索引
        assert rec._sys_rate == 48000
        assert opened["input_device_index"] == 5

    def test_vb_cable_preferred_when_present(self, tmp_path):
        rec = UnifiedRecorder(save_dir=str(tmp_path), use_vb_cable=True)
        opened = {}

        vb_dev = {"name": "VB-Audio Cable", "maxInputChannels": 2,
                  "defaultSampleRate": 48000}
        p = _FakePyAudio([
            {"name": "Microphone", "maxInputChannels": 1, "defaultSampleRate": 16000},
            vb_dev,
        ], loopback=[{"index": 9, "name": "Should-not-use", "maxInputChannels": 2,
                      "defaultSampleRate": 44100}])

        def fake_open(**kwargs):
            opened.update(kwargs)
            return object()
        p.open = fake_open

        class _FakeModule:
            paFloat32 = 1
            paContinue = 0
        rec._open_loopback_stream(p, _FakeModule())

        # 应使用 VB-Cable（索引 1），而非 loopback（索引 9）
        assert opened["input_device_index"] == 1


# ── REC-009：停止后触发"询问转写" ────────────────────────────


class TestAskTranscribeTrigger:
    def test_stop_complete_triggers_ask_transcribe(self, tmp_path, monkeypatch):
        """REC-009：录音保存后应调用 home_page.ask_transcribe_after_record。"""
        # 直接驱动 app 的 _handle_stop_complete，断言询问被排程。
        import gui.app as app_mod

        # 用轻量替身验证回调链，不构造完整窗口。
        asked = {}

        class _FakeHome:
            def refresh_file_list(self):
                pass

            def ask_transcribe_after_record(self, path):
                asked["path"] = path

        class _FakeFM:
            def get_file(self, p):
                return None

            def add_file(self, p):
                pass

        # singleShot 立即执行回调，便于断言
        monkeypatch.setattr(app_mod, "QTimer",
                            type("Q", (), {"singleShot": staticmethod(lambda ms, fn: fn())}))

        fake_self = type("S", (), {})()
        fake_self._home_page = _FakeHome()
        fake_self.file_manager = _FakeFM()
        fake_self._log = lambda *a, **k: None

        saved = os.path.join(str(tmp_path), "061614会议.wav")
        app_mod.MeetScribeApp._handle_stop_complete(fake_self, [saved])

        assert asked.get("path") == saved


# ── REC-010：命名符合 T-G12 校正格式（MMDDHH会议.wav） ────────


class TestNaming:
    def test_filename_stamp_is_mmddhh(self):
        from datetime import datetime
        stamp = _recording_filename_stamp(datetime(2026, 6, 16, 14, 30, 0))
        assert stamp == "061614"

    def test_start_names_files_per_convention(self, rec, monkeypatch):
        """start() 应按 MMDDHH会议.wav 约定命名（不真正启动音频线程）。"""
        monkeypatch.setattr("unified_recorder._recording_filename_stamp",
                            lambda dt=None: "061614")
        # 阻止真正启动后台音频线程（避免导入 pyaudiowpatch）
        monkeypatch.setattr(rec, "_audio_loop", lambda: None)

        rec.start(mode="dual")
        try:
            assert os.path.basename(rec._mic_file) == "061614会议.wav"
            assert os.path.basename(rec._sys_file) == f"061614会议{SYS_TRACK_SUFFIX}.wav"
        finally:
            rec._recording = False
