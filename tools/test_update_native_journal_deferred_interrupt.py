#!/usr/bin/env python3
"""Windows deferred live journal process interruption, NOT power loss.

External immutable PE/companion, source-bound debugger and retained signed
loopback closure. Separate fresh fixtures exercise retry and exhaustion budgets.
"""
import argparse
from collections import Counter
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
from test_update_native_journal import (PENDING_ERROR, UNCONFIRMED_PHASES,
    ensure_retirable, preflight_paths, sha, snapshot, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import DEFERRED, helper_identity
from test_update_native_journal_initial import bind_initial, cold_phase, full_snapshot
from test_update_native_journal_interrupt import EXHAUSTED
from test_update_native_journal_live import destination_lock, retire_runtime
from test_update_native_recovery import digest
from test_update_native_windows_unreadable import ExclusiveHTTPServer, busy_port_control, kernel32

READY = 'JOURNAL_DEFERRED_INTERRUPT_READY'
SCENARIOS = ('none', 'crash-before', 'crash-after-repaired',
             'crash-after-corrupt-repaired', 'crash-after-exhausted')


def grade_http(hits, expected):
    assert dict(hits) == expected, 'unexpected HTTP request during live/offline recovery: ' + repr(dict(hits))
    return dict(hits)


def grade_events(events, binding, mode):
    assert mode in ('none', 'crash-before', 'crash-after')
    names = ['child', 'writer', 'writer', 'before']
    if mode != 'crash-before':
        names.append('after')
    if mode != 'none':
        names.append('interrupt')
    names.append('exit')
    assert [e['event'] for e in events] == names, 'exact deferred native event order required'
    child, first, second, pre, last = events[0], events[1], events[2], events[3], events[-1]
    assert child['pid'] > 0 and child['pid'] == last['pid']
    assert [first['ordinal'], second['ordinal']] == [1, 2]
    assert [first['caller_rva'], second['caller_rva']] == [binding['initial_caller_rva'], binding['deferred_caller_rva']]
    assert first['rva'] == second['rva'] == binding['entry_rva']
    boundaries = [e for e in events if e['event'] in ('writer', 'before', 'after')]
    assert first['thread'] > 0 and len({e['thread'] for e in boundaries}) == 1
    assert pre['rva'] == binding['pre_rva'] and pre['paths_verified'] is True
    assert pre['authority_absent'] is binding['before'], 'wrong prior-authority boundary'
    if mode != 'crash-before':
        post = events[4]
        assert post['rva'] == binding['post_rva'] and post['native_result'] > 0
    hits = 2 if mode == 'crash-before' else 3
    code = 0 if mode == 'none' else 86
    assert last['hits'] == hits and last['calls'] == 2 and last['code'] == code
    if mode != 'none':
        assert events[-2] == dict(event='interrupt', code=86, hits=hits)
    return child['pid'], code


def live(engine, helper, binding, dest, phase, mode, rows):
    phase.mkdir(parents=True)
    UNCONFIRMED_PHASES.add(phase)
    cfg = dest / 'ftesurf/cfg/test/deferred-interrupt.cfg'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
                   'update_autocheck 0\nupdate_allow_insecure 1\n'
                   f'update_manifest_url "{rows["url"]}"\n'
                   'developer 1\nlog_developer 1\nlog_name journal-deferred-interrupt\nlog_enable 1\n'
                   f'echo {READY}\n')
    args = [str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'vid_renderer', 'headless', '+exec', 'cfg/test/deferred-interrupt.cfg']
    env = dict(os.environ, OWNED_JOURNAL_ENGINE=str(engine), OWNED_JOURNAL_COMMAND=subprocess.list2cmdline(args))
    keys = ('entry_rva', 'pre_rva', 'post_rva', 'entry_byte', 'pre_byte', 'post_byte', 'initial_caller_rva', 'commit_caller_rva')
    invocation = [str(helper)] + [f'{binding[k]:x}' for k in keys] + [binding['abi'],
        str(dest / '.ftesurf-updater/ingame'), str(phase / 'debug.jsonl'), str(phase / 'pending-temp.json'), mode,
        f'{binding["deferred_caller_rva"]:x}', str(phase / 'initial-authority.json')]
    receipt = dict(status='FAIL', mode=mode)
    process = job = None
    contained = exported = handles_ok = False
    def logs():
        return '\n'.join(p.read_text(errors='replace') for p in dest.rglob('journal-deferred-interrupt*.log'))
    def wait(actor):
        until = time.monotonic() + 30
        while time.monotonic() < until:
            text = logs()
            if actor in text:
                return text
            assert process.poll() is None, 'client exited before: ' + actor
            time.sleep(0.05)
        raise AssertionError('missing native actor: ' + actor)
    def send(command):
        assert len(command.encode()) < 255
        process.stdin.write((command + '\n').encode())
        process.stdin.flush()
    try:
        with (phase / 'stdout.log').open('wb') as out:
            process = subprocess.Popen(invocation, cwd='C:/FTESurf', env=env, stdin=subprocess.PIPE,
                stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            job = owned_job(process)
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes, resume.restype = [w.HANDLE], ctypes.c_long
            assert resume(int(process._handle)) == 0
            wait(READY)
            send('update_check force')
            wait('update: 2 file')
            send('update_info; echo JOURNAL_DEFERRED_INTERRUPT_AVAILABLE')
            assert 'update state : available' in wait('JOURNAL_DEFERRED_INTERRUPT_AVAILABLE')
            with destination_lock(dest / rows['pending']):
                send('echo JOURNAL_DEFERRED_INTERRUPT_APPLY; update_apply')
                if mode == 'none':
                    wait(DEFERRED)
                    send('update_info; echo JOURNAL_DEFERRED_INTERRUPT_DONE; quit')
                    assert 'update state : restart' in wait('JOURNAL_DEFERRED_INTERRUPT_DONE')
                process.wait(timeout=30)
            assert process.returncode == 0, 'native debugger failed'
            events = [json.loads(line) for line in (phase / 'debug.jsonl').read_text().splitlines()]
            receipt['child_pid'], receipt['child_exit'] = grade_events(events, binding, mode)
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            contained = True
            text = logs()
            assert text.count('JOURNAL_DEFERRED_INTERRUPT_APPLY') == 1
            assert f'update: {rows["pending"]} is locked, will finish on next launch' in text
            if mode != 'none':
                assert DEFERRED not in text and 'JOURNAL_DEFERRED_INTERRUPT_DONE' not in text
            receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        try:
            if job:
                natural = contained
                contained = False
                if natural:
                    wait_win_job_empty(job, receipt, 'job_active_after_cleanup')
                else:
                    stop_win_job(job, process, receipt)
                contained = True
            elif process:
                # Job setup failed while helper was still suspended: no child could start.
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
                contained = True
        except BaseException as error:
            receipt.update(status='FAIL', containment_error=repr(error))
            raise
        finally:
            try:
                snapshot(dest, phase / 'state')
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
                    handles_ok = True
                except BaseException as error:
                    receipt.update(status='FAIL', handle_cleanup_error=repr(error))
                    raise
                finally:
                    receipt.update(helper_pid=process.pid if process else None,
                        helper_exit=process.poll() if process else None, full_export=exported,
                        containment_confirmed=contained, handles_confirmed=handles_ok)
                    (phase / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
                if contained and exported and handles_ok:
                    UNCONFIRMED_PHASES.discard(phase)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'helper', 'feed', 'runtime-root', 'evidence'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    ap.add_argument('--nm', type=Path, default=Path('C:/msys64/ucrt64/bin/nm.exe'))
    ap.add_argument('--objdump', type=Path, default=Path('C:/msys64/ucrt64/bin/objdump.exe'))
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    helper, helper_hash = helper_identity(a.helper)
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    binding = bind_initial(engine, symbols, a.nm, a.objdump)
    assert binding['before'] == a.expect_before, 'source arm does not match requested old/subject'
    signed = a.feed.read_bytes()
    manifest = updatefeed.verify(signed)
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
    selected = ['ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/updater_fixture.txt']
    paths = [p for p in files if p in selected]
    assert len(paths) == 2
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
    (root / 'OWNER.md').write_text('Owned synthetic deferred interruption fixtures; observed jobs/full export before retirement.\n')
    sources = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('test_update_native*.py')}
    result = dict(status='FAIL', binding=binding, helper_sha256=helper_hash, source_sha256=sources,
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
    server = thread = dest = None
    try:
        result['busy_port_control'] = busy_port_control()
        server = ExclusiveHTTPServer(('127.0.0.1', mirror.port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        for position in ('pending-first', 'pending-last'):
            pending = paths[0 if position == 'pending-first' else 1]
            content = next(p for p in paths if p != pending)
            expected = [dict(p=p, h=files[p]['hash'], s=files[p]['size'], x=int(files[p]['exec'])) for p in paths]
            reduced = [r for r in expected if r['p'] == pending]
            for scenario in SCENARIOS:
                name = position + '-' + scenario
                hits.clear()
                dest = root / name
                dest.mkdir()
                zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
                guards = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned settings\n',
                          'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n',
                          'ftesurf/gfx/unmanaged-sentinel.txt': b'owned unmanaged asset\n',
                          zone: b'// owned protected local zone edit\n'}
                for p, data in (payload | guards).items():
                    target = dest / p
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                meta = dest / '.ftesurf-updater'
                meta.mkdir()
                (meta / 'consent').write_text('1\n')
                old = b'old managed deferred interruption content\n'
                ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
                for p in paths:
                    (dest / p).write_bytes(old)
                    ledger['files'][p] = digest(old)
                (meta / 'state.json').write_text(json.dumps(ledger))
                stage = meta / 'ingame/staged'
                authority, temp = meta / 'ingame/journal.json', meta / 'ingame/journal.tmp'
                phase = evidence / name
                def check_partial():
                    assert (dest / content).read_bytes() == payload[content], 'ordinary installation never ACTED'
                    assert (dest / pending).read_bytes() == old
                    state = json.loads((meta / 'state.json').read_text())
                    assert state == dict(version=ledger['version'], files=ledger['files'] | {content: files[content]['hash']})
                    assert not (meta / 'installed.json').exists()
                    assert (meta / 'ingame/manifest.json').read_bytes() == signed
                    for p, data in guards.items():
                        assert (dest / p).read_bytes() == data, p
                mode = 'crash-after' if scenario.startswith('crash-after') else scenario
                live(engine, helper, binding, dest, phase / 'live', mode,
                     dict(url=f'http://127.0.0.1:{mirror.port}/update.json', pending=pending))
                initial = (phase / 'live/initial-authority.json').read_bytes()
                assert json.loads(initial) == dict(version=manifest['version'], attempts=1, files=expected)
                native_temp = (phase / 'live/pending-temp.json').read_bytes()
                assert json.loads(native_temp) == dict(version=manifest['version'], attempts=1, files=reduced)
                expected_http = {'/update.json': 1} | {
                    '/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash']: 1 for p in paths}
                result[name + '_http'] = grade_http(hits, expected_http)
                check_partial()
                for p in paths:
                    assert (stage / files[p]['hash']).read_bytes() == payload[p]
                committed = mode != 'crash-before'
                if committed:
                    assert authority.read_bytes() == native_temp and not temp.exists()
                else:
                    assert temp.read_bytes() == native_temp
                    if binding['before']:
                        assert not authority.exists(), 'old authority-loss detector did not ACT'
                    else:
                        assert authority.read_bytes() == initial, 'full prior authority lost'
                bad = stage / files[pending]['hash']
                if mode == 'crash-before' or 'corrupt' in scenario or scenario.endswith('exhausted'):
                    bad.write_bytes(b'owned corrupt pending object\n')
                    old_gap = binding['before'] and mode == 'crash-before'
                    cold_phase(engine, dest, phase / 'cold-corrupt', error=None if old_gap else PENDING_ERROR)
                    check_partial()
                    if old_gap:
                        assert not authority.exists() and temp.read_bytes() == native_temp
                        full_snapshot(dest, phase / 'detected-mixed-startup')
                        authority.write_bytes(initial)  # explicit control-only restoration AFTER detection/export
                        (phase / 'control-only-restored-authority.json').write_bytes(initial)
                    else:
                        assert json.loads(authority.read_text()) == dict(version=manifest['version'], attempts=2, files=reduced)
                    if scenario.endswith('exhausted'):
                        cold_phase(engine, dest, phase / 'cold-corrupt-attempt3', error=PENDING_ERROR)
                        check_partial()
                        assert json.loads(authority.read_text()) == dict(version=manifest['version'], attempts=3, files=reduced)
                    bad.write_bytes(payload[pending])
                if scenario.endswith('exhausted'):
                    saved = authority.read_bytes()
                    saved_stages = {p.name: p.read_bytes() for p in stage.iterdir()}
                    cold_phase(engine, dest, phase / 'cold-exhausted-repaired', error=EXHAUSTED)
                    check_partial()
                    assert authority.read_bytes() == saved
                    assert {p.name: p.read_bytes() for p in stage.iterdir()} == saved_stages
                else:
                    cold_phase(engine, dest, phase / 'cold-completion')
                    assert json.loads((meta / 'state.json').read_text()) == dict(
                        version=manifest['version'], files={p: f['hash'] for p, f in files.items()})
                    assert (meta / 'installed.json').read_bytes() == signed and not authority.exists()
                    for p in paths:
                        assert (dest / p).read_bytes() == payload[p]
                    assert not bad.exists(), 'pending selected staged input not retired'
                    if committed:
                        # Reduced authority cannot name the already resolved live input.
                        assert (stage / files[content]['hash']).read_bytes() == payload[content], 'known orphan limit changed'
                    if binding['before'] and mode == 'crash-before':
                        assert temp.read_bytes() == native_temp, 'legacy failed temp orphan changed'
                    else:
                        assert not temp.exists()
                for p, data in guards.items():
                    assert (dest / p).read_bytes() == data, p
                result[name + '_http_after_cold'] = grade_http(hits, expected_http)
                full_snapshot(dest, phase / 'final')
                result['passed'].append(name)
                print('PASS deferred-interruption', name, 'old' if binding['before'] else 'subject', flush=True)
                ensure_retirable()
                shutil.rmtree(dest)
                dest = None
        assert sha(engine.read_bytes()) == binding['engine_sha256'], 'native disk client changed'
        assert sha(helper.read_bytes()) == helper_hash, 'native disk helper changed'
        assert {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('test_update_native*.py')} == sources, 'sources changed during matrix'
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
