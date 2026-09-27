"""Census: can one map's zone file be used on a DIFFERENT build of that map?

The zone loader keys on map name alone (sv_zones.qc:177-181), so making
Momentum's zones apply to a CS:S or _ksf build of the same map needs no code --
only maps/zones/local/<thatname>.json.  What it DOES need is for the two builds
to share a coordinate frame, because a zone is an absolute world polygon
(sh_zones.qc:34), and for the restart destinations to exist, because 3241 of
3297 start/stage regions locate theirs by `teleDestTargetname` naming an
info_teleport_destination IN THE BSP (sh_zones.qc:63-70).  Neither is implied by
"the geometry is the same-ish".

So this measures both, per candidate pair, and never guesses:

  FRAME      every start/end region inside the target's world bbox, and the two
             worldspawn bboxes agreeing on their mins.  A recompile changes the
             maxs (added geometry, a raised skybox); a re-origined map moves the
             mins, and then every zone polygon is in the wrong place.
  DESTS      every teleDestTargetname the zone file names resolves to a
             targetname in the TARGET bsp.
  GEOMETRY   worldspawn brush-model bbox, both builds, so a rescale is visible.

A pair that fails FRAME cannot be fixed by copying the file; it needs an offset,
which is a different feature.  A pair that passes FRAME and fails DESTS gets
zones that time correctly and a restart that goes nowhere -- worth knowing
separately, which is why they are graded apart rather than as one "works".

WHAT THE FIRST RUN GOT WRONG, kept here because the fix is the point.  The
verdict was originally driven off destination COINCIDENCE: how many of the
source's info_teleport_destination origins sit at the same coordinates in the
target.  That called surf_aqua and surf_chaos SHIFTED at 0 of 3 and 0 of 6 --
while their worldspawn mins were identical on all three axes and every
targetname the zone file names resolved in the target.  Those are `_fix` builds
and moving a broken start teleport is what the fix WAS.  The zone file locates
its destination BY NAME, so it follows the entity wherever that build put it,
which is the behaviour you want.  Coincidence is now reported as evidence and
never as a verdict: a moved entity and a moved world are different findings, and
only one of them is a defect.

Usage:
  python tools/census/zonefit.py <zonemap>=<targetmap> [...]
  python tools/census/zonefit.py --file pairs.txt     # one pair per line
Env: MOMENTUM_DIR overrides the install root.
"""
import json, os, sys

import bsplib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum")
MOMMAPS = os.path.join(MOM, "maps")
ZONLINE = os.path.join(MOMMAPS, "zones", "online")
ZLOCAL = os.path.join(ROOT, "ftesurf", "maps", "zones", "local")
GAMEMAPS = os.path.join(ROOT, "ftesurf", "maps")

# A destination is "the same point" within this many units on every axis.  1.0,
# not 0: VBSP writes entity origins as decimal text and two compiles of the same
# .vmf can disagree in the last digit.  Nothing legitimate is 1 unit away from
# its own twin, and a shifted build is out by hundreds.
SAMEPT = 1.0


# Where a donor's zone file is looked up, in order.  A caller that is about to
# WRITE into ZLOCAL must pin this to the Momentum install first -- otherwise a
# second run reads back its own copies and the check stops being independent.
SEARCH = [ZLOCAL, ZONLINE]


def zonepath(name):
    for d in SEARCH:
        p = os.path.join(d, name + ".json")
        if os.path.exists(p):
            return p
    return None


def bsppath(name):
    """Gamedir first, exactly as the engine's VFS resolves it."""
    for d in (GAMEMAPS, MOMMAPS):
        p = os.path.join(d, name + ".bsp")
        if os.path.exists(p):
            return p, ("gamedir" if d == GAMEMAPS else "momentum")
    return None, None


def regions(z):
    """-> [(tag, region_dict)] for every region in the file, start/end tagged."""
    out = []

    def seg(zones, who):
        segs = zones.get("segments") or []
        for i, s in enumerate(segs):
            for j, cp in enumerate(s.get("checkpoints") or []):
                # segments[0].checkpoints[0] is the START; later checkpoints[0]
                # are STAGE gates.  sh_zones.qc:43-45.
                tag = ("start" if (i == 0 and j == 0)
                       else "stage" if j == 0 else "checkpoint")
                for r in cp.get("regions") or []:
                    out.append(("%s:%s" % (who, tag), r))
        end = zones.get("end") or {}
        for r in end.get("regions") or []:
            out.append(("%s:end" % who, r))

    tracks = z.get("tracks") or {}
    main = tracks.get("main") or {}
    seg(main.get("zones") or {}, "main")
    for k, b in enumerate(tracks.get("bonuses") or []):
        seg(b.get("zones") or {}, "b%d" % (k + 1))
    return out


def rbox(r):
    pts = r.get("points") or []
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    b = float(r.get("bottom", 0))
    h = float(r.get("height", 0))
    return (min(xs), min(ys), b), (max(xs), max(ys), b + h)


def inside(box, wmins, wmaxs, slack=64.0):
    lo, hi = box
    for a in range(3):
        if hi[a] < wmins[a] - slack or lo[a] > wmaxs[a] + slack:
            return False
    return True


def origins(ents, classname):
    out = []
    for e in ents:
        if (e.get("classname") or "").lower() != classname:
            continue
        o = (e.get("origin") or "").split()
        if len(o) != 3:
            continue
        try:
            out.append(tuple(float(v) for v in o))
        except ValueError:
            pass
    return out


