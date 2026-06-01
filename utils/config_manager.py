# -*- coding: utf-8 -*-
"""
配置持久化管理器
简单的 JSON 文件读写，支持自动保存
配置文件路径：项目根目录下的 config.json（已加入 .gitignore）
"""
import json
import os

from utils.logger import get_logger

logger = get_logger(__name__)

# 配置文件放在项目根目录，与 main.py 同级
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config.json",
)

_data: dict = {}


def load() -> None:
    """从磁盘加载配置，文件不存在时静默初始化为空"""
    global _data
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                _data = json.load(f)
            logger.info(f"配置已加载: {_CONFIG_PATH}")
        except Exception as e:
            logger.warning(f"配置加载失败: {e}")
            _data = {}
    else:
        _data = {}


def save() -> None:
    """立即写入磁盘"""
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"配置保存失败: {e}")


def get(key: str, default=None):
    """读取配置项，不存在时返回 default"""
    return _data.get(key, default)


def set(key: str, value) -> None:
    """写入配置项并自动保存到磁盘"""
    _data[key] = value
    save()
