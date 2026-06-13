#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
录音控制栏组件

从 home_page.py 中提取的录音控制 UI，包含：
- 录音指示点和状态文本
- 录音模式选择（现场会议/线上会议）及模式提示
- 计时器显示
- 开始/暂停/停止按钮
- 转写队列状态
"""

import customtkinter as ctk
from gui.styles import (
    C_CARD, C_BORDER, C_ERROR, C_WARN,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY,
)


class RecordingBar(ctk.CTkFrame):
    """录音控制栏组件"""

    # 模式反查表
    _MODE_REVERSE = {"现场会议": "mic", "线上会议": "dual"}

    def __init__(self, parent, on_start=None, on_stop=None, on_pause=None,
                 on_mode_change=None, initial_mode="dual", **kwargs):
        """
        Args:
            parent: 父容器
            on_start: 开始录音回调
            on_stop: 停止录音回调
            on_pause: 暂停/继续录音回调
            on_mode_change: 模式切换回调，签名 (mode: str) 其中 mode 为 "mic" 或 "dual"
            initial_mode: 初始录音模式 "mic" 或 "dual"
        """
        super().__init__(parent, **kwargs)

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_pause = on_pause
        self._on_mode_change = on_mode_change

        # 反查初始显示名
        mode_display = {"mic": "现场会议", "dual": "线上会议"}
        self._initial_display = mode_display.get(initial_mode, "现场会议")

        self._setup_ui()

    def _setup_ui(self):
        """初始化 UI"""
        # 录音指示点
        self._rec_dot = ctk.CTkLabel(
            self, text="", width=12, height=12,
            fg_color=C_TXT3, corner_radius=6,
        )
        self._rec_dot.pack(side="left", padx=(0, 6))

        # 录音状态文本
        self._rec_status_lbl = ctk.CTkLabel(
            self, text="准备就绪",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2, width=56,
        )
        self._rec_status_lbl.pack(side="left", padx=(0, 10))

        # 录音模式选择
        self.mode_var = ctk.StringVar(value=self._initial_display)
        self.mode_menu = ctk.CTkOptionMenu(
            self, values=["现场会议", "线上会议"],
            variable=self.mode_var, width=100, height=28, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color="#F0F0F0", button_color="#D0D0D0",
            button_hover_color="#C0C0C0",
            text_color=C_TXT1,
            command=self._handle_mode_change,
        )
        self.mode_menu.pack(side="left", padx=(0, 6))

        # 模式提示
        self._rec_mode_hint = ctk.CTkLabel(
            self, text=self._initial_display,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=C_TXT3, width=60,
        )
        self._rec_mode_hint.pack(side="left", padx=(0, 10))

        # 计时器
        self.timer_label = ctk.CTkLabel(
            self, text="00:00:00",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=C_TXT1, width=110,
        )
        self.timer_label.pack(side="left", padx=(0, 12))

        # 控制按钮
        self.record_btn = ctk.CTkButton(
            self, text="开始录音", width=90, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=C_ERROR, hover_color="#A52318",
            command=self._on_start,
        )
        self.record_btn.pack(side="left", padx=(0, 6))

        self.pause_btn = ctk.CTkButton(
            self, text="暂停", width=60, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", border_width=1, border_color=C_ERROR,
            text_color=C_ERROR, hover_color="#FDE8E8",
            state="disabled",
            command=self._on_pause,
        )
        self.pause_btn.pack(side="left", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            self, text="停止", width=60, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", border_width=1, border_color=C_TXT3,
            text_color=C_TXT3, hover_color="#F0F0F0",
            state="disabled",
            command=self._on_stop,
        )
        self.stop_btn.pack(side="left")

        # 右侧信息
        ctk.CTkLabel(
            self, text="16kHz WAV · 录音结束后可直接转写",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=C_TXT3,
        ).pack(side="right")

        # 队列状态
        self._queue_label = ctk.CTkLabel(
            self, text="转写队列: 空",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        )
        self._queue_label.pack(side="right", padx=(0, 10))

    def _handle_mode_change(self, display_name):
        """处理模式切换"""
        mode = self._MODE_REVERSE.get(display_name, "mic")
        self._rec_mode_hint.configure(text=display_name)
        if self._on_mode_change:
            self._on_mode_change(mode)

    def update_state(self, recording, paused):
        """更新录音状态（完整状态管理，含颜色、指示点、标签）"""
        if recording and not paused:
            # 录音中
            self.record_btn.configure(state="disabled")
            self.stop_btn.configure(
                state="normal", border_color=C_ERROR, text_color=C_ERROR)
            self.pause_btn.configure(state="normal", text="暂停")
            self._rec_dot.configure(fg_color=C_ERROR)
            self._rec_status_lbl.configure(text="录音中", text_color=C_ERROR)
            self.timer_label.configure(text_color=C_ERROR)

        elif recording and paused:
            # 已暂停
            self.pause_btn.configure(text="继续")
            self._rec_dot.configure(fg_color=C_WARN)
            self._rec_status_lbl.configure(text="已暂停", text_color=C_WARN)
            self.timer_label.configure(text_color=C_WARN)

        else:
            # 已停止 / 就绪
            self.record_btn.configure(state="normal", text="开始录音")
            self.stop_btn.configure(
                state="disabled", border_color=C_TXT3, text_color=C_TXT3)
            self.pause_btn.configure(state="disabled", text="暂停")
            self._rec_dot.configure(fg_color=C_TXT3)
            self._rec_status_lbl.configure(text="准备就绪", text_color=C_TXT2)
            self.timer_label.configure(text="00:00:00", text_color=C_TXT1)

    def update_timer(self, elapsed):
        """更新计时器显示"""
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.timer_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def update_queue_status(self, text):
        """更新队列状态文本"""
        self._queue_label.configure(text=text)

    def get_mode(self):
        """获取录音模式"""
        mode_text = self.mode_var.get()
        return "dual" if mode_text == "线上会议" else "mic"
