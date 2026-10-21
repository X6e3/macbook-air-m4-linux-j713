#!/usr/bin/env python3
"""Split m1n1 boot images into their parts and record a SHA-256 for each part.

An x6e3 boot image is: m1n1 stage 2 binary, zero padding, a text payload config
("chosen.bootargs=..."), the DTB, then Image.gz and the initramfs. The images themselves are not
published (later initramfs layers carry vendor firmware), so this script's output is committed instead.

    python3 analysis/split_boot_image.py <image.bin>... > evidence/01-first-boot/image-parts.csv
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fdt  # noqa: E402

sha = lambda b: hashlib.sha256(b).hexdigest()

w = csv.writer(sys.stdout, lineterminator="\n")
w.writerow(["image", "variant", "image_sha256", "m1n1_sha256", "dtb_sha256", "kernel_initramfs_sha256", "bootargs"])
for path in sys.argv[1:]:
    blob = Path(path).read_bytes()
    off, size = fdt.find_dtb(blob)
    head, dtb, tail = blob[:off], blob[off:off + size], blob[off + size:]
    pad = head.rfind(b"\0" * 64)                 # m1n1 ends with padding before the payload config
    m = re.search(rb"chosen\.bootargs=([^\n]*)", head)
    bootargs = m.group(1).decode() if m else ""
    variant = re.search(r"x6e3\.v=(\S+)", bootargs)
    w.writerow([Path(path).name, variant.group(1) if variant else "", sha(blob), sha(head[:pad]), sha(dtb), sha(tail),
                bootargs])
