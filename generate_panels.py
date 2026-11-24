#!/usr/bin/env python3
"""Generate per-segment subtitle frames at native recording resolution."""
from PIL import Image, ImageDraw, ImageFont
import os, sys

W, H = 2560, 1664

BOLD_FONT = "/System/Library/Fonts/Helvetica.ttc"
SFNS_FONT = "/System/Library/Fonts/SFNS.ttf"

WHITE  = (255, 255, 0,   255)   # yellow
BG     = (0,   0,   0,   210)   # subtitle background strip

FONT_SIZE = 46
LINE_H    = 60
MARGIN_X  = 140   # left/right margin for text
PAD_Y     = 20    # padding inside strip
STRIP_TOP = H - 180  # subtitle strip starts here

# Voiceover script -- one entry per video segment.
# Keep each line short enough to speak within the segment duration.
VOICEOVER = [
    # seg0  4s  -- terminal opens, dejavu header
    "DejaVu finds the mistakes your AI agent keeps repeating.",

    # seg1  4s  -- gen_samples runs, shows "Generated 47 synthetic sessions"
    "I feed it forty-seven synthetic Claude sessions to analyze.",

    # seg2  6s  -- analyze command runs, output scrolls by
    "The analyze command scans all sessions "
    "and ranks every mistake by frequency.",

    # seg3  5s  -- analysis results on screen: r001, 11 sessions
    "Top rule: Edit without Read -- "
    "found in eleven out of forty-seven sessions.",

    # seg4  5s  -- "open /tmp/report.html" typed, Safari opens full screen
    "One command opens the full HTML report in the browser.",

    # seg5  5s  -- top of report visible full screen: header, rule list
    "The report shows every pattern DejaVu found, "
    "ranked by how often it occurred.",

    # seg6  12s  -- scrolling through full report (4 scroll steps x 3s)
    "Scrolling down shows the detail for each rule -- "
    "trigger, description, and session count.",

    # seg7  5s  -- exit full screen, terminal back, preview r001
    "Back in the terminal: preview shows "
    "exactly what rule r001 checks for.",

    # seg8  5s  -- emit creates hook, output confirms path
    "Emit writes a hook file that fires "
    "before every Edit call Claude makes.",

    # seg9  4s  -- cat shows first 20 lines of hook code
    "The hook reads the target file first -- "
    "injecting the fix before the mistake can happen.",

    # seg10 4s  -- final success message: "Rule active. Run measure..."
    "Run measure after your next sessions "
    "to see if the error rate dropped.",

    # seg11 3s  -- countdown / done
    "Find it. Fix it. Measure it.",
]

def load_font():
    # index 2 = Helvetica Oblique (italic), index 3 = Bold Oblique
    for path, idx in [(BOLD_FONT, 3), (BOLD_FONT, 2), (SFNS_FONT, 0)]:
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
