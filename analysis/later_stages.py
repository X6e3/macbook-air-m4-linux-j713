#!/usr/bin/env python3
"""Recompute sections 4–7 from archived evidence. This does not run hardware tests."""
import argparse
import collections
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

if not __debug__:
    raise SystemExit('Run evidence checks without -O')

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'


def read(section, name):
    return (EVIDENCE / section / name).read_text()


def table(section, name, allow_na=()):
    lines = read(section, name).splitlines()
    header = lines[0].split()
    result = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split()
        assert len(values) == len(header), (name, line)
        result.append({k: None if v == 'NA' and k in allow_na else float(v) for k, v in zip(header, values)})
    assert result, f'{name}: empty table'
    assert all(v is None or math.isfinite(v) for row in result for v in row.values()), f'{name}: nonfinite value'
    if 't' in header:
        assert all(a['t'] < b['t'] for a, b in zip(result, result[1:])), f'{name}: unordered/duplicate timestamps'
    return result


def draw_rates(name, start):
    """(time, draws/s) from a stress-load log; each reading covers the preceding 10 s."""
    return [(start + float(m[1]), float(m[2]))
            for m in re.finditer(r'^([\d.]+) s: ([\d.]+) draws/s$', read('04-gpu', name), re.M)]


def phase_starts(name):
    return [(int(t), label) for t, label in (l.split() for l in read('04-gpu', name).splitlines())]


def phase_medians(rows, name, rates, length, tail):
    phases = phase_starts(name)
    out = []
    for i, (t0, label) in enumerate(phases):
        t1 = phases[i + 1][0] if i + 1 < len(phases) else t0 + length
        sel = [r for r in rows if t1 - tail <= r['t'] < t1]
        out.append({'setting': label,
                    'median_PP1b_W': statistics.median(r['SMC_PP1b'] for r in sel)/1e6,
                    'median_draws_per_second': statistics.median(x for t, x in rates if t1 - tail <= t < t1),
                    'median_TVS1_C': statistics.median(r['SMC_TVS1'] for r in sel)/1000})
    return out


def regulation(name, samples, start):
    first = next(i for i, r in enumerate(samples) if r['cooling_state'] > 0)
    regulated = samples[first:]
    return {'first_cooling_state_seconds': regulated[0]['t'] - start,
            'TVS1_C': {'min': min(r['SMC_TVS1'] for r in regulated)/1000,
                       'median': statistics.median(r['SMC_TVS1'] for r in regulated)/1000,
                       'max': max(r['SMC_TVS1'] for r in regulated)/1000},
            'max_cooling_state': int(max(r['cooling_state'] for r in samples)),
            'regulated_cooling_fraction': sum(r['cooling_state'] > 0 for r in regulated)/len(regulated),
            'regulated_mean_PP1b_W': statistics.mean(r['SMC_PP1b'] for r in regulated)/1e6,
            'whole_run_max_TCMz_C': max(r['SoC_TCMz'] for r in samples)/1000,
            'min_draws_per_second': min(x for _, x in draw_rates(f'{name}-load.txt', start))}


