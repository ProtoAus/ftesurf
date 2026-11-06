"""Cosmetic bake inputs, not a native verifier or a new recording format.

Read existing Momentum/FTESURF-REC samples without changing any original. Source
hashes deduplicate identical recording files. Scope-preserving converted clips
are retained even when they share an original demo hash. Native contact flags
remain recorded; foreign contacts are inferred and matched against actual BSP
facets by rampwear.py. Unreadable/truncated/mismatched inputs are counted, never
silently substituted for a different map. No player identity enters bake reports.
"""
from dataclasses import dataclass
import hashlib
import math
import json
import struct
from pathlib import Path
import re

import heldmeta
import momreplay
import rampinfer
import ksfreplay_info
from ksfconvert import infer_ducked


@dataclass
class Tick:
    tick: int
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    flags: int
    noint: int = 0


def capture(path, mapname):
    """(immutable bytes, source identity, kind). Dedup BEFORE expensive decoding."""
    data = Path(path).read_bytes()
    if data.startswith(b'MMTV'):
        head = momreplay.read_header(data)
        if head['map'].lower() != mapname:
            raise ValueError('map binding differs')
        return data, ('momentum', hashlib.sha1(data).hexdigest()), 'momentum'
    if not data.startswith(b'FTESURF-REC '):
        binding = json.loads(Path(path).with_suffix('.binding.json').read_text(encoding='utf-8'))
        digest = hashlib.sha256(data).hexdigest()
        if binding.get('map') != mapname or binding.get('game') != 'css66' or binding.get('sha256') != digest:
            raise ValueError('raw KSF advertised map/game/hash binding differs')
        ksfreplay_info.inspect(data)
        return data, ('ksf', digest), 'ksf_raw'
    magic = data.splitlines()[0].split()
    version = int(magic[1])
    if version not in range(2, 16):
        raise ValueError('unsupported recording version')
    if heldmeta.is_native_recording(data, version):
        data = heldmeta.parse_recording(data).ordinary
    text = data.decode('utf-8', 'strict').replace('\r\n', '\n').replace('\r', '\n')
    header, sep, _ = text.partition('\nbegin\n')
    if not sep:
        raise ValueError('missing begin')
    head = dict(line.split(None, 1) for line in header.splitlines()[1:] if len(line.split(None, 1)) == 2)
    if head.get('map', '').lower() != mapname:
        raise ValueError('map binding differs')
    foreign = head.get('foreign', '').split()
    if foreign:
        if len(foreign) < 2 or foreign[0] not in ('momentum', 'ksf') or not re.fullmatch(r'[0-9a-f]{1,64}', foreign[1]):
            raise ValueError('invalid foreign source binding')
        # Older Momentum imports omitted leading zeroes in provenance hashes.
        # This cosmetic reader does not certify or repair that provenance: its
        # identity is the actual unchanged recording bytes, not the legacy token.
        # A stage/bonus conversion may cover only PART of the same original.
        # Never drop later clips just because they share a foreign source hash.
        identity, kind = (foreign[0], hashlib.sha256(data).hexdigest()), foreign[0]
    else:
        identity, kind = ('native', hashlib.sha256(data).hexdigest()), 'native'
    return data, identity, kind


def prefer_originals(paths, mapname):
    """Drop clipped KSF conversions only when their FULL original is readable/bound.

    Preserve distinct clips when no complete original exists. Source tokens alone
    must not merge their disjoint poses, and an invalid raw input cannot hide a
    usable conversion. No recording or provenance is rewritten.
    """
    full, headers = set(), {}
    for path in paths:
        p = Path(path)
        try:
            with p.open('rb') as f:
                header = f.read(4096)
        except OSError:
            headers[path] = b''
            continue  # ordinary bake loop retains its unreadable-input accounting
        headers[path] = header
        if not header.startswith(b'FTESURF-REC ') and p.with_suffix('.binding.json').is_file():
            try:
                _, identity, _ = capture(p, mapname)
            except (OSError, ValueError, KeyError, struct.error):
                continue
            full.add(identity)
    kept = []
    for path in paths:
        header = headers[path]
        if header.startswith(b'FTESURF-REC '):
            foreign = re.search(rb'(?m)^foreign (momentum|ksf) ([0-9a-f]{1,64})(?:\s|$)', header)
            if foreign:
                kind, digest = (x.decode('ascii') for x in foreign.groups())
                if kind == 'ksf' and (kind, digest) in full:
                    continue
        kept.append(path)
    return kept


