#!/usr/bin/env python3
"""Patch 744: the spectator's HUD reads the watched player's run.  Two clients, one surfs.

A real dedicated socket and two clients on surf_kitsune (Source map, hl2 plugin beside
the exes), each with its own basedir, config and data root under --out.  "Surfer" walks
out of the start, hops with a strafe, is put above a real ramp and rides it, then is put
in stage 2's start.  "Watcher" first makes rows of its own (a ride), then spectates the
Surfer through all of that, then comes back.

Graded on the subjects' own lines, never the panels' pixels:
  telemetry  `spectate status` says the HUD was fed, with samples and no unexplained gaps
  trainer    the Watcher's `trainer status` jumps match the Surfer's own: count, what
             ended each, strafes, air time, strafe rates
  segments   the Watcher's `boarding` rows and board numbers match the Surfer's
  splits     every split row the Watcher drew is one of the Surfer's own rows, exactly
  restore    after spectate the Watcher's own `boarding` rows and `timer` rows are back
--control runs the same gestures against a build without the patch and expects the
Watcher to have been fed nothing (no telemetry line, no rows, no jumps).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_chat_smoke import Peer  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAP = 'surf_kitsune'
# tools/p621trn.py: 126 u above a ramp 5500 u long (plane -0.76 -0.14 0.64).
DROP = '-15212.4 14484.6 10766.4 0 -104 0'
# Stage 2 ("Orange") start, the middle of its region, 40 u above its floor.
STAGE2 = '-13312 -15088 -424 0 90 0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(a, name):
    base = a.out / name
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'models', 'textures', 'sound', 'particles'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'crosshairs', 'env', 'ui'):
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
        'FTEMANIFEST 1\nGAME FTESurfP744Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p744-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


def rows(text, offset=0):
    """`timer`'s client rows: (kind, seg, ticks, delta, class)."""
    return [tuple(float(x) for x in m) for m in re.findall(
        r'row \d+: kind (\S+) seg (\S+) ticks (\S+) delta (\S+) class (\S+)', text[offset:])]


def boarding(text):
    seq = [(int(k), float(l)) for k, l in re.findall(r'boarding: row \d+ kind (\d+) level (-?[\d.]+)', text)]
    enter = re.search(r'boarding: enter (-?[\d.]+) u/s (-?[\d.]+)e .* ok (\d+) cost (-?[\d.]+) age (-?[\d.]+)', text)
    leave = re.search(r'boarding: leave (-?[\d.]+) u/s (-?[\d.]+)e .* ok (\d+) age (-?[\d.]+)', text)
    return {'rows': seq,
            'enter': enter and [float(enter.group(i)) for i in (1, 2, 4)],
            'leave': leave and [float(leave.group(i)) for i in (1, 2)]}


