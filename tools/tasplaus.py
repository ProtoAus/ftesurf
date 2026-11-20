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
        that stop before the finish, a header readers would disagree about.
        (Speed past sv_maxvelocity is HOLD: the cap given may be lower than the map's.)
Native recordings with saves, loads, warps or pauses are HOLD here: those are
teleports by design and only the exact verifier (pm_verify) can judge them.
Not known to it: collision. A path that ignores the map's walls at legal speeds passes
(review 2: a made-up slide from the start box, 5.73 s against the 7.83 record), so the upload
service holds any time faster than the course's record. Also unknown: push/booster volumes and
stage-end teleporters (both HOLD), stage legs (HOLD), sv_accelerate other than 5 (ahop's 10 HOLDs
on the ground rule).
20 Nov, our own 111 recordings with samples: the energy HOLDs sit on
surf_classics/classics2/sodacity/mesa (boosters), none on push-free maps.
P1640 review: one header reading (a key twice or a stray line break is FAIL); samples
must be whole ticks apart and printed to 0.01; jumps start on the ground; contact ticks
move no further than their velocity change explains; air control's direction is checked;
teleports land on the ridden stage's start without gaining speed; the start speed is
capped in 3D, and where a course has no start limit the recording must open slow.
Review 2: ground ticks lose friction's share (4 x max(v, 100) x dt) before accelerating;
a jump needs the sample before it not rising; unexplained horizontal travel is summed over
each second (in the air against the post-accel velocity the mover uses); a turn air control
cannot make passes only if it costs the speed a wall or ramp would (|v'| <= |v| cos + 0.1|v|
+ air control), on contact ticks too; the clock starts within 128 u of the start box floor.
Ground ticks may step up or down 18 u; checkpoints count from t=0; the precision is the
most decimals any number shows (a shortest-form printer writes 0.0 beside 123.456789).
Review 3: a jump needs vz 0 reached by a clip (landing, even rising: the engine lands at vz <= 140)
or standing, not by gravity alone; a landing on a slope may keep up to the 3D speed (slope fix);
the precision is the coarser of positions and velocities; steps of 2+ ticks count with off-tick
ones and their turns are bounded by k x 2 asin(30/|v|) unless a wall or ramp took the speed.
Review 4: the engine also lands at the next tick's start and jumps from vz up to 140 (riding up a
slope); the jump tick is held to air control's |v'|^2 <= |v|^2 + 900, not a flat +30; a 6-digit
printer's coarser deep z widens only the height term; at most one 2+ tick step after t=0 (a lost
packet: 2 in 301 honest files), moving at most half its velocity change off the mean (3.04 of 3.15
measured) -- one such step can still hide ~2 ticks, ~0.03 s; the off-tick allowance counts samples
from t=0. Unknown too: trigger_gravity (low gravity reads as push/booster).
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
  ground d(|v_h|^2)    max 3269 a tick (cap 10000); after friction max 9764 of 9760 (12937 ticks,
                       all 301 honest files: ours, online, imports)
  jumps                476 real ones: vz 0 before, the sample before that never rising
  drift                one-second sum of unexplained horizontal travel: max 0.3 on the corpus
                       (cap 24); past it only on booster runs already held (9 of 301)
  start height         4.5-59.5 u above the start box floor here, 73.8 on surf_whoknows2
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
FRICTION, STOPSPEED = 4.0, 75.0    # cfg/default.cfg sv_friction / sv_stopspeed (mode_ahop's 100 only takes more)
OPEN_CAP = 1500.0        # |v| a recording may open with on a course with no start limit (measured 1209: falling in)
LAND_VZ = 140.5          # the engine lands rising up to vz 140 (pm_source.c:2350)
STEP = 18.0              # u a ground move steps up or down (sv_stepheight)
DRIFT_SECOND = 24.0      # u: unexplained horizontal travel summed over 66 ticks (corpus max 0.3; check())
START_HEIGHT = 128.0     # u above the start box floor at t=0 (measured max 73.8, a 528 u box)
CLIP_SLACK = 0.1         # a wall or ramp turn keeps at most |v| cos(turn) + this |v| (+ air control)
REASON_KEEP = 200        # reasons listed per run; the rest only counted ("unlisted"): a crafted file gives ~2 a tick
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
# could hide inside a line one reader sees and another does not (review of P1640). None occurs in 281
# real files (164 of ours, 117 imports), nor does a repeated header key.
# str.split() also splits on the Unicode spaces here, so `track\xa04` would read as track 4 to us and
# not to the game (QC tokenizes on ASCII): refused the same way.
ODD_BREAK = re.compile('[\x0b\x0c\x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]|\r(?!\n)')


