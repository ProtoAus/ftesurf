#!/usr/bin/env python3
"""Act the deployer's guarded-master proof against an owned Linux fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from test_surfd_transition_guard import Fixture, GEN, check, save, stop


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out = a.out.resolve()
    check(any((p / 'OWNER.md').is_file() for p in [a.out, *a.out.parents]), 'owned --out required')
    a.out.mkdir(mode=0o700)  # A fresh fixture only; never reuse an earlier attempt.
    a.out.chmod(0o700)  # NVMe scratch inherits setgid; guard fixtures require exact private modes.
    tools = Path(__file__).resolve().parent
    text = (tools / 'surfd-deploy.ps1').read_text()
    code = text.split("<<'GUARDED_MASTER_PY'\n", 1)[1].split('\nGUARDED_MASTER_PY', 1)[0]
    f = Fixture(a.out / 'fixture', target_schema=20)
    p = f.candidate()
    try:
        f.run('reopen', '--generation', GEN, '--receipt', str(f.receipt()))
        remote = a.out / 'remote'
        remote.mkdir()
        pidfile = remote / 'surfd.pid'
        pidfile.write_text(str(p.pid))
        code = code.replace('__STAGE__', str(tools.parent)).replace('__GUARD__', str(f.state))
        code = code.replace('__REMOTE__', str(remote)).replace('__PID__', str(p.pid))

        def proof(ok):
            r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
            check((r.returncode == 0) == ok, 'unexpected guarded-master verdict')
            if ok:
                check('GUARD_MASTER_OK=%d' % p.pid in r.stdout, 'missing positive witness')
            check(p.poll() is None and not (f.home / 'imports').exists(),
                  'proof signaled candidate or imported app')

        proof(True)
        for path, changed in (
                (pidfile, str(p.pid + 1).encode()),
                (f.state / 'state.json', json.dumps(dict(json.loads((f.state / 'state.json').read_text()),
                                                        admission='CLOSED')).encode()),
                (f.home / 'surfd.py', b'# changed target source\n')):
            original = path.read_bytes()
            path.write_bytes(changed)
            proof(False)
            path.write_bytes(original)
        record = f.state / 'candidate.json'
        original = record.read_bytes()
        value = json.loads(original)
        value['process']['start'] = str(int(value['process']['start']) + 1)
        save(record, value)
        proof(False)
        record.write_bytes(original)
        f.state.chmod(0o755)
        try:
            proof(False)
        finally:
            f.state.chmod(0o700)
        proof(True)
        print('PASS: current OPEN candidate acts; wrong pid/start, CLOSED, changed source and insecure root refuse')
    finally:
        stop(p)  # Only this fixture's handle, never a serving master.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
