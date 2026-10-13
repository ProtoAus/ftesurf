#!/usr/bin/env python3
"""Real Linux delivery fixture: production pack/verify, unchanged Rust -> engine.

This is not a full release.ps1/receipt or production publication test. Runtime
root must be an empty, privately mounted ext4/tmpfs task-owned directory; no mode
repair, engine shim, or bootstrap rebuild occurs after extraction. Mutants are
real tar.xz files; production PowerShell archive policy is checked separately.
"""
import argparse
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tarfile
import threading
import time

import updatefeed


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph(path):
    meta = json.loads(path.read_text(encoding='utf-8-sig'))
    nodes = {n['id']: n for n in meta['resolve']['nodes']}
    seen, todo = set(), [meta['resolve']['root']]
    while todo:
        item = todo.pop()
        if item in seen:
            continue
        seen.add(item)
        todo.extend(dep['pkg'] for dep in nodes[item]['deps'])
    return sorted((p['name'], p['version'], p.get('checksum')) for p in meta['packages'] if p['id'] in seen)


def session_pids(session):
    result = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                if os.getsid(int(entry.name)) == session:
                    result.append(int(entry.name))
            except ProcessLookupError:
                pass
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--runtime-root', type=Path, required=True)
    p.add_argument('--control-stage', type=Path, required=True)
    p.add_argument('--engine-release', type=Path, required=True)
    p.add_argument('--bootstrap', type=Path, required=True)
    p.add_argument('--notices', type=Path, required=True)
    p.add_argument('--pack-helper', type=Path, required=True)
    p.add_argument('--launcher-script', type=Path, required=True)
    p.add_argument('--builder-metadata', type=Path, required=True)
    p.add_argument('--notice-metadata', type=Path, required=True)
    args = p.parse_args()
    assert os.name == 'posix'
    root = args.work_root.resolve()
    runtime = args.runtime_root.resolve()
    assert not root.exists(), 'fresh evidence root required'
    assert runtime.is_dir() and not list(runtime.iterdir()), 'empty private runtime mount required'
    assert subprocess.run(['mountpoint', '-q', str(runtime)]).returncode == 0, 'runtime must preserve real modes'
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned isolated Linux delivery fixture and runtime evidence; no publication. Retain baseline archive/stage; mutated archives disposable only after policy verification.\n')
    packages = graph(args.builder_metadata)
    assert packages == graph(args.notice_metadata), 'build and notice target graphs differ'
    text = args.notices.read_text()
    for name, version, _ in packages:
        assert f'\n{name} {version}\nDeclared license:' in text, 'missing package notice: ' + name
    print('PASS identical locked Linux build/notice reachable package inventory and notice package coverage:', len(packages))
    stage_root = root / 'stage'
    stage = stage_root / 'FTESurf'
    stage.mkdir(parents=True)
    shutil.copytree(args.control_stage / 'ftesurf', stage / 'ftesurf')
    for name in ('default.fmf', 'LICENSE', 'SOURCE.txt'):
        shutil.copyfile(args.control_stage / name, stage / name)
    shutil.copyfile(args.engine_release / 'fteqw64', stage / 'ftesurf64')
    shutil.copyfile(args.engine_release / 'fteplug_hl2_amd64.so', stage / 'fteplug_hl2_amd64.so')
    shutil.copyfile(args.bootstrap, stage / 'ftesurf-launcher')
    (stage / 'ftesurf.sh').write_bytes(args.launcher_script.read_bytes().replace(b'\r\n', b'\n'))
    (stage / 'notices').mkdir()
    shutil.copyfile(args.notices, stage / 'notices/bootstrap.txt')
    (stage / 'VERSION.txt').write_text('ISOLATED Linux delivery fixture, dirty source/test-stamped engine; no release decision.\n')
    (stage / 'INSTALL.txt').write_text('Verification fixture, not a publishable release archive.\n')
    rel = 'ftesurf/gfx/updater_fixture.txt'
    (stage / rel).write_bytes(b'baseline Linux delivery content\n')
    expected = {f.relative_to(stage).as_posix(): digest(f) for f in stage.rglob('*') if f.is_file()}
    archive = root / 'linux-bootstrap-delivery-fixture.tar.xz'
    subprocess.run(['sh', str(args.pack_helper), 'pack', str(stage_root), 'FTESurf', str(archive),
                    'ftesurf64', 'ftesurf.sh', 'ftesurf-launcher'], check=True, timeout=180)
    def verify(path):
        before = digest(path)
        r = subprocess.run(['sh', str(args.pack_helper), 'verify', str(path), 'FTESurf'],
                           capture_output=True, text=True, timeout=90, check=True)
        log = root / (path.stem + '-verify.log')
        log.write_text(r.stdout + r.stderr)
        assert 'VERIFIED\n' in r.stdout and not any(s.startswith('L ') for s in r.stdout.splitlines()), r.stdout
        assert digest(path) == before, 'archive changed during verification'
        return {'archive': path.name, 'archive_sha256': before, 'verify_log_sha256': digest(log)}
    archive_info = verify(archive)
    extracted = runtime / 'extracted installation with spaces'
    extracted.mkdir()
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        assert len({m.name for m in members}) == len(members)
        for m in members:
            assert m.name == 'FTESurf' or m.name.startswith('FTESurf/')
            assert '..' not in Path(m.name).parts and (m.isdir() or m.isfile())
            want = 0o755 if m.isdir() or m.name in ('FTESurf/ftesurf64', 'FTESurf/ftesurf.sh', 'FTESurf/ftesurf-launcher') else 0o644
            assert m.mode == want and m.uid == m.gid == 0, m.name
        tar.extractall(extracted, filter='data')
    install = extracted / 'FTESurf'
    actual = {f.relative_to(install).as_posix(): digest(f) for f in install.rglob('*') if f.is_file()}
    assert actual == expected, 'exact extracted byte/entry equality failed'
    assert stat.S_IMODE((install / 'ftesurf-launcher').stat().st_mode) == 0o755
    # Real independently malformed archives, retaining all unrelated baseline entries.
    mutants = []
    for name, target, mode in (
        ('missing-bootstrap', 'ftesurf-launcher', None),
        ('missing-notices', 'notices/bootstrap.txt', None),
        ('bootstrap-not-executable', 'ftesurf-launcher', 0o644),
        ('notices-executable', 'notices/bootstrap.txt', 0o755),
        ('notices-byte-change', 'notices/bootstrap.txt', -1),
    ):
        bad = root / (name + '.tar.xz')
        with tarfile.open(archive) as src, tarfile.open(bad, 'w:xz', preset=0) as dst:
            for m in src.getmembers():
                data = src.extractfile(m).read() if m.isfile() else None
                if m.name == 'FTESurf/' + target:
                    if mode is None:
                        continue
                    if mode == -1:
                        data += b'\nmutated notice byte\n'
                        m.size = len(data)
                    else:
                        m.mode = mode
                dst.addfile(m, io.BytesIO(data) if data is not None else None)
        info = verify(bad)
        mutants.append({'name': name, **info, 'target': target, 'kind': mode})
    (root / 'policy-input.json').write_text(json.dumps({'baseline': archive_info, 'stage': expected, 'mutants': mutants}, indent=2))
    def runtime_controls(route):
        # Separate extractions; no chmod/repair/substitution of the subject.
        bad_runtime = runtime / 'nonexecutable-control'; bad_runtime.mkdir()
        with tarfile.open(root / 'bootstrap-not-executable.tar.xz') as tar:
            tar.extractall(bad_runtime, filter='data')
        try:
            subprocess.run([str(bad_runtime / 'FTESurf/ftesurf-launcher'), *route, '--offline'],
                           check=True, timeout=10, stdin=subprocess.DEVNULL)
        except PermissionError:
            pass
        else:
            raise AssertionError('non-executable bootstrap unexpectedly ran')
        missing_engine = runtime / 'missing-engine-control'; missing_engine.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(missing_engine, members=[m for m in tar.getmembers() if m.name != 'FTESurf/ftesurf64'], filter='data')
        result = subprocess.run([str(missing_engine / 'FTESurf/ftesurf-launcher'), *route, '--offline'],
                                capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        (root / 'missing-engine-control.log').write_text(result.stdout + result.stderr)
        assert result.returncode != 0 and 'FTESurf is not installed here' in result.stderr and 'No game was started' in result.stderr, 'missing real engine did not fail actionably'
        print('PASS runtime controls: 0644 bootstrap refuses exec; absent real engine refuses launch')
    print('PASS real tar exact bytes/entries/modes/ownership; independent physical mutants ready for production policy')
    http = runtime / 'http'; http.mkdir()
    hits = Counter()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            super().do_GET()
        def log_message(self, *unused):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(http)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    url = f'http://127.0.0.1:{server.server_port}'
    route = ['--allow-insecure', '--manifest-url', url + '/update.json']
    seed = Path(os.environ['FTESURF_UPDATE_SEED_FILE']).read_bytes()
    baseline = runtime / 'baseline'
    updatefeed.build({'linux64': stage}, baseline, '0.1.24', [url], seed)
    meta = install / '.ftesurf-updater'; meta.mkdir()
    payload = updatefeed.verify((baseline / 'update.json').read_bytes())
    assert all(f['path'] != 'ftesurf-launcher' for f in payload['files'])
    (meta / 'state.json').write_text(json.dumps({'version': payload['version'], 'files': {f['path']: f['hash'] for f in payload['files']}}))
    (meta / 'installed.json').write_bytes((baseline / 'update.json').read_bytes())
    subject = runtime / 'subject-stage'
    shutil.copytree(stage, subject)
    (subject / rel).write_bytes(b'real archived Linux bootstrap installed this content\n')
    updatefeed.build({'linux64': subject}, http, '0.1.25', [url], seed)
    protected = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned settings\n',
                 'ftesurf/fs_addons.txt': b'// owned custom mounts\n',
                 'ftesurf/maps/zones/local/surf_fixture.json': b'owned local zone\n',
                 'ftesurf/data/runs/player-sentinel.rec': b'owned player recording\n'}
    for path, data in protected.items():
        dest = install / path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
    actors = []
    def start(name, flags):
        cfg = f'cfg/test/{name} actor with spaces.cfg'
        (install / 'ftesurf/cfg/test').mkdir(parents=True, exist_ok=True)
        (install / 'ftesurf' / cfg).write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvolume 0\nmusicvolume 0\n'
            f'developer 1\nlog_developer 1\nlog_name {name}\nlog_enable 1\n'
            f'update_allow_insecure 1\nupdate_manifest_url "{url}/update.json"\n'
            f'echo bootstrap-actor: {name} started\necho bootstrap-argv: $bootstrap_arg\n'
            'ruleset_allow_in 1\nin 3 quit\n')
        with (root / (name + '-stdout.log')).open('wb') as stdout:
            # Every bootstrap arm targets the measured server. Disable only the
            # ENGINE's independent autocheck so enabled-consent --offline can
            # isolate Rust's one-launch override without overwriting permission.
            process = subprocess.Popen([str(install / 'ftesurf-launcher'), *route, *flags, '--', '-window', '+set', 'update_autocheck', '0',
                '+set', 'cfg_save_auto', '0', '+set', 'bootstrap_arg', name + ' argument with spaces', '+exec', cfg],
                cwd='/', stdin=subprocess.DEVNULL, stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                process.wait(timeout=45)
                assert process.returncode == 0, (name, process.returncode)
                deadline = time.monotonic() + 5
                while session_pids(process.pid):
                    assert time.monotonic() < deadline, 'lingering owned actor descendants'
                    time.sleep(.05)
            finally:
                if session_pids(process.pid):
                    os.killpg(process.pid, signal.SIGKILL)  # Only this atomically created actor session.
                if process.poll() is None:
                    process.wait(timeout=10)
        logs = list((install / 'ftesurf/logs').glob(name + '*.log'))
        text = '\n'.join(f.read_text(errors='replace') for f in logs)
        for f in logs:
            shutil.copyfile(f, root / f.name)
        assert f'bootstrap-actor: {name} started' in text, 'real engine did not act'
        assert f'bootstrap-argv: {name} argument with spaces' in text, 'exact engine argv was not preserved'
        for path, data in protected.items():
            assert (install / path).read_bytes() == data, 'protected player bytes changed: ' + path
        assert digest(install / 'ftesurf-launcher') == expected['ftesurf-launcher']
        actors.append({'name': name, 'exit': process.returncode, 'active_descendants': 0})
        print('PASS extracted unmodified Rust -> real engine:', name, '(argv, normal exits, zero descendants)')
    try:
        thread.start()
        runtime_controls(route)
        assert not hits, 'offline failure controls contacted update server'
        start('explicit_offline', ['--offline'])
        assert not hits and not (meta / 'consent').exists(), hits
        (meta / 'consent').write_text('0\n')
        start('stored_optout', [])
        assert not hits and (meta / 'consent').read_text() == '0\n', hits
        start('direct_update', ['--enable-updates'])
        assert hits['/update.json'] == 1 and sum(v for k, v in hits.items() if '/objects/' in k) == 1, hits
        assert (install / rel).read_bytes() == (subject / rel).read_bytes()
        assert json.loads((meta / 'state.json').read_text())['version'] == '0.1.25'
        assert (meta / 'consent').read_text() == '1\n', 'explicit enable did not persist permission'
        before = dict(hits)
        start('offline_after_update', ['--offline'])
        assert dict(hits) == before and (meta / 'consent').read_text() == '1\n', 'one-launch Rust offline did not preserve enabled consent/zero HTTP'
        assert digest(install / 'ftesurf64') == expected['ftesurf64']
        (root / 'result.json').write_text(json.dumps({'archive_sha256': digest(archive), 'file_count': len(actual),
            'bootstrap_sha256': expected['ftesurf-launcher'], 'engine_sha256': expected['ftesurf64'],
            'notices_sha256': expected['notices/bootstrap.txt'], 'Linux_notice_packages': len(packages),
            'actors': actors, 'http_hits': dict(hits), 'protected_paths': list(protected),
            'policy_status': 'Pending separate PowerShell policy check bound to current archive/log SHA256',
            'limits': 'Delivery fixture only, dirty/test-stamped source. GUI on WSLg/glibc 2.35; baseline chain separately on 2.31. Engine independent autocheck disabled to isolate Rust offline/consent. Not full release/receipt/publication.'}, indent=2))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    main()
