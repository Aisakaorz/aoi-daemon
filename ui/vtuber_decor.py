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
    QLinearGradient, QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ui.avatar import load_app_icon_pixmap
from ui.card_paint import paint_cute_card
from ui.splash_screen import heart_path
from ui.theme import BLUSH, ONLINE, ROSE, TEXT_MUTED
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
    """常驻 LIVE 状态牌：奶油渐变卡片 + 无环圆形头像 + 呼吸在线点 + 萌体文字。

    在线点的呼吸是这块牌自带的显示效果（不再单列开关）：牌可见就呼吸，
    关掉 LIVE 牌时定时器随 hideEvent 一起停，不空转。
    """

    _W, _H = 168, 44
    _AV, _AX, _AY = 26, 16, 9
    _PULSE_MS = 110        # 呼吸很慢，低频重绘足够，避免挤占 16ms 粒子层

    def __init__(self, character_name: str = "葵酱", parent=None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._name = character_name
        self._avatar = round_avatar_pixmap(self._AV, ring=False)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(self._PULSE_MS)
        self._pulse_timer.timeout.connect(self.update)

    def set_enabled(self, enabled: bool) -> None:
        """设置界面切换时即时显隐（不销毁，避免重建头像位图）；呼吸随之启停"""
        self.setVisible(bool(enabled))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._pulse_timer.start()

    def hideEvent(self, event) -> None:
        self._pulse_timer.stop()
        super().hideEvent(event)

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
            # 在线点：绿点 + 白描边 + 2.4s 呼吸光晕，独立于头像轮廓。
            # 呼吸是 LIVE 牌自带的显示效果，只改这个 8px 点的半径/亮度，
            # 不碰全窗 HeartBurst 粒子层。
            wave = 0.5 + 0.5 * math.sin(self._elapsed.elapsed() / 1000.0 * math.tau / 2.4)
            r = 3.2 + 1.0 * wave
            halo = QColor(QColor(ONLINE))
            halo.setAlpha(int(50 + 45 * wave))
            cx = self._AX + self._AV - 4
            cy = self._AY + self._AV - 4
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QRectF(cx - r - 2, cy - r - 2, (r + 2) * 2, (r + 2) * 2))
            p.setBrush(QColor(ONLINE))
            p.setPen(QPen(QColor("#FFFFFF"), 1.6))
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        p.setFont(cute_font(11, QFont.Weight.Bold))
        p.setPen(QColor(ROSE))
        p.drawText(
            QRectF(50, 5, self.width() - 56, self.height() - 10),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"LIVE · {self._name}",
        )
        p.end()


# 好感度牌的三档配色：只管小爱心与进度条的渐变深浅，
# 数值统一用 LIVE 牌文字同款 ROSE，避免三档越到后面颜色越深、显得过重
_TIER_COLORS = {
    "shy": ("#FFD9D4", "#FFB4AB"),
    "warm": ("#FFC9C2", "#FF8A80"),
    "close": ("#FFB4AB", "#F2668B"),
}
# 好感满值：暖金渐变作为里程碑，数值回落时会自动变回粉色
_BOND_COLORS = ("#FFE9B0", "#F2B03C")


