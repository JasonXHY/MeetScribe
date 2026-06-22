#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 配置管理
JSON 文件持久化，带默认值
"""

import os
import json
import logging

logger = logging.getLogger("MeetScribe")

# 默认配置
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {
    "recording_dir": os.path.join(PROJECT_ROOT, "recordings"),
    "transcript_dir": os.path.join(PROJECT_ROOT, "transcripts"),
    "output_format": "llm-md",
    "speaker_names": {},
    "auto_transcribe": True,
    "auto_open_result": True,
    # AI 摘要/纠错开关：统一用 UI 下拉框的字符串值（设置页写入、转写调度读取均以此为准）。
    # 转写调度 _process_message 对历史布尔值仍做兼容（见 transcription.py）。
    "auto_correction": "关闭",
    "auto_summary": "转写后自动生成",
    "asr_engine": "SenseVoice",
    "recording_mode": "dual",
    "use_vb_cable": False,  # v1.0: 已移除，使用 WASAPI Loopback
    "window_width": 1000,
    "window_height": 700,
    # v1.0 内测预置 AI 配置
    "ai_vendor": "小米 MiMo",
    "ai_model": "mimo-v2.5",
    "ai_access_mode": "按量计费",
    "ai_default_api_key": "sk-c4wihuvmfe4fv7qurdhk975rinuxflgi056dphuvv25x8lbm",
    "ai_user_api_key": "",
    # 本地 LLM（Ollama）配置：启用开关 + 服务地址 + 模型名（AI-005 / SET-016）
    "ollama_enabled": "关闭",
    "ollama_url": "http://localhost:11434/v1",
    "ollama_model": "qwen3:1.7b",
}


class Config:
    """应用配置管理

    所有配置项通过 DEFAULTS 字典定义，使用 get()/set() 访问。
    """

    @staticmethod
    def _get_default_path():
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "settings.json"
        )

    def __init__(self, config_path=None):
        self._path = config_path or self._get_default_path()
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        """从文件加载配置"""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # 过滤空字符串值，防止覆盖 DEFAULTS 中的有意义默认值
                filtered = {k: v for k, v in saved.items()
                           if v != "" or k not in DEFAULTS or DEFAULTS[k] == ""}
                self._data.update(filtered)
                logger.info(f"Config loaded from {self._path}")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
        else:
            logger.info("No config file found, using defaults")

        # 向后兼容：旧版 mimo 配置 → 新版 ai 配置
        if "mimo_api_key" in self._data and "ai_vendor" not in self._data:
            old_key = self._data.get("mimo_api_key", "")
            old_model = self._data.get("mimo_model", "mimo-v2.5-pro")

            # 模型名映射表（旧版 → 新版）
            model_map = {
                "mimo-v2.5-pro": ("小米 MiMo", "mimo-v2.5-pro"),
                "mimo-v2.5": ("小米 MiMo", "mimo-v2.5"),
                "mimo-v2-flash": ("小米 MiMo", "mimo-v2.5"),  # V2 Flash 已停服，迁移到 V2.5
                "MiMo-V2.5-Pro": ("小米 MiMo", "mimo-v2.5-pro"),
                "MiMo-V2.5": ("小米 MiMo", "mimo-v2.5"),
                "MiMo-V2-Flash": ("小米 MiMo", "mimo-v2.5"),
            }
            vendor, model = model_map.get(old_model, ("小米 MiMo", "mimo-v2.5-pro"))

            self._data["ai_vendor"] = vendor
            self._data["ai_model"] = model
            self._data["ai_access_mode"] = "按量计费"
            self._data["ai_api_key"] = old_key
            self.save()
            logger.info(f"配置已自动迁移: 旧版 mimo 格式 → 新版 ai 格式")

    def save(self):
        """保存配置到文件（原子写入）"""
        import tempfile

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        try:
            dir_name = os.path.dirname(self._path)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=dir_name, delete=False) as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                temp_path = f.name

            # 原子替换
            os.replace(temp_path, self._path)
            logger.info(f"Config saved to {self._path}")
        except Exception as e:
            # 清理临时文件
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, save=True):
        """设置配置值

        Args:
            key: 配置键
            value: 配置值
            save: 是否立即保存到文件（批量操作时可设为 False）
        """
        self._data[key] = value
        if save:
            self.save()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def as_dict(self):
        return dict(self._data)
