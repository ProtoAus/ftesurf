#!/usr/bin/env python3
"""Acted static-brush native trajectories + full native/joint convex queries.

No halfspace max-gap classification. Ground/airborne AABB cases use a bounded
joint oracle; ACTED capsule, transformed, non-world, embedded and triangle cases ABSTAIN
from geometry/support. None is a continuous physical-exit timestamp or general marker policy.
"""
import argparse
from collections import Counter
import hashlib
from functools import lru_cache
from itertools import combinations
import json
import math
from pathlib import Path
import re

from offramp_buffer import require, parse as buffer_parse
from offramp_hull import decode as hull_decode
from offramp_origin import CHECKS as ORIGIN_CHECKS, integers, parse as origin_parse
from offramp_shape import category as shape_category, decode as shape_decode

LABELS = ('interior-ride', 'partial-full-side-exit', 'convex-side-exit',
          'interior-input-departure', 'ground-jump', 'overlapping-brush-seam',
          'open-ground-duck-cycle', 'ceiling-blocked-unduck', 'capsule-ramp-side-departure',
          'translated-yaw-brush-departure', 'non-world-physent-departure', 'removed-physent-control',
          'embedded-model-departure', 'removed-embedded-model-control',
          'triangle-departure', 'removed-triangle-control',
          'airborne-duck-cycle', 'airborne-standing-control',
          'grounded-cached-ramp-approach', 'removed-ramp-approach-control')
TRIANGLE_VERTICES = [-256, -64, 256*.8/.6, -256, 64, 256*.8/.6, 256, 0, -256*.8/.6]
ENTITY_MODEL = '*authored_offramp_entity'
EMBEDDED_MODEL = '*authored_offramp_embedded'
EMBEDDED_AXIS = [1, 0, 0, 0, 1, 0, 0, 0, 1]
WORLD_MODEL = 'maps/authored_offramp_motion.bsp'
INSTANCE = [9, 0, 1000, -300, 100, 0, 45, 0, 1, 0]
STEPS = 32
MAX_STEPS = 192


def step_count(case): return 64 if case >= 16 else (STEPS if case < 6 or case >= 8 else (96 if case == 6 else MAX_STEPS))
WIDTHS = {'BEGIN': 5, 'SOURCE': 2, 'PARAM': 2, 'CASE': 4, 'BRUSH': 9, 'PLANE': 7,
          'INSTANCE': 10, 'SET': 3, 'PHYSENT': 6, 'EMBED': 19, 'TRIANGLE': 15, 'BRUSHSET': 4, 'SEED': 13, 'TICK': 28, 'ORACLE': 19, 'CASE_END': 2, 'END': 1, 'COMPLETE': 0}
PARAMS = dict(zip(('physicsmode ticrate gravity entgravity maxspeed spectatormaxspeed maxairspeed maxvelocity '
                   'accelerate airaccelerate wateraccelerate friction waterfriction stopspeed stepheight '
                   'jumpvelocity standablenormal standheight duckheight duckspeed viewheight duckviewheight '
                   'viewscale walkspeed groundtracedist bumpcount snaptoground groundquadrants fixslopes '
                   'fixedges fixrampbugs rampretrace ladders slide stamina normalizejump jumpaddrise '
                   'jumpzoffset autobunny flags coord_float32 rotatedboxhulls trisoup_bevels').split(),
                  (1, .015, 800, 1, 250, 250, 30, 3500, 5, 150, 10, 4, 1, 75, 18,
                   301.9933774, .7, 62, 45, .34, 64, 47, .5, .52, 2, 8, 1, 1, 1, 1, 2, .2,
                   0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1)))
EPS = 1e-5  # Numeric feasibility tolerance, NOT a collision/classification gap.


def numbers(words):
    try: v = [float(w) for w in words]
    except ValueError as e: raise AssertionError('nonnumeric motion row') from e
    require(all(math.isfinite(x) and abs(x) <= 3.4028235e38 for x in v), 'nonfinite motion row')
    return v


def close(a, b, tol=1e-4):
    return len(a) == len(b) and all(abs(x-y) <= tol for x, y in zip(a, b))


def parse(text):
    rows = []
    for line in text.splitlines():
        p = line.find('OFFRAMPMOTION_')
        if p < 0: continue
        w = line[p:].split(); tag = w[0].removeprefix('OFFRAMPMOTION_')
        require(tag in WIDTHS and len(w)-1 == WIDTHS[tag], 'unknown/malformed motion row')
        rows.append((tag, w[1:]))
    return rows


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def dot(a, b): return sum(x*y for x, y in zip(a, b))


def joint_overlap(planes, mins, maxs):
    return _joint_overlap(tuple(tuple(p) for p in planes), tuple(mins), tuple(maxs))


@lru_cache(maxsize=4096)
def _joint_overlap(planes, mins, maxs):
    """Bounded joint brush/query-AABB feasibility, NOT expanded-face maxima.

    A bounded intersection has a vertex. Enumerate three-plane vertices of
    brush + query-box constraints and test every inequality at the SAME point.
    """
    constraints = [list(p) for p in planes]
    for i in range(3):
        n = [0, 0, 0]; n[i] = 1
        constraints += [n+[maxs[i]], [-v for v in n]+[-mins[i]]]
    for a, b, c in combinations(constraints, 3):
        bc, ca, ab = cross(b[:3], c[:3]), cross(c[:3], a[:3]), cross(a[:3], b[:3])
        det = dot(a[:3], bc)
        if abs(det) < 1e-10: continue
        p = [(a[3]*bc[i]+b[3]*ca[i]+c[3]*ab[i])/det for i in range(3)]
        if all(dot(q[:3], p) <= q[3]+EPS for q in constraints): return True
    return False


def authored(case):
    count = 2 if case in (5, 7) or 10 <= case < 16 or case >= 18 else 1
    brushes = []
    for b in range(count):
        lo = [-256, -256 if case == 2 else (-8 if b else -64), -512]
        hi = [256, 256 if case == 2 else ((192 if b else 0) if case == 5 else 64), 512]
        if case >= 18: lo[1] = -64 if b else -256
        if 10 <= case < 16: lo[1], hi[1] = (-64, 64) if b else (-1024, -896)
        planes = [[1, 0, 0, hi[0]], [-1, 0, 0, -lo[0]], [0, 1, 0, hi[1]], [0, -1, 0, -lo[1]],
                  [0, 0, -1, 512], [0 if case == 4 else .8, 0, 1 if case == 4 else .6, 0]]
        if case == 2: planes += [[math.sqrt(.5), math.sqrt(.5), 0, 0]]
        if case in (6, 7, 16, 17) or (case >= 18 and not b):
            lo = [-32, -128, 50] if b else [-256, -256, -512]
            hi = [32, 128, 128] if b else [256, 256, 0]
            planes = [[1, 0, 0, hi[0]], [-1, 0, 0, -lo[0]], [0, 1, 0, hi[1]],
                      [0, -1, 0, -lo[1]], [0, 0, -1, -lo[2]], [0, 0, 1, hi[2]]]
        if case >= 18 and b: planes[5] = [-.8, 0, .6, 0]
        brushes.append({'mins': lo, 'maxs': hi, 'planes': planes})
    x, y = (-40 if case == 2 else -100), (76 if case == 1 else (-32 if case == 5 else 0))
    z = .05 if case == 4 else (12.8-.8*x+.05)/.6
    seed = [x, y, z, 0 if case == 3 else (60 if case == 4 else 300),
            250 if case in (1, 2, 5) or case >= 10 else 0, 0 if case in (3, 4) else -400, -16, -16, 0, 16, 16, 62]
    if case in (6, 7): seed = [-100, 0, .05, 0, 0, 0, -16, -16, 0, 16, 16, 62]
    if case in (16, 17): seed = [-100, 0, 128, 60, 0, 0, -16, -16, 0, 16, 16, 62]
    if case >= 18: seed = [-100, 0, .05, 250, 0, 0, -16, -16, 0, 16, 16, 62]
    if case == 8: seed = [-100, 0, (6.4+80+.05)/.6, 300, 250, -400, -16, -16, 0, 16, 16, 62]
    if case == 9:
        s = math.sqrt(.5)
        seed = [1000-100*s, -300-100*s, 100+(16*.8*math.sqrt(2)+80+.05)/.6,
                50*s, 550*s, -400, -16, -16, 0, 16, 16, 62]
    return brushes, seed


