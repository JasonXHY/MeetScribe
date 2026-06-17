"""
首次启动引导弹窗（PySide6 版本，UI-011）

多步向导，依次引导用户完成：
1. 模型检查/下载——调用真实 ``ModelManager.download_all_missing``（带进度回调）。
2. VB-Audio Cable 检测与安装指引——检测是否已安装，未装时给出下载链接。
3. API Key 配置——可填入并保存到 config，或跳过。

每一步均可跳过，跳过不阻塞进入主界面；完成或跳过后置位
``first_launch=false``，下次不再弹出。
"""

import logging
import webbrowser

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QWidget, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QThread

from gui.styles import (
    C_BORDER, C_ACCENT, C_BTN_HOVER,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY, MODEL_CACHE_DIR
)
from transcriber import ModelManager

logger = logging.getLogger("MeetScribe")

# VB-Audio Cable 官方下载地址
VB_CABLE_URL = "https://vb-audio.com/Cable/"


def detect_vb_cable():
    """检测系统是否已安装 VB-Audio Cable 虚拟声卡。

    尽力而为：通过 pyaudio 枚举音频设备，匹配 ``VB-Audio`` / ``CABLE``。
    任何异常（如未装 pyaudio）一律视为未安装并返回 ``False``。

    Returns:
        bool: 已检测到 VB-Audio Cable 返回 True，否则 False。
    """
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                name = p.get_device_info_by_index(i).get("name", "")
                if "VB-Audio" in name or "CABLE" in name:
                    return True
            return False
        finally:
            p.terminate()
    except Exception as e:
        logger.debug(f"VB-Cable 检测失败（视为未安装）: {e}")
        return False


class ModelDownloadWorker(QThread):
    """模型下载工作线程——调用真实 ``ModelManager.download_all_missing``。"""

    progress = Signal(int, str)   # percent, message
    finished = Signal(bool, str)  # success, message

    def __init__(self, cache_dir):
        super().__init__()
        self._cache_dir = cache_dir

    def run(self):
        """在后台线程内执行真实下载（不再 time.sleep 模拟）。"""
        try:
            manager = ModelManager(self._cache_dir)

            def _cb(msg):
                # ModelManager 只回传文本进度，这里以不确定进度（0）转发
                self.progress.emit(0, str(msg))

            self.progress.emit(0, "正在检查模型...")
            success, message = manager.download_all_missing(progress_callback=_cb)
            self.progress.emit(100 if success else 0, message)
            self.finished.emit(success, message)
        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            self.finished.emit(False, f"下载失败: {e}")


