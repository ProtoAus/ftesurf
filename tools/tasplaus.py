#!/usr/bin/env python3
"""tasplaus -- does an uploaded run make physical sense, whatever tool made it?

For user-uploaded TAS records (Lex, 20 Nov 2026: "as long as the run makes sense
physics wise, it's fine"). It reads only the per-tick SAMPLES of a FTESURF-REC
file (position, velocity), so it works on our own recordings, KSF/Momentum
imports and files written by a fork or a bot. It is not pm_verify: nothing is
re-simulated and collision is not checked. Exact replays stay sweep.py's job.

Verdicts:
  PASS  every checked tick obeys the bounds below and the zones are visited.
  HOLD  something a map feature could explain (push, booster, a teleport that
        does not land in a zone) or the checker could not see (no zones, a
        sample gap): a person looks. Never an accusation.
  FAIL  the file cannot be a run: no samples, time running backwards, samples
        that stop before the finish, speed past sv_maxvelocity.
Native recordings with saves, loads, warps or pauses are HOLD here: those are
teleports by design and only the exact verifier (pm_verify) can judge them.
Not known to it: collision (a wall clip or an invisible ledge at legal speed passes),
a map's push/booster volumes and stage-end teleporters (both HOLD), stage legs (HOLD).
20 Nov, our own 111 recordings with samples: the energy HOLDs sit on
surf_classics/classics2/sodacity/mesa (boosters), none on push-free maps.
P1639 review: one header reading (a key twice or a stray line break is FAIL); samples
must be whole ticks apart and printed to 0.01; jumps start on the ground; contact ticks
move no further than their velocity change explains; air control's direction is checked;
teleports land on the ridden stage's start without gaining speed; the start speed is
capped in 3D, and where a course has no start limit the recording must open slow.

Bounds, measured on 117 KSF + Momentum replays of surf_sandtrap2 bonus 4
(20 Nov 2026, 2-6 decimal files):
  free flight / ramps  d(|v|^2 + 2 g z) per tick  max 921; theory 900 = 30^2, the
                       air-accel cap (|v'|^2 = |v|^2 + 900 - (v.w)^2).
  ground               d|v_h| per tick             p99 19.5 (sv_accelerate 5 x 250 x 0.015)
  jump                 vz 0 -> 289.99 (283.99 on a half-gravity tick)
  position             |do - v_avg dt| per tick    max 9.6 outside teleports, 1.42 in free flight
  gravity              vz never fell exactly 2+ ticks of gravity in one tick (0 of 35k)
  clock                median |do_h| / (|v_h| dt) over moving samples: 1.0000-1.0009 on 228
                       files (imports, our runs/PBs/segmented/shadows); a 1% faster clock is 1.010
  duck in the air      origin z moves +-8.5 with velocity unchanged (2 g 8.5 = 13600 of
                       "energy"), so a shift is taken out before the energy test and the
                       shifts must cancel (running sum within +-19).
  air turn             v'.(v'-v) - 30|v'-v| over one free tick: max 12.8 (tolerance 30 + precision)
  ground d(|v_h|^2)    max 3269 a tick (cap 10000)
  contact residual     |do - v_avg dt| - |dv| dt: max ~2 u after the start
  start                |v| at t=0 max 406; finish within 16 u (the hull) of the end zone, all 117
A 1% speedhack at 1000 u/s is d(v^2) ~ 20000 a tick; a skipped tick is ~15 u.
"""

import argparse
import io
import json
import math
import re
import sys

F32_MAX = 3.4028234663852886e38


def is_sample(tok):
    """reccheck.is_sample: a sample starts with a digit (padding samples with '-')."""
    return bool(tok) and (tok[0].isdigit() or (tok[0] == "-" and len(tok) > 1 and tok[1].isdigit()))