def native_plane(plane, transformed):
    # BIH rotates normal; PM wrapper does NOT translate plane.dist. This binds
    # the mixed native snapshot contract, NOT an independent world plane.
    if not transformed: return plane
    s = math.sqrt(.5)
    x, y, z, d = plane
    return [s*(x-y), s*(x+y), z, d]


def hit(row): return row[10] < 1 and row[11] == row[12] == 0


def oracle_validate(row, tick, brushes):
    case, ordinal = integers(row[:2]); kind = row[2]; brush = integers(row[3:4])[0]
    v = numbers(row[4:]); start, end = v[:3], v[3:6]
    require(0 <= v[6] <= 1 and all(f in (0, 1) for f in integers(row[11:13])) and
            v[8] <= v[7] and (kind in ('standing', 'box', 'identity', 'rampdown2') or integers(row[11:13]) == [0, 0]), 'invalid/embedded authored oracle fraction/flags')
    contents = integers(row[18:])[0]
    require(0 <= contents <= 0xffffffff, 'invalid oracle contents')
    pos, mins, maxs = tick[10:13], tick[16:19], tick[19:22]
    if kind == 'standing': maxs = maxs[:2]+[mins[2]+PARAMS['standheight']]
    expected_start, expected_end = pos[:], pos[:]
    if kind in ('down2', 'identity', 'worldonly', 'unembedded', 'untriangled', 'rampdown2', 'unramped'): expected_end[2] -= 2
    elif kind == 'projected':
        p = brushes[0]['planes'][5]
        low = sum(n*(hi if n < 0 else lo) for n, lo, hi in zip(p[:3], mins, maxs))
        z = (p[3]-low-p[0]*pos[0]-p[1]*pos[1])/p[2]
        expected_start[2], expected_end[2] = z+2, z-2
    else: require(kind in ('stationary', 'standing', 'box'), 'unknown oracle query kind')
    require(close(start, expected_start) and close(end, expected_end), 'oracle endpoints not bound to actual tick hull/point')
    if case >= 18:
        require(tick[:2] == [case, ordinal] and tick[25] == 0 and
                kind in ('stationary', 'down2', 'rampdown2', 'unramped') and
                brush == (1 if kind == 'rampdown2' else (0 if kind == 'unramped' else -1)),
                'unregistered cached-approach query')
    elif 10 <= case < 16:
        removal = 'untriangled' if case >= 14 else ('unembedded' if case >= 12 else 'worldonly')
        require(tick[:2] == [case, ordinal] and tick[25] == 0 and
                kind in ('stationary', 'down2', removal) and brush == (0 if kind == removal else -1),
                'unregistered entity/embedded/triangle query')
    else:
        require(kind not in ('worldonly', 'unembedded', 'untriangled', 'rampdown2', 'unramped') and -1 <= brush < len(brushes), 'unregistered query brush/removal')
    subset = brushes if brush == -1 else [brushes[brush]]
    if case == 19 and brush == -1: subset = brushes[:1]
    if case in (11, 13, 14, 15): subset = brushes[:1]
    elif case == 12 and kind != 'unembedded': subset = brushes[1:2]
    lo = [min(a, b)+m for a, b, m in zip(start, end, mins)]
    hi = [max(a, b)+m for a, b, m in zip(start, end, maxs)]
    native = v[6] < 1 or bool(v[7] or v[8])
    expected_entity = ((0 if case >= 12 else 1) if native else -1) if 10 <= case < 16 else 0
    require(integers(row[13:14]) == [expected_entity], 'oracle fixture entity binding changed')
    if tick[25]:
        require(case == 8 and kind in ('stationary', 'down2', 'box') and brush == -1,
                'unregistered capsule query')
    else:
        require(kind != 'box', 'box counterfactual lacks actual capsule')
    if case == 9:
        require(tick[:2] == [case, ordinal] and tick[25] == 0 and
                kind in ('stationary', 'down2', 'identity') and brush == -1,
                'unregistered transformed query')
        if kind == 'identity':
            lo = [a-b for a, b in zip(lo, INSTANCE[2:5])]
            hi = [a-b for a, b in zip(hi, INSTANCE[2:5])]
    else:
        require(kind != 'identity', 'identity query lacks transformed actor')
    # No joint AABB substitution for actual capsule, rotated or triangle geometry.
    # BOX, translated-only identity and remote-only queries may use joint AABB.
    if ((not tick[25] or kind == 'box') and (case != 9 or kind == 'identity') and
            (case != 14 or kind == 'untriangled')):
        joint = any(joint_overlap(b['planes'], lo, hi) for b in subset)
        require(native == joint, 'native query disagrees with JOINT convex oracle')
    if kind == 'stationary': require(not native, 'authored mover ended embedded in solid')
    if v[7] or v[8]:
        require(((kind == 'identity' or (case == 19 and kind == 'rampdown2')) and
                 v[6:9] == [1, 1, 1] and v[10:14] == [0, 0, 0, 0] and contents == 0) or
                (kind in ('standing', 'box') and contents == 1 and
                 (v[10:14] == [0, 0, 0, 0] or any(close(v[10:14], p) for b in subset for p in b['planes']))),
                'counterfactual solid not bound to authored collider/native contract')
    elif v[6] < 1 and case == 14:
        # Native triangle/slab/bevel plane only. No brush oracle substitution.
        require(contents == 1 and abs(math.sqrt(dot(v[10:13], v[10:13]))-1) < 1e-5,
                'triangle native winning plane/contents invalid')
    elif v[6] < 1:
        winner_brushes = brushes[1:2] if 10 <= case < 16 else subset
        require(any(close(v[10:14], native_plane(p, case == 9 and kind != 'identity'))
                    for b in winner_brushes for p in b['planes']) and contents == 1,
                'oracle winning plane/contents not authored collider')
    else:
        require(v[10:14] == [0, 0, 0, 0] and contents == 0, 'missed oracle query promoted stale winning data')
    # Mixed row: numeric selectors followed by strings, then numeric results.
    return [case, ordinal, kind, brush]+v


