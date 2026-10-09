from __future__ import annotations
import csv, os
import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QFileDialog, QSplitter, QAbstractItemView, QMessageBox)
from ui.widgets import ImageView
from ui import theme


class HistoryPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx; self.rows = []
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 12); root.setSpacing(10)
        head = QHBoxLayout(); t = QLabel("History"); t.setObjectName("h1")
        self.flt = QComboBox(); self.flt.addItems(["All", "PASS", "NOK"]); self.flt.currentIndexChanged.connect(self.refresh)
        b_ref = QPushButton("Refresh"); b_ref.clicked.connect(self.refresh)
        b_exp = QPushButton("Export CSV…"); b_exp.clicked.connect(self._export)
        b_dir = QPushButton("Open data folder"); b_dir.clicked.connect(self._open_dir)
        head.addWidget(t); head.addStretch(); head.addWidget(QLabel("Filter:")); head.addWidget(self.flt)
        head.addWidget(b_ref); head.addWidget(b_exp); head.addWidget(b_dir)
        root.addLayout(head)
        split = QSplitter(Qt.Horizontal)
        self.tbl = QTableWidget(0, 5); self.tbl.setHorizontalHeaderLabels(["Time", "Recipe", "Source", "Result", "Scores"])
        self.tbl.verticalHeader().setVisible(False); self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows); self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.itemSelectionChanged.connect(self._selected)
        split.addWidget(self.tbl)
        pv = QWidget(); pl = QVBoxLayout(pv); pl.setContentsMargins(8, 0, 0, 0)
        pl.addWidget(QLabel("SAVED IMAGE (NOK results)", objectName="h2"))
        self.view = ImageView(); pl.addWidget(self.view, 1)
        split.addWidget(pv); split.setStretchFactor(0, 3); split.setStretchFactor(1, 2)
        root.addWidget(split, 1)
        ctx.historyChanged.connect(self.refresh); self.refresh()

    def refresh(self):
        rows = self.ctx.history.read(500)
        f = self.flt.currentText()
        self.rows = [r for r in rows if f == "All" or r["status"] == f]
        self.tbl.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            for j, k in enumerate(["time", "recipe", "source", "status", "details"]):
                it = QTableWidgetItem(r[k])
                if k == "status":
                    it.setForeground(QColor(theme.OK if r[k] == "PASS" else theme.NOK))
                self.tbl.setItem(i, j, it)

    def _selected(self):
        i = self.tbl.currentRow()
        if 0 <= i < len(self.rows):
            p = self.rows[i].get("image", "")
            img = cv2.imread(p) if p and os.path.isfile(p) else None
            if img is not None:
                self.view.set_image(img)
            else:
                self.view.clear()

    def _export(self):
        f, _ = QFileDialog.getSaveFileName(self, "Export CSV", "inspection_results.csv", "CSV (*.csv)")
        if f and self.rows:
            with open(f, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, list(self.rows[0].keys())); w.writeheader(); w.writerows(self.rows)
            QMessageBox.information(self, "Export", f"{len(self.rows)} rows exported.")

    def _open_dir(self):
        d = self.ctx.history.root
        if os.name == "nt":
            os.startfile(d)
        else:
            import subprocess; subprocess.Popen(["xdg-open", d])
