"""
侧耳倾听 文件列表视图组件（PySide6 重新设计版）

核心改进：
1. 使用 QTableWidget 替代 QGridLayout，原生支持列宽比例调整
2. 使用 QIcon 替代 emoji，渲染一致
3. 操作列表头居中对齐
4. 文件名列窄、主题列宽，防止窗口缩小时遮挡
5. 数据行顶部对齐
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter

from gui.icons import (
    create_icon, icon_play, icon_stop, icon_preview, icon_open_folder,
    icon_speaker, icon_retry, icon_export, icon_delete, icon_merge,
    get_status_icon, get_status_color, IconColors
)

logger = logging.getLogger("MeetScribe")


class FileListView(QWidget):
    """
    文件列表视图组件

    使用 QTableWidget 实现，支持：
    - 列宽按比例自动调整（窗口缩放时保持比例）
    - 文件名列较窄（用户最不需要的信息）
    - 主题列较宽
    - 操作列表头居中
    - 数据行顶部对齐
    """

    # 列定义：(标题, 初始宽度比例, 对齐方式)
    COLUMNS = [
        ("队列",   0.04, Qt.AlignCenter),
        ("文件名", 0.22, Qt.AlignLeft | Qt.AlignVCenter),
        ("主题",   0.25, Qt.AlignLeft | Qt.AlignVCenter),
        ("时长",   0.10, Qt.AlignCenter),
        ("大小",   0.10, Qt.AlignCenter),
        ("状态",   0.10, Qt.AlignCenter),
        ("操作",   0.19, Qt.AlignLeft | Qt.AlignVCenter),  # 操作列表头居中
    ]

    # 信号
    file_selected = Signal(list)  # 选中文件列表
    file_action = Signal(str, str)  # (action, file_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_data = []  # 文件数据列表
        self._selected_paths = set()
        # 增量更新状态（FILE-004）：file_path -> 该行已渲染的快照，用于检测变化
        # {path: {"status": str, "name": str, "topic": str,
        #         "duration": str, "size": str, "queue_pos": Any}}
        self._row_state = {}
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建表格
        self._table = QTableWidget()
        self._setup_table()
        layout.addWidget(self._table)

    def _setup_table(self):
        """配置表格属性"""
        # 列数
        self._table.setColumnCount(len(self.COLUMNS))

        # 设置表头
        headers = [col[0] for col in self.COLUMNS]
        self._table.setHorizontalHeaderLabels(headers)

        # 表头样式
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)  # 不自动拉伸最后一列
        header.setDefaultAlignment(Qt.AlignLeft)
        header.setSectionsClickable(False)
        header.setHighlightSections(False)

        # 设置列宽模式为 Interactive（允许用户调整，但初始按比例）
        for i, (_, ratio, _) in enumerate(self.COLUMNS):
            header.setSectionResizeMode(i, QHeaderView.Interactive)

        # 表格属性
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(38)  # 行高
        self._table.verticalHeader().setMinimumSectionSize(38)

        # 图标尺寸
        self._table.setIconSize(QSize(16, 16))

        # 样式
        self._table.setStyleSheet("""
            QTableWidget {
                border: none;
            }
            QTableWidget::item {
                border-bottom: 1px solid #F3F4F6;
            }
            QTableWidget::item:hover {
                background-color: #F9FAFB;
            }
        """)

        # 信号
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    def resizeEvent(self, event):
        """窗口大小变化时按比例调整列宽"""
        super().resizeEvent(event)
        self._adjust_column_widths()

    def showEvent(self, event):
        """首次显示时延迟调整列宽，确保 viewport 宽度已确定"""
        super().showEvent(event)
        QTimer.singleShot(0, self._adjust_column_widths)

    def _adjust_column_widths(self):
        """按比例调整列宽"""
        total_width = self._table.viewport().width()
        if total_width <= 0:
            return

        for i, (_, ratio, _) in enumerate(self.COLUMNS):
            width = int(total_width * ratio)
            self._table.setColumnWidth(i, width)

    def set_files(self, files):
        """
        设置文件列表数据。

        Args:
            files: 文件数据列表，每个元素为 dict:
                {
                    "id": str,
                    "path": str,
                    "name": str,
                    "topic": str,
                    "duration": str,
                    "size": str,
                    "status": str,  # "pending" | "processing" | "done" | "failed"
                    "queue_pos": int,
                }
        """
        self.refresh(files)

    def refresh(self, files):
        """
        增量刷新文件列表（FILE-004）。

        以 ``file_path`` 为主键 diff 当前已渲染状态与新数据：
        - 新增文件 → 追加行；
        - 删除文件 → 移除对应行；
        - 顺序变化 → 移动行；
        - 状态/时长/主题等变化 → 只更新该行受影响的单元格/按钮；
        若 files 未变化，则不重建任何行（控件实例保持不变）。

        Args:
            files: 同 ``set_files`` 的文件数据 dict 列表。
        """
        files = files or []
        self._file_data = files

        self._apply_incremental(files)

        # 空状态提示
        if not files:
            self._table.setRowCount(0)
            self._row_state.clear()
            if not hasattr(self, '_empty_widget'):
                from PySide6.QtWidgets import QVBoxLayout
                self._empty_widget = QWidget()
                empty_layout = QVBoxLayout(self._empty_widget)
                empty_layout.setAlignment(Qt.AlignCenter)

                icon_lbl = QLabel("📁")
                icon_lbl.setStyleSheet("font-size: 40px; color: #D1D5DB; background: transparent; border: none;")
                icon_lbl.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(icon_lbl)

                title_lbl = QLabel("暂无文件")
                title_lbl.setStyleSheet("font-size: 15px; color: #9CA3AF; font-weight: 500; background: transparent; border: none;")
                title_lbl.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(title_lbl)

                hint_lbl = QLabel("点击「添加文件」导入音频")
                hint_lbl.setStyleSheet("font-size: 12px; color: #9CA3AF; background: transparent; border: none;")
                hint_lbl.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(hint_lbl)

                self._empty_widget.setParent(self._table)
            self._empty_widget.setGeometry(self._table.viewport().rect())
            self._empty_widget.show()
        else:
            if hasattr(self, '_empty_widget'):
                self._empty_widget.hide()

    # ------------------------------------------------------------------ #
    # 增量更新引擎（FILE-004）
    # ------------------------------------------------------------------ #
    def _current_row_paths(self) -> list:
        """按当前表格行顺序返回 file_path 列表（来自文件名单元格的 toolTip）。"""
        paths = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 1)
            paths.append(item.toolTip() if item is not None else None)
        return paths

    @staticmethod
    def _snapshot(file_info: dict) -> dict:
        """提取影响渲染的字段，用于检测某行是否发生变化。"""
        return {
            "name": file_info.get("name", ""),
            "topic": file_info.get("topic", ""),
            "duration": file_info.get("duration", ""),
            "size": file_info.get("size", ""),
            "status": file_info.get("status", "pending"),
            "queue_pos": file_info.get("queue_pos"),
        }

    def _apply_incremental(self, files: list):
        """以 file_path 为主键，将表格增量更新为 files。"""
        new_paths = [f.get("path", "") for f in files]
        new_set = set(new_paths)

        # 1) 删除不再存在的行（从底部向上删，保持其余行控件实例不变）
        for row in range(self._table.rowCount() - 1, -1, -1):
            item = self._table.item(row, 1)
            path = item.toolTip() if item is not None else None
            if path not in new_set:
                self._table.removeRow(row)
                self._row_state.pop(path, None)

        # 2) 按目标顺序就地更新 / 插入，使行顺序与 files 一致
        for target_row, file_info in enumerate(files):
            path = file_info.get("path", "")
            current_paths = self._current_row_paths()

            if path in current_paths:
                cur_row = current_paths.index(path)
                if cur_row != target_row:
                    # 顺序变化：重建该行到目标位置（保持其它行不变）
                    self._table.removeRow(cur_row)
                    self._row_state.pop(path, None)
                    self._table.insertRow(target_row)
                    self._create_row(target_row, file_info)
                    self._row_state[path] = self._snapshot(file_info)
                else:
                    # 同位置：仅当内容变化时就地更新单元格/按钮
                    snap = self._snapshot(file_info)
                    if self._row_state.get(path) != snap:
                        self._update_row(target_row, file_info)
                        self._row_state[path] = snap
            else:
                # 新增文件：在目标位置插入新行
                self._table.insertRow(target_row)
                self._create_row(target_row, file_info)
                self._row_state[path] = self._snapshot(file_info)

        self._adjust_column_widths()

    def _update_row(self, row: int, file_info: dict):
        """就地更新一行的单元格内容与操作按钮，不重建已存在的 item 实例。"""
        prev = self._row_state.get(file_info.get("path", ""), {})

        # 队列号
        queue_item = self._table.item(row, 0)
        if queue_item is not None:
            queue_item.setText(str(file_info["queue_pos"]) if file_info.get("queue_pos") else "")

        # 文件名
        name_item = self._table.item(row, 1)
        if name_item is not None:
            name_item.setText(file_info.get("name", ""))
            name_item.setToolTip(file_info.get("path", ""))

        # 主题
        topic_item = self._table.item(row, 2)
        if topic_item is not None:
            topic_item.setText(file_info.get("topic", ""))

        # 时长
        dur_item = self._table.item(row, 3)
        if dur_item is not None:
            dur_item.setText(file_info.get("duration", ""))

        # 大小
        size_item = self._table.item(row, 4)
        if size_item is not None:
            size_item.setText(file_info.get("size", ""))

        # 状态（保持 item 实例，仅更新图标/提示）
        status = file_info.get("status", "pending")
        status_item = self._table.item(row, 5)
        if status_item is not None:
            status_item.setIcon(get_status_icon(status))
            status_item.setToolTip(self._get_status_text(status))

        # 操作按钮：仅当状态变化（按钮集合依赖状态）时重建该单元格控件
        if prev.get("status") != status or self._table.cellWidget(row, 6) is None:
            self._create_action_buttons(row, file_info)

    def _create_row(self, row: int, file_info: dict):
        """创建一行数据"""
        # 队列号
        queue_item = QTableWidgetItem()
        queue_item.setTextAlignment(Qt.AlignCenter)
        if file_info.get("queue_pos"):
            queue_item.setText(str(file_info["queue_pos"]))
        else:
            queue_item.setText("")
        self._table.setItem(row, 0, queue_item)

        # 文件名（带蓝色圆点）
        name = file_info.get("name", "")
        name_item = QTableWidgetItem(name)
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_item.setToolTip(file_info.get("path", ""))
        name_item.setForeground(QColor("#111827"))
        # 蓝色圆点图标
        dot_pixmap = QPixmap(6, 6)
        dot_pixmap.fill(Qt.transparent)
        painter = QPainter(dot_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#3B82F6"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 6, 6)
        painter.end()
        name_item.setIcon(QIcon(dot_pixmap))
        self._table.setItem(row, 1, name_item)

        # 主题
        topic_item = QTableWidgetItem(file_info.get("topic", ""))
        topic_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        topic_item.setForeground(QColor("#9CA3AF"))
        self._table.setItem(row, 2, topic_item)

        # 时长
        dur_item = QTableWidgetItem(file_info.get("duration", ""))
        dur_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 3, dur_item)

        # 大小
        size_item = QTableWidgetItem(file_info.get("size", ""))
        size_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 4, size_item)

        # 状态图标
        status = file_info.get("status", "pending")
        status_item = QTableWidgetItem()
        status_item.setTextAlignment(Qt.AlignCenter)
        status_item.setIcon(get_status_icon(status))
        status_item.setToolTip(self._get_status_text(status))
        self._table.setItem(row, 5, status_item)

        # 操作按钮
        self._create_action_buttons(row, file_info)

    def _create_action_buttons(self, row: int, file_info: dict):
        """创建操作按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)

        status = file_info.get("status", "pending")
        file_path = file_info.get("path", "")

        if status == "done":
            # 已完成：预览、打开文件夹、发言人、重新转写、导出
            buttons = [
                ("预览", icon_preview(), lambda: self._on_action("preview", file_path)),
                ("打开", icon_open_folder(), lambda: self._on_action("open_folder", file_path)),
                ("发言人", icon_speaker(), lambda: self._on_action("speaker", file_path)),
                ("重试", icon_retry(), lambda: self._on_action("retry", file_path)),
                ("导出", icon_export(), lambda: self._on_action("export", file_path)),
            ]
        elif status == "failed":
            # 失败：重新转写
            buttons = [
                ("重试", icon_retry(), lambda: self._on_action("retry", file_path)),
            ]
        elif status == "processing":
            # 处理中：停止
            buttons = [
                ("停止", icon_stop(), lambda: self._on_action("stop", file_path)),
            ]
        else:
            # 待处理：转写、删除
            buttons = [
                ("转写", icon_play(), lambda: self._on_action("transcribe", file_path)),
                ("删除", icon_delete(), lambda: self._on_action("delete", file_path)),
            ]

        for text, icon, callback in buttons:
            btn = QPushButton()
            btn.setIcon(icon)
            btn.setIconSize(btn.icon().availableSizes()[0] if btn.icon().availableSizes() else (16, 16))
            btn.setToolTip(text)
            btn.setFixedSize(26, 26)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background: #F3F4F6;
                }
                QPushButton:pressed {
                    background: #E5E7EB;
                }
            """)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        layout.addStretch()
        self._table.setCellWidget(row, 6, widget)

    def _get_status_text(self, status: str) -> str:
        """获取状态文本"""
        return {
            "pending": "待转写",
            "processing": "转写中",
            "done": "已完成",
            "failed": "失败",
        }.get(status, "未知")

    def _on_selection_changed(self):
        """选中变化回调"""
        selected = self._table.selectionModel().selectedRows()
        paths = []
        for idx in selected:
            row = idx.row()
            if row < len(self._file_data):
                path = self._file_data[row].get("path", "")
                if path:
                    paths.append(path)
        self._selected_paths = set(paths)
        self.file_selected.emit(paths)

    def _on_action(self, action: str, file_path: str):
        """操作按钮回调"""
        self.file_action.emit(action, file_path)

    def get_selected_paths(self) -> list:
        """获取选中的文件路径"""
        return list(self._selected_paths)

    def get_selected(self) -> list:
        """获取选中的文件路径（兼容旧接口）"""
        return list(self._selected_paths)

    def clear_selection(self):
        """清空选中"""
        self._table.clearSelection()
        self._selected_paths.clear()
