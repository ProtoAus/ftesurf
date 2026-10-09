#!/usr/bin/env python3
"""PRIVATE multi-patch PM actor installer/runner over the path capture; NEVER ship."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

from offramp_bevpm_smoke import source_digest as bevpm_digest
from offramp_contact_smoke import isolated
from offramp_motion_smoke import sha
from offramp_tripath_smoke import TARGET as PATH_TARGET, prepare as path_prepare, source_digest as path_digest
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ('offramp_trimulti_native.inc', 'offramp_trimulti_bih.inc')
NAMES = ('nooracle', 'control', 'off', 'on', 'repeat')


def source_digest():
    return hashlib.sha256(b''.join((ROOT/'tools'/n).read_bytes() for n in
                                  (*TARGETS, 'offramp_trimulti_smoke.py'))).hexdigest()


def prepare(engine, control=False):
    common = engine/'engine/common'
    if any((common/t).exists() for t in TARGETS):
        raise RuntimeError('Refusing to overwrite private multi-patch include')
    prepared = path_prepare(engine, control)
    path, bih = common/'pm_source.c', common/'com_bih.c'
    text = once(prepared[path], 'static void OfframpBevPM_f(void);',
                'static void OfframpTriMulti_f(void);\nstatic void OfframpBevPM_f(void);')
    text = once(text, 'void PMSrc_Init (void)\n{',
                'void PMSrc_Init (void)\n{\n\tCmd_AddCommandD("pm_offramp_multitrajectory", OfframpTriMulti_f, '
                '"PRIVATE multi-patch PM actors; NEVER ship.");')
    prepared[path] = text+f'\n#define OFFRAMP_TRIMULTI_SOURCE_SHA256 "{source_digest()}"\n#include "{TARGETS[0]}"\n'
    # struct bihnode_s is private to com_bih.c, so the leaf copy has to live there, in BOTH servers.
    prepared[bih] += f'\n#include "{TARGETS[1]}"\n'
    for name in TARGETS:
        prepared[common/name] = (ROOT/'tools'/name).read_text()
    return prepared


def instrument(engine, control=False):
    isolated(engine)
    prepared = prepare(engine, control)  # validate every seam before any write
    for path, text in prepared.items():
        # Same byte contract as the path layer for everything it wrote; LF for the new includes.
        path.write_text(text, newline='' if path.name in (PATH_TARGET, 'offramp_motion_native.inc', *TARGETS) else None)
    print('Private multi-patch actors installed:', 'fixture-only' if control else 'capture', engine)


def run(server, output, content, port, timeout, capture, oracle):
    rig = Path(tempfile.mkdtemp(prefix='trimulti-', dir=output))
    cfg = rig/'ftesurf/cfg/test/motion.cfg'
    cfg.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'default.fmf', rig/'default.fmf')
    executable = rig/'fteqwsv64.exe'
    shutil.copyfile(server, executable)
    cfg.write_text('cfg_save_auto 0\nsv_cheats 1\ndeveloper 0\npm_dispprobe 0\npm_ladderprobe 0\npm_selftest\n'
                   f'pm_offramp_trajectory {capture} {oracle}\n'
                   f'pm_offramp_bevtrajectory {capture} {oracle}\n'
                   f'pm_offramp_multitrajectory {capture} {oracle}\necho OFFRAMPMOTION_COMPLETE\nquit\n')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', port))
    command = [str(executable), '-basedir', str(rig), '-manifest', str(rig/'default.fmf'),
               '-homedir', str(rig/'home'), '-port', str(port), '+sv_public', '0',
               '+log_enable', '1', '+log_name', 'offramp_motion', '+cfg_save_auto', '0',
               '+exec', 'cfg/test/motion.cfg']
    meta = {'utc_start': datetime.now(timezone.utc).isoformat(), 'rig': str(rig),
            'server_sha256': sha(executable), 'fixture_sha256': sha(ROOT/'tools/offramp_motion_native.inc'),
            'bevpm_source_sha256': bevpm_digest(), 'tripath_source_sha256': path_digest(),
            'trimulti_source_sha256': source_digest(), 'cfg_sha256': sha(cfg), 'manifest_sha256': sha(rig/'default.fmf'),
            'tooling_source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'capture': capture, 'oracle': oracle, 'command': command}
    process = None
    try:
        with (rig/'stdout.log').open('x') as out:
            process = subprocess.Popen(command, cwd=content, stdout=out, stderr=subprocess.STDOUT)
            meta['exit_code'] = process.wait(timeout=timeout)
        if meta['exit_code'] != 0:
            raise RuntimeError('Native multi-patch server failed; inspect retained arm')
        logs = list(rig.rglob('offramp_motion.log'))
        if len(logs) != 1:
            raise RuntimeError('Expected one owned multi-patch log')
        meta['log'] = str(logs[0])
        if 'OFFRAMPMOTION_COMPLETE' not in logs[0].read_text(errors='replace'):
            raise RuntimeError('Native multi-patch command path did not complete')
        return meta
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
            meta['terminated_owned_process'] = True
        meta['utc_end'] = datetime.now(timezone.utc).isoformat()
        (rig/'arm.json').write_text(json.dumps(meta, indent=2)+'\n')
        print('Retained private multi-patch rig:', rig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path); ap.add_argument('--fixture-only', action='store_true')
    ap.add_argument('--server', type=Path); ap.add_argument('--control-server', type=Path)
    ap.add_argument('--output-dir', type=Path); ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--port', type=int, default=27617); ap.add_argument('--timeout', type=float, default=240)
    a = ap.parse_args()
    if a.instrument_native:
        instrument(a.instrument_native, a.fixture_only); return
    if not all((a.server, a.control_server, a.output_dir)) or a.fixture_only:
        ap.error('Need --server --control-server --output-dir')
    if a.output_dir.exists() or not (a.port == 27510 or 27520 <= a.port <= 27620) or a.timeout <= 0:
        ap.error('Need NEW output directory, positive timeout and lobby-range port')
    a.output_dir = a.output_dir.resolve()
    a.server = a.server.resolve(); a.control_server = a.control_server.resolve()
    a.content = a.content.resolve()
    a.output_dir.mkdir(parents=True)
    arms = {}
    for name, server, capture, oracle in zip(NAMES, (a.control_server, a.control_server, a.server, a.server, a.server),
                                             (0, 0, 0, 1, 1), (0, 1, 1, 1, 1)):
        arms[name] = run(server, a.output_dir, a.content, a.port, a.timeout, capture, oracle)
        (a.output_dir/'arms.json').write_text(json.dumps(arms, indent=2)+'\n')
    print('Five native multi-patch arms completed; completion is NOT grading.')


if __name__ == '__main__':
    main()
