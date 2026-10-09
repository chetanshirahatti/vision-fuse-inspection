from __future__ import annotations
import datetime
import os
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QIcon, QGuiApplication
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QPushButton, QStackedWidget,
                               QButtonGroup, QMessageBox)
from ui.dashboard import DashboardPage
from ui.calibration import CalibrationPage
from ui.training import TrainingPage
from ui.history import HistoryPage
from ui.plc_page import PlcPage, STATUS_COL
from ui.settings_page import SettingsPage
from ui import theme
from ui.icons import nav_icon
from app_context import APP_DIR

PAGES = [("dashboard", "Dashboard", DashboardPage), ("calibration", "Calibration", CalibrationPage), ("training", "Training", TrainingPage),
         ("history", "History", HistoryPage), ("plc", "PLC / Modbus", PlcPage), ("settings", "Settings", SettingsPage)]


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("JRSS Vision Inspect")
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(scr.width() * 0.92), int(scr.height() * 0.92)); self.setMinimumSize(1000, 640)
        central = QWidget(); self.setCentralWidget(central)
        lay = QHBoxLayout(central); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(210)
        sl = QVBoxLayout(side); sl.setContentsMargins(12, 16, 12, 12); sl.setSpacing(4)
        logo_path = os.path.join(APP_DIR, "assets", "logo.png")
        pm = QPixmap(logo_path)
        if not pm.isNull():
            self.setWindowIcon(QIcon(logo_path))
            card = QFrame(); card.setStyleSheet("QFrame{background:white;border-radius:12px;border:none;}")
            cl = QVBoxLayout(card); cl.setContentsMargins(10, 10, 10, 10)
            logo = QLabel(); logo.setStyleSheet("background:transparent;")
            logo.setPixmap(pm.scaledToWidth(130, Qt.SmoothTransformation)); logo.setAlignment(Qt.AlignCenter)
            cl.addWidget(logo)
            sl.addWidget(card); sl.addSpacing(8)
            tag = QLabel("VISION INSPECT"); tag.setAlignment(Qt.AlignCenter)
            tag.setStyleSheet(f"font-size:12px;font-weight:700;letter-spacing:3px;color:{theme.MUTED};padding:2px 0 14px 0;")
            sl.addWidget(tag)
        else:
            logo = QLabel("◉  JRSS Vision Inspect"); logo.setStyleSheet(f"font-size:17px;font-weight:800;color:{theme.ACCENT};padding:4px 8px 14px 8px;")
            sl.addWidget(logo)
        self.stack = QStackedWidget(); self.group = QButtonGroup(self); self.group.setExclusive(True)
        for i, (icon, name, cls) in enumerate(PAGES):
            b = QPushButton("  " + name); b.setObjectName("nav"); b.setCheckable(True)
            b.setIcon(nav_icon(icon)); b.setIconSize(QSize(20, 20))
            b.setCursor(Qt.PointingHandCursor)
            self.group.addButton(b, i); sl.addWidget(b)
            self.stack.addWidget(cls(ctx))
        sl.addStretch()
        ver = QLabel("v1.0  ·  OpenCV + PySide6"); ver.setObjectName("muted"); sl.addWidget(ver)
        self.group.idClicked.connect(self.goto)
        lay.addWidget(side); lay.addWidget(self.stack, 1)

        sb = self.statusBar()
        self.s_recipe = QLabel(); self.s_plc = QLabel(); self.s_clock = QLabel()
        sb.addWidget(self.s_recipe, 1); sb.addPermanentWidget(self.s_plc); sb.addPermanentWidget(self.s_clock)
        ctx.recipeChanged.connect(self._recipe); ctx.plc.statusChanged.connect(self._plc); self._recipe(); self._plc(ctx.plc._status or "Disabled")
        t = QTimer(self); t.timeout.connect(lambda: self.s_clock.setText(datetime.datetime.now().strftime("  %Y-%m-%d  %H:%M:%S  "))); t.start(1000)

        self._menu()
        self.goto(0)

    def _menu(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        a = QAction("Exit", self); a.setShortcut(QKeySequence.Quit); a.triggered.connect(self.close); m.addAction(a)
        v = mb.addMenu("&View")
        for i, (_ic, name, _) in enumerate(PAGES):
            a = QAction(name, self); a.setShortcut(f"Ctrl+{i + 1}"); a.triggered.connect(lambda _=False, k=i: self.goto(k)); v.addAction(a)
        h = mb.addMenu("&Help")
        a = QAction("About", self); a.triggered.connect(lambda: QMessageBox.about(
            self, "About", "Fuse Vision Inspector\nMaster-image based visual inspection with Modbus TCP PLC link.")); h.addAction(a)

    def goto(self, i):
        self.stack.setCurrentIndex(i); self.group.button(i).setChecked(True)

    def _recipe(self):
        r = self.ctx.recipe
        self.s_recipe.setText(f"  Active recipe: {r.name}" if r else "  No recipe")

    def _plc(self, s):
        self.s_plc.setText(f"PLC: <span style='color:{STATUS_COL.get(s, theme.MUTED)}'>● {s}</span>  ")

    def closeEvent(self, e):
        self.ctx.shutdown(); super().closeEvent(e)
