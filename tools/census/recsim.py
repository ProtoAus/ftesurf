#!/usr/bin/env python3
"""recsim.py -- cross-run similarity over the SERVER-WRITTEN move columns.

BACKLOG item F.  The question: can two recordings be told to be the same
performance, from columns the server wrote and a client cannot reach?

WHY THESE COLUMNS AND NOT THE ANGLES.  An `in` row is

    in <pk> <mt> <carry> <fwd side up> <pit> <yaw> <roll> <bt> [<fl>]

and the grammar block over SV_RecOpen in sv_timer.qc is authoritative for it.
The angles are continuous and would drift between two honest playbacks of the
same recording, because the client renders between samples.  `<fwd side up>` and
`<bt>` are not: forwardmove/sidemove/upmove are the player's intent quantised to
the move values, and `<bt>` is exactly three bits (1 jump, 2 duck, 4 speed).  A
playback reproduces them EXACTLY.  Two honest runs of one map by one player do
not, because nobody plays a map twice identically.

WHY THIS IS THE STRONGEST POSITION IN THE EVIDENCE CHAIN.  The `.rec` is written
by the server.  No client-side artifact is involved, so there is nothing on the
attacker's side to forge -- contrast the `.view` and the `.hid`, which the client
writes and signs, and the receipt, which the client also writes.  A duplicate
found here is a duplicate the server itself recorded twice.

THE STATISTIC THAT SEPARATES IS `match`, NOT `cover`, AND THAT WAS MEASURED
RATHER THAN CHOSEN.  Over 20 independent long runs (>=2000 moves, all different
sha256) giving 376 ordered negative pairs, and synthetic positives made by
re-parsing one file and perturbing it:

    exact replay, shifted epoch        match 1.0000   cover 1.0000
    replay, first half only (trimmed)  match 1.0000   cover 0.4998
    replay, ONE move perturbed at 1%   match 0.9997   cover 0.0098
    replay, 0.1% of moves perturbed    match 0.9990   cover 0.0047
    replay, 1% of moves perturbed      match 0.9900   cover 0.0006
    --- 376 pairs of genuinely different runs ---
    NEGATIVE max                       match 0.5242   cover 0.0078
    NEGATIVE median                    match 0.1660   cover 0.0000

So `match` separates 1.0000 against 0.5242 -- a margin of 1.91x, with the
highest negative being two runs of the same map that share a common opening
(holding forward out of a start box, standing idle) and agree nowhere else.
`cover` -- the exact contiguous prefix -- separates even further on an exact
replay (1.0000 vs 0.0078) but IS THE WRONG DISCRIMINATOR, for two reasons the
synthetics found and the real corpus could not:
  * it is BRITTLE.  One perturbed move at 1% of the run drops it from 1.0000 to
    0.0098, so a playback tool that edits a single input anywhere early reads as
    completely unrelated.  A discriminator that fails on the weakest version of
    the attack is not a discriminator.
  * it MISSES THE TRIMMED PLAYBACK, which is the cheap attack: submit the first
    half of someone else's recording.  cover reads 0.4998 -- below any threshold
    anyone would set -- while match still reads 1.0000, correctly, because every
    compared row agrees.
Both are reported.  `match` is the one a gate would use; `cover` is diagnostic
(it says whether the agreement is contiguous from the start or scattered).

WHAT IT DOES NOT SEE, stated up front rather than discovered later:
  * a run that POSTS is the only run that keeps a `.rec` at all --
    SV_RecKeepEvidence returns early on rec_rec_posts <= 0, so a main-leg run
    walked away from leaves no file to compare.  37 of this tree's 38 receipts
    are that shape.
  * a re-recording tool that perturbs the move stream defeats it.  This catches
    PLAYBACK, not a TAS that re-plays with edits -- which is the honest limit and
    the same limit every similarity check has.
  * it cannot tell two runs apart that are legitimately identical, e.g. a map
    whose only route is one jump.  That is why the output is a measurement and
    the threshold is a separate decision.

Usage:
  python tools/census/recsim.py census [--root DIR]     what is comparable
  python tools/census/recsim.py pairs  [--root DIR] [--max N] [--per-map N]
                                                        the separation measurement
  python tools/census/recsim.py one A B                 one pair, in detail
"""
import argparse
import collections
import glob
import io
import locale
import hashlib
import os
import re
import sys

# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

SKIPPED = []

# THE SHORTEST RUN WORTH COMPARING -- a parameter with a measured reason, not a
# constant with an assumed one.  This tree holds real runs of 7, 8, 9 and 13
# moves: stubs a harness produced by walking out of a start box.  Two 9-move runs
# agree over all 9 and report a perfect score, and six of the ten "closest
# negative pairs" the first cut reported came from bhop_eazy files that short.
# So the false-positive risk it was pointing at was an artifact of the corpus and
# not a property of the metric.  Nine quaternions of move+buttons is not enough
# to identify a performance.  A pair below this is NOT COMPARED and is counted
# separately, rather than being reported as a low score -- a low score for a pair
# that could not have been judged is the same false reading as a high one, and
# both are worse than a count of what was skipped.
MIN_LEN = 50

