#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件列表视图组件：从 HomePage 中提取的文件列表渲染逻辑

支持功能：
- Grid 布局 7+1 列（队列、文件名、主题、时长、大小、状态、操作 + 滚动条占位）
- 行点击选中（非复选框）
- 选中标记（● 前缀）和合并文件显示（📎 前缀）
- 状态图标（ICON_STATUS/ICON_COLOR）
- 丰富的操作按钮（含 Tooltips）
- 增量更新（不全量重建）
- 空状态处理
- 队列位置显示
"""

import customtkinter as ctk
from CTkToolTip import CTkToolTip
from file_manager import FileStatus
from gui.styles import (
    C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_WARN, C_ERROR, C_TXT1, C_TXT2, C_TXT3,
    FONT_FAMILY, ICON_STATUS, ICON_ACTION, ICON_COLOR, TOOLTIPS,
)


class FileListView(ctk.CTkFrame):
    """文件列表视图组件"""

    # 状态颜色映射（保留供外部引用）
    _ST_COLORS = {
        FileStatus.PENDING: C_TXT3, FileStatus.PROCESSING: C_WARN,
        FileStatus.DONE: C_SUCCESS, FileStatus.FAILED: C_ERROR,
    }
    _ST_MAP = {
        FileStatus.PENDING: "待转写", FileStatus.PROCESSING: "转写中...",
        FileStatus.DONE: "已完成", FileStatus.FAILED: "失败",
    }

    def __init__(self, parent, on_select=None, on_action=None,
                 get_queue_position=None, get_queue=None, **kwargs):
        """
        Args:
            parent: 父容器
            on_select: 选中回调，签名 (selected_paths: list)
            on_action: 操作回调，签名 (action: str, file_path: str)
            get_queue_position: 获取队列位置的回调，签名 (file_path) -> int
            get_queue: 获取当前队列的回调，签名 () -> list
        """
        super().__init__(parent, **kwargs)

        self._on_select = on_select
        self._on_action = on_action
        self._get_queue_position = get_queue_position or (lambda fp: 0)
        self._get_queue = get_queue or (lambda: [])
        self._row_widgets = {}  # file_path -> widgets dict
        self._selected_files = set()

        self._setup_ui()

    def _setup_ui(self):
        """初始化 UI"""
        import logging
        logger = logging.getLogger("MeetScribe")

        # 列权重: 队列, 文件名, 主题, 时长, 大小, 状态, 操作
        col_weights = [0, 1, 3, 1, 1, 1, 2]

        # ── 滚动区域（占满整个 FileListView） ──
        self._scroll_container = ctk.CTkFrame(self, fg_color="transparent")
        self._scroll_container.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._scroll_container.grid_columnconfigure(0, weight=1)
        self._scroll_container.grid_rowconfigure(0, weight=1)

        self._canvas = ctk.CTkCanvas(self._scroll_container, highlightthickness=0)
        self._scrollbar = ctk.CTkScrollbar(
            self._scroll_container, orientation="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scrollbar.grid(row=0, column=1, sticky="ns")

        self._data_frame = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._data_frame, anchor="nw")

        # 数据区域列权重
        for i, w in enumerate(col_weights):
            self._data_frame.grid_columnconfigure(i, weight=w)

        # Canvas 内容宽度跟随 Canvas 宽度 + 动态测量滚动条宽度
        self._scrollbar_measured = False

        def _on_canvas_configure(event):
            self._canvas.itemconfig(self._canvas_window, width=event.width)
            logger.debug(
                f"[Layout] Canvas={event.width}x{event.height}, "
                f"scroll_container={self._scroll_container.winfo_width()}x{self._scroll_container.winfo_height()}, "
                f"FileListView={self.winfo_width()}x{self.winfo_height()}, "
                f"scrollbar={self._scrollbar.winfo_width()}px"
            )
            if not self._scrollbar_measured:
                self._scrollbar_measured = True
                self.update_idletasks()
                actual_w = self._scrollbar.winfo_width()
                if actual_w <= 0:
                    from customtkinter import ScalingTracker
                    scaling = ScalingTracker.get_widget_scaling(self._scrollbar)
                    actual_w = int(16 * scaling)
                if actual_w != self._scrollbar_placeholder:
                    self._scrollbar_placeholder = actual_w
        self._canvas.bind("<Configure>", _on_canvas_configure)

        # _data_frame 内容高度变化时更新滚动区域
        def _on_frame_configure(event):
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._data_frame.bind("<Configure>", _on_frame_configure)

        # 鼠标滚轮绑定：递归绑定 _data_frame 及所有子控件
        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._on_mousewheel = _on_mousewheel
        self._bind_mousewheel_recursive(self._data_frame)

        # ── 表头（row 0，在 _data_frame 内，随内容一起滚动） ──
        hdr_style = {
            "font": ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            "text_color": C_TXT3,
        }
        ctk.CTkLabel(self._data_frame, text="队列", anchor="center",
                     **hdr_style).grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkLabel(self._data_frame, text="文件名", anchor="w",
                     **hdr_style).grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=(4, 2))
        ctk.CTkLabel(self._data_frame, text="主题", anchor="w",
                     **hdr_style).grid(row=0, column=2, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkLabel(self._data_frame, text="时长", anchor="center",
                     **hdr_style).grid(row=0, column=3, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkLabel(self._data_frame, text="大小", anchor="center",
                     **hdr_style).grid(row=0, column=4, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkLabel(self._data_frame, text="状态", anchor="center",
                     **hdr_style).grid(row=0, column=5, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkLabel(self._data_frame, text="操作", anchor="center",
                     **hdr_style).grid(row=0, column=6, sticky="ew", padx=4, pady=(4, 2))

        # 表头分隔线（row 1）
        self._header_sep = ctk.CTkFrame(self._data_frame, height=1, fg_color=C_BORDER)
        self._header_sep.grid(row=1, column=0, columnspan=7, sticky="ew", pady=(0, 2))

        # 数据行起始行号（表头占 row 0，分隔线占 row 1）
        self._DATA_START_ROW = 2

        # 空状态（放在 _data_frame 内）
        self._empty_frame = ctk.CTkFrame(self._data_frame, fg_color="transparent")
        self._empty_frame.grid(row=self._DATA_START_ROW, column=0, columnspan=7, pady=50)
        ctk.CTkLabel(
            self._empty_frame, text="暂无文件",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16),
            text_color=C_TXT3,
        ).pack()
        ctk.CTkLabel(
            self._empty_frame, text='点击「添加文件」导入音频，或使用上方录音功能',
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT3,
        ).pack(pady=(4, 0))

    # ── 公开方法 ─────────────────────────────────────────────

    def refresh(self, files):
        """刷新文件列表（增量更新）"""
        if not files:
            for path in list(self._row_widgets.keys()):
                self._destroy_file_row(path)
            self._empty_frame.grid(row=self._DATA_START_ROW, column=0, columnspan=7, pady=50)
            return

        self._empty_frame.grid_forget()

        current_paths = {f.file_path for f in files}
        old_paths = list(self._row_widgets.keys())

        # 删除不再存在的行
        for path in old_paths:
            if path not in current_paths:
                self._destroy_file_row(path)

        # 更新或创建行（行号从 0 开始，在 _data_frame 内）
        for idx, f in enumerate(files):
            row_idx = idx
            if f.file_path in self._row_widgets:
                self._update_file_row(f, row_idx)
            else:
                self._create_file_row(f, row_idx)

        # 刷新后重新绑定滚轮（新创建的子控件需要绑定）
        self._bind_mousewheel_recursive(self._data_frame)

    def get_selected(self):
        """获取选中的文件路径"""
        return list(self._selected_files)

    def clear_selection(self):
        """清空选择"""
        self._selected_files.clear()
        for fp, widgets in self._row_widgets.items():
            widgets["bg"].configure(fg_color="transparent")
            self._update_name_label(fp, widgets)

    def update_action_buttons(self, file_item):
        """增量更新单个文件行的操作按钮状态"""
        widgets = self._row_widgets.get(file_item.file_path)
        if widgets and "action_buttons" in widgets:
            self._update_action_buttons_state(widgets["action_buttons"], file_item)

    # ── 行操作 ─────────────────────────────────────────────

    def _destroy_file_row(self, file_path):
        """销毁单行的所有 widget"""
        widgets = self._row_widgets.pop(file_path, None)
        if widgets:
            for w in widgets.values():
                if isinstance(w, dict):
                    continue  # 跳过 action_buttons 子字典
                try:
                    w.destroy()
                except Exception:
                    pass

    def _create_file_row(self, file_item, row_idx):
        """创建单行 widget（所有 widget 放在 _data_frame 内）"""
        is_sel = (file_item.file_path in self._selected_files)
        row_bg = C_ACCENT_LT if is_sel else "transparent"
        is_merged = bool(file_item.source_files)
        grid_row = self._DATA_START_ROW + row_idx

        bg = ctk.CTkFrame(self._data_frame, fg_color=row_bg, corner_radius=4, height=34)
        bg.grid(row=grid_row, column=0, columnspan=7, sticky="ew", pady=1)
        bg.grid_propagate(False)

        # 队列位置
        queue_pos = self._get_queue_position(file_item.file_path)
        queue_text = str(queue_pos) if queue_pos > 0 else ""
        q = ctk.CTkLabel(
            self._data_frame, text=queue_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_ACCENT if queue_text else C_TXT3, anchor="center",
        )
        q.grid(row=grid_row, column=0, sticky="ew", padx=4, pady=2)

        # 文件名（含选中标记）
        sel_mark = "● " if is_sel else "  "
        display_name = file_item.file_name
        if is_merged:
            display_name = f"📎 {file_item.file_name} ({len(file_item.source_files)}个文件)"
        nm = ctk.CTkLabel(
            self._data_frame, text=f"{sel_mark}{display_name}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT1, anchor="w",
        )
        nm.grid(row=grid_row, column=1, sticky="ew", padx=(8, 4), pady=2)
        nm.bind("<Button-1>", lambda e, fp=file_item.file_path: self._toggle_select(fp))
        bg.bind("<Button-1>", lambda e, fp=file_item.file_path: self._toggle_select(fp))

        # 主题
        topic_text = file_item.topic if file_item.topic else ""
        tp = ctk.CTkLabel(
            self._data_frame, text=topic_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2 if topic_text else C_TXT3, anchor="w",
        )
        tp.grid(row=grid_row, column=2, sticky="ew", padx=4, pady=2)
        tp.bind("<Button-1>", lambda e, fp=file_item.file_path: self._toggle_select(fp))

        # 时长
        dur = ctk.CTkLabel(
            self._data_frame, text=file_item.duration_str,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2, anchor="center",
        )
        dur.grid(row=grid_row, column=3, sticky="ew", padx=4, pady=2)

        # 大小
        sz = ctk.CTkLabel(
            self._data_frame, text=file_item.size_str,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2, anchor="center",
        )
        sz.grid(row=grid_row, column=4, sticky="ew", padx=4, pady=2)

        # 状态图标
        st_key = file_item.status.value
        st_icon = ICON_STATUS.get(st_key, "○")
        st_color = ICON_COLOR.get(st_key, C_TXT3)
        st = ctk.CTkLabel(
            self._data_frame, text=st_icon,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=st_color, anchor="center",
        )
        st.grid(row=grid_row, column=5, sticky="ew", padx=4, pady=2)

        # 操作按钮
        act_f = ctk.CTkFrame(self._data_frame, fg_color="transparent")
        act_f.grid(row=grid_row, column=6, sticky="ew", padx=4, pady=2)
        action_buttons = self._build_action_buttons(act_f, file_item)

        self._row_widgets[file_item.file_path] = {
            "bg": bg, "name": nm, "topic": tp, "dur": dur,
            "size": sz, "status": st, "action": act_f, "queue": q,
            "action_buttons": action_buttons,
        }

    def _update_file_row(self, file_item, row_idx):
        """更新已有行的变化字段"""
        widgets = self._row_widgets.get(file_item.file_path)
        if not widgets:
            return

        grid_row = self._DATA_START_ROW + row_idx

        # 更新行号
        for key, w in widgets.items():
            if isinstance(w, dict):
                continue
            if hasattr(w, 'grid_info') and w.grid_info():
                info = w.grid_info()
                current_row = info.get('row')
                if current_row is not None and current_row != grid_row:
                    w.grid(row=grid_row)

        # 更新选中状态
        is_sel = (file_item.file_path in self._selected_files)
        row_bg = C_ACCENT_LT if is_sel else "transparent"
        widgets["bg"].configure(fg_color=row_bg)

        # 更新队列位置
        queue_pos = self._get_queue_position(file_item.file_path)
        queue_text = str(queue_pos) if queue_pos > 0 else ""
        widgets["queue"].configure(
            text=queue_text,
            text_color=C_ACCENT if queue_text else C_TXT3,
        )

        # 更新文件名
        self._update_name_label(file_item.file_path, widgets, file_item)

        # 更新主题
        topic_text = file_item.topic if file_item.topic else ""
        widgets["topic"].configure(
            text=topic_text,
            text_color=C_TXT2 if topic_text else C_TXT3,
        )

        # 更新状态图标
        st_key = file_item.status.value
        st_icon = ICON_STATUS.get(st_key, "○")
        st_color = ICON_COLOR.get(st_key, C_TXT3)
        widgets["status"].configure(text=st_icon, text_color=st_color)

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
            current = widgets["name"].cget("text")
            display_name = current.lstrip("● ").lstrip("📎 ")
        widgets["name"].configure(text=f"{sel_mark}{display_name}")

    def _toggle_select(self, file_path):
        """切换文件选择状态"""
        if file_path in self._selected_files:
            self._selected_files.discard(file_path)
        else:
            self._selected_files.add(file_path)

        # 更新该行的视觉状态
        widgets = self._row_widgets.get(file_path)
        if widgets:
            is_sel = (file_path in self._selected_files)
            row_bg = C_ACCENT_LT if is_sel else "transparent"
            widgets["bg"].configure(fg_color=row_bg)
            self._update_name_label(file_path, widgets)

        if self._on_select:
            self._on_select(list(self._selected_files))

    # ── 操作按钮 ─────────────────────────────────────────────

    def _build_action_buttons(self, parent, file_item):
        """构建所有操作按钮（首次创建时调用），返回按钮引用字典。

        所有按钮一次性创建，通过 show/hide 控制可见性，
        避免状态变化时销毁重建按钮导致 UI 卡顿。
        """
        buttons = {}
        fp = file_item.file_path
        btn_kw = dict(width=28, height=26, corner_radius=4,
                      font=ctk.CTkFont(family=FONT_FAMILY, size=13))
        queue_kw = dict(width=24, height=24, corner_radius=3,
                        font=ctk.CTkFont(family=FONT_FAMILY, size=11))

        def _action(action_type):
            if self._on_action:
                self._on_action(action_type, fp)

        # ── DONE 状态按钮 ──
        btn_preview = ctk.CTkButton(
            parent, text=ICON_ACTION["preview"], **btn_kw,
            fg_color="#E8F0FE", text_color=C_ACCENT, hover_color="#D0E0FF",
            command=lambda: _action("preview"),
        )
        btn_preview.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_preview, message=TOOLTIPS["preview"], delay=0.5)
        buttons["preview"] = btn_preview

        btn_open = ctk.CTkButton(
            parent, text=ICON_ACTION["open"], **btn_kw,
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=lambda: _action("open"),
        )
        btn_open.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_open, message=TOOLTIPS["open"], delay=0.5)
        buttons["open"] = btn_open

        btn_speaker = ctk.CTkButton(
            parent, text=ICON_ACTION["speaker"], **btn_kw,
            fg_color="#F0E6FF", text_color="#7B2FF2", hover_color="#E0D0FF",
            command=lambda: _action("speaker"),
        )
        btn_speaker.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_speaker, message=TOOLTIPS["speaker"], delay=0.5)
        buttons["speaker"] = btn_speaker

        btn_retry = ctk.CTkButton(
            parent, text=ICON_ACTION["retry"], **btn_kw,
            fg_color="#FFF0E0", text_color=C_WARN, hover_color="#FFE0C0",
            command=lambda: _action("retry"),
        )
        btn_retry.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_retry, message=TOOLTIPS["retry"], delay=0.5)
        buttons["retry"] = btn_retry

        btn_export = ctk.CTkButton(
            parent, text=ICON_ACTION["export"], **btn_kw,
            fg_color="#E8F0FE", text_color=C_ACCENT, hover_color="#D0E0FF",
            command=lambda: _action("export"),
        )
        btn_export.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_export, message=TOOLTIPS["export"], delay=0.5)
        buttons["export"] = btn_export

        # ── PROCESSING 状态按钮 ──
        btn_stop = ctk.CTkButton(
            parent, text=ICON_ACTION["stop"], **btn_kw,
            fg_color="#FFF0E0", text_color=C_WARN, hover_color="#FFE0C0",
            command=lambda: _action("stop"),
        )
        btn_stop.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_stop, message=TOOLTIPS["stop"], delay=0.5)
        buttons["stop"] = btn_stop

        # ── PENDING/默认状态按钮 ──
        btn_transcribe = ctk.CTkButton(
            parent, text=ICON_ACTION["transcribe"], **btn_kw,
            fg_color=C_SUCCESS, hover_color="#0A5E0A",
            command=lambda: _action("transcribe"),
        )
        btn_transcribe.pack(side="left", padx=(0, 2))
        CTkToolTip(btn_transcribe, message=TOOLTIPS["transcribe"], delay=0.5)
        buttons["transcribe"] = btn_transcribe

        btn_move_up = ctk.CTkButton(
            parent, text="▲", **queue_kw,
            fg_color="transparent", text_color=C_ACCENT,
            hover_color="#E8F0FE",
            command=lambda: _action("move_up"),
        )
        btn_move_up.pack(side="left", padx=(0, 1))
        CTkToolTip(btn_move_up, message=TOOLTIPS["move_up"], delay=0.5)
        buttons["move_up"] = btn_move_up

        btn_move_down = ctk.CTkButton(
            parent, text="▼", **queue_kw,
            fg_color="transparent", text_color=C_ACCENT,
            hover_color="#E8F0FE",
            command=lambda: _action("move_down"),
        )
        btn_move_down.pack(side="left", padx=(0, 1))
        CTkToolTip(btn_move_down, message=TOOLTIPS["move_down"], delay=0.5)
        buttons["move_down"] = btn_move_down

        btn_remove = ctk.CTkButton(
            parent, text="✕", **queue_kw,
            fg_color="transparent", text_color=C_ERROR,
            hover_color="#FDE8E8",
            command=lambda: _action("remove"),
        )
        btn_remove.pack(side="left", padx=(0, 1))
        CTkToolTip(btn_remove, message=TOOLTIPS["remove"], delay=0.5)
        buttons["remove_from_queue"] = btn_remove

        # 根据初始状态设置可见性
        self._update_action_buttons_state(buttons, file_item)

        return buttons

    def _update_action_buttons_state(self, buttons, file_item):
        """只更新按钮可见性和状态，不重建 widget。

        DONE + result_path: 显示 preview/open/speaker/retry/export
        PROCESSING:         显示 stop
        其他(PENDING等):    显示 transcribe，若在队列中还显示队列管理按钮
        """
        if not buttons:
            return

        status = file_item.status
        has_result = bool(file_item.result_path)
        is_done = (status == FileStatus.DONE and has_result)
        is_processing = (status == FileStatus.PROCESSING)

        # DONE 状态按钮组
        for key in ("preview", "open", "speaker", "retry", "export"):
            if key in buttons:
                if is_done:
                    buttons[key].pack(side="left", padx=(0, 2))
                else:
                    buttons[key].pack_forget()

        # PROCESSING 状态按钮
        if "stop" in buttons:
            if is_processing:
                buttons["stop"].pack(side="left", padx=(0, 2))
            else:
                buttons["stop"].pack_forget()

        # PENDING/默认状态按钮
        if "transcribe" in buttons:
            if not is_done and not is_processing:
                buttons["transcribe"].pack(side="left", padx=(0, 2))
            else:
                buttons["transcribe"].pack_forget()

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
                buttons["move_up"].configure(
                    state="normal" if queue_idx > 0 else "disabled",
                    text_color=C_ACCENT if queue_idx > 0 else C_TXT3,
                )
                buttons["move_up"].pack(side="left", padx=(0, 1))
            else:
                buttons["move_up"].pack_forget()

        if "move_down" in buttons:
            if in_queue:
                buttons["move_down"].configure(
                    state="normal" if queue_idx < queue_len - 1 else "disabled",
                    text_color=C_ACCENT if queue_idx < queue_len - 1 else C_TXT3,
                )
                buttons["move_down"].pack(side="left", padx=(0, 1))
            else:
                buttons["move_down"].pack_forget()

        if "remove_from_queue" in buttons:
            if in_queue:
                buttons["remove_from_queue"].pack(side="left", padx=(0, 1))
            else:
                buttons["remove_from_queue"].pack_forget()

    # ── 工具方法（保留供测试兼容） ─────────────────────────────

    def _format_duration(self, seconds):
        """格式化时长"""
        if seconds <= 0:
            return "--:--"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _get_status_text(self, status):
        """获取状态文本"""
        status_map = {
            FileStatus.PENDING: "等待中",
            FileStatus.PROCESSING: "转写中",
            FileStatus.DONE: "已完成",
            FileStatus.FAILED: "失败",
            FileStatus.PAUSED: "已暂停",
        }
        return status_map.get(status, "未知")

    def _bind_mousewheel_recursive(self, widget):
        """递归绑定 MouseWheel 事件到 widget 及其所有子控件"""
        widget.bind("<MouseWheel>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child)
