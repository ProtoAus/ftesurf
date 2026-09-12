#!/usr/bin/env python3
"""
migrate_runs.py -- the moves of data/runs that QC cannot make itself.

    (default)  the flat build-22 layout  -> build 23's per-map folders
    legs1      build 23..56's stage folders, named by segment -> build 57's, by leg

A tree old enough to need both takes them in that order: the build-22 move
writes build 23's segment-numbered folders, and legs1 renumbers those.

Usage:
    python tools/migrate_runs.py [--apply] [--runs <dir>]
    python tools/migrate_runs.py legs1 <runs_dir> [--apply] [--backup-dir DIR]

===========================================================================
THE BUILD-22 MOVE (the default job)
===========================================================================

    data/runs/surf_utopia.pb                     -> data/runs/surf_utopia/best.pb
    data/runs/surf_utopia_t0_s0_pb.rec           -> data/runs/surf_utopia/main/0004108_pb.rec
    data/runs/surf_utopia_t0_s0_pb.view          ->                             0004108_pb.view
    data/runs/surf_utopia_t0_s0_pb.hid           ->                             0004108_pb.hid
    data/runs/surf_utopia_t0_s0_last.rec         -> data/runs/surf_utopia/main/last.rec
    data/runs/surf_ace_t0_s3_pb.rec              -> data/runs/surf_ace/stage_3/...
    data/runs/surf_ace_t1_s0_pb.rec              -> data/runs/surf_ace/bonus_1/...

QC cannot move a file, so this exists rather than a one-shot upgrade path in the
game.  Without it every recording already on disk is simply invisible to the new
build -- not lost, but orphaned, which is worse because nothing says so.

THE TIME COMES OUT OF THE FILE, not out of a guess.  Every .rec carries an
`end <ticks> ...` trailer, which is the same number SV_RecClose puts in the new
filename, so a migrated file is named exactly as the game would have named it.
A .rec whose trailer is missing or unreadable is REFUSED and left where it is:
inventing a time would put a wrong row on a leaderboard, and a file left behind
is a file you can still look at.

A .view or .hid is named from the tick count of the .rec it belongs to.  One
without a .rec cannot be placed and is left alone, for the same reason.

BUILD 57: this job still writes build 23's layout -- `_s3` is segment 3 and goes
to stage_3 (seg_dir_build23), exactly as builds 23 to 56 filed it -- because the
<map>.pb it moves beside those folders is a version-1 file keyed the same way.
Placing the recordings by leg while the .pb stayed keyed by segment would hand
legs1 a map that is half of each.  Run legs1 after it.  It refuses a tree legs1
has already marked, for the same reason.

Dry run by default.  Pass --apply to actually move anything.

===========================================================================
LEGS1 -- BUILD 57, 2026-09-12: A STAGE FOLDER IS NAMED BY ITS LEG
===========================================================================

    data/runs/surf_kitsune/stage_1/          -> stage_2/        (it always held stage 2)
    data/runs/surf_garden/stage_9/           -> stage_10/
    data/runs/<map>/bonus_1_stage_2/         -> bonus_1_stage_3/
    data/runs/<map>/best.pb   FTESURF-PB 1   -> FTESURF-PB 2
                              best 0 1 179   -> best 0 2 179
                              best 0 0 ..., split ..., cp ...  byte for byte

Builds 23 to 56 named a stage folder by the 0-based SEGMENT its run started in,
and segment 0 was the full run -- so Momentum's stage 1 had no folder at all and
every other stage sat one number low: kitsune's stage_1 held stage 2.  Build 57
names it by LEG, 0 the full run and k stage k, which is what the HUD, `!s` and
the scoreboard's row labels always meant.  `split t seg` and `cp` lines are
still keyed by segment and do not move; neither does any .rec's `startseg`.

HIGHEST N FIRST.  Renaming upward in ascending order would put stage_1 onto a
stage_2 that has not moved out of the way yet.

THE NUMBERING COMES OUT OF THE FILES, as the time does above.  Every .rec in a
stage folder carries `startseg`: builds 23 to 56 put startseg N into stage_N, and
build 57 puts startseg N-1 (and `leg N`) there.  A map whose recordings disagree
with its best.pb header, or with each other, is REFUSED -- that is a map build 57
has already written into, and no rename can tell its old files from its new
ones -- and --apply will not start while any map is refused.  Nothing is ever
half-done by design; sort the map out by hand, then run it again.

ONCE ONLY, three ways.  --apply copies the whole tree to <runs>.backup-build57
first and refuses if that already exists.  It marks the tree .legs1.partial while
it works and .legs1 when it has finished, and refuses to start on either.  And a
best.pb that already says FTESURF-PB 2 is skipped with a message, along with its
map's folders.  The dry run re-derives everything from the files rather than
from the marker, so run it afterwards: it must find nothing left to do.

MIGRATE WITH THE GAME CLOSED AND BUILD 57 IN PLACE.  A build before 57 reads the
migrated `best 0 2 179` as segment 2, which is stage 3, and its next save writes
that back under a version-1 header -- which build 57 then shifts a second time,
because it shifts a version-1 file's keys on load.

AND RUN IT BEFORE PLAYING BUILD 57 AT ALL -- listen server or lobby, one run is
enough.  This is the ordering that bites, because nothing stops you:

    install build 57  ->  play one staged map  ->  run legs1  ->  REFUSED

A finish on build 57 makes SV_PBSave rewrite that map's best.pb as FTESURF-PB 2
while its stage folders are still segment-numbered, and a lobby finish writes
`<ticks>_lobby.rec` into a leg-numbered folder beside segment-numbered ones.
legs1 then reads a map whose file says one numbering and whose folders say the
other, refuses it -- correctly, because no rename can tell the two apart -- and
--apply refuses the WHOLE tree while any map is refused.  The way out is by hand.

So: compile build 57, run legs1 --apply, and only then play.
"""

