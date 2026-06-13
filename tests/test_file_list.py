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

    def test_home_page_has_toggle_select(self):
        """测试 HomePage 有 _toggle_file_select 方法"""
        from gui.home_page import HomePage
        assert hasattr(HomePage, '_toggle_file_select')

    def test_home_page_has_update_row_selection(self):
        """测试 HomePage 有 _update_row_selection 方法"""
        from gui.home_page import HomePage
        assert hasattr(HomePage, '_update_row_selection')

    def test_home_page_has_create_file_row(self):
        """测试 HomePage 有 _create_file_row 方法"""
        from gui.home_page import HomePage
        assert hasattr(HomePage, '_create_file_row')

    def test_home_page_has_destroy_file_row(self):
        """测试 HomePage 有 _destroy_file_row 方法"""
        from gui.home_page import HomePage
        assert hasattr(HomePage, '_destroy_file_row')

    def test_home_page_has_update_file_row(self):
        """测试 HomePage 有 _update_file_row 方法"""
        from gui.home_page import HomePage
        assert hasattr(HomePage, '_update_file_row')
