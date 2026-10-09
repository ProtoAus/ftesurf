#!/usr/bin/env python3
"""Independent authored triangle/slab SAT diagnostic; NEVER support acceptance.

The vertices come from fixture wiring, not an accepted copied triangle. Native
tracing has its own bias/axial/broadphase semantics; only the bounded retained
standing-AABB actor is compared. No native plane or fraction drives the oracle.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from offramp_buffer import require
from offramp_motion import LABELS, TRIANGLE_VERTICES, close, compare

SPATIAL_TOLERANCE = 2e-4
NATIVE_BIAS = 1 / 32


def dot(a, b):
    value = sum(x*y for x, y in zip(a, b))
    require(math.isfinite(value), 'nonfinite SAT projection')
    return value


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def vector(v):
    require(len(v) == 3 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v),
            'invalid/nonfinite SAT vector')
    return list(v)


def prism(vertices, thickness=4):
    """Documented solid-side winding; return six independent geometric vertices."""
    require(len(vertices) == 3 and math.isfinite(thickness) and thickness > 0,
            'invalid triangle/slab thickness')
    vs = [vector(v) for v in vertices]
    n = cross(sub(vs[0], vs[1]), sub(vs[2], vs[1]))
    length = math.sqrt(dot(n, n))
    require(math.isfinite(length) and length > 1e-9, 'degenerate/nonfinite triangle')
    n = [x/length for x in n]
    return vs + [[x-thickness*y for x, y in zip(v, n)] for v in vs], n


def separating_axes(vertices, normal):
    """Complete prism/AABB SAT: face normals and both shapes' edge crosses."""
    xyz = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    edges = [sub(vertices[(i+1) % 3], vertices[i]) for i in range(3)]
    candidates = xyz + [normal] + [cross(e, normal) for e in edges]
    candidates += [cross(e, a) for e in edges+[normal] for a in xyz]
    axes = []
    for n in candidates:
        length = math.sqrt(dot(n, n))
        if length <= 1e-9:
            continue
        n = [x/length for x in n]
        # Interval tests use BOTH signs. Canonicalization only deduplicates.
        first = next(x for x in n if abs(x) > 1e-9)
        if first < 0:
            n = [-x for x in n]
        if not any(close(n, a, 1e-9) for a in axes):
            axes.append(n)
    return axes


def sweep(vertices, start, end, mins, maxs, thickness=4):
    """Exact closed interval of translating AABB/finite prism intersection.

    No epsilon expansion or native trace reproduction. Touching counts as a
    geometric intersection; starts_penetrating distinguishes strict overlap.
    Entry planes are derived from vertex projections, not native trace output.
    """
    points, normal = prism(vertices, thickness)
    start, end, mins, maxs = map(vector, (start, end, mins, maxs))
    require(all(lo < hi for lo, hi in zip(mins, maxs)), 'inverted/zero-volume SAT hull')
    axes = separating_axes(points[:3], normal)
    delta = sub(end, start)
    lower, upper, entering = -math.inf, math.inf, []
    starts_overlap, starts_penetrating = True, True
    for axis in axes:
        plo, phi = min(dot(p, axis) for p in points), max(dot(p, axis) for p in points)
        blo = dot(start, axis) + sum(n*(lo if n >= 0 else hi) for n, lo, hi in zip(axis, mins, maxs))
        bhi = dot(start, axis) + sum(n*(hi if n >= 0 else lo) for n, lo, hi in zip(axis, mins, maxs))
        require(math.isfinite(blo) and math.isfinite(bhi), 'nonfinite SAT hull projection')
        starts_overlap = starts_overlap and blo <= phi+1e-9 and bhi >= plo-1e-9
        starts_penetrating = starts_penetrating and blo < phi-1e-9 and bhi > plo+1e-9
        velocity = dot(delta, axis)
        if abs(velocity) <= 1e-12:
            if blo > phi+1e-9 or bhi < plo-1e-9:
                return dict(intersects=False, starts_overlap=False, starts_penetrating=False,
                            enter=None, leave=None, entry_planes=[], axes=len(axes))
            continue
        if velocity > 0:
            lo, hi = (plo-bhi)/velocity, (phi-blo)/velocity
            plane = [-x for x in axis]+[-plo]
        else:
            lo, hi = (phi-blo)/velocity, (plo-bhi)/velocity
            plane = axis+[phi]
        if lo > lower+1e-9:
            lower, entering = lo, [plane]
        elif abs(lo-lower) <= 1e-9:
            entering.append(plane)
        upper = min(upper, hi)
    intersects = lower <= upper+1e-9 and upper >= -1e-9 and lower <= 1+1e-9
    return dict(intersects=intersects, starts_overlap=starts_overlap, starts_penetrating=starts_penetrating,
                enter=max(0, lower) if intersects else None, leave=min(1, upper) if intersects else None,
                entry_planes=entering if intersects and lower >= 0 else [], axes=len(axes))


