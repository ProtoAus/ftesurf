#!/usr/bin/env python3
"""Build/grade inert movement preparation QC fixtures, not prediction tests."""
import argparse
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent


def check_source_contract(engine):
    text = (engine / 'engine/common/protocol.h').read_text()
    struct = text[:text.index('} pmsourcestate_t;')].rsplit('typedef struct', 1)[1]
    struct = re.sub(r'/\*.*?\*/|//[^\n]*', '', struct, flags=re.S)
    if not struct.lstrip().startswith('{'):
        raise ValueError('Unrecognized Source state declaration')
    fields = set()
    for declaration in struct.lstrip()[1:].split(';'):
        if not declaration.strip():
            continue
        field = re.fullmatch(r'\s*(?:\w+\s+)+[*\s]*(\w+)\s*(?:\[[^\]]+\]\s*)?', declaration)
        if not field:
            raise ValueError('Unrecognized Source field declaration: ' + declaration.strip())
        fields.add(field[1])
    module = (ROOT / 'src/server/sv_moveprep.qc').read_text()
    policies = set(re.findall(r'^#define MP_SRC_(\w+) \d+i$', module, re.M)) - {'ALL'}
    if not fields or fields != policies:
        raise ValueError(f'Source policy drift: missing={fields-policies}, extra={policies-fields}')
    for forbidden in ('CSQC_PredictPlayerPreMove', 'SV_MovePrepLoad(', 'SV_MovePrepRelease('):
        for path in (ROOT / 'src').rglob('*.qc'):
            if path.name == 'sv_moveprep.qc' or path.parent.name == 'defs':
                continue
            if forbidden in path.read_text():
                raise ValueError(f'Unexpected production consumer/export: {path}: {forbidden}')
    print(f'PASS all {len(fields)} Source carried fields have explicit policies; no production consumers')


def build_fixture(out, weak):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    src = ROOT / 'src'
    lines = (src / 'sv_progs.src').read_text().splitlines()
    lines[0] = (out / ('weak-qwprogs.dat' if weak else 'qwprogs.dat')).as_posix()
    idx = lines.index('server/sv_player.qc')
    lines.insert(idx, '../tools/fixtures/moveprep_begin.qc')
    lines.append('../tools/fixtures/moveprep.qc')
    if weak:
        module = (src / 'server/sv_moveprep.qc').read_text()
        old = 'status = MP_FileMatches(sprintf("%s/save%s/state.txt", root, SL_NN(id)), r);'
        if module.count(old) != 1:
            raise ValueError('Weak-control source anchor drift')
        # Exactly one production decision differs, not fixture expectations.
        target = out / 'weak-moveprep.qc'
        target.write_text(module.replace(old, old + '\n\tstatus = MP_READY; // test-only weak content control'))
        lines[lines.index('server/sv_moveprep.qc')] = pathlib.Path(os.path.relpath(target, src)).as_posix()
    listing = src / ('p678moveprep_weak.src' if weak else 'p678moveprep.src')
    listing.write_text('\n'.join(lines) + '\n')
    try:
        result = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', listing.name],
                                cwd=src, text=True, capture_output=True)
        (out / ('weak-compile.log' if weak else 'compile.log')).write_text(result.stdout + result.stderr)
        text = result.stdout + result.stderr
        if result.returncode or 'Done. 0 warnings' not in text or re.search(r': (?:warning|error)', text, re.I):
            raise RuntimeError('Fixture compile failed or warned; inspect retained compile log')
    finally:
        listing.unlink()
    print('PASS fixture compiled:', lines[0])


def grade(server, client, weak):
    for marker in ('FTESurf CSQC loaded', 'MOVEPREP CLIENT COMPLETE', 'RUNLINES COMPLETE'):
        if marker not in client:
            raise ValueError('Client control did not act: ' + marker)
    for bad in ('Unknown command', 'QC VM error', 'Cannot call', 'stack overflow'):
        if bad in server or bad in client:
            raise ValueError('Runtime fault: ' + bad)
    rows = re.findall(r'MOVEPREP COMPLETE checks=(\d+) failed=(\d+)', server)
    if len(rows) != 1:
        raise ValueError('Exactly one completed preparation control is required')
    checks, failures = map(int, rows[0])
    if checks < 50:
        raise ValueError('Preparation controls did not act')
    if weak:
        if not failures or 'MOVEPREP FAIL velocity changed independently' not in server:
            raise ValueError('Weak-validation detector did not fire')
        print(f'PASS negative control detected weak validation: {failures}/{checks} assertions failed as expected')
    else:
        if failures or 'MOVEPREP FAIL' in server:
            raise ValueError(f'Preparation failed: {failures}/{checks}')
        print(f'PASS real QC preparation and old-operation parity: {checks} checks, 0 failed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=pathlib.Path)
    p.add_argument('--out', type=pathlib.Path)
    p.add_argument('--log', type=pathlib.Path)
    p.add_argument('--client-log', type=pathlib.Path)
    p.add_argument('--weak', action='store_true')
    a = p.parse_args()
    if a.engine:
        check_source_contract(a.engine)
    if a.out:
        build_fixture(a.out, a.weak)
    if a.log:
        if not a.client_log:
            p.error('--log requires --client-log')
        grade(a.log.read_text(errors='replace'), a.client_log.read_text(errors='replace'), a.weak)
    if not (a.engine or a.out or a.log):
        p.error('Use --engine, --out and/or --log')


if __name__ == '__main__':
    main()
