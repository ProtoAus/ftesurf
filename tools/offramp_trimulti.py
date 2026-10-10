#!/usr/bin/env python3
"""Bounded ACTED multi-patch PM actors: native patch copy, path, exact front reach; support ABSTAIN.

Eleven authored actors with one standing identity AABB, on one ramp-plane family
and, for the trough, its mirror image. The supplied patch set is the built
native BIH's own triangle leaves, copied by value and required to equal the
authored table; no neighbour is inferred or discovered. The mover's clip
velocity is checked against the mover's own rules for one plane (a wall
included) and for two; of the two-plane rules only the crease has been taken by
a capture. Three or more planes and every outcome that stops the body are
refusals. Reach is exact on serialized decimals, not support.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

import offramp_bevclip as clip
import offramp_bevpm as pm
import offramp_tripath as path
import offramp_trireach as walk
import offramp_trisupport as reach
from offramp_buffer import parse as buffer_parse, require
from offramp_hull import decode as hull_decode
from offramp_motion import close, numbers
from offramp_origin import CHECKS as ORIGIN_CHECKS, integers, parse as origin_parse
from offramp_shape import decode as shape_decode
from offramp_triangle import NATIVE_BIAS, SPATIAL_TOLERANCE, cross, dot
from offramp_tribev import decode as bevel_decode
from offramp_tricopy import decode as copy_decode
from offramp_trimulti_smoke import NAMES, source_digest
from offramp_trislab import decode as slab_decode

CONTRACT = 'MULTI_PATCH_COMMITTED_PATH_FRONT_REACH_V3'
ROOT = Path(__file__).resolve().parent.parent
MODEL = 'maps/authored_offramp_trimulti.bsp'
MINS, MAXS, ORIGIN, STEPS = pm.MINS, pm.MAXS, [46, 24, -39.5], 32
INDEXES = ([0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7])
# P1 is y 0..y1, P2 is y y2..256 lowered by drop; live counts the leaves handed to the native builder.
# A trough replaces both: plane A over x 0..trough, its mirror image over x trough..2*trough.
# 1, 2, 5 and 6 are the 2 x 2 of gap width (16, 50) by neighbour height (coplanar, lowered 2).
ACTORS = (dict(label='seam-handoff', y1=64, y2=64, drop=0, authored=4, live=4, velocity=[0, 400, 0]),
          dict(label='narrow-gap', y1=64, y2=80, drop=0, authored=4, live=4, velocity=[0, 400, 0]),
          dict(label='wide-gap-recontact', y1=64, y2=114, drop=2, authored=4, live=4, velocity=[0, 400, 0]),
          dict(label='removed-neighbour-exit', y1=64, y2=114, drop=2, authored=4, live=2, velocity=[0, 400, 0]),
          dict(label='vertical-lift', y1=256, y2=256, drop=0, authored=2, live=2, velocity=[40, 400, 30]),
          dict(label='narrow-gap-lowered', y1=64, y2=80, drop=2, authored=4, live=4, velocity=[0, 400, 0]),
          dict(label='wide-gap-coplanar', y1=64, y2=114, drop=0, authored=4, live=4, velocity=[0, 400, 0]),
          dict(label='crease-trough', trough=72, authored=4, live=4, velocity=[60, 400, -80]),
          # Tick ends placed at a boundary: 0.0003 inside and 0.00016 outside a footprint edge,
          # 0.0013 outside and 0.0006 inside the horizon-2 cut.
          dict(label='edge-ladder', y1=8.0078125, y2=256, drop=0, authored=2, live=2, velocity=[0, .03125, 0]),
          dict(label='horizon-graze-out', y1=256, y2=256, drop=0, authored=2, live=2, velocity=[23.5, 400, 17.6875]),
          dict(label='horizon-graze-in', y1=256, y2=256, drop=0, authored=2, live=2, velocity=[23.5, 400, 17.65625]))
GAP_DESIGN = (1, 2, 5, 6)
WIDTHS = dict(BEGIN=5, SOURCE=3, CASE=5, FIXTURE=15, LEAF=16, LEAVES=3, SEED=13, TICK=28, QUERY=19, CASE_END=2, END=1)
MISS = [1, 0, 0, 0, -1, 0, 0, 0, 0, 0]
OWN = 'OFFRAMPTRIMULTI_'
# The mover's own constants: movevars.standablenormal in the fixture profile, PMSRC_MIN_RAMP_NZ, float.h.
STANDABLE, MIN_RAMP, FLT_EPSILON = .7, .1, 1.1920929e-07
# A sign test this close to zero (u/s) can be decided by float32 rounding: both branches are kept.
SIGN_NOISE = 1e-3
SINGLE, ALONG, CREASE, EITHER = ('NATIVE_SINGLE_PLANE_BRANCH_VERIFIED', 'NATIVE_MULTI_PLANE_ALONG_ONE_PLANE_VERIFIED',
                                 'NATIVE_TWO_PLANE_CREASE_VERIFIED', 'NATIVE_TWO_PLANE_ALONG_OR_CREASE_SAME_VELOCITY')
RULES = (SINGLE, ALONG, CREASE, EITHER)
TAG_MATCHES = ('MODEL_ENTRY_PLANE', 'COINCIDENT_MODEL_PLANE', 'FACE_PLANE_BEVEL_TURNED_IN_THE_MODEL')
# Farther down than any front of the fixture lies under any body here.
DEEP = 1024
# The layers a capture case may contain. Named, because a row no reader owns is otherwise read by nobody:
# split() takes this envelope away from every predecessor. The shape layer's prefix is GEOM.
LAYERS = frozenset(f'OFFRAMP{n}_' for n in ('BUF', 'ORIGIN', 'GEOM', 'HULL', 'TRICOPY', 'TRISLAB', 'TRIBEV', 'TRIPATH'))
PREFIX = re.compile(r'OFFRAMP[A-Z0-9]+_')
# 0 and 2 get the full dual-certified domains; 4 and 8 are SAT-only horizon sensitivity.
HORIZONS, SENSITIVITY = walk.HORIZONS, (4, 8)


def authored(actor):
    """The fixture from its table alone; no native row is an input."""
    a = ACTORS[actor]
    if 'trough' in a:
        t = a['trough']; z = -t*4/3
        xyz = [[0, 0, 0], [0, 256, 0], [t, 256, z], [t, 0, z], [t, 0, z], [t, 256, z], [2*t, 256, 0], [2*t, 0, 0]]
    else:
        xyz = [[0, 0, 0], [0, a['y1'], 0], [192, a['y1'], -256], [192, 0, -256], [0, a['y2'], -a['drop']],
               [0, 256, -a['drop']], [192, 256, -256-a['drop']], [192, a['y2'], -256-a['drop']]]
    return [[xyz[i] for i in INDEXES[j]] for j in range(a['authored'])]


def parse(text):
    rows = []
    for line in text.splitlines():
        p = line.find(OWN)
        if p < 0:
            continue
        words = line[p:].split()
        tag = words[0].removeprefix(OWN)
        require(tag in WIDTHS and len(words)-1 == WIDTHS[tag], 'unknown/malformed multi-patch row')
        rows.append((tag, words[1:]))
    return rows


def foreign(text):
    """Every other layer's row prefix in the text, once per row."""
    return [p for p in PREFIX.findall(text) if p != OWN]


