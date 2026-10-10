#!/usr/bin/env python3
"""Isolated actual-scoreboard route controls. No owner configs/data or device claims."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time

from p590bridge import sha
from p598build import build, ROOT
from test_ui_modern import make_map

ARMS = ('legacy', 'native1', 'native2', 'absent', 'oldplugin', 'oldengine')


def compile_client(rig):
    src = ROOT / 'src'
    lines = (src / 'cl_progs.src').read_text(encoding='utf-8').splitlines()
    result = [os.path.relpath(rig / 'csprogs.dat', src).replace('\\', '/')]
    for line in lines[1:]:
        name = line.strip()
        if name == 'client/cl_main.qc':
            result.append('../tools/fixtures/p603scores_prefix.qc')
        if name == 'client/cl_scores_native.qc':
            result.append('../tools/fixtures/p603life_prefix.qc')
        result.append(line)
        if name == 'client/cl_scores_native.qc':
            result.append('../tools/fixtures/p603life_postfix.qc')
    result.append('../tools/fixtures/p603scores_runtime.qc')
    result.append('../tools/fixtures/p603follow_runtime.qc')
    result.append('../tools/fixtures/p603http_runtime.qc')
    result.append('../tools/fixtures/p603life_runtime.qc')
    result.append('../tools/fixtures/p603font_runtime.qc')
    result.append('../tools/fixtures/p603dense_runtime.qc')
    #Old-style fteqcc rejects absolute input paths. Use an owned same-directory
    #manifest with unchanged relative inputs, exactly as build.ps1 -NoDeploy.
    manifest = src / (rig.name + '-cl_progs.src')
    if manifest.exists(): raise RuntimeError('control manifest already exists')
    manifest.write_text('\n'.join(result) + '\n', encoding='utf-8')
    shutil.copy2(manifest, rig / 'cl_progs.src')
    log = rig / 'compile-client.log'
    try:
        with log.open('w', encoding='utf-8') as out:
            r = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', manifest.name],
                               cwd=src, stdout=out, stderr=subprocess.STDOUT)
    finally:
        manifest.unlink()
    if r.returncode or 'Done. 0 warnings' not in log.read_text(errors='replace'):
        raise RuntimeError('actual-source fixture compilation failed: ' + str(log))


def config(arm, port):
    width, height = (960, 540) if arm == 'native2' else (1920, 1080)
    scale = 1.5 if arm == 'native2' else 3
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name scores',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             'cl_maxfps 100', 'vid_vsync 0', 'vid_fullscreen 0', 'vid_winmaximize 0',
             'vid_width 1920', 'vid_height 1080', 'vid_conautoscale 0',
             f'vid_conwidth {width}', f'vid_conheight {height}', f'set hud_scale {scale}',
             'scr_consize 0', 'vid_srgb 0', 'v_gamma 1', 'v_contrast 1', 'v_brightness 0',
             'name P603Fixture', 'waitms 1500', 'menu_restart', 'waitms 700', 'ui_close']
    if arm != 'absent': lines += ['plug_load ui_imgui', 'ui_imgui_status']
    lines += [f'connect 127.0.0.1:{port}', 'waitms 6500', 'ui_close',
              'set ui_native_scores ' + ('0' if arm == 'legacy' else '1'),
              'set ui_native_scores_font 13',
              'scores tab local', '+showscores', 'waitms 1000',
              'p603 probe peek', 'screenshot peek']
    if arm.startswith('native'):
        lines += ['p603 move watch', 'waitms 200', 'p603 down', 'waitms 200',
                  'p603 up', 'waitms 300']
    lines += ['p603 probe passive_click', 'p603 pin', 'p603 unpin',
              'waitms 1000', 'p603 probe pinned', 'screenshot pinned']

    def click(target):
        return ['p603 move ' + target, 'waitms 200', 'p603 down', 'waitms 200',
                'p603 up', 'waitms 500']

    if arm.startswith('native'):
        lines += click('line') + ['waitms 1000', 'p603 probe line_control', 'scores lines']
        lines += click('line') + ['p603 probe line_off']
    else:
        #Legacy's responsive budget omits the line column in this layout. Its
        #documented command is the acting line-hand-off control, not a fake hit.
        lines += ['scores line 0', 'waitms 1500', 'p603 probe line_control', 'scores lines',
                  'scores line 0', 'waitms 500', 'p603 probe line_off']
    if arm.startswith('native'):
        lines += click('next') + ['p603 probe next', 'screenshot next']
        lines += ['p603 move previous', 'waitms 200', 'p603 down', 'waitms 200',
                  'p603 up', 'waitms 500', 'p603 probe previous']
    reset = ['-showscores', 'replay off', 'waitms 200', 'scores tab local', '+showscores',
             'waitms 500', 'p603 pin', 'p603 unpin', 'waitms 700']
    lines += click('watch') + ['p603 probe watch_control', 'replay status'] + reset
    lines += ['p603 probe stale_control']
    #A same-path rebuild must invalidate authority even when all displayed bytes match.
    lines += ['p603 move watch', 'waitms 200', 'p603 down', 'waitms 200',
              'p603 rescan', 'waitms 500', 'p603 up', 'waitms 500',
              'p603 probe stale_rescan', 'screenshot stale_rescan'] + reset
    lines += ['p603 probe focus_control', 'p603 move watch', 'waitms 200', 'p603 down', 'waitms 200',
              'p603 focus -1 0', 'waitms 300', 'p603 up', 'waitms 300',
              'p603 probe keyboard_lost', 'p603 focus -1 1', 'waitms 700',
              'p603 probe keyboard_back'] + reset
    lines += ['toggleconsole', 'waitms 700', 'p603 probe console', 'toggleconsole',
              'waitms 700', 'p603 probe console_back', '-showscores', 'replay off', 'waitms 500',
              'p603 probe closed1']
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['waitms 500', 'p603 probe closed2']
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['echo P603 FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def seed(game, rows=8):
    (game / 'maps/zones/local').mkdir(parents=True)
    region = {'points': [[-400, -400], [-300, -400], [-300, -300], [-400, -300]],
              'bottom': 0, 'height': 100}
    end = dict(region, points=[[300, 300], [400, 300], [400, 400], [300, 400]])
    zones = {'tracks': {'main': {'zones': {
        'segments': [{'checkpoints': [{'regions': [region]}]}], 'end': {'regions': [end]}}}}}
    for mapname in ('p603scores', 'p603scores.map'):
        (game / f'maps/zones/local/{mapname}.json').write_text(json.dumps(zones))
        folder = game / f'data/runs/{mapname}/main'
        folder.mkdir(parents=True)
        for row in range(rows):
            head = (f'FTESURF-REC 5\nmap {mapname}\nowner "P603 Row{row}"\ntrack 0\n'
                    'startseg 0\nleg 0\ntickrate 0.015\nflags 0\nbegin\n')
            samples = ''.join(f'{i} {i} 0 80 100 0 0 0 0 0 0 1 0 0 0\n' for i in range(20))
            (folder / f'{100+row:07d}_p603{row}_pb.rec').write_text(head + samples + f'end {100+row} 20 0 0\n')


def run(a):
    if a.out is None:
        raise RuntimeError('new runtime arms require --out beneath an owned task root')
    out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in [out, *out.parents]):
        raise RuntimeError('--out requires an ancestor OWNER.md before population')
    out.mkdir(parents=True, exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix='p603-scores-', dir=out))
    (rig / 'P603_RIG.txt').write_text('Owned scoreboard controls. No owner/player data.\n')
    compile_client(rig)
    if a.http or a.dense:
        from p603http import compile_server
        compile_server(rig)
    plugin = a.plugin or build(a.fte.resolve(), rig / 'native-build', a.cxx.resolve())
    report = {'follow': a.follow, 'http': a.http, 'http_version': 2, 'life': a.life,
              'dense': a.dense, 'dense_http': a.dense, 'font': a.font, 'font_fallback': a.font_fallback, 'utc': datetime.now(timezone.utc).isoformat(), 'csprogs_sha256': sha(rig / 'csprogs.dat'),
              'plugin_sha256': sha(plugin), 'renderer': a.renderer, 'planned_arms': a.arms, 'arms': {}}
    for arm in a.arms:
        root = rig / arm
        game = root / 'ftesurf'
        game.mkdir(parents=True)
        (game / 'cfg').mkdir()
        (game / 'cfg/default.cfg').write_text('cfg_save_auto 0\n')
        (game / 'downloads/csprogsvers').mkdir(parents=True)
        for folder in ('glsl', 'scripts', 'particles', 'models', 'gfx/fonts'):
            source = ROOT / 'ftesurf' / folder
            if not source.is_dir(): source = Path('C:/FTESurf/ftesurf') / folder
            if source.is_dir(): shutil.copytree(source, game / folder)
        (game / 'maps').mkdir(exist_ok=True)
        (game / 'maps/p603scores.map').write_text(make_map())
        seed(game, rows=32 if a.dense else 8)
        if a.follow:
            from p603follow import seed_boards
            seed_boards(game)
        shutil.copy2(rig / 'csprogs.dat', game / 'csprogs.dat')
        for name in ('qwprogs.dat', 'menu.dat'):
            source = rig / name if (a.http or a.dense) and name == 'qwprogs.dat' else a.qc_artifacts / name
            shutil.copy2(source, game / name)
        subprocess.run([os.sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                       check=True, stdout=subprocess.DEVNULL)
        engine = a.old_engine if arm == 'oldengine' else a.engine
        if engine is None: raise RuntimeError('oldengine arm needs --old-engine')
        shutil.copy2(engine, root / 'ftesurf64.exe')
        shutil.copy2(a.server, root / 'fteqwsv64.exe')
        if arm != 'absent':
            source = a.old_plugin if arm == 'oldplugin' else plugin
            if source is None: raise RuntimeError('oldplugin arm needs --old-plugin')
            shutil.copy2(source, root / 'fteplug_ui_imgui_x64.dll')
        (root / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfScoresFixture\n'
                                         'NAME "Native scoreboard fixture"\nBASEGAME ftesurf\n'
                                         'DISABLEHOMEDIR 1\nMAINCONFIG p603-unused\n')
        port = None
        for candidate in range(27620, 27519, -1):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                try: s.bind(('127.0.0.1', candidate))
                except OSError: continue
                port = candidate
                break
        if port is None: raise RuntimeError('no free designated dedicated test port')
        stub = None
        if a.http or a.dense:
            from p603http import start_stub
            if a.dense:
                from p603dense_http import board32
                stub = start_stub(root, board32)
            else: stub = start_stub(root)
        cfg = config(arm, port)
        if a.dense:
            from p603dense import config_dense
            cfg = config_dense(cfg, arm)
            from p603dense_http import extend
            cfg = extend(cfg, arm, stub.server_port)
        if a.follow:
            from p603follow import extend_config
            cfg = extend_config(cfg, arm)
        if a.http:
            from p603http import extend_config as extend_http
            cfg = extend_http(cfg, arm, stub.server_port)
        if a.life:
            from p603life import extend_config as extend_life
            cfg = extend_life(cfg, arm)
        if a.font:
            from p603font import extend_config as extend_font
            cfg = extend_font(cfg, arm, a.font_fallback)
        (game / 'probe.cfg').write_text(cfg)
        svcmd = [str(root / 'fteqwsv64.exe'), '-basedir', str(root), '-nohome', '-noplugins',
                 '-port', str(port), '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0',
                 '+set', 'lobby_dir', '', '+map', 'p603scores.map']
        clcmd = [str(root / 'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound', '-nocdaudio',
                 '-window', '+set', 'plug_loaddefault', '0', '+set', 'vid_width', '1920',
                 '+set', 'vid_height', '1080', '+set', 'vid_fullscreen', '0',
                 '+set', 'vid_winmaximize', '0', '+set', 'vid_renderer', a.renderer,
                 '+set', 'cfg_save_auto', '0', '+exec', 'probe.cfg']
        with (root / 'server.log').open('w') as so, (root / 'launch.log').open('w') as co:
            server = subprocess.Popen(svcmd, cwd='C:/FTESurf', stdout=so, stderr=subprocess.STDOUT)
            client = None
            try:
                time.sleep(2)
                if server.poll() is not None: raise RuntimeError('owned server exited: ' + str(root))
                client = subprocess.Popen(clcmd, cwd='C:/FTESurf', stdout=co, stderr=subprocess.STDOUT)
                code = client.wait(timeout=240 if a.life or a.font or a.dense else 180 if a.http else 100)
            finally:
                for p in (client, server):
                    if p is not None and p.poll() is None:
                        p.terminate()
                        try: p.wait(timeout=10)
                        except subprocess.TimeoutExpired: p.kill(); p.wait()
                if stub is not None:
                    stub.shutdown()
                    stub.server_close()
                    stub.worker.join(timeout=10)
                    if stub.worker.is_alive(): raise RuntimeError('owned HTTP thread failed to stop')
        report['arms'][arm] = {'returncode': code, 'port': port, 'engine_sha256': sha(root / 'ftesurf64.exe'),
                              'plugin_sha256': sha(root / 'fteplug_ui_imgui_x64.dll') if arm != 'absent' else None,
                              'qwprogs_sha256': sha(game / 'qwprogs.dat'), 'csprogs_sha256': sha(game / 'csprogs.dat'),
            'menu_sha256': sha(game / 'menu.dat'), 'server_sha256': sha(root / 'fteqwsv64.exe'),
            'client_pid': client.pid, 'server_pid': server.pid}
        (rig / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Completed', arm, root)
    print('Runtime rig', rig)
    return rig


def grade(rig):
    errors = []
    try:
        report = json.loads((rig / 'report.json').read_text())
    except (OSError, ValueError):
        return ['missing/invalid report']
    if report.get('dense'):
        from p603dense import grade_dense
        return grade_dense(rig, report)
    required = ('peek', 'passive_click', 'pinned', 'line_control', 'line_off',
                'watch_control', 'stale_control', 'stale_rescan', 'focus_control',
                'keyboard_lost', 'keyboard_back', 'console', 'console_back', 'closed1', 'closed2')
    if not report.get('arms'): errors.append('no acting arms')
    if set(report.get('planned_arms', ())) != set(report.get('arms', {})):
        errors.append('planned/acting arm set differs')
    for arm, result in report.get('arms', {}).items():
        def need(ok, why):
            if not ok: errors.append(arm + ': ' + why)
        need(arm in ARMS, 'unknown arm')
        logs = list((rig / arm / 'ftesurf/logs').glob('scores*.log'))
        if len(logs) != 1:
            errors.append(arm + ': unique log required'); continue
        text = logs[0].read_text(errors='replace')
        need(result.get('returncode') == 0, 'client did not exit cleanly')
        need(text.count('P603 FINISHED') == 1, 'completion marker missing/duplicated')
        need(report.get('font') or 'P603 FONT ' not in text, 'font evidence without planned gate')
        need(not re.search(r'Unknown command|QC runtime error|CSQC_Abort|Menu_Abort|Shader double free|VK_ERROR_DEVICE_LOST|ERROR: vk|failed: Device lost', text, re.I),
             'runtime/command/resource error')
        shots = ('peek', 'pinned', 'stale_rescan') + (('next',) if arm.startswith('native') else ())
        for shot in shots:
            paths = list((rig / arm / 'ftesurf/screenshots').glob(shot + '.*'))
            need(len(paths) == 1, 'missing/duplicated screenshot ' + shot)
        captures = {}
        for kind, name, body in re.findall(r'P603 (STATE|OWNER|ACTIVE|LINE) (\w+) ([^\r\n]+)', text):
            key = kind, name
            need(key not in captures, 'duplicated ' + kind + '/' + name)
            captures[key] = {k: float(v) for k, v in re.findall(r'(\w+)=(-?[0-9]+(?:\.[0-9]+)?)', body)}
        native = arm.startswith('native')
        names = required + (('next', 'previous') if native else ())
        backend = {'gl': 'OpenGL', 'd3d9': 'Direct3D9', 'd3d11': 'Direct3D11', 'vk': 'Vulkan'}.get(report.get('renderer', 'gl'))
        need(backend is not None and (backend + ' renderer initialized') in text,
             'requested renderer not positively initialized (fallback is not parity)')
        fields = {'STATE': {'h', 'painted', 'failed', 'revision', 'page', 'rows'},
                  'OWNER': {'held', 'pin', 'cursor', 'focus', 'down', 'taken'},
                  'ACTIVE': {'watch', 'samples', 'lines'}, 'LINE': {'ready', 'samples'}}
        for name in names:
            for kind, expected in fields.items():
                need(set(captures.get((kind, name), {})) == expected, 'missing/malformed ' + kind + '/' + name)
        if any((kind, name) not in captures or set(captures[(kind, name)]) != fields[kind]
               for kind in fields for name in names): continue
        def get(kind, name, field): return captures[kind, name][field]
        need(get('STATE', 'peek', 'rows') == 8, 'actual local rows did not populate')
        for name in ('peek', 'passive_click'):
            need(get('OWNER', name, 'held') == 1 and get('OWNER', name, 'pin') == 0 and
                 get('OWNER', name, 'cursor') == 0 and get('ACTIVE', name, 'watch') == 0,
                 'passive peek/cursor policy ' + name)
        for name in ('pinned', 'stale_control', 'focus_control'):
            need(get('OWNER', name, 'held') == 1 and get('OWNER', name, 'pin') == 1 and
                 get('OWNER', name, 'cursor') != 0, 'pin control did not act ' + name)
            need((get('STATE', name, 'h') > 0) == native and
                 get('STATE', name, 'painted') == int(native), 'native/fallback route ' + name)
        need(get('ACTIVE', 'line_control', 'lines') == 1 and get('LINE', 'line_control', 'ready') == 1 and
             get('LINE', 'line_control', 'samples') == 20, 'actual line control did not build once')
        need(get('ACTIVE', 'line_off', 'lines') == 0, 'line off control did not act')
        need('scores: line 1 on: l:data/runs/p603scores.map/main/0000100_p6030_pb.rec' in text,
             'line control selected wrong row identity')
        need(get('ACTIVE', 'watch_control', 'watch') == 1 and
             get('ACTIVE', 'watch_control', 'samples') == 20, 'actual Watch_Open control did not act')
        watch_text = text.partition('P603 STATE watch_control')[0]
        watch_text = watch_text.rsplit('P603 RECT ' + ('previous' if native else 'line_off'), 1)[-1]
        need(re.search(r'replay: data/runs/p603scores\.map/main/0000100_p6030_pb\.rec\s+P603 Row0\s+0:01\.500\s+20 samples', watch_text),
             'watch control selected wrong row identity')
        need(get('STATE', 'watch_control', 'h') == 0 and get('OWNER', 'watch_control', 'pin') == 0,
             'watch hand-off did not release table')
        if arm == 'oldengine':
            caps = re.findall(r'P603 CAP gamefocus=([01]) model=([01])', text)
            need(len(caps) == 1 and caps[0][0] == '0', 'old engine missing-focus subject did not act')
            need(result.get('plugin_sha256') == report.get('plugin_sha256'), 'old engine must use current plugin')
        if native:
            need(get('STATE', 'next', 'page') == 6 and get('STATE', 'previous', 'page') == 0,
                 'actual native page controls did not act')
            need(get('ACTIVE', 'stale_rescan', 'watch') == 0 and get('OWNER', 'stale_rescan', 'pin') == 1,
                 'same-path rescan retargeted held click')
            need(get('STATE', 'stale_rescan', 'revision') > get('STATE', 'stale_control', 'revision'),
                 'rescan subject never changed model')
            need(get('STATE', 'keyboard_lost', 'h') == 0 and get('ACTIVE', 'keyboard_lost', 'watch') == 0,
                 'keyboard-only focus loss retained/activated native owner')
            need(get('STATE', 'keyboard_back', 'h') > 0 and get('STATE', 'keyboard_back', 'painted') == 1,
                 'keyboard focus regain did not restore usable table')
            need(get('STATE', 'console_back', 'h') > 0 and get('STATE', 'console_back', 'painted') == 1,
                 'console regain did not restore usable table')
        need(get('OWNER', 'console', 'focus') == 0 and get('STATE', 'console', 'h') == 0,
             'console precedence subject never acted/released native')
        for name in ('closed1', 'closed2'):
            need(get('STATE', name, 'h') == 0 and get('STATE', name, 'painted') == 0 and
                 get('OWNER', name, 'held') == 0 and get('OWNER', name, 'pin') == 0 and
                 get('OWNER', name, 'cursor') == 0 and get('OWNER', name, 'down') == 0 and
                 get('OWNER', name, 'taken') == 0 and get('ACTIVE', name, 'watch') == 0,
                 'close did not release owners/buttons ' + name)
        if arm != 'absent':
            stats = re.findall(r'UIIMGUI STATUS ([^\r\n]+)', text)
            need(len(stats) >= 3, 'acting plugin status missing')
            if len(stats) >= 3:
                need(stats[-1] == stats[-2] and 'live=0' in stats[-1], 'steady closed native work/resources')
    if report.get('follow'):
        from p603follow import grade_follow
        errors += grade_follow(rig, report)
    if report.get('http'):
        from p603http import grade_http
        errors += grade_http(rig, report)
    if report.get('life'):
        from p603life import grade_life
        errors += grade_life(rig, report)
    if report.get('font'):
        from p603font import grade_font
        errors += grade_font(rig, report)
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--engine', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqw64.exe'))
    p.add_argument('--server', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqwsv64.exe'))
    p.add_argument('--qc-artifacts', type=Path)
    p.add_argument('--grade', type=Path)
    p.add_argument('--plugin', type=Path)
    p.add_argument('--old-plugin', type=Path)
    p.add_argument('--old-engine', type=Path)
    p.add_argument('--cxx', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--arms', nargs='+', choices=ARMS, default=['native1'])
    p.add_argument('--renderer', choices=('gl', 'd3d9', 'd3d11', 'vk'), default='gl')
    suite = p.add_mutually_exclusive_group()
    suite.add_argument('--follow', action='store_true', help='append finite-body finish/standing gate')
    suite.add_argument('--http', action='store_true', help='append loopback HTTP/identity/refresh gate')
    p.add_argument('--life', action='store_true', help='append input/lifecycle/fallback gate')
    suite.add_argument('--font', action='store_true', help='append bounded physical-font gate')
    suite.add_argument('--dense', action='store_true', help='bounded additive capacity/24-row page gate')
    p.add_argument('--font-fallback', action='store_true', help='expect older scoreboard provider to cover non-default sizes')
    p.add_argument('--out', type=Path, help='owned task-root output directory')
    a = p.parse_args()
    if not a.grade and a.qc_artifacts is None: p.error('--qc-artifacts is required for runtime')
    if (a.font or a.dense) and a.life: p.error('font/dense and lifecycle gates must run separately')
    if a.font_fallback and not a.font: p.error('--font-fallback requires --font')
    if a.font_fallback and any(not arm.startswith('native') for arm in a.arms):
        p.error('--font-fallback requires native arms with an explicitly supplied prior scoreboard plugin')
    rig = a.grade or run(a)
    errors = grade(rig)
    for error in errors: print('FAIL', error)
    print('Local-route failures:', len(errors))
    raise SystemExit(bool(errors))
    raise SystemExit(bool(errors))
