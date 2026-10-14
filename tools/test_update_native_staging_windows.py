#!/usr/bin/env python3
"""Windows native authority-bounded staged retirement and orphan characterization.

Retained signed loopback closure + immutable external client only. No signing,
product edit, unreferenced deletion, power-loss or deployment acceptance.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import ctypes
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

import updatefeed
from test_update_native_journal import (PENDING_ERROR, REWRITE_ERROR, UNCONFIRMED_PHASES,
    preflight_paths, sha, source_lock)
from test_update_native_journal_initial import cold_phase
from test_update_native_journal_live import destination_lock, retire_runtime
from test_update_native_recovery import digest
from test_update_native_windows_unreadable import ExclusiveHTTPServer, busy_port_control, kernel32

KINDS = ('unique', 'corrupt-resolved', 'wrong-size-resolved', 'shared', 'rewrite-failure', 'reduced-orphan')
CORRUPT_KINDS = ('corrupt-resolved', 'wrong-size-resolved')
OLD = b'previous managed baseline\n'
EDITED = b'// intervening protected local edit; keep these exact bytes\n'
CORRUPT = b'corrupt pending staged object\n'
WRONG_SIZE_RESOLVED = b'corrupt resolved staged object\n'


def corrupt_same_size(data):
    assert data
    corrupt = bytes([data[0] ^ 1]) + data[1:]
    assert len(corrupt) == len(data) and digest(corrupt) != digest(data)
    return corrupt


def journal(files, paths, version, attempts):
    return dict(version=version, attempts=attempts, files=[dict(p=p, h=files[p]['hash'],
        s=files[p]['size'], x=int(files[p]['exec'])) for p in paths])


def select_paths(files, kind):
    assert kind in KINDS
    resolved, pending = ('ftesurf/gfx/env/missingtexture.png', 'ftesurf/textures/no_texture.png') if kind == 'shared' else (
        'ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png')
    zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
    assert files[resolved]['hash'] != files[zone]['hash'] != files[pending]['hash']
    assert (files[resolved]['hash'] == files[pending]['hash']) == (kind == 'shared'), 'signed shared/unique object control required'
    if kind == 'shared':
        assert files[resolved]['size'] == files[pending]['size']
    return resolved, zone, pending


def prepare(root, name, kind, pending_first, signed, manifest, files, payload):
    resolved, zone, pending = select_paths(files, kind)
    dest = root / name
    dest.mkdir()
    for path, data in payload.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    sentinels = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned settings sentinel\n',
        'ftesurf/data/runs/player-sentinel.rec': b'owned recording sentinel\n',
        'ftesurf/gfx/unmanaged-staging-sentinel.txt': b'owned unmanaged asset sentinel\n', zone: EDITED}
    for path, data in sentinels.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    meta = dest / '.ftesurf-updater'
    staged = meta / 'ingame/staged'
    staged.mkdir(parents=True)
    (meta / 'consent').write_bytes(b'0\n')
    (meta / 'ingame/manifest.json').write_bytes(signed)
    ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
    rows = [pending, zone, resolved] if pending_first else [resolved, zone, pending]
    stage = {}
    for path in rows:
        ledger['files'][path] = digest(OLD)
        stage[files[path]['hash']] = payload[path]
        if path != zone:
            (dest / path).write_bytes(OLD)
    if kind in ('shared', 'reduced-orphan'):
        (dest / resolved).write_bytes(payload[resolved])
    if kind == 'reduced-orphan':
        # Deliberately seeded reduced authority, NOT an interruption actor.
        rows = [pending]
        ledger['files'][resolved] = files[resolved]['hash']
        del stage[files[zone]['hash']]
    if kind != 'shared':
        stage[files[pending]['hash']] = CORRUPT
    if kind in CORRUPT_KINDS:
        corrupt = corrupt_same_size(payload[zone]) if kind == 'corrupt-resolved' else WRONG_SIZE_RESOLVED
        assert (len(corrupt) == files[zone]['size']) == (kind == 'corrupt-resolved')
        assert digest(corrupt) != files[zone]['hash']
        stage[files[zone]['hash']] = corrupt
    unrelated = {digest(b'valid unreferenced staged sentinel'): b'valid unreferenced staged sentinel',
                 digest(b'expected bytes not stored'): b'corrupt unreferenced staged sentinel'}
    assert not stage.keys() & unrelated.keys()
    stage.update(unrelated)
    for name, data in stage.items():
        (staged / name).write_bytes(data)
    authority = journal(files, rows, manifest['version'], 1)
    (meta / 'state.json').write_text(json.dumps(ledger))
    raw_authority = json.dumps(authority).encode()
    (meta / 'ingame/journal.json').write_bytes(raw_authority)
    return dict(dest=dest, meta=meta, files=files, payload=payload, signed=signed, version=manifest['version'],
        kind=kind, resolved=resolved, pending=pending, zone=zone, ledger=ledger, sentinels=sentinels,
        stage=stage, raw_authority=raw_authority)


def expected_stage(fixture, complete):
    f = fixture
    stage = dict(f['stage'])
    if complete:
        stage.pop(f['files'][f['pending']]['hash'])
        if f['kind'] != 'reduced-orphan':
            stage.pop(f['files'][f['resolved']]['hash'], None)
            if f['kind'] not in CORRUPT_KINDS:
                stage.pop(f['files'][f['zone']]['hash'], None)
    elif f['kind'] not in ('rewrite-failure', 'reduced-orphan'):
        if f['kind'] != 'shared':
            stage.pop(f['files'][f['resolved']]['hash'])
        if f['kind'] not in CORRUPT_KINDS:
            stage.pop(f['files'][f['zone']]['hash'])
    return stage


def grade(fixture, complete, hits):
    f = fixture
    assert not hits, 'unexpected cold signed-mirror HTTP: ' + repr(dict(hits))
    for path, data in f['sentinels'].items():
        assert (f['dest'] / path).read_bytes() == data, 'protected sentinel: ' + path
    assert (f['dest'] / f['resolved']).read_bytes() == f['payload'][f['resolved']], 'resolved install did not ACT'
    assert (f['dest'] / f['pending']).read_bytes() == (f['payload'][f['pending']] if complete else OLD)
    assert (f['meta'] / 'ingame/manifest.json').read_bytes() == f['signed']
    expected = dict(version=f['version'] if complete else f['ledger']['version'], files=dict(f['ledger']['files']))
    expected['files'][f['resolved']] = f['files'][f['resolved']]['hash']
    if complete:
        expected['files'][f['pending']] = f['files'][f['pending']]['hash']
    assert json.loads((f['meta'] / 'state.json').read_text()) == expected, 'false ledger hash/version'
    path = f['meta'] / 'ingame/journal.json'
    cert = f['meta'] / 'installed.json'
    if complete:
        assert not path.exists() and cert.read_bytes() == f['signed']
    else:
        assert not cert.exists(), 'partial state has completion certificate'
        if f['kind'] == 'rewrite-failure':
            assert path.read_bytes() == f['raw_authority'], 'failed commit changed prior authority'
        else:
            assert json.loads(path.read_text()) == journal(f['files'], [f['pending']], f['version'], 2)
    tmp = f['meta'] / 'ingame/journal.tmp'
    if f['kind'] == 'rewrite-failure':
        assert json.loads(tmp.read_text()) == journal(f['files'], [f['pending']], f['version'], 2)
        if complete:
            assert tmp.read_bytes() == f['failed_temp'], 'failed temp orphan changed on direct completion'
    else:
        assert not tmp.exists()
    actual = {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir()}
    assert actual == expected_stage(f, complete), 'wrong staged retention/removal'
    return dict(stage_sha256={name: sha(data) for name, data in actual.items()},
        signed_mirror_http=dict(hits), version=expected['version'], complete=complete)


def grade_phase(fixture, phase, complete, hits):
    guard = phase / 'semantic-receipt-guard'
    UNCONFIRMED_PHASES.add(guard)
    receipt = dict(status='FAIL')
    try:
        receipt.update(grade(fixture, complete, hits), status='PASS')
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        (phase / 'grade.json').write_text(json.dumps(receipt, indent=2) + '\n')
        UNCONFIRMED_PHASES.discard(guard)  # a failed receipt write must retain the guard


@contextmanager
def hold(fixture, case, receipt):
    guard = case / 'lock-guard'
    UNCONFIRMED_PHASES.add(guard)
    if fixture['kind'] == 'rewrite-failure':
        with source_lock(fixture['meta'] / 'ingame/journal.tmp', receipt):
            yield
    else:
        path = fixture['dest'] / fixture['pending']
        with destination_lock(path):
            probe = path.with_name(path.name + '.rename-probe')
            assert not probe.exists()
            k = kernel32()
            k.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
            assert not k.MoveFileExW(str(path), str(probe), 1), 'destination lock did not ACT'
            receipt['destination_rename_error'] = ctypes.get_last_error()
            assert receipt['destination_rename_error'] == 32 and path.read_bytes() == OLD and not probe.exists()
            yield
    (case / 'lock.json').write_text(json.dumps(receipt, indent=2) + '\n')
    UNCONFIRMED_PHASES.discard(guard)


class OfflineHTTPServer(ExclusiveHTTPServer):
    # server_close must join accepted workers before the final counter is read.
    daemon_threads = False
    block_on_close = True


def final_http(hits, result):
    assert not hits, 'unexpected final signed-mirror HTTP: ' + repr(dict(hits))
    result['signed_mirror_http'] = dict(hits)


@contextmanager
def offline_mirror(manifest):
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path
    hits = Counter()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(3)
            super().setup()
        def log_message(self, *args):
            pass
        def do_GET(self):
            hits[self.path] += 1
            self.send_error(503)
    with OfflineHTTPServer(('127.0.0.1', mirror.port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield hits
        finally:
            server.shutdown()
            thread.join(timeout=10)
            assert not thread.is_alive(), 'owned mirror did not stop'


def load_inputs(feed, bases):
    signed = feed.read_bytes()
    manifest = updatefeed.verify(signed)
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
    for kind in KINDS:
        select_paths(files, kind)
    payload = {}
    for path, entry in files.items():
        obj = next((base / entry['hash'][:2] / entry['hash'] for base in bases if
            (base / entry['hash'][:2] / entry['hash']).is_file()), None)
        assert obj and not obj.is_symlink(), 'missing/linked signed object: ' + path
        data = obj.read_bytes()
        assert len(data) == entry['size'] and digest(data) == entry['hash'], 'wrong signed object: ' + path
        payload[path] = data
    return signed, manifest, files, payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'feed', 'runtime-root', 'evidence'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    a = ap.parse_args()
    assert os.name == 'nt', 'Windows native driver required'
    engine = a.engine.resolve(strict=True)
    assert engine.is_file()
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    signed, manifest, files, payload = load_inputs(a.feed, a.objects)
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned synthetic Windows staged retirement fixtures; guarded job0/full evidence before retirement.\n')
    sources = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('test_update_native*.py')}
    for name in ('updatefeed.py', 'test_update_handoff.py', 'test_ingame_update.py'):
        sources[name] = sha(Path(__file__).with_name(name).read_bytes())
    result = dict(status='FAIL', engine_sha256=sha(engine.read_bytes()), feed_sha256=sha(signed),
        sources_sha256=sources, runtime_root=str(root), cases=[])
    fixture = None
    try:
        result['busy_port_control'] = busy_port_control()
        with offline_mirror(manifest) as hits:
            for kind in KINDS:
                for first in ((False,) if kind == 'reduced-orphan' else (False, True)):
                    name = kind if kind == 'reduced-orphan' else kind + ('-pending-first' if first else '-pending-last')
                    case = evidence / name
                    case.mkdir()
                    fixture = prepare(root, name, kind, first, signed, manifest, files, payload)
                    partial, complete = case / 'partial', case / 'complete'
                    if kind in ('shared', 'rewrite-failure'):
                        lock = {}
                        with hold(fixture, case, lock):
                            cold_phase(engine, fixture['dest'], partial, REWRITE_ERROR if kind == 'rewrite-failure' else PENDING_ERROR)
                    else:
                        cold_phase(engine, fixture['dest'], partial, PENDING_ERROR)
                    grade_phase(fixture, partial, False, hits)
                    if kind == 'rewrite-failure':
                        fixture['failed_temp'] = (fixture['meta'] / 'ingame/journal.tmp').read_bytes()
                    (fixture['meta'] / 'ingame/staged' / files[fixture['pending']]['hash']).write_bytes(payload[fixture['pending']])
                    cold_phase(engine, fixture['dest'], complete)
                    grade_phase(fixture, complete, True, hits)
                    result['cases'].append(name)
                    print('PASS', name, flush=True)
        final_http(hits, result)  # listener and every accepted request worker have stopped
        assert sha(engine.read_bytes()) == result['engine_sha256'], 'external client changed during testing'
        assert all(sha(Path(__file__).with_name(name).read_bytes()) == value for name, value in sources.items()), 'driver sources changed during testing'
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        retire_runtime(root, evidence, result, fixture['dest'] if fixture and result['status'] == 'FAIL' else None)


if __name__ == '__main__':
    main()
