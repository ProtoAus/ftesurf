"""How far is a track's END from its own START?  Patch 448's argument turns on it.

WHY THIS EXISTS.  Patch 448 clears the hopped-start tag at a ZONE_END finish, and its
safety argument is:

    reaching the end zone means traversing the map, so a finisher's speed was built on
    the course rather than in the start box -- and to start again they must get back to a
    start, which costs either an `!r` (velocity zeroed) or the trip.

A round-8 reviewer said the trip is 16 to 64 units on eight shipped tracks.  That number
decides whether the argument holds, so it gets a tool rather than a quotation -- the same
reason tools/census/startrearm.py exists.  If the trip really is 16 units then "the trip"
is not a cost and the clear can hand back a clean next run with the speed still on, which
is exactly the class Patch 445 exists to eliminate.

WHAT IT MEASURES.  For every track in every shipped zone file: the gap between that
track's END regions and its OWN segment-0 START regions.  Per track, because a gap to
some other track's start is not a route -- the player must re-arm the leg they intend to
run.  Both AABB gap and, where both regions are axis-aligned rectangles, the EXACT gap.

GRADING, per tools/census/README.md.  This is zone-to-zone, so there is no AABB problem
in the sense that census has -- the regions are authored prisms.  But a region is a
POLYGON with a bottom and a height, and its AABB is larger than the prism whenever the
polygon is not an axis-aligned rectangle.  So an AABB gap is a LOWER BOUND on the real
gap, and this reports the two separately: `exact` where every polygon involved is a
rectangle (the AABB *is* the prism), `bound` otherwise.  Only the exact rows carry the
argument; the bounds say "no closer than".

WHAT IT DOES NOT SHOW.  That the trip is walkable, that the END is reachable, or that a
finisher retains speed across it.  A small gap is a candidate for a live check, not a
finding.

RESULT 2026-09-27: 537 zone files, 0 unreadable, 1734 tracks, 1732 with both an END and
a START (2 have no END at all, so they cannot be finished).

    END within   0 u of its own START:   5 tracks  (4 EXACT)
    END within  64 u:                   17 tracks (12 EXACT)
    END within 128 u:                   22 tracks (15 EXACT)
    END within 256 u:                   31 tracks (20 EXACT)

THE TWELVE EXACT ROWS AT OR UNDER 64 u ARE THE ONES THAT CARRY THE ARGUMENT, because for
them the AABB *is* the prism:

    0.0 u  agtricks main, surf_ethereal b1, surf_flyin_fortress main, surf_quirky b9
   16.0 u  surf_bikini_bottom b1, surf_ember2 b2, surf_tripportals b1
   32.0 u  surf_moonkingdom b3
   64.0 u  surf_kz_protraining b2, surf_liopleurodon2 b2, surf_quirky b3,
           surf_summer main (ELEVEN segments)

Five more are polygonal, so their gap is only a lower bound: surf_pools b2 (>=0),
surf_rez b1 (>=12), surf_efficacy b1 (>=32), surf_school b1 (>=64), surf_voyager b2
(>=64).

SO PATCH 448's "the trip costs something" WAS FALSE ON TWELVE TRACKS, and Patch 454 is
the answer: the finish ARMS a forgiveness and coming to rest takes it, so the clear
cannot carry speed whatever the geometry.  The four rows at 0.0 are a separate finding --
an END that overlaps its own START should read as a CANCEL rather than a finish
(SV_TimerTryArm runs before the event dispatch), which would mean those tracks cannot be
finished at all.  That is in BACKLOG.md and is not 448's or 454's doing.
"""
import json
import os
import sys

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common"
                     r"\Momentum Mod Playtest\momentum")
ZON = os.path.join(MOM, "maps", "zones", "online")


def regions(node):
    """-> list of (points, bottom, top) for a zones node that has `regions`."""
    out = []
    for r in (node or {}).get("regions") or []:
        pts = r.get("points") or []
        if len(pts) < 3:
            continue
        b = r.get("bottom", 0.0)
        out.append((pts, b, b + r.get("height", 0.0)))
    return out


