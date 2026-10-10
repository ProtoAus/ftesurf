#!/usr/bin/env python3
"""Patch 614: the engine's NativeUIPlot/1 bridge and grammar, without a game.

  python tools/test_p614plot_unit.py --fte <engine tree> --out <owned dir>

Two fixtures against the tree's own sources. p614plot_host.c is the real host bridge
(engine/client/cl_plugin_ui_plot.inc, as tools/test_p590bridge_unit.py builds the others) over a
small VM: every builtin through good and hostile transactions, memory that will not come, the
whole row allowance, a provider that refuses. p614plot_valid.cpp is the shared grammar
(plugins/ui_model.h) against a table of malformed revisions and views; it prints one line a
case, and this fails on any FAIL line, on a compiler diagnostic, or when the count of cases is
not the one written here (a case that was never reached cannot pass). --header grades a mutated
copy of the grammar, which must fail.
"""
import argparse
from pathlib import Path
import os
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p590bridge_unit import host_controls  # noqa: E402
from p598build import build as build_host  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CASES = 63          # lines the fixture must print: 53 refusals and the 10 controls that are accepted


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--header', type=Path, help='grade this copy of ui_model.h instead (a mutant must FAIL)')
    a = p.parse_args()
    out = a.out.resolve()
    if not any((d / 'OWNER.md').is_file() for d in [out, *out.parents]):
        raise SystemExit('--out requires an ancestor OWNER.md before population')
    out.mkdir(parents=True, exist_ok=True)
    if not a.header and host_controls(a.fte, a.cc.with_name('gcc.exe'), ROOT / 'tools/fixtures/p614plot_host.c'):
        raise SystemExit('FAIL the host bridge fixture (p614plot_host.c)')
    env = os.environ.copy()
    env['PATH'] = str(a.cc.parent) + os.pathsep + env['PATH']
    flags = ['-std=c++17', '-DFTEPLUGIN', '-DIMGUI_USE_WCHAR32', '-Wall', '-Wextra', '-Werror']
    flags += ['-I' + str(a.fte / d) for d in ('plugins', 'engine/client', 'engine/common', 'engine/server', 'engine/gl',
                                               'plugins/ui_imgui')]
    if a.header:
        flags += ['-DP614_GRAMMAR="' + a.header.resolve().as_posix() + '"']
    exe = out / 'p614plot_valid.exe'
    build = subprocess.run([str(a.cc), *flags, '-O1', str(ROOT / 'tools/fixtures/p614plot_valid.cpp'), '-o', str(exe)],
                           env=env, capture_output=True, text=True)
    if build.returncode or build.stdout.strip() or build.stderr.strip():
        print(build.stdout + build.stderr)
        raise SystemExit('FAIL the fixture did not compile clean against ' + str(a.fte))
    run = subprocess.run([str(exe)], capture_output=True, text=True)
    lines = [ln for ln in run.stdout.splitlines() if re.match(r'(PASS|FAIL) ', ln)]
    bad = [ln for ln in lines if ln.startswith('FAIL')]
    for ln in bad:
        print(ln)
    print(f'P614 PLOT GRAMMAR checks={len(lines)} failed={len(bad)} exit={run.returncode}')
    if len(lines) != CASES:
        raise SystemExit(f'FAIL {len(lines)} cases printed, {CASES} are written in the fixture')
    if bad or run.returncode or a.header:
        raise SystemExit(bool(bad) or run.returncode != 0)
    # The provider itself: ui_imgui.cpp with plots.inc, pinned ImGui and ImPlot, owner 206, at
    # both index widths. What it draws is counted and measured against the rows it was handed.
    for bits in (16, 32):
        exe = build_host(a.fte.resolve(), out / f'plots{bits}', a.cc.resolve(), host=True, index32=bits == 32,
                    host_source=ROOT / 'tools/fixtures/p614plots_host.cpp')
        run = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
        text = run.stdout + run.stderr
        (out / f'plots{bits}/host.log').write_text(text, encoding='utf-8')
        for ln in text.splitlines():
            if ln.startswith(('FAIL', 'P614 PLOTS')):
                print(ln)
        done = re.search(r'P614 PLOTS indexbits=%d checks=(\d+) failed=(\d+)' % bits, text)
        if run.returncode or not done or done.group(2) != '0':
            raise SystemExit(f'FAIL the provider fixture, {bits}-bit indices: {out / f"plots{bits}/host.log"}')
    raise SystemExit(0)


if __name__ == '__main__':
    main()
