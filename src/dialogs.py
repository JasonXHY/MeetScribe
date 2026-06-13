#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 弹窗组件
- PreviewDialog: 转写结果预览
- ExportDialog: 导出转写结果
- SpeakerDialog: 发言人管理
- MergeOrderDialog: 合并转写排序
"""

import os
import re
import json
import logging
from tkinter import messagebox

import customtkinter as ctk
from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER,
    C_SUCCESS, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY, ICON_ICO, SPEAKER_COLORS,
)

logger = logging.getLogger("MeetScribe")


class PreviewDialog(ctk.CTkToplevel):
    """转写结果预览弹窗"""

    def __init__(self, parent, file_name, result_path, summary_path=None):
        super().__init__(parent)
        self.title(f"预览 - {file_name}")
        self.geometry("750x600")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=C_BG)

        # 读取转写结果
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                self._transcript_text = f.read()
        except Exception as e:
            messagebox.showerror("错误", f"无法读取结果文件: {e}")
            self.destroy()
            return

        # 读取摘要
        self._summary_text = None
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    self._summary_text = f.read()
            except Exception:
                pass

        self._build()

    def _build(self):
        # 标签页切换
        tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        tab_frame.pack(fill="x", padx=16, pady=(12, 0))

        content_frame = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8)
        content_frame.pack(fill="both", expand=True, padx=16, pady=(8, 12))

        self._text_box = ctk.CTkTextbox(
            content_frame, wrap="word",
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=C_CARD, text_color=C_TXT1,
            border_width=0, corner_radius=8,
        )
        self._text_box.pack(fill="both", expand=True, padx=8, pady=8)

        def show_transcript():
            self._text_box.configure(state="normal")
            self._text_box.delete("1.0", "end")
            self._text_box.insert("1.0", self._transcript_text)
            self._text_box.configure(state="disabled")
            btn_transcript.configure(fg_color=C_ACCENT, text_color="white")
            if self._summary_text:
                btn_summary.configure(fg_color="transparent", text_color=C_TXT2)

        def show_summary():
            if self._summary_text:
                self._text_box.configure(state="normal")
                self._text_box.delete("1.0", "end")
                self._text_box.insert("1.0", self._summary_text)
                self._text_box.configure(state="disabled")
                btn_summary.configure(fg_color=C_ACCENT, text_color="white")
                btn_transcript.configure(fg_color="transparent", text_color=C_TXT2)

        btn_transcript = ctk.CTkButton(
            tab_frame, text="转写结果", width=90, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_ACCENT, text_color="white",
            command=show_transcript,
        )
        btn_transcript.pack(side="left", padx=(0, 6))

        btn_summary = None
        if self._summary_text:
            btn_summary = ctk.CTkButton(
                tab_frame, text="AI 摘要", width=90, height=30, corner_radius=6,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                fg_color="transparent", text_color=C_TXT2,
                border_width=1, border_color=C_BORDER,
                command=show_summary,
            )
            btn_summary.pack(side="left")

        show_transcript()


class ExportDialog(ctk.CTkToplevel):
    """导出对话框"""

    def __init__(self, parent, file_path, result_path):
        super().__init__(parent)
        self.title("导出转写结果")
        self.geometry("400x300")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=C_BG)

        self._file_path = file_path
        self._result_path = result_path
        self._export_format = ctk.StringVar(value="md")

        self._build()

    def _build(self):
        # 标题
        ctk.CTkLabel(
            self, text="选择导出格式",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=C_TXT1
        ).pack(pady=(20, 10))

        # 格式选择
        formats = [
            ("Markdown (.md)", "md"),
            ("纯文本 (.txt)", "txt"),
            ("SRT 字幕 (.srt)", "srt"),
            ("JSON 数据 (.json)", "json"),
        ]

        for text, value in formats:
            ctk.CTkRadioButton(
                self, text=text,
                variable=self._export_format,
                value=value,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=C_TXT1
            ).pack(anchor="w", padx=40, pady=5)

        # 按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(20, 20))

        ctk.CTkButton(
            btn_frame, text="取消", width=100, height=32,
            fg_color=C_TXT3, hover_color="#616161",
            command=self.destroy
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="导出", width=100, height=32,
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=self._export
        ).pack(side="right")

    def _export(self):
        """执行导出"""
        format_type = self._export_format.get()
        import json as json_mod

        try:
            base_name = os.path.splitext(self._result_path)[0]
            ext_map = {
                "md": ".md",
                "txt": ".txt",
                "srt": ".srt",
                "json": ".json",
            }
            ext = ext_map.get(format_type, ".md")
            out_path = base_name + ext

            # 如果文件已存在，自动加序号
            if os.path.exists(out_path) and out_path != self._result_path:
                counter = 1
                while os.path.exists(f"{base_name}({counter}){ext}"):
                    counter += 1
                out_path = f"{base_name}({counter}){ext}"

            with open(self._result_path, "r", encoding="utf-8") as f:
                content = f.read()

            if format_type == "md" or format_type == "txt":
                # 纯文本：去掉 Markdown 格式标记
                if format_type == "txt":
                    content = self._strip_markdown(content)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(content)

            elif format_type == "srt":
                srt_content = self._convert_to_srt(content)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)

            elif format_type == "json":
                # 尝试解析现有 JSON，否则包装为纯文本
                try:
                    parsed = json_mod.loads(content)
                    with open(out_path, "w", encoding="utf-8") as f:
                        json_mod.dump(parsed, f, ensure_ascii=False, indent=2)
                except (json_mod.JSONDecodeError, ValueError):
                    # 将文本内容包装为 JSON
                    data = {
                        "source": os.path.basename(self._file_path),
                        "content": content,
                        "format": "plain",
                    }
                    with open(out_path, "w", encoding="utf-8") as f:
                        json_mod.dump(data, f, ensure_ascii=False, indent=2)

            self.destroy()

            # 打开文件所在文件夹
            import subprocess
            import sys
            folder = os.path.dirname(out_path)
            if sys.platform == "win32":
                subprocess.Popen(
                    ["explorer", "/select,", out_path],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            else:
                subprocess.Popen(["open", folder])

        except Exception as e:
            messagebox.showerror("导出失败", f"导出文件时出错:\n{e}")

    def _strip_markdown(self, text):
        """去除 Markdown 格式标记，转为纯文本"""
        # 移除加粗标记
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        # 移除标题标记
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # 移除行内代码
        text = re.sub(r'`(.+?)`', r'\1', text)
        return text

    def _convert_to_srt(self, text):
        """将转写结果转换为 SRT 字幕格式"""
        import re as re_mod
        lines = text.splitlines()
        srt_lines = []
        counter = 1
        # 匹配 [MM:SS] 或 [HH:MM:SS] 时间戳
        time_pattern = re_mod.compile(r'\[(\d{2}:\d{2}(?::\d{2})?)\]\s*(.+?)\*\*')

        for line in lines:
            m = time_pattern.search(line)
            if m:
                timestamp = m.group(1)
                speaker_text = m.group(2).strip()
                # 提取冒号后面的实际内容
                colon_idx = speaker_text.find("**")
                if colon_idx >= 0:
                    # 去掉 **speaker:** 部分
                    speaker_text = speaker_text.split("**")[-1]
                    speaker_text = re.sub(r'^:\s*', '', speaker_text)

                # 将时间戳转为 SRT 格式 (HH:MM:SS,000)
                parts = timestamp.split(":")
                if len(parts) == 2:
                    h, m_val = "00", f"{int(parts[0]):02d}"
                    s_val = f"{int(parts[1]):02d}"
                else:
                    h, m_val, s_val = f"{int(parts[0]):02d}", f"{int(parts[1]):02d}", f"{int(parts[2]):02d}"
                srt_time = f"{h}:{m_val}:{s_val},000"
                # 结束时间加 3 秒作为近似
                end_s = int(s_val) + 3
                end_m = int(m_val)
                end_h = int(h)
                if end_s >= 60:
                    end_s -= 60
                    end_m += 1
                if end_m >= 60:
                    end_m -= 60
                    end_h += 1
                srt_end = f"{end_h:02d}:{end_m:02d}:{end_s:02d},000"

                srt_lines.append(str(counter))
                srt_lines.append(f"{srt_time} --> {srt_end}")
                srt_lines.append(speaker_text.strip())
                srt_lines.append("")
                counter += 1

        return "\n".join(srt_lines)


class SpeakerDialog(ctk.CTkToplevel):
    """发言人管理弹窗"""

    def __init__(self, parent, file_name, speakers, on_save=None,
                 speaker_embeddings=None, speaker_qualities=None,
                 audio_path=None, sentences=None):
        """
        Args:
            parent: 父窗口
            file_name: 文件名（显示用）
            speakers: 说话人列表 [{"spk_id", "label", "name", "pct"}, ...]
            on_save: 保存回调 callable(names_dict)
            speaker_embeddings: 说话人嵌入向量 {spk_id: embedding_vector}
            speaker_qualities: 说话人质量评分 {spk_id: quality}
            audio_path: 原始音频文件路径（用于中间片段截取）
            sentences: 转写句子列表 [{"spk", "start", "end", "text"}, ...]
        """
        super().__init__(parent)
        self.title("发言人管理")
        self.geometry("540x600")
        self.configure(fg_color=C_BG)
        self.transient(parent)
        self.grab_set()

        try:
            if os.path.exists(ICON_ICO):
                self.iconbitmap(ICON_ICO)
        except Exception:
            pass

        self._file_name = file_name
        self._speakers = speakers
        self._on_save = on_save
        self._speaker_embeddings = speaker_embeddings or {}
        self._speaker_qualities = speaker_qualities or {}
        self._speaker_entries = {}
        self._audio_path = audio_path
        self._sentences = sentences or []

        self._build(file_name)

    def _build(self, file_name):
        ctk.CTkLabel(
            self, text="发言人管理",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=C_TXT1,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            self, text=f"文件: {file_name}  |  识别出 {len(self._speakers)} 位说话人",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(anchor="w", padx=20, pady=(0, 12))

        # Batch replace
        batch_frame = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8,
                                   border_width=1, border_color=C_BORDER)
        batch_frame.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            batch_frame, text="  批量替换",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=C_TXT1,
        ).pack(anchor="w", padx=12, pady=(10, 6))

        batch_row = ctk.CTkFrame(batch_frame, fg_color="transparent")
        batch_row.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(batch_row, text="将", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left", padx=(0, 6))

        spk_labels = [f"{s['label']}" + (f" ({s['name']})" if s.get('name') else "")
                      for s in self._speakers]
        self._batch_from_var = ctk.StringVar(value=spk_labels[0] if spk_labels else "")
        batch_dropdown = ctk.CTkOptionMenu(
            batch_row, variable=self._batch_from_var, values=spk_labels,
            width=140, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_BG, button_color=C_ACCENT,
            button_hover_color=C_BTN_HOVER,
            text_color=C_TXT1,
        )
        batch_dropdown.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(batch_row, text="替换为", font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=C_TXT2).pack(side="left", padx=(0, 6))

        self._batch_to_entry = ctk.CTkEntry(
            batch_row, height=30, corner_radius=6, width=120,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            placeholder_text="输入姓名", border_color=C_BORDER, fg_color=C_BG,
        )
        self._batch_to_entry.pack(side="left", padx=(0, 6))

        def do_batch_replace():
            sel = self._batch_from_var.get()
            new_name = self._batch_to_entry.get().strip()
            if not new_name:
                messagebox.showinfo("提示", "请输入替换后的姓名", parent=self)
                return
            for s in self._speakers:
                label = f"{s['label']}" + (f" ({s['name']})" if s.get('name') else "")
                if label == sel or s['label'] == sel:
                    s['name'] = new_name
                    break
            self._batch_to_entry.delete(0, "end")
            self._refresh_speaker_list()
            logger.info(f"发言人映射: {sel} → {new_name}")

        ctk.CTkButton(
            batch_row, text="替换", width=60, height=30, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=do_batch_replace,
        ).pack(side="left")

        # Speaker list
        list_card = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8,
                                 border_width=1, border_color=C_BORDER)
        list_card.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self._scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=8, pady=8)

        self._refresh_speaker_list()

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            footer, text="取消", width=80, height=34, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TXT2, hover_color="#F5F5F5",
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            footer, text="  保存", width=80, height=34, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=self._save_and_close,
        ).pack(side="right")

    def _refresh_speaker_list(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._speaker_entries.clear()
        new_labels = [f"{s['label']}" + (f" ({s['name']})" if s.get('name') else "")
                      for s in self._speakers]
        self._batch_from_var.set(new_labels[0] if new_labels else "")

        # 获取音色库人名列表
        voiceprint_names = []
        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            voiceprint_names = sorted(library.get_speakers().keys())
        except Exception as e:
            logger.debug(f"[DIALOG] 加载音色库人名失败: {e}")

        for i, s in enumerate(self._speakers):
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            color = SPEAKER_COLORS[i % len(SPEAKER_COLORS)]
            ctk.CTkLabel(row, text="", width=12, height=12,
                         fg_color=color, corner_radius=6).pack(side="left", padx=(4, 8))

            ctk.CTkLabel(row, text=s['label'], width=80,
                         font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                         text_color=C_TXT3, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(
                row, height=30, corner_radius=6,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                placeholder_text="输入真实姓名", border_color=C_BORDER, fg_color=C_BG,
            )
            if s.get('name'):
                entry.insert(0, s['name'])
            entry.pack(side="left", fill="x", expand=True, padx=(8, 4))
            self._speaker_entries[i] = entry

            # 音色库匹配建议
            self._add_match_suggestion(row, s, entry)

            # 音色库下拉框
            if voiceprint_names:
                combo_values = ["（从音色库选择）"] + voiceprint_names
                combo = ctk.CTkComboBox(
                    row, values=combo_values, width=140, height=30,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    border_color=C_BORDER, fg_color=C_BG,
                    button_color=C_ACCENT, button_hover_color=C_BTN_HOVER,
                    dropdown_fg_color=C_CARD, dropdown_hover_color=C_BTN_HOVER,
                    command=lambda name, e=entry: self._on_voiceprint_select(name, e),
                )
                combo.set("（从音色库选择）")
                combo.pack(side="left", padx=(0, 4))

            ctk.CTkLabel(row, text=f"{s['pct']:.1f}%", width=50,
                         font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                         text_color=C_TXT3, anchor="e").pack(side="right", padx=(0, 4))

            # 保存到音色库按钮
            spk_id = s['spk_id']
            save_btn = ctk.CTkButton(
                row, text="保存到音色库", width=100, height=28,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
                command=lambda idx=i: self._save_to_library(idx),
            )
            save_btn.pack(side="right", padx=(4, 0))

    def _on_voiceprint_select(self, name, entry):
        """从音色库选择人名，自动填充到输入框"""
        if name and name != "（从音色库选择）":
            entry.delete(0, "end")
            entry.insert(0, name)

    def _add_match_suggestion(self, row, speaker, name_entry):
        """添加音色库匹配建议

        对当前说话人的嵌入向量与音色库进行匹配，
        如果匹配成功，在姓名输入框旁边显示建议标签和接受按钮。

        Args:
            row: 所在行 Frame
            speaker: 说话人信息字典 {"spk_id", "label", "name", "pct"}
            name_entry: 姓名输入框 CTkEntry
        """
        # 如果已有姓名，不显示建议
        if speaker.get('name'):
            return

        spk_id = speaker['spk_id']
        embedding = self._get_speaker_embedding(spk_id)
        if embedding is None:
            return

        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            matched_name, score = library.match(embedding)
        except Exception as e:
            logger.debug(f"[DIALOG] 匹配音色库失败: {e}")
            return

        if not matched_name:
            return

        # 显示建议
        confidence_pct = int(score * 100)
        suggestion_frame = ctk.CTkFrame(row, fg_color="transparent")
        suggestion_frame.pack(side="left", padx=2)

        ctk.CTkLabel(
            suggestion_frame,
            text=f"可能是 {matched_name} ({confidence_pct}%)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color="#0067C0",
        ).pack(side="left")

        ctk.CTkButton(
            suggestion_frame,
            text="接受",
            width=40,
            height=20,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=lambda: self._accept_suggestion(name_entry, matched_name, suggestion_frame),
        ).pack(side="left", padx=2)

        logger.debug(f"[DIALOG] 显示匹配建议: {speaker['label']} -> {matched_name} ({confidence_pct}%)")

    def _accept_suggestion(self, entry, name, suggestion_frame=None):
        """接受匹配建议，将建议的姓名填入输入框

        Args:
            entry: 姓名输入框 CTkEntry
            name: 建议的姓名
            suggestion_frame: 建议框架（接受后隐藏）
        """
        entry.delete(0, "end")
        entry.insert(0, name)
        if suggestion_frame:
            suggestion_frame.pack_forget()
        logger.info(f"[DIALOG] 接受匹配建议: {name}")

    def _save_and_close(self):
        names = {}
        for i, entry in self._speaker_entries.items():
            name = entry.get().strip()
            if name:
                spk_id = self._speakers[i]['spk_id']
                if isinstance(spk_id, str) and '-' in spk_id:
                    names[spk_id] = name
                else:
                    names[str(spk_id + 1)] = name

        # 自动创建音色记录（仅保存新名字）
        self._auto_save_voiceprints(names)

        if self._on_save:
            self._on_save(names)
        self.destroy()

    def _auto_save_voiceprints(self, names):
        """自动保存说话人到音色库（支持追加已存在说话人）"""
        if not self._speaker_embeddings:
            return

        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            existing_speakers = library.get_speakers()
        except Exception as e:
            logger.debug(f"[DIALOG] 自动保存音色记录时加载音色库失败: {e}")
            return

        saved_count = 0
        updated_count = 0
        for i, s in enumerate(self._speakers):
            spk_id = s['spk_id']

            if isinstance(spk_id, str) and '-' in spk_id:
                name = names.get(spk_id, '')
            else:
                name = names.get(str(spk_id + 1), '')

            if not name:
                continue

            embedding = self._get_speaker_embedding(spk_id)
            if embedding is None:
                logger.debug(f"[DIALOG] 自动保存音色记录: 无法获取 {name} 的声纹数据")
                continue

            try:
                quality = self._speaker_qualities.get(spk_id, 0.85)
                added = library.add_speaker(name, embedding, self._file_name, quality=quality)
                if added:
                    if name in existing_speakers:
                        updated_count += 1
                        logger.info(f"[DIALOG] 追加音色样本: {name}")
                    else:
                        saved_count += 1
                        logger.info(f"[DIALOG] 自动创建音色记录: {name}")
            except Exception as e:
                logger.warning(f"[DIALOG] 自动保存音色记录失败: {name} - {e}")

        if saved_count > 0 or updated_count > 0:
            logger.info(f"[DIALOG] 新建 {saved_count} 人, 追加 {updated_count} 个样本")

    def _extract_middle_segment_embedding(self, spk_id, duration_sec=5):
        """从说话人最长发言的中间片段提取嵌入向量"""
        if not self._audio_path or not self._sentences:
            return None

        try:
            import numpy as np
            import soundfile as sf
            from funasr import AutoModel
        except ImportError:
            return None

        # 找到该说话人最长的发言片段（兼容 spk 和 spk_id 键名）
        speaker_segments = []
        for sent in self._sentences:
            sent_spk = sent.get('spk_id', sent.get('spk', -1))
            if sent_spk == spk_id:
                speaker_segments.append({
                    'start': sent.get('start', 0),
                    'end': sent.get('end', 0),
                })

        if not speaker_segments:
            return None

        segments_sorted = sorted(speaker_segments, key=lambda s: s['end'] - s['start'], reverse=True)
        best = segments_sorted[0]
        seg_ms = best['end'] - best['start']
        target_ms = duration_sec * 1000

        if seg_ms >= target_ms * 2:
            center = (best['start'] + best['end']) / 2
            start_ms = center - target_ms / 2
            end_ms = center + target_ms / 2
        elif seg_ms >= target_ms:
            start_ms, end_ms = best['start'], best['end']
        else:
            start_ms, end_ms = best['start'], best['end']

        try:
            audio_data, sr = sf.read(self._audio_path)
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            start_s = int(start_ms / 1000 * sr)
            end_s = int(end_ms / 1000 * sr)
            segment = audio_data[start_s:end_s].astype(np.float32)

            min_len = int(0.5 * sr)
            if len(segment) < min_len:
                return None

            model = AutoModel(model="cam++", device="cpu", disable_update=True)
            result = model.inference(input=segment)
            if result and len(result) > 0:
                spk_emb = result[0].get("spk_embedding")
                if spk_emb is not None:
                    if hasattr(spk_emb, "cpu"):
                        spk_emb = spk_emb.cpu().numpy()
                    if hasattr(spk_emb, "tolist"):
                        spk_emb = np.array(spk_emb.tolist())
                    if isinstance(spk_emb, list):
                        spk_emb = np.array(spk_emb)
                    if len(spk_emb.shape) > 1 and spk_emb.shape[0] == 1:
                        spk_emb = spk_emb[0]
                    return spk_emb.tolist()
        except Exception as e:
            logger.warning(f"中间片段提取失败: {e}")
        return None

    def _save_to_library(self, idx):
        """保存说话人到音色库（优先使用中间片段嵌入）"""
        spk = self._speakers[idx]
        name = self._speaker_entries[idx].get().strip()
        if not name:
            messagebox.showwarning("提示", "请先输入说话人姓名", parent=self)
            return

        logger.debug(f"[DIALOG] Saving speaker to library: name={name}, spk_id={spk['spk_id']}")
        logger.debug(f"[DIALOG] Available embeddings: {list(self._speaker_embeddings.keys())}")

        # 优先尝试从长发言中间片段提取
        middle_embedding = None
        if self._audio_path and self._sentences:
            middle_embedding = self._extract_middle_segment_embedding(
                spk['spk_id'], duration_sec=5
            )

        # 降级使用平均嵌入
        embedding = middle_embedding
        if embedding is None:
            embedding = self._get_speaker_embedding(spk['spk_id'])

        if embedding is None:
            logger.debug(f"[DIALOG] Failed to get embedding for spk_id={spk['spk_id']}")
            messagebox.showwarning("提示", "无法提取声纹数据，请确保已转写完成", parent=self)
            return

        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            spk_id = spk['spk_id']
            quality = self._speaker_qualities.get(spk_id, 0.85)
            library.add_speaker(name, embedding, self._file_name, quality=quality)
            speaker_count = len(library.get_speakers())
            sample_count = len(library.get_speakers()[name].embeddings)
            messagebox.showinfo("成功",
                f"已将说话人保存到音色库:\n\n"
                f"姓名: {name}\n"
                f"样本数: {sample_count}\n"
                f"音色库总人数: {speaker_count}",
                parent=self)
            logger.debug(f"[DIALOG] Saved speaker {name} successfully (samples: {sample_count}, total: {speaker_count})")
        except Exception as e:
            logger.error(f"保存到音色库失败: {e}")
            messagebox.showerror("错误", f"保存到音色库失败:\n{e}", parent=self)

    @staticmethod
    def _get_embedding_by_id(embeddings, spk_id):
        """统一的 spk_id 查询方法，兼容 int、str、"spk-N" 格式

        Args:
            embeddings: 嵌入向量字典
            spk_id: 说话人 ID（支持 int、数字字符串、"spk-N" 格式）

        Returns:
            对应的嵌入向量，未找到返回 None
        """
        # 尝试直接 int 转换
        try:
            key = int(spk_id)
            if key in embeddings:
                return embeddings[key]
        except (ValueError, TypeError):
            pass

        # 尝试解析 "spk-N" 格式
        if isinstance(spk_id, str) and spk_id.startswith("spk-"):
            try:
                key = int(spk_id[4:])
                if key in embeddings:
                    return embeddings[key]
            except ValueError:
                pass

        # 尝试直接使用原值
        if spk_id in embeddings:
            return embeddings[spk_id]

        return None

    def _get_speaker_embedding(self, spk_id):
        """获取说话人嵌入向量"""
        logger.debug(f"[DIALOG] _get_speaker_embedding: spk_id={spk_id} (type: {type(spk_id).__name__})")
        logger.debug(f"[DIALOG] self._speaker_embeddings keys: {list(self._speaker_embeddings.keys())}")

        result = self._get_embedding_by_id(self._speaker_embeddings, spk_id)
        if result is None:
            logger.debug(f"[DIALOG] No embedding found for spk_id={spk_id}")
        else:
            logger.debug(f"[DIALOG] Found embedding for spk_id={spk_id}")
        return result


class MergeOrderDialog(ctk.CTkToplevel):
    """合并转写排序弹窗"""

    def __init__(self, parent, items, on_confirm=None):
        """
        Args:
            parent: 父窗口
            items: AudioFile 列表
            on_confirm: 确认回调 callable(ordered_items)
        """
        super().__init__(parent)
        self.title("合并转写 - 调整顺序")
        self.geometry("500x450")
        self.configure(fg_color=C_BG)
        self.transient(parent)
        self.grab_set()

        try:
            if os.path.exists(ICON_ICO):
                self.iconbitmap(ICON_ICO)
        except Exception:
            pass

        self._order_list = list(items)
        self._on_confirm = on_confirm
        self._row_widgets = []

        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="合并转写 - 调整文件顺序",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=C_TXT1,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            self, text="拖动或使用按钮调整文件顺序，排在前面的文件会先转写",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=C_TXT3,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=C_CARD, corner_radius=8,
                                                   border_width=1, border_color=C_BORDER)
        self._list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self._list_frame.grid_columnconfigure(0, weight=1)

        self._refresh_list()

        # 底部按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_frame, text="取消", width=80, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent", border_width=1, border_color=C_BORDER,
            text_color=C_TXT2, hover_color="#F5F5F5",
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="开始合并转写", width=120, height=32, corner_radius=6,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=C_SUCCESS, hover_color="#0A5E0A",
            command=self._confirm,
        ).pack(side="right")

    def _refresh_list(self):
        for w in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()

        for idx, item in enumerate(self._order_list):
            row = ctk.CTkFrame(self._list_frame, fg_color="transparent", height=36)
            row.grid(row=idx, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)
            self._row_widgets.append(row)

            ctk.CTkLabel(row, text=f"{idx+1}.",
                         font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                         text_color=C_ACCENT, width=30).grid(row=0, column=0, padx=(4, 0))

            ctk.CTkLabel(row, text=item.file_name,
                         font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                         text_color=C_TXT1, anchor="w").grid(row=0, column=1, sticky="ew", padx=4)

            if idx > 0:
                ctk.CTkButton(row, text="上移", width=50, height=26, corner_radius=4,
                              font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                              fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
                              command=lambda i=idx: self._move_up(i)).grid(row=0, column=2, padx=2)
            else:
                ctk.CTkLabel(row, text="", width=50).grid(row=0, column=2, padx=2)

            if idx < len(self._order_list) - 1:
                ctk.CTkButton(row, text="下移", width=50, height=26, corner_radius=4,
                              font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                              fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
                              command=lambda i=idx: self._move_down(i)).grid(row=0, column=3, padx=2)
            else:
                ctk.CTkLabel(row, text="", width=50).grid(row=0, column=3, padx=2)

    def _move_up(self, idx):
        if idx > 0:
            self._order_list[idx], self._order_list[idx-1] = self._order_list[idx-1], self._order_list[idx]
            self._refresh_list()

    def _move_down(self, idx):
        if idx < len(self._order_list) - 1:
            self._order_list[idx], self._order_list[idx+1] = self._order_list[idx+1], self._order_list[idx]
            self._refresh_list()

    def _confirm(self):
        self.destroy()
        if self._on_confirm:
            self._on_confirm(self._order_list)


class TranscriptionCompleteDialog(ctk.CTkToplevel):
    """转写完成弹窗"""

    def __init__(self, parent, success_count, fail_count, output_dir):
        super().__init__(parent)
        self.title("转写完成")
        self.geometry("400x250")
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=C_BG)

        self._build(success_count, fail_count, output_dir)

    def _build(self, success_count, fail_count, output_dir):
        # 标题
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            title_frame, text="✓ 转写完成",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=C_SUCCESS
        ).pack(side="left")

        # 信息
        info_frame = ctk.CTkFrame(self, fg_color=C_CARD, corner_radius=8)
        info_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(
            info_frame, text=f"成功: {success_count} 个文件",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            text_color=C_TXT1
        ).pack(anchor="w", padx=15, pady=(15, 5))

        if fail_count > 0:
            ctk.CTkLabel(
                info_frame, text=f"失败: {fail_count} 个文件",
                font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                text_color=C_ERROR
            ).pack(anchor="w", padx=15, pady=(0, 5))

        ctk.CTkLabel(
            info_frame, text=f"结果已保存到: {output_dir}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2
        ).pack(anchor="w", padx=15, pady=(0, 15))

        # 按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="关闭", width=100, height=32,
            fg_color=C_TXT3, hover_color="#616161",
            command=self.destroy
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="打开文件夹", width=120, height=32,
            fg_color=C_ACCENT, hover_color=C_BTN_HOVER,
            command=lambda: self._open_folder(output_dir)
        ).pack(side="right")

    def _open_folder(self, folder_path):
        """打开文件夹"""
        import subprocess
        import sys

        if sys.platform == "win32":
            # Windows: 使用 CREATE_NO_WINDOW 避免闪现控制台
            subprocess.Popen(
                ["explorer", folder_path],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        else:
            # macOS/Linux
            subprocess.Popen(["open", folder_path])


# ── 工具函数 ─────────────────────────────────────────────────

def parse_speakers_from_result(result_path, saved_names=None):
    """从转写结果文件中解析说话人信息

    支持多种格式：
      - md:   **[00:00] Speaker 1** 或 **[00:00] 张三** (AI映射后)
      - llm:  **[Speaker 1]:** 或 ## Speaker 1
      - txt:  [00:00] Speaker 1: 或 Speaker 1:
      - json: segments[].speaker_id
      - 双轨: **[00:00] 本地-1** 或 **[00:00] 远程-2**
      - 摘要: [Speaker N] 姓名 格式
    """
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.debug(f"[SPEAKER-PARSE] Parsing result file: {result_path}")

        if result_path.endswith(".json"):
            speakers = _parse_speakers_json(content)
        else:
            speakers = _parse_speakers_text(content)

        if saved_names:
            speakers = _apply_saved_names(speakers, saved_names)

        logger.debug(f"[SPEAKER-PARSE] Final speakers: {[(s['label'], s['name']) for s in speakers.values()]}")

    except Exception as e:
        logger.error(f"解析说话人信息失败: {e}")
        return []

    return list(speakers.values())


def _parse_speakers_json(content):
    """解析 JSON 格式的说话人信息（segments 中的 speaker_id）"""
    speakers = {}
    data = json.loads(content)
    segments = data.get("segments", [])
    spk_counts = {}
    for seg in segments:
        sid = seg.get("speaker_id", -1)
        if sid >= 0:
            spk_counts[sid] = spk_counts.get(sid, 0) + 1
    total = sum(spk_counts.values()) or 1
    for sid, count in sorted(spk_counts.items()):
        speakers[sid] = {
            "spk_id": sid, "label": f"Speaker {sid + 1}",
            "name": "", "pct": count / total * 100,
        }
    return speakers


def _parse_speakers_text(content):
    """解析文本格式的说话人信息（Speaker N、双轨、姓名模式）"""
    speakers = {}
    spk_counts = {}

    for line in content.splitlines():
        # 支持多种格式：Speaker N、[Speaker N]、[00:00] Speaker N
        m = re.search(r'(?:\[)?Speaker\s+(\d+)(?:\])?', line)
        if m:
            sid = int(m.group(1)) - 1
            spk_counts[sid] = spk_counts.get(sid, 0) + 1
            continue

        m = re.search(r'(本地|远程)-(\d+)', line)
        if m:
            source = m.group(1)
            num = int(m.group(2))
            key = f"{source}-{num}"
            spk_counts[key] = spk_counts.get(key, 0) + 1

    logger.debug(f"[SPEAKER-PARSE] Found speaker counts: {spk_counts}")

    if spk_counts:
        total = sum(spk_counts.values()) or 1
        dual_speakers = {}
        for key, count in sorted(spk_counts.items()):
            if isinstance(key, str) and '-' in key:
                dual_speakers[key] = {
                    "spk_id": key, "label": key,
                    "name": "", "pct": count / total * 100,
                }
            else:
                sid = key
                speakers[sid] = {
                    "spk_id": sid, "label": f"Speaker {sid + 1}",
                    "name": "", "pct": count / total * 100,
                }

        if dual_speakers:
            speakers = dual_speakers

        logger.debug(f"[SPEAKER-PARSE] Parsed speakers: {list(speakers.keys())}")
    else:
        speakers = _parse_speaker_names_from_text(content)

    return speakers


def _parse_speaker_names_from_text(content):
    """从文本中解析姓名模式（**[MM:SS] 姓名** 格式）"""
    speakers = {}
    name_counts = {}
    for line in content.splitlines():
        nm = re.search(r'\*\*\[\d{2}:\d{2}\]\s*(.+?)\*\*', line)
        if nm:
            name = nm.group(1).strip()
            if name:
                name_counts[name] = name_counts.get(name, 0) + 1

    if name_counts:
        total = sum(name_counts.values()) or 1
        for idx, (name, count) in enumerate(
            sorted(name_counts.items(), key=lambda x: -x[1])
        ):
            speakers[idx] = {
                "spk_id": idx,
                "label": f"Speaker {idx + 1}",
                "name": name,
                "pct": count / total * 100,
            }

    return speakers


def _apply_saved_names(speakers, saved_names):
    """将用户保存的说话人名称应用到解析结果中"""
    logger.debug(f"[SPEAKER-PARSE] Applying saved names: {saved_names}")
    if not speakers and saved_names:
        for sid_str, name in saved_names.items():
            if '-' in sid_str:
                speakers[sid_str] = {
                    "spk_id": sid_str, "label": sid_str,
                    "name": name, "pct": 0,
                }
            else:
                sid = int(sid_str) - 1
                speakers[sid] = {
                    "spk_id": sid, "label": f"Speaker {sid + 1}",
                    "name": name, "pct": 0,
                }
    else:
        for sid, info in speakers.items():
            if isinstance(sid, str) and '-' in sid:
                if sid in saved_names and saved_names[sid]:
                    info["name"] = saved_names[sid]
            else:
                key = str(sid + 1)
                if key in saved_names and saved_names[key]:
                    info["name"] = saved_names[key]
    return speakers
