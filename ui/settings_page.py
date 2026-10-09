from __future__ import annotations
import time
from dataclasses import replace
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
                               QGroupBox, QFormLayout, QMessageBox, QComboBox, QLineEdit, QDialog, QApplication)
from core.cameras import open_source
from ui.widgets import cv_to_pixmap


class SettingsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx; s = ctx.settings
        root = QVBoxLayout(self); root.setContentsMargins(20, 16, 20, 12); root.setSpacing(12)
        t = QLabel("Settings"); t.setObjectName("h1"); root.addWidget(t)

        g = QGroupBox("Camera"); f = QFormLayout(g)
        self.src = QComboBox(); self.src.addItems(["USB webcam", "MindVision GigE camera"])
        self.src.setCurrentIndex(1 if s.camera_source == "mindvision" else 0)
        self.cam = QSpinBox(); self.cam.setRange(0, 10); self.cam.setValue(s.camera_index)
        self.trig = QComboBox(); self.trig.addItems(["Software trigger - ONE picture per command (recommended)",
                            "Hardware trigger - ONE picture per external pulse",
                            "Continuous - live stream (setup/focusing only)"])
        self.trig.setCurrentIndex({"software": 0, "hardware": 1, "continuous": 2}.get(s.camera_trigger, 0))
        self.edge = QComboBox(); self.edge.addItems(["Rising edge", "Falling edge"])
        self.edge.setCurrentIndex(1 if s.camera_hw_edge == "falling" else 0)
        self.exp = QDoubleSpinBox(); self.exp.setRange(0.05, 2000); self.exp.setDecimals(2); self.exp.setSuffix(" ms"); self.exp.setValue(s.camera_exposure_ms)
        self.tmo = QSpinBox(); self.tmo.setRange(200, 30000); self.tmo.setSuffix(" ms"); self.tmo.setValue(s.camera_timeout_ms)
        self.maxs = QSpinBox(); self.maxs.setRange(0, 10000); self.maxs.setSingleStep(100); self.maxs.setSpecialValueText("off"); self.maxs.setValue(s.camera_max_side)
        self.res = QSpinBox(); self.res.setRange(-1, 40); self.res.setSpecialValueText("camera default"); self.res.setValue(s.camera_resolution_index)
        self.sdk = QLineEdit(s.mindvision_sdk_dir)
        f.addRow("Camera type", self.src); f.addRow("Camera index (0 = first)", self.cam); f.addRow("Trigger mode", self.trig); f.addRow("Hardware pulse edge", self.edge)
        f.addRow("Exposure (MindVision)", self.exp); f.addRow("Wait for picture (timeout)", self.tmo)
        f.addRow("Shrink pictures to longest side", self.maxs); f.addRow("Resolution preset (MindVision)", self.res)
        f.addRow("MindVision SDK folder", self.sdk)
        hint = QLabel("Close the MindVision viewer before using the camera here - only one program can open it at a time. With a software or hardware trigger the camera sends NO live stream, only one picture per trigger. "
                      "A 20 MP picture is slow to inspect, so keep 'shrink' at about 2000 and use the same settings for training and running.")
        hint.setObjectName("muted"); hint.setWordWrap(True); f.addRow(hint)
        row = QHBoxLayout(); tb = QPushButton("Test camera"); tb.clicked.connect(self._test)
        row.addWidget(tb); row.addStretch(); f.addRow(row)
        root.addWidget(g)

        g = QGroupBox("Automation"); f = QFormLayout(g)
        self.auto = QSpinBox(); self.auto.setRange(200, 60000); self.auto.setSingleStep(100); self.auto.setSuffix(" ms"); self.auto.setValue(s.auto_interval_ms)
        self.nok = QCheckBox("Save an annotated image for every NOK result"); self.nok.setChecked(s.save_nok_images)
        f.addRow("Auto-run interval", self.auto); f.addRow(self.nok)
        root.addWidget(g)

        g = QGroupBox("Data"); l = QVBoxLayout(g)
        lab = QLabel(f"Recipes, history and settings are stored in:<br><b>{ctx.data_dir}</b>"); lab.setWordWrap(True); l.addWidget(lab)
        root.addWidget(g)
        b = QPushButton("Save settings"); b.setProperty("kind", "accent"); b.setMinimumHeight(38); b.clicked.connect(self._save)
        root.addWidget(b); root.addStretch()

    def _apply(self):
        s = self.ctx.settings
        s.camera_source = "mindvision" if self.src.currentIndex() == 1 else "webcam"
        s.camera_index, s.camera_trigger = self.cam.value(), ["software", "hardware", "continuous"][self.trig.currentIndex()]
        s.camera_hw_edge = "falling" if self.edge.currentIndex() == 1 else "rising"
        s.camera_exposure_ms, s.camera_timeout_ms = self.exp.value(), self.tmo.value()
        s.camera_max_side, s.camera_resolution_index = self.maxs.value(), self.res.value()
        s.mindvision_sdk_dir = self.sdk.text().strip()
        s.auto_interval_ms, s.save_nok_images = self.auto.value(), self.nok.isChecked()
        self.ctx.save_settings()

    def _save(self):
        self._apply()
        QMessageBox.information(self, "Settings", "Saved. Restart the camera on the Dashboard for camera changes to apply.")

    def _test(self):
        self._apply()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            src = open_source(replace(self.ctx.settings, camera_trigger="software"))   # test = one picture on command
            try:
                t0 = time.perf_counter(); img = src.capture(); ms = (time.perf_counter() - t0) * 1000
                info = src.describe(); presets = getattr(src, "presets", [])
            finally:
                src.release()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Camera test failed", str(e)); return
        QApplication.restoreOverrideCursor()
        if img is None:
            QMessageBox.warning(self, "Camera test", "The camera opened but sent no picture before the timeout.\n"
                                "Try a longer timeout, a smaller resolution preset, or check the cable/IP.")
            return
        d = QDialog(self); d.setWindowTitle("Camera test OK"); lay = QVBoxLayout(d)
        txt = f"{info}\nPicture {img.shape[1]}×{img.shape[0]} px, received in {ms:.0f} ms"
        if presets:
            txt += "\n\nResolution presets (enter the number in 'Resolution preset'):\n" + "\n".join(presets[:12])
        lb = QLabel(txt); lb.setWordWrap(True); lay.addWidget(lb)
        pic = QLabel(); pic.setPixmap(cv_to_pixmap(img).scaled(720, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)); lay.addWidget(pic)
        ok = QPushButton("Close"); ok.clicked.connect(d.accept); lay.addWidget(ok); d.exec()
