
from __future__ import annotations
import os
import cv2
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox,
                               QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
                               QDoubleSpinBox, QSpinBox, QFormLayout, QAbstractItemView, QStackedWidget, QButtonGroup,
                               QInputDialog)
from core.recipe import Recipe, Roi
from core.imageio import read_image, limit_size
from core.cameras import open_source
from ui.widgets import ImageView
from ui import theme

TAB_STYLE = f"""
QPushButton {{ padding: 8px 26px; border-radius: 8px; font-weight: 600; background: {theme.PANEL2}; border: 1px solid {theme.BORDER}; }}
QPushButton:checked {{ background: {theme.ACCENT}; border-color: {theme.ACCENT}; color: white; }}
"""


class TrainingPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.master = None
        self.rois: list[Roi] = []
        self.loading = False

        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 12); root.setSpacing(12)

        # ---- header with the two tab buttons ----
        head = QHBoxLayout()
        t = QLabel("Training"); t.setObjectName("h1")
        head.addWidget(t); head.addStretch()
        self.tab_img = QPushButton("🖼  Master image")
        self.tab_cfg = QPushButton("⚙  Recipe && ROIs")
        self.tab_group = QButtonGroup(self); self.tab_group.setExclusive(True)
        for i, b in enumerate((self.tab_img, self.tab_cfg)):
            b.setCheckable(True); b.setCursor(Qt.PointingHandCursor); b.setStyleSheet(TAB_STYLE)
            self.tab_group.addButton(b, i); head.addWidget(b)
        self.tab_img.setChecked(True)
        self.tab_group.idClicked.connect(self._tab)
        root.addLayout(head)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)

        # ================= TAB 1: master image =================
        p0 = QWidget(); v = QVBoxLayout(p0); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(10)
        row = QHBoxLayout(); row.setSpacing(8)
        b = QPushButton("Load image…"); b.clicked.connect(self._load_image)
        c = QPushButton("Capture from camera"); c.clicked.connect(self._capture)
        row.addWidget(b); row.addWidget(c); row.addStretch()
        v.addLayout(row)
        hint = QLabel("Load or capture the master (golden) image, then drag on the picture to draw a ROI around each part/marking "
                      "to verify.   Wheel = zoom · right/middle drag = pan · double-click = fit")
        hint.setObjectName("muted"); hint.setWordWrap(True)
        v.addWidget(hint)
        self.view = ImageView(edit=True)
        self.view.roiDrawn.connect(self._roi_drawn); self.view.roiClicked.connect(self._roi_clicked)
        v.addWidget(self.view, 1)
        self.pages.addWidget(p0)

        # ================= TAB 2: recipe, ROIs, parameters =================
        p1 = QWidget(); h = QHBoxLayout(p1); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(16)
        left = QVBoxLayout(); left.setSpacing(10)
        g = QGroupBox("Recipe"); f = QFormLayout(g)
        self.name = QLineEdit(); self.name.setPlaceholderText("e.g. Fuse_80A_400A")
        self.combo = QComboBox()
        row = QHBoxLayout(); b1 = QPushButton("Load"); b2 = QPushButton("New")
        b1.clicked.connect(self._load_selected); b2.clicked.connect(self._new)
        row.addWidget(self.combo, 1); row.addWidget(b1); row.addWidget(b2)
        f.addRow("Name", self.name); f.addRow("Existing", row)
        left.addWidget(g)

        g = QGroupBox("Parameters"); f = QFormLayout(g)
        self.def_thr = QDoubleSpinBox(); self.def_thr.setRange(0.3, 0.99); self.def_thr.setSingleStep(0.01); self.def_thr.setValue(0.80)
        self.pad = QSpinBox(); self.pad.setRange(0, 80); self.pad.setValue(14)
        f.addRow("Default limit for new ROIs", self.def_thr); f.addRow("Search tolerance (px)", self.pad)
        left.addWidget(g)

        self.del_btn = QPushButton("Delete recipe"); self.del_btn.setProperty("kind", "danger"); self.del_btn.clicked.connect(self._delete_recipe)
        left.addWidget(self.del_btn); left.addStretch()
        h.addLayout(left, 2)

        g = QGroupBox("Regions of interest (ROI)"); l = QVBoxLayout(g)
        self.tbl = QTableWidget(0, 4); self.tbl.setHorizontalHeaderLabels(["Name", "Expected", "Limit", "Size"])
        self.tbl.verticalHeader().setVisible(False); self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.itemChanged.connect(self._table_edited); self.tbl.itemSelectionChanged.connect(self._table_selected)
        l.addWidget(self.tbl)
        row = QHBoxLayout(); d = QPushButton("Delete ROI"); d.setProperty("kind", "danger")
        cl = QPushButton("Clear all")
        d.clicked.connect(self._delete_roi); cl.clicked.connect(self._clear_rois)
        row.addWidget(d); row.addWidget(cl); l.addLayout(row)
        h.addWidget(g, 3)
        self.pages.addWidget(p1)

        # ---- bottom bar (visible on both tabs) ----
        bar = QHBoxLayout()
        self.roi_status = QLabel(""); self.roi_status.setObjectName("muted")
        self.save_btn = QPushButton("💾  Train && Save recipe"); self.save_btn.setProperty("kind", "accent")
        self.save_btn.setMinimumHeight(42); self.save_btn.setMinimumWidth(260); self.save_btn.clicked.connect(self._train)
        bar.addWidget(self.roi_status, 1); bar.addWidget(self.save_btn)
        root.addLayout(bar)

        ctx.recipeChanged.connect(self._refresh_combo)
        self._refresh_combo()
        if ctx.recipe:
            self._load_recipe(ctx.recipe.name)
        else:
            self._rebuild()

    def _tab(self, i):
        self.pages.setCurrentIndex(i)

    # ---- helpers ----
    def _refresh_combo(self):
        self.combo.clear(); self.combo.addItems(self.ctx.store.names())
        if self.ctx.recipe:
            self.combo.setCurrentText(self.ctx.recipe.name)

    def _load_recipe(self, name):
        r, m = self.ctx.store.load(name)
        self.name.setText(r.name); self.master = m.copy()
        self.rois = [Roi(**vars(x)) for x in r.rois]; self.pad.setValue(r.search_pad)
        self.view.set_image(self.master); self._rebuild()

    def _load_selected(self):
        if self.combo.currentText():
            self._load_recipe(self.combo.currentText())

    def _new(self):
        self.name.clear(); self.master = None; self.rois = []; self.view.clear(); self._rebuild()
        self.tab_img.click()                               # start a new recipe on the master-image tab

    def _set_master(self, img):
        img = limit_size(img, self.ctx.settings.max_side)
        self.master = img; self.view.set_image(img); self.rois = []; self._rebuild()

    def _load_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Master image", (os.path.join(self.ctx.data_dir, "captures", "master") if os.path.isdir(os.path.join(self.ctx.data_dir, "captures", "master")) else self.ctx.samples_dir), "Images (*.png *.jpg *.jpeg *.bmp)")
        if f:
            img = read_image(f)
            if img is None:
                QMessageBox.warning(self, "Load", "Could not read image."); return
            self._set_master(img)

    def _capture(self):
        try:
            from dataclasses import replace
            src = open_source(replace(self.ctx.settings, camera_trigger="software"))   # one picture on command
        except Exception as e:
            QMessageBox.warning(self, "Camera", str(e)); return
        try:
            frame = src.capture()
        except Exception as e:
            QMessageBox.warning(self, "Camera", str(e)); return
        finally:
            src.release()
        if frame is None:
            QMessageBox.warning(self, "Camera", "No frame received (timeout). Check lighting, trigger mode and connection."); return
        self._set_master(frame)

    # ---- ROI editing ----
    def _roi_drawn(self, x1, y1, x2, y2):
        names = {r.name for r in self.rois}
        default = f"ROI_{len(self.rois) + 1}"
        name, ok = QInputDialog.getText(self, "New ROI", "Name this region (e.g. FUSE_80A):", text=default)
        if not ok:
            return                                         # cancelled -> drop the box
        name = name.strip() or default
        base, k = name, 2
        while name in names:                               # keep names unique
            name = f"{base}_{k}"; k += 1
        self.rois.append(Roi(name, x1, y1, x2, y2, "", self.def_thr.value()))
        self._rebuild(select=len(self.rois) - 1)

    def _roi_clicked(self, i):
        self.tbl.selectRow(i)

    def _rebuild(self, select=-1):
        self.loading = True
        self.tbl.setRowCount(len(self.rois))
        for i, r in enumerate(self.rois):
            vals = [r.name, r.expected, f"{r.threshold:.2f}", f"{r.x2 - r.x1}×{r.y2 - r.y1}"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 3:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tbl.setItem(i, j, it)
        self.loading = False
        if select >= 0:
            self.tbl.selectRow(select)
        self.view.set_rois(self.rois, select)
        n = len(self.rois)
        self.tab_cfg.setText(f"⚙  Recipe && ROIs ({n})")
        self.roi_status.setText(f"{n} ROI{'s' if n != 1 else ''} drawn" +
                                ("  ·  set expected text and limits in the 'Recipe & ROIs' tab" if n else "  ·  drag on the master image to add one"))

    def _table_edited(self, it):
        if self.loading:
            return
        r = self.rois[it.row()]
        if it.column() == 0:
            r.name = it.text().strip() or r.name
        elif it.column() == 1:
            r.expected = it.text().strip()
        elif it.column() == 2:
            try:
                r.threshold = max(0.3, min(0.99, float(it.text())))
            except ValueError:
                pass
            self.loading = True; it.setText(f"{r.threshold:.2f}"); self.loading = False
        self.view.set_rois(self.rois, self.tbl.currentRow())

    def _table_selected(self):
        self.view.set_rois(self.rois, self.tbl.currentRow())

    def _delete_roi(self):
        i = self.tbl.currentRow()
        if 0 <= i < len(self.rois):
            del self.rois[i]; self._rebuild()

    def _clear_rois(self):
        self.rois = []; self._rebuild()

    # ---- train / save ----
    def _train(self):
        name = self.name.text().strip()
        if self.master is None:
            self.tab_img.click()
            QMessageBox.warning(self, "Train", "Load or capture a master image first."); return
        if not self.rois:
            self.tab_img.click()
            QMessageBox.warning(self, "Train", "Draw at least one ROI on the master image."); return
        if not name:
            self.tab_cfg.click(); self.name.setFocus()      # the recipe name lives on the second tab
            QMessageBox.warning(self, "Train", "Enter a recipe name."); return
        if len({r.name for r in self.rois}) != len(self.rois):
            self.tab_cfg.click()
            QMessageBox.warning(self, "Train", "ROI names must be unique."); return
        if name in self.ctx.store.names():
            if QMessageBox.question(self, "Overwrite", f"Recipe '{name}' exists. Overwrite?") != QMessageBox.Yes:
                return
        old = self.ctx.store.load(name)[0] if name in self.ctx.store.names() else None
        rec = Recipe(name, [Roi(**vars(r)) for r in self.rois], search_pad=self.pad.value())
        if old:
            rec.created = old.created
        self.ctx.save_recipe(rec, self.master)
        QMessageBox.information(self, "Training complete",
                                f"Recipe '{name}' saved with {len(rec.rois)} ROI(s) and is now active.\n\n"
                                "Next: open Calibration to verify the limits with OK / NOK images.")

    def _delete_recipe(self):
        n = self.combo.currentText()
        if n and QMessageBox.question(self, "Delete", f"Delete recipe '{n}'?") == QMessageBox.Yes:
            self.ctx.delete_recipe(n); self._new()
