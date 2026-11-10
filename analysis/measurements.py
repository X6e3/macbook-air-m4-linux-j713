#!/usr/bin/env python3
"""Recompute section 9 (27 October 2026) from the archived evidence: the MCA window map, the blind stride runs,
the left/right tests, the amplifier slot registers, the phone recordings and the O2 dose test. This does not run
hardware tests."""
import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

if not __debug__:
    raise SystemExit('Run evidence checks without -O')

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'evidence/09-measurements'
TAIL = 25   # samples per phase median, as in o-gpu-summary.py


def read(name):
    return (DIR / name).read_text()


def check_hashes():
    listed = set()
    for line in read('SHA256SUMS').splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((DIR / name).read_bytes()).hexdigest() == expected, name
        listed.add(name)
    for item in json.loads(read('manifest.json'))['files']:
        raw = (DIR / item['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['published_sha256'], item['file']
        assert len(raw.splitlines()) == item['published_lines'], item['file']
        assert item['file'] in listed, item['file']
    on_disk = {str(p.relative_to(DIR)) for p in DIR.rglob('*') if p.is_file()} - {'SHA256SUMS'}
    assert on_disk == listed, sorted(on_disk ^ listed)
    return len(listed)


def mca_map():
    words = {}
    chunks = sorted(DIR.glob('map/chunk-*-a.txt'))
    for a in chunks:
        assert a.read_text() == a.with_name(a.name[:-6] + '-b.txt').read_text(), a.name   # two reads, same words
        for line in a.read_text().splitlines():
            addr, rest = line.split(':')
            for i, w in enumerate(rest.split()):
                words[int(addr, 16) + 4 * i] = int(w, 16)
    state = read('map/state.txt').split()
    assert state[-2:] == ['bad', '0x8c00'], state[-2:]
    end = max(words) + 4
    assert end == 0x8c00 and min(words) == 0
    nonzero = lambda lo, hi: [a for a in range(lo, hi, 4) if words.get(a)]
    clock = [s for s in range(0x2000, 0x3000, 0x100) if words.get(s + 4)]
    serial = [s for s in range(0x6000, 0x8000, 0x100) if words.get(s + 4)]
    assert clock == list(range(0x2000, 0x2600, 0x100)) and not nonzero(0x2600, 0x3000)
    assert serial == list(range(0x6000, 0x7100, 0x100)) and all(words.get(s + 0x84) for s in serial)
    period = json.loads(read('map/o1-period.json'))
    return {'chunks': len(chunks), 'second_read_identical': True, 'readable_bytes': hex(end),
            'hung_at': '0x8c00',
            'clock_blocks_with_word_0x04': [hex(s) for s in clock],
            'clock_page_nonzero_after_0x2600': 0,
            'unit1_port_words': {hex(a): hex(words[a]) for a in (0x2160, 0x2164, 0x2168)},
            'serializer_blocks_with_words_0x04_and_0x84': [hex(serial[0]), hex(serial[-1]), len(serial)],
            'o1_period_of_driver_page': hex(period['period']), 'o1_other_periods': [hex(p) for p in period['others']]}


def trials(name):
    lines = read(name).splitlines()
    head = lines[0].split()
    return [dict(zip(head, l.split())) for l in lines[1:] if l.strip()]


def stride():
    rows = trials('stride/ab-trials.txt')
    out = {'trials': len(rows), 'A_0x100': [], 'B': {}, 'C_one_unit': None}
    for r in rows:
        if r['card'] == 'none':
            outcome = 'no speaker card'
        elif int(r['faults']) > 0:
            outcome = 'amplifier fault'
        elif r['heard1'] == r['heard2'] == 'heard':
            outcome = 'both heard'
        else:
            outcome = f"{r['heard1']}/{r['heard2']}"
        if r['kind'] == 'A':
            out['A_0x100'].append(outcome)
        elif r['kind'] == 'B':
            out['B'][r['stride']] = outcome
        else:
            out['C_one_unit'] = outcome
    assert out['A_0x100'] == ['both heard'] * 6
    assert out['B'] == {'0x200': 'amplifier fault', '0xc000': 'no speaker card', '0x80': 'amplifier fault',
                        '0x400': 'amplifier fault'}
    assert out['C_one_unit'] == 'no speaker card'
    earlier = {}
    for p in sorted(DIR.glob('stride/earlier/ab-trials-*.txt')):
        tag = p.name[len('ab-trials-'):-4]
        got = [x for r in trials('stride/earlier/' + p.name) for x in (r.get('heard1'), r.get('heard2'))
               if x not in (None, '-')]
        earlier[tag] = {k: got.count(k) for k in sorted(set(got))}
    out['earlier_runs'] = earlier
    return out


def sides():
    regs = read('sides/regs-20261027-191026.txt')
    cfg = dict(re.findall(r'== (0-00\w\w)\s+\(.*CFG3 0c=(\w\w)\)', regs))
    slot = lambda f: dict(re.findall(r'(0-00\w\w): 000a: \w\w 000c: (\w\w)', read(f)))
    before, after = slot('sides/lr-blind/system.txt'), slot('sides/lr-one/system.txt')
    assert cfg == before == {'0-0038': '00', '0-003b': '11'} and after == {'0-0038': '11', '0-003b': '00'}
    blind = trials('sides/lr-blind/trials.txt')
    pairs = [r['first'] + ' ' + r['second'] for r in blind]
    one = trials('sides/lr-one/trials.txt')
    normal = [(r['channel'] == '1') == (r['answer'] == 'l') for r in one]
    n, k = len(one), sum(normal)
    p = sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n
    per = {c: {s: sum(1 for r in one if r['channel'] == c and r['answer'] == s) for s in 'lr'} for c in '12'}
    assert all(int(r['faults']) == 0 for r in blind + one)
    return {'amplifier_CFG3_before_fix': before, 'amplifier_CFG3_after_fix_LR1': after,
            'two_burst_trials': len(blind), 'two_burst_answer_pairs': {x: pairs.count(x) for x in sorted(set(pairs))},
            'one_burst_trials': n, 'one_burst_normal': k, 'one_burst_p_at_least_this_many_by_guessing': p,
            'one_burst_answers_by_channel': per, 'faults': 0}


PHONE_BIN = 0.5    # s: burst detection works on half-second medians
PHONE_RISE = 4.0   # dB above the room that counts as a burst


def phone_bursts(samples):
    """The loud stretches of one recording: half-second medians at least PHONE_RISE above the room (the median
    of the quietest third of the bins), joined across one quiet bin, at least 1.5 s long."""
    bins = {}
    for t, db in samples:
        bins.setdefault(int(t / PHONE_BIN), []).append(db)
    med = {k: statistics.median(v) for k, v in bins.items()}
    room = statistics.median(sorted(med.values())[:max(1, len(med) // 3)])
    runs = []
    for k in sorted(k for k in med if med[k] >= room + PHONE_RISE):
        if runs and k - runs[-1][-1] <= 2:
            runs[-1].append(k)
        else:
            runs.append([k])
    bursts = []
    for r in runs:
        lo, hi = r[0] * PHONE_BIN, (r[-1] + 1) * PHONE_BIN
        if hi - lo >= 1.5:
            bursts.append({'from_s': lo, 'to_s': hi,
                           'median_dB': round(statistics.median(db for t, db in samples if lo <= t < hi), 1)})
    return round(room, 1), bursts


def phone():
    """Each export's samples, the stretch of the recording they cover, and the noise bursts in them. The app
    exports at most about the last 20 s: the 18:07 export holds only its last segment."""
    meta = {l.split(',')[0]: dict(zip(('system', 'phone', 'played'), l.split(',')[1:]))
            for l in read('sides/phone/recordings.csv').splitlines()[1:] if l}
    out = {}
    for amp in sorted(DIR.glob('sides/phone/*-amplitudes.csv')):
        stem = amp.name[:-len('-amplitudes.csv')]
        rows = [tuple(map(float, l.split(','))) for l in amp.read_text().splitlines()[1:] if l]
        a = [(t, db) for t, db in rows if not math.isnan(db)]
        ev = [l.split(',') for l in (DIR / f'sides/phone/{stem}-events.csv').read_text().splitlines()[1:] if l]
        starts = [float(e[1]) for e in ev if e[0] == 'START']
        stops = [float(e[1]) for e in ev if e[0] == 'PAUSE']
        recorded = sum(e - s for s, e in zip(starts, stops))
        span = rows[-1][0] - rows[0][0]
        if abs(span - recorded) < 1:
            holds = 'the whole recording'
        else:
            assert abs(span - (stops[-1] - starts[-1])) < 1, stem
            holds = 'its last segment only'
        room, bursts = phone_bursts(a)
        out[stem] = {**meta[stem], 'recorded_s': round(recorded, 1), 'samples_s': round(span, 1),
                     'samples_hold': holds, 'room_dB': room, 'bursts': bursts, 'last_level_dB': round(a[-1][1], 1)}
    assert set(out) == set(meta), sorted(set(out) ^ set(meta))
    return {'recordings': out, 'burst_rule': f'{PHONE_BIN} s medians >= room + {PHONE_RISE} dB, >= 1.5 s',
            'scope': 'phone microphone, calibration offset 0 dB: relative levels, not SPL'}


def dose():
    rows = [l.split() for l in read('dose/sensors.txt').splitlines() if l.strip()]
    names, data = rows[0][1:], [r for r in rows[1:] if len(r) == len(rows[0])]
    col = lambda r, n: int(r[1 + names.index(n)])
    pauses = [tuple(map(int, l.split())) for l in read('dose/pauses.txt').splitlines() if l.strip()]
    in_pause = lambda t0, t1: any(a < t1 and t0 < b for a, b in pauses)
    start = int(read('dose/load-start.txt'))
    m = re.search(r'done: (\d+) draws in ([\d.]+) s, GL error (0x[0-9a-f]+)', read('dose/load.txt'))
    assert m and int(m[3], 16) == 0
    load_end = start + int(float(m[2]))
    phases = [(int(l.split()[0]), l.split()[1]) for l in read('dose/phases.txt').splitlines() if l.strip()]
    ends = [p[0] for p in phases[1:]] + [load_end]

    def watts(t1):
        sel = [r for r in data if int(r[0]) < t1 and not in_pause(int(r[0]), int(r[0]) + 1)][-TAIL:]
        return statistics.median(col(r, 'SMC_PP1b') / 1e6 for r in sel)

    results = [(label, watts(t1)) for (_, label), t1 in zip(phases, ends)]
    a = [w for l, w in results if l == 'A']
    by = {}
    for l, w in results:
        if l != 'A':
            by.setdefault(l, []).append(round(w, 2))
    word = lambda w: {k: v for k, v in by.items() if k.startswith(w + '=')}
    for w in ('+0x84', '+0x90', '+0x94'):
        assert all(abs(x - statistics.median(a)) < 0.3 for v in word(w).values() for x in v), w
    assert by['+0x88=750'] == by['+0x98=750'] == [6.04]
    assert by['+0x88=500'] == by['+0x8c=500'] == [3.69]
    ladder = [by[f'+0x8c={d}'][0] for d in range(50, 1000, 50)]
    assert all(a < b for a, b in zip(ladder[:-3], ladder[1:-2])), ladder   # rises at every step from 50 to 900
    assert all(abs(x - statistics.median(a)) < 0.3 for x in ladder[-2:])   # 900 and 950: as with no limit
    changed = {int(r[1 + names.index('region_c_changed')]) for r in data}
    assert changed == {0}
    return {'phases': len(phases), 'pauses': len(pauses), 'paused_s': sum(b - a for a, b in pauses),
            'load_s': float(m[2]), 'draws': int(m[1]),
            'A_median_PP1b_W': {'min': round(min(a), 2), 'max': round(max(a), 2)},
            'dose_PP1b_W': {k: by[k] for k in sorted(by, key=lambda s: (s.split('=')[0], int(s.split('=')[1])))},
            'region_c_changed_by_firmware': 0,
            'scope': f'median SMC PP1b over the last {TAIL} s of load in each phase, paused seconds left out'}


def calculate():
    n = check_hashes()
    return {'evidence_files': n, 'map': mca_map(), 'stride': stride(), 'sides': sides(), 'phone': phone(),
            'dose': dose()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(calculate(), indent=2) + '\n'
    output = ROOT / 'data/09-measurements/measurements_summary.json'
    if args.check:
        assert output.read_text() == content, 'saved summary differs; run make measurements'
        print('Section 9: evidence hashes, map, stride runs, sides, slots and dose results match')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
