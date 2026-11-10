#!/usr/bin/env python3
"""Summary of one o-gpu.sh run: per phase medians, each B against the A phases on both sides, response time, and
for +0x8c the plateaus of the dose-response curve, found from the data.

    python3 -I o-gpu-summary.py <result dir>
    python3 -I o-gpu-summary.py --selftest

Samples taken while the load was paused (pauses.txt) are left out, and so are draw-rate lines whose 10 s window
overlaps a pause. A phase runs until the next phase starts; its median covers its last 25 s of load.
"""
import random
import re
import statistics as st
import sys
from pathlib import Path

TAIL = 25


def plateaus(points, rel=0.06, floor=0.25):
    """points: (value, watts), any order. Walk from the highest value down; a new plateau starts when the power
    differs from the current plateau's median by more than max(floor W, rel * median)."""
    out = []
    for v, w in sorted(points, reverse=True):
        if out:
            m = st.median(x for _, x in out[-1])
            if abs(w - m) <= max(floor, rel * m):
                out[-1].append((v, w))
                continue
        out.append([(v, w)])
    return out


def edges(groups):
    """The interval in which each step lies: (lowest value of the plateau above, highest value of the one below)."""
    return [(a[-1][0], b[0][0]) for a, b in zip(groups, groups[1:])]


