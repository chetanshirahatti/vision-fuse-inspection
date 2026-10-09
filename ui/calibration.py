from __future__ import annotations
import os
import cv2
from core.imageio import read_image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QFileDialog, QFrame,
                               QTabWidget, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                               QGroupBox, QApplication, QAbstractItemView)
from core import calibrate
from ui.widgets import ImageView, ScoreBar, cv_to_pixmap
from ui import theme


class RoiCard(QFrame):
    def __init__(self, roi, master, on_change):
        super().__init__()
        self.setObjectName("card"); self.roi = roi; self.on_change = on_change
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(12)
        thumb = QLabel(); x1, y1, x2, y2 = roi.rect
        crop = master[y1:y2, x1:x2]
        pm = cv_to_pixmap(crop).scaledToHeight(64, Qt.SmoothTransformation)
        thumb.setPixmap(pm); thumb.setFixedWidth(max(80, pm.width()))
        lay.addWidget(thumb)
        mid = QVBoxLayout(); mid.setSpacing(4)
        self.title = QLabel(f"<b>{roi.name}</b>  <span style='color:{theme.MUTED}'>expects “{roi.expected or '-'}” · {x2 - x1}×{y2 - y1}px</span>")
        self.title.setWordWrap(True)
        self.bar = ScoreBar()
        row = QHBoxLayout()
        self.sl = QSlider(Qt.Horizontal); self.sl.setRange(30, 99); self.sl.setValue(int(round(roi.threshold * 100)))
        self.val = QLabel(f"limit {roi.threshold:.2f}"); self.val.setMinimumWidth(70)
        self.sl.valueChanged.connect(self._moved)
        row.addWidget(self.sl, 1); row.addWidget(self.val)
        mid.addWidget(self.title); mid.addWidget(self.bar); mid.addLayout(row)
        lay.addLayout(mid, 1)
        self.verdict = QLabel("-"); self.verdict.setMinimumWidth(50); self.verdict.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.verdict)
        self.score = None

    def _moved(self, v):
        self.roi.threshold = v / 100
        self.val.setText(f"limit {self.roi.threshold:.2f}")
        self.set_score(self.score)
        self.on_change()

    def set_threshold(self, t):
        self.sl.setValue(int(round(t * 100)))

    def set_score(self, s):
        self.score = s
        self.bar.set(s, self.roi.threshold)
        if s is None:
            self.verdict.setText("-"); self.verdict.setStyleSheet("")
        else:
            ok = s >= self.roi.threshold
            self.verdict.setText("OK" if ok else "NOK")
            self.verdict.setStyleSheet(f"font-weight:700; color:{theme.OK if ok else theme.NOK};")


class CalibrationPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx; self.cards = []; self.suggestion = None
        root = QHBoxLayout(self); root.setContentsMargins(20, 16, 20, 12); root.setSpacing(16)

        left = QVBoxLayout()
        t = QLabel("Calibration"); t.setObjectName("h1")
        self.info = QLabel(); self.info.setObjectName("muted")
        self.tabs = QTabWidget()
        self.master_view, self.test_view = ImageView(), ImageView()
        self.tabs.addTab(self.master_view, "Trained master"); self.tabs.addTab(self.test_view, "Test result")
        left.addWidget(t); left.addWidget(self.info); left.addWidget(self.tabs, 1)
        root.addLayout(left, 3)

        right = QVBoxLayout(); right.setSpacing(10)
        h = QLabel("TRAINED REGIONS  ·  adjust limits and verify"); h.setObjectName("h2"); right.addWidget(h)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.holder = QWidget(); self.holder.setStyleSheet('background: transparent;'); self.vl = QVBoxLayout(self.holder); self.vl.setSpacing(8); self.vl.addStretch()
        self.scroll.setWidget(self.holder); right.addWidget(self.scroll, 1)

        g = QGroupBox("Verify && auto-calibrate"); gl = QVBoxLayout(g)
        row = QHBoxLayout()
        b1 = QPushButton("Test one image…"); b1.clicked.connect(self._test_one)
        b2 = QPushButton("Auto-calibrate from OK / NOK folders…"); b2.setProperty("kind", "accent"); b2.clicked.connect(self._auto)
        row.addWidget(b1); row.addWidget(b2); gl.addLayout(row)
        self.tbl = QTableWidget(0, 4); self.tbl.setHorizontalHeaderLabels(["Image", "Class", "Worst ROI", "Verdict"])
        self.tbl.verticalHeader().setVisible(False); self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        gl.addWidget(self.tbl)
        self.sugg = QLabel(""); self.sugg.setWordWrap(True); self.sugg.setObjectName("muted"); gl.addWidget(self.sugg)
        row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply suggested limit"); self.apply_btn.setEnabled(False); self.apply_btn.clicked.connect(self._apply)
        save = QPushButton("💾  Save limits"); save.setProperty("kind", "accent"); save.clicked.connect(self._save)
        row.addWidget(self.apply_btn); row.addWidget(save); gl.addLayout(row)
        right.addWidget(g, 2)
        root.addLayout(right, 2)
        ctx.recipeChanged.connect(self._rebuild); self._rebuild()

    def _rebuild(self):
        c = self.ctx
        for w in self.cards:
            w.setParent(None)
        self.cards = []; self.tbl.setRowCount(0); self.sugg.setText(""); self.apply_btn.setEnabled(False)
        if c.recipe is None:
            self.info.setText("No recipe trained yet."); self.master_view.clear(); return
        r = c.recipe
        self.info.setText(f"Recipe {r.name}  ·  trained {r.created or '-'}  ·  updated {r.updated or '-'}  ·  "
                          f"{r.img_w}×{r.img_h}px  ·  search tolerance {r.search_pad}px")
        self.master_view.set_image(c.master); self.master_view.set_rois(r.rois)
        for roi in r.rois:
            card = RoiCard(roi, c.master, self._limit_changed)
            self.vl.insertWidget(self.vl.count() - 1, card); self.cards.append(card)

    def _limit_changed(self):
        pass

    def _dir(self, sub):
        c = os.path.join(self.ctx.data_dir, "captures", sub)
        return c if os.path.isdir(c) else os.path.join(self.ctx.samples_dir, sub)

    def _need(self):
        if self.ctx.inspector is None:
            QMessageBox.information(self, "Calibration", "Train a recipe first."); return False
        return True

    def _test_one(self):
        if not self._need():
            return
        f, _ = QFileDialog.getOpenFileName(self, "Test image", self.ctx.samples_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
        if f:
            self.test_file(f)

    def test_file(self, path):
        img = read_image(path)
        res = self.ctx.inspector.inspect(img)
        from core.inspector import Inspector
        self.test_view.set_image(Inspector.annotate(res)); self.tabs.setCurrentIndex(1)
        for card, r in zip(self.cards, res.rois):
            card.set_score(r.score)
        return res

    def _auto(self):
        if not self._need():
            return
        d_ok = QFileDialog.getExistingDirectory(self, "Folder with known-GOOD (OK) images", self._dir("OK"))
        if not d_ok:
            return
        d_nok = QFileDialog.getExistingDirectory(self, "Folder with known-BAD (NOK) images (Cancel to skip)",
                                                 self._dir("NOK"))
        self.run_auto(d_ok, d_nok or None)

    def run_auto(self, d_ok, d_nok=None):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            insp = self.ctx.inspector
            ok_rows = calibrate.evaluate(insp, calibrate.list_images(d_ok), "OK")
            nok_rows = calibrate.evaluate(insp, calibrate.list_images(d_nok), "NOK") if d_nok else []
        finally:
            QApplication.restoreOverrideCursor()
        rows = ok_rows + nok_rows
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            good = bool(r["scores"]) and all(sc >= ro.threshold for sc, ro in zip(r["scores"], self.ctx.recipe.rois))
            right = (good and r["cls"] == "OK") or (not good and r["cls"] == "NOK")
            vals = [r["file"], r["cls"], f'{r["worst"]:.2f}', "as expected" if right else "WRONG"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 3:
                    it.setForeground(QColor(theme.OK if right else theme.NOK))
                self.tbl.setItem(i, j, it)
        self.suggestion, msg = calibrate.suggest(ok_rows, nok_rows)
        self.sugg.setText((f"Suggested limit: <b>{self.suggestion:.2f}</b> - " if self.suggestion else "") + msg)
        self.apply_btn.setEnabled(self.suggestion is not None)
        return ok_rows, nok_rows

    def _apply(self):
        if self.suggestion is not None:
            for c in self.cards:
                c.set_threshold(self.suggestion)

    def _save(self):
        if self._need():
            self.ctx.save_thresholds()
            QMessageBox.information(self, "Calibration", "Limits saved to the recipe.")
