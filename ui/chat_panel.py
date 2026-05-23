# -*- coding: utf-8 -*-
"""
聊天气泡面板
紧凑设计：输入框 + 最近消息气泡，像漫画对话框一样
固定在角色下方（窗口底部居中）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtGui import (
    QFont, QPainter, QColor, QLinearGradient, QBrush, QPen
)

from utils.logger import get_logger

logger = get_logger(__name__)

# 面板最大高度（px）
_MAX_PANEL_HEIGHT = 400
# 顶部淡出区域高度（px）：消息的底部进入此区域后开始变淡
# 值越大，淡出越平缓，越不容易出现"突然截断"的视觉效果
_FADE_ZONE = 150
# 完全超出顶部边界后自动删除的阈值（px）
_PRUNE_THRESHOLD = -30


class BubbleWidget(QWidget):
    """
    自定义气泡组件（QPainter 自绘 + 手动字符级换行 + 文本垂直居中）
    使用 widget 上下文中的 QFontMetrics 确保 DPI/字体完全一致，
    手动逐字符排版后逐行绘制，根治 Qt 文本引擎尺寸计算与渲染不一致的 bug。
    """

    def __init__(self, text: str, is_user: bool, max_width: int, parent=None):
        super().__init__(parent)
        self._is_user = is_user
        self._fade_opacity = 0.0
        self._position_opacity = 1.0
        self._raw_text = text
        self._font = QFont("Microsoft YaHei", 10)
        self.setFont(self._font)
        self._max_w = max_width
        self._pad_h = 10
        self._pad_v = 6

        if is_user:
            self._text_color = QColor("#1A3A5C")
            self._bg_start = QColor("#A0D8EF")
            self._bg_end = QColor("#7ECBF5")
        else:
            self._text_color = QColor("#333333")
            self._bg_start = QColor("#FFF5F5")
            self._bg_end = QColor("#FFE4E1")

        self._lines: list[str] = []
        self._compute_size()

    def set_fade_opacity(self, opacity: float) -> None:
        """淡入动画使用的透明度（0.0 → 1.0）"""
        self._fade_opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    def set_position_opacity(self, opacity: float) -> None:
        """根据在面板中的垂直位置计算的透明度（越靠上越淡）"""
        self._position_opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    # ---- 尺寸计算 ----

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """字符级换行"""
        fm = self.fontMetrics()
        lines: list[str] = []
        current = ""
        for ch in text:
            test = current + ch
            if fm.horizontalAdvance(test) > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = test
        if current:
            lines.append(current)
        return lines

    def _compute_size(self) -> None:
        fm = self.fontMetrics()
        content_max_w = self._max_w - self._pad_h * 2

        self._lines = self._wrap_text(self._raw_text, content_max_w)
        max_line_w = max(
            (fm.horizontalAdvance(line) for line in self._lines), default=0
        )
        line_h = fm.height()

        w = min(max_line_w + self._pad_h * 2, self._max_w)
        # +6px buffer，确保圆角和 descender 不被裁掉
        h = len(self._lines) * line_h + self._pad_v * 2 + 6
        self.setFixedSize(w, h)

    # ---- 绘制 ----

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        # 最终透明度 = 淡入动画透明度 × 位置淡出透明度
        painter.setOpacity(self._fade_opacity * self._position_opacity)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1) 圆角渐变背景（圆角半径 8px，避免 12px 与文本底部冲突）
        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, self._bg_start)
        gradient.setColorAt(1, self._bg_end)
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(0, 0, 0, 15), 1))
        painter.drawRoundedRect(rect, 8, 8)

        # 2) 多行纯文本（逐行绘制，垂直居中）
        painter.setPen(self._text_color)
        painter.setFont(self._font)
        fm = self.fontMetrics()
        line_h = fm.height()
        text_h = len(self._lines) * line_h
        available_h = self.height() - self._pad_v * 2
        start_y = self._pad_v + (available_h - text_h) / 2

        for i, line in enumerate(self._lines):
            baseline_y = start_y + i * line_h + fm.ascent()
            painter.drawText(self._pad_h, int(baseline_y), line)


class ChatPanel(QWidget):
    """
    聊天面板主组件（紧凑漫画风格）
    信号：
        - message_sent(str): 用户发送消息时触发
        - geometry_changed(): 面板高度变化时触发
    """

    message_sent = Signal(str)
    geometry_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._message_widgets: list[QWidget] = []
        self.setVisible(False)

    def _setup_ui(self) -> None:
        """初始化界面布局"""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setObjectName("ChatPanel")

        self._base_width = 280
        self._input_height = 40
        self.setFixedWidth(self._base_width)

        # 气泡最大宽度 = 面板宽度的 90%
        self._bubble_max_width = int(self._base_width * 0.9)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # 消息区域 —— 禁用自动布局，改为手动计算每条消息的 y 坐标
        # 这样可以根治 QBoxLayout 在空间不足时压缩 spacing 导致气泡重叠/间距变小的问题
        self._msg_layout = QVBoxLayout()
        self._msg_layout.setSpacing(4)
        self._msg_layout.setContentsMargins(2, 2, 2, 2)
        self._msg_layout.setEnabled(False)  # 禁用自动布局
        layout.addLayout(self._msg_layout)

        # 输入框外壳
        self._input_frame = QFrame(self)
        self._input_frame.setFixedHeight(40)
        self._input_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 20px;
            }
        """)
        frame_layout = QHBoxLayout(self._input_frame)
        frame_layout.setContentsMargins(12, 0, 12, 0)
        frame_layout.setSpacing(0)

        self._input = QLineEdit(self._input_frame)
        self._input.setPlaceholderText("跟葵酱说点什么吧~ ✨")
        self._input.returnPressed.connect(self._on_send)
        self._input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                outline: none;
                font-family: "Microsoft YaHei";
                font-size: 10pt;
                color: #333333;
            }
        """)
        frame_layout.addWidget(self._input)
        layout.addWidget(self._input_frame)

        # 初始高度 = 输入框 + layout spacing + msg layout 边距
        initial_h = (
            self._input_height
            + layout.spacing()
            + self._msg_layout.contentsMargins().top()
            + self._msg_layout.contentsMargins().bottom()
        )
        self.setFixedHeight(initial_h)

    def _on_send(self) -> None:
        """用户按下回车发送消息"""
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.add_message(text, is_user=True)
        self.message_sent.emit(text)

    def add_message(self, text: str, is_user: bool = False) -> None:
        """添加一条消息气泡到面板"""
        bubble = BubbleWidget(text, is_user, self._bubble_max_width)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        # 固定行高度 = 气泡高度，防止任何 layout 压缩气泡
        row.setFixedHeight(bubble.height())
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if is_user:
            row_layout.addStretch()
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch()

        # 存储布局高度（widget 首次显示前 height() 可能返回 0，不能依赖）
        row.setProperty("_layout_height", bubble.height())

        self._msg_layout.addWidget(row)
        self._message_widgets.append(row)

        QTimer.singleShot(0, lambda: self._finalize_message(row, bubble))
        logger.debug(f"添加{'用户' if is_user else 'AI'}消息: {text[:30]}...")

    def _finalize_message(self, row: QWidget, bubble: BubbleWidget) -> None:
        """layout 完成后的收尾：调整高度 → 手动排布 → 更新透明度 → 淡入动画"""
        new_height = self._adjust_height()
        self._relayout_messages(panel_height=new_height)
        self._update_opacity_by_position(panel_height=new_height)
        self.geometry_changed.emit()
        self._animate_appear(bubble)

    def _relayout_messages(self, panel_height: int | None = None) -> None:
        """
        手动计算每条消息/指示器的 y 坐标，从下往上排列，spacing 永远固定为 4px。
        这是根治 QBoxLayout 压缩 spacing 导致气泡重叠的核心手段。
        """
        if panel_height is None:
            panel_height = self.height()

        # 收集所有需要排布的 widget（消息 + 可选的打字指示器）
        widgets: list[QWidget] = list(self._message_widgets)
        if hasattr(self, "_typing_widget") and self._typing_widget is not None:
            widgets.append(self._typing_widget)

        if not widgets:
            return

        margin_top = self._msg_layout.contentsMargins().top()
        margin_bottom = self._msg_layout.contentsMargins().bottom()
        spacing = self._msg_layout.spacing()

        # 消息区域可用高度
        available_h = (
            panel_height
            - self._input_height
            - self.layout().spacing()
            - margin_top
            - margin_bottom
        )

        # 内容块从底部对齐：内容块底部 = margin_top + available_h
        content_bottom = margin_top + available_h
        current_bottom = content_bottom
        margin_left = self._msg_layout.contentsMargins().left()
        margin_right = self._msg_layout.contentsMargins().right()
        row_width = self.width() - margin_left - margin_right

        # 从下往上逐个设置 geometry（使用存储的高度，避免 height() 返回 0）
        for w in reversed(widgets):
            h = w.property("_layout_height")
            if h is None:
                h = w.height()
            y = current_bottom - h
            w.setGeometry(margin_left, int(y), row_width, h)
            current_bottom = y - spacing

    def _update_opacity_by_position(self, panel_height: int | None = None) -> None:
        """
        根据消息在面板中的垂直位置更新透明度。
        只有当消息总高度超出可用区域、顶部消息被推出边界后，才开始淡出。
        消息少的时候全部完全不透明；消息多到溢出后，越靠顶部的越淡。
        """
        if not self._message_widgets:
            return

        if panel_height is None:
            panel_height = self.height()

        # 计算消息总高度（不含打字指示器）
        msg_count = len(self._message_widgets)
        total_msg_h = 0
        for r in self._message_widgets:
            h = r.property("_layout_height")
            if h is None:
                h = r.height()
            total_msg_h += h
        if msg_count > 1:
            total_msg_h += (msg_count - 1) * self._msg_layout.spacing()

        # 计算消息区域的可用高度
        available_h = (
            panel_height
            - self._input_height
            - self.layout().spacing()
            - self._msg_layout.contentsMargins().top()
            - self._msg_layout.contentsMargins().bottom()
        )

        # 没有溢出：所有消息完全可见（opacity = 1）
        if total_msg_h <= available_h:
            for row in self._message_widgets:
                bubble = None
                for child in row.findChildren(BubbleWidget):
                    bubble = child
                    break
                if bubble:
                    bubble.set_position_opacity(1.0)
            return

        # 有溢出：顶部消息被推出边界，根据消息底部进入淡出区域的程度计算透明度
        to_remove: list[QWidget] = []
        fade_zone = _FADE_ZONE

        for row in self._message_widgets:
            bubble = None
            for child in row.findChildren(BubbleWidget):
                bubble = child
                break
            if bubble is None:
                continue

            y = row.y()
            h = row.property("_layout_height")
            if h is None:
                h = row.height()
            bottom = y + h  # 消息的底部坐标

            if bottom <= 0:
                # 完全在可见区域上方
                if y < _PRUNE_THRESHOLD:
                    to_remove.append(row)
                else:
                    bubble.set_position_opacity(0.0)
            elif bottom < fade_zone:
                # 底部进入顶部淡出区域，使用平方曲线让淡出更自然平缓
                ratio = max(0.0, bottom / fade_zone)
                bubble.set_position_opacity(ratio * ratio)
            else:
                # 在安全区域，完全可见
                bubble.set_position_opacity(1.0)

        for row in to_remove:
            if row in self._message_widgets:
                self._message_widgets.remove(row)
                self._do_remove(row)

        # 如果删除了消息，延迟重新排布并再次更新透明度
        if to_remove:
            QTimer.singleShot(0, lambda: self._relayout_and_update_opacity(panel_height))

    def _relayout_and_update_opacity(self, panel_height: int | None = None) -> None:
        """删除消息后重新排布并更新透明度"""
        if panel_height is None:
            panel_height = self.height()
        self._relayout_messages(panel_height)
        self._update_opacity_by_position(panel_height)

    def _animate_appear(self, bubble: BubbleWidget) -> None:
        """消息气泡淡入动画（0.0 → 1.0，300ms）"""
        if bubble is None:
            return
        anim = QVariantAnimation(bubble)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: bubble.set_fade_opacity(v))
        anim.start()

    def _do_remove(self, widget: QWidget) -> None:
        """从布局移除并销毁"""
        self._msg_layout.removeWidget(widget)
        widget.deleteLater()

    def _adjust_height(self) -> int:
        """
        根据消息数量动态调整面板高度，最大不超过 _MAX_PANEL_HEIGHT。
        返回计算出的新高度（供手动排布使用，因为 setFixedHeight 不会立即更新 self.height()）。
        """
        widgets = list(self._message_widgets)
        if hasattr(self, "_typing_widget") and self._typing_widget is not None:
            widgets.append(self._typing_widget)

        count = len(widgets)
        total_h = 0
        for w in widgets:
            h = w.property("_layout_height")
            if h is None:
                h = w.height()
            total_h += h
        if count > 1:
            total_h += (count - 1) * self._msg_layout.spacing()

        height = (
            self._input_height
            + total_h
            + self.layout().spacing()
            + self._msg_layout.contentsMargins().top()
            + self._msg_layout.contentsMargins().bottom()
        )
        new_height = min(height, _MAX_PANEL_HEIGHT)
        self.setFixedHeight(new_height)
        self.geometry_changed.emit()
        return new_height

    def show_typing_indicator(self) -> None:
        """显示 AI 正在输入的指示器（三个跳动小点）"""
        if hasattr(self, "_typing_widget") and self._typing_widget is not None:
            return
        self._typing_widget = QWidget()
        self._typing_widget.setStyleSheet("background: transparent;")
        # 固定指示器高度，避免 height() 返回 0
        self._typing_widget.setProperty("_layout_height", 14)
        layout = QHBoxLayout(self._typing_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._typing_dots: list[QLabel] = []
        for i in range(3):
            dot = QLabel("●")
            dot.setStyleSheet("color: #CCCCCC; font-size: 8px;")
            layout.addWidget(dot)
            self._typing_dots.append(dot)

        layout.addStretch()
        self._msg_layout.addWidget(self._typing_widget)

        new_height = self._adjust_height()
        self._relayout_messages(new_height)
        self.geometry_changed.emit()
        self._start_typing_animation()

    def _start_typing_animation(self) -> None:
        """启动输入指示器圆点波浪动画"""
        if not hasattr(self, "_typing_dots") or not self._typing_dots:
            return
        for i, dot in enumerate(self._typing_dots):
            anim = QVariantAnimation(dot)
            anim.setDuration(600)
            anim.setStartValue(0.3)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setLoopCount(-1)
            anim.valueChanged.connect(lambda v, d=dot: d.setWindowOpacity(v))
            QTimer.singleShot(i * 200, anim.start)
            dot.setProperty("_anim", anim)

    def hide_typing_indicator(self) -> None:
        """隐藏并销毁输入指示器"""
        if hasattr(self, "_typing_widget") and self._typing_widget is not None:
            if hasattr(self, "_typing_dots"):
                for dot in self._typing_dots:
                    anim = dot.property("_anim")
                    if anim:
                        anim.stop()
            self._msg_layout.removeWidget(self._typing_widget)
            self._typing_widget.deleteLater()
            self._typing_widget = None
            self._typing_dots = []
            new_height = self._adjust_height()
            self._relayout_messages(new_height)
            self.geometry_changed.emit()

    def toggle_visibility(self) -> None:
        """切换显示/隐藏"""
        self.setVisible(not self.isVisible())

    def showEvent(self, event) -> None:
        """显示时自定位到父窗口底部居中，并聚焦输入框"""
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            cx = (parent.width() - self.width()) // 2
            cy = parent.height() - self.height() - 10
            self.move(cx, max(cy, 0))
            self.raise_()
        self._input.setFocus()
