#!/usr/bin/env python3
"""Import phone photos as evidence without their metadata.

For each photo: record the original's SHA-256 and capture time, then write a re-encoded copy
(long side 1600 px) that carries no EXIF/GPS/camera fields. macOS only (Quick Look + sips + mdls);
the originals stay where they are and are never modified.

    python3 tools/import_photos.py <out-dir> <photo>...
"""
import hashlib
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEP = {0xE0, 0xE2}  # APP0 (JFIF header) and APP2 (ICC colour profile); everything else before the scan goes


def strip_jpeg(b):
    """Drop every APPn/COM segment except JFIF and ICC: removes EXIF, XMP, IPTC and comments."""
    assert b[:2] == b"\xff\xd8"
    out, i = [b[:2]], 2
    while True:
        marker = b[i + 1]
        if marker == 0xDA:                       # start of scan: image data follows unchanged
            out.append(b[i:])
            return b"".join(out)
        length = int.from_bytes(b[i + 2:i + 4], "big")
        seg = b[i:i + 2 + length]
        if not ((0xE0 <= marker <= 0xEF or marker == 0xFE) and marker not in KEEP):
            out.append(seg)
        i += 2 + length


def metadata_segments(b):
    found, i = [], 2
    while b[i + 1] != 0xDA:
        if 0xE0 <= b[i + 1] <= 0xEF or b[i + 1] == 0xFE:
            found.append(hex(b[i + 1]))
        i += 2 + int.from_bytes(b[i + 2:i + 4], "big")
    return found


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
LOCAL = timezone(timedelta(hours=3))  # Turkey, where the photos were taken
rows = []
for src in map(Path, sys.argv[2:]):
    raw = src.read_bytes()
    created = subprocess.run(["mdls", "-raw", "-name", "kMDItemContentCreationDate", str(src)],
                             capture_output=True, text=True, check=True).stdout.strip()
    when = datetime.strptime(created, "%Y-%m-%d %H:%M:%S %z").astimezone(LOCAL)
    dst = out / f"{when:%Y%m%d-%H%M%S}-{src.stem}.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        # Quick Look renders a fresh bitmap (no metadata), sips encodes it as JPEG
        subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", tmp, str(src)], check=True, capture_output=True)
        png = next(Path(tmp).glob("*.png"))
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", str(png), "--out", str(dst)],
                       check=True, capture_output=True)
    dst.write_bytes(strip_jpeg(dst.read_bytes()))
    left = metadata_segments(dst.read_bytes())
    assert set(left) <= {"0xe0", "0xe2"}, f"metadata survived in {dst}: {left}"
    rows.append((dst.name, src.name, hashlib.sha256(raw).hexdigest(), f"{when:%Y-%m-%d %H:%M:%S %z}"))

with (out / "SOURCES.tsv").open("a") as f:
    for r in rows:
        f.write("\t".join(r) + "\n")
for r in rows:
    print(*r, sep="  ")
