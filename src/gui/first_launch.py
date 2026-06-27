"""
首次启动引导弹窗（v1.0）

两步向导：
1. 内测版本提醒 + API Key 选择（使用内置 / 自己配置）
2. 模型下载引导（可跳过）

每个步骤均可跳过，跳过不阻塞进入主界面；完成或跳过后置位
``first_launch=false``，下次不再弹出。
"""

import logging
import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QWidget
)
from PySide6.QtCore import Qt, Signal, QThread

from gui.styles import (
    C_BORDER, C_ACCENT, C_BTN_HOVER, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY, MODEL_CACHE_DIR
)

logger = logging.getLogger("MeetScribe")


class ModelDownloadWorker(QThread):
    """模型下载工作线程"""

    progress = Signal(int, str)   # percent, message
    finished = Signal(bool, str)  # success, message

    def __init__(self, cache_dir):
        super().__init__()
        self._cache_dir = cache_dir

    def run(self):
        try:
            from transcriber import ModelManager
            manager = ModelManager(self._cache_dir)

            def _cb(msg):
                self.progress.emit(0, str(msg))

            self.progress.emit(0, "正在检查模型...")
            success, message = manager.download_all_missing(progress_callback=_cb)
            self.progress.emit(100 if success else 0, message)
            self.finished.emit(success, message)
        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            self.finished.emit(False, f"下载失败: {e}")


