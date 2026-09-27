#!/usr/bin/env python3
"""
p447dollar.py -- does a map's allow-listed `say`/`echo` EXPAND a cvar with `$`?

    python tools/p447dollar.py [--exe ftesurf64.exe] [--control] [--keep]

THIS IS THE VERIFICATION PATCH 446 OWED.  446 refuses `$` in a map's console command,
and it did so on a READ OF THE ENGINE that nobody had driven:

    Cmd_ExpandCvar interpolates `$cvar` AFTER the Cbuf split, so it cannot start a
    second command -- but it can read a cvar INTO the allow-listed text.  The
    expansion gate admits any cvar whose restriction is <= the exec level, and at
    localcmd's RESTRICT_INSECURE (30) that includes rcon_password (restriction 29).
    The CVAR_NOUNSAFEEXPAND guard beside it tests Cmd_IsInsecure() against an exec
    level that is still 0 at expansion time, so it may not bite.

446 blocked it anyway because the census priced the block at zero (0 of 1438 shipped
Command rows contain `$` or `%`).  Blocking an unproven read for nothing is the right
trade -- but "unproven" is not a place to leave a possible secret disclosure, because
the ANSWER DECIDES SOMETHING OUTSIDE THE CODE: if a pre-446 build really did broadcast
`rcon_password` to everyone on the server, then that leaked for as long as the door was
open and THE LOBBY KEYS WANT ROTATING.  That is not a question a code comment can close.

THE REAL SECRET IS NEVER INVOLVED.  Two canaries instead, which separate the two halves
of the engine read:

  A  `p447canary`  -- an ordinary cvar with no flags.  Answers "does expansion happen
     at this exec level at all?"
  B  `rcon_password` SET TO A CANARY VALUE BY THIS CFG -- the same cvar the concern is
     about, carrying CVAR_NOUNSAFEEXPAND, but holding `CANARY447RCON` rather than
     anything real.  Answers "does the NOUNSAFEEXPAND guard bite?"  Testing the guard
     needs a cvar that HAS the flag; it does not need a live password, and using one
     would put a secret in a log file for no gain.

  A expands and B does not  -> expansion works, the guard bites, rcon_password was
                               never readable.  446's `$` block is belt-and-braces.
  A and B both expand       -> the read was REAL.  446 closed a secret disclosure, and
                               the lobby keys should be rotated.
  neither expands           -> the engine read was wrong and 446's `$` arm guards
                               nothing.  Still free, but say so.

The fixture is built by tools/p446inject.py's `stage()` (shared so there is one
implementation of the lump relocation), with this arm's own payload and its own
filename.  Run with --control against a PRE-446 build: on a fixed build `$` is refused
and the question cannot be asked, which is the point of the patch and is graded as
`refused`.

RESULT 2026-09-27, both sides exit 0.  qwprogs AB1F10EBDD196A3E fixed /
1F000116DB26CD5A control (a worktree at bb4fe45, HEAD before Patch 446).

    **THE ENGINE READ WAS REAL.  BOTH CANARIES EXPANDED ON THE PRE-446 BUILD.**

  CONTROL  fired present, `P447A CANARY447PLAIN` present, `P447B CANARY447RCON`
           PRESENT, `literal` absent.  So expansion happens at this exec level AND the
           CVAR_NOUNSAFEEXPAND guard did NOT bite -- the text really was substituted
           rather than printed literally.  A pre-446 map's
           `server,Command,say $rcon_password` would have broadcast the password to
           everyone on the lobby.
  FIXED    fired absent, both canaries absent, refusal present.  The question cannot
           even be asked on a build with 446 in it, which is the patch working.

WHAT IT MEANS OFF THE DISK: the fleet has a REAL 48-character rcon_password in
game/ftesurf/cfg/lobby_local.cfg (checked as a length, never printed), so there was a
live secret behind the door.  MITIGATING AND MEASURED: 0 of 1438 shipped Command rows
contain `$` or `%` (tools/census/iocmd.py), so nothing in the installed corpus exploited
it -- a crafted map would have had to be installed on the server first.  The hole closed
on the fleet at 2026-09-27 00:29:40 UTC when 446 deployed.  ROTATION IS THE OPERATOR'S
CALL and this tool does not touch credentials.

ONE DEFECT IN THIS ARM, found by running it: the first cut searched for the bare canary
VALUE, and the cfg sets and reads back both canaries -- so `plain` read present on a
build that had refused the command outright.  Every expansion field is anchored on its
marker now (`P447A <value>`), which nothing but a substitution can produce.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p446inject as P

ROOT = P.ROOT
GAMEDIR = P.GAMEDIR
FIXTURE = os.path.join(P.MAPSDIR, "p447dollar.bsp")
LOG = os.path.join(GAMEDIR, "logs", "p447dollar.log")
CFG = "cfg/test/p447dollar.cfg"

# Both canaries in one payload, so one map load answers both halves.  `echo` is
# allow-listed, and there is NO `;` -- this arm is about `$` alone, so a separator would
# confound it with the class 446 already closed.
PAYLOAD = b"echo P447A $p447canary P447B $rcon_password"

# EVERY EXPANSION FIELD IS ANCHORED ON ITS MARKER, and that is this arm's own first-run
# correction.  The first cut searched for the bare canary value -- and the cfg SETS and
# then READS BACK both canaries, so the value was in the log on a build that had refused
# the command outright: `plain present` on the fixed side, which is nonsense.  Same class
# as p446inject's first cut, where the refusal dprint quoted the token being searched
# for.  The payload is `echo P447A $p447canary P447B $rcon_password`, so an EXPANSION
# puts the value immediately after its marker and nothing else in the log can.
FIELDS = {
    "fired":    rb"P447A",
    # Expansion happened at all: the no-flags cvar's value, next to its marker.
    "plain":    rb"P447A CANARY447PLAIN",
    # The guard did not bite: the NOUNSAFEEXPAND cvar's value, next to its marker.
    # THIS IS THE ONE THE KEY-ROTATION QUESTION TURNS ON.
    "unsafe":   rb"P447B CANARY447RCON",
    "refused":  rb"REFUSED map command",
    # What a build that does NOT expand prints instead.
    "literal":  rb"P447A \$p447canary",
    # The third verdict: the canary really was SET, so an absent expansion cannot
    # quietly mean "the cvar was empty".  This one DOES read the cfg's own readback,
    # deliberately -- that is what it is for.
    "canaryset": rb'"p447canary" is "CANARY447PLAIN"',
}
# On a FIXED build the whole command is refused, so nothing is echoed and nothing is
# expanded -- `refused` is the witness that the entity fired.  On the CONTROL the
# question is actually asked, and `fired` is that witness.  `plain`/`unsafe` are
# REPORTED rather than predicted on the control: they ARE the unknown this arm exists to
# resolve, and pre-registering a value I do not know would make the run unfalsifiable.
EXPECT_FIXED = {"fired": False, "plain": False, "unsafe": False,
                "refused": True, "canaryset": True}
EXPECT_CONTROL = {"fired": True, "refused": False, "canaryset": True}
NOISE = rb"entity I/O:"


def grade(control):
    want = EXPECT_CONTROL if control else EXPECT_FIXED
    if not os.path.exists(LOG):
        print("no log at %s" % LOG)
        return False
    with open(LOG, "rb") as fh:
        txt = fh.read()
    clean = b"\n".join(l for l in txt.split(b"\n") if NOISE not in l)
    ok = True
    print("observables (%s), %s predictions:"
          % (os.path.basename(LOG), "PRE-446" if control else "POST-446"))
    for k in sorted(FIELDS):
        hay = clean if k in ("fired", "plain", "unsafe", "literal") else txt
        got = bool(re.search(FIELDS[k], hay))
        if k not in want:
            print("  %-8s %-8s (REPORTED -- this is the unknown, not a prediction)"
                  % (k, "present" if got else "absent"))
            continue
        good = (got == want[k])
        ok = ok and good
        print("  %-8s %-8s %s" % (k, "present" if got else "absent",
                                  "ok" if good else "MISMATCH, want %s"
                                  % ("present" if want[k] else "absent")))
    if not re.search(rb"p447dollar", txt):
        print("  THE FIXTURE MAP IS NOT NAMED IN THE LOG -- it probably never loaded")
        ok = False
    if control:
        pl = bool(re.search(FIELDS["plain"], clean))
        un = bool(re.search(FIELDS["unsafe"], clean))
        print()
        print("  VERDICT on the engine read 446 acted on:")
        if pl and un:
            print("    BOTH EXPANDED -- the read was REAL.  A pre-446 map could have")
            print("    broadcast rcon_password.  446 closed a secret disclosure and")
            print("    THE LOBBY KEYS SHOULD BE ROTATED.")
        elif pl and not un:
            print("    the plain cvar expanded, the NOUNSAFEEXPAND one did NOT -- the")
            print("    guard bites, rcon_password was never readable this way, and")
            print("    446's `$` arm is belt-and-braces rather than a closed hole.")
        elif not pl and not un:
            print("    NEITHER expanded -- expansion does not happen at this exec")
            print("    level, so the engine read was wrong and 446's `$` arm guards")
            print("    nothing.  Still free (0 shipped rows), but say so.")
        else:
            print("    the NOUNSAFEEXPAND cvar expanded and the plain one did not,")
            print("    which contradicts the engine read in both directions -- do not")
            print("    conclude anything from this run.")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    ran = [(d, P.sha(os.path.join(GAMEDIR, d)))
           for d in ("qwprogs.dat", "csprogs.dat")]
    for d, h in ran:
        print("%-12s %s" % (d, h))

    P.stage(new=PAYLOAD, fixture=FIXTURE)
    try:
        if os.path.exists(LOG):
            os.remove(LOG)
        flags = 0x08000000 if os.name == "nt" else 0
        p = subprocess.Popen([os.path.join(ROOT, a.exe), "-WindowStyle", "Minimized",
                              "+exec", CFG], cwd=ROOT, creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < a.timeout:
            time.sleep(1)
        if p.poll() is None:
            p.kill()
            raise SystemExit("the run did not exit in %g s -- killed" % a.timeout)
        secs = time.time() - t0
    finally:
        P.restore(a.keep, fixture=FIXTURE)
    print("ran %s on %s for %.0f s" % (a.exe, CFG, secs))
    good = grade(a.control)
    side = "control" if a.control else "fixed"
    shutil.copyfile(LOG, LOG + "." + side)
    with open(LOG + "." + side + ".hash", "w") as fh:
        for d, h in ran:
            fh.write("%s %s\n" % (d, h))
    print("kept %s and its .hash" % os.path.relpath(LOG + "." + side, ROOT))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
