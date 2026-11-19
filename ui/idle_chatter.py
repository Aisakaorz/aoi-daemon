# -*- coding: utf-8 -*-
"""
说话气泡 / 自定义说话反馈（v0.1.31 / C 版）

葵酱冒一句小气泡说话，两类短句共用同一个 Qt 层自绘气泡，全部自绘，
不触碰 Live2D 渲染与聊天气泡布局：

- 待机自语（动作驱动）：跟着状态机的自动轮播一起出现 —— 每 10~15 秒
  自动播放动作时冒一句，不再单独计时。约 30% 说与该动作适配的短句，
  其余仍走 24 句通用池（一轮不重复、跨轮首句≠上轮末句）+ 亲近句 /
  满值句 / 话题句。显示 4.2s；好感档位越高越容易抽到亲近句。
- 交互短句：摸头 / 点身体 / 思考 / 回复时冒一句更短的口语反馈，
  5 类各 5 句，显示 2.0s，气泡更靠上、描边稍重，由主窗口事件触发
  （不改动 StateMachine 已有的状态回调）。
- 久别问候：启动时由 say() 指定文案说一句，同样受总开关控制。
- 话题记忆：由 core.companion 下发最近聊到的话题词，偶尔接上一句；
  刚聊完则下一次自动动作时优先说。仍归「说话气泡」总开关，
  不新增设置项、不新增定时器。

要点：
- 两者本质是同一件事「葵酱说句话」，合并为**一个开关**；开关重新打开时
  由 preview() 立即冒一句，不用等下一次动作就能确认效果。
- 不再有独立的自语定时器：动作回调直接触发；气泡显示期间才用 33ms
  墙钟驱动淡入淡出，空闲时完全停表。
- WA_TransparentForMouseEvents，不抢桌面 / 角色点击。
- 组件常驻为透明覆盖层：只靠 _visible 控制绘制，不能 hide 自己，
  否则真机上永远不冒泡（v0.1.31 修过的坑）。
"""
import math
import random
import time

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

# 好感高了才会渐渐出现的「亲近」句：不新增界面，只让语句池慢慢变
_CLOSE_LINES = (
    "今天也一直陪着我呀", "你回来我就安心了", "和你待着最舒服了~",
    "不用说点什么也很好呢", "明天的直播间也给你留位置", "嘿嘿，越来越熟悉啦",
    "又一起过了一天呢", "这种安静的下午真好",
)

# 好感满值后解锁的专属句：满值不是终点，仍有新的话可说
_MAX_LINES = (
    "今天也最喜欢你了", "以后也要一直在一起哦",
    "你是我最安心的角落", "这份心情我记了好久好久",
)

# 交互短句：短、口语、带语气，避免和待机自语句式重复
_EMOTES = {
    "head": ("嘿嘿~", "痒痒的…", "摸摸头♪", "诶嘿！", "头上有小花吗？"),
    "body": ("呀！", "噗——", "别戳啦~", "吓我一跳", "嘻嘻"),
    "think": ("嗯…让我想想", "…？", "容我想一下", "唔……", "稍等哦"),
    "reply": ("好啦~", "这样吗？", "说完啦", "嗯嗯！", "收到~"),
    "greet": ("我来啦~", "早上好呀", "今天也在哦", "嗨——", "上线啦♪"),
}

# 话题记忆：把最近聊到的短词套进待机自语，文案克制、只留 5 句
_TOPIC_LINES = (
    "刚才聊到 {w} 了呢", "{w}…我还在想哦", "你说过 {w}，我记着呢",
    "关于 {w}，还想再听一点~", "{w} 这个词，悄悄记下来啦",
)
_TOPIC_CHANCE = 0.18          # 通用语句之外，话题句的低频出现概率
_TOPIC_IMMEDIATE_GAP = 60.0   # 「刚聊完必说一次」的冷却（秒，进程内）
_TOPIC_MAX_WORDS = 6          # 与 core.companion 的 _TOPIC_MAX 对齐

