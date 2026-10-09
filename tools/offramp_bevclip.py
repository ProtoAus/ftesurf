#!/usr/bin/env python3
"""Bounded native triangle halfspace diagnostic; general support ABSTAIN.

A mathematical model of the identity/standing-AABB fixture's native plane set,
NOT a physical finite-prism oracle or engine replacement. Construct every plane
from xyz/winding before reading observed hits, planes or fractions. Ideal SAT
remains separate. This offline reader never launches or instruments a server.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import offramp_bevpm as pm
from offramp_buffer import require
from offramp_triangle import NATIVE_BIAS, SPATIAL_TOLERANCE, cross, dot, prism, sub, sweep, vector

CONTRACT = 'BIH_TRIANGLE_IDENTITY_STANDING_AABB_PLANE_SET'


def unit(axis):
    length = math.sqrt(dot(axis, axis))
    require(length > 1e-9, 'degenerate native-semantic plane')
    return [x/length for x in axis]


def triangle_planes(vertices, bevels):
    """Native order: front/back, outward sides, optional bevels, raw xyz axes.

    The six axial distances deliberately use ONLY the three front vertices.
    Unlike ideal prism SAT they can exclude portions of the four-unit back slab.
    No native output row is an input to this construction.
    """
    require(type(bevels) is bool, 'invalid bevel mode')
    points, front = prism(vertices)
    vertices = points[:3]
    distance = dot(vertices[0], front)
    planes = [dict(tag=0, normal=front, dist=distance, kind='front'),
              dict(tag=1, normal=[-x for x in front], dist=4-distance, kind='back')]
    edges = [(0, 1, 2), (1, 2, 0), (2, 0, 1)]
    for i, (a, b, c) in enumerate(edges):
        normal = unit(cross(sub(vertices[b], vertices[a]), front))
        if dot(sub(vertices[c], vertices[a]), normal) > 0:
            normal = [-x for x in normal]
        planes.append(dict(tag=i+2, normal=normal, dist=dot(vertices[a], normal), kind='side'))
    if bevels:
        for a, b, c in edges:
            for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1]):
                normal = cross(sub(vertices[b], vertices[a]), axis)
                if math.sqrt(dot(normal, normal)) < 1e-5:
                    continue
                normal = unit(normal)
                if dot(sub(vertices[c], vertices[a]), normal) > 0:
                    normal = [-x for x in normal]
                # Support the full slab, including outward-shifted back corners.
                distance = dot(vertices[a], normal)-4*min(0, dot(normal, front))
                planes.append(dict(tag=len(planes), normal=normal, dist=distance, kind='bevel'))
    for i in range(6):
        axis, sign = i % 3, 1 if i < 3 else -1
        normal = [0, 0, 0]; normal[axis] = sign
        distance = max(dot(v, normal) for v in vertices)
        planes.append(dict(tag=100+i, normal=normal, dist=distance, kind='raw-triangle-axial'))
    return planes


def interval(planes, start, end, mins, maxs):
    """Closed halfspace interval and per-plane certificates in world units.

    Hull support is applied directly to the body origin; this is algebraically
    equivalent to native recentring. Strict maximum keeps the first entering
    plane on a tie, as the one-triangle clipper does. Never expand by bias here.
    """
    start, end, mins, maxs = map(vector, (start, end, mins, maxs))
    require(all(lo < hi for lo, hi in zip(mins, maxs)), 'invalid native-semantic hull')
    lower, upper, entry = -math.inf, math.inf, None
    certificates, parallel_outside = [], []
    for p in planes:
        normal, distance = vector(p['normal']), p['dist']
        require(math.isfinite(distance) and abs(dot(normal, normal)-1) < 1e-8,
                'invalid native-semantic plane')
        support = sum(n*(lo if n >= 0 else hi) for n, lo, hi in zip(normal, mins, maxs))
        a, b = dot(start, normal)-distance+support, dot(end, normal)-distance+support
        cert = dict(**p, start_distance=a, end_distance=b, enter=None, leave=None)
        if a == b:
            if a > 0:
                parallel_outside.append(p['tag'])
        elif a > b:
            f = a/(a-b); cert['enter'] = f
            if f > lower:
                lower, entry = f, cert
        else:
            f = a/(a-b); cert['leave'] = f
            upper = min(upper, f)
        certificates.append(cert)
    intersects = not parallel_outside and lower <= upper and upper >= 0 and lower <= 1
    starts_overlap = all(p['start_distance'] <= 0 for p in certificates)
    ends_overlap = all(p['end_distance'] <= 0 for p in certificates)
    return dict(intersects=bool(intersects), starts_overlap=starts_overlap, ends_overlap=ends_overlap,
                enter=max(0, lower) if intersects else None, leave=min(1, upper) if intersects else None,
                lower=lower if math.isfinite(lower) else None, upper=upper if math.isfinite(upper) else None,
                entry_plane=entry if intersects and lower >= 0 else None,
                parallel_outside_tags=parallel_outside,
                whole_segment_outside_tags=[p['tag'] for p in certificates if
                                            p['start_distance'] > 0 and p['end_distance'] > 0],
                planes=certificates)


def prediction(vertices, start, end, mins, maxs, bevels):
    """Fixture clear-start query result, NOT general startsolid/wrapper semantics."""
    clipped = interval(triangle_planes(vertices, bevels), start, end, mins, maxs)
    # The retained actual fixture starts clear. Embedded stationary PM wrappers
    # have other return semantics, deliberately outside this diagnostic's scope.
    if clipped['starts_overlap']:
        return dict(expected=None, clipped=clipped, wrapper_semantics='EMBEDDED_NOT_MODELED')
    if not clipped['intersects']:
        expected = [1, 0, 0, 0, -1, 0, 0, 0, 0, 0]
    else:
        p = clipped['entry_plane']
        require(p is not None and start != end, 'native-semantic entry did not ACT')
        speed = p['start_distance']-p['end_distance']
        near = max(0, clipped['enter']-NATIVE_BIAS/speed)
        expected = [near, clipped['enter'], 0, 0, 0, *p['normal'], p['dist'], 1]
    return dict(expected=expected, clipped=clipped)


def check_observation(observed, predicted, *, truefraction_observed=True):
    require(len(observed) == 10 and all(isinstance(x, (int, float)) and math.isfinite(x)
                                      for i, x in enumerate(observed) if i != 1 or truefraction_observed) and
            (truefraction_observed or observed[1] is None), 'invalid native-semantic observation')
    want = predicted['expected']
    require(want is not None, 'native-semantic embedded start unsupported')
    if want[0] == 1:
        require(observed == want, 'native-semantic predicted miss differs')
    else:
        require(observed[2:5] == want[2:5] and observed[9] == want[9] and
                pm.close(observed[5:8], want[5:8], 1e-5) and
                abs(observed[8]-want[8]) <= SPATIAL_TOLERANCE,
                'native-semantic predicted hit flags/plane/contents differ')
        p = predicted['clipped']['entry_plane']; speed = p['start_distance']-p['end_distance']
        count = 2 if truefraction_observed else 1
        require(all(0 <= x <= 1 for x in observed[:count]) and
                all(abs(a-b)*speed <= SPATIAL_TOLERANCE for a, b in zip(observed[:count], want[:count])),
                'native-semantic predicted fractions differ')


def assess_query(row, tick, case):
    # The prior strict decoder binds command/body/query/hull/mode and schema.
    start, end, mins, maxs = row[3:6], row[6:9], tick[16:19], tick[19:22]
    predicted = prediction(pm.VERTICES, start, end, mins, maxs, case != 2)
    active = case != 1 and row[2] != 'untriangled'
    expected = predicted if active else dict(expected=[1, 0, 0, 0, -1, 0, 0, 0, 0, 0])
    check_observation(row[9:], expected)
    ideal = sweep(pm.VERTICES, start, end, mins, maxs)
    result = dict(query=row[2], active=active, native_hit=row[9] < 1,
                  counterfactual_native=predicted, ideal_prism=ideal,
                  geometry_basis='AUTHORED_FIXTURE_NOT_ACCEPTED_COPY')
    if active and ideal['intersects'] and not predicted['clipped']['intersects']:
        planes = triangle_planes(pm.VERTICES, case != 2)
        axial = [p for p in predicted['clipped']['planes'] if p['kind'] == 'raw-triangle-axial' and
                 p['start_distance'] > 0 and p['end_distance'] > 0]
        tags = [p['tag'] for p in axial]
        relaxed = interval([p for p in planes if p['tag'] not in tags], start, end, mins, maxs)
        require(tags and relaxed['intersects'], 'ideal/native difference not explained by axial exclusion')
        result['axial_exclusion'] = dict(tags=tags, separating_planes=axial, without_exclusions=relaxed)
    return result


def assess_contact(contact, case):
    row, cp = contact['contact'], contact['copied_winner']
    predicted = prediction(cp['vertices'], row[9:12], row[12:15], row[15:18], row[18:21],
                           bool(cp['native_bevels_applied']))
    require(predicted['clipped']['intersects'] and predicted['clipped']['entry_plane']['tag'] == cp['native_plane_tag'],
            'copied native-semantic accepted tag/entry differs')
    # CONTACT does not retain truefraction; do NOT pretend it was observed.
    observed = [row[4], None, 0, 0, 0, *row[6:9], row[5], 1]
    check_observation(observed, predicted, truefraction_observed=False)
    return dict(tick=int(row[1]), geometry_basis='COPIED_WINNING_NATIVE_TRIANGLE',
                predicted_native=predicted, observed_truefraction='NOT_CAPTURED',
                ideal_prism=contact['ideal_prism'])


def compare(*texts):
    prior = pm.compare(*texts)
    cases = []
    for case, c in enumerate(prior['cases']):
        queries = [[assess_query(r, t, case) for r in qs] for t, qs in zip(c['ticks'], c['queries'])]
        accepted = [assess_contact(r, case) for r in c['accepted']]
        cases.append(dict(label=c['label'], queries=queries, accepted=accepted))
    exclusions = [i for i, qs in enumerate(cases[0]['queries']) if 'axial_exclusion' in qs[1]]
    require(exclusions == [21, 22] and all(cases[0]['queries'][i][1]['axial_exclusion']['tags'] == [103]
                                         for i in exclusions), 'bounded ON axial discrepancy did not ACT')
    # Derive the unobstructed first attempted move at raw loss from the real prior
    # body and half-gravity rule already bound for every accepted captured sweep.
    loss = prior['raw_loss_ticks']
    require(loss == [22], 'bounded native loss differs')
    t = prior['cases'][0]['ticks'][loss[0]-1]
    start = t[10:13]; end = [p+.015*(v-(6 if a == 2 else 0)) for a, (p, v) in enumerate(zip(start, t[13:16]))]
    attempted = prediction(pm.VERTICES, start, end, pm.MINS, pm.MAXS, True)
    require(not attempted['clipped']['intersects'] and pm.close(end, prior['cases'][0]['ticks'][22][10:13], 2e-5),
            'derived raw-loss first move did not ACT unobstructed native miss')
    points, _ = prism(pm.VERTICES)
    whole_segment = [p for p in attempted['clipped']['planes'] if
                     p['tag'] in attempted['clipped']['whole_segment_outside_tags']]
    prism_separators = [dict(**p, prism_support=max(dot(v, p['normal']) for v in points)) for p in whole_segment
                       if abs(p['dist']-max(dot(v, p['normal']) for v in points)) < 1e-9]
    require(prism_separators and not sweep(pm.VERTICES, start, end, pm.MINS, pm.MAXS)['intersects'],
            'raw-loss ideal miss lacks independent full-prism separating certificate')
    return dict(bounded_native_plane_set_gates='PASS', contract=CONTRACT,
                actual_query_checks=sum(len(qs) for c in cases for qs in c['queries']),
                accepted_contact_checks=sum(len(c['accepted']) for c in cases),
                accepted_entry_plane_tags=sorted({r['predicted_native']['clipped']['entry_plane']['tag']
                                                 for c in cases for r in c['accepted']}),
                all_plane_runtime_coverage='NOT_CLAIMED',
                quiet_arm_queries='NOT_CAPTURED', embedded_counterfactual_wrapper_semantics='NOT_MODELED',
                on_down2_axial_exclusion_ticks=exclusions,
                on_stationary_ideal_overlap_ticks=[i for i, qs in enumerate(cases[0]['queries']) if qs[0]['ideal_prism']['intersects']],
                raw_loss_first_move=dict(tick=22, basis='DERIVED_ATTEMPT_NOT_CAPTURED_ACCEPTED_TRACE',
                                         start=start, end=end, predicted_native=attempted,
                                         ideal_prism=sweep(pm.VERTICES, start, end, pm.MINS, pm.MAXS),
                                         full_prism_separating_planes=prism_separators),
                cases=cases, prior_pm_report=prior, general_triangle_support='ABSTAIN',
                general_native_triangle_semantics='NOT_TESTED', physical_exit_acceptance='NOT_TESTED')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('Need NEW output file; refusing to overwrite retained evidence')
    texts, manifest = pm.load_arms(args.arms)
    result = compare(*texts); result['arms'] = manifest
    result['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print('PASS bounded native plane-set diagnostic; general support ABSTAIN; physical exit NOT_TESTED')


if __name__ == '__main__':
    main()
