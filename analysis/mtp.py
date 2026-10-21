#!/usr/bin/env python3
"""Derive the A1/B1/B2 results and source line references from the MTP startup logs, and the
RUN-to-interrupt timing from the three earlier wide1 boots.

python3 -I analysis/mtp.py          writes data/02-input/mtp_summary.json
python3 -I analysis/mtp.py --check  verifies hashes, lineage and saved results

Only MTP's RTKit instance is used for protocol/wake events. NVMe has a
separate RTKit instance and must not be counted as MTP initialization.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / 'evidence/02-input'
OUT = ROOT / 'data/02-input/mtp_summary.json'
MTP = 'rtkit-helper 394600000.mtp:'
HID = 'dockchannel-hid 394b28000.input:'
DART = 'apple-dart 394800000.iommu:'


def only(matches, label, required=False):
    if len(matches) > 1 or (required and not matches):
        raise ValueError(f'{label}: expected {"one" if required else "at most one"}, found {len(matches)}')
    return matches[0] if matches else None


def summarize(entry):
    data = (EV / entry['file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['published_sha256']:
        raise ValueError(f"{entry['id']}: published checksum mismatch")
    lines = data.decode('utf-8').splitlines()
    if len(lines) != entry['line_count']:
        raise ValueError(f"{entry['id']}: line count mismatch")

    def find(pattern, device=None, required=False):
        result = []
        for n, text in enumerate(lines, 1):
            match = re.search(pattern, text) if device is None or device in text else None
            if match:
                result.append({'line': n, 'groups': list(match.groups())})
        return only(result, f"{entry['id']}:{pattern}", required)

    release = find(r'Linux version (\S+)', required=True)
    variant = find(r'\bx6e3\.v=(\S+)', required=True)
    if release['groups'][0] != entry['kernel_release'] or variant['groups'][0] != entry['command_line_variant']:
        raise ValueError(f"{entry['id']}: kernel/variant lineage mismatch")
    wake = find(r'apple_rtkit_wake\(\) returned (-?\d+) t=(\d+)us irqs=(\d+)', MTP, True)
    protocol = find(r'RTKit: Initializing \(protocol version (\d+)\)', MTP)
    timeout = find(r'RTKit: timed out waiting for (.*): (-?\d+)', MTP)

    def rules(tag, result_tag):
        found = []
        for n, text in enumerate(lines, 1):
            if MTP not in text:
                continue
            match = re.search(re.escape(tag) + r' dapf\[(\d+)\].* (MATCH|DIFF)$', text)
            if match:
                found.append({'index': int(match[1]), 'match': match[2] == 'MATCH', 'line': n})
        result = find(re.escape(result_tag) + r' RESULT (?:MATCH|DIFF) \((\d+)/(\d+) entries match ADT\)', MTP)
        if not found and result is None:
            return None
        if sorted(x['index'] for x in found) != list(range(9)) or result is None:
            raise ValueError(f"{entry['id']}: incomplete DAPF rules for {tag}")
        count = sum(x['match'] for x in found)
        if result['groups'] != [str(count), '9']:
            raise ValueError(f"{entry['id']}: DAPF result disagrees with its rule lines")
        return {'matches': count, 'entries': 9, 'result_line': result['line'], 'rules': found}

    before = rules('A1', 'A1:') if entry['id'] == 'a1' else rules('B1: pre-write', 'B1: pre-write')
    after = rules('B1: post-write', 'B1: post-write')
    written_end = find(r'write rule\[7\].* end=(0x[0-9a-f]+)', MTP)
    read_end = find(r'post-write dapf\[7\].* end=(0x[0-9a-f]+)', MTP)
    firmware = find(r'Direct firmware load for apple/tpmtfw-j713.bin failed with error (-?\d+)', HID)
    return {
        'id': entry['id'], 'file': entry['file'], 'line_count': len(lines),
        'kernel': {'release': release['groups'][0], 'line': release['line']},
        'variant': {'value': variant['groups'][0], 'line': variant['line']},
        'dapf_before': before, 'dapf_after': after,
        'rule7_end_written': written_end, 'rule7_end_readback': read_end,
        'wake': {'return': int(wake['groups'][0]), 'trace_time_us': int(wake['groups'][1]),
                 'dart_irq_count': int(wake['groups'][2]), 'line': wake['line']},
        'mtp_protocol': protocol, 'timeout': timeout,
        'delay_trace': find(r'10 ms after RUN, before wake', MTP),
        'mtp_hello': find(r'MTP Says Hello', MTP),
        'keyboard_input': find(r'input: Apple MTP keyboard Keyboard'),
        'keyboard_ready': find(r'Keyboard ready', MTP),
        'trackpad_firmware_error': firmware,
        'multitouch_ready': find(r'Interface multi-touch is now ready', HID),
    }


def survey(entry):
    """wide1: when the DART interrupts start relative to RUN and to the first mailbox message."""
    data = (EV / entry['file']).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['published_sha256']:
        raise ValueError(f"{entry['id']}: published checksum mismatch")
    lines = data.decode('utf-8').splitlines()
    if len(lines) != entry['line_count']:
        raise ValueError(f"{entry['id']}: line count mismatch")

    def first(pattern, device):
        for n, text in enumerate(lines, 1):
            match = re.search(pattern, text) if device in text else None
            if match:
                return n, match
        raise ValueError(f"{entry['id']}: missing {pattern}")

    if first(r'Linux version (\S+)', 'Linux version')[1][1] != entry['kernel_release'] or \
            first(r'\bx6e3\.v=(\S+)', 'Kernel command line')[1][1] != entry['command_line_variant']:
        raise ValueError(f"{entry['id']}: kernel/variant lineage mismatch")
    run_line, run = first(r'CPU_CONTROL after RUN = 0x10 t=(\d+)us', MTP)
    irq_line, irq = first(r'x6e3 irq-first: t=(\d+)us', DART)
    delay_line, delay = first(r'10 ms after RUN, before wake: .* irqs=(\d+)', MTP)
    tx_line, tx = first(r'mbox TX #1 .* t=(\d+)us', MTP)
    wake_line, wake = first(r'apple_rtkit_wake\(\) returned (-?\d+) t=\d+us irqs=(\d+)', MTP)
    if not int(run[1]) < int(irq[1]) < int(tx[1]):
        raise ValueError(f"{entry['id']}: interrupts do not start between RUN and the first mailbox message")
    return {'id': entry['id'], 'file': entry['file'],
            'run_to_first_irq_us': int(irq[1]) - int(run[1]), 'first_irq_to_tx1_us': int(tx[1]) - int(irq[1]),
            'irqs_at_10ms_checkpoint': int(delay[1]), 'wake_return': int(wake[1]), 'irqs_at_wake_return': int(wake[2]),
            'lines': {'run': run_line, 'first_irq': irq_line, 'checkpoint_10ms': delay_line, 'tx1': tx_line,
                      'wake_return': wake_line}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((EV / 'manifest.json').read_text())
    if [x['id'] for x in manifest['logs']] != ['a1', 'b1', 'b1-repeat', 'b2']:
        raise ValueError('Unexpected experiment selection/order')
    result = {'schema': 1, 'scope': 'Archived MTP startup observations; not a new hardware test',
              'logs': [summarize(x) for x in manifest['logs']],
              'wide1': [survey(x) for x in manifest['survey_logs']]}
    if args.check:
        if json.loads(OUT.read_text()) != result:
            raise ValueError('Saved MTP summary is stale; run make mtp')
        n = len(manifest['logs']) + len(manifest['survey_logs'])
        print(f'MTP: {n} log hashes, lineage, DAPF readback counts, wide1 timing and saved summary match')
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + '\n')
        print('Wrote data/02-input/mtp_summary.json')


if __name__ == '__main__':
    main()
