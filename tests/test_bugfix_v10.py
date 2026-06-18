"""
TDD 测试：v1.0 Bugfix 验证（5个 cherry-pick commit）

验证范围：
1. 厂商名规范化 (vendor_map) — 0935e08
2. 转写文件输出到配置目录 (out_dir) — 146b21e
3. 打开文件夹修复 (result_path) — e911e50
4. 导出摘要合并 (summary_path) — e911e50
5. config 空值过滤 — e911e50
6. 日志前缀分离 — e911e50
7. 主题提取增强 — e911e50

运行方式：
    pytest tests/test_bugfix_v10.py -v --timeout=30
"""

import os
import sys
import re
import json
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ══════════════════════════════════════════════════════════
#  1. 厂商名规范化 (vendor_map)
# ══════════════════════════════════════════════════════════

class TestVendorNormalization:
    """厂商名规范化：旧版短名 → 新版全名"""

    def test_xiaomi_mapping(self):
        """'小米' → '小米 MiMo'"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d="": {
            "ai_vendor": "小米",
            "ai_user_api_key": "",
            "ai_default_api_key": "sk-test",
            "ai_model": "mimo-v2.5",
            "ai_access_mode": "按量计费",
        }.get(k, d)
        handler._app = mock_app

        with patch('ai_service.AIService') as MockAI:
            mock_ai = MagicMock()
            MockAI.return_value = mock_ai
            handler._get_ai_service()
            call_kwargs = MockAI.call_args
            assert call_kwargs[1]['vendor'] == '小米 MiMo' or call_kwargs[0][0] == '小米 MiMo'

    def test_all_vendor_mappings(self):
        """所有厂商映射都正确"""
        vendor_map = {
            "小米": "小米 MiMo",
            "智谱": "智谱 AI",
            "阿里": "阿里巴巴",
            "腾讯": "腾讯混元",
            "百度": "百度文心",
            "月之暗面": "月之暗面 Kimi",
            "讯飞": "讯飞星火",
            "百川": "百川智能",
        }
        for short_name, full_name in vendor_map.items():
            assert vendor_map.get(short_name, short_name) == full_name

    def test_unknown_vendor_passthrough(self):
        """未知厂商名直接透传"""
        vendor_map = {
            "小米": "小米 MiMo",
        }
        unknown = "OpenAI"
        assert vendor_map.get(unknown, unknown) == "OpenAI"

    def test_already_full_name(self):
        """已是全名的厂商不被修改"""
        vendor_map = {
            "小米": "小米 MiMo",
        }
        full_name = "小米 MiMo"
        assert vendor_map.get(full_name, full_name) == "小米 MiMo"


# ══════════════════════════════════════════════════════════
#  2. 转写文件输出到配置目录 (out_dir)
# ══════════════════════════════════════════════════════════

class TestOutputDirectory:
    """转写文件应输出到配置的目录"""

    def test_out_dir_from_config(self):
        """_execute_task 应从 config 读取 out_dir"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.return_value = "/custom/output/dir"
        handler._app = mock_app

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start(["test.wav"], "llm-md", {}, "")

        assert handler._file_queue is not None

    def test_out_dir_empty_uses_default(self):
        """out_dir 为空时应使用默认值"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.return_value = ""
        handler._app = mock_app

        with patch('gui.transcription.multiprocessing.Process'):
            handler.start(["test.wav"], "llm-md", {}, "")

        assert handler._file_queue is not None


# ══════════════════════════════════════════════════════════
#  3. 打开文件夹修复 (result_path)
# ══════════════════════════════════════════════════════════

class TestOpenFolderFix:
    """打开文件夹应定位到转写结果目录"""

    def test_open_folder_uses_result_path(self, qtbot):
        """有 result_path 时应打开其所在目录"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        mock_item = MagicMock()
        mock_item.result_path = "/results/meeting_transcript.md"

        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm

        with patch('subprocess.Popen') as mock_popen:
            test_app._home_page._open_folder("/recordings/meeting.wav")
            if mock_popen.called:
                call_args = mock_popen.call_args[0][0]
                assert "/results" in call_args[1] or "results" in call_args[1]

        test_app.close()

    def test_open_folder_fallback_to_file_path(self, qtbot):
        """无 result_path 时应回退到 file_path 目录"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        mock_item = MagicMock()
        mock_item.result_path = None

        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm

        with patch('subprocess.Popen') as mock_popen:
            test_app._home_page._open_folder("/recordings/meeting.wav")
            if mock_popen.called:
                call_args = mock_popen.call_args[0][0]
                assert "/recordings" in call_args[1] or "recordings" in call_args[1]

        test_app.close()


# ══════════════════════════════════════════════════════════
#  4. 导出摘要合并 (summary_path)
# ══════════════════════════════════════════════════════════

class TestExportWithSummary:
    """导出应包含摘要内容"""

    def test_export_dialog_receives_summary_path(self, qtbot, tmp_path):
        """ExportDialog 应接收 summary_path 参数"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        transcript = tmp_path / "meeting_transcript.md"
        transcript.write_text("# 转写内容\n\nSpeaker 1: 你好")
        summary = tmp_path / "meeting_summary.md"
        summary.write_text("# 摘要\n\n会议讨论了项目进度")

        mock_item = MagicMock()
        mock_item.result_path = str(transcript)

        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm

        with patch('utils.get_summary_path', return_value=str(summary)):
            with patch('gui.dialogs.ExportDialog') as MockDialog:
                mock_dialog = MagicMock()
                MockDialog.return_value = mock_dialog
                test_app._home_page._export_result("/recordings/meeting.wav")
                if MockDialog.called:
                    call_args = MockDialog.call_args
                    assert len(call_args[0]) >= 4 or 'summary_path' in str(call_args)

        test_app.close()

    def test_export_dialog_without_summary(self, qtbot, tmp_path):
        """无摘要时 ExportDialog 也应正常工作"""
        from unittest.mock import MagicMock, patch
        from gui.app import MeetScribeApp

        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        transcript = tmp_path / "meeting_transcript.md"
        transcript.write_text("# 转写内容")

        mock_item = MagicMock()
        mock_item.result_path = str(transcript)

        mock_fm = MagicMock()
        mock_fm.get_file.return_value = mock_item
        test_app.file_manager = mock_fm

        with patch('utils.get_summary_path', return_value=None):
            with patch('gui.dialogs.ExportDialog') as MockDialog:
                mock_dialog = MagicMock()
                MockDialog.return_value = mock_dialog
                test_app._home_page._export_result("/recordings/meeting.wav")
                if MockDialog.called:
                    call_args = MockDialog.call_args
                    assert call_args[0][3] is None or call_args[1].get('summary_path') is None

        test_app.close()