# WHO SET IT, read out of the filename.  FS_RunLeaf's grammar (sh_defs.qc) is
#   <ticks7>_<who>_<tag>.<ext>     with who = <name>-<FS_GuidId>
# and FS_GuidId is sha256(guid)'s first FS_WHO_IDLEN hex chars -- stable across
# renames BECAUSE THE GUID IS.  So the hex tail, not the name, is the identity:
# `proto-26c95e00`, `kap-26c95e00`, `1proto-26c95e00` and `player-26c95e00` are
# ONE INSTALL under four netnames (measured on the fleet corpus: 53 of its 64
# files carry 26c95e00), because a player's guid is the `qkey` in the install
# root and two clients from one install are one player to the server.
#
# WHY A SIMILARITY CENSUS NEEDS THIS.  A negative pair is "two runs that are not
# a playback", and the hardest honest population is ONE PLAYER replaying ONE MAP
# -- the same person's route, the same habits, the same start.  A corpus that is
# mostly one identity therefore measures the pessimistic case, and one that is
# mostly cross-identity measures the easy one.  Printing a single negative max
# hides which was measured, and the difference is the whole calibration.
WHO_RE = re.compile(r"([0-9a-f]{8})$", re.IGNORECASE)


def who_of(path):
    """The identity hex of a run's filename, or '' when it carries none.

    '' is its own answer and not a failure: every recording written before build
    66 has no player segment at all, and a local run has no identity to name.
    Those pairs are counted as UNKNOWN rather than folded into either side, so a
    pre-66 corpus reports that it cannot answer instead of reporting agreement.

    THE HEX IS MATCHED WITHOUT A REQUIRED '-' IN FRONT, and that is deliberate
    even though it costs an ambiguity.  The segment is `<name>-<hex>`, or the bare
    `<hex>` when the name slugs to "" (FS_PlayerSeg, sh_defs.qc: a name of colour
    codes, unicode or punctuation), and a dash-anchored pattern reads that bare id
    as no identity.  Every `<name>-<hex>` reads the same under both patterns.
    The cost is that a name ENDING in 8 hex characters and no guid (`player-12345678`,
    where 12345678 is all the name there is) reads as an identity; that is a
    census imprecision in the safe direction -- it can merge two identities into
    one bucket and so UNDER-report cross-identity pairs, never invent them -- and
    it is why a figure quoted from the split always says how many pairs were
    unknown.
    """
    base = os.path.basename(path.replace(os.sep, "/"))
    for part in base.rsplit(".", 1)[0].split("_"):
        mo = WHO_RE.search(part)
        if mo:
            return mo.group(1).lower()
    return ""


class Rec(object):
    __slots__ = ("path", "map", "leg", "ver", "tickrate", "moves", "btns",
                 "mt", "end_ticks")

    def __init__(self, path):
        self.path = path
        self.map = ""
        self.leg = ""
        self.ver = 0
        self.tickrate = 0.0
        self.moves = []       # (fwd, side, up) per simulated move
        self.btns = []        # bt per simulated move
        self.mt = []          # <mt> per move: the tick epoch, for alignment
        self.end_ticks = None


class MalformedRec(ValueError):
    """A required move-stream value cannot be read safely."""


# Capability marker for collectors that must never fall back to unbounded reads.
BOUNDED_INPUT_VERSION = 1


class SourceLimit(ValueError):
    """The source exceeds an operational ingestion budget, not a player fault."""


def parse_rec(path, strict=False, max_bytes=None, max_moves=None):
    """Read move columns; optional limits bound capture and retained move rows."""
    try:
        return _parse_rec(path, max_bytes=max_bytes, max_moves=max_moves)
    except (OSError, MalformedRec, SourceLimit) as exc:
        if strict:
            raise
        SKIPPED.append((path, str(exc)))
        return None


