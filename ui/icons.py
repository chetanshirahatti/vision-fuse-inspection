"""Crisp, consistent vector nav icons drawn with QPainter (no font/emoji dependence)."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon, QBrush


def _pix(draw, color, size=22, scale=2):
    pm = QPixmap(size * scale, size * scale); pm.fill(Qt.transparent); pm.setDevicePixelRatio(scale)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    pen = QPen(QColor(color), 1.9); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.NoBrush)
    draw(p, QColor(color)); p.end()
    return pm


def _dashboard(p, c):
    for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
        p.drawRoundedRect(QRectF(x, y, 8, 8), 2, 2)

def _calibration(p, c):
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5); p.drawEllipse(QPointF(12, 12), 3.5, 3.5)
    for a, b, x, y in ((12, 1.5, 12, 5), (12, 19, 12, 22.5), (1.5, 12, 5, 12), (19, 12, 22.5, 12)):
        p.drawLine(QPointF(a, b), QPointF(x, y))

def _training(p, c):
    p.drawRect(QRectF(5, 6, 14, 12))
    p.setBrush(QBrush(c))
    for x, y in ((5, 6), (19, 6), (5, 18), (19, 18)):
        p.drawRect(QRectF(x - 2, y - 2, 4, 4))

def _history(p, c):
    for y in (6, 12, 18):
        p.drawPoint(QPointF(4.5, y)); p.drawLine(QPointF(9, y), QPointF(21, y))
    pen = p.pen(); pen.setWidthF(3.2); p.setPen(pen)
    for y in (6, 12, 18):
        p.drawPoint(QPointF(4.5, y))

def _plc(p, c):
    p.drawLine(QPointF(3, 8), QPointF(20, 8)); p.drawLine(QPointF(16, 4), QPointF(20, 8)); p.drawLine(QPointF(16, 12), QPointF(20, 8))
    p.drawLine(QPointF(21, 16), QPointF(4, 16)); p.drawLine(QPointF(8, 12), QPointF(4, 16)); p.drawLine(QPointF(8, 20), QPointF(4, 16))

def _settings(p, c):
    for y, x in ((6, 15), (12, 8), (18, 16)):
        p.drawLine(QPointF(3, y), QPointF(21, y))
        p.setBrush(QBrush(QColor("#171d27"))); p.drawEllipse(QPointF(x, y), 2.8, 2.8); p.setBrush(Qt.NoBrush)

DRAWERS = dict(dashboard=_dashboard, calibration=_calibration, training=_training,
               history=_history, plc=_plc, settings=_settings)


def nav_icon(kind, normal="#8b96a8", active="#ffffff"):
    ic = QIcon(); d = DRAWERS[kind]
    ic.addPixmap(_pix(d, normal), QIcon.Normal, QIcon.Off)
    ic.addPixmap(_pix(d, active), QIcon.Normal, QIcon.On)
    return ic
