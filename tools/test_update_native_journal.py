#!/usr/bin/env python3
"""Native journal replacement failure/process-interruption falsifiers.

Reuse an existing signed object closure, never a signing key or player install.
Windows forces real source-rename sharing failure. Linux uses the companion
native_journal_fault.c interposer before/after the exact journal rename. These
are namespace/process-crash checks, NOT power-loss or hostile path-race proof.
"""
import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import updatefeed
from test_update_native_recovery import digest

ACTOR = 'NATIVE_JOURNAL_STARTUP_ACTED'
REWRITE_ERROR = 'Cannot rewrite the update recovery journal'
PENDING_ERROR = 'Unfinished content update'
UNCONFIRMED_PHASES = set()


def ensure_retirable():
    assert not UNCONFIRMED_PHASES, 'client containment or evidence export unconfirmed: ' + str(UNCONFIRMED_PHASES)


def win_job_active(job):
    from ctypes import wintypes as w
    class Accounting(ctypes.Structure):
        _fields_ = [('times', ctypes.c_int64 * 4), ('faults', w.DWORD),
                    ('total', w.DWORD), ('active', w.DWORD), ('terminated', w.DWORD)]
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]
    accounting = Accounting()
    assert k.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None)
    return accounting.active


def wait_win_job_empty(job, receipt, key, timeout=10):
    # Debugger EXIT_PROCESS and leader wait can precede final job accounting.
    until = time.monotonic() + timeout
    counts = []
    while True:
        count = win_job_active(job)
        counts.append(count)
        if count == 0 or time.monotonic() >= until:
            receipt[key] = count
            receipt[key + '_observations'] = counts
            assert count == 0, 'owned job did not quiesce'
            return
        time.sleep(0.01)


def stop_win_job(job, process, receipt):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    assert k.TerminateJobObject(job, 91), ctypes.get_last_error()
    if process and process.poll() is None:
        process.wait(timeout=10)
    wait_win_job_empty(job, receipt, 'job_active_after_cleanup')


