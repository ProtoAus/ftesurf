#!/usr/bin/env python3
"""Exact front reach on CAPTURED committed native segments; support ABSTAIN.

Feeds the bounded TryPlayerMove capture's committed body segments, not chords
between command endpoints, to the exact front-domain algebra. In-place
intersection is serialized beside hypothetical downward reach. Nominal shares
parameterize a command from captured bookkeeping; they are not a clock.
Arithmetic is exact on serialized decimals, which is not measurement precision.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import offramp_bevpm as pm
import offramp_tripath as path
import offramp_trisupport as reach
from offramp_buffer import require

CONTRACT = 'CAPTURED_COMMITTED_SEGMENT_FRONT_REACH_V2'
# hypothetical_down is the closed range 0<=d<=2 and so CONTAINS in_place.
# Horizon 2 binds the existing down2 query; it is not a support/classifier constant.
HORIZONS = (('in_place', 0), ('hypothetical_down', 2))
SHARE_BASIS = 'NATIVE_TIME_LEFT_BEFORE_TIMES_COMMITTED_FRACTION_NOT_AN_EXIT_CLOCK'
PROBES = tuple(Fraction(i, 4) for i in range(1, 4))
NEAR = Fraction(1, 2**40)


def shares(rows, duration):
    """Exact nominal share of one native command per committed segment."""
    lefts = [reach.rational(r['native_left_before']) for r in rows]
    fractions = [reach.rational(r['committed_fraction']) for r in rows]
    require(rows and all(x > 0 for x in lefts) and all(0 <= f <= 1 for f in fractions),
            'invalid committed time-left/fraction')
    weights = [a*b for a, b in zip(lefts, fractions)]
    total = sum(weights)
    require(total > 0 and abs(total-reach.rational(duration)) <= Fraction(1, 10**8),
            'committed shares do not sum to the native command')
    return [w/total for w in weights]


def glue(pieces):
    """Map closed local coverage through consecutive path shares summing to one."""
    require(isinstance(pieces, (list, tuple)) and len(pieces) > 0, 'invalid committed path')
    offset, mapped = Fraction(0), []
    for share, local in pieces:
        share = reach.rational(share)
        require(share >= 0, 'invalid committed path share')
        mapped += [[offset+lo*share, offset+hi*share] for lo, hi in reach.union_coverage(local)]
        offset += share
    require(offset == 1, 'committed path shares do not sum to one')
    coverage = reach.union_coverage(mapped)
    return coverage, reach.gaps(coverage)


def path_reach(triangles, points, path_shares, mins, maxs, horizon):
    """Supplied front patches along a continuous piecewise-linear body path.

    points has one more entry than path_shares. A zero share is one point of
    the path parameter and must not move. No chord skips a captured point.
    """
    require(isinstance(points, (list, tuple)) and isinstance(path_shares, (list, tuple)) and
            len(points) == len(path_shares)+1 >= 2, 'invalid committed path')
    points = [reach.vector(p) for p in points]
    path_shares = [reach.rational(s) for s in path_shares]
    require(all(s > 0 or a == b for s, a, b in zip(path_shares, points, points[1:])),
            'moving committed segment has no path share')
    local = [reach.patch_coverage(triangles, a, b, mins, maxs, horizon) for a, b in zip(points, points[1:])]
    coverage, gaps = glue([(s, p['coverage']) for s, p in zip(path_shares, local)])
    return dict(points=points, shares=path_shares, segments=local, coverage=coverage, gaps=gaps)


def locate(path_shares, u):
    """Inverse of glue written separately: every (segment, local t) at parameter u."""
    found, offset = [], Fraction(0)
    for i, share in enumerate(path_shares):
        if offset <= u <= offset+share:
            found.append((i, (u-offset)/share if share else Fraction(0)))
        offset += share
    return found


def origin(result, site):
    i, t = site
    return [a+t*(b-a) for a, b in zip(result['points'][i], result['points'][i+1])]


def probe(triangles, result, mins, maxs, horizon):
    """Glued coverage against local coverage everywhere, and against witnesses.

    Membership is constant between consecutive breakpoints, so one parameter per
    cell plus the breakpoints settles the GLUING exhaustively. Witnesses at those
    parameters, hard against each breakpoint and at fixed local t only SAMPLE a
    segment's own domain: an interval lost from both local and glued coverage
    can sit between samples. The witness shares the polygon primitive.
    """
    offset, marks, fixed = Fraction(0), {Fraction(0), Fraction(1)}, []
    for share, local in zip(result['shares'], result['segments']):
        marks |= {offset, offset+share} | {offset+x*share for p in local['coverage'] for x in p}
        fixed += [offset+t*share for t in PROBES]
        offset += share
    marks = sorted(marks | {x for p in result['coverage'] for x in p})
    wanted = marks+fixed+[a+(b-a)*k for a, b in zip(marks, marks[1:]) for k in (NEAR, Fraction(1, 2), 1-NEAR)]
    wanted = list(dict.fromkeys(wanted))
    inside = 0
    for u in wanted:
        sites = locate(result['shares'], u)
        covered = any(lo <= u <= hi for lo, hi in result['coverage'])
        require(sites and covered == any(lo <= t <= hi for i, t in sites for lo, hi in result['segments'][i]['coverage']),
                'glued coverage differs from local segment coverage')
        require({any(reach.spatial_witness(t, origin(result, s), mins, maxs, horizon) is not None for t in triangles)
                 for s in sites} == {covered}, 'committed path coverage differs from common-point witness')
        inside += covered
    return dict(parameters=len(wanted), inside_coverage=inside)


def separate(in_place, hypothetical):
    """The horizon-0 domain must be exactly the d=0 edge of the deeper one.

    Returns how many patches had a non-empty edge to compare; empty against
    empty proves nothing.
    """
    require(len(in_place['domains']) == len(hypothetical['domains']), 'in-place/hypothetical patch sets differ')
    for a, b in zip(in_place['domains'], hypothetical['domains']):
        require(a['downward_bounds'] == [0, 0] and b['downward_bounds'][1] > 0 and
                a['polygon'] == sorted(p for p in b['polygon'] if p[1] == 0),
                'in-place reach is not the zero-distance edge of hypothetical downward reach')
    return sum(bool(a['polygon']) for a in in_place['domains'])


def regained(coverage):
    """Reach lost and found again: every maximal interval after the first."""
    return [dict(lost_at=a[1], regained_at=b[0], regained_measure=b[1]-b[0]) for a, b in zip(coverage, coverage[1:])]


def recontact_verdict(found):
    return ('OBSERVED' if any(r['regained_measure'] > 0 for r in found) else
            'ZERO_MEASURE_TOUCH_ONLY' if found else 'NOT_ACTED_IN_THESE_ACTORS')


def ramp_versus_reach(reached):
    """Live front only, horizon 2: (command, native ramp return, command reach).

    Emptiness, not measure, decides "no reach"; a bare touch is listed apart.
    A disagreement is an observation, not a verdict.
    """
    return dict(live_native_ramp_without_reach_commands=[i for i, ramp, r in reached if ramp and not r['coverage']],
                live_reach_without_native_ramp_commands=[i for i, ramp, r in reached if r['coverage'] and not ramp],
                live_partially_reached_commands=[i for i, _, r in reached if r['coverage'] and r['covered_share'] < 1],
                live_zero_measure_reach_commands=[i for i, _, r in reached if r['coverage'] and not r['covered_share']])


def committed(call, tick, body, ordinal):
    """Captured committed segments of one native call with native provenance."""
    rows = []
    require(len(call['committed_segments']) == len(call['attempts']) == len(call['outcomes']) > 0,
            'committed segment/attempt/outcome counts differ')
    for k, (s, r, o) in enumerate(zip(call['committed_segments'], call['attempts'], call['outcomes'])):
        left = call['call'][2] if k == 0 else rows[-1]['native_left_after']
        fraction = r[24]
        require(r[0] == ordinal+k and r[1] == call['command_index'] and r[2] == k and
                s['attempt_ordinal'] == r[0] == o[0], 'committed segment identity differs')
        require(s['start'] == body == r[5:8] and s['end'] == r[34:37] == o[3:6],
                'committed segment not continuous in serialized values')
        require(s['native_left_before'] == r[4] == left and s['native_left_after'] == o[2] and
                s['committed_fraction'] == fraction and 0 <= fraction <= 1 and
                (o[2] == left if fraction == 1 else abs(o[2]-left*(1-fraction)) <= 1e-8),
                'committed segment time-left/fraction provenance differs')
        hit = fraction < 1
        rows.append(dict(segment=k, attempt_ordinal=int(r[0]), bump=int(r[2]), start=s['start'], end=s['end'],
                         wanted_end=r[14:17], mins=r[17:20], maxs=r[20:23], native_left_before=r[4],
                         native_left_after=o[2], committed_fraction=fraction, native_hit=hit,
                         # A clear pass prints truefraction 0; that is not an entry.
                         truefraction=r[25] if hit else None, native_plane=r[29:33] if hit else None,
                         native_outcome=int(o[1]), velocity_before=r[11:14], velocity_after=o[6:9]))
        body = s['end']
    require(body == tick[10:13] and call['returned'][-1] == tick[8],
            'committed path does not end at the captured command body/ramp flag')
    return rows


def transitions(result, owners, horizon):
    """Where glued coverage starts and stops, located back on captured segments.

    A boundary reachable only at the full horizon moves with the horizon.
    """
    found = []
    for lo, hi in result['coverage']:
        for kind, u in (('enter', lo), ('exit', hi)):
            sites = []
            for i, t in locate(result['shares'], u):
                row = owners[i]
                downs = [p[1] for d in result['segments'][i]['domains'] for p in d['polygon'] if p[0] == t]
                sites.append(dict(command_index=row['command_index'], segment=row['segment'],
                                  attempt_ordinal=row['attempt_ordinal'], local_t=t,
                                  command_parameter=row['command_offset']+t*row['command_share'],
                                  origin=origin(result, (i, t)),
                                  down_range_at_boundary=[min(downs), max(downs)] if downs else None))
            found.append(dict(kind=kind if 0 < u < 1 else 'track-bound', track_parameter=u, sites=sites,
                              strictly_inside_command=all(0 < s['command_parameter'] < 1 for s in sites),
                              reachable_only_at_full_horizon=all(
                                  s['down_range_at_boundary'] and s['down_range_at_boundary'][0] == horizon
                                  for s in sites) if horizon else None))
    return found


def consistent(coverage, found, commands, name, count):
    """Two computations of one thing must agree: the track cut to a command with
    that command's own glue, and each boundary site with its command parameter."""
    for c in commands:
        lo0, hi0 = Fraction(c['command_index'], count), Fraction(c['command_index']+1, count)
        cut = [[(max(lo, lo0)-lo0)*count, (min(hi, hi0)-lo0)*count] for lo, hi in coverage if max(lo, lo0) <= min(hi, hi0)]
        require(cut == c[name]['coverage'], 'track coverage differs from the command glue')
    require(all(t['track_parameter'] == (s['command_index']+s['command_parameter'])/count
                for t in found for s in t['sites']), 'boundary site differs from its command parameter')


