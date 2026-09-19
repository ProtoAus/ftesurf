#!/usr/bin/env python3
"""
bodytrace.py -- statistics of a `body_trace` dump (Patch 383, client/cl_body.qc).

Reads a client log.  Line shapes (after the log's timestamp):

  bt <cltime> <re> <x> <y> <z> <yaw> <pitch> <eye> <st> <keys> <kraw> <slot> <fl>
       one drawn frame; re = render time in ticks (0 on the engine fallback),
       st = BT_* bits: 1 starved 2 reseed 4 snap 8 underrun 16 hold 32 jump 64 held
       128 raw (cl_body_raw 1: the undelayed newest sample, the UX control);
       fl = PBF_* plus 256 when the drawn sample carried SPEC
  bx <cltime> <tick> <gap> <lag> <pf> <spec> <reseed> <mv>
       one received sample; mv 1 = its origin or angles differ from the newest
       cell's.  tick -1 = the engine fallback (gap = deltas counted)
  body: cltime <t>, <n> bodies, tick <pm_ticrate>, ...     (body_stats)

Prints the numbers Patch 383's predictions name and one verdict per check the
chosen --arm registers (cfg/test/p383view.cfg).  The tick comes from the
body_stats lines; every registered number assumes 0.015 (the ARM line).
--from/--to (cltime) cut a window; without them the run must contain every
event its arm names, and a missing kill, rest, stall, attack or raw segment is
a FAIL rather than n/a.

usage: python tools/bodytrace.py <log> [--arm A] [--from T] [--to T]
                                       [--p1rate R] [--tick T]
  A: base (default) | rate15 | rate22 | rate66 | budget500 | loss | csqc |
     ctl15 | ctl66
"""

import bisect
import math
import re
import sys

ST_STARVED, ST_RESEED, ST_SNAP, ST_UNDER, ST_HOLD, ST_JUMP, ST_HELD, ST_RAW = 1, 2, 4, 8, 16, 32, 64, 128
FSI_TLEFT, FSI_ATTACK = 64, 256
PC_SPEC = 256
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
BODY = re.compile(r"body: cltime [-\d.]+, \d+ bodies, tick ([-\d.eE]+)")
CSQCRW = re.compile(r"CSQC (overread|underread) entity")

# The registered numbers (p383view.cfg).  Arm: (verdict, gap mode, samples/s).
REG_TICK = 0.015
ARMS = {
    "base":      ("P1",  1, (58.0, 67.0)),
    "rate15":    ("P2",  5, (12.0, 13.6)),
    "rate22":    ("P2",  3, (20.0, 22.6)),
    "rate66":    ("P2",  1, (58.0, 67.0)),
    "budget500": ("P10", 3, (20.0, 22.6)),
    "loss":      ("P9",  None, None),
    "csqc":      ("P7",  None, None),
    "ctl15":     ("P2",  None, (12.0, 13.6)),   # the stream's P2 at 15: the control may pass it
    "ctl66":     ("P2",  None, (58.0, 67.0)),   # ...and must fail it at 66.67
}
CTL_RATE = {"ctl15": (12.0, 13.6), "ctl66": (25.0, 45.0)}
YAW_RATE = (126.0, 154.0)       # cl_yawspeed 140 +-10%
PITCH_RANGE = 50.0              # the +-30 deg triangle wave
MIN_STEADY = 1000               # steady frames P3 needs before it can pass
KA_RATE = (1.6, 2.4)            # keepalives/s in a rest >= 5 s


def parse(path, t0, t1):
    frames, rx, ticks, rw = [], [], [], 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = STAMP.sub("", line.strip())
            if CSQCRW.search(line):
                rw += 1
            m = BODY.search(line)
            if m:
                ticks.append(float(m.group(1)))
                continue
            f = line.split()
            if len(f) < 2 or f[0] not in ("bt", "bx"):
                continue
            try:
                v = [float(x) for x in f[1:]]
            except ValueError:
                continue
            if not (t0 <= v[0] <= t1):
                continue
            if f[0] == "bt" and len(v) >= 13:
                frames.append(v)
            elif f[0] == "bx" and len(v) >= 7:
                rx.append(v)
    return frames, rx, ticks, rw


def mean(a):
    return sum(a) / len(a) if a else 0.0


