#!/usr/bin/env python3
"""assist.py -- the timing-assist statistics, and what the corpus will support.

BACKLOG item G / cheatanalysis FINDINGS.md §8.  The question: can a timing
assist -- Tranquility's `Edgebug assist`, `Jumpbug assist`, `null strafe`,
`AutoBounce`, `Stamina Hop`, shithop's `Nulls`, `Edge Jump`, `Perf-Hop Key` --
be told apart from a human, from a kept `.rec` alone?

Those features produce PHYSICS-LEGAL motion, so `pm_verify` PASSes them by
design (it is an exactness check, not a plausibility one) and the energy walk in
`tools/p452col.py` finds nothing, because no tick exceeds what strafing can
produce.  §8 proposed the answer as SUCCESS RATE PER OPPORTUNITY rather than
per-event perfection, and proposed to read it off "`fl` bit 1 ... ground contact
per tick, `vz` the approach".

THIS TOOL MEASURES THAT PROPOSAL AND IT DOES NOT SURVIVE THE CORPUS.  Three
separate obstacles, each measured over the whole tree (5571 .rec files: 5281
Momentum imports, 130 native runs, 157 with no sample rows) rather than reasoned
about, and each recorded here because each one is the kind of thing that reads
as a low score rather than as no score:

  1. `fl` BIT 1 IS NOT GROUND CONTACT ON A SURF RUN, AND A LANDING IS NOT A JUMP
     OPPORTUNITY.  Source sets FL_ONGROUND only on walkable ground; sliding a
     ramp leaves it CLEAR, which is the whole mechanic.  So 5369 of the 5414
     files that have sample rows hold fewer than MIN_OPP fresh-press ground-bit
     landings -- 42 Momentum runs and 3 native ones are judgeable at all.  And
     the landings that do exist are
     mostly not jumps: of 9855 ground-bit landings with no jump held beforehand,
     9122 (92.6%) see NO press within 40 ticks, because on a surf map you land
     and keep going.  A rate over the remaining 733 is a rate over 7% of the
     events the statistic was proposed to read.

  2. THE BIT THAT WOULD WORK IS THE ONE THE HUMAN CORPUS DOES NOT HAVE.  Bit 16
     (`run_rampcontact`, SV_RecFlags) is real ramp contact and is exactly the
     signal a landing-precision statistic wants.  It is written by OUR server.
     A `.mtv` records no contact plane, so `momreimport.py` writes `fl` without
     it -- its own docstring says "Never 16".  Measured: 101 of 5571 files have a
     single ramp-contact tick, EVERY ONE of them native; 90 of those hold a
     fresh-press ramp landing, and they yield 16 delays between them.  The corpus
     with the signal has no players; the corpus with players has no signal.

  3. THE NULL OBSERVABLE IS NOT THE ONE §8 ASSUMED, AND IT DOES NOT SEPARATE.
     The natural reading -- "compare the `keys` mask against the move columns" --
     is VACUOUS in every file in this tree, because `keys` is DERIVED from the
     moves: SV_RecKeys sets FSI_LEFT/RIGHT from the SIGN of `movement_y`, and
     momreimport.py applies "the same rule as SV_RecKeys".  FSI_LEFT and
     FSI_RIGHT are therefore mutually exclusive by construction and an overlap
     statistic reads a perfect score for everybody.  This is cheatanalysis
     Finding E's self-referential trap one layer over, and it was caught before
     the tool was written rather than after.  THE SAME DERIVATION MAKES `fl` BIT 4
     AND `keys` FSI_JUMP ONE FACT, not two witnesses -- both are `e.button2`, and
     this census confirms they agree on every row of all 5571 files (0
     disagreements), so nothing in a `.rec` corroborates a jump against anything.
     What IS observable is the net sidemove passing through ZERO at a direction
     reversal: holding both keys cancels the wish, so a tick of `side == 0`
     between opposite signs is the null window, and a perfect null-cancel never
     shows one.  But over 4237 judgeable Momentum runs the clean-switch rate has
     median 0.9038, p95 1.0000, and **364 runs (8.59%) read exactly 1.0000**
     (native: 4 of 60, 6.67%).  A gate at 1.0000 would therefore false-accuse
     one human run in twelve, and the assist it is aimed at reads the same as
     they do.  Null-cancelling by BIND is ordinary practice in the community this
     corpus came from, which is the likely reason and not a surprising one.

  AND THE ONE EXPLANATION I HAD FOR THE RESIDUAL SPIKE IS FALSIFIED.  Of the 733
  landings that are followed by a press, 73 (9.96%) come within 2 ticks -- far
  faster than the ~150-250 ms (10-17 ticks) a reaction to an unanticipated
  contact needs, and 46 runs (1.30%) contain one.  I predicted jump MASHING, on
  the reasoning that a player spamming the key lands with it already down often
  enough to look frame-perfect.  `delays` tests that by bucketing runs on the
  fraction of ticks jump is held, and the prediction is BACKWARDS: the fast rate
  is 32.9% in the bucket that holds jump on 0-5% of ticks and 0.68% in the
  75-100% bucket.  Two explanations survive and NEITHER IS TESTED here, because
  no assist sample exists in this tree to test against: (a) a selection artifact
  of the autobunny exclusion -- landings during a tap are removed, so what is
  left is biased toward "the tap starts just after this contact"; (b) a PREDICTED
  press, timed to a landing the player can see coming, which has no reaction
  delay and is entirely legitimate.  Both say the same thing about the gate: a
  small delay is ordinary human play, so delay cannot accuse.

WHAT DOES HAVE COVERAGE, and it is one statistic.  The jump impulse is visible in
`vz` WITHOUT the ground bit, which obstacle 1 makes necessary: over 200 files,
255,592 upward vz steps form a sharply bimodal distribution -- 89.6% below
150 u/s and 90.9% (232,251) below the band's floor, all of it a ramp converting
horizontal to vertical; a spike of 16,428 in the 275-300 bucket alone
(pm_jumpvelocity ~289, added in ONE tick), 19,494 inside the band; and 3,847
(1.5%) above its ceiling, which are boosters, pads and teleports rather than
jumps.  `steps` prints that histogram so HOP_MIN and
HOP_MAX are a measured cut placed in the valley, not a guess.  The interval
regularity of those impulses (`cv`) is judgeable on 204 Momentum runs and reads
min 0.5487, median 0.9130 against 0.0000 for a synthetic perfectly periodic
chain -- a wide-looking margin, but it bounds separation from ONE side only:
no real assist sample was measured, and a timer-driven assist still has to react
to terrain, so its cv is not 0.  Treat 0.5487 as the human floor and nothing
more.

So this ships as a CENSUS, like recsim.py beside it, and not as a detector.  It
reports COVERAGE (how many runs have enough opportunities to judge at all) and
the human DISTRIBUTION of each rate, which is the input a future threshold
needs.  `control` proves each statistic can fire, so that a low count is read as
coverage and not as a broken statistic -- an arm whose detector never fired is
the failure mode AGENTS.md warns about, and "0.00" and "not measured" print
alike.

COLUMN LAYOUT (17 columns; `tools/reccheck.py` and `tools/p452col.py` read the
same one, and SV_RecLine in src/server/sv_timer.qc is authoritative):

    0 t | 1-3 origin | 4-6 velocity | 7 pitch | 8 yaw | 9 fl | 10 keys
    11-13 fwd side up | 14-16 plane normal

    fl:   1 FL_ONGROUND, 2 ducked, 4 jump held, 8 attack held, 16 ramp contact
    keys: FSI_* (1 fwd, 2 back, 4 left, 8 right, 16 jump, 32 duck, 256 attack)

Rows are held as the ten-tuple the index constants below name.  They are
CONSTANTS and not bare numbers on purpose: the first cut of this file parsed
nine columns and read `side` at index 6, which is `vz`, so the null statistic
measured vertical velocity and printed a confident number about it.  A column
index is the cheapest thing in this file to get wrong and the hardest to notice.

`fl` bit 4 and `keys` FSI_JUMP are the SAME fact (both `e.button2`), so they are
not two witnesses; this tool reads bit 4 and cross-checks the agreement once.

Usage:
    python tools/census/assist.py census [--limit N] [--root DIR]
    python tools/census/assist.py delays [--limit N]    # pooled landing delays
    python tools/census/assist.py one <file.rec>
    python tools/census/assist.py steps [--limit N]     # upward-vz histogram
    python tools/census/assist.py control [file.rec]    # the arm that must fire
"""

