#!/usr/bin/env python3
"""Owned Windows live initial-journal failure and deferred-rewrite controls.

Accepts a retained signed loopback feed and closure union. Never signs, changes
pins, starts an installed game or seizes an occupied listener. Cold helper proves
that the live journal actually replays after the deferred destination is released.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit

import updatefeed
from test_update_handoff import owned_job
from test_update_native_journal import (UNCONFIRMED_PHASES, ensure_retirable, preflight_paths,
    run_native, sha, snapshot, source_lock, stop_win_job, wait_win_job_empty)
from test_update_native_recovery import digest
from test_update_native_windows_unreadable import ExclusiveHTTPServer, busy_port_control, kernel32


@contextmanager
def destination_lock(path):
    k = kernel32()
    h = k.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)
    assert h != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        yield
    finally:
        assert k.CloseHandle(h), ctypes.get_last_error()


def live(engine, dest, evidence, kind, expect_before, rows):
    UNCONFIRMED_PHASES.add(evidence)
    cfg = dest / 'ftesurf/cfg/test/live-journal.cfg'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
                   'update_autocheck 0\nupdate_allow_insecure 1\n'
                   f'update_manifest_url "{rows["url"]}"\n'
                   'developer 1\nlog_developer 1\nlog_name journal-live\nlog_enable 1\n'
                   'echo JOURNAL_LIVE_READY\n')
    evidence.mkdir(parents=True)
    args = [str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'vid_renderer', 'headless', '+exec', 'cfg/test/live-journal.cfg']
    receipt = {'status': 'FAIL', 'kind': kind}
    process = job = None
    contained = exported = False
    def logs():
        return '\n'.join(p.read_text(errors='replace') for p in dest.rglob('journal-live*.log'))
    def wait(actor):
        until = time.monotonic() + 30
        while time.monotonic() < until:
            text = logs()
            if actor in text:
                return text
            assert process.poll() is None, 'client exited before actor: ' + actor
            time.sleep(0.05)
        raise AssertionError('live actor missing: ' + actor)
    def send(command):
        assert len(command.encode()) < 255
        process.stdin.write((command + '\n').encode())
        process.stdin.flush()
    try:
        with (evidence / 'stdout.log').open('wb') as out:
            process = subprocess.Popen(args, cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=out,
                                       stderr=subprocess.STDOUT, creationflags=4)
            job = owned_job(process)
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes = [w.HANDLE]
            resume.restype = ctypes.c_long
            assert resume(int(process._handle)) == 0
            wait('JOURNAL_LIVE_READY')
            send('update_check force')
            wait('update: 2 file')
            send('update_info; echo JOURNAL_LIVE_PLANNED')
            assert 'update state : available' in wait('JOURNAL_LIVE_PLANNED')
            meta = dest / '.ftesurf-updater'
            if kind == 'initial-failure':
                (meta / 'ingame').mkdir(parents=True, exist_ok=True)
                with source_lock(meta / 'ingame/journal.tmp', receipt):
                    send('update_apply')
                    reason = 'cannot save the complete recovery journal; nothing installed' if expect_before else 'cannot commit the recovery journal; nothing installed'
                    wait(reason)
                    send('update_info; echo JOURNAL_LIVE_REFUSED')
                    assert 'update state : error' in wait('JOURNAL_LIVE_REFUSED')
                    assert not (meta / 'ingame/journal.json').exists()
                    for path in rows['paths']:
                        assert (dest / path).read_bytes() == rows['old']
                    assert json.loads((meta / 'state.json').read_text()) == rows['ledger']
                    assert not (meta / 'installed.json').exists()
                # An active client holds an exclusive updater lock; full export is
                # after containment in finally, not during this same-process retry.
                (evidence / 'initial-refused.log').write_text(logs(), encoding='utf-8')
                send('update_check force')
                # Check is asynchronous: require a fresh second available actor.
                until = time.monotonic() + 30
                while logs().count('update: 2 file') < 2:
                    assert process.poll() is None and time.monotonic() < until
                    time.sleep(0.05)
                send('update_apply')
                wait('update: installed 2 files')
                assert not (meta / 'ingame/journal.json').exists()
                assert (meta / 'installed.json').read_bytes() == rows['signed']
                for path in rows['paths']:
                    assert (dest / path).read_bytes() == rows['payload'][path]
            else:
                with destination_lock(dest / rows['paths'][1]):
                    send('update_apply')
                    wait('update: installed 1 of 2 files; restart to finish')
                    journal = json.loads((meta / 'ingame/journal.json').read_text())
                    assert journal['attempts'] == 1 and [r['p'] for r in journal['files']] == [rows['paths'][1]]
                    assert (dest / rows['paths'][0]).read_bytes() == rows['payload'][rows['paths'][0]]
                    assert (dest / rows['paths'][1]).read_bytes() == rows['old']
                    assert json.loads((meta / 'state.json').read_text())['version'] == '0.1.24'
                    assert not (meta / 'installed.json').exists()
            send('update_info; echo JOURNAL_LIVE_DONE; quit')
            process.wait(timeout=30)
            text = logs()
            assert process.returncode == 0 and 'JOURNAL_LIVE_DONE' in text
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            contained = True
            receipt['status'] = 'PASS'
    except BaseException as error:
        receipt.update(status='FAIL', error=repr(error))
        raise
    finally:
        try:
            if job:
                natural = contained
                contained = False
                if not natural:
                    stop_win_job(job, process, receipt)
                else:
                    wait_win_job_empty(job, receipt, 'job_active_after_cleanup')
                contained = True
            elif process and process.poll() is None:
                process.terminate()  # job setup failed while client was suspended
                process.wait(timeout=10)
                contained = True
        except BaseException as error:
            receipt.update(status='FAIL', containment_error=repr(error))
            raise
        finally:
            try:
                for p in dest.rglob('journal-live*.log'):
                    shutil.copyfile(p, evidence / p.name)
                snapshot(dest, evidence / 'state')
                exported = True
            except BaseException as error:
                receipt.update(status='FAIL', export_error=repr(error))
                raise
            finally:
                try:
                    if job:
                        assert kernel32().CloseHandle(job), ctypes.get_last_error()
                    if process and process.stdin:
                        process.stdin.close()
                except BaseException as error:
                    receipt.update(status='FAIL', handle_cleanup_error=repr(error))
                    raise
                finally:
                    if process:
                        receipt.update(pid=process.pid, exit=process.poll())
                    receipt.update(full_export=exported, containment_confirmed=contained)
                    (evidence / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
                if contained and exported:
                    UNCONFIRMED_PHASES.discard(evidence)


def retire_runtime(root, evidence, result, dest=None):
    """Export failed-state evidence first; cleanup failure can never retain PASS."""
    try:
        if dest:
            snapshot(dest, evidence / 'failed-final-state')
        ensure_retirable()
        result.update(runtime_retired=False, retirement_authorized=True)
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        shutil.rmtree(root)  # retain runtime if export/containment/receipt raises
    except BaseException as error:
        result.update(status='FAIL', retirement_error=repr(error))
        raise
    finally:
        result['runtime_retired'] = not root.exists()
        if not result['runtime_retired']:
            result['status'] = 'FAIL'
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['engine', 'feed', 'runtime-root', 'evidence']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    engine = a.engine.resolve(strict=True)
    signed = a.feed.read_bytes()
    manifest = updatefeed.verify(signed)
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
    payload, objects = {}, {}
    for path, entry in files.items():
        obj = next((base / entry['hash'][:2] / entry['hash'] for base in a.objects if
                    (base / entry['hash'][:2] / entry['hash']).is_file()), None)
        assert obj and not obj.is_symlink(), path
        data = obj.read_bytes()
        assert len(data) == entry['size'] and digest(data) == entry['hash'], path
        payload[path] = data
        objects['/objects/' + entry['hash'][:2] + '/' + entry['hash']] = data
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned live journal synthetic runtime; no keys or installed player data.\n')
    result = dict(status='FAIL', expect_before=a.expect_before, engine_sha256=sha(engine.read_bytes()),
                  harness_sha256=sha(Path(__file__).read_bytes()), feed_sha256=sha(signed), passed=[])
    hits = Counter()
    class Handler(BaseHTTPRequestHandler):
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
        def log_message(self, *unused):
            pass
    server = thread = None
    dest = None
    try:
        result['busy_port_control'] = busy_port_control()
        server = ExclusiveHTTPServer(('127.0.0.1', mirror.port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        paths = ['ftesurf/gfx/updater_fixture.txt', 'ftesurf/gfx/crosshairs/xhair1.png']
        old = b'old managed live content\n'
        for kind in ['initial-failure', 'deferred-rewrite']:
            hits.clear()
            dest = root / kind
            dest.mkdir()
            for path, data in payload.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            guards = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// own settings\n',
                      'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n'}
            for path, data in guards.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            meta = dest / '.ftesurf-updater'
            meta.mkdir()
            (meta / 'consent').write_text('1\n')
            ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
            for path in paths:
                (dest / path).write_bytes(old)
                ledger['files'][path] = digest(old)
            (meta / 'state.json').write_text(json.dumps(ledger))
            rows = dict(paths=paths, old=old, payload=payload, ledger=ledger, signed=signed,
                        url=f'http://127.0.0.1:{mirror.port}/update.json')
            live(engine, dest, evidence / kind / 'live', kind, a.expect_before, rows)
            assert hits['/update.json'] == (2 if kind == 'initial-failure' else 1)
            assert {k for k in hits if '/objects/' in k} == {
                '/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash'] for p in paths}
            result[kind + '_http'] = dict(hits)
            if kind == 'deferred-rewrite':
                # Export committed live authority before cold completion removes it.
                shutil.copyfile(meta / 'ingame/journal.json', evidence / kind / 'live-journal.json')
                run_native(engine, dest, evidence / kind / 'cold-completion')
                assert (dest / paths[1]).read_bytes() == payload[paths[1]]
                assert not (meta / 'ingame/journal.json').exists()
                assert (meta / 'installed.json').read_bytes() == signed
            assert json.loads((meta / 'state.json').read_text())['version'] == manifest['version']
            for path, data in guards.items():
                assert (dest / path).read_bytes() == data, path
            snapshot(dest, evidence / kind / 'final')
            result['passed'].append(kind)
            print('PASS', kind, flush=True)
            ensure_retirable()
            shutil.rmtree(dest)
            dest = None
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        try:
            if server:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
                assert not thread.is_alive()
            result['http_thread_stopped'] = thread is None or not thread.is_alive()
        except BaseException as error:
            result.update(status='FAIL', server_cleanup_error=repr(error))
            raise
        finally:
            retire_runtime(root, evidence, result, dest)


if __name__ == '__main__':
    main()
