#!/usr/bin/env python3
"""First boot: what changed between the first-night DTBs.

Compares two DTBs property by property. Changes that only renumber phandles are separated from
changes in meaning: a phandle-valued property that points at the same node in both trees is not a
change. Output goes to data/01-first-boot/dtb_diff.txt.

    python3 analysis/dtb_diff.py
"""
import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
import fdt  # noqa: E402

DTB_DIR = ROOT / "evidence/01-first-boot/dtb"
PAIRS = [("c35fabb6", "7dab1c02", "v3c/v4ctl -> v4"), ("7dab1c02", "82886b6e", "v4 -> v5")]
# phandle-valued property -> the #...-cells property of the target node that gives each entry's argument count
PHANDLE_PROPS = {"power-domains": "#power-domain-cells", "pwms": "#pwm-cells", "gpio": "#gpio-cells",
                 "gpios": "#gpio-cells", "interrupt-parent": None, "iommus": "#iommu-cells", "phys": "#phy-cells",
                 "clocks": "#clock-cells"}


def cells(v):
    return struct.unpack(f">{len(v) // 4}I", v) if len(v) % 4 == 0 else None


def resolve(v, ph, nodes, prop):
    """Split a phandle list into entries and replace each phandle by the node it points to.

    Each entry is a phandle followed by as many argument cells as the target's #...-cells says
    (power-domains on Apple pmgr has 0, so every cell is its own phandle). Returns the raw bytes
    if any phandle is unknown or the cells do not divide into whole entries.
    """
    c, entries, i = cells(v), [], 0
    while c and i < len(c):
        if c[i] not in ph:
            return v
        path, label = ph[c[i]]
        n = cells(nodes[path].get(PHANDLE_PROPS[prop], b"\0\0\0\0"))[0] if PHANDLE_PROPS[prop] else 0
        if i + 1 + n > len(c):
            return v
        entries.append((path, label, c[i + 1:i + 1 + n]))
        i += 1 + n
    return tuple(entries) if entries else v


def show(v):
    if isinstance(v, tuple):
        return ", ".join(f"&{path}" + (f" (label {label})" if label else "") +
                         (f" + {list(map(hex, args))}" if args else "") for path, label, args in v)
    c = cells(v)
    if c and len(v) <= 32:
        return " ".join(hex(x) for x in c)
    return repr(v.rstrip(b"\0").decode(errors="replace"))


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
out = []
for a, b, title in PAIRS:
    A, B = fdt.parse((DTB_DIR / f"{a}.dtb").read_bytes()), fdt.parse((DTB_DIR / f"{b}.dtb").read_bytes())
    pa, pb = fdt.phandles(A), fdt.phandles(B)
    meaning, renumber = [], []
    for path in sorted(set(A) | set(B)):
        if path not in A or path not in B:
            meaning.append(f"  node {'added' if path in B else 'removed'}: {path}")
            continue
        for prop in sorted(set(A[path]) | set(B[path])):
            va, vb = A[path].get(prop), B[path].get(prop)
            if va == vb:
                continue
            if prop == "phandle":
                renumber.append(f"  {path}: phandle {show(va) if va else '-'} -> {show(vb) if vb else '-'}")
                continue
            if va is not None and vb is not None and prop in PHANDLE_PROPS:
                ra, rb = resolve(va, pa, A, prop), resolve(vb, pb, B, prop)
                if ra == rb:
                    targets = ", ".join(e[0] for e in ra)
                    renumber.append(f"  {path}:{prop} {show(va)} -> {show(vb)} (same target {targets})")
                    continue
                meaning.append(f"  {path}:{prop}\n      {show(ra)}\n   -> {show(rb)}")
                continue
            meaning.append(f"  {path}:{prop}  {show(va) if va is not None else '(absent)'} -> "
                           f"{show(vb) if vb is not None else '(absent)'}")
    out.append(f"== {title}: {a}.dtb -> {b}.dtb")
    out.append(f"changes in meaning: {len(meaning)}")
    out.extend(meaning)
    out.append(f"phandle renumbering only: {len(renumber)}")
    out.extend(renumber)
    out.append("")

target = ROOT / "data/01-first-boot/dtb_diff.txt"
if args.check:
    if target.read_text() != "\n".join(out):
        raise SystemExit("Stale DTB comparison: run analysis/dtb_diff.py")
else:
    target.write_text("\n".join(out))
print("\n".join(out))
