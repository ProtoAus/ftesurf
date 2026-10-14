#!/usr/bin/env python3
"""Real-client persistent Steam-picture controls; --root is a NEW owned folder.
Fresh client VMs share an isolated rig, never the owner's data/config/processes.
"""
import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
import p615link as L
import p640pics as P


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.output_dir = a.root.resolve(); a.output_dir.mkdir()
    (a.output_dir / 'OWNER.md').write_text('p715pics; current pi.dev task, owned child clients only; retained evidence.\n')
    a.progs = a.progs.resolve()
    rig, gd, junctions = L.build_rig(a)
    client = web = None
    try:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        web, db = L.start_surfd(rig, port, '127.0.0.1')
        S, A = sys.modules['surfd'], sys.modules['accounts']
        import steamsync
        c = sqlite3.connect(db)
        c.execute('INSERT INTO accounts (steamid,name,created_at,avatar) VALUES (?,?,?,?)',
                  (P.SID, 'Pictured', int(time.time()), P.HASH))
        for player, name, ticks in ((P.SID, 'Pictured', 3000), (P.PLAIN, 'Plain', 3100)):
            c.execute("INSERT INTO runs (map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) VALUES ('bhop_eazy',0,0,'ksf','clean',?,?,?,100,?,0,'import',?,?,0)",
                      (player, name, ticks, ticks * 10, 'i-' + player, int(time.time())))
        c.commit(); c.close()
        os.makedirs(S.AVATAR_DIR, exist_ok=True)
        body = steamsync.game_form(P.picture())
        Path(S.AVATAR_DIR, P.HASH + '.jpg').write_bytes(P.picture())
        Path(S.AVATAR_DIR, P.HASH + '.txt').write_text(body, newline='\n')
        S.avatars_reset(); S.people_reset()
        real, asks = S.game_avatar, []
        def avatar(who, now):
            asks.append(time.time()); return real(who, now)
        S.game_avatar = avatar
        origin = 'http://127.0.0.1:%d' % port
        key = hashlib.sha256((origin + '\n' + A.who_of(P.SID)).encode()).hexdigest()
        cache = gd / 'data/cache/steampic' / (key[:2] + '.txt')
        for arm in ('cold', 'warm', 'corrupt', 'expired', 'collision', 'origin', 'nondigit'):
            if arm == 'corrupt': cache.write_bytes(cache.read_bytes()[:110])
            if arm in ('expired', 'collision', 'nondigit'):
                text = cache.read_text()
                if arm == 'expired':
                    lines = text.splitlines(); lines[0] = lines[0][:-8] + '20000101'; text = '\n'.join(lines) + '\n'
                if arm == 'collision': text = text.replace(key, 'f' * 64, 1)
                if arm == 'nondigit':
                    i = text.index('FTESURF-AVATAR 1 32 32\n') + len('FTESURF-AVATAR 1 32 32\n'); text = text[:i] + 'z' + text[i+1:]
                cache.write_text(text, newline='\n')
            before = len(asks)
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 4
            client = subprocess.Popen([str(a.client), '-plugin', '-nobrowse', '-basedir', str(rig),
                '-manifest', str(rig / 'default.fmf'), '+set', 'cfg_save_auto', '0', '+set', 'log_enable', '1',
                '+set', 'log_dir', 'logs', '+set', 'log_name', arm, '-window', '-nosound',
                '+set', 'con_savehistory', '0', '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
                '+set', 'vid_width', '1280', '+set', 'vid_height', '720'], cwd=a.content,
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
            def send(line):
                client.stdin.write(line.encode('ascii') + b'\n'); client.stdin.flush()
            cl = L.Log(gd / ('logs/' + arm + '.log')); time.sleep(8)
            send('map bhop_eazy')
            L.check(arm + ': CSQC loaded', bool(cl.wait('FTESurf CSQC loaded', 45)), True)
            base = origin + ('/' if arm == 'origin' else '')
            send('menu_restart'); send('closemenu'); send('set rec_terms 5'); send('set lobby_dir "%s"' % base)
            time.sleep(1); send('scores open'); send('scores tab online')
            for _ in range(30):
                send('scores pics'); time.sleep(1)
                if 'state 3' in cl.text(): break
            time.sleep(2); send('screenshot ' + arm); time.sleep(2)
            shots = list((gd / 'screenshots').glob(arm + '.*'))
            L.check(arm + ': rendered quadrants', bool(shots) and P.quadrants(shots[0])[0] > 0, True)
            L.check(arm + ': HTTP request count', len(asks) - before, 0 if arm == 'warm' else 1)
            L.check(arm + ': VM errors', [x for x in ('QC VM error', 'Unknown command', 'Cannot call') if x in cl.text()], [])
            if arm == 'cold':
                L.check('cold: validated body persisted', cache.exists() and cache.read_bytes().endswith(body.encode()), True)
                n = len(asks); send('vid_restart'); time.sleep(6); send('closemenu'); time.sleep(3)
                send('scores pics'); send('screenshot restart'); time.sleep(2)
                shots = list((gd / 'screenshots').glob('restart.*'))
                L.check('renderer restart: rendered quadrants', bool(shots) and P.quadrants(shots[0])[0] > 0, True)
                L.check('renderer restart: zero HTTP requests', len(asks) - n, 0)
            send('quit'); client.wait(timeout=15); client = None
        (a.output_dir / 'http.json').write_text(json.dumps(asks)); print('evidence:', rig)
        return 1 if L.FAILED else 0
    finally:
        if client is not None and client.poll() is None: client.terminate(); client.wait(timeout=10)
        if web is not None: web.shutdown()
        for p in junctions:
            if not p.lstat().st_file_attributes & 0x400: raise RuntimeError('not our junction: %s' % p)
            p.rmdir()


if __name__ == '__main__':
    raise SystemExit(main())
