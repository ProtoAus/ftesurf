#!/usr/bin/env python3
"""Post-deploy smoke against a LIVE lobby, from an isolated rig.

A fresh client with NO csprogs of its own joins a public lobby, so the client
code it runs is the code that lobby served. Graded on what the subject itself
produced:
  1. the csprogs the engine downloaded hashes to the build that was deployed;
  2. `scores status` prints a drawn board (`cols N   type M`, M > 0);
  3. the log holds no QC error and the cfg reached its end marker.
Map content comes from the same read-only Steam mounts an install uses
(fs_addons.default.txt). Nothing is launched from an install and no owner
config or player data is read. One test player is visible on that lobby for
under a minute, and a window opens on this desktop for as long.

The rig uses the REAL default.fmf: a lobby refuses a client whose PROTOCOLNAME
differs ("Game mismatch"), which is what this tool's first cut measured instead
of the deploy.
Exit 0 pass, 1 a check failed, 2 could not run.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True, help='client exe; fteplug_hl2_x64.dll is taken from beside it')
    p.add_argument('--menu', type=Path, required=True, help='menu.dat (client-local, never served)')
    p.add_argument('--csprogs', type=Path, required=True, help='the csprogs.dat that was deployed; only its hash is used')
    p.add_argument('--addr', default='192.168.1.102:27510', help='lobby host:port (27510 or 27520..27620, never 27698)')
    p.add_argument('--out', type=Path, required=True, help='owned task-root output directory')
    p.add_argument('--wait', type=int, default=45, help='seconds to give the connect, map load and download')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9.-]+:\d+', a.addr) or a.addr.endswith(':27698'):
        p.error('--addr must be a lobby host:port')
    out = a.out.resolve()
    if not any((d / 'OWNER.md').is_file() for d in [out, *out.parents]):
        p.error('--out requires an ancestor OWNER.md')
    plugin = a.engine.parent / 'fteplug_hl2_x64.dll'
    for need in (a.engine, a.menu, a.csprogs, plugin, ROOT / 'default.fmf'):
        if not need.is_file():
            print('CANNOT RUN: missing', need)
            return 2
    want = sha(a.csprogs)

    rig = out / ('pi-lobby-smoke-' + time.strftime('%Y%m%dT%H%M%S'))
    game = rig / 'ftesurf'
    game.mkdir(parents=True)
    (rig / 'PI_SMOKE_RIG.txt').write_text('Owned disposable post-deploy smoke rig. No owner config or player data.\n')
    for folder in ('cfg', 'glsl', 'scripts', 'models', 'gfx', 'textures'):
        if (ROOT / 'ftesurf' / folder).is_dir():
            shutil.copytree(ROOT / 'ftesurf' / folder, game / folder)
    shutil.copy2(ROOT / 'ftesurf/fs_addons.default.txt', game / 'fs_addons.txt')
    shutil.copy2(a.menu, game / 'menu.dat')                 # csprogs.dat is deliberately NOT copied
    shutil.copy2(a.engine, rig / 'ftesurf64.exe')
    shutil.copy2(plugin, rig / plugin.name)                 # Source BSPs need it
    shutil.copy2(ROOT / 'default.fmf', rig / 'default.fmf')
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name pismoke', 'con_notifytime 0',
             'con_notifylines 0', 'developer 0', 'cl_idlefps 0', 'cl_maxfps 100', 'vid_vsync 0',
             'set ui_bootcheck 0', 'set run_resume 0', 'set lobby_dir ""', 'name PiLobbySmoke',
             'waitms 1500', 'menu_restart', 'waitms 800', 'ui_close',
             f'connect {a.addr}', f'waitms {a.wait * 1000}', 'ui_close', 'waitms 500',
             'scores tab local', '+showscores', 'waitms 1500', 'scores status', 'screenshot pismoke_board',
             '-showscores', 'waitms 300', 'echo PISMOKE DONE', 'disconnect', 'waitms 700', 'quit']
    (game / 'pismoke.cfg').write_text('\n'.join(lines) + '\n')
    cmd = [str(rig / 'ftesurf64.exe'), '-basedir', str(rig), '-nohome', '-nosound', '-nocdaudio', '-window',
           '+set', 'vid_width', '1280', '+set', 'vid_height', '720', '+set', 'vid_fullscreen', '0',
           '+set', 'vid_winmaximize', '0', '+set', 'cfg_save_auto', '0', '+exec', 'pismoke.cfg']
    with (rig / 'launch.log').open('w') as log:
        client = subprocess.Popen(cmd, cwd=str(rig), stdout=log, stderr=subprocess.STDOUT)
        try:
            code = client.wait(timeout=a.wait + 105)
        except subprocess.TimeoutExpired:
            client.terminate()                              # only the handle this invocation created
            try:
                client.wait(timeout=10)
            except subprocess.TimeoutExpired:
                client.kill()
                client.wait()
            code = 'TIMEOUT'

    print('Rig', rig)
    print('client exit', code)
    fails = 0

    def check(ok, message):
        nonlocal fails
        fails += not ok
        print(('PASS ' if ok else 'FAIL ') + message)

    logs = list((game / 'logs').glob('pismoke*.log'))
    text = logs[0].read_text(errors='replace') if logs else ''
    if 'Game mismatch' in text or 'PISMOKE DONE' not in text:
        print('CANNOT GRADE: the client never joined or never finished its cfg; read', logs[0] if logs else rig)
        return 2
    held = {f.relative_to(game).as_posix(): sha(f) for f in game.rglob('*.dat') if f.name != 'menu.dat'}
    print('  .dat files the client holds besides menu.dat:', {k: v[:16] for k, v in held.items()})
    check(want in held.values(), 'a csprogs the lobby served hashes to the deployed build ' + want[:16])
    status = re.findall(r'tab (\w+)\s+filter (\w+)\s+cols (\d+)\s+type (\d+)', text)
    print('  scores status lines:', status)
    check(any(int(t) > 0 and int(c) >= 5 for _, _, c, t in status), 'the board drew (cols and type from the last frame)')
    bad = re.findall(r'[^\r\n]*(?:QC runtime error|CSQC_Abort|Menu_Abort|Unknown command "scores")[^\r\n]*', text)
    check(not bad, 'no QC error in the client log' + (': ' + bad[0][:120] if bad else ''))
    check(len(list((game / 'screenshots').glob('pismoke_board.*'))) == 1, 'screenshot captured')
    print('Lobby smoke failures:', fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
