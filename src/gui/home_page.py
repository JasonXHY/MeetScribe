"""
MeetScribe 主页（PySide6 版本）
录音条 + 文件列表 + 日志

已连接核心业务逻辑：
- 录音控制（开始/停止/暂停）
- 文件管理（添加/删除/清空）
- 转写队列管理
"""

import os
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_ERROR, C_TXT1, C_TXT2, C_TXT3,
    FONT_FAMILY, OUTPUT_FORMATS, DEFAULT_SPK_QUALITY,
)
from gui.recording_bar import RecordingBar
from gui.file_list_view import FileListView

logger = logging.getLogger("MeetScribe")

# FILE-001: 导入音频文件过滤器（含 spec 要求的全部格式 WAV/MP3/FLAC/M4A/AAC/OGG/WMA）
AUDIO_FILE_FILTER = (
    "音频文件 (*.wav *.mp3 *.m4a *.flac *.aac *.ogg *.oga *.opus *.wma);;"
    "所有文件 (*.*)"
)

USER_FRIENDLY_KEYWORDS = [
    "录音已开始", "录音已停止", "录音已保存",
    "转写完成", "转写已停止", "转写中", "正在转写",
    "添加文件", "删除文件", "文件已保存",
    "模型加载完成", "格式转换完成",
    "双轨录音", "模型检查通过", "开始转写",
    "Subprocess started", "转写任务已完成",
    "已加入转写队列", "队列中", "双轨合并",
]


