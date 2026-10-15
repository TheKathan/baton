#!/usr/bin/env python3
"""Build a fixed 96-colour palette: every colour already in source.gif (63) kept exactly,
plus the outline colours and the caption bars' colours quantised into what is left.
This stops median-cut palettegen from merging the source's few chromatic colours
(the red refusal text, the desaturated green bullets) into greys."""
import os
from PIL import Image, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
src = set()
with Image.open(os.path.join(HERE, "source.gif")) as g:
    for fr in ImageSequence.Iterator(g):
        src |= {c for _, c in fr.convert("RGB").getcolors(1 << 16)}
cols = list(src) + [(0xF8, 0x51, 0x49), (0xFF, 0x92, 0x2B)]  # outline red / orange
room = 96 - len(cols)
caps = [Image.open(os.path.join(HERE, "caps", f)).convert("RGB") for f in sorted(os.listdir(os.path.join(HERE, "caps")))]
sheet = Image.new("RGB", (1200, 40 * len(caps)))
for i, c in enumerate(caps):
    sheet.paste(c, (0, 40 * i))
q = sheet.quantize(colors=room, method=Image.Quantize.MEDIANCUT).convert("RGB")
for _, c in q.getcolors(1 << 16):
    if c not in cols:
        cols.append(c)
cols = cols[:96]
cols += [cols[0]] * (96 - len(cols))
uniq = list(cols)
cols = uniq + [uniq[0]] * (256 - 96)  # paletteuse needs 256 entries; the extras repeat colour 0
pal = Image.new("RGB", (16, 16))
pal.putdata(cols)
pal.save(os.path.join(HERE, "caps", "palette.png"))
print(f"palette: {len(src)} source colours + {96 - len(src)} caption/outline")
