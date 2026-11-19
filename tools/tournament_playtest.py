#!/usr/bin/env python3
"""Launch a disposable Linux tournament playtest; never alter the live install.

A real dedicated FTE server, backend and independently signed clients run on
loopback. Synthetic account linking is confined to this fixture's app/database;
normal account-signature verification, SSQC mutations and UI remain in use.
The clearly labelled practice partner accepts offered seats, drafts and readies,
but DOES NOT surf, invent finishes or submit scores. Human finishes use the normal
timer. No Steam relink, billing, public allocation or production credentials.

Generated test-only QC redirects fixed web origins to this loopback backend and
uses a distinct protocol name. This is NOT a release build or ranked acceptance.
"""
import argparse
import contextlib
import hashlib
import importlib
import json
import os
from pathlib import Path
import pty
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
MAPS = ('surf_prelude', 'surf_liopleurodon2', 'surf_aircontrol',
        'surf_forbidden_ways', 'surf_lux', 'surf_lo_tek')
ORIGINS = ('https://play.proto.bar', 'https://dl.proto.bar', 'https://proto.bar')


def owned_root(path):
    path = path.resolve()
    if not any((p / 'OWNER.md').is_file() for p in (path, *path.parents)):
        raise ValueError('--work-root requires an existing ancestor OWNER.md')
    path.mkdir(parents=True, exist_ok=True)
    return path


def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def map_assets(content, cache, download):
    """Only named public game assets; no owner data/recordings/config/key copy."""
    maps = cache / 'maps'
    zones = maps / 'zones/local'
    zones.mkdir(parents=True, exist_ok=True)
    for name in MAPS:
        zone = next((p for kind in ('local', 'online')
                     if (p := content/'ftesurf/maps/zones'/kind/(name+'.json')).is_file()), None)
        if zone is None:
            raise ValueError('No inspected server zone file for '+name)
        copy_file(zone, zones/(name+'.json'))
        target = maps/(name+'.bsp')
        if not target.is_file():
            existing = content/'ftesurf/maps'/(name+'.bsp')
            if existing.is_file():
                copy_file(existing, target)
            elif download:
                print('Fetching public game map:', name, flush=True)
                # Same published asset route as the normal game. R2 redirect is
                # intentional; HTTPS verification stays enabled. Bound the body.
                # Identify the game tool honestly: Cloudflare's browser-integrity
                # rule rejects the generic Python-urllib user agent (error1010).
                request = urllib.request.Request('https://play.proto.bar/maps/'+name+'.bsp',
                    headers={'User-Agent': 'WorldOfSurf-LocalPlaytest/1.0'})
                with urllib.request.urlopen(request, timeout=90) as response:
                    if not response.url.startswith('https://'):
                        raise ValueError('Map redirect left HTTPS')
                    data = response.read(64*1024*1024+1)
                if len(data) > 64*1024*1024 or not data.startswith(b'VBSP'):
                    raise ValueError('Not a bounded Source BSP: '+name)
                part = target.with_suffix('.part')
                part.write_bytes(data)
                part.replace(target)
            else:
                raise ValueError('Missing '+name+'; prepare once with --download')
        if target.read_bytes()[:4] != b'VBSP':
            raise ValueError('Not a Source BSP: '+str(target))
    (cache/'map-assets.json').write_text(json.dumps({
        str(p.relative_to(cache)): digest(p) for p in sorted(maps.rglob('*')) if p.is_file()
    }, indent=2)+'\n')
    return maps


