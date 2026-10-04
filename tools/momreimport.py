#!/usr/bin/env python3
"""Rewrite the imported Momentum runs from their own demos (ROADMAP 3).

  python tools/momreimport.py --root <gamedir>/data/momentum \
         --demos <momentum/momtv> --demos <wrlines_data/demos> --out <dir> [--go]
         [--map M] [--limit N]

momimport.py wrote these runs from `.wrpath` files: positions only, a velocity
differenced from them, angles from the direction of travel, and zero keys,
flags and moves.  The demos they came from hold all of it per tick, and
tools/momreplay.py decodes it.  This reads <root>/manifest.tsv, finds each
row's .mtv by the 39-character key momimport matched the same way (the demo's
file stem), and writes the SAME leaf under --out with the demo's own columns.
Every file it does not rewrite is copied unchanged, so --out is a whole tree.

WHAT EACH COLUMN NOW SAYS, and where it comes from:
  t          (tick - the timer's start event) * the demo's tick interval; the
             pre-roll before the start is the negative padding, as ours is.
             No sample past the run's own last tick (start + ticks): most stage
             demos stop one tick after their timer froze.
  origin, velocity, eye angles   m_vecOrigin, m_vecVelocity, m_angEyeAngles,
             the tick's own values (velocity is post-move, as SV_RecLine's).
  fl         1 m_fFlags FL_ONGROUND, 2 FL_DUCKING, 4 IN_JUMP held, 8 IN_ATTACK
             -- SV_RecFlags' bits.  Never 16: a .mtv records no ramp contact,
             and the plane stays 0 0 0 (BACKLOG: inferring it).
  fwd side up  the move the physics used, from the recorded wishVel on the eye
             yaw (`moves wishvel`): below the 260 speed cap it is the move as
             the game applied it (a half press reads 225, a ducked one about a
             third), and at the cap its direction is exact, scaled so the
             larger component is 450 (cl_forwardspeed / cl_sidespeed,
             default.cfg).  Readers use its sign and direction only.  The
             33-prop format records no wishVel; there the physical buttons
             give it (`moves keys`), the later press of an opposing pair
             winning, as Momentum's does.  The buttons also stand in for a
             non-zero wish that did not update while the yaw turned, and on a
             teleport tick; a zero wish always stays zero.
  keys       FSI_* from those moves' signs plus jump, duck and attack -- the
             same rule as SV_RecKeys, so reccheck's mask check holds -- and
             +left/+right as FSI_TLEFT/TRIGHT, which a .mtv does record.

THE HEADER is the old file's, line for line, except: `startseg` is leg - 1 on
a stage run (FTESurf's numbering; momimport wrote leg), `clock counted` (t is
the mover's own tick count now), `momquality` is the decoded peak over the
demo's own maxHorizontalSpeed with the extractor's low-confidence bit cleared,
and two keys go in before `flags`: `moves <wishvel|keys> 450` and `momdemo
<sha1 of the .mtv>`.  `end` keeps the manifest's ticks -- the leaf is named
after them -- and a demo whose own run time disagrees is refused.

A ROW KEEPS ITS OLD BODY, and is counted by reason, when its demo is missing or
ambiguous, fails to decode, or disagrees with the row on map, track, leg or
ticks, or has other than one timer start and one stop.  Its startseg is still
corrected, so a stage folder holds one numbering.
"""
import argparse
import bisect
import collections
import hashlib
import math
import multiprocessing
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import momimport  # noqa: E402
import momreplay  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Source's button bits (in_buttons.h) and m_fFlags bits.
IN_ATTACK, IN_JUMP, IN_DUCK, IN_FORWARD, IN_BACK = 1, 2, 4, 8, 16
IN_LEFT, IN_RIGHT, IN_MOVELEFT, IN_MOVERIGHT = 128, 256, 512, 1024
FL_ONGROUND, FL_DUCKING = 1, 2
# sh_defs.qc's FSI_* (reccheck.py:439-440 has the same numbers).
FSI_FWD, FSI_BACK, FSI_LEFT, FSI_RIGHT = 1, 2, 4, 8
FSI_JUMP, FSI_DUCK, FSI_TLEFT, FSI_TRIGHT, FSI_ATTACK = 16, 32, 64, 128, 256
MOVE = 450          # cl_forwardspeed / cl_sidespeed, ftesurf/cfg/default.cfg
EV_START, EV_STOP = 0, 1

