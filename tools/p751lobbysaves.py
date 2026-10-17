#!/usr/bin/env python3
"""Patch 751: a save made in one lobby is listed, loadable and never overwritten in another.

Two dedicated servers share ONE basedir (and so one data/saves), as the twelve
Pi lobbies do, and both load surf_dune before any save exists.  One client with
a guid walks B -> A -> B -> A:

  B  list           nothing saved, and B's block is now scanned for this guid
  A  save           walk out of the start, then save 1 (slot 001) mid-run
  B  list           subject: 1 saved            control: nothing saved
  B  load           subject: run resumed (A's run.rec read through B's hash)
  B  save           subject: slot 002           control: slot 001, over A's save
  A  list           subject: 2 saved            control: 1 saved

--control runs the same gestures against a build without the patch and expects
the control answers, so the arm is shown to discriminate.  Everything lives under
--out (beneath an OWNER.md); the install's data is never read.  Leave cl_sendguid
alone: 1 hashes the guid with the server's address, two ports are two players.
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

ROOT = Path(__file__).resolve().parents[1]
MAP = 'surf_dune'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Peer:
    def __init__(self, exe, base, cfg, log, server=False):
        self.log = base / 'ftesurf/logs' / (log + '.log')
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             *([] if server else ['-window', '-width', '640', '-height', '480', '-nosound']),
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if server else 0)

    def text(self):
        if not self.log.exists():
            return ''
        return re.sub(r'\^[0-9]', '', self.log.read_text(encoding='utf-8', errors='replace'))

    def send(self, line):
        self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=30):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'owned process exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def query(self, command, pattern, timeout=60):
        offset = len(self.text())
        self.send(command)
        return self.wait(pattern, offset, timeout)

    def stop(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)


def prepare(a, name):
    base = a.out / name
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'models', 'textures', 'sound', 'particles'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('maps/zones/local', 'logs', 'downloads/csprogsvers'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(a.content / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    shutil.copy2(a.content / f'ftesurf/maps/zones/local/{MAP}.json', game / f'maps/zones/local/{MAP}.json')
    shutil.copy2(a.plugin, base / a.plugin.name)
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP751Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p751-unused\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--ports', type=int, nargs=2, default=[27561, 27562])
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    for port in a.ports:
        if not 27520 <= port <= 27620:
            ap.error('use dedicated lobby-range ports')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', port))
    a.out.mkdir(parents=True, exist_ok=False)
    peers, checks = [], []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0']

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        return bool(ok)

    try:
        shared = prepare(a, 'lobbies')
        servers = {}
        for tag, port in (('B', a.ports[1]), ('A', a.ports[0])):
            (shared / f'ftesurf/probe{tag}.cfg').write_text('\n'.join(common + [
                f'log_name probe{tag}', f'sv_port {port}', 'sv_playerslots 4', 'sv_maxclients 4',
                'set sv_guidkey p751-fixture', 'set rec_enable 1', 'set lobby_norec 0',
                'developer 1', 'log_developer 1', f'map {MAP}']) + '\n')
            servers[tag] = Peer(a.server, shared, f'probe{tag}.cfg', f'probe{tag}', True)
            peers.append(servers[tag])
            servers[tag].wait(r'Server spawned\.', timeout=90)
        base = prepare(a, 'client')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            'log_name probe', 'cl_threadedphysics 0', 'name "P751"',
            f'connect 127.0.0.1:{a.ports[1]}']) + '\n')
        cl = Peer(a.client, base, 'probe.cfg', 'probe'); peers.append(cl)

        def visit(tag, first=False):
            port = a.ports[0] if tag == 'A' else a.ports[1]
            offset = len(cl.text())
            if not first:
                cl.send(f'disconnect; connect 127.0.0.1:{port}')
            cl.wait('FTESurf CSQC loaded', offset, timeout=90)
            # Not `cmd viewpos`: a rejoined slot answers with the last visit's
            # origin before the spawn, and commands sent then are dropped.
            cl.wait(r'welcome to World of Surf', offset, timeout=90)
            time.sleep(1)

        def listing(tag):
            m = cl.query('cmd sl_list', r'saveloc: (nothing saved on this map|(\d+) saved on)')
            n = int(m.group(2)) if m.group(2) else 0
            print(f'{tag}: {n} saved', flush=True)
            return n

        def save(tag):
            m = cl.query('cmd sl_save', r'save (\d+) \(slot (\d+)\)')
            print(f'{tag}: save {m.group(1)} slot {m.group(2)}', flush=True)
            return int(m.group(2))

        visit('B', first=True)
        check(listing('B') == 0, "B starts empty and scans this guid's block")
        visit('A')
        cl.send('cmd zone_goto 0')
        time.sleep(1.5)
        cl.send('+forward'); time.sleep(1.2); cl.send('-forward'); time.sleep(0.5)
        state = cl.query('cmd timer', r'timer: (\w+) on').group(1)
        check(state == 'running', f'A: a run is on the clock ({state})')
        rec = cl.query('cmd timer', r'recording (\d+)').group(1)
        check(rec == '1', 'A: the run is recording, so the save has a run.rec')
        check(save('A') == 1, 'A writes slot 001')
        visit('B')
        nb = listing('B')
        loaded = cl.query('cmd sl_load', r'(run resumed at|nothing saved on this map|could not|changed on disk)').group(1)
        print('B load:', loaded, flush=True)
        time.sleep(1)
        slot = save('B')
        visit('A')
        na = listing('A')
        folders = sorted(p.parent.relative_to(shared / 'ftesurf/data/saves').as_posix()
                         for p in (shared / 'ftesurf/data/saves').rglob('state.txt'))
        owners = {f.split('/')[1] for f in folders}
        report['folders'] = folders
        report['b_load'] = loaded
        check(len(owners) == 1, 'one guid folder: both lobbies saw the same player')
        folders = [f.split('/')[-1] for f in folders]
        if a.control:
            check(nb == 0, "control: B does not see A's save")
            check(slot == 1, "control: B reuses slot 001 over A's save")
            check(na == 1, 'control: A still lists one')
            check(folders == ['save001'], "control: one slot folder, A's save written over")
        else:
            check(nb == 1, "B lists A's save")
            check(loaded == 'run resumed at', "B loads it and resumes A's run")
            check(slot == 2, "B takes slot 002, A's 001 kept")
            check(na == 2, "A lists B's save after the rejoin")
            check(folders == ['save001', 'save002'], 'two slot folders on disk')
            # Adoption runs only after a read missed, so these lines are the hash
            # being stale and the cure acting, in the server that read the files.
            adopted = re.findall(r'saveloc: adopted (\S+)', servers['B'].text())
            report['b_adopted'] = adopted
            check(any(p.endswith('/gen.txt') for p in adopted), "B adopted A's gen.txt on the rejoin")
            check(any(p.endswith('save001/state.txt') for p in adopted), "B adopted A's state.txt in the rescan")
    finally:
        for peer in reversed(peers):
            peer.stop()
        (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    ok = checks and all(c['pass'] for c in checks)
    print('P751', 'CONTROL' if a.control else 'SUBJECT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
