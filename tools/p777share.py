#!/usr/bin/env python3
"""P777 arm: share paint and saves between two players; paint layouts.

tools/p744spec.py's rig: a dedicated server and two clients (Alice, Bob), each with its
own basedir, config and data root under --out, on surf_dune with lobby bodies streamed.
Keys are WM_KEYDOWN/UP posted to each client's own window. Graded on the subjects' own
lines: `share status` (card, offer, links, received), `paint_status` (placed, received),
the server's relay counters, the save line the server prints, and the two layout files
`paint_save <name>` writes (Alice's discs against what Bob received).

    python tools/p777share.py --out <dir under an OWNER.md root> --progs <dir with the three .dat>

--progs is a build.ps1 -NoDeploy output (rig/build-nodeploy-*); default.cfg comes from the
tree two levels above it. Run it under the rig lock.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
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
MAP = 'surf_dune'
O = (11614.0, 11675.0, 12912.6)     # surf_dune's spawn; a flat wall at x=12032, 418u ahead
CHECKS = []
NOTES = {}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(ok, name, detail=''):
    CHECKS.append({'name': name, 'pass': bool(ok), 'detail': str(detail)[:400]})
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''), flush=True)


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
    shutil.copy2(a.progs.parent.parent / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(a.plugin, base / a.plugin.name)
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP777Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p777-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


def window(pid):
    user = C.WinDLL('user32', use_last_error=True)
    cb = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user.GetWindowThreadProcessId.argtypes = (W.HWND, C.POINTER(W.DWORD))
    found = []

    @cb
    def visit(hwnd, _):
        actual = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, C.byref(actual))
        if actual.value == pid and user.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user.EnumWindows(visit, 0)
    if len(found) != 1:
        raise RuntimeError(f'pid {pid}: {len(found)} visible windows')
    return user, found[0]


def key(peer, vk):
    user, hwnd = window(peer.proc.pid)
    user.MapVirtualKeyW.argtypes = (W.UINT, W.UINT)
    scan = user.MapVirtualKeyW(vk, 0)
    user.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    user.PostMessageW(hwnd, 0x100, vk, 1 | scan << 16)
    time.sleep(0.12)
    user.PostMessageW(hwnd, 0x101, vk, 0xC0000001 | scan << 16)
    time.sleep(0.6)


def block(peer, command, end, timeout=15):
    off = len(peer.text())
    peer.send(command)
    peer.wait(end, off, timeout)
    time.sleep(0.2)
    return peer.text()[off:]


def share_status(peer):
    out = block(peer, 'share status', r'share: received')
    st = {}
    m = re.search(r'share: you are slot (\d+)', out)
    if m:
        st['me'] = int(m[1])
    m = re.search(r'share: painting with (.*?); card (-?\d+), offer from (-?\d+) kind (\d+) n (\d+)', out)
    if m:
        st.update(links=m[1], card=int(m[2]), offer=int(m[3]), kind=int(m[4]))
    m = re.search(r'share: received(.*?); stream to (-?\d+) kind (\d+) at (\d+)/(\d+), (\d+) queued', out)
    if m:
        st.update(rx=m[1].strip(), sto=int(m[2]), sat=int(m[4]), sn=int(m[5]))
    return st


def paint_status(peer):
    out = block(peer, 'paint_status', r'paint: received')
    st = {}
    m = re.search(r'paint: (\d+) live \(max \d+\), placed (\d+)', out)
    if m:
        st.update(live=int(m[1]), placed=int(m[2]))
    m = re.search(r'paint: received (\d+), waiting (\d+), layout (-?\d+), loading (\d+)', out)
    if m:
        st.update(rx=int(m[1]), wait=int(m[2]), layout=int(m[3]))
    return st


def discs(path):
    out = []
    for l in open(path, encoding='utf-8'):
        w = l.split()
        if len(w) == 12 and w[0] == 'd':
            out.append([float(x) for x in w[1:]])
    return out


def run(a, sv, A, B):
    for p in (A, B):
        for line in ('noclip', 'cl_nopred 1', 'paint_size 24', 'paint_alpha 1', 'paint_rate 20',
                     'paint_autoload 0', 'paint_clear'):
            p.send(line)
    A.send(f'setpos {O[0]} {O[1]} {O[2]} 0 0 0')
    B.send(f'setpos {O[0] + 300} {O[1]} {O[2]} 0 180 0')
    time.sleep(3)
    sa, sb = share_status(A), share_status(B)
    a_, b_ = sa.get('me'), sb.get('me')
    check(a_ is not None and b_ is not None and a_ != b_, 'two slots', [a_, b_])

    # The pick and the card, by native keys.
    B.send('share')
    time.sleep(1)
    sb = share_status(B)
    check(sb.get('card') == a_, 'Bob looking at Alice: share opens the card on her', sb.get('card'))
    key(B, 0x31)                                    # 1: paint together
    time.sleep(1)
    sa = share_status(A)
    check(sa.get('offer') == b_ and sa.get('kind') == 1, 'Alice has the live offer', [sa.get('offer'), sa.get('kind')])
    key(A, 0x72)                                    # F3: accept
    time.sleep(1.5)
    sa, sb = share_status(A), share_status(B)
    check('nobody' not in sa.get('links', 'nobody') and 'nobody' not in sb.get('links', 'nobody'),
          'linked both ways', [sa.get('links'), sb.get('links')])

    # Live, both ways: every disc one sprays arrives at the other.
    p0, rb0 = paint_status(A), paint_status(B).get('rx', 0)
    A.send('paint_color random')
    A.send('+paint')
    time.sleep(1.0)
    A.send('-paint')
    time.sleep(1.5)
    p1, rb1 = paint_status(A), paint_status(B).get('rx', 0)
    na = p1['placed'] - p0['placed']
    check(na > 10 and rb1 - rb0 == na, 'Alice sprays: Bob receives every disc', [na, rb1 - rb0])
    B.send(f'setpos {O[0] + 300} {O[1]} {O[2]} 0 0 0')
    time.sleep(2)
    q0, ra0 = paint_status(B), paint_status(A).get('rx', 0)
    B.send('paint_color random')
    B.send('+paint')
    time.sleep(1.0)
    B.send('-paint')
    time.sleep(1.5)
    q1, ra1 = paint_status(B), paint_status(A).get('rx', 0)
    nb = q1['placed'] - q0['placed']
    check(nb > 10 and ra1 - ra0 == nb, 'Bob sprays: Alice receives every disc', [nb, ra1 - ra0])
    out = block(A, 'cmd share status', r'share: relayed')
    NOTES['relay_alice'] = re.search(r'share: relayed.*', out)[0]
    check('dropped 0' in out, 'the relay dropped none', NOTES['relay_alice'])

    # A layout: what Alice has up (hers and Bob's) goes to Bob, who cleared his.
    B.send('paint_clear')
    la = paint_status(A)['live']
    A.send(f'share layout {b_}')
    time.sleep(1.5)
    sb = share_status(B)
    check(sb.get('offer') == a_ and sb.get('kind') == 2, 'Bob has the layout offer', [sb.get('offer'), sb.get('kind')])
    off = len(B.text())
    key(B, 0x72)                                    # F3
    B.wait(r'sent you \d+ marks', off, timeout=max(15, la / 100))
    m = re.search(r'sent you (\d+) marks', B.text()[off:])
    check(m and int(m[1]) == la, 'Bob is told Alice sent all of it', [la, m and m[1]])
    lb = paint_status(B)
    check(lb.get('live', 0) + lb.get('wait', 0) == la, 'Bob now holds Alice\'s paint', [la, lb])
    block(A, 'paint_save p777', r'paint: saved')
    block(B, 'paint_save p777', r'paint: saved')
    fa = a.out / 'alice/ftesurf/data/paint/surf_dune.p777.txt'
    fb = a.out / 'bob/ftesurf/data/paint/surf_dune.p777.txt'
    da, db = sorted(discs(fa)), sorted(discs(fb))
    worst = [0.0, 0.0, 0.0]
    if len(da) == len(db):
        for x, y in zip(da, db):
            worst[0] = max(worst[0], max(abs(x[i] - y[i]) for i in (0, 1, 2)))
            worst[1] = max(worst[1], max(abs(x[i] - y[i]) for i in (3, 4, 5)))
            worst[2] = max(worst[2], max(abs(x[i] - y[i]) for i in (6, 7, 8, 9, 10)))
    check(len(da) == len(db) == la and worst[0] <= 0.011 and worst[1] <= 0.01 and worst[2] <= 0.006,
          'Bob\'s copy matches Alice\'s discs (origin, normal, colour/size/alpha)', [len(da), len(db), worst])

    # A big one: 1500 more discs, streamed at 200 a second over the reliable relay.
    out = block(A, 'paint_fill 1500 50', r'paint: fill', 30)
    la2 = paint_status(A)['live']
    B.send('paint_clear')
    time.sleep(2.5)                                 # Alice's offers are two seconds apart
    A.send(f'share layout {b_}')
    time.sleep(1.5)
    off = len(B.text())
    key(B, 0x72)
    t0 = time.monotonic()
    B.wait(r'sent you \d+ marks', off, timeout=la2 / 150 + 20)
    NOTES['big_stream_s'] = round(time.monotonic() - t0, 1)
    m = re.search(r'sent you (\d+) marks', B.text()[off:])
    lb = paint_status(B)
    check(m and int(m[1]) == la2 and lb.get('live', 0) + lb.get('wait', 0) == la2,
          'a 1500-disc layout arrives whole', [la2, m and m[1], lb, NOTES['big_stream_s']])
    out = block(A, 'cmd share status', r'share: relayed')
    NOTES['relay_alice_big'] = re.search(r'share: relayed.*', out)[0]

    # The layout comes back from its file.
    A.send('paint_clear')
    out = block(A, 'paint_load p777', r'paint: loaded', 20)
    m = re.search(r'paint: loaded (\d+)', out)
    st = paint_status(A)
    check(m and int(m[1]) == la and st.get('live', 0) + st.get('wait', 0) == la, 'Alice reloads her layout',
          [la, m and m[1], st])

    # A save: Alice saves, offers it, Bob takes it.
    out = block(A, 'sl_save', r'save', 10)
    NOTES['alice_save'] = out.strip()[-200:]
    A.send(f'share save {b_}')
    time.sleep(1.5)
    sb = share_status(B)
    check(sb.get('offer') == a_ and sb.get('kind') == 3, 'Bob has the save offer', [sb.get('offer'), sb.get('kind')])
    off = len(B.text())
    key(B, 0x72)
    B.wait(r'share: save', off, 10)
    m = re.search(r'share: save .*', B.text()[off:])
    NOTES['bob_save'] = m and m[0]
    check(m and 'from' in m[0], 'Bob has Alice\'s save as a row', NOTES['bob_save'])
    check('has your save' in A.text(), 'Alice is told he has it')
    out = block(B, 'cmd timer', r'timer', 10)
    NOTES['bob_timer_after_save'] = out.strip()[-300:]

    # No, and no answer.
    off = len(A.text())
    A.send(f'share layout {b_}')
    time.sleep(2.5)
    key(B, 0x73)                                    # F4: decline
    time.sleep(1)
    check('said no' in A.text()[off:], 'a decline reaches Alice')
    off = len(A.text())
    A.send(f'share layout {b_}')                    # within 10 s of a no: refused
    time.sleep(1.5)
    check('a few seconds' in A.text()[off:], 'the same sender waits after a no')
    time.sleep(9)
    off = len(A.text())
    A.send(f'share layout {b_}')
    time.sleep(23)
    check('did not answer' in A.text()[off:], 'an unanswered offer runs out')
    time.sleep(10)                                  # the cooldown after no answer
    sb = share_status(B)
    check(sb.get('offer') == -1, 'Bob\'s card went with it', sb.get('offer'))

    # share_offers 0: an offer is declined unseen.
    B.send('share_offers 0')
    time.sleep(2.5)
    off = len(A.text())
    A.send(f'share layout {b_}')
    time.sleep(2)
    sb = share_status(B)
    check('said no' in A.text()[off:] and sb.get('offer') == -1, 'share_offers 0 declines unseen',
          sb.get('offer'))
    B.send('share_offers 1')

    # Stop: nothing more crosses.
    A.send('share stop')
    time.sleep(1.5)
    sa = share_status(A)
    check('nobody' in sa.get('links', ''), 'stopped', sa.get('links'))
    rb0 = paint_status(B).get('rx', 0)
    A.send('paint_color "255 0 255"')
    A.send('paint')
    time.sleep(1.5)
    check(paint_status(B).get('rx', 0) == rb0, 'after stop Bob receives nothing')

    # A re-link sends Alice's paint again; Bob keeps one copy of it.
    A.send('paint_clear')
    B.send('paint_clear')
    for yaw in (-6, -3, 0, 3, 6):
        A.send(f'setpos {O[0]} {O[1]} {O[2]} 0 {yaw} 0')
        time.sleep(0.7)
        A.send('paint')
        time.sleep(0.3)
    na = paint_status(A)['live']
    seen = []
    for _ in (1, 2):
        time.sleep(2.5)
        A.send(f'share paint {b_}')
        time.sleep(1.5)
        key(B, 0x72)
        time.sleep(3)
        seen.append(paint_status(B)['live'])
        A.send('share stop')
        time.sleep(1.5)
    check(na >= 3 and seen == [na, na], 'a re-link brings Alice\'s paint once, not twice', [na, seen])

    # The pick's miss, and pictures.
    B.send(f'setpos {O[0] + 300} {O[1]} {O[2]} 0 90 0')
    time.sleep(2)
    off = len(B.text())
    B.send('share')
    time.sleep(1)
    check('look at a player' in B.text()[off:], 'Bob looking away: no card')
    B.send(f'setpos {O[0] + 150} {O[1]} {O[2]} 0 0 0')
    time.sleep(2)
    B.send('screenshot p777bob_wall')
    B.send(f'setpos {O[0] + 300} {O[1]} {O[2]} 0 180 0')
    time.sleep(2)
    B.send('share')
    time.sleep(1)
    B.send('screenshot p777bob_card')
    time.sleep(1)
    A.send('share layout %g' % b_)
    time.sleep(1.5)
    B.send('screenshot p777bob_offer')
    time.sleep(1)
    A.send('hud_player')
    time.sleep(1.5)
    A.send('screenshot p777alice_panel')
    time.sleep(1.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--port', type=int, default=27619)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', a.port))
    a.out.mkdir(parents=True, exist_ok=False)
    report = {'utc': datetime.now(timezone.utc).isoformat(),
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': CHECKS, 'notes': NOTES}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set lobby_avatars 1', 'set lobby_av_stream 1',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0', 'set milk_enable 0',
              'set update_autocheck 0']
    peers = []
    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set sv_guidkey p777-fixture',
            f'map {MAP}', 'wait', 'sv_cheats 1']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True)
        peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=120)
        sv.send('sv_cheats 1')
        cl = []
        for folder, name in (('alice', 'Alice'), ('bob', 'Bob')):
            base = prepare(a, folder)
            (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
                f'name "{name}"', f'connect 127.0.0.1:{a.port}']) + '\n')
            p = Peer(a.client, base, 'probe.cfg')
            peers.append(p)
            cl.append(p)
            p.wait('FTESurf CSQC loaded', timeout=120)
            time.sleep(3)
            p.send('menu_restart; ui_close')
            time.sleep(1)
        run(a, sv, cl[0], cl[1])
    finally:
        for p in reversed(peers):
            try:
                p.stop()
            except Exception as e:
                print('stop:', e)
        fails = [c['name'] for c in CHECKS if not c['pass']]
        report['fails'] = fails
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
        print(f'{len(CHECKS) - len(fails)} of {len(CHECKS)} checks passed', flush=True)


if __name__ == '__main__':
    main()
