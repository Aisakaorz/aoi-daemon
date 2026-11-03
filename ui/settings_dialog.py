# -*- coding: utf-8 -*-
"""
设置窗口（v0.1.26）：非模态圆角卡片，与启动画面/关于同一设计语言
三段式布局——外观（角色大小/置顶/吸附）、语音（模型选择与管理）、关于
改动即时生效并写回 config.json；右键/托盘菜单精简为 4 项
"""
import math
import os

from PySide6.QtCore import Qt, QRectF, QElapsedTimer, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QCursor, QLinearGradient
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QButtonGroup,
)

from core.bootstrap import APP_VERSION
from ui.card_paint import paint_cute_card
from ui.splash_screen import heart_path
from utils.font_manager import cute_font, body_font
from utils.logger import get_logger

logger = get_logger(__name__)


_SEGMENT_QSS = """
QFrame#segment_box {
    background: #F7E9E3;
    border-radius: 11px;
}
QPushButton {
    border: none;
    border-radius: 9px;
    padding: 4px 18px;
    color: #8A736C;
    background: transparent;
    font-size: 10pt;
}
QPushButton:checked {
    background: #FF8A80;
    color: #FFFFFF;
}
QPushButton:hover:!checked {
    background: #FBE3DC;
}
"""

_PILL_BTN_QSS = """
QPushButton {
    background: #FFFFFF;
    border: 1.5px solid #FFD9D4;
    border-radius: 10px;
    padding: 4px 8px;
    color: #E0507A;
    font-size: 9pt;
}
QPushButton:hover:!disabled {
    background: #FFF0EC;
    border-color: #FFB4AB;
}
QPushButton:disabled {
    color: #C9B8B2;
    border-color: #EFE0DA;
    background: #FBF4F1;
}
"""

# “使用中”态：珊瑚实心高亮（区别于置灰的不可用态）
_PILL_BTN_ACTIVE_QSS = """
QPushButton {
    background: #FF9E96;
    border: 1.5px solid #F2668B;
    border-radius: 10px;
    padding: 4px 8px;
    color: #FFFFFF;
    font-size: 9pt;
}
"""

_LINK_QSS = "color: #E0507A; background: transparent; border: none; font-size: 9pt;"


class ToggleSwitch(QWidget):
    """胶囊开关：圆角药丸 + 白色滑块，切换时滑块平滑滑动（自绘）"""

    toggled = Signal(bool)

    _W, _H = 44, 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._W, self._H)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checked = False
        self._pos = 0.0   # 滑块位置 0.0（左）~ 1.0（右），逐帧逼近
        self._target = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if self._checked == checked:
            # 同步外部状态时不重复动画
            self._pos = self._target = 1.0 if checked else 0.0
            self.update()
            return
        self._checked = checked
        self._target = 1.0 if checked else 0.0

    def isChecked(self) -> bool:
        return self._checked

    def _tick(self) -> None:
        diff = self._target - self._pos
        if abs(diff) < 0.005:
            if self._pos != self._target:
                self._pos = self._target
                self.update()
            return
        self._pos += diff * 0.28
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 药丸底：灰粉 → 珊瑚 渐变过渡
        off_color = QColor("#EDDCD6")
        on_color = QColor("#FF8A80")
        t = self._pos
        bg = QColor(
            int(off_color.red() + (on_color.red() - off_color.red()) * t),
            int(off_color.green() + (on_color.green() - off_color.green()) * t),
            int(off_color.blue() + (on_color.blue() - off_color.blue()) * t),
        )
        pill = QRectF(1, 1, self._W - 2, self._H - 2)
        pill_path = QPainterPath()
        pill_path.addRoundedRect(pill, self._H / 2 - 1, self._H / 2 - 1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawPath(pill_path)
        # 白色滑块
        knob_d = self._H - 9
        x = 4.5 + t * (self._W - 9 - knob_d)
        knob = QRectF(x, (self._H - knob_d) / 2.0, knob_d, knob_d)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(0, 0, 0, 18), 1))
        p.drawEllipse(knob)
        p.end()


