"""
GUI 启动测试
注意: 这些测试需要图形界面环境
"""

import pytest


@pytest.mark.gui
class TestGUIStartup:
    """GUI 启动相关测试"""

    def test_main_import(self):
        """测试 main 模块可以导入"""
        import main
        assert main is not None

    def test_app_class_exists(self):
        """测试 MeetScribeApp 类存在"""
        from gui.app import MeetScribeApp
        assert MeetScribeApp is not None

    def test_styles_loaded(self):
        """测试样式模块加载"""
        from gui.styles import C_ACCENT, C_BG, C_TXT1
        assert C_ACCENT is not None
        assert C_BG is not None
        assert C_TXT1 is not None

    def test_sidebar_navigation(self):
        """测试侧边栏导航项"""
        from gui.sidebar import Sidebar
        assert Sidebar is not None

    def test_home_page_exists(self):
        """测试主页类存在"""
        from gui.home_page import HomePage
        assert HomePage is not None

    def test_settings_page_exists(self):
        """测试设置页类存在"""
        from gui.settings_page import SettingsPage
        assert SettingsPage is not None

    def test_transcription_handler_exists(self):
        """测试转写处理器存在"""
        from gui.transcription import TranscriptionHandler
        assert TranscriptionHandler is not None
