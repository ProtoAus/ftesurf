#!/usr/bin/env python3
"""Source-bound Windows initial full live journal failure/process interruption.

Immutable external PE/companion + retained signed loopback closure; no signing,
product edit, power-loss, default-HTTPS, release or deployment acceptance.
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
import subprocess
import threading
import time
from urllib.parse import urlsplit

import updatefeed
from test_update_handoff import owned_job
from test_update_native_journal import (UNCONFIRMED_PHASES, PENDING_ERROR,
    ensure_retirable, publication_snapshot, run_native, sha, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import helper_identity, pe_text
from test_update_native_journal_interrupt import preflight_paths, snapshot
from test_update_native_journal_live import retire_runtime
from test_update_native_recovery import digest
from test_update_native_windows_unreadable import ExclusiveHTTPServer, busy_port_control, kernel32

READY = 'JOURNAL_INITIAL_READY'
INITIAL_ERROR = 'cannot commit the recovery journal; nothing installed'
OLD_ERROR = 'cannot save the complete recovery journal; nothing installed'


def bind_code(base, text_rva, code, listing, disassembly, before):
    def symbol(name, kinds='tT'):
        values = re.findall(r'^([0-9a-f]+) [' + kinds + '] ' + re.escape(name) + '$', listing, re.M)
        assert len(values) == 1, 'unique symbol required: ' + name
        return int(values[0], 16)
    def section(name):
        matches = re.findall(r'^[0-9a-f]+ <' + re.escape(name) + r'>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)', disassembly, re.M | re.S)
        assert len(matches) == 1, 'unique function required: ' + name
        return matches[0]
    def calls(body, target):
        return re.findall(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})\s+call\s+[^\n]*<' + re.escape(target) + r'>$', body, re.M)
    def bytes_at(address, size):
        off = address - base - text_rva
        assert 0 <= off and off + size <= len(code)
        return code[off:off + size]
    def direct(body, target):
        sites = calls(body, target)
        assert len(sites) == 1, 'unique direct call required: ' + target
        addr, encoded = sites[0]
        address, raw = int(addr, 16), bytes.fromhex(encoded)
        assert len(raw) == 5 and raw[0] == 0xe8 and bytes_at(address, 5) == raw
        assert address + 5 + int.from_bytes(raw[1:], 'little', signed=True) == symbol(target), 'actual direct target mismatch'
        return address
    writer = 'QKU_WriteJournal.constprop.0'
    entry = symbol(writer)
    apply = section('QKU_Apply')
    symbol('QKU_Apply')
    sites = calls(apply, writer)
    assert len(sites) == 2 and len(calls(disassembly, writer)) == 2, 'exact two live call sites required'
    callers = []
    for addr, encoded in sites:
        address, raw = int(addr, 16), bytes.fromhex(encoded)
        assert len(raw) == 5 and raw[0] == 0xe8 and bytes_at(address, 5) == raw
        assert address + 5 + int.from_bytes(raw[1:], 'little', signed=True) == entry
        callers.append(address + 5 - base)
    assert callers == sorted(callers)
    if before:
        body = section(writer)
        assert bytes_at(entry, 11) == bytes.fromhex('55 57 56 53 48 81 ec 48 08 00 00'), 'old writer frame required'
        pre = direct(body, 'FS_Rename')
        removes = calls(body, 'FS_Remove')
        assert len(removes) == 1 and 0 < pre - int(removes[0][0], 16) < 32, 'preceding old unlink required'
        raw = bytes_at(pre, 5)
        abi, commit_caller = 'fs', 0
        assert bytes_at(pre+5, 1) == b'\x90', 'old native return instruction required'
    else:
        part = 'QKU_CommitJournal.part.0'
        start = symbol(part)
        assert bytes_at(start, 8) == bytes.fromhex('57 b8 30 18 00 00 56 53')
        assert bytes_at(start+8, 1) == b'\xe8' and bytes_at(start+13, 3) == bytes.fromhex('48 29 c4'), 'exact commit frame allocation required'
        assert start+13+int.from_bytes(bytes_at(start+9, 4), 'little', signed=True) == symbol('___chkstk_ms'), 'actual stack probe target required'
        assert re.search(r'add\s+\$0x28,%rsp\n\s*[0-9a-f]+:.*jmp\s+' + f'{start:x}' + r' <QKU_CommitJournal.part.0>', section('QKU_CommitJournal')), 'commit tail wrapper required'
        write_part = 'QKU_WriteJournal.part.0.constprop.0'
        write_start = symbol(write_part)
        assert bytes_at(entry, 4) == bytes.fromhex('48 83 ec 28')
        assert re.search(r'add\s+\$0x28,%rsp\n\s*[0-9a-f]+:.*jmp\s+' + f'{write_start:x}' + r' <' + re.escape(write_part) + '>', section(writer)), 'writer tail wrapper required'
        commit_caller = direct(section(write_part), 'QKU_CommitJournal') + 5 - base
        native = calls(section(part), '__imp_MoveFileExW')
        assert len(native) == 1, 'unique real replace import required'
        address, encoded = native[0]
        pre, raw = int(address, 16), bytes.fromhex(encoded)
        assert len(raw) == 6 and raw[:2] == b'\xff\x15' and bytes_at(pre, 6) == raw
        assert pre+6+int.from_bytes(raw[2:], 'little', signed=True) == symbol('__imp_MoveFileExW', 'iI'), 'actual native import target required'
        assert bytes_at(pre+6, 1) == b'\x85', 'native return instruction required'
        abi = 'wide'
    return dict(entry_rva=entry-base, pre_rva=pre-base, post_rva=pre+len(raw)-base,
                entry_byte=bytes_at(entry, 1)[0], pre_byte=raw[0], post_byte=bytes_at(pre+len(raw), 1)[0],
                initial_caller_rva=callers[0], deferred_caller_rva=callers[1], commit_caller_rva=commit_caller, abi=abi)


def bind_initial(engine, symbols, nm, objdump):
    base, text_rva, code = pe_text(engine)
    assert pe_text(symbols) == (base, text_rva, code), 'companion text differs'
    listing = subprocess.check_output([str(nm), '-n', str(symbols)], text=True)
    disassembly = subprocess.check_output([str(objdump), '-d', str(symbols)], text=True)
    # The old writer is void; its actual FS_Rename return is still observed.
    before = 'QKU_CommitJournal.part.0' not in listing
    return bind_code(base, text_rva, code, listing, disassembly, before) | dict(
        engine_sha256=sha(engine.read_bytes()), symbols_sha256=sha(symbols.read_bytes()), text_sha256=sha(code), before=before)


def grade_events(events, binding, mode):
    assert mode in ('none', 'source-lock', 'crash-before', 'crash-after')
    names = ['child', 'writer', 'before']
    if mode == 'source-lock':
        names += ['source-lock']
    if mode != 'crash-before':
        names += ['after']
    if mode.startswith('crash-'):
        names += ['interrupt']
    names += ['exit']
    assert [e['event'] for e in events] == names, 'exact native event order required'
    child, writer, pre, last = events[0], events[1], events[2], events[-1]
    assert child['pid'] > 0 and child['pid'] == last['pid']
    assert writer['ordinal'] == 1 and writer['rva'] == binding['entry_rva'] and writer['caller_rva'] == binding['initial_caller_rva']
    assert pre['rva'] == binding['pre_rva'] and pre['paths_verified'] is True and pre['authority_absent'] is True
    boundaries = [e for e in events if e['event'] in ('writer', 'before', 'after')]
    assert writer['thread'] > 0 and len({e['thread'] for e in boundaries}) == 1
    if mode == 'source-lock':
        assert events[3] == dict(event='source-lock', rename_error=32, write_allowed=True)
    if mode != 'crash-before':
        post = next(e for e in events if e['event'] == 'after')
        assert post['rva'] == binding['post_rva'] and ((post['native_result'] == 0) == (mode == 'source-lock'))
    hits = 2 if mode == 'crash-before' else 3
    assert last['hits'] == hits and last['code'] == (86 if mode.startswith('crash-') else 0)
    if mode.startswith('crash-'):
        assert events[-2] == dict(event='interrupt', code=86, hits=hits)
    return child['pid'], last['code']


def live(engine, helper, binding, dest, phase, mode, rows, inspect):
    phase.mkdir(parents=True)
    UNCONFIRMED_PHASES.add(phase)
    cfg = dest / 'ftesurf/cfg/test/initial-journal.cfg'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
                   'update_autocheck 0\nupdate_allow_insecure 1\n'
                   f'update_manifest_url "{rows["url"]}"\n'
                   'developer 1\nlog_developer 1\nlog_name journal-initial\nlog_enable 1\n'
                   f'echo {READY}\n')
    args = [str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'vid_renderer', 'headless', '+exec', 'cfg/test/initial-journal.cfg']
    env = dict(os.environ, OWNED_JOURNAL_ENGINE=str(engine), OWNED_JOURNAL_COMMAND=subprocess.list2cmdline(args))
    keys = ('entry_rva', 'pre_rva', 'post_rva', 'entry_byte', 'pre_byte', 'post_byte', 'initial_caller_rva', 'commit_caller_rva')
    invocation = [str(helper)] + [f'{binding[k]:x}' for k in keys] + [binding['abi'],
        str(dest / '.ftesurf-updater/ingame'), str(phase / 'debug.jsonl'), str(phase / 'initial-temp.json'), mode]
    receipt = dict(status='FAIL', mode=mode)
    process = job = None
    contained = exported = False
    def logs():
        return '\n'.join(p.read_text(errors='replace') for p in dest.rglob('journal-initial*.log'))
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
            send('update_info; echo JOURNAL_INITIAL_AVAILABLE')
            assert 'update state : available' in wait('JOURNAL_INITIAL_AVAILABLE')
            send('echo JOURNAL_INITIAL_APPLY; update_apply')
            if mode in ('none', 'source-lock'):
                if mode == 'source-lock':
                    text = wait(OLD_ERROR if binding['before'] else INITIAL_ERROR)
                    assert 'update: installed' not in text
                    send('update_info; echo JOURNAL_INITIAL_REFUSED')
                    assert 'update state : error' in wait('JOURNAL_INITIAL_REFUSED')
                    publication_snapshot(dest, phase / 'failed-publication')
                    inspect('failed-publication')
                    send('update_check force')
                    until = time.monotonic() + 30
                    while logs().count('update: 2 file') < 2:
                        assert process.poll() is None and time.monotonic() < until, 'fresh retry plan missing'
                        time.sleep(0.05)
                    send('update_info; echo JOURNAL_INITIAL_RETRY_AVAILABLE')
                    assert 'update state : available' in wait('JOURNAL_INITIAL_RETRY_AVAILABLE').split('JOURNAL_INITIAL_REFUSED', 1)[1]
                    send('echo JOURNAL_INITIAL_RETRY_APPLY; update_apply')
                wait('update: installed 2 files')
                send('update_info; echo JOURNAL_INITIAL_DONE; quit')
                text = wait('JOURNAL_INITIAL_DONE')
                assert 'update state : restart' in text
            process.wait(timeout=30)
            assert process.returncode == 0, 'native debugger failed'
            events = [json.loads(line) for line in (phase / 'debug.jsonl').read_text().splitlines()]
            receipt['child_pid'], receipt['child_exit'] = grade_events(events, binding, mode)
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            contained = True
            text = logs()
            assert text.count('JOURNAL_INITIAL_APPLY') == 1
            if mode.startswith('crash-'):
                assert 'update: installed' not in text and 'JOURNAL_INITIAL_DONE' not in text
            snapshot(dest, phase / 'state')
            receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
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
            snapshot(dest, phase / 'state')
            exported = True
        except BaseException as error:
            receipt.update(status='FAIL', cleanup_error=repr(error))
            raise
        finally:
            try:
                if job:
                    assert kernel32().CloseHandle(job), ctypes.get_last_error()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                if process and process.stdin:
                    process.stdin.close()
            except BaseException as error:
                receipt.update(status='FAIL', handle_cleanup_error=repr(error))
                raise
            finally:
                if process:
                    receipt.update(helper_pid=process.pid, helper_exit=process.poll())
                receipt.update(full_export=exported, containment_confirmed=contained)
                (phase / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
            if contained and exported:
                UNCONFIRMED_PHASES.discard(phase)


def full_snapshot(dest, target):
    """Never let optional/final export failure fall through to partial retirement."""
    guard = target / 'caller-full-snapshot-guard'
    assert guard not in UNCONFIRMED_PHASES, 'previous caller export to this target is unconfirmed'
    UNCONFIRMED_PHASES.add(guard)
    snapshot(dest, target)
    UNCONFIRMED_PHASES.discard(guard)


def cold_phase(engine, dest, phase, error=None):
    """Full state export is independent of the imported runner's log/job guard."""
    guard = phase / 'full-export-guard'
    UNCONFIRMED_PHASES.add(guard)
    receipt = dict(status='FAIL', full_export=False)
    try:
        run_native(engine, dest, phase, error=error)
        receipt['status'] = 'PASS'
    except BaseException as failure:
        receipt['error'] = repr(failure)
        raise
    finally:
        try:
            # Grading failure can follow a real content mutation. Always snapshot.
            snapshot(dest, phase / 'state')
            receipt['full_export'] = True
            assert phase not in UNCONFIRMED_PHASES, 'cold runner containment/export unconfirmed'
        except BaseException as failure:
            receipt.update(status='FAIL', full_export_error=repr(failure))
            raise
        finally:
            receipt['runner_confirmed'] = phase not in UNCONFIRMED_PHASES
            releasable = receipt['full_export'] and receipt['runner_confirmed']
            receipt['guard_retained'] = not releasable
            phase.mkdir(parents=True, exist_ok=True)
            (phase / 'full-export.json').write_text(json.dumps(receipt, indent=2) + '\n')
            if releasable:
                UNCONFIRMED_PHASES.discard(guard)


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
    (root / 'OWNER.md').write_text('Owned synthetic initial journal fixtures; retire after export and observed job0.\n')
    result = dict(status='FAIL', binding=binding, helper_sha256=helper_hash,
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
        for scenario in ('none', 'source-lock', 'crash-before', 'crash-after-repaired', 'crash-after-corrupt'):
            hits.clear()
            dest = root / scenario
            dest.mkdir()
            zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
            guards = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned settings\n',
                      'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n',
                      'ftesurf/gfx/unmanaged-sentinel.txt': b'owned unmanaged asset\n',
                      zone: b'// owned protected local zone edit\n'}
            for path, data in (payload | guards).items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            meta = dest / '.ftesurf-updater'
            meta.mkdir()
            (meta / 'consent').write_text('1\n')
            old = b'old managed initial journal content\n'
            ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
            for path in paths:
                (dest / path).write_bytes(old)
                ledger['files'][path] = digest(old)
            ledger_bytes = json.dumps(ledger).encode()
            (meta / 'state.json').write_bytes(ledger_bytes)
            authority, temp = meta / 'ingame/journal.json', meta / 'ingame/journal.tmp'
            stage = meta / 'ingame/staged'
            phase = evidence / scenario
            rows = dict(url=f'http://127.0.0.1:{mirror.port}/update.json')
            expected_rows = [dict(p=p, h=files[p]['hash'], s=files[p]['size'], x=int(files[p]['exec'])) for p in files if p in paths]
            def unchanged():
                assert (meta / 'state.json').read_bytes() == ledger_bytes
                assert not (meta / 'installed.json').exists()
                assert (meta / 'ingame/manifest.json').read_bytes() == signed
                for p in paths:
                    assert (dest / p).read_bytes() == old
                    assert (stage / files[p]['hash']).read_bytes() == payload[p]
            def inspect(unused):
                unchanged()
                assert not authority.exists()
                assert temp.read_bytes() == (phase / 'live/initial-temp.json').read_bytes()
            mode = 'crash-after' if scenario.startswith('crash-after') else scenario
            live(engine, helper, binding, dest, phase / 'live', mode, rows, inspect)
            full_bytes = (phase / 'live/initial-temp.json').read_bytes()
            full = json.loads(full_bytes)
            assert full == dict(version=manifest['version'], attempts=1, files=expected_rows), 'complete initial native writer did not ACT'
            expected_http = {'/update.json': 2 if mode == 'source-lock' else 1} | {
                '/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash']: 2 if mode == 'source-lock' else 1 for p in paths}
            assert dict(hits) == expected_http, dict(hits)
            result[scenario + '_http'] = dict(hits)
            if mode.startswith('crash-'):
                unchanged()
                if mode == 'crash-before':
                    assert not authority.exists() and temp.read_bytes() == full_bytes
                    cold_phase(engine, dest, phase / 'cold-no-authority')
                    unchanged()
                    assert not authority.exists() and temp.read_bytes() == full_bytes
                else:
                    assert authority.read_bytes() == full_bytes and not temp.exists()
                    if scenario.endswith('corrupt'):
                        bad = stage / files[paths[1]]['hash']
                        bad.write_bytes(b'owned corrupt pending object\n')
                        cold_phase(engine, dest, phase / 'cold-corrupt', error=PENDING_ERROR)
                        pending = json.loads(authority.read_text())
                        assert pending == dict(version=manifest['version'], attempts=2, files=[r for r in expected_rows if r['p'] == paths[1]])
                        assert (dest / paths[0]).read_bytes() == payload[paths[0]] and (dest / paths[1]).read_bytes() == old
                        partial = json.loads((meta / 'state.json').read_text())
                        assert partial['version'] == ledger['version'] and partial['files'][paths[0]] == files[paths[0]]['hash']
                        assert partial['files'][paths[1]] == digest(old) and not (meta / 'installed.json').exists()
                        assert partial == dict(version=ledger['version'], files=ledger['files'] | {paths[0]: files[paths[0]]['hash']})
                        bad.write_bytes(payload[paths[1]])
                    cold_phase(engine, dest, phase / 'cold-completion')
            if mode != 'crash-before':
                final = json.loads((meta / 'state.json').read_text())
                assert final == dict(version=manifest['version'], files={p: f['hash'] for p, f in files.items()})
                assert not authority.exists() and not temp.exists()
                assert (meta / 'installed.json').read_bytes() == signed
                for p in paths:
                    assert (dest / p).read_bytes() == payload[p] and final['files'][p] == files[p]['hash']
                    assert not (stage / files[p]['hash']).exists(), 'resolved selected object was not retired'
            for p, data in guards.items():
                assert (dest / p).read_bytes() == data, p
            full_snapshot(dest, phase / 'final')
            result['passed'].append(scenario)
            print('PASS initial-live', scenario, 'old' if binding['before'] else 'subject', flush=True)
            ensure_retirable()
            shutil.rmtree(dest)
            dest = None
        assert sha(engine.read_bytes()) == binding['engine_sha256'], 'native disk client changed'
        assert sha(helper.read_bytes()) == helper_hash, 'native disk helper changed'
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
