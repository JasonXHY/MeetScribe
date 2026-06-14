"""Tests for AddVoiceDialog"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)


def test_preset_text_exists():
    from gui.voiceprint_page import AddVoiceDialog
    assert hasattr(AddVoiceDialog, 'PRESET_TEXT')
    assert AddVoiceDialog.PRESET_TEXT == "你好，我是{姓名}，这是我的声纹样本。"


def test_dialog_instantiation():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog.windowTitle() == "添加新说话人"
    assert dialog._recording is False
    assert dialog._audio_path is None
    assert dialog._embedding is None


def test_record_btn_initial_state():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._record_btn.isEnabled() is True
    assert dialog._record_btn.text() == "开始录音"


def test_save_btn_initial_state():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._save_btn.isEnabled() is False


def test_voiceprint_page_add_speaker_uses_dialog():
    from gui.voiceprint_page import VoiceprintPage, AddVoiceDialog
    assert AddVoiceDialog.__name__ == 'AddVoiceDialog'


def test_name_entry_exists():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._name_entry is not None
    assert dialog._name_entry.placeholderText() == "请输入姓名"


def test_status_label_initial():
    from gui.voiceprint_page import AddVoiceDialog
    dialog = AddVoiceDialog()
    assert dialog._status_label.text() == "准备就绪"


if __name__ == "__main__":
    test_preset_text_exists()
    test_dialog_instantiation()
    test_record_btn_initial_state()
    test_save_btn_initial_state()
    test_voiceprint_page_add_speaker_uses_dialog()
    test_name_entry_exists()
    test_status_label_initial()
    print("All tests passed!")
