#!/usr/bin/env python3
"""Bounded copied-winning front-edge/bevel diagnostic; general support ABSTAIN.

Full BIH setup calls, NOT PM trajectories. Independent ideal finite-prism SAT
checks only the registered front region; native back-slab NON-equivalence stays.
Bevel-OFF earlier contact/false solid is measured, not promoted as real geometry.
"""
import argparse
import json
import math
from pathlib import Path
import re

from offramp_buffer import require
from offramp_motion import LABELS, close, numbers
from offramp_origin import integers
from offramp_triangle import NATIVE_BIAS, SPATIAL_TOLERANCE, dot, sub, sweep
from offramp_tribev_smoke import source_digest
from offramp_trislab import compare as slab_compare, load_arms

VERTICES = [[0, 0, 0], [0, 4, -4], [4, 0, -4]]
MINS, MAXS = [-.5]*3, [.5]*3
QUERY_LABELS = ('face-reference', 'bevel-edge', 'ghost-stationary', 'occupied-edge', 'outside')
ENDPOINTS = (([1, 1, 2], [1, 1, -2]), ([-.25, 2, 0], [-.25, 2, -2]),
             ([-.25, 2, -.75], [-.25, 2, -.75]), ([-.25, 2, -2], [-.25, 2, -2]), ([6]*3, [6]*3))
WIDTHS = dict(BEGIN=2, SOURCE=1, FIXTURE=18, QUERY=23, COPY=17, END=1)


def parse(text):
    rows = []
    for line in text.splitlines():
        position = line.find('OFFRAMPTRIBEV_')
        if position < 0:
            continue
        words = line[position:].split()
        tag = words[0].removeprefix('OFFRAMPTRIBEV_')
        require(tag in WIDTHS and len(words)-1 == WIDTHS[tag], 'unknown/malformed front-edge/bevel row')
        rows.append((tag, words[1:]))
    return rows


def fixture(words):
    values = numbers(words)
    require(values == [0, 1, 2, *(x for v in VERTICES for x in v), *MINS, *MAXS],
            'front-edge/bevel authored fixture/index/hull differs')


def expected(ordinal):
    """Hand-derived registered results; NOT a port of native clipping."""
    c, mode = (ordinal-1) % 5, ((ordinal-1) % 15)//5
    active, bevels = mode != 2, mode != 1
    start, end = ENDPOINTS[c]
    result = [1, 1, 0, 0, 0, *([0]*4), 0, -1, -1, 0, 0]
    copy = [ordinal, *([0]*16)]
    if active and c < 2:
        if c == 0:
            enter, normal, tag = 5/8, [1/math.sqrt(3)]*3, 0
        elif bevels:
            enter, normal, tag = 1/2, [0, 1/math.sqrt(2), 1/math.sqrt(2)], 5
        else:
            enter, normal, tag = 1/4, [-2/math.sqrt(6), 1/math.sqrt(6), 1/math.sqrt(6)], 2
        speed = abs(dot(sub(end, start), normal))
        result = [enter-NATIVE_BIAS/speed, enter, 0, 0, 1, *normal, 0, 2, 1, 1, 0, 1]
        copy = [ordinal, 1, tag, int(bevels), 4, 0, 1, 2, *(x for v in VERTICES for x in v)]
    elif active and (c == 3 or (c == 2 and not bevels)):
        result[2:5] = [1, 1, 1]
    return [ordinal, int(active), int(bevels), *start, *end, *result], copy


