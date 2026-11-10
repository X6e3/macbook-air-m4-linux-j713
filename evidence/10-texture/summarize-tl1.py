#!/usr/bin/env python3
"""Parse Mesa AGX resource New/Destroy records with TL1 stage markers.

Resource identities are matched by pointer + GPU Base + handle within one process.
This is Gallium object-lifetime accounting, NOT a claim about physical BO reclaim.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit('usage: summarize-tl1.py <result_directory>')
root = Path(sys.argv[1])

stage_re = re.compile(r'^TL1 ns=(\d+) stage=(\S+)')
event_re = re.compile(r'^\[[^\]]+\]\s+(New|Destroy):\s+(.*)$')
size_re = re.compile(r'\bSize=(0x[0-9a-fA-F]+)\b')
base_re = re.compile(r'\bBase=(0x[0-9a-fA-F]+)\b')
handle_re = re.compile(r'\bH:([0-9a-fA-F]+/[0-9a-fA-F]+)\b')
ptr_re = re.compile(r'@ (0x[0-9a-fA-F]+)\s*$')
format_re = re.compile(r'r8g8b8a8_unorm\s+1024x1024x1\b')

print('# TL1 — AGX resource lifetime, 1024² RGBA8')
print()
print('Instrument: `ASAHI_MESA_DEBUG=resource` with phase markers. Each scenario runs in a fresh process/context.')
print('Note: New/Destroy refer to logged resource objects; these are not direct measurements of physical GPU memory reclamation.')
print()
print('| Scenario | Renderer | 4 MiB New→Destroy | 5.34 MiB New→Destroy | Old live at delete | Old live after finish | Status |')
print('|---|---|---|---|---:|---:|---|')

def kind_name(size):
    if size == 0x400000:
        return 'old'
    if size == 0x558000:
        return 'mips'
    return None

for name in 'ABCDEOV':
    log = root / f'{name}.log'
    out = root / f'{name}.out'
    stfile = root / f'{name}.status'
    if not log.exists():
        continue
    stage = 'before_markers'
    live: dict[str, dict] = {}
    events: dict[str, list[dict]] = {'old': [], 'mips': []}
    snapshot: dict[str, int] = {}
    dup_new = []
    orphan_destroys = []
    for line_no, line in enumerate(log.read_text(errors='replace').splitlines(), start=1):
        m = stage_re.search(line)
        if m:
            stage = m.group(2)
            if stage in ('delete_begin','post_delete_finish_end','context_destroy_end'):
                snapshot[stage] = sum(x['kind'] == 'old' for x in live.values())
            continue
        m = event_re.search(line)
        if not m:
            continue
        action, desc = m.groups()
        if not format_re.search(desc):
            continue
        sz = size_re.search(desc)
        ptr = ptr_re.search(desc)
        base = base_re.search(desc)
        handle = handle_re.search(desc)
        if not (sz and ptr and base and handle):
            continue
        kind = kind_name(int(sz.group(1), 16))
        if not kind:
            continue
        key = f'{ptr.group(1)}|{base.group(1)}|{handle.group(1)}'
        item = {'kind': kind, 'key': key, 'line': line_no, 'stage': stage, 'action': action}
        events[kind].append(item)
        if action == 'New':
            if key in live:
                dup_new.append(key)
            live[key] = item
        else:
            if key not in live:
                orphan_destroys.append(key)
            live.pop(key, None)

    def show_pair(kind):
        starts = [e['stage'] for e in events[kind] if e['action'] == 'New']
        ends = [e['stage'] for e in events[kind] if e['action'] == 'Destroy']
        if not starts and not ends:
            return 'none'
        def digest(vals):
            from collections import Counter
            return ', '.join(f'{s}×{n}' for s, n in Counter(vals).items()) or 'none'
        return f'{len(starts)} ({digest(starts)}) → {len(ends)} ({digest(ends)})'

    stdout = out.read_text(errors='replace') if out.exists() else ''
    r = re.search(r'^renderer=(.*)$', stdout, re.M)
    renderer = (r.group(1) if r else '?').replace('|','/')
    if len(renderer) > 31: renderer = renderer[:29] + '…'
    sr = stfile.read_text(errors='replace').strip() if stfile.exists() else 'status=?'
    before = snapshot.get('delete_begin', '?')
    after = snapshot.get('post_delete_finish_end', '?')
    print(f'| {name} | {renderer} | {show_pair("old")} | {show_pair("mips")} | {before} | {after} | {sr} |')
    if dup_new or orphan_destroys:
        print(f'\n**Warning for {name}:** duplicate-New={len(dup_new)}, orphan-Destroy={len(orphan_destroys)}; check raw log.\n')
    if name == 'V':
        px = re.search(r'^pixel_rgba=(.*)$', stdout, re.M)
        print(f'\nVerification pixel: `{px.group(1) if px else "missing"}`.\n')

print('\n**Decision rule:** Compare A and B (finish without draw), C and D (finish after draw), D and E (unbind), then O (original order) and V (sampling/readback validation). Do not infer a leak simply because a resource survives to context cleanup. Check raw logs and phases before interpreting causality.')