class AffectionMeter(QWidget):
    """LIVE 牌右侧的好感度小牌：小爱心 + 数值 + 迷你进度条。

    按审核反馈把原本隐藏的好感值显示出来，归「LIVE 牌」这个开关管
    （关 LIVE 牌时一起隐藏）。数值增长时小爱心弹一下、进度条平滑追上、
    冒一个小小的 +N；按小时回落时则显示柔和的 -N、不弹爱心，进度条平滑退下。
    520ms 后停表 —— 只在变化时活动，不新增常驻定时器。
    """

    _W, _H = 96, 44
    _POP_MS = 520
    _TICK_MS = 33

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._value = 0
        self._shown = 0.0
        self._from = 0.0
        self._tier = "shy"
        self._gain = 0
        self._pop_active = False
        self._pop = QElapsedTimer()
        self._pop.start()
        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    def set_enabled(self, enabled: bool) -> None:
        """随 LIVE 牌开关显隐（不销毁，保留当前数值）"""
        self.setVisible(bool(enabled))

    def hideEvent(self, event) -> None:
        self._timer.stop()
        self._pop_active = False
        super().hideEvent(event)

    def set_value(self, value: int, animate: bool = True,
                  tier: str | None = None) -> None:
        """由 core.companion 下发；animate=False 用于启动恢复，不放入场动画。

        涨值显示 +N 并弹一下爱心，回落显示 -N（柔和灰粉、不弹爱心），
        两种方向都让进度条平滑追上新值，520ms 后停表。
        """
        if tier in _TIER_COLORS:
            self._tier = tier
        v = max(0, min(100, int(value)))
        if v == self._value:
            self.update()
            return
        self._gain = v - self._value
        self._value = v
        if animate and self.isVisible():
            self._from = self._shown
            self._pop.restart()
            self._pop_active = True
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._shown = float(v)
            self._pop_active = False
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        """墙钟驱动：进度条缓出追上新值，动画结束即停表"""
        t = min(1.0, self._pop.elapsed() / self._POP_MS)
        ease = 1.0 - (1.0 - t) ** 2
        self._shown = self._from + (self._value - self._from) * ease
        if t >= 1.0:
            self._shown = float(self._value)
            self._pop_active = False
            self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_cute_card(p, self.width(), self.height(), 14, 6)
        # 满值是里程碑：整块渐变换成暖金，回落一格就变回粉色，数值因此始终有起伏
        bond = self._value >= 100
        c0, c1 = (QColor(x) for x in
                  (_BOND_COLORS if bond else _TIER_COLORS[self._tier]))
        value_color = QColor(ROSE)   # 与左侧「LIVE · 葵酱」同色，不再随档位加深
        t = min(1.0, self._pop.elapsed() / self._POP_MS) if self._pop_active else 1.0
        # 只有涨值才弹爱心；回落时爱心保持原大小，避免「掉分还庆祝」
        pop = (math.sin(math.pi * t)
               if (self._pop_active and self._gain > 0) else 0.0)

        # 小爱心：整体右移留足左边距，档位越高略大，涨好感时弹一下
        p.save()
        p.translate(20.0, 17.0)
        tier_bonus = 0.0 if self._tier == "shy" else (0.3 if self._tier == "warm" else 0.6)
        s = (4.6 + tier_bonus) * (1.0 + 0.32 * pop)
        p.scale(s, s)
        p.translate(0, -0.91)
        g = QLinearGradient(0.0, 0.0, 0.0, 1.82)
        g.setColorAt(0.0, c0)
        g.setColorAt(1.0, c1)
        # 与光标 / 图标同一套画法：白色外描边让浅色档也立得住轮廓，
        # 深玫红细描边 + 渐变填充 + 一点白高光，比纯色小爱心更精致
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#FFFFFF"), 0.22))
        p.drawPath(heart_path())
        p.setBrush(g)
        p.setPen(QPen(QColor("#E0507A"), 0.10))
        p.drawPath(heart_path())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 210))
        p.drawEllipse(QRectF(-0.44, -0.42, 0.18, 0.14))
        p.restore()

        # 标签位平时写「好感」，变化的 520ms 里临时变成 +N / -N。
        # 数值紧跟标签左对齐（不再贴到卡片最右），中间不留大片空白、右侧也有边距。
        gaining = self._pop_active and self._gain > 0
        cooling = self._pop_active and self._gain < 0
        hint = (f"+{self._gain}" if gaining
                else (f"-{abs(self._gain)}" if cooling else "好感"))
        p.setFont(cute_font(8, QFont.Weight.Bold if (gaining or cooling)
                            else QFont.Weight.Normal))
        p.setPen(value_color if gaining else
                 (QColor("#B08A82") if cooling else QColor(TEXT_MUTED)))
        p.drawText(QRectF(30, 8, 26, 20),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   hint)
        p.setFont(cute_font(10, QFont.Weight.Bold))
        p.setPen(value_color)
        p.drawText(QRectF(52, 7, 34, 22),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   str(self._value))

        # 迷你进度条：左右各留 14px，与上方内容对齐
        bar = QRectF(14.0, 29.0, 68.0, 5.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFE6E2"))
        p.drawRoundedRect(bar, 2.5, 2.5)
        fw = min(bar.width(), max(0.0, bar.width() * self._shown / 100.0))
        if fw > 0.5:
            fill = QRectF(bar.x(), bar.y(), fw, bar.height())
            bg = QLinearGradient(bar.left(), 0.0, bar.right(), 0.0)
            bg.setColorAt(0.0, c0)
            bg.setColorAt(1.0, c1)
            p.setBrush(bg)
            p.drawRoundedRect(fill, 2.5, 2.5)
            if bond:
                # 满值时进度条末端是一颗小四角星，而不是普通白色高光点
                cx, cy = fill.right() - 2.0, bar.y() + bar.height() / 2
                star = QPainterPath()
                for i in range(8):
                    r = 3.0 if i % 2 == 0 else 1.0
                    a = -math.pi / 2 + i * math.pi / 4
                    sx, sy = cx + r * math.cos(a), cy + r * math.sin(a)
                    if i == 0:
                        star.moveTo(sx, sy)
                    else:
                        star.lineTo(sx, sy)
                star.closeSubpath()
                p.setBrush(QColor("#FFF6E0"))
                p.setPen(QPen(QColor("#E8A63C"), 0.5))
                p.drawPath(star)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 230))
                p.drawEllipse(QRectF(fill.right() - 2.4, bar.y() + 0.9, 3.2, 3.2))
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
_GREET_PETAL: QPainterPath | None = None
# 登场只留少量点缀色；主体花瓣直接取「飘落花瓣」的时段配色，
# 让登场环与常驻花瓣是同一套颜色，过渡才自然。
_GREET_ACCENTS = ("#FF8A80", "#F2668B", "#FFD98A", "#FFF3EE")


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