def group_active(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def stop_posix_group(process, timeout=10):
    """Contain the recorded owned group even after its leader has been reaped."""
    import signal
    if group_active(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # independently confirmed disappearance, not a generic OS-error swallow
    if process.poll() is None:
        process.wait(timeout=timeout)
    until = time.monotonic() + timeout
    while group_active(process.pid):
        if time.monotonic() >= until:
            raise AssertionError('owned group remains after termination: ' + str(process.pid))
        time.sleep(0.01)


def export_game_logs(dest, phase):
    for p in dest.rglob('journal-' + phase.name + '*.log'):
        shutil.copyfile(p, phase / ('game-' + p.name))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run_native(engine, dest, phase, error=None, fault=None, library=None):
    """Persist raw exit/census before grading; contain only the owned client."""
    phase.mkdir(parents=True)
    UNCONFIRMED_PHASES.add(phase)
    protected = {p: (dest / p).read_bytes() for p in
                 ['ftesurf/ftesurf.cfg', 'ftesurf/data/runs/player-sentinel.rec']}
    args = [str(engine), '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'con_savehistory', '0',
            '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
            '+set', 'update_autocheck', '0', '+set', 'log_enable', '1',
            '+set', 'log_name', 'journal-' + phase.name, '+echo', ACTOR, '+quit']
    env = os.environ.copy()
    if fault:
        assert os.name == 'posix' and library
        env.update(LD_PRELOAD=str(library), NATIVE_JOURNAL_FAULT=fault,
                   NATIVE_JOURNAL_FAULT_LOG=str(phase / 'fault.log'))
    process = job = master = None
    receipt = {'expected_error': error, 'fault': fault, 'status': 'FAIL'}
    try:
        with (phase / 'output.log').open('wb') as out:
            if os.name == 'nt':
                from test_update_handoff import owned_job
                from test_ingame_update import owned_error
                process = subprocess.Popen(args, cwd=dest, env=env, stdin=subprocess.DEVNULL,
                                           stdout=out, stderr=subprocess.STDOUT, creationflags=4)
                job = owned_job(process)
                resume = ctypes.WinDLL('ntdll').NtResumeProcess
                resume.argtypes = [ctypes.c_void_p]
                resume.restype = ctypes.c_long
                assert resume(int(process._handle)) == 0
                if error:
                    (phase / 'fatal.log').write_text(owned_error(process, error), encoding='utf-8')
                process.wait(timeout=30)
                wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            else:
                import errno
                import pty
                import signal
                master, slave = pty.openpty()
                try:
                    process = subprocess.Popen(args, cwd=dest, env=env, stdin=subprocess.DEVNULL,
                                               stdout=out, stderr=slave, start_new_session=True)
                finally:
                    os.close(slave)
                process.wait(timeout=30)
                os.set_blocking(master, False)
                while True:
                    try:
                        block = os.read(master, 65536)
                    except BlockingIOError:
                        break
                    except OSError as ex:
                        if ex.errno != errno.EIO:
                            raise
                        break
                    if not block:
                        break
                    out.write(block)
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    receipt['group_active_before_cleanup'] = False
                else:
                    receipt['group_active_before_cleanup'] = True
                    raise AssertionError('owned process group remains')
        receipt.update(pid=process.pid, exit=process.returncode)
        # Export this phase's gamedir log only: earlier startup actors cannot pass it.
        export_game_logs(dest, phase)
        text = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in phase.glob('*.log'))
        if fault:
            faulttext = (phase / 'fault.log').read_text()
            assert f'journal-rename pid={process.pid} mode={fault}\n' in faulttext, 'fault never ACTED'
        if fault and fault.startswith('crash-'):
            assert process.returncode == 86 and ACTOR not in text, (process.returncode, text)
            if fault == 'crash-after':
                assert 'journal-rename committed\n' in faulttext
        elif error:
            assert process.returncode != 0 and error in text and ACTOR not in text, (process.returncode, text)
        else:
            assert process.returncode == 0 and ACTOR in text, (process.returncode, text)
        for path, data in protected.items():
            assert (dest / path).read_bytes() == data, path
        receipt['status'] = 'PASS'
    finally:
        exported = contained = False
        try:
            # Also export when owned_error, wait, or the pre-cleanup census raised.
            export_game_logs(dest, phase)
            exported = True
        except BaseException as error:
            receipt.update(status='FAIL', export_error=repr(error))
            raise
        finally:
            try:
                if job:
                    k = ctypes.WinDLL('kernel32', use_last_error=True)
                    k.CloseHandle.argtypes = [ctypes.c_void_p]
                    try:
                        if receipt.get('job_active_before_cleanup') != 0:
                            stop_win_job(job, process, receipt)
                        else:
                            wait_win_job_empty(job, receipt, 'job_active_after_cleanup')
                    finally:
                        assert k.CloseHandle(job)
                if process:
                    if os.name == 'posix':
                        stop_posix_group(process)
                        receipt['group_active_after_cleanup'] = False
                    elif process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
                contained = True
            except BaseException as error:
                receipt.update(status='FAIL', containment_error=repr(error))
                raise
            finally:
                if process:
                    receipt.update(pid=process.pid, exit=process.poll())
                if master is not None:
                    os.close(master)
                (phase / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
                if exported and contained:
                    UNCONFIRMED_PHASES.discard(phase)


@contextmanager
def source_lock(path, receipt):
    """Prove writes work but the actual Win32 rename of this source fails."""
    from ctypes import wintypes as w
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
    k.CreateFileW.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.MoveFileExW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.DWORD]
    path.write_bytes(b'owned precreated journal temp\n')
    h = k.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)  # read/write shared, NOT delete
    assert h != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        path.write_bytes(b'write/truncate allowed while source held\n')
        before = path.read_bytes()
        moved = path.with_suffix('.probe')
        assert not moved.exists()
        assert not k.MoveFileExW(str(path), str(moved), 1), 'sharing condition did not block rename'
        receipt['source_rename_error'] = ctypes.get_last_error()
        assert receipt['source_rename_error'] == 32
        assert path.read_bytes() == before and not moved.exists()
        yield
    finally:
        assert k.CloseHandle(h), ctypes.get_last_error()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['engine', 'feed', 'objects', 'runtime-root', 'evidence']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--fault-library', type=Path)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    root, evidence = a.runtime_root.absolute(), a.evidence.absolute()
    engine = a.engine.resolve(strict=True)
    assert not root.exists() and not evidence.exists(), 'fresh owned paths required'
    if os.name == 'posix':
        assert os.geteuid() != 0, 'unprivileged POSIX runtime required'
        assert a.fault_library and a.fault_library.is_file()
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned native journal fixtures, synthetic sentinels only; retire after small evidence export.\n')
    result = dict(status='FAIL', expect_before=a.expect_before, platform=os.name, passed=[],
                  engine_sha256=sha(engine.read_bytes()), harness_sha256=sha(Path(__file__).read_bytes()),
                  runtime_root=str(root))
    dest = None
    safe_to_retire = False
    try:
        signed = a.feed.read_bytes()
        manifest = updatefeed.verify(signed)
        result['feed_sha256'] = sha(signed)
        if a.fault_library:
            result['fault_library_sha256'] = sha(a.fault_library.read_bytes())
        platform = 'win64' if os.name == 'nt' else 'linux64'
        files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', platform)}
        content, later = 'ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png'
        zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
        payload = {}
        for path, entry in files.items():
            obj = a.objects / entry['hash'][:2] / entry['hash']
            assert obj.is_file() and not obj.is_symlink(), path
            data = obj.read_bytes()
            assert len(data) == entry['size'] and digest(data) == entry['hash'], path
            payload[path] = data
        old, edited = b'old managed content\n', b'// intervening zone edit; retain exact bytes\n'

        def prepare(name, rows):
            dest = root / name
            dest.mkdir()
            for path, data in payload.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                if os.name == 'posix' and files[path]['exec']:
                    p.chmod(0o755)
            (dest / 'ftesurf/ftesurf.cfg').write_bytes(b'cfg_save_auto 0\n// owned settings sentinel\n')
            (dest / 'ftesurf/data/runs').mkdir(parents=True, exist_ok=True)
            (dest / 'ftesurf/data/runs/player-sentinel.rec').write_bytes(b'owned recording sentinel\n')
            meta = dest / '.ftesurf-updater'
            (meta / 'ingame/staged').mkdir(parents=True)
            (meta / 'consent').write_text('0\n')
            ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
            for p in rows:
                (dest / p).write_bytes(edited if p == zone else old)
                ledger['files'][p] = digest(old)
                (meta / 'ingame/staged' / files[p]['hash']).write_bytes(payload[p])
            (meta / 'state.json').write_text(json.dumps(ledger))
            (meta / 'ingame/manifest.json').write_bytes(signed)
            (meta / 'ingame/journal.json').write_text(json.dumps(dict(attempts=1, version=manifest['version'], files=[
                dict(p=p, h=files[p]['hash'], s=files[p]['size'], x=int(files[p]['exec'])) for p in rows])))
            (meta / 'ingame/staged' / files[later]['hash']).write_bytes(b'corrupt pending object\n')
            return dest, meta, ledger

        def snapshot(meta, phase):
            phase.mkdir(parents=True, exist_ok=True)
            for p in meta.rglob('*'):
                if p.is_file() and p.suffix in ('.json', '.tmp'):
                    target = phase / 'metadata' / p.relative_to(meta)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(p, target)
            (phase / 'staging.json').write_text(json.dumps({p.name: digest(p.read_bytes()) for p in
                (meta / 'ingame/staged').iterdir() if p.is_file()}, indent=2))

        def passed(name):
            result['passed'].append(name)
            print('PASS', name, flush=True)

        modes = ['none', 'source-lock'] if os.name == 'nt' else ['none', 'fail', 'crash-before', 'crash-after']
        for order in ['content-first', 'protected-first']:
            rows = [content, zone, later] if order == 'content-first' else [zone, content, later]
            for mode in modes:
                name = order + '-' + mode
                dest, meta, ledger = prepare(name, rows)
                journal = meta / 'ingame/journal.json'
                before = journal.read_bytes()
                stage_before = {p.name: p.read_bytes() for p in (meta / 'ingame/staged').iterdir()}
                phase = evidence / name / 'fault'
                expected = PENDING_ERROR if mode == 'none' else REWRITE_ERROR
                if mode == 'source-lock':
                    with source_lock(meta / 'ingame/journal.tmp', result):
                        run_native(engine, dest, phase, error=expected)
                else:
                    run_native(engine, dest, phase, error=expected,
                               fault=None if mode == 'none' else mode, library=a.fault_library)
                snapshot(meta, phase)
                assert (dest / content).read_bytes() == payload[content], 'recovery install never ACTED'
                assert (dest / zone).read_bytes() == edited and (dest / later).read_bytes() == old
                state = json.loads((meta / 'state.json').read_text())
                assert state['version'] == ledger['version'] and state['files'][content] == files[content]['hash']
                assert state['files'][zone] == ledger['files'][zone] and state['files'][later] == ledger['files'][later]
                assert not (meta / 'installed.json').exists()
                committed = mode in ['none', 'crash-after']
                if committed:
                    current = json.loads(journal.read_text())
                    assert current['attempts'] == 2 and [r['p'] for r in current['files']] == [later]
                elif a.expect_before:
                    assert not journal.exists(), 'old missing-authority defect did not ACT'
                else:
                    assert journal.read_bytes() == before, 'original authority lost or changed'
                if mode != 'none':
                    assert {p.name: p.read_bytes() for p in (meta / 'ingame/staged').iterdir()} == stage_before
                passed(name + ': fault/partial publication ACTED')
                if not committed:
                    phase = evidence / name / 'still-corrupt'
                    run_native(engine, dest, phase, error=None if a.expect_before else PENDING_ERROR)
                    snapshot(meta, phase)
                    assert (dest / later).read_bytes() == old and (dest / zone).read_bytes() == edited
                    assert not (meta / 'installed.json').exists()
                    if a.expect_before:
                        assert not journal.exists()
                        passed(name + ': BEFORE mixed installation reaches startup')
                        # Restore saved authority only in the defective control to prove repair capability.
                        journal.write_bytes(before)
                    else:
                        assert json.loads(journal.read_text())['attempts'] == 2
                        passed(name + ': next cold start refuses mixed installation')
                (meta / 'ingame/staged' / files[later]['hash']).write_bytes(payload[later])
                phase = evidence / name / 'repaired'
                run_native(engine, dest, phase)
                snapshot(meta, phase)
                state = json.loads((meta / 'state.json').read_text())
                assert (dest / later).read_bytes() == payload[later] and (dest / zone).read_bytes() == edited
                assert state['version'] == manifest['version'] and state['files'][later] == files[later]['hash']
                assert state['files'][zone] == ledger['files'][zone]
                assert not journal.exists() and (meta / 'installed.json').read_bytes() == signed
                passed(name + ': repaired recovery completes and starts')
                shutil.rmtree(dest)
                dest = None
        result['status'] = 'PASS'
        safe_to_retire = True
    except BaseException as error:
        result['error'] = repr(error)
        if dest is not None:
            snapshot(dest / '.ftesurf-updater', evidence / 'failed-final-state')
        safe_to_retire = True  # only after failed-state evidence exported successfully
        raise
    finally:
        # All clients have been reaped before any fixture retirement.
        try:
            if safe_to_retire:
                ensure_retirable()
                shutil.rmtree(root)
        finally:
            result['runtime_retired'] = not root.exists()
            if not result['runtime_retired']:
                result['status'] = 'FAIL'
            (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
