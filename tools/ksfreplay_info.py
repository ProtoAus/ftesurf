#!/usr/bin/env python3
"""Inspect KSF's public binary replay (NOT FTESurf's text .rec or a Source .dem).

Format measured against ksf.surf/gokz/js/replayviewer.js, 2026-10-14. Viewer
links are HTML; raw bytes live at /api/replays/<filename>?game=66t (CSS).
No download, database write or certification occurs here. Header ticks and
file frames can include lead-in/out. Bookmarks are reported, not guessed into
a timer interval, map identity, track, style or native verification verdict.
"""
import argparse
import json
import math
from pathlib import Path
import struct

MAX_BYTES = 64 << 20
MAX_FRAMES = 2000000
MAX_BOOKMARKS = 4096
PREFIX = struct.Struct('<i5fi3f')


def inspect(data):
    if not 16 <= len(data) <= MAX_BYTES:
        raise ValueError('replay length out of bounds')
    version, kind, ticks, marks = struct.unpack_from('<4i', data)
    if version not in (2, 3) or not 0 < ticks <= MAX_FRAMES or not 0 <= marks <= MAX_BOOKMARKS:
        raise ValueError('unsupported replay header')
    cells, ext, off = 10, 0, 16
    if version == 3:
        if len(data) < 24:
            raise ValueError('truncated v3 header')
        cells, ext = struct.unpack_from('<2i', data, 16)
        if not 10 <= cells <= 128 or not 0 <= ext <= 4096:
            raise ValueError('unsupported frame/extension size')
        off = 24 + ext * 4
    frameoff = off + marks * 524
    size = cells * 4
    if frameoff >= len(data) or (len(data) - frameoff) % size:
        raise ValueError('truncated bookmarks or frames')
    frames = (len(data) - frameoff) // size
    if not 0 < frames <= MAX_FRAMES:
        raise ValueError('frame count out of bounds')
    bookmarks = []
    for i in range(marks):
        p = off + i * 524
        tick, touch, zone = struct.unpack_from('<3i', data, p)
        if not 0 <= tick < frames or touch not in (1, 2, 3):
            raise ValueError('invalid bookmark')
        def text(a):
            return data[a:a + 256].split(b'\0', 1)[0].decode('utf-8', 'replace')
        bookmarks.append(dict(tick=tick, touch=touch, zone=zone,
                              target=text(p + 12), classname=text(p + 268)))
    lo, hi, maxspeed = [math.inf] * 3, [-math.inf] * 3, 0.0
    for i in range(frames):
        rec = PREFIX.unpack_from(data, frameoff + i * size)
        if not all(math.isfinite(v) and abs(v) < 1e7 for v in rec[1:6] + rec[7:10]):
            raise ValueError('invalid frame coordinate')
        for a in range(3):
            lo[a] = min(lo[a], rec[a + 1]); hi[a] = max(hi[a], rec[a + 1])
        maxspeed = max(maxspeed, math.hypot(*rec[7:10]))
    return dict(version=version, kind=kind, header_ticks=ticks, frames=frames,
                frame_cells=cells, extension_cells=ext, bookmarks=bookmarks,
                bounds=[lo, hi], max_speed=maxspeed,
                timed_interval='not inferred', native_verified=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('replay', type=Path)
    a = p.parse_args()
    try:
        with a.replay.open('rb') as f:
            data = f.read(MAX_BYTES + 1)
        print(json.dumps(inspect(data), indent=2))
    except (OSError, ValueError, struct.error) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
