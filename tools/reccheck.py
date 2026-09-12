#!/usr/bin/env python3
"""
reccheck.py -- read a run recording and say whether it is well formed.

WHY THIS EXISTS.  The .rec format has one writer (sv_timer.qc) and, until the
replay lands, no reader at all.  A format with no reader is a format nobody has
ever checked: the v2 files on disk were produced for two months without anything
ever parsing one back, and the only way a mistake would have surfaced is when the
replay tried to play it and looked wrong -- at which point the bug could be in
either half.

So this is the reader that exists to disagree with the writer.  It is written
from the grammar in the header comment of sv_timer.qc's recorder section, NOT
from the writer's source, so that a writer that drifts from its own documentation
is caught rather than matched.

WHAT IT CHECKS, beyond "does it parse":

  * column count per sample, which is the whole v2/v3 compatibility claim;
  * that padding samples come first and carry negative timestamps, since that is
    how a reader finds t=0;
  * that `end` agrees with the samples actually present -- the counts in it are
    written from separate counters, so a mismatch means one of them is wrong;
  * that `split` records really do follow `end`, because they do, and a reader
    that stops at `end` would silently lose them;
  * that a `resume` record (build 17, save states) is well formed, and that the
    samples stay in time order ACROSS one.  That last is not a formality: the
    first attempt at restoring the clock used the rounded tick count, which put
    the resumed run up to half a tick behind the recording it was appending to,
    and this file is what refused the result;
  * that the v3 key mask agrees with the movement columns it is derived from.
    They are written from the same .movement in the same call, so any
    disagreement is a real bug and not a rounding argument;
  * the sample RATE, per second, measured rather than assumed.  The recorder
    samples once per received packet and not once per tick, so this is expected
    to be near but under the tick rate -- and a number far under it is packet
    loss, which is worth seeing.

And, when the .view sidecar is beside it, that the two files describe the same
run: that the sidecar's tick range is inside the recording's, and that its frames
group into usercmds sensibly.

Usage:
    python reccheck.py                          # every .rec and .part in data/runs
    python reccheck.py <file> [<file> ...]
    python reccheck.py --verbose                # per-file detail, not just faults
"""

import argparse
import glob
import math
import os
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(SURFDIR, "ftesurf", "data", "runs")
SAVES = os.path.join(SURFDIR, "ftesurf", "data", "saves")


def is_prefix(path):
    """Is this a save state's run.rec rather than a finished recording?

    A prefix is a real, well-formed FTESURF-REC file that simply stops in the
    middle -- it is the movement up to a save point, and the run it belongs to
    has not ended.  So it has no `end` trailer and no `split` records, and
    demanding those of it would report every save state on the disk as broken.

    Recognised by its location rather than by its contents: the writer puts one
    at data/saves/<map>/saveNN/run.rec and nowhere else, and guessing from the
    absence of a trailer would make a genuinely TRUNCATED .rec unreportable --
    which is the failure this tool exists to catch.
    """
    return os.path.basename(path) == "run.rec"

# Sample columns, by version.  This is the compatibility contract in one line:
# v3 is v2 plus four and v4 is v3 plus three, always APPENDED, so a reader of any
# version taking the columns it knows about is correct on a later file.
#
# v4's three are the plane under the player -- run_rampnormal while the new flags
# bit 16 is set, run_groundnorm while bit 1 is set, and zero in free air.  One
# vector and not two, because the three consumers all pick exactly one of them
# and pick it with those same two bits; see the format block in sv_timer.qc.
COLUMNS = {2: 10, 3: 14, 4: 17}

# Header keys each version is allowed to write.  Unknown keys are SKIPPED by a
# reader rather than rejected, so an unexpected one is a note and not a fault.
HEAD_V2 = {"map", "track", "startseg", "tickrate"}
HEAD_V3 = HEAD_V2 | {"owner", "runid"}

# v4's one new key.  It is RESERVED at open as `flags 0` and rewritten in place
# at close, because the flags it reports are not known until the run ends and the
# header is still in memory then.  That is what lets the leaderboard read
# clean-vs-stitched with nine fgets instead of by walking a 444 KB file to its
# trailer.
HEAD_V4 = HEAD_V3 | {"flags"}

# shared/sh_defs.qc.  Only the two a stored run may assert: TF_RECORDING and
# TF_FROZEN are masked out by SV_RecClose, because neither is a fact about the
# run -- one says a buffer was open and the other says a save-lock was being held
# at that instant.
TF_PRACTICE, TF_SHADOW = 1, 8

# Build 44.  TF_PRACTICE stops being the only answer to "why is this run not
# clean" and becomes the UMBRELLA over two reasons: a save state was used
# (segment) or the physics were not the ruleset's (cheat).  Both imply it, which
# is what makes the split free for every reader that only knew the umbrella.
#
# WHAT IS *NOT* ASSERTED HERE, and it would be wrong to add it: TF_SHADOW does
# not have to carry TF_SEGMENT.  Three files on disk are practice+shadow with no
# segment bit because they were written before build 44, and they are not wrong
# -- FS_RunClass reads shadow as segment precisely so they classify correctly
# without being rewritten.  A checker that faulted them would be faulting the
# archive for predating the format, which is the one thing a format check must
# never do.
TF_SEGMENT, TF_CHEAT = 128, 256

# shared/sh_defs.qc's FS_RunClass, and the precedence is the point: a run that
# both noclipped and loaded a save carries both bits, and reading segment first
# would put the gentler word on the worse run.
def run_class(fv):
    if fv & TF_CHEAT:
        return "cheated"
    if fv & TF_SEGMENT:
        return "segmented"
    if fv & TF_SHADOW:
        return "segmented"
    if fv & TF_PRACTICE:
        return "practice"
    return "clean"

# Build 30.  The run contains at least one GHOST WINDOW -- a stretch where the
# player's camera was detached and the body carried on unattended.
#
# IT DOES NOT IMPLY TF_PRACTICE, and that is deliberate rather than an oversight
# in the writer: a ghosted run is still a run.  The bit exists because a ghost
# window is otherwise INDISTINGUISHABLE FROM LETTING GO -- the usercmd is emptied
# and its angles pinned, so the movement and key columns go flat zero and
# pitch/yaw stop moving, and the mask check further down is satisfied by zeros
# agreeing with zeros.  It would have passed silently.
TF_GHOST = 64

# Build 58.  The run was set with the raw input journal switched off, so no .hid
# describes it.
#
# LIKE TF_GHOST AND UNLIKE THE FOUR ABOVE, it implies nothing about how the run
# was played and must not be folded into run_class().  `rec_hid 0` changes no
# physics and loads no save; the run is clean, the EVIDENCE is not.  A checker
# that reported it as a taint class would be calling an honest player's run
# dirty on the strength of a recording switch.
#
# IT IS ALSO NOT A FAULT HERE, and that is the deliberate part.  The server sets
# it only when the client explicitly reported `rechid 0` -- an absent key stays
# unknown and sets nothing -- so the bit's presence means the player made a
# choice the HUD had already warned them about, and its ABSENCE means either a
# journal or an unknown, which this file cannot tell apart and must not guess
# between.  What a .hid actually proves is hidcheck.py's business; all this
# format check may say is whether the bit and the sidecar agree.
TF_NOJOURNAL = 512