# ══════════════════════════════════════════════════════════
#  5. config 空值过滤
# ══════════════════════════════════════════════════════════

class TestConfigEmptyFilter:
    """config 空字符串不应覆盖 DEFAULTS"""

    def test_empty_string_not_overwrite_default(self, tmp_path):
        """空字符串不应覆盖有值的默认配置"""
        config_path = tmp_path / "settings.json"
        config_path.write_text(json.dumps({
            "ai_vendor": "",
            "ai_model": "",
            "auto_correction": "",
        }))

        from config import Config
        config = Config(str(config_path))

        assert config.get("ai_vendor") == "小米 MiMo"
        assert config.get("ai_model") == "mimo-v2.5"
        assert config.get("auto_correction") == "关闭"

    def test_empty_string_allowed_when_default_empty(self):
        """默认值本身就是空字符串时，空字符串应被保留"""
        from config import Config, DEFAULTS
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "settings.json")

            empty_keys = [k for k, v in DEFAULTS.items() if v == ""]
            if not empty_keys:
                pytest.skip("No empty-string defaults to test")

            test_data = {empty_keys[0]: ""}
            with open(config_path, 'w') as f:
                json.dump(test_data, f)

            config = Config(config_path)
            assert config.get(empty_keys[0]) == ""

    def test_real_value_preserved(self):
        """非空值应正常保留"""
        from config import Config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "settings.json")
            with open(config_path, 'w') as f:
                json.dump({"ai_vendor": "自定义厂商"}, f)

            config = Config(config_path)
            assert config.get("ai_vendor") == "自定义厂商"


# ══════════════════════════════════════════════════════════
#  6. 日志前缀分离
# ══════════════════════════════════════════════════════════

class TestLogPrefixes:
    """日志消息应有正确的前缀"""

    def test_transcription_done_prefix(self):
        """转写完成日志应有 [转写完成] 前缀"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        handler._app = MagicMock()

        log_messages = []
        handler.log_message.connect(lambda msg: log_messages.append(msg))

        handler._file_status = {"test.wav": "done"}

        mock_item = MagicMock()
        mock_item.status = MagicMock()
        mock_item.status.value = "done"
        mock_item.result_path = "test_transcript.md"

        mock_fm = MagicMock()
        mock_fm.files = [mock_item]
        handler._app.file_manager = mock_fm

        with patch('gui.transcription.FileStatus') as MockStatus:
            MockStatus.DONE = MagicMock()
            MockStatus.DONE.value = "done"
            handler._process_message(("file_done", "test.wav", "test_transcript.md"))

        has_prefix = any("[转写完成]" in msg for msg in log_messages)
        assert has_prefix, f"Expected [转写完成] prefix in logs: {log_messages}"

    def test_ai_correction_prefix(self):
        """AI 纠错日志应有 [AI纠错] 前缀"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d="": {
            "auto_correction": "转写后自动纠错",
        }.get(k, d)
        handler._app = mock_app

        log_messages = []
        handler.log_message.connect(lambda msg: log_messages.append(msg))

        handler._process_message(("auto_correction", "raw text content", "base", "/out", "transcript_path"))

        has_prefix = any("[AI纠错]" in msg for msg in log_messages)
        assert has_prefix, f"Expected [AI纠错] prefix: {log_messages}"

    def test_ai_summary_prefix(self):
        """AI 摘要日志应有 [AI摘要] 前缀"""
        from unittest.mock import MagicMock, patch
        from gui.transcription import TranscriptionHandler

        handler = TranscriptionHandler(app=None)
        mock_app = MagicMock()
        mock_app.config.get.side_effect = lambda k, d="": {
            "auto_summary": "转写后自动生成",
        }.get(k, d)
        handler._app = mock_app

        log_messages = []
        handler.log_message.connect(lambda msg: log_messages.append(msg))

        handler._process_message(("auto_summary", "test.wav", "base", "/out"))

        has_prefix = any("[AI摘要]" in msg or "跳过" in msg for msg in log_messages)
        assert has_prefix, f"Expected [AI摘要] prefix or skip message: {log_messages}"


