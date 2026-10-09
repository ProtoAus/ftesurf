#!/usr/bin/env python3
"""Return-bound copied winning triangle diagnostic; general support ABSTAIN.

Copy identity is actual native leaf/index/xyz, not a current probe or authored
wiring substitution. Bounded standing-world actor sweep checks use copied xyz.
Native general axial/broadphase/bevel/slab semantics remain unverified.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from offramp_buffer import parse as buffer_parse, require
from offramp_motion import LABELS, WORLD_MODEL, close, compare as motion_compare, numbers
from offramp_origin import integers, parse as origin_parse
from offramp_triangle import NATIVE_BIAS, SPATIAL_TOLERANCE, dot, prism, sub, sweep

ROOT = Path(__file__).resolve().parent.parent
CHECKS = ('whole-winning-triangle', 'indexes-mutation-preserves-copy', 'vertices-mutation-preserves-copy',
          'different-output-address-abstains', 'later-same-kind-probe-preserves-copy', 'nearer-same-kind-replaces-copy',
          'triangle-equal-fraction-replaces', 'brush-winner-clears-triangle', 'null-source-clears-copy',
          'null-xyz-invalid-not-partial', 'null-indexes-invalid-not-partial', 'degenerate-source-invalid-not-partial',
          'losing-nested-triangle-copy', 'winning-nested-local-triangle-copy', 'losing-physent-triangle-copy',
          'winning-physent-triangle-copy', 'translated-triangle-copy-metadata', 'capsule-triangle-copy-metadata',
          'hybrid-triangle-copy-not-direct-bih', 'portal-clears-triangle-copy', 'disabled-read-clears-copy',
          'solid-return-clears-copy', 'nohit-return-clears-copy')
WIDTHS = dict(CHECK=3, SELFTEST=2, BEGIN=2, SOURCE=1, CONTACT=18, END=3)


def source_digest():
    names = ('offramp_tricopy_types.inc', 'offramp_tricopy_native.inc',
             'offramp_tricopy_selftest.inc', 'offramp_tricopy_smoke.py')
    return hashlib.sha256(b''.join((ROOT/'tools'/n).read_bytes() for n in names)).hexdigest()


def parse(text):
    rows = []
    for line in text.splitlines():
        position = line.find('OFFRAMPTRICOPY_')
        if position < 0:
            continue
        words = line[position:].split()
        tag = words[0].removeprefix('OFFRAMPTRICOPY_')
        require(tag in WIDTHS and len(words)-1 == WIDTHS[tag], 'unknown/malformed triangle-copy row')
        rows.append((tag, words[1:]))
    return rows


def decode(text, contacts, origins):
    rows = parse(text)
    header = [('CHECK', [str(i), name, '1']) for i, name in enumerate(CHECKS, 1)]
    header += [('SELFTEST', [str(len(CHECKS)), '0']), ('BEGIN', ['1', '3']), ('SOURCE', [source_digest()])]
    require(rows[:len(header)] == header, 'missing/failed/reordered triangle-copy setup/source')
    require(len(contacts) == len(origins) and len(rows) == len(header)+len(contacts)+1,
            'missing/extra triangle-copy accepted row')
    bound = []
    for (tag, words), contact, origin in zip(rows[len(header):-1], contacts, origins):
        require(tag == 'CONTACT', 'reordered triangle-copy accepted row')
        values = numbers(words)
        ordinal, tick, status, plane_tag, bevels = integers(words[:5])
        indexes = integers(words[6:9])
        require((ordinal, tick) == tuple(contact[:2]) == tuple(origin[:2]), 'triangle copy not bound to returned contact')
        require(status in (0, 1, 2) and bevels in (0, 1) and
                all(0 <= i <= 0xffffffff for i in indexes), 'invalid triangle-copy status/flags/indexes')
        if status == 1:
            require(origin[3] == 2 and len(set(indexes)) == 3 and values[5] == 4 and
                    plane_tag in (*range(14), *range(100, 106)),
                    'nontriangle/invalid native tag/slab promoted copied geometry')
            vertices = [values[i:i+3] for i in range(9, 18, 3)]
            # Reject a serialized partial/degenerate copy independently of C.
            prism(vertices, values[5])
        else:
            require(values[3:] == [0]*15, 'empty/invalid triangle copy promoted stale/partial geometry')
            require(status == 0 or origin[3] == 2, 'nontriangle invalid snapshot status')
            vertices = [[0]*3 for _ in range(3)]
        if origin[3] != 2:
            require(status == 0, 'brush/unknown origin promoted triangle copy')
        bound.append(dict(ordinal=ordinal, tick=tick, status=status, native_plane_tag=plane_tag,
                          native_bevels_applied=bevels, back_slab=values[5], indexes=indexes, vertices=vertices))
    counts = Counter(r['status'] for r in bound)
    require(rows[-1] == ('END', [str(len(bound)), str(counts[1]), str(counts[2])]),
            'missing/duplicate/incorrect triangle-copy footer')
    return bound


def contact_sweep(copy, contact):
    """Independent geometry for this clear standing-world actor ONLY."""
    require(copy['status'] == 1 and copy['native_plane_tag'] == 0 and copy['native_bevels_applied'] == 1 and
            contact[15:21] == [-16, -16, 0, 16, 16, 62] and contact[21:] == [0, 0, 0] and
            0 <= contact[4] < 1, 'unsupported copied triangle sweep/hull/route')
    geometry = sweep(copy['vertices'], contact[9:12], contact[12:15], contact[15:18], contact[18:21], copy['back_slab'])
    require(geometry['intersects'] and geometry['entry_planes'], 'copied triangle SAT sweep misses native accepted contact')
    matches = [p for p in geometry['entry_planes'] if close(p[:3], contact[6:9], 1e-5) and
               abs(p[3]-contact[5]) <= SPATIAL_TOLERANCE]
    require(matches, 'copied triangle SAT entry plane differs from accepted normal/distance')
    speed = abs(dot(sub(contact[12:15], contact[9:12]), matches[0][:3]))
    require(speed > 1e-9, 'copied triangle SAT closing motion did not ACT')
    expected = max(0, geometry['enter']-NATIVE_BIAS/speed)
    require(abs(expected-contact[4])*speed <= SPATIAL_TOLERANCE,
            'copied triangle SAT accepted fraction/bias differs')
    return dict(independent_copied_triangle_sweep='PASS', expected_biased_fraction=expected,
                geometry_basis='COPIED_WINNING_NATIVE_TRIANGLE', **geometry)


def grade(text, motion):
    blocks = re.findall(r'OFFRAMPMOTION_CASE [0-9]+ .*?(?=OFFRAMPMOTION_CASE_END [0-9]+ [0-9]+)', text, flags=re.S)
    require(len(blocks) == len(LABELS) and len(parse(text)) == sum(len(parse(b)) for b in blocks),
            'triangle-copy rows outside native case envelopes')
    cases, total, triangles = [], 0, 0
    for index, (block, case) in enumerate(zip(blocks, motion['cases'])):
        buffer, _ = buffer_parse(block)
        raw, _ = origin_parse(block)
        origins = [integers(w[:9])+[w[9]] for w in raw['CONTACT']]
        copies = decode(block, buffer['CONTACT'], origins)
        require(len(copies) == len(case['accepted']), 'copied geometry/accepted winner count differs')
        for copy, contact, origin, winner in zip(copies, buffer['CONTACT'], origins, case['accepted']):
            total += 1
            if index != 14:
                require(copy['status'] == 0, 'nontriangle motion actor promoted triangle geometry')
                continue
            require(origin[2:10] == [0, 2, 0, 0, 0, 1, 0, WORLD_MODEL] and
                    winner['geometry_status'] == 'world-triangle-unresolved' and
                    winner['instance'] == dict(instance_origin=[0]*3, instance_angles=[0]*3,
                                              raw_instance_scale=1, direct_bih_callback=1) and
                    copy['indexes'] == integers(case['triangle'][3:6]) and
                    close([x for v in copy['vertices'] for x in v], numbers(case['triangle'][6:]), 1e-4),
                    'copied triangle not bound to actual native leaf/index/wiring/instance')
            copy['accepted_sweep'] = contact_sweep(copy, contact)
            copy['model'], copy['leaf'], copy['rootleaf'], copy['depth'], copy['physent_index'] = origin[9], *origin[4:7], origin[8]
            triangles += 1
        require(index != 14 or (len(copies) == 14 and all(c['status'] == 1 for c in copies)),
                'copied triangle actor did not ACT')
        if index == 14:
            signatures = {(tuple(c['indexes']), tuple(x for v in c['vertices'] for x in v), c['back_slab']) for c in copies}
            require(len(signatures) == 1, 'one static native triangle leaf changed copied geometry')
        cases.append(dict(label=case['label'], contacts=copies))
    require(triangles == 14 and not cases[15]['contacts'], 'native triangle/removal copy control did not ACT')
    return dict(copied_winning_triangle_binding='PASS', bounded_copied_triangle_sweeps='PASS',
                native_setup_checks_per_case=len(CHECKS), accepted_contact_rows=total, copied_triangle_contacts=triangles,
                source=source_digest(), cases=cases, general_triangle_support='ABSTAIN',
                general_native_triangle_semantics='NOT_TESTED', physical_exit_acceptance='NOT_TESTED')


def compare(*texts):
    require(len(texts) == 5 and not any(parse(t) for t in texts[:3]), 'fixture-only/OFF triangle copy not quiet')
    motion = motion_compare(*texts)
    result = grade(texts[3], motion)
    require(result == grade(texts[4], motion), 'repeated copied triangle geometry differs')
    result.update(original_motion_body_oracle_sha256=motion['body_oracle_sha256'],
                  original_motion_source=motion['source'], five_arm_motion_parity='PASS', repeat_triangle_copy='PASS')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'triangle-copy report needs NEW path')
    arms = json.loads(a.arms.read_text())
    names = ('nooracle', 'control', 'off', 'on', 'repeat')
    require(set(arms) == set(names) and all(r['exit_code'] == 0 for r in arms.values()), 'missing/failed native triangle-copy arms')
    require(arms['control']['server_sha256'] == arms['nooracle']['server_sha256'] != arms['on']['server_sha256'] and
            len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) == 1 and
            len({r['fixture_sha256'] for r in arms.values()}) == len({r['manifest_sha256'] for r in arms.values()}) == 1,
            'native triangle-copy control/subject provenance differs')
    for row in arms.values():
        for relative, key in (('fteqwsv64.exe', 'server_sha256'), ('default.fmf', 'manifest_sha256'),
                              ('ftesurf/cfg/test/motion.cfg', 'cfg_sha256')):
            require(hashlib.sha256((Path(row['rig'])/relative).read_bytes()).hexdigest() == row[key],
                    'retained native triangle-copy binary/manifest/cfg differs')
    texts = [Path(arms[n]['log']).read_text(errors='replace') for n in names]
    result = compare(*texts)
    require(result['original_motion_source'][0] == arms['on']['fixture_sha256'] ==
            hashlib.sha256((ROOT/'tools/offramp_motion_native.inc').read_bytes()).hexdigest(),
            'native triangle-copy motion fixture differs')
    result['arms_file_sha256'] = hashlib.sha256(a.arms.read_bytes()).hexdigest()
    result['log_sha256'] = {n: hashlib.sha256(Path(arms[n]['log']).read_bytes()).hexdigest() for n in names}
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print('Return-bound winning triangle copies:14; native setup23/case; bounded copied sweep SAT PASS')
    print('Original20 actor/winner/category parity PASS; general triangle support ABSTAIN; physical exit NOT_TESTED')


if __name__ == '__main__':
    main()