def cv(a):
    if len(a) < 2:
        return 0.0
    m = mean(a)
    if m == 0:
        return 0.0
    return math.sqrt(sum((x - m) ** 2 for x in a) / (len(a) - 1)) / abs(m)


def pct(a, p):
    if not a:
        return 0.0
    s = sorted(a)
    return s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))]


def wrap(a):
    return a - 360.0 * math.floor((a + 180.0) / 360.0)


def dist(a, b):
    return math.sqrt((a[2] - b[2]) ** 2 + (a[3] - b[3]) ** 2 + (a[4] - b[4]) ** 2)


def moved(v, pos):
    return dist(v, pos) > 0.5 or abs(wrap(v[5] - pos[5])) > 0.5 or abs(v[6] - pos[6]) > 0.5


def mv(v):
    return v[7] if len(v) > 7 else None


def verdict(name, ok, text):
    print("  %-4s %-5s %s" % (name, "PASS" if ok else "FAIL", text))


def na(name, text):
    print("  %-4s n/a   %s" % (name, text))


def arrivals(rx):
    print("== samples (bx)")
    if not rx:
        print("  none")
        return {}
    span = rx[-1][0] - rx[0][0]
    engine = rx[0][1] < 0
    # engine fallback: one line per frame that saw deltas, the count in <gap>
    total = sum(v[2] for v in rx[1:]) if engine else len(rx) - 1
    rate = total / span if span > 0 else 0.0
    out = {"n": len(rx), "rate": rate, "engine": engine, "spec": sum(1 for v in rx if v[5])}
    print("  %d samples over %.2f s: %.2f /s%s" % (len(rx), span, rate,
          "  (engine deltas: lobby_av_stream 0)" if engine else ""))
    win, start, n = [], rx[0][0], 0
    for v in rx:
        while v[0] >= start + 1.0:
            win.append(n)
            start += 1.0
            n = 0
        n += 1
    if win:
        print("  per-second: min %d median %d max %d" % (min(win), pct(win, 0.5), max(win)))
    if engine:
        return out
    # The moving rate: whole seconds in which every sample advanced 1..8 ticks
    # and none carried SPEC (a spectated owner publishes every tick, any cap).
    steady, start, n, ok = [], rx[0][0], 0, True
    for v in rx:
        while v[0] >= start + 1.0:
            if ok and n:
                steady.append(n)
            start += 1.0
            n, ok = 0, True
        n += 1
        ok = ok and 1 <= v[2] <= 8 and not v[5]
    out["steadyrate"] = mean(steady)
    out["steadyn"] = len(steady)
    print("  moving seconds %d: %.2f samples/s" % (len(steady), out["steadyrate"]))
    gaps = [int(v[2]) for v in rx if v[2] > 0 and not v[5]]
    small = [g for g in gaps if g <= 8]
    hist = {}
    for g in gaps:
        hist[g] = hist.get(g, 0) + 1
    mode = max(hist, key=hist.get) if hist else 0
    print("  tick gaps (no SPEC): mode %d, mean(<=8) %.3f, histogram %s" % (
        mode, mean(small), " ".join("%d:%d" % (k, hist[k]) for k in sorted(hist)[:12])))
    same = sum(1 for v in rx if v[2] == 0)
    print("  same-tick samples %d, resume flags %d, with SPEC %d, reseeds %d" % (
        same, sum(1 for v in rx if int(v[4]) & 128), out["spec"], sum(1 for v in rx if v[6])))
    lags = [v[3] for v in rx[1:] if 0 < v[2] <= 8]
    if lags:
        print("  arrival lag over o: median %.4f p95 %.4f max %.4f s" % (
            pct(lags, 0.5), pct(lags, 0.95), max(lags)))
    out.update({"mode": mode, "gapmean": mean(small)})
    return out


def engine_moving_rate(fr, rx):
    """Deltas/s over the whole seconds in which the drawn body covered > 100 u
    (the circle's 1 s chord is ~199 u), so rests do not dilute the control."""
    ft = [v[0] for v in fr]
    rt = [v[0] for v in rx]
    rates, s = [], fr[0][0]
    while s + 1.0 <= fr[-1][0]:
        a, b = bisect.bisect_left(ft, s), bisect.bisect_left(ft, s + 1.0) - 1
        if b > a and dist(fr[a], fr[b]) > 100:
            rates.append(sum(v[2] for v in rx[bisect.bisect_left(rt, s):bisect.bisect_left(rt, s + 1.0)]))
        s += 1.0
    return mean(rates), len(rates)


