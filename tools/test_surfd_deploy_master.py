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
    ap.add_argument('--script', type=Path, default=Path(__file__).with_name('surfd-deploy.ps1'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    check(any((p / 'OWNER.md').is_file() for p in [a.out, *a.out.parents]), 'owned --out required')
    a.out.mkdir(mode=0o700)  # A fresh fixture only; never reuse an earlier attempt.
    a.out.chmod(0o700)  # NVMe scratch inherits setgid; guard fixtures require exact private modes.
    tools = Path(__file__).resolve().parent
    text = a.script.read_text()
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

        def proof(ok, script=None):
            r = subprocess.run([sys.executable, '-c', script or code], capture_output=True, text=True)
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
        print('control: immutable source-root refusal')
        for inside in (f.home, f.home / 'nested'):
            inside.mkdir(exist_ok=True)
            (inside / 'surfd.pid').write_text(str(p.pid))
            proof(False, code.replace(str(remote), str(inside)))
            print('control: double-slash immutable root refusal')
            proof(False, code.replace(str(remote), '/' + str(inside)))
        alias = a.out / 'alias'
        alias.symlink_to(f.home, target_is_directory=True)
        try:
            proof(False, code.replace(str(remote), str(alias)))
        finally:
            alias.unlink()
        for leaf in ('momgrab.py', 'momgrab.py.new'):
            link = remote / leaf
            link.symlink_to(f.home / 'surfd.py')
            try:
                proof(False)
            finally:
                link.unlink()
        proof(True)
        print('PASS: OPEN candidate acts; identity/state/source/mode and immutable-root/nested/symlink destinations refuse')
    finally:
        stop(p)  # Only this fixture's handle, never a serving master.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
