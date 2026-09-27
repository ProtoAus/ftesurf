#!/usr/bin/env python3
"""
p446inject.py -- driver for cfg/test/p446io.cfg (Patch 446: a map's allow-listed
console command could carry a second command past the allow-list, because Cbuf
terminates a line at an unquoted `;`).

    python tools/p446inject.py [--exe ftesurf64.exe] [--control] [--keep]
                               [--grade-only [--side fixed|control]]

THE ARM DRIVES THE REAL ENTITY-I/O PATH, and it has to MAKE its own condition.  No
shipped map carries an allow-listed Command with a `;` in it -- tools/census/iocmd.py
counted 1438 Command rows over all 1316 bsps and found THIRTEEN with a terminator, none
of them allow-listed -- so pointing at the corpus would be pointing at a filter that
never fires.  CLAUDE.md: make the condition, do not just point at it.
(Those counts are round 7's.  The first published pair was 737/3: the census took a
dict that dropped repeated entity keys, and assumed a comma separator where VBSP >= v25
uses 0x1B ESC.  The conclusion held; the numbers were roughly half.)

HOW THE FIXTURE IS MADE, and why it is not a compiled map.  bhop_futile's logic_auto
already fires `server,Command,sv_airaccelerate 150` at map spawn -- the row the gate's
own essay was written about.  Its parameter is replaced with

    echo P446FIRED;set p446hit 1

whose first token `echo` the allow-list admits and whose `;` is the payload.  The
second half is a `set` rather than a second `echo` because the refusal dprint QUOTES
the command it refused -- so any token inside the payload appears in the log on the
fixed build too, and the first cut of this arm read `payload present` on a build that
had just refused it.  A cvar is a witness the subject cannot echo.

A RAW BYTE PATCH DOES NOT REACH IT, and the first cut of this driver tried one and
refused itself loudly (needle count 0).  bhop_futile's entity lump is LZMA-compressed:
5616 bytes on disk, 67166 uncompressed, with the uncompressed size carried in the
lump's fourCC field.  So the fixture is built by RELOCATING the lump instead:
decompress, patch, append the plain text at end of file, and rewrite lump 0's header
entry to (new offset, 67166, version, fourCC 0).  VBSP lumps are addressed absolutely
and need not be contiguous, so this is a valid file and the abandoned compressed bytes
simply stop being referenced.  Nothing else in the header moves.

  on a PRE-446 build   Cbuf splits the line, the echo runs AND the `set` runs ->
                       `p446hit` reads 1.  That is the injection, demonstrated rather
                       than argued.
  on a FIXED build     SV_IOCmdInjects refuses -> the refusal line is in the log and
                       `p446hit` is still 0.  (Round 7 moved that test INSIDE the
                       allow-list, so only a verb the gate would have admitted can
                       reach it -- the census key was otherwise filed under "probing"
                       for every ordinary map in the corpus.)

The fixture is written to ftesurf/maps/ (gitignored) under its own name, never over a
Steam file, and removed afterwards.  It carries no zone data, which is deliberate:
this arm is about entity I/O at map spawn and a timer that never arms cannot confuse
the reading.

EACH SIDE HAS ITS OWN WITNESS THAT THE ENTITY FIRED AT ALL, and they differ because
the fix refuses the whole command rather than stripping its tail.  On the CONTROL it is
`fired` (the first echo ran).  On the FIXED build the echo does not run either, so the
witness is `injsay` -- SV_IOCommand's own refusal dprint, which it can only print if it
was reached.  Without one of these a build that simply never ran the entity would read
identically to one that refused, which is the arm-whose-condition-never-occurs trap a
level up.  `cvarread` is the third verdict beside them: it proves the payload witness
was readable, so `payload absent` cannot quietly mean "could not see".

RESULT 2026-09-27, both sides exit 0, re-run after round 7.  qwprogs AB1F10EBDD196A3E
fixed / 1F000116DB26CD5A control (a worktree at bb4fe45, HEAD before the patch).

  CONTROL  fired present, `p446hit` reads 1, no refusal line.  THE INJECTION IS
           DEMONSTRATED: a map's allow-listed `echo` carried a `set` past the gate and
           Cbuf ran it.  The real payload would have been `set run_starthop 0`, which
           the hop block reads live every packet.
  FIXED    fired ABSENT, `p446hit` still 0, refusal line present.

One prediction of mine was falsified and is written up where it was made: I expected
`fired` present on both sides.  Refusing outright discards the legitimate half too, so
a future map writing `say Secret 1; well done` prints nothing -- free only because the
census measured zero allow-listed rows carrying a `;` across all 1438 shipped rows.  And
the defect bit this arm's OWN cfg first: an `echo ==== ... fixture; its logic_auto ...`
line was split by Cbuf and the run logged `Unknown command "its"`.
"""
import argparse
import hashlib
import struct
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
MAPSDIR = os.path.join(GAMEDIR, "maps")
FIXTURE = os.path.join(MAPSDIR, "p446inject.bsp")
LOG = os.path.join(GAMEDIR, "logs", "p446io.log")
CFG = "cfg/test/p446io.cfg"

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common"
                     r"\Momentum Mod Playtest\momentum")
