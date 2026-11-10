"""Write the published excerpt of the REL2 boot journal saved after the crash.

The full journal also holds other programs' messages, so it stays private. This keeps the kernel identity, the
Xonotic launches and crashes, KWin's messages from 04:00 to 04:29, the kernel's reports in the seconds around each
failure (without other programs' rows and out-of-memory lines) and the journalctl commands I ran to save the logs.

    python3 -I excerpt.py FULL-BOOT.LOG > excerpt.txt
"""
import re
import sys

WINDOWS = [('04:02:56', '04:02:58'), ('04:09:39', '04:09:47'), ('04:12:50', '04:12:52')]
PROGRAMS = {'kernel', 'audit', 'sudo', 'systemd-coredump', 'plasmashell', 'kwin_wayland', 'kwin_wayland_wrapper'}
STAMP = re.compile(r'^Oct 28 (\d\d:\d\d:\d\d)\.\d+ \S+ (\S+?)(?:\[\d+\])?: ')


def keep(line, last):
    m = STAMP.match(line)
    if not m:
        return last and 'xonotic' in line.lower()
    t, ident = m.groups()
    if ident not in PROGRAMS:
        return False
    rest = line[m.end():]
    low = line.lower()
    if ident == 'kernel' and ('Linux version' in rest or rest.startswith('Memory:')):
        return True
    if ident == 'sudo' and 'COMMAND=/usr/sbin/journalctl' in rest:
        return True
    if 'xonotic' in low:
        return True
    if 'kwin' in low and '04:00:00' <= t <= '04:29:59':
        return True
    if ident == 'kernel' and any(a <= t <= b for a, b in WINDOWS):
        if re.match(r'\[\s*\d+\]', rest):
            return False
        if re.search(r'oom-kill:|Out of memory: Killed process', rest) and 'systemd-coredum' not in rest:
            return False
        return not rest.startswith('audit:')
    return False


def main(path):
    last = False
    for line in open(path, encoding='utf-8', errors='replace'):
        k = keep(line, last)
        if STAMP.match(line):
            last = k
        if k:
            sys.stdout.write(line)


if __name__ == '__main__':
    main(sys.argv[1])