COLS = ("map", "track", "leg", "ticks", "seconds", "samples", "ratio", "oracle",
        "lowconf", "steamid64", "player", "sha", "leaf")


def read_manifest(path):
    head, rows = [], []
    for s in open(path, encoding="utf-8"):
        s = s.rstrip("\n")
        if s.startswith("#"):
            head.append(s)
            continue
        f = s.split("\t")
        if len(f) == len(COLS):
            rows.append(dict(zip(COLS, f)))
    return head, rows


def find_demo(row, keys, stems, cache):
    """The .mtv for one row: the stems its key prefixes, narrowed by the header's
    run time, track and map when there is more than one.  (path, why-not)."""
    k = row["sha"]
    i = bisect.bisect_left(keys, k)
    cands = []
    while i < len(keys) and keys[i].startswith(k):
        cands.append(stems[keys[i]])
        i += 1
    if not cands:
        return None, "no demo"
    if len(cands) == 1:
        return cands[0], None
    want_t = int(row["ticks"])
    track, leg = int(row["track"]), int(row["leg"])
    fit = []
    for p in cands:
        h = cache.get(p)
        if h is None:
            try:
                h = cache[p] = momreplay.read_header(open(p, "rb").read(0x200))
            except Exception:
                continue
        ti = h["tick_interval"]
        if not 0.001 <= ti <= 0.1:
            continue
        try:                            # a NaN or infinite run time is no fit
            ok = (h["map"].lower() == row["map"].lower()
                  and momimport.track_leg(h["track_type"], h["track_number"]) == (track, leg)
                  and int(round(h["run_time"] / ti)) == want_t)
        except (ValueError, OverflowError):
            ok = False
        if ok:
            fit.append(p)
    # Two copies of one file (the corpus has 135) are one demo.
    if len({hashlib.sha1(open(p, "rb").read()).hexdigest() for p in fit}) == 1:
        return fit[0], None
    return None, "ambiguous demo (%d candidates, %d fit)" % (len(cands), len(fit))


def old_header(path):
    lines = []
    with open(path, encoding="utf-8") as fh:
        for s in fh:
            s = s.rstrip("\n")
            lines.append(s)
            if s == "begin":
                return lines
    raise ValueError("no begin line")


CAP = 259.5         # |wishVel| at or past this is the 260 speed cap, not the usercmd
SNAP = 256          # units between ticks that only a teleport covers (the readers' rule)


def wish_moves(s):
    """(fwd, side) from the recorded wishVel on the eye yaw, or None without one.
    Source's right vector at yaw y is (sin y, -cos y)."""
    if s.wish_x is None or s.wish_y is None:
        return None
    y = math.radians(s.yaw)
    fm = s.wish_x * math.cos(y) + s.wish_y * math.sin(y)
    sm = s.wish_x * math.sin(y) - s.wish_y * math.cos(y)
    mag = math.hypot(fm, sm)
    # The yaw is stored in 0.176-degree steps, so a pure strafe leaves a sliver on
    # the other axis (fwd -1 lit BACK on surf_4am b4); a key is never under 3%.
    dead = max(1.0, 0.03 * mag)
    fm = 0.0 if abs(fm) < dead else fm
    sm = 0.0 if abs(sm) < dead else sm
    if mag >= CAP:
        big = max(abs(fm), abs(sm))
        fm, sm = fm * MOVE / big, sm * MOVE / big
    return int(round(fm)), int(round(sm))


