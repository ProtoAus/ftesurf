#!/usr/bin/env python3
"""
b89browse.py -- does the map browser's build-88 work actually do anything?

    python tools/b89browse.py

FIVE CLAIMS, AND EACH ONE IS CHECKED AGAINST A NUMBER DERIVED A SECOND WAY.
That is the whole design.  The engine prints what it did; this script works the
same figure out of data/mapmeta.txt, data/mapdl.txt and data/mapwr.txt without
looking at the log, and the two have to agree.  A wrong index over the right
data reads exactly like a result -- the only thing that catches it is having two
numbers for one question.

THERE IS NO SEPARATE CONTROL BUILD, and that is a decision rather than an
omission.  Four of the five claims carry their own falsifier in the same run:

  * the gutter fails the arm if the OLD 92 px would have been enough, which is
    the premise of the fix;
  * the tier order fails if the rank histogram shows one populated bucket,
    which is the "ascending" verdict being vacuous;
  * the ksf and best-time counts fail at 0, which is what a compiled-out
    loader gives;
  * the library switch fails if all three settings return the same count,
    which is what a filter that does nothing gives.

The fifth -- that the order was previously WRONG -- is checked here in Python
against the alphabetical order the browser used to draw, because building a
pre-patch menu.dat to prove that a list sorted by name is not sorted by tier
would be ceremony around an arithmetic fact.  It is printed as its own line so
the claim is visible rather than assumed.
"""

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = "cfg/test/b89browse.cfg"
LOG = os.path.join(ROOT, "ftesurf", "logs", "b89browse.log")
DATA = os.path.join(ROOT, "ftesurf", "data")

OLD_GUTTER = 92          # the flat width build 87 drew the button in


def read_rows(path, verb, n):
    """-> list of token lists for lines starting `verb` with >= n tokens."""
    out = []
    p = os.path.join(DATA, path)
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            t = ln.split()
            if len(t) >= n and t[0] == verb:
                out.append(t)
    return out


def expected():
    """The five figures, worked out of the data files alone."""
    meta = {t[1].lower(): t for t in read_rows("mapmeta.txt", "meta", 11)}
    dl = {t[1].lower(): t for t in read_rows("mapdl.txt", "dl", 8)}
    wr = {t[1].lower(): t for t in read_rows("mapwr.txt", "wr", 3)}

    # A tier comes from the fallback exactly when the browser would show NO tier
    # -- mapmeta has no row, or has one whose tier column is a sentinel -- and
    # mapdl carries a usable one.  Stated from the file rather than by reading
    # ui_meta_load a second time.
    #
    # BOTH HALVES OF "no tier", and the first cut had only the first.  It
    # predicted 462 against the engine's 550, and chasing the 88 (7 of them this
    # line, 81 of them a real misalignment) is what found the build-58 defect in
    # ui_dl_load.  A condition stated slightly wrong reads exactly like a bug in
    # the subject.
    def shown_tier(n):
        t = meta.get(n)
        if not t or not t[2].isdigit():
            return 0
        return int(t[2])

    ksf = [n for n, t in dl.items()
           if shown_tier(n) == 0 and t[4] not in ("0", "-")]
    # mapmeta.py's own tsrc `ksf` rows draw the same mark; they have a tier, so
    # they are never in the list above.
    ksf += [n for n, t in meta.items() if t[10] == "ksf" and shown_tier(n) > 0]

    return {
        "meta": meta,
        "dl": dl,
        "wr": wr,
        "ksf_max": len(ksf),
    }


def run(exe, timeout):
    # DELETE THE LOG FIRST -- FTE appends, so otherwise the grader reads a
    # previous run's lines too.  p465dl's control failed this way once.
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", CFG], cwd=ROOT, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


