#!/usr/bin/env python3
"""Signed launcher supersession of a retained native retirement generation.

Separate gate; never signs feeds, edits historical graders, or starts a game from
Rust. The external native candidate is used only for owned cold-start controls.
"""
import argparse
from collections import Counter
import copy
import ctypes
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import urlsplit

from test_update_handoff import owned_job
from test_update_native_journal import (UNCONFIRMED_PHASES, ensure_retirable,
    preflight_paths, sha, snapshot, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import pe_text
from test_update_native_journal_initial import cold_phase
from test_update_native_journal_interrupt import EXHAUSTED
import test_update_native_retirement_windows as retirement
import test_update_native_staging_windows as staging


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def authority_inventory(f):
    return {p: b for p, b in retirement.inventory(f['dest']).items()
            if not p.endswith('install.lock') and not p.endswith('.log')}


def grade_unchanged(f, before):
    assert authority_inventory(f) == before, 'launcher refusal changed authority/content/staging'
    return {'unchanged': True, 'file_count': len(before)}


def grade_repaired(f, original, staged, ledger, hits, expected_objects):
    """Independent signed closure + exact authority parking and object-set oracle."""
    meta = f['meta']
    for path, wanted in f['payload'].items():
        actual = (f['dest'] / path).read_bytes()
        assert actual == f['sentinels'].get(path, wanted), 'signed/protected closure: ' + path
    for path, wanted in f['sentinels'].items():
        assert (f['dest'] / path).read_bytes() == wanted, 'unmanaged/protected: ' + path
    assert (meta / 'consent').read_bytes() == b'1\n'
    assert not (meta / 'ingame/journal.json').exists(), 'old authority still blocks generation'
    parked = list(meta.glob('recovered-ingame-*.json'))
    assert len(parked) == 1 and parked[0].read_bytes() == original, 'old full authority not parked exactly'
    assert (meta / 'ingame/manifest.json').read_bytes() == f['signed'], 'old signed envelope changed'
    assert (meta / 'installed.json').read_bytes() == f['signed'], 'false completion certificate'
    assert not (meta / 'pending.json').exists(), 'Rust transaction not completed'
    actual_staged = {p.name: p.read_bytes() for p in (meta / 'ingame/staged').iterdir()}
    assert actual_staged == staged, 'launcher swept/adopted old native stage bytes'
    assert (meta / 'ingame/journal.tmp').read_bytes() == f['extras']['ingame/journal.tmp'], 'old failed sibling changed'
    wanted_ledger = copy.deepcopy(ledger)
    wanted_ledger['version'] = f['version']
    for path, entry in f['files'].items():
        if f['sentinels'].get(path, f['payload'][path]) == f['payload'][path]:
            wanted_ledger['files'][path] = entry['hash']
    assert json.loads((meta / 'state.json').read_text()) == wanted_ledger, 'ledger/protected policy mismatch'
    assert hits == Counter({'/update.json': 1, **expected_objects}), 'wrong signed mirror census: ' + repr(hits)
    return {'parked_authority_sha256': sha(original), 'signed_file_count': len(f['files']),
            'native_stage_sha256': {n: sha(b) for n, b in staged.items()},
            'signed_mirror_http': dict(hits), 'complete_version': f['version']}


def launcher_phase(launcher, f, phase, url, extra=(), expected_error=None):
    phase.mkdir(parents=True)
    UNCONFIRMED_PHASES.add(phase)
    args = [str(launcher), '--dir', str(f['dest']), '--no-launch', '--allow-insecure',
            '--manifest-url', url, *extra]
    process = job = None
    receipt = {'status': 'FAIL', 'argv': args, 'expected_error': expected_error}
    contained = exported = False
    try:
        with (phase / 'output.log').open('wb') as out:
            process = subprocess.Popen(args, cwd=f['dest'], stdin=subprocess.DEVNULL,
                stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            receipt['pid'] = process.pid
            job = owned_job(process)
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes = [ctypes.c_void_p]
            resume.restype = ctypes.c_long
            assert resume(int(process._handle)) == 0
            process.wait(timeout=90)
            receipt['exit'] = process.returncode
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
        text = (phase / 'output.log').read_text(encoding='utf-8', errors='replace')
        if expected_error:
            assert process.returncode != 0 and expected_error in text, (process.returncode, text)
            assert 'is ready.' not in text and 'Recovered the interrupted in-game update.' not in text
        else:
            assert process.returncode == 0 and 'Recovered the interrupted in-game update.' in text, text
            assert f"FTESurf {f['version']} is ready." in text, text
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        try:
            if job:
                if receipt.get('job_active_before_cleanup') != 0:
                    stop_win_job(job, process, receipt)
                else:
                    wait_win_job_empty(job, receipt, 'job_active_after_cleanup')
            elif process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            contained = True
            snapshot(f['dest'], phase / 'state')
            exported = True
        except BaseException as error:
            receipt.update(status='FAIL', cleanup_export_error=repr(error))
            raise
        finally:
            if job:
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                assert kernel.CloseHandle(job)
            receipt.update(full_export=exported, containment_confirmed=contained)
            save(phase / 'process.json', receipt)
            if exported and contained:
                UNCONFIRMED_PHASES.discard(phase)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'launcher', 'launcher-binding', 'feed', 'runtime-root', 'evidence'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--objects', type=Path, action='append', required=True)
    args = parser.parse_args()
    assert os.name == 'nt', 'real Windows actors required'
    engine, symbols, launcher = (p.resolve(strict=True) for p in (args.engine, args.symbols, args.launcher))
    assert pe_text(engine) == pe_text(symbols), 'candidate executable/companion text mismatch'
    binding_bytes = args.launcher_binding.read_bytes()
    binding = json.loads(binding_bytes)
    assert sha(launcher.read_bytes()) == binding['sha256'].lower(), 'published launcher binary binding mismatch'
    launcher_repo = Path(binding['inspected_repo'])
    launcher_sources = binding['inspected_sources_sha256']
    assert all(sha((launcher_repo / n).read_bytes()) == h for n, h in launcher_sources.items()), 'launcher source binding changed'
    root, evidence = preflight_paths(args.runtime_root, args.evidence)
    signed, manifest, files, payload = staging.load_inputs(args.feed, args.objects)
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned retained-generation launcher fixtures. No launcher-spawned game; preserve failed runtime/guards.\n')
    sources = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('test_update_native*.py')}
    for name in ('updatefeed.py', 'test_update_handoff.py', 'test_ingame_update.py'):
        sources[name] = sha(Path(__file__).with_name(name).read_bytes())
    result = {'status': 'FAIL', 'engine_sha256': sha(engine.read_bytes()), 'symbols_sha256': sha(symbols.read_bytes()),
              'launcher_sha256': sha(launcher.read_bytes()), 'launcher_binding': binding,
              'feed_sha256': sha(signed), 'sources_sha256': sources,
              'launcher_binding_sha256': sha(binding_bytes), 'cases': []}
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path
    objects = {'/objects/' + entry['hash'][:2] + '/' + entry['hash']: payload[path] for path, entry in files.items()}
    mode, hits = {'online': False}, Counter()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(3)
            super().setup()
        def log_message(self, *unused):
            pass
        def do_GET(self):
            hits[self.path] += 1
            data = signed if self.path == '/update.json' else objects.get(self.path)
            if not mode['online'] or data is None:
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    f = None
    try:
        with staging.OfflineHTTPServer(('127.0.0.1', mirror.port), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for completed in (True, False):
                    name = 'complete-corrupt-stage3' if completed else 'incomplete-exhausted3'
                    case = evidence / name
                    case.mkdir()
                    f = retirement.prepare(root, name, 'corrupt-resolved', False, signed, manifest, files, payload,
                                           attempts=3, completed=completed)
                    # Existing enabled consent avoids testing first-run UI; --yes repair is explicit.
                    (f['meta'] / 'consent').write_bytes(b'1\n')
                    f['seed'] = retirement.inventory(f['dest'])
                    snapshot(f['dest'], case / 'seed')
                    cold_phase(engine, f['dest'], case / 'native-retained', None if completed else EXHAUSTED)
                    assert json.loads((f['meta'] / 'ingame/journal.json').read_text()) == retirement.authority(f, 3), 'candidate did not retain full original signed authority/budget'
                    if completed:
                        actual_stage = {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir()}
                        assert actual_stage == retirement.expected_objects(f, True), 'native retirement identity/removal did not ACT'
                        assert len(actual_stage) < len(f['stage']) + 2, 'native retirement did not ACT'
                        for path, data in f['payload'].items():
                            assert (f['dest'] / path).read_bytes() == f['sentinels'].get(path, data), 'native changed signed/protected closure'
                        assert json.loads((f['meta'] / 'state.json').read_text()) == f['ledger']
                        assert (f['meta'] / 'installed.json').read_bytes() == signed
                    else:
                        retirement.unchanged(f)
                    save(case / 'native-retained/grade.json', {'status': 'PASS', 'full_original_rows': len(f['rows']), 'attempts': 3, 'complete': completed})
                    before = authority_inventory(f)
                    original = (f['meta'] / 'ingame/journal.json').read_bytes()
                    staged = {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir()}
                    ledger = json.loads((f['meta'] / 'state.json').read_text())
                    initial_hits = dict(hits)
                    assert not initial_hits, 'cold native unexpectedly used mirror'
                    url = f'http://127.0.0.1:{mirror.port}/update.json'
                    launcher_phase(launcher, f, case / 'offline-refusal', url, ('--offline',),
                        'unfinished in-game update: enable updates')
                    save(case / 'offline-refusal/grade.json', grade_unchanged(f, before))
                    assert not hits, 'offline launcher requested network'
                    mode['online'] = False
                    launcher_phase(launcher, f, case / 'unavailable-refusal', url, ('--yes', '--verify'),
                        'cannot repair the unfinished in-game update while the update service is unavailable')
                    save(case / 'unavailable-refusal/grade.json', grade_unchanged(f, before))
                    assert hits == Counter({'/update.json': 1}), 'unavailable launcher object census'
                    hits.clear()
                    mode['online'] = True
                    launcher_phase(launcher, f, case / 'signed-repair', url, ('--yes', '--verify'))
                    expected_objects = {} if completed else {
                        '/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash']: 1
                        for p in (f['resolved'], f['pending'])}
                    grade = grade_repaired(f, original, staged, ledger, hits, expected_objects)
                    save(case / 'signed-repair/grade.json', {'status': 'PASS', **grade})
                    # Fresh same-candidate native startup proves supersession unblocks, not just Rust print.
                    mode['online'] = False
                    cold_phase(engine, f['dest'], case / 'native-after-repair')
                    assert not (f['meta'] / 'ingame/journal.json').exists()
                    assert {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir()} == staged
                    assert (f['meta'] / 'ingame/manifest.json').read_bytes() == signed
                    assert (f['meta'] / 'consent').read_bytes() == b'1\n'
                    post_grade = grade_repaired(f, original, staged, ledger, hits, expected_objects)
                    save(case / 'native-after-repair/grade.json', {'status': 'PASS', 'native_startup_acted': True, **post_grade})
                    result['cases'].append({'name': name, **grade})
                    # Keep census intact through fresh native; reset only after exact identity comparison.
                    assert hits == Counter({'/update.json': 1, **expected_objects})
                    print('PASS', name, flush=True)
                    if completed:
                        result['first_case_http'] = dict(hits)
                        hits.clear()
            finally:
                server.shutdown()
                thread.join(timeout=10)
                assert not thread.is_alive(), 'owned signed-mirror listener remains'
        # server_close joins ALL accepted workers; grade the late final census, not an early snapshot.
        assert hits == Counter(result['cases'][-1]['signed_mirror_http']), 'late HTTP after phase'
        result['final_signed_mirror_http'] = dict(hits)
        assert sha(engine.read_bytes()) == result['engine_sha256']
        assert sha(symbols.read_bytes()) == result['symbols_sha256']
        assert sha(launcher.read_bytes()) == result['launcher_sha256']
        assert args.launcher_binding.read_bytes() == binding_bytes, 'bootstrap binding changed'
        assert all(sha((launcher_repo / n).read_bytes()) == h for n, h in launcher_sources.items()), 'launcher sources changed'
        assert all(sha(Path(__file__).with_name(n).read_bytes()) == h for n, h in sources.items()), 'test sources changed'
        ensure_retirable()
        result['status'] = 'PASS'
        save(evidence / 'result.json', result)
        # Only verified successful synthetic fixtures; never historical roots, never failures.
        list(retirement._checked_files(root))
        shutil.rmtree(root)
        result['runtime_retired'] = not root.exists()
        assert result['runtime_retired']
    except BaseException as error:
        result.update(status='FAIL', error=repr(error), runtime_retired=False)
        if f:
            snapshot(f['dest'], evidence / 'failed-final-state')
        raise
    finally:
        result['guards'] = [str(p) for p in UNCONFIRMED_PHASES]
        save(evidence / 'result.json', result)


if __name__ == '__main__':
    main()
