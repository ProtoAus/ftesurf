"""p456solo.py -- the one-frame angle rule convicts honest low-frame-rate players.

    python tools/p456solo.py --rec <f.rec> --view <honest.view> [--foreign <other.view>]
    python tools/p456solo.py --rec <f.rec> --view <honest.view> --bias
    python tools/p456solo.py --rec <f.rec> --view <honest.view> --decimate <out.view>

WHAT IS WRONG.  reccheck's ANG_SOLO rule faults a pair when too many ticks that held
exactly ONE rendered frame disagree with the recording by more than a flat 0.05 deg.  That
population is not a sample of anything anomalous.  reccheck.py:2871 scores a tick as the
MINIMUM over the frames in it:

    dy = min(angdelta(y, f[4]) for f in g)
    if len(g) == 1: solo.append(...)

so a tick holding four frames picks its best of four and a `solo` tick, by definition, has
no minimum to take.  `solo` is the ordinary population with one advantage removed.

WHY IT MATTERS MORE THAN IT LOOKS.  Coverage is `len(solo) / comparable`, so a LOW frame
rate RAISES it -- and `covered` (>= ANG_SOLO_COVER) is what promotes the verdict to
`tight`.  A client drawing one frame per tick therefore makes every tick solo, reaches
100% cover, and is judged at MAXIMUM confidence by a rule that scores it with the handicap.
Decimating an honest sidecar to one frame per tick (`--decimate`) is how this was measured:
real angles, nothing rewritten, an unremarkable 49 fps, and the shipped rule answers
`angle_rule tight` and `the sidecar is not this recording's` at 67.6%.

THE FIX IS PHYSICS, NOT A THRESHOLD.  A rendered frame is drawn at some instant INSIDE the
tick, so the angle it holds cannot differ from the tick's own angle by more than about what
the camera swept during that tick.  Deviation above the tick's sweep is not explainable as
sampling time at any frame rate.  So:

    R0  shipped   dev > ANG_SOLO
    R1  ratio     dev > k * max(sweep, ANG_SOLO)

R1 needs no second test: with the floor at ANG_SOLO a still camera reduces it to exactly
R0, so the still-camera teeth -- the case the sweep rule is blind to, by reccheck's own
note -- are kept unchanged, and only a TURNING camera is given the tick's own motion as
slack.  k = 1 is the bound itself; the table below is printed for a range so the choice is
visible rather than asserted.

WHAT IT DOES NOT SHOW.  That the pair is honest.  It shows which rule can tell an honest
pair from a substituted one, and no rule here inspects anything but angles.

RESULT 2026-09-27, on runid 20260921-160402-0-p27520 (surf_4am), the chain's first ever
FAULT, against the same .rec joined to a different run's .view as the forgery control:

                                   R0 shipped      R1 ratio, k=1
    honest, as recorded (196 fps)  45.8%  FAULT     0.6%  clear
    honest, decimated  (49 fps)    67.6%  FAULT     0.1%  clear
    forgery            (196 fps)  100.0%  FAULT    99.7%  FAULT
    forgery, decimated (49 fps)    99.8%  FAULT    99.6%  FAULT

    fault when more than ANG_SOLO_HOLD = 5% of solo ticks are past the cut.

So R0 convicts every honest row and R1 discriminates on all four.  The three-way (`--bias`)
is the reason: denying the ordinary ticks their minimum makes them WORSE than the ticks the
rule convicted on -- 67.7% past cut against 45.8%, worst 6.12 deg against 2.44.

AND THE BASELINE THE FAULT TEXT QUOTES CANNOT BE ONE.  "honest worst measured: 0.0104 deg"
is a camera turning under 1 deg/s; every v9 corpus fixture drives its route with setpos and
noclip, so the camera never turns.  The run measured here swept 25351 deg.

A PAIR IS NOT IN THE REPO.  Recordings are archived as
data/runs/<map>/<leg>/<ticks>_<tag>_run.rec and matched to a receipt by the `runid` INSIDE
the file, not by filename -- so a filename search for a runid finds nothing.  Point --rec
and --view at any pair; the tools derive nothing from their location.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reccheck                                            # noqa: E402

ad = reccheck.angdelta
HOLD = 5.0                      # reccheck.ANG_SOLO_HOLD: per cent of solo past cut


def joined(recpath, viewpath):
    """Every joined tick, via reccheck's OWN join -- (nframes, dev_min, dev_first, sweep).

    Intercepting angle_join rather than re-parsing is deliberate: a hand-rolled parse of
    this same pair found 24 solo ticks where reccheck found 155, and a disagreement about
    the join makes every number downstream worthless.
    """
    grab = {}
    orig = reccheck.angle_join

    def spy(r, rec, frames):
        grab.update(frames=frames, rec=rec, r=r)
        return orig(r, rec, frames)

    reccheck.angle_join = spy
    try:
        rec = reccheck.check_rec(recpath)
        reccheck.check_view(viewpath, rec)
    finally:
        reccheck.angle_join = orig
    if "frames" not in grab:
        raise SystemExit("angle_join never ran on %s -- this measured NOTHING; the .view "
                         "did not parse or the .rec carries no angle stream" % viewpath)

    r = grab["r"]
    mts, yaws, pits, instart, source, ver = rec.angles
    m = re.match(r"([+-]?\d+) ticks", r.info.get("angle_lag", ""))
    lag = int(m.group(1)) if m else 0
    endtick = rec.info.get("ticks")
    gw = list(rec.angle_ghosts)
    byt = {}
    for f in grab["frames"]:
        byt.setdefault(int(f[2]), []).append(f)

    out = []
    py = pp = None
    for i in range(len(mts)):
        y, p = yaws[i], pits[i]
        sy = 0.0 if py is None else ad(y, py)
        sp = 0.0 if pp is None else ad(p, pp)
        py, pp = y, p
        raw = mts[i] - instart
        tk = raw - lag
        if raw < 0 or (endtick is not None and raw > endtick):
            continue            # both ends come from the RECORDING, as reccheck does it
        if gw and any(a <= raw and (b is None or raw <= b) for a, b in gw):
            continue
        g = byt.get(tk)
        if not g:
            continue
        dmin = max(min(ad(y, f[4]) for f in g), min(ad(p, f[3]) for f in g))
        dfst = max(ad(y, g[0][4]), ad(p, g[0][3]))
        out.append((len(g), dmin, dfst, max(sy, sp)))
    return out, source


def pctl(v, q):
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(q / 100.0 * (len(s) - 1)))))] if s else 0.0


def line(name, v):
    if not v:
        print("  %-44s (empty -- measured nothing)" % name)
        return
    print("  %-44s n=%-6d p50 %7.4f  p99 %7.4f  max %8.4f  past cut %5.1f%%"
          % (name, len(v), pctl(v, 50), pctl(v, 99), max(v),
             100.0 * sum(1 for d in v if d > reccheck.ANG_SOLO) / len(v)))


def decimate(src, dst):
    """Write `src` keeping the FIRST frame of each run-relative tick (column 3).

    An honest client drawing at or below the tick rate renders one frame per tick and does
    not choose which, so this is an honest low-frame-rate sidecar built from honest angles.
    """
    seen = set()
    kept = dropped = 0
    with open(src, "r", errors="replace") as fi, open(dst, "w", newline="\n") as fo:
        body = False
        for ln in fi:
            if not body:
                fo.write(ln)
                body = ln.strip() == "begin"
                continue
            a = ln.split()
            if len(a) < 5:
                fo.write(ln)
                continue
            if a[2] in seen:
                dropped += 1
                continue
            seen.add(a[2])
            kept += 1
            fo.write(ln)
    print("decimated %s -> %s: kept %d frames, dropped %d"
          % (os.path.basename(src), os.path.basename(dst), kept, dropped))
    if not dropped:
        print("NOTE: nothing was dropped, so this is not a low-frame-rate sidecar and "
              "grading it proves nothing about coverage.")
    return kept


def grade(rows, k):
    """-> (r0_frac, r1_frac) over the SOLO ticks only, which is what the rule judges."""
    solo = [(d, s) for n, d, _f, s in rows if n == 1]
    if not solo:
        return None
    n = float(len(solo))
    r0 = 100.0 * sum(1 for d, s in solo if d > reccheck.ANG_SOLO) / n
    r1 = 100.0 * sum(1 for d, s in solo
                     if d > k * max(s, reccheck.ANG_SOLO)) / n
    return (r0, r1, len(solo))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rec", required=True)
    ap.add_argument("--view", required=True, help="the honest sidecar for that .rec")
    ap.add_argument("--foreign", help="another run's .view -- the forgery control")
    ap.add_argument("--bias", action="store_true",
                    help="the three-way that shows solo is a handicap, not an anomaly")
    ap.add_argument("--decimate", metavar="OUT",
                    help="write a one-frame-per-tick copy of --view and grade it too")
    ap.add_argument("--k", type=float, default=None,
                    help="grade one k instead of the table")
    a = ap.parse_args()

    rows, source = joined(a.rec, a.view)
    if not rows:
        raise SystemExit("no joined ticks -- measured nothing")
    print("PAIR   %s" % os.path.basename(a.rec))
    print("       %s   (angle source %r)" % (os.path.basename(a.view), source))
    nsolo = sum(1 for n, _d, _f, _s in rows if n == 1)
    print("joined %d ticks, %d of them solo (%.0f%% -- coverage is what promotes the "
          "verdict to `tight`)" % (len(rows), nsolo, 100.0 * nsolo / len(rows)))

    if a.bias:
        print()
        print("THREE WAYS, deg.  A is what the rule judges; C is B under A's handicap:")
        line("A  solo ticks, one frame, no choice",
             [d for n, d, _f, _s in rows if n == 1])
        line("B  multi-frame ticks, min over frames",
             [d for n, d, _f, _s in rows if n > 1])
        line("C  multi-frame ticks, FIRST frame only",
             [f for n, _d, f, _s in rows if n > 1])
        print()
        print("  If C is no better than A, `solo` is not an anomalous sample -- it is the")
        print("  ordinary population with the minimum-over-frames advantage removed.")
        sol = [(d, s) for n, d, _f, s in rows if n == 1]
        if sol:
            print()
            print("  And where the deviation lives, for the solo ticks:")
            line("solo, camera swept >= 1 deg", [d for d, s in sol if s >= 1.0])
            line("solo, camera swept <  1 deg", [d for d, s in sol if s < 1.0])
            print("  A sampling-time difference scales with the turn; a rewritten angle")
            print("  does not.")

    sets = [("honest, as recorded", rows)]
    if a.decimate:
        if decimate(a.view, a.decimate):
            drows, _ = joined(a.rec, a.decimate)
            sets.append(("honest, decimated", drows))
    if a.foreign:
        frows, _ = joined(a.rec, a.foreign)
        sets.append(("FORGERY control", frows))

    ks = [a.k] if a.k else [0.5, 1.0, 1.5, 2.0]
    print()
    print("SOLO TICKS PAST CUT, and a rule must clear every honest row AND fault the")
    print("forgery.  Fault above %g%%.  R0 = shipped flat %g deg; R1 = dev > k*sweep."
          % (HOLD, reccheck.ANG_SOLO))
    print()
    print("  %-22s %8s   %-16s %s" % ("", "n solo", "R0 shipped", "R1 ratio"))
    bad = 0
    for k in ks:
        print("  k = %.1f" % k)
        for name, rr in sets:
            g = grade(rr, k)
            if not g:
                print("  %-22s   (no solo ticks -- measured nothing)" % name)
                continue
            r0, r1, n = g
            v = lambda f: "FAULT" if f > HOLD else "clear"          # noqa: E731
            print("  %-22s %8d   %6.1f%% %-7s  %6.1f%% %-7s"
                  % (name, n, r0, v(r0), r1, v(r1)))
        if a.foreign:
            hon = [grade(rr, k) for nm, rr in sets if nm != "FORGERY control"]
            frg = grade([rr for nm, rr in sets if nm == "FORGERY control"][0], k)
            if frg and all(hon):
                ok0 = all(h[0] <= HOLD for h in hon) and frg[0] > HOLD
                ok1 = all(h[1] <= HOLD for h in hon) and frg[1] > HOLD
                print("      R0 %s    R1 %s"
                      % ("DISCRIMINATES" if ok0 else "no",
                         "DISCRIMINATES" if ok1 else "no"))
                if not ok1:
                    bad = 1
        print()
    print("SELF-CHECK: with --foreign, R0 is expected to FAULT the honest rows -- that is")
    print("the defect. If R0 clears them, this is not reproducing the bug and the R1")
    print("column proves nothing by comparison.")
    return bad


if __name__ == "__main__":
    sys.exit(main())
