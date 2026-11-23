#!/usr/bin/env python3
"""Generate per-segment subtitle frames at native recording resolution."""
from PIL import Image, ImageDraw, ImageFont
import os, sys

W, H = 2560, 1664

BOLD_FONT = "/System/Library/Fonts/Helvetica.ttc"
SFNS_FONT = "/System/Library/Fonts/SFNS.ttf"

WHITE  = (255, 255, 255, 255)
BG     = (0,   0,   0,   170)   # subtitle background strip

FONT_SIZE = 46
LINE_H    = 60
MARGIN_X  = 140   # left/right margin for text
PAD_Y     = 20    # padding inside strip
STRIP_TOP = H - 180  # subtitle strip starts here

# Voiceover script -- one entry per video segment.
# Keep each line short enough to speak within the segment duration.
VOICEOVER = [
    "I run DejaVu on forty-seven of my Claude sessions.",                           # seg0  3s
    "It ranks my mistakes by frequency. "                                           # seg1  5s
    "Top one: Edit without Read -- eleven sessions.",
    "I preview rule zero-zero-one and emit it. "                                    # seg2  7s
    "One command -- a hook that fires before every Edit.",
    "The hook injects the correction into Claude's context "                        # seg3  5s
    "before the mistake happens.",
    "After my next sessions, I run measure to see if errors dropped.",              # seg4  5s
    "That's the full loop: find the pattern, emit the correction, "                 # seg5  6s
    "measure whether it worked.",
    "Find it. Fix it. Measure it.",                                                 # seg6  2s
]

def load_font():
    for path, idx in [(BOLD_FONT, 1), (SFNS_FONT, 0)]:
        try:
            return ImageFont.truetype(path, FONT_SIZE, index=idx)
        except Exception:
            pass
    return ImageFont.load_default()

def wrap_lines(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) > max_w and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines

def make_frame(text):
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    font = load_font()

    max_w = W - 2 * MARGIN_X
    lines = wrap_lines(text, font, max_w, d)

    block_h   = len(lines) * LINE_H
    strip_top = H - block_h - 2 * PAD_Y - 24
    strip_bot = H - 16

    # Semi-transparent background strip
    d.rectangle([(0, strip_top), (W, strip_bot)], fill=BG)

    y = strip_top + PAD_Y
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        x    = (W - (bbox[2] - bbox[0])) // 2
        # Outline pass
        for dx, dy in [(-2,-2),(-2,0),(-2,2),(0,-2),(0,2),(2,-2),(2,0),(2,2)]:
            d.text((x+dx, y+dy), line, fill=(0,0,0,230), font=font)
        # Text
        d.text((x, y), line, fill=WHITE, font=font)
        y += LINE_H

    return img

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp"

for i, text in enumerate(VOICEOVER):
    path = os.path.join(OUT_DIR, f"dv_panel_{i}.png")
    make_frame(text).save(path)
    print(f"Saved {path}")

print("done")
