#!/usr/bin/env python3
"""
turnstats.py -- the Layer 3 signatures that are about the INPUT's SHAPE, not
its quality, measured on the input trace a .rec already carries.

WHY A SECOND TOOL.  strafestats.py answers "is this yaw too good", which is the
question a strafe optimiser raises.  It is the harder question and it is not the
only one: an injected or engine-generated turn is not better than a human's, it
is DIFFERENT IN SHAPE -- perfectly constant, or perfectly flat in the axis the
injector never touches, or beginning on exactly the tick a key changed.  Those
are structural and they do not need a quality model.

IT READS THE `in` ROWS AND NOT THE SAMPLES, and that is the whole reason this
can work.  A sample carries yaw at TWO decimals, one per received packet; an
`in` row carries the usercmd the mover was handed, at FOUR -- which recovers the
wire short exactly, quantum 360/65536 = 0.0054932 deg (see the .rec grammar
block in sv_timer.qc, and engine Patch 345 on rounding).  A detector that has to
tell a constant rate from a nearly-constant one cannot be built on the samples:
their rounding is 4x the thing being measured.  The price is that `in` rows
exist only from QC build 82, so most of the archive is invisible here.

THE THREE SIGNATURES

  plateau    consecutive moves whose yaw RATE is constant to within one wire
             quantum per tick, while the player is actually turning.  A console
             `+left` (cl_yawspeed) or a turnbind produces an exactly constant
             rate for as long as it is held.  A hand on a mouse cannot: the
             counts arrive as integers at an irregular rate, so the per-tick
             rate wobbles by at least a quantum almost every tick.
             AGENTS.md notes the two routes that stay open on this client -- a
             console +left and an F-key under the engine menu -- so this one has
             a live target rather than a hypothetical one.

  flatpitch  consecutive moves with the yaw moving and the pitch EXACTLY
             unchanged.  SendInput and most injectors write dx and leave dy 0.
             A human's hand does not hold a pitch to the last bit for long, but
             it does hold one for a while -- so this is reported as a
             distribution and never as a threshold.  It is the weakest of the
             three and it is here because it is free.

  onset      the tick offset between a strafe key edge and the first yaw
             movement after it.  A script that drives both moves them on the
             same tick every time, with no spread; a person has a reaction time
             and it varies.  What matters is the SPREAD, not the mean: a fast
             player is not a suspicious one.

WHAT THIS IS NOT.  It does not accuse and it produces no threshold.  The plan's
decision policy is that statistical findings flag for human review and never
auto-reject, and this tool is written to that: its output is distributions and
its headline is the honest floor.  Nothing here is wired to a taint bit.

MEASURED HONEST FLOOR, on the LIVE corpus (the Pi's 12 lobbies, 2026-09-21):
45 recordings, 278,586 moves, 225,938 of them turning, cadence 1.000 mover
ticks per move.

    plateau    812 runs of 4+, longest 23, 1.80% of turning moves
               length median 5, p90 6, p99 16
    flatpitch  360 runs of 4+, longest 50, 1.94% of turning moves
    onset      4888 edges, 91.9% at offset zero, sd 3.45

AND THE POSITIVE CONTROL SEPARATES: --inject, which overwrites one stretch in
three with an exactly constant 2 deg/tick turn, moves the plateau figure from
1.80% to 39.17% of turning moves with a length distribution that collapses onto
the injected span (median 12, p90 12, p99 12).  That is a 22x separation on the
statistic, and it is the only thing here that has been shown to detect anything
-- every real recording in the corpus is a true negative, so a detector that
always said "clean" would have scored perfectly on all 45.

WHAT THE FLOOR SAYS ABOUT EACH SIGNATURE, including the one that failed:

  plateau    usable.  Honest play reaches 23 consecutive moves at one rate ONCE
             in 226k turning moves, and its p90 is 6.  A held turnbind produces
             hundreds.  There is room between those for a review threshold that
             nobody honest trips -- which is for a human to set, not this file.

  flatpitch  usable but wide: honest play reaches 50.  A pitch held to the last
             bit for half a second is something people do.

  onset      DOES NOT SEPARATE, and this is the finding rather than a gap.  The
             plan specifies "motion onset with no human reaction latency after a
             button edge"; on this game 91.9% of honest edges are already at
             offset ZERO, because a strafer is turning before the key changes --
             the turn leads the key, not the other way round.  One honest player
             in the corpus reads sd 0.17 over a whole run.  The statistic is
             computed and printed for completeness; nothing should be built on
             it without a different edge definition.

PER-PLAYER, keyed on the recording's player id and NOT on the display name (see
player_key): the largest baseline, 37 recordings under three different names
from one id, sits at 1.71% plateau / 1.59% flatpitch -- i.e. the pooled floor is
one player's floor.  The highest figures in the corpus, 3.94% / 8.34%, belong to
a DIFFERENT id with three recordings, and three recordings is not a baseline.
It is exactly the shape the plan's decision policy is written for: a number to
look at, never a verdict, and the thing that would actually answer it is that
player's .hid -- mouse smoothing (m_filter) and a low frame rate both smooth a
rate for innocent reasons, and neither is visible from the server's file.

Usage:
    python tools/turnstats.py                      # every .rec under data/runs
    python tools/turnstats.py <file.rec> [...]
    python tools/turnstats.py --pooled             # one distribution over all
    python tools/turnstats.py --by-player          # the per-player baseline
    python tools/turnstats.py --inject             # the positive control
"""

