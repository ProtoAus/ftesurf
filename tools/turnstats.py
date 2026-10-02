#!/usr/bin/env python3
"""
turnstats.py -- Layer 3 signatures about the INPUT's SHAPE, measured on the
`in` rows a .rec carries (QC build 82 and later).

A CLASSIFIER, NOT AN ACCUSATION.  Turn binds (+left/+right at cl_yawspeed) are
allowed in this game.  This tool says which stretches of a recording have the
shape of one and which have a mouse behind them; it prints distributions and
never a verdict.

IT READS `in` ROWS, NOT SAMPLES.  An `in` row carries the usercmd's angles at
%.4f, which recovers the 16-bit wire short exactly (quantum 360/65536 deg);
a sample carries yaw at %.2f and cannot tell a constant rate from a nearly
constant one.  Everything here is in whole quanta per mover tick.

THE SIGNATURES

  plateau    a maximal run of consecutive moves turning at >= 2 quanta/tick
             whose integer rate stays within one quantum of the run's first
             move.  INTEGER, because a held key arrives as a dither: at tick
             0.015 cl_yawspeed 60 is 163.84 quanta/tick, so the wire alternates
             163 and 164.  The earlier float comparator (one-quantum tolerance
             on a %.4f-derived rate) cut that dither into pieces: on the file
             below it found a longest plateau of 6 where this one finds 19.
  mc join    Patch 376 `mc` rows carry the client's cumulative mouse counts.
             A plateau whose span moved no counts is keyboard-shaped; one with
             counts behind it is a mouse at constant speed, reported apart and
             never merged.  No `mc` rows: the file cannot be joined, and that
             is said, not assumed (an older recording is not keyboard-only).
  flatpitch  turning moves whose pitch did not move by a single quantum.
  onset      moves from a strafe-key edge to the first turn after it.  On the
             first corpus the turn LED the key (most offsets were zero), so only
             the spread could carry anything; no edge definition has yet.

POSITIVE CONTROL: a real keyboard-turn recording, not an injection.  The old
--inject wrote an unquantised constant float rate, a shape no file can hold,
so it tested the comparator against nothing; it is gone.

MEASURED, data/resume/surf_colin_blaster_69000/@local/save000/run.rec
(keyboard-only play: pitch 0.0000 on every row, mouse counts never move):
7830 `in` rows, 7829 moves, 197 turning, tick 0.015.
    integer comparator   11 plateaus >= 4, longest 19, 82 moves = 41.6% of
                         turning; every plateau rate is +-163 or +-164
                         (reference 163.84); of the 33 moves inside plateaus
                         >= 10, 28 (84.8%) are at exactly 164
    float comparator     11 plateaus, longest 6, 52 moves = 26.4%
    mc join              921 mc rows, all 11 plateaus at zero counts

THE CORPUS FLOOR IS NOT MEASURED.  The figures the earlier docstring carried
(45 recordings) came from the float comparator and are withdrawn; re-measure
on the Pi's corpus with --pooled and --by-player before building on this.

Usage:
    python tools/turnstats.py                      # every .rec under data/runs
    python tools/turnstats.py <file.rec> [...]
    python tools/turnstats.py --pooled             # one distribution over all
    python tools/turnstats.py --by-player          # per player id
"""

import argparse
import bisect
import collections
import glob
import math
import os
import re
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(SURFDIR, "ftesurf", "data", "runs")

# The wire quantum: usercmd angles travel as shorts.
QUANT = 360.0 / 65536.0

# `mc` counts are summed since the client started and wrap here (grammar block
# over SV_RecOpen, sv_timer.qc).
MC_MOD = 1 << 20

# Quanta per tick.  A move at or above TURN_MIN is turning (about 1.1 deg/s at
# a 100 Hz tick); a plateau holds while each move is within RATE_TOL of the
# run's FIRST move, which keeps a 163/164 dither in one run and splits 163/165.
TURN_MIN = 2
RATE_TOL = 1

# A plateau shorter than this is not evidence of anything -- two moves at the
# same rate happen constantly.
PLATEAU_MIN = 4

