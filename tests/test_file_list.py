"""
文件列表测试（PySide6 QTableWidget 版本）
"""

import pytest


@pytest.mark.gui
class TestFileList:
    """文件列表相关测试"""

    def test_file_manager_import(self):
        """测试 FileManager 可以导入"""
        from file_manager import FileManager, FileStatus
        assert FileManager is not None

    def test_home_page_has_refresh_method(self):
        """测试 HomePage 有 refresh_file_list 方法"""
        from gui.home_page import HomePage
        assert hasattr(HomePage, 'refresh_file_list')

    def test_file_list_view_has_set_files(self):
        """测试 FileListView 有 set_files 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, 'set_files')

    def test_file_list_view_has_get_selected(self):
        """测试 FileListView 有 get_selected 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, 'get_selected')

    def test_file_list_view_has_clear_selection(self):
        """测试 FileListView 有 clear_selection 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, 'clear_selection')

    def test_file_list_view_has_create_row(self):
        """测试 FileListView 有 _create_row 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_create_row')

    def test_file_list_view_has_create_action_buttons(self):
        """测试 FileListView 有 _create_action_buttons 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_create_action_buttons')

    def test_file_list_view_has_file_action_signal(self):
        """测试 FileListView 有 file_action 信号"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, 'file_action')

    def test_file_list_view_has_file_selected_signal(self):
        """测试 FileListView 有 file_selected 信号"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, 'file_selected')
