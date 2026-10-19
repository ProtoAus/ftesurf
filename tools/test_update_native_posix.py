#!/usr/bin/env python3
"""Linux native/Rust lock and restart falsifiers on bounded ext4 gamedir fixtures.

Uses prebuilt task-owned progs and an Ubuntu test engine, not a release build.
No canonical config/player data or production feed is written. Runtime copies
are retired after owned processes exit; cleanup failure explicitly retains the
runtime path. Allowlisted logs/PNGs and provenance are retained.
"""
from pathlib import Path
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import pty
import shutil
import signal
import subprocess
import tempfile
import threading
import time

import updatefeed


def cleanup_owned(processes):
    """Bounded TERM/KILL/reap of recorded sessions; finish every owned group."""
    groups = {p.pid for p, _, _ in processes}
    errors = []
    def members():
        found = []
        for stat in Path('/proc').glob('[0-9]*/stat'):
            try: fields = stat.read_text().rsplit(')', 1)[1].split()
            except (FileNotFoundError, ProcessLookupError): continue
            if int(fields[2]) in groups: found.append((int(stat.parent.name), int(fields[2]), fields[0]))
        return found
    def reap():
        for p, _, _ in processes: p.poll()
        for pgid in groups:
            while True:
                try: pid, _ = os.waitpid(-pgid, os.WNOHANG)
                except ChildProcessError: break
                if not pid: break
    def send(sig, selected):
        for pgid in selected:
            try: os.killpg(pgid, sig)
            except ProcessLookupError: pass
            except OSError as e: errors.append(f'signal {sig} group {pgid}: {e}')
    active_before = [pid for pid, _, state in members() if state != 'Z']
    send(signal.SIGTERM, groups)
    until = time.monotonic() + 2
    while time.monotonic() < until:
        reap()
        if not members(): break
        time.sleep(0.05)
    remaining = {pgid for _, pgid, state in members() if state != 'Z'}
    send(signal.SIGKILL, remaining)
    until = time.monotonic() + 8
    while time.monotonic() < until:
        reap()
        if not members(): break
        time.sleep(0.05)
    survivors = members()
    if survivors: errors.append('owned descendants survived TERM/KILL: ' + repr(survivors))
    for p, out, master in processes:
        try: p.wait(timeout=0.1)
        except subprocess.TimeoutExpired: errors.append(f'owned parent still running: {p.pid}')
        for close in [lambda fd=master: os.close(fd), out.close]:
            try: close()
            except OSError as e: errors.append('handle close: ' + str(e))
    return dict(owned_groups=len(groups), active_before_cleanup=active_before,
                escalated_groups=sorted(remaining), surviving_descendants=len(survivors), cleanup_errors=errors)


def apply_cleanup_verdict(result, cleanup):
    result.update(cleanup)
    if result.get('status') == 'PASS' and result['active_before_cleanup']:
        result.update(status='FAIL', error='successful arm left active descendants before cleanup')
    if result['cleanup_errors']:
        result.update(status='FAIL', error='; '.join(result['cleanup_errors']))


