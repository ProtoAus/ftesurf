#!/usr/bin/env python3
"""Windows native F2 regression and corner-layout fixtures; never sends owner input.

WM_KEYDOWN/UP go only to a HWND whose PID is our retained Popen handle. F3's
console actor proves Key_Event/binds ran; ui_key is NOT used to test F2.
State pictures use a separately compiled, NEVER DEPLOYABLE menu fixture that
changes only MU_Status's read-only status inputs and instruments text geometry.
They do not test updater permission, HTTP, verification or restart authority.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('cfg', 'glsl', 'scripts', 'models', 'gfx', 'textures')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owned(out):
    if not any((p / 'OWNER.md').is_file() for p in (out, *out.parents)):
        raise RuntimeError('--out requires ancestor OWNER.md')


def window(pid):
    user = C.WinDLL('user32', use_last_error=True)
    callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user.GetWindowThreadProcessId.argtypes = (W.HWND, C.POINTER(W.DWORD))
    user.IsWindowVisible.argtypes = (W.HWND,)
    found = []

    @callback
    def visit(hwnd, _):
        actual = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, C.byref(actual))
        if actual.value == pid and user.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user.EnumWindows(visit, 0)
    if len(found) != 1:
        raise RuntimeError(f'owned PID must have one visible HWND, found {len(found)}')
    return user, found[0]


def key(process, vk, scan):
    if process.poll() is not None:
        raise RuntimeError('owned client already exited')
    user, hwnd = window(process.pid)
    # Recheck ownership at dispatch. Do not focus, SendInput, or enumerate/kill peers.
    actual = W.DWORD()
    user.GetWindowThreadProcessId(hwnd, C.byref(actual))
    if actual.value != process.pid:
        raise RuntimeError('HWND ownership changed')
    user.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    for message, value in ((0x100, 1 | scan << 16), (0x101, 0xC0000001 | scan << 16)):
        if not user.PostMessageW(hwnd, message, vk, value):
            raise C.WinError(C.get_last_error())
        time.sleep(0.1)


def wait_text(process, logfile, needle, timeout=35):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        text = logfile.read_text(errors='replace') if logfile.exists() else ''
        if needle in text:
            return
        if process.poll() is not None:
            break
        time.sleep(0.05)
    raise RuntimeError(f'actor not reached: {needle}')


def base_config():
    return ['cfg_save_auto 0', 'con_savehistory 0', 'cl_idlefps 0', 'cl_maxfps 100',
            'vid_conautoscale 1', 'vid_conwidth 0', 'vid_conheight 0',
            'milk_enable 0', 'milk_panels 0', 'update_autocheck 0', 'lobby_dir ""',
            'developer 1', 'log_dir logs', 'log_name corner', 'log_enable 1',
            'waitms 1200']


def run(a, name, menu, cfg, size=(1280, 720), native=False):
    rig = Path(tempfile.mkdtemp(prefix=name + '-', dir=a.out))
    (rig / 'UI_CORNER_RIG.txt').write_text('Owned disposable native/menu rig. No owner data/config.\n')
    game = rig / 'ftesurf'
    game.mkdir()
    for folder in SOURCES:
        src = ROOT / 'ftesurf' / folder
        if src.is_dir():
            shutil.copytree(src, game / folder)
    (game / 'data').mkdir()
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(menu, game / 'menu.dat')
    shutil.copy2(a.engine, rig / 'ftesurf64.exe')
    (rig / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfUIGallery\nNAME "Update corner fixture"\n'
                                    'BASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG corner-unused\n')
    (game / 'corner.cfg').write_text('\n'.join(cfg) + '\n')
    logfile = game / 'logs/corner.log'
    command = [str(rig / 'ftesurf64.exe'), '-basedir', str(rig), '-nohome', '-nosound', '-nocdaudio',
               '-noplugins', '-window', '+set', 'vid_width', str(size[0]), '+set', 'vid_height', str(size[1]),
               '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0', '+set', 'cfg_save_auto', '0',
               '+set', 'name', 'CornerFixture', '+exec', 'corner.cfg']
    process = None
    try:
        with (rig / 'launch.log').open('w') as output:
            process = subprocess.Popen(command, cwd=rig, stdout=output, stderr=subprocess.STDOUT)
            if native:
                wait_text(process, logfile, 'CORNER KEY READY')
                key(process, 0x72, 0x3D)  # F3: independent actor proving native bind dispatch
                wait_text(process, logfile, 'CORNER NATIVE F3 ACTED')
                key(process, 0x71, 0x3C)  # F2: actual Windows/native key route
                time.sleep(0.5)
                key(process, 0x73, 0x3E)  # F4: trusted diagnostic/capture/exit bind
            code = process.wait(timeout=100)
        text = logfile.read_text(errors='replace')
        if code or text.count('CORNER FINISHED') != 1:
            raise RuntimeError(f'{name}: exit/completion failure')
        bad = re.findall(r'[^\r\n]*(?:QC runtime error|Menu_Abort|Unknown command)[^\r\n]*', text)
        if bad:
            raise RuntimeError(f'{name}: {bad[:3]}')
        result = {'rig': str(rig), 'menu_sha256': sha(menu), 'engine_sha256': sha(a.engine), 'exit': code}
        (rig / 'inputs.json').write_text(json.dumps(result, indent=2) + '\n')
        return rig, text
    finally:
        if process is not None and process.poll() is None:
            process.terminate()  # retained own Popen only
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        # All these copies were authored above; preserve configs/logs/PNGs/data.
        for path in [*(game / p for p in SOURCES), game / 'menu.dat', rig / 'ftesurf64.exe']:
            if path.is_dir():
                for child in path.rglob('*'):
                    if child.lstat().st_file_attributes & 0x400:
                        raise RuntimeError(f'refusing linked retirement path: {child}')
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        (rig / 'RETENTION.txt').write_text('Client exited; owned static/executable copies retired. Evidence retained.\n')


def native_config(kind):
    lines = base_config()
    lines += {'legacy': ['bindlevel F2 30 ui_updates'], 'blank': ['unbind F2'],
              'custom': ['bind F2 "echo CORNER CUSTOM F2 ACTED"']}[kind]
    return lines + ['bind F3 "echo CORNER NATIVE F3 ACTED"',
                    'bind F4 "echo CORNER NATIVE F4 ACTED; ui_update_probe; screenshot native_f2; waitms 500; echo CORNER FINISHED; quit"',
                    'menu_restart', 'waitms 1500', 'ui_journal', 'ui_key escape',
                    'waitms 500', 'bind F2', 'echo CORNER KEY READY']


def layout_fixture(a):
    fixture = a.out / ('status-fixture-' + uuid.uuid4().hex)
    fixture.mkdir()
    original = (ROOT / 'src/menu/m_update.qc').read_text()
    start = original.index('void(vector screensize) MU_Status =')
    end = len(original)                   # P823: MU_Status is the file's last function
    body = original[start:end].replace('"update_state"', '"corner_state"').replace(
        '"update_version"', '"corner_latest"').replace('"update_consent"', '"corner_consent"')
    source = original[:start] + body + original[end:]
    needle = '\ttext = ui_fit_text(text, width, size);'
    if source.count(needle) != 1:
        raise RuntimeError('status geometry instrumentation requires unique helper')
    source = source.replace(needle, needle + '\n\tif (cvar("corner_probe"))\n\t{\n'
        '\t\tprint(sprintf("CORNER LINE right=%.3f y=%g width=%.3f text=%s\\n", right, y, stringwidth(text, TRUE, size), text));\n'
        '\t\tif (y == 58) cvar_set("corner_probe", "0");\n\t}')
    (fixture / 'm_update_fixture.qc').write_text(source)
    manifest = (ROOT / 'src/m_progs.src').read_text().splitlines()
    relative = lambda p: os.path.relpath(p, ROOT / 'src').replace('\\', '/')
    manifest[0] = relative(fixture / 'menu.dat')
    manifest = [relative(fixture / 'm_update_fixture.qc') if l == 'menu/m_update.qc' else l for l in manifest]
    src = ROOT / 'src' / ('corner-fixture-' + uuid.uuid4().hex + '.src')
    try:
        src.write_text('\n'.join(manifest) + '\n')
        (fixture / 'm_progs.src').write_text(src.read_text())
        built = subprocess.run([str(a.qcc), '-srcfile', src.name], cwd=ROOT / 'src',
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (fixture / 'compile.log').write_text(built.stdout)
        if built.returncode or re.search(r'(?im)^.*\bwarning\b(?!s|\s*$)', built.stdout):
            raise RuntimeError('status-only fixture did not compile cleanly; read compile.log')
    finally:
        src.unlink(missing_ok=True)
    (fixture / 'FIXTURE_ONLY.txt').write_text('NEVER DEPLOY: only MU_Status reads fixture inputs; no updater authority proof.\n'
        + 'product source SHA256 ' + hashlib.sha256(original.encode()).hexdigest() + '\n')
    return fixture / 'menu.dat'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ('engine', 'artifacts', 'control-artifacts', 'qcc', 'out'):
        p.add_argument('--' + option, type=Path, required=True)
    a = p.parse_args()
    a.out = a.out.resolve()
    owned(a.out)
    a.out.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, artifacts, kind, expected in (
        ('control-legacy', a.control_artifacts, 'legacy', 0),
        ('subject-legacy', a.artifacts, 'legacy', 8),
        ('subject-blank', a.artifacts, 'blank', 8),
        ('subject-custom', a.artifacts, 'custom', 0)):
        rig, text = run(a, name, artifacts / 'menu.dat', native_config(kind), native=True)
        probes = re.findall(r'ui_update_probe: .*screen=(\d+)', text)
        ok = probes == [str(expected)] and text.count('CORNER NATIVE F3 ACTED') == 1 and text.count('CORNER NATIVE F4 ACTED') == 1
        if kind == 'custom':
            ok = ok and len(re.findall(r'(?m) CORNER CUSTOM F2 ACTED\r?$', text)) == 1
        results[name] = {'pass': ok, 'rig': str(rig), 'screens': probes}
        print(name, results[name])
        (a.out / 'native-verdict.json').write_text(json.dumps(results, indent=2) + '\n')
        if not ok:
            raise RuntimeError('native input arm failed')
    fixture = layout_fixture(a)
    states = ('idle', 'checking', 'uptodate', 'error', 'downloading', 'applying', 'available', 'launcher', 'restart', 'off', 'custom')
    for size in ((1280, 720), (800, 600)):
        cfg = base_config() + ['bind F2 ui_journal', 'menu_restart', 'waitms 1500', 'ui_journal', 'ui_key escape', 'waitms 500',
                               'set ui_release_version 9.8.7', 'set corner_latest 9.8.8']
        for state in states:
            cfg += [f'set corner_state {"restart" if state in ("off", "custom") else state}',
                    f'set corner_consent {0 if state == "off" else 1}']
            if state == 'custom':
                cfg += ['bind F2 "echo CUSTOM"']
            cfg += [f'echo CORNER STATE {state}', 'set corner_probe 1', 'waitms 200',
                    f'screenshot {state}', 'waitms 500']
        cfg += ['echo CORNER FINISHED', 'quit']
        rig, text = run(a, f'layout-{size[0]}', fixture, cfg, size)
        lines = re.findall(r'CORNER LINE right=([\d.]+) y=(\d+) width=([\d.]+) text=([^\r\n]+)', text)
        good = len(lines) == len(states) * 3
        for index, state in enumerate(states):
            trio = lines[index * 3:index * 3 + 3]
            good = good and len(trio) == 3 and all(float(r) == size[0] - 16 and float(w) <= 320 for r, _, w, _ in trio)
            if trio:
                good = good and '[F2]' not in trio[0][3]   # P823: Restart to update is a button
            good = good and len(list((rig / 'ftesurf/screenshots').glob(state + '.*'))) == 1
        results[f'layout-{size[0]}'] = {'pass': good, 'rig': str(rig), 'drawn_lines': lines}
        if not good:
            raise RuntimeError('status layout/state arm failed')
    (a.out / 'verdict.json').write_text(json.dumps(results, indent=2) + '\n')
    print('All native key and status-layout controls passed; inspect PNGs for appearance.')


if __name__ == '__main__':
    main()