def split(text):
    """(everything else, the one multi-patch envelope). Prior readers only ever see the first."""
    rows = parse(text)
    matches = list(re.finditer(r'OFFRAMPTRIMULTI_BEGIN[^\n]*\n.*?OFFRAMPTRIMULTI_END[^\n]*(?:\n|$)', text, re.S))
    require(len(matches) == 1, 'missing/duplicate multi-patch envelope')
    m = matches[0]
    require(parse(m.group()) == rows, 'multi-patch rows outside envelope')
    return text[:m.start()]+text[m.end():], m.group()


def candidates(triangle, start, end):
    """One triangle's predicted hit, once per entering plane tied with its latest entry.

    The plane-set model keeps the first plane of a tie. Native compares in
    float32, so between two coplanar planes of one triangle (here a bevel built
    from a slope-direction edge and the y axis IS the face plane) either can win.
    """
    predicted = clip.prediction(triangle, start, end, MINS, MAXS, True)
    require(predicted['expected'] is not None, 'multi-patch embedded start unsupported')
    clipped, found = predicted['clipped'], []
    for q in clipped['planes'] if predicted['expected'] != MISS else []:
        speed = q['start_distance']-q['end_distance']
        if q['enter'] is not None and (clipped['lower']-q['enter'])*speed <= SPATIAL_TOLERANCE:
            found.append(dict(expected=[max(0, q['enter']-NATIVE_BIAS/speed), max(0, q['enter']), 0, 0, 0, *q['normal'], q['dist'], 1],
                              clipped=dict(clipped, entry_plane=q), model_tag=clipped['entry_plane']['tag']))
    return found


def named_plane(found, tag):
    """The tied candidates whose entry plane native names by tag.

    A bevel built from an edge and an axis that both lie in the face plane IS
    that plane or, turned round, the back of the slab. Which, is decided by
    rounding, natively in float32 and here in doubles, and not necessarily
    alike. So a tag naming such a bevel is the face when the face is tied, and
    is marked. The tag is therefore bound only up to the planes that coincide
    with the entry plane in this model or would if turned: native can name
    some of those and never others, which this reader cannot tell apart.
    """
    named = [c for c in found if c['clipped']['entry_plane']['tag'] == tag]
    face = [c for c in found if c['clipped']['entry_plane']['tag'] == 0]
    if not named and face:
        front = face[0]['clipped']['entry_plane']['normal']
        if any(q['tag'] == tag and q['kind'] == 'bevel' and close(q['normal'], [-x for x in front], 1e-9)
               for q in face[0]['clipped']['planes']):
            named = [dict(c, turned_bevel=True) for c in face]
    return named


def native_prediction(triangles, start, end):
    """Earliest entry over the supplied triangles by the per-triangle plane-set model.

    A tie between triangles keeps every candidate. Which one native reports
    depends on traversal order and float32 equality, and is not modelled.
    """
    found = [dict(c, triangle=j) for j, t in enumerate(triangles) for c in candidates(t, start, end)]
    if not found:
        return [dict(expected=MISS)]
    first = min(c['clipped']['enter'] for c in found)
    return [c for c in found if (c['clipped']['enter']-first)*(c['clipped']['entry_plane']['start_distance'] -
                                                             c['clipped']['entry_plane']['end_distance']) <= SPATIAL_TOLERANCE]


def check_trace(row, start, end, triangles):
    """Native trace against the model; returns how many triangles, (triangle, plane) pairs and planes tie.

    Two coplanar triangles, or a face and its own coplanar bevel, tie on ONE
    plane. Two planes means the tie is between different surfaces, as in a
    crease, and then even the reported normal is not modelled.
    """
    require(len(row) == 13, 'multi-patch trace width differs')
    wanted, refusal = native_prediction(triangles, start, end), None
    for candidate in wanted:
        try:
            clip.check_observation(row[:10], candidate)
            break
        except AssertionError as error:
            refusal = error
    else:
        raise AssertionError(f'multi-patch native trace differs from every plane-set candidate: {refusal}')
    require(close(row[10:], [s+row[0]*(e-s) for s, e in zip(start, end)], 2e-5), 'multi-patch trace endpoint/fraction differs')
    found, planes = [c for c in wanted if 'triangle' in c], []
    for c in found:
        if not any(close(c['expected'][5:9], p, 1e-6) for p in planes):
            planes.append(c['expected'][5:9])
    return dict(triangles=len({c['triangle'] for c in found}), candidates=len(found), planes=len(planes))


def entry_planes(triangles, start, end):
    """The model's tied entry candidates of one sweep: [triangle, plane tag, plane kind]."""
    return [[c['triangle'], c['clipped']['entry_plane']['tag'], c['clipped']['entry_plane']['kind']]
            for c in native_prediction(triangles, start, end) if 'triangle' in c]


def clip_velocity(velocity, normal):
    """PMSrc_ClipVelocity at overbounce 1, with its one corrective pass.

    Overbounce is 1 on every branch here because the fixture profile zeroes
    sv_bounce. The pass only acts when the normal is shorter than unit length,
    by at most 3.5e-6 u/s on the float32 normals captured so far: far under the
    clip gate's tolerance, so the arithmetic is the mover's but no capture has
    told the pass from none.
    """
    out = [v-dot(velocity, normal)*a for v, a in zip(velocity, normal)]
    back = min(0, dot(out, normal))
    return [v-back*a for v, a in zip(out, normal)]


def plane_list(planes, normal, fraction):
    """Native clip-plane list after a hit: ANY move clears it, then this plane is appended.

    So a hit after a positive move, however small, is the one-plane branch
    again; only consecutive zero-fraction hits accumulate.
    """
    return ([] if fraction > 0 else planes)+[normal]


def clip_rules(velocity, planes, primal):
    """Every (velocity, rule) the native clip may leave where the mover goes on.

    One plane is the airborne first-impact branch. Two is the multi-plane
    branch: the first plane whose clip does not head into the other (which for
    one plane hit twice is that plane), else for two different planes the
    crease, the last clip projected on their cross product. A sign test inside
    SIGN_NOISE keeps both outcomes. Nothing comes back for an outcome that
    ends the command there (the same-plane push, a result opposing the velocity
    the command entered with) or for three or more planes. That last is a
    choice, not a limit of the rows: the mover then clips the velocity the
    list's FIRST hit left, which its outcome row carries, but no capture has
    reached a third plane and a rule nothing exercised is not graded.
    """
    if len(planes) == 1:
        return [(clip_velocity(velocity, planes[0]), SINGLE)]
    if len(planes) > 2:
        return []
    found, tried = [], None
    for i, normal in enumerate(planes):
        tried = clip_velocity(velocity, normal)
        into = [dot(tried, other) for j, other in enumerate(planes) if j != i]
        if all(d >= -SIGN_NOISE for d in into):
            found.append((tried, ALONG))
        if all(d >= SIGN_NOISE for d in into):
            break
    else:
        if not close(planes[0], planes[1], FLT_EPSILON):
            axis = cross(planes[0], planes[1])
            length = math.sqrt(dot(axis, axis))
            # Native normalises the cross product; between (anti)parallel planes it is zero, and then so is the result.
            unit = [x/length for x in axis] if length > 1e-6 else [0, 0, 0]
            found.append(([dot(tried, unit)*x for x in unit], CREASE))
    # The mover stops dead when a multi-plane result opposes the velocity the command entered with.
    return [(v, rule) for v, rule in found if dot(v, primal) > 0]


