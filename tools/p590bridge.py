#!/usr/bin/env python3
"""Acting disposable MQC/CSQC bridge controls. Grade is portable; launch is Windows."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
from PIL import Image
from test_ui_modern import make_map

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('control', 'absent', 'subject1', 'subject2', 'fullview')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cfg(arm: str, port: int) -> str:
    provider = arm not in ('control', 'absent')
    vw, vh = (640, 360) if arm == 'subject2' else (320, 240)
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name bridge',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             'cl_maxfps 100', 'vid_vsync 0', 'vid_fullscreen 0', 'vid_winmaximize 0',
             'vid_width 640', 'vid_height 480', 'vid_conautoscale 0',
             f'vid_conwidth {vw}', f'vid_conheight {vh}', 'scr_consize 0',
             'vid_srgb 0', 'v_gamma 1', 'v_contrast 1', 'v_brightness 0',
             'set p590_menudraw 1', 'set p590_phase 0', 'set p590_failure 0',
             'set p590_menu_handle 0', 'set p590_client_handle 0',
             'waitms 1500']
    if provider:
        lines += ['plug_load p590bridge']
    lines += ['menu_restart', 'waitms 500', 'p590_menu show', 'waitms 400',
              'screenshot menu', 'p590_menu outside', 'p590_menu close',
              'waitms 400', 'set p590_phase 1', 'waitms 200', 'screenshot menu_close',
              'menu_restart', 'waitms 400', 'set p590_phase 2', 'waitms 200',
              'screenshot menu_restart', 'p590_menu hide', f'connect 127.0.0.1:{port}',
              'waitms 6500', 'set p590_phase 3', 'waitms 400', 'screenshot client',
              'p590_client outside', 'p590_client close', 'waitms 500',
              'set p590_phase 4', 'waitms 200', 'screenshot client_close']
    if provider:
        lines += ['p590_status', 'p590_menu show', 'waitms 400', 'set p590_phase 5',
                  'waitms 200', 'screenshot both', 'p590_menu hide',
                  'plug_close p590bridge', 'waitms 400', 'set p590_phase 6',
                  'waitms 200', 'screenshot plugin_off', 'plug_load p590bridge',
                  'waitms 400', 'set p590_phase 7', 'waitms 200', 'screenshot plugin_on',
                  'vid_restart', 'waitms 1600', 'set p590_phase 8', 'waitms 200',
                  'screenshot renderer', 'p590_status', 'set p590_failure 2',
                  'waitms 300', 'set p590_phase 9', 'waitms 200', 'screenshot draw_failed',
                  'set p590_failure 1', 'waitms 300', 'set p590_phase 10', 'waitms 200',
                  'screenshot open_failed', 'set p590_failure 0', 'waitms 500',
                  'set p590_phase 11', 'waitms 200', 'screenshot recovered',
                  'disconnect', 'waitms 500', 'p590_menu show', 'waitms 400',
                  'set p590_phase 12', 'waitms 200', 'screenshot disconnected',
                  'p590_status', 'p590_menu hide', f'connect 127.0.0.1:{port}',
                  'waitms 6500', 'set p590_phase 13', 'waitms 200',
                  'screenshot reconnected', 'p590_status']
    return '\n'.join(lines + ['echo P590 FINISHED', 'quit', ''])


def pixels(path: Path, native: bool) -> list[str]:
    errors = []
    im = Image.open(path).convert('RGB')
    if im.size != (640, 480):
        return [f'{path.name}: unexpected resolution {im.size}']
    points = {'before': ((50, 90), (255, 0, 0)),
              'inside': ((90, 90), (0, 255, 0) if native else (255, 255, 0)),
              'after': ((115, 90), (0, 0, 255)),
              'clip-top': ((90, 55), (255, 0, 0)),
              'clip-right': ((170, 90), (255, 0, 0)),
              'clip-bottom': ((90, 140), (255, 0, 0)),
              'restored': ((245, 90), (255, 255, 255)),
              'background': ((270, 180), (0, 0, 0))}
    for label, ((x, y), expected) in points.items():
        actual = im.getpixel((x*2, y*2))
        if max(abs(a-b) for a, b in zip(actual, expected)) > 8:
            errors.append(f'{path.name} {label}: expected {expected}, got {actual}')
    return errors


def grade(rig: Path) -> list[str]:
    errors = []
    report = json.loads((rig/'report.json').read_text())
    for arm in ARMS:
        root = rig/arm
        provider = arm not in ('control', 'absent')
        meta = report.get('arms', {}).get(arm, {})
        if meta.get('exit') != 0 or meta.get('timed_out'):
            errors.append(arm+': client did not finish normally')
        logs = list((root/'ftesurf/logs').glob('bridge*.log'))
        text = '\n'.join(p.read_text(errors='replace') for p in logs)
        if 'P590 FINISHED' not in text:
            errors.append(arm+': finish sentinel absent')
        if re.search(r'Unknown command|QC runtime error|Shader double free|CSQC_Abort|Menu_Abort', text, re.I):
            errors.append(arm+': command/runtime/resource error')
        for vm in ('menu', 'client'):
            if not re.search(rf'P590 QC INIT vm={vm} available={int(provider)} outside_open=0 builtin={int(arm != "control")}', text):
                errors.append(f'{arm}: {vm} init/guard did not act')
            if not re.search(rf'P590 QC DRAW vm={vm} .*native={int(provider)} .*before=1 after=1 legacy={int(not provider)}', text):
                errors.append(f'{arm}: {vm} mixed/legacy draw did not act')
            if not re.search(rf'P590 QC COMMAND vm={vm} command=outside .*result=0', text):
                errors.append(f'{arm}: {vm} outside-draw rejection absent')
            if provider:
                if not re.search(rf'P590 QC COMMAND vm={vm} command=close .*result=1 stale=0', text):
                    errors.append(f'{arm}: {vm} close/stale rejection absent')
                if not re.search(rf'P590 QC DRAW vm={vm} .*native=1 rejects=[5-9]', text):
                    errors.append(f'{arm}: {vm} invalid/duplicate/foreign rejection absent')
        shots = {'menu': provider, 'menu_close': provider, 'menu_restart': provider,
                 'client': provider, 'client_close': provider}
        if provider:
            shots.update(both=True, plugin_off=False, plugin_on=True, renderer=True,
                         draw_failed=False, open_failed=False, recovered=True,
                         disconnected=True, reconnected=True)
            if 'P590 ABI rejected=7 service=1' not in text:
                errors.append(arm+': ABI registration controls absent')
            for vm in (1, 2):
                if not re.search(rf'P590 DRAW vm={vm} .*ok=1 .*pixel=640x480 clip=120,120,300,240', text):
                    errors.append(f'{arm}: native VM {vm} physical dimensions/clip did not act')
            closes = re.findall(r'P590 CLOSE vm=([12]) handle=(\d+) reason=([1-5]) destroyed=([01])', text)
            if not closes or any(c[3] != '1' for c in closes):
                errors.append(arm+': owner cleanup did not destroy every allocated texture')
            for reason in range(1, 6):
                if not any(c[2] == str(reason) for c in closes):
                    errors.append(f'{arm}: cleanup reason {reason} absent')
            keys = [(c[0], c[1]) for c in closes]
            if len(keys) != len(set(keys)):
                errors.append(arm+': duplicate owner release')
            opened = re.findall(r'P590 OPEN vm=([12]) owner=\d+ handle=(\d+) allocated=1', text)
            if len(opened) != len(set(h for _, h in opened)):
                errors.append(arm+': recycled handle')
            if set(opened) != set(keys):
                errors.append(arm+': opened/released owner mismatch')
        for name, native in shots.items():
            files = list((root/'ftesurf/screenshots').glob(name+'.*'))
            if len(files) != 1:
                errors.append(f'{arm}: missing/ambiguous screenshot {name}')
            else:
                errors += [arm+': '+e for e in pixels(files[0], native)]
    return errors


def run(args: argparse.Namespace) -> int:
    if os.name != 'nt':
        raise RuntimeError('launch requires Windows; grading is portable')
    rig = Path(tempfile.mkdtemp(prefix='p590-bridge-', dir=ROOT/'rig'))
    (rig/'P590_RIG.txt').write_text('Owned disposable bridge fixture. Never owner data.\n')
    env = os.environ.copy()
    env['PATH'] = str(args.cc.resolve().parent)+os.pathsep+env.get('PATH', '')
    fte = args.fte.resolve()
    includes = [fte/'plugins']+[fte/'engine'/x for x in ('client', 'common', 'server', 'gl')]
    command = [str(args.cc.resolve()), '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2',
               '-DFTEPLUGIN', '-shared', '-static-libgcc']+['-I'+str(p) for p in includes]+[
               str(ROOT/'tools/fixtures/p590bridge.c'), '-o', str(rig/'fteplug_p590bridge_x64.dll')]
    with (rig/'compile-plugin.log').open('w') as out:
        rc = subprocess.run(command, env=env, stdout=out, stderr=subprocess.STDOUT).returncode
    if rc or (rig/'compile-plugin.log').read_text().strip():
        raise RuntimeError('fixture compiler failed/warned: '+str(rig/'compile-plugin.log'))
    compiler = ROOT/'src/fteqcc64.exe'
    qc = rig/'qc'; qc.mkdir()
    for name in ('m_defs', 'cl_defs'):
        shutil.copy2(ROOT/'src/defs'/f'{name}.qc', qc/f'{name}.qc')
    for source in (ROOT/'src/shared/sh_nativeui.qc', ROOT/'tools/fixtures/p590bridge.qc'):
        shutil.copy2(source, qc/source.name)
    for name, defs, extra in (('menu', 'm_defs', ''), ('csprogs', 'cl_defs', ''),
                               ('fullview', 'cl_defs', '#define FULLVIEW\n')):
        (qc/'mode.qc').write_text(extra)
        (qc/'progs.src').write_text(f'{rig/name}.dat\n{defs}.qc\nmode.qc\nsh_nativeui.qc\np590bridge.qc\n')
        with (rig/f'compile-{name}.log').open('w') as out:
            rc = subprocess.run([str(compiler), '-srcfile', 'progs.src'], cwd=qc,
                                stdout=out, stderr=subprocess.STDOUT).returncode
        text = (rig/f'compile-{name}.log').read_text(errors='replace')
        if rc or not re.search(r'Done\. 0 warnings', text):
            raise RuntimeError('QC fixture failed/warned: '+str(rig/f'compile-{name}.log'))
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'compile': command,
              'bridge_sha256': sha(fte/'engine/client/cl_plugin_ui.inc'),
              'fixture_sha256': sha(ROOT/'tools/fixtures/p590bridge.c'), 'arms': {}}
    for arm in ARMS:
        root = rig/arm; game = root/'ftesurf'; game.mkdir(parents=True)
        engine = args.control if arm == 'control' else args.engine
        shutil.copy2(engine, root/'ftesurf64.exe')
        shutil.copy2(args.server, root/'fteqwsv64.exe')
        shutil.copy2(rig/'fteplug_p590bridge_x64.dll', root/'fteplug_p590bridge_x64.dll')
        shutil.copy2(rig/'menu.dat', game/'menu.dat')
        shutil.copy2(rig/('fullview.dat' if arm == 'fullview' else 'csprogs.dat'), game/'csprogs.dat')
        shutil.copy2(ROOT/'ftesurf/qwprogs.dat', game/'qwprogs.dat')
        (game/'downloads/csprogsvers').mkdir(parents=True)
        subprocess.run([os.sys.executable, str(ROOT/'tools/seed_csprogs.py'), str(game/'csprogs.dat')],
                       check=True, stdout=subprocess.DEVNULL)
        (game/'maps').mkdir()
        (game/'maps/p590_bridge.map').write_text(make_map())
        (game/'cfg').mkdir(); (game/'cfg/default.cfg').write_text('cfg_save_auto 0\n')
        (root/'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfBridgeFixture\nNAME "Bridge fixture"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p590-unused\n')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        (game/'probe.cfg').write_text(cfg(arm, port))
        servercmd = [str(root/'fteqwsv64.exe'), '-basedir', str(root), '-nohome', '-noplugins',
                     '-port', str(port), '+set', 'cfg_save_auto', '0', '+set', 'sv_mintic', '0.01',
                     '+set', 'sv_maxtic', '0.01', '+set', 'sv_public', '0', '+map', 'p590_bridge.map']
        clientcmd = [str(root/'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound',
                     '-nocdaudio', '-window', '+set', 'plug_loaddefault', '0',
                     '+set', 'vid_width', '640', '+set', 'vid_height', '480',
                     '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0',
                     '+set', 'vid_renderer', 'gl', '+set', 'cfg_save_auto', '0', '+exec', 'probe.cfg']
        timed_out = False
        with (root/'server.log').open('w') as svout, (root/'launch.log').open('w') as out:
            server = subprocess.Popen(servercmd, cwd=root, stdout=svout, stderr=subprocess.STDOUT)
            try:
                client = subprocess.Popen(clientcmd, cwd=root, stdout=out, stderr=subprocess.STDOUT)
                try:
                    rc = client.wait(timeout=70)
                except subprocess.TimeoutExpired:
                    timed_out = True; client.terminate(); rc = client.wait(timeout=10)
            finally:
                if server.poll() is None:
                    server.terminate(); server.wait(timeout=10)
        report['arms'][arm] = {'exit': rc, 'timed_out': timed_out,
                               'engine_sha256': sha(engine), 'plugin_sha256': sha(root/'fteplug_p590bridge_x64.dll'),
                               'csprogs_sha256': sha(game/'csprogs.dat'),
                               'client_command': clientcmd, 'server_command': servercmd}
        (rig/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    errors = grade(rig)
    (rig/'grade.json').write_text(json.dumps({'errors': errors}, indent=2)+'\n')
    for error in errors:
        print('FAIL', error)
    print(f'{len(errors)} failed; evidence: {rig}')
    return bool(errors)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', nargs='?', choices=('run', 'grade'), default='run')
    p.add_argument('rig', nargs='?', type=Path)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-ui-bridge'))
    p.add_argument('--engine', type=Path, default=ROOT/'ftesurf64.exe')
    p.add_argument('--server', type=Path, default=ROOT/'rig/p590-build/fteqwsv64.exe')
    p.add_argument('--control', type=Path, default=Path('C:/msys64/home/Lex/fteqw-ui-font/engine/release/fteqw64.exe'))
    p.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    args = p.parse_args()
    try:
        if args.mode == 'grade':
            if not args.rig:
                p.error('grade requires a retained rig')
            errors = grade(args.rig)
            for error in errors:
                print('FAIL', error)
            print(f'{len(errors)} failed')
            return bool(errors)
        return run(args)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as e:
        print('ERROR', e)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