def native_query(row, tick, vertices, active):
    """Compare independent geometry only for the fixed clear-body fixture scope."""
    require(len(row) == 19 and len(tick) == 28 and
            all(isinstance(x, (int, float)) and math.isfinite(x) for x in row[:2]+row[4:]+tick),
            'invalid/nonfinite triangle diagnostic row')
    require(row[:2] == tick[:2] and tick[0] in (14, 15) and
            row[2:4] in (['stationary', -1], ['down2', -1], ['untriangled', 0]) and
            tick[16:28] == [-16, -16, 0, 16, 16, 62, 0, 0, 0, 0, 0, 0],
            'unsupported triangle query/hull/posture actor')
    require(row[4:7] == tick[10:13] and row[7:9] == tick[10:12] and close(row[9:10],
            [tick[12]-(2 if row[2] != 'stationary' else 0)], SPATIAL_TOLERANCE),
            'triangle query/body endpoints differ')
    require(vertices == [TRIANGLE_VERTICES[i:i+3] for i in range(0, 9, 3)],
            'triangle oracle not bound to authored fixture wiring')
    require(active == (tick[0] == 14 and row[2] != 'untriangled'), 'triangle active/removal binding differs')
    geometry = sweep(vertices, row[4:7], row[7:10], tick[16:19], tick[19:22])
    if active:
        require(not geometry['starts_overlap'], 'triangle diagnostic starts embedded/touching; unsupported')
    if not active or not geometry['intersects']:
        require(row[10:14] == [1, 0, 0, -1] and row[14:19] == [0]*5,
                'triangle native miss/removal differs from independent SAT')
    else:
        require(row[11:14] == [0, 0, 0] and row[18] == 1 and 0 <= row[10] < 1,
                'triangle native hit flags/contents differ')
        delta = sub(row[7:10], row[4:7])
        matches = [p for p in geometry['entry_planes'] if close(row[14:17], p[:3], 1e-5) and
                   abs(row[17]-p[3]) <= SPATIAL_TOLERANCE]
        require(matches, 'triangle native plane differs from independent SAT entry')
        # Native clipping intentionally stops 1/32 before exact geometry. Check
        # in spatial units, independent of sweep length or recorded fraction.
        speed = abs(dot(delta, matches[0][:3]))
        require(speed > 1e-9 and abs((geometry['enter']-row[10])*speed-NATIVE_BIAS) <= SPATIAL_TOLERANCE,
                'triangle native fraction differs from independent SAT/bias')
    return dict(query=row[2], active=active, native_hit=row[10] < 1 or bool(row[11] or row[12]),
                geometry_basis='AUTHORED_WIRING_NOT_COPIED_ACCEPTED_TRIANGLE', **geometry)