# sv_timer.qc SV_RecLine's <bt>: 1 jump, 2 duck, 4 speed.  NOT input_buttons --
# see the grammar block's essay on why those three are per-bit fields.
BT_JUMP = 1

# Reference turn rates: cl_yawspeed values worth printing beside the histogram,
# and cl_anglespeedkey, which +speed multiplies them by.
YAWSPEEDS = (60, 140)
ANGLESPEEDKEY = 1.5


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


def angle_q(deg):
    """The wire short behind a %.4f angle column, in [0, 65536)."""
    return int(round(deg * 65536.0 / 360.0)) % 65536


def wrap16(d):
    d %= 65536
    return d - 65536 if d >= 32768 else d


def wrap20(d):
    d %= MC_MOD
    return d - MC_MOD if d >= MC_MOD >> 1 else d


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


def read_rec(path):
    """-> (header dict, [`in` rows], [`mc` rows]), or (None, None, None).

    A row is kept only when it parses in full.  The v6-v8 shape has no <fl> and
    its angles are .v_angle rather than input_angles (v9); both are read, and
    `angver` says which, because a reader that silently mixed them would be
    comparing two different columns across a corpus.
    """
    head, rows, mcs = {}, [], []
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None, None, None
    with fh:
        first = fh.readline().strip()
        if not first.startswith("FTESURF-REC"):
            return None, None, None
        try:
            head["version"] = int(first.split()[1])
        except (ValueError, IndexError):
            return None, None, None
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
            try:
                if t[0] == "in" and len(t) >= 11:
                    rows.append({
                        "pk": int(t[1]), "mt": int(t[2]), "carry": float(t[3]),
                        "fwd": float(t[4]), "side": float(t[5]), "up": float(t[6]),
                        "pit": float(t[7]), "yaw": float(t[8]), "roll": float(t[9]),
                        "bt": int(float(t[10])),
                        "fl": int(float(t[11])) if len(t) > 11 else -1,
                    })
                elif t[0] == "mc" and len(t) >= 8:
                    # mc <pk> <row> <rx> <ry> <ax> <ay> <rej>, counts at %.10g
                    mcs.append({
                        "pk": int(t[1]), "row": int(t[2]),
                        "rx": int(float(t[3])), "ry": int(float(t[4])),
                        "ax": int(float(t[5])), "ay": int(float(t[6])),
                        "rej": int(float(t[7])),
                    })
            except ValueError:
                continue
    return head, rows, mcs


def tick_of(head):
    for k in ("movetickrate", "tickrate"):
        try:
            return float(head[k])
        except (KeyError, ValueError):
            pass
    return None


def ref_rates(tick):
    """-> [(cl_yawspeed, quanta per tick)]: 163.84 and 382.29 at tick 0.015."""
    return [(ys, ys * tick / QUANT) for ys in YAWSPEEDS]


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


# One move: `row` indexes its first `in` row; `dq`/`dp` are yaw/pitch in wire
# quanta; `r` is quanta per mover tick.  A float rate is dq * QUANT / ticks.
Move = collections.namedtuple("Move", "row ticks dq r dp side bt")

# One plateau: `start` indexes moves(), `rate` is the FIRST move's r.
Plateau = collections.namedtuple("Plateau", "start n rate")


def moves(rows):
    """-> [Move] for each consecutive pair of rows spanning 1..8 mover ticks.

    A pair spanning zero ticks is dropped: the mover consumed nothing, so there
    is no rate to speak of.
    """
    out = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        ticks = b["mt"] - a["mt"]
        if ticks <= 0 or ticks > 8:
            continue
        dq = wrap16(angle_q(b["yaw"]) - angle_q(a["yaw"]))
        out.append(Move(i - 1, ticks, dq, int(round(dq / ticks)),
                        wrap16(angle_q(b["pit"]) - angle_q(a["pit"])),
                        a["side"], a["bt"]))
    return out


