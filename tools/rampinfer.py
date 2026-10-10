#!/usr/bin/env python3
"""rampinfer.py -- ramp contact inferred from a recording's own samples.

An imported Momentum run carries no ramp contact: a .mtv records none, so flags
bit 16 is never set and the plane is 0 0 0 (tools/momreimport.py).  The viewer
infers it (src/client/cl_infer.qc) and says that it did.  This is the same rule,
written from the measurement and not from the QC, for four jobs:

  python tools/rampinfer.py FILE.rec ...            what the viewer must conclude
  python tools/rampinfer.py --score DIR|FILE ...    the rule against native bit 16
  python tools/rampinfer.py --twin IMPORT NATIVE    an import against a native
                                                    recording of the same run
  python tools/rampinfer.py --shape DIR             what it says over a tree of imports

THE RULE.  Free flight changes vertical velocity by one exact step a tick, the
same on every tick of a file (gravity in two half steps; air strafing is
horizontal).  A ramp pushes up.  So, between two consecutive samples one mover
tick apart, neither on ground, not a teleport:

    r = (vz1 - vz0) + step
    contact = r > EPS  and not  (r > FLAT * step and sideways change < FLATH)

`step` is read off the file: the commonest fall between such pairs, to 0.01.
It is NOT assumed to be 800 * tick -- one imported map runs 750.

The second half leaves out a hard push with no sideways change at all: a floor
touched for a tick with no ground flag, or a straight shove.  A face in the
recorder's ramp band (|nz| <= 0.7) turns at least as much velocity sideways as
it turns up.  It is deliberately no stricter than "none at all": requiring the
ramp's own ratio (1.02 * r less the 30 u/s air strafing can add) refused the
first tick of 10 rides in 33 on the demo below, where the body lands in the
crease between two facets of a curved ramp and their sideways pushes cancel.

UNAVAILABLE is a third answer, not "no contact", and it has four causes:
  - over SCANMAX samples.  That one is the viewer's and not the rule's: a replay
    opens in a single QC call with a fixed budget, which the longest import
    (238,434 samples) spent 95% of with the inference in it and 76% without;
  - an import whose header has no `momdemo`.  Its velocity was differenced from
    positions and it has NO ground flag (21 of 5,281, tools/momimport.py's
    body), so standing on a floor would read as a ramp.  Its fall step is sharp
    enough to pass the next test (shares 0.27 to 0.50), which is why this is
    read from the header and not from the data;
  - under MINAIR judgeable pairs;
  - no fall common enough (MINSHARE of them).

A tick whose vz did not move at all is NOT left out, though noclip, a ladder
and a hover produce it: so does a body wedged still on a ramp (vz stays at half
a step), which is how a surf run waits at its start, and native recordings set
the bit there (2,770 such ticks against bit 16 in the owner's runs).

WHAT IT CANNOT SEE, and --shape counts by their own numbers: a lift, a booster,
a gravity zone, a ladder and noclip also move vz against the step, and so does
a face flatter than the ramp band that the body slides on without grounding; a
face that points DOWN pushes down and is not looked for (looking for it found
every missed ride on the demo below, and as many pushes that are no ramp); the
plane is not inferred at all.

AGAINST TRUTH: see the numbers `--score` and `--twin` print; the ones measured
on 2026-10-10 are in ENGINE_PATCHES.md beside this rule's patch.  --twin is the
only check on a real demo: cfg/test/p492voy.rec is the owner's surf_voyager
Momentum run flown again by this engine from the demo's inputs (bodies a
median 0.3 u apart over the timed run, velocities 0.02 u/s), so its bit 16 is
the contact the import lacks.  The approach before the clock is each file's
own and is left out.

--score compares with flags bit 16 on native recordings, tick by tick and ride
by ride (contact joined across gaps of RAMP_GAP, the label's unit), one file a
run.  A native file older than format 5 samples by frame with a jittery clock:
--score drops its repeated samples and counts the rest as one tick each, and
says so.  An extra ride is counted apart when its file is a cheat or practice
run or a save (noclip lives there).  Counts only: no sample, name or path above
the last three parts is printed.
"""
import argparse
import bisect
import collections
import math
import pathlib
import struct
import sys

EPS = 0.045          # between the 0.04 and 0.05 a %.2f column can produce
FLAT = 2.5           # steps: a wedged body's push is one
FLATH = 0.5          # u/s of sideways change
MINAIR = 30
MINSHARE = 0.10      # 5,258 imports: the lowest is 0.279
HMAX = 4000          # falls up to 40.00 a tick
SCANMAX = 200000     # samples.  Not the rule's: the viewer's limit (cl_infer.qc INF_SCANMAX)
RAMP_GAP = 0.08      # cl_board.qc Board_RampHeld
F_ONGROUND, F_RAMP = 1, 16
TF_PRACTICE, TF_CHEAT = 1, 256
REWIND = ("warp", "portal", "restart", "resume", "retry")

