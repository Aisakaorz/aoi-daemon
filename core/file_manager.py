# -*- coding: utf-8 -*-
"""
用户上传文件管理器
- 文件暂存到项目 temp/uploads/ 目录
- 应用退出时自动清空
- 当前仅作临时暂存，预留后续基于上传文件扩展功能
"""
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
        return cls._instance

    # ---- 公开接口 ----

    def save_upload(self, src_path: str) -> Path:
        """
        保存上传文件到临时目录
        :param src_path: 用户选择的原始文件路径
        :return: 保存后的目标路径
        """
        filename = os.path.basename(src_path)
        # 目录可能已被 clear_all() 删除（如退出清理后再次使用），保存前确保存在
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        dst = self._upload_dir / filename

        shutil.copy2(src_path, dst)
        logger.info(f"文件已上传: {dst}")
        return dst

    def clear_all(self) -> None:
        """清空所有上传文件（应用退出时调用）"""
        if self._upload_dir.exists():
            shutil.rmtree(self._upload_dir, ignore_errors=True)
            logger.info("上传临时文件已清空")
