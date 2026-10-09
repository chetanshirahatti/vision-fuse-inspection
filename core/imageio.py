"""Unicode/OneDrive-safe image read/write (avoids cv2.imread/imwrite path problems on Windows)."""
import cv2
import numpy as np


def read_image(path):
    try:
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    except Exception:
        return None


def write_image(path, img):
    ext = "." + path.rsplit(".", 1)[-1].lower()
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise IOError(f"Could not encode image for {path}")
    buf.tofile(path)


def limit_size(img, max_side):
    """Downscale so the longest side is <= max_side (keeps 20 MP camera images fast). 0 = off."""
    if img is None or not max_side:
        return img
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return img
    s = max_side / m
    return cv2.resize(img, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
