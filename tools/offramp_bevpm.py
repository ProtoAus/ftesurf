#!/usr/bin/env python3
"""Bounded real PM copied-winning bevel diagnostic; general support ABSTAIN."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from offramp_buffer import parse as buffer_parse, require
from offramp_hull import decode as hull_decode, parse as hull_parse
from offramp_motion import close, numbers
from offramp_origin import CHECKS as ORIGIN_CHECKS, integers, parse as origin_parse
from offramp_shape import decode as shape_decode, parse as shape_parse
from offramp_triangle import NATIVE_BIAS, SPATIAL_TOLERANCE, cross, dot, prism, sub, sweep
from offramp_tricopy import decode as copy_decode, parse as copy_parse
from offramp_tribev import compare as prior_compare, decode as bevel_decode, parse as bevel_parse
from offramp_trislab import decode as slab_decode, parse as slab_parse, load_arms
from offramp_bevpm_smoke import source_digest

ROOT = Path(__file__).resolve().parent.parent
MODEL = 'maps/authored_offramp_bevpm.bsp'
# IEEE float32(-1024/3), serialized by the registered native %.9g contract.
VERTICES = [[0, 0, 0], [0, 256, -341.333344], [256, 0, -256]]
MINS, MAXS = [-16, -16, 0], [16, 16, 62]
SEED = [-8, 64, -32, -25, 200, -400, *MINS, *MAXS]
LABELS = ('edge-bevel-departure', 'removed-triangle-control', 'bevel-disabled-control')
QUERIES = ('stationary', 'down2', 'untriangled')
WIDTHS = dict(BEGIN=5, SOURCE=3, CASE=5, FIXTURE=13, SEED=13, TICK=28, QUERY=19, CASE_END=2, END=1)
NAMES = ('nooracle', 'control', 'off', 'on', 'repeat')


def parse(text):
    rows = []
    for line in text.splitlines():
        p = line.find('OFFRAMPBEVPM_')
        if p < 0:
            continue
        words = line[p:].split()
        tag = words[0].removeprefix('OFFRAMPBEVPM_')
        require(tag in WIDTHS and len(words)-1 == WIDTHS[tag], 'unknown/malformed bevel PM row')
        rows.append((tag, words[1:]))
    return rows


def split(text):
    rows = parse(text)
    matches = list(re.finditer(r'OFFRAMPBEVPM_BEGIN[^\n]*\n.*?OFFRAMPBEVPM_END[^\n]*(?:\n|$)', text, re.S))
    require(len(matches) == 1, 'missing/duplicate bevel PM envelope')
    m = matches[0]
    block = m.group()
    require(parse(block) == rows, 'bevel PM rows outside envelope')
    return text[:m.start()]+text[m.end():], block


def entry_check(vertices, start, end, fraction, normal, dist, truefraction=None):
    """Complete independent finite-prism SAT; native plane never constructs it."""
    ideal = sweep(vertices, start, end, MINS, MAXS)
    require(ideal['intersects'] and not ideal['starts_overlap'] and ideal['entry_planes'],
            'copied bevel PM SAT did not ACT clear-start entry')
    planes = [p for p in ideal['entry_planes'] if close(p[:3], normal, 1e-5) and
              abs(p[3]-dist) <= SPATIAL_TOLERANCE]
    require(planes, 'copied bevel PM SAT entry plane differs')
    speed = abs(dot(sub(end, start), planes[0][:3]))
    require(speed > 1e-9, 'copied bevel PM closing sweep did not ACT')
    expected = max(0, ideal['enter']-NATIVE_BIAS/speed)
    require(abs(fraction-expected)*speed <= SPATIAL_TOLERANCE, 'copied bevel PM fraction/bias differs')
    if truefraction is not None:
        require(abs(truefraction-ideal['enter'])*speed <= SPATIAL_TOLERANCE, 'bevel PM truefraction differs')
    return dict(expected_biased_fraction=expected, **ideal)


def ghost_plane_check(vertices, start, end, fraction, normal, dist, truefraction=None):
    """Independent old edge-side plane prediction, explicitly NOT physical SAT."""
    _, front = prism(vertices)
    axis = cross(sub(vertices[1], vertices[0]), front)
    length = math.sqrt(dot(axis, axis))
    require(length > 1e-9, 'degenerate OFF ghost edge')
    axis = [x/length for x in axis]
    if dot(sub(vertices[2], vertices[0]), axis) > 0:
        axis = [-x for x in axis]
    distance = dot(vertices[0], axis)
    require(close(normal, axis, 1e-5) and abs(dist-distance) <= SPATIAL_TOLERANCE, 'OFF ghost side plane differs')
    support = sum(a*(lo if a >= 0 else hi) for a, lo, hi in zip(axis, MINS, MAXS))
    a = dot(start, axis)-distance+support
    b = dot(end, axis)-distance+support
    speed = a-b
    require(a >= -SPATIAL_TOLERANCE and speed > 1e-9, 'OFF ghost plane entry did not ACT')
    entry = max(0, a/speed)
    require(abs(fraction-max(0, entry-NATIVE_BIAS/speed))*speed <= SPATIAL_TOLERANCE,
            'OFF ghost side fraction/bias differs')
    if truefraction is not None:
        require(abs(truefraction-entry)*speed <= SPATIAL_TOLERANCE, 'OFF ghost truefraction differs')


def query(words, tick, case, index, q):
    row = numbers(words[:2])+[words[2]]+numbers(words[3:])
    integers([words[i] for i in (0, 1, 11, 12, 13, 18)])
    require(row[:3] == [case, index, QUERIES[q]] and row[3:6] == tick[10:13] and
            row[6:8] == tick[10:12] and close(row[8:9], [tick[12]-(2 if q else 0)], 2e-5),
            'bevel PM query/body/input binding differs')
    require(0 <= row[9] <= 1 and 0 <= row[10] <= 1 and row[11:13] == [0, 0],
            'bevel PM actual/counterfactual query embedded or fraction invalid')
    hit = row[9] < 1
    if not hit:
        require(row[9:] == [1, 0, 0, 0, -1, 0, 0, 0, 0, 0], 'bevel PM native miss retains stale output')
    else:
        require(case != 1 and q == 1 and row[13] == 0 and row[18] == 1 and
                abs(dot(row[14:17], row[14:17])-1) < 1e-5 and row[17] == 0,
                'bevel PM query unsupported plane/winner/contents')
    ideal = sweep(VERTICES, row[3:6], row[6:9], MINS, MAXS)
    if case == 0 and q == 1 and hit:
        require(close(row[14:17], [0, .8, .6], 1e-5), 'bevel PM native query not registered front-edge plane')
        entry_check(VERTICES, row[3:6], row[6:9], row[9], row[14:17], row[17], row[10])
    if case == 2 and q == 1 and hit:
        ghost_plane_check(VERTICES, row[3:6], row[6:9], row[9], row[14:17], row[17], row[10])
    if q == 0 or q == 2 or case == 1:
        require(not hit, 'stationary/removal bevel PM query did not ACT clear')
    # Native original-triangle axial clipping can exclude extruded back corners.
    # A miss remains a native observation, never an independent support decision.
    return row, dict(native_hit=hit, active=case != 1 and q != 2, ideal_prism=ideal,
                     geometry_basis='AUTHORED_FIXTURE_NOT_ACCEPTED_COPY', native_miss_support='ABSTAIN')


def capture(block, ticks, case):
    buffer, order = buffer_parse(block)
    contacts = buffer['CONTACT']
    require(buffer['BEGIN'] == [[1, 32768]] and buffer['END'] == [[32, len(contacts), 0]] and
            order == ['BEGIN']+['TICK']*32+['CONTACT']*len(contacts)+['END'], 'bevel PM buffer envelope differs')
    for i, (r, t) in enumerate(zip(buffer['TICK'], ticks)):
        require(r[:4] == [i, i, i+1, i+1] and close(r[4:7], t[7:10]) and r[7:13] == t[10:16],
                'bevel PM body not bound to actual captured tick')
    origins, order = origin_parse(block)
    require(origins['CHECK'] == [[str(i), n, '1'] for i, n in enumerate(ORIGIN_CHECKS, 1)] and
            origins['SELFTEST'] == [[str(len(ORIGIN_CHECKS)), '0']] and
            order == ['CHECK']*len(ORIGIN_CHECKS)+['SELFTEST']+['CONTACT']*len(contacts), 'bevel PM origin setup differs')
    origin_rows = [integers(w[:9])+[w[9]] for w in origins['CONTACT']]
    payloads, shapes, _ = shape_decode(block, contacts, origin_rows)
    ht, hc, _ = hull_decode(block, buffer['TICK'], contacts, shapes)
    copies = copy_decode(block, contacts, origin_rows)
    bevel_decode(block); slab_decode(block)
    per_tick, results = Counter(), []
    for i, (r, o, s, h, cp) in enumerate(zip(contacts, origin_rows, shapes, hc, copies)):
        t = int(r[1]); p = payloads[s['payload_id']]
        require(r[:4] == [i, t, 0, 0] and 0 <= t < 32 and 0 <= r[4] < 1 and r[21:] == [0]*3 and
                r[15:21] == MINS+MAXS and o == [i, t, 0, 2, 0, 0, 0, 1, 0, MODEL],
                'bevel PM accepted trace/route/world/origin binding differs')
        require(p['status'] == p['source_side_count'] == 0 and not p['planes'] and
                s['capsule'] == 0 and s['direct_bih_callback'] == 1 and
                s['instance_origin'] == s['instance_angles'] == [0]*3 and s['raw_instance_scale'] == 1,
                'bevel PM empty brush/actual instance binding differs')
        require(h['mins'] == MINS and h['maxs'] == MAXS and
                [h['capsule'], h['pm_type'], h['ducked'], h['ducking'], h['ducktime_ms'], h['oldbuttons']] == [0]*6 and
                [h['raw_standheight'], h['raw_duckheight']] == [62, 45], 'bevel PM contact actual posture differs')
        require(cp['status'] == 1 and cp['indexes'] == [0, 1, 2] and cp['vertices'] == VERTICES and
                cp['back_slab'] == 4 and cp['native_bevels_applied'] == int(case != 2) and
                cp['native_plane_tag'] == (5 if case == 0 else 2) and case != 1,
                'bevel PM winning copy/index/xyz/slab/tag/bevel binding differs')
        start = SEED[:3] if t == 0 else ticks[t-1][10:13]
        velocity = SEED[3:6] if t == 0 else ticks[t-1][13:16]
        endpoint = [p+.015*(v-(6 if axis == 2 else 0)) for axis, (p, v) in enumerate(zip(start, velocity))]
        require(close(r[9:12], start, 2e-5) and close(r[12:15], endpoint, 2e-5),
                'bevel PM accepted sweep not bound to previous body/half-gravity velocity')
        if case == 0:
            require(close(r[6:9], [0, .8, .6], 1e-5) and r[5] == 0, 'bevel PM accepted bevel plane differs')
            ideal = entry_check(cp['vertices'], r[9:12], r[12:15], r[4], r[6:9], r[5])
        else:
            ghost_plane_check(cp['vertices'], r[9:12], r[12:15], r[4], r[6:9], r[5])
            ideal = sweep(cp['vertices'], r[9:12], r[12:15], MINS, MAXS)
            pos = [s+r[4]*(e-s) for s, e in zip(r[9:12], r[12:15])]
            require(not sweep(cp['vertices'], pos, pos, MINS, MAXS)['starts_overlap'],
                    'bevel-disabled earlier ghost contact did not ACT')
        per_tick[t] += 1
        results.append(dict(contact=r, origin=o, copied_winner=cp, ideal_prism=ideal,
                            geometry_basis='COPIED_WINNING_NATIVE_TRIANGLE', geometry_category='world-triangle-unresolved'))
    require(len(ht) == len(ticks) == 32, 'missing bevel PM captured tick hull')
    for i, (h, t) in enumerate(zip(ht, ticks)):
        current = [r for r in contacts if r[1] == i]
        expected_cache = current[-1][6:9] if current else [0]*3
        require(close(buffer['TICK'][i][13:], expected_cache, 1e-5), 'bevel PM native rampnormal cache differs')
        require(h['mins'] == t[16:19] and h['maxs'] == t[19:22] and
                [h['ducked'], h['ducking'], h['ducktime_ms'], h['capsule'], h['pm_type'], h['oldbuttons']] == t[22:] and
                [h['raw_standheight'], h['raw_duckheight']] == [62, 45] and bool(per_tick[i]) == bool(t[8]),
                'bevel PM ramp/posture not bound to ACTED capture')
    return results


def fixture(words, case):
    require(numbers(words) == [case, 0, 1, 2, *(x for v in VERTICES for x in v)],
            'bevel PM fixture/winding/index differs')


def seed(words, case):
    require(numbers(words) == [case, *SEED], 'bevel PM seed/hull differs')


def grade(block):
    rows = parse(block)
    require(len(rows) >= 2 and rows[0][0] == 'BEGIN', 'bevel PM BEGIN differs')
    version, cap, oracle, cases, steps = integers(rows[0][1])
    require((version, cases, steps) == (1, 3, 32) and cap in (0, 1) and oracle in (0, 1), 'bevel PM flags/counts differ')
    source = [source_digest(), hashlib.sha256((ROOT/'tools/offramp_motion_native.inc').read_bytes()).hexdigest(),
              'ee1d0201e0b3da97a240c20aee39e316ed8ae643']
    require(rows[1] == ('SOURCE', source), 'bevel PM fixture/base provenance differs')
    blocks = re.findall(r'OFFRAMPBEVPM_CASE [0-9]+ .*?(?=OFFRAMPBEVPM_CASE_END)', block, re.S)
    require(len(blocks) == 3, 'bevel PM case envelopes missing/duplicated')
    cursor, result = 2, []
    for c, b in enumerate(blocks):
        require(rows[cursor] == ('CASE', [str(c), LABELS[c], '32', str(int(c != 1)), str(int(c != 2))]),
                'bevel PM actor/active/mode/order differs')
        require(rows[cursor+1][0] == 'FIXTURE' and rows[cursor+2][0] == 'SEED', 'bevel PM fixture/seed order differs')
        fixture(rows[cursor+1][1], c); seed(rows[cursor+2][1], c)
        cursor += 3
        ticks, qs, qr = [], [], []
        for i in range(32):
            tag, w = rows[cursor]; cursor += 1
            require(tag == 'TICK', 'bevel PM tick missing/reordered')
            t = numbers(w)
            integers([w[j] for j in (*range(7), 8, 9, 22, 23, 25, 26, 27)])
            require(t[:7] == [c, i, 15, 0, 0, 0, 1] and close(t[7:8], [.015], 1e-8) and
                    t[8] in (0, 1) and t[9] == 0 and t[16:] == MINS+MAXS+[0]*6,
                    'bevel PM actual native command/tick/hull/posture differs')
            ticks.append(t); queries, diagnostics = [], []
            for q in range(3 if oracle else 0):
                tag, w = rows[cursor]; cursor += 1
                require(tag == 'QUERY', 'bevel PM query missing/reordered')
                row, d = query(w, t, c, i, q); queries.append(row); diagnostics.append(d)
            qs.append(queries); qr.append(diagnostics)
        require(rows[cursor] == ('CASE_END', [str(c), '32']), 'bevel PM case footer differs'); cursor += 1
        if cap:
            accepted = capture(b, ticks, c)
        else:
            require(not re.search(r'OFFRAMP(?:BUF|ORIGIN|SHAPE|HULL|TRICOPY|TRISLAB|TRIBEV)_', b), 'quiet bevel PM arm has capture rows')
            accepted = []
        result.append(dict(label=LABELS[c], ticks=ticks, queries=qs, query_diagnostics=qr, accepted=accepted))
    require(rows[cursor:] == [('END', ['3'])], 'bevel PM unknown/extra/footer rows')
    if cap:
        for parser in (buffer_parse, origin_parse):
            require(parser(block)[1] == sum((parser(b)[1] for b in blocks), []), 'bevel PM capture outside cases')
        for parser in (shape_parse, hull_parse, copy_parse, bevel_parse, slab_parse):
            require(parser(block) == sum((parser(b) for b in blocks), []), 'bevel PM capture/setup outside cases')
    else:
        require(not re.search(r'OFFRAMP(?:BUF|ORIGIN|SHAPE|HULL|TRICOPY|TRISLAB|TRIBEV)_', block),
                'quiet bevel PM envelope has capture rows')
    ramp = [[i for i, t in enumerate(c['ticks']) if t[8]] for c in result]
    losses = [i for i in range(1, 32) if result[0]['ticks'][i-1][8] and not result[0]['ticks'][i][8]]
    require(ramp[0] and not ramp[1] and ramp[2] and min(ramp[2]) < min(ramp[0]) and losses and
            result[0]['ticks'][0][10:16] == result[1]['ticks'][0][10:16] and
            result[0]['ticks'][-1][10:16] != result[1]['ticks'][-1][10:16] and
            result[0]['ticks'][-1][10:16] != result[2]['ticks'][-1][10:16], 'bevel PM positive/removal/OFF trajectory did not ACT')
    if oracle:
        hits = [i for i, qs in enumerate(result[0]['queries']) if qs[1][9] < 1]
        misses = [i for i, qs in enumerate(result[0]['queries']) if qs[1][9] == 1]
        require(hits and misses and min(hits) < max(misses) and all(qs[2][9] == 1 for qs in result[0]['queries']),
                'bevel PM down2 hit/later miss/removal query did not ACT')
    return dict(capture=cap, oracle=oracle, source=source, cases=result, ramp_ticks=ramp, raw_loss_ticks=losses)


def compare(*texts):
    require(len(texts) == 5, 'bevel PM requires five arms')
    splittexts = [split(t) for t in texts]
    prior = prior_compare(*(t[0] for t in splittexts))
    reports = [grade(t[1]) for t in splittexts]
    require([(r['capture'], r['oracle']) for r in reports] == [(0, 0), (0, 1), (0, 1), (1, 1), (1, 1)], 'bevel PM arm modes differ')
    require(all([[c['ticks'] for c in r['cases']] == [c['ticks'] for c in reports[0]['cases']] for r in reports]),
            'bevel PM five-arm body parity differs')
    require(all([[c['queries'] for c in r['cases']] == [c['queries'] for c in reports[1]['cases']] for r in reports[1:]]),
            'bevel PM query parity differs')
    require(reports[3] == reports[4], 'bevel PM repeat capture differs')
    return dict(bounded_pm_copied_bevel_entry_and_bias='PASS', bevel_disabled_earlier_ghost_contacts='ACTED',
                triangle_removal_trajectory='ACTED', five_arm_body_query_parity='PASS', runtime_repeat='PASS',
                original_twenty_case_report=prior, source=reports[3]['source'], cases=reports[3]['cases'],
                ramp_ticks=reports[3]['ramp_ticks'], raw_loss_ticks=reports[3]['raw_loss_ticks'],
                general_triangle_support='ABSTAIN', general_native_triangle_semantics='NOT_VERIFIED',
                physical_exit_acceptance='NOT_TESTED', classifier_render_hold='NOT_TESTED')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'bevel PM report needs NEW path')
    texts, provenance = load_arms(a.arms)
    arms = json.loads(a.arms.read_text())
    require(all(arms[n].get('bevpm_source_sha256') == source_digest() for n in NAMES), 'bevel PM arm fixture identity differs')
    result = compare(*texts); result['provenance'] = provenance
    with a.output.open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print('Real PM copied-winning bevel SAT/bias, removal, bevel-OFF ghosts and five-arm parity PASS; support ABSTAIN')


if __name__ == '__main__':
    main()
