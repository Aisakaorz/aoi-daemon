# -*- coding: utf-8 -*-
"""
语音转文字封装
基于 faster-whisper 本地推理 + sounddevice 录音
"""
import atexit
import os
import tempfile
import wave
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from utils.logger import get_logger

logger = get_logger(__name__)

# 固定临时文件路径，每次覆盖，程序退出时统一清理
_STT_TMP_PATH = os.path.join(tempfile.gettempdir(), "aoi_stt.wav")


def _cleanup_stt_tmp() -> None:
    try:
        os.unlink(_STT_TMP_PATH)
    except OSError:
        pass


atexit.register(_cleanup_stt_tmp)


class AudioRecorder:
    """基于 sounddevice InputStream 的非阻塞录音器"""

    def __init__(self, samplerate: int = 16000):
        self.samplerate = samplerate
        self._chunks: list = []
        self._stream: Optional[sd.InputStream] = None
        self._volume = 0.0  # 0.0 ~ 1.0，实时音量

    def start(self) -> None:
        self._chunks = []
        self._volume = 0.0
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype=np.int16,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("录音开始")

    def get_volume(self) -> float:
        return self._volume

    def _callback(self, indata, frames, time_info, status) -> None:
        self._chunks.append(indata.copy())
        # 计算 RMS 音量并归一化到 0~1
        float_data = indata.astype(np.float64)
        rms = np.sqrt(np.mean(float_data ** 2))
        # 典型语音 rms 约 300~3000，放大低音量以提高可视性
        raw = min(rms / 2500.0, 1.0)
        # 平滑处理 + 录音期间保持最低可见高度
        self._volume = max(self._volume * 0.6 + raw * 0.4, 0.08)

    def stop(self) -> Optional[np.ndarray]:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._chunks:
            return None
        data = np.concatenate(self._chunks, axis=0)
        duration = len(data) / self.samplerate
        logger.info(f"录音结束，时长 {duration:.2f}s")
        return data

    def save_wav(self, data: np.ndarray, path: str) -> None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(data.tobytes())


class TranscribeSignals(QObject):
    finished = Signal(str)


class TranscribeRunnable(QRunnable):
    """后台转录任务"""

    def __init__(self, stt_provider, audio_path: str):
        super().__init__()
        self._stt = stt_provider
        self._path = audio_path
        self.signals = TranscribeSignals()

    def run(self) -> None:
        try:
            text = self._stt.transcribe(self._path)
            self.signals.finished.emit(text)
        except Exception as e:
            logger.error(f"转录失败: {e}")
            self.signals.finished.emit("")


class STTProvider:
    """faster-whisper 封装，延迟加载模型"""

    def __init__(self, model_size: str | None = None):
        # model_size 参数保留兼容，实际从 model_manager 获取当前模型
        self._model_size = model_size
        self._model = None
        self._recorder = AudioRecorder()

    def _load_model(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        from voice.model_manager import get_current_model_id, get_model_local_dir, is_model_downloaded

        model_id = get_current_model_id()
        if not is_model_downloaded(model_id):
            raise RuntimeError(f"模型 {model_id} 未下载")
        local_dir = get_model_local_dir(model_id)
        logger.info(f"从本地加载 faster-whisper 模型: {local_dir}")
        self._model = WhisperModel(
            local_dir,
            device="cpu",
            compute_type="int8",
        )

    def get_volume(self) -> float:
        """获取当前录音音量（0.0 ~ 1.0）"""
        return self._recorder.get_volume()

    def start_recording(self) -> None:
        # 如果之前有未停止的录音，先清理（防止重复 start 导致资源泄漏）
        if self._recorder._stream is not None:
            self._recorder.stop()
        self._recorder.start()

    def stop_recording_and_transcribe(self, on_finished: Callable[[str], None]) -> None:
        data = self._recorder.stop()
        if data is None or len(data) == 0:
            on_finished("")
            return

        self._recorder.save_wav(data, _STT_TMP_PATH)

        self._load_model()
        worker = TranscribeRunnable(self, _STT_TMP_PATH)
        worker.signals.finished.connect(on_finished)
        QThreadPool.globalInstance().start(worker)

    def transcribe(self, audio_path: str) -> str:
        self._load_model()
        segments, info = self._model.transcribe(
            audio_path,
            language="zh",
            beam_size=5,
        )
        text = "".join([segment.text for segment in segments])
        logger.info(f"转录结果: {text[:50]}...")
        return text.strip()
