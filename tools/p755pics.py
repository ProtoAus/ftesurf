#!/usr/bin/env python3
"""P755 real-client Steam-picture disk cache: a file a mark, kept SP_DISKDAYS,
drawn from disk at once with only asks paced. --root is a NEW owned folder.

Thirteen pictured players on one board. Every arm grades the client's own
`scores pics` lines (state 3 drawn, 6 old copy drawn, 7 old copy refreshing),
surfd's count of picture requests, and a screenshot. Run it under the rig lock
(rig_wait.py). Against a pre-P755 csprogs the warm burst, yesterday and file
layout arms must fail. `vid_restart` ends the test client on both builds
(BACKLOG); its two checks fail for that reason, not the cache.
"""
import argparse
import hashlib
import json
import re
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
import p615link as L
import p640pics as P

N = 13
DRAWN = ('3', '6', '7')


def pics(cl):
    """{mark: state} from the last `scores pics` block, and its disk-hit count."""
    t = cl.text()
    i = t.rfind('steampic: asked')
    if i < 0:
        return {}, 0
    block = t[i:]
    states = dict(re.findall(r'steampic: slot \d+ mark ([0-9a-f]{8}) state (\d+)', block))
    m = re.search(r'disk hits (\d+)', block)
    return states, int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.output_dir = a.root.resolve(); a.output_dir.mkdir()
    (a.output_dir / 'OWNER.md').write_text('p755pics; owned child clients only; retained evidence.\n')
    a.progs = a.progs.resolve()
    rig, gd, junctions = L.build_rig(a)
    client = web = None
    try:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        web, db = L.start_surfd(rig, port, '127.0.0.1')
        S, A = sys.modules['surfd'], sys.modules['accounts']
        import steamsync
        sids = [str(int(P.SID) + 2 * k) for k in range(N)]
        c = sqlite3.connect(db)
        for k, sid in enumerate(sids):
            c.execute('INSERT INTO accounts (steamid,name,created_at,avatar) VALUES (?,?,?,?)',
                      (sid, 'Pictured%02d' % k, int(time.time()), P.HASH))
            c.execute("INSERT INTO runs (map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) VALUES ('bhop_eazy',0,0,'ksf','clean',?,?,?,100,?,0,'import',?,?,0)",
                      (sid, 'Pictured%02d' % k, 3000 + k, (3000 + k) * 10, 'i-' + sid, int(time.time())))
        c.commit(); c.close()
        Path(S.AVATAR_DIR).mkdir(parents=True, exist_ok=True)
        body = steamsync.game_form(P.picture())
        Path(S.AVATAR_DIR, P.HASH + '.jpg').write_bytes(P.picture())
        Path(S.AVATAR_DIR, P.HASH + '.txt').write_text(body, newline='\n')
        S.avatars_reset(); S.people_reset()
        real, asks = S.game_avatar, []
        def avatar(who, now):
            asks.append(time.time()); return real(who, now)
        S.game_avatar = avatar
        origin = 'http://127.0.0.1:%d' % port
        marks = [A.who_of(sid) for sid in sids]
        keys = {m: hashlib.sha256((origin + '\n' + m).encode()).hexdigest() for m in marks}
        folder = gd / 'data/cache/steampic'
        path = {m: folder / (keys[m] + '.txt') for m in marks}
        today = time.strftime('%Y%m%d', time.localtime())          # strftime(TRUE): local
        yesterday = time.strftime('%Y%m%d', time.localtime(time.time() - 86400))
        results = {}

        def redate(m, day):
            text = path[m].read_text()
            lines = text.splitlines(); lines[0] = lines[0][:-8] + day
            path[m].write_text('\n'.join(lines) + '\n', newline='\n')

        # No 404 arm: a board row carries no mark for a player without a picture, so
        # the client never asks for one (measured 2026-10-17); SP_DiskForget is unexercised.
        for arm in ('cold', 'warm', 'yesterday', 'old', 'legacy', 'corrupt', 'origin'):
            moved = {marks[1]} if arm in ('corrupt', 'origin') else set()   # the legacy arm's
            if arm != 'cold':
                L.check(arm + ': per-mark files from cold exist',
                        all(path[m].exists() for m in marks if m not in moved), True)
            if arm == 'yesterday':
                for m in marks:
                    if path[m].exists(): redate(m, yesterday)
            if arm == 'old' and path[marks[0]].exists():
                redate(marks[0], '20000101')
            if arm == 'legacy' and path[marks[1]].exists():
                text = path[marks[1]].read_text(); path[marks[1]].unlink()
                (folder / (keys[marks[1]][:2] + '.txt')).write_text(text, newline='\n')
            if arm == 'corrupt' and path[marks[2]].exists():
                path[marks[2]].write_bytes(path[marks[2]].read_bytes()[:110])
            want = {'cold': N, 'warm': 0, 'yesterday': N, 'old': 1, 'legacy': 0,
                    'corrupt': 1, 'origin': N}[arm]
            before = len(asks)
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 4
            client = subprocess.Popen([str(a.client), '-plugin', '-nobrowse', '-basedir', str(rig),
                '-manifest', str(rig / 'default.fmf'), '+set', 'cfg_save_auto', '0', '+set', 'log_enable', '1',
                '+set', 'log_dir', 'logs', '+set', 'log_name', arm, '-window', '-nosound',
                '+set', 'con_savehistory', '0', '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
                '+set', 'vid_width', '1280', '+set', 'vid_height', '720'], cwd=a.content,
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
            def send(line):
                try:
                    client.stdin.write(line.encode('ascii') + b'\n'); client.stdin.flush()
                except OSError:
                    pass                # a client that has gone is graded by poll() below
            cl = L.Log(gd / ('logs/' + arm + '.log')); time.sleep(8)
            send('map bhop_eazy')
            L.check(arm + ': CSQC loaded', bool(cl.wait('FTESurf CSQC loaded', 45)), True)
            base = origin + ('/' if arm == 'origin' else '')
            send('menu_restart'); send('closemenu'); send('set rec_terms 6'); send('set lobby_dir "%s"' % base)
            time.sleep(1); send('scores open'); send('scores tab online')
            t0, drawn_at, asks_at_draw, reopened = time.time(), None, None, time.time()
            while time.time() - t0 < 60:
                send('scores pics'); time.sleep(0.5)
                st, disk = pics(cl)
                if not st and time.time() - reopened > 3:
                    # The client's zones can land after the first open (leg "?"): ask again.
                    send('scores open'); send('scores tab online'); reopened = time.time()
                if drawn_at is None and sum(1 for m in marks if st.get(m) in DRAWN) == N:
                    drawn_at, asks_at_draw = time.time() - t0, len(asks) - before
                if drawn_at is not None and len(asks) - before >= want:
                    if all(st.get(m) == '3' for m in marks) or arm in ('warm', 'legacy'):
                        break
            st, disk = pics(cl)
            time.sleep(1); send('screenshot ' + arm); time.sleep(2)
            shots = list((gd / 'screenshots').glob(arm + '.*'))
            results[arm] = dict(drawn_s=drawn_at, asks_at_draw=asks_at_draw, asks=len(asks) - before,
                                disk_hits=disk, states=[st.get(m) for m in marks])
            print('  %s %s' % (arm, json.dumps(results[arm])), flush=True)
            L.check(arm + ': all %d drawn' % N, drawn_at is not None, True)
            L.check(arm + ': rendered quadrants', bool(shots) and P.quadrants(shots[0])[0] > 0, True)
            L.check(arm + ': picture requests', len(asks) - before, want)
            L.check(arm + ': VM errors', [x for x in ('QC VM error', 'Unknown command', 'Cannot call') if x in cl.text()], [])
            if arm in ('warm', 'yesterday', 'legacy'):
                # From disk, not 1.5 s apart: the whole board within 4 s of opening it.
                L.check(arm + ': whole board drawn within 4 s', drawn_at is not None and drawn_at <= 4, True)
                L.check(arm + ': every picture came from the disk', disk, N)
            if arm == 'cold':
                L.check('cold: a file per mark, body persisted',
                        all(p.exists() and p.read_bytes().endswith(body.encode()) for p in path.values()), True)
            if arm == 'yesterday':
                L.check('yesterday: refreshed copies re-dated today',
                        all(p.exists() and p.read_text().splitlines()[0].endswith(today) for p in path.values()), True)
            if arm == 'warm':
                n = len(asks); send('vid_restart'); time.sleep(6); send('closemenu'); time.sleep(3)
                send('scores pics'); time.sleep(1); send('screenshot restart'); time.sleep(2)
                shots = list((gd / 'screenshots').glob('restart.*'))
                L.check('renderer restart: rendered quadrants', bool(shots) and P.quadrants(shots[0])[0] > 0, True)
                L.check('renderer restart: zero picture requests', len(asks) - n, 0)
                L.check('renderer restart: client still running', client.poll() is None, True)
            send('quit')
            try:
                client.wait(timeout=15)
            except subprocess.TimeoutExpired:
                client.terminate(); client.wait(timeout=10)
            client = None
        (a.output_dir / 'results.json').write_text(json.dumps(dict(results=results, failed=L.FAILED), indent=1))
        print('evidence:', rig)
        return 1 if L.FAILED else 0
    finally:
        if client is not None and client.poll() is None: client.terminate(); client.wait(timeout=10)
        if web is not None: web.shutdown()
        for p in junctions:
            if not p.lstat().st_file_attributes & 0x400: raise RuntimeError('not our junction: %s' % p)
            p.rmdir()


if __name__ == '__main__':
    raise SystemExit(main())
