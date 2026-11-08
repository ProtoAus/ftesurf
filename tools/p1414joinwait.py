#!/usr/bin/env python3
"""P1414 arm: the menu's join wait against a slow directory (a 400 ms-ping player's view).

    python -B tools/p1414joinwait.py --out <dir under an OWNER.md root> --progs <dir with the three .dat>
                                     [--delay 1.5] [--switch 12]

A local HTTP directory answers /api/join with "starting" (wait 90) and serves lobbies.json whose one row
switches to the asked map --switch seconds after the ask; every reply is held --delay seconds. The client
(menu only, no map) runs `ui_join surf_p1414`. Graded on the menu's own lines: "has surf_p1414 live now"
(the wait saw the switch) against "never came live" / state 3. The directory's log says how many polls
overlapped. Needs the rig lock.
"""
import argparse
import json
import re
import shutil
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402
import p1384lead as L  # noqa: E402
from spec_chat_smoke import Peer  # noqa: E402

MAP = 'surf_p1414'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--delay', type=float, default=1.5)
    ap.add_argument('--switch', type=float, default=12.0)
    a = ap.parse_args()
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    base = L.prepare(a.out, 'client', a.progs, a.progs / 'csprogs.dat')
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text('version 8\n')

    state = {'join_at': None, 'log': [], 'inflight': 0, 'maxinflight': 0}
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = self.path.split('?')[0]
            t0 = time.monotonic()
            if path not in ('/api/join', '/lobbies.json'):
                self.send_response(404)
                self.end_headers()
                return
            with lock:
                state['inflight'] += 1
                state['maxinflight'] = max(state['maxinflight'], state['inflight'])
                if path == '/api/join' and state['join_at'] is None:
                    state['join_at'] = t0
            time.sleep(a.delay)
            with lock:
                ja = state['join_at']
                live = ja is not None and time.monotonic() - ja >= a.switch
                state['inflight'] -= 1
                state['log'].append((round(t0 - (ja or t0), 2), path, live))
            if path == '/api/join':
                body = {'addr': '127.0.0.1:27999', 'map': MAP, 'state': 'starting', 'wait': 90,
                        'timed': 1, 'why': 'P1414 arm'}
            else:
                body = {'ttl': 30, 'lobbies': [{'name': 'P1414 Lobby', 'map': MAP if live else 'surf_other',
                                                'addr': '127.0.0.1:27999', 'players': 0, 'max': 32, 'age': 1}]}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    srv = ThreadingHTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    (game / 'probe.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
        'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
        f'set lobby_dir "http://127.0.0.1:{port}"', 'set lobby_poll 6', 'set lobby_master ""',
        'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0', 'name "P1414 Arm"']) + '\n')
    res = {'delay': a.delay, 'switch': a.switch}
    R.take_lock('p1414 join wait arm (ftesurf-3a)')
    cl = None
    try:
        cl = Peer(L.CONTENT / 'ftesurf64.exe', base, 'probe.cfg')
        end = time.monotonic() + 120
        while 'menu' not in cl.text().lower() and time.monotonic() < end:
            time.sleep(0.5)
        time.sleep(8)
        off = len(cl.text())
        t_ask = time.monotonic()
        cl.send(f'ui_join {MAP}')
        verdict, t_end = None, None
        while time.monotonic() - t_ask < 60:
            seg = cl.text()[off:]
            if f'has {MAP} live now' in seg:
                verdict, t_end = 'live', time.monotonic()
                break
            if 'never came live' in seg or 'left the directory' in seg or 'did not answer' in seg:
                verdict, t_end = 'failed', time.monotonic()
                break
            time.sleep(0.2)
        time.sleep(1)
        cl.send('ui_join')
        time.sleep(1)
        res['verdict'] = verdict
        res['seconds'] = round(t_end - t_ask, 1) if t_end else None
        res['lines'] = [l[20:] for l in cl.text()[off:].splitlines()
                        if 'online' in l or 'ui_join' in l or 'lobby' in l][:12]
    finally:
        if cl is not None:
            cl.stop()
        R.drop_lock()
        srv.shutdown()
    with lock:
        res['requests'] = state['log']
        res['max_inflight'] = state['maxinflight']
    (a.out / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != 'requests'}, indent=1))
    print('requests:', len(res['requests']), 'lobbies polls:', sum(1 for r in res['requests'] if r[1] == '/lobbies.json'),
          'max in flight:', res['max_inflight'])


if __name__ == '__main__':
    main()
