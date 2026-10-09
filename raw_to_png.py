"""Convert a MindVision .raw capture (headerless mono) to PNG.
Usage:  python raw_to_png.py IMG_xxx.raw WIDTH HEIGHT
WIDTH/HEIGHT = the 'Resolution' shown in the MindVision viewer status bar when the picture was streaming.
Supports 8-bit (file size = W*H) and 16-bit (file size = 2*W*H) mono."""
import sys, numpy as np, cv2

path, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
data = np.fromfile(path, dtype=np.uint8)
if data.size == w * h:
    img = data.reshape(h, w)
elif data.size == 2 * w * h:
    img = np.frombuffer(data.tobytes(), dtype="<u2").reshape(h, w)
    img = (img >> 4).astype(np.uint8) if img.max() < 4096 else (img >> 8).astype(np.uint8)
else:
    sys.exit(f"File has {data.size} bytes; expected {w*h} (8-bit) or {2*w*h} (16-bit) for {w}x{h}. Check the resolution.")
out = path.rsplit(".", 1)[0] + ".png"
cv2.imencode(".png", img)[1].tofile(out)
print("saved", out)
