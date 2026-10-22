#!/usr/bin/env python3
"""Gracefully stop only the inspected generation's pidfile master, via pidfd.

No process discovery, SIGKILL or signal to a reused/unrelated PID. Rollback may
use --if-matches to leave a different generation's current master untouched.
"""
import argparse
import os
from pathlib import Path
import select
import signal


def stop_master(pid, old, if_matches=False):
    old = old.resolve()
    proc = Path('/proc') / str(pid)

    def identity():
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        return int(fields[1]), fields[19]  # ppid, start ticks

    try:
        before = identity()
        fd = os.pidfd_open(pid, 0)
    except (FileNotFoundError, ProcessLookupError):
        if if_matches:
            return False
        raise RuntimeError('Inspected master already exited') from None
    try:
        args = (proc / 'cmdline').read_bytes().split(b'\0')
        matches = (identity() == before and before[0] == 1
                   and str(old / 'control').encode() in args
                   and b'witness_wsgi:app' in args
                   and Path(os.readlink(proc / 'cwd')).resolve() == old / 'runtime')
        if not matches:
            if if_matches:
                return False
            raise RuntimeError('Master identity/role changed; no signal sent')
        poll = select.poll()
        poll.register(fd, select.POLLIN)
        if not poll.poll(0):
            signal.pidfd_send_signal(fd, signal.SIGTERM)
        if not poll.poll(45000):
            raise RuntimeError('Master did not exit gracefully; no forced kill; recovery required')
        return True
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('generation_root', type=Path)
    parser.add_argument('--if-matches', action='store_true')
    args = parser.parse_args()
    if args.pid <= 1:
        parser.error('Refusing PID <= 1')
    print('Stopped inspected master' if stop_master(args.pid, args.generation_root, args.if_matches)
          else 'No matching live master; left other processes untouched')


if __name__ == '__main__':
    main()
