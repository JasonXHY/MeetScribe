#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 文件管理
管理录音文件列表、状态跟踪、转写结果关联
"""

import os
import json
import time
import wave
import logging
import subprocess
import threading
from enum import Enum
from datetime import datetime

logger = logging.getLogger("MeetScribe")


def get_audio_duration(file_path):
    """
    获取音频文件时长（秒）。

    优先用 wave 模块（WAV 文件，无额外依赖），
    其次用 FFprobe（支持所有格式，MeetScribe 已依赖 FFmpeg）。
    失败返回 0。
    """
    ext = os.path.splitext(file_path)[1].lower()
    # WAV 文件直接用 stdlib
    if ext == ".wav":
        try:
            with wave.open(file_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / rate
        except Exception:
            pass
    # FFprobe 通用方案
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             file_path],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0


class FileStatus(Enum):
    PENDING = "pending"       # 待处理
    PROCESSING = "processing" # 处理中
    DONE = "done"             # 已完成
    FAILED = "failed"         # 失败
    PAUSED = "paused"         # 已暂停（P1）


class TranscriptionProgress:
    """转写进度信息"""
    def __init__(self):
        self.percent = 0          # 进度百分比
        self.stage = ""           # 当前阶段
        self.current_file = 0     # 当前文件索引
        self.total_files = 0      # 总文件数
        self.eta = ""             # 预估剩余时间


class AudioFile:
    """录音文件条目"""

    def __init__(self, file_path, duration_s=0, file_size=0):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.duration_s = duration_s
        self.file_size = file_size or (os.path.getsize(file_path) if os.path.exists(file_path) else 0)
        self.status = FileStatus.PENDING
        self.result_path = None
        self.error_msg = None
        self.added_time = datetime.now()
        # 合并转写相关
        self.topic = ""           # AI 生成的主题/摘要标题
        self.merged_group = ""    # 合并组 ID（同一组的文件共享此 ID）
        self.source_files = []    # 合并组的源文件列表（仅合并行有效）
        self.speaker_names = {}   # 本次转写的发言人映射 {"0": "张三", "1": "李四"}

    @property
    def duration_str(self):
        if self.duration_s <= 0:
            return "--:--"
        total = int(self.duration_s)
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @property
    def size_str(self):
        if self.file_size <= 0:
            return "-"
        if self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.0f} KB"
        return f"{self.file_size / (1024 * 1024):.1f} MB"

    @property
    def status_icon(self):
        icons = {
            FileStatus.PENDING: "[ ]",
            FileStatus.PROCESSING: "[...]",
            FileStatus.DONE: "[OK]",
            FileStatus.FAILED: "[ERR]",
            FileStatus.PAUSED: "[||]",
        }
        return icons.get(self.status, "[ ]")


class FileManager:
    """文件列表管理器"""

    # 默认数据文件路径（可在 gui.py 中覆盖）
    DEFAULT_DATA_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "file_history.json"
    )

    def __init__(self, data_file=None):
        self._files = []  # List[AudioFile]
        self._listeners = []
        self._data_file = data_file or self.DEFAULT_DATA_FILE
        # 启动时自动加载历史记录
        self._load_from_file()

    @property
    def files(self):
        return list(self._files)

    @property
    def display_files(self):
        """获取用于 UI 显示的文件列表（合并子文件不单独显示）"""
        return [f for f in self._files if not f.merged_group or f.source_files]

    @property
    def count(self):
        return len(self._files)

    def add_listener(self, callback):
        """添加变更监听器 callback(event_type, file_item)"""
        self._listeners.append(callback)

    def _notify(self, event, item=None):
        for cb in self._listeners:
            try:
                cb(event, item)
            except Exception as e:
                logger.warning(f"Listener error: {e}")

    def add_file(self, file_path, duration_s=0):
        """添加音频文件到列表"""
        # 去重
        for f in self._files:
            if f.file_path == file_path:
                return f

        item = AudioFile(file_path, duration_s=duration_s)
        self._files.append(item)
        self._notify("added", item)
        self._save_to_file()
        logger.info(f"File added: {item.file_name} (duration={duration_s:.1f}s)")

        # 时长未知时异步获取，避免阻塞主线程
        if duration_s <= 0:
            threading.Thread(
                target=self._fetch_duration_async,
                args=(item,),
                daemon=True
            ).start()

        return item

    def _fetch_duration_async(self, item):
        """后台获取音频时长

        Thread safety: This method runs in a daemon thread. Simple attribute
        assignment (item.duration_s = duration) is safe under CPython's GIL.
        The subsequent _notify() and _save_to_file() calls may briefly
        interleave with main-thread operations, but _save_to_file() uses
        atomic os.replace() and _notify() tolerates stale state, so no
        data corruption occurs. If the caller needs main-thread marshaling
        for UI updates, the listener callback should use app.after(0, ...).
        """
        try:
            duration = get_audio_duration(item.file_path)
            if duration > 0:
                item.duration_s = duration
                self._notify("updated", item)
                self._save_to_file()
                logger.info(f"Async duration fetched: {item.file_name} ({duration:.1f}s)")
        except Exception as e:
            logger.warning(f"异步获取时长失败: {e}")

    def remove_file(self, file_path):
        """从列表移除文件"""
        for i, f in enumerate(self._files):
            if f.file_path == file_path:
                removed = self._files.pop(i)
                self._notify("removed", removed)
                self._save_to_file()
                logger.info(f"File removed: {removed.file_name}")
                return removed
        return None

    def get_file(self, file_path):
        """获取文件条目"""
        for f in self._files:
            if f.file_path == file_path:
                return f
        return None

    def update_status(self, file_path, status, result_path=None, error_msg=None):
        """更新文件状态"""
        item = self.get_file(file_path)
        if item is None:
            return
        item.status = status
        if result_path:
            item.result_path = result_path
        if error_msg:
            item.error_msg = error_msg
        self._notify("updated", item)
        self._save_to_file()

    def clear_all(self):
        """清空文件列表"""
        removed = list(self._files)
        self._files.clear()
        for item in removed:
            self._notify("removed", item)
        self._save_to_file()
        logger.info(f"File list cleared ({len(removed)} files)")

    def get_pending_files(self):
        """获取所有待处理文件（不含合并子文件）"""
        return [f for f in self._files
                if f.status == FileStatus.PENDING and not f.merged_group]

    def get_done_files(self):
        """获取所有已完成文件"""
        return [f for f in self._files
                if f.status == FileStatus.DONE and f.result_path]

    def create_merged_group(self, source_paths, merged_name):
        """
        创建合并组：将多个源文件合并为一行显示。

        Args:
            source_paths: 源文件路径列表
            merged_name: 合并后的显示名称

        Returns:
            AudioFile: 合并行条目
        """
        group_id = f"mg_{int(time.time() * 1000)}"

        # 计算总时长和总大小
        total_duration = 0
        total_size = 0
        source_names = []
        for fp in source_paths:
            item = self.get_file(fp)
            if item:
                total_duration += item.duration_s
                total_size += item.file_size
                source_names.append(item.file_name)
                # 标记为合并子文件
                item.merged_group = group_id

        # 创建合并行（用第一个文件的路径作为主键）
        merged_item = AudioFile(source_paths[0], duration_s=total_duration, file_size=total_size)
        merged_item.file_name = merged_name
        merged_item.merged_group = group_id
        merged_item.source_files = source_paths
        merged_item.status = FileStatus.PENDING

        # 插入到列表中（替换第一个源文件的位置）
        for i, f in enumerate(self._files):
            if f.file_path == source_paths[0]:
                self._files[i] = merged_item
                break

        self._notify("updated", merged_item)
        self._save_to_file()
        return merged_item

    def update_topic(self, file_path, topic):
        """更新文件的主题字段"""
        item = self.get_file(file_path)
        if item:
            item.topic = topic
            self._notify("updated", item)
            self._save_to_file()

    def update_speaker_names(self, file_path, speaker_names):
        """更新文件的发言人映射"""
        item = self.get_file(file_path)
        if item:
            item.speaker_names = speaker_names
            self._notify("updated", item)
            self._save_to_file()

    def get_files_by_status(self, status):
        """按状态筛选"""
        return [f for f in self._files if f.status == status]

    def _save_to_file(self):
        """保存文件历史到文件（原子写入）"""
        import tempfile

        try:
            # 确保目录存在
            data_dir = os.path.dirname(self._data_file)
            if data_dir:
                os.makedirs(data_dir, exist_ok=True)

            # 构建要保存的数据
            save_data = {
                "version": 1,
                "saved_at": datetime.now().isoformat(),
                "files": []
            }

            for f in self._files:
                save_data["files"].append({
                    "file_path": f.file_path,
                    "file_name": f.file_name,
                    "duration_s": f.duration_s,
                    "file_size": f.file_size,
                    "status": getattr(f.status, 'value', str(f.status)),
                    "result_path": f.result_path,
                    "error_msg": f.error_msg,
                    "added_time": f.added_time.isoformat() if f.added_time else None,
                    "topic": f.topic,
                    "merged_group": f.merged_group,
                    "source_files": f.source_files,
                    "speaker_names": f.speaker_names,
                })

            dir_name = os.path.dirname(self._data_file) or '.'
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=dir_name, delete=False) as fp:
                json.dump(save_data, fp, ensure_ascii=False, indent=2)
                temp_path = fp.name

            # 原子替换
            os.replace(temp_path, self._data_file)

            logger.info(f"File history saved: {len(save_data['files'])} items -> {self._data_file}")
            return True

        except Exception as e:
            # 清理临时文件
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Failed to save file history: {e}")
            return False

    def _load_from_file(self):
        """从 JSON 文件加载文件列表"""
        if not os.path.exists(self._data_file):
            logger.debug("No file history found, starting fresh")
            return False

        try:
            with open(self._data_file, "r", encoding="utf-8") as fp:
                save_data = json.load(fp)

            files_data = save_data.get("files", [])
            loaded_count = 0

            for item in files_data:
                file_path = item.get("file_path", "")
                if not file_path or not os.path.exists(file_path):
                    # 跳过不存在的文件
                    logger.debug(f"Skipping missing file: {file_path}")
                    continue

                audio = AudioFile(
                    file_path=file_path,
                    duration_s=item.get("duration_s", 0),
                    file_size=item.get("file_size", 0),
                )
                # 历史记录中时长为 0 的，补测一次
                if audio.duration_s <= 0:
                    audio.duration_s = get_audio_duration(file_path)
                # 恢复状态
                status_str = item.get("status", "pending")
                try:
                    audio.status = FileStatus(status_str)
                except ValueError:
                    audio.status = FileStatus.PENDING

                audio.result_path = item.get("result_path")
                audio.error_msg = item.get("error_msg")
                audio.topic = item.get("topic", "")
                audio.merged_group = item.get("merged_group", "")
                audio.source_files = item.get("source_files", [])
                audio.speaker_names = item.get("speaker_names", {})

                # 恢复添加时间
                added_time_str = item.get("added_time")
                if added_time_str:
                    try:
                        audio.added_time = datetime.fromisoformat(added_time_str)
                    except (ValueError, TypeError):
                        audio.added_time = datetime.now()

                self._files.append(audio)
                loaded_count += 1

            logger.info(f"File history loaded: {loaded_count} items from {self._data_file}")
            return loaded_count > 0

        except Exception as e:
            logger.warning(f"Failed to load file history: {e}")
            return False
