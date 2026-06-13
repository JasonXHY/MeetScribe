#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe v3 主窗口
"""

import os
import sys
import logging

import customtkinter as ctk

from gui.styles import C_BG, FONT_FAMILY, ICON_PNG, ICON_ICO, OUTPUT_FORMATS
from gui.topbar import TopBar
from gui.home_page import HomePage
from gui.settings_page import SettingsPage
from gui.voiceprint_page import VoiceprintPage
from gui.transcription import TranscriptionHandler
from config import Config
from file_manager import FileManager
from unified_recorder import UnifiedRecorder

logger = logging.getLogger("MeetScribe")


class MeetScribeApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ── Window config ──
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title("MeetScribe")
        self.geometry("1060x720")
        self.minsize(880, 600)
        self.configure(fg_color=C_BG)

        # 窗口图标
        try:
            if os.path.exists(ICON_PNG):
                from PIL import Image
                icon_img = Image.open(ICON_PNG)
                self.iconphoto(True, ctk.CTkImage(light_image=icon_img, size=(32, 32)))
            elif os.path.exists(ICON_ICO):
                self.iconbitmap(ICON_ICO)
        except Exception:
            pass

        # Windows 11 rounded corners (DWM)
        try:
            from ctypes import windll, c_int, byref, sizeof
            hwnd = windll.user32.GetParent(self.winfo_id())
            windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, byref(c_int(2)), sizeof(c_int))
            if os.path.exists(ICON_ICO):
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MeetScribe.App")
        except Exception:
            pass

        # ── Core components ──
        self.config = Config()
        self.file_manager = FileManager()
        self.recorder = UnifiedRecorder(
            save_dir=self.config.get("recording_dir", r"C:\MeetScribe\recordings"),
            use_vb_cable=self.config.get("use_vb_cable", False),
        )
        self._transcription_handler = TranscriptionHandler(self)

        # ── State ──
        self._recording = False
        self._paused = False
        self._recording_mode = self.config.get("recording_mode", "dual")
        self._refresh_pending = None

        # ── Recorder callbacks ──
        self.recorder.on_state_change = self._on_recorder_state_change
        self.recorder.on_save = self._on_recorder_save
        self.recorder.on_stop_complete = self._on_recorder_stop_complete

        # ── Build UI ──
        self._build_ui()
        self._restore_config()

        # ── File manager listener (debounced) ──
        self.file_manager.add_listener(self._on_file_changed)

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.home_page.log("MeetScribe 已启动")
        self.home_page.refresh_file_list()

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=0)  # topbar
        self.grid_rowconfigure(1, weight=1)  # content
        self.grid_rowconfigure(2, weight=0)  # status bar
        self.grid_columnconfigure(0, weight=1)

        # Top navigation bar
        self._topbar = TopBar(self, on_navigate=self._switch_page)
        self._topbar.grid(row=0, column=0, sticky="ew")

        # Content area (full width)
        self._content = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self._content.grid(row=1, column=0, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Pages
        self.home_page = HomePage(self._content, self)
        self.home_page.grid(row=0, column=0, sticky="nsew")

        self.settings_page = SettingsPage(
            self._content, self.config,
            log_callback=self.home_page.log,
        )
        self.settings_page.grid(row=0, column=0, sticky="nsew")

        self.voiceprint_page = VoiceprintPage(self._content, self)
        self.voiceprint_page.grid(row=0, column=0, sticky="nsew")

        # Status bar
        self._build_status_bar()

        # Show home page
        self._switch_page("home")

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, height=28, fg_color="#FAFAFA",
                           corner_radius=0, border_width=1, border_color="#E5E5E5")
        bar.grid(row=2, column=0, sticky="sew")
        bar.grid_propagate(False)

        self._status_lbl = ctk.CTkLabel(
            bar, text="  就绪",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color="#757575", anchor="w",
        )
        self._status_lbl.pack(side="left", padx=8)

        ctk.CTkLabel(
            bar, text="SenseVoice + CAM++ + ct-punc  ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color="#757575", anchor="e",
        ).pack(side="right", padx=8)

    def _switch_page(self, page_key):
        if page_key == "home":
            self.home_page.grid(row=0, column=0, sticky="nsew")
            self.settings_page.grid_forget()
            self.voiceprint_page.grid_forget()
        elif page_key == "settings":
            self.settings_page.grid(row=0, column=0, sticky="nsew")
            self.home_page.grid_forget()
            self.voiceprint_page.grid_forget()
        elif page_key == "voiceprint":
            self.voiceprint_page.grid(row=0, column=0, sticky="nsew")
            self.home_page.grid_forget()
            self.settings_page.grid_forget()
            self.voiceprint_page.refresh_list()
        self._topbar.highlight(page_key)

    def _restore_config(self):
        self.home_page.restore_format()
        self.settings_page.restore_config()

    def _save_current_config(self):
        self.settings_page.save_config()
        fmt_label = self.home_page._batch_format_var.get()
        self.config.set("output_format", OUTPUT_FORMATS.get(fmt_label, "md"))
        self.config.save()

    def _get_speaker_names(self):
        return self.config.get("speaker_names", {})

    def get_output_dir(self):
        """获取输出目录（公共接口）"""
        return self.settings_page._out_dir_entry.get().strip()

    def _set_status(self, text):
        self._status_lbl.configure(text=f"  {text}")

    def _log(self, message):
        """向日志区域追加消息（供 transcription.py 等模块调用）"""
        self.home_page.log(message)

    def _refresh_file_list(self):
        """刷新文件列表 UI（供 transcription.py 等模块调用）"""
        self.home_page.refresh_file_list()

    # ══════════════════════════════════════════════════════════
    #  File Change Debounce
    # ══════════════════════════════════════════════════════════

    def _on_file_changed(self, *_):
        """防抖：200ms 内的多次变更合并为一次刷新"""
        if self._refresh_pending:
            self.after_cancel(self._refresh_pending)
        self._refresh_pending = self.after(200, self._do_refresh)

    def _do_refresh(self):
        """实际执行刷新"""
        self._refresh_pending = None
        self.home_page.refresh_file_list()

    # ══════════════════════════════════════════════════════════
    #  Recorder Callbacks
    # ══════════════════════════════════════════════════════════

    def _on_recorder_state_change(self, is_recording, is_paused):
        self.after(0, self.home_page.update_recording_ui, is_recording, is_paused)

    def _on_recorder_save(self, file_path, duration_s):
        self.after(0, self.file_manager.add_file, file_path, duration_s)

    def _on_recorder_stop_complete(self, saved_files):
        """后台保存完成后回调"""
        self.after(0, self._handle_stop_complete, saved_files)

    def _handle_stop_complete(self, saved_files):
        """录音停止后处理：添加文件到列表、合并双轨、询问转写"""
        for saved in saved_files:
            self.home_page.log(f"录音已保存: {os.path.basename(saved)}")
            # 确保每个文件都添加到 file_manager（如果尚未添加）
            existing = self.file_manager.get_file(saved)
            if not existing:
                self.file_manager.add_file(saved)

        if saved_files:
            if len(saved_files) == 2:
                # 双轨录音：自动合并成一行显示
                from dual_track_merge import find_dual_track_pair
                pair = find_dual_track_pair(saved_files[0])
                if pair:
                    mic_path, sys_path = pair
                    source_names = [os.path.basename(fp) for fp in pair]
                    merged_display = "、".join(source_names)
                    self.file_manager.create_merged_group(list(pair), merged_display)
                    self.home_page.log("双轨录音已合并显示")
                else:
                    self.home_page.log("双轨录音完成，但未找到配对文件")
                # 双轨录音完成后也询问转写
                self.after(300, lambda: self.home_page.ask_transcribe_after_record(saved_files[0]))
            elif len(saved_files) == 1:
                # 单轨录音：直接询问转写
                self.after(300, lambda: self.home_page.ask_transcribe_after_record(saved_files[0]))

    # ══════════════════════════════════════════════════════════
    #  Transcription Callbacks
    # ══════════════════════════════════════════════════════════

    def _on_transcription_done(self, success_count=0, fail_count=0):
        """转写完成回调"""
        self.home_page.update_transcribe_buttons(False)
        self._set_status("转写完成")
        self.home_page.log("所有转写任务已完成")

        # 发送系统通知 + 弹窗
        if success_count > 0 or fail_count > 0:
            self._send_notification(
                "转写完成",
                f"成功: {success_count} 个文件\n失败: {fail_count} 个文件"
            )

            from tkinter import messagebox
            msg = f"转写完成\n\n成功: {success_count} 个文件\n失败: {fail_count} 个文件"
            if success_count > 0:
                msg += f"\n\n结果已保存到: transcripts/"
            messagebox.showinfo("转写完成", msg)

    def _send_notification(self, title, message):
        """发送系统通知（受设置开关控制）"""
        if not self.config.get("enable_notification", True):
            return
        try:
            if sys.platform == "win32":
                from ctypes import windll, wintypes, byref, sizeof, c_wchar_p
                # Windows Toast via PowerShell
                ps_script = (
                    f"[Windows.UI.Notifications.ToastNotificationManager, "
                    f"Windows.UI.Notifications, ContentType = WindowsRuntime] > $null\n"
                    f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                    f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02)\n"
                    f"$textNodes = $template.GetElementsByTagName('text')\n"
                    f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null\n"
                    f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null\n"
                    f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template)\n"
                    f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('MeetScribe').Show($toast)"
                )
                import subprocess
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                logger.info(f"Notification [{title}]: {message}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    # ══════════════════════════════════════════════════════════
    #  Window Close
    # ══════════════════════════════════════════════════════════

    def _on_closing(self):
        if self._recording:
            self.recorder.stop()
        if self._refresh_pending:
            self.after_cancel(self._refresh_pending)
            self._refresh_pending = None
        try:
            self.file_manager._save_to_file()
        except Exception as e:
            logger.warning(f"保存文件历史失败: {e}")
        self._save_current_config()
        self.destroy()


class GUILogHandler(logging.Handler):
    """将日志转发到 GUI 日志区域"""

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._forwarding = False

    def emit(self, record):
        if self._forwarding:
            return
        try:
            self._forwarding = True
            self._app.after(0, self._app.home_page._append_log_widget, self.format(record))
        except Exception:
            self.handleError(record)
        finally:
            self._forwarding = False
