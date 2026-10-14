#!/usr/bin/env python3
"""Live retained-generation apply admission; no launcher execution or product edits."""
import argparse
from collections import Counter
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

from test_update_handoff import owned_job
from test_update_native_journal import (UNCONFIRMED_PHASES, preflight_paths, sha,
    snapshot, _checked_files, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import pe_text
from test_update_native_windows_unreadable import kernel32, busy_port_control
import test_update_native_retirement_windows as retirement
import test_update_native_staging_windows as staging

REFUSAL = 'retained update recovery; run the launcher before another update'
READY = 'RETAINED_APPLY_READY'
LOCK = '.ftesurf-updater/install.lock'
LIVE_LOG = 'ftesurf/logs/retained-apply.log'


def state(dest):
    return {p.relative_to(dest).as_posix(): p.read_bytes() for p in _checked_files(dest)
            if p.relative_to(dest).as_posix() not in (LOCK, LIVE_LOG)}


def active_snapshot(dest, target):
    """Incomplete active export: exact registered log/lock only; NOT retirement."""
    target.mkdir(parents=True)
    entries = []
    for relative, data in state(dest).items():
        out = target / 'files' / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        assert out.read_bytes() == data
        entries.append(dict(path=relative, size=len(data), sha256=sha(data)))
    (target / 'inventory.json').write_text(json.dumps(dict(full_export=False,
        excluded=[LOCK, LIVE_LOG], files=entries), indent=2) + '\n')


def grade_unchanged(baseline, actual):
    # Logs/cfg are control artifacts; everything else, including new metadata,
    # must be byte-identical, not merely the old authority's selected rows.
    def content(files):
        return {p: b for p, b in files.items() if p != LIVE_LOG}
    assert content(actual) == content(baseline), 'apply/check changed retained content or authority'
    return dict(unchanged_files=len(content(baseline)))


def grade_http(hits, path, files, retained):
    expected = {'/update.json': 1}
    if not retained:
        h = files[path]['hash']
        expected['/objects/' + h[:2] + '/' + h] = 1
    assert dict(hits) == expected, ('signed-mirror census', dict(hits), expected)
    return dict(hits)


def grade_installed(f, path, baseline, actual):
    """Complete expected positive map; no metadata/log namespace exemption."""
    ledger = '.ftesurf-updater/state.json'
    stage = '.ftesurf-updater/ingame/staged/' + f['files'][path]['hash']
    tmp = '.ftesurf-updater/ingame/journal.tmp'
    authority = '.ftesurf-updater/ingame/journal.json'
    assert authority not in baseline, 'positive fixture already has retained authority'
    assert stage in baseline and tmp in baseline, 'positive survivor/consumed-temp controls absent'
    assert json.loads(actual[ledger]) == f['ledger'], 'complete ledger changed protected policy'
    expected = dict(baseline)
    expected[path] = f['payload'][path]
    expected[ledger] = actual[ledger]  # ONLY fully checked ledger formatting may differ.
    expected['.ftesurf-updater/installed.json'] = f['signed']
    expected['.ftesurf-updater/ingame/manifest.json'] = f['signed']
    del expected[stage]  # The sole downloaded/install transaction's signed object.
    del expected[tmp]   # Native journal publication consumes this exact sibling.
    assert actual == expected, 'positive changed/removed/added unrelated content or metadata'
    return dict(installed_path=path, installed_sha256=sha(f['payload'][path]),
                exact_files=len(expected), removed_paths=[stage, tmp])


def persist_http(target, hits, lifecycle, live_completed):
    target.mkdir(parents=True)
    receipt = dict(status='PASS' if live_completed and lifecycle.get('joined') else 'FAIL',
                   joined=lifecycle.get('joined', False), live_completed=live_completed,
                   hits=dict(hits))
    (target / 'census.json').write_text(json.dumps(receipt, indent=2) + '\n')


@contextmanager
def mirror(signed, manifest, files, payload, lifecycle):
    url = urlsplit(manifest['mirrors'][0])
    assert url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port and not url.path
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
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *unused):
            pass
    server = staging.OfflineHTTPServer(('127.0.0.1', url.port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield hits, f'http://127.0.0.1:{url.port}/update.json'
    finally:
        server.shutdown()
        thread.join(timeout=10)
        assert not thread.is_alive()
        server.server_close()  # Joins every accepted non-daemon worker, even on live failure.
        lifecycle['joined'] = True


def semantic(phase, checker):
    guard = phase / 'semantic-guard'
    UNCONFIRMED_PHASES.add(guard)
    receipt = dict(status='FAIL')
    try:
        receipt.update(checker(), status='PASS')
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        (phase / 'grade.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if receipt['status'] == 'PASS':
            UNCONFIRMED_PHASES.discard(guard)


def live(engine, f, phase, url, retained, before):
    dest, meta = f['dest'], f['meta']
    phase.mkdir()
    UNCONFIRMED_PHASES.add(phase)
    cfg = dest / 'ftesurf/cfg/test/retained-apply.cfg'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
        'update_autocheck 0\nupdate_allow_insecure 1\n'
        f'update_manifest_url "{url}"\n'
        'developer 1\nlog_developer 1\nlog_name retained-apply\nlog_enable 1\n'
        f'echo {READY}\n')
    args = [str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'vid_renderer', 'headless', '+exec', 'cfg/test/retained-apply.cfg']
    receipt = dict(status='FAIL', argv=args, engine_sha256=sha(engine.read_bytes()), retained=retained, before=before)
    process = job = None
    natural = exported = False
    def logs():
        return '\n'.join(p.read_text(errors='replace') for p in dest.rglob('retained-apply*.log'))
    def wait(actor):
        until = time.monotonic() + 30
        while time.monotonic() < until:
            text = logs()
            if actor in text:
                return text
            assert process.poll() is None, 'native client exited before: ' + actor
            time.sleep(.05)
        raise AssertionError('missing native actor: ' + actor)
    def send(command):
        process.stdin.write((command + '\n').encode())
        process.stdin.flush()
    def capture(name, checker):
        target = phase / name
        active_snapshot(dest, target)
        semantic(target, checker)
    try:
        with (phase / 'stdout.log').open('wb') as out:
            process = subprocess.Popen(args, cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=out,
                stderr=subprocess.STDOUT, creationflags=4)
            job = owned_job(process)
            receipt['pid'] = process.pid
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes, resume.restype = [w.HANDLE], ctypes.c_long
            assert resume(int(process._handle)) == 0
            wait(READY)
            # Startup complete-only replay must preserve corrupt named candidates.
            def startup():
                if retained and not before:
                    actual = state(dest)
                    ledger_path = '.ftesurf-updater/state.json'
                    assert json.loads(actual[ledger_path]) == json.loads(f['seed'][ledger_path])
                    # Complete-only cold replay rewrites ledger formatting at boot;
                    # this is BEFORE the live check/apply baseline, not an exemption
                    # for subsequent replacement of any authority or ledger bytes.
                    expected = f['seed'] | {ledger_path: actual[ledger_path]}
                    return grade_unchanged(expected, actual)
                if retained:
                    assert not (meta / 'ingame/journal.json').exists(), 'old unlink defect must ACT'
                    assert (meta / 'ingame/manifest.json').read_bytes() == f['signed']
                    for h, data in f['stage'].items():
                        assert (meta / 'ingame/staged' / h).read_bytes() == data
                    return dict(before_lost_authority=True)
                return grade_unchanged(f['seed'], state(dest))
            # cfg was authored after seed; include only that exact runner artifact.
            f['seed'][cfg.relative_to(dest).as_posix()] = cfg.read_bytes()
            capture('startup', startup)
            # Signed-complete startup otherwise produces no plan. Author a single
            # managed drift AFTER startup on both arms, not a cached/echo plan.
            path = f['resolved']
            (dest / path).write_bytes(staging.OLD)
            baseline = state(dest)
            capture('pre-check', lambda: grade_unchanged(baseline, state(dest)))
            send('update_check force')
            wait('update: 1 file (')
            send('update_info; echo RETAINED_APPLY_PLANNED')
            assert 'update state : available' in wait('RETAINED_APPLY_PLANNED')
            capture('planned', lambda: grade_unchanged(baseline, state(dest)))
            send('update_apply')
            refuse = retained and not before
            wait(REFUSAL if refuse else 'update: installed 1 files')
            send('update_info; echo RETAINED_APPLY_RESULT')
            text = wait('RETAINED_APPLY_RESULT').split('RETAINED_APPLY_PLANNED', 1)[1]
            assert ('update state : launcher' if refuse else 'update state : restart') in text
            if refuse:
                capture('applied', lambda: grade_unchanged(baseline, state(dest)))
            else:
                def installed():
                    return grade_installed(f, path, baseline, state(dest))
                capture('applied', installed)
            send('echo RETAINED_APPLY_DONE; quit')
            process.wait(timeout=30)
            assert process.returncode == 0 and 'RETAINED_APPLY_DONE' in logs()
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            natural = True
            wait_win_job_empty(job, receipt, 'job_active_after_cleanup')
            snapshot(dest, phase / 'final')
            exported = True
            semantic(phase / 'final', lambda: grade_unchanged(baseline, state(dest)) if refuse else installed())
            receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        try:
            if job and not natural:
                stop_win_job(job, process, receipt)
            elif process and process.poll() is None:
                process.terminate()  # own suspended process if job registration failed
                process.wait(timeout=10)
            if not exported:
                snapshot(dest, phase / 'failed-final')
                exported = True
        finally:
            if job:
                assert kernel32().CloseHandle(job), ctypes.get_last_error()
            if process and process.stdin:
                process.stdin.close()
            receipt.update(exit=process.poll() if process else None, natural_job0=natural, full_export=exported)
            (phase / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
            if receipt['status'] == 'PASS' and natural and exported:
                UNCONFIRMED_PHASES.discard(phase)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'feed', 'runtime-root', 'evidence', 'source', 'build-receipt', 'serializer'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    assert pe_text(engine) == pe_text(symbols)
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    build = json.loads(a.build_receipt.read_text())
    assert build['status'] == 'PASS' and build['source_unchanged'] is True
    assert build['engine_sha256'] == sha(engine.read_bytes())
    assert build['symbols_sha256'] == sha(symbols.read_bytes())
    assert build['qkupdate_sha256'] == sha(a.source.read_bytes())
    signed, manifest, files, payload = staging.load_inputs(a.feed, a.objects)
    binding = {str(p.resolve()): sha(p.read_bytes()) for p in
               (engine, symbols, a.source, a.build_receipt, a.serializer)}
    if not a.expect_before:
        assert sha(a.source.read_bytes()) == '7321da290913f67c047f1cf86103203ad79327d05dbacb44fe7ca9da695ec5d3'
        assert binding[str(engine)] == 'b566bf46b17a2f7cb4e95599e2089ad7fabff4dc9397ac5bc982ed6210480596'
    else:
        assert binding[str(engine)] == 'f9ba9842a5a138cfcffcd1c826488fad6dfbecbc2e3588b18a4d7cc067f514bc'
    sources = {str(Path(m.__file__).resolve()): sha(Path(m.__file__).read_bytes())
               for m in list(sys.modules.values()) if getattr(m, '__file__', None)
               and Path(m.__file__).resolve().parent == Path(__file__).resolve().parent}
    sources[str(Path(__file__).resolve())] = sha(Path(__file__).read_bytes())
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned apply admission fixtures; preserve runtime/guards on failure; no peers.\n')
    result = dict(status='FAIL', binding=binding, sources=sources, signed_sha256=sha(signed),
                  argv=sys.argv, expect_before=a.expect_before, cases=[])
    try:
        result['busy_port_control'] = busy_port_control()
        for retained in (False, True):
            name = 'retained-corrupt' if retained else 'ordinary-apply'
            f = retirement.prepare(root, name, 'unique', False, signed, manifest, files, payload, completed=True)
            (f['meta'] / 'consent').write_bytes(b'1\n')
            if retained:
                for row in f['rows']:
                    data = staging.corrupt_same_size(payload[row['p']])
                    (f['meta'] / 'ingame/staged' / row['h']).write_bytes(data)
                    f['stage'][row['h']] = data
            else:
                (f['meta'] / 'ingame/journal.json').unlink()
            f['seed'] = state(f['dest'])
            snapshot(f['dest'], evidence / (name + '-seed'))
            hits, lifecycle, live_completed = Counter(), {}, False
            target = evidence / name / 'http'
            try:
                with mirror(signed, manifest, files, payload, lifecycle) as (hits, url):
                    live(engine, f, evidence / name, url, retained, a.expect_before)
                    live_completed = True
            finally:
                persist_http(target, hits, lifecycle, live_completed)
            assert lifecycle.get('joined'), 'mirror close/join unconfirmed'
            semantic(target, lambda: dict(signed_mirror_http=grade_http(hits, f['resolved'], files, retained and not a.expect_before), joined=True))
            result['cases'].append(name)
        assert not UNCONFIRMED_PHASES
        assert all(sha(Path(p).read_bytes()) == h for p, h in (binding | sources).items())
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        result['runtime_retained'] = str(root)
        result['unconfirmed_guards'] = sorted(map(str, UNCONFIRMED_PHASES))
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