def decode(path, data, kind):
    if data.startswith(b'MMTV'):
        # The decoder takes a path; don't let a changed source get a frozen identity.
        if Path(path).read_bytes() != data:
            raise ValueError('replay changed during capture')
        r = momreplay.parse(path)
        return dict(r, kind=kind, recorded_contacts=False)
    if kind == 'ksf_raw':
        info = ksfreplay_info.inspect(data)
        off = (24 + info['extension_cells'] * 4) if info['version'] == 3 else 16
        off += len(info['bookmarks']) * 524
        stride = info['frame_cells'] * 4
        ground = info['version'] == 3 and info['frame_cells'] >= 11
        frames = []
        for i in range(info['frames']):
            b, x, y, z, _p, _y, _r, vx, vy, vz = ksfreplay_info.PREFIX.unpack_from(data, off + i * stride)
            g = (struct.unpack_from('<i', data, off + i * stride + 40)[0] & 1) if ground else None
            frames.append((b, x, y, z, vx, vy, vz, g))
        ducked, _ = infer_ducked(frames, 0.015)
        ticks = [Tick(i, *frame[1:7], (1 if frame[7] else 0) | (2 if ducked[i] else 0))
                 for i, frame in enumerate(frames)]
        # Use the WHOLE advertised CSS66 replay, not only one timer interval.
        # This is cosmetic pose inference, never a native record or verdict.
        return dict(kind='ksf_raw', recorded_contacts=False, ticks=ticks, tick_interval=0.015)
    text = data.decode('utf-8', 'strict').replace('\r\n', '\n').replace('\r', '\n')
    header, _, body = text.partition('\nbegin\n')
    head = dict(line.split(None, 1) for line in header.splitlines()[1:] if len(line.split(None, 1)) == 2)
    version = int(header.splitlines()[0].split()[1])
    dt = rampinfer.tick_of(head)
    if not math.isfinite(dt) or not 0 < dt <= 1:
        raise ValueError('missing/invalid sample clock')
    ticks, epoch, ended, lasttime = [], 0, False, None
    for line in body.splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == 'end':
            ended = True
            break
        if f[0] in rampinfer.REWIND or f[0] in ('warp', 'portal', 'resume', 'session'):
            epoch += 1
        if not (f[0][0].isdigit() or f[0][0] == '-'):
            continue
        if len(f) < 10:
            raise ValueError('short sample')
        values = [float(v) for v in f[:10]]
        if not all(math.isfinite(v) and abs(v) <= 1e9 for v in values):
            raise ValueError('nonfinite/out-of-bounds sample')
        seconds = values[0]
        if lasttime is not None and seconds <= lasttime:
            epoch += 1
        lasttime = seconds
        ticks.append(Tick(round(seconds / dt), *values[1:7], int(values[9]), epoch))
    if not ended:
        raise ValueError('unfinished/truncated recording')
    # Before sampled clocks, repeated frame samples are not independent mover ticks.
    if kind == 'native' and version < 5:
        unique = []
        for t in ticks:
            if unique and (t.x, t.y, t.z, t.vx, t.vy, t.vz, t.noint) == (unique[-1].x, unique[-1].y, unique[-1].z, unique[-1].vx, unique[-1].vy, unique[-1].vz, unique[-1].noint):
                continue
            unique.append(t)
        ticks = unique
    return {'ticks': ticks, 'tick_interval': dt, 'kind': kind,
            'recorded_contacts': kind == 'native' and version >= 4}
