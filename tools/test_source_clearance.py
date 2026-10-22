#!/usr/bin/env python3
"""Run the engine's real trace/mover selftest in one owned, map-free rig."""
import argparse
from pathlib import Path
import shutil
import socket
import subprocess


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server', type=Path, required=True)
    ap.add_argument('--rig', type=Path, required=True, help='new path under an owned task root')
    ap.add_argument('--port', type=int, default=27617)
    args = ap.parse_args()
    if args.port != 27510 and not 27520 <= args.port <= 27620:
        ap.error('use an allowed dedicated lobby port')
    root = Path(__file__).resolve().parents[1]
    args.rig.mkdir(parents=True, exist_ok=False)
    cfg = args.rig / 'ftesurf/cfg/test/source_clearance.cfg'
    cfg.parent.mkdir(parents=True)
    shutil.copyfile(root / 'default.fmf', args.rig / 'default.fmf')
    cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\n'
                   'pm_selftest\necho SOURCE_CLEARANCE_COMPLETE\nquit\n')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('0.0.0.0', args.port))
        port = args.port
    cmd = [str(args.server.resolve()), '-basedir', str(args.rig.resolve()),
           '-manifest', str((args.rig / 'default.fmf').resolve()),
           '-homedir', str((args.rig / 'home').resolve()), '-port', str(port),
           '+sv_public', '0', '+log_enable', '1', '+log_name', 'source_clearance',
           '+cfg_save_auto', '0', '+exec', 'cfg/test/source_clearance.cfg']
    with (args.rig / 'stdout.log').open('w') as out:
        subprocess.run(cmd, cwd='C:/FTESurf', stdout=out, stderr=subprocess.STDOUT,
                       timeout=45, check=True)
    logs = list(args.rig.rglob('source_clearance.log'))
    if len(logs) != 1:
        raise RuntimeError(f'Expected one acting log, found {logs}')
    text = logs[0].read_text(errors='replace')
    if 'SOURCE_CLEARANCE_COMPLETE' not in text or 'all checks passed' not in text or 'FAILED' in text:
        raise RuntimeError(f'Selftest did not pass: {logs[0]}')
    # Baseline engines may be tested too: report, rather than invent, new coverage.
    print('Selftest passed;', text.count('P916'), 'P916 trace/state checks;', logs[0])


if __name__ == '__main__':
    main()