def clip_rule(observed, velocity, planes, primal):
    """The rule a captured clip velocity fits and by how much: (name, largest component error); else a refusal.

    Along one plane and the crease can leave the same velocity, a wall joined
    to a ramp for one; the row then cannot say which branch native took.
    """
    fits = [(max(abs(x-y) for x, y in zip(observed, v)), name) for v, name in clip_rules(velocity, planes, primal)]
    fits = [(error, name) for error, name in fits if error <= clip_tolerance(velocity)]
    require(fits, 'multi-patch clip velocity differs from every native clip rule')
    return (fits[0][1] if len({name for _, name in fits}) == 1 else EITHER), min(error for error, _ in fits)


def contact_class(normal):
    """What the mover makes of a hit plane: RAMP (the accepted band, either winding) or WALL; else a refusal."""
    steep = abs(normal[2])
    if MIN_RAMP <= steep <= STANDABLE:
        return 'RAMP'
    require(steep <= FLT_EPSILON, 'unsupported multi-patch contact plane: floor or neither ramp nor wall')
    return 'WALL'


def clip_tolerance(velocity):
    """How far (u/s, per component) a native clip velocity may sit from its rule.

    8e-5 plus two float32 steps of the speed, 2.4e-7 of it at most: above
    1,024 u/s one step alone is 1.2e-4, and a flat 8e-5 refuses some honest
    clips there (by a float32 transcription of the mover's clip; no clip
    captured here starts above 502 u/s). The crease needs the room most:
    native normalises the cross product and multiplies by it twice. Measured in
    one V at 400 u/s: 6.1e-5 a clip, two steps, a loss in 16 of 16. So at 400
    u/s a consistent lie about a crease velocity from about 1.1e-4 slower to
    2.3e-4 faster than native is not seen, and the band widens with speed. One
    plane needs far less than it gets: the largest of 242 captured errors is
    1.3e-5, against 2.0e-4 allowed at 500 u/s.
    """
    return 8e-5+2.4e-7*math.sqrt(dot(velocity, velocity))


def capture(block, ticks, live, nodes):
    """Accepted contacts with their copied winning triangle, bound to one supplied leaf and its node."""
    buffer, order = buffer_parse(block)
    contacts = buffer['CONTACT']
    require(buffer['BEGIN'] == [[1, 32768]] and buffer['END'] == [[STEPS, len(contacts), 0]] and
            order == ['BEGIN']+['TICK']*STEPS+['CONTACT']*len(contacts)+['END'], 'multi-patch buffer envelope differs')
    for i, (r, t) in enumerate(zip(buffer['TICK'], ticks)):
        require(r[:4] == [i, i, i+1, i+1] and close(r[4:7], t[7:10]) and r[7:13] == t[10:16],
                'multi-patch body not bound to actual captured tick')
    origins, order = origin_parse(block)
    require(origins['CHECK'] == [[str(i), n, '1'] for i, n in enumerate(ORIGIN_CHECKS, 1)] and
            origins['SELFTEST'] == [[str(len(ORIGIN_CHECKS)), '0']] and
            order == ['CHECK']*len(ORIGIN_CHECKS)+['SELFTEST']+['CONTACT']*len(contacts), 'multi-patch origin setup differs')
    origin_rows = [integers(w[:9])+[w[9]] for w in origins['CONTACT']]
    payloads, shapes, _ = shape_decode(block, contacts, origin_rows)
    ht, hc, _ = hull_decode(block, buffer['TICK'], contacts, shapes)
    copies = copy_decode(block, contacts, origin_rows)
    bevel_decode(block); slab_decode(block)
    results = []
    for i, (r, o, s, h, cp) in enumerate(zip(contacts, origin_rows, shapes, hc, copies)):
        t = int(r[1]); p = payloads[s['payload_id']]
        # Origin row: ordinal, tick, route, kind (2 triangle), leaf node, root leaf node, depth, contents, entity, model.
        require(r[0] == i and 0 <= t < STEPS and r[2] >= 0 and r[3] == 0 and 0 <= r[4] < 1 and r[21:] == [0]*3 and
                r[15:21] == MINS+MAXS and o[:4] == [i, t, 0, 2] and o[4] == o[5] and o[6:] == [0, 1, 0, MODEL],
                'multi-patch accepted trace/route/world/origin binding differs')
        require(p['status'] == p['source_side_count'] == 0 and not p['planes'] and
                s['capsule'] == 0 and s['direct_bih_callback'] == 1 and
                s['instance_origin'] == s['instance_angles'] == [0]*3 and s['raw_instance_scale'] == 1,
                'multi-patch empty brush/actual instance binding differs')
        require(h['mins'] == MINS and h['maxs'] == MAXS and
                [h['capsule'], h['pm_type'], h['ducked'], h['ducking'], h['ducktime_ms'], h['oldbuttons']] == [0]*6 and
                [h['raw_standheight'], h['raw_duckheight']] == [62, 45], 'multi-patch contact actual posture differs')
        members = [j for j, triangle in enumerate(live) if cp['indexes'] == INDEXES[j] and cp['vertices'] == triangle]
        require(cp['native_bevels_applied'] == 1 and len(members) == 1,
                'multi-patch winning copy is not exactly one supplied triangle with bevels on')
        # The winner's native leaf is a node index; it must be the node the walker dumped for that triangle.
        require(o[4] == nodes[members[0]], 'multi-patch native leaf is not the dumped node of the copied triangle')
        named = named_plane(candidates(cp['vertices'], r[9:12], r[12:15]), cp['native_plane_tag'])
        require(len(named) == 1, 'multi-patch copied winner plane tag is not a latest-entry plane of its triangle')
        clip.check_observation([r[4], None, 0, 0, 0, *r[6:9], r[5], 1], named[0], truefraction_observed=False)
        results.append(dict(contact=r, origin=o, copied_winner=cp, triangle=members[0], native_leaf_node=o[4],
                            plane_tag_tied_with_model_tag=None if named[0]['model_tag'] == cp['native_plane_tag']
                            else named[0]['model_tag'],
                            plane_tag_match=('FACE_PLANE_BEVEL_TURNED_IN_THE_MODEL' if named[0].get('turned_bevel') else
                                             'MODEL_ENTRY_PLANE' if named[0]['model_tag'] == cp['native_plane_tag'] else
                                             'COINCIDENT_MODEL_PLANE'),
                            geometry_basis='COPIED_WINNING_NATIVE_TRIANGLE_MEMBER_OF_NATIVE_LEAF_SET'))
    require(len(ht) == len(ticks) == STEPS, 'missing multi-patch captured tick hull')
    for i, (h, t) in enumerate(zip(ht, ticks)):
        current = [r for r in contacts if r[1] == i]
        require(close(buffer['TICK'][i][13:], current[-1][6:9] if current else [0]*3, 1e-5),
                'multi-patch native rampnormal cache differs')
        require(h['mins'] == t[16:19] and h['maxs'] == t[19:22] and
                [h['ducked'], h['ducking'], h['ducktime_ms'], h['capsule'], h['pm_type'], h['oldbuttons']] == t[22:] and
                [h['raw_standheight'], h['raw_duckheight']] == [62, 45], 'multi-patch posture not bound to ACTED capture')
    return results


