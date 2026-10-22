#!/usr/bin/env python3
"""Linux-only acted stop/refusal test; argument is a NEW fixture under your OWN root.
Never uses the production pidfile or signals a discovered/shared process.
"""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time


def main():
    root = Path(sys.argv[1])
    assert root.is_absolute() and root.resolve() == root
    assert str(root).startswith('/srv/nvme/agent-work/') and not root.exists()
    assert any((p / 'OWNER.md').is_file() for p in root.parents), 'Owned task root required'
    control = root / 'control'
    control.mkdir(parents=True)
    helper = Path(__file__).with_name('stop_master.py')
    read, write = os.pipe()
    parent = os.fork()
    if parent == 0:
        os.close(read)
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)',
                                  '--chdir', str(control), 'witness_wsgi:app'],
                                 cwd=control, start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        os.write(write, str(child.pid).encode())
        os._exit(0)
    os.close(write)
    pid = int(os.read(read, 32))
    os.close(read)
    os.waitpid(parent, 0)
    fd = os.pidfd_open(pid, 0)
    poll = select.poll()
    poll.register(fd, select.POLLIN)
    record = root / 'process.json'
    record.write_text(json.dumps({'pid': pid, 'stopped': False}))
    try:
        for _ in range(50):
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[1]) == 1:
                break
            time.sleep(.02)
        assert int(fields[1]) == 1, 'Synthetic daemon not adopted by PID1'

        def run(where, *extra):
            return subprocess.run([sys.executable, str(helper), str(pid), str(where), *extra],
                                  capture_output=True, timeout=50)

        refused = run(root / 'different')
        assert refused.returncode != 0 and not poll.poll(0), 'Wrong role signalled fixture'
        optional = run(root / 'different', '--if-matches')
        assert optional.returncode == 0 and not poll.poll(0), 'Rollback skip signalled fixture'
        stopped = run(root)
        assert stopped.returncode == 0 and poll.poll(1000), 'Matching master not stopped'
        print('PASS acted synthetic daemon: strict wrong-root refused, optional wrong-root untouched, exact role stopped via pidfd')
    finally:
        if not poll.poll(0):
            signal.pidfd_send_signal(fd, signal.SIGTERM)
            assert poll.poll(5000), 'Owned fixture did not stop; recovery required'
        record.write_text(json.dumps({'pid': pid, 'stopped': True}))
        os.close(fd)


if __name__ == '__main__':
    main()