def bind_capture(text, case, ticks, brushes):
    steps = step_count(case)
    buffer, order = buffer_parse(text)
    contacts = buffer['CONTACT']
    require(buffer['BEGIN'] == [[1, 32768]] and buffer['END'] == [[steps, len(contacts), 0]] and
            order == ['BEGIN']+['TICK']*steps+['CONTACT']*len(contacts)+['END'], 'invalid case native capture envelope')
    require(len(buffer['TICK']) == steps, 'missing captured native tick')
    for i, (r, t) in enumerate(zip(buffer['TICK'], ticks)):
        require(r[:4] == [i, i, i+1, i+1] and close(r[4:7], [t[7], t[8], t[9]]) and
                r[7:13] == t[10:16], 'motion not bound to actual captured native tick')
    origins, order = origin_parse(text)
    require(origins['CHECK'] == [[str(i), name, '1'] for i, name in enumerate(ORIGIN_CHECKS, 1)] and
            origins['SELFTEST'] == [[str(len(ORIGIN_CHECKS)), '0']] and
            order == ['CHECK']*len(ORIGIN_CHECKS)+['SELFTEST']+['CONTACT']*len(contacts), 'missing/failed case origin setup')
    origin_rows = [integers(w[:9])+[w[9]] for w in origins['CONTACT']]
    payloads, shapes, _ = shape_decode(text, contacts, origin_rows)
    ht, hc, _ = hull_decode(text, buffer['TICK'], contacts, shapes)
    per_tick = Counter(); winners = []
    for i, (r, o, s) in enumerate(zip(contacts, origin_rows, shapes)):
        require(r[0] == i and int(r[1]) == r[1] and 0 <= r[1] < steps and 0 <= r[4] <= 1 and
                int(r[2]) == r[2] and 0 <= r[2] < 8 and r[3] == (1 if case == 10 else 0) and r[21:] == [0, 0, 0], 'invalid accepted fixture trace')
        require(o[:2] == [i, int(r[1])] and o[8] == (1 if case == 10 else 0) and o[3] == (2 if case == 14 else 1) and o[4] >= 0 and o[5] >= 0 and
                o[6] == (1 if case == 12 else 0) and o[7] == 1, 'accepted origin not bound to fixture collider')
        p = payloads[s['payload_id']]
        reason, _ = shape_category(o, r, s, p, 'authored_offramp_motion')
        expected_reason = {8: 'capsule-hull-unsupported', 9: 'transformed-instance-unsupported', 10: 'entity-unsupported', 12: 'embedded-model-unsupported', 14: 'world-triangle-unresolved'}.get(case, 'copied-world-brush-plane-bound')
        require(reason == expected_reason, 'fixture winning shape incorrectly promoted/unsupported')
        if case == 14:
            require(o[2] == 0 and o[4:7] == [0, 0, 0] and o[9] == WORLD_MODEL and
                    p['status'] == 0 and p['source_side_count'] == 0 and not p['planes'] and
                    s['capsule'] == 0 and s['direct_bih_callback'] == 1 and
                    s['instance_origin'] == s['instance_angles'] == [0]*3 and s['raw_instance_scale'] == 1 and
                    hc[i]['capsule'] == 0 and
                    [hc[i]['pm_type'], hc[i]['ducked'], hc[i]['ducking'], hc[i]['ducktime_ms'], hc[i]['oldbuttons']] == [0]*5 and
                    hc[i]['mins'] == [-16, -16, 0] and hc[i]['maxs'] == [16, 16, 62] and
                    abs(math.sqrt(dot(r[6:9], r[6:9]))-1) < 1e-5,
                    'triangle winner/empty brush payload/instance/hull not bound')
            per_tick[int(r[1])] += 1
            winners.append({'ordinal': i, 'tick': int(r[1]), 'leaf': o[4], 'rootleaf': o[5],
                            'physent_index': o[8], 'model': o[9], 'geometry_status': reason,
                            'native_plane': r[6:9]+[r[5]],
                            'instance': {k: s[k] for k in ('instance_origin', 'instance_angles', 'raw_instance_scale', 'direct_bih_callback')}})
            continue
        matches = [b for b, a in enumerate(brushes) if close(p['model_local_mins'], a['mins']) and close(p['model_local_maxs'], a['maxs']) and
                   len(p['planes']) == len(a['planes']) and all(close(q, z) for q, z in zip(p['planes'], a['planes']))]
        require(len(matches) == 1 and s['capsule'] == int(case == 8), 'winning copied shape not an authored whole brush')
        if case == 12:
            require(matches == [1] and o[2] == 0 and o[4:7] == [0, 0, 1] and o[9] == EMBEDDED_MODEL and
                    s['instance_origin'] == s['instance_angles'] == [0]*3 and
                    s['raw_instance_scale'] == 1 and s['direct_bih_callback'] == 1 and p['status'] == 1 and
                    r[6:9]+[r[5]] in p['planes'] and hc[i]['capsule'] == 0 and
                    [hc[i]['pm_type'], hc[i]['ducked'], hc[i]['ducking'], hc[i]['ducktime_ms'], hc[i]['oldbuttons']] == [0]*5 and
                    hc[i]['mins'] == [-16, -16, 0] and hc[i]['maxs'] == [16, 16, 62],
                    'embedded winner/child/root/depth/brush/instance/hull not bound')
        if case == 10:
            require(matches == [1] and o[2] == 0 and o[4:7] == [0, 0, 0] and o[9] == ENTITY_MODEL and
                    s['instance_origin'] == s['instance_angles'] == [0]*3 and
                    s['raw_instance_scale'] == 1 and s['direct_bih_callback'] == 1 and p['status'] == 1 and
                    r[6:9]+[r[5]] in p['planes'] and hc[i]['capsule'] == 0 and
                    [hc[i]['pm_type'], hc[i]['ducked'], hc[i]['ducking'], hc[i]['ducktime_ms'], hc[i]['oldbuttons']] == [0]*5 and
                    hc[i]['mins'] == [-16, -16, 0] and hc[i]['maxs'] == [16, 16, 62],
                    'entity winner/model/brush/instance/hull not bound')
        if case == 9:
            require(s['instance_origin'] == INSTANCE[2:5] and s['instance_angles'] == INSTANCE[5:8] and
                    s['raw_instance_scale'] == INSTANCE[8] and s['direct_bih_callback'] == 1 and p['status'] == 1 and
                    any(close(r[6:9], native_plane(plane, True)[:3], 1e-5) and r[5] == plane[3] for plane in p['planes']) and
                    hc[i]['capsule'] == 0 and
                    [hc[i]['pm_type'], hc[i]['ducked'], hc[i]['ducking'], hc[i]['ducktime_ms'], hc[i]['oldbuttons']] == [0]*5 and
                    hc[i]['mins'] == [-16, -16, 0] and hc[i]['maxs'] == [16, 16, 62],
                    'transformed instance/accepted normal/hull snapshot not bound')
        if case == 8:
            require(r[6:9]+[r[5]] in p['planes'] and hc[i]['capsule'] == 1 and
                    [hc[i]['pm_type'], hc[i]['ducked'], hc[i]['ducking'], hc[i]['ducktime_ms'], hc[i]['oldbuttons']] == [0]*5 and
                    hc[i]['mins'] == [-16, -16, 0] and hc[i]['maxs'] == [16, 16, 62],
                    'capsule accepted plane/hull snapshot not bound')
        if case == 18:
            require(o[2] in (0, 1) and matches == [1] and o[6] == 0 and o[9] == WORLD_MODEL and
                    p['status'] == 1 and s['direct_bih_callback'] == 1 and
                    s['instance_origin'] == s['instance_angles'] == [0]*3 and s['raw_instance_scale'] in (0, 1) and
                    close(r[6:9]+[r[5]], [-.8, 0, .6, 0]) and r[15:21] == [-16, -16, 0, 16, 16, 62] and
                    [hc[i]['pm_type'], hc[i]['ducked'], hc[i]['ducking'], hc[i]['ducktime_ms'], hc[i]['oldbuttons']] == [0]*5,
                    'cached-approach winner/route/plane/shape/instance/hull not bound')
        per_tick[int(r[1])] += 1
        winners.append({'ordinal': i, 'tick': int(r[1]), 'brush': matches[0], 'leaf': o[4], 'rootleaf': o[5]})
        if case == 18:
            winners[-1].update(originroute=o[2], bump=int(r[2]), fraction=r[4], native_plane=r[6:9]+[r[5]],
                               sweep_start=r[9:12], sweep_end=r[12:15])
        if case in (8, 9, 10, 12): winners[-1]['geometry_status'] = reason
        if case == 10: winners[-1].update(physent_index=o[8], model=o[9])
        if case == 12: winners[-1].update(physent_index=o[8], model=o[9], child_leaf=o[4], root_leaf=o[5], embedded_depth=o[6])
        if case == 9:
            winners[-1]['instance'] = {k: s[k] for k in ('instance_origin', 'instance_angles', 'raw_instance_scale', 'direct_bih_callback')}
    for i, (h, t) in enumerate(zip(ht, ticks)):
        require(h['mins'] == t[16:19] and h['maxs'] == t[19:22] and
                [h['ducked'], h['ducking'], h['ducktime_ms'], h['capsule'], h['pm_type'], h['oldbuttons']] == t[22:] and
                close([h['raw_standheight'], h['raw_duckheight']], [62, 45]), 'actual tick hull/posture mismatch')
        require(bool(per_tick[i]) == bool(t[8]), 'ramp flag lacks ACTED accepted contact')
    if case == 18: assess_cached_capture(ticks, winners)
    return winners