def assess_case(native, previous, derived, index):
    require(previous['label'] == derived['label'] == pm.LABELS[index], 'committed reach actor order differs')
    active = index != 1
    triangles = [pm.VERTICES]
    count = len(native['calls'])
    require(count == len(previous['ticks']) == len(derived['segments']) > 0, 'committed/derived command counts differ')
    body, commands, owners = pm.SEED[:3], [], []
    for call, tick, chord in zip(native['calls'], previous['ticks'], derived['segments']):
        rows = committed(call, tick, body, len(owners))
        duration = Fraction(int(tick[2]), 1000)
        require(chord['start'] == body and chord['end'] == rows[-1]['end'] and
                abs(duration-reach.rational(call['call'][2])) <= Fraction(1, 10**8),
                'derived chord or command duration not bound to the committed command')
        body = rows[-1]['end']
        moving = [r['start'] != r['end'] for r in rows]
        require(moving == [r[5:8] != r[34:37] for r in call['attempts']], 'captured kink not carried into the reach path')
        offset = Fraction(0)
        for row, share in zip(rows, shares(rows, call['call'][2])):
            # Pins the share RULE: the captured pre-clip velocity must carry the captured
            # start to the captured end in that nominal time. Only hit commands can tell rules apart.
            require(all(abs(reach.rational(e)-reach.rational(s)-reach.rational(v)*share*reach.rational(call['call'][2]))
                        <= Fraction(4, 10**5) for s, e, v in zip(row['start'], row['end'], row['velocity_before'])),
                    'committed displacement differs from velocity x nominal share')
            row.update(command_index=call['command_index'], command_share=share, command_offset=offset,
                       track_share=share/count)
            offset += share
        # How far a captured interior point sits from the chord at the same share, against
        # one float32 step of the command's largest coordinate: the mover's own quantum.
        a, b = reach.vector(chord['start']), reach.vector(chord['end'])
        kink = max((abs(p-(x+(row['command_offset']+row['command_share'])*(y-x)))
                    for row in rows[:-1] for p, x, y in zip(reach.vector(row['end']), a, b)), default=Fraction(0))
        quantum = Fraction(2)**(math.frexp(max(abs(x) for row in rows for x in row['start']+row['end']))[1]-24)
        owners += rows
        commands.append(dict(command_index=call['command_index'], duration_seconds=duration,
                             native_ramp_return=bool(tick[8]), segments=rows, path_is_endpoint_chord=sum(moving) <= 1,
                             kink_offset_units=kink, float32_step_units=quantum, kink_resolved=kink > quantum, chord=chord))
    mins, maxs = owners[0]['mins'], owners[0]['maxs']
    require(all(r['mins'] == mins and r['maxs'] == maxs for r in owners), 'committed path hull is not one fixed AABB')
    points = [pm.SEED[:3]]+[r['end'] for r in owners]
    seconds = sum(c['duration_seconds'] for c in commands)
    track = {}
    for name, horizon in HORIZONS:
        result = path_reach(triangles, points, [r['track_share'] for r in owners], mins, maxs, horizon)
        probes = probe(triangles, result, mins, maxs, horizon)
        for row, local in zip(owners, result['segments']):
            row[name] = local
        for c in commands:
            coverage, gaps = glue([(r['command_share'], r[name]['coverage']) for r in c['segments']])
            c[name] = dict(coverage=coverage, gaps=gaps, covered_share=sum(hi-lo for lo, hi in coverage),
                           front_is_live=active)
        found = transitions(result, owners, horizon)
        consistent(result['coverage'], found, commands, name, count)
        for gap in result['gaps']:
            gap['nominal_seconds_not_exit_clock'] = gap['length']*seconds
        track[name] = dict(horizon=horizon, front_is_live=active, common_point_probes=probes,
                           front_coverage=result['coverage'], front_gaps=result['gaps'], front_transitions=found,
                           live_coverage=result['coverage'] if active else [],
                           live_gaps=result['gaps'] if active else
                           [dict(reach.gaps([])[0], nominal_seconds_not_exit_clock=seconds)],
                           live_regained=regained(result['coverage']) if active else [])
    edges = sum(separate(row['in_place'], row['hypothetical_down']) for row in owners)
    for c in commands:
        chord = c.pop('chord')
        own = reach.certified_domain(pm.VERTICES, chord['start'], chord['end'], mins, maxs, HORIZONS[1][1])
        require(own['polygon'] == chord['front_domain']['polygon'] and own['coverage'] == chord['front_domain']['coverage'],
                'derived chord domain differs from its recomputation')
        got, want = c['hypothetical_down']['coverage'], [own['coverage']] if own['coverage'] is not None else []
        c['chord_hypothetical_coverage'] = want
        c['chord_boundary_shift'] = (max(abs(x-y) for p, q in zip(got, want) for x, y in zip(p, q))
                                     if got and len(got) == len(want) else Fraction(0) if got == want else None)
        c['chord_comparison'] = ('EQUAL' if got == want else 'DIFFERS' if c['kink_resolved'] else
                                 'DIFFERS_BELOW_FLOAT32_KINK')
    hits, ramped = [], {c['command_index'] for c in commands if c['native_ramp_return']}
    for row in owners:
        if row['native_hit']:
            at = reach.certified_domain(pm.VERTICES, row['end'], row['end'], mins, maxs, HORIZONS[1][1])
            # The REQUESTED sweep, not committed motion: where the exact front would be met in place.
            wanted = reach.certified_domain(pm.VERTICES, row['start'], row['wanted_end'], mins, maxs, 0)['coverage']
            closing = abs(sum((reach.rational(e)-reach.rational(s))*reach.rational(n) for s, e, n in
                              zip(row['start'], row['wanted_end'], row['native_plane'])))
            late = wanted[0]-reach.rational(row['truefraction']) if wanted else None
            hits.append(dict(command_index=row['command_index'], attempt_ordinal=row['attempt_ordinal'],
                             committed_fraction=row['committed_fraction'], truefraction=row['truefraction'],
                             committed_hit_body=row['end'], front_is_live=active,
                             # False marks a fresh entry; True a re-contact from bias distance.
                             previous_command_native_ramp=row['command_index']-1 in ramped,
                             hypothetical_down_reachable=bool(at['polygon']),
                             down_distance_range=at['reach_distance_range'],
                             requested_sweep_front_entry=wanted[0] if wanted else None,
                             front_entry_minus_truefraction=late,
                             # Along the NATIVE contact plane's normal, which is not the front's.
                             front_entry_after_native_along_contact_normal=late*closing if wanted else None,
                             requested_sweep_basis='CAPTURED_REQUEST_NOT_COMMITTED_PATH'))
    return dict(label=previous['label'], active=active, command_count=count, segment_count=len(owners),
                point_segment_count=sum(r['start'] == r['end'] for r in owners), commands=commands, track=track,
                native_hits=hits, in_place_edge_nonempty_count=edges,
                kinked_commands=[c['command_index'] for c in commands if not c['path_is_endpoint_chord']],
                resolved_kink_commands=[c['command_index'] for c in commands if c['kink_resolved']],
                coverage_differs_from_chord_commands=[c['command_index'] for c in commands
                                                      if c['chord_comparison'] == 'DIFFERS'],
                coverage_differs_below_float32_commands=[c['command_index'] for c in commands
                                                         if c['chord_comparison'] == 'DIFFERS_BELOW_FLOAT32_KINK'],
                **ramp_versus_reach([(c['command_index'], c['native_ramp_return'], c['hypothetical_down'])
                                     for c in commands if active]),
                trajectory_basis='CAPTURED_NATIVE_COMMITTED_SEGMENTS_LINEAR_WITHIN_A_SEGMENT_NEVER_ACROSS_A_COMMAND',
                geometry_basis='AUTHORED_FIXTURE_FRONT_NOT_COPIED_NEIGHBORHOOD', share_basis=SHARE_BASIS,
                horizon_basis='hypothetical_down IS THE CLOSED RANGE 0<=d<=2 AND CONTAINS in_place')