def plateaus(mv):
    """Maximal runs of consecutive turning moves at one integer rate.

    -> [Plateau] for runs of at least PLATEAU_MIN moves.  Every move in the run
    clears TURN_MIN (a still player's long run at rate 0 means nothing) and sits
    within RATE_TOL of the run's first move; a dropped pair (moves() skipped a
    row) ends the run, since the moves either side of it are not consecutive.
    """
    out = []
    start = n = r0 = 0
    for k, m in enumerate(mv):
        joins = (n > 0 and m.row == mv[k - 1].row + 1
                 and abs(m.r) >= TURN_MIN and abs(m.r - r0) <= RATE_TOL)
        if joins:
            n += 1
            continue
        if n >= PLATEAU_MIN:
            out.append(Plateau(start, n, r0))
        if abs(m.r) >= TURN_MIN:
            start, n, r0 = k, 1, m.r
        else:
            n = 0
    if n >= PLATEAU_MIN:
        out.append(Plateau(start, n, r0))
    return out


def span_rows(mv, p):
    """-> (first, last) `in` row indices a plateau covers, inclusive."""
    return mv[p.start].row, mv[p.start + p.n - 1].row + 1


def counts_index(mcs):
    """-> (sorted pks, ax per pk): the FIRST mc row of each packet is in force
    for it and for every later packet until the next mc row."""
    by = {}
    for m in mcs:
        by.setdefault(m["pk"], m["ax"])
    pks = sorted(by)
    return pks, [by[p] for p in pks]


def counts_at(idx, pk):
    """ax in force for packet `pk`, or None before the first mc row."""
    pks, axs = idx
    i = bisect.bisect_right(pks, pk) - 1
    return axs[i] if i >= 0 else None


def join_counts(rows, mcs, mv, pl):
    """-> [dax or None], one per plateau: the change in `ax` over its rows.

    Move s is rows s -> s+1, so its counts are ax(pk of s+1) - ax(pk of s); the
    run's total is the difference between its last row's packet and its first.
    None when the run begins before the first mc row: not joined, which is a
    third answer and not either of the other two.
    """
    idx = counts_index(mcs)
    out = []
    for p in pl:
        first, last = span_rows(mv, p)
        a = counts_at(idx, rows[first]["pk"])
        b = counts_at(idx, rows[last]["pk"])
        out.append(None if a is None or b is None else wrap20(b - a))
    return out


def keyboard_spans(rows, mcs):
    """-> [(first_row, last_row, rate)] for plateaus whose span moved no mouse
    counts, so another tool can exclude them from mouse statistics.  Row indices
    index the `in` rows, inclusive.  Empty when the file has no mc rows: it
    cannot be joined, and an unjoined file is not a keyboard-only one."""
    if not mcs:
        return []
    mv = moves(rows)
    pl = plateaus(mv)
    out = []
    for p, dax in zip(pl, join_counts(rows, mcs, mv, pl)):
        if dax == 0:
            out.append(span_rows(mv, p) + (p.rate,))
    return out


def flatpitch(mv):
    """Maximal runs of turning moves whose pitch did not move at all.

    -> [length].  `dp == 0` on the recovered shorts: the column is a quantised
    short at four decimals, so "unchanged" is exact or it is nothing.
    """
    out = []
    n = 0
    for m in mv:
        if abs(m.r) >= TURN_MIN and m.dp == 0:
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
    for i, m in enumerate(mv):
        edge = (m.side != 0.0 and (prev == 0.0 or (m.side > 0) != (prev > 0)))
        prev = m.side
        if edge:
            pending = i
        if pending >= 0 and abs(m.r) >= TURN_MIN:
            out.append(i - pending)
            pending = -1
    return out


