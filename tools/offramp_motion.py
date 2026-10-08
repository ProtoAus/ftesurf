#!/usr/bin/env python3
"""Acted static-brush native trajectories + full native/joint convex queries.

No halfspace max-gap classification. The bounded fixture oracle is not a
continuous physical-exit timestamp or arbitrary-map support/marker policy.
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
          'interior-input-departure', 'ground-jump', 'overlapping-brush-seam')
STEPS = 32
WIDTHS = {'BEGIN': 5, 'SOURCE': 2, 'PARAM': 2, 'CASE': 4, 'BRUSH': 9, 'PLANE': 7,
          'SEED': 13, 'TICK': 28, 'ORACLE': 19, 'CASE_END': 2, 'END': 1, 'COMPLETE': 0}
PARAMS = dict(zip(('physicsmode ticrate gravity entgravity maxspeed spectatormaxspeed maxairspeed maxvelocity '
                   'accelerate airaccelerate wateraccelerate friction waterfriction stopspeed stepheight '
                   'jumpvelocity standablenormal standheight duckheight duckspeed viewheight duckviewheight '
                   'viewscale walkspeed groundtracedist bumpcount snaptoground groundquadrants fixslopes '
                   'fixedges fixrampbugs rampretrace ladders slide stamina normalizejump jumpaddrise '
                   'jumpzoffset autobunny flags coord_float32').split(),
                  (1, .015, 800, 1, 250, 250, 30, 3500, 5, 150, 10, 4, 1, 75, 18,
                   301.9933774, .7, 62, 45, .34, 64, 47, .5, .52, 2, 8, 1, 1, 1, 1, 2, .2,
                   0, 0, 0, 0, 0, 0, 0, 0, 1)))
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
    count = 2 if case == 5 else 1
    brushes = []
    for b in range(count):
        lo = [-256, -256 if case == 2 else (-8 if b else -64), -512]
        hi = [256, 256 if case == 2 else ((192 if b else 0) if case == 5 else 64), 512]
        planes = [[1, 0, 0, hi[0]], [-1, 0, 0, -lo[0]], [0, 1, 0, hi[1]], [0, -1, 0, -lo[1]],
                  [0, 0, -1, 512], [0 if case == 4 else .8, 0, 1 if case == 4 else .6, 0]]
        if case == 2: planes += [[math.sqrt(.5), math.sqrt(.5), 0, 0]]
        brushes.append({'mins': lo, 'maxs': hi, 'planes': planes})
    x, y = (-40 if case == 2 else -100), (76 if case == 1 else (-32 if case == 5 else 0))
    z = .05 if case == 4 else (12.8-.8*x+.05)/.6
    seed = [x, y, z, 0 if case == 3 else (60 if case == 4 else 300),
            250 if case in (1, 2, 5) else 0, 0 if case in (3, 4) else -400, -16, -16, 0, 16, 16, 62]
    return brushes, seed


def hit(row): return row[10] < 1 and row[11] == row[12] == 0


def oracle_validate(row, tick, brushes):
    case, ordinal = integers(row[:2]); kind = row[2]; brush = integers(row[3:4])[0]
    v = numbers(row[4:]); start, end = v[:3], v[3:6]
    require(0 <= v[6] <= 1 and integers(row[11:13]) == [0, 0], 'invalid/embedded authored oracle fraction/flags')
    require(integers(row[13:14]) == [0], 'oracle fixture entity binding changed')
    contents = integers(row[18:])[0]
    require(0 <= contents <= 0xffffffff, 'invalid oracle contents')
    pos, mins, maxs = tick[10:13], tick[16:19], tick[19:22]
    expected_start, expected_end = pos[:], pos[:]
    if kind == 'down2': expected_end[2] -= 2
    elif kind == 'projected':
        p = brushes[0]['planes'][5]
        low = sum(n*(hi if n < 0 else lo) for n, lo, hi in zip(p[:3], mins, maxs))
        z = (p[3]-low-p[0]*pos[0]-p[1]*pos[1])/p[2]
        expected_start[2], expected_end[2] = z+2, z-2
    else: require(kind == 'stationary', 'unknown oracle query kind')
    require(close(start, expected_start) and close(end, expected_end), 'oracle endpoints not bound to actual tick hull/point')
    subset = brushes if brush == -1 else [brushes[brush]]
    lo = [min(a, b)+m for a, b, m in zip(start, end, mins)]
    hi = [max(a, b)+m for a, b, m in zip(start, end, maxs)]
    joint = any(joint_overlap(b['planes'], lo, hi) for b in subset)
    native = v[6] < 1 or bool(v[7] or v[8])
    require(native == joint, 'native query disagrees with JOINT convex oracle')
    if kind == 'stationary': require(not native, 'authored mover ended embedded in solid')
    if v[6] < 1:
        require(any(close(v[10:14], p) for b in subset for p in b['planes']) and contents == 1,
                'oracle winning plane/contents not authored collider')
    else:
        require(v[10:14] == [0, 0, 0, 0] and contents == 0, 'missed oracle query promoted stale winning data')
    # Mixed row: numeric selectors followed by strings, then numeric results.
    return [case, ordinal, kind, brush]+v


def bind_capture(text, case, ticks, brushes):
    buffer, order = buffer_parse(text)
    contacts = buffer['CONTACT']
    require(buffer['BEGIN'] == [[1, 32768]] and buffer['END'] == [[STEPS, len(contacts), 0]] and
            order == ['BEGIN']+['TICK']*STEPS+['CONTACT']*len(contacts)+['END'], 'invalid case native capture envelope')
    require(len(buffer['TICK']) == STEPS, 'missing captured native tick')
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
        require(r[0] == i and int(r[1]) == r[1] and 0 <= r[1] < STEPS and 0 <= r[4] <= 1 and
                int(r[2]) == r[2] and 0 <= r[2] < 8 and r[3] == 0 and r[21:] == [0, 0, 0], 'invalid accepted fixture trace')
        require(o[:2] == [i, int(r[1])] and o[8] == 0 and o[3] == 1 and o[4] >= 0 and o[5] >= 0 and
                o[6] == 0 and o[7] == 1, 'accepted origin not bound to fixture brush')
        p = payloads[s['payload_id']]
        reason, _ = shape_category(o, r, s, p, 'authored_offramp_motion')
        require(reason == 'copied-world-brush-plane-bound', 'fixture accepted unsupported winning shape')
        matches = [b for b, a in enumerate(brushes) if close(p['model_local_mins'], a['mins']) and close(p['model_local_maxs'], a['maxs']) and
                   len(p['planes']) == len(a['planes']) and all(close(q, z) for q, z in zip(p['planes'], a['planes']))]
        require(len(matches) == 1 and s['capsule'] == 0, 'winning copied shape not an authored whole brush')
        per_tick[int(r[1])] += 1
        winners.append({'ordinal': i, 'tick': int(r[1]), 'brush': matches[0], 'leaf': o[4], 'rootleaf': o[5]})
    for i, (h, t) in enumerate(zip(ht, ticks)):
        require(h['mins'] == t[16:19] and h['maxs'] == t[19:22] and
                [h['ducked'], h['ducking'], h['ducktime_ms'], h['capsule'], h['pm_type'], h['oldbuttons']] == t[22:] and
                close([h['raw_standheight'], h['raw_duckheight']], [62, 45]), 'actual tick hull/posture mismatch')
        require(bool(per_tick[i]) == bool(t[8]), 'ramp flag lacks ACTED accepted contact')
    return winners


def grade(text):
    require('all checks passed' in text and len(re.findall(r'\bok\s+', text)) >= 100 and
            not any(s in text for s in ('Unknown command', 'QC VM error', 'SV_Error', 'check(s) FAILED', 'OFFRAMPMOTION_REFUSE')), 'native command/setup did not ACT')
    rows = parse(text); pos = 0
    def take(tag):
        nonlocal pos
        require(pos < len(rows) and rows[pos][0] == tag, f'missing/duplicate/reordered motion {tag}')
        w = rows[pos][1]; pos += 1; return w
    header = integers(take('BEGIN'))
    require(header[0] == 1 and header[1] in (0, 1) and header[2] in (0, 1) and header[3:] == [6, STEPS], 'unsupported motion header')
    capture, oracle = header[1:3]
    source = take('SOURCE')
    require(re.fullmatch('[0-9a-f]{64}', source[0]) and re.fullmatch('[0-9a-f]{40}', source[1]), 'invalid fixture/source stamp')
    for name, expected in PARAMS.items():
        p = take('PARAM'); require(p[0] == name and close(numbers(p[1:]), [expected], 1e-4), 'wrong/duplicate native input profile')
    cases = []
    blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', text, flags=re.S)
    require(len(blocks) == 6, 'missing/duplicate native case block')
    legacy = ('OFFRAMPBUF_', 'OFFRAMPORIGIN_', 'OFFRAMPGEOM_', 'OFFRAMPHULL_')
    legacy_count = lambda s: sum(any(p in line for p in legacy) for line in s.splitlines())
    require(legacy_count(text) == sum(legacy_count(b) for b in blocks), 'capture rows outside native case envelope')
    if not capture:
        require(not any(s in text for s in ('OFFRAMPBUF_', 'OFFRAMPORIGIN_', 'OFFRAMPGEOM_', 'OFFRAMPHULL_')), 'fixture-only/OFF capture not quiet')
    for c, label in enumerate(LABELS):
        authored_brushes, seed = authored(c); case = take('CASE')
        require(case == [str(c), label, str(STEPS), str(len(authored_brushes))], 'wrong case actor/header')
        brushes = []
        for b, expected in enumerate(authored_brushes):
            row = take('BRUSH'); require(integers(row[:3]) == [c, b, len(expected['planes'])] and close(numbers(row[3:]), expected['mins']+expected['maxs']), 'wrong authored brush')
            planes = []
            for i, p in enumerate(expected['planes']):
                r = take('PLANE'); require(integers(r[:3]) == [c, b, i] and close(numbers(r[3:]), p, 1e-5), 'missing/changed/unordered authored plane')
                planes.append(numbers(r[3:]))
            brushes.append({'mins': numbers(row[3:6]), 'maxs': numbers(row[6:]), 'planes': planes})
        r = take('SEED'); require(integers(r[:1]) == [c] and close(numbers(r[1:]), seed), 'wrong/changed case seed')
        ticks, queries = [], []
        for i in range(STEPS):
            t = numbers(take('TICK'))
            require(t[:7] == [c, i, 15, 250 if c == 3 and i == 3 else 0, 0, 2 if c == 4 and i == 3 else 0, 1] and
                    close(t[7:8], [.015], 1e-8) and t[8] in (0, 1) and t[9] in (0, 1) and
                    t[16:22] == [-16, -16, 0, 16, 16, 62] and t[22:27] == [0, 0, 0, 0, 0] and
                    t[27].is_integer() and 0 <= t[27] <= 255, 'wrong command/tick/hull actor')
            ticks.append(t)
            qrows = []
            if oracle:
                for kind, brush in [('stationary', -1), ('down2', -1), ('projected', -1), *[('projected', b) for b in range(len(brushes))]]:
                    row = take('ORACLE'); require(integers(row[:2]) == [c, i] and row[2:4] == [kind, str(brush)], 'oracle not bound/ordered to native case tick')
                    qrows.append(oracle_validate(row, t, brushes))
            queries.append(qrows)
        require(integers(take('CASE_END')) == [c, STEPS] and math.dist(ticks[-1][10:13], seed[:3]) > 1, 'native trajectory did not ACT')
        winners = bind_capture(blocks[c], c, ticks, brushes) if capture else []
        cases.append({'label': label, 'brushes': brushes, 'seed': numbers(r[1:]), 'ticks': ticks, 'oracles': queries, 'accepted': winners})
    require(integers(take('END')) == [6] and take('COMPLETE') == [] and pos == len(rows), 'missing/duplicate motion completion')
    return {'capture': capture, 'oracle': oracle, 'source': source, 'cases': cases}


def assess(cases):
    for c in cases:
        ts, qs = c['ticks'], c['oracles']
        require(all(qs), 'missing full native query actor')
        c['raw_loss_ticks'] = [i for i in range(1, STEPS) if ts[i-1][8] and not ts[i][8]]
        c['immediate_support_ticks'] = [i for i, q in enumerate(qs) if hit(q[1])]
        c['projected_support_ticks'] = [i for i, q in enumerate(qs) if hit(q[2])]
    a, side, convex, interior, jump, seam = cases
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
    require(len(seam['projected_support_ticks']) == STEPS and all(t[8] for t in seam['ticks']) and
            {a['brush'] for a in seam['accepted']} == {0, 1} and
            len({a['leaf'] for a in seam['accepted']}) == 2 and any(not hit(q[3]) and hit(q[4]) for q in seam['oracles']), 'union/previous-brush seam handoff did not ACT')


def compare(nooracle, control, off, on, repeat):
    reports = [grade(t) for t in (nooracle, control, off, on, repeat)]
    require([(r['capture'], r['oracle']) for r in reports] == [(0, 0), (0, 1), (0, 1), (1, 1), (1, 1)], 'invalid fixture arms')
    require(all(r['source'] == reports[0]['source'] for r in reports), 'native fixture/base provenance differs')
    canonical = lambda r: [{k: c[k] for k in ('label', 'brushes', 'seed', 'ticks', 'oracles')} for c in r['cases']]
    require(all(canonical(r) == canonical(reports[1]) for r in reports[2:]), 'fixture-only/OFF/ON/repeat body/oracle differs')
    require(all(a['ticks'] == b['ticks'] for a, b in zip(reports[0]['cases'], reports[1]['cases'])), 'oracle queries altered later movement')
    require(reports[3] == reports[4], 'repeated captured fixture binding differs')
    assess(reports[3]['cases'])
    digest = hashlib.sha256(json.dumps(canonical(reports[1]), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'native_static_fixture_gates': 'PASS', 'nooracle_body_parity': 'PASS', 'capture_body_oracle_parity': 'PASS',
            'repeat_capture_binding': 'PASS', 'body_oracle_sha256': digest, 'source': reports[3]['source'],
            'cases': reports[3]['cases'], 'physical_exit_acceptance': 'NOT_TESTED', 'classifier_mark_acceptance': 'NOT_TESTED',
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
    print('Six acted native static-brush fixtures: PASS; full native/joint query and capture parity PASS')
    print('Physical timestamp/classifier/mark/unsupported paths/clock/render/rate/hold acceptance: NOT_TESTED')


if __name__ == '__main__': main()
