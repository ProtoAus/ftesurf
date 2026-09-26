#!/usr/bin/env python3
"""
p443start.py -- driver for cfg/test/p443hop.cfg and cfg/test/p443air.cfg
(Patch 443: a restored ARM is not a settled START, and "at rest" in a start box
also has to mean "standing on something").

TWO DEFECTS, TWO ARMS, ONE CONTROL BUILD.  Both fixes are new in Patch 443, so the
control for both arms is HEAD before it -- one worktree, not two:

    git worktree add ../ctl443 89f5f7a
    cp src/fteqcc64.exe ../ctl443/src/ && pwsh -NoProfile -File ../ctl443/src/build.ps1
    cp ftesurf/qwprogs.dat ftesurf/csprogs.dat <scratch>/443fixed/      # keep the fix
    cp ../ctl443/ftesurf/qwprogs.dat ../ctl443/ftesurf/csprogs.dat ftesurf/
    python tools/p443start.py --arm hop --control                       # then copy back

    python tools/p443start.py --arm hop|air [--exe ftesurf64.exe] [--control]
                              [--keep] [--grade-only [--side fixed|control]]

WHAT EACH ARM MEASURES is in its cfg's header, including the pre-registered
predictions and the FALSIFIED IF.  In one line each: `hop` retries from a clean
ARMED start and reads `start: ok`, which the restore used to set to 1 -- switching
the whole hop rule off for a rankable attempt; `air` loads a save taken 36 units
above the floor INSIDE the start slab, which used to arm clean and buy the fall.

THE POSITIVE CONTROL IS INSIDE THE ARM, in both of them, and it is the part
tools/p435pre.py --arm shipped did not have: `hop` reads `start: ok 0` on a FRESH
arm before it retries (so the field is not one that always reads 0), and `air` loads
a GROUNDED row on the same build in the same run (so a gate that never fires cannot
be mistaken for a gate that refused).

This driver PRINTS THE SHA256 OF THE PROGS IT RAN.  A --control run whose qwprogs
hash equals the fixed one's has measured the same build twice and proves nothing.

ftesurf/data/saves/bhop_eazy IS A SHARED FIXTURE (p415reset, p428hold, p434rew,
p435pre and p441void read it).  It is PARKED -- renamed, not copied -- for every arm
including `hop`, which stages nothing: `retry` writes its point into save000 under
that same root, so without the park the gesture would leave a directory in the
shared tree.  PARK is the ONE name tools/p435pre.py and tools/p441void.py use, so
two drivers interleaving is a loud refusal rather than a lost fixture.

Exit status 0 when every pre-registered prediction in the cfg's header held.

RESULT (2026-09-26, both arms, both sides, exit 0 every time; qwprogs
88E5939564887CAD fixed / 3096B6F5468BEE3A control, the latter byte-identical to the
pair deployed on the twelve lobbies).  Each cfg carries its own numbers; in one line,
the control side settled a start that had not happened (`start: ok 1` after a retry,
so an autohop chain in the start box went unjudged on a clean rankable attempt) and
armed a save taken 36 units above the floor as CLEAN.  Three predictions of mine were
falsified on the way and are written up in p443hop.cfg where they were made: three
taps 300 ms apart are LEGAL jumps rather than a chain, a held chain on bhop map rules
measures nothing because mode_bhop.cfg switches run_starthop off, and a ten-second
blind chain taints the CONTROL too through a mechanism the arm does not control --
that last one withdrew a whole section rather than being explained away.
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
SAVES = os.path.join(GAMEDIR, "data", "saves", "bhop_eazy")
PARK = SAVES + ".savepark"          # the shared park name; see the docstring
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")

# arm -> rows staged, in `seq` order, which is the order sl_goto counts in.  `hop`
# stages nothing and still parks.  p435rest.txt is REUSED rather than copied to a
# p443 name: it is exactly the grounded at-rest row this arm needs for its positive
# control, and a second copy of a fixture is a second thing to keep in step.
STAGED = {
    "air": (("save901", "p435rest.txt"), ("save904", "p443air.txt")),
    "hop": (),
}
ZONED = ("air",)                    # arms that need the start slab to be visible

# `hop` MUST NOT run on bhop map rules.  cfg/lobby/mode_bhop.cfg:131 sets
# run_starthop 0 -- hopping out of the start is the sport there -- and
# SV_TimerMapInit applies that file from the map's metadata on a listen server too,
# so the rule the patch restores is off by the operator's own decision.  The
# configuration where it is ON is the default (surf) ruleset, which is also
# leave-the-box rather than start-on-jump.  Same override tools/p435pre.py --arm mode
# uses, and the cfg grades `start on leave` and `starthop 1` to prove it took.
EXTRA = {"hop": ["+set", "sv_gamemode", "surf"]}

HOPSAY = r"hopped start\^?7? -- one jump out of the start"
REARMSAY = r"start re-armed\^?7? -- one jump out of the start"

# One regex each, and every one reads a line the SUBJECT printed about its own
# state: `cmd timer`'s report, SV_RetryApply's own last word, SL_RowGrounded's
# dprint, or SV_TimerClassSay's.
FIELDS = {
    "state":     r"timer: (\w+) on",
    # THE TWO PREMISES of the hop arm, both read in section C.  `startrule` is the
    # timer's own first line and says whether sv_gamemode surf took; `starthop` is the
    # engine echoing the cvar, because the rule being ON is a premise and a premise
    # that is assumed is how the second cut of this arm measured nothing.
    "startrule": r"tick [\d.]+, (start on \w+)",
    "starthop":  r"\"run_starthop\" is \"(\d)\"",
    # THE FIELD PATCH 443a WRITES.  `start: ok %g dwell ... hopped %g rearmhop %g`.
    "startok":   r"start: ok (\d)",
    "hopped":    r"start:.* hopped (\d)",
    "dwell":     r"start: ok \d dwell (\d+\.\d+)",
    "practice":  r"practice (\d)",
    # Anchored on `(seg`: bare `class: (\w+)` also matches `stage class:` two lines
    # down, and every graded section has both (p441void.py's own note).
    "class":     r"class: (\w+) \(seg",
    "azone":     r"arm zone (-?\d+) \(armed from",
    "armedfrom": r"arm zone -?\d+ \(armed from (-?\d+)\)",
    "ground":    r"phase: ground (\d+\.\d+)",
    "air":       r"phase: ground \d+\.\d+  air (\d+\.\d+)",
    # SL_RowGrounded's dprint, the subject's own verdict and the three numbers it
    # decided from.  The row index is NOT pinned in the pattern -- SL_Base is the
    # caller's block and a lobby's is not 0 -- so `row` is reported instead.
    "support":   r"save: row -?\d+ support (\d)",
    "row":       r"save: row (-?\d+) support",
    "solid":     r"support \d at z -?[\d.]+ \(solid (\d)",
    "frac":      r"\(solid \d frac ([\d.]+)",
    "nz":        r"frac [\d.]+ nz (-?[\d.]+)",
    "z":         r"support \d at z (-?[\d.]+)",
    # Which row actually loaded.  `sl_goto <n>` CLAMPS (`if (n > cnt) n = cnt` in
    # SV_SaveLocLoad), so an arm that asks for row 2 and gets row 1 would grade every
    # other field identically and pass while measuring the other row.  `op 2` is the
    # LOAD (cl_board.qc reads the event); a save would otherwise hand back its slot.
    "evslot":    r"seq: event seq \d+ op 2 id (\d+)",
    "retrysay":  r"retry.{0,4} -- (run restored at|back where you were)",
    "hopsay":    HOPSAY,
    "rearmsay":  REARMSAY,
    "stitched":  r"(segmented run -- this run will not be saved)",
}

PRESENCE = ("hopsay", "rearmsay", "stitched")

# arm -> (cfg, log, EXPECT post-fix, CONTROL overrides, REPORT-only fields)
ARMS = {
    "hop": (
        "cfg/test/p443hop.cfg", "p443hop.log",
        {"C":  {"startrule": "start on leave", "starthop": "1",
                "state": "armed", "startok": "0", "hopped": "0"},
         "S":  {"retrysay": "back where you were", "state": "armed",
                "startok": "0"},
         "J1": {"hopsay": "present", "hopped": "1", "state": "armed"},
         # The taint must be FORGIVABLE: the message is the discriminator, since the
         # field reads 0 on both builds once the re-arm has run (and on the control it
         # was never 1).  A `hopped 1` here on the fixed build is the patch having
         # made a permanent accusation, which is the cfg's FALSIFIED IF.
         "J2": {"rearmsay": "present", "hopped": "0", "state": "armed"}},
        {"S":  {"startok": "1"},
         "J1": {"hopsay": "absent", "hopped": "0"},
         "J2": {"rearmsay": "absent"}},
        {"C":  ("dwell", "ground", "class", "practice"),
         "S":  ("azone", "armedfrom", "hopped", "ground", "class", "practice"),
         "J1": ("startok", "ground", "air", "azone", "class", "practice"),
         "J2": ("startok", "ground", "air", "azone", "class", "practice")},
    ),
    "air": (
        "cfg/test/p443air.cfg", "p443air.log",
        {"S": {"evslot": "904", "support": "0", "solid": "0", "frac": "1.000",
               "state": "armed", "azone": "0", "armedfrom": "0",
               "class": "segmented", "practice": "1"},
         "P": {"evslot": "901", "support": "1", "class": "clean",
               "practice": "0"}},
        # The control has no SL_RowGrounded at all, so every field that reads its
        # dprint is dropped there rather than predicted -- and `support` being
        # absent is itself the proof the two logs came from different progs.
        {"S": {"support": None, "solid": None, "frac": None,
               "class": "clean", "practice": "0"},
         "P": {"support": None}},
        {"S": ("row", "z", "nz", "stitched", "azone", "armedfrom", "startok"),
         "P": ("row", "z", "nz", "solid", "frac", "azone", "armedfrom",
               "support", "state")},
    ),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest().upper()[:16]


def stage(arm):
    if os.path.isdir(PARK):
        raise SystemExit("refusing: %s already exists (a previous run did not restore)" % PARK)
    if os.path.exists(ZONES):
        raise SystemExit("refusing: %s already exists -- it shadows the shipped zones" % ZONES)
    if os.path.isdir(SAVES):
        os.rename(SAVES, PARK)
    for slot, src in STAGED[arm]:
        d = os.path.join(SAVES, slot)
        os.makedirs(d)
        shutil.copyfile(os.path.join(CFGDIR, src), os.path.join(d, "state.txt"))
    if arm in ZONED:
        os.makedirs(os.path.dirname(ZONES), exist_ok=True)
        shutil.copyfile(os.path.join(CFGDIR, "p435.zones.json"), ZONES)


def listing(where):
    """What the run left behind.  A cleanup written from an assumption is how two
    leaks survived a green run (CLAUDE.md), so the tree is printed, not assumed."""
    out = []
    for dirpath, dirnames, files in os.walk(where):
        dirnames.sort()
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            out.append("    %s  %d bytes" % (os.path.relpath(p, ROOT), os.path.getsize(p)))
    return out


def restore(keep):
    """No `except: pass` anywhere in here, on purpose: a removal that did not happen
    must be loud, not tidy.  And --keep keeps a COPY -- the real tree always goes
    back, because leaving these fixtures in place would have the next p435pre or
    p441void run park THEM as if they were the shared fixture."""
    if os.path.exists(ZONES):
        os.remove(ZONES)
    if keep and os.path.isdir(SAVES):
        kept = SAVES + ".kept.p443"
        if os.path.isdir(kept):
            shutil.rmtree(kept)
        shutil.copytree(SAVES, kept)
        print("--keep: staged copy at %s (the real tree is restored below)"
              % os.path.relpath(kept, ROOT))
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
    """{tag: text} from the cfg's own `==== TAG ` echoes, so an earlier arm's report
    cannot be read for a later one.  `---- ` lines are DROPPED: p441void.cfg's own
    reminder line satisfied a graded field once, and an echo is never a measurement."""
    with open(path, "r", errors="replace") as fh:
        txt = fh.read()
    out, cur = {}, None
    for line in txt.splitlines():
        m = re.search(r"==== (\S+)\b", line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        if "---- " in line:
            continue
        if cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def read(txt, name):
    """THE FIRST match (re.search).  Every pattern above is anchored rather than
    relying on that, because a convention holding a field up is how `class:` came to
    match `stage class:`."""
    if name in PRESENCE:
        return "present" if re.search(FIELDS[name], txt) else "absent"
    m = re.search(FIELDS[name], txt, re.M)
    return m.group(1) if m else "<absent>"


def grade(log, control, arm):
    ok = True
    _, _, expect, ctl, report = ARMS[arm]
    want = {t: dict(v) for t, v in expect.items()}
    if control:
        for t, over in ctl.items():
            want.setdefault(t, {})
            for k, v in over.items():
                if v is None:
                    want[t].pop(k, None)      # not predicted for this build
                else:
                    want[t][k] = v
    s = sections(log)
    print("observables (%s), %s predictions:"
          % (os.path.basename(log), "PRE-FIX" if control else "POST-FIX"))
    for tag in sorted(set(list(want) + list(report))):
        txt = s.get(tag)
        if txt is None:
            print("  %-4s SECTION ABSENT -- the cfg never reached it" % tag)
            ok = False
            continue
        for k in sorted(want.get(tag, {})):
            got, w = read(txt, k), want[tag][k]
            good = (got == w)
            ok = ok and good
            print("  %-4s %-10s %-14s %s"
                  % (tag, k, got, "ok" if good else "MISMATCH, want %s" % w))
        for k in report.get(tag, ()):
            if k not in want.get(tag, {}):
                print("  %-4s %-10s %-14s (reported, not graded)" % (tag, k, read(txt, k)))
    # A COMMAND THE ENGINE DID NOT RECOGNISE FAILS THE RUN, whatever the fields say.
    # `sl_goto` without the `cmd` prefix is not a client command, and the first cut of
    # p443air.cfg sent it bare: every field downstream read `<absent>`, which is a
    # MISMATCH here but would be a PASS in any arm whose predictions happen to be
    # absences.  p441pi.cfg grades this by hand; it belongs in the driver.
    with open(log, "r", errors="replace") as fh:
        unknown = re.findall(r'Unknown command "([^"]+)"', fh.read())
    if unknown:
        print("  UNKNOWN COMMAND(S) in the log: %s -- the gesture did not land"
              % ", ".join(sorted(set(unknown))))
        ok = False

    # THE CONTROL MUST NOT CARRY THE FIX'S OWN LINE.  SL_RowGrounded does not exist
    # on the pre-443 build, so a --control log containing its dprint is a log written
    # by the wrong progs -- the one failure the hashes are also there to catch, said
    # twice because copying a .dat back is a manual step.
    if control:
        with open(log, "r", errors="replace") as fh:
            if re.search(r"save: row -?\d+ support", fh.read()):
                print("  THE CONTROL LOG CONTAINS SL_RowGrounded's dprint -- it was"
                      " written by a build that HAS the fix")
                ok = False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS), default="hop")
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--side", choices=("fixed", "control"), default=None,
                    help="with --grade-only, read <log>.fixed or <log>.control")
    ap.add_argument("--grade-only", action="store_true",
                    help="grade the log already on disk; stage and run nothing")
    a = ap.parse_args()

    cfg, logname, _, _, _ = ARMS[a.arm]
    log = os.path.join(GAMEDIR, "logs", logname)

    if a.grade_only:
        if a.side:
            log = log + "." + a.side
        if not os.path.exists(log):
            raise SystemExit("no log at %s" % log)
        return 0 if grade(log, a.control, a.arm) else 1

    for _, src in STAGED[a.arm]:
        if not os.path.exists(os.path.join(CFGDIR, src)):
            raise SystemExit("no fixture: %s" % src)
    # Which build is about to run, taken ONCE and before it does: this repo has more
    # than one live session, so reading the .dat after the run could name a build
    # that did not write the log.
    ran = [(d, sha(os.path.join(GAMEDIR, d))) for d in ("qwprogs.dat", "csprogs.dat")]
    for d, h in ran:
        print("%-12s %s" % (d, h))
    cleanup_ok = True
    stage(a.arm)
    try:
        secs = run(a.exe, a.timeout, cfg, log, EXTRA.get(a.arm, ()))
        left = listing(SAVES)
    finally:
        # LOUD, BUT NOT MASKING: a raise from restore() inside `finally` would
        # replace whatever run() raised, which is how a cleanup failure hides the
        # fault that caused it.
        try:
            restore(a.keep)
        except OSError as exc:
            cleanup_ok = False
            print("CLEANUP FAILED, the shared fixture may still be parked at %s: %s"
                  % (os.path.relpath(PARK, ROOT), exc))
    print("ran %s on %s for %.0f s" % (a.exe, cfg, secs))
    print("the staged tree at exit (%d file(s)):" % len(left))
    for line in left:
        print(line)
    good = grade(log, a.control, a.arm)
    side = "control" if a.control else "fixed"
    shutil.copyfile(log, log + "." + side)
    with open(log + "." + side + ".hash", "w") as fh:
        for d, h in ran:
            fh.write("%s %s\n" % (d, h))
    print("kept %s and its .hash" % os.path.relpath(log + "." + side, ROOT))
    return 0 if (good and cleanup_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
