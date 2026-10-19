#!/usr/bin/env python3
"""Patch 822 falsifier: zone_edit's publish dialog, against a stand-in zone service.

The subject is a TEST BUILD of the patch, made by --make-variant in a scratch worktree:
ZP_BASE points at this script's service on 127.0.0.1, `zone_edit press ze_upload` may
open the dialog (the shipped build takes only a device click there), and a MOUSE1 press
anywhere counts as one on Publish (the free cursor reads the desktop's position, and an
arm must not move the owner's). Signing is untouched: the engine signs only under a
device's press, and this rig's presses are PostMessage keys and buttons on the game's
own window (p615link.Keys), which reach the engine as a device's.

  1 the dialog opens on a challenge and waits on page 2             shot p822_confirm
  2 `zone_edit press zp_go` is refused and posts nothing
  3 a real Esc cancels
  4 reopened, a real Enter signs and posts; the answer page          shot p822_accepted
    (the draft's zones are the saved file's bytes, its nonce the one issued)
  5 OK by command closes it
  6 reopened, a real MOUSE1 press signs and posts (published=1)      shot p822_published
  7 reopened, the service refuses the challenge: Not published       shot p822_refused
    and a real Esc closes it
Each step grades the client's own lines and the bodies the service received.
"""
import argparse
from datetime import datetime, timezone
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p815zones as Z  # noqa: E402

VARIANT = [
    ('src/client/cl_zonepublish.qc', '#define ZP_BASE "https://play.proto.bar/api/zones/"',
     '#define ZP_BASE "http://127.0.0.1:%(port)d/api/zones/"'),
    ('src/client/cl_zoneedit.qc', 'return (strcmp(id, "ze_upload") != 0);', 'return TRUE;'),
    ('src/client/cl_zoneedit.qc', 'ZonePub_Begin(ze_real_t > 0 && cltime - ze_real_t < 0.25);',
     'ZonePub_Begin(TRUE);'),
    ('src/client/cl_zonepublish.qc', 'if (ze_mouse_seen && is_2dpoint_in_bbox(ze_mouse, zp_go_p, zp_go_s)) ZonePub_Go();',
     'if (zp_go_s_x > 0) ZonePub_Go();'),
]


def make_variant(tree, port):
    for rel, old, new in VARIANT:
        p = Path(tree) / rel
        s = p.read_bytes().decode('utf-8')
        if s.count(old) != 1:
            raise SystemExit(f'variant: {rel} does not hold exactly one {old!r}')
        p.write_bytes(s.replace(old, new % {'port': port} if '%(port)' in new else new).encode('utf-8'))
    print('variant written; build it with build.ps1 -NoDeploy and pass its outputs as --progs')


