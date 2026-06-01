# -*- coding: utf-8 -*-
"""
日志工具：统一应用日志格式、级别与输出目标
- 控制台输出级别由环境变量 AOI_LOG_LEVEL 控制（默认 INFO）
- 运行时可通过 set_level() 切换
- ERROR 级别日志自动写入 logs/aoi-error.log
"""
import logging
import os
import sys

# 日志级别映射
_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

# 从环境变量读取默认级别，未设置则使用 INFO
_DEFAULT_LEVEL_NAME = os.environ.get("AOI_LOG_LEVEL", "INFO").upper()
_current_level = _LEVEL_MAP.get(_DEFAULT_LEVEL_NAME, logging.INFO)

# ERROR 文件 Handler（全局共享，懒加载）
_error_file_handler = None


def _get_error_file_handler() -> logging.FileHandler:
    """获取 ERROR 级别的文件 Handler，首次调用时创建"""
    global _error_file_handler
    if _error_file_handler is None:
        os.makedirs("logs", exist_ok=True)
        _error_file_handler = logging.FileHandler(
            "logs/aoi-error.log", encoding="utf-8", mode="a"
        )
        _error_file_handler.setLevel(logging.WARNING)
        _error_file_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    return _error_file_handler


def get_logger(name: str) -> logging.Logger:
    """
    获取统一配置的日志记录器
    :param name: 模块名
    :return: 配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    # logger 本身记录所有级别，由 Handler 控制实际输出
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # 控制台 Handler（跟随全局级别）
        try:
            stream_handler = logging.StreamHandler(sys.stdout)
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            stream_handler = logging.StreamHandler(sys.stdout)

        stream_handler.setLevel(_current_level)
        stream_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(stream_handler)

        # ERROR 文件 Handler（固定 ERROR 级别）
        logger.addHandler(_get_error_file_handler())

    return logger


def set_level(level_name: str) -> None:
    """
    运行时切换所有控制台 Handler 的日志级别，并持久化到 config.json
    :param level_name: DEBUG / INFO / WARNING / ERROR
    """
    global _current_level
    level = _LEVEL_MAP.get(level_name.upper())
    if level is None:
        return

    _current_level = level

    # 遍历所有已创建的 logger，更新 StreamHandler 级别
    for logger_name in list(logging.root.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            # 只修改控制台 StreamHandler，不修改文件 Handler
            if type(handler) is logging.StreamHandler:
                handler.setLevel(level)

    # 根 logger
    for handler in logging.root.handlers:
        if type(handler) is logging.StreamHandler:
            handler.setLevel(level)

    # 持久化到 config.json
    try:
        from utils import config_manager as cfg
        cfg.set("log_level", level_name.upper())
    except Exception:
        pass

    logging.getLogger(__name__).info(f"Log level changed to {level_name.upper()}")


def get_current_level_name() -> str:
    """返回当前控制台日志级别的名称"""
    for name, level in _LEVEL_MAP.items():
        if level == _current_level:
            return name
    return "INFO"
