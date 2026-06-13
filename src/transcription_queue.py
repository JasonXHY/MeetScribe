#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 转写任务队列管理
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TranscriptionTask:
    """转写任务"""
    file_paths: List[str]
    fmt: str
    speaker_names: dict
    out_dir: str
    merge: bool = False
    created_at: float = field(default_factory=time.time)
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")


class TranscriptionQueue:
    """转写任务队列管理"""

    def __init__(self, app):
        """
        Args:
            app: MeetScribeApp 实例，用于访问 _log 等方法
        """
        self._app = app
        self._queue: List[TranscriptionTask] = []  # 等待队列
        self._current_task: Optional[TranscriptionTask] = None  # 当前执行的任务
        self._history: List[TranscriptionTask] = []  # 历史任务（最近 10 个）

    @property
    def is_empty(self) -> bool:
        """队列是否为空"""
        return len(self._queue) == 0 and self._current_task is None

    @property
    def queue_length(self) -> int:
        """队列中等待的任务数量"""
        return len(self._queue)

    @property
    def current_task(self) -> Optional[TranscriptionTask]:
        """当前正在执行的任务"""
        return self._current_task

    def add_task(self, task: TranscriptionTask) -> str:
        """
        添加任务到队列

        Args:
            task: 要添加的任务

        Returns:
            任务 ID
        """
        self._queue.append(task)
        task_type = "合并转写" if task.merge else "普通转写"
        self._app._log(f"已加入转写队列 ({task_type})，位置: {len(self._queue)}")
        return task.task_id

    def get_next_task(self) -> Optional[TranscriptionTask]:
        """
        获取下一个任务

        Returns:
            下一个任务，如果队列为空返回 None
        """
        if self._queue:
            task = self._queue.pop(0)
            self._current_task = task
            return task
        return None

    def complete_current_task(self):
        """完成当前任务"""
        if self._current_task:
            self._history.append(self._current_task)
            if len(self._history) > 10:
                self._history.pop(0)
            self._current_task = None

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 要取消的任务 ID

        Returns:
            是否成功取消
        """
        for i, task in enumerate(self._queue):
            if task.task_id == task_id:
                self._queue.pop(i)
                return True
        return False

    def get_queue_status(self) -> dict:
        """
        获取队列状态

        Returns:
            包含 current, queue, history 的字典
        """
        return {
            'current': self._current_task,
            'queue': self._queue.copy(),
            'history': self._history.copy(),
        }

    def get_status_text(self) -> str:
        """
        获取队列状态文本（用于 UI 显示）

        Returns:
            状态文本
        """
        if self._current_task:
            text = f"转写中: {len(self._current_task.file_paths)} 个文件"
            if len(self._queue) > 0:
                text += f" | 队列中: {len(self._queue)} 个任务"
            return text
        elif len(self._queue) > 0:
            return f"队列中: {len(self._queue)} 个任务"
        else:
            return "转写队列: 空"
