#!/usr/bin/env python3
"""Compile/grade actual QC reset policy preparation; no prediction acceptance."""
import argparse
import os
import pathlib
import re
import subprocess

from test_moveprep import ROOT, check_source_contract, grade as grade_load


def build(out, weak):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    src = ROOT / 'src'
    lines = (src / 'sv_progs.src').read_text().splitlines()
    lines[0] = (out / 'qwprogs.dat').as_posix()
    lines.insert(lines.index('server/sv_player.qc'), '../tools/fixtures/moveprep_begin.qc')
    lines.extend(['../tools/fixtures/zoneprep.qc', '../tools/fixtures/moveprep.qc'])
    if weak:
        module = (src / 'server/sv_moveprep.qc').read_text()
        old = "out->velocity = '0 0 0'; out->velocity_policy = MP_SET;"
        if module.count(old) != 1:
            raise ValueError('Weak reset source anchor drift')
        target = out / 'weak-moveprep.qc'
        target.write_text(module.replace(old, 'out->velocity = e.velocity; out->velocity_policy = MP_SET;'))
        lines[lines.index('server/sv_moveprep.qc')] = pathlib.Path(os.path.relpath(target, src)).as_posix()
    listing = src / 'p680zoneprep.src'
    listing.write_text('\n'.join(lines) + '\n')
    try:
        result = subprocess.run([str(src / 'fteqcc64.exe'), '-DZONEPREP_FIXTURE', '-srcfile', listing.name],
                                cwd=src, text=True, capture_output=True)
        text = f'fteqcc exit={result.returncode}\n' + result.stdout + result.stderr
        (out / 'compile.log').write_text(text)
        if result.returncode or 'Done. 0 warnings' not in text or re.search(r': (?:warning|error)', text, re.I):
            raise RuntimeError('Fixture compile failed or warned; inspect retained compile log')
    finally:
        listing.unlink()
    print('PASS zone fixture compiled:', lines[0])


def grade(server, client, weak):
    for fault in ('SV_Error:', 'Host_Error:', 'runaway loop', 'Program error'):
        if fault in server or fault in client:
            raise ValueError('Runtime fault cannot grade preparation: ' + fault)
    grade_load(server, client, False)  # existing load/release must still act and pass
    if 'ZONEPREP CLIENT COMPLETE' not in client:
        raise ValueError('Zone client control did not act')
    rows = re.findall(r'ZONEPREP COMPLETE checks=(\d+) failed=(\d+)', server)
    if len(rows) != 1:
        raise ValueError('Exactly one completed zone control required')
    checks, failed = map(int, rows[0])
    if checks != 71:
        raise ValueError(f'Complete zone controls did not act: {checks}/71')
    if failed != len(re.findall(r'ZONEPREP FAIL ', server)):
        raise ValueError('Zone failure marker/count mismatch')
    if weak:
        if not failed or 'ZONEPREP FAIL reset zero velocity' not in server:
            raise ValueError('Weak reset detector did not fire')
        print(f'PASS negative reset control detected: {failed}/{checks} assertions failed as expected')
    elif failed or 'ZONEPREP FAIL' in server:
        raise ValueError(f'Zone preparation failed: {failed}/{checks}')
    else:
        print(f'PASS real QC zone/reset policy and old-operation parity: {checks} checks, 0 failed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=pathlib.Path)
    p.add_argument('--engine', type=pathlib.Path)
    p.add_argument('--log', type=pathlib.Path)
    p.add_argument('--client-log', type=pathlib.Path)
    p.add_argument('--weak', action='store_true')
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
