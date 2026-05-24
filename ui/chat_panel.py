# -*- coding: utf-8 -*-
"""
聊天气泡面板
紧凑设计：输入框 + 最近消息气泡，像漫画对话框一样
固定在角色下方（窗口底部居中）
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame, QDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QVariantAnimation, QEasingCurve, QEvent, QDateTime
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
        self._setup_ui()
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

        # 消息区域 —— 禁用自动布局，改为手动计算每条消息的 y 坐标
        # 这样可以根治 QBoxLayout 在空间不足时压缩 spacing 导致气泡重叠/间距变小的问题
        self._msg_layout = QVBoxLayout()
        self._msg_layout.setSpacing(4)
        self._msg_layout.setContentsMargins(2, 2, 2, 2)
        self._msg_layout.setEnabled(False)  # 禁用自动布局
        layout.addLayout(self._msg_layout)

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

        # 初始高度 = 输入框 + layout spacing + msg layout 边距
        initial_h = (
            self._input_height
            + layout.spacing()
            + self._msg_layout.contentsMargins().top()
            + self._msg_layout.contentsMargins().bottom()
        )
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
        self._update_opacity_by_position(new_height)

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
        new_height = min(height, self._get_max_panel_height())
        self.setFixedHeight(new_height)
        self.geometry_changed.emit()
        return new_height

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

        new_height = self._adjust_height()
        self._relayout_messages(new_height)
        self._update_opacity_by_position(new_height)
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
            self._update_opacity_by_position(new_height)
            self.geometry_changed.emit()

    def toggle_visibility(self) -> None:
        """切换显示/隐藏"""
        self.setVisible(not self.isVisible())

    def resizeEvent(self, event) -> None:
        """尺寸变化时重新排布消息（保持对齐和间距正确）"""
        super().resizeEvent(event)
        self._relayout_messages()

    def showEvent(self, event) -> None:
        """显示时自定位到父窗口底部居中，并聚焦输入框"""
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            cx = (parent.width() - self.width()) // 2
            cy = parent.height() - self.height() - 10
            self.move(cx, max(cy, 0))
            self.raise_()
        if hasattr(self, "_input") and self._input is not None:
            self._input.setFocus()

    # ---- 语音输入 ----

    def _on_voice_long_press(self) -> None:
        """长按确认：开始录音（录制前检测模型，避免白录）"""
        if self._stt is None:
            return
        from voice.stt_provider import is_model_available
        if not is_model_available():
            # 弹窗前恢复按钮样式，避免对话框关闭后按钮卡在 recording 状态
            self._voice_btn.reset_style()
            from ui.model_download_dialog import ModelDownloadDialog
            dialog = ModelDownloadDialog(self)
            result = dialog.exec()
            if result != QDialog.DialogCode.Accepted:
                return
            # 下载完成，提示用户再次长按开始录音（不自动开始，因为弹窗已打断操作流程）
            self.add_message("葵酱：模型下载好啦，请再次长按麦克风按钮说话哦~", is_user=False)
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
        # 启动自动停止定时器（后备：防止鼠标移出窗口释放等导致 mouseReleaseEvent 丢失）
        self._auto_stop_timer = QTimer(self)
        self._auto_stop_timer.setSingleShot(True)
        self._auto_stop_timer.timeout.connect(self._auto_stop_recording)
        self._auto_stop_timer.start(15000)  # 15 秒后备超时

    def _auto_stop_recording(self) -> None:
        """自动停止录音（极端情况后备：grabMouse 失效时兜底）"""
        logger.info("录音自动停止（超时后备）")
        self._auto_stop_timer = None
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
        self._restore_input_after_recording()
        self._stt.stop_recording_and_transcribe(self._on_transcribe_done)

    def _restore_input_after_recording(self) -> None:
        """录音结束后恢复输入框状态"""
        self._input.setPlaceholderText("跟葵酱说点什么吧~ ✨")
        self._input.setEnabled(True)

    def _on_transcribe_done(self, text: str) -> None:
        """转录完成回调（在主线程执行）"""
        if text:
            self._input.setText(text)
            self._input.setFocus()
            logger.info(f"语音转文字成功: {text[:30]}...")
        else:
            self.add_message("葵酱：没有听清呢，请再试一次吧~", is_user=False)

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

            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_timer_timeout)

            self._set_style("normal")

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
