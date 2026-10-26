#!/usr/bin/env python3
"""Recompute the section 8 reboot tallies from the archived logs and my observation notes. This does not reboot
anything."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

if not __debug__:
    raise SystemExit('Run evidence checks without -O')

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'evidence/08-reboot'
FIRST_TRACED_BOOT = '575a5871'   # first logged boot with the traced stage 1 (source notes)
STALL_GAP = 75                   # seconds, as in reboot-loop.sh


def read(name):
    return (DIR / name).read_text()


def check_hashes():
    for line in read('SHA256SUMS').splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((DIR / name).read_bytes()).hexdigest() == expected, name
    for item in json.loads(read('manifest.json'))['files']:
        raw = (DIR / item['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['published_sha256'], item['file']
        assert len(raw.splitlines()) == item['published_lines'], item['file']


def observations():
    """{(run, start): (count, stalled)} from the table in observations.md."""
    rows = {}
    for line in read('observations.md').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) == 5 and cells[2].isdigit():
            run, start, count, stalled = cells[0], cells[1], int(cells[2]), int(cells[3])
            assert start in ('reboot from Linux', 'cold start') and stalled <= count, line
            assert (run, start) not in rows, line
            rows[run, start] = (count, stalled)
    assert rows, 'observations.md: no table rows'
    return rows


def reboot_log():
    """6k1-boots.log: the distinct boots on 6boot-K1 with the GPU on, and the answered reboots on the GPU-off image."""
    text = read('6k1-boots.log')
    boots = re.findall(r'^\S+ \S+ boot=(\w{8}) tag=(\S+) ', text, re.M)
    gpu_on = list(dict.fromkeys(b for b, tag in boots if tag == '6boot-k1-root2'))
    nogpu = re.findall(r'^\S+ \S+ reboot mode=desktop@6boot-k1nogpu-root2 from=(\w{8}) stalled=(yes|no)$', text, re.M)
    return gpu_on, [s == 'yes' for _, s in nogpu]


def loop_log():
    """auto-boots.log: (boot, gap seconds, verdict) for each logged reboot, split at the first traced boot."""
    before, after, seen = [], [], False
    for line in read('auto-boots.log').splitlines():
        m = re.match(r'\S+ \S+ loop \d+/\d+ boot=(\w{8}) .* ntp=(\w+) ', line)
        if not m:
            assert re.match(r'\S+ \S+ loop (set up|ended):', line), line
            continue
        boot, ntp = m.groups()
        seen |= boot == FIRST_TRACED_BOOT
        r = re.search(r'\| reboot from \w{8}: (\d+)s -> (clean|stall\?)( |$)', line)
        if r:
            assert ntp == 'yes', line
            assert (r[2] == 'clean') == (int(r[1]) <= STALL_GAP), line
            (after if seen else before).append((boot, int(r[1]), r[2]))
    assert seen, 'first traced boot not in the loop log'
    return before, after


def fisher_one_sided(a_stalled, a_n, b_stalled, b_n):
    """P(at least a_stalled of all stalls fall in group a) when both groups share one stall chance."""
    k, n = a_stalled + b_stalled, a_n + b_n
    return sum(math.comb(a_n, x) * math.comb(b_n, k - x) for x in range(a_stalled, min(k, a_n) + 1)) / math.comb(n, k)


def calculate():
    check_hashes()
    notes = observations()
    gpu_on, nogpu = reboot_log()
    dongle_free, traced = loop_log()

    # Machine logs where they exist, my notes for the starts that left no line.
    assert len(gpu_on) == notes['6boot-k1', 'reboot from Linux'][0], 'boots reached on 6boot-K1 vs reboots noted'
    assert len(nogpu) == 8 and sum(nogpu) == 1
    assert len(dongle_free) == 2 and all(v == 'clean' for _, _, v in dongle_free)
    runs = {
        'k1': {'reboot from Linux': notes['k1', 'reboot from Linux'], 'cold start': notes['k1', 'cold start']},
        '6boot-k1': {'reboot from Linux': notes['6boot-k1', 'reboot from Linux'],
                     'cold start': notes['6boot-k1', 'cold start']},
        'env': {'reboot from Linux': notes['env', 'reboot from Linux'], 'cold start': notes['env', 'cold start']},
        'nogpu': {'reboot from Linux': (len(nogpu), sum(nogpu)), 'cold start': notes['nogpu', 'cold start']},
        'dongle-free': {'reboot from Linux': (len(dongle_free) + notes['dongle-free', 'reboot from Linux'][0],
                                              notes['dongle-free', 'reboot from Linux'][1]),
                        'cold start': notes['dongle-free', 'cold start']},
    }
    assert set(notes) <= {(r, s) for r in runs for s in runs[r]}, 'a note row belongs to no run'
    total = {s: tuple(sum(runs[r][s][i] for r in runs) for i in (0, 1)) for s in ('reboot from Linux', 'cold start')}
    gaps = [g for _, g, _ in traced]
    assert all(v == 'clean' for _, _, v in traced)

    old = total['reboot from Linux']
    p = fisher_one_sided(old[1], old[0], 0, len(traced))
    as_dict = lambda c: {'starts': c[0], 'stalled': c[1]}
    return {
        'old_stage1': {
            'object': 'aec6f182',
            'runs': {r: {s: as_dict(c) for s, c in v.items()} for r, v in runs.items()},
            'reboots_from_linux': as_dict(old),
            'cold_starts': as_dict(total['cold start']),
            'all_starts': as_dict(tuple(a + b for a, b in zip(old, total['cold start']))),
        },
        'traced_stage1': {
            'object': 'aecfdd4e',
            'reboots_from_linux': as_dict((len(traced), 0)),
            'reboot_to_logged_boot_s': {'min': min(gaps), 'max': max(gaps)},
        },
        'gpu': {'on_6boot_k1': as_dict(runs['6boot-k1']['reboot from Linux']),
                'off_nogpu_image': as_dict(runs['nogpu']['reboot from Linux'])},
        'reboots_fisher_one_sided_p': round(p, 6),
        'scope': 'stage 1 cannot be seen from Linux; stalls without a log line are my notes',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'data/08-reboot/reboot_summary.json'
    content = json.dumps(calculate(), indent=2) + '\n'
    if args.check:
        assert output.read_text() == content, 'Summary differs; regenerate with make reboot'
        print('Section 8: evidence hashes and reboot tallies match')
    else:
        output.write_text(content)
        print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
