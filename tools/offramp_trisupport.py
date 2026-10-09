#!/usr/bin/env python3
"""Exact bounded FRONT-triangle downward reachability; support acceptance ABSTAIN.

Serialized-decimal rational geometry, not exact float32/native physics. Domains
cover supplied upward-wound triangles and fixed translating AABBs only. Derived
linear body interpolation is NOT captured sub-command motion or an exit clock.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import offramp_bevclip as clip
import offramp_bevpm as pm
from offramp_buffer import require

CONTRACT = 'SERIALIZED_DECIMAL_FRONT_TRIANGLE_DOWNWARD_REACH_DOMAIN_V1'


def rational(x):
    require(type(x) in (int, float, Fraction), 'invalid rational coordinate type')
    require((type(x) is not float or math.isfinite(x)) and abs(x) <= 3.4028235e38,
            'invalid/nonfinite rational coordinate')
    return x if type(x) is Fraction else Fraction(str(x))


def vector(v):
    require(isinstance(v, (list, tuple)) and len(v) == 3, 'invalid reach vector')
    return [rational(x) for x in v]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def inputs(vertices, start, end, mins, maxs, horizon):
    require(isinstance(vertices, (list, tuple)) and len(vertices) == 3, 'invalid front triangle')
    vs = [vector(v) for v in vertices]
    start, end, mins, maxs = map(vector, (start, end, mins, maxs))
    horizon = rational(horizon)
    require(horizon >= 0 and all(a < b for a, b in zip(mins, maxs)), 'invalid reach horizon/hull')
    normal = cross(sub(vs[0], vs[1]), sub(vs[2], vs[1]))
    require(normal[2] > 0, 'degenerate/vertical/downward front triangle unsupported')
    return vs, start, end, mins, maxs, horizon


def canonical(polygon):
    """Exact convex polygon/segment/point representation, including degeneracy."""
    unique = list(dict.fromkeys(tuple(p) for p in polygon))
    if len(unique) <= 2:
        return sorted(unique)
    area = sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(unique, unique[1:]+unique[:1]))
    if not area:
        return [min(unique), max(unique)]
    result = []
    for i, b in enumerate(unique):
        a, c = unique[i-1], unique[(i+1) % len(unique)]
        if (b[0]-a[0])*(c[1]-b[1]) != (b[1]-a[1])*(c[0]-b[0]):
            result.append(b)
    return sorted(result)


def polygon_clip(polygon, constraints):
    """Closed a*x+b*y<=c, exact fractions, NO geometric epsilon/bias."""
    for a, b, c in constraints:
        if not polygon:
            break
        out = []
        previous = polygon[-1]
        fp = a*previous[0]+b*previous[1]-c
        for current in polygon:
            fc = a*current[0]+b*current[1]-c
            if (fp <= 0) != (fc <= 0):
                ratio = fp/(fp-fc)
                out.append(tuple(x+ratio*(y-x) for x, y in zip(previous, current)))
            if fc <= 0:
                out.append(tuple(current))
            previous, fp = current, fc
        polygon = list(dict.fromkeys(out))
    return canonical(polygon)


def axes(vertices):
    """Complete triangle/AABB SAT: xyz, face normal, triangle-edge cross xyz.

    No slab extrusion, side-plane max-gap approximation or native plane input.
    Unnormalized integer/rational axes avoid introducing square-root rounding.
    """
    xyz = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    edges = [sub(vertices[(i+1) % 3], vertices[i]) for i in range(3)]
    normal = cross(sub(vertices[0], vertices[1]), sub(vertices[2], vertices[1]))
    result = []
    for axis in xyz+[normal]+[cross(e, a) for e in edges for a in xyz]:
        if not any(axis):
            continue
        axis = [Fraction(x) for x in axis]
        pivot = next(x for x in axis if x)
        axis = tuple(x/pivot for x in axis)
        if axis not in result:
            result.append(axis)
    return result


def domain(vertices, start, end, mins, maxs, horizon):
    vs, start, end, mins, maxs, horizon = inputs(vertices, start, end, mins, maxs, horizon)
    delta = sub(end, start)
    constraints = []
    for axis in axes(vs):
        lo, hi = min(dot(v, axis) for v in vs), max(dot(v, axis) for v in vs)
        blo = dot(start, axis)+sum(n*(a if n >= 0 else b) for n, a, b in zip(axis, mins, maxs))
        bhi = dot(start, axis)+sum(n*(b if n >= 0 else a) for n, a, b in zip(axis, mins, maxs))
        speed = dot(delta, axis)
        constraints.extend([(speed, -axis[2], hi-blo), (-speed, axis[2], bhi-lo)])
    zero, one = Fraction(0), Fraction(1)
    polygon = polygon_clip([(zero, zero), (one, zero), (one, horizon), (zero, horizon)], constraints)
    coverage = [min(p[0] for p in polygon), max(p[0] for p in polygon)] if polygon else None
    return dict(polygon=polygon, coverage=coverage, constraints=constraints,
                parameter_bounds=[zero, one], downward_bounds=[zero, horizon],
                reach_distance_range=[min(p[1] for p in polygon), max(p[1] for p in polygon)] if polygon else None)


def eliminate(constraints):
    """Fourier-Motzkin elimination of first variable, positive scales only."""
    positive = [p for p in constraints if p[0] > 0]
    negative = [p for p in constraints if p[0] < 0]
    result = [p[1:] for p in constraints if p[0] == 0]
    for p in positive:
        for n in negative:
            result.append(tuple(a/p[0]+b/(-n[0]) for a, b in zip(p[1:], n[1:])))
    return list(dict.fromkeys(result))


def barycentric_domain(vertices, start, end, mins, maxs, horizon):
    """Independent joint point feasibility; NO SAT axes or expanded-face maxima.

    q=v0+u*(v1-v0)+v*(v2-v0), u>=0, v>=0, u+v<=1; require
    origin(t)-d*Z+mins <= q <= origin(t)-d*Z+maxs at the SAME point.
    Eliminate u/v to obtain the exact domain in t/d.
    """
    vs, start, end, mins, maxs, horizon = inputs(vertices, start, end, mins, maxs, horizon)
    e, f, delta = sub(vs[1], vs[0]), sub(vs[2], vs[0]), sub(end, start)
    constraints = [tuple(Fraction(x) for x in row) for row in
                   [(-1, 0, 0, 0, 0), (0, -1, 0, 0, 0), (1, 1, 0, 0, 1)]]
    for i in range(3):
        row = (e[i], f[i], -delta[i], Fraction(int(i == 2)))
        constraints += [(*row, start[i]+maxs[i]-vs[0][i]),
                        (*[-x for x in row], vs[0][i]-start[i]-mins[i])]
    projected = eliminate(eliminate(constraints))
    zero, one = Fraction(0), Fraction(1)
    return polygon_clip([(zero, zero), (one, zero), (one, horizon), (zero, horizon)], projected)


def spatial_witness(vertices, origin, mins, maxs, horizon):
    """Independent barycentric clipping against the downward-expanded xyz box.

    Existence across d in [0,D] equals this swept box. Returns a common point,
    barycentrics and a legal d, not independently satisfied plane distances.
    """
    vs, origin, _, mins, maxs, horizon = inputs(vertices, origin, origin, mins, maxs, horizon)
    e, f = sub(vs[1], vs[0]), sub(vs[2], vs[0])
    constraints = []
    for i in range(3):
        lo = origin[i]+mins[i]-(horizon if i == 2 else 0)
        hi = origin[i]+maxs[i]
        constraints += [(e[i], f[i], hi-vs[0][i]), (-e[i], -f[i], vs[0][i]-lo)]
    polygon = polygon_clip([(Fraction(0), Fraction(0)), (Fraction(1), Fraction(0)),
                            (Fraction(0), Fraction(1))], constraints)
    if not polygon:
        return None
    u, v = polygon[0]
    point = [a+u*b+v*c for a, b, c in zip(vs[0], e, f)]
    down = max(Fraction(0), origin[2]+mins[2]-point[2])
    require(down <= horizon and all(origin[i]+mins[i]-(down if i == 2 else 0) <= point[i] <=
                                   origin[i]+maxs[i]-(down if i == 2 else 0) for i in range(3)),
            'independent common-point witness failed')
    return dict(barycentric=[1-u-v, u, v], point=point, down=down)


def certified_domain(vertices, start, end, mins, maxs, horizon):
    result = domain(vertices, start, end, mins, maxs, horizon)
    independent = barycentric_domain(vertices, start, end, mins, maxs, horizon)
    require(result['polygon'] == independent, 'front SAT/joint-barycentric domain differs')
    require(result['coverage'] == ([min(p[0] for p in independent), max(p[0] for p in independent)]
                                  if independent else None), 'front domain coverage projection differs')
    require(result['reach_distance_range'] == ([min(p[1] for p in independent), max(p[1] for p in independent)]
                                              if independent else None), 'front reach distance projection differs')
    require(result['parameter_bounds'] == [0, 1] and result['downward_bounds'] == [0, rational(horizon)],
            'front domain parameter bounds differ')
    start, end = vector(start), vector(end)
    witnesses = []
    for t, down in result['polygon']:
        origin = [a+t*(b-a)-(down if i == 2 else 0) for i, (a, b) in enumerate(zip(start, end))]
        witness = spatial_witness(vertices, origin, mins, maxs, 0)
        require(witness is not None, 'front domain vertex has no common-point witness')
        witnesses.append(dict(t=t, down=down, **{'surface': witness}))
    result['joint_barycentric_equality'] = 'PASS'
    result['vertex_witnesses'] = witnesses
    return result


def union_coverage(intervals):
    intervals = [list(map(rational, p)) for p in intervals]
    require(all(len(p) == 2 and 0 <= p[0] <= p[1] <= 1 for p in intervals), 'invalid coverage interval')
    merged = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(hi, merged[-1][1])
        else:
            merged.append([lo, hi])
    return merged


def gaps(coverage):
    """Complement of closed coverage: gap endpoint inclusion is explicit.

    A touching point partitions the complement but has zero coverage duration.
    Nonzero gaps are never hidden by endpoint-only or sampled/dwell decisions.
    """
    merged = union_coverage(coverage)
    result, previous = [], Fraction(0)
    left_covered = False
    for lo, hi in merged:
        if previous < lo:
            result.append(dict(start=previous, end=lo, start_included=not left_covered,
                               end_included=False, length=lo-previous))
        previous, left_covered = hi, True
    if previous < 1 or not merged:
        result.append(dict(start=previous, end=Fraction(1), start_included=not left_covered,
                           end_included=True, length=1-previous))
    return result


def patch_coverage(triangles, start, end, mins, maxs, horizon):
    require(isinstance(triangles, (list, tuple)), 'invalid supplied patch set')
    start, end, mins, maxs = map(vector, (start, end, mins, maxs))
    horizon = rational(horizon)
    require(horizon >= 0 and all(a < b for a, b in zip(mins, maxs)), 'invalid reach horizon/hull')
    domains = [certified_domain(vs, start, end, mins, maxs, horizon) for vs in triangles]
    coverage = union_coverage([d['coverage'] for d in domains if d['coverage'] is not None])
    return dict(domains=domains, coverage=coverage, gaps=gaps(coverage),
                neighborhood_basis='SUPPLIED_PATCH_SET_NOT_DISCOVERED_TOPOLOGY')


def assess_case(case, index, horizon=2):
    active = index != 1
    points = [pm.SEED[:3]]+[t[10:13] for t in case['ticks']]
    segments, samples, global_coverage = [], [], []
    duration = Fraction(15, 1000)
    for i, tick in enumerate(case['ticks']):
        start, end = points[i], points[i+1]
        d = certified_domain(pm.VERTICES, start, end, tick[16:19], tick[19:22], horizon)
        segments.append(dict(command_index=i, start=start, end=end, front_domain=d))
        if active and d['coverage'] is not None:
            lo, hi = d['coverage']
            global_coverage.append([(i+lo)/len(case['ticks']), (i+hi)/len(case['ticks'])])
        point_domain = certified_domain(pm.VERTICES, end, end, tick[16:19], tick[19:22], horizon)
        witness = spatial_witness(pm.VERTICES, end, tick[16:19], tick[19:22], horizon)
        require(bool(point_domain['polygon']) == (witness is not None), 'front sample witness/status differs')
        samples.append(dict(tick=i, counterfactual_front_reachable=bool(point_domain['polygon']), active=active,
                            live_front_reachable=active and bool(point_domain['polygon']),
                            distance_range=point_domain['reach_distance_range'], witness=witness,
                            native_ramp=bool(tick[8]), native_down2_hit=case['queries'][i][1][9] < 1))
    coverage = union_coverage(global_coverage)
    derived_gaps = gaps(coverage)
    total = duration*len(case['ticks'])
    for gap in derived_gaps:
        gap['derived_seconds'] = gap['length']*total
    return dict(label=case['label'], active=active, horizon=horizon, samples=samples, segments=segments,
                live_derived_track_coverage=coverage, live_derived_track_gaps=derived_gaps,
                trajectory_basis='LINEAR_INTERPOLATION_OF_CAPTURED_COMMAND_ENDPOINTS_NOT_CAPTURED_SUBCOMMAND_PATH',
                geometry_basis='AUTHORED_FIXTURE_FRONT_NOT_COPIED_NEIGHBORHOOD', derived_duration_seconds=total)


def assess_contact(contact):
    cp, row = contact['copied_winner'], contact['contact']
    require(cp['vertices'] == pm.VERTICES and cp['indexes'] == [0, 1, 2] and
            row[15:21] == pm.MINS+pm.MAXS, 'copied front geometry/hull binding differs')
    return dict(tick=int(row[1]), contact_ordinal=int(row[0]), vertices=cp['vertices'],
                start=row[9:12], end=row[12:15], mins=row[15:18], maxs=row[18:21],
                geometry_basis='COPIED_WINNING_NATIVE_TRIANGLE_FRONT_ONLY',
                attempted_sweep_basis='CAPTURED_ACCEPTED_CONTACT_REQUEST_NOT_ACTUAL_BODY_PATH',
                front_domain=certified_domain(cp['vertices'], row[9:12], row[12:15], row[15:18], row[18:21], 2))


def compare(*texts):
    prior = clip.compare(*texts)
    pm_report = prior['prior_pm_report']
    cases = [assess_case(c, i) for i, c in enumerate(pm_report['cases'])]
    accepted = [dict(case_index=i, **assess_contact(r)) for i, c in enumerate(pm_report['cases']) for r in c['accepted']]
    # This is an exact geometric gate, not a data-derived physical exit policy.
    for i in (21, 22):
        sample = cases[0]['samples'][i]
        tick = pm_report['cases'][0]['ticks'][i]
        require(rational(tick[10])+rational(tick[19]) < 0 and not sample['counterfactual_front_reachable'],
                'late front-triangle X exclusion did not ACT')
    return dict(bounded_front_reachability_gates='PASS', contract=CONTRACT, cases=cases, accepted=accepted,
                sample_count=sum(len(c['samples']) for c in cases),
                derived_segment_count=sum(len(c['segments']) for c in cases), accepted_request_count=len(accepted),
                prior_plane_set_report=prior, general_triangle_support='ABSTAIN',
                native_front_reach_equivalence='NOT_CLAIMED', physical_exit_acceptance='NOT_TESTED',
                standability_load_bearing_acceptance='NOT_TESTED', discovered_neighborhood_topology='NOT_IMPLEMENTED',
                classifier_render_hold_clock='NOT_TESTED')


def encoded(value):
    """JSON contract: all exact rational outputs are reduced fraction strings."""
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encoded(v) for v in value]
    return value


def load_arms(path):
    texts, provenance = pm.load_arms(path)
    arms = json.loads(path.read_text())
    modes = ((0, 0), (0, 1), (0, 1), (1, 1), (1, 1))
    require(all(arms[n].get('bevpm_source_sha256') == pm.source_digest() and
                all(type(arms[n].get(k)) is int for k in ('capture', 'oracle')) and
                (arms[n].get('capture'), arms[n].get('oracle')) == mode for n, mode in zip(pm.NAMES, modes)),
            'front reach retained PM fixture/mode manifest differs')
    return texts, provenance


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('Need NEW output file; refusing to overwrite retained evidence')
    texts, manifest = load_arms(args.arms)
    result = compare(*texts); result['arms'] = manifest
    result['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(encoded(result), indent=2, allow_nan=False)+'\n')
    print('PASS exact bounded front reach domains + joint witnesses; support ABSTAIN; exit NOT_TESTED')


if __name__ == '__main__':
    main()
