from __future__ import annotations
import csv, os, datetime
import cv2

FIELDS = ["time", "recipe", "source", "status", "details", "image"]


class History:
    def __init__(self, root):
        self.root = root
        self.csv = os.path.join(root, "results.csv")
        self.img_dir = os.path.join(root, "images")
        os.makedirs(self.img_dir, exist_ok=True)

    def log(self, recipe, source, res, annotated=None, save_image=True):
        ts = datetime.datetime.now()
        path = ""
        if annotated is not None and save_image and res.status == "NOK":
            path = os.path.join(self.img_dir, ts.strftime("%Y%m%d_%H%M%S_%f") + "_NOK.jpg")
            cv2.imwrite(path, annotated)
        details = "; ".join(f"{r.name}={r.score:.2f}" for r in res.rois) or res.reason
        new = not os.path.isfile(self.csv)
        with open(self.csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, FIELDS)
            if new:
                w.writeheader()
            w.writerow(dict(time=ts.strftime("%Y-%m-%d %H:%M:%S"), recipe=recipe, source=source,
                            status=res.status, details=details, image=path))
        return path

    def read(self, limit=1000):
        if not os.path.isfile(self.csv):
            return []
        with open(self.csv, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return rows[-limit:][::-1]