def _parse_rec(path, max_bytes=None, max_moves=None):
    r = Rec(path)
    body = False
    if max_bytes is None:
        fh = open(path, "r", errors="replace")
    else:
        # Bound the actual capture, not stat size: files can grow during a read.
        # StringIO preserves the text reader's universal newline/locale behavior.
        with open(path, "rb") as raw:
            data = raw.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise SourceLimit("source byte limit reached")
        fh = io.StringIO(data.decode(locale.getpreferredencoding(False), errors="replace"),
                         newline=None)
    with fh:
        for line in fh:
            if not body:
                if line.startswith("FTESURF-REC"):
                    try:
                        r.ver = int(line.split()[1])
                    except (IndexError, ValueError):
                        r.ver = 0
                elif line.startswith("map "):
                    f = line.split()
                    if len(f) < 2:
                        raise MalformedRec("malformed map header")
                    r.map = f[1].strip()
                elif line.startswith("track ") or line.startswith("leg "):
                    f = line.split()
                    if len(f) > 1:
                        r.leg = f[1].strip()
                elif line.startswith("tickrate"):
                    try:
                        r.tickrate = float(line.split()[1])
                    except (IndexError, ValueError):
                        pass
                elif line.startswith("begin"):
                    body = True
                continue
            if line.startswith("in "):
                if max_moves is not None and len(r.moves) >= max_moves:
                    raise SourceLimit("source move limit reached")
                f = line.split()
                # in <pk> <mt> <carry> <fwd side up> <pit> <yaw> <roll> <bt> [<fl>]
                #     0    1    2       3   4   5    6     7    8     9    10
                if len(f) < 11:
                    raise MalformedRec("malformed input row")
                try:
                    mt = int(float(f[2]))
                    move = (int(float(f[4])), int(float(f[5])), int(float(f[6])))
                    btn = int(float(f[10]))
                except (ValueError, OverflowError) as exc:
                    raise MalformedRec("malformed input row") from exc
                r.mt.append(mt)
                r.moves.append(move)
                r.btns.append(btn)
            elif line.startswith("end "):
                f = line.split()
                if len(f) > 1:
                    try:
                        r.end_ticks = int(float(f[1]))
                    except (ValueError, OverflowError):
                        pass
    if not r.moves:
        return None
    return r


def derive_leg(path, r):
    """The map/leg identity.  The header's own `map` is authoritative when
    present; the directory layout is data/runs/<map>/<leg>/... and the Momentum
    imports are data/momentum/<map>/<legdir>/...  Both are used because a file
    whose header omits `map` is still comparable to its neighbours."""
    p = path.replace(os.sep, "/")
    parts = p.split("/")
    m = r.map
    leg = r.leg
    if not m:
        for i, seg in enumerate(parts):
            if seg in ("runs", "momentum", "evidence", "online", "saves") and i + 1 < len(parts):
                m = parts[i + 1]
                if i + 2 < len(parts) and parts[i + 2].endswith(".rec"):
                    leg = ""
                elif i + 2 < len(parts):
                    leg = parts[i + 2]
                break
    return m or "?", leg or ""


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------

def stream(r):
    """The comparable stream: move triple and buttons, as one tuple per move.

    Angles and timing are deliberately EXCLUDED -- see the module docstring.  A
    playback reproduces this exactly; an honest re-play does not.
    """
    if not len(r.mt) == len(r.moves) == len(r.btns):
        raise MalformedRec("incomplete move stream")
    return list(zip(r.moves, r.btns))


def best_offset(a, b, max_shift=None, min_len=0):
    """The row offset that aligns b onto a with the most agreement.

    Returns (offset, matched, compared, prefix, cover).  `prefix` is the length of
    the exact common run from the aligned start, which is the discriminator: a
    playback reproduces a contiguous prefix exactly, while two honest runs agree in
    scattered places by chance.  `cover` is that prefix as a fraction of the
    LONGER run -- see the note below, because normalising by the shorter one is a
    defect that was measured before it was fixed.

    The offset is searched over the DIFFERENCE OF THE FIRST TICKS and a small
    window around it, because a re-submitted run starts at a different absolute
    tick but the same relative one.  Nothing here searches a wide window: a wide
    search finds agreement that is not there, which is the same mistake as a join
    window in the angle rules (reccheck's angle_lag is read OFF the files for
    exactly that reason).

    TWO GATES THAT WERE NOT IN THE FIRST CUT, and both were found by looking at
    the output rather than by reasoning about the metric:

    * MIN_LEN.  This tree holds runs of 7, 8, 9 and 13 moves -- stubs a harness
      produced by walking out of a start box.  Two 9-move runs agree over all 9
      and report prefix 1.0000, which is arithmetically true and means nothing:
      nine quaternions of move+buttons is not enough to identify a performance,
      and the bhop_eazy group produced six of the ten "closest negative pairs"
      from files that short.  A similarity statistic needs a floor, and the floor
      is a parameter rather than a constant because the right value depends on
      how much the move alphabet repeats on a given map.
    * COVER OVER THE LONGER RUN.  The first cut divided the prefix by
      min(len(a), len(b)), so a 299-move run matching the first 299 moves of a
      4903-move run reported 1.0000 -- a perfect score for matching 6% of a
      performance.  Both fractions are printed now: `match` is agreement over
      what was compared, `cover` is how much of the LONGER run the exact prefix
      accounts for.  A playback scores 1.0 on both; a short run inside a long one
      scores high on match and low on cover, which is the truth about it.
    """
    sa, sb = stream(a), stream(b)
    if not sa or not sb:
        return (0, 0, 0, 0, 0.0)
    longer = max(len(sa), len(sb))
    if min(len(sa), len(sb)) < min_len:
        return (0, 0, 0, 0, 0.0)
    base = 0
    if a.mt and b.mt:
        base = b.mt[0] - a.mt[0]
    window = range(-4, 5) if max_shift is None else range(-max_shift, max_shift + 1)

    best = (base, 0, 0, 0, 0.0)
    for d in window:
        # d is a shift in ROWS, not ticks: rows are per simulated move and the
        # tick column only picks the centre of the window.
        matched = compared = 0
        i, j = 0, d
        while i < len(sa) and j < len(sb):
            if j >= 0:
                compared += 1
                if sa[i] == sb[j]:
                    matched += 1
            i += 1
            j += 1
        pl = prefix_len(a, b, d)
        if matched > best[1] or (best[2] == 0 and compared > 0):
            best = (d, matched, compared, pl, pl / float(longer))
    return best


