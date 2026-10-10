#!/usr/bin/env python3
"""Actual pinned ImGui scoreboard controls, both index widths, warnings fatal."""
import argparse
import os
from pathlib import Path
import subprocess

from p598build import ROOT, build


def run(fte: Path, cxx: Path, out: Path) -> int:
    for bits in (16, 32):
        exe = build(fte, out / f'host{bits}', cxx, host=True,
                    index32=bits == 32, host_source=ROOT / 'tools/fixtures/p603scores_host.cpp')
        env = os.environ.copy()
        env['PATH'] = str(cxx.parent) + os.pathsep + env['PATH']
        result = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
        log = out / f'host{bits}/host.log'
        text = result.stdout + result.stderr
        log.write_text(text, encoding='utf-8')
        for line in text.splitlines():
            if line.startswith(('FAIL', 'P595 HOST', 'P603 SCORES')):
                print(line)
        if result.returncode or 'P603 SCORES' not in text or 'failed=0' not in text:
            print('Failed host log:', log)
            return 1
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--cxx', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--out', type=Path, default=ROOT / 'rig/p603-scores-host')
    a = p.parse_args()
    raise SystemExit(run(a.fte.resolve(), a.cxx.resolve(), a.out.resolve()))