def assess(present, removed):
    require(present['label'] == LABELS[14] and removed['label'] == LABELS[15] and
            present['seed'] == removed['seed'] and
            all(len(c['ticks']) == len(c['oracles']) == 32 for c in (present, removed)),
            'missing matched native triangle/removal actor')
    vertices = [TRIANGLE_VERTICES[i:i+3] for i in range(0, 9, 3)]
    results = []
    for index, c in enumerate((present, removed)):
        require(close([float(x) for x in c['triangle'][6:]], TRIANGLE_VERTICES, 1e-4),
                'native triangle wiring differs')
        ticks = []
        for tick, queries in zip(c['ticks'], c['oracles']):
            require([q[2:4] for q in queries] == [['stationary', -1], ['down2', -1], ['untriangled', 0]],
                    'missing/reordered triangle native queries')
            ticks.append([native_query(q, tick, vertices, index == 0 and q[2] != 'untriangled') for q in queries])
        results.append(dict(label=c['label'], queries=ticks))
    hits = [i for i, qs in enumerate(results[0]['queries']) if qs[1]['native_hit']]
    misses = [i for i, qs in enumerate(results[0]['queries']) if not qs[1]['native_hit']]
    counterfactual = [i for i, qs in enumerate(results[1]['queries']) if qs[1]['intersects']]
    require(hits and misses and min(hits) < max(misses) and counterfactual and
            all(not qs[0]['native_hit'] and not qs[2]['native_hit'] for c in results for qs in c['queries']),
            'independent triangle hit/miss/removal counterfactual did not ACT')
    return dict(bounded_triangle_query_sat_gates='PASS', native_down2_hit_ticks=hits,
                native_down2_miss_ticks=misses, removed_inactive_triangle_intersection_ticks=counterfactual,
                cases=results, triangle_support_geometry_acceptance='ABSTAIN',
                geometry_basis='AUTHORED_WIRING_NOT_COPIED_ACCEPTED_TRIANGLE',
                general_native_triangle_semantics='NOT_TESTED', physical_exit_acceptance='NOT_TESTED')


def compare_triangle(*texts):
    motion = compare(*texts)
    result = assess(*motion['cases'][14:16])
    result.update(source=motion['source'], motion_body_oracle_sha256=motion['body_oracle_sha256'],
                  five_arm_motion_parity='PASS', repeat_capture_binding='PASS')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'triangle report needs NEW path')
    arms = json.loads(a.arms.read_text())
    names = ('nooracle', 'control', 'off', 'on', 'repeat')
    require(set(arms) == set(names) and all(r['exit_code'] == 0 for r in arms.values()), 'missing/failed triangle native arm')
    require(arms['control']['server_sha256'] == arms['nooracle']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1 and
            len({r['fixture_sha256'] for r in arms.values()}) == len({r['manifest_sha256'] for r in arms.values()}) == 1,
            'triangle native control/subject provenance differs')
    for r in arms.values():
        for relative, key in (('fteqwsv64.exe', 'server_sha256'), ('default.fmf', 'manifest_sha256'),
                              ('ftesurf/cfg/test/motion.cfg', 'cfg_sha256')):
            require(hashlib.sha256((Path(r['rig'])/relative).read_bytes()).hexdigest() == r[key],
                    'retained triangle native binary/manifest/cfg differs')
    texts = [Path(arms[n]['log']).read_text(errors='replace') for n in names]
    result = compare_triangle(*texts)
    require(result['source'][0] == arms['on']['fixture_sha256'] ==
            hashlib.sha256(Path(__file__).with_name('offramp_motion_native.inc').read_bytes()).hexdigest(),
            'retained native triangle fixture stamp differs')
    result['arms_file_sha256'] = hashlib.sha256(a.arms.read_bytes()).hexdigest()
    result['log_sha256'] = {n: hashlib.sha256(Path(arms[n]['log']).read_bytes()).hexdigest() for n in names}
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('Independent authored triangle/slab SAT: bounded native queries PASS; five-arm retained parity PASS')
    print('Copied triangle/general native semantics/physical off-ramp acceptance: ABSTAIN or NOT_TESTED')


if __name__ == '__main__':
    main()
