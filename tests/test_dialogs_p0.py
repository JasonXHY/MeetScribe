"""
测试 dialogs.py 5个P0级功能修复
"""
import os
import sys
import tempfile
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.dialogs import (
    SpeakerDialog, ExportDialog, parse_speakers_from_result,
    _parse_speakers_json, _parse_speakers_text,
    _parse_speaker_names_from_text, _apply_saved_names,
)


# ── P0-4: parse_speakers_from_result 双轨说话人解析 ──────────

class TestParseSpeakersDualTrack:
    def test_basic_speaker_format(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] Speaker 1** hello\n"
            "**[00:05] Speaker 2** world\n"
            "**[00:10] Speaker 1** again\n",
            encoding="utf-8",
        )
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2
        ids = {s["spk_id"] for s in speakers}
        assert 0 in ids and 1 in ids

    def test_dual_track_local_remote(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] 本地-1** hello\n"
            "**[00:05] 远程-1** world\n"
            "**[00:10] 本地-1** again\n",
            encoding="utf-8",
        )
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2
        labels = {s["label"] for s in speakers}
        assert "本地-1" in labels
        assert "远程-1" in labels

    def test_name_pattern_format(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] 张三** hello\n"
            "**[00:05] 李四** world\n",
            encoding="utf-8",
        )
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2
        names = {s["name"] for s in speakers}
        assert "张三" in names
        assert "李四" in names

    def test_json_format(self, tmp_path):
        result = tmp_path / "result.json"
        data = {
            "segments": [
                {"speaker_id": 0, "text": "hello"},
                {"speaker_id": 1, "text": "world"},
                {"speaker_id": 0, "text": "again"},
            ]
        }
        result.write_text(json.dumps(data), encoding="utf-8")
        speakers = parse_speakers_from_result(str(result))
        assert len(speakers) == 2

    def test_saved_names_applied(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] Speaker 1** hello\n"
            "**[00:05] Speaker 2** world\n",
            encoding="utf-8",
        )
        speakers = parse_speakers_from_result(
            str(result), saved_names={"1": "张三", "2": "李四"}
        )
        names = {s["name"] for s in speakers}
        assert "张三" in names
        assert "李四" in names

    def test_dual_track_saved_names(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text(
            "**[00:00] 本地-1** hello\n"
            "**[00:05] 远程-1** world\n",
            encoding="utf-8",
        )
        speakers = parse_speakers_from_result(
            str(result), saved_names={"本地-1": "张三", "远程-1": "李四"}
        )
        names = {s["name"] for s in speakers}
        assert "张三" in names
        assert "李四" in names

    def test_percentage_calculation(self, tmp_path):
        result = tmp_path / "result.md"
        lines = ["**[00:00] Speaker 1** line\n"] * 7 + ["**[00:05] Speaker 2** line\n"] * 3
        result.write_text("\n".join(lines), encoding="utf-8")
        speakers = parse_speakers_from_result(str(result))
        total_pct = sum(s["pct"] for s in speakers)
        assert abs(total_pct - 100.0) < 0.1

    def test_no_speakers_returns_empty(self, tmp_path):
        result = tmp_path / "result.md"
        result.write_text("No speaker info here\n", encoding="utf-8")
        speakers = parse_speakers_from_result(str(result))
        assert speakers == [] or all(s["name"] for s in speakers)


class TestParseSpeakersHelper:
    def test_parse_speakers_json_basic(self):
        content = json.dumps({
            "segments": [
                {"speaker_id": 0, "text": "a"},
                {"speaker_id": 1, "text": "b"},
            ]
        })
        speakers = _parse_speakers_json(content)
        assert 0 in speakers
        assert 1 in speakers

    def test_parse_speakers_text_dual_track(self):
        content = "**[00:00] 本地-1** hello\n**[00:05] 远程-1** world\n"
        speakers = _parse_speakers_text(content)
        assert "本地-1" in speakers
        assert "远程-1" in speakers

    def test_parse_speaker_names_from_text(self):
        content = "**[00:00] 张三** hello\n**[00:05] 李四** world\n"
        speakers = _parse_speaker_names_from_text(content)
        names = [s["name"] for s in speakers.values()]
        assert "张三" in names
        assert "李四" in names

    def test_apply_saved_names_empty_speakers(self):
        speakers = {}
        saved = {"1": "张三"}
        result = _apply_saved_names(speakers, saved)
        assert "张三" in [s["name"] for s in result.values()]

    def test_apply_saved_names_dual_track(self):
        speakers = {"本地-1": {"spk_id": "本地-1", "label": "本地-1", "name": "", "pct": 50}}
        saved = {"本地-1": "张三"}
        result = _apply_saved_names(speakers, saved)
        assert result["本地-1"]["name"] == "张三"


# ── P0-1/2/3: SpeakerDialog 方法存在性检查 ──────────

class TestSpeakerDialogMethods:
    def test_has_voiceprint_select(self):
        assert hasattr(SpeakerDialog, "_on_voiceprint_select")

    def test_has_match_suggestion(self):
        assert hasattr(SpeakerDialog, "_add_match_suggestion")

    def test_has_accept_suggestion(self):
        assert hasattr(SpeakerDialog, "_accept_suggestion")

    def test_has_extract_middle_segment(self):
        assert hasattr(SpeakerDialog, "_extract_middle_segment_embedding")

    def test_has_get_embedding_by_id(self):
        assert hasattr(SpeakerDialog, "_get_embedding_by_id")

    def test_has_get_speaker_embedding(self):
        assert hasattr(SpeakerDialog, "_get_speaker_embedding")

    def test_has_refresh_speaker_list(self):
        assert hasattr(SpeakerDialog, "_refresh_speaker_list")


class TestGetEmbeddingById:
    def test_int_key(self):
        emb = {0: [1, 2, 3], 1: [4, 5, 6]}
        assert SpeakerDialog._get_embedding_by_id(emb, 0) == [1, 2, 3]

    def test_str_int_key(self):
        emb = {0: [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, "0") == [1, 2, 3]

    def test_spk_n_format(self):
        emb = {0: [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, "spk-0") == [1, 2, 3]

    def test_direct_key(self):
        emb = {"spk-0": [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, "spk-0") == [1, 2, 3]

    def test_not_found(self):
        emb = {0: [1, 2, 3]}
        assert SpeakerDialog._get_embedding_by_id(emb, 99) is None


# ── P0-5: ExportDialog 自动打开文件夹 ──────────

class TestExportDialogAutoOpen:
    def test_source_contains_explorer_select(self):
        src = open(
            os.path.join(os.path.dirname(__file__), "..", "src", "gui", "dialogs.py"),
            encoding="utf-8",
        ).read()
        assert 'explorer' in src
        assert '/select,' in src

    def test_source_contains_open_folder_logic(self):
        src = open(
            os.path.join(os.path.dirname(__file__), "..", "src", "gui", "dialogs.py"),
            encoding="utf-8",
        ).read()
        assert 'subprocess.Popen' in src
        assert 'CREATE_NO_WINDOW' in src