def from_template(args, out):
    template = args.template.resolve()
    if not template.is_dir() or not any((p/'OWNER.md').is_file() for p in (template,*template.parents)):
        raise ValueError('Template must be an existing owned prepared session')
    if (template/'backend').exists():
        raise ValueError('Only a pristine --prepare-only template is reusable, never a played profile')
    if not (template/'src').is_dir():
        raise ValueError('Template lacks its source snapshot; prepare a fresh template')
    manifest = json.loads((template/'manifest.json').read_text())
    if manifest.get('test_only') is not True or manifest['url'] != 'http://127.0.0.1:'+str(manifest['http_port']):
        raise ValueError('Not a loopback-only playtest template')
    for name, expected in manifest['source_files'].items():
        if digest(ROOT/name) != expected:
            raise ValueError('Template source is stale: '+name+'; prepare a fresh template')
    for name, expected in manifest['native'].items():
        if digest(template/'bin'/name) != expected:
            raise ValueError('Template native executable changed: '+name)
    for profile in ('server','player','partner'):
        for name, expected in manifest['vms'].items():
            if digest(template/profile/'ftesurf'/name) != expected:
                raise ValueError('Template VM changed: '+profile+'/'+name)
    rig = Path(tempfile.mkdtemp(prefix='session-', dir=out))
    os.chmod(rig, 0o700)
    (rig/'OWNER.md').write_text('Fresh local test from immutable prepared template. No production state.\n')
    for name in ('bin','src','ftesurf','server','player','partner'):
        shutil.copytree(template/name, rig/name, symlinks=True)
    manifest['template'] = str(template)
    (rig/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return rig, manifest


def stable_ports(out):
    """Compiled VMs embed the loopback URL, so the HTTP port must survive between
    launches for the VM cache to hit. A busy port is replaced (cache misses once)."""
    state = out/'ports.json'
    try:
        ports = json.loads(state.read_text())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # The last run's port sits in TIME_WAIT for a minute; the backend binds
            # with SO_REUSEADDR too, so only a live listener counts as busy.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', ports['http']))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', ports['game']))
    except (OSError, KeyError, ValueError, TypeError):
        ports = dict(http=free_port(socket.SOCK_STREAM), game=free_port(socket.SOCK_DGRAM))
        state.write_text(json.dumps(ports)+'\n')
    return ports['http'], ports['game']


def vm_key(src, vm, compiler):
    """Everything one VM is built from: the compiler, its .src list and each listed
    file (already origin-rewritten), so a menu edit does not rebuild csprogs."""
    h = hashlib.sha256((digest(compiler)+'|'+vm+'|').encode())
    listing = (src/(vm+'.src')).read_text()
    h.update(listing.encode())
    for line in listing.splitlines():
        line = line.split('//')[0].strip()
        if line.endswith('.qc'):
            h.update(line.encode()+b'\0'+(src/line).read_bytes()+b'\0')
    return h.hexdigest()


def cached_qualification(rig, manifest, cache):
    """Native map identities only change with the maps, zones, server binary and
    server VM; reuse an earlier observation of exactly those inputs."""
    h = hashlib.sha256()
    h.update(json.dumps([manifest['native'], manifest['vms'].get('qwprogs.dat'), manifest['maps']], sort_keys=True).encode())
    h.update(digest(Path(__file__).resolve().parent/'tournament_qualify.py').encode())
    for name in manifest['maps']:
        h.update(digest(rig/'server/ftesurf/maps'/(name+'.bsp')).encode())
        h.update(digest(rig/'server/ftesurf/maps/zones/local'/(name+'.json')).encode())
    return cache/('qualification-'+h.hexdigest()[:32]+'.json')


def prepare(args):
    out = owned_root(args.work_root)
    if args.template:
        return from_template(args, out)
    rig = Path(tempfile.mkdtemp(prefix='session-', dir=out))
    os.chmod(rig, 0o700)
    (rig/'OWNER.md').write_text('Owned disposable local tournament playtest. No production state.\n')
    http_port, game_port = stable_ports(out)
    cache = out/'cache'
    cache.mkdir(exist_ok=True)
    url = 'http://127.0.0.1:'+str(http_port)
    assets = out/'assets'
    maps = map_assets(args.content, assets, args.download)
    bin_dir = rig/'bin'
    bin_dir.mkdir()
    for source, name in ((args.client, 'fteqw64'), (args.server, 'fteqw-sv64'),
                         (args.compiler, 'fteqcc64'),
                         (args.content/'fteplug_hl2_amd64.so', 'fteplug_hl2_amd64.so')):
        copy_file(source, bin_dir/name)
    # Selective game-owned render dependencies, NOT an install/data/profile copy.
    render = assets/'render'
    render.mkdir(exist_ok=True)
    for name in ('gfx', 'glsl', 'scripts', 'models', 'sound', 'particles', 'textures'):
        source = args.content/'ftesurf'/name
        if source.is_dir() and not (render/name).is_dir():
            shutil.copytree(source, render/name)
    src = rig/'src'
    shutil.copytree(ROOT/'src', src)
    redirects = {}
    for path in src.rglob('*.qc'):
        old = path.read_text()
        new = old
        for origin in ORIGINS:
            new = new.replace(origin, url)
        if new != old:
            path.write_text(new)
            redirects[str(path.relative_to(src))] = digest(path)
    (rig/'ftesurf').mkdir()
    outputs = dict(sv_progs='qwprogs.dat', cl_progs='csprogs.dat', m_progs='menu.dat')
    for vm in ('sv_progs', 'cl_progs', 'm_progs'):
        cached = cache/(vm+'-'+vm_key(src, vm, bin_dir/'fteqcc64')[:32]+'.dat')
        if cached.is_file():
            print('Reusing compiled '+vm+' (sources unchanged)', flush=True)
            copy_file(cached, rig/'ftesurf'/outputs[vm])
            (rig/(vm+'-build.log')).write_text('reused '+str(cached)+'\n')
            continue
        print('Preparing local '+vm+' (compiler log retained in '+str(rig)+')', flush=True)
        with (rig/(vm+'-build.log')).open('w') as log:
            subprocess.run([str(bin_dir/'fteqcc64'), '-O2', '-Wall', '-v',
                            '-max_strings', '4194304', '-srcfile', vm+'.src'],
                           cwd=src, stdout=log, stderr=subprocess.STDOUT, check=True)
        copy_file(rig/'ftesurf'/outputs[vm], cached)
        # Keep the three newest builds of each VM.
        for old in sorted(cache.glob(vm+'-*.dat'), key=lambda f: f.stat().st_mtime)[:-3]:
            old.unlink()
    profile_names = ('server', 'player', 'partner')
    term_text = (ROOT/'src/shared/sh_defs.qc').read_text()
    tier = int(re.search(r'#define\s+FS_TERMS_ONLINE\s+(\d+)', term_text)[1])
    for who in profile_names:
        profile = rig/who
        gd = profile/'ftesurf'
        gd.mkdir(parents=True)
        (gd/'data').mkdir()
        (gd/'maps/zones/local').mkdir(parents=True)
        (gd/'cfg').mkdir()
        for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
            copy_file(rig/'ftesurf'/name, gd/name)
        # Fresh tracked defaults, not the owner's saved cfg or consent.
        shutil.copytree(ROOT/'ftesurf/cfg', gd/'cfg', dirs_exist_ok=True)
        for cfg in (gd/'cfg').rglob('*.cfg'):
            text = cfg.read_text()
            for origin in ORIGINS:
                text = text.replace(origin, url)
            cfg.write_text(text)
        shutil.copytree(args.content/'ftesurf/particles', gd/'particles', dirs_exist_ok=True)
        for name in MAPS:
            (gd/'maps'/(name+'.bsp')).symlink_to(maps/(name+'.bsp'))
            copy_file(maps/'zones/local'/(name+'.json'), gd/'maps/zones/local'/(name+'.json'))
        meta = args.content/'ftesurf/data/mapmeta.txt'
        if meta.is_file():
            copy_file(meta, gd/'data/mapmeta.txt')
        library = args.content/'steam_libraries.txt'
        if library.is_file():
            copy_file(library, profile/'steam_libraries.txt')
        defaults = (ROOT/'ftesurf/fs_addons.default.txt').read_text()
        (gd/'fs_addons.txt').write_text(str(render)+'\n'+defaults)
        # No maps/data/configs from an owner-writable directory are mounted.
        manifest = (ROOT/'default.fmf').read_text()
        manifest = re.sub(r'(?m)^PROTOCOLNAME\s+.*$', 'PROTOCOLNAME WOS-Tournament-Local-Test', manifest)
        (profile/'default.fmf').write_text(manifest)
        if who == 'partner' or (who == 'player' and args.smoke):
            # Synthetic automated actor only. Human profile asks normally in UI.
            (gd/'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion '+str(tier)+'\nfixture automated-actor\n')
    manifest = {
        'test_only': True, 'url': url, 'http_port': http_port, 'game_port': game_port,
        'maps': list(MAPS), 'source_ref': subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_files': {str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT/'src').rglob('*')) if p.is_file() and p.suffix in ('.qc','.src')},
        'test_origin_rewrites': redirects,
        'native': {p.name: digest(p) for p in bin_dir.iterdir()},
        'vms': {p.name: digest(p) for p in (rig/'ftesurf').glob('*.dat')},
    }
    (rig/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return rig, manifest


def start_backend(rig, manifest):
    """Fixture seam links fresh public keys; signature checks stay unmodified."""
    home = rig/'backend'
    home.mkdir()
    (home/'surfd.env').write_text('SURFD_KEY=local-test-only\n')
    (home/'data').mkdir()
    (home/'data/mappool.json').write_text('{}')
    # Transport/UI fixture metadata only: native map/course pins are observed
    # separately, but these T1/provenance labels are NOT real difficulty data.
    (home/'data/mapwatch').mkdir()
    (home/'data/mapwatch/mapdl.txt').write_text('FTESURF-MAPDL 1\n'+''.join(
        'dl '+name+' surf - 1 1 - 0 1 0\n' for name in MAPS))
    (home/'momtracks.tsv').write_text(''.join(name+'\t0\t1\n' for name in MAPS))
    (home/'CATALOGUE-SCOPE.txt').write_text(
        'Synthetic T1 and provenance labels for disposable transport/UI tests only.\n'
        'Not authoritative map difficulty or live-node qualification/approval.\n')
    env = {'SURFD_HOME': str(home), 'SURFD_DB': str(home/'test.db'),
           'SURFD_ENV': str(home/'surfd.env'), 'SURFD_RUNS': str(home/'runs'),
           'SURFD_EVIDENCE': str(home/'evidence'), 'SURFD_KEEP': str(home/'keep'),
           'SURFD_MAPS': str(rig/'server/ftesurf/maps'),
           'SURFD_ZONES': str(rig/'server/ftesurf/maps/zones/local'),
           'SURFD_LINK_HOSTS': '127.0.0.1', 'SURFD_TRUSTED': '127.0.0.1/32',
           'SURFD_PROXIES': '', 'SURFD_PUBLIC_HOST': '',
           'SURFD_TOOLS': str(ROOT/'tools'),
           'SURFD_GAME_CODE': str(rig/'ftesurf/csprogs.dat'),
           'SURFD_TOURNAMENTS': '1', 'SURFD_TOURNAMENT_ACCESS': 'free_beta',
           'SURFD_MOMTRACKS': str(home/'momtracks.tsv'),
           'SURFD_TOURNAMENT_QUALIFICATIONS': str(rig/'fixture-qualifications.json')}
    os.environ.update(env)
    sys.path.insert(0, str(ROOT/'surfd'))
    S = importlib.import_module('surfd')
    accounts = importlib.import_module('accounts')
    from flask import request
    from werkzeug.serving import WSGIRequestHandler, make_server
    # Use the real installed-BSP/zone qualification index, not a mocked pool.
    actors = []
    accounts.avatar_url = lambda *a: ''

    @S.app.before_request
    def fixture_link():
        if request.path not in ('/api/account', '/api/account/bind', '/api/tournament-lobbies/action'):
            return None
        pub = request.form.get('pub', '')
        if not re.fullmatch(r'[0-9a-f]{64}', pub):
            return None
        db = S.get_db()
        if not db.execute('SELECT 1 FROM keylinks WHERE pub=?', (pub,)).fetchone():
            # Host is launched/authenticated before partner. Real engine proof
            # still has to verify after this synthetic linking fixture hook.
            index = len(actors)
            if index >= 2:
                return None
            sid = str(76561198000991000+index)
            name = 'Local player (test)' if index == 0 else 'Practice partner (test)'
            now = int(time.time())
            db.execute('INSERT INTO accounts(steamid,name,created_at) VALUES(?,?,?)', (sid,name,now))
            db.execute('INSERT INTO keylinks(pub,steamid,linked_at) VALUES(?,?,?)', (pub, sid, now))
            db.commit()
            actors.append({'sid': sid, 'who': accounts.who_of(sid), 'name': name})
        return None

    # Retain only action acknowledgements/public handoffs, never signatures/tokens.
    S.playtest_events = []

    @S.app.after_request
    def fixture_observe(response):
        if request.path == '/api/tournament-lobbies/action':
            body = response.get_json(silent=True) or {}
            from urllib.parse import parse_qs
            payload = parse_qs(request.form.get('payload', ''))
            S.playtest_events.append(dict(op=payload.get('op', [''])[0],
                ok=body.get('ok'), error=body.get('error'), me=body.get('me'),
                party=(body.get('party') or {}).get('id'), launch=body.get('launch')))
        return response

    class Quiet(WSGIRequestHandler):
        def log_request(self, *args, **kwargs):
            pass
    web = make_server('127.0.0.1', manifest['http_port'], S.app, request_handler=Quiet)
    thread = threading.Thread(target=web.serve_forever, daemon=True)
    thread.start()
    return S, actors, web, thread


class Native:
    def __init__(self, rig, name, command):
        self.name = name
        self.log = (rig/(name+'-console.log')).open('w')
        # Linux FTE deliberately ignores non-tty stdin. An owned PTY enables its
        # normal console path without a plugin flag or owner-console attachment.
        self.input, slave = pty.openpty()
        env = dict(os.environ, HOME=str(rig/name/'home'),
                   XDG_CONFIG_HOME=str(rig/name/'config'), XDG_DATA_HOME=str(rig/name/'user-data'),
                   XDG_CACHE_HOME=str(rig/name/'cache'))
        try:
            self.process = subprocess.Popen(command, cwd=rig/name, stdin=slave,
                                            stdout=self.log, stderr=subprocess.STDOUT,
                                            env=env, start_new_session=True)
        except BaseException:
            os.close(self.input)
            self.log.close()
            raise
        finally:
            os.close(slave)

    def send(self, commands):
        if self.process.poll() is not None:
            raise RuntimeError(self.name+' stopped; inspect retained console log')
        data = (commands+'\n').encode()
        while data:
            data = data[os.write(self.input, data):]

    def stop(self):
        if self.process.poll() is None:
            with contextlib.suppress(BrokenPipeError, OSError):
                self.send('quit')
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        os.close(self.input)
        self.log.close()


def command_base(rig, name, executable):
    return [str(rig/'bin'/executable), '-nohome', '-nobrowse', '-nojoy', '-nosound',
            '-basedir', str(rig/name), '-manifest', str(rig/name/'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0',
            '+set', 'fs_lazy_addons', '0', '+set', 'cl_idlefps', '0',
            '+set', 'cl_maxfps', '100']


def click(client, name):
    client.send('hud_edit ui hover '+name+'\nwaitms 100\nhud_edit ui down mouse1\nwaitms 100\nhud_edit ui up mouse1')


def menu_elements(client, rig):
    """Observe a fresh draw; startup console commands can precede menu registration."""
    log = rig/(client.name+'-console.log')
    offset = log.stat().st_size
    client.send('ui_cursor')
    deadline = time.monotonic()+1
    while time.monotonic() < deadline:
        with log.open() as stream:
            stream.seek(offset)
            text = stream.read()
        header = re.search(r'ui_cursor: .* elements (\d+)', text)
        rows = re.findall(r'ui_element \d+ \[([^\]]+)\] ([^\r\n]+)', text)
        if header and len(rows) >= int(header[1]):
            return {name: tuple(map(float, box.split())) for name, box in rows}
        if 'Unknown command "ui_cursor"' in text:
            return {}
        time.sleep(.05)
    return {}


def menu_click(client, rig, name):
    """Aim the existing native click at the menu's actual transformed hit box."""
    box = menu_elements(client, rig).get(name)
    if box is None:
        return False
    x, y, w, h = box
    client.send(f'ui_click {x+w/2:g} {y+h/2:g}')
    return True


def menu_tab_click(client, rig, name):
    """Narrow rooms split players/settings into tabs: open the one holding the control."""
    if menu_click(client, rig, name):
        return True
    tab = 'mt_view_players' if name.startswith('mt_seat') else 'mt_view_maps'
    menu_click(client, rig, tab)
    return False


def menu_map(client, rig, index):
    """Ban/pick any available card. Only the actor's own pool cards register a hit
    box, so an empty page means the cards are on another page: page backwards
    first (a later pick can need an earlier page), then forwards."""
    elements = menu_elements(client, rig)
    cards = sorted((int(k[6:]), k) for k in elements if re.fullmatch(r'mt_map\d+', k))
    if cards:
        x, y, w, h = elements[cards[0][1]]
        client.send(f'ui_click {x+w/2:g} {y+h/2:g}')
        return True
    for nav in ('mt_maps_prev', 'mt_maps_next'):
        if nav in elements:
            menu_click(client, rig, nav)
            return False
    return False


def native_failures(rig):
    for name in ('player', 'partner', 'server'):
        path = rig/(name+'-console.log')
        if path.is_file():
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size-32768))
                tail = stream.read().decode(errors='replace')
            for marker in ('CSQC_Abort:', 'QC runtime error', 'Host_Error:', 'Sys_Error:'):
                if marker in tail:
                    raise RuntimeError(name+' native failure ('+marker+'); inspect '+str(path))


def run(args, rig, manifest):
    # Consent is never inherited from a played profile or silently granted to a
    # human. Only this invocation's synthetic automated actors are preaccepted.
    tier = int(re.search(r'#define\s+FS_TERMS_ONLINE\s+(\d+)', (ROOT/'src/shared/sh_defs.qc').read_text())[1])
    consent = rig/'player/ftesurf/data/consent.txt'
    human = rig.parent/'cache/human-consent.txt'
    if args.smoke:
        consent.write_text('FTESURF-CONSENT 1\nversion '+str(tier)+'\nfixture automated-actor\n')
    else:
        if consent.exists():
            consent.unlink()
        # Your own acceptance from an earlier local playtest, if its version is current;
        # delete cache/human-consent.txt to be asked again.
        saved = re.search(r'(?m)^version\s+(\d+)', human.read_text()) if human.is_file() else None
        if saved and int(saved[1]) >= tier and 'fixture' not in human.read_text():
            copy_file(human, consent)
            print('Using your terms acceptance from an earlier local playtest.', flush=True)
    S, actors, web, web_thread = start_backend(rig, manifest)
    import tournaments as T
    natives = []
    port, url = manifest['game_port'], manifest['url']
    endpoint = '127.0.0.1:'+str(port)
    partner = None
    checks = {}
    action_at = 0
    setup_steps = 0
    tour = getattr(args, 'tour', False)
    tour_step = 0
    shots = set()

    def shot(client, name):
        # Once per name: the room redraws every frame, one picture per stage is enough.
        if client and name not in shots:
            shots.add(name)
            client.send('screenshot '+name)
            return True
        return False
    width, height = getattr(args, 'width', 1280), getattr(args, 'height', 800)
    seats = getattr(args, 'smoke_seats', 2)
    stage = 'startup'
    stage_at = time.monotonic()
    started = time.monotonic()
    samples = []
    failure = None
    try:
        server = Native(rig, 'server', command_base(rig, 'server', 'fteqw-sv64') + [
            '-ip', '127.0.0.1', '-port', str(port), '+set', 'maxclients', '8',
            '+set', 'maxspectators', '6', '+set', 'sv_playerslots', '8', '+set', 'lobby_enable', '1',
            '+set', 'lobby_mode', '2', '+set', 'lobby_nocollide', '1',
            '+set', 'tournament_enable', '1', '+set', 'lobby_master', url,
            '+set', 'lobby_master_key', 'local-test-only', '+set', 'lobby_cycle', '0',
            '+set', 'lobby_records', '0', '+set', 'lobby_stats', '0',
            '+set', 'sv_dlURL', url, '+serverinfo', 'tournament_test', '1',
            '+hostname', 'LOCAL tournament playtest', '+map', MAPS[0]])
        natives.append(server)
        # Observe native heartbeat, not an arbitrary startup sleep.
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            with S.app.app_context():
                ready = S.get_db().execute('SELECT count(*) FROM lobbies').fetchone()[0]
            if args.smoke and time.monotonic()-started > 200:
                raise RuntimeError('Bounded smoke timed out waiting for dedicated heartbeat')
            if ready:
                break
            if server.process.poll() is not None:
                raise RuntimeError('Dedicated server stopped before heartbeat')
            time.sleep(.2)
        else:
            raise RuntimeError('No dedicated heartbeat; inspect server-console.log')
        player_command = command_base(rig, 'player', 'fteqw64') + [
            '+set', 'vid_renderer', args.renderer if args.smoke else 'gl', '-window', '-width', str(width), '-height', str(height),
            '+set', 'vid_fullscreen', '0', '+set', 'vid_conautoscale', '1',
            '+set', 'lobby_dir', url, '+set', 'lobby_hosts', '127.0.0.1 localhost',
            '+set', 'lobby_hosts_gen', '1', '+set', 'lobby_dir_gen', '1',
            '+set', 'sv_dlURL', url, '+set', 'ui_mapdl_gen', '1',
            '+set', 'rec_upload', '0', '+set', 'rec_hid_upload', '0',
            '+set', 'ui_update', '0',
            '+bind', 'F6', 'tournament', '+name', 'Local player (test)']
        # Both clients boot disconnected. Only MT_Launch may connect them.
        player = Native(rig, 'player', player_command)
        natives.append(player)
        print('LOCAL MAIN-MENU TEST: fresh synthetic linked accounts, no public times/billing.\n'
              'Accept online terms in the fresh visible profile. Tournaments opens automatically.\n'
              'Create a tournament; offer partner a seat; Accept seat; Lock roster; ban/pick;\n'
              'Ready to connect; Start. Nobody connects before Start. F6 opens in-game controls.\n'
              'The labelled native practice partner accepts/drafts/readies, never surfs or scores.\n'
              'Quit or Ctrl-C to stop all owned actors. Retained session: '+str(rig), flush=True)
        player.send('menu_restart')
        browser_opened = False
        partner_opened = False
        partner_greeted = chat_said = 0
        partner_replied = False
        while player.process.poll() is None:
            now = time.monotonic()
            if args.smoke and (now-started > (360 if tour else 200) or now-stage_at > (100 if tour else 45)):
                raise RuntimeError('Bounded main-menu smoke timed out at '+stage)
            native_failures(rig)
            if server.process.poll() is not None:
                raise RuntimeError('Owned dedicated server stopped unexpectedly')
            if not browser_opened and consent.is_file():
                accepted = re.search(r'(?m)^version\s+(\d+)', consent.read_text())
                if accepted and int(accepted[1]) >= tier and menu_elements(player, rig):
                    player.send('ui_tournaments')
                    browser_opened = True
            with S.app.app_context():
                db = S.get_db()
                # One read snapshot: Start must not look half pre/half post launch.
                db.execute('BEGIN')
                sessions = db.execute('SELECT count(DISTINCT steamid) FROM social_sessions').fetchone()[0]
                row = db.execute('SELECT state FROM tournament_parties ORDER BY touched DESC LIMIT 1').fetchone()
                party = json.loads(row['state']) if row else None
                m = T.current(db, 'p'+str(port))
                matches = db.execute('SELECT count(*) FROM tournament_matches').fetchone()[0]
                reservations = db.execute('SELECT count(*) FROM tournament_reservations').fetchone()[0]
                node = db.execute('SELECT native_occupants FROM tournament_nodes WHERE node=?', ('p'+str(port),)).fetchone()
                occupants = node['native_occupants'] if node else None
                lobby = db.execute('SELECT players FROM lobbies WHERE node=?', ('p'+str(port),)).fetchone()
                active_players = lobby['players'] if lobby else None
                db.rollback()
            next_stage = ('in-game' if party and party.get('menu_started') else
                          party['phase'] if party else 'create')
            if next_stage != stage:
                stage, stage_at = next_stage, now
                print('Main-menu stage:', stage, flush=True)
            if not party or not party.get('menu_started'):
                sample = dict(stage=stage, sessions=sessions, matches=matches,
                              reservations=reservations, native_occupants=occupants, active_players=active_players)
                if not samples or samples[-1] != sample:
                    samples.append(sample)
                if sessions or matches or reservations or occupants not in (None, 0) or active_players not in (None, 0):
                    raise RuntimeError('Pre-Start isolation violated: '+json.dumps(sample))
            if party and partner is None:
                partner = Native(rig, 'partner', command_base(rig, 'partner', 'fteqw64') + [
                    '+set', 'vid_renderer', 'egl_headless', '-width', str(width), '-height', str(height),
                    '+set', 'lobby_dir', url,
                    '+set', 'lobby_hosts', '127.0.0.1 localhost', '+set', 'lobby_hosts_gen', '1',
                    '+set', 'lobby_dir_gen', '1', '+set', 'sv_dlURL', url,
                    '+set', 'rec_upload', '0', '+set', 'rec_hid_upload', '0',
                    '+set', 'ui_update', '0', '+name', 'Practice partner (test)'])
                natives.append(partner)
                partner.send('menu_restart')
                checks['create_from_mainmenu'] = not args.smoke
            if partner and not partner_opened and menu_elements(partner, rig):
                partner.send('ui_tournaments')
                partner_opened = True
            if now < action_at:
                time.sleep(.15)
                continue
            action_at = now+1.5
            if party and not party.get('menu_started'):
                roster = [p for p in party['players'] if p['role']=='player']
                peer = next((p for p in party['players'] if len(actors)>1 and p['who']==actors[1]['who']), None)
                chat = party.get('chat') or []
                # Re-sent until the line is in the room: the menu may not have adopted the room yet.
                if peer is not None and partner_greeted < 5 and not any(c['who'] == peer['who'] for c in chat):
                    partner.send('ui_tournament_say glhf! (practice partner)')
                    partner_greeted += 1
                if (not args.smoke and not partner_replied and actors
                        and any(c['who'] == actors[0]['who'] for c in chat)):
                    partner.send('ui_tournament_say I am a scripted test bot, but good luck out there.')
                    partner_replied = True
                if len(actors) > 1 and {c['who'] for c in chat} >= {actors[0]['who'], actors[1]['who']}:
                    checks['room_chat_both'] = True
                if peer is None:
                    if args.smoke and shot(partner, 'partner-browser.png'):
                        pass
                    else:
                        menu_click(partner, rig, 'mt_join0')
                elif peer['role']=='player':
                    if party['phase']=='lobby' and not peer['accepted']:
                        menu_click(partner, rig, 'mt_accept')
                    elif party['phase']=='draft' and party['turn_who']==peer['who']:
                        index = next(i for i,c in enumerate(party['maps']) if c['status']=='pool')
                        menu_map(partner, rig, index)
                    elif party['phase']=='loading' and not peer.get('menu_ready'):
                        menu_click(partner, rig, 'mt_ready')
                if args.smoke:
                    host = next(p for p in party['players'] if p['who']==party['host'])
                    if party['phase']=='lobby':
                        # Seats are an in-room host setting now (default 4).
                        if party['capacity'] == seats:
                            checks['create_from_mainmenu'] = True
                        if party['capacity'] != seats:
                            menu_tab_click(player, rig, 'mt_capacity' if party['capacity'] < seats else 'mt_capacity_down')
                        elif peer and peer['role']!='player':
                            shot(player, 'mt-lobby-waiting.png')
                            menu_tab_click(player, rig, 'mt_seat'+str(party['players'].index(peer)))
                        elif not host['accepted']:
                            menu_click(player, rig, 'mt_accept')
                        elif len(roster)==2 and all(p['accepted'] for p in roster):
                            checks['native_seat_accept_both'] = True
                            tiers = party['settings']['tiers']
                            if chat_said < 5 and not any(c['who'] == host['who'] for c in chat):
                                player.send('ui_tournament_say hello from the host')
                                chat_said += 1
                            if tour and tour_step < 8:
                                # The pool dialog and one live settings edit (T4 on, then off again).
                                step = ('mt_pool', None, 'mt-pool.png', 'mt_pool_cancel', 'mt_tier4', 15, 'mt_tier4', 7)[tour_step]
                                if step is None:
                                    tour_step += 1
                                elif isinstance(step, int):
                                    if tiers == step:
                                        checks['inroom_settings_edit_'+str(step)] = True
                                        tour_step += 1
                                elif step.endswith('.png'):
                                    shot(player, step)
                                    tour_step += 1
                                elif (menu_tab_click(player, rig, step) if step.startswith(('mt_pool', 'mt_tier'))
                                      and step != 'mt_pool_cancel' else menu_click(player, rig, step)):
                                    tour_step += 1
                            elif shot(player, 'mt-lobby.png'):
                                shot(partner, 'partner-lobby.png')
                            elif 'mt_view_players' in menu_elements(player, rig) and 'mt-lobby-players.png' not in shots:
                                if menu_click(player, rig, 'mt_view_players'):
                                    shots.add('mt-lobby-players.png')
                                    action_at = time.monotonic()+0.5
                            elif 'mt-lobby-players.png' in shots and shot(player, 'mt-lobby-players-tab.png'):
                                pass
                            else:
                                menu_click(player, rig, 'mt_lock')
                    elif party['phase']=='draft' and not shot(player, 'mt-draft.png') and not (
                            any(c['status']=='picked' for c in party['maps']) and shot(player, 'mt-draft-picks.png')
                            and shot(partner, 'partner-draft-picks.png')) and party['turn_who']==host['who']:
                        index = next(i for i,c in enumerate(party['maps']) if c['status']=='pool')
                        menu_map(player, rig, index)
                    elif party['phase']=='loading':
                        checks['native_draft_complete'] = bool(party['schedule'])
                        if shot(player, 'mt-ready-check.png'):
                            pass
                        elif not host.get('menu_ready'):
                            menu_click(player, rig, 'mt_ready')
                        elif len(roster)==2 and all(p.get('menu_ready') for p in roster):
                            checks['mainmenu_ready_both'] = True
                            checks['prestart_zero_game_state'] = occupants == 0 and not any((sessions,matches,reservations))
                            player.send('screenshot mainmenu-ready.png')
                            menu_click(player, rig, 'mt_start')
            elif not party and args.smoke:
                # Existing hit boxes tell us which of browser/setup is drawn.
                elements = menu_elements(player, rig)
                if 'mt_new' in elements and now-stage_at > 3 and shot(player, 'mt-browser.png'):
                    pass
                elif 'mt_new' in elements and 'mt-browser.png' not in shots:
                    pass
                elif 'mt_capacity' in elements and setup_steps < seats-2:
                    if menu_click(player, rig, 'mt_capacity'):
                        setup_steps += 1
                elif 'mt_create' in elements:
                    menu_click(player, rig, 'mt_create')
                else:
                    menu_click(player, rig, 'mt_new')
            elif party and party.get('menu_started') and m:
                checks['menu_started_real_match'] = (m['id']==party['id'] and m['node']=='p'+str(port)
                    and party['addr']==endpoint and matches==1 and reservations==1)
                launches = [e for e in S.playtest_events if e['ok']==1 and e['launch']]
                checks['native_handoff_both'] = len({e['me'] for e in launches
                    if e['launch']['id']==m['id'] and e['launch']['addr']==endpoint})==2
                checks['native_occupants_two'] = occupants == 2 and active_players == 2
                checks['native_bound_identities_two'] = sessions == 2 and all(p.get('ready') for p in m['players'] if p['role']=='player')
                if partner and m['phase']=='loading':
                    peer = next((p for p in m['players'] if len(actors)>1 and p['who']==actors[1]['who']), None)
                    if peer and not peer['ready']:
                        partner.send('tourney_open')
                        click(partner, 'tour_ready')
                if args.smoke and m['phase']=='loading':
                    host = next(p for p in m['players'] if p['who']==m['host'])
                    player.send('tourney_open')
                    if not host['ready']:
                        click(player, 'tour_ready')
                    elif all(p['ready'] for p in m['players'] if p['role']=='player'):
                        click(player, 'tour_start')
                if m['phase']=='live':
                    checks['server_live'] = True
                    if args.smoke:
                        player.send('screenshot tournament-live.png')
                        break
            time.sleep(.15)
        if args.smoke and not all(checks.get(k, False) for k in (
                'create_from_mainmenu', 'native_seat_accept_both', 'native_draft_complete', 'room_chat_both',
                'mainmenu_ready_both', 'prestart_zero_game_state', 'menu_started_real_match',
                'native_handoff_both', 'native_occupants_two', 'native_bound_identities_two', 'server_live')):
            raise RuntimeError('Native smoke did not complete all main-menu/game gates')
        return 0
    except BaseException as exc:
        failure = str(exc) or type(exc).__name__
        raise
    finally:
        expected = ('create_from_mainmenu', 'native_seat_accept_both', 'native_draft_complete',
                    *(('room_chat_both',) if args.smoke else ()), 'mainmenu_ready_both', 'prestart_zero_game_state', 'menu_started_real_match',
                    'native_handoff_both', 'native_occupants_two', 'native_bound_identities_two', 'server_live')
        result = dict(ok=not failure and all(checks.get(k, False) for k in expected),
                      checks=checks, failure=failure, stage=stage, prestart_samples=samples,
                      menu_events=S.playtest_events, rig=str(rig),
                      scope='Local synthetic accounts/native menu actions and game load only; no human finish or deployment')
        (rig/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        cleanup_errors = []
        for native in reversed(natives):
            try:
                native.stop()
            except Exception as exc:
                cleanup_errors.append(native.name+': '+str(exc))
        web.shutdown()
        web_thread.join(timeout=5)
        if not args.smoke and consent.is_file() and 'fixture' not in consent.read_text():
            copy_file(consent, human)
        if cleanup_errors:
            print('OWNED CLEANUP NEEDS ATTENTION: '+'; '.join(cleanup_errors), file=sys.stderr, flush=True)
        else:
            print('Owned clients/server/backend stopped. Session retained:', rig, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--content', type=Path, required=True)
    ap.add_argument('--compiler', type=Path, required=True)
    ap.add_argument('--client', type=Path, required=True)
    ap.add_argument('--server', type=Path, required=True)
    ap.add_argument('--template', type=Path, help='reuse an immutable prepared template into a fresh session; source/native/VM hashes checked')
    ap.add_argument('--download', action='store_true', help='fetch only the six named public game BSPs if absent')
    ap.add_argument('--prepare-only', action='store_true')
    ap.add_argument('--smoke', action='store_true', help='synthetic automated actor; bounded actual native UI checks')
    ap.add_argument('--renderer', default='egl_headless', help='smoke renderer only; manual playtest uses OpenGL')
    ap.add_argument('--width', type=int, default=1280, help='native client width, including bounded layout checks')
    ap.add_argument('--height', type=int, default=800, help='native client height')
    ap.add_argument('--tour', action='store_true', help='smoke also opens the pool/tier dialogs, makes one live settings edit and screenshots each stage')
    ap.add_argument('--smoke-seats', type=int, choices=range(2,9), default=2, help='configured capacity; smoke still seats two real native actors')
    args = ap.parse_args()
    if args.width < 640 or args.height < 480:
        ap.error('native fixture requires width>=640 and height>=480')
    # A terminating supervisor/terminal should unwind owned native processes,
    # not orphan their independent sessions. No handler targets unrelated PIDs.
    def stop_signal(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_signal)
    for key in ('content','compiler','client','server'):
        setattr(args, key, getattr(args,key).resolve())
    try:
        rig, manifest = prepare(args)
        print('Prepared isolated local test:', rig, flush=True)
        if args.prepare_only:
            return 0
        from tournament_qualify import qualify_prepared
        cached = cached_qualification(rig, manifest, args.work_root.resolve()/'cache')
        if cached.is_file():
            print('Reusing native map qualification (maps, server and VM unchanged).', flush=True)
            copy_file(cached, rig/'fixture-qualifications.json')
        else:
            print('Observing native map/course identities in a separate disposable server.\n'
                  'Local catalogue T1/provenance labels are synthetic, not real difficulty data.', flush=True)
            qualify_prepared(rig, args.compiler, fixture_approve=True)
            copy_file(rig/'fixture-qualifications.json', cached)
            for old in sorted(cached.parent.glob('qualification-*.json'), key=lambda f: f.stat().st_mtime)[:-3]:
                old.unlink()
        return run(args, rig, manifest)
    except KeyboardInterrupt:
        print('Local playtest stopped by operator.', flush=True)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
