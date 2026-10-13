# -*- coding: utf-8 -*-
"""
启动画面（Splash Screen）
在 Live2D 模型加载期间显示，提供视觉反馈，避免用户面对空白窗口
设计：galgame 风格加载卡片——奶白渐变底 + 珊瑚粉边框 + 柔影 + 圆形头像徽章
      + 彗星不定态进度条 + 跳动省略号 + 手绘星星装饰
"""
import math
import os

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, QRectF, QElapsedTimer
from PySide6.QtGui import (
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QLinearGradient,
)

from utils.logger import get_logger

logger = get_logger(__name__)


class _CometBar(QWidget):
    """不定态滚动进度条：小色块匀速向右循环滚动（marquee），带方向性拖尾"""

    _PERIOD_MS = 1100  # 单程滚动周期

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 8)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 轨道
        track = QRectF(0, 1, self.width(), 6)
        track_path = QPainterPath()
        track_path.addRoundedRect(track, 3, 3)
        p.fillPath(track_path, QColor("#FFDDD5"))

        # 滚动小条：按墙钟时间定位（启动期事件循环被阻塞、稀疏重绘时位置依然正确）
        t = (self._elapsed.elapsed() % self._PERIOD_MS) / self._PERIOD_MS
        comet_w = 56
        x = t * (self.width() - comet_w)
        comet = QRectF(x, 1, comet_w, 6)
        comet_path = QPainterPath()
        comet_path.addRoundedRect(comet, 3, 3)
        grad = QLinearGradient(x, 0, x + comet_w, 0)
        grad.setColorAt(0.0, QColor(255, 111, 102, 0))
        grad.setColorAt(0.55, QColor("#FF6F66"))
        grad.setColorAt(1.0, QColor("#F06292"))
        p.fillPath(comet_path, grad)
        p.end()