def main():
    ap = argparse.ArgumentParser()
    for name in ['tree', 'engine-release', 'progs', 'launcher', 'evidence']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--fault-library', type=Path, help='harness-only LD_PRELOAD read-fault interposer')
    ap.add_argument('--driver-delay', type=float, default=0, help='delay nonexec provisioning beyond old fixed-wait interval to falsify gate scheduling')
    a = ap.parse_args()
    if not 0 <= a.driver_delay <= 10: ap.error('--driver-delay must be 0..10 seconds')
    if os.name != 'posix' or not Path('/proc/self/stat').exists(): ap.error('Linux only')
    evidence = a.evidence.resolve()
    if evidence.exists(): ap.error('fresh evidence directory required')
    evidence.mkdir(parents=True)
    # The native restart fork is deliberately detached. Adopt ONLY our own
    # descendants so they can be reaped and audited after the original game exits.
    assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0, 'subreaper setup failed'
    result = {'engine_sha256': hashlib.sha256((a.engine_release / 'fteqw64').read_bytes()).hexdigest(),
              'launcher_sha256': hashlib.sha256(a.launcher.read_bytes()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'progs_sha256': {name: hashlib.sha256((a.progs / name).read_bytes()).hexdigest() for name in ['menu.dat', 'csprogs.dat', 'qwprogs.dat']},
              'passed': []}
    root = Path(tempfile.mkdtemp(prefix='ftesurf-native-posix-'))
    result['runtime_root'] = str(root)
    (root / 'OWNER.md').write_text('Owned runtime-only native POSIX updater fixtures; never canonical player data. Evidence: ' + str(evidence) + '\n')
    processes = []
    server = thread = None
    env = os.environ.copy()
    env.pop('WAYLAND_DISPLAY', None) # explicit WSLg X11 lane
    env['FTESURF_UPDATE_SEED_FILE'] = env.get('FTESURF_UPDATE_SEED_FILE', '/mnt/c/FTESurf-private/keys/ftesurf-updates/seed')
    try:
        stage = root / 'stage'
        stage.mkdir()
        shutil.copyfile(a.engine_release / 'fteqw64', stage / 'ftesurf64')
        (stage / 'ftesurf64').chmod(0o755)
        shutil.copyfile(a.tree / 'default.fmf', stage / 'default.fmf')
        (stage / 'ftesurf').mkdir()
        for name in ['menu.dat', 'csprogs.dat', 'qwprogs.dat']:
            shutil.copyfile(a.progs / name, stage / 'ftesurf' / name)
        for name in ['gfx/fonts', 'models', 'glsl', 'particles', 'scripts']:
            source = a.tree / 'ftesurf' / name
            if source.exists(): shutil.copytree(source, stage / 'ftesurf' / name)
        (stage / 'ftesurf/cfg').mkdir()
        shutil.copyfile(a.tree / 'ftesurf/cfg/default.cfg', stage / 'ftesurf/cfg/default.cfg')
        rel = 'ftesurf/gfx/updater_fixture.txt'
        (stage / rel).write_bytes(b'old updater control\n')
        http = root / 'http'; http.mkdir()
        hits = Counter()
        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self): hits[self.path] += 1; super().do_GET()
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(http)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        url = f'http://127.0.0.1:{server.server_port}/update.json'
        seed = Path(env['FTESURF_UPDATE_SEED_FILE']).read_bytes()
        serial = 0
        def publish(version):
            nonlocal serial
            serial += 1
            output = root / f'feed-{serial}'
            updatefeed.build({'linux64': stage}, output, version, [url.rsplit('/', 1)[0]], seed)
            for f in (output / 'objects').glob('*/*'):
                dest = http / 'objects' / f.parent.name / f.name
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, dest)
            data = (output / 'update.json').read_bytes(); (http / 'update.json').write_bytes(data)
            return data
        baseline = publish('0.1.24')
        bm = updatefeed.verify(baseline)
        control = root / 'control'; shutil.copytree(stage, control)
        sentinels = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owner settings sentinel\n',
                     'ftesurf/fs_addons.txt': b'// mounted-game sentinel\n',
                     'hl2/player-sentinel.txt': b'owned mounted asset sentinel\n'}
        def install(name, consent):
            dest = root / name; shutil.copytree(control, dest)
            meta = dest / '.ftesurf-updater'; meta.mkdir()
            (meta / 'consent').write_text(str(consent) + '\n')
            (meta / 'state.json').write_text(json.dumps({'version': '0.1.24', 'files': {f['path']: f['hash'] for f in bm['files']}}))
            (meta / 'installed.json').write_bytes(baseline)
            for r, content in sentinels.items():
                f = dest / r; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(content)
            (dest / 'ftesurf/data').mkdir()
            (dest / 'ftesurf/data/consent.txt').write_text('version 1\n')
            return dest
        def protected(dest):
            for r, content in sentinels.items(): assert (dest / r).read_bytes() == content, r
        def spawn(argv, dest, name):
            stdout = (dest / (name + '.stdout.log')).open('wb')
            master, slave = pty.openpty()
            try: p = subprocess.Popen(argv, cwd=dest, env=env, stdout=stdout, stderr=slave, start_new_session=True)
            except BaseException:
                os.close(master); stdout.close(); raise
            finally: os.close(slave)
            processes.append((p, stdout, master))
            return p
        def drain(p):
            row = next(r for r in processes if r[0] is p)
            _, out, master = row
            os.set_blocking(master, False)
            while True:
                try: data = os.read(master, 65536)
                except BlockingIOError: break
                except OSError as e:
                    if e.errno != errno.EIO: raise
                    break
                if not data: break
                out.write(data)
            out.flush()
        def logs(dest, name):
            return '\n'.join(f.read_text(errors='replace') for f in (dest / 'ftesurf/logs').glob(name + '*.log'))
        def wait_actor(p, dest, name, actor):
            until = time.monotonic() + 35
            while time.monotonic() < until:
                text = logs(dest, name)
                if actor in text: return text
                drain(p)
                assert p.poll() is None, f'game exited before {actor}; see {dest}'
                time.sleep(0.05)
            raise AssertionError('missing actor: ' + actor)
        # P823: no Updates screen. Its buttons were the menu's way into these engine commands;
        # Restart to update is the title menu's corner button.
        UPDATE_CMDS = {'mu_enable': 'update_permission 1\nupdate_check auto', 'mu_disable': 'update_permission 0',
                       'mu_off': 'update_permission 0', 'mu_check': 'update_check force'}
        def click(button):
            if button in UPDATE_CMDS: return UPDATE_CMDS[button] + '\nwait 60\n'
            return f'ui_hover @{button}\nwait 5\nui_mouse down\nwait 5\nui_mouse up\nwait 60\n'
        def start(dest, name, steps, autocheck=1):
            cfg = dest / 'ftesurf/cfg/test'; cfg.mkdir(parents=True, exist_ok=True)
            (cfg / (name + '.cfg')).write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvid_width 1280\nvid_height 720\nvolume 0\nmusicvolume 0\n'
                + f'developer 1\nlog_developer 1\nlog_name {name}\nlog_enable 1\nupdate_allow_insecure 1\nupdate_manifest_url "{url}"\nupdate_autocheck {autocheck}\n'
                + f'name UpdaterRig\nruleset_allow_in 1\nin 2 exec cfg/test/{name}-steps.cfg\n')
            (cfg / (name + '-steps.cfg')).write_text('cfg_save_auto 0\nmenu_restart\nwait 60\n' + steps)
            return spawn([str(dest / 'ftesurf64'), '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'), '-window', '+set', 'cfg_save_auto', '0', '+exec', f'cfg/test/{name}.cfg'], dest, name)
        def finish(p, dest, name, error=None):
            p.wait(timeout=40); drain(p); protected(dest)
            if error:
                text = (dest / (name + '.stdout.log')).read_text(errors='replace')
                assert p.returncode != 0 and error in text, text
                assert not list((dest / 'ftesurf/logs').glob(name + '*.log')), 'cold rejection after mounting/logging'
            else:
                assert p.returncode == 0, f'game exit {p.returncode}'
                text = logs(dest, name)
                assert 'ui_update_probe:' in text and 'ui_hover: no control' not in text, text
            return text
        def objects(): return sum(n for path, n in hits.items() if path.startswith('/objects/'))
        def passed(name): result['passed'].append(name); print('PASS ' + name, flush=True)
        (stage / rel).write_bytes(b'new updater control\n'); upgrade = publish('0.1.25')

        dest = install('permission-link', 0); hits.clear()
        target = root / 'permission-target'; target.write_bytes(b'owned permission target\n')
        link = dest / '.ftesurf-updater/consent.tmp'; link.symlink_to(target)
        text = finish(start(dest, 'permission', click('mu_enable') + 'wait 200\nui_update_probe\nquit\n'), dest, 'permission')
        assert 'linked permission path; permission was not changed' in text and 'consent=0 state=disabled' in text
        assert not hits and target.read_bytes() == b'owned permission target\n'
        assert (dest / '.ftesurf-updater/consent').read_text() == '0\n'
        link.unlink()
        passed('consent.tmp symlink refused: real click, unchanged target/permission, zero requests')

        dest = install('native-lock', 0); hits.clear()
        hold = dest / 'ftesurf/cfg/test/hold-lock.cfg'
        hold.parent.mkdir(parents=True, exist_ok=True)
        hold.write_text('wait 20\nexec cfg/test/hold-lock.cfg\n')
        p = start(dest, 'lock', 'ui_update_probe\necho posix-actor: native lock held\nexec cfg/test/hold-lock.cfg\n')
        wait_actor(p, dest, 'lock', 'posix-actor: native lock held')
        lock = dest / '.ftesurf-updater/install.lock'
        with lock.open('r+b') as f:
            try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: pass
            else: raise AssertionError('native process did not hold flock')
        duplicate = start(dest, 'duplicate', 'ui_update_probe\nquit\n')
        finish(duplicate, dest, 'duplicate', 'Close it before starting another copy')
        args = [str(a.launcher.resolve()), '--dir', str(dest), '--yes', '--no-launch', '--allow-insecure', '--manifest-url', url]
        blocked = spawn(args, dest, 'rust-blocked'); blocked.wait(timeout=10); drain(blocked)
        assert blocked.returncode != 0 and 'another updater is running' in (dest / 'rust-blocked.stdout.log').read_text()
        assert not hits and (dest / '.ftesurf-updater/consent').read_text() == '0\n'
        def blocked_snapshot():
            meta = dest / '.ftesurf-updater'
            snapshot = {str(f.relative_to(meta)): f.read_bytes() if f.is_file() else None
                        for f in meta.rglob('*') if f.name != 'install.lock'}
            snapshot['managed-content'] = (dest / rel).read_bytes()
            return snapshot
        before = blocked_snapshot()
        child = spawn(args + ['--wait-for-game'], dest, 'rust-wait')
        until = time.monotonic() + 2.0
        observations = 0
        while time.monotonic() < until:
            assert child.poll() is None and p.poll() is None
            with lock.open('r+b') as f:
                try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: pass
                else: raise AssertionError('native lock released before controlled observation ended')
            assert not hits and blocked_snapshot() == before, 'waiting Rust requested or changed updater state/content while lock held'
            observations += 1
            time.sleep(0.05)
        result['lock_observations'] = observations
        release = hold.with_suffix('.tmp'); release.write_text('quit\n'); release.replace(hold)
        finish(p, dest, 'lock'); child.wait(timeout=40); drain(child)
        assert child.returncode == 0 and hits['/update.json'] == 1 and objects() == 1, dict(hits)
        assert (dest / rel).read_bytes() == (stage / rel).read_bytes()
        assert (dest / '.ftesurf-updater/consent').read_text() == '1\n'
        protected(dest)
        passed('native flock -> duplicate native/Rust refusal -> real Rust wait/update; zero requests or updater-metadata/content changes throughout controlled 2s held interval')

        def adapter(dest):
            path = dest / 'ftesurf-launcher'
            body = '#!/usr/bin/python3\nimport json, os, pathlib, subprocess, sys\n'
            body += f'root = pathlib.Path({str(dest)!r})\n'
            body += 'assert sys.argv[1] == "--dir" and pathlib.Path(sys.argv[2]).resolve() == root\nassert sys.argv[3:] == ["--wait-for-game", "--yes"], sys.argv\n'
            argv = [str(a.launcher.resolve()), '--allow-insecure', '--manifest-url', url, '--', '-nohome', '-window', '+set', 'cfg_save_auto', '0', '+exec', 'cfg/test/return.cfg']
            body += f'fixed = {argv!r}\nfull = [fixed[0]] + sys.argv[1:] + fixed[1:]\n'
            body += '(root / "adapter.json").write_text(json.dumps({"argv": sys.argv[1:], "rust_argv": full}))\n'
            body += 'env = os.environ.copy()\nfor key in ["LD_PRELOAD", "FTESURF_POSIX_READ_FAULT", "FTESURF_POSIX_READ_EIO"]: env.pop(key, None)\n'
            body += 'rc = subprocess.call(full, env=env)\n(root / "adapter-exit.json").write_text(json.dumps({"exit": rc}))\nsys.exit(rc)\n'
            path.write_text(body); path.chmod(0o755)
            cfg = dest / 'ftesurf/cfg/test'; cfg.mkdir(parents=True, exist_ok=True)
            (cfg / 'return.cfg').write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvid_width 1280\nvid_height 720\nvolume 0\nmusicvolume 0\n'
                + f'log_name returned\nlog_enable 1\nupdate_allow_insecure 1\nupdate_manifest_url "{url}"\nin 2 exec cfg/test/return-steps.cfg\n')
            (cfg / 'return-steps.cfg').write_text('cfg_save_auto 0\nmenu_restart\nwait 60\nwait 200\nui_update_probe\nupdate_info\necho posix-actor: real returning engine\nscreenshot returned.png\nquit\n')
        def returned(dest, version):
            until = time.monotonic() + 40
            while not (dest / 'adapter-exit.json').exists():
                assert time.monotonic() < until, 'returning Rust/engine actor missing'
                time.sleep(0.05)
            assert json.loads((dest / 'adapter-exit.json').read_text())['exit'] == 0
            assert 'posix-actor: real returning engine' in logs(dest, 'returned')
            assert 'state=uptodate' in logs(dest, 'returned')
            assert (dest / 'ftesurf/screenshots/returned.png').exists()
            assert json.loads((dest / '.ftesurf-updater/state.json').read_text())['version'] == version
            protected(dest)

        def gate(dest, phase):
            cfg = dest / 'ftesurf/cfg/test'; cfg.mkdir(parents=True, exist_ok=True)
            path = cfg / (phase + '.cfg')
            path.write_text(f'wait 20\nexec cfg/test/{phase}.cfg\n')
            return path
        def release_gate(path, text):
            replacement = path.with_suffix('.tmp'); replacement.write_text(text); replacement.replace(path)
        for binary in [False, True]:
            name = 'restart-binary' if binary else 'restart-content'
            dest = install(name, 1); hits.clear()
            if binary:
                with (stage / 'ftesurf64').open('ab') as f: f.write(b'owned POSIX binary trailer')
                publish('0.1.26')
            steps = 'wait 300\n'
            gates = {}
            for failure in ['missing', 'nonexec', 'linked', 'interpreter']:
                gates[failure] = gate(dest, 'gate-' + failure)
                steps += f'echo posix-actor: {failure} armed\nexec cfg/test/gate-{failure}.cfg\necho posix-actor: {failure} observed\n'
            retry = gate(dest, 'gate-retry')
            steps += 'echo posix-actor: retry armed\nexec cfg/test/gate-retry.cfg\nupdate_error\necho posix-actor: successful retry queued quit\n'
            p = start(dest, name, steps)
            expected_state = 'launcher' if binary else 'restart'
            path = dest / 'ftesurf-launcher'
            for failure, reason in [('missing', 'launcher is missing or not executable'), ('nonexec', 'launcher is missing or not executable'), ('linked', 'linked launcher path; restart was not started'), ('interpreter', 'could not start the launcher')]:
                armed = f'posix-actor: {failure} armed'
                observed = f'posix-actor: {failure} observed'
                wait_actor(p, dest, name, armed)
                if failure == 'nonexec' and a.driver_delay:
                    time.sleep(a.driver_delay)
                    assert p.poll() is None and observed not in logs(dest, name), 'click advanced without driver provisioning'
                    result.setdefault('gated_delay_controls', []).append({'case': name, 'delay_seconds': a.driver_delay, 'click_held': True})
                if path.exists() or path.is_symlink(): path.unlink()
                if failure == 'nonexec': path.write_text('#!/bin/sh\nexit 99\n'); path.chmod(0o644)
                elif failure == 'linked': path.symlink_to(a.launcher.resolve())
                elif failure == 'interpreter': path.write_text('#!/missing-owned-interpreter\n'); path.chmod(0o755)
                if failure == 'missing': assert not path.exists() and not path.is_symlink()
                elif failure == 'nonexec': assert not path.is_symlink() and not os.access(path, os.X_OK) and path.stat().st_mode & 0o111 == 0
                elif failure == 'linked': assert path.is_symlink()
                else: assert os.access(path, os.X_OK) and path.read_text().startswith('#!/missing-owned-interpreter\n')
                release_gate(gates[failure], click('mu_restart') + f'ui_update_probe\nupdate_info\nupdate_error\nscreenshot {failure}.png\n')
                text = wait_actor(p, dest, name, observed)
                tail = text.split(armed, 1)[1].split(observed, 1)[0]
                assert reason in tail and f'consent=1 state={expected_state}' in tail, tail
                assert 'last error   :' in tail and '"update_error" is "' in tail
                assert any('update:' in line and reason in line for line in tail.splitlines()), 'click did not emit a fresh native failure'
                assert not (dest / 'adapter.json').exists()
                assert hits['/update.json'] == 1 and objects() == (0 if binary else 1), dict(hits)
                if binary:
                    assert (dest / rel).read_bytes() == b'old updater control\n'
                    assert (dest / 'ftesurf64').read_bytes() == (control / 'ftesurf64').read_bytes()
            wait_actor(p, dest, name, 'posix-actor: retry armed')
            path.unlink(); adapter(dest); release_gate(retry, click('mu_restart'))
            text = finish(p, dest, name)
            tail = text.split('posix-actor: interpreter observed', 1)[1]
            assert '"update_error" is ""' in tail and 'last error' not in tail, tail
            returned(dest, '0.1.26' if binary else '0.1.25')
            assert hits['/update.json'] == 3 and objects() == (2 if binary else 1), dict(hits)
            assert (dest / 'ftesurf64').read_bytes() == (stage / 'ftesurf64').read_bytes()
            passed(name + ': four real failed clicks retain state/error, same-game retry -> exact native argv -> real Rust -> real returning engine')
        if a.fault_library:
            (stage / 'ftesurf64').write_bytes((control / 'ftesurf64').read_bytes())
            publish('0.1.25')
            for fault in ['EINTR', 'EIO']:
                dest = install('restart-read-' + fault, 1); hits.clear()
                marker = dest / 'read-fault'
                path = dest / 'ftesurf-launcher'
                path.write_text('#!/missing-owned-interpreter\n'); path.chmod(0o755)
                env['LD_PRELOAD'] = str(a.fault_library.resolve())
                env['FTESURF_POSIX_READ_FAULT'] = str(marker)
                if fault == 'EIO': env['FTESURF_POSIX_READ_EIO'] = '1'
                steps = 'wait 300\necho posix-actor: arm read fault\nwait 200\n' + click('mu_restart')
                steps += 'ui_update_probe\nupdate_info\nupdate_error\necho posix-actor: read failure survived\nwait 200\n'
                steps += click('mu_restart') + 'update_error\n'
                p = start(dest, 'read-' + fault, steps)
                for key in ['LD_PRELOAD', 'FTESURF_POSIX_READ_FAULT', 'FTESURF_POSIX_READ_EIO']: env.pop(key, None)
                wait_actor(p, dest, 'read-' + fault, 'posix-actor: arm read fault')
                marker.write_text('armed\n')
                text = wait_actor(p, dest, 'read-' + fault, 'posix-actor: read failure survived')
                assert (dest / 'read-fault.fired').read_text() == 'read fault acted\n', 'interposer did not act'
                assert 'could not start the launcher' in text and 'consent=1 state=restart' in text
                marker.unlink(); path.unlink(); adapter(dest)
                text = finish(p, dest, 'read-' + fault)
                assert '\"update_error\" is \"\"' in text.split('posix-actor: read failure survived', 1)[1]
                returned(dest, '0.1.25')
                assert hits['/update.json'] == 3 and objects() == 1, dict(hits)
                passed('restart pipe ' + fault + ': interposer ACTED; failure retained game/state, same-game retry completed')
            # This success control distinguishes retrying EINTR from simply
            # rejecting every negative read and falsely retaining the game.
            dest = install('restart-read-EINTR-success', 1); hits.clear(); adapter(dest)
            marker = dest / 'read-fault'
            env['LD_PRELOAD'] = str(a.fault_library.resolve())
            env['FTESURF_POSIX_READ_FAULT'] = str(marker)
            steps = 'wait 300\necho posix-actor: arm successful EINTR\nwait 200\n' + click('mu_restart') + 'ui_update_probe\nupdate_error\n'
            p = start(dest, 'read-EINTR-success', steps)
            for key in ['LD_PRELOAD', 'FTESURF_POSIX_READ_FAULT']: env.pop(key, None)
            wait_actor(p, dest, 'read-EINTR-success', 'posix-actor: arm successful EINTR')
            marker.write_text('armed\n')
            text = finish(p, dest, 'read-EINTR-success')
            assert (dest / 'read-fault.fired').read_text() == 'read fault acted\n'
            assert 'Restart was not started:' not in text and '"update_error" is ""' in text
            returned(dest, '0.1.25')
            assert hits['/update.json'] == 3 and objects() == 1, dict(hits)
            passed('restart pipe EINTR with VALID launcher: interposer ACTED; retry accepted EOF -> real Rust -> real returning engine')
        result['status'] = 'PASS'
    except BaseException as e:
        result.update(status='FAIL', error=f'{type(e).__name__}: {e}')
        raise
    finally:
        apply_cleanup_verdict(result, cleanup_owned(processes))
        if server:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            if thread.is_alive(): result.update(status='FAIL', error='HTTP server thread survived cleanup')
        try:
            for f in root.rglob('*'):
                if f.is_symlink() or not f.is_file(): continue
                if f.suffix not in ['.log', '.png', '.fired'] and f.name not in ['state.json', 'journal.json', 'consent', 'adapter.json', 'adapter-exit.json']: continue
                dest = evidence / f.relative_to(root); dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(f.read_bytes())
        except OSError as e:
            result.update(status='FAIL', evidence_error=str(e))
        result['runtime_fixtures_retired'] = False
        if not result['surviving_descendants'] and not result.get('evidence_error'):
            try:
                shutil.rmtree(root)
                assert not root.exists()
                result['runtime_fixtures_retired'] = True
            except OSError as e: result.update(status='FAIL', retirement_error=str(e))
        # Final verdict is persisted AFTER cleanup/retirement acceptance, never
        # a stale PASS artifact followed by an out-of-band assertion failure.
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        if result.get('status') != 'PASS': raise SystemExit('FAIL: ' + str(evidence / 'result.json'))


if __name__ == '__main__': main()
