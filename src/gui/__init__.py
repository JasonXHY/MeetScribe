#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe GUI 模块包

注意：不要在此处自动导入 gui.app，会导致循环导入问题。
子进程（transcribe_worker）会导入 transcriber → gui.styles，
如果 gui/__init__.py 导入 gui.app → gui.settings_page → transcriber，
就会形成循环导入，导致子进程卡死。

使用时请直接导入具体模块：from gui.app import MeetScribeApp
"""

__all__ = ["MeetScribeApp", "GUILogHandler"]


def __getattr__(name):
    """延迟导入，避免循环导入"""
    if name == "MeetScribeApp":
        from gui.app import MeetScribeApp
        return MeetScribeApp
    elif name == "GUILogHandler":
        from gui.app import GUILogHandler
        return GUILogHandler
    raise AttributeError(f"module 'gui' has no attribute '{name}'")
