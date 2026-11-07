# -*- coding: utf-8 -*-
"""
VTuber 常驻装饰（v0.1.30 / B 版）

全部在 Qt 层自绘，不触碰 QOpenGLWidget（避免 GL 状态污染）；
装饰层均设 WA_TransparentForMouseEvents，保持桌面鼠标穿透。
动画一律 QElapsedTimer 墙钟驱动（位置只由时间决定，不依赖累计帧数）：
装饰动画 33ms 重绘，点击粒子与 Live2D 的 60fps 对齐走 16ms，
空闲即停表，不新增常驻定时器。
"""
import math
import random
from dataclasses import dataclass

from PySide6.QtCore import Qt, QRect, QRectF, QElapsedTimer, QTimer, QPoint
from PySide6.QtGui import (
    QColor, QFont, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ui.avatar import load_app_icon_pixmap
from ui.card_paint import paint_cute_card
from ui.splash_screen import heart_path
from ui.theme import BLUSH, ONLINE, ROSE
from utils.font_manager import cute_font

_AVATAR_CACHE: dict[tuple[int, float, bool], QPixmap] = {}


def round_avatar_pixmap(size: int, dpr: float | None = None, ring: bool = True) -> QPixmap | None:
    """把矩形应用图标裁成圆形头像。

    高分屏下按 devicePixelRatio 超采样（至少 2x）：生成更大物理像素的位图
    并 setDevicePixelRatio，逻辑尺寸仍为 size，drawPixmap 时不会被拉伸成
    模糊的马赛克。按 (size, 采样倍率, 是否描边) 缓存，避免重复读盘与缩放。
    ring=False 时只做圆形裁切、不画那圈珊瑚粉环（用于 LIVE 牌，避免与
    卡片矩形边框形成两圈贴在一起的线）。
    """
    if dpr is None:
        dpr = 1.0
        gui = QGuiApplication.instance()
        if gui is not None:
            screen = gui.primaryScreen()
            if screen is not None:
                dpr = screen.devicePixelRatio()
    scale = max(2.0, min(3.0, float(dpr)))
    key = (size, round(scale, 2), ring)
    if key in _AVATAR_CACHE:
        return _AVATAR_CACHE[key]

    src = load_app_icon_pixmap()
    if not src or src.isNull():
        return None
    side = min(src.width(), src.height())
    square = src.copy(
        (src.width() - side) // 2, (src.height() - side) // 2, side, side
    )
    phys = max(2, int(round(size * scale)))
    square = square.scaled(
        phys, phys,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    pm = QPixmap(phys, phys)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(0.5, 0.5, phys - 1.0, phys - 1.0))
    p.setClipPath(clip)
    p.drawPixmap(0, 0, square)
    p.setClipping(False)
    if ring:
        line = max(1.0, 1.5 * scale)
        p.setPen(QPen(QColor(BLUSH), line))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(line / 2, line / 2, phys - line, phys - line))
    p.end()
    pm.setDevicePixelRatio(scale)
    _AVATAR_CACHE[key] = pm
    return pm


class LiveBadge(QWidget):
    """常驻 LIVE 状态牌：奶油渐变卡片 + 无环圆形头像 + 独立在线点 + 萌体文字。

    头像不再用带多层圆环的 AvatarBadge：圆形头像与卡片矩形边框贴得太近时，
    两圈描边会视觉粘连。改成「无描边圆形裁切 + 淡粉柔影」把头像从卡片里
    托出来，卡片边框与头像之间留出 3~10px 空隙；在线点单独画在右下角，
    保留 LIVE 语义但不引入第二圈线。
    """

    _W, _H = 168, 44
    _AV, _AX, _AY = 26, 16, 9

    def __init__(self, character_name: str = "葵酱", parent=None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._name = character_name
        self._avatar = round_avatar_pixmap(self._AV, ring=False)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_cute_card(p, self.width(), self.height(), 14, 6)
        if self._avatar and not self._avatar.isNull():
            # 淡粉柔影（不是描边），让无环头像在奶油底上依然清晰
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(249, 184, 196, 55))
            p.drawEllipse(QRectF(self._AX - 2, self._AY - 2, self._AV + 4, self._AV + 4))
            p.drawPixmap(self._AX, self._AY, self._avatar)
            # 在线点：绿点 + 白描边，独立于头像轮廓
            p.setBrush(QColor(ONLINE))
            p.setPen(QPen(QColor("#FFFFFF"), 1.6))
            p.drawEllipse(QRectF(self._AX + self._AV - 7, self._AY + self._AV - 7, 8, 8))
        p.setFont(cute_font(11, QFont.Weight.Bold))
        p.setPen(QColor(ROSE))
        p.drawText(
            QRectF(50, 5, self.width() - 56, self.height() - 10),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"LIVE · {self._name}",
        )
        p.end()