import os
import re
import sys
import time
import shutil
import argparse

# <map>_t<track>_s<startseg>_<tag>.<ext>.  The map name may itself contain
# underscores and digits (surf_utopia_v2), so the leg part is anchored to the
# END of the stem and the map is whatever is left -- matching from the front
# would swallow the map at the first _t it met.
STEM = re.compile(r"^(?P<map>.+)_t(?P<track>\d+)_s(?P<seg>\d+)_(?P<tag>pb|last|shadow)$")

ARCHIVED = ("pb", "shadow")


def leg_dir(track, leg):
    """The mirror of FS_LegDir in src/shared/sh_defs.qc.  Keep them in step.

    BUILD 57, 2026-09-12: the second argument is the LEG -- 0 the full run of the
    track, k stage k -- and no longer the 0-based segment the run started in.
    Stage 1 now has a folder of its own and stage_k holds stage k.  Before, segment
    0 was `main` and every stage folder was named one lower than the stage inside
    it; seg_dir_build23 keeps that spelling, and legs1 moves one onto the other.
    """
    if track <= 0:
        return "main" if leg <= 0 else "stage_%d" % leg
    if leg <= 0:
        return "bonus_%d" % track
    return "bonus_%d_stage_%d" % (track, leg)


def seg_dir_build23(track, seg):
    """FS_LegDir as builds 23 to 56 spelled it, keyed by the 0-based SEGMENT.

    Frozen here and mirroring nothing live: the build-22 move still writes this
    layout (see the docstring above for why), and it is what legs1 reads.
    """
    if track <= 0:
        return "main" if seg <= 0 else "stage_%d" % seg
    if seg <= 0:
        return "bonus_%d" % track
    return "bonus_%d_stage_%d" % (track, seg)


