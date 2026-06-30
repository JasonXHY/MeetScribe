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
import json
import time
import logging
import threading
import queue
from PySide6.QtCore import QObject, QTimer, Signal

from gui.styles import MODEL_CACHE_DIR, DEFAULT_SPK_QUALITY
from file_manager import FileStatus, TranscriptionProgress
from transcribe_worker import transcribe_worker_process
from transcription_queue import TranscriptionQueue, TranscriptionTask
from utils import apply_speaker_mapping, get_summary_path

logger = logging.getLogger("MeetScribe")


class TranscriptionHandler(QObject):
    """转写任务调度器"""

    # 信号
    status_changed = Signal(str)
    log_message = Signal(str)
    file_status_changed = Signal(str, object)  # file_path, FileStatus
    transcription_done = Signal(int, int)  # success_count, fail_count
    progress_updated = Signal(object)
    refresh_needed = Signal()  # 通知主线程刷新文件列表
    post_process_status = Signal(str)  # 后处理状态更新

    def __init__(self, app=None):
        super().__init__()
        self._app = app
        self._transcribing = False
        self._queue = None
        self._thread = None
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
        self._voiceprint_matched = False
        self._voiceprint_match_results = {}
        self._current_batch_paths = set()
        self._names_applied = False  # 防重入标记
        self._active_workers = []  # 保持 Worker 引用，防止 GC 回收
        self._last_heartbeat = 0  # 上次收到心跳的时间戳
        self._heartbeat_timeout = 120  # 心跳超时秒数

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
        self._current_batch_paths = set(file_paths)
        # 重置声纹匹配状态（每次新转写都需要重新匹配）
        self._voiceprint_matched = False
        self._voiceprint_match_results = {}

        if self._transcribing:
            self._task_queue.add_task(task)
            return

        self._execute_task(task)

    def _execute_task(self, task):
        """执行转写任务"""
        # 清理残留线程
        if self._thread and self._thread.is_alive():
            logger.warning("发现残留线程，正在清理")
            self._thread.join(timeout=3)
            self._thread = None

        self._transcribing = True
        self._file_status = {}
        self._done_called = False  # 重置防重入标记
        self._names_applied = False  # 重置姓名应用防重入标记
        self._last_heartbeat = time.time()  # 重置心跳时间戳

        # 重置说话人相关数据
        self._speaker_embeddings = {}
        self._speaker_qualities = {}
        self._sentences = []

        # 从配置读取输出目录（如果未指定）
        if not task.out_dir and self._app and hasattr(self._app, 'config'):
            task.out_dir = self._app.config.get("transcript_dir", "")

        # 启动转写线程
        device = "cpu"
        if self._app and hasattr(self._app, 'config'):
            device_cfg = self._app.config.get("device", "CPU")
            device = "cuda" if "cuda" in device_cfg.lower() else "cpu"
        self._queue = queue.Queue()
        self._thread = threading.Thread(
            target=transcribe_worker_process,
            args=(
                self._queue,
                MODEL_CACHE_DIR,
                device,
                task.file_paths,
                task.fmt,
                task.speaker_names,
                task.out_dir,
                task.merge,
            ),
            daemon=True,
        )
        self._thread.start()
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
                    # 防御性检查：防止 _on_done() 在循环间隙将 queue 置 None
                    if self._queue is None:
                        break
                    msg = self._queue.get_nowait()
                    self._process_message(msg)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Queue poll error: {e}")

        # 检查线程状态
        if self._thread and not self._thread.is_alive():
            self._thread.join(timeout=1)
            if not self._done_called:
                self._on_done()

        # 心跳超时检测：线程存活但长时间无消息
        elif self._thread and self._thread.is_alive() and self._last_heartbeat > 0:
            elapsed = time.time() - self._last_heartbeat
            if elapsed > self._heartbeat_timeout:
                logger.error(f"转写超时：线程 {elapsed:.0f} 秒无响应")
                self.log_message.emit(f"转写超时：线程 {elapsed:.0f} 秒无响应")
                # daemon 线程会在主线程退出时自动终止
                self._transcribing = False
                self._poll_timer.stop()
                self._on_done()

    def _process_message(self, msg):
        """处理转写消息"""
        msg_type = msg[0]

        if msg_type == "status":
            self.status_changed.emit(msg[1])
        elif msg_type == "heartbeat":
            self._last_heartbeat = time.time()
        elif msg_type == "log":
            self.log_message.emit(msg[1])
        elif msg_type == "processing":
            fp = msg[1]
            if self._app and hasattr(self._app, 'file_manager'):
                self._app.file_manager.update_status(fp, FileStatus.PROCESSING)
            self.file_status_changed.emit(fp, FileStatus.PROCESSING)
            self._file_status[fp] = "processing"
        elif msg_type == "file_done":
            fp, rpath = msg[1], msg[2]
            # 更新文件管理器
            if self._app and hasattr(self._app, 'file_manager'):
                self._app.file_manager.update_status(fp, FileStatus.DONE, rpath)
            self._file_status[fp] = "done"
            self.file_status_changed.emit(fp, FileStatus.DONE)
            self.log_message.emit(f"[转写完成] {os.path.basename(fp)}")
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
            auto_correction = self._app.config.get("auto_correction", False) if self._app else False
            # 支持布尔值和字符串两种格式
            should_correct = (
                auto_correction is True
                or auto_correction == "转写后自动纠错"
                or auto_correction == "true"
            )
            if should_correct:
                self.log_message.emit(f"[AI纠错] 正在进行转写纠错...")
                self._start_correction_async(raw_text, base, out_dir, transcript_path)
        elif msg_type == "auto_summary":
            # AI 摘要
            base, out_dir = msg[1], msg[2]

            # 先执行声纹匹配（如果尚未执行且有嵌入数据）
            if not self._voiceprint_matched and self._speaker_embeddings:
                self._match_voiceprints()

            # 执行姓名应用（无论有无声纹，正则提取都需要跑）
            self._apply_speaker_names()

            # 最后生成摘要（确保声纹匹配和姓名应用已完成）
            auto_summary = self._app.config.get("auto_summary", True) if self._app else True
            # 支持布尔值和字符串两种格式
            should_summary = (
                auto_summary is True
                or auto_summary == "转写后自动生成"
                or auto_summary == "true"
            )
            if should_summary:
                self.log_message.emit(f"[AI摘要] 正在生成摘要...")
                # 读取转写内容
                transcript_path = os.path.join(out_dir, f"{base}_transcript.md")
                if os.path.exists(transcript_path):
                    with open(transcript_path, "r", encoding="utf-8") as f:
                        transcript = f.read()
                    self._start_summary_async(transcript, base, out_dir)
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
        if self._done_called:
            return
        self._done_called = True
        self._transcribing = False
        self._poll_timer.stop()

        success_count = sum(1 for s in self._file_status.values() if s == "done")
        fail_count = sum(1 for s in self._file_status.values() if s == "failed")

        # 将未完成的 processing 文件标记为 failed
        if self._app and hasattr(self._app, 'file_manager'):
            for fp, status in list(self._file_status.items()):
                if status == "processing":
                    self._app.file_manager.update_status(fp, FileStatus.FAILED)
                    self._file_status[fp] = "failed"
                    fail_count += 1

        # 声纹匹配
        if self._speaker_embeddings:
            self._match_voiceprints()
        else:
            logger.warning("[VOICEPRINT] No speaker embeddings received, skipping match")

        # 发言人姓名提取（AI-003）：声纹 confirmed > 姓名提取 > 保留 Speaker N
        self._apply_speaker_names()

        # 保存声纹embedding到磁盘（供重启后恢复）
        self._save_embeddings_to_disk()

        # 清理资源
        try:
            if self._thread:
                if self._thread.is_alive():
                    self._thread.join(timeout=2)
            self._thread = None
            self._queue = None
        except Exception as e:
            logger.warning(f"转写线程清理异常: {e}")
            self._thread = None
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

    def _save_embeddings_to_disk(self):
        """将声纹嵌入向量保存到磁盘，程序重启后可恢复"""
        if not self._speaker_embeddings:
            return

        # 按文件分组保存：遍历当前批次的文件，每个文件保存对应的嵌入向量
        for fp in self._current_batch_paths:
            if not self._app or not hasattr(self._app, 'file_manager'):
                continue
            item = self._app.file_manager.get_file(fp)
            if not item or not item.result_path:
                continue

            result_dir = os.path.dirname(item.result_path)
            base = os.path.splitext(os.path.basename(item.result_path))[0]
            # 去掉 _transcript 后缀
            if base.endswith("_transcript"):
                base = base[:-len("_transcript")]

            emb_path = os.path.join(result_dir, f"{base}_embeddings.json")

            # 构建该文件的嵌入向量（所有说话人的）
            emb_data = {}
            for spk_id, embedding in self._speaker_embeddings.items():
                # numpy array 转 list 以便 JSON 序列化
                if hasattr(embedding, 'tolist'):
                    emb_data[str(spk_id)] = {
                        "vector": embedding.tolist(),
                        "quality": self._speaker_qualities.get(spk_id, DEFAULT_SPK_QUALITY),
                    }
                else:
                    emb_data[str(spk_id)] = {
                        "vector": list(embedding) if embedding is not None else [],
                        "quality": self._speaker_qualities.get(spk_id, DEFAULT_SPK_QUALITY),
                    }

            try:
                with open(emb_path, "w", encoding="utf-8") as f:
                    json.dump(emb_data, f, ensure_ascii=False, indent=2)
                logger.debug(f"[EMBEDDINGS] 已保存到 {emb_path} ({len(emb_data)} 个说话人)")
            except Exception as e:
                logger.warning(f"[EMBEDDINGS] 保存失败: {e}")

    # ══════════════════════════════════════════════════════════
    #  Voiceprint Matching
    # ══════════════════════════════════════════════════════════

    def _match_voiceprints(self):
        """用音色库匹配转写结果中的说话人（两阶段匹配+冲突检测）"""
        if not self._speaker_embeddings:
            logger.debug("[VOICEPRINT] No speaker embeddings available")
            return
        if self._voiceprint_matched:
            logger.debug("[VOICEPRINT] Already matched, skipping")
            return
        self._voiceprint_matched = True
        self._voiceprint_match_results = {}

        try:
            from voiceprint import VoiceprintLibrary, HIGH_CONFIDENCE
            library = VoiceprintLibrary()

            speaker_embeddings = self._extract_speaker_embeddings()
            if not speaker_embeddings:
                logger.debug("[VOICEPRINT] No valid speaker embeddings extracted")
                return

            # 第一阶段：收集所有匹配结果
            all_matches = []
            for speaker_id, embedding in speaker_embeddings.items():
                # 详细日志：打印与每个音色库成员的匹配分数
                import numpy as np
                emb_array = np.array(embedding) if not isinstance(embedding, np.ndarray) else embedding
                logger.info(f"[VOICEPRINT] Speaker {speaker_id + 1}: embedding dim={emb_array.shape}")
                for spk_name, profile in library.get_speakers().items():
                    avg_emb = profile.get_weighted_embedding()
                    if avg_emb is not None:
                        avg_array = np.array(avg_emb)
                        cos_sim = np.dot(emb_array, avg_array) / (np.linalg.norm(emb_array) * np.linalg.norm(avg_array))
                        logger.info(f"[VOICEPRINT]   vs {spk_name}: cos_sim={cos_sim:.4f}")

                name, score = library.match(embedding)
                if name:
                    confidence = "confirmed" if score >= HIGH_CONFIDENCE else "suggested"
                    all_matches.append((speaker_id, name, confidence, score, embedding))
                    logger.info(f"[VOICEPRINT] Speaker {speaker_id + 1}: match={name}, "
                               f"score={score:.3f}, confidence={confidence}")
                else:
                    logger.info(f"[VOICEPRINT] Speaker {speaker_id + 1}: no match (best score below threshold)")

            if not all_matches:
                logger.warning("[VOICEPRINT] No matches found for any speaker")
                return

            # 第二阶段：冲突检测 — 对每个音色库成员，只保留 score 最高的
            best_by_name = {}
            for speaker_id, name, confidence, score, embedding in all_matches:
                if name not in best_by_name or score > best_by_name[name][2]:
                    best_by_name[name] = (speaker_id, confidence, score, embedding)

            # 第三阶段：写入映射
            for name, (speaker_id, confidence, score, embedding) in best_by_name.items():
                self._apply_voiceprint_match(name, speaker_id, confidence, embedding, library)

            # 记录未写入的匹配（供日志和后续确认）
            written_ids = {v[0] for v in best_by_name.values()}
            for speaker_id, name, confidence, score, embedding in all_matches:
                if speaker_id not in written_ids:
                    logger.info(f"[VOICEPRINT] Skipped conflict: Speaker {speaker_id+1} -> {name} "
                              f"(score={score:.3f}, lower than best match)")

        except Exception as e:
            logger.error(f"Voiceprint matching failed: {e}")

    def _apply_voiceprint_match(self, name, speaker_id, confidence, embedding, library):
        """将单个说话人的匹配结果写入文件，并记录到 _voiceprint_match_results。

        匹配记录会先行写入 self._voiceprint_match_results（供摘要注入 AI-006 使用），
        即使后续写文件或自动追加声纹样本失败，匹配结果仍然保留。
        """
        logger.debug(f"[VOICEPRINT] Applying match: speaker_id={speaker_id}, name={name}, confidence={confidence}")
        logger.debug(f"[VOICEPRINT] Current batch paths: {self._current_batch_paths}")

        # 记录匹配结果（供摘要注入与姓名提取优先级判断使用）
        self._voiceprint_match_results[speaker_id] = {
            "name": name,
            "confidence": confidence,
        }
        try:
            if self._app and hasattr(self._app, 'file_manager'):
                for item in self._app.file_manager.files:
                    if item.status == FileStatus.DONE and item.result_path:
                        if item.file_path not in self._current_batch_paths:
                            logger.debug(f"[VOICEPRINT] Skipping {item.file_path}: not in batch")
                            continue
                        logger.debug(f"[VOICEPRINT] Item status: {item.status}, result_path: {item.result_path}")
                        logger.debug(f"[VOICEPRINT] File path in batch: {item.file_path in self._current_batch_paths}")
                        str_mapping = item.speaker_names or {}
                        str_key = str(speaker_id + 1)
                        str_mapping[str_key] = name
                        self._app.file_manager.update_speaker_names(
                            item.file_path, str_mapping
                        )
                        logger.debug(f"[VOICEPRINT] Updated speaker_names: {str_mapping}")
                        if os.path.exists(item.result_path):
                            apply_speaker_mapping(item.result_path, {speaker_id + 1: name})
                            summary_path = get_summary_path(item.result_path)
                            if summary_path and os.path.exists(summary_path):
                                apply_speaker_mapping(summary_path, {speaker_id + 1: name})

                        self.log_message.emit(
                            f"音色库匹配: Speaker {speaker_id + 1} -> {name} ({confidence})"
                        )

                        # confirmed 级别自动追加声纹样本
                        if confidence == "confirmed":
                            quality = self._speaker_qualities.get(speaker_id, DEFAULT_SPK_QUALITY)
                            source_name = getattr(item, 'file_name', 'auto_match')
                            library.add_speaker(name, embedding,
                                source=source_name, quality=quality)
                            logger.info(f"自动添加声纹样本: {name}")
        except Exception as e:
            logger.error(f"Apply voiceprint match failed: {e}")

    def _extract_speaker_embeddings(self):
        """从接收到的嵌入向量中提取每个说话人的代表向量"""
        if not self._speaker_embeddings:
            return {}

        embeddings = {}
        for spk_id, embedding in self._speaker_embeddings.items():
            if embedding is not None:
                embeddings[int(spk_id)] = embedding
        return embeddings

    # ══════════════════════════════════════════════════════════
    #  Speaker Name Extraction (AI-003)
    # ══════════════════════════════════════════════════════════

    def _apply_speaker_names(self):
        """从转写文本提取发言人真实姓名并应用到结果（AI-003）。

        优先级：声纹高置信（confirmed）匹配 > 姓名提取（正则优先 + LLM 兜底）> 保留 Speaker N。
        即：已被声纹 confirmed 命名的说话人不会被本步骤覆盖。
        正则优先；正则无果且配置了可用 AI 服务时才走 LLM 兜底。
        懒加载导入 SpeakerNamer，使本模块在无 funasr 环境下仍可导入。
        """
        # 防重入检查
        if self._names_applied:
            logger.debug("[SPEAKER_NAMES] Already applied, skipping")
            return
        self._names_applied = True

        try:
            if not (self._app and hasattr(self._app, 'file_manager')):
                return

            from speaker_namer import SpeakerNamer
            namer = SpeakerNamer()

            # 已被声纹 confirmed 命名的说话人（0 基 id → 转写文本中的 1 基 Speaker 编号）
            confirmed_ids = {
                int(spk_id) + 1
                for spk_id, info in (self._voiceprint_match_results or {}).items()
                if isinstance(info, dict) and info.get("confidence") == "confirmed"
            }

            for item in self._app.file_manager.files:
                if item.status != FileStatus.DONE or not item.result_path:
                    continue
                if item.file_path not in self._current_batch_paths:
                    continue
                if not os.path.exists(item.result_path):
                    continue

                # 读取转写文本
                try:
                    with open(item.result_path, "r", encoding="utf-8") as f:
                        transcript = f.read()
                except Exception as e:
                    logger.warning(f"读取转写文件失败，跳过姓名提取: {e}")
                    continue

                # 收集转写中出现的 Speaker 编号（1 基），排除已被声纹 confirmed 命名的
                speaker_ids = sorted({
                    int(n) for n in re.findall(r'(?<!\w)Speaker\s+(\d+)(?!\w)', transcript)
                })
                target_ids = [str(n) for n in speaker_ids if n not in confirmed_ids]
                if not target_ids:
                    continue

                # 正则优先；正则无果时若有可用 AI 服务则 LLM 兜底
                ai_service = self._get_ai_service()
                name_map = namer.extract_names(
                    transcript, target_ids, ai_service=ai_service
                )
                if not name_map:
                    continue

                # 转为 {int(1 基编号): 姓名}，再次过滤 confirmed 说话人
                int_mapping = {
                    int(sid): name
                    for sid, name in name_map.items()
                    if name and int(sid) not in confirmed_ids
                }
                if not int_mapping:
                    continue

                # 应用到转写结果与摘要文件
                apply_speaker_mapping(item.result_path, int_mapping)
                summary_path = get_summary_path(item.result_path)
                if summary_path and os.path.exists(summary_path):
                    apply_speaker_mapping(summary_path, int_mapping)

                # 合并写入说话人映射（保留已有的声纹命名）
                str_mapping = item.speaker_names or {}
                for sid, name in int_mapping.items():
                    str_mapping[str(sid)] = name
                self._app.file_manager.update_speaker_names(item.file_path, str_mapping)

                self.log_message.emit(
                    "姓名提取: "
                    + ", ".join(f"Speaker {k}→{v}" for k, v in int_mapping.items())
                )
        except Exception as e:
            logger.error(f"发言人姓名提取失败: {e}", exc_info=True)

    # ══════════════════════════════════════════════════════════
    #  AI Service
    # ══════════════════════════════════════════════════════════

    def _get_ai_service(self):
        """获取 AI 服务实例（懒加载）"""
        if self._ai_service is None:
            if not self._app or not hasattr(self._app, 'config'):
                return None

            vendor = self._app.config.get("ai_vendor", "")
            # 优先读用户 Key，为空则读内置 Key
            api_key = self._app.config.get("ai_user_api_key", "")
            if not api_key:
                api_key = self._app.config.get("ai_default_api_key", "")
            if not api_key:
                return None

            # 厂商名规范化：旧版 "小米" → 新版 "小米 MiMo"
            vendor_map = {
                "小米": "小米 MiMo",
                "智谱": "智谱 AI",
                "阿里": "阿里巴巴",
                "腾讯": "腾讯混元",
                "百度": "百度文心",
                "月之暗面": "月之暗面 Kimi",
                "讯飞": "讯飞星火",
                "百川": "百川智能",
            }
            vendor = vendor_map.get(vendor, vendor)

            try:
                from ai_service import AIService
                # 透传 Ollama 本地 LLM 配置（地址 / 模型），供姓名提取等本地路径使用（AI-005 / SET-016）
                ollama_enabled = self._app.config.get("ollama_enabled", "关闭")
                self._ai_service = AIService(
                    vendor=vendor or "小米 MiMo",
                    model=self._app.config.get("ai_model", "mimo-v2.5"),
                    access_mode=self._app.config.get("ai_access_mode", "按量计费"),
                    api_key=api_key,
                    ollama_url=self._app.config.get("ollama_url", None),
                    ollama_model=self._app.config.get("ollama_model", None),
                    ollama_enabled=ollama_enabled == "开启",
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

            summary = ai.generate_summary(transcript, voiceprint_matches=self._voiceprint_match_results)
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

                # 主题更新后刷新文件列表
                if topic and self._app and hasattr(self._app, '_home_page'):
                    self.refresh_needed.emit()

                # 提取参会人员映射
                speaker_mapping = self._extract_speaker_mapping_from_summary(summary)
                if speaker_mapping and self._app and hasattr(self._app, 'file_manager'):
                    # 过滤已被声纹 confirmed 匹配的说话人（不覆盖）
                    confirmed_ids = {
                        int(spk_id) + 1
                        for spk_id, info in (self._voiceprint_match_results or {}).items()
                        if isinstance(info, dict) and info.get("confidence") == "confirmed"
                    }
                    filtered_mapping = {
                        k: v for k, v in speaker_mapping.items()
                        if k not in confirmed_ids
                    }

                    if filtered_mapping:
                        for item in self._app.file_manager.files:
                            if item.result_path and os.path.basename(item.result_path).startswith(base_name + "_transcript"):
                                if os.path.exists(item.result_path):
                                    apply_speaker_mapping(item.result_path, filtered_mapping)
                                if os.path.exists(summary_path):
                                    apply_speaker_mapping(summary_path, filtered_mapping)
                                str_mapping = {str(k): v for k, v in filtered_mapping.items()}
                                self._app.file_manager.update_speaker_names(item.file_path, str_mapping)
                                self.log_message.emit(f"已自动识别参会人员: {', '.join(f'Speaker {k}→{v}' for k, v in filtered_mapping.items())}")
                                break
            else:
                self.log_message.emit(f"摘要生成失败: {summary}")
        except Exception as e:
            self.log_message.emit(f"AI 摘要异常: {e}")

    def _start_correction_async(self, raw_text, base_name, out_dir, transcript_path):
        """异步启动 AI 纠错"""
        ai = self._get_ai_service()
        if not ai:
            self.log_message.emit("未配置云端 API Key，跳过转写纠错")
            return

        self.post_process_status.emit("正在进行AI纠错...")
        worker = AICorrectionWorker(ai, raw_text)
        worker.finished.connect(
            lambda corrected: self._on_correction_finished(corrected, base_name, out_dir, transcript_path)
        )
        worker.error.connect(self._on_correction_error)
        worker.finished.connect(lambda: self._remove_worker(worker))
        worker.error.connect(lambda: self._remove_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _start_summary_async(self, transcript, base_name, out_dir):
        """异步启动 AI 摘要"""
        ai = self._get_ai_service()
        if not ai:
            self.log_message.emit("未配置云端 API Key，跳过自动摘要")
            return

        self.post_process_status.emit("正在生成摘要...")
        worker = AISummaryWorker(ai, transcript, self._voiceprint_match_results)
        worker.finished.connect(
            lambda summary: self._on_summary_finished(summary, base_name, out_dir)
        )
        worker.error.connect(self._on_summary_error)
        worker.finished.connect(lambda: self._remove_worker(worker))
        worker.error.connect(lambda: self._remove_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _remove_worker(self, worker):
        """Worker 完成后从活跃列表移除"""
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def _on_correction_finished(self, corrected, base_name, out_dir, transcript_path):
        """纠错完成回调"""
        try:
            if corrected:
                # 备份原始转写
                raw_path = os.path.join(out_dir, f"{base_name}_transcript_raw.md")
                if not os.path.exists(raw_path):
                    # 读取原始内容（从 transcript_path）
                    if os.path.exists(transcript_path):
                        with open(transcript_path, "r", encoding="utf-8") as rf:
                            raw_text = rf.read()
                        with open(raw_path, "w", encoding="utf-8") as wf:
                            wf.write(raw_text)
                        self.log_message.emit(f"原始转写已备份: {os.path.basename(raw_path)}")

                # 保存纠错后的转写
                with open(transcript_path, "w", encoding="utf-8") as tf:
                    tf.write(corrected)
                self.log_message.emit("LLM 转写纠错完成")
            else:
                self.log_message.emit("LLM 纠错无变化，保留原文")
        except Exception as e:
            self.log_message.emit(f"保存纠错结果失败: {e}")

    def _on_correction_error(self, error_msg):
        """纠错失败回调"""
        self.log_message.emit(f"AI 纠错异常（已保留原文）: {error_msg}")

    def _on_summary_finished(self, summary, base_name, out_dir):
        """摘要完成回调"""
        try:
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

                # 主题更新后刷新文件列表
                if topic and self._app and hasattr(self._app, '_home_page'):
                    self.refresh_needed.emit()

                # 提取参会人员映射
                speaker_mapping = self._extract_speaker_mapping_from_summary(summary)
                if speaker_mapping and self._app and hasattr(self._app, 'file_manager'):
                    # 过滤已被声纹 confirmed 匹配的说话人（不覆盖）
                    confirmed_ids = {
                        int(spk_id) + 1
                        for spk_id, info in (self._voiceprint_match_results or {}).items()
                        if isinstance(info, dict) and info.get("confidence") == "confirmed"
                    }
                    filtered_mapping = {
                        k: v for k, v in speaker_mapping.items()
                        if k not in confirmed_ids
                    }

                    if filtered_mapping:
                        for item in self._app.file_manager.files:
                            if item.result_path and os.path.basename(item.result_path).startswith(base_name + "_transcript"):
                                if os.path.exists(item.result_path):
                                    apply_speaker_mapping(item.result_path, filtered_mapping)
                                if os.path.exists(summary_path):
                                    apply_speaker_mapping(summary_path, filtered_mapping)
                                str_mapping = {str(k): v for k, v in filtered_mapping.items()}
                                self._app.file_manager.update_speaker_names(item.file_path, str_mapping)
                                self.log_message.emit(f"已自动识别参会人员: {', '.join(f'Speaker {k}→{v}' for k, v in filtered_mapping.items())}")
                                break
            else:
                self.log_message.emit(f"摘要生成失败: {summary}")
        except Exception as e:
            self.log_message.emit(f"保存摘要结果失败: {e}")

    def _on_summary_error(self, error_msg):
        """摘要失败回调"""
        self.log_message.emit(f"AI 摘要异常: {error_msg}")

    def _extract_topic_from_summary(self, summary):
        """从摘要中提取会议主题"""
        try:
            lines = summary.splitlines()
            for i, line in enumerate(lines[:15]):
                line = line.strip()
                # 找到"会议主题"相关的 section header，取下一行正文作为主题
                if line.startswith("#") and ("主题" in line or "会议" in line):
                    for j in range(i + 1, min(i + 4, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith("#"):
                            topic = next_line[:50]
                            if len(topic) > 2:
                                return topic
                    break
                # 兼容：直接匹配 "主题：xxx" 或 "**主题**：xxx" 格式
                if "主题" in line and ("：" in line or ":" in line):
                    m = re.search(r'主题[：:]\s*(.+)', line)
                    if m:
                        topic = m.group(1).strip()
                        if len(topic) > 2:
                            return topic[:50]
        except Exception:
            pass
        return None

    def _extract_speaker_mapping_from_summary(self, summary):
        """从摘要中提取参会人员映射

        支持多种格式：
          - [Speaker N] 姓名
          - [Speaker N]姓名
          - Speaker N: 姓名
          - N. 姓名

        过滤角色推断（如"（项目负责人）"、"（角色推断：XXX）"）
        过滤重复姓名（如"嘉诚 嘉诚" → "嘉诚"）
        """
        mapping = {}
        try:
            lines = summary.splitlines()
            in_section = False
            for line in lines:
                line = line.strip()
                # 仅在 header 行触发 in_section
                if re.match(r'^#+\s*(?:参会人员|与会者|出席人员|Participants)', line, re.IGNORECASE):
                    in_section = True
                    continue
                if in_section:
                    if line.startswith("- ") or line.startswith("* "):
                        content = line.lstrip("-* ").strip()
                        # 匹配 [Speaker N] 姓名 格式（支持 — 角色描述 后缀）
                        m = re.match(r'\[Speaker\s+(\d+)\]\s+(.+?)(?:\s*[—\-]\s*.*)?$', content)
                        if m:
                            spk_num = int(m.group(1))
                            name = m.group(2).strip().strip('*_#,，。')
                            # 过滤角色推断：以括号开头的不是姓名
                            if name and name.startswith(("（", "(")):
                                continue
                            # 过滤重复姓名（如 "嘉诚 嘉诚" → "嘉诚"）
                            if name and " " in name:
                                parts = name.split()
                                if len(parts) == 2 and parts[0] == parts[1]:
                                    name = parts[0]
                            if name and len(name) < 50:
                                mapping[spk_num] = name
                                continue
                        # 匹配 Speaker N: 姓名 格式
                        m = re.match(r'Speaker\s+(\d+)[.:：]\s*(.+)', content)
                        if m:
                            spk_num = int(m.group(1))
                            name = m.group(2).strip()
                            if name and name.startswith(("（", "(")):
                                continue
                            # 过滤重复姓名
                            if name and " " in name:
                                parts = name.split()
                                if len(parts) == 2 and parts[0] == parts[1]:
                                    name = parts[0]
                            if name and len(name) < 50:
                                mapping[spk_num] = name
                                continue
                        # 匹配 N. 姓名 格式
                        m = re.match(r'(\d+)[.:：]\s*(.+)', content)
                        if m:
                            spk_num = int(m.group(1))
                            name = m.group(2).strip()
                            # 过滤重复姓名
                            if name and " " in name:
                                parts = name.split()
                                if len(parts) == 2 and parts[0] == parts[1]:
                                    name = parts[0]
                            if name and len(name) < 50:
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

        self._transcribing = False  # 立即置 False，防止重入
        self._poll_timer.stop()

        # 等待线程结束（daemon 线程会在主线程退出时自动终止）
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        # 更新文件状态
        if file_path:
            self.file_status_changed.emit(file_path, FileStatus.PENDING)
        else:
            for fp in self._file_status:
                self.file_status_changed.emit(fp, FileStatus.PENDING)

        self.log_message.emit("转写已停止")


# ══════════════════════════════════════════════════════════
#  Worker Classes for Async Post-processing
# ══════════════════════════════════════════════════════════

from PySide6.QtCore import QThread


class AICorrectionWorker(QThread):
    """AI纠错Worker线程"""
    finished = Signal(str)  # corrected_text
    error = Signal(str)  # error_message

    def __init__(self, ai_service, raw_text, parent=None):
        super().__init__(parent)
        self._ai_service = ai_service
        self._raw_text = raw_text

    def run(self):
        try:
            corrected = self._ai_service.generate_correction(self._raw_text)
            if corrected:
                self.finished.emit(corrected)
            else:
                self.finished.emit(self._raw_text)
        except Exception as e:
            logger.error(f"AI correction failed: {e}")
            self.error.emit(str(e))


class AISummaryWorker(QThread):
    """AI摘要Worker线程"""
    finished = Signal(str)  # summary_text
    error = Signal(str)  # error_message

    def __init__(self, ai_service, transcript, voiceprint_matches=None, parent=None):
        super().__init__(parent)
        self._ai_service = ai_service
        self._transcript = transcript
        self._voiceprint_matches = voiceprint_matches or {}

    def run(self):
        try:
            summary = self._ai_service.generate_summary(
                self._transcript,
                voiceprint_matches=self._voiceprint_matches
            )
            if summary and not summary.startswith("[错误]"):
                self.finished.emit(summary)
            else:
                self.error.emit(summary or "摘要生成失败")
        except Exception as e:
            logger.error(f"AI summary failed: {e}")
            self.error.emit(str(e))
