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
from test_update_native_journal_interrupt import bind_commit, interrupt
from test_update_native_journal_deferred import helper_identity
from test_update_native_publication_superset import (BEFORE, SUBJECT, prepare,
    grade_state, stage_map, full_authority, mirror_server)
from test_update_native_staging_windows import load_inputs, journal


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
                for mode in ('source-lock', 'crash-before', 'crash-after', 'none'):
                    name = position + '-' + mode
                    dest, meta, expected, ledger = prepare(root, name, payload, files, paths)
                    case = evidence / name; case.mkdir()
                    stage = meta / 'ingame/staged'; stage.mkdir(parents=True)
                    stages = {files[p]['hash']: payload[p] for p in paths}
                    bad = bytearray(payload[pending]); bad[0] ^= 1
                    assert len(bad) == files[pending]['size'] and sha(bad) != files[pending]['hash']
                    stages[files[pending]['hash']] = bytes(bad)
                    # Unmanaged sibling must never be adopted or silently removed.
                    stages['cold-unmanaged.tmp'] = b'owned unrelated staged sibling\n'
                    for h, data in stages.items(): (stage / h).write_bytes(data)
                    (meta / 'ingame/manifest.json').write_bytes(signed)
                    original = json.dumps(journal(files, paths, manifest['version'], 1)).encode()
                    authority = meta / 'ingame/journal.json'; authority.write_bytes(original)
                    snapshot(dest, case / 'seed')
                    lock_receipt = {}
                    if mode == 'source-lock':
                        with source_lock(meta / 'ingame/journal.tmp', lock_receipt):
                            cold_phase(engine, dest, case / 'fault', REWRITE_ERROR)
                        (case / 'source-probe.json').write_text(json.dumps(lock_receipt, indent=2))
                    else:
                        interrupt(engine, helper, binding, dest, case / 'fault', mode)
                    expected[resolved] = payload[resolved]
                    ledger['files'][resolved] = files[resolved]['hash']
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                    committed = mode in ('none', 'crash-after')
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
                    (case / 'publication-oracle.json').write_text(json.dumps(dict(status='PASS',
                        native_authority_sha256=sha(native_bytes), legacy_full_oracle_rejected=rejected,
                        committed=committed, attempts=2, stages={h:sha(b) for h,b in partial_stages.items()}), indent=2))
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