def read_end_ticks(path):
    """The `end <ticks> ...` trailer of a .rec, or None."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            # The trailer is near the end but `split` records follow it, so the
            # whole tail is scanned rather than just the last line.
            tail = fh.readlines()[-64:]
    except OSError:
        return None
    for ln in reversed(tail):
        f = ln.split()
        if len(f) >= 2 and f[0] == "end":
            try:
                return int(float(f[1]))
            except ValueError:
                return None
    return None


def plan(runs):
    """Return (moves, skips).  moves is a list of (src, dst)."""
    moves, skips = [], []
    try:
        entries = sorted(os.listdir(runs))
    except OSError as e:
        print("cannot read %s: %s" % (runs, e))
        return moves, skips

    # Pass 1: the .pb files.
    for name in entries:
        src = os.path.join(runs, name)
        if not os.path.isfile(src) or not name.endswith(".pb"):
            continue
        mapname = name[:-3]
        moves.append((src, os.path.join(runs, mapname, "best.pb")))

    # Pass 2: recordings.  Group by stem so .rec/.view/.hid share one tick count.
    groups = {}
    for name in entries:
        src = os.path.join(runs, name)
        if not os.path.isfile(src):
            continue
        stem, dot, ext = name.rpartition(".")
        if dot != "." or ext not in ("rec", "view", "hid"):
            continue
        m = STEM.match(stem)
        if not m:
            skips.append((src, "filename is not <map>_t<n>_s<n>_<tag>"))
            continue
        groups.setdefault(stem, {})[ext] = (src, m)

    for stem in sorted(groups):
        files = groups[stem]
        m = list(files.values())[0][1]
        mapname = m.group("map")
        track = int(m.group("track"))
        seg = int(m.group("seg"))
        tag = m.group("tag")
        dstdir = os.path.join(runs, mapname, seg_dir_build23(track, seg))

        if tag in ARCHIVED:
            if "rec" not in files:
                for ext, (src, _) in sorted(files.items()):
                    skips.append((src, "no .rec beside it, so its time is unknown"))
                continue
            ticks = read_end_ticks(files["rec"][0])
            if ticks is None:
                for ext, (src, _) in sorted(files.items()):
                    skips.append((src, "the .rec has no readable `end <ticks>` trailer"))
                continue
            base = "%07d_%s" % (ticks, tag)
        else:
            base = tag                      # `last` keeps its fixed name

        for ext, (src, _) in sorted(files.items()):
            moves.append((src, os.path.join(dstdir, "%s.%s" % (base, ext))))

    return moves, skips


# ===========================================================================
#  legs1
# ===========================================================================

LEGS1_MARKER = ".legs1"
LEGS1_PARTIAL = ".legs1.partial"
LEGS1_BACKUP_SUFFIX = ".backup-build57"

# sv_timer.qc.  SV_PBLoad keeps a key of 0..23 and drops 24 and up, so a stage
# that shifts to leg 24 is carried over but not read.  Five mapmeta rows have 24
# or more stages and already truncate; this migration does not change that.
FS_MAXSPLITS = 24

# The names seg_dir_build23 writes.  %d of a positive number: no leading zero,
# and never stage_0, because segment 0 was `main`.
STAGE_DIR = re.compile(r"^(?:bonus_(?P<track>[1-9][0-9]*)_)?stage_(?P<n>[1-9][0-9]*)$")
FIXED_DIR = re.compile(r"^(?:main|bonus_[1-9][0-9]*)$")

# A word as tokenize() splits a best.pb line.
PB_WORD = re.compile(rb"[^ \t\r\n\f\v]+")


def pb_version(data):
    """1 or 2 from a best.pb's first line, or None when it is neither."""
    lines = data.splitlines()
    words = lines[0].split() if lines else []
    if len(words) == 2 and words[0] == b"FTESURF-PB" and words[1] in (b"1", b"2"):
        return int(words[1])
    return None


