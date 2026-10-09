from __future__ import annotations
import json, os
from dataclasses import dataclass, field, asdict


@dataclass
class ModbusConfig:
    enabled: bool = False
    simulate: bool = True
    host: str = "192.168.0.10"
    port: int = 502
    unit: int = 1
    poll_ms: int = 200
    # Holding-register map (0-based addresses, as used by pymodbus)
    reg_trigger: int = 10      # PLC -> app : 1 = start inspection
    reg_result: int = 0        # app -> PLC : val_ok / val_nok
    reg_mask: int = 1          # app -> PLC : bit n = ROI n failed
    reg_done: int = 2          # app -> PLC : 1 = result valid
    reg_heartbeat: int = 3     # app -> PLC : counter, +1 every second
    val_ok: int = 1
    val_nok: int = 2


@dataclass
class Settings:
    camera_index: int = 0
    camera_source: str = "webcam"          # "webcam" or "mindvision"
    camera_trigger: str = "software"       # "software" (single picture on command), "hardware" (external pulse) or "continuous" (live)
    camera_hw_edge: str = "rising"         # hardware trigger: "rising" or "falling" edge
    camera_exposure_ms: float = 30.0
    camera_timeout_ms: int = 3000
    camera_max_side: int = 2000            # shrink frames so the longest side is at most this (0 = off)
    camera_resolution_index: int = -1      # -1 = keep camera default, else preset number
    mindvision_sdk_dir: str = r"C:\Program Files (x86)\MindVision\SDK\X64"
    max_side: int = 2000          # longest image side used for inspection/training (0 = full size)
    auto_interval_ms: int = 1500
    save_nok_images: bool = True
    last_recipe: str = ""
    modbus: ModbusConfig = field(default_factory=ModbusConfig)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load(path):
        s = Settings()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                mb = d.pop("modbus", {})
                for k, v in d.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
                for k, v in mb.items():
                    if hasattr(s.modbus, k):
                        setattr(s.modbus, k, v)
            except Exception:
                pass
        return s