def is_rect(pts):
    """True if the polygon is an axis-aligned rectangle, so its AABB IS the prism."""
    if len(pts) != 4:
        return False
    xs = sorted(set(round(p[0], 4) for p in pts))
    ys = sorted(set(round(p[1], 4) for p in pts))
    return len(xs) == 2 and len(ys) == 2


def box(r):
    pts, b, t = r
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), b), (max(xs), max(ys), t)


def gap(a, b):
    """Largest per-axis separation; 0 if the boxes touch or overlap."""
    amn, amx = box(a)
    bmn, bmx = box(b)
    g = 0.0
    for i in range(3):
        d = max(amn[i] - bmx[i], bmn[i] - amx[i])
        if d > g:
            g = d
    return g


def tracks(doc):
    """-> list of (label, trackdict)."""
    t = doc.get("tracks") or {}
    out = []
    if isinstance(t.get("main"), dict):
        out.append(("main", t["main"]))
    for i, b in enumerate(t.get("bonuses") or []):
        if isinstance(b, dict):
            out.append(("b%d" % (i + 1), b))
    return out


def main():
    if not os.path.isdir(ZON):
        sys.exit("no zone dir at %s (set MOMENTUM_DIR)" % ZON)
    files = sorted(f for f in os.listdir(ZON) if f.lower().endswith(".json"))

    rows = []
    st = dict(files=0, unreadable=0, tracks=0, pairable=0, noend=0, nostart=0)
    for f in files:
        try:
            doc = json.load(open(os.path.join(ZON, f), encoding="utf-8-sig"))
        except Exception:
            st["unreadable"] += 1
            continue
        st["files"] += 1
        name = os.path.splitext(f)[0]
        for label, tr in tracks(doc):
            st["tracks"] += 1
            z = tr.get("zones") or {}
            ends = regions(z.get("end"))
            segs = z.get("segments") or []
            starts = regions((segs[0] or {}).get("checkpoints", [{}])[0]) if segs else []
            if not ends:
                st["noend"] += 1
                continue
            if not starts:
                st["nostart"] += 1
                continue
            st["pairable"] += 1
            best = min(gap(e, s) for e in ends for s in starts)
            # Exact only when every polygon on both sides is an axis-aligned rectangle.
            exact = all(is_rect(e[0]) for e in ends) and all(is_rect(s[0]) for s in starts)
            segn = len(segs)
            rows.append((best, exact, name, label, segn))

    rows.sort()
    print("zone files %(files)d  unreadable %(unreadable)d  tracks %(tracks)d  "
          "with both an END and a START %(pairable)d  (no end %(noend)d, "
          "no start %(nostart)d)" % st)
    print()
    for cut in (0.0, 64.0, 128.0, 256.0):
        n = sum(1 for r in rows if r[0] <= cut)
        ex = sum(1 for r in rows if r[0] <= cut and r[1])
        print("  END within %6.0f u of its own START: %3d tracks  (%d of them EXACT)"
              % (cut, n, ex))
    print()
    print("EXACT rows at or under 64 u -- these are the ones that carry the argument:")
    hits = [r for r in rows if r[0] <= 64.0 and r[1]]
    for g, ex, name, label, segn in hits:
        print("  %7.1f u  %-34s %-5s  (%d segment%s)"
              % (g, name, label, segn, "" if segn == 1 else "s"))
    if not hits:
        print("  none")
    print()
    print("LOWER BOUNDS at or under 64 u (polygonal, so the real gap is >= this):")
    for g, ex, name, label, segn in [r for r in rows if r[0] <= 64.0 and not r[1]]:
        print("  >=%6.1f u  %-34s %-5s" % (g, name, label))
    print()
    print("SELF-CHECK: `pairable` is the denominator, and a zero above would be")
    print("meaningless if it were small.  A track with no END cannot be finished at all,")
    print("so `no end` is reported rather than folded into the counts.")


if __name__ == "__main__":
    main()
