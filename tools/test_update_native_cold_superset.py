#!/usr/bin/env python3
"""Independent signed-original-row oracle at the ordinary startup cold writer."""
import argparse
import copy
import json
import os
from pathlib import Path

from test_update_native_journal import (preflight_paths, sha, snapshot, source_lock,
    PENDING_ERROR, REWRITE_ERROR, ensure_retirable)
from test_update_native_journal_initial import cold_phase
from test_update_native_journal_interrupt import bind_commit, interrupt, EXHAUSTED
from test_update_native_journal_deferred import helper_identity
from test_update_native_publication_superset import (BEFORE, SUBJECT, prepare,
    grade_state, stage_map, full_authority, mirror_server)
from test_update_native_staging_windows import load_inputs, journal
from test_update_native_recovery import digest
from test_update_native_retirement_windows import inventory


def authority_grade(actual, files, paths, version, attempts, before, pending):
    rejected = False
    try:
        full_authority(actual, files, paths, version, attempts)
    except AssertionError:
        assert before, 'candidate lost original signed rows'
        assert actual == journal(files, [pending], version, attempts), 'not exact legacy reduced authority'
        rejected = True
    assert rejected == before, 'legacy reduction must ACT'
    return rejected


def stages_grade(dest, expected):
    assert stage_map(dest) == expected, 'exact stage leaves/siblings changed'


def corrupt_grade(data, row):
    assert len(data) == row['size'] and digest(data) != row['hash'], 'bad signed digest premise'


def metadata_expected(seed, ledger, stages, authority=None, temp=None, installed=None, launched=True):
    # Only the independently seeded fixture and expected operation admit names.
    expected = {p: b for p, b in seed.items() if p not in
                ('state.json', 'ingame/journal.json') and not p.startswith('ingame/staged/')}
    expected['state.json'] = copy.deepcopy(ledger)
    expected.update({'ingame/staged/' + p: b for p, b in stages.items()})
    if launched:
        expected['install.lock'] = b''
    for p, value in (('ingame/journal.json', authority), ('ingame/journal.tmp', temp),
                     ('installed.json', installed)):
        if value is not None:
            expected[p] = value
    return expected


def metadata_grade(meta, expected):
    actual = inventory(meta)
    assert actual.keys() == expected.keys(), 'complete updater metadata namespace changed'
    for p, value in expected.items():
        if isinstance(value, dict):
            assert json.loads(actual[p]) == value, 'metadata semantic identity: ' + p
        else:
            assert actual[p] == value, 'metadata byte identity: ' + p


