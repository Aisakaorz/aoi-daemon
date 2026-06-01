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

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QSystemTrayIcon
from PySide6.QtCore import Qt, QPoint, QByteArray, QTimer
from PySide6.QtGui import QMouseEvent

from utils import config_manager as cfg
from utils.logger import set_level, get_current_level_name

from ui.live2d_canvas import Live2DCanvas
from ui.chat_panel import ChatPanel
from ui.tray_icon import TrayIcon
from l2d.model_wrapper import Live2DModelWrapper
from core.state_machine import StateMachine, CharacterState
from core.file_manager import FileManager
from ai.command_router import CommandRouter
from utils.logger import get_logger

logger = get_logger(__name__)

# 默认窗口尺寸
_DEFAULT_WIDTH = 400
_DEFAULT_HEIGHT = 600

# 角色底部占窗口高度的比例（从顶部算起），用于限制聊天面板位置
# 经实际视觉微调：haru 模型脚部约在 95.5% 高度处
_CHARACTER_BOTTOM_RATIO = 0.955

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
        splash_screen=None,
        parent=None
    ):
        super().__init__(parent)
        self._model = model_wrapper
        self._state = state_machine
        self._splash = splash_screen

        self._setup_window()
        self._setup_central_widget()
        self._setup_tray()
        self._build_shared_menu()
        self._setup_passthrough_timer()
        self._setup_download_tracking()

        # 窗口初始位置：屏幕右下角
        # 当前角色缩放比例（1.0 = 默认 400×600）
        self._current_scale = 1.0

        # 窗口位置/尺寸防抖保存定时器
        self._save_geometry_timer = QTimer(self)
        self._save_geometry_timer.setSingleShot(True)
        self._save_geometry_timer.timeout.connect(self._save_window_geometry)

        # 文件管理与指令路由
        self._file_mgr = FileManager()
        self._cmd_router = CommandRouter(self._file_mgr)

        # 连接文件上传信号
        self._chat.file_uploaded.connect(self._on_file_uploaded)

        # 从配置恢复用户设置（覆盖默认值）
        self._apply_config()

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
        self._canvas.model_ready.connect(self._on_model_ready)
        layout.addWidget(self._canvas, stretch=1)

        # 聊天面板（浮动叠加在画布上方，底部居中）
        self._chat = ChatPanel(central)
        self._chat.message_sent.connect(self._on_user_message)
        self._chat.geometry_changed.connect(self._move_chat_to_bottom)
        # 窗口 resize 时重新调整聊天面板位置
        self.resizeEvent = self._on_resize

    def _apply_config(self) -> None:
        """从 config.json 恢复用户配置（角色大小、置顶、吸附、聊天、窗口位置）"""
        # 1. 角色大小（先恢复，会改变窗口尺寸）
        size = cfg.get("character_size", "medium")
        scale_map = {"small": 0.75, "medium": 1.0, "large": 1.25}
        scale = scale_map.get(size, 1.0)
        if scale != 1.0:
            self._apply_scale(scale)
        # 同步菜单选中状态
        for action in self._size_group.actions():
            action.setChecked(action.data() == scale)

        # 2. 置顶状态
        top = cfg.get("always_on_top", True)
        if not top:
            flags = self.windowFlags()
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            self._action_top.setChecked(False)
            self.show()
        else:
            self._action_top.setChecked(True)

        # 3. 任务栏吸附
        snap = cfg.get("taskbar_snap", True)
        self._action_snap.setChecked(snap)
        if snap:
            self._snap_to_taskbar()

        # 4. 聊天面板
        chat = cfg.get("chat_enabled", False)
        if chat:
            self._chat.show()
            self._move_chat_to_bottom()
            self._chat._input.setFocus()
        else:
            self._chat.hide()

        # 5. 窗口位置（最后恢复，覆盖默认位置）
        geo = cfg.get("window_geometry")
        if geo:
            self.setGeometry(geo["x"], geo["y"], geo["width"], geo["height"])
        else:
            self._move_to_default_position()

        logger.info(
            f"配置已恢复: size={size}, top={top}, snap={snap}, chat={chat}"
        )

    def _save_window_geometry(self) -> None:
        """保存当前窗口位置与尺寸到 config.json"""
        cfg.set(
            "window_geometry",
            {
                "x": self.x(),
                "y": self.y(),
                "width": self.width(),
                "height": self.height(),
            },
        )

    def _on_model_ready(self) -> None:
        """Live2D 模型初始化完成后关闭启动画面"""
        if self._splash is not None:
            logger.info("模型加载完成，关闭启动画面")
            self._splash.close()
            self._splash = None

    def _setup_tray(self) -> None:
        """初始化系统托盘"""
        self._tray = TrayIcon(self)
        self._tray.show_window.connect(self.show)
        self._tray.hide_window.connect(self.hide)
        self._tray.show()

    def _build_shared_menu(self) -> None:
        """
        构建统一菜单（任务栏右键 + 角色右键共用）
        菜单项：显示/隐藏、聊天开关、置顶、角色大小、关于、退出
        """
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QActionGroup

        self._menu = QMenu(self)

        # ---- 显示/隐藏葵酱 ----
        self._action_visible = QAction("隐藏葵酱", self)
        self._action_visible.triggered.connect(self._toggle_visibility)
        self._menu.addAction(self._action_visible)

        # ---- 聊天开关 ----
        self._action_chat = QAction("想和葵酱聊天", self)
        self._action_chat.triggered.connect(self._toggle_chat_panel)
        self._menu.addAction(self._action_chat)

        # ---- 窗口置顶 ----
        self._action_top = QAction("窗口置顶", self)
        self._action_top.setCheckable(True)
        self._action_top.setChecked(True)  # 默认置顶
        self._action_top.triggered.connect(self._toggle_topmost)
        self._menu.addAction(self._action_top)

        # ---- 任务栏吸附 ----
        self._action_snap = QAction("任务栏吸附", self)
        self._action_snap.setCheckable(True)
        self._action_snap.setChecked(True)  # 默认开启
        self._action_snap.triggered.connect(self._toggle_snap)
        self._menu.addAction(self._action_snap)

        self._menu.addSeparator()

        # ---- 角色大小子菜单 ----
        size_menu = QMenu("角色大小", self)
        self._size_group = QActionGroup(self)
        self._size_group.setExclusive(True)

        for label, scale in [("小", 0.75), ("中", 1.0), ("大", 1.25)]:
            action = QAction(label, self, checkable=True)
            action.setData(scale)
            if scale == 1.0:
                action.setChecked(True)
            action.triggered.connect(lambda checked, s=scale: self._apply_scale(s))
            self._size_group.addAction(action)
            size_menu.addAction(action)

        self._menu.addMenu(size_menu)

        # ---- 语音转文字模型子菜单 ----
        self._stt_menu = self._build_stt_menu()
        self._menu.addMenu(self._stt_menu)

        # ---- 日志级别子菜单 ----
        log_menu = QMenu("日志级别", self)
        self._log_group = QActionGroup(self)
        self._log_group.setExclusive(True)
        current_level = get_current_level_name()
        for label in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            action = QAction(label, self, checkable=True)
            action.setData(label)
            action.setChecked(label == current_level)
            action.triggered.connect(lambda checked, l=label: set_level(l))
            self._log_group.addAction(action)
            log_menu.addAction(action)
        self._menu.addMenu(log_menu)

        self._menu.addSeparator()

        # ---- 关于 ----
        action_about = QAction("关于", self)
        action_about.triggered.connect(self._show_about)
        self._menu.addAction(action_about)

        # ---- 退出 ----
        action_quit = QAction("退出", self)
        action_quit.triggered.connect(self._on_quit)
        self._menu.addAction(action_quit)

        # 菜单显示前更新动态文字和模型完整性
        self._menu.aboutToShow.connect(self._update_menu_text)

        # 同时设置给托盘
        self._tray.set_menu(self._menu)

    def _build_stt_menu(self):
        """构建语音转文字模型子菜单"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QActionGroup
        from voice.model_manager import get_available_models, get_current_model_id

        stt_menu = QMenu("语音转文字模型", self)
        self._stt_group = QActionGroup(self)
        self._stt_group.setExclusive(True)

        for model_id, config in get_available_models().items():
            action = QAction(config["name"], self, checkable=True)
            action.setData(model_id)
            action.setChecked(model_id == get_current_model_id())
            action.triggered.connect(lambda checked, m=model_id: self._on_stt_model_selected(m))
            self._stt_group.addAction(action)
            stt_menu.addAction(action)

        return stt_menu

    def _ensure_chat_visible(self) -> None:
        """确保聊天面板可见并正确定位（保持窗口位置不变）"""
        if not self._chat.isVisible():
            pos = self.pos()
            self._chat.show()
            self.move(pos)
            self._move_chat_to_bottom()

    def _on_stt_model_selected(self, model_id: str) -> None:
        """菜单中选择语音模型：未下载则直接开始下载并显示进度，已下载则切换"""
        from voice.model_manager import is_model_downloaded, set_current_model_id, get_download_manager

        if not is_model_downloaded(model_id):
            dm = get_download_manager()
            if dm.is_downloading():
                self._chat.add_message("葵酱：当前正在下载模型呢，请稍后再试哦~", is_user=False)
                return
            set_current_model_id(model_id)
            dm.start_download(model_id)
            self._update_stt_menu_state()
            self._chat.add_message("葵酱：开始下载语音模型啦，请稍候~", is_user=False)
            self._ensure_chat_visible()
            self._chat.show_download_progress()
            return

        set_current_model_id(model_id)
        self._update_stt_menu_state()
        from voice.model_manager import get_available_models
        name = get_available_models()[model_id]["name"]
        self._chat.add_message(f"葵酱：已切换到 {name}~", is_user=False)
        self._ensure_chat_visible()
        logger.info(f"语音模型切换为 {model_id}")

    def _update_stt_menu_state(self) -> None:
        """更新语音模型菜单的选中状态"""
        from voice.model_manager import get_current_model_id
        current = get_current_model_id()
        for action in self._stt_group.actions():
            action.setChecked(action.data() == current)

    def _check_stt_model_integrity(self) -> None:
        """菜单打开时检测当前选中的模型是否仍完整存在"""
        from voice.model_manager import get_current_model_id, is_model_downloaded, set_current_model_id
        current = get_current_model_id()
        if current is not None and not is_model_downloaded(current):
            set_current_model_id(None)
            self._update_stt_menu_state()

    def _setup_download_tracking(self) -> None:
        """连接下载管理器信号，在托盘显示下载进度"""
        from voice.model_manager import get_download_manager
        dm = get_download_manager()
        dm.progress.connect(self._on_download_progress)
        dm.finished.connect(self._on_download_finished)
        dm.download_started.connect(self._on_download_started)
        dm.download_stopped.connect(self._on_download_stopped)

    def _on_download_started(self, model_id: str) -> None:
        # 在输入框位置显示常驻进度条
        self._ensure_chat_visible()
        self._chat.show_download_progress()

    def _on_download_stopped(self) -> None:
        self._tray.update_tooltip()

    def _on_download_progress(self, model_id, pct, downloaded, total, speed):
        from voice.model_manager import get_available_models
        name = get_available_models()[model_id]["name"]
        detail = f"下载 {name}: {pct}%"
        if speed:
            detail += f" ({speed})"
        self._tray.update_tooltip(detail)

    def _on_download_finished(self, model_id, success, message):
        from voice.model_manager import get_available_models
        name = get_available_models()[model_id]["name"]
        self._tray.update_tooltip()
        if success:
            self._tray.show_message("下载完成", f"{name} 已下载完成，可以使用语音输入啦~")
            self._chat.add_message(f"葵酱：{name} 下载完成啦，可以使用语音输入了哦~", is_user=False)
            # 下载完成自动打开聊天面板
            self._ensure_chat_visible()
            # 如果当前没有设置模型，自动设置为刚下载的
            from voice.model_manager import get_current_model_id, set_current_model_id
            if get_current_model_id() != model_id:
                set_current_model_id(model_id)
                self._update_stt_menu_state()
        else:
            if message == "已取消":
                self._chat.add_message("葵酱：下载已取消，资源已清理~", is_user=False)
                return
            friendly = message
            if any(k in message for k in ("10060", "10054", "Connection", "Timeout")):
                friendly = "网络连接失败"
            self._tray.show_message("下载失败", f"{name} {friendly}，请重试", QSystemTrayIcon.MessageIcon.Warning)
            self._chat.add_message(f"葵酱：下载失败 — {friendly}，请重试~", is_user=False)

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
        """将窗口移动到屏幕右下角，角色底部贴住任务栏顶部"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - _DEFAULT_WIDTH - 20
        # 垂直方向吸附：角色底部贴住任务栏顶部
        if hasattr(self, '_action_snap') and self._action_snap.isChecked():
            y = screen.bottom() - int(_DEFAULT_HEIGHT * _CHARACTER_BOTTOM_RATIO)
        else:
            y = screen.bottom() - _DEFAULT_HEIGHT - 20
        self.move(x, y)

    def _move_chat_to_bottom(self) -> None:
        """将聊天面板定位到角色底部对齐"""
        if hasattr(self, '_chat'):
            chat = self._chat
            parent = chat.parentWidget()
            if parent:
                chat_width = getattr(chat, '_base_width', 280)
                cx = (parent.width() - chat_width) // 2
                # 聊天面板底部略低于角色底部，遮住一点脚部
                character_bottom = int(parent.height() * _CHARACTER_BOTTOM_RATIO) + 3
                cy = character_bottom - chat.height()
                cy = max(cy, 0)
                chat.move(cx, cy)
                chat.raise_()

    def _on_resize(self, event) -> None:
        """窗口大小变化时，重新调整聊天面板位置并防抖保存尺寸"""
        super().resizeEvent(event)
        self._move_chat_to_bottom()
        self._save_geometry_timer.start(500)

    def moveEvent(self, event) -> None:
        """窗口移动时防抖保存位置"""
        super().moveEvent(event)
        self._save_geometry_timer.start(500)

    def _snap_to_taskbar(self) -> None:
        """拖拽释放时：若角色底部靠近任务栏顶部则吸附"""
        screen = QApplication.screenAt(self.geometry().center())
        if not screen:
            return

        geo = screen.geometry()
        avail = screen.availableGeometry()

        # 只处理底部有任务栏的情况
        if avail.bottom() >= geo.bottom():
            return

        taskbar_top = avail.bottom()
        # 以角色底部为基准计算距离
        character_bottom = self.y() + int(self.height() * _CHARACTER_BOTTOM_RATIO)
        dist = taskbar_top - character_bottom

        # 阈值 = 任务栏高度的一半（动态适应不同 DPI/屏幕）
        taskbar_height = geo.bottom() - avail.bottom()
        threshold = max(taskbar_height // 2, 10)

        # 角色底部高于或低于任务栏顶部，只要在阈值内就吸附
        if -threshold <= dist <= threshold:
            if hasattr(self, '_action_snap') and self._action_snap.isChecked():
                new_y = taskbar_top - int(self.height() * _CHARACTER_BOTTOM_RATIO)
                self.move(self.x(), new_y)
                logger.debug(f"角色底部吸附到任务栏顶部: y={self.y()}")

    # ---- 事件重写 ----

    def showEvent(self, event) -> None:
        """窗口首次显示时重新确认位置（覆盖窗口管理器可能的默认定位），并延迟调整聊天面板"""
        super().showEvent(event)
        if not getattr(self, '_geometry_restored', False):
            self._geometry_restored = True
            geo = cfg.get("window_geometry")
            if geo:
                self.move(geo["x"], geo["y"])
                # 若开启了吸附，在正确位置基础上再次吸附
                if self._action_snap.isChecked():
                    self._snap_to_taskbar()
        QTimer.singleShot(50, self._move_chat_to_bottom)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        鼠标按下：记录拖拽起始位置
        注意：实际拖拽逻辑主要在 Live2DCanvas 中处理，这里作为后备
        """
        if event.button() == Qt.MouseButton.RightButton:
            self._menu.popup(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        """右键菜单事件"""
        self._menu.popup(event.globalPos())

    # ---- 槽函数 ----

    def _toggle_visibility(self) -> None:
        """切换主窗口显示/隐藏"""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _update_menu_text(self) -> None:
        """菜单显示前更新动态文字（显示/隐藏、聊天开关）"""
        if self.isVisible():
            self._action_visible.setText("隐藏葵酱")
        else:
            self._action_visible.setText("显示葵酱")

        if self._chat.isVisible():
            self._action_chat.setText("不和葵酱聊天")
        else:
            self._action_chat.setText("想和葵酱聊天")

        self._check_stt_model_integrity()

    def _toggle_chat_panel(self) -> None:
        """
        切换聊天面板显示/隐藏
        同时保存并恢复窗口位置，避免位置被重置
        """
        pos = self.pos()
        self._chat.toggle_visibility()
        self.move(pos)
        cfg.set("chat_enabled", self._chat.isVisible())
        if self._chat.isVisible():
            self._move_chat_to_bottom()
            self._chat._input.setFocus()

    def _on_file_uploaded(self, path: str) -> None:
        """用户通过 📎 上传文件"""
        dst = self._file_mgr.save_upload(path)
        filename = dst.name
        self._chat.add_system_message(f"📎 已收到文件 {filename}")
        self._chat.add_message(
            "葵酱：可以输入指令查询成绩啦~\n"
            "试试：/成绩 <歌曲名>",
            is_user=False,
        )
        logger.info(f"用户上传文件: {filename}")

    def _on_user_message(self, text: str) -> None:
        """
        用户发送消息后的处理
        先尝试斜杠指令路由，非指令再走 AI 回复流程
        """
        logger.info(f"用户消息: {text}")

        # 1. 先尝试斜杠指令（本地处理）
        cmd_reply = self._cmd_router.handle(text)
        if cmd_reply is not None:
            self._chat.show_typing_indicator()
            QTimer.singleShot(600, lambda: self._show_reply(cmd_reply))
            return

        # 2. 非指令，走 AI 回复流程
        self._state.force_transit(CharacterState.THINKING)
        self._chat.show_typing_indicator()
        QTimer.singleShot(2000, lambda: self._do_ai_reply(text))

    def _show_reply(self, text: str) -> None:
        """显示指令回复（不经过 AI）"""
        self._chat.hide_typing_indicator()
        self._chat.add_message(text, is_user=False)
        # 指令回复不改变角色状态，保持 IDLE

    def _do_ai_reply(self, text: str) -> None:
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
            cfg.set("always_on_top", False)
            logger.info("置顶已关闭")
        else:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
            self._action_top.setChecked(True)
            cfg.set("always_on_top", True)
            logger.info("置顶已开启")
        self.show()

    def _toggle_snap(self) -> None:
        """切换任务栏吸附状态，开启时若已在阈值内则立即吸附"""
        if self._action_snap.isChecked():
            cfg.set("taskbar_snap", True)
            logger.info("任务栏吸附已开启")
            self._snap_to_taskbar()
        else:
            cfg.set("taskbar_snap", False)
            logger.info("任务栏吸附已关闭")

    def _apply_scale(self, scale: float) -> None:
        """应用角色大小缩放"""
        if scale == self._current_scale:
            return
        self._current_scale = scale

        new_width = int(_DEFAULT_WIDTH * scale)
        new_height = int(_DEFAULT_HEIGHT * scale)

        # 记录窗口中心点，缩放后以中心为锚点保持位置
        old_geo = self.geometry()
        center_x = old_geo.center().x()
        center_y = old_geo.center().y()

        # 调整窗口大小
        self.resize(new_width, new_height)

        # 以中心为锚点重新定位，避免窗口漂移
        new_x = center_x - new_width // 2
        new_y = center_y - new_height // 2
        self.move(new_x, new_y)

        # 同步调整聊天面板宽度
        if hasattr(self, '_chat'):
            new_chat_width = int(280 * scale)
            self._chat.set_panel_width(new_chat_width)
            self._move_chat_to_bottom()

        size_map = {0.75: "small", 1.0: "medium", 1.25: "large"}
        cfg.set("character_size", size_map.get(scale, "medium"))
        logger.info(f"角色大小调整为 {scale}x ({new_width}x{new_height})")

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
        """退出应用（保存配置、清空临时文件后退出）"""
        from voice.model_manager import get_download_manager
        dm = get_download_manager()
        if dm.is_downloading():
            dm.cancel_download()
        self._save_window_geometry()
        self._file_mgr.clear_all()
        logger.info("用户请求退出")
        self._tray.hide()
        QApplication.instance().quit()
