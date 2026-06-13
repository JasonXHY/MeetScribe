"""
弹窗组件（PySide6 完整版）

包含：
- PreviewDialog: 转写结果预览
- ExportDialog: 导出转写结果（含格式转换）
- SpeakerDialog: 发言人管理（含声纹匹配、嵌入向量保存）
- MergeOrderDialog: 合并转写排序
- parse_speakers_from_result: 解析说话人信息
"""

import os
import re
import json
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QComboBox, QFileDialog, QMessageBox,
    QLineEdit, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER, C_SUCCESS, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY, SPEAKER_COLORS, DEFAULT_SPK_QUALITY,
)

logger = logging.getLogger("MeetScribe")


class PreviewDialog(QDialog):
    """转写结果预览弹窗"""

    def __init__(self, parent, file_name, result_path, summary_path=None):
        super().__init__(parent)
        self.setWindowTitle(f"预览 - {file_name}")
        self.setMinimumSize(750, 600)
        self.setModal(True)

        self._transcript_text = ""
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                self._transcript_text = f.read()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法读取结果文件: {e}")
            self.reject()
            return

        self._summary_text = None
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    self._summary_text = f.read()
            except Exception:
                pass

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tab_layout = QHBoxLayout()
        self._btn_transcript = QPushButton("转写结果")
        self._btn_transcript.setFixedSize(90, 30)
        self._btn_transcript.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white; border: none;
                border-radius: 6px; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        self._btn_transcript.clicked.connect(self._show_transcript)
        tab_layout.addWidget(self._btn_transcript)

        self._btn_summary = None
        if self._summary_text:
            self._btn_summary = QPushButton("AI 摘要")
            self._btn_summary.setFixedSize(90, 30)
            self._btn_summary.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {C_TXT2};
                    border: 1px solid {C_BORDER}; border-radius: 6px;
                    font-family: {FONT_FAMILY}; font-size: 12px; }}
            """)
            self._btn_summary.clicked.connect(self._show_summary)
            tab_layout.addWidget(self._btn_summary)

        tab_layout.addStretch()
        layout.addLayout(tab_layout)

        self._text_box = QPlainTextEdit()
        self._text_box.setReadOnly(True)
        self._text_box.setFont(QFont("Consolas", 13))
        self._text_box.setStyleSheet(f"""
            QPlainTextEdit {{ background-color: {C_CARD}; color: {C_TXT1};
                border: 1px solid {C_BORDER}; border-radius: 8px; padding: 8px; }}
        """)
        layout.addWidget(self._text_box, 1)

        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(80, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {C_TXT2};
                border: 1px solid {C_BORDER}; border-radius: 6px;
                font-family: {FONT_FAMILY}; font-size: 12px; }}
            QPushButton:hover {{ background-color: #F5F5F5; }}
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        self._show_transcript()

    def _show_transcript(self):
        self._text_box.setPlainText(self._transcript_text)
        self._btn_transcript.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white; border: none;
                border-radius: 6px; font-family: {FONT_FAMILY}; font-size: 12px; }}
        """)
        if self._btn_summary:
            self._btn_summary.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {C_TXT2};
                    border: 1px solid {C_BORDER}; border-radius: 6px;
                    font-family: {FONT_FAMILY}; font-size: 12px; }}
            """)

    def _show_summary(self):
        if self._summary_text:
            self._text_box.setPlainText(self._summary_text)
            self._btn_summary.setStyleSheet(f"""
                QPushButton {{ background-color: {C_ACCENT}; color: white; border: none;
                    border-radius: 6px; font-family: {FONT_FAMILY}; font-size: 12px; }}
            """)
            self._btn_transcript.setStyleSheet(f"""
                QPushButton {{ background-color: transparent; color: {C_TXT2};
                    border: 1px solid {C_BORDER}; border-radius: 6px;
                    font-family: {FONT_FAMILY}; font-size: 12px; }}
            """)


class ExportDialog(QDialog):
    """导出对话框"""

    def __init__(self, parent, file_path, result_path):
        super().__init__(parent)
        self.setWindowTitle("导出转写结果")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        self._file_path = file_path
        self._result_path = result_path

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("选择导出格式")
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 16px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        # 使用 RadioButton 而非 ComboBox
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        self._format_group = QButtonGroup()
        formats = [
            ("Markdown (.md)", "md"),
            ("纯文本 (.txt)", "txt"),
            ("SRT 字幕 (.srt)", "srt"),
            ("JSON 数据 (.json)", "json"),
        ]
        for text, value in formats:
            rb = QRadioButton(text)
            rb.setProperty("formatValue", value)
            rb.setStyleSheet(f"""
                QRadioButton {{
                    font-family: {FONT_FAMILY};
                    font-size: 12px;
                    background: transparent;
                    border: none;
                    spacing: 8px;
                }}
            """)
            self._format_group.addButton(rb)
            layout.addWidget(rb)
            if value == "md":
                rb.setChecked(True)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {C_TXT2};
                border: 1px solid {C_BORDER}; border-radius: 6px; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        export_btn = QPushButton("导出")
        export_btn.setFixedSize(80, 32)
        export_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 6px; }}
        """)
        export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

    def _do_export(self):
        # 获取选中的格式
        checked_btn = self._format_group.checkedButton()
        if not checked_btn:
            QMessageBox.warning(self, "提示", "请选择导出格式")
            return
        fmt = checked_btn.property("formatValue")

        ext_map = {"md": "*.md", "txt": "*.txt", "srt": "*.srt", "json": "*.json"}
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出转写结果", "", f"{fmt.upper()} 文件 ({ext_map.get(fmt, '*.md')})"
        )

        if save_path:
            try:
                with open(self._result_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if fmt == "txt":
                    content = self._strip_markdown(content)
                elif fmt == "srt":
                    content = self._convert_to_srt(content)
                elif fmt == "json":
                    try:
                        parsed = json.loads(content)
                        content = json.dumps(parsed, ensure_ascii=False, indent=2)
                    except (json.JSONDecodeError, ValueError):
                        data = {"source": os.path.basename(self._file_path), "content": content}
                        content = json.dumps(data, ensure_ascii=False, indent=2)

                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content)

                QMessageBox.information(self, "成功", f"已导出到: {save_path}")
                self.accept()

                import subprocess
                import sys as _sys
                if _sys.platform == "win32":
                    subprocess.Popen(
                        ["explorer", "/select,", save_path],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                else:
                    subprocess.Popen(["open", os.path.dirname(save_path)])
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _strip_markdown(self, text):
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'`(.+?)`', r'\1', text)
        return text

    def _convert_to_srt(self, text):
        lines = text.splitlines()
        srt_lines = []
        counter = 1
        time_pattern = re.compile(r'\[(\d{2}:\d{2}(?::\d{2})?)\]\s*(.+?)\*\*')

        for line in lines:
            m = time_pattern.search(line)
            if m:
                timestamp = m.group(1)
                speaker_text = m.group(2).strip()
                colon_idx = speaker_text.find("**")
                if colon_idx >= 0:
                    speaker_text = speaker_text.split("**")[-1]
                    speaker_text = re.sub(r'^:\s*', '', speaker_text)

                parts = timestamp.split(":")
                if len(parts) == 2:
                    h, m_val = "00", f"{int(parts[0]):02d}"
                    s_val = f"{int(parts[1]):02d}"
                else:
                    h, m_val, s_val = f"{int(parts[0]):02d}", f"{int(parts[1]):02d}", f"{int(parts[2]):02d}"
                srt_time = f"{h}:{m_val}:{s_val},000"

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


