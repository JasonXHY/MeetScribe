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
    QPlainTextEdit, QTextBrowser, QComboBox, QFileDialog, QMessageBox,
    QLineEdit, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor

from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_BTN_HOVER, C_SUCCESS, C_ERROR,
    C_TXT1, C_TXT2, C_TXT3, FONT_FAMILY, SPEAKER_COLORS, DEFAULT_SPK_QUALITY,
)

logger = logging.getLogger("MeetScribe")


class EmbeddingExtractWorker(QThread):
    """后台提取声纹嵌入向量（避免阻塞 GUI）"""
    finished = Signal(object)  # embedding or None
    error = Signal(str)

    def __init__(self, audio_path, sentences, spk_id):
        super().__init__()
        self._audio_path = audio_path
        self._sentences = sentences
        self._spk_id = spk_id

    def run(self):
        try:
            import numpy as np
            import soundfile as sf
            from funasr import AutoModel
        except ImportError:
            self.error.emit("缺少依赖库")
            return

        try:
            speaker_segments = []
            for sent in self._sentences:
                sent_spk = sent.get('spk_id', sent.get('spk', -1))
                if sent_spk == self._spk_id:
                    speaker_segments.append({
                        'start': sent.get('start', 0),
                        'end': sent.get('end', 0),
                    })

            if not speaker_segments:
                self.finished.emit(None)
                return

            segments_sorted = sorted(speaker_segments, key=lambda s: s['end'] - s['start'], reverse=True)
            best = segments_sorted[0]
            start_ms, end_ms = _middle_third_window(best['start'], best['end'])

            audio_data, sr = sf.read(self._audio_path)
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            start_s = int(start_ms / 1000 * sr)
            end_s = int(end_ms / 1000 * sr)
            segment = audio_data[start_s:end_s].astype(np.float32)

            min_len = int(0.5 * sr)
            if len(segment) < min_len:
                self.finished.emit(None)
                return

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
                    self.finished.emit(spk_emb.tolist())
                    return
            self.finished.emit(None)
        except Exception as e:
            self.error.emit(str(e))


