#!/usr/bin/env python3
"""Compile/run the real explicit bridge and real ImGui input controls, both index widths."""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile
from p598build import build, ROOT
from test_p590bridge_unit import host_controls


def run(fte, cc, cxx, out):
    if host_controls(fte, cc, ROOT/'tools/fixtures/p600bridge_host.c'):
        return 1
    env = os.environ.copy()
    env['PATH'] = str(cxx.parent)+os.pathsep+env.get('PATH', '')
    for bits in (16, 32):
        exe = build(fte, out/f'host{bits}', cxx, host=True, index32=bits == 32,
                    host_source=ROOT/'tools/fixtures/p600input_host.cpp')
        log = out/f'host{bits}.log'
        with log.open('w') as stream:
            result = subprocess.run([str(exe)], env=env, stdout=stream, stderr=subprocess.STDOUT)
        text = log.read_text()
        for line in text.splitlines():
            if line.startswith(('FAIL', 'P595 HOST', 'P599 INPUT')):
                print(line)
        if result.returncode or 'failed=0' not in text:
            print('Failed host log:', log)
            return 1
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    p.add_argument('--cxx', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        raise SystemExit(run(a.fte.resolve(), a.cc.resolve(), a.cxx.resolve(), a.out.resolve()))
    with tempfile.TemporaryDirectory(prefix='p599-input-') as d:
        raise SystemExit(run(a.fte.resolve(), a.cc.resolve(), a.cxx.resolve(), Path(d)))
