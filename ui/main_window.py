# -*- coding: utf-8 -*-
"""
主窗口：透明无边框置顶窗口
负责窗口属性设置（Tool + Frameless + Translucent + Topmost）、
承载 Live2DCanvas 与 ChatPanel，并协调两者布局
"""
import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QPoint, QByteArray, QTimer
from PySide6.QtGui import QMouseEvent

from ui.live2d_canvas import Live2DCanvas
from ui.chat_panel import ChatPanel
from ui.tray_icon import TrayIcon
from l2d.model_wrapper import Live2DModelWrapper
from core.state_machine import StateMachine, CharacterState
from utils.logger import get_logger

logger = get_logger(__name__)

# 默认窗口尺寸
_DEFAULT_WIDTH = 400
_DEFAULT_HEIGHT = 600

# Windows API 常量
WS_EX_TRANSPARENT = 0x00000020
GWL_EXSTYLE = -20
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOOWNERZORDER = 0x0200
SWP_NOACTIVATE = 0x0010
SWP_FLAGS = SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_NOACTIVATE


class MainWindow(QMainWindow):
    """
    葵之使魔主窗口
    - 透明无边框置顶
    - 支持鼠标拖拽移动（到屏幕任意位置）
    - 集成 Live2D 渲染与聊天面板
    - 右键菜单（带置顶勾选状态）
    - Windows 透明区域鼠标穿透（定时器 + SetWindowLong）
    """

    def __init__(
        self,
        model_wrapper: Live2DModelWrapper,
        state_machine: StateMachine,
        parent=None
    ):
        super().__init__(parent)
        self._model = model_wrapper
        self._state = state_machine

        self._setup_window()
        self._setup_central_widget()
        self._setup_tray()
        self._setup_context_menu()
        self._setup_passthrough_timer()

        # 窗口初始位置：屏幕右下角
        self._move_to_default_position()

        logger.info("MainWindow 初始化完成")

    # ---- 窗口属性 ----

    def _setup_window(self) -> None:
        """配置窗口属性：无边框、透明、置顶、工具窗口"""
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # 允许鼠标事件穿透但又能接收交互：关键属性组合
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_MouseTracking, True)

        self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
        self.setMinimumSize(200, 300)
        self.setMaximumSize(600, 900)

    def _setup_central_widget(self) -> None:
        """构建中央部件：Live2D 画布 + 聊天面板叠加"""
        central = QWidget(self)
        central.setMouseTracking(True)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Live2D OpenGL 画布（占满整个窗口）
        self._canvas = Live2DCanvas(self._model, self._state, central)
        layout.addWidget(self._canvas, stretch=1)

        # 聊天面板（浮动叠加在画布上方，底部居中）
        self._chat = ChatPanel(central)
        self._chat.message_sent.connect(self._on_user_message)
        self._chat.geometry_changed.connect(self._move_chat_to_bottom)
        # 窗口 resize 时重新调整聊天面板位置
        self.resizeEvent = self._on_resize

    def _setup_tray(self) -> None:
        """初始化系统托盘"""
        self._tray = TrayIcon(self)
        self._tray.show_window.connect(self.show)
        self._tray.hide_window.connect(self.hide)
        self._tray.toggle_chat.connect(self._toggle_chat_panel)
        self._tray.about_app.connect(self._show_about)
        self._tray.quit_app.connect(self._on_quit)
        self._tray.show()

    def _setup_context_menu(self) -> None:
        """
        右键菜单（通过 Qt 实现）
        在 MainWindow 上右键时弹出
        """
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        self._context_menu = QMenu(self)

        action_chat = QAction("显示/隐藏聊天面板", self)
        action_chat.triggered.connect(self._toggle_chat_panel)
        self._context_menu.addAction(action_chat)

        self._action_top = QAction("窗口置顶", self)
        self._action_top.setCheckable(True)
        self._action_top.setChecked(True)  # 默认置顶
        self._action_top.triggered.connect(self._toggle_topmost)
        self._context_menu.addAction(self._action_top)

        self._context_menu.addSeparator()

        action_about = QAction("关于", self)
        action_about.triggered.connect(self._show_about)
        self._context_menu.addAction(action_about)

        action_quit = QAction("退出", self)
        action_quit.triggered.connect(self._on_quit)
        self._context_menu.addAction(action_quit)

    def _setup_passthrough_timer(self) -> None:
        """
        设置定时器实现透明区域鼠标穿透（Windows）
        每 30ms 检测一次鼠标位置，响应更快，避免上下区域穿透延迟
        """
        if sys.platform != "win32":
            return
        self._passthrough_timer = QTimer(self)
        self._passthrough_timer.timeout.connect(self._update_passthrough)
        self._passthrough_timer.start(30)

    def _update_passthrough(self) -> None:
        """更新窗口穿透状态"""
        try:
            hwnd = int(self.winId())
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            has_transparent = bool(ex_style & WS_EX_TRANSPARENT)

            # 拖拽期间始终保持窗口可交互，避免中途"掉落"
            if hasattr(self, '_canvas') and self._canvas._dragging:
                if has_transparent:
                    ctypes.windll.user32.SetWindowLongW(
                        hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT
                    )
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
                return

            # 聊天面板打开时：整个窗口可交互，不禁用鼠标事件
            if hasattr(self, '_chat') and self._chat.isVisible():
                if has_transparent:
                    ctypes.windll.user32.SetWindowLongW(
                        hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT
                    )
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
                return

            # 获取鼠标屏幕坐标
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            # 获取窗口矩形
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            # 检查鼠标是否在窗口内
            in_window = rect.left <= pt.x <= rect.right and rect.top <= pt.y <= rect.bottom

            if in_window:
                # 鼠标在窗口内：根据是否在模型上切换穿透
                if hasattr(self, '_canvas') and not self._canvas._mouse_over_model:
                    # 透明区域：添加 WS_EX_TRANSPARENT（如果还没有）
                    if not has_transparent:
                        ctypes.windll.user32.SetWindowLongW(
                            hwnd, GWL_EXSTYLE, ex_style | WS_EX_TRANSPARENT
                        )
                        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
                else:
                    # 模型区域：移除 WS_EX_TRANSPARENT（如果已经有）
                    if has_transparent:
                        ctypes.windll.user32.SetWindowLongW(
                            hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT
                        )
                        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
            else:
                # 鼠标不在窗口内：移除穿透样式（避免影响其他操作）
                if has_transparent:
                    ctypes.windll.user32.SetWindowLongW(
                        hwnd, GWL_EXSTYLE, ex_style & ~WS_EX_TRANSPARENT
                    )
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        except Exception as e:
            logger.debug(f"穿透更新异常: {e}")

    def _move_to_default_position(self) -> None:
        """将窗口移动到屏幕右下角"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - _DEFAULT_WIDTH - 20
        y = screen.bottom() - _DEFAULT_HEIGHT - 20
        self.move(x, y)

    def _move_chat_to_bottom(self) -> None:
        """将聊天面板移动到父窗口（central widget）底部居中"""
        if hasattr(self, '_chat'):
            chat = self._chat
            parent = chat.parentWidget()
            if parent:
                chat_width = getattr(chat, '_base_width', 280)
                cx = (parent.width() - chat_width) // 2
                cy = parent.height() - chat.height() - 10
                chat.move(cx, max(cy, 0))
                chat.raise_()

    def _on_resize(self, event) -> None:
        """窗口大小变化时，重新调整聊天面板位置"""
        super().resizeEvent(event)
        self._move_chat_to_bottom()

    # ---- 事件重写 ----

    def showEvent(self, event) -> None:
        """窗口首次显示时延迟重新定位聊天面板（确保 Qt 尺寸计算已就绪）"""
        super().showEvent(event)
        QTimer.singleShot(50, self._move_chat_to_bottom)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        鼠标按下：记录拖拽起始位置
        注意：实际拖拽逻辑主要在 Live2DCanvas 中处理，这里作为后备
        """
        if event.button() == Qt.MouseButton.RightButton:
            self._context_menu.popup(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        """右键菜单事件"""
        self._context_menu.popup(event.globalPos())

    # ---- 槽函数 ----

    def _toggle_chat_panel(self) -> None:
        """
        切换聊天面板显示/隐藏
        同时保存并恢复窗口位置，避免位置被重置
        """
        pos = self.pos()
        self._chat.toggle_visibility()
        self.move(pos)
        if self._chat.isVisible():
            self._move_chat_to_bottom()
            self._chat._input.setFocus()

    def _on_user_message(self, text: str) -> None:
        """
        用户发送消息后的处理
        Phase 1 测试模式：显示输入指示器，延迟 2 秒后回复
        """
        logger.info(f"用户消息: {text}")
        # 进入 Thinking 状态
        self._state.force_transit(CharacterState.THINKING)
        # 显示正在输入指示器
        self._chat.show_typing_indicator()
        # 延迟 2 秒后回复（模拟网络/API 延迟）
        QTimer.singleShot(2000, lambda: self._do_reply(text))

    def _do_reply(self, text: str) -> None:
        """执行 AI 回复（Phase 1 测试：直接 echo 用户消息）"""
        self._chat.hide_typing_indicator()
        self._chat.add_message(text, is_user=False)
        self._state.return_to_idle()

    def _toggle_topmost(self) -> None:
        """切换置顶状态"""
        flags = self.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            self._action_top.setChecked(False)
            logger.info("置顶已关闭")
        else:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
            self._action_top.setChecked(True)
            logger.info("置顶已开启")
        self.show()

    def _show_about(self) -> None:
        """显示关于信息（自定义弹窗，无提示图标，应用图标，内容绝对居中）"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame
        from PySide6.QtGui import QIcon, QFont

        dialog = QDialog(self)
        dialog.setWindowTitle("关于 葵之使魔")
        dialog.setFixedSize(260, 110)
        dialog.setStyleSheet("QDialog { background-color: #FAFAFA; }")

        # 设置应用图标
        icon_path = "resources/icons/app_icon.ico"
        if os.path.exists(icon_path):
            dialog.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("葵之使魔 ~AoiDaemon~")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #333333;")

        # 装饰分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #E0E0E0;")
        line.setFixedHeight(2)

        desc = QLabel("桌面级 Live2D AI 伴侣应用\n💻Powered by Aoi🌻 and Kimi🤖")
        desc.setFont(QFont("Microsoft YaHei", 9))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #888888;")

        layout.addWidget(title)
        layout.addWidget(line)
        layout.addWidget(desc)
        layout.addStretch()

        dialog.exec()

    def _on_quit(self) -> None:
        """退出应用"""
        logger.info("用户请求退出")
        self._tray.hide()
        QApplication.instance().quit()
