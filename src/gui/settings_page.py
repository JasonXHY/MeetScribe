"""
MeetScribe 设置页（PySide6 版本）
"""

import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QScrollArea,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER, C_SUCCESS, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, C_WARN, FONT_FAMILY, MODEL_CACHE_DIR,
    APP_VERSION, APP_NAME,
)

logger = logging.getLogger("MeetScribe")


class ModelDownloadWorker(QThread):
    """模型下载工作线程"""
    finished = Signal(bool, str)  # success, message

    def __init__(self, model_manager, parent=None):
        super().__init__(parent)
        self._model_manager = model_manager

    def run(self):
        try:
            success, msg = self._model_manager.download_all_missing(
                progress_callback=lambda m: None
            )
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))


class SettingsPage(QWidget):
    """设置页"""

    settings_changed = Signal()

    def __init__(self, parent=None, config=None, log_callback=None):
        super().__init__(parent)
        self._config = config
        self._log = log_callback or (lambda msg: None)
        self._model_manager = None
        self._build()
        self._init_model_manager()
        self._restore_config()

    def _init_model_manager(self):
        try:
            from transcriber import ModelManager
            self._model_manager = ModelManager(MODEL_CACHE_DIR)
        except Exception as e:
            logger.warning(f"Failed to init ModelManager: {e}")

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(8)

        title = QLabel("设置")
        title.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT1};
                font-family: {FONT_FAMILY};
                font-size: 22px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(12)

        self._build_path_section(self._scroll_layout)
        self._build_engine_section(self._scroll_layout)
        self._build_ai_section(self._scroll_layout)
        self._build_model_section(self._scroll_layout)
        self._build_audio_section(self._scroll_layout)
        self._build_notification_section(self._scroll_layout)
        self._build_about_section(self._scroll_layout)

        save_btn = QPushButton("保存设置")
        save_btn.setFixedSize(140, 36)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-family: {FONT_FAMILY};
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {C_BTN_HOVER};
            }}
        """)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        self._scroll_layout.addWidget(save_btn)

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def _build_path_section(self, layout):
        """存储路径设置"""
        group = self._create_group("存储路径", layout)
        self._rec_dir_entry = self._create_path_row(
            group, "录音保存目录",
            self._config.get("recording_dir", "") if self._config else "")
        self._out_dir_entry = self._create_path_row(
            group, "转写输出目录",
            self._config.get("output_dir", "") if self._config else "")

    def _build_engine_section(self, layout):
        """转写引擎设置（含四项引擎参数）"""
        group = self._create_group("转写引擎", layout)

        row0 = QHBoxLayout()
        lbl0 = QLabel("转写模式:")
        lbl0.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
        row0.addWidget(lbl0)
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["FunASR (本地)", "MiMo ASR (云端)"])
        self._engine_combo.setFixedWidth(200)
        current_engine = self._config.get("transcription_engine", "funasr") if self._config else "funasr"
        self._engine_combo.setCurrentIndex(0 if current_engine == "funasr" else 1)
        row0.addWidget(self._engine_combo)
        row0.addStretch()
        group.layout().addLayout(row0)

        engine_items = [
            ("标点恢复", ["自动 (ct-punc)", "关闭"], "_punc_var"),
            ("乱码过滤", ["开启 (中文模式)", "关闭"], "_garble_var"),
            ("VAD 灵敏度", ["适中 (推荐)", "高 (更多分段)", "低 (更少分段)"], "_vad_var"),
            ("运算设备", ["CPU", "CUDA (GPU)"], "_device_var"),
        ]
        for label_text, values, attr in engine_items:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(90)
            lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
            row.addWidget(lbl)
            combo = QComboBox()
            combo.addItems(values)
            combo.setFixedWidth(180)
            setattr(self, attr, combo)
            row.addWidget(combo)
            row.addStretch()
            group.layout().addLayout(row)

    def _build_ai_section(self, layout):
        """AI 服务设置"""
        group = self._create_group("AI 服务", layout)

        row = QHBoxLayout()
        label = QLabel("MiMo API Key:")
        label.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
        row.addWidget(label)
        self._api_key_entry = QLineEdit()
        self._api_key_entry.setFixedWidth(300)
        self._api_key_entry.setEchoMode(QLineEdit.Password)
        api_key = self._config.get("mimo_api_key", "") if self._config else ""
        self._api_key_entry.setText(api_key)
        self._api_key_entry.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background-color: white;
            }}
            QLineEdit:focus {{
                border-color: {C_ACCENT};
            }}
        """)
        row.addWidget(self._api_key_entry)
        row.addStretch()
        group.layout().addLayout(row)

        row2 = QHBoxLayout()
        self._ai_summary_cb = QCheckBox("启用 AI 摘要")
        self._ai_summary_cb.setChecked(self._config.get("ai_summary_enabled", True) if self._config else True)
        row2.addWidget(self._ai_summary_cb)
        row2.addStretch()
        group.layout().addLayout(row2)

        row3 = QHBoxLayout()
        self._ai_correction_cb = QCheckBox("启用 AI 纠错")
        self._ai_correction_cb.setChecked(self._config.get("ai_correction_enabled", True) if self._config else True)
        row3.addWidget(self._ai_correction_cb)
        row3.addStretch()
        group.layout().addLayout(row3)

    def _build_model_section(self, layout):
        """模型管理（含模型详情列表 + 下载按钮）"""
        group = self._create_group("模型管理", layout)

        row_cache = QHBoxLayout()
        lbl_cache = QLabel(f"模型缓存目录: {MODEL_CACHE_DIR}")
        lbl_cache.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
        lbl_cache.setWordWrap(True)
        row_cache.addWidget(lbl_cache)
        row_cache.addStretch()
        group.layout().addLayout(row_cache)

        self._model_status_frame = QFrame()
        self._model_status_frame.setStyleSheet("background: transparent; border: none;")
        self._model_status_layout = QVBoxLayout(self._model_status_frame)
        self._model_status_layout.setContentsMargins(0, 0, 0, 0)
        self._model_status_layout.setSpacing(2)
        group.layout().addWidget(self._model_status_frame)

        btn_row = QHBoxLayout()
        self._btn_check_models = QPushButton("检查模型")
        self._btn_check_models.setFixedWidth(100)
        self._btn_check_models.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_TXT2};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
            }}
        """)
        self._btn_check_models.setCursor(Qt.PointingHandCursor)
        self._btn_check_models.clicked.connect(self._check_models)
        btn_row.addWidget(self._btn_check_models)

        self._btn_download_models = QPushButton("下载缺失模型")
        self._btn_download_models.setFixedWidth(120)
        self._btn_download_models.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0A5E0A;
            }}
            QPushButton:disabled {{
                background-color: {C_TXT3};
            }}
        """)
        self._btn_download_models.setCursor(Qt.PointingHandCursor)
        self._btn_download_models.clicked.connect(self._download_missing_models)
        btn_row.addWidget(self._btn_download_models)

        self._model_status_label = QLabel("")
        self._model_status_label.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
        btn_row.addWidget(self._model_status_label)
        btn_row.addStretch()
        group.layout().addLayout(btn_row)

        self._refresh_model_status()

    def _build_audio_section(self, layout):
        """音频设备设置"""
        group = self._create_group("音频设备", layout)
        self._vb_cable_cb = QCheckBox("使用 VB-Audio Cable（推荐）")
        self._vb_cable_cb.setChecked(self._config.get("use_vb_cable", False) if self._config else False)
        group.layout().addWidget(self._vb_cable_cb)
        hint = QLabel("启用后可避免停止录音时暂停媒体播放器")
        hint.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
        group.layout().addWidget(hint)

    def _build_notification_section(self, layout):
        """通知设置"""
        group = self._create_group("通知", layout)
        self._notification_cb = QCheckBox("启用系统通知")
        self._notification_cb.setChecked(self._config.get("enable_notification", True) if self._config else True)
        group.layout().addWidget(self._notification_cb)
        hint = QLabel("转写完成后发送系统通知并弹窗提示")
        hint.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
        group.layout().addWidget(hint)

    def _build_about_section(self, layout):
        """关于"""
        group = self._create_group("关于", layout)
        about_info = QLabel(
            f"{APP_NAME} v{APP_VERSION}  —  本地会议录音转写助手"
        )
        about_info.setStyleSheet(f"color: {C_TXT1}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        group.layout().addWidget(about_info)

        dev_info = QLabel("制作者：刘家诚")
        dev_info.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
        group.layout().addWidget(dev_info)

        for line in [
            "引擎: FunASR SenseVoice + CAM++ + ct-punc (本地推理)",
            "AI: MiMo 云端 (摘要/纠错) + 内网大模型 (预留)",
            "支持格式: WAV / MP3 / M4A / FLAC / OGG / OGA / OPUS",
        ]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
            group.layout().addWidget(lbl)

    def _create_group(self, title, layout):
        """创建分组卡片（标题在卡片外面）"""
        title_lbl = QLabel(f"  {title}")
        title_lbl.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT1};
                font-family: {FONT_FAMILY};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(title_lbl)

        card = QFrame()
        card.setProperty("cssClass", "card")
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(6)
        layout.addWidget(card)
        return card

    def _create_path_row(self, parent, label_text, default_value):
        """创建路径输入行"""
        row = QHBoxLayout()
        label = QLabel(f"{label_text}:")
        label.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
        row.addWidget(label)
        entry = QLineEdit(default_value)
        entry.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }}
        """)
        row.addWidget(entry, 1)
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(64)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG};
                color: {C_TXT1};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #EAEAEA;
            }}
        """)
        browse_btn.setCursor(Qt.PointingHandCursor)
        if "录音" in label_text:
            browse_btn.clicked.connect(lambda: self._browse_dir(entry, "选择录音目录"))
        else:
            browse_btn.clicked.connect(lambda: self._browse_dir(entry, "选择输出目录"))
        row.addWidget(browse_btn)
        row.addStretch()
        parent.layout().addLayout(row)
        return entry

    def _browse_dir(self, entry, title):
        """浏览目录"""
        path = QFileDialog.getExistingDirectory(self, title, entry.text())
        if path:
            entry.setText(path)

    def _refresh_model_status(self):
        """刷新模型状态显示"""
        if not self._model_manager:
            return

        while self._model_status_layout.count():
            item = self._model_status_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        status = self._model_manager.check_all_models()

        for model_id, state in status.items():
            row = QHBoxLayout()
            row.setSpacing(4)

            if state["cached"]:
                icon = "\u2705"
                color = C_SUCCESS
            else:
                icon = "\u274c"
                color = C_ERROR if state["info"]["required"] else C_WARN

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(24)
            icon_lbl.setStyleSheet("background: transparent; border: none; font-size: 12px;")
            row.addWidget(icon_lbl)

            name_lbl = QLabel(model_id)
            name_lbl.setFixedWidth(140)
            name_lbl.setStyleSheet(f"color: {C_TXT1}; font-size: 12px; font-weight: bold; background: transparent; border: none;")
            row.addWidget(name_lbl)

            desc_lbl = QLabel(state["info"]["description"])
            desc_lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 11px; background: transparent; border: none;")
            row.addWidget(desc_lbl)

            size_lbl = QLabel(state["info"]["size_hint"])
            size_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
            row.addWidget(size_lbl)

            status_text = "已缓存" if state["cached"] else ("必需" if state["info"]["required"] else "可选")
            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent; border: none;")
            row.addWidget(status_lbl)

            row.addStretch()

            container = QWidget()
            container.setLayout(row)
            container.setStyleSheet("background: transparent; border: none;")
            self._model_status_layout.addWidget(container)

        missing = self._model_manager.get_missing_models(required_only=True)
        if missing:
            self._model_status_label.setText(f"缺少 {len(missing)} 个必需模型")
            self._model_status_label.setStyleSheet(f"color: {C_ERROR}; font-size: 11px; background: transparent; border: none;")
        else:
            self._model_status_label.setText("所有必需模型已就绪")
            self._model_status_label.setStyleSheet(f"color: {C_SUCCESS}; font-size: 11px; background: transparent; border: none;")

    def _check_models(self):
        """检查模型状态"""
        self._log("正在检查模型状态...")
        self._refresh_model_status()
        self._log("模型检查完成")

    def _download_missing_models(self):
        """下载缺失模型"""
        if not self._model_manager:
            QMessageBox.warning(self, "错误", "模型管理器未初始化")
            return

        missing = self._model_manager.get_missing_models(required_only=True)
        if not missing:
            QMessageBox.information(self, "提示", "所有必需模型已就绪，无需下载")
            return

        model_list = "\n".join(f"  - {m}" for m in missing)
        reply = QMessageBox.question(
            self, "确认下载",
            f"将下载以下模型:\n{model_list}\n\n下载可能需要较长时间，是否继续?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._btn_download_models.setEnabled(False)
        self._btn_download_models.setText("下载中...")

        self._download_worker = ModelDownloadWorker(self._model_manager, self)
        self._download_worker.finished.connect(self._on_download_complete)
        self._download_worker.start()

    def _on_download_complete(self, success, msg):
        """下载完成回调"""
        self._btn_download_models.setEnabled(True)
        self._btn_download_models.setText("下载缺失模型")
        self._refresh_model_status()

        if success:
            self._log(f"模型下载完成: {msg}")
            QMessageBox.information(self, "完成", msg)
        else:
            self._log(f"模型下载失败: {msg}")
            QMessageBox.critical(self, "错误", f"模型下载失败:\n{msg}")

    def _restore_config(self):
        """从配置恢复 UI 状态"""
        if not self._config:
            return

        self._punc_var.setCurrentText(self._config.get("punc_restore", "自动 (ct-punc)"))
        self._garble_var.setCurrentText(self._config.get("garble_filter", "开启 (中文模式)"))
        self._vad_var.setCurrentText(self._config.get("vad_sensitivity", "适中 (推荐)"))
        self._device_var.setCurrentText(self._config.get("device", "CPU"))

    def _on_save(self):
        """保存设置"""
        if not self._config:
            QMessageBox.warning(self, "错误", "配置对象未初始化")
            return

        self._config.set("recording_dir", self._rec_dir_entry.text())
        self._config.set("transcript_dir", self._out_dir_entry.text())

        if hasattr(self, '_engine_combo'):
            engine_text = self._engine_combo.currentText()
            engine_map = {"FunASR (本地)": "funasr", "MiMo ASR (云端)": "mimo"}
            self._config.set("transcription_engine", engine_map.get(engine_text, "funasr"))

        self._config.set("punc_restore", self._punc_var.currentText())
        self._config.set("garble_filter", self._garble_var.currentText())
        self._config.set("vad_sensitivity", self._vad_var.currentText())
        self._config.set("device", self._device_var.currentText())

        if hasattr(self, '_api_key_entry'):
            self._config.set("ai_api_key", self._api_key_entry.text().strip())
            self._config.set("mimo_api_key", self._api_key_entry.text().strip())
        if hasattr(self, '_ai_summary_cb'):
            self._config.set("ai_summary_enabled", self._ai_summary_cb.isChecked())
            self._config.set("auto_summary", "转写后自动生成" if self._ai_summary_cb.isChecked() else "关闭")
        if hasattr(self, '_ai_correction_cb'):
            self._config.set("ai_correction_enabled", self._ai_correction_cb.isChecked())
            self._config.set("auto_correction", "转写后自动纠错" if self._ai_correction_cb.isChecked() else "关闭")

        if hasattr(self, '_vb_cable_cb'):
            self._config.set("use_vb_cable", self._vb_cable_cb.isChecked())
        if hasattr(self, '_notification_cb'):
            self._config.set("enable_notification", self._notification_cb.isChecked())

        self._config.save()
        self._log("设置已保存")
        self.settings_changed.emit()
        QMessageBox.information(self, "成功", "设置已保存")
