# -*- coding: utf-8 -*-
"""
启动画面（Splash Screen）
VTuber 直播间待机风格：漂浮爱心/星星粒子、待机浮动徽章头像（LIVE 小红标）、
缎带横幅、气泡状态文案、扫光标题、糖针纹滚动进度条（爱心车头）
动画运行在 splash_child.py 子进程的专属事件循环中，全程流畅不受主进程阻塞
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
from PySide6.QtCore import (
    Qt,
    QTimer,
    QRect,
    QRectF,
    QElapsedTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QLinearGradient,
    QPixmap,
)

from utils.logger import get_logger

logger = get_logger(__name__)


def _heart_path() -> QPainterPath:
    """心形路径：四段三次贝塞尔曲线，竖向比例拉长（避免显扁），静态缓存"""
    path = QPainterPath()
    path.moveTo(0.0, 0.42)
    path.cubicTo(0.0, 0.22, -0.20, 0.0, -0.5, 0.0)
    path.cubicTo(-0.88, 0.0, -1.02, 0.30, -1.02, 0.58)
    path.cubicTo(-1.02, 1.02, -0.58, 1.42, 0.0, 1.82)
    path.cubicTo(0.58, 1.42, 1.02, 1.02, 1.02, 0.58)
    path.cubicTo(1.02, 0.30, 0.88, 0.0, 0.5, 0.0)
    path.cubicTo(0.20, 0.0, 0.0, 0.22, 0.0, 0.42)
    return path


_HEART = None


def heart_path() -> QPainterPath:
    global _HEART
    if _HEART is None:
        _HEART = _heart_path()
    return _HEART


class _CometBar(QWidget):
    """糖针纹滚动进度条：斜纹轨道 + 珊瑚渐变滑块 + 爱心车头（大爱心完整显示）"""

    _PERIOD_MS = 1100  # 单程滚动周期

    def __init__(self, parent=None):
        super().__init__(parent)
        # 背景层需要持续重绘（粒子/星星动画），由本控件的定时器驱动
        self.setFixedSize(200, 20)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 轨道：圆角底 + pastel 斜纹（糖针感）
        track = QRectF(0, 7, self.width(), 6)
        track_path = QPainterPath()
        track_path.addRoundedRect(track, 3, 3)
        p.fillPath(track_path, QColor("#FFDDD5"))
        p.save()
        p.setClipPath(track_path)
        p.setPen(QPen(QColor("#FFF5F0"), 4))
        for x in range(-8, self.width() + 8, 10):
            p.drawLine(x, 18, x + 8, 0)
        p.restore()

        # 滚动滑块：按墙钟时间定位（稀疏重绘时位置依然正确）
        t = (self._elapsed.elapsed() % self._PERIOD_MS) / self._PERIOD_MS
        comet_w = 56
        x = t * (self.width() - comet_w)
        comet = QRectF(x, 7, comet_w, 6)
        comet_path = QPainterPath()
        comet_path.addRoundedRect(comet, 3, 3)
        grad = QLinearGradient(x, 0, x + comet_w, 0)
        grad.setColorAt(0.0, QColor(255, 111, 102, 0))
        grad.setColorAt(0.55, QColor("#FF6F66"))
        grad.setColorAt(1.0, QColor("#F06292"))
        p.fillPath(comet_path, grad)

        # 大爱心车头：明显大于轨道高度，像一颗大爱心拖着滑块跑
        p.save()
        p.translate(x + comet_w - 3, 10.2)
        p.scale(7.2, 7.2)
        p.translate(0, -0.62)
        p.setPen(QPen(QColor("#FFFFFF"), 0.24))
        p.setBrush(QColor("#FF4D6D"))
        p.drawPath(heart_path())
        p.restore()
        p.end()


class _BubbleLabel(QWidget):
    """气泡状态文案：圆角白泡 + 小尾巴 + 弹入动画（几何回弹）"""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._label = QLabel(text, self)
        self._label.setFont(QFont("Microsoft YaHei UI", 11))
        self._label.setStyleSheet("color: #8A736C; background: transparent; border: none;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._popped = False

    def setText(self, text: str) -> None:
        self._label.setText(text)
        self.adjustSizeToContent()

    def adjustSizeToContent(self) -> None:
        fm = self._label.fontMetrics()
        w = fm.horizontalAdvance(self._label.text()) + 34
        self.setFixedSize(w, 34)
        self._label.setGeometry(0, 0, w, 30)

    def pop_in(self) -> None:
        """弹性弹入动画（OutBack 回弹曲线，几何缩放实现）"""
        if self._popped:
            return
        self._popped = True
        final = QRect(self.x(), self.y(), self.width(), self.height())
        sw, sh = int(final.width() * 0.6), int(final.height() * 0.6)
        start = QRect(final.center().x() - sw // 2, final.center().y() - sh // 2, sw, sh)
        self.setGeometry(start)
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(380)
        anim.setStartValue(start)
        anim.setEndValue(final)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.start()
        self._pop_anim = anim  # 持有引用防止被 GC 回收

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), 30
        # 尾巴（底部居中偏左，指向角色方向）
        tail = QPainterPath()
        cx = w // 2 - 10
        tail.moveTo(cx, h - 2)
        tail.lineTo(cx + 12, h - 2)
        tail.lineTo(cx + 3, h + 7)
        tail.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFD9D4"))
        p.drawPath(tail)
        tail_in = tail.translated(0, -1.2)
        p.setBrush(QColor("#FFFFFF"))
        p.drawPath(tail_in)
        # 泡体
        body = QPainterPath()
        body.addRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 15, 15)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#FFD9D4"), 1.5))
        p.drawPath(body)
        p.end()


class SplashScreen(QWidget):
    """
    VTuber 待机风格启动画面
    - 无边框、置顶、抗锯齿自绘圆角卡片（透明背景）、居中显示
    - 加载完成后由外部调用 request_close()（最短展示 1.2s + 淡出后关闭）
    """

    _CORNER_RADIUS = 20
    # 卡片区域（四周留出空间手绘柔影与缎带）
    _CARD_MARGIN = 16
    # 最短展示时长：加载极快时也不闪退，保证用户看清启动画面（含淡出）
    _MIN_VISIBLE_MS = 1200
    # 标题扫光周期
    _SWEEP_PERIOD_MS = 2200

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setFixedSize(340, 272)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # 全局文字样式（卡片背景、柔影与装饰由 paintEvent 自绘）
        self.setStyleSheet("QLabel { color: #4A3F3A; background: transparent; border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 16, 30, 12)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 图标（窗口图标 + 徽章内图标）
        icon_path = "resources/icons/app_icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 徽章容器：头像待机浮动 + LIVE 小红标
        holder = QWidget(self)
        holder.setFixedSize(76, 86)
        holder.setStyleSheet("background: transparent; border: none;")

        badge = QLabel(holder)
        badge.setGeometry(6, 18, 64, 64)
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

        # LIVE 小红标：放在容器（holder）层而非徽章内——徽章的圆角
        # 样式表会裁剪子控件，导致骑角部分被切断；随头像一起浮动。
        # 基础 y 留足上浮余量（bob 最大上移 5px），防止最高点时被容器上缘截断
        live = QLabel("LIVE", holder)
        live.setGeometry(32, 8, 36, 16)
        live.setAlignment(Qt.AlignmentFlag.AlignCenter)
        live.setFont(QFont("Microsoft YaHei UI", 7, QFont.Weight.Bold))
        live.setStyleSheet(
            "background: #FF4D4D; color: #FFFFFF; border: 2px solid #FFFFFF;"
            "border-radius: 8px;"
        )
        live.raise_()

        layout.addWidget(holder, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(2)

        # 标题区：用占位条占据布局，文字与扫光由父窗口 paintEvent 统一绘制
        # （透明子控件自绘扫光会累积残影/破坏底层，同一表面直绘才是正确做法）
        self._title_row = QWidget(self)
        self._title_row.setFixedHeight(30)
        self._title_row.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._title_row)

        title_font = QFont("Microsoft YaHei UI", 20, QFont.Weight.Bold)
        try:
            title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        except Exception:
            pass
        self._title_font = title_font
        self._title_text = "葵之使魔"

        layout.addSpacing(2)

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

        layout.addSpacing(8)

        # 气泡状态文案
        self._bubble = _BubbleLabel("葵酱正在梳妆打扮，请稍候~")
        self._bubble.adjustSizeToContent()
        layout.addWidget(self._bubble, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(10)

        # 糖针纹滚动进度条
        self._comet = _CometBar()
        layout.addWidget(self._comet, alignment=Qt.AlignmentFlag.AlignCenter)

        self._center_on_screen()
        self._elapsed = QElapsedTimer()
        self._elapsed.start()

        # 待机浮动：墙钟正弦驱动（比 QPropertyAnimation yoyo 更顺滑且无跳变）
        # 徽章与 LIVE 标同步浮动
        self._badge = badge
        self._live = live
        self._badge_base = badge.pos()
        self._live_base = live.pos()
        self._bob_timer = QTimer(self)
        self._bob_timer.timeout.connect(self._bob_tick)
        self._bob_timer.start(33)

        # 背景层（粒子/闪烁星星在 paintEvent 中按墙钟定位）需要持续重绘才能动起来
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self.update)
        self._bg_timer.start(33)

        logger.info("启动画面已创建")

    def _bob_tick(self) -> None:
        t = self._elapsed.elapsed() / 1000.0
        dy = (math.sin(t * 2 * math.pi / 1.6) + 1.0) / 2.0 * 5.0
        self._badge.move(self._badge_base.x(), self._badge_base.y() - dy)
        self._live.move(self._live_base.x(), self._live_base.y() - dy)

    # ---- 自绘：卡片、柔影、缎带、漂浮粒子、闪烁星星 ----

    def _card_rect(self) -> QRectF:
        m = self._CARD_MARGIN
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._bubble.adjustSizeToContent()
        # 布局稳定后再弹入，避免动画起点取到错误几何
        QTimer.singleShot(60, self._bubble.pop_in)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = self._card_rect()
        t = self._elapsed.elapsed() / 1000.0

        # 手绘柔影
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

        # 柔粉边框（外）+ 内高光线
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

        # 漂浮粒子：爱心 / 星星 / 圆点，缓慢上浮 + 透明度呼吸
        self._paint_particles(p, card, t)

        # 闪烁四角星（墙钟正弦脉冲）
        for cx, cy, r, speed, phase in (
            (card.left() + 22, card.top() + 66, 4.5, 2.2, 0.0),
            (card.right() - 26, card.top() + 44, 3.2, 2.8, 1.5),
            (card.right() - 42, card.bottom() - 50, 4.0, 2.4, 3.0),
            (card.left() + 40, card.bottom() - 44, 2.8, 3.1, 4.2),
        ):
            breathe = 0.55 + 0.45 * math.sin(t * speed + phase)
            color = QColor("#FFCCC4")
            color.setAlphaF(color.alphaF() * breathe)
            self._paint_sparkle(p, cx, cy, r, color)

        # 标题（父窗口统一绘制：原色文字 + 柔边扫光）
        title_rect = self._title_row.geometry()
        if title_rect.width() > 0:
            p.setFont(self._title_font)
            p.setPen(QColor("#F2668B"))
            p.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self._title_text)
            self._paint_title_shine(p, title_rect, t)

        # 缎带横幅：STARTING ♡（斜贴卡片左上角，跨越边缘）
        p.save()
        p.translate(card.left() + 70, card.top() + 2)
        p.rotate(-7)
        ribbon = QRectF(-56, -12, 112, 24)
        ribbon_path = QPainterPath()
        ribbon_path.addRoundedRect(ribbon, 12, 12)
        r_grad = QLinearGradient(ribbon.left(), 0, ribbon.right(), 0)
        r_grad.setColorAt(0.0, QColor("#FF8A80"))
        r_grad.setColorAt(1.0, QColor("#F06292"))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(ribbon_path, r_grad)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        p.drawText(ribbon, Qt.AlignmentFlag.AlignCenter, "STARTING ♡")
        p.restore()
        p.end()

    def _paint_particles(self, p: QPainter, card: QRectF, t: float) -> None:
        """背景漂浮粒子：环绕卡片边缘分布（两侧竖带 + 头像/气泡两侧），
        中间内容列保持干净——形成完整的背景层，不与头像/标题/气泡互相截断
        (类型, x比例, 上浮周期s, 尺寸占卡宽比例, 相位, 垂直区间(顶,底)比例, 颜色)"""
        particles = (
            ("heart", 0.055, 6.5, 0.052, 0.0, (0.06, 0.94), QColor(255, 142, 170, 85)),
            ("star", 0.125, 8.5, 0.04, 2.1, (0.10, 0.90), QColor(255, 179, 150, 95)),
            ("dot", 0.090, 6.0, 0.026, 4.4, (0.04, 0.96), QColor(255, 179, 180, 90)),
            ("heart", 0.922, 8.0, 0.048, 1.2, (0.08, 0.92), QColor(255, 142, 170, 80)),
            ("star", 0.875, 7.0, 0.038, 3.3, (0.12, 0.88), QColor(255, 179, 150, 90)),
            ("dot", 0.910, 9.0, 0.025, 5.0, (0.02, 0.98), QColor(255, 179, 180, 85)),
            ("star", 0.255, 9.0, 0.033, 2.8, (0.04, 0.42), QColor(244, 143, 177, 80)),
            ("heart", 0.750, 7.5, 0.044, 0.6, (0.06, 0.40), QColor(255, 142, 170, 80)),
            ("dot", 0.240, 8.0, 0.024, 3.9, (0.58, 0.97), QColor(255, 179, 180, 85)),
            ("star", 0.760, 9.0, 0.032, 5.6, (0.60, 0.95), QColor(255, 179, 150, 80)),
        )
        for kind, fx, period, rel, phase, (z0, z1), color in particles:
            prog = ((t / period) + phase / 6.283) % 1.0
            top = card.top() + card.height() * z0
            travel = card.height() * (z1 - z0)
            y = top + (1.0 - prog) * travel
            x = card.left() + card.width() * fx + math.sin(t * 0.9 + phase) * 4.0
            edge_fade = math.sin(prog * math.pi)  # 首尾淡出
            c = QColor(color)
            c.setAlphaF(color.alphaF() * edge_fade)
            size = rel * card.width()
            if kind == "heart":
                p.save()
                p.translate(x, y)
                p.scale(size, size)
                p.translate(0, -0.35)
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

    def _paint_title_shine(self, p: QPainter, title_rect, t: float) -> None:
        """标题扫光：白色文字渲染进光带位图，再用水平渐变做 SourceIn 合成，
        光带两侧羽化过渡——只有字形变色、边缘柔和无矩形边界"""
        prog = ((t * 1000) % self._SWEEP_PERIOD_MS) / self._SWEEP_PERIOD_MS
        band_w = 64.0
        feather = band_w * 0.32  # 两侧羽化宽度
        band_x = title_rect.left() + prog * (title_rect.width() + 2 * band_w) - band_w
        h = title_rect.height()
        dpr = self.devicePixelRatioF()

        pm = QPixmap(int(band_w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        pp = QPainter(pm)
        pp.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 以光带为局部坐标系绘制白色文字（文字全局位置 = title_rect → 平移进光带）
        pp.setFont(self._title_font)
        pp.setPen(QColor(255, 255, 255, 255))
        pp.drawText(title_rect.translated(-band_x, 0), Qt.AlignmentFlag.AlignCenter, self._title_text)
        # SourceIn：用渐变填充只在文字像素上生效，两侧羽化到全透明
        pp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        grad = QLinearGradient(0, 0, band_w, 0)
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(feather / band_w, QColor(255, 255, 255, 120))
        grad.setColorAt(1.0 - feather / band_w, QColor(255, 255, 255, 120))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        pp.setPen(Qt.PenStyle.NoPen)
        pp.setBrush(grad)
        pp.drawRect(QRectF(0, 0, band_w, h))
        pp.end()

        p.drawPixmap(int(band_x), int(title_rect.top()), pm)

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

    # ---- 关闭流程 ----

    def request_close(self) -> None:
        """加载完成后调用：距创建不足最短展示时长时稍候片刻，淡出后关闭"""
        remaining = self._MIN_VISIBLE_MS - self._elapsed.elapsed()
        if remaining > 0:
            QTimer.singleShot(int(remaining), self._fade_out_and_close)
        else:
            self._fade_out_and_close()

    def _fade_out_and_close(self) -> None:
        """淡出动画结束后关闭（窗口透明属性支持 windowOpacity）"""
        try:
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(220)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(self.close)
            anim.start()
            self._fade_anim = anim  # 持有引用防止被 GC 回收
        except Exception:
            self.close()

    def set_status(self, text: str) -> None:
        """更新加载状态文案（气泡内文本）"""
        self._bubble.setText(text)

    def _center_on_screen(self) -> None:
        """将窗口居中到主屏幕"""
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )
