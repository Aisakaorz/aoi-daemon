# -*- coding: utf-8 -*-
"""
圆形头像徽章：把矩形的 app_icon 裁成圆形，套白环 + 珊瑚粉外环，右下角带在线点

解决的问题：
    图标本身是矩形 PNG/ICO，直接塞进"圆角白底 QLabel"时，图片四个角会压在
    圆底之外露出来（`setScaledContents` 不会按圆角裁剪）。这里统一用 QPainter
    做圆形裁切，四角透明，任何尺寸都不会露出方形边缘。

用法：
    from ui.avatar import AvatarBadge
    badge = AvatarBadge(64, parent)
    badge.setOnline(False)   # 需要时切换在线状态
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from utils.logger import get_logger
from utils.paths import app_icon_path

logger = get_logger(__name__)

# 取自启动画面/关于卡片同一套配色，保证与既有装饰一致
_RING_COLOR = "#FFD9D4"      # 珊瑚粉外环
_ONLINE_COLOR = "#7FD1A6"    # 在线点


def load_app_icon_pixmap(size: int | None = None) -> QPixmap | None:
    """加载应用图标为位图（失败返回 None，调用方自行兜底）

    默认取图标文件内的**最大原生尺寸**，而不是写死一个大值：Windows 与
    macOS 的 ico 解析都遵循同一套 QIcon 逻辑，若图标只有 128px 帧而请求
    256px，Qt 会先放大再让我们缩回去，白丢一层清晰度。
    """
    path = app_icon_path()
    if not path:
        return None
    icon = QIcon(path)
    if icon.isNull():
        return None
    if size is None:
        sizes = icon.availableSizes()
        size = max((s.width() for s in sizes), default=256)
    pixmap = icon.pixmap(size, size)
    return None if pixmap.isNull() else pixmap


class AvatarBadge(QWidget):
    """圆形头像徽章：圆形裁切 + 白环 + 珊瑚粉外环 + 右下在线点"""

    def __init__(self, diameter: int = 64, parent=None, show_dot: bool = True):
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._d = float(diameter)
        self._show_dot = show_dot
        self._online = True
        self._src = load_app_icon_pixmap()
        # 呼吸脉冲（启动画面用来表达"正在唤醒"，静态使用时不开）
        self._pulse = False
        self._phase = 0.0
        self._pulse_timer: QTimer | None = None

    def setPulse(self, enabled: bool) -> None:
        """右下角状态点是否呼吸脉冲：加载中用 True，就绪后常亮用 False"""
        self._pulse = enabled
        if enabled:
            if self._pulse_timer is None:
                t = QTimer(self)
                t.timeout.connect(self._tick)
                t.start(90)
                self._pulse_timer = t
        elif self._pulse_timer is not None:
            self._pulse_timer.stop()
            self._pulse_timer = None
            self.update()

    def _tick(self) -> None:
        self._phase += 0.22
        if self._phase > math.tau:
            self._phase -= math.tau
        self.update()

    def setOnline(self, online: bool) -> None:
        """切换右下角状态点（False 时点变为灰白，仍然保留位置避免布局跳动）"""
        if self._online != online:
            self._online = online
            self.update()

    def setSourcePixmap(self, pixmap: QPixmap) -> None:
        """替换头像图（默认用应用图标，未来聊天头像可直接复用本控件）"""
        self._src = pixmap
        self.update()

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        d = self._d
        c = QPointF(d / 2.0, d / 2.0)
        ring_w = 2.0 if d < 80 else 2.6
        outer_r = d / 2.0 - ring_w / 2.0 - 0.5      # 外环中心线
        gap = max(2.0, d * 0.04)                     # 白环宽度
        image_r = outer_r - ring_w / 2.0 - gap

        # 白底圆（同时承担"图片与粉环之间的留白"）
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(c, outer_r, outer_r)

        # 圆形裁切的头像：源图按短边居中取正方形，再缩放进圆内
        p.save()
        clip = QPainterPath()
        clip.addEllipse(c, image_r, image_r)
        p.setClipPath(clip)
        if self._src is not None:
            src = self._src
            side = min(src.width(), src.height())
            src_rect = QRectF(
                (src.width() - side) / 2.0, (src.height() - side) / 2.0, side, side
            )
            dst = QRectF(c.x() - image_r, c.y() - image_r, image_r * 2, image_r * 2)
            p.drawPixmap(dst, src, src_rect)
        else:
            p.fillRect(
                QRectF(c.x() - image_r, c.y() - image_r, image_r * 2, image_r * 2),
                QColor("#FFE3DC"),
            )
        p.restore()

        # 珊瑚粉外环
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(_RING_COLOR), ring_w))
        p.drawEllipse(c, outer_r, outer_r)

        # 右下角在线点：压在外环内缘，白描边与头像分离
        if self._show_dot:
            # 注意：这里是"沿 x、y 各偏 offset"，实际距圆心是 offset*√2，
            # 所以系数要按 1/√2 折算，否则点会跑到圆外去
            r_dot = max(4.0, d * 0.082)
            dist = outer_r - r_dot * 1.05          # 点中心距圆心
            offset = dist / (2 ** 0.5)
            dot = QPointF(c.x() + offset, c.y() + offset)

            # 呼吸：半径轻微起伏 + 一圈淡光晕（不做缩放动画，避免文字抖动）
            breathe = math.sin(self._phase) if self._pulse else 0.0
            r_draw = r_dot * (1.0 + 0.10 * breathe)
            if self._pulse:
                halo = QColor(_ONLINE_COLOR)
                halo.setAlphaF(0.18 + 0.14 * breathe)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(dot, r_draw + 3.0, r_draw + 3.0)

            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.setBrush(QColor(_ONLINE_COLOR if self._online else "#D9D2CF"))
            p.drawEllipse(dot, r_draw, r_draw)

        p.end()
