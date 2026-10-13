#!/usr/bin/env python3
"""Native cold-recovery falsifiers using an existing signed fixture, never a key.

Reconstruct ONLY the signed object set under a fresh owned root. The engine is
invoked externally: its test build need not match the signed archived engine.
No player install, production signing/feed or HTTP request is used. --expect-before
requires both the old zone-overwrite and linked-ledger-temp actors to act.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import updatefeed


def digest(data):
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def run_engine(engine, dest, error=None):
    protected = {p: (dest / p).read_bytes() for p in
                 ['ftesurf/ftesurf.cfg', 'ftesurf/data/runs/player-sentinel.rec']}
    args = [str(engine), '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
            '+set', 'cfg_save_auto', '0', '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
            '+set', 'update_autocheck', '0',
            '+set', 'update_allow_insecure', '1', '+set', 'log_name', 'recovery',
            '+set', 'log_enable', '1', '+echo', 'NATIVE_RECOVERY_ACTED', '+quit']
    master = slave = job = None
    with (dest / 'native-output.log').open('wb') as out:
        if os.name == 'nt':
            # Suspend before assignment: no descendant may escape the owned job.
            from test_update_handoff import owned_job
            from test_ingame_update import owned_error
            p = subprocess.Popen(args, cwd=Path('C:/FTESurf'), stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=subprocess.STDOUT, creationflags=4)
            try:
                job = owned_job(p)
                resume = ctypes.WinDLL('ntdll').NtResumeProcess
                resume.argtypes = [ctypes.c_void_p]
                resume.restype = ctypes.c_long
                assert resume(int(p._handle)) == 0, 'could not resume owned engine'
                if error:
                    fatal = owned_error(p, error)
                    (dest / 'fatal.log').write_text(fatal, encoding='utf-8')
                p.wait(timeout=30)
            finally:
                if job:
                    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    assert kernel.CloseHandle(job), ctypes.get_last_error()
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=10)
        else:
            import errno
            import pty
            import signal
            master, slave = pty.openpty()
            p = subprocess.Popen(args, cwd=dest, stdin=subprocess.DEVNULL, stdout=out,
                                 stderr=slave, start_new_session=True)
            os.close(slave)
            try:
                p.wait(timeout=30)
            finally:
                if p.poll() is None:
                    os.killpg(p.pid, signal.SIGTERM)
                    try: p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(p.pid, signal.SIGKILL)
                        p.wait(timeout=10)
                os.set_blocking(master, False)
                while True:
                    try: block = os.read(master, 65536)
                    except BlockingIOError: break
                    except OSError as e:
                        if e.errno != errno.EIO: raise
                        break
                    if not block: break
                    out.write(block)
                os.close(master)
    text = (dest / 'native-output.log').read_text(encoding='utf-8', errors='replace')
    # Windows GUI-subsystem engines do not necessarily inherit stdout, so
    # redirected stdout alone is not a startup actor. Read the explicit engine log.
    text += '\n'.join(p.read_text(encoding='utf-8', errors='replace')
                      for p in dest.rglob('recovery*.log'))
    if error:
        fatal = (dest / 'fatal.log').read_text(encoding='utf-8') if os.name == 'nt' else text
        assert error in fatal and p.returncode != 0, (p.returncode, fatal)
        assert 'NATIVE_RECOVERY_ACTED' not in text, 'refusal occurred after startup actor'
    else:
        assert p.returncode == 0 and 'NATIVE_RECOVERY_ACTED' in text, (p.returncode, text)
    for path, data in protected.items():
        assert (dest / path).read_bytes() == data, 'changed protected player sentinel: ' + path
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--feed', type=Path, required=True, help='retained signed fixture update.json')
    ap.add_argument('--objects', type=Path, required=True, help='read-only complete object closure')
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    engine, root = a.engine.resolve(strict=True), a.work_root.absolute()
    assert not root.exists(), 'fresh uniquely owned work root required'
    signed = a.feed.read_bytes()
    manifest = updatefeed.verify(signed)
    platform = 'win64' if os.name == 'nt' else 'linux64'
    files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', platform)}
    zone = next(p for p in files if p.startswith('ftesurf/maps/zones/local/'))
    content = next(p for p in files if p.startswith('ftesurf/gfx/updater_fixture'))
    payload = {}
    for path, entry in files.items():
        obj = a.objects / entry['hash'][:2] / entry['hash']
        assert obj.is_file() and not obj.is_symlink(), 'missing/linked fixture object: ' + path
        data = obj.read_bytes()
        assert len(data) == entry['size'] and digest(data) == entry['hash'], 'corrupt fixture object: ' + path
        payload[path] = data
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Native recovery runtime-only signed fixture set. No keys, network, player data or install writes. Own PID/job handles only; retained evidence.\n')
    result = {'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'feed_sha256': hashlib.sha256(signed).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'expect_before': a.expect_before, 'passed': []}
    old_zone = b'previous managed zone baseline\n'
    old_content = b'previous managed content baseline\n'
    edited = b'owner intervening zone edit; keep this\n'

    def prepare(name, rows, edited_zone=False, corrupt_ledger=False, recorded_zone=True):
        dest = root / name
        dest.mkdir()
        for path, data in payload.items():
            p = dest / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        (dest / content).write_bytes(old_content)
        (dest / zone).write_bytes(edited if edited_zone else old_zone)
        (dest / 'ftesurf/ftesurf.cfg').write_bytes(b'cfg_save_auto 0\n// owned player settings sentinel\n')
        (dest / 'ftesurf/data/runs').mkdir(parents=True)
        (dest / 'ftesurf/data/runs/player-sentinel.rec').write_bytes(b'owned player recording sentinel\n')
        meta = dest / '.ftesurf-updater'
        (meta / 'ingame/staged').mkdir(parents=True)
        (meta / 'consent').write_bytes(b'0\n')
        ledger = {'version': '0.1.25', 'files': {p: f['hash'] for p, f in files.items()}}
        ledger['files'].update({zone: digest(old_zone), content: digest(old_content)})
        if not recorded_zone:
            ledger['files'].pop(zone)
        (meta / 'state.json').write_bytes(b'{broken ledger' if corrupt_ledger else json.dumps(ledger).encode())
        (meta / 'ingame/manifest.json').write_bytes(signed)
        for path in rows:
            (meta / 'ingame/staged' / files[path]['hash']).write_bytes(payload[path])
        journal = {'attempts': 1, 'version': manifest['version'], 'files': [
            {'p': p, 'h': files[p]['hash'], 's': files[p]['size'], 'x': int(files[p]['exec'])} for p in rows]}
        (meta / 'ingame/journal.json').write_text(json.dumps(journal))
        return dest, meta, ledger

    def passed(name):
        result['passed'].append(name)
        print('PASS', name)

    try:
        # Positive control proves replay, signed validation, replacement and ledger ACT.
        dest, meta, ledger = prepare('unedited-positive', [content, zone])
        run_engine(engine, dest)
        state = json.loads((meta / 'state.json').read_text())
        assert (dest / content).read_bytes() == payload[content] and (dest / zone).read_bytes() == payload[zone]
        assert state['version'] == manifest['version'] and all(state['files'][p] == files[p]['hash'] for p in [content, zone])
        assert (meta / 'installed.json').read_bytes() == signed and not (meta / 'ingame/journal.json').exists()
        passed('signed unedited zone/content recovery actually installs and commits')

        orders = [('edited-first', [zone, content], True), ('edited-later', [content, zone], True),
                  ('edited-only', [zone], True), ('unrecorded-edit', [content, zone], False),
                  ('unrecorded-only', [zone], False)]
        for name, rows, recorded in orders:
            dest, meta, ledger = prepare(name, rows, edited_zone=True, recorded_zone=recorded)
            if rows == [zone]:
                (dest / content).write_bytes(payload[content])
            run_engine(engine, dest)
            state = json.loads((meta / 'state.json').read_text())
            if a.expect_before:
                assert (dest / zone).read_bytes() == payload[zone] and state['files'][zone] == files[zone]['hash'], 'pre-fix zone overwrite did not ACT'
            else:
                assert (dest / zone).read_bytes() == edited, name + ' overwrote intervening local edits'
                assert state['files'].get(zone) == ledger['files'].get(zone), name + ' falsely certified edited bytes'
            assert state['version'] == manifest['version'] and (dest / content).read_bytes() == payload[content]
            assert not (meta / 'ingame/journal.json').exists() and (meta / 'installed.json').read_bytes() == signed
            passed(('BEFORE overwrite actor: ' if a.expect_before else 'intervening edit preserved without false ledger: ') + name)

        dest, meta, ledger = prepare('corrupt-ledger', [content, zone], edited_zone=True, corrupt_ledger=True)
        pending = (meta / 'ingame/journal.json').read_bytes()
        run_engine(engine, dest, 'Cannot read the update recovery ledger')
        assert (dest / content).read_bytes() == old_content and (dest / zone).read_bytes() == edited
        assert (meta / 'state.json').read_bytes() == b'{broken ledger' and (meta / 'ingame/journal.json').read_bytes() == pending
        passed('corrupt ledger refuses before earlier content replacement')

        dest, meta, ledger = prepare('linked-ledger-temp', [content, zone])
        outside = root / 'outside-ledger-sentinel.txt'
        sentinel = b'outside native ledger temp sentinel; must not truncate\n'
        outside.write_bytes(sentinel)
        link = meta / 'state.json.enginetmp'
        link.symlink_to(outside)
        pending = (meta / 'ingame/journal.json').read_bytes()
        ledger_bytes = (meta / 'state.json').read_bytes()
        run_engine(engine, dest, None if a.expect_before else 'Linked updater metadata')
        if a.expect_before:
            assert outside.read_bytes() != sentinel, 'pre-fix linked-temp write did not ACT'
            assert json.loads(outside.read_text())['version'] == manifest['version']
            passed('BEFORE native ledger temp follows link and overwrites outside sentinel')
        else:
            assert outside.read_bytes() == sentinel and link.is_symlink()
            assert (meta / 'state.json').read_bytes() == ledger_bytes and (meta / 'ingame/journal.json').read_bytes() == pending
            assert (dest / content).read_bytes() == old_content and (dest / zone).read_bytes() == old_zone
            passed('linked native ledger temp refuses before external/live/metadata writes')
        result['status'] = 'PASS'
    except BaseException as error:
        result.update(status='FAIL', error=str(error))
        raise
    finally:
        (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
