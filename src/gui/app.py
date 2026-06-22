"""
侧耳倾听 主窗口（PySide6 版本）
"""

import os
import sys
import logging
import queue
import traceback
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QFrame, QTextEdit, QStatusBar
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_TXT1, C_TXT2, C_TXT3,
    FONT_FAMILY, ICON_ICO, APP_VERSION, MAIN_STYLESHEET, OUTPUT_FORMATS,
    DEFAULT_DEBOUNCE_MS,
)
from gui.topbar import TopBar
from gui.recording_bar import RecordingBar
from gui.home_page import HomePage
from gui.settings_page import SettingsPage
from gui.voiceprint_page import VoiceprintPage
from gui.transcription import TranscriptionHandler
from gui.first_launch import check_first_launch, show_first_launch_dialog

# 导入业务逻辑模块
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
from config import Config
from file_manager import FileManager
from unified_recorder import UnifiedRecorder

logger = logging.getLogger("MeetScribe")


class GUILogHandler(logging.Handler):
    """将日志输出到 GUI 日志区域（线程安全，使用队列）"""

    def __init__(self):
        super().__init__()
        self._log_area = None
        self._log_queue = queue.Queue()
        self._timer = None

    def set_log_area(self, log_area):
        self._log_area = log_area

    def start_polling(self):
        """启动定时轮询队列"""
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._poll_queue)
            self._timer.start(100)  # 100ms 轮询
            logger.debug("GUILogHandler polling started")

    def _poll_queue(self):
        """轮询日志队列"""
        try:
            while not self._log_queue.empty():
                msg = self._log_queue.get_nowait()
                if self._log_area:
                    # 日志过滤：只显示用户关心的内容
                    from gui.home_page import USER_FRIENDLY_KEYWORDS
                    if not any(keyword in msg for keyword in USER_FRIENDLY_KEYWORDS):
                        continue
                    self._log_area.appendPlainText(msg)
        except queue.Empty:
            pass
        except Exception as e:
            logger.debug(f"GUILogHandler poll error: {e}")

    def emit(self, record):
        msg = self.format(record)
        self._log_queue.put(msg)