class KeyMoves:
    """(fwd, side) from the physical buttons, for the format with no wishVel: the
    later press of an opposing pair wins (measured: Momentum's choice on 7539 of
    7572 A+D overlaps)."""

    def __init__(self):
        self.down, self.n = {}, 0       # bit -> the press's order

    def __call__(self, b):
        for bit in (IN_FORWARD, IN_BACK, IN_MOVELEFT, IN_MOVERIGHT):
            if not b & bit:
                self.down.pop(bit, None)
            elif bit not in self.down:
                self.n += 1
                self.down[bit] = self.n

        def axis(pos, neg):
            p, n = self.down.get(pos), self.down.get(neg)
            if p and n:
                return MOVE if p > n else -MOVE
            return MOVE if p else (-MOVE if n else 0)
        return axis(IN_FORWARD, IN_BACK), axis(IN_MOVERIGHT, IN_MOVELEFT)


def sample(s, start, ti, moves):
    b, f = s.buttons or 0, s.flags or 0
    fl = 0
    if f & FL_ONGROUND:
        fl += 1
    if f & FL_DUCKING:
        fl += 2
    if b & IN_JUMP:
        fl += 4
    if b & IN_ATTACK:
        fl += 8
    fwd, side = moves
    keys = 0
    if fwd > 0:
        keys += FSI_FWD
    if fwd < 0:
        keys += FSI_BACK
    if side < 0:
        keys += FSI_LEFT
    if side > 0:
        keys += FSI_RIGHT
    if b & IN_JUMP:
        keys += FSI_JUMP
    if b & IN_DUCK:
        keys += FSI_DUCK
    if b & IN_LEFT:
        keys += FSI_TLEFT
    if b & IN_RIGHT:
        keys += FSI_TRIGHT
    if b & IN_ATTACK:
        keys += FSI_ATTACK
    # The column formats momimport and SV_RecLine use; never an exponent.
    return ("%.4f %.2f %.2f %.2f %.2f %.2f %.2f %.1f %.1f %d %d %d %d 0 0.0000 0.0000 0.0000"
            % ((s.tick - start) * ti, s.x, s.y, s.z, s.vx, s.vy, s.vz, s.pitch, s.yaw,
               fl, keys, fwd, side))


