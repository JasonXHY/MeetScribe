"""
侧耳倾听 GUI 模块
基于 PySide6/Qt
"""


def __getattr__(name):
    if name == "MeetScribeApp":
        from gui.app import MeetScribeApp
        return MeetScribeApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
