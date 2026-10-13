#!/usr/bin/env python3
"""Source-bound Windows cold journal process interruption (NOT power loss).

External immutable clients/companions and a retained signed closure only. Separate
fresh after-commit fixtures test repaired completion and corrupt/exhausted retry.
"""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from types import SimpleNamespace

import updatefeed
from test_ingame_update import owned_error
from test_update_handoff import owned_job
from test_update_native_journal import (ACTOR, PENDING_ERROR, UNCONFIRMED_PHASES,
    ensure_retirable, run_native, sha, stop_win_job, wait_win_job_empty)
from test_update_native_journal_deferred import helper_identity, pe_text, snapshot as journal_snapshot
from test_update_native_journal_live import retire_runtime
from test_update_native_recovery import digest

EXHAUSTED = 'Update cannot finish while files are held open'


def preflight_paths(runtime, evidence):
    runtime, evidence = (p.resolve() for p in (runtime, evidence))
    assert not (runtime.is_relative_to(evidence) or evidence.is_relative_to(runtime)), 'runtime/evidence must be disjoint'
    assert not runtime.exists() and not evidence.exists(), 'fresh owned paths required'
    return runtime, evidence


def snapshot(dest, target):
    journal_snapshot(dest, target)
    identities = {}
    for p in (dest / 'ftesurf').rglob('*'):
        assert not p.is_symlink(), 'linked synthetic fixture'
        if p.is_file():
            identities[p.relative_to(dest).as_posix()] = sha(p.read_bytes())
    (target / 'runtime-files.sha256.json').write_text(json.dumps(identities, indent=2) + '\n')


def bind_commit(engine, symbols, nm, objdump, before):
    base, text_rva, code = pe_text(engine)
    assert pe_text(symbols) == (base, text_rva, code), 'symbol companion text differs'
    listing = subprocess.check_output([str(nm), '-n', str(symbols)], text=True)
    disassembly = subprocess.check_output([str(objdump), '-d', str(symbols)], text=True)
    return bind_code(base, text_rva, code, listing, disassembly, before) | dict(
        engine_sha256=sha(engine.read_bytes()), symbols_sha256=sha(symbols.read_bytes()), text_sha256=sha(code))


def bind_code(base, text_rva, code, listing, disassembly, before):
    def symbol(name):
        values = re.findall(r'^([0-9a-f]+) [tT] ' + re.escape(name) + '$', listing, re.M)
        assert len(values) == 1, 'unique symbol required: ' + name
        return int(values[0], 16)
    def section(name):
        matches = re.findall(r'^[0-9a-f]+ <' + re.escape(name) + r'>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)', disassembly, re.M | re.S)
        assert len(matches) == 1, 'unique disassembled function required: ' + name
        return matches[0]
    def calls(body, target):
        return re.findall(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )*[0-9a-f]{2})\s+call\s+[^\n]*<' + re.escape(target) + r'>$', body, re.M)
    def bytes_at(address, size):
        off = address - base - text_rva
        assert 0 <= off and off + size <= len(code)
        return code[off:off + size]
    replay = section('QKU_ReplayJournal')
    symbol('QKU_ReplayJournal')
    if before:
        sites = calls(replay, 'FS_Rename')
        assert len(sites) == 1, 'unique old cold rename required'
        address, encoded = sites[0]
        pre = int(address, 16)
        assert bytes.fromhex(encoded)[0] == 0xe8 and len(bytes.fromhex(encoded)) == 5
        removes = calls(replay, 'FS_Remove')
        assert any(0 < pre - int(addr, 16) < 32 for addr, unused in removes), 'old preceding unlink required'
        abi, caller = 'fs', 0
    else:
        part = 'QKU_CommitJournal.part.0'
        start = symbol(part)
        assert bytes_at(start, 8) == bytes.fromhex('57 b8 30 18 00 00 56 53'), 'inspected stack frame required'
        assert bytes_at(start+8, 1) == b'\xe8' and bytes_at(start+13, 3) == bytes.fromhex('48 29 c4'), 'exact frame allocation required'
        assert 'sub    %rax,%rsp' in section(part)
        wrapper = section('QKU_CommitJournal')
        assert re.search(r'add\s+\$0x28,%rsp\n\s*[0-9a-f]+:.*jmp\s+' + f'{start:x}' + r' <QKU_CommitJournal.part.0>', wrapper), 'tail wrapper required'
        sites = calls(section(part), '__imp_MoveFileExW')
        assert len(sites) == 1, 'unique real replace call required'
        address, encoded = sites[0]
        pre = int(address, 16)
        assert bytes.fromhex(encoded)[:2] == b'\xff\x15' and len(bytes.fromhex(encoded)) == 6
        cold = calls(replay, 'QKU_CommitJournal')
        assert len(cold) == 1 and len(bytes.fromhex(cold[0][1])) == 5
        caller = int(cold[0][0], 16) + 5 - base
        abi = 'wide'
    call_bytes = bytes.fromhex(encoded)
    assert bytes_at(pre, len(call_bytes)) == call_bytes, 'disassembly/client call mismatch'
    post = pre + len(call_bytes)
    assert bytes_at(post, 1) == (b'\x89' if before else b'\x85'), 'inspected return instruction required'
    assert bytes_at(pre, 1) != b'\xcc'
    return dict(pre_rva=pre-base, post_rva=post-base, pre_byte=call_bytes[0],
                post_byte=bytes_at(post, 1)[0], abi=abi, cold_caller_rva=caller)


