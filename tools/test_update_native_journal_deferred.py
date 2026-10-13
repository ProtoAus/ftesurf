#!/usr/bin/env python3
"""Source-bound Windows second live journal write: real sharing failure and retry.

External immutable client + matching .exe.db only. The debugger temporarily
patches one owned child's function-entry byte, not disk or native API results.
It locks only journal.tmp at invocation two; native OPEN/write/close/rename runs.
This is loopback signed-fixture acceptance, NOT default HTTPS or crash durability.
"""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes as w
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import threading
import time
from urllib.parse import urlsplit

import updatefeed
from test_update_handoff import owned_job
from test_update_native_journal import (PENDING_ERROR, UNCONFIRMED_PHASES, ensure_retirable,
    preflight_paths, run_native, sha, snapshot, stop_win_job)
from test_update_native_journal_live import destination_lock, retire_runtime
from test_update_native_recovery import digest
from test_update_native_windows_unreadable import ExclusiveHTTPServer, busy_port_control, kernel32

REWRITE_ERROR = 'cannot rewrite the recovery journal; restart to recover before playing'
DEFERRED = 'update: installed 1 of 2 files; restart to finish'


def pe_text(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    machine, count = struct.unpack_from('<HH', data, pe + 4)
    assert machine == 0x8664, 'x64 PE required'
    optional = pe + 24
    assert struct.unpack_from('<H', data, optional)[0] == 0x20b
    base = struct.unpack_from('<Q', data, optional + 24)[0]
    size = struct.unpack_from('<H', data, pe + 20)[0]
    for i in range(count):
        section = optional + size + 40 * i
        if data[section:section + 8].rstrip(b'\0') == b'.text':
            virtual_size, rva, raw_size, raw = struct.unpack_from('<IIII', data, section + 8)
            assert virtual_size <= raw_size and raw + raw_size <= len(data)
            return base, rva, data[raw:raw + virtual_size]
    raise AssertionError('missing executable text')


def bind_writer(engine, symbols, nm, objdump):
    base, text_rva, code = pe_text(engine)
    assert pe_text(symbols) == (base, text_rva, code), 'symbol companion text differs from native client'
    listing = subprocess.check_output([str(nm), '-n', str(symbols)], text=True)
    addresses = re.findall(r'^([0-9a-f]+) t QKU_WriteJournal\.constprop\.0$', listing, re.M)
    assert len(addresses) == 1, 'unique optimized writer symbol required'
    address = int(addresses[0], 16)
    offset = address - base - text_rva
    assert 0 <= offset < len(code) and code[offset] != 0xcc
    disassembly = subprocess.check_output([str(objdump), '-d', str(symbols)], text=True)
    calls = re.findall(r'^\s*([0-9a-f]+):\s+e8 (?:[0-9a-f]{2} ){3}[0-9a-f]{2}\s+call\s+' +
                       f'{address:x}' + r' <QKU_WriteJournal\.constprop\.0>$', disassembly, re.M)
    assert len(calls) == 2, 'exact initial/deferred direct call sites required'
    return dict(rva=address - base, prologue_byte=code[offset], caller_rvas=[int(c, 16) + 5 - base for c in calls],
                engine_sha256=sha(engine.read_bytes()), symbols_sha256=sha(symbols.read_bytes()), text_sha256=sha(code))


def helper_identity(path):
    assert path.is_file() and not path.is_symlink(), 'regular unlinked debugger helper file required'
    helper = path.resolve(strict=True)
    assert helper.suffix.lower() == '.exe', 'Windows debugger helper executable required'
    return helper, sha(helper.read_bytes())


def job_count(job):
    class Accounting(ctypes.Structure):
        _fields_ = [('times', ctypes.c_int64 * 4), ('faults', w.DWORD),
                    ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]
    k = kernel32()
    k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]
    a = Accounting()
    assert k.QueryInformationJobObject(job, 1, ctypes.byref(a), ctypes.sizeof(a), None), ctypes.get_last_error()
    return a.active


def wait_job_empty(job, receipt, key):
    # EXIT_PROCESS debug delivery precedes final kernel/job exit accounting.
    # Observe natural quiescence; never make a success arm pass by killing it.
    until = time.monotonic() + 10
    counts = []
    while True:
        count = job_count(job)
        counts.append(count)
        if count == 0 or time.monotonic() >= until:
            receipt[key] = count
            receipt[key + '_observations'] = counts
            assert count == 0, 'owned job did not quiesce'
            return
        time.sleep(0.01)


