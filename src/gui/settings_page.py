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

        save_btn_row = QHBoxLayout()
        save_btn_row.setContentsMargins(0, 8, 0, 20)
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
        save_btn_row.addWidget(save_btn)
        save_btn_row.addStretch()
        self._scroll_layout.addLayout(save_btn_row)

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

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["FunASR (本地)", "MiMo ASR (云端)"])
        self._engine_combo.setFixedWidth(180)
        current_engine = self._config.get("transcription_engine", "funasr") if self._config else "funasr"
        self._engine_combo.setCurrentIndex(0 if current_engine == "funasr" else 1)
        self._form_row(group, "转写模式", self._engine_combo)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
        group.layout().addWidget(sep)

        engine_items = [
            ("标点恢复", ["自动 (ct-punc)", "关闭"], "_punc_var"),
            ("乱码过滤", ["开启 (中文模式)", "关闭"], "_garble_var"),
            ("VAD 灵敏度", ["适中 (推荐)", "高 (更多分段)", "低 (更少分段)"], "_vad_var"),
            ("运算设备", ["CPU", "CUDA (GPU)"], "_device_var"),
        ]
        for label_text, values, attr in engine_items:
            combo = QComboBox()
            combo.addItems(values)
            combo.setFixedWidth(180)
            setattr(self, attr, combo)
            self._form_row(group, label_text, combo)

    def _build_ai_section(self, layout):
        """AI 服务设置"""
        group = self._create_group("AI 增强", layout)

        try:
            from model_registry import get_vendor_list, get_models_for_vendor
        except ImportError:
            get_vendor_list = lambda: ["小米"]
            get_models_for_vendor = lambda v: ["MiMo"]

        self._vendor_combo = QComboBox()
        self._vendor_combo.addItems(get_vendor_list())
        self._vendor_combo.setFixedWidth(180)
        self._vendor_combo.currentTextChanged.connect(self._on_vendor_changed)
        self._form_row(group, "模型厂商", self._vendor_combo)

        self._model_combo = QComboBox()
        self._model_combo.addItems(get_models_for_vendor("小米"))
        self._model_combo.setFixedWidth(180)
        self._form_row(group, "摘要模型", self._model_combo)

        api_key_widget = QHBoxLayout()
        api_key_widget.setSpacing(4)
        self._api_key_entry = QLineEdit()
        self._api_key_entry.setEchoMode(QLineEdit.Password)
        self._api_key_entry.setFixedWidth(260)
        api_key = self._config.get("mimo_api_key", "") if self._config else ""
        self._api_key_entry.setText(api_key)
        api_key_widget.addWidget(self._api_key_entry)
        self._api_key_toggle = QPushButton("👁")
        self._api_key_toggle.setFixedSize(30, 30)
        self._api_key_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_BG}; color: {C_TXT2};
                border: 1px solid {C_BORDER}; border-radius: 6px; font-size: 14px;
            }}
            QPushButton:hover {{ background-color: #EAEAEA; }}
        """)
        self._api_key_toggle.setCursor(Qt.PointingHandCursor)
        self._api_key_toggle.clicked.connect(self._toggle_api_key)
        api_key_widget.addWidget(self._api_key_toggle)
        api_key_container = QWidget()
        api_key_container.setLayout(api_key_widget)
        api_key_container.setStyleSheet("background: transparent; border: none;")
        self._form_row(group, "API Key", api_key_container)

        self._access_mode_combo = QComboBox()
        self._access_mode_combo.addItems(["Token Plan", "按量计费"])
        self._access_mode_combo.setFixedWidth(180)
        self._form_row(group, "接入模式", self._access_mode_combo,
                       hint_text="Token Plan = 包月套餐 | 按量计费 = 按用量付费")

        self._ollama_combo = QComboBox()
        self._ollama_combo.addItems(["关闭", "Ollama (本地)"])
        self._ollama_combo.setFixedWidth(180)
        self._form_row(group, "本地 LLM", self._ollama_combo)

        self._auto_summary_combo = QComboBox()
        self._auto_summary_combo.addItems(["关闭", "转写后自动生成", "手动触发"])
        self._auto_summary_combo.setFixedWidth(180)
        self._form_row(group, "自动摘要", self._auto_summary_combo)

        self._auto_correction_combo = QComboBox()
        self._auto_correction_combo.addItems(["关闭", "转写后自动纠错"])
        self._auto_correction_combo.setFixedWidth(180)
        self._form_row(group, "转写纠错", self._auto_correction_combo,
                       hint_text="LLM 纠错转写错字、乱码、标点")

    def _on_vendor_changed(self, vendor):
        from model_registry import get_models_for_vendor
        models = get_models_for_vendor(vendor)
        self._model_combo.clear()
        self._model_combo.addItems(models if models else [])

    def _toggle_api_key(self):
        if self._api_key_entry.echoMode() == QLineEdit.Password:
            self._api_key_entry.setEchoMode(QLineEdit.Normal)
            self._api_key_toggle.setText("🔒")
        else:
            self._api_key_entry.setEchoMode(QLineEdit.Password)
            self._api_key_toggle.setText("👁")

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
        btn_row.setSpacing(8)
        self._btn_check_models = QPushButton("检查模型")
        self._btn_check_models.setFixedSize(100, 32)
        self._btn_check_models.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 6px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {C_BTN_HOVER}; }}
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

        group.layout().addSpacing(4)

        dev_info = QLabel("制作者：刘家诚")
        dev_info.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
        group.layout().addWidget(dev_info)

        group.layout().addSpacing(4)

        for line in [
            "引擎: FunASR SenseVoice + CAM++ + ct-punc (本地推理)",
            "AI: MiMo 云端 (摘要/纠错) + 内网大模型 (预留)",
            "支持格式: WAV / MP3 / M4A / FLAC / OGG / OGA / OPUS",
        ]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
            group.layout().addWidget(lbl)

    def _create_group(self, title, layout):
        """创建分组卡片（标题在卡片外面）"""
        layout.addSpacing(8)
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
        card_layout.setSpacing(8)
        layout.addWidget(card)
        return card

    def _form_row(self, parent, label_text, control_widget, hint_text=None):
        """创建标准表单行：标签(90px右对齐) + 控件 + [可选提示]"""
        row = QHBoxLayout()
        row.setSpacing(12)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(90)
        lbl.setStyleSheet(f"""
            color: {C_TXT2};
            font-family: {FONT_FAMILY};
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)

        row.addWidget(control_widget)
        row.addStretch()
        parent.layout().addLayout(row)

        if hint_text:
            hint_row = QHBoxLayout()
            hint_row.setSpacing(12)
            placeholder = QLabel("")
            placeholder.setFixedWidth(90)
            hint_row.addWidget(placeholder)
            hint = QLabel(hint_text)
            hint.setStyleSheet(f"""
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 10px;
                background: transparent;
                border: none;
            """)
            hint_row.addWidget(hint)
            hint_row.addStretch()
            parent.layout().addLayout(hint_row)

        return control_widget

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
            name_lbl.setFixedWidth(160)
            name_lbl.setStyleSheet(f"color: {C_TXT1}; font-size: 12px; font-weight: bold; background: transparent; border: none;")
            row.addWidget(name_lbl)

            desc_lbl = QLabel(state["info"]["description"])
            desc_lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 11px; background: transparent; border: none;")
            row.addWidget(desc_lbl, 1)

            size_lbl = QLabel(state["info"]["size_hint"])
            size_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
            size_lbl.setFixedWidth(60)
            row.addWidget(size_lbl)

            status_text = "已缓存" if state["cached"] else ("必需" if state["info"]["required"] else "可选")
            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent; border: none;")
            status_lbl.setFixedWidth(40)
            row.addWidget(status_lbl)

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

        if hasattr(self, '_vendor_combo'):
            vendor = self._config.get("ai_vendor", "小米")
            idx = self._vendor_combo.findText(vendor)
            if idx >= 0:
                self._vendor_combo.setCurrentIndex(idx)
        if hasattr(self, '_model_combo'):
            model = self._config.get("ai_model", "MiMo")
            idx = self._model_combo.findText(model)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
        if hasattr(self, '_access_mode_combo'):
            mode = self._config.get("ai_access_mode", "按量计费")
            idx = self._access_mode_combo.findText(mode)
            if idx >= 0:
                self._access_mode_combo.setCurrentIndex(idx)
        if hasattr(self, '_ollama_combo'):
            ollama = self._config.get("ollama_enabled", "关闭")
            if isinstance(ollama, bool):
                ollama = "Ollama (本地)" if ollama else "关闭"
            idx = self._ollama_combo.findText(ollama)
            if idx >= 0:
                self._ollama_combo.setCurrentIndex(idx)
        if hasattr(self, '_auto_summary_combo'):
            summary = self._config.get("auto_summary", "转写后自动生成")
            if isinstance(summary, bool):
                summary = "转写后自动生成" if summary else "关闭"
            idx = self._auto_summary_combo.findText(summary)
            if idx >= 0:
                self._auto_summary_combo.setCurrentIndex(idx)
        if hasattr(self, '_auto_correction_combo'):
            correction = self._config.get("auto_correction", "转写后自动纠错")
            if isinstance(correction, bool):
                correction = "转写后自动纠错" if correction else "关闭"
            idx = self._auto_correction_combo.findText(correction)
            if idx >= 0:
                self._auto_correction_combo.setCurrentIndex(idx)

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

        if hasattr(self, '_vendor_combo'):
            self._config.set("ai_vendor", self._vendor_combo.currentText())
        if hasattr(self, '_model_combo'):
            self._config.set("ai_model", self._model_combo.currentText())
        if hasattr(self, '_api_key_entry'):
            self._config.set("ai_api_key", self._api_key_entry.text().strip())
            self._config.set("mimo_api_key", self._api_key_entry.text().strip())
        if hasattr(self, '_access_mode_combo'):
            self._config.set("ai_access_mode", self._access_mode_combo.currentText())
        if hasattr(self, '_ollama_combo'):
            self._config.set("ollama_enabled", self._ollama_combo.currentText())
        if hasattr(self, '_auto_summary_combo'):
            self._config.set("auto_summary", self._auto_summary_combo.currentText())
        if hasattr(self, '_auto_correction_combo'):
            self._config.set("auto_correction", self._auto_correction_combo.currentText())

        if hasattr(self, '_vb_cable_cb'):
            self._config.set("use_vb_cable", self._vb_cable_cb.isChecked())
        if hasattr(self, '_notification_cb'):
            self._config.set("enable_notification", self._notification_cb.isChecked())

        self._config.save()
        self._log("设置已保存")
        self.settings_changed.emit()
        QMessageBox.information(self, "成功", "设置已保存")
