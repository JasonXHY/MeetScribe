#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 配置相关功能测试（合并自 test_settings_engine / test_settings_dialogs_g16 / test_first_launch / test_model_registry）。"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QLineEdit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config

pytestmark = pytest.mark.integration


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    """创建 QApplication 实例（模块级共享）"""
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def config():
    """创建临时 Config 实例"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{}')
        temp_path = f.name
    try:
        cfg = Config(temp_path)
        yield cfg
    finally:
        os.remove(temp_path)


def _create_settings_page(config):
    """辅助函数：创建 SettingsPage 实例"""
    from gui.settings_page import SettingsPage
    with patch('gui.settings_page.QMessageBox'):
        page = SettingsPage(config=config, log_callback=lambda msg: None)
    return page


def _make_speaker_dialog(app, speakers=None, embeddings=None,
                         audio_path=None, sentences=None, qualities=None):
    """辅助函数：构造最小 SpeakerDialog"""
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


# ═══════════════════════════════════════════════════════════════
# 1. 引擎参数 ComboBox（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestEngineComboBoxes:
    """引擎参数 ComboBox 存在且有正确选项"""

    def test_punc_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_punc_var')
        assert page._punc_var.count() == 2

    def test_punc_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._punc_var.itemText(i) for i in range(page._punc_var.count())]
        assert "自动 (ct-punc)" in options
        assert "关闭" in options

    def test_garble_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_garble_var')
        assert page._garble_var.count() == 2

    def test_garble_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._garble_var.itemText(i) for i in range(page._garble_var.count())]
        assert "开启 (中文模式)" in options
        assert "关闭" in options

    def test_vad_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_vad_var')
        assert page._vad_var.count() == 3

    def test_vad_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._vad_var.itemText(i) for i in range(page._vad_var.count())]
        assert "适中 (推荐)" in options
        assert "高 (更多分段)" in options
        assert "低 (更少分段)" in options

    def test_device_combo_exists(self, config, app):
        page = _create_settings_page(config)
        assert hasattr(page, '_device_var')
        assert page._device_var.count() == 2

    def test_device_combo_options(self, config, app):
        page = _create_settings_page(config)
        options = [page._device_var.itemText(i) for i in range(page._device_var.count())]
        assert "CPU" in options
        assert "CUDA (GPU)" in options


# ═══════════════════════════════════════════════════════════════
# 2. 保存配置（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestSaveConfig:
    """保存配置包含引擎参数 key"""

    def test_save_includes_punc_restore(self, config, app):
        page = _create_settings_page(config)
        page._punc_var.setCurrentText("关闭")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("punc_restore") == "关闭"

    def test_save_includes_garble_filter(self, config, app):
        page = _create_settings_page(config)
        page._garble_var.setCurrentText("关闭")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("garble_filter") == "关闭"

    def test_save_includes_vad_sensitivity(self, config, app):
        page = _create_settings_page(config)
        page._vad_var.setCurrentText("高 (更多分段)")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("vad_sensitivity") == "高 (更多分段)"

    def test_save_includes_device(self, config, app):
        page = _create_settings_page(config)
        page._device_var.setCurrentText("CUDA (GPU)")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("device") == "CUDA (GPU)"

    def test_save_includes_all_engine_keys(self, config, app):
        page = _create_settings_page(config)
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        d = config.as_dict()
        assert "punc_restore" in d
        assert "garble_filter" in d
        assert "vad_sensitivity" in d
        assert "device" in d


# ═══════════════════════════════════════════════════════════════
# 3. 恢复配置（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestRestoreConfig:
    """恢复配置能正确还原引擎参数"""

    def test_restore_punc(self, config, app):
        config.set("punc_restore", "关闭")
        page = _create_settings_page(config)
        assert page._punc_var.currentText() == "关闭"

    def test_restore_garble(self, config, app):
        config.set("garble_filter", "关闭")
        page = _create_settings_page(config)
        assert page._garble_var.currentText() == "关闭"

    def test_restore_vad(self, config, app):
        config.set("vad_sensitivity", "高 (更多分段)")
        page = _create_settings_page(config)
        assert page._vad_var.currentText() == "高 (更多分段)"

    def test_restore_device(self, config, app):
        config.set("device", "CUDA (GPU)")
        page = _create_settings_page(config)
        assert page._device_var.currentText() == "CUDA (GPU)"


# ═══════════════════════════════════════════════════════════════
# 4. Ollama 本地 LLM 配置（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestOllamaConfig:
    """Ollama 本地 LLM 地址 / 模型配置（SET-016）"""

    def test_ollama_address_default(self, config, app):
        page = _create_settings_page(config)
        assert page._ollama_url_entry.text() == "http://localhost:11434/v1"
        assert page._ollama_model_entry.text() == "qwen3:1.7b"

    def test_ollama_address_save_restore(self, config, app):
        page = _create_settings_page(config)
        page._ollama_url_entry.setText("http://host:1234/v1")
        page._ollama_model_entry.setText("llama3")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()

        assert config.get("ollama_url") == "http://host:1234/v1"
        assert config.get("ollama_model") == "llama3"

        page2 = _create_settings_page(config)
        assert page2._ollama_url_entry.text() == "http://host:1234/v1"
        assert page2._ollama_model_entry.text() == "llama3"


# ═══════════════════════════════════════════════════════════════
# 5. 转写输出目录 save/restore（test_settings_engine）
# ═══════════════════════════════════════════════════════════════


class TestOutputDirRoundtrip:
    """T-G3: 转写输出目录 save/restore 必须用同一个配置键。"""

    def test_output_dir_save_restore_roundtrip(self, config, app):
        page = _create_settings_page(config)
        page._out_dir_entry.setText("/custom/out/dir")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()

        page2 = _create_settings_page(config)
        assert page2._out_dir_entry.text() == "/custom/out/dir"

    def test_output_dir_saved_under_transcript_dir_key(self, config, app):
        """权威键为 transcript_dir（与 app.get_output_dir 一致）。"""
        page = _create_settings_page(config)
        page._out_dir_entry.setText("/custom/out/dir")
        with patch('gui.settings_page.QMessageBox'):
            page._on_save()
        assert config.get("transcript_dir") == "/custom/out/dir"


# ═══════════════════════════════════════════════════════════════
# 6. API Key 明文切换（test_settings_dialogs_g16）
# ═══════════════════════════════════════════════════════════════


class TestApiKeyToggle:
    def test_toggle_switches_echo_mode(self, config, app):
        from gui.settings_page import SettingsPage
        with patch('gui.settings_page.QMessageBox'):
            page = SettingsPage(config=config, log_callback=lambda m: None)

        assert page._api_key_entry.echoMode() == QLineEdit.Password

        page._toggle_api_key()
        assert page._api_key_entry.echoMode() == QLineEdit.Normal

        page._toggle_api_key()
        assert page._api_key_entry.echoMode() == QLineEdit.Password


# ═══════════════════════════════════════════════════════════════
# 7. 批量替换（test_settings_dialogs_g16）
# ═══════════════════════════════════════════════════════════════


class TestBatchReplace:
    def test_batch_replace_sets_name_on_selected_speaker(self, app):
        dlg = _make_speaker_dialog(app)
        dlg._batch_from_combo.setCurrentIndex(0)
        dlg._batch_to_entry.setText("张三")

        with patch("gui.dialogs.QMessageBox"):
            dlg._do_batch_replace()

        assert dlg._speakers[0]["name"] == "张三"
        assert dlg._speaker_entries[0].text() == "张三"

    def test_batch_replace_empty_name_noop(self, app):
        dlg = _make_speaker_dialog(app)
        dlg._batch_from_combo.setCurrentIndex(0)
        dlg._batch_to_entry.setText("")
        with patch("gui.dialogs.QMessageBox"):
            dlg._do_batch_replace()
        assert dlg._speakers[0]["name"] == ""


# ═══════════════════════════════════════════════════════════════
# 8. 音色库下拉选择填充（test_settings_dialogs_g16）
# ═══════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════
# 9. 保存到音色库（test_settings_dialogs_g16）
# ═══════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════
# 10. 中间片段选择（test_settings_dialogs_g16）
# ═══════════════════════════════════════════════════════════════


class TestMiddleSegmentWindow:
    def test_middle_third_window(self):
        from gui.dialogs import _middle_third_window
        start, end = _middle_third_window(0, 3000)
        assert start == pytest.approx(1000)
        assert end == pytest.approx(2000)

    def test_extract_picks_longest_segment_middle(self, app):
        """SPK-007：应选最长发言段，并对其中间 1/3 提取。"""
        sentences = [
            {"spk_id": 0, "start": 0, "end": 1000},
            {"spk_id": 0, "start": 10000, "end": 40000},
            {"spk_id": 1, "start": 2000, "end": 5000},
        ]
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

            fake_funasr = MagicMock()
            fake_funasr.AutoModel = _FakeModel
            with patch.dict(sys.modules, {"funasr": fake_funasr}):
                result = dlg._extract_middle_segment_embedding(0, duration_sec=5)

            assert result is not None
            assert np.array_equal(np.asarray(result), fixed_emb)
            assert captured["len"] == pytest.approx(160000, rel=0.05)
        finally:
            os.remove(wav_path)


# ═══════════════════════════════════════════════════════════════
# 11. 首次启动引导（test_first_launch）
# ═══════════════════════════════════════════════════════════════


class FakeConfig:
    """轻量内存版 Config，记录 set/save 调用，便于断言。"""

    def __init__(self, data=None):
        self._data = dict(data or {})
        self.saved = False

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, save=True):
        self._data[key] = value
        if save:
            self.save()

    def save(self):
        self.saved = True


@pytest.fixture
def fake_config():
    return FakeConfig({"first_launch": True})


def test_check_first_launch_defaults_true_when_no_config():
    from gui.first_launch import check_first_launch
    assert check_first_launch(None) is True


def test_check_first_launch_reads_config(fake_config):
    from gui.first_launch import check_first_launch
    assert check_first_launch(fake_config) is True
    fake_config.set("first_launch", False)
    assert check_first_launch(fake_config) is False


def test_model_worker_calls_real_download_all_missing():
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.download_all_missing.return_value = (True, "所有模型下载完成")

    with patch("transcriber.ModelManager", return_value=mock_mgr):
        worker = first_launch.ModelDownloadWorker("/tmp/models_cache")
        worker.run()

    mock_mgr.download_all_missing.assert_called_once()


def test_model_worker_emits_finished_on_success():
    from gui import first_launch

    mock_mgr = MagicMock()
    mock_mgr.download_all_missing.return_value = (True, "完成")

    received = []
    with patch("transcriber.ModelManager", return_value=mock_mgr):
        worker = first_launch.ModelDownloadWorker("/tmp/mc")
        worker.finished.connect(lambda ok, msg: received.append((ok, msg)))
        worker.run()

    assert received and received[-1][0] is True


def test_dialog_has_beta_notice_step(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    assert dlg._stack.currentIndex() == 0


def test_builtin_api_button_sets_config(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._on_use_builtin()

    assert dlg._stack.currentIndex() == 1
    assert fake_config.get("ai_user_api_key") == ""


def test_finish_sets_first_launch_false(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._finish()

    assert fake_config.get("first_launch") is False


def test_skip_all_sets_first_launch_false(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    dlg._on_skip()

    assert fake_config.get("first_launch") is False


def test_show_first_launch_dialog_noop_when_not_first(fake_config):
    from gui import first_launch

    fake_config.set("first_launch", False)
    with patch.object(first_launch, "FirstLaunchDialog") as Dlg:
        first_launch.show_first_launch_dialog(None, fake_config)
        Dlg.assert_not_called()


def test_wizard_has_two_steps(fake_config, qtbot):
    from gui import first_launch

    dlg = first_launch.FirstLaunchDialog(config=fake_config)
    qtbot.addWidget(dlg)
    assert dlg.step_count() == 2


# ═══════════════════════════════════════════════════════════════
# 12. 模型注册表（test_model_registry）
# ═══════════════════════════════════════════════════════════════


from model_registry import (
    MODEL_REGISTRY,
    _VENDOR_ORDER,
    get_vendor_list,
    get_models_for_vendor,
    get_base_url,
    is_free_model,
)


class TestGetVendorList:
    def test_vendor_count(self):
        vendors = get_vendor_list()
        assert len(vendors) == 10

    def test_vendor_order(self):
        expected = [
            "小米 MiMo", "智谱 AI", "阿里巴巴", "DeepSeek", "腾讯混元",
            "百度文心", "月之暗面 Kimi", "讯飞星火", "百川智能", "MiniMax",
        ]
        assert get_vendor_list() == expected

    def test_returns_list(self):
        result = get_vendor_list()
        assert isinstance(result, list)

    def test_all_vendors_in_registry(self):
        for vendor in get_vendor_list():
            assert vendor in MODEL_REGISTRY


class TestGetModelsForVendor:
    def test_xiaomi_models(self):
        models = get_models_for_vendor("小米 MiMo")
        assert "mimo-v2.5-pro" in models
        assert "mimo-v2.5" in models
        assert len(models) == 2

    def test_unknown_vendor(self):
        models = get_models_for_vendor("不存在的厂商")
        assert models == []

    def test_returns_list(self):
        for vendor in _VENDOR_ORDER:
            models = get_models_for_vendor(vendor)
            assert isinstance(models, list)
            assert len(models) > 0


class TestGetBaseUrl:
    def test_xiaomi_token_plan(self):
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "token_plan")
        assert url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_xiaomi_paygo(self):
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "paygo")
        assert url == "https://api.xiaomimimo.com/v1"

    def test_zhipu_different_urls(self):
        url_tp = get_base_url("智谱 AI", "glm-4.7-flash", "token_plan")
        url_pg = get_base_url("智谱 AI", "glm-4.7-flash", "paygo")
        assert url_tp == "https://open.bigmodel.cn/api/coding/paas/v4"
        assert url_pg == "https://open.bigmodel.cn/api/paas/v4"

    def test_unknown_vendor(self):
        url = get_base_url("不存在的厂商", "model", "token_plan")
        assert url == ""

    def test_unknown_model(self):
        url = get_base_url("小米 MiMo", "不存在的模型", "token_plan")
        assert url == ""

    def test_fallback_to_token_plan(self):
        url = get_base_url("小米 MiMo", "mimo-v2.5-pro", "unknown_mode")
        assert url == "https://token-plan-cn.xiaomimimo.com/v1"

    def test_alibaba_url(self):
        url = get_base_url("阿里巴巴", "qwen3.7-max", "token_plan")
        assert url == "https://token-plan.cn-beijing.maas.aliuncs.com/v1"

    def test_deepseek_url(self):
        url = get_base_url("DeepSeek", "deepseek-v4-flash", "token_plan")
        assert url == "https://api.deepseek.com/v1"


class TestIsFreeModel:
    def test_free_models_detected(self):
        assert is_free_model("glm-4.7-flash") is True
        assert is_free_model("glm-5-turbo") is True
        assert is_free_model("spark-lite") is True
        assert is_free_model("Baichuan-M3-Plus") is True

    def test_paid_models_not_free(self):
        assert is_free_model("mimo-v2.5-pro") is False
        assert is_free_model("glm-5") is False
        assert is_free_model("qwen3.7-max") is False

    def test_free_keyword(self):
        assert is_free_model("some-model-free") is True
        assert is_free_model("FREE-model") is True
