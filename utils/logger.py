# -*- coding: utf-8 -*-
"""
日志工具：统一应用日志格式与级别
"""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    获取统一配置的日志记录器
    :param name: 模块名
    :return: 配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 Handler
    if not logger.handlers:
        # 尝试使用 utf-8 编码输出，解决 Windows 控制台中文乱码
        try:
            handler = logging.StreamHandler(sys.stdout)
            # 强制设置编码为 utf-8（Python 3.7+）
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            handler = logging.StreamHandler(sys.stdout)

        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