def frames_report(fr, rx, tick):
    print("== frames (bt)")
    if len(fr) < 3:
        print("  none")
        return {}
    engine = fr[0][11] < 0 and fr[0][1] == 0
    dts = [fr[i][0] - fr[i - 1][0] for i in range(1, len(fr))]
    print("  %d frames, %.1f fps median" % (len(fr), 1.0 / max(1e-6, pct(dts, 0.5))))
    counts = {}
    for name, bit in (("starved", ST_STARVED), ("reseed", ST_RESEED), ("snap", ST_SNAP),
                      ("under", ST_UNDER), ("hold", ST_HOLD), ("jump", ST_JUMP), ("held", ST_HELD),
                      ("raw", ST_RAW)):
        counts[name] = sum(1 for v in fr if int(v[8]) & bit)
    print("  status: " + " ".join("%s %d" % (k, counts[k]) for k in counts))

    step = [0.0] + [dist(fr[i], fr[i - 1]) for i in range(1, len(fr))]
    moving_steps = [s for s in step if s > 0.01]
    med = pct(moving_steps, 0.5) if moving_steps else 0.0

    # large-step clusters: a teleport drawn in one frame, or smeared over several
    big = max(4.0, 4.0 * med)
    clusters, cur = [], None
    for i in range(1, len(fr)):
        if step[i] > big and not int(fr[i][8]) & ST_RAW:
            if cur and i == cur["last"] + 1:
                cur["last"] = i
                cur["frames"] += 1
                cur["dist"] += step[i]
                cur["snap"] = cur["snap"] or bool(int(fr[i][8]) & ST_SNAP)
            else:
                cur = {"first": i, "last": i, "frames": 1, "dist": step[i],
                       "snap": bool(int(fr[i][8]) & ST_SNAP)}
                clusters.append(cur)
    print("  large steps (> %.1f u/frame): %d cluster(s)" % (big, len(clusters)))
    for c in clusters[:12]:
        print("    at %.3f: %d frame(s), %.1f u%s" % (fr[c["first"]][0], c["frames"], c["dist"],
              ", snap" if c["snap"] else ""))

    # rests: >= 2 s with no drawn movement
    rests, i = [], 1
    while i < len(fr):
        if step[i] <= 0.01:
            j = i
            while j + 1 < len(fr) and step[j + 1] <= 0.01:
                j += 1
            if fr[j][0] - fr[i][0] >= 2.0:
                rests.append((i, j))
            i = j + 1
        else:
            i += 1

    # Steady windows keep 1 s clear of these.  Underruns and jumps are not on
    # the list: in a steady window they are clock failures and count against P3b.
    events = [fr[c["first"]][0] for c in clusters]
    events += [v[0] for v in fr if int(v[8]) & (ST_RESEED | ST_SNAP)]
    events += [fr[i][0] for i in range(1, len(fr)) if (int(fr[i][8]) ^ int(fr[i - 1][8])) & ST_RAW]
    for a, b in rests:
        events += [fr[a][0], fr[b][0]]
    events.sort()

    def near_event(t):
        k = bisect.bisect_left(events, t - 1.0)
        return k < len(events) and events[k] < t + 1.0

    inrest = set()
    for a, b in rests:
        inrest.update(range(a, b + 1))

    spd, yawr, rclk, starv, clockbad = [], [], [], 0, 0
    pitch_dir = []
    for i in range(1, len(fr)):
        st = int(fr[i][8])
        if i in inrest or near_event(fr[i][0]) or st & ST_RAW:
            continue
        if st & (ST_UNDER | ST_JUMP):
            clockbad += 1
        dt = fr[i][0] - fr[i - 1][0]
        if dt <= 0 or step[i] / dt < 50:
            continue
        spd.append(step[i] / dt)
        yawr.append(abs(wrap(fr[i][5] - fr[i - 1][5])) / dt)
        pitch_dir.append((i, (fr[i][6] - fr[i - 1][6]) / dt))
        if not engine:
            rclk.append((fr[i][1] - fr[i - 1][1]) * tick / dt)
        if st & ST_STARVED:
            starv += 1
    # pitch rate away from its reversals (0.1 s either side)
    rev = [fr[i][0] for k, (i, r) in enumerate(pitch_dir[1:], 1)
           if (r > 0) != (pitch_dir[k - 1][1] > 0)]
    pitr = []
    for i, r in pitch_dir:
        k = bisect.bisect_left(rev, fr[i][0] - 0.1)
        if abs(r) > 1 and not (k < len(rev) and rev[k] < fr[i][0] + 0.1):
            pitr.append(abs(r))
    out = {"engine": engine, "counts": counts, "clusters": clusters, "rests": rests,
           "nsteady": len(spd), "clockbad": clockbad, "medstep": med,
           "pitchrange": max(v[6] for v in fr) - min(v[6] for v in fr)}

    # frames that drew no movement while the body moves (a stepped body shows
    # most frames still between samples; UX control C1 is cl_body_raw 1)
    live = [i for i in range(1, len(fr)) if i not in inrest and not near_event(fr[i][0])
            and not int(fr[i][8]) & (ST_STARVED | ST_HELD)]
    interp = [i for i in live if not int(fr[i][8]) & ST_RAW]
    raw = [i for i in live if int(fr[i][8]) & ST_RAW]
    out["still"] = sum(1 for i in interp if step[i] <= 0.001) / len(interp) if interp else 0.0
    out["rawstill"] = sum(1 for i in raw if step[i] <= 0.001) / len(raw) if raw else None
    print("  steady frames %d (underrun/jump among them %d); still frames while moving %.1f%%" % (
        len(spd), clockbad, 100.0 * out["still"]))
    if raw:
        print("  cl_body_raw frames %d: still while moving %.1f%% (the UX control)" % (
            len(raw), 100.0 * out["rawstill"]))
    if spd:
        out.update({"speedcv": cv(spd), "yawmean": mean(yawr), "yawcv": cv(yawr),
                    "pitchcv": cv(pitr), "npitch": len(pitr), "starved": starv / len(spd)})
        print("  speed mean %.1f u/s CV %.4f | yaw rate mean %.1f deg/s CV %.4f" % (
            mean(spd), cv(spd), mean(yawr), cv(yawr)))
        print("  pitch rate mean %.1f deg/s CV %.4f (n %d), pitch range %.2f deg" % (
            mean(pitr), cv(pitr), len(pitr), out["pitchrange"]))
        if rclk:
            out.update({"rclk_lo": pct(rclk, 0.01), "rclk_hi": pct(rclk, 0.99)})
            print("  render clock rate mean %.4f p1 %.4f p99 %.4f; starved %.2f%%" % (
                mean(rclk), out["rclk_lo"], out["rclk_hi"], 100.0 * out["starved"]))

    # Rests and their resume (P5).  The resume tick is the first moved sample
    # after the last still one to arrive during the rest -- not the RESUME flag,
    # which a newer sample can supersede.
    p5 = []
    for a, b in rests:
        t_a, t_b = fr[a][0], fr[b][0]
        ka = [v for v in rx if t_a <= v[0] <= t_b and mv(v) != 1]
        line = "  rest %.3f..%.3f (%.1f s): %d still samples (%.2f /s)" % (
            t_a, t_b, t_b - t_a, len(ka), len(ka) / max(1e-6, t_b - t_a))
        tr = None
        if not engine and rx and mv(rx[0]) is not None:
            last = max((k for k, v in enumerate(rx) if v[0] <= t_b and mv(v) == 0), default=None)
            if last is not None:
                tr = next((v[1] for v in rx[last + 1:] if mv(v) == 1), None)
        elif not engine:
            tr = next((v[1] for v in rx if v[0] > t_a and int(v[4]) & 128), None)
        bad = None
        if tr is not None:
            pos = fr[b]
            bad = sum(1 for v in fr[b:] if v[1] < tr - 1 and moved(v, pos))
            first = next((v for v in fr[b:] if moved(v, pos)), None)
            line += ", resume tick %d, first drawn move at re %.2f, %d early frame(s)" % (
                tr, first[1] if first else -1, bad)
        print(line)
        p5.append((t_a, t_b - t_a, len(ka) / max(1e-6, t_b - t_a), bad))
    out["p5"] = p5

    # stalls (P6): each reseed with the starved run before it and the hold after
    stalls, reseeds = [], 0
    for i, v in enumerate(fr):
        if not int(v[8]) & ST_RESEED:
            continue
        reseeds += 1
        j = i - 1
        while j > 0 and int(fr[j][8]) & ST_STARVED:
            j -= 1
        path = sum(step[k] for k in range(j + 1, i))
        k, hold = i, 0.0
        while k + 1 < len(fr) and int(fr[k][8]) & ST_HOLD:
            hold += fr[k + 1][0] - fr[k][0]
            k += 1
        after = []          # the second AFTER the first one: "back under 2% within 1 s"
        for m in range(k + 1, len(fr)):
            if fr[m][0] < fr[k][0] + 1.0:
                continue
            if fr[m][0] > fr[k][0] + 2.0:
                break
            dt = fr[m][0] - fr[m - 1][0]
            if dt > 0 and step[m] / dt > 50:
                after.append(step[m] / dt)
        stalls.append((v[0], fr[i - 1][0] - fr[j][0], path, hold, cv(after), len(after)))
        print("  reseed at %.3f: starved %.3f s before, drawn drift %.2f u, hold after %.3f s, "
              "speed CV 1..2 s after %.4f (n %d)" % stalls[-1])
    out["stalls"] = [s for s in stalls if s[1] >= 0.5]
    out["reseeds"] = reseeds
    # a reseed with no stall before it, clear of teleports and rests, is a steady one
    quiet = [fr[c["first"]][0] for c in clusters] + [fr[a][0] for a, b in rests] + [fr[b][0] for a, b in rests]
    out["steady_reseeds"] = sum(1 for s in stalls
                                if s[1] < 0.1 and not any(abs(s[0] - e) < 1.0 for e in quiet))

    # held runs (P12): the largest drawn step within 0.6 s of the held edge.  The
    # held flag stops extrapolation, so the body halts on the held pose; without
    # it the body runs cl_body_extrap past it and snaps back when a keepalive
    # finally carries the flag.
    helds, i = [], 0
    while i < len(fr):
        if int(fr[i][8]) & ST_HELD:
            j = i
            while j + 1 < len(fr) and int(fr[j + 1][8]) & ST_HELD:
                j += 1
            t_e = fr[i][0]
            w = [step[k] for k in range(1, len(fr)) if abs(fr[k][0] - t_e) <= 0.6]
            helds.append((t_e, fr[j][0] - t_e, max(w) if w else 0.0, med))
            print("  held %.3f for %.2f s: largest step within 0.6 s of the edge %.2f u "
                  "(median moving step %.2f u)" % helds[-1])
            i = j + 1
        else:
            i += 1
    out["helds"] = helds

    # keys: frames drawn from a sample whose WIRE byte has attack (64); each
    # must show FSI_ATTACK (256) and not FSI_TLEFT (64), the unmapped bit
    spec = sum(1 for v in fr if int(v[12]) & PC_SPEC)
    att = [v for v in fr if int(v[10]) & 64]
    out["keys"] = (spec, len(att), sum(1 for v in att if not int(v[9]) & FSI_ATTACK),
                   sum(1 for v in att if int(v[9]) & FSI_TLEFT))
    print("  SPEC frames %d, wire-attack frames %d: without FSI_ATTACK %d, with FSI_TLEFT %d" % out["keys"])
    return out