class TypingDots(QWidget):
    """三个呼吸圆点：墙钟驱动 + 33ms 重绘，替代 3 个无限循环 QVariantAnimation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)

    def start(self) -> None:
        self._elapsed.start()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, event) -> None:
        t = self._elapsed.elapsed() / 1000.0 if self._elapsed.isValid() else 0.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            wave = 0.5 + 0.5 * math.sin(t * 4.2 - i * 0.9)
            c = QColor(ROSE)
            c.setAlpha(int(255 * (0.30 + 0.70 * wave)))
            p.setBrush(c)
            p.drawEllipse(QRectF(2 + i * 13, 3 - 2.0 * wave, 8, 8))
        p.end()


_STAR: QPainterPath | None = None


def _star_path() -> QPainterPath:
    """四角星（尖瓣闪光），单位半径 1，静态缓存"""
    global _STAR
    if _STAR is None:
        path = QPainterPath()
        for i in range(8):
            r = 1.0 if i % 2 == 0 else 0.30
            a = -math.pi / 2 + i * math.pi / 4
            x, y = r * math.cos(a), r * math.sin(a)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        _STAR = path
    return _STAR


@dataclass
class _Particle:
    kind: str          # heart / star / dot
    x: float
    y: float
    size: float
    color: QColor
    born: int
    life: int
    drift: float       # 水平漂移
    rise: float        # 上升高度
    swing: float       # 正弦横摆幅度
    phase: float
    spin: float        # 旋转角度（度）


class HeartBurst(QWidget):
    """点击角色时的「爱心 + 星星 + 闪光」粒子。

    与 Live2D 的 60fps 对齐（16ms 重绘），但位置全部由 QElapsedTimer 墙钟
    计算，掉帧也不会跳跃；粒子与闪光耗尽即停表隐藏，不新增常驻定时器。
    """

    _TIMER_MS = 16
    _FLASH_MS = 520
    _POP_MS = 1900          # 与粒子 life(1500~2000) 同步，避免主爱心先一步消失
    _COUNT_HEART, _COUNT_STAR, _COUNT_DOT = 5, 2, 2
    _PALETTE = ("#F2668B", "#FF8A80", "#FFB4AB", "#FFF3EE", "#FFD98A")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(self._TIMER_MS)
        # 默认 CoarseTimer 会把 16ms 对齐到系统时钟粒度（Windows 常见 15.6/31.2ms），
        # 用 PreciseTimer 才真正贴近 60fps。
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._particles: list[_Particle] = []
        self._flash: tuple[float, float, int] | None = None
        self._pop: tuple[float, float, int] | None = None
        self._dirty = QRect()   # 只需重绘点击点附近，省掉整窗透明层重绘
        self.hide()

    @staticmethod
    def _region_for(pos: QPoint) -> QRect:
        """覆盖粒子飘散全程的局部区域（横向 ±150、上方 175、下方 70）"""
        return QRect(pos.x() - 150, pos.y() - 175, 300, 245)

    def _tick(self) -> None:
        """局部重绘：粒子只在一个小范围内活动，没必要每帧刷整个 400×600 透明层"""
        if self._dirty.isEmpty():
            self.update()
        else:
            self.update(self._dirty)

    def burst(self, pos: QPoint) -> None:
        """在 canvas 局部坐标 pos 处生成一簇混合粒子 + 一圈点击闪光"""
        if not self._elapsed.isValid():
            self._elapsed.start()
        now = self._elapsed.elapsed()
        self._particles = [
            item for item in self._particles if now - item.born < item.life
        ]
        kinds = (
            ["heart"] * self._COUNT_HEART
            + ["star"] * self._COUNT_STAR
            + ["dot"] * self._COUNT_DOT
        )
        for i, kind in enumerate(kinds):
            if kind == "heart":
                color = QColor(self._PALETTE[i % 3])
                size = random.uniform(12.0, 19.0)
            elif kind == "star":
                color = QColor(self._PALETTE[3 + (i % 2)])
                size = random.uniform(9.0, 14.0)
            else:
                color = QColor(self._PALETTE[2])
                size = random.uniform(5.5, 9.0)
            self._particles.append(_Particle(
                kind=kind,
                x=pos.x() + random.uniform(-46, 46),
                y=pos.y() + random.uniform(-18, 18),
                size=size,
                color=color,
                born=now + i * 70,
                life=random.randint(1500, 2000),
                drift=random.uniform(-70, 70),
                rise=random.uniform(58, 100),
                swing=random.uniform(6.0, 16.0),
                phase=random.uniform(0.0, math.tau),
                spin=random.uniform(-28, 28),
            ))
        self._flash = (float(pos.x()), float(pos.y()), now)
        self._pop = (float(pos.x()), float(pos.y()), now)
        region = self._region_for(pos).intersected(self.rect())
        self._dirty = region if self._dirty.isEmpty() else self._dirty.united(region)
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start()

    # ---- 绘制 ----

    def _paint_flash(self, p: QPainter, now: int) -> bool:
        """点击瞬间向外扩散的粉色柔光波。

        不用纯白（浅色桌面 / 角色上几乎看不见，且中心又被大爱心盖住），
        也不用硬圈线或长放射线（上一版四道斜线被看成白色大叉号）。
        改成「中心透明 → 中环亮 → 边缘透明」的环形渐变：没有硬边，
        但能明显看到一圈暖粉色的光从点击点扩散开。
        """
        if self._flash is None:
            return False
        x, y, born = self._flash
        t = (now - born) / self._FLASH_MS
        if t < 0:
            return True
        if t >= 1:
            self._flash = None
            return False
        alpha = 1.0 - t
        r = 14.0 + 54.0 * (1.0 - (1.0 - t) ** 2)
        # 注意：QRadialGradient 的 6 参数重载是 (cx,cy,centerRadius,fx,fy,focalRadius)，
        # 写成 (x,y,0,x,y,r) 会让渐变几乎画不出来；中心点+半径要用 3 参数形式。
        glow = QRadialGradient(x, y, r)
        glow.setColorAt(0.00, QColor(255, 255, 255, 0))
        glow.setColorAt(0.30, QColor(255, 214, 222, int(28 * alpha)))
        glow.setColorAt(0.58, QColor(255, 150, 178, int(150 * alpha)))
        glow.setColorAt(0.78, QColor(255, 205, 216, int(72 * alpha)))
        glow.setColorAt(1.00, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))
        # 中心一点暖白亮度，让点击点「亮一下」
        core = QRadialGradient(x, y, r * 0.42)
        core.setColorAt(0.0, QColor(255, 250, 246, int(120 * alpha)))
        core.setColorAt(1.0, QColor(255, 250, 246, 0))
        p.setBrush(core)
        p.drawEllipse(QRectF(x - r * 0.42, y - r * 0.42, r * 0.84, r * 0.84))
        # 一颗短小四角星（不是长斜线）
        p.save()
        p.setOpacity(max(0.0, min(1.0, alpha * 0.9)))
        p.translate(x, y)
        s = 3.0 + 6.0 * t
        p.scale(s, s)
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawPath(_star_path())
        p.restore()
        return True

    def _paint_pop_heart(self, p: QPainter, now: int) -> bool:
        """点击正中央弹出的主爱心：弹性回弹后，以与粒子相同的慢速一起向上飘散"""
        if self._pop is None:
            return False
        x, y, born = self._pop
        t = (now - born) / self._POP_MS
        if t < 0:
            return True
        if t >= 1:
            self._pop = None
            return False
        k = min(1.0, t / 0.16) - 1.0
        pop = 1.0 + 2.70158 * k ** 3 + 1.70158 * k ** 2
        # 淡出曲线与粒子一致（t=0.68 才开始淡），配合 1.9s 生命不再一闪而过
        fade = min(1.0, t / 0.06) * min(1.0, (1.0 - t) / 0.32)
        p.save()
        p.setOpacity(max(0.0, min(1.0, fade)))
        # 与周围粒子同向：匀速上升 78px / 1.9s ≈ 41px/s（粒子约 30~67px/s）
        px = x + math.sin(t * 3.0) * 7.0
        py = y - 78.0 * t
        p.translate(px, py)
        s = 24.0 * pop * (1.0 - 0.28 * t) / 2.04
        p.scale(s, s)
        p.translate(0, -0.91)
        p.setBrush(QColor("#FF8A80"))
        p.setPen(QPen(QColor("#E0507A"), 0.09))
        p.drawPath(heart_path())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(QRectF(-0.50, -0.44, 0.19, 0.19))
        p.restore()
        return True

    def _paint_particle(self, p: QPainter, item: _Particle, now: int) -> bool:
        """返回 False 表示生命结束、可从列表移除"""
        t = (now - item.born) / item.life
        if t < 0:
            return True
        if t >= 1:
            return False
        # 弹性入场（easeOutBack，轻微回弹）+ 末尾轻收；整体节奏随 life 拉长而放慢
        k = min(1.0, t / 0.16) - 1.0
        pop = 1.0 + 2.70158 * k ** 3 + 1.70158 * k ** 2
        pop *= 1.0 - 0.12 * max(0.0, (t - 0.8) / 0.2)
        fade = min(1.0, t / 0.07) * min(1.0, (1.0 - t) / 0.32)
        # 匀速上升（原来是先快后猛冲，观感太急），横摆频率同步放慢
        px = item.x + item.drift * t + math.sin(t * 4.0 + item.phase) * item.swing
        py = item.y - item.rise * t

        p.save()
        p.setOpacity(max(0.0, min(1.0, fade)))
        p.translate(px, py)
        p.rotate(item.spin * t)
        if item.kind == "heart":
            s = item.size * pop / 2.04
            p.save()
            p.scale(s, s)
            p.translate(0, -0.91)
            p.setBrush(item.color)
            p.setPen(QPen(QColor("#E0507A"), 0.085))
            p.drawPath(heart_path())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawEllipse(QRectF(-0.50, -0.44, 0.17, 0.17))
            p.restore()
        elif item.kind == "star":
            s = item.size * pop / 2.0
            p.save()
            p.scale(s, s)
            p.setBrush(item.color)
            p.setPen(QPen(QColor("#F2A6B8"), 0.08))
            p.drawPath(_star_path())
            p.restore()
        else:
            r = item.size * pop / 2.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(item.color)
            p.drawEllipse(QRectF(-r, -r, r * 2, r * 2))
            p.setBrush(QColor(255, 255, 255, 210))
            p.drawEllipse(QRectF(-r * 0.45, -r * 0.50, r * 0.45, r * 0.45))
        p.restore()
        return True

    def paintEvent(self, event) -> None:
        if not self._particles and self._flash is None and self._pop is None:
            return
        now = self._elapsed.elapsed()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        flash_alive = self._paint_flash(p, now)
        pop_alive = self._paint_pop_heart(p, now)
        alive = [item for item in self._particles if self._paint_particle(p, item, now)]
        p.end()
        self._particles = alive
        if not self._particles and not flash_alive and not pop_alive:
            self._dirty = QRect()
            self._timer.stop()
            self.hide()
