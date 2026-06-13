#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 转写调度和 AI 后处理
"""

import os
import re
import json
import logging
import threading
import multiprocessing

from gui.styles import MODEL_CACHE_DIR
from file_manager import FileStatus, TranscriptionProgress
from transcribe_worker import transcribe_worker_process
from utils import apply_speaker_mapping
from transcription_queue import TranscriptionQueue, TranscriptionTask

logger = logging.getLogger("MeetScribe")


class TranscriptionHandler:
    """转写任务调度器"""

    def __init__(self, app):
        """
        Args:
            app: MeetScribeApp 实例，用于访问 config, file_manager, _log 等
        """
        self._app = app
        self._transcribing = False
        self._queue = None
        self._process = None
        self._ai_service = None
        self._file_status = {}  # file_path -> "done" | "failed"
        self._progress = TranscriptionProgress()
        self._file_queue = []  # 转写队列（文件路径列表，按优先级排序）
        self._speaker_embeddings = {}  # {spk_id: embedding_vector} 音色库匹配用
        self._speaker_qualities = {}  # {spk_id: quality}
        self._sentences = []  # 转写句子列表（供中间片段截取）
        self._task_queue = TranscriptionQueue(app)  # 任务队列管理
        self._poll_interval = 50  # 初始轮询间隔（毫秒）
        self._current_batch_paths = set()  # 当前批次的文件路径集合
        self._voiceprint_matched = False  # 音色库匹配防重入 guard
        self._voiceprint_match_results = {}  # 音色库匹配结果 {spk_id: {"name", "confidence"}}

    @property
    def is_transcribing(self):
        return self._transcribing

    def _execute_task(self, task: TranscriptionTask):
        """执行转写任务"""
        self._transcribing = True
        self._file_status = {}  # 重置文件状态计数
        self._speaker_embeddings = {}  # 重置说话人嵌入向量
        self._speaker_qualities = {}  # 重置说话人质量分数
        self._sentences = []  # 重置句子数据
        self._voiceprint_matched = False  # 重置防重入 guard
        self._voiceprint_match_results = {}  # 重置音色库匹配结果
        self._current_batch_paths = set(task.file_paths)  # 记录当前批次文件

        # 合并模式：立即在 UI 上合并为一行
        if task.merge:
            source_names = [os.path.basename(fp) for fp in task.file_paths]
            merged_display = "、".join(source_names)
            self._app.file_manager.create_merged_group(task.file_paths, merged_display)
            self._app.file_manager.update_status(task.file_paths[0], FileStatus.PROCESSING)
            self._app._refresh_file_list()

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
        self._poll(task.file_paths)

    def get_queue_status(self) -> dict:
        """获取队列状态（供 UI 调用）"""
        return self._task_queue.get_queue_status()

    def get_queue_status_text(self) -> str:
        """获取队列状态文本（供 UI 显示）"""
        return self._task_queue.get_status_text()

    # ── Queue Management ───────────────────────────────────────

    def add_to_queue(self, file_paths):
        """添加文件到转写队列"""
        self._file_queue.extend(file_paths)

    def remove_from_queue(self, file_path):
        """从队列中移除文件"""
        if file_path in self._file_queue:
            self._file_queue.remove(file_path)

    def move_up_in_queue(self, file_path):
        """在队列中上移文件（提高优先级）"""
        idx = self._file_queue.index(file_path)
        if idx > 0:
            self._file_queue[idx], self._file_queue[idx - 1] = self._file_queue[idx - 1], self._file_queue[idx]

    def move_down_in_queue(self, file_path):
        """在队列中下移文件（降低优先级）"""
        idx = self._file_queue.index(file_path)
        if idx < len(self._file_queue) - 1:
            self._file_queue[idx], self._file_queue[idx + 1] = self._file_queue[idx + 1], self._file_queue[idx]

    def get_queue(self):
        """获取转写队列（副本）"""
        return self._file_queue.copy()

    def get_queue_position(self, file_path):
        """获取文件在队列中的位置（从 1 开始），不在队列中返回 0"""
        try:
            return self._file_queue.index(file_path) + 1
        except ValueError:
            return 0

    def start(self, file_paths, fmt, speaker_names, out_dir, merge=False):
        """启动转写任务"""
        # 创建任务
        task = TranscriptionTask(
            file_paths=file_paths,
            fmt=fmt,
            speaker_names=speaker_names,
            out_dir=out_dir,
            merge=merge,
        )

        # 如果正在转写，加入队列
        if self._transcribing:
            self._task_queue.add_task(task)
            self._app.home_page.update_queue_status()
            return

        # 立即执行
        self._execute_task(task)

    def _poll(self, file_paths):
        """自适应轮询转写进度 - 空闲时指数退避减少 CPU 消耗"""
        has_messages = False
        try:
            while not self._queue.empty():
                msg = self._queue.get_nowait()
                msg_type = msg[0]

                try:
                    if msg_type == "status":
                        self._app._set_status(msg[1])
                    elif msg_type == "log":
                        self._app._log(msg[1])
                    elif msg_type == "processing":
                        self._app.file_manager.update_status(msg[1], FileStatus.PROCESSING)
                        self._file_status[msg[1]] = "processing"
                    elif msg_type == "file_done":
                        fp, rpath = msg[1], msg[2]
                        self._app.file_manager.update_status(fp, FileStatus.DONE, rpath)
                        self._file_status[fp] = "done"
                        # 重置 speaker_names，确保新转写重新匹配
                        item = self._app.file_manager.get_file(fp)
                        if item:
                            item.speaker_names = {}
                    elif msg_type == "merge_done":
                        src_paths, rpath, base = msg[1], msg[2], msg[3]
                        self._app.file_manager.update_status(src_paths[0], FileStatus.DONE, rpath)
                        self._app._refresh_file_list()
                        self._file_status[src_paths[0]] = "done"
                    elif msg_type == "auto_correction":
                        raw_text, base, out_dir, transcript_path = msg[1], msg[2], msg[3], msg[4]
                        auto_correction = self._app.config.get("auto_correction", "关闭")
                        if auto_correction == "转写后自动纠错":
                            self._app._log("正在进行 LLM 转写纠错...")
                            self._process_auto_correction(raw_text, base, out_dir, transcript_path)
                    elif msg_type == "auto_summary":
                        base, out_dir = msg[1], msg[2]
                        # 音色库匹配已移到 _on_done()，确保在 file_done 之后执行
                        # 这里只生成 AI 摘要
                        auto_summary = self._app.config.get("auto_summary", "关闭")
                        if auto_summary == "转写后自动生成":
                            self._process_auto_summary(base, out_dir)
                    elif msg_type == "progress":
                        self._update_progress(msg[1])
                    elif msg_type == "spk_embeddings":
                        logger.debug(f"[MAIN] Received spk_embeddings: {len(msg[1])} speakers")
                        for spk_id, data in msg[1].items():
                            # multiprocessing pickle 序列化会将 tuple 转为 list，需兼容两种类型
                            is_tuple = isinstance(data, (tuple, list))
                            has_2_elems = len(data) == 2 if is_tuple else False
                            elem1_is_num = isinstance(data[1], (int, float)) if has_2_elems else False
                            logger.debug(f"[MAIN] spk {spk_id}: is_tuple={is_tuple}, has_2={has_2_elems}, elem1_num={elem1_is_num}, type(data)={type(data)}")
                            if is_tuple and has_2_elems and elem1_is_num:
                                embedding, quality = data
                                self._speaker_embeddings[spk_id] = embedding
                                self._speaker_qualities[spk_id] = quality
                                logger.debug(f"[MAIN] spk {spk_id}: quality={quality}")
                            else:
                                self._speaker_embeddings[spk_id] = data
                                self._speaker_qualities[spk_id] = 0.85  # fallback
                                logger.debug(f"[MAIN] spk {spk_id}: fallback quality=0.85, data_type={type(data)}")
                        logger.debug(f"[MAIN] Total embeddings now: {len(self._speaker_embeddings)}")
                    elif msg_type == "sentences":
                        self._sentences = msg[1]
                        logger.debug(f"[MAIN] Received {len(self._sentences)} sentences")
                    elif msg_type == "error":
                        self._app._log(f"转写失败: {msg[1]}")
                        for fp in file_paths:
                            try:
                                item = self._app.file_manager.get_file(fp)
                                if item and item.status == FileStatus.PROCESSING:
                                    self._app.file_manager.update_status(fp, FileStatus.FAILED, None, str(msg[1])[:60])
                                    self._file_status[fp] = "failed"
                            except Exception:
                                pass
                        self._on_done()
                        return
                    elif msg_type == "done":
                        self._on_done()
                        return

                    has_messages = True
                except Exception as msg_err:
                    self._app._log(f"处理消息时出错: {msg_err}")

        except Exception as poll_err:
            self._app._log(f"队列读取出错: {poll_err}")

        # 更新轮询间隔：有消息时快速轮询，无消息时指数退避
        if has_messages:
            self._poll_interval = 50  # 有消息时快速轮询
        else:
            # 无消息时指数退避，最大 500ms
            self._poll_interval = min(self._poll_interval * 1.5, 500)

        # 检查进程是否还活着
        try:
            if self._process is not None and self._process.is_alive():
                self._app.after(int(self._poll_interval), self._poll, file_paths)
            elif self._process is not None:
                self._process.join(timeout=1)
                self._process = None
                if self._transcribing:
                    self._on_done()
        except Exception:
            if self._transcribing:
                self._on_done()

    def stop_transcription(self, file_path=None):
        """停止转写

        注意：此方法只能在主线程调用（因为它使用了 messagebox）
        """
        if not self._transcribing:
            return

        # 确认停止
        from tkinter import messagebox
        if not messagebox.askyesno("确认停止", "停止后当前转写进度不会保存，需要重新进行转写。\n\n是否继续？"):
            return

        # 终止转写进程
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)

        # 更新文件状态
        if file_path:
            self._app.file_manager.update_status(file_path, FileStatus.PENDING)
        else:
            # 停止所有正在处理的文件
            for fp, status in self._file_status.items():
                if status == "processing":
                    self._app.file_manager.update_status(fp, FileStatus.PENDING)

        self._transcribing = False
        self._app.after(0, self._app._refresh_file_list)
        self._app._set_status("转写已停止")

    def _on_done(self):
        """转写完成"""
        self._transcribing = False

        # 统计成功/失败数量
        success_count = sum(1 for s in self._file_status.values() if s == "done")
        fail_count = sum(1 for s in self._file_status.values() if s == "failed")

        # 清理多进程资源
        try:
            if self._process is not None:
                if self._process.is_alive():
                    self._process.terminate()
                self._process.join(timeout=2)
                self._process = None
            self._queue = None
        except Exception:
            self._process = None
            self._queue = None

        # 清除进度显示
        self._progress = TranscriptionProgress()
        try:
            self._app._refresh_file_list()
        except Exception:
            pass

        # 双轨合并（在通知 app 之前执行）
        try:
            self._merge_dual_track_results()
        except Exception as e:
            self._app._log(f"双轨合并异常: {e}")

        # 音色库匹配（必须在 file_done 之后、摘要生成之前执行）
        # _match_voiceprints() 内部有 guard 防止重复执行
        try:
            self._match_voiceprints()
        except Exception as e:
            self._app._log(f"音色库匹配异常: {e}")

        # 保存声纹嵌入向量到磁盘（程序重启后可恢复）
        try:
            self._save_embeddings_to_disk()
        except Exception as e:
            logger.debug(f"[EMBEDDINGS] 保存嵌入向量失败: {e}")

        # 通知 app
        try:
            self._app._on_transcription_done(success_count, fail_count)
        except Exception:
            pass

        # 完成当前任务并检查队列
        self._task_queue.complete_current_task()
        self._check_queue()

    def _check_queue(self):
        """检查队列，执行下一个任务"""
        # 更新队列状态显示
        try:
            self._app.home_page.update_queue_status()
        except Exception:
            pass

        next_task = self._task_queue.get_next_task()
        if next_task:
            self._app._log(f"开始执行队列中的下一个任务: {len(next_task.file_paths)} 个文件")
            self._execute_task(next_task)

    def _save_embeddings_to_disk(self):
        """将声纹嵌入向量保存到磁盘，程序重启后可恢复"""
        if not self._speaker_embeddings:
            return

        # 按文件分组保存：遍历当前批次的文件，每个文件保存对应的嵌入向量
        for fp in self._current_batch_paths:
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
                        "quality": self._speaker_qualities.get(spk_id, 0.85),
                    }
                else:
                    emb_data[str(spk_id)] = {
                        "vector": list(embedding) if embedding is not None else [],
                        "quality": self._speaker_qualities.get(spk_id, 0.85),
                    }

            try:
                with open(emb_path, "w", encoding="utf-8") as f:
                    json.dump(emb_data, f, ensure_ascii=False, indent=2)
                logger.debug(f"[EMBEDDINGS] 已保存到 {emb_path} ({len(emb_data)} 个说话人)")
            except Exception as e:
                logger.warning(f"[EMBEDDINGS] 保存失败: {e}")

    def _update_progress(self, data):
        """更新转写进度"""
        self._progress.percent = data.get("percent", 0)
        self._progress.stage = data.get("stage", "")
        self._progress.current_file = data.get("current_file", 0)
        self._progress.total_files = data.get("total_files", 0)
        self._progress.eta = data.get("eta", "")

        # 更新 UI 进度显示
        try:
            self._app._set_status(f"转写中: {self._progress.stage} ({self._progress.percent}%)")
            self._app.home_page.update_transcription_progress(self._progress)
        except Exception:
            pass

    def _get_ai_service(self):
        """获取 AI 服务实例（懒加载）"""
        if self._ai_service is None:
            # 读新格式配置
            vendor = self._app.config.get("ai_vendor", "")
            api_key = self._app.config.get("ai_api_key", "")
            if not api_key:
                # 向后兼容：尝试读旧格式
                api_key = self._app.config.get("mimo_api_key", "")
            if not api_key:
                return None

            from ai_service import AIService
            self._ai_service = AIService(
                vendor=vendor or self._app.config.get("ai_vendor", "小米"),
                model=self._app.config.get("ai_model", "MiMo-V2.5-Pro"),
                access_mode=self._app.config.get("ai_access_mode", "按量计费"),
                api_key=api_key,
            )
        return self._ai_service

    def _generate_correction(self, raw_text, base_name, out_dir, transcript_path):
        """LLM 转写纠错"""
        try:
            ai = self._get_ai_service()
            if not ai:
                self._app._log("未配置云端 API Key，跳过转写纠错")
                return
            corrected = ai.generate_correction(raw_text)
            if corrected:
                raw_path = os.path.join(out_dir, f"{base_name}_transcript_raw.md")
                if not os.path.exists(raw_path):
                    with open(raw_path, "w", encoding="utf-8") as rf:
                        rf.write(raw_text)
                    self._app._log(f"原始转写已备份: {os.path.basename(raw_path)}")
                with open(transcript_path, "w", encoding="utf-8") as tf:
                    tf.write(corrected)
                self._app._log("LLM 转写纠错完成")
            else:
                self._app._log("LLM 纠错无变化，保留原文")
        except Exception as e:
            self._app._log(f"LLM 转写纠错异常（已保留原文）: {e}")

    def _generate_summary(self, transcript, base_name, out_dir):
        """AI 摘要生成"""
        try:
            ai = self._get_ai_service()
            if not ai:
                self._app._log("未配置云端 API Key，跳过自动摘要")
                return
            voiceprint_matches = getattr(self, '_voiceprint_match_results', None)
            summary = ai.generate_summary(transcript, voiceprint_matches=voiceprint_matches)
            if summary and not summary.startswith("[错误]"):
                summary_name = f"{base_name}_summary.md"
                summary_path = os.path.join(out_dir, summary_name)
                with open(summary_path, "w", encoding="utf-8") as sf:
                    sf.write(summary)
                self._app._log(f"摘要已保存: {summary_name}")

                # 提取主题
                topic = _extract_topic_from_summary(summary)
                if topic:
                    for item in self._app.file_manager.files:
                        if item.result_path and os.path.basename(item.result_path).startswith(base_name + "_transcript"):
                            self._app.file_manager.update_topic(item.file_path, topic)
                            self._app._log(f"会议主题: {topic}")
                            break

                # 提取参会人员映射
                speaker_mapping = _extract_speaker_mapping_from_summary(summary)
                if speaker_mapping:
                    for item in self._app.file_manager.files:
                        if item.result_path and os.path.basename(item.result_path).startswith(base_name + "_transcript"):
                            if os.path.exists(item.result_path):
                                apply_speaker_mapping(item.result_path, speaker_mapping)
                            summary_path = os.path.join(out_dir, summary_name)
                            if os.path.exists(summary_path):
                                apply_speaker_mapping(summary_path, speaker_mapping)
                            str_mapping = {str(k): v for k, v in speaker_mapping.items()}
                            self._app.file_manager.update_speaker_names(item.file_path, str_mapping)
                            self._app._log(f"已自动识别参会人员: {', '.join(f'Speaker {k}→{v}' for k, v in speaker_mapping.items())}")
                            break
            else:
                self._app._log(f"摘要生成失败: {summary}")
        except Exception as e:
            self._app._log(f"摘要生成异常: {e}")

    def _process_auto_correction(self, raw_text, base, out_dir, transcript_path):
        """异步处理自动修正 - 将 AI 纠错移到后台线程，避免大文件阻塞 UI"""
        def _do_work():
            try:
                self._generate_correction(raw_text, base, out_dir, transcript_path)
            except Exception as e:
                self._app.after(0, lambda: self._app._log(f"自动纠错异常: {e}"))

        threading.Thread(target=_do_work, daemon=True).start()

    def _process_auto_summary(self, base, out_dir):
        """异步处理自动摘要 - 将文件读取和 AI 摘要移到后台线程，避免大文件阻塞 UI"""
        def _do_work():
            try:
                ext = ".md"
                transcript_path = os.path.join(out_dir, f"{base}_transcript{ext}")
                if not os.path.exists(transcript_path):
                    for try_ext in [".txt", ".html", ".srt", ".json"]:
                        transcript_path = os.path.join(out_dir, f"{base}_transcript{try_ext}")
                        if os.path.exists(transcript_path):
                            break
                if os.path.exists(transcript_path):
                    with open(transcript_path, "r", encoding="utf-8") as tf:
                        result = tf.read()
                    self._app.after(0, lambda: self._app._log("正在生成 AI 摘要..."))
                    self._generate_summary(result, base, out_dir)
                else:
                    self._app.after(0, lambda: self._app._log("未找到转写文件，跳过摘要生成"))
            except Exception as e:
                self._app.after(0, lambda: self._app._log(f"读取转写文件失败: {e}"))

        threading.Thread(target=_do_work, daemon=True).start()

    def _merge_dual_track_results(self):
        """合并双轨转写结果"""
        from dual_track_merge import find_dual_track_pair, merge_dual_transcripts

        done_files = self._app.file_manager.get_done_files()
        merged_pairs = set()

        self._app._log(f"开始检查双轨合并，已完成文件数: {len(done_files)}")

        for item in done_files:
            fp = item.file_path
            result_path = item.result_path

            if not result_path or not os.path.exists(result_path):
                continue

            pair = find_dual_track_pair(fp)
            if not pair:
                self._app._log(f"未找到双轨配对: {os.path.basename(fp)}")
                continue

            mic_path, sys_path = pair
            pair_key = (mic_path, sys_path)

            if pair_key in merged_pairs:
                self._app._log(f"已处理过此配对，跳过: {os.path.basename(mic_path)}")
                continue

            mic_item = self._app.file_manager.get_file(mic_path)
            sys_item = self._app.file_manager.get_file(sys_path)

            if not mic_item or not sys_item:
                self._app._log(f"双轨配对文件不存在: {os.path.basename(mic_path)} 或 {os.path.basename(sys_path)}")
                continue
            if mic_item.status != FileStatus.DONE or sys_item.status != FileStatus.DONE:
                self._app._log(f"双轨配对文件未完成: {os.path.basename(mic_path)} ({mic_item.status}) 或 {os.path.basename(sys_path)} ({sys_item.status})")
                continue
            if not mic_item.result_path or not sys_item.result_path:
                self._app._log(f"双轨配对文件无转写结果: {os.path.basename(mic_path)} 或 {os.path.basename(sys_path)}")
                continue

            try:
                with open(mic_item.result_path, "r", encoding="utf-8") as f:
                    mic_text = f.read()
                with open(sys_item.result_path, "r", encoding="utf-8") as f:
                    sys_text = f.read()

                merged_text = merge_dual_transcripts(mic_text, sys_text)

                with open(mic_item.result_path, "w", encoding="utf-8") as f:
                    f.write(merged_text)

                self._app._log(f"双轨合并完成: {os.path.basename(mic_item.result_path)}")
                merged_pairs.add(pair_key)

            except Exception as e:
                self._app._log(f"双轨合并失败: {e}")

    def _match_voiceprints(self):
        """用音色库匹配转写结果中的说话人"""
        if not self._speaker_embeddings:
            logger.debug("[VOICEPRINT] No speaker embeddings available")
            return  # 无数据直接返回，不消耗 guard
        if self._voiceprint_matched:
            logger.debug("[VOICEPRINT] Already matched, skipping")
            return  # 有数据但已匹配过，跳过
        self._voiceprint_matched = True
        self._voiceprint_match_results = {}

        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()

            speaker_embeddings = self._extract_speaker_embeddings()
            if not speaker_embeddings:
                logger.debug("[VOICEPRINT] No valid speaker embeddings extracted")
                return

            logger.debug(f"[VOICEPRINT] Matching {len(speaker_embeddings)} speakers against library")
            matched_count = 0
            for speaker_id, embedding in speaker_embeddings.items():
                name, confidence = library.match_with_confidence(embedding)
                logger.debug(f"[VOICEPRINT] Speaker {speaker_id + 1}: match={name}, confidence={confidence}")
                if name:
                    # 更新文件管理器中的说话人映射（仅当前批次）
                    logger.debug(f"[VOICEPRINT] Current batch paths: {self._current_batch_paths}")
                    for item in self._app.file_manager.files:
                        if item.status == FileStatus.DONE and item.result_path:
                            # P1-3: 只处理当前批次的文件，不修改历史文件
                            if item.file_path not in self._current_batch_paths:
                                continue
                            logger.debug(f"[VOICEPRINT] Processing file: {item.file_path}")
                            str_mapping = item.speaker_names or {}
                            # speaker_id 是 0-indexed，转写文件中 Speaker N 是 1-indexed
                            str_key = str(speaker_id + 1)  # 转换为 1-indexed
                            # 检查是否需要更新：不存在、以 Speaker 开头、或包含 Speaker（处理 [Speaker N] 格式）
                            current_name = str_mapping.get(str_key, "")
                            needs_update = (
                                str_key not in str_mapping
                                or current_name.startswith("Speaker")
                                or "Speaker" in current_name
                            )
                            if needs_update:
                                str_mapping[str_key] = name
                                self._app.file_manager.update_speaker_names(
                                    item.file_path, str_mapping
                                )
                                # 应用到转写文件
                                if os.path.exists(item.result_path):
                                    from utils import apply_speaker_mapping
                                    logger.debug(f"[VOICEPRINT] Applying mapping: Speaker {speaker_id + 1} -> {name} to {item.result_path}")
                                    apply_speaker_mapping(
                                        item.result_path, {speaker_id + 1: name}
                                    )
                                    # 同时应用到摘要文件
                                    summary_path = item.result_path.replace("_transcript", "_summary")
                                    if os.path.exists(summary_path):
                                        logger.debug(f"[VOICEPRINT] Applying mapping to summary: {summary_path}")
                                        apply_speaker_mapping(
                                            summary_path, {speaker_id + 1: name}
                                        )
                    matched_count += 1
                    self._voiceprint_match_results[speaker_id] = {
                        "name": name,
                        "confidence": confidence,
                    }
                    self._app._log(
                        f"音色库匹配: Speaker {speaker_id + 1} -> {name} ({confidence})"
                    )
                    # 高置信度匹配后，自动添加嵌入向量到音色库
                    if confidence == "confirmed":
                        try:
                            quality = self._speaker_qualities.get(speaker_id, 0.85)
                            library.add_speaker(name, embedding, source=item.file_name, quality=quality)
                            logger.info(f"自动添加声纹样本: {name}")
                        except Exception as e:
                            logger.warning(f"自动添加声纹失败: {e}")

            if matched_count > 0:
                logger.info(f"[VOICEPRINT] Matched {matched_count} speakers")
                self._app._log(f"音色库匹配完成: {matched_count} 位说话人已识别")
            else:
                logger.info("[VOICEPRINT] No speakers matched")
                self._app._log("音色库匹配: 未找到匹配的说话人")

        except ImportError:
            logger.debug("Voiceprint module not available, skipping matching")
        except Exception as e:
            logger.error(f"Voiceprint matching failed: {e}", exc_info=True)

    def _extract_speaker_embeddings(self):
        """从接收到的嵌入向量中提取每个说话人的代表向量"""
        if not self._speaker_embeddings:
            return {}

        embeddings = {}
        for spk_id, embedding in self._speaker_embeddings.items():
            if embedding is not None:
                embeddings[int(spk_id)] = embedding
        return embeddings


# ── 工具函数 ─────────────────────────────────────────────────

def _extract_speaker_mapping_from_summary(summary_text):
    """从 AI 摘要的参会人员部分提取 Speaker ID → 姓名映射"""
    mapping = {}

    # 容错多种标题格式
    section = re.search(
        r'#+\s*(?:参会人员|与会者|出席人员|Participants)\s*\n(.*?)(?=\n#{1,3}\s|\Z)',
        summary_text, re.DOTALL | re.IGNORECASE
    )
    section_text = section.group(1) if section else summary_text

    # 匹配 [Speaker N] 姓名（可选：— 角色描述）
    for m in re.finditer(r'\[Speaker\s+(\d+)\]\s+(.+?)(?:\s*[—\-]\s*.*)?$', section_text, re.MULTILINE):
        spk_id = int(m.group(1))
        name = m.group(2).strip().strip('*_#,，。')
        # 过滤角色推断部分
        name = re.sub(r'[（(]角色推断.*$', '', name).strip()
        name = re.sub(r'[（(]推测.*$', '', name).strip()
        if name and name != f"Speaker {spk_id}" and not name.startswith("Speaker"):
            mapping[spk_id] = name

    return mapping



def _extract_topic_from_summary(summary_text):
    """从 AI 摘要中提取会议主题"""
    m = re.search(r'#+\s*会议主题\s*\n\s*(.+)', summary_text)
    if m:
        topic = m.group(1).strip()
        topic = topic.strip('*_#>- ')
        return topic if topic else ""
    return ""

