# -*- coding: utf-8 -*-
"""
说话气泡 / 自定义说话反馈（v0.1.31 / C 版）

葵酱冒一句小气泡说话，两类短句共用同一个 Qt 层自绘气泡，全部自绘，
不触碰 Live2D 渲染与聊天气泡布局：

- 待机自语：空闲一会儿后冒一句随机短句，像 VTuber 待机时自言自语。
  24 句语句池 + 洗牌队列（一轮不重复、跨轮首句≠上轮末句），显示 4.2s。
- 交互短句：摸头 / 点身体 / 思考 / 回复时冒一句更短的口语反馈，
  5 类各 5 句，显示 2.0s，气泡更靠上、描边稍重，由主窗口事件触发
  （不改动 StateMachine 已有的状态回调）。

要点：
- 两者本质是同一件事「葵酱说句话」，合并为**一个开关**；开关重新打开时
  由 preview() 立即冒一句，不用等空闲计时就能确认效果。
- 低频 1s 空闲检查；气泡显示期间才用 33ms 墙钟驱动淡入淡出，空闲停表。
- WA_TransparentForMouseEvents，不抢桌面 / 角色点击。
- 组件常驻为透明覆盖层：只靠 _visible 控制绘制，不能 hide 自己，
  否则真机上永远不冒泡（v0.1.31 修过的坑）。
"""
import math
import random

from PySide6.QtCore import Qt, QRectF, QElapsedTimer, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QLinearGradient
from PySide6.QtWidgets import QWidget

from ui.effect_settings import FX_IDLE_CHATTER, is_enabled
from utils.font_manager import cute_font

# 语句池：分主题写开，避免句式雷同；洗牌后逐句取，一轮内不重复
_LINES = (
    "今天也要元气满满呢~", "主人还在忙吗？", "窗外的天气好像不错…",
    "嘿嘿，被你发现我在发呆了", "要不要一起听首歌？", "我悄悄数了下云朵",
    "桌面好安静呀…", "突然想伸个懒腰~", "有你在就安心了",
    "刚才那句话我记下来啦", "摸摸头会有好运哦", "呼——有点困了",
    "今天的我也有好好待机", "主人记得喝水哦", "蝴蝶飞过去了吗？",
    "我在练习新的打招呼方式", "阳光晒得暖暖的", "悄悄许了个小愿望",
    "要不要聊点什么？", "我把花瓣数到第七片了", "嗯…就这样待着也很好",
    "啊，刚刚走神了一秒", "今天的直播间也很安静", "等你回来再说给你听~",
)

# 交互短句：短、口语、带语气，避免和待机自语句式重复
_EMOTES = {
    "head": ("嘿嘿~", "痒痒的…", "摸摸头♪", "诶嘿！", "头上有小花吗？"),
    "body": ("呀！", "噗——", "别戳啦~", "吓我一跳", "嘻嘻"),
    "think": ("嗯…让我想想", "…？", "容我想一下", "唔……", "稍等哦"),
    "reply": ("好啦~", "这样吗？", "说完啦", "嗯嗯！", "收到~"),
    "greet": ("我来啦~", "早上好呀", "今天也在哦", "嗨——", "上线啦♪"),
}

_IDLE_SECONDS = 10.0     # 空闲多久后第一次冒泡（原 22s 太难等到）
_GAP_SECONDS = 18.0      # 两次之间的最短间隔（原 34s）
_SHOW_SECONDS = 4.2      # 待机单句显示时长
_EMOTE_SECONDS = 2.0     # 交互短句更短促
_FADE = 0.32             # 淡入 / 淡出时长


