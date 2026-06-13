#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 主页：录音条 + 文件列表 + 日志
"""

import os
import json
import time
import logging
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_WARN, C_ERROR, C_TXT1, C_TXT2, C_TXT3,
    FONT_FAMILY, AUDIO_EXTENSIONS, OUTPUT_FORMATS,
    ICON_STATUS, ICON_ACTION, ICON_COLOR, TOOLTIPS,
)
from gui.dialogs import PreviewDialog, ExportDialog, SpeakerDialog, MergeOrderDialog, parse_speakers_from_result
from gui.recording_bar import RecordingBar
from gui.file_list_view import FileListView
from file_manager import FileStatus
from utils import get_summary_path, apply_speaker_mapping

logger = logging.getLogger("MeetScribe")

# 用户关心的日志关键词
USER_FRIENDLY_KEYWORDS = [
    "录音已开始", "录音已停止", "录音已保存",
    "转写完成", "转写已停止", "转写中", "正在转写",
    "添加文件", "删除文件", "文件已保存",
    "模型加载完成", "格式转换完成",
    "双轨录音", "模型检查通过", "开始转写",
    "Subprocess started", "转写任务已完成",
    "已加入转写队列", "队列中", "双轨合并",
]


class HomePage(ctk.CTkFrame):
    """主页：录音条 + 文件列表 + 日志"""

    def __init__(self, parent, app):
        """
        Args:
            parent: 父容器
            app: MeetScribeApp 实例，用于访问 config, file_manager, recorder 等
        """
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(0, weight=0)  # title
        self.grid_rowconfigure(1, weight=0)  # record bar
        self.grid_rowconfigure(2, weight=1)  # file card (flex)
        self.grid_rowconfigure(3, weight=0)  # log card
        self.grid_columnconfigure(0, weight=1)

        self._app = app
        self._record_start_time = None
        self._timer_after_id = None

        self._build()

    # ── 代理属性（保持测试和外部代码兼容）─────────────────────

    @property
    def _file_rows(self):
        """代理到 FileListView 的 _row_widgets"""
        return self._file_list_view._row_widgets

    @property
    def _selected_files(self):
        """代理到 FileListView 的 _selected_files"""
        return self._file_list_view._selected_files

    # ── 构建 ─────────────────────────────────────────────────

    def _build(self):
        self._build_title()
        self._build_record_bar()
        self._build_file_card()
        self._build_log_area()

    # ── Title ─────────────────────────────────────────────────

    def _build_title(self):
        title_f = ctk.CTkFrame(self, fg_color="transparent")
        title_f.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 6))
        ctk.CTkLabel(
            title_f, text="主页",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=C_TXT1,
        ).pack(side="left")
        self._file_count_lbl = ctk.CTkLabel(
            title_f, text="", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT3,
        )
        self._file_count_lbl.pack(side="right")

    # ── Record Bar ────────────────────────────────────────────

    def _build_record_bar(self):
        rec_bar = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8,
                               border_width=1, border_color=C_BORDER, height=56)
        rec_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 6))
        rec_bar.grid_propagate(False)

        inner = ctk.CTkFrame(rec_bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=8)

        initial_mode = self._app.config.get("recording_mode", "mic")
        self._recording_bar = RecordingBar(
            inner,
            on_start=self._start_recording,
            on_stop=self._stop_recording,
            on_pause=self._toggle_pause,
            on_mode_change=self._on_rec_mode_change,
            initial_mode=initial_mode,
            fg_color="transparent",
        )
        self._recording_bar.pack(fill="both", expand=True)

        # 保持对旧属性的兼容引用
        self._rec_dot = self._recording_bar._rec_dot
        self._rec_status_lbl = self._recording_bar._rec_status_lbl
        self._rec_mode_var = self._recording_bar.mode_var
        self._rec_mode_menu = self._recording_bar.mode_menu
        self._rec_mode_hint = self._recording_bar._rec_mode_hint
        self._timer_lbl = self._recording_bar.timer_label
        self._btn_start_rec = self._recording_bar.record_btn
        self._btn_pause_rec = self._recording_bar.pause_btn
        self._btn_stop_rec = self._recording_bar.stop_btn
        self._queue_label = self._recording_bar._queue_label

    # ── File Card ─────────────────────────────────────────────

    def _build_file_card(self):
        card = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8,
                            border_width=1, border_color=C_BORDER)
        card.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 6))
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(card, fg_color="transparent")
        tb.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))

        btn_font = ctk.CTkFont(family=FONT_FAMILY, size=12)
        btn_padx = 4

        self._btn_add = ctk.CTkButton(
            tb, text=" 添加文件", width=90, height=32, corner_radius=6,
            font=btn_font, fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=self._add_files,
        )
        self._btn_add.pack(side="left", padx=(0, btn_padx))

        self._btn_transcribe = ctk.CTkButton(
            tb, text=" 开始转写", width=90, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=C_SUCCESS, hover_color="#0A5E0A",
            command=self._start_transcription,
        )
        self._btn_transcribe.pack(side="left", padx=(0, btn_padx))

        self._btn_ai_summary = ctk.CTkButton(
            tb, text=" AI 摘要", width=84, height=32, corner_radius=6,
            font=btn_font, fg_color="#7B2FF2", hover_color="#6420CC",
            command=self._open_summary_for_selected,
        )
        self._btn_ai_summary.pack(side="left", padx=(0, btn_padx))

        self._btn_merge = ctk.CTkButton(
            tb, text=" 合并转写", width=90, height=32, corner_radius=6,
            font=btn_font, fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TXT2, hover_color="#F5F5F5",
            command=self._merge_transcribe,
        )
        self._btn_merge.pack(side="left", padx=(0, btn_padx))

        sep_v = ctk.CTkFrame(tb, width=1, height=24, fg_color=C_BORDER)
        sep_v.pack(side="left", padx=6)

        self._btn_delete = ctk.CTkButton(
            tb, text=" 删除选中", width=80, height=32, corner_radius=6,
            font=btn_font, fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TXT2, hover_color="#F5F5F5",
            command=self._delete_selected,
        )
        self._btn_delete.pack(side="left", padx=(0, btn_padx))

        self._btn_clear = ctk.CTkButton(
            tb, text=" 清空列表", width=80, height=32, corner_radius=6,
            font=btn_font, fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TXT2, hover_color="#F5F5F5",
            command=self._clear_files,
        )
        self._btn_clear.pack(side="left", padx=(0, btn_padx))

        # Format selector
        fmt_f = ctk.CTkFrame(tb, fg_color="transparent")
        fmt_f.pack(side="right")
        ctk.CTkLabel(
            fmt_f, text="输出格式", font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(side="left", padx=(0, 6))
        fmt_labels = list(OUTPUT_FORMATS.keys())
        self._batch_format_var = ctk.StringVar(value=fmt_labels[0])
        self._batch_format_menu = ctk.CTkOptionMenu(
            fmt_f, variable=self._batch_format_var, values=fmt_labels,
            width=130, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_CARD, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER, text_color=C_TXT1,
        )
        self._batch_format_menu.pack(side="left")

        # Separator
        ctk.CTkFrame(card, height=1, fg_color=C_BORDER).grid(
            row=0, column=0, sticky="sew", padx=14, pady=(44, 0))

        # File List View（组件化）
        self._file_list_view = FileListView(
            card,
            on_select=self._on_file_select,
            on_action=self._on_file_action,
            get_queue_position=self._get_queue_position,
            get_queue=self._get_queue,
            fg_color="transparent",
        )
        self._file_list_view.grid(row=1, column=0, sticky="nsew", padx=14, pady=(4, 10))

    # ── Log Area ──────────────────────────────────────────────

    def _build_log_area(self):
        log_card = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8,
                                border_width=1, border_color=C_BORDER, height=120)
        log_card.grid(row=3, column=0, sticky="sew", padx=20, pady=(0, 10))
        log_card.grid_propagate(False)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(
            log_hdr, text="运行日志",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=C_TXT2,
        ).pack(side="left")
        ctk.CTkButton(
            log_hdr, text="清除", width=50, height=22, corner_radius=4,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color="transparent", text_color=C_TXT3, hover_color="#F0F0F0",
            command=self._clear_log,
        ).pack(side="right")

        self._log_text = ctk.CTkTextbox(
            log_card, height=78, state="disabled", wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#FAFAFA", text_color=C_TXT2,
        )
        self._log_text.pack(fill="both", expand=True, padx=12, pady=(2, 6))

    # ══════════════════════════════════════════════════════════
    #  Recording
    # ══════════════════════════════════════════════════════════

    def _start_recording(self):
        # 立即更新 UI 状态，避免等待回调的延迟
        self._btn_start_rec.configure(state="disabled", text="启动中...")
        self._btn_stop_rec.configure(state="normal")
        self._btn_pause_rec.configure(state="normal")
        self.update_idletasks()

        try:
            display_name = self._rec_mode_var.get()
            mode = {"现场会议": "mic", "线上会议": "dual"}.get(display_name, "mic")
            self._app.recorder.start(mode)
            self.log(f"录音模式: {display_name}")
        except Exception as e:
            # 启动失败，恢复按钮状态
            self._btn_start_rec.configure(state="normal", text="开始录音")
            self._btn_stop_rec.configure(state="disabled")
            self._btn_pause_rec.configure(state="disabled")
            messagebox.showerror("录音错误", f"无法启动录音:\n{e}")
            self.log(f"录音启动失败: {e}")

    def _stop_recording(self):
        self._app.recorder.stop()
        self.log("正在保存录音...")

    def _toggle_pause(self):
        if self._app._paused:
            self._app.recorder.resume()
        else:
            self._app.recorder.pause()

    def _on_rec_mode_change(self, mode):
        """模式切换回调（由 RecordingBar 调用）"""
        self._app._recording_mode = mode
        self._app.config.set("recording_mode", mode)
        self._app.config.save()

    def update_recording_ui(self, is_recording, is_paused):
        """更新录音 UI 状态"""
        self._app._recording = is_recording
        self._app._paused = is_paused

        if is_recording and not is_paused:
            self._recording_bar.update_state(recording=True, paused=False)
            if not self._record_start_time:
                self._record_start_time = time.time()
            self._tick_timer()
            self._app._set_status("正在录音...")
            self.log("录音已开始")

        elif is_recording and is_paused:
            self._recording_bar.update_state(recording=True, paused=True)
            self._app._set_status("录音已暂停")
            self.log("录音已暂停")

        else:
            self._recording_bar.update_state(recording=False, paused=False)
            self._record_start_time = None
            if self._timer_after_id:
                self.after_cancel(self._timer_after_id)
                self._timer_after_id = None
            self._app._set_status("就绪")
            self.log("录音已停止")

    def _tick_timer(self):
        if not self._app._recording or self._app._paused:
            return
        if not self._record_start_time:
            return
        elapsed = time.time() - self._record_start_time - self._app.recorder.paused_duration
        self._recording_bar.update_timer(elapsed)
        self._timer_after_id = self.after(500, self._tick_timer)

    def ask_transcribe_after_record(self, file_path):
        """录音完成后询问是否转写"""
        if messagebox.askyesno("录音完成",
                               f"录音已保存:\n{os.path.basename(file_path)}\n\n是否立即开始转写?"):
            fmt = OUTPUT_FORMATS.get(self._batch_format_var.get(), "md")
            self._app._transcription_handler.add_to_queue([file_path])
            self._app._transcription_handler.start(
                [file_path], fmt, self._app._get_speaker_names(),
                self._app.get_output_dir(),
            )

    # ══════════════════════════════════════════════════════════
    #  File Management
    # ══════════════════════════════════════════════════════════

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择音频文件", filetypes=AUDIO_EXTENSIONS)
        if not paths:
            return
        for p in paths:
            self._app.file_manager.add_file(p)
            self.log(f"已添加: {os.path.basename(p)}")
        self._app._set_status(f"已添加 {len(paths)} 个文件")
        self.refresh_file_list()

    def _delete_selected(self):
        selected = self._file_list_view.get_selected()
        if not selected:
            messagebox.showinfo("提示", "请先点击文件行选中一个或多个文件")
            return
        count = len(selected)
        if messagebox.askyesno("确认", f"从列表中移除选中的 {count} 个文件?"):
            for fp in list(selected):
                self._app.file_manager.remove_file(fp)
            self._file_list_view.clear_selection()
            self.log(f"已删除 {count} 个文件")
            self.refresh_file_list()

    def _clear_files(self):
        if self._app.file_manager.count == 0:
            return
        if messagebox.askyesno("确认", "清空所有文件列表?"):
            self._app.file_manager.clear_all()
            self._file_list_view.clear_selection()
            self.log("文件列表已清空")
            self.refresh_file_list()

    def _on_file_select(self, selected_paths):
        """FileListView 选中回调"""
        self._update_file_count()

    def _on_file_action(self, action, file_path):
        """FileListView 操作回调"""
        action_map = {
            "preview": self._preview_result,
            "open": self._open_result,
            "speaker": self._open_speaker_modal,
            "retry": self._retry_transcription,
            "export": self._export_result,
            "stop": self._stop_transcription,
            "transcribe": self._transcribe_single,
            "move_up": self._queue_move_up,
            "move_down": self._queue_move_down,
            "remove": self._queue_remove,
        }
        handler = action_map.get(action)
        if handler:
            handler(file_path)

    def _get_queue_position(self, file_path):
        """获取文件在转写队列中的位置"""
        try:
            return self._app._transcription_handler.get_queue_position(file_path)
        except Exception:
            return 0

    def _get_queue(self):
        """获取当前转写队列"""
        try:
            return self._app._transcription_handler.get_queue()
        except Exception:
            return []

    def _update_file_count(self):
        """只更新文件计数标签"""
        files = self._app.file_manager.display_files
        sel_count = len(self._file_list_view.get_selected())
        total = len(files)
        if total == 0:
            self._file_count_lbl.configure(text="")
        else:
            count_text = f"共 {total} 个文件"
            if sel_count:
                count_text += f"，已选 {sel_count}"
            self._file_count_lbl.configure(text=count_text)

    # ── 代理方法（保持测试兼容）────────────────────────────

    def _destroy_file_row(self, file_path):
        """代理到 FileListView（保持测试兼容）"""
        self._file_list_view._destroy_file_row(file_path)

    def _create_file_row(self, file_item, row_idx):
        """代理到 FileListView（保持测试兼容）"""
        self._file_list_view._create_file_row(file_item, row_idx)

    def _update_file_row(self, file_item, row_idx):
        """代理到 FileListView（保持测试兼容）"""
        self._file_list_view._update_file_row(file_item, row_idx)

    def _update_action_buttons_state(self, buttons, file_item):
        """代理到 FileListView（保持测试兼容）"""
        self._file_list_view._update_action_buttons_state(buttons, file_item)

    def _toggle_file_select(self, file_path):
        """代理到 FileListView（保持测试兼容）"""
        self._file_list_view._toggle_select(file_path)
        self._update_file_count()

    def _update_row_selection(self, file_path):
        """代理到 FileListView（保持测试兼容）"""
        widgets = self._file_list_view._row_widgets.get(file_path)
        if not widgets:
            return
        is_sel = (file_path in self._file_list_view._selected_files)
        row_bg = C_ACCENT_LT if is_sel else "transparent"
        widgets["bg"].configure(fg_color=row_bg)
        self._file_list_view._update_name_label(file_path, widgets)

    # ── 状态常量（保持测试兼容）────────────────────────────

    _ST_COLORS = {
        FileStatus.PENDING: C_TXT3, FileStatus.PROCESSING: C_WARN,
        FileStatus.DONE: C_SUCCESS, FileStatus.FAILED: C_ERROR,
    }
    _ST_MAP = {
        FileStatus.PENDING: "待转写", FileStatus.PROCESSING: "转写中...",
        FileStatus.DONE: "已完成", FileStatus.FAILED: "失败",
    }

    def _open_result(self, file_path):
        """打开文件所在文件夹"""
        import sys
        import subprocess

        item = self._app.file_manager.get_file(file_path)
        if not item or not item.result_path:
            messagebox.showinfo("提示", "结果文件不存在")
            return

        result_dir = os.path.dirname(item.result_path)
        if sys.platform == "win32":
            subprocess.Popen(
                ["explorer", result_dir],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        else:
            subprocess.Popen(["open", result_dir])
        self.log(f"已打开文件夹: {result_dir}")

    def _preview_result(self, file_path):
        item = self._app.file_manager.get_file(file_path)
        if not item or not item.result_path or not os.path.exists(item.result_path):
            messagebox.showinfo("提示", "结果文件不存在")
            return

        summary_path = get_summary_path(item.result_path)
        PreviewDialog(self, item.file_name, item.result_path, summary_path)

    def _export_result(self, file_path):
        """导出转写结果"""
        item = self._app.file_manager.get_file(file_path)
        if not item or not item.result_path or not os.path.exists(item.result_path):
            messagebox.showinfo("提示", "结果文件不存在")
            return

        ExportDialog(self, file_path, item.result_path)

    def _open_summary_for_selected(self):
        selected = list(self._file_list_view.get_selected())
        if not selected:
            for item in self._app.file_manager.files:
                if item.status == FileStatus.DONE and item.result_path:
                    selected = [item.file_path]
                    break
        if not selected:
            messagebox.showinfo("提示", "请先选择已完成转写的文件")
            return

        fp = selected[0]
        item = self._app.file_manager.get_file(fp)
        if not item or not item.result_path:
            messagebox.showinfo("提示", "该文件尚未完成转写")
            return

        summary_path = get_summary_path(item.result_path)
        if summary_path:
            import sys
            import subprocess
            if sys.platform == "win32":
                subprocess.Popen(
                    ["explorer", summary_path],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            else:
                subprocess.Popen(["open", summary_path])
            self.log(f"已打开摘要: {os.path.basename(summary_path)}")
        else:
            messagebox.showinfo("提示",
                f"未找到 AI 摘要文件。\n\n"
                f"请确认已在设置中开启「自动摘要」并配置 MiMo API Key。")

    def _open_speaker_modal(self, file_path):
        item = self._app.file_manager.get_file(file_path)
        if not item or not item.result_path:
            messagebox.showinfo("提示", "请先完成转写")
            return

        speakers = parse_speakers_from_result(item.result_path, item.speaker_names)
        if not speakers:
            messagebox.showinfo("提示", "未识别到说话人信息")
            return

        def on_save(names):
            self._app.file_manager.update_speaker_names(file_path, names)
            if names:
                if item.result_path and os.path.exists(item.result_path):
                    apply_speaker_mapping(item.result_path, names)
                summary_path = get_summary_path(item.result_path)
                if summary_path and os.path.exists(summary_path):
                    apply_speaker_mapping(summary_path, names)
                mapped = ", ".join(f"{k}→{v}" for k, v in names.items())
                if mapped:
                    self.log(f"发言人映射已保存（本文件）: {mapped}")

        # 获取说话人嵌入向量（用于保存到音色库）
        speaker_embeddings = {}
        sentences = []
        audio_path = file_path  # 原始音频文件路径
        speaker_qualities = {}
        try:
            handler = self._app._transcription_handler
            if hasattr(handler, '_speaker_embeddings'):
                speaker_embeddings = dict(handler._speaker_embeddings)
            if hasattr(handler, '_sentences'):
                sentences = list(handler._sentences)
            if hasattr(handler, '_speaker_qualities'):
                speaker_qualities = dict(handler._speaker_qualities)
        except Exception:
            pass

        # 如果内存中没有嵌入向量，尝试从磁盘加载（程序重启后恢复）
        if not speaker_embeddings and item.result_path:
            speaker_embeddings, speaker_qualities = self._load_embeddings_from_disk(
                item.result_path)

        SpeakerDialog(self, item.file_name, speakers, on_save=on_save,
                      speaker_embeddings=speaker_embeddings,
                      speaker_qualities=speaker_qualities,
                      audio_path=audio_path, sentences=sentences)

    def _load_embeddings_from_disk(self, result_path):
        """从磁盘加载声纹嵌入向量（程序重启后恢复）"""
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
                spk_id = spk_id_str  # 保持字符串 key，与对话框匹配
                vector = info.get("vector", [])
                quality = info.get("quality", 0.85)
                if vector:
                    speaker_embeddings[spk_id] = vector
                    speaker_qualities[spk_id] = quality
            logger.debug(f"[HOME] 从磁盘加载了 {len(speaker_embeddings)} 个说话人的嵌入向量")
        except Exception as e:
            logger.debug(f"[HOME] 从磁盘加载嵌入向量失败: {e}")
        return speaker_embeddings, speaker_qualities

    # ══════════════════════════════════════════════════════════
    #  Transcription
    # ══════════════════════════════════════════════════════════

    def _transcribe_single(self, file_path):
        if self._app._transcription_handler.is_transcribing:
            messagebox.showinfo("提示", "正在转写中，请等待完成")
            return
        fmt = OUTPUT_FORMATS.get(self._batch_format_var.get(), "md")
        out_dir = self._app.get_output_dir()
        self._app._transcription_handler.add_to_queue([file_path])
        self._app._transcription_handler.start(
            [file_path], fmt, self._app._get_speaker_names(), out_dir,
        )

    def _stop_transcription(self, file_path):
        """停止转写"""
        self._app._transcription_handler.stop_transcription(file_path)

    # ── Queue Management ───────────────────────────────────────

    def _queue_move_up(self, file_path):
        """将文件在转写队列中上移"""
        self._app._transcription_handler.move_up_in_queue(file_path)
        self.log(f"队列调整: {os.path.basename(file_path)} 上移")
        self.refresh_file_list()

    def _queue_move_down(self, file_path):
        """将文件在转写队列中下移"""
        self._app._transcription_handler.move_down_in_queue(file_path)
        self.log(f"队列调整: {os.path.basename(file_path)} 下移")
        self.refresh_file_list()

    def _queue_remove(self, file_path):
        """从转写队列中移除文件"""
        self._app._transcription_handler.remove_from_queue(file_path)
        self.log(f"已从转写队列移除: {os.path.basename(file_path)}")
        self.refresh_file_list()

    def _retry_transcription(self, file_path):
        """重新转写"""
        from tkinter import messagebox

        # 确认重新转写
        if not messagebox.askyesno("确认重新转写", "重新转写将覆盖现有转写结果，是否继续？"):
            return

        # 获取文件信息
        file_item = self._app.file_manager.get_file(file_path)
        if not file_item:
            return

        # 删除旧的转写文件
        if file_item.result_path and os.path.exists(file_item.result_path):
            try:
                os.remove(file_item.result_path)
            except Exception as e:
                self.log(f"删除旧转写文件失败: {e}")

        # 重置文件状态
        self._app.file_manager.update_status(file_path, FileStatus.PENDING)
        file_item.result_path = None

        # 重新执行转写
        self._transcribe_single(file_path)

    def _start_transcription(self):
        pending = self._app.file_manager.get_pending_files()
        if not pending:
            messagebox.showinfo("提示", "没有待转写的文件\n请先添加音频文件")
            return
        fmt = OUTPUT_FORMATS.get(self._batch_format_var.get(), "md")
        paths = [f.file_path for f in pending]

        # 检测双轨配对
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
                self.log(f"检测到双轨配对: {os.path.basename(mic_path)} + {os.path.basename(sys_path)}")
            else:
                all_paths.append(fp)
                processed.add(fp)

        # 将文件加入转写队列
        self._app._transcription_handler.add_to_queue(all_paths)

        out_dir = self._app.get_output_dir()
        self.log(f"开始转写 {len(all_paths)} 个文件...")
        self._app._transcription_handler.start(
            all_paths, fmt, self._app._get_speaker_names(), out_dir,
        )

    def _merge_transcribe(self):
        if len(self._selected_files) < 2:
            messagebox.showinfo("提示", "请至少选中 2 个文件进行合并转写\n(点击文件行进行多选)")
            return

        selected_items = []
        for fp in self._selected_files:
            item = self._app.file_manager.get_file(fp)
            if item and item.status == FileStatus.PENDING:
                selected_items.append(item)

        if len(selected_items) < 2:
            messagebox.showinfo("提示", "选中的文件中至少需要 2 个待转写文件")
            return

        def on_confirm(ordered_items):
            fmt = OUTPUT_FORMATS.get(self._batch_format_var.get(), "md")
            paths = [f.file_path for f in ordered_items]
            names = [f.file_name for f in ordered_items]
            out_dir = self._app.get_output_dir()
            self._app._transcription_handler.add_to_queue(paths)
            self.log(f"开始合并转写 {len(paths)} 个文件，顺序: {' -> '.join(names)}")
            self._app._transcription_handler.start(
                paths, fmt, self._app._get_speaker_names(), out_dir, merge=True,
            )

        MergeOrderDialog(self, selected_items, on_confirm=on_confirm)

    def update_transcribe_buttons(self, transcribing):
        """更新转写按钮状态"""
        if transcribing:
            self._btn_transcribe.configure(state="disabled", text="  转写中...")
            self._btn_ai_summary.configure(state="disabled")
        else:
            self._btn_transcribe.configure(state="normal", text="  开始转写")
            self._btn_ai_summary.configure(state="normal", text=" AI 摘要")

    def update_transcription_progress(self, progress):
        """
        更新文件列表中的进度显示

        Args:
            progress: TranscriptionProgress 对象
        """
        if not progress or progress.total_files == 0:
            return

        # 更新正在处理的文件行状态显示
        for file_path, widgets in self._file_rows.items():
            item = self._app.file_manager.get_file(file_path)
            if item and item.status == FileStatus.PROCESSING:
                progress_text = f"{progress.stage}"
                if progress.eta:
                    progress_text += f" (剩余 {progress.eta})"
                widgets["status"].configure(text=progress_text, text_color=C_WARN)
                break

    def update_queue_status(self):
        """更新队列状态显示"""
        try:
            status_text = self._app._transcription_handler.get_queue_status_text()
            self._queue_label.configure(text=status_text)
        except Exception:
            pass

    def refresh_file_list(self):
        """增量更新文件列表"""
        files = sorted(self._app.file_manager.display_files,
                       key=lambda f: f.added_time, reverse=True)
        self._file_list_view.refresh(files)
        self._update_file_count()

    # ══════════════════════════════════════════════════════════
    #  Logging
    # ══════════════════════════════════════════════════════════

    def log(self, message):
        """写日志（仅 UI）"""
        self._append_log_widget(message)
        # 不再调用 logger.info，避免 GUILogHandler 重复添加

    def _append_log_widget(self, message):
        # 过滤：只显示用户关心的日志
        if not any(keyword in message for keyword in USER_FRIENDLY_KEYWORDS):
            return  # 跳过不关心的日志

        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def restore_format(self):
        """恢复输出格式设置"""
        saved_fmt = self._app.config.get("output_format", "md")
        for label, val in OUTPUT_FORMATS.items():
            if val == saved_fmt:
                self._batch_format_var.set(label)
                break
