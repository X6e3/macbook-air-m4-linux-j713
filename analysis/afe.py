#!/usr/bin/env python3
"""Trackpad AFE start before and after the J713 AFE power sequence.

python3 -I analysis/afe.py          writes data/02-input/afe_summary.json
python3 -I analysis/afe.py --check  verifies hashes and the saved summary

Before: the 15 boots of 15–18 October. Images are written to the ESP from macOS, so a boot whose image differs
from the previous boot's is a first boot after macOS. A boot that repeats the previous image is usually a Linux
reboot, but may also follow macOS; it is counted separately and not classified further.
After: the screen photographs of 18 October, as transcribed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / 'evidence/02-input/afe'
OUT = ROOT / 'data/02-input/afe_summary.json'
READY = 'Interface multi-touch is now ready'
FAIL = re.compile(r'Failed to attach to AFE|No HINT_L')


def checked(entry):
    data = (EV / entry['file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['published_sha256']:
        raise ValueError(f"{entry['file']}: published checksum mismatch")
    lines = data.decode('utf-8').splitlines()
    if len(lines) != entry['line_count']:
        raise ValueError(f"{entry['file']}: line count mismatch")
    return lines


def outcome(lines, name):
    ready = any(READY in x for x in lines)
    failed = any(FAIL.search(x) for x in lines)
    if ready == failed:
        raise ValueError(f'{name}: expected exactly one of READY or an AFE failure')
    return 'ready' if ready else 'afe-failure'


def before(manifest):
    boots, previous = [], manifest['previous_variant']
    for entry in manifest['boots']:
        lines = checked(entry)
        variant = re.search(r'\bx6e3\.v=(\S+)', next(x for x in lines if 'x6e3.v=' in x))[1]
        boots.append({'file': entry['file'], 'variant': variant, 'new_image': variant != previous,
                      'outcome': outcome(lines, entry['file'])})
        previous = variant
    count = lambda new, result: sum(b['new_image'] == new and b['outcome'] == result for b in boots)
    return {'boots': boots,
            'new_image': {'ready': count(True, 'ready'), 'afe_failure': count(True, 'afe-failure')},
            'same_image': {'ready': count(False, 'ready'), 'afe_failure': count(False, 'afe-failure')}}


def photos():
    text = (EV / 'photo-transcriptions.md').read_text(encoding='utf-8')
    result = []
    for head, body in re.findall(r'^## (IMG_\d+), [^\n]*\n(.*?)(?=^## |\Z)', text, re.S | re.M):
        stamps = {k: float(m[1]) for k, p in (('start', r'\[\s*([\d.]+)\] .*AFE reset GPIO before start'),
                                               ('firmware', r'\[\s*([\d.]+)\] .*Sending firmware'),
                                               ('ready', r'\[\s*([\d.]+)\] .*' + READY))
                  for m in [re.search(p, body)] if m}
        result.append({'photo': head, 'outcome': outcome(body.splitlines(), head),
                       'start_to_firmware_ms': round((stamps['firmware'] - stamps['start']) * 1000, 1),
                       'ready_s': stamps.get('ready')})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((EV / 'manifest.json').read_text())
    result = {'schema': 1, 'scope': 'Archived boots and photographs; not a new hardware test',
              'before': before(manifest['before']), 'photos': photos()}
    if args.check:
        if json.loads(OUT.read_text()) != result:
            raise ValueError('Saved AFE summary is stale; run make afe')
        print(f"AFE: {len(manifest['before']['boots'])} boot hashes, outcomes and photo timings match")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + '\n')
        print('Wrote data/02-input/afe_summary.json')


if __name__ == '__main__':
    main()