def prefix_len(a, b, d=0):
    """Length of the exact common run from the aligned start.  This is the
    statistic that separates a playback from a coincidence: a playback is one
    long contiguous run, chance agreement is short and scattered."""
    sa, sb = stream(a), stream(b)
    n = 0
    i, j = 0, d
    while i < len(sa) and 0 <= j < len(sb):
        if sa[i] != sb[j]:
            break
        n += 1
        i += 1
        j += 1
    return n


# --------------------------------------------------------------------------
# one pair, for a caller that already knows which two files it means
# --------------------------------------------------------------------------

SKIP_UNREADABLE = "unreadable"
SKIP_NO_ROWS = "no sample rows"
SKIP_SHORT = "too short"
SKIP_SAME_FILE = "same file"
SKIP_MALFORMED = "malformed input"
SKIP_NO_OPPORTUNITIES = "no comparison opportunities"
SKIP_SOURCE_LIMIT = "source limit"


def compare_paths(path_a, path_b, min_len=MIN_LEN, max_bytes=None, max_moves=None):
    """Compare two `.rec` files by path.  -> (verdict, detail).

    THIS IS THE ONE ENTRY POINT A SECOND CALLER SHOULD USE, and the reason it
    exists is the tree's own rule about parsers: `reccheck` owns the `.rec`
    GRAMMAR (it counts `in` rows but does not retain them, because it is a
    validator and not a reader), and this module owns the move STREAM.  A caller
    that re-parses `.rec` itself creates a second source of truth for a format
    with one authoritative comment block, which is how `rcptcheck` came to delegate
    to `reccheck` rather than re-read the grammar beside it.

    `verdict` is one of:
      "compared"  -- `detail` is a dict of the measurement;
      a SKIP_* string -- `detail` is a one-line reason.

    Optional max_bytes/max_moves are operational source budgets; exceeding either
    abstains as SKIP_SOURCE_LIMIT without comparing a surviving prefix. Defaults
    preserve standalone census behavior; fleet collectors pass explicit bounds.

    A SKIP IS NOT A LOW SCORE AND IS NOT AN ERROR.  That distinction is the whole
    lesson of MIN_LEN above: a pair that could not be judged must be counted
    separately, because reporting it as a low score is the same false reading as
    reporting it as a high one.  Callers store the skip so a corpus can say how
    much of itself was judgeable, which is what `assist.py`'s coverage columns do.

    `detail` keys, all measured on the fleet corpus 2026-10-05 (see
    tools/census/README.md for what they separated on):
      match    agreement over the rows actually compared (0..1)
      cover    the exact prefix as a fraction of the LONGER run (0..1)
      prefix   the exact prefix in rows
      offset   the row shift that aligned them
      compared rows compared, matched rows that agreed
      moves_a, moves_b  each file's move count
      tickrate_a, tickrate_b  each header's tickrate
      who_a, who_b      the 8-hex FS_GuidId in each filename, or ""
      same_who  True when both carry an identity and it is the same one

    TICKRATE IS RETURNED AND DELIBERATELY NOT GATED ON.  Two runs at 66.67 and
    125 tick cannot be a playback of one another, so a tickrate mismatch is a
    reason to distrust a HIGH match -- but it is not a reason to refuse the
    comparison, and refusing it would hide exactly the pairs worth reading.  The
    caller decides; nothing here does.
    """
    if os.path.realpath(path_a) == os.path.realpath(path_b):
        return SKIP_SAME_FILE, "both arguments resolve to one file"
    recs = []
    for p in (path_a, path_b):
        try:
            r = parse_rec(p, strict=True, max_bytes=max_bytes, max_moves=max_moves)
        except SourceLimit as exc:
            return SKIP_SOURCE_LIMIT, str(exc)
        except MalformedRec:
            return SKIP_MALFORMED, "malformed required move-stream input"
        except (PermissionError, OSError) as e:
            return SKIP_UNREADABLE, "%s: %s" % (os.path.basename(p), e)
        if r is None:
            return SKIP_NO_ROWS, "%s has no `in` rows" % os.path.basename(p)
        if len(r.moves) < min_len:
            return SKIP_SHORT, "%s has %d moves, under the floor %d" % (
                os.path.basename(p), len(r.moves), min_len)
        recs.append(r)
    a, b = recs
    off, matched, compared, prefix, cover = best_offset(a, b, min_len=min_len)
    if not compared:
        return SKIP_NO_OPPORTUNITIES, "no comparison opportunities"
    wa, wb = who_of(a.path), who_of(b.path)
    return "compared", {
        "match": (matched / float(compared)) if compared else 0.0,
        "cover": cover,
        "prefix": prefix,
        "offset": off,
        "compared": compared,
        "matched": matched,
        "moves_a": len(a.moves),
        "moves_b": len(b.moves),
        "tickrate_a": a.tickrate,
        "tickrate_b": b.tickrate,
        "who_a": wa,
        "who_b": wb,
        "same_who": bool(wa) and wa == wb,
    }


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

