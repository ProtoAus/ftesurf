#!/usr/bin/env python3
"""Resolve a loading-stall profile (engine branch p1259-probe writes <cwd>/p1259prof.txt) into functions.

usage: loadprof_resolve.py PROF EXE_UNSTRIPPED(.db) PLUGIN_DLL [--top N]
A stall is a run of samples whose gap keeps growing; each gets its step, length, and the functions
found most often on its stacks (inclusive, once per sample) and at the top (self).
"""
import bisect
import collections
import re
import subprocess
import sys

TOOLS = 'C:/msys64/ucrt64/bin/'


def symtab(path):
    base = None
    for line in subprocess.run([TOOLS + 'objdump.exe', '-p', path], capture_output=True, text=True).stdout.splitlines():
        if line.startswith('ImageBase'):
            base = int(line.split()[1], 16)
            break
    addrs, names = [], []
    out = subprocess.run([TOOLS + 'nm.exe', '--defined-only', path], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] in 'tTwW':
            rows.append((int(parts[0], 16), parts[2]))
    rows.sort()
    for a, n in rows:
        addrs.append(a)
        names.append(n)
    return base, addrs, names


def main():
    prof, exe, plug = sys.argv[1:4]
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 8
    tabs = {}
    for key, path in (('exe', exe), ('plug', plug)):
        tabs[key] = symtab(path)

    def name(frame):
        m = re.match(r'(.+)\+([0-9a-f]+)$', frame)
        if not m:
            return frame
        mod, off = m.group(1).lower(), int(m.group(2), 16)
        key = 'exe' if mod.endswith('.exe') else 'plug' if 'hl2' in mod else None
        if not key:
            return mod
        base, addrs, names = tabs[key]
        i = bisect.bisect_right(addrs, base + off) - 1
        return names[i] if i >= 0 else frame

    stalls = []
    cur = None
    for line in open(prof, encoding='utf-8', errors='replace'):
        if line.startswith('#'):
            print(line.rstrip())
            cur = None
            continue
        if not line.startswith('S '):
            continue
        head, _, frames = line.partition('|')
        t, gap, *step = head.split()[1:]
        t, gap = float(t), float(gap)
        fns = [name(f) for f in frames.split()]
        if cur is None or gap < cur['last']:
            cur = {'t': t - gap, 'steps': collections.Counter(), 'n': 0, 'inc': collections.Counter(),
                   'self': collections.Counter(), 'last': 0}
            stalls.append(cur)
        cur['last'] = gap
        cur['n'] += 1
        cur['steps'][' '.join(step)] += 1
        cur['self'][fns[0] if fns else '?'] += 1
        for f in set(fns):
            cur['inc'][f] += 1
    for s in sorted(stalls, key=lambda s: -s['last']):
        if s['last'] < 150:
            continue
        print(f"\n== stall from {s['t']:.0f} ms, at least {s['last']:.0f} ms, {s['n']} samples; steps: "
              + ', '.join(f'{k} ({v})' for k, v in s['steps'].most_common(3)))
        print('  inclusive: ' + '; '.join(f'{k} {100 * v // s["n"]}%' for k, v in s['inc'].most_common(top)))
        print('  self:      ' + '; '.join(f'{k} {100 * v // s["n"]}%' for k, v in s['self'].most_common(top)))


main()
