#!/usr/bin/env python3
"""Bounded ACTED native TryPlayerMove attempt/commit provenance; exit NOT_TESTED.

Fixed standing identity actors only. No interpolation substituted for the native
path; all attempts, validation queries, outcomes and returns must be present.
Unsupported recovery/cached/portal/ground/sliding routes fail this bounded gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import offramp_bevclip as clip
import offramp_bevpm as pm
from offramp_buffer import require
from offramp_motion import close, numbers
from offramp_origin import integers
from offramp_triangle import sweep
from offramp_tripath_smoke import source_digest

CONTRACT = 'CAPTURED_ORDINARY_TRYPLAYERMOVE_IDENTITY_STANDING_AABB_V1'
WIDTHS = dict(BEGIN=6, CALL=28, ATTEMPT=37, VALIDATE=18, OUTCOME=10, RETURN=11, END=1)
INTS = dict(CALL=(*range(2), *range(3, 8), *range(20, 24), 25, 26, 27),
            ATTEMPT=(*range(4), 23, 26, 27, 28, 33), VALIDATE=(0, 1, 7, 8, 9, 14),
            OUTCOME=(0, 1, 9), RETURN=(0, 1, 10))


def parse(text):
    result = []
    for line in text.splitlines():
        pos = line.find('OFFRAMPTRIPATH_')
        if pos < 0:
            continue
        words = line[pos:].split(); tag = words[0].removeprefix('OFFRAMPTRIPATH_'); words = words[1:]
        require(tag in WIDTHS and len(words) == WIDTHS[tag], 'unknown/malformed path row')
        if tag == 'BEGIN':
            integers(words[:5]); require(words[5] == source_digest(), 'path source contract differs')
        else:
            numbers(words); integers([words[i] for i in INTS.get(tag, range(len(words)))])
        result.append((tag, words))
    return result


def same(got, want, message, tolerance=2e-5):
    require(len(got) == len(want) and close(got, want, tolerance), message)


def check_trace(row, start, end, case):
    require(len(row) == 13, 'path trace width differs')
    prediction = clip.prediction(pm.VERTICES, start, end, pm.MINS, pm.MAXS, case != 2)
    if case == 1:
        prediction = dict(expected=[1, 0, 0, 0, -1, 0, 0, 0, 0, 0])
    clip.check_observation(row[:10], prediction)
    same(row[10:], [s+row[0]*(e-s) for s, e in zip(start, end)], 'path trace endpoint/fraction differs')


def grade_case(block, case, previous):
    rows = parse(block)
    require(rows and rows[0][0] == 'BEGIN', 'missing path envelope')
    begin = integers(rows[0][1][:5]); count = begin[3]
    require(begin[:3] == [1, case, 32] and begin[4] == 0 and 32 <= count <= 64,
            'path version/case/calls/count/overflow differs')
    require(rows[-1] == ('END', [str(case)]), 'path footer differs')
    cursor, calls, attempts, validations, outcomes, returns = 1, [], [], {}, [], []
    for i in range(32):
        require(rows[cursor][0] == 'CALL', 'missing/reordered native path call')
        c = numbers(rows[cursor][1]); cursor += 1
        require(c[:2] == [i, i] and c[3:8] == [0, 0, 1, 0, 0] and c[14:] == pm.MINS+pm.MAXS+[0]*8,
                'unsupported path call/route/posture/ramp context')
        same(c[2:3], [.015], 'path native command duration differs', 1e-8)
        priorbody = pm.SEED[:6] if i == 0 else previous['ticks'][i-1][10:16]
        same(c[8:11], priorbody[:3], 'path call not bound to command input body')
        same(c[11:14], [priorbody[3], priorbody[4], priorbody[5]-6], 'path call not bound to native half-gravity velocity')
        calls.append(c)
    for n in range(count):
        require(rows[cursor][0] == 'ATTEMPT', 'missing/reordered native path attempt')
        r = numbers(rows[cursor][1]); cursor += 1
        require(r[0] == n and 0 <= r[1] < 32 and r[2] in (0, 1) and r[3] == 0 and r[17:23] == pm.MINS+pm.MAXS,
                'path attempt ordinal/call/bump/route/hull differs')
        check_trace(r[24:], r[5:8], r[14:17], case)
        if rows[cursor][0] == 'VALIDATE':
            v = numbers(rows[cursor][1]); cursor += 1
            require(v[:2] == [n, 1] and v[2:5] == r[34:37], 'path validation identity/start differs')
            check_trace(v[5:], v[2:5], v[2:5], case)
            require(v[5:] == [1, 0, 0, 0, -1, 0, 0, 0, 0, 0, *v[2:5]], 'path endpoint validation did not ACT clear')
            validations[n] = v
        require(rows[cursor][0] == 'OUTCOME', 'missing/reordered native path outcome')
        o = numbers(rows[cursor][1]); cursor += 1
        require(o[0] == n and o[1] in (1, 2), 'unsupported path outcome/refusal')
        attempts.append(r); outcomes.append(o)
    for i in range(32):
        require(rows[cursor][0] == 'RETURN', 'missing/reordered native path return')
        r = numbers(rows[cursor][1]); cursor += 1
        require(r[:2] == [i, 0], 'unsupported path return/floor/wall')
        returns.append(r)
    require(rows[cursor:] == [('END', [str(case)])], 'extra path rows or incomplete envelope')
    bycall, accepted = [], []
    for i, call in enumerate(calls):
        indices = [n for n, r in enumerate(attempts) if r[1] == i]
        require(1 <= len(indices) <= 2 and indices == list(range(indices[0], indices[-1]+1)),
                'path attempts not contiguous within command')
        body, velocity, left, ramp, total = call[8:11], call[11:14], call[2], 0, 0
        committed = []
        for bump, n in enumerate(indices):
            r, o = attempts[n], outcomes[n]
            require(r[2] == bump and r[23] == ramp, 'path bump/ramp transition differs')
            same(r[4:5], [left], 'path native time-left continuity differs', 1e-8)
            same(r[5:8], body, 'path actual trace start not previous committed body')
            same(r[8:11], body, 'path fixed origin differs from ordinary native trace start')
            same(r[11:14], velocity, 'path preclip velocity continuity differs')
            same(r[14:17], [s+left*v for s, v in zip(body, velocity)], 'path wanted endpoint/time-left differs')
            fraction = r[24]
            require(0 <= fraction <= 1 and (n in validations) == (bump == 0 and fraction == 1),
                    'path clear endpoint validation coverage differs')
            before = body
            body = r[34:37]; total += fraction
            if fraction < 1:
                require(bump == 0 and o[1] == 2 and len(indices) == 2, 'path hit not followed by residual native attempt')
                normal = r[29:32]; into = sum(v*a for v, a in zip(velocity, normal))
                velocity = [v-into*a for v, a in zip(velocity, normal)]
                left *= 1-fraction; ramp = 1
                accepted.append((i, r))
            else:
                require(o[1] == 1 and bump == len(indices)-1, 'path clean move not terminal native attempt')
                # Native code breaks before reducing time_left on a clean pass.
            same(o[2:3], [left], 'path outcome native time-left differs', 1e-8)
            same(o[3:6], body, 'path committed body/trace endpoint differs')
            same(o[6:9], velocity, 'path native clip velocity differs', 8e-5)
            require(o[9] == ramp, 'path outcome ramp flag differs')
            committed.append(dict(attempt_ordinal=n, native_left_before=r[4], native_left_after=o[2],
                                  start=before, end=body, committed_fraction=fraction,
                                  velocity_before=r[11:14], velocity_after=o[6:9]))
            velocity = o[6:9]  # captured float32 result, after independent algebra gate
        returned = returns[i]
        same(returned[2:4], [left, total], 'path return time-left/allFraction differs', 2e-7)
        require(returned[4:] == [*body, *velocity, ramp], 'path return/body/velocity/ramp differs from final outcome')
        tick = previous['ticks'][i]
        require(tick[8] == ramp, 'path return/native command ramp flag differs')
        same(tick[10:13], body, 'path committed return not actual command body')
        same(tick[13:16], [velocity[0], velocity[1], velocity[2]-6], 'path return/final half-gravity differs')
        bycall.append(dict(command_index=i, call=call, attempts=[attempts[n] for n in indices],
                           outcomes=[outcomes[n] for n in indices], committed_segments=committed, returned=returned))
    require(len(accepted) == len(previous['accepted']), 'path actual hits/copied accepted contact count differs')
    for (tick, r), copied in zip(accepted, previous['accepted']):
        a = copied['contact']
        require(a[1] == tick and a[2] == r[2] and a[3] == 0 and a[4:5] == r[24:25] and
                a[5:6] == r[32:33] and a[6:9] == r[29:32] and a[9:12] == r[5:8] and
                a[12:15] == r[14:17] and a[15:21] == r[17:23], 'path hit not bound to copied winning contact')
    return dict(case_index=case, calls=bycall, attempt_count=count, validation_count=len(validations),
                hit_count=len(accepted), attempted_geometry_basis='AUTHORED_FIXTURE_FOR_MISSES_COPIED_WINNER_FOR_HITS',
                validations=validations)


def compare(*texts):
    prior = clip.compare(*texts)
    blocks = [pm.split(t)[1] for t in texts]
    for b in blocks[:3]:
        require(not parse(b), 'quiet native path arm contains capture rows')
    result = []
    for b in blocks[3:]:
        cases = re.findall(r'OFFRAMPBEVPM_CASE [0-9]+ .*?(?=OFFRAMPBEVPM_CASE_END)', b, re.S)
        require(len(cases) == 3 and parse(b) == sum((parse(c) for c in cases), []), 'native path rows outside case')
        result.append([grade_case(c, i, prior['prior_pm_report']['cases'][i]) for i, c in enumerate(cases)])
    require(all(parse(t) == parse(b) for t, b in zip(texts, blocks)), 'native path rows outside PM envelope')
    require(result[0] == result[1], 'native path repeat differs')
    cases = result[0]
    require([c['attempt_count'] for c in cases] == [44, 32, 38] and
            [c['validation_count'] for c in cases] == [20, 32, 26] and
            [c['hit_count'] for c in cases] == [12, 0, 6], 'native path clear/hit/residual/removal actors did not ACT')
    loss = cases[0]['calls'][22]
    require(len(loss['attempts']) == 1 and loss['attempts'][0][24] == 1 and
            not sweep(pm.VERTICES, loss['attempts'][0][5:8], loss['attempts'][0][14:17], pm.MINS, pm.MAXS)['intersects'],
            'actual raw-loss first sweep not native/ideal clear')
    return dict(bounded_native_attempt_commit_gates='PASS', contract=CONTRACT, cases=cases,
                actual_raw_loss_first_move='CAPTURED_NATIVE_AND_IDEAL_CLEAR', prior_plane_set_report=prior,
                native_attempt_count=114, native_endpoint_validation_count=78,
                accepted_copied_hit_count=18, actual_committed_segment_count=114,
                general_native_path_acceptance='ABSTAIN', recovery_cached_portal_ground_slide_acceptance='NOT_TESTED',
                physical_exit_acceptance='NOT_TESTED', classifier_render_hold_clock='NOT_TESTED')


def load_arms(path):
    texts, provenance = pm.load_arms(path)
    arms = json.loads(path.read_text())
    modes = ((0, 0), (0, 1), (0, 1), (1, 1), (1, 1))
    require(all(arms[n].get('tripath_source_sha256') == source_digest() and
                arms[n].get('bevpm_source_sha256') == pm.source_digest() and
                all(type(arms[n].get(k)) is int for k in ('capture', 'oracle')) and
                (arms[n]['capture'], arms[n]['oracle']) == mode for n, mode in zip(pm.NAMES, modes)),
            'native path manifest/source/mode differs')
    return texts, provenance


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if a.output.exists():
        ap.error('Need NEW output file; refusing to overwrite retained evidence')
    texts, provenance = load_arms(a.arms)
    result = compare(*texts); result['arms'] = provenance
    result['reader_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print('PASS 114 actual native attempts/commits, 78 validations, 18 copied hits; exit NOT_TESTED')


if __name__ == '__main__':
    main()