def file_float(tok):
    """reccheck.file_float without its float32 rounding detail. Inlined so the upload
    service (surfd/tasupd.py) ships this file alone; reccheck imports heldmeta."""
    x = float(tok)
    if not math.isfinite(x) or abs(x) > F32_MAX:
        raise ValueError("non-finite or out-of-range number")
    return x

GRAVITY = 800.0
AIR_DV2 = 900.0          # 30 u/s air cap, squared
GROUND_DV = 20.0         # ground accel per tick, u/s (measured p99 19.5)
JUMP_VZ = (250.0, 302.0)
POS_TOL = 12.0           # u per tick outside teleports and duck shifts
FREE_TOL = 3.0           # u per tick in free flight (vz fell exactly g dt): measured max 1.42 of 35k
DUCK_SHIFT = (7.5, 19.0) # |z| an air duck/unduck moves the origin: 8.5 measured (CS:S); 18 = a full hull
DUCK_NET = 19.0          # the shifts must undo each other: running sum stays inside +-this
MAX_GAP = 8              # ticks between samples before the checker says it cannot see
ZONE_PAD = 48.0          # u around a checkpoint/stage box, plus one tick of travel
EDGE_PAD = 16.0          # u at the start and the end: the hull's half-width, plus one tick of travel
START_CAP = 380.0        # horizontal u/s at t=0 under limitStartGroundSpeed (measured max 306)
START_CAP_3D = 480.0     # |v| at t=0 (measured max 406); and at the first sample where no start limit exists
GROUND_DV2 = 10000.0     # d(|v_h|^2) a ground tick: 2 A W - A^2, A = 19.5, W = 260 (measured max 3269)
MIN_DECIMALS = 2         # every position/velocity printed to 0.01 or finer (all 281 real files)
DEFAULT_MAXVEL = 3500.0
WORLD = 131072.0         # |coordinate|: Source's +-16384 map limit, eight times over
MAX_TICKS = 100000000    # surfd.MAX_TICKS
AIR_CAP = 30.0           # sv_air_max_wishspeed (CS:S, Momentum)
TURN_TOL = 30.0          # u^2/s^2 over v'.(v'-v) - 30|v'-v|; see the turn test in check()
CLOCK_RATIO = (0.9985, 1.002)
# Native records that move the body or the clock outside the movement code.
NATIVE_STATE = ("resume", "session", "pause", "hold", "warp", "restart", "takeover")
PASS, HOLD, FAIL = "PASS", "HOLD", "FAIL"


# A .rec breaks lines on \n (CRLF allowed); splitlines() would also break on these, so a header key
# could hide inside a line one reader sees and another does not (review of P1639). None occurs in 281
# real files (164 of ours, 117 imports), nor does a repeated header key.
ODD_BREAK = re.compile('[\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]|\r(?!\n)')


class Run:
    def __init__(self):
        self.hdr = {}
        self.dups = set()    # header keys given twice: FAIL, readers would disagree on which counts
        self.has_body = False   # a `begin` line was seen
        self.odd_breaks = False
        self.samples = []    # (t, o[3], v[3])
        self.end = None
        self.decimals = 99   # fewest decimals of any position/velocity number (exponent form counts 0)
        self.records = set()
        self.yaw = []        # view yaw per sample (runcompare reads it)


def read(path=None, text=None, header_only=False):
    """One reader for the header and the samples (surfd/tasupd.py reads the header through it too)."""
    run = Run()
    if text is None:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    run.odd_breaks = bool(ODD_BREAK.search(text))
    body = False
    for line in io.StringIO(text):   # newline="\n": splits on \n only, like the game
        tok = line.split()
        if not tok:
            continue
        if not body:
            if tok[0] == "begin":
                body = run.has_body = True
                if header_only:
                    break
            else:
                if tok[0] in run.hdr:
                    run.dups.add(tok[0])
                run.hdr[tok[0]] = " ".join(tok[1:])
            continue
        if tok[0] == "end":
            try:
                run.end = int(tok[1])
            except (IndexError, ValueError):
                run.end = None
            continue
        if not is_sample(tok[0]):
            run.records.add(tok[0])
            continue
        if len(tok) < 14:
            continue
        try:
            nums = [file_float(x) for x in tok[:7]]
        except ValueError:
            continue
        for x in tok[1:7]:
            dot = x.find(".")
            run.decimals = min(run.decimals, len(x) - dot - 1 if dot >= 0 and x[dot + 1:].isdigit() else 0)
        run.samples.append((nums[0], tuple(nums[1:4]), tuple(nums[4:7])))
        try:
            run.yaw.append(file_float(tok[8]))
        except ValueError:
            run.yaw.append(0.0)
    return run


