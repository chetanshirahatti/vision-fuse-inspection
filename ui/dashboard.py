
from __future__ import annotations
import os
import cv2
from core.imageio import read_image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QMenu, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QFileDialog,
                               QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QStackedWidget, QButtonGroup,
                               QMessageBox, QAbstractItemView)
from PySide6.QtGui import QColor
from core.calibrate import list_images
from core.cameras import open_source
from core.imageio import write_image
import datetime as _dt
from ui.widgets import ImageView, Card, Verdict
from ui import theme

MODES = ["Image file", "Folder", "Camera"]

TAB_STYLE = f"""
QPushButton {{ padding: 8px 26px; border-radius: 8px; font-weight: 600; background: {theme.PANEL2}; border: 1px solid {theme.BORDER}; }}
QPushButton:checked {{ background: {theme.ACCENT}; border-color: {theme.ACCENT}; color: white; }}
"""


class DashboardPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.files, self.idx = [], -1
        self.cap = None
        self.frame = None
        self.cam_timer = QTimer(self); self.cam_timer.timeout.connect(self._cam_tick)
        self.auto_timer = QTimer(self); self.auto_timer.timeout.connect(self._auto_tick)

        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 12); root.setSpacing(12)

        # ---- header: title, recipe, and the two tab buttons ----
        head = QHBoxLayout()
        t = QLabel("Dashboard"); t.setObjectName("h1")
        self.recipe_lbl = QLabel(); self.recipe_lbl.setObjectName("muted")
        self.recipe_box = QComboBox(); self.recipe_box.setMinimumWidth(220)
        self.recipe_box.activated.connect(self._pick_recipe)
        head.addWidget(t); head.addSpacing(12); head.addWidget(QLabel("Recipe:")); head.addWidget(self.recipe_box)
        head.addWidget(self.recipe_lbl); head.addStretch()
        self.tab_live, self.tab_results = QPushButton("●  Live"), QPushButton("☰  Results")
        self.tab_group = QButtonGroup(self); self.tab_group.setExclusive(True)
        for i, b in enumerate((self.tab_live, self.tab_results)):
            b.setCheckable(True); b.setCursor(Qt.PointingHandCursor); b.setStyleSheet(TAB_STYLE)
            self.tab_group.addButton(b, i); head.addWidget(b)
        self.tab_live.setChecked(True)
        self.tab_group.idClicked.connect(self._tab)
        root.addLayout(head)

        # ---- counters (always visible) + PASS/FAIL banner (Live tab only) ----
        self.kp = kp = QHBoxLayout(); kp.setSpacing(12)
        self.k_total, self.k_ok = Card("TOTAL", "0"), Card("PASS", "0", theme.OK)
        self.k_nok, self.k_yield = Card("NOK", "0", theme.NOK), Card("YIELD", "-")
        self.k_ms = Card("CYCLE TIME", "-")
        for k in (self.k_total, self.k_ok, self.k_nok, self.k_yield, self.k_ms):
            kp.addWidget(k)
        self.verdict = Verdict(); self.verdict.setMinimumWidth(260)
        kp.addWidget(self.verdict, 1)
        kp.addStretch(0)
        self._spacer_idx = kp.count() - 1
        root.addLayout(kp)

        # ---- tab pages ----
        self.pages = QStackedWidget()
        # page 0: LIVE - one big picture
        self.live_view = ImageView()
        self.pages.addWidget(self.live_view)
        # page 1: RESULTS - ROI table + recent list
        res_page = QWidget(); rl = QHBoxLayout(res_page); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(16)
        left = QVBoxLayout()
        lb = QLabel("ROI RESULTS"); lb.setObjectName("h2"); left.addWidget(lb)
        self.roi_tbl = self._table(["ROI", "Expect", "Score", "Limit", "Result"])
        self.roi_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        left.addWidget(self.roi_tbl, 1)
        self.reason = QLabel(""); self.reason.setObjectName("muted"); self.reason.setWordWrap(True)
        left.addWidget(self.reason)
        rl.addLayout(left, 3)
        right = QVBoxLayout()
        lb = QLabel("RECENT"); lb.setObjectName("h2"); right.addWidget(lb)
        self.recent = self._table(["Time", "Source", "Result"])
        right.addWidget(self.recent, 1)
        rl.addLayout(right, 2)
        self.pages.addWidget(res_page)
        root.addWidget(self.pages, 1)

        # ---- bottom control bar ----
        bar = QHBoxLayout(); bar.setSpacing(8)
        self.mode = QComboBox(); self.mode.addItems(MODES); self.mode.currentIndexChanged.connect(self._mode_changed)
        self.btn_open = QPushButton("Open…"); self.btn_open.clicked.connect(self._open)
        self.btn_prev, self.btn_next = QPushButton("◀"), QPushButton("▶")
        self.btn_prev.clicked.connect(lambda: self._step(-1)); self.btn_next.clicked.connect(lambda: self._step(1))
        self.btn_cam = QPushButton("Start camera"); self.btn_cam.clicked.connect(self._toggle_cam)
        self.btn_save = QPushButton("📷 Save frame ▾")
        m = QMenu(self.btn_save)
        for label, sub in (("Save as OK sample (good part)", "OK"), ("Save as NOK sample (bad part)", "NOK"), ("Save as master candidate", "master")):
            m.addAction(label, lambda sub=sub: self._save_frame(sub))
        self.btn_save.setMenu(m)
        self.src_lbl = QLabel("No source"); self.src_lbl.setObjectName("muted")
        self.btn_inspect = QPushButton("▶  INSPECT"); self.btn_inspect.setProperty("kind", "accent")
        self.btn_inspect.clicked.connect(self.inspect_current)
        self.chk_auto = QCheckBox("Auto-run"); self.chk_auto.toggled.connect(self._auto_toggled)
        self.btn_reset = QPushButton("Reset counters"); self.btn_reset.clicked.connect(self._reset)
        for w in (QLabel("Source:"), self.mode, self.btn_open, self.btn_prev, self.btn_next, self.btn_cam, self.btn_save, self.src_lbl):
            bar.addWidget(w)
        bar.addStretch()
        for w in (self.chk_auto, self.btn_reset, self.btn_inspect):
            bar.addWidget(w)
        root.addLayout(bar)

        ctx.recipeChanged.connect(self._recipe_changed)
        ctx.plc.triggered.connect(self._on_plc_trigger)
        self._recipe_changed(); self._mode_changed(0); self._tab(0)
        self.btn_inspect.setMinimumHeight(40)

    def _table(self, cols):
        t = QTableWidget(0, len(cols)); t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection); t.setAlternatingRowColors(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return t

    # ---- tabs ----
    def _tab(self, i):
        self.pages.setCurrentIndex(i)
        self.verdict.setVisible(i == 0)                       # PASS/FAIL banner only on the Live tab
        self.kp.setStretch(self._spacer_idx, 0 if i == 0 else 1)

    # ---- recipe ----
    def _pick_recipe(self, i):
        name = self.recipe_box.itemText(i)
        if name and (self.ctx.recipe is None or name != self.ctx.recipe.name):
            self.ctx.load_recipe(name)

    def _recipe_changed(self):
        c = self.ctx
        self.recipe_box.blockSignals(True)
        self.recipe_box.clear(); self.recipe_box.addItems(c.store.names())
        if c.recipe:
            self.recipe_box.setCurrentText(c.recipe.name)
        self.recipe_box.blockSignals(False)
        if c.recipe is None:
            self.recipe_lbl.setText("No recipe - create one in Training"); return
        self.recipe_lbl.setText(f"{len(c.recipe.rois)} ROIs")
        self.live_view.clear(); self.verdict.set_state("idle"); self.roi_tbl.setRowCount(0); self.reason.setText("")

    # ---- source handling ----
    def _mode_changed(self, i):
        self._stop_cam()
        m = MODES[i]
        self.btn_open.setVisible(m != "Camera"); self.btn_open.setText("Open image…" if m == "Image file" else "Open folder…")
        self.btn_prev.setVisible(m == "Folder"); self.btn_next.setVisible(m == "Folder")
        self.btn_cam.setVisible(m == "Camera"); self.btn_save.setVisible(m == "Camera")
        self.files, self.idx = [], -1
        self.src_lbl.setText("No source")
        if m == "Camera":
            self._cam_labels()
        if m == "Folder" and os.path.isdir(self.ctx.samples_dir):
            self._load_folder(self.ctx.samples_dir)

    def _open(self):
        if self.mode.currentText() == "Image file":
            f, _ = QFileDialog.getOpenFileName(self, "Open image", self.ctx.samples_dir, "Images (*.png *.jpg *.jpeg *.bmp)")
            if f:
                self.files, self.idx = [f], 0; self._show_src(); self.inspect_current()
        else:
            d = QFileDialog.getExistingDirectory(self, "Open image folder", self.ctx.samples_dir)
            if d:
                self._load_folder(d)

    def _load_folder(self, d):
        self.files = list_images(d)
        if not self.files:   # allow parent folders such as samples/ (OK + NOK sub-folders)
            for sub in sorted(os.listdir(d)):
                p = os.path.join(d, sub)
                if os.path.isdir(p):
                    self.files += list_images(p)
        self.idx = 0 if self.files else -1
        self._show_src()

    def _show_src(self):
        if self.idx >= 0:
            self.src_lbl.setText(f"{self.idx + 1}/{len(self.files)}  {os.path.basename(self.files[self.idx])}")
        else:
            self.src_lbl.setText("No images found")

    def _step(self, d):
        if self.files:
            self.idx = (self.idx + d) % len(self.files); self._show_src(); self.inspect_current()

    def _cam_mode(self):
        return self.cap.mode if self.cap is not None else self.ctx.settings.camera_trigger

    def _cam_labels(self):
        m = self._cam_mode(); on = self.cap is not None
        self.btn_cam.setText(("Disarm camera" if on else "Arm camera") if m != "continuous" else ("Stop camera" if on else "Start camera"))
        self.src_lbl.setText({"continuous": "Camera live" if on else "Camera stopped",
                              "software": "Armed - INSPECT / PLC trigger takes ONE picture" if on else "Camera not armed",
                              "hardware": "Armed - waiting for hardware pulse" if on else "Camera not armed"}[m])

    def _open_camera(self):
        try:
            self.cap = open_source(self.ctx.settings)
        except Exception as e:
            self.cap = None
            QMessageBox.warning(self, "Camera", str(e)); return False
        self.cam_timer.start(100 if self.cap.mode != "software" else 1000)
        self.src_lbl.setToolTip(self.cap.describe()); self._cam_labels()
        return True

    def _toggle_cam(self):
        if self.cap is None:
            self._open_camera()
        else:
            self._stop_cam()

    def _stop_cam(self):
        self.cam_timer.stop()
        if self.cap is not None:
            self.cap.release(); self.cap = None
        self.frame = None; self._cam_labels()

    def _cam_tick(self):
        if self.cap is None:
            return
        try:
            f = self.cap.preview()
        except Exception as e:
            self._stop_cam(); QMessageBox.warning(self, "Camera", str(e)); return
        if f is None:
            return
        self.frame = f
        if self.cap.mode == "hardware":              # a pulse fired the camera -> inspect that picture right away
            self._inspect_img(f, "camera (pulse)")
        elif not self.chk_auto.isChecked():
            self.live_view.set_image(f)

    def _save_frame(self, sub):
        if self.cap is None:
            QMessageBox.information(self, "Save frame", "Start the camera first."); return
        try:
            img = self.cap.capture()
        except Exception as e:
            QMessageBox.warning(self, "Camera", str(e)); return
        if img is None:
            QMessageBox.warning(self, "Save frame", "No picture received (timeout)."); return
        d = os.path.join(self.ctx.data_dir, "captures", sub); os.makedirs(d, exist_ok=True)
        path = os.path.join(d, _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3] + ".png")
        write_image(path, img)
        n = len([f for f in os.listdir(d) if f.endswith(".png")])
        self.src_lbl.setText(f"Saved to captures/{sub}  ({n} total)")

    # ---- inspection ----
    def _current_image(self):
        if self.mode.currentText() == "Camera":
            if self.cap is None and not self._open_camera():      # arm the camera automatically on first use
                return None, "camera"
            try:
                self.frame = self.cap.capture()          # ONE fresh picture (fires the trigger in software mode)
            except Exception as e:
                QMessageBox.warning(self, "Camera", str(e)); return None, "camera"
            return self.frame, "camera"
        if self.idx >= 0:
            p = self.files[self.idx]
            return read_image(p), os.path.basename(p)
        return None, ""

    def inspect_current(self):
        c = self.ctx
        if c.inspector is None:
            QMessageBox.information(self, "Inspect", "No recipe loaded. Train one first."); return
        img, src = self._current_image()
        if img is None:
            self.auto_timer.stop(); self.chk_auto.setChecked(False)
            QMessageBox.information(self, "Inspect", "No picture received. Open a file/folder, or check the camera, trigger and lighting."); return
        self._inspect_img(img, src)

    def _inspect_img(self, img, src):
        res, ann = self.ctx.run_inspection(img, src)
        self.live_view.set_image(ann)
        self.verdict.set_state(res.status)
        self._fill(res)

    def _fill(self, res):
        t = self.roi_tbl; t.setRowCount(len(res.rois))
        for i, r in enumerate(res.rois):
            vals = [r.name, r.expected, f"{r.score:.2f}", f"{r.threshold:.2f}", "OK" if r.ok else "NOK"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 4:
                    it.setForeground(QColor(theme.OK if r.ok else theme.NOK))
                t.setItem(i, j, it)
        self.reason.setText(res.reason or f"All ROIs match the master  ·  {res.matches} alignment features")
        s = self.ctx.stats
        self.k_total.set(str(s["total"])); self.k_ok.set(str(s["ok"])); self.k_nok.set(str(s["nok"]))
        self.k_yield.set(f'{100 * s["ok"] / s["total"]:.0f}%' if s["total"] else "-")
        self.k_ms.set(f"{res.ms:.0f} ms")
        rt = self.recent; rt.insertRow(0)
        import datetime
        for j, v in enumerate([datetime.datetime.now().strftime("%H:%M:%S"), self._current_image_name(), res.status]):
            it = QTableWidgetItem(v)
            if j == 2:
                it.setForeground(QColor(theme.OK if res.status == "PASS" else theme.NOK))
            rt.setItem(0, j, it)
        while rt.rowCount() > 30:
            rt.removeRow(rt.rowCount() - 1)

    def _current_image_name(self):
        return "camera" if self.mode.currentText() == "Camera" else (os.path.basename(self.files[self.idx]) if self.idx >= 0 else "")

    def _auto_toggled(self, on):
        if on:
            self.auto_timer.start(self.ctx.settings.auto_interval_ms)
        else:
            self.auto_timer.stop()

    def _auto_tick(self):
        if self.mode.currentText() == "Folder" and self.files:
            self._step(1)
        else:
            self.inspect_current()

    def _on_plc_trigger(self):
        if self.mode.currentText() == "Camera" and self._cam_mode() == "hardware":
            return                               # the electrical pulse itself triggers the picture
        self.inspect_current()

    def _reset(self):
        self.ctx.reset_stats()
        for k, v in ((self.k_total, "0"), (self.k_ok, "0"), (self.k_nok, "0"), (self.k_yield, "-"), (self.k_ms, "-")):
            k.set(v)
        self.recent.setRowCount(0)

    def closeEvent(self, e):
        self._stop_cam()
        super().closeEvent(e)