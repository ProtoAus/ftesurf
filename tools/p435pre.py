#!/usr/bin/env python3
"""
p435pre.py -- driver for cfg/test/p435pre.cfg (Patch 435: a start-box load that
carries speed does not arm a clean run).

WHY A DRIVER.  The arm needs three files in the live tree that a cfg cannot
write: two save fixtures (the pair that differs in one line) and a local zones
file that lowers bhop_eazy's start region so Build 47's gate fires at all.  The
zones file especially must not be left behind -- it shadows the shipped one for
every harness on this map, and pm_verify REFUSEs a recording made under it.

ftesurf/data/saves/bhop_eazy IS A SHARED FIXTURE (p415reset, p428hold, p434rew
read it).  It is PARKED -- renamed, not copied -- and restored afterwards,
including when the run throws.  --keep leaves the staged tree for inspection.

    python tools/p435pre.py [--exe ftesurf64.exe] [--control] [--grade-only]

--control grades the PRE-fix predictions: copy sv_saveloc.qc aside, `git
checkout --` it, build, run this with --control, copy back, rebuild, run again.

Exit status 0 when every pre-registered prediction in the cfg header held.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
SAVES = os.path.join(GAMEDIR, "data", "saves", "bhop_eazy")
PARK = SAVES + ".p435park"
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")
ZONES_SRC = os.path.join(CFGDIR, "p435.zones.json")

# tag -> the fixtures it needs staged
SAVES_STAGED = (("save901", "p435rest.txt"), ("save902", "p435speed.txt"))


def stage(zones):
    if os.path.isdir(PARK):
        raise SystemExit("refusing: %s already exists (a previous run did not restore)" % PARK)
    if not zones and os.path.exists(ZONES):
        raise SystemExit("refusing: %s already exists -- it shadows the shipped zones" % ZONES)
    if os.path.isdir(SAVES):
        os.rename(SAVES, PARK)
    for slot, src in SAVES_STAGED:
        d = os.path.join(SAVES, slot)
        os.makedirs(d)
        shutil.copyfile(os.path.join(CFGDIR, src), os.path.join(d, "state.txt"))
    if zones:
        os.makedirs(os.path.dirname(ZONES), exist_ok=True)
        shutil.copyfile(os.path.join(CFGDIR, "p435.zones.json"), ZONES)


def restore(keep):
    if os.path.exists(ZONES):
        os.remove(ZONES)
    if keep:
        print("--keep: staged saves left at %s (the zones fixture is always removed)" % SAVES)
        return
    if os.path.isdir(SAVES):
        shutil.rmtree(SAVES)
    if os.path.isdir(PARK):
        os.rename(PARK, SAVES)


def run(exe, timeout, cfg, log, extra=()):
    # The basedir is the cwd, so this must not inherit a shell left in ftesurf/.
    if os.path.exists(log):
        os.remove(log)
    flags = 0x08000000 if os.name == "nt" else 0     # CREATE_NO_WINDOW
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized"]
                         + list(extra) + ["+exec", cfg], cwd=ROOT,
                         creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


def sections(path):
    """{tag: text} keyed by the cfg's own `---- <tag> ` and `==== <arm> ` echoes,
    so a read is graded against the lines that follow its own marker.  Tags are
    one to four characters (A1, ML2, H1), stopped by the space the echo has."""
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines()
    out, cur = {}, None
    for line in lines:
        m = re.search(r"(?:----|====) ([A-Za-z][A-Za-z0-9]{0,3}) ", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


PATS = {
    "state": r"timer: (\w+) on",
    "startrule": r"timer: \w+ on \S+, tick \S+, (start on \w+)",
    "practice": r"practice (\d)",
    "class": r"class: (\w+) \(seg",
    "armzone": r"arm zone (-?\d+) \(armed from (-?\d+)\)",
    "horizontal": r"horizontal (-?[\d.]+)",
    # viewpos answers `setpos x y z pitch yaw roll` on the line above it.
    "z": r"setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)",
}


def get(txt, key, which=0):
    ms = list(re.finditer(PATS[key], txt))
    if not ms:
        return "<absent>"
    m = ms[which]
    if key == "armzone":
        return "%s/%s" % (m.group(1), m.group(2))
    if key == "z":
        return m.group(3)
    return m.group(1)


# The pre-registered predictions, POST-FIX and on the CONTROL build.  `bled`
# means "the row's 250 u/s is on the body", graded as a number rather than a
# string because friction and the packet boundary move it by a few units.
EXPECT = {
    # A1 is parked: Patch 428 runs no zone tests under a hold, so the arm cannot
    # have landed yet and the class still reads the load's taint on BOTH builds.
    # The gate's own effect is `arm zone`, and the class shows at A3.
    "A1": {"state": "armed", "practice": "1", "class": "segmented", "armzone": "-1/0"},
    "A2": {"horizontal": 0.0},
    "A3": {"state": "running", "practice": "0", "class": "clean"},
    "B1": {"state": "armed", "practice": "1", "class": "segmented", "armzone": "0/0"},
    "B2": {"horizontal": 0.0},
    "B3": {"horizontal": "bled"},
    "B4": {"state": "running", "practice": "1", "class": "segmented"},
    "C1": {"horizontal": 250.0},
    "C2": {"practice": "1", "class": "segmented"},
}
CONTROL = {
    "B1": {"armzone": "-1/0"},
    "B4": {"practice": "0", "class": "clean"},
    "C2": {"practice": "0", "class": "clean"},
}


    # --shipped grades these: bhop_eazy's own zones, where Build 47's gate never
# fires, so the question is whether a HOP launders the load's taint.  Both
# expectations are Patch 415's measurement, repeated: the gate cannot fire, so
# nothing here arms clean -- at rest OR with speed, hop or not.
EXPECT_SHIP = {
    "H1": {"practice": "1", "class": "segmented", "armzone": "-1/0"},
    # PATCH 441: THE CFG'S OWN PREDICTION, which is `practice 0` / `clean` -- H3 is
    # the CONTROL (the at-rest save, loaded and jumped), and p435hop.cfg's
    # `FALSIFIED IF ... H3 is tainted` says a tainted H3 means the hop arms nothing
    # on this map, so H2 cannot show a launder either way.  This table used to carry
    # `practice 1, segmented` here -- the failed reading, entered as the expectation
    # -- so the arm printed all-ok with its control down, and "the hop does not
    # launder in bhop mode" was written up out of it and into BACKLOG.md.  It is
    # graded as predicted now, and verdict() below says NOT DEMONSTRATED instead.
    "H3": {"practice": "0", "class": "clean"},
}
# H2/M1 are the measurements, not predictions: both answers are pre-registered in
# the cfg headers and which one lands decides whether Patch 435 is complete.  They
# are reported here and then RESOLVED by verdict(), which is the only place either
# arm produces a conclusion.
REPORT_SHIP = {"H2": ("practice", "class", "armzone", "state", "horizontal")}
# --mode forces sv_gamemode surf, so the observable that the mode TOOK is the
# start rule in `cmd timer`'s first line.
EXPECT_MODE = {"M0": {"startrule": "start on leave"},
               # ML is the lift proof: the placed body sits at 64.0312, 5e-5 below
               # its zone's bottom, so an airborne z above 64.03125 is what makes
               # the point test see an entry edge at all.
               "ML": {"z": "lifted"},
               "M2": {"practice": "0", "class": "clean"}}
REPORT_MODE = {"ML": ("horizontal",),
               "M1": ("practice", "class", "armzone", "state", "horizontal")}

# bhop_eazy's start slab bottom, which state.txt's `origin %.4f` puts the placed
# body 5e-5 below (64.0312 against 64.03125).
SLAB_BOTTOM = 64.03125

ARMS = {
    "pre": ("cfg/test/p435pre.cfg", "p435pre.log", True, EXPECT, {}),
    "shipped": ("cfg/test/p435hop.cfg", "p435hop.log", False, EXPECT_SHIP, REPORT_SHIP),
    "mode": ("cfg/test/p435mode.cfg", "p435mode.log", False, EXPECT_MODE, REPORT_MODE),
}


def grade(log, control, arm="pre"):
    ok = True
    s = sections(log)
    cfgname, logname, zones, expect, report = ARMS[arm]
    want = {k: dict(v) for k, v in expect.items()}
    if arm == "pre" and control:
        for tag, over in CONTROL.items():
            want[tag] = dict(want[tag], **over)
    print("observables (%s), %s predictions:"
          % (os.path.basename(log), "PRE-FIX" if control and arm == "pre" else "POST-FIX"))
    for tag in sorted(set(list(want) + list(report))):
        txt = s.get(tag)
        if txt is None:
            print("  %-4s SECTION ABSENT -- the cfg never reached it" % tag)
            ok = False
            continue
        pairs = list(want.get(tag, {}).items())
        pairs += [(k, None) for k in report.get(tag, ())
                  if k not in want.get(tag, {})]
        for key, exp in pairs:
            # The last occurrence in the section: a section that prints the body
            # twice (airborne, then landed) is graded on the read that matters,
            # and a control that must not match anything is graded on its only
            # chance to.
            got = get(txt, key, -1)
            if exp is None:
                print("  %-4s %-11s %-24s reported" % (tag, key, got))
                continue
            if exp == "lifted":
                # The subject must have left the floor, or M1's verdict is "the
                # hop never happened" rather than an answer about the launder.
                try:
                    good = float(got) > SLAB_BOTTOM
                except ValueError:
                    good = False
                exp = "above the slab bottom %g" % SLAB_BOTTOM
            elif exp == "bled":
                # The row's 250 u/s, bled by ground friction since the release
                # (147 measured at 120 ms).  C1 is the arm that quotes it exactly.
                try:
                    good = 50 < float(got) < 250
                except ValueError:
                    good = False
                exp = "50..250, the row's speed bled by friction"
            elif key == "horizontal":
                try:
                    good = abs(float(got) - exp) < 1.0
                except ValueError:
                    good = False
            else:
                good = (got == exp)
            ok = ok and good
            print("  %-4s %-11s %-24s %s"
                  % (tag, key, got, "ok" if good else "MISMATCH, want %s" % exp))
    return verdict(arm, s, ok)


def verdict(arm, s, ok):
    """THE THIRD ANSWER, for the two arms that have one.

    `shipped` and `mode` each pre-register BOTH of their subject's possible
    readings, so the subject cannot be graded against one of them -- and each has a
    control whose failure means the subject measured nothing at all.  That is three
    outcomes, and a driver with two exit states had to mislabel one of them: it
    graded the control against the reading that falsifies the arm and reported the
    subject without a verdict (Patch 441).  So the conclusion is drawn here, once,
    and "the control failed" is one of the things it can say."""
    if arm == "shipped":
        h2, h3 = s.get("H2"), s.get("H3")
        if h2 is None or h3 is None:
            print("VERDICT: NOT DEMONSTRATED -- H%s is absent from the log"
                  % ("2" if h2 is None else "3"))
            return False
        p3, c3 = get(h3, "practice", -1), get(h3, "class", -1)
        if (p3, c3) != ("0", "clean"):
            print("VERDICT: NOT DEMONSTRATED -- H3, the CONTROL, reads practice %s "
                  "class %s.  p435hop.cfg's own FALSIFIED IF: with H3 tainted the "
                  "hop arms nothing on this map, so H2 says nothing about a launder."
                  % (p3, c3))
            return False
        p2, c2 = get(h2, "practice", -1), get(h2, "class", -1)
        print("VERDICT: against a clean H3, the hop %s the load's taint in bhop mode "
              "(H2 practice %s, class %s)"
              % ("LAUNDERS" if p2 == "0" else "does NOT launder", p2, c2))
        return ok
    if arm == "mode":
        m1 = s.get("M1")
        if m1 is None:
            print("VERDICT: NOT DEMONSTRATED -- M1 is absent from the log")
            return False
        if not ok:
            print("VERDICT: NOT DEMONSTRATED -- a control in this arm MISMATCHED "
                  "above, so M1's reading is not about the launder")
            return False
        p1, c1 = get(m1, "practice", -1), get(m1, "class", -1)
        print("VERDICT: in surf mode the prespeed load + jump %s (M1 practice %s, "
              "class %s, arm zone %s)"
              % ("ARMS CLEAN -- the launder reproduces" if p1 == "0"
                 else "stays tainted", p1, c1, get(m1, "armzone", -1)))
        return ok
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions (the --arm pre table)")
    ap.add_argument("--arm", choices=sorted(ARMS), default="pre",
                    help="pre: the lowered start region, gate fires (the fix). "
                         "shipped: bhop_eazy's own zones, gate cannot fire, hop "
                         "measured in bhop mode. mode: the same, sv_gamemode surf.")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--grade-only", action="store_true",
                    help="grade the log already on disk; stage and run nothing")
    a = ap.parse_args()

    cfg, logname, zones, _, _ = ARMS[a.arm]
    log = os.path.join(GAMEDIR, "logs", logname)
    if a.grade_only:
        if not os.path.exists(log):
            raise SystemExit("no log at %s" % log)
        return 0 if grade(log, a.control, a.arm) else 1

    for _, src in SAVES_STAGED:
        if not os.path.exists(os.path.join(CFGDIR, src)):
            raise SystemExit("no fixture: %s" % src)
    stage(zones)
    try:
        secs = run(a.exe, a.timeout, cfg, log,
                   ["+set", "sv_gamemode", "surf"] if a.arm == "mode" else [])
    finally:
        restore(a.keep)
    print("ran %s (%s) for %.0f s" % (a.exe, cfg, secs))
    if not os.path.exists(log):
        raise SystemExit("no log at %s -- was the cwd C:\\FTESurf?" % log)
    return 0 if grade(log, a.control, a.arm) else 1


if __name__ == "__main__":
    sys.exit(main())
