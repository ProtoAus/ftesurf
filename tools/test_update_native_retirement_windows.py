#!/usr/bin/env python3
"""Separate native full-superset retirement gate; historical graders are immutable."""
import argparse
from contextlib import contextmanager
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path

from test_update_native_journal import (PENDING_ERROR, UNCONFIRMED_PHASES,
    preflight_paths, sha, snapshot, _checked_files)
from test_update_native_journal_initial import cold_phase
from test_update_native_journal_live import destination_lock, retire_runtime
from test_update_native_journal_deferred import pe_text
from test_update_native_journal_interrupt import EXHAUSTED
import test_update_native_staging_windows as staging
from test_update_native_windows_unreadable import busy_port_control, kernel32


def byte_hash(data):
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in _checked_files(root)}


def authority(f, attempts):
    return dict(version=f['version'], attempts=attempts, files=copy.deepcopy(f['rows']))


def stage_path(f, path):
    return f['meta'] / 'ingame/staged' / f['files'][path]['hash']


def prepare(root, name, kind, first, signed, manifest, files, payload, attempts=1, completed=False):
    f = staging.prepare(root, name, kind, first, signed, manifest, files, payload)
    f['rows'] = json.loads(f['raw_authority'])['files']
    f['attempts'] = attempts
    if completed:
        for key in ('resolved', 'pending'):
            (f['dest'] / f[key]).write_bytes(payload[f[key]])
            f['ledger']['files'][f[key]] = files[f[key]]['hash']
        f['ledger']['version'] = f['version']
        (f['meta'] / 'state.json').write_text(json.dumps(f['ledger']))
        (f['meta'] / 'installed.json').write_bytes(signed)
        stage_path(f, f['pending']).write_bytes(payload[f['pending']])
        f['stage'][files[f['pending']]['hash']] = payload[f['pending']]
    f['seed_complete'] = completed
    raw = json.dumps(authority(f, attempts)).encode()
    (f['meta'] / 'ingame/journal.json').write_bytes(raw)
    f['raw_authority'] = raw
    # These are outside the retirement authority, including failed temp siblings.
    extras = {'ingame/staged/' + 'a' * 64 + '.part': b'outside part sentinel',
              'ingame/staged/' + 'b' * 64 + '.install': b'outside install sentinel',
              'ingame/journal.tmp': b'outside failed temp sentinel'}
    for path, data in extras.items():
        (f['meta'] / path).write_bytes(data)
    f['extras'] = extras
    f['seed'] = inventory(f['dest'])
    return f


def pending_hashes(f, complete):
    # Independent raw-byte/protection oracle: no engine/model pending predicate.
    pending = set()
    for row in f['rows']:
        path = row['p']
        data = f['payload'][path] if complete and path == f['pending'] else (
            f['payload'][path] if path == f['resolved'] else f['seed'][path])
        protected = '/zones/local/' in path and data != staging.OLD
        if not protected and (len(data) != row['s'] or byte_hash(data) != row['h']):
            pending.add(row['h'])
    return pending


def expected_objects(f, complete, blocked=()):
    expected = dict(f['stage'])
    pending = pending_hashes(f, complete)
    for row in f['rows']:
        h = row['h']
        data = expected.get(h)
        if data is None or h in pending or h in blocked:
            continue
        if len(data) == row['s'] and byte_hash(data) == h:
            del expected[h]
    for path, data in f['extras'].items():
        if path.startswith('ingame/staged/'):
            expected[Path(path).name] = data
    return expected


