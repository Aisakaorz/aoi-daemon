# -*- coding: utf-8 -*-
"""
应用内的萌系鼠标样式 + 光标小拖尾（v0.1.31 / C 版）

类比 Windows 的「自定义鼠标指针 + 指针特效」，但只作用于桌宠窗口：
鼠标移到葵酱身上时，系统箭头直接换成一颗**珊瑚粉小爱心**（不再是
「箭头 + 挂件」），移动时身后留几片极小的花瓣 / 光点，很快淡出。

与之前被删掉的「悬停柔光」的区别：这是**看得懂、有用途的鼠标样式**
（明确的爱心形状 + 小花瓣拖尾），不是一团说不清的椭圆光晕。

要点：
- 热点用 QCursor 的默认值（不传 hotX/hotY），由 Qt 自动取光标位图的正中心，
  等价于逻辑坐标 (16, 16) —— 也就是爱心的中心，点击位置与看到的一致。
  不手写数字：位图按 DPR 超采样后是 64×64@2x，手写坐标的换算语义
  容易与 Qt 内部不一致，交给 Qt 取中心最稳，也不会随缩放比例变化。
- 拖尾配色取常驻飘落花瓣的同一套时段配色，风格与画面统一。
- 拖尾层鼠标穿透、Qt 层自绘；只在鼠标移动时短暂活动，空闲停表，
  不新增常驻定时器；局部重绘。
"""
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QElapsedTimer, QTimer
from PySide6.QtGui import (
    QColor, QCursor, QGuiApplication, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import QWidget

from ui.ambient_decor import current_palette
from ui.effect_settings import FX_CUTE_CURSOR, is_enabled

_CURSOR_CACHE: dict[float, QPixmap] = {}


def _petal_path() -> QPainterPath:
    """单位花瓣：上下尖、中部饱满的杏仁形"""
    path = QPainterPath()
    path.moveTo(0.0, -1.0)
    path.cubicTo(0.78, -0.62, 0.70, 0.52, 0.0, 1.0)
    path.cubicTo(-0.70, 0.52, -0.78, -0.62, 0.0, -1.0)
    path.closeSubpath()
    return path


_PETAL = _petal_path()


def cute_cursor_pixmap(size: int = 32, dpr: float | None = None) -> QPixmap:
    """一颗带渐变的小爱心作为整个指针：白色外描边 + 深玫红细描边。

    按审核反馈：去掉标准箭头后爱心本体放大居中，这里再缩到**约 16×15px**
    （和原生鼠标差不多大），并把纯色填充换成上浅下深的珊瑚粉线性渐变。
    渐变本身已有层次，不再叠白色高光点（旧版高光画在了心形轮廓外，
    会变成爱心上方一颗来路不明的小白点）。
    高分屏按 devicePixelRatio 超采样（至少 2x），逻辑尺寸仍是 size。
    """
    if dpr is None:
        dpr = 1.0
        gui = QGuiApplication.instance()
        if gui is not None:
            screen = gui.primaryScreen()
            if screen is not None:
                dpr = screen.devicePixelRatio()
    scale = max(2.0, min(3.0, float(dpr)))
    if scale in _CURSOR_CACHE:
        return _CURSOR_CACHE[scale]

    phys = int(round(size * scale))
    pm = QPixmap(phys, phys)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(scale, scale)

    # 一颗居中的小爱心就是指针本体（不再画箭头）
    from ui.splash_screen import heart_path
    heart = heart_path()
    s = size * 0.25          # 心形宽约 2.04s ≈ 16px、高约 1.82s ≈ 15px
    p.save()
    p.translate(size / 2.0, size / 2.0)
    p.scale(s, s)
    p.translate(0, -0.91)    # heart_path 的 y 范围是 0~1.82，移到中心
    # 白色外描边：浅色桌面也能立住轮廓（线宽按 s 缩放，缩小后同步减细）
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#FFFFFF"), 0.22))
    p.drawPath(heart)
    # 主体：上浅下深的珊瑚粉渐变，比纯色更柔和有层次
    grad = QLinearGradient(0.0, 0.0, 0.0, 1.82)
    grad.setColorAt(0.00, QColor("#FFC9C2"))
    grad.setColorAt(0.48, QColor("#FF8A80"))
    grad.setColorAt(1.00, QColor("#F2668B"))
    p.setBrush(grad)
    p.setPen(QPen(QColor("#E0507A"), 0.09))
    p.drawPath(heart)
    p.restore()
    p.end()

    pm.setDevicePixelRatio(scale)
    _CURSOR_CACHE[scale] = pm
    return pm


def cute_cursor() -> QCursor:
    """纯爱心没有指向性，热点交给 Qt 取位图正中心，点击位置与爱心中心一致"""
    return QCursor(cute_cursor_pixmap())


def apply_cute_cursor(widget: QWidget) -> None:
    widget.setCursor(cute_cursor())


def restore_cursor(widget: QWidget) -> None:
    widget.unsetCursor()


class CursorTrail(QWidget):
    """光标小拖尾：极小花瓣 / 光点，跟随鼠标移动后快速淡出"""

    _LIFE_MS = 520
    _STEP_PX = 10       # 移动超过 10px 才留一个，避免糊成一条线
    _MAX_POINTS = 18
    _TICK_MS = 33

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._enabled = is_enabled(FX_CUTE_CURSOR)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._points: list[tuple] = []
        self._last = QPoint(-9999, -9999)
        self._dirty = QRect()
        self.hide()

    # ---- 开关 / 生命周期 ----

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if not enabled:
            self._points.clear()
            self._timer.stop()
            self._clear_dirty()
            self.hide()
        self.update()

    def pause(self) -> None:
        self._timer.stop()
        self._points.clear()
        self._clear_dirty()
        self.hide()

    def resume(self) -> None:
        self._elapsed.restart()
        self._last = QPoint(-9999, -9999)

    def _clear_dirty(self) -> None:
        if not self._dirty.isEmpty():
            self.update(self._dirty)
            self._dirty = QRect()

    # ---- 输入 ----

    def on_cursor_moved(self, pos: QPoint) -> None:
        """由 Live2DCanvas.cursor_moved 驱动（复用已有的 30ms 检测）"""
        if not self._enabled:
            return
        if (pos - self._last).manhattanLength() < self._STEP_PX:
            return
        self._last = QPoint(pos)
        now = self._elapsed.elapsed()
        kind = "petal" if len(self._points) % 2 == 0 else "dot"
        self._points.append((float(pos.x()), float(pos.y()), now, kind))
        if len(self._points) > self._MAX_POINTS:
            self._points.pop(0)
        region = self._region()
        new_dirty = region if self._dirty.isEmpty() else self._dirty.united(region)
        self._dirty = new_dirty
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start()
        self.update(new_dirty)

    def _region(self) -> QRect:
        r = QRect()
        for x, y, _born, _kind in self._points:
            r = r.united(QRect(int(x) - 16, int(y) - 16, 32, 40))
        return r

    def _tick(self) -> None:
        now = self._elapsed.elapsed()
        old = self._dirty
        self._points = [q for q in self._points if now - q[2] < self._LIFE_MS]
        if not self._points:
            self._timer.stop()
            self._dirty = QRect()
            if not old.isEmpty():
                self.update(old)
            self.hide()
            return
        self._dirty = self._region()
        self.update(self._dirty.united(old))

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:
        if not self._enabled or not self._points:
            return
        now = self._elapsed.elapsed()
        _name, colors, _alpha_scale, _speed = current_palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for idx, (x, y, born, kind) in enumerate(self._points):
            t = (now - born) / self._LIFE_MS
            if t < 0 or t >= 1:
                continue
            fade = 1.0 - t
            py = y + 9.0 * t
            p.save()
            p.setOpacity(fade * 0.95)
            p.translate(x, py)
            p.rotate(18.0 * t + idx * 23.0)
            if kind == "petal":
                s = 5.0 * (1.0 - 0.3 * t)
                p.scale(s, s)
                p.setBrush(QColor(colors[idx % len(colors)]))
                p.setPen(QPen(QColor(224, 80, 122, int(170 * fade)), 0.14))
                p.drawPath(_PETAL)
            else:
                r = 3.0 * (1.0 - 0.35 * t)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#FFC98C"))
                p.drawEllipse(QRectF(-r, -r, r * 2, r * 2))
                p.setBrush(QColor(255, 255, 255, 210))
                p.drawEllipse(QRectF(-r * 0.45, -r * 0.5, r * 0.45, r * 0.45))
            p.restore()
        p.end()