def grade_path(block, case, ticks, accepted, live):
    """Every attempt, validation, outcome and return of the ordinary airborne route.

    Position, time-left, fraction and the trace itself are bound for every
    attempt, whatever the bump count. A hit is a ramp contact (accepted, with a
    copied winner) or a wall (neither, and the command returns blocked 2); a
    floor or any other plane is refused. The clip VELOCITY must be one of
    clip_rules(); the outcomes that stop the body are refused.
    """
    rows = path.parse(block)
    kind = lambda at: rows[at][0] if at < len(rows) else None
    require(kind(0) == 'BEGIN', 'missing multi-patch path envelope')
    begin = integers(rows[0][1][:5]); count = begin[3]
    require(begin[:3] == [1, case, STEPS] and begin[4] == 0 and STEPS <= count <= 512,
            'multi-patch path version/case/calls/count/overflow differs')
    cursor, calls, attempts, validations, outcomes, returns = 1, [], [], {}, [], []
    for i in range(STEPS):
        require(kind(cursor) == 'CALL', 'missing/reordered multi-patch path call')
        calls.append(numbers(rows[cursor][1])); cursor += 1
    for n in range(count):
        require(kind(cursor) == 'ATTEMPT', 'missing/reordered multi-patch path attempt')
        attempts.append(numbers(rows[cursor][1])); cursor += 1
        if kind(cursor) == 'VALIDATE':
            v = numbers(rows[cursor][1]); cursor += 1
            require(v[:2] == [n, 1] and v[2:5] == attempts[n][34:37], 'multi-patch validation identity/start differs')
            check_trace(v[5:], v[2:5], v[2:5], live)
            validations[n] = v
        require(kind(cursor) == 'OUTCOME', 'missing/reordered multi-patch path outcome')
        outcomes.append(numbers(rows[cursor][1])); cursor += 1
        require(outcomes[n][0] == n and outcomes[n][1] in (1, 2), 'unsupported multi-patch path outcome/refusal')
    for i in range(STEPS):
        require(kind(cursor) == 'RETURN', 'missing/reordered multi-patch path return')
        returns.append(numbers(rows[cursor][1])); cursor += 1
    require(rows[cursor:] == [('END', [str(case)])], 'extra multi-patch path rows or incomplete envelope')
    body, velocity, result, hits, walls, ordinal = ORIGIN, ACTORS[case]['velocity'], [], [], [], 0
    for i, (call, returned, tick) in enumerate(zip(calls, returns, ticks)):
        require(call[:2] == [i, i] and call[3:8] == [0, 0, 1, 0, 0] and call[14:] == MINS+MAXS+[0]*8,
                'unsupported multi-patch path call/route/posture/ramp context')
        require(close(call[2:3], [.015], 1e-8) and call[8:11] == body and
                close(call[11:14], [velocity[0], velocity[1], velocity[2]-6], 2e-5),
                'multi-patch path call not bound to command body/half-gravity velocity')
        indices = [n for n, r in enumerate(attempts) if r[1] == i]
        require(indices and indices == list(range(ordinal, ordinal+len(indices))),
                'multi-patch path attempts not contiguous within command')
        ordinal += len(indices)
        velocity, left, ramp, total, planes, blocked, committed = call[11:14], call[2], 0, 0, [], 0, []
        primal = velocity
        for bump, n in enumerate(indices):
            r, o = attempts[n], outcomes[n]
            require(r[0] == n and r[2] == bump and r[3] == 0 and r[17:23] == MINS+MAXS and r[23] == ramp,
                    'multi-patch path attempt ordinal/bump/route/hull/ramp differs')
            require(r[4] == left and r[5:8] == body == r[8:11] and r[11:14] == velocity and
                    close(r[14:17], [s+left*v for s, v in zip(body, velocity)], 2e-5),
                    'multi-patch path attempt time-left/start/velocity/wanted endpoint differs')
            ties = check_trace(r[24:], r[5:8], r[14:17], live)
            fraction, before, rule, contact, error = r[24], body, None, None, None
            require(0 <= fraction <= 1 and (n in validations) == (bump == 0 and fraction == 1),
                    'multi-patch clear endpoint validation coverage differs')
            body = r[34:37]; total += fraction
            if fraction == 1:
                require(o[1] == 1 and bump == len(indices)-1 and o[2] == left and o[6:9] == velocity,
                        'multi-patch clean move not terminal or changed time-left/velocity')
            else:
                require(o[1] == 2 and bump < len(indices)-1 and abs(o[2]-left*(1-fraction)) <= 1e-8,
                        'multi-patch hit not followed by a residual native attempt')
                normal, left = r[29:32], o[2]
                planes = plane_list(planes, normal, fraction)
                rule, error = clip_rule(o[6:9], velocity, planes, primal)
                contact = contact_class(normal)
                if contact == 'RAMP':
                    ramp = 1
                    hits.append((i, r))
                else:
                    blocked = 2
                    walls.append(dict(command_index=i, attempt_ordinal=n, bump=bump, committed_fraction=fraction,
                                      truefraction=r[25], normal=normal, dist=r[32], hit_body=body,
                                      model_entry_planes=entry_planes(live, r[5:8], r[14:17])))
            require(o[3:6] == body and o[9] == ramp, 'multi-patch outcome body/ramp flag differs')
            velocity = o[6:9]
            committed.append(dict(attempt_ordinal=n, native_left_before=r[4], native_left_after=o[2], start=before,
                                  end=body, committed_fraction=fraction, velocity_before=r[11:14],
                                  velocity_after=o[6:9], clip_rule=rule, clip_plane_count=len(planes) if rule else None,
                                  clip_velocity_error=error, contact_class=contact, tied_triangles=ties['triangles'],
                                  tied_candidates=ties['candidates'], tied_planes=ties['planes']))
        # allFraction is a float32 running sum, one rounding per attempt. blocked is 2 for a wall and nothing else here.
        require(returned[:2] == [i, blocked] and close(returned[2:4], [left, total], 2e-7*len(indices)) and
                returned[4:] == [*body, *velocity, ramp], 'unsupported multi-patch return/blocked/body/velocity/ramp')
        require(tick[8] == ramp and tick[10:13] == body and
                close(tick[13:16], [velocity[0], velocity[1], velocity[2]-6], 2e-5),
                'multi-patch return not the actual command body/second half gravity')
        velocity = tick[13:16]
        result.append(dict(command_index=i, call=call, attempts=[attempts[n] for n in indices],
                           outcomes=[outcomes[n] for n in indices], committed_segments=committed, returned=returned))
    require(ordinal == count, 'multi-patch path attempt belongs to no command')
    require(len(hits) == len(accepted), 'multi-patch ramp hits/copied accepted contact count differs')
    for (tick, r), copied in zip(hits, accepted):
        a = copied['contact']
        require(a[1] == tick and a[2] == r[2] and a[3] == 0 and a[4:5] == r[24:25] and a[5:6] == r[32:33] and
                a[6:9] == r[29:32] and a[9:12] == r[5:8] and a[12:15] == r[14:17] and a[15:21] == r[17:23],
                'multi-patch path hit not bound to copied winning contact')
        segment = next(s for s in result[tick]['committed_segments'] if s['attempt_ordinal'] == r[0])
        segment.update(winner_triangle=copied['triangle'], winner_native_leaf_node=copied['native_leaf_node'],
                       winner_plane_tag=copied['copied_winner']['native_plane_tag'],
                       winner_plane_tag_tied_with_model_tag=copied['plane_tag_tied_with_model_tag'],
                       winner_plane_tag_match=copied['plane_tag_match'])
    return dict(calls=result, attempt_count=count, validation_count=len(validations), hit_count=len(hits), wall_hits=walls)


