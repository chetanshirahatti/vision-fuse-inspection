"""Modbus TCP communication with the PLC (background thread, handshake based).

Handshake (holding registers, addresses editable in the PLC page):
  PLC  : writes 1 to reg_trigger                -> app starts an inspection
  App  : clears reg_done, runs inspection
  App  : writes reg_result (OK/NOK value), reg_mask (failed ROI bits), reg_done = 1, reg_trigger = 0
  App  : increments reg_heartbeat every second (PLC can use it as a watchdog)
"""
from __future__ import annotations
import inspect, queue, time
from PySide6.QtCore import QThread, Signal

try:
    from pymodbus.client import ModbusTcpClient
except Exception:                      # pymodbus not installed -> simulation only
    ModbusTcpClient = None


def _unit_kw(fn, unit):
    params = inspect.signature(fn).parameters
    for k in ("device_id", "slave", "unit"):
        if k in params:
            return {k: unit}
    return {}


class PlcWorker(QThread):
    statusChanged = Signal(str)       # Disabled | Simulation | Connecting | Connected | Error
    log = Signal(str)
    triggered = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._stop = False
        self._q = queue.Queue()
        self._client = None
        self._status = ""
        self._last_try = 0.0
        self._hb = 0
        self._hb_t = 0.0
        self._trig_prev = 0

    # ---- public API (called from the UI thread) ----
    def apply(self, cfg):
        self.cfg = cfg
        self._close()
        self._last_try = 0.0

    def publish(self, status, mask):
        self._q.put(("result", status, mask))

    def manual_trigger(self):
        self.log.emit("Manual trigger")
        self.triggered.emit()

    def stop(self):
        self._stop = True
        self.wait(2000)
        self._close()

    # ---- internals ----
    def _set(self, s):
        if s != self._status:
            self._status = s
            self.statusChanged.emit(s)

    def _close(self):
        c, self._client = self._client, None
        if c is not None:
            try:
                c.close()
            except Exception:
                pass

    def _write(self, addr, value):
        c, cfg = self._client, self.cfg
        rr = c.write_register(addr, int(value) & 0xFFFF, **_unit_kw(c.write_register, cfg.unit))
        if rr.isError():
            raise IOError(f"write @{addr} failed: {rr}")

    def _read(self, addr):
        c, cfg = self._client, self.cfg
        rr = c.read_holding_registers(addr, count=1, **_unit_kw(c.read_holding_registers, cfg.unit))
        if rr.isError():
            raise IOError(f"read @{addr} failed: {rr}")
        return rr.registers[0]

    def _do_result(self, status, mask):
        cfg = self.cfg
        val = cfg.val_ok if status == "PASS" else cfg.val_nok
        if cfg.simulate or self._client is None:
            self.log.emit(f"[SIM] result={val} ({status}) mask=0x{mask:04X} done=1 trigger=0")
            return
        self._write(cfg.reg_result, val)
        self._write(cfg.reg_mask, mask)
        self._write(cfg.reg_done, 1)
        self._write(cfg.reg_trigger, 0)
        self.log.emit(f"-> PLC: result={val} ({status}) mask=0x{mask:04X} done=1, trigger cleared")

    def run(self):
        while not self._stop:
            cfg = self.cfg
            try:
                if not cfg.enabled:
                    self._close()
                    self._set("Disabled")
                    while not self._q.empty():
                        self._q.get_nowait()
                    self.msleep(200)
                    continue
                if cfg.simulate:
                    self._close()
                    self._set("Simulation")
                    while not self._q.empty():
                        _, st, mk = self._q.get_nowait()
                        self._do_result(st, mk)
                    self.msleep(cfg.poll_ms)
                    continue
                if ModbusTcpClient is None:
                    self._set("Error")
                    self.log.emit("pymodbus is not installed (pip install pymodbus)")
                    self.msleep(2000)
                    continue
                if self._client is None:
                    if time.time() - self._last_try < 2.0:
                        self.msleep(100)
                        continue
                    self._last_try = time.time()
                    self._set("Connecting")
                    c = ModbusTcpClient(cfg.host, port=cfg.port, timeout=1)
                    if c.connect():
                        self._client = c
                        self._set("Connected")
                        self.log.emit(f"Connected to {cfg.host}:{cfg.port} (unit {cfg.unit})")
                    else:
                        self._set("Error")
                        self.log.emit(f"Cannot connect to {cfg.host}:{cfg.port}")
                        continue
                # connected: send pending results, heartbeat, poll trigger
                while not self._q.empty():
                    _, st, mk = self._q.get_nowait()
                    self._do_result(st, mk)
                now = time.time()
                if now - self._hb_t >= 1.0:
                    self._hb_t = now
                    self._hb = (self._hb + 1) & 0xFFFF
                    self._write(cfg.reg_heartbeat, self._hb)
                trig = self._read(cfg.reg_trigger)
                if trig == 1 and self._trig_prev == 0:
                    self.log.emit("<- PLC trigger received")
                    self._write(cfg.reg_done, 0)
                    self.triggered.emit()
                self._trig_prev = 1 if trig == 1 else 0
                self.msleep(cfg.poll_ms)
            except Exception as e:                     # communication problem -> reconnect
                self.log.emit(f"Communication error: {e}")
                self._close()
                self._set("Error")
                self.msleep(500)