def jumps(text):
    out = []
    for num, end, kept, made, air, v0, v1, trace, q, rates in re.findall(
            r'trainer: jump (\d+) end (\d+) strafes (\d+) of (\d+) air (\d+)ms v (-?[\d.]+)->(-?[\d.]+)'
            r' trace (\d+) q (-?[\d.]+) rates((?: [LR][\d.]+)*)', text):
        out.append({'end': int(end), 'strafes': int(kept), 'air': int(air), 'v0': float(v0), 'v1': float(v1),
                    'q': float(q), 'rates': [(r[0], float(r[1:])) for r in rates.split()]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--port', type=int, default=27616)
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
    hud = ['set hud_trainer 1', 'set hud_trainer_split 1', 'set hud_seq 1', 'set hud_board 1',
           'set hud_boarding 1', 'set hud_splits 1', 'set hud_timer 1', 'set hud_energy_ref 0',
           'set hud_board_sound 0', 'set run_prestrafe 0', 'set cl_yawspeed 220']

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        return bool(ok)

    def block(peer, command, end, timeout=25):
        """A command's whole reply, up to a line only it prints last."""
        offset = len(peer.text())
        peer.send(command)
        peer.wait(end, offset, timeout)
        time.sleep(.3)
        return peer.text()[offset:]

    def dump(peer, tag):
        out = {'timer': block(peer, 'timer', r'cl results:'),
               'boarding': block(peer, 'boarding', r'boarding: zero now'),
               'trainer': block(peer, 'trainer status', r'trainer: panel ')}
        (a.out / f'{tag}.txt').write_text('\n'.join(out.values()))
        return out

    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4',
            'developer 1', 'log_developer 1', f'map {MAP}', 'wait', 'sv_cheats 1']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=90)
        sv.send('sv_cheats 1')
        clients = []
        for folder, name in [('surfer', 'Surfer'), ('watcher', 'Watcher')]:
            base = prepare(a, folder)
            (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + hud + [
                'cl_threadedphysics 0', f'name "{name}"', f'connect 127.0.0.1:{a.port}']) + '\n')
            cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl); clients.append(cl)
            cl.wait('FTESurf CSQC loaded', timeout=90)
            time.sleep(3)
            cl.send('menu_restart; ui_close')
            time.sleep(1)
            for line in hud:
                cl.send(line)
        surfer, watcher = clients

        def pos(peer):
            return peer.query('cmd viewpos', r'setpos ([-\d.]+ [-\d.]+ [-\d.]+)').group(1)

        # The Watcher's own rows first: a ride of its own, so the restore has something to keep.
        watcher.send('cmd zone_goto 0')
        time.sleep(1)
        watcher.send('+forward'); time.sleep(1.5); watcher.send('-forward')
        notes['watcher_walk'] = pos(watcher)
        watcher.send('+moveright')
        watcher.send('setpos ' + DROP)
        time.sleep(2.5)
        watcher.send('-moveright')
        time.sleep(1.5)
        pre = dump(watcher, 'watcher-before')

        # The Surfer stands in the start; the Watcher starts watching it there.
        surfer.send('cmd zone_goto 0')
        time.sleep(1.5)
        notes['surfer_start'] = pos(surfer)
        watcher.send('spectate Surfer')
        time.sleep(2)
        st = block(watcher, 'spectate status', r'camera ')
        (a.out / 'watcher-status-start.txt').write_text(st)
        check(re.search(r'spectate: stat [1-9]', st), 'the Watcher is spectating')

        # Out of the start, into stage 2 (the split), a hop with a right strafe from its
        # floor, the ride, and back to that floor to stand still for the dumps.
        watcher.send('body_trace 0 2500')    # `bx` per sample arrival, for a failure's diagnosis
        surfer.send('+forward'); time.sleep(1.2); surfer.send('-forward')
        notes['surfer_walk'] = pos(surfer)
        surfer.send('setpos ' + STAGE2)
        time.sleep(1.5)
        surfer.send('+moveright; +right; +jump'); time.sleep(0.08)
        surfer.send('-jump'); time.sleep(0.35)
        surfer.send('-right; -moveright'); time.sleep(1.5)
        surfer.send('+moveright')
        surfer.send('setpos ' + DROP)
        time.sleep(1.2)
        surfer.send('+left'); time.sleep(0.3); surfer.send('-left')
        time.sleep(0.5)
        # Off the ramp and straight to stage 2's floor, before the ramp's end teleports
        # the body: after that map teleport the server ran no move ticks for 0.7 s and
        # never set the ground flag, while the Surfer's own prediction landed it (run5).
        # The key's release rides a usercmd and setpos a stringcmd, which the server can take
        # first: sent together, the teleport's yaw step was graded on one side only.
        surfer.send('-moveright')
        time.sleep(0.2)
        surfer.send('setpos ' + STAGE2)
        time.sleep(3.0)

        st = block(watcher, 'spectate status', r'camera ')
        (a.out / 'watcher-status-end.txt').write_text(st)
        mine = dump(surfer, 'surfer')
        seen = dump(watcher, 'watcher-watching')

        # And back.
        watcher.send('spectate off')
        time.sleep(4.5)
        st2 = block(watcher, 'spectate status', r'camera ')
        back = dump(watcher, 'watcher-after')

        tele = re.search(r'telemetry held (\S+) fed (\S+) state (\S+) samples (\S+) last (\S+) gaps (\S+) rows (\S+)', st)
        if a.control:
            check(not tele, 'control: no telemetry line')
            check(jumps(seen['trainer']) == jumps(pre['trainer']), 'control: the Watcher\'s trainer was fed nothing')
            check(boarding(seen['boarding'])['rows'] == boarding(pre['boarding'])['rows'],
                  'control: the Watcher\'s segment rows did not move while watching')
            return

        check(tele and tele.group(2) == '1' and tele.group(3) == '1', 'telemetry: the HUD was fed STATE')
        if tele:
            notes['telemetry'] = tele.groups()
            check(float(tele.group(4)) > 300, f'telemetry: {tele.group(4)} samples fed')
            check(float(tele.group(6)) <= 2, f'telemetry: {tele.group(6)} gaps')

        jm, js = jumps(mine['trainer']), jumps(seen['trainer'])
        notes['jumps_surfer'], notes['jumps_watcher'] = jm, js
        check(jm and len(jm) == len(js), f'trainer: {len(js)} jumps seen, {len(jm)} made')
        for i, (m, s) in enumerate(zip(jm, js)):
            check(m['end'] == s['end'] and m['strafes'] == s['strafes'],
                  f'trainer jump {i}: end {s["end"]}/{m["end"]} strafes {s["strafes"]}/{m["strafes"]}')
            # Your own trainer reads the server's ground flag a snapshot late at each input
            # frame; the fed one has each sample's own tick.  Four ticks of that jitter.
            check(abs(m['air'] - s['air']) <= 60, f'trainer jump {i}: air {s["air"]} ms against {m["air"]}')
            # Jumps 0 and 1 turn at cl_yawspeed for the whole strafe: 5%.  Jump 2's turn
            # crosses the ramp's exit, and your own trainer reads ramp contact a snapshot
            # late, so which edge ticks are graded moves its mean (run7: 68.8 against 62.4).
            tol = 0.05 if i < 2 else 0.12
            for (dm, rm), (ds, rs) in zip(m['rates'], s['rates']):
                check(dm == ds and abs(rm - rs) <= max(3, tol * rm),
                      f'trainer jump {i}: strafe {ds}{rs} against {dm}{rm} deg/s')

        bm, bs = boarding(mine['boarding']), boarding(seen['boarding'])
        notes['boarding_surfer'], notes['boarding_watcher'] = bm, bs
        check(bs['rows'] and [k for k, _ in bs['rows']] == [k for k, _ in bm['rows']][-len(bs['rows']):],
              f'segments: kinds {[k for k, _ in bs["rows"]]} against {[k for k, _ in bm["rows"]]}')
        for (km, lm), (ks, ls) in zip(bm['rows'][-len(bs['rows']):], bs['rows']):
            check(abs(lm - ls) <= 3, f'segments: row level {ls} against {lm}')
        if bm['enter'] and bs['enter']:
            check(abs(bm['enter'][0] - bs['enter'][0]) <= 1 and abs(bm['enter'][2] - bs['enter'][2]) <= 1,
                  f'boarding: enter {bs["enter"]} against {bm["enter"]}')

        rm_, rs_ = rows(mine['timer']), rows(seen['timer'])
        notes['rows_surfer'], notes['rows_watcher'] = rm_, rs_
        check(rs_ and all(r[:3] in [x[:3] for x in rm_] for r in rs_),
              f'splits: the Watcher drew {rs_} of the Surfer\'s {rm_}')

        check(re.search(r'spectate: stat 0 ', st2), 'restore: the Watcher is back')
        bp, bb = boarding(pre['boarding']), boarding(back['boarding'])
        check(bb['rows'][:len(bp['rows'])] == bp['rows'], f'restore: segment rows {bb["rows"]} were {bp["rows"]}')
        check(rows(back['timer']) == rows(pre['timer']), f'restore: split rows {rows(back["timer"])} were {rows(pre["timer"])}')
        for peer in peers:
            check(not any(bad in peer.text() for bad in ('QC VM error', 'stack overflow', 'NULL pointer')),
                  peer.log.parent.parent.parent.name + ' has no VM errors')
    finally:
        for peer in reversed(peers):
            peer.stop()
        report['stopped_owned_processes'] = all(p.proc.poll() is not None for p in peers)
        report['failures'] = sum(1 for c in checks if not c['pass'])
        (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('report', a.out / 'report.json', 'failures', report['failures'])


if __name__ == '__main__':
    main()