AVAILABLE, UNAVAILABLE = "inferred", "unavailable"


def f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def read(path):
    """(header keys, samples).  A sample: (t, origin, velocity, flags, plane z,
    a rewinding record sat before it)."""
    keys, rows, body, rew = {}, [], False, False
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        keys["version"] = fh.readline().strip()
        for line in fh:
            if not body:
                s = line.strip()
                if s == "begin":
                    body = True
                else:
                    p = s.split(None, 1)
                    if p:
                        keys[p[0]] = p[1] if len(p) > 1 else ""
                continue
            c = line[:1]
            if c.isdigit() or c == "-":
                f = line.split()
                if len(f) < 10:
                    continue
                try:
                    rows.append((f32(float(f[0])),
                                 tuple(f32(float(x)) for x in f[1:4]),
                                 tuple(f32(float(x)) for x in f[4:7]),
                                 int(float(f[9])),
                                 float(f[16]) if len(f) >= 17 else 0.0, rew))
                except ValueError:
                    continue
                rew = False
            elif c.isalpha() and line.split(None, 1)[0] in REWIND:
                rew = True
    return keys, rows


def tick_of(keys):
    for k in ("movetickrate", "tickrate"):
        try:
            v = float(keys.get(k, "0").split()[0])
        except (ValueError, IndexError):
            v = 0.0
        if v > 0:
            return v
    return 0.0


def snap(o0, v0, o1, v1, dt):
    """sh_interp.qc Interp_Fit's INTERP_SNAP."""
    d = [o1[i] - o0[i] - (v0[i] + v1[i]) * (0.5 * dt) for i in range(3)]
    return math.sqrt(sum(x * x for x in d)) > \
        0.5 * (math.sqrt(sum(x * x for x in v0)) + math.sqrt(sum(x * x for x in v1))) * dt + 64


def judgeable(a, b, tick):
    """One mover tick apart, neither on ground, not a teleport."""
    dt = b[0] - a[0]
    if not (dt > tick * 0.5 and dt < tick * 1.5):
        return False
    if (a[3] | b[3]) & F_ONGROUND:
        return False
    return not snap(a[1], a[2], b[1], b[2], dt)


def infer(rows, tick):
    """(bits, step, airborne pairs, share).  step 0: unavailable, bits all False."""
    n = len(rows)
    bits = [False] * n
    if tick <= 0 or n < 2:
        return bits, 0.0, 0, 0.0
    ok = [False] * n
    hist = collections.Counter()
    nair = 0
    for i in range(1, n):
        if judgeable(rows[i - 1], rows[i], tick):
            ok[i] = True
            nair += 1
            j = int(math.floor((rows[i - 1][2][2] - rows[i][2][2]) * 100 + 0.5))
            if 1 <= j <= HMAX:
                hist[j] += 1
    if not hist:
        return bits, 0.0, nair, 0.0
    top = max(hist.values())
    mode = min(j for j, c in hist.items() if c == top)      # the lowest wins a tie
    share = top / nair
    if nair < MINAIR or share < MINSHARE:
        return bits, 0.0, nair, share
    step = mode / 100.0
    for i in range(1, n):
        if ok[i]:
            a, b = rows[i - 1][2], rows[i][2]
            r = b[2] - a[2] + step
            bits[i] = r > EPS and not (r > FLAT * step and
                                       math.hypot(b[0] - a[0], b[1] - a[1]) < FLATH)
    return bits, step, nair, share


def verdict(keys, rows):
    """What the viewer concludes for a file: (bits, step, airborne pairs, share,
    why).  why "" is inferred; anything else is the reason it is unavailable,
    or "measured" for a native file, whose bits are its own."""
    if "foreign" not in keys:
        return [bool(r[3] & F_RAMP) for r in rows], 0.0, 0, 0.0, "measured"
    if "momdemo" not in keys:
        return [False] * len(rows), 0.0, 0, 0.0, "no per-tick velocity"
    if len(rows) > SCANMAX:
        return [False] * len(rows), 0.0, 0, 0.0, "over %d samples" % SCANMAX
    bits, step, nair, share = infer(rows, tick_of(keys))
    if step:
        return bits, step, nair, share, ""
    return bits, step, nair, share, ("under %d airborne pairs" % MINAIR if nair < MINAIR
                                     else "no fall common enough")