def query(words, tick, case, index, q, live):
    row = numbers(words[:2])+[words[2]]+numbers(words[3:])
    integers([words[i] for i in (0, 1, 11, 12, 13, 18)])
    require(row[:3] == [case, index, pm.QUERIES[q]] and row[3:6] == tick[10:13] and
            row[6:8] == tick[10:12] and close(row[8:9], [tick[12]-(2 if q else 0)], 2e-5),
            'multi-patch query/body/input binding differs')
    for candidate in native_prediction(live if q < 2 else [], row[3:6], row[6:9]):
        try:
            clip.check_observation(row[9:], candidate)
            break
        except AssertionError:
            pass
    else:
        raise AssertionError('multi-patch native query differs from every plane-set candidate')
    return row


def grade_case(block, c, cap, oracle):
    """One actor's own rows and capture: its CASE row up to, not including, its CASE_END."""
    rows, actor, cursor = parse(block), ACTORS[c], 0
    table = authored(c)

    def take(tag):
        nonlocal cursor
        require(cursor < len(rows) and rows[cursor][0] == tag, f'multi-patch {tag} row missing/reordered')
        cursor += 1
        return rows[cursor-1][1]
    require(take('CASE') == [str(c), actor['label'], str(STEPS), str(actor['authored']), str(actor['live'])],
            'multi-patch actor/order/counts differ')
    for j, triangle in enumerate(table):
        require(numbers(take('FIXTURE')) == [c, j, *INDEXES[j], int(j < actor['live']), *(x for v in triangle for x in v)],
                'multi-patch authored fixture/winding/index/active differs')
    leaves = []
    while cursor < len(rows) and rows[cursor][0] == 'LEAF':
        words = take('LEAF'); leaf = numbers(words)
        integers(words[:7])
        require(leaf[:2] == [c, len(leaves)] and leaf[2] >= 0 and leaf[6] == 1,
                'multi-patch native leaf order/node/contents differs')
        leaves.append(dict(node=int(leaf[2]), indexes=[int(x) for x in leaf[3:6]],
                           vertices=[leaf[7+3*k:10+3*k] for k in range(3)]))
    require(take('LEAVES') == [str(c), str(actor['live']), '0'] and len(leaves) == actor['live'] and
            len({x['node'] for x in leaves}) == len(leaves) and
            sorted((x['indexes'], x['vertices']) for x in leaves) ==
            sorted((INDEXES[j], [[float(x) for x in v] for v in t]) for j, t in enumerate(table[:actor['live']])),
            'multi-patch native BIH leaves are not the live authored set')
    # From here on the supplied patch set is the dump itself, in authored order.
    by = {tuple(x['indexes']): x for x in leaves}
    supplied = [by[tuple(INDEXES[j])]['vertices'] for j in range(actor['live'])]
    nodes = [by[tuple(INDEXES[j])]['node'] for j in range(actor['live'])]
    require(numbers(take('SEED')) == [c, *ORIGIN, *actor['velocity'], *MINS, *MAXS], 'multi-patch seed/hull differs')
    ticks, queries = [], []
    for i in range(STEPS):
        w = take('TICK'); t = numbers(w)
        integers([w[j] for j in (*range(7), 8, 9, 22, 23, 25, 26, 27)])
        require(t[:7] == [c, i, 15, 0, 0, 0, 1] and close(t[7:8], [.015], 1e-8) and
                t[8] in (0, 1) and t[9] == 0 and t[16:] == MINS+MAXS+[0]*6,
                'multi-patch actual native command/tick/hull/posture differs')
        ticks.append(t)
        queries.append([query(take('QUERY'), t, c, i, q, supplied) for q in range(3 if oracle else 0)])
    require(cursor == len(rows), 'multi-patch unknown/extra case rows')
    others = set(foreign(block))
    if cap:
        require(others <= LAYERS, 'multi-patch case has rows no reader owns')
        accepted = capture(block, ticks, supplied, nodes)
        native = grade_path(block, c, ticks, accepted, supplied)
    else:
        require(not others, 'quiet multi-patch arm has capture rows')
        accepted, native = [], None
    return dict(label=actor['label'], ticks=ticks, queries=queries, native_leaves=leaves, supplied=supplied,
                accepted=accepted, path=native)


def grade(block):
    rows = parse(block)
    require(len(rows) >= 2 and rows[0][0] == 'BEGIN', 'multi-patch BEGIN differs')
    version, cap, oracle, cases, steps = integers(rows[0][1])
    require((version, cases, steps) == (3, len(ACTORS), STEPS) and cap in (0, 1) and oracle in (0, 1),
            'multi-patch flags/counts differ')
    source = [source_digest(), hashlib.sha256((ROOT/'tools/offramp_motion_native.inc').read_bytes()).hexdigest(),
              'ee1d0201e0b3da97a240c20aee39e316ed8ae643']
    require(rows[1] == ('SOURCE', source), 'multi-patch fixture/base provenance differs')
    blocks = re.findall(r'OFFRAMPTRIMULTI_CASE [0-9]+ .*?(?=OFFRAMPTRIMULTI_CASE_END)', block, re.S)
    require(len(blocks) == len(ACTORS) and rows[2:] == sum((parse(b)+[('CASE_END', [str(c), str(STEPS)])]
                                                           for c, b in enumerate(blocks)), [])+[('END', [str(len(ACTORS))])],
            'multi-patch case envelopes/footers missing, duplicated or reordered')
    require(len(foreign(block)) == sum(len(foreign(b)) for b in blocks), 'multi-patch capture outside cases')
    return dict(capture=cap, oracle=oracle, source=source,
                cases=[grade_case(b, c, cap, oracle) for c, b in enumerate(blocks)])


def sensitivity(triangles, points, shares, horizon):
    """SAT-only coverage at another horizon: where a boundary goes, not a certified domain."""
    pieces = []
    for (a, b), share in zip(zip(points, points[1:]), shares):
        local = [reach.domain(t, a, b, MINS, MAXS, horizon)['coverage'] for t in triangles]
        pieces.append((share, [x for x in local if x is not None]))
    coverage, gaps = walk.glue(pieces)
    return dict(horizon=horizon, coverage=coverage, regained=walk.regained(coverage),
                basis='SAT_ONLY_NOT_DUAL_CERTIFIED_HORIZON_SENSITIVITY')


def track(triangles, names, points, owners, commands, horizon, key):
    result = walk.path_reach(triangles, points, [r['track_share'] for r in owners], MINS, MAXS, horizon)
    probes = walk.probe(triangles, result, MINS, MAXS, horizon)
    found = walk.transitions(result, owners, horizon)
    for transition in found:
        for site in transition['sites']:
            domains = result['segments'][site['attempt_ordinal']]['domains']
            # At a track bound this is simply what is reachable there.
            site['bounding_triangles'] = [names[j] for j, d in enumerate(domains)
                                          if any(p[0] == site['local_t'] for p in d['polygon'])]
    if key:
        for row, local in zip(owners, result['segments']):
            row[key] = local
        for c in commands:
            coverage, gaps = walk.glue([(r['command_share'], r[key]['coverage']) for r in c['segments']])
            c[key] = dict(coverage=coverage, gaps=gaps, covered_share=sum(hi-lo for lo, hi in coverage))
        walk.consistent(result['coverage'], found, commands, key, len(commands))
    seconds = sum(c['duration_seconds'] for c in commands)
    for gap in result['gaps']:
        gap['nominal_seconds_not_exit_clock'] = gap['length']*seconds
    return result, dict(horizon=horizon, common_point_probes=probes, coverage=result['coverage'], gaps=result['gaps'],
                        transitions=found, regained=walk.regained(result['coverage']))


