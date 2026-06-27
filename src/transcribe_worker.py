#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 多进程转写工作函数
独立模块，避免子进程导入 GUI 库（customtkinter/tkinter）
"""

import os
import sys
import logging

# ── 子进程初始化：修复 Windows "spawn" 模式下 stdout/stderr 为 None 的问题 ──
# 这必须在任何其他导入之前执行
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# 在子进程中配置日志（只写文件，不写控制台）
# 打包模式使用 AppData 目录，开发模式使用项目目录
if getattr(sys, 'frozen', False):
    _data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'MeetScribe')
else:
    _src_dir = os.path.dirname(os.path.abspath(__file__))
    _data_dir = os.path.dirname(_src_dir)
_log_dir = os.path.join(_data_dir, "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "meetscribe.log")

_sub_logger = logging.getLogger("MeetScribe")
_sub_logger.setLevel(logging.DEBUG)
if not _sub_logger.handlers:
    _fh = logging.FileHandler(_log_file, encoding="utf-8", mode="a")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s [SUBPROCESS] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _sub_logger.addHandler(_fh)

logger = _sub_logger


def send_progress(queue, percent, stage, current_file, total_files, eta):
    """发送进度消息"""
    queue.put(("progress", {
        "percent": percent,
        "stage": stage,
        "current_file": current_file,
        "total_files": total_files,
        "eta": eta
    }))


def _send_embeddings(queue, transcriber):
    """从 transcriber 提取说话人嵌入向量并发送到主进程"""
    try:
        embeddings = getattr(transcriber, "spk_embeddings", {})
        logger.debug(f"[WORKER] spk_embeddings count: {len(embeddings)}")
        if embeddings:
            # 打印每个说话人的嵌入向量维度
            for spk_id, emb in embeddings.items():
                # emb 是 (embedding_list, quality) 元组
                if isinstance(emb, (tuple, list)) and len(emb) == 2:
                    emb_list = emb[0]
                    emb_len = len(emb_list) if hasattr(emb_list, '__len__') else 'unknown'
                else:
                    emb_len = len(emb) if hasattr(emb, '__len__') else 'unknown'
                logger.debug(f"[WORKER] Speaker {spk_id}: embedding dim={emb_len}"
                           f"{', WARN expected 192' if isinstance(emb_len, int) and emb_len != 192 else ''}")
            queue.put(("spk_embeddings", embeddings))
            logger.debug("[WORKER] Sent spk_embeddings to main process")
        else:
            logger.debug("[WORKER] No spk_embeddings to send")
    except Exception as e:
        logger.error(f"[WORKER] Failed to send embeddings: {e}")


def _send_sentences(queue, transcriber):
    """从 transcriber 提取句子列表并发送到主进程（用于中间片段截取）"""
    try:
        sentences = getattr(transcriber, "sentences", [])
        if sentences:
            # 只发送轻量字段，避免 pickle 大对象
            light_sentences = [
                {"spk": s.get("spk", -1), "start": s.get("start", 0), "end": s.get("end", 0)}
                for s in sentences
            ]
            queue.put(("sentences", light_sentences))
            logger.debug(f"[WORKER] Sent {len(light_sentences)} sentences to main process")
        else:
            logger.debug("[WORKER] No sentences to send")
    except Exception as e:
        logger.error(f"[WORKER] Failed to send sentences: {e}")


def transcribe_worker_process(queue, model_cache_dir, device,
                               file_paths, output_format, speaker_names,
                               output_dir, merge):
    """
    在独立进程中运行转写任务。
    通过 queue 发送消息给主进程:
        ("status", msg)          - 状态栏更新
        ("log", msg)             - 日志
        ("processing", fp)       - 文件开始处理
        ("file_done", fp, rpath) - 文件转写完成
        ("progress", {...})      - 转写进度 {percent, stage, current_file, total_files, eta}
        ("auto_summary", result, base, out_dir) - 需要生成摘要
        ("done",)                - 全部完成
        ("error", msg)           - 出错
    """
    try:
        logger.info("Subprocess started for transcription")

        # 确保 src 目录在 sys.path 中
        src_dir = os.path.dirname(os.path.abspath(__file__))
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        from transcriber import Transcriber

        queue.put(("log", "模型检查通过，开始转写..."))

        transcriber = Transcriber(model_cache_dir=model_cache_dir, device=device)

        ready, missing = transcriber.check_models_ready()
        if not ready:
            missing_str = "\n".join(f"  - {m}" for m in missing)
            queue.put(("error", f"缺少必需模型:\n{missing_str}"))
            return

        def progress_cb(msg):
            queue.put(("status", str(msg)))
            queue.put(("log", str(msg)))

        ext_map = {"llm-md": ".md", "md": ".md", "html": ".html",
                   "txt": ".txt", "srt": ".srt", "json": ".json"}
        ext = ext_map.get(output_format, ".txt")

        if merge:
            # 区分双轨对（mic + system 同一次录音）与普通多文件合并：
            # 双轨走 merge_dual_transcripts 按时间戳交错并加本地/远程前缀，
            # 普通多文件仍走 "## file" 顺序拼接。判定与合并都在
            # dual_track_merge.build_merged_transcript 这个纯函数里完成，
            # worker 只负责逐轨转写后把文本喂进去。
            from dual_track_merge import build_merged_transcript, is_dual_track_group

            is_dual = is_dual_track_group(file_paths) is not None
            mode_desc = "双轨" if is_dual else "多文件"
            queue.put(("log", f"合并模式（{mode_desc}）：将 {len(file_paths)} 个文件合并转写"))
            for fp in file_paths:
                queue.put(("processing", fp))

            first_name = os.path.basename(file_paths[0])
            base = os.path.splitext(first_name)[0] + "_merged"

            per_file_texts = {}
            import time as _time
            start_time = _time.time()
            for idx, fp in enumerate(file_paths):
                fname = os.path.basename(fp)
                queue.put(("log", f"正在转写: {fname}"))
                elapsed = _time.time() - start_time
                eta_sec = int(elapsed / max(idx, 1) * (len(file_paths) - idx)) if idx > 0 else 0
                eta_str = f"{eta_sec // 60}分{eta_sec % 60}秒" if eta_sec > 0 else "计算中..."
                send_progress(queue, int(idx / len(file_paths) * 100),
                              f"转写 {idx+1}/{len(file_paths)}", idx, len(file_paths), eta_str)
                result = transcriber.transcribe(
                    audio_path=fp, output_format=output_format,
                    speaker_names=speaker_names,
                    progress_callback=progress_cb,
                )
                per_file_texts[fp] = result

                # 提取并发送说话人嵌入向量（供音色库匹配）
                _send_embeddings(queue, transcriber)
                # 发送句子数据（供中间片段截取）
                _send_sentences(queue, transcriber)
            send_progress(queue, 100, "合并完成", len(file_paths), len(file_paths), "")

            merged_result, merged_is_dual = build_merged_transcript(
                file_paths, per_file_texts, mic_label="本地", sys_label="远程"
            )
            if merged_is_dual:
                queue.put(("log", "双轨按时间戳合并完成（本地/远程）"))
            rname = f"{base}_transcript.md"
            rpath = os.path.join(output_dir, rname)
            with open(rpath, "w", encoding="utf-8") as rf:
                rf.write(merged_result)

            # 通知主进程：创建合并行（隐藏子文件，显示合并行）
            queue.put(("merge_done", file_paths, rpath, base))

            # LLM 纠错（在摘要之前，确保摘要用的是纠错后的文本）
            queue.put(("auto_correction", merged_result, base, output_dir, rpath))
            # 合并转写也需要 AI 摘要
            queue.put(("auto_summary", base, output_dir))
            queue.put(("log", f"合并转写完成 -> {rname}"))

        else:
            import time as _time
            start_time = _time.time()
            for idx, fp in enumerate(file_paths):
                fname = os.path.basename(fp)
                queue.put(("processing", fp))
                queue.put(("log", f"正在转写: {fname}"))

                elapsed = _time.time() - start_time
                eta_sec = int(elapsed / max(idx, 1) * (len(file_paths) - idx)) if idx > 0 else 0
                eta_str = f"{eta_sec // 60}分{eta_sec % 60}秒" if eta_sec > 0 else "计算中..."
                send_progress(queue, int(idx / len(file_paths) * 100),
                              f"转写 {idx+1}/{len(file_paths)}", idx, len(file_paths), eta_str)

                result = transcriber.transcribe(
                    audio_path=fp, output_format=output_format,
                    speaker_names=speaker_names,
                    progress_callback=progress_cb,
                )

                # 提取并发送说话人嵌入向量（供音色库匹配）
                _send_embeddings(queue, transcriber)
                # 发送句子数据（供中间片段截取）
                _send_sentences(queue, transcriber)

                base = os.path.splitext(fname)[0]
                rname = f"{base}_transcript{ext}"
                rpath = os.path.join(output_dir, rname)
                with open(rpath, "w", encoding="utf-8") as rf:
                    rf.write(result)

                queue.put(("file_done", fp, rpath))
                queue.put(("log", f"完成: {fname} -> {rname}"))

                # LLM 纠错（在摘要之前，确保摘要用的是纠错后的文本）
                queue.put(("auto_correction", result, base, output_dir, rpath))
                # AI 摘要在主进程处理（需要 API key），从文件读取（可能是纠错后的）
                queue.put(("auto_summary", base, output_dir))

        queue.put(("done",))

    except Exception as e:
        import traceback
        queue.put(("error", str(e)))
        queue.put(("log", f"转写失败: {e}\n{traceback.format_exc()}"))
