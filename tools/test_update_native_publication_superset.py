#!/usr/bin/env python3
"""Separate full-survivor oracle for immutable native deferred publication actors."""
import argparse
from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

from test_update_native_journal import preflight_paths, sha, snapshot, ensure_retirable
from test_update_native_journal_initial import bind_initial, cold_phase
import test_update_native_journal_deferred as failure
import test_update_native_journal_deferred_interrupt as interruption
from test_update_native_retirement_windows import inventory
from test_update_native_staging_windows import load_inputs, journal, OfflineHTTPServer
from test_update_native_recovery import digest

BEFORE = 'f9ba9842a5a138cfcffcd1c826488fad6dfbecbc2e3588b18a4d7cc067f514bc'
SUBJECT = 'b566bf46b17a2f7cb4e95599e2089ad7fabff4dc9397ac5bc982ed6210480596'
OLD = b'owned previous publication content\n'


def full_authority(actual, files, paths, version, attempts):
    # Never derive expected rows from the native journal or its temp.
    assert actual == journal(files, paths, version, attempts), 'original signed transaction rows lost'


def stage_map(dest):
    path = dest / '.ftesurf-updater/ingame/staged'
    return inventory(path) if path.exists() else {}


def check_bytes(dest, expected):
    for path, data in expected.items():
        assert (dest / path).read_bytes() == data, 'closure/protected identity: ' + path


