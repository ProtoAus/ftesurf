#!/usr/bin/env python3
"""
migrate_runs.py -- move data/runs from the flat build-22 layout to build 23's.

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

Dry run by default.  Pass --apply to actually move anything.

Usage:
    python tools/migrate_runs.py [--apply] [--runs <dir>]
"""

import os
import re
import sys
import shutil

# <map>_t<track>_s<startseg>_<tag>.<ext>.  The map name may itself contain
# underscores and digits (surf_utopia_v2), so the leg part is anchored to the
# END of the stem and the map is whatever is left -- matching from the front
# would swallow the map at the first _t it met.
STEM = re.compile(r"^(?P<map>.+)_t(?P<track>\d+)_s(?P<seg>\d+)_(?P<tag>pb|last|shadow)$")

ARCHIVED = ("pb", "shadow")


def leg_dir(track, seg):
    """The mirror of FS_LegDir in src/shared/sh_defs.qc.  Keep them in step."""
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
        dstdir = os.path.join(runs, mapname, leg_dir(track, seg))

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


def main(argv):
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

    for src, dst in moves:
        print("  %-46s -> %s" % (os.path.basename(src),
                                 os.path.relpath(dst, runs).replace("\\", "/")))
    for src, why in skips:
        print("  LEFT  %-42s   %s" % (os.path.basename(src), why))

    if not apply_it:
        print()
        print("%d file(s) would move, %d left alone.  Re-run with --apply."
              % (len(moves), len(skips)))
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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
