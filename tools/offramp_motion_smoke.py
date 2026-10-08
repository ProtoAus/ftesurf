#!/usr/bin/env python3
"""PRIVATE authored mover fixture installer and five-arm standalone runner.

Never ship these servers. A fixture-only control contains only the same native
command, not buffer/origin/shape/hull capture seams. No maps/progs/plugins,
async map readiness, player data or completed-rig content links are required.
"""
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
from offramp_hull_smoke import prepare as hull_prepare
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
TARGET = 'offramp_motion_native.inc'


def prepare(engine, control=False):
    common = engine/'engine/common'
    if (common/TARGET).exists():
        raise RuntimeError('Refusing to overwrite private motion include')
    prepared = {} if control else hull_prepare(engine)
    path = common/'pm_source.c'
    source = prepared.get(path, path.read_text())
    source = once(source, 'void PMSrc_Init (void)\n{',
                  'static void OfframpMotion_f(void);\nvoid PMSrc_Init (void)\n{\n'
                  '\tCmd_AddCommandD("pm_offramp_trajectory", OfframpMotion_f, "PRIVATE authored mover fixtures; NEVER ship.");')
    fixture = (ROOT/'tools'/TARGET).read_text()
    digest = hashlib.sha256((ROOT/'tools'/TARGET).read_bytes()).hexdigest()
    base = subprocess.check_output(['git', '-C', str(engine), 'rev-parse', 'HEAD'], text=True).strip()
    source += ('\n' if control else '\n#define OFFRAMP_MOTION_CAPTURE 1\n')
    source += f'#define OFFRAMP_MOTION_SOURCE_SHA256 "{digest}"\n#define OFFRAMP_MOTION_ENGINE_COMMIT "{base}"\n'
    source += '#include "offramp_motion_native.inc"\n'
    prepared[path] = source
    prepared[common/TARGET] = fixture
    return prepared


def instrument(engine, control=False):
    isolated(engine)
    prepared = prepare(engine, control)
    for path, source in prepared.items():
        # Keep template bytes equal to the native embedded provenance digest.
        path.write_text(source, newline='' if path.name == TARGET else None)
    print('Private authored trajectory seams installed:', 'fixture-only' if control else 'capture', engine)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(server, output, content, port, timeout, capture, oracle):
    rig = Path(tempfile.mkdtemp(prefix='offramp-motion-', dir=output))
    gd = rig/'ftesurf'
    cfg = gd/'cfg/test/motion.cfg'
    cfg.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'default.fmf', rig/'default.fmf')
    executable = rig/'fteqwsv64.exe'
    shutil.copyfile(server, executable)
    cfg.write_text('cfg_save_auto 0\nsv_cheats 1\ndeveloper 0\n'
                   'pm_dispprobe 0\npm_ladderprobe 0\npm_selftest\n'
                   f'pm_offramp_trajectory {capture} {oracle}\necho OFFRAMPMOTION_COMPLETE\nquit\n')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', port))
    command = [str(executable), '-basedir', str(rig), '-manifest', str(rig/'default.fmf'),
               '-homedir', str(rig/'home'), '-port', str(port), '+sv_public', '0',
               '+log_enable', '1', '+log_name', 'offramp_motion', '+cfg_save_auto', '0',
               '+exec', 'cfg/test/motion.cfg']
    meta = {'utc_start': datetime.now(timezone.utc).isoformat(), 'rig': str(rig),
            'server_sha256': sha(executable), 'fixture_sha256': sha(ROOT/'tools'/TARGET),
            'cfg_sha256': sha(cfg), 'manifest_sha256': sha(rig/'default.fmf'),
            'tooling_source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'capture': capture, 'oracle': oracle, 'command': command}
    (rig/'arm.json').write_text(json.dumps(meta, indent=2)+'\n')
    process = None
    try:
        with (rig/'stdout.log').open('w') as out:
            process = subprocess.Popen(command, cwd=content, stdout=out, stderr=subprocess.STDOUT)
            meta['exit_code'] = process.wait(timeout=timeout)
        if meta['exit_code'] != 0:
            raise RuntimeError('Native fixture server failed; inspect retained arm')
        logs = list(rig.rglob('offramp_motion.log'))
        if len(logs) != 1:
            raise RuntimeError('Expected one owned standalone log')
        meta['log'] = str(logs[0])
        text = logs[0].read_text(errors='replace')
        if 'OFFRAMPMOTION_COMPLETE' not in text:
            raise RuntimeError('Standalone command path did not complete')
        return meta
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
            meta['terminated_owned_process'] = True
        meta['utc_end'] = datetime.now(timezone.utc).isoformat()
        (rig/'arm.json').write_text(json.dumps(meta, indent=2)+'\n')
        print('Retained standalone private rig:', rig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path)
    ap.add_argument('--fixture-only', action='store_true')
    ap.add_argument('--server', type=Path)
    ap.add_argument('--control-server', type=Path)
    ap.add_argument('--output-dir', type=Path)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--timeout', type=float, default=120)
    a = ap.parse_args()
    if a.instrument_native:
        instrument(a.instrument_native, a.fixture_only)
        return
    if not all((a.server, a.control_server, a.output_dir)):
        ap.error('Need --server --control-server --output-dir')
    if a.fixture_only or a.output_dir.exists():
        ap.error('Runner needs a NEW output directory; --fixture-only is installer-only')
    a.output_dir.mkdir(parents=True)
    arms = {}
    for name, server, capture, oracle in (('nooracle', a.control_server, 0, 0),
                                        ('control', a.control_server, 0, 1),
                                        ('off', a.server, 0, 1), ('on', a.server, 1, 1),
                                        ('repeat', a.server, 1, 1)):
        arms[name] = run(server, a.output_dir, a.content, a.port, a.timeout, capture, oracle)
        (a.output_dir/'arms.json').write_text(json.dumps(arms, indent=2)+'\n')
    print('Standalone native fixture arms completed; reader must grade every actor/oracle.')


if __name__ == '__main__':
    main()
