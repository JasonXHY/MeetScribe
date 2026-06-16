"""
音色库管理页面（PySide6 完整版）

功能：
- 说话人列表显示
- 说话人详情查看
- 添加/编辑/删除说话人
- 声纹样本管理
- 录音朗读添加音色
"""

import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QMessageBox, QInputDialog,
    QDialog, QSplitter, QListWidget, QListWidgetItem, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QSize
from PySide6.QtGui import QFont

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_ERROR, C_WARN, C_TXT1, C_TXT2, C_TXT3, C_PURPLE,
    FONT_FAMILY, SPEAKER_COLORS, DEFAULT_SPK_QUALITY,
)

logger = logging.getLogger("MeetScribe")


class AudioProcessWorker(QThread):
    """音频处理工作线程"""
    finished = Signal(dict)  # result
    error = Signal(str)  # error message

    def __init__(self, audio_path, voiceprint_lib, parent=None):
        super().__init__(parent)
        self._audio_path = audio_path
        self._voiceprint_lib = voiceprint_lib

    def run(self):
        try:
            if not self._audio_path or not os.path.exists(self._audio_path):
                self.error.emit("音频文件不存在")
                return

            embedding = self._voiceprint_lib.extract_embedding(self._audio_path)
            if embedding is not None:
                self.finished.emit({"embedding": embedding, "audio_path": self._audio_path})
            else:
                self.error.emit("声纹提取失败")
        except Exception as e:
            self.error.emit(str(e))