def edge_checks(in_place, hypothetical, triangles):
    """How much the d=0 edge gate had to compare: empty against empty proves nothing."""
    found = [walk.separate(a, b) for a, b in zip(in_place, hypothetical)]
    return dict(segments=len(found), domain_pairs=len(found)*triangles, nonempty_segments=sum(map(bool, found)),
                nonempty_domains=sum(found))


def margins(triangles, origin):
    """How far one body is from each kind of reach boundary, exactly.

    least_down_distance is the smallest downward translation at which the hull
    touches a supplied front (None: moving it straight down never meets one).
    footprint_bounding_slack compares the hull's xy footprint with each
    triangle's xy BOUNDING rectangle and keeps the largest: positive is overlap,
    negative clearance. A bounding rectangle is not the triangle, so the slack
    means what it says only beside an axis-aligned patch edge.
    """
    downs = [d['reach_distance_range'][0] for d in (reach.domain(t, origin, origin, MINS, MAXS, DEEP) for t in triangles)
             if d['reach_distance_range'] is not None]
    p = reach.vector(origin)
    slack = max(min(min(p[k]+MAXS[k], max(reach.rational(v[k]) for v in t)) -
                    max(p[k]+MINS[k], min(reach.rational(v[k]) for v in t)) for k in (0, 1)) for t in triangles)
    return dict(least_down_distance=min(downs) if downs else None, footprint_bounding_slack=slack)


def sharpest(cases, horizon):
    """The tick end nearest each boundary on each side, with what native and the exact reach said there."""
    rows = [dict(actor=i, **e) for i, c in enumerate(cases) for e in c['tick_ends']]
    under = [r for r in rows if r['least_down_distance'] is not None]
    pick = lambda found, key: min(found, key=key) if found else None
    return dict(horizon_inside=pick([r for r in under if r['least_down_distance'] <= horizon], lambda r: horizon-r['least_down_distance']),
                horizon_outside=pick([r for r in under if r['least_down_distance'] > horizon], lambda r: r['least_down_distance']-horizon),
                footprint_inside=pick(under, lambda r: r['footprint_bounding_slack']),
                footprint_outside=pick([r for r in rows if r['footprint_bounding_slack'] < 0], lambda r: -r['footprint_bounding_slack']),
                basis='NEAREST_TICK_END_PER_SIDE_MEASURED_NOT_GATED')


def reach_outcome(coverage):
    """What became of reach along one track: "not regained" alone hides whether it was ever lost.

    A piece of zero length, a touch, counts as a loss and not as a regain. No
    track captured so far has one.
    """
    return dict(reached_at_start=bool(coverage) and coverage[0][0] == 0, reached_at_end=bool(coverage) and coverage[-1][1] == 1,
                times_lost=sum(hi < 1 for _, hi in coverage), times_regained=sum(hi > lo for lo, hi in coverage[1:]))