class DownloadBar(QWidget):
    """内联下载进度条：糖针风圆角轨道 + 珊瑚渐变填充"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._pct = 0

    def setProgress(self, pct: int) -> None:
        self._pct = max(0, min(100, int(pct)))
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 0, self.width(), self.height())
        track_path = QPainterPath()
        track_path.addRoundedRect(track, 5, 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F7E2DB"))
        p.drawPath(track_path)
        if self._pct > 0:
            fill_w = max(10.0, self.width() * self._pct / 100.0)
            fill = QRectF(0, 0, min(fill_w, self.width()), self.height())
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill, 5, 5)
            grad = QLinearGradient(0, 0, self.width(), 0)
            grad.setColorAt(0.0, QColor("#FFB4AB"))
            grad.setColorAt(1.0, QColor("#F2668B"))
            p.setBrush(grad)
            p.drawPath(fill_path)
        p.end()


class _SectionTitle(QLabel):
    """小节标题：萌体文字"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(cute_font(12, QFont.Weight.Bold))
        self.setStyleSheet("color: #F2668B; background: transparent; border: none;")


class SettingsDialog(QWidget):
    """
    设置卡片窗口（非模态）：
    - 外观：角色大小（分段选择）、窗口置顶、任务栏吸附（胶囊开关）
    - 语音：语音转文字模型（状态 + 内联下载进度条 + 取消/重试）
    - 关于：版本、许可、项目链接、完整关于卡片入口
    """

    _RADIUS = 18
    _MARGIN = 12

    def __init__(self, main_window):
        # Qt.Window：独立顶层窗口，避免 macOS 上父窗口为 Tool 的弹窗焦点坑
        super().__init__(main_window, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self._mw = main_window
        self.setFixedSize(340, 444)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("设置 · 葵之使魔")
        icon_path = os.path.join("resources", "icons", "app_icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

        self._drag_pos = None
        # 背景花纹动画驱动（与启动画面/关于同款漂浮粒子）
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self.update)
        self._bg_timer.start(33)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 16, 26, 16)
        layout.setSpacing(0)

        # ---- 标题栏（可拖动） ----
        header = QHBoxLayout()
        header.setContentsMargins(2, 4, 2, 0)
        title = QLabel("设置")
        title.setFont(cute_font(14, QFont.Weight.Bold))
        title.setStyleSheet("color: #F2668B; background: transparent; border: none;")
        header.addWidget(title)
        header.addStretch(1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; border-radius: 12px;
                color: #C9A9A0; font-size: 11pt;
            }
            QPushButton:hover { background: #FFE3DE; color: #E0507A; }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        layout.addSpacing(8)
        layout.addWidget(self._make_separator())
        layout.addSpacing(6)

        # ---- ✦ 外观 ----
        layout.addWidget(_SectionTitle("✦ 外观"))
        layout.addSpacing(8)
        layout.addLayout(self._build_size_row())
        layout.addSpacing(10)
        layout.addLayout(self._build_switch_row("窗口置顶", "top"))
        layout.addSpacing(8)
        layout.addLayout(self._build_switch_row("任务栏吸附", "snap"))
        layout.addSpacing(10)
        layout.addWidget(self._make_separator())
        layout.addSpacing(6)

        # ---- ✦ 语音 ----
        layout.addWidget(_SectionTitle("✦ 语音"))
        layout.addSpacing(8)
        self._build_model_block(layout)
        layout.addSpacing(10)
        layout.addWidget(self._make_separator())
        layout.addSpacing(6)

        # ---- ✦ 关于 ----
        layout.addWidget(_SectionTitle("✦ 关于"))
        layout.addSpacing(8)
        info = QLabel(f"葵之使魔 ~AoiDaemon~ · v{APP_VERSION}")
        info.setFont(cute_font(9))
        info.setStyleSheet("color: #8A736C; background: transparent; border: none;")
        layout.addWidget(info)
        layout.addSpacing(10)
        link = QLabel('<a href="https://github.com/Aisakaorz/aoi-daemon" style="color:#E0507A;">项目主页 · MIT License</a>')
        link.setFont(cute_font(9))
        link.setStyleSheet(_LINK_QSS)
        link.setOpenExternalLinks(True)
        layout.addWidget(link)
        layout.addSpacing(12)
        about_btn = QPushButton("查看完整关于卡片")
        about_btn.setFont(cute_font(9))
        about_btn.setStyleSheet(_PILL_BTN_QSS)
        about_btn.clicked.connect(self._mw._show_about)
        layout.addWidget(about_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

        # 下载进度联动
        from voice.model_manager import get_download_manager
        self._dm = get_download_manager()
        self._dm.progress.connect(self._on_download_progress)
        self._dm.finished.connect(self._on_download_finished)

    # ---- 行构建 ----

    def _make_separator(self) -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #FFD9D4; border: none;")
        return line

    def _build_size_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel("角色大小")
        label.setFont(cute_font(10))
        label.setStyleSheet("color: #4A3F3A; background: transparent; border: none;")
        row.addWidget(label)
        row.addStretch(1)
        segment = QFrame()
        segment.setObjectName("segment_box")
        seg_layout = QHBoxLayout(segment)
        seg_layout.setContentsMargins(3, 3, 3, 3)
        seg_layout.setSpacing(2)
        self._size_buttons = []
        group = QButtonGroup(self)
        group.setExclusive(True)
        for text, scale in (("小", 0.75), ("中", 1.0), ("大", 1.25)):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setStyleSheet(_SEGMENT_QSS)
            btn.clicked.connect(lambda checked, s=scale: self._on_size_clicked(s))
            group.addButton(btn)
            seg_layout.addWidget(btn)
            self._size_buttons.append((btn, scale))
        segment.setStyleSheet(_SEGMENT_QSS)
        row.addWidget(segment)
        return row

    def _build_switch_row(self, text: str, key: str) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(text)
        label.setFont(cute_font(10))
        label.setStyleSheet("color: #4A3F3A; background: transparent; border: none;")
        row.addWidget(label)
        row.addStretch(1)
        switch = ToggleSwitch()
        if key == "top":
            switch.toggled.connect(self._on_top_toggled)
        else:
            switch.toggled.connect(self._on_snap_toggled)
        setattr(self, f"_switch_{key}", switch)
        row.addWidget(switch)
        return row

    def _build_model_block(self, layout: QVBoxLayout) -> None:
        # 第一行：名称 + 状态
        row1 = QHBoxLayout()
        name = QLabel("Whisper Tiny · ~75MB")
        name.setFont(cute_font(10))
        name.setStyleSheet("color: #4A3F3A; background: transparent; border: none;")
        row1.addWidget(name)
        row1.addStretch(1)
        self._model_status = QLabel("")
        self._model_status.setFont(cute_font(9))
        self._model_status.setStyleSheet("color: #8A736C; background: transparent; border: none;")
        row1.addWidget(self._model_status)
        layout.addLayout(row1)

        # 第二行：内联下载进度条（仅下载中显示）
        self._dl_bar = DownloadBar()
        self._dl_bar.setVisible(False)
        layout.addSpacing(6)
        layout.addWidget(self._dl_bar)

        # 第三行：操作按钮（删除 + 使用/下载/取消，同宽）
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 8, 0, 0)
        row3.addStretch(1)
        # 删除按钮：仅已下载且非当前使用时可用，释放磁盘空间
        self._del_btn = QPushButton("删除")
        self._del_btn.setStyleSheet(_PILL_BTN_QSS)
        self._del_btn.setFont(cute_font(9))
        self._del_btn.setFixedWidth(76)
        self._del_btn.setToolTip("删除已下载的模型文件（可重新下载）")
        self._del_btn.clicked.connect(self._on_delete_model)
        row3.addWidget(self._del_btn)
        row3.addSpacing(6)
        self._model_btn = QPushButton("")
        self._model_btn.setStyleSheet(_PILL_BTN_QSS)
        self._model_btn.setFont(cute_font(9))
        self._model_btn.setFixedWidth(76)
        self._model_btn.clicked.connect(self._on_model_button)
        row3.addWidget(self._model_btn)
        layout.addLayout(row3)

    # ---- 状态加载与同步 ----

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_state()

    def _current_model_id(self) -> str | None:
        from voice.model_manager import get_available_models, get_current_model_id
        current = get_current_model_id()
        if current is None:
            models = get_available_models()
            current = next(iter(models), None)
        return current

    def _load_state(self) -> None:
        """从主窗口/配置加载当前状态到控件"""
        mw = self._mw
        scale = getattr(mw, "_current_scale", 1.0)
        for btn, s in self._size_buttons:
            btn.setChecked(abs(s - scale) < 0.01)
        self._switch_top.setChecked(mw._action_top.isChecked())
        self._switch_snap.setChecked(mw._action_snap.isChecked())
        self._refresh_model_state()

    def _refresh_model_state(self) -> None:
        from voice.model_manager import get_current_model_id, is_model_downloaded
        model_id = self._current_model_id()
        downloaded = is_model_downloaded(model_id)
        current = get_current_model_id()

        if self._dm.is_downloading():
            self._model_status.setText("下载中…")
            self._model_btn.setText("取消")
            self._model_btn.setEnabled(True)
            self._del_btn.setVisible(False)
            self._dl_bar.setVisible(True)
            return

        self._dl_bar.setVisible(False)
        self._dl_bar.setProgress(0)
        self._del_btn.setVisible(downloaded)
        if downloaded:
            is_current = (current == model_id)
            self._model_status.setText("已下载")
            if is_current:
                self._model_btn.setText("使用中")
                self._model_btn.setEnabled(False)
                self._model_btn.setStyleSheet(_PILL_BTN_ACTIVE_QSS)  # 高亮当前使用态
                self._del_btn.setEnabled(False)  # 使用中的模型不可删除
            else:
                self._model_btn.setText("使用")
                self._model_btn.setEnabled(True)
                self._model_btn.setStyleSheet(_PILL_BTN_QSS)
                self._del_btn.setEnabled(True)
        else:
            self._model_status.setText("未下载")
            self._model_btn.setText("下载")
            self._model_btn.setEnabled(True)
            self._model_btn.setStyleSheet(_PILL_BTN_QSS)

    def _on_delete_model(self) -> None:
        """删除已下载的语音模型文件"""
        from voice.model_manager import delete_model
        model_id = self._current_model_id()
        if delete_model(model_id):
            self._model_status.setText("已删除")
        self._refresh_model_state()

    # ---- 交互 ----

    def _on_size_clicked(self, scale: float) -> None:
        self._mw._apply_scale(scale)

    def _on_top_toggled(self, checked: bool) -> None:
        if self._mw._action_top.isChecked() != checked:
            self._mw._action_top.setChecked(checked)
            self._mw._toggle_topmost()

    def _on_snap_toggled(self, checked: bool) -> None:
        if self._mw._action_snap.isChecked() != checked:
            self._mw._action_snap.setChecked(checked)
            self._mw._toggle_snap()

    def _on_model_button(self) -> None:
        """按当前状态执行：取消下载 / 开始下载（安静模式）/ 切换模型"""
        from voice.model_manager import get_current_model_id, set_current_model_id
        model_id = self._current_model_id()
        if self._dm.is_downloading():
            self._dm.cancel_download()
            self._model_status.setText("正在取消…")
            return
        from voice.model_manager import is_model_downloaded
        if not is_model_downloaded(model_id):
            self._mw._start_stt_download_quiet(model_id)
            self._refresh_model_state()
            return
        # 已下载但非当前：安静切换
        set_current_model_id(model_id)
        self._refresh_model_state()
        logger.info(f"语音模型切换为 {model_id}")

    def _on_download_progress(self, model_id, pct, downloaded, total, speed) -> None:
        if not self.isVisible():
            return
        if self._dm.is_downloading():
            speed_txt = f" · {speed}" if speed else ""
            self._model_status.setText(f"下载中 {pct}%{speed_txt}")
            self._model_btn.setText("取消")
            self._model_btn.setEnabled(True)
            self._del_btn.setVisible(False)
            self._dl_bar.setVisible(True)
            self._dl_bar.setProgress(pct)

    def _on_download_finished(self, model_id, success, message) -> None:
        self._dl_bar.setVisible(False)
        self._dl_bar.setProgress(0)
        if not success and message != "已取消":
            self._model_status.setText("下载失败")
            self._model_btn.setText("重试")
            self._model_btn.setEnabled(True)
            return
        self._refresh_model_state()

    # ---- 卡片绘制与拖动 ----

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = paint_cute_card(p, self.width(), self.height(), self._RADIUS, self._MARGIN)

        # 背景花纹（与启动画面/关于同款：两侧边栏漂浮爱心/星星 + 闪烁四角星）
        t = self._elapsed.elapsed() / 1000.0
        self._paint_particles(p, card, t)
        p.end()

    def _paint_particles(self, p: QPainter, card: QRectF, t: float) -> None:
        particles = (
            # (类型, x比例, 上浮周期s, 尺寸占卡宽比例, 相位, 颜色)
            ("heart", 0.085, 6.0, 0.05, 0.0, QColor(255, 142, 170, 80)),
            ("star", 0.155, 8.0, 0.038, 2.1, QColor(255, 179, 150, 85)),
            ("dot", 0.12, 7.0, 0.024, 4.4, QColor(255, 179, 180, 85)),
            ("heart", 0.845, 7.0, 0.046, 1.2, QColor(255, 142, 170, 75)),
            ("star", 0.92, 7.5, 0.036, 3.3, QColor(255, 179, 150, 80)),
            ("dot", 0.885, 8.5, 0.023, 5.0, QColor(255, 179, 180, 80)),
        )
        top = card.top() + 14
        travel = card.height() - 28
        for kind, fx, period, rel, phase, color in particles:
            prog = ((t / period) + phase / 6.283) % 1.0
            y = top + (1.0 - prog) * travel
            x = card.left() + card.width() * fx + math.sin(t * 0.9 + phase) * 3.0
            edge_fade = math.sin(prog * math.pi)
            c = QColor(color)
            c.setAlphaF(color.alphaF() * edge_fade)
            size = rel * card.width()
            if kind == "heart":
                p.save()
                p.translate(x, y)
                p.scale(size, size)
                p.translate(0, -0.5)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawPath(heart_path())
                p.restore()
            elif kind == "star":
                self._paint_sparkle(p, x, y, size, c)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawEllipse(QRectF(x - size / 2, y - size / 2, size, size))

        # 两角闪烁星星
        for cx, cy, r, speed, phase in (
            (card.left() + 24, card.bottom() - 26, 4.0, 2.4, 0.0),
            (card.right() - 28, card.top() + 84, 3.2, 2.9, 1.6),
        ):
            breathe = 0.55 + 0.45 * math.sin(t * speed + phase)
            c = QColor("#FFCCC4")
            c.setAlphaF(c.alphaF() * breathe)
            self._paint_sparkle(p, cx, cy, r, c)

    @staticmethod
    def _paint_sparkle(p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
        path = QPainterPath()
        for i in range(8):
            radius = r if i % 2 == 0 else r * 0.42
            angle = math.pi / 4 * i - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)