def _greet_petal_path() -> QPainterPath:
    """登场花瓣：上下尖、中部饱满的杏仁形，圆润无棱角（静态缓存）"""
    global _GREET_PETAL
    if _GREET_PETAL is None:
        path = QPainterPath()
        path.moveTo(0.0, -1.0)
        path.cubicTo(0.78, -0.62, 0.70, 0.52, 0.0, 1.0)
        path.cubicTo(-0.70, 0.52, -0.78, -0.62, 0.0, -1.0)
        path.closeSubpath()
        _GREET_PETAL = path
    return _GREET_PETAL


@dataclass
class _Particle:
    kind: str          # heart / star / dot / petal / puff
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
    from_greet: bool = False   # 登场粒子：关「点击爱心」时不该把它一起清掉
    # 登场环：沿椭圆绕中心转动，位置由 orbit_a0 + t*转数 决定，不用 drift/rise
    orbit: bool = False
    orbit_a0: float = 0.0
    orbit_rx: float = 0.0
    orbit_ry: float = 0.0


class HeartBurst(QWidget):
    """点击角色时的「爱心 + 星星 + 闪光」粒子。

    与 Live2D 的 60fps 对齐（16ms 重绘），但位置全部由 QElapsedTimer 墙钟
    计算，掉帧也不会跳跃；粒子与闪光耗尽即停表隐藏，不新增常驻定时器。
    """

    _TIMER_MS = 16
    _FLASH_MS = 520
    _POP_MS = 1900          # 与粒子 life(1500~2000) 同步，避免主爱心先一步消失
    _GREET_MS = 1600        # 登场柔光雾的持续时间（视觉主体是外圈旋转的粒子环）
    _GREET_COUNT = 14       # 收敛到 14 颗，避免太绚烂；以花瓣为主衔接常驻花瓣
    _GREET_TURN = math.tau * 0.55   # 转约 198° 就够，不再转满一大圈
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
        self._greet: tuple[float, float, int] | None = None
        self._greet_center: tuple[float, float] = (0.0, 0.0)  # 外圈旋转中心
        self._dirty = QRect()   # 只需重绘点击点附近，省掉整窗透明层重绘
        self._enabled = True         # 点击爱心开关，由 MainWindow.apply_effect() 下发
        self._greet_enabled = True   # 登场特效开关（与点击爱心独立）
        self.hide()

    def set_enabled(self, enabled: bool) -> None:
        """点击爱心开关：仅影响点击触发，不影响登场特效"""
        self._enabled = bool(enabled)

    def set_greeting(self, enabled: bool) -> None:
        """登场特效开关：关闭时把进行中的登场光环与登场粒子一起收干净"""
        self._greet_enabled = bool(enabled)
        if not enabled:
            self._greet = None
            self._particles = [i for i in self._particles if not i.from_greet]
            if not self._particles and self._flash is None and self._pop is None:
                self._dirty = QRect()
                self._timer.stop()
                self.hide()
            self.update()

    @staticmethod
    def _region_for(pos: QPoint, wide: bool = False) -> QRect:
        """覆盖粒子飘散全程的局部区域；登场散得更开，用大一圈的脏区"""
        if wide:
            # 外圈 + 后段下落都要罩得住（下方多留 60px）
            return QRect(pos.x() - 220, pos.y() - 240, 440, 440)
        return QRect(pos.x() - 150, pos.y() - 175, 300, 245)

    def _tick(self) -> None:
        """局部重绘：粒子只在一个小范围内活动，没必要每帧刷整个 400×600 透明层"""
        if self._dirty.isEmpty():
            self.update()
        else:
            self.update(self._dirty)

    def greet(self, pos: QPoint) -> None:
        """登场特效：外圈花瓣环绕着葵酱转半圈，然后像花瓣一样落下。

        按「有点太过绚烂、要跟飘落花瓣衔接」的反馈收敛：
        - 中心仍留白（角色自己就是中心），只有极淡柔光雾。
        - 粒子 20 → 14 颗，旋转 306° → 198°，以**花瓣**为主、爱心只作点缀。
        - 花瓣直接取常驻飘落花瓣的**当前时段配色**（同一个 current_palette），
          环与常驻花瓣同色系；后段粒子缓缓下落淡出，同时氛围层淡入，
          于是「登场 → 常态花瓣」是连续过渡，不会突然空掉。
        """
        if not self._greet_enabled:
            return
        if not self._elapsed.isValid():
            self._elapsed.start()
        now = self._elapsed.elapsed()
        self._particles = [
            item for item in self._particles if now - item.born < item.life
        ]
        # 与常驻花瓣同一套时段配色，登场和待机看起来是「同一场花瓣」
        from ui.ambient_decor import current_palette
        _name, petal_colors, _alpha_scale, _speed = current_palette()
        kinds = ["petal"] * 6 + ["heart"] * 5 + ["puff"] * 2 + ["dot"] * 1
        random.shuffle(kinds)
        self._greet_center = (float(pos.x()), float(pos.y()))
        for i, kind in enumerate(kinds):
            if kind == "petal":
                color = QColor(petal_colors[i % len(petal_colors)])
                size = random.uniform(13.0, 18.0)
            elif kind == "heart":
                color = QColor(_GREET_ACCENTS[i % 2])
                size = random.uniform(13.0, 18.0)
            elif kind == "puff":
                color = QColor(_GREET_ACCENTS[2])
                size = random.uniform(9.0, 13.0)
            else:
                color = QColor(_GREET_ACCENTS[3])
                size = random.uniform(5.0, 8.0)
            a0 = -math.pi / 2 + (i / self._GREET_COUNT) * math.tau \
                + random.uniform(-0.10, 0.10)
            rx = random.uniform(96.0, 138.0)
            ry = random.uniform(68.0, 104.0)
            self._particles.append(_Particle(
                kind=kind,
                x=pos.x() + math.cos(a0) * rx,
                y=pos.y() + math.sin(a0) * ry,
                size=size,
                color=color,
                born=now + i * 28,
                life=random.randint(2400, 3000),
                drift=0.0,
                rise=0.0,
                swing=random.uniform(2.0, 6.0),
                phase=random.uniform(0.0, math.tau),
                spin=random.uniform(-20.0, 20.0),
                from_greet=True,
                orbit=True,
                orbit_a0=a0,
                orbit_rx=rx,
                orbit_ry=ry,
            ))
        self._greet = (float(pos.x()), float(pos.y()), now)
        region = self._region_for(pos, wide=True).intersected(self.rect())
        self._dirty = region if self._dirty.isEmpty() else self._dirty.united(region)
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start()

    def burst(self, pos: QPoint) -> None:
        """在 canvas 局部坐标 pos 处生成一簇混合粒子 + 一圈点击闪光"""
        if not self._enabled:
            return
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

    def _paint_greeting(self, p: QPainter, now: int) -> bool:
        """登场：中心不再画任何具象形状，只有几团极淡的暖光雾。

        按审核反馈：中央那朵五瓣花「画得太明显太分明」，而且角色本来就在
        窗口中心，叠个花反而挡住主角。现在把中心完全留给葵酱，视觉主体是
        _paint_particle 里沿宽椭圆缓缓转一圈的外圈粒子。
        QRadialGradient 一律 3 参数（中心 + 半径），边缘全透明无硬圆边。
        """
        if self._greet is None:
            return False
        x, y, born = self._greet
        t = (now - born) / self._GREET_MS
        if t < 0:
            return True
        if t >= 1:
            self._greet = None
            return False
        fade = min(1.0, t / 0.12) * min(1.0, (1.0 - t) / 0.42)

        p.save()
        p.setOpacity(max(0.0, min(1.0, fade)))
        # 范围比旧版更宽、亮度更淡，只提供「亮起来」的氛围，不抢角色
        for i, (dx, dy, r0) in enumerate(((0.0, 0.0, 86.0),
                                          (-46.0, 18.0, 60.0),
                                          (42.0, -22.0, 56.0))):
            r = r0 * (0.82 + 0.35 * (1.0 - (1.0 - t) ** 2))
            ox = x + dx + math.sin(t * 1.4 + i) * 7.0
            oy = y + dy + math.cos(t * 1.1 + i) * 6.0
            glow = QRadialGradient(ox, oy, r)
            glow.setColorAt(0.00, QColor(255, 248, 242, 50))
            glow.setColorAt(0.50, QColor(255, 200, 216, 32))
            glow.setColorAt(1.00, QColor(255, 200, 216, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QRectF(ox - r, oy - r, r * 2, r * 2))
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
        if item.orbit:
            # 登场外圈：沿宽椭圆绕中心缓缓转过去，整体轻微上浮，形成「绕一圈」
            a = item.orbit_a0 + t * self._GREET_TURN
            cx, cy = self._greet_center
            px = cx + math.cos(a) * item.orbit_rx \
                + math.sin(t * 4.0 + item.phase) * item.swing
            py = cy + math.sin(a) * item.orbit_ry - 16.0 * t
            # 后段像花瓣一样缓缓落下并淡出，正好接上淡入的常驻花瓣
            fall = max(0.0, (t - 0.55) / 0.45)
            py += 80.0 * fall * fall
        else:
            # 点击粒子：匀速上升 + 横摆
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
        elif item.kind == "petal":
            # 登场专用：圆润杏仁花瓣 + 一点白高光，没有尖角
            s = item.size * pop / 2.0
            p.save()
            p.scale(s, s)
            p.setBrush(item.color)
            p.setPen(QPen(QColor("#E0507A"), 0.085))
            p.drawPath(_greet_petal_path())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(QRectF(-0.20, -0.48, 0.18, 0.13))
            p.restore()
        elif item.kind == "puff":
            # 登场专用：圆润四瓣小星，尺寸小、只作一圈里的点缀（不是主体）
            s = item.size * pop / 2.0
            p.save()
            p.scale(s, s)
            p.setBrush(item.color)
            p.setPen(QPen(QColor("#F2A6B8"), 0.055))
            for dx, dy in ((0.0, -0.55), (0.55, 0.0), (0.0, 0.55), (-0.55, 0.0)):
                p.drawEllipse(QRectF(dx - 0.36, dy - 0.36, 0.72, 0.72))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 215))
            p.drawEllipse(QRectF(-0.20, -0.20, 0.40, 0.40))
            p.restore()
        else:
            r = item.size * pop / 2.0
            # 登场光点加一圈淡粉细描边，浅底上才立得住；点击粒子保持原样
            if item.orbit:
                p.setPen(QPen(QColor("#F2A6B8"), 0.8))
            else:
                p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(item.color)
            p.drawEllipse(QRectF(-r, -r, r * 2, r * 2))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 210))
            p.drawEllipse(QRectF(-r * 0.45, -r * 0.50, r * 0.45, r * 0.45))
        p.restore()
        return True

    def paintEvent(self, event) -> None:
        if not self._particles and self._flash is None and self._pop is None and self._greet is None:
            return
        now = self._elapsed.elapsed()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        flash_alive = self._paint_flash(p, now)
        pop_alive = self._paint_pop_heart(p, now)
        greet_alive = self._paint_greeting(p, now)
        alive = [item for item in self._particles if self._paint_particle(p, item, now)]
        p.end()
        self._particles = alive
        if not self._particles and not flash_alive and not pop_alive and not greet_alive:
            self._dirty = QRect()
            self._timer.stop()
            self.hide()