class Run:
    def __init__(self):
        self.hdr = {}
        self.dups = set()    # header keys given twice: FAIL, readers would disagree on which counts
        self.has_body = False   # a `begin` line was seen
        self.odd_breaks = False
        self.samples = []    # (t, o[3], v[3])
        self.end = None
        self.decimals = 0    # the coarser of positions and velocities, each its most decimals (at most 6)
        self._dec = [0, 0]
        # Rounding of a 6-significant-digit printer (%g): z at -15123.4 is 0.05 coarse beside x, y at
        # 0.01. Per group, the coarsest such number (6+ significant digits, fewer decimals).
        self.sig_q = [0.0, 0.0]
        self.short = 0       # sample lines with fewer than 14 columns (dropped)
        self.records = set()
        self.yaw = []        # view yaw per sample (runcompare reads it)


def _lines(text):
    """Lines split on \n only, like the game; slices of `text`, no 4-bytes-a-char StringIO buffer."""
    pos, n = 0, len(text)
    while pos < n:
        j = text.find("\n", pos)
        j = n if j < 0 else j + 1
        yield text[pos:j]
        pos = j


def _sig_digits(x):
    m = x.lstrip("+-").split("e")[0].split("E")[0].replace(".", "").lstrip("0")
    return len(m)


def read(path=None, text=None, header_only=False):
    """One reader for the header and the samples (surfd/tasupd.py reads the header through it too)."""
    run = Run()
    if text is None:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    run.odd_breaks = bool(ODD_BREAK.search(text))
    body = False
    for line in _lines(text):
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
            run.short += 1
            continue
        try:
            nums = [file_float(x) for x in tok[:7]]
        except ValueError:
            continue
        # The most a group shows, not the fewest: a shortest-form printer writes 0.0 beside 123.456789.
        # The coarser group sets the precision: positions at 0.1 under velocities' 0.01 would read as
        # energy jumps rather than as the precision HOLD.
        for col, x in enumerate(tok[1:7]):
            dot = x.find(".")
            d = len(x) - dot - 1 if dot >= 0 and x[dot + 1:].isdigit() else 0
            g = col // 3
            if d:
                run._dec[g] = min(6, max(run._dec[g], d))
            if d < 6 and "e" not in x and "E" not in x and _sig_digits(x) >= 6:
                run.sig_q[g] = max(run.sig_q[g], 0.5 * 10.0 ** -d)
        run.decimals = min(run._dec)
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
    out = {"verdict": PASS, "reasons": [], "stats": {}, "unlisted": 0}

    def note(level, t, what):
        if len(out["reasons"]) < REASON_KEEP:
            out["reasons"].append({"level": level, "t": round(t, 4) if t is not None else None, "what": what})
        else:
            out["unlisted"] += 1
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
             else "line breaks or spaces other than newline, space and tab: readers would disagree about the header")
        return out
    if not s or len(s) < 3:
        note(FAIL, None, f"no samples ({run.short} sample lines have fewer than the 14 columns the format needs)"
             if run.short else "no samples")
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
        note(HOLD, None, f"{'positions' if run._dec[0] <= run._dec[1] else 'velocities'} printed with at most"
             f" {run.decimals} decimals: the bounds need {MIN_DECIMALS} or more")
    # Velocity rules use q; the energy test's height term uses q_pos (a %g printer rounds deep z coarser).
    q = max(0.5 * 10.0 ** (-max(run._dec[1], MIN_DECIMALS)), min(run.sig_q[1], 0.05))
    q_pos = max(0.5 * 10.0 ** (-max(run._dec[0], MIN_DECIMALS)), min(run.sig_q[0], 0.05))
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
    worst_air = worst_ground = worst_turn = worst_drift = 0.0
    nchk = njump = ntele = nduck = offtick = gaps = 0
    duck_net = 0.0
    drift = []          # horizontal residuals of the last second (aligned single ticks after t=0)
    drift_said = False
    reached = [1, 0]   # highest stage start visited, samples scanned

    def stage_reached(upto):
        for x in win[reached[1]:upto + 1]:
            for n, regs, bb in stages:
                if n > reached[0] and _in_bbox(x[1], bb) and any(_inside(x[1], r, ZONE_PAD) for r in regs):
                    reached[0] = n
        reached[1] = max(reached[1], upto + 1)
        return reached[0]

    def turn_deg(va, vb, n):
        dot = sum(va[c] * vb[c] for c in range(n))
        cross = math.sqrt(max(0.0, sum(va[c] * va[c] for c in range(n)) * sum(vb[c] * vb[c] for c in range(n)) - dot * dot))
        return math.degrees(math.atan2(cross, dot))

    def clip_ok(va, vb, n, extra):
        """vb is va after a wall or ramp: such a turn keeps at most |v| cos(turn) of the speed (single plane,
        no overbounce), plus slack for overbounce and two planes (CLIP_SLACK: surf_mesa's bounce needs 0.053)
        and the air control or gravity added in the same tick."""
        sa = math.sqrt(sum(va[c] * va[c] for c in range(n)))
        sb = math.sqrt(sum(vb[c] * vb[c] for c in range(n)))
        if sa < 1.0:
            return sb <= extra
        cosine = sum(va[c] * vb[c] for c in range(n)) / (sa * max(sb, 1e-9))
        return sb <= sa * max(cosine, 0.0) + CLIP_SLACK * sa + extra

    if win:
        for c in range(3):
            if abs(win[0][2][c]) > maxvel + GRAVITY * rate + 0.5:
                note(HOLD, win[0][0], f"velocity {win[0][2][c]:.1f} past sv_maxvelocity {maxvel:.0f}")
                break
    for i, (a, b) in enumerate(zip(win, win[1:])):
        t = a[0]
        k = (b[0] - a[0]) / rate
        aligned = abs(k - round(k)) < 0.02
        kk = max(1, math.ceil(k - 0.02))   # mover steps: the air cap and the tolerances are per step
        if not aligned or k < 0.98 or (round(k) >= 2 and a[0] >= 0):
            # Each pair gets a whole step's allowance (ten samples a tick would get ten), and a step of
            # 2+ ticks skips the one-tick turn and drift tests: both counted (honest: 0-1 of the latter).
            offtick += 1
        over_cap = next((c for c in range(3) if abs(b[2][c]) > maxvel + GRAVITY * rate + 0.5), None)
        if over_cap is not None:
            # HOLD, not FAIL: the cap given may be lower than the map's (cfg/maps, a trigger, a stage).
            note(HOLD, b[0], f"velocity {b[2][over_cap]:.1f} past sv_maxvelocity {maxvel:.0f}")
        if k > MAX_GAP:
            note(HOLD, t, f"{k}-tick gap between samples: cannot check it")
            drift = []
            continue
        nchk += 1
        va, vb = a[2], b[2]
        ha, hb = math.hypot(va[0], va[1]), math.hypot(vb[0], vb[1])
        r = resid(a, b)
        dvz = vb[2] - va[2]
        free = abs(dvz + GRAVITY * rate * k) < 0.05
        # From the ground: standing (vz 0 before too), or landed -- the tick into it a clip, not free
        # flight. The engine lands rising at vz <= 140 (pm_source.c:2350): at the tick's end (vz 0), or
        # at the next tick's start with jump held, the jump firing from vz up to 140 (riding up a slope).
        # An arc's top reaches its vz by gravity alone. A faked clip in mid-air is collision, unknown.
        if i > 0:
            pv, pdt = win[i - 1][2][2], a[0] - win[i - 1][0]
            clipped = abs(va[2] - pv + GRAVITY * pdt) >= 0.05
            standing = abs(pv) < 0.01 and abs(va[2]) < 0.01
        else:
            clipped, standing = True, abs(va[2]) < 0.01
        jump = (JUMP_VZ[0] <= vb[2] <= JUMP_VZ[1] and -0.01 < va[2] <= LAND_VZ
                and (standing or clipped))
        ground = abs(va[2]) < 0.01 and abs(vb[2]) < 0.01
        shift = 0.0
        if math.hypot(r[0], r[1]) < 2.0 * kk and DUCK_SHIFT[0] <= abs(r[2]) <= DUCK_SHIFT[1] and not ground:
            shift = r[2]
            duck_net += shift
            nduck += 1
            if abs(duck_net) > DUCK_NET:
                note(HOLD, t, f"duck shifts add up to {duck_net:+.1f} u of height")
                duck_net = max(-DUCK_NET, min(DUCK_NET, duck_net))
        if ground or jump:
            duck_net = 0.0   # standing up on the ground (or on a bhop's jump tick) shifts nothing back
        d = math.sqrt(r[0] ** 2 + r[1] ** 2 + (r[2] - shift) ** 2)
        if d > POS_TOL * kk and not (ground and math.hypot(r[0], r[1]) <= POS_TOL * kk and abs(r[2]) <= STEP + 1):
            ntele += 1
            drift = []
            duck_net = 0.0
            dest = next((n for n, regs, bb in stages
                         if _in_bbox(b[1], bb) and any(_inside(b[1], rg, ZONE_PAD) for rg in regs)), None)
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
        if aligned and round(k) >= 2 and a[0] >= 0:
            # A step of k ticks (a lost packet: honest files have at most one, 2 in 301): it moves at most
            # half its velocity change x its time off the mean velocity (measured 3.04 of 3.15), and what
            # that cannot explain counts toward the second too, standing for k ticks of it.
            gaps += 1
            dvk = math.sqrt(sum((vb[c] - va[c]) ** 2 for c in range(3))) * (b[0] - a[0])
            if d > dvk / 2 + FREE_TOL:
                note(HOLD, t, f"moves {d:.1f} u off its velocities in {round(k)} ticks, more than their change explains:"
                     " skipped or edited ticks")
            rh = math.hypot(r[0], r[1])
            room = math.sqrt(sum((vb[c] - va[c]) ** 2 for c in range(3))) * (b[0] - a[0])
            f = max(0.0, rh - room) / rh if rh > 1e-9 else 0.0
            drift.extend([(r[0] * f, r[1] * f)] + [(0.0, 0.0)] * (round(k) - 1))
            del drift[:-66]
            if len(drift) == 66:
                dsum = math.hypot(sum(x for x, _ in drift), sum(y for _, y in drift))
                worst_drift = max(worst_drift, dsum)
                if dsum > DRIFT_SECOND and not drift_said:
                    drift_said = True
                    note(HOLD, t, f"positions drift {dsum:.0f} u off the velocities within one second: edited positions?")
        if aligned and round(k) == 1 and a[0] >= 0:
            # In the air the mover accelerates, then moves the whole tick on the new velocity: against that
            # the window sum is <= 0.3 u on all 117 corpus runs (against the mean of the two, 8 u; summing
            # those put 84 of 301 honest files past 24 u). On contact only what the change cannot explain.
            if free:
                rd = [b[1][c] - a[1][c] - vb[c] * (b[0] - a[0]) for c in range(2)]
            else:
                rh = math.hypot(r[0], r[1])
                room = math.sqrt(sum((vb[c] - va[c]) ** 2 for c in range(3))) * (b[0] - a[0])
                f = max(0.0, rh - room) / rh if rh > 1e-9 else 0.0
                rd = [r[0] * f, r[1] * f]
            drift.append((rd[0], rd[1]))
            if len(drift) > 66:
                drift.pop(0)
            if len(drift) == 66:
                dsum = math.hypot(sum(x for x, _ in drift), sum(y for _, y in drift))
                worst_drift = max(worst_drift, dsum)
                if dsum > DRIFT_SECOND and not drift_said:
                    drift_said = True
                    note(HOLD, t, f"positions drift {dsum:.0f} u off the velocities within one second: edited positions?")
        if not free and aligned:
            m = round(-dvz / (GRAVITY * rate))
            if (2 <= m <= MAX_GAP and m != round(k) and abs(dvz + GRAVITY * rate * m) < 0.05
                    and d > FREE_TOL * kk):   # a ramp tick can land on a multiple of g dt by chance; its position fits
                note(HOLD, t, f"vertical speed fell exactly {m} ticks of gravity in {round(k)}: missing or edited ticks")
        dvh = math.hypot(vb[0] - va[0], vb[1] - va[1])
        # A wall touch leaves vz on gravity but changes v_h by more than air control can, costing speed.
        wall = free and dvh > AIR_CAP * kk + 1.0 and clip_ok(va, vb, 2, AIR_CAP * kk + 4 * q)
        if free and not wall and FREE_TOL * kk < d <= POS_TOL * kk:
            note(HOLD, t, f"free-flight position off by {d:.1f} u in {k:.2g} tick(s): missing or edited ticks")
        elif (not free or wall) and t >= 0 and d <= POS_TOL * kk:
            # Contact (a ramp clip) moves the body with a velocity between the two samples', so the
            # residual is bounded by the change: measured excess <= 2 u after the start (t < 0: one
            # import's start zone zeroes velocity but not motion, 3.9 u a tick). On the ground a step
            # or a slope moves it up or down by up to STEP without vertical speed.
            dz = max(0.0, abs(r[2] - shift) - STEP) if ground else r[2] - shift
            dg = math.sqrt(r[0] ** 2 + r[1] ** 2 + dz ** 2)
            dv = math.sqrt(sum((vb[c] - va[c]) ** 2 for c in range(3)))
            if dg > dv * (b[0] - a[0]) + FREE_TOL * kk:
                note(HOLD, t, f"moves {dg:.1f} u off its velocity in {k:.2g} tick(s), more than the velocity change explains")
        if ground and not jump:
            # Friction first (FRICTION, STOPSPEED), then ground accel: at most 20 u/s a tick, and past
            # wishspeed at most 2AW - A^2 onto v^2 (measured max 9764 against 9760 over 12937 ticks).
            reach = ha
            for _ in range(kk):
                reach = max(0.0, reach - max(reach, STOPSPEED) * FRICTION * rate)
                reach = math.sqrt(reach * reach + GROUND_DV2)
            tol = 4 * math.sqrt(2) * q + 0.5
            worst_ground = max(worst_ground, (hb - ha) / (GROUND_DV * kk))
            if hb - ha > GROUND_DV * kk + 4 * q + 0.5:
                note(HOLD, t, f"ground speed +{hb - ha:.1f} u/s in {k:.2g} tick(s) (cap {GROUND_DV * kk:.0f})")
            elif hb > reach + tol:
                note(HOLD, t, f"ground speed {ha:.0f} -> {hb:.0f} u/s in {k:.2g} tick(s): friction allows {reach:.0f}")
            continue
        if jump:
            njump += 1
            # The jump tick moves in the air (jump comes before friction): air control's |v'|^2 <= |v|^2
            # + 900, so +30 from rest but ~0 at speed (a flat +30 let fabricated hops pump speed).
            if hb * hb - ha * ha > AIR_DV2 * kk + 4 * math.sqrt(2) * hb * q + 1.0:
                note(HOLD, t, f"speed {ha:.0f} -> {hb:.0f} u/s on the jump tick: air control adds |v|^2 + 900 at most")
            continue
        ea = va[0] ** 2 + va[1] ** 2 + va[2] ** 2 + 2 * GRAVITY * a[1][2]
        eb = vb[0] ** 2 + vb[1] ** 2 + vb[2] ** 2 + 2 * GRAVITY * (b[1][2] - shift)
        spd = max(math.sqrt(ea - 2 * GRAVITY * a[1][2]), 1.0)
        tol = 4 * math.sqrt(3) * spd * q + 4 * GRAVITY * q_pos + 30.0
        gain = eb - ea
        worst_air = max(worst_air, gain / (AIR_DV2 * kk))
        if gain > AIR_DV2 * kk + tol:
            note(HOLD, t, f"energy +{gain:.0f} in {k:.2g} tick(s), air cap {AIR_DV2 * kk:.0f}"
                 f" ({gain / (AIR_DV2 * kk):.1f}x): push, booster or speed change")
        elif aligned and round(k) >= 2 and t >= 0 and min(ha, hb) > 1.0:
            # A step of k ticks: air control turns at most 2 asin(30/|v|) a tick, a wall or ramp only
            # by taking speed.
            turn = turn_deg(va, vb, 2)
            most = math.degrees(2 * math.asin(min(1.0, AIR_CAP / min(ha, hb)))) * round(k) + 1.0
            extra = AIR_CAP * kk + GRAVITY * rate * kk + 4 * q
            landing = va[2] < -1.0 and abs(vb[2]) < 0.01 and hb <= math.sqrt(sum(c * c for c in va)) + extra
            if turn > most and not landing and not clip_ok(va, vb, 2, extra):
                note(HOLD, t, f"{ha:.0f} -> {hb:.0f} u/s turning {turn:.1f} deg in {round(k)} ticks: air control"
                     f" turns at most {most:.1f}, and a wall or ramp would have taken speed")
        elif aligned and round(k) == 1 and t >= 0:
            # Air control adds a*w with w horizontal and v'.w <= 30, so v'.(v' - v) <= 30 |v' - v|
            # whatever sv_airaccelerate is. A wall or ramp breaks that only by taking speed (clip_ok).
            if free:
                dvx, dvy = vb[0] - va[0], vb[1] - va[1]
                over = vb[0] * dvx + vb[1] * dvy - AIR_CAP * dvh
                n, extra = 2, AIR_CAP + 4 * q
            else:   # contact: the ramp adds gravity's share along it
                over = sum(vb[c] * (vb[c] - va[c]) for c in range(3)) - AIR_CAP * dvh - GRAVITY * rate * max(0.0, -vb[2])
                n, extra = 3, AIR_CAP + GRAVITY * rate + 4 * q
                if va[2] < -1.0 and abs(vb[2]) < 0.01:
                    # A landing on a slope keeps the velocity clipped onto it, then zeroes vz
                    # (pm_source.c slope fix, FullWalkMove): the run speed may take up to the 3D speed.
                    over = min(over, hb - math.sqrt(sum(c * c for c in va)) - extra)
            worst_turn = max(worst_turn, over)
            if over > TURN_TOL + 6 * math.sqrt(3) * max(ha, hb, abs(vb[2])) * q and not clip_ok(va, vb, n, extra):
                note(HOLD, t, f"{ha:.0f} -> {hb:.0f} u/s turning {turn_deg(va, vb, n):.1f} deg in one tick: air control"
                     " cannot, and a wall or ramp would have taken speed")

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
    if gaps > 1:
        note(HOLD, None, f"{gaps} sample steps skip ticks after the start: one sample a tick, please")
    # The allowance counts samples from t=0: padding the pre-start must not buy skipped ticks (review 4).
    if offtick > 2 + sum(1 for x in win if x[0] >= 0) // 500:   # packet timing: 1-2 in 3 of 164 of ours
        note(HOLD, None, f"{offtick} sample steps are not one whole tick: the per-tick bounds cannot be applied"
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
        inside = [rg for rg in start_regs if _inside(t0s[1], rg, EDGE_PAD + travel(t0s))]
        if not inside:
            note(HOLD, 0.0, "the clock starts outside the start zone")
        else:
            floors = [float(rg["bottom"]) for rg in inside if "bottom" in rg]
            floor = min(floors) if floors else t0s[1][2]
            if t0s[1][2] - floor > START_HEIGHT:
                note(HOLD, 0.0, f"the clock starts {t0s[1][2] - floor:.0f} u above the start zone's floor")
        v0 = math.sqrt(sum(c * c for c in t0s[2]))
        if limit_start and h0 > START_CAP:
            note(HOLD, 0.0, f"leaves the start at {h0:.0f} u/s (cap {START_CAP:.0f})")
        elif limit_start and v0 > START_CAP_3D:
            note(HOLD, 0.0, f"leaves the start at {v0:.0f} u/s counting vertical speed (cap {START_CAP_3D:.0f})")
        first = math.sqrt(sum(c * c for c in win[0][2]))
        if not limit_start and first > OPEN_CAP:
            # Nothing caps the start here, so the speed the recording opens with would be free.
            note(HOLD, win[0][0], f"opens already moving at {first:.0f} u/s on a course with no start speed limit")
        j = next((jj for jj, x in enumerate(win) if x[0] >= -1e-6), len(win))   # checkpoints count from t=0
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
            if r["unlisted"]:
                print(f"   ... {r['unlisted']} more not listed")
    return worst


if __name__ == "__main__":
    sys.exit(main())
