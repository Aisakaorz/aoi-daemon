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

    def _check_core_lib(self) -> bool:
        """
        检查 Live2D Core 动态库是否存在
        :return: 是否存在
        """
        if sys.platform == "darwin":
            lib_path = "lib/libCore.dylib"
        elif sys.platform == "win32":
            lib_path = "lib/Core.dll"
        else:
            logger.warning(f"未知平台 {sys.platform}，尝试使用默认库路径")
            lib_path = "lib/Core.dll"

        if not os.path.exists(lib_path):
            logger.error(
                f"Live2D Core 库未找到: {os.path.abspath(lib_path)}\n"
                f"请从 Live2D 官网下载 Cubism SDK for Native，"
                f"放置对应平台的 Core 动态库到 lib/ 目录。"
            )
            return False
        logger.info(f"Live2D Core 库已找到: {lib_path}")
        return True

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

            # 3. 检查 Core 库
            if not self._check_core_lib():
                # 库缺失时仍继续运行，但模型无法加载，窗口会显示占位
                logger.warning("Core 库缺失，将以降级模式运行（无 Live2D 模型）")

            # 4. 初始化核心模块
            self._model = Live2DModelWrapper()
            self._state = StateMachine()

            # 5. 创建主窗口
            self._window = MainWindow(self._model, self._state)
            self._window.show()

            logger.info("葵之使魔启动成功，进入主事件循环")
            return self._app.exec()

        except Exception as e:
            logger.exception(f"应用启动失败: {e}")
            return 1
