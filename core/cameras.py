"""Camera sources for the app: normal USB webcam, or MindVision GigE camera through MindVision's SDK (mvsdk.py).

Every source offers the same small interface:
    .mode       "continuous" (camera streams) or "software" (app asks for each picture)
    .preview()  next live frame for the screen, or None (software mode has no live preview)
    .capture()  a FRESH frame for inspection (in software mode this fires the camera trigger)
    .release()  close the camera
"""
from __future__ import annotations
import importlib, os, platform, threading
import cv2
import numpy as np

DEFAULT_SDK_DIRS = [r"C:\Program Files (x86)\MindVision\SDK\X64", r"C:\Program Files\MindVision\SDK\X64"]


def _fit(img, max_side):
    """Shrink very large pictures (a 20 MP frame is too slow to inspect) - keeps aspect ratio."""
    if max_side and max(img.shape[:2]) > max_side:
        s = max_side / max(img.shape[:2])
        return cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    return img


def load_mvsdk(sdk_dir=""):
    """Import MindVision's mvsdk. Python 3.8+ ignores PATH for DLLs, so the SDK folder is registered explicitly."""
    if platform.system() == "Windows":
        for d in [sdk_dir, os.environ.get("MV_SDK_DIR", ""), *DEFAULT_SDK_DIRS]:
            if d and os.path.isdir(d):
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(d)
                    except OSError:
                        pass
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    try:
        return importlib.import_module("core.mvsdk")
    except Exception as e:
        raise RuntimeError(
            "MindVision SDK could not be loaded: %s\n\n"
            "Check: 1) the MindVision SDK is installed, 2) Python is 64-bit, "
            "3) the SDK folder (…\\MindVision\\SDK\\X64) is correct in Settings." % e)


class WebcamSource:
    mode = "continuous"

    def __init__(self, s):
        api = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(s.camera_index, api)
        if not self.cap.isOpened():
            self.cap = None
            raise RuntimeError(f"Cannot open camera {s.camera_index}. Check the camera index in Settings.")
        self.max_side, self.name = s.camera_max_side, f"Webcam {s.camera_index}"

    def preview(self):
        ok, f = self.cap.read()
        return _fit(f, self.max_side) if ok else None

    def capture(self):
        f = None
        for _ in range(4):                      # skip stale frames / let exposure settle
            ok, g = self.cap.read()
            if ok:
                f = g
        return _fit(f, self.max_side) if f is not None else None

    def describe(self):
        return self.name

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class MindVisionSource:
    def __init__(self, s):
        mv = self.mv = load_mvsdk(getattr(s, "mindvision_sdk_dir", ""))
        self.mode = s.camera_trigger if s.camera_trigger in ("software", "hardware") else "continuous"
        self.max_side, self.timeout = s.camera_max_side, int(s.camera_timeout_ms)
        self.lock = threading.Lock()
        self.h, self.buf, self.presets = 0, None, []
        devs = mv.CameraEnumerateDevice()
        if not devs:
            raise RuntimeError("No MindVision camera found.\nCheck power, cable and that the PC network port "
                               "is on the camera's IP range (e.g. 192.168.1.x). Close the MindVision viewer "
                               "- only one program can use the camera at a time.")
        idx = s.camera_index if 0 <= s.camera_index < len(devs) else 0
        info = devs[idx]
        self.name = info.GetFriendlyName()
        try:
            self.h = mv.CameraInit(info, -1, -1)
        except mv.CameraException as e:
            raise RuntimeError(f"CameraInit failed ({e.error_code}): {e.message}\n"
                               "If the MindVision viewer is open, close it first.")
        try:
            cap = mv.CameraGetCapability(self.h)
            self.mono = cap.sIspCapacity.bMonoSensor != 0
            self.presets = [f"{i}: {cap.pImageSizeDesc[i].GetDescription()} "
                            f"({cap.pImageSizeDesc[i].iWidth}x{cap.pImageSizeDesc[i].iHeight})"
                            for i in range(cap.iImageSizeDesc)]
            ri = s.camera_resolution_index
            if 0 <= ri < cap.iImageSizeDesc:
                mv.CameraSetImageResolution(self.h, cap.pImageSizeDesc[ri])
            mv.CameraSetIspOutFormat(self.h, mv.CAMERA_MEDIA_TYPE_MONO8 if self.mono else mv.CAMERA_MEDIA_TYPE_BGR8)
            mv.CameraSetTriggerMode(self.h, {"continuous": 0, "software": 1, "hardware": 2}[self.mode])
            if self.mode == "hardware":                                               # which edge of the external pulse fires the camera
                mv.CameraSetExtTrigSignalType(self.h, mv.EXT_TRIG_TRAILING_EDGE if s.camera_hw_edge == "falling" else mv.EXT_TRIG_LEADING_EDGE)
            mv.CameraSetAeState(self.h, 0)                                            # manual exposure
            mv.CameraSetExposureTime(self.h, float(s.camera_exposure_ms) * 1000.0)
            size = cap.sResolutionRange.iWidthMax * cap.sResolutionRange.iHeightMax * (1 if self.mono else 3)
            self.buf = mv.CameraAlignMalloc(size, 16)
            mv.CameraPlay(self.h)
        except Exception:
            self.release()
            raise

    def _grab(self, timeout):
        mv = self.mv
        try:
            raw, head = mv.CameraGetImageBuffer(self.h, timeout)
        except mv.CameraException as e:
            if e.error_code == mv.CAMERA_STATUS_TIME_OUT:
                return None
            raise RuntimeError(f"Camera grab failed ({e.error_code}): {e.message}")
        try:
            mv.CameraImageProcess(self.h, raw, self.buf, head)
        finally:
            mv.CameraReleaseImageBuffer(self.h, raw)
        if platform.system() == "Windows":          # SDK delivers bottom-up frames on Windows
            mv.CameraFlipFrameBuffer(self.buf, head, 1)
        data = (mv.c_ubyte * head.uBytes).from_address(self.buf)
        ch = 1 if head.uiMediaType == mv.CAMERA_MEDIA_TYPE_MONO8 else 3
        img = np.frombuffer(data, np.uint8).reshape(head.iHeight, head.iWidth, ch).copy()
        if ch == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return _fit(img, self.max_side)

    def preview(self):
        """continuous: next live frame | hardware: a frame if a pulse just fired the camera | software: never (no stream)."""
        if self.mode == "software":
            return None
        with self.lock:
            return self._grab(60 if self.mode == "continuous" else 30)

    def capture(self):
        with self.lock:
            self.mv.CameraClearBuffer(self.h)          # drop old frames so the picture is taken NOW
            if self.mode == "software":
                self.mv.CameraSoftTrigger(self.h)                # one pulse -> exactly one picture
            return self._grab(self.timeout)                      # hardware mode: waits for the external pulse

    def describe(self):
        return f"{self.name} · {'mono' if getattr(self, 'mono', False) else 'colour'} · {self.mode} mode"

    def release(self):
        with self.lock:
            if self.h:
                try:
                    self.mv.CameraUnInit(self.h)
                except Exception:
                    pass
                self.h = 0
            if self.buf:
                try:
                    self.mv.CameraAlignFree(self.buf)
                except Exception:
                    pass
                self.buf = None


def open_source(settings):
    return MindVisionSource(settings) if settings.camera_source == "mindvision" else WebcamSource(settings)