def pb_shift(data):
    """A version-1 best.pb as version 2.  Returns (bytes, changes, problems, notes).

    Two things change and nothing else: the version word of the header, and the
    third word of a `best` line whose stage key is above zero.  Each is replaced
    in place, between the bytes around it, so spacing, line endings, the date
    comment, `best t 0`, `split`, `cp` and any line this tool has never heard of
    come out exactly as they went in, in the same order.  Re-formatting the lines
    instead would be one more place for a number to drift.
    """
    out, changes, problems, notes = [], [], [], []
    for i, line in enumerate(data.splitlines(True)):
        spans = [m.span() for m in PB_WORD.finditer(line)]
        words = [line[a:b] for a, b in spans]
        new = line
        if i == 0:
            a, b = spans[1]                 # pb_version checked there are two
            new = line[:a] + b"2" + line[b:]
        elif len(words) >= 4 and words[0] == b"best":
            key = words[2]
            if key.isdigit():
                s = int(key)
                if s > 0:
                    a, b = spans[2]
                    new = line[:a] + (b"%d" % (s + 1)) + line[b:]
                    if s + 1 >= FS_MAXSPLITS:
                        notes.append("best.pb line %d: leg %d is past the %d legs build 57 "
                                     "loads; kept, not read" % (i + 1, s + 1, FS_MAXSPLITS - 1))
            else:
                # SV_PBSave writes %g of a whole number, so this is not a file the
                # game wrote.  stof reads a positive spelling of it as a stage key
                # that should shift, and guessing how to re-spell it is exactly the
                # kind of guess this tool does not make.  Zero, negative and
                # non-numbers load as the full run or not at all, and stay put.
                try:
                    positive = float(key) > 0
                except ValueError:
                    positive = False
                if positive:
                    problems.append("best.pb line %d: stage key %s is not a whole number"
                                    % (i + 1, key.decode("ascii", "backslashreplace")))
        if new != line:
            changes.append((line.rstrip(b"\r\n"), new.rstrip(b"\r\n")))
        out.append(new)
    return b"".join(out), changes, problems, notes


def rec_header(path):
    """(startseg, leg) from a .rec's header; either is None when it is absent."""
    got = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for n, ln in enumerate(fh):
                f = ln.split()
                if n >= 64 or (f and f[0] == "begin"):
                    break
                if len(f) >= 2 and f[0] in ("startseg", "leg"):
                    try:
                        got[f[0]] = int(float(f[1]))
                    except ValueError:
                        pass
    except OSError:
        pass
    return got.get("startseg"), got.get("leg")


def folder_numbering(path, n):
    """Which numbering the recordings in a stage_<n> folder were filed under.

    Returns ("segment", why), ("leg", why), ("none", "") when no .rec says, or
    ("conflict", why).  Builds 23 to 56 put startseg N into stage_N; build 57 puts
    startseg N-1 and `leg N` there.  Neither build can write the other's number,
    so one file is enough to tell -- and two files that disagree mean the folder
    holds both builds' runs.

    A header with neither key says nothing and is not counted against anything.
    """
    seen = {}
    folder = os.path.basename(path)
    try:
        names = sorted(os.listdir(path))
    except OSError as e:
        return "conflict", "%s: cannot list it (%s)" % (folder, e)
    for name in names:
        if not name.endswith(".rec"):
            continue
        ss, leg = rec_header(os.path.join(path, name))
        if leg is not None:
            kind = "leg" if leg == n else None
        elif ss is None:
            continue
        elif ss == n:
            kind = "segment"
        elif ss == n - 1:
            kind = "leg"
        else:
            kind = None
        said = "%s/%s has %s%s" % (folder, name,
                                   "no startseg" if ss is None else "startseg %d" % ss,
                                   "" if leg is None else ", leg %d" % leg)
        if kind is None:
            return "conflict", said + ", which fits neither numbering"
        seen.setdefault(kind, said)
    if len(seen) == 2:
        return "conflict", "%s (builds 23-56) but %s (build 57)" % (seen["segment"], seen["leg"])
    for kind, said in seen.items():
        return kind, said
    return "none", ""


