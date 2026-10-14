#!/usr/bin/env python3
"""Native Windows shared-open byte-lock falsifier for recovery readability.

Historical runners/graders stay immutable. Export only after job0 and lock release.
"""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import stat

from test_update_handoff import owned_job
from test_ingame_update import owned_error
from test_update_native_journal import (ACTOR, UNCONFIRMED_PHASES, _checked_files,
    preflight_paths, sha, snapshot, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import pe_text
import test_update_native_staging_windows as staging
import test_update_native_retirement_windows as retirement

READ_ERROR = 'Unreadable signed recovery content; nothing installed.'
EDIT = b'{"owned_readlock_edit":true}\n' + b' ' * (6 * 1024 * 1024)


def inventory(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in _checked_files(root)}


def directories(root):
    found = set()
    def walk(parent):
        with os.scandir(parent) as entries:
            for entry in entries:
                path = parent / entry.name
                if stat.S_ISDIR(path.lstat().st_mode):
                    found.add(path.relative_to(root).as_posix())
                    walk(path)
    walk(root)
    return found


class Overlapped(ctypes.Structure):
    _fields_ = [('internal', ctypes.c_size_t), ('internal_high', ctypes.c_size_t),
                ('offset', w.DWORD), ('offset_high', w.DWORD), ('event', w.HANDLE)]


class ReadLock:
    """Exclusive first-byte lock, but shared READ/WRITE opens (not share denial)."""
    def __init__(self, path):
        self.path, self.handle = path, None
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
        self.k.CreateFileW.restype = w.HANDLE
        self.k.LockFileEx.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, w.DWORD, ctypes.POINTER(Overlapped)]
        self.k.UnlockFileEx.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.POINTER(Overlapped)]
        self.k.ReadFile.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]
        self.k.CloseHandle.argtypes = [w.HANDLE]
        self.overlapped = Overlapped()

    def open(self, access):
        handle = self.k.CreateFileW(str(self.path), access, 3, None, 3, 0x80, None)
        assert handle not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
        return handle

    def acquire(self):
        self.handle = self.open(0xc0000000)
        assert self.k.LockFileEx(self.handle, 3, 0, 1, 0, ctypes.byref(self.overlapped)), ctypes.get_last_error()

    def probe(self, locked):
        handle = self.open(0x80000000)
        try:
            buf, count = ctypes.create_string_buffer(1), w.DWORD()
            ctypes.set_last_error(0)
            ok = self.k.ReadFile(handle, buf, 1, ctypes.byref(count), None)
            error = ctypes.get_last_error()
            if locked:
                assert not ok and error == 33 and count.value == 0, (ok, error, count.value)
            else:
                assert ok and count.value == 1 and buf.raw == EDIT[:1], (ok, error, count.value)
            return dict(open_succeeded=True, share_read_write=True, read_ok=bool(ok), error=error, bytes=count.value)
        finally:
            assert self.k.CloseHandle(handle), ctypes.get_last_error()

    def release(self):
        if self.handle is not None:
            assert self.k.UnlockFileEx(self.handle, 0, 1, 0, ctypes.byref(self.overlapped)), ctypes.get_last_error()
            assert self.k.CloseHandle(self.handle), ctypes.get_last_error()
            self.handle = None


def prepare(root, signed, manifest, files, payload):
    f = retirement.prepare(root, 'complete-attempt3', 'unique', False,
                           signed, manifest, files, payload, attempts=3, completed=True)
    (f['meta'] / 'install.lock').write_bytes(b'')
    (f['dest'] / f['zone']).write_bytes(EDIT)
    f['sentinels'][f['zone']] = EDIT
    f['seed'] = inventory(f['dest'])
    f['seed_directories'] = directories(f['dest'])
    return f


