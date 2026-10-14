#!/usr/bin/env python3
"""Full-original-row first QKU_Apply publication extension; immutable native actor."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path

from test_update_native_journal import preflight_paths, sha, snapshot, ensure_retirable, PENDING_ERROR
from test_update_native_journal_initial import bind_initial, live, cold_phase
from test_update_native_journal_interrupt import EXHAUSTED
from test_update_native_journal_deferred import helper_identity
from test_update_native_publication_superset import (BEFORE, SUBJECT, prepare, grade_state,
    full_authority, mirror_server)
from test_update_native_retirement_windows import inventory
from test_update_native_staging_windows import load_inputs, journal


def initial_namespace(meta, signed, stages, authority=None, temp=None):
    expected = {'manifest.json': signed}
    expected.update({'staged/' + h: data for h, data in stages.items()})
    if authority is not None:
        expected['journal.json'] = authority
    if temp is not None:
        expected['journal.tmp'] = temp
    assert inventory(meta / 'ingame') == expected, 'exact initial authority/temp/full-stage namespace mismatch'


def partial_authority(actual, files, paths, pending, version, before, attempts=2):
    expected = journal(files, [pending] if before else paths, version, attempts)
    assert actual == expected, 'partial replay original rows/attempts/version mismatch'
    rejected = False
    try:
        full_authority(actual, files, paths, version, attempts)
    except AssertionError:
        assert before
        rejected = True
    assert rejected == before, 'legacy reduction control failed to discriminate'
    return rejected


def exhaust_initial(engine, dest, meta, case, expected, ledger, signed, files, paths,
                    pending, version, before, stages, payload):
    authority = meta / 'ingame/journal.json'
    cold_phase(engine, dest, case / 'cold-corrupt-attempt3', error=PENDING_ERROR)
    grade_state(dest, meta, expected, ledger, signed, version)
    partial_authority(json.loads(authority.read_bytes()), files, paths, pending, version, before, 3)
    initial_namespace(meta, signed, stages, authority=authority.read_bytes())
    snapshot(dest, case / 'debit3')
    for repair in (False, True):
        if repair:
            # Repair only signed stage input, never native authority or destination.
            (meta / 'ingame/staged' / files[pending]['hash']).write_bytes(payload[pending])
            stages[files[pending]['hash']] = payload[pending]
        frozen = inventory(meta)
        cold_phase(engine, dest, case / ('cold-exhausted-stage-repaired' if repair else 'cold-exhausted'),
                   error=EXHAUSTED)
        assert inventory(meta) == frozen, 'exhausted startup mutated native metadata/stages'
        grade_state(dest, meta, expected, ledger, signed, version)
        partial_authority(json.loads(authority.read_bytes()), files, paths, pending, version, before, 3)
        initial_namespace(meta, signed, stages, authority=authority.read_bytes())
    (case / 'exhaustion-oracle.json').write_text(json.dumps(dict(status='PASS',
        native_debits=[1, 2, 3], ordinary_exhaustion_unchanged=True,
        signed_stage_repair_still_exhausted=True, authority_authored_by_harness=False), indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'symbols', 'helper', 'feed', 'runtime-root', 'evidence', 'serializer'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--objects', type=Path, action='append', required=True)
    ap.add_argument('--expect-before', action='store_true')
    ap.add_argument('--exhaustion-only', action='store_true', help='fresh bounded debit/exhaustion extension only')
    a = ap.parse_args()
    assert os.name == 'nt'
    engine, symbols = (p.resolve(strict=True) for p in (a.engine, a.symbols))
    assert sha(engine.read_bytes()) == (BEFORE if a.expect_before else SUBJECT)
    helper, helper_hash = helper_identity(a.helper)
    binding = bind_initial(engine, symbols, Path('C:/msys64/ucrt64/bin/nm.exe'), Path('C:/msys64/ucrt64/bin/objdump.exe'))
    assert binding['before'] is False, 'both clients must have P692 atomic initial publication'
    signed, manifest, files, payload = load_inputs(a.feed, a.objects)
    paths = [p for p in files if p in ('ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png')]
    assert len(paths) == 2 and files[paths[0]]['hash'] != files[paths[1]]['hash']
    root, evidence = preflight_paths(a.runtime_root, a.evidence)
    root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Owned initial-only synthetic fixtures; retained for independent review including failures.\n')
    sources = list(Path(__file__).parent.glob('test_update_native*.py')) + [Path(__file__), a.serializer,
        Path(__file__).with_name('native_journal_initial.c'), Path(__file__).with_name('updatefeed.py'),
        Path(__file__).with_name('test_update_handoff.py')]
    hashes = {str(p): sha(p.read_bytes()) for p in sources}
    result = dict(status='FAIL', binding=binding, helper_sha256=helper_hash, sources=hashes,
                  signed_sha256=sha(signed), signed_rows=len(manifest['files']), selected_rows=len(files),
                  objects=len({f['hash'] for f in manifest['files']}), exhaustion_only=a.exhaustion_only, cases=[])
    expected_http = Counter()
    hits = Counter()
    try:
        with mirror_server(manifest, signed, payload, files) as (hits, url):
            scenarios = ('crash-after-corrupt-exhaustion-first', 'crash-after-corrupt-exhaustion-last') if a.exhaustion_only else (
                'none', 'source-lock', 'crash-before', 'crash-after-repaired',
                'crash-after-corrupt-first', 'crash-after-corrupt-last')
            for name in scenarios:
                mode = 'crash-after' if name.startswith('crash-after') else name
                dest, meta, expected, ledger = prepare(root, name, payload, files, paths)
                case = evidence / name
                case.mkdir()
                snapshot(dest, case / 'seed')
                stages = {files[p]['hash']: payload[p] for p in paths}
                authority = meta / 'ingame/journal.json'
                temp = meta / 'ingame/journal.tmp'
                def inspect(unused):
                    # Active export excludes only the byte-locked install.lock; post-exit is full.
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                    raw = (case / 'live/initial-temp.json').read_bytes()
                    full_authority(json.loads(raw), files, paths, manifest['version'], 1)
                    initial_namespace(meta, signed, stages, temp=raw)
                    (case / 'source-lock-boundary.json').write_text(json.dumps(dict(status='PASS',
                        authority_absent=True, attempts=1, stages={h: sha(b) for h, b in stages.items()}), indent=2))
                live(engine, helper, binding, dest, case / 'live', mode, dict(url=url), inspect)
                count = 2 if mode == 'source-lock' else 1
                expected_http['/update.json'] += count
                for p in paths:
                    expected_http['/objects/' + files[p]['hash'][:2] + '/' + files[p]['hash']] += count
                raw = (case / 'live/initial-temp.json').read_bytes()
                full_authority(json.loads(raw), files, paths, manifest['version'], 1)
                rejected = False
                if mode.startswith('crash-'):
                    grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                    initial_namespace(meta, signed, stages, authority=raw if mode == 'crash-after' else None,
                                      temp=raw if mode == 'crash-before' else None)
                    if mode == 'crash-before':
                        cold_phase(engine, dest, case / 'cold-no-authority')
                        grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                        initial_namespace(meta, signed, stages, temp=raw)
                    else:
                        if 'corrupt' in name:
                            pending = paths[0] if name.endswith('first') else paths[-1]
                            content = next(p for p in paths if p != pending)
                            bad = bytes([payload[pending][0] ^ 1]) + payload[pending][1:]
                            assert len(bad) == files[pending]['size'] and sha(bad) != files[pending]['hash']
                            (meta / 'ingame/staged' / files[pending]['hash']).write_bytes(bad)
                            stages[files[pending]['hash']] = bad
                            cold_phase(engine, dest, case / 'cold-corrupt', error=PENDING_ERROR)
                            expected[content] = payload[content]
                            ledger['files'][content] = files[content]['hash']
                            grade_state(dest, meta, expected, ledger, signed, manifest['version'])
                            rejected = partial_authority(json.loads(authority.read_bytes()), files, paths,
                                                         pending, manifest['version'], a.expect_before)
                            del stages[files[content]['hash']]  # freshly installed by this cold pass, in both clients
                            initial_namespace(meta, signed, stages, authority=authority.read_bytes())
                            snapshot(dest, case / 'partial')
                            if a.exhaustion_only:
                                exhaust_initial(engine, dest, meta, case, expected, ledger, signed, files,
                                                paths, pending, manifest['version'], a.expect_before, stages, payload)
                            else:
                                (meta / 'ingame/staged' / files[pending]['hash']).write_bytes(payload[pending])
                        if not a.exhaustion_only:
                            cold_phase(engine, dest, case / 'cold-completion')
                if mode != 'crash-before' and not a.exhaustion_only:
                    expected.update({p: payload[p] for p in paths})
                    final_ledger = dict(version=manifest['version'], files={p: f['hash'] for p, f in files.items()})
                    grade_state(dest, meta, expected, final_ledger, signed, manifest['version'], True)
                    initial_namespace(meta, signed, {})
                snapshot(dest, case / 'final')
                (case / 'initial-oracle.json').write_text(json.dumps(dict(status='PASS', mode=mode,
                    original_attempt1_rows=True, legacy_partial_reduction_rejected=rejected), indent=2))
                result['cases'].append(name)
                print('PASS initial-superset', name, 'before' if a.expect_before else 'subject', flush=True)
        result['signed_mirror_http_joined'] = dict(hits)
        assert hits == expected_http, ('joined exact HTTP census', dict(hits), dict(expected_http))
        assert {str(p): sha(p.read_bytes()) for p in sources} == hashes, 'source freeze changed'
        assert sha(engine.read_bytes()) == binding['engine_sha256'] and sha(symbols.read_bytes()) == binding['symbols_sha256']
        assert sha(helper.read_bytes()) == helper_hash
        ensure_retirable()
        result['status'] = 'PASS'
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        result['signed_mirror_http_joined'] = dict(hits)
        result['expected_http'] = dict(expected_http)
        result['runtime_retired'] = False
        result['retention'] = str(root) + ': all fixtures retained for independent review; no failed-attempt cleanup'
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