def legs1_map(runs, mapname, marked):
    """Everything legs1 would do to one map folder, decided before any of it is done."""
    mdir = os.path.join(runs, mapname)
    mp = {"map": mapname, "renames": [], "pb": None, "pb_src": None, "changes": [],
          "refused": [], "skipped": None, "check": [], "left": [], "notes": []}
    try:
        entries = sorted(os.listdir(mdir))
    except OSError as e:
        mp["refused"].append("cannot list it (%s)" % e)
        return mp

    stages = []
    for e in entries:
        if not os.path.isdir(os.path.join(mdir, e)):
            continue
        m = STAGE_DIR.match(e)
        if m:
            stages.append((int(m.group("track") or 0), int(m.group("n")), e))
        elif not FIXED_DIR.match(e):
            mp["left"].append((e, "not a folder name FS_LegDir writes"))

    # Highest N first, and the whole sequence walked against the names that will
    # exist at each step -- lower-cased, because Windows calls Stage_4 and stage_4
    # one folder.  With only game-written names the top target is always free and
    # each later one has just been vacated, so a hit here is a name the game did
    # not write, sitting where a stage has to go.
    stages.sort(key=lambda s: (-s[1], s[0]))
    taken = set(e.lower() for e in entries)
    for track, n, e in stages:
        dst = leg_dir(track, n + 1)
        if dst.lower() in taken:
            mp["refused"].append("%s -> %s: something named %s is already there" % (e, dst, dst))
            continue
        taken.discard(e.lower())
        taken.add(dst.lower())
        mp["renames"].append((e, dst))
        if n + 1 >= FS_MAXSPLITS:
            mp["notes"].append("%s: leg %d is past the %d legs build 57 lists; moved, not shown"
                               % (dst, n + 1, FS_MAXSPLITS - 1))

    seg, leg = [], []
    for track, n, e in stages:
        kind, why = folder_numbering(os.path.join(mdir, e), n)
        if kind == "conflict":
            mp["refused"].append(why)
        elif kind == "segment":
            seg.append(why)
        elif kind == "leg":
            leg.append(why)

    pbpath = os.path.join(mdir, "best.pb")
    pbv, data = "missing", None
    if os.path.isfile(pbpath):
        try:
            with open(pbpath, "rb") as fh:
                data = fh.read()
            pbv = pb_version(data) or "unknown"
        except OSError as e:
            pbv = "unreadable"
            mp["refused"].append("cannot read best.pb (%s)" % e)

    if pbv == "unknown":
        mp["refused"].append("best.pb does not begin FTESURF-PB 1 or FTESURF-PB 2")
    if seg and leg:
        mp["refused"].append("%s (builds 23-56), yet %s (build 57)" % (seg[0], leg[0]))
    if pbv == 2 and seg:
        mp["refused"].append("best.pb is FTESURF-PB 2, yet %s -- a builds 23-56 folder" % seg[0])
    if pbv == 1 and leg:
        mp["refused"].append("best.pb is FTESURF-PB 1, yet %s -- a build 57 folder" % leg[0])

    if mp["refused"]:
        mp["renames"] = []
        return mp

    if pbv == 2 or (pbv == "missing" and leg):
        mp["renames"] = []
        if pbv == 2:
            mp["skipped"] = "best.pb is already FTESURF-PB 2; its folders are left as they are"
        else:
            mp["skipped"] = "no best.pb, and %s -- already on build 57's legs" % leg[0]
        return mp

    if marked:
        # The marker says this tree is done, so nothing here is work to do: it is
        # what the check found.  A version-1 best.pb or a segment-numbered folder
        # in a marked tree was written by a build older than 57 after the
        # migration, and renaming on top of that is the second shift the marker
        # exists to prevent.  A folder with no evidence either way is taken at the
        # marker's word.
        mp["renames"] = []
        if pbv == 1:
            mp["check"].append("best.pb is FTESURF-PB 1 in a migrated tree -- saved by a build "
                               "older than 57 after legs1 ran?")
        if seg:
            mp["check"].append("%s -- a builds 23-56 folder in a migrated tree" % seg[0])
        return mp

    if pbv == 1:
        new, changes, problems, notes = pb_shift(data)
        if problems:
            mp["refused"].extend(problems)
            mp["renames"] = []
            return mp
        mp["pb"], mp["pb_src"], mp["changes"] = new, data, changes
        mp["notes"].extend(notes)
    return mp