def v_p3(f):
    if "speedcv" not in f:
        verdict("P3", False, "no steady frames")
        return
    ok = (f["nsteady"] >= MIN_STEADY and f["speedcv"] < 0.02
          and YAW_RATE[0] <= f["yawmean"] <= YAW_RATE[1] and f["yawcv"] < 0.03
          and f["pitchrange"] >= PITCH_RANGE and f["npitch"] >= 0.5 * f["nsteady"]
          and f["pitchcv"] < 0.03)
    verdict("P3", ok, "steady frames %d >= %d; speed CV %.4f < 0.02; yaw %.1f deg/s in [%g,%g], CV %.4f < 0.03; "
            "pitch range %.1f >= %g, rate n %d >= half, CV %.4f < 0.03" % (
                f["nsteady"], MIN_STEADY, f["speedcv"], f["yawmean"], YAW_RATE[0], YAW_RATE[1],
                f["yawcv"], f["pitchrange"], PITCH_RANGE, f["npitch"], f["pitchcv"]))


def v_p4(f, whole):
    snaps = [c for c in f["clusters"] if c["dist"] > 64]
    if snaps:
        verdict("P4", all(c["frames"] == 1 for c in snaps),
                "%d teleport(s) > 64 u, frames each: %s (want 1; the control smears)" % (
                    len(snaps), [c["frames"] for c in snaps]))
    elif whole:
        verdict("P4", False, "no teleport > 64 u in the run (the kill at S+60)")
    else:
        na("P4", "no teleport > 64 u in this window")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    t0, t1, tick, arm, p1rate = -1e9, 1e9, None, "base", None
    i = 2
    while i < len(argv):
        if argv[i] == "--from":
            t0 = float(argv[i + 1])
        elif argv[i] == "--to":
            t1 = float(argv[i + 1])
        elif argv[i] == "--tick":
            tick = float(argv[i + 1])
        elif argv[i] == "--arm":
            arm = argv[i + 1]
        elif argv[i] == "--p1rate":
            p1rate = float(argv[i + 1])
        i += 2
    if arm not in ARMS:
        print("unknown --arm %s: %s" % (arm, " ".join(ARMS)))
        return 2
    whole = t0 == -1e9 and t1 == 1e9
    fr, rx, ticks, rw = parse(argv[1], t0, t1)
    logtick = ticks[-1] if ticks else None
    if tick is None:
        tick = logtick if logtick else REG_TICK
    print("== arm %s, tick %g (%s)" % (arm, tick, "from body_stats" if logtick else "not in the log"))
    if ticks and min(ticks) != max(ticks):
        print("  body_stats ticks disagree: %s" % sorted(set(ticks)))
    a = arrivals(rx)
    f = frames_report(fr, rx, tick)

    print("== verdicts (pre-registered in cfg/test/p383view.cfg)")
    verdict("ARM", logtick is not None and abs(logtick - REG_TICK) < 1e-6,
            "log tick %s, registered %g (a bhop_ map without sv_gamemode none runs 0.01)"
            % (logtick, REG_TICK))
    name, mode, band = ARMS[arm]

    if arm == "csqc":
        verdict("P7", rw == 0 and a.get("spec", 0) > 0,
                "%d CSQC over/underread line(s) (want 0), %d SPEC sample(s) (want > 0); "
                "grep the server log for Write*: value" % (rw, a.get("spec", 0)))
        return 0
    if not a or not f:
        verdict(name, False, "no trace")
        return 1

    if arm.startswith("ctl"):
        lo, hi = CTL_RATE[arm]
        rate, nsec = engine_moving_rate(fr, rx) if a["engine"] else (a.get("steadyrate", 0), 0)
        verdict("CTL", a["engine"] and f["engine"] and nsec > 0 and lo <= rate <= hi and f["pitchrange"] < 0.5,
                "engine fallback %s, %.2f deltas/s over %d moving s in [%g,%g], pitch range %.2f < 0.5 "
                "(must PASS)" % (a["engine"], rate, nsec, lo, hi, f["pitchrange"]))
        verdict(name, band[0] <= rate <= band[1],
                "%.2f /s in the stream's [%g,%g] (must FAIL at 66.67; at 15 the rates coincide)"
                % (rate, band[0], band[1]))
        v_p3(f)
        v_p4(f, whole)
        print("  (control: P3 and P4 must FAIL)")
        return 0

    if a["engine"]:
        verdict(name, False, "engine fallback: the stream is off (lobby_av_stream 0?)")
        return 1

    if arm == "loss":
        if p1rate is None:
            na("P9", "pass --p1rate <P1's moving rate>")
        elif "speedcv" not in f:
            verdict("P9", False, "no steady frames")
        else:
            verdict("P9", 0.90 * p1rate <= a["steadyrate"] <= 1.00 * p1rate
                    and f["starved"] < 0.03 and f["speedcv"] < 0.04,
                    "moving rate %.2f in [0.90,1.00] x %.2f, starved %.2f%% < 3%%, speed CV %.4f < 0.04"
                    % (a["steadyrate"], p1rate, 100 * f["starved"], f["speedcv"]))
        return 0

    ok = a["mode"] == mode and band[0] <= a["steadyrate"] <= band[1] and a["steadyn"] > 0
    text = "gap mode %d (want %d), moving rate %.2f in [%g,%g] over %d s" % (
        a["mode"], mode, a["steadyrate"], band[0], band[1], a["steadyn"])
    if arm == "base":
        ok = ok and 1.0 <= a["gapmean"] <= 1.15
        text += ", mean gap %.3f in [1.00,1.15]" % a["gapmean"]
    verdict(name, ok, text)
    if arm != "base":
        return 0

    v_p3(f)
    if "speedcv" in f:
        verdict("P3b", 0.95 <= f.get("rclk_lo", 0) and f.get("rclk_hi", 9) <= 1.05
                and f["starved"] < 0.01 and f["steady_reseeds"] == 0 and f["clockbad"] == 0,
                "render clock p1..p99 %.3f..%.3f in [0.95,1.05], starved %.2f%% < 1%%, "
                "steady reseeds %d, underrun/jump frames %d" % (
                    f.get("rclk_lo", 0), f.get("rclk_hi", 0), 100 * f["starved"],
                    f["steady_reseeds"], f["clockbad"]))
    v_p4(f, whole)

    resumed = [r for r in f["p5"] if r[3] is not None]
    for r in resumed:
        verdict("P5", r[3] == 0, "rest %.3f: %d frame(s) moved (> 0.5 u or 0.5 deg) before "
                "the resume tick - 1" % (r[0], r[3]))
    for r in f["p5"]:
        if r[1] >= 5.0:
            verdict("P5k", KA_RATE[0] <= r[2] <= KA_RATE[1], "rest %.3f (%.1f s): %.2f still samples/s "
                    "in [%g,%g]" % (r[0], r[1], r[2], KA_RATE[0], KA_RATE[1]))
    if not resumed:
        (verdict("P5", False, "no rest with a resume in the run") if whole
         else na("P5", "no rest with a resume in this window"))

    # The drift sums from the last unstarved frame, so one frame of travel before
    # the newest sample rides on top of cl_body_extrap's 0.03 s.
    drift = 260 * 0.03 + 1.5 * f["medstep"]
    for s in f["stalls"]:
        verdict("P6", s[2] <= drift and s[3] <= 0.07 and s[4] < 0.02 and s[5] > 0,
                "reseed %.3f: drift %.2f <= 7.8 + 1.5 frames = %.2f u, hold %.3f <= D + 1 frame, "
                "CV 1..2 s after %.4f < 0.02" % (s[0], s[2], drift, s[3], s[4]))
    if whole:
        want = 1 + len(f["helds"])      # the owner stall, and each unhold (P12's run)
        verdict("P6n", len(f["stalls"]) == want and f["reseeds"] == want,
                "%d stall reseed(s), %d reseed(s) in all (want %d: the stall + %d unhold)"
                % (len(f["stalls"]), f["reseeds"], want, len(f["helds"])))
    elif not f["stalls"]:
        na("P6", "no stall in this window")

    if f.get("rawstill") is not None:
        verdict("C1", f["rawstill"] >= 0.25 and f["still"] < 0.01,
                "raw frames still %.1f%% >= 25%% (must fail smoothness); interpolated %.2f%% < 1%%"
                % (100 * f["rawstill"], 100 * f["still"]))
    elif whole:
        verdict("C1", False, "no cl_body_raw frames in the run")

    for h in f["helds"]:
        verdict("P12", h[2] <= max(1.5 * h[3], 1.0),
                "held edge %.3f: largest step %.2f u <= 1.5 x median step (control: ~0.03 x speed)"
                % (h[0], h[2]))

    spec, natt, noatt, tleft = f["keys"]
    if natt:
        verdict("KEY", noatt == 0 and tleft == 0,
                "%d wire-attack frame(s): %d without FSI_ATTACK, %d with FSI_TLEFT (want 0, 0)"
                % (natt, noatt, tleft))
    elif spec or whole:
        verdict("KEY", False, "%d SPEC frame(s) and no wire-attack frame" % spec)
    else:
        na("KEY", "no SPEC frames in this window")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
