#!/usr/bin/env python3
"""P1391 arm: the report panel in a hosted game, sending to a local stand-in for surfd's /api/report.

    python -B tools/p1391report.py --out <dir under an OWNER.md root> --progs <build.ps1 -NoDeploy dir>

The stand-in (127.0.0.1:--port) stores each POST body and answers {"ok":true,"id":N}. The client opens
the panel (`report`), is screenshotted empty and filled in, sends, and prints `report status`.
Graded on the stand-in's copy: valid JSON, the contract's fields, meta keys, and a JPEG that decodes
(FF D8 ... FF D9); and on the client's own lines ("report: received by the service").
Needs the rig lock and an announcement to peers.
"""
import argparse
import base64
import http.server
import json
import threading
import time
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402
import p1384lead as L  # noqa: E402  prepare() (surf_dune fixture)
from spec_chat_smoke import Peer  # noqa: E402

GOT = []


class Stand(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(n)
        GOT.append({'path': self.path, 'type': self.headers.get('Content-Type'), 'body': body})
        out = json.dumps({'ok': True, 'id': len(GOT)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18391)
    ap.add_argument('--url', default='', help='send to this service instead of the local stand-in (e.g. a local reportd)')
    a = ap.parse_args()
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    srv = None
    if not a.url:
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', a.port), Stand)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = a.url or f'http://127.0.0.1:{a.port}/api/report'
    base = L.prepare(a.out, 'client', a.progs, a.progs / 'csprogs.dat')
    game = base / 'ftesurf'
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
              'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0',
              f'set cl_report_url "{url}"', 'name "P1391 Arm"', f'map {L.MAP}']
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    R.take_lock('p1391 report arm (ftesurf-3a)')
    cl = None
    res = {}
    try:
        cl = Peer(L.CONTENT / 'ftesurf64.exe', base, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=180)
        time.sleep(6)
        cl.send('menu_restart; ui_close')
        time.sleep(1.5)
        cl.send('setpos 11614 11675 12913 0 30 0')
        time.sleep(1.5)
        cl.query('bindlist', r'f3|F3', 10)
        cl.send('report')
        time.sleep(2.5)
        cl.send('screenshot p1391_empty.png')
        time.sleep(1.5)
        cl.send('report cat render')
        cl.send('report subject "Glass flickers on the second ramp"')
        cl.send('report body "Looking up at the glass roof after the second ramp, it flickers black about '
                'twice a second. It happens every time from this save. Expected: steady glass like stage 1."')
        time.sleep(1.5)
        cl.send('screenshot p1391_filled.png')
        time.sleep(1.5)
        off = len(cl.text())
        cl.send('report send')
        try:
            cl.wait(r'report\^7: (received by the service|not sent)', off, 30)
        except RuntimeError as e:
            res['wait'] = str(e)[:120]
        time.sleep(0.8)
        cl.send('report status')
        time.sleep(1)
        res['client'] = [l[20:] for l in cl.text()[off:].splitlines() if 'report' in l][:12]
        cl.send('report')               # reopens after the sent close (1.5 s)
        time.sleep(3)
        cl.send('screenshot p1391_again.png')
        time.sleep(1.5)
        cl.send('report')
        time.sleep(1)
        off = len(cl.text())
        cl.send('map surf_dune')        # the next map load rehashes the index fs_flush left stale
        cl.wait(r'fs: maps/surf_dune\.bsp in', off, 120)
        res['reload_fs'] = [l[20:] for l in cl.text()[off:].splitlines() if l[20:].startswith('fs: ')][:2]
        time.sleep(2)
    finally:
        if cl is not None:
            cl.stop()
        R.drop_lock()
        if srv is not None:
            srv.shutdown()
    log = (game / 'logs/probe.log').read_text(encoding='utf-8', errors='replace')
    res['fs_lines'] = [l[20:] for l in log.splitlines() if 'fs: maps/' in l]   # first load vs after fs_flush
    res['posts'] = len(GOT)
    if GOT:
        g = GOT[0]
        res['path'], res['type'], res['bytes'] = g['path'], g['type'], len(g['body'])
        try:
            j = json.loads(g['body'].decode('utf-8'))
            shot = base64.b64decode(j.get('shot', '')) if j.get('shot') else b''
            res['json'] = {k: (v if k not in ('shot', 'meta') else None) for k, v in j.items()}
            res['meta'] = j.get('meta')
            res['shot_bytes'] = len(shot)
            res['shot_jpeg'] = shot[:3] == b'\xff\xd8\xff' and shot[-2:] == b'\xff\xd9'
            (a.out / 'shot.jpg').write_bytes(shot)
        except Exception as e:      # the grade, not a crash
            res['json_error'] = repr(e)
            (a.out / 'body.bin').write_bytes(g['body'])
    shots = sorted(str(p) for p in game.glob('screenshots/*'))
    res['screenshots'] = shots
    (a.out / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