class MeetScribeApp(QMainWindow):
    """主窗口"""

    # 跨线程信号：后台线程通过此信号通知主线程执行操作
    stop_complete_signal = Signal(list)

    def __init__(self):
        try:
            super().__init__()
            logger.debug("QMainWindow.__init__ done")

            self.setWindowTitle("侧耳倾听")
            self.setMinimumSize(1000, 650)
            self.resize(1060, 720)  # 初始窗口尺寸

            # 设置图标
            if os.path.exists(ICON_ICO):
                self.setWindowIcon(QIcon(ICON_ICO))
                logger.debug("Icon set")

            # 应用全局样式
            self.setStyleSheet(MAIN_STYLESHEET)
            logger.debug("Stylesheet applied")

            # Win11 DWM 圆角
            if sys.platform == "win32":
                try:
                    from ctypes import windll, c_int, byref, sizeof
                    hwnd = int(self.winId())
                    windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 33, byref(c_int(2)), sizeof(c_int))
                except (OSError, AttributeError, ValueError):
                    pass

            # 日志 handler
            self._gui_log_handler = GUILogHandler()

            # 初始化业务逻辑
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.json")
            self.config = Config(config_path)
            self.file_manager = FileManager()
            logger.debug("Config and FileManager initialized")

            # 初始化录音模块
            recording_dir = self.config.get("recording_dir", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings"))
            os.makedirs(recording_dir, exist_ok=True)
            self.recorder = UnifiedRecorder(
                save_dir=recording_dir,
                use_vb_cable=self.config.get("use_vb_cable", False),
            )
            self._recording = False
            self._paused = False
            self._recording_mode = self.config.get("recording_mode", "dual")

            # 注册录音回调
            self.recorder.on_state_change = self._on_recorder_state_change
            self.recorder.on_save = self._on_recorder_save
            self.recorder.on_stop_complete = self._on_recorder_stop_complete
            # 信号槽连接：后台线程通过信号安全通知主线程
            self.stop_complete_signal.connect(self._handle_stop_complete)
            logger.debug("UnifiedRecorder initialized with callbacks")

            # 转写调度器
            self._transcription_handler = TranscriptionHandler(app=self)
            self._transcription_handler.log_message.connect(self._log)
            self._transcription_handler.transcription_done.connect(self._on_transcription_done)
            logger.debug("TranscriptionHandler created")

            # 初始化防抖计时器
            self._init_refresh_timer()

            # 中心部件
            central = QWidget()
            self.setCentralWidget(central)
            main_layout = QVBoxLayout(central)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            logger.debug("Central widget created")

            # 顶部导航栏
            self.topbar = TopBar()
            self.topbar.navigate_clicked.connect(self._on_navigate)
            main_layout.addWidget(self.topbar)
            logger.debug("TopBar created")

            # 页面堆栈
            self._pages = QStackedWidget()
            self._home_page = HomePage(app=self)
            self._settings_page = SettingsPage(config=self.config, log_callback=self._log)
            self._voiceprint_page = VoiceprintPage(app=self)
            logger.debug("VoiceprintPage created")

            self._pages.addWidget(self._home_page)
            self._pages.addWidget(self._voiceprint_page)
            self._pages.addWidget(self._settings_page)
            main_layout.addWidget(self._pages, 1)
            logger.debug("Pages stacked")

            # 连接设置变更信号
            self._settings_page.settings_changed.connect(self._on_settings_changed)

            # 连接转写调度器的刷新信号（需在 _home_page 创建后）
            self._transcription_handler.refresh_needed.connect(self._home_page.refresh_file_list)

            # 状态栏
            status_frame = QFrame()
            status_frame.setFixedHeight(28)
            status_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FAFAFA;
                    border: none;
                    border-top: 1px solid {C_BORDER};
                }}
            """)
            sb_layout = QHBoxLayout(status_frame)
            sb_layout.setContentsMargins(8, 0, 8, 0)

            self._status_lbl = QLabel("就绪")
            self._status_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; border: none; background: transparent;")
            sb_layout.addWidget(self._status_lbl)

            sb_layout.addStretch()

            engine_lbl = QLabel("SenseVoice + CAM++ + ct-punc")
            engine_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; border: none; background: transparent;")
            sb_layout.addWidget(engine_lbl)

            main_layout.addWidget(status_frame)
            logger.debug("StatusBar created")

            # 连接日志 handler 并启动轮询
            self._gui_log_handler.set_log_area(self._home_page.get_log_area())
            self._gui_log_handler.start_polling()
            logger.debug("Log handler connected")

            # 文件变更监听（防抖刷新）
            self.file_manager.add_listener(self._on_file_changed)

            # 默认显示主页
            self.topbar.highlight("home")
            logger.debug("Home page highlighted")

            # 恢复配置
            self._restore_config()

            # 刷新文件列表
            self._home_page.refresh_file_list()

            # 首次启动引导
            if check_first_launch(self.config):
                QTimer.singleShot(500, self._show_first_launch)

            # 窗口关闭处理
            self.destroyed.connect(self._on_destroy)

            # 安全检查定时器 - 监控应用状态
            self._safety_timer = QTimer()
            self._safety_timer.timeout.connect(self._safety_check)
            self._safety_timer.start(5000)  # 每5秒检查一次

            logger.info("MeetScribeApp initialized (PySide6)")

        except Exception as e:
            logger.critical(f"MeetScribeApp init failed: {e}")
            logger.critical(traceback.format_exc())
            raise

    def _safety_check(self):
        """安全检查 - 防止意外崩溃"""
        try:
            if not self.isVisible():
                logger.debug("Window not visible, skipping check")
                return
            # 检查关键组件是否存在
            if not hasattr(self, '_home_page') or self._home_page is None:
                logger.warning("HomePage is None!")
            if not hasattr(self, '_pages') or self._pages is None:
                logger.warning("Pages widget is None!")
        except Exception as e:
            logger.error(f"Safety check error: {e}")

    def _show_first_launch(self):
        """显示首次启动引导"""
        from gui.first_launch import FirstLaunchDialog, check_first_launch
        if not check_first_launch(self.config):
            return

        dialog = FirstLaunchDialog(self, self.config)

        def on_use_builtin():
            self._log("已使用内置 API Key")

        def on_go_to_settings():
            self._on_navigate("settings")

        dialog.use_builtin_api.connect(on_use_builtin)
        dialog.go_to_settings.connect(on_go_to_settings)
        dialog.exec()

        # 兜底：即使对话框被强制关闭，也标记已完成首次启动
        self.config.set("first_launch", False)
        self.config.save()

    def _on_settings_changed(self):
        """设置变更回调"""
        # 重新加载配置到各组件
        self._recording_mode = self.config.get("recording_mode", "dual")
        self._log("设置已更新")

    # ══════════════════════════════════════════════════════════
    #  File Change Debounce
    # ══════════════════════════════════════════════════════════

    def _init_refresh_timer(self):
        """初始化防抖计时器"""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh)

    def _on_file_changed(self, *_):
        """文件变更监听（防抖 200ms）"""
        self._refresh_timer.start(DEFAULT_DEBOUNCE_MS)

    def _do_refresh(self):
        """实际执行刷新"""
        self._home_page.refresh_file_list()

    def _refresh_file_list(self):
        """刷新文件列表 UI（公共方法）"""
        self._home_page.refresh_file_list()

    def _on_navigate(self, page_key):
        """页面切换"""
        try:
            page_map = {
                "home": 0,
                "voiceprint": 1,
                "settings": 2,
            }
            index = page_map.get(page_key, 0)
            self._pages.setCurrentIndex(index)
            self.topbar.highlight(page_key)
            logger.debug(f"Navigated to {page_key}")
        except (KeyError, AttributeError, RuntimeError) as e:
            logger.error(f"Navigation error: {e}")

    def _log(self, msg):
        """添加日志"""
        self._append_log(msg)

    def _append_log(self, msg):
        """线程安全的日志追加（仅显示用户关心的内容）"""
        try:
            from gui.home_page import USER_FRIENDLY_KEYWORDS
            if not any(kw in msg for kw in USER_FRIENDLY_KEYWORDS):
                return
            log_area = self._home_page.get_log_area() if self._home_page else None
            if log_area:
                log_area.appendPlainText(msg)
        except (RuntimeError, AttributeError) as e:
            logger.debug(f"Log append error: {e}")

    def _set_status(self, msg):
        """设置状态栏"""
        try:
            self._status_lbl.setText(msg)
        except (RuntimeError, AttributeError) as e:
            logger.debug(f"Status set error: {e}")

    # ══════════════════════════════════════════════════════════
    #  Recorder Callbacks
    # ══════════════════════════════════════════════════════════

    def _on_recorder_state_change(self, is_recording, is_paused):
        """录音状态变更回调"""
        self._recording = is_recording
        self._paused = is_paused
        recording_bar = self._home_page.get_recording_bar()
        if recording_bar:
            recording_bar.update_state(is_recording, is_paused)

    def _on_recorder_save(self, file_path, duration_s=None):
        """录音保存回调（后台线程调用，仅记录日志）"""
        logger.info(f"Audio file saved: {file_path} (duration={duration_s:.1f}s)" if duration_s else f"Audio file saved: {file_path}")

    def _on_recorder_stop_complete(self, saved_files):
        """后台保存完成后回调（从后台线程调用，通过信号安全通知主线程）"""
        self.stop_complete_signal.emit(saved_files)

    def _handle_stop_complete(self, saved_files):
        """录音停止后处理：添加文件到列表、合并双轨、询问转写（主线程执行）"""
        for saved in saved_files:
            self._log(f"录音已保存: {os.path.basename(saved)}")
            existing = self.file_manager.get_file(saved)
            if not existing:
                self.file_manager.add_file(saved)

        if saved_files:
            if len(saved_files) == 2:
                # 双轨录音
                try:
                    from dual_track_merge import find_dual_track_pair
                    pair = find_dual_track_pair(saved_files[0])
                    if pair:
                        source_names = [os.path.basename(fp) for fp in pair]
                        merged_display = "、".join(source_names)
                        self.file_manager.create_merged_group(list(pair), merged_display)
                        self._log("双轨录音已合并显示")
                    else:
                        self._log("双轨录音完成，但未找到配对文件")
                except (OSError, ValueError, KeyError) as e:
                    self._log(f"双轨合并处理失败: {e}")

            # 刷新文件列表
            self._home_page.refresh_file_list()

            # 录音完成后询问是否转写
            QTimer.singleShot(300, lambda: self._home_page.ask_transcribe_after_record(saved_files[0]))

    # ══════════════════════════════════════════════════════════
    #  Transcription Callbacks
    # ══════════════════════════════════════════════════════════

    def _on_transcription_done(self, success_count=0, fail_count=0):
        """转写完成回调"""
        self._log(f"转写完成: 成功 {success_count} 个, 失败 {fail_count} 个")
        self._set_status("转写完成")

        # 发送系统通知 + 弹窗
        if success_count > 0 or fail_count > 0:
            self._send_notification(
                "转写完成",
                f"成功: {success_count} 个文件\n失败: {fail_count} 个文件"
            )
            from PySide6.QtWidgets import QMessageBox
            msg = f"转写完成\n\n成功: {success_count} 个文件\n失败: {fail_count} 个文件"
            if success_count > 0:
                msg += f"\n\n结果已保存到输出目录"
            QMessageBox.information(self, "转写完成", msg)

        # 刷新文件列表（只调用一次）
        self._home_page.refresh_file_list()

    def _send_notification(self, title, message):
        """发送系统通知"""
        if not self.config.get("enable_notification", True):
            return
        try:
            if sys.platform == "win32":
                import subprocess
                # 转义单引号防止注入
                safe_title = title.replace("'", "''")
                safe_message = message.replace("'", "''")
                ps_script = (
                    f"[Windows.UI.Notifications.ToastNotificationManager, "
                    f"Windows.UI.Notifications, ContentType = WindowsRuntime] > $null\n"
                    f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                    f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02)\n"
                    f"$textNodes = $template.GetElementsByTagName('text')\n"
                    f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) > $null\n"
                    f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_message}')) > $null\n"
                    f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template)\n"
                    f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('侧耳倾听').Show($toast)"
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"Failed to send notification: {e}")

    # ══════════════════════════════════════════════════════════
    #  Config Management
    # ══════════════════════════════════════════════════════════

    def _restore_config(self):
        """恢复配置"""
        # 恢复录音模式
        self._recording_mode = self.config.get("recording_mode", "dual")
        # 恢复输出格式到 UI
        saved_fmt = self.config.get("output_format", "md")
        fmt_map = {v: k for k, v in OUTPUT_FORMATS.items()}
        fmt_label = fmt_map.get(saved_fmt, list(OUTPUT_FORMATS.keys())[0])
        self._home_page.set_format(fmt_label)

    def _save_current_config(self):
        """保存当前配置"""
        self.config.set("recording_mode", self._recording_mode)
        # 保存输出格式
        fmt_label = self._home_page.get_format()
        self.config.set("output_format", OUTPUT_FORMATS.get(fmt_label, "md"))
        self.config.save()

    def _get_speaker_names(self):
        """获取说话人名称映射"""
        return self.config.get("speaker_names", {})

    def get_output_dir(self):
        """获取输出目录"""
        return self.config.get("transcript_dir", os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "transcripts"))

    # ══════════════════════════════════════════════════════════
    #  Window Close
    # ══════════════════════════════════════════════════════════

    def _on_destroy(self):
        """窗口销毁时清理"""
        logger.info("MeetScribeApp destroyed")

    def closeEvent(self, event):
        """窗口关闭事件"""
        logger.info("MeetScribeApp closing")
        try:
            # 停止录音
            if self._recording:
                self.recorder.stop()
            # 保存配置
            self._save_current_config()
            # 保存文件历史
            self.file_manager._save_to_file()
            # 停止定时器
            if hasattr(self, '_safety_timer'):
                self._safety_timer.stop()
            if hasattr(self, '_gui_log_handler') and self._gui_log_handler._timer:
                self._gui_log_handler._timer.stop()
                self._gui_log_handler._timer = None
        except (RuntimeError, AttributeError) as e:
            logger.debug(f"Cleanup error: {e}")
        event.accept()
