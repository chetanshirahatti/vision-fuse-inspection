from __future__ import annotations
import cv2
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QImage, QPixmap, QPen, QColor, QBrush, QPainter, QFont
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem,
                               QFrame, QLabel, QVBoxLayout, QWidget)
from ui import theme


def cv_to_pixmap(img):
    rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB) if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())


class ImageView(QGraphicsView):
    """Zoom (wheel) / pan (drag) image viewer. In edit mode, left-drag draws a ROI."""
    roiDrawn = Signal(int, int, int, int)
    roiClicked = Signal(int)

    def __init__(self, edit=False, parent=None):
        super().__init__(parent)
        self.edit = edit
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix = self._scene.addPixmap(QPixmap())
        self._items = []
        self._rois = []
        self._sel = -1
        self._auto_fit = True
        self._size = (0, 0)
        self._start = None
        self._rubber = None
        self._pan = None
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        if edit:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setMinimumSize(220, 220)

    def clear(self):
        self._pix.setPixmap(QPixmap())
        self._size = (0, 0)
        self._clear_items()

    def set_image(self, img):
        pm = cv_to_pixmap(img)
        size = (pm.width(), pm.height())
        self._pix.setPixmap(pm)
        self._scene.setSceneRect(QRectF(pm.rect()))
        if size != self._size:
            self._size = size
            self._auto_fit = True
            self._rebuild()
        if self._auto_fit:
            self.fit()

    def set_rois(self, rois, selected=-1):
        self._rois, self._sel = list(rois), selected
        self._rebuild()

    def _clear_items(self):
        for it in self._items:
            self._scene.removeItem(it)
        self._items = []

    def _rebuild(self):
        self._clear_items()
        if not self._size[0]:
            return
        fsz = max(10, self._size[0] // 38)
        for i, r in enumerate(self._rois):
            col = QColor(theme.WARN if i == self._sel else theme.OK)
            pen = QPen(col, 2.5)
            pen.setCosmetic(True)
            item = QGraphicsRectItem(QRectF(r.x1, r.y1, r.x2 - r.x1, r.y2 - r.y1))
            item.setPen(pen)
            item.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 30)))
            self._scene.addItem(item)
            txt = QGraphicsSimpleTextItem(f"{i + 1}. {r.name}")
            f = QFont("Segoe UI")
            f.setPixelSize(fsz)
            f.setBold(True)
            txt.setFont(f)
            txt.setBrush(QBrush(col))
            txt.setPos(r.x1, max(0, r.y1 - fsz * 1.5))
            self._scene.addItem(txt)
            self._items += [item, txt]

    def fit(self):
        if self._size[0]:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._auto_fit:
            self.fit()

    def mouseDoubleClickEvent(self, e):
        self._auto_fit = True
        self.fit()

    def wheelEvent(self, e):
        self._auto_fit = False
        f = 1.2 if e.angleDelta().y() > 0 else 1 / 1.2
        self.scale(f, f)

    # ---- ROI drawing (edit mode) ----
    def mousePressEvent(self, e):
        if not self.edit:
            return super().mousePressEvent(e)
        if e.button() == Qt.LeftButton and self._size[0]:
            p = self.mapToScene(e.position().toPoint())
            hit = [i for i, r in enumerate(self._rois) if r.x1 <= p.x() <= r.x2 and r.y1 <= p.y() <= r.y2]
            self._start = p
            self._hit = hit[0] if hit else -1
            self._rubber = QGraphicsRectItem()
            pen = QPen(QColor(theme.ACCENT), 2, Qt.DashLine)
            pen.setCosmetic(True)
            self._rubber.setPen(pen)
            self._scene.addItem(self._rubber)
        elif e.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan = e.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if not self.edit:
            return super().mouseMoveEvent(e)
        if self._rubber is not None:
            p = self.mapToScene(e.position().toPoint())
            self._rubber.setRect(QRectF(self._start, p).normalized())
        elif self._pan is not None:
            d = e.position().toPoint() - self._pan
            self._pan = e.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())

    def mouseReleaseEvent(self, e):
        if not self.edit:
            return super().mouseReleaseEvent(e)
        if self._pan is not None:
            self._pan = None
            self.setCursor(Qt.CrossCursor)
        if self._rubber is not None:
            r = self._rubber.rect()
            self._scene.removeItem(self._rubber)
            self._rubber = None
            W, H = self._size
            x1, y1 = max(0, int(r.left())), max(0, int(r.top()))
            x2, y2 = min(W, int(r.right())), min(H, int(r.bottom()))
            if x2 - x1 >= 8 and y2 - y1 >= 8:
                self.roiDrawn.emit(x1, y1, x2, y2)
            elif self._hit >= 0:
                self.roiClicked.emit(self._hit)


class Card(QFrame):
    """KPI tile: small caption + big value."""
    def __init__(self, caption, value="-", color=None):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10); self.setMinimumWidth(130)
        lay.setSpacing(0)
        self.cap = QLabel(caption)
        self.cap.setObjectName("h2")
        self.val = QLabel(value)
        self.color = color
        self.val.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {color or theme.TEXT};")
        lay.addWidget(self.cap)
        lay.addWidget(self.val)

    def set(self, text, color=None):
        self.val.setText(text)
        c = color or self.color or theme.TEXT
        self.val.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {c};")


class Verdict(QLabel):
    def __init__(self):
        super().__init__("READY")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(64)
        self.set_state("idle")

    def set_state(self, state, text=None):
        col = {"idle": theme.PANEL2, "PASS": theme.OK, "NOK": theme.NOK}.get(state, theme.PANEL2)
        fg = theme.MUTED if state == "idle" else "white"
        label = text or {"idle": "READY", "PASS": "PASS  ✔  OK", "NOK": "FAIL  ✖  NOK"}[state]
        self.setText(label)
        self.setStyleSheet(f"background:{col}; color:{fg}; font-size:28px; font-weight:800; border-radius:10px;")


class ScoreBar(QWidget):
    """Horizontal bar showing a score with a threshold marker."""
    def __init__(self):
        super().__init__()
        self.score, self.thr = None, 0.8
        self.setMinimumHeight(22)

    def set(self, score, thr):
        self.score, self.thr = score, thr
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setBrush(QColor(theme.BORDER)); p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 4, w, h - 8, 5, 5)
        if self.score is not None:
            col = QColor(theme.OK if self.score >= self.thr else theme.NOK)
            p.setBrush(col)
            p.drawRoundedRect(0, 4, max(4, int(w * max(0, min(1, self.score)))), h - 8, 5, 5)
            p.setPen(QColor("white"))
            p.drawText(8, 0, w - 16, h, Qt.AlignVCenter | Qt.AlignLeft, f"{self.score:.2f}")
        p.setPen(QPen(QColor(theme.WARN), 2))
        x = int(w * self.thr)
        p.drawLine(x, 0, x, h)