class SpeakerDialog(QDialog):
    """发言人管理弹窗（完整版）"""

    def __init__(self, parent, file_name, speakers, on_save=None,
                 speaker_embeddings=None, speaker_qualities=None,
                 audio_path=None, sentences=None):
        super().__init__(parent)
        self.setWindowTitle("发言人管理")
        self.setMinimumSize(540, 600)
        self.setModal(True)

        self._file_name = file_name
        self._speakers = speakers
        self._on_save = on_save
        self._speaker_embeddings = speaker_embeddings or {}
        self._speaker_qualities = speaker_qualities or {}
        self._speaker_entries = {}
        self._audio_path = audio_path
        self._sentences = sentences or []
        self._names = {}

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel("发言人管理")
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 16px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        subtitle = QLabel(f"文件: {self._file_name}  |  识别出 {len(self._speakers)} 位说话人")
        subtitle.setStyleSheet(f"""
            QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 11px; }}
        """)
        layout.addWidget(subtitle)

        # 批量替换
        batch_frame = QFrame()
        batch_frame.setStyleSheet(f"""
            QFrame {{ background-color: {C_CARD}; border: 1px solid {C_BORDER};
                border-radius: 8px; }}
        """)
        batch_layout = QVBoxLayout(batch_frame)
        batch_layout.setContentsMargins(12, 10, 12, 10)

        batch_title = QLabel("批量替换")
        batch_title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 12px; font-weight: bold; }}
        """)
        batch_layout.addWidget(batch_title)

        batch_row = QHBoxLayout()
        batch_row.addWidget(QLabel("将"))

        self._batch_from_combo = QComboBox()
        self._batch_from_combo.setFixedWidth(140)
        for s in self._speakers:
            label = f"{s['label']}" + (f" ({s['name']})" if s.get('name') else "")
            self._batch_from_combo.addItem(label)
        batch_row.addWidget(self._batch_from_combo)

        batch_row.addWidget(QLabel("替换为"))

        self._batch_to_entry = QLineEdit()
        self._batch_to_entry.setPlaceholderText("输入姓名")
        self._batch_to_entry.setFixedWidth(120)
        batch_row.addWidget(self._batch_to_entry)

        batch_btn = QPushButton("替换")
        batch_btn.setFixedSize(60, 30)
        batch_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 6px; font-size: 12px; }}
        """)
        batch_btn.clicked.connect(self._do_batch_replace)
        batch_row.addWidget(batch_btn)

        batch_layout.addLayout(batch_row)
        layout.addWidget(batch_frame)

        # 说话人列表
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        self._speaker_widget = QWidget()
        self._speaker_widget.setStyleSheet("background: transparent;")
        self._speaker_layout = QVBoxLayout(self._speaker_widget)
        self._speaker_layout.setContentsMargins(0, 0, 0, 0)
        self._speaker_layout.setSpacing(8)

        self._refresh_speaker_list()

        scroll_area.setWidget(self._speaker_widget)
        layout.addWidget(scroll_area, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {C_TXT2};
                border: 1px solid {C_BORDER}; border-radius: 6px; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setFixedSize(80, 32)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 6px; font-weight: bold; }}
        """)
        save_btn.clicked.connect(self._do_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _refresh_speaker_list(self):
        while self._speaker_layout.count():
            child = self._speaker_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._speaker_entries.clear()

        voiceprint_names = []
        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            voiceprint_names = sorted(library.get_speakers().keys())
        except Exception as e:
            logger.debug(f"[DIALOG] 加载音色库人名失败: {e}")

        for i, s in enumerate(self._speakers):
            row = QHBoxLayout()
            row.setSpacing(6)

            color_label = QLabel()
            color_label.setFixedSize(12, 12)
            color = SPEAKER_COLORS[i % len(SPEAKER_COLORS)]
            color_label.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
            row.addWidget(color_label)

            label = QLabel(s['label'])
            label.setFixedWidth(80)
            label.setStyleSheet(f"QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 12px; }}")
            row.addWidget(label)

            entry = QLineEdit()
            entry.setPlaceholderText("输入真实姓名")
            if s.get('name'):
                entry.setText(s['name'])
            entry.setStyleSheet(f"""
                QLineEdit {{ border: 1px solid {C_BORDER}; border-radius: 6px;
                    padding: 4px 8px; font-family: {FONT_FAMILY}; font-size: 12px; }}
            """)
            row.addWidget(entry, 1)
            self._speaker_entries[i] = entry

            self._add_match_suggestion(row, s, entry)

            if voiceprint_names:
                combo = QComboBox()
                combo.addItem("（从音色库选择）")
                combo.addItems(voiceprint_names)
                combo.setFixedWidth(140)
                combo.setStyleSheet(f"""
                    QComboBox {{
                        border: 1px solid {C_BORDER}; border-radius: 4px;
                        padding: 2px 4px; font-family: {FONT_FAMILY}; font-size: 11px;
                        background-color: {C_BG};
                    }}
                    QComboBox::drop-down {{
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 20px;
                    }}
                """)
                combo.currentTextChanged.connect(
                    lambda name, e=entry: self._on_voiceprint_select(name, e)
                )
                row.addWidget(combo)

            pct_label = QLabel(f"{s['pct']:.1f}%")
            pct_label.setFixedWidth(50)
            pct_label.setStyleSheet(f"QLabel {{ color: {C_TXT3}; font-family: {FONT_FAMILY}; font-size: 11px; }}")
            row.addWidget(pct_label)

            save_btn = QPushButton("保存到音色库")
            save_btn.setFixedSize(100, 28)
            save_btn.setStyleSheet(f"""
                QPushButton {{ background-color: {C_ACCENT}; color: white;
                    border: none; border-radius: 4px; font-size: 11px; }}
            """)
            save_btn.clicked.connect(lambda checked, idx=i: self._save_to_library(idx))
            row.addWidget(save_btn)

            container = QWidget()
            container.setLayout(row)
            self._speaker_layout.addWidget(container)

        self._speaker_layout.addStretch()

    def _do_batch_replace(self):
        sel = self._batch_from_combo.currentText()
        new_name = self._batch_to_entry.text().strip()
        if not new_name:
            QMessageBox.information(self, "提示", "请输入替换后的姓名")
            return

        for i, s in enumerate(self._speakers):
            label = f"{s['label']}" + (f" ({s['name']})" if s.get('name') else "")
            if label == sel or s['label'] == sel:
                s['name'] = new_name
                if i in self._speaker_entries:
                    self._speaker_entries[i].setText(new_name)
                break

        self._batch_to_entry.clear()
        logger.info(f"发言人映射: {sel} → {new_name}")

    def _save_to_library(self, idx):
        """保存说话人到音色库（优先使用中间片段嵌入）"""
        spk = self._speakers[idx]
        name = self._speaker_entries[idx].text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请先输入说话人姓名")
            return

        middle_embedding = None
        if self._audio_path and self._sentences:
            middle_embedding = self._extract_middle_segment_embedding(
                spk['spk_id'], duration_sec=5
            )

        embedding = middle_embedding
        if embedding is None:
            embedding = self._get_speaker_embedding(spk['spk_id'])

        if embedding is None:
            QMessageBox.information(self, "提示", "无法获取该说话人的声纹数据")
            return

        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            spk_id = spk['spk_id']
            quality = self._speaker_qualities.get(spk_id, DEFAULT_SPK_QUALITY)
            library.add_speaker(name, embedding, self._file_name, quality=quality)
            sample_count = len(library.get_speakers()[name].embeddings)
            speaker_count = len(library.get_speakers())
            QMessageBox.information(self, "成功",
                f"已将说话人保存到音色库:\n\n"
                f"姓名: {name}\n"
                f"样本数: {sample_count}\n"
                f"音色库总人数: {speaker_count}")
            logger.debug(f"[DIALOG] Saved speaker {name} successfully (samples: {sample_count}, total: {speaker_count})")
        except Exception as e:
            logger.error(f"保存到音色库失败: {e}")
            QMessageBox.critical(self, "错误", f"保存到音色库失败:\n{e}")

    def _on_voiceprint_select(self, name, entry):
        if name and name != "（从音色库选择）":
            entry.setText(name)

    def _add_match_suggestion(self, layout, speaker, name_entry):
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

        confidence_pct = int(score * 100)

        suggestion_label = QLabel(f"可能是 {matched_name} ({confidence_pct}%)")
        suggestion_label.setStyleSheet(f"color: #0067C0; font-size: 11px;")
        layout.addWidget(suggestion_label)

        accept_btn = QPushButton("接受")
        accept_btn.setFixedSize(40, 20)
        accept_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 3px; font-size: 10px; }}
        """)
        accept_btn.clicked.connect(lambda: self._accept_suggestion(
            name_entry, matched_name, suggestion_label, accept_btn
        ))
        layout.addWidget(accept_btn)

        logger.debug(f"[DIALOG] 显示匹配建议: {speaker['label']} -> {matched_name} ({confidence_pct}%)")

    def _accept_suggestion(self, entry, name, suggestion_label=None, accept_btn=None):
        entry.setText(name)
        if suggestion_label:
            suggestion_label.hide()
        if accept_btn:
            accept_btn.hide()
        logger.info(f"[DIALOG] 接受匹配建议: {name}")

    def _extract_middle_segment_embedding(self, spk_id, duration_sec=5):
        if not self._audio_path or not self._sentences:
            return None

        try:
            import numpy as np
            import soundfile as sf
            from funasr import AutoModel
        except ImportError:
            return None

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

    @staticmethod
    def _get_embedding_by_id(embeddings, spk_id):
        try:
            key = int(spk_id)
            if key in embeddings:
                return embeddings[key]
        except (ValueError, TypeError):
            pass

        if isinstance(spk_id, str) and spk_id.startswith("spk-"):
            try:
                key = int(spk_id[4:])
                if key in embeddings:
                    return embeddings[key]
            except ValueError:
                pass

        if spk_id in embeddings:
            return embeddings[spk_id]

        return None

    def _get_speaker_embedding(self, spk_id):
        return self._get_embedding_by_id(self._speaker_embeddings, spk_id)

    def _do_save(self):
        self._names = {}
        for i, entry in self._speaker_entries.items():
            name = entry.text().strip()
            if name:
                spk_id = self._speakers[i]['spk_id']
                if isinstance(spk_id, str) and '-' in spk_id:
                    self._names[spk_id] = name
                else:
                    self._names[str(spk_id + 1)] = name

        # 自动保存到音色库
        self._auto_save_voiceprints()

        if self._on_save:
            self._on_save(self._names)
        self.accept()

    def _auto_save_voiceprints(self):
        """自动保存说话人到音色库"""
        if not self._speaker_embeddings:
            return

        try:
            from voiceprint import VoiceprintLibrary
            library = VoiceprintLibrary()
            existing_speakers = library.get_speakers()
        except Exception as e:
            logger.debug(f"自动保存音色记录失败: {e}")
            return

        saved_count = 0
        updated_count = 0
        for i, s in enumerate(self._speakers):
            spk_id = s['spk_id']
            if isinstance(spk_id, str) and '-' in spk_id:
                name = self._names.get(spk_id, '')
            else:
                name = self._names.get(str(spk_id + 1), '')

            if not name:
                continue

            embedding = self._get_speaker_embedding(spk_id)
            if embedding is None:
                logger.debug(f"[DIALOG] 自动保存音色记录: 无法获取 {name} 的声纹数据")
                continue

            try:
                quality = self._speaker_qualities.get(spk_id, DEFAULT_SPK_QUALITY)
                added = library.add_speaker(name, embedding, self._file_name, quality=quality)
                if added:
                    if name in existing_speakers:
                        updated_count += 1
                        logger.info(f"[DIALOG] 追加音色样本: {name}")
                    else:
                        saved_count += 1
                        logger.info(f"[DIALOG] 自动创建音色记录: {name}")
            except Exception as e:
                logger.debug(f"自动保存音色失败: {e}")

        if saved_count > 0 or updated_count > 0:
            logger.info(f"[DIALOG] 新建 {saved_count} 人, 追加 {updated_count} 个样本")


