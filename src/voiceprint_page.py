#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 音色库管理页面
"""

import os
import time
import logging
import customtkinter as ctk

logger = logging.getLogger("MeetScribe")
from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER,
    C_SUCCESS, C_ERROR, C_TXT1, C_TXT2, C_TXT3,
    FONT_FAMILY,
)


class VoiceprintPage(ctk.CTkFrame):
    """音色库管理页面"""

    def __init__(self, parent, app):
        """
        Args:
            parent: 父容器
            app: MeetScribeApp 实例
        """
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._selected_speaker = None

        self._build()

    def _build(self):
        """构建页面布局"""
        # 标题
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=24, pady=(16, 6))

        ctk.CTkLabel(
            title_frame, text="音色库管理",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=C_TXT1,
        ).pack(side="left")

        # 主体区域（左右分栏）
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(0, weight=1)

        # 左侧：说话人列表
        self._build_speaker_list(main_frame)

        # 右侧：说话人详情
        self._build_speaker_detail(main_frame)

    def _build_speaker_list(self, parent):
        """构建说话人列表面板"""
        list_card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=8,
                                 border_width=1, border_color=C_BORDER)
        list_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        list_card.grid_rowconfigure(1, weight=1)
        list_card.grid_columnconfigure(0, weight=1)

        # 标题
        header = ctk.CTkFrame(list_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            header, text="说话人列表",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=C_TXT1,
        ).pack(side="left")

        # 添加音色按钮
        self._add_btn = ctk.CTkButton(
            header, text="+ 添加音色", width=80, height=28, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=self._add_speaker,
        )
        self._add_btn.pack(side="right")

        # 说话人列表
        self._list_frame = ctk.CTkScrollableFrame(
            list_card, fg_color="transparent", corner_radius=4,
        )
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 10))
        self._list_frame.grid_columnconfigure(0, weight=1)

        # 空状态提示
        self._empty_label = ctk.CTkLabel(
            self._list_frame, text="暂无注册的说话人",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT3,
        )
        self._empty_label.grid(row=0, column=0, pady=50)

        # 说话人项目字典
        self._speaker_items = {}

        # 刷新列表
        self.refresh_list()

    def _build_speaker_detail(self, parent):
        """构建说话人详情面板"""
        self._detail_card = ctk.CTkFrame(parent, fg_color=C_CARD, corner_radius=8,
                                         border_width=1, border_color=C_BORDER)
        self._detail_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # 默认显示提示
        self._show_empty_detail()

    def _show_empty_detail(self):
        """显示空详情提示"""
        for widget in self._detail_card.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self._detail_card, text="请选择一个说话人",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            text_color=C_TXT3,
        ).pack(expand=True)

    def refresh_list(self):
        """刷新说话人列表"""
        from voiceprint import VoiceprintLibrary

        library = VoiceprintLibrary()
        speakers = library.get_speakers()

        # 清空现有项目
        for item in self._speaker_items.values():
            item.destroy()
        self._speaker_items.clear()

        if not speakers:
            self._empty_label.grid(row=0, column=0, pady=50)
            return

        self._empty_label.grid_forget()

        # 创建说话人项目
        for idx, (name, profile) in enumerate(speakers.items()):
            item = self._create_speaker_item(name, profile, idx)
            self._speaker_items[name] = item

    def _create_speaker_item(self, name, profile, row_idx):
        """创建说话人列表项"""
        item = ctk.CTkFrame(self._list_frame, fg_color="transparent", corner_radius=4)
        item.grid(row=row_idx, column=0, sticky="ew", pady=2)
        item.grid_columnconfigure(0, weight=1)

        # 说话人信息
        info_frame = ctk.CTkFrame(item, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=6)

        name_label = ctk.CTkLabel(
            info_frame, text=name,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=C_TXT1,
        )
        name_label.pack(side="left")

        count_label = ctk.CTkLabel(
            info_frame, text=f"({len(profile.embeddings)} 个样本)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        )
        count_label.pack(side="left", padx=(4, 0))

        # 绑定点击事件
        _click = lambda e, n=name: self._on_speaker_select(n)
        item.bind("<Button-1>", _click)
        info_frame.bind("<Button-1>", _click)
        name_label.bind("<Button-1>", _click)
        count_label.bind("<Button-1>", _click)

        return item

    def _on_speaker_select(self, speaker_name):
        """选中说话人事件"""
        t0 = time.perf_counter()

        self._selected_speaker = speaker_name
        self._show_speaker_detail(speaker_name)

        # 更新选中状态
        for name, item in self._speaker_items.items():
            if name == speaker_name:
                item.configure(fg_color="#E8F0FE")
            else:
                item.configure(fg_color="transparent")

        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug(f"[PERF] _on_speaker_select total: {elapsed:.1f}ms")

    def _show_speaker_detail(self, speaker_name):
        """显示说话人详情"""
        t0 = time.perf_counter()

        from voiceprint import VoiceprintLibrary

        library = VoiceprintLibrary()
        t1 = time.perf_counter()
        logger.debug(f"[PERF] VoiceprintLibrary load: {(t1-t0)*1000:.1f}ms")

        speakers = library.get_speakers()
        profile = speakers.get(speaker_name)

        if not profile:
            self._show_empty_detail()
            logger.debug(f"[PERF] _show_speaker_detail (no profile): {(time.perf_counter()-t0)*1000:.1f}ms")
            return

        # 清空现有内容
        for widget in self._detail_card.winfo_children():
            widget.destroy()
        t2 = time.perf_counter()
        logger.debug(f"[PERF] destroy widgets: {(t2-t1)*1000:.1f}ms")

        # 标题
        header = ctk.CTkFrame(self._detail_card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            header, text=speaker_name,
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=C_TXT1,
        ).pack(side="left")

        # 操作按钮
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(
            btn_frame, text="编辑", width=60, height=28, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=lambda: self._edit_speaker(speaker_name),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_frame, text="删除", width=60, height=28, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=C_ERROR, hover_color="#A52318",
            command=lambda: self._delete_speaker(speaker_name),
        ).pack(side="left")

        # 基本信息
        info_card = ctk.CTkFrame(self._detail_card, fg_color=C_BG, corner_radius=6)
        info_card.pack(fill="x", padx=16, pady=(0, 8))

        info_items = [
            ("样本数", str(len(profile.embeddings))),
            ("创建时间", profile.created_at[:10]),
        ]

        for label, value in info_items:
            row = ctk.CTkFrame(info_card, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)

            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=C_TXT3, width=80, anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=value,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=C_TXT1, anchor="w",
            ).pack(side="left")

        # 声纹样本列表
        ctk.CTkLabel(
            self._detail_card, text="声纹样本",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=C_TXT1, anchor="w",
        ).pack(anchor="w", padx=16, pady=(8, 4))

        samples_frame = ctk.CTkFrame(self._detail_card, fg_color=C_BG, corner_radius=6)
        samples_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        if profile.embeddings:
            for idx, emb in enumerate(profile.embeddings):
                row = ctk.CTkFrame(samples_frame, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=2)

                ctk.CTkLabel(
                    row, text=f"样本 {idx + 1}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=C_TXT2, width=60, anchor="w",
                ).pack(side="left")

                ctk.CTkLabel(
                    row, text=emb.get("source", "未知来源"),
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=C_TXT3, anchor="w",
                ).pack(side="left", padx=(0, 8))

                ctk.CTkLabel(
                    row, text=f"质量: {emb.get('quality', 0.85):.2f}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=C_TXT3, anchor="w",
                ).pack(side="right")
        else:
            ctk.CTkLabel(
                samples_frame, text="暂无声纹样本",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=C_TXT3,
            ).pack(expand=True)

        t3 = time.perf_counter()
        logger.debug(f"[PERF] create widgets: {(t3-t2)*1000:.1f}ms")
        logger.debug(f"[PERF] _show_speaker_detail total: {(t3-t0)*1000:.1f}ms")

    def _add_speaker(self):
        """添加说话人（人工添加音色）"""
        AddVoiceDialog(self, on_save=lambda: self.refresh_list())

    def _edit_speaker(self, old_name):
        """编辑说话人姓名"""
        from tkinter import simpledialog
        from voiceprint import VoiceprintLibrary

        new_name = simpledialog.askstring(
            "编辑说话人姓名",
            "请输入新的姓名:",
            initialvalue=old_name,
            parent=self,
        )

        if new_name and new_name != old_name:
            library = VoiceprintLibrary()

            if not library.rename_speaker(old_name, new_name):
                from tkinter import messagebox
                messagebox.showwarning("提示", f"姓名 '{new_name}' 已存在或 '{old_name}' 不存在", parent=self)
                return

            self._app.home_page.log(f"已重命名说话人: {old_name} -> {new_name}")
            self.refresh_list()

            # 如果选中的是被重命名的说话人，更新选中状态
            if self._selected_speaker == old_name:
                self._selected_speaker = new_name
                self._show_speaker_detail(new_name)

    def _delete_speaker(self, name):
        """删除说话人"""
        from tkinter import messagebox
        from voiceprint import VoiceprintLibrary

        if messagebox.askyesno("确认删除", f"确定要删除说话人 '{name}' 吗？\n\n此操作不可撤销。", parent=self):
            library = VoiceprintLibrary()
            library.remove_speaker(name)
            self._app.home_page.log(f"已删除说话人: {name}")

            if self._selected_speaker == name:
                self._selected_speaker = None
                self._show_empty_detail()

            self.refresh_list()


class AddVoiceDialog(ctk.CTkToplevel):
    """人工添加音色弹窗"""

    # 预设标准文本（基于 CAM++ 官方推荐的声纹录制内容）
    # 包含 {姓名} 占位符，录制时替换为实际姓名
    PRESET_TEXT = "你好，我是{姓名}，这是我的声纹样本。"

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.title("添加音色")
        self.geometry("480x400")
        self.configure(fg_color=C_BG)
        self.transient(parent)
        self.grab_set()

        self._parent = parent
        self._on_save = on_save
        self._recording = False
        self._recorder = None
        self._audio_path = None

        self._build()

    def _build(self):
        """构建弹窗布局"""
        # 标题
        ctk.CTkLabel(
            self, text="添加新说话人",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=C_TXT1,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            self, text="录音朗读以下文本，系统将自动提取声纹",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(anchor="w", padx=20, pady=(0, 12))

        # 姓名输入
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            name_frame, text="说话人姓名",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2,
        ).pack(anchor="w")

        self._name_entry = ctk.CTkEntry(
            name_frame, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            placeholder_text="请输入姓名",
        )
        self._name_entry.pack(fill="x", pady=(4, 0))

        # 预设文本显示
        text_card = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=6,
                                 border_width=1, border_color=C_BORDER)
        text_card.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            text_card, text="请朗读以下文本：",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=C_TXT2, anchor="w",
        ).pack(anchor="w", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            text_card, text=f"• {self.PRESET_TEXT}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT1, anchor="w", wraplength=420,
        ).pack(anchor="w", padx=12, pady=2)

        ctk.CTkFrame(text_card, height=1, fg_color=C_BORDER).pack(fill="x", padx=12, pady=6)

        # 录音状态
        self._status_label = ctk.CTkLabel(
            text_card, text="准备就绪",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        )
        self._status_label.pack(anchor="w", padx=12, pady=(0, 8))

        # 录音按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        self._record_btn = ctk.CTkButton(
            btn_frame, text="开始录音", width=120, height=36, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=C_ERROR, hover_color="#A52318",
            command=self._toggle_recording,
        )
        self._record_btn.pack(side="left")

        self._save_btn = ctk.CTkButton(
            btn_frame, text="保存", width=80, height=36, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_SUCCESS, hover_color="#0A5E0A",
            state="disabled",
            command=self._save,
        )
        self._save_btn.pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="取消", width=80, height=36, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TXT2, hover_color="#F5F5F5",
            command=self.destroy,
        ).pack(side="right")

    def _toggle_recording(self):
        """切换录音状态"""
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """开始录音"""
        import tempfile
        from unified_recorder import UnifiedRecorder
        import logging
        logger = logging.getLogger("MeetScribe")

        try:
            # 创建临时目录
            self._temp_dir = tempfile.mkdtemp()
            self._audio_path = None
            logger.debug(f"[ADD-VOICE] Created temp dir: {self._temp_dir}")

            # 创建录音器
            self._recorder = UnifiedRecorder(
                save_dir=self._temp_dir,
                use_vb_cable=False,
            )

            # 设置回调函数
            self._recorder.on_stop_complete = self._on_recording_complete

            # 开始录音
            self._recorder.start("mic")
            self._recording = True

            # 更新 UI
            self._record_btn.configure(text="停止录音")
            self._status_label.configure(text="录音中... 请朗读上述文本", text_color=C_ERROR)
            logger.debug("[ADD-VOICE] Recording started")

        except Exception as e:
            import logging
            logger = logging.getLogger("MeetScribe")
            logger.error(f"[ADD-VOICE] Failed to start recording: {e}")
            from tkinter import messagebox
            messagebox.showerror("录音错误", f"无法启动录音:\n{e}", parent=self)
            self._status_label.configure(text="录音启动失败", text_color=C_ERROR)

    def _stop_recording(self):
        """停止录音"""
        import logging
        logger = logging.getLogger("MeetScribe")

        if self._recorder:
            logger.debug("[ADD-VOICE] Stopping recording...")
            self._recorder.stop()
            self._recording = False

            # 更新 UI
            self._record_btn.configure(text="开始录音", state="disabled")
            self._status_label.configure(text="正在提取声纹...", text_color=C_TXT3)

    def _on_recording_complete(self, saved_files):
        """录音完成回调"""
        import logging
        logger = logging.getLogger("MeetScribe")

        logger.debug(f"[ADD-VOICE] Recording complete, saved files: {saved_files}")

        if saved_files:
            self._audio_path = saved_files[0]
            logger.debug(f"[ADD-VOICE] Using audio file: {self._audio_path}")

            # 在后台线程处理音频
            import threading
            thread = threading.Thread(target=self._process_audio, daemon=True)
            thread.start()
        else:
            logger.error("[ADD-VOICE] No files saved!")
            self.after(0, lambda: self._status_label.configure(
                text="录音失败，请重试", text_color=C_ERROR))
            self.after(0, lambda: self._record_btn.configure(state="normal"))

    def _process_audio(self):
        """处理录音，提取声纹（在后台线程执行）"""
        import logging
        logger = logging.getLogger("MeetScribe")

        logger.debug(f"[ADD-VOICE] Processing audio: {self._audio_path}")
        logger.debug(f"[ADD-VOICE] File exists: {os.path.exists(self._audio_path) if self._audio_path else False}")

        if not self._audio_path or not os.path.exists(self._audio_path):
            logger.error("[ADD-VOICE] Audio file not found!")
            self.after(0, lambda: self._status_label.configure(
                text="录音失败，请重试", text_color=C_ERROR))
            self.after(0, lambda: self._record_btn.configure(state="normal"))
            return

        try:
            from voiceprint import VoiceprintLibrary

            # 使用 VoiceprintLibrary 的 extract_embedding_from_file 方法
            library = VoiceprintLibrary()
            embeddings = library.extract_embedding_from_file(self._audio_path)

            logger.debug(f"[ADD-VOICE] Extracted embeddings: {embeddings}")

            if embeddings:
                # 保存嵌入向量
                self._embedding = list(embeddings.values())[0]
                self.after(0, lambda: self._save_btn.configure(state="normal"))
                self.after(0, lambda: self._status_label.configure(
                    text=f"声纹提取成功！共 {len(embeddings)} 个说话人",
                    text_color=C_SUCCESS))
            else:
                self.after(0, lambda: self._status_label.configure(
                    text="未能提取声纹，请重试",
                    text_color=C_ERROR))
                self.after(0, lambda: self._record_btn.configure(state="normal"))

        except Exception as e:
            self.after(0, lambda: self._status_label.configure(
                text=f"处理失败: {str(e)[:50]}",
                text_color=C_ERROR))
            self.after(0, lambda: self._record_btn.configure(state="normal"))

    def _save(self):
        """保存到音色库"""
        name = self._name_entry.get().strip()
        if not name:
            from tkinter import messagebox
            messagebox.showwarning("提示", "请输入说话人姓名", parent=self)
            return

        if not hasattr(self, '_embedding'):
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先录音提取声纹", parent=self)
            return

        try:
            from voiceprint import VoiceprintLibrary

            library = VoiceprintLibrary()
            library.add_speaker(name, self._embedding, "manual_recording", quality=0.90)

            from tkinter import messagebox
            messagebox.showinfo("成功", f"已将说话人保存到音色库:\n{name}", parent=self)

            if self._on_save:
                self._on_save()

            self.destroy()

        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", f"保存失败:\n{e}", parent=self)

    def destroy(self):
        """销毁弹窗，清理临时文件"""
        if hasattr(self, '_temp_dir') and os.path.exists(self._temp_dir):
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        super().destroy()
