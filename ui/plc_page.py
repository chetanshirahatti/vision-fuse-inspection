from __future__ import annotations
import datetime
from dataclasses import replace
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSpinBox, QCheckBox,
                               QGroupBox, QFormLayout, QPlainTextEdit, QRadioButton, QMessageBox)
from ui import theme

STATUS_COL = {"Connected": theme.OK, "Simulation": theme.WARN, "Connecting": theme.WARN,
              "Error": theme.NOK, "Disabled": theme.MUTED}


class PlcPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx; c = ctx.settings.modbus
        root = QHBoxLayout(self); root.setContentsMargins(20, 16, 20, 12); root.setSpacing(16)

        left = QVBoxLayout(); left.setSpacing(10)
        t = QLabel("PLC / Modbus TCP"); t.setObjectName("h1"); left.addWidget(t)
        st = QHBoxLayout(); self.led = QLabel("●"); self.state = QLabel("Disabled"); self.state.setStyleSheet("font-size:16px;font-weight:600;")
        st.addWidget(self.led); st.addWidget(self.state); st.addStretch(); left.addLayout(st)

        g = QGroupBox("Connection"); f = QFormLayout(g)
        self.enabled = QCheckBox("Enable PLC communication"); self.enabled.setChecked(c.enabled)
        self.sim = QRadioButton("Simulation (no hardware)"); self.real = QRadioButton("Real PLC (Modbus TCP)")
        (self.sim if c.simulate else self.real).setChecked(True)
        self.host = QLineEdit(c.host)
        self.port = self._spin(c.port, 1, 65535); self.unit = self._spin(c.unit, 0, 247); self.poll = self._spin(c.poll_ms, 20, 5000)
        f.addRow(self.enabled); f.addRow(self.sim); f.addRow(self.real)
        f.addRow("IP address", self.host); f.addRow("Port", self.port); f.addRow("Unit / slave ID", self.unit); f.addRow("Poll interval (ms)", self.poll)
        left.addWidget(g)

        g = QGroupBox("Holding register map (0-based)"); f = QFormLayout(g)
        self.r_trig = self._spin(c.reg_trigger); self.r_res = self._spin(c.reg_result); self.r_mask = self._spin(c.reg_mask)
        self.r_done = self._spin(c.reg_done); self.r_hb = self._spin(c.reg_heartbeat)
        self.v_ok = self._spin(c.val_ok, 0, 65535); self.v_nok = self._spin(c.val_nok, 0, 65535)
        f.addRow("Trigger  (PLC → app)", self.r_trig); f.addRow("Result  (app → PLC)", self.r_res)
        f.addRow("Failed-ROI bitmask", self.r_mask); f.addRow("Done flag", self.r_done); f.addRow("Heartbeat", self.r_hb)
        f.addRow("Value for OK", self.v_ok); f.addRow("Value for NOK", self.v_nok)
        left.addWidget(g)

        row = QHBoxLayout()
        ap = QPushButton("Apply && connect"); ap.setProperty("kind", "accent"); ap.setMinimumHeight(38); ap.clicked.connect(self._apply)
        tr = QPushButton("Manual trigger"); tr.clicked.connect(ctx.plc.manual_trigger)
        row.addWidget(ap); row.addWidget(tr); left.addLayout(row); left.addStretch()
        root.addLayout(left, 2)

        right = QVBoxLayout()
        g = QGroupBox("How it works"); gl = QVBoxLayout(g)
        how = QLabel("1. PLC writes <b>1</b> to the Trigger register.<br>"
                     "2. The app clears Done, captures/loads an image and inspects it.<br>"
                     "3. The app writes <b>Result</b> (OK/NOK value), <b>Failed-ROI bitmask</b> (bit n = ROI n failed), "
                     "sets <b>Done = 1</b> and clears Trigger.<br>"
                     "4. A <b>Heartbeat</b> counter increments every second so the PLC can detect a stopped app.<br>"
                     "Every result is also sent when you inspect from the Dashboard.")
        how.setWordWrap(True); how.setObjectName("muted"); gl.addWidget(how); right.addWidget(g)
        lb = QLabel("COMMUNICATION LOG"); lb.setObjectName("h2"); right.addWidget(lb)
        self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True); self.logbox.setMaximumBlockCount(500); right.addWidget(self.logbox, 1)
        root.addLayout(right, 2)

        ctx.plc.statusChanged.connect(self._status); ctx.plc.log.connect(self._log)
        self._status(ctx.plc._status or "Disabled")

    def _spin(self, v, lo=0, hi=65535):
        s = QSpinBox(); s.setRange(lo, hi); s.setValue(v); return s

    def _status(self, s):
        self.state.setText(s); self.led.setStyleSheet(f"font-size:22px;color:{STATUS_COL.get(s, theme.MUTED)};")

    def _log(self, m):
        self.logbox.appendPlainText(f"{datetime.datetime.now():%H:%M:%S}  {m}")

    def _apply(self):
        cfg = replace(self.ctx.settings.modbus, enabled=self.enabled.isChecked(), simulate=self.sim.isChecked(),
                      host=self.host.text().strip(), port=self.port.value(), unit=self.unit.value(), poll_ms=self.poll.value(),
                      reg_trigger=self.r_trig.value(), reg_result=self.r_res.value(), reg_mask=self.r_mask.value(),
                      reg_done=self.r_done.value(), reg_heartbeat=self.r_hb.value(), val_ok=self.v_ok.value(), val_nok=self.v_nok.value())
        regs = [cfg.reg_trigger, cfg.reg_result, cfg.reg_mask, cfg.reg_done, cfg.reg_heartbeat]
        if len(set(regs)) != len(regs):
            QMessageBox.warning(self, "Register map", "Each function needs its own register address."); return
        self.ctx.settings.modbus = cfg; self.ctx.save_settings(); self.ctx.plc.apply(cfg)
        self._log("Settings applied")
