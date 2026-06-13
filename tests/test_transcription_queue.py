#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 转写任务队列管理单元测试
"""

import pytest
from unittest.mock import MagicMock
from transcription_queue import TranscriptionQueue, TranscriptionTask


@pytest.fixture
def mock_app():
    """创建模拟的 app 对象"""
    app = MagicMock()
    app._log = MagicMock()
    return app


@pytest.fixture
def queue(mock_app):
    """创建队列实例"""
    return TranscriptionQueue(mock_app)


class TestTranscriptionTask:
    """TranscriptionTask 类测试"""

    def test_task_creation(self):
        """测试任务创建"""
        task = TranscriptionTask(
            file_paths=["file1.wav", "file2.wav"],
            fmt="md",
            speaker_names={},
            out_dir="/tmp",
            merge=False,
        )
        assert task.file_paths == ["file1.wav", "file2.wav"]
        assert task.fmt == "md"
        assert task.merge is False
        assert task.task_id is not None
        assert task.task_id.startswith("task_")

    def test_task_merge_mode(self):
        """测试合并模式任务"""
        task = TranscriptionTask(
            file_paths=["file1.wav", "file2.wav"],
            fmt="md",
            speaker_names={},
            out_dir="/tmp",
            merge=True,
        )
        assert task.merge is True

    def test_task_unique_ids(self):
        """测试任务 ID 唯一性"""
        import time
        task1 = TranscriptionTask([], "md", {}, "/tmp")
        time.sleep(0.01)  # 等待 10ms 确保时间戳不同
        task2 = TranscriptionTask([], "md", {}, "/tmp")
        assert task1.task_id != task2.task_id


class TestTranscriptionQueue:
    """TranscriptionQueue 类测试"""

    def test_initial_state(self, queue):
        """测试初始状态"""
        assert queue.is_empty is True
        assert queue.queue_length == 0
        assert queue.current_task is None

    def test_add_task(self, queue, mock_app):
        """测试添加任务"""
        task = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        task_id = queue.add_task(task)
        assert task_id == task.task_id
        assert queue.queue_length == 1
        assert queue.is_empty is False
        mock_app._log.assert_called_once()

    def test_add_multiple_tasks(self, queue):
        """测试添加多个任务"""
        task1 = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        task2 = TranscriptionTask(["file2.wav"], "md", {}, "/tmp")
        queue.add_task(task1)
        queue.add_task(task2)
        assert queue.queue_length == 2

    def test_get_next_task(self, queue):
        """测试获取下一个任务"""
        task = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        queue.add_task(task)
        next_task = queue.get_next_task()
        assert next_task == task
        assert queue.queue_length == 0
        assert queue.current_task == task

    def test_get_next_task_empty_queue(self, queue):
        """测试从空队列获取任务"""
        next_task = queue.get_next_task()
        assert next_task is None

    def test_complete_current_task(self, queue):
        """测试完成当前任务"""
        task = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        queue.add_task(task)
        queue.get_next_task()
        queue.complete_current_task()
        assert queue.current_task is None
        assert queue.is_empty is True
        assert len(queue._history) == 1

    def test_history_limit(self, queue):
        """测试历史记录限制（最多10条）"""
        for i in range(12):
            task = TranscriptionTask([f"file{i}.wav"], "md", {}, "/tmp")
            queue.add_task(task)
            queue.get_next_task()
            queue.complete_current_task()
        assert len(queue._history) == 10

    def test_cancel_task(self, queue):
        """测试取消任务"""
        task1 = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        task2 = TranscriptionTask(["file2.wav"], "md", {}, "/tmp")
        queue.add_task(task1)
        queue.add_task(task2)
        result = queue.cancel_task(task1.task_id)
        assert result is True
        assert queue.queue_length == 1
        assert queue._queue[0] == task2

    def test_cancel_nonexistent_task(self, queue):
        """测试取消不存在的任务"""
        result = queue.cancel_task("nonexistent_id")
        assert result is False

    def test_get_queue_status(self, queue):
        """测试获取队列状态"""
        task = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        queue.add_task(task)
        status = queue.get_queue_status()
        assert "current" in status
        assert "queue" in status
        assert "history" in status
        assert len(status["queue"]) == 1

    def test_get_status_text_idle(self, queue):
        """测试获取状态文本（空闲）"""
        status_text = queue.get_status_text()
        assert "空" in status_text

    def test_get_status_text_processing(self, queue):
        """测试获取状态文本（转写中）"""
        task = TranscriptionTask(["file1.wav", "file2.wav"], "md", {}, "/tmp")
        queue.add_task(task)
        queue.get_next_task()
        status_text = queue.get_status_text()
        assert "转写中" in status_text
        assert "2 个文件" in status_text

    def test_get_status_text_queued(self, queue):
        """测试获取状态文本（队列中）"""
        task1 = TranscriptionTask(["file1.wav"], "md", {}, "/tmp")
        task2 = TranscriptionTask(["file2.wav"], "md", {}, "/tmp")
        queue.add_task(task1)
        queue.add_task(task2)
        queue.get_next_task()
        status_text = queue.get_status_text()
        assert "转写中" in status_text
        assert "队列中: 1 个任务" in status_text

    def test_add_task_log_message(self, queue, mock_app):
        """测试添加任务时的日志消息"""
        # 普通转写
        task1 = TranscriptionTask(["file1.wav"], "md", {}, "/tmp", merge=False)
        queue.add_task(task1)
        assert "普通转写" in mock_app._log.call_args[0][0]

        # 合并转写
        task2 = TranscriptionTask(["file1.wav", "file2.wav"], "md", {}, "/tmp", merge=True)
        queue.add_task(task2)
        assert "合并转写" in mock_app._log.call_args[0][0]
