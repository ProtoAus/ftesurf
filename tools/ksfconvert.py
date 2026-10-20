#!/usr/bin/env python3
"""Convert a local KSF CSS/66t binary replay to an imported FTESurf .rec.

Map, course, style and owner are external bindings: the binary does not name
any of them. Use the exact public viewer/board row, never the header kind or
filename numbers. No download, native evidence, verification or board filing.
See tools/ksfplayback.md for conversion and in-game playback commands.
"""
import argparse
import hashlib
import io
import math
from pathlib import Path
import re
import struct

import ksfreplay_info as K

STYLES = ('FW', 'SW', 'HSW', 'BW')
# Non-direction Source buttons -> FSI_* keys. FSI directions are resolved moves,
# not raw buttons (native contract). Keep the raw mask separately, without loss.
KEYS = ((2, 16), (4, 32), (128, 64), (256, 128), (1, 256))


def classify(target):
    """Only the documented 5939xxx trigger namespace; other names are unknown."""
    if not re.fullmatch(r'5939\d{3}', target):
        return None
    n = int(target) - 5939000
    if 101 <= n <= 199:
        return ('bonus_start' if n % 2 else 'bonus_end', (n - 99) // 2)
    if 1 <= n <= 99:
        return ('main', n)
    return ('other', n)


def interval(bookmarks, bonus, lead_ok=False, stage=0, last=False):
    """One unambiguous start-exit and finish-entry, never full-file fallbacks.

    KSF bonus start/end share zone30+N. Named triggers distinguish them; the
    unclassified-target form requires an entry at/before the one exit and exactly
    one later entry (the plugin's second-entry rule).

    Patch 757: lead_ok accepts a recording that begins inside the start zone (no
    entry before its one exit: 10 of 17 refusals, each a 334-tick lead-in), for a
    caller whose official time then binds the interval.

    Patch 891: a stage file is its own recording (KSF serves one per stage). Stage N
    exits zone N and finishes entering zone N+1; the last stage finishes in the end
    zone, which none of surf_kepler's 13 stage-9 files bookmarks, so a stop of None
    asks the caller to place it by the official time.
    """
    if any(a['tick'] > b['tick'] for a, b in zip(bookmarks, bookmarks[1:])):
        raise ValueError('bookmarks are out of order')
    if stage:
        starts = [m['tick'] for m in bookmarks if m['zone'] == stage and m['touch'] == 3]
        if len(starts) != 1:
            raise ValueError('stage needs exactly one start-zone exit')
        start = starts[0]
        if not lead_ok and not any(m['zone'] == stage and m['touch'] == 2 and m['tick'] <= start
                                   for m in bookmarks):
            raise ValueError('stage has no initial start-zone entry')
        stops = [m['tick'] for m in bookmarks if m['tick'] > start and m['touch'] == 2
                 and m['zone'] == (99 if last else stage + 1)]
        if len(stops) > 1 or not (stops or last):
            raise ValueError('stage needs exactly one finish-zone entry')
        return start, (stops[0] if stops else None)
    zone = 30 + bonus if bonus else 1
    marks = [m for m in bookmarks if m['zone'] == zone]
    starts = []
    for m in marks:
        c = classify(m['target'])
        if m['touch'] == 3:
            if bonus and c is not None and c != ('bonus_start', bonus):
                continue
            starts.append(m['tick'])
    if len(starts) != 1:
        raise ValueError('course needs exactly one start-zone exit')
    start = starts[0]
    if not lead_ok and not any(m['touch'] == 2 and m['tick'] <= start for m in marks):
        raise ValueError('course has no initial start-zone entry')
    stops = []
    for m in bookmarks:
        if m['tick'] <= start or m['touch'] != 2:
            continue
        if m['zone'] != (zone if bonus else 99):
            continue
        c = classify(m['target'])
        if bonus and c is not None and c != ('bonus_end', bonus):
            continue
        stops.append(m['tick'])
    if len(stops) != 1:
        raise ValueError('course needs exactly one finish-zone entry')
    return start, stops[0]


def clean_owner(owner):
    # Owner runs to EOL; quotes/comment delimiters would also alter QC tokens.
    return ''.join(' ' if ord(c) < 32 or ord(c) == 127 or c in '\"\\' else c
                   for c in owner).replace('//', ' ').strip()[:64] or '?'


def convert(data, mapname, bonus=0, style='FW', owner='?', seconds=None, stage=0, last=False):
    if not re.fullmatch(r'[a-z0-9_]{1,64}', mapname):
        raise ValueError('map must be a plain lowercase map name')
    if type(bonus) is not int or not 0 <= bonus <= 69:
        raise ValueError('bonus must be 0 (main) or 1..69')
    if type(stage) is not int or not 0 <= stage <= 30 or (stage and bonus):
        raise ValueError('stage must be 0 or 1..30, and only on the main track')
    if type(last) is not bool or (last and not stage):
        raise ValueError('last is a stage flag')
    if style not in STYLES:
        raise ValueError('style must be FW, SW, HSW or BW')
    info = K.inspect(data)
    start, stop = interval(info['bookmarks'], bonus, lead_ok=seconds is not None,
                           stage=stage, last=last)
    # CSS 66t, also the current ksfimport.py TICK. No CSS100/CSGO rate guessed.
    dt = 0.015
    timed = stop is None
    if timed:
        # The last stage's finish is unbookmarked: the official time places it. A file
        # that ends at the finish ends on the tick before (the timer counts sub-tick).
        if seconds is None or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('an unbookmarked stage finish needs the official time')
        stop = start + round(seconds / dt)
        if stop > info['frames'] - 1:
            if stop - (info['frames'] - 1) > 2:
                raise ValueError('official time runs past the recording')
            stop = info['frames'] - 1
    if stop + 1 > 200000:
        raise ValueError('playback exceeds the 200000-frame conversion bound')
    duration = (stop - start) * dt
    off = 16
    if info['version'] == 3:
        off = 24 + info['extension_cells'] * 4
    off += len(info['bookmarks']) * 524
    stride = info['frame_cells'] * 4
    repeats = 0
    if seconds is not None:
        # Patch 757: KSF's time is its timer's, not this file's frame count. Measured
        # on 29 of its demos: 22 within 0.87 tick; five short runs 1.005 to 2.03 with
        # no frame repeated; surf_monolith main HSW 24.15 over 24,692 frames, 23 of them
        # repeating the frame before while the body moves, and BW 3.99 over 57,053 (a
        # dropped frame cannot be counted on a route that teleports). So 2.5 ticks, plus
        # each repeated frame, plus one a 10,000 frames. A wrong run is seconds off.
        last = None
        for i in range(start, stop + 1):
            rec = K.PREFIX.unpack_from(data, off + i * stride)
            if last == rec[1:4] and math.hypot(*rec[7:10]) >= 50:
                repeats += 1
            last = rec[1:4]
        tol = dt * (2.5 + repeats + (stop - start) / 10000)
        if not math.isfinite(seconds) or seconds <= 0 or abs(seconds - duration) > tol:
            raise ValueError('public time %.6f differs from bookmark interval %.3f by over %.3f s'
                             % (seconds, duration, tol))
    # v3 common prefix + ground bit, and the documented full 18-cell layout.
    ground = info['version'] == 3 and info['frame_cells'] >= 11
    moves = info['version'] == 3 and info['frame_cells'] == 18
    # Cell10 bit1 is conflicting in the public viewer (ducked vs teleport).
    # Never turn it into native DUCKED. Neither version records a ramp plane.
    digest = hashlib.sha256(data).hexdigest()
    out = io.StringIO()
    out.write('FTESURF-REC 5\nmap %s\ntrack %d\nstartseg %d\nleg %d\n'
              % (mapname, bonus, max(stage - 1, 0), stage))
    out.write('tickrate 0.015\nmovetickrate 0.015\nclock sampled\nowner %s\n' % clean_owner(owner))
    out.write('runid ksf-%s\nforeign ksf %s\nmapbuild unknown\n' % (digest[:20], digest))
    out.write('ksfdemo %d %d %d %s\nksfground %d\nksfmoves %d\n' %
              (info['version'], start, stop, style, ground, moves))
    if timed:
        out.write('ksfstop timed\n')    # additive: the finish frame is the official time's
    out.write('moves %s\n' % ('recorded' if moves else 'buttons 1'))
    if seconds is not None:
        out.write('ksftime %.9f\n' % seconds)
    # Shared viewer capability, only when ground + real per-tick velocity exist.
    if ground:
        out.write('demodata 1\n')
    out.write('flags 0\nbegin\n')
    for i in range(stop + 1):
        p = off + i * stride
        b, x, y, z, pitch, yaw, _roll, vx, vy, vz = K.PREFIX.unpack_from(data, p)
        # Keys are INPUT; ground is STATE. Jump/attack bits retain input meaning.
        fl = (4 if b & 2 else 0) | (8 if b & 1 else 0)
        if ground and struct.unpack_from('<i', data, p + 40)[0] & 1:
            fl |= 1
        keys = sum(dst for src, dst in KEYS if b & src)
        # v2 unit direction proxy, NOT a measured analog magnitude. Opposing
        # keys cancel rather than guessing Source's SOCD order. Raw mask below.
        fwd = float(bool(b & 8)) - float(bool(b & 16))
        side = float(bool(b & 1024)) - float(bool(b & 512))
        up = 0.0
        if moves:
            fwd, side = struct.unpack_from('<2f', data, p + 52)
            up, = struct.unpack_from('<f', data, p + 68)
            if not all(math.isfinite(v) and abs(v) < 1e7 for v in (fwd, side, up)):
                raise ValueError('invalid analog move')
        # FSI directions follow the serialized fixed-point commands. Sub-micro
        # analog values round to zero, never to a phantom nonzero direction.
        fwd, side, up = (float('%.6f' % v) for v in (fwd, side, up))
        keys |= (1 if fwd > 0 else 2 if fwd < 0 else 0)
        keys |= (8 if side > 0 else 4 if side < 0 else 0)
        out.write('ksfbuttons %d %d\n' % (i, b))
        # Fixed decimals: the viewer's sample discriminator does not accept exponents.
        out.write('%.4f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %d %d %.6f %.6f %.6f 0 0 0\n' %
                  ((i - start) * dt, x, y, z, vx, vy, vz, pitch, yaw, fl, keys, fwd, side, up))
    out.write('end %d %d %d 0\n' % (stop - start, stop + 1, start))
    return out.getvalue(), dict(info, start=start, stop=stop, seconds=duration,
                                official_seconds=seconds, repeats=repeats, sha256=digest,
                                map=mapname, bonus=bonus, stage=stage, timed_stop=timed, style=style,
                                ground_recorded=ground, moves_recorded=moves,
                                duck_state='unknown', map_build='unknown')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('replay', type=Path, help='local binary from the CSS/66t viewer')
    p.add_argument('--map', required=True)
    p.add_argument('--bonus', type=int, default=0, help='0 = main, N = bonus N (not a stage)')
    p.add_argument('--stage', type=int, default=0, help='N = stage N of the main track')
    p.add_argument('--last-stage', action='store_true', help='the map has no stage after this one')
    p.add_argument('--style', required=True, choices=STYLES, help='external board binding, not header kind')
    p.add_argument('--owner', default='?', help='display alias, not proof of player identity')
    p.add_argument('--seconds', type=float,
                   help='optional official row time, within 2.5 CSS ticks plus repeated frames')
    p.add_argument('--out', required=True, type=Path, help='NEW .rec; existing files are never overwritten')
    a = p.parse_args()
    try:
        with a.replay.open('rb') as f:
            data = f.read(K.MAX_BYTES + 1)
        text, info = convert(data, a.map, a.bonus, a.style, a.owner, a.seconds,
                             stage=a.stage, last=a.last_stage)
        # Parse everything before creating a file. Do not mutate an existing recording.
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open('x', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('%s: KSF import, %d frames, %.3fs bookmark clock; map build/duck state unknown' %
              (a.out, info['stop'] + 1, info['seconds']))
    except (OSError, ValueError, struct.error) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
