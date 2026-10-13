#!/usr/bin/env python3
"""Run owned Windows client updater controls. Never touches an installed player's game.
Logs stay in the task root; only updater/probe lines are printed, not identity/receipt output.
"""
import argparse
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

import updatefeed


def owned_error(process, expected):
    """Read/dismiss ONLY the Error dialog belonging to this harness-owned PID."""
    import ctypes
    from ctypes import wintypes as w
    assert os.name == 'nt', 'this runtime driver expects the Windows engine'
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback, w.LPARAM]
    user.EnumChildWindows.argtypes = [w.HWND, callback, w.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    user.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    found = []
    @callback
    def visit(hwnd, unused):
        pid = w.DWORD(); user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != process.pid: return True
        title = ctypes.create_unicode_buffer(1024); cls = ctypes.create_unicode_buffer(64)
        user.GetWindowTextW(hwnd, title, len(title)); user.GetClassNameW(hwnd, cls, len(cls))
        if title.value != 'Error' or cls.value != '#32770': return True
        texts = []
        @callback
        def child(ch, unused):
            text = ctypes.create_unicode_buffer(2048); user.GetWindowTextW(ch, text, len(text))
            texts.append(text.value); return True
        user.EnumChildWindows(hwnd, child, 0)
        text = '\n'.join(text for text in texts if text and text != 'OK')
        # The owned modal can be enumerated before its static text is created.
        # Wait for the rejection actor before dismissing it, not an empty shell.
        if text:
            found.append(text)
            user.PostMessageW(hwnd, 0x10, 0, 0) # WM_CLOSE, only our owned MB_OK modal
        return True
    until = time.monotonic() + 20
    while process.poll() is None and time.monotonic() < until:
        user.EnumWindows(visit, 0); time.sleep(0.05)
    assert found and expected in found[0], f'owned rejection actor missing/wrong: {found}'
    assert process.poll() is not None, 'owned fatal dialog did not close/exit'
    return found[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--tree', type=Path, required=True)
    ap.add_argument('--engine-release', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    a = ap.parse_args()
    posix = os.name == 'posix'
    exe = 'ftesurf64' if posix else 'ftesurf64.exe'
    platform = 'linux64' if posix else 'win64'
    root = a.work_root
    if root.exists(): raise SystemExit('Use a fresh owned runtime directory')
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned synthetic updater client fixtures. No canonical player data. Stop only subprocess handles created here.\n')
    stage = root / 'stage'
    stage.mkdir()
    def copy(src, rel):
        dest = stage / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    copy(a.tree / 'default.fmf', 'default.fmf')
    copy(a.engine_release / ('fteqw64' if posix else 'fteqw64.exe'), exe)
    if posix: (stage / exe).chmod(0o755)
    plugins = ['fteplug_hl2_amd64.so'] if posix else ['fteplug_hl2_x64.dll', 'fteplug_ui_imgui_x64.dll']
    for name in plugins:
        if posix: (stage / name).write_bytes(b'not loaded in updater UI harness\n')
        else: copy(a.engine_release / name, name)
    for name in ['qwprogs.dat', 'csprogs.dat', 'menu.dat']:
        copy(a.progs / name, 'ftesurf/' + name)
    for d in ['gfx/fonts', 'models', 'glsl', 'particles', 'scripts']:
        source = a.tree / 'ftesurf' / d
        if source.exists(): shutil.copytree(source, stage / 'ftesurf' / d)
    copy(a.tree / 'ftesurf/cfg/default.cfg', 'ftesurf/cfg/default.cfg')
    fixture = stage / 'ftesurf/gfx/updater_fixture.txt'
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_bytes(b'old updater control\n')
    zone = stage / 'ftesurf/maps/zones/local/surf_updater_fixture.json'
    zone.parent.mkdir(parents=True, exist_ok=True); zone.write_bytes(b'published zone fixture\n')
    protected = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// user settings sentinel\n',
                 'ftesurf/fs_addons.txt': b'// custom mounted-game sentinel\n',
                 'ftesurf/maps/zones/local/surf_updater_fixture.json': b'edited zone sentinel\n',
                 'hl2/player-sentinel.txt': b'mounted asset sentinel\n'}
    http = root / 'http'
    http.mkdir()
    hits = Counter()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self): hits[self.path] += 1; super().do_GET()
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(http)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    seed = Path(os.environ.get('FTESURF_UPDATE_SEED_FILE', 'C:/FTESurf-private/keys/ftesurf-updates/seed')).read_bytes()
    serial = 0
    def publish(version):
        nonlocal serial
        serial += 1
        output = root / f'feed-{serial}'
        updatefeed.build({platform: stage}, output, version, [base], seed)
        for obj in (output / 'objects').glob('*/*'):
            dest = http / 'objects' / obj.parent.name / obj.name
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(obj, dest)
        shutil.copyfile(output / 'update.json', http / 'update.json')
        return (http / 'update.json').read_text()
    baseline = publish('0.1.24')
    bm = updatefeed.verify(baseline.encode())
    control = root / 'control-stage'
    shutil.copytree(stage, control)
    def install(name, permission):
        dest = root / name
        shutil.copytree(control, dest)
        (dest / '.ftesurf-updater').mkdir()
        (dest / '.ftesurf-updater/consent').write_text(str(permission) + '\n')
        (dest / '.ftesurf-updater/state.json').write_text(json.dumps({'version': '0.1.24', 'files': {f['path']: f['hash'] for f in bm['files']}}))
        (dest / '.ftesurf-updater/installed.json').write_text(baseline)
        (dest / 'ftesurf/data').mkdir(parents=True, exist_ok=True)
        (dest / 'ftesurf/data/consent.txt').write_text('version 1\n')
        for rel, content in protected.items():
            p = dest / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(content)
        return dest
    run_serial = 0
    def run(dest, extra='', expected_error=None):
        nonlocal run_serial
        run_serial += 1
        logname = f'updater-{run_serial}'
        cfg = dest / 'ftesurf/cfg/test/updater.cfg'
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\n'
                       'vid_fullscreen 0\nvid_width 1280\nvid_height 720\nvolume 0\nmusicvolume 0\n'
                       f'developer 1\nlog_developer 1\nlog_name {logname}\nlog_enable 1\n'
                       f'update_allow_insecure 1\nupdate_manifest_url "{base}/update.json"\n'
                       'name UpdaterRig\nruleset_allow_in 1\n' + extra + '\n'
                       'in 3 exec cfg/test/updater-steps.cfg\n')
        (cfg.parent / 'updater-steps.cfg').write_text(f'cfg_save_auto 0\nmenu_restart\nwait 60\nui_updates\nwait 500\nui_update_probe\nupdate_info\nscreenshot {logname}.png\nwait 30\nquit\n')
        stdout = (dest / 'stdout.log').open('wb')
        # Sys_Error execs xmessage when stderr is redirected. A private stderr
        # PTY makes cold refusals exit instead of leaving an owned modal behind.
        master = slave = None
        if posix:
            import pty
            master, slave = pty.openpty()
        p = subprocess.Popen([str(dest / exe), '-nohome', '-basedir', str(dest),
                              '-manifest', str(dest / 'default.fmf'), '-window',
                              '+set', 'cfg_save_auto', '0', '+set', 'name', 'UpdaterRig', '+exec', 'cfg/test/updater.cfg'], cwd=dest if posix else 'C:/FTESurf', stdout=stdout, stderr=slave if posix else subprocess.STDOUT)
        if slave is not None: os.close(slave)
        try:
            if expected_error and not posix:
                fatal = owned_error(p, expected_error)
                (dest / 'fatal.log').write_text(fatal)
            p.wait(timeout=40)
        finally:
            if p.poll() is None: p.terminate(); p.wait(timeout=10)
            if master is not None:
                os.set_blocking(master, False)
                while True:
                    try: block = os.read(master, 65536)
                    except BlockingIOError: break
                    except OSError as e:
                        if e.errno != 5: raise # PTY EOF is EIO
                        break
                    if not block: break
                    stdout.write(block)
                os.close(master)
            stdout.close()
        if expected_error and posix:
            fatal = (dest / 'stdout.log').read_text(errors='replace')
            assert expected_error in fatal, fatal
            (dest / 'fatal.log').write_text(fatal)
        for rel, content in protected.items(): assert (dest / rel).read_bytes() == content, rel
        if expected_error:
            assert p.returncode != 0, 'rejected cold start must fail'
            assert not list((dest / 'ftesurf/logs').glob('*.log')), 'cold rejection came too late: game initialized logging'
            print('Native cold rejection:', fatal.splitlines()[0]); return fatal
        assert p.returncode == 0, f'owned client failed, exit {p.returncode:#x}'
        logs = '\n'.join(f.read_text(errors='replace') for f in dest.rglob(f'{logname}*.log'))
        lines = [l for l in logs.splitlines() if any(k in l for k in ['ui_update_probe:', 'update:', 'update state', 'last error'])]
        for line in lines: print(line)
        probes = [l for l in lines if 'ui_update_probe:' in l]
        assert probes, 'menu draw/probe control did not act'
        permission_path = dest / '.ftesurf-updater/consent'
        permission = permission_path.read_text().strip() if permission_path.exists() else '-1'
        assert f'consent={permission} ' in probes[-1] and 'screen=7 client=1' in probes[-1], probes[-1]
        assert (dest / 'ftesurf/screenshots' / f'{logname}.png').exists(), 'menu pixels were not captured'
        return logs
    try:
        off = install('off', 0)
        fixture.write_bytes(b'new updater control\n'); publish('0.1.25')
        hits.clear(); logs = run(off)
        assert not hits, dict(hits)
        assert (off / 'ftesurf/gfx/updater_fixture.txt').read_bytes() == b'old updater control\n'
        print('PASS opt-out: menu probe acted, zero HTTP requests and no changed file')
        unknown = install('undecided', 1); (unknown / '.ftesurf-updater/consent').unlink()
        hits.clear(); logs = run(unknown)
        assert not hits and not (unknown / '.ftesurf-updater/consent').exists()
        assert 'consent=-1' in logs
        print('PASS undecided: opt-in UI acts, no permission is assumed and no requests made')
        on = install('on', 1)
        hits.clear(); logs = run(on)
        assert hits['/update.json'] >= 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 1, dict(hits)
        assert (on / 'ftesurf/gfx/updater_fixture.txt').read_bytes() == b'new updater control\n'
        state = json.loads((on / '.ftesurf-updater/state.json').read_text())
        assert state['version'] == '0.1.25' and state['files']['ftesurf/gfx/updater_fixture.txt'] == hashlib.blake2b(b'new updater control\n', digest_size=32).hexdigest()
        assert updatefeed.verify((on / '.ftesurf-updater/installed.json').read_bytes())['version'] == '0.1.25'
        assert 'restart' in logs
        print('PASS real menu capability: signed content applied, shared ledger/cache updated, restart required')
        duplicate = install('duplicate-hash', 1)
        fixture_two = fixture.with_name('updater_duplicate.txt')
        fixture_two.write_bytes(fixture.read_bytes()); publish('0.1.26')
        hits.clear(); logs = run(duplicate)
        assert hits['/update.json'] >= 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 1, dict(hits)
        for f in [fixture, fixture_two]:
            assert (duplicate / f.relative_to(stage)).read_bytes() == b'new updater control\n'
        assert 'update: installed 2 files' in logs
        assert not (duplicate / '.ftesurf-updater/ingame/journal.json').exists()
        assert not list((duplicate / '.ftesurf-updater/ingame/staged').iterdir())
        print('PASS duplicate content hashes: ONE object request, BOTH destinations installed, owned cache purged')
        hits.clear(); run(duplicate)
        assert hits['/update.json'] >= 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        (duplicate / fixture.relative_to(stage)).write_bytes(b'X' * len(fixture.read_bytes()))
        hits.clear(); run(duplicate)
        assert sum(n for p, n in hits.items() if '/objects/' in p) == 1
        assert (duplicate / fixture.relative_to(stage)).read_bytes() == fixture.read_bytes()
        print('PASS current install: no object requests; same-size corruption: ONE repair object')
        signed = (http / 'update.json').read_bytes()
        manifest = updatefeed.verify(signed)
        delta = [f for f in manifest['files'] if f['path'] in [fixture.relative_to(stage).as_posix(), fixture_two.relative_to(stage).as_posix()]]
        def prepare_recovery(name, entries=None):
            dest = install(name, 1); meta = dest / '.ftesurf-updater/ingame'
            (meta / 'staged').mkdir(parents=True)
            (meta / 'manifest.json').write_bytes(signed)
            for f in delta: (meta / 'staged' / f['hash']).write_bytes(fixture.read_bytes())
            rows = [{'p': f['path'], 'h': f['hash'], 's': f['size'], 'x': 0} for f in delta]
            (meta / 'journal.json').write_text(json.dumps({'attempts': 1, 'version': '0.1.26', 'files': rows if entries is None else entries}))
            return dest
        recovery = prepare_recovery('cold-recovery')
        hits.clear(); logs = run(recovery)
        recovered_state = json.loads((recovery / '.ftesurf-updater/state.json').read_text())
        assert recovered_state['version'] == '0.1.26' and all(recovered_state['files'].get(f['path']) == f['hash'] for f in delta)
        assert sum(n for p, n in hits.items() if '/objects/' in p) == 0
        assert all((recovery / f['path']).read_bytes() == fixture.read_bytes() for f in delta)
        assert not (recovery / '.ftesurf-updater/ingame/journal.json').exists()
        assert not list((recovery / '.ftesurf-updater/ingame/staged').iterdir())
        print('PASS cold forward recovery: duplicate cache object copied twice before mounting; no object requests')
        forged = prepare_recovery('cold-forged', [{'p': delta[0]['path'], 'h': delta[0]['hash'], 's': delta[0]['size']},
                                               {'p': 'ftesurf/ftesurf.cfg', 'h': delta[0]['hash'], 's': delta[0]['size']}])
        before = (forged / fixture.relative_to(stage)).read_bytes()
        hits.clear(); run(forged, expected_error='Unverified or linked recovery entry')
        assert not hits and (forged / fixture.relative_to(stage)).read_bytes() == before
        assert (forged / '.ftesurf-updater/ingame/journal.json').exists()
        print('PASS entire journal preflight: later forged path prevents EVEN the earlier valid replacement')
        linked = prepare_recovery('cold-linked-cache')
        link = linked / '.ftesurf-updater/ingame/staged'; target = root / 'linked-cache-target'; link.rename(target)
        if posix: link.symlink_to(target, target_is_directory=True)
        else:
            made = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True, text=True)
            assert made.returncode == 0, 'could not construct owned cache junction control'
        try:
            hits.clear(); run(linked, expected_error='Unverified or linked recovery entry')
            assert not hits and (target / delta[0]['hash']).read_bytes() == fixture.read_bytes()
            assert (linked / fixture.relative_to(stage)).read_bytes() == b'old updater control\n'
        finally:
            if posix: link.unlink()
            else: os.rmdir(link) # unlink ONLY this owned junction; do not walk its target
        print('PASS native staged-cache link: refuses before mount/replacements; linked target untouched')
        shortened = prepare_recovery('cold-shortened', [{'p': delta[0]['path'], 'h': delta[0]['hash'], 's': delta[0]['size']}])
        hits.clear(); run(shortened, expected_error='Incomplete signed installation after recovery')
        assert not hits and (shortened / '.ftesurf-updater/ingame/journal.json').exists()
        print('PASS shortened journal cannot declare an incomplete signed release ready')
        badpolicy = dict(manifest); badpolicy['files'] = [f for f in manifest['files'] if f['path'] != 'ftesurf/menu.dat']
        (http / 'update.json').write_bytes(updatefeed.envelope(badpolicy, seed))
        rejected = install('signed-missing-required', 1)
        hits.clear(); logs = run(rejected)
        assert 'signed update format/policy is invalid' in logs and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        assert (rejected / fixture.relative_to(stage)).read_bytes() == b'old updater control\n'
        print('PASS valid signature is insufficient: missing required file rejected before object requests')
        badpolicy = json.loads(signed)['payload']; badpolicy = json.loads(badpolicy)
        alias = dict(delta[0]); alias.update(path='ftesurf/gfx/hash_alias.txt', size=alias['size']+1); badpolicy['files'].append(alias)
        (http / 'update.json').write_bytes(updatefeed.envelope(badpolicy, seed))
        rejected = install('signed-inconsistent-hash', 1)
        hits.clear(); logs = run(rejected)
        assert 'signed update format/policy is invalid' in logs and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        nul = json.loads(signed); nul['payload'] += '\0ignored tail'; (http / 'update.json').write_text(json.dumps(nul))
        rejected = install('nul-payload', 1)
        hits.clear(); logs = run(rejected)
        assert 'signature is invalid' in logs and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        print('PASS inconsistent same-hash sizes and decoded NUL payload rejected before objects')
        (http / 'update.json').write_bytes(signed)
        obj = http / 'objects' / delta[0]['hash'][:2] / delta[0]['hash']
        obj.write_bytes(b'not the signed object')
        broken = install('corrupt-object', 1)
        hits.clear(); logs = run(broken)
        assert 'state=error' in logs and (broken / fixture.relative_to(stage)).read_bytes() == b'old updater control\n'
        assert not (broken / '.ftesurf-updater/ingame/journal.json').exists()
        obj.write_bytes(fixture.read_bytes())
        print('PASS corrupt object rejected before any live replacement')
        large = fixture.with_name('updater_large.txt'); large.write_bytes(b'x' * (17*1024*1024)); publish('0.1.26')
        capped = install('hard-cap', 1)
        hits.clear(); logs = run(capped, 'update_max_mb 999\nupdate_max_files 9999')
        assert 'too big for in-game' in logs and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        assert not (capped / large.relative_to(stage)).exists()
        large.unlink(); publish('0.1.26')
        print('PASS hard 16-MB in-game cap cannot be bypassed by increasing policy cvars')
        bad = install('bad-signature', 1)
        e = json.loads((http / 'update.json').read_text()); e['payload'] = e['payload'].replace('0.1.26', '0.1.27')
        (http / 'update.json').write_text(json.dumps(e))
        hits.clear(); logs = run(bad)
        assert hits['/update.json'] >= 1 and not sum(n for p, n in hits.items() if '/objects/' in p)
        assert 'signature is invalid' in logs
        print('PASS invalid signature rejected, zero object requests')
        binary = install('binary-handoff', 1)
        # Signed, benign root delta; never executed/installed by the in-game updater.
        with (stage / exe).open('ab') as f: f.write(b'fixture trailer')
        publish('0.1.27')
        hits.clear(); logs = run(binary, 'update_engine_policy 1')
        assert hits['/update.json'] >= 1 and not sum(n for p, n in hits.items() if '/objects/' in p)
        assert 'launcher' in logs
        assert (binary / exe).read_bytes() == (off / exe).read_bytes()
        print('PASS native binary delta always hands off, even with engine policy forced')
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    print('All in-game arms passed; bounded logs retained in', root)


if __name__ == '__main__': main()
