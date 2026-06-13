"""
首次启动引导弹窗（PySide6 版本）

功能：
- 检测是否首次启动
- 提示用户选择模型存储位置
- 显示模型下载进度
- 保存配置
"""

import os
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QProgressBar, QMessageBox, QWidget,
    QFrame
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY, MODEL_CACHE_DIR
)

logger = logging.getLogger("MeetScribe")


class ModelDownloadWorker(QThread):
    """模型下载工作线程"""
    progress = Signal(int, str)  # percent, message
    finished = Signal(bool, str)  # success, message

    def __init__(self, target_dir):
        super().__init__()
        self._target_dir = target_dir

    def run(self):
        try:
            # 检查目标目录
            os.makedirs(self._target_dir, exist_ok=True)

            # 模拟下载过程（实际应从云端下载）
            models = [
                ("SenseVoice", "~900MB"),
                ("ct-punc", "~1GB"),
                ("CAM++", "~60MB"),
                ("fsmn-vad", "~2MB"),
            ]

            total = len(models)
            for i, (name, size) in enumerate(models):
                percent = int((i + 1) / total * 100)
                self.progress.emit(percent, f"正在下载 {name} ({size})...")
                # 模拟下载延迟
                import time
                time.sleep(0.5)

            self.finished.emit(True, "模型下载完成")

        except Exception as e:
            self.finished.emit(False, f"下载失败: {e}")


class FirstLaunchDialog(QDialog):
    """首次启动引导弹窗"""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用侧耳倾听")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self._config = config
        self._model_dir = MODEL_CACHE_DIR
        self._worker = None

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # 标题
        title = QLabel("欢迎使用侧耳倾听")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 24px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        # 说明
        desc = QLabel("首次使用需要下载语音识别模型（约 2GB）\n请选择模型存储位置：")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(f"""
            QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY};
                font-size: 14px; line-height: 1.5; }}
        """)
        layout.addWidget(desc)

        # 模型路径选择
        path_frame = QFrame()
        path_frame.setStyleSheet(f"""
            QFrame {{ background-color: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 8px; }}
        """)
        path_layout = QHBoxLayout(path_frame)
        path_layout.setContentsMargins(16, 12, 16, 12)

        self._path_entry = QLineEdit(self._model_dir)
        self._path_entry.setStyleSheet(f"""
            QLineEdit {{ border: 1px solid {C_BORDER}; border-radius: 6px;
                padding: 8px 12px; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        path_layout.addWidget(self._path_entry, 1)

        browse_btn = QPushButton("浏览")
        browse_btn.setFixedSize(80, 32)
        browse_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_CARD}; color: {C_TXT1};
                border: 1px solid {C_BORDER}; border-radius: 6px;
                font-family: {FONT_FAMILY}; font-size: 12px; }}
            QPushButton:hover {{ background-color: #F5F5F5; }}
        """)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(browse_btn)

        layout.addWidget(path_frame)

        # 进度条（初始隐藏）
        self._progress_frame = QWidget()
        self._progress_layout = QVBoxLayout(self._progress_frame)
        self._progress_layout.setContentsMargins(0, 0, 0, 0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background-color: #E0E0E0;
                border-radius: 3px; height: 8px; text-align: center; }}
            QProgressBar::chunk {{ background-color: {C_ACCENT}; border-radius: 3px; }}
        """)
        self._progress_bar.setVisible(False)
        self._progress_layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignCenter)
        self._progress_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        self._progress_label.setVisible(False)
        self._progress_layout.addWidget(self._progress_label)

        layout.addWidget(self._progress_frame)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        skip_btn = QPushButton("跳过（稍后下载）")
        skip_btn.setFixedSize(140, 36)
        skip_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {C_TXT2};
                border: 1px solid {C_BORDER}; border-radius: 6px;
                font-family: {FONT_FAMILY}; font-size: 12px; }}
            QPushButton:hover {{ background-color: #F5F5F5; }}
        """)
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.clicked.connect(self._skip)
        btn_layout.addWidget(skip_btn)

        self._download_btn = QPushButton("开始下载")
        self._download_btn.setFixedSize(120, 36)
        self._download_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 6px;
                font-family: {FONT_FAMILY}; font-size: 13px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {C_BTN_HOVER}; }}
            QPushButton:disabled {{ background-color: {C_TXT3}; }}
        """)
        self._download_btn.setCursor(Qt.PointingHandCursor)
        self._download_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self._download_btn)

        layout.addLayout(btn_layout)

    def _browse_path(self):
        """选择模型存储目录"""
        path = QFileDialog.getExistingDirectory(
            self, "选择模型存储目录", self._path_entry.text()
        )
        if path:
            self._path_entry.setText(path)

    def _start_download(self):
        """开始下载模型"""
        self._model_dir = self._path_entry.text().strip()
        if not self._model_dir:
            QMessageBox.warning(self, "提示", "请选择模型存储目录")
            return

        # 保存路径到配置
        if self._config:
            self._config.set("model_cache_dir", self._model_dir)
            self._config.save()

        # 显示进度条
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_label.setVisible(True)
        self._progress_label.setText("准备下载...")
        self._download_btn.setEnabled(False)
        self._download_btn.setText("下载中...")

        # 启动下载线程
        self._worker = ModelDownloadWorker(self._model_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, percent, message):
        """更新进度"""
        self._progress_bar.setValue(percent)
        self._progress_label.setText(message)

    def _on_finished(self, success, message):
        """下载完成"""
        self._progress_label.setText(message)
        if success:
            QMessageBox.information(self, "完成", message)
            self.accept()
        else:
            QMessageBox.critical(self, "错误", message)
            self._download_btn.setEnabled(True)
            self._download_btn.setText("开始下载")

    def _skip(self):
        """跳过下载"""
        # 保存路径到配置（即使不下载）
        if self._config:
            self._config.set("model_cache_dir", self._model_dir)
            self._config.set("first_launch", False)
            self._config.save()
        self.accept()


def check_first_launch(config):
    """检查是否首次启动"""
    if config is None:
        return True
    return config.get("first_launch", True)


def show_first_launch_dialog(parent=None, config=None):
    """显示首次启动引导"""
    if not check_first_launch(config):
        return

    dialog = FirstLaunchDialog(parent, config)
    dialog.exec()

    # 标记已完成首次启动
    if config:
        config.set("first_launch", False)
        config.save()
