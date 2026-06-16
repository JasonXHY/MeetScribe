#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T-G2 测试基础设施自检：synthetic_wav fixture + marker 注册。
纯单元，不依赖 funasr/pyaudio。
"""

import wave
import pytest


@pytest.mark.unit
def test_synthetic_wav_is_valid_16k_mono_pcm16(synthetic_wav):
    path = synthetic_wav("probe.wav", seconds=0.5, freq=440.0)
    with wave.open(path, "rb") as wf:
        assert wf.getnchannels() == 1, "应为单声道"
        assert wf.getframerate() == 16000, "应为 16kHz"
        assert wf.getsampwidth() == 2, "应为 PCM16"
        assert wf.getnframes() == int(0.5 * 16000)


@pytest.mark.unit
def test_synthetic_wav_distinct_names(synthetic_wav):
    a = synthetic_wav("a.wav")
    b = synthetic_wav("b.wav")
    assert a != b
    assert a.endswith("a.wav") and b.endswith("b.wav")


@pytest.mark.unit
def test_markers_registered(pytestconfig):
    """关键 marker 必须已注册（避免 PytestUnknownMarkWarning）。"""
    markers = pytestconfig.getini("markers")
    joined = "\n".join(markers)
    for name in ("unit", "integration", "e2e_heavy", "e2e_network"):
        assert name in joined, f"marker 未注册: {name}"
