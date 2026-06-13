"""
文件列表视图组件（PySide6 版本）

支持功能：
- Grid 布局 7 列（队列、文件名、主题、时长、大小、状态、操作）
- 行点击选中（非复选框）
- 选中标记（● 前缀）和合并文件显示（📎 前缀）
- 状态图标（ICON_STATUS/ICON_COLOR）
- 丰富的操作按钮
- 增量更新（不全量重建）
- 空状态处理
- 队列位置显示
"""

from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QToolTip
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor

from file_manager import FileStatus
from gui.styles import (
    C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_WARN, C_ERROR, C_TXT1, C_TXT2, C_TXT3,
    FONT_FAMILY, ICON_STATUS, ICON_ACTION, ICON_COLOR, TOOLTIPS,
)


class FileListView(QFrame):
    """文件列表视图组件"""

    file_selected = Signal(list)
    file_action = Signal(str, str)

    _ST_COLORS = {
        FileStatus.PENDING: C_TXT3, FileStatus.PROCESSING: C_WARN,
        FileStatus.DONE: C_SUCCESS, FileStatus.FAILED: C_ERROR,
    }
    _ST_MAP = {
        FileStatus.PENDING: "待转写", FileStatus.PROCESSING: "转写中...",
        FileStatus.DONE: "已完成", FileStatus.FAILED: "失败",
    }

    def __init__(self, parent=None, get_queue_position=None, get_queue=None):
        super().__init__(parent)

        self._get_queue_position = get_queue_position or (lambda fp: 0)
        self._get_queue = get_queue or (lambda: [])
        self._row_widgets = {}
        self._selected_files = set()

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"QFrame {{ background: transparent; border: none; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: #C0C0C0;
                border-radius: 4px;
                min-height: 30px;
            }}
        """)

        # 内容容器
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # 表头
        self._build_header()

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
        self._layout.addWidget(sep)

        # 数据区域
        self._data_widget = QWidget()
        self._data_widget.setStyleSheet("background: transparent;")
        self._data_layout = QVBoxLayout(self._data_widget)
        self._data_layout.setContentsMargins(0, 0, 0, 0)
        self._data_layout.setSpacing(0)
        self._layout.addWidget(self._data_widget, 1)

        # 空状态
        self._empty_widget = QWidget()
        self._empty_widget.setStyleSheet("background: transparent;")
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)

        empty_title = QLabel("暂无文件")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_title.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 16px;
                background: transparent;
                border: none;
            }}
        """)
        empty_layout.addWidget(empty_title)

        empty_hint = QLabel('点击「添加文件」导入音频，或使用上方录音功能')
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_hint.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        empty_layout.addWidget(empty_hint)

        self._data_layout.addWidget(self._empty_widget)
        self._empty_widget.show()

        scroll.setWidget(self._container)
        main_layout.addWidget(scroll)

    def _build_header(self):
        """构建表头"""
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {C_CARD};
                border: none;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(0)

        headers = [
            ("队列", 0), ("文件名", 1), ("主题", 3),
            ("时长", 1), ("大小", 1), ("状态", 1), ("操作", 2)
        ]
        col_weights = [0, 1, 3, 1, 1, 1, 2]

        for i, (text, weight) in enumerate(headers):
            label = QLabel(text)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {C_TXT3};
                    font-family: {FONT_FAMILY};
                    font-size: 11px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
            header_layout.addWidget(label, weight)

        self._layout.addWidget(header)

    def refresh(self, files):
        """刷新文件列表（增量更新）"""
        if not files:
            self._clear_all_rows()
            self._empty_widget.show()
            return

        self._empty_widget.hide()

        current_paths = {f.file_path for f in files}
        old_paths = list(self._row_widgets.keys())

        # 删除不再存在的行
        for path in old_paths:
            if path not in current_paths:
                self._destroy_file_row(path)

        # 更新或创建行
        for idx, f in enumerate(files):
            if f.file_path in self._row_widgets:
                self._update_file_row(f, idx)
            else:
                self._create_file_row(f, idx)

    def get_selected(self):
        return list(self._selected_files)

    def clear_selection(self):
        self._selected_files.clear()
        for fp, widgets in self._row_widgets.items():
            widgets["row"].setStyleSheet(f"""
                QWidget {{
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                }}
            """)
            self._update_name_label(fp, widgets)

    def update_action_buttons(self, file_item):
        widgets = self._row_widgets.get(file_item.file_path)
        if widgets and "action_buttons" in widgets:
            self._update_action_buttons_state(widgets["action_buttons"], file_item)

    def _clear_all_rows(self):
        for path in list(self._row_widgets.keys()):
            self._destroy_file_row(path)

    def _destroy_file_row(self, file_path):
        widgets = self._row_widgets.pop(file_path, None)
        if widgets:
            row = widgets.get("row")
            if row:
                self._data_layout.removeWidget(row)
                row.deleteLater()

    def _create_file_row(self, file_item, row_idx):
        is_sel = (file_item.file_path in self._selected_files)
        row_bg = C_ACCENT_LT if is_sel else "transparent"
        is_merged = bool(file_item.source_files)

        # 行容器
        row = QWidget()
        row.setStyleSheet(f"""
            QWidget {{
                background-color: {row_bg};
                border: none;
                border-radius: 4px;
            }}
            QWidget:hover {{
                background-color: #F0F5FF;
            }}
        """)
        row.setFixedHeight(34)
        row.setCursor(QCursor(Qt.PointingHandCursor))

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 2, 8, 2)
        row_layout.setSpacing(0)

        # 队列位置
        queue_pos = self._get_queue_position(file_item.file_path)
        queue_text = str(queue_pos) if queue_pos > 0 else ""
        q = QLabel(queue_text)
        q.setAlignment(Qt.AlignCenter)
        q.setStyleSheet(f"""
            QLabel {{
                color: {C_ACCENT if queue_text else C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        row_layout.addWidget(q, 0)

        # 文件名
        sel_mark = "● " if is_sel else "  "
        display_name = file_item.file_name
        if is_merged:
            display_name = f"📎 {file_item.file_name} ({len(file_item.source_files)}个文件)"
        nm = QLabel(f"{sel_mark}{display_name}")
        nm.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT1};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        row_layout.addWidget(nm, 1)

        # 主题
        topic_text = file_item.topic if file_item.topic else ""
        tp = QLabel(topic_text)
        tp.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2 if topic_text else C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        row_layout.addWidget(tp, 3)

        # 时长
        dur = QLabel(file_item.duration_str)
        dur.setAlignment(Qt.AlignCenter)
        dur.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        row_layout.addWidget(dur, 1)

        # 大小
        sz = QLabel(file_item.size_str)
        sz.setAlignment(Qt.AlignCenter)
        sz.setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)
        row_layout.addWidget(sz, 1)

        # 状态图标
        st_key = file_item.status.value
        st_icon = ICON_STATUS.get(st_key, "○")
        st_color = ICON_COLOR.get(st_key, C_TXT3)
        st = QLabel(st_icon)
        st.setAlignment(Qt.AlignCenter)
        st.setStyleSheet(f"""
            QLabel {{
                color: {st_color};
                font-family: {FONT_FAMILY};
                font-size: 13px;
                background: transparent;
                border: none;
            }}
        """)
        row_layout.addWidget(st, 1)

        # 操作按钮
        act_f = QWidget()
        act_f.setStyleSheet("background: transparent; border: none;")
        act_layout = QHBoxLayout(act_f)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(2)
        action_buttons = self._build_action_buttons(act_layout, file_item)
        row_layout.addWidget(act_f, 2)

        # 点击事件
        row.mousePressEvent = lambda e, fp=file_item.file_path: self._toggle_select(fp)

        self._row_widgets[file_item.file_path] = {
            "row": row, "name": nm, "topic": tp, "dur": dur,
            "size": sz, "status": st, "queue": q,
            "action_buttons": action_buttons,
        }

        # 插入到数据区域（在 empty_widget 之前）
        self._data_layout.insertWidget(self._data_layout.count() - 1, row)

    def _update_file_row(self, file_item, row_idx):
        widgets = self._row_widgets.get(file_item.file_path)
        if not widgets:
            return

        # 更新选中状态
        is_sel = (file_item.file_path in self._selected_files)
        row_bg = C_ACCENT_LT if is_sel else "transparent"
        widgets["row"].setStyleSheet(f"""
            QWidget {{
                background-color: {row_bg};
                border: none;
                border-radius: 4px;
            }}
            QWidget:hover {{
                background-color: {C_ACCENT_LT};
            }}
        """)

        # 更新队列位置
        queue_pos = self._get_queue_position(file_item.file_path)
        queue_text = str(queue_pos) if queue_pos > 0 else ""
        widgets["queue"].setText(queue_text)
        widgets["queue"].setStyleSheet(f"""
            QLabel {{
                color: {C_ACCENT if queue_text else C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)

        # 更新文件名
        self._update_name_label(file_item.file_path, widgets, file_item)

        # 更新主题
        topic_text = file_item.topic if file_item.topic else ""
        widgets["topic"].setText(topic_text)
        widgets["topic"].setStyleSheet(f"""
            QLabel {{
                color: {C_TXT2 if topic_text else C_TXT3};
                font-family: {FONT_FAMILY};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
        """)

        # 更新状态图标
        st_key = file_item.status.value
        st_icon = ICON_STATUS.get(st_key, "○")
        st_color = ICON_COLOR.get(st_key, C_TXT3)
        widgets["status"].setText(st_icon)
        widgets["status"].setStyleSheet(f"""
            QLabel {{
                color: {st_color};
                font-family: {FONT_FAMILY};
                font-size: 13px;
                background: transparent;
                border: none;
            }}
        """)

        # 更新操作按钮
        self._update_action_buttons_state(
            widgets.get("action_buttons", {}), file_item)

    def _update_name_label(self, file_path, widgets, file_item=None):
        """更新文件名标签的选中标记"""
        is_sel = (file_path in self._selected_files)
        sel_mark = "● " if is_sel else "  "
        if file_item:
            display_name = file_item.file_name
            if file_item.source_files:
                display_name = f"📎 {file_item.file_name} ({len(file_item.source_files)}个文件)"
        else:
            # 从现有文本中提取（去掉选中标记）
            current = widgets["name"].text()
            if current.startswith("● "):
                current = current[2:]
            if current.startswith("  "):
                current = current[2:]
            if current.startswith("📎 "):
                current = current[2:]
            display_name = current
        widgets["name"].setText(f"{sel_mark}{display_name}")

    def _toggle_select(self, file_path):
        if file_path in self._selected_files:
            self._selected_files.discard(file_path)
        else:
            self._selected_files.add(file_path)

        widgets = self._row_widgets.get(file_path)
        if widgets:
            is_sel = (file_path in self._selected_files)
            row_bg = C_ACCENT_LT if is_sel else "transparent"
            widgets["row"].setStyleSheet(f"""
                QWidget {{
                    background-color: {row_bg};
                    border: none;
                    border-radius: 4px;
                }}
                QWidget:hover {{
                    background-color: {C_ACCENT_LT};
                }}
            """)
            self._update_name_label(file_path, widgets)

        self.file_selected.emit(list(self._selected_files))

    def _build_action_buttons(self, layout, file_item):
        buttons = {}
        fp = file_item.file_path

        def _make_btn(text, tooltip, color, bg_color, hover_bg, action_type, is_queue=False):
            btn = QPushButton(text)
            btn.setFixedSize(28 if not is_queue else 24, 26 if not is_queue else 24)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {color};
                    border: none;
                    border-radius: 4px;
                    font-family: {FONT_FAMILY};
                    font-size: {"13" if not is_queue else "11"}px;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                }}
                QPushButton:disabled {{
                    color: {C_TXT3};
                }}
            """)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda: self.file_action.emit(action_type, fp))
            layout.addWidget(btn)
            return btn

        # DONE 状态按钮
        buttons["preview"] = _make_btn(
            ICON_ACTION["preview"], TOOLTIPS["preview"],
            C_ACCENT, "#E8F0FE", "#D0E0FF", "preview")
        buttons["open"] = _make_btn(
            ICON_ACTION["open"], TOOLTIPS["open"],
            "white", C_ACCENT, C_BTN_HOVER, "open")
        buttons["speaker"] = _make_btn(
            ICON_ACTION["speaker"], TOOLTIPS["speaker"],
            "#7B2FF2", "#F0E6FF", "#E0D0FF", "speaker")
        buttons["retry"] = _make_btn(
            ICON_ACTION["retry"], TOOLTIPS["retry"],
            C_WARN, "#FFF0E0", "#FFE0C0", "retry")
        buttons["export"] = _make_btn(
            ICON_ACTION["export"], TOOLTIPS["export"],
            C_ACCENT, "#E8F0FE", "#D0E0FF", "export")

        # PROCESSING 状态按钮
        buttons["stop"] = _make_btn(
            ICON_ACTION["stop"], TOOLTIPS["stop"],
            C_WARN, "#FFF0E0", "#FFE0C0", "stop")

        # PENDING/默认状态按钮
        buttons["transcribe"] = _make_btn(
            ICON_ACTION["transcribe"], TOOLTIPS["transcribe"],
            "white", C_SUCCESS, "#0A5E0A", "transcribe")

        # 队列管理按钮
        buttons["move_up"] = _make_btn(
            "▲", TOOLTIPS["move_up"],
            C_ACCENT, "transparent", "#E8F0FE", "move_up", is_queue=True)
        buttons["move_down"] = _make_btn(
            "▼", TOOLTIPS["move_down"],
            C_ACCENT, "transparent", "#E8F0FE", "move_down", is_queue=True)
        buttons["remove_from_queue"] = _make_btn(
            "✕", TOOLTIPS["remove"],
            C_ERROR, "transparent", "#FDE8E8", "remove", is_queue=True)

        # 根据初始状态设置可见性
        self._update_action_buttons_state(buttons, file_item)

        return buttons

    def _update_action_buttons_state(self, buttons, file_item):
        if not buttons:
            return

        status = file_item.status
        has_result = bool(file_item.result_path)
        is_done = (status == FileStatus.DONE and has_result)
        is_processing = (status == FileStatus.PROCESSING)

        # DONE 状态按钮组
        for key in ("preview", "open", "speaker", "retry", "export"):
            if key in buttons:
                buttons[key].setVisible(is_done)

        # PROCESSING 状态按钮
        if "stop" in buttons:
            buttons["stop"].setVisible(is_processing)

        # PENDING/默认状态按钮
        if "transcribe" in buttons:
            buttons["transcribe"].setVisible(not is_done and not is_processing)

        # 队列管理按钮
        in_queue = False
        queue_idx = 0
        queue_len = 0
        if not is_done and not is_processing:
            queue = self._get_queue()
            if file_item.file_path in queue:
                in_queue = True
                queue_idx = queue.index(file_item.file_path)
                queue_len = len(queue)

        if "move_up" in buttons:
            if in_queue:
                buttons["move_up"].setEnabled(queue_idx > 0)
                buttons["move_up"].setVisible(True)
            else:
                buttons["move_up"].setVisible(False)

        if "move_down" in buttons:
            if in_queue:
                buttons["move_down"].setEnabled(queue_idx < queue_len - 1)
                buttons["move_down"].setVisible(True)
            else:
                buttons["move_down"].setVisible(False)

        if "remove_from_queue" in buttons:
            buttons["remove_from_queue"].setVisible(in_queue)
