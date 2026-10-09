"""Core inspection engine (no UI): ORB alignment to the master + per-ROI template matching."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
import cv2
import numpy as np
from core.imageio import limit_size


def prep(gray):
    """Lighting normalisation so brightness/contrast changes don't matter."""
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)


@dataclass
class RoiResult:
    name: str
    expected: str
    score: float
    threshold: float
    rect: tuple

    @property
    def ok(self):
        return self.score >= self.threshold


@dataclass
class InspectionResult:
    rois: list = field(default_factory=list)
    aligned: object = None
    matches: int = 0
    reason: str = ""
    ms: float = 0.0
    aligned_ok: bool = False

    @property
    def status(self):
        return "PASS" if (self.aligned_ok and self.rois and all(r.ok for r in self.rois)) else "NOK"

    @property
    def fail_mask(self):
        if not self.aligned_ok:
            return 0xFFFF
        m = 0
        for i, r in enumerate(self.rois[:16]):
            if not r.ok:
                m |= 1 << i
        return m

    @property
    def worst(self):
        return min((r.score for r in self.rois), default=0.0)


class Inspector:
    def __init__(self, recipe, master):
        self.recipe, self.master = recipe, master
        self.max_side = 0
        mg = cv2.cvtColor(master, cv2.COLOR_BGR2GRAY)
        self.mprep = prep(mg)
        self.orb = cv2.ORB_create(4000)
        self.kp, self.des = self.orb.detectAndCompute(mg, None)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)

    def align(self, live):
        g = cv2.cvtColor(live, cv2.COLOR_BGR2GRAY)
        k2, d2 = self.orb.detectAndCompute(g, None)
        if d2 is None or self.des is None:
            return None, 0
        pairs = self.bf.knnMatch(d2, self.des, k=2)
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
        if len(good) < self.recipe.min_matches:
            return None, len(good)
        src = np.float32([k2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([self.kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
        if H is None:
            return None, len(good)
        h, w = self.master.shape[:2]
        return cv2.warpPerspective(live, H, (w, h)), int(mask.sum())

    def inspect(self, live) -> InspectionResult:
        t0 = time.perf_counter()
        live = limit_size(live, self.max_side)
        res = InspectionResult()
        aligned, n = self.align(live)
        res.matches = n
        if aligned is None:
            res.reason = f"Alignment failed ({n} feature matches)"
            res.aligned = live
            res.rois = [RoiResult(r.name, r.expected, 0.0, r.threshold, r.rect) for r in self.recipe.rois]
            res.ms = (time.perf_counter() - t0) * 1000
            return res
        res.aligned, res.aligned_ok = aligned, True
        lg = prep(cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY))
        pad = self.recipe.search_pad
        H, W = lg.shape
        for r in self.recipe.rois:
            x1, y1, x2, y2 = r.rect
            tpl = self.mprep[y1:y2, x1:x2]
            area = lg[max(0, y1 - pad):min(H, y2 + pad), max(0, x1 - pad):min(W, x2 + pad)]
            if tpl.size == 0 or area.shape[0] < tpl.shape[0] or area.shape[1] < tpl.shape[1]:
                score = 0.0
            else:
                score = float(cv2.matchTemplate(area, tpl, cv2.TM_CCOEFF_NORMED).max())
            res.rois.append(RoiResult(r.name, r.expected, score, r.threshold, r.rect))
        if not res.rois:
            res.reason = "Recipe has no ROIs"
        elif res.status == "NOK":
            res.reason = "Mismatch: " + ", ".join(r.name for r in res.rois if not r.ok)
        res.ms = (time.perf_counter() - t0) * 1000
        return res

    @staticmethod
    def annotate(res: InspectionResult):
        img = res.aligned.copy()
        t = max(2, img.shape[1] // 250)
        fs = max(0.6, img.shape[1] / 900)
        for r in res.rois:
            x1, y1, x2, y2 = r.rect
            col = (0, 190, 0) if (r.ok and res.aligned_ok) else (0, 0, 230)
            cv2.rectangle(img, (x1 - 6, y1 - 6), (x2 + 6, y2 + 6), col, t)
            cv2.putText(img, f"{r.name} {r.score:.2f}", (x1 - 6, max(20, y1 - 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, fs * 0.6, col, max(1, t - 1), cv2.LINE_AA)
        return img