def rides(bits, rows):
    """Runs of contact joined across gaps of up to RAMP_GAP: [(first, last)]."""
    out, first, last = [], None, None
    for i, on in enumerate(bits):
        if not on:
            continue
        if first is None:
            first = i
        elif f32(rows[i][0] - rows[last][0]) > f32(RAMP_GAP):
            out.append((first, last))
            first = i
        last = i
    if first is not None:
        out.append((first, last))
    return out


def match(t_r, g_r):
    """True rides against inferred ones, both [(first, last)] over one index:
    [(true ride, [inferred rides touching it])], and the inferred touching none."""
    ends = [e for _, e in g_r]
    used, out = set(), []
    for s, e in t_r:
        j = bisect.bisect_left(ends, s)
        hit = []
        while j < len(g_r) and g_r[j][0] <= e:
            hit.append(j)
            j += 1
        used.update(hit)
        out.append(((s, e), [g_r[k] for k in hit]))
    return out, [g for k, g in enumerate(g_r) if k not in used]


def reclock(rows, tick):
    """A frame-sampled native file as one sample a mover tick: repeats dropped
    (no tick ran), the rest counted.  (rows, repeats dropped)"""
    out = [rows[0]]
    for r in rows[1:]:
        if r[1] == out[-1][1] and r[2] == out[-1][2] and not r[5]:
            continue
        out.append(r)
    return [(f32(i * tick),) + r[1:] for i, r in enumerate(out)], len(rows) - len(out)


def tick_exact(rows, tick):
    good = sum(1 for a, b in zip(rows, rows[1:])
               if b[0] > a[0] and abs((b[0] - a[0]) / tick - round((b[0] - a[0]) / tick)) < 0.02)
    return good >= 0.99 * (len(rows) - 1)


def files_of(args):
    for a in args:
        p = pathlib.Path(a)
        if p.is_dir():
            yield from sorted(p.rglob("*.rec"))
        else:
            yield p


def tail(p):
    return "/".join(p.parts[-3:])


def cmd_files(paths):
    bad = 0
    for p in files_of(paths):
        keys, rows = read(p)
        if not rows:
            print("CANNOT CHECK %s: no samples" % tail(p))
            bad = 1
            continue
        bits, step, nair, share, why = verdict(keys, rows)
        print("%s: %s  step %.2f  share %.3f of %d airborne pairs  contact ticks %d  rides %d  samples %d"
              % (tail(p), why if why == "measured" else AVAILABLE if not why else
                 "%s (%s)" % (UNAVAILABLE, why), step, share, nair,
                 sum(bits), len(rides(bits, rows)), len(rows)))
    return bad


def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "   n/a"


