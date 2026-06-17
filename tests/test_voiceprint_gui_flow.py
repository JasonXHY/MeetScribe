#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-G15 — 声纹 GUI 流行为测试（VPR-002/003/004）。

- VPR-003：rename_speaker 三类行为（成功迁移 / 目标已存在 / 源不存在）+ GUI _edit_speaker。
- VPR-004：GUI _delete_speaker 确认弹窗 → remove_speaker + 列表刷新。
- VPR-002：AddVoiceDialog._save 的 extract→save 链路（embedding 提取用 mock）。

不依赖 funasr / CAM++：提取边界用 mock 注入固定向量。
"""

import time

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from voiceprint import VoiceprintLibrary

pytestmark = pytest.mark.integration


@pytest.fixture
def lib(tmp_path):
    """空音色库，指向临时文件。"""
    return VoiceprintLibrary(library_path=str(tmp_path / "vp.json"))


def _populate(lib, name="张三"):
    lib.add_speaker(name, np.random.rand(512).astype(np.float32),
                    "manual_recording", quality=0.9)
    return lib


# ── VPR-003：rename_speaker 行为 ──────────────────────────────


class TestRenameSpeakerBehavior:
    def test_rename_migrates_embeddings_and_created_at(self, lib):
        _populate(lib, "张三")
        before = lib.get_speakers()["张三"]
        old_embeddings = before.embeddings
        old_created = before.created_at

        ok = lib.rename_speaker("张三", "张总")
        assert ok is True

        speakers = lib.get_speakers()
        assert "张三" not in speakers
        assert "张总" in speakers
        # embedding 与 created_at 迁移保留
        assert speakers["张总"].embeddings == old_embeddings
        assert speakers["张总"].created_at == old_created

    def test_rename_persists_to_disk(self, lib, tmp_path):
        _populate(lib, "张三")
        lib.rename_speaker("张三", "张总")

        # 重新加载，确认持久化
        reloaded = VoiceprintLibrary(library_path=str(tmp_path / "vp.json"))
        names = set(reloaded.get_speakers().keys())
        assert names == {"张总"}

    def test_rename_rejects_when_target_exists(self, lib):
        _populate(lib, "张三")
        _populate(lib, "李四")
        assert lib.rename_speaker("张三", "李四") is False
        # 两者都还在
        assert set(lib.get_speakers()) == {"张三", "李四"}

    def test_rename_returns_false_when_source_missing(self, lib):
        assert lib.rename_speaker("不存在", "新名") is False


# ── VPR-003：GUI _edit_speaker 集成 ──────────────────────────


class TestEditSpeakerGui:
    def test_edit_speaker_renames_and_refreshes(self, qtbot, lib):
        from gui.voiceprint_page import VoiceprintPage

        _populate(lib, "张三")
        page = VoiceprintPage()
        qtbot.addWidget(page)
        page._library = lib  # 注入临时库
        page.refresh_list()

        with patch("gui.voiceprint_page.QInputDialog.getText",
                   return_value=("张总", True)):
            page._edit_speaker("张三")

        assert "张总" in lib.get_speakers()
        assert "张三" not in lib.get_speakers()


# ── VPR-004：GUI _delete_speaker 确认路径 ────────────────────


class TestDeleteSpeakerGui:
    def test_delete_confirmed_calls_remove_and_refreshes(self, qtbot):
        from gui.voiceprint_page import VoiceprintPage
        from PySide6.QtWidgets import QMessageBox

        fake_lib = MagicMock()
        page = VoiceprintPage()
        qtbot.addWidget(page)
        page._library = fake_lib

        with patch("gui.voiceprint_page.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            page._delete_speaker("张三")

        fake_lib.remove_speaker.assert_called_once_with("张三")

    def test_delete_cancelled_does_not_remove(self, qtbot):
        from gui.voiceprint_page import VoiceprintPage
        from PySide6.QtWidgets import QMessageBox

        fake_lib = MagicMock()
        page = VoiceprintPage()
        qtbot.addWidget(page)
        page._library = fake_lib

        with patch("gui.voiceprint_page.QMessageBox.question",
                   return_value=QMessageBox.No):
            page._delete_speaker("张三")

        fake_lib.remove_speaker.assert_not_called()


# ── VPR-002：AddVoiceDialog 录入链路 ─────────────────────────


class TestAddVoiceSaveFlow:
    def test_save_calls_add_speaker_with_correct_source_quality(self, qtbot):
        from gui.voiceprint_page import AddVoiceDialog

        dialog = AddVoiceDialog()
        qtbot.addWidget(dialog)

        # 模拟提取已完成：填入姓名 + 固定 embedding
        fixed_embedding = np.ones(512, dtype=np.float32)
        dialog._name_entry.setText("王五")
        dialog._temp_embedding = fixed_embedding

        fake_lib = MagicMock()
        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.voiceprint_page.QMessageBox"):
            dialog._save()

        fake_lib.add_speaker.assert_called_once()
        args, kwargs = fake_lib.add_speaker.call_args
        # 姓名、来源、quality 与实现约定一致
        assert args[0] == "王五"
        assert np.array_equal(args[1], fixed_embedding)
        assert args[2] == "manual_recording"
        assert kwargs.get("quality") == 0.90

    def test_save_blocks_without_embedding(self, qtbot):
        from gui.voiceprint_page import AddVoiceDialog

        dialog = AddVoiceDialog()
        qtbot.addWidget(dialog)
        dialog._name_entry.setText("无声纹")
        dialog._temp_embedding = None

        fake_lib = MagicMock()
        with patch("voiceprint.VoiceprintLibrary", return_value=fake_lib), \
             patch("gui.voiceprint_page.QMessageBox"):
            dialog._save()

        # 未提取声纹时不得写库
        fake_lib.add_speaker.assert_not_called()