def grade(f, retired, engine_logs=()):
    """Exact complete file namespace; only captured named engine logs may be added."""
    actual = inventory(f['dest'])
    removed = {'.ftesurf-updater/ingame/staged/' + f['files'][f[k]]['hash']
               for k in ('resolved', 'pending', 'zone')}
    removed.add('.ftesurf-updater/ingame/journal.json')
    expected = {p: b for p, b in f['seed'].items() if not (retired and p in removed)}
    expected_directories = f['seed_directories'] | ({'ftesurf/logs'} if engine_logs else set())
    assert directories(f['dest']) == expected_directories, 'directory namespace differs'
    ledger_path = '.ftesurf-updater/state.json'
    if retired:
        assert json.loads(actual[ledger_path]) == f['ledger'], 'completion ledger differs'
        actual[ledger_path] = f['seed'][ledger_path]
    for path in engine_logs:
        assert path not in expected and path in actual
        assert path in ('ftesurf/logs/journal-locked.log', 'ftesurf/logs/journal-released.log'), path
        del actual[path]
    assert actual == expected, 'complete namespace differs: ' + repr({
        'missing': sorted(expected.keys() - actual.keys()),
        'extra': sorted(actual.keys() - expected.keys()),
        'changed': sorted(p for p in actual.keys() & expected.keys() if actual[p] != expected[p])})
    assert f['ledger']['files'][f['zone']] != f['files'][f['zone']]['hash']
    assert len(EDIT) > 5 * 1024 * 1024 and actual[f['zone']] == EDIT
    return dict(retired=retired, zone_sha256=sha(actual[f['zone']]), signed_rows=len(f['payload']),
                removed=sorted(removed) if retired else [], seed_file_count=len(f['seed']),
                engine_logs=sorted(engine_logs))


def finalize_phase(dest, phase, receipt, release, checker):
    """Called after containment; failed/unknown steps must never clear the guard."""
    release()
    snapshot(dest, phase / 'state')
    receipt['full_export'] = True
    receipt['grade'] = checker()
    assert receipt.get('job_active_before_cleanup') == 0
    assert receipt.get('job_active_after_cleanup') == 0
    assert receipt.get('natural_exit') is True
    receipt['status'] = 'PASS'