def assess_cached_capture(ticks, winners):
    cached = [w for w in winners if w['originroute'] == 1]
    require(cached, 'native cached firsttrace branch did not ACT')
    first = min(w['tick'] for w in cached)
    require(0 < first < len(ticks) and ticks[first-1][8:10] == [0, 1],
            'cached first impact did not follow native grounded approach')
    for w in cached:
        i = w['tick']
        require(0 < i < len(ticks), 'cached trace tick outside native body envelope')
        prior = ticks[i-1]
        # Only this prescribed one-dimensional standing ground command, NOT a
        # generalized mover solver or physical-support oracle.
        speed = prior[13]
        requested = min(PARAMS['maxspeed'], max(0, speed-max(PARAMS['stopspeed'], speed)*PARAMS['friction']*.015)
                        + PARAMS['accelerate']*PARAMS['maxspeed']*.015)
        require(w['bump'] == 0 and w['brush'] == 1 and prior[9] == 1 and
                prior[14:16] == [0, 0] and speed > 0 and 0 <= w['fraction'] < 1 and
                close(w['native_plane'], [-.8, 0, .6, 0]) and
                close(w['sweep_start'], ticks[i-1][10:13]) and
                close(w['sweep_end'], [w['sweep_start'][0]+requested*.015, w['sweep_start'][1], w['sweep_start'][2]]),
                'cached firsttrace not bound to prior ground/horizontal requested native sweep')


