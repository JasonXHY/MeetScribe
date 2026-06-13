#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe GUI 样式常量和配置常量
"""

import os

# ── Color Palette (Windows 11 Light Fluent) ──────────────────
C_BG         = "#F3F3F3"
C_SIDEBAR    = "#FAFAFA"
C_CARD       = "#FFFFFF"
C_BORDER     = "#E5E5E5"
C_ACCENT     = "#0067C0"
C_ACCENT_LT  = "#E8F0FE"
C_SUCCESS    = "#0F7B0F"
C_WARN       = "#9D5D00"
C_ERROR      = "#C42B1C"
C_TXT1       = "#1A1A1A"
C_TXT2       = "#616161"
C_TXT3       = "#757575"
C_BTN_HOVER  = "#005BA1"

# ── Constants ────────────────────────────────────────────────
APP_VERSION  = "0.9"
APP_NAME     = "MeetScribe"
FONT_FAMILY  = "Segoe UI"
SIDEBAR_W    = 170  # 临时保留，Task 2 会移除
TOPBAR_H     = 44
ASSETS_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
ICON_PNG     = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO     = os.path.join(ASSETS_DIR, "icon.ico")

# ── File Dialog Filters ──────────────────────────────────────
AUDIO_EXTENSIONS = [
    ("音频文件", "*.wav *.mp3 *.m4a *.flac *.ogg *.oga *.opus"),
    ("WAV", "*.wav"), ("MP3", "*.mp3"), ("M4A", "*.m4a"),
    ("FLAC", "*.flac"), ("OGG/OGA", "*.ogg *.oga *.opus"),
    ("所有文件", "*.*"),
]

# ── Output Formats ───────────────────────────────────────────
OUTPUT_FORMATS = {
    "Markdown (推荐)": "md",
    "LLM Markdown": "llm-md",
    "HTML 网页 (带颜色)": "html",
    "纯文本 (txt)": "txt",
    "SRT 字幕": "srt",
    "JSON 数据": "json",
}

# ── Model Cache ──────────────────────────────────────────────
MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models_cache")

# ── Speaker Colors ───────────────────────────────────────────
SPEAKER_COLORS = [
    "#4A90D9", "#E67E22", "#27AE60", "#E74C3C",
    "#9B59B6", "#1ABC9C", "#F39C12", "#2C3E50",
    "#16A085", "#C0392B", "#2980B9", "#8E44AD",
]

# ── Icons ──────────────────────────────────────────────────
ICON_STATUS = {
    "pending": "○",
    "processing": "⏳",
    "done": "✓",
    "failed": "✗",
}

ICON_ACTION = {
    "preview": "👁",
    "open": "📂",
    "speaker": "👤",
    "retry": "🔄",
    "stop": "⏹",
    "transcribe": "▶",
    "export": "📤",
}

ICON_COLOR = {
    "pending": "#757575",
    "processing": "#007bff",
    "done": "#28a745",
    "failed": "#dc3545",
}

# ── Tooltips ──────────────────────────────────────────────────
TOOLTIPS = {
    "preview": "预览转写结果",
    "open": "打开文件夹",
    "speaker": "管理发言人",
    "retry": "重新转写",
    "stop": "停止转写",
    "transcribe": "开始转写",
    "export": "导出结果",
    "move_up": "上移",
    "move_down": "下移",
    "remove": "从队列移除",
}
