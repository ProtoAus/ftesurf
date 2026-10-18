#!/usr/bin/env python3
"""Patch 786: spectate inside a trigger, on surf_colony, isolated.

A dedicated server and two clients (Watcher, Target), each in its own basedir
under --out, the map from the Steam mounts (fs_addons.default.txt).  colony's
trigger_multiple *93 (multi_moon, wait 1) runs `echo multi_moon hit` on
OnStartTouch, so every entry is the server's own log line.  Its moon stands
inside the box, so a body dropped at SPOT rests in the trigger.
  A  rest in *93, hold 2 s, leave: does the entry output fire again?
  B  out, then back in: the entry output fires again (the leave was seen).
  C  rest in *93, step out and toggle spectate every few frames (raw rec_spec),
     step back in mid-toggle and toggle on: v2 fires the entry output exactly
     once (the touch ended while toggling, and holds inside do not re-fire);
     r2 fires none (toggling kept the left touch).  The step-out spot is inside
     *77, which has outputs, so the held lines' "pending" is not *93's.
  On v2 the server's run_spec_cooldown (never under 0.1 s) refuses most of the
  toggled re-entries ("you just left spectate"); r2 has no cooldown.
  D  (--countdown N > 0, instead of C) rest in *93 and hold/leave 20 times: each
     release comes from PlayerPostThink after the countdown, before the next
     move.  v2 fires no entry output; r4 (07239692's window rule) re-fires some.
--expect main (P784: A refused), v1 (ac6882ad: A accepted, re-fires on the
release), r2 (c410d513: C keeps the left touch), r4 (c4ca4a6a: D re-fires) or v2.  Exit 0 all held, 1 one failed, 2 could
not measure (the body did not come to rest in the trigger).
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from spec_chat_smoke import Peer, sha  # noqa: E402

MAP = 'surf_colony'
HIT = 'multi_moon hit'
# Inside *93 (x -4752..-1408, y 2720..3776, z -3200..-2152); a probe found the body stays put
# here (y 2900/3250 fall through to the fail teleport).
SPOT = '-3100 3600 -2200'
OUT = '-15234 -4838 3140'       # the spawn area, in no trigger
BOX = ((-4752, 2720, -3200), (-1408, 3776, -2152))


def prepare(a, name):
    base = a.out / name
    game = base / 'ftesurf'
    for folder in ('cfg', 'logs'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(ROOT / 'ftesurf/fs_addons.default.txt', game / 'fs_addons.txt')
    models = a.content / 'ftesurf/models'
    if models.is_dir():
        shutil.copytree(models, game / 'models')
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP786Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p786-unused\n')
    subprocess.run(['python', str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


class CannotMeasure(Exception):
    pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--expect', choices=('main', 'v1', 'r2', 'r4', 'v2'), required=True)
    ap.add_argument('--port', type=int, default=27616)
    ap.add_argument('--cooldown', type=float, default=0.25)
    ap.add_argument('--countdown', type=float, default=0)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    if not 27520 <= a.port <= 27620:
        ap.error('use a dedicated lobby-range port')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', a.port))
    a.out.mkdir(parents=True, exist_ok=False)
    peers, checks, failed = [], [], []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'expect': a.expect,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks, 'numbers': {}}
    num = report['numbers']
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set lobby_avatars 1', 'set lobby_av_stream 1',
              'set lobby_nocollide 1', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0']

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            failed.append(name)

    v = a.expect
    rc = 2
    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4',
            f'set run_spec_countdown {a.countdown:g}', f'set run_spec_cooldown {a.cooldown:g}', 'developer 1', 'log_developer 1',
            f'map {MAP}']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=120)
        clients = []
        for folder, name in [('watcher', 'Watcher'), ('target', 'Target')]:
            base = prepare(a, folder)
            (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
                'cl_threadedphysics 0', f'name "{name}"', f'connect 127.0.0.1:{a.port}']) + '\n')
            cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl); clients.append(cl)
            cl.wait('FTESurf CSQC loaded', timeout=120)
            time.sleep(2)
            cl.query('menu_restart; ui_close; cmd viewpos', r'setpos [-\d.]+ [-\d.]+ [-\d.]+')
        w, tg = clients
        time.sleep(1)

        def pos():
            m = w.query('cmd viewpos', r'setpos ([-\d.]+) ([-\d.]+) ([-\d.]+)')
            return tuple(float(x) for x in m.groups())

        def mark(tag):
            # Through the idle client's chat: ordered with the server's own lines.
            o = len(sv.text())
            tg.send(f'say P786MARK {tag}')
            sv.wait(f'P786MARK {tag}', o)
            return sv.text().index(f'P786MARK {tag}', o)

        def hits(a0, a1=None):
            return sv.text()[a0:a1].count(HIT)

        def inbox(q):
            return all(BOX[0][i] < q[i] < BOX[1][i] for i in range(3))

        def rest_in_box(tag):
            o = mark(tag)
            w.send(f'cmd setpos {SPOT}')
            time.sleep(3.0)
            p0 = pos(); time.sleep(0.5); p1 = pos()
            num[tag] = {'rest': [p0, p1], 'hits': hits(o)}
            if max(abs(p0[i] - p1[i]) for i in range(3)) > 0.5 or not inbox(p1):
                raise CannotMeasure(f'{tag}: not at rest inside *93 ({p0} -> {p1})')
            return hits(o)

        # A
        if rest_in_box('A-in') != 1:
            raise CannotMeasure(f"A-in: {num['A-in']['hits']} entry outputs, not 1")
        co, o = len(w.text()), len(sv.text())
        w.send('spectate next')
        time.sleep(1.0)
        said = ' | '.join(s for s in re.findall(r'spectate:(?:\^7)? ([^\n]*)', w.text()[co:])
                          if not s.startswith('stat '))
        ok = int(w.status()) > 0
        num['A_accepted'], num['A_said'] = ok, said
        if v == 'main':
            check(not ok and 'trigger' in said, f'A main: refused inside *93 ({said!r})')
        else:
            check(ok, 'A accepted inside *93')
            m = re.search(r'spectate: Watcher held inside a trigger \(touch (\d), pending (\d)\)', sv.text()[o:])
            num['A_held'] = m.group(0) if m else ''
            check(m is not None and m.group(2) == '1', f"A server: held inside a trigger, pending 1 ({num['A_held']!r})")
        if ok:
            time.sleep(1.0)
            o = len(sv.text())
            w.send('spectate off')
            try:
                m = sv.wait(r'spectate: Watcher released \((\w+)\)[^\n]*', o, timeout=10 + a.countdown)
            except RuntimeError:
                m = None
            check(m is not None and m.group(1) == 'leave', 'A released (leave)')
            if m is None:
                raise CannotMeasure('no release line')
            num['A_release'] = m.group(0)
            rel = o + m.end()
            time.sleep(2.5)
            end = mark('A-after')
            num['A_hits_after'] = hits(rel, end)
            num['A_rest_after'] = pos()
            check(inbox(num['A_rest_after']), f"A still inside *93 after the release ({num['A_rest_after']})")
            if v == 'r4':
                pass                    # its release can re-fire at random: recorded, D grades it
            elif v == 'v1':
                check(num['A_hits_after'] >= 1, f"A v1: the entry output fires again on release ({num['A_hits_after']})")
            else:
                check(num['A_hits_after'] == 0, f"A v2: no entry output after release ({num['A_hits_after']})")

        # B
        o = mark('B-out')
        w.send(f'cmd setpos {OUT}')
        time.sleep(1.5)
        num['B_hits_out'] = hits(o)
        check(num['B_hits_out'] == 0, f"B no entry output on leaving ({num['B_hits_out']})")
        b = rest_in_box('B-in')
        check(b == 1, f'B the entry output fires on re-entry ({b})')

        # C: toggling after leaving.  Target is entnum 2 (it connected second).
        if v != 'main' and a.countdown <= 0:
            w.send('alias p786tg "cmd rec_spec 2; wait; wait; wait; wait; cmd rec_spec 0; wait; wait"')
            rest_in_box('C-in')
            co = len(w.text())
            o = mark('C-out')
            w.send(f'cmd setpos {OUT}; ' + 'p786tg; ' * 12 + f'cmd setpos {SPOT}; ' + 'p786tg; ' * 6)
            time.sleep(4.5)
            w.send('cmd rec_spec 0')
            time.sleep(0.5)
            seg = sv.text()[o:]
            holds = re.findall(r'spectate: Watcher (held inside a trigger \(touch \d, pending (\d)\)|released \(leave\))', seg)
            # Each release ends a hold; a hold inside the touch logs its line first.
            flags, inside = [], False
            for whole, pend in holds:
                if whole.startswith('held'):
                    inside = pend == '1'
                else:
                    flags.append(inside)
                    inside = False
            num['C_out_holds'] = flags
            refused = re.findall(r'spectate:(?:\^7)? ((?!stat |watching)[^\n]*)', w.text()[co:])
            num['C_refused'] = refused
            if v == 'r2':
                if len(flags) < 12 or refused:
                    raise CannotMeasure(f"C: {len(flags)} holds released, refusals {refused}")
            else:
                cd = max(0.1, a.cooldown)
                cool = [r for r in refused if 'just left spectate' in r]
                # ~1.2 s of toggling: at most one entry per cooldown gets through.
                check(len(cool) >= 6 and 2 <= len(flags) <= 1.5 / cd + 1,
                      f"C cooldown: toggled re-entries refused ({len(cool)} refused, {len(flags)} holds)")
            num['C_hits'] = hits(o)
            num['C_rest'] = pos()
            if not inbox(num['C_rest']):
                raise CannotMeasure(f"C: not back inside *93 ({num['C_rest']})")
            if v == 'r2':
                check(num['C_hits'] == 0, f"C r2: toggling kept the left touch, no re-entry output ({num['C_hits']})")
            else:
                check(num['C_hits'] == 1, f"C: the re-entry fires the entry output once ({num['C_hits']}, {len(flags)} holds)")

        # D: releases from PlayerPostThink (the countdown), inside *93.
        if v != 'main' and a.countdown > 0:
            rest_in_box('D-in')
            o = mark('D-start')
            for _ in range(20):
                w.send('cmd rec_spec 2')
                time.sleep(0.4)
                w.send('cmd rec_spec 0')
                time.sleep(a.countdown + max(0.1, a.cooldown) + 0.4)
            end = mark('D-end')
            seg = sv.text()[o:end]
            num['D_releases'] = len(re.findall(r'spectate: Watcher released \(leave\)', seg))
            num['D_hits'] = seg.count(HIT)
            num['D_rest'] = pos()
            if num['D_releases'] < 15 or not inbox(num['D_rest']):
                raise CannotMeasure(f"D: {num['D_releases']} releases, rest {num['D_rest']}")
            if v == 'r4':
                check(num['D_hits'] >= 1, f"D r4: a countdown release re-fires the entry output ({num['D_hits']}/{num['D_releases']})")
            else:
                check(num['D_hits'] == 0, f"D: no entry output across {num['D_releases']} countdown releases ({num['D_hits']})")

        for peer in peers:
            bad = [b for b in ('QC VM error', 'stack overflow') if b in peer.text()]
            check(not bad, f'{peer.log.parent.parent.parent.name} has no VM errors')
        rc = 1 if failed else 0
    except (CannotMeasure, RuntimeError) as ex:
        print(f'CANNOT MEASURE: {ex}', flush=True)
        report['cannot_measure'] = str(ex)
        rc = 2
    finally:
        for peer in reversed(peers):
            peer.stop()
        report['stopped_owned_processes'] = all(p.proc.poll() is not None for p in peers)
        report['exit'] = rc
        (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'p786trig {v}: {"PASS" if rc == 0 else "FAIL" if rc == 1 else "CANNOT MEASURE"}'
          f' ({len(failed)} failed)', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
