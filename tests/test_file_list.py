"""
文件列表增量更新测试
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

    def test_file_list_view_has_toggle_select(self):
        """测试 FileListView 有 _toggle_select 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_toggle_select')

    def test_file_list_view_has_update_action_buttons(self):
        """测试 FileListView 有 _update_action_buttons_state 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_update_action_buttons_state')

    def test_file_list_view_has_create_file_row(self):
        """测试 FileListView 有 _create_file_row 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_create_file_row')

    def test_file_list_view_has_destroy_file_row(self):
        """测试 FileListView 有 _destroy_file_row 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_destroy_file_row')

    def test_file_list_view_has_update_file_row(self):
        """测试 FileListView 有 _update_file_row 方法"""
        from gui.file_list_view import FileListView
        assert hasattr(FileListView, '_update_file_row')
