# -*- coding: utf-8 -*-
"""
启动画面（Splash Screen）
在 Live2D 模型加载期间显示，提供视觉反馈，避免用户面对空白窗口
"""
import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QFont,
    QIcon,
    QBitmap,
    QPainter,
    QPainterPath,
    QColor,
    QBrush,
    QPixmap,
)

from utils.logger import get_logger

logger = get_logger(__name__)


class SplashScreen(QWidget):
    """
    轻量级启动画面
    - 无边框、置顶、圆角、居中显示
    - 显示应用标题 + 加载状态文案 + 进度条（反映真实加载进度）
    - 加载完成后由外部调用 close() 关闭
    """

    _CORNER_RADIUS = 16

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setFixedSize(340, 200)

        # 用遮罩裁剪出圆角形状，样式表背景色会在可见区域内正常显示
        self._apply_rounded_mask()

        # 样式表只应用到 SplashScreen 自身，避免子 QWidget（如 header）继承边框
        self.setStyleSheet(
            f"""
            SplashScreen {{
                background-color: #FFF5F0;
                border-radius: {self._CORNER_RADIUS}px;
                border: 2px solid #FF8A80;
            }}
            QLabel {{
                color: #4A3F3A;
                background: transparent;
                border: none;
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 图标
        icon_path = "resources/icons/app_icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 应用图标 + 标题（同一行，整体居中，图标紧贴标题）
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        # 左侧弹性占位，把图标+标题推到中间
        header_layout.addStretch(1)

        # 图标（用 QIcon.pixmap 选最大分辨率）
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setScaledContents(True)
        icon_label.setStyleSheet("background: transparent; border: none;")
        if os.path.exists(icon_path):
            icon_pixmap = QIcon(icon_path).pixmap(48, 48)
            if not icon_pixmap.isNull():
                icon_label.setPixmap(icon_pixmap)
        header_layout.addWidget(icon_label)

        # 图标与标题之间的小间距
        header_layout.addSpacing(6)

        # 标题（无 stretch，紧挨图标）
        title = QLabel("葵之使魔")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #E57373; border: none;")
        header_layout.addWidget(title)

        # 右侧弹性占位，与左侧对称
        header_layout.addStretch(1)

        layout.addWidget(header)

        # 加载状态文案
        self._status = QLabel("葵酱正在梳妆打扮，请稍候~")
        self._status.setFont(QFont("Microsoft YaHei", 12))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        # 进度条（0~100，反映真实加载进度）
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(8)
        self._progress.setStyleSheet(
            """
            QProgressBar {
                background-color: #FFE0D6;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #FF8A80;
                border-radius: 4px;
            }
        """
        )
        layout.addWidget(self._progress)

        # 进度条平滑动画
        self._target_progress = 0
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._animate_progress)

        self._center_on_screen()
        logger.info("启动画面已创建")

    def _apply_rounded_mask(self) -> None:
        """设置圆角遮罩，使窗口边缘呈现真正的圆角"""
        bitmap = QBitmap(self.size())
        bitmap.clear()

        painter = QPainter(bitmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            bitmap.rect(), self._CORNER_RADIUS, self._CORNER_RADIUS
        )
        painter.fillPath(path, QBrush(Qt.GlobalColor.color1))
        painter.end()

        self.setMask(bitmap)

    def resizeEvent(self, event) -> None:
        """窗口大小变化时重新应用圆角遮罩"""
        super().resizeEvent(event)
        self._apply_rounded_mask()

    def _center_on_screen(self) -> None:
        """将窗口居中到主屏幕"""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

    def set_status(self, text: str) -> None:
        """更新加载状态文案"""
        self._status.setText(text)
        QApplication.processEvents()

    def set_progress(self, value: int) -> None:
        """设置目标进度值，由定时器平滑插值到目标"""
        self._target_progress = max(0, min(100, value))
        if not self._progress_timer.isActive():
            self._progress_timer.start(16)  # ~60fps

    def _animate_progress(self) -> None:
        """ease-out 插值动画，让进度条连续平滑变化"""
        current = self._progress.value()
        diff = self._target_progress - current
        if abs(diff) <= 1:
            self._progress.setValue(self._target_progress)
            self._progress_timer.stop()
            return
        # ease-out: 每次移动差值的 20%，最低 1
        step = max(1, int(abs(diff) * 0.2))
        self._progress.setValue(current + (step if diff > 0 else -step))
        QApplication.processEvents()
