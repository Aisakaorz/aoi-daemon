# -*- coding: utf-8 -*-
"""
聊天气泡面板
紧凑设计：输入框 + 最近消息气泡，像漫画对话框一样
固定在角色下方（窗口底部居中）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame, QDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer, QVariantAnimation, QEasingCurve, QEvent, QDateTime, QPoint, QRect
from PySide6.QtGui import (
    QFont, QPainter, QColor, QLinearGradient, QBrush, QPen, QRegion
)

from utils.logger import get_logger

logger = get_logger(__name__)

# 面板最大高度（px）
_MAX_PANEL_HEIGHT = 400

# 消息区域布局常量
_MSG_MARGIN = 2
_MSG_SPACING = 4
# 顶部淡出区域高度（px）：消息的底部进入此区域后开始变淡
# 值越大，淡出越平缓，越不容易出现"突然截断"的视觉效果
_FADE_ZONE = 150

# 角色底部占窗口高度的比例（与 main_window.py 保持一致）
_CHARACTER_BOTTOM_RATIO = 0.955


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

    def update_max_width(self, max_width: int) -> None:
        """更新最大宽度并重新计算尺寸（用于角色大小缩放时同步调整气泡）"""
        if max_width == self._max_w:
            return
        self._max_w = max_width
        self._compute_size()
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
        self._scroll_offset = 0  # 手动滚动偏移量（负数=向上滚动查看历史）
        self._setup_ui()
        self._setup_download_tracking()
        self._message_widgets: list[QWidget] = []
        self.setVisible(False)
        # 面板最大高度占父窗口高度的比例（随角色大小同步缩放）
        self._max_height_ratio = 0.65
        # 初始化语音转文字（失败时静默降级）
        try:
            from voice.stt_provider import STTProvider
            self._stt = STTProvider()
        except Exception as e:
            logger.warning(f"STT 初始化失败: {e}")
            self._stt = None

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

        # 语音按钮提示消息通过 add_message 显示（与长按时间过短保持一致）

        # 消息区域 —— 保留 QVBoxLayout 作为容器（启用状态，否则气泡不可见）
        # 用 _scroll_offset 实现手动滚动，_relayout_messages 在 LayoutRequest 时覆盖自动布局
        self._msg_layout = QVBoxLayout()
        self._msg_layout.setSpacing(_MSG_SPACING)
        self._msg_layout.setContentsMargins(_MSG_MARGIN, _MSG_MARGIN, _MSG_MARGIN, _MSG_MARGIN)
        layout.addLayout(self._msg_layout, stretch=1)

        # 跳到底部按钮（滚动到上方历史时显示）
        self._scroll_to_bottom_btn = QLabel("▼", self)
        self._scroll_to_bottom_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_to_bottom_btn.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 248, 243, 0.95);
                color: #4A3F3A;
                border: 1.5px solid rgba(255, 170, 160, 0.75);
                border-radius: 6px;
                font-size: 9pt;
                font-family: "Microsoft YaHei";
            }
            QLabel:hover {
                background-color: rgba(255, 230, 225, 0.98);
                border: 1.5px solid rgba(255, 140, 130, 0.9);
            }
        """)
        self._scroll_to_bottom_btn.setFixedSize(24, 20)
        self._scroll_to_bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scroll_to_bottom_btn.hide()
        self._scroll_to_bottom_btn.mousePressEvent = lambda e: self._scroll_to_bottom() if e.button() == Qt.MouseButton.LeftButton else None

        # 输入框外壳（galgame 风格：半透明暗色底 + 暖色边框）
        self._input_frame = QFrame(self)
        self._input_frame.setFixedHeight(40)
        self._update_input_frame_style(focused=False)

        frame_layout = QHBoxLayout(self._input_frame)
        frame_layout.setContentsMargins(8, 0, 12, 0)
        frame_layout.setSpacing(6)

        # 语音转文字按钮
        self._voice_btn = ChatPanel._VoiceButton(self._input_frame)
        self._voice_btn.long_press_confirmed.connect(self._on_voice_long_press)
        self._voice_btn.press_released.connect(self._on_voice_released)
        frame_layout.addWidget(self._voice_btn)

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
                color: #4A3F3A;
            }
            QLineEdit::placeholder {
                color: rgba(140, 130, 125, 0.55);
            }
        """)
        self._input.installEventFilter(self)
        frame_layout.addWidget(self._input)
        layout.addWidget(self._input_frame)

        # 下载进度外壳（与输入框布局一致：左按钮 + 右详情，背景叠加进度）
        self._download_frame = QFrame(self)
        self._download_frame.setFixedHeight(40)

        dl_layout = QHBoxLayout(self._download_frame)
        dl_layout.setContentsMargins(8, 0, 12, 0)
        dl_layout.setSpacing(6)

        # 左侧：下载图标（28x28，和语音按钮一致）
        self._dl_icon = ChatPanel._DownloadIcon(self._download_frame)
        self._dl_icon.clicked.connect(self._on_cancel_download_clicked)
        dl_layout.addWidget(self._dl_icon)

        # 中间：下载详情（替代 QLineEdit）
        self._download_detail = QLabel("", self._download_frame)
        self._download_detail.setStyleSheet("""
            font-family: "Microsoft YaHei";
            font-size: 10pt;
            color: #4A3F3A;
            background: transparent;
            border: none;
        """)
        dl_layout.addWidget(self._download_detail, stretch=1)

        self._download_frame.hide()
        layout.addWidget(self._download_frame)

        # 初始高度 = 输入框 + layout spacing
        initial_h = self._input_height + layout.spacing()
        self.setFixedHeight(initial_h)

    def set_panel_width(self, width: int) -> None:
        """调整面板宽度（用于角色大小缩放时同步调整）"""
        self._base_width = width
        self._bubble_max_width = int(width * 0.9)

        # 同步更新所有已有气泡的换行和尺寸
        for row in self._message_widgets:
            bubble = None
            for child in row.findChildren(BubbleWidget):
                bubble = child
                break
            if bubble is not None:
                bubble.update_max_width(self._bubble_max_width)
                new_h = bubble.height()
                row.setFixedHeight(new_h)
                row.setProperty("_layout_height", new_h)

        # 重新计算面板总高度，然后一次性设置宽高（只触发一次 resizeEvent）
        new_height = self._adjust_height()
        self.setFixedSize(width, new_height)
        # 重新计算透明度（消息数量/高度变化后可能溢出）
        self._update_opacity_by_position()

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

        # 确保输入框始终在最上层，不被消息气泡遮挡
        self._input_frame.raise_()

        QTimer.singleShot(0, lambda: self._finalize_message(row, bubble))
        logger.debug(f"添加{'用户' if is_user else 'AI'}消息: {text[:30]}...")

    def _finalize_message(self, row: QWidget, bubble: BubbleWidget) -> None:
        """layout 完成后的收尾：调整高度 → 手动排布 → 更新透明度 → 淡入动画"""
        self._adjust_height()
        self._relayout_messages()
        self._update_opacity_by_position()
        self.geometry_changed.emit()
        self._animate_appear(bubble)

    def _relayout_messages(self, panel_height: int | None = None) -> None:
        """
        手动计算每条消息/指示器的 y 坐标，从下往上排列。
        使用 _scroll_offset 支持滚轮滚动查看历史消息。
        """
        if panel_height is None:
            panel_height = self.height()

        widgets: list[QWidget] = list(self._message_widgets)
        if hasattr(self, "_typing_widget") and self._typing_widget is not None:
            widgets.append(self._typing_widget)

        if not widgets:
            return

        margin_top = self._msg_layout.contentsMargins().top()
        margin_bottom = self._msg_layout.contentsMargins().bottom()
        spacing = self._msg_layout.spacing()

        available_h = (
            panel_height
            - self._input_height
            - self.layout().spacing()
            - margin_top
            - margin_bottom
        )
        content_bottom = margin_top + available_h + self._scroll_offset
        current_bottom = content_bottom
        margin_left = self._msg_layout.contentsMargins().left()
        margin_right = self._msg_layout.contentsMargins().right()
        row_width = self.width() - margin_left - margin_right

        for w in reversed(widgets):
            h = w.property("_layout_height")
            if h is None:
                h = w.height()
            y = current_bottom - h
            w.setGeometry(margin_left, int(y), row_width, h)
            current_bottom = y - spacing

    def _update_opacity_by_position(self) -> None:
        """
        顶部透明化规则：
        - 消息堆叠高度未进入顶部 150px 透明区域时，全部不透明
        - 进入后，顶部消息按 (bottom/150)² 渐变淡出
        底部规则：只用 mask 硬截断，不再透明化
        """
        if not self._message_widgets:
            return

        margin_top = self._msg_layout.contentsMargins().top()
        margin_bottom = self._msg_layout.contentsMargins().bottom()
        available_h = (
            self.height()
            - self._input_height
            - self.layout().spacing()
            - margin_top
            - margin_bottom
        )
        # 底部 mask 截断边界 = 输入框顶部下方 5px
        clip_y = self.height() - self._input_height + 5

        # 计算消息总高度（含打字指示器）
        total_msg_h = self._get_total_content_height()

        # 计算固定的底部不透明区域阈值：
        # 基于最大面板高度下的最大消息区域，减去最大透明化区域 150px
        max_available_h = (
            self._get_max_panel_height()
            - self._input_height
            - self.layout().spacing()
            - margin_top
            - margin_bottom
        )
        threshold = max(0, max_available_h - _FADE_ZONE)

        # 消息堆叠未超过底部不透明区域：全部不淡出，确保所有行可见
        if total_msg_h <= threshold:
            for row in self._message_widgets:
                row.show()
                bubble = self._find_bubble(row)
                if bubble:
                    bubble.set_position_opacity(1.0)
                    bubble.clearMask()
            return

        # 透明化区域大小 = 超出 threshold 的部分，最大不超过 150px
        # 随着消息增多，fade_zone 从 0 慢慢增长到 150
        fade_zone = min(total_msg_h - threshold, _FADE_ZONE)

        for row in self._message_widgets:
            bubble = self._find_bubble(row)
            if bubble is None:
                continue

            h = row.property("_layout_height")
            if h is None:
                h = row.height()
            top = row.y()
            bottom = top + h

            # 顶部淡出：消息底部进入 0~150px 区域时渐变
            if bottom <= 0:
                opacity = 0.0
            elif bottom < fade_zone:
                ratio = max(0.0, bottom / fade_zone)
                opacity = ratio * ratio
            else:
                opacity = 1.0

            # 底部：硬截断
            if bottom > clip_y:
                visible_h = max(0, clip_y - top)
                if visible_h > 0:
                    # 气泡部分跨越截断线：mask 只保留上方可见区域
                    bubble.setMask(QRegion(0, 0, bubble.width(), visible_h))
                    row.show()
                else:
                    # 气泡完全在截断线下方：隐藏整行
                    row.hide()
            elif top >= clip_y:
                # 气泡完全在截断线下方：隐藏整行
                row.hide()
            else:
                # 气泡完全在截断线上方：清除 mask，确保可见
                bubble.clearMask()
                row.show()

            bubble.set_position_opacity(opacity)

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

    def _get_total_content_height(self) -> int:
        """计算消息区域总高度（含打字指示器）"""
        total_h = 0
        for w in self._message_widgets:
            h = w.property("_layout_height")
            if h is None:
                h = w.height()
            total_h += h
        if len(self._message_widgets) > 1:
            total_h += (len(self._message_widgets) - 1) * self._msg_layout.spacing()
        if hasattr(self, "_typing_widget") and self._typing_widget is not None:
            th = self._typing_widget.property("_layout_height")
            if th is None:
                th = self._typing_widget.height()
            total_h += th + self._msg_layout.spacing()
        return total_h

    def _find_bubble(self, row: QWidget) -> BubbleWidget | None:
        """从消息行中查找气泡组件"""
        for child in row.findChildren(BubbleWidget):
            return child
        return None

    def _adjust_height(self) -> int:
        """
        根据消息数量动态调整面板高度，最大不超过 _MAX_PANEL_HEIGHT。
        """
        total_h = self._get_total_content_height()

        height = (
            self._input_height
            + total_h
            + self.layout().spacing()
            + self._msg_layout.contentsMargins().top()
            + self._msg_layout.contentsMargins().bottom()
        )
        new_height = min(height, self._get_max_panel_height())
        self.setFixedHeight(new_height)

        self._clamp_scroll_offset()
        self._update_scroll_to_bottom_btn_pos()
        self.geometry_changed.emit()
        return new_height

    def _clamp_scroll_offset(self) -> None:
        """限制滚动偏移量在 [0, max_offset]：
        0 = 最新消息在底部（默认）
        max_offset = 最旧消息刚好到达顶部（全部历史可见）
        """
        available_h = (
            self.height()
            - self._input_height
            - self.layout().spacing()
            - self._msg_layout.contentsMargins().top()
            - self._msg_layout.contentsMargins().bottom()
        )
        total_h = self._get_total_content_height()

        if total_h <= available_h:
            self._scroll_offset = 0
        else:
            # 最旧消息可以滚动到屏幕底部，让用户完整看到历史
            max_offset = total_h
            self._scroll_offset = max(0, min(max_offset, self._scroll_offset))

    def _get_max_panel_height(self) -> int:
        """根据父窗口高度动态计算面板最大高度"""
        parent = self.parentWidget()
        if parent:
            return int(parent.height() * self._max_height_ratio)
        return _MAX_PANEL_HEIGHT

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

        # 确保输入框始终在最上层
        self._input_frame.raise_()

        new_height = self._adjust_height()
        self._relayout_messages()
        self._update_opacity_by_position()
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
            anim.valueChanged.connect(lambda v, d=dot: d.setStyleSheet(
                f"color: rgba(204, 204, 204, {int(v * 255)}); font-size: 8px;"
            ))
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
            self._relayout_messages()
            self._update_opacity_by_position()
            self.geometry_changed.emit()

    def toggle_visibility(self) -> None:
        """切换显示/隐藏"""
        self.setVisible(not self.isVisible())

    def event(self, event) -> bool:
        """拦截 LayoutRequest：Qt 布局引擎在失焦/右键菜单/样式变化时会尝试重新排布，
        用我们的手动计算立即覆盖，防止 spacing 被压缩。"""
        if event.type() == QEvent.Type.LayoutRequest:
            self._relayout_messages()
            self._update_opacity_by_position()
        return super().event(event)

    def resizeEvent(self, event) -> None:
        """尺寸变化时重新排布消息并更新透明度"""
        super().resizeEvent(event)
        self._relayout_messages()
        self._update_opacity_by_position()
        self._update_scroll_to_bottom_btn_pos()

    def showEvent(self, event) -> None:
        """显示时自定位到底部与角色底部对齐，并聚焦输入框"""
        super().showEvent(event)
        self._relayout_messages()
        self._update_opacity_by_position()
        parent = self.parentWidget()
        if parent:
            cx = (parent.width() - self.width()) // 2
            # 聊天面板底部略低于角色底部，遮住一点脚部
            # haru 模型脚部实际约占父窗口高度的 95.5%
            character_bottom = int(parent.height() * _CHARACTER_BOTTOM_RATIO) + 3
            cy = character_bottom - self.height()
            cy = max(cy, 0)
            self.move(cx, cy)
            self.raise_()
        if hasattr(self, "_input") and self._input is not None:
            self._input.setFocus()

    # ---- 滚动相关 ----

    def _update_scroll_to_bottom_btn_pos(self) -> None:
        """更新跳到底部按钮的位置和显隐状态"""
        available_h = (
            self.height()
            - self._input_height
            - self.layout().spacing()
            - self._msg_layout.contentsMargins().top()
            - self._msg_layout.contentsMargins().bottom()
        )
        total_h = self._get_total_content_height()

        if total_h <= available_h or self._scroll_offset <= 10:
            self._scroll_to_bottom_btn.hide()
        else:
            viewport_height = self.height() - self._input_height - self.layout().spacing()
            btn_x = self.width() - 28
            btn_y = viewport_height - 26
            self._scroll_to_bottom_btn.move(btn_x, btn_y)
            self._scroll_to_bottom_btn.raise_()
            self._scroll_to_bottom_btn.show()

    def _scroll_to_bottom(self) -> None:
        """滚动到底部（查看最新消息）"""
        self._scroll_offset = 0
        self._relayout_messages()
        self._update_opacity_by_position()
        self._update_scroll_to_bottom_btn_pos()

    def wheelEvent(self, event) -> None:
        """滚轮事件：在消息区域滚动浏览历史"""
        viewport_height = self.height() - self._input_height - self.layout().spacing()
        # 只在消息区域内处理滚轮
        if event.position().y() > viewport_height:
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()
        if delta > 0:
            self._scroll_offset += 20
        else:
            self._scroll_offset -= 20

        self._clamp_scroll_offset()
        self._relayout_messages()
        self._update_opacity_by_position()
        self._update_scroll_to_bottom_btn_pos()
        event.accept()

    # ---- 语音输入 ----

    def _on_voice_long_press(self) -> None:
        """长按确认：开始录音（录制前检测模型，避免白录）"""
        if self._stt is None:
            return
        from voice.model_manager import get_download_manager, is_model_downloaded, get_current_model_id
        dm = get_download_manager()

        # 检查是否有模型正在下载
        if dm.is_downloading():
            self._voice_btn.reset_style()
            self.add_message("葵酱：语音转文字模型正在下载中呢，请稍候再试哦~", is_user=False)
            return

        current_model = get_current_model_id()
        if current_model is None:
            self._voice_btn.reset_style()
            self.add_message("葵酱：还没有选择语音转文字模型呢，请去菜单栏选择哦~", is_user=False)
            return

        if not is_model_downloaded(current_model):
            self._voice_btn.reset_style()
            self.add_message("葵酱：语音转文字模型还没下载呢，请去菜单栏下载哦~", is_user=False)
            return
        # 取消之前的自动停止定时器（防止重叠）
        if hasattr(self, "_auto_stop_timer") and self._auto_stop_timer is not None:
            self._auto_stop_timer.stop()
            self._auto_stop_timer = None
        # 清空输入框，确保 placeholder 可见
        self._input.clear()
        self._stt.start_recording()
        logger.info("语音录制开始")
        # 显示明显的"正在聆听"提示，并禁用键盘输入避免冲突
        self._input.setPlaceholderText("🎙 正在聆听... 松开按钮结束录音")
        self._input.setEnabled(False)
        # 启动音量可视化定时器（每 50ms 更新一次）
        self._volume_timer = QTimer(self)
        self._volume_timer.timeout.connect(self._update_voice_volume)
        self._volume_timer.start(50)
        # 启动自动停止定时器（后备：防止鼠标移出窗口释放等导致 mouseReleaseEvent 丢失）
        self._auto_stop_timer = QTimer(self)
        self._auto_stop_timer.setSingleShot(True)
        self._auto_stop_timer.timeout.connect(self._auto_stop_recording)
        self._auto_stop_timer.start(15000)  # 15 秒后备超时

    def _auto_stop_recording(self) -> None:
        """自动停止录音（极端情况后备：grabMouse 失效时兜底）"""
        logger.info("录音自动停止（超时后备）")
        self._auto_stop_timer = None
        self._stop_voice_volume_timer()
        self._voice_btn.reset_style()  # 释放鼠标捕获
        self._restore_input_after_recording()
        if self._stt:
            self._stt.stop_recording_and_transcribe(self._on_transcribe_done)

    def _on_voice_released(self, valid: bool) -> None:
        """松开按钮：结束录音并转文字"""
        # 取消自动停止定时器
        if hasattr(self, "_auto_stop_timer") and self._auto_stop_timer is not None:
            self._auto_stop_timer.stop()
            self._auto_stop_timer = None
        if not valid:
            self.add_message("葵酱：按住时间太短啦，请长按麦克风按钮说话哦~", is_user=False)
            return
        if self._stt is None:
            self.add_message("葵酱：语音功能暂时不可用呢~", is_user=False)
            return
        self._stop_voice_volume_timer()
        self._restore_input_after_recording()
        # 显示转录中的思考状态
        self._input.setPlaceholderText("💭 葵酱正在思考你说了什么...")
        self.show_typing_indicator()
        logger.info("提交语音转录任务")
        self._stt.stop_recording_and_transcribe(self._on_transcribe_done)

    def _restore_input_after_recording(self) -> None:
        """录音结束后恢复输入框状态"""
        self._input.setPlaceholderText("跟葵酱说点什么吧~ ✨")
        self._input.setEnabled(True)

    def _update_voice_volume(self) -> None:
        """更新麦克风音量可视化"""
        if self._stt:
            self._voice_btn.set_volume(self._stt.get_volume())

    def _stop_voice_volume_timer(self) -> None:
        """停止音量可视化定时器"""
        if hasattr(self, '_volume_timer') and self._volume_timer is not None:
            self._volume_timer.stop()
            self._volume_timer = None
        self._voice_btn.set_volume(0.0)

    def _on_transcribe_done(self, text: str) -> None:
        """转录完成回调（在主线程执行）"""
        logger.info(f"_on_transcribe_done 被调用，text={'有内容' if text else '空'}")
        self.hide_typing_indicator()
        self._input.setPlaceholderText("跟葵酱说点什么吧~ ✨")
        if text:
            self._input.setText(text)
            self._input.setFocus()
            logger.info(f"语音转文字成功: {text[:30]}...")
        else:
            self.add_message("葵酱：没有听清呢，请再试一次吧~", is_user=False)

    # ---- 下载进度（常驻在输入框位置） ----

    def show_download_progress(self) -> None:
        """显示下载进度条，隐藏输入框"""
        self._input_frame.hide()
        self._download_frame.show()
        self._update_download_style(0)
        self._download_detail.setText("准备下载...")

    def _update_download_style(self, pct: int) -> None:
        """更新整个框的背景渐变进度（边框=输入框focus粗边框，填充=实色覆盖）"""
        if pct >= 100:
            bg = "background-color: rgba(255, 200, 195, 0.95);"
        else:
            ratio = pct / 100.0
            r = min(ratio + 0.005, 1.0)
            bg = f"""background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(255, 200, 195, 0.95),
                stop:{ratio:.4f} rgba(255, 200, 195, 0.95),
                stop:{r:.4f} rgba(255, 248, 243, 0.95),
                stop:1 rgba(255, 248, 243, 0.95));"""
        self._download_frame.setStyleSheet(f"""
            QFrame {{
                {bg}
                border: 2px solid rgba(255, 170, 160, 0.85);
                border-radius: 10px;
            }}
        """)

    def _on_download_progress(self, model_id, pct, downloaded, total, speed):
        """更新下载进度显示"""
        from voice.model_manager import _fmt_bytes
        self._update_download_style(pct)
        detail = f"{_fmt_bytes(downloaded)} / {_fmt_bytes(total)}"
        if speed:
            detail += f"  {speed}"
        self._download_detail.setText(detail)

    def _on_download_stopped(self):
        """下载结束，恢复输入框"""
        self._download_frame.hide()
        self._input_frame.show()
        self._download_detail.setText("")

    def _on_cancel_download_clicked(self):
        """点击图标取消下载"""
        self._download_detail.setText("正在取消下载并清除不完整资源...")
        from voice.model_manager import get_download_manager
        get_download_manager().cancel_download()

    def _setup_download_tracking(self) -> None:
        """连接下载管理器信号，在输入框位置显示常驻进度条"""
        from voice.model_manager import get_download_manager
        dm = get_download_manager()
        dm.progress.connect(self._on_download_progress)
        dm.download_stopped.connect(self._on_download_stopped)

    # ---- 内部类：下载图标 ----

    class _DownloadIcon(QWidget):
        """下载图标：默认沙漏，悬停叉号，点击取消"""
        clicked = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedSize(28, 28)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 248, 243, 0.95);
                    border-radius: 8px;
                }
            """)
            self._label = QLabel("⏳", self)
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._label)

        def enterEvent(self, event) -> None:
            self._label.setText("❌")
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 230, 225, 0.98);
                    border-radius: 8px;
                }
            """)
            super().enterEvent(event)

        def leaveEvent(self, event) -> None:
            self._label.setText("⏳")
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 248, 243, 0.95);
                    border-radius: 8px;
                }
            """)
            super().leaveEvent(event)

        def mousePressEvent(self, event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()

    # ---- 输入框样式 ----

    def _update_input_frame_style(self, focused: bool = False) -> None:
        """更新输入框外壳样式（galgame 风格）"""
        if focused:
            self._input_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 248, 243, 0.95);
                    border: 2px solid rgba(255, 170, 160, 0.85);
                    border-radius: 10px;
                }
            """)
        else:
            self._input_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 250, 245, 0.92);
                    border: 1.5px solid rgba(255, 200, 195, 0.6);
                    border-radius: 10px;
                }
            """)

    def eventFilter(self, obj, event) -> bool:
        """监听输入框 focus 事件以切换外壳样式"""
        if obj is self._input:
            if event.type() == QEvent.Type.FocusIn:
                self._update_input_frame_style(focused=True)
            elif event.type() == QEvent.Type.FocusOut:
                self._update_input_frame_style(focused=False)
        return super().eventFilter(obj, event)

    # ---- 内部类：语音按钮 ----

    class _VoiceButton(QWidget):
        """语音转文字按钮：支持长按检测"""

        long_press_confirmed = Signal()
        press_released = Signal(bool)  # bool = 是否是有效长按

        def __init__(self, parent=None):
            super().__init__(parent)
            self._pressing = False
            self._confirmed = False
            self._min_ms = 300

            self.setFixedSize(28, 28)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            self._icon = QLabel("🎙", self)
            self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self._icon)

            # 音量可视化覆盖层（录制时从下到上填充）
            self._volume_overlay = QWidget(self)
            self._volume_overlay.setStyleSheet(
                "background-color: rgba(160, 50, 50, 0.55); border-radius: 6px;"
            )
            self._volume_overlay.setGeometry(2, self.height() - 2, self.width() - 4, 2)
            self._volume_overlay.hide()

            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_timer_timeout)

            self._set_style("normal")

        def set_volume(self, vol: float) -> None:
            """设置音量可视化（0.0 ~ 1.0）"""
            if vol <= 0:
                self._volume_overlay.hide()
                return
            h = int((self.height() - 4) * min(vol, 1.0))
            # 保证最小高度让圆角可见，且 radius 不超过高度的一半
            h = max(h, 4)
            radius = min(3, h // 2)
            self._volume_overlay.setStyleSheet(
                f"background-color: rgba(160, 50, 50, 0.55); border-radius: {radius}px;"
            )
            self._volume_overlay.setGeometry(
                2, self.height() - 2 - h, self.width() - 4, h
            )
            self._volume_overlay.show()

        def _set_style(self, state: str) -> None:
            if state == "recording":
                self.setStyleSheet("""
                    QWidget {
                        background-color: rgba(220, 100, 100, 0.75);
                        border-radius: 8px;
                    }
                """)
            elif state == "pending":
                self.setStyleSheet("""
                    QWidget {
                        background-color: rgba(200, 160, 140, 0.55);
                        border-radius: 8px;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QWidget {
                        background-color: rgba(200, 160, 140, 0.35);
                        border-radius: 8px;
                    }
                    QWidget:hover {
                        background-color: rgba(200, 160, 140, 0.5);
                    }
                """)

        def mousePressEvent(self, event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self._pressing = True
                self._confirmed = False
                self._set_style("pending")
                self._timer.start(self._min_ms)
                self.grabMouse()  # 捕获鼠标，移出窗口后仍能收到 release

        def _on_timer_timeout(self) -> None:
            if self._pressing:
                self._confirmed = True
                self._set_style("recording")
                self.long_press_confirmed.emit()

        def mouseReleaseEvent(self, event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.releaseMouse()
                if self._pressing:
                    self._pressing = False
                    self._timer.stop()
                    valid = self._confirmed
                    self._set_style("normal")
                    self.press_released.emit(valid)

        def reset_style(self) -> None:
            """外部调用：强制恢复按钮为 normal 状态"""
            self.releaseMouse()
            self._pressing = False
            self._confirmed = False
            self._timer.stop()
            self._set_style("normal")
            self.set_volume(0.0)
