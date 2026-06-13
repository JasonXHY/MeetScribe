#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 统一录音模块
基于 PyAudioWPatch，支持麦克风和系统音频（WASAPI Loopback）录制
所有音频操作在一个后台线程中完成，避免与 tkinter 冲突
"""

import os
import time
import queue
import threading
import logging
import numpy as np
from datetime import datetime

logger = logging.getLogger("MeetScribe")


class UnifiedRecorder:
    """统一录音器（支持麦克风和系统音频）"""

    def __init__(self, save_dir, sample_rate=16000, channels=1, use_vb_cable=False):
        self.save_dir = save_dir
        self.target_rate = sample_rate
        self.target_channels = channels
        self._use_vb_cable = use_vb_cable

        self._recording = False
        self._paused = False
        self._mode = None

        # 音频数据队列
        self._mic_queue = queue.Queue()
        self._sys_queue = queue.Queue()

        # 文件名
        self._mic_file = None
        self._sys_file = None

        # 实际采样率（由设备决定，如 44100 / 48000）
        self._mic_rate = None
        self._sys_rate = None

        # 后台线程
        self._audio_thread = None

        # 线程安全锁（保护 _paused_duration 等复合操作）
        self._lock = threading.Lock()

        # 计时
        self._start_time = None
        self._paused_duration = 0.0
        self._pause_start = None

        self.on_state_change = None
        self.on_save = None
        self.on_stop_complete = None

        os.makedirs(save_dir, exist_ok=True)

    @property
    def is_recording(self):
        return self._recording

    @property
    def is_paused(self):
        return self._paused

    @property
    def paused_duration(self):
        """获取已暂停时长（公共接口）"""
        return self._paused_duration

    def _open_mic_stream(self, p, pyaudio):
        """打开麦克风流

        Args:
            p: PyAudio 实例
            pyaudio: pyaudiowpatch 模块引用（用于 paContinue 常量）

        Returns:
            stream: PyAudio 流对象，失败返回 None
        """
        # 直接使用 16kHz 单声道，无需格式转换
        target_rate = 16000
        target_channels = 1

        mic_dev = None
        try:
            info = p.get_default_input_device_info()
            mic_dev = {"index": info["index"], "rate": target_rate,
                       "channels": target_channels, "name": info["name"]}
        except Exception:
            # 回退遍历
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0 and "Loopback" not in info["name"]:
                    mic_dev = {"index": i, "rate": target_rate,
                               "channels": target_channels, "name": info["name"]}
                    break

        if not mic_dev:
            logger.error("Mic device not found")
            return None

        self._mic_rate = target_rate
        logger.info(f"Mic device: {mic_dev['name']} ({target_rate}Hz, {target_channels}ch)")

        def mic_cb(in_data, frame_count, time_info, status):
            if in_data and not self._paused:
                audio = np.frombuffer(in_data, dtype=np.float32)
                # 直接使用单声道数据
                self._mic_queue.put(audio.copy())
            return (None, pyaudio.paContinue)

        stream = p.open(
            format=pyaudio.paFloat32,
            channels=target_channels,
            rate=target_rate,
            input=True,
            input_device_index=mic_dev["index"],
            frames_per_buffer=4096,
            stream_callback=mic_cb,
        )
        logger.info(f"Mic stream opened: {self._mic_file}")
        return stream

    def _open_loopback_stream(self, p, pyaudio):
        """打开系统音频流（VB-Audio Cable 或 WASAPI Loopback）

        Args:
            p: PyAudio 实例
            pyaudio: pyaudiowpatch 模块引用（用于 paContinue 常量）

        Returns:
            stream: PyAudio 流对象，失败返回 None
        """
        sys_dev = None

        # 优先使用 VB-Audio Cable（避免停止录音时暂停媒体播放器）
        if self._use_vb_cable:
            vb_index = self._find_vb_cable(p)
            if vb_index is not None:
                try:
                    info = p.get_device_info_by_index(vb_index)
                    sys_dev = {"index": vb_index, "rate": int(info["defaultSampleRate"]),
                               "channels": info["maxInputChannels"], "name": info["name"]}
                    logger.info(f"Using VB-Audio Cable: {sys_dev['name']}")
                except Exception as e:
                    logger.warning(f"Failed to open VB-Audio Cable: {e}, falling back to WASAPI Loopback")
                    sys_dev = None
            else:
                logger.warning("VB-Audio Cable enabled but not found, falling back to WASAPI Loopback")

        # 回退到 WASAPI Loopback
        if sys_dev is None:
            try:
                for d in p.get_loopback_device_info_generator():
                    sys_dev = {"index": d["index"], "rate": int(d["defaultSampleRate"]),
                               "channels": d["maxInputChannels"], "name": d["name"]}
                    break
            except Exception:
                pass

        if not sys_dev:
            logger.error("Loopback device not found")
            return None

        self._sys_rate = sys_dev["rate"]
        logger.info(f"Loopback device: {sys_dev['name']} ({sys_dev['rate']}Hz, {sys_dev['channels']}ch)")

        def sys_cb(in_data, frame_count, time_info, status):
            if in_data and not self._paused:
                audio = np.frombuffer(in_data, dtype=np.float32)
                if sys_dev["channels"] > 1:
                    audio = audio.reshape(-1, sys_dev["channels"])
                self._sys_queue.put(audio.copy())
            return (None, pyaudio.paContinue)

        stream = p.open(
            format=pyaudio.paFloat32,
            channels=sys_dev["channels"],
            rate=sys_dev["rate"],
            input=True,
            input_device_index=sys_dev["index"],
            frames_per_buffer=4096,
            stream_callback=sys_cb,
        )
        logger.info(f"System audio stream opened: {self._sys_file}")
        return stream

    def _find_vb_cable(self, p):
        """查找 VB-Audio Cable 虚拟音频设备

        Returns:
            int: 设备索引，未找到返回 None
        """
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            name = info.get("name", "")
            if "VB-Audio" in name or "CABLE Input" in name:
                return i
        return None

    def start(self, mode="mic"):
        if self._recording:
            logger.warning("Already recording")
            return

        self._mode = mode
        self._start_time = time.time()
        self._paused_duration = 0.0
        self._pause_start = None
        self._mic_rate = None
        self._sys_rate = None
        ts = datetime.now().strftime("%y%m%d%H")

        # 清空上次残留的队列数据
        for q in (self._mic_queue, self._sys_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

        if mode in ("mic", "dual"):
            self._mic_file = os.path.join(self.save_dir, f"{ts}会议.wav")
        if mode == "dual":
            self._sys_file = os.path.join(self.save_dir, f"{ts}会议_系统音频.wav")

        self._recording = True
        self._paused = False

        # 启动音频后台线程（所有 PyAudio 操作在此线程中）
        self._audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._audio_thread.start()

        if self.on_state_change:
            self.on_state_change(True, False)

    def _audio_loop(self):
        """音频采集后台线程：创建 PyAudio、打开 Stream、运行 callback

        修复方案:
        - ERR-009: 确保所有 PyAudio 操作在后台线程完成，不干扰 tkinter
        - ERR-010: 先打开所有 stream 再 start，避免设备状态变化窗口期
        """
        import pyaudiowpatch as pyaudio

        p = pyaudio.PyAudio()
        mic_stream = None
        sys_stream = None

        try:
            # 打开麦克风
            if self._mode in ("mic", "dual"):
                mic_stream = self._open_mic_stream(p, pyaudio)

            # 打开系统音频
            if self._mode == "dual":
                sys_stream = self._open_loopback_stream(p, pyaudio)

            # 所有 stream 打开后统一 start（ERR-010 修复）
            if mic_stream:
                mic_stream.start_stream()
                logger.info("Mic recording started")
            if sys_stream:
                sys_stream.start_stream()
                logger.info("System audio recording started")

            # 等待停止信号
            while self._recording:
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Audio loop error: {e}")
        finally:
            # 关闭所有 stream
            if mic_stream:
                try:
                    mic_stream.stop_stream()
                    mic_stream.close()
                except Exception:
                    pass
            if sys_stream:
                try:
                    sys_stream.stop_stream()
                    sys_stream.close()
                except Exception:
                    pass

            # 释放 PyAudio 资源，防止端口泄漏
            try:
                p.terminate()
            except Exception:
                pass

            logger.info("Audio streams closed and PyAudio terminated")

    def pause(self):
        """暂停录音（线程安全）"""
        with self._lock:
            if not self._recording or self._paused:
                return
            self._paused = True
            self._pause_start = time.time()
        logger.info("Recording paused")
        if self.on_state_change:
            self.on_state_change(True, True)

    def resume(self):
        """继续录音（线程安全）"""
        with self._lock:
            if not self._recording or not self._paused:
                return
            self._paused = False
            if self._pause_start:
                self._paused_duration += time.time() - self._pause_start
                self._pause_start = None
        logger.info("Recording resumed")
        if self.on_state_change:
            self.on_state_change(True, False)

    def get_elapsed(self):
        """获取录音时长（线程安全）"""
        with self._lock:
            if not self._recording:
                return self._paused_duration
            elapsed = time.time() - self._start_time - self._paused_duration
            if self._paused:
                elapsed -= (time.time() - self._pause_start)
            return max(0, elapsed)

    def stop(self):
        """停止录音（非阻塞），文件保存在后台线程中完成，通过 on_stop_complete 回调通知"""
        if not self._recording:
            return []
        with self._lock:
            if self._paused and self._pause_start:
                self._paused_duration += time.time() - self._pause_start
            self._recording = False
            self._paused = False

        # 在后台线程中等待音频线程结束并保存文件，避免阻塞 GUI
        threading.Thread(target=self._stop_and_save, daemon=True).start()
        return []

    def _stop_and_save(self):
        """后台线程：等待音频线程退出 → 保存文件 → 回调通知"""
        try:
            if self._audio_thread and self._audio_thread.is_alive():
                self._audio_thread.join(timeout=10)

            saved_files = []

            if self._mic_file and self._mode in ("mic", "dual"):
                f = self._save_audio(self._mic_queue, self._mic_file, self._mic_rate)
                if f:
                    saved_files.append(f)

            if self._sys_file and self._mode == "dual":
                f = self._save_audio(self._sys_queue, self._sys_file, self._sys_rate)
                if f:
                    saved_files.append(f)

            if self.on_state_change:
                self.on_state_change(False, False)

            if self.on_stop_complete:
                self.on_stop_complete(saved_files)

        except Exception as e:
            logger.error(f"Error in _stop_and_save: {e}")
            if self.on_state_change:
                self.on_state_change(False, False)
            if self.on_stop_complete:
                self.on_stop_complete([])

    def _save_audio(self, audio_queue, file_path, sample_rate=None):
        frames = []
        while not audio_queue.empty():
            frames.append(audio_queue.get())
        if not frames:
            logger.warning(f"No audio data for {os.path.basename(file_path)}")
            return None

        audio_data = np.concatenate(frames, axis=0)

        # 多声道转单声道
        if audio_data.ndim == 2 and audio_data.shape[1] > 1:
            audio_data = np.mean(audio_data, axis=1)
        elif audio_data.ndim == 2:
            audio_data = audio_data[:, 0]

        # 确定采样率
        rate = sample_rate or self.target_rate
        duration = len(audio_data) / rate

        # pyaudio float32 数据范围 [-1.0, 1.0]，转为 int16 保存兼容性最好
        audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)

        import soundfile as sf
        sf.write(file_path, audio_int16, rate, subtype="PCM_16")
        logger.info(f"Audio saved: {os.path.basename(file_path)} ({rate}Hz, {duration:.1f}s)")

        if self.on_save:
            self.on_save(file_path, duration)
        return file_path

    @staticmethod
    def list_devices():
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append({
                    "id": i, "name": info["name"], "type": "input",
                    "channels": info["maxInputChannels"],
                    "sample_rate": int(info["defaultSampleRate"]),
                })
        try:
            for d in p.get_loopback_device_info_generator():
                devices.append({
                    "id": d["index"], "name": d["name"], "type": "loopback",
                    "channels": d["maxInputChannels"],
                    "sample_rate": int(d["defaultSampleRate"]),
                })
        except Exception:
            pass
        p.terminate()
        return devices