class HomePage(QWidget):
    """主页：录音条 + 文件列表 + 日志"""

    def __init__(self, parent=None, app=None):
        super().__init__(parent)
        self._app = app
        self._record_start_time = None
        self._timer_id = None

        self._build()
        self._connect_signals()

    @property
    def _selected_files(self):
        return self._file_list_view.get_selected()

    # ══════════════════════════════════════════════════════════
    #  Public API (for cross-component access)
    # ══════════════════════════════════════════════════════════

    def get_log_area(self):
        """获取日志区域（供外部组件使用）"""
        return self._log_area

    def get_recording_bar(self):
        """获取录音控制栏（供外部组件使用）"""
        return self._recording_bar

    def get_format_combo(self):
        """获取格式选择框（供外部组件使用）"""
        return self._fmt_combo

    def set_format(self, fmt_label):
        """设置输出格式"""
        if self._fmt_combo:
            self._fmt_combo.setCurrentText(fmt_label)

    def get_format(self):
        """获取当前输出格式"""
        if self._fmt_combo:
            return self._fmt_combo.currentText()
        return "md"

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(6)

        # ── Title ──
        title_frame = QHBoxLayout()
        title_label = QLabel("主页")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT1};
                font-family: {FONT_FAMILY};
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        title_frame.addWidget(title_label)
        title_frame.addStretch()

        self._file_count_lbl = QLabel("")
        self._file_count_lbl.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        title_frame.addWidget(self._file_count_lbl)
        layout.addLayout(title_frame)

        # ── Recording Bar ──
        rec_card = QFrame()
        rec_card.setFixedHeight(56)
        rec_card.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        rec_layout = QVBoxLayout(rec_card)
        rec_layout.setContentsMargins(16, 10, 16, 10)

        initial_mode = "dual"
        if self._app and hasattr(self._app, 'config'):
            initial_mode = self._app.config.get("recording_mode", "mic")

        self._recording_bar = RecordingBar(initial_mode=initial_mode)
        rec_layout.addWidget(self._recording_bar)
        layout.addWidget(rec_card)

        # ── File Card ──
        file_card = QFrame()
        file_card.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(16, 12, 16, 12)
        file_layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_style_secondary = f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TXT2};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #F3F4F6;
            }}
            QPushButton:disabled {{
                color: {C_TXT3};
                border-color: #D1D5DB;
            }}
        """

        self._btn_add = QPushButton("添加文件")
        self._btn_add.setFixedSize(104, 32)
        self._btn_add.setProperty("cssClass", "primary")
        self._btn_add.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._btn_add)

        self._btn_transcribe = QPushButton("开始转写")
        self._btn_transcribe.setFixedSize(104, 32)
        self._btn_transcribe.setProperty("cssClass", "success")
        self._btn_transcribe.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._btn_transcribe)

        self._btn_ai_summary = QPushButton("AI 摘要")
        self._btn_ai_summary.setFixedSize(96, 32)
        self._btn_ai_summary.setProperty("cssClass", "purple")
        self._btn_ai_summary.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._btn_ai_summary)

        # 分隔线（AI 摘要和合并转写之间）
        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
        toolbar.addWidget(sep)

        self._btn_merge = QPushButton("合并转写")
        self._btn_merge.setFixedSize(104, 32)
        self._btn_merge.setStyleSheet(btn_style_secondary)
        self._btn_merge.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._btn_merge)

        self._btn_delete = QPushButton("删除选中")
        self._btn_delete.setFixedSize(80, 32)
        self._btn_delete.setStyleSheet(btn_style_secondary)
        self._btn_delete.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._btn_delete)

        self._btn_clear = QPushButton("清空列表")
        self._btn_clear.setFixedSize(80, 32)
        self._btn_clear.setStyleSheet(btn_style_secondary)
        self._btn_clear.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self._btn_clear)

        toolbar.addStretch()

        # 格式选择
        fmt_label = QLabel("输出格式")
        fmt_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2};
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        toolbar.addWidget(fmt_label)

        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(OUTPUT_FORMATS.keys())
        self._fmt_combo.setFixedWidth(130)
        self._fmt_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background-color: white;
            }}
        """)
        toolbar.addWidget(self._fmt_combo)

        file_layout.addLayout(toolbar)

        # File List View
        self._file_list_view = FileListView()
        file_layout.addWidget(self._file_list_view, 1)

        layout.addWidget(file_card, 1)

        # ── Log Area ──
        log_card = QFrame()
        log_card.setFixedHeight(120)
        log_card.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 8, 16, 8)
        log_layout.setSpacing(4)

        # 日志标题 + 清除按钮
        log_hdr = QHBoxLayout()
        log_label = QLabel("运行日志")
        log_label.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        log_hdr.addWidget(log_label)

        clear_btn = QPushButton("清除")
        clear_btn.setFixedSize(50, 22)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TXT3};
                border: none;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: #F0F0F0;
            }}
        """)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(lambda: self._log_area.clear())
        log_hdr.addWidget(clear_btn)
        log_hdr.addStretch()
        log_layout.addLayout(log_hdr)

        # 日志标题和内容之间的分隔线
        log_sep = QFrame()
        log_sep.setFixedHeight(1)
        log_sep.setStyleSheet(f"background-color: #F3F4F6; border: none;")
        log_layout.addWidget(log_sep)

        from PySide6.QtWidgets import QPlainTextEdit
        self._log_area = QPlainTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMaximumBlockCount(500)
        self._log_area.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: white;
                color: {C_TXT2};
                border: none;
                font-family: "Cascadia Code", Consolas, monospace;
                font-size: 11px;
            }}
        """)
        log_layout.addWidget(self._log_area)

        layout.addWidget(log_card)

    def _connect_signals(self):
        """连接信号槽"""
        # 录音控制
        self._recording_bar.start_clicked.connect(self._start_recording)
        self._recording_bar.stop_clicked.connect(self._stop_recording)
        self._recording_bar.pause_clicked.connect(self._toggle_pause)
        self._recording_bar.mode_changed.connect(self._on_rec_mode_change)

        # 工具栏按钮
        self._btn_add.clicked.connect(self._add_files)
        self._btn_transcribe.clicked.connect(self._start_transcription)
        self._btn_ai_summary.clicked.connect(self._open_summary_for_selected)
        self._btn_merge.clicked.connect(self._merge_transcribe)
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_clear.clicked.connect(self._clear_files)

        # 文件列表操作
        self._file_list_view.file_action.connect(self._on_file_action)
        self._file_list_view.file_selected.connect(self._on_file_select)

        # 转写调度器信号
        if self._app and hasattr(self._app, '_transcription_handler'):
            handler = self._app._transcription_handler
            handler.file_status_changed.connect(self._on_file_status_changed)
            handler.transcription_done.connect(self._on_transcription_done_handler)
            handler.progress_updated.connect(self._on_progress_updated)

    # ══════════════════════════════════════════════════════════
    #  Recording
    # ══════════════════════════════════════════════════════════

    def _start_recording(self):
        """开始录音"""
        try:
            if not self._app or not hasattr(self._app, 'recorder'):
                self._log("录音模块未初始化")
                return

            mode = self._recording_bar.get_mode()
            self._app.recorder.start(mode)
            # 不直接操作 app 状态，让回调统一管理
            self._recording_bar.update_state(recording=True, paused=False)
            self._record_start_time = datetime.now()
            self._start_timer()
            self._log(f"录音已开始 (模式: {mode})")
        except Exception as e:
            self._log(f"录音启动失败: {e}")
            self._recording_bar.update_state(recording=False, paused=False)

    def _stop_recording(self):
        """停止录音"""
        try:
            if self._app and hasattr(self._app, 'recorder'):
                self._app.recorder.stop()
            # 不直接操作 app 状态，让回调统一管理
            self._recording_bar.update_state(recording=False, paused=False)
            self._stop_timer()
            self._log("录音已停止")
        except Exception as e:
            self._log(f"停止录音失败: {e}")

    def _toggle_pause(self):
        """暂停/继续录音"""
        try:
            if self._app and hasattr(self._app, 'recorder'):
                if self._recording_bar._paused:
                    self._app.recorder.resume()
                    self._recording_bar.update_state(recording=True, paused=False)
                    self._log("录音已继续")
                else:
                    self._app.recorder.pause()
                    self._recording_bar.update_state(recording=True, paused=True)
                    self._log("录音已暂停")
        except Exception as e:
            self._log(f"暂停操作失败: {e}")

    def _on_rec_mode_change(self, mode):
        """录音模式切换"""
        if self._app and hasattr(self._app, 'config'):
            self._app.config.set("recording_mode", mode)
            self._app.config.save()
        self._log(f"录音模式切换为: {mode}")

    def update_recording_ui(self, is_recording, is_paused):
        if is_recording and not is_paused:
            self._recording_bar.update_state(recording=True, paused=False)
            if not self._record_start_time:
                self._record_start_time = datetime.now()
            self._start_timer()
            self._log("录音已开始")
        elif is_recording and is_paused:
            self._recording_bar.update_state(recording=True, paused=True)
            self._log("录音已暂停")
        else:
            self._recording_bar.update_state(recording=False, paused=False)
            self._record_start_time = None
            self._stop_timer()
            self._log("录音已停止")

    def _start_timer(self):
        """启动计时器"""
        if self._timer_id:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(500)

    def _stop_timer(self):
        """停止计时器"""
        if self._timer_id:
            self.killTimer(self._timer_id)
            self._timer_id = None

    def timerEvent(self, event):
        """定时器事件 - 更新录音时长"""
        if self._record_start_time and not self._recording_bar._paused:
            elapsed = (datetime.now() - self._record_start_time).total_seconds()
            self._recording_bar.update_timer(elapsed)

    def ask_transcribe_after_record(self, file_path):
        """录音完成后询问是否转写"""
        reply = QMessageBox.question(
            self, "录音完成",
            f"录音已保存: {os.path.basename(file_path)}\n\n是否立即开始转写?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._transcribe_single(file_path)
        # 确保文件列表在弹窗关闭后刷新
        self.refresh_file_list()

    # ══════════════════════════════════════════════════════════
    #  File Management
    # ══════════════════════════════════════════════════════════

    def _add_files(self):
        """添加音频文件"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择音频文件", "", AUDIO_FILE_FILTER
        )
        if not paths:
            return

        if self._app and hasattr(self._app, 'file_manager'):
            for p in paths:
                self._app.file_manager.add_file(p)
            self._log(f"已添加 {len(paths)} 个文件")
            self.refresh_file_list()
        else:
            self._log("文件管理器未初始化")

    def _confirm_delete(self, message):
        """删除确认弹窗，含"同时删除磁盘源文件"复选框（FILE-002）。

        Returns:
            (confirmed, delete_source): confirmed 为用户是否点击确认，
            delete_source 为是否勾选了删除磁盘源文件。
        """
        from PySide6.QtWidgets import QCheckBox

        box = QMessageBox(self)
        box.setWindowTitle("确认")
        box.setText(message)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        checkbox = QCheckBox("同时删除磁盘源文件")
        box.setCheckBox(checkbox)
        confirmed = box.exec() == QMessageBox.Yes
        return confirmed, checkbox.isChecked()

    def _delete_selected(self):
        """删除选中的文件"""
        selected = self._file_list_view.get_selected()
        if not selected:
            QMessageBox.information(self, "提示", "请先点击文件行选中一个或多个文件")
            return

        confirmed, delete_source = self._confirm_delete(
            f"从列表中移除选中的 {len(selected)} 个文件?"
        )
        if confirmed:
            if self._app and hasattr(self._app, 'file_manager'):
                for fp in list(selected):
                    self._app.file_manager.remove_file(fp, delete_source=delete_source)
                self._file_list_view.clear_selection()
                self._log(f"已删除 {len(selected)} 个文件")
                self.refresh_file_list()

    def _clear_files(self):
        """清空文件列表"""
        if self._app and hasattr(self._app, 'file_manager'):
            if self._app.file_manager.count == 0:
                return
            reply = QMessageBox.question(
                self, "确认", "清空所有文件列表?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._app.file_manager.clear_all()
                self._file_list_view.clear_selection()
                self._log("文件列表已清空")
                self.refresh_file_list()

    def _on_file_action(self, action, file_path):
        """处理文件操作"""
        action_map = {
            "preview": self._preview_result,
            "open_folder": self._open_folder,
            "transcribe": self._transcribe_single,
            "retry": self._retry_transcription,
            "export": self._export_result,
            "speaker": self._open_speaker_modal,
            "stop": self._stop_transcription,
            "delete": self._delete_single,
            "move_up": self._queue_move_up,
            "move_down": self._queue_move_down,
            "remove": self._queue_remove,
        }
        handler = action_map.get(action)
        if handler:
            handler(file_path)

    def _on_file_status_changed(self, file_path, status):
        """文件状态变更回调"""
        self.refresh_file_list()

    def _on_transcription_done_handler(self, success_count, fail_count):
        """转写完成回调（home_page 版本）"""
        self._btn_transcribe.setEnabled(True)
        self._btn_transcribe.setText("开始转写")
        self._recording_bar.stop_btn.setEnabled(False)
        self._recording_bar.stop_btn.setStyleSheet(f"""
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
        self.refresh_file_list()
        msg = f"转写完成: 成功 {success_count} 个"
        if fail_count > 0:
            msg += f", 失败 {fail_count} 个"
        self._log(msg)

    def _on_file_select(self, selected_paths):
        """文件选中回调"""
        # 更新文件计数
        files = self._app.file_manager.display_files if self._app and hasattr(self._app, 'file_manager') else []
        sel_count = len(selected_paths)
        total = len(files)
        if total == 0:
            self._file_count_lbl.setText("")
        else:
            count_text = f"共 {total} 个文件"
            if sel_count:
                count_text += f"，已选 {sel_count}"
            self._file_count_lbl.setText(count_text)

    def _on_progress_updated(self, progress):
        """转写进度更新"""
        if hasattr(progress, 'stage') and hasattr(progress, 'percent'):
            self._recording_bar.update_queue_status(f"转写中: {progress.stage} ({progress.percent}%)")

    def _preview_result(self, file_path):
        """预览转写结果"""
        from utils import get_summary_path
        from gui.dialogs import PreviewDialog

        if self._app and hasattr(self._app, 'file_manager'):
            item = self._app.file_manager.get_file(file_path)
            if item and item.result_path and os.path.exists(item.result_path):
                summary_path = get_summary_path(item.result_path)
                if summary_path is None:
                    import time
                    file_age = time.time() - os.path.getmtime(item.result_path)
                    if file_age < 60:
                        QMessageBox.information(self, "提示", "AI 摘要正在生成中，请稍后再预览")
                        return
                dialog = PreviewDialog(self, item.file_name, item.result_path, summary_path)
                dialog.exec()
            else:
                QMessageBox.information(self, "提示", "结果文件不存在")

    def _delete_single(self, file_path):
        """删除单个文件"""
        if self._app and hasattr(self._app, 'file_manager'):
            confirmed, delete_source = self._confirm_delete(
                f"从列表中移除「{os.path.basename(file_path)}」?"
            )
            if not confirmed:
                return
            self._app.file_manager.remove_file(file_path, delete_source=delete_source)
            self._log(f"已删除: {os.path.basename(file_path)}")
            self.refresh_file_list()

    def _open_folder(self, file_path):
        """打开转写结果所在文件夹"""
        import subprocess
        import sys

        logger.debug(f"[OPEN-FOLDER] Called with file_path={repr(file_path)}")

        folder = None
        if self._app and hasattr(self._app, 'file_manager'):
            item = self._app.file_manager.get_file(file_path)
            logger.debug(f"[OPEN-FOLDER] get_file returned: {item}")
            if item and item.result_path:
                folder = os.path.dirname(item.result_path)
                logger.debug(f"[OPEN-FOLDER] Using result_path dir: {repr(folder)}")

        if not folder or not os.path.exists(folder):
            fallback = os.path.dirname(file_path)
            logger.debug(f"[OPEN-FOLDER] Falling back to dirname(file_path): {repr(fallback)}")
            folder = fallback

        # Windows: 使用 normpath 确保路径格式正确
        if folder and sys.platform == "win32":
            folder = os.path.normpath(folder)

        logger.debug(f"[OPEN-FOLDER] Final folder={repr(folder)}, exists={os.path.exists(folder) if folder else False}")

        if folder and os.path.exists(folder):
            try:
                if sys.platform == "win32":
                    os.startfile(folder)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
                self._log(f"已打开文件夹: {folder}")
            except Exception as e:
                logger.error(f"[OPEN-FOLDER] Failed to open folder: {e}")
                self._log(f"无法打开文件夹: {folder}")
        else:
            logger.warning(f"[OPEN-FOLDER] Folder does not exist: {repr(folder)}")
            self._log(f"无法打开文件夹: {folder}")

    def _export_result(self, file_path):
        """导出转写结果"""
        from gui.dialogs import ExportDialog
        from utils import get_summary_path
        if self._app and hasattr(self._app, 'file_manager'):
            item = self._app.file_manager.get_file(file_path)
            if item and item.result_path and os.path.exists(item.result_path):
                summary_path = get_summary_path(item.result_path)
                dialog = ExportDialog(self, file_path, item.result_path, summary_path)
                dialog.exec()
            else:
                QMessageBox.information(self, "提示", "结果文件不存在")

    def _open_speaker_modal(self, file_path):
        """打开发言人管理弹窗"""
        from gui.dialogs import SpeakerDialog, parse_speakers_from_result
        from utils import get_summary_path, apply_speaker_mapping
        import json

        if self._app and hasattr(self._app, 'file_manager'):
            item = self._app.file_manager.get_file(file_path)
            if item and item.result_path and os.path.exists(item.result_path):
                speakers = parse_speakers_from_result(item.result_path, item.speaker_names)
                if speakers:
                    # 获取说话人嵌入向量
                    speaker_embeddings = {}
                    speaker_qualities = {}
                    try:
                        handler = self._app._transcription_handler
                        if hasattr(handler, '_speaker_embeddings'):
                            speaker_embeddings = dict(handler._speaker_embeddings)
                        if hasattr(handler, '_speaker_qualities'):
                            speaker_qualities = dict(handler._speaker_qualities)
                    except Exception:
                        pass

                    # 从磁盘加载嵌入向量（程序重启后恢复）
                    if not speaker_embeddings and item.result_path:
                        speaker_embeddings, speaker_qualities = self._load_embeddings_from_disk(
                            item.result_path)

                    def on_save(names):
                        self._app.file_manager.update_speaker_names(file_path, names)
                        if names and item.result_path and os.path.exists(item.result_path):
                            apply_speaker_mapping(item.result_path, names)
                            summary_path = get_summary_path(item.result_path)
                            if summary_path and os.path.exists(summary_path):
                                apply_speaker_mapping(summary_path, names)
                            self._log(f"发言人映射已保存: {', '.join(f'{k}→{v}' for k, v in names.items())}")

                    dialog = SpeakerDialog(
                        self, item.file_name, speakers,
                        on_save=on_save,
                        speaker_embeddings=speaker_embeddings,
                        speaker_qualities=speaker_qualities,
                        audio_path=file_path
                    )
                    dialog.exec()
                else:
                    QMessageBox.information(self, "提示", "未识别到说话人信息")
            else:
                QMessageBox.information(self, "提示", "请先完成转写")

    def _load_embeddings_from_disk(self, result_path):
        """从磁盘加载声纹嵌入向量"""
        import json
        speaker_embeddings = {}
        speaker_qualities = {}
        try:
            result_dir = os.path.dirname(result_path)
            base = os.path.splitext(os.path.basename(result_path))[0]
            if base.endswith("_transcript"):
                base = base[:-len("_transcript")]
            emb_path = os.path.join(result_dir, f"{base}_embeddings.json")
            if not os.path.exists(emb_path):
                return speaker_embeddings, speaker_qualities
            with open(emb_path, "r", encoding="utf-8") as f:
                emb_data = json.load(f)
            for spk_id_str, info in emb_data.items():
                spk_id = spk_id_str
                vector = info.get("vector", [])
                quality = info.get("quality", DEFAULT_SPK_QUALITY)
                if vector:
                    speaker_embeddings[spk_id] = vector
                    speaker_qualities[spk_id] = quality
        except Exception as e:
            logger.debug(f"从磁盘加载嵌入向量失败: {e}")
        return speaker_embeddings, speaker_qualities

    def _open_summary_for_selected(self):
        """打开AI摘要"""
        from utils import get_summary_path
        selected = self._file_list_view.get_selected()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择已完成转写的文件")
            return

        fp = selected[0]
        if self._app and hasattr(self._app, 'file_manager'):
            item = self._app.file_manager.get_file(fp)
            if item and item.result_path:
                summary_path = get_summary_path(item.result_path)
                if summary_path and os.path.exists(summary_path):
                    import subprocess
                    import sys
                    if sys.platform == "win32":
                        subprocess.Popen(["explorer", summary_path])
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", summary_path])
                    else:
                        subprocess.Popen(["xdg-open", summary_path])
                    self._log(f"已打开摘要: {os.path.basename(summary_path)}")
                else:
                    QMessageBox.information(self, "提示", "未找到 AI 摘要文件")

    def _merge_transcribe(self):
        """合并转写"""
        from gui.dialogs import MergeOrderDialog
        from file_manager import FileStatus

        selected = self._file_list_view.get_selected()
        if len(selected) < 2:
            QMessageBox.information(self, "提示", "请至少选中 2 个文件进行合并转写\n(点击文件行进行多选)")
            return

        if self._app and hasattr(self._app, 'file_manager'):
            selected_items = []
            for fp in selected:
                item = self._app.file_manager.get_file(fp)
                if item and item.status == FileStatus.PENDING:
                    selected_items.append(item)

            if len(selected_items) < 2:
                QMessageBox.information(self, "提示", "选中的文件中至少需要 2 个待转写文件")
                return

            def on_confirm(ordered_items):
                fmt = self.get_selected_format()
                paths = [f.file_path for f in ordered_items]
                names = [f.file_name for f in ordered_items]
                handler = self._app._transcription_handler
                handler.add_to_queue(paths)
                self._log(f"开始合并转写 {len(paths)} 个文件，顺序: {' -> '.join(names)}")
                handler.start(paths, fmt, {}, "", merge=True)

            dialog = MergeOrderDialog(self, selected_items, on_confirm=on_confirm)
            dialog.exec()

    def _stop_transcription(self, file_path):
        """停止转写"""
        if self._app and hasattr(self._app, '_transcription_handler'):
            self._app._transcription_handler.stop_transcription(file_path)
            self._recording_bar.stop_btn.setEnabled(False)
            self._recording_bar.stop_btn.setStyleSheet(f"""
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

    def _queue_move_up(self, file_path):
        """队列上移"""
        if self._app and hasattr(self._app, '_transcription_handler'):
            self._app._transcription_handler.move_up_in_queue(file_path)
            self._log(f"队列调整: {os.path.basename(file_path)} 上移")
            self.refresh_file_list()

    def _queue_move_down(self, file_path):
        """队列下移"""
        if self._app and hasattr(self._app, '_transcription_handler'):
            self._app._transcription_handler.move_down_in_queue(file_path)
            self._log(f"队列调整: {os.path.basename(file_path)} 下移")
            self.refresh_file_list()

    def _queue_remove(self, file_path):
        """从队列移除"""
        if self._app and hasattr(self._app, '_transcription_handler'):
            self._app._transcription_handler.remove_from_queue(file_path)
            self._log(f"已从队列移除: {os.path.basename(file_path)}")
            self.refresh_file_list()

    def _transcribe_single(self, file_path):
        """转写单个文件"""
        if self._app and hasattr(self._app, '_transcription_handler'):
            handler = self._app._transcription_handler
            if handler.is_transcribing:
                QMessageBox.information(self, "提示", "正在转写中，请等待完成")
                return
            fmt = self.get_selected_format()
            handler.start([file_path], fmt, {}, "")
            self._btn_transcribe.setEnabled(False)
            self._btn_transcribe.setText("转写中...")
            self._recording_bar.stop_btn.setEnabled(True)
            self._recording_bar.stop_btn.setStyleSheet(f"""
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
            self._log(f"开始转写: {os.path.basename(file_path)}")
            self.refresh_file_list()

    def _retry_transcription(self, file_path):
        """重新转写"""
        self._log(f"重新转写: {os.path.basename(file_path)}")
        self._transcribe_single(file_path)

    def _start_transcription(self):
        """开始批量转写"""
        if self._app and hasattr(self._app, 'file_manager'):
            pending = self._app.file_manager.get_pending_files()
            if not pending:
                QMessageBox.information(self, "提示", "没有待转写的文件\n请先添加音频文件")
                return
            if self._app and hasattr(self._app, '_transcription_handler'):
                handler = self._app._transcription_handler
                if handler.is_transcribing:
                    QMessageBox.information(self, "提示", "正在转写中，请等待完成")
                    return
                fmt = self.get_selected_format()
                paths = [f.file_path for f in pending]

                from dual_track_merge import find_dual_track_pair
                all_paths = []
                processed = set()
                for fp in paths:
                    if fp in processed:
                        continue
                    pair = find_dual_track_pair(fp)
                    if pair:
                        mic_path, sys_path = pair
                        if mic_path not in processed:
                            all_paths.append(mic_path)
                            processed.add(mic_path)
                        if sys_path not in processed:
                            all_paths.append(sys_path)
                            processed.add(sys_path)
                        self._log(f"检测到双轨配对: {os.path.basename(mic_path)} + {os.path.basename(sys_path)}")
                    else:
                        all_paths.append(fp)
                        processed.add(fp)

                handler.add_to_queue(all_paths)
                handler.start(all_paths, fmt, {}, "")
                self._btn_transcribe.setEnabled(False)
                self._btn_transcribe.setText("转写中...")
                self._recording_bar.stop_btn.setEnabled(True)
                self._recording_bar.stop_btn.setStyleSheet(f"""
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
                self._log(f"开始转写 {len(all_paths)} 个文件...")
                self.refresh_file_list()

    # ══════════════════════════════════════════════════════════
    #  Public Methods
    # ══════════════════════════════════════════════════════════

    def refresh_file_list(self, files=None):
        """刷新文件列表"""
        if files is None and self._app and hasattr(self._app, 'file_manager'):
            # 使用 display_files 属性（过滤合并子文件）
            files = self._app.file_manager.display_files
        if files:
            # 按添加时间降序排序
            files = sorted(files, key=lambda f: f.added_time, reverse=True)
            # 转换为新 FileListView 需要的格式
            file_data = []
            for f in files:
                status_map = {
                    "pending": "pending",
                    "processing": "processing",
                    "done": "done",
                    "failed": "failed",
                }
                file_data.append({
                    "path": f.file_path,
                    "name": f.file_name,
                    "topic": getattr(f, 'topic', '') or '',
                    "duration": f.duration_str if hasattr(f, 'duration_str') else self._format_duration(getattr(f, 'duration_s', 0)),
                    "size": f.size_str if hasattr(f, 'size_str') else self._format_size(getattr(f, 'file_size', 0)),
                    "status": f.status.value if hasattr(f.status, 'value') else str(f.status),
                    "queue_pos": None,
                    "merged": bool(getattr(f, 'merged_group', '')),
                })
            self._file_list_view.set_files(file_data)
            self._file_count_lbl.setText(f"共 {len(files)} 个文件")
        else:
            self._file_list_view.set_files([])
            self._file_count_lbl.setText("")

    def _format_duration(self, seconds):
        """格式化时长"""
        if not seconds:
            return ""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if not size_bytes:
            return ""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    def get_selected_format(self):
        """获取选中的导出格式"""
        text = self._fmt_combo.currentText()
        return OUTPUT_FORMATS.get(text, "md")

    def _log(self, msg):
        """添加日志（仅显示用户关心的信息）"""
        if not any(kw in msg for kw in USER_FRIENDLY_KEYWORDS):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_area.appendPlainText(f"[{ts}] {msg}")

    def update_queue_status(self, text):
        """更新队列状态"""
        self._recording_bar.update_queue_status(text)