@contextmanager
def mirror_server(manifest, signed, payload, files):
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path
    objects = {'/objects/' + f['hash'][:2] + '/' + f['hash']: payload[p] for p, f in files.items()}
    hits = Counter()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(3)
            super().setup()
        def do_GET(self):
            hits[self.path] += 1
            data = signed if self.path == '/update.json' else objects.get(self.path)
            if data is None:
                self.send_error(404)
            else:
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        def log_message(self, *args):
            pass
    with OfflineHTTPServer(('127.0.0.1', mirror.port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield hits, f'http://127.0.0.1:{mirror.port}/update.json'
        finally:
            server.shutdown()
            thread.join(timeout=10)
            assert not thread.is_alive()
    # OfflineHTTPServer.server_close joins ALL accepted request workers here.


def prepare(root, name, payload, files, paths):
    dest = root / name
    dest.mkdir()
    zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
    guards = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// publication settings\n',
              'ftesurf/data/runs/player-sentinel.rec': b'publication recording\n',
              'ftesurf/gfx/publication-unmanaged.txt': b'publication unmanaged\n',
              zone: b'// publication preserved zone edit\n'}
    expected = payload | guards | {p: OLD for p in paths}
    for p, data in expected.items():
        target = dest / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    meta = dest / '.ftesurf-updater'
    meta.mkdir()
    (meta / 'consent').write_bytes(b'1\n')
    ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
    ledger['files'].update({p: digest(OLD) for p in paths})
    (meta / 'state.json').write_text(json.dumps(ledger))
    return dest, meta, expected, ledger


def grade_state(dest, meta, expected, ledger, signed, version, complete=False):
    check_bytes(dest, expected)
    assert json.loads((meta / 'state.json').read_text()) == ledger, 'complete current ledger/version mismatch'
    assert (meta / 'consent').read_bytes() == b'1\n'
    assert (meta / 'ingame/manifest.json').read_bytes() == signed
    certificate = meta / 'installed.json'
    if complete:
        assert ledger['version'] == version and certificate.read_bytes() == signed
    else:
        assert ledger['version'] == '0.1.24' and not certificate.exists()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'helper', 'failure-helper', 'feed', 'runtime-root', 'evidence', 'serializer'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    assert sha(engine.read_bytes()) == (BEFORE if a.expect_before else SUBJECT), 'exact inspected native arm required'
    helper, helper_hash = failure.helper_identity(a.helper)
    fail_helper, fail_hash = failure.helper_identity(a.failure_helper)
    binding = bind_initial(engine, symbols, Path('C:/msys64/ucrt64/bin/nm.exe'), Path('C:/msys64/ucrt64/bin/objdump.exe'))
    assert binding['before'] is False, 'both inspected clients have atomic P692 publication'
    fail_binding = failure.bind_writer(engine, symbols, Path('C:/msys64/ucrt64/bin/nm.exe'), Path('C:/msys64/ucrt64/bin/objdump.exe'))
    signed, manifest, files, payload = load_inputs(a.feed, a.objects)
    paths = [p for p in files if p in ('ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png')]
    assert len(paths) == 2 and files[paths[0]]['hash'] != files[paths[1]]['hash']
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Publication lane owned synthetic runtimes. Retained for independent review; no cleanup of failed attempts.\n')
    source_paths = list(Path(__file__).parent.glob('test_update_native*.py')) + [Path(__file__), a.serializer,
        Path(__file__).with_name('native_journal_initial.c'), Path(__file__).with_name('native_journal_live_fault.c'),
        Path(__file__).with_name('updatefeed.py'), Path(__file__).with_name('test_update_handoff.py')]
    hashes = {str(p): sha(p.read_bytes()) for p in source_paths}
    result = dict(status='FAIL', binding=binding, failure_binding=fail_binding, sources=hashes,
                  helper_sha256=helper_hash, failure_helper_sha256=fail_hash, signed_sha256=sha(signed), cases=[])
    expected_http = Counter()
    try:
        with mirror_server(manifest, signed, payload, files) as (hits, url):
            for pending in paths:
                content = next(p for p in paths if p != pending)
                position = 'pending-first' if pending == paths[0] else 'pending-last'
                for mode in ('source-lock', 'crash-before', 'crash-after', 'none'):
                    name = position + '-' + mode
                    dest, meta, expected, ledger = prepare(root, name, payload, files, paths)
                    case = evidence / name
                    case.mkdir()
                    snapshot(dest, case / 'seed')
                    if mode == 'source-lock':
                        failure.live(engine, fail_helper, fail_binding, dest, case / 'live', mode, False,
                                     dict(url=url, paths=[content, pending]))
                        native_temp = (meta / 'ingame/journal.tmp').read_bytes()
                    else:
                        interruption.live(engine, helper, binding, dest, case / 'live', mode,
                                          dict(url=url, pending=pending))
                        native_temp = (case / 'live/pending-temp.json').read_bytes()
                    expected_http['/update.json'] += 1
                    for p in paths:
                        expected_http['/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash']] += 1
                    initial = (case / 'live/initial-authority.json').read_bytes()
                    full_authority(json.loads(initial), files, paths, manifest['version'], 1)
                    expected[content] = payload[content]  # ordinary install must ACT
                    ledger['files'][content] = files[content]['hash']
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                    full = journal(files, paths, manifest['version'], 1)
                    reduced = journal(files, [pending], manifest['version'], 1)
                    assert json.loads(native_temp) == (reduced if a.expect_before else full)
                    authority = meta / 'ingame/journal.json'
                    if mode in ('source-lock', 'crash-before'):
                        assert authority.read_bytes() == initial, 'failed/uncommitted publication changed authority'
                        assert (meta / 'ingame/journal.tmp').read_bytes() == native_temp
                    else:
                        assert authority.read_bytes() == native_temp and not (meta / 'ingame/journal.tmp').exists()
                    stages = {files[p]['hash']: payload[p] for p in paths}
                    if mode == 'none' and not a.expect_before:
                        del stages[files[content]['hash']]  # actual successful publication permits retirement
                    assert stage_map(dest) == stages, 'premature retirement or incomplete stage inventory'
                    detected = False
                    try:
                        full_authority(json.loads(authority.read_bytes()), files, paths, manifest['version'], 1)
                    except AssertionError:
                        assert a.expect_before and mode in ('none', 'crash-after')
                        detected = True
                    assert detected == (a.expect_before and mode in ('none', 'crash-after'))
                    (case / 'publication-oracle.json').write_text(json.dumps(dict(status='PASS',
                        legacy_full_survivor_oracle_rejected=detected, mode=mode, stages={k: sha(v) for k, v in stages.items()}), indent=2))
                    # Fresh ordinary cold repair acts without rewriting authority in the harness.
                    cold_phase(engine, dest, case / 'repair')
                    expected[pending] = payload[pending]
                    ledger = dict(version=manifest['version'], files={p: f['hash'] for p, f in files.items()})
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'], True)
                    assert not authority.exists()
                    if a.expect_before and mode in ('source-lock', 'crash-before'):
                        assert (meta / 'ingame/journal.tmp').read_bytes() == native_temp, 'legacy failed sibling must remain exact'
                    else:
                        assert not (meta / 'ingame/journal.tmp').exists()
                    survivors = {files[content]['hash']: payload[content]} if detected else {}
                    assert stage_map(dest) == survivors, 'repair did not ACT exact retirement/orphan control'
                    snapshot(dest, case / 'final')
                    result['cases'].append(name)
                    print('PASS publication-superset', name, 'before' if a.expect_before else 'subject', flush=True)
        interruption.grade_http(hits, dict(expected_http))  # census AFTER all accepted handlers join
        result['signed_mirror_http_joined'] = dict(hits)
        assert {str(p): sha(p.read_bytes()) for p in source_paths} == hashes, 'source freeze changed'
        assert sha(engine.read_bytes()) == binding['engine_sha256'] and sha(symbols.read_bytes()) == binding['symbols_sha256']
        assert sha(helper.read_bytes()) == helper_hash and sha(fail_helper.read_bytes()) == fail_hash
        ensure_retirable()
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        result['runtime_retired'] = False
        result['retention'] = str(root) + ': source/evidence review fixtures and all failed attempts retained; no blanket cleanup'
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
