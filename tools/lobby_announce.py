#!/usr/bin/env python3
"""lobby_announce.py -- say one line in every lobby's chat (P1243), run ON the Pi.

build.ps1 -Pi -PiForce copies this beside the gamedir and runs it before a restart that drops
players.  It uses surfd's own rcon client (rcon.py: hashed password, loopback only, refuses `;`,
quotes, `$` and control characters) with the password from surfd.env, and sends ONE `say` per
port: the engine blocks a source for 24 h past 15 rcon packets in 30 s on a port, and zonepub and
the admin panel spend from that budget too.  A lobby that does not answer is reported, not retried.

usage: python3 -I lobby_announce.py --surfd /srv/nvme/surfd --text "<line>" PORT [PORT ...]
"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--surfd', default='/srv/nvme/surfd')
    ap.add_argument('--text', required=True)
    ap.add_argument('ports', nargs='+', type=int)
    a = ap.parse_args()
    sys.path.insert(0, a.surfd)
    import rcon
    rcon.check_arg(a.text)
    password = ''
    for line in (Path(a.surfd) / 'surfd.env').read_text().splitlines():
        key, _, value = line.partition('=')
        if key.strip() == 'SURFD_RCON_PASSWORD':
            password = value.strip().strip('"').strip("'")
    if not password:
        print('no SURFD_RCON_PASSWORD in surfd.env: nothing announced')
        return 2
    bad = 0
    for port in a.ports:
        try:
            rcon.Rcon('127.0.0.1', port, password, crypt=True).execute(['say', a.text])
            print('sent to %d' % port)     # a say has no reply: sent is all this can know
        except Exception as e:  # one lobby's trouble must not skip the rest
            bad += 1
            print('port %d: %s %s' % (port, type(e).__name__, rcon.redact(str(e))[:120]))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