def cmd_score(paths, show):
    """Against flags bit 16.  One file a run: the largest sharing a `runid`."""
    by_run = {}
    unreadable = 0
    for p in files_of(paths):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(4096)
        except OSError:
            unreadable += 1
            continue
        rid = [l.split(None, 1)[1].strip() for l in head.splitlines() if l.startswith("runid ")]
        key = rid[0] if rid else str(p)
        size = p.stat().st_size
        if key not in by_run or size > by_run[key][0]:
            by_run[key] = (size, p)
    groups, maps = collections.OrderedDict(), collections.defaultdict(set)
    skipped = collections.Counter()
    listed = []
    for size, p in sorted(by_run.values(), key=lambda x: -x[0]):
        keys, rows = read(p)
        tick = tick_of(keys)
        if "foreign" in keys:
            skipped["an import: no truth in it"] += 1
            continue
        if tick <= 0 or len(rows) < 50:
            skipped["no tick rate, or under 50 samples"] += 1
            continue
        name = "clock counts ticks"
        if not tick_exact(rows, tick):
            rows, _ = reclock(rows, tick)
            name = "frame-sampled, repeats dropped and counted"
        bits, step, nair, share = infer(rows, tick)
        if not step:
            skipped["unavailable (%s)" % ("under %d airborne pairs" % MINAIR if nair < MINAIR
                                           else "no fall common enough")] += 1
            continue
        try:
            flags = int(float(keys.get("flags", "0").split()[0]))
        except (ValueError, IndexError):
            flags = 0
        clean = not (flags & (TF_PRACTICE | TF_CHEAT)) and p.name != "cheat.rec" and "saves" not in p.parts
        g = groups.setdefault(name, collections.Counter())
        maps[name].add(keys.get("map", "?"))
        g["runs"] += 1
        truth = [False] * len(rows)
        for i in range(1, len(rows)):
            b = rows[i]
            if b[5]:
                bits[i] = False            # a rewind: the file says why vz moved
                continue
            truth[i] = bool(b[3] & F_RAMP) and not (b[3] & F_ONGROUND)
            g[("tick", truth[i], bits[i])] += 1
            if truth[i] and not bits[i]:
                g["missed ticks on a face pointing down" if b[4] < 0 else
                  "missed ticks, other"] += 1
        t_r = rides(truth, rows)
        pairs, extra = match(t_r, rides(bits, rows))
        g["true rides"] += len(t_r)
        g["true rides in clean runs"] += len(t_r) if clean else 0
        for (s, e), hit in pairs:
            if not hit:
                g["true rides missed"] += 1
                listed.append("missed  %s t %.3f ticks %d  [%s]" % (tail(p), rows[s][0], e - s + 1, name))
                continue
            g["first tick exact" if hit[0][0] == s else "first tick off"] += 1
            g["last tick exact" if hit[-1][1] == e else "last tick off"] += 1
            if hit[0][0] != s or hit[-1][1] != e:
                listed.append("edge    %s t %.3f first %+d last %+d ticks  [%s]"
                              % (tail(p), rows[s][0], hit[0][0] - s, hit[-1][1] - e, name))
        for s, e in extra:
            n = sum(1 for i in range(s, e + 1) if bits[i])
            g["extra rides"] += 1
            g["extra rides in clean runs" if clean else "extra rides in cheat, practice and save files"] += 1
            g["...of one tick" if n == 1 else "...of 2 to 6 ticks" if n <= 6 else "...longer"] += 1
            v = rows[s][2]
            listed.append("extra   %s t %.3f ticks %d speed %.0f vz %.0f  [%s%s]"
                          % (tail(p), rows[s][0], n, math.hypot(v[0], v[1]), v[2], name,
                             "" if clean else ", not a clean run"))
    if unreadable:
        skipped["could not be read"] = unreadable
    print("runs not scored: %s" % (dict(skipped) or "none"))
    for name, g in groups.items():
        tp, fn, fp = g[("tick", True, True)], g[("tick", True, False)], g[("tick", False, True)]
        print("== %s: %d runs on %d maps" % (name, g["runs"], len(maps[name])))
        print("   ticks: of %d true contact, found %d (%s); of %d inferred, true %d (%s)"
              % (tp + fn, tp, pct(tp, tp + fn).strip(), tp + fp, tp, pct(tp, tp + fp).strip()))
        print("          missed: %d on a face pointing down, %d other"
              % (g["missed ticks on a face pointing down"], g["missed ticks, other"]))
        print("   rides: %d true, %d missed; found ones: first tick exact %d, off %d; last exact %d, off %d"
              % (g["true rides"], g["true rides missed"], g["first tick exact"], g["first tick off"],
                 g["last tick exact"], g["last tick off"]))
        print("          %d extra (%d of one tick, %d of 2 to 6, %d longer): %d in clean runs holding %d"
              " true rides, %d in cheat, practice and save files"
              % (g["extra rides"], g["...of one tick"], g["...of 2 to 6 ticks"], g["...longer"],
                 g["extra rides in clean runs"], g["true rides in clean runs"],
                 g["extra rides in cheat, practice and save files"]))
    for line in listed[:show]:
        print("   " + line)
    return 0 if groups else 2


