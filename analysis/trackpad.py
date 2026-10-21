#!/usr/bin/env python3
"""Verify retained evidence and derive the trackpad/AFE timeline. No device access."""
import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / 'evidence/02-input/trackpad'
OUT = ROOT / 'data/02-input/trackpad_summary.json'


def derive():
    manifest = json.loads((EV / 'manifest.json').read_text())
    for entry in manifest['files']:
        data = (EV / entry['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['published_sha256']:
            raise ValueError(f"Checksum mismatch: {entry['file']}")
        if len(data.splitlines()) != entry['line_count']:
            raise ValueError(f"Line count mismatch: {entry['file']}")
    boots = []
    current = None
    events = {
        'firmware_missing': 'Direct firmware load for apple/tpmtfw-j713.bin failed with error -2',
        'firmware_sent': 'Sending firmware for multi-touch',
        'reset': 'Resetting multi-touch',
        'ready': 'Interface multi-touch is now ready',
        'afe_failure': 'Failed to attach to AFE',
        'hint_missing': 'No HINT_L',
        'start_timeout': 'iface multi-touch start timed out',
        'already_starting': 'Interface multi-touch is already starting',
        'userspace_open_failure': 'Operation now in progress',
    }
    for number, line in enumerate((EV / 'journal-timeline.txt').read_text().splitlines(), 1):
        header = re.match(r'== boot (-?\d+) x6e3.v=(\S+) x6e3.k=(\S+)', line)
        if header:
            current = dict(boot_index=int(header[1]), variant=header[2], kernel_hash_prefix=header[3],
                           header_line=number, events={})
            boots.append(current)
            continue
        stamp = re.match(r'\[\s*([\d.]+)\]', line)
        if stamp and current is not None:
            for key, token in events.items():
                if token in line:
                    current['events'].setdefault(key, []).append(dict(line=number, seconds=stamp[1]))
    for boot in boots:
        ev = boot['events']
        if ev.get('ready') and ev.get('reset'):
            boot['reset_to_ready_ms'] = str((Decimal(ev['ready'][0]['seconds']) - Decimal(ev['reset'][0]['seconds']))*1000)
    firmware_boots = [b for b in boots if b['events'].get('firmware_sent') and b['variant']=='mtp-dapf-w2']
    selected_counts = dict(b2_with_firmware=len(firmware_boots),
                          b2_with_firmware_ready=sum(bool(b['events'].get('ready')) for b in firmware_boots),
                          b2_with_firmware_afe_failure=sum(bool(b['events'].get('afe_failure')) for b in firmware_boots))
    followup = {}
    for name in ['afe-fail-20261007.txt','afe-ready-20261007.txt']:
        lines = (EV/name).read_text().splitlines()
        followup[name] = {key: [i for i,line in enumerate(lines,1) if token in line] for key,token in events.items()}
        followup[name]['retry_lines'] = [i for i,line in enumerate(lines,1) if 'resetting again (attempt' in line]
    return dict(schema=1,scope='Counts from selected archived records only; not platform reliability estimates',
                selected_counts=selected_counts,boots=boots,october_followup=followup,
                physical_cursor_evidence='Physical observation at the machine; no log or input trace kept',
                raw_hid_evidence='Debugfs observation at the machine; packet capture not kept')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    result = derive()
    if args.check:
        if json.loads(OUT.read_text()) != result:
            raise ValueError('Saved trackpad summary is stale; run make trackpad')
        n = len(json.loads((EV / 'manifest.json').read_text())['files'])
        print(f'Trackpad: {n} evidence hashes, line counts and derived timeline match')
    else:
        OUT.write_text(json.dumps(result,indent=2)+'\n')
        print('Wrote data/02-input/trackpad_summary.json')


if __name__ == '__main__':
    main()