import argparse
import collections
import glob
import math
import os
import sys

# --- the parsed row's own indices.  See the docstring for why these exist. ----
T, X, Y, Z, VX, VY, VZ, SIDE, FL, KEYS = range(10)
NCOL = 10

# --- flag bits, from SV_RecFlags (src/server/sv_timer.qc) ---------------------
F_ONGROUND, F_DUCKED, F_JUMP, F_ATTACK, F_RAMP = 1, 2, 4, 8, 16
# --- FSI_* (src/shared/sh_defs.qc) -------------------------------------------
FSI_LEFT, FSI_RIGHT, FSI_JUMP = 4, 8, 16

# A run with fewer opportunities than this is NOT JUDGED and is counted
# separately.  A rate over three opportunities is not a rate: recsim.py's MIN_LEN
# exists for the same reason, and the lesson there was that a pair which could
# not have been judged must not be reported as a low score.
MIN_OPP = 20

# The jump-impulse band, MEASURED and not guessed: `steps` histograms every
# upward vz step in the corpus and the distribution is sharply bimodal.  Over 200
# Momentum runs, 255,592 upward steps:
#
#       0-150 u/s   228,971  (89.6%)  a ramp converting horizontal to vertical
#     150-250 u/s     4,190  ( 1.6%)  the valley -- the cut sits in it
#     250-320 u/s    19,494  ( 7.6%)  THE JUMP IMPULSE, 16,428 of them in the
#                                     single 275-300 bucket alone (6.4%)
#     320+  u/s      ~4,800  ( 1.9%)  boosters, pads and teleports
#
# A ramp adds vz gradually over many ticks; a jump adds pm_jumpvelocity (~289 in
# Momentum's surf) in ONE, and that shows up as a spike with valleys either side.
# The upper bound matters as much as the lower: a `trigger_push` or a setspeed pad
# also produces a large upward step, and counting one as a hop would put a map
# feature into a statistic about the player.
HOP_MIN = 250.0
HOP_MAX = 320.0

# Gravity, for the synthetic chain's flight model.
GRAVITY = 800.0

# Directories that are fixtures rather than runs.  The full account of why this
# has to be a directory rule AND a name rule, and what each pass let through, is
# in recsim.py's cmd_pairs comment; this is the same rule and it is deliberately
# not re-derived here.  data/momentum/ needs none of it: every file there is an
# imported human run.
FIXDIR = ("data/p", "data/evidence/", "data/saves/", "data/resume/",
          "data/parts/", "data/staged/", "data/import/")


class Rows(object):
    """One recording's sample rows, split into contiguous segments."""

    __slots__ = ("path", "tick", "segs", "header", "nrows")

    def __init__(self, path=None, tick=0.015, segs=None, header=None, nrows=0):
        self.path = path
        self.tick = tick
        self.segs = segs or []
        self.header = header or {}
        self.nrows = nrows