def grade(text):
    require('all checks passed' in text and len(re.findall(r'\bok\s+', text)) >= 100 and
            not any(s in text for s in ('Unknown command', 'QC VM error', 'SV_Error', 'check(s) FAILED', 'OFFRAMPMOTION_REFUSE')), 'native command/setup did not ACT')
    rows = parse(text); pos = 0
    def take(tag):
        nonlocal pos
        require(pos < len(rows) and rows[pos][0] == tag, f'missing/duplicate/reordered motion {tag}')
        w = rows[pos][1]; pos += 1; return w
    header = integers(take('BEGIN'))
    require(header[0] == 9 and header[1] in (0, 1) and header[2] in (0, 1) and header[3:] == [len(LABELS), MAX_STEPS], 'unsupported motion header')
    capture, oracle = header[1:3]
    source = take('SOURCE')
    require(re.fullmatch('[0-9a-f]{64}', source[0]) and re.fullmatch('[0-9a-f]{40}', source[1]), 'invalid fixture/source stamp')
    for name, expected in PARAMS.items():
        p = take('PARAM'); require(p[0] == name and close(numbers(p[1:]), [expected], 1e-4), 'wrong/duplicate native input profile')
    cases = []
    blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', text, flags=re.S)
    require(len(blocks) == len(LABELS), 'missing/duplicate native case block')
    legacy = ('OFFRAMPBUF_', 'OFFRAMPORIGIN_', 'OFFRAMPGEOM_', 'OFFRAMPHULL_')
    legacy_count = lambda s: sum(any(p in line for p in legacy) for line in s.splitlines())
    require(legacy_count(text) == sum(legacy_count(b) for b in blocks), 'capture rows outside native case envelope')
    if not capture:
        require(not any(s in text for s in ('OFFRAMPBUF_', 'OFFRAMPORIGIN_', 'OFFRAMPGEOM_', 'OFFRAMPHULL_')), 'fixture-only/OFF capture not quiet')
    for c, label in enumerate(LABELS):
        steps = step_count(c)
        authored_brushes, seed = authored(c); case = take('CASE')
        require(case == [str(c), label, str(steps), str(len(authored_brushes))], 'wrong case actor/header')
        brushes = []
        for b, expected in enumerate(authored_brushes):
            row = take('BRUSH'); require(integers(row[:3]) == [c, b, len(expected['planes'])] and close(numbers(row[3:]), expected['mins']+expected['maxs']), 'wrong authored brush')
            planes = []
            for i, p in enumerate(expected['planes']):
                r = take('PLANE'); require(integers(r[:3]) == [c, b, i] and close(numbers(r[3:]), p, 1e-5), 'missing/changed/unordered authored plane')
                planes.append(numbers(r[3:]))
            brushes.append({'mins': numbers(row[3:6]), 'maxs': numbers(row[6:]), 'planes': planes})
        if c == 9: require(numbers(take('INSTANCE')) == INSTANCE, 'changed/invalid actual transformed instance')
        if 10 <= c < 16:
            entity_set = integers(take('SET'))
            require(entity_set == [c, 2 if c == 10 else 1, -1], 'changed/invalid entity physent set')
            physents, instances = [], []
            for b in range(1 if c >= 12 else 2):
                pe = take('PHYSENT')
                require(pe == [str(c), str(b), str(42 if b else 0), ENTITY_MODEL if b else WORLD_MODEL,
                               str(-1 if c in (12, 14) else b), str(int(b < entity_set[1]))], 'changed/unordered entity physent binding')
                instance = numbers(take('INSTANCE'))
                require(instance == [c, b, 0, 0, 0, 0, 0, 0, 1, 0], 'changed/invalid entity instance')
                physents.append(pe); instances.append(instance)
        if 14 <= c < 16:
            triangle = take('TRIANGLE')
            require(integers(triangle[:6]) == [c, int(c == 14), 0 if c == 14 else -1, 0, 1, 2] and
                    close(numbers(triangle[6:]), TRIANGLE_VERTICES), 'changed/invalid triangle fixture wiring')
        elif 12 <= c < 14:
            embed = take('EMBED')
            require(integers(embed[:5]) == [c, 0, 0, 1, int(c == 12)] and
                    embed[5:7] == ['model' if c == 12 else 'brush', EMBEDDED_MODEL] and
                    numbers(embed[7:]) == [0]*3+EMBEDDED_AXIS, 'changed/invalid embedded root/child/transform')
        if c >= 18:
            brushset = integers(take('BRUSHSET'))
            require(brushset == [c, 2 if c == 18 else 1, 1, int(c == 18)], 'changed/invalid actual cached-approach brush set')
        r = take('SEED'); require(integers(r[:1]) == [c] and close(numbers(r[1:]), seed), 'wrong/changed case seed')
        ticks, queries = [], []
        for i in range(steps):
            t = numbers(take('TICK'))
            forward = 250 if c in (6, 7, 18, 19) or (c == 3 and i == 3) else 0
            buttons = (8 if 3 <= i <= (34 if c == 6 else 44) else 0) if c in (6, 7) else (
                (8 if 3 <= i <= 10 else 0) if c == 16 else (2 if c == 4 and i == 3 else 0))
            require(t[:7] == [c, i, 15, forward, 0, buttons, 1] and
                    close(t[7:8], [.015], 1e-8) and t[8] in (0, 1) and t[9] in (0, 1) and
                    t[16:21] == [-16, -16, 0, 16, 16] and t[21] in (45, 62) and
                    t[22] in (0, 1) and t[23] in (0, 1) and 0 <= t[24] <= 1000 and t[25:27] == [int(c == 8), 0] and
                    t[27].is_integer() and 0 <= t[27] <= 255 and
                    (c in (6, 7, 16) or (t[21] == 62 and t[22:25] == [0, 0, 0])), 'wrong command/tick/hull actor')
            ticks.append(t)
            qrows = []
            if oracle:
                query_order = [('stationary', -1), ('down2', -1), ('rampdown2', 1), ('unramped', 0)] if c >= 18 else (
                    [('stationary', -1), ('down2', -1), ('untriangled' if c >= 14 else ('unembedded' if c >= 12 else 'worldonly'), 0)] if 10 <= c < 16 else (
                    [('stationary', -1), ('down2', -1), ('box' if c == 8 else 'identity', -1)] if 8 <= c < 10 else [
                    ('stationary', -1), ('down2', -1), ('projected', -1),
                    *[('projected', b) for b in range(len(brushes))], *([('standing', -1)] if c in (6, 7, 16, 17) else [])]))
                for kind, brush in query_order:
                    row = take('ORACLE'); require(integers(row[:2]) == [c, i] and row[2:4] == [kind, str(brush)], 'oracle not bound/ordered to native case tick')
                    qrows.append(oracle_validate(row, t, brushes))
            queries.append(qrows)
        require(integers(take('CASE_END')) == [c, steps] and math.dist(ticks[-1][10:13], seed[:3]) > 1, 'native trajectory did not ACT')
        winners = bind_capture(blocks[c], c, ticks, brushes) if capture else []
        cases.append({'label': label, 'brushes': brushes, 'seed': numbers(r[1:]), 'ticks': ticks, 'oracles': queries, 'accepted': winners})
        if c >= 18: cases[-1]['brushset'] = brushset
        if c == 9: cases[-1]['instance'] = INSTANCE[:]
        if 10 <= c < 16: cases[-1].update(physent_set=entity_set, physents=physents, instances=instances)
        if 14 <= c < 16: cases[-1]['triangle'] = triangle
        elif 12 <= c < 14: cases[-1]['embedded'] = embed
    require(integers(take('END')) == [len(LABELS)] and take('COMPLETE') == [] and pos == len(rows), 'missing/duplicate motion completion')
    if oracle:
        assess_posture(*cases[6:8])
        assess_capsule(cases[8])
        assess_transform(cases[9])
        assess_entity(*cases[10:12])
        assess_embedded(*cases[12:14])
        assess_triangle(*cases[14:16])
        assess_airposture(*cases[16:18])
        assess_cached_actor(*cases[18:20])
    return {'capture': capture, 'oracle': oracle, 'source': source, 'cases': cases}


def assess_posture(open_cycle, ceiling):
    for c in (open_cycle, ceiling):
        ts, qs = c['ticks'], c['oracles']
        require(len(ts) == step_count(LABELS.index(c['label'])) and all(t[9] == 1 and t[8] == 0 for t in ts), 'posture ground actor failed')
        require(all(t[21] == (45 if t[22] else 62) and (int(t[27]) & 8) == t[5] for t in ts),
                'posture hull/button state is not an actual transition')
        down = [i for i, t in enumerate(ts) if t[5] == 8 and t[23] == 1 and t[22] == 0 and t[21] == 62]
        crouch = [i for i, t in enumerate(ts) if t[5] == 8 and t[22] == 1 and t[23] == 0 and t[21] == 45]
        up = [i for i, t in enumerate(ts) if t[5] == 0 and t[22:24] == [1, 1] and t[21] == 45]
        stand = [i for i, t in enumerate(ts) if i > 34 and t[5] == 0 and t[22:25] == [0, 0, 0] and t[21] == 62]
        require(down and crouch and up and stand and ts[0][22:25] == [0, 0, 0] and
                max(down) < min(crouch) < min(up) < min(stand) and
                len(down) >= 26 and len(up) >= 13 and stand[-1] == len(ts)-1 and
                all(hit(q[1]) for q in qs),
                'real duck/unduck cycle did not ACT')
        c['duck_transition_ticks'], c['crouched_button_ticks'] = down, crouch
        c['unduck_transition_ticks'], c['standing_after_release_ticks'] = up, stand
        c['standing_fit_blocked_ticks'] = [i for i, q in enumerate(qs) if q[-1][10] < 1 or q[-1][11] or q[-1][12]]
    require(not open_cycle['standing_fit_blocked_ticks'], 'open posture fit control is blocked')
    ts = ceiling['ticks']; blocked = ceiling['standing_fit_blocked_ticks']
    released = [i for i in blocked if ts[i][5] == 0 and ts[i][21:24] == [45, 1, 0]]
    require(released and len(released) >= 3 and max(blocked) < min(ceiling['unduck_transition_ticks']) and
            ts[max(blocked)+1][10] > 48 and
            any(t[10] < -48 and abs(t[13]) < EPS and t[21] == 62 for t in ts[3:30]) and
            all(not (q[0][10] < 1 or q[0][11] or q[0][12]) for q in ceiling['oracles']),
            'ceiling block/clear/real unduck did not ACT')
    ceiling['released_but_ceiling_blocked_ticks'] = released


