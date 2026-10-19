#!/usr/bin/env python3
"""Render the slim (40 px) caption bars used by build.sh (this ffmpeg has no drawtext)."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caps")
os.makedirs(OUT, exist_ok=True)

W, H = 1240, 40
BG, FG, MUTED = "#161B22", "#E6EDF3", "#8B949E"
ORANGE, RED, LINE = "#FF922B", "#F85149", "#30363D"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def font(size, weight):
    f = ImageFont.truetype(MONO, size)
    f.set_variation_by_name(weight)
    return f


F_NUM = font(15, "Bold")
F_TAG = font(13, "Regular")
F_SPD = font(13, "Medium")
TAG = "real agents · Codex + Claude Code"

CAPS = [
    ("c1", "1", ORANGE, [("frontend (Codex) asks backend which route serves the health check", FG)], None),
    ("c2", "2", RED, [("backend (Claude Code) hands off → refused: ", FG), ("Q-001", RED), (" is unanswered", FG)], None),
    ("c3", "3", ORANGE, [("it answers ", FG), ("Q-001", ORANGE), (", and the hand-off goes through as ", FG), ("H-002", ORANGE)], None),
    ("c4", "check", ORANGE, [("two vendors, one board: no ", FG), ("--force", ORANGE), (" needed", FG)], None),
]


def fit_font(parts, room):
    for size in (19, 18):
        f = font(size, "Semibold")
        if sum(f.getlength(t) for t, _ in parts) <= room:
            return f
    return f


for name, badge, accent, parts, speed in CAPS:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, H - 2, W, H], fill=accent)
    cy, r, cx = (H - 2) // 2, 12, 26
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    if badge == "check":
        d.line([(cx - 6, cy), (cx - 2, cy + 5), (cx + 6, cy - 5)], fill="#0D1117", width=3, joint="curve")
    else:
        d.text((cx, cy + 1), badge, font=F_NUM, fill="#0D1117", anchor="mm")
    tag_w = d.textlength(TAG, font=F_TAG)
    x = cx + r + 12
    room = W - 16 - tag_w - 24 - x - (60 if speed else 0)
    f_cap = fit_font(parts, room)
    for text, color in parts:
        d.text((x, cy), text, font=f_cap, fill=color, anchor="lm")
        x += d.textlength(text, font=f_cap)
    if speed:
        x += 14
        tw = d.textlength(speed, font=F_SPD)
        d.rounded_rectangle([x, cy - 10, x + tw + 14, cy + 10], radius=5, outline=LINE, width=2)
        d.text((x + 7, cy + 1), speed, font=F_SPD, fill=MUTED, anchor="lm")
    d.text((W - 16, cy), TAG, font=F_TAG, fill=MUTED, anchor="rm")
    im.save(os.path.join(OUT, name + ".png"))
    print(name, "font", f_cap.size)
