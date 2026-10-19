"""Usage: python3 -I mask.py <frames_in_dir> <frames_out_dir> <template_frame.png>"""
import glob
import os
import sys

import numpy as np
from PIL import Image

X0, X1, Y0, Y1 = 872, 1090, 63, 86
src, dst, tpl_path = sys.argv[1:4]
os.makedirs(dst, exist_ok=True)
tpl = np.asarray(Image.open(tpl_path).convert("RGB")).astype(np.int16)[Y0:Y1, X0:X1]
h = Y1 - Y0
masked = []
for f in sorted(glob.glob(os.path.join(src, "f*.png"))):
    im = Image.open(f).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    strip = a[:, X0:X1]
    hits = []
    for y in range(20, a.shape[0] - h):
        if np.abs(strip[y:y + h] - tpl).mean() < 12:
            hits.append(y)
    if hits:
        out = np.asarray(im).copy()
        bg = out[hits[0], X1 + 5]  # background just right of the text
        for y in hits:
            out[y:y + h, X0 - 2:X1 + 2] = bg
        im = Image.fromarray(out)
        masked.append(os.path.basename(f))
    im.save(os.path.join(dst, os.path.basename(f)))
print(f"masked {len(masked)} frames:", masked[0] if masked else "-", "...", masked[-1] if masked else "-")
