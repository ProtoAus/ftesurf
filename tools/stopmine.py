#!/usr/bin/env python3
"""Find dead stops in FTESURF-REC recordings, so a rare movement bug can be caught after the
fact instead of live (Patch 813: Lex's ramp stops were all in the Pi's lobby recordings).

    python tools/stopmine.py <dir or .rec>... [--minspeed 300] [--ratio 0.35] [--all]

An event is two consecutive samples where horizontal speed drops below --ratio of at least
--minspeed with no record between them that moves the player (warp, portal, seed...), no
noclip/teleport input flag, and no jump in position. By default only full stops are kept:
|v| under 20 and not on ground, which is what TryPlayerMove's velocity clear leaves after
the second half of gravity ((0, 0, -6) at 66 Hz). --all keeps every collapse, walls included.

Sample columns: t ox oy oz vx vy vz pit yaw fl keys fwd side up nx ny nz, fl 1 onground,
2 ducked, 4 jump, 16 ramp contact (sv_timer.qc SV_RecFlags). Next steps for a hit: replay
the file with `pm_recsim` (or `pm_verify` on the Pi) under `pm_dispprobe 3`, and list the
brushes at the position with tools/bspnear.py.
"""
import argparse
import math
import os
import sys

MOVERS = {"warp", "portal", "seed", "ride", "spec", "pause", "session"}


def samples(path):
    recs, infl, began = [], 0, False
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            tok = ln.split()
            if not tok:
                continue
            if not began:
                began = tok[0] == "begin"
                continue
            c = tok[0][0]
            if c.isdigit() or (c == "-" and len(tok[0]) > 1 and tok[0][1].isdigit()):
                try:
                    v = [float(x) for x in tok[:17]]
                except ValueError:
                    continue
                if len(v) >= 10:
                    yield v, recs, infl
                recs, infl = [], 0
            elif tok[0] == "in":
                if len(tok) >= 12 and tok[11].isdigit():
                    infl |= int(tok[11])     # v9 `in` fl: 2 teleport_time, 4 not WALK
            else:
                recs.append(tok[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--minspeed", type=float, default=300)
    ap.add_argument("--ratio", type=float, default=0.35)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    files = []
    for r in a.roots:
        if os.path.isfile(r):
            files.append(r)
        for d, _, fs in os.walk(r):
            files += [os.path.join(d, x) for x in fs if x.endswith(".rec")]
    nev = nsamp = 0
    for p in sorted(set(files)):
        prev = None
        for v, recs, infl in samples(p):
            nsamp += 1
            if prev is not None:
                dt = v[0] - prev[0]
                s0 = math.sqrt(sum(x * x for x in prev[4:7]))
                s1 = math.sqrt(sum(x * x for x in v[4:7]))
                h0, h1 = math.hypot(prev[4], prev[5]), math.hypot(v[4], v[5])
                moved = math.sqrt(sum((v[i] - prev[i]) ** 2 for i in (1, 2, 3)))
                full = s1 <= 20 and not (int(v[9]) & 1)
                if (0 < dt <= 0.2 and h0 >= a.minspeed and h1 <= a.ratio * h0
                        and not MOVERS.intersection(recs) and not (infl & 6)
                        and moved <= (s0 + s1) * max(dt, 0.015) + 64 and (a.all or full)):
                    nev += 1
                    n = v[14:17] if len(v) >= 17 else [0, 0, 0]
                    print("%s t=%.4f speed %.1f->%.1f (vz %.1f->%.1f) fl %d->%d plane %.4f %.4f %.4f org %.2f %.2f %.2f"
                          % (p, v[0], s0, s1, prev[6], v[6], int(prev[9]), int(v[9]), n[0], n[1], n[2], v[1], v[2], v[3]))
            prev = v
    print("files %d samples %d events %d" % (len(set(files)), nsamp, nev), file=sys.stderr)


if __name__ == "__main__":
    main()