class AddVoiceDialog(QDialog):
    """人工添加音色弹窗"""

    PRESET_TEXT = "你好，我是{姓名}，这是我的声纹样本。"

    def __init__(self, parent=None, on_save=None):
        super().__init__(parent)
        self.setWindowTitle("添加新说话人")
        self.setFixedSize(440, 380)
        self.setStyleSheet(f"QDialog {{ background-color: {C_BG}; }}")

        self._parent = parent
        self._on_save = on_save
        self._recording = False
        self._recorder = None
        self._audio_path = None
        self._temp_dir = None
        self._embedding = None

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(6)

        # 标题
        title = QLabel("添加新说话人")
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 16px; font-weight: bold;
                background: transparent; border: none; }}
        """)
        layout.addWidget(title)

        subtitle = QLabel("录音朗读以下文本，系统将自动提取声纹")
        subtitle.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY};
                font-size: 12px; background: transparent; border: none; }}
        """)
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        # 姓名输入
        name_label = QLabel("说话人姓名")
        name_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY};
                font-size: 12px; background: transparent; border: none; }}
        """)
        layout.addWidget(name_label)

        self._name_entry = QLineEdit()
        self._name_entry.setPlaceholderText("请输入姓名")
        self._name_entry.setFixedHeight(32)
        self._name_entry.setStyleSheet(f"""
            QLineEdit {{ border: 1px solid {C_BORDER}; border-radius: 6px;
                padding: 4px 8px; font-family: {FONT_FAMILY}; font-size: 12px;
                color: {C_TXT1}; background: white; }}
        """)
        layout.addWidget(self._name_entry)
        layout.addSpacing(2)

        # 朗读文本区域（无边框，占剩余空间）
        read_label = QLabel("请朗读以下文本：")
        read_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY};
                font-size: 12px; font-weight: 600;
                background: transparent; border: none; }}
        """)
        layout.addWidget(read_label)

        self._preset_label = QLabel(f"\u2022 {self.PRESET_TEXT}")
        self._preset_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY}; font-size: 12px;
                background: transparent; border: none; }}
        """)
        self._preset_label.setWordWrap(True)
        layout.addWidget(self._preset_label, 1)

        # 录音状态
        rec_state_row = QHBoxLayout()
        rec_state_row.setSpacing(6)
        self._rec_dot = QLabel()
        self._rec_dot.setFixedSize(8, 8)
        self._rec_dot.setStyleSheet(f"""
            QLabel {{ background-color: {C_TXT3}; border-radius: 4px; border: none;
                min-width: 8px; min-height: 8px; }}
        """)
        rec_state_row.addWidget(self._rec_dot)

        self._status_label = QLabel("准备就绪")
        self._status_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 11px;
                background: transparent; border: none; }}
        """)
        rec_state_row.addWidget(self._status_label)
        rec_state_row.addStretch()
        layout.addLayout(rec_state_row)

        btn_layout = QHBoxLayout()

        self._record_btn = QPushButton("开始录音")
        self._record_btn.setFixedSize(120, 36)
        self._record_btn.setProperty("cssClass", "danger")
        self._record_btn.setCursor(Qt.PointingHandCursor)
        self._record_btn.clicked.connect(self._toggle_recording)
        btn_layout.addWidget(self._record_btn)

        self._save_btn = QPushButton("保存")
        self._save_btn.setFixedSize(80, 36)
        self._save_btn.setEnabled(False)
        self._save_btn.setProperty("cssClass", "primary")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self._save_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        import tempfile
        from unified_recorder import UnifiedRecorder

        try:
            self._temp_dir = tempfile.mkdtemp()
            self._audio_path = None
            logger.debug(f"[ADD-VOICE] Created temp dir: {self._temp_dir}")

            self._recorder = UnifiedRecorder(
                save_dir=self._temp_dir,
                use_vb_cable=False,
            )
            self._recorder.on_stop_complete = self._on_recording_complete
            self._recorder.start("mic")
            self._recording = True

            self._record_btn.setText("停止录音")
            self._rec_dot.setStyleSheet(f"""
                QLabel {{ background-color: {C_ERROR}; border-radius: 4px; border: none; }}
            """)
            self._status_label.setText("录音中... 请朗读上述文本")
            self._status_label.setStyleSheet(f"""
                QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY}; font-size: 11px;
                    background: transparent; border: none; }}
            """)
            logger.debug("[ADD-VOICE] Recording started")

        except Exception as e:
            logger.error(f"[ADD-VOICE] Failed to start recording: {e}")
            QMessageBox.critical(self, "录音错误", f"无法启动录音:\n{e}")
            self._status_label.setText("录音启动失败")
            self._status_label.setStyleSheet(f"""
                QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY}; font-size: 11px; }}
            """)

    def _stop_recording(self):
        if self._recorder:
            logger.debug("[ADD-VOICE] Stopping recording...")
            self._recorder.stop()
            self._recording = False

            self._record_btn.setText("开始录音")
            self._record_btn.setEnabled(False)
            self._rec_dot.setStyleSheet(f"""
                QLabel {{ background-color: {C_TXT3}; border-radius: 4px; border: none; }}
            """)
            self._status_label.setText("正在提取声纹...")
            self._status_label.setStyleSheet(f"""
                QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 11px;
                    background: transparent; border: none; }}
            """)

    def _on_recording_complete(self, saved_files):
        logger.debug(f"[ADD-VOICE] Recording complete, saved files: {saved_files}")

        if saved_files:
            self._audio_path = saved_files[0]
            logger.debug(f"[ADD-VOICE] Using audio file: {self._audio_path}")
            self._process_audio_worker = AudioProcessWorker(
                self._audio_path, self._voiceprint_lib, self
            )
            self._process_audio_worker.finished.connect(self._on_audio_process_done)
            self._process_audio_worker.error.connect(self._on_audio_process_error)
            self._process_audio_worker.start()
        else:
            logger.error("[ADD-VOICE] No files saved!")
            QTimer.singleShot(0, lambda: self._status_label.setText("录音失败，请重试"))
            QTimer.singleShot(0, lambda: self._status_label.setStyleSheet(
                f"QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY}; font-size: 11px; }}"))
            QTimer.singleShot(0, lambda: self._record_btn.setEnabled(True))

    def _on_audio_process_done(self, result):
        """音频处理完成回调"""
        embedding = result.get("embedding")
        audio_path = result.get("audio_path")
        if embedding is not None:
            self._temp_embedding = embedding
            self._temp_audio_path = audio_path
            self._rec_dot.setStyleSheet(f"""
                QLabel {{ background-color: {C_SUCCESS}; border-radius: 4px; border: none; }}
            """)
            self._status_label.setText("声纹提取成功，请填写信息后保存")
            self._status_label.setStyleSheet(
                f"QLabel {{ color: {C_SUCCESS}; font-family: {FONT_FAMILY}; font-size: 11px; }}")
            self._save_btn.setEnabled(True)
        else:
            self._status_label.setText("声纹提取失败，请重试")
            self._status_label.setStyleSheet(
                f"QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY}; font-size: 11px; }}")
            self._record_btn.setEnabled(True)

    def _on_audio_process_error(self, error_msg):
        """音频处理错误回调"""
        logger.error(f"[ADD-VOICE] Audio process error: {error_msg}")
        self._status_label.setText(f"处理失败: {error_msg}")
        self._status_label.setStyleSheet(
            f"QLabel {{ color: {C_ERROR}; font-family: {FONT_FAMILY}; font-size: 11px; }}")
        self._record_btn.setEnabled(True)

    def _save(self):
        name = self._name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入说话人姓名")
            return

        if self._temp_embedding is None:
            QMessageBox.warning(self, "提示", "请先录音提取声纹")
            return

        try:
            from voiceprint import VoiceprintLibrary

            library = VoiceprintLibrary()
            library.add_speaker(name, self._temp_embedding, "manual_recording", quality=0.90)

            QMessageBox.information(self, "成功", f"已将说话人保存到音色库:\n{name}")

            if self._on_save:
                self._on_save()

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{e}")

    def closeEvent(self, event):
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        super().closeEvent(event)


