#!/usr/bin/env python3
"""Unprivileged native recovery controls using a retained signed Linux object set.

Run on ext4/tmpfs, never DrvFS: --runtime-root is fresh and disposable; --evidence
is fresh and retained. No signing seed, network, player install or key override.
--expect-before requires the historical overwrite/leaked-object actors to ACT.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

import updatefeed
from test_update_native_recovery import digest, run_engine


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['engine', 'feed', 'objects', 'runtime-root', 'evidence']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    if os.name != 'posix' or os.geteuid() == 0:
        ap.error('requires an unprivileged Linux driver/client')
    root, evidence = a.runtime_root.absolute(), a.evidence.absolute()
    assert not root.exists() and not evidence.exists(), 'fresh owned paths required'
    assert not root.parent.is_symlink() and not evidence.parent.is_symlink()
    root.mkdir()
    (root / 'OWNER.md').write_text('Owned unprivileged native recovery runtime; no player data. Retire after evidence export.\n')
    evidence.mkdir(parents=True)
    result = dict(status='FAIL', uid=os.geteuid(), gid=os.getegid(), groups=os.getgroups(),
                  engine_sha256=hashlib.sha256(a.engine.read_bytes()).hexdigest(),
                  harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  runtime_root=str(root), expect_before=a.expect_before, passed=[])
    modes = []
    try:
        # chmod behavior AND open refusal must discriminate before native testing.
        probe = root / 'mode-probe'
        probe.write_bytes(b'permission probe')
        probe.chmod(0)
        assert probe.stat().st_mode & 0o777 == 0
        try:
            probe.read_bytes()
        except PermissionError:
            pass
        else:
            raise AssertionError('filesystem/uid did not enforce mode000')
        probe.chmod(0o600)
        probe.unlink()
        result['mode000_open_refused'] = True
        signed = a.feed.read_bytes()
        manifest = updatefeed.verify(signed)
        result['feed_sha256'] = hashlib.sha256(signed).hexdigest()
        files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'linux64')}
        zone = next(p for p in files if p.endswith('.json') and '/zones/local/' in p)
        addon = 'ftesurf/fs_addons.txt'
        content = 'ftesurf/gfx/crosshairs/xhair1.png'
        later = 'ftesurf/gfx/crosshairs/xhair2.png'
        shared = 'ftesurf/gfx/env/missingtexture.png'
        locked = 'ftesurf/textures/no_texture.png'
        assert files[shared]['hash'] == files[locked]['hash'], 'signed shared-object control required'
        payload = {}
        for path, entry in files.items():
            obj = a.objects / entry['hash'][:2] / entry['hash']
            assert not obj.is_symlink()
            data = obj.read_bytes()
            assert len(data) == entry['size'] and digest(data) == entry['hash'], path
            payload[path] = data
        old = b'previous managed baseline\n'
        edited = b'// intervening protected local edit; keep these exact bytes\n'

        def prepare(name, rows, protected=None, missing=False):
            dest = root / name
            dest.mkdir()
            for path, data in payload.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                if files[path]['exec']:
                    p.chmod(0o755)
            (dest / 'ftesurf/ftesurf.cfg').write_bytes(b'cfg_save_auto 0\n// owned player settings sentinel\n')
            (dest / 'ftesurf/data/runs').mkdir(parents=True, exist_ok=True)
            (dest / 'ftesurf/data/runs/player-sentinel.rec').write_bytes(b'owned recording sentinel\n')
            meta = dest / '.ftesurf-updater'
            (meta / 'ingame/staged').mkdir(parents=True)
            (meta / 'consent').write_text('0\n')
            ledger = dict(version='0.1.24', files={p: e['hash'] for p, e in files.items()})
            for p in rows:
                (dest / p).write_bytes(old)
                ledger['files'][p] = digest(old)
                (meta / 'ingame/staged' / files[p]['hash']).write_bytes(payload[p])
            if protected:
                (dest / protected).write_bytes(edited)
                if missing:
                    (dest / protected).unlink()
            (meta / 'state.json').write_text(json.dumps(ledger))
            (meta / 'ingame/manifest.json').write_bytes(signed)
            (meta / 'ingame/journal.json').write_text(json.dumps(dict(attempts=1, version=manifest['version'], files=[
                dict(p=p, h=files[p]['hash'], s=files[p]['size'], x=int(files[p]['exec'])) for p in rows])))
            return dest, meta, ledger

        def export(dest, out):
            out.mkdir(parents=True)
            for p in dest.rglob('*.log'):
                target = out / p.relative_to(dest)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
            for p in (dest / '.ftesurf-updater').rglob('*.json'):
                target = out / p.relative_to(dest)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
            (out / 'staging.json').write_text(json.dumps({p.name: digest(p.read_bytes()) for p in
                (dest / '.ftesurf-updater/ingame/staged').iterdir() if p.is_file()}, indent=2))

        def passed(name, dest):
            export(dest, evidence / dest.name / ('phase-%02d' % (len(result['passed']) + 1)))
            result['passed'].append(name)
            print('PASS', name, flush=True)

        for protected in [zone, addon]:
            label = 'zone' if protected == zone else 'addons'
            dest, meta, ledger = prepare(label + '-missing', [content, protected], protected, missing=True)
            run_engine(a.engine, dest)
            state = json.loads((meta / 'state.json').read_text())
            assert (dest / protected).read_bytes() == payload[protected]
            assert state['version'] == manifest['version'] and state['files'][protected] == files[protected]['hash']
            assert not (meta / 'ingame/journal.json').exists() and (meta / 'installed.json').read_bytes() == signed
            passed(label + ': genuinely missing protected file installs', dest)

            for first in [False, True]:
                rows = [protected, content] if first else [content, protected]
                dest, meta, ledger = prepare(label + '-unreadable-' + str(first), rows, protected)
                before_journal = (meta / 'ingame/journal.json').read_bytes()
                before_state = (meta / 'state.json').read_bytes()
                p = dest / protected
                p.chmod(0)
                modes.append((p, 0o644))
                try:
                    p.read_bytes()
                except PermissionError:
                    pass
                else:
                    raise AssertionError('protected fixture was readable')
                text = run_engine(a.engine, dest, None if a.expect_before else 'Cannot read protected update file')
                mode_after = p.stat().st_mode & 0o777
                p.chmod(0o644)
                if a.expect_before:
                    assert p.read_bytes() == payload[protected], 'old overwrite did not ACT'
                    assert json.loads((meta / 'state.json').read_text())['files'][protected] == files[protected]['hash']
                else:
                    assert p.read_bytes() == edited and mode_after == 0
                    assert (dest / content).read_bytes() == old, 'refused after earlier mutation'
                    assert (meta / 'state.json').read_bytes() == before_state
                    assert (meta / 'ingame/journal.json').read_bytes() == before_journal
                    assert not (meta / 'installed.json').exists()
                passed(label + ': mode000 ' + ('old overwrite ACTED' if a.expect_before else 'preflight refusal') + ' first=' + str(first), dest)

        for first in [False, True]:
            rows = [zone, content] if first else [content, zone]
            dest, meta, ledger = prepare('zone-inaccessible-ancestor-' + str(first), rows, zone)
            before_state = (meta / 'state.json').read_bytes()
            before_journal = (meta / 'ingame/journal.json').read_bytes()
            parent = (dest / zone).parent
            parent.chmod(0)
            modes.append((parent, 0o755))
            try:
                (dest / zone).stat()
            except PermissionError:
                pass
            else:
                raise AssertionError('ancestor allowed search')
            run_engine(a.engine, dest, 'Unfinished content update' if a.expect_before else 'Cannot read protected update file')
            parent.chmod(0o755)
            assert (dest / zone).read_bytes() == edited
            if a.expect_before:
                assert (dest / content).read_bytes() == payload[content], 'old late refusal did not ACT'
            else:
                assert (dest / content).read_bytes() == old
                assert (meta / 'state.json').read_bytes() == before_state
                assert (meta / 'ingame/journal.json').read_bytes() == before_journal
            assert not (meta / 'installed.json').exists()
            passed('inaccessible ancestor: ' + ('old late refusal ACTED' if a.expect_before else 'preflight refusal') + ' first=' + str(first), dest)

        # Different paths can consume one staged hash: do not purge it while a
        # locked outstanding row still needs it, even if another row resolved.
        for name, tail, is_locked in [('mixed-corrupt', later, False), ('mixed-corrupt-protected-object', later, False), ('mixed-locked-shared', locked, True)]:
            first = shared if is_locked else content
            dest, meta, ledger = prepare(name, [first, zone, tail], zone)
            if is_locked:
                (dest / first).write_bytes(payload[first])
                parent = (dest / tail).parent
                parent.chmod(0o555)
                modes.append((parent, 0o755))
                try:
                    (parent / 'write-probe').write_bytes(b'must refuse')
                except PermissionError:
                    pass
                else:
                    raise AssertionError('locked directory was writable')
            else:
                (meta / 'ingame/staged' / files[tail]['hash']).write_bytes(b'corrupt staged object\n')
            corrupt_resolved = name == 'mixed-corrupt-protected-object'
            if corrupt_resolved:
                (meta / 'ingame/staged' / files[zone]['hash']).write_bytes(b'corrupt resolved object\n')
            unrelated = meta / 'ingame/staged' / digest(b'unreferenced sentinel')
            unrelated.write_bytes(b'unreferenced sentinel')
            run_engine(a.engine, dest, 'Unfinished content update')
            state = json.loads((meta / 'state.json').read_text())
            journal = json.loads((meta / 'ingame/journal.json').read_text())
            assert (dest / first).read_bytes() == payload[first] and (dest / zone).read_bytes() == edited
            assert state['version'] == ledger['version']
            assert state['files'][first] == files[first]['hash'] and state['files'][zone] == ledger['files'][zone]
            assert state['files'][tail] == ledger['files'][tail] and not (meta / 'installed.json').exists()
            assert journal['attempts'] == 2 and [r['p'] for r in journal['files']] == [tail]
            staged = meta / 'ingame/staged'
            assert (staged / files[tail]['hash']).exists() and unrelated.read_bytes() == b'unreferenced sentinel'
            for p in [first, zone]:
                needed = files[p]['hash'] == files[tail]['hash'] or (corrupt_resolved and p == zone)
                assert (staged / files[p]['hash']).exists() == (a.expect_before or needed), 'resolved object retirement: ' + p
            passed(name + ': honest partial ledger/journal and ' + ('old resolved-object leak ACTED' if a.expect_before else 'bounded retirement'), dest)
            if is_locked:
                parent.chmod(0o755)
            else:
                (staged / files[tail]['hash']).write_bytes(payload[tail])
            run_engine(a.engine, dest)
            state = json.loads((meta / 'state.json').read_text())
            assert (dest / tail).read_bytes() == payload[tail] and (dest / zone).read_bytes() == edited
            assert state['version'] == manifest['version'] and state['files'][tail] == files[tail]['hash']
            assert state['files'][zone] == ledger['files'][zone]
            assert not (meta / 'ingame/journal.json').exists() and (meta / 'installed.json').read_bytes() == signed
            assert not (staged / files[tail]['hash']).exists() and unrelated.read_bytes() == b'unreferenced sentinel'
            if corrupt_resolved:
                assert (staged / files[zone]['hash']).read_bytes() == b'corrupt resolved object\n'
            passed(name + ': repaired retry ACTS and completes', dest)

        dest, meta, ledger = prepare('journal-rewrite-refusal', [content, zone, later], zone)
        (meta / 'ingame/staged' / files[later]['hash']).write_bytes(b'corrupt staged object\n')
        before_journal = (meta / 'ingame/journal.json').read_bytes()
        (meta / 'ingame').chmod(0o555)
        modes.append((meta / 'ingame', 0o755))
        run_engine(a.engine, dest, 'Unfinished content update' if a.expect_before else 'Cannot rewrite the update recovery journal')
        (meta / 'ingame').chmod(0o755)
        assert (dest / content).read_bytes() == payload[content] and (dest / zone).read_bytes() == edited
        assert (meta / 'ingame/journal.json').read_bytes() == before_journal
        assert all((meta / 'ingame/staged' / files[p]['hash']).exists() for p in [content, zone, later])
        assert not (meta / 'installed.json').exists()
        assert json.loads((meta / 'state.json').read_text())['version'] == ledger['version']
        passed('failed journal rewrite refuses without retiring any object', dest)

        dest, meta, ledger = prepare('retry-exhaustion', [content])
        (meta / 'ingame/staged' / files[content]['hash']).write_bytes(b'corrupt staged object\n')
        for attempts in [2, 3]:
            run_engine(a.engine, dest, 'Unfinished content update')
            assert json.loads((meta / 'ingame/journal.json').read_text())['attempts'] == attempts
        before_journal = (meta / 'ingame/journal.json').read_bytes()
        before_state = (meta / 'state.json').read_bytes()
        run_engine(a.engine, dest, 'Update cannot finish while files are held open')
        assert (meta / 'ingame/journal.json').read_bytes() == before_journal
        assert (meta / 'state.json').read_bytes() == before_state
        assert (dest / content).read_bytes() == old and not (meta / 'installed.json').exists()
        passed('retry exhaustion retains original journal, ledger and local bytes', dest)
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        try:
            for path, mode in reversed(modes):
                if path.exists():
                    path.chmod(mode)
            # No copystat: an unprivileged driver cannot chmod DrvFS evidence.
            if result['status'] == 'FAIL' and 'dest' in locals():
                export(dest, evidence / dest.name / 'failed-phase')
        finally:
            try:
                shutil.rmtree(root)
            finally:
                result['runtime_retired'] = not root.exists()
                if not result['runtime_retired']:
                    result.update(status='FAIL', cleanup_error='runtime retirement failed')
                (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
