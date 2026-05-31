# -*- coding: utf-8 -*-
"""
应用主控制器（Application Controller）
协调 Live2D 模型、状态机、UI 窗口、AI 后端等各模块的初始化与生命周期
"""
import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from l2d.model_wrapper import Live2DModelWrapper
from core.state_machine import StateMachine
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from utils.logger import get_logger

logger = get_logger(__name__)


class AoiDaemonApp:
    """
    葵之使魔应用主类
    葵酱（Aoi）是基于 Live2D 免费模型 haru 的桌面看板娘。
    负责：
    1. QApplication 创建
    2. 平台相关初始化（macOS/Windows 高分屏等）
    3. 核心模块组装（ModelWrapper + StateMachine + MainWindow）
    4. 主事件循环启动
    """

    def __init__(self):
        self._app: QApplication = None
        self._model: Live2DModelWrapper = None
        self._state: StateMachine = None
        self._window: MainWindow = None

    def _setup_platform(self) -> None:
        """
        平台相关初始化
        - Windows: 设置 DPI 感知
        - macOS: 启用 Retina 高分屏支持
        """
        if sys.platform == "darwin":
            # macOS: 启用 Retina 支持
            os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
            logger.info("macOS 平台：启用 Retina 高分屏支持")
        elif sys.platform == "win32":
            # Windows: 高 DPI 缩放
            os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
            os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
            logger.info("Windows 平台：启用高 DPI 缩放")

    def run(self) -> int:
        """
        启动应用主循环
        :return: 进程退出码
        """
        try:
            # 1. 平台设置
            self._setup_platform()

            # 2. 创建 Qt 应用
            # 注意：QApplication 接受命令行参数
            self._app = QApplication(sys.argv)
            self._app.setApplicationName("葵之使魔")
            self._app.setApplicationDisplayName("AoiDaemon")

            # 显示启动画面（在模型加载完成前提供视觉反馈）
            splash = SplashScreen()
            splash.show()
            self._app.processEvents()

            # 3. 初始化核心模块
            self._model = Live2DModelWrapper()
            self._state = StateMachine()

            # 5. 创建主窗口（传入启动画面，模型加载完成后自动关闭）
            self._window = MainWindow(self._model, self._state, splash_screen=splash)
            self._window.show()

            logger.info("葵之使魔启动成功，进入主事件循环")
            return self._app.exec()

        except Exception as e:
            logger.exception(f"应用启动失败: {e}")
            return 1