def analyse(path):
    head, rows, mcs = read_rec(path)
    if head is None or not rows:
        return None
    mv = moves(rows)
    if len(mv) < 20:
        return None

    pl = plateaus(mv)
    dax = join_counts(rows, mcs, mv, pl) if mcs else [None] * len(pl)
    fp = flatpitch(mv)
    on = onsets(mv)
    turning = sum(1 for m in mv if abs(m.r) >= TURN_MIN)
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
        "tick": tick_of(head),
        "moves": len(mv),
        "turning": turning,
        # (length, rate in quanta/tick, ax moved over the run or None)
        "plateaus": [(p.n, p.rate, d) for p, d in zip(pl, dax)],
        "plat_max": max((p.n for p in pl), default=0),
        "plat_moves": sum(p.n for p in pl),
        "mc_rows": len(mcs),
        "flat": fp,
        "flat_max": max(fp, default=0),
        "flat_moves": sum(fp),
        "onsets": on,
    }


def classify(plats):
    """-> (zero counts, with counts, not joined) lists of (n, rate, dax)."""
    return ([p for p in plats if p[2] == 0],
            [p for p in plats if p[2] is not None and p[2] != 0],
            [p for p in plats if p[2] is None])


def frac(moves_in, turning):
    """The share line's tail; says so when fewer than PLATEAU_MIN moves turn."""
    if turning < PLATEAU_MIN:
        return "cannot measure: %d turning moves, fewer than %d" % (turning, PLATEAU_MIN)
    return "%.2f%% of turning" % (100.0 * moves_in / turning)


def hist(plats):
    """-> 'rate xcount ...' over plateau rates, or 'none'."""
    c = collections.Counter(p[1] for p in plats)
    return "  ".join("%d x%d" % (r, n) for r, n in sorted(c.items())) or "none"


def rate_lines(plats, joined, indent):
    """The rate histogram per mc-join class; the classes are never merged."""
    kb, mouse, unj = classify(plats)
    out = []
    if not joined:
        out.append("%srates (not joined)   %s" % (indent, hist(unj)))
        return out
    out.append("%srates (zero counts)  %s" % (indent, hist(kb)))
    if mouse:
        out.append("%srates (with counts)  %s" % (indent, hist(mouse)))
    if unj:
        out.append("%srates (not joined)   %s" % (indent, hist(unj)))
    return out


def ref_line(tick, indent):
    if tick is None:
        return "%sreference  no tickrate in the header; reference rates not computed" % indent
    rr = ref_rates(tick)
    return ("%sreference  tick %g: " % (indent, tick)
            + "  ".join("cl_yawspeed %d = %.2f" % (ys, q) for ys, q in rr)
            + " quanta/tick; x%.1f under +speed = " % ANGLESPEEDKEY
            + "  ".join("%.2f" % (q * ANGLESPEEDKEY) for ys, q in rr))


def join_line(mc_rows, plats, indent):
    if not mc_rows:
        return ["%smc join    no mc rows: cannot join (client before Patch 376); "
                "keyboard-shaped spans: none" % indent]
    kb, mouse, unj = classify(plats)
    s = ("%smc join    %d mc rows: %d runs at zero counts (keyboard-shaped%s), "
         "%d with counts (mouse at constant speed%s)"
         % (indent, mc_rows, len(kb),
            ", longest %d" % max(p[0] for p in kb) if kb else "",
            len(mouse),
            ", longest %d" % max(p[0] for p in mouse) if mouse else ""))
    if unj:
        s += ", %d before the first mc row (not joined)" % len(unj)
    out = [s]
    for n, rate, dax in mouse[:6]:
        out.append("%s           with counts: %d moves at %d/tick, ax %+d" % (indent, n, rate, dax))
    if len(mouse) > 6:
        out.append("%s           ... and %d more with counts" % (indent, len(mouse) - 6))
    return out