def targetnames(ents):
    return {(e.get("targetname") or "") for e in ents} - {""}


def near(p, pool):
    for q in pool:
        if all(abs(p[a] - q[a]) <= SAMEPT for a in range(3)):
            return True
    return False


def check(zonemap, targetmap):
    zp = zonepath(zonemap)
    if zp is None:
        return "NO-ZONE", "no zone file for %s" % zonemap, None
    sp, ssrc = bsppath(zonemap)
    tp, tsrc = bsppath(targetmap)
    if tp is None:
        return "NO-BSP", "%s.bsp not installed" % targetmap, None

    z = json.load(open(zp, encoding="utf-8-sig"))
    tents, tmodels = bsplib.read(tp)
    if tents is None:
        return "UNREADABLE", "%s is not a VBSP" % targetmap, None

    regs = regions(z)
    twm, twx = (tmodels[0][0], tmodels[0][1]) if tmodels else ((0,) * 3, (0,) * 3)

    out_of_world = [tag for tag, r in regs
                    if tag.endswith(("start", "end", "stage"))
                    and rbox(r) and not inside(rbox(r), twm, twx)]

    # DESTS -- every targetname the file names, against the TARGET's entities.
    want = set()
    npos = 0
    for _, r in regs:
        tn = r.get("teleDestTargetname")
        if tn:
            want.add(tn)
        elif r.get("teleDestPos"):
            npos += 1
    have = targetnames(tents)
    missing = sorted(want - have)

    # FRAME -- the strong test.  Same coordinate frame means the two builds put
    # their teleport destinations at the same coordinates.
    frame = None
    if sp:
        sents, smodels = bsplib.read(sp)
        if sents is not None:
            sd = origins(sents, "info_teleport_destination")
            td = origins(tents, "info_teleport_destination")
            if sd:
                hit = sum(1 for p in sd if near(p, td))
                frame = (hit, len(sd), len(td))
            swm, swx = (smodels[0][0], smodels[0][1]) if smodels else (None, None)
        else:
            swm = swx = None
    else:
        swm = swx = None

    # The frame test: worldspawn mins.  Not the maxs -- a recompile legitimately
    # raises the skybox or adds geometry at the far end, and surf_aqua/_fix
    # differs there by 2048 units on Z while sharing an origin.
    minshift = None
    if swm is not None:
        minshift = max(abs(swm[a] - twm[a]) for a in range(3))

    det = {"regions": len(regs), "out_of_world": out_of_world,
           "want": len(want), "missing": missing, "telepos": npos,
           "frame": frame, "minshift": minshift,
           "sbbox": (swm, swx), "tbbox": (twm, twx),
           "zone": zp, "target": "%s (%s)" % (tp, tsrc)}

    if out_of_world:
        return "SHIFTED", "%d start/end/stage region(s) outside the target world" % len(out_of_world), det
    if minshift is not None and minshift > 64:
        return "SHIFTED", "world mins differ by up to %.0f units" % minshift, det
    if missing:
        return "NO-DESTS", "%d of %d teleDestTargetname absent from the target" % (len(missing), len(want)), det
    if swm is None:
        # The donor has no bsp of its own (surf_adrift), so there is nothing to
        # compare a frame against.  Not a pass and not a failure.
        return "UNCHECKED", "no donor bsp -- frame not comparable, %d dests all present" % len(want), det
    return "FIT", "%d regions, %d destinations all present" % (len(regs), len(want)), det


def main(argv):
    pairs = []
    i = 1
    while i < len(argv):
        if argv[i] == "--file":
            i += 1
            for ln in open(argv[i], encoding="utf-8"):
                ln = ln.split("#")[0].strip()
                if "=" in ln:
                    pairs.append(tuple(x.strip() for x in ln.split("=", 1)))
        elif "=" in argv[i]:
            pairs.append(tuple(x.strip() for x in argv[i].split("=", 1)))
        i += 1

    if not pairs:
        print(__doc__)
        return 2

    print("zonefit -- MOM=%s" % MOM)
    print("%-28s %-28s %-10s %s" % ("zone from", "applied to", "verdict", "detail"))
    tally = {}
    for zm, tm in pairs:
        v, why, det = check(zm, tm)
        tally[v] = tally.get(v, 0) + 1
        print("%-28s %-28s %-10s %s" % (zm, tm, v, why))
        if det and det["frame"]:
            hit, ns, nt = det["frame"]
            print("%58s frame: %d/%d dests coincide (target has %d)" % ("", hit, ns, nt))
        if det and det["missing"]:
            print("%58s missing: %s%s" % ("", ", ".join(det["missing"][:4]),
                                          " ..." if len(det["missing"]) > 4 else ""))
        if det and det["sbbox"][0] and det["tbbox"][0]:
            (a, b), (c, d) = det["sbbox"], det["tbbox"]
            print("%58s bbox src %s..%s" % ("", fmt(a), fmt(b)))
            print("%58s      tgt %s..%s" % ("", fmt(c), fmt(d)))
    print()
    print("  " + ", ".join("%s %d" % kv for kv in sorted(tally.items())))
    return 0


def fmt(v):
    return "(%.0f %.0f %.0f)" % tuple(v)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
