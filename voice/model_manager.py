# -*- coding: utf-8 -*-
"""
语音转文字模型管理器
- 模型注册表（名称、大小、仓库ID、本地路径）
- 下载管理器（后台下载、进度跟踪、取消）
"""
import os
import time
import shutil
import threading

from PySide6.QtCore import QObject, Signal, QThread, QTimer
from tqdm import tqdm

from utils.logger import get_logger

logger = get_logger(__name__)

MODELS: dict[str, dict] = {
    "tiny": {
        "name": "Whisper Tiny",
        "size_str": "~75MB",
        "repo_id": "guillaumekln/faster-whisper-tiny",
        "local_dir": os.path.abspath(os.path.join("resources", "whisper", "tiny")),
        "size_bytes": 75 * 1024 * 1024,
    },
}

# 模型完整存在所需的关键文件
_REQUIRED_FILES = ["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"]

_current_model_id: str | None = None


def get_available_models() -> dict[str, dict]:
    """返回所有可用模型配置（深拷贝，防止外部修改）"""
    import copy
    return copy.deepcopy(MODELS)


def get_current_model_id() -> str | None:
    return _current_model_id


def set_current_model_id(model_id: str | None) -> None:
    global _current_model_id
    if model_id is not None and model_id not in MODELS:
        raise ValueError(f"未知模型: {model_id}")
    _current_model_id = model_id
    logger.info(f"当前语音模型切换为: {model_id}")


def is_model_downloaded(model_id: str | None) -> bool:
    """检查指定模型是否已完整下载（关键文件必须全部存在）"""
    if model_id is None or model_id not in MODELS:
        return False
    local_dir = MODELS[model_id]["local_dir"]
    return all(
        os.path.exists(os.path.join(local_dir, fname))
        for fname in _REQUIRED_FILES
    )


def get_model_local_dir(model_id: str | None) -> str | None:
    if model_id is None or model_id not in MODELS:
        return None
    return MODELS[model_id]["local_dir"]


def _fmt_bytes(b: int) -> str:
    """格式化字节数为人类可读字符串"""
    if b > 1024 * 1024 * 1024:
        return f"{b / 1024 / 1024 / 1024:.2f}GB"
    elif b > 1024 * 1024:
        return f"{b / 1024 / 1024:.1f}MB"
    elif b > 1024:
        return f"{b / 1024:.1f}KB"
    else:
        return f"{b}B"


def _set_hf_mirror() -> None:
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


# 线程锁，保护共享进度状态
_progress_lock = threading.Lock()


class _GlobalDownloadTracker:
    """全局下载进度跟踪器（替代易出错的类变量累加）"""
    def __init__(self, total_bytes: int):
        self.total_bytes = total_bytes
        self.downloaded_bytes = 0

    def add_bytes(self, n: int) -> None:
        with _progress_lock:
            self.downloaded_bytes += n

    def get_progress(self) -> tuple[int, int]:
        with _progress_lock:
            return self.downloaded_bytes, self.total_bytes


class HFProgressBar(tqdm):
    """自定义 tqdm：将每个文件的下载增量汇总到全局 tracker，支持取消"""
    _tracker: _GlobalDownloadTracker | None = None
    _signal = None
    _cancelled = False

    def update(self, n=1):
        with _progress_lock:
            if HFProgressBar._cancelled:
                raise RuntimeError("下载已取消")
        super().update(n)
        if self.unit != "B" or not self.total:
            return
        tracker = HFProgressBar._tracker
        if tracker:
            tracker.add_bytes(n)
        signal = HFProgressBar._signal
        if signal:
            signal()