def collect(root):
    pats = ["**/*.rec"]
    out = []
    for pat in pats:
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            out.append(p)
    return sorted(set(out))


def cmd_census(args):
    paths = collect(args.root)
    print("root %s: %d .rec files" % (args.root, len(paths)))
    by_ver = collections.Counter()
    by_map = collections.Counter()
    with_in = 0
    without = 0
    unavailable = collections.Counter()
    grouped = collections.defaultdict(list)
    limit = args.limit or len(paths)
    for p in paths[:limit]:
        try:
            r = parse_rec(p, strict=True)
        except OSError:
            unavailable["unreadable"] += 1
            continue
        except MalformedRec:
            unavailable["malformed"] += 1
            continue
        if r is None:
            without += 1
            continue
        with_in += 1
        by_ver[r.ver] += 1
        m, leg = derive_leg(p, r)
        by_map[m] += 1
        grouped[(m, leg)].append((p, len(r.moves)))
    print("  with `in` rows: %d   without (samples only): %d" % (with_in, without))
    for category, count in sorted(unavailable.items()):
        print("  SKIPPED %s: %d" % (category, count))
    print("  versions:", dict(sorted(by_ver.items())))
    multi = {k: v for k, v in grouped.items() if len(v) > 1}
    print("  map/leg groups: %d, of which %d hold >1 comparable run"
          % (len(grouped), len(multi)))
    print("  comparable PAIRS available: %d"
          % sum(len(v) * (len(v) - 1) // 2 for v in multi.values()))
    print("  largest groups:")
    for k, v in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:12]:
        print("    %-28s %-10s %3d runs  (%d-%d moves)"
              % (k[0], k[1], len(v), min(x[1] for x in v), max(x[1] for x in v)))
    return 0


def cmd_one(args):
    try:
        a, b = parse_rec(args.a, strict=True), parse_rec(args.b, strict=True)
    except MalformedRec:
        print('not compared: malformed required move-stream input')
        return 1
    except OSError:
        print('not compared: unreadable recording')
        return 1
    if a is None or b is None:
        print("one of those has no `in` rows")
        return 1
    print("A %s  map %s leg %s ver %d  %d moves" % (args.a, a.map, a.leg, a.ver, len(a.moves)))
    print("B %s  map %s leg %s ver %d  %d moves" % (args.b, b.map, b.leg, b.ver, len(b.moves)))
    d, matched, compared, pl, cover = best_offset(a, b, min_len=args.min_len)
    longer = max(len(a.moves), len(b.moves))
    shorter = min(len(a.moves), len(b.moves))
    if not compared:
        print("not compared: min_len %d excludes a %d/%d-move pair"
              % (args.min_len, len(a.moves), len(b.moves)))
        return 1
    print("best row offset %d" % d)
    print("  match   %.4f  (%d of %d compared rows agree)   <-- THE DISCRIMINATOR"
          % (matched / float(compared), matched, compared))
    print("  prefix  %d exact contiguous rows from the aligned start" % pl)
    print("  cover   %.4f  (prefix / the LONGER run, %d moves)   diagnostic only"
          % (cover, longer))
    print("          cover is NOT the statistic a gate would use: it is brittle")
    print("          (one perturbed move at 1% of a run drops it from 1.0000 to")
    print("          0.0098) and it misses the trimmed playback -- submitting the")
    print("          first half of someone else's recording reads cover 0.4998")
    print("          while match still reads 1.0000, correctly.")
    print("  for contrast, prefix / the SHORTER run (%d moves) reads %.4f --"
          % (shorter, pl / float(shorter)))
    print("          that was the first cut's normalisation, and it scores a")
    print("          299-move run inside a 4903-move one as a perfect 1.0000.")
    return 0


def cmd_pairs(args):
    # THE FIXTURE FILTER IS A DIRECTORY RULE AND A NAME RULE, and getting it right
    # took three passes because each pass found a class the previous one had let
    # through -- which is itself the finding, and the reason this comment lists
    # what is in the tree rather than what the code does.  Measured:
    #   data/pNNN/       every patch's harness output (p349, p352, p356, p367,
    #                    p369, p373, p376, p380, p382, p385, p394, p416, p417 ...)
    #   data/evidence/   the run-evidence tree
    #   data/saves/      save slots, including *.kept.pNNN parks
    #   data/resume/, data/parts/, data/staged/   Multi-Session and upload staging
    #   data/runs/, data/online/   THE ACTUAL RUNS, and the only honest source of
    #                    negative pairs -- everything above is a fixture or a copy
    #                    of one.
    # Plus NAME patterns, because a fixture can sit inside data/runs/: n1clk,
    # n2jmp, n3floor, n4cold, n5why, n6nosess are reccheck's mutants, and b88fin,
    # b352fin, p349_zcrc, p356_v10, p358seam are harness arms.  Pass 1 filtered
    # two directories and reported surf_derpis's nine mutants as the
    # false-positive risk.  Pass 2 added names and STILL reported b352fin vs
    # p356_v10 at prefix 1.0000, because those live in data/runs/bhop_eazy/main/
    # -- a real directory holding harness output.  Pass 3 found b88fin vs
    # p349_zcrc in the same place.  THERE IS NO WAY TO TELL THEM APART BY PATH,
    # only by name, and the name list has to be grown every time a new harness
    # writes into data/runs/.  That is a maintenance liability and it is recorded
    # here rather than hidden, because a filter that silently admits a fixture
    # inflates the false-positive rate and a filter that silently excludes a real
    # run deflates the negative count -- and the two look alike from the summary
    # line.
    REAL = ("data/runs/", "data/online/")
    FIXNAME = ("derpis", "n1late", "n2noopen", "n3noclose", "n4steer", "n6late",
               "n7pe", "n8move", "p5lag", "seam", "p360sf", "cheat", "mutant",
               "n1clk", "n2jmp", "n3floor", "n4cold", "n5why", "n6nosess",
               "b26", "b35", "b48", "b52", "b57", "b58", "b64", "b65", "b86",
               "b88", "p299", "p301", "p303", "p305", "p306", "p307", "p309",
               "p310", "p313", "p326", "p328", "p335", "p338", "p339", "p346",
               "p349", "p352", "p356", "p358", "p360", "p362", "p364", "p367",
               "p368", "p369", "p370", "p371", "p372", "p373", "p375", "p376",
               "p380", "p382", "p383", "p385", "p386", "p389", "p390", "p394",
               "p396", "p403", "p405", "p406", "p407", "p411", "p412", "p416",
               "p417", "p418", "p420", "p421", "p422", "p423", "p424", "p425",
               "p426", "p428", "p435", "p438", "p439", "p440", "p441", "p445",
               "p448", "p449", "p451", "p452", "p453", "p457", "p462", "p465",
               "p466", "p467", "p468", "p470", "p473", "p475", "p477", "p484",
               "p485", "p486", "_t0", "_cut", "_samp", "_ticks", "_zcrc",
               "_extra", "_sess", "fin_", "_fin")

    def is_real(p):
        q = p.replace(os.sep, "/")
        if not any(d in q for d in REAL):
            return False
        b = os.path.basename(q).lower()
        return not any(f in b for f in FIXNAME)

    paths = collect(args.root)
    recs = {}
    grouped = collections.defaultdict(list)
    seen = {}
    dupes = 0
    for p in paths:
        if not is_real(p):
            continue
        r = parse_rec(p)
        if r is None:
            continue
        # DEDUPLICATE BYTE-IDENTICAL FILES BEFORE GROUPING.  The same recording is
        # stored twice for at least surf_aura and surf_aweles (measured: identical
        # sha256 and size, one copy under data/p369/ and one under data/online/).
        # A copy is not a negative pair, and it is not an interesting positive
        # either -- surfd already stores a whole-file sha256 as replays.sha, which
        # catches that case outright and needs no move-column comparison at all.
        try:
            h = hashlib.sha256(open(p, "rb").read(1 << 20)).hexdigest()
            h += ":%d" % os.path.getsize(p)
        except OSError:
            continue
        if h in seen:
            dupes += 1
            continue
        seen[h] = p
        m, leg = derive_leg(p, r)
        recs[p] = r
        grouped[(m, leg)].append(p)

    print("byte-identical duplicates skipped: %d" % dupes)
    print("real runs (data/runs|online, fixtures excluded by name): %d in %d map/leg groups"
          % (len(recs), len(grouped)))
    for k, v in sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:10]:
        if len(v) > 1:
            print("    %-24s %-10s %3d runs  (%d-%d moves)"
                  % (k[0], k[1], len(v), min(len(recs[x].moves) for x in v),
                     max(len(recs[x].moves) for x in v)))

    neg = []
    fixpairs = 0
    short = 0
    done = 0
    for (m, leg), ps in sorted(grouped.items()):
        if len(ps) < 2:
            continue
        if done >= args.max:
            break
        taken = 0
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                if args.per_map and taken >= args.per_map:
                    break
                if done >= args.max:
                    break
                if not is_real(ps[i]) or not is_real(ps[j]):
                    fixpairs += 1
                    continue
                a, b = recs[ps[i]], recs[ps[j]]
                d, matched, compared, pl, cover = best_offset(
                    a, b, min_len=args.min_len)
                if not compared:
                    short += 1
                    continue
                frac = matched / float(compared)
                neg.append((cover, frac, pl, max(len(a.moves), len(b.moves)),
                            m, leg, os.path.basename(ps[i]),
                            os.path.basename(ps[j]),
                            who_of(ps[i]), who_of(ps[j])))
                taken += 1
                done += 1

    print("pairs skipped as fixtures: %d" % fixpairs)
    print("NEGATIVE pairs (different runs, same map+leg): %d" % len(neg))
    pfs = []
    if neg:
        neg.sort(reverse=True)
        pfs = [n[0] for n in neg]
        fr = sorted(n[1] for n in neg)
        print("  MATCH (agreement over compared rows) -- THE DISCRIMINATOR:")
        print("      max %.4f  p99 %.4f  median %.4f  min %.4f"
              % (fr[-1], fr[max(0, int(len(fr) * 0.01) - 1)],
                 fr[len(fr) // 2], fr[0]))
        print("  cover (exact contiguous prefix / the LONGER run) -- diagnostic:")
        print("      max %.4f  median %.4f"
              % (pfs[0], pfs[len(pfs) // 2]))
        bym = sorted(neg, key=lambda n: -n[1])
        print("  the ten highest-MATCH negative pairs -- the false-positive risk:")
        for n in bym[:10]:
            print("    match %.4f  cover %.4f  prefix %d  compared %d  %s/%s  %s vs %s"
                  % (n[1], n[0], n[2], n[3], n[4], n[5], n[6], n[7]))

        # THE IDENTITY SPLIT, and it is the difference between a calibration and
        # a number.  A same-identity pair is ONE PLAYER replaying ONE MAP -- the
        # hardest honest case a similarity gate faces, because the routes, the
        # start and the habits are all shared.  A cross-identity pair is the easy
        # case.  Which one dominates is a property of the CORPUS, not of the
        # metric, and printing one max hides it: measured on the fleet corpus,
        # 53 of 64 files are one install (26c95e00) under four netnames, so its
        # negative max is a same-player figure and reads as the pessimistic one.
        def split(pred):
            xs = [n[1] for n in neg if pred(n)]
            return (len(xs), max(xs), sorted(xs)[len(xs) // 2]) if xs else (0, None, None)

        for label, pred in (("SAME identity (one player, replaying -- the hard case)",
                             lambda n: n[8] and n[8] == n[9]),
                            ("CROSS identity (different installs -- the easy case)",
                             lambda n: n[8] and n[9] and n[8] != n[9]),
                            ("UNKNOWN identity (a pre-build-66 name, no who segment)",
                             lambda n: not n[8] or not n[9])):
            cnt, mx, md = split(pred)
            if not cnt:
                continue
            print("  %-58s %3d pairs  max %.4f  median %.4f"
                  % (label, cnt, mx, md))
        ids = sorted({n[8] for n in neg if n[8]} | {n[9] for n in neg if n[9]})
        ncross = sum(1 for n in neg if n[8] and n[9] and n[8] != n[9])
        if neg and not ncross:
            # SAY WHAT WAS NOT MEASURED, not what was.  The first cut of this
            # note concluded "measures only the same-player case", which is not
            # what an UNKNOWN pair says -- a pre-build-66 name carries no
            # identity at all, so those pairs are unattributed rather than
            # same-player.  The true statement is that the cross-player rate has
            # no sample here, and that is what a reader needs before quoting a
            # threshold.
            print("  NOTE: NOT ONE CROSS-IDENTITY PAIR was measured (%d identities"
                  " seen: %s).  The negative max above is therefore a"
                  " same-player-or-unattributed figure.  That is the pessimistic"
                  " direction for a gate -- one player replaying one map is the"
                  " hardest honest case -- but it is NOT a measurement of the"
                  " cross-player rate, and a corpus of local runs cannot give"
                  " one."
                  % (len(ids), ", ".join(ids) if ids else "none"))

        perfect = [n for n in neg if n[1] >= 0.9999]
        if perfect:
            # THIS LINE IS THE MEASUREMENT'S OWN CAVEAT AND IT FIRES ON THIS TREE.
            # Two runs of one map+leg agreeing on EVERY compared row are not two
            # independent performances.  On a local tree they are one of three
            # things, and the tool cannot tell them apart, so it says so instead
            # of printing a bare OVERLAP that reads as "the metric failed":
            #   * the same performance recorded twice -- which is what the check
            #     is FOR, and a true positive mislabelled as a negative here;
            #   * a harness arm that drives the same scripted route twice
            #     (measured: surf_666's `anna-ab9ae4aa` group is the p371 harness
            #     on port 27641, three runs 2.5 min apart sharing a 299-move
            #     identical prefix, all with different sha256 and different
            #     runids);
            #   * a _pb/_run pair of one run, i.e. one recording stored under two
            #     names by the save machinery.
            # None of the three is a false positive of the metric.  What it means
            # is that THIS CORPUS CANNOT CALIBRATE A THRESHOLD, because it holds
            # no two genuinely independent runs of one map.  A fleet corpus can.
            print()
            print("  %d negative pair(s) agree on EVERY compared row.  Two runs of"
                  % len(perfect))
            print("  one map+leg that agree exactly are not two independent")
            print("  performances: they are either the same performance recorded")
            print("  twice (a TRUE POSITIVE, mislabelled negative here), a harness")
            print("  arm driving one scripted route twice, or a _pb/_run pair of")
            print("  one recording.  The tool cannot tell them apart, so:")
            print("  THIS CORPUS CANNOT CALIBRATE A THRESHOLD -- it holds no two")
            print("  genuinely independent runs of one map.  A fleet corpus can.")
    else:
        print("  NOTHING COMPARABLE: either no map+leg holds two real runs, or"
              " every pair fell below min_len.")

    # POSITIVE pairs: each file against a re-reading of itself with a SHIFTED
    # TICK EPOCH, which is what one performance recorded twice actually produces
    # -- the same move stream, a different absolute tick, a different header
    # nonce, different file bytes.  A byte-identical copy is NOT the interesting
    # positive (a sha256 catches that) and is not what this models.
    pos = []
    sample = [p for p in list(recs) if recs[p] and is_real(p)][:args.max]
    for p in sample:
        a = recs[p]
        b = parse_rec(p)
        # A re-submission of one performance: the SAME move stream, a different
        # absolute tick epoch, a different header nonce, different file bytes.
        # Shifting the epoch is what makes this a positive for the ALIGNMENT
        # rather than for the file hash -- a byte-identical copy is caught by
        # replays.sha and is not what this measures.
        b.mt = [x + 12345 for x in b.mt]
        d, matched, compared, pl, cover = best_offset(a, b, min_len=args.min_len)
        if not compared:
            short += 1
            continue
        pos.append((cover, matched / float(compared), pl, len(a.moves),
                    os.path.basename(p), d))
    print()
    print("pairs below min_len %d, not compared at all: %d" % (args.min_len, short))
    print("POSITIVE pairs (same recording, shifted tick epoch): %d" % len(pos))
    if pos:
        pp = sorted(n[0] for n in pos)
        print("  cover: min %.4f  median %.4f  max %.4f"
              % (pp[0], pp[len(pp) // 2], pp[-1]))
        off = sorted(set(n[5] for n in pos))
        print("  alignment offsets found: %s" % (off[:6],))
        print("  (all zero means the epoch shift was absorbed without a row"
              " shift, which is what a playback does)")
        if pfs:
            pm = sorted(n[1] for n in pos)
            nm = max(n[1] for n in neg)
            print()
            print("  SEPARATION on MATCH (the discriminator): positive min %.4f"
                  "  vs  negative max %.4f  -> %s"
                  % (pm[0], nm,
                     "CLEAN, margin %.2fx" % (pm[0] / nm) if nm > 0 and pm[0] > nm
                     else ("OVERLAP (see the caveat above: on a local tree the"
                           " overlapping negatives are harness output, not"
                           " independent runs)" if nm >= pm[0] else "clean")))
            print("  SEPARATION on cover (diagnostic only): positive min %.4f"
                  "  vs  negative max %.4f" % (pp[0], pfs[0]))
            print("  A gate would threshold MATCH, not cover: cover is brittle"
                  " (one perturbed move at 1% of a run drops it to 0.0098) and"
                  " misses the trimmed playback (first half only reads 0.4998"
                  " while match still reads 1.0000).")
        else:
            print("  SEPARATION: cannot be measured -- no negative pair"
                  " survived min_len %d.  THIS IS THE EXPECTED RESULT ON A LOCAL"
                  " TREE: it holds no two independent runs of one map, because"
                  " every multi-run group here is harness output.  Run this"
                  " against a fleet corpus." % args.min_len)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "ftesurf", "data"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("census")
    c.add_argument("--limit", type=int, default=0)
    c.set_defaults(fn=cmd_census)

    o = sub.add_parser("one")
    o.add_argument("a")
    o.add_argument("b")
    o.add_argument("--min-len", type=int, default=MIN_LEN)
    o.set_defaults(fn=cmd_one)

    p = sub.add_parser("pairs")
    p.add_argument("--max", type=int, default=400)
    p.add_argument("--per-map", type=int, default=6)
    p.add_argument("--min-len", type=int, default=MIN_LEN,
                   help="shortest run in simulated moves worth comparing; below "
                        "this a pair is not compared at all rather than reported "
                        "as a low score")
    p.set_defaults(fn=cmd_pairs)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