def run_phase(engine, f, phase, error, lock, retired):
    phase.mkdir()
    assert phase not in UNCONFIRMED_PHASES
    UNCONFIRMED_PHASES.add(phase)
    receipt = dict(status='FAIL', natural_exit=False, full_export=False)
    args = [str(engine), '-nohome', '-basedir', str(f['dest']), '-manifest', str(f['dest'] / 'default.fmf'),
        '+set', 'cfg_save_auto', '0', '+set', 'con_savehistory', '0',
        '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
        '+set', 'update_autocheck', '0', '+set', 'log_enable', '1',
        '+set', 'log_name', 'journal-' + phase.name, '+echo', ACTOR, '+quit']
    receipt['command'] = args
    process = job = None
    try:
        if lock:
            lock.acquire()
            receipt['locked_probe'] = lock.probe(True)
        with (phase / 'output.log').open('wb') as out:
            process = subprocess.Popen(args, cwd=f['dest'], stdin=subprocess.DEVNULL,
                stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            receipt['pid'] = process.pid
            job = owned_job(process)
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes = [w.HANDLE]
            resume.restype = ctypes.c_long
            assert resume(int(process._handle)) == 0
            if error:
                receipt['fatal'] = owned_error(process, error)
            process.wait(timeout=30)
            receipt['exit'] = process.returncode
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            receipt['natural_exit'] = True
        # No termination on this path: independently census after cleanup.
        wait_win_job_empty(job, receipt, 'job_active_after_cleanup')
        if lock:
            receipt['locked_probe_after_job0'] = lock.probe(True)
        def release():
            if lock:
                lock.release()
                receipt['released_probe'] = lock.probe(False)
        def checker():
            texts = [receipt.get('fatal', '')]
            logs = set(f.get('engine_logs', ()))
            for p in (f['dest'] / 'ftesurf').rglob('journal-' + phase.name + '*.log'):
                data = p.read_bytes()
                relative = p.relative_to(f['dest']).as_posix()
                assert relative == 'ftesurf/logs/journal-' + phase.name + '.log', relative
                logs.add(relative)
                (phase / ('game-' + p.name)).write_bytes(data)
                texts.append(data.decode('utf-8', errors='replace'))
            texts.append((phase / 'output.log').read_text(encoding='utf-8', errors='replace'))
            text = '\n'.join(texts)
            if error:
                assert process.returncode != 0 and error in text and ACTOR not in text
            else:
                assert process.returncode == 0 and ACTOR in text, (process.returncode, text)
            if retired and lock:
                try:
                    grade(f, False, logs)
                except AssertionError as refusal:
                    receipt['refusal_oracle_rejected'] = str(refusal)
                else:
                    raise AssertionError('blocked build did not discriminate refusal')
            result = grade(f, retired, logs)
            f['engine_logs'] = logs
            return result
        finalize_phase(f['dest'], phase, receipt, release, checker)
    except BaseException as failure:
        receipt.update(status='FAIL', error=repr(failure))
        # A failure remains failed even if forced containment/export succeeds.
        try:
            if job and not receipt['natural_exit']:
                stop_win_job(job, process, receipt)
            elif process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            if lock:
                lock.release()
            snapshot(f['dest'], phase / 'failed-state')
        except BaseException as cleanup_error:
            receipt['cleanup_error'] = repr(cleanup_error)
        raise
    finally:
        try:
            if job:
                k = ctypes.WinDLL('kernel32', use_last_error=True)
                k.CloseHandle.argtypes = [w.HANDLE]
                assert k.CloseHandle(job), ctypes.get_last_error()
        except BaseException as failure:
            receipt.update(status='FAIL', handle_error=repr(failure))
            raise
        finally:
            receipt['guard_retained'] = receipt['status'] != 'PASS'
            (phase / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
            if receipt['status'] == 'PASS':
                UNCONFIRMED_PHASES.discard(phase)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'feed', 'runtime-root', 'evidence', 'build-receipt'):
        ap.add_argument('--' + name, required=True, type=Path)
    ap.add_argument('--objects', required=True, action='append', type=Path)
    ap.add_argument('--expect-defective', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt', 'native Windows required'
    engine, symbols = a.engine.resolve(strict=True), a.symbols.resolve(strict=True)
    build = json.loads(a.build_receipt.read_text())
    assert build['status'] == 'PASS', 'build receipt not PASS'
    expected_source = ('87326b33b7133550f05c83469ba97e1dc0023163c88d74300e221b2e2a1a29b3' if a.expect_defective else
                       '7321da290913f67c047f1cf86103203ad79327d05dbacb44fe7ca9da695ec5d3')
    assert build['qkupdate_sha256'] == expected_source
    assert build['source_unchanged'] is True and build['exit'] == 0
    assert engine == Path(build['engine']).resolve(strict=True)
    assert symbols == Path(build['symbols']).resolve(strict=True)
    assert sha(engine.read_bytes()) == build['engine_sha256']
    assert sha(symbols.read_bytes()) == build['symbols_sha256']
    assert pe_text(engine) == pe_text(symbols), 'PE companion text mismatch'
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    signed, manifest, files, payload = staging.load_inputs(a.feed, a.objects)
    assert sha(signed) == '35942d7284e7f57625d9cfacfd644eae75c2b296dfc9df775f80a04c110320f3'
    assert len(payload) == 821, 'complete signed win64 closure required'
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned readgate byte-lock fixtures; retain full runtime/evidence; no deployment.\n')
    sources = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    result = dict(status='FAIL', command=subprocess.list2cmdline(__import__('sys').argv), engine=str(engine),
        engine_sha256=sha(engine.read_bytes()), symbols=str(symbols), symbols_sha256=sha(symbols.read_bytes()),
        source_sha256=expected_source, build_receipt=build, build_receipt_sha256=sha(a.build_receipt.read_bytes()),
        feed=str(a.feed), feed_sha256=sha(signed), objects=[str(p) for p in a.objects],
        helper_sha256=sources, expect_defective=a.expect_defective, runtime_retained=True)
    try:
        f = prepare(root, signed, manifest, files, payload)
        snapshot(f['dest'], evidence / 'seed')
        with staging.offline_mirror(manifest) as hits:
            run_phase(engine, f, evidence / 'locked', None if a.expect_defective else READ_ERROR,
                      ReadLock(f['dest'] / f['zone']), a.expect_defective)
            run_phase(engine, f, evidence / 'released', None, None, True)
        staging.final_http(hits, result)
        assert not UNCONFIRMED_PHASES
        assert sha(engine.read_bytes()) == result['engine_sha256']
        assert sha(symbols.read_bytes()) == result['symbols_sha256']
        assert all(sha(Path(__file__).with_name(p).read_bytes()) == h for p, h in sources.items())
        result['status'] = 'PASS'
    except BaseException as failure:
        result['error'] = repr(failure)
        raise
    finally:
        result['unconfirmed_guards'] = sorted(str(p) for p in UNCONFIRMED_PHASES)
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