def _middle_third_window(start_ms, end_ms):
    """SPK-007: 返回发言段"中间 1/3"的时间窗口（毫秒）。

    将 [start_ms, end_ms] 三等分，取中间一段。该窗口去除发言起止处
    最容易混入静音/其他说话人的部分，质量最高。
    """
    length = end_ms - start_ms
    third = length / 3.0
    return start_ms + third, end_ms - third


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

        self._text_box = QTextBrowser()
        self._text_box.setOpenExternalLinks(False)
        self._text_box.setFont(QFont("Consolas", 13))
        self._text_box.setStyleSheet(f"""
            QTextBrowser {{ background-color: {C_CARD}; color: {C_TXT1};
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
        try:
            import markdown
            html = markdown.markdown(self._transcript_text)
            self._text_box.setHtml(html)
        except ImportError:
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
            try:
                import markdown
                html = markdown.markdown(self._summary_text)
                self._text_box.setHtml(html)
            except ImportError:
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

    def __init__(self, parent, file_path, result_path, summary_path=None):
        super().__init__(parent)
        self.setWindowTitle("导出转写结果")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        self._file_path = file_path
        self._result_path = result_path
        self._summary_path = summary_path

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

                # 读取摘要内容（如果存在）
                summary_content = ""
                if self._summary_path and os.path.exists(self._summary_path):
                    with open(self._summary_path, "r", encoding="utf-8") as f:
                        summary_content = f.read()

                # 合并内容：摘要在前，转写在后
                if summary_content:
                    content = f"{summary_content}\n\n---\n\n{content}"

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
                 audio_path=None, sentences=None, cross_track_pairs=None,
                 is_dual_track=False):
        super().__init__(parent)
        self.setWindowTitle("发言人管理")
        self.setMinimumSize(820, 560)
        self.resize(900, 600)
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
        self._cross_track_pairs = cross_track_pairs or []
        self._is_dual_track = is_dual_track
        self._merge_rules = []  # 已确认的合并规则: [(local_label, remote_label, unified_name)]

        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

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

        # 跨轨合并区域（仅双轨模式且有跨轨匹配对时显示）
        if self._is_dual_track and self._cross_track_pairs:
            self._build_merge_section(layout)

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

    # ══════════════════════════════════════════════════════════
    #  跨轨合并区域
    # ══════════════════════════════════════════════════════════

    def _build_merge_section(self, parent_layout):
        """构建跨轨发言人合并区域"""
        merge_frame = QFrame()
        merge_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFBEB;
                border: 1px solid #FDE68A;
                border-radius: 8px;
            }}
        """)
        merge_layout = QVBoxLayout(merge_frame)
        merge_layout.setContentsMargins(14, 12, 14, 12)
        merge_layout.setSpacing(6)

        # 标题
        merge_title = QLabel("跨轨发言人合并")
        merge_title.setStyleSheet(f"""
            QLabel {{ color: #92400E; font-family: {FONT_FAMILY};
                font-size: 12px; font-weight: bold; }}
        """)
        merge_layout.addWidget(merge_title)

        merge_hint = QLabel("声纹匹配检测到以下发言人可能是同一人，确认后转写文本中的标签将统一更新")
        merge_hint.setStyleSheet(f"""
            QLabel {{ color: #B45309; font-family: {FONT_FAMILY}; font-size: 11px; }}
        """)
        merge_layout.addWidget(merge_hint)

        # 已确认的合并规则展示区（可滚动）
        self._merge_pairs_container = QWidget()
        self._merge_pairs_container.setStyleSheet("background: transparent;")
        self._merge_pairs_layout = QVBoxLayout(self._merge_pairs_container)
        self._merge_pairs_layout.setContentsMargins(0, 4, 0, 0)
        self._merge_pairs_layout.setSpacing(4)

        # 构建预填合并对
        self._merge_pair_widgets = []
        for local_label, remote_label, score in self._cross_track_pairs:
            self._add_merge_pair_row(local_label, remote_label, score)

        self._merge_pairs_layout.addStretch()
        merge_layout.addWidget(self._merge_pairs_container)

        # 手动添加合并规则
        add_row = QHBoxLayout()
        add_row.setSpacing(8)

        self._merge_local_combo = QComboBox()
        self._merge_local_combo.setFixedWidth(140)
        self._merge_local_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid #FDE68A; border-radius: 6px;
                padding: 2px 8px; font-family: {FONT_FAMILY}; font-size: 12px;
                background-color: #FFF; color: #6B7280;
            }}
        """)
        # 填充本地发言人选项
        self._merge_local_combo.addItem("选择本地发言人")
        for s in self._speakers:
            if s['label'].startswith("本地-"):
                self._merge_local_combo.addItem(s['label'])
        add_row.addWidget(self._merge_local_combo)

        arrow_label = QLabel("=")
        arrow_label.setStyleSheet(f"QLabel {{ color: #D97706; font-size: 14px; font-weight: bold; }}")
        add_row.addWidget(arrow_label)

        self._merge_remote_combo = QComboBox()
        self._merge_remote_combo.setFixedWidth(140)
        self._merge_remote_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid #FDE68A; border-radius: 6px;
                padding: 2px 8px; font-family: {FONT_FAMILY}; font-size: 12px;
                background-color: #FFF; color: #6B7280;
            }}
        """)
        # 填充远程发言人选项
        self._merge_remote_combo.addItem("选择远程发言人")
        for s in self._speakers:
            if s['label'].startswith("远程-"):
                self._merge_remote_combo.addItem(s['label'])
        add_row.addWidget(self._merge_remote_combo)

        add_btn = QPushButton("+ 添加合并规则")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                color: #B45309; background: transparent;
                border: 1px dashed #FDE68A; border-radius: 6px;
                font-family: {FONT_FAMILY}; font-size: 11px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background: #FEF3C7; }}
        """)
        add_btn.clicked.connect(self._add_manual_merge_rule)
        add_row.addWidget(add_btn)

        merge_layout.addLayout(add_row)
        parent_layout.addWidget(merge_frame)

    def _add_merge_pair_row(self, local_label, remote_label, score, unified_name=""):
        """添加一个合并对行到合并区域"""
        row = QHBoxLayout()
        row.setSpacing(8)

        # 圆点
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet("background-color: #F59E0B; border-radius: 4px;")
        row.addWidget(dot)

        # 本地 chip
        local_chip = QLabel(local_label)
        local_chip.setStyleSheet(f"""
            QLabel {{
                background-color: #EFF6FF; border: 1px solid #BFDBFE;
                border-radius: 6px; padding: 4px 10px;
                font-family: {FONT_FAMILY}; font-size: 12px; color: #111827;
            }}
        """)
        row.addWidget(local_chip)

        # =
        eq_label = QLabel("=")
        eq_label.setStyleSheet(f"QLabel {{ color: #D97706; font-size: 14px; font-weight: bold; }}")
        row.addWidget(eq_label)

        # 远程 chip
        remote_chip = QLabel(remote_label)
        remote_chip.setStyleSheet(f"""
            QLabel {{
                background-color: #EEF2FF; border: 1px solid #C7D2FE;
                border-radius: 6px; padding: 4px 10px;
                font-family: {FONT_FAMILY}; font-size: 12px; color: #111827;
            }}
        """)
        row.addWidget(remote_chip)

        # 百分比
        score_label = QLabel(f"{score:.0%}")
        score_label.setStyleSheet(f"""
            QLabel {{ color: #B45309; font-family: {FONT_FAMILY};
                font-size: 11px; font-weight: 500; }}
        """)
        row.addWidget(score_label)

        # →
        arrow = QLabel("→")
        arrow.setStyleSheet(f"QLabel {{ color: #D97706; font-size: 14px; font-weight: bold; }}")
        row.addWidget(arrow)

        # 统一姓名输入框
        name_input = QLineEdit()
        name_input.setFixedWidth(120)
        name_input.setPlaceholderText("统一姓名")
        if unified_name:
            name_input.setText(unified_name)
        else:
            # 预填：查找本地发言人是否已有姓名
            for s in self._speakers:
                if s['label'] == local_label and s.get('name'):
                    name_input.setText(s['name'])
                    break
        name_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid #FDE68A; border-radius: 6px;
                padding: 4px 8px; font-family: {FONT_FAMILY}; font-size: 12px;
                background-color: #FFF;
            }}
            QLineEdit:focus {{ border-color: #F59E0B; }}
        """)
        row.addWidget(name_input)

        # 确认按钮
        confirm_btn = QPushButton("确认")
        confirm_btn.setFixedSize(60, 28)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #F59E0B; color: white;
                border: none; border-radius: 6px;
                font-family: {FONT_FAMILY}; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #D97706; }}
            QPushButton:disabled {{ background-color: #D1D5DB; }}
        """)
        confirm_btn.clicked.connect(lambda checked, l=local_label, r=remote_label, inp=name_input:
                                    self._confirm_merge(l, r, inp))
        row.addWidget(confirm_btn)

        container = QWidget()
        container.setLayout(row)
        self._merge_pairs_layout.insertWidget(self._merge_pairs_layout.count() - 1, container)

        self._merge_pair_widgets.append({
            'local': local_label,
            'remote': remote_label,
            'name_input': name_input,
            'confirm_btn': confirm_btn,
            'widget': container,
        })

    def _confirm_merge(self, local_label, remote_label, name_input):
        """确认合并一对发言人"""
        unified_name = name_input.text().strip()
        if not unified_name:
            QMessageBox.information(self, "提示", "请输入统一姓名")
            return

        # 检查是否已有该合并规则
        for rule in self._merge_rules:
            if rule[0] == local_label and rule[1] == remote_label:
                # 更新已有规则
                rule[2] = unified_name
                break
        else:
            self._merge_rules.append((local_label, remote_label, unified_name))

        # 预览：更新发言人列表中的姓名
        for i, s in enumerate(self._speakers):
            if s['label'] in (local_label, remote_label):
                s['name'] = unified_name
                if i in self._speaker_entries:
                    self._speaker_entries[i].setText(unified_name)

        # 禁用确认按钮，标记为已确认
        sender = self.sender()
        if sender:
            sender.setEnabled(False)
            sender.setText("已确认")

        logger.info(f"[MERGE] 合并规则: {local_label} + {remote_label} → {unified_name}")

    def _add_manual_merge_rule(self):
        """手动添加合并规则"""
        local_label = self._merge_local_combo.currentText()
        remote_label = self._merge_remote_combo.currentText()

        if local_label == "选择本地发言人" or remote_label == "选择远程发言人":
            QMessageBox.information(self, "提示", "请选择本地和远程发言人")
            return

        # 检查是否已有该对
        for pair in self._cross_track_pairs:
            if pair[0] == local_label and pair[1] == remote_label:
                QMessageBox.information(self, "提示", "该合并对已存在")
                return

        # 检查是否已确认
        for rule in self._merge_rules:
            if rule[0] == local_label and rule[1] == remote_label:
                QMessageBox.information(self, "提示", "该合并规则已确认")
                return

        # 添加到预设对列表
        self._cross_track_pairs.append((local_label, remote_label, 0.0))

        # 插入新行到 add_row 之前（即 stretch 之前）
        self._add_merge_pair_row(local_label, remote_label, 0.0)

        # 重置下拉框
        self._merge_local_combo.setCurrentIndex(0)
        self._merge_remote_combo.setCurrentIndex(0)

        logger.info(f"[MERGE] 手动添加合并对: {local_label} = {remote_label}")

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
            row.setSpacing(10)

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
                combo.setFixedWidth(150)
                combo.setStyleSheet(f"""
                    QComboBox {{
                        border: 1px solid {C_BORDER}; border-radius: 4px;
                        padding: 2px 6px; font-family: {FONT_FAMILY}; font-size: 12px;
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
            save_btn.setFixedSize(120, 28)
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C_ACCENT}; color: white;
                    border: none; border-radius: 4px; font-size: 12px;
                    padding: 0 10px;
                    min-height: 0px;
                }}
            """)
            save_btn.clicked.connect(lambda checked, idx=i: self._save_to_library(idx))
            row.addWidget(save_btn)

            container = QWidget()
            container.setLayout(row)
            self._speaker_layout.addWidget(container)

        self._speaker_layout.addStretch()

    def _save_to_library(self, idx):
        """保存说话人到音色库（优先使用中间片段嵌入）"""
        spk = self._speakers[idx]
        name = self._speaker_entries[idx].text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请先输入说话人姓名")
            return

        # 禁用按钮防止重入
        save_btn = self.sender()
        if save_btn:
            save_btn.setEnabled(False)

        if self._audio_path and self._sentences:
            # 后台线程提取声纹
            self._saving_idx = idx
            self._save_btn = save_btn
            self._embedding_worker = EmbeddingExtractWorker(
                self._audio_path, self._sentences, spk['spk_id']
            )
            self._embedding_worker.finished.connect(self._on_embedding_extracted)
            self._embedding_worker.error.connect(self._on_embedding_error)
            self._embedding_worker.start()
        else:
            embedding = self._get_speaker_embedding(spk['spk_id'])
            self._finish_save_to_library(idx, embedding, save_btn)

    def _on_embedding_extracted(self, embedding):
        """声纹提取完成回调"""
        idx = self._saving_idx
        save_btn = self._save_btn
        self._finish_save_to_library(idx, embedding, save_btn)

    def _on_embedding_error(self, error_msg):
        """声纹提取失败回调"""
        save_btn = self._save_btn
        if save_btn:
            save_btn.setEnabled(True)
        QMessageBox.warning(self, "提示", f"声纹提取失败: {error_msg}")

    def _finish_save_to_library(self, idx, embedding, save_btn):
        """完成保存到音色库"""
        spk = self._speakers[idx]
        name = self._speaker_entries[idx].text().strip()

        if embedding is None:
            embedding = self._get_speaker_embedding(spk['spk_id'])

        if embedding is None:
            if save_btn:
                save_btn.setEnabled(True)
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
        finally:
            if save_btn:
                save_btn.setEnabled(True)

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
        suggestion_label.setStyleSheet(f"QLabel {{ color: {C_ACCENT}; font-size: 12px; font-weight: 500; }}")
        layout.addWidget(suggestion_label)

        accept_btn = QPushButton("接受")
        accept_btn.setFixedSize(60, 28)
        accept_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT}; color: white;
                border: none; border-radius: 4px; font-size: 12px;
                padding: 0 8px;
                min-height: 0px;
            }}
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
        # duration_sec 保留参数仅作兼容；SPK-007 实际取最长发言"中间 1/3"。
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
        # SPK-007: 取最长发言的"中间 1/3"作为声纹片段。
        start_ms, end_ms = _middle_third_window(best['start'], best['end'])

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
        # 1. 直接用原始 key 查找（兼容字符串 key）
        if spk_id in embeddings:
            return embeddings[spk_id]

        # 2. 尝试转整数查找
        try:
            key = int(spk_id)
            if key in embeddings:
                return embeddings[key]
        except (ValueError, TypeError):
            pass

        # 3. 兼容 "spk-N" 格式
        if isinstance(spk_id, str) and spk_id.startswith("spk-"):
            try:
                key = int(spk_id[4:])
                if key in embeddings:
                    return embeddings[key]
            except ValueError:
                pass

        # 4. 尝试字符串形式查找（JSON key 是字符串）
        str_key = str(spk_id)
        if str_key in embeddings:
            return embeddings[str_key]

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

        # 应用所有已确认的合并规则（远程标签 → 统一姓名）
        for local_label, remote_label, unified_name in self._merge_rules:
            if unified_name:
                self._names[remote_label] = unified_name
                # 如果本地发言人尚未命名，也用统一姓名
                if local_label not in self._names or not self._names[local_label]:
                    self._names[local_label] = unified_name

        # 自动保存到音色库
        self._auto_save_voiceprints()

        if self._on_save:
            self._on_save(self._names, self._merge_rules if self._merge_rules else None)
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

        subtitle = QLabel("使用上移/下移按钮调整文件顺序，排在前面的文件会先转写")
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
