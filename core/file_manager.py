# -*- coding: utf-8 -*-
"""
用户上传文件管理器
- 文件暂存到系统临时目录下的 aoi_uploads/
- 应用退出时自动清空
- 支持 taiko_scores_*.json 成绩文件的上传与替换
"""
import json
import os
import shutil
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)

_UPLOAD_DIR = Path(__file__).parent.parent / "temp" / "uploads"


class FileManager:
    """
    管理用户上传的临时文件
    - 单例模式，整个应用共享同一个 FileManager 实例
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._upload_dir = _UPLOAD_DIR
            cls._instance._upload_dir.mkdir(parents=True, exist_ok=True)
            cls._instance._current_taiko_file: Path | None = None
            cls._instance._scan_existing_taiko()
        return cls._instance

    def _scan_existing_taiko(self) -> None:
        """启动时扫描是否已有 taiko_scores 文件"""
        files = list(self._upload_dir.glob("taiko_scores_*.json"))
        if files:
            self._current_taiko_file = files[0]
            logger.info(f"启动时发现已有成绩文件: {self._current_taiko_file.name}")

    # ---- 公开接口 ----

    def save_upload(self, src_path: str) -> Path:
        """
        保存上传文件到临时目录
        :param src_path: 用户选择的原始文件路径
        :return: 保存后的目标路径
        """
        filename = os.path.basename(src_path)
        dst = self._upload_dir / filename

        # 如果是 taiko_scores 文件，先清除旧的
        if filename.startswith("taiko_scores_"):
            self._clear_taiko_files()
            self._current_taiko_file = dst

        shutil.copy2(src_path, dst)
        logger.info(f"文件已上传: {dst}")
        return dst

    def get_current_taiko_data(self) -> list[dict] | None:
        """读取当前太鼓成绩 JSON 数据"""
        if self._current_taiko_file is None or not self._current_taiko_file.exists():
            return None
        try:
            with open(self._current_taiko_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取成绩文件失败: {e}")
            return None

    @property
    def has_taiko_file(self) -> bool:
        return self._current_taiko_file is not None and self._current_taiko_file.exists()

    @property
    def current_filename(self) -> str | None:
        if self._current_taiko_file:
            return self._current_taiko_file.name
        return None

    def clear_all(self) -> None:
        """清空所有上传文件（应用退出时调用）"""
        if self._upload_dir.exists():
            shutil.rmtree(self._upload_dir, ignore_errors=True)
            self._current_taiko_file = None
            logger.info("上传临时文件已清空")

    # ---- 内部 ----

    def _clear_taiko_files(self) -> None:
        """清除旧的 taiko_scores 文件"""
        for f in self._upload_dir.glob("taiko_scores_*.json"):
            try:
                f.unlink()
                logger.debug(f"删除旧成绩文件: {f.name}")
            except OSError:
                pass
