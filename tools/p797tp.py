#!/usr/bin/env python3
"""Patch 797: `tp_player`, the TAB player list's Teleport.  A server and two clients.

"Mover" teleports to "Target" on surf_kitsune (p744spec.py's fixture: own basedirs,
configs and data roots under --out; no sv_cheats, so a run starts clean).  Graded on
the server's own words to the Mover: `setpos:` / `teleport:` / `run cancelled` lines,
`cmd viewpos` and `cmd timer`.

  setpos     setpos still moves and aims (its body is SV_SetPosSelf now)
  refuse     tp_player 0, 99 and the Mover's own number: "nobody to go to there", no move
  run        mid-run, the teleport cancels the run as `!r` would (the timer goes idle),
             lands 48 u behind the Target with its yaw, and a second one inside a
             second is refused
  solid      a Target inside solid: "no room to stand", no move

--control runs the same gestures on progs without P797 and expects no `teleport:`
line and no move from tp_player (setpos unchanged).
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_chat_smoke import Peer  # noqa: E402
from p744spec import MAP, prepare, sha  # noqa: E402

SPOT = '-15000 -15100 -400 10 20 0'     # setpos's own arm: anywhere, then read back
SOLID = '30000 30000 30000 0 0 0'       # outside the map: solid to every hull


def vec(s):
    return [float(x) for x in s.split()]


def near(a, b, tol):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    if not 27520 <= a.port <= 27620:
        ap.error('use a dedicated lobby-range port')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', a.port))
    a.out.mkdir(parents=True, exist_ok=False)
    peers, checks, notes = [], [], {}
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks, 'notes': notes}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set lobby_avatars 1', 'set lobby_av_stream 1',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0']

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        return bool(ok)

    def said(peer, command, settle=1.5):
        """What the server sprinted back to `command` (it has no end marker of its own)."""
        offset = len(peer.text())
        peer.send(command)
        time.sleep(settle)
        return peer.text()[offset:]

    def pos(peer):
        m = peer.query('cmd viewpos', r'setpos ([-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+)')
        return vec(m.group(1))

    def timer(peer):
        return peer.query('cmd timer', r'class: (\S+) \(seg \S+ cheat (\S+)', 25)

    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4',
            'developer 1', 'log_developer 1', f'map {MAP}']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=90)
        clients = []
        for folder, name in [('mover', 'Mover'), ('target', 'Target')]:
            base = prepare(a, folder)
            (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
                'cl_threadedphysics 0', f'name "{name}"', f'connect 127.0.0.1:{a.port}']) + '\n')
            cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl); clients.append(cl)
            cl.wait('FTESurf CSQC loaded', timeout=90)
            time.sleep(3)
            cl.send('menu_restart; ui_close')
            time.sleep(1)
        mover, target = clients
        st = said(sv, 'status', 2)
        (a.out / 'status.txt').write_text(st)
        # Slots are taken in connect order; the run arm's landing proves which one is which.
        me, them = 1, 2

        # setpos: its body moved into SV_SetPosSelf.
        out = said(mover, 'setpos ' + SPOT)
        p = pos(mover)
        notes['setpos'] = p
        check('setpos: ' in out and near(p[:3], vec(SPOT)[:3], 1) and near(p[3:5], vec(SPOT)[3:5], 0.5),
              'setpos moves and aims')

        # Refusals: world, an empty slot, yourself.
        for n in (0, 99, me):
            before = pos(mover)
            out = said(mover, f'cmd tp_player {n}')
            after = pos(mover)
            refused = 'nobody to go to there' in out
            check((not refused if a.control else refused) and near(before, after, 0.01),
                  f'tp_player {n}: {"no answer" if a.control else "refused"}, no move')

        # The run: the Target walks well out of the start and stops; the Mover walks
        # out less far (a running run), then teleports.
        target.send('cmd zone_goto 0')
        time.sleep(1.5)
        target.send('+forward'); time.sleep(3.0); target.send('-forward')
        time.sleep(1.5)
        tp = pos(target)
        notes['target'] = tp
        mover.send('cmd zone_goto 0')
        time.sleep(1.5)
        mover.send('+forward'); time.sleep(1.5); mover.send('-forward')
        time.sleep(1.0)
        m0 = timer(mover)
        out = said(mover, 'cmd timer', 1.0)
        notes['before'] = {'class': m0.group(1), 'cheat': m0.group(2), 'running': 'running on' in out}
        check(m0.group(1) == 'clean' and 'running on' in out, 'the Mover is on a clean running run')
        before = pos(mover)
        out = said(mover, f'cmd tp_player {them}', 0.5)
        again = said(mover, f'cmd tp_player {them}', 1.0)     # inside TP_GAP
        after = pos(mover)
        state = said(mover, 'cmd timer', 1.0)
        yaw = math.radians(tp[4])
        behind = [tp[0] - 48 * math.cos(yaw), tp[1] - 48 * math.sin(yaw), tp[2]]
        notes['after'] = {'pos': after, 'expected': behind, 'running': 'running on' in state}
        (a.out / 'mover-run.txt').write_text(out + again + state)
        if a.control:
            check('teleport:' not in out and near(before[:3], after[:3], 64), 'no teleport without P797')
        else:
            check('teleport:^7 to' in out or 'teleport: to' in out, 'the Mover is told it teleported')
            check('run cancelled' in out and 'running on' not in state and 'idle on' in state,
                  'the running run was cancelled, as !r cancels one, and the timer is idle')
            check(near(after[:3], behind, 4), 'the Mover stands 48 u behind the Target')
            check(abs((after[4] - tp[4] + 180) % 360 - 180) < 1, "the Mover has the Target's yaw")
            check('one a second' in again, 'a second teleport inside a second is refused')

        # Solid: the Target outside the map.
        target.send('setpos ' + SOLID)
        time.sleep(1.5)
        before = pos(mover)
        out = said(mover, f'cmd tp_player {them}')
        after = pos(mover)
        check(('no room to stand' not in out if a.control else 'no room to stand' in out)
              and near(before[:3], after[:3], 64), 'a Target in solid: refused, no move')
    finally:
        for peer in reversed(peers):
            peer.stop()
        report['stopped_owned_processes'] = all(p.proc.poll() is not None for p in peers)
        report['failures'] = sum(1 for c in checks if not c['pass'])
        (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('report', a.out / 'report.json', 'failures', report['failures'])


if __name__ == '__main__':
    main()