def query(words, copied, ordinal):
    require(len(words) == 23 and len(copied) == 17, 'front-edge/bevel query/copy arity')
    row, copy = numbers(words), numbers(copied)
    integers([words[i] for i in (0, 1, 2, 11, 12, 13, 18, 19, 20, 21, 22)])
    integers([copied[i] for i in (0, 1, 2, 3, 5, 6, 7)])
    want, wantcopy = expected(ordinal)
    require(row[:9] == want[:9], 'front-edge/bevel query/input/mode binding differs')
    require(close(row[9:11], want[9:11], 1e-7) and row[11:14] == want[11:14] and
            close(row[14:18], want[14:18], 1e-6) and row[18:] == want[18:],
            'front-edge/bevel measured native fraction/plane/flags/ownership differs')
    require(copy == wantcopy, 'front-edge/bevel copied winning xyz/index/tag/slab/empty binding differs')
    c, active, bevels = (ordinal-1) % 5, bool(row[1]), bool(row[2])
    native_hit, native_solid = row[9] < 1, bool(row[11] or row[12])
    vertices = [copy[i:i+3] for i in (8, 11, 14)] if native_hit else VERTICES
    ideal = sweep(vertices, row[3:6], row[6:9], MINS, MAXS, copy[4] if native_hit else 4)
    # This fixture's original-triangle axial clipping is satisfied at contact.
    # Do not extend the result to the whole extruded back slab or arbitrary hulls.
    if active and c < 4:
        t = row[10] if native_hit else 0
        position = [s+t*(e-s) for s, e in zip(row[3:6], row[6:9])]
        require(all(min(v[i] for v in VERTICES)-MAXS[i] <= position[i] <=
                    max(v[i] for v in VERTICES)-MINS[i] for i in range(3)),
                'front-region original axial bounds not satisfied')
    agrees = native_hit == ideal['intersects'] if c < 2 else native_solid == ideal['starts_penetrating']
    if active and native_hit and (bevels or c == 0):
        require(ideal['intersects'] and not ideal['starts_overlap'] and len(ideal['entry_planes']) == 1,
                'copied-winning bounded front SAT did not ACT unique clear-start entry')
        plane = ideal['entry_planes'][0]
        require(close(plane[:3], row[14:17], 1e-5) and abs(plane[3]-row[17]) <= SPATIAL_TOLERANCE,
                'copied-winning bounded front SAT entry plane differs')
        speed = abs(dot(sub(row[6:9], row[3:6]), plane[:3]))
        require(speed > 1e-9 and abs(row[10]-ideal['enter'])*speed <= SPATIAL_TOLERANCE and
                abs(row[9]-max(0, ideal['enter']-NATIVE_BIAS/speed))*speed <= SPATIAL_TOLERANCE,
                'copied-winning bounded front SAT truefraction/bias differs')
    if active and c == 1 and not bevels:
        require(ideal['enter'] == .5 and row[10] < ideal['enter']-.2,
                'bevel-disabled earlier ghost contact did not ACT')
        agrees = False
    if active:
        require(agrees == (bevels or c not in (1, 2)), 'bevel ON/OFF geometry difference did not ACT')
    else:
        require(not native_hit and not native_solid, 'removed native triangle not clear')
    return dict(label=QUERY_LABELS[c], active=active, bevels=bevels,
                native_fraction=row[9], native_truefraction=row[10], native_plane=row[14:18],
                native_solid=native_solid, native_hit=native_hit, origin=row[18:],
                copied_winner=copy[1:], geometry_basis='COPIED_WINNING_NATIVE_TRIANGLE' if native_hit else
                'AUTHORED_SETUP_WIRING'+('' if active else '_INACTIVE_HYPOTHETICAL'),
                agrees_with_ideal_prism=agrees if active else None, ideal_prism=ideal)


def decode(text):
    rows = parse(text)
    require(len(rows) == 64 and rows[:2] == [('BEGIN', ['1', '30']), ('SOURCE', [source_digest()])] and
            rows[2][0] == 'FIXTURE' and rows[-1] == ('END', ['30']),
            'front-edge/bevel missing/reordered/source/count envelope')
    fixture(rows[2][1])
    result, values = [], []
    for i in range(30):
        q, c = rows[3+2*i:5+2*i]
        require(q[0] == 'QUERY' and c[0] == 'COPY', 'front-edge/bevel reordered query/copy')
        result.append(query(q[1], c[1], i+1))
        values.append((numbers(q[1])[1:], numbers(c[1])[1:]))
    require(values[:15] == values[15:], 'front-edge/bevel local repeat differs')
    return result


def grade(text):
    blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', text, flags=re.S)
    require(len(blocks) == len(LABELS) and len(parse(text)) == sum(len(parse(b)) for b in blocks),
            'front-edge/bevel rows outside twenty native case envelopes')
    cases = [decode(block) for block in blocks]
    require(all(case == cases[0] for case in cases), 'restored front-edge/bevel setup differs across cases')
    return dict(native_queries_per_setup=30, native_setup_calls=len(cases), native_queries=30*len(cases),
                copied_setup_winners=8*len(cases), bevel_winners=2*len(cases),
                unique_on_queries=cases[0][:5], unique_off_queries=cases[0][5:10],
                unique_removed_queries=cases[0][10:15], source=source_digest(),
                bounded_copied_front_entry_and_bias='PASS', bevel_disabled_geometry_difference='ACTED',
                local_repeat='PASS', all_case_setup_repeat='PASS', general_triangle_support='ABSTAIN',
                general_native_triangle_semantics='NOT_VERIFIED', physical_exit_acceptance='NOT_TESTED', new_mover_actor='NONE')


def compare(*texts):
    require(len(texts) == 5 and not any(parse(t) for t in texts[:3]), 'fixture-only/OFF front-edge/bevel rows not quiet')
    prior = slab_compare(*texts)
    result = grade(texts[3])
    require(result == grade(texts[4]), 'front-edge/bevel runtime repeat differs')
    result.update(five_arm_original_motion_copy_slab_parity='PASS', runtime_repeat='PASS',
                  original_motion_body_oracle_sha256=prior['original_motion_body_oracle_sha256'])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'front-edge/bevel report needs NEW path')
    texts, provenance = load_arms(a.arms)
    result = compare(*texts)
    result['provenance'] = provenance
    with a.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print('Bounded copied-winning front-edge/bevel entry+bias PASS; bevel-OFF ghosts ACT; original actor exact; support ABSTAIN')


if __name__ == '__main__':
    main()
