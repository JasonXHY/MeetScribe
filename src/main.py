#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 入口
启动 GUI 应用并配置全局日志
"""

import os
import sys
import logging
import multiprocessing

# ── 确保 src 目录在 sys.path 中 ──
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# ── 日志目录 ──
LOG_DIR = os.path.join(os.path.dirname(SRC_DIR), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "meetscribe.log")


def setup_logging():
    """配置全局日志：文件 + 控制台，GUI handler 在 app 启动后追加"""
    root_logger = logging.getLogger("MeetScribe")
    root_logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（热重载场景）
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 格式
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler（UTF-8，追加模式）
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    root_logger.addHandler(console_handler)

    return root_logger


def main():
    """应用入口"""
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("MeetScribe starting up...")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 50)

    try:
        # 导入并创建 GUI
        from gui import MeetScribeApp

        app = MeetScribeApp()

        # 将 GUI 日志 handler 追加到 MeetScribe logger
        from gui import GUILogHandler
        gui_handler = GUILogHandler(app)
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger("MeetScribe").addHandler(gui_handler)

        logger.info("GUI initialized, entering main loop")

        # 启动主循环
        app.mainloop()

    except ImportError as e:
        logger.critical(f"Failed to import required module: {e}")
        print(f"\n[FATAL] Missing dependency: {e}")
        print("Please install required packages:")
        print("  pip install customtkinter sounddevice soundfile numpy")
        sys.exit(1)

    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        print(f"\n[FATAL] Unexpected error: {e}")
        sys.exit(1)

    logger.info("MeetScribe exited normally")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