def parse(path):
    """Read a .rec into a Rows.  A segment breaks wherever dt is not the tick,
    so no statistic ever straddles a pause, a resume or a stage restart -- a
    discontinuity looks like an instantaneous landing otherwise."""
    header = {}
    body = False
    tick = 0.015
    out = []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            if not body:
                if line.startswith("begin"):
                    body = True
                    continue
                if line.startswith("tickrate"):
                    try:
                        tick = float(line.split()[1])
                    except (ValueError, IndexError):
                        pass
                    continue
                if " " in line:
                    k, v = line.split(" ", 1)
                    header[k] = v.strip()
                continue
            c = line[:1]
            if not (c.isdigit() or c == "-"):
                continue
            f = line.split()
            if len(f) < 14:
                continue
            try:
                row = [0.0] * NCOL
                row[T] = float(f[0])
                row[X] = float(f[1])
                row[Y] = float(f[2])
                row[Z] = float(f[3])
                row[VX] = float(f[4])
                row[VY] = float(f[5])
                row[VZ] = float(f[6])
                row[SIDE] = float(f[12])
                row[FL] = int(float(f[9]))
                row[KEYS] = int(float(f[10]))
                out.append(tuple(row))
            except (ValueError, IndexError):
                continue
    segs = []
    cur = []
    prev = None
    for r in out:
        if prev is not None and tick > 0:
            dt = r[T] - prev[T]
            # half a tick of slack: the column is %.4f, so a 0.015 tick prints
            # exactly, but a stage restart or a pause shows up as a large jump.
            if dt > tick * 1.5 or dt < -tick * 0.5:
                if len(cur) > 1:
                    segs.append(cur)
                cur = []
        cur.append(r)
        prev = r
    if len(cur) > 1:
        segs.append(cur)
    return Rows(path, tick, segs, header, len(out))


# --------------------------------------------------------------------------
# statistic 1: the null window at a strafe reversal
# --------------------------------------------------------------------------
def stat_null(rows):
    """(opportunities, clean) over one segment.

    An OPPORTUNITY is a reversal of the net sidemove's sign.  It is CLEAN when no
    tick of `side == 0` sits between the two opposite signs -- i.e. the wish went
    from -450 to +450 with no cancellation in between, which is what a
    null-cancel (by bind or by assist) produces.  A reversal WITH a zero tick in
    it is a player who held both keys, or who let go and pressed again.

    This is the only null observable in the file.  The `keys` mask cannot be one:
    see the module docstring, obstacle 3."""
    opp = clean = 0
    sign = 0
    zeros = 0
    for r in rows:
        s = r[SIDE]
        if s > 0:
            sg = 1
        elif s < 0:
            sg = -1
        else:
            if sign:
                zeros += 1
            continue
        if sign and sg != sign:
            opp += 1
            if zeros == 0:
                clean += 1
        sign = sg
        zeros = 0
    return opp, clean


# --------------------------------------------------------------------------
# statistic 2: jump timing at a landing
# --------------------------------------------------------------------------
def stat_land(rows, bit):
    """(opportunities, delay0, delay1, delays) for landings on `bit`.

    An OPPORTUNITY is a landing the player had to press for: a 0->1 transition of
    `bit` where jump was NOT already held on the previous tick.  A landing with
    jump held through it is an autobunny hop and is EXCLUDED, because the engine
    fires that jump itself on the contact tick -- counting it would grade
    `pm_autobunny` as frame-perfect play, and every bhop player uses it.

    The DELAY is the number of ticks from the landing tick to the first tick
    jump is held, or None within the window.  delay0 is the assist's signature:
    a `Perf-Hop`/`Edge Jump`/jumpbug assist fires on the contact tick, every
    time, so its rate is 1.000 and its delay has no spread."""
    opp = d0 = d1 = 0
    delays = []
    g = [(r[FL] & bit) != 0 for r in rows]
    j = [(r[FL] & F_JUMP) != 0 for r in rows]
    for i in range(1, len(rows)):
        if not (g[i] and not g[i - 1]):
            continue
        if j[i - 1]:
            continue                    # autobunny: the press predates the land
        opp += 1
        d = None
        for k in range(i, min(i + 40, len(rows))):
            if j[k]:
                d = k - i
                break
        delays.append(d)
        if d == 0:
            d0 += 1
            d1 += 1
        elif d == 1:
            d1 += 1
    return opp, d0, d1, delays


def all_delays(rows, bit):
    """Every fresh-press landing delay in a recording, pooled across segments.

    This exists because the PER-RUN RATE is the wrong unit for this statistic and
    the corpus said so: a real surf run holds 15 ground-bit landings, below
    MIN_OPP, so no per-run rate is judgeable -- but the DELAY of each landing is
    a sample on its own, and pooling them over thousands of runs gives a
    distribution with plenty of mass.  The discriminator is then the SHAPE (a
    spike at 0 against a spread centred on human reaction time) rather than a
    rate, and it needs no minimum opportunity count to be meaningful."""
    out = []
    for seg in rows.segs:
        out.extend(stat_land(seg, bit)[3])
    return out


# --------------------------------------------------------------------------
# statistic 3: hop impulses and their regularity
# --------------------------------------------------------------------------
def upward_steps(rows):
    """[(index, step)] for every tick whose vz rose.  Gravity only ever removes
    vertical speed and AirAccelerate adds none (it flattens wishdir), so ANY
    upward step is a contact, a jump or a booster -- never free flight."""
    out = []
    for i in range(1, len(rows)):
        d = rows[i][VZ] - rows[i - 1][VZ]
        if d > 0:
            out.append((i, d))
    return out


def stat_hop(rows):
    """(hops, cv) over one segment.

    A HOP is an upward vz step inside the measured jump band, which is the
    impulse signature rather than the ground bit -- the bit an autobunny chain
    never sets, per
    AGENTS.md ("a clean pm_autobunny chain has no frame with onground set at
    all") and per obstacle 1 above.

    `cv` is the coefficient of variation of the INTERVALS between hops: sd over
    mean.  This is a REGULARITY statistic and not a success rate, and it is the
    weakest of the three -- physics quantises the interval, so a low cv is
    expected of a good human too.  It is included because an `AutoBounce` or
    `Stamina Hop` assist fires on a timer and should read lower than any human,
    and because on the bhop half of the corpus it is the only statistic with
    coverage at all.  Whether it separates is exactly what the census is for."""
    idx = [i for i, d in upward_steps(rows) if HOP_MIN < d <= HOP_MAX]
    if len(idx) < 3:
        return len(idx), None
    gaps = [rows[b][T] - rows[a][T] for a, b in zip(idx, idx[1:])]
    gaps = [g for g in gaps if g > 0]
    if len(gaps) < 2:
        return len(idx), None
    m = sum(gaps) / len(gaps)
    if m <= 0:
        return len(idx), None
    var = sum((g - m) ** 2 for g in gaps) / len(gaps)
    return len(idx), math.sqrt(var) / m