SRC_BSP = os.path.join(MOM, "maps", "bhop_futile.bsp")

OLD = b"sv_airaccelerate 150"
# THE LENGTH CONSTRAINT IS GONE, because the lump is rewritten whole (see the
# docstring) -- the first cut kept the text at 20 characters for an in-place patch that
# could not reach a compressed lump anyway.  So the payload is now the REAL attack
# shape: a `set` of a cvar, which leaves a witness that is not text.
NEW = b"echo P446FIRED;set p446hit 1"

# THE PAYLOAD IS GRADED ON A CVAR, NOT ON TEXT, and that is this arm's own first-run
# correction rather than a preference.  The first cut searched the log for the injected
# token -- and SV_IOCommand's refusal dprint QUOTES THE WHOLE COMMAND, so the token was
# present on the fixed build too and the arm read `payload present` on a build that had
# just refused it.  An arm cannot grade a string its own subject echoes back.
# `set p446hit 1` leaves a value instead, and the cfg zeroes it before the map loads so
# the reading is an EDGE and not a default.
FIELDS = {
    # `fired` and `payload` are searched with the `entity I/O:` lines REMOVED, for that
    # same reason: the refusal line contains both tokens.
    "fired":    rb"P446FIRED",
    "payload":  rb'"p446hit" is "1"',
    # Anchored on the DISTINCTIVE half only.  The full sentence was matched at first and
    # round 7 broke it by rewording the dprint (it gained `or $`) -- the arm went red on
    # a build whose refusal was working, which is the right failure for a check that
    # grades the subject's own print, but the pattern should not be that brittle.
    "injsay":   rb"REFUSED map command",
    "blocked":  rb"refused map command .* only say/echo/print",
    # Proof the cvar was readable at all.  Without it, `payload absent` could mean
    # "could not see" rather than "did not run" -- CLAUDE.md's third verdict, in the
    # arm rather than in the subject.
    "cvarread": rb'"p446hit" is "',
}
# Dropped before searching for a token the subject itself prints.
NOISE = rb"entity I/O:"
# A PREDICTION OF MINE WAS FALSIFIED HERE AND THE FIX IS SOUND ANYWAY.  I predicted
# `fired` PRESENT on both sides, treating the first echo as a side-agnostic positive
# control.  It reads ABSENT on the fixed build, because the refusal discards the WHOLE
# command -- including the legitimate half.  That is a real behavioural consequence of
# "refuse outright" rather than "strip the tail", and it is free only because
# tools/census/iocmd.py measured ZERO allow-listed rows carrying a `;` in 1316 shipped
# bsps.  A future map writing `say Secret 1; well done` would print nothing.
#
# So the two sides have DIFFERENT witnesses that the entity fired at all, and each is
# sound: on the control it is `fired`, and on the fixed build it is `injsay` -- which
# SV_IOCommand can only print if it was reached.  Neither side can pass while measuring
# nothing.
EXPECT_FIXED = {"fired": False, "payload": False, "injsay": True, "cvarread": True}
EXPECT_CONTROL = {"fired": True, "payload": True, "injsay": False, "cvarread": True}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest().upper()[:16]


