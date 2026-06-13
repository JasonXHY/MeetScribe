#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 顶部导航栏组件（替代原侧边栏）
"""

import os
import customtkinter as ctk
from gui.styles import (
    C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT,
    C_TXT1, C_TXT3, FONT_FAMILY, ICON_PNG, APP_VERSION,
)


class TopBar(ctk.CTkFrame):
    """顶部导航栏：Logo + 导航按钮 + 版本号"""

    NAV_ITEMS = [
        ("home",       "主页"),
        ("voiceprint", "音色库"),
        ("settings",   "设置"),
    ]

    def __init__(self, parent, on_navigate=None):
        super().__init__(parent, height=44, fg_color=C_CARD, corner_radius=0,
                         border_width=0)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._nav_buttons = {}
        self._current_page = None
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=0)

        # Logo
        try:
            if os.path.exists(ICON_PNG):
                from PIL import Image
                icon_img = ctk.CTkImage(
                    light_image=Image.open(ICON_PNG), size=(22, 22))
                ctk.CTkLabel(inner, image=icon_img, text="").pack(
                    side="left", padx=(0, 6))
        except Exception:
            pass

        ctk.CTkLabel(
            inner, text="MeetScribe",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=C_ACCENT,
        ).pack(side="left")

        # 分隔线
        ctk.CTkFrame(inner, width=1, height=20, fg_color=C_BORDER).pack(
            side="left", padx=(16, 12))

        # 导航按钮
        for key, label in self.NAV_ITEMS:
            btn = ctk.CTkButton(
                inner, text=label,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                fg_color="transparent", text_color=C_TXT1,
                hover_color=C_ACCENT_LT,
                width=64, height=32, corner_radius=6,
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(side="left", padx=2)
            self._nav_buttons[key] = btn

        # 右侧版本号
        ctk.CTkLabel(
            inner, text=f"v{APP_VERSION} | FunASR",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=C_TXT3,
        ).pack(side="right")

    def _navigate(self, page_key):
        if self._on_navigate:
            self._on_navigate(page_key)

    def highlight(self, page_key):
        """高亮当前页面按钮"""
        self._current_page = page_key
        for key, btn in self._nav_buttons.items():
            if key == page_key:
                btn.configure(
                    fg_color=C_ACCENT_LT, text_color=C_ACCENT,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent", text_color=C_TXT1,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                )
