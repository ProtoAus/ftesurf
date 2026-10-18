#!/usr/bin/env python3
"""Patch 805: the step smoother after a long frame (CL_CalcCrouch), on surf_null.

Drives tools/conbridge.py (a dedicated server + one client in the real install, the owner's
config in a private copy).  Each trial: cl_maxfps 4, `cmd respawn` -- the spawn is 25 u above
the floor, so the fall is seen across one ~0.25 s frame -- then cl_maxfps 100, two seconds
standing still, and `cl_predtrace 4`.  Graded on the engine's own trace line (`ptr ... vh
crouch`): crouch must be back to 0 within two seconds of landing.  The client is --client, so
the same script measures an installed exe (the control) and a built one (the subject).
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
BRIDGE = [sys.executable, str(ROOT / 'tools/conbridge.py')]


def bridge(name, *args, timeout=330):
    r = subprocess.run(BRIDGE + ['--name', name] + list(args), capture_output=True, text=True,
                       timeout=timeout, cwd=str(ROOT))
    return r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--client', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--trials', type=int, default=3)
    ap.add_argument('--out', type=pathlib.Path, required=True)
    a = ap.parse_args()
    out = {'client': a.client, 'trials': []}
    print(bridge(a.name, 'start', '--map', 'surf_null', '--window', 'back', '--client', a.client)
          .strip().splitlines()[-1])
    try:
        for t in range(a.trials):
            bridge(a.name, 'send', 'cl_maxfps 4')
            time.sleep(1.5)
            bridge(a.name, 'send', 'cmd respawn')
            time.sleep(2.5)
            bridge(a.name, 'send', 'cl_maxfps 100')
            time.sleep(2.0)
            bridge(a.name, 'log')                       # drop everything before the trace
            bridge(a.name, 'send', 'cl_predtrace 4')
            time.sleep(1.5)
            log = bridge(a.name, 'log')
            rows = re.findall(r'^.*?ptr \d+ .* (-?[\d.]+) (-?[\d.]+)\s*$', log, re.M)
            crouch = [float(c) for vh, c in rows]
            info = bridge(a.name, 'info')
            z = re.search(r'origin \S+ \S+ (\S+)', info)
            trial = {'crouch': crouch, 'server_z': float(z.group(1)) if z else None}
            out['trials'].append(trial)
            print('trial %d: server z %s, crouch %s' % (t + 1, trial['server_z'], crouch), flush=True)
    finally:
        print(bridge(a.name, 'stop').strip().splitlines()[0])
    stuck = [tr for tr in out['trials'] if tr['crouch'] and max(abs(c) for c in tr['crouch']) > 0.5]
    out['stuck_trials'] = len(stuck)
    a.out.write_text(json.dumps(out, indent=2) + '\n')
    print('stuck trials: %d of %d' % (len(stuck), len(out['trials'])))


if __name__ == '__main__':
    main()
