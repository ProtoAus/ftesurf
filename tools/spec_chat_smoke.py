#!/usr/bin/env python3
"""Acted dedicated-socket !spec control/subject, isolated from player data.

--out must be fresh and beneath this session's OWNER.md. --progs selects the
exact clean build output. --control expects aliases to remain ordinary chat,
then proves the existing console spectate route works. No test-only QC ships.
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
import time

from test_ui_modern import make_map

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Peer:
    def __init__(self, exe, base, cfg, server=False):
        self.log = base / 'ftesurf/logs/probe.log'
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             *([] if server else ['-window', '-width', '640', '-height', '480', '-nosound']),
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if server else 0)
        (base / 'owned-pid.txt').write_text(str(self.proc.pid) + '\n')

    def text(self):
        return self.log.read_text(encoding='utf-8', errors='replace') if self.log.exists() else ''

    def send(self, line):
        self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=25):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'owned process exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def query(self, command, pattern, timeout=25):
        offset = len(self.text())
        self.send(command)
        return self.wait(pattern, offset, timeout)

    def status(self):
        return self.query('spectate status', r'spectate: stat (-?\d+) ').group(1)

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
    for folder in ('cfg', 'maps', 'logs'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    models = a.content / 'ftesurf/models'
    if models.is_dir():
        shutil.copytree(models, game / 'models')
    (game / 'maps/spec_chat.map').write_text(make_map())
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfSpecChatFixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG spec-unused\n')
    subprocess.run(['python', str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--port', type=int, default=27615)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    if not 27520 <= a.port <= 27620:
        ap.error('use a dedicated lobby-range port')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', a.port))
    a.out.mkdir(parents=True, exist_ok=False)
    peers = []
    checks = []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set lobby_avatars 1', 'set lobby_av_stream 1',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0']

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            raise AssertionError(name)

    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4',
            'developer 1', 'log_developer 1', 'map spec_chat.map']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.')
        clients = []
        for folder, name in [('watcher', 'Watcher'), ('proto', '^2Proto Player'), ('other', 'Proton')]:
            base = prepare(a, folder)
            (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
                'cl_threadedphysics 0', f'name "{name}"',
                f'connect 127.0.0.1:{a.port}']) + '\n')
            cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl); clients.append(cl)
            cl.wait('FTESurf CSQC loaded')
            time.sleep(2)
            cl.query('menu_restart; ui_close; cmd viewpos', r'setpos 0\.0 0\.0 (?!0\.0)[-\d.]+')
        watcher, proto, other = clients
        time.sleep(2)
        check(watcher.status() == '0', 'spawned watcher starts outside spectate')
        if a.control:
            pos = len(watcher.text())
            watcher.send('say !spec')
            watcher.wait(r'Watcher\^7: !spec', pos)
            check(watcher.status() == '0', 'pre-change bare alias is chat, not spectate')
            pos = len(watcher.text())
            watcher.send('say !spec proto')
            watcher.wait(r'Watcher\^7: !spec proto', pos)
            check(watcher.status() == '0', 'pre-change named alias is chat, not spectate')
            watcher.send('spectate next')
        else:
            watcher.send('say !spec')
        time.sleep(1)
        check(int(watcher.status()) > 0, 'bare entry ACTS (console control / chat subject)')
        watcher.send('spectate off' if a.control else 'say !spec')
        time.sleep(.3)
        # Patch 784: run_spec_countdown 0 by default, so the leave lands at once (<= 0).
        check(int(watcher.status()) <= 0, 'leave ACTS (straight back, or through a countdown)')
        time.sleep(4)
        check(watcher.status() == '0', 'leave restores own body')
        if a.control:
            return

        for command, pattern in [
            ('say !spec PrOtO PLaYeR', r'target slot \d+ \(.*Proto Player'),
            ('cmd say !spec proto player', r'target slot \d+ \(.*Proto Player'),
            ('say_team !spec proto player', r'target slot \d+ \(.*Proto Player'),
        ]:
            watcher.send(command)
            time.sleep(.7)
            watcher.query('spectate status', pattern)
            check(int(watcher.status()) > 0, command + ' selects exact multiword coloured name')
            watcher.send('say !spec off')
            time.sleep(4)
            check(watcher.status() == '0', 'explicit off returns safely')
        other.send('name Other')
        time.sleep(.5)
        watcher.send('say !spec proto')
        time.sleep(.7)
        watcher.query('spectate status', r'target slot \d+ \(.*Proto Player')
        check(int(watcher.status()) > 0, 'unique case-insensitive name prefix selects Proto Player')
        # Restore ambiguity while watching: a refusal must not switch/leave.
        other.send('name Proton')
        time.sleep(.7)
        before = watcher.status()
        for command, pattern in [
            ('say !spec proto', 'matches more than one player'),
            ('say !spec MissingPlayer', 'nobody called'),
            ('say !spec watcher', 'you cannot watch yourself'),
            ('say !spec missing;echo SPEC_SPLIT_SENTINEL', 'nobody called'),
        ]:
            # Semicolon case is submitted as one wire chat argument, not local commands.
            if 'SENTINEL' in command:
                command = 'cmd say "!spec missing;echo SPEC_SPLIT_SENTINEL"'
            watcher.query(command, pattern)
            check(watcher.status() == before, command + ' refuses without changing target')
        check('Execing' not in watcher.text()[-200:] and
              not re.search(r'(?m)^\S+ \S+ SPEC_SPLIT_SENTINEL\s*$', watcher.text()),
              'quoted chat tail cannot split into an extra command')
        watcher.send('say !spec off'); time.sleep(4)
        check(watcher.status() == '0', 'final off releases spectate')
        watcher.query('say ordinary-spec-chat-check', r'Watcher\^7: ordinary-spec-chat-check')
        check(True, 'ordinary chat still broadcasts')
        watcher.query('say !spectacular proto', r'Watcher\^7: !spectacular proto')
        check(True, 'other exclamation commands still broadcast')
        check(not re.search(r'Watcher\^7: !spec(?: |$)', watcher.text()),
              'handled aliases are not broadcast to chat')
        for peer in (other, proto):
            peer.stop()
        time.sleep(1)
        server_offset = len(sv.text())
        watcher.send('say !SPEC')
        sv.wait(r'Client command: say "!SPEC"', server_offset)
        time.sleep(.5)
        watcher.query('spectate status', r'spectate: stat 0  mode .* asking 0  leaving 0  offered 1')
        check(not re.search(r'Watcher\^7: !SPEC', watcher.text()),
              'uppercase alias with no targets is handled without a pending camera request')
        for peer in peers:
            check(not any(bad in peer.text() for bad in ('Unknown command', 'QC VM error', 'stack overflow')),
                  peer.log.parent.parent.parent.name + ' has no command/VM errors')
    finally:
        for peer in reversed(peers):
            peer.stop()
        report['stopped_owned_processes'] = all(p.proc.poll() is not None for p in peers)
        (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
