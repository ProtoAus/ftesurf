#!/usr/bin/env python3
"""Screenshot gallery of the SUI panels in an isolated rig: look at pixels.

One arm per window size (--sizes). Each arm opens the main menu, the map
picker, the menu leaderboard, hud_edit, the save-lock and Source-renderer menus
and the in-game leaderboard (legacy and, with the plugin, native), and
screenshots each. --against pairs every shot with another rig's, side by side.
Lobbies and boards come from a loopback stub; maps, thumbnails and the tier
table are COPIED from --library. Nothing is launched from an install and no
owner config or player data is read.

This is not a gate: it grades only that every shot exists and the log holds no
QC/command error. Appearance is judged by a person reading the PNGs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.server
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
MAP = 'uigallery'
SHOTS = ('menu_main', 'menu_create', 'menu_create_hover', 'menu_board', 'menu_board_empty',
         'hud_plain', 'hudedit_list', 'hudedit_pane', 'hudedit_tip', 'gfx_page1', 'gfx_page2',
         'saveloc', 'scores_local', 'scores_online', 'linegraph')
NAMES = ('Lex', 'kitsune', 'moonwalk', 'ramp_goblin', 'Aurora', 'strafe.exe', 'veloc1ty',
         'surf_dad', 'nyx', 'Halcyon', 'bhop_bunny', 'zero-g', 'Mistral', 'pixelrain',
         'tau', 'Odyssey', 'driftwood', 'Juniper', 'afterimage', 'koi', 'Solstice',
         'wavelength', 'emberfall', 'quasar', 'lowgrav', 'Tanager', 'hexa', 'Borealis')
BSPS = ('bhop_3d', 'poop', 'surf_kitsune', 'surf_raqbonus3ramp', 'surf_voyager')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_map():
    return '''{\n"classname" "worldspawn"\n{
( -512 -512 -32 ) ( -512 512 -32 ) ( 512 512 -32 ) stone 0 0 0 1 1
( -512 -512 0 ) ( 512 -512 0 ) ( 512 512 0 ) stone 0 0 0 1 1
( -512 -512 -32 ) ( 512 -512 -32 ) ( 512 -512 0 ) stone 0 0 0 1 1
( 512 512 -32 ) ( -512 512 -32 ) ( -512 512 0 ) stone 0 0 0 1 1
( -512 512 -32 ) ( -512 -512 -32 ) ( -512 -512 0 ) stone 0 0 0 1 1
( 512 -512 -32 ) ( 512 512 -32 ) ( 512 512 0 ) stone 0 0 0 1 1
}\n}\n{\n"classname" "info_player_start"\n"origin" "0 0 128"\n"angle" "0"\n}\n'''


def seed_runs(game):
    """A zone file and local recordings, so the board has legs and rows."""
    (game / 'maps/zones/local').mkdir(parents=True)
    region = {'points': [[-400, -400], [-300, -400], [-300, -300], [-400, -300]],
              'bottom': 0, 'height': 100}
    end = dict(region, points=[[300, 300], [400, 300], [400, 400], [300, 400]])
    zones = {'tracks': {'main': {'zones': {
        'segments': [{'checkpoints': [{'regions': [region]}]}], 'end': {'regions': [end]}}}}}
    for name in (MAP, MAP + '.map'):
        (game / f'maps/zones/local/{name}.json').write_text(json.dumps(zones))
        folder = game / f'data/runs/{name}/main'
        folder.mkdir(parents=True)
        for row in range(18):
            ticks = 2900 + row * 137 + (row * row) % 53
            head = (f'FTESURF-REC 5\nmap {name}\nowner "{NAMES[row]}"\ntrack 0\n'
                    'startseg 0\nleg 0\ntickrate 0.015\nflags 0\nbegin\n')
            samples = ''.join(f'{i} {i} 0 80 100 0 0 0 0 0 0 1 0 0 0\n' for i in range(20))
            (folder / f'{ticks:07d}_g{row}_pb.rec').write_text(head + samples + f'end {ticks} 20 0 0\n')


def menu_board(query):
    tier = query.get('tier', 'ranked')
    off = int(query.get('offset', 0))
    lim = int(query.get('limit', 100))
    total = {'ksf': 46, 'momentum': 28, 'ranked': 0}.get(tier, 0)
    rows = [{'r': i + 1, 'name': NAMES[i % len(NAMES)] + ('' if i < len(NAMES) else str(i)),
             'ms': 41250 + i * 613 + (i * i * 7) % 400, 'when': 1759000000 - i * 86400 * 3}
            for i in range(off, min(total, off + lim))]
    return {'map': query.get('map', ''), 'tier': tier, 'offset': off, 'rows': rows,
            'counts': {'ksf': 46, 'momentum': 28, 'ranked': 0, 'imported': 74, 'community': 0}}


def game_board(query):
    rows = []
    for i in range(14):
        ms = 43880 + i * 512 + (i * 37) % 90
        rows.append({'r': i + 1, 'name': NAMES[(i * 3) % len(NAMES)], 'player': f'gallery-peer-{i}',
                     'ticks': round(ms / 15), 'rate': 66.6667, 'ms': ms, 'flags': 0,
                     'when': 1000 - i * 60, 'rep': 0, 'ver': int(i % 4 == 0)})
    return {'map': query.get('map', ''), 'track': int(query.get('track', 0)),
            'leg': int(query.get('leg', 0)), 'tier': query.get('tier', 'ranked'),
            'style': query.get('style', 'clean'), 't': 2000,
            'counts': {'ranked': 14, 'imported': 0}, 'rows': rows}


def start_stub(root):
    lobbies = {'lobbies': [
        {'map': 'surf_kitsune', 'addr': '203.0.113.7:27520', 'name': 'FTESurf -- Sydney 1', 'players': 6, 'max': 32},
        {'map': 'surf_voyager', 'addr': '203.0.113.7:27521', 'name': 'FTESurf -- Sydney 2', 'players': 2, 'max': 32},
        {'map': 'bhop_3d', 'addr': '203.0.113.7:27522', 'name': 'FTESurf -- Bhop', 'players': 0, 'max': 32},
        {'map': 'surf_utopia', 'addr': '203.0.113.7:27523', 'name': 'FTESurf -- Rotation', 'players': 11, 'max': 32}]}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            code = 200
            if url.path.endswith('/lobbies.json'):
                data = lobbies
            elif url.path.endswith('/api/board'):
                # The menu pages with an offset; csprogs asks for one page.
                data = menu_board(query) if 'offset' in query else game_board(query)
            else:
                code, data = 404, {'error': 'gallery route absent'}
            body = json.dumps(data, separators=(',', ':')).encode()
            self.send_response(code)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
            with self.server.lock, (root / 'http.jsonl').open('a') as stream:
                stream.write(json.dumps({'path': self.path, 'code': code, 'bytes': len(body)}) + '\n')

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.lock = threading.Lock()
    # Daemon, so an exception before the run's try/finally cannot hang the driver.
    server.worker = threading.Thread(target=server.serve_forever, name='ui-gallery-http', daemon=True)
    server.worker.start()
    return server


def config(a, size, port, http_port, native):
    def shot(name, wait=600):
        return [f'waitms {wait}', 'screenshot ' + name, 'waitms 250']

    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             'cl_maxfps 100', 'vid_vsync 0', 'scr_consize 0', 'set fs_missingwarn 0',
             'r_fullbright 1',
             'vid_srgb 0', 'v_gamma 1', 'v_contrast 1', 'v_brightness 0',
             'set ui_bootcheck 0', 'set rec_terms 4', 'set run_resume 0',
             f'set lobby_dir "http://127.0.0.1:{http_port}"', 'set lobby_poll 6',
             'set ui_tooltip_delay 0.35', 'name GalleryUser',
             'waitms 1500', 'menu_restart', 'waitms 1200']
    lines += shot('menu_main', 900)
    lines += ['ui_strip_test screen create'] + shot('menu_create', 4500)
    lines += ['ui_key downarrow', 'waitms 300', 'ui_key downarrow'] + shot('menu_create_hover', 700)
    if size == (1920, 1080):
        # The tier-1 chip under a parked MOUSE cursor: tooltips ignore the keyboard's.
        # `ui_hover` alone then prints whether a tip is up (test_ui_theme.py grades it).
        lines += ['ui_hover 486 224'] + shot('menu_create_tip', 1200) + ['ui_hover', 'ui_key downarrow', 'waitms 300']
    lines += ['ui_board_test surf_kitsune ksf'] + shot('menu_board', 2500)
    lines += ['ui_board_test tab ranked'] + shot('menu_board_empty', 1500)
    lines += ['ui_board_test close', 'waitms 300', 'ui_close', 'waitms 300']
    if native:
        lines += ['plug_load ui_imgui']
    lines += [f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
              f'set hud_scale {a.hud_scale}', 'set rec_terms 4',
              f'set lobby_dir "http://127.0.0.1:{http_port}"',
              'set hud_edit_panel_x 0.05', 'set hud_edit_panel_y 0.08',
              'set hud_mapinfo_timeleft 0', 'set ui_native_scores 0']
    # Nothing open: what every in-game panel shot must visibly differ from.
    lines += shot('hud_plain', 800)
    lines += ['hud_edit on', 'waitms 700', 'hud_edit ui hover he_done'] + shot('hudedit_list')
    lines += ['hud_edit ui hover he_sel_speed', 'hud_edit ui down mouse1', 'waitms 120',
              'hud_edit ui hover he_sel_speed', 'hud_edit ui up mouse1'] + shot('hudedit_pane', 700)
    lines += ['hud_edit ui hover he_fontfx'] + shot('hudedit_tip', 1000)
    lines += ['hud_edit off', 'waitms 400']
    # Mixed values, so On, Off, a named mode and an inert row are all on screen.
    lines += ['set hl2_water 3', 'set hl2_refract 1', 'set hl2_translucent 1', 'set hl2_animated 0',
              'set hl2_dither_alpha 0.55', 'set hl2_dither_force 0', 'set r_reflectcube 1',
              'set hl2_cubemaps 1', 'set hl2_bumpmap 0', 'set vbsp_skyroom 1', 'set vbsp_decals 1',
              'gfx_menu page 1'] + shot('gfx_page1')
    lines += ['gfx_menu page 2'] + shot('gfx_page2') + ['gfx_menu', 'waitms 300']
    lines += ['set rec_savelock 1', 'sl_save', 'waitms 400', 'sl_save', 'waitms 400', 'sl_save',
              'waitms 400', 'saveloc_menu'] + shot('saveloc', 800) + ['saveloc_menu', 'waitms 300']
    lines += ['scores tab local', '+showscores'] + shot('scores_local', 1200)
    lines += ['scores tab online', 'board_fetch 0 0 ranked clean'] + shot('scores_online', 2000)
    if native:
        lines += ['-showscores', 'waitms 300', 'set ui_native_scores 1', 'set ui_native_scores_font 16',
                  'scores tab local', '+showscores'] + shot('scores_native', 1500)
        lines += ['ui_imgui_status']
    # The run-comparison panel draws with the board's palette macros.
    lines += ['-showscores', 'waitms 300', 'set ui_native_scores 0', 'scores tab local',
              'scores line 0', 'waitms 1500', 'scores line 1', 'waitms 1500', 'linegraph']
    lines += shot('linegraph', 1200) + ['linegraph close', 'waitms 200', 'scores lines clear']
    lines += ['waitms 300', 'echo UIGALLERY FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def copy_tree(src, dst):
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def run(a):
    out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in [out, *out.parents]):
        raise RuntimeError('--out requires an ancestor OWNER.md before population')
    out.mkdir(parents=True, exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix='ui-gallery-', dir=out))
    (rig / 'UI_GALLERY_RIG.txt').write_text('Owned disposable gallery rig. No owner config or player data.\n')
    native = (a.plugins / 'fteplug_ui_imgui_x64.dll').is_file()
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'native': native,
              'planned': [f'{w}x{h}' for w, h in a.sizes], 'hud_scale': a.hud_scale, 'arms': {},
              'engine_sha256': sha(a.engine), 'server_sha256': sha(a.server),
              'progs_sha256': {n: sha(a.qc_artifacts / n) for n in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')}}
    for size in a.sizes:
        arm = f'{size[0]}x{size[1]}'
        root = rig / arm
        game = root / 'ftesurf'
        game.mkdir(parents=True)
        for folder in ('cfg', 'glsl', 'scripts', 'models', 'gfx', 'textures'):
            copy_tree(ROOT / 'ftesurf' / folder, game / folder)
        (game / 'downloads/csprogsvers').mkdir(parents=True)
        (game / 'maps').mkdir(exist_ok=True)
        (game / 'data').mkdir(exist_ok=True)
        (game / f'maps/{MAP}.map').write_text(make_map())
        (game / 'data/consent.txt').write_text('version 4\n')
        if a.library:
            for name in ('mapmeta.txt', 'mapdl.txt', 'mapwr.txt', 'mapdeps.txt'):
                if (a.library / 'data' / name).is_file():
                    shutil.copy2(a.library / 'data' / name, game / 'data' / name)
            copy_tree(a.library / 'gfx/mapthumbs', game / 'gfx/mapthumbs')
            copy_tree(a.library / 'gfx/thumbnails', game / 'gfx/thumbnails')
            for name in BSPS:
                if (a.library / f'maps/{name}.bsp').is_file():
                    shutil.copy2(a.library / f'maps/{name}.bsp', game / f'maps/{name}.bsp')
        seed_runs(game)
        for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
            shutil.copy2(a.qc_artifacts / name, game / name)
        subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                       check=True, stdout=subprocess.DEVNULL)
        shutil.copy2(a.engine, root / 'ftesurf64.exe')
        shutil.copy2(a.server, root / 'fteqwsv64.exe')
        if native:
            shutil.copy2(a.plugins / 'fteplug_ui_imgui_x64.dll', root / 'fteplug_ui_imgui_x64.dll')
        (root / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfUIGallery\nNAME "UI gallery"\n'
                                         'BASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG gallery-unused\n')
        port = None
        for candidate in range(27620, 27519, -1):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                try:
                    s.bind(('127.0.0.1', candidate))
                except OSError:
                    continue
                port = candidate
                break
        if port is None:
            raise RuntimeError('no free designated dedicated test port')
        stub = start_stub(root)
        (game / 'gallery.cfg').write_text(config(a, size, port, stub.server_port, native))
        # The raw .map has no clipping hull: without this the player falls for ever.
        (game / 'gallery_server.cfg').write_text(f'sv_cheats 1\nmap {MAP}.map\nwaitms 1000\nsv_gravity 0\n')
        svcmd = [str(root / 'fteqwsv64.exe'), '-basedir', str(root), '-nohome', '-noplugins',
                 '-port', str(port), '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0',
                 '+set', 'lobby_dir', '', '+exec', 'gallery_server.cfg']
        clcmd = [str(root / 'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound', '-nocdaudio',
                 '-window', '+set', 'plug_loaddefault', '0', '+set', 'vid_width', str(size[0]),
                 '+set', 'vid_height', str(size[1]), '+set', 'vid_fullscreen', '0',
                 '+set', 'vid_winmaximize', '0', '+set', 'vid_renderer', a.renderer,
                 '+set', 'cfg_save_auto', '0', '+exec', 'gallery.cfg']
        code = None
        with (root / 'server.log').open('w') as so, (root / 'launch.log').open('w') as co:
            server = subprocess.Popen(svcmd, cwd=str(root), stdout=so, stderr=subprocess.STDOUT)
            client = None
            try:
                time.sleep(2)
                if server.poll() is not None:
                    raise RuntimeError('owned server exited: ' + str(root))
                client = subprocess.Popen(clcmd, cwd=str(root), stdout=co, stderr=subprocess.STDOUT)
                code = client.wait(timeout=a.timeout)
            finally:
                # Only the handles this invocation created.
                for p in (client, server):
                    if p is not None and p.poll() is None:
                        p.terminate()
                        try:
                            p.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            p.kill()
                            p.wait()
                stub.shutdown()
                stub.server_close()
                stub.worker.join(timeout=10)
        report['arms'][arm] = {'returncode': code, 'port': port}
        (rig / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Completed', arm, root)
    return rig


def grade(rig):
    errors = []
    report = json.loads((rig / 'report.json').read_text())
    for arm in report.get('planned', []):
        if arm not in report['arms']:
            errors.append(f'{arm}: planned arm never ran')
    for arm, result in report['arms'].items():
        root = rig / arm
        logs = list((root / 'ftesurf/logs').glob('gallery*.log'))
        if len(logs) != 1:
            errors.append(f'{arm}: unique log required')
            continue
        text = logs[0].read_text(errors='replace')
        if result.get('returncode') != 0:
            errors.append(f'{arm}: client exit {result.get("returncode")}')
        if text.count('UIGALLERY FINISHED') != 1:
            errors.append(f'{arm}: completion marker missing')
        for bad in re.findall(r'[^\r\n]*(?:Unknown command|QC runtime error|CSQC_Abort|Menu_Abort|sui error|sui warning|sui_probe: no control|sui_probe: editor closed)[^\r\n]*', text):
            # Progs from before Patch 606 have no ui_hover; they are still a valid control.
            if 'Unknown command "ui_hover"' not in bad:
                errors.append(f'{arm}: {bad.strip()[:140]}')
        # Not a failure of the build: the owner's desktop reached the rig. The parked
        # hovers are gone and real input may have landed, so no shot can be trusted.
        if '[focus] window is foreground' in text:
            errors.append(f'{arm}: INTERFERED -- the rig window took the foreground mid-run; rerun it')
        wanted = SHOTS + (('scores_native',) if report.get('native') else ())
        if arm == '1920x1080':
            wanted += ('menu_create_tip',)
        for name in wanted:
            if len(list((root / 'ftesurf/screenshots').glob(name + '.*'))) != 1:
                errors.append(f'{arm}: missing screenshot {name}')
    return errors


def sheet(rig, against):
    """Side-by-side PNG per shot: `against` on the left, this rig on the right.

    An arm pairs with the same-named arm of `against`, or with `against` itself
    when that directory is one arm (it holds ftesurf/screenshots).
    """
    from PIL import Image
    report = json.loads((rig / 'report.json').read_text())
    for arm in report['arms']:
        left = against / arm if (against / arm / 'ftesurf/screenshots').is_dir() else against
        if not (left / 'ftesurf/screenshots').is_dir():
            print('NO PAIRS for', arm, '-- no screenshots under', left)
            continue
        dest = rig / 'pairs' / arm
        for shot in sorted((rig / arm / 'ftesurf/screenshots').glob('*.*')):
            other = left / 'ftesurf/screenshots' / shot.name
            if not other.is_file():
                continue
            dest.mkdir(parents=True, exist_ok=True)
            a, b = Image.open(other).convert('RGB'), Image.open(shot).convert('RGB')
            pair = Image.new('RGB', (a.width + b.width + 8, max(a.height, b.height)), (255, 0, 255))
            pair.paste(a, (0, 0))
            pair.paste(b, (a.width + 8, 0))
            pair.save(dest / (shot.stem + '.png'))


def size_arg(text):
    w, _, h = text.partition('x')
    if not (w.isdigit() and h.isdigit()):
        raise argparse.ArgumentTypeError('a size is WIDTHxHEIGHT')
    return int(w), int(h)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path)
    p.add_argument('--server', type=Path)
    p.add_argument('--plugins', type=Path, help='directory holding fteplug_ui_imgui_x64.dll (optional shot)')
    p.add_argument('--qc-artifacts', type=Path)
    p.add_argument('--library', type=Path, help='an install gamedir to COPY map tables, thumbnails and small maps from')
    p.add_argument('--out', type=Path, help='owned task-root output directory')
    p.add_argument('--sizes', nargs='+', type=size_arg, default=[(1920, 1080)], metavar='WxH')
    p.add_argument('--against', type=Path, help='another gallery rig (or one arm of one) to pair every shot with')
    p.add_argument('--hud-scale', type=float, default=2)
    p.add_argument('--renderer', choices=('gl', 'd3d11', 'vk'), default='gl')
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--grade', type=Path)
    a = p.parse_args()
    if not a.grade:
        for need in ('engine', 'server', 'qc_artifacts', 'out'):
            if getattr(a, need) is None:
                p.error('--' + need.replace('_', '-') + ' is required for a run')
        if a.plugins is None:
            a.plugins = a.engine.parent
    rig = a.grade or run(a)
    errors = grade(rig)
    if a.against:
        sheet(rig, a.against)
    for error in errors:
        print('FAIL', error)
    print('Gallery rig', rig)
    print('Gallery failures:', len(errors))
    raise SystemExit(bool(errors))
