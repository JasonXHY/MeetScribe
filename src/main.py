"""
侧耳倾听 入口（PySide6 版本）
启动 GUI 应用并配置全局日志
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import traceback

# ── 确保 src 目录在 sys.path 中 ──
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# ── 数据目录（打包模式用 %LOCALAPPDATA%，开发模式用项目目录） ──
from utils import get_data_dir
DATA_DIR = get_data_dir()

# ── 启动时预创建必要目录 ──
for _dir in ("logs", "config", "data", "recordings", "transcripts"):
    os.makedirs(os.path.join(DATA_DIR, _dir), exist_ok=True)

LOG_DIR = os.path.join(DATA_DIR, "logs")
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

    # 文件 handler（UTF-8，轮转：最大 5MB，保留 3 个备份）
    file_handler = RotatingFileHandler(LOG_FILE, encoding="utf-8", maxBytes=5*1024*1024, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    root_logger.addHandler(console_handler)

    return root_logger


def exception_hook(exc_type, exc_value, exc_traceback):
    """全局异常钩子 - 捕获未处理的异常"""
    logger = logging.getLogger("MeetScribe")
    logger.critical("=== UNCAUGHT EXCEPTION ===")
    logger.critical(f"Type: {exc_type.__name__}")
    logger.critical(f"Value: {exc_value}")
    logger.critical("Traceback:")
    for line in traceback.format_exception(exc_type, exc_value, exc_traceback):
        logger.critical(line.rstrip())
    logger.critical("=== END EXCEPTION ===")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main():
    """应用入口"""
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("侧耳倾听 starting up (PySide6)...")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info("=" * 50)

    # 设置全局异常钩子
    sys.excepthook = exception_hook

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        import PySide6
        logger.info(f"PySide6 version: {PySide6.__version__}")

        # 高 DPI 支持
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        qapp = QApplication(sys.argv)
        logger.info("QApplication created")

        # 导入并创建 GUI
        from gui.app import MeetScribeApp, GUILogHandler

        app = MeetScribeApp()
        logger.info("MeetScribeApp created")

        # 显示窗口
        app.show()
        app.raise_()
        app.activateWindow()
        logger.info(f"Window shown - visible: {app.isVisible()}, size: {app.size().width()}x{app.size().height()}")

        # 将 GUI 日志 handler 追加到 MeetScribe logger
        gui_handler = app._gui_log_handler
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger("MeetScribe").addHandler(gui_handler)

        logger.info("GUI initialized, entering main loop")

        # 启动主循环
        exit_code = qapp.exec()

        # 清理
        logging.getLogger("MeetScribe").removeHandler(gui_handler)
        logger.info("侧耳倾听 exited normally")
        sys.exit(exit_code)

    except ImportError as e:
        logger.critical(f"Failed to import required module: {e}")
        logger.critical(traceback.format_exc())
        print(f"\n[FATAL] Missing dependency: {e}")
        print("Please install required packages:")
        print("  pip install PySide6 soundfile numpy")
        sys.exit(1)

    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        logger.critical(traceback.format_exc())
        print(f"\n[FATAL] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
