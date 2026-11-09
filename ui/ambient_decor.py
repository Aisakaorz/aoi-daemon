# -*- coding: utf-8 -*-
"""
角色周边常驻氛围：飘落花瓣（v0.1.31 / C 版）

按审核反馈精简：脚下柔光台与聊天面板重叠、四角微光点在浅色桌面几乎
看不见，两者都已移除，只保留评价最好的飘落花瓣。

花瓣自带「按时段换色」：它属于花瓣的显示效果，不是独立特效，因此没有
单独开关，四段配色按本机当前小时自动选择，无网络、无额外定时器。

设计要点：
- 全部在 Qt 层自绘，叠在 Live2D 画布之上、聊天面板之下，不触碰
  QOpenGLWidget（避免 GL 状态污染，见 PRD 踩坑 #18/#21）。
- WA_TransparentForMouseEvents：不抢桌面 / 角色的鼠标事件。
- QElapsedTimer 墙钟驱动 + 33ms 重绘；窗口隐藏或开关关闭时停表，
  恢复时时间轴无缝续上（减去暂停时长），不空转。
- 花瓣固定数量循环复用，不产生垃圾对象；开关由 ui/effect_settings 统一管理。

与 HeartBurst 的区别：那是点击时的一次性爆发粒子，这里是常驻的、
极淡且缓慢的氛围层，两者颜色 / 速度 / 寿命都刻意拉开。
"""
import math
import random

from PySide6.QtCore import Qt, QRectF, QElapsedTimer, QTimer, QTime
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ui.effect_settings import FX_PETALS, is_enabled

# 默认（白天 / 关闭时段换色时）配色：淡粉奶油，避免抢角色
_PETAL_COLORS = ("#FFC9C2", "#FFE0D8", "#FFF1E9", "#FFE6BE")

# 时段配色：每个时段一套色调 + 一个整体不透明度系数（夜晚更安静、清晨更清透）
# 结构：名称 / 花瓣配色 / alpha 系数 / 下落速度系数
_TIME_PALETTES = (
    # 清晨 05:00–09:59：带露水的浅粉 + 嫩芽奶白
    (range(5, 10), "清晨", ("#FFD9DF", "#FFF0E6", "#FFF8EC", "#E9F3DD"), 0.92, 1.06),
    # 白天 10:00–16:59：明亮奶油粉（默认）
    (range(10, 17), "白天", _PETAL_COLORS, 1.00, 1.00),
    # 黄昏 17:00–19:59：橘金 + 蜜桃
    (range(17, 20), "黄昏", ("#FFC7A8", "#FFD9B8", "#FFE8CC", "#FFC98C"), 0.96, 0.94),
    # 夜晚 20:00–04:59：藕紫 + 月白，更淡更慢
    (None, "夜晚", ("#E3D8EC", "#F0E2EC", "#EDE7F5", "#D8D2EC"), 0.72, 0.82),
)


def current_palette(hour: int | None = None):
    """按时段返回 (名称, 配色, alpha 系数, 速度系数)；hour 便于离屏验证"""
    if hour is None:
        hour = QTime.currentTime().hour()
    for span, name, colors, alpha, speed in _TIME_PALETTES:
        if span is not None and hour in span:
            return name, colors, alpha, speed
        if span is None:
            return name, colors, alpha, speed
    return "白天", _PETAL_COLORS, 1.00, 1.00


# 固定种子保证每次启动花瓣分布一致（可预期、不会忽多忽少）
_RNG = random.Random(20261108)


def _petal_path() -> QPainterPath:
    """单位花瓣：上下尖、中部饱满的杏仁形，静态缓存"""
    path = QPainterPath()
    path.moveTo(0.0, -1.0)
    path.cubicTo(0.78, -0.62, 0.70, 0.52, 0.0, 1.0)
    path.cubicTo(-0.70, 0.52, -0.78, -0.62, 0.0, -1.0)
    path.closeSubpath()
    return path


_PETAL = _petal_path()


