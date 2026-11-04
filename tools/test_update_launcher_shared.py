#!/usr/bin/env python3
"""P1294: a real launcher against "all" entries, over an owned loopback feed; never starts a game.

An install made from an old-style feed (every file listed per platform, as 0.1.38 is) updates to a merged feed of the
same bytes with zero object downloads; a changed shared file downloads once; a fresh install from a merged feed gets
every file. The production key signs (the launchers pin it); key bytes never leave this process.
usage: test_update_launcher_shared.py --launcher <WOS-Launcher> --old-updatefeed <pre-P1294 updatefeed.py> --work-root <new dir>
"""
import argparse
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

import updatefeed


def load(path):
    spec = importlib.util.spec_from_file_location("updatefeed_old", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--old-updatefeed', type=Path, required=True)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--seed-file', type=Path, default=Path('C:/FTESurf-private/keys/ftesurf-updates/seed')
                    if os.name == 'nt' else Path('/mnt/c/FTESurf-private/keys/ftesurf-updates/seed'))
    a = ap.parse_args()
    old = load(a.old_updatefeed)
    me = 'win64' if os.name == 'nt' else 'linux64'
    root = a.work_root
    if root.exists():
        raise SystemExit('Use a fresh uniquely owned test directory')
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('P1294 launcher loopback fixtures; no game is ever spawned.\n')
    serverdir = root / 'http'
    serverdir.mkdir()
    hits = Counter()

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            super().do_GET()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(serverdir)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    shared = ['default.fmf', 'ftesurf/menu.dat', 'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat', 'ftesurf/maps/tiers.txt',
              'ftesurf/gfx/rampwear/surf_fixture.txt', 'ftesurf/gfx/rampwear/surf_fixture.png']
    stages = {}
    for platform, exe in (('win64', 'ftesurf64.exe'), ('linux64', 'ftesurf64')):
        st = root / ('stage-' + platform)
        for p in shared + [exe, 'ftesurf.sh']:
            t = st / p
            t.parent.mkdir(parents=True, exist_ok=True)
            # ftesurf.sh: same bytes on both, exec only on Linux, so it stays native per platform
            t.write_bytes(('published ' + (p if p in shared or p == 'ftesurf.sh' else platform + ' ' + p) + '\n').encode())
        stages[platform] = st
    sentinels = {'ftesurf/ftesurf.cfg': b'player settings sentinel\n', 'ftesurf/data/consent.txt': b'consent sentinel\n',
                 'ftesurf/maps/zones/local/surf_fixture.json': b'edited zone sentinel\n'}
    seed = a.seed_file.read_bytes()
    serial = 0

    def publish(builder, version):
        nonlocal serial
        serial += 1
        out = root / f'feed-{serial}'
        builder.build(dict(stages), out, version, [base], seed)
        for obj in (out / 'objects').glob('*/*'):
            dest = serverdir / 'objects' / obj.parent.name / obj.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(obj, dest)
        shutil.copyfile(out / 'update.json', serverdir / 'update.json')
        return json.loads(json.loads((serverdir / 'update.json').read_text())['payload'])

    def run(install, expected=0):
        cmd = [str(a.launcher), '--dir', str(install), '--no-launch', '--allow-insecure',
               '--manifest-url', base + '/update.json', '--yes']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        (root / f'run-{serial:02d}-{install.name}.log').write_text(r.stdout + r.stderr)
        assert (r.returncode == 0) == (expected == 0), (r.returncode, r.stdout[-800:], r.stderr[-800:])
        for p, content in sentinels.items():
            assert (install / p).read_bytes() == content, p
        return r

    def want(install, platform):
        exe = 'ftesurf64.exe' if platform == 'win64' else 'ftesurf64'
        for p in shared + [exe, 'ftesurf.sh']:
            got = (install / p).read_bytes()
            assert got == (stages[platform] / p).read_bytes(), p
        other = 'ftesurf64' if platform == 'win64' else 'ftesurf64.exe'
        assert not (install / other).exists(), 'installed the other platform\'s engine'
        if platform == 'linux64':
            assert os.access(install / 'ftesurf.sh', os.X_OK) and os.access(install / 'ftesurf64', os.X_OK)

    def objects_fetched():
        return sum(n for p, n in hits.items() if '/objects/' in p)

    def fresh(name):
        d = root / name
        for p, content in sentinels.items():
            t = d / p
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(content)
        return d

    try:
        m = publish(old, '0.1.38')
        assert not any(f['platform'] == 'all' for f in m['files'])
        upd = fresh('install-upd')
        hits.clear(); run(upd); want(upd, me)
        print('PASS old-style feed (per-platform entries): installed, %d objects' % objects_fetched())
        m = publish(updatefeed, '0.1.39')
        n_all = sum(1 for f in m['files'] if f['platform'] == 'all')
        assert n_all == len(shared), n_all
        hits.clear(); run(upd); want(upd, me)
        assert hits['/update.json'] == 1 and objects_fetched() == 0, dict(hits)
        print('PASS update to the merged feed (%d "all" entries): accepted, 0 objects, files intact' % n_all)
        (stages['win64'] / 'ftesurf/menu.dat').write_bytes(b'new shared menu\n')
        (stages['linux64'] / 'ftesurf/menu.dat').write_bytes(b'new shared menu\n')
        m = publish(updatefeed, '0.1.40')
        assert any(f['path'] == 'ftesurf/menu.dat' and f['platform'] == 'all' for f in m['files'])
        hits.clear(); run(upd); want(upd, me)
        assert objects_fetched() == 1, dict(hits)
        print('PASS a changed shared file: 1 object, new bytes installed')
        new = fresh('install-new')
        hits.clear(); run(new); want(new, me)
        print('PASS fresh install from the merged feed: every file, none of the other platform\'s')
        bad = dict(m, files=m['files'] + [dict(next(f for f in m['files'] if f['platform'] == 'all'), platform=me)])
        try:
            updatefeed.validate(bad)
            raise AssertionError('publisher accepted an all + native overlap')
        except ValueError:
            pass
        print('PASS publisher refuses an all + native overlap before signing')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
