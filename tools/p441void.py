#!/usr/bin/env python3
"""
p441void.py -- driver for cfg/test/p441void.cfg, p441fast.cfg, p441norec.cfg
(Patch 441: the run Patch 434 cancels must not come back armed and clean, and a
server that records nothing must not lose its runs).

WHY A DRIVER.  The subject is a save whose run.rec is MISSING and whose origin
must be INSIDE the start slab -- two things no cfg can make.  So this stages
cfg/test/p441rest.txt and p441fast.txt as data/saves/bhop_eazy/save901,902, and
for the two arming arms cfg/test/p435.zones.json as the local zones override
(bhop_eazy's shipped start slab has its bottom at the floor, and `origin %.4f`
puts a placed body 0.00005 below it, where no scan can see it -- p434rew measured
exactly that and so never reached this defect).

ftesurf/data/saves/bhop_eazy IS A SHARED FIXTURE (p415reset, p428hold, p434rew
and p435pre read it).  It is PARKED -- renamed, not copied -- for the run and
restored afterwards, including when the run throws.  The zones override is
REMOVED either way: left behind it shadows the shipped zones for every later run
on this map.  Pass --keep to leave the staged saves (never the zones).

    python tools/p441void.py --arm rest|fast|norec [--exe ftesurf64.exe]
                             [--control] [--grade-only] [--keep]

--control grades the PRE-fix predictions.  The control build is a worktree at the
commit before Patch 441, NOT `git checkout --` of one file (this tree holds more
than one patch at a time):

    git worktree add ../ctl441 <pre-441 commit>
    cp src/fteqcc64.exe ../ctl441/src/ && pwsh -NoProfile -File ../ctl441/src/build.ps1
    cp ftesurf/qwprogs.dat ftesurf/csprogs.dat /tmp/441fixed/   # keep the fixed pair
    cp ../ctl441/ftesurf/qwprogs.dat ../ctl441/ftesurf/csprogs.dat ftesurf/
    python tools/p441void.py --arm rest --control                # then copy back

This driver PRINTS THE SHA256 OF THE PROGS IT RAN so the two runs can be told
apart afterwards; a --control run whose qwprogs hash equals the fixed one's has
measured the same build twice and proves nothing.

Exit status 0 when every pre-registered prediction in the cfg's header held.

RESULT (2026-09-26, all three arms x both builds, exit 0 every time.  qwprogs
3786B7D1D3341D4B fixed / 830A76438E00EFA4 control, the control built in a
worktree at 3ab4195.)  Each cfg's header carries its own numbers; in one line:
the control build answered `armed / class: clean / practice 0` to a cancelled
run (rest), started a recorded clean run at the save's 400 u/s once the body left
the box (fast), and cancelled an honest run on a server with rec_enable 0
(norec).  The fixed build answered idle-with-the-latch-back, idle, and
running-uncancelled.  Two predictions of mine were falsified on the way and are
written up where they were made: 400 u/s does not coast out of a 196-unit box
against ground friction, and an uncancelled clock keeps counting (so norec's
clock is graded as an inequality).
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
PARK = SAVES + ".p441park"
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")

# slot -> the fixture staged into it.  All three, for every arm, so the row numbers
# are the same in every log (the sort is by `seq`): 1 = 901 at rest, 2 = 902 with
# 400 u/s, 3 = 903 with NO recording behind it (`reclines 0`).
SAVES_STAGED = (("save901", "p441rest.txt"), ("save902", "p441fast.txt"),
                ("save903", "p441none.txt"))

CANCEL = r"run cancelled \(the save's recording could not be restored\)"

# How each graded field is read out of one `==== TAG` section of the log.  One
# regex each, and every one of them is a line the SUBJECT printed about its own
# state -- `cmd timer`'s report, or the void's own cancel line.
FIELDS = {
    "state":     r"timer: (\w+) on",
    "clock":     r"\s(\d+:\d\d\.\d+)\s+pb",
    "practice":  r"practice (\d)",
    "recording": r"recording (\d)",
    "class":     r"class: (\w+)",
    "azone":     r"arm zone (-?\d+) \(armed from",
    "armedfrom": r"arm zone -?\d+ \(armed from (-?\d+)\)",
    "stopped":   r"stopped (\d)",
    "buffer":    r"recorder: buffer (-?\d+)",
    # WHICH ROW ACTUALLY LOADED.  `sl_goto <n>` CLAMPS (`if (n > cnt) n = cnt`,
    # sv_saveloc.qc:2276), so an arm that asks for row 2 and gets row 1 -- one
    # fixture missing, one scan short -- would grade every other field identically
    # and pass while measuring the other arm's case.  This is the slot id in the
    # load event the client read (cl_board.qc:1923), i.e. the one that landed.
    "evslot":    r"seq: event seq \d+ op \d+ id (\d+)",
    # The fixture's own row, out of `sl_list`: row 2 is the 400 u/s one, and the
    # list prints the speed, so "the save with speed" is checked and not assumed.
    "rowspeed":  r"slot 902(?:\s+-?\d+){3}\s+(\d+) u/s",
    # THE POSITIVE CONTROL FOR `cancel: absent`.  SV_TimerStitched prints this on
    # every completed load, before the rewind and whatever the void does, so it
    # fires on both builds -- which is what makes an ABSENT cancel line mean "no
    # void" rather than "the log stopped carrying server prints" or "the regex
    # stopped matching".  An absence is evidence only once something shows the
    # reader got that far.
    "stitched":  r"(segmented run -- this run will not be saved)",
}

# arm -> (cfg, log, stage the zones override, EXPECT post-fix, CONTROL overrides,
#         REPORT-only fields)
ARMS = {
    # `clock` and `stopped` are graded on the fixed build and DROPPED for the
    # control (the None below) because the control reads the same 0:05.000 and
    # `stopped 1` beside `timer: armed` -- they are the void's own doing on both
    # builds.  What discriminates the rest arm is `state` (idle vs armed) and
    # `armedfrom` (-1 vs 0); the cfg header says which is which.
    "rest": (
        "cfg/test/p441void.cfg", "p441void.log", True,
        {"C1": {"state": "running", "recording": "1"},
         "S":  {"cancel": "present", "stitched": "present", "evslot": "901",
                "state": "idle", "azone": "0",
                "armedfrom": "-1", "clock": "0:05.000", "stopped": "1"}},
        {"S":  {"cancel": "present", "state": "armed", "azone": "0",
                "armedfrom": "0", "class": "clean", "practice": "0",
                "clock": None, "stopped": None}},
        {"S": ("practice", "class", "recording")},
    ),
    "fast": (
        "cfg/test/p441fast.cfg", "p441fast.log", True,
        # C0 grades the FIXTURE: row 2 is the one carrying 400 u/s, read out of
        # `sl_list`.  S grades which row the load landed on.  Without those two the
        # arm could be measuring the at-rest save through a clamped `sl_goto`.
        {"C0": {"rowspeed": "400"},
         "C1": {"state": "running", "recording": "1"},
         "S":  {"cancel": "present", "stitched": "present", "evslot": "902",
                "state": "idle", "azone": "0"},
         "S2": {"state": "idle", "azone": "-1"}},
        {"S":  {"state": "armed", "class": "clean", "practice": "0"},
         "S2": {"state": "running", "class": "clean", "practice": "0",
                "azone": None}},
        {"S": ("class", "practice"), "S2": ("clock", "recording", "armedfrom")},
    ),
    "norec": (
        "cfg/test/p441norec.cfg", "p441norec.log", False,
        # Row 3 (slot 903) is the realistic shape of a save taken while nothing was
        # recording: `reclines 0`, which is what SV_RecWritePrefix writes with an
        # empty buffer.  The first cut of this arm used the 500-line fixture, which
        # no server with rec_enable 0 could ever have produced.
        # The clock is graded as an INEQUALITY: an uncancelled run keeps counting,
        # so the exact value is the driver's own latency.  5.000 is what a STOPPED
        # clock holds, which is what the control build answers with.
        {"C1": {"state": "running", "recording": "0"},
         "S":  {"cancel": "absent", "stitched": "present", "evslot": "903",
                "state": "running", "clock": ">5.0",
                "recording": "0", "class": "segmented", "practice": "1"}},
        {"S":  {"cancel": "present", "state": "idle", "stopped": "1",
                "clock": "=5.0", "class": None, "practice": None}},
        {"S": ("azone", "stopped")},
    ),
    # Round 2, and its control is Patch 441's OWN first commit (20f25a1), not a
    # pre-441 build: a pre-441 build voids here too, for the reason the cfg gives.
    "mid": (
        "cfg/test/p441mid.cfg", "p441mid.log", False,
        {"C1": {"state": "running", "recording": "1"},
         "C2": {"state": "running", "recording": "1"},
         "S":  {"cancel": "present", "stitched": "present", "evslot": "901",
                "state": "idle", "clock": "=5.0", "stopped": "1"}},
        {"S":  {"cancel": "absent", "state": "running", "clock": ">5.0",
                "buffer": "-1", "stopped": None}},
        {"S": ("buffer", "practice", "class")},
    ),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest().upper()[:16]


def stage(zones):
    if os.path.isdir(PARK):
        raise SystemExit("refusing: %s already exists (a previous run did not restore)" % PARK)
    if os.path.exists(ZONES):
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
    """No `except: pass` anywhere in here, on purpose: a removal that did not
    happen must be loud, not tidy."""
    if os.path.exists(ZONES):
        os.remove(ZONES)
    if keep:
        print("--keep: staged saves left at %s (the zones override is always removed)" % SAVES)
        return
    if os.path.isdir(SAVES):
        shutil.rmtree(SAVES)
    if os.path.isdir(PARK):
        os.rename(PARK, SAVES)


def run(exe, timeout, cfg, log):
    # The basedir is the cwd, so this must not inherit a shell left in ftesurf/.
    if os.path.exists(log):
        os.remove(log)
    flags = 0x08000000 if os.name == "nt" else 0     # CREATE_NO_WINDOW
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", cfg], cwd=ROOT, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


def sections(path):
    """{tag: text} from the cfg's own `==== TAG ` echoes, so an earlier arm's
    report cannot be read for a later one."""
    with open(path, "r", errors="replace") as fh:
        txt = fh.read()
    out, cur = {}, None
    for line in txt.splitlines():
        m = re.search(r"==== (\S+)\b", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def secs(v):
    """m:ss.mmm as seconds, or a plain number."""
    if ":" in v:
        mm, ss = v.split(":")
        return float(mm) * 60 + float(ss)
    return float(v)


def agrees(got, want):
    """`>N`, `<N`, `=N` compare NUMBERS -- a clock that is still running counts, so
    for it the prediction is an inequality and the exact value is this driver's own
    latency.  Anything else is an exact string match."""
    if want[:1] in "<>=":
        try:
            g, n = secs(got), float(want[1:])
        except ValueError:
            return False
        return g > n if want[0] == ">" else (g < n if want[0] == "<" else g == n)
    return got == want


PRESENCE = ("cancel", "stitched")     # graded present/absent, not by value


def read(txt, name):
    if name == "cancel":
        return "present" if re.search(CANCEL, txt) else "absent"
    if name in PRESENCE:
        return "present" if re.search(FIELDS[name], txt) else "absent"
    m = re.search(FIELDS[name], txt, re.M)
    return m.group(1) if m else "<absent>"


def grade(log, control, arm):
    ok = True
    _, _, _, expect, ctl, report = ARMS[arm]
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
            good = agrees(got, w)
            ok = ok and good
            print("  %-4s %-12s %-14s %s"
                  % (tag, k, got, "ok" if good else "MISMATCH, want %s" % w))
        for k in report.get(tag, ()):
            if k not in want.get(tag, {}):
                print("  %-4s %-12s %-14s (reported, not graded)" % (tag, k, read(txt, k)))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS), default="rest")
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--grade-only", action="store_true",
                    help="grade the log already on disk; stage and run nothing")
    a = ap.parse_args()

    cfg, logname, zones, _, _, _ = ARMS[a.arm]
    log = os.path.join(GAMEDIR, "logs", logname)

    if a.grade_only:
        if not os.path.exists(log):
            raise SystemExit("no log at %s" % log)
        return 0 if grade(log, a.control, a.arm) else 1

    for _, src in SAVES_STAGED:
        if not os.path.exists(os.path.join(CFGDIR, src)):
            raise SystemExit("no fixture: %s" % src)
    # Which build is about to run.  A --control run whose qwprogs hash matches the
    # fixed one's has measured the same bytes twice.
    for d in ("qwprogs.dat", "csprogs.dat"):
        print("%-12s %s" % (d, sha(os.path.join(GAMEDIR, d))))
    stage(zones)
    try:
        secs = run(a.exe, a.timeout, cfg, log)
        left = listing(SAVES)
    finally:
        restore(a.keep)
    print("ran %s on %s for %.0f s" % (a.exe, cfg, secs))
    print("the staged tree at exit (%d file(s)):" % len(left))
    for line in left:
        print(line)
    if not os.path.exists(log):
        raise SystemExit("no log at %s -- was the cwd C:\\FTESurf?" % log)
    return 0 if grade(log, a.control, a.arm) else 1


if __name__ == "__main__":
    sys.exit(main())