class ModelDownloadWorker(QThread):
    """后台下载模型"""
    progress = Signal(int)  # 0 ~ 100
    progress_detail = Signal(str, int, int, int, str)  # model_id, pct, downloaded, total, speed
    finished = Signal(str, bool, str)  # model_id, success, message

    def __init__(self, model_id: str, repo_id: str, local_dir: str, total_bytes: int, parent=None):
        super().__init__(parent)
        self._model_id = model_id
        self._repo_id = repo_id
        self._local_dir = local_dir
        self._total_bytes = total_bytes
        self._tracker = _GlobalDownloadTracker(total_bytes)
        self._cancelled = False
        self._last_bytes = 0
        self._last_time = time.time()
        self._last_emit_time = 0.0

    def _cleanup(self) -> None:
        """删除已下载的残缺内容（在 worker 线程执行，不阻塞 UI）"""
        if os.path.isdir(self._local_dir):
            try:
                shutil.rmtree(self._local_dir)
                logger.info(f"已清理残缺模型目录: {self._local_dir}")
            except Exception as e:
                logger.warning(f"清理模型目录失败: {e}")

    def _emit_progress(self):
        now = time.time()
        if now - self._last_emit_time < 0.1:
            return
        self._last_emit_time = now
        downloaded, total = self._tracker.get_progress()
        delta = downloaded - self._last_bytes
        dt = now - self._last_time
        speed_str = ""
        if dt > 0.5 and delta > 0:
            speed = delta / dt
            if speed > 1024 * 1024:
                speed_str = f"{speed / 1024 / 1024:.1f}MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.1f}KB/s"
            else:
                speed_str = f"{speed:.0f}B/s"
            self._last_bytes = downloaded
            self._last_time = now
        pct = int(downloaded / total * 100) if total > 0 else 0
        self.progress.emit(min(pct, 100))
        self.progress_detail.emit(
            self._model_id, min(pct, 100), downloaded, total, speed_str
        )

    def run(self) -> None:
        try:
            _set_hf_mirror()
            from huggingface_hub import snapshot_download

            # 重新下载前先清空已有内容
            self._cleanup()
            os.makedirs(self._local_dir, exist_ok=True)

            # 重置全局状态
            with _progress_lock:
                HFProgressBar._cancelled = False
                HFProgressBar._tracker = self._tracker
                HFProgressBar._signal = self._emit_progress
            self._last_bytes = 0
            self._last_time = time.time()
            self._last_emit_time = 0.0

            snapshot_download(
                self._repo_id,
                local_dir=self._local_dir,
                tqdm_class=HFProgressBar,
            )
            self.finished.emit(self._model_id, True, "")
        except RuntimeError as e:
            if "下载已取消" in str(e):
                logger.info(f"模型下载已取消: {self._model_id}")
                self._cleanup()
                self.finished.emit(self._model_id, False, "已取消")
            else:
                logger.error(f"模型下载失败: {e}")
                self._cleanup()
                self.finished.emit(self._model_id, False, str(e))
        except Exception as e:
            logger.error(f"模型下载失败: {e}")
            self._cleanup()
            self.finished.emit(self._model_id, False, str(e))
        finally:
            # 防止 dangling signal reference
            with _progress_lock:
                HFProgressBar._tracker = None
                HFProgressBar._signal = None

    def cancel(self) -> None:
        """请求取消下载（协作式）"""
        self._cancelled = True
        with _progress_lock:
            HFProgressBar._cancelled = True


class DownloadManager(QObject):
    """模型下载管理器（后台下载、全局进度跟踪）"""
    progress = Signal(str, int, int, int, str)  # model_id, pct, downloaded, total, speed
    finished = Signal(str, bool, str)  # model_id, success, message
    download_started = Signal(str)  # model_id
    download_stopped = Signal()  # 下载结束或取消时触发

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: ModelDownloadWorker | None = None
        self._model_id: str | None = None
        self._cancelling = False
        self._last_progress: tuple | None = None  # (model_id, pct, downloaded, total, speed)

    def is_downloading(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def current_model_id(self) -> str | None:
        return self._model_id if self.is_downloading() else None

    def start_download(self, model_id: str) -> None:
        if self.is_downloading():
            logger.warning(f"已有下载任务进行中: {self._model_id}")
            return
        if model_id not in MODELS:
            raise ValueError(f"未知模型: {model_id}")

        self._model_id = model_id
        config = MODELS[model_id]
        self._worker = ModelDownloadWorker(
            model_id, config["repo_id"], config["local_dir"], config["size_bytes"], parent=self
        )
        self._worker.progress_detail.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        self.download_started.emit(model_id)
        logger.info(f"开始下载模型: {model_id}")

    def cancel_download(self) -> None:
        """请求取消下载：非阻塞，让 worker 协作式结束"""
        if self._worker and self._worker.isRunning():
            self._cancelling = True
            self._worker.cancel()
            # 不再 disconnect finished 信号，让 _on_finished 自然处理
            # 不再 wait/terminate，避免阻塞 UI 或导致崩溃

    def _on_progress(self, model_id, pct, downloaded, total, speed):
        self._last_progress = (model_id, pct, downloaded, total, speed)
        self.progress.emit(model_id, pct, downloaded, total, speed)

    def _on_finished(self, model_id, success, message):
        # 无论正常完成还是取消，都先通知 UI，再清理状态
        self.finished.emit(model_id, success, message)
        self._cleanup_after_cancel()

    def _cleanup_after_cancel(self) -> None:
        """统一清理：释放 worker 引用、重置状态、通知 UI"""
        self._worker = None
        self._model_id = None
        self._cancelling = False
        self.download_stopped.emit()


# 全局下载管理器实例
_download_manager: DownloadManager | None = None


def get_download_manager() -> DownloadManager:
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager()
    return _download_manager
