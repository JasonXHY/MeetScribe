#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[DEPRECATED] 侧边栏组件已由 TopBar 替代。
此文件保留供回退，新代码请使用 src/gui/topbar.py。
"""

import os
import customtkinter as ctk
from gui.styles import (
    C_SIDEBAR, C_BORDER, C_ACCENT, C_ACCENT_LT,
    C_TXT1, C_TXT3, FONT_FAMILY, SIDEBAR_W, ICON_PNG, APP_VERSION,
)


class Sidebar(ctk.CTkFrame):
    """侧边栏导航组件"""

    def __init__(self, parent, on_navigate=None):
        super().__init__(parent, width=SIDEBAR_W, fg_color=C_SIDEBAR, corner_radius=0)
        self.grid(row=0, column=0, rowspan=2, sticky="nsw")
        self.grid_propagate(False)

        self._on_navigate = on_navigate
        self._nav_buttons = {}
        self._current_page = None

        self._build()

    def _build(self):
        # Logo
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 4))

        try:
            if os.path.exists(ICON_PNG):
                from PIL import Image
                icon_img = ctk.CTkImage(
                    light_image=Image.open(ICON_PNG),
                    size=(28, 28),
                )
                ctk.CTkLabel(logo_frame, image=icon_img, text="").pack(side="left", padx=(0, 8))
        except Exception:
            pass

        ctk.CTkLabel(
            logo_frame, text="MeetScribe",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=C_ACCENT,
        ).pack(side="left")

        ctk.CTkLabel(
            self, text="会议转写助手",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(anchor="w", padx=18, pady=(0, 8))

        ctk.CTkFrame(self, height=1, fg_color=C_BORDER).pack(fill="x", padx=16, pady=(4, 12))

        # Navigation
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=12)

        nav_items = [
            ("home",      "主页"),
            ("voiceprint", "音色库"),
            ("settings",  "设置"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                nav_frame, text=f"  {label}", anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                fg_color="transparent", text_color=C_TXT1,
                hover_color=C_ACCENT_LT,
                height=38, corner_radius=6,
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[key] = btn

        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        ctk.CTkLabel(
            self, text=f"v{APP_VERSION}  |  FunASR + MiMo",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=C_TXT3,
        ).pack(padx=16, pady=(0, 12), anchor="w")

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
