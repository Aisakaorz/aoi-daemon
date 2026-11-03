# -*- coding: utf-8 -*-
"""
圆角卡片绘制助手：奶油渐变底 + 珊瑚粉双边框 + 手绘柔影
与启动画面/关于对话框同一套视觉配方（抽出来供新的卡片窗口复用）
"""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen


def paint_cute_card(p: QPainter, width: int, height: int, radius: int, margin: int = 12) -> QRectF:
    """在 widget 上绘制整套圆角卡片，返回卡片内容区域 rect"""
    card = QRectF(margin, margin, width - 2 * margin, height - 2 * margin)

    # 手绘柔影
    for expand, dy, alpha in ((5.0, 4.0, 28), (3.0, 3.0, 40), (1.5, 2.0, 56)):
        shadow_rect = QRectF(card).adjusted(-expand, -expand, expand, expand)
        shadow_rect.translate(0, dy)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, radius + expand, radius + expand)
        p.fillPath(shadow_path, QColor(249, 184, 196, alpha))

    # 卡片：奶白 → 浅珊瑚 纵向渐变
    path = QPainterPath()
    path.addRoundedRect(card, radius, radius)
    grad = QLinearGradient(0, card.top(), 0, card.bottom())
    grad.setColorAt(0.0, QColor("#FFFBF8"))
    grad.setColorAt(1.0, QColor("#FFF0EA"))
    p.fillPath(path, grad)

    # 珊瑚粉边框（外）+ 内高光线
    stroke = QRectF(card).adjusted(0.5, 0.5, -0.5, -0.5)
    stroke_path = QPainterPath()
    stroke_path.addRoundedRect(stroke, radius, radius)
    p.setPen(QPen(QColor("#FFB4AB"), 2))
    p.drawPath(stroke_path)
    inner = QRectF(card).adjusted(2.5, 2.5, -2.5, -2.5)
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner, radius - 2, radius - 2)
    p.setPen(QPen(QColor(255, 255, 255, 160), 1))
    p.drawPath(inner_path)

    return card