import argparse
import glob
import math
import os
import re
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(SURFDIR, "ftesurf", "data", "runs")

# The wire quantum: usercmd angles travel as shorts.  Everything below is
# measured in multiples of it, because it is the smallest difference that can
# exist in this column at all.
QUANT = 360.0 / 65536.0

# A move is "turning" when its rate clears this.  Two quanta per tick, i.e.
# about 1.1 deg/s at a 100 Hz tick: low enough that a slow deliberate turn
# counts, high enough that the rounding floor does not.
TURN_MIN = 2.0 * QUANT

# Two rates are "the same" within this.  One quantum per tick: the finest
# distinction the column can carry, so a plateau found at this tolerance is one
# the file actually states rather than one the arithmetic invented.
RATE_TOL = QUANT

# A plateau shorter than this is not evidence of anything -- two moves at the
# same rate happen constantly.  Reported from 4 up so the distribution's tail is
# visible; the floor below says what honest play reaches.
PLATEAU_MIN = 4

# sv_timer.qc SV_RecLine's <bt>: 1 jump, 2 duck, 4 speed.  NOT input_buttons --
# see the grammar block's essay on why those three are per-bit fields.
BT_JUMP = 1


# The recording leaf's player segment: <ticks7>_<slug>-<id8>_<tag>.rec, where
# the id is the first 8 hex of sha256(guid) (FS_WHO_IDLEN, sh_defs.qc).
WHO_RE = re.compile(r"^\d{7}_(?P<slug>[^-]*)-(?P<id>[0-9a-f]{8})_")


def player_key(path, head):
    """-> (key, label) for the baseline.

    THE ID AND NOT THE NAME, and the live corpus is why.  Grouped by the `owner`
    header this tool first reported five players; the filenames say otherwise.
    `kap-26c95e00` and `proto-26c95e00` are ONE id -- the same person renamed --
    while `boro-67603710` and `borobongo-4e78ae4e` are two.  A per-player
    baseline keyed on a display name is therefore wrong in both directions at
    once: it splits one player's season in half and it merges two players who
    picked similar names.

    A file with no id segment (an unstamped `cheat.rec`, or a run recorded with
    no guid) falls back to the owner name, marked, because that is all it has.
    """
    m = WHO_RE.match(os.path.basename(path))
    if m:
        return m.group("id"), "%s (%s)" % (m.group("id"), m.group("slug") or "?")
    who = head.get("owner", "?")
    return "name:" + who, "%s [no id in the filename]" % who


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


def pct(xs, p):
    if not xs:
        return float("nan")
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))
    return s[i]


