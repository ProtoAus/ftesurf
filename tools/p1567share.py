#!/usr/bin/env python3
"""P1567 arm: a shared save carries its run; loading it makes the run "with help".

P777's rig (tools/p744spec.py's shape): a dedicated server and two clients, Alice and Bob,
each with its own basedir, config and data root under --out, on surf_dune with lobby saves
(one @guid folder each). Keys are WM_KEYDOWN/UP posted to each client's own window.

Graded on the subjects' own lines and files: the share lines both players get, the copied
state.txt (`helped`, `recserial 0`) and run.rec (Alice's bytes) in Bob's folder, Bob's
client sidecars absent from the gift slot (Alice's own save has hers), `cmd timer`'s class
after Bob loads it ("with help"), Bob's next save (flags carry TF_HELPED, `takeover <ticks>
Bob` right after `resume`), reccheck's note of the takeover, and the replay's own line.

--progs of a build without P1567 is the control: the gift arrives as a position-only row.

    python tools/p1567share.py --out <dir under an OWNER.md root> --progs <dir with the three .dat>
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
TF_HELPED = 1048576
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
    (game / 'data/parts').mkdir()                   # a lobby streams its runs here (SV_RecPartPath)
    (game / 'data/consent.txt').write_text('version 4\n')
    (game / 'downloads/csprogsvers').mkdir(parents=True)
    shutil.copy2(a.content / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    shutil.copy2(a.content / f'ftesurf/maps/zones/local/{MAP}.json', game / f'maps/zones/local/{MAP}.json')
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(a.plugin, base / a.plugin.name)
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP1567Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p1567-unused\n'
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
    time.sleep(0.3)
    return peer.text()[off:]


def me(peer):
    out = block(peer, 'share status', r'share: received')
    m = re.search(r'share: you are slot (\d+)', out)
    return int(m[1]) if m else None


def share_offer(peer):
    out = block(peer, 'share status', r'share: received')
    m = re.search(r'offer from (-?\d+) kind (\d+)', out)
    return (int(m[1]), int(m[2])) if m else (None, None)


def timer(peer):
    return block(peer, 'cmd timer', r'class: ', 10)


def start_and_save(peer, srv):
    """Walk out of the start zone and save at once: surf_dune's start drops onto a ramp that slides
    back into the zone, which cancels the run. A cancelled run's recording closes for a few seconds
    (SV_HeldPump), and a run started inside that has none, so each try waits and the save only counts
    when the server wrote its run.rec. -> the save line."""
    for move in ('forward', 'back', 'moveleft', 'moveright'):
        for dur in (0.6, 1.0, 1.6):
            peer.send('goto_start')
            time.sleep(6)
            peer.send(f'+{move}')
            time.sleep(dur)
            peer.send(f'-{move}')
            out = block(peer, 'sl_save', r'save \S+ \(slot', 10)
            line = re.search(r'save \S+ \(slot.*', out)
            time.sleep(1.5)
            if line and 'no run' not in line[0]:
                newest = max(saves(srv), key=lambda p: p.stat().st_mtime, default=None)
                if newest and (newest.parent / 'run.rec').exists():
                    return line[0]
                NOTES.setdefault('alice_no_rec', []).append(line[0])
    return None


def saves(base):
    return sorted((base / 'ftesurf/data/saves' / MAP).glob('@*/save*/state.txt'))


def run(a, sv, A, B):
    a_, b_ = me(A), me(B)
    check(a_ is not None and b_ is not None and a_ != b_, 'two slots', [a_, b_])

    line = start_and_save(A, a.out / 'server')
    NOTES['alice_save'] = line
    check(line is not None, 'Alice saves during a run (left the start zone on foot)', line)
    if line is None:
        return
    time.sleep(2.5)                                 # offers are two seconds apart

    A.send(f'share save {b_}')
    time.sleep(1.5)
    frm, kind = share_offer(B)
    check(frm == a_ and kind == 3, 'Bob has the save offer', [frm, kind])
    off = len(B.text())
    key(B, 0x72)                                    # F3
    B.wait(r'share: save', off, 10)
    line = re.search(r'share: save .*', B.text()[off:])[0]
    NOTES['bob_gift_line'] = line
    check('with their run' in line, 'Bob is told the save came with its run', line)
    time.sleep(1)
    check('has your save and its run' in A.text(), 'Alice is told it went with its run')

    srv = a.out / 'server'
    states = saves(srv)
    gift = [p for p in states if 'helped ' in p.read_text(errors='replace')]
    check(len(gift) == 1, 'one state.txt on the server says helped', [str(p.relative_to(srv)) for p in states])
    if gift:
        g = gift[0]
        text = g.read_text(errors='replace')
        m = re.search(r'^helped (\d+) (.*)$', text, re.M)
        check(m and m[2] == 'Alice', 'the gift names its sender', m and m[0])
        check(re.search(r'^recserial 0$', text, re.M) is not None, 'the gift never warm-loads (recserial 0)')
        alice = [p for p in states if p.parent.parent != g.parent.parent and (p.parent / 'run.rec').exists()]
        same = [p for p in alice if sha(p.parent / 'run.rec') == sha(g.parent / 'run.rec')]
        check(len(same) == 1, "the gift's run.rec is one of Alice's, byte for byte", [str(p) for p in alice])
        alice = same
        slot = g.parent.name
        root = g.parent.parent.name
        bob_side = a.out / 'bob/ftesurf/data/saves' / MAP / root / slot
        left = sorted(p.name for p in bob_side.glob('*')) if bob_side.exists() else []
        check(not any(n in left for n in ('seq.txt', 'trail.txt', 'run.view')),
              "Bob's client wrote none of its own sidecars into the gift slot", left)
        if alice:
            al_side = a.out / 'alice/ftesurf/data/saves' / MAP / alice[0].parent.parent.name / alice[0].parent.name
            NOTES['alice_sidecars'] = sorted(p.name for p in al_side.glob('*')) if al_side.exists() else []

    # Bob loads it: the run is his now, with help.
    # One line, one server frame: Alice's save is 0.1 s past the start, and surf_dune's ramp slides a
    # loaded body back into the start zone (which cancels the run) about a second later.
    B.send('sl_load')
    time.sleep(0.4)
    out = block(B, 'cmd timer; sl_save', r'save \S+ \(slot', 15)
    NOTES['bob_load_timer_save'] = out.strip()[-1500:]
    check(re.search(r'timer\^?7?: running', out) is not None and 'class: with help' in out,
          "Bob's loaded run is running and reads 'with help'",
          (re.search(r'class: .*', out) or [''])[0])
    time.sleep(1.5)
    states2 = [p for p in saves(srv) if p not in states]
    check(len(states2) == 1, "Bob's own save after the load", [str(p) for p in states2])
    if states2:
        st = states2[0].read_text(errors='replace')
        m = re.search(r'^flags (\d+)$', st, re.M)
        check(m and int(m[1]) & TF_HELPED, "Bob's save carries TF_HELPED in flags", m and m[0])
        rec = (states2[0].parent / 'run.rec').read_text(errors='replace').splitlines()
        ho = [i for i, l in enumerate(rec) if l.startswith('takeover ')]
        check(len(ho) == 1 and rec[ho[0]].endswith(' Bob') and rec[ho[0] - 1].startswith('resume '),
              "the run's recording names Bob from the resume on", [rec[i - 1:i + 1] for i in ho])
        rc = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/reccheck.py'), '-v', str(states2[0].parent / 'run.rec')],
                            capture_output=True, text=True)
        NOTES['reccheck'] = (rc.stdout + rc.stderr)[-1500:]
        m = re.search(r'taken_over_by\s+(.*)', rc.stdout)
        check(m and m[1].strip() == 'Bob', 'reccheck reports the takeover (-v)', m and m[0])

        # The replay names who ran which part.
        dst = a.out / 'bob/ftesurf/data/p1567'
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(states2[0].parent / 'run.rec', dst / 'run.rec')
        B.send('fs_flush')                          # the file list was taken before the copy
        time.sleep(1)
        off = len(B.text())
        B.send('replay data/p1567/run.rec')
        try:
            B.wait(r'replay: with help', off, 15)
        except RuntimeError:
            pass
        m = re.search(r'replay: with help.*', B.text()[off:])
        check(m and 'last to Bob' in m[0], "the replay says who it passed to", m and m[0])
        time.sleep(2)
        B.send('screenshot p1567_replay')
        time.sleep(1.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--port', type=int, default=27667)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTESurf/fteqwsv64.exe'))
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
              'set lobby_enable 1', 'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0',
              'set milk_enable 0', 'set update_autocheck 0']
    peers = []
    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set sv_guidkey p1567-fixture',
            'set lobby_norec 0', 'set developer 1', f'map {MAP}']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True)
        peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=120)
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