def assess_airposture(cycle, control):
    require(cycle['label'] == LABELS[16] and control['label'] == LABELS[17] and
            cycle['seed'] == control['seed'] and all(len(c['ticks']) == 64 and all(c['oracles']) for c in (cycle, control)),
            'missing matched airborne posture actors')
    ts, baseline = cycle['ticks'], control['ticks']
    landings = [[i for i in range(1, 64) if not c['ticks'][i-1][9] and c['ticks'][i][9]] for c in (cycle, control)]
    require(landings[0] == landings[1] and len(landings[0]) == 1 and 11 < landings[0][0] < 63,
            'airborne posture fall/landing did not ACT')
    landing = landings[0][0]
    for i, (t, b) in enumerate(zip(ts, baseline)):
        duck = 3 <= i <= 10
        require(t[8] == b[8] == 0 and t[9] == b[9] == int(i >= landing) and
                t[21:28] == [45 if duck else 62, int(duck), 0, 1000-15*(i-3) if duck else 0, 0, 0, 8 if duck else 0] and
                b[21:28] == [62, 0, 0, 0, 0, 0, 0] and
                close(t[10:12]+t[13:16], b[10:12]+b[13:16], 1e-5) and
                abs(t[12]-b[12]-(8.5 if duck else 0)) < 1e-4,
                'airborne instant duck/unduck origin/hull/timer/control did not ACT')
        if i < landing:
            require(abs(b[15]+12*(i+1)) < 1e-4 and b[12] > 0 and
                    (i == 0 or b[12] < baseline[i-1][12]), 'airborne native gravity actor failed')
        else:
            require(abs(b[15]) < EPS and abs(b[12]) < .1, 'airborne landed body did not ACT')
        for c in (cycle, control):
            q = c['oracles'][i]
            require(hit(q[2]) and hit(q[3]) and not (q[4][10] < 1 or q[4][11] or q[4][12]),
                    'airborne projected floor/standing-hull query failed')
    require(all(not hit(c['oracles'][i][1]) for c in (cycle, control) for i in range(12)) and
            all(hit(c['oracles'][-1][1]) for c in (cycle, control)), 'airborne native down2 miss/hit did not ACT')
    cycle.update(airborne_duck_ticks=list(range(3, 11)), instant_airborne_unduck_tick=11,
                 matched_control_origin_shift=8.5, native_landing_tick=landing,
                 posture_acceptance='BOUNDED_OPEN_AIR_DUCK_UNDUCK_ONLY')
    control.update(native_landing_tick=landing, airborne_no_duck_control='PASS')


def assess_cached_actor(present, removed):
    require(present['label'] == LABELS[18] and removed['label'] == LABELS[19] and
            present['seed'] == removed['seed'] and all(len(c['ticks']) == 64 and all(c['oracles']) for c in (present, removed)),
            'missing matched cached-approach native actors')
    ts, baseline, qs = present['ticks'], removed['ticks'], present['oracles']
    impacts = [i for i, t in enumerate(ts) if t[8]]
    different = [i for i, (t, b) in enumerate(zip(ts, baseline)) if t[10:16] != b[10:16]]
    supported = [i for i, q in enumerate(qs) if hit(q[1]) and close(q[1][14:18], [-.8, 0, .6, 0]) and
                 q[3][10:13] == [1, 0, 0]]
    hypothetical_solid = [i for i, q in enumerate(removed['oracles']) if q[2][11:13] == [1, 1] and hit(q[1])]
    require(impacts and different and min(impacts) == min(different) and min(impacts) > 5 and
            all(t[8:10] == [0, 1] for t in ts[:min(impacts)]) and
            all(t[8:10] == [0, 1] and abs(t[12]) < .1 and abs(t[15]) < EPS for t in baseline) and
            all(hit(q[1]) and hit(q[3]) for q in removed['oracles']) and supported and hypothetical_solid and
            ts[-1][12] > 1 and ts[-1][10] < baseline[-1][10],
            'cached ramp approach/ground/impact/removal/query difference did not ACT')
    present.update(native_ramp_impact_ticks=impacts, first_native_impact_tick=min(impacts),
                   ramp_hit_flooronly_miss_ticks=supported, matched_removal_actor='PASS')
    removed.update(removed_ramp_native_ground_walk='PASS', inactive_ramp_counterfactual_solid_ticks=hypothetical_solid)


def assess_capsule(c):
    ts, qs = c['ticks'], c['oracles']
    require(c['label'] == LABELS[8] and len(ts) == STEPS and all(qs), 'missing capsule native actor')
    losses = [i for i in range(1, STEPS) if ts[i-1][8] and not ts[i][8]]
    hits = [i for i, q in enumerate(qs) if hit(q[1])]
    misses = [i for i, q in enumerate(qs) if not hit(q[1])]
    differences = [i for i, q in enumerate(qs) if q[2][11] == q[2][12] == 1 and
                   not (q[0][10] < 1 or q[0][11] or q[0][12])]
    require(ts[0][8] == 1 and losses and hits and misses and min(hits) < max(misses) and differences and
            all(t[25:27] == [1, 0] and t[21:25] == [62, 0, 0, 0] for t in ts),
            'capsule native hit/miss/path difference did not ACT')
    c.update(raw_loss_ticks=losses, native_down2_hit_ticks=hits, native_down2_miss_ticks=misses,
             capsule_miss_box_solid_ticks=differences, geometry_acceptance='ABSTAIN-capsule-hull-unsupported',
             independent_capsule_oracle='NOT_IMPLEMENTED')


def assess_transform(c):
    ts, qs = c['ticks'], c['oracles']
    require(c['label'] == LABELS[9] and c['instance'] == INSTANCE and len(ts) == STEPS and all(qs),
            'missing transformed native actor')
    losses = [i for i in range(1, STEPS) if ts[i-1][8] and not ts[i][8]]
    hits = [i for i, q in enumerate(qs) if hit(q[1])]
    misses = [i for i, q in enumerate(qs) if not hit(q[1])]
    differences = [i for i, q in enumerate(qs) if hit(q[1]) and q[2][10:13] == [1, 0, 0]]
    identity_solid = [i for i, q in enumerate(qs) if q[2][11] or q[2][12]]
    require(ts[0][8] == 1 and losses and hits and misses and min(hits) < max(misses) and differences and
            all(t[21:27] == [62, 0, 0, 0, 0, 0] for t in ts),
            'transformed native hit/miss/rotation difference did not ACT')
    c.update(raw_loss_ticks=losses, native_down2_hit_ticks=hits, native_down2_miss_ticks=misses,
             transformed_hit_identity_miss_ticks=differences, identity_counterfactual_solid_ticks=identity_solid,
             geometry_acceptance='ABSTAIN-transformed-instance-unsupported', independent_transform_oracle='NOT_IMPLEMENTED')


