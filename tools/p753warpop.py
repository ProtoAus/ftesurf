#!/usr/bin/env python3
"""Patch 753: `!r`, goto_spawn and a held save load are predicted -- no prederr.

A real dedicated socket with sv_minping (so the client predicts several commands
ahead) and one client on surf_dune.  Each gesture is made away from where it puts
the body, and the client's own `prederr:` lines (cl_prederror 4, the snap-back
meter) are counted from the gesture until 1.5 s after it settles:

  reset   walk out, `say !r`                      (the chat path, CSQC_ChatSay)
  spawn   walk out, `goto_spawn`
  load    crouch-jump, save at the top of the jump, land, stand, walk away,
          `+sl_hold` for a second and `-sl_hold`: the save is ducked in the air
          and the release unducks it there, the trick that shifted z

--control sets cl_warpop 0, the old stringcmds, and expects prederr in each
window.  The subject must print its own actions (`warpop:` on both sides, with
developer 1) and must still arrive where the server put it.

--posture duck|stand: crouch on the ground, save, stand, then hold the load.  The
server holds the body ducked; cl_predtrace's `vh` is the eye height the client
PREDICTS, ducked (~47) only if the replay has the server's posture.  With
--control (stringcmds) that is Patch 754's engine fix: the installed client
reads standing (~64), the fixed one ducked.  Without it, the op's own DUCK.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MAP = 'surf_dune'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Peer:
    def __init__(self, exe, base, cfg, server=False):
        self.log = base / 'ftesurf/logs/probe.log'
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             *([] if server else ['-window', '-width', '640', '-height', '480', '-nosound']),
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if server else 0)

    def text(self):
        if not self.log.exists():
            return ''
        return re.sub(r'\^[0-9]', '', self.log.read_text(encoding='utf-8', errors='replace'))

    def send(self, line):
        self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=30):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'owned process exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def query(self, command, pattern, timeout=30):
        offset = len(self.text())
        self.send(command)
        return self.wait(pattern, offset, timeout)

    def stop(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)


def prepare(a, name):
    base = a.out / name
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'models', 'textures', 'sound', 'particles'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (a.content / 'ftesurf/gfx' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    (game / 'maps/zones/local').mkdir(parents=True)
    (game / 'logs').mkdir()
    (game / 'data').mkdir()
    (game / 'data/consent.txt').write_text('version 4\n')
    (game / 'downloads/csprogsvers').mkdir(parents=True)
    shutil.copy2(a.content / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    shutil.copy2(a.content / f'ftesurf/maps/zones/local/{MAP}.json', game / f'maps/zones/local/{MAP}.json')
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(a.plugin, base / a.plugin.name)
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP753Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p753-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


PRED = re.compile(r'prederr: seq (\d+) origin off by ([\d.]+)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--threaded', action='store_true',
                    help='cl_threadedphysics 1: no CSQC_Input_Frame, so every gesture must fall back')
    ap.add_argument('--hold-engine', action='store_true',
                    help='the client predicts through a hold (Patch 754): expect no release prederr either')
    ap.add_argument('--posture', choices=['duck', 'stand'],
                    help='only the held ducked load, expecting this predicted eye')
    ap.add_argument('--port', type=int, default=27563)
    ap.add_argument('--minping', type=int, default=80)
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
    peers, checks, windows = [], [], {}
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks, 'windows': windows}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""', 'set lobby_enable 1',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0',
              'developer 1', 'log_developer 1']

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        return bool(ok)

    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set sv_guidkey p753-fixture',
            f'set sv_minping {a.minping}', f'map {MAP}']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=90)
        base = prepare(a, 'client')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'cl_threadedphysics {1 if a.threaded else 0}', 'name "P753"', 'set cl_prederror 4',
            f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl)
        cl.wait('FTESurf CSQC loaded', timeout=90)
        time.sleep(3)
        cl.send('menu_restart; ui_close')
        time.sleep(1)
        cl.send(f'set cl_warpop {0 if a.control else 1}')
        cl.send('set cl_prederror 4')
        time.sleep(1)

        def pos():
            m = cl.query('cmd viewpos', r'setpos ([-\d.]+) ([-\d.]+) ([-\d.]+)')
            return [float(m.group(i)) for i in (1, 2, 3)]

        def walk(t=1.2):
            cl.send('+forward'); time.sleep(t); cl.send('-forward'); time.sleep(0.8)

        def window(tag, gesture, settle=1.5):
            c0, s0 = len(cl.text()), len(sv.text())
            gesture()
            time.sleep(settle)
            ct, st = cl.text()[c0:], sv.text()[s0:]
            errs = [(int(s), float(d)) for s, d in PRED.findall(ct)]
            windows[tag] = {'prederr': errs, 'client_ops': re.findall(r'warpop: (\d+) on command (\d+)', ct),
                            'server_ops': re.findall(r'warpop: (\d+) at command (\d+)', st),
                            'said': re.findall(r'(!r|!m) -- [^\n]*\(([^)]*)\)', ct)}
            (a.out / f'{tag}-client.txt').write_text(ct)
            print(tag, json.dumps(windows[tag]), flush=True)
            return windows[tag]

        cl.send('cmd zone_goto 0')
        time.sleep(1.5)
        start = pos()
        if a.posture:
            cl.send('+duck'); time.sleep(1.0)
            cl.send('sl_save'); time.sleep(0.5)
            cl.send('-duck'); time.sleep(1.0)
            walk(0.6)
            c0 = len(cl.text())
            cl.send('+sl_hold'); time.sleep(0.8)
            cl.send('cl_predtrace 40'); time.sleep(1.2)
            cl.send('-sl_hold'); time.sleep(1.5)
            cl.send('cl_predtrace 1'); time.sleep(1.0)
            ct = cl.text()[c0:]
            (a.out / 'posture-client.txt').write_text(ct)
            rows = [line.split() for line in ct.splitlines() if re.match(r'.*\bptr \d', line)]
            vh = [float(r[-2]) for r in rows if len(r) >= 24]
            windows['posture'] = {'vh': vh, 'held': cl.text()[c0:].count('save 1')}
            print('posture vh', vh[:40], flush=True)
            check(len(vh) >= 20, 'cl_predtrace recorded the hold')
            mid = sorted(vh)[len(vh) // 2] if vh else 0
            if a.posture == 'duck':
                check(mid < 55.5, f'the client predicts the server\'s duck (eye {mid:.1f})')
            else:
                check(mid > 55.5, f'control: the client predicts standing (eye {mid:.1f})')
            return
        walk()
        away = pos()
        check(abs(away[0] - start[0]) + abs(away[1] - start[1]) > 50, 'walked away from the start')
        w = window('reset', lambda: cl.send('say !r'))
        back = pos()
        check(abs(back[0] - start[0]) + abs(back[1] - start[1]) < 2, 'say !r put the body back at the start')
        walk()
        w2 = window('spawn', lambda: cl.send('goto_spawn'))
        back2 = pos()
        check(abs(back2[0] - start[0]) + abs(back2[1] - start[1]) < 2, 'goto_spawn put the body at the start')

        walk(0.8)

        def crouch_save():
            # Moving: a still save hides the release's round trip (speed x RTT).
            cl.send('+forward'); time.sleep(0.6)
            cl.send('+jump'); time.sleep(0.2)
            cl.send('+duck'); time.sleep(0.15)
            cl.send('sl_save'); time.sleep(0.1)
            cl.send('-jump; -forward'); time.sleep(1.0)
            cl.send('-duck'); time.sleep(0.5)
        crouch_save()
        lst = cl.query('cmd sl_list', r'saveloc: (\d+) saved on[^\n]*\n[^\n]*')
        listing = cl.text()[-2000:]
        report['listing'] = listing
        check('ducked' in listing, 'the save is ducked')
        walk()

        def load():
            cl.send('+sl_hold'); time.sleep(1.0)
            cl.send('-sl_hold')
        w3 = window('load', load, settle=2.0)

        if a.threaded:
            check(not w['client_ops'] and not w2['client_ops'] and not w3['client_ops'],
                  'threaded: nothing queued an op')
            check(not w['server_ops'] and not w2['server_ops'] and not w3['server_ops'],
                  'threaded: the server ran no op')
        elif a.control:
            check(len(w['prederr']) > 0, 'control: say !r corrects the prediction')
            check(len(w2['prederr']) > 0, 'control: goto_spawn (zone_restart) corrects it')
            check(len(w3['prederr']) > 0, 'control: the held load corrects it')
        else:
            check([o for o, _ in w['client_ops']] == ['201'] and [o for o, _ in w['server_ops']] == ['201'],
                  'say !r rode one command on both sides')
            check(w['client_ops'][0][1] == w['server_ops'][0][1], 'the server ran it at that command')
            check([o for o, _ in w2['client_ops']] == ['202'] and [o for o, _ in w2['server_ops']] == ['202'],
                  'goto_spawn rode one command on both sides')
            check([o for o, _ in w3['server_ops']] == ['203', '204'], 'the load and its release rode commands')
            for tag, ww in (('reset', w), ('spawn', w2)):
                check(not ww['prederr'], f'{tag}: no prederr')
            rel = int(w3['server_ops'][1][1]) if len(w3['server_ops']) > 1 else 1 << 30
            held = [e for e in w3['prederr'] if e[0] < rel]
            after = [e for e in w3['prederr'] if e[0] >= rel]
            windows['load']['split'] = {'release': rel, 'before': held, 'after': after}
            check(not held, 'load: no prederr from the load to the release')
            if a.hold_engine:
                check(not after, 'load: no prederr at or after the release (Patch 754 engine)')
            else:
                print(f'note: release prederr on this engine: {after}', flush=True)
    finally:
        for peer in reversed(peers):
            peer.stop()
        (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    ok = checks and all(c['pass'] for c in checks)
    print('P753', 'CONTROL' if a.control else 'SUBJECT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