def read_in_rows(path):
    """-> (header dict, [row dicts]).  Rows are the `in` records, in order.

    A row is kept only when it parses in full.  The v6-v8 shape has no <fl> and
    its angles are .v_angle rather than input_angles (v9); both are read, and
    `angver` says which, because a reader that silently mixed them would be
    comparing two different columns across a corpus.
    """
    head, rows = {}, []
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    with fh:
        first = fh.readline().strip()
        if not first.startswith("FTESURF-REC"):
            return None, None
        try:
            head["version"] = int(first.split()[1])
        except (ValueError, IndexError):
            return None, None
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
            if t[0] != "in":
                continue
            if len(t) < 11:
                continue
            try:
                rows.append({
                    "pk": int(t[1]), "mt": int(t[2]), "carry": float(t[3]),
                    "fwd": float(t[4]), "side": float(t[5]), "up": float(t[6]),
                    "pit": float(t[7]), "yaw": float(t[8]), "roll": float(t[9]),
                    "bt": int(float(t[10])),
                    "fl": int(float(t[11])) if len(t) > 11 else -1,
                })
            except ValueError:
                continue
    return head, rows


def cadence(rows):
    """-> (mean ticks per move, mean moves per packet).

    THE CONFOUND EVERY NUMBER BELOW HAS TO BE READ AGAINST.  A move that spans
    two mover ticks has its yaw divided by two, which halves the rate AND halves
    its wobble -- so a client sending fewer, longer commands produces smoother
    rates for an entirely innocent reason, and would climb the plateau figure
    without anything being wrong.  Reported beside the signatures rather than
    corrected for: a correction would bury the confound in a coefficient.
    """
    if len(rows) < 2:
        return float("nan"), float("nan")
    spans = [rows[i]["mt"] - rows[i - 1]["mt"] for i in range(1, len(rows))]
    spans = [s for s in spans if 0 < s <= 8]
    pks = len(set(r["pk"] for r in rows))
    return (sum(spans) / len(spans) if spans else float("nan"),
            len(rows) / pks if pks else float("nan"))


def moves(rows):
    """-> [(ticks, rate, dpitch, side, bt)] for each consecutive pair.

    `rate` is degrees of yaw per MOVER TICK, which is the only rate two runs at
    different tickrates can be compared on.  A pair spanning zero ticks is
    dropped: the mover consumed nothing, so there is no rate to speak of.
    """
    out = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        ticks = b["mt"] - a["mt"]
        if ticks <= 0 or ticks > 8:
            continue
        out.append((ticks,
                    wrap(b["yaw"] - a["yaw"]) / ticks,
                    b["pit"] - a["pit"],
                    a["side"], a["bt"]))
    return out


def plateaus(mv):
    """Maximal runs of consecutive moves at a constant turning rate.

    -> [(length, rate)] for runs of at least PLATEAU_MIN moves.

    THE TURNING TEST IS INSIDE THE RUN AND NOT A FILTER OVER IT.  A player
    holding still produces a long run of rate 0, which is constant and means
    nothing; requiring every move in the run to clear TURN_MIN is what makes the
    length mean "turned at one rate for this long".
    """
    out = []
    run_len, run_rate = 0, 0.0
    for ticks, rate, dpit, side, bt in mv:
        if abs(rate) < TURN_MIN:
            if run_len >= PLATEAU_MIN:
                out.append((run_len, run_rate))
            run_len = 0
            continue
        if run_len and abs(rate - run_rate) <= RATE_TOL:
            run_len += 1
        else:
            if run_len >= PLATEAU_MIN:
                out.append((run_len, run_rate))
            run_len, run_rate = 1, rate
    if run_len >= PLATEAU_MIN:
        out.append((run_len, run_rate))
    return out


def flatpitch(mv):
    """Maximal runs of turning moves whose pitch did not move at all.

    -> [length].  `== 0.0` and not a tolerance: the column is four decimals of
    a quantised short, so "unchanged" is exact or it is nothing.
    """
    out = []
    n = 0
    for ticks, rate, dpit, side, bt in mv:
        if abs(rate) >= TURN_MIN and dpit == 0.0:
            n += 1
        else:
            if n >= PLATEAU_MIN:
                out.append(n)
            n = 0
    if n >= PLATEAU_MIN:
        out.append(n)
    return out


