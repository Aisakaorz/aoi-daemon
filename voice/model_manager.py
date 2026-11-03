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
from utils.paths import app_root

logger = get_logger(__name__)

MODELS: dict[str, dict] = {
    "tiny": {
        "name": "Whisper Tiny",
        "size_str": "~75MB",
        "repo_id": "guillaumekln/faster-whisper-tiny",
        # ModelScope 国内镜像（主下载源，CDN 快且稳）；目录为合集仓库内的模型子目录
        "ms_repo": "XXXXRT/faster-whisper",
        "ms_path": "faster-whisper-tiny",
        "local_dir": os.path.join(app_root("resources"), "whisper", "tiny"),
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
    # 网络超时放宽，避免慢网反复重试
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")
    # 注：hf_transfer 已被新版 huggingface_hub 弃用（改推 Xet，国内镜像不支持），
    # 故不再启用；下载速度主要取决于镜像带宽（实测 ~1.3MB/s，75MB 约 1 分钟）。
    # 如需提速可调研 ModelScope 镜像源（未来版本）


def delete_model(model_id: str) -> bool:
    """删除已下载的语音模型文件（不可恢复）；删除当前使用中的模型时同时重置选中态"""
    local_dir = get_model_local_dir(model_id)
    if not local_dir or not os.path.isdir(local_dir):
        return False
    try:
        shutil.rmtree(local_dir)
        logger.info(f"语音模型已删除: {model_id}")
    except Exception as e:
        logger.warning(f"删除语音模型失败: {e}")
        return False
    if get_current_model_id() == model_id:
        set_current_model_id(None)
    return True


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
        self._last_speed_str = ""

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
        # 速度估计每 ≥0.5s 刷新一次，但每次都随信号发出（避免 UI 上速度时有时无地闪烁）
        if dt > 0.5 and delta > 0:
            speed = delta / dt
            if speed > 1024 * 1024:
                self._last_speed_str = f"{speed / 1024 / 1024:.1f}MB/s"
            elif speed > 1024:
                self._last_speed_str = f"{speed / 1024:.1f}KB/s"
            else:
                self._last_speed_str = f"{speed:.0f}B/s"
            self._last_bytes = downloaded
            self._last_time = now
        pct = int(downloaded / total * 100) if total > 0 else 0
        self.progress.emit(min(pct, 100))
        self.progress_detail.emit(
            self._model_id, min(pct, 100), downloaded, total, self._last_speed_str
        )

    def run(self) -> None:
        try:
            _set_hf_mirror()
            # 优先 ModelScope 国内 CDN（真实进度/速度、单文件流式），失败回退 hf-mirror
            if not self._download_from_modelscope():
                self._download_from_hf_mirror()
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

    def _download_from_modelscope(self) -> bool:
        """从 ModelScope（国内 CDN）按文件直链流式下载：逐块真实进度与速度、可协作取消。
        仓库缺文件或网络异常时返回 False，由调用方回退 hf-mirror。"""
        import requests

        ms_repo = MODELS[self._model_id].get("ms_repo")
        ms_path = MODELS[self._model_id].get("ms_path")
        if not ms_repo or not ms_path:
            return False
        try:
            api = f"https://modelscope.cn/api/v1/models/{ms_repo}/repo/files?Recursive=true"
            resp = requests.get(api, timeout=15)
            resp.raise_for_status()
            entries = resp.json().get("Data", {}).get("Files", [])
            wanted = {
                f["Path"]: f["Size"]
                for f in entries
                if f["Path"].startswith(ms_path + "/")
                and os.path.basename(f["Path"]) in _REQUIRED_FILES
            }
            if len(wanted) < len(_REQUIRED_FILES):
                logger.warning(f"ModelScope 仓库缺少必要文件: {ms_repo}/{ms_path}")
                return False

            total = sum(wanted.values())
            with _progress_lock:
                HFProgressBar._cancelled = False
            # 用接口返回的真实总大小重建进度跟踪器
            self._tracker = _GlobalDownloadTracker(total)
            with _progress_lock:
                HFProgressBar._tracker = self._tracker
                HFProgressBar._signal = self._emit_progress
            self._last_bytes = 0
            self._last_time = time.time()
            self._last_emit_time = 0.0
            self._last_speed_str = ""

            self._cleanup()
            os.makedirs(self._local_dir, exist_ok=True)
            logger.info(f"从 ModelScope 下载 {ms_repo}/{ms_path}（共 {total / 1024 / 1024:.0f}MB）")

            for rel_path in wanted:
                fname = os.path.basename(rel_path)
                url = f"https://modelscope.cn/models/{ms_repo}/resolve/master/{rel_path}"
                with requests.get(url, stream=True, timeout=(10, 60)) as r:
                    r.raise_for_status()
                    with open(os.path.join(self._local_dir, fname), "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 512):
                            if not chunk:
                                continue
                            with _progress_lock:
                                cancelled = HFProgressBar._cancelled
                            if cancelled:
                                raise RuntimeError("下载已取消")
                            f.write(chunk)
                            self._tracker.add_bytes(len(chunk))
                            self._emit_progress()
            logger.info("ModelScope 下载完成")
            return True
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(f"ModelScope 下载不可用，回退 hf-mirror: {e}")
            return False

    def _download_from_hf_mirror(self) -> None:
        """回退方案：hf-mirror + huggingface_hub snapshot_download"""
        from huggingface_hub import snapshot_download

        self._cleanup()
        os.makedirs(self._local_dir, exist_ok=True)

        with _progress_lock:
            HFProgressBar._cancelled = False
            HFProgressBar._tracker = self._tracker
            HFProgressBar._signal = self._emit_progress
        self._last_bytes = 0
        self._last_time = time.time()
        self._last_emit_time = 0.0
        self._last_speed_str = ""

        snapshot_download(
            self._repo_id,
            local_dir=self._local_dir,
            tqdm_class=HFProgressBar,
            max_workers=4,
        )

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

    def shutdown(self, timeout_ms: int = 3000) -> None:
        """退出前调用：协作式取消并等待下载线程结束，防止进程退出时线程仍在运行"""
        worker = self._worker
        if worker is not None and worker.isRunning():
            logger.info("退出前等待下载线程结束...")
            self._cancelling = True
            worker.cancel()
            if not worker.wait(timeout_ms):
                logger.warning(f"下载线程未在 {timeout_ms}ms 内结束，继续退出")

    def _on_progress(self, model_id, pct, downloaded, total, speed):
        self._last_progress = (model_id, pct, downloaded, total, speed)
        self.progress.emit(model_id, pct, downloaded, total, speed)

    def _on_finished(self, model_id, success, message):
        # 无论正常完成还是取消，都先清理自身状态、再通知 UI，
        # 防止 UI 槽收到 finished 后立即 start_download，新 worker 被后续清理置空
        self._cleanup_after_cancel()
        self.finished.emit(model_id, success, message)

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