def grade(f, complete, attempts, before=False, blocked=(), journal_held=False):
    for path, data in f['sentinels'].items():
        assert (f['dest'] / path).read_bytes() == data, 'protected sentinel: ' + path
    assert (f['dest'] / f['resolved']).read_bytes() == f['payload'][f['resolved']], 'resolved install must ACT'
    assert (f['dest'] / f['pending']).read_bytes() == (f['payload'][f['pending']] if complete else staging.OLD)
    for path, data in f['payload'].items():
        if path not in (f['pending'], f['resolved']) and path not in f['sentinels']:
            assert (f['dest'] / path).read_bytes() == data, 'signed closure byte identity: ' + path
    assert (f['meta'] / 'consent').read_bytes() == b'0\n'
    assert (f['meta'] / 'ingame/manifest.json').read_bytes() == f['signed']
    ledger = copy.deepcopy(f['ledger'])
    ledger['files'][f['resolved']] = f['files'][f['resolved']]['hash']
    if complete:
        ledger['version'] = f['version']
        ledger['files'][f['pending']] = f['files'][f['pending']]['hash']
    assert json.loads((f['meta'] / 'state.json').read_text()) == ledger, 'ledger/version/preserved policy'
    expected = expected_objects(f, complete, blocked)
    actual = {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir()}
    assert actual == expected, 'staged byte map/removal ACT'
    named_survivors = {row['h'] for row in f['rows']} & expected.keys()
    path = f['meta'] / 'ingame/journal.json'
    if before:
        if complete and not journal_held:
            assert not path.exists(), 'before unlink-before-purge defect did not ACT'
        elif complete:
            assert path.read_bytes() == f['raw_authority']
        else:
            assert json.loads(path.read_text()) == dict(version=f['version'], attempts=attempts,
                files=[r for r in f['rows'] if r['p'] == f['pending']]), 'before reduction defect did not ACT'
    elif not complete or named_survivors or journal_held:
        assert json.loads(path.read_text()) == authority(f, attempts), 'full signed row superset/budget'
    else:
        assert not path.exists(), 'final authority was not retired'
    cert = f['meta'] / 'installed.json'
    if complete:
        assert cert.read_bytes() == f['signed']
    else:
        assert not cert.exists(), 'partial completion certificate'
    # Partial publication consumes its temp; cleanup-only completion must not adopt it.
    tmp = f['meta'] / 'ingame/journal.tmp'
    if not complete or f.get('partial_completed', False) or (complete and not f['seed_complete'] and not before):
        assert not tmp.exists(), 'published temp not consumed'
    else:
        assert tmp.read_bytes() == f['extras']['ingame/journal.tmp'], 'outside temp adopted'
    return dict(complete=complete, attempts=attempts, named_survivors=sorted(named_survivors),
                stage_sha256={name: sha(data) for name, data in actual.items()},
                before_defect=before and (not complete or bool(named_survivors)))


def unchanged(f):
    actual = inventory(f['dest'])
    # The native runner adds only its own logs, lock and manifest/cfg control files.
    for path, data in f['seed'].items():
        assert actual.get(path) == data, 'refusal mutated seed bytes: ' + path
    protected_prefixes = ('.ftesurf-updater/', 'ftesurf/data/')
    def protected(path):
        return path.startswith(protected_prefixes) and path != '.ftesurf-updater/install.lock'
    assert {p: b for p, b in actual.items() if protected(p)} == {
        p: b for p, b in f['seed'].items() if protected(p)}, 'refusal added retirement/content files'
    return dict(seed_file_count=len(f['seed']), unchanged=True)


def semantic_phase(phase, checker):
    guard = phase / 'retirement-semantic-guard'
    UNCONFIRMED_PHASES.add(guard)
    receipt = dict(status='FAIL')
    try:
        receipt.update(checker(), status='PASS')
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        (phase / 'grade.json').write_text(json.dumps(receipt, indent=2) + '\n')
        UNCONFIRMED_PHASES.discard(guard)


