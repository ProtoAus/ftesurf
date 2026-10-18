#!/usr/bin/env python3
"""Patch 815 falsifier: which zone table a client and a hosted game load.

Three versions of surf_dune's zones differ only in the end zone's height:
  A  the shipped library copy (ftesurf/maps/zones/local), as in a release install
  B  the PUBLISHED copy: the lobby's zones/local, and what the zone mirror serves
  C  this install's own saved edit (data/maps/zones/local)
The client also holds B as its Momentum online copy (behind the shipped A in the load
order) and fetches nothing (cl_download_zonesrc ""): the address is fixed in code.

  lobby   dedicated server holds B; client holds A (+ B online).  Subject: the client
          switches to B ("..., the server's table").  Control (old csprogs): stays on A.
  own     as lobby, the client also holds C.  Must keep C: an own edit is never replaced.
  nomatch as lobby without the online B.  Must stay on A: no copy matches the server.
  hosted  listen game; data/maps/zones/curated holds B, the shipped A.  Subject: the hosted
          server and client both load B.  Control: A.

Each arm grades the subject's own lines: `zones(sv): ... crc X` (developer) and the
client's `zones: ... crc X[, the server's ...]`, against crcs printed by a calibration load.
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

FTESURF = Path('C:/FTESurf')
MAP = 'surf_dune'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variant(height):
    d = json.loads((FTESURF / f'ftesurf/maps/zones/local/{MAP}.json').read_text())
    d['tracks']['main']['zones']['end']['regions'][0]['height'] = height
    return (json.dumps(d, indent=2) + '\n').encode()


ZA, ZB, ZC = variant(400), variant(480), variant(560)


class Peer:
    def __init__(self, exe, base, cfg, server=False):
        self.log = base / 'ftesurf/logs/probe.log'
        si = None
        if not server:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 4
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             *([] if server else ['-window', '-width', '640', '-height', '480', '-nosound']),
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW if server else 0)

    def text(self):
        if not self.log.exists():
            return ''
        return re.sub(r'\^[0-9]', '', self.log.read_text(encoding='utf-8', errors='replace'))

    def send(self, line):
        self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=60):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'owned process exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def stop(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)


def prepare(a, name, shipped=None, own=None, curated=None, online=None, plugin=None):
    base = a.out / name
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'models', 'textures', 'sound', 'particles'):
        if (FTESURF / 'ftesurf' / folder).is_dir():
            shutil.copytree(FTESURF / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (FTESURF / 'ftesurf/gfx' / folder).is_dir():
            shutil.copytree(FTESURF / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for d in ('maps/zones/local', 'maps/zones/online', 'logs', 'data/maps/zones/local', 'data/maps/zones/curated', 'downloads/csprogsvers'):
        (game / d).mkdir(parents=True, exist_ok=True)
    (game / 'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion 7\naccepted 20261019-000000\n')
    shutil.copy2(FTESURF / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    if shipped is not None:
        (game / f'maps/zones/local/{MAP}.json').write_bytes(shipped)
    if own is not None:
        (game / f'data/maps/zones/local/{MAP}.json').write_bytes(own)
    if online is not None:
        (game / f'maps/zones/online/{MAP}.json').write_bytes(online)
    if curated is not None:
        (game / f'data/maps/zones/curated/{MAP}.json').write_bytes(curated)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    plugin = plugin or a.plugin
    shutil.copy2(plugin, base / plugin.name)
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP815Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p815-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(FTESURF / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


COMMON = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
          'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
          'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""', 'set lobby_enable 1',
          'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0',
          'developer 1', 'log_developer 1']
CLZ = re.compile(r'zones: \d+ on surf_dune \(([^)]*)\) crc ([0-9a-f]{8})([^\n]*)')
SVZ = re.compile(r'zones\(sv\): \d+ on surf_dune \(([^)]*)\) crc ([0-9a-f]{8})')


def lines(text, rx):
    return [m.groups() for m in rx.finditer(text)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--arm', choices=('calib', 'lobby', 'own', 'nomatch', 'hosted'), required=True)
    ap.add_argument('--port', type=int, default=27591)
    ap.add_argument('--client', type=Path, default=FTESURF / 'ftesurf64.exe')
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--plugin', type=Path, default=FTESURF / 'fteplug_hl2_x64.dll')
    ap.add_argument('--cplugin', type=Path, help="the client's hl2 plugin (an older --client needs its own)")
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'arm': a.arm,
              'progs': {p: sha(a.progs / p)[:8] for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client)[:8], 'server': sha(a.server)[:8],
              'cplugin': sha(a.cplugin or a.plugin)[:8]}
    peers = []
    try:
        if a.arm in ('calib', 'hosted'):
            # calib: three hosted loads, own edit only, to learn each version's crc.
            plan = [('A', ZA), ('B', ZB), ('C', ZC)] if a.arm == 'calib' else [('hosted', None)]
            for tag, body in plan:
                kw = dict(own=body) if a.arm == 'calib' else dict(shipped=ZA, curated=ZB)
                base = prepare(a, 'host-' + tag, **kw)
                (base / 'ftesurf/probe.cfg').write_text('\n'.join(COMMON + [
                    'set cl_download_zonesrc ""', 'set lobby_enable 0',     # a hosted game is not a lobby
                    'set sv_zones_curated %d' % (a.arm == 'hosted'),       # what the picker's Play sets
                    'set sv_port %d' % a.port, f'map {MAP}']) + '\n')
                cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl)
                cl.wait(r'zones: \d+ on surf_dune', timeout=180)
                time.sleep(2)
                t = cl.text()
                report[tag] = {'client': lines(t, CLZ), 'server': lines(t, SVZ)}
                print(tag, json.dumps(report[tag]), flush=True)
                cl.stop(); peers.remove(cl)
        else:
            sbase = prepare(a, 'server', shipped=ZB)
            (sbase / 'ftesurf/probe.cfg').write_text('\n'.join(COMMON + [
                f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set sv_guidkey p815-fixture',
                f'map {MAP}']) + '\n')
            sv = Peer(a.server, sbase, 'probe.cfg', True); peers.append(sv)
            sv.wait(r'Server spawned\.', timeout=120)
            report['server'] = lines(sv.text(), SVZ)
            cbase = prepare(a, 'client', shipped=ZA, own=ZC if a.arm == 'own' else None, plugin=a.cplugin,
                            online=None if a.arm == 'nomatch' else ZB)
            (cbase / 'ftesurf/probe.cfg').write_text('\n'.join(COMMON + [
                'set cl_download_zonesrc ""', 'name "P815"', f'connect 127.0.0.1:{a.port}']) + '\n')
            cl = Peer(a.client, cbase, 'probe.cfg'); peers.append(cl)
            cl.wait('FTESurf CSQC loaded', timeout=180)
            cl.wait(r'zones: \d+ on surf_dune', timeout=60)
            time.sleep(4)
            t = cl.text()
            report['client'] = lines(t, CLZ)
            report['refreshed'] = re.findall(r'zones: refreshed cache for (\S+)', t)
            report['serverinfo_zonecrc'] = re.findall(r'zonecrc\s+(\S+)', t)
            (a.out / 'client.txt').write_text(t)
            print(json.dumps({k: report[k] for k in ('server', 'client', 'refreshed')}), flush=True)
    finally:
        for p in peers:
            p.stop()
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
        for d in a.out.iterdir():
            if d.is_dir():
                log = d / 'ftesurf/logs/probe.log'
                if log.exists():
                    shutil.copy2(log, a.out / f'{d.name}-probe.log')
                shutil.rmtree(d)
        print('report', a.out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