def live(engine, helper, binding, dest, evidence, mode, before, rows):
    evidence.mkdir(parents=True)
    phase = str(evidence)
    UNCONFIRMED_PHASES.add(phase)
    cfg = dest / 'ftesurf/cfg/test/deferred-journal.cfg'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
                   'update_autocheck 0\nupdate_allow_insecure 1\n'
                   f'update_manifest_url "{rows["url"]}"\n'
                   'developer 1\nlog_developer 1\nlog_name journal-deferred\nlog_enable 1\n'
                   'echo JOURNAL_DEFERRED_READY\n')
    meta = dest / '.ftesurf-updater'
    args = [str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'vid_renderer', 'headless', '+exec', 'cfg/test/deferred-journal.cfg']
    env = dict(os.environ, OWNED_JOURNAL_ENGINE=str(engine), OWNED_JOURNAL_COMMAND=subprocess.list2cmdline(args))
    invocation = [str(helper), f'{binding["rva"]:x}', f'{binding["prologue_byte"]:x}', str(meta / 'ingame'),
                  str(evidence / 'debug.jsonl'), str(evidence / 'initial-authority.json'), mode]
    receipt = dict(status='FAIL', mode=mode)
    process = job = None
    contained = exported = False
    def logs():
        return '\n'.join(p.read_text(errors='replace') for p in dest.rglob('journal-deferred*.log'))
    def wait(actor):
        until = time.monotonic() + 30
        while time.monotonic() < until:
            text = logs()
            if actor in text:
                return text
            assert process.poll() is None, 'debug client exited before: ' + actor
            time.sleep(0.05)
        raise AssertionError('missing native actor: ' + actor)
    def send(command):
        assert len(command.encode()) < 255
        process.stdin.write((command + '\n').encode())
        process.stdin.flush()
    try:
        with (evidence / 'stdout.log').open('wb') as out:
            process = subprocess.Popen(invocation, cwd='C:/FTESurf', env=env, stdin=subprocess.PIPE,
                stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            job = owned_job(process)  # helper suspended; child inherits the job before native startup
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes, resume.restype = [w.HANDLE], ctypes.c_long
            assert resume(int(process._handle)) == 0
            wait('JOURNAL_DEFERRED_READY')
            send('update_check force')
            wait('update: 2 file')
            send('update_info; echo JOURNAL_DEFERRED_AVAILABLE')
            assert 'update state : available' in wait('JOURNAL_DEFERRED_AVAILABLE')
            with destination_lock(dest / rows['paths'][1]):
                send('echo JOURNAL_DEFERRED_APPLY; update_apply')
                wait(REWRITE_ERROR if mode == 'source-lock' and not before else DEFERRED)
                send('update_info; echo JOURNAL_DEFERRED_RESULT')
                text = wait('JOURNAL_DEFERRED_RESULT')
                if mode == 'source-lock' and not before:
                    assert DEFERRED not in text and 'update state : error' in text
                else:
                    assert REWRITE_ERROR not in text and 'update state : restart' in text
                assert text.count('JOURNAL_DEFERRED_APPLY') == 1
                send('echo JOURNAL_DEFERRED_DONE; quit')
                process.wait(timeout=30)
            receipt['helper_exit'] = process.returncode
            assert process.returncode == 0 and 'JOURNAL_DEFERRED_DONE' in logs()
            events = [json.loads(line) for line in (evidence / 'debug.jsonl').read_text().splitlines()]
            writers = [e for e in events if e['event'] == 'writer']
            assert [e['ordinal'] for e in writers] == [1, 2]
            assert [e['caller_rva'] for e in writers] == binding['caller_rvas'], 'not inspected live initial/deferred call sites'
            assert all(e['rva'] == binding['rva'] for e in writers)
            assert len({e['thread'] for e in writers}) == 1
            child = [e for e in events if e['event'] == 'child']
            exits = [e for e in events if e['event'] == 'exit']
            assert len(child) == len(exits) == 1 and child[0]['pid'] == exits[0]['pid']
            assert exits[0]['code'] == 0 and exits[0]['calls'] == 2
            faults = [e for e in events if e['event'] == 'source-lock']
            assert faults == ([dict(event='source-lock', ordinal=2, rename_error=32, write_allowed=True)] if mode == 'source-lock' else [])
            receipt.update(child_pid=child[0]['pid'], child_exit=exits[0]['code'])
            wait_job_empty(job, receipt, 'job_active_before_cleanup')
            contained = True
            receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        # Kill only this job on failure; verify its census while handle is still valid.
        try:
            if job:
                natural = contained
                contained = False
                if not natural:
                    stop_win_job(job, process, receipt)
                else:
                    wait_job_empty(job, receipt, 'job_active_after_cleanup')
                contained = True
            elif process and process.poll() is None:
                process.terminate()  # job setup failed while helper was suspended
                process.wait(timeout=10)
                contained = True
        except BaseException as error:
            receipt.update(status='FAIL', containment_error=repr(error))
            raise
        finally:
            try:
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
                    receipt.update(helper_pid=process.pid if process else None,
                        helper_exit=process.poll() if process else None,
                        full_export=exported, containment_confirmed=contained)
                    (evidence / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
                if contained and exported:
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
    helper, helper_sha256 = helper_identity(a.helper)
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    binding = bind_writer(engine, symbols, a.nm, a.objdump)
    signed = a.feed.read_bytes()
    manifest = updatefeed.verify(signed)
    mirror = urlsplit(manifest['mirrors'][0])
    assert mirror.scheme == 'http' and mirror.hostname == '127.0.0.1' and mirror.port and not mirror.path
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
    paths = ['ftesurf/gfx/updater_fixture.txt', 'ftesurf/gfx/crosshairs/xhair1.png']
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
    result = dict(status='FAIL', expect_before=a.expect_before, binding=binding, helper_sha256=helper_sha256,
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
        (root / 'OWNER.md').write_text('Owned synthetic Windows deferred journal fixture; parent kill-on-close jobs only.\n')
        result['busy_port_control'] = busy_port_control()
        server = ExclusiveHTTPServer(('127.0.0.1', mirror.port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        for mode in ('none', 'source-lock'):
            hits.clear()
            dest = root / mode
            dest.mkdir()
            for path, data in payload.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            guards = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned settings\n',
                      'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n',
                      'ftesurf/gfx/unmanaged-sentinel.txt': b'owned unmanaged asset\n'}
            zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
            guards[zone] = b'// owned protected local zone edit\n'
            for path, data in guards.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            meta = dest / '.ftesurf-updater'
            meta.mkdir()
            (meta / 'consent').write_text('1\n')
            old = b'old managed live content\n'
            ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
            for path in paths:
                (dest / path).write_bytes(old)
                ledger['files'][path] = digest(old)
            (meta / 'state.json').write_text(json.dumps(ledger))
            rows = dict(paths=paths, url=f'http://127.0.0.1:{mirror.port}/update.json')
            phase = evidence / mode
            live(engine, helper, binding, dest, phase / 'live', mode, a.expect_before, rows)
            assert hits['/update.json'] == 1
            assert {k for k in hits if '/objects/' in k} == {
                '/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash'] for p in paths}
            result[mode + '_http'] = dict(hits)
            initial = (phase / 'live/initial-authority.json').read_bytes()
            full = json.loads(initial)
            assert full['attempts'] == 1 and full['version'] == manifest['version']
            expected_rows = [dict(p=p, h=files[p]['hash'], s=files[p]['size'], x=int(files[p]['exec']))
                             for p in files if p in paths]  # native signed-manifest order
            pending_rows = [r for r in expected_rows if r['p'] == paths[1]]
            assert full['files'] == expected_rows
            assert (dest / paths[0]).read_bytes() == payload[paths[0]] and (dest / paths[1]).read_bytes() == old
            partial = json.loads((meta / 'state.json').read_text())
            assert partial['version'] == ledger['version'] and partial['files'][paths[0]] == files[paths[0]]['hash']
            assert partial['files'][paths[1]] == digest(old) and not (meta / 'installed.json').exists()
            assert (meta / 'ingame/manifest.json').read_bytes() == signed
            authority = meta / 'ingame/journal.json'
            if mode == 'none':
                reduced = json.loads(authority.read_text())
                assert reduced['attempts'] == 1 and reduced['files'] == pending_rows
                run_native(engine, dest, phase / 'cold-completion')
            else:
                pending = json.loads((meta / 'ingame/journal.tmp').read_text())
                assert pending['attempts'] == 1 and pending['files'] == pending_rows, 'native second writer did not ACT'
                assert authority.exists() != a.expect_before
                if not a.expect_before:
                    assert authority.read_bytes() == initial, 'deferred fault lost/changed full authority'
                stage = meta / 'ingame/staged'
                for p in paths:
                    assert (stage / files[p]['hash']).read_bytes() == payload[p], 'fault retired staged input'
                bad = stage / files[paths[1]]['hash']
                bad.write_bytes(b'owned corrupt pending object\n')
                run_native(engine, dest, phase / 'cold-corrupt', error=None if a.expect_before else PENDING_ERROR)
                assert (dest / paths[1]).read_bytes() == old
                if a.expect_before:
                    assert not authority.exists(), 'missing-authority control was silently repaired'
                    authority.write_bytes(initial)  # explicit subsequent control-only repair
                else:
                    next_journal = json.loads(authority.read_text())
                    assert next_journal['attempts'] == 2 and next_journal['files'] == pending_rows
                snapshot(dest, phase / 'after-corrupt')
                bad.write_bytes(payload[paths[1]])
                run_native(engine, dest, phase / 'cold-repaired')
            assert not authority.exists() and (meta / 'installed.json').read_bytes() == signed
            if mode == 'source-lock' and a.expect_before:
                # Legacy direct repair does not rewrite: its failed sibling is an
                # observed orphan, not silently credited as native cleanup.
                assert json.loads((meta / 'ingame/journal.tmp').read_text()) == pending
            else:
                assert not (meta / 'ingame/journal.tmp').exists()
            final = json.loads((meta / 'state.json').read_text())
            assert final['version'] == manifest['version']
            for p in paths:
                assert (dest / p).read_bytes() == payload[p] and final['files'][p] == files[p]['hash']
            for p, data in guards.items():
                assert (dest / p).read_bytes() == data, p
            snapshot(dest, phase / 'final')
            result['passed'].append(mode)
            print('PASS deferred-live', mode, 'before' if a.expect_before else 'subject', flush=True)
            ensure_retirable()
            shutil.rmtree(dest)
            dest = None
        assert sha(engine.read_bytes()) == binding['engine_sha256'], 'native client disk bytes changed'
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
