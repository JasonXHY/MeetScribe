"""P0 feature tests for home_page.py proxy properties and update_recording_ui."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget


app = QApplication.instance() or QApplication(sys.argv)


def _make_home_page():
    from gui.home_page import HomePage

    mock_app = MagicMock()
    mock_app.config.get.return_value = "mic"
    mock_app.recorder = MagicMock()
    mock_app.recorder.paused_duration = 0

    with patch.object(HomePage, '_build'), \
         patch.object(HomePage, '_connect_signals'):
        home = HomePage(parent=None, app=mock_app)

    home._recording_bar = MagicMock()
    home._recording_bar._paused = False
    home._recording_bar.update_state = MagicMock()
    home._recording_bar.update_timer = MagicMock()

    home._file_list_view = MagicMock()
    home._file_list_view._row_widgets = {"test.mp3": {"bg": MagicMock(), "status": MagicMock()}}
    home._file_list_view._selected_files = {"test.mp3"}
    home._file_list_view.get_selected = MagicMock(return_value=["test.mp3"])

    home._log_area = MagicMock()
    home._timer_id = None
    home._record_start_time = None

    return home


def test_file_rows_property():
    home = _make_home_page()
    rows = home._file_rows
    assert isinstance(rows, dict), f"_file_rows should be dict, got {type(rows)}"
    assert "test.mp3" in rows, "_file_rows should contain 'test.mp3'"
    print("PASS: _file_rows property works")


def test_selected_files_property():
    home = _make_home_page()
    selected = home._selected_files
    assert isinstance(selected, (set, list)), f"_selected_files should be set/list, got {type(selected)}"
    assert "test.mp3" in selected, "_selected_files should contain 'test.mp3'"
    print("PASS: _selected_files property works")


def test_update_recording_ui_exists_and_callable():
    home = _make_home_page()
    assert hasattr(home, 'update_recording_ui'), "update_recording_ui method missing"
    assert callable(home.update_recording_ui), "update_recording_ui should be callable"

    home.update_recording_ui(True, False)
    home._recording_bar.update_state.assert_called_with(recording=True, paused=False)

    home.update_recording_ui(True, True)
    home._recording_bar.update_state.assert_called_with(recording=True, paused=True)

    home.update_recording_ui(False, False)
    home._recording_bar.update_state.assert_called_with(recording=False, paused=False)
    print("PASS: update_recording_ui exists and works for all 3 states")


if __name__ == "__main__":
    test_file_rows_property()
    test_selected_files_property()
    test_update_recording_ui_exists_and_callable()
    print("\nAll P0 tests passed!")