def stage(new=None, fixture=None):
    """Copy the source map, patch its Command parameter, relocate the entity lump.

    `new` and `fixture` are parameters so a sibling arm can reuse this with a different
    payload (tools/p447dollar.py does, for the cvar-expansion question).  Defaults are
    this arm's own, so the call in main() is unchanged.

    Refuses loudly rather than guessing at every step: a needle that is absent or
    doubled means the source map is not the one this arm was written against, and
    every reading below would be void.
    """
    new = NEW if new is None else new
    fixture = FIXTURE if fixture is None else fixture
    if os.path.exists(fixture):
        raise SystemExit("refusing: %s already exists (a previous run did not clean up)"
                         % os.path.relpath(fixture, ROOT))
    if not os.path.exists(SRC_BSP):
        raise SystemExit("no source map at %s (set MOMENTUM_DIR)" % SRC_BSP)
    # NO LENGTH ASSERT.  The first cut had one, because it patched bytes in place; the
    # lump is rewritten and relocated now, so the replacement may be any length.  Left
    # as a note rather than deleted silently: an assert that no longer guards anything
    # is the kind of thing a later reader reinstates.

    sys.path.insert(0, os.path.join(ROOT, "tools", "census"))
    import bsplib

    with open(SRC_BSP, "rb") as fh:
        blob = bytearray(fh.read())
        fh.seek(0)
        L = bsplib.lumps(fh)
    if L is None:
        raise SystemExit("%s is not a VBSP" % os.path.basename(SRC_BSP))

    off, ln, ver, fourcc = L[0]                  # lump 0 = entities
    ents = bsplib._delump(bytes(blob[off:off + ln]))
    if not ents:
        raise SystemExit("could not decompress the entity lump")
    n = ents.count(OLD)
    if n != 1:
        raise SystemExit("the needle %r appears %d times in the entity lump -- "
                         "expected exactly 1" % (OLD.decode(), n))
    ents = ents.replace(OLD, new)

    # Append the plain text and repoint the lump.  VBSP lumps are absolute and need
    # not be contiguous, so the old compressed bytes just stop being referenced.
    newoff = len(blob)
    blob += ents
    hdr = 8 + 0 * 16
    blob[hdr:hdr + 16] = struct.pack("<iiii", newoff, len(ents), ver, 0)

    os.makedirs(MAPSDIR, exist_ok=True)
    with open(fixture, "wb") as fh:
        fh.write(blob)

    # Read it back through the same reader the census uses: if bsplib cannot parse the
    # result, the engine will not either, and a silent bad fixture would grade as a
    # clean refusal on both builds.
    check, _ = bsplib.read(fixture)
    got = [e for e in (check or []) if any(
        isinstance(v, str) and new.decode() in v for v in e.values())]
    if len(got) != 1:
        raise SystemExit("re-read of the fixture found %d entities carrying the "
                         "payload -- expected 1" % len(got))
    print("fixture %s  %d bytes  (entity lump %d -> %d bytes, relocated to %d, "
          "uncompressed)" % (os.path.relpath(fixture, ROOT), len(blob), ln,
                             len(ents), newoff))
    print("          %r -> %r  in %s" % (OLD.decode(), new.decode(),
                                         got[0].get("classname", "?")))


def restore(keep, fixture=None):
    """No `except: pass` -- a removal that did not happen must be loud."""
    fixture = FIXTURE if fixture is None else fixture
    if keep and os.path.exists(fixture):
        print("--keep: fixture left at %s" % os.path.relpath(fixture, ROOT))
        return
    if os.path.exists(fixture):
        os.remove(fixture)
        print("fixture removed")


def run(exe, timeout):
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


def grade(control):
    want = EXPECT_CONTROL if control else EXPECT_FIXED
    if not os.path.exists(LOG):
        print("no log at %s" % LOG)
        return False
    with open(LOG, "rb") as fh:
        txt = fh.read()
    # The subject quotes the command it refused, so the refusal lines are dropped
    # before anything is searched for a token that appears INSIDE that command.
    clean = b"\n".join(l for l in txt.split(b"\n") if NOISE not in l)
    ok = True
    print("observables (%s), %s predictions:"
          % (os.path.basename(LOG), "PRE-FIX" if control else "POST-FIX"))
    for k in sorted(set(list(want) + list(FIELDS))):
        hay = clean if k in ("fired", "payload") else txt
        got = bool(re.search(FIELDS[k], hay))
        if k not in want:
            print("  %-9s %-9s (reported, not graded)" % (k, "present" if got else "absent"))
            continue
        good = (got == want[k])
        ok = ok and good
        print("  %-9s %-9s %s" % (k, "present" if got else "absent",
                                  "ok" if good else "MISMATCH, want %s"
                                  % ("present" if want[k] else "absent")))
    unknown = re.findall(rb'Unknown command "([^"]+)"', txt)
    if unknown:
        print("  UNKNOWN COMMAND(S): %s -- the gesture did not land"
              % b", ".join(sorted(set(unknown))).decode(errors="replace"))
        ok = False
    # A map that did not load measures nothing, whatever the fields say.
    if not re.search(rb"p446inject", txt):
        print("  THE FIXTURE MAP IS NOT NAMED IN THE LOG -- it probably never loaded")
        ok = False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--side", default=None)
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    global LOG
    if a.grade_only:
        if a.side:
            LOG = LOG + "." + a.side
        return 0 if grade(a.control) else 1

    ran = [(d, sha(os.path.join(GAMEDIR, d))) for d in ("qwprogs.dat", "csprogs.dat")]
    for d, h in ran:
        print("%-12s %s" % (d, h))
    stage()
    try:
        secs = run(a.exe, a.timeout)
    finally:
        restore(a.keep)
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