# 动作适配的短句：只占约三成，其余仍走通用池 / 亲近句 / 满值句 / 话题句
_MOTION_LINES = {
    "idle": ("悄悄换了个姿势~", "正在发呆中…别叫我"),
    "shake": ("咦？刚才想到什么来着", "摇摇头，把困意甩掉~"),
    "pinch_in": ("唔…脸颊被捏到了", "别捏啦~会鼓起来的"),
    "pinch_out": ("呼——松手啦", "嘿嘿，脸还圆吗？"),
    "tap_body": ("呀，被戳到了", "痒痒的…别闹啦"),
}
_MOTION_LINE_CHANCE = 0.30    # 抽到动作专属句的概率

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
        self._paused = False          # 主窗口隐藏时不接受动作联动
        self._shown = QElapsedTimer()
        self._shown.start()
        self._text = ""
        self._visible = False
        self._mode = "idle"          # idle / emote
        self._tier = "shy"           # shy / warm / close（由 core.companion 下发）
        self._max = False            # 好感满值，解锁专属语句池
        self._show_seconds = _SHOW_SECONDS
        self._side = 1               # 气泡在角色左侧 / 右侧交替
        self._queue: list[str] = []
        self._last_line: str | None = None
        self._topics: list[str] = []      # 最近聊到的话题词（由 companion 下发）
        self._topic_next = False          # 刚聊完：下一次自动动作优先说话题句
        self._topic_last_at = 0.0         # time.monotonic()，即时反馈冷却

        # 只在气泡显示期间重绘；空闲时完全停表（不再有独立自语定时器）
        self._paint_timer = QTimer(self)
        self._paint_timer.setInterval(33)
        self._paint_timer.timeout.connect(self.update)
        # 组件常驻为透明覆盖层：只靠 _visible 控制绘制，绝不 hide 自己
        self.show()

    # ---- 开关与活动 ----

    def set_enabled(self, enabled: bool) -> None:
        """「说话气泡」总开关：同时控制动作联动自语与交互短句"""
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if not enabled:
            self._hide_current()   # 无论当前是自语还是交互短句，一律收起
        self.update()

    def note_activity(self) -> None:
        """用户发消息 / 点击角色时调用：收起当前气泡，让位给交互短句"""
        if self._visible:
            self._hide_current()

    def pause(self) -> None:
        """主窗口隐藏：停掉重绘，并暂停接受动作联动"""
        self._paused = True
        self._paint_timer.stop()

    def resume(self) -> None:
        """主窗口重新显示：恢复联动（收起可能残留的气泡）"""
        self._paused = False
        self.note_activity()

    # ---- 语句抽取与即时预览 ----

    def set_tier(self, tier: str) -> None:
        """由陪伴记忆下发好感档位，只影响之后抽取的语句池"""
        if tier in ("shy", "warm", "close"):
            self._tier = tier
            self._queue.clear()   # 换档后重建池，让新句子有机会立刻出现

    def set_max(self, reached: bool) -> None:
        """由 core.companion.is_max() 下发；满值时混入专属语句池"""
        reached = bool(reached)
        if reached != self._max:
            self._max = reached
            self._queue.clear()

    def say(self, text: str, seconds: float = _SHOW_SECONDS) -> None:
        """外部指定文案说一句（久别问候等），同样受「说话气泡」总开关控制"""
        if not self._enabled or not text:
            return
        self._present(text, "idle", seconds)

    def _line_pool(self) -> list[str]:
        """通用句 + 按档位混入的亲近句；亲近句重复几次即提高权重"""
        pool = list(_LINES)
        if self._tier == "warm":
            pool += list(_CLOSE_LINES[:3])
        elif self._tier == "close":
            pool += list(_CLOSE_LINES) + list(_CLOSE_LINES[:4])
        if self._max:
            pool += list(_MAX_LINES)
        return pool

    def set_topics(self, words, *, immediate: bool = False) -> None:
        """由 core.companion 下发最近话题词。

        启动恢复用 immediate=False（不冒旧话题）；用户发消息后用
        immediate=True（下一次待机自语优先接上，60s 内最多一次，
        避免连发消息把气泡刷成话题播报）。
        """
        self._topics = [str(w) for w in (words or [])
                        if isinstance(w, str) and w][:_TOPIC_MAX_WORDS]
        self._queue.clear()
        if immediate and self._topics:
            now = time.monotonic()
            if now - self._topic_last_at >= _TOPIC_IMMEDIATE_GAP:
                self._topic_next = True
                self._topic_last_at = now

    def _topic_line(self) -> str:
        """随机取一个话题词套一句模板；只用于待机自语，交互短句不受影响"""
        if not self._topics:
            return ""
        return random.choice(_TOPIC_LINES).format(w=random.choice(self._topics))

    def _next_line(self) -> str:
        """洗牌队列：一轮内不重复，且新一轮首句不与上一轮末句相同。

        话题句在通用队列之外按概率插入：刚聊完必说一次，之后低频出现，
        不进队列、不影响通用句的洗牌节奏。
        """
        if self._topics and (self._topic_next or random.random() < _TOPIC_CHANCE):
            self._topic_next = False
            line = self._topic_line()
            if line and line != self._last_line:
                self._last_line = line
                return line
        if not self._queue:
            pool = self._line_pool()
            if self._last_line in pool:
                pool.remove(self._last_line)
            random.shuffle(pool)
            self._queue = pool
        line = self._queue.pop()
        self._last_line = line
        return line

    def on_auto_motion(self, group: str, no: int = 0) -> None:
        """状态机自动轮播动作时调用：让说话与动作同时发生。

        只在开关打开、窗口可见、且当前没有气泡时说一句；交互动作不走这里，
        因此不会和 show_emote 打架。
        """
        if not self._enabled or self._paused or self._visible:
            return
        self._present(self._line_for_motion(group), "idle", _SHOW_SECONDS)

    def _line_for_motion(self, group: str) -> str:
        """约三成说与动作适配的短句，其余仍走通用池（含话题记忆）。

        刚聊完时优先让 _next_line() 消费话题句，避免被专属句挤掉。
        """
        if self._topic_next or random.random() >= _MOTION_LINE_CHANCE:
            return self._next_line()
        pool = [x for x in _MOTION_LINES.get(group, ()) if x != self._last_line]
        if not pool:
            return self._next_line()
        line = random.choice(pool)
        self._last_line = line
        return line

    def preview(self) -> None:
        """设置里重新打开「说话气泡」时立即冒一句 greet 短句，不用等下一次动作"""
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

    # ---- 状态 ----

    def _hide_current(self) -> None:
        self._visible = False
        self._paint_timer.stop()
        self.update()
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

        # 微信式侧边小尾巴：朝向角色的一侧（_side=1 气泡在右 → 尾巴在左）。
        # 与主体做布尔并集后一次绘制，填充与描边共用同一条外轮廓，
        # 不会出现底部三角与圆角矩形两层叠加时描边横穿接缝的拼接感。
        tw, th = 6.0, 9.0
        ty = rect.top() + 8.0
        tip_y = ty + th * 0.38
        tail = QPainterPath()
        if self._side > 0:
            tail.moveTo(rect.left() + 1.5, ty)
            tail.lineTo(rect.left() - tw, tip_y)
            tail.lineTo(rect.left() + 1.5, ty + th)
        else:
            tail.moveTo(rect.right() - 1.5, ty)
            tail.lineTo(rect.right() + tw, tip_y)
            tail.lineTo(rect.right() - 1.5, ty + th)
        tail.closeSubpath()
        shape = QPainterPath()
        shape.addRoundedRect(rect, 12, 12)
        shape = shape.united(tail)

        # 奶油渐变圆角气泡 + 珊瑚粉细描边（交互短句描边稍重，区分两种短句）
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0.0, QColor("#FFFBF8"))
        grad.setColorAt(1.0, QColor("#FFE6E2" if emote else "#FFF0EA"))
        p.setBrush(grad)
        p.setPen(QPen(QColor(242, 102, 139, 175 if emote else 130), 1.4 if emote else 1.2))
        p.drawPath(shape)

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
