"""
转写调度器（PySide6 版本）

负责：
- 转写任务队列管理
- 多进程转写调度
- 进度轮询
- AI 后处理（摘要、纠错）
"""

import os
import re
import logging
import multiprocessing
import queue
from PySide6.QtCore import QObject, QTimer, Signal

from gui.styles import MODEL_CACHE_DIR, DEFAULT_SPK_QUALITY
from file_manager import FileStatus, TranscriptionProgress
from transcribe_worker import transcribe_worker_process
from transcription_queue import TranscriptionQueue, TranscriptionTask
from utils import apply_speaker_mapping

logger = logging.getLogger("MeetScribe")


class TranscriptionHandler(QObject):
    """转写任务调度器"""

    # 信号
    status_changed = Signal(str)
    log_message = Signal(str)
    file_status_changed = Signal(str, object)  # file_path, FileStatus
    transcription_done = Signal(int, int)  # success_count, fail_count
    progress_updated = Signal(object)

    def __init__(self, app=None):
        super().__init__()
        self._app = app
        self._transcribing = False
        self._queue = None
        self._process = None
        self._ai_service = None
        self._file_status = {}
        self._progress = TranscriptionProgress()
        self._file_queue = []
        self._speaker_embeddings = {}
        self._speaker_qualities = {}
        self._sentences = []
        self._task_queue = TranscriptionQueue(app)
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll)
        self._poll_interval = 50
        self._done_called = False  # 防止 _on_done 重复调用

    @property
    def is_transcribing(self):
        return self._transcribing

    def add_to_queue(self, file_paths):
        """添加文件到转写队列"""
        self._file_queue.extend(file_paths)

    def remove_from_queue(self, file_path):
        """从队列中移除文件"""
        if file_path in self._file_queue:
            self._file_queue.remove(file_path)

    def move_up_in_queue(self, file_path):
        """在队列中上移文件"""
        try:
            idx = self._file_queue.index(file_path)
            if idx > 0:
                self._file_queue[idx], self._file_queue[idx - 1] = self._file_queue[idx - 1], self._file_queue[idx]
        except ValueError:
            pass

    def move_down_in_queue(self, file_path):
        """在队列中下移文件"""
        try:
            idx = self._file_queue.index(file_path)
            if idx < len(self._file_queue) - 1:
                self._file_queue[idx], self._file_queue[idx + 1] = self._file_queue[idx + 1], self._file_queue[idx]
        except ValueError:
            pass

    def get_queue(self):
        """获取转写队列"""
        return self._file_queue.copy()

    def get_queue_position(self, file_path):
        """获取文件在队列中的位置"""
        try:
            return self._file_queue.index(file_path) + 1
        except ValueError:
            return 0

    def get_queue_status_text(self):
        """获取队列状态文本"""
        if not self._file_queue:
            return "转写队列: 空"
        return f"转写队列: {len(self._file_queue)} 个文件"

    def start(self, file_paths, fmt, speaker_names, out_dir, merge=False):
        """启动转写任务"""
        task = TranscriptionTask(
            file_paths=file_paths,
            fmt=fmt,
            speaker_names=speaker_names,
            out_dir=out_dir,
            merge=merge,
        )

        if self._transcribing:
            self._task_queue.add_task(task)
            return

        self._execute_task(task)

    def _execute_task(self, task):
        """执行转写任务"""
        self._transcribing = True
        self._file_status = {}
        self._done_called = False  # 重置防重入标记

        # 重置说话人相关数据
        self._speaker_embeddings = {}
        self._speaker_qualities = {}
        self._sentences = []

        # 启动多进程转写
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(
            target=transcribe_worker_process,
            args=(
                self._queue,
                MODEL_CACHE_DIR,
                "cpu",
                task.file_paths,
                task.fmt,
                task.speaker_names,
                task.out_dir,
                task.merge,
            ),
            daemon=True,
        )
        self._process.start()
        self.log_message.emit(f"开始转写 {len(task.file_paths)} 个文件...")

        # 启动轮询
        self._poll_timer.start(self._poll_interval)

    def _poll(self):
        """轮询转写进度"""
        if self._queue is None:
            self._poll_timer.stop()
            return

        try:
            # 使用 get_nowait() 替代 empty()，更可靠
            while True:
                try:
                    msg = self._queue.get_nowait()
                    self._process_message(msg)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Queue poll error: {e}")

        # 检查进程状态
        if self._process and not self._process.is_alive():
            self._process.join(timeout=1)
            if not self._done_called:
                self._on_done()

    def _process_message(self, msg):
        """处理转写消息"""
        msg_type = msg[0]

        if msg_type == "status":
            self.status_changed.emit(msg[1])
        elif msg_type == "log":
            self.log_message.emit(msg[1])
        elif msg_type == "processing":
            self.file_status_changed.emit(msg[1], FileStatus.PROCESSING)
            self._file_status[msg[1]] = "processing"
        elif msg_type == "file_done":
            fp, rpath = msg[1], msg[2]
            # 更新文件管理器
            if self._app and hasattr(self._app, 'file_manager'):
                self._app.file_manager.update_status(fp, FileStatus.DONE, rpath)
            self._file_status[fp] = "done"
            self.file_status_changed.emit(fp, FileStatus.DONE)
        elif msg_type == "merge_done":
            src_paths, rpath, base = msg[1], msg[2], msg[3]
            if self._app and hasattr(self._app, 'file_manager'):
                # 更新所有源文件的状态
                for fp in src_paths:
                    self._app.file_manager.update_status(fp, FileStatus.DONE, rpath)
                    self._file_status[fp] = "done"
        elif msg_type == "spk_embeddings":
            # 处理说话人嵌入向量
            for spk_id, data in msg[1].items():
                if isinstance(data, (tuple, list)) and len(data) == 2 and isinstance(data[1], (int, float)):
                    embedding, quality = data
                    self._speaker_embeddings[spk_id] = embedding
                    self._speaker_qualities[spk_id] = quality
                else:
                    self._speaker_embeddings[spk_id] = data
                    self._speaker_qualities[spk_id] = DEFAULT_SPK_QUALITY
        elif msg_type == "sentences":
            self._sentences = msg[1]
        elif msg_type == "progress":
            self.progress_updated.emit(msg[1])
        elif msg_type == "auto_correction":
            # AI 纠错
            raw_text, base, out_dir, transcript_path = msg[1], msg[2], msg[3], msg[4]
            auto_correction = self._app.config.get("auto_correction", "关闭") if self._app else "关闭"
            if auto_correction == "转写后自动纠错":
                self.log_message.emit("正在进行 LLM 转写纠错...")
                self._generate_correction(raw_text, base, out_dir, transcript_path)
        elif msg_type == "auto_summary":
            # AI 摘要
            base, out_dir = msg[1], msg[2]
            auto_summary = self._app.config.get("auto_summary", "关闭") if self._app else "关闭"
            if auto_summary == "转写后自动生成":
                self.log_message.emit("正在生成 AI 摘要...")
                # 读取转写内容
                transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
                if os.path.exists(transcript_path):
                    with open(transcript_path, "r", encoding="utf-8") as f:
                        transcript = f.read()
                    self._generate_summary(transcript, base, out_dir)
        elif msg_type == "error":
            self.log_message.emit(f"转写失败: {msg[1]}")
            # 更新文件状态为失败
            if self._app and hasattr(self._app, 'file_manager'):
                for fp in list(self._file_status.keys()):
                    if self._file_status[fp] == "processing":
                        self._app.file_manager.update_status(fp, FileStatus.FAILED)
                        self._file_status[fp] = "failed"
            self._on_done()
        elif msg_type == "done":
            self._on_done()

    def _on_done(self):
        """转写完成"""
        self._transcribing = False
        self._poll_timer.stop()

        success_count = sum(1 for s in self._file_status.values() if s == "done")
        fail_count = sum(1 for s in self._file_status.values() if s == "failed")

        # 清理资源
        try:
            if self._process:
                if self._process.is_alive():
                    self._process.terminate()
                self._process.join(timeout=2)
            self._process = None
            self._queue = None
        except Exception:
            self._process = None
            self._queue = None

        self.transcription_done.emit(success_count, fail_count)
        self._task_queue.complete_current_task()

        # 检查队列中的下一个任务
        self._check_queue()

    def _check_queue(self):
        """检查队列，执行下一个任务"""
        next_task = self._task_queue.get_next_task()
        if next_task:
            self._execute_task(next_task)

    # ══════════════════════════════════════════════════════════
    #  AI Service
    # ══════════════════════════════════════════════════════════

    def _get_ai_service(self):
        """获取 AI 服务实例（懒加载）"""
        if self._ai_service is None:
            if not self._app or not hasattr(self._app, 'config'):
                return None

            vendor = self._app.config.get("ai_vendor", "")
            api_key = self._app.config.get("ai_api_key", "")
            if not api_key:
                api_key = self._app.config.get("mimo_api_key", "")
            if not api_key:
                return None

            try:
                from ai_service import AIService
                self._ai_service = AIService(
                    vendor=vendor or "小米",
                    model=self._app.config.get("ai_model", "mimo-v2.5"),
                    access_mode=self._app.config.get("ai_access_mode", "按量计费"),
                    api_key=api_key,
                )
            except Exception as e:
                logger.error(f"Failed to init AIService: {e}")
                return None

        return self._ai_service

    def _generate_correction(self, raw_text, base_name, out_dir, transcript_path):
        """LLM 转写纠错"""
        try:
            ai = self._get_ai_service()
            if not ai:
                self.log_message.emit("未配置云端 API Key，跳过转写纠错")
                return

            corrected = ai.generate_correction(raw_text)
            if corrected:
                # 备份原始转写
                raw_path = os.path.join(out_dir, f"{base_name}_transcript_raw.md")
                if not os.path.exists(raw_path):
                    with open(raw_path, "w", encoding="utf-8") as rf:
                        rf.write(raw_text)
                    self.log_message.emit(f"原始转写已备份: {os.path.basename(raw_path)}")

                # 保存纠错后的转写
                with open(transcript_path, "w", encoding="utf-8") as tf:
                    tf.write(corrected)
                self.log_message.emit("LLM 转写纠错完成")
            else:
                self.log_message.emit("LLM 纠错无变化，保留原文")
        except Exception as e:
            self.log_message.emit(f"LLM 转写纠错异常（已保留原文）: {e}")

    def _generate_summary(self, transcript, base_name, out_dir):
        """AI 摘要生成"""
        try:
            ai = self._get_ai_service()
            if not ai:
                self.log_message.emit("未配置云端 API Key，跳过自动摘要")
                return

            summary = ai.generate_summary(transcript)
            if summary and not summary.startswith("[错误]"):
                summary_name = f"{base_name}_summary.md"
                summary_path = os.path.join(out_dir, summary_name)
                with open(summary_path, "w", encoding="utf-8") as sf:
                    sf.write(summary)
                self.log_message.emit(f"摘要已保存: {summary_name}")

                # 提取主题
                topic = self._extract_topic_from_summary(summary)
                if topic and self._app and hasattr(self._app, 'file_manager'):
                    for item in self._app.file_manager.files:
                        if item.result_path and os.path.basename(item.result_path).startswith(base_name + "_transcript"):
                            self._app.file_manager.update_topic(item.file_path, topic)
                            self.log_message.emit(f"会议主题: {topic}")
                            break

                # 提取参会人员映射
                speaker_mapping = self._extract_speaker_mapping_from_summary(summary)
                if speaker_mapping and self._app and hasattr(self._app, 'file_manager'):
                    for item in self._app.file_manager.files:
                        if item.result_path and os.path.basename(item.result_path).startswith(base_name + "_transcript"):
                            if os.path.exists(item.result_path):
                                apply_speaker_mapping(item.result_path, speaker_mapping)
                            if os.path.exists(summary_path):
                                apply_speaker_mapping(summary_path, speaker_mapping)
                            str_mapping = {str(k): v for k, v in speaker_mapping.items()}
                            self._app.file_manager.update_speaker_names(item.file_path, str_mapping)
                            self.log_message.emit(f"已自动识别参会人员: {', '.join(f'Speaker {k}→{v}' for k, v in speaker_mapping.items())}")
                            break
            else:
                self.log_message.emit(f"摘要生成失败: {summary}")
        except Exception as e:
            self.log_message.emit(f"AI 摘要异常: {e}")

    def _extract_topic_from_summary(self, summary):
        """从摘要中提取会议主题"""
        try:
            lines = summary.splitlines()
            for line in lines[:10]:
                line = line.strip()
                if line.startswith("# ") or line.startswith("## "):
                    topic = line.lstrip("# ").strip()
                    if len(topic) > 5:
                        return topic[:50]
        except Exception:
            pass
        return None

    def _extract_speaker_mapping_from_summary(self, summary):
        """从摘要中提取参会人员映射"""
        mapping = {}
        try:
            lines = summary.splitlines()
            in_section = False
            for line in lines:
                line = line.strip()
                if "参会人员" in line or "与会人员" in line or "Speaker" in line:
                    in_section = True
                    continue
                if in_section:
                    if line.startswith("- ") or line.startswith("* "):
                        content = line.lstrip("-* ").strip()
                        # 匹配 "Speaker N: 姓名" 或 "N. 姓名" 格式
                        m = re.match(r'(?:Speaker\s*)?(\d+)[.:：]\s*(.+)', content)
                        if m:
                            spk_num = int(m.group(1))
                            name = m.group(2).strip()
                            if name and len(name) < 20:
                                mapping[spk_num] = name
                    elif line and not line.startswith("#"):
                        in_section = False
        except Exception:
            pass
        return mapping if mapping else None

    def stop_transcription(self, file_path=None):
        """停止转写"""
        if not self._transcribing:
            return

        # 终止进程
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)

        # 更新文件状态
        if file_path:
            self.file_status_changed.emit(file_path, FileStatus.PENDING)
        else:
            for fp in self._file_status:
                self.file_status_changed.emit(fp, FileStatus.PENDING)

        self._transcribing = False
        self._poll_timer.stop()
        self.log_message.emit("转写已停止")