def assess_actor(index, case):
    actor, live = ACTORS[index], case['supplied']
    removed = authored(index)[actor['live']:]
    body, commands, owners = ORIGIN, [], []
    for call, tick in zip(case['path']['calls'], case['ticks']):
        rows = walk.committed(call, tick, body, len(owners))
        duration = Fraction(int(tick[2]), 1000)  # 15 ms by the tick gate; the call's own 0.015 is bound in grade_path
        body, offset = rows[-1]['end'], Fraction(0)
        for row, share, s in zip(rows, walk.shares(rows, call['call'][2]), call['committed_segments']):
            require(all(abs(reach.rational(e)-reach.rational(a)-reach.rational(v)*share*reach.rational(call['call'][2]))
                        <= Fraction(4, 10**5) for a, e, v in zip(row['start'], row['end'], row['velocity_before'])),
                    'multi-patch committed displacement differs from velocity x nominal share')
            row.update(command_index=call['command_index'], command_share=share, command_offset=offset, track_share=share/STEPS,
                       **{k: s.get(k) for k in ('clip_rule', 'clip_plane_count', 'clip_velocity_error', 'contact_class', 'tied_triangles',
                                                'tied_candidates', 'tied_planes', 'winner_triangle',
                                                'winner_native_leaf_node', 'winner_plane_tag',
                                                'winner_plane_tag_tied_with_model_tag', 'winner_plane_tag_match')})
            offset += share
        owners += rows
        commands.append(dict(command_index=call['command_index'], duration_seconds=duration,
                             native_ramp_return=bool(tick[8]), segments=rows))
    points = [ORIGIN]+[r['end'] for r in owners]
    names, tracks, results = list(range(len(live))), {}, {}
    for name, horizon in HORIZONS:
        results[name], tracks[name] = track(live, names, points, owners, commands, horizon, name)
    edges = edge_checks(results['in_place']['segments'], results['hypothetical_down']['segments'], len(live))
    shares = [r['track_share'] for r in owners]
    rational = [reach.vector(p) for p in points]
    wider = [sensitivity(live, rational, shares, h) for h in SENSITIVITY]
    chain = [tracks['hypothetical_down']['coverage']]+[w['coverage'] for w in wider]
    require(all(any(a <= lo and hi <= b for a, b in outer) for inner, outer in zip(chain, chain[1:]) for lo, hi in inner),
            'multi-patch coverage does not nest across horizons')
    counterfactual = None
    if removed:
        # The supplied leaves plus the authored triangles that were never built. Never live coverage.
        everything = live+removed
        full = {name: track(everything, list(range(len(everything))), points, owners, commands, horizon, None)
                for name, horizon in HORIZONS}
        counterfactual = {name: summary for name, (_, summary) in full.items()}
        # The body falls through where the removed front was: the one place here the d=0 edge is not empty.
        counterfactual['in_place_edge'] = edge_checks(full['in_place'][0]['segments'],
                                                      full['hypothetical_down'][0]['segments'], len(everything))
        counterfactual['basis'] = 'SUPPLIED_LEAVES_PLUS_AUTHORED_TRIANGLES_NEVER_BUILT_NOT_LIVE_COVERAGE'
        require(all(any(a <= lo and hi <= b for a, b in counterfactual['hypothetical_down']['coverage'])
                    for lo, hi in tracks['hypothetical_down']['coverage']), 'full authored set does not contain live reach')
    ends = []
    for tick, queries in zip(case['ticks'], case['queries']):
        seen = any(reach.spatial_witness(t, tick[10:13], MINS, MAXS, HORIZONS[1][1]) is not None for t in live)
        ends.append(dict(tick=int(tick[1]), native_down2_hit=queries[1][9] < 1, exact_horizon2_reach=seen,
                         native_ramp=bool(tick[8]), **margins(live, tick[10:13])))
        # Two computations of one thing: the witness at horizon 2 and the least distance from the SAT domain.
        require(seen == (ends[-1]['least_down_distance'] is not None and ends[-1]['least_down_distance'] <= HORIZONS[1][1]),
                'multi-patch tick-end reach differs from its least down distance')
    hits = []
    for row in owners:
        if row['winner_triangle'] is not None:
            reached = [j for j, t in enumerate(live)
                       if reach.spatial_witness(t, row['end'], MINS, MAXS, HORIZONS[1][1]) is not None]
            hits.append(dict(command_index=row['command_index'], attempt_ordinal=row['attempt_ordinal'], bump=row['bump'],
                             committed_fraction=row['committed_fraction'], truefraction=row['truefraction'],
                             winner_triangle=row['winner_triangle'], winner_native_leaf_node=row['winner_native_leaf_node'],
                             winner_plane_tag=row['winner_plane_tag'],
                             winner_plane_tag_tied_with_model_tag=row['winner_plane_tag_tied_with_model_tag'],
                             winner_plane_tag_match=row['winner_plane_tag_match'],
                             clip_rule=row['clip_rule'], clip_plane_count=row['clip_plane_count'],
                             native_normal=row['native_plane'][:3], velocity_after=row['velocity_after'],
                             tied_triangles=row['tied_triangles'], tied_planes=row['tied_planes'],
                             horizon2_reachable_triangles_at_hit_body=reached,
                             winner_horizon2_reachable_at_hit_body=row['winner_triangle'] in reached))
    # Empty domains carry nothing a reader needs; their constraints are not serialized.
    for row in owners:
        for name, _ in HORIZONS:
            row[name]['domains'] = [d if d['polygon'] else dict(polygon=[], coverage=None, reach_distance_range=None,
                                                               serialized='EMPTY_DOMAIN_CONSTRAINTS_OMITTED')
                                    for d in row[name]['domains']]
    return dict(label=actor['label'], command_count=STEPS, segment_count=len(owners),
                point_segment_count=sum(r['start'] == r['end'] for r in owners),
                supplied_patch_set=dict(triangles=live, indexes=[INDEXES[j] for j in names],
                                        native_leaves=case['native_leaves'],
                                        basis='TRIANGLE_LEAVES_DUMPED_FROM_THE_BUILT_NATIVE_BIH_EQUAL_TO_THE_AUTHORED_TABLE'
                                              '_WHOLE_MODEL_NOT_A_DISCOVERED_NEIGHBORHOOD'),
                authored_triangles_never_built=removed, commands=commands, track=tracks,
                horizon_sensitivity=wider, full_authored_set_counterfactual=counterfactual,
                in_place_edge=edges, native_hits=hits, tick_ends=ends,
                down2_disagreement_ticks=[e['tick'] for e in ends if e['native_down2_hit'] != e['exact_horizon2_reach']],
                # Commands in which a hit was clipped against two or more planes at once, and how each hit was clipped.
                second_plane_commands=sorted({r['command_index'] for r in owners if (r['clip_plane_count'] or 0) > 1}),
                clip_rule_counts={rule: sum(r['clip_rule'] == rule for r in owners) for rule in RULES},
                # How each accepted winner's plane tag was matched: the last kind is the alias for a bevel turned in the model.
                winner_tag_match_counts={kind: sum(h['winner_plane_tag_match'] == kind for h in hits) for kind in TAG_MATCHES},
                # Largest component by which a native clip velocity differs from its rule: how much room the gate had.
                clip_velocity_error={rule: max((r['clip_velocity_error'] for r in owners if r['clip_rule'] == rule), default=None)
                                     for rule in RULES},
                max_attempts_in_a_command=max(len(c['segments']) for c in commands),
                later_bump_hit_count=sum(r['bump'] > 0 and r['native_hit'] for r in owners),
                wall_hits=case['path']['wall_hits'],
                # A candidate is a (triangle, plane) pair, so a face tying its own coplanar bevel is counted apart.
                triangle_tie_trace_count=sum(r['tied_triangles'] > 1 for r in owners),
                plane_only_tie_trace_count=sum(r['tied_triangles'] == 1 and r['tied_candidates'] > 1 for r in owners),
                # A tie between two DIFFERENT planes: neither the winner nor the reported normal is modelled.
                different_plane_tie_trace_count=sum(r['tied_planes'] > 1 for r in owners),
                winner_triangles_in_order=[h['winner_triangle'] for h in hits],
                # Front reach at horizon 2 lost and found again; it says nothing about native contact.
                live_horizon2_reach_regained=walk.recontact_verdict(tracks['hypothetical_down']['regained']),
                live_horizon2_reach_outcome=reach_outcome(tracks['hypothetical_down']['coverage']),
                **walk.ramp_versus_reach([(c['command_index'], c['native_ramp_return'], c['hypothetical_down'])
                                          for c in commands]),
                trajectory_basis='CAPTURED_NATIVE_COMMITTED_SEGMENTS_LINEAR_WITHIN_A_SEGMENT_NEVER_ACROSS_A_COMMAND',
                share_basis=walk.SHARE_BASIS,
                horizon_basis='hypothetical_down IS THE CLOSED RANGE 0<=d<=2 AND CONTAINS in_place')


def exercised(rules, walls):
    """Status labels said per rule and from the counts: a rule no hit took is modelled, not verified.

    What refuses cannot be in a report that passed, so those are constant.
    """
    seen = lambda count: 'VERIFIED_ON_CAPTURED_HITS' if count else 'NOT_EXERCISED'
    return dict(multi_plane_clip=dict(two_plane_crease=seen(rules[CREASE]), along_one_plane=seen(rules[ALONG]),
                                      three_or_more_planes='REFUSED_SO_NOT_EXERCISED', stopping_outcomes='REFUSED_SO_NOT_EXERCISED'),
                wall_return='GRADED_ON_CAPTURED_HITS' if walls else 'NOT_EXERCISED', floor_contact='REFUSED_SO_NOT_EXERCISED')


def first_difference(a, b):
    """First tick at which two actors' captured bodies differ; None if they never do."""
    return next((i for i, (x, y) in enumerate(zip(a['ticks'], b['ticks'])) if x[10:16] != y[10:16]), None)


def removal_acts(kept, removed):
    """First tick at which the removed-neighbour twin's body differs: it must share a prefix, then part."""
    same = first_difference(kept, removed)
    require(same is not None and 0 < same < STEPS and len(removed['native_leaves']) < len(kept['native_leaves']),
            'multi-patch removed-neighbour trajectory did not ACT')
    return same


def same_prior(prior, retained):
    """The predecessor report this capture yields against a retained one; the embedded copy alone proves nothing."""
    ours = json.loads(json.dumps(reach.encoded(prior), allow_nan=False))
    require(all(key in retained and retained[key] == value for key, value in ours.items()),
            'predecessor report from this capture differs from the retained one')
    return 'EQUAL_TO_RETAINED_REPORT'