def legs1_flat_leftovers(runs):
    """Files at the top of the tree that the build-22 move has not placed yet."""
    out = []
    for name in sorted(os.listdir(runs)):
        if os.path.isfile(os.path.join(runs, name)) and \
                name.rpartition(".")[2] in ("pb", "rec", "view", "hid"):
            out.append(name)
    return out


def tree_census(root):
    """{relative path: size} of every file under root."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            p = os.path.join(dirpath, name)
            out[os.path.relpath(p, root)] = os.path.getsize(p)
    return out


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as e:
        return "(cannot read it: %s)\n" % e


def as_text(b):
    return b.decode("utf-8", "backslashreplace")


def legs1_print(plans):
    for mp in plans:
        lines = []
        for src, dst in mp["renames"]:
            lines.append("    rename   %-24s -> %s" % (src, dst))
        for old, new in mp["changes"]:
            lines.append("    best.pb  %-24s -> %s" % (as_text(old), as_text(new)))
        for why in mp["refused"]:
            lines.append("    REFUSED  %s" % why)
        if mp["skipped"]:
            lines.append("    SKIP     %s" % mp["skipped"])
        for why in mp["check"]:
            lines.append("    CHECK    %s" % why)
        for name, why in mp["left"]:
            lines.append("    LEFT     %-24s %s" % (name, why))
        for why in mp["notes"]:
            lines.append("    note     %s" % why)
        if lines:
            print("  %s" % mp["map"])
            for ln in lines:
                print(ln)


def legs1_main(argv):
    ap = argparse.ArgumentParser(
        prog="migrate_runs.py legs1",
        description="Build 57: rename stage_N -> stage_N+1 (highest first) and rewrite "
                    "best.pb as FTESURF-PB 2.  Dry run unless --apply.")
    ap.add_argument("runs_dir", help="a data/runs tree, e.g. ftesurf/data/runs")
    ap.add_argument("--apply", action="store_true",
                    help="back the tree up, then rename and rewrite")
    ap.add_argument("--backup-dir",
                    help="where --apply copies the tree first (default: <runs_dir>%s)"
                         % LEGS1_BACKUP_SUFFIX)
    a = ap.parse_args(argv)

    runs = os.path.normpath(os.path.abspath(a.runs_dir))
    backup = (os.path.normpath(os.path.abspath(a.backup_dir)) if a.backup_dir
              else runs + LEGS1_BACKUP_SUFFIX)
    marker = os.path.join(runs, LEGS1_MARKER)
    partial = os.path.join(runs, LEGS1_PARTIAL)

    print("runs directory: %s" % runs)
    if not os.path.isdir(runs):
        print("  does not exist -- nothing to migrate")
        return 1

    marked = os.path.exists(marker)
    stopped = os.path.exists(partial)
    if marked:
        print("  %s is there -- legs1 has already run on this tree:" % LEGS1_MARKER)
        for ln in read_text(marker).splitlines():
            print("      %s" % ln)
        if a.apply:
            print("  Refusing: a second --apply would shift every stage again.  Nothing changed.")
            return 1
        print("  Checking the files anyway.")
    if stopped:
        print("  %s is there -- an earlier --apply stopped part way through:" % LEGS1_PARTIAL)
        for ln in read_text(partial).splitlines():
            print("      %s" % ln)
        print("  Put the backup named there back first: delete %s, rename the backup" % runs)
        print("  to %s, and run legs1 --apply again." % os.path.basename(runs))
        if a.apply:
            print("  Refusing.  Nothing changed.")
            return 1

    flat = legs1_flat_leftovers(runs)
    if flat:
        print("  %d file(s) here are still in the build-22 flat layout (%s%s)."
              % (len(flat), flat[0], ", ..." if len(flat) > 1 else ""))
        print("  Move those first:  python tools/migrate_runs.py --apply --runs \"%s\"" % runs)
        if a.apply:
            print("  Refusing.  Nothing changed.")
            return 1

    maps = [e for e in sorted(os.listdir(runs)) if os.path.isdir(os.path.join(runs, e))]
    plans = [legs1_map(runs, m, marked) for m in maps]
    legs1_print(plans)

    work = [mp for mp in plans if mp["renames"] or mp["pb"] is not None]
    n_ren = sum(len(mp["renames"]) for mp in plans)
    n_pb = sum(1 for mp in plans if mp["pb"] is not None)
    n_keys = sum(len(mp["changes"]) - 1 for mp in plans if mp["pb"] is not None)
    n_skip = sum(1 for mp in plans if mp["skipped"])
    n_ref = sum(1 for mp in plans if mp["refused"])
    n_check = sum(len(mp["check"]) for mp in plans)
    n_left = sum(len(mp["left"]) for mp in plans)

    print()
    print("%d folder rename(s) and %d best.pb rewrite(s) (%d stage key(s) shifted) in %d of %d map(s)."
          % (n_ren, n_pb, n_keys, len(work), len(plans)))
    print("%d map(s) skipped as already on legs, %d refused, %d check finding(s), %d folder(s) left alone."
          % (n_skip, n_ref, n_check, n_left))

    if not a.apply:
        if n_ref:
            print("--apply will refuse until the refused map(s) are sorted out.")
        elif not work:
            print("Nothing left to do.")
        else:
            print("Dry run -- nothing changed.  --apply copies the tree to %s first." % backup)
        return 0

    if n_ref:
        print("Refusing: %d map(s) above cannot be renumbered from what is on disk.  Nothing changed."
              % n_ref)
        return 1

    stamp = time.strftime("%Y-%m-%d %H:%M")
    if not work:
        # Nothing on disk is numbered by segment, so there is nothing to protect
        # with a copy -- but the marker still matters: a stage folder build 57
        # later writes with no .rec in it carries no evidence, and without the
        # marker a future --apply would take it for an old one and shift it.
        with open(marker, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("FTESURF-LEGS 1\n# tools/migrate_runs.py legs1 --apply, %s\n"
                     "# nothing needed renumbering; no backup was made\n"
                     "renamed 0\nrewritten 0\nshifted 0\n" % stamp)
        print("Nothing to rename or rewrite.  Wrote %s so this tree is not renumbered later." % marker)
        return 0

    if os.path.exists(backup):
        print("Refusing: the backup directory %s already exists.  An old backup is either" % backup)
        print("a previous run's -- in which case this tree may already be migrated -- or")
        print("something else; either way it is not overwritten.  Nothing changed.")
        return 1
    try:
        inside = os.path.commonpath([runs, backup]) == runs
    except ValueError:
        inside = False                      # different drives
    if inside:
        print("Refusing: the backup directory %s is inside the tree it would copy." % backup)
        return 1

    print()
    print("backing up to %s" % backup)
    try:
        shutil.copytree(runs, backup)
    except (OSError, shutil.Error) as e:
        print("  backup FAILED: %s" % e)
        print("  Nothing in %s was changed.  Delete the incomplete %s and run again." % (runs, backup))
        return 1
    want, got = tree_census(runs), tree_census(backup)
    if want != got:
        print("  the backup does not match the tree (%d file(s) vs %d).  Nothing in %s was changed."
              % (len(want), len(got), runs))
        return 1
    print("  %d file(s), %d byte(s), verified against the tree" % (len(want), sum(want.values())))

    with open(partial, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-LEGS 1\n# tools/migrate_runs.py legs1 --apply, started %s\nbackup %s\n"
                 % (stamp, backup))

    done_ren = done_pb = 0
    for mp in work:
        mdir = os.path.join(runs, mp["map"])
        try:
            for src, dst in mp["renames"]:
                s, d = os.path.join(mdir, src), os.path.join(mdir, dst)
                # os.rename onto an existing EMPTY folder succeeds silently on
                # POSIX; the plan already walked this, so a hit means something
                # wrote here since.
                if os.path.lexists(d):
                    raise OSError("%s appeared after the plan was made" % d)
                os.rename(s, d)
                done_ren += 1
            if mp["pb"] is not None:
                pbpath = os.path.join(mdir, "best.pb")
                with open(pbpath, "rb") as fh:
                    if fh.read() != mp["pb_src"]:
                        raise OSError("%s changed after the plan was made -- is the game running?"
                                      % pbpath)
                # Written beside it and swapped in, so a best.pb is always one
                # whole file or the other, never a truncated one.
                tmp = pbpath + ".legs1-new"
                with open(tmp, "wb") as fh:
                    fh.write(mp["pb"])
                os.replace(tmp, pbpath)
                done_pb += 1
        except OSError as e:
            print()
            print("STOPPED at %s: %s" % (mp["map"], e))
            print("%s is part-migrated (%d rename(s) and %d rewrite(s) done) and %s marks it,"
                  % (runs, done_ren, done_pb, LEGS1_PARTIAL))
            print("so this tool will not start on it again.  Close whatever holds the files, then")
            print("put the backup back and run legs1 --apply again:")
            print("    delete  %s" % runs)
            print("    rename  %s  ->  %s" % (backup, os.path.basename(runs)))
            return 1
        print("  %-30s %d folder(s) renamed%s" % (mp["map"], len(mp["renames"]),
                                                 ", best.pb rewritten" if mp["pb"] is not None else ""))

    with open(marker, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-LEGS 1\n"
                 "# tools/migrate_runs.py legs1 --apply, %s\n"
                 "# stage_N -> stage_N+1 and best.pb FTESURF-PB 1 -> 2: build 57 names stages by leg\n"
                 "backup %s\nrenamed %d\nrewritten %d\nshifted %d\n"
                 % (stamp, backup, done_ren, done_pb, n_keys))
    os.remove(partial)

    print()
    print("renamed %d folder(s) and rewrote %d best.pb file(s) (%d stage key(s) shifted)."
          % (done_ren, done_pb, n_keys))
    print("backup: %s" % backup)
    print("marker: %s" % marker)
    return 0


def main(argv):
    # A path or a best.pb byte this console cannot encode must not end a run
    # half way through its report.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")

    if argv and argv[0] == "legs1":
        return legs1_main(argv[1:])

    apply_it = "--apply" in argv
    runs = None
    if "--runs" in argv:
        runs = argv[argv.index("--runs") + 1]
    if runs is None:
        here = os.path.dirname(os.path.abspath(__file__))
        runs = os.path.join(os.path.dirname(here), "ftesurf", "data", "runs")

    print("runs directory: %s" % runs)
    if not os.path.isdir(runs):
        print("  does not exist -- nothing to migrate")
        return 0

    moves, skips = plan(runs)

    if not moves and not skips:
        print("  nothing in the old layout; already migrated or empty")
        return 0

    if moves and os.path.exists(os.path.join(runs, LEGS1_MARKER)):
        # This job files `_s3` under stage_3, which in a tree legs1 has renumbered
        # is the folder for the stage after it.  See the docstring.
        print("  %s is there: legs1 has renumbered this tree for build 57, and this" % LEGS1_MARKER)
        print("  job writes build 23's segment-numbered folders.  Mixing the two would")
        print("  file stages one number apart.  Nothing moved.")
        return 1

    for src, dst in moves:
        print("  %-46s -> %s" % (os.path.basename(src),
                                 os.path.relpath(dst, runs).replace("\\", "/")))
    for src, why in skips:
        print("  LEFT  %-42s   %s" % (os.path.basename(src), why))

    if not apply_it:
        print()
        print("%d file(s) would move, %d left alone.  Re-run with --apply."
              % (len(moves), len(skips)))
        if moves:
            print("Build 57 then needs:  python tools/migrate_runs.py legs1 \"%s\"" % runs)
        return 0

    done = 0
    for src, dst in moves:
        if os.path.exists(dst):
            # Never overwrite.  A collision means this has been run before, or
            # the game has already written the new name -- either way the file
            # on the destination side is the newer truth.
            print("  EXISTS, not overwriting: %s" % dst)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        done += 1

    print()
    print("moved %d file(s); %d left alone." % (done, len(skips)))
    if done:
        print("Build 57 then needs:  python tools/migrate_runs.py legs1 \"%s\" --apply" % runs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