# Build 62, engine Patch 313.  THE RUN'S PHYSICS WERE NOT PROVABLY THE RULESET'S.
#
# The server reads the engine's *ruleset "<locked> <off> <seq>" key at the start
# of the run and again at the finish, and sets this if the lock was disengaged,
# if any cvar in the locked movement table was off its canonical value, or if the
# sequence counter moved while the clock was running -- the last of which is the
# only way to see an unlock-and-relock window, because both ends of it read
# locked 1 / off 0.
#
# NOT A TAINT CLASS AND NOT A FAULT HERE, for the same two reasons TF_NOJOURNAL
# is neither.  It describes a hole in the CERTIFICATION rather than something the
# player did -- an install that never set pm_lockmovement is misconfigured, not
# cheating -- and the clear case is genuinely ambiguous: an engine older than
# Patch 313 publishes no key at all, the server refuses to guess from its
# absence, and every run recorded before this build is in exactly that state.
TF_NORULESET = 1024

# Build 17 added save states and a `resume` RECORD, not a header key -- a save
# rewinds the buffer and appends from the mark, so anything written at the resume
# lands in the middle of the sample stream, and the header ends at `begin`.  So
# the header is unchanged and the version stays 3.
#
# It also added a third filename tag.  A run resumed from a save is practice by
# definition, so before this it would have been written as `_last` and would have
# overwritten the most recent ordinary run on the same leg -- which is exactly
# the file you would want to compare it against.
#
# Build 45 added the fourth, one class further down and for word-for-word the
# same reason: a cheated run is practice, is never a personal best, and is not
# TF_SHADOW unless a save was ALSO loaded -- so build 44 wrote it as `last` and
# it overwrote the most recent ordinary attempt.  Unstamped like `last`, because
# there is no version of "keep every cheated run on this leg" that anyone wants.
TAGS = ("pb", "last", "shadow", "cheat")


def tag_from_name(path):
    """The tag word out of a run filename, or None if it is not one of ours.

    Two shapes, and the split is the archived question: `<ticks>_<tag>.rec` for
    the classes that accumulate, a bare `<tag>.rec` for the two scratch slots.
    rsplit handles both without asking which it is looking at.
    """
    base = os.path.basename(path)
    if not base.endswith(".rec"):
        return None
    word = base[:-4].rsplit("_", 1)[-1]
    return word if word in TAGS else None

# shared/sh_defs.qc
FSI_FWD, FSI_BACK, FSI_LEFT, FSI_RIGHT = 1, 2, 4, 8
FSI_JUMP, FSI_DUCK, FSI_TLEFT, FSI_TRIGHT = 16, 32, 64, 128
FSI_ATTACK, FSI_PSREL = 256, 512


class Report:
    def __init__(self, path):
        self.path = path
        self.faults = []
        self.notes = []
        self.info = {}

    def fault(self, msg):
        self.faults.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    @property
    def ok(self):
        return not self.faults


def is_sample(tok):
    """A sample line starts with a number; every record type starts with a word.

    Padding samples carry NEGATIVE timestamps, so the leading '-' is part of the
    grammar and not a malformed line.
    """
    if not tok:
        return False
    return tok[0].isdigit() or (tok[0] == "-" and len(tok) > 1 and tok[1].isdigit())