class FirstLaunchDialog(QDialog):
    """首次启动引导弹窗（两步向导）。"""

    # 信号：通知外部使用内置 API 或跳转设置
    use_builtin_api = Signal()
    go_to_settings = Signal()
    # 后台下载启动信号：传递 worker 实例给外部管理
    background_download_started = Signal(object)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用侧耳倾听")
        self.setMinimumSize(500, 480)
        self.setModal(True)

        self._config = config
        self._models_packaged = self._check_models_packaged()
        self._model_dir = MODEL_CACHE_DIR
        self._worker = None

        self._build()

    def _check_models_packaged(self):
        """检查模型是否已打包到安装目录"""
        if getattr(sys, 'frozen', False):
            model_dir = os.path.join(os.path.dirname(sys.executable), 'models')
            return os.path.exists(model_dir)
        return False

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        # 标题
        title = QLabel("欢迎使用「侧耳倾听」")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 22px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        # 副标题
        self._subtitle = QLabel("内测版本 · v1.0")
        self._subtitle.setAlignment(Qt.AlignCenter)
        self._subtitle.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        layout.addWidget(self._subtitle)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
        layout.addWidget(sep)

        # 步骤页容器
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_beta_step())
        if not self._models_packaged:
            self._stack.addWidget(self._build_model_step())
        layout.addWidget(self._stack, 1)

        # 底部到期提醒
        self._expiry_label = QLabel("⚠️ 内置 API 将于 2026年7月31日 到期")
        self._expiry_label.setAlignment(Qt.AlignCenter)
        self._expiry_label.setStyleSheet(f"""
            QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY};
                font-size: 11px; }}
        """)
        layout.addWidget(self._expiry_label)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self._skip_btn = QPushButton("跳过引导")
        self._skip_btn.setFixedHeight(36)
        self._skip_btn.setStyleSheet(self._ghost_btn_style())
        self._skip_btn.setCursor(Qt.PointingHandCursor)
        self._skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self._skip_btn)

        btn_layout.addStretch()

        self._next_btn = QPushButton("下一步")
        self._next_btn.setFixedSize(120, 36)
        self._next_btn.setStyleSheet(self._accent_btn_style())
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self._next_btn)

        layout.addLayout(btn_layout)

        self._stack.setCurrentIndex(0)
        self._update_nav()

    # ── Step 1: 内测提醒 + API 选择 ──────────────────────

    def _build_beta_step(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        desc = QLabel(
            "感谢参与内测！本版本为测试版，\n"
            "AI 摘要和纠错功能使用开发者的云端 API。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(self._desc_style())
        v.addWidget(desc)

        warning = QLabel(
            "⚠️ 内置 API 将于 2026年7月31日 到期关闭，\n"
            "届时需在设置中配置自己的 API Key。"
        )
        warning.setWordWrap(True)
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet(f"""
            QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY};
                font-size: 13px; line-height: 1.6; }}
        """)
        v.addWidget(warning)

        v.addSpacing(8)

        # 用开发者的 API
        self._builtin_btn = QPushButton("🚀  用开发者的 API，先试试看")
        self._builtin_btn.setFixedHeight(44)
        self._builtin_btn.setStyleSheet(self._primary_btn_style())
        self._builtin_btn.setCursor(Qt.PointingHandCursor)
        self._builtin_btn.clicked.connect(self._on_use_builtin)
        v.addWidget(self._builtin_btn)

        # 自己配置 API
        self._custom_btn = QPushButton("⚙️  我有 API Key，自己配置")
        self._custom_btn.setFixedHeight(44)
        self._custom_btn.setStyleSheet(self._ghost_btn_style())
        self._custom_btn.setCursor(Qt.PointingHandCursor)
        self._custom_btn.clicked.connect(self._on_setup_own)
        v.addWidget(self._custom_btn)

        v.addStretch()
        return page

    # ── Step 2: 模型下载 ─────────────────────────────────

    def _build_model_step(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        desc = QLabel(
            "首次使用需要下载语音识别模型（约 2GB）。\n"
            "使用国内 ModelScope 源，速度有保障。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(self._desc_style())
        v.addWidget(desc)

        # 模型列表
        models_info = QLabel(
            "模型列表：\n"
            "  · SenseVoiceSmall (896MB) — 语音识别\n"
            "  · ct-punc (1132MB) — 标点恢复\n"
            "  · CAM++ (28MB) — 说话人分离\n"
            "  · fsmn-vad (4MB) — 语音端点检测"
        )
        models_info.setStyleSheet(f"""
            QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY};
                font-size: 12px; line-height: 1.6; background-color: #F9FAFB;
                border: 1px solid {C_BORDER}; border-radius: 6px; padding: 12px; }}
        """)
        v.addWidget(models_info)

        # 进度条
        from PySide6.QtWidgets import QProgressBar
        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background-color: #E0E0E0;
                border-radius: 3px; height: 8px; text-align: center; }}
            QProgressBar::chunk {{ background-color: {C_ACCENT}; border-radius: 3px; }}
        """)
        self._progress_bar.setVisible(False)
        v.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        self._progress_label.setVisible(False)
        v.addWidget(self._progress_label)

        # 下载按钮
        self._download_btn = QPushButton("开始下载")
        self._download_btn.setFixedSize(140, 36)
        self._download_btn.setStyleSheet(self._accent_btn_style())
        self._download_btn.setCursor(Qt.PointingHandCursor)
        self._download_btn.clicked.connect(self._start_download)

        self._bg_download_btn = QPushButton("后台下载，先去设置")
        self._bg_download_btn.setFixedSize(160, 36)
        self._bg_download_btn.setStyleSheet(self._ghost_btn_style())
        self._bg_download_btn.setCursor(Qt.PointingHandCursor)
        self._bg_download_btn.clicked.connect(self._start_background_download)

        dl_btn_layout = QHBoxLayout()
        dl_btn_layout.addWidget(self._download_btn)
        dl_btn_layout.addWidget(self._bg_download_btn)
        dl_btn_layout.addStretch()
        v.addLayout(dl_btn_layout)

        v.addStretch()
        return page

    # ── 样式 ─────────────────────────────────────────────

    def _desc_style(self):
        return (f"QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY}; "
                f"font-size: 14px; line-height: 1.6; }}")

    def _accent_btn_style(self):
        return (f"QPushButton {{ background-color: {C_ACCENT}; color: white; "
                f"border: none; border-radius: 6px; font-family: {FONT_FAMILY}; "
                f"font-size: 13px; font-weight: bold; padding: 0 16px; }}"
                f"QPushButton:hover {{ background-color: {C_BTN_HOVER}; }}"
                f"QPushButton:disabled {{ background-color: {C_TXT3}; }}")

    def _primary_btn_style(self):
        return (f"QPushButton {{ background-color: {C_ACCENT}; color: white; "
                f"border: none; border-radius: 8px; font-family: {FONT_FAMILY}; "
                f"font-size: 14px; font-weight: bold; padding: 0 16px; }}"
                f"QPushButton:hover {{ background-color: {C_BTN_HOVER}; }}")

    def _ghost_btn_style(self):
        return (f"QPushButton {{ background-color: transparent; color: {C_TXT2}; "
                f"border: 1px solid {C_BORDER}; border-radius: 6px; "
                f"font-family: {FONT_FAMILY}; font-size: 12px; padding: 0 16px; }}"
                f"QPushButton:hover {{ background-color: #F5F5F5; }}")

    # ── 导航 ─────────────────────────────────────────────

    def _update_nav(self):
        idx = self._stack.currentIndex()
        total = self._stack.count()
        self._next_btn.setText("完成" if idx == total - 1 else "下一步")
        self._subtitle.setText(
            f"内测版本 · v1.0 — 第 {idx + 1}/{total} 步"
        )

    def step_count(self):
        """向导步骤总数。"""
        return self._stack.count()

    def _on_next(self):
        idx = self._stack.currentIndex()
        if idx >= self._stack.count() - 1:
            self._finish()
            return
        self._stack.setCurrentIndex(idx + 1)
        self._update_nav()

    def _on_skip(self):
        self._finish()

    # ── Step 1 动作 ──────────────────────────────────────

    def _on_use_builtin(self):
        """使用内置 API Key"""
        if self._config:
            self._config.set("ai_user_api_key", "")
        self.use_builtin_api.emit()
        if self._stack.count() > 1:
            self._stack.setCurrentIndex(1)
            self._update_nav()
        else:
            self._finish()

    def _on_setup_own(self):
        """自己配置 API Key → 跳转设置页"""
        self.go_to_settings.emit()
        self._finish()

    # ── Step 2 动作 ──────────────────────────────────────

    def _start_download(self):
        """启动模型下载（阻塞等待）"""
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)
        self._progress_label.setVisible(True)
        self._progress_label.setText("准备下载...")
        self._download_btn.setEnabled(False)
        self._download_btn.setText("下载中...")
        self._bg_download_btn.setEnabled(False)

        self._worker = ModelDownloadWorker(self._model_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.start()

    def _start_background_download(self):
        """启动模型下载（后台运行，立即关闭弹窗）"""
        worker = ModelDownloadWorker(self._model_dir)
        self.background_download_started.emit(worker)
        self._finish()

    def _on_progress(self, percent, message):
        if percent > 0:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(percent)
        self._progress_label.setText(message)

    def _on_download_finished(self, success, message):
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100 if success else 0)
        self._progress_label.setText(message)
        self._download_btn.setEnabled(True)
        self._download_btn.setText("重新下载" if not success else "下载完成")

    # ── 完成 ─────────────────────────────────────────────

    def _finish(self):
        if self._config:
            self._config.set("first_launch", False)
            self._config.save()
        self.accept()


def check_first_launch(config):
    """检查是否首次启动。"""
    if config is None:
        return True
    return config.get("first_launch", True)


def show_first_launch_dialog(parent=None, config=None):
    """显示首次启动引导（非首次启动时直接返回）。"""
    if not check_first_launch(config):
        return

    dialog = FirstLaunchDialog(parent, config)
    dialog.exec()

    # 兜底：即使对话框被强制关闭，也标记已完成首次启动
    if config:
        config.set("first_launch", False)
        config.save()
