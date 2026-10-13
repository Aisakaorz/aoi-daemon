# -*- coding: utf-8 -*-
"""
启动引导（轻量模块，无任何重型依赖）
必须在创建 QApplication 之前调用：
- 平台相关环境变量（高分屏缩放）
- 默认 OpenGL 表面格式（4x MSAA + Alpha8）

独立成小模块的原因：main.py 要在导入重型依赖链（live2d/语音等）之前
就显示启动画面，因此平台/GL 准备工作不能依赖 core.app
"""
import os
import sys

from PySide6.QtGui import QSurfaceFormat

from utils.logger import get_logger

logger = get_logger(__name__)

# 应用版本号（关于对话框显示，随版本更新）
APP_VERSION = "0.1.21"


def setup_platform_env() -> None:
    """平台相关初始化（Qt5 风格环境变量，Qt6 下多为兼容保留）"""
    if sys.platform == "darwin":
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        logger.info("macOS 平台：启用 Retina 高分屏支持")
    elif sys.platform == "win32":
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        logger.info("Windows 平台：启用高 DPI 缩放")


def setup_surface_format() -> None:
    """设置默认 OpenGL 表面格式（4x MSAA + Alpha8），须在 QApplication 创建前调用"""
    fmt = QSurfaceFormat()
    fmt.setSamples(4)
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)
    logger.info("OpenGL 表面格式已设置：4x MSAA + Alpha8")