def onsets(mv):
    """Moves between a strafe-key edge and the first turn after it.

    -> [offset in moves].  The edge is `side` changing sign or leaving zero,
    which is A or D pressed; the answer is how many moves passed before the yaw
    moved.  A run that was already turning through the edge contributes 0, which
    is correct and is why the SPREAD is the statistic rather than the mean: a
    player mid-strafe is not answering the key, and both kinds of zero are in
    there.  Only the variance separates a hand from a script.
    """
    out = []
    prev = 0.0
    pending = -1
    for i, (ticks, rate, dpit, side, bt) in enumerate(mv):
        edge = (side != 0.0 and (prev == 0.0 or (side > 0) != (prev > 0)))
        prev = side
        if edge:
            pending = i
        if pending >= 0 and abs(rate) >= TURN_MIN:
            out.append(i - pending)
            pending = -1
    return out


def inject_turn(mv, rate, span):
    """POSITIVE CONTROL: overwrite every `span`-th stretch with a constant rate.

    NOT A SIMULATION, and the same caveat strafestats.py's --inject carries: a
    turn that actually happened would have changed where the player went and
    therefore every later row.  What it asks is narrower and is the only thing a
    detector can be held to: given a stretch that IS exactly constant, does the
    estimator find it, and does the honest remainder stay quiet?
    """
    out = list(mv)
    i = 0
    while i + span <= len(out):
        for j in range(i, i + span):
            ticks, _r, dpit, side, bt = out[j]
            out[j] = (ticks, rate, 0.0, side, bt)
        i += span * 3          # one injected stretch, two honest ones
    return out


def analyse(path, inject=None):
    head, rows = read_in_rows(path)
    if head is None or not rows:
        return None
    mv = moves(rows)
    if len(mv) < 20:
        return None
    if inject:
        mv = inject_turn(mv, inject[0], inject[1])

    pl = plateaus(mv)
    fp = flatpitch(mv)
    on = onsets(mv)
    turning = [m for m in mv if abs(m[1]) >= TURN_MIN]
    key, label = player_key(path, head)
    tpm, mpp = cadence(rows)
    return {
        "ticks_per_move": tpm,
        "moves_per_packet": mpp,
        "path": path,
        "map": head.get("map", "?"),
        "owner": head.get("owner", "?"),
        "pkey": key,
        "plabel": label,
        "version": head["version"],
        "angver": "input_angles" if head["version"] >= 9 else "v_angle",
        "moves": len(mv),
        "turning": len(turning),
        "plateaus": pl,
        "plat_max": max((n for n, r in pl), default=0),
        "plat_moves": sum(n for n, r in pl),
        "flat": fp,
        "flat_max": max(fp, default=0),
        "flat_moves": sum(fp),
        "onsets": on,
    }


def report(r):
    print("%-40s %-16s n %5d  turning %5d  (%s)"
          % (os.path.basename(r["path"])[:40], r["map"][:16], r["moves"],
             r["turning"], r["angver"]))
    print("      plateau    longest %4d moves   %4d moves in runs >= %d (%.2f%% of turning)"
          % (r["plat_max"], r["plat_moves"], PLATEAU_MIN,
             100.0 * r["plat_moves"] / r["turning"] if r["turning"] else 0.0))
    print("      flatpitch  longest %4d moves   %4d moves in runs >= %d (%.2f%%)"
          % (r["flat_max"], r["flat_moves"], PLATEAU_MIN,
             100.0 * r["flat_moves"] / r["turning"] if r["turning"] else 0.0))
    if r["onsets"]:
        print("      onset      n %4d  median %.1f  sd %.2f  zero-offset %.1f%%"
              % (len(r["onsets"]), median(r["onsets"]), sd(r["onsets"]),
                 100.0 * sum(1 for x in r["onsets"] if x == 0) / len(r["onsets"])))
    print()


