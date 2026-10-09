"""Threshold calibration from folders of known-good (OK) and known-bad (NOK) images."""
import os, glob
from core.imageio import read_image

EXT = ("*.png", "*.jpg", "*.jpeg", "*.bmp")


def list_images(folder):
    files = []
    for e in EXT:
        files += glob.glob(os.path.join(folder, e))
    return sorted(files)


def evaluate(inspector, files, cls):
    rows = []
    for f in files:
        img = read_image(f)
        if img is None:
            continue
        r = inspector.inspect(img)
        rows.append(dict(file=os.path.basename(f), cls=cls, worst=r.worst,
                         scores=[x.score for x in r.rois]))
    return rows


def suggest(ok_rows, nok_rows):
    """Return (threshold, message). 'worst' = lowest ROI score of an image."""
    ok = [r["worst"] for r in ok_rows]
    nok = [r["worst"] for r in nok_rows]
    if not ok:
        return None, "No OK images evaluated."
    min_ok = min(ok)
    if nok:
        max_nok = max(nok)
        thr = round((min_ok + max_nok) / 2, 2)
        if min_ok <= max_nok:
            return thr, (f"Classes overlap (lowest OK {min_ok:.2f} <= highest NOK {max_nok:.2f}). "
                         "Improve lighting / ROI placement before trusting this threshold.")
        return thr, f"Lowest OK {min_ok:.2f}, highest NOK {max_nok:.2f} -> margin {min_ok - max_nok:.2f}."
    thr = round(max(0.5, min_ok - 0.15), 2)
    return thr, f"Lowest OK {min_ok:.2f}. No NOK images given, so threshold = lowest OK - 0.15."