def run_stats(rows):
    """Every statistic over every segment of one recording."""
    st = {"null_opp": 0, "null_clean": 0,
          "landg_opp": 0, "landg_d0": 0, "landg_d1": 0,
          "landr_opp": 0, "landr_d0": 0, "landr_d1": 0,
          "hop": 0, "cvs": [], "ramp_ticks": 0, "ground_ticks": 0,
          "jumpagree": None, "nsegs": len(rows.segs)}
    fj = kj = agree = nrow = 0
    for seg in rows.segs:
        o, c = stat_null(seg)
        st["null_opp"] += o
        st["null_clean"] += c
        for bit, pre in ((F_ONGROUND, "landg"), (F_RAMP, "landr")):
            o, d0, d1, _ = stat_land(seg, bit)
            st[pre + "_opp"] += o
            st[pre + "_d0"] += d0
            st[pre + "_d1"] += d1
        h, cv = stat_hop(seg)
        st["hop"] += h
        if cv is not None:
            st["cvs"].append(cv)
        for r in seg:
            if r[FL] & F_ONGROUND:
                st["ground_ticks"] += 1
            if r[FL] & F_RAMP:
                st["ramp_ticks"] += 1
            a = bool(r[FL] & F_JUMP)
            b = bool(r[KEYS] & FSI_JUMP)
            fj += a
            kj += b
            nrow += 1
            agree += (a == b)
    # (agreeing rows, rows compared, fl-bit4 rows, keys-FSI_JUMP rows).  The first
    # cut stored three of these and the census compared `agree` to `fj` -- which
    # is not a disagreement test, and printed 5303 of 5571 files as disagreeing
    # when the two columns agree on every row of every file.  A check that
    # compares a count to the wrong denominator reports a defect that does not
    # exist, and this one was caught only because the number was implausible.
    st["jumpagree"] = (agree, nrow, fj, kj) if nrow else None
    return st


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = q * (len(s) - 1)
    lo = int(math.floor(i))
    hi = int(math.ceil(i))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def fmt(x, w=7):
    return ("%*.4f" % (w, x)) if x is not None else ("%*s" % (w, "-"))


def iter_recs(root, limit=0):
    seen = []
    for p in sorted(glob.glob(os.path.join(root, "**", "*.rec"), recursive=True)):
        q = p.replace(os.sep, "/")
        if any(f in q for f in FIXDIR):
            continue
        seen.append(p)
    if limit:
        seen = seen[:limit]
    return seen


def classify(path):
    q = path.replace(os.sep, "/")
    if "/momentum/" in q:
        return "momentum"
    if "/data/runs/" in q or "/data/online/" in q:
        return "native"
    return "other"


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------
def cmd_census(args):
    files = iter_recs(args.root, args.limit)
    print("assist.py census -- %d .rec files under %s" % (len(files), args.root))
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    counts = collections.Counter()
    unramped = 0
    jumpdis = 0
    for p in files:
        try:
            rows = parse(p)
        except OSError:
            counts["unreadable"] += 1
            continue
        if not rows.segs:
            counts["norows"] += 1
            continue
        st = run_stats(rows)
        kind = classify(p)
        counts[kind] += 1
        if st["jumpagree"] and st["jumpagree"][0] != st["jumpagree"][1]:
            jumpdis += 1
        b = per[kind]
        b["rows"].append(rows.nrows)
        if st["ramp_ticks"]:
            unramped += 1
        if st["null_opp"] >= MIN_OPP:
            b["null_rate"].append(st["null_clean"] / float(st["null_opp"]))
            b["null_opp"].append(st["null_opp"])
        else:
            counts["null_notjudged"] += 1
        if st["landg_opp"] >= MIN_OPP:
            b["landg_rate"].append(st["landg_d0"] / float(st["landg_opp"]))
            b["landg1_rate"].append(st["landg_d1"] / float(st["landg_opp"]))
        else:
            counts["landg_notjudged"] += 1
            b["landg_opp_small"].append(st["landg_opp"])
        if st["landr_opp"] >= MIN_OPP:
            b["landr_rate"].append(st["landr_d0"] / float(st["landr_opp"]))
        else:
            counts["landr_notjudged"] += 1
        b["hop"].append(st["hop"])
        if st["hop"] >= MIN_OPP and st["cvs"]:
            b["hop_cv"].append(sum(st["cvs"]) / len(st["cvs"]))
        else:
            counts["hop_notjudged"] += 1
        if st["ground_ticks"] == 0:
            counts["no_ground_at_all"] += 1

    print("\nfiles: %s" % dict(counts))
    print("files with ANY ramp-contact tick (fl bit 16): %d" % unramped)
    print("files where fl bit 4 and keys FSI_JUMP disagree on ANY row: %d"
          "  (they are the same fact, e.button2, so this must be 0)" % jumpdis)

    for kind in sorted(per):
        b = per[kind]
        if not b["rows"]:
            continue
        print("\n=== %s (%d files, median %d rows) ==="
              % (kind, len(b["rows"]), int(pct(b["rows"], 0.5))))

        def block(name, rates, opps=None, note=""):
            if not rates:
                print("  %-22s NO RUN JUDGEABLE (every run below %d opportunities)%s"
                      % (name, MIN_OPP, note))
                return
            at1 = sum(1 for r in rates if r >= 0.999999)
            print("  %-22s judgeable %4d   rate  min %s  p25 %s  med %s"
                  "  p75 %s  p95 %s  max %s"
                  % (name, len(rates), fmt(pct(rates, 0.0)), fmt(pct(rates, 0.25)),
                     fmt(pct(rates, 0.5)), fmt(pct(rates, 0.75)),
                     fmt(pct(rates, 0.95)), fmt(pct(rates, 1.0))))
            print("  %-22s              runs reading 1.0000: %d of %d (%.2f%%)%s"
                  % ("", at1, len(rates), 100.0 * at1 / len(rates), note))
            if opps:
                print("  %-22s              opportunities per run: med %d  max %d"
                      % ("", int(pct(opps, 0.5)), max(opps)))

        small = ("  [not-judgeable runs hold a median of %d opportunities]"
                 % int(pct(b["landg_opp_small"], 0.5))) if b["landg_opp_small"] else ""
        block("null: clean switch", b["null_rate"], b["null_opp"])
        block("land(bit1) delay 0", b["landg_rate"], None, small)
        block("land(bit1) delay<=1", b["landg1_rate"])
        block("land(bit16) delay 0", b["landr_rate"])
        cvs = b["hop_cv"]
        if cvs:
            print("  %-22s judgeable %4d   cv    min %s  med %s  p95 %s  max %s"
                  % ("hop interval cv", len(cvs), fmt(pct(cvs, 0.0)),
                     fmt(pct(cvs, 0.5)), fmt(pct(cvs, 0.95)), fmt(pct(cvs, 1.0))))
        else:
            print("  %-22s NO RUN JUDGEABLE" % "hop interval cv")
        print("  %-22s hops per run: med %d  max %d"
              % ("", int(pct(b["hop"], 0.5)) if b["hop"] else 0,
                 max(b["hop"]) if b["hop"] else 0))

    print("""
READ THIS BEFORE QUOTING A NUMBER.  This is a CENSUS of what the corpus supports,
not a detector, and the three obstacles in the module docstring are the result:
  * a rate over fewer than %d opportunities is NOT JUDGED and is counted as such,
    never reported as a low score;
  * a run at 1.0000 is reported as a COUNT AND A FRACTION of the judgeable runs,
    because that is the false-accusation rate a threshold at 1.0000 would have;
  * the momentum half is Source physics at the demo's own tick rate and its
    players are leaderboard players, so it is the hardest population to accuse and
    the right one to calibrate on -- but it is not FTESurf play.
  * THE FLEET CORPUS HAS BEEN RUN (2026-10-05, the Pi's `data/runs/`; fetch it
    read-only per tools/census/README.md and pass --root <dir>/data).  It inverts
    the coverage problem: 54 of 64 files carry a ramp-contact tick against 101 of
    5571 locally, 27 runs are judgeable on `land(bit16)` and EVERY ONE reads
    0.0000.  `null` still does not separate (4 of 57 fleet runs read exactly
    1.0000, against 8.59%% locally).  So the human side of a cut is measured and
    the cheat side is not -- no assist sample exists to run through it.
NO THRESHOLD IS ASSERTED ANYWHERE IN THIS FILE, and none should be added without
an assist sample beside the native corpus.""" % MIN_OPP)
    return 0