class FirstLaunchDialog(QDialog):
    """首次启动引导弹窗（三步向导）。"""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用侧耳倾听")
        self.setMinimumSize(540, 460)
        self.setModal(True)

        self._config = config
        self._model_dir = MODEL_CACHE_DIR
        self._worker = None
        self._vb_installed = detect_vb_cable()

        self._build()

    # ── 构建 UI ──────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("欢迎使用侧耳倾听")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 22px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        self._step_hint = QLabel("")
        self._step_hint.setAlignment(Qt.AlignCenter)
        self._step_hint.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        layout.addWidget(self._step_hint)

        # 步骤页容器
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_model_step())
        self._stack.addWidget(self._build_vb_step())
        self._stack.addWidget(self._build_api_step())
        layout.addWidget(self._stack, 1)

        # 底部导航按钮
        btn_layout = QHBoxLayout()
        self._skip_all_btn = QPushButton("跳过引导")
        self._skip_all_btn.setFixedHeight(36)
        self._skip_all_btn.setStyleSheet(self._ghost_btn_style())
        self._skip_all_btn.setCursor(Qt.PointingHandCursor)
        self._skip_all_btn.clicked.connect(self.skip_all)
        btn_layout.addWidget(self._skip_all_btn)

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

    def _build_model_step(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        desc = QLabel("首次使用需要下载语音识别模型（约 2GB）。\n"
                      "点击「开始下载」联网获取，或跳过稍后在设置页下载。")
        desc.setWordWrap(True)
        desc.setStyleSheet(self._desc_style())
        v.addWidget(desc)

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

        self._download_btn = QPushButton("开始下载")
        self._download_btn.setFixedSize(140, 36)
        self._download_btn.setStyleSheet(self._accent_btn_style())
        self._download_btn.setCursor(Qt.PointingHandCursor)
        self._download_btn.clicked.connect(self.start_download)
        v.addWidget(self._download_btn, 0, Qt.AlignLeft)

        v.addStretch()
        return page

    def _build_vb_step(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        self._vb_status = QLabel("")
        self._vb_status.setWordWrap(True)
        self._vb_status.setStyleSheet(self._desc_style())
        v.addWidget(self._vb_status)

        self._vb_link_btn = QPushButton("打开 VB-Audio Cable 下载页")
        self._vb_link_btn.setFixedHeight(36)
        self._vb_link_btn.setStyleSheet(self._ghost_btn_style())
        self._vb_link_btn.setCursor(Qt.PointingHandCursor)
        self._vb_link_btn.clicked.connect(self._open_vb_link)
        v.addWidget(self._vb_link_btn, 0, Qt.AlignLeft)

        v.addStretch()
        self._refresh_vb_status()
        return page

    def _build_api_step(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        desc = QLabel("可在此填入云端 AI 摘要所需的 API Key（也可留空，稍后在设置页配置）。")
        desc.setWordWrap(True)
        desc.setStyleSheet(self._desc_style())
        v.addWidget(desc)

        self._api_entry = QLineEdit()
        self._api_entry.setEchoMode(QLineEdit.Password)
        self._api_entry.setPlaceholderText("sk-...")
        self._api_entry.setStyleSheet(f"""
            QLineEdit {{ border: 1px solid {C_BORDER}; border-radius: 6px;
                padding: 8px 12px; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        v.addWidget(self._api_entry)

        v.addStretch()
        return page

    # ── 样式辅助 ──────────────────────────────────────────────

    def _desc_style(self):
        return (f"QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY}; "
                f"font-size: 14px; line-height: 1.6; }}")

    def _accent_btn_style(self):
        return (f"QPushButton {{ background-color: {C_ACCENT}; color: white; "
                f"border: none; border-radius: 6px; font-family: {FONT_FAMILY}; "
                f"font-size: 13px; font-weight: bold; padding: 0 16px; }}"
                f"QPushButton:hover {{ background-color: {C_BTN_HOVER}; }}"
                f"QPushButton:disabled {{ background-color: {C_TXT3}; }}")

    def _ghost_btn_style(self):
        return (f"QPushButton {{ background-color: transparent; color: {C_TXT2}; "
                f"border: 1px solid {C_BORDER}; border-radius: 6px; "
                f"font-family: {FONT_FAMILY}; font-size: 12px; padding: 0 16px; }}"
                f"QPushButton:hover {{ background-color: #F5F5F5; }}")

    # ── 状态/导航 ─────────────────────────────────────────────

    def step_count(self):
        """向导步骤总数。"""
        return self._stack.count()

    def is_vb_cable_installed(self):
        """返回 VB-Audio Cable 检测结果。"""
        return self._vb_installed

    def _refresh_vb_status(self):
        """根据检测结果更新 VB-Cable 步骤的提示与按钮。"""
        if self._vb_installed:
            self._vb_status.setText("已检测到 VB-Audio Cable 虚拟声卡，可录制系统声音。")
            self._vb_link_btn.setVisible(False)
        else:
            self._vb_status.setText(
                "未检测到 VB-Audio Cable。若需录制系统/会议声音，建议安装该虚拟声卡。\n"
                "安装完成后重启本应用即可生效。"
            )
            self._vb_link_btn.setVisible(True)

    def _open_vb_link(self):
        """打开 VB-Audio Cable 官方下载页。"""
        try:
            webbrowser.open(VB_CABLE_URL)
        except Exception as e:
            logger.warning(f"打开 VB-Cable 下载页失败: {e}")

    def _update_nav(self):
        """更新底部导航提示与按钮文案。"""
        idx = self._stack.currentIndex()
        total = self._stack.count()
        self._step_hint.setText(f"第 {idx + 1} / {total} 步")
        self._next_btn.setText("完成" if idx == total - 1 else "下一步")

    def _on_next(self):
        """进入下一步；在 API 步骤保存 Key；最后一步触发完成。"""
        idx = self._stack.currentIndex()
        # 离开 API Key 步骤时尝试保存
        if idx == 2:
            self.save_api_key()
        if idx >= self._stack.count() - 1:
            self.finish_wizard()
            return
        self._stack.setCurrentIndex(idx + 1)
        self._update_nav()

    # ── 步骤动作 ──────────────────────────────────────────────

    def start_download(self):
        """启动真实模型下载（后台线程）。"""
        if self._config:
            self._config.set("model_cache_dir", self._model_dir)

        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # 不确定进度
        self._progress_label.setVisible(True)
        self._progress_label.setText("准备下载...")
        self._download_btn.setEnabled(False)
        self._download_btn.setText("下载中...")

        self._worker = ModelDownloadWorker(self._model_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.start()

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

    def set_api_key_text(self, text):
        """供测试/外部设置 API Key 输入框内容。"""
        self._api_entry.setText(text)

    def save_api_key(self):
        """将输入的 API Key 写入 config（``ai_user_api_key``）；留空则不写。"""
        key = self._api_entry.text().strip()
        if key and self._config:
            self._config.set("ai_user_api_key", key)

    def _mark_done(self):
        """置位 first_launch=false 并保存。"""
        if self._config:
            self._config.set("model_cache_dir", self._model_dir, save=False)
            self._config.set("first_launch", False)
            self._config.save()

    def finish_wizard(self):
        """完成向导：置位 first_launch=false 并关闭。"""
        self._mark_done()
        self.accept()

    def skip_all(self):
        """跳过整个引导：仍置位 first_launch=false，不阻塞进入主界面。"""
        self._mark_done()
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
