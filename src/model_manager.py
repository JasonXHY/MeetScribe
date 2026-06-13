#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型管理器：负责检查、下载和管理 AI 模型
"""

import os
import json
import logging
from pathlib import Path


class ModelManager:
    """模型管理器"""

    # 模型配置
    MODELS = {
        "sensevoice": {
            "name": "iic/SenseVoiceSmall",
            "description": "语音识别模型",
        },
        "cam++": {
            "name": "iic/speech_campplus_sv_zh-cn_16k-common",
            "description": "说话人分离模型",
        },
        "ct-punc": {
            "name": "iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727",
            "description": "标点恢复模型",
        },
    }

    def __init__(self, cache_dir=None):
        self._cache_dir = cache_dir or self._get_default_cache_dir()
        self._status_file = os.path.join(self._cache_dir, "model_status.json")
        self._status = self._load_status()

    def check_models(self):
        """检查模型状态"""
        status = {}
        for model_key, model_info in self.MODELS.items():
            model_path = os.path.join(self._cache_dir, model_info["name"].replace("/", "--"))
            status[model_key] = {
                "exists": os.path.exists(model_path),
                "path": model_path,
                "description": model_info["description"],
            }
        return status

    def get_model_path(self, model_key):
        """获取模型路径"""
        if model_key not in self.MODELS:
            raise ValueError(f"未知模型: {model_key}")

        model_info = self.MODELS[model_key]
        return os.path.join(self._cache_dir, model_info["name"].replace("/", "--"))

    def download_models(self, callback=None):
        """下载缺失模型"""
        status = self.check_models()

        for model_key, info in status.items():
            if not info["exists"]:
                logging.info(f"下载模型: {model_key}")
                self._download_model(model_key, callback)

    def _download_model(self, model_key, callback=None):
        """下载单个模型"""
        try:
            from modelscope import snapshot_download

            model_info = self.MODELS[model_key]
            model_name = model_info["name"]

            if callback:
                callback(f"正在下载 {model_key}...")

            snapshot_download(model_name, cache_dir=self._cache_dir)

            # 更新状态
            self._status[model_key] = {"downloaded": True}
            self._save_status()

            if callback:
                callback(f"{model_key} 下载完成")

        except Exception as e:
            logging.error(f"下载模型 {model_key} 失败: {e}")
            if callback:
                callback(f"{model_key} 下载失败: {e}")

    def _load_status(self):
        """加载模型状态"""
        try:
            if os.path.exists(self._status_file):
                with open(self._status_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_status(self):
        """保存模型状态"""
        try:
            os.makedirs(os.path.dirname(self._status_file), exist_ok=True)
            with open(self._status_file, "w", encoding="utf-8") as f:
                json.dump(self._status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存模型状态失败: {e}")

    def _get_default_cache_dir(self):
        """获取默认缓存目录"""
        return os.path.join(os.path.dirname(__file__), "..", "models_cache")
