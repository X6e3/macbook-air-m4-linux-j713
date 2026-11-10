#!/usr/bin/env python3
"""O1: find the repeat period of a register window from its dump, without a list of candidates.

    python3 -I o1-period.py [--start 0x2000] <map dir>        chunk-XXXX-a/b.txt from o-mca.sh map
    python3 -I o1-period.py [--start 0x2000] --rw <map dir>   rw-XXXX.txt from o-mca.sh rwmap
    python3 -I o1-period.py --selftest                        synthetic windows with known periods

Map mode: a word's signature is its value, if both reads agree (words that changed between the reads are
volatile and left out). rw mode: the signature is (value read back after writing all ones, after writing
zeros), i.e. which bits are writable and which are fixed.

The window is analysed one 4 KiB page at a time, since different blocks of a device repeat at different
periods. In each page with at least 8 non-zero words, for every period p from 0x20 to 0x800 in steps of 0x20,
the score is the share of non-zero words whose signature appears again p bytes before or after them. The page's
period is the smallest p within 90 % of the best score; the best must stand at least four times above the median
score of the periods that are not multiples of it, or the page gets none. Blocks of that period are then compared one after the other to
show where the repetition starts and ends. "period" in o1-period.json is the period of the page that holds
--start (the driver's first register group); "others" are the other periods found. Writes o1-period.json next
to the dumps.
"""
import json
import random
import re
import sys
from pathlib import Path

STEP, PAGE, MIN_MATCHES, MIN_LIVE = 0x20, 0x1000, 8, 8
MAX_P = PAGE // 2


def load_map(d):
    a, b = {}, {}
    for f in sorted(d.glob('chunk-*-[ab].txt')):
        target = a if f.name.endswith('-a.txt') else b
        for line in f.read_text().splitlines():
            m = re.match(r'([0-9a-f]+): ((?:[0-9a-f]{8} ?){4})$', line.strip())
            if m:
                base = int(m.group(1), 16)
                for i, w in enumerate(m.group(2).split()):
                    target[base + 4 * i] = int(w, 16)
    sig = {off: v for off, v in a.items() if b.get(off) == v}
    volatile = sorted(off for off in a if off in b and b[off] != a[off])
    return sig, volatile


def load_rw(d):
    sig = {}
    for f in sorted(d.glob('rw-*.txt')):
        for line in f.read_text().splitlines():
            m = re.match(r'([0-9a-f]+): ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8})$', line.strip())
            if m:
                sig[int(m.group(1), 16)] = (int(m.group(3), 16), int(m.group(4), 16))
    return sig, []


def empty(s):
    return s == 0 or s == (0, 0)


def scores(sig):
    live = [(x, s) for x, s in sig.items() if not empty(s)]
    out = []
    for p in range(STEP, MAX_P + 1, STEP):
        m = sum(sig.get(x + p) == s or sig.get(x - p) == s for x, s in live)
        out.append((p, m / len(live) if live else 0.0, m))
    return out