def check_rec(path, verbose=False):
    r = Report(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n").rstrip("\r") for l in f]

    if not lines:
        r.fault("empty file")
        return r

    magic = lines[0].split()
    if len(magic) != 2 or magic[0] != "FTESURF-REC":
        r.fault("first line is not 'FTESURF-REC <version>': %r" % lines[0][:60])
        return r
    try:
        ver = int(magic[1])
    except ValueError:
        r.fault("version is not a number: %r" % magic[1])
        return r
    if ver not in COLUMNS:
        r.fault("unknown version %d (this tool knows %s)"
                % (ver, ", ".join(str(v) for v in sorted(COLUMNS))))
        return r
    r.info["version"] = ver
    want_cols = COLUMNS[ver]
    if ver >= 4:
        allowed = HEAD_V4
    elif ver >= 3:
        allowed = HEAD_V3
    else:
        allowed = HEAD_V2

    # ---- header ------------------------------------------------------------
    head = {}
    i = 1
    while i < len(lines):
        parts = lines[i].split(None, 1)
        if not parts:
            i += 1
            continue
        if parts[0] == "begin":
            i += 1
            break
        head[parts[0]] = parts[1] if len(parts) > 1 else ""
        if parts[0] not in allowed:
            r.note("header key %r is not part of v%d" % (parts[0], ver))
        i += 1
    else:
        r.fault("no 'begin' line: the header never ends")
        return r

    for k in ("map", "track", "startseg", "tickrate"):
        if k not in head:
            r.fault("header is missing %r" % k)
    r.info.update(head)

    tickrate = float(head.get("tickrate", 0) or 0)
    if tickrate <= 0:
        r.fault("tickrate %r is not positive" % head.get("tickrate"))
        tickrate = 0.015

    # ---- body --------------------------------------------------------------
    samples = []            # (t, cols)
    padding = 0
    records = []            # (lineno, kind, args)
    saw_end = None
    splits = []
    resumes = []            # (lineno, args) -- build 17 save states
    retries = []            # (lineno, args) -- build 18 `retry`, see below
    cprecs = []             # (lineno, args) -- build 19 checkpoints
    boards = []             # (lineno, args) -- build 24 v4 board entries
    ghosts = []             # (lineno, args) -- build 30 ghost window edges
    stagerecs = []          # (lineno, kind, args) -- build 43: stage/stagestart/restart
    seen_positive = False
    bad_cols = 0
    mask_disagree = 0

    for lineno in range(i, len(lines)):
        s = lines[lineno].strip()
        if not s:
            r.note("blank line at %d" % (lineno + 1))
            continue
        tok = s.split()

        if is_sample(tok[0]):
            if len(tok) != want_cols:
                bad_cols += 1
                if bad_cols <= 3:
                    r.fault("line %d has %d columns, v%d samples have %d"
                            % (lineno + 1, len(tok), ver, want_cols))
                continue
            try:
                vals = [float(x) for x in tok]
            except ValueError:
                r.fault("line %d has a non-numeric column" % (lineno + 1))
                continue

            t = vals[0]
            if t < 0:
                if seen_positive:
                    r.fault("line %d: negative timestamp %.4f after the run "
                            "started -- padding must come first" % (lineno + 1, t))
                else:
                    padding += 1
            else:
                seen_positive = True

            if samples and t < samples[-1][0]:
                r.fault("line %d: time goes backwards, %.4f after %.4f"
                        % (lineno + 1, t, samples[-1][0]))
            samples.append((t, vals))
            continue

        kind = tok[0]
        records.append((lineno + 1, kind, tok[1:]))
        if kind == "end":
            if saw_end is not None:
                r.fault("line %d: a second 'end' record" % (lineno + 1))
            saw_end = (lineno + 1, tok[1:])
        elif kind == "split":
            splits.append((lineno + 1, tok[1:]))
            if saw_end is None:
                r.fault("line %d: 'split' before 'end' -- the writer emits them "
                        "after" % (lineno + 1))
        elif kind == "resume":
            # Build 17.  The run was resumed from a save state: everything after
            # this line is a fresh attempt at the same section, appended over the
            # abandoned one rather than beside it.
            #
            # It is the ONE place a reader has to expect a discontinuity that is
            # not an error.  The samples' own timestamps stay monotonic across it
            # (the writer restores the unrounded clock precisely so they do), but
            # the .view sidecar's cltime column jumps by however long the failed
            # attempt lasted -- there is real wall-clock time on either side of
            # this line that no frame in the file describes.
            resumes.append((lineno + 1, tok[1:]))
        elif kind == "retry":
            # Build 18.  The MAP was restarted underneath the run -- `retry` --
            # and the attempt was restored from a state written a moment before
            # it.  The player did not move.
            #
            # A SEPARATE RECORD FROM `resume` BECAUSE THE SIDECAR BREAKS THE
            # OTHER WAY.  At a resume the .view's cltime jumps FORWARD by the
            # length of the abandoned attempt.  At a retry it jumps BACKWARDS,
            # to near zero: cltime is realtime - cl.mapstarttime and
            # clientcommandframe is cl.movesequence, and the map restart resets
            # both.  A reader told "resume" would see two monotonic clocks run
            # backwards with nothing to explain it.
            #
            # Across this line the only valid join key between the two files is
            # the run clock -- field 3 of a .view line, STAT_FS_TIMERTICKS --
            # because the writer restores the unrounded clock precisely so the
            # .rec's own `t` column stays continuous through it.
            retries.append((lineno + 1, tok[1:]))
        elif kind == "cp":
            # Build 19.  `cp <ordinal> <ticks>`.
            #
            # THE FIRST FIELD CHANGED MEANING IN BUILD 19 and an old file cannot
            # be told from a new one by shape alone -- both are two numbers.  It
            # used to be zone_seg[], the SEGMENT the checkpoint lived in, which on
            # a linear map is 0 for every checkpoint on the map; so a pre-19 file
            # reads `cp 0 <ticks>` over and over and a post-19 one counts 1, 2, 3.
            # The all-zeroes case is therefore diagnosed rather than faulted: it
            # is a valid old file, not a broken new one.
            cprecs.append((lineno + 1, tok[1:]))
        elif kind == "board":
            # Build 24, v4.  `board <t> <n> <nx ny nz> <vx vy vz>`.
            boards.append((lineno + 1, tok[1:]))
        elif kind == "ghost":
            # Build 30.  `ghost <0|1> <ticks>` -- the camera detached (1) or came
            # back (0).  Between a 1 and the next 0 the body was running with
            # nobody steering it: real physics, no input.
            #
            # THE SAMPLES INSIDE ONE ARE NOT SUSPICIOUS, THEY ARE PREDICTABLE,
            # and that is what makes this checkable rather than merely declared.
            # See the window check below: a marker that does not describe what
            # the samples actually do is the interesting failure here, because
            # the forgery this record could enable is claiming a stretch of play
            # was a ghost when it was not.
            ghosts.append((lineno + 1, tok[1:]))
        elif kind in ("stage", "stagestart", "restart"):
            # Build 43.  The three records that describe one stage's life, and
            # they are collected together because the only checks worth making
            # are about the SEQUENCE they form -- see the block below.
            #
            #   stage <seg> <ticks>       the boundary was crossed: seg begins
            #   stagestart <seg> <ticks>  you LEFT its box: the clock rebases here
            #   restart <seg> <ticks>     you came back INTO it, or typed !r
            #
            # `stage` and `restart` are older than this check and were previously
            # tolerated unvalidated.  They are validated now for the reason the
            # build-43 change gives them a second producer apiece: an untested
            # record grammar is one nobody notices breaking.
            stagerecs.append((lineno + 1, kind, tok[1:]))
        else:
            r.note("line %d: unknown record %r" % (lineno + 1, kind))

    r.info["samples"] = len(samples)
    r.info["padding"] = padding
    r.info["records"] = len(records)
    if resumes:
        # Reported rather than merely tolerated: "this is a shadow run and it was
        # resumed four times" is the single most useful thing to know about a
        # file whose sample stream is otherwise indistinguishable from a clean
        # one -- which is the whole point of the rewind being seamless.
        r.info["resumes"] = len(resumes)
        r.info["resumed_from"] = ",".join(a[0] if a else "?" for _, a in resumes)
        for ln, a in resumes:
            if len(a) != 2:
                r.fault("line %d: 'resume' takes 2 fields, has %d" % (ln, len(a)))

    if retries:
        # Same reasoning as resumes, plus the warning: this is the marker that
        # says a paired .view has two clocks that RESTART here, so a cross-file
        # check must join on the run clock across it and nothing else.
        r.info["retries"] = len(retries)
        r.info["retried_at"] = ",".join(a[0] if a else "?" for _, a in retries)
        for ln, a in retries:
            if len(a) != 1:
                r.fault("line %d: 'retry' takes 1 field, has %d" % (ln, len(a)))

    # ---- ghost windows (build 30) ------------------------------------------
    #
    # Three things are checked and they are not the same question:
    #
    #   the RECORDS are well formed and bracket properly -- 1 then 0, never two
    #   of a kind in a row, never a 0 with nothing open, and their tick stamps
    #   ascend with the stream they sit in;
    #
    #   the HEADER agrees -- TF_GHOST is set if and only if there are windows,
    #   so a reader that only looks at the flags word is told the truth;
    #
    #   the SAMPLES INSIDE each window actually look like a ghost.  That is the
    #   one that earns its keep.  A `ghost` record is a claim the writer makes
    #   about a stretch of the file, and the abuse it would enable is the
    #   opposite of the one people reach for first: not hiding a ghost, but
    #   CLAIMING one -- labelling a stretch of real play as "nobody was
    #   steering" to explain away something else in it.  While detached the
    #   usercmd genuinely carries no movement, no keys and a pinned angle, so
    #   every sample in a real window has zero in columns 10..13 and byte-equal
    #   pitch and yaw.  If it does not, the marker is a lie about that file.
    ghost_windows = []
    if ghosts:
        open_at = None
        last_tick = None
        for ln, a in ghosts:
            if len(a) != 2:
                r.fault("line %d: 'ghost' takes 2 fields, has %d" % (ln, len(a)))
                continue
            try:
                on, tick = int(float(a[0])), float(a[1])
            except ValueError:
                r.fault("line %d: 'ghost' has a non-numeric field" % ln)
                continue
            if on not in (0, 1):
                r.fault("line %d: 'ghost' state %r is not 0 or 1" % (ln, a[0]))
                continue
            if last_tick is not None and tick < last_tick:
                r.fault("line %d: 'ghost' tick %g goes backwards after %g"
                        % (ln, tick, last_tick))
            last_tick = tick

            if on:
                if open_at is not None:
                    r.fault("line %d: 'ghost 1' while one opened at line %d is "
                            "still open" % (ln, open_at[0]))
                open_at = (ln, tick)
            else:
                if open_at is None:
                    r.fault("line %d: 'ghost 0' with no window open" % ln)
                else:
                    ghost_windows.append((open_at[1], tick))
                    open_at = None

        if open_at is not None:
            # Not a fault.  A run that FINISHES while still detached is legal --
            # the body crossed the end zone on its own, which is exactly the
            # thing a reader of this file most needs to be told about.
            ghost_windows.append((open_at[1], None))
            r.info["ghost_open_at_end"] = "yes"

        r.info["ghosts"] = len(ghost_windows)
        r.info["ghost_ticks"] = sum(
            (b - a) for a, b in ghost_windows if b is not None)

    # ---- the samples inside a declared window, against what one must look like
    if ghost_windows and samples:
        # 0:t 1..3:org 4..6:vel 7:pit 8:yaw 9:fl 10:keys 11:fwd 12:side 13:up
        #
        # Windows are in TICKS and samples in SECONDS, so the comparison is made
        # in seconds via the file's own tickrate -- never by assuming 66.67.
        bad = 0
        held = 0
        for a, b in ghost_windows:
            lo = a * tickrate
            hi = (b * tickrate) if b is not None else float("inf")
            first = None
            for t, v in samples:
                if t < lo or t > hi:
                    continue
                held += 1
                if v[10] or v[11] or v[12] or v[13]:
                    bad += 1
                    continue
                if first is None:
                    first = (v[7], v[8])
                elif (v[7], v[8]) != first:
                    bad += 1
        r.info["ghost_samples"] = held
        if bad:
            r.fault("%d of %d samples inside a declared ghost window carry "
                    "input or a moving aim -- the marker does not describe "
                    "them" % (bad, held))

    # ---- the stage sequence (build 43) --------------------------------------
    #
    # A main run's stage records form a small state machine and it is checkable
    # end to end, which the previous build did not do at all: `stage` and
    # `restart` were on the tolerated list and nothing looked at their fields.
    #
    #   stage N        opens segment N.  The seg must go UP by one -- a run
    #                  passes through its stages in order, and SV_TimerEvent
    #                  refuses an out-of-order boundary rather than guessing.
    #   stagestart N   at most ONE per open stage, naming the OPEN stage, and at
    #                  a tick not before the boundary that opened it.  More than
    #                  one would mean the arm re-fired without a fail between,
    #                  which is the specific bug a "did we ever stand in the box"
    #                  latch exists to prevent -- so it is worth asserting rather
    #                  than trusting.
    #   restart N      names the open stage.  A fail re-arms it, so a
    #                  `stagestart` may legitimately follow.
    #
    # Ticks across all three must not go backwards.  They are the RUN clock, and
    # the run clock is deliberately not rewound by a stage fail -- that is the
    # decision build 12 made and build 43 kept, so a `restart` whose tick went
    # backwards would mean the writer had rewound something it promises not to.
    if stagerecs:
        open_seg = None         # the segment currently open, or None
        started = False         # has this stage's `stagestart` been seen
        opened_at = None
        last_tick = None
        n_start = n_restart = 0

        for ln, kind, a in stagerecs:
            if len(a) != 2:
                r.fault("line %d: %r takes 2 fields, has %d" % (ln, kind, len(a)))
                continue
            try:
                seg, tick = float(a[0]), float(a[1])
            except ValueError:
                r.fault("line %d: %r has a non-numeric field" % (ln, kind))
                continue
            if seg != int(seg) or seg < 0:
                r.fault("line %d: %r segment %r is not a non-negative integer"
                        % (ln, kind, a[0]))
                continue
            seg = int(seg)

            if last_tick is not None and tick < last_tick:
                r.fault("line %d: %r tick %g goes backwards after %g -- the run "
                        "clock is never rewound" % (ln, kind, tick, last_tick))
            last_tick = tick

            if kind == "stage":
                if open_seg is not None and seg != open_seg + 1:
                    r.fault("line %d: 'stage %d' after 'stage %d' -- boundaries "
                            "are crossed in order" % (ln, seg, open_seg))
                open_seg, started, opened_at = seg, False, tick
            elif kind == "stagestart":
                n_start += 1
                if open_seg is None:
                    r.fault("line %d: 'stagestart %d' with no stage open" % (ln, seg))
                elif seg != open_seg:
                    r.fault("line %d: 'stagestart %d' names a stage that is not "
                            "the open one (%d)" % (ln, seg, open_seg))
                elif started:
                    r.fault("line %d: a second 'stagestart' for stage %d with no "
                            "'restart' between them" % (ln, seg))
                else:
                    started = True
                    if opened_at is not None and tick < opened_at:
                        r.fault("line %d: 'stagestart' at %g is before the "
                                "boundary that opened it at %g"
                                % (ln, tick, opened_at))
            else:   # restart
                n_restart += 1
                if open_seg is None:
                    # Legal: `!r` on the run's first segment reaches
                    # SV_TimerRestartSeg without a `stage` record ever having
                    # been written, because segment 0 has no boundary.
                    open_seg = seg
                elif seg != open_seg:
                    r.fault("line %d: 'restart %d' names a stage that is not the "
                            "open one (%d)" % (ln, seg, open_seg))
                started, opened_at = False, tick

        if n_start:
            r.info["stagestarts"] = n_start
        if n_restart:
            # Reported rather than merely tolerated, exactly like `resumes`: "this
            # stage was taken four times" is the most useful thing to know about a
            # run whose sample stream is otherwise continuous.
            r.info["stage_restarts"] = n_restart

    if cprecs:
        r.info["checkpoints"] = len(cprecs)
        rows = []
        for ln, a in cprecs:
            if len(a) != 2:
                r.fault("line %d: 'cp' takes 2 fields, has %d" % (ln, len(a)))
                continue
            try:
                rows.append((ln, float(a[0]), float(a[1])))
            except ValueError:
                r.fault("line %d: 'cp' has a non-numeric field" % ln)

        for ln, _, t in rows:
            if t < 0:
                r.fault("line %d: checkpoint at a negative run time %g" % (ln, t))

        r.info["cp_ordinals"] = ",".join("%g" % n for _, n, _ in rows)

        # DECIDED BEFORE THE ORDER IS CHECKED, or every pre-19 file faults: they
        # are all `cp 0`, and 0 does not strictly increase.  An old file is a
        # valid old file, not a broken new one.
        if rows and all(n == 0 for _, n, _ in rows):
            r.note("all %d 'cp' records have ordinal 0 -- a pre-build-19 file, "
                   "where the field was the segment and not the checkpoint"
                   % len(rows))
        else:
            # The server only records a checkpoint whose ordinal beats the
            # highest reached so far.  That rule is what makes a gate built from
            # several regions count once (surf_utopia's first is a mirrored pair)
            # and what stops walking back through one counting twice, so a repeat
            # here means the rule did not hold.
            last, bad = None, 0
            for ln, n, _ in rows:
                if last is not None and n <= last:
                    bad += 1
                    if bad <= 3:
                        r.fault("line %d: checkpoint %g after %g -- ordinals "
                                "must strictly increase within a run"
                                % (ln, n, last))
                last = n

    # ---- v4: the board records, and the plane column -----------------------
    if boards:
        r.info["boards"] = len(boards)
        if ver < 4:
            r.fault("%d 'board' records in a v%d file -- that record is v4"
                    % (len(boards), ver))
        last_t, last_n = None, None
        for ln, a in boards:
            if len(a) != 8:
                r.fault("line %d: 'board' takes 8 fields, has %d" % (ln, len(a)))
                continue
            try:
                bt, bn = float(a[0]), float(a[1])
                nrm = [float(x) for x in a[2:5]]
            except ValueError:
                r.fault("line %d: 'board' has a non-numeric field" % ln)
                continue

            # The plane is what everything downstream grades against: a
            # non-unit normal makes the approach angle and the kept percentage
            # both wrong, quietly, in a way no other check would catch.
            mag = math.sqrt(sum(x * x for x in nrm))
            if abs(mag - 1.0) > 0.01:
                r.fault("line %d: 'board' normal has length %.4f, not 1" % (ln, mag))

            # In order, and the counter only ever goes up -- it is the engine's
            # own monotonic board count.  A step of more than one is legal and
            # is worth a note rather than a fault: samples are written per
            # PACKET and a packet can carry four usercmds, so two boards inside
            # one packet collapse to one record.
            if last_t is not None and bt < last_t:
                r.fault("line %d: 'board' at %.4f after %.4f -- records must be "
                        "in time order" % (ln, bt, last_t))
            if last_n is not None and bn <= last_n:
                r.fault("line %d: board counter %g after %g -- it must increase"
                        % (ln, bn, last_n))
            last_t, last_n = bt, bn

        skipped = 0
        for i in range(1, len(boards)):
            try:
                a, b = float(boards[i - 1][1][1]), float(boards[i][1][1])
            except (ValueError, IndexError):
                continue
            if b - a > 1:
                skipped += 1
        if skipped:
            r.note("%d 'board' record(s) skip a counter value -- two boards "
                   "inside one move packet, which the format collapses" % skipped)

    if not samples:
        r.fault("no samples at all")
        return r

    if ver >= 4:
        # 14..16 is the plane.  Its LENGTH is the check, and it is a three-way
        # one rather than "is it a unit vector": a sample carries a plane only
        # while the ramp-contact or onground bit is set, and zero the rest of the
        # time.  Both a missing plane under a set bit and a stray plane in free
        # air would send the strafe bar a target that was never there.
        FL_ONGROUND, FL_RAMP = 1, 16
        no_plane = stray_plane = not_unit = 0
        for t, v in samples:
            fl = int(v[9])
            mag = math.sqrt(v[14] * v[14] + v[15] * v[15] + v[16] * v[16])
            if fl & (FL_ONGROUND | FL_RAMP):
                if mag < 0.01:
                    no_plane += 1
                elif abs(mag - 1.0) > 0.01:
                    not_unit += 1
            elif mag > 0.01:
                stray_plane += 1

        if not_unit:
            r.fault("%d of %d samples carry a plane that is not a unit vector"
                    % (not_unit, len(samples)))
        if stray_plane:
            r.fault("%d of %d samples carry a plane while neither onground nor "
                    "ramp contact is set" % (stray_plane, len(samples)))
        if no_plane:
            # A NOTE and not a fault, and the reason is measured rather than
            # assumed.  run_groundnorm is not the floor under the player's feet:
            # SV_PlayerPostThink sweeps the hull one tick FORWARD along their own
            # velocity and takes whatever it hits, returning '0 0 0' both on a
            # miss and when the velocity is exactly zero.  So every sample of a
            # player standing still carries no plane, which is a real state --
            # and it is the same quantity the live strafe bar is fed through
            # STAT_FS_GROUNDNORM, which already handles the empty case.
            r.note("%d of %d samples are grounded or riding with no plane "
                   "recorded (standing still records none: see SV_RecNormal)"
                   % (no_plane, len(samples)))

        rc = sum(1 for _, v in samples if int(v[9]) & FL_RAMP)
        r.info["ramp_samples"] = rc
        if rc == 0 and boards:
            r.fault("%d board records but no sample has the ramp-contact bit -- "
                    "flags bit 16 is not being written" % len(boards))

    if ver >= 4 and "flags" in head:
        try:
            fv = int(float(head["flags"]))
        except ValueError:
            r.fault("header 'flags' is not a number: %r" % head["flags"])
        else:
            # TF_SHADOW implies TF_PRACTICE -- loading a save sets both -- and a
            # file claiming shadow without practice would put the wrong word on
            # the leaderboard's filter.
            if (fv & TF_SHADOW) and not (fv & TF_PRACTICE):
                r.fault("header flags %d says shadow without practice" % fv)
            r.info["clean"] = "no" if (fv & TF_PRACTICE) else "yes"

            # Build 44.  The same implication, twice more, and it is the whole
            # of what makes the split free downstream: SV_TimerFinish and
            # rec_sb_best refuse TF_PRACTICE and nothing was taught the new bits,
            # so a file asserting a class without the umbrella would be ranked
            # as a clean run while every word on screen called it cheated.
            if (fv & TF_SEGMENT) and not (fv & TF_PRACTICE):
                r.fault("header flags %d says segment without practice" % fv)
            if (fv & TF_CHEAT) and not (fv & TF_PRACTICE):
                r.fault("header flags %d says cheat without practice" % fv)
            r.info["class"] = run_class(fv)

            # Build 45.  The NAME and the flags have to agree about a cheated
            # run, in the ONE direction it is safe to assert.
            #
            # cheat.rec => TF_CHEAT is checkable because only build 45 and later
            # write that name, and SV_TimerFinish picks the tag from the same
            # run_t_flags word the header is stamped from a few lines later.  A
            # disagreement means those two reads have drifted -- which is the
            # exact bug the shared FS_TagName/FS_TagArchived pair exists to stop
            # and would be worth hearing about loudly.
            #
            # THE CONVERSE IS NOT ASSERTED, and adding it would be wrong for the
            # same reason as the TF_SHADOW note above: every cheated run build
            # 44 wrote is sitting in a `last.rec` right now, correctly flagged
            # and wrongly named, and faulting those would be faulting the
            # archive for predating the fix.
            tw = tag_from_name(path)
            if tw == "cheat" and not (fv & TF_CHEAT):
                r.fault("named cheat.rec but header flags %d does not say cheat"
                        % fv)

            # Build 30.  The header and the sample stream have to agree about
            # whether this run contains a ghost, in BOTH directions -- the whole
            # value of the bit is that a reader can trust it without scanning,
            # and a bit that can be set or cleared independently of the records
            # is worth nothing.
            #
            # Deliberately NOT an implication of TF_PRACTICE either way: a
            # ghosted run is not practice, and practice runs are not ghosts.
            if (fv & TF_GHOST) and not ghost_windows:
                r.fault("header flags %d says ghost, but there is no 'ghost' "
                        "record in the stream" % fv)
            if ghost_windows and not (fv & TF_GHOST):
                r.fault("%d ghost window(s) in the stream, but header flags %d "
                        "does not say ghost" % (len(ghost_windows), fv))
            r.info["ghosted"] = "yes" if (fv & TF_GHOST) else "no"

            # Build 58.  Reported, never faulted -- see TF_NOJOURNAL above.
            #
            # THREE STATES COLLAPSED INTO A BIT, which is why the word for the
            # unset case is "unknown" and not "yes".  Set means the client said
            # `rechid 0`; clear means it said 1 OR said nothing at all, and this
            # file cannot tell those apart.  Printing "yes, a journal exists"
            # off a clear bit would be inventing the difference -- and a .hid
            # beside the .rec is not proof either, since a run can finish with
            # the journal on and still write none (Rec_HidEnd keeps PB only).
            r.info["journal"] = "OFF (player set rec_hid 0)" if (fv & TF_NOJOURNAL) \
                                else "unknown"

            # Build 62.  Reported, never faulted -- see TF_NORULESET above, and
            # it collapses three states into a bit exactly as the journal one
            # does.  Set means the server read the key and it said the physics
            # were not provably the ruleset's.  Clear means the ruleset checked
            # out OR the engine was too old to publish the key at all, and this
            # file cannot tell those apart.  "certified" would be a claim the
            # bit does not support, so the clear word is "unknown".
            r.info["ruleset"] = "NOT LOCKED/CONFORMING" if (fv & TF_NORULESET) \
                                else "unknown"

    # ---- the v3 mask, against the movement it came from --------------------
    if ver >= 3:
        # 0:t 1..3:org 4..6:vel 7:pit 8:yaw 9:fl 10:keys 11:fwd 12:side 13:up
        for t, v in samples:
            keys = int(v[10])
            fwd, side = v[11], v[12]
            want = 0
            if fwd > 0:
                want |= FSI_FWD
            if fwd < 0:
                want |= FSI_BACK
            if side < 0:
                want |= FSI_LEFT
            if side > 0:
                want |= FSI_RIGHT
            got = keys & (FSI_FWD | FSI_BACK | FSI_LEFT | FSI_RIGHT)
            if got != want:
                mask_disagree += 1
        if mask_disagree:
            r.fault("%d of %d samples: the key mask's direction bits disagree "
                    "with the movement columns they are derived from"
                    % (mask_disagree, len(samples)))

    # ---- the trailer, against what is actually here ------------------------
    if saw_end is None:
        # A .part is an interrupted recording and has no trailer; that is not a
        # fault, it is what a .part is.  Nor does a SAVE PREFIX have one --
        # data/saves/<map>/saveNN/run.rec is the movement up to the save point
        # and the run it belongs to has not ended, so demanding a trailer of it
        # would report every save state as broken.
        if is_prefix(path):
            r.note("no 'end' record (expected: this is a save-state prefix)")
        elif path.endswith(".rec"):
            r.fault("no 'end' record in a finished .rec")
        else:
            r.note("no 'end' record (expected: this is an interrupted .part)")
    else:
        ln, args = saw_end
        if len(args) != 4:
            r.fault("line %d: 'end' takes 4 fields, has %d" % (ln, len(args)))
        else:
            e_ticks, e_n, e_pad, e_cp = (float(x) for x in args)
            if int(e_n) != len(samples):
                r.fault("'end' says %d samples, the file has %d"
                        % (int(e_n), len(samples)))
            if int(e_pad) != padding:
                r.fault("'end' says %d padding samples, the file has %d"
                        % (int(e_pad), padding))
            cps = sum(1 for _, k, _ in records if k == "cp")
            if int(e_cp) != cps:
                r.fault("'end' says %d checkpoints, the file has %d cp records"
                        % (int(e_cp), cps))
            r.info["ticks"] = int(e_ticks)
            r.info["time"] = e_ticks * tickrate

    # ---- rate, measured ----------------------------------------------------
    run = [t for t, _ in samples if t >= 0]
    if len(run) > 1:
        span = run[-1] - run[0]
        if span > 0:
            rate = (len(run) - 1) / span
            r.info["rate"] = rate
            nominal = 1.0 / tickrate
            if rate > nominal * 1.02:
                r.fault("sample rate %.1f/s is ABOVE the tick rate %.1f/s"
                        % (rate, nominal))
            elif rate < nominal * 0.5:
                r.note("sample rate %.1f/s is well under the tick rate %.1f/s "
                       "-- heavy packet loss, or a stall" % (rate, nominal))
    r.info["span"] = (samples[0][0], samples[-1][0])
    return r


def check_view(path, rec_report=None):
    """The angle sidecar.  cltime cmdframe ticks pitch yaw keys.

    VERSION 2 (build 22) added one header key, `hid`, saying whether a raw input
    journal was taken for this run.  The sample lines are unchanged, so a v1
    reader is still correct about every one of them -- the bump exists because
    this tool reports an unexpected header key as a finding, and a build that
    makes its own checker complain teaches everyone to stop reading it.
    """
    r = Report(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n").rstrip("\r") for l in f]

    if not lines or not lines[0].startswith("FTESURF-VIEW"):
        r.fault("first line is not 'FTESURF-VIEW <version>'")
        return r

    magic = lines[0].split()
    if len(magic) == 2:
        try:
            r.info["view_version"] = int(magic[1])
        except ValueError:
            r.fault("view version is not a number: %r" % magic[1])
            return r
    vver = r.info.get("view_version", 1)
    if vver not in (1, 2):
        r.fault("unknown .view version %d (this tool knows 1, 2)" % vver)
        return r
    vallowed = {"map"} | ({"hid"} if vver >= 2 else set())

    i = 1
    head = {}
    while i < len(lines) and lines[i].strip() != "begin":
        p = lines[i].split(None, 1)
        if p:
            head[p[0]] = p[1] if len(p) > 1 else ""
            if p[0] not in vallowed:
                r.note("unknown .view header key %r for version %d" % (p[0], vver))
        i += 1
    if i >= len(lines):
        r.fault("no 'begin' line")
        return r
    i += 1

    # Not a fault either way -- rec_hid can legitimately be off, and the whole
    # point of writing it down is that a run recorded without a journal is
    # visibly a run recorded without a journal rather than passing as one that
    # had one.  hidcheck.py is what cross-checks it against an actual .hid.
    if "hid" in head:
        r.info["hid"] = head["hid"].strip()

    frames = []
    view_ghosts = []        # (lineno, state, cltime, ticks) -- the sidecar's ghost edges
    for lineno in range(i, len(lines)):
        s = lines[lineno].strip()
        if not s:
            continue
        tok = s.split()
        if tok[0] == "ghost":
            # The sidecar's copy of the .rec's build-30 ghost edge: `ghost <0|1>
            # <cltime> <ticks>`, written by the client when the camera detaches
            # and re-attaches.  It carries no angles, so it is a marker row and
            # not a frame; a checker that only knew frames reported every ghosted
            # run's .view as "4 columns, expected 6" (first seen on the build-48
            # verification, b48c, 2026-09-09).  Counted and sanity-checked here;
            # the windows themselves are judged on the .rec side.
            if len(tok) != 4:
                r.fault("line %d: .view 'ghost' takes 3 fields, has %d" % (lineno + 1, len(tok) - 1))
                continue
            try:
                gst, gct, gtk = int(tok[1]), float(tok[2]), float(tok[3])
            except ValueError:
                r.fault("line %d: .view 'ghost' has a non-numeric field" % (lineno + 1))
                continue
            if gst not in (0, 1):
                r.fault("line %d: .view 'ghost' state %r is not 0 or 1" % (lineno + 1, tok[1]))
            elif view_ghosts and view_ghosts[-1][1] == gst:
                r.fault("line %d: .view 'ghost %d' repeats the previous edge's state" % (lineno + 1, gst))
            view_ghosts.append((lineno + 1, gst, gct, gtk))
            continue
        if len(tok) != 6:
            r.fault("line %d has %d columns, expected 6" % (lineno + 1, len(tok)))
            continue
        try:
            frames.append([float(x) for x in tok])
        except ValueError:
            r.fault("line %d has a non-numeric column" % (lineno + 1))

    if not frames:
        r.fault("no frames")
        return r

    r.info["frames"] = len(frames)

    # BOTH OF THESE CLOCKS MAY RESET EXACTLY ONCE, and only build 18 made that
    # true.  cltime is realtime - cl.mapstarttime and clientcommandframe is
    # cl.movesequence; a `retry` restarts the map underneath the run, which
    # zeroes both while the run itself carries on.  So a single backwards step
    # is the signature of a retry join and is expected; two means the file has
    # been spliced from unrelated attempts, which is a real fault.
    #
    # The .rec's `retry` record is the other half of this and says where.
    resets = [(i, a[0], b[0]) for i, (a, b) in enumerate(zip(frames, frames[1:]))
              if b[0] < a[0]]
    cmdresets = [(i, a[1], b[1]) for i, (a, b) in enumerate(zip(frames, frames[1:]))
                 if b[1] < a[1]]

    if len(resets) > 1:
        r.fault("cltime goes backwards %d times -- at most one (a retry) is "
                "expected; first at frame %d, %.4f after %.4f"
                % (len(resets), resets[0][0] + 1, resets[0][2], resets[0][1]))
    elif resets:
        r.note("cltime restarts once at frame %d (%.4f after %.4f) -- a retry"
               % (resets[0][0] + 1, resets[0][2], resets[0][1]))

    if len(cmdresets) > 1:
        r.fault("clientcommandframe goes backwards %d times -- at most one (a "
                "retry) is expected; first at frame %d, %g after %g"
                % (len(cmdresets), cmdresets[0][0] + 1,
                   cmdresets[0][2], cmdresets[0][1]))

    # THE RUN CLOCK IS THE INVARIANT THAT SURVIVES A RETRY, and therefore the
    # only key a cross-file join may use across one.  Field 2 is
    # STAT_FS_TIMERTICKS, which the server restores unrounded precisely so that
    # it stays continuous through a restart the other two clocks do not.
    for i, (a, b) in enumerate(zip(frames, frames[1:])):
        if b[2] < a[2]:
            r.fault("run clock goes backwards at frame %d: %g after %g -- the "
                    "one column that must not" % (i + 1, b[2], a[2]))
            break

    span = frames[-1][0] - frames[0][0]
    if span > 0:
        r.info["fps"] = (len(frames) - 1) / span
    cmds = len(set(f[1] for f in frames))
    r.info["usercmds"] = cmds
    if cmds:
        r.info["frames_per_cmd"] = len(frames) / cmds

    if rec_report and "ticks" in rec_report.info:
        vmax = max(f[2] for f in frames)
        if vmax > rec_report.info["ticks"]:
            r.fault("sidecar reaches tick %g, the recording ends at %d"
                    % (vmax, rec_report.info["ticks"]))
    return r


def ramp_report(path):
    """Build 25 -- WHY DOES THE STRAFE INDICATOR FLICKER ON A RAMP?

    Two candidate mechanisms, both in the engine, both per-tick, and they look
    identical on screen while wanting opposite fixes:

      the CONTACT drops out    PMSrc_Tick clears rampcontact and rampnormal at
                               the top of every tick (pm_source.c:2665) and only
                               a tick whose trace actually hits the ramp sets
                               them again (:1135).  A tick that clears its whole
                               move sets neither, so the client flips between
                               the ramp regime and the air regime mid-ride.

      the PLANE alternates     rampnormal is whatever the LAST BUMP of that tick
                               clipped (:1142), so a curved or displacement ramp
                               legitimately reports different facet normals on
                               consecutive ticks.  The target rate follows them
                               and there is no dropout at all.

    A .rec v4 records both -- flags bit 16 is the contact and columns 14..16 are
    the plane -- so the file answers the question exactly, per tick, which is
    something no live readout can do against a 66.7 Hz stat.

    A RIDE is a run of samples bounded by a gap longer than GAPMAX_S.  That is
    deliberately far longer than the client's own 0.08s hold (the engine's
    PMSRC_BOARD_AIRGATE, which the fix reuses): if the two matched, this could
    never report a gap the hold refuses to bridge, which is the single most
    useful thing it can say.
    """
    GAPMAX_S = 0.5
    FL_RAMP = 16
    HOLD_S = 0.08                       # RAMP_GAP, the client's hold

    # HOW DIFFERENT IS "A DIFFERENT PLANE", and the first answer was wrong.
    #
    # This was cos(2.6 deg) on the reasoning that anything smaller was float
    # noise.  There is no float noise: the engine VectorCopy's pm.plane.normal
    # into pmove.rampnormal unchanged and the recorder writes it to four
    # decimals, so an unchanged plane comes back bit-identical and dots to
    # exactly 1.0.  Meanwhile a real curved ramp's facets are much closer
    # together than 2.6 degrees -- the fixture rotates one 4 degrees about z,
    # which moves the NORMAL only 2.3, and the tight threshold reported zero
    # flips on a file built to have nothing else.  That is the negative control
    # doing its job and it caught the constant rather than the code.
    #
    # So: as tight as the format allows.  cos(0.26 deg) is comfortably inside
    # any real facet difference and comfortably outside four-decimal rounding.
    SAME = 0.99999

    head, samples = {}, []
    ver = 0
    with open(path, "r", errors="replace") as f:
        first = f.readline().split()
        if len(first) >= 2 and first[0] == "FTESURF-REC":
            ver = int(first[1])
        inhead = True
        for line in f:
            tok = line.split()
            if not tok:
                continue
            if inhead:
                if tok[0] == "begin":
                    inhead = False
                elif len(tok) >= 2:
                    head[tok[0]] = tok[1]
                continue
            if is_sample(tok[0]) and len(tok) >= COLUMNS[4]:
                samples.append([float(x) for x in tok])

    if ver < 4:
        print("%s: FTESURF-REC %d -- no ramp bit and no per-sample plane.  "
              "Only a v4 recording can answer this."
              % (os.path.basename(path), ver))
        return

    tick = float(head.get("tickrate", 0.015)) or 0.015
    gapmax = max(1, int(round(GAPMAX_S / tick)))
    holdticks = HOLD_S / tick

    print("%s  %d samples, tick %.4f"
          % (os.path.basename(path), len(samples), tick))

    rides, cur, gap = [], None, 0
    for v in samples:
        if int(v[9]) & FL_RAMP:
            if cur is None:
                cur = {"t0": v[0], "t1": v[0], "ticks": 0,
                       "gaps": [], "flips": 0, "n": None, "worstdot": 1.0}
            elif gap:
                cur["gaps"].append(gap)
            gap = 0
            cur["ticks"] += 1
            cur["t1"] = v[0]

            n = (v[14], v[15], v[16])
            if abs(n[0] * n[0] + n[1] * n[1] + n[2] * n[2] - 1.0) < 0.05:
                if cur["n"] is not None:
                    d = sum(a * b for a, b in zip(n, cur["n"]))
                    if d < SAME:
                        cur["flips"] += 1
                    # The SIZE of the largest change, not just that there was
                    # one: a ride whose facets differ by a twentieth of a degree
                    # is alternating in a way nothing on screen could show, and
                    # one whose facets differ by ten degrees is a different
                    # report entirely.  A count alone cannot tell them apart.
                    cur["worstdot"] = min(cur["worstdot"], d)
                cur["n"] = n
        elif cur is not None:
            gap += 1
            if gap > gapmax:
                rides.append(cur)
                cur, gap = None, 0
    if cur is not None:
        rides.append(cur)

    if not rides:
        print("  no ramp contact anywhere in this file")
        return

    over = 0
    print("  %-9s %-9s %6s %6s %6s %6s %8s"
          % ("t0", "t1", "ticks", "gaps", "worst", "flips", "maxturn"))
    for rd in rides:
        worst = max(rd["gaps"]) if rd["gaps"] else 0
        if worst > holdticks:
            over += 1
        print("  %-9.3f %-9.3f %6d %6d %6d %6d %7.2fd"
              % (rd["t0"], rd["t1"], rd["ticks"], len(rd["gaps"]),
                 worst, rd["flips"],
                 math.degrees(math.acos(max(-1.0, min(1.0, rd["worstdot"]))))))

    tot_t = sum(rd["ticks"] for rd in rides)
    tot_g = sum(len(rd["gaps"]) for rd in rides)
    tot_f = sum(rd["flips"] for rd in rides)
    worstdot = min(rd["worstdot"] for rd in rides)
    print("  %d ride(s), %d contact ticks, %d bridged gap(s), %d plane flip(s), "
          "biggest plane change %.2f deg"
          % (len(rides), tot_t, tot_g, tot_f,
             math.degrees(math.acos(max(-1.0, min(1.0, worstdot))))))
    print("  the client's hold is %.2fs = %.1f ticks; %d ride(s) contain a gap "
          "longer than that" % (HOLD_S, holdticks, over))

    # The verdict, spelled out, because the point of the tool is to CHOOSE
    # between the two mechanisms rather than to print a table somebody then has
    # to interpret.  Build 12's pale-ramp measurement is the precedent: a
    # diagnostic that does not commit to a reading gets read as whatever the
    # person already believed.
    if not tot_g and not tot_f:
        print("  VERDICT: neither.  The contact never dropped and the plane "
              "never changed -- the flicker is not in this data.")
    elif tot_g and not tot_f:
        print("  VERDICT: the CONTACT drops out.  The 0.08s hold is the fix.")
    elif tot_f and not tot_g:
        print("  VERDICT: the PLANE alternates.  A contact hold cannot touch "
              "it; the plane needs holding or averaging instead.")
    else:
        print("  VERDICT: both are present.  Fix the contact first -- it is the "
              "larger regime change -- and re-measure.")


def emit(r, verbose):
    tag = "ok  " if r.ok else "FAIL"
    print("%s %s" % (tag, os.path.basename(r.path)))
    if verbose or not r.ok:
        for k in ("version", "map", "track", "startseg", "samples", "padding",
                  "records", "checkpoints", "cp_ordinals", "resumes",
                  "resumed_from", "retries", "retried_at",
                  # Build 43.  Same class of fact as `resumes`: the sample
                  # stream is continuous across both, so a reader that does not
                  # print them cannot tell a run that was taken once from one
                  # whose stage was reset four times.
                  "stagestarts", "stage_restarts",
                  # Build 24, v4.  `clean` is the one the leaderboard filters on
                  # and the one worth being able to read off a file by hand.
                  # Build 44.  `class` is `clean`'s successor and both are
                  # printed: the first is what every reader before this build
                  # filtered on, the second is why.
                  "boards", "ramp_samples", "clean", "class",
                  # Build 62.  These three were being COMPUTED AND DISCARDED --
                  # each is assigned into r.info above and none was in this
                  # tuple, so a reader could not see them at any verbosity.
                  # `ghosted` and `journal` date from builds 30 and 58 and have
                  # been invisible ever since; `ruleset` would have shipped the
                  # same way, which is how it was noticed.  A field nobody can
                  # read is not evidence, which is the whole argument this
                  # file's own header makes for writing the checker from the
                  # grammar rather than from the writer.
                  "ghosted", "journal", "ruleset",
                  "ticks", "time", "rate", "view_version", "hid", "frames",
                  "fps", "usercmds", "frames_per_cmd"):
            if k in r.info:
                v = r.info[k]
                print("       %-14s %s" % (k, ("%.3f" % v) if isinstance(v, float) else v))
    for m in r.faults:
        print("     ! %s" % m)
    if verbose:
        for m in r.notes:
            print("     - %s" % m)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--verbose", "-v", action="store_true")
    # Build 25.  Not part of the sweep: it is a measurement of one ride, it
    # prints a table per file, and running it over fifty recordings would bury
    # the one answer it exists to give.  See ramp_report.
    ap.add_argument("--ramps", action="store_true",
                    help="per-ride ramp contact and plane analysis (v4 only)")
    a = ap.parse_args()

    if a.ramps:
        if not a.files:
            raise SystemExit("--ramps needs a .rec to look at")
        for p in a.files:
            ramp_report(p)
        return 0

    files = a.files
    if not files:
        # Save prefixes are checked by default too.  They are the same format
        # written by the same code, they are what a shadow run is built on, and
        # a prefix that is malformed produces a resumed run that is malformed
        # from its first line -- so leaving them out of the default sweep would
        # hide the failure one step upstream of where it shows.
        # BUILD 23 moved runs to data/runs/<map>/<leg>/<ticks>_<tag>.rec.  The
        # old flat pattern is kept in the sweep rather than replaced: a tree
        # that has not been through tools/migrate_runs.py still has files in it,
        # and a checker that silently stops looking at them is worse than one
        # that finds nothing -- "0 files, all clean" reads exactly like success.
        files = sorted(glob.glob(os.path.join(RUNS, "*", "*", "*.rec")) +
                       glob.glob(os.path.join(RUNS, "*.rec")) +
                       glob.glob(os.path.join(RUNS, "*.part")) +
                       glob.glob(os.path.join(SAVES, "*", "*", "run.rec")))
        if not files:
            raise SystemExit("nothing to check in %s or %s" % (RUNS, SAVES))

    bad = 0
    for p in files:
        # A .view NAMED ON THE COMMAND LINE is checked as a .view, not fed to
        # check_rec first.  Without this, `reccheck.py some/run.view` reported a
        # FAIL ("first line is not FTESURF-REC") and an ok for the same file --
        # which reads as a broken sidecar and is only the tool checking it twice.
        # The sweep still pairs them the other way round, from the .rec.
        if p.endswith(".view"):
            v = check_view(p, None)
            emit(v, a.verbose)
            bad += 0 if v.ok else 1
            continue

        r = check_rec(p, a.verbose)
        emit(r, a.verbose)
        bad += 0 if r.ok else 1

        view = os.path.splitext(p)[0] + ".view"
        if os.path.exists(view):
            v = check_view(view, r)
            emit(v, a.verbose)
            bad += 0 if v.ok else 1

    print("\n%d file(s) checked, %d with faults" % (len(files), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
