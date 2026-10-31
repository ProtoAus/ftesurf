#!/usr/bin/env python3
"""Bounded native visual smoke. Real dedicated socket, product CSQC and menu.

Only SSQC has a synthetic capability/bootstrap command, compiled as a shadow
file. A loopback mock exercises real SSQC poll/equip HTTP, callback, private
state and public *kit -> CSQC. Authentication is covered by test_inventory.py,
not this mock. It also asserts that the shipped roster requests inventory.
Never deploy the fixture qwprogs. No install/player-data writes or game kills.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import threading
from urllib.parse import parse_qs, urlsplit
from test_ui_modern import make_map

ROOT = Path(__file__).resolve().parents[1]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--artifacts', required=True, type=Path)
    ap.add_argument('--client', default=Path('C:/FTESurf/ftesurf64.exe'), type=Path)
    ap.add_argument('--server', default=Path('C:/FTEQuake/fteqwsv64.exe'), type=Path)
    a = ap.parse_args()
    out = a.out.resolve()
    if os.name != 'nt' or not any((p / 'OWNER.md').is_file() for p in (out, *out.parents)):
        ap.error('Windows and owned --out required')
    out.mkdir(exist_ok=True)
    if (out / 'report.json').exists() or (out / 'server-launch.log').exists():
        raise RuntimeError('retained launched arm: inspect it before another launch')
    src = ROOT / 'src'
    game = out / 'ftesurf'
    game.mkdir(exist_ok=True)
    (game / 'cfg').mkdir(exist_ok=True)
    (game / 'cfg/default.cfg').write_text('cfg_save_auto 0\n')
    (game / 'maps').mkdir(exist_ok=True)
    (game / 'maps/inventory_smoke.map').write_text(make_map())
    # Catalogue-only subjects: the menu never loads these deliberately invalid BSPs.
    names = ('surf_inventory_fixture', 'bhop_inventory_fixture', 'kz_inventory_fixture', 'inventory_other_fixture')
    (game / 'data').mkdir(exist_ok=True)
    (game / 'data/mapdl.txt').write_text('FTESURF-MAPDL 1\n' + ''.join(
        f'dl {name} {name.split("_")[0]} m 1 100 2026-10-31 0 1 0\n' for name in names))
    for name in names:
        (game / 'maps' / (name + '.bsp')).write_bytes(b'menu-only fixture, never load\n')
    # Read-only content copies only. No player data, maps library or full install.
    assets = Path('C:/FTESurf/ftesurf')
    for folder in ('glsl', 'scripts', 'gfx/fonts'):
        shutil.copytree(assets / folder, game / folder, dirs_exist_ok=True)
    (game / 'models').mkdir(exist_ok=True)
    for p in (assets / 'models').glob('player*'):
        if p.is_file(): shutil.copy2(p, game / 'models' / p.name)
    for name in ('csprogs.dat', 'menu.dat'):
        shutil.copy2(a.artifacts / name, game / name)
    # One shadow file, no modified product sources. Relative .src paths matter.
    original = (src / 'server/sv_player.qc').read_text()
    hook = '''
	if (!strcmp(c, "inventory_fixture"))
	{
		if (!strcmp(argv(1), "view"))
		{
			setorigin(self, '150 0 0'); self.angles = self.v_angle = '8 180 0'; self.fixangle = TRUE;
			return;
		}
		setorigin(self, '0 0 0');
		self.acct_state = 2;
		Social_Set(self, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "12345678");
		self.inv_revision = -1;
		inv_fixture_root = json_parse(!strcmp(argv(1), "off") ?
		  "{\\"revision\\":3,\\"roles\\":5,\\"outline\\":0,\\"hat\\":0,\\"items\\":[{\\"id\\":1,\\"colour\\":0,\\"equipped\\":0},{\\"id\\":2,\\"colour\\":5,\\"equipped\\":0}]}" :
		  "{\\"revision\\":2,\\"roles\\":5,\\"outline\\":1,\\"hat\\":6,\\"items\\":[{\\"id\\":1,\\"colour\\":0,\\"equipped\\":1},{\\"id\\":2,\\"colour\\":5,\\"equipped\\":1}]}");
		Inv_SVApply(self, inv_fixture_root); json_free(inv_fixture_root);
		return;
	}
'''
    marker = '\tif (!strcmp(c, "inventory_equip"))'
    if original.count(marker) != 1: raise RuntimeError('dispatch seam changed')
    # fteqcc resolves even NESTED includes relative to the top-level file.
    # Keep this one owned shadow alongside the original, remove it after compile.
    shadow = src / 'server/inventory_smoke_owned.qc'
    if shadow.exists(): raise RuntimeError('owned shadow collision')
    shadow.write_text('float inv_fixture_root;\n' + original.replace(marker, hook + marker))
    shutil.copy2(shadow, out / 'sv_player_smoke.qc')
    lines = (src / 'sv_progs.src').read_text().splitlines()
    lines[0] = os.path.relpath(game / 'qwprogs.dat', src).replace('\\', '/')
    lines[lines.index('server/sv_player.qc')] = os.path.relpath(shadow, src).replace('\\', '/')
    manifest = src / 'inventory-smoke-owned.src'
    if manifest.exists(): raise RuntimeError('owned manifest collision')
    manifest.write_text('\n'.join(lines) + '\n')
    try:
        r = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', manifest.name], cwd=src,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if (out / 'fixture-compile.log').exists():
            shutil.copy2(out / 'fixture-compile.log', out / 'fixture-compile.include-failure.log')
        (out / 'fixture-compile.log').write_bytes(r.stdout)
        if r.returncode or b'0 warnings' not in r.stdout: raise RuntimeError('fixture compilation failed')
    finally:
        manifest.unlink()
        shadow.unlink()
    shutil.copy2(a.client, out / 'ftesurf64.exe')
    shutil.copy2(a.server, out / 'fteqwsv64.exe')
    (out / 'default.fmf').write_text('FTEMANIFEST 1\nGAME InventorySmoke\nNAME "Inventory smoke"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG inventory-unused\n')
    port = None
    for candidate in range(27620, 27519, -1):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try: s.bind(('127.0.0.1', candidate))
            except OSError: continue
            port = candidate
            break
    if not port: raise RuntimeError('no designated dedicated port free')
    state = dict(revision=3, roles=5, outline=0, hat=0, items=[
        dict(id=1, colour=0, equipped=0), dict(id=2, colour=5, equipped=0)])
    wire = dict(polls=0, rows=0, equips=0, errors=[])

    class Backend(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_POST(self):
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode(), keep_blank_values=True).items()}
            path = urlsplit(self.path).path
            reply, code = dict(ok=0), 200
            try:
                if path in ('/api/social/poll', '/api/social/inventory'):
                    assert form.get('key') == 'inventory-fixture', 'wrong fixture node key'
                    assert form.get('node') == f'p{port}', 'wrong fixture node namespace'
                if path == '/api/social/poll':
                    rows = json.loads(form['roster'])
                    players = []
                    for row in rows:
                        assert row.get('inventory') == 1, 'roster omitted inventory opt-in'
                        players.append(dict(token=row['token'], hash='', messages=[], inventory=state))
                    wire['polls'] += 1
                    wire['rows'] += len(rows)
                    reply = dict(ok=1, players=players, invalid=[])
                elif path == '/api/social/inventory':
                    assert form.get('token') == 'a' * 64 and form.get('op') == 'equip', 'wrong fixture capability/action'
                    assert int(form['revision']) == state['revision'], 'stale native revision'
                    item, on = int(form['item']), int(form['on'])
                    assert item in (1, 2) and on in (0, 1), 'invalid native equipment'
                    state['items'][item - 1]['equipped'] = on
                    state['outline'] = state['items'][0]['equipped']
                    state['hat'] = 6 if state['items'][1]['equipped'] else 0
                    state['revision'] += 1
                    wire['equips'] += 1
                    reply = dict(inventory=1, ok=1, **state)
            except (AssertionError, KeyError, ValueError) as error:
                wire['errors'].append(str(error)); code = 400
            body = json.dumps(reply).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    backend = HTTPServer(('127.0.0.1', 0), Backend)
    backend_url = f'http://127.0.0.1:{backend.server_port}'
    common = ['cfg_save_auto 0', 'set log_enable 1', 'set log_dir logs', 'set log_readable 1',
              'set developer 1', 'set log_developer 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set cl_run_upload 0', 'set vid_vsync 0', 'set vid_conautoscale 0',
              'set vid_conwidth 1280', 'set vid_conheight 720', 'set hud_scale 2', 'set hud_scale_ui 2',
              'set lobby_dir ""', 'set cl_board_url ""', 'set ui_serverbgm 0', 'waitms 1200',
              'menu_restart', 'waitms 800', 'ui_close', f'connect 127.0.0.1:{port}', 'waitms 6500', 'ui_close']
    subject = common + ['set name InventorySubject', 'cmd inventory_fixture off', 'waitms 600',
              'hud_player', 'waitms 600', 'inventory', 'screenshot inventory_off',
              'cmd inventory_equip 1 1 3', 'waitms 1000', 'cmd inventory_equip 2 1 4', 'waitms 1000',
              'inventory', 'r_shaderpasses ftesurf/ice_outline', 'screenshot inventory_on',
              'waitms 14000', 'hud_player', 'disconnect', 'waitms 300', 'set ui_maps_filters 1',
              'set ui_maps_modes 511', 'set ui_bootcheck 2', 'menu_restart', 'waitms 100', 'ui_showall 1',
              'waitms 5000', 'echo INVENTORY SUBJECT FINISHED', 'quit']
    observer = common + ['set name InventoryObserver', 'cmd inventory_fixture view', 'waitms 2500',
              'screenshot inventory_remote', 'echo INVENTORY OBSERVER FINISHED', 'quit']
    for label, cfg in [('subject', subject), ('observer', observer)]:
        (game / (label + '.cfg')).write_text('\n'.join(['cfg_save_auto 0', f'set log_name {label}'] + cfg) + '\n')
    svcmd = [str(out / 'fteqwsv64.exe'), '-basedir', str(out), '-nohome', '-noplugins', '-port', str(port),
             '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0', '+set', 'lobby_master', backend_url,
             '+set', 'lobby_master_key', 'inventory-fixture',
             '+set', 'lobby_dir', '', '+set', 'lobby_enable', '1', '+set', 'lobby_nocollide', '1', '+set', 'log_enable', '1', '+set', 'log_name', 'server', '+map', 'inventory_smoke.map']
    def clcmd(label):
        return [str(out / 'ftesurf64.exe'), '-basedir', str(out), '-nohome', '-nosound', '-nocdaudio', '-window',
                '+set', 'cfg_save_auto', '0', '+set', 'plug_loaddefault', '0', '+set', 'vid_width', '1280',
                '+set', 'vid_height', '720', '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0',
                '+set', 'vid_renderer', 'gl', '+exec', label + '.cfg']
    actors = []
    with (out / 'server-launch.log').open('w') as so, (out / 'subject-launch.log').open('w') as co, (out / 'observer-launch.log').open('w') as oo:
        try:
            threading.Thread(target=backend.serve_forever, daemon=True).start()
            server = subprocess.Popen(svcmd, cwd='C:/FTESurf', stdout=so, stderr=subprocess.STDOUT); actors.append(server)
            time.sleep(2)
            if server.poll() is not None: raise RuntimeError('owned server exited')
            subject = subprocess.Popen(clcmd('subject'), cwd='C:/FTESurf', stdout=co, stderr=subprocess.STDOUT); actors.append(subject)
            time.sleep(9)
            observer = subprocess.Popen(clcmd('observer'), cwd='C:/FTESurf', stdout=oo, stderr=subprocess.STDOUT); actors.append(observer)
            observer.wait(timeout=35)
            subject.wait(timeout=35)
            if wire['errors'] or wire['rows'] < 1 or wire['equips'] != 2:
                raise RuntimeError('Native HTTP contract did not act: ' + repr(wire))
            text = (game / 'logs/subject.log').read_text(errors='replace')
            if 'Inventory: ready 1 revision 5 owned 1/1 equipped 1/1 hat colour 5' not in text:
                raise RuntimeError('Native equip reply did not reach private CSQC state')
            report = dict(utc=datetime.now(timezone.utc).isoformat(), wire=wire,
                          client=digest(a.client), server=digest(a.server), csprogs=digest(game / 'csprogs.dat'),
                          menu=digest(game / 'menu.dat'), fixture_qwprogs=digest(game / 'qwprogs.dat'),
                          subject_exit=subject.returncode, observer_exit=observer.returncode,
                          limit='Synthetic capability/mock backend, genuine native HTTP/replication. Auth and human acceptance are separate. Never deploy fixture qwprogs.')
            (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        finally:
            for proc in reversed(actors):
                if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
            backend.shutdown(); backend.server_close()
    print('Native inventory smoke:', out)


if __name__ == '__main__':
    main()
