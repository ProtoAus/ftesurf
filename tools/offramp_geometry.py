#!/usr/bin/env python3
"""Offline static VBSP brush candidates for buffered airborne contact losses.

A trace plane is NOT a brush ID. Return all matching nearby convex brush
candidates, never manufacture a winning brush or label a physical ramp exit.
Not applicable to triangle/displacement hits, moving entities, recovery planes,
portals or discontinuous/native rewind histories. No new runtime probes.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from census import bsplib
from offramp_buffer import compare, grade, require

# Deliberately above the Source 1/32 clipping pullback. This is an offline
# candidate envelope, NOT a movement/contact/debounce or exit threshold.
ENVELOPE = .0625


def read_lump(f, hdr, index):
    offset, length, _, _ = hdr[index]
    f.seek(offset)
    raw = f.read(length)
    require(len(raw) == length, 'truncated geometry lump')
    if raw[:4] != b'LZMA':
        return raw
    require(len(raw) >= 17, 'truncated compressed lump header')
    actual, compressed = struct.unpack_from('<II', raw, 4)
    require(compressed <= len(raw)-17, 'compressed geometry overruns lump')
    decoded = bsplib._delump(raw)
    require(len(decoded) >= actual, 'short/undecodable compressed geometry')
    # The plugin supplies actual as LzmaDecode's output cap and checks destLen.
    # Python's raw decoder can produce padding beyond it; it is NOT a leaf.
    return decoded[:actual]


def load_brushes(path):
    size = path.stat().st_size
    require(size >= bsplib.HDRSZ, 'truncated VBSP header')
    with path.open('rb') as f:
        ident, version = struct.unpack('<4si', f.read(8))
        require(ident == b'VBSP' and 17 <= version <= 21, 'not a supported VBSP')
        hdr = bsplib.lumps(f)
        require(hdr is not None and all(0 <= o <= size and 0 <= n <= size-o
                                       for o, n, _, _ in (hdr[i] for i in (1, 5, 10, 14, 17, 18, 19))),
                'invalid geometry lump range')
        planes_data = read_lump(f, hdr, 1)
        brushes_data = read_lump(f, hdr, 18)
        sides_data = read_lump(f, hdr, 19)
        nodes_data, leaves_data = (read_lump(f, hdr, i) for i in (5, 10))
        models_data, leafbrushes_data = (read_lump(f, hdr, i) for i in (14, 17))
    # Restrict candidates to model 0's referenced brushes, not all global brush
    # records (which also contain inline/movable model geometry).
    require(hdr[10][2] in (0, 1), 'unsupported leaf lump version')
    leafsize = 56 if version == 19 else 32
    require(models_data and len(models_data) % 48 == 0 and len(nodes_data) % 32 == 0 and
            len(leaves_data) % leafsize == 0 and len(leafbrushes_data) % 2 == 0,
            'malformed world BSP tree')
    refs = [x[0] for x in struct.iter_unpack('<H', leafbrushes_data)]
    pending = [struct.unpack_from('<i', models_data, 36)[0]]
    visited, world = set(), set()
    while pending:
        index = pending.pop()
        if index in visited:
            continue
        visited.add(index)
        if index >= 0:
            require(index < len(nodes_data)//32, 'invalid world node index')
            pending.extend(struct.unpack_from('<2i', nodes_data, index*32+4))
        else:
            leaf = -1-index
            require(leaf < len(leaves_data)//leafsize, 'invalid world leaf index')
            first, count = struct.unpack_from('<2H', leaves_data, leaf*leafsize+24)
            require(first <= len(refs) and count <= len(refs)-first, 'invalid world leaf brush range')
            world.update(refs[first:first+count])
    require(world and all(b < len(brushes_data)//12 for b in world), 'no valid world brushes')
    require(planes_data and brushes_data and sides_data, 'empty/undecodable VBSP brush geometry')
    require(len(planes_data) % 20 == len(brushes_data) % 12 == len(sides_data) % 8 == 0,
            'malformed VBSP geometry lump')
    planes = [p[:4] for p in struct.iter_unpack('<4fi', planes_data)]
    require(all(all(math.isfinite(x) for x in p) and abs(math.sqrt(sum(x*x for x in p[:3]))-1) < .002
                for p in planes), 'invalid BSP plane')
    sides = list(struct.iter_unpack('<Hhhh', sides_data))
    require(all(0 <= s[0] < len(planes) for s in sides), 'invalid side plane index')
    brushes = []
    by_plane = {}
    for i, (first, count, contents) in enumerate(struct.iter_unpack('<iii', brushes_data)):
        require(0 <= first <= len(sides) and 0 <= count <= len(sides)-first, 'invalid brush side range')
        ids = [s[0] for s in sides[first:first+count]]
        brushes.append({'index': i, 'contents': contents, 'planes': ids})
        if i in world:
            for pid in set(ids):
                by_plane.setdefault(pid, []).append(i)
    return planes, brushes, by_plane


def gap(plane, origin, mins, maxs):
    # Point hull origin in a half-space expanded by the support of its AABB.
    # Positive means outside that expanded half-space; zero is support contact.
    n, dist = plane[:3], plane[3]
    return sum(n[i] * (origin[i] + (mins[i] if n[i] >= 0 else maxs[i])) for i in range(3)) - dist


def candidates(loss, planes, brushes, by_plane):
    trace = loss['previous_trace']
    if trace['physent_index'] != 0 or trace['recovery_plane']:
        return {'status': 'unsupported-entity-or-recovery', 'candidates': []}
    matches = [i for i, p in enumerate(planes) if abs(p[3]-trace['plane_dist']) <= .02 and
               max(abs(a-b) for a, b in zip(p[:3], trace['normal'])) <= .0001]
    result = []
    mins, maxs = trace['hull_mins'], trace['hull_maxs']
    for bid in sorted({bid for pid in matches for bid in by_plane.get(pid, [])}):
        brush = brushes[bid]
        ids = brush['planes']
        before = [(pid, gap(planes[pid], loss['previous_position'], mins, maxs)) for pid in ids]
        # Collision contents must overlap the player's solid/playerclip mask.
        # VBSP CONTENTS_SOLID=1, CONTENTS_PLAYERCLIP=0x10000. Other masks are
        # intentionally unsupported rather than described as world ramp hits.
        if not brush['contents'] & (1 | 0x10000) or not before or max(g for _, g in before) > ENVELOPE:
            continue
        after = [(pid, gap(planes[pid], loss['loss_position'], mins, maxs)) for pid in ids]
        faces = sorted(set(ids) & set(matches))
        edges = [(pid, g) for pid, g in after if pid not in faces]
        result.append({'brush_candidate': bid, 'matching_plane_indices': faces,
                       'contents': brush['contents'],
                       'previous_max_halfspace_gap': max(g for _, g in before),
                       'loss_max_halfspace_gap': max(g for _, g in after),
                       'loss_max_nonface_gap': max((g for _, g in edges), default=None),
                       'loss_outside_nonface_planes': [pid for pid, g in edges if g > ENVELOPE],
                       'face_support_gaps': [{'plane_index': pid,
                                              'previous': gap(planes[pid], loss['previous_position'], mins, maxs),
                                              'loss': gap(planes[pid], loss['loss_position'], mins, maxs)} for pid in faces]})
    return {'status': 'static-brush-candidates' if result else 'no-supported-brush-candidate',
            'plane_matches': len(matches), 'candidates': result}


def analyse(capture, bsp, expected_sha):
    actual = hashlib.sha256(bsp.read_bytes()).hexdigest()
    require(actual == expected_sha, 'offline BSP differs from captured runtime bytes')
    result = grade(capture)
    planes, brushes, by_plane = load_brushes(bsp)
    result['geometry'] = {'map_sha256': actual, 'candidate_envelope': ENVELOPE,
                          'basis': 'static VBSP brush plane/AABB halfspaces, not authenticated winning brushes',
                          'planes': len(planes), 'brushes': len(brushes)}
    for loss in result['losses']:
        loss['geometry_candidates'] = candidates(loss, planes, brushes, by_plane)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path, required=True)
    ap.add_argument('--map', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    arms = json.loads(a.arms.read_text())
    require(set(arms) == {'clean', 'off', 'on', 'repeat'}, 'missing runtime control provenance')
    sha = arms['on']['map_sha256']
    require(all(x['map_sha256'] == sha for x in arms.values()), 'control map identity differs')
    texts = {name: Path(arm['log']).read_text(errors='replace') for name, arm in arms.items()}
    compare(*(texts[name] for name in ('clean', 'off', 'on', 'repeat')))
    result = analyse(texts['on'], a.map, sha)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    counts = {}
    for loss in result['losses']:
        status = loss['geometry_candidates']['status']
        counts[status] = counts.get(status, 0) + 1
    print('Static geometry statuses:', counts)
    print('Winning brush identity and physical-exit acceptance: NOT_TESTED')


if __name__ == '__main__':
    main()
