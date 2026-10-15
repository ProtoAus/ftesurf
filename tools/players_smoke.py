#!/usr/bin/env python3
"""Bounded native Players UX fixture; NOT 64 network clients or backend authority.

Builds an owned source overlay using build.ps1 -NoDeploy (never -Engine).
Only cl_players' roster reads are substituted; production rendering, list and
input/search/profile functions run in the native engine. Loopback HTTP serves
explicitly synthetic search/profile responses. Retains logs, screenshots and
pixel-difference measurements; visual quality remains a human judgement.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
WHO = 'abcdef123456'
ACTIVE_STATUS = 'Status: active; owned wrappers: build/runtime; loopback HTTP may start.'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Overlay seam changed: ' + old)
    return text.replace(old, new)


def click(control):
    return ('hud_edit ui hover %s\nwaitms 200\nhud_edit ui down mouse1\n'
            'waitms 100\nhud_edit ui up mouse1\nwaitms 800\n' % control)


def desktop_idle():
    result = subprocess.run(['pwsh', '-NoProfile', '-Command',
        'if (Get-Process ftesurf64,fteqw64,fteqwsv64,fteqcc64,fteqcc '
        '-ErrorAction SilentlyContinue) { exit 2 }'], check=False, timeout=15)
    return result.returncode == 0


def wait_owned(command, children, *, timeout, **kwargs):
    # Never hard-kill a wrapper: its finally owns native handles and junctions.
    process = subprocess.Popen(command, **kwargs)
    children.append(process)
    process.wait(timeout=timeout)
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command)
    return process


def retained_junctions(out):
    paths = []
    for rig in out.glob('*/ftesurf-runlines-*'):
        for name in ('maps', 'gfx', 'models', 'particles'):
            path = rig / 'ftesurf' / name
            try:
                if path.lstat().st_file_attributes & 0x400:
                    paths.append(str(path))
            except FileNotFoundError:
                pass
    return paths


def record_lifecycle(out, owner, children):
    alive = [p.pid for p in children if p.poll() is None]
    codes = [p.poll() for p in children]
    try:
        idle = desktop_idle()
        links = retained_junctions(out)
        observed = True
    except (OSError, subprocess.SubprocessError):
        idle, links, observed = False, [], False
    verified = observed and not alive and all(code == 0 for code in codes) and idle and not links
    result = {'active_wrapper_pids': alive, 'wrapper_exit_codes': codes,
              'native_compiler_idle': idle, 'retained_junctions': links,
              'observed': observed, 'verified': verified}
    (out / 'lifecycle.json').write_text(json.dumps(result, indent=2))
    status = ('Status: retained; wrappers exited; native/compiler idle and no content junctions verified.'
              if verified else 'Status: BLOCKED / cleanup-unverified; active owned wrapper PIDs %s; '
              'native/compiler idle %s; retained junctions %d. No discovered process was signalled.'
              % (alive, idle, len(links)))
    (out / 'OWNER.md').write_text(owner.replace(ACTIVE_STATUS, status))
    return result


def grade_log(text):
    phases = {m.group(1): text[m.end():].split('PLAYERS PHASE', 1)[0]
              for m in re.finditer(r'PLAYERS PHASE (\w+)\r?\n', text)}
    if set(phases) != {'inert', 'top', 'bottom', 'search', 'profile', 'back'}:
        raise ValueError('Missing or unexpected Players phase')
    def generation(phase):
        match = re.search(r'PLAYERS FIXTURE .* gen (\d+)', phases[phase])
        return int(match.group(1)) if match else -1
    def scroll(phase):
        match = re.search(r'players rows 64 scroll ([0-9.]+)', phases[phase])
        return match.group(1) if match else None
    restored = ('scores: pinned on surf_dune' in phases['back']
                and 'tab players ' in phases['back']
                and bool(re.search(r'players rows 64 .*profile\s*\n', phases['back'])))
    fresh = generation('back') > generation('profile') >= 0
    return {
        'inert renders exactly one real row': 'players rows 1 scroll 0.0' in phases['inert']
            and 'visible 0..0 drawn 1' in phases['inert'],
        'top rendered 64 synthetic rows': 'players rows 64 scroll 0.0' in phases['top'] and 'visible 0..' in phases['top'],
        'wheel down and release acted': all('sui_event '+edge+' mwheeldown took 1' in text for edge in ('down', 'up')),
        'last row rendered after scroll': bool(re.search(r'visible \d+\.\.63 drawn [1-9]', phases['bottom'])),
        'search response parsed': 'profile: search "Fixture" found 1' in text,
        'unacted result did not select profile': 'profile '+WHO not in phases['search'],
        'result click selected parsed profile': 'profile '+WHO in phases['profile'] and 'pf_h0' in text
            and 'profile: '+WHO+' on surf_dune: 0 times' in text,
        'Back restored pinned Players': restored and fresh,
        'Back advances roster draw generation': fresh,
        'Back preserved scroll': restored and fresh and scroll('bottom') is not None
            and scroll('bottom') == scroll('back'),
    }


def config(width, height, port):
    text = '''cfg_save_auto 0
con_savehistory 0
developer 1
log_developer 1
log_enable 1
log_dir logs
log_name runlines_smoke
con_notifytime 0
con_notifylines 0
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
vid_winmaximize 0
vid_width %d
vid_height %d
vid_conautoscale 1
sv_public 0
set players_fixture 0
waitms 2000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
set rec_terms 5
set hud_scale 2
set lobby_dir "http://127.0.0.1:%d"
scores open
waitms 500
scores tab players
waitms 800
echo PLAYERS PHASE inert
scores status
screenshot players_inert.png
set players_fixture 1
waitms 800
echo PLAYERS PHASE top
scores status
screenshot players_top.png
hud_edit ui hover pl_list
''' % (width, height, port)
    text += ('hud_edit ui down mwheeldown\nwaitms 40\n'
             'hud_edit ui up mwheeldown\nwaitms 40\n') * 40
    text += '''waitms 800
echo PLAYERS PHASE bottom
scores status
screenshot players_bottom.png
scores find Fixture
waitms 2000
echo PLAYERS PHASE search
scores status
screenshot players_search.png
'''
    text += click('pf_h0')
    text += '''waitms 1000
echo PLAYERS PHASE profile
scores status
screenshot players_profile.png
'''
    text += click('pf_onback')
    text += '''echo PLAYERS PHASE back
scores status
screenshot players_back.png
echo RUNLINES COMPLETE
quit
'''
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True,
                    help='NEW players-runtime-* directory under an owned task root')
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--http-port', type=int, default=27638)
    ap.add_argument('--sizes', nargs='+', default=['1280x720', '800x600'])
    a = ap.parse_args()
    out = a.output_dir.resolve()
    if out.exists() or not out.name.startswith('players-runtime-'):
        raise SystemExit('Use a new players-runtime-* output directory')
    if not any((p / 'OWNER.md').is_file() for p in out.parents):
        raise SystemExit('Parent task OWNER.md required')
    sizes = [tuple(map(int, s.split('x'))) for s in a.sizes]
    if any(w < 640 or h < 480 or w > 1920 or h > 1080 for w, h in sizes):
        raise SystemExit('Sizes must be bounded 640x480..1920x1080')
    if os.name != 'nt':
        raise SystemExit('Native Windows rig required')
    if not desktop_idle():
        raise SystemExit('Desktop busy; no owner/peer process will be signalled')
    out.mkdir()
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    owner = ('# Players runtime UX fixture\nOwner: P722 Players continuation.\n'
             f'Created UTC: {datetime.now(timezone.utc).isoformat()}\n'
             f'Base: {head}\nOwned paths: this directory and descendants only.\n'
             f'{ACTIVE_STATUS}\n'
             'Retention: preserve source overlay, logs, progs and screenshots for review.\n')
    (out / 'OWNER.md').write_text(owner)
    (out / 'predictions.md').write_text(
        'Control: fixture disabled renders one real local row, not 64.\n'
        'Subject: 64 synthetic rows; wheel gestures reach row index 63.\n'
        'Unacted search result remains a dropdown; released result selects its identity.\n'
        'Released Back requires pinned Players, a fresh roster draw generation and the same scroll.\n'
        'Timeouts never kill cleanup-owning wrappers; uncertain cleanup stays BLOCKED.\n'
        'Native screenshots must differ.\n'
        'Pixels need visual inspection; nonzero differences alone do not establish layout.\n')
    protected = [Path(base) / 'ftesurf' / name for base in ('C:/FTESurf', 'C:/FTEQuake')
                 for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'ftesurf.cfg')]
    before = {str(p): sha(p) for p in protected if p.is_file()}
    overlay = out / 'source'; overlay.mkdir()
    shutil.copytree(ROOT / 'src', overlay / 'src')
    shutil.copyfile(ROOT / 'ENGINE.txt', overlay / 'ENGINE.txt')
    src = overlay / 'src'
    shutil.copyfile(ROOT / 'tools/fixtures/players_roster.qc', src / 'client/players_roster.qc')
    manifest = src / 'cl_progs.src'
    manifest.write_text(replace_once(manifest.read_text(), 'client/cl_players.qc',
        'client/players_roster.qc\nclient/cl_players.qc'))
    players = src / 'client/cl_players.qc'
    text = players.read_text().replace('getplayerkeyvalue(', 'PlayersFixture_Key(')
    text = replace_once(text, 'lp = \'0 0 0\';', 'PlayersFixture_Begin();\n\tlp = \'0 0 0\';')
    text = replace_once(text, 'j = slots[i];', 'PlayersFixture_Row(i);\n\t\tj = slots[i];')
    text = replace_once(text, 'IN THIS SERVER: %g', 'SYNTHETIC TEST FIXTURE roster: %g')
    players.write_text(text)
    scores = src / 'client/cl_scores.qc'
    scores.write_text(replace_once(scores.read_text(),
        'print(sprintf("  players rows %g', 'PlayersFixture_Status();\n\tprint(sprintf("  players rows %g'))
    cmd = ['pwsh', '-NoProfile', '-File', str(src / 'build.ps1'), '-NoDeploy', '-Jobs', '8']
    children = []
    try:
        with (out / 'build.log').open('w') as log:
            wait_owned(cmd, children, cwd=src, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    except (subprocess.SubprocessError, OSError):
        record_lifecycle(out, owner, children)
        raise
    builds = list((overlay / 'rig').glob('build-nodeploy-*'))
    if len(builds) != 1:
        raise RuntimeError('Expected one isolated NoDeploy output')
    progs = builds[0]
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            q = parse_qs(urlsplit(self.path).query)
            requests.append(q)
            if 'players' in q:
                body = {'players': [{'who': WHO, 'name': 'FIXTURE Search Result', 'n': 0, 'src': 'ranked', 'av': 0}]}
            elif 'on' in q:
                body = {'who': WHO, 'name': 'FIXTURE Search Result', 'on': q['on'][0], 'rows': [], 'av': 0}
            else:
                body = {'map': 'surf_dune', 'rows': []}
            data = json.dumps(body).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    web = ThreadingHTTPServer(('127.0.0.1', a.http_port), Handler)
    thread = threading.Thread(target=web.serve_forever, daemon=True); thread.start()
    checks = {}
    try:
        from PIL import Image, ImageChops
        for w, h in sizes:
            arm = out / ('%dx%d' % (w, h)); arm.mkdir()
            cfg = arm / 'control.cfg'; cfg.write_text(config(w, h, a.http_port))
            command = [sys.executable, '-B', str(ROOT / 'tools/runlines_smoke.py'), str(cfg),
                '--mount', '--content', str(a.content), '--output-dir', str(arm), '--timeout', '120',
                '--ssqc', str(progs / 'qwprogs.dat'), '--csqc', str(progs / 'csprogs.dat'),
                '--mqc', str(progs / 'menu.dat')]
            with (arm / 'harness.log').open('w') as log:
                wait_owned(command, children, stdout=log, stderr=subprocess.STDOUT, timeout=140)
            rigs = list(arm.glob('ftesurf-runlines-*'))
            gd = rigs[0] / 'ftesurf'
            text = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
            results = grade_log(text)
            shots = gd / 'screenshots'
            pixels = {}
            for first, second in [('inert', 'top'), ('top', 'bottom'), ('search', 'profile'), ('profile', 'back')]:
                im1 = Image.open(shots / ('players_'+first+'.png')).convert('RGB')
                im2 = Image.open(shots / ('players_'+second+'.png')).convert('RGB')
                if im1.size != (w, h) or im2.size != (w, h):
                    raise ValueError('Screenshot size does not match measured arm')
                # Central board region avoids unrelated peripheral HUD ink.
                box = (w//8, h//8, w*7//8, h*7//8)
                diff = ImageChops.difference(im1.crop(box), im2.crop(box))
                data = diff.tobytes()
                count = sum(1 for i in range(0, len(data), 3) if max(data[i:i+3]) > 20)
                pixels[first+'->'+second] = count
                results['pixels discriminate '+first+'->'+second] = count > 100
            (arm / 'pixels.json').write_text(json.dumps(pixels, indent=2))
            checks[arm.name] = results
    finally:
        web.shutdown(); web.server_close(); thread.join(timeout=5)
        after = {str(p): sha(p) for p in protected if p.is_file()}
        (out / 'isolation.json').write_text(json.dumps({'before': before, 'after': after,
            'unchanged': before == after, 'fixture_csprogs': sha(progs / 'csprogs.dat')}, indent=2))
        (out / 'http.json').write_text(json.dumps(requests, indent=2))
        lifecycle = record_lifecycle(out, owner, children)
    checks['lifecycle'] = {'wrappers/children/junction cleanup observed': lifecycle['verified']}
    checks['isolation'] = {'installed progs/configs unchanged': before == after}
    (out / 'verdict.json').write_text(json.dumps(checks, indent=2))
    print(json.dumps(checks, indent=2))
    return 0 if all(all(arm.values()) for arm in checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