def analyse(sig):
    sc = scores(sig)
    usable = [r for r in sc if r[2] >= MIN_MATCHES]
    if not usable:
        return None, sc
    best = max(s for _, s, _ in usable)
    period = min(p for p, s, _ in usable if s >= 0.9 * best)
    rest = sorted(s for p, s, _ in sc if p % period)          # periods that are not multiples of it
    baseline = rest[len(rest) // 2] if rest else 0.0
    if best < 0.1 or best < 4 * baseline:
        return None, sc
    return period, sc


def blocks(sig, p):
    """Similarity of each block of p bytes to the next one, over the populated span."""
    live = sorted(x for x, s in sig.items() if not empty(s))
    if not live:
        return []
    start, end = live[0] // p * p, live[-1] // p * p + p
    rows = []
    for b in range(start, end - p, p):
        n = same = 0
        for x in range(b, b + p, 4):
            s, t = sig.get(x), sig.get(x + p)
            if s is None or t is None or (empty(s) and empty(t)):
                continue
            n += 1
            same += s == t
        rows.append((b, b + p, same / n if n else None, n))
    return rows


def pages(sig):
    """(page, period or None, non-zero words, blocks) for each page with enough non-zero words."""
    out = []
    for page in range(0, max(sig) + 4, PAGE):
        sub = {x: s for x, s in sig.items() if page <= x < page + PAGE}
        live = sum(not empty(s) for s in sub.values())
        if live < MIN_LIVE:
            continue
        period, _ = analyse(sub)
        out.append((page, period, live, blocks(sub, period) if period else []))
    return out


def report(sig, volatile, start, out_dir=None):
    print(f'{len(sig)} words with a stable signature, {len(volatile)} volatile, '
          f'{sum(not empty(s) for s in sig.values())} non-zero')
    found = pages(sig)
    print('page     non-zero  period   repeating blocks (each against the next, share of equal words)')
    for page, period, live, rows in found:
        runs = ' '.join(f'{b:#06x}:{s:.2f}' for b, e, s, n in rows if n)
        print(f'{page:#06x}  {live:8d}  {f"{period:#x}" if period else "none":>6}   {runs}')
    mine = next((p for pg, p, _, _ in found if pg <= start < pg + PAGE), None)
    others = sorted({p for pg, p, _, _ in found if p and p != mine})
    print(f'period of the page holding {start:#x}: ' + (f'{mine:#x}' if mine else 'none'))
    print('other periods in the window: ' + (' '.join(f'{p:#x}' for p in others) or 'none'))
    result = {'start': start, 'period': mine, 'others': others,
              'pages': [[pg, p, live, [list(r) for r in rows]] for pg, p, live, rows in found],
              'volatile': volatile}
    if out_dir:
        (out_dir / 'o1-period.json').write_text(json.dumps(result, indent=1) + '\n')
    return mine


def selftest():
    ok = True
    for seed in range(20):
        rnd = random.Random(seed)
        period = rnd.choice([0x40, 0x80, 0x100, 0x200])
        units = rnd.randint(3, 0x1000 // period)
        base = rnd.choice([0x1000, 0x2000, 0x3000, 0x4000])
        pattern = [rnd.choice([0, 0, 0, rnd.getrandbits(32), rnd.getrandbits(8)]) for _ in range(period // 4)]
        if not any(pattern):
            pattern[0] = 1
        sig = {x: 0 for x in range(0, 0xc000, 4)}
        for u in range(units):
            for i, v in enumerate(pattern):
                sig[base + u * period + 4 * i] = v
        for i in rnd.sample(range(period // 4), max(1, period // 64)):   # unit 0 is running: some words differ
            sig[base + 4 * i] ^= rnd.getrandbits(32) | 1
        for x in rnd.sample(sorted(sig), 40):                             # unrelated non-zero words elsewhere
            if not base <= x < base + units * period:
                sig[x] = rnd.getrandbits(32)
        other = rnd.choice([0x80, 0x400])                             # another block, its own period
        for x in range(0x8000, 0x9000, other):
            sig[x + 4], sig[x + 8] = 0x1234, 0x80
        volatile = rnd.sample(sorted(sig), 30)
        for x in volatile:
            del sig[x]
        found = next((p for pg, p, _, _ in pages(sig) if pg <= base < pg + PAGE), None)
        got_other = next((p for pg, p, _, _ in pages(sig) if pg == 0x8000), None)
        good = found == period and got_other == other
        ok &= good
        print(f'seed {seed:2d}: period {period:#x}, {units} units at {base:#x}, '
              f'{sum(v != 0 for v in pattern)} non-zero words per unit -> '
              + (f'{found:#x}' if found else 'none'), 'ok' if good else 'WRONG')
    # No structure at all: only scattered words. Nothing may be reported.
    rnd = random.Random(99)
    sig = {x: 0 for x in range(0, 0xc000, 4)}
    for x in rnd.sample(sorted(sig), 200):
        sig[x] = rnd.getrandbits(32)
    found = [p for _, p, _, _ in pages(sig) if p]
    print('no structure ->', f'{found} WRONG' if found else 'none ok')
    ok &= not found
    print('selftest', 'passed' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--selftest']:
        sys.exit(0 if selftest() else 1)
    start = 0x2000
    if args[0] == '--start':
        start, args = int(args[1], 0), args[2:]
    rw = args[0] == '--rw'
    d = Path(args[-1])
    sig, volatile = (load_rw if rw else load_map)(d)
    if not sig:
        sys.exit(f'no dump lines found in {d}')
    report(sig, volatile, start, d)