def calculate():
    for section in ['04-gpu', '05-display', '06-audio', '07-idle']:
        for line in read(section, 'SHA256SUMS').splitlines():
            expected, name = line.split('  ', 1)
            assert hashlib.sha256((EVIDENCE / section / name).read_bytes()).hexdigest() == expected, name
        manifest = json.loads(read(section, 'manifest.json'))
        for item in manifest['files']:
            raw = (EVIDENCE / section / item['file']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == item['published_sha256'], item['file']
            assert len(raw.splitlines()) == item['published_lines'], item['file']

    result = {}
    adt = json.loads(read('04-gpu', 'adt-performance.json'))
    rows = adt['rows']
    assert len(rows) == adt['perf_state_count'] and adt['perf_state_table_count'] == 1
    groups = []
    for i, row in enumerate(rows):
        assert row['index'] == i and row['frequency_hz'] % 1000000 == 0
        if not groups or groups[-1][0]['core_voltage'] != row['core_voltage']:
            groups.append([])
        groups[-1].append(row)
    assert all(len({r['sram_voltage'] for r in group}) == 1 for group in groups)
    assert all(a[0]['core_voltage'] < b[0]['core_voltage'] for a,b in zip(groups,groups[1:]))
    result['adt'] = {'rows': len(rows), 'voltage_groups': len(groups),
                     'groups': [{'indices': [r['index'] for r in g],
                                 'min_MHz': min(r['frequency_hz'] for r in g)//1000000,
                                 'max_MHz': max(r['frequency_hz'] for r in g)//1000000}
                                for g in groups]}
    mac_start = int(read('04-gpu', 'macos-load-start.txt'))
    assert 'load for 900.0 s' in read('04-gpu', 'macos-load.txt')
    mac_load = [r for r in table('04-gpu', 'macos-smc.txt') if mac_start <= r['t'] < mac_start + 900]
    first_45 = next(r for r in mac_load if r['TVS1'] >= 45.0)
    mac_held = [r for r in mac_load if r['t'] >= first_45['t']]
    result['macos'] = {
        'load_seconds': 900, 'samples': len(mac_load),
        'TVS1_first_at_45C_after_load_start_s': first_45['t'] - mac_start,
        'held_samples': len(mac_held),
        'held_TVS1_C': {'min': min(r['TVS1'] for r in mac_held),
                        'median': statistics.median(r['TVS1'] for r in mac_held),
                        'max': max(r['TVS1'] for r in mac_held)},
        'held_max_TCMz_C': max(r['TCMz'] for r in mac_held),
        'scope': 'macOS SMC reader in degrees C; held = from the first TVS1 reading at or above 45.0 to the end of the 900 s load'}

    assert '10 steps, max-frequency=1470 MHz, max-power=23533 mW' in read('04-gpu', 'probe.txt')
    assert 'Cannot allocate memory' in read('04-gpu', 'baseline-repro.log')
    assert '1000 texture uploads; all 74529 pixels/frame match; GL error 0x0' in read('04-gpu', 'patched-repro.log')
    cold = json.loads(read('04-gpu', 'cold-session-result.json'))
    assert cold['pass'] and cold['seconds'] == 180 and not cold['gpu_errors']
    assert cold['renderer'] == 'Apple M4 (G16G B1)'
    timestamps = [int(l.split()[2]) for l in read('04-gpu', 'presentation-probe.txt').splitlines() if l.startswith('PRESENT ')]
    assert len(timestamps) > 1 and all(a < b for a,b in zip(timestamps,timestamps[1:]))
    result['presentation'] = {'events': len(timestamps),
                              'events_per_second': (len(timestamps)-1) * 1e9 / (timestamps[-1]-timestamps[0]),
                              'scope': 'Wayland presentation feedback on simpledrm, not physical panel refresh'}

    start = int(read('04-gpu', 'lim2-load-start.txt'))
    done = re.search(r'done: (\d+) draws in ([\d.]+) s, GL error (0x[0-9a-f]+)', read('04-gpu', 'lim2-load.txt'))
    assert done and int(done[3], 16) == 0
    draws, seconds = int(done[1]), float(done[2])
    samples = [r for r in table('04-gpu', 'lim2-sensors.txt') if start <= r['t'] < start+seconds]
    assert all(r['cooling_state'] == int(r['cooling_state']) and 0 <= r['cooling_state'] <= 6 for r in samples)
    assert len(samples) > 1100 and samples[-1]['t'] - start == 1199
    first = next(i for i, r in enumerate(samples) if r['cooling_state'] > 0)
    regulated = samples[first:]
    assert min(r['cooling_state'] for r in samples) == 0
    assert max(r['cooling_state'] for r in samples) == 6
    assert '65972 draws in 1200.0 s, GL error 0x0' in read('04-gpu', 'lim2-load.txt')
    result['lim2'] = {
        'load_seconds': seconds, 'sample_count': len(samples), 'first_cooling_state_seconds': regulated[0]['t']-start,
        'regulated_window_seconds': [regulated[0]['t']-start, regulated[-1]['t']-start],
        'regulated_samples': len(regulated),
        'TVS1_C': {'min': min(r['SMC_TVS1'] for r in regulated)/1000,
                   'median': statistics.median(r['SMC_TVS1'] for r in regulated)/1000,
                   'max': max(r['SMC_TVS1'] for r in regulated)/1000},
        'regulated_mean_PP1b_W': statistics.mean(r['SMC_PP1b'] for r in regulated)/1e6,
        'regulated_cooling_fraction': sum(r['cooling_state'] > 0 for r in regulated)/len(regulated),
        'whole_run_mean_PP1b_W': statistics.mean(r['SMC_PP1b'] for r in samples)/1e6,
        'whole_run_max_TCMz_C': max(r['SoC_TCMz'] for r in samples)/1000,
        'draws': draws,
        'scope': 'sample statistics, unweighted; missing seconds are not interpolated; PP1b is an SMC reading'
    }
    result['lim2'].update(regulation('lim2', samples, start))


    assert '10 s idle, then N s' in read('04-gpu', 'macos-1h-run.sh')
    assert 'load for 3605.0 s' in read('04-gpu', 'macos-1h-load.txt')
    hour = table('04-gpu', 'macos-1h-smc.txt')
    hour_start = hour[0]['t'] + 10  # the SMC reader starts before the 10 s idle period
    held = [r for r in hour if hour_start + 900 <= r['t'] < hour_start + 3600]
    result['macos_1h'] = {
        'window_s': [900, 3600], 'samples': len(held),
        'TVS1_C': {'min': min(r['TVS1'] for r in held), 'mean': statistics.mean(r['TVS1'] for r in held),
                   'max': max(r['TVS1'] for r in held), 'pstdev': statistics.pstdev(r['TVS1'] for r in held)},
        'TCMz_C': {'min': min(r['TCMz'] for r in held), 'max': max(r['TCMz'] for r in held)},
        'scope': 'minutes 15-60 of the load; load start taken as the first SMC sample + 10 s'}

    soc = ['SoC_TCMz', 'SoC_Tp3P', 'SoC_Tp0Z', 'SoC_Tp0f']
    tg = table('04-gpu', 'tg1-sensors.txt')
    tg_done = re.search(r'done: (\d+) draws in ([\d.]+) s, GL error (0x[0-9a-f]+)', read('04-gpu', 'tg1-load.txt'))
    assert tg_done and int(tg_done[3], 16) == 0
    tg_load = [r for r in tg if r['SMC_PP1b'] > 1e6]
    tg_rates = [x for _, x in draw_rates('tg1-load.txt', 0)]
    tg_hot = max(tg_load, key=lambda r: r['SoC_TCMz'])
    result['tg1'] = {
        'load_seconds': float(tg_done[2]), 'draws': int(tg_done[1]),
        'draws_per_second': {'min': min(tg_rates), 'max': max(tg_rates), 'readings': len(tg_rates)},
        'load_samples': len(tg_load),
        'median_PP1b_W': statistics.median(r['SMC_PP1b'] for r in tg_load)/1e6,
        'median_system_W': statistics.median(r['Total_System_Power'] for r in tg_load)/1e6,
        'TCMz_C': {'first': tg_load[0]['SoC_TCMz']/1000, 'max': tg_hot['SoC_TCMz']/1000,
                   'max_at_s': tg_hot['t'] - tg_load[0]['t'], 'last': tg_load[-1]['SoC_TCMz']/1000},
        'hottest_SoC_max_C': max(r[k] for r in tg_load for k in soc)/1000,
        'GPU_Tg_columns': sum(k.startswith('GPU_Tg') for k in tg[0]),
        'GPU_Tg_raw_value_counts': {str(int(v)): n for v, n in sorted(collections.Counter(
            r[k] for r in tg for k in r if k.startswith('GPU_Tg')).items())},
        'scope': 'no thermal limit; load samples are those with PP1b above 1 W'}

    a1 = table('04-gpu', 'ag1-sensors.txt')
    a1_start = int(read('04-gpu', 'ag1-load-start.txt'))
    writes = re.findall(r'G16: AG1 power budget (\d+) mW', read('04-gpu', 'ag1-dmesg-ag1.txt'))
    assert writes == ['7000', '26250', '3500', '26250']
    tvs1 = [r['SMC_TVS1'] for r in a1]
    result['ag1'] = {
        'TVS1_C': {'min': min(tvs1)/1000, 'max': max(tvs1)/1000, 'distinct_values': len(set(tvs1))},
        'TVS1_first_45C_s': next(r['t'] for r in a1 if r['t'] >= a1_start and r['SMC_TVS1'] >= 45000) - a1_start,
        'budget_writes_mW': [int(w) for w in writes],
        'phases': phase_medians(a1, 'ag1-phases.txt', draw_rates('ag1-load.txt', a1_start), 120, 60),
        'scope': 'medians over the last 60 s of each 120 s phase'}

    a2 = table('04-gpu', 'ag2-sensors.txt')
    a2_phases = phase_starts('ag2-phases.txt')
    result['ag2'] = {
        'phases': phase_medians(a2, 'ag2-phases.txt', draw_rates('ag2-load.txt', int(read('04-gpu', 'ag2-load-start.txt'))), 90, 45),
        'PP1b_W_after_switch': {f'phase {i + 1}, {label}': [r['SMC_PP1b']/1e6 for r in a2 if t <= r['t'] <= t + 3]
                                for i, (t, label) in enumerate(a2_phases) if label.startswith('cltm_limit')},
        'scope': 'medians over the last 45 s of each 90 s phase; PP1b_W_after_switch lists seconds 0-3'}

    runs = [l.split() for l in read('04-gpu', 'stk-bench.txt').splitlines()[1:] if len(l.split()) == 8]
    stops = re.findall(r'SAFETY STOP at [\d:]+: (\S+) (\d+) m°C', read('04-gpu', 'stk-bench.txt'))
    stk = table('04-gpu', 'stk-sensors.txt', allow_na=('CPU_busy_pct',))
    stk_start = int(read('04-gpu', 'stk-start.txt'))
    stk_load = [r for r in stk if r['SMC_PP1b'] > 1e6]
    result['stk'] = {
        'runs': len(runs), 'typical_fps': {'min': min(int(r[7]) for r in runs), 'max': max(int(r[7]) for r in runs)},
        'loop_seconds_at_stop': int(runs[-1][2]),
        'first_stop': {'sensor': stops[0][0], 'C': int(stops[0][1])/1000},
        'max_TCMz_C': max(r['SoC_TCMz'] for r in stk)/1000,
        'first_TCMz_100C_after_start_s': next(r['t'] for r in stk if r['SoC_TCMz'] >= 100000) - stk_start,
        'median_PP1b_W': statistics.median(r['SMC_PP1b'] for r in stk_load)/1e6,
        'median_system_W': statistics.median(r['Total_System_Power'] for r in stk_load)/1e6,
        'scope': 'no thermal limit; benchmark loop timings from stk-bench.txt'}

    l1_start = int(read('04-gpu', 'lim1-load-start.txt'))
    l1_done = re.search(r'done: (\d+) draws in ([\d.]+) s, GL error (0x[0-9a-f]+)', read('04-gpu', 'lim1-load.txt'))
    assert l1_done and int(l1_done[3], 16) == 0
    l1 = [r for r in table('04-gpu', 'lim1-sensors.txt') if l1_start <= r['t'] < l1_start + float(l1_done[2])]
    result['lim1'] = regulation('lim1', l1, l1_start)

    display = {}
    for d in range(4, 9):
        text = read('05-display', f'd{d}-kernel.txt')
        assert 'DCP booted' in text and 'appledrmfb frame buffer device' in text and 'Run /init as init process' in text
        brightness = [int(v) for v in re.findall(r'brightness_changed: brightness value: (\d+)', text)]
        fifo = text.count('FIFO error')
        assert fifo == (1 if d < 7 else 0), f'D{d}'
        assert brightness == ([0] if d == 4 else [9830400]), f'D{d}'
        mode = re.search(r'select_mode\(color:\d+ timing:\d+\) \"(\d+)x(\d+)\": (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)', text)
        assert mode, f'D{d}: missing selected mode'
        display[f'D{d}'] = {'FIFO_error_lines': fifo, 'firmware_brightness_values': brightness,
                            'mode': f'{mode[1]}x{mode[2]} at {mode[3]} Hz', 'initramfs_reached': True}
    parts = json.loads(read('05-display', 'image-parts.json'))
    for key in ['stage2_sha256', 'kernel_initramfs_sha256', 'arguments_without_image_label_sha256']:
        assert parts['D5'][key] == parts['D7'][key] == parts['D8'][key], key
    normalize = lambda s: re.sub(r'x6e3.v=\S+', 'x6e3.v=[image]', s)
    assert normalize(parts['D5']['arguments_redacted']) == normalize(parts['D7']['arguments_redacted']) == normalize(parts['D8']['arguments_redacted'])
    assert len({parts[d]['dtb_sha256'] for d in ('D5','D7','D8')}) == 3
    result['display'] = display

    sink, = json.loads(read('06-audio', 'pactl-sinks.json'))
    assert sink['sample_specification'] == 's24-32le 2ch 48000Hz'
    assert sink['channel_map'] == 'front-left,front-right'
    assert read('06-audio', 'ceiling-dvc.txt').split()[-1] == '60'
    ceiling = int(read('06-audio', 'ceiling-dvc.txt').split()[-1])
    result['audio'] = {'ceiling_dvc': ceiling, 'ceiling_dB': -ceiling/2,
                       'PipeWire_format': sink['sample_specification'], 'state': sink['state'],
                       'scope': '23 October passive snapshot; this is not a playback or speaker-calibration test'}

    idle = {}
    for run in ['aba-wfi4-1003', 'aba-wfi5-1032']:
        phases = {p: [] for p in ['A1', 'B', 'A2']}
        sequence, times = [], []
        for line in read('07-idle', run + '/power.txt').splitlines():
            phase, timestamp, power, battery, status, ac, load = line.split()
            assert ac == '0' and status == 'Discharging'
            phases[phase].append(int(power)/1e6)
            sequence.append(phase)
            times.append(int(timestamp))
        assert all(len(v) == 90 for v in phases.values())
        assert sequence == ['A1']*90 + ['B']*90 + ['A2']*90
        assert all(a < b for a,b in zip(times,times[1:]))
        assert 'RESTORE OK' in read('07-idle', run + '/run.log')
        means = {p: statistics.mean(v) for p, v in phases.items()}
        combined = statistics.mean(phases['A1'] + phases['A2'])
        idle[run] = {'samples_per_phase': 90, 'mean_system_W': means, 'combined_A_W': combined,
                     'reduction_vs_B_percent': 100*(1-combined/means['B']), 'restored': True}
    result['idle'] = idle
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'data/04-07-summary.json'
    content = json.dumps(calculate(), indent=2) + '\n'
    if args.check:
        assert output.read_text() == content, 'Summary differs; regenerate with make later-stages'
        print('Sections 4–7: evidence hashes and derived results match')
    else:
        output.write_text(content)
        print(output.relative_to(ROOT))


if __name__ == '__main__':
    main()