def assess_entity(present, removed):
    require(present['label'] == LABELS[10] and removed['label'] == LABELS[11] and
            present['seed'] == removed['seed'] and all(len(c['ticks']) == STEPS and all(c['oracles']) for c in (present, removed)),
            'missing matched native entity actors')
    ts, qs = present['ticks'], present['oracles']
    losses = [i for i in range(1, STEPS) if ts[i-1][8] and not ts[i][8]]
    hits = [i for i, q in enumerate(qs) if hit(q[1])]
    misses = [i for i, q in enumerate(qs) if not hit(q[1])]
    differences = [i for i, q in enumerate(qs) if hit(q[1]) and q[2][10:14] == [1, 0, 0, -1]]
    require(ts[0][8] == 1 and losses and hits and misses and min(hits) < max(misses) and differences and
            all(q[2][10:14] == [1, 0, 0, -1] for q in qs) and
            all(t[8:10] == [0, 0] for t in removed['ticks']) and
            all(all(q[10:14] == [1, 0, 0, -1] for q in tick) for tick in removed['oracles']) and
            ts[0][10:16] != removed['ticks'][0][10:16] and ts[-1][10:16] != removed['ticks'][-1][10:16],
            'entity winner/hit/miss/removal trajectory control did not ACT')
    present.update(raw_loss_ticks=losses, native_down2_hit_ticks=hits, native_down2_miss_ticks=misses,
                   entity_hit_worldonly_miss_ticks=differences, geometry_acceptance='ABSTAIN-entity-unsupported',
                   independent_entity_query_oracle='JOINT_CONVEX_AABB_FIXTURE_ONLY')
    removed.update(removed_entity_trajectory_gates='PASS', geometry_acceptance='ABSTAIN-no-accepted-contact')


def assess_embedded(present, removed):
    require(present['label'] == LABELS[12] and removed['label'] == LABELS[13] and
            present['seed'] == removed['seed'] and all(len(c['ticks']) == STEPS and all(c['oracles']) for c in (present, removed)),
            'missing matched native embedded actors')
    ts, qs = present['ticks'], present['oracles']
    losses = [i for i in range(1, STEPS) if ts[i-1][8] and not ts[i][8]]
    hits = [i for i, q in enumerate(qs) if hit(q[1])]
    misses = [i for i, q in enumerate(qs) if not hit(q[1])]
    differences = [i for i, q in enumerate(qs) if hit(q[1]) and q[2][10:14] == [1, 0, 0, -1]]
    require(ts[0][8] == 1 and losses and hits and misses and min(hits) < max(misses) and differences and
            all(q[2][10:14] == [1, 0, 0, -1] for q in qs) and
            all(t[8:10] == [0, 0] for t in removed['ticks']) and
            all(all(q[10:14] == [1, 0, 0, -1] for q in tick) for tick in removed['oracles']) and
            ts[0][10:16] != removed['ticks'][0][10:16] and ts[-1][10:16] != removed['ticks'][-1][10:16],
            'embedded winner/hit/miss/removal trajectory control did not ACT')
    present.update(raw_loss_ticks=losses, native_down2_hit_ticks=hits, native_down2_miss_ticks=misses,
                   embedded_hit_unembedded_miss_ticks=differences, geometry_acceptance='ABSTAIN-embedded-model-unsupported',
                   independent_embedded_query_oracle='JOINT_CONVEX_AABB_IDENTITY_FIXTURE_ONLY')
    removed.update(removed_embedded_trajectory_gates='PASS', geometry_acceptance='ABSTAIN-no-accepted-contact')


def assess_triangle(present, removed):
    require(present['label'] == LABELS[14] and removed['label'] == LABELS[15] and
            present['seed'] == removed['seed'] and all(len(c['ticks']) == STEPS and all(c['oracles']) for c in (present, removed)),
            'missing matched native triangle actors')
    ts, qs = present['ticks'], present['oracles']
    losses = [i for i in range(1, STEPS) if ts[i-1][8] and not ts[i][8]]
    hits = [i for i, q in enumerate(qs) if hit(q[1])]
    misses = [i for i, q in enumerate(qs) if not hit(q[1])]
    differences = [i for i, q in enumerate(qs) if hit(q[1]) and q[2][10:14] == [1, 0, 0, -1]]
    require(ts[0][8] == 1 and losses and hits and misses and min(hits) < max(misses) and differences and
            any(close(q[1][14:18], [.8, 0, .6, 0]) for q in qs if hit(q[1])) and
            all(q[2][10:14] == [1, 0, 0, -1] for q in qs) and
            all(t[8:10] == [0, 0] for t in removed['ticks']) and
            all(all(q[10:14] == [1, 0, 0, -1] for q in tick) for tick in removed['oracles']) and
            ts[0][10:16] != removed['ticks'][0][10:16] and ts[-1][10:16] != removed['ticks'][-1][10:16],
            'triangle winner/hit/miss/removal trajectory control did not ACT')
    present.update(raw_loss_ticks=losses, native_down2_hit_ticks=hits, native_down2_miss_ticks=misses,
                   triangle_hit_untriangled_miss_ticks=differences, geometry_acceptance='ABSTAIN-triangle-unsupported',
                   independent_triangle_query_oracle='NOT_IMPLEMENTED',
                   triangle_fixture_vertices_basis='AUTHORED_WIRING_NOT_COPIED_ACCEPTED_GEOMETRY')
    removed.update(removed_triangle_trajectory_gates='PASS', geometry_acceptance='ABSTAIN-no-accepted-contact')