class Service:
    """Answers challenge and draft as zonepub.py's shapes; `script` says how."""
    def __init__(self, port):
        self.got, self.nonces, self.refuse_next = [], [], False
        self.published_next = 0
        svc = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                kind = self.path.rsplit('/', 1)[-1]
                svc.got.append((kind, body))
                if kind == 'challenge':
                    req = json.loads(body)
                    if svc.refuse_next:
                        svc.refuse_next = False
                        out, code = {'ok': 0, 'error': 'Not a zone admin'}, 403
                    else:
                        n = secrets.token_hex(16); svc.nonces.append(n)
                        out, code = {'ok': 1, 'nonce': n, 'map': req['map'], 'sha': req['sha']}, 200
                else:
                    pub = svc.published_next
                    out = {'ok': 1, 'draft': 'x' * 24, 'published': pub,
                           'note': 'Published: lobbies time with these zones from their next map load' if pub
                           else 'Accepted: live once no lobby has had surf_dune loaded for 10 minutes and its runs are verified'}
                    code = 200
                raw = json.dumps(out).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.http = http.server.ThreadingHTTPServer(('127.0.0.1', port), H)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def drafts(self):
        return [json.loads(b) for k, b in self.got if k == 'draft']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--make-variant', type=Path, help='write the test build into this scratch worktree and stop')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--progs', type=Path, help='the TEST build: qwprogs/csprogs/menu.dat')
    ap.add_argument('--tier', type=int, required=True, help="FS_TERMS_ONLINE of that build's source")
    ap.add_argument('--zport', type=int, default=27822)
    ap.add_argument('--port', type=int, default=27592)
    ap.add_argument('--client', type=Path, default=Z.FTESURF / 'ftesurf64.exe')
    ap.add_argument('--plugin', type=Path, default=Z.FTESURF / 'fteplug_hl2_x64.dll')
    a = ap.parse_args()
    if a.make_variant:
        return make_variant(a.make_variant, a.zport)
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(Z.FTESURF / 'tools'))
    import p615link as L
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'checks': [],
              'progs': {p: Z.sha(a.progs / p)[:8] for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')}}
    fails = []

    def check(ok, label, detail=''):
        report['checks'].append([bool(ok), label, detail])
        print(('PASS ' if ok else 'FAIL ') + label + (f'  [{detail}]' if detail else ''), flush=True)
        if not ok:
            fails.append(label)

    svc = Service(a.zport)
    base = Z.prepare(SimpleNamespace(out=a.out, progs=a.progs, plugin=a.plugin), 'host', shipped=Z.ZA)
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text(f'FTESURF-CONSENT 1\nversion {a.tier}\naccepted 20261019-000000\n')
    (game / 'probe.cfg').write_text('\n'.join(Z.COMMON + [
        'set cl_download_zonesrc ""', 'set lobby_enable 0', 'set sv_zones_curated 1',
        f'set sv_port {a.port}', f'map {Z.MAP}']) + '\n')
    cl = Z.Peer(a.client, base, 'probe.cfg')
    at = 0

    def wait(rx, timeout=30):
        nonlocal at
        m = cl.wait(rx, at, timeout)
        at += m.end()
        return m

    def maybe(rx, timeout=8):
        try:
            return wait(rx, timeout)
        except RuntimeError:
            return None

    def shot(name):
        cl.send('screenshot ' + name)
        end = time.time() + 20
        while time.time() < end:
            found = list((game / 'screenshots').glob(name + '.*'))
            if found and found[0].stat().st_size > 0:
                time.sleep(1.0)
                shutil.copy2(found[0], a.out / found[0].name)
                return True
            time.sleep(0.4)
        return False

    def page(n):
        return wait(r'publish dialog page %d, screen ([^,]*), go ([^,]*), cancel ([^\n]*)' % n)

    try:
        wait(r'zones: \d+ on surf_dune', 180)
        keys = L.Keys(cl.proc.pid)
        cl.send('zone_edit'); wait(r'zone_edit: add a zone from the panel')
        cl.send('zone_edit save force'); wait(r'zone_edit: saved \d+ zones to data/maps/zones/local/surf_dune.json')
        saved = (game / 'data/maps/zones/local/surf_dune.json').read_bytes()

        # 1
        cl.send('zone_edit press ze_upload')
        wait(r'publish dialog open for surf_dune'); wait(r'publish dialog waiting for Publish or Cancel')
        m = page(2)
        report['confirm_rect'] = m.groups()
        check(shot('p822_confirm'), '1 the confirm page opens and is on screen', ' '.join(m.groups()))
        # 2
        n0 = len(svc.drafts())
        cl.send('zone_edit press zp_go')
        refused = maybe(r'a command cannot publish')
        time.sleep(1.5)
        check(refused and len(svc.drafts()) == n0, '2 a command on Publish is refused and posts nothing')
        # 3
        keys.press('esc')
        check(maybe(r'zone upload cancelled; nothing sent') and maybe(r'publish dialog closed'),
              '3 a real Esc cancels and closes')
        # 4
        cl.send('zone_edit press ze_upload'); wait(r'publish dialog waiting'); page(2)
        keys.press('enter')
        sent = maybe(r'upload sent, signed under a real press', 10)
        ans = maybe(r'upload answered: Accepted', 10)
        page(4)
        d = svc.drafts()
        ok = bool(sent and ans and len(d) == n0 + 1)
        if ok:
            env = d[-1]
            zones_raw = svc.got[-1][1].split(b'"zones":', 1)[1][:-1]
            saved = (game / 'data/maps/zones/local/surf_dune.json').read_bytes()   # as Begin re-saved it
            ok = env['nonce'] == svc.nonces[-1] and zones_raw == saved and all(env.get(k) for k in ('pub', 'sig', 'game'))
        check(ok, '4 a real Enter signs and posts the saved bytes under the issued nonce')
        check(shot('p822_accepted'), '4 the Accepted page is on screen')
        # 5
        cl.send('zone_edit press zp_go')
        check(maybe(r'publish dialog closed'), '5 OK closes the answer page')
        # 6
        svc.published_next = 1
        cl.send('zone_edit press ze_upload'); wait(r'publish dialog waiting'); page(2)
        n1 = len(svc.drafts())
        u = keys.u
        u.PostMessageW(keys.hwnd, 0x0200, 0, 0)                      # WM_MOUSEMOVE
        u.PostMessageW(keys.hwnd, 0x0201, 1, 0); time.sleep(0.08)    # WM_LBUTTONDOWN, MK_LBUTTON
        u.PostMessageW(keys.hwnd, 0x0202, 0, 0)                      # WM_LBUTTONUP
        sent = maybe(r'upload sent, signed under a real press', 10)
        ans = maybe(r'upload answered: Published', 10)
        if sent or len(svc.drafts()) > n1:
            page(4)
            check(sent and ans and len(svc.drafts()) == n1 + 1, '6 a real MOUSE1 press signs and posts')
            check(shot('p822_published'), '6 the Published page is on screen')
            cl.send('zone_edit press zp_go'); maybe(r'publish dialog closed')
        else:
            report['checks'].append([None, '6 NOT MEASURED: the posted click did not reach the game', ''])
            print('---- 6 NOT MEASURED: the posted click did not reach the game', flush=True)
            keys.press('esc'); maybe(r'publish dialog closed')
        # 7
        svc.refuse_next = True
        cl.send('zone_edit press ze_upload')
        check(maybe(r'upload answered: Refused: update the game, link your Steam account'),
              '7 a 403 refusal is answered in words (the reply body never reaches QC)')
        page(4)
        check(shot('p822_refused'), '7 the Not published page is on screen')
        keys.press('esc')
        check(maybe(r'publish dialog closed'), '7 a real Esc closes it')
        t = cl.text()
        check(not re.search(r'(?i)qc (error|crash)|stack overflow|runaway|exceeds MAX_ACTION_ELEMENTS', t),
              'no QC faults, and the dialog fit in SUI\'s element cap')
    except RuntimeError as e:
        check(False, 'the arm ran to the end', str(e)[:200])
    finally:
        cl.stop()
        svc.http.shutdown()
        report['service'] = [[k, len(b)] for k, b in svc.got]
        log = game / 'logs/probe.log'
        if log.exists():
            shutil.copy2(log, a.out / 'client-probe.log')
        shutil.rmtree(base)
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
        print('report', a.out / 'report.json', 'failures', len(fails), flush=True)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