class AmbientDecor(QWidget):
    """常驻氛围层：缓慢飘落的花瓣（可在设置中即时开关）"""

    _TICK_MS = 33
    _PETAL_COUNT = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._enabled = is_enabled(FX_PETALS)
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._offset_ms = 0        # 累计暂停时长，让时间轴在隐藏期间冻结
        self._pause_start: int | None = None
        # 登场衔接：花瓣从 0 淡入到常态，登场环散开时正好接管画面
        self._fade_start: int | None = None
        self._fade_ms = 1800

        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self.update)

        # 固定花瓣参数：起始相位、横向位置、全程用时、横摆、旋转、尺寸、颜色
        self._petals = []
        for i in range(self._PETAL_COUNT):
            self._petals.append({
                "phase": i / self._PETAL_COUNT + _RNG.uniform(-0.05, 0.05),
                "xr": _RNG.uniform(0.10, 0.90),
                "dur": _RNG.uniform(9.0, 15.0),
                "sway": _RNG.uniform(10.0, 26.0),
                "freq": _RNG.uniform(0.35, 0.70),
                "rot": _RNG.uniform(-26.0, 26.0),
                "size": _RNG.uniform(11.0, 17.0),
                "color": QColor(_PETAL_COLORS[i % len(_PETAL_COLORS)]),
            })
        if not self._enabled:
            self.hide()

    # ---- 生命周期 ----

    def set_enabled(self, enabled: bool) -> None:
        """设置界面切换「飘落花瓣」时即时生效"""
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self._fade_start = None   # 手动打开立即全显，不重复走登场淡入
            self.start()
        else:
            self.pause()
            self.hide()
        self.update()

    def fade_in(self, ms: int = 1800) -> None:
        """登场时让花瓣从 0 渐显到常态：环散开后画面不会突然空掉。

        复用已有的 33ms 定时器，不新增常驻定时器；关闭花瓣开关时不生效。
        """
        if not self._enabled:
            return
        self._fade_ms = max(1, int(ms))
        self._fade_start = self._elapsed.elapsed()
        self.start()
        self.update()

    def _fade_factor(self) -> float:
        if self._fade_start is None:
            return 1.0
        t = (self._elapsed.elapsed() - self._fade_start) / self._fade_ms
        if t >= 1.0:
            self._fade_start = None
            return 1.0
        return max(0.0, min(1.0, t))

    def start(self) -> None:
        """开始 / 恢复氛围动画"""
        if not self._enabled:
            return
        if self._pause_start is not None:
            self._offset_ms += self._elapsed.elapsed() - self._pause_start
            self._pause_start = None
        if not self._timer.isActive():
            self._timer.start()
        if self.isHidden():       # showEvent 里再调 show 会递归，先判状态
            self.show()

    def pause(self) -> None:
        """窗口隐藏时停表；时间轴冻结，恢复后不跳变"""
        if self._timer.isActive():
            self._pause_start = self._elapsed.elapsed()
        self._timer.stop()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._enabled:
            self.start()

    def _t(self) -> float:
        """当前动画时间（秒），扣除隐藏期间"""
        now = self._pause_start if self._pause_start is not None else self._elapsed.elapsed()
        return max(0.0, (now - self._offset_ms) / 1000.0)

    # ---- 绘制 ----

    def _paint_petals(self, p: QPainter, t: float) -> None:
        """固定 7 片花瓣循环飘落：淡入淡出 + 正弦横摆 + 缓慢自转"""
        w, h = self.width(), self.height()
        # 按时段自动换色（花瓣自带效果，无独立开关）
        _name, colors, alpha_scale, speed = current_palette()
        fade = self._fade_factor()   # 登场衔接：整层从 0 渐显
        if fade <= 0:
            return
        for i, pt in enumerate(self._petals):
            prog = ((t * speed / pt["dur"]) + pt["phase"]) % 1.0
            y = -24.0 + prog * (h + 48.0)
            x = w * pt["xr"] + math.sin(t * pt["freq"] * math.tau + pt["phase"] * 9.0) * pt["sway"]
            # 两端各 12% 淡入淡出，循环无痕
            edge = min(1.0, prog / 0.12, (1.0 - prog) / 0.12)
            alpha = int(190 * alpha_scale * fade * max(0.0, edge))
            if alpha <= 0:
                continue
            color = QColor(colors[i % len(colors)])
            p.save()
            p.setOpacity(alpha / 255.0)
            p.translate(x, y)
            p.rotate(pt["rot"] * t + pt["phase"] * 360.0)
            s = pt["size"] * 0.5
            p.scale(s, s)
            p.setPen(QPen(QColor(242, 138, 150, int(alpha * 0.55)), 0.10))
            p.setBrush(color)
            p.drawPath(_PETAL)
            # 一点白色高光，让花瓣不是纯色片
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(QRectF(-0.22, -0.52, 0.20, 0.14))
            p.restore()

    def paintEvent(self, event) -> None:
        if not self._enabled:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_petals(p, self._t())
        p.end()