def _zone_regions(zones, track):
    """[(label, region)] in visiting order for one track, end last; None if absent."""
    if not zones:
        return None
    tr = zones.get("tracks", {})
    if track == 0:
        t = tr.get("main")
    else:
        b = tr.get("bonuses") or []
        t = b[track - 1] if 0 < track <= len(b) else None
    if not t:
        return None
    z = t.get("zones", {})
    seq = []
    for si, seg in enumerate(z.get("segments", [])):
        for ci, cp in enumerate(seg.get("checkpoints", [])):
            label = "start" if (si, ci) == (0, 0) else (
                f"stage {si + 1}" if ci == 0 else f"checkpoint {si + 1}.{ci}")
            seq.append((label, cp.get("regions", [])))
    seq.append(("end", z.get("end", {}).get("regions", [])))
    limit = bool(z.get("segments") and z["segments"][0].get("limitStartGroundSpeed"))
    return seq, limit


def _inside(o, region, pad):
    pts = region.get("points") or []
    if len(pts) < 3:
        return False
    bottom = float(region.get("bottom", -1e9))
    if not (bottom - pad <= o[2] <= bottom + float(region.get("height", 1e9)) + pad):
        return False
    x, y = o[0], o[1]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if pad > 0 and min(xs) - pad <= x <= max(xs) + pad and min(ys) - pad <= y <= max(ys) + pad:
        # padded test: inside the polygon, or within pad of one of its edges
        if _in_poly(x, y, pts):
            return True
        return any(_seg_dist(x, y, pts[i], pts[(i + 1) % len(pts)]) <= pad for i in range(len(pts)))
    return _in_poly(x, y, pts)


def _in_poly(x, y, pts):
    c = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def _seg_dist(x, y, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1e-9
    u = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - (ax + u * dx), y - (ay + u * dy))


def hdr_int(hdr, key, default=0):
    """The header's first word as an int, or `default` (absent, empty or not a number)."""
    try:
        return int(hdr.get(key, "").split()[0])
    except (ValueError, IndexError):
        return default


def _bbox(regions, pad):
    pts = [p for r in regions for p in (r.get("points") or [])]
    if not pts:
        return None
    lo = min(float(r.get("bottom", -1e9)) for r in regions) - pad
    hi = max(float(r.get("bottom", -1e9)) + float(r.get("height", 1e9)) for r in regions) + pad
    return (min(p[0] for p in pts) - pad, max(p[0] for p in pts) + pad,
            min(p[1] for p in pts) - pad, max(p[1] for p in pts) + pad, lo, hi)


def _in_bbox(o, b):
    return b is not None and b[0] <= o[0] <= b[1] and b[2] <= o[1] <= b[3] and b[4] <= o[2] <= b[5]


