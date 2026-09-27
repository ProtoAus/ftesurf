#!/usr/bin/env python3
"""
p450map.py -- driver for cfg/test/p450map.cfg (Patch 450: a start-box load only arms
clean if the save can prove which BSP it came from).

    python tools/p450map.py [--exe ftesurf64.exe] [--control] [--keep]
                            [--grade-only [--side fixed|control]]

Control is HEAD before Patch 450, built in a worktree as elsewhere in this tree.

WHAT IT MEASURES is in the cfg's header.  In one line: the Build 47 gate launders a
start-box load's taint by forcing an arm, and it did so without ever checking that the
save came from the bsp now loaded -- the zone JSON is keyed by map NAME, so the
coordinates match on a different .bsp while the brushes SL_RowGrounded traces do not.

THE THIRD SECTION IS THE POINT OF THE ARM.  A patch that refuses everything would pass
two sections out of three, so `S` takes a save ON THIS INSTALL (`sl_save`) and loads it:
that save carries the live crc without this file hard-coding one, which would be wrong on
every other machine.  N is the pre-450 save (no crc: cannot tell), W is a deliberately
wrong crc (disproved), S is a provable match.  Three states, three readings, because the
flag gates a GRANT and "cannot tell" therefore has to refuse.

THE PREMISE THAT THE REFUSAL IS THE *MAP* CHECK is carried by `nocrc`/`crcsay` naming
the reason, plus section S reading `support 1` on the same kind of row on the same build.
It is NOT carried by `support` at N: the gate tests the map before SL_RowGrounded, so on
a refused map the probe never runs and prints nothing.  The first run of this arm
predicted `support 1` there and read <absent>; the ordering is right, so the arm moved.

RESULT 2026-09-27, both sides exit 0.  qwprogs BFC3D491E36ADAB1 fixed /
2EE7916A043FC579 control (a worktree at 7947906, HEAD before this patch).

  CONTROL  N `class clean practice 0 support 1` -- the gate fired and LAUNDERED a save
           that cannot prove its map.  W the same, on a save whose crc is definitely not
           this install's.  S also clean.  So pre-450 every load at rest in a start box
           armed clean regardless of which bsp the save came from.
  FIXED    N `segmented practice 1` + the "cannot prove which bsp" dprint.
           W `segmented practice 1` + the "taken on a DIFFERENT bsp" dprint -- a different
           sentence, which is the third verdict being distinguishable rather than
           decorative.
           S `clean practice 0` -- the gesture the gate exists for still works.

S IS WHAT MAKES THE OTHER TWO MEAN ANYTHING.  A patch that simply broke the gate would
pass N and W and fail S, and S reads identically on both builds (clean/0): on the control
because nothing was checked, on the fixed build because the save proved its map.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")
SAVES = os.path.join(GAMEDIR, "data", "saves", "bhop_eazy")
PARK = SAVES + ".savepark"          # the shared park name -- see tools/p443start.py
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
LOG = os.path.join(GAMEDIR, "logs", "p450map.log")
CFG = "cfg/test/p450map.cfg"
EXTRA = ["+set", "sv_gamemode", "surf"]

STAGED = (("save901", "p435rest.txt"),      # no mapcrc: the pre-450 save
          ("save902", "p450wrong.txt"))     # a non-empty crc that is not this install's

FIELDS = {
    "state":    r"timer: (\w+) on",
    "class":    r"class: (\w+) \(seg",
    "practice": r"practice (\d)",
    "support":  r"save: row -?\d+ support (\d)",
    "azone":    r"arm zone (-?\d+) \(armed from",
    "evslot":   r"seq: event seq \d+ op 2 id (\d+)",
    "hopped":   r"start:.* hopped (\d)",
    # The two refusals, which MUST read differently -- one is "cannot tell", the other is
    # "no".  Folding them into one message would make the third verdict undetectable.
    "nocrc":    r"(cannot prove which bsp it came from)",
    "crcsay":   r"(was taken on a DIFFERENT bsp)",
}
PRESENCE = ("nocrc", "crcsay")

EXPECT = {
    # `support` IS NOT GRADED HERE and the first run is why.  The gate tests sl_mapsame
    # BEFORE SL_RowGrounded, so on a refused map the probe never runs and prints nothing
    # -- `support` reads <absent>, not 0.  That ordering is right (a string compare is
    # cheaper than a tracebox, and there is nothing to ask about geometry until the bsp is
    # known), so the ARM moved rather than the code.
    # The premise it was there for is carried by two other readings instead: `nocrc`
    # present proves the refusal came from the MAP check by name, and section S reads
    # `support 1` on the same kind of row on the same build, proving the probe accepts it.
    "N": {"class": "segmented", "practice": "1", "nocrc": "present"},
    "W": {"class": "segmented", "practice": "1", "crcsay": "present"},
    "S": {"class": "clean", "practice": "0"},
}
CONTROL = {
    # Pre-450 the gate never asked, so every load at rest in the box laundered.
    "N": {"class": "clean", "practice": "0", "nocrc": "absent"},
    "W": {"class": "clean", "practice": "0", "crcsay": "absent"},
    # S reads the same on both sides: on the control because nothing was checked, on the
    # fixed build because the save proved its map.  That is what makes it a guard for
    # "the patch did not simply break the gesture".
}
REPORT = {
    "N": ("state", "azone", "evslot", "hopped", "support"),
    "W": ("state", "azone", "evslot", "support", "hopped"),
    "S": ("state", "azone", "evslot", "support", "hopped", "nocrc", "crcsay"),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest().upper()[:16]


def stage():
    if os.path.isdir(PARK):
        raise SystemExit("refusing: %s already exists (a previous run did not restore)"
                         % os.path.relpath(PARK, ROOT))
    if os.path.exists(ZONES):
        raise SystemExit("refusing: %s already exists -- it shadows the shipped zones"
                         % os.path.relpath(ZONES, ROOT))
    if os.path.isdir(SAVES):
        os.rename(SAVES, PARK)
    for slot, src in STAGED:
        d = os.path.join(SAVES, slot)
        os.makedirs(d)
        shutil.copyfile(os.path.join(CFGDIR, src), os.path.join(d, "state.txt"))
    os.makedirs(os.path.dirname(ZONES), exist_ok=True)
    shutil.copyfile(os.path.join(CFGDIR, "p435.zones.json"), ZONES)
    print("staged %d save rows and the zones override" % len(STAGED))


def listing(where):
    out = []
    for dirpath, dirnames, files in os.walk(where):
        dirnames.sort()
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            out.append("    %s  %d bytes" % (os.path.relpath(p, ROOT), os.path.getsize(p)))
    return out


def restore(keep):
    """No `except: pass` anywhere -- a removal that did not happen must be loud, and a
    left-behind zones override silently shadows the shipped zones for every later run."""
    if os.path.exists(ZONES):
        os.remove(ZONES)
    if keep and os.path.isdir(SAVES):
        kept = SAVES + ".kept.p450"
        if os.path.isdir(kept):
            shutil.rmtree(kept)
        shutil.copytree(SAVES, kept)
        print("--keep: staged copy at %s" % os.path.relpath(kept, ROOT))
    if os.path.isdir(SAVES):
        shutil.rmtree(SAVES)
    if os.path.isdir(PARK):
        os.rename(PARK, SAVES)


def sections(path):
    with open(path, "r", errors="replace") as fh:
        txt = fh.read()
    out, cur = {}, None
    for line in txt.splitlines():
        m = re.search(r"==== (\S+)\b", line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        if cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def read(txt, name):
    if name in PRESENCE:
        return "present" if re.search(FIELDS[name], txt) else "absent"
    m = re.search(FIELDS[name], txt, re.M)
    return m.group(1) if m else "<absent>"


def grade(control):
    want = {t: dict(v) for t, v in EXPECT.items()}
    if control:
        for t, over in CONTROL.items():
            want.setdefault(t, {}).update(over)
    s = sections(LOG)
    ok = True
    print("observables (%s), %s predictions:"
          % (os.path.basename(LOG), "PRE-450" if control else "POST-450"))
    for tag in sorted(set(list(want) + list(REPORT))):
        txt = s.get(tag)
        if txt is None:
            print("  %-3s SECTION ABSENT -- the cfg never reached it" % tag)
            ok = False
            continue
        for k in sorted(want.get(tag, {})):
            got, w = read(txt, k), want[tag][k]
            good = (got == w)
            ok = ok and good
            print("  %-3s %-9s %-12s %s"
                  % (tag, k, got, "ok" if good else "MISMATCH, want %s" % w))
        for k in REPORT.get(tag, ()):
            if k not in want.get(tag, {}):
                print("  %-3s %-9s %-12s (reported, not graded)" % (tag, k, read(txt, k)))
    with open(LOG, "r", errors="replace") as fh:
        blob = fh.read()
    unknown = re.findall(r'Unknown command "([^"]+)"', blob)
    if unknown:
        print("  UNKNOWN COMMAND(S): %s -- the gesture did not land"
              % ", ".join(sorted(set(unknown))))
        ok = False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--timeout", type=float, default=200)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--side", default=None)
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    global LOG
    if a.grade_only:
        if a.side:
            LOG = LOG + "." + a.side
        return 0 if grade(a.control) else 1

    for _, src in STAGED:
        if not os.path.exists(os.path.join(CFGDIR, src)):
            raise SystemExit("no fixture: %s" % src)
    ran = [(d, sha(os.path.join(GAMEDIR, d))) for d in ("qwprogs.dat", "csprogs.dat")]
    for d, h in ran:
        print("%-12s %s" % (d, h))
    cleanup_ok = True
    left = []
    stage()
    try:
        if os.path.exists(LOG):
            os.remove(LOG)
        flags = 0x08000000 if os.name == "nt" else 0
        p = subprocess.Popen([os.path.join(ROOT, a.exe), "-WindowStyle", "Minimized"]
                             + EXTRA + ["+exec", CFG], cwd=ROOT, creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < a.timeout:
            time.sleep(1)
        if p.poll() is None:
            p.kill()
            raise SystemExit("the run did not exit in %g s -- killed" % a.timeout)
        secs = time.time() - t0
        left = listing(SAVES)
    finally:
        try:
            restore(a.keep)
        except OSError as exc:
            cleanup_ok = False
            print("CLEANUP FAILED, the shared fixture may still be parked at %s: %s"
                  % (os.path.relpath(PARK, ROOT), exc))
    print("ran %s on %s for %.0f s" % (a.exe, CFG, secs))
    print("the staged tree at exit (%d file(s)):" % len(left))
    for line in left:
        print(line)
    good = grade(a.control)
    side = "control" if a.control else "fixed"
    shutil.copyfile(LOG, LOG + "." + side)
    with open(LOG + "." + side + ".hash", "w") as fh:
        for d, h in ran:
            fh.write("%s %s\n" % (d, h))
    print("kept %s and its .hash" % os.path.relpath(LOG + "." + side, ROOT))
    return 0 if (good and cleanup_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