def cmd_twin(imp, nat, show):
    """An import's inferred contact against a native recording of the same run,
    sample by sample at equal clocks.  2: they are not the same run."""
    ki, a = read(pathlib.Path(imp))
    kn, b = read(pathlib.Path(nat))
    bits, step, nair, share, why = verdict(ki, a)
    if why:
        print("CANNOT CHECK: the import is %s" % why)
        return 2
    if "foreign" in kn or not b:
        print("CANNOT CHECK: the second file is not a native recording with samples")
        return 2
    tick = tick_of(ki)
    by_t = {round(r[0] / tick): r for r in b}
    truth = [False] * len(a)
    timed, shared, apart, dv = 0, 0, [], []
    for i, r in enumerate(a):
        if r[0] < 0:
            bits[i] = False                 # the approach before the clock is each file's own
            continue
        timed += 1
        o = by_t.get(round(r[0] / tick))
        if o is None:
            continue
        shared += 1
        apart.append(math.dist(r[1], o[1]))
        dv.append(math.dist(r[2], o[2]))
        truth[i] = bool(o[3] & F_RAMP) and not (o[3] & F_ONGROUND)
    if shared < 0.9 * timed or not apart or max(apart) > 64:
        print("CANNOT CHECK: not one run -- %d of %d timed samples share a clock, bodies up to %.0f u apart"
              % (shared, timed, max(apart) if apart else -1))
        return 2
    apart.sort()
    dv.sort()
    print("one run twice: %d of %d timed samples share a clock; bodies a median %.1f u apart (most %.1f),"
          " velocities a median %.2f u/s apart (most %.2f)"
          % (shared, timed, apart[len(apart) // 2], apart[-1], dv[len(dv) // 2], dv[-1]))
    tp = sum(1 for x, y in zip(truth, bits) if x and y)
    print("step %.2f; ticks: of %d true contact, found %d; of %d inferred, true %d"
          % (step, sum(truth), tp, sum(bits), tp))
    t_r = rides(truth, a)
    pairs, extra = match(t_r, rides(bits, a))
    found = [(t, hit) for t, hit in pairs if hit]
    print("rides: %d true, %d found (first tick exact %d, last exact %d), %d missed, %d extra"
          % (len(t_r), len(found), sum(1 for (s, e), hit in found if hit[0][0] == s),
             sum(1 for (s, e), hit in found if hit[-1][1] == e), len(t_r) - len(found), len(extra)))
    lines = ["missed  t %.3f ticks %d" % (a[s][0], e - s + 1) for (s, e), hit in pairs if not hit]
    lines += ["edge    t %.3f first %+d last %+d ticks" % (a[s][0], hit[0][0] - s, hit[-1][1] - e)
              for (s, e), hit in found if hit[0][0] != s or hit[-1][1] != e]
    lines += ["extra   t %.3f ticks %d" % (a[s][0], sum(bits[s:e + 1])) for s, e in extra]
    for line in lines[:show]:
        print("   " + line)
    return 0


def cmd_shape(paths):
    """No truth: what the rule says over a tree, by its own numbers."""
    tot = collections.Counter()
    shares, kinds, length = [], collections.Counter(), collections.Counter()
    for p in files_of(paths):
        keys, rows = read(p)
        bits, step, nair, share, why = verdict(keys, rows)
        tot["files"] += 1
        if why:
            tot["%s: %s" % (UNAVAILABLE if why != "measured" else "native", why)] += 1
            continue
        tot["inferred"] += 1
        tot["step is not 800 * tick"] += abs(step - 800 * tick_of(keys)) > 0.006
        shares.append(share)
        for s, e in rides(bits, rows):
            rs = [rows[i][2][2] - rows[i - 1][2][2] + step for i in range(s, e + 1) if bits[i]]
            hs = [math.hypot(rows[i][2][0] - rows[i - 1][2][0], rows[i][2][1] - rows[i - 1][2][1])
                  for i in range(s, e + 1) if bits[i]]
            dur = rows[e][0] - rows[s][0]
            length["one tick" if len(rs) == 1 else "under 0.1 s" if dur < 0.1 else
                   "0.1 to 0.5 s" if dur < 0.5 else "0.5 to 2 s" if dur < 2 else "2 s and over"] += 1
            kinds["a single tick" if len(rs) == 1 else
                  "straight up throughout (no sideways change)" if max(hs) < 0.02 else
                  "one constant push for 8 ticks or more" if len(rs) >= 8 and len(set(round(x, 2) for x in rs)) == 1
                  else "the rest"] += 1
    if not tot["files"]:
        print("CANNOT CHECK: no recordings under %s" % ", ".join(paths))
        return 2
    print("  ".join("%s %d" % kv for kv in sorted(tot.items())))
    if shares:
        shares.sort()
        print("share of airborne pairs falling by the step, a file: min %.3f  p5 %.3f  median %.3f"
              % (shares[0], shares[len(shares) // 20], shares[len(shares) // 2]))
    n = sum(length.values())
    print("rides %d: %s" % (n, ", ".join("%s %d" % kv for kv in length.most_common())))
    print("by their own numbers: %s" % ", ".join("%s %d (%s)" % (k, v, pct(v, n).strip())
                                                 for k, v in kinds.most_common()))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--twin", action="store_true")
    ap.add_argument("--shape", action="store_true")
    ap.add_argument("--list", type=int, default=0,
                    help="with --score or --twin: print this many missed, shifted and extra rides")
    a = ap.parse_args()
    if a.score:
        return cmd_score(a.paths, a.list)
    if a.twin:
        if len(a.paths) != 2:
            ap.error("--twin takes the import and its native recording")
        return cmd_twin(a.paths[0], a.paths[1], a.list)
    if a.shape:
        return cmd_shape(a.paths)
    return cmd_files(a.paths)


if __name__ == "__main__":
    sys.exit(main())