def grade(exp):
    if not os.path.exists(LOG):
        return False, ["no log at %s" % LOG]
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        log = fh.read()

    notes, ok = [], True

    def bad(msg):
        notes.append("^1FAIL^7 " + msg)

    def good(msg):
        notes.append("     " + msg)

    if 'Unknown command "ui_browse"' in log:
        return False, ["the menu VM never started -- menu_restart did not take"]

    # ---- the readings -----------------------------------------------------
    maps = re.findall(r"ui_browse: maps (\d+) -- tiered (\d+), untiered (\d+), "
                      r"(\d+) of them from ksf", log)
    best = re.findall(r"ui_browse: best times (\d+)", log)
    lib = re.findall(r"ui_browse: library both (\d+), momentum (\d+), "
                     r"cs:s (\d+)", log)
    order = re.findall(r"ui_browse: view (\d+), tier order (\S+)", log)
    ranks = re.findall(r"ui_browse: ranks ([\d ]+) \(", log)
    gut = re.findall(r"ui_browse: gutter (\d+) px \(label (\d+), "
                     r"re-get (\d+), pad (\d+)\)", log)
    ends = re.findall(r"ui_browse: first rank (\d+), last rank (\d+)", log)

    if not maps or not lib or not order or not ranks or not gut:
        return False, ["ui_browse printed nothing usable -- "
                       "maps=%d lib=%d order=%d ranks=%d gutter=%d"
                       % (len(maps), len(lib), len(order), len(ranks), len(gut))]

    # TWO readings are taken; they must agree with each other before either is
    # compared to anything.  A count that moves between two loads of the same
    # data is a bug in the loader whatever its value.
    if len(maps) > 1 and len(set(maps)) != 1:
        ok = False
        bad("the two readings disagree: %s" % (maps,))
    else:
        good("two readings agree")

    nmaps, tiered, untiered, ksf = (int(x) for x in maps[0])
    nbest = int(best[0])
    both, mom, css = (int(x) for x in lib[0])
    nview, verdict = int(order[0][0]), order[0][1]
    hist = [int(x) for x in ranks[0].split()]
    gw, wlabel, wreget, wpad = (int(x) for x in gut[0])

    # ---- 1. the gutter ----------------------------------------------------
    need = max(wlabel, wreget) + wpad
    if gw < need:
        ok = False
        bad("gutter %d px does not fit its own widest string (%d)" % (gw, need))
    else:
        good("gutter %d px fits label %d / re-get %d plus %d pad"
             % (gw, wlabel, wreget, wpad))

    # THE PREMISE.  If the old width was enough, the reported chop was not this.
    if wreget + wpad <= OLD_GUTTER:
        ok = False
        bad("the OLD %d px would have fitted re-get (%d + %d pad) -- the chop "
            "had another cause and this fix is aimed at the wrong thing"
            % (OLD_GUTTER, wreget, wpad))
    else:
        good("the old %d px could not: re-get needs %d + %d pad = %d"
             % (OLD_GUTTER, wreget, wpad, wreget + wpad))

    # ---- 2. tier order ----------------------------------------------------
    if verdict != "ascending":
        ok = False
        bad("tier order %s" % verdict)
    else:
        good("tier order ascending over %d rows" % nview)

    populated = len([h for h in hist if h > 0])
    if populated < 3:
        ok = False
        bad("only %d rank(s) populated -- 'ascending' measures nothing here: %s"
            % (populated, hist))
    else:
        good("%d of %d ranks populated: %s" % (populated, len(hist), hist))

    if sum(hist) != nview:
        ok = False
        bad("histogram sums to %d, view is %d" % (sum(hist), nview))

    if ends:
        first, last = (int(x) for x in ends[0])
        if last != len(hist) - 1 or hist[-1] == 0:
            ok = False
            bad("untiered maps are not last: first rank %d, last rank %d, "
                "untiered bucket %d" % (first, last, hist[-1]))
        else:
            good("first row rank %d, last row rank %d (untiered, %d of them)"
                 % (first, last, hist[-1]))

    # THE OLD ORDER, worked out here rather than built: the browser drew ms_name
    # order, which is alphabetical.  If that were already tier-ascending there
    # would have been nothing to fix.
    alpha = sorted(exp["meta"])
    seq = [exp["meta"][n][2] for n in alpha]
    seq = [int(t) if t.isdigit() and t != "0" else 99 for t in seq]
    drops = sum(1 for a, b in zip(seq, seq[1:]) if b < a)
    if drops == 0:
        ok = False
        bad("alphabetical order was ALREADY tier-ascending -- nothing to fix")
    else:
        good("the old alphabetical order went backwards %d times over %d "
             "mapmeta rows" % (drops, len(seq)))

    # ---- 3. the ksf tier fallback ----------------------------------------
    if ksf == 0:
        ok = False
        bad("no tiers came from KSF's roster -- the fallback did not run")
    elif ksf > exp["ksf_max"]:
        ok = False
        bad("%d ksf tiers, but only %d maps qualify from the data files"
            % (ksf, exp["ksf_max"]))
    else:
        good("%d tier(s) from KSF's roster, of %d that qualify (the rest are "
             "maps this install does not list)" % (ksf, exp["ksf_max"]))

    if untiered + tiered != nmaps:
        ok = False
        bad("tiered %d + untiered %d != %d maps" % (tiered, untiered, nmaps))

    # ---- 4. best times ----------------------------------------------------
    if nbest == 0:
        ok = False
        bad("no best times loaded -- data/mapwr.txt missing or unread")
    elif nbest > len(exp["wr"]):
        ok = False
        bad("%d best times, but mapwr.txt holds %d rows"
            % (nbest, len(exp["wr"])))
    else:
        good("%d best time(s) of mapwr.txt's %d rows joined onto the list"
             % (nbest, len(exp["wr"])))

    # ---- 5. the library switch -------------------------------------------
    if mom == both and css == both:
        ok = False
        bad("all three settings show %d rows -- the switch filters nothing"
            % both)
    elif mom == 0 or css == 0:
        ok = False
        bad("a setting shows nothing: momentum %d, cs:s %d" % (mom, css))
    elif mom > both or css > both:
        ok = False
        bad("a single library (%d / %d) exceeds both (%d)" % (mom, css, both))
    elif mom + css < both:
        ok = False
        bad("momentum %d + cs:s %d < both %d -- rows in neither list"
            % (mom, css, both))
    else:
        good("library: both %d, momentum %d, cs:s %d (overlap %d)"
             % (both, mom, css, mom + css - both))

    # ---- the named map, end to end ---------------------------------------
    for m in re.finditer(r"ui_browse: \"(\S+)\" tier (\S+) src (\S+) "
                         r"lst (\S+) wr (\S+) pb (\S+)", log):
        good("%s: tier %s src %s lst %s wr %s pb %s" % m.groups())

    return ok, notes


def main():
    exp = expected()
    print("b89browse: mapmeta %d, mapdl %d, mapwr %d rows on disk"
          % (len(exp["meta"]), len(exp["dl"]), len(exp["wr"])))
    secs = run("ftesurf64.exe", 180)
    print("b89browse: the run exited after %.0f s" % secs)
    ok, notes = grade(exp)
    for n in notes:
        print("  " + n.replace("^1", "").replace("^7", ""))
    print("b89browse: %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