def grade_events(events, binding, mode):
    sequence = ['child', 'before'] + ([] if mode == 'crash-before' else ['after']) + ([] if mode == 'none' else ['interrupt']) + ['exit']
    assert [e['event'] for e in events] == sequence, 'exact native event order required'
    children = [e for e in events if e['event'] == 'child']
    exits = [e for e in events if e['event'] == 'exit']
    assert len(children) == len(exits) == 1 and children[0]['pid'] == exits[0]['pid']
    expected = ['before'] if mode == 'crash-before' else ['before', 'after']
    boundaries = [e for e in events if e['event'] in ('before', 'after')]
    assert [e['event'] for e in boundaries] == expected
    assert boundaries[0]['rva'] == binding['pre_rva'] and boundaries[0]['paths_verified'] is True
    assert len({e['thread'] for e in boundaries}) == 1
    if len(boundaries) == 2:
        assert boundaries[1]['rva'] == binding['post_rva'] and boundaries[1]['native_result'] != 0
    interrupts = [e for e in events if e['event'] == 'interrupt']
    assert interrupts == ([] if mode == 'none' else [dict(event='interrupt', code=86, hits=len(expected))])
    assert exits[0]['hits'] == len(expected)
    assert (exits[0]['code'] != 0 if mode == 'none' else exits[0]['code'] == 86)
    return children[0]['pid'], exits[0]['code']