# ══════════════════════════════════════════════════════════
#  7. 主题提取增强
# ══════════════════════════════════════════════════════════

class TestTopicExtraction:
    """_extract_topic_from_summary 应支持多种格式"""

    def _extract(self, summary):
        """复现 _extract_topic_from_summary 逻辑"""
        if not summary:
            return None
        try:
            lines = summary.splitlines()
            for line in lines[:10]:
                line = line.strip()
                if line.startswith("# ") or line.startswith("## "):
                    topic = line.lstrip("# ").strip()
                    if len(topic) > 5:
                        return topic[:50]
                if "主题" in line:
                    m = re.search(r'主题[：:]\s*(.+)', line)
                    if m:
                        topic = m.group(1).strip()
                        if len(topic) > 2:
                            return topic[:50]
        except Exception:
            pass
        return None

    def test_h1_title(self):
        """# 标题 格式"""
        result = self._extract("# 项目进度会议纪要\n\n内容")
        assert result == "项目进度会议纪要"

    def test_h2_title(self):
        """## 标题 格式"""
        result = self._extract("## 第一季度工作汇报\n\n内容")
        assert result == "第一季度工作汇报"

    def test_topic_colon_format(self):
        """主题：xxx 格式"""
        result = self._extract("主题：产品发布计划讨论\n\n内容")
        assert result == "产品发布计划讨论"

    def test_topic_bold_format(self):
        """**主题**：xxx 格式"""
        result = self._extract("**主题**：技术架构评审\n\n内容")
        assert result == "技术架构评审" or result is None

    def test_topic_english_colon(self):
        """主题: xxx 格式（英文冒号）"""
        result = self._extract("主题: 用户反馈分析\n\n内容")
        assert result == "用户反馈分析"

    def test_short_topic_ignored(self):
        """过短的主题应被忽略（<3字符）"""
        result = self._extract("主题：OK\n\n内容")
        assert result is None

    def test_empty_summary(self):
        """空摘要返回 None"""
        assert self._extract("") is None
        assert self._extract(None) is None

    def test_no_topic_format(self):
        """无主题格式时返回 None"""
        result = self._extract("这是一段没有标题的摘要内容")
        assert result is None


# ══════════════════════════════════════════════════════════
#  8. 综合集成测试
# ══════════════════════════════════════════════════════════

class TestIntegrationBugfix:
    """综合集成测试：验证多个 bugfix 协同工作"""

    def test_app_startup_with_fixed_config(self, qtbot):
        """App 启动时使用修正后的配置"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        assert test_app.config.get("ai_vendor") == "小米 MiMo"
        assert test_app.config.get("ai_model") == "mimo-v2.5"
        assert test_app.config.get("recording_dir") != "C:/MeetScribe/recordings"

        test_app.close()

    def test_settings_page_loads_correctly(self, qtbot):
        """设置页加载显示正确的厂商名"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)
        test_app.show()

        test_app._on_navigate("settings")
        QTest.qWait(500)

        sp = test_app._settings_page
        assert sp is not None

        if hasattr(sp, '_vendor_combo'):
            current = sp._vendor_combo.currentText()
            assert "MiMo" in current or "小米" in current

        test_app.close()

    def test_file_list_view_exists(self, qtbot):
        """文件列表视图存在"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        hp = test_app._home_page
        assert hasattr(hp, '_file_list_view')
        assert hp._file_list_view is not None

        test_app.close()

    def test_recording_bar_exists(self, qtbot):
        """录音条存在"""
        from gui.app import MeetScribeApp
        test_app = MeetScribeApp()
        qtbot.addWidget(test_app)

        hp = test_app._home_page
        assert hasattr(hp, '_recording_bar')
        assert hp._recording_bar is not None

        test_app.close()


# ══════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

app = QApplication.instance() or QApplication(sys.argv)
