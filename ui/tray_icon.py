# -*- coding: utf-8 -*-
"""
系统托盘图标与右键菜单
提供最小化到托盘、显示/隐藏窗口、退出等功能
"""
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QWidget, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal, QObject

from utils.logger import get_logger

logger = get_logger(__name__)


class TrayIcon(QObject):
    """
    系统托盘封装
    信号：
        - show_window: 请求显示主窗口
        - hide_window: 请求隐藏主窗口
        - toggle_chat: 请求切换聊天面板显示状态
        - quit_app: 请求退出应用
    """

    show_window = Signal()
    hide_window = Signal()
    toggle_chat = Signal()
    about_app = Signal()
    quit_app = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent = parent
        self._tray = QSystemTrayIcon(parent)
        self._tray.setToolTip("葵之使魔 ~AoiDaemon~")

        # 尝试加载图标，如果没有则使用系统默认
        self._setup_icon()
        self._setup_menu()

        # 左键单击切换显示/隐藏
        self._tray.activated.connect(self._on_activated)

    def _setup_icon(self) -> None:
        """设置托盘图标，优先使用 resources/icons/tray_icon.png"""
        icon_paths = [
            "resources/icons/tray_icon.png",
            "resources/icons/tray.ico",
            "resources/icons/app_icon.ico",
        ]
        for path in icon_paths:
            if __import__('os').path.exists(path):
                self._tray.setIcon(QIcon(path))
                logger.info(f"托盘图标加载成功: {path}")
                return
        # 使用系统默认图标
        self._tray.setIcon(QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_ComputerIcon
        ))
        logger.warning("未找到自定义托盘图标，使用系统默认图标")

    def _setup_menu(self) -> None:
        """构建右键菜单"""
        menu = QMenu(self._parent)

        action_show = QAction("显示窗口", self._parent)
        action_show.triggered.connect(self.show_window.emit)
        menu.addAction(action_show)

        action_hide = QAction("隐藏窗口", self._parent)
        action_hide.triggered.connect(self.hide_window.emit)
        menu.addAction(action_hide)

        menu.addSeparator()

        action_chat = QAction("显示/隐藏聊天面板", self._parent)
        action_chat.triggered.connect(self.toggle_chat.emit)
        menu.addAction(action_chat)

        menu.addSeparator()

        action_about = QAction("关于", self._parent)
        action_about.triggered.connect(self.about_app.emit)
        menu.addAction(action_about)

        menu.addSeparator()

        action_quit = QAction("退出", self._parent)
        action_quit.triggered.connect(self.quit_app.emit)
        menu.addAction(action_quit)

        self._tray.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """
        托盘图标被激活时的回调
        :param reason: 激活原因
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 左键单击：切换显示/隐藏
            if self._parent.isVisible():
                self.hide_window.emit()
            else:
                self.show_window.emit()

    def show(self) -> None:
        """显示托盘图标"""
        self._tray.show()
        logger.info("系统托盘图标已显示")

    def hide(self) -> None:
        """隐藏托盘图标"""
        self._tray.hide()
