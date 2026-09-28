#!/usr/bin/env python3
"""
b89join.py -- does a lobby join fetch the map before connecting?

    python tools/b89join.py

WHAT IT IS FOR.  Lex was kicked from a public lobby on surf_rookie for a map
mismatch and asked for the download to happen on join instead of being a button
they have to know to press.  ui_prejoin holds the connect, fetches the Pi's
build and issues the connect itself.  This is whether that is true.

THE TWO NEGATIVE ARMS ARE NOT PADDING.  A pre-join check that holds a connect it
should not have held is a player who cannot join anything, which is a worse bug
than the one being fixed -- so "does not hold" is graded as hard as "holds".
And the run is against the REAL mirror: a stub would prove the state machine and
leave the feature unproven.

CLEANUP IS PART OF THE ARM.  Arm 3 really downloads a map into ftesurf/maps/,
and this removes it afterwards and SAYS SO -- a driver that leaks its fixture
makes the next run's "already have it" a pass for the wrong reason.  The removal
is checked rather than wrapped in a bare except.
"""

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = "cfg/test/b89join.cfg"
LOG = os.path.join(ROOT, "ftesurf", "logs", "b89join.log")

HAVE = "surf_ace"                       # installed here, size agrees with the Pi
NONE = "surf_no_such_map_anywhere"      # in no list at all
WANT = "bhop_back_and_forth"            # 562 KB, the smallest we do not have
WANT_BSP = os.path.join(ROOT, "ftesurf", "maps", WANT + ".bsp")


def run(exe, timeout):
    # DELETE THE LOG FIRST -- FTE appends, so the grader would otherwise read a
    # previous run's lines too.  p465dl's control failed exactly this way once.
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


def grade():
    if not os.path.exists(LOG):
        return False, ["no log at %s" % LOG]
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        log = fh.read()

    notes, ok = [], True

    def bad(m):
        notes.append("FAIL " + m)

    def good(m):
        notes.append("     " + m)

    if 'Unknown command "ui_prejoin"' in log:
        return False, ["the menu VM never started -- menu_restart did not take"]

    held = dict((m.group(1), int(m.group(2))) for m in
                re.finditer(r'ui_prejoin: "(\S+)" held=(\d+)', log))
    for name in (HAVE, NONE, WANT):
        if name not in held:
            return False, ["ui_prejoin never reported on %s" % name]

    # ---- the two that must NOT hold --------------------------------------
    if held[HAVE] != 0:
        ok = False
        bad("%s is installed and agrees on size, yet the join was held" % HAVE)
    else:
        good("%s: not held, as it should not be" % HAVE)

    if held[NONE] != 0:
        ok = False
        bad("%s is in no list at all, yet the join was held" % NONE)
    else:
        good("%s: not held -- an unknown map connects and lets the server "
             "answer" % NONE)

    # ---- the one that must ------------------------------------------------
    if held[WANT] != 1:
        ok = False
        bad("%s is NOT on this disk and the join was not held -- the fetch "
            "never happened" % WANT)
        return ok, notes
    good("%s: held" % WANT)

    # The subject's own words for each step, not a downstream consequence.
    if ("holding the join" not in log) or (WANT not in log.split("holding the join")[1][:200]):
        ok = False
        bad("no 'holding the join' line naming %s" % WANT)
    else:
        good("it said so: 'holding the join -- fetching the server's build'")

    if "got it -- connecting to" not in log:
        ok = False
        bad("the fetch never handed off: no 'got it -- connecting' line. "
            "Last dlstate lines: %s"
            % (re.findall(r"ui_dlmap: .*", log)[-2:] or "none"))
    else:
        good("handed off: " + re.search(r"got it -- connecting to \S+",
                                        log).group(0))

    # And the file really arrived, which is the only thing that makes the
    # hand-off honest -- Dl_Tick asks the filesystem for exactly this reason.
    if not os.path.exists(WANT_BSP):
        ok = False
        bad("no %s on disk after the run" % WANT_BSP)
    else:
        good("%s is on disk, %d bytes" % (WANT + ".bsp",
                                          os.path.getsize(WANT_BSP)))
    return ok, notes


def cleanup():
    """Remove the fixture and SAY what happened.  Never a bare except: a
    removal that silently did not happen makes the next run pass for the wrong
    reason."""
    if not os.path.exists(WANT_BSP):
        return "nothing to clean up"
    try:
        os.remove(WANT_BSP)
    except OSError as exc:
        return "COULD NOT REMOVE %s: %s -- the next run will read 'already " \
               "have it' and pass for the wrong reason" % (WANT_BSP, exc)
    if os.path.exists(WANT_BSP):
        return "%s still present after remove()" % WANT_BSP
    return "removed %s" % os.path.basename(WANT_BSP)


def main():
    if os.path.exists(WANT_BSP):
        print("b89join: %s is already here; removing it so arm 3 has its case"
              % os.path.basename(WANT_BSP))
        os.remove(WANT_BSP)
    secs = run("ftesurf64.exe", 240)
    print("b89join: the run exited after %.0f s" % secs)
    ok, notes = grade()
    for n in notes:
        print("  " + n)
    print("b89join: cleanup -- %s" % cleanup())
    print("b89join: %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
