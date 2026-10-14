#!/usr/bin/env python3
"""Exact deferred source-lock native path/return boundary and full-row oracle."""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import time

from test_update_handoff import owned_job
from test_update_native_journal import (UNCONFIRMED_PHASES,
    ensure_retirable, preflight_paths, sha, snapshot, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import DEFERRED, REWRITE_ERROR, helper_identity
from test_update_native_journal_initial import bind_initial, cold_phase
from test_update_native_journal_live import destination_lock
from test_update_native_windows_unreadable import kernel32

READY = 'JOURNAL_DEFERRED_INTERRUPT_READY'

def grade_events(events, binding, mode, dest):
    assert mode in ('none', 'source-lock')
    names = ['child', 'writer', 'writer', 'before', 'boundary']
    if mode == 'source-lock':
        names.append('source-lock')
    names += ['after', 'exit']
    assert [e['event'] for e in events] == names, 'exact raw boundary event order'
    child, first, second, pre, boundary, post, last = (*events[:5], events[-2], events[-1])
    assert child['pid'] > 0 and child['pid'] == last['pid']
    assert [first['ordinal'], second['ordinal']] == [1, 2]
    assert [first['caller_rva'], second['caller_rva']] == [binding['initial_caller_rva'], binding['deferred_caller_rva']]
    assert first['rva'] == second['rva'] == binding['entry_rva']
    assert first['thread'] > 0 and len({e['thread'] for e in events if e['event'] in ('writer', 'before', 'boundary', 'after')}) == 1
    assert pre == dict(event='before', rva=binding['pre_rva'], thread=first['thread'], paths_verified=True, authority_absent=False)
    meta = dest / '.ftesurf-updater/ingame'
    boundary = dict(boundary)
    for name in ('source', 'destination'):
        assert isinstance(boundary[name], str)
        boundary[name] = boundary[name].replace('\\', '/')
    assert boundary == dict(event='boundary', ordinal=2, thread=first['thread'],
        commit_caller_rva=binding['commit_caller_rva'], flags=1,
        source=(meta / 'journal.tmp').as_posix(), destination=(meta / 'journal.json').as_posix()), 'wrong native paths/flags/caller'
    if mode == 'source-lock':
        assert events[5] == dict(event='source-lock', rename_error=32, write_allowed=True)
    assert post['event'] == 'after' and post['rva'] == binding['post_rva'] and post['ordinal'] == 2
    assert type(post['native_result']) is int and 0 <= post['native_result'] <= 0xffffffff
    assert (post['native_result'] == 0) == (mode == 'source-lock'), 'real native return disagrees with acting control'
    assert last == dict(event='exit', pid=child['pid'], code=0, hits=3, calls=2)
    return child['pid'], 0


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
                if mode in ('none', 'source-lock'):
                    wait(REWRITE_ERROR if mode == 'source-lock' else DEFERRED)
                    send('update_info; echo JOURNAL_DEFERRED_INTERRUPT_DONE; quit')
                    assert ('update state : error' if mode == 'source-lock' else 'update state : restart') in wait('JOURNAL_DEFERRED_INTERRUPT_DONE')
                process.wait(timeout=30)
            assert process.returncode == 0, 'native debugger failed'
            events = [json.loads(line) for line in (phase / 'debug.jsonl').read_text().splitlines()]
            receipt['child_pid'], receipt['child_exit'] = grade_events(events, binding, mode, dest)
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            contained = True
            text = logs()
            assert text.count('JOURNAL_DEFERRED_INTERRUPT_APPLY') == 1
            assert f'update: {rows["pending"]} is locked, will finish on next launch' in text
            if mode == 'source-lock':
                assert DEFERRED not in text and REWRITE_ERROR in text
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


from test_update_native_publication_superset import (BEFORE, SUBJECT, full_authority,
    stage_map, prepare, grade_state, mirror_server)
from test_update_native_staging_windows import load_inputs, journal
from test_update_native_retirement_windows import inventory

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'helper', 'feed', 'runtime-root', 'evidence', 'serializer'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    assert sha(engine.read_bytes()) == (BEFORE if a.expect_before else SUBJECT), 'exact inspected native arm required'
    helper, helper_hash = helper_identity(a.helper)
    binding = bind_initial(engine, symbols, Path('C:/msys64/ucrt64/bin/nm.exe'), Path('C:/msys64/ucrt64/bin/objdump.exe'))
    assert binding['before'] is False, 'both inspected clients have atomic P692 publication'
    signed, manifest, files, payload = load_inputs(a.feed, a.objects)
    paths = [p for p in files if p in ('ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png')]
    assert len(paths) == 2 and files[paths[0]]['hash'] != files[paths[1]]['hash']
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Publication lane owned synthetic runtimes. Retained for independent review; no cleanup of failed attempts.\n')
    source_paths = list(Path(__file__).parent.glob('test_update_native*.py')) + [Path(__file__), a.serializer,
        Path(__file__).with_name('native_journal_deferred_boundary.c'),
        Path(__file__).with_name('updatefeed.py'), Path(__file__).with_name('test_update_handoff.py')]
    hashes = {str(p): sha(p.read_bytes()) for p in source_paths}
    result = dict(status='FAIL', argv=list(__import__('sys').argv), binding=binding, sources=hashes,
                  helper_sha256=helper_hash, signed_sha256=sha(signed), signed_rows=len(files), signed_objects=len({f['hash'] for f in files.values()}), cases=[])
    expected_http = Counter()
    hits = Counter()
    try:
        with mirror_server(manifest, signed, payload, files) as (hits, url):
            for pending in paths:
                content = next(p for p in paths if p != pending)
                position = 'pending-first' if pending == paths[0] else 'pending-last'
                for mode in ('source-lock', 'none'):
                    name = position + '-' + mode
                    dest, meta, expected, ledger = prepare(root, name, payload, files, paths)
                    case = evidence / name
                    case.mkdir()
                    snapshot(dest, case / 'seed')
                    live(engine, helper, binding, dest, case / 'live', mode,
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
                    if mode == 'source-lock':
                        assert authority.read_bytes() == initial, 'failed/uncommitted publication changed authority'
                        assert (meta / 'ingame/journal.tmp').read_bytes() == native_temp
                    else:
                        assert authority.read_bytes() == native_temp and not (meta / 'ingame/journal.tmp').exists()
                    stages = {files[p]['hash']: payload[p] for p in paths}
                    if mode == 'none' and not a.expect_before:
                        del stages[files[content]['hash']]  # actual successful publication permits retirement
                    assert stage_map(dest) == stages, 'premature retirement or incomplete stage inventory'
                    namespace = {'manifest.json': signed, 'journal.json': authority.read_bytes()}
                    if mode == 'source-lock':
                        namespace['journal.tmp'] = native_temp
                    namespace.update({'staged/' + h: data for h, data in stages.items()})
                    assert inventory(meta / 'ingame') == namespace, 'unexpected temp/stage sibling at live boundary'
                    detected = False
                    try:
                        full_authority(json.loads(authority.read_bytes()), files, paths, manifest['version'], 1)
                    except AssertionError:
                        assert a.expect_before and mode == 'none'
                        detected = True
                    assert detected == (a.expect_before and mode == 'none')
                    (case / 'publication-oracle.json').write_text(json.dumps(dict(status='PASS',
                        legacy_full_survivor_oracle_rejected=detected, mode=mode, stages={k: sha(v) for k, v in stages.items()}), indent=2))
                    # Fresh ordinary cold repair acts without rewriting authority in the harness.
                    cold_phase(engine, dest, case / 'repair')
                    expected[pending] = payload[pending]
                    ledger = dict(version=manifest['version'], files={p: f['hash'] for p, f in files.items()})
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'], True)
                    assert not authority.exists()
                    if a.expect_before and mode == 'source-lock':
                        assert (meta / 'ingame/journal.tmp').read_bytes() == native_temp, 'legacy failed sibling must remain exact'
                    else:
                        assert not (meta / 'ingame/journal.tmp').exists()
                    survivors = {files[content]['hash']: payload[content]} if detected else {}
                    assert stage_map(dest) == survivors, 'repair did not ACT exact retirement/orphan control'
                    namespace = {'manifest.json': signed} | {'staged/' + h: data for h, data in survivors.items()}
                    if a.expect_before and mode == 'source-lock':
                        namespace['journal.tmp'] = native_temp
                    assert inventory(meta / 'ingame') == namespace, 'unexpected repaired temp/stage sibling'
                    snapshot(dest, case / 'final')
                    result['cases'].append(name)
                    print('PASS deferred-boundary', name, 'before' if a.expect_before else 'subject', flush=True)
        assert dict(hits) == dict(expected_http), 'joined exact HTTP census'  # census AFTER all accepted handlers join
        result['signed_mirror_http_joined'] = dict(hits)
        assert {str(p): sha(p.read_bytes()) for p in source_paths} == hashes, 'source freeze changed'
        assert sha(engine.read_bytes()) == binding['engine_sha256'] and sha(symbols.read_bytes()) == binding['symbols_sha256']
        assert sha(helper.read_bytes()) == helper_hash
        ensure_retirable()
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        result['raw_http'] = dict(hits)
        result['guards'] = [str(p) for p in UNCONFIRMED_PHASES]
        result['runtime_retired'] = False
        result['retention'] = str(root) + ': source/evidence review fixtures and all failed attempts retained; no blanket cleanup'
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
