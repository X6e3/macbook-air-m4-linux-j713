#!/usr/bin/env python3
"""Recompute the section 10 Xonotic results from the REL2 evidence: the game logs of the night of 28 October, the
three logged reruns with Mesa's buffer dump, and the published excerpt of the boot journal saved after the crash."""
import argparse
import hashlib
import json
import re
from pathlib import Path

if not __debug__:
    raise SystemExit('Run evidence checks without -O')

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'evidence/10-xonotic'
ANSI = re.compile(r'\x1b\[[0-9;]*m|\^\d')
UNITS = {'B': 1, 'KiB': 1 << 10, 'MiB': 1 << 20, 'GiB': 1 << 30}
STAMP = re.compile(r'^Oct 28 (\d\d:\d\d:\d\d)\.\d+ \S+ (\S+?)(?:\[\d+\])?: (.*)')
GAME_LOGS = ['engine.log', 'zink-test.log', 'wayland-test.log', 'xonotic-agx-gameplay.log']
RUNS = ['lowres-050506', 'rt-owner-051419', 'rt-test-051702']


def text(path):
    return ANSI.sub('', (DIR / path).read_text(encoding='utf-8', errors='replace'))


def check_hashes():
    for line in (DIR / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((DIR / name).read_bytes()).hexdigest() == expected, name


def size(value, unit):
    return float(value) * UNITS[unit]


def game(name):
    lines = text(f'game/{name}').splitlines()
    players = []
    for line in lines:
        m = re.match(r'(\S+) connected$', line)
        if m and m.group(1) not in players:
            players.append(m.group(1))
    return {
        'renderer': sorted({l.split(': ', 1)[1] for l in lines if l.startswith('GL_RENDERER: ')}),
        'video_modes': sorted({l.split(': ', 1)[1] for l in lines if l.startswith('Video Mode: ')}),
        'maps': [l.split()[-1] for l in lines if l.startswith('Switching to map ')],
        'bots': [p for p in players if p != 'x6e3U'],
        'mine': sorted({l.strip() for l in lines if l.startswith('x6e3U ') and ('blood' in l or 'FRAG' in l)}),
    }


def run(name):
    lines = text(f'rel2-runs/{name}/game.log').splitlines()
    dumps, current = [], None   # one (render target, total) pair per buffer dump that lists render targets
    for line in lines:
        m = re.match(r'(Render target|Total): ([\d.]+) (B|KiB|MiB|GiB),(?: mapped [^,]+,)? (\d+) BOs', line)
        if m and m.group(1) == 'Render target':
            current = (size(m.group(2), m.group(3)), int(m.group(4)))
        elif m and current:
            dumps.append((current, (size(m.group(2), m.group(3)), int(m.group(4)))))
            current = None
    available = []
    for line in text(f'rel2-runs/{name}/memory.log').splitlines():
        m = re.search(r'MemAvailable: ([\d.]+)GiB', line) or re.search(r'Available=(\d+)', line)
        if m:
            available.append(float(m.group(1)) if 'GiB' in m.group(0) else int(m.group(1)) / (1 << 20))
        elif re.match(r'\d\d:\d\d:\d\d (\d+) \d+$', line):
            available.append(int(line.split()[1]) / (1 << 20))
    out = {
        'maps': [l.split()[-1] for l in lines if l.startswith('Switching to map ')],
        'video_modes': sorted({l.split(': ', 1)[1] for l in lines if l.startswith('Video Mode: ')}),
        'dumps': len(dumps),
        'available_GiB_first_min': [round(available[0], 2), round(min(available), 2)],
    }
    if dumps:
        first, peak = dumps[0], max(dumps, key=lambda d: d[0][0])
        out['render_target_first_MiB'] = [round(first[0][0] / UNITS['MiB'], 1), first[0][1]]
        out['render_target_peak_MiB'] = [round(peak[0][0] / UNITS['MiB'], 1), peak[0][1]]
        out['total_at_peak_MiB'] = [round(peak[1][0] / UNITS['MiB'], 1), peak[1][1]]
    events = DIR / f'rel2-runs/{name}/events.log'
    if events.exists():
        out['events'] = events.read_text().split('\n')[0].strip()
    kernel = DIR / f'rel2-runs/{name}/kernel.log'
    if kernel.exists():
        k = kernel.read_text()
        m = re.search(r'^Oct 28 (\S+) \S+ kernel: (\S+): page allocation failure: (order:\d)', k, re.M)
        out['kernel_failure'] = [m.group(1)[:8], m.group(2), m.group(3), re.search(r'7\.1\.13-x6e3-\w+', k).group(0)]
    return out


def journal():
    lines = (DIR / 'journal/excerpt.txt').read_text().splitlines()
    out = {'launches': [], 'failures': [], 'oom_killer': [], 'terminations': [], 'saved_with_journalctl': []}
    pending = None
    for line in lines:
        m = STAMP.match(line)
        if not m:
            continue
        t, ident, rest = m.groups()
        if ident == 'kernel' and rest.startswith('Linux version'):
            out['kernel'] = rest.split()[2]
        elif ident == 'kernel' and rest.startswith('Memory:'):
            out['memory_GiB'] = round(int(re.search(r'/(\d+)K', rest).group(1)) / (1 << 20), 1)
        elif ident == 'plasmashell' and 'xonotic-sdl.desktop' in rest:
            if t[:5] not in out['launches']:
                out['launches'].append(t[:5])
        elif ident == 'kernel' and 'page allocation failure' in rest:
            pending = {'time': t, 'process': rest.split(':')[0], 'order': re.search(r'order:\d', rest).group(0)}
            out['failures'].append(pending)
        elif ident == 'kernel' and pending and 'unevictable' not in pending and rest.startswith('Node 0 active_anon'):
            for key in ('unevictable', 'shmem'):
                pending[key + '_GiB'] = round(int(re.search(key + r':(\d+)kB', rest).group(1)) / (1 << 20), 2)
            pending['unevictable'] = True
        elif ident == 'kernel' and pending and 'free_GiB' not in pending and rest.startswith('Node 0 DMA free:'):
            for key in ('free', 'min'):
                pending[key + '_GiB'] = round(int(re.search(r'\b' + key + r':(\d+)kB', rest).group(1)) / (1 << 20), 2)
        elif ident == 'kernel' and 'invoked oom-killer' in rest:
            out['oom_killer'].append([t, rest.split()[0], re.search(r'order=\d', rest).group(0)])
        elif ident == 'systemd-coredump' and 'terminated abnormally' in rest:
            p = re.search(r'\(([^)]+)\) of user \d+ terminated abnormally with(?:out generating a coredump| signal (\S+))', rest)
            if p.group(2):
                out['terminations'].append([t, p.group(1), p.group(2).rstrip(',.')])
        elif ident == 'kwin_wayland_wrapper' and 'ASAHI_SUBMIT render failed' in rest:
            out['kwin_render_failed'] = [t, rest]
        elif ident == 'kernel' and 'failed to unbind closed GEM object' in rest:
            out['unbind_failed'] = [t, rest.split(': ', 1)[1] if ': ' in rest else rest]
        elif ident == 'kwin_wayland_wrapper' and 'VM_BIND failed' in rest:
            out['kwin_restart_vm_bind_failures'] = out.get('kwin_restart_vm_bind_failures', 0) + 1
        elif ident == 'sudo' and 'COMMAND=/usr/sbin/journalctl' in rest:
            out['saved_with_journalctl'].append(t[:5])
    for f in out['failures']:
        f.pop('unevictable', None)
    return out


def calculate():
    check_hashes()
    return {'journal': journal(), 'games': {n: game(n) for n in GAME_LOGS}, 'reruns': {n: run(n) for n in RUNS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'data/10-xonotic/xonotic_summary.json'
    content = json.dumps(calculate(), indent=2) + '\n'
    if args.check:
        assert output.read_text() == content, 'Summary differs; regenerate with make xonotic'
        print('Section 10: Xonotic evidence hashes, crash sequence, game logs and buffer dumps match')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
