"""
侧耳倾听 顶部导航栏组件（PySide6 版本）
"""

import os
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from gui.styles import (
    C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT,
    C_TXT1, C_TXT3, FONT_FAMILY, ICON_PNG, APP_VERSION,
)


class TopBar(QFrame):
    """顶部导航栏：Logo + 导航按钮 + 版本号"""

    NAV_ITEMS = [
        ("home",       "主页"),
        ("voiceprint", "音色库"),
        ("settings",   "设置"),
    ]

    navigate_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: none;
                border-bottom: 1px solid {C_BORDER};
            }}
        """)

        self._nav_buttons = {}
        self._current_page = None
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        # Logo
        if os.path.exists(ICON_PNG):
            icon_label = QLabel()
            pixmap = QPixmap(ICON_PNG).scaled(
                22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            layout.addWidget(icon_label)
            layout.addSpacing(6)

        # App name
        name_label = QLabel("侧耳倾听")
        name_label.setStyleSheet(f"""
            QLabel {{
                color: {C_ACCENT};
                font-family: {FONT_FAMILY};
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(name_label)
        layout.addSpacing(12)

        # Navigation buttons
        for key, label in self.NAV_ITEMS:
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setMinimumWidth(64)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-family: {FONT_FAMILY};
                    font-size: 13px;
                    color: {C_TXT1};
                }}
                QPushButton:hover {{
                    background-color: {C_ACCENT_LT};
                }}
            """)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            layout.addWidget(btn)
            layout.addSpacing(2)
            self._nav_buttons[key] = btn

        layout.addStretch()

        # Version label
        from gui.styles import APP_NAME_EN
        version_label = QLabel(f"{APP_NAME_EN} v{APP_VERSION}")
        version_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 10px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(version_label)

    def _navigate(self, page_key):
        self.navigate_clicked.emit(page_key)

    def highlight(self, page_key):
        """高亮当前页面按钮"""
        self._current_page = page_key
        for key, btn in self._nav_buttons.items():
            if key == page_key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {C_ACCENT_LT};
                        border: none;
                        border-radius: 6px;
                        padding: 4px 12px;
                        font-family: {FONT_FAMILY};
                        font-size: 13px;
                        font-weight: bold;
                        color: {C_ACCENT};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: 6px;
                        padding: 4px 12px;
                        font-family: {FONT_FAMILY};
                        font-size: 13px;
                        color: {C_TXT1};
                    }}
                    QPushButton:hover {{
                        background-color: {C_ACCENT_LT};
                    }}
                """)