def convert(row, demo, oldpath):
    """(text, info) for one row, or raise ValueError with the reason."""
    r = momreplay.parse(demo)
    h, ticks, ti = r["header"], r["ticks"], r["tick_interval"]
    if not 0.001 <= ti <= 0.1:
        raise ValueError("tick interval %r" % ti)
    if h["map"].lower() != row["map"].lower():
        raise ValueError("map %s" % h["map"])
    track, leg = int(row["track"]), int(row["leg"])
    if momimport.track_leg(h["track_type"], h["track_number"]) != (track, leg):
        raise ValueError("track %d/%d" % (h["track_type"], h["track_number"]))
    want = int(row["ticks"])
    if int(round(h["run_time"] / ti)) != want:
        raise ValueError("ticks %d, the row says %d" % (int(round(h["run_time"] / ti)), want))
    starts = [e[0] for e in r["events"] if e[1] == EV_START]
    stops = [e[0] for e in r["events"] if e[1] == EV_STOP]
    if len(starts) != 1 or len(stops) != 1:
        raise ValueError("%d timer starts, %d stops" % (len(starts), len(stops)))
    start = starts[0]
    if not ticks or abs((stops[0] - start) - want) > 1:
        raise ValueError("stop - start %d, the row says %d" % (stops[0] - start, want))

    oracle = (r["stats"].get("trackStats") or {}).get("maxHorizontalSpeed")
    oracle = oracle if isinstance(oracle, (int, float)) and oracle > 0 else 0.0
    # The JSON's figure is the run's, so the pre-roll is not in the peak.
    peak = max([(s.vx * s.vx + s.vy * s.vy) ** 0.5 for s in ticks
                if start <= s.tick <= stops[0]] or [0.0])
    ratio = (peak / oracle) if oracle else 0.0
    sha = hashlib.sha1(open(demo, "rb").read()).hexdigest()

    # The 33-prop format records no wishVel on any tick; the others on every one.
    haswish = all(s.wish_x is not None for s in ticks)
    # Exactly the header's %.6g rate: the float32 interval (0.0099999998) put t
    # 0.0001 low past tick ~149k.
    tdt = float("%.6g" % ti)
    keymoves = KeyMoves()
    body = []
    pad = keyed = 0
    prev = None
    for s in ticks:
        if s.tick - start > want:
            break                       # the demo's stop can trail the frozen timer
        if s.tick < start:
            pad += 1
        km = keymoves(s.buttons or 0)
        # A NON-ZERO wish is not this tick's move in two cases, and the buttons
        # are: it stopped updating while the yaw turned (ladders, water -- 193
        # ticks on surf_water-run), and on a teleport tick it was built on the
        # yaw before.  A zero wish is the truth either way -- the game applied no
        # move (an A+D overlap it zeroes, a key it held back) -- and equals the
        # last zero whatever the yaw, so it is never re-derived: round 3 found
        # that wrote 4,273 keys the demo's own velocity contradicts.
        use_keys = not haswish
        if haswish and prev is not None and (s.wish_x or s.wish_y):
            stale = (s.wish_x, s.wish_y) == (prev.wish_x, prev.wish_y) and s.yaw != prev.yaw
            snap = math.dist((s.x, s.y, s.z), (prev.x, prev.y, prev.z)) > SNAP
            use_keys = stale or snap
            keyed += use_keys
        body.append(sample(s, start, tdt, km if use_keys else wish_moves(s)))
        prev = s

    out = []
    for s in fixed_header(old_header(oldpath), leg):
        k = s.split(" ", 1)[0]
        if k == "momquality":
            s = "momquality %.4f %.1f 0" % (ratio, oracle)
        elif k == "clock":
            s = "clock counted"
        elif k == "flags":
            out.append("moves %s %d" % ("wishvel" if haswish else "keys", MOVE))
            out.append("momdemo %s" % sha)
        elif k in ("moves", "momdemo"):
            continue
        out.append(s)
    out += body
    out.append("end %d %d %d 0" % (want, len(body), pad))
    return "\n".join(out) + "\n", {"samples": len(body), "ratio": ratio, "oracle": oracle,
                                   "padding": pad, "sha": sha, "wish": haswish, "keyed": keyed}


def fixed_header(lines, leg):
    """FTESurf's stage numbering, for every row whether or not its body changes."""
    return ["startseg %d" % (leg - 1 if leg > 0 else 0) if s.split(" ", 1)[0] == "startseg"
            else s for s in lines]