def summarise(d):
    rows = [line.split() for line in (d / 'sensors.txt').read_text().splitlines() if line.strip()]
    names, data = rows[0][1:], [r for r in rows[1:] if len(r) == len(rows[0])]
    pauses = []
    if (d / 'pauses.txt').exists():
        pauses = [tuple(map(int, l.split())) for l in (d / 'pauses.txt').read_text().splitlines() if l.strip()]
    in_pause = lambda t0, t1: any(a < t1 and t0 < b for a, b in pauses)

    def col(r, n):
        v = r[1 + names.index(n)] if n in names else 'NA'
        return int(v) if v.lstrip('-').isdigit() else None

    start = int((d / 'load-start.txt').read_text())
    draws = []
    for line in (d / 'load.txt').read_text().splitlines():
        if line.endswith('draws/s') and ' s: ' in line:
            t = start + float(line.split(' s:')[0])
            if not in_pause(t - 10, t):
                draws.append((t, float(line.split(': ')[1].split()[0])))

    print('region_c written by the firmware? region_c_changed over the run:',
          sorted({col(r, 'region_c_changed') for r in data if col(r, 'region_c_changed') is not None}),
          'first changed word:', sorted({col(r, 'region_c_first') for r in data if col(r, 'region_c_first') is not None}))
    for w in ('84', '88', '8c', '90', '94', '98'):
        vals = sorted({col(r, 'live_' + w) for r in data if col(r, 'live_' + w) is not None})
        print(f'  live_{w}: {vals[:12]}{" ..." if len(vals) > 12 else ""}')
    if pauses:
        print(f'load paused {len(pauses)} times, {sum(b - a for a, b in pauses)} s in all')

    pf = d / 'phases.txt'
    if not pf.exists():
        return
    phases = [(int(l.split()[0]), l.split()[1]) for l in pf.read_text().splitlines() if l.strip()]
    load_end = max(int(r[0]) for r in data)
    for line in (d / 'load.txt').read_text().splitlines():   # gl-burn's last line: "done: N draws in S s"
        m = re.match(r'done: \d+ draws in ([\d.]+) s', line)
        if m:
            load_end = start + int(float(m.group(1)))
    ends = [p[0] for p in phases[1:]] + [load_end]

    def summary(t1):
        sel = [r for r in data if int(r[0]) < t1 and not in_pause(int(r[0]), int(r[0]) + 1)][-TAIL:]
        p = [col(r, 'SMC_PP1b') / 1e6 for r in sel if col(r, 'SMC_PP1b') is not None]
        tv = [col(r, 'SMC_TVS1') / 1000 for r in sel if col(r, 'SMC_TVS1') is not None]
        cool = [col(r, 'cooling') for r in sel if col(r, 'cooling') is not None]
        t0 = int(sel[0][0]) if sel else t1
        dr = [x for t, x in draws if t0 <= t < t1]
        med = lambda v: st.median(v) if v else None
        return {'W': med(p), 'draws': med(dr), 'TVS1': med(tv), 'cool': max(cool) if cool else None}

    def response(t0, a_w, b_w):
        if a_w is None or b_w is None or abs(a_w - b_w) < 0.3:
            return None
        half = (a_w + b_w) / 2
        for r in data:
            t, v = int(r[0]), col(r, 'SMC_PP1b')
            if t >= t0 and v is not None and (v / 1e6 - half) * (a_w - b_w) < 0:
                return t - t0
        return None

    s = [summary(t1) for t1 in ends]
    f = lambda v, w=7: f'{v:{w}.2f}' if v is not None else ' ' * (w - 2) + 'NA'
    print(f'\nmedians over the last {TAIL} s of load in each phase; B against the mean of the A phases around it')
    print('  phase  setting        PP1b W  draws/s   TVS1 C  cooling   dW vs A  draws vs A  response s')
    results = []
    for i, ((t0, label), m) in enumerate(zip(phases, s)):
        extra = ''
        if label != 'A' and 0 < i < len(s) - 1:
            a = [s[j] for j in (i - 1, i + 1) if phases[j][1] == 'A']
            aw = st.mean([x['W'] for x in a if x['W'] is not None]) if a else None
            ad = st.mean([x['draws'] for x in a if x['draws'] is not None]) if a else None
            dw = m['W'] - aw if m['W'] is not None and aw is not None else None
            dd = 100 * (m['draws'] / ad - 1) if m['draws'] and ad else None
            rt = response(t0, aw, m['W'])
            extra = f'  {f(dw, 8)}  {f(dd, 9)}%  {rt if rt is not None else "NA":>9}'
            results.append((label, m['W'], dw, dd))
        print(f'  {i + 1:5d}  {label:12s} {f(m["W"])}  {f(m["draws"])}  {f(m["TVS1"])}  '
              f'{m["cool"] if m["cool"] is not None else "NA":>7}{extra}')

    print('\nper word: the largest change against A over its B phases (W, draws %)')
    for w in ('84', '88', '8c', '90', '94', '98'):
        r = [x for x in results if x[0].startswith(f'+0x{w}=') and x[2] is not None]
        if r:
            print(f'  +0x{w}: {max(abs(x[2]) for x in r):5.2f} W, '
                  f'{max(abs(x[3]) for x in r if x[3] is not None) if any(x[3] is not None for x in r) else float("nan"):5.1f} %'
                  f'  over {len(r)} phases')
    pts = [(int(x[0].split('=')[1]), x[1]) for x in results if x[0].startswith('+0x8c=') and x[1] is not None]
    if len(pts) >= 3:
        aw = [m['W'] for (_, l), m in zip(phases, s) if l == 'A' and m['W'] is not None]
        if aw:
            pts.append((1000, st.median(aw)))   # A: the start value
        groups = plateaus(pts)
        print('\n+0x8c plateaus (values that give the same power, from the data):')
        for g in groups:
            print(f'  {g[0][0]:4d} .. {g[-1][0]:4d}: {st.median(w for _, w in g):5.2f} W  ({len(g)} values)')
        print('steps lie between:', ', '.join(f'{lo} and {hi}' for lo, hi in edges(groups)) or 'none')
    dmesg = d / 'dmesg-o2.txt'
    if dmesg.exists():
        print('\ndmesg:')
        print(dmesg.read_text().strip() or '(no O2 lines)')


def selftest():
    """A synthetic curve with flat steps every `step`, plus noise: the plateaus must split exactly at the steps."""
    ok = True
    for seed in range(10):
        rnd = random.Random(seed)
        step = rnd.choice([100, 150, 200, 250])
        top = rnd.choice([700, 800, 900, 1000])
        power = lambda v: 1.0 + 8.0 * (min(v, top) // step * step) / top
        pts = [(v, power(v) + rnd.gauss(0, 0.05)) for v in range(950, 0, -50)] + [(1000, power(1000))]
        e = edges(plateaus(pts))
        good = all((hi // step) != (lo // step) or hi > top for lo, hi in e) and len(e) == len(
            {min(v, top) // step for v, _ in pts}) - 1
        ok &= good
        print(f'seed {seed}: step {step}, top {top}: steps between', e, 'ok' if good else 'WRONG')
    print('selftest', 'passed' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        sys.exit(0 if selftest() else 1)
    summarise(Path(sys.argv[1]))
