#!/usr/bin/env python3
"""Grade native r_shaderpasses depth probes (not a source-pattern test).

Place the probe fixture in an owned rig with --prepare, restart its client,
then r_remapshader a loaded material to each probe to force registration and
run `r_shaderpasses probe/`. Grade a fresh client log. This does not grade pixels.
"""
import argparse
from pathlib import Path
import re

PROBES = {
    'implicit_alpha': False,
    'explicit_alpha': True,
    'explicit_add': True,
    'opaque': True,
    'replace': True,
}
FIXTURE = '''probe/implicit_alpha
{
    program defaultwall
    diffusemap $whiteimage
    progblendfunc blend
}
probe/explicit_alpha
{
    {
        program defaultwall
        map $whiteimage
        depthwrite
    }
    progblendfunc blend
}
probe/explicit_add
{
    {
        program defaultwall
        map $whiteimage
        depthwrite
    }
    progblendfunc add
}
probe/opaque
{
    program defaultwall
    diffusemap $whiteimage
}
probe/replace
{
    {
        program defaultwall
        map $whiteimage
    }
    progblendfunc replace
}
'''
HEADER = re.compile(r'\bprobe/(\w+)\s+flags=.*\bpasses=(\d+)')
PASS = re.compile(r'\bpass 0:.*shaderbits=0x([0-9a-f]+)', re.I)


def grade(text):
    seen = {}
    current = None
    for line in text.splitlines():
        header = HEADER.search(line)
        if header:
            current = header[1]
            if int(header[2]) < 1:
                raise AssertionError(f'{current}: no leader pass')
        elif current:
            p = PASS.search(line)
            if p:
                seen[current] = int(p[1], 16)
                current = None
    for name, depth in PROBES.items():
        if name not in seen:
            raise AssertionError(f'{name}: missing acted probe')
        if bool(seen[name] & 0x10000) != depth:
            raise AssertionError(f'{name}: depthwrite mismatch 0x{seen[name]:x}')
    print('PASS: implicit alpha no-write; explicit alpha/additive masks and opaque/replace write')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path, nargs='?')
    parser.add_argument('--prepare', type=Path, help='existing owned rig root')
    args = parser.parse_args()
    if args.prepare:
        gamedir = args.prepare / 'ftesurf'
        if not gamedir.is_dir():
            parser.error('prepare requires an existing owned rig/ftesurf')
        path = gamedir / 'scripts/material-depth-probe.shader'
        if path.exists():
            parser.error('probe fixture already exists; not overwriting it')
        path.parent.mkdir(exist_ok=True)
        path.write_text(FIXTURE, encoding='utf-8')
        print(path)
    if args.log:
        grade(args.log.read_text(encoding='utf-8', errors='replace'))
    if not args.log and not args.prepare:
        parser.error('provide a log or --prepare')


if __name__ == '__main__':
    main()
