#!/usr/bin/env python3
"""Exercise a bootstrap fixture or an existing full archive, never publish either.

Extract real engine/progs/bootstrap and exercise direct startup/argv/opt-out/update
without the native handoff adapter. Signed loopback fixtures are never published.
An existing archive must match both its exact stage and its release receipt.
"""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes as w
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from test_update_handoff import owned_job
import updatefeed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--control-stage', type=Path, required=True)
    parser.add_argument('--build-info', type=Path)
    parser.add_argument('--notices', type=Path)
    parser.add_argument('--archive', type=Path, help='Existing full release preview, not a regenerated fixture')
    parser.add_argument('--receipt', type=Path, help='Required with --archive')
    parser.add_argument('--bootstrap-helper', type=Path, required=True)
    args = parser.parse_args()
    if args.archive:
        if not args.receipt or args.build_info or args.notices:
            parser.error('--archive requires --receipt and cannot use fixture build-info/notices')
    elif args.receipt or not args.build_info or not args.notices:
        parser.error('fixture mode requires --build-info and --notices; --receipt requires --archive')
    assert os.name == 'nt', 'Windows runtime test'
    root = args.work_root.resolve()
    assert not root.exists(), 'fresh owned fixture required'
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned bootstrap archive verification; no publication. Real Rust/engine, no adapter.\n'
                                   'Owned jobs contain all children before resume; preserve evidence.\n')
    stage = root / 'stage'
    shutil.copytree(args.control_stage, stage)
    if args.archive:
        receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
        info = {'provenance': receipt['bootstrap']}
    else:
        info = json.loads(args.build_info.read_text(encoding='utf-8-sig'))
        shutil.copyfile(info['binary'], stage / 'ftesurf-launcher.exe')
        (stage / 'notices').mkdir(exist_ok=True)
        shutil.copyfile(args.notices, stage / 'notices/bootstrap.txt')
    expected = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in stage.rglob('*') if p.is_file()}
    assert expected['ftesurf-launcher.exe'].upper() == info['provenance']['sha256']
    sevenzip = 'C:/Program Files/7-Zip/7z.exe'
    if args.archive:
        archive = args.archive.resolve()
        assert archive.name == receipt['archive']['name']
        assert archive.stat().st_size == receipt['archive']['bytes']
        assert hashlib.sha256(archive.read_bytes()).hexdigest().upper() == receipt['archive']['sha256'].upper()
        assert len(expected) == receipt['content']['file_count']
        assert sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()) == receipt['content']['raw_bytes']
        for path, digest in receipt['content']['hashes'].items():
            assert expected[path].upper() == digest.upper(), 'receipt content mismatch: ' + path
        assert expected['notices/bootstrap.txt'].upper() == receipt['bootstrap']['notices_sha256'].upper()
    else:
        archive = root / 'bootstrap-delivery-fixture.7z'
        subprocess.run([sevenzip, 'a', '-t7z', '-mx=9', '-ms=on', '-mmt=on', '-bso0', '-bsp0', str(archive), '.\\*'],
                       cwd=stage, check=True, timeout=90, capture_output=True)
    install = root / 'extracted installation with spaces'
    subprocess.run([sevenzip, 'x', '-y', '-bso0', '-bsp0', '-o' + str(install), str(archive)],
                   check=True, timeout=90, capture_output=True)
    actual = {p.relative_to(install).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in install.rglob('*') if p.is_file()}
    assert actual == expected, 'extracted bytes/entries must equal the stage'
    entries = root / 'entries.json'
    def policy(paths, error=None):
        entries.write_text(json.dumps(paths))
        helper = str(args.bootstrap_helper.resolve()).replace("'", "''")
        name = str(entries).replace("'", "''")
        command = f". '{helper}'; Assert-BootstrapEntries @(Get-Content -Raw -LiteralPath '{name}' | ConvertFrom-Json) 'win64'"
        result = subprocess.run(['pwsh', '-NoProfile', '-Command', command], capture_output=True, text=True, timeout=30)
        if error:
            assert result.returncode != 0 and error in result.stderr + result.stdout, result
        else:
            assert result.returncode == 0, result.stderr
    policy(list(actual))
    for missing in ('ftesurf-launcher.exe', 'notices/bootstrap.txt'):
        bad = root / ('missing-' + Path(missing).stem + '.7z')
        shutil.copyfile(archive, bad)
        subprocess.run([sevenzip, 'd', '-bso0', '-bsp0', str(bad), missing], check=True, capture_output=True, timeout=90)
        listing = subprocess.run([sevenzip, 'l', '-ba', '-slt', str(bad)], check=True, capture_output=True, text=True).stdout
        paths, current = [], None
        for line in listing.splitlines():
            if line.startswith('Path = '):
                current = line[7:].replace('\\', '/')
            elif line.startswith('Attributes = ') and current:
                if 'D' not in line:
                    paths.append(current)
                current = None
        assert missing not in paths and len(paths) == len(actual) - 1
        policy(paths, 'required bootstrap file: ' + missing)
    (root / 'archive-stage-hashes.json').write_text(json.dumps(expected, indent=2))
    print('PASS archive exact-byte control and missing bootstrap/notices policy falsifiers')
    http = root / 'http'; http.mkdir()
    hits = Counter()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            super().do_GET()
        def log_message(self, *unused):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(http)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    seed = Path('C:/FTESurf-private/keys/ftesurf-updates/seed').read_bytes()
    # Immutable baseline ledger, then exactly one content object changes.
    baseline = root / 'baseline'
    updatefeed.build({'win64': stage}, baseline, '0.1.24', [url], seed)
    meta = install / '.ftesurf-updater'; meta.mkdir()
    payload = updatefeed.verify((baseline / 'update.json').read_bytes())
    assert all(f['path'] != 'ftesurf-launcher.exe' for f in payload['files'])
    (meta / 'state.json').write_text(json.dumps({'version': payload['version'], 'files': {f['path']: f['hash'] for f in payload['files']}}))
    (meta / 'installed.json').write_bytes((baseline / 'update.json').read_bytes())
    rel = 'ftesurf/gfx/updater_fixture.txt'
    (stage / rel).write_bytes(b'bootstrap directly installed content\n')
    updatefeed.build({'win64': stage}, http, '0.1.25', [url], seed)
    protected = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned player settings\n',
                 'ftesurf/fs_addons.txt': b'// owned custom mounts\n',
                 'ftesurf/maps/zones/local/surf_bootstrap_fixture.json': b'owned edited zone\n',
                 'ftesurf/data/consent.txt': b'version 1\n',
                 'ftesurf/data/runs/player-sentinel.rec': b'owned player recording\n',
                 'hl2/player-sentinel.txt': b'owned mounted content\n'}
    for p, content in protected.items():
        dest = install / p; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(content)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]
    resume = ctypes.WinDLL('ntdll').NtResumeProcess
    resume.argtypes = [w.HANDLE]; resume.restype = w.LONG
    jobs = []
    def start(name, flags):
        cfgdir = install / 'ftesurf/cfg/test'; cfgdir.mkdir(parents=True, exist_ok=True)
        cfg = f'cfg/test/{name} actor with spaces.cfg'
        (install / 'ftesurf' / cfg).write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvolume 0\nmusicvolume 0\n'
            f'developer 1\nlog_developer 1\nlog_name {name}\nlog_enable 1\n'
            f'update_allow_insecure 1\nupdate_manifest_url "{url}/update.json"\n'
            f'echo bootstrap-actor: {name} started\n'
            f'echo bootstrap-argv: $bootstrap_arg\n'
            'ruleset_allow_in 1\nin 3 quit\n')
        stdout = (root / f'{name}-stdout.log').open('wb')
        # Suspend until job assignment: even a fast launcher cannot create an uncontained child.
        process = subprocess.Popen([str(install / 'ftesurf-launcher.exe'), *flags, '--',
                                    '-window', '+set', 'cfg_save_auto', '0', '+set', 'bootstrap_arg', name + ' argument with spaces',
                                    '+exec', cfg], cwd='C:/FTESurf', stdout=stdout, stderr=subprocess.STDOUT,
                                   creationflags=0x4)
        job = owned_job(process); jobs.append((process, stdout, job))
        assert resume(int(process._handle)) == 0, 'cannot resume owned bootstrap'
        process.wait(timeout=45)
        assert process.returncode == 0, (name, process.returncode)
        text = '\n'.join(p.read_text(errors='replace') for p in (install / 'ftesurf/logs').glob(name + '*.log'))
        assert f'bootstrap-actor: {name} started' in text, 'real engine actor missing'
        assert f'bootstrap-argv: {name} argument with spaces' in text, 'engine argv was not preserved'
        for p, content in protected.items():
            assert (install / p).read_bytes() == content, 'player sentinel changed: ' + p
        # The bootstrap waits for its game; job closure is not success evidence.
        until = time.monotonic() + 5
        accounting = ctypes.create_string_buffer(48)
        while True:
            assert kernel.QueryInformationJobObject(job, 1, accounting, 48, None), ctypes.get_last_error()
            active = int.from_bytes(accounting.raw[40:44], 'little')
            if not active:
                break
            assert time.monotonic() < until, 'lingering owned descendant'
            time.sleep(.05)
        print('PASS real archived bootstrap -> engine:', name, '(exact argv; normal exits; zero descendants)')
    try:
        start('explicit_offline', ['--offline'])
        assert not hits and not (meta / 'consent').exists()
        (meta / 'consent').write_text('0\n')  # Same file written by the measured menu opt-out control.
        start('stored_optout', [])
        assert not hits and (meta / 'consent').read_text() == '0\n'
        start('direct_update', ['--enable-updates', '--allow-insecure', '--manifest-url', url + '/update.json'])
        assert hits['/update.json'] >= 1 and sum(v for p, v in hits.items() if '/objects/' in p) == 1, hits
        assert (install / rel).read_bytes() == (stage / rel).read_bytes()
        assert json.loads((meta / 'state.json').read_text())['version'] == '0.1.25'
        assert hashlib.sha256((install / 'ftesurf-launcher.exe').read_bytes()).hexdigest() == expected['ftesurf-launcher.exe']
        print('PASS real signed direct update: one object installed; bootstrap excluded and unchanged')
        # Native reads persisted permission too. Give this one-launch CLI arm a
        # stored opt-out to suppress native auto checks while measuring Rust's --offline.
        before = dict(hits)
        (meta / 'consent').write_text('0\n')
        start('offline', ['--offline'])
        assert dict(hits) == before and (meta / 'consent').read_text() == '0\n'
        (root / 'result.json').write_text(json.dumps({'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'files': len(actual), 'bootstrap': info['provenance'],
            'notices_sha256': expected['notices/bootstrap.txt'], 'http_hits': dict(hits),
            'owned_jobs': len(jobs), 'active_descendants': 0,
            'archive_mode': 'existing-full-archive' if args.archive else 'delivery-fixture',
            'limit': 'Isolated archive/loopback verification only; no publication or default HTTPS native handoff.'}, indent=2))
    finally:
        for process, stdout, job in jobs:
            kernel.CloseHandle(job)
            if process.poll() is None:
                process.wait(timeout=10)
            stdout.close()
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    main()
