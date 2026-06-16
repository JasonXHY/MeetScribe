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


def _make_file(path, name=None, status="pending", topic="", duration="00:10", size="1MB"):
    return {
        "path": path,
        "name": name or path.split("/")[-1],
        "topic": topic,
        "duration": duration,
        "size": size,
        "status": status,
        "queue_pos": None,
    }


def _row_widgets(view, row):
    """返回某行可标识的控件实例：状态单元格 item + 操作列 cellWidget"""
    table = view._table
    return {
        "name_item": table.item(row, 1),
        "status_item": table.item(row, 5),
        "action_widget": table.cellWidget(row, 6),
    }


@pytest.mark.gui
@pytest.mark.integration
class TestFileListIncrementalUpdate:
    """FILE-004 增量更新（不全量重建）"""

    def test_incremental_update_keeps_unchanged_rows(self, qtbot):
        """连续两次 refresh 相同 files，不应重建任何行（控件实例不变）"""
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="done"),
            _make_file("/c.wav", status="processing"),
        ]
        view.refresh(files)

        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        # 用等价但不同的 dict 列表再刷一次（模拟 home_page 每次重新构造 file_data）
        files2 = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="done"),
            _make_file("/c.wav", status="processing"),
        ]
        view.refresh(files2)

        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}

        for path in before:
            assert after[path]["status_item"] is before[path]["status_item"], (
                f"{path} status item recreated"
            )
            assert after[path]["action_widget"] is before[path]["action_widget"], (
                f"{path} action widget recreated"
            )
            assert after[path]["name_item"] is before[path]["name_item"], (
                f"{path} name item recreated"
            )

    def test_status_change_updates_only_that_row(self, qtbot):
        """单文件 PENDING→DONE 只更新该行，其它行控件实例不变"""
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="pending"),
            _make_file("/c.wav", status="pending"),
        ]
        view.refresh(files)
        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [
            _make_file("/a.wav", status="pending"),
            _make_file("/b.wav", status="done"),  # 变化
            _make_file("/c.wav", status="pending"),
        ]
        view.refresh(files2)
        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}

        # 未变化的行：控件实例保持
        for path in ("/a.wav", "/c.wav"):
            assert after[path]["status_item"] is before[path]["status_item"]
            assert after[path]["action_widget"] is before[path]["action_widget"]

        # 变化行 b：状态文本更新为已完成（状态 item 实例保持，仅内容更新）
        assert after["/b.wav"]["status_item"] is before["/b.wav"]["status_item"]
        assert "完成" in after["/b.wav"]["status_item"].toolTip()

    def test_add_single_file_appends_one_row(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [_make_file("/a.wav"), _make_file("/b.wav")]
        view.refresh(files)
        assert view._table.rowCount() == 2
        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [_make_file("/a.wav"), _make_file("/b.wav"), _make_file("/c.wav")]
        view.refresh(files2)
        assert view._table.rowCount() == 3
        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}
        # 旧两行保持
        for path in ("/a.wav", "/b.wav"):
            assert after[path]["status_item"] is before[path]["status_item"]
        # 新行存在
        assert after["/c.wav"]["status_item"] is not None

    def test_remove_single_file_removes_one_row(self, qtbot):
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        files = [_make_file("/a.wav"), _make_file("/b.wav"), _make_file("/c.wav")]
        view.refresh(files)
        before = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files)}

        files2 = [_make_file("/a.wav"), _make_file("/c.wav")]
        view.refresh(files2)
        assert view._table.rowCount() == 2
        after = {f["path"]: _row_widgets(view, i) for i, f in enumerate(files2)}
        # 保留的行控件实例不变
        for path in ("/a.wav", "/c.wav"):
            assert after[path]["status_item"] is before[path]["status_item"]
            assert after[path]["action_widget"] is before[path]["action_widget"]


@pytest.mark.gui
@pytest.mark.integration
class TestMergedGroupBadge:
    """FILE-006 合并组 📎 显示"""

    def test_merged_group_shows_badge(self, qtbot):
        """属于合并组（merged=True）的行名称带 📎 前缀，普通行不带。

        徽标须在创建行与就地更新行两种路径下都生效（兼容 G7 增量更新）。
        """
        from gui.file_list_view import FileListView
        view = FileListView()
        qtbot.addWidget(view)

        normal = _make_file("/normal.wav", name="normal.wav")
        merged = _make_file("/merged.wav", name="dual-track")
        merged["merged"] = True

        # 创建行路径
        view.refresh([normal, merged])
        assert "📎" not in view._table.item(0, 1).text(), "普通行不应带 📎"
        assert "📎" in view._table.item(1, 1).text(), "合并组行应带 📎"

        # 就地更新路径：普通行变为合并组行（路径不变，仅 merged 变化）
        normal2 = _make_file("/normal.wav", name="normal.wav")
        normal2["merged"] = True
        view.refresh([normal2, merged])
        assert "📎" in view._table.item(0, 1).text(), "就地更新为合并组后应带 📎"