def assess(cases):
    for c in cases[:8]:
        ts, qs = c['ticks'], c['oracles']
        require(all(qs), 'missing full native query actor')
        c['raw_loss_ticks'] = [i for i in range(1, len(ts)) if ts[i-1][8] and not ts[i][8]]
        c['immediate_support_ticks'] = [i for i, q in enumerate(qs) if hit(q[1])]
        c['projected_support_ticks'] = [i for i, q in enumerate(qs) if hit(q[2])]
    a, side, convex, interior, jump, seam, open_cycle, ceiling = cases[:8]
    require(all(t[8] for t in a['ticks']) and len(a['projected_support_ticks']) == STEPS and not a['raw_loss_ticks'], 'interior ride control failed')
    for c, edge in ((side, [0, 1, 0, 64]), (convex, [math.sqrt(.5), math.sqrt(.5), 0, 0])):
        partial = [i for i in c['projected_support_ticks'] if dot(edge[:3], c['ticks'][i][10:13]) > edge[3]]
        full = [i for i in range(STEPS) if i not in c['projected_support_ticks']]
        require(partial and full and c['raw_loss_ticks'] and min(full) > min(partial), 'partial/full convex edge actor failed')
        c['partial_supported_ticks'] = partial; c['fully_unsupported_ticks'] = full
        c['raw_loss_minus_first_support_loss_ticks'] = c['raw_loss_ticks'][0]-full[0]
    require(interior['raw_loss_ticks'] and len(interior['projected_support_ticks']) == STEPS and
            len(interior['immediate_support_ticks']) == STEPS and interior['ticks'][3][3] == 250 and
            any(interior['ticks'][i][8] for i in range(interior['raw_loss_ticks'][0]+1, STEPS)), 'interior command loss/reacquisition did not ACT')
    require(jump['ticks'][2][9] == 1 and jump['ticks'][3][5] == 2 and jump['ticks'][3][13+2] > 250 and
            jump['ticks'][3][9] == 0 and 3 not in jump['immediate_support_ticks'] and len(jump['projected_support_ticks']) == STEPS, 'real ground jump did not ACT')
    assess_posture(open_cycle, ceiling)
    assess_capsule(cases[8])
    require(cases[8]['accepted'] and all(w['geometry_status'] == 'capsule-hull-unsupported' for w in cases[8]['accepted']),
            'capsule winning capture absent/promoted')
    assess_transform(cases[9])
    require(cases[9]['accepted'] and all(w['geometry_status'] == 'transformed-instance-unsupported' for w in cases[9]['accepted']),
            'transformed winning capture absent/promoted')
    assess_entity(*cases[10:12])
    assess_embedded(*cases[12:14])
    assess_triangle(*cases[14:16])
    assess_airposture(*cases[16:18])
    assess_cached_actor(*cases[18:20])
    assess_cached_capture(cases[18]['ticks'], cases[18]['accepted'])
    require(not cases[19]['accepted'], 'removed ramp actor accepted a native ramp contact')
    cases[18]['cached_firsttrace_contact_ticks'] = sorted({w['tick'] for w in cases[18]['accepted'] if w['originroute'] == 1})
    require(cases[14]['accepted'] and all(w['geometry_status'] == 'world-triangle-unresolved' for w in cases[14]['accepted']) and
            any(close(w['native_plane'], [.8, 0, .6, 0]) for w in cases[14]['accepted']) and not cases[15]['accepted'],
            'triangle winning capture absent/promoted or removal capture nonempty')
    require(cases[12]['accepted'] and all(w['geometry_status'] == 'embedded-model-unsupported' for w in cases[12]['accepted']) and
            not cases[13]['accepted'], 'embedded winning capture absent/promoted or removal capture nonempty')
    require(cases[10]['accepted'] and all(w['geometry_status'] == 'entity-unsupported' for w in cases[10]['accepted']) and
            not cases[11]['accepted'], 'entity winning capture absent/promoted or removal capture nonempty')
    require(len(seam['projected_support_ticks']) == STEPS and all(t[8] for t in seam['ticks']) and
            {a['brush'] for a in seam['accepted']} == {0, 1} and
            len({a['leaf'] for a in seam['accepted']}) == 2 and any(not hit(q[3]) and hit(q[4]) for q in seam['oracles']), 'union/previous-brush seam handoff did not ACT')


def compare(nooracle, control, off, on, repeat):
    reports = [grade(t) for t in (nooracle, control, off, on, repeat)]
    require([(r['capture'], r['oracle']) for r in reports] == [(0, 0), (0, 1), (0, 1), (1, 1), (1, 1)], 'invalid fixture arms')
    require(all(r['source'] == reports[0]['source'] for r in reports), 'native fixture/base provenance differs')
    def canonical(report):
        rows = []
        for c in report['cases']:
            keys = ('label', 'brushes', 'seed', 'ticks', 'oracles')
            if c['label'] in LABELS[18:20]: keys += ('brushset',)
            if c['label'] == LABELS[9]: keys += ('instance',)
            elif c['label'] in LABELS[10:16]: keys += ('physent_set', 'physents', 'instances')
            if c['label'] in LABELS[14:16]: keys += ('triangle',)
            elif c['label'] in LABELS[12:14]: keys += ('embedded',)
            rows.append({k: c[k] for k in keys})
        return rows
    require(all(canonical(r) == canonical(reports[1]) for r in reports[2:]), 'fixture-only/OFF/ON/repeat body/oracle differs')
    require(all(a['ticks'] == b['ticks'] for a, b in zip(reports[0]['cases'], reports[1]['cases'])), 'oracle queries altered later movement')
    require(reports[3] == reports[4], 'repeated captured fixture binding differs')
    assess(reports[3]['cases'])
    digest = hashlib.sha256(json.dumps(canonical(reports[1]), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'native_static_fixture_gates': 'PASS', 'nooracle_body_parity': 'PASS', 'capture_body_oracle_parity': 'PASS',
            'repeat_capture_binding': 'PASS', 'body_oracle_sha256': digest, 'source': reports[3]['source'],
            'cases': reports[3]['cases'], 'physical_exit_acceptance': 'NOT_TESTED', 'classifier_mark_acceptance': 'NOT_TESTED',
            'capsule_native_path_capture_gates': 'PASS', 'capsule_support_geometry_acceptance': 'ABSTAIN',
            'transformed_native_path_capture_gates': 'PASS', 'transformed_support_geometry_acceptance': 'ABSTAIN',
            'entity_native_path_capture_gates': 'PASS', 'entity_removal_trajectory_gates': 'PASS',
            'entity_support_geometry_acceptance': 'ABSTAIN',
            'embedded_native_path_capture_gates': 'PASS', 'embedded_removal_trajectory_gates': 'PASS',
            'embedded_support_geometry_acceptance': 'ABSTAIN',
            'triangle_native_path_capture_gates': 'PASS', 'triangle_removal_trajectory_gates': 'PASS',
            'triangle_support_geometry_acceptance': 'ABSTAIN',
            'airborne_open_duck_unduck_native_gates': 'PASS', 'general_airborne_posture_acceptance': 'NOT_TESTED',
            'cached_ground_approach_native_path_capture_gates': 'PASS', 'cached_ramp_removal_trajectory_gates': 'PASS',
            'general_cached_recovery_portal_acceptance': 'NOT_TESTED',
            'unsupported_mover_paths_acceptance': 'NOT_TESTED', 'clock_render_rate_hold_acceptance': 'NOT_TESTED'}


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); arms = json.loads(a.arms.read_text()); names = ('nooracle', 'control', 'off', 'on', 'repeat')
    require(set(arms) == set(names) and all(r['exit_code'] == 0 for r in arms.values()), 'missing/failed native fixture arm')
    require(arms['control']['server_sha256'] == arms['nooracle']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1, 'invalid control/subject binaries')
    require(len({r['fixture_sha256'] for r in arms.values()}) == len({r['manifest_sha256'] for r in arms.values()}) == 1, 'fixture/manifest inputs differ')
    result = compare(*(Path(arms[n]['log']).read_text(errors='replace') for n in names))
    require(result['source'][0] == arms['on']['fixture_sha256'], 'binary fixture stamp differs from tooling template')
    result['arms'] = arms; a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('AABB/ground+airborne posture/cached approach + ACTED capsule/transformed/entity/embedded/triangle paths: PASS; five-arm parity PASS')
    print('Capsule/transformed/entity/embedded/triangle geometry/support: ABSTAIN; bounded AABB queries and native removal controls PASS')
    print('Physical timestamp/classifier/mark/unsupported paths/clock/render/rate/hold acceptance: NOT_TESTED')


if __name__ == '__main__': main()