def exhaustion_grade(dest, meta, expected, ledger, signed, version, authority_bytes, ledger_bytes, stages, metadata):
    grade_state(dest, meta, expected, ledger, signed, version)
    assert (meta / 'ingame/journal.json').read_bytes() == authority_bytes, 'exhausted authority mutated'
    assert (meta / 'state.json').read_bytes() == ledger_bytes, 'exhausted ledger bytes mutated'
    assert not (meta / 'ingame/journal.tmp').exists(), 'exhausted refusal created temp'
    stages_grade(dest, stages)
    metadata_grade(meta, metadata)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'helper', 'feed', 'runtime-root', 'evidence', 'serializer'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, required=True, action='append')
    ap.add_argument('--expect-before', action='store_true')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    assert sha(engine.read_bytes()) == (BEFORE if a.expect_before else SUBJECT)
    helper, helper_hash = helper_identity(a.helper)
    # Both exact arms use atomic P692; expect-before names reduction, not unlink.
    binding = bind_commit(engine, symbols, Path('C:/msys64/ucrt64/bin/nm.exe'),
                          Path('C:/msys64/ucrt64/bin/objdump.exe'), False)
    signed, manifest, files, payload = load_inputs(a.feed, a.objects)
    paths = [p for p in files if p in ('ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png')]
    assert len(paths) == 2 and files[paths[0]]['hash'] != files[paths[1]]['hash']
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    root.mkdir(parents=True); evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned synthetic cold publication matrix; retain failures and successful copies through review.\n')
    sources = list(Path(__file__).parent.glob('test_update_native*.py')) + [a.serializer,
        Path(__file__).with_name('native_journal_interrupt.c'),
        Path(__file__).with_name('updatefeed.py'), Path(__file__).with_name('test_update_handoff.py'),
        Path(__file__).with_name('test_ingame_update.py')]
    hashes = {str(p): sha(p.read_bytes()) for p in sources}
    result = dict(status='FAIL', binding=binding, sources=hashes, helper_sha256=helper_hash,
        signed_sha256=sha(signed), selected_rows=len(files), selected_objects=len({f['hash'] for f in files.values()}),
        cases=[], raw_failure_api_return='not observed: independent probe32 plus actual cold rewrite refusal only')
    hits = {}
    try:
        with mirror_server(manifest, signed, payload, files) as (hits, unused_url):
            for pending in paths:
                resolved = next(p for p in paths if p != pending)
                position = 'pending-first' if pending == paths[0] else 'pending-last'
                for mode in ('source-lock', 'crash-before', 'crash-after', 'none', 'exhaustion'):
                    name = position + '-' + mode
                    dest, meta, expected, ledger = prepare(root, name, payload, files, paths)
                    case = evidence / name; case.mkdir()
                    stage = meta / 'ingame/staged'; stage.mkdir(parents=True)
                    stages = {files[p]['hash']: payload[p] for p in paths}
                    bad = bytearray(payload[pending]); bad[0] ^= 1
                    corrupt_grade(bad, files[pending])
                    stages[files[pending]['hash']] = bytes(bad)
                    # Unmanaged sibling must never be adopted or silently removed.
                    stages['cold-unmanaged.tmp'] = b'owned unrelated staged sibling\n'
                    for h, data in stages.items(): (stage / h).write_bytes(data)
                    (meta / 'ingame/manifest.json').write_bytes(signed)
                    original = json.dumps(journal(files, paths, manifest['version'], 1)).encode()
                    authority = meta / 'ingame/journal.json'; authority.write_bytes(original)
                    for p in ('cold-unmanaged.tmp', 'ingame/cold-unmanaged.tmp'):
                        (meta / p).write_bytes(b'owned unrelated metadata sibling\n')
                    seed_metadata = inventory(meta)
                    metadata_grade(meta, metadata_expected(seed_metadata, ledger, stages,
                                   authority=original, launched=False))
                    snapshot(dest, case / 'seed')
                    lock_receipt = {}
                    if mode == 'source-lock':
                        with source_lock(meta / 'ingame/journal.tmp', lock_receipt):
                            cold_phase(engine, dest, case / 'fault', REWRITE_ERROR)
                        (case / 'source-probe.json').write_text(json.dumps(lock_receipt, indent=2))
                    else:
                        interrupt(engine, helper, binding, dest, case / 'fault',
                                  'crash-after' if mode == 'exhaustion' else mode)
                    expected[resolved] = payload[resolved]
                    ledger['files'][resolved] = files[resolved]['hash']
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                    committed = mode in ('none', 'crash-after', 'exhaustion')
                    native = authority if committed else meta / 'ingame/journal.tmp'
                    native_bytes = native.read_bytes()
                    rejected = authority_grade(json.loads(native_bytes), files, paths,
                        manifest['version'], 2, a.expect_before, pending)
                    if not committed:
                        assert authority.read_bytes() == original, 'unpublished original authority changed'
                    else:
                        assert not (meta / 'ingame/journal.tmp').exists()
                    partial_stages = copy.deepcopy(stages)
                    if mode == 'none':
                        del partial_stages[files[resolved]['hash']]
                    stages_grade(dest, partial_stages)
                    published = journal(files, [pending] if a.expect_before else paths, manifest['version'], 2)
                    metadata_grade(meta, metadata_expected(seed_metadata, ledger, partial_stages,
                        authority=published if committed else original,
                        temp=None if committed else published))
                    (case / 'publication-oracle.json').write_text(json.dumps(dict(status='PASS',
                        native_authority_sha256=sha(native_bytes), legacy_full_oracle_rejected=rejected,
                        committed=committed, attempts=2, stages={h:sha(b) for h,b in partial_stages.items()}), indent=2))
                    if mode == 'exhaustion':
                        # The native next admission alone spends3; never patch authority.
                        cold_phase(engine, dest, case / 'still-corrupt', PENDING_ERROR)
                        grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                        debit = authority.read_bytes()
                        authority_grade(json.loads(debit), files, paths, manifest['version'],
                                        3, a.expect_before, pending)
                        assert not (meta / 'ingame/journal.tmp').exists()
                        exhausted_stages = copy.deepcopy(stages)
                        if not a.expect_before:
                            del exhausted_stages[files[resolved]['hash']]
                        stages_grade(dest, exhausted_stages)
                        metadata_grade(meta, metadata_expected(seed_metadata, ledger, exhausted_stages,
                            authority=journal(files, [pending] if a.expect_before else paths, manifest['version'], 3)))
                        # Capture exact bytes only AFTER independent namespace/semantic validation.
                        exhausted_metadata = inventory(meta)
                        # Stage-only repair cannot reset content budget or install pending.
                        (stage / files[pending]['hash']).write_bytes(payload[pending])
                        exhausted_stages[files[pending]['hash']] = payload[pending]
                        exhausted_metadata['ingame/staged/' + files[pending]['hash']] = payload[pending]
                        ledger_bytes = (meta / 'state.json').read_bytes()
                        (case / 'stage-only-repair.json').write_text(json.dumps(dict(path=pending,
                            sha256=sha(payload[pending]), attempts=3, authority_sha256=sha(debit))))
                        exhaustion_grade(dest, meta, expected, ledger, signed, manifest['version'],
                                         debit, ledger_bytes, exhausted_stages, exhausted_metadata)
                        cold_phase(engine, dest, case / 'exhausted-stage-repaired', EXHAUSTED)
                        exhaustion_grade(dest, meta, expected, ledger, signed, manifest['version'],
                                         debit, ledger_bytes, exhausted_stages, exhausted_metadata)
                        (case / 'exhaustion-oracle.json').write_text(json.dumps(dict(status='PASS',
                            attempts=3, authority_sha256=sha(debit), ledger_sha256=sha(ledger_bytes),
                            legacy_reduction=a.expect_before, pending_still_old=True,
                            stages={h:sha(b) for h,b in exhausted_stages.items()}), indent=2))
                        snapshot(dest, case / 'final')
                        result['cases'].append(name)
                        print('PASS cold-superset', name, 'before' if a.expect_before else 'subject', flush=True)
                        continue
                    # Repair object only; never replace native authority or temp.
                    (stage / files[pending]['hash']).write_bytes(payload[pending])
                    (case / 'repair-input.json').write_text(json.dumps(dict(path=pending,
                        sha256=sha(payload[pending]), authority_unchanged=True)))
                    cold_phase(engine, dest, case / 'repair')
                    expected[pending] = payload[pending]
                    complete_ledger = copy.deepcopy(ledger)
                    complete_ledger['version'] = manifest['version']
                    complete_ledger['files'][pending] = files[pending]['hash']
                    grade_state(dest, meta, expected, complete_ledger, signed, manifest['version'], True)
                    assert not authority.exists()
                    temp = meta / 'ingame/journal.tmp'
                    if a.expect_before and not committed:
                        assert temp.read_bytes() == native_bytes, 'legacy failed-temp exact lifecycle'
                    else:
                        assert not temp.exists(), 'successful cleanup must discharge failed temp'
                    survivors = {'cold-unmanaged.tmp': stages['cold-unmanaged.tmp']}
                    if a.expect_before and mode == 'crash-after':
                        survivors[files[resolved]['hash']] = payload[resolved]
                    stages_grade(dest, survivors)
                    metadata_grade(meta, metadata_expected(seed_metadata, complete_ledger, survivors,
                        temp=native_bytes if a.expect_before and not committed else None, installed=signed))
                    snapshot(dest, case / 'final')
                    result['cases'].append(name)
                    print('PASS cold-superset', name, 'before' if a.expect_before else 'subject', flush=True)
        result['signed_mirror_http_joined'] = dict(hits)
        assert not hits, 'cold startup unexpectedly fetched signed mirror objects'
        assert {str(p):sha(p.read_bytes()) for p in sources} == hashes, 'source freeze changed'
        assert sha(engine.read_bytes()) == binding['engine_sha256']
        assert sha(symbols.read_bytes()) == binding['symbols_sha256'] and sha(helper.read_bytes()) == helper_hash
        ensure_retirable()
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        result['signed_mirror_http_joined'] = dict(hits)
        result['runtime_retired'] = False
        result['retention'] = str(root) + ': retain for independent review; no failure relabel or blanket cleanup'
        result['unconfirmed_guards'] = [str(p) for p in __import__('test_update_native_journal').UNCONFIRMED_PHASES]
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
