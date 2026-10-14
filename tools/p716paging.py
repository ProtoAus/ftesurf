#!/usr/bin/env python3
"""Real CSQC paging beyond the former 1000-board / 200-profile row limits.
Supply a NEW owned --root, an isolated --progs build and canonical --content.
Existing explicit board/profile controls exercise the real HTTP append paths.
"""
import argparse
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import time
import p615link as L

PLAYER = '76561198000000042'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args(); a.output_dir = a.root.resolve(); a.output_dir.mkdir()
    (a.output_dir / 'OWNER.md').write_text('p716paging fixture; pi.dev current task; owned client only; retain evidence.\n')
    a.progs = a.progs.resolve(); rig, gd, junctions = L.build_rig(a)
    web = client = None
    try:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        web, db = L.start_surfd(rig, port, '127.0.0.1')
        S = sys.modules['surfd']; asks = []
        @S.app.before_request
        def observed():
            if S.request.path == '/api/board': asks.append(dict(S.request.args))
        c = sqlite3.connect(db)
        sql = "INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) VALUES (?,0,0,'ksf','clean',?,'Paging fixture',?,100,?,0,'ksf',?,1000,0)"
        for i in range(1050):
            player = str(int(PLAYER)+i)
            c.execute(sql, ('bhop_eazy', player, 3000+i, 30000+10*i, 'board-%d' % i))
        for i in range(1004):
            c.execute(sql, ('surf_page%d' % i, PLAYER, 3000+i, 30000+10*i, 'profile-%d' % i))
        c.commit(); c.close(); S.people_reset()
        si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 4
        client = subprocess.Popen([str(a.client), '-plugin', '-nobrowse', '-basedir', str(rig), '-manifest', str(rig/'default.fmf'),
            '+set','cfg_save_auto','0','+set','log_enable','1','+set','log_dir','logs','+set','log_name','paging',
            '-window','-nosound','+set','con_savehistory','0','+set','cl_idlefps','0','+set','cl_maxfps','100',
            '+set','vid_width','1280','+set','vid_height','720'], cwd=a.content,
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
        def send(line):
            client.stdin.write(line.encode('ascii')+b'\n'); client.stdin.flush()
        cl = L.Log(gd/'logs/paging.log'); time.sleep(8); send('map bhop_eazy')
        L.check('client spawned', bool(cl.wait('FTESurf CSQC loaded',45)),True)
        send('menu_restart'); send('closemenu'); send('set rec_terms 5'); send('set lobby_dir "http://127.0.0.1:%d"'%port)
        time.sleep(1); send('scores open'); send('scores tab online'); time.sleep(3)
        for i in range(12):
            send('scores more'); time.sleep(.7)
        send('scores status'); time.sleep(1)
        L.check('board holds all1050 rows beyond old1000 cap', 'held 1050 of 10000' in cl.text(), True)
        L.check('server actually served offset1000', any(x.get('offset')=='1000' and not x.get('player') for x in asks),True)
        send('screenshot board1050'); time.sleep(1); send('scores close')
        send('hud_player view '+S.web_handle(PLAYER)); time.sleep(3)
        # Scroll must reach the NEW end after each asynchronous page lands.
        for i in range(70):
            send('hud_player scroll 10000'); time.sleep(.8)
            send('hud_player status'); time.sleep(.15)
            if 'rows 1005/1005' in cl.text(): break
        send('hud_player status'); time.sleep(1)
        L.check('profile holds all1005 rows beyond old200 cap','rows 1005/1005' in cl.text(),True)
        L.check('profile actually requested beyond200',any(x.get('player') and int(x.get('offset','0'))>=200 for x in asks),True)
        L.check('profile demand is queued, no upstream call',sqlite3.connect(db).execute('SELECT state FROM ksfprofiles WHERE player=?',(PLAYER,)).fetchone()[0],'queued')
        send('screenshot profile1005'); time.sleep(2)
        L.check('no VM/unknown-command errors',[x for x in ('QC VM error','Unknown command','Cannot call') if x in cl.text()],[])
        (a.output_dir/'http.json').write_text(__import__('json').dumps(asks,indent=2));print('evidence:',rig)
        send('quit');client.wait(timeout=15);client=None
        return 1 if L.FAILED else 0
    finally:
        if client is not None and client.poll() is None:client.terminate();client.wait(timeout=10)
        if web is not None:web.shutdown()
        for p in junctions:
            if not p.lstat().st_file_attributes & 0x400:raise RuntimeError('not our junction: %s'%p)
            p.rmdir()


if __name__=='__main__':
    raise SystemExit(main())