def work(job):
    """One row in a worker: convert, write when asked, return a summary only --
    the text of a 380k-tick run is 34 MB, and 5000 of them do not fit in one
    process."""
    rel, demo, row, oldpath, dst = job
    try:
        text, info = convert(row, demo, oldpath)
    except Exception as e:          # one bad demo must not stop the set
        if isinstance(e, ValueError):
            return rel, None, str(e).split(",")[0].split(" ")[0], str(e)
        return rel, None, type(e).__name__, str(e)
    if dst:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return rel, info, None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="data/momentum, with manifest.tsv")
    ap.add_argument("--demos", action="append", required=True, help=".mtv root (repeatable)")
    ap.add_argument("--out", required=True, help="a new tree; must not exist (or be empty)")
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--go", action="store_true", help="write --out")
    a = ap.parse_args()

    if os.path.abspath(a.out) == os.path.abspath(a.root):
        sys.exit("--out must be a new tree, not --root")
    if a.go and os.path.exists(a.out) and os.listdir(a.out):
        sys.exit("--out %s is not empty" % a.out)
    head, rows = read_manifest(os.path.join(a.root, "manifest.tsv"))
    stems = momimport.index_demos(a.demos)
    keys = sorted(stems)
    want_maps = {m.lower() for m in a.map}
    print("manifest %d rows, %d demos indexed" % (len(rows), len(stems)))

    refused = collections.Counter()
    examples = {}
    done = {}
    cache = {}
    jobs = []
    for row in rows:
        if want_maps and row["map"].lower() not in want_maps:
            continue
        if a.limit and len(jobs) + sum(refused.values()) >= a.limit:
            break
        rel = os.path.join(row["map"], momimport.leg_dir(int(row["track"]), int(row["leg"])),
                           row["leaf"])
        demo, why = find_demo(row, keys, stems, cache)
        if demo is None:
            refused[why.split(" (")[0]] += 1
            examples.setdefault(why.split(" (")[0], (rel, why))
            continue
        jobs.append((rel, demo, row, os.path.join(a.root, rel),
                     os.path.join(a.out, rel) if a.go else None))
    n = len(jobs) + sum(refused.values())

    with multiprocessing.Pool(max(1, a.jobs)) as pool:
        for rel, info, reason, detail in pool.imap_unordered(work, jobs, chunksize=4):
            if info is None:
                refused[reason] += 1
                examples.setdefault(reason, (rel, detail))
            else:
                done[rel] = info

    print("rewritten %d of %d rows considered" % (len(done), n))
    for why, c in refused.most_common():
        print("  left as it was: %-28s %5d   e.g. %s -- %s" % (why, c, examples[why][0], examples[why][1]))
    if done:
        dq = sorted(i["ratio"] for i in done.values() if i["ratio"])
        if dq:
            print("  decoded peak / maxHorizontalSpeed: min %.4f median %.4f max %.4f"
                  % (dq[0], dq[len(dq) // 2], dq[-1]))
    if not a.go:
        print("dry run: nothing written (--go writes %s)" % a.out)
        return 0

    # The rest of the tree; the workers wrote the rewritten leaves.  A manifest
    # row's file keeps its body and takes the startseg fix; anything else is copied.
    legs = {os.path.join(r["map"], momimport.leg_dir(int(r["track"]), int(r["leg"])), r["leaf"]):
            int(r["leg"]) for r in rows}
    copied = renum = 0
    for dp, _, fns in os.walk(a.root):
        for f in fns:
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, a.root)
            if rel == "manifest.tsv" or rel in done:
                continue
            dst = os.path.join(a.out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if rel in legs:
                with open(src, encoding="utf-8", newline="") as fh:
                    text = fh.read()
                fhead, sep, rest = text.partition("\nbegin\n")     # not `head`: the manifest's
                new = "\n".join(fixed_header(fhead.split("\n"), legs[rel])) + sep + rest
                with open(dst, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
                renum += new != text
            else:
                shutil.copy2(src, dst)
            copied += 1
    with open(os.path.join(a.out, "manifest.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        for s in head:
            fh.write(s + "\n")
        for row in rows:
            rel = os.path.join(row["map"], momimport.leg_dir(int(row["track"]), int(row["leg"])),
                               row["leaf"])
            if rel in done:
                info = done[rel]
                row = dict(row, samples=str(info["samples"]), ratio="%.4f" % info["ratio"],
                           oracle="%.1f" % info["oracle"], lowconf="0")
            fh.write("\t".join(row[c] for c in COLS) + "\n")
    print("wrote %s: %d rewritten, %d kept (%d of them renumbered), manifest.tsv"
          % (a.out, len(done), copied, renum))
    print("moves from wishVel in %d, from the keys in %d; %d wish ticks keyed (stale or teleport)"
          % (sum(1 for i in done.values() if i["wish"]), sum(1 for i in done.values() if not i["wish"]),
             sum(i["keyed"] for i in done.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