def compare(*texts, retained=None):
    require(len(texts) == 5, 'multi-patch requires five arms')
    parts = [split(t) for t in texts]
    reports = [grade(p[1]) for p in parts]
    require([(r['capture'], r['oracle']) for r in reports] == [(0, 0), (0, 1), (0, 1), (1, 1), (1, 1)],
            'multi-patch arm modes differ')
    require(all([c['ticks'] for c in r['cases']] == [c['ticks'] for c in reports[0]['cases']] and
                [c['native_leaves'] for c in r['cases']] == [c['native_leaves'] for c in reports[0]['cases']]
                for r in reports), 'multi-patch five-arm body/leaf parity differs')
    require(all([c['queries'] for c in r['cases']] == [c['queries'] for c in reports[1]['cases']] for r in reports[1:]),
            'multi-patch query parity differs')
    require(reports[3] == reports[4], 'multi-patch repeat capture differs')
    native = reports[3]['cases']
    same = removal_acts(native[2], native[3])
    # Every predecessor gate, on the text with the new envelope taken out.
    prior = walk.compare(*(p[0] for p in parts))
    cases = [assess_actor(i, c) for i, c in enumerate(native)]
    probes = [c['track'][n]['common_point_probes'] for c in cases for n, _ in HORIZONS]
    second, walls = sum(len(c['second_plane_commands']) for c in cases), sum(len(c['wall_hits']) for c in cases)
    rules = {rule: sum(c['clip_rule_counts'][rule] for c in cases) for rule in RULES}
    traces =[tuple(a[4:17])+tuple(a[24:37]) for c in native for call in c['path']['calls'] for a in call['attempts']]
    against = [c['full_authored_set_counterfactual']['in_place_edge'] for c in cases if c['full_authored_set_counterfactual']]
    return dict(bounded_multi_patch_gates='PASS', contract=CONTRACT, cases=cases, source=reports[3]['source'],
                native_attempt_count=sum(c['path']['attempt_count'] for c in native),
                native_endpoint_validation_count=sum(c['path']['validation_count'] for c in native),
                accepted_copied_hit_count=sum(c['path']['hit_count'] for c in native),
                committed_segment_count=sum(c['segment_count'] for c in cases),
                # Six actors share their opening commands and most hits are the same re-contact: carry what is distinct.
                distinct=dict(attempts=len(set(traces)), hits=len({t for t in traces if t[13] < 1}),
                              tick_end_bodies=len({tuple(t[10:16]) for c in native for t in c['ticks']}),
                              zero_length_segments=sum(c['point_segment_count'] for c in cases)),
                removed_neighbour_first_differing_tick=same,
                # Against the wide lowered gap (actor 2): where each other cell of the 2 x 2 parts from it, if it does.
                twin_first_differing_tick={ACTORS[i]['label']: first_difference(native[2], native[i]) for i in GAP_DESIGN if i != 2},
                gap_design=[dict(actor=i, label=ACTORS[i]['label'], gap_width=ACTORS[i]['y2']-ACTORS[i]['y1'],
                                 neighbour_lowered=ACTORS[i]['drop'],
                                 horizon2_coverage=cases[i]['track']['hypothetical_down']['coverage'],
                                 horizon2_reach=cases[i]['live_horizon2_reach_outcome'],
                                 wider_horizon_coverage=[w['coverage'] for w in cases[i]['horizon_sensitivity']],
                                 wall_hit_commands=[w['command_index'] for w in cases[i]['wall_hits']],
                                 native_ramp_commands=[c['command_index'] for c in cases[i]['commands'] if c['native_ramp_return']])
                            for i in GAP_DESIGN],
                live_horizon2_reach_regained=[c['live_horizon2_reach_regained'] for c in cases],
                live_horizon2_reach_outcome=[c['live_horizon2_reach_outcome'] for c in cases],
                second_plane_command_count=second, clip_rule_counts=rules, **exercised(rules, walls),
                clip_velocity_error={rule: max((c['clip_velocity_error'][rule] for c in cases if c['clip_velocity_error'][rule] is not None),
                                               default=None) for rule in RULES},
                winner_tag_match_counts={kind: sum(c['winner_tag_match_counts'][kind] for c in cases) for kind in TAG_MATCHES},
                wall_hit_count=walls,
                max_attempts_in_a_command=max(c['max_attempts_in_a_command'] for c in cases),
                later_bump_hit_count=sum(c['later_bump_hit_count'] for c in cases),
                triangle_tie_trace_count=sum(c['triangle_tie_trace_count'] for c in cases),
                plane_only_tie_trace_count=sum(c['plane_only_tie_trace_count'] for c in cases),
                different_plane_tie_trace_count=sum(c['different_plane_tie_trace_count'] for c in cases),
                down2_disagreement_count=sum(len(c['down2_disagreement_ticks']) for c in cases),
                down2_disagreements=[dict(actor=i, **e) for i, c in enumerate(cases) for e in c['tick_ends']
                                     if e['native_down2_hit'] != e['exact_horizon2_reach']],
                tick_end_count=sum(len(c['tick_ends']) for c in cases),
                sharpest_tick_ends=sharpest(cases, HORIZONS[1][1]),
                common_point_probes=dict(parameters=sum(p['parameters'] for p in probes),
                                         inside_coverage=sum(p['inside_coverage'] for p in probes)),
                in_place_edge=dict(live={k: sum(c['in_place_edge'][k] for c in cases) for k in cases[0]['in_place_edge']},
                                   full_authored_set_counterfactual={k: sum(e[k] for e in against) for k in (against or [{}])[0]}),
                predecessor_report=same_prior(prior, retained) if retained is not None else 'NOT_COMPARED_WITH_A_RETAINED_REPORT',
                rational_basis='EXACT_ARITHMETIC_ON_SERIALIZED_DECIMALS_NOT_MEASUREMENT_PRECISION',
                native_cases=native, prior_committed_reach_report=prior,
                general_triangle_support='ABSTAIN', native_front_reach_equivalence='NOT_CLAIMED',
                discovered_neighborhood_topology='NOT_IMPLEMENTED',
                physical_exit_acceptance='NOT_TESTED', standability_load_bearing_acceptance='NOT_TESTED',
                classifier_render_hold_clock='NOT_TESTED', recovery_cached_portal_ground_slide_acceptance='NOT_TESTED')


def load_arms(arms_path):
    texts, provenance = path.load_arms(arms_path)
    arms = json.loads(arms_path.read_text())
    require(all(arms[n].get('trimulti_source_sha256') == source_digest() for n in NAMES),
            'multi-patch manifest/source differs')
    return texts, provenance


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--prior-report', type=Path, help='retained committed-reach report the old envelopes must reproduce')
    a = ap.parse_args()
    if a.output.exists():
        ap.error('Need NEW output file; refusing to overwrite retained evidence')
    texts, provenance = load_arms(a.arms)
    retained = json.loads(a.prior_report.read_text(encoding='utf-8')) if a.prior_report else None
    result = compare(*texts, retained=retained); result['arms'] = provenance
    result['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x', encoding='utf-8') as f:
        f.write(json.dumps(reach.encoded(result), indent=2, allow_nan=False)+'\n')
    print(f"PASS {result['native_attempt_count']} native attempts ({result['distinct']['attempts']} distinct), "
          f"{result['accepted_copied_hit_count']} copied hits, {result['committed_segment_count']} committed segments "
          f"({result['distinct']['zero_length_segments']} zero-length); horizon-2 reach regained "
          f"{result['live_horizon2_reach_regained']}; second-plane commands {result['second_plane_command_count']} "
          f"(crease clips {result['clip_rule_counts'][CREASE]}, along one plane {result['clip_rule_counts'][ALONG]}); "
          f"wall hits {result['wall_hit_count']}; "
          f"down2 disagreements {result['down2_disagreement_count']} of {result['tick_end_count']} tick ends; "
          f"predecessor report {result['predecessor_report']}; support ABSTAIN; exit NOT_TESTED")


if __name__ == '__main__':
    main()
