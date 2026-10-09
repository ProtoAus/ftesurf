#!/usr/bin/env python3
"""Bounded native back-slab NON-equivalence diagnostic; support remains ABSTAIN.

Full native BIH queries are measured against analytic fixture results and a
separate ideal finite-prism SAT answer. Native miss is NOT a prism-clear proof.
This is setup-only small-AABB evidence, not a new PM trajectory or product fix.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from offramp_buffer import require
from offramp_motion import LABELS, close, numbers
from offramp_origin import integers
from offramp_triangle import sweep
from offramp_tricopy import compare as copy_compare
from offramp_trislab_smoke import source_digest

ROOT = Path(__file__).resolve().parent.parent
VERTICES = [[-100, -100, 0], [0, 100, 0], [100, -100, 0]]
MINS, MAXS = [-.5]*3, [.5]*3
LABELS_QUERY = ('front', 'back-axial', 'short-back', 'stationary-back-slab', 'stationary-face', 'outside')
Z = ((6, -6), (-6, 2), (-6, -2), (-2, -2), (0, 0), (0, 0))
WIDTHS = dict(BEGIN=2, SOURCE=1, FIXTURE=18, QUERY=21, END=1)


def parse(text):
    rows = []
    for line in text.splitlines():
        pos = line.find('OFFRAMPTRISLAB_')
        if pos < 0:
            continue
        words = line[pos:].split()
        tag = words[0].removeprefix('OFFRAMPTRISLAB_')
        require(tag in WIDTHS and len(words)-1 == WIDTHS[tag], 'unknown/malformed back-slab row')
        rows.append((tag, words[1:]))
    return rows


def query(row, ordinal, vertices=VERTICES, mins=MINS, maxs=MAXS):
    require(len(row) == 21, 'back-slab query arity')
    row = numbers(row)
    # Reject fractional flags/indexes even where tolerant fraction checks apply.
    integers([str(row[i]) for i in (0, 1, 10, 11, 12, 17, 18, 19, 20)])
    c, active = (ordinal-1) % 6, (ordinal-1) % 12 < 6
    x = 150 if c == 5 else 0
    start, end = [x, 0, Z[c][0]], [x, 0, Z[c][1]]
    require(row[:8] == [ordinal, int(active), *start, *end], 'back-slab query/input/removal binding differs')
    require(vertices == VERTICES and mins == MINS and maxs == MAXS, 'back-slab authored fixture/hull drift')
    ideal = sweep(vertices, start, end, mins, maxs)
    # Analytic NATIVE expectation is intentionally distinct from ideal SAT.
    # Source's axial extents use the original triangle, not extruded back xyz.
    expected = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, -1, 0, 0]
    if active and c in (0, 1):
        speed, enter, normal, tag = (12, 5.5/12, 1, 0) if c == 0 else (8, 5.5/8, -1, 105)
        expected = [enter-(1/32)/speed, enter, 0, 0, 1, 0, 0, normal, 0, 2, 1, 1, tag]
    elif active and c == 4:
        expected = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, -1, 0, 0]
    require(close(row[8:10], expected[:2], 1e-7) and row[10:] == expected[2:], 'back-slab measured native semantics differ')
    native_intersects = row[8] < 1 or bool(row[10] or row[11])
    differs = active and (native_intersects != ideal['intersects'] or
                          (c == 1 and abs(row[9]-ideal['enter']) > 1e-7))
    require(differs == (active and c in (1, 2, 3)), 'back-slab non-equivalence did not ACT')
    return dict(label=LABELS_QUERY[c], active=active, native_intersects=native_intersects,
                native_fraction=row[8], native_truefraction=row[9], native_plane=row[13:17],
                native_origin_status=row[17:21], differs_from_ideal_prism=differs,
                geometry_basis='AUTHORED_SETUP_WIRING_NOT_ACCEPTED_COPY', ideal_prism=ideal)


def decode(text):
    rows = parse(text)
    header = [('BEGIN', ['1', '24']), ('SOURCE', [source_digest()])]
    require(len(rows) == 28 and rows[:2] == header and rows[2][0] == 'FIXTURE' and
            rows[-1] == ('END', ['24']), 'back-slab missing/reordered/source/count envelope')
    fixture = numbers(rows[2][1])
    require(fixture == [0, 1, 2, *(x for v in VERTICES for x in v), *MINS, *MAXS], 'back-slab geometry/hull/index fixture differs')
    queries = []
    values = []
    for i, (tag, words) in enumerate(rows[3:-1], 1):
        require(tag == 'QUERY', 'back-slab reordered query')
        queries.append(query(words, i))
        values.append(numbers(words))
    require([r[1:] for r in values[:12]] == [r[1:] for r in values[12:]], 'back-slab local repeat differs')
    return queries


def grade(text):
    blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', text, flags=re.S)
    require(len(blocks) == len(LABELS) and len(parse(text)) == sum(len(parse(b)) for b in blocks),
            'back-slab rows outside twenty native case envelopes')
    cases = [decode(block) for block in blocks]
    require(all(case == cases[0] for case in cases), 'back-slab setup differs across restored mover cases')
    return dict(native_queries_per_setup=24, native_setup_calls=len(cases), native_queries=24*len(cases),
                unique_present_queries=cases[0][:6], unique_removed_queries=cases[0][6:12],
                measured_native_vs_ideal='NON_EQUIVALENT_BACK_SLAB', source=source_digest(),
                local_repeat='PASS', all_case_setup_repeat='PASS', general_triangle_support='ABSTAIN',
                physical_exit_acceptance='NOT_TESTED', new_mover_actor='NONE')


def compare(*texts):
    require(len(texts) == 5 and not any(parse(t) for t in texts[:3]), 'fixture-only/OFF back-slab rows not quiet')
    original = copy_compare(*texts)
    result = grade(texts[3])
    require(result == grade(texts[4]), 'back-slab runtime repeat differs')
    result.update(five_arm_original_motion_copy_parity='PASS', runtime_repeat='PASS',
                  original_motion_body_oracle_sha256=original['original_motion_body_oracle_sha256'])
    return result


def load_arms(path):
    arms = json.loads(path.read_text())
    names = ('nooracle', 'control', 'off', 'on', 'repeat')
    require(set(arms) == set(names) and all(a['exit_code'] == 0 for a in arms.values()), 'missing/failed back-slab native arm')
    require(arms['control']['server_sha256'] == arms['nooracle']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1 and
            len({a['fixture_sha256'] for a in arms.values()}) == len({a['manifest_sha256'] for a in arms.values()}) == 1,
            'back-slab arm provenance differs')
    texts = []
    hashes = {}
    for n in names:
        a = arms[n]
        rig = Path(a['rig'])
        for file, key in ((rig/'fteqwsv64.exe', 'server_sha256'), (rig/'ftesurf/cfg/test/motion.cfg', 'cfg_sha256'),
                          (rig/'default.fmf', 'manifest_sha256')):
            require(hashlib.sha256(file.read_bytes()).hexdigest() == a[key], 'back-slab retained binary/config/manifest changed')
        require(hashlib.sha256((ROOT/'tools/offramp_motion_native.inc').read_bytes()).hexdigest() == a['fixture_sha256'],
                'back-slab unchanged motion source drift')
        data = Path(a['log']).read_bytes()
        hashes[n] = hashlib.sha256(data).hexdigest()
        texts.append(data.decode(errors='replace'))
    return texts, dict(manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), log_sha256=hashes,
                      binary_sha256={n:arms[n]['server_sha256'] for n in names})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'back-slab report needs NEW path')
    texts, provenance = load_arms(a.arms)
    result = compare(*texts)
    result['provenance'] = provenance
    with a.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print('Bounded full native back-slab queries ACT NON-equivalence; original mover/copy parity PASS; support ABSTAIN')


if __name__ == '__main__':
    main()
