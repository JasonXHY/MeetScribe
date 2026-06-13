#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe FileManager 单元测试
"""

import os
import tempfile
import pytest
from file_manager import FileManager, FileStatus, AudioFile


class TestFileManager:
    """FileManager 类测试"""

    def _make_fm(self):
        """创建一个使用临时数据文件的 FileManager"""
        fd, data_path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        return FileManager(data_file=data_path)

    def test_file_manager_import(self):
        """测试 FileManager 类可以导入"""
        assert hasattr(FileManager, '__init__')

    def test_file_manager_add_file(self):
        """测试添加文件"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            item = fm.add_file(temp_path, duration_s=10.0)
            assert item is not None
            assert item.file_path == temp_path
            assert len(fm.files) == 1
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_remove_file(self):
        """测试移除文件"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)
            assert len(fm.files) == 1

            removed = fm.remove_file(temp_path)
            assert removed is not None
            assert len(fm.files) == 0
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_update_status(self):
        """测试更新状态"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)

            fm.update_status(temp_path, FileStatus.PROCESSING)
            item = fm.get_file(temp_path)
            assert item.status == FileStatus.PROCESSING

            fm.update_status(temp_path, FileStatus.DONE)
            item = fm.get_file(temp_path)
            assert item.status == FileStatus.DONE
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_dedup(self):
        """测试文件去重"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)
            fm.add_file(temp_path, duration_s=10.0)  # 重复添加

            assert len(fm.files) == 1
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_get_file(self):
        """测试获取文件条目"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)
            item = fm.get_file(temp_path)
            assert item is not None
            assert item.file_name == os.path.basename(temp_path)

            # 不存在的文件返回 None
            assert fm.get_file("/nonexistent/file.wav") is None
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_remove_nonexistent(self):
        """测试移除不存在的文件返回 None"""
        fm = self._make_fm()
        result = fm.remove_file("/nonexistent/file.wav")
        assert result is None
        os.remove(fm._data_file)

    def test_file_manager_clear_all(self):
        """测试清空文件列表"""
        fm = self._make_fm()
        files = []
        for i in range(3):
            fd, path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            files.append(path)
            fm.add_file(path, duration_s=5.0)

        try:
            assert len(fm.files) == 3
            fm.clear_all()
            assert len(fm.files) == 0
        finally:
            for p in files:
                os.remove(p)
            os.remove(fm._data_file)

    def test_file_manager_get_pending_files(self):
        """测试获取待处理文件"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)
            pending = fm.get_pending_files()
            assert len(pending) == 1

            fm.update_status(temp_path, FileStatus.DONE)
            pending = fm.get_pending_files()
            assert len(pending) == 0
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_get_done_files(self):
        """测试获取已完成文件"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)

            # 无 result_path 时不算 done
            fm.update_status(temp_path, FileStatus.DONE)
            done = fm.get_done_files()
            assert len(done) == 0

            # 有 result_path 时算 done
            fm.update_status(temp_path, FileStatus.DONE, result_path="/some/result.md")
            done = fm.get_done_files()
            assert len(done) == 1
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_file_manager_listener(self):
        """测试变更监听器"""
        fm = self._make_fm()
        events = []
        fm.add_listener(lambda event, item: events.append(event))

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            fm.add_file(temp_path, duration_s=10.0)
            assert "added" in events
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)

    def test_audio_file_properties(self):
        """测试 AudioFile 属性方法"""
        fm = self._make_fm()
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            item = fm.add_file(temp_path, duration_s=0)
            # duration_s=0 时显示 --:--
            assert item.duration_str == "--:--"

            item.duration_s = 65
            assert item.duration_str == "01:05"

            item.duration_s = 3661
            assert item.duration_str == "1:01:01"

            # size_str
            item.file_size = 0
            assert item.size_str == "-"
            item.file_size = 512 * 1024
            assert "KB" in item.size_str
            item.file_size = 5 * 1024 * 1024
            assert "MB" in item.size_str

            # status_icon
            item.status = FileStatus.DONE
            assert "[OK]" in item.status_icon
            item.status = FileStatus.FAILED
            assert "[ERR]" in item.status_icon
        finally:
            os.remove(temp_path)
            os.remove(fm._data_file)
