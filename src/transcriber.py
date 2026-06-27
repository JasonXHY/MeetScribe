#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 转写引擎
基于 FunASR 的 SenseVoice(ASR) + CAM++(说话人分离) + fsmn-vad(VAD)
"""

import os
import re
import sys
import json
import math
import time
import html
import logging
import subprocess
import shutil
import tempfile
import threading
from datetime import datetime

from gui.styles import SPEAKER_COLORS
from formatters import TranscriptFormatter

logger = logging.getLogger("MeetScribe")


def _compute_quality(segment_count, total_duration_sec):
    """计算嵌入质量分数

    Args:
        segment_count: 说话人片段数
        total_duration_sec: 总语音时长（秒）

    Returns:
        质量分数 [0.5, 1.0]
    """
    q_seg = min(1.0, math.log2(max(1, segment_count)) / 3.0)
    q_dur = min(1.0, total_duration_sec / 60.0)
    raw = 0.6 * q_seg + 0.4 * q_dur
    return round(0.5 + 0.5 * raw, 3)


# ── 模型定义 ──────────────────────────────────────────────
# 所有需要的模型，固化在这里，方便管理和检查
REQUIRED_MODELS = {
    "SenseVoiceSmall": {
        "alias": "iic/SenseVoiceSmall",
        "ms_id": "iic/SenseVoiceSmall",
        "description": "语音识别 (ASR)",
        "required": True,
        "size_hint": "~900MB",
        "min_size_mb": 800,
    },
    "fsmn-vad": {
        "alias": "fsmn-vad",
        "ms_id": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        "description": "语音端点检测 (VAD)",
        "required": True,
        "size_hint": "~2MB",
        "min_size_mb": 1,
    },
    "ct-punc": {
        "alias": "ct-punc",
        "ms_id": "iic/punc_ct-transformer_cn-en-common-vocab471067-large",
        "description": "标点恢复",
        "required": True,
        "size_hint": "~1GB",
        "min_size_mb": 1000,
    },
    "cam++": {
        "alias": "cam++",
        "ms_id": "iic/speech_campplus_sv_zh-cn_16k-common",
        "description": "说话人分离",
        "required": True,
        "size_hint": "~60MB",
        "min_size_mb": 20,
    },
}

# 每个模型运行时必需的辅助文件（如 tokenizer）
REQUIRED_AUX_FILES = {
    "SenseVoiceSmall": ["chn_jpn_yue_eng_ko_spectok.bpe.model"],
    "fsmn-vad": [],
    "ct-punc": [],
    "cam++": [],
}

# 兼容旧代码的别名映射
_MODEL_ALIASES = {k: v["ms_id"] for k, v in REQUIRED_MODELS.items()}

# 全局 MODELSCOPE_CACHE 设置标志
_MODELSCOPE_CACHE_SET = False

# 追踪 _safe_model_path 创建的临时目录，便于会话结束时清理
_temp_model_dirs = []


def _setup_modelscope_cache(cache_dir):
    """在最早时机设置 MODELSCOPE_CACHE 环境变量，确保 FunASR 使用指定缓存目录"""
    global _MODELSCOPE_CACHE_SET
    if _MODELSCOPE_CACHE_SET or not cache_dir:
        return
    os.environ["MODELSCOPE_CACHE"] = cache_dir
    os.environ.setdefault("MODELSCOPE_SCENARIO", "cli")

    # 增大 SDK 超时（默认 60s 对慢速网络不够）
    # 依赖 modelscope.hub.constants，版本变化时静默跳过
    try:
        import modelscope.hub.constants as hc
        hc.API_FILE_DOWNLOAD_TIMEOUT = 180  # per-socket-read: 180s
        hc.API_HTTP_CLIENT_TIMEOUT = 180    # 连接+API调用: 180s
    except (ImportError, AttributeError):
        pass

    _MODELSCOPE_CACHE_SET = True
    logger.info(f"MODELSCOPE_CACHE set to: {cache_dir}")


def _resolve_model_path(model_id, cache_dir):
    """
    将模型 ID（别名或 ModelScope ID）解析为本地缓存路径。
    只返回已缓存的路径，不触发下载。
    """
    ms_id = _MODEL_ALIASES.get(model_id, model_id)

    # 已经是本地绝对路径且存在
    if os.path.isabs(ms_id) and os.path.isdir(ms_id):
        return ms_id

    # 从 ModelScope ID 提取目录名
    parts = ms_id.split("/")
    model_name = parts[-1] if len(parts) >= 2 else ms_id

    # 检查本地缓存
    if cache_dir:
        local_path = os.path.join(cache_dir, "models", "iic", model_name)
        if os.path.isdir(local_path):
            return local_path

    # 返回 None 表示未缓存
    return None


class ModelManager:
    """模型管理器 - 检查、下载、状态记录"""

    _download_lock = threading.Lock()

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.status_file = os.path.join(cache_dir, "model_status.json")
        _setup_modelscope_cache(cache_dir)

    def _get_model_path(self, model_id):
        """获取模型本地缓存路径"""
        if model_id not in REQUIRED_MODELS:
            return None
        ms_id = REQUIRED_MODELS[model_id]["ms_id"]
        parts = ms_id.split("/")
        model_name = parts[-1] if len(parts) >= 2 else ms_id
        return os.path.join(self.cache_dir, "models", "iic", model_name)

    def check_all_models(self):
        """
        检查所有模型的缓存状态

        Returns:
            dict: {model_id: {"cached": bool, "path": str|None, "info": dict, "aux_missing": list}}
        """
        results = {}
        for model_id, info in REQUIRED_MODELS.items():
            local_path = self._get_model_path(model_id)

            # 检查目录是否存在
            dir_exists = os.path.isdir(local_path) if local_path else False

            # 检查模型权重文件是否存在
            has_weights = False
            weight_file = None
            if dir_exists:
                config_file = os.path.join(local_path, "configuration.json")
                if os.path.isfile(config_file):
                    try:
                        import json
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        weight_file = config.get("file_path_metas", {}).get("init_param", "model.pt")
                        has_weights = os.path.isfile(os.path.join(local_path, weight_file))
                    except Exception:
                        has_weights = (
                            os.path.isfile(os.path.join(local_path, "model.pt")) or
                            os.path.isfile(os.path.join(local_path, "campplus_cn_common.bin"))
                        )
                else:
                    has_weights = (
                        os.path.isfile(os.path.join(local_path, "model.pt")) or
                        os.path.isfile(os.path.join(local_path, "campplus_cn_common.bin"))
                    )

            # 检查文件大小（防止截断/损坏文件通过检查）
            size_ok = True
            if has_weights and weight_file:
                min_size = info.get("min_size_mb", 0) * 1024 * 1024
                if min_size > 0:
                    actual_size = os.path.getsize(os.path.join(local_path, weight_file))
                    if actual_size < min_size:
                        size_ok = False
                        has_weights = False

            # 检查必需辅助文件
            aux_files = REQUIRED_AUX_FILES.get(model_id, [])
            aux_missing = []
            if dir_exists:
                for aux_file in aux_files:
                    if not os.path.isfile(os.path.join(local_path, aux_file)):
                        aux_missing.append(aux_file)

            cached = dir_exists and has_weights and size_ok and not aux_missing

            results[model_id] = {
                "cached": cached,
                "path": local_path if cached else None,
                "info": info,
                "aux_missing": aux_missing,
            }

        self._save_status(results)
        return results

    def get_missing_models(self, required_only=True):
        """获取缺失的模型列表"""
        status = self.check_all_models()
        missing = []
        for model_id, state in status.items():
            if not state["cached"]:
                if required_only and not state["info"]["required"]:
                    continue
                missing.append(model_id)
        return missing

    def download_model(self, model_id, progress_callback=None, max_retries=3):
        """
        下载指定模型

        Returns:
            (success: bool, message: str)
        """
        if model_id not in REQUIRED_MODELS:
            return False, f"未知模型: {model_id}"

        if not self._download_lock.acquire(blocking=False):
            return False, "已有下载任务正在进行"

        try:
            return self._download_model_inner(model_id, progress_callback, max_retries)
        finally:
            self._download_lock.release()

    def _download_model_inner(self, model_id, progress_callback, max_retries):
        info = REQUIRED_MODELS[model_id]

        # 检查是否已完整缓存
        status = self.check_all_models()
        if status.get(model_id, {}).get("cached"):
            return True, f"模型 {model_id} 已在本地缓存"

        last_error = None
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"下载 {model_id} 失败，{wait}s 后重试 ({attempt+1}/{max_retries})")
                if progress_callback:
                    progress_callback(f"下载失败，{wait}s 后重试...")
                time.sleep(wait)

            if progress_callback:
                progress_callback(f"正在下载 {model_id} ({info['size_hint']})...")

            try:
                _setup_modelscope_cache(self.cache_dir)
                from modelscope import snapshot_download
                ms_id = info["ms_id"]
                snapshot_download(ms_id, cache_dir=self.cache_dir)

                # 下载后校验完整性
                status = self.check_all_models()
                if status.get(model_id, {}).get("cached"):
                    return True, f"模型 {model_id} 下载完成且验证通过"
                else:
                    aux = status.get(model_id, {}).get("aux_missing", [])
                    if aux:
                        last_error = f"下载不完整：缺少辅助文件 {', '.join(aux)}"
                    else:
                        last_error = f"下载不完整：模型 {model_id} 未通过完整性校验"

            except Exception as e:
                last_error = self._classify_download_error(e)

        logger.error(f"下载模型 {model_id} 失败（已重试 {max_retries} 次）: {last_error}")
        return False, last_error

    @staticmethod
    def _classify_download_error(e):
        error_str = str(e).lower()
        error_type = type(e).__name__

        if "timeout" in error_str or "timed out" in error_str:
            return "下载超时，请检查网络连接后重试"
        elif "connection" in error_str or "connectionrefused" in error_str:
            return "无法连接到下载服务器，请检查网络"
        elif "ssl" in error_str or "certificate" in error_str:
            return "SSL 证书验证失败，可能是公司网络代理导致，请检查网络环境"
        elif "quota" in error_str or "rate limit" in error_str:
            return "下载频率超限，请稍后重试"
        elif "disk" in error_str or "no space" in error_str:
            return "磁盘空间不足，请清理后重试"
        elif "permission" in error_str or "access denied" in error_str:
            return "没有写入权限，请以管理员身份运行"
        elif error_type == "FileDownloadError":
            return f"文件下载失败: {e}"
        else:
            return f"下载失败: {e}"

    def download_all_missing(self, progress_callback=None):
        """下载所有缺失的必需模型"""
        missing = self.get_missing_models(required_only=True)
        if not missing:
            return True, "所有必需模型已就绪"

        results = []
        for model_id in missing:
            success, msg = self.download_model(model_id, progress_callback)
            results.append((model_id, success, msg))

        failed = [(m, msg) for m, s, msg in results if not s]
        if failed:
            return False, "部分模型下载失败: " + "; ".join(f"{m}: {msg}" for m, msg in failed)
        return True, "所有模型下载完成"

    def _save_status(self, status_data):
        """保存模型状态到文件"""
        try:
            os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
            save_data = {
                "last_check": datetime.now().isoformat(),
                "cache_dir": self.cache_dir,
                "models": {}
            }
            for model_id, state in status_data.items():
                save_data["models"][model_id] = {
                    "cached": state["cached"],
                    "path": state["path"],
                    "description": state["info"]["description"],
                    "required": state["info"]["required"],
                }
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save model status: {e}")

    def load_status(self):
        """加载上次保存的状态"""
        if not os.path.exists(self.status_file):
            return None
        try:
            with open(self.status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


def _patch_funasr_campplus():
    """
    Monkey-patch FunASR campplus utils to handle None timestamps gracefully.
    SenseVoice + punc_model + spk_model can produce sentence_info with
    None start/end, causing TypeError in distribute_spk.
    """
    try:
        from funasr.models.campplus import utils as campplus_utils
        _orig_distribute_spk = campplus_utils.distribute_spk

        def _safe_distribute_spk(sentence_list, sd_time_list):
            # Filter out sentences with missing timestamps to avoid TypeError
            valid_sentences = []
            for d in sentence_list:
                if d.get("start") is None or d.get("end") is None:
                    d["spk"] = 0
                else:
                    valid_sentences.append(d)
            if valid_sentences:
                _orig_distribute_spk(valid_sentences, sd_time_list)
            return sentence_list

        campplus_utils.distribute_spk = _safe_distribute_spk
        logger.debug("Patched funasr.models.campplus.utils.distribute_spk")
    except Exception as e:
        logger.warning(f"Failed to patch campplus utils: {e}")


def _ensure_ffmpeg_in_path():
    """确保 FFmpeg 的 bin 目录在 PATH 中（torchcodec 需要）"""
    candidates = [
        # WinGet 安装路径
        os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
            r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
            r"\ffmpeg-8.1.1-full_build\bin"
        ),
        # 常见手动安装路径
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
    ]
    for d in candidates:
        if os.path.isdir(d) and d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            logger.debug(f"Added {d} to PATH for FFmpeg")
            return d
    return None


# 模块加载时就确保 FFmpeg 在 PATH 中
_ensure_ffmpeg_in_path()


def _safe_model_path(model_path):
    """处理路径中含非 ASCII 字符导致 sentencepiece 崩溃的问题

    sentencepiece C++ 层在 Windows 上无法处理中文路径，
    如果路径包含非 ASCII 字符，将整个模型目录复制到临时 ASCII 路径。
    """
    if not model_path or not os.path.isdir(model_path):
        return model_path

    # 检查路径是否纯 ASCII
    try:
        model_path.encode('ascii')
        return model_path  # 纯 ASCII 路径，无需处理
    except UnicodeEncodeError:
        pass

    # 路径含非 ASCII 字符，复制到临时目录
    import shutil
    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="ms_model_")
    dest = os.path.join(tmp_dir, os.path.basename(model_path))
    logger.info(f"Non-ASCII path detected, copying model to: {dest}")
    shutil.copytree(model_path, dest, dirs_exist_ok=True)
    _temp_model_dirs.append(tmp_dir)
    return dest


def _cleanup_temp_model_dirs():
    """清理 _safe_model_path 创建的临时目录"""
    for d in _temp_model_dirs:
        try:
            if os.path.exists(d):
                shutil.rmtree(d)
        except Exception as e:
            logger.warning(f"Failed to clean temp model dir {d}: {e}")
    _temp_model_dirs.clear()


class Transcriber:
    """MeetScribe 核心转写引擎"""

    def __init__(self, model_cache_dir=None, device="cpu"):
        self.model = None
        self.device = device
        self.model_cache_dir = model_cache_dir
        self.model_manager = ModelManager(model_cache_dir) if model_cache_dir else None
        self._loaded = False
        self._spk_disabled = False
        self.spk_embeddings = {}  # {spk_id: embedding_vector} 转写后存储说话人嵌入向量
        self.sentences = []  # 转写句子列表，供外部读取

        # 尽早设置 MODELSCOPE_CACHE（必须在 FunASR import 之前）
        if model_cache_dir:
            _setup_modelscope_cache(model_cache_dir)

    def check_models_ready(self):
        """
        检查转写所需模型是否就绪

        Returns:
            (ready: bool, missing: list[str])
        """
        if not self.model_manager:
            return False, ["未配置模型缓存目录"]

        missing = self.model_manager.get_missing_models(required_only=True)
        return len(missing) == 0, missing

    def load_model(self, progress_callback=None, disable_spk=False):
        """加载 SenseVoice + CAM++ + fsmn-vad 模型（必须已缓存）"""
        if self._loaded and not disable_spk:
            return
        if self._loaded and disable_spk and self._spk_disabled:
            return

        # 检查必需模型是否已缓存
        ready, missing = self.check_models_ready()
        if not ready:
            raise RuntimeError(
                f"缺少必需模型，请先在设置页下载:\n" +
                "\n".join(f"  - {m}" for m in missing)
            )

        if progress_callback:
            progress_callback("正在加载模型（ASR + VAD + 说话人分离 + 标点恢复）...")

        _patch_funasr_campplus()
        from funasr import AutoModel

        # 使用本地缓存路径（已确认存在）
        sensevoice_path = _resolve_model_path("SenseVoiceSmall", self.model_cache_dir)
        vad_path = _resolve_model_path("fsmn-vad", self.model_cache_dir)

        # 处理非 ASCII 路径（sentencepiece C++ 不支持中文路径）
        sensevoice_path = _safe_model_path(sensevoice_path)

        kwargs = {
            "model": sensevoice_path,
            "vad_model": vad_path,
            "device": self.device,
            "disable_update": True,
        }

        if not disable_spk:
            # cam++ 必须用别名（FunASR 类名注册机制要求）
            # 注意：不在这里加载 punc_model，它会干扰 CAM++ 的说话人分离
            # ct-punc 在转写完成后作为后处理步骤单独加载
            kwargs["spk_model"] = "cam++"
            self._spk_disabled = False
        else:
            self._spk_disabled = True
            logger.warning("Speaker diarization disabled (fallback mode)")

        logger.info("Loading models...")
        logger.info(f"  model:      {sensevoice_path}")
        logger.info(f"  vad_model:  {vad_path}")
        if not disable_spk:
            logger.info(f"  spk_model:  cam++ (alias)")
            logger.info(f"  punc_model: (post-processing, loaded separately)")

        try:
            self.model = AutoModel(**kwargs)
        except Exception as e:
            raise

        self._loaded = True
        logger.info("Models loaded successfully")

        if progress_callback:
            progress_callback("模型加载完成")

    def _reload_without_spk(self, progress_callback=None):
        """降级加载：去掉说话人分离模型（用于兼容性问题回退）"""
        logger.warning("Reloading models without speaker diarization due to compatibility issue")
        self._loaded = False
        self.model = None
        self.load_model(progress_callback=progress_callback, disable_spk=True)

    @property
    def is_loaded(self):
        return self._loaded

    def transcribe_staged(self, audio_path, output_format="llm-md",
                          speaker_names=None, progress_callback=None):
        """
        分步转写音频文件（3阶段加载，降低峰值内存）

        Stage 1: SenseVoice + VAD → 文本转写中
        Stage 2: cam++            → 识别说话人信息中
        Stage 3: ct-punc          → 追加标点符号中

        每个阶段结束后释放模型，控制峰值内存。
        """
        import gc

        def _cb(msg):
            if progress_callback:
                progress_callback(msg)

        # 检查必需模型
        ready, missing = self.check_models_ready()
        if not ready:
            raise RuntimeError(
                f"缺少必需模型:\n" +
                "\n".join(f"  - {m}" for m in missing)
            )

        _cb("正在准备音频...")
        audio_for_asr = self._ensure_wav(audio_path, progress_callback)

        _patch_funasr_campplus()
        from funasr import AutoModel

        sensevoice_path = _resolve_model_path("SenseVoiceSmall", self.model_cache_dir)
        vad_path = _resolve_model_path("fsmn-vad", self.model_cache_dir)

        # 处理非 ASCII 路径（sentencepiece C++ 不支持中文路径）
        sensevoice_path = _safe_model_path(sensevoice_path)

        start_time = time.time()
        sentences = []
        self.spk_embeddings = {}  # 重置嵌入向量

        try:
            # ── Stage 1: ASR ─────────────────────────────────
            _cb("文本转写中...")
            logger.info("[Stage 1] Loading SenseVoice + VAD...")
            model_asr = AutoModel(
                model=sensevoice_path,
                vad_model=vad_path,
                device=self.device,
                disable_update=True,
            )
            logger.info("[Stage 1] Running ASR...")
            res = model_asr.generate(
                input=audio_for_asr,
                batch_size_s=300,
                language="zh",
            )
            sentences = self._extract_sentences(res)
            del model_asr
            gc.collect()
            logger.info(f"[Stage 1] ASR done: {len(sentences)} sentences")

            if not sentences:
                return "[empty] 未识别到语音内容"

            # ── Stage 2: Speaker Embedding Extraction ─────────────────
            _cb("提取说话人声纹中...")
            logger.info("[Stage 2] Loading cam++ for per-speaker embedding extraction...")
            try:
                # 使用新的按说话人分段提取方法
                self.spk_embeddings = self._extract_per_speaker_embeddings(audio_for_asr, sentences)
                if self.spk_embeddings:
                    logger.info(f"[Stage 2] Extracted embeddings for {len(self.spk_embeddings)} speakers")
                else:
                    logger.info("[Stage 2] No speaker embeddings extracted")
            except Exception as e:
                logger.warning(f"[Stage 2] Speaker embedding extraction failed: {e}", exc_info=True)
                _cb(f"声纹提取失败（已跳过）: {e}")

            # ── Stage 3: Punctuation ─────────────────────────
            # 逐句加载 ct-punc 加标点（不重跑音频，不影响说话人标签）
            logger.info("[Stage 3] Applying punctuation post-processing...")
            sentences = self._punctuate_sentences(sentences, _cb)
            logger.info(f"[Stage 3] Punctuation done")

            # ── Stage 4: Post-processing ─────────────────────
            sentences = self._postprocess_sentences(sentences)
            logger.info(f"[Stage 4] Post-processing done: {len(sentences)} sentences")

        finally:
            _cleanup_temp_model_dirs()
            if audio_for_asr != audio_path and os.path.exists(audio_for_asr):
                try:
                    os.remove(audio_for_asr)
                except OSError:
                    pass

        elapsed = time.time() - start_time
        logger.info(f"Staged transcription completed in {elapsed:.1f}s")
        _cb(f"转写完成，耗时 {elapsed:.1f} 秒")

        self.sentences = sentences  # 保存句子数据供外部读取
        return self._format(sentences, output_format, speaker_names or {},
                            os.path.basename(audio_path), elapsed)

    def transcribe(self, audio_path, output_format="llm-md",
                   speaker_names=None, progress_callback=None):
        """
        转写音频文件（一次性加载所有模型）

        Args:
            audio_path:     音频文件路径
            output_format:  输出格式 llm-md / md / txt / srt / json
            speaker_names:  说话人名称映射 {"0": "张三", "1": "李四"}
            progress_callback: 进度回调 callable(str)

        Returns:
            str: 格式化的转写结果
        """
        if not self._loaded:
            self.load_model(progress_callback)

        if progress_callback:
            progress_callback(f"正在转写: {os.path.basename(audio_path)}（文本识别 + 说话人分离）")

        # 非 WAV 格式需要先转换为 16kHz 单声道 WAV
        audio_for_asr = self._ensure_wav(audio_path, progress_callback)

        start_time = time.time()
        sentences = []  # 初始化，确保在 except 块中也可用

        try:
            res = self.model.generate(
                input=audio_for_asr,
                batch_size_s=300,
                language="zh",
            )

            # 提取句子信息
            sentences = self._extract_sentences(res)

            # 提取说话人嵌入向量（供音色库匹配使用）
            # 使用新的按说话人分段提取方法（需要在临时文件删除前执行）
            self.spk_embeddings = self._extract_per_speaker_embeddings(audio_for_asr, sentences)
            if self.spk_embeddings:
                logger.info(f"Extracted embeddings for {len(self.spk_embeddings)} speakers")

        except Exception as e:
            error_msg = str(e).lower()
            # 当 spk_model + punc_model 组合出现内部兼容性错误时，自动降级到纯 ASR
            is_spk_error = (
                "'>' not supported between instances of 'float' and 'NoneType'" in str(e)
                or "missing punc_model" in error_msg
                or "speaker diarization relies on timestamps" in error_msg
                or "distribute_spk" in error_msg
                or "not registered" in error_msg
                or "punc" in error_msg
            )
            if is_spk_error and not getattr(self, "_spk_disabled", False):
                logger.warning(f"Speaker diarization failed ({e}), falling back to ASR-only mode")
                if progress_callback:
                    progress_callback("说话人分离出错，降级为纯转写模式...")
                self._reload_without_spk(progress_callback)
                res = self.model.generate(
                    input=audio_for_asr,
                    batch_size_s=300,
                    language="zh",
                )
                sentences = self._extract_sentences(res)
                self.spk_embeddings = self._extract_per_speaker_embeddings(audio_for_asr, sentences)
                if self.spk_embeddings:
                    logger.info(f"Extracted embeddings for {len(self.spk_embeddings)} speakers")
            else:
                logger.error(f"Transcription failed: {e}")
                raise
        finally:
            _cleanup_temp_model_dirs()
            # 清理临时文件
            if audio_for_asr != audio_path and os.path.exists(audio_for_asr):
                try:
                    os.remove(audio_for_asr)
                except OSError:
                    pass

        elapsed = time.time() - start_time
        logger.info(f"Transcription completed in {elapsed:.1f}s")

        if progress_callback:
            progress_callback(f"转写完成，耗时 {elapsed:.1f} 秒")

        if not sentences:
            return "[empty] 未识别到语音内容"

        # 后处理：逐句加标点（不影响说话人标签）
        sentences = self._punctuate_sentences(sentences, progress_callback)

        # 后处理：过滤 unk、清理标点、合并碎片
        sentences = self._postprocess_sentences(sentences)

        self.sentences = sentences  # 保存句子数据供外部读取
        return self._format(sentences, output_format, speaker_names or {},
                            os.path.basename(audio_path), elapsed)

    # ── 内部方法 ──────────────────────────────────────────

    # 需要 FFmpeg 预转换的格式扩展名
    _NEED_CONVERT = {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".aac", ".wma", ".flac"}

    # SenseVoice 输出的特殊标签正则
    _SPECIAL_TOKEN_RE = re.compile(r"<\|[^|]*\|>")

    # 日文假名过滤（多语言解码误识别）
    _JAPANESE_RE = re.compile(
        r'[\u3040-\u309F'   # 平假名
        r'\u30A0-\u30FF'    # 片假名
        r'\u31F0-\u31FF'    # 片假名扩展
        r']+'
    )
    # 异常英文 token（如中文语气词被误识别为 yes）
    _ANOMALY_EN_RE = re.compile(r'(?<![a-zA-Z])[yY][eE][sS](?![a-zA-Z])')
    # 纯标点/空白检测（清洗后如果只剩标点和空白则视为无效）
    _PUNCT_ONLY_RE = re.compile(
        r'^[\s\u3000\uff0c\u3001\u3002\uff01\uff1f\uff1b\uff1a'
        r'\u2018\u2019\u201c\u201d\u300a\u300b\u3010\u3011\uff08\uff09'
        r',.!?;:\'\"()\[\]{}\-—…·\u2026\u00b7]+$'
    )

    @classmethod
    def _clean_text(cls, text):
        """清除 SenseVoice 的特殊标签 token + 日文乱码 + 异常 token + 纯标点"""
        if not text:
            return ""
        text = cls._SPECIAL_TOKEN_RE.sub("", text)
        text = cls._JAPANESE_RE.sub("", text)
        text = cls._ANOMALY_EN_RE.sub("", text)
        text = text.strip()
        # 如果清洗后只剩标点符号和空白，视为无效内容
        if text and cls._PUNCT_ONLY_RE.match(text):
            return ""
        return text

    def _punctuate_sentences(self, sentences, progress_callback=None):
        """
        后处理步骤：用 ct-punc 对每个句子的文本单独加标点。

        逐句处理保证只修改 text 字段，不触碰 spk/start/end。
        格式化函数分开使用这些字段，说话人标签不会被标点污染。
        """
        if not sentences:
            return sentences

        # 筛选需要加标点的句子（没有句号/问号结尾的）
        needs_punc = [
            i for i, s in enumerate(sentences)
            if s.get("text") and not s["text"].rstrip()[-1] in "。？！…!?；;"
        ]
        if not needs_punc:
            return sentences

        punc_path = _resolve_model_path("ct-punc", self.model_cache_dir)
        if not punc_path:
            logger.warning("ct-punc model not cached, skipping punctuation")
            return sentences

        try:
            if progress_callback:
                progress_callback("加载标点恢复模型...")

            from funasr import AutoModel
            punc_model = AutoModel(
                model=punc_path,
                device=self.device,
                disable_update=True,
            )

            if progress_callback:
                progress_callback(f"标点恢复中（{len(needs_punc)} 句）...")

            for idx in needs_punc:
                text = sentences[idx]["text"]
                try:
                    res = punc_model.generate(input=text)
                    if res and isinstance(res, list) and len(res) > 0:
                        punctuated = res[0].get("text", "")
                        if punctuated and len(punctuated) >= len(text) * 0.5:
                            sentences[idx]["text"] = punctuated
                except Exception as e:
                    logger.debug(f"Punctuation failed for sentence: {e}")

            del punc_model
            import gc
            gc.collect()
            logger.info(f"Punctuation applied to {len(needs_punc)} sentences")

        except Exception as e:
            logger.warning(f"ct-punc post-processing failed: {e}")
            if progress_callback:
                progress_callback(f"标点恢复失败（已跳过）: {e}")

        return sentences

    def _postprocess_sentences(self, sentences):
        """后处理：过滤 <unk> 标记、清理连续标点、合并碎片化短句"""
        processed = []
        for s in sentences:
            text = s.get("text", "")

            # 1. 过滤 <unk> 标记
            text = text.replace("<unk>", "")

            # 2. 清理连续标点（中文）
            text = re.sub(r'[，。？！、；：]{2,}', '，', text)
            # 清理连续标点（英文）
            text = re.sub(r'[,\.?!;:]{2,}', ',', text)

            # 3. 清理首尾多余标点
            text = text.strip('，。？！、,.? ')

            # 4. 跳过空句或过短的句子（少于 2 个字符）
            if len(text) < 2:
                continue

            s["text"] = text
            processed.append(s)

        # 5. 合并碎片化短句：将连续同一说话人的极短句（<=2 字）合并到前一句
        merged = []
        for s in processed:
            text = s["text"]
            if (merged
                    and len(text) <= 2
                    and s.get("spk", -1) == merged[-1].get("spk", -1)
                    and s.get("start", 0) - merged[-1].get("end", 0) < 3000):
                merged[-1]["text"] += text
                merged[-1]["end"] = s.get("end", merged[-1]["end"])
            else:
                merged.append(s)

        return merged

    def _ensure_wav(self, audio_path, progress_callback=None):
        """
        确保音频格式可被 FunASR 处理。

        优化：FunASR 内部使用 FFmpeg 解码音频，支持 MP3/M4A/FLAC/OGG 等格式直接输入。
        只有 WAV 文件格式不对时才需要重采样。

        关于音质：格式转换不会增加音质，但也不会明显损失——
        真正的音质损失来自原始的有损压缩（如 MP3 的编码），而非格式转换。
        """
        ext = os.path.splitext(audio_path)[1].lower()

        # WAV 文件：检查是否已经是 16kHz 单声道
        if ext == ".wav":
            if self._check_wav_format(audio_path):
                return audio_path
            # WAV 但格式不对（如 44.1kHz 立体声），需要重采样
            if progress_callback:
                progress_callback("WAV 重采样中: 转为 16kHz 单声道 ...")
            return self._convert_to_wav(audio_path, progress_callback)

        # 非 WAV 格式：直接传给 FunASR，不需要手动转换
        # FunASR 内部使用 FFmpeg 解码，支持 MP3/M4A/FLAC/OGG 等格式
        if progress_callback:
            progress_callback(f"使用 FunASR 直接处理: {ext}")
        return audio_path

    def _check_wav_format(self, wav_path):
        """检查 WAV 文件是否已经是 16kHz 单声道"""
        try:
            import wave
            with wave.open(wav_path, "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                return channels == 1 and sample_rate == 16000
        except Exception:
            return False

    def _convert_to_wav(self, audio_path, progress_callback=None):
        """通过 FFmpeg 转换为 16kHz 单声道 WAV"""
        tmp_dir = tempfile.gettempdir()
        with tempfile.NamedTemporaryFile(suffix='.wav', dir=tmp_dir, delete=False) as f:
            tmp_wav = f.name

        try:
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-ar", "16000", "-ac", "1",
                "-acodec", "pcm_s16le",
                tmp_wav,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg conversion failed: {result.stderr[:200]}")

            logger.info(f"Audio converted to 16kHz WAV: {tmp_wav}")
            if progress_callback:
                progress_callback("格式转换完成")
            return tmp_wav
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg 未找到。请安装 FFmpeg 并确保其在系统 PATH 中。\n"
                "安装命令: winget install Gyan.FFmpeg"
            )

    def _extract_sentences(self, res):
        """从 FunASR 结果中提取标准化的句子列表"""
        sentences = []

        if not res or not isinstance(res, list):
            return sentences

        result = res[0] if isinstance(res[0], dict) else {}

        # 优先取 sentence_info（SenseVoice + VAD 分段后的结果）
        raw = result.get("sentence_info", [])
        if not raw:
            # 降级：取整段文本
            text = self._clean_text(result.get("text", ""))
            if text:
                sentences.append({
                    "text": text,
                    "start": 0,
                    "end": 0,
                    "spk": -1,
                    "timestamp": [],
                })
            return sentences

        for s in raw:
            # FunASR 1.x 中 sentence_info 的文本键名是 "sentence"
            raw_text = s.get("sentence", "") or s.get("text", "")
            text = self._clean_text(raw_text)
            if not text:
                continue  # 跳过空文本段落
            start = s.get("start", 0)
            end = s.get("end", 0)
            # 处理 SenseVoice + punc_model 组合中可能出现的 None 时间戳
            if start is None:
                start = 0
            if end is None:
                end = start
            sentences.append({
                "text": text,
                "start": start,
                "end": end,
                "spk": s.get("spk", -1),
                "timestamp": s.get("timestamp", []),
            })

        return sentences

    def _extract_spk_embeddings(self, res):
        """
        从 FunASR 结果中提取说话人嵌入向量。

        FunASR CAM++ 模型的输出格式可能有多种：
        - res[0]["spk_emb"]: 全局说话人嵌入（单个向量）
        - res[0]["sentence_info"][i]["spk_emb"]: 逐句嵌入
        - res[0]["spk_embeddings"]: dict 形式 {spk_id: vector}

        Returns:
            dict: {spk_id: embedding_vector}，spk_id 为 int，vector 为 list
        """
        embeddings = {}
        if not res or not isinstance(res, list):
            logger.debug("[SPK-EMB] No result or not list")
            return embeddings

        result = res[0] if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict) else {}
        if not result:
            logger.debug("[SPK-EMB] Empty result dict")
            return embeddings

        # 格式 1: spk_embeddings dict（已有聚合结果）
        spk_emb_dict = result.get("spk_embeddings")
        if isinstance(spk_emb_dict, dict):
            for spk_id, emb in spk_emb_dict.items():
                embeddings[int(spk_id)] = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            logger.debug(f"[SPK-EMB] Format 1 (spk_embeddings dict): {len(embeddings)} speakers")
            return embeddings

        # 格式 2: sentence_info 中的逐句嵌入
        sentences = result.get("sentence_info", [])
        spk_emb_accum = {}  # spk_id -> [vector, ...]
        for s in sentences:
            spk = s.get("spk", -1)
            if spk < 0:
                continue
            emb = s.get("spk_emb")
            if emb is None:
                continue
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            elif not isinstance(emb, list):
                continue
            if spk not in spk_emb_accum:
                spk_emb_accum[spk] = []
            spk_emb_accum[spk].append(emb)

        # 对每个说话人的多个嵌入取平均
        import numpy as np
        for spk_id, vecs in spk_emb_accum.items():
            if vecs:
                avg = np.mean(vecs, axis=0)
                embeddings[spk_id] = avg.tolist()

        if embeddings:
            logger.debug(f"[SPK-EMB] Format 2 (sentence_info): {len(embeddings)} speakers, "
                        f"{sum(len(v) for v in spk_emb_accum.values())} embeddings total")
            return embeddings

        # 格式 3: 全局 spk_emb（单个向量，标记为 spk_id=0）
        global_emb = result.get("spk_emb")
        if global_emb is not None:
            if hasattr(global_emb, "tolist"):
                global_emb = global_emb.tolist()
            if isinstance(global_emb, list):
                embeddings[0] = global_emb
                logger.debug("[SPK-EMB] Format 3 (global spk_emb): 1 speaker")

        if not embeddings:
            logger.debug("[SPK-EMB] No embeddings found in any format")

        return embeddings

    def _extract_per_speaker_embeddings(self, audio_path, sentences):
        """
        按说话人分段提取嵌入向量。

        思路：对每个说话人的每个片段分别提取嵌入向量，然后取平均。
        这样可以避免聚合片段过长导致包含其他说话人音频的问题。

        Args:
            audio_path: 音频文件路径（WAV 格式，16kHz）
            sentences: 句子列表，每个含 start, end, spk 等字段

        Returns:
            dict: {spk_id: embedding_vector}，spk_id 为 int，vector 为 list
        """
        import soundfile as sf
        import numpy as np

        embeddings = {}

        if not sentences:
            logger.debug("[SPK-EMB-PER] No sentences provided")
            return embeddings

        # 1. 按 spk_id 聚合时间段
        spk_segments = {}  # {spk_id: [(start_ms, end_ms), ...]}
        for s in sentences:
            spk = s.get("spk", -1)
            if spk < 0:
                continue
            if spk not in spk_segments:
                spk_segments[spk] = []
            spk_segments[spk].append((s["start"], s["end"]))

        if not spk_segments:
            logger.debug("[SPK-EMB-PER] No valid speaker segments found")
            return embeddings

        logger.debug(f"[SPK-EMB-PER] Found {len(spk_segments)} speakers: {list(spk_segments.keys())}")

        # 2. 加载 CAM++ 模型（使用本地路径，避免每次触发 ModelScope 下载）
        try:
            _patch_funasr_campplus()
            from funasr import AutoModel
            campp_path = _resolve_model_path("cam++", self.model_cache_dir)
            if campp_path:
                model_spk = AutoModel(model=campp_path, device=self.device, disable_update=True)
            else:
                model_spk = AutoModel(model="cam++", device=self.device, disable_update=True)
        except Exception as e:
            logger.error(f"[SPK-EMB-PER] Failed to load CAM++ model: {e}")
            return embeddings

        # 3. 读取原始音频
        try:
            audio_data, sample_rate = sf.read(audio_path)
            logger.debug(f"[SPK-EMB-PER] Audio loaded: {len(audio_data)} samples, {sample_rate}Hz")
        except Exception as e:
            logger.error(f"[SPK-EMB-PER] Failed to read audio: {e}")
            del model_spk
            return embeddings

        # 4. 对每个说话人的每个片段提取嵌入，然后取平均
        for spk_id, segments in spk_segments.items():
            try:
                spk_embeddings = []  # 存储该说话人的多个嵌入

                for start_ms, end_ms in segments:
                    # 前后各扩展 100ms 缓冲区（减少边界噪声）
                    buffer_ms = 100  # ms
                    start_ms_buffered = max(0, start_ms - buffer_ms)
                    end_ms_buffered = min(len(audio_data) / sample_rate * 1000, end_ms + buffer_ms)

                    # 截取音频
                    start_sample = int(start_ms_buffered / 1000 * sample_rate)
                    end_sample = int(end_ms_buffered / 1000 * sample_rate)
                    segment_audio = audio_data[start_sample:end_sample]

                    # 确保是 float32 单声道
                    if len(segment_audio.shape) > 1:
                        segment_audio = segment_audio.mean(axis=1)
                    segment_audio = segment_audio.astype(np.float32)

                    # 检查音频片段长度（至少 0.5 秒）
                    min_length = int(0.5 * sample_rate)
                    if len(segment_audio) < min_length:
                        continue

                    # 提取嵌入
                    result = model_spk.inference(input=segment_audio)
                    if result and len(result) > 0:
                        spk_emb = result[0].get("spk_embedding")
                        if spk_emb is None:
                            spk_emb = result[0].get("spk_emb")
                        if spk_emb is not None:
                            # 转换为 numpy array
                            if hasattr(spk_emb, "cpu"):
                                spk_emb = spk_emb.cpu().numpy()
                            elif hasattr(spk_emb, "tolist"):
                                spk_emb = np.array(spk_emb)
                            if isinstance(spk_emb, list):
                                spk_emb = np.array(spk_emb)
                            logger.debug(f"[SPK-EMB] Before squeeze: type={type(spk_emb)}, shape={getattr(spk_emb, 'shape', 'N/A')}")
                            # 关键修复：用 squeeze 去掉所有 size=1 的维度
                            spk_emb = np.squeeze(spk_emb)
                            logger.debug(f"[SPK-EMB] After squeeze: shape={spk_emb.shape}, ndim={spk_emb.ndim}")
                            # 校验最终维度（CAM++ 应为 192）
                            if spk_emb.ndim != 1:
                                logger.warning(f"[SPK-EMB] Unexpected dim after squeeze: {spk_emb.shape}, skipping")
                                continue
                            spk_embeddings.append(spk_emb)

                # 对该说话人的多个嵌入取平均
                if spk_embeddings:
                    avg_embedding = np.mean(spk_embeddings, axis=0)
                    seg_count = len(segments)
                    total_dur = sum((e - s) / 1000.0 for s, e in segments)
                    quality = _compute_quality(seg_count, total_dur)
                    embeddings[spk_id] = (avg_embedding.tolist(), quality)
                    logger.debug(f"[SPK-EMB-PER] Speaker {spk_id}: extracted {len(spk_embeddings)} embeddings, averaged (dim={len(avg_embedding)})")
                else:
                    logger.debug(f"[SPK-EMB-PER] Speaker {spk_id}: no valid embeddings extracted")

            except Exception as e:
                logger.warning(f"[SPK-EMB-PER] Speaker {spk_id}: extraction failed: {e}")

        # 释放模型
        del model_spk
        import gc
        gc.collect()

        logger.info(f"[SPK-EMB-PER] Total extracted: {len(embeddings)} speakers")
        return embeddings

    def _spk_color(self, spk_id):
        """获取说话人颜色"""
        if spk_id < 0:
            return "#616161"
        return SPEAKER_COLORS[spk_id % len(SPEAKER_COLORS)]

    @staticmethod
    def _merge_consecutive(sentences, gap_ms=3000):
        """
        按时间顺序合并同一说话人的连续发言。

        Parameters
        ----------
        sentences : list[dict]
            原始句子列表，每个含 start, end, spk, text
        gap_ms : int
            超过此时间间隔（毫秒）视为不连续，默认 3 秒

        Returns
        -------
        list[dict]
            合并后的段落列表，每个含 spk, start, end, texts(list)
        """
        if not sentences:
            return []

        # 按时间排序
        ordered = sorted(sentences, key=lambda s: s["start"])
        paragraphs = []
        current = {
            "spk": ordered[0]["spk"],
            "start": ordered[0]["start"],
            "end": ordered[0]["end"],
            "texts": [ordered[0]["text"]],
        }

        for s in ordered[1:]:
            same_spk = s["spk"] == current["spk"]
            gap_ok = (s["start"] - current["end"]) <= gap_ms
            if same_spk and gap_ok:
                current["texts"].append(s["text"])
                current["end"] = s["end"]
            else:
                paragraphs.append(current)
                current = {
                    "spk": s["spk"],
                    "start": s["start"],
                    "end": s["end"],
                    "texts": [s["text"]],
                }
        paragraphs.append(current)
        return paragraphs

    def _adapt_segments_for_formatter(self, sentences):
        """将转写器内部格式转换为 TranscriptFormatter 兼容格式

        转写器内部用 ``spk`` 键表示说话人 ID，TranscriptFormatter 用 ``speaker``。
        """
        return [
            {
                "text": s["text"],
                "start": s["start"],
                "end": s["end"],
                "speaker": s.get("spk", -1),
            }
            for s in sentences
        ]

    def _speaker_names_to_list(self, speaker_names, sentences):
        """将说话人名称字典转换为 TranscriptFormatter 所需的列表格式

        输入: ``{"0": "张三", "1": "李四"}``
        输出: ``["张三", "李四"]``（按 spk_id 索引，缺失则用默认名）
        """
        spk_ids = {s.get("spk", -1) for s in sentences if s.get("spk", -1) >= 0}
        if not spk_ids:
            return []
        max_spk = max(spk_ids)
        return [
            speaker_names.get(str(i), "") or f"Speaker {i + 1}"
            for i in range(max_spk + 1)
        ]

    def _format(self, sentences, fmt, speaker_names, filename, elapsed):
        """分发到具体格式化器

        srt / csv / vtt 委托给 TranscriptFormatter；其余保留自定义格式化器。
        """
        # ── 委托给 TranscriptFormatter ──
        if fmt in ("srt", "csv", "vtt"):
            segments = self._adapt_segments_for_formatter(sentences)
            if fmt == "srt":
                # SRT 不附带说话人标签（与旧行为一致）
                return TranscriptFormatter.format_srt(segments)
            speakers = self._speaker_names_to_list(speaker_names, sentences)
            if fmt == "csv":
                return TranscriptFormatter.format_csv(segments, speakers)
            return TranscriptFormatter.format_vtt(segments, speakers)

        # ── 自定义格式化器 ──
        formatters = {
            "llm-md": self._fmt_llm_md,
            "md":       self._fmt_md,
            "txt":      self._fmt_txt,
            "json":     self._fmt_json,
            "html":     self._fmt_html,
        }
        fn = formatters.get(fmt, self._fmt_llm_md)
        return fn(sentences, speaker_names, filename, elapsed)

    def _spk_label(self, spk_id, names):
        """获取说话人显示名称"""
        key = str(spk_id)
        if key in names and names[key]:
            return names[key]
        return f"Speaker {spk_id + 1}" if spk_id >= 0 else "Unknown"

    @staticmethod
    def _ms_to_time(ms):
        """毫秒 → HH:MM:SS"""
        total = max(0, ms) // 1000
        h, m, s = total // 3600, (total % 3600) // 60, total % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    # ── 格式化器 ──────────────────────────────────────────

    def _fmt_llm_md(self, sentences, names, filename, elapsed):
        """LLM 友好的 Markdown"""
        lines = [
            f"# Meeting Transcription",
            f"",
            f"- **File**: {filename}",
            f"- **Duration**: {self._ms_to_time(sentences[-1]['end']) if sentences else 'N/A'}",
            f"- **Transcribed**: {elapsed:.1f}s",
            "",
            "---",
            "",
        ]
        for s in sentences:
            label = self._spk_label(s["spk"], names)
            t = self._ms_to_time(s["start"])
            lines.append(f"[{t}] **{label}**: {s['text']}")
            lines.append("")
        return "\n".join(lines)

    def _fmt_md(self, sentences, names, filename, elapsed):
        """人类可读 Markdown（按时间线 + 连续发言合并）"""
        lines = [
            f"# Meeting Transcription - {filename}",
            f"",
            f"> 转写耗时: {elapsed:.1f}s  |  说话人: {len({s['spk'] for s in sentences if s['spk'] >= 0})} 位",
            "",
            "---",
            "",
        ]
        paragraphs = self._merge_consecutive(sentences, gap_ms=3000)
        for p in paragraphs:
            label = self._spk_label(p["spk"], names)
            t = self._ms_to_time(p["start"])
            text = " ".join(p["texts"])
            lines.append(f"**[{t}] {label}**  ")
            lines.append(f"{text}")
            lines.append("")
        return "\n".join(lines)

    def _fmt_txt(self, sentences, names, _fn, _el):
        """纯文本"""
        out = []
        for s in sentences:
            label = self._spk_label(s["spk"], names)
            t = self._ms_to_time(s["start"])
            out.append(f"[{t}] {label}: {s['text']}")
        return "\n".join(out)

    def _fmt_json(self, sentences, names, filename, elapsed):
        """结构化 JSON"""
        total_end = sentences[-1]["end"] if sentences else 0
        spk_ids = sorted(s for s in set(s["spk"] for s in sentences) if s >= 0)
        data = {
            "file": filename,
            "duration_ms": total_end,
            "duration": self._ms_to_time(total_end),
            "transcription_time_s": round(elapsed, 1),
            "speaker_count": len(spk_ids),
        }
        data["segments"] = [
            {
                "start_ms": s["start"],
                "end_ms": s["end"],
                "start": self._ms_to_time(s["start"]),
                "end": self._ms_to_time(s["end"]),
                "speaker_id": s["spk"],
                "speaker": self._spk_label(s["spk"], names),
                "text": s["text"],
            }
            for s in sentences
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _fmt_html(self, sentences, names, filename, elapsed):
        """带颜色标记的 HTML（人读版，浏览器打开即可查看）"""
        paragraphs = self._merge_consecutive(sentences, gap_ms=3000)
        body_lines = []
        for p in paragraphs:
            # 转义动态内容，防止正文中的 < > & 破坏标签结构或注入脚本。
            label = html.escape(self._spk_label(p["spk"], names))
            color = self._spk_color(p["spk"])
            t = self._ms_to_time(p["start"])
            text = html.escape(" ".join(p["texts"]))
            body_lines.append(
                f'  <div class="para">'
                f'<span class="spk" style="color:{color}">{label}</span>'
                f'<span class="time">[{t}]</span>'
                f'<span class="text">{text}</span></div>'
            )

        body = "\n".join(body_lines)
        total_speakers = len({s["spk"] for s in sentences if s["spk"] >= 0})
        filename = html.escape(filename)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MeetScribe - {filename}</title>
<style>
  body {{ font-family: "Segoe UI", system-ui, sans-serif; max-width: 800px;
         margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.7; }}
  h1 {{ font-size: 22px; margin-bottom: 6px; }}
  .meta {{ color: #616161; font-size: 13px; margin-bottom: 24px; }}
  .para {{ margin: 14px 0; padding: 12px 16px; background: #fafafa;
          border-radius: 8px; border-left: 4px solid #ddd; }}
  .spk {{ font-weight: 600; font-size: 14px; margin-right: 8px; }}
  .time {{ color: #9e9e9e; font-size: 12px; margin-right: 10px; }}
  .text {{ font-size: 15px; }}
</style>
</head>
<body>
<h1>Meeting Transcription</h1>
<div class="meta">{filename} &nbsp;|&nbsp; {len(sentences)} 句 &nbsp;|&nbsp;
{total_speakers} 位说话人 &nbsp;|&nbsp; 转写耗时 {elapsed:.1f}s</div>
{body}
</body>
</html>"""
