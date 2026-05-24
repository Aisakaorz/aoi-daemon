# -*- coding: utf-8 -*-
"""
语音转文字封装
基于 faster-whisper 本地推理 + sounddevice 录音
"""
import os
import tempfile
import wave
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from utils.logger import get_logger

logger = get_logger(__name__)

# 本地模型存放路径（相对项目根目录）
MODEL_LOCAL_DIR = os.path.abspath(os.path.join("resources", "whisper", "tiny"))


def is_model_available() -> bool:
    """检查本地 faster-whisper tiny 模型是否已下载"""
    return os.path.exists(os.path.join(MODEL_LOCAL_DIR, "model.bin"))


class AudioRecorder:
    """基于 sounddevice InputStream 的非阻塞录音器"""

    def __init__(self, samplerate: int = 16000):
        self.samplerate = samplerate
        self._chunks: list = []
        self._stream: Optional[sd.InputStream] = None

    def start(self) -> None:
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype=np.int16,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("录音开始")

    def _callback(self, indata, frames, time_info, status) -> None:
        self._chunks.append(indata.copy())

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

    def __init__(self, model_size: str = "tiny"):
        self._model_size = model_size
        self._model = None
        self._recorder = AudioRecorder()

    def _load_model(self) -> None:
        if self._model is None:
            from faster_whisper import WhisperModel
            if is_model_available():
                logger.info(f"从本地加载 faster-whisper 模型: {MODEL_LOCAL_DIR}")
                model_path = MODEL_LOCAL_DIR
            else:
                logger.info(f"加载 faster-whisper 模型（将自动下载）: {self._model_size}")
                model_path = self._model_size
            self._model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
            )

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

        tmp_path = os.path.join(tempfile.gettempdir(), "aoi_stt.wav")
        self._recorder.save_wav(data, tmp_path)

        self._load_model()
        worker = TranscribeRunnable(self, tmp_path)
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
