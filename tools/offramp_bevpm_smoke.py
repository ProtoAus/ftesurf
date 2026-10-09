#!/usr/bin/env python3
"""PRIVATE separately enveloped PM triangle bevel installer/runner; NEVER ship."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

from offramp_contact_smoke import isolated
from offramp_motion_smoke import prepare as motion_prepare, sha
from offramp_tribev_smoke import prepare as bevel_prepare
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
TARGET = 'offramp_bevpm_native.inc'


def source_digest():
    return hashlib.sha256(b''.join((ROOT/'tools'/n).read_bytes() for n in
                                  (TARGET, 'offramp_bevpm_smoke.py'))).hexdigest()


def prepare(engine, control=False):
    common = engine/'engine/common'
    if (common/TARGET).exists():
        raise RuntimeError('Refusing to overwrite private bevel PM include')
    prepared = motion_prepare(engine, True) if control else bevel_prepare(engine)
    path = common/'pm_source.c'
    prepared[path] = once(prepared[path], 'static void OfframpMotion_f(void);',
                         'static void OfframpBevPM_f(void);\nstatic void OfframpMotion_f(void);')
    prepared[path] = once(prepared[path], 'void PMSrc_Init (void)\n{',
                         'void PMSrc_Init (void)\n{\n\tCmd_AddCommandD("pm_offramp_bevtrajectory", OfframpBevPM_f, "PRIVATE bevel PM actors; NEVER ship.");')
    prepared[path] += f'\n#define OFFRAMP_BEVPM_SOURCE_SHA256 "{source_digest()}"\n#include "{TARGET}"\n'
    prepared[common/TARGET] = (ROOT/'tools'/TARGET).read_text()
    # BIH's probe record/functions are translation-unit-local, not com_bih.h APIs.
    # Identical save/restore adapters in both fixture-only and capture servers.
    bih = common/'com_bih.c'
    prepared[bih] = prepared.get(bih, bih.read_text()) + (
        '\nstatic struct bihproberec_s offramp_bevpm_savedprobe;\n'
        'void OfframpBevPM_ProbeSave(void) { BIH_ProbeSave(&offramp_bevpm_savedprobe); }\n'
        'void OfframpBevPM_ProbeRestore(void) { BIH_ProbeRestore(&offramp_bevpm_savedprobe); }\n')
    return prepared


def instrument(engine, control=False):
    isolated(engine)
    prepared = prepare(engine, control)
    for path, text in prepared.items():
        path.write_text(text, newline='' if path.name in (TARGET, 'offramp_motion_native.inc') else None)
    print('Private bevel PM actors installed:', 'fixture-only' if control else 'capture', engine)


def run(server, output, content, port, timeout, capture, oracle):
    rig = Path(tempfile.mkdtemp(prefix='bevpm-', dir=output))
    cfg = rig/'ftesurf/cfg/test/motion.cfg'
    cfg.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'default.fmf', rig/'default.fmf')
    executable = rig/'fteqwsv64.exe'
    shutil.copyfile(server, executable)
    cfg.write_text('cfg_save_auto 0\nsv_cheats 1\ndeveloper 0\npm_dispprobe 0\npm_ladderprobe 0\npm_selftest\n'
                   f'pm_offramp_trajectory {capture} {oracle}\n'
                   f'pm_offramp_bevtrajectory {capture} {oracle}\necho OFFRAMPMOTION_COMPLETE\nquit\n')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', port))
    command = [str(executable), '-basedir', str(rig), '-manifest', str(rig/'default.fmf'),
               '-homedir', str(rig/'home'), '-port', str(port), '+sv_public', '0',
               '+log_enable', '1', '+log_name', 'offramp_motion', '+cfg_save_auto', '0',
               '+exec', 'cfg/test/motion.cfg']
    meta = {'utc_start': datetime.now(timezone.utc).isoformat(), 'rig': str(rig),
            'server_sha256': sha(executable), 'fixture_sha256': sha(ROOT/'tools/offramp_motion_native.inc'),
            'bevpm_source_sha256': source_digest(), 'cfg_sha256': sha(cfg), 'manifest_sha256': sha(rig/'default.fmf'),
            'tooling_source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'capture': capture, 'oracle': oracle, 'command': command}
    process = None
    try:
        with (rig/'stdout.log').open('x') as out:
            process = subprocess.Popen(command, cwd=content, stdout=out, stderr=subprocess.STDOUT)
            meta['exit_code'] = process.wait(timeout=timeout)
        if meta['exit_code'] != 0:
            raise RuntimeError('Native bevel PM server failed; inspect retained arm')
        logs = list(rig.rglob('offramp_motion.log'))
        if len(logs) != 1:
            raise RuntimeError('Expected one owned bevel PM log')
        meta['log'] = str(logs[0])
        if 'OFFRAMPMOTION_COMPLETE' not in logs[0].read_text(errors='replace'):
            raise RuntimeError('Native bevel PM command path did not complete')
        return meta
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
            meta['terminated_owned_process'] = True
        meta['utc_end'] = datetime.now(timezone.utc).isoformat()
        (rig/'arm.json').write_text(json.dumps(meta, indent=2)+'\n')
        print('Retained private bevel PM rig:', rig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path)
    ap.add_argument('--fixture-only', action='store_true')
    ap.add_argument('--server', type=Path)
    ap.add_argument('--control-server', type=Path)
    ap.add_argument('--output-dir', type=Path)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--timeout', type=float, default=180)
    a = ap.parse_args()
    if a.instrument_native:
        instrument(a.instrument_native, a.fixture_only)
        return
    if not all((a.server, a.control_server, a.output_dir)) or a.fixture_only:
        ap.error('Need --server --control-server --output-dir')
    if a.output_dir.exists() or not (a.port == 27510 or 27520 <= a.port <= 27620) or a.timeout <= 0:
        ap.error('Need NEW output directory, positive timeout and lobby-range port')
    a.output_dir.mkdir(parents=True)
    arms = {}
    for name, server, capture, oracle in (('nooracle', a.control_server, 0, 0), ('control', a.control_server, 0, 1),
                                        ('off', a.server, 0, 1), ('on', a.server, 1, 1), ('repeat', a.server, 1, 1)):
        arms[name] = run(server, a.output_dir, a.content, a.port, a.timeout, capture, oracle)
        (a.output_dir/'arms.json').write_text(json.dumps(arms, indent=2)+'\n')
    print('Five native bevel PM arms completed; completion is NOT grading.')


if __name__ == '__main__':
    main()
