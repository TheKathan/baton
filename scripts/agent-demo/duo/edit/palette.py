#!/usr/bin/env python3
"""Build a fixed 256-entry palette: every colour already in source.gif (127) kept exactly,
plus the caption bars' colours quantised into what is left.
This stops median-cut palettegen from merging the source's few chromatic colours
(the red refusal text, the desaturated green bullets) into greys."""
import os
from PIL import Image, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
src = set()
with Image.open(os.path.join(HERE, "source.gif")) as g:
    for fr in ImageSequence.Iterator(g):
        src |= {c for _, c in fr.convert("RGB").getcolors(1 << 16)}
cols = list(src)
N = 256
room = N - len(cols)
caps = [Image.open(os.path.join(HERE, "caps", f)).convert("RGB") for f in sorted(os.listdir(os.path.join(HERE, "caps"))) if f.startswith("c")]
sheet = Image.new("RGB", (caps[0].width, 40 * len(caps)))
for i, c in enumerate(caps):
    sheet.paste(c, (0, 40 * i))
q = sheet.quantize(colors=room, method=Image.Quantize.MEDIANCUT).convert("RGB")
for _, c in q.getcolors(1 << 16):
    if c not in cols:
        cols.append(c)
assert len(src) <= N, "source has more colours than the palette"
cols = cols[:N]
cols += [cols[0]] * (N - len(cols))
pal = Image.new("RGB", (16, 16))
pal.putdata(cols)
pal.save(os.path.join(HERE, "caps", "palette.png"))
print(f"palette: {len(src)} source colours kept + {N - len(src)} for captions")
