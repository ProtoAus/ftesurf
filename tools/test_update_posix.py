#!/usr/bin/env python3
"""Acted POSIX updater permission/recovery controls; no real game is started.

Requires the production seed FILE to sign fixtures accepted by the pinned verifier.
The seed is read only in-process, never printed. Runtime fixtures live in a bounded
TemporaryDirectory on a POSIX filesystem; only small evidence is retained.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading

import updatefeed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--seed-file', type=Path, required=True)
    ap.add_argument('--expect-before', action='store_true', help='prove the pre-fix defect')
    a = ap.parse_args()
    if os.name != 'posix':
        ap.error('requires POSIX chmod semantics')
    launcher = a.launcher.resolve(strict=True)
    if a.evidence.exists():
        ap.error('evidence path must be fresh')
    a.evidence.parent.mkdir(parents=True, exist_ok=True)
    seed = a.seed_file.read_bytes()
    cases = []
    skipped = []
    requests = []
    script = b'#!/bin/sh\nprintf "%s\\n" "$@" > game-argv.txt\nprintf "acted\\n" > game-acted.txt\n'
    payloads = {'ftesurf64': script, 'ftesurf.sh': b'#!/bin/sh\nexit 0\n',
                'default.fmf': b'fixture-manifest\n', 'ftesurf/menu.dat': b'menu-fixture\n',
                'ftesurf/csprogs.dat': b'client-fixture\n', 'ftesurf/qwprogs.dat': b'POSIX-control-progs\n'}
    h = lambda b: hashlib.blake2b(b, digest_size=32).hexdigest()
    manifest = dict(schema=2, game='ftesurf', channel='stable', version='9.1.0', hash_algo='blake2b-256',
                    launcher_version='0.1.6', install_root_name='FTESurf',
                    exec={'cmd': 'ftesurf64', 'args': ['-manifest', 'default.fmf']}, removed=[],
                    files=[dict(path=p, size=len(b), hash=h(b), exec=p in ('ftesurf64', 'ftesurf.sh'),
                                platform='linux64' if p == 'ftesurf64' else 'all', component='engine' if p == 'ftesurf64' else 'content')
                           for p, b in payloads.items()])

    with tempfile.TemporaryDirectory(prefix='ftesurf-posix-controls-') as tmp:
        work = Path(tmp)
        feed = work / 'feed'
        feed.mkdir()
        for b in payloads.values():
            obj = feed / 'objects' / h(b)[:2] / h(b)
            obj.parent.mkdir(parents=True, exist_ok=True)
            obj.write_bytes(b)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(feed), **kwargs)

            def log_message(self, *_args):
                pass

            def do_GET(self):
                requests.append(self.path)
                super().do_GET()

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/update.json'
        manifest['mirrors'] = [url.rsplit('/', 1)[0]]
        data = updatefeed.envelope(manifest, seed)
        (feed / 'update.json').write_bytes(data)

        def install(name, mode=0o644):
            root = work / name
            root.mkdir()
            for p, b in payloads.items():
                dest = root / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b)
                dest.chmod(mode if p in ('ftesurf64', 'ftesurf.sh') else 0o600)
            # Out-of-feed player-owned data must retain both bytes and mode.
            for p in ('ftesurf/maps/zones/local/surf_fixture.json', 'ftesurf/fs_addons.txt'):
                dest = root / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b'player-owned\n')
                dest.chmod(0o600)
            return root

        def invoke(root, *args, online=True, expect=0):
            cmd = [str(launcher), '--dir', str(root), '--yes']
            if online:
                cmd += ['--manifest-url', url, '--allow-insecure']
            else:
                cmd += ['--offline']
            p = subprocess.run([*cmd, *args], capture_output=True, text=True, timeout=20)
            assert (p.returncode == 0) == (expect == 0), (root.name, p.returncode, p.stdout, p.stderr)
            return p

        def modes(root):
            return {p: stat.S_IMODE((root / p).stat().st_mode) for p in payloads}

        def preserved(root):
            for p, b in payloads.items():
                assert (root / p).read_bytes() == b, (root.name, p)
            for p in ('ftesurf/maps/zones/local/surf_fixture.json', 'ftesurf/fs_addons.txt'):
                assert (root / p).read_bytes() == b'player-owned\n'
                assert stat.S_IMODE((root / p).stat().st_mode) == 0o600

        def record(name, root, p):
            cases.append(dict(case=name, exit=p.returncode, stdout=p.stdout, stderr=p.stderr, modes=modes(root)))

        def cached(root):
            meta = root / '.ftesurf-updater'
            meta.mkdir(exist_ok=True)
            (meta / 'installed.json').write_bytes(data)
            return meta

        try:
            # Acting fresh-download control: hashes, chmod, launch and argv all matter.
            fresh = work / 'fresh'
            fresh.mkdir()
            p = invoke(fresh, '--', '-test', 'space value')
            assert (fresh / 'game-acted.txt').read_text() == 'acted\n'
            assert (fresh / 'game-argv.txt').read_text().splitlines() == ['-manifest', 'default.fmf', '-test', 'space value']
            assert modes(fresh)['ftesurf64'] & 0o100
            record('fresh-download-launch-actor', fresh, p)

            adopt = install('adopt')
            before = len(requests)
            p = invoke(adopt, '--verify', '--no-launch')
            assert not any('/objects/' in path for path in requests[before:]), 'repair downloaded byte-correct files'
            preserved(adopt)
            assert bool(modes(adopt)['ftesurf64'] & 0o100) != a.expect_before
            record('byte-correct-mode-repair', adopt, p)
            p = invoke(adopt, '--', '-test', 'space value', expect=1 if a.expect_before else 0)
            assert (adopt / 'game-acted.txt').exists() != a.expect_before
            record('adopted-launch-actor', adopt, p)

            # Cold pending transaction: rename already completed, chmod interrupted.
            recovery = install('recovery')
            meta = recovery / '.ftesurf-updater'
            meta.mkdir(parents=True)
            pending = meta / 'pending.json'
            pending.write_text(json.dumps({'envelope': data.decode(), 'paths': []}))
            before = len(requests)
            p = invoke(recovery, '--no-launch', '--allow-insecure', online=False)
            assert len(requests) == before
            assert not pending.exists()
            assert bool(modes(recovery)['ftesurf64'] & 0o100) != a.expect_before
            preserved(recovery)
            record('cold-after-rename-recovery', recovery, p)
            p = invoke(recovery, online=False, expect=1 if a.expect_before else 0)
            assert (recovery / 'game-acted.txt').exists() != a.expect_before
            record('recovered-launch-actor', recovery, p)

            if not a.expect_before:
                # Preserve unusual permissions rather than chmod everything to 0755.
                special = install('special', 0o640)
                p = invoke(special, '--no-launch')
                assert modes(special)['ftesurf64'] == 0o750
                assert modes(special)['ftesurf.sh'] == 0o750
                preserved(special)
                record('preserve-read-write-access-repair', special, p)

                dry = install('dry')
                original = modes(dry)
                p = invoke(dry, '--dry-run')
                assert modes(dry) == original
                assert not (dry / '.ftesurf-updater/installed.json').exists()
                assert not (dry / '.ftesurf-updater/pending.json').exists()
                preserved(dry)
                record('dry-run-does-not-chmod', dry, p)

                dry_pending = install('dry-pending')
                meta = dry_pending / '.ftesurf-updater'
                meta.mkdir()
                pending = meta / 'pending.json'
                journal = json.dumps({'envelope': data.decode(), 'paths': []}).encode()
                pending.write_bytes(journal)
                before = len(requests)
                p = invoke(dry_pending, '--dry-run', '--no-launch', expect=1)
                assert len(requests) == before and pending.read_bytes() == journal
                assert modes(dry_pending)['ftesurf64'] == 0o644
                assert not (meta / 'installed.json').exists()
                record('dry-run-cold-pending-no-commit', dry_pending, p)

                dry_outage = install('dry-outage')
                cached(dry_outage)
                p = subprocess.run([str(launcher), '--dir', str(dry_outage), '--manifest-url', url + '.missing', '--allow-insecure', '--yes', '--dry-run'], capture_output=True, text=True, timeout=20)
                assert p.returncode != 0 and 'executable permission' in p.stderr
                assert modes(dry_outage)['ftesurf64'] == 0o644
                assert not (dry_outage / 'game-acted.txt').exists()
                record('dry-run-cached-outage-read-only', dry_outage, p)

                offline = install('explicit-offline')
                p = invoke(offline, online=False, expect=1)
                assert not (offline / 'game-acted.txt').exists()
                assert modes(offline)['ftesurf64'] == 0o644
                record('unsigned-explicit-offline-no-repair', offline, p)

                # Entire signed set must verify before any mode mutation.
                bad = install('bad-pending')
                meta = bad / '.ftesurf-updater'
                meta.mkdir(parents=True)
                pending = meta / 'pending.json'
                pending.write_text(json.dumps({'envelope': data.decode(), 'paths': []}))
                (bad / 'ftesurf/qwprogs.dat').write_bytes(b'wrong-progs')
                p = invoke(bad, '--no-launch', '--allow-insecure', online=False, expect=1)
                assert 'journal omits required repair: ftesurf/qwprogs.dat' in p.stderr
                assert modes(bad)['ftesurf64'] == 0o644
                assert pending.exists()
                record('later-corrupt-content-no-chmod', bad, p)

                linked = install('linked-pending')
                meta = linked / '.ftesurf-updater'
                meta.mkdir(parents=True)
                pending = meta / 'pending.json'
                pending.write_text(json.dumps({'envelope': data.decode(), 'paths': []}))
                external = work / 'external-script'
                external.write_bytes(payloads['ftesurf.sh'])
                external.chmod(0o644)
                (linked / 'ftesurf.sh').unlink()
                (linked / 'ftesurf.sh').symlink_to(external)
                p = invoke(linked, '--no-launch', '--allow-insecure', online=False, expect=1)
                assert 'linked install path' in p.stderr
                assert modes(linked)['ftesurf64'] == 0o644
                assert stat.S_IMODE(external.stat().st_mode) == 0o644
                assert pending.exists()
                record('later-linked-exec-no-chmod', linked, p)

                outage = install('signed-outage')
                cached(outage)
                # HTTP transport error, not a rejected manifest/signature.
                before = len(requests)
                p = subprocess.run([str(launcher), '--dir', str(outage), '--manifest-url', url + '.missing', '--allow-insecure', '--yes'], capture_output=True, text=True, timeout=20)
                assert p.returncode == 0, (p.stdout, p.stderr)
                assert (outage / 'game-acted.txt').read_text() == 'acted\n'
                assert not any('/objects/' in path for path in requests[before:])
                preserved(outage)
                record('signed-cache-outage-launch-actor', outage, p)

                # Exercise prepare_install directly through cached fallback, not an
                # earlier journal/plan rejection: later invalid content gates chmod.
                for name, linked_file in (('corrupt-cache-outage', False), ('linked-cache-outage', True)):
                    rejected = install(name)
                    cached(rejected)
                    if linked_file:
                        external = work / 'cached-external-script'
                        external.write_bytes(payloads['ftesurf.sh'])
                        external.chmod(0o644)
                        (rejected / 'ftesurf.sh').unlink()
                        (rejected / 'ftesurf.sh').symlink_to(external)
                    else:
                        (rejected / 'ftesurf/qwprogs.dat').write_bytes(b'wrong-progs')
                    before = len(requests)
                    p = subprocess.run([str(launcher), '--dir', str(rejected), '--manifest-url', url + '.missing', '--allow-insecure', '--yes'], capture_output=True, text=True, timeout=20)
                    assert p.returncode != 0 and not (rejected / 'game-acted.txt').exists()
                    assert ('linked install path' if linked_file else 'install needs repair: ftesurf/qwprogs.dat') in p.stderr
                    assert not any('/objects/' in path for path in requests[before:])
                    assert modes(rejected)['ftesurf64'] == 0o644
                    if linked_file:
                        assert stat.S_IMODE(external.stat().st_mode) == 0o644
                        assert external.read_bytes() == payloads['ftesurf.sh']
                    record(name + '-no-earlier-chmod', rejected, p)

                # WSL commonly runs as root. A nobody child proves a real chmod
                # failure propagates without publishing completion/clearing pending.
                if os.geteuid() == 0:
                    work.chmod(0o711)
                    denied = install('chmod-denied')
                    for path in payloads:
                        (denied / path).chmod(0o644)  # readable to actor, still owned by root
                    meta = denied / '.ftesurf-updater'
                    meta.mkdir()
                    pending = meta / 'pending.json'
                    journal = json.dumps({'envelope': data.decode(), 'paths': []}).encode()
                    pending.write_bytes(journal)
                    lock = meta / 'install.lock'
                    lock.touch()
                    lock.chmod(0o666)
                    p = subprocess.run([str(launcher), '--dir', str(denied), '--offline', '--no-launch', '--allow-insecure'], capture_output=True, text=True, timeout=20, user=65534, group=65534, extra_groups=[])
                    assert p.returncode != 0 and 'cannot enable execute permission: ftesurf64' in p.stderr, (p.returncode, p.stdout, p.stderr)
                    assert pending.read_bytes() == journal and modes(denied)['ftesurf64'] == 0o644
                    assert not (meta / 'installed.json').exists() and not (meta / 'state.json').exists()
                    preserved(denied)
                    record('chmod-denied-retains-pending-no-ready-ledger', denied, p)
                else:
                    skipped.append('chmod-denied control requires root to start a distinct unprivileged fixture child')

                # Even a signed exec flag cannot authorize chmod of player-owned files.
                protected = install('protected-exec-flag')
                extra = json.loads(json.dumps(manifest))
                for path in ('ftesurf/maps/zones/local/surf_fixture.json', 'ftesurf/fs_addons.txt'):
                    extra['files'].append(dict(path=path, hash=h(b'published default'), size=len(b'published default'), platform='all', exec=True))
                (feed / 'update.json').write_bytes(updatefeed.envelope(extra, seed))
                p = invoke(protected, '--no-launch')
                preserved(protected)
                record('signed-protected-exec-flags-no-chmod', protected, p)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            assert not thread.is_alive()

    # The context above proves runtime-only fixtures have been retired.
    assert not Path(tmp).exists()
    result = dict(status='PASS', expected_before=a.expect_before,
                  launcher_sha256=hashlib.sha256(launcher.read_bytes()).hexdigest(),
                  runtime_fixtures_retired=True, cases=cases, skipped=skipped, requests=requests)
    a.evidence.write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS {len(cases)} acted POSIX controls; evidence: {a.evidence}')


if __name__ == '__main__':
    main()
