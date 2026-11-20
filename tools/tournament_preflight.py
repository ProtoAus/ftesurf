#!/usr/bin/env python3
"""Read-only tournament check before a live event (a stream). Prints GO / WARN / STOP lines and exits
0 (all GO), 1 (warnings) or 2 (a STOP). Changes nothing on the Pi or the site.

  python3 tools/tournament_preflight.py [--pi nanopi] [--site https://play.proto.bar]

Checks: the public routes the menu uses; the backend reports tournaments on, with free tournament
servers and map pools for surf and bhop; every lobby unit is up and in the directory; nobody is
sitting on a tournament server; surfd health; how many maps dropped out of the registry (a zone
republish since the last qualification run).
"""
import argparse
import json
import subprocess
import sys
import urllib.request

RESULTS = []


def note(level, text):
    RESULTS.append((level, text))
    print('%-5s %s' % (level, text), flush=True)


def get_public(site, path):
    req = urllib.request.Request(site + path, headers={'User-Agent': 'ftesurf-tournament-preflight'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read()


def pi(host, command):
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host, command],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-300:] or 'ssh failed')
    return r.stdout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pi', default='nanopi')
    ap.add_argument('--site', default='https://play.proto.bar')
    args = ap.parse_args(argv)

    # 1. What a player's menu sees, over the internet.
    try:
        status, body = get_public(args.site, '/api/tournament-lobbies?brief=1')
        d = json.loads(body)
        note('GO' if status == 200 and d.get('enabled') == 1 else 'STOP',
             'public room list: HTTP %d, enabled=%s' % (status, d.get('enabled')))
    except Exception as exc:  # noqa: BLE001 -- any failure here is the finding
        note('STOP', 'public room list unreachable: %s (the TOURNAMENT tab stays hidden)' % exc)
    for kind in ('surf', 'bhop'):
        try:
            status, body = get_public(args.site, '/api/tournament-map-pool?kind=%s&tiers=1023&profile=default&limit=1' % kind)
            d = json.loads(body)
            total, unq = d.get('total', 0), d.get('unqualified', 0)
            level = 'GO' if status == 200 and d.get('hosting') == 1 and total >= 24 else 'STOP'
            note(level, '%s map pool: %s qualified, %s unqualified, hosting=%s' % (kind, total, unq, d.get('hosting')))
            if unq > 20:
                note('WARN', '%s: %d maps fell out of the registry (zone republish?): re-run tools/tournament_qualify_live.py' % (kind, unq))
        except Exception as exc:  # noqa: BLE001
            note('STOP', '%s map pool unreachable: %s' % (kind, exc))

    # 2. The Pi: backend state, servers, units.
    try:
        raw = pi(args.pi, 'curl -s --max-time 5 localhost:8084/api/tournaments; echo @@; '
                          'curl -s --max-time 5 localhost:8084/lobbies.json; echo @@; '
                          'curl -s --max-time 5 localhost:8084/health; echo @@; '
                          "systemctl list-units 'ftesurf@*' --state=active --no-legend --no-pager | wc -l; echo @@; "
                          'grep -l "^set tournament_enable 1" /srv/nvme/ftesurf-server/game/ftesurf/cfg/lobby/lobby*.cfg | wc -l')
        parts = [p.strip() for p in raw.split('@@')]
        tours, lobbies, health = json.loads(parts[0]), json.loads(parts[1]), json.loads(parts[2])
        units, enabled_cfgs = int(parts[3]), int(parts[4])
    except Exception as exc:  # noqa: BLE001
        note('STOP', 'cannot read the Pi: %s' % exc)
        return finish()
    note('GO' if health.get('ok') else 'STOP', 'surfd health: %s' % json.dumps(health))
    note('GO' if tours.get('enabled') == 1 else 'STOP', 'backend tournaments enabled=%s' % tours.get('enabled'))
    rows = lobbies['lobbies'] if isinstance(lobbies, dict) else lobbies
    note('GO' if units == 12 and len(rows) == 12 else 'WARN', 'lobby units active %d, in the directory %d (expect 12)' % (units, len(rows)))
    slots = tours.get('slots', [])
    running = tours.get('rows', [])
    note('GO' if len(slots) >= 1 else 'STOP',
         'free tournament servers: %d of %d opted in (%s); matches running: %d' %
         (len(slots), enabled_cfgs, ', '.join(s.get('name', '?') for s in slots) or 'none', len(running)))
    tour_addrs = {s.get('addr') for s in slots}
    busy = [r for r in rows if r.get('addr') in tour_addrs and r.get('players')]
    for r in busy:
        note('WARN', '%s has %s player(s) on it: it cannot take a tournament until empty' % (r.get('name'), r.get('players')))
    if len(slots) < enabled_cfgs:
        note('WARN', '%d tournament server(s) not free (busy, reserved, or not heartbeating)' % (enabled_cfgs - len(slots)))
    return finish()


def finish():
    worst = max((('GO', 'WARN', 'STOP').index(level) for level, _ in RESULTS), default=0)
    print({0: 'ALL GO', 1: 'GO WITH WARNINGS', 2: 'STOP: fix the STOP lines first'}[worst])
    return worst


if __name__ == '__main__':
    sys.exit(main())
