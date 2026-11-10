#!/usr/bin/env python3
"""Recompute the section 10 texture-lifetime results from the Mesa resource logs of TL1 and TL2: which 1024x1024
DXT5 texture resources exist, and in which phase the single-level one is destroyed."""
import argparse
import hashlib
import json
import re
from pathlib import Path

if not __debug__:
    raise SystemExit('Run evidence checks without -O')

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'evidence/10-texture'
RX = re.compile(r'\b(New|Destroy): (\S+) 1024x1024x1 \d+L \d+/(\d+)M .*?Size=0x([0-9a-f]+).*?H:([0-9a-f]+)/')
SINGLE, FULL = (1, 0x400000), (11, 0x558000)   # (levels, bytes): level 0 alone, and the full chain as RGBA8
MiB = 1 << 20


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


def run(prefix, case):
    """Fields of <prefix>-<case>.out and the 1024x1024 resource events as (kind, shape, handle, stage)."""
    out = dict(line.split('=', 1) for line in read(f'{prefix}-{case}.out').splitlines() if '=' in line)
    assert read(f'{prefix}-{case}.status').strip() == 'status=0', case
    assert out['renderer'].startswith('Apple M4') and out['s3tc_extension'] == 'yes', case
    stage, events = None, []
    for line in read(f'{prefix}-{case}.log').splitlines():
        m = re.match(r'TL\d ns=\d+ stage=(\S+)', line)
        if m:
            stage = m.group(1)
            continue
        m = RX.search(line)
        if m:
            kind, fmt, levels, size, handle = m.groups()
            assert fmt == 'r8g8b8a8_unorm', (case, fmt)
            events.append((kind, (int(levels), int(size, 16)), handle, stage))
    assert {shape for _, shape, _, _ in events} <= {SINGLE, FULL}, case
    return out, events


def tl1():
    result = {}
    for case in 'ABCDEOV':
        out, events = run('tl1', case)
        single = [e for e in events if e[1] == SINGLE]
        full = [e for e in events if e[1] == FULL]
        assert [e[0] for e in single] == ['New', 'Destroy'] and [e[0] for e in full] == ['New', 'Destroy'], case
        result[case] = {'single_level_created': single[0][3], 'single_level_destroyed': single[1][3],
                        'full_chain_created': full[0][3], 'full_chain_destroyed': full[1][3]}
    for case in 'AB':
        assert result[case]['single_level_destroyed'] == 'delete_begin', case
    for case in 'CDEOV':
        assert result[case]['single_level_destroyed'] == 'draw_begin', case
    pixel = dict(line.split('=', 1) for line in read('tl1-V.out').splitlines() if '=' in line)['pixel_rgba']
    assert pixel == '255,255,255,255'
    return {'scenarios': result, 'white_texture_readback': pixel}


def tl2():
    result = {}
    for case in 'ABCDE':
        out, events = run('tl2', case)
        n, draws, maxlevel = int(out['textures']), int(out['draw_count']), out['maxlevel'] == '1'
        live, checkpoint = {}, None
        for kind, shape, handle, stage in events:
            if checkpoint is None and stage in ('checkpoint_before_delete', 'readback_begin', 'readback_end',
                                                'delete_begin'):
                checkpoint = {s: sum(v == s for v in live.values()) for s in (SINGLE, FULL)}
            if kind == 'New':
                live[handle] = shape
            else:
                assert live.pop(handle) == shape, (case, handle)
        if checkpoint is None:
            checkpoint = {s: sum(v == s for v in live.values()) for s in (SINGLE, FULL)}
        created_single = sum(k == 'New' and s == SINGLE for k, s, _, _ in events)
        expected_single = 0 if maxlevel else n - draws
        assert checkpoint[SINGLE] == expected_single and checkpoint[FULL] == n, case
        assert created_single == (0 if maxlevel else n), case
        result[case] = {'textures': n, 'drawn': draws, 'max_level_set_first': maxlevel,
                        'single_level_created': created_single, 'single_level_live_at_checkpoint': checkpoint[SINGLE],
                        'full_chain_live_at_checkpoint': checkpoint[FULL],
                        'live_MiB': round((checkpoint[SINGLE] * SINGLE[1] + checkpoint[FULL] * FULL[1]) / MiB, 2),
                        'pixel': out['pixel_rgba']}
    return result


def calculate():
    check_hashes()
    out = dict(line.split('=', 1) for line in read('tl1-V.out').splitlines() if '=' in line)
    dxt = int(out['dxt5_bytes_per_texture'])
    return {'dxt5_bytes_per_texture': dxt, 'rgba8_full_chain_bytes': FULL[1],
            'rgba8_over_dxt5': round(FULL[1] / dxt, 2), 'tl1': tl1(), 'tl2': tl2()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'data/10-texture/texture_summary.json'
    content = json.dumps(calculate(), indent=2) + '\n'
    if args.check:
        assert output.read_text() == content, 'Summary differs; regenerate with make texture'
        print('Section 10: evidence hashes and texture lifetimes match')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