def cmd_delays(args):
    """Pool every fresh-press landing delay in the corpus and histogram it.

    THIS IS THE STATISTIC THAT SURVIVES, and the reason it is not the per-run
    rate is measured rather than argued: obstacle 1 leaves a surf run with 0-15
    ground-bit landings, so no per-run rate clears MIN_OPP -- but each delay is a
    sample, and a human cannot press a key inside one tick of a contact they did
    not predict.  Simple reaction time is ~150-250 ms, i.e. 10-17 ticks at 66.67
    Hz.  A `Perf-Hop`/`Edge Jump`/jumpbug assist fires ON the contact tick.
    Whatever the histogram shows at 0-2 ticks is therefore the false-accusation
    rate of a threshold there, measured on real play rather than assumed."""
    files = [p for p in iter_recs(args.root, args.limit)]
    kinds = collections.defaultdict(collections.Counter)
    runs = collections.Counter()
    fast = collections.Counter()
    runsfast = collections.Counter()
    none_count = collections.Counter()
    # jump-density buckets, to TEST the mashing explanation rather than assert it
    BUCKETS = ((0.0, 0.05), (0.05, 0.25), (0.25, 0.75), (0.75, 1.01))
    dens = collections.defaultdict(lambda: collections.Counter())
    BITS = ((F_ONGROUND, "bit1 ground"), (F_RAMP, "bit16 ramp"))
    for p in files:
        try:
            rows = parse(p)
        except OSError:
            continue
        if not rows.segs:
            continue
        ticks = sum(len(s) for s in rows.segs)
        jheld = sum(1 for s in rows.segs for r in s if r[FL] & F_JUMP)
        frac = jheld / float(ticks) if ticks else 0.0
        bk = None
        for lo, hi in BUCKETS:
            if lo <= frac < hi:
                bk = "%.0f-%.0f%%" % (lo * 100, min(hi, 1.0) * 100)
                break
        for bit, name in BITS:
            ds = all_delays(rows, bit)
            if not ds:
                continue
            runs[name] += 1
            hasfast = False
            for d in ds:
                if d is None:
                    none_count[name] += 1
                    continue
                kinds[name][min(d, 60)] += 1
                if bk:
                    dens[bk]["land"] += 1
                if d <= args.fast:
                    fast[name] += 1
                    hasfast = True
                    if bk:
                        dens[bk]["fast"] += 1
            if bk:
                dens[bk]["runs"] += 1
                if hasfast:
                    dens[bk]["runsfast"] += 1
            if hasfast:
                runsfast[name] += 1
    print("pooled fresh-press landing delays over %d files" % len(files))
    for name in sorted(kinds):
        tot = sum(kinds[name].values())
        nr = none_count[name]
        print("\n=== %s: %d runs with at least one such landing, %d delays"
              " (+%d with no press within 40 ticks) ===" % (name, runs[name], tot, nr))
        cum = 0
        for d in sorted(kinds[name]):
            cum += kinds[name][d]
            label = "%d+" % d if d == 60 else "%d" % d
            print("  delay %3s ticks  %8d   cum %6.4f  %s"
                  % (label, kinds[name][d], cum / float(tot),
                     "#" * min(60, int(60.0 * kinds[name][d]
                                      / max(kinds[name].values())))))
        p = [d for d, c in sorted(kinds[name].items()) for _ in range(c)]
        print("  percentiles: p1 %s  p5 %s  p25 %s  med %s  p75 %s"
              % (fmt(pct(p, 0.01), 4), fmt(pct(p, 0.05), 4), fmt(pct(p, 0.25), 4),
                 fmt(pct(p, 0.5), 4), fmt(pct(p, 0.75), 4)))
        print("  delays <= %d ticks: %d of %d (%.4f%% of landings)"
              % (args.fast, fast[name], tot, 100.0 * fast[name] / tot))
        # the number a gate actually needs: how many RUNS contain one
        print("  runs containing at least one delay <= %d: %d of %d (%.3f%%)"
              "  <-- the false-accusation rate of a per-run gate"
              % (args.fast, runsfast[name], runs[name],
                 100.0 * runsfast[name] / runs[name] if runs[name] else 0.0))
    if not kinds:
        print("no fresh-press landings anywhere in the corpus -- obstacle 1 in full.")
        return 1

    print("""
IS THE SPIKE AT 0-1 TICKS JUMP MASHING?  Tested rather than assumed, because the
whole question is whether a delay-0 press accuses anybody.  If it does, the fast
presses must CONCENTRATE in runs that hold jump most of the time -- a player
mashing the key lands with it already down, so the press and the contact share a
tick by luck, many times a run.  If instead they were spread evenly across runs
that barely touch jump, mashing would not explain them and the spike would still
need an explanation.""")
    print("  %-12s %6s %9s %9s %11s %13s"
          % ("jump held", "runs", "landings", "fast", "fast rate", "runs w/ fast"))
    for lo, hi in BUCKETS:
        bk = "%.0f-%.0f%%" % (lo * 100, min(hi, 1.0) * 100)
        d = dens[bk]
        if not d["runs"]:
            print("  %-12s %6d" % (bk, 0))
            continue
        print("  %-12s %6d %9d %9d %10.3f%% %8d (%.2f%%)"
              % (bk, d["runs"], d["land"], d["fast"],
                 100.0 * d["fast"] / d["land"] if d["land"] else 0.0,
                 d["runsfast"], 100.0 * d["runsfast"] / d["runs"]))
    return 0


