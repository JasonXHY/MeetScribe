"""
录音控制栏组件（PySide6 版本）

从 home_page.py 中提取的录音控制 UI，包含：
- 录音指示点和状态文本
- 录音模式选择（现场会议/线上会议）及模式提示
- 计时器显示
- 开始/暂停/停止按钮
- 转写队列状态
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QComboBox, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from gui.styles import (
    C_CARD, C_BORDER, C_ACCENT_LT, C_ERROR, C_WARN,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY,
)


class RecordingBar(QFrame):
    """录音控制栏组件"""

    # 模式反查表
    _MODE_REVERSE = {"现场会议": "mic", "线上会议": "dual"}

    start_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()
    mode_changed = Signal(str)

    def __init__(self, parent=None, initial_mode="dual"):
        super().__init__(parent)

        self._initial_display = {"mic": "现场会议", "dual": "线上会议"}.get(initial_mode, "现场会议")
        self._recording = False
        self._paused = False

        self._setup_ui()

    def _setup_ui(self):
        """初始化 UI"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 去掉自身 margins，外层已设置
        layout.setSpacing(0)  # 基础 spacing 为 0，手动控制间距

        # 录音指示点
        self._rec_dot = QLabel()
        self._rec_dot.setFixedSize(12, 12)
        self._rec_dot.setStyleSheet(f"""
            background-color: {C_TXT3};
            border-radius: 6px;
            border: none;
        """)
        layout.addWidget(self._rec_dot)

        # 录音状态文本
        self._rec_status_lbl = QLabel("准备就绪")
        self._rec_status_lbl.setFixedWidth(56)
        self._rec_status_lbl.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._rec_status_lbl)

        # 录音模式选择
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["现场会议", "线上会议"])
        self.mode_combo.setCurrentText(self._initial_display)
        self.mode_combo.setFixedWidth(100)
        self.mode_combo.setFixedHeight(28)
        self.mode_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 2px 8px;
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background-color: #F0F0F0;
                color: {C_TXT1};
            }}
            QComboBox:hover {{
                background-color: #E0E0E0;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: white;
                border: 1px solid {C_BORDER};
                selection-background-color: {C_ACCENT_LT};
            }}
        """)
        self.mode_combo.currentTextChanged.connect(self._handle_mode_change)
        layout.addWidget(self.mode_combo)

        self._rec_mode_hint = QLabel(self._initial_display)
        self._rec_mode_hint.setFixedWidth(60)
        self._rec_mode_hint.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._rec_mode_hint)

        layout.addSpacing(6)  # 模式和计时器之间的间距

        # 计时器
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setFixedWidth(110)
        self.timer_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT1};
                font-family: {FONT_FAMILY};
                font-size: 22px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.timer_label)

        # 开始录音按钮
        self.record_btn = QPushButton("开始录音")
        self.record_btn.setFixedSize(90, 32)
        self.record_btn.setCursor(Qt.PointingHandCursor)
        self.record_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ERROR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #A52318;
            }}
            QPushButton:disabled {{
                background-color: {C_TXT3};
            }}
        """)
        self.record_btn.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self.record_btn)

        # 暂停按钮
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setFixedSize(60, 32)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {C_ERROR};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
                color: {C_ERROR};
            }}
            QPushButton:hover {{
                background-color: #FDE8E8;
            }}
            QPushButton:disabled {{
                border-color: {C_TXT3};
                color: {C_TXT3};
            }}
        """)
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        layout.addWidget(self.pause_btn)

        # 停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFixedSize(60, 32)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {C_TXT3};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
                color: {C_TXT3};
            }}
            QPushButton:hover {{
                background-color: #F0F0F0;
            }}
            QPushButton:disabled {{
                border-color: {C_TXT3};
                color: {C_TXT3};
            }}
        """)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.stop_btn)

        # 弹性空间（填充中间，使左右分离）
        layout.addStretch()

        # 右侧信息（先添加，确保靠右）
        info_label = QLabel("16kHz WAV · 录音结束后可直接转写")
        info_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 10px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(info_label)

        layout.addSpacing(10)

        # 队列状态
        self._queue_label = QLabel("转写队列: 空")
        self._queue_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._queue_label)

    def _handle_mode_change(self, display_name):
        """处理模式切换"""
        mode = self._MODE_REVERSE.get(display_name, "mic")
        self._rec_mode_hint.setText(display_name)
        self.mode_changed.emit(mode)

    def update_state(self, recording, paused):
        """更新录音状态（完整状态管理，含颜色、指示点、标签）"""
        self._recording = recording
        self._paused = paused

        if recording and not paused:
            # 录音中
            self.record_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {C_ERROR};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-family: {FONT_FAMILY};
                    font-size: 12px;
                    color: {C_ERROR};
                }}
                QPushButton:hover {{
                    background-color: #FDE8E8;
                }}
            """)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("暂停")
            self._rec_dot.setStyleSheet(f"""
                background-color: {C_ERROR};
                border-radius: 6px;
                border: none;
            """)
            self._rec_status_lbl.setText("录音中")
            self._rec_status_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {C_ERROR};
                    font-family: {FONT_FAMILY};
                    font-size: 12px;
                    background: transparent;
                    border: none;
                }}
            """)
            self.timer_label.setStyleSheet(f"""
                QLabel {{
                    color: {C_ERROR};
                    font-family: {FONT_FAMILY};
                    font-size: 22px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)

        elif recording and paused:
            # 已暂停
            self.pause_btn.setText("继续")
            self._rec_dot.setStyleSheet(f"""
                background-color: {C_WARN};
                border-radius: 6px;
                border: none;
            """)
            self._rec_status_lbl.setText("已暂停")
            self._rec_status_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {C_WARN};
                    font-family: {FONT_FAMILY};
                    font-size: 12px;
                    background: transparent;
                    border: none;
                }}
            """)
            self.timer_label.setStyleSheet(f"""
                QLabel {{
                    color: {C_WARN};
                    font-family: {FONT_FAMILY};
                    font-size: 22px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)

        else:
            # 已停止 / 就绪
            self.record_btn.setEnabled(True)
            self.record_btn.setText("开始录音")
            self.stop_btn.setEnabled(False)
            self.stop_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {C_TXT3};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-family: {FONT_FAMILY};
                    font-size: 12px;
                    color: {C_TXT3};
                }}
                QPushButton:hover {{
                    background-color: #F0F0F0;
                }}
                QPushButton:disabled {{
                    border-color: {C_TXT3};
                    color: {C_TXT3};
                }}
            """)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("暂停")
            self._rec_dot.setStyleSheet(f"""
                background-color: {C_TXT3};
                border-radius: 6px;
                border: none;
            """)
            self._rec_status_lbl.setText("准备就绪")
            self._rec_status_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {C_TXT2};
                    font-family: {FONT_FAMILY};
                    font-size: 12px;
                    background: transparent;
                    border: none;
                }}
            """)
            self.timer_label.setText("00:00:00")
            self.timer_label.setStyleSheet(f"""
                QLabel {{
                    color: {C_TXT1};
                    font-family: {FONT_FAMILY};
                    font-size: 22px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)

    def update_timer(self, elapsed):
        """更新计时器显示"""
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def update_queue_status(self, text):
        """更新队列状态文本"""
        self._queue_label.setText(text)

    def get_mode(self):
        """获取录音模式"""
        mode_text = self.mode_combo.currentText()
        return "dual" if mode_text == "线上会议" else "mic"