class IdleChatter(QWidget):
    """说话气泡共用层：待机自语 / 交互短句共用，覆盖整窗但只在气泡附近绘制"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._enabled = is_enabled(FX_IDLE_CHATTER)
        self._activity = QElapsedTimer()
        self._activity.start()
        self._shown = QElapsedTimer()
        self._shown.start()
        self._text = ""
        self._visible = False
        self._mode = "idle"          # idle / emote
        self._show_seconds = _SHOW_SECONDS
        self._side = 1               # 气泡在角色左侧 / 右侧交替
        self._queue: list[str] = []
        self._last_line: str | None = None
        self._next_at = _IDLE_SECONDS

        # 低频检查（1s），不占高频刷新
        self._check_timer = QTimer(self)
        self._check_timer.setInterval(1000)
        self._check_timer.timeout.connect(self._check)
        # 显示期间的淡入淡出重绘，空闲即停表
        self._paint_timer = QTimer(self)
        self._paint_timer.setInterval(33)
        self._paint_timer.timeout.connect(self.update)
        if self._enabled:
            self._check_timer.start()
        # 组件常驻为透明覆盖层：只靠 _visible 控制绘制，绝不 hide 自己
        self.show()

    # ---- 开关与活动 ----

    def set_enabled(self, enabled: bool) -> None:
        """「说话气泡」总开关：同时控制待机自语与交互短句"""
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self.note_activity()
            self._check_timer.start()
        else:
            self._check_timer.stop()
            self._hide_current()   # 无论当前是自语还是交互短句，一律收起
        self.update()

    def note_activity(self) -> None:
        """用户发消息 / 点击角色时调用：重置空闲计时并收起当前气泡"""
        self._activity.restart()
        self._next_at = _IDLE_SECONDS
        if self._visible:
            self._hide_current()
            self._next_at = _IDLE_SECONDS

    def pause(self) -> None:
        """主窗口隐藏：停掉检查与重绘，不空转"""
        self._check_timer.stop()
        self._paint_timer.stop()

    def resume(self) -> None:
        """主窗口重新显示：恢复计时（视为一次活动）"""
        self.note_activity()
        if self._enabled:
            self._check_timer.start()

    # ---- 语句抽取与即时预览 ----

    def _next_line(self) -> str:
        """洗牌队列：一轮内不重复，且新一轮首句不与上一轮末句相同"""
        if not self._queue:
            pool = list(_LINES)
            if self._last_line in pool:
                pool.remove(self._last_line)
            random.shuffle(pool)
            self._queue = pool
        line = self._queue.pop()
        self._last_line = line
        return line

    def preview(self) -> None:
        """设置里重新打开「说话气泡」时立即冒一句 greet 短句，不用等 10 秒"""
        if not self._enabled:
            return
        self._present(random.choice(_EMOTES["greet"]), "emote", _EMOTE_SECONDS)

    def show_emote(self, kind: str) -> None:
        """交互短句：由主窗口事件触发（head / body / think / reply / greet）"""
        if not self._enabled or kind not in _EMOTES:
            return
        self._present(random.choice(_EMOTES[kind]), "emote", _EMOTE_SECONDS)

    def _present(self, text: str, mode: str, seconds: float) -> None:
        self._text = text
        self._mode = mode
        self._show_seconds = seconds
        self._visible = True
        self._shown.restart()
        self._side = -self._side
        self._paint_timer.start()
        self.update()

    # ---- 计时 ----

    def _check(self) -> None:
        if not self._enabled or self._visible:
            return
        if self._activity.elapsed() / 1000.0 >= self._next_at:
            self._present(self._next_line(), "idle", _SHOW_SECONDS)

    def _hide_current(self) -> None:
        self._visible = False
        self._paint_timer.stop()
        self.update()
        self._activity.restart()
        self._next_at = _GAP_SECONDS if self._mode == "idle" else _IDLE_SECONDS
        self._mode = "idle"

    # ---- 绘制 ----

    def _bubble_rect(self) -> QRectF:
        font = cute_font(9)
        w = min(self.width() - 32, self._text_width(font) + 26)
        h = 28.0 if self._mode == "emote" else 30.0
        cx = self.width() * 0.5 + self._side * min(self.width() * 0.26, 92)
        x = max(8.0, min(self.width() - w - 8.0, cx - w / 2))
        y = self.height() * (0.16 if self._mode == "emote" else 0.20)
        return QRectF(x, y, w, h)

    def _text_width(self, font: QFont) -> int:
        from PySide6.QtGui import QFontMetrics
        return int(QFontMetrics(font).horizontalAdvance(self._text))

    def paintEvent(self, event) -> None:
        if not self._visible or not self._text:
            return
        t = self._shown.elapsed() / 1000.0
        if t >= self._show_seconds:
            self._hide_current()
            return
        alpha = max(0.0, min(1.0, t / _FADE, (self._show_seconds - t) / _FADE))
        rect = self._bubble_rect()
        emote = self._mode == "emote"
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(alpha)

        # 小尾巴（指向角色）
        tail = QPainterPath()
        tip_x = rect.center().x() - self._side * rect.width() * 0.28
        tail.moveTo(tip_x - 5, rect.bottom() - 1)
        tail.lineTo(tip_x + 5, rect.bottom() - 1)
        tail.lineTo(tip_x, rect.bottom() + 7)
        tail.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFF0EA"))
        p.drawPath(tail)

        # 奶油渐变圆角气泡 + 珊瑚粉细描边（交互短句描边稍重，区分两种短句）
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0.0, QColor("#FFFBF8"))
        grad.setColorAt(1.0, QColor("#FFE6E2" if emote else "#FFF0EA"))
        p.setBrush(grad)
        p.setPen(QPen(QColor(242, 102, 139, 175 if emote else 130), 1.4 if emote else 1.2))
        p.drawRoundedRect(rect, 12, 12)

        p.setFont(cute_font(9))
        p.setPen(QColor("#8A5A55"))
        p.drawText(rect.adjusted(10, 0, -10, 0),
                   Qt.AlignmentFlag.AlignCenter, self._text)

        # 气泡角上一颗小四角星点缀
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 200, 160, int(200 * alpha)))
        star = QPainterPath()
        for i in range(8):
            r = 3.0 if i % 2 == 0 else 0.9
            a = -math.pi / 2 + i * math.pi / 4
            sx, sy = rect.right() - 2 + r * math.cos(a), rect.top() + 2 + r * math.sin(a)
            if i == 0:
                star.moveTo(sx, sy)
            else:
                star.lineTo(sx, sy)
        star.closeSubpath()
        p.drawPath(star)
        p.end()