def pooled(results, label="POOLED"):
    pl = [n for r in results for n, _rate in r["plateaus"]]
    fp = [n for r in results for n in r["flat"]]
    on = [x for r in results for x in r["onsets"]]
    turning = sum(r["turning"] for r in results)
    mv = sum(r["moves"] for r in results)
    tpm = mean([r["ticks_per_move"] for r in results if r["ticks_per_move"] == r["ticks_per_move"]])
    mpp = mean([r["moves_per_packet"] for r in results if r["moves_per_packet"] == r["moves_per_packet"]])
    print("%s over %d recordings: %d moves, %d turning" % (label, len(results), mv, turning))
    print("  cadence    %.3f mover ticks per move, %.3f moves per packet -- read "
          "the rest against this" % (tpm, mpp))
    if not turning:
        print("  nothing to measure -- no turning moves\n")
        return
    print("  plateau    runs >= %d: %d   longest %d   moves in them %.2f%% of turning"
          % (PLATEAU_MIN, len(pl), max(pl, default=0),
             100.0 * sum(pl) / turning))
    if pl:
        print("             length  median %.1f  p90 %.0f  p99 %.0f  max %d"
              % (median(pl), pct(pl, 90), pct(pl, 99), max(pl)))
    print("  flatpitch  runs >= %d: %d   longest %d   moves in them %.2f%% of turning"
          % (PLATEAU_MIN, len(fp), max(fp, default=0),
             100.0 * sum(fp) / turning))
    if fp:
        print("             length  median %.1f  p90 %.0f  p99 %.0f  max %d"
              % (median(fp), pct(fp, 90), pct(fp, 99), max(fp)))
    if on:
        print("  onset      n %d  median %.1f  sd %.2f  p90 %.0f  zero-offset %.1f%%"
              % (len(on), median(on), sd(on), pct(on, 90),
                 100.0 * sum(1 for x in on if x == 0) / len(on)))
    print()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--pooled", action="store_true",
                    help="one distribution over every file: the honest floor")
    ap.add_argument("--by-player", action="store_true",
                    help="pool per `owner`, which is what a season baseline "
                         "looks like -- a player against the floor, not a run "
                         "against a threshold")
    ap.add_argument("--inject", action="store_true",
                    help="SYNTHETIC POSITIVE CONTROL: overwrite one stretch in "
                         "three with an exactly constant turn and re-measure")
    ap.add_argument("--inject-rate", type=float, default=2.0,
                    help="degrees per tick for --inject (default 2.0, about "
                         "200 deg/s at a 100 Hz tick)")
    ap.add_argument("--inject-span", type=int, default=12,
                    help="moves per injected stretch (default 12)")
    a = ap.parse_args(argv)

    files = a.files or sorted(glob.glob(os.path.join(RUNS, "**", "*.rec"), recursive=True))
    if not files:
        print("no .rec files found under %s" % RUNS)
        return 1

    inj = (a.inject_rate, a.inject_span) if a.inject else None
    if inj:
        print("SYNTHETIC POSITIVE CONTROL -- %.2f deg/tick for %d moves in every "
              "%d\n" % (a.inject_rate, a.inject_span, a.inject_span * 3))

    results = [analyse(f, inject=inj) for f in files]
    results = [r for r in results if r]
    if not results:
        print("%d file(s) read, none with an input trace of 20+ moves "
              "(`in` rows are QC build 82 and later)" % len(files))
        return 1

    if a.by_player:
        by, labels = {}, {}
        for r in results:
            by.setdefault(r["pkey"], []).append(r)
            labels.setdefault(r["pkey"], set()).add(r["plabel"])
        for who in sorted(by, key=lambda w: -sum(x["turning"] for x in by[w])):
            pooled(by[who], "PLAYER %s" % " / ".join(sorted(labels[who])))
        return 0

    if a.pooled:
        pooled(results)
        return 0

    for r in results:
        report(r)
    print("%d recording(s) read, %d with an input trace" % (len(files), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