def cmd_one(args):
    rows = parse(args.file)
    st = run_stats(rows)
    print("%s" % args.file)
    print("  tick %s  rows %d  segments %d  map %s  moves %s"
          % (rows.tick, rows.nrows, st["nsegs"], rows.header.get("map", "?"),
             rows.header.get("moves", "-")))
    print("  ground ticks %d   ramp ticks %d   hops %d"
          % (st["ground_ticks"], st["ramp_ticks"], st["hop"]))
    if st["jumpagree"]:
        a, n, fj, kj = st["jumpagree"]
        print("  fl bit4 %d / keys FSI_JUMP %d, agreeing on %d of %d rows"
              % (fj, kj, a, n))
    for name, opp, succ in (("null clean switch", st["null_opp"], st["null_clean"]),
                            ("land bit1 delay0", st["landg_opp"], st["landg_d0"]),
                            ("land bit1 delay<=1", st["landg_opp"], st["landg_d1"]),
                            ("land bit16 delay0", st["landr_opp"], st["landr_d0"])):
        if opp >= MIN_OPP:
            print("  %-20s %5d opportunities   %5d successes   rate %s"
                  % (name, opp, succ, fmt(succ / float(opp))))
        else:
            print("  %-20s %5d opportunities   NOT JUDGED (below %d)"
                  % (name, opp, MIN_OPP))
    if st["cvs"]:
        print("  hop interval cv      %s over %d segments"
              % (fmt(sum(st["cvs"]) / len(st["cvs"])), len(st["cvs"])))
    return 0


