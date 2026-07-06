"""共享 Worker 线程类"""

from PySide6.QtCore import QThread, Signal


class ModelDownloadWorker(QThread):
    """模型下载工作线程（统一版）"""
    finished = Signal(bool, str)  # success, message
    progress = Signal(int, str)   # percent, message

    def __init__(self, model_manager, parent=None):
        super().__init__(parent)
        self._model_manager = model_manager

    def run(self):
        try:
            self.progress.emit(0, "正在检查模型...")

            def _cb(msg):
                self.progress.emit(0, str(msg))

            success, msg = self._model_manager.download_all_missing(progress_callback=_cb)
            self.progress.emit(100 if success else 0, msg)
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))
