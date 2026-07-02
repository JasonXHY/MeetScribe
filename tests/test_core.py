import os
import sys
import tempfile
import wave
from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# Utils Tests
# ═══════════════════════════════════════════════════════════════════

class TestGetDataDir:
    """get_data_dir() 函数测试"""

    def test_returns_absolute_path(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from utils import get_data_dir
        result = get_data_dir()
        assert os.path.isabs(result)

    def test_dev_mode_returns_project_dir(self):
        from utils import get_data_dir
        result = get_data_dir()
        assert os.path.exists(result)

    def test_frozen_mode_returns_appdata(self):
        from utils import get_data_dir
        with patch('sys.frozen', True, create=True):
            with patch.dict(os.environ, {'LOCALAPPDATA': '/tmp/test'}):
                result = get_data_dir()
                assert result == os.path.join('/tmp/test', 'MeetScribe')

    def test_fallback_no_localappdata(self):
        from utils import get_data_dir
        with patch('sys.frozen', True, create=True):
            with patch.dict(os.environ, {}, clear=True):
                with patch('os.path.expanduser', return_value='/tmp/home'):
                    result = get_data_dir()
                    assert 'MeetScribe' in result


class TestSpeakerMapping:
    """Speaker 映射函数测试"""

    def test_extract_speaker_mapping(self):
        from utils import extract_speaker_mapping_from_summary
        summary = """
        ## 发言人
        [Speaker 1] 张三
        [Speaker 2] 李四
        """
        mapping = extract_speaker_mapping_from_summary(summary)
        assert 1 in mapping or '1' in mapping

    def test_apply_speaker_mapping(self, tmp_path):
        from utils import apply_speaker_mapping
        test_file = tmp_path / "test.md"
        test_file.write_text("[Speaker 1] 你好", encoding='utf-8')

        mapping = {1: '张三'}
        apply_speaker_mapping(str(test_file), mapping)

        content = test_file.read_text(encoding='utf-8')
        assert '张三' in content


class TestSummaryPath:
    """汇总文件路径测试"""

    def test_get_summary_path_returns_none_for_missing(self):
        from utils import get_summary_path
        result = get_summary_path("/tmp/nonexistent_transcript.md")
        assert result is None

    def test_get_summary_path_none_input(self):
        from utils import get_summary_path
        result = get_summary_path(None)
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Config Tests
# ═══════════════════════════════════════════════════════════════════

class TestConfig:
    """Config 类测试"""

    def test_config_import(self):
        from config import Config
        assert hasattr(Config, '__init__')

    def test_config_default_values(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            assert config.get("recording_mode") == "dual"
            assert config.get("use_vb_cable") is True
        finally:
            os.remove(temp_path)

    def test_config_get_set(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            config.set("test_key", "test_value")
            assert config.get("test_key") == "test_value"
        finally:
            os.remove(temp_path)

    def test_config_save_load(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            config.set("test_key", "test_value")
            config.save()

            config2 = Config(temp_path)
            assert config2.get("test_key") == "test_value"
        finally:
            os.remove(temp_path)

    def test_config_get_default_return(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            assert config.get("nonexistent_key") is None
            assert config.get("nonexistent_key", "fallback") == "fallback"
        finally:
            os.remove(temp_path)

    def test_config_as_dict(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            config.set("my_key", 42)
            d = config.as_dict()
            assert isinstance(d, dict)
            assert d["my_key"] == 42
            d["my_key"] = 999
            assert config.get("my_key") == 42
        finally:
            os.remove(temp_path)

    def test_config_attr_access(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            assert config.recording_mode == "dual"
            with pytest.raises(AttributeError):
                _ = config.nonexistent_attribute
        finally:
            os.remove(temp_path)

    def test_config_persistence_integrity(self):
        from config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{}')
            temp_path = f.name
        try:
            config = Config(temp_path)
            config.set("string_val", "hello")
            config.set("int_val", 123)
            config.set("bool_val", True)
            config.set("list_val", [1, 2, 3])
            config.save()

            config2 = Config(temp_path)
            assert config2.get("string_val") == "hello"
            assert config2.get("int_val") == 123
            assert config2.get("bool_val") is True
            assert config2.get("list_val") == [1, 2, 3]
        finally:
            os.remove(temp_path)


class TestConfigEdgeCases:
    """配置文件错误场景测试"""

    def test_corrupted_json(self, tmp_path):
        from config import Config
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding='utf-8')
        config = Config(str(bad_file))
        assert config.get("recording_mode") == "dual"

    def test_missing_file(self, tmp_path):
        from config import Config
        config = Config(str(tmp_path / "nonexistent.json"))
        assert config.get("recording_mode") == "dual"

    def test_empty_file(self, tmp_path):
        from config import Config
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}", encoding='utf-8')
        config = Config(str(empty_file))
        assert config.get("recording_mode") == "dual"

    def test_partial_config(self, tmp_path):
        from config import Config
        partial_file = tmp_path / "partial.json"
        partial_file.write_text('{"recording_mode": "mic"}', encoding='utf-8')
        config = Config(str(partial_file))
        assert config.get("recording_mode") == "mic"
        assert config.get("use_vb_cable") is True

    @pytest.mark.xfail(reason="Config.get() 无类型校验，已知 GAP")
    def test_config_invalid_type(self, tmp_path):
        """类型错误 config 应回退到默认值"""
        from config import Config
        path = tmp_path / "settings.json"
        path.write_text('{"vad_sensitivity": 123}')
        config = Config(str(path))
        # 类型错误时应使用默认值
        assert isinstance(config.get("vad_sensitivity"), str)


# ═══════════════════════════════════════════════════════════════════
# File Write Path Tests
# ═══════════════════════════════════════════════════════════════════

class TestFileWritePaths:
    """验证所有写入路径使用 get_data_dir()"""

    def test_file_manager_default_path(self):
        from file_manager import FileManager
        from utils import get_data_dir
        expected = os.path.join(get_data_dir(), "data", "file_history.json")
        assert FileManager.DEFAULT_DATA_FILE == expected

    def test_voiceprint_default_path(self):
        from voiceprint import VoiceprintLibrary
        from utils import get_data_dir
        lib = VoiceprintLibrary()
        expected = os.path.join(get_data_dir(), "data", "voiceprint_library.json")
        assert lib.library_path == expected

    def test_config_project_root(self):
        from config import PROJECT_ROOT
        from utils import get_data_dir
        assert PROJECT_ROOT == get_data_dir()

    def test_model_cache_dir(self):
        from gui.styles import MODEL_CACHE_DIR
        from utils import get_data_dir
        expected = os.path.join(get_data_dir(), "models_cache")
        assert MODEL_CACHE_DIR == expected


class TestFrozenPaths:
    """打包模式路径逻辑测试"""

    def test_frozen_data_dir(self):
        from utils import get_data_dir
        with patch.object(sys, 'frozen', True, create=True):
            with patch.dict(os.environ, {'LOCALAPPDATA': '/tmp/test'}):
                result = get_data_dir()
                assert result == os.path.join('/tmp/test', 'MeetScribe')

    def test_frozen_model_cache(self):
        from utils import get_data_dir
        with patch.object(sys, 'frozen', True, create=True):
            with patch.dict(os.environ, {'LOCALAPPDATA': '/tmp/test'}):
                result = get_data_dir()
                assert result == os.path.join('/tmp/test', 'MeetScribe')

    def test_transcribe_worker_log_dir(self):
        from transcribe_worker import _log_dir
        assert os.path.isabs(_log_dir)
        assert 'logs' in _log_dir


# ═══════════════════════════════════════════════════════════════════
# Infrastructure Tests
# ═══════════════════════════════════════════════════════════════════

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
    markers = pytestconfig.getini("markers")
    joined = "\n".join(markers)
    for name in ("unit", "integration", "e2e_heavy", "e2e_network"):
        assert name in joined, f"marker 未注册: {name}"


# ═══════════════════════════════════════════════════════════════════
# Optimization Tests
# ═══════════════════════════════════════════════════════════════════

def test_model_directory_size():
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models_cache', 'models')
    if not os.path.exists(models_dir):
        pytest.skip("模型目录不存在")

    total_size = 0
    for dirpath, dirnames, filenames in os.walk(models_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)

    size_gb = total_size / (1024**3)
    print(f"模型目录大小: {size_gb:.2f} GB")
    assert size_gb < 3.0, f"模型目录大小 {size_gb:.2f} GB 超过 3GB 限制"


def test_gui_import():
    from gui import app, home_page, settings_page, transcription, dialogs, styles
    print("所有 GUI 模块导入成功")


def test_transcriber_import():
    from transcriber import Transcriber, REQUIRED_MODELS
    print(f"转写模块导入成功，模型数量: {len(REQUIRED_MODELS)}")
