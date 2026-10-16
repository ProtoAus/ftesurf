#!/usr/bin/env python3
"""Real launcher falsifiers against an owned loopback feed; never starts a game.

Requires the production signing key only to make a feed the shipped pinned verifier
can accept. Key bytes never leave this process. HTTP fixtures require the EXPLICIT
loopback-only test flag and are never published. No player directories are used.
"""
import argparse
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

import updatefeed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--seed-file', type=Path, default=Path('C:/FTESurf-private/keys/ftesurf-updates/seed')
                    if os.name == 'nt' else Path('/mnt/c/FTESurf-private/keys/ftesurf-updates/seed'))
    a = ap.parse_args()
    platform = 'win64' if os.name == 'nt' else 'linux64'
    engine = 'ftesurf64.exe' if os.name == 'nt' else 'ftesurf64'
    root = a.work_root
    if root.exists():
        raise SystemExit('Use a fresh uniquely owned test directory')
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Launcher loopback fixtures; owned by updater task. No game is ever spawned.\n')
    serverdir, stagedir, install = root / 'http', root / 'stage', root / 'install'
    for p in (serverdir, stagedir, install): p.mkdir()
    hits = Counter()
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            super().do_GET()
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(serverdir)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    paths = ['default.fmf', engine, 'ftesurf/menu.dat', 'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat',
             'ftesurf/fs_addons.txt', 'ftesurf/maps/zones/local/surf_fixture.json',
             'ftesurf/maps/tiers.txt']
    for p in paths:
        target = stagedir / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(('published ' + p + '\n').encode())
    sentinels = {'ftesurf/ftesurf.cfg': b'player settings sentinel\n',
                 'ftesurf/data/consent.txt': b'player consent sentinel\n',
                 'hl2/pak01_dir.vpk': b'mounted content sentinel\n',
                 'ftesurf/fs_addons.txt': b'custom mount sentinel\n',
                 'ftesurf/maps/zones/local/surf_fixture.json': b'edited zone sentinel\n'}
    for p, content in sentinels.items():
        target = install / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    seed = a.seed_file.read_bytes()
    version = '0.1.25'
    serial = 0
    def publish(v=version):
        nonlocal serial
        serial += 1
        out = root / f'feed-{serial}'
        updatefeed.build({platform: stagedir}, out, v, [base], seed)
        for obj in (out / 'objects').glob('*/*'):
            dest = serverdir / 'objects' / obj.parent.name / obj.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(obj, dest)
        shutil.copyfile(out / 'update.json', serverdir / 'update.json')
        return json.loads((serverdir / 'update.json').read_text())
    def run(expected=0, extra=(), consent_yes=True):
        cmd = [str(a.launcher), '--dir', str(install), '--no-launch', '--allow-insecure',
               '--manifest-url', base + '/update.json', *(['--yes'] if consent_yes else []), *extra]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        (root / f'run-{len(list(root.glob("run-*.log"))):02d}.log').write_text(r.stdout + r.stderr)
        assert (r.returncode == 0) == (expected == 0), (r.returncode, r.stdout, r.stderr)
        for p, content in sentinels.items(): assert (install / p).read_bytes() == content, p
        return r
    try:
        good = publish()
        run()
        assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 6
        assert (install / 'ftesurf/maps/tiers.txt').read_bytes() == (stagedir / 'ftesurf/maps/tiers.txt').read_bytes()
        print('PASS positive install control: feed + 5 objects, protected sentinels unchanged')
        hits.clear(); run()
        assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        print('PASS current install: feed request, zero objects')
        consent = install / '.ftesurf-updater/consent'
        consent.write_text('0\n')
        hits.clear(); run(consent_yes=False)
        assert not hits and consent.read_text() == '0\n'
        print('PASS stored opt-out: zero requests, permission unchanged')
        consent.unlink()
        hits.clear(); run(1, consent_yes=False)
        assert not hits and not consent.exists()
        print('PASS undecided noninteractive launch: refuses before any request')
        consent.write_text('1\n')
        p = install / 'ftesurf/menu.dat'
        p.write_bytes(b'X' * p.stat().st_size)
        hits.clear(); run()
        assert sum(n for p, n in hits.items() if '/objects/' in p) == 1
        assert p.read_bytes() == (stagedir / 'ftesurf/menu.dat').read_bytes()
        print('PASS same-sized corruption repaired by hash, not trusted by size')
        bad = dict(good); bad['payload'] = bad['payload'].replace(version, '0.1.26')
        (serverdir / 'update.json').write_text(json.dumps(bad))
        hits.clear(); run(1)
        assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        print('PASS changed signed payload rejected before object requests')
        publish('0.1.24'); run(1)
        print('PASS older signed release rejected')
        publish()
        # Cross-process lock, same byte as the engine's LockFileEx/flock.
        lock = (install / '.ftesurf-updater/install.lock').open('r+b')
        if __import__('os').name == 'nt':
            import msvcrt
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        hits.clear(); run(1)
        assert not hits
        lock.close()
        print('PASS held game/updater lock rejects before network/writes')
        # Simulate interruption after the old menu was parked but before new file lands.
        (stagedir / 'ftesurf/menu.dat').write_bytes(b'new recovered menu\n')
        new = publish('0.1.26')
        m = json.loads(new['payload'])
        f = next(f for f in m['files'] if f['path'] == 'ftesurf/menu.dat')
        src = install / '.ftesurf-updater/download' / f['path']
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes((stagedir / f['path']).read_bytes())
        backup = install / '.ftesurf-updater/previous' / f['path']
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists(): backup.unlink()
        p.rename(backup)
        (install / '.ftesurf-updater/pending.json').write_text(json.dumps({'envelope': json.dumps(new), 'paths': [f['path']]}))
        hits.clear(); run(extra=('--offline',))
        assert not hits and p.read_bytes() == b'new recovered menu\n'
        assert not (install / '.ftesurf-updater/pending.json').exists()
        print('PASS interrupted replacement recovered fully before offline launch path')
        # Every pending recovery entry is preflighted BEFORE the first live rename.
        original_stage = {path: (stagedir / path).read_bytes() for path in ['ftesurf/menu.dat', 'ftesurf/csprogs.dat']}
        (stagedir / 'ftesurf/menu.dat').write_bytes(b'preflight new menu\n')
        (stagedir / 'ftesurf/csprogs.dat').write_bytes(b'preflight new csprogs\n')
        pending = install / '.ftesurf-updater/pending.json'
        for case in ['unsigned-later-path', 'corrupt-later-object', 'older-signed-journal', 'corrupt-ledger', 'missing-later-path', 'linked-recovery-metadata']:
            signed = publish('0.1.25' if case == 'older-signed-journal' else '0.1.27')
            entries = {f['path']: f for f in json.loads(signed['payload'])['files']}
            menu = entries['ftesurf/menu.dat']; client = entries['ftesurf/csprogs.dat']
            rows = [menu['path']]
            if case == 'unsigned-later-path': rows.append('ftesurf/ftesurf.cfg')
            if case in ['corrupt-later-object', 'older-signed-journal', 'linked-recovery-metadata']: rows.append(client['path'])
            for entry in [menu, client]:
                src = install / '.ftesurf-updater/download' / entry['path']
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_bytes(b'corrupt staged client' if case == 'corrupt-later-object' and entry == client else (stagedir / entry['path']).read_bytes())
            pending_bytes = json.dumps({'envelope': json.dumps(signed), 'paths': rows}).encode()
            pending.write_bytes(pending_bytes)
            ledger = install / '.ftesurf-updater/state.json'; ledger_bytes = ledger.read_bytes()
            if case == 'corrupt-ledger': ledger.write_bytes(b'{broken recovery ledger')
            before = {path: (install / path).read_bytes() for path in paths if (install / path).is_file()}
            link = install / '.ftesurf-updater/installed.json.tmp'
            target = root / 'recovery-metadata-target.txt'
            if case == 'linked-recovery-metadata':
                target.write_bytes(b'owned recovery metadata target\n'); link.symlink_to(target)
            try:
                hits.clear(); run(1, extra=('--offline',))
                assert not hits and all((install / path).read_bytes() == content for path, content in before.items()), case + ' changed live bytes before full preflight'
                if case == 'linked-recovery-metadata': assert target.read_bytes() == b'owned recovery metadata target\n'
            finally:
                if case == 'linked-recovery-metadata' and link.is_symlink(): link.unlink()
            assert pending.read_bytes() == pending_bytes, case + ' lost recovery marker'
            assert ledger.read_bytes() == (b'{broken recovery ledger' if case == 'corrupt-ledger' else ledger_bytes)
            pending.unlink() # ONLY this synthetic marker, after unchanged-byte assertions
            if case == 'corrupt-ledger': ledger.write_bytes(ledger_bytes)
        ledger_bytes = ledger.read_bytes()
        installed_manifest = install / '.ftesurf-updater/installed.json'; installed_bytes = installed_manifest.read_bytes()
        signed = publish('0.1.27')
        rows = ['ftesurf/menu.dat', 'ftesurf/csprogs.dat', 'ftesurf/maps/zones/local/surf_fixture.json']
        for path in rows:
            src = install / '.ftesurf-updater/download' / path
            src.parent.mkdir(parents=True, exist_ok=True); src.write_bytes((stagedir / path).read_bytes())
        pending.write_text(json.dumps({'envelope': json.dumps(signed), 'paths': rows}))
        hits.clear(); run(extra=('--offline',)) # run() also asserts EVERY protected sentinel
        assert not hits and not pending.exists()
        assert (install / 'ftesurf/menu.dat').read_bytes() == b'preflight new menu\n'
        assert (install / 'ftesurf/csprogs.dat').read_bytes() == b'preflight new csprogs\n'
        # Restore ONLY these synthetic fixture files/metadata for the remaining older arms.
        for path, content in original_stage.items():
            (stagedir / path).write_bytes(content); (install / path).write_bytes(content)
        ledger.write_bytes(ledger_bytes); installed_manifest.write_bytes(installed_bytes)
        publish('0.1.26')
        print('PASS whole Rust recovery preflight: later unsigned/corrupt entry, old signed journal, corrupt ledger, incomplete journal and linked metadata cannot mutate earlier valid files; signed journal preserves edited zone')
        # Opaque, damaged in-game metadata is NOT an authority for repair paths.
        journal = install / '.ftesurf-updater/ingame/journal.json'
        journal.parent.mkdir(parents=True, exist_ok=True)
        opaque = b'{"files":[{"p":"ftesurf/ftesurf.cfg"}],"damaged":'
        journal.write_bytes(opaque)
        cs = install / 'ftesurf/csprogs.dat'; cs.write_bytes(b'partial ingame replacement\n')
        hits.clear(); run(1, extra=('--offline',))
        assert not hits and journal.read_bytes() == opaque
        hits.clear(); run()
        assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 1
        assert cs.read_bytes() == (stagedir / 'ftesurf/csprogs.dat').read_bytes()
        assert not journal.exists()
        saved = list((install / '.ftesurf-updater').glob('recovered-ingame-*.json'))
        assert len(saved) == 1 and saved[0].read_bytes() == opaque
        print('PASS in-game marker: offline refuses; signed FULL feed repairs only managed paths and parks opaque metadata')
        ledger = install / '.ftesurf-updater/state.json'; ledger_bytes = ledger.read_bytes()
        ledger.write_bytes(b'{broken metadata')
        hits.clear(); run(1)
        assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        assert ledger.read_bytes() == b'{broken metadata'
        ledger.write_bytes(ledger_bytes)
        print('PASS corrupt ledger fails closed without object requests or destructive repair')
        valid = publish('0.1.26'); model = json.loads(valid['payload'])
        cases = []
        missing = json.loads(valid['payload']); missing['files'] = [f for f in model['files'] if f['path'] != 'ftesurf/menu.dat']; cases.append(missing)
        duplicate = json.loads(valid['payload']); duplicate['files'].append(dict(duplicate['files'][0])); cases.append(duplicate)
        inconsistent = json.loads(valid['payload']); alias = dict(inconsistent['files'][0]); alias.update(path='ftesurf/gfx/hash_alias.txt', size=alias['size']+1); inconsistent['files'].append(alias); cases.append(inconsistent)
        for case in cases:
            (serverdir / 'update.json').write_bytes(updatefeed.envelope(case, seed))
            hits.clear(); run(1)
            assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        nul = dict(valid); nul['payload'] += '\0ignored tail'
        (serverdir / 'update.json').write_text(json.dumps(nul))
        hits.clear(); run(1)
        assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
        publish('0.1.26')
        print('PASS signed missing/duplicate/inconsistent entries and decoded NUL payload rejected before objects')
        # A managed ancestor link must never redirect a game update outside its install.
        extra_file = stagedir / 'ftesurf/gfx/junction_fixture.txt'
        extra_file.parent.mkdir(parents=True, exist_ok=True); extra_file.write_bytes(b'signed fixture\n')
        publish('0.1.26')
        target = root / 'junction-target'; target.mkdir()
        marker = target / 'player-sentinel.txt'; marker.write_bytes(b'outside install sentinel\n')
        link = install / 'ftesurf/gfx'
        if os.name == 'nt':
            made = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True, text=True)
            assert made.returncode == 0, 'could not construct owned junction control'
        else: link.symlink_to(target, target_is_directory=True)
        try:
            hits.clear(); run(1)
            assert hits['/update.json'] == 1 and sum(n for p, n in hits.items() if '/objects/' in p) == 0
            assert marker.read_bytes() == b'outside install sentinel\n' and not (target / 'junction_fixture.txt').exists()
        finally:
            if os.name == 'nt': os.rmdir(link) # unlink ONLY our junction, never walk its target
            else: link.unlink()
        extra_file.unlink(); publish('0.1.26')
        print('PASS real junction/symlink rejected before object requests; outside sentinel unchanged')
        # Object corruption must leave every live game file at the previously installed set.
        (stagedir / 'ftesurf/menu.dat').write_bytes(b'new corrupt-object target\n')
        new = publish('0.1.27')
        m = json.loads(new['payload']); f = next(f for f in m['files'] if f['path'] == 'ftesurf/menu.dat')
        obj = serverdir / 'objects' / f['hash'][:2] / f['hash']
        obj.write_bytes(b'not the signed object')
        before = {f: (install / f).read_bytes() for f in paths if (install / f).exists()}
        run(1)
        assert all((install / f).read_bytes() == b for f, b in before.items())
        assert not (install / '.ftesurf-updater/pending.json').exists()
        print('PASS corrupt object fails before live replacements')
        # Transport failure permits a verified cached installation (not a bad signature).
        server.shutdown(); server.server_close()
        run()
        print('PASS unavailable update service uses verified cached installation')
        journal.write_bytes(opaque)
        run(1)
        assert journal.read_bytes() == opaque
        print('PASS unavailable service with in-game marker refuses mixed-install launch')
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    print('All launcher integration arms passed; logs retained under', root)


if __name__ == '__main__': main()