class VoiceprintPage(QWidget):
    """音色库管理页面"""

    def __init__(self, parent=None, app=None):
        super().__init__(parent)
        self._app = app
        self._selected_speaker = None
        self._library = None  # 缓存 VoiceprintLibrary 实例

        self._build()
        self.refresh_list()

    def _get_library(self):
        """获取 VoiceprintLibrary 实例（懒加载）"""
        if self._library is None:
            from voiceprint import VoiceprintLibrary
            self._library = VoiceprintLibrary()
        return self._library

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(8)

        # 标题
        title_frame = QHBoxLayout()
        title = QLabel("音色库管理")
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 24px; font-weight: bold; }}
        """)
        title_frame.addWidget(title)
        title_frame.addStretch()

        add_btn = QPushButton("+ 添加音色")
        add_btn.setFixedSize(110, 32)
        add_btn.setProperty("cssClass", "primary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_speaker)
        title_frame.addWidget(add_btn)
        layout.addLayout(title_frame)

        # 主体区域（左右分栏）
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {C_BG};
                width: 12px;
            }}
            QSplitter::handle:hover {{
                background-color: #F3F4F6;
            }}
        """)

        # 左侧：说话人列表
        left_panel = QFrame()
        left_panel.setStyleSheet(f"""
            QFrame {{ background-color: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 8px; }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        left_header = QFrame()
        left_header.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border: none;
                border-bottom: 1px solid {C_BORDER}; }}
        """)
        left_header_layout = QHBoxLayout(left_header)
        left_header_layout.setContentsMargins(14, 12, 14, 12)

        list_title = QLabel("说话人列表")
        list_title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 13px; font-weight: bold;
                background: transparent; border: none; }}
        """)
        left_header_layout.addWidget(list_title)
        left_header_layout.addStretch()
        self._list_count_label = QLabel("0 人")
        self._list_count_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-size: 11px;
                background: transparent; border: none; }}
        """)
        left_header_layout.addWidget(self._list_count_label)
        left_layout.addWidget(left_header)

        # 搜索框
        search_row = QHBoxLayout()
        search_row.setContentsMargins(14, 4, 14, 4)
        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText("搜索说话人...")
        self._search_entry.setFixedHeight(28)
        self._search_entry.setStyleSheet(f"""
            QLineEdit {{ border: 1px solid {C_BORDER}; border-radius: 4px;
                padding: 2px 8px; font-size: 11px; background: white; color: {C_TXT1}; }}
            QLineEdit:focus {{ border-color: {C_ACCENT}; }}
        """)
        self._search_entry.textChanged.connect(self._filter_speakers)
        search_row.addWidget(self._search_entry)
        left_layout.addLayout(search_row)

        self._speaker_list = QListWidget()
        self._speaker_list.setStyleSheet(f"""
            QListWidget {{
                background: transparent; border: none;
                font-family: {FONT_FAMILY}; font-size: 12px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 0 4px 2px 4px;
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: {C_ACCENT_LT}; color: {C_TXT1};
            }}
            QListWidget::item:hover {{
                background-color: #F9FAFB;
            }}
        """)
        self._speaker_list.currentItemChanged.connect(self._on_speaker_select)
        left_layout.addWidget(self._speaker_list, 1)

        splitter.addWidget(left_panel)

        # 右侧：说话人详情
        right_panel = QFrame()
        right_panel.setStyleSheet(f"""
            QFrame {{ background-color: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 8px; }}
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._detail_header = QFrame()
        self._detail_header.setStyleSheet(f"""
            QFrame {{ background-color: transparent; border: none;
                border-bottom: 1px solid {C_BORDER}; }}
        """)
        detail_header_layout = QHBoxLayout(self._detail_header)
        detail_header_layout.setContentsMargins(20, 16, 20, 16)

        self._detail_title = QLabel("请选择一个说话人")
        self._detail_title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY};
                font-size: 18px; font-weight: bold;
                background: transparent; border: none; }}
        """)
        detail_header_layout.addWidget(self._detail_title)
        detail_header_layout.addStretch()
        right_layout.addWidget(self._detail_header)

        self._detail_content = QScrollArea()
        self._detail_content.setWidgetResizable(True)
        self._detail_content.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._detail_widget = QWidget()
        self._detail_widget.setStyleSheet("background: transparent;")
        self._detail_layout = QVBoxLayout(self._detail_widget)
        self._detail_layout.setContentsMargins(20, 16, 20, 16)
        self._detail_layout.setSpacing(12)
        self._detail_layout.addStretch()

        self._detail_content.setWidget(self._detail_widget)
        right_layout.addWidget(self._detail_content, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([280, 560])

        layout.addWidget(splitter, 1)

        # 底部信息
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(4, 4, 4, 0)

        info_label = QLabel("音色库用于识别已注册的说话人，转写时自动匹配")
        info_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-size: 11px; background: transparent; border: none; }}
        """)
        info_layout.addWidget(info_label)
        info_layout.addStretch()

        self._count_label = QLabel("共 0 个说话人")
        self._count_label.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-size: 11px; background: transparent; border: none; }}
        """)
        info_layout.addWidget(self._count_label)

        layout.addLayout(info_layout)

    def refresh_list(self):
        """刷新说话人列表"""
        try:
            library = self._get_library()
            speakers = library.get_speakers()

            self._speaker_list.clear()

            if not speakers:
                self._count_label.setText("共 0 个说话人")
                self._list_count_label.setText("0 人")
                # 添加空状态提示
                empty_item = QListWidgetItem("暂无注册的说话人")
                empty_item.setFlags(Qt.NoItemFlags)  # 不可选中
                empty_item.setTextAlignment(Qt.AlignCenter)
                self._speaker_list.addItem(empty_item)
                return

            for name, profile in speakers.items():
                # 创建带彩色头像的自定义widget
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(10, 10, 10, 10)
                item_layout.setSpacing(10)

                # 彩色圆形头像
                avatar = QLabel(name[0] if name else "?")
                avatar.setFixedSize(32, 32)
                avatar.setAlignment(Qt.AlignCenter)
                color_idx = hash(name) % len(SPEAKER_COLORS)
                avatar.setStyleSheet(f"""
                    background-color: {SPEAKER_COLORS[color_idx]};
                    color: white; border-radius: 16px;
                    font-size: 13px; font-weight: bold;
                """)
                item_layout.addWidget(avatar)

                # 名字 + 样本数
                info_layout = QVBoxLayout()
                info_layout.setSpacing(1)
                name_lbl = QLabel(name)
                name_lbl.setStyleSheet(f"color: {C_TXT1}; font-size: 13px; font-weight: 500; background: transparent; border: none;")
                info_layout.addWidget(name_lbl)
                meta_lbl = QLabel(f"{len(profile.embeddings)} 个样本")
                meta_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
                info_layout.addWidget(meta_lbl)
                item_layout.addLayout(info_layout)
                item_layout.addStretch()

                list_item = QListWidgetItem()
                list_item.setSizeHint(QSize(0, 52))
                list_item.setData(Qt.UserRole, name)
                self._speaker_list.addItem(list_item)
                self._speaker_list.setItemWidget(list_item, item_widget)

            total_samples = sum(len(p.embeddings) for p in speakers.values())
            self._count_label.setText(f"共 {len(speakers)} 个说话人，{total_samples} 个样本")
            self._list_count_label.setText(f"{len(speakers)} 人")

        except Exception as e:
            logger.error(f"Failed to refresh voiceprint list: {e}")

    def _filter_speakers(self, text):
        """过滤说话人列表"""
        text = text.strip().lower()
        for i in range(self._speaker_list.count()):
            item = self._speaker_list.item(i)
            name = item.data(Qt.UserRole) or ""
            item.setHidden(text != "" and text not in name.lower())

    def _on_speaker_select(self, current, previous):
        """选中说话人"""
        if current:
            name = current.data(Qt.UserRole)
            self._selected_speaker = name
            self._show_speaker_detail(name)

    def _show_speaker_detail(self, speaker_name):
        """显示说话人详情"""
        try:
            library = self._get_library()
            speakers = library.get_speakers()
            profile = speakers.get(speaker_name)

            if not profile:
                self._detail_title.setText("未找到说话人")
                return

            self._detail_title.setText(speaker_name)
            self._detail_title.setStyleSheet(f"""
                QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                    font-size: 18px; font-weight: bold;
                    background: transparent; border: none; }}
            """)

            # 清空详情
            while self._detail_layout.count():
                child = self._detail_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # 操作按钮
            btn_layout = QHBoxLayout()
            edit_btn = QPushButton("编辑")
            edit_btn.setFixedSize(60, 28)
            edit_btn.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {C_TXT2};
                    border: 1px solid {C_BORDER}; border-radius: 4px;
                    font-size: 12px; }}
                QPushButton:hover {{ background-color: #F3F4F6; }}
            """)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.clicked.connect(lambda: self._edit_speaker(speaker_name))
            btn_layout.addWidget(edit_btn)

            delete_btn = QPushButton("删除")
            delete_btn.setFixedSize(60, 28)
            delete_btn.setProperty("cssClass", "danger-outline")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.clicked.connect(lambda: self._delete_speaker(speaker_name))
            btn_layout.addWidget(delete_btn)
            btn_layout.addStretch()

            btn_container = QWidget()
            btn_container.setLayout(btn_layout)
            self._detail_layout.addWidget(btn_container)

            # 基本信息
            info_title = QLabel("基本信息")
            info_title.setStyleSheet(f"""
                QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                    font-size: 13px; font-weight: bold;
                    background: transparent; border: none; }}
            """)
            self._detail_layout.addWidget(info_title)

            info_card = QFrame()
            info_card.setStyleSheet(f"""
                QFrame {{ background-color: #F9FAFB; border: none; border-radius: 6px; }}
            """)
            info_card_layout = QVBoxLayout(info_card)
            info_card_layout.setContentsMargins(12, 8, 12, 8)
            info_card_layout.setSpacing(4)

            info_items = [
                ("样本数", str(len(profile.embeddings))),
                ("创建时间", profile.created_at[:10] if profile.created_at else "未知"),
            ]
            if profile.embeddings:
                avg_quality = sum(e.get('quality', DEFAULT_SPK_QUALITY) for e in profile.embeddings) / len(profile.embeddings)
                info_items.append(("平均质量", f"{avg_quality:.2f}"))
            for label, value in info_items:
                row = QHBoxLayout()
                row.setSpacing(0)
                lbl = QLabel(label)
                lbl.setFixedWidth(80)
                lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 12px; background: transparent; border: none;")
                row.addWidget(lbl)
                val_lbl = QLabel(value)
                val_lbl.setStyleSheet(f"color: {C_TXT1}; font-size: 12px; background: transparent; border: none;")
                row.addWidget(val_lbl)
                row.addStretch()
                info_card_layout.addLayout(row)

            self._detail_layout.addWidget(info_card)

            # 声纹样本列表
            samples_title = QLabel("声纹样本")
            samples_title.setStyleSheet(f"""
                QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                    font-size: 13px; font-weight: bold;
                    background: transparent; border: none; }}
            """)
            self._detail_layout.addWidget(samples_title)

            samples_card = QFrame()
            samples_card.setStyleSheet(f"""
                QFrame {{ background-color: #F9FAFB; border: none; border-radius: 6px; }}
            """)
            samples_layout = QVBoxLayout(samples_card)
            samples_layout.setContentsMargins(12, 8, 12, 8)
            samples_layout.setSpacing(4)

            if profile.embeddings:
                for idx, emb in enumerate(profile.embeddings):
                    row = QHBoxLayout()
                    row.setSpacing(0)
                    name_lbl = QLabel(f"样本 {idx + 1}")
                    name_lbl.setFixedWidth(60)
                    name_lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 11px; background: transparent; border: none;")
                    row.addWidget(name_lbl)
                    src_lbl = QLabel(emb.get("source", "未知来源"))
                    src_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
                    row.addWidget(src_lbl)
                    row.addStretch()
                    quality = emb.get('quality', DEFAULT_SPK_QUALITY)
                    quality_color = C_SUCCESS if quality >= 0.8 else C_WARN
                    quality_bg = "#ECFDF5" if quality >= 0.8 else "#FEF3C7"
                    quality_lbl = QLabel(f"  {quality:.2f}  ")
                    quality_lbl.setStyleSheet(f"""
                        color: {quality_color}; background: {quality_bg};
                        border-radius: 10px; font-size: 11px; font-weight: 500;
                        padding: 2px 8px; border: none;
                    """)
                    row.addWidget(quality_lbl)
                    samples_layout.addLayout(row)
            else:
                empty_lbl = QLabel("暂无声纹样本")
                empty_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 12px; background: transparent; border: none;")
                samples_layout.addWidget(empty_lbl)

            self._detail_layout.addWidget(samples_card)
            self._detail_layout.addStretch()

        except Exception as e:
            logger.error(f"Failed to show speaker detail: {e}")

    def _add_speaker(self):
        """添加说话人"""
        dialog = AddVoiceDialog(parent=self, on_save=self.refresh_list)
        dialog.exec()

    def _edit_speaker(self, old_name):
        """编辑说话人姓名"""
        new_name, ok = QInputDialog.getText(
            self, "编辑说话人姓名", "请输入新的姓名:", text=old_name
        )
        if ok and new_name and new_name != old_name:
            try:
                library = self._get_library()

                if not library.rename_speaker(old_name, new_name):
                    QMessageBox.warning(self, "提示", f"姓名 '{new_name}' 已存在或 '{old_name}' 不存在")
                    return

                if self._app and hasattr(self._app, '_home_page'):
                    self._app._home_page._log(f"已重命名说话人: {old_name} -> {new_name}")

                self.refresh_list()

                # 更新选中状态
                if self._selected_speaker == old_name:
                    self._selected_speaker = new_name

            except Exception as e:
                QMessageBox.critical(self, "错误", f"重命名失败: {e}")

    def _delete_speaker(self, speaker_name):
        """删除说话人"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除说话人 '{speaker_name}' 吗？\n\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                library = self._get_library()
                library.remove_speaker(speaker_name)

                if self._app and hasattr(self._app, '_home_page'):
                    self._app._home_page._log(f"已删除说话人: {speaker_name}")

                self._selected_speaker = None
                self.refresh_list()
                self._detail_title.setText("请选择一个说话人")
                self._detail_title.setStyleSheet(f"""
                    QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY};
                        font-size: 18px; font-weight: bold;
                        background: transparent; border: none; }}
                """)

                # 清空详情
                while self._detail_layout.count():
                    child = self._detail_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                self._detail_layout.addStretch()

            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")