def check(run, zones=None, maxvel=None):
    out = {"verdict": PASS, "reasons": [], "stats": {}}

    def note(level, t, what):
        out["reasons"].append({"level": level, "t": round(t, 4) if t is not None else None, "what": what})
        if level == FAIL or (level == HOLD and out["verdict"] == PASS):
            out["verdict"] = level

    rate = 0.0
    for k in ("movetickrate", "tickrate"):
        try:
            rate = float(run.hdr.get(k, "") or 0)
        except ValueError:
            rate = 0.0
        if not math.isfinite(rate):   # "nan" passes every comparison below
            rate = 0.0
        if rate > 0:
            break
    s = run.samples
    if run.dups or run.odd_breaks:
        note(FAIL, None, "header repeats " + ", ".join(sorted(run.dups)) if run.dups
             else "line breaks other than newline: readers would disagree about the header")
        return out
    if not s or len(s) < 3:
        note(FAIL, None, "no samples")
        return out
    if rate <= 0 or rate > 0.1:
        note(FAIL, None, f"no usable tickrate ({rate})")
        return out
    if run.end is None or run.end <= 0 or run.end > MAX_TICKS:
        note(FAIL, None, "no finish (end line)")
        return out
    if any(abs(c) > WORLD for _, o, _ in s for c in o) or any(abs(c) > 1e5 for _, _, v in s for c in v):
        note(FAIL, None, "a sample is outside the world")   # also keeps x ** 2 below finite
        return out
    fin = run.end * rate
    track, startseg = hdr_int(run.hdr, "track"), hdr_int(run.hdr, "startseg")
    if startseg:
        note(HOLD, None, f"stage leg (startseg {startseg}): this checker covers whole courses")
        zones = None
    zr = _zone_regions(zones, track)
    seq, limit_start = zr if zr else (None, False)
    if maxvel is None:
        maxvel = float((zones or {}).get("maxVelocity") or DEFAULT_MAXVEL)

    if run.decimals < MIN_DECIMALS:
        # The tolerances follow the print precision: "1234e-3" or "12" would widen them past the caps.
        note(HOLD, None, f"numbers printed with {run.decimals} decimals: the bounds need {MIN_DECIMALS} or more")
    q = 0.5 * 10.0 ** (-max(run.decimals, MIN_DECIMALS))
    # Teleport destinations: stage starts, numbered (the main start is stage 1 and a teleport into it
    # is a reset, into the end a skip). Back to the stage being ridden is a fall; on to the next one
    # is the map's stage-end teleporter, which the checker cannot see, so a person looks.
    stages = [(int(lab.split()[1]), regs, _bbox(regs, ZONE_PAD)) for lab, regs in (seq or []) if lab.startswith("stage ")]

    # Our own recordings sample once a packet, so dt need not be whole ticks; bounds scale with dt.
    for (t0, _, _), (t1, _, _) in zip(s, s[1:]):
        if t1 <= t0:
            note(FAIL, t1, "sample clock runs backwards")
            return out
    native = sorted(run.records.intersection(NATIVE_STATE))
    if native:
        note(HOLD, None, "has " + ", ".join(native) + " records (saves/loads/warps): needs the exact verifier")
    if s[-1][0] < fin - 2 * rate:
        note(FAIL, s[-1][0], f"samples stop at {s[-1][0]:.3f}s before the {fin:.3f}s finish")
        return out
    if s[0][0] > 0:
        note(FAIL, s[0][0], "no sample at or before the start (t=0)")
        return out

    def resid(a, b):
        dt = b[0] - a[0]
        return [b[1][i] - a[1][i] - (a[2][i] + b[2][i]) * 0.5 * dt for i in range(3)]

    def disc(a, b):
        return math.sqrt(sum(x * x for x in resid(a, b)))

    # Window: from the last jump in position at or before t=0 (the teleport into the start).
    i0 = 0
    for i in range(1, len(s)):
        if s[i][0] > 0:
            break
        k = (s[i][0] - s[i - 1][0]) / rate
        if disc(s[i - 1], s[i]) > POS_TOL * max(1, k):
            i0 = i
    win = [x for x in s[i0:] if x[0] <= fin + rate + 1e-6]
    worst_air = worst_ground = worst_turn = 0.0
    nchk = njump = ntele = nduck = offtick = 0
    duck_net = 0.0
    reached = [1, 0]   # highest stage start visited, samples scanned

    def stage_reached(upto):
        for x in win[reached[1]:upto + 1]:
            for n, regs, bb in stages:
                if n > reached[0] and _in_bbox(x[1], bb) and any(_inside(x[1], r, ZONE_PAD) for r in regs):
                    reached[0] = n
        reached[1] = max(reached[1], upto + 1)
        return reached[0]

    for i, (a, b) in enumerate(zip(win, win[1:])):
        t = a[0]
        k = (b[0] - a[0]) / rate
        aligned = abs(k - round(k)) < 0.02
        kk = max(1, math.ceil(k - 0.02))   # mover steps: the air cap and the tolerances are per step
        if not aligned or k < 0.98:
            offtick += 1   # each pair gets a whole step's allowance: ten samples a tick would get ten
        for c in range(3):
            if abs(b[2][c]) > maxvel + GRAVITY * rate + 0.5:   # half gravity lands after the clamp
                note(FAIL, b[0], f"velocity {b[2][c]:.1f} past sv_maxvelocity {maxvel:.0f}")
                return out
        if k > MAX_GAP:
            note(HOLD, t, f"{k}-tick gap between samples: cannot check it")
            continue
        nchk += 1
        r = resid(a, b)
        shift = 0.0
        if math.hypot(r[0], r[1]) < 2.0 * kk and DUCK_SHIFT[0] <= abs(r[2]) <= DUCK_SHIFT[1]:
            shift = r[2]
            duck_net += shift
            nduck += 1
            if abs(duck_net) > DUCK_NET:
                note(HOLD, t, f"duck shifts add up to {duck_net:+.1f} u of height")
                duck_net = max(-DUCK_NET, min(DUCK_NET, duck_net))
        d = math.sqrt(r[0] ** 2 + r[1] ** 2 + (r[2] - shift) ** 2)
        dvz = b[2][2] - a[2][2]
        free = abs(dvz + GRAVITY * rate * k) < 0.05
        if not free and aligned:
            m = round(-dvz / (GRAVITY * rate))
            if 2 <= m <= MAX_GAP and m != round(k) and abs(dvz + GRAVITY * rate * m) < 0.05:
                note(HOLD, t, f"vertical speed fell exactly {m} ticks of gravity in {round(k)}: missing or edited ticks")
        if free and FREE_TOL * kk < d <= POS_TOL * kk:
            note(HOLD, t, f"free-flight position off by {d:.1f} u in {k:.2g} tick(s): missing or edited ticks")
        elif not free and t >= 0 and d <= POS_TOL * kk:
            # Contact (a ramp clip) moves the body with a velocity between the two samples', so the
            # residual is bounded by the change: measured excess <= 2 u after the start (t < 0: one
            # import's start zone zeroes velocity but not motion, 3.9 u a tick).
            dv = math.sqrt(sum((b[2][c] - a[2][c]) ** 2 for c in range(3)))
            if d > dv * (b[0] - a[0]) + FREE_TOL * kk:
                note(HOLD, t, f"moves {d:.1f} u off its velocity in {k:.2g} tick(s), more than the velocity change explains")
        va, vb = a[2], b[2]
        ha, hb = math.hypot(va[0], va[1]), math.hypot(vb[0], vb[1])
        if d > POS_TOL * kk:
            ntele += 1
            dest = next((n for n, regs, bb in stages
                         if _in_bbox(b[1], bb) and any(_inside(b[1], r, ZONE_PAD) for r in regs)), None)
            # A teleport keeps or zeroes velocity (a yaw turn at most): it never turns falling into running.
            gained = max(hb - ha, abs(vb[2]) - abs(va[2]))
            if dest is not None and dest == stage_reached(i) and gained <= 40.0 * kk:
                continue   # a fall back to the start of the stage being ridden
            note(HOLD, t, f"position jumps {d:.0f} u" + (
                " (no zones to check against)" if not seq else
                ", not onto a stage start" if dest is None else
                f" onto stage {dest}'s start, gaining {gained:.0f} u/s" if dest == reached[0] else
                f" onto stage {dest}'s start from stage {reached[0]}: a stage-end teleporter? (not known to the checker)"))
            continue
        jump = abs(va[2]) < 0.01 and JUMP_VZ[0] <= vb[2] <= JUMP_VZ[1]   # from the ground: all 118 real ones
        ground = abs(va[2]) < 0.01 and abs(vb[2]) < 0.01
        if jump or ground:
            njump += jump
            gain = hb - ha
            lim = GROUND_DV * kk + 4 * q + 0.5
            worst_ground = max(worst_ground, gain / (GROUND_DV * kk))
            if gain > lim:
                note(HOLD, t, f"ground speed +{gain:.1f} u/s in {k:.2g} tick(s) (cap {GROUND_DV * kk:.0f})")
            elif hb * hb - ha * ha > GROUND_DV2 * kk + 4 * math.sqrt(2) * hb * q + 1.0:
                # Ground accel only adds speed below wishspeed: past it a tick adds at most 2AW - A^2 to v^2.
                note(HOLD, t, f"ground speed {ha:.0f} -> {hb:.0f} u/s in {k:.2g} tick(s): accelerating past run speed")
            continue
        ea = va[0] ** 2 + va[1] ** 2 + va[2] ** 2 + 2 * GRAVITY * a[1][2]
        eb = vb[0] ** 2 + vb[1] ** 2 + vb[2] ** 2 + 2 * GRAVITY * (b[1][2] - shift)
        spd = max(math.sqrt(ea - 2 * GRAVITY * a[1][2]), 1.0)
        tol = 4 * math.sqrt(3) * spd * q + 4 * GRAVITY * q + 30.0
        gain = eb - ea
        worst_air = max(worst_air, gain / (AIR_DV2 * kk))
        if gain > AIR_DV2 * kk + tol:
            note(HOLD, t, f"energy +{gain:.0f} in {k:.2g} tick(s), air cap {AIR_DV2 * kk:.0f}"
                 f" ({gain / (AIR_DV2 * kk):.1f}x): push, booster or speed change")
        elif free and aligned and round(k) == 1:
            # Air control adds a*w with w horizontal and v'.w <= 30, so v'.(v' - v) <= 30 |v' - v|
            # whatever sv_airaccelerate is: a constant-speed turn moves v by at most 60 u/s a tick.
            dvx, dvy = vb[0] - va[0], vb[1] - va[1]
            dh = math.hypot(dvx, dvy)
            over = vb[0] * dvx + vb[1] * dvy - AIR_CAP * dh
            worst_turn = max(worst_turn, over)
            if over > TURN_TOL + 6 * math.sqrt(2) * max(ha, hb) * q:
                turn = math.degrees(abs(math.atan2(va[0] * vb[1] - va[1] * vb[0], va[0] * vb[0] + va[1] * vb[1])))
                note(HOLD, t, f"{ha:.0f} -> {hb:.0f} u/s turning {turn:.1f} deg in one tick: air control cannot"
                     " change velocity like that")

    # The clock against the motion: distance over speed x claimed time, median of moving samples.
    ratios = []
    for a, b in zip(win, win[1:]):
        dt = b[0] - a[0]
        vh = math.hypot((a[2][0] + b[2][0]) * 0.5, (a[2][1] + b[2][1]) * 0.5)
        if a[0] >= 0 and vh >= 200 and dt / rate <= MAX_GAP:
            ratios.append(math.hypot(b[1][0] - a[1][0], b[1][1] - a[1][1]) / (vh * dt))
    clock = sorted(ratios)[len(ratios) // 2] if len(ratios) >= 20 else None
    if clock is None:
        note(HOLD, None, "too little movement to check the clock")
    elif not CLOCK_RATIO[0] <= clock <= CLOCK_RATIO[1]:
        note(HOLD, None, f"the body moves {clock:.4f}x what its speed and clock allow: clock edited?")
    if offtick > 2 + len(win) // 500:   # packet timing: 1-2 in 3 of 164 of our own recordings
        note(HOLD, None, f"{offtick} sample steps are not whole ticks: the per-tick bounds cannot be applied"
             " (one sample a tick, please; native recordings need the exact verifier)")

    # Zones: start, every checkpoint in order, finish.
    t0s = min(s, key=lambda x: abs(x[0]))
    h0 = math.hypot(t0s[2][0], t0s[2][1])
    if seq is None:
        note(HOLD, None, "no zones for this map/track: start and finish not checked")
    else:
        travel = lambda x: math.sqrt(sum(c * c for c in x[2])) * rate  # noqa: E731
        pad = lambda x: ZONE_PAD + travel(x)  # noqa: E731
        start_regs = seq[0][1]
        if not any(_inside(t0s[1], r, EDGE_PAD + travel(t0s)) for r in start_regs):
            note(HOLD, 0.0, "the clock starts outside the start zone")
        v0 = math.sqrt(sum(c * c for c in t0s[2]))
        if limit_start and h0 > START_CAP:
            note(HOLD, 0.0, f"leaves the start at {h0:.0f} u/s (cap {START_CAP:.0f})")
        elif limit_start and v0 > START_CAP_3D:
            note(HOLD, 0.0, f"leaves the start at {v0:.0f} u/s counting vertical speed (cap {START_CAP_3D:.0f})")
        first = math.sqrt(sum(c * c for c in win[0][2]))
        if not limit_start and first > START_CAP_3D:
            # Nothing caps the start here, so the speed the recording opens with would be free.
            note(HOLD, win[0][0], f"opens already moving at {first:.0f} u/s on a course with no start speed limit")
        j = 0
        for lab, regs in seq[1:]:
            hit = None
            for jj in range(j, len(win)):
                p = EDGE_PAD if lab == "end" else pad(win[jj])   # the hull's half-width: all 117 real finishes
                if any(_inside(win[jj][1], r, p) for r in regs):
                    hit = jj
                    break
            if hit is None:
                note(HOLD, None, f"never reaches {lab}")
                break
            j = hit
        else:
            if win[j][0] < fin - 0.25:
                note(HOLD, win[j][0], f"reaches the end zone at {win[j][0]:.3f}s, finish says {fin:.3f}s")
    out["stats"] = {"finish": round(fin, 4), "ticks_checked": nchk, "jumps": njump,
                    "teleports": ntele, "duck_shifts": nduck, "clock_ratio": round(clock, 5) if clock else None, "start_speed": round(h0, 1),
                    "worst_air_ratio": round(worst_air, 3), "worst_ground_ratio": round(worst_ground, 3),
                    "worst_turn_excess": round(worst_turn, 1),
                    "decimals": run.decimals, "window_from": round(win[0][0], 4) if win else None}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rec", nargs="+")
    ap.add_argument("--zones", help="zone JSON (maps/zones/.../<map>.json)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    zones = None
    if a.zones:
        with open(a.zones, encoding="utf-8") as f:
            zones = json.load(f)
    worst = 0
    for p in a.rec:
        r = check(read(p), zones)
        worst = max(worst, (PASS, HOLD, FAIL).index(r["verdict"]))
        if a.json:
            print(json.dumps({"file": p, **r}))
        else:
            st = r["stats"]
            print(f"{r['verdict']} {p}  finish {st.get('finish')}s  air {st.get('worst_air_ratio')}x"
                  f"  ground {st.get('worst_ground_ratio')}x  teleports {st.get('teleports')}")
            for x in r["reasons"]:
                print(f"   {x['level']} t={x['t']}: {x['what']}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