def report(r):
    ind = "      "
    print("%-40s %-16s n %5d  turning %5d  (%s)"
          % (os.path.basename(r["path"])[:40], r["map"][:16], r["moves"],
             r["turning"], r["angver"]))
    if r["turning"] < PLATEAU_MIN:
        print("%splateau    %s" % (ind, frac(0, r["turning"])))
    else:
        print("%splateau    longest %4d moves   %4d moves in %d runs >= %d (%s)"
              % (ind, r["plat_max"], r["plat_moves"], len(r["plateaus"]),
                 PLATEAU_MIN, frac(r["plat_moves"], r["turning"])))
    for line in rate_lines(r["plateaus"], r["mc_rows"] > 0, ind + "           "):
        print(line)
    print(ref_line(r["tick"], ind))
    for line in join_line(r["mc_rows"], r["plateaus"], ind):
        print(line)
    if r["turning"] < PLATEAU_MIN:
        print("%sflatpitch  %s" % (ind, frac(0, r["turning"])))
    else:
        print("%sflatpitch  longest %4d moves   %4d moves in runs >= %d (%s)"
              % (ind, r["flat_max"], r["flat_moves"], PLATEAU_MIN,
                 frac(r["flat_moves"], r["turning"])))
    if r["onsets"]:
        print("%sonset      n %4d  median %.1f  sd %.2f  zero-offset %.1f%%"
              % (ind, len(r["onsets"]), median(r["onsets"]), sd(r["onsets"]),
                 100.0 * sum(1 for x in r["onsets"] if x == 0) / len(r["onsets"])))
    print()


def pooled(results, label="POOLED"):
    plats = [p for r in results for p in r["plateaus"]]
    pl = [p[0] for p in plats]
    fp = [n for r in results for n in r["flat"]]
    on = [x for r in results for x in r["onsets"]]
    turning = sum(r["turning"] for r in results)
    mv = sum(r["moves"] for r in results)
    tpm = mean([r["ticks_per_move"] for r in results if r["ticks_per_move"] == r["ticks_per_move"]])
    mpp = mean([r["moves_per_packet"] for r in results if r["moves_per_packet"] == r["moves_per_packet"]])
    joined = [r for r in results if r["mc_rows"]]
    print("%s over %d recordings: %d moves, %d turning" % (label, len(results), mv, turning))
    print("  cadence    %.3f mover ticks per move, %.3f moves per packet -- read "
          "the rest against this" % (tpm, mpp))
    if turning < PLATEAU_MIN:
        print("  plateau    %s\n" % frac(0, turning))
        return
    print("  plateau    runs >= %d: %d   longest %d   moves in them %s"
          % (PLATEAU_MIN, len(pl), max(pl, default=0), frac(sum(pl), turning)))
    if pl:
        print("             length  median %.1f  p90 %.0f  p99 %.0f  max %d"
              % (median(pl), pct(pl, 90), pct(pl, 99), max(pl)))
    # Files without mc rows cannot be joined; their runs are the not-joined
    # class, beside the joined files' classes and never merged into them.
    for line in rate_lines([p for r in joined for p in r["plateaus"]], True, "             "):
        print(line)
    unjoined = [p for r in results if not r["mc_rows"] for p in r["plateaus"]]
    if unjoined:
        print("             rates (not joined, %d files without mc rows)  %s"
              % (len(results) - len(joined), hist(unjoined)))
    for tick in sorted(set(r["tick"] for r in results), key=lambda t: (t is None, t)):
        print(ref_line(tick, "  "))
    if joined:
        kb, mouse, unj = classify([p for r in joined for p in r["plateaus"]])
        print("  mc join    %d of %d files have mc rows: %d runs at zero counts "
              "(keyboard-shaped), %d with counts (mouse at constant speed), "
              "%d before their first mc row (not joined)"
              % (len(joined), len(results), len(kb), len(mouse), len(unj)))
    else:
        print("  mc join    no file has mc rows: cannot join; keyboard-shaped spans: none")
    print("  flatpitch  runs >= %d: %d   longest %d   moves in them %s"
          % (PLATEAU_MIN, len(fp), max(fp, default=0), frac(sum(fp), turning)))
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
                    help="one distribution over every file")
    ap.add_argument("--by-player", action="store_true",
                    help="pool per player id, which is what a season baseline "
                         "looks like -- a player against the pool, not a run "
                         "against a threshold")
    a = ap.parse_args(argv)

    files = a.files or sorted(glob.glob(os.path.join(RUNS, "**", "*.rec"), recursive=True))
    if not files:
        print("no .rec files found under %s" % RUNS)
        return 1

    results = [analyse(f) for f in files]
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