def assess(native, derived):
    require(native['prior_plane_set_report'] == derived['prior_plane_set_report'], 'prior reports differ between readers')
    previous = native['prior_plane_set_report']['prior_pm_report']['cases']
    require(len(native['cases']) == len(previous) == len(derived['cases']) == 3, 'committed reach requires the three actors')
    cases = [assess_case(n, p, d, i) for i, (n, p, d) in enumerate(zip(native['cases'], previous, derived['cases']))]
    edges = sum(c['in_place_edge_nonempty_count'] for c in cases)
    require(sum(c['segment_count'] for c in cases) == native['actual_committed_segment_count'] and edges > 0 and
            cases[1]['track']['hypothetical_down']['front_coverage'],
            'committed segments, in-place edge or removed-front counterfactual did not ACT')
    resolved = sum(len(c['resolved_kink_commands']) for c in cases)
    differs = sum(len(c['coverage_differs_from_chord_commands']) for c in cases)
    probes = [c['track'][n]['common_point_probes'] for c in cases for n, _ in HORIZONS]
    derived = dict(derived); derived['prior_plane_set_report'] = 'IDENTICAL_TO_prior_path_report.prior_plane_set_report'
    return dict(bounded_committed_path_front_reach_gates='PASS', contract=CONTRACT, cases=cases,
                committed_segment_count=sum(c['segment_count'] for c in cases),
                point_segment_count=sum(c['point_segment_count'] for c in cases),
                kinked_command_count=sum(len(c['kinked_commands']) for c in cases), resolved_kink_command_count=resolved,
                coverage_differs_from_chord_command_count=differs,
                committed_path_vs_chord='ACTED' if differs else 'RESOLVED_KINK_COVERAGE_EQUAL' if resolved else 'NOT_ACTED',
                live_interior_gap_recontact=recontact_verdict(
                    [r for c in cases for n, _ in HORIZONS for r in c['track'][n]['live_regained']]),
                common_point_probes=dict(parameters=sum(p['parameters'] for p in probes),
                                         inside_coverage=sum(p['inside_coverage'] for p in probes),
                                         live_inside_coverage=sum(c['track'][n]['common_point_probes']['inside_coverage']
                                                                  for c in cases if c['active'] for n, _ in HORIZONS)),
                in_place_edge_checks=dict(segments=sum(c['segment_count'] for c in cases), nonempty=edges),
                rational_basis='EXACT_ARITHMETIC_ON_SERIALIZED_DECIMALS_NOT_MEASUREMENT_PRECISION',
                prior_path_report=native, prior_derived_front_report=derived,
                general_triangle_support='ABSTAIN', native_front_reach_equivalence='NOT_CLAIMED',
                physical_exit_acceptance='NOT_TESTED', standability_load_bearing_acceptance='NOT_TESTED',
                discovered_neighborhood_topology='NOT_IMPLEMENTED', classifier_render_hold_clock='NOT_TESTED',
                recovery_cached_portal_ground_slide_acceptance='NOT_TESTED')


def compare(*texts):
    return assess(path.compare(*texts), reach.compare(*texts))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if a.output.exists():
        ap.error('Need NEW output file; refusing to overwrite retained evidence')
    texts, provenance = path.load_arms(a.arms)
    result = compare(*texts); result['arms'] = provenance
    result['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(reach.encoded(result), indent=2, allow_nan=False)+'\n')
    probes = result['common_point_probes']
    print(f"PASS {result['committed_segment_count']} committed segments, {probes['parameters']} probes "
          f"({probes['inside_coverage']} inside coverage, {probes['live_inside_coverage']} live); "
          f"in-place edge non-empty on {result['in_place_edge_checks']['nonempty']}; "
          f"chord {result['committed_path_vs_chord']} in {result['coverage_differs_from_chord_command_count']}; "
          f"recontact {result['live_interior_gap_recontact']}; support ABSTAIN; exit NOT_TESTED")


if __name__ == '__main__':
    main()
