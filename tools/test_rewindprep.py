#!/usr/bin/env python3
"""Compile/grade real QC warm rewind selection/preparation, not prediction."""
import argparse
import os
import pathlib
import re
import subprocess

from test_moveprep import ROOT, check_source_contract

CHECKS = 91  # Exact complete acting suite; updated only with fixture changes.
FAULTS = ('SV_Error:', 'Host_Error:', 'runaway loop', 'Program error',
          'Unknown command', 'QC VM error', 'Cannot call', 'stack overflow')


def build(out, weak):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    src = ROOT / 'src'
    lines = (src / 'sv_progs.src').read_text().splitlines()
    lines[0] = (out / 'qwprogs.dat').as_posix()
    lines.insert(lines.index('server/sv_player.qc'), '../tools/fixtures/moveprep_begin.qc')
    lines.append('../tools/fixtures/rewindprep.qc')
    if weak:
        if weak == 'selection':
            name = 'sv_saveloc.qc'
            old = 'd = vlen([m[i + 1], m[i + 2], m[i + 3]] - near);'
            new = 'd = fabs(m[i] - t); // test-only weakened spatial selection'
        else:
            name = 'sv_moveprep.qc'
            old = "out->velocity = '0 0 0'; out->velocity_policy = MP_SET; out->release_velocity = vel;"
            new = "out->velocity = vel; out->velocity_policy = MP_SET; out->release_velocity = vel;"
        module = (src / 'server' / name).read_text()
        if module.count(old) != 1:
            raise ValueError('Weak source anchor drift: ' + name)
        target = out / ('weak-' + name)
        target.write_text(module.replace(old, new))
        lines[lines.index('server/' + name)] = pathlib.Path(os.path.relpath(target, src)).as_posix()
        # sv_saveloc includes its sibling state writer; out is deliberately isolated.
        if name == 'sv_saveloc.qc':
            (out / 'sv_rewindstate.qc').write_text((src / 'server/sv_rewindstate.qc').read_text())
    listing = src / 'p682rewindprep.src'
    listing.write_text('\n'.join(lines) + '\n')
    try:
        result = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', listing.name],
                                cwd=src, text=True, capture_output=True)
        text = f'fteqcc exit={result.returncode}\n' + result.stdout + result.stderr
        (out / 'compile.log').write_text(text)
        if result.returncode or 'Done. 0 warnings' not in text or re.search(r': (?:warning|error)', text, re.I):
            raise RuntimeError('Fixture compile failed or warned; inspect retained log')
    finally:
        listing.unlink()
    print('PASS rewind fixture compiled:', lines[0])


def grade(server, client, weak):
    for fault in FAULTS:
        if fault in server or fault in client:
            raise ValueError('Runtime fault cannot grade preparation: ' + fault)
    for marker in ('FTESurf CSQC loaded', 'REWINDPREP CLIENT COMPLETE', 'RUNLINES COMPLETE'):
        if marker not in client:
            raise ValueError('Client control did not act: ' + marker)
    if 'REWINDPREP SETUP FAILED' in server:
        raise ValueError('Prerequisite actor did not act')
    rows = re.findall(r'REWINDPREP COMPLETE checks=(\d+) failed=(\d+)', server)
    if len(rows) != 1:
        raise ValueError('Exactly one completed rewind control required')
    checks, failed = map(int, rows[0])
    if checks != CHECKS:
        raise ValueError(f'Complete rewind controls did not act: {checks}/{CHECKS}')
    if failed != len(re.findall(r'REWINDPREP FAIL ', server)):
        raise ValueError('Failure marker/count mismatch')
    if weak:
        required = ('spatial window winner beats nearer tick' if weak == 'selection'
                    else 'actual go held release velocity parity')
        if not failed or ('REWINDPREP FAIL ' + required) not in server:
            raise ValueError('Required one-factor detector did not fire')
        print(f'PASS negative {weak} control detected: {failed}/{checks} expected assertion failures')
    elif failed or 'REWINDPREP FAIL' in server:
        raise ValueError(f'Rewind preparation failed: {failed}/{checks}')
    else:
        print(f'PASS real QC rewind selection/body and legacy go parity: {checks} checks, 0 failed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=pathlib.Path)
    p.add_argument('--engine', type=pathlib.Path)
    p.add_argument('--log', type=pathlib.Path)
    p.add_argument('--client-log', type=pathlib.Path)
    p.add_argument('--weak', choices=('selection', 'held'))
    a = p.parse_args()
    if a.engine:
        check_source_contract(a.engine)
    if a.out:
        build(a.out, a.weak)
    if a.log:
        if not a.client_log:
            p.error('--log requires --client-log')
        grade(a.log.read_text(errors='replace'), a.client_log.read_text(errors='replace'), a.weak)
    if not (a.out or a.engine or a.log):
        p.error('Use --out, --engine and/or --log')


if __name__ == '__main__':
    main()
