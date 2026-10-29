# -*- coding: utf-8 -*-
"""
应用主控制器（Application Controller）
协调 Live2D 模型、状态机、UI 窗口等各模块的初始化与生命周期

说明：QApplication 与启动画面由 main.py 在导入重型依赖链之前创建并传入
（尽早显示加载界面，避免黑屏）；平台环境与 OpenGL 表面格式由 core.bootstrap
在 QApplication 创建前设置
"""
from PySide6.QtWidgets import QApplication

from l2d.model_wrapper import Live2DModelWrapper
from core.state_machine import StateMachine
from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from utils.logger import get_logger

logger = get_logger(__name__)


class AoiDaemonApp:
    """
    葵之使魔应用主类
    负责核心模块组装（ModelWrapper + StateMachine + MainWindow）与主事件循环
    """

    def __init__(self, app: QApplication, splash=None):
        """
        :param app: QApplication 实例（由 main.py 创建）
        :param splash: 启动画面（SplashScreen 或子进程代理，均需实现 request_close；
                       None 表示无启动画面）
        """
        self._app = app
        self._splash = splash
        self._model: Live2DModelWrapper = None
        self._state: StateMachine = None
        self._window: MainWindow = None

    def run(self) -> int:
        """
        启动应用主循环
        :return: 进程退出码
        """
        try:
            # 1. 初始化核心模块
            self._model = Live2DModelWrapper()
            self._state = StateMachine()

            # 2. 启动画面子进程如果在启动阶段就崩了（PySide6 导入失败、
            #    环境变量污染等），主进程此前无从得知——表现为"完全没有启动画面"。
            #    这里补上检测并回退到进程内启动画面，至少让加载过程可见。
            self._ensure_splash_alive()

            # 3. 创建主窗口（传入启动画面，模型加载完成后自动关闭）
            self._window = MainWindow(self._model, self._state, splash_screen=self._splash)
            self._window.show()

            logger.info("葵之使魔启动成功，进入主事件循环")
            return self._app.exec()

        except Exception as e:
            logger.exception(f"应用启动失败: {e}")
            return 1

    def _ensure_splash_alive(self) -> None:
        """启动画面子进程已退出时，回退为进程内启动画面（并留下可查的告警）"""
        if self._splash is None:
            return
        died = getattr(self._splash, "exited", None)
        if not callable(died) or not died():
            return

        logger.warning(
            "启动画面子进程已提前退出，回退进程内启动画面（详情见 logs/splash_child.log）"
        )
        try:
            fallback = SplashScreen()
            fallback.show()
            self._app.processEvents()
            self._splash = fallback
        except Exception as e:
            logger.warning(f"进程内启动画面创建失败，跳过: {e}")
            self._splash = None
