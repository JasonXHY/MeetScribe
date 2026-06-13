#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 设置页
"""

import threading
import logging
from tkinter import messagebox

import customtkinter as ctk
from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER, C_SUCCESS, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, C_WARN, FONT_FAMILY, MODEL_CACHE_DIR, OUTPUT_FORMATS,
    APP_VERSION, APP_NAME,
)
from transcriber import ModelManager

logger = logging.getLogger("MeetScribe")


class SettingsPage(ctk.CTkFrame):
    """设置页"""

    def __init__(self, parent, config, log_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._config = config
        self._log = log_callback or (lambda msg: None)
        self._model_manager = ModelManager(MODEL_CACHE_DIR)

        self._build()

    def _build(self):
        """构建设置页面"""
        ctk.CTkLabel(
            self, text="设置",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=C_TXT1,
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)

        self._build_path_section(scroll)
        self._build_engine_section(scroll)
        self._build_ai_section(scroll)
        self._build_model_section(scroll)
        self._build_audio_section(scroll)
        self._build_notification_section(scroll)
        self._build_about_section(scroll)

        # Save button
        ctk.CTkButton(
            scroll, text="  保存设置", width=140, height=36, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=self._on_save,
        ).pack(anchor="w", pady=(8, 20))

    def _build_path_section(self, parent):
        """构建路径设置部分"""
        self._s_title(parent, "存储路径")
        path_card = self._s_card(parent)

        r1 = ctk.CTkFrame(path_card, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(r1, text="录音保存目录", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(anchor="w")
        r1b = ctk.CTkFrame(r1, fg_color="transparent")
        r1b.pack(fill="x", pady=(4, 0))
        self._rec_dir_entry = ctk.CTkEntry(
            r1b, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            border_color=C_BORDER, fg_color=C_BG,
        )
        self._rec_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            r1b, text="浏览", width=64, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, text_color=C_TXT1, border_width=1, border_color=C_BORDER,
            hover_color="#EAEAEA", command=self._browse_recording_dir,
        ).pack(side="right")

        r2 = ctk.CTkFrame(path_card, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(8, 12))
        ctk.CTkLabel(r2, text="转写输出目录", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(anchor="w")
        r2b = ctk.CTkFrame(r2, fg_color="transparent")
        r2b.pack(fill="x", pady=(4, 0))
        self._out_dir_entry = ctk.CTkEntry(
            r2b, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            border_color=C_BORDER, fg_color=C_BG,
        )
        self._out_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            r2b, text="浏览", width=64, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, text_color=C_TXT1, border_width=1, border_color=C_BORDER,
            hover_color="#EAEAEA", command=self._browse_output_dir,
        ).pack(side="right")

    def _build_engine_section(self, parent):
        """构建引擎设置部分"""
        self._s_title(parent, "转写引擎")
        eng_card = self._s_card(parent)

        eng_items = [
            ("标点恢复", ["自动 (ct-punc)", "关闭"], "_punc_var"),
            ("乱码过滤", ["开启 (中文模式)", "关闭"], "_garble_var"),
            ("VAD 灵敏度", ["适中 (推荐)", "高 (更多分段)", "低 (更少分段)"], "_vad_var"),
            ("运算设备", ["CPU", "CUDA (GPU)"], "_device_var"),
        ]
        for i, (label, values, attr) in enumerate(eng_items):
            row = ctk.CTkFrame(eng_card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(10 if i == 0 else 4, 6))
            ctk.CTkLabel(row, text=label, width=90, anchor="w",
                         font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                         text_color=C_TXT2).pack(side="left")
            var = ctk.StringVar(value=values[0])
            setattr(self, attr, var)
            ctk.CTkOptionMenu(
                row, variable=var, values=values,
                width=180, height=30, corner_radius=6,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                fg_color=C_BG, button_color=C_ACCENT,
                button_hover_color=C_BTN_HOVER,
                text_color=C_TXT1,
            ).pack(side="left")

    def _build_ai_section(self, parent):
        """构建 AI 增强设置部分（左右布局）"""
        self._s_title(parent, "AI 增强")
        card = self._s_card(parent)

        from model_registry import get_vendor_list, get_models_for_vendor

        # --- Row 1: 模型厂商 ---
        r_vendor = ctk.CTkFrame(card, fg_color="transparent")
        r_vendor.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(r_vendor, text="模型厂商", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._vendor_var = ctk.StringVar(value="小米")
        ctk.CTkOptionMenu(
            r_vendor, variable=self._vendor_var,
            values=get_vendor_list(),
            command=self._on_vendor_changed,
            width=180, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        ).pack(side="left")

        # --- Row 2: 摘要模型 ---
        r_model = ctk.CTkFrame(card, fg_color="transparent")
        r_model.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(r_model, text="摘要模型", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._model_var = ctk.StringVar(value="MiMo-V2.5-Pro")
        self._model_combo = ctk.CTkOptionMenu(
            r_model, variable=self._model_var,
            values=get_models_for_vendor("小米"),
            width=180, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        )
        self._model_combo.pack(side="left")

        # --- Row 3: API Key ---
        r_api = ctk.CTkFrame(card, fg_color="transparent")
        r_api.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(r_api, text="API Key", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._api_key_var = ctk.StringVar()
        self._api_key_entry = ctk.CTkEntry(
            r_api, textvariable=self._api_key_var, show="*",
            width=280, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            border_color=C_BORDER, fg_color=C_BG,
        )
        self._api_key_entry.pack(side="left", padx=(0, 4))

        self._api_key_visible = False
        self._api_key_toggle = ctk.CTkButton(
            r_api, text="👁", width=30, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            fg_color=C_BG, text_color=C_TXT2, border_width=1, border_color=C_BORDER,
            hover_color="#EAEAEA",
            command=self._toggle_api_key_visibility,
        )
        self._api_key_toggle.pack(side="left")

        # --- Row 4: 接入模式 ---
        r_mode = ctk.CTkFrame(card, fg_color="transparent")
        r_mode.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(r_mode, text="接入模式", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._access_mode_var = ctk.StringVar(value="按量计费")
        ctk.CTkOptionMenu(
            r_mode, variable=self._access_mode_var,
            values=["Token Plan", "按量计费"],
            width=180, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        ).pack(side="left")

        # --- Row 5: 接入模式说明 ---
        r_mode_hint = ctk.CTkFrame(card, fg_color="transparent")
        r_mode_hint.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(r_mode_hint, text="", width=90).pack(side="left")
        ctk.CTkLabel(
            r_mode_hint, text="Token Plan = 包月套餐 | 按量计费 = 按用量付费",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=C_TXT3,
        ).pack(side="left")

        # --- Row 6: 本地 LLM ---
        r_ollama = ctk.CTkFrame(card, fg_color="transparent")
        r_ollama.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(r_ollama, text="本地 LLM", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._ollama_var = ctk.StringVar(value="关闭")
        ctk.CTkOptionMenu(
            r_ollama, variable=self._ollama_var,
            values=["关闭", "Ollama (本地)"],
            width=180, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        ).pack(side="left")

        # --- Row 7: 自动摘要 ---
        r_summary = ctk.CTkFrame(card, fg_color="transparent")
        r_summary.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(r_summary, text="自动摘要", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._auto_summary_var = ctk.StringVar(value="关闭")
        ctk.CTkOptionMenu(
            r_summary, variable=self._auto_summary_var,
            values=["关闭", "转写后自动生成", "手动触发"],
            width=180, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        ).pack(side="left")

        # --- Row 8: 转写纠错 ---
        r_correct = ctk.CTkFrame(card, fg_color="transparent")
        r_correct.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(r_correct, text="转写纠错", width=90, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left")
        self._auto_correction_var = ctk.StringVar(value="关闭")
        ctk.CTkOptionMenu(
            r_correct, variable=self._auto_correction_var,
            values=["关闭", "转写后自动纠错"],
            width=180, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        ).pack(side="left")

        # --- Row 9: 转写纠错说明 ---
        r_correct_hint = ctk.CTkFrame(card, fg_color="transparent")
        r_correct_hint.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(r_correct_hint, text="", width=90).pack(side="left")
        ctk.CTkLabel(
            r_correct_hint, text="LLM 纠错转写错字、乱码、标点",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=C_TXT3,
        ).pack(side="left")

    def _on_vendor_changed(self, vendor):
        """厂商切换时更新模型列表"""
        from model_registry import get_models_for_vendor
        models = get_models_for_vendor(vendor)
        if models:
            self._model_combo.configure(values=models)
            self._model_var.set(models[0])
        else:
            self._model_combo.configure(values=[])
            self._model_var.set("")

    def _build_model_section(self, parent):
        """构建模型设置部分"""
        self._s_title(parent, "模型管理")
        model_card = self._s_card(parent)

        self._model_status_frame = ctk.CTkFrame(model_card, fg_color="transparent")
        self._model_status_frame.pack(fill="x", padx=16, pady=(12, 6))

        model_btn_frame = ctk.CTkFrame(model_card, fg_color="transparent")
        model_btn_frame.pack(fill="x", padx=16, pady=(6, 12))

        self._btn_check_models = ctk.CTkButton(
            model_btn_frame, text="检查模型", width=100, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=self._check_models,
        )
        self._btn_check_models.pack(side="left", padx=(0, 8))

        self._btn_download_models = ctk.CTkButton(
            model_btn_frame, text="下载缺失模型", width=120, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_SUCCESS, hover_color="#0A5E0A",
            command=self._download_missing_models,
        )
        self._btn_download_models.pack(side="left", padx=(0, 8))

        self._model_status_label = ctk.CTkLabel(
            model_btn_frame, text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        )
        self._model_status_label.pack(side="left", padx=(8, 0))

        self._refresh_model_status()

    def _build_audio_section(self, parent):
        """构建音频设置部分"""
        self._s_title(parent, "音频设备")
        audio_card = self._s_card(parent)

        self._vb_cable_var = ctk.BooleanVar(value=self._config.get("use_vb_cable", False))

        ctk.CTkCheckBox(
            audio_card, text="使用 VB-Audio Cable（推荐）",
            variable=self._vb_cable_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT1,
        ).pack(anchor="w", padx=16, pady=(12, 5))

        ctk.CTkLabel(
            audio_card, text="启用后可避免停止录音时暂停媒体播放器",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _build_notification_section(self, parent):
        """构建通知设置部分"""
        self._s_title(parent, "通知")
        notify_card = self._s_card(parent)

        self._notification_var = ctk.BooleanVar(value=self._config.get("enable_notification", True))

        ctk.CTkCheckBox(
            notify_card, text="启用系统通知",
            variable=self._notification_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT1,
        ).pack(anchor="w", padx=16, pady=(12, 5))

        ctk.CTkLabel(
            notify_card, text="转写完成后发送系统通知并弹窗提示",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _build_about_section(self, parent):
        """构建关于部分"""
        self._s_title(parent, "关于")
        about_card = self._s_card(parent)
        about_f = ctk.CTkFrame(about_card, fg_color="transparent")
        about_f.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            about_f, text=f"{APP_NAME} v{APP_VERSION}  —  本地会议录音转写助手",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=C_TXT1, anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        ctk.CTkLabel(
            about_f, text="制作者：刘家诚",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2, anchor="w",
        ).pack(anchor="w", pady=2)

        for line in [
            "引擎: FunASR SenseVoice + CAM++ + ct-punc (本地推理)",
            "AI: MiMo 云端 (摘要/纠错) + 内网大模型 (预留)",
            "支持格式: WAV / MP3 / M4A / FLAC / OGG / OGA / OPUS",
        ]:
            ctk.CTkLabel(
                about_f, text=line,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=C_TXT2, anchor="w",
            ).pack(anchor="w", pady=2)

    def _s_title(self, parent, text):
        ctk.CTkLabel(
            parent, text=f"  {text}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=C_TXT1,
        ).pack(anchor="w", pady=(12, 4))

    def _s_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=8,
                            border_width=1, border_color=C_BORDER)
        card.pack(fill="x", pady=(0, 4))
        return card

    def restore_config(self):
        """从配置恢复 UI 状态"""
        self._rec_dir_entry.insert(0, self._config.get("recording_dir", r"C:\MeetScribe\recordings"))
        self._out_dir_entry.insert(0, self._config.get("transcript_dir", r"C:\MeetScribe\transcripts"))

        # AI 增强配置（新格式，兼容旧键）
        self._vendor_var.set(self._config.get("ai_vendor", "小米"))
        # 先触发一次厂商变更以填充模型列表
        self._on_vendor_changed(self._vendor_var.get())
        self._model_var.set(self._config.get("ai_model", "MiMo-V2.5-Pro"))
        self._access_mode_var.set(self._config.get("ai_access_mode", "按量计费"))

        api_key = self._config.get("ai_api_key", "")
        if not api_key:
            # 回退到旧键
            api_key = self._config.get("mimo_api_key", "")
        if api_key:
            self._api_key_var.set(api_key)

        self._ollama_var.set(self._config.get("ollama_enabled", "关闭"))
        self._auto_summary_var.set(self._config.get("auto_summary", "关闭"))
        self._auto_correction_var.set(self._config.get("auto_correction", "关闭"))
        self._vb_cable_var.set(self._config.get("use_vb_cable", False))
        self._notification_var.set(self._config.get("enable_notification", True))

    def _toggle_api_key_visibility(self):
        """切换 API Key 明文/密文显示"""
        self._api_key_visible = not self._api_key_visible
        if self._api_key_visible:
            self._api_key_entry.configure(show="")
            self._api_key_toggle.configure(text="🔒")
        else:
            self._api_key_entry.configure(show="*")
            self._api_key_toggle.configure(text="👁")

    def save_config(self):
        """保存当前 UI 状态到配置"""
        self._config.set("recording_dir", self._rec_dir_entry.get().strip())
        self._config.set("transcript_dir", self._out_dir_entry.get().strip())

        # AI 增强配置（新格式）
        self._config.set("ai_vendor", self._vendor_var.get())
        self._config.set("ai_model", self._model_var.get())
        self._config.set("ai_access_mode", self._access_mode_var.get())
        self._config.set("ai_api_key", self._api_key_var.get().strip())

        # 过渡期：同时保留旧键
        self._config.set("mimo_api_key", self._config.get("ai_api_key", ""))
        self._config.set("mimo_model", self._config.get("ai_model", ""))

        self._config.set("ollama_enabled", self._ollama_var.get())
        self._config.set("auto_summary", self._auto_summary_var.get())
        self._config.set("auto_correction", self._auto_correction_var.get())
        self._config.set("use_vb_cable", self._vb_cable_var.get())
        self._config.set("enable_notification", self._notification_var.get())
        self._config.save()

    def _on_save(self):
        self.save_config()
        self._log("设置已保存")

    def _browse_recording_dir(self):
        from tkinter import filedialog
        import os
        path = filedialog.askdirectory(title="选择录音保存目录")
        if path:
            self._rec_dir_entry.delete(0, "end")
            self._rec_dir_entry.insert(0, path)
            os.makedirs(path, exist_ok=True)
            self._log(f"录音目录: {path}")

    def _browse_output_dir(self):
        from tkinter import filedialog
        import os
        path = filedialog.askdirectory(title="选择转写输出目录")
        if path:
            self._out_dir_entry.delete(0, "end")
            self._out_dir_entry.insert(0, path)
            os.makedirs(path, exist_ok=True)
            self._log(f"输出目录: {path}")

    def _refresh_model_status(self):
        """刷新模型状态显示"""
        if not self._model_manager:
            return

        for widget in self._model_status_frame.winfo_children():
            widget.destroy()

        status = self._model_manager.check_all_models()

        for model_id, state in status.items():
            row = ctk.CTkFrame(self._model_status_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            if state["cached"]:
                icon = "✅"
                color = C_SUCCESS
            else:
                icon = "❌"
                color = C_ERROR if state["info"]["required"] else C_WARN

            ctk.CTkLabel(row, text=icon, width=24,
                         font=ctk.CTkFont(size=12)).pack(side="left")

            ctk.CTkLabel(
                row, text=model_id, width=180, anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=C_TXT1,
            ).pack(side="left", padx=(4, 8))

            ctk.CTkLabel(
                row, text=state["info"]["description"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=C_TXT2,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkLabel(
                row, text=state["info"]["size_hint"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=C_TXT3,
            ).pack(side="left")

            status_text = "已缓存" if state["cached"] else ("必需" if state["info"]["required"] else "可选")
            ctk.CTkLabel(
                row, text=status_text,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=color,
            ).pack(side="right")

        missing = self._model_manager.get_missing_models(required_only=True)
        if missing:
            self._model_status_label.configure(
                text=f"缺少 {len(missing)} 个必需模型",
                text_color=C_ERROR,
            )
        else:
            self._model_status_label.configure(
                text="所有必需模型已就绪",
                text_color=C_SUCCESS,
            )

    def _check_models(self):
        self._log("正在检查模型状态...")
        self._refresh_model_status()
        self._log("模型检查完成")

    def _download_missing_models(self):
        missing = self._model_manager.get_missing_models(required_only=True)
        if not missing:
            messagebox.showinfo("提示", "所有必需模型已就绪，无需下载")
            return

        model_list = "\n".join(f"  - {m}" for m in missing)
        if not messagebox.askyesno("确认下载",
                                   f"将下载以下模型:\n{model_list}\n\n下载可能需要较长时间，是否继续?"):
            return

        self._btn_download_models.configure(state="disabled", text="下载中...")

        def download_worker():
            try:
                success, msg = self._model_manager.download_all_missing(
                    progress_callback=lambda m: self.after(0, self._log, m)
                )
                self.after(0, self._on_download_complete, success, msg)
            except Exception as e:
                self.after(0, self._on_download_complete, False, str(e))

        threading.Thread(target=download_worker, daemon=True).start()

    def _on_download_complete(self, success, msg):
        self._btn_download_models.configure(state="normal", text="下载缺失模型")
        self._refresh_model_status()

        if success:
            self._log(f"模型下载完成: {msg}")
            messagebox.showinfo("完成", msg)
        else:
            self._log(f"模型下载失败: {msg}")
            messagebox.showerror("错误", f"模型下载失败:\n{msg}")
