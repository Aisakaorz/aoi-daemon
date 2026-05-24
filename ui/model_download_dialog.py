# -*- coding: utf-8 -*-
"""
语音转文字模型下载对话框
支持下载进度显示、取消、失败提示
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QHBoxLayout, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from tqdm import tqdm

from utils.logger import get_logger

logger = get_logger(__name__)

MODEL_REPO_ID = "guillaumekln/faster-whisper-tiny"


def _set_hf_mirror() -> None:
    """在中国大陆优先使用 hf-mirror 镜像，避免连接 HuggingFace 超时"""
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


class HFProgressBar(tqdm):
    """自定义 tqdm，将下载字节进度转换为总体百分比并发射给 UI"""

    _signal = None
    _total_bytes = 0
    _downloaded_bytes = 0
    _known_totals = set()

    def update(self, n=1):
        super().update(n)
        # 只跟踪字节进度条（unit == 'B'）
        if self.unit != "B" or not self.total:
            return
        # 累加总体积（只累加一次每个不同的 total）
        if self.total not in HFProgressBar._known_totals:
            HFProgressBar._total_bytes += self.total
            HFProgressBar._known_totals.add(self.total)
        HFProgressBar._downloaded_bytes += n
        if HFProgressBar._signal and HFProgressBar._total_bytes > 0:
            pct = int(HFProgressBar._downloaded_bytes / HFProgressBar._total_bytes * 100)
            HFProgressBar._signal.emit(min(pct, 100))


class ModelDownloadWorker(QThread):
    """后台下载 faster-whisper tiny 模型"""

    progress = Signal(int)  # 0 ~ 100
    finished = Signal(bool, str)  # success, message

    def __init__(self, local_dir: str):
        super().__init__()
        self._local_dir = local_dir
        self._cancelled = False

    def run(self) -> None:
        try:
            _set_hf_mirror()
            from huggingface_hub import snapshot_download

            os.makedirs(self._local_dir, exist_ok=True)

            # 重置全局进度计数器
            HFProgressBar._total_bytes = 0
            HFProgressBar._downloaded_bytes = 0
            HFProgressBar._known_totals.clear()
            HFProgressBar._signal = self.progress

            snapshot_download(
                MODEL_REPO_ID,
                local_dir=self._local_dir,
                tqdm_class=HFProgressBar,
            )
            self.finished.emit(True, "")
        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            self.finished.emit(False, str(e))

    def cancel(self) -> None:
        self._cancelled = True


class ModelDownloadDialog(QDialog):
    """模型下载确认 + 进度对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载语音转文字模型")

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "resources", "icons", "app_icon.ico"
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        self._label = QLabel(
            "语音转文字模型尚未下载（约39MB）\n"
            "需要联网从HuggingFace下载\n是否立即下载？"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.hide()
        layout.addWidget(self._progress)

        # 按钮容器：占满宽度，内部居中
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self._btn_download = QPushButton("下载")
        self._btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_download.clicked.connect(self._start_download)

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_download)
        btn_layout.addWidget(self._btn_cancel)
        btn_layout.addStretch()
        layout.addWidget(btn_container)

        self._worker: ModelDownloadWorker | None = None

    def _start_download(self) -> None:
        self._btn_download.setEnabled(False)
        # 取消按钮改为中断下载
        self._btn_cancel.clicked.disconnect(self.reject)
        self._btn_cancel.clicked.connect(self._cancel_download)
        self._progress.show()
        self._label.setText("正在下载模型，请稍候...")

        from voice.stt_provider import MODEL_LOCAL_DIR
        self._local_dir = MODEL_LOCAL_DIR
        self._worker = ModelDownloadWorker(MODEL_LOCAL_DIR)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _cancel_download(self) -> None:
        self._stop_and_cleanup()
        self.reject()

    def _stop_and_cleanup(self) -> None:
        """终止下载线程并清空已下载的残缺文件"""
        if self._worker and self._worker.isRunning():
            # 先断开信号，避免 terminate 后仍收到 finished 信号导致操作已销毁 UI
            try:
                self._worker.finished.disconnect(self._on_finished)
            except Exception:
                pass
            try:
                self._worker.progress.disconnect(self._progress.setValue)
            except Exception:
                pass
            self._worker.cancel()
            self._worker.terminate()
            self._worker.wait(3000)
        # 删除已下载的残缺内容
        local_dir = getattr(self, "_local_dir", None)
        if local_dir and os.path.isdir(local_dir):
            import shutil
            try:
                shutil.rmtree(self._local_dir)
            except Exception:
                pass

    def _on_finished(self, success: bool, message: str) -> None:
        # 对话框已关闭时不操作 UI，避免悬空指针
        if not self.isVisible():
            return
        self._btn_download.setEnabled(True)
        self._btn_cancel.setEnabled(True)
        if success:
            self._label.setText("下载完成！")
            self._progress.setValue(100)
            QTimer.singleShot(800, self.accept)
        else:
            friendly = message
            if any(k in message for k in ("10060", "10054", "Connection", "Timeout")):
                friendly = "网络连接失败，请检查网络或代理设置后重试"
            self._label.setText(f"下载失败：{friendly}")
            self._progress.hide()
            # 恢复取消按钮为关闭对话框
            try:
                self._btn_cancel.clicked.disconnect(self._cancel_download)
            except Exception:
                pass
            self._btn_cancel.clicked.connect(self.reject)

    def closeEvent(self, event) -> None:
        self._stop_and_cleanup()
        super().closeEvent(event)
