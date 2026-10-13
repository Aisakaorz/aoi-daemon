# -*- coding: utf-8 -*-
"""
关于对话框：与启动画面同一设计语言的圆角卡片
徽章图标 + 萌体标题 + 版本信息 + 漂浮爱心/星星背景装饰，点击任意处关闭
"""
import math
import os

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QRectF, QTimer, QElapsedTimer
from PySide6.QtGui import (
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QLinearGradient,
)

from core.bootstrap import APP_VERSION
from ui.splash_screen import heart_path
from utils.font_manager import cute_font
from utils.logger import get_logger

logger = get_logger(__name__)


class AboutDialog(QDialog):
    """圆角卡片式关于弹窗（奶油渐变底 + 珊瑚粉边框 + 手绘柔影）"""

    _CORNER_RADIUS = 16
    _CARD_MARGIN = 12

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(280, 216)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 14)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 徽章图标
        badge = QLabel()
        badge.setFixedSize(56, 56)
        badge.setStyleSheet(
            "background: #FFFFFF; border: 2px solid #FFD9D4; border-radius: 28px;"
        )
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(5, 5, 5, 5)
        icon_label = QLabel()
        icon_label.setFixedSize(44, 44)
        icon_label.setScaledContents(True)
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_path = "resources/icons/app_icon.ico"
        if os.path.exists(icon_path):
            pixmap = QIcon(icon_path).pixmap(88, 88)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap)
        badge_layout.addWidget(icon_label)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        title = QLabel("葵之使魔")
        title.setFont(cute_font(15, QFont.Weight.Bold))
        title.setStyleSheet("color: #F2668B; background: transparent; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(2)

        caption_font = cute_font(7)
        try:
            caption_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
        except Exception:
            pass
        caption = QLabel("AOIDAEMON")
        caption.setFont(caption_font)
        caption.setStyleSheet("color: #D8B4AC; background: transparent; border: none;")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)

        layout.addSpacing(10)

        version = QLabel(f"v{APP_VERSION} · 桌面 Live2D 伴侣")
        version.setFont(cute_font(9))
        version.setStyleSheet("color: #8A736C; background: transparent; border: none;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        layout.addSpacing(4)

        foot = QLabel("Powered by Aoi🌻 Kimi🤖 · MIT License")
        foot.setFont(cute_font(8))
        foot.setStyleSheet("color: #C9A9A0; background: transparent; border: none;")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(foot)

        layout.addSpacing(8)

        # 关闭提示（浅灰，放最底部）
        hint = QLabel("点击任意处即可关闭")
        hint.setFont(cute_font(7))
        hint.setStyleSheet("color: #D8C8C2; background: transparent; border: none;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # 背景装饰动画驱动（与启动画面同款的漂浮爱心/星星）
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self.update)
        self._bg_timer.start(33)

    # ---- 卡片绘制（与启动画面同一套配方） ----

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = QRectF(
            self._CARD_MARGIN,
            self._CARD_MARGIN,
            self.width() - 2 * self._CARD_MARGIN,
            self.height() - 2 * self._CARD_MARGIN,
        )
        # 手绘柔影
        for expand, dy, alpha in ((4.0, 3.0, 26), (2.0, 2.0, 42)):
            shadow_rect = QRectF(card).adjusted(-expand, -expand, expand, expand)
            shadow_rect.translate(0, dy)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                shadow_rect, self._CORNER_RADIUS + expand, self._CORNER_RADIUS + expand
            )
            p.fillPath(shadow_path, QColor(249, 184, 196, alpha))
        # 卡片：奶油渐变底
        path = QPainterPath()
        path.addRoundedRect(card, self._CORNER_RADIUS, self._CORNER_RADIUS)
        grad = QLinearGradient(0, card.top(), 0, card.bottom())
        grad.setColorAt(0.0, QColor("#FFFBF8"))
        grad.setColorAt(1.0, QColor("#FFF0EA"))
        p.fillPath(path, grad)

        # 背景装饰粒子（两侧边栏上浮，与启动画面同款配方）
        self._paint_particles(p, card, self._elapsed.elapsed() / 1000.0)

        # 珊瑚粉边框 + 内高光线
        stroke = QRectF(card).adjusted(0.5, 0.5, -0.5, -0.5)
        stroke_path = QPainterPath()
        stroke_path.addRoundedRect(stroke, self._CORNER_RADIUS, self._CORNER_RADIUS)
        p.setPen(QPen(QColor("#FFB4AB"), 2))
        p.drawPath(stroke_path)
        inner = QRectF(card).adjusted(2.5, 2.5, -2.5, -2.5)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(inner, self._CORNER_RADIUS - 2, self._CORNER_RADIUS - 2)
        p.setPen(QPen(QColor(255, 255, 255, 160), 1))
        p.drawPath(inner_path)
        p.end()

    def _paint_particles(self, p: QPainter, card: QRectF, t: float) -> None:
        """漂浮爱心/星星/圆点：沿卡片两侧边栏上浮，首尾淡入淡出"""
        particles = (
            # (类型, x比例, 上浮周期s, 尺寸占卡宽比例, 相位, 颜色)
            ("heart", 0.09, 6.5, 0.055, 0.0, QColor(255, 142, 170, 80)),
            ("star", 0.17, 8.5, 0.042, 2.1, QColor(255, 179, 150, 85)),
            ("dot", 0.125, 7.0, 0.027, 4.4, QColor(255, 179, 180, 85)),
            ("heart", 0.83, 7.5, 0.05, 1.2, QColor(255, 142, 170, 75)),
            ("star", 0.915, 8.0, 0.04, 3.3, QColor(255, 179, 150, 80)),
            ("dot", 0.875, 9.0, 0.026, 5.0, QColor(255, 179, 180, 80)),
        )
        top = card.top() + 12
        travel = card.height() - 24
        for kind, fx, period, rel, phase, color in particles:
            prog = ((t / period) + phase / 6.283) % 1.0
            y = top + (1.0 - prog) * travel
            x = card.left() + card.width() * fx + math.sin(t * 0.9 + phase) * 3.0
            edge_fade = math.sin(prog * math.pi)
            c = QColor(color)
            c.setAlphaF(color.alphaF() * edge_fade)
            size = rel * card.width()
            if kind == "heart":
                p.save()
                p.translate(x, y)
                p.scale(size, size)
                p.translate(0, -0.5)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawPath(heart_path())
                p.restore()
            elif kind == "star":
                self._paint_sparkle(p, x, y, size, c)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawEllipse(QRectF(x - size / 2, y - size / 2, size, size))

    @staticmethod
    def _paint_sparkle(p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
        path = QPainterPath()
        for i in range(8):
            radius = r if i % 2 == 0 else r * 0.42
            angle = math.pi / 4 * i - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(path)

    def mousePressEvent(self, event) -> None:
        """点击任意处关闭"""
        self.accept()
        super().mousePressEvent(event)
