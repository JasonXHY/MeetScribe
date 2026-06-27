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
from PySide6.QtCore import Qt, Signal, QThread, QSize
from PySide6.QtGui import QFont

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER, C_SUCCESS, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, C_WARN, FONT_FAMILY, MODEL_CACHE_DIR,
    APP_VERSION, APP_NAME, APP_NAME_EN,
)
from gui.icons import icon_api_key_visible, icon_api_key_hidden, IconColors, icon_status_done, icon_status_failed

logger = logging.getLogger("MeetScribe")


class ModelDownloadWorker(QThread):
    """模型下载工作线程"""
    finished = Signal(bool, str)  # success, message
    progress = Signal(int, str)

    def __init__(self, model_manager, parent=None):
        super().__init__(parent)
        self._model_manager = model_manager

    def run(self):
        try:
            def _cb(msg):
                self.progress.emit(0, str(msg))
            success, msg = self._model_manager.download_all_missing(progress_callback=_cb)
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
        self._init_model_manager()
        self._build()
        self._restore_config()

    def _init_model_manager(self):
        try:
            from transcriber import ModelManager
            self._model_manager = ModelManager(MODEL_CACHE_DIR)
        except Exception as e:
            logger.warning(f"Failed to init ModelManager: {e}")

    def eventFilter(self, obj, event):
        """阻止 ComboBox 滚轮变更值，但允许页面继续滚动"""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
        if event.type() == QEvent.Wheel and isinstance(obj, QComboBox):
            # 将滚轮事件转发给父容器，让页面继续滚动
            parent = obj.parentWidget()
            if parent:
                QApplication.sendEvent(parent, event)
            return True  # 拦截 ComboBox 自身处理
        return super().eventFilter(obj, event)

    def _disable_combo_wheel(self, combo):
        """禁用 ComboBox 滚轮事件"""
        combo.installEventFilter(self)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(8)

        title = QLabel("设置")
        title.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT1};
                font-family: {FONT_FAMILY};
                font-size: 24px;
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
        self._scroll_layout.setSpacing(10)

        self._build_path_section(self._scroll_layout)
        self._build_engine_section(self._scroll_layout)
        self._build_ai_section(self._scroll_layout)
        self._build_model_section(self._scroll_layout)
        self._build_audio_section(self._scroll_layout)
        self._build_notification_section(self._scroll_layout)
        self._build_about_section(self._scroll_layout)

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        save_btn_row = QHBoxLayout()
        save_btn_row.setContentsMargins(0, 16, 0, 0)
        save_btn = QPushButton("保存设置")
        save_btn.setFixedSize(160, 44)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 24px;
                min-height: 44px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {C_BTN_HOVER};
            }}
        """)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        save_btn_row.addWidget(save_btn)
        save_btn_row.addStretch()
        layout.addLayout(save_btn_row)

    def _build_path_section(self, layout):
        """存储路径设置"""
        group = self._create_group("存储路径", layout)
        self._rec_dir_entry = self._create_path_row(
            group, "录音保存目录",
            self._config.get("recording_dir", "") if self._config else "")
        # 转写输出目录：权威键为 transcript_dir（与 _on_save 写入及
        # app.get_output_dir() 读取一致）。回退 output_dir 仅为兼容旧配置。
        out_dir_default = ""
        if self._config:
            out_dir_default = self._config.get("transcript_dir", "") or self._config.get("output_dir", "")
        self._out_dir_entry = self._create_path_row(
            group, "转写输出目录", out_dir_default)

    def _build_engine_section(self, layout):
        """转写引擎设置（含四项引擎参数）"""
        group = self._create_group("转写引擎", layout)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["FunASR (本地)", "MiMo ASR (云端)"])
        self._engine_combo.setFixedWidth(200)
        current_engine = self._config.get("transcription_engine", "funasr") if self._config else "funasr"
        self._engine_combo.setCurrentIndex(0 if current_engine == "funasr" else 1)
        self._form_row(group, "转写模式", self._engine_combo)
        self._disable_combo_wheel(self._engine_combo)

        engine_items = [
            ("标点恢复", ["自动 (ct-punc)", "关闭"], "_punc_var"),
            ("乱码过滤", ["开启 (中文模式)", "关闭"], "_garble_var"),
            ("VAD 灵敏度", ["适中 (推荐)", "高 (更多分段)", "低 (更少分段)"], "_vad_var"),
            ("运算设备", ["CPU", "CUDA (GPU)"], "_device_var"),
        ]
        for label_text, values, attr in engine_items:
            combo = QComboBox()
            combo.addItems(values)
            combo.setFixedWidth(200)
            setattr(self, attr, combo)
            self._form_row(group, label_text, combo)
            self._disable_combo_wheel(combo)

    def _build_ai_section(self, layout):
        """AI 服务设置"""
        group = self._create_group("AI 增强", layout)

        try:
            from model_registry import get_vendor_list, get_models_for_vendor
        except ImportError:
            get_vendor_list = lambda: ["小米 MiMo"]
            get_models_for_vendor = lambda v: ["MiMo"]

        self._vendor_combo = QComboBox()
        self._vendor_combo.addItems(get_vendor_list())
        self._vendor_combo.setFixedWidth(200)
        self._vendor_combo.currentTextChanged.connect(self._on_vendor_changed)
        self._form_row(group, "模型厂商", self._vendor_combo)
        self._disable_combo_wheel(self._vendor_combo)

        self._model_combo = QComboBox()
        self._model_combo.addItems(get_models_for_vendor("小米 MiMo"))
        self._model_combo.setFixedWidth(200)
        self._form_row(group, "摘要模型", self._model_combo)
        self._disable_combo_wheel(self._model_combo)

        self._api_key_entry = QLineEdit()
        self._api_key_entry.setEchoMode(QLineEdit.Password)
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
        api_key = self._config.get("ai_user_api_key", "") if self._config else ""
        self._api_key_entry.setText(api_key)
        self._api_key_toggle = QPushButton()
        self._api_key_toggle.setFixedSize(32, 32)
        self._api_key_toggle.setIcon(icon_api_key_visible())
        self._api_key_toggle.setIconSize(QSize(16, 16))
        self._api_key_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: #F9FAFB;
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: #F3F4F6;
                border-color: #D1D5DB;
            }}
        """)
        self._api_key_toggle.setCursor(Qt.PointingHandCursor)
        self._api_key_toggle.clicked.connect(self._toggle_api_key)
        
        # API Key 容器
        api_key_inner = QHBoxLayout()
        api_key_inner.setSpacing(4)
        api_key_inner.setContentsMargins(0, 0, 0, 0)
        api_key_inner.addWidget(self._api_key_entry, 1)
        api_key_inner.addWidget(self._api_key_toggle)
        api_key_container = QWidget()
        api_key_container.setLayout(api_key_inner)
        api_key_container.setStyleSheet("background: transparent; border: none;")

        # API Key 状态提示
        has_user_key = bool(self._config.get("ai_user_api_key", "")) if self._config else False
        has_default_key = bool(self._config.get("ai_default_api_key", "")) if self._config else False
        if has_user_key:
            api_key_hint = "已配置自定义 Key"
        elif has_default_key:
            api_key_hint = "使用内置 Key（不可查看）"
        else:
            api_key_hint = "未配置 API Key，AI 功能不可用"

        self._api_key_hint = QLabel(api_key_hint)
        hint_color = C_SUCCESS if has_user_key else C_TXT3
        self._api_key_hint.setStyleSheet(f"""
            QLabel {{
                color: {hint_color};
                font-family: {FONT_FAMILY};
                font-size: 10px;
                background: transparent;
                border: none;
                padding-left: 108px;
            }}
        """)
        self._form_row(group, "API Key", api_key_container)
        # 在 form_row 之后添加提示
        group.layout().addWidget(self._api_key_hint)

        self._access_mode_combo = QComboBox()
        self._access_mode_combo.addItems(["按量计费", "Token Plan"])
        self._access_mode_combo.setFixedWidth(200)
        self._form_row(group, "接入模式", self._access_mode_combo,
                       hint_text="Token Plan = 包月套餐 | 按量计费 = 按用量付费")
        self._disable_combo_wheel(self._access_mode_combo)

        self._ollama_combo = QComboBox()
        self._ollama_combo.addItems(["关闭", "Ollama (本地)"])
        self._ollama_combo.setFixedWidth(200)
        self._form_row(group, "本地 LLM", self._ollama_combo)
        self._disable_combo_wheel(self._ollama_combo)

        # Ollama 服务地址输入框（SET-016：QCheckBox/开关 + 地址输入）
        self._ollama_url_entry = QLineEdit("http://localhost:11434/v1")
        self._ollama_url_entry.setFixedWidth(280)
        self._form_row(group, "Ollama 地址", self._ollama_url_entry,
                       hint_text="本地 Ollama 服务地址，默认 http://localhost:11434/v1")

        # Ollama 模型名输入框
        self._ollama_model_entry = QLineEdit("qwen3:1.7b")
        self._ollama_model_entry.setFixedWidth(200)
        self._form_row(group, "Ollama 模型", self._ollama_model_entry,
                       hint_text="本地 LLM 模型名，默认 qwen3:1.7b")

        self._auto_summary_combo = QComboBox()
        self._auto_summary_combo.addItems(["转写后自动生成", "关闭", "手动触发"])
        self._auto_summary_combo.setFixedWidth(200)
        self._form_row(group, "自动摘要", self._auto_summary_combo)
        self._disable_combo_wheel(self._auto_summary_combo)

        self._auto_correction_combo = QComboBox()
        self._auto_correction_combo.addItems(["关闭", "转写后自动纠错"])
        self._auto_correction_combo.setFixedWidth(200)
        self._form_row(group, "转写纠错", self._auto_correction_combo,
                       hint_text="LLM 纠错转写错字、乱码、标点")
        self._disable_combo_wheel(self._auto_correction_combo)

    def _on_vendor_changed(self, vendor):
        from model_registry import get_models_for_vendor
        models = get_models_for_vendor(vendor)
        self._model_combo.clear()
        self._model_combo.addItems(models if models else [])

    def _toggle_api_key(self):
        if self._api_key_entry.echoMode() == QLineEdit.Password:
            self._api_key_entry.setEchoMode(QLineEdit.Normal)
            self._api_key_toggle.setIcon(icon_api_key_hidden())
        else:
            self._api_key_entry.setEchoMode(QLineEdit.Password)
            self._api_key_toggle.setIcon(icon_api_key_visible())

    def _build_model_section(self, layout):
        """模型管理（含模型详情列表 + 下载按钮）"""
        group = self._create_group("模型管理", layout)

        # 1. 缓存路径
        row_cache = QHBoxLayout()
        lbl_cache = QLabel(f"模型缓存: {MODEL_CACHE_DIR}")
        lbl_cache.setStyleSheet(f"""
            color: {C_TXT3};
            font-size: 11px;
            font-family: "Cascadia Code", Consolas, monospace;
            background-color: #F9FAFB;
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
        """)
        lbl_cache.setWordWrap(True)
        row_cache.addWidget(lbl_cache)
        row_cache.addStretch()
        group.layout().addLayout(row_cache)

        # 2. 模型行容器（固定位置，动态填充）
        self._model_rows_container = QWidget()
        self._model_rows_container.setStyleSheet("background: transparent; border: none;")
        self._model_rows_layout = QVBoxLayout(self._model_rows_container)
        self._model_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._model_rows_layout.setSpacing(0)
        group.layout().addWidget(self._model_rows_container)

        # 3. 状态标签（固定位置）
        self._model_status_label = QLabel("")
        self._model_status_label.setStyleSheet(
            f"color: {C_TXT3}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
        )
        group.layout().addWidget(self._model_status_label)

        # 4. 按钮行（固定位置，永远在最底部）
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_check_models = QPushButton("检查模型")
        self._btn_check_models.setFixedSize(120, 40)
        self._btn_check_models.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                min-height: 40px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {C_BTN_HOVER};
            }}
        """)
        self._btn_check_models.setCursor(Qt.PointingHandCursor)
        self._btn_check_models.clicked.connect(self._check_models)
        btn_row.addWidget(self._btn_check_models)

        self._btn_download_models = QPushButton("下载缺失模型")
        self._btn_download_models.setFixedSize(150, 40)
        self._btn_download_models.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                min-height: 40px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        self._btn_download_models.setCursor(Qt.PointingHandCursor)
        self._btn_download_models.clicked.connect(self._download_missing_models)
        btn_row.addWidget(self._btn_download_models)

        btn_row.addStretch()
        group.layout().addLayout(btn_row)

        # 5. 初始填充模型状态
        self._refresh_model_status()

    def _build_audio_section(self, layout):
        """音频设备设置（v1.0: 已移除 VB-Cable，使用 WASAPI Loopback）"""
        group = self._create_group("音频设备", layout)
        hint = QLabel("系统音频录制使用 Windows 内置 WASAPI Loopback，无需额外安装驱动")
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

        dev_info = QLabel(f"制作者：刘家诚 | {APP_NAME_EN}")
        dev_info.setStyleSheet(f"color: {C_TXT2}; font-size: 12px; background: transparent; border: none;")
        group.layout().addWidget(dev_info)

        group.layout().addSpacing(4)

        for line in [
            "引擎: FunASR SenseVoice + CAM++ + ct-punc (本地推理)",
            "AI: 支持国内主流云端模型厂商",
            "支持格式: WAV / MP3 / M4A / FLAC / OGG / OGA / OPUS",
        ]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
            group.layout().addWidget(lbl)

    def _create_group(self, title, layout):
        """创建分组卡片（标题在卡片外面）"""
        layout.addSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2};
                font-family: {FONT_FAMILY};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
                padding-left: 2px;
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
        row.setSpacing(8)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(100)
        lbl.setStyleSheet(f"""
            color: {C_TXT2};
            font-family: {FONT_FAMILY};
            font-size: 13px;
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
            placeholder.setFixedWidth(100)
            placeholder.setStyleSheet("background: transparent; border: none;")
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
        """创建路径输入行（使用 _form_row 统一样式）"""
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
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(64)
        browse_btn.setCursor(Qt.PointingHandCursor)
        if "录音" in label_text:
            browse_btn.clicked.connect(lambda: self._browse_dir(entry, "选择录音目录"))
        else:
            browse_btn.clicked.connect(lambda: self._browse_dir(entry, "选择输出目录"))
        container = QWidget()
        container_row = QHBoxLayout(container)
        container_row.setContentsMargins(0, 0, 0, 0)
        container_row.setSpacing(6)
        container_row.addWidget(entry, 1)
        container_row.addWidget(browse_btn)
        container.setStyleSheet("background: transparent; border: none;")
        self._form_row(parent, label_text, container)
        return entry

    def _browse_dir(self, entry, title):
        """浏览目录"""
        path = QFileDialog.getExistingDirectory(self, title, entry.text())
        if path:
            entry.setText(path)

    def _refresh_model_status(self):
        """刷新模型状态显示"""
        # 清空模型行容器中的所有内容
        while self._model_rows_layout.count():
            item = self._model_rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self._model_manager:
            self._model_status_label.setText("模型管理器未初始化")
            self._model_status_label.setStyleSheet(
                f"color: {C_TXT3}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
            )
            return

        status = self._model_manager.check_all_models()
        model_ids = list(status.keys())

        for i, (model_id, state) in enumerate(status.items()):
            # 模型行
            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent; border: none;")
            row = QHBoxLayout(row_widget)
            row.setSpacing(4)
            row.setContentsMargins(0, 4, 0, 4)

            if state["cached"]:
                icon = icon_status_done()
                color = C_SUCCESS
            else:
                icon = icon_status_failed() if state["info"]["required"] else icon_status_done()
                color = C_ERROR if state["info"]["required"] else C_WARN

            icon_lbl = QLabel()
            icon_lbl.setFixedWidth(24)
            icon_lbl.setPixmap(icon.pixmap(16, 16))
            icon_lbl.setStyleSheet("background: transparent; border: none;")
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

            self._model_rows_layout.addWidget(row_widget)

            # 分隔线（非最后一行）
            if i < len(model_ids) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background-color: #F3F4F6; border: none;")
                self._model_rows_layout.addWidget(sep)

        # 更新状态标签
        missing = self._model_manager.get_missing_models(required_only=True)
        if missing:
            self._model_status_label.setText(f"缺少 {len(missing)} 个必需模型")
            self._model_status_label.setStyleSheet(
                f"color: {C_ERROR}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
            )
        else:
            self._model_status_label.setText("所有必需模型已就绪")
            self._model_status_label.setStyleSheet(
                f"color: {C_SUCCESS}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
            )

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
        self._download_worker.progress.connect(self._on_download_progress)
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

    def _on_download_progress(self, percent, message):
        if hasattr(self, '_model_status_label'):
            self._model_status_label.setText(message)

    def _restore_config(self):
        """从配置恢复 UI 状态"""
        if not self._config:
            return

        self._punc_var.setCurrentText(self._config.get("punc_restore", "自动 (ct-punc)"))
        self._garble_var.setCurrentText(self._config.get("garble_filter", "开启 (中文模式)"))
        self._vad_var.setCurrentText(self._config.get("vad_sensitivity", "适中 (推荐)"))
        self._device_var.setCurrentText(self._config.get("device", "CPU"))

        if hasattr(self, '_vendor_combo'):
            vendor = self._config.get("ai_vendor", "小米 MiMo")
            idx = self._vendor_combo.findText(vendor)
            if idx >= 0:
                self._vendor_combo.setCurrentIndex(idx)
        if hasattr(self, '_model_combo'):
            model = self._config.get("ai_model", "mimo-v2.5")
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
        if hasattr(self, '_ollama_url_entry'):
            self._ollama_url_entry.setText(
                self._config.get("ollama_url", "http://localhost:11434/v1"))
        if hasattr(self, '_ollama_model_entry'):
            self._ollama_model_entry.setText(
                self._config.get("ollama_model", "qwen3:1.7b"))
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

    def _refresh_api_key_hint(self):
        """刷新 API Key 状态提示"""
        if not self._config:
            return
        has_user_key = bool(self._config.get("ai_user_api_key", ""))
        has_default_key = bool(self._config.get("ai_default_api_key", ""))
        if has_user_key:
            self._api_key_hint.setText("已配置自定义 Key")
            self._api_key_hint.setStyleSheet(f"color: {C_SUCCESS}; font-size: 10px; background: transparent; border: none; padding-left: 108px;")
        elif has_default_key:
            self._api_key_hint.setText("使用内置 Key（不可查看）")
            self._api_key_hint.setStyleSheet(f"color: {C_TXT3}; font-size: 10px; background: transparent; border: none; padding-left: 108px;")
        else:
            self._api_key_hint.setText("未配置 API Key，AI 功能不可用")
            self._api_key_hint.setStyleSheet(f"color: {C_ERROR}; font-size: 10px; background: transparent; border: none; padding-left: 108px;")

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
            key_text = self._api_key_entry.text().strip()
            self._config.set("ai_user_api_key", key_text)
        if hasattr(self, '_access_mode_combo'):
            self._config.set("ai_access_mode", self._access_mode_combo.currentText())
        if hasattr(self, '_ollama_combo'):
            self._config.set("ollama_enabled", self._ollama_combo.currentText())
        if hasattr(self, '_ollama_url_entry'):
            self._config.set("ollama_url", self._ollama_url_entry.text().strip())
        if hasattr(self, '_ollama_model_entry'):
            self._config.set("ollama_model", self._ollama_model_entry.text().strip())
        if hasattr(self, '_auto_summary_combo'):
            self._config.set("auto_summary", self._auto_summary_combo.currentText())
        if hasattr(self, '_auto_correction_combo'):
            self._config.set("auto_correction", self._auto_correction_combo.currentText())

        if hasattr(self, '_notification_cb'):
            self._config.set("enable_notification", self._notification_cb.isChecked())

        self._config.save()
        self._refresh_api_key_hint()
        self._log("设置已保存")
        self.settings_changed.emit()
        QMessageBox.information(self, "成功", "设置已保存")
