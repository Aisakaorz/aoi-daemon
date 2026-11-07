# -*- coding: utf-8 -*-
"""
自绘矢量小图标：替代界面里渲染不稳定的 emoji 文本

双色配方：深粉描边 + 浅粉填充 + 白色高光，细线圆头、对称留白，
小尺寸下也保持精致。不依赖系统 emoji 字体（Windows / macOS / 离屏一致）。
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

ICON_COLOR = QColor("#E0507A")          # 深粉描边
ICON_COLOR_LIGHT = QColor("#FFFFFF")    # 录音态：深底上的白色图标
_FILL = QColor("#FFD9D4")               # 浅粉填充
_FILL_LIGHT = QColor(255, 255, 255, 80)
_HIGHLIGHT = QColor(255, 255, 255, 200)


def _setup(p: QPainter, c: QColor, s: float) -> None:
    """统一画笔：细线 + 圆头圆角；填充后调用可复位画刷（见 PRD 踩坑 #27）"""
    p.setPen(QPen(
        c, max(1.3, s * 0.075),
        Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
    ))
    p.setBrush(Qt.BrushStyle.NoBrush)


def paint_icon(p: QPainter, kind: str, rect: QRectF, color: QColor | None = None) -> None:
    """在 rect 内居中绘制矢量图标（按短边等比缩放）"""
    c = color or ICON_COLOR
    light = (c == ICON_COLOR_LIGHT)
    fill = _FILL_LIGHT if light else _FILL
    s = min(rect.width(), rect.height())
    cx, cy = rect.center().x(), rect.center().y()

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _setup(p, c, s)

    if kind == "mic":
        # 胶囊麦头：浅粉填充 + 深粉描边 + 两道网罩细线
        w, h = s * 0.34, s * 0.46
        head = QRectF(cx - w / 2, cy - s * 0.44, w, h)
        path = QPainterPath()
        path.addRoundedRect(head, w / 2, w / 2)
        p.setBrush(fill)
        p.drawPath(path)
        grid = QColor(c)
        grid.setAlpha(130)
        p.setPen(QPen(grid, max(0.8, s * 0.032), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(cx - w * 0.26, cy - s * 0.31, cx + w * 0.26, cy - s * 0.31)
        p.drawLine(cx - w * 0.26, cy - s * 0.21, cx + w * 0.26, cy - s * 0.21)
        _setup(p, c, s)
        # U 形支架 + 底座
        arc = QPainterPath()
        arc.moveTo(cx - s * 0.24, cy - s * 0.01)
        arc.quadTo(cx - s * 0.24, cy + s * 0.28, cx, cy + s * 0.28)
        arc.quadTo(cx + s * 0.24, cy + s * 0.28, cx + s * 0.24, cy - s * 0.01)
        p.drawPath(arc)
        p.drawLine(cx, cy + s * 0.28, cx, cy + s * 0.40)
        p.drawLine(cx - s * 0.12, cy + s * 0.40, cx + s * 0.12, cy + s * 0.40)

    elif kind in ("upload", "download"):
        # 附件 / 下载：淡粉圆底 + 填充箭头 + 白色高光 + 圆角托盘（成对且精致）
        up = (kind == "upload")
        bg = QColor(c)
        bg.setAlpha(22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(QRectF(cx - s * 0.36, cy - s * 0.36, s * 0.72, s * 0.72))

        # 圆角托盘（浅粉填充 + 深粉细描边），不再是一根光秃秃的横线
        tray = QRectF(cx - s * 0.23, cy + s * 0.22, s * 0.46, s * 0.13)
        tray_path = QPainterPath()
        tray_path.addRoundedRect(tray, s * 0.055, s * 0.055)
        p.setBrush(fill)
        p.setPen(QPen(c, max(1.0, s * 0.05)))
        p.drawPath(tray_path)

        # 填充箭头：珊瑚粉三角 + 深粉描边 + 白色高光斜线
        head = QPainterPath()
        if up:
            head.moveTo(cx, cy - s * 0.31)
            head.lineTo(cx - s * 0.17, cy - s * 0.05)
            head.lineTo(cx + s * 0.17, cy - s * 0.05)
            stem_y0, stem_y1 = cy + s * 0.18, cy - s * 0.02
        else:
            head.moveTo(cx, cy + s * 0.19)
            head.lineTo(cx - s * 0.17, cy - s * 0.03)
            head.lineTo(cx + s * 0.17, cy - s * 0.03)
            stem_y0, stem_y1 = cy - s * 0.30, cy - s * 0.02
        head.closeSubpath()
        p.setBrush(QColor(255, 255, 255, 220) if light else QColor("#FF8A80"))
        p.setPen(QPen(c, max(1.0, s * 0.055), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(head)
        # 箭杆
        p.setPen(QPen(c, max(1.5, s * 0.085), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(cx, stem_y0, cx, stem_y1)
        # 箭头上的柔白高光
        p.setPen(QPen(_HIGHLIGHT, max(0.8, s * 0.04), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        if up:
            p.drawLine(cx - s * 0.06, cy - s * 0.16, cx - s * 0.02, cy - s * 0.24)
        else:
            p.drawLine(cx - s * 0.06, cy + s * 0.02, cx - s * 0.02, cy + s * 0.10)


    elif kind == "close":
        # 叉号：淡粉圆底 + 均匀圆头双线
        p.setPen(Qt.PenStyle.NoPen)
        bg = QColor(c)
        bg.setAlpha(26)
        p.setBrush(bg)
        p.drawEllipse(QRectF(cx - s * 0.34, cy - s * 0.34, s * 0.68, s * 0.68))
        r = s * 0.21
        p.setPen(QPen(c, max(1.5, s * 0.08), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(cx - r, cy - r, cx + r, cy + r)
        p.drawLine(cx + r, cy - r, cx - r, cy + r)

    elif kind == "down":
        # 下箭头：圆角三角，边角柔化
        r = s * 0.27
        path = QPainterPath()
        path.moveTo(cx - r, cy - r * 0.52)
        path.lineTo(cx + r, cy - r * 0.52)
        path.quadTo(cx + r, cy - r * 0.52, cx + r * 0.84, cy - r * 0.26)
        path.lineTo(cx + r * 0.10, cy + r * 0.62)
        path.quadTo(cx, cy + r * 0.82, cx - r * 0.10, cy + r * 0.62)
        path.lineTo(cx - r * 0.84, cy - r * 0.26)
        path.quadTo(cx - r, cy - r * 0.52, cx - r, cy - r * 0.52)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawPath(path)

    elif kind == "heart":
        # 爱心：珊瑚填充 + 深粉细描边 + 左上白色高光
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.34)
        path.cubicTo(cx - s * 0.62, cy - s * 0.02, cx - s * 0.34, cy - s * 0.48, cx, cy - s * 0.14)
        path.cubicTo(cx + s * 0.34, cy - s * 0.48, cx + s * 0.62, cy - s * 0.02, cx, cy + s * 0.34)
        p.setBrush(QColor(255, 255, 255, 220) if light else QColor("#FF8A80"))
        p.setPen(QPen(c, max(1.0, s * 0.05)))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_HIGHLIGHT)
        p.drawEllipse(QRectF(cx - s * 0.23, cy - s * 0.25, s * 0.10, s * 0.10))

    p.restore()


def icon_pixmap(kind: str, size: int = 20, color: QColor | None = None) -> QPixmap:
    """生成透明底图标位图，供 QLabel.setPixmap 使用"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    paint_icon(p, kind, QRectF(0, 0, size, size), color)
    p.end()
    return pm