def interrupt(engine, helper, binding, dest, phase, mode):
    phase.mkdir(parents=True)
    UNCONFIRMED_PHASES.add(phase)
    args = [str(engine), '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'con_savehistory', '0',
            '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100', '+set', 'update_autocheck', '0',
            '+set', 'log_enable', '1', '+set', 'log_name', 'journal-' + phase.name, '+echo', ACTOR, '+quit']
    env = dict(os.environ, OWNED_JOURNAL_ENGINE=str(engine), OWNED_JOURNAL_COMMAND=subprocess.list2cmdline(args))
    debug = phase / 'debug.jsonl'
    command = [str(helper), f'{binding["pre_rva"]:x}', f'{binding["post_rva"]:x}',
               f'{binding["pre_byte"]:x}', f'{binding["post_byte"]:x}',
               str(dest / '.ftesurf-updater/ingame'), str(debug), mode, binding['abi'], f'{binding["cold_caller_rva"]:x}']
    receipt = dict(status='FAIL', mode=mode)
    process = job = None
    contained = exported = False
    try:
        with (phase / 'stdout.log').open('wb') as out:
            process = subprocess.Popen(command, cwd='C:/FTESurf', env=env, stdin=subprocess.DEVNULL,
                stdout=out, stderr=subprocess.STDOUT, creationflags=4)
            job = owned_job(process)
            resume = ctypes.WinDLL('ntdll').NtResumeProcess
            resume.argtypes, resume.restype = [w.HANDLE], ctypes.c_long
            assert resume(int(process._handle)) == 0
            if mode == 'none':
                until = time.monotonic() + 10
                while not debug.exists() or not debug.read_text():
                    assert time.monotonic() < until and process.poll() is None, 'missing owned child receipt'
                    time.sleep(0.01)
                first = json.loads(debug.read_text().splitlines()[0])
                assert first['event'] == 'child'
                proxy = SimpleNamespace(pid=first['pid'], poll=process.poll)
                (phase / 'fatal.log').write_text(owned_error(proxy, PENDING_ERROR), encoding='utf-8')
            process.wait(timeout=30)
            receipt['helper_exit'] = process.returncode
            assert process.returncode == 0, 'native debugger failed'
            events = [json.loads(line) for line in debug.read_text().splitlines()]
            receipt['child_pid'], receipt['child_exit'] = grade_events(events, binding, mode)
            wait_win_job_empty(job, receipt, 'job_active_before_cleanup')
            contained = True
            snapshot(dest, phase / 'state')
            text = '\n'.join(p.read_text(errors='replace') for p in phase.rglob('*.log'))
            assert ACTOR not in text, 'interrupted/refused phase reached startup'
            if mode == 'none':
                assert PENDING_ERROR in text
            receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        try:
            if job:
                if not contained:
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
            if process:
                receipt.update(helper_pid=process.pid, helper_exit=process.poll())
            (phase / 'process.json').write_text(json.dumps(receipt, indent=2) + '\n')
            if job:
                k = ctypes.WinDLL('kernel32', use_last_error=True)
                k.CloseHandle.argtypes = [w.HANDLE]
                assert k.CloseHandle(job)
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            if contained and exported:
                UNCONFIRMED_PHASES.discard(phase)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'helper', 'feed', 'objects', 'runtime-root', 'evidence'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--nm', type=Path, default=Path('C:/msys64/ucrt64/bin/nm.exe'))
    ap.add_argument('--objdump', type=Path, default=Path('C:/msys64/ucrt64/bin/objdump.exe'))
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    helper, helper_hash = helper_identity(a.helper)
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    binding = bind_commit(engine, symbols, a.nm, a.objdump, a.expect_before)
    signed = a.feed.read_bytes()
    manifest = updatefeed.verify(signed)
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'win64')}
    payload = {}
    for path, entry in files.items():
        obj = a.objects / entry['hash'][:2] / entry['hash']
        assert obj.is_file() and not obj.is_symlink(), path
        data = obj.read_bytes()
        assert len(data) == entry['size'] and digest(data) == entry['hash'], path
        payload[path] = data
    content, pending = 'ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png'
    zone = next(p for p in files if '/zones/local/' in p and p.endswith('.json'))
    old = b'old managed interruption content\n'
    guards = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\n// owned settings\n',
              'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n',
              'ftesurf/gfx/unmanaged-sentinel.txt': b'owned unmanaged asset\n',
              zone: b'// owned intervening protected zone edit\n'}
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned synthetic cold interruption fixtures; retire after exported evidence and empty jobs.\n')
    result = dict(status='FAIL', expect_before=a.expect_before, binding=binding,
                  helper_sha256=helper_hash, harness_sha256=sha(Path(__file__).read_bytes()),
                  feed_sha256=sha(signed), passed=[])
    dest = None
    def check_partial(meta):
        assert (dest / content).read_bytes() == payload[content], 'earlier content never installed'
        assert (dest / pending).read_bytes() == old
        state = json.loads((meta / 'state.json').read_text())
        assert state['version'] == '0.1.24' and state['files'][content] == files[content]['hash']
        assert state['files'][zone] == digest(old) and state['files'][pending] == digest(old)
        assert not (meta / 'installed.json').exists()
        assert (meta / 'ingame/manifest.json').read_bytes() == signed
        for p, data in guards.items():
            assert (dest / p).read_bytes() == data, p
    try:
        for order in ('content-first', 'protected-first'):
            rows = [content, zone, pending] if order == 'content-first' else [zone, content, pending]
            for scenario in ('none', 'crash-before', 'crash-after-repaired', 'crash-after-corrupt'):
                name = order + '-' + scenario
                dest = root / name
                dest.mkdir()
                for p, data in (payload | guards).items():
                    target = dest / p
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                meta = dest / '.ftesurf-updater'
                stage = meta / 'ingame/staged'
                stage.mkdir(parents=True)
                (meta / 'consent').write_text('0\n')
                ledger = dict(version='0.1.24', files={p: f['hash'] for p, f in files.items()})
                for p in rows:
                    if p != zone:
                        (dest / p).write_bytes(old)
                    ledger['files'][p] = digest(old)
                    (stage / files[p]['hash']).write_bytes(payload[p])
                bad = stage / files[pending]['hash']
                bad.write_bytes(b'owned corrupt pending object\n')
                (meta / 'state.json').write_text(json.dumps(ledger))
                (meta / 'ingame/manifest.json').write_bytes(signed)
                authority = meta / 'ingame/journal.json'
                original = json.dumps(dict(attempts=1, version=manifest['version'], files=[
                    dict(p=p, h=files[p]['hash'], s=files[p]['size'], x=int(files[p]['exec'])) for p in rows])).encode()
                authority.write_bytes(original)
                stages = {p.name: p.read_bytes() for p in stage.iterdir()}
                phase = evidence / name / 'fault'
                mode = 'crash-after' if scenario.startswith('crash-after') else scenario
                interrupt(engine, helper, binding, dest, phase, mode)
                check_partial(meta)
                committed = mode in ('none', 'crash-after')
                if committed:
                    reduced = json.loads(authority.read_text())
                    assert reduced['attempts'] == 2 and reduced['version'] == manifest['version']
                    assert reduced['files'] == [json.loads(original)['files'][-1]]
                    assert not (meta / 'ingame/journal.tmp').exists()
                else:
                    tmp = json.loads((meta / 'ingame/journal.tmp').read_text())
                    assert tmp['attempts'] == 2 and tmp['files'] == [json.loads(original)['files'][-1]]
                    if a.expect_before:
                        assert not authority.exists(), 'old authority-loss detector did not ACT'
                    else:
                        assert authority.read_bytes() == original
                if mode != 'none':
                    assert {p.name: p.read_bytes() for p in stage.iterdir()} == stages, 'interruption retired staged inputs'
                if mode == 'crash-before' or scenario == 'crash-after-corrupt':
                    cold = evidence / name / 'still-corrupt'
                    old_gap = a.expect_before and mode == 'crash-before'
                    run_native(engine, dest, cold, error=None if old_gap else PENDING_ERROR)
                    snapshot(dest, cold / 'state')
                    check_partial(meta)
                    if old_gap:
                        assert not authority.exists()
                        authority.write_bytes(original)  # only after independently grading mixed startup
                        (evidence / name / 'control-only-restored-authority.json').write_bytes(original)
                    else:
                        retry = json.loads(authority.read_text())
                        assert retry['attempts'] == (3 if committed else 2)
                        assert retry['files'] == [json.loads(original)['files'][-1]]
                bad.write_bytes(payload[pending])
                if scenario == 'crash-after-corrupt':
                    # A separate repaired arm completed at attempt3. This one must
                    # truthfully refuse attempt4 even after fixing the object.
                    saved = authority.read_bytes()
                    saved_stages = {p.name: p.read_bytes() for p in stage.iterdir()}
                    phase = evidence / name / 'exhausted-repaired'
                    run_native(engine, dest, phase, error=EXHAUSTED)
                    snapshot(dest, phase / 'state')
                    check_partial(meta)
                    assert authority.read_bytes() == saved
                    assert {p.name: p.read_bytes() for p in stage.iterdir()} == saved_stages
                else:
                    phase = evidence / name / 'repaired'
                    run_native(engine, dest, phase)
                    snapshot(dest, phase / 'state')
                    assert (dest / pending).read_bytes() == payload[pending]
                    state = json.loads((meta / 'state.json').read_text())
                    assert state['version'] == manifest['version'] and state['files'][pending] == files[pending]['hash']
                    assert state['files'][zone] == digest(old)
                    assert not authority.exists() and (meta / 'installed.json').read_bytes() == signed
                    if mode == 'crash-after':
                        # Newly reduced authority cannot name these resolved objects.
                        for p in (content, zone):
                            assert (stage / files[p]['hash']).read_bytes() == stages[files[p]['hash']]
                    for p, data in guards.items():
                        assert (dest / p).read_bytes() == data, p
                snapshot(dest, evidence / name / 'final')
                result['passed'].append(name)
                print('PASS interruption', name, 'before' if a.expect_before else 'subject', flush=True)
                ensure_retirable()
                shutil.rmtree(dest)
                dest = None
        assert sha(engine.read_bytes()) == binding['engine_sha256'], 'native disk client changed'
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        retire_runtime(root, evidence, result, dest)


if __name__ == '__main__':
    main()
