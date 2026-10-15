#!/usr/bin/env python3
"""Rasterize an SVG figure to PNG at a given pixel width.

Uses rsvg-convert when it is installed (Linux: librsvg2-tools). On macOS without it, falls back to
Quick Look (qlmanage), which only renders square thumbnails: the figure is centred on a square
canvas of its own background colour and the middle strip is cropped back out with sips.

    python3 tools/rasterize.py <in.svg> <out.png> <width-px>
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

src, dst, width = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
svg = src.read_text()
w, h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
height = round(width * h / w)

if shutil.which("rsvg-convert"):
    subprocess.run(["rsvg-convert", "-w", str(width), "-o", str(dst), str(src)], check=True)
elif shutil.which("qlmanage") and shutil.which("sips"):
    bg = re.search(r'<rect width="[\d.]+" height="[\d.]+" fill="(#[0-9a-fA-F]+)"', svg).group(1)
    pad = (w - h) / 2
    body = svg.split(">", 1)[1].rsplit("</svg>", 1)[0]            # drop the outer <svg ...> tag
    square = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {w}" width="{w}" height="{w}">'
              f'<rect width="{w}" height="{w}" fill="{bg}"/><g transform="translate(0,{pad})">{body}</g></svg>')
    with tempfile.TemporaryDirectory() as tmp:
        sq = Path(tmp) / "square.svg"
        sq.write_text(square)
        subprocess.run(["qlmanage", "-t", "-s", str(width), "-o", tmp, str(sq)], check=True, capture_output=True)
        subprocess.run(["sips", "-c", str(height), str(width), str(sq) + ".png", "--out", str(dst)], check=True,
                       capture_output=True)
else:
    sys.exit("need rsvg-convert, or qlmanage + sips on macOS")
print(f"{dst} {width}x{height}")