class MergeOrderDialog(QDialog):
    """合并转写排序弹窗"""

    def __init__(self, parent, items, on_confirm=None):
        super().__init__(parent)
        self.setWindowTitle("合并转写排序")
        self.setMinimumSize(500, 450)
        self.setModal(True)

        self._items = list(items)
        self._on_confirm = on_confirm

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("调整文件顺序")
        title.setStyleSheet(f"""
            QLabel {{ color: {C_TXT1}; font-family: {FONT_FAMILY};
                font-size: 16px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        subtitle = QLabel("拖动或使用按钮调整文件顺序，排在前面的文件会先转写")
        subtitle.setStyleSheet(f"color: {C_TXT3}; font-size: 11px;")
        layout.addWidget(subtitle)

        self._list_widget = QScrollArea()
        self._list_widget.setWidgetResizable(True)
        self._list_widget.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        self._list_content = QWidget()
        self._list_content.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_content)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)

        self._refresh_list()

        self._list_widget.setWidget(self._list_content)
        layout.addWidget(self._list_widget, 1)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("开始合并转写")
        confirm_btn.setFixedSize(120, 32)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_SUCCESS}; color: white;
                border: none; border-radius: 6px; }}
        """)
        confirm_btn.clicked.connect(self._do_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def _refresh_list(self):
        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for idx, item in enumerate(self._items):
            row = QHBoxLayout()
            row.setSpacing(8)

            num_label = QLabel(f"{idx + 1}.")
            num_label.setFixedWidth(30)
            num_label.setStyleSheet(f"color: {C_ACCENT}; font-weight: bold;")
            row.addWidget(num_label)

            name_label = QLabel(item.file_name)
            name_label.setStyleSheet(f"color: {C_TXT1}; font-size: 12px;")
            row.addWidget(name_label, 1)

            if idx > 0:
                up_btn = QPushButton("上移")
                up_btn.setFixedSize(50, 26)
                up_btn.setStyleSheet(f"""
                    QPushButton {{ background-color: {C_ACCENT}; color: white;
                        border: none; border-radius: 4px; font-size: 11px; }}
                """)
                up_btn.clicked.connect(lambda checked, i=idx: self._move_up(i))
                row.addWidget(up_btn)

            if idx < len(self._items) - 1:
                down_btn = QPushButton("下移")
                down_btn.setFixedSize(50, 26)
                down_btn.setStyleSheet(f"""
                    QPushButton {{ background-color: {C_ACCENT}; color: white;
                        border: none; border-radius: 4px; font-size: 11px; }}
                """)
                down_btn.clicked.connect(lambda checked, i=idx: self._move_down(i))
                row.addWidget(down_btn)

            container = QWidget()
            container.setLayout(row)
            self._list_layout.addWidget(container)

        self._list_layout.addStretch()

    def _move_up(self, idx):
        if idx > 0:
            self._items[idx], self._items[idx-1] = self._items[idx-1], self._items[idx]
            self._refresh_list()

    def _move_down(self, idx):
        if idx < len(self._items) - 1:
            self._items[idx], self._items[idx+1] = self._items[idx+1], self._items[idx]
            self._refresh_list()

    def _do_confirm(self):
        if self._on_confirm:
            self._on_confirm(self._items)
        self.accept()


class TranscriptionCompleteDialog(QDialog):
    """转写完成弹窗"""

    def __init__(self, parent, success_count, fail_count, output_dir):
        super().__init__(parent)
        self.setWindowTitle("转写完成")
        self.setMinimumSize(400, 250)
        self.setModal(True)
        self._output_dir = output_dir

        self._build(success_count, fail_count)

    def _build(self, success_count, fail_count):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 标题
        title = QLabel("✓ 转写完成")
        title.setStyleSheet(f"""
            QLabel {{ color: {C_SUCCESS}; font-family: {FONT_FAMILY};
                font-size: 18px; font-weight: bold; }}
        """)
        layout.addWidget(title)

        # 信息卡片
        info_card = QFrame()
        info_card.setStyleSheet(f"""
            QFrame {{ background: {C_CARD}; border-radius: 8px; border: 1px solid {C_BORDER}; }}
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)

        info_layout.addWidget(QLabel(f"成功: {success_count} 个文件"))
        if fail_count:
            fail_lbl = QLabel(f"失败: {fail_count} 个文件")
            fail_lbl.setStyleSheet(f"color: {C_ERROR};")
            info_layout.addWidget(fail_lbl)
        info_layout.addWidget(QLabel(f"输出目录: {self._output_dir}"))
        layout.addWidget(info_card)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        open_btn = QPushButton("打开输出目录")
        open_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 6px; padding: 8px 16px; }}
        """)
        open_btn.clicked.connect(self._open_output_dir)
        btn_row.addWidget(open_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {C_TXT2};
                border: 1px solid {C_BORDER}; border-radius: 6px; padding: 8px 16px; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _open_output_dir(self):
        import subprocess
        if os.path.exists(self._output_dir):
            subprocess.Popen(["explorer", self._output_dir])


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
