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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon

from gui.icons import (
    create_icon, icon_play, icon_preview, icon_open_folder,
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
        ("操作",   0.19, Qt.AlignCenter),  # 操作列表头居中
    ]

    # 信号
    file_selected = Signal(list)  # 选中文件列表
    file_action = Signal(str, str)  # (action, file_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_data = []  # 文件数据列表
        self._selected_paths = set()
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
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(38)  # 行高

        # 样式
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: none;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 0 8px;
                border-bottom: 1px solid #F3F4F6;
            }
            QTableWidget::item:selected {
                background-color: #EFF6FF;
            }
            QTableWidget::item:hover {
                background-color: #F9FAFB;
            }
            QHeaderView::section {
                background-color: #FAFBFC;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 600;
                color: #9CA3AF;
            }
        """)

        # 信号
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    def resizeEvent(self, event):
        """窗口大小变化时按比例调整列宽"""
        super().resizeEvent(event)
        self._adjust_column_widths()

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
        self._file_data = files
        self._refresh_table()

    def _refresh_table(self):
        """刷新表格内容"""
        self._table.setRowCount(len(self._file_data))

        for row, file_info in enumerate(self._file_data):
            self._create_row(row, file_info)

        self._adjust_column_widths()

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

        # 文件名
        name_item = QTableWidgetItem(file_info.get("name", ""))
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_item.setToolTip(file_info.get("path", ""))
        self._table.setItem(row, 1, name_item)

        # 主题
        topic_item = QTableWidgetItem(file_info.get("topic", ""))
        topic_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
        if selected:
            row = selected[0].row()
            if row < len(self._file_data):
                path = self._file_data[row].get("path", "")
                self.file_selected.emit([path])

    def _on_action(self, action: str, file_path: str):
        """操作按钮回调"""
        self.file_action.emit(action, file_path)

    def get_selected_paths(self) -> list:
        """获取选中的文件路径"""
        return list(self._selected_paths)

    def clear_selection(self):
        """清空选中"""
        self._table.clearSelection()
        self._selected_paths.clear()