def cmd_steps(args):
    """Histogram the upward-vz steps, so HOP_MIN is a measured cut and not a
    guess.  Two populations are expected and the gap between them is the cut."""
    files = iter_recs(args.root, args.limit)
    hist = collections.Counter()
    n = 0
    for p in files:
        try:
            rows = parse(p)
        except OSError:
            continue
        for seg in rows.segs:
            for _, d in upward_steps(seg):
                hist[int(min(d, 2000) // 25) * 25] += 1
                n += 1
    if not n:
        print("steps: no upward vz steps found in %d files" % len(files))
        return 1
    print("upward vz steps over %d files: %d" % (len(files), n))
    print("  bucket (25 u/s)   count    cumulative fraction below")
    top = max(hist.values())
    tot = 0
    for k in sorted(hist):
        tot += hist[k]
        bar = "#" * min(60, int(60.0 * hist[k] / top))
        print("  %6d-%-6d %9d   %6.4f  %s"
              % (k, k + 25, hist[k], tot / float(n), bar))
    below = sum(v for k, v in hist.items() if k + 25 <= HOP_MIN)
    inband = sum(v for k, v in hist.items() if HOP_MIN < k + 25 <= HOP_MAX + 25)
    above = sum(v for k, v in hist.items() if k >= HOP_MAX)
    print("\n  the jump band %.0f-%.0f u/s holds %d of %d steps (%.2f%%)"
          % (HOP_MIN, HOP_MAX, inband, n, 100.0 * inband / n))
    print("  rejected: %d below the band (ramp climb), %d above it (booster/pad)"
          % (below, above))
    print("  A cut placed anywhere in the 150-250 valley gives the same answer;"
          " the band's EDGES are what the histogram measures.")
    return 0


# --------------------------------------------------------------------------
# the control: an arm whose detector has never fired measures nothing
# --------------------------------------------------------------------------
def synth_assist(rows):
    """Return a copy of `rows` rewritten to be assist-shaped, changing ONE thing
    per statistic so the difference beside the original is a measurement.

    null: every zero-side tick that sits between two opposite signs takes the
          following sign, so no reversal passes through a null window.
    land: every landing that needed a fresh press gets jump held ON the landing
          tick, i.e. delay 0, which is what a Perf-Hop/Jumpbug assist does.
          BOTH CONTACT BITS, not just F_ONGROUND.  The first cut rewrote only
          bit 1, so `control` proved the walkable-ground statistic and said
          nothing about the ramp-contact one -- which is the statistic that
          actually has coverage on this game's runs (bit 1 is nearly absent on
          a surf run, obstacle 1; bit 16 is written only by our server, so the
          fleet corpus is all of it and the Momentum corpus none).  A statistic
          the control never fires reads 0.0000 for two opposite reasons, and
          only the control tells them apart.
    hop:  left alone -- its control is the periodic chain below, because a
          regularity statistic cannot be forced by editing one column."""
    out = []
    for seg in rows.segs:
        s = [r[SIDE] for r in seg]
        nxt = [0] * len(s)              # the next nonzero sign after each tick
        last = 0
        for i in range(len(s) - 1, -1, -1):
            nxt[i] = last
            if s[i]:
                last = 1 if s[i] > 0 else -1
        prevsign = 0
        newseg = []
        for i, r in enumerate(seg):
            fl = r[FL]
            side = r[SIDE]
            if side == 0 and prevsign and nxt[i] and nxt[i] != prevsign:
                side = 450.0 * nxt[i]          # close the null window
            j_prev = i > 0 and (seg[i - 1][FL] & F_JUMP) != 0
            for bit in (F_ONGROUND, F_RAMP):   # F_JUMP aliases neither
                g_now = (fl & bit) != 0
                g_prev = i > 0 and (seg[i - 1][FL] & bit) != 0
                if g_now and not g_prev and not j_prev:
                    fl |= F_JUMP               # fire on the contact tick
            row = list(r)
            row[SIDE] = side
            row[FL] = fl
            newseg.append(tuple(row))
            prevsign = 1 if side > 0 else (-1 if side < 0 else prevsign)
        out.append(newseg)
    return Rows(rows.path, rows.tick, out, rows.header, rows.nrows)


def synth_periodic(n=120, tick=0.015, period=25):
    """A perfectly periodic hop chain: what a timer-driven AutoBounce looks like.
    Free flight under gravity, then an impulse on schedule.

    `period` is chosen so the impulse lands INSIDE the measured jump band: at
    tick 0.015 gravity removes 800*0.015 = 12 u/s per tick, so a 24-tick flight
    gives a step of exactly 288 u/s -- the 275-300 bucket the real corpus spikes
    in.  A chain whose impulse fell outside the band would be counted as zero hops
    and the control would report a broken statistic that is merely mis-tuned."""
    v0 = GRAVITY * tick * (period - 1)
    rows = []
    vz = v0
    for i in range(n * period):
        rows.append((i * tick, 0.0, 0.0, 100.0, 0.0, 0.0, vz, 450.0, 0, 0))
        vz = v0 if (i % period == period - 1) else vz - GRAVITY * tick
    return Rows("synthetic-periodic", tick, [rows], {}, len(rows))


def _rate(st, num, den):
    return st[num] / float(st[den]) if st[den] else None


def cmd_control(args):
    src = args.file
    if not src:
        # MOMENTUM FIRST, THEN NATIVE, and the order is the point: the published
        # control numbers were measured on a Momentum run, so a corpus that has
        # one still picks one and stays reproducible.  The fallback exists
        # because a FLEET corpus has none -- `data/runs/` on the Pi is all
        # native, and the first cut printed "no source run" there and returned 1,
        # i.e. the control arm was unusable on exactly the corpus that has the
        # ramp-contact coverage.  Whichever it picked is printed below.
        seen = set()
        cands = []
        for kind in ("momentum", "native", "other"):
            for p in iter_recs(args.root, 600):
                if classify(p) == kind and p not in seen:
                    seen.add(p)
                    cands.append(p)
        # THREE PASSES, STRICTEST FIRST.  A control that exercises only some of
        # the statistics is a control that reports green beside a statistic nobody
        # has ever seen fire -- the shape this tree keeps finding (Patch 484's
        # arm A: an unmeasured state wearing a clean measurement's clothes).  So
        # ask for a source with BOTH landing bits before settling for one, and
        # print which pass answered.  A bhop map is walkable ground with no surf
        # ramps (landg only); a surf map is the reverse.
        passes = (("both landing bits", lambda st: st["landg_opp"] >= 3 and st["landr_opp"] >= 3),
                  ("either landing bit", lambda st: st["landg_opp"] >= 3 or st["landr_opp"] >= 3),
                  ("null only, no landing coverage", lambda st: True))
        for label, want in passes:
            for p in cands:
                try:
                    st = run_stats(parse(p))
                except OSError:
                    continue
                if st["null_opp"] >= MIN_OPP and want(st):
                    src = p
                    break
            if src:
                print("control: source picked on the '%s' pass" % label)
                break
        if not src:
            print("control: no source run with %d null opportunities under %s"
                  % (MIN_OPP, args.root))
            return 1
    rows = parse(src)
    asst = synth_assist(rows)
    a, b = run_stats(rows), run_stats(asst)
    skipped = []          # statistics this source could not exercise
    print("control source: %s  [%s]" % (src, classify(src)))
    print("  %-32s %14s %14s" % ("", "AS RECORDED", "ASSIST-SHAPED"))
    ok = True

    def line(label, ka, kb):
        va = _rate(a, *ka) if isinstance(ka, tuple) else a[ka]
        vb = _rate(b, *kb) if isinstance(kb, tuple) else b[kb]
        sa = fmt(va, 14) if isinstance(va, float) else ("%14d" % va if va is not None else "%14s" % "-")
        sb = fmt(vb, 14) if isinstance(vb, float) else ("%14d" % vb if vb is not None else "%14s" % "-")
        print("  %-32s %s %s" % (label, sa, sb))
        return va, vb

    line("null opportunities", "null_opp", "null_opp")
    na, nb = line("null clean rate", ("null_clean", "null_opp"),
                  ("null_clean", "null_opp"))
    if nb is None or nb < 0.999999:
        print("  FAIL: the null statistic did not reach 1.0000 on an assist-shaped"
              " run (%s) -- the detector has not fired." % nb)
        ok = False
    else:
        print("  null: FIRES.  %s -> %s on the same run with the windows closed."
              % (fmt(na), fmt(nb)))
        if na is not None and na >= 0.999999:
            print("  NOTE: the source run ALREADY reads 1.0000, which is obstacle 3"
                  " -- a human is inside the assist's range.")

    line("land(bit1) opportunities", "landg_opp", "landg_opp")
    la, lb = line("land(bit1) delay0 rate", ("landg_d0", "landg_opp"),
                  ("landg_d0", "landg_opp"))
    if a["landg_opp"] >= 1:
        if lb is None or lb < 0.999999:
            print("  FAIL: the landing statistic did not reach 1.0000 (%s)." % lb)
            ok = False
        else:
            print("  land: FIRES.  %s -> %s over %d opportunities."
                  % (fmt(la), fmt(lb), a["landg_opp"]))
            if a["landg_opp"] < MIN_OPP:
                print("  AND THE OPPORTUNITY COUNT IS %d, below MIN_OPP %d -- which"
                      " is obstacle 1: this run cannot be judged even though the"
                      " statistic works." % (a["landg_opp"], MIN_OPP))
    else:
        print("  land: the source run has ZERO fresh-press landings, so the"
              " statistic cannot fire on it at all (obstacle 1) -- the landing"
              " half of the control needs a run that touches walkable ground.")
        skipped.append("land(bit1)")

    # THE BIT-16 TWIN, and on this game's runs it is the one that matters: a
    # surf run leaves FL_ONGROUND clear while sliding a ramp (that is the
    # mechanic), so `landg` is unjudgeable on most of the fleet while `landr` is
    # judgeable on 27 of 64 runs.  bit 16 is written only by our server, so the
    # Momentum corpus has none of it and the fleet corpus is all of it -- the two
    # halves of the control are calibrated on disjoint populations, which is why
    # both are printed rather than one standing in for the other.
    line("land(bit16) opportunities", "landr_opp", "landr_opp")
    ra, rb = line("land(bit16) delay0 rate", ("landr_d0", "landr_opp"),
                  ("landr_d0", "landr_opp"))
    if a["landr_opp"] >= 1:
        if rb is None or rb < 0.999999:
            print("  FAIL: the ramp-contact landing statistic did not reach"
                  " 1.0000 (%s) -- the detector has not fired, so a 0.0000 in the"
                  " census is coverage and not a clean population." % rb)
            ok = False
        else:
            print("  landr: FIRES.  %s -> %s over %d ramp-contact opportunities."
                  % (fmt(ra), fmt(rb), a["landr_opp"]))
            if a["landr_opp"] < MIN_OPP:
                print("  AND THE OPPORTUNITY COUNT IS %d, below MIN_OPP %d --"
                      " obstacle 1 on this run too." % (a["landr_opp"], MIN_OPP))
    else:
        # DO NOT ASSERT A CAUSE THE RUN HAS NOT MEASURED.  The first cut blamed
        # obstacle 2 (a .mtv records no contact plane) unconditionally, and on a
        # NATIVE bhop source that is false -- the reason there is no ramp contact
        # is that a bhop map has no surf ramps.  A control that explains its own
        # skip wrongly is worse than one that just says "skipped".
        if classify(src) == "momentum":
            print("  landr: the source is a MOMENTUM IMPORT, which records no"
                  " contact plane at all (obstacle 2) -- no .mtv-derived run can"
                  " ever fire this one.  Pass a native run to exercise it.")
        else:
            print("  landr: the source run has ZERO fresh ramp contacts.  On a"
                  " native run that means the map has no surf ramps (a bhop map"
                  " is walkable ground -- obstacle 1's mirror).  Pass a surf run"
                  " to exercise it.")
        skipped.append("land(bit16)")

    per = synth_periodic()
    hp, cvp = stat_hop(per.segs[0])
    real = b["cvs"]
    print("\n  synthetic periodic hop chain: %d hops, interval cv %s"
          % (hp, fmt(cvp)))
    print("  source run's own hop cv:      %s"
          % (fmt(sum(real) / len(real)) if real else "-"))
    if cvp is None or cvp > 0.02:
        print("  FAIL: a perfectly periodic chain should read cv ~ 0, got %s."
              % fmt(cvp))
        ok = False
    else:
        print("  hop: FIRES -- a timer-driven bounce reads cv %.4f." % cvp)

    # A SKIP IS NOT A PASS and the verdict must not read as one.  The search
    # above already preferred a source that exercises everything, so what
    # reaches here is honest coverage -- but "EVERY STATISTIC FIRED" printed
    # beside a statistic that never ran is the false green this tree keeps
    # paying for, so the verdict line itself is qualified.
    if not ok:
        verdict = "FAILED"
    elif skipped:
        verdict = "EVERY STATISTIC THAT RAN, FIRED"
    else:
        verdict = "EVERY STATISTIC FIRED"
    print("\ncontrol: %s" % verdict)
    if skipped:
        print("control: NOT EXERCISED ON THIS SOURCE: %s -- the numbers above"
              " prove nothing about those statistics.  Re-run with an explicit"
              " file that has them." % ", ".join(skipped))
    return 0 if ok else 1


def main():
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(here, "ftesurf", "data"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("census")
    c.add_argument("--limit", type=int, default=0)
    c.set_defaults(fn=cmd_census)

    o = sub.add_parser("one")
    o.add_argument("file")
    o.set_defaults(fn=cmd_one)

    s = sub.add_parser("steps")
    s.add_argument("--limit", type=int, default=400)
    s.set_defaults(fn=cmd_steps)

    d = sub.add_parser("delays")
    d.add_argument("--limit", type=int, default=0)
    d.add_argument("--fast", type=int, default=2,
                   help="ticks within which a jump press is faster than a human "
                        "could have reacted to the contact it follows")
    d.set_defaults(fn=cmd_delays)

    k = sub.add_parser("control")
    k.add_argument("file", nargs="?")
    k.set_defaults(fn=cmd_control)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
