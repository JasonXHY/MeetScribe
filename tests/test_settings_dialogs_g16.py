#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-G16 — 设置/发言人弹窗行为测试。

- SET-007/014：API Key 明文/密文切换 _toggle_api_key（echoMode 翻转）。
- SPK-002：_do_batch_replace 批量替换。
- SPK-003：_on_voiceprint_select 下拉填充 entry。
- SPK-005：_save_to_library 调用 library.add_speaker（mock library）。
- SPK-007：_extract_middle_segment_embedding 片段选择（最长发言中间 1/3）。

不依赖网络/funasr。
"""

import os
import sys
import tempfile

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QApplication, QLineEdit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance()
    if inst is None:
        inst = QApplication(sys.argv)
    return inst


@pytest.fixture
def config():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{}')
        temp_path = f.name
    try:
        yield Config(temp_path)
    finally:
        os.remove(temp_path)


# ── SET-007 / SET-014：API Key 明文切换 ──────────────────────


class TestApiKeyToggle:
    def test_toggle_switches_echo_mode(self, config, app):
        from gui.settings_page import SettingsPage
        with patch('gui.settings_page.QMessageBox'):
            page = SettingsPage(config=config, log_callback=lambda m: None)

        # 默认密文
        assert page._api_key_entry.echoMode() == QLineEdit.Password

        page._toggle_api_key()
        assert page._api_key_entry.echoMode() == QLineEdit.Normal

        page._toggle_api_key()
        assert page._api_key_entry.echoMode() == QLineEdit.Password


# ── SpeakerDialog 帮助：构造一个最小弹窗 ─────────────────────


def _make_speaker_dialog(app, speakers=None, embeddings=None,
                         audio_path=None, sentences=None, qualities=None):
    from gui.dialogs import SpeakerDialog
    speakers = speakers if speakers is not None else [
        {"label": "Speaker 1", "spk_id": 0, "name": "", "pct": 60.0},
        {"label": "Speaker 2", "spk_id": 1, "name": "", "pct": 40.0},
    ]
    return SpeakerDialog(
        parent=None,
        file_name="meeting.wav",
        speakers=speakers,
        speaker_embeddings=embeddings or {},
        speaker_qualities=qualities or {},
        audio_path=audio_path,
        sentences=sentences or [],
    )


# ── SPK-002：批量替换 ────────────────────────────────────────


class TestBatchReplace:
    def test_batch_replace_sets_name_on_selected_speaker(self, app):
        dlg = _make_speaker_dialog(app)
        # 选中第一个说话人，输入新名
        dlg._batch_from_combo.setCurrentIndex(0)
        dlg._batch_to_entry.setText("张三")

        with patch("gui.dialogs.QMessageBox"):
            dlg._do_batch_replace()

        # 第 0 位说话人的 name 被替换，且对应输入框被更新
        assert dlg._speakers[0]["name"] == "张三"
        assert dlg._speaker_entries[0].text() == "张三"

    def test_batch_replace_empty_name_noop(self, app):
        dlg = _make_speaker_dialog(app)
        dlg._batch_from_combo.setCurrentIndex(0)
        dlg._batch_to_entry.setText("")
        with patch("gui.dialogs.QMessageBox"):
            dlg._do_batch_replace()
        assert dlg._speakers[0]["name"] == ""


# ── SPK-003：音色库下拉选择填充 entry ───────────────────────


class TestVoiceprintSelect:
    def test_select_fills_entry(self, app):
        dlg = _make_speaker_dialog(app)
        entry = QLineEdit()
        dlg._on_voiceprint_select("李四", entry)
        assert entry.text() == "李四"

    def test_select_placeholder_does_not_fill(self, app):
        dlg = _make_speaker_dialog(app)
        entry = QLineEdit()
        dlg._on_voiceprint_select("（从音色库选择）", entry)
        assert entry.text() == ""


# ── SPK-005：保存到音色库 ───────────────────────────────────


class TestSaveToLibrary:
    def test_save_calls_add_speaker(self, app):
        emb = np.ones(512, dtype=np.float32)
        dlg = _make_speaker_dialog(app, embeddings={0: emb})
        dlg._speaker_entries[0].setText("王五")

        fake_lib = MagicMock()
        fake_profile = MagicMock()
        fake_profile.embeddings = [emb]
        fake_lib.get_speakers.return_value = {"王五": fake_profile}

        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.dialogs.QMessageBox"):
            dlg._save_to_library(0)

        fake_lib.add_speaker.assert_called_once()
        args, kwargs = fake_lib.add_speaker.call_args
        assert args[0] == "王五"
        assert np.array_equal(args[1], emb)

    def test_save_blocks_without_name(self, app):
        dlg = _make_speaker_dialog(app, embeddings={0: np.ones(512)})
        dlg._speaker_entries[0].setText("")

        fake_lib = MagicMock()
        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.dialogs.QMessageBox"):
            dlg._save_to_library(0)
        fake_lib.add_speaker.assert_not_called()


# ── SPK-007：中间片段选择（最长发言的中间 1/3） ─────────────


class TestMiddleSegmentWindow:
    def test_middle_third_window(self):
        from gui.dialogs import _middle_third_window
        start, end = _middle_third_window(0, 3000)
        assert start == pytest.approx(1000)
        assert end == pytest.approx(2000)

    def test_extract_picks_longest_segment_middle(self, app):
        """SPK-007：应选最长发言段，并对其中间 1/3 提取。"""
        # spk 0 有一短一长两段；应选长段 [10000,40000] → 中间 [20000,30000]
        sentences = [
            {"spk_id": 0, "start": 0, "end": 1000},
            {"spk_id": 0, "start": 10000, "end": 40000},
            {"spk_id": 1, "start": 2000, "end": 5000},
        ]
        # 用真实 WAV 文件（足够长），mock CAM++ 提取
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            import soundfile as sf
            sr = 16000
            sf.write(wav_path, np.zeros(45 * sr, dtype=np.float32), sr)

            dlg = _make_speaker_dialog(
                app, embeddings={0: np.ones(512)},
                audio_path=wav_path, sentences=sentences,
            )

            captured = {}
            fixed_emb = np.arange(512, dtype=np.float32)

            class _FakeModel:
                def __init__(self, *a, **k):
                    pass

                def inference(self, input=None, **k):
                    captured["len"] = len(input)
                    return [{"spk_embedding": fixed_emb}]

            # mock funasr.AutoModel
            fake_funasr = MagicMock()
            fake_funasr.AutoModel = _FakeModel
            with patch.dict(sys.modules, {"funasr": fake_funasr}):
                result = dlg._extract_middle_segment_embedding(0, duration_sec=5)

            assert result is not None
            assert np.array_equal(np.asarray(result), fixed_emb)
            # 中间 1/3 长度约 10s @16kHz = 160000 样本
            assert captured["len"] == pytest.approx(160000, rel=0.05)
        finally:
            os.remove(wav_path)
