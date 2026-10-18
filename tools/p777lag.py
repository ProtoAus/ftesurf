#!/usr/bin/env python3
"""P777 latency arm: a 1500-disc layout from Alice to Bob with cl_delay_packets on both
clients (the overseas case the review worked out from the engine source). Graded on: Bob
still connected, Bob's received count against Alice's, the server's dropped count, and
"overflow" / "MAX_BACK_BUFFERS" lines in the three logs.

    python tools/p777lag.py --out <dir> --progs <dir> --delay <ms>    (under the rig lock)
"""
import argparse
import json
from pathlib import Path
import re
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p777share as R  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--delay', type=int, default=300)
    ap.add_argument('--port', type=int, default=27619)
    a = ap.parse_args()
    a.content = Path('C:/FTESurf')
    a.client = Path('C:/FTESurf/ftesurf64.exe')
    a.server = Path('C:/FTEQuake/fteqwsv64.exe')
    a.plugin = Path('C:/FTESurf/fteplug_hl2_x64.dll')
    a.out = a.out.resolve()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', a.port))
    a.out.mkdir(parents=True, exist_ok=False)
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set lobby_avatars 1', 'set lobby_av_stream 1',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0', 'set milk_enable 0',
              'set update_autocheck 0']
    peers = []
    res = {'delay': a.delay}
    try:
        base = R.prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set sv_guidkey p777-fixture',
            f'map {R.MAP}', 'wait', 'sv_cheats 1']) + '\n')
        sv = R.Peer(a.server, base, 'probe.cfg', True)
        peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=120)
        sv.send('sv_cheats 1')
        cl = []
        for folder, name in (('alice', 'Alice'), ('bob', 'Bob')):
            base = R.prepare(a, folder)
            (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
                f'name "{name}"', f'connect 127.0.0.1:{a.port}']) + '\n')
            p = R.Peer(a.client, base, 'probe.cfg')
            peers.append(p)
            cl.append(p)
            p.wait('FTESurf CSQC loaded', timeout=120)
            time.sleep(3)
            p.send('menu_restart; ui_close')
            time.sleep(1)
        A, B = cl
        for p in (A, B):
            for line in ('noclip', 'cl_nopred 1', 'paint_size 24', 'paint_alpha 1', 'paint_autoload 0',
                         'paint_color random', 'paint_clear', f'cl_delay_packets {a.delay}'):
                p.send(line)
        A.send(f'setpos {R.O[0]} {R.O[1]} {R.O[2]} 0 0 0')
        B.send(f'setpos {R.O[0] + 300} {R.O[1]} {R.O[2]} 0 180 0')
        time.sleep(4)
        b_ = R.share_status(B).get('me')
        R.block(A, 'paint_fill 1500 50', r'paint: fill', 30)
        la = R.paint_status(A)['live']
        res['alice_live'] = la
        out = R.block(A, 'share status', r'share: pacing', 20)
        m = re.search(r'share: pacing by a (\d+) ms', out)
        res['alice_rtt_ms_before'] = m and int(m[1])
        off_b = len(B.text())
        A.send(f'share layout {b_}')
        time.sleep(3)
        out = R.block(B, 'share status', r'share: received', 20)
        m = re.search(r'offer from (-?\d+) kind (\d+)', out)
        res['bob_offer'] = m and m[0]
        off_a = len(A.text())
        B.send('share yes')
        t0 = time.monotonic()
        for _ in range(10):                 # the pacing as the stream starts
            A.send('share status')
            time.sleep(0.25)
        res['pacing'] = re.findall(r'share: pacing by.*|share: received.*stream to.*|Outgoing message overflow',
                                   A.text()[off_a:])[:30]
        got = None
        while time.monotonic() - t0 < 120:
            m = re.search(r'sent you (\d+) marks(, (\d+) arrived)?', B.text()[off_b:])
            if m:
                got = m[0]
                break
            if B.proc.poll() is not None:
                break
            time.sleep(1)
        res['bob_note'] = got
        out = R.block(A, 'share status', r'share: pacing', 20)
        m = re.search(r'share: pacing by a (\d+) ms', out)
        res['alice_rtt_ms_after'] = m and int(m[1])
        res['stream_s'] = round(time.monotonic() - t0, 1)
        time.sleep(2)
        try:
            res['bob_paint'] = R.paint_status(B)
        except Exception as e:
            res['bob_paint'] = f'no answer: {e}'
        try:
            out = R.block(A, 'cmd share status', r'share: relayed', 20)
            res['relay'] = re.search(r'share: relayed.*', out)[0]
        except Exception as e:
            res['relay'] = f'no answer: {e}'
        res['logs'] = {}
        for name, p in (('server', sv), ('alice', A), ('bob', B)):
            t = p.text()
            res['logs'][name] = [l for l in t.splitlines()
                                 if re.search(r'(?i)overflow|MAX_BACK_BUFFERS|dropped|disconnect|kicked|timed out', l)][-8:]
    finally:
        for p in reversed(peers):
            try:
                p.stop()
            except Exception as e:
                print('stop:', e)
        (a.out / 'lag.json').write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1), flush=True)


if __name__ == '__main__':
    main()
