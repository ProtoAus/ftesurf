#!/usr/bin/env python3
"""
b90bind.py -- driver for cfg/test/b90bind.cfg (build 90: the save-lock actions
as bindable names, and Momentum's spellings aliased onto them).

    python tools/b90bind.py [--exe ftesurf64.exe]

WHAT IT GRADES, AND WHAT IT REFUSES TO GRADE.  The change is small -- eleven
registercommand lines, one dispatch hook and a cfg alias block -- and every way
it can fail is silent.  A name that was not registered prints `Unknown command`
and does nothing; a name aliased straight onto `cmd sl_*` works perfectly and
skips the clean-run guard.  Neither shows up in a screenshot, and neither shows
up in "the game did not crash".

So every arm here reads a line the HANDLER PRINTED ITSELF:

  arm 0/1  the sl_delall arming line.  It is the only action that prints on the
           first press, and the server has no such arming -- so reading it
           proves the name reached SaveLoc_Console rather than being forwarded.
  arm 2    `saveloc`'s `holding` field, which build 90 added to that status line
           precisely because +sl_hold latches without a keypress and nothing
           printed the key side.
  arm 3    SaveLoc_Refuse's "no loads mid-run", gated on arm 3a having shown
           `locked 1` first.

ARM 3 HAS THREE VERDICTS.  A clean run may simply fail to start -- the clock
begins when the hull leaves the start box and AGENTS.md records a map where a
plain +forward stops inside it.  If `locked 0` the refusal had nothing to
refuse, and this reports INCONCLUSIVE and exits 2.  Reporting that as a pass is
the failure mode this whole file is arranged against: an arm that passes because
its condition never occurred proves nothing.

THE CONTROL.  There is no separate pre-change build, because each arm carries
its own falsifier in the same run: arm 0 fails on `Unknown command "sl_delall"`,
which is exactly what the previous build printed; arm 1 fails the same way for
the alias; arm 2 fails if `holding` never reaches 1; arm 3 fails if a clean run
was on the clock and the load went through anyway, which is the bare-alias bug
this design exists to avoid.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = "cfg/test/b90bind.cfg"
LOG = os.path.join(ROOT, "ftesurf", "logs", "b90bind.log")

# Arms 0 and 1 arm a delete-every-save on this map.  They are spaced past
# FS_SL_ARMTIME so neither confirms, but "the spacing holds" is not something to
# bet somebody's saves on -- so the tree is renamed aside for the run and the
# restore is CHECKED.  The `.savepark` suffix is p434rew.py's, deliberately:
# one park name across every driver means the second one refuses instead of
# rmtree-ing the first one's work.
SAVES = os.path.join(ROOT, "ftesurf", "data", "saves", "surf_dune")
PARK = SAVES + ".savepark"

ARM = re.compile(r"saveloc:\s+again within [\d.]+ s to delete EVERY save")
REFUSE = re.compile(r"saveloc:\s+no loads mid-run")
STATUS = re.compile(r"saveloc: locked (\d+) refkey (\d+) hold (\d+) holding (\d+)")


def run(exe, timeout):
    # DELETE THE LOG FIRST -- FTE appends, so otherwise the grader reads a
    # previous run's lines too (b89browse's header records p465dl losing a
    # control run to exactly this).
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


def park():
    """Returns (parked, entries) -- the count is what unpark checks against."""
    if os.path.exists(PARK):
        raise SystemExit("%s already exists -- another driver is mid-run, or "
                         "one died holding it. Put it back by hand." % PARK)
    if os.path.exists(SAVES):
        n = len(os.listdir(SAVES))
        os.rename(SAVES, PARK)
        return True, n
    return False, 0


def unpark(parked, had):
    """NEVER swallowed: a cleanup that cannot fail is a cleanup that never ran."""
    made = os.path.isdir(SAVES)
    if not parked:
        if made:
            print("b90bind: the run created %s and nothing was parked -- left "
                  "in place, delete it if you do not want it" % SAVES)
        return
    if made:
        # Safe to remove: SAVES did not exist when park() ran, so everything
        # in it is arm 2's own sl_save.  The originals are in PARK.
        shutil.rmtree(SAVES)
        print("b90bind: removed the save arm 2 created")
    os.rename(PARK, SAVES)
    if not os.path.isdir(SAVES):
        raise SystemExit("restore failed: %s is not a directory" % SAVES)
    back = len(os.listdir(SAVES))
    if back != had:
        raise SystemExit("restore is short: parked %d entries, put back %d"
                         % (had, back))
    print("b90bind: surf_dune saves restored (%d entries)" % back)


def grade():
    """Returns (ok, inconclusive, notes)."""
    if not os.path.exists(LOG):
        return False, False, ["no log at %s" % LOG]
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        log = fh.read()

    notes, ok, incon = [], True, False

    # The first cut of this arm ran every command against an engine that had a
    # map and no client VM, and every `Unknown command` below was that rather
    # than a missing registration.  Refuse to grade such a run at all.
    if "FTESurf CSQC loaded" not in log:
        return False, False, ["csprogs never loaded -- the arms beat the boot "
                              "and measured an engine with no client VM. "
                              "Nothing here is a verdict about the change."]

    def bad(m):
        notes.append("FAIL " + m)

    def good(m):
        notes.append("     " + m)

    # Split on the arm banners so a line from arm 0 cannot be read as arm 3's.
    def section(a, b=None):
        i = log.find(a)
        if i < 0:
            return ""
        j = log.find(b, i) if b else len(log)
        return log[i:j if j > 0 else len(log)]

    s0 = section("b90 arm 0", "b90 arm 1")
    s1 = section("b90 arm 1", "b90 arm 2")
    s2 = section("b90 arm 2", "b90 arm 3")
    s3a = section("b90 arm 3a", "b90 arm 3b")
    s3b = section("b90 arm 3b", "b90 done")

    if not s0 or not s3b:
        return False, False, ["the run did not reach every arm -- check %s" % LOG]

    for name in ("sl_delall", "mom_saveloc_remove_all", "+sl_hold", "-sl_hold",
                 "sl_next", "saveloc"):
        if 'Unknown command "%s"' % name in log:
            bad("%s was never registered -- the engine called it unknown" % name)
            ok = False

    # ---- arm 0: the bare name reaches SaveLoc_Console ----------------------
    if ARM.search(s0):
        good("arm 0  sl_delall armed and said so -- dispatched into the handler")
    else:
        bad("arm 0  sl_delall printed no arming line; either the name did not "
            "reach SaveLoc_Console or it deleted outright")
        ok = False

    # ---- arm 1: the alias, and that arm 0's arm had lapsed -----------------
    if ARM.search(s1):
        good("arm 1  mom_saveloc_remove_all armed too -- the alias resolves, "
             "and it ARMED rather than confirming, so FS_SL_ARMTIME held")
    else:
        bad("arm 1  the Momentum alias printed no arming line")
        ok = False

    # ---- arm 2: sl_save, then the hold pair --------------------------------
    # The list line is the server's own answer, so an sl_save that never landed
    # fails HERE rather than surfacing as a hold that would not latch -- which
    # is what the first cut of this arm reported.
    if "nothing saved on this map" in s2:
        bad("arm 2  sl_save left the list empty -- the save did not land, so "
            "the hold below has nothing to hold and cannot be measured")
        ok = False
    else:
        good("arm 2  sl_save landed -- the map's list is no longer empty")

    holds = [int(m.group(4)) for m in STATUS.finditer(s2)]
    if len(holds) < 3:
        bad("arm 2  expected three saveloc status lines, read %d" % len(holds))
        ok = False
    elif holds[0] == 0 and holds[1] == 1 and holds[2] == 0:
        good("arm 2  holding 0 -> 1 -> 0 across +sl_hold / -sl_hold")
    else:
        bad("arm 2  holding went %s; wanted 0 -> 1 -> 0. A middle 0 means "
            "+sl_hold never latched" % " -> ".join(str(h) for h in holds))
        ok = False

    # ---- arm 3: the guard, and whether it could be measured at all ---------
    m = STATUS.search(s3a)
    if not m:
        bad("arm 3a no saveloc status line -- cannot say whether a run was on")
        ok = False
    elif m.group(1) == "0":
        notes.append("---- arm 3  INCONCLUSIVE: locked 0, so no clean run was "
                     "on the clock. The hull did not leave the start box (see "
                     "the cfg header). The guard was NOT exercised -- this is "
                     "not a pass.")
        incon = True
    else:
        good("arm 3a locked 1 -- a clean run is on the clock, so the next "
             "line is a measurement")
        if REFUSE.search(s3b):
            good("arm 3b sl_next was REFUSED -- the bound name goes through "
                 "SaveLoc_RunLocked, not straight to `cmd sl_next`")
        else:
            bad("arm 3b sl_next was NOT refused on a clean run. This is the "
                "bare-alias bug: a bound load that ends a clean PB where the "
                "digit key would have refused it")
            ok = False

    return ok, incon, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    if not a.grade_only:
        parked, had = park()
        print("b90bind: surf_dune saves %s"
              % ("parked (%d entries)" % had if parked
                 else "absent, nothing to park"))
        try:
            secs = run(a.exe, 300)
            print("b90bind: the run exited after %.0f s" % secs)
        finally:
            unpark(parked, had)     # including when the run throws or is killed
    ok, incon, notes = grade()
    for n in notes:
        print("  " + n)
    if not ok:
        print("b90bind: FAIL")
        sys.exit(1)
    if incon:
        print("b90bind: INCONCLUSIVE -- arms 0-2 passed, arm 3 never ran its case")
        sys.exit(2)
    print("b90bind: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