class SplashScreen(QWidget):
    """
    轻量级启动画面
    - 无边框、置顶、圆角（透明背景 + 抗锯齿自绘）、居中显示
    - 显示应用标题 + 加载状态文案 + 不定态彗星进度条
    - 加载完成后由外部调用 close() 关闭（WA_DeleteOnClose 自动销毁动画定时器）
    """

    _CORNER_RADIUS = 20
    # 卡片区域（四周留出空间手绘柔影）
    _CARD_MARGIN = 12
    # 最短展示时长：加载极快时也不闪退，保证用户看清启动画面（含淡出）
    _MIN_VISIBLE_MS = 1200

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setFixedSize(340, 230)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # 全局文字样式（卡片背景、柔影与装饰由 paintEvent 自绘）
        self.setStyleSheet("QLabel { color: #4A3F3A; background: transparent; border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 22)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 图标（窗口图标 + 徽章内图标）
        icon_path = "resources/icons/app_icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 圆形白色徽章头像
        badge = QLabel()
        badge.setFixedSize(64, 64)
        badge.setStyleSheet(
            "background: #FFFFFF; border: 2px solid #FFD9D4; border-radius: 32px;"
        )
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(6, 6, 6, 6)
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setScaledContents(True)
        icon_label.setStyleSheet("background: transparent; border: none;")
        if os.path.exists(icon_path):
            icon_pixmap = QIcon(icon_path).pixmap(96, 96)
            if not icon_pixmap.isNull():
                icon_label.setPixmap(icon_pixmap)
        badge_layout.addWidget(icon_label)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(12)

        # 标题
        title_font = QFont("Microsoft YaHei UI", 20, QFont.Weight.Bold)
        try:
            title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        except Exception:
            pass
        title = QLabel("葵之使魔")
        title.setFont(title_font)
        title.setStyleSheet("color: #F2668B; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(4)

        # 英文小字幕
        caption_font = QFont("Microsoft YaHei UI", 8)
        try:
            caption_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.0)
        except Exception:
            pass
        caption = QLabel("AOIDAEMON")
        caption.setFont(caption_font)
        caption.setStyleSheet("color: #D8B4AC; border: none;")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)

        layout.addSpacing(14)

        # 加载状态文案（静态，动效只由滚动进度条承担）
        self._status = QLabel("葵酱正在梳妆打扮，请稍候~")
        self._status.setFont(QFont("Microsoft YaHei UI", 11))
        self._status.setStyleSheet("color: #8A736C; border: none;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        layout.addSpacing(16)

        # 彗星进度条
        self._comet = _CometBar()
        layout.addWidget(self._comet, alignment=Qt.AlignmentFlag.AlignCenter)

        self._center_on_screen()
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        logger.info("启动画面已创建")

    def request_close(self) -> None:
        """加载完成后调用：距创建不足最短展示时长时稍候片刻，淡出后关闭"""
        remaining = self._MIN_VISIBLE_MS - self._elapsed.elapsed()
        if remaining > 0:
            QTimer.singleShot(int(remaining), self._fade_out_and_close)
        else:
            # 不经过定时器直接淡出，避免 singleShot(0) 在个别场景不触发
            self._fade_out_and_close()

    def _fade_out_and_close(self) -> None:
        """淡出动画结束后关闭（窗口透明属性支持 windowOpacity）"""
        try:
            from PySide6.QtCore import QPropertyAnimation

            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(220)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(self.close)
            anim.start()
            self._fade_anim = anim  # 持有引用防止被 GC 回收
        except Exception:
            self.close()

    # ---- 自绘卡片背景、柔影与装饰 ----

    def _card_rect(self) -> QRectF:
        """卡片圆角矩形区域（四周留出 _CARD_MARGIN 给手绘柔影）"""
        m = self._CARD_MARGIN
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = self._card_rect()

        # 手绘柔影：多层半透明圆角矩形模拟模糊（避免 QGraphicsDropShadowEffect
        # 在透明窗口上的白色残影，且不影响子控件动画刷新）
        for expand, dy, alpha in ((5.0, 4.0, 28), (3.0, 3.0, 40), (1.5, 2.0, 56)):
            shadow_rect = QRectF(card).adjusted(-expand, -expand, expand, expand)
            shadow_rect.translate(0, dy)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                shadow_rect, self._CORNER_RADIUS + expand, self._CORNER_RADIUS + expand
            )
            p.fillPath(shadow_path, QColor(249, 184, 196, alpha))

        # 卡片本体：奶白 → 浅珊瑚 纵向渐变
        path = QPainterPath()
        path.addRoundedRect(card, self._CORNER_RADIUS, self._CORNER_RADIUS)
        grad = QLinearGradient(0, card.top(), 0, card.bottom())
        grad.setColorAt(0.0, QColor("#FFFBF8"))
        grad.setColorAt(1.0, QColor("#FFF0EA"))
        p.fillPath(path, grad)

        # 柔粉边框（外）+ 顶部高光线（内）
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

        # 手绘装饰：四角小星星与圆点（相对卡片定位）
        self._paint_sparkle(p, card.left() + 18, card.top() + 22, 5, QColor("#FFCCC4"))
        self._paint_sparkle(p, card.right() - 18, card.top() + 30, 3.5, QColor("#FFDAD4"))
        self._paint_sparkle(p, card.right() - 32, card.bottom() - 20, 4.5, QColor("#FFCCC4"))
        self._paint_sparkle(p, card.left() + 32, card.bottom() - 16, 3, QColor("#FFDAD4"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFD0C8"))
        for x, y in ((card.left() + 40, card.top() + 14),
                     (card.right() - 44, card.top() + 52),
                     (card.left() + 54, card.bottom() - 30)):
            p.drawEllipse(QRectF(x - 1.6, y - 1.6, 3.2, 3.2))
        p.end()

    @staticmethod
    def _paint_sparkle(p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
        """四角星：外圈/内圈半径交替的八角多边形"""
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

    # ---- 动画与状态 ----

    def set_status(self, text: str) -> None:
        """更新加载状态文案（静态文本）"""
        self._status.setText(text)

    def _center_on_screen(self) -> None:
        """将窗口居中到主屏幕"""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )
