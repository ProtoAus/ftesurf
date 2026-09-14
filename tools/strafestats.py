#!/usr/bin/env python3
"""
strafestats.py -- the Layer 3 strafe statistics, measured on real recordings.

WHY THIS EXISTS.  The anti-cheat plan names three statistical detectors and has
built none of them.  The one that matters for a strafe optimiser is stated as
"regress applied yaw against asin(30/speed)" plus "a discontinuity in strafe
quality EXACTLY at 280 u/s, conditioned on jump held and sign(mouse_x) ==
sign(sidemove)".  That is a specification, not a number.  Before anything can be
detected, somebody has to measure what HONEST play looks like under it -- because
a detector whose false-positive rate is unknown may not be pointed at a named
person on a public board.

So this tool computes the statistic on the recordings that already exist, and
its headline output is a NOISE FLOOR rather than a verdict.

THE GATE IS THE CHEAT'S OWN, TERM FOR TERM.  StrafePro (a Python strafe
optimiser; external, closed-loop, SendInput) fires only when

    speed > 280.0  and  jump held  and  exactly one of A/D

and injects  round(degrees(asin(30/speed)) * GAIN / 0.022 * POWER)  mouse counts
every 10 ms.  Those four conditions are reproduced below from the .rec columns,
not approximated: `keys` carries FSI_JUMP/FSI_LEFT/FSI_RIGHT directly.

TWO STATISTICS, AND THE SECOND IS THE USEFUL ONE.

  rho   the assist ratio: the player's own applied yaw per tick divided by the
        optimiser's target angle for that speed.  MEASURED ON 90,792 GATED
        SAMPLES FROM 87 HONEST RECORDINGS: mean +0.59, sd 1.54, median +0.44.
        The spread is 2.6x the mean, so rho's LEVEL separates nothing per run --
        which is the `opti_power 20` problem the plan already names.  Its
        VARIANCE is a different matter at full power, where the tool does
        essentially all the steering and rho must collapse toward a constant;
        the v2 sample's author reports 99.4% strafe accuracy at 100/100, which
        is a claim about exactly that collapse.  Not implemented here: it needs
        an assisted recording to calibrate against and there is not one yet.

  step  the 280 u/s discontinuity, and THE OBVIOUS ESTIMATOR FOR IT DOES NOT
        WORK.  Comparing mean assist below the gate with mean assist above it
        reads +0.38 deg/tick on honest play, because speed and turn rate are
        physically correlated and a +-30 u/s window carries that trend.  A
        local-linear regression-discontinuity fit removes it and the honest
        floor drops to -0.09, which is the zero it should always have been.
        See rd_step().

        VALIDATED AGAINST A KNOWN ANSWER, not only against nulls: --inject adds
        the optimiser's own arithmetic to the honest corpus above the gate, and
        the fit recovers 99.7% of the injected step for v1 and 82% for v2.  The
        missing 18% is v2's exponential smoother, which resets at the gate and
        ramps in over ~7 ticks -- so what the estimator is looking for is no
        longer quite a step.

WHAT THIS IS NOT.  It does not accuse.  The plan's decision policy says
statistical findings flag for human review and never auto-reject, and nothing
here produces a threshold.  It produces distributions.  Nor is --inject a
simulation: a real assist would have changed the trajectory and therefore the
speeds, so it bounds the signal rather than reproducing a run.

Usage:
    python tools/strafestats.py                     # every .rec under data/runs
    python tools/strafestats.py <file.rec> [...]
    python tools/strafestats.py --pooled            # one distribution over all
    python tools/strafestats.py --pooled --inject   # the positive control
    python tools/strafestats.py --variant v1        # the older sample's presets
    python tools/strafestats.py --sens 0.3          # the k a prediction assumes
"""

import argparse
import glob
import math
import os
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(SURFDIR, "ftesurf", "data", "runs")

# shared/sh_defs.qc -- FSI_<x> is 1 << FSK_<x>.
FSI_LEFT, FSI_RIGHT, FSI_JUMP = 4, 8, 16
# sv_timer.qc SV_RecLine's `fl`.
FL_ONGROUND, FL_JUMPBTN, FL_RAMP = 1, 4, 16

# strafe_pro.py's own constants. Quoted, not re-derived.
AIR_WISHSPEED = 30.0
VELOCITY_THRESHOLD = 280.0
M_YAW = 0.022

# TWO VARIANTS ARE IN THE SAMPLE SET AND THEY DIFFER IN WAYS THAT MATTER HERE.
# The output stage is identical in both -- SendInput, MOUSEEVENTF_MOVE, dy 0 --
# so E1's verdict covers both without re-running it. What changed is the size of
# the signal and the SHAPE of it at the gate:
#
#   v1  POWER_PRESETS [0.125, 0.25, 0.375, 0.50], GAIN [0.1875 .. 0.75],
#       injection = round(delta * power).  The rounding quantises small deltas
#       to zero outright.
#
#   v2  POWER_PRESETS [0.25, 0.50, 0.75, 1.0] -- the maximum DOUBLES -- GAIN
#       [0.184 .. 0.736], and two new mechanisms:
#         * a sub-pixel accumulator carrying the fraction across ticks instead
#           of round(), so the delivered angle is exact on average rather than
#           quantised.  Removes a dither a detector could have keyed on.
#         * an exponential smoother, alpha 0.35, RESET TO ZERO whenever the gate
#           closes.  So crossing 280 no longer produces a step: it produces a
#           ramp reaching 95% in about 7 ticks (~70 ms at 0.01).  That is aimed
#           squarely at the discontinuity below, whether or not it was meant to
#           be -- the author's note was that it feels smoother.
#       It also resolves A+D held together to the LAST key pressed, where v1
#       returned and did nothing.  The gate is therefore slightly wider.
VARIANTS = {
    "v1": {"power": 0.50, "gain": 0.75,  "alpha": 1.0,  "subpixel": False},
    "v2": {"power": 1.00, "gain": 0.736, "alpha": 0.35, "subpixel": True},
}
POWER = VARIANTS["v2"]["power"]
GAIN = VARIANTS["v2"]["gain"]

# The speed windows either side of the gate. Deliberately narrow and symmetric:
# a wide window measures "do fast players turn differently from slow ones", which
# is true and is not the question.
BAND = 30.0


def wrap(d):
    while d > 180.0:
        d -= 360.0
    while d < -180.0:
        d += 360.0
    return d


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def median(xs):
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def rd_step(rows, cut=VELOCITY_THRESHOLD, band=None):
    """The discontinuity at `cut`, with the smooth trend removed.

    THE NAIVE ESTIMATOR DOES NOT WORK AND THIS IS WHY.  Comparing mean assist
    below the gate with mean assist above it measures a real honest-play step of
    about +0.38 deg/tick -- because speed and turn rate are PHYSICALLY
    CORRELATED.  A player at 300 u/s is further into a ramp than one at 260 and
    is turning harder for reasons that have nothing to do with 280.  Measured
    over 90,792 gated samples from 87 real recordings, that confound is two
    thirds the size of the signal a MAXIMUM-power assist would add, so the test
    as specified in the plan cannot separate them.

    So: fit a line to each side over the same window and take the difference of
    the two INTERCEPTS at the cut.  The trend cancels; a genuine step does not.
    This is the standard local-linear regression-discontinuity estimator, and it
    is the difference between a statistic that works and one that does not.

    Returns (step, n_below, n_above) or (nan, n, n) if either side is too thin.
    """
    band = band or BAND
    lo = [(sp - cut, ass) for sp, ass, fl in rows if cut - band <= sp < cut]
    hi = [(sp - cut, ass) for sp, ass, fl in rows if cut <= sp < cut + band]
    if len(lo) < 20 or len(hi) < 20:
        return float("nan"), len(lo), len(hi)

    def intercept(pts):
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        if sxx <= 0:
            return my
        b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
        return my - b * mx          # value of the fit AT the cut (x = 0)

    return intercept(hi) - intercept(lo), len(lo), len(hi)


def theta_star(speed):
    """StrafePro's target angle for this speed, in degrees, before GAIN."""
    return math.degrees(math.asin(min(AIR_WISHSPEED / speed, 1.0)))


def injected_degrees(speed, k, var=None):
    """Degrees of view rotation StrafePro delivers per 10 ms tick at this speed.

    Note what it does NOT do: `sensitivity` is absent from strafe_pro.py, which
    hardcodes M_YAW and converts its angle to COUNTS.  The victim's engine then
    turns counts back into degrees with its own k = sensitivity * m_yaw.  So the
    delivered angle is the intended one scaled by (k / 0.022) -- at sensitivity
    0.5 that is half, at 0.3 it is under a third.  The cheat is quietly weaker
    than its own settings claim on every config but sensitivity 1.0, and neither
    variant knows it.

    This is the STEADY-STATE value.  v2's smoother has unit gain once settled,
    so it changes the transient at the gate and not the size here; v2's
    accumulator makes the average exact rather than rounded, which is why only
    v1 rounds.
    """
    v = var or VARIANTS["v2"]
    counts = theta_star(speed) * v["gain"] / M_YAW * v["power"]
    if not v["subpixel"]:
        counts = round(counts)
    return counts * k


def read_rec(path):
    """-> (header dict, [sample tuples]).  Padding samples (t < 0) are dropped."""
    head, samples = {}, []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        first = fh.readline().strip()
        if not first.startswith("FTESURF-REC"):
            return None, None
        head["version"] = int(first.split()[1])
        inbody = False
        for line in fh:
            t = line.split()
            if not t:
                continue
            if not inbody:
                if t[0] == "begin":
                    inbody = True
                elif len(t) >= 2:
                    head[t[0]] = " ".join(t[1:])
                continue
            if t[0] in ("end", "split", "cp", "stage", "board", "resume", "ghost", "best"):
                continue
            try:
                v = [float(x) for x in t]
            except ValueError:
                continue
            if len(v) < 14:          # v2 has no keys/movement columns at all
                continue
            if v[0] < 0:             # pre-start padding ring
                continue
            samples.append(v)
    return head, samples


def analyse(path, inject_k=None):
    """inject_k: if set, ADD StrafePro's assist to every sample above the gate.

    A SYNTHETIC POSITIVE CONTROL, and it is not a simulation.  The assisted view
    would have changed the trajectory and therefore the speeds, so this file is
    not a run that could have happened.  What it IS, exactly, is the question the
    estimator has to answer: if this player's yaw had carried the optimiser's
    increment above 280 u/s and nothing below it, does the fit recover the step,
    and at what size?  A detector validated only against nulls is half validated
    -- every honest recording in the tree is a true negative and there is not one
    true positive anywhere, so a test that always returned "clean" would have
    scored perfectly on all 87 of them.
    """
    head, s = read_rec(path)
    if head is None:
        return None
    if len(s) < 2:
        return None

    rate = 0.0
    for key in ("movetickrate", "tickrate"):
        try:
            rate = float(head.get(key, 0))
        except ValueError:
            rate = 0.0
        if rate > 0:
            break
    if rate <= 0:
        rate = 0.015

    var = VARIANTS[inject_k[1]] if inject_k else VARIANTS["v2"]
    k = inject_k[0] if inject_k else 0.0

    rows = []
    last_key = None          # v2's A+D tie-break: whichever was pressed last
    smoothed = 0.0           # v2's exponential state, reset when the gate shuts
    carry = 0.0              # v2's sub-pixel accumulator, reset with it
    prev_left = prev_right = False
    for i in range(1, len(s)):
        a, b = s[i - 1], s[i]
        dt = b[0] - a[0]
        if dt <= 0 or dt > 0.2:
            continue
        speed = math.hypot(a[4], a[5])
        if speed < 1.0:
            continue
        keys = int(a[10])
        left, right = bool(keys & FSI_LEFT), bool(keys & FSI_RIGHT)
        if left and not prev_left:
            last_key = "a"
        if right and not prev_right:
            last_key = "d"
        prev_left, prev_right = left, right

        gate = bool(keys & FSI_JUMP) and (left or right) and speed > VELOCITY_THRESHOLD
        if not gate:
            smoothed = carry = 0.0       # exactly where the cheat resets them
        if not (left or right):
            continue
        if not (keys & FSI_JUMP):        # `keyboard.is_pressed("space")`
            continue
        if left and right:
            # v1 returned here; v2 follows the last key pressed. Taking v2's
            # reading widens the gate slightly, and both-held is rare enough
            # that it does not move any number below.
            side = -1.0 if last_key == "a" else 1.0
        else:
            side = 1.0 if right else -1.0

        # +dx is a rightward mouse move, which DECREASES yaw, and StrafePro signs
        # its injection with copysign(..., side). So the direction it pushes is
        # -side in yaw. `assist` is positive when the player turns that way.
        dyaw = wrap(b[8] - a[8])
        assist = -side * dyaw / (dt / rate)

        if inject_k and speed > VELOCITY_THRESHOLD:
            # Walk the cheat's own state machine per tick so the gate transient
            # is modelled rather than assumed: v2 ramps in from zero with
            # alpha 0.35, v1 (alpha 1.0) steps.
            ticks = max(1, int(round(dt / rate)))
            added = 0.0
            target = theta_star(speed) * var["gain"] / M_YAW      # counts/tick
            for _ in range(ticks):
                smoothed += (target - smoothed) * var["alpha"]
                want = smoothed * var["power"]
                if var["subpixel"]:
                    carry += want
                    emit = int(carry)
                    carry -= emit
                else:
                    emit = round(want)
                added += emit * k
            assist += added / ticks

        rows.append((speed, assist, int(a[9])))

    if not rows:
        return {"path": path, "map": head.get("map", "?"), "n": 0}

    gated = [(sp, ass) for sp, ass, fl in rows if sp > VELOCITY_THRESHOLD]
    rho = [ass / theta_star(sp) for sp, ass in gated if theta_star(sp) > 0]

    below = [ass for sp, ass, fl in rows if VELOCITY_THRESHOLD - BAND <= sp < VELOCITY_THRESHOLD]
    above = [ass for sp, ass, fl in rows if VELOCITY_THRESHOLD <= sp < VELOCITY_THRESHOLD + BAND]

    step, nlo, nhi = rd_step(rows)

    return {
        "path": path,
        "map": head.get("map", "?"),
        "version": head["version"],
        "rate": rate,
        "n": len(rows),
        "n_gated": len(gated),
        "rho": rho,
        "below": below,
        "above": above,
        "rows": rows,
        "rd": step,
        "rd_n": (nlo, nhi),
        "speeds": [sp for sp, ass in gated],
    }


def report(r, sens, verbose, variant="v2"):
    if r is None:
        return
    if r.get("n", 0) == 0:
        if verbose:
            print("%-58s  no air-strafe samples under the gate" % os.path.basename(r["path"]))
        return
    k = sens * M_YAW
    nlo, nhi = r["rd_n"]
    # What the cheat would ADD above the gate and not below it, at these speeds.
    # ARITHMETIC, NOT A SIMULATION: the assisted view would have changed the
    # trajectory and therefore the speeds. It bounds the signal, it is not a run.
    pred = mean([injected_degrees(sp, k, VARIANTS[variant]) for sp in r["speeds"]]) if r["speeds"] else float("nan")

    print("%-44s %-18s n %5d  gated %5d" % (
        os.path.basename(r["path"])[:44], r["map"][:18], r["n"], r["n_gated"]))
    print("      rho  mean %+7.3f  sd %6.3f  median %+7.3f" % (
        mean(r["rho"]), sd(r["rho"]), median(r["rho"])))
    if r["rd"] == r["rd"]:
        print("      RD   step %+7.4f deg/tick at the 280 gate  (n %d below, %d above)"
              % (r["rd"], nlo, nhi))
        print("           a max-power assist would add %+.4f deg/tick" % pred)
    else:
        # This is the usual case and it is a result, not a gap: air-strafe time
        # is spent well ABOVE 280, so the window the discontinuity test needs is
        # thinly populated on most runs. Pooled, only ~10% of gated samples fall
        # within +-30 u/s of the gate.
        print("           no discontinuity estimate -- only %d/%d samples within +-%.0f u/s"
              " of the gate (need 20 each side)" % (nlo, nhi, BAND))
    print()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--pooled", action="store_true",
                    help="one distribution over every file, which is what a "
                         "per-player baseline would look like")
    ap.add_argument("--sens", type=float, default=0.5,
                    help="the sensitivity a prediction assumes (default 0.5)")
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="v2",
                    help="which StrafePro's constants to use (default v2)")
    ap.add_argument("--inject", action="store_true",
                    help="SYNTHETIC POSITIVE CONTROL: add the optimiser's assist "
                         "to every honest run above the gate and re-measure. Not "
                         "a simulation -- the real assist would have changed the "
                         "trajectory. It asks only whether the estimator RECOVERS "
                         "a step it is known to have been given.")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)

    files = a.files or sorted(glob.glob(os.path.join(RUNS, "**", "*.rec"), recursive=True))
    if not files:
        print("no .rec files found under %s" % RUNS)
        return 1

    inj = (a.sens * M_YAW, a.variant) if a.inject else None
    if a.inject:
        print("SYNTHETIC POSITIVE CONTROL -- StrafePro %s at sensitivity %.2f "
              "added above the gate\n" % (a.variant, a.sens))
    results = [analyse(f, inject_k=inj) for f in files]
    results = [r for r in results if r and r.get("n", 0) > 0]

    if a.pooled:
        rho, below, above, speeds, rows = [], [], [], [], []
        for r in results:
            rho += r["rho"]; below += r["below"]; above += r["above"]
            speeds += r["speeds"]; rows += r["rows"]
        k = a.sens * M_YAW
        pooled_rd, nlo, nhi = rd_step(rows)
        print("POOLED over %d recordings with air-strafe samples (of %d read)"
              % (len(results), len(files)))
        print("  gated samples          %d" % len(rho))
        print()
        print("  rho (assist ratio -- applied yaw / optimiser's target angle)")
        print("        mean %+.4f  sd %.4f  median %+.4f" % (mean(rho), sd(rho), median(rho)))
        print("        the sd is %.1fx the mean: rho cannot separate anything per run."
              % (sd(rho) / abs(mean(rho)) if mean(rho) else float('nan')))
        print()
        print("  the 280 u/s discontinuity, +-%.0f u/s either side" % BAND)
        print("        naive means      below %+.4f (n %d)   above %+.4f (n %d)   step %+.4f"
              % (mean(below), len(below), mean(above), len(above), mean(above) - mean(below)))
        print("        local-linear RD  step %+.4f deg/tick (n %d below, %d above)"
              % (pooled_rd, nlo, nhi))
        print("        support          %d of %d gated samples are within the band (%.1f%%)"
              % (nlo + nhi, len(rho), 100.0 * (nlo + nhi) / len(rho) if rho else 0.0))
        print("                         <- THE HONEST-PLAY FLOOR. The naive figure is")
        print("                            mostly the speed/turn-rate trend, not a step.")
        if speeds:
            print()
            print("  a max-power assist (POWER %.2f x GAIN %.2f) at sensitivity %.2f would add"
                  % (POWER, GAIN, a.sens))
            print("        %+.4f deg/tick averaged over every gated speed, and" 
                  % mean([injected_degrees(sp, k, VARIANTS[a.variant]) for sp in speeds]))
            print("        %+.4f deg/tick AT THE CUT, which is what the RD fit recovers"
                  % injected_degrees(VELOCITY_THRESHOLD, k, VARIANTS[a.variant]))
        # Per-file spread is what a threshold has to clear on ONE run.
        steps = [r["rd"] for r in results if r["rd"] == r["rd"]]
        if steps:
            print()
            print("  per-file RD step, %d files with >=20 samples each side:" % len(steps))
            print("        mean %+.4f  sd %.4f  min %+.4f  max %+.4f"
                  % (mean(steps), sd(steps), min(steps), max(steps)))
            if speeds:
                sig = injected_degrees(VELOCITY_THRESHOLD, k, VARIANTS[a.variant])
                print("        a max-power assist is %.2f sd from the honest mean"
                      % (sig / sd(steps) if sd(steps) else float('nan')))
        return 0

    for r in results:
        report(r, a.sens, a.verbose, a.variant)
    print("%d recordings, %d with air-strafe samples under the gate"
          % (len(files), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