@contextmanager
def held_delete(path, case):
    """Readable leaf with real DeleteFileW error32; release before next launch."""
    guard = case / 'delete-lock-guard'
    UNCONFIRMED_PHASES.add(guard)
    receipt = dict(status='FAIL', path=path.name)
    before = path.read_bytes()
    try:
        with destination_lock(path):
            k = kernel32()
            k.DeleteFileW.argtypes = [ctypes.c_wchar_p]
            k.DeleteFileW.restype = ctypes.c_int
            assert not k.DeleteFileW(str(path)), 'delete denial did not ACT'
            receipt['delete_error'] = ctypes.get_last_error()
            assert receipt['delete_error'] == 32 and path.read_bytes() == before
            # A second open can write the same bytes: no write-denial substitute.
            path.write_bytes(before)
            assert path.read_bytes() == before
            receipt['read_write_identity'] = sha(before)
            yield
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['error'] = repr(error)
        raise
    finally:
        (case / 'lock.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if receipt['status'] == 'PASS':
            UNCONFIRMED_PHASES.discard(guard)


def mutate_authority(f, mutation):
    path = f['meta'] / 'ingame/journal.json'
    j = json.loads(path.read_text())
    if mutation == 'duplicate':
        j['files'].append(copy.deepcopy(j['files'][0]))
    elif mutation == 'exec':
        j['files'][0]['x'] ^= 1
    elif mutation == 'tuple':
        j['files'][0]['s'] += 1
    elif mutation == 'unsigned':
        (f['meta'] / 'ingame/manifest.json').write_bytes(b'{}')
    elif mutation == 'version':
        j['version'] = '0.0.0'
    elif mutation == 'malformed':
        path.write_bytes(b'{')
        f['seed'] = inventory(f['dest'])
        return
    else:
        raise AssertionError(mutation)
    path.write_text(json.dumps(j))
    f['seed'] = inventory(f['dest'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'feed', 'runtime-root', 'evidence'):
        ap.add_argument('--' + name, required=True, type=Path)
    ap.add_argument('--objects', required=True, action='append', type=Path)
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt', 'Windows native driver required'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    assert engine.is_file() and symbols.is_file()
    assert pe_text(engine) == pe_text(symbols), 'immutable executable/companion text mismatch'
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    signed, manifest, files, payload = staging.load_inputs(a.feed, a.objects)
    sources = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('test_update_native*.py')}
    for name in ('updatefeed.py', 'test_update_handoff.py', 'test_ingame_update.py'):
        sources[name] = sha(Path(__file__).with_name(name).read_bytes())
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned retirement synthetic fixtures; no peer processes; preserve failures and guards.\n')
    result = dict(status='FAIL', engine_sha256=sha(engine.read_bytes()), symbols_sha256=sha(symbols.read_bytes()),
                  feed_sha256=sha(signed), sources_sha256=sources, expect_before=a.expect_before, cases=[])
    f = None
    def seed(name, kind='unique', first=False, attempts=1, completed=False):
        nonlocal f
        case = evidence / name
        case.mkdir()
        f = prepare(root, name, kind, first, signed, manifest, files, payload, attempts, completed)
        snapshot(f['dest'], case / 'seed')
        return case
    def phase(case, name, error=None, checker=None):
        target = case / name
        cold_phase(engine, f['dest'], target, error)
        semantic_phase(target, checker)
    try:
        result['busy_port_control'] = busy_port_control()
        with staging.offline_mirror(manifest) as hits:
            for kind in ('unique', 'shared', 'corrupt-resolved', 'wrong-size-resolved', 'reduced-orphan'):
                for first in ((False,) if kind == 'reduced-orphan' else (False, True)):
                    name = kind + ('-first' if first else '-last')
                    case = seed(name, kind, first)
                    if kind == 'shared':
                        with held_delete(f['dest'] / f['pending'], case):
                            phase(case, 'partial', PENDING_ERROR, lambda: grade(f, False, 2, a.expect_before))
                    else:
                        phase(case, 'partial', PENDING_ERROR, lambda: grade(f, False, 2, a.expect_before))
                    f['partial_completed'] = True  # prior publication already consumed its sibling
                    stage_path(f, f['pending']).write_bytes(payload[f['pending']])
                    # Keep the repaired input explicit for independent map expectations.
                    f['stage'][files[f['pending']]['hash']] = payload[f['pending']]
                    if a.expect_before:
                        # Historical reduced authority cannot adopt previously resolved rows.
                        f['rows'] = [r for r in f['rows'] if r['p'] == f['pending']]
                        f['stage'] = {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir() if len(p.name) == 64}
                    phase(case, 'complete', checker=lambda: grade(f, True, 3, a.expect_before))
                    result['cases'].append(name)
            for scenario, attempts, completed, final_lock in (
                    ('stage-held-admitted', 2, False, False), ('stage-held-completed3', 3, True, False),
                    ('journal-held-completed', 2, True, True)):
                case = seed(scenario, attempts=attempts, completed=completed)
                if not completed:
                    stage_path(f, f['pending']).write_bytes(payload[f['pending']])
                    f['stage'][files[f['pending']]['hash']] = payload[f['pending']]
                held = f['meta'] / 'ingame/journal.json' if final_lock else stage_path(f, f['resolved'])
                blocked = () if final_lock else (files[f['resolved']]['hash'],)
                with held_delete(held, case):
                    if a.expect_before and attempts == 3:
                        phase(case, 'held', EXHAUSTED, lambda: unchanged(f))
                        phase(case, 'held-repeat', EXHAUSTED, lambda: unchanged(f))
                    else:
                        bump = attempts if completed else attempts + 1
                        phase(case, 'held', checker=lambda: grade(f, True, bump, a.expect_before, blocked, final_lock))
                        # Before loses stage authority: repeat cannot revisit it.
                        phase(case, 'held-repeat', checker=lambda: grade(f, True, bump, a.expect_before, blocked, final_lock))
                if a.expect_before and attempts == 3:
                    phase(case, 'released', EXHAUSTED, lambda: unchanged(f))
                elif a.expect_before and not final_lock:
                    # Exact old defect: held object survives released restart without authority.
                    phase(case, 'released', checker=lambda: grade(f, True, attempts + 1, True, blocked))
                else:
                    phase(case, 'released', checker=lambda: grade(f, True, attempts if completed else attempts + 1, a.expect_before))
                result['cases'].append(scenario)
            case = seed('unresolved-attempt3', attempts=3)
            stage_path(f, f['pending']).write_bytes(payload[f['pending']])
            f['seed'] = inventory(f['dest'])
            phase(case, 'refused', EXHAUSTED, lambda: unchanged(f))
            result['cases'].append('unresolved-attempt3')
            case = seed('no-authority', completed=True)
            (f['meta'] / 'ingame/journal.json').unlink()
            f['seed'] = inventory(f['dest'])
            phase(case, 'startup', checker=lambda: unchanged(f))
            result['cases'].append('no-authority')
            errors = {'tuple': 'Unverified or linked recovery entry', 'duplicate': 'Duplicate recovery path',
                      'exec': 'Unverified or linked recovery entry', 'unsigned': 'Update recovery lacks a valid signed manifest',
                      'version': 'Update journal does not match its signed manifest', 'malformed': 'Damaged update journal'}
            for mutation in errors:
                case = seed('tamper-' + mutation, completed=True)
                mutate_authority(f, mutation)
                if a.expect_before and mutation in ('duplicate', 'exec'):
                    # Before accepts duplicate/exec mismatch. Require native ACT, not a relaxed subject refusal.
                    phase(case, 'accepted-defect', checker=lambda: grade(f, True, 2, True))
                else:
                    phase(case, 'refused', errors[mutation], lambda: unchanged(f))
                result['cases'].append('tamper-' + mutation)
        staging.final_http(hits, result)  # all accepted request workers joined
        assert sha(engine.read_bytes()) == result['engine_sha256']
        assert sha(symbols.read_bytes()) == result['symbols_sha256']
        assert all(sha(Path(__file__).with_name(p).read_bytes()) == h for p, h in sources.items())
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        retire_runtime(root, evidence, result, f['dest'] if f and result['status'] == 'FAIL' else None)


if __name__ == '__main__':
    main()
