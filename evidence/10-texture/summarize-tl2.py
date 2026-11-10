#!/usr/bin/env python3
"""Summarize TL2 source-level AGX/Gallium resource events.

Identity is pointer + Base + Handle within one process. These are logged resource
object lifetimes, not necessarily physical backing-memory release times.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit('usage: summarize-tl2.py RESULT_DIRECTORY')
root = Path(sys.argv[1])

stage_re = re.compile(r'^TL2 ns=(\d+) stage=(\S+)')
event_re = re.compile(r'^\[[^]]+\]\s+(New|Destroy):\s+(.*)$')
format_re = re.compile(r'\br8g8b8a8_unorm\s+1024x1024x1\b')
size_re = re.compile(r'\bSize=(0x[0-9a-fA-F]+)\b')
base_re = re.compile(r'\bBase=(0x[0-9a-fA-F]+)\b')
handle_re = re.compile(r'\bH:([0-9a-fA-F]+/[0-9a-fA-F]+)\b')
ptr_re = re.compile(r'@ (0x[0-9a-fA-F]+)\s*$')
expected_draws = {'A': 0, 'B': 1, 'C': 16, 'D': 32, 'E': 0}
expected_old = {'A': 32, 'B': 31, 'C': 16, 'D': 0, 'E': 0}

print('# TL2 — AGX selective sampling / resource lifetime')
print()
print('32 textures, each DXT5 1024×1024 with 11 mip levels; fresh process/EGL context per condition.')
print('**Checkpoint:** after the selected draws and `glFinish`, BEFORE `glReadPixels`, `glDeleteTextures`, or context destruction.')
print('Counts are Gallium resource objects reported by `ASAHI_MESA_DEBUG=resource`; physical BO reclamation is not measured.')
print()
print('| Case | Draws | Old 4 MiB: New | Old destroyed by checkpoint | **Old live** | Full 5.34 MiB live | Retained target MiB | Pixel | Result |')
print('|---|---:|---:|---:|---:|---:|---:|---|---|')

for name in 'ABCDE':
    f = root / f'{name}.log'
    stdout = (root / f'{name}.out').read_text(errors='replace') if (root / f'{name}.out').exists() else ''
    exit_line = (root / f'{name}.status').read_text(errors='replace').strip() if (root / f'{name}.status').exists() else 'status=missing'
    if not f.exists():
        print(f'| {name} | {expected_draws[name]} | — | — | — | — | — | — | MISSING LOG |')
        continue

    stage = 'initial'
    live: dict[str, dict] = {}
    new_old = 0
    old_destroyed_at_checkpoint = 0
    snapshot = None
    extras = []
    warnings = []
    for lineno, line in enumerate(f.read_text(errors='replace').splitlines(), 1):
        mark = stage_re.search(line)
        if mark:
            stage = mark.group(2)
            if stage == 'checkpoint_before_delete':
                if snapshot is not None:
                    warnings.append('duplicate checkpoint')
                snapshot = {
                    'old': sum(x['kind'] == 'old' for x in live.values()),
                    'full': sum(x['kind'] == 'full' for x in live.values()),
                    'old_destroyed': old_destroyed_at_checkpoint,
                }
            continue
        event = event_re.search(line)
        if not event or not format_re.search(event.group(2)):
            continue
        action, desc = event.groups()
        sz = size_re.search(desc)
        base = base_re.search(desc)
        handle = handle_re.search(desc)
        ptr = ptr_re.search(desc)
        if not (sz and base and handle and ptr):
            warnings.append(f'incomplete parsed event at line {lineno}')
            continue
        nbytes = int(sz.group(1), 16)
        if nbytes not in (0x400000, 0x558000):
            extras.append(nbytes)
            continue
        kind = 'old' if nbytes == 0x400000 else 'full'
        key = '|'.join((ptr.group(1), base.group(1), handle.group(1)))
        if action == 'New':
            if key in live:
                warnings.append(f'duplicate live New at line {lineno}')
            live[key] = {'kind': kind, 'size': nbytes}
            if kind == 'old':
                new_old += 1
        else:
            if key not in live:
                warnings.append(f'orphan Destroy at line {lineno}')
            else:
                if kind == 'old' and snapshot is None:
                    old_destroyed_at_checkpoint += 1
                live.pop(key)

    renderer = re.search(r'^renderer=(.*)$', stdout, re.M)
    renderer = renderer.group(1) if renderer else '(missing)'
    px = re.search(r'^pixel_rgba=(.*)$', stdout, re.M)
    px = px.group(1) if px else '(missing)'
    draws = re.search(r'^draw_count=(\d+)$', stdout, re.M)
    draws = int(draws.group(1)) if draws else -1
    done = 'done=1' in stdout
    old = snapshot['old'] if snapshot else None
    full = snapshot['full'] if snapshot else None
    destroyed = snapshot['old_destroyed'] if snapshot else None
    mib = (old * 4 + full * (0x558000 / 2**20)) if snapshot else None
    desired_px = ('255,255,255,255' if expected_draws[name] else '0,0,0,255')
    good = (
        exit_line == 'status=0'
        and renderer.startswith('Apple M4')
        and draws == expected_draws[name]
        and done
        and old == expected_old[name]
        and full == 32
        and px == desired_px
        and not warnings and not extras
    )
    def field(v):
        return str(v) if v is not None else '?'
    print(f'| {name} | {field(draws)} | {new_old} | {field(destroyed)} | '
          f'**{field(old)}** | {field(full)} | {f"{mib:.2f}" if mib is not None else "?"} | '
          f'`{px}` | {"matches model" if good else "CHECK RAW LOG"} |')
    notes = []
    if not renderer.startswith('Apple M4'):
        notes.append(f'renderer={renderer!r}')
    if exit_line != 'status=0':
        notes.append(exit_line)
    if old != expected_old[name]:
        notes.append(f'old live={old}; hypothesis expects {expected_old[name]}')
    if full != 32:
        notes.append(f'full live={full}; model expects 32')
    if px != desired_px:
        notes.append(f'pixel mismatch: {px}; expected {desired_px}')
    if extras:
        notes.append(f'other 1024 RGBA8 allocation sizes: {sorted(set(extras))}')
    notes += warnings[:8]
    if notes:
        print(f'\n**{name} notes:** ' + '; '.join(notes) + '\n')

print()
print('**Interpretation rule:** A versus B from TL1 showed finish alone did not release the old resource; TL2 tests whether first sampling releases the old 4 MiB resource on a per-texture basis.')
print('A linear 32→31→16→0 result supports draw-associated validation; it does not prove a Mesa leak or reclaimable physical RAM.')
print('If E produces no old resource, setting MAX_LEVEL before the first mip upload avoids transient single-level allocations in this controlled path. Xonotic behavior still needs separate attribution.')
