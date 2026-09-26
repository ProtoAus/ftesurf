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

    python tools/p441void.py --arm rest|fast|norec|twice|mid|retry
                             [--exe ftesurf64.exe] [--control] [--keep]
                             [--grade-only [--side fixed|control]]

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

RESULT (2026-09-26, round 4: six arms here plus p442jump in p435pre.py, both sides
each, exit 0 every time.  The fixed
build is qwprogs 3096B6F5468BEE3A; the control is a DIFFERENT build per arm, which
is the point -- 830A76438E00EFA4 (pre-441, 3ab4195) for rest/fast/norec,
3786B7D1D3341D4B (441 as first committed) for mid, and 8B84B5CE71C058E8 (this tree
with the predicate cut to `hadrec` alone) for twice, and 63AF428049260231 (441 round
3, the cut that stopped covering the retry path) for retry.  Both runs' logs are kept per
arm as <log>.fixed and <log>.control, with a .hash beside each naming the build
that wrote it, so every number in every RESULT block can be read back off disk --
in THIS working tree.  ftesurf/logs is gitignored (.gitignore:216), so a fresh
clone has the cfgs' quoted numbers and not the logs they came from; re-run both
sides to rebuild them.  Each cfg carries its own; in one line: the control side
answered `armed` to a cancelled run (rest), started a recorded clean run at the
save's 400 u/s (fast), cancelled honest runs under rec_enable 0 including an old
save that merely CLAIMED a recording (norec), let a RUNNING attempt carry on with
its recorder discarded (mid, and twice with the clause compiled out).  Predictions
of mine falsified along the way, each written up where it was made: 400 u/s does
not coast out of a 196-unit box against friction; an uncancelled clock keeps
counting; and `practice`/`class` do not discriminate the rest arm at all.
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
# ONE PARK NAME, SHARED WITH tools/p435pre.py ON PURPOSE.  Each driver used to
# park this shared directory under its own name and refuse only on its own, so
# interleaving the two rmtree'd the real fixture and put nothing back.  A single
# name turns that into a loud refusal.
PARK = SAVES + ".savepark"
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")

# slot -> the fixture staged into it.  All three, for every arm, so the row numbers
# are the same in every log (the sort is by `seq`): 1 = 901 at rest, 2 = 902 with
# 400 u/s, 3 = 903 with NO recording behind it (`reclines 0`).
SAVES_STAGED = (("save901", "p441rest.txt"), ("save902", "p441fast.txt"),
                ("save903", "p441none.txt"))

CANCEL = r"run cancelled \(the save's recording could not be restored\)"

# arm -> a path staged as a DIRECTORY so that a write to it must fail.  save000/run.rec
# is what SL_RecPath(FS_RETRY_SLOT) spells, so SV_RecWritePrefix's fopen(FILE_WRITE)
# cannot open it: the retry point gets `reclines 0` while the run keeps TF_RECORDING,
# which is the one state that tells `mark > 0` and `flg & TF_RECORDING` apart.
BLOCK = {"retryw": os.path.join("save000", "run.rec")}

# How each graded field is read out of one `==== TAG` section of the log.  One
# regex each, and every one of them is a line the SUBJECT printed about its own
# state -- `cmd timer`'s report, or the void's own cancel line.
FIELDS = {
    "state":     r"timer: (\w+) on",
    "clock":     r"\s(\d+:\d\d\.\d+)\s+pb",
    "practice":  r"practice (\d)",
    "recording": r"recording (\d)",
    # ANCHORED on `(seg`, as p435pre.py does: bare `class: (\w+)` also matches the
    # report's `stage class: stitch N` two lines down, and every graded section has
    # both.  It read correctly only because this driver takes the FIRST match and
    # the run class prints above the stage class -- a convention holding a field up.
    "class":     r"class: (\w+) \(seg",
    "azone":     r"arm zone (-?\d+) \(armed from",
    "armedfrom": r"arm zone -?\d+ \(armed from (-?\d+)\)",
    "stopped":   r"stopped (\d)",
    "buffer":    r"recorder: buffer (-?\d+)",
    # WHICH ROW ACTUALLY LOADED.  `sl_goto <n>` CLAMPS (`if (n > cnt) n = cnt` in
    # SV_SaveLocLoad -- cited by name because the line has moved twice under two
    # reviews), so an arm that asks for row 2 and gets row 1 -- one
    # fixture missing, one scan short -- would grade every other field identically
    # and pass while measuring the other arm's case.  This is the slot id in the
    # load event the client read (cl_board.qc:1923), i.e. the one that landed.
    # `op 2` is the LOAD; a section whose first event is a save (op 1) would
    # otherwise hand back the wrong slot.
    "evslot":    r"seq: event seq \d+ op 2 id (\d+)",
    # The fixture's own row, out of `sl_list`: row 2 is the 400 u/s one, and the
    # list prints the speed, so "the save with speed" is checked and not assumed.
    "rowspeed":  r"slot 902(?:\s+-?\d+){3}\s+(\d+) u/s",
    # THE POSITIVE CONTROL FOR `cancel: absent`, and exactly what it is worth --
    # the first draft of this comment overstated it.  The line comes from
    # SV_TimerClassSay (sv_timer.qc:8940) by way of SV_TimerPractice, behind two
    # guards: the run must be RUNNING, and the class must be an UPGRADE, so it
    # prints once.  It is therefore NOT unconditional and NOT independent of C1's
    # premise -- a second load, or a load into a run already announced segmented,
    # prints nothing and this reads `absent`.  It fails safe (an arm expecting
    # `present` goes red), and what it does buy is real: an absent CANCEL line
    # cannot be the log having stopped carrying server prints, because this came
    # through the same channel.
    "stitched":  r"(segmented run -- this run will not be saved)",
    # SV_RetryApply's own last word, and the only subject-printed line that says
    # which way the retry path went: `run restored at <clock>` when the restored
    # state is still RUNNING, `back where you were` when it is not.  It also proves
    # the retry LANDED, which `rec_retry 0` or a second player would prevent.
    "retrysay":  r"retry.{0,4} -- (run restored at|back where you were)",
    # SV_RecWritePrefix's own dprint when the prefix cannot be opened -- the subject
    # saying `mark` is 0, and for the reason p441retryw.cfg stages.  Without it that
    # arm would be measuring p441retry's case over again.
    "cannotwrite": r"(timer: cannot write .*run\.rec)",
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
                "recording": "0", "class": "segmented", "practice": "1"},
         # S2 is the OLD save (row 1, `reclines 500`) on the same no-recording
         # server.  Round 2's `mark > 0` cancelled here and not at S; round 3 asks
         # the server and the run, so both must read the same.  `stitched` is not
         # expected twice -- SV_TimerClassSay prints once per class upgrade.
         "S2": {"cancel": "absent", "evslot": "901", "state": "running",
                "clock": ">5.0", "recording": "0", "class": "segmented"}},
        {"S":  {"cancel": "present", "state": "idle", "stopped": "1",
                "clock": "=5.0", "class": None, "practice": None},
         "S2": {"cancel": "present", "state": "idle", "clock": "=5.0",
                "class": None}},
        {"S": ("azone", "stopped"), "S2": ("practice", "stopped")},
    ),
    # Round 3.  THE ARM FOR THE OTHER CLAUSE: the second load of one row, where the
    # first void has taken the recorder down (`hadrec` false) and only the server's
    # own answer is left.  Its control is the fix COMPILED OUT -- the predicate cut
    # to `hadrec` alone -- because no earlier commit isolates this.  Between this and
    # `mid`, clauses 1 and 2 are each shown to be load-bearing.  `retry` shows a third
    # clause is needed at all; `retryw` shows WHICH third clause, being the only arm
    # where `mark > 0` and `flg & TF_RECORDING` disagree.  Before them, a half could
    # have been deleted with every arm still green.
    "twice": (
        "cfg/test/p441twice.cfg", "p441twice.log", False,
        {"C1": {"state": "running", "recording": "1"},
         # S1's `recording 0` IS the premise of S2 -- it is what makes `hadrec`
         # false at the second load -- so it is graded rather than assumed, the way
         # p441mid.cfg grades its C2.  (It reads 0 on both builds: on the control
         # because the first void discarded too.  It is a premise, not a
         # discriminator, and the cfg says which fields are which.)
         "S1": {"cancel": "present", "state": "idle", "clock": "=5.0",
                "recording": "0"},
         "S2": {"cancel": "present", "state": "idle", "clock": "=5.0",
                "recording": "0", "evslot": "901"}},
        {"S2": {"cancel": "absent", "state": "running", "clock": ">5.0",
                "buffer": "-1"}},
        {"S1": ("buffer",), "S2": ("buffer", "practice", "class")},
    ),
    # Round 6.  WRITTEN TO TELL ROUND 4 AND ROUND 5 APART -- and it does not, which is
    # the finding.  The plan was a retry whose PREFIX WRITE FAILS with the recorder
    # live, giving `reclines 0` beside a flags word that still carries TF_RECORDING.
    # MEASURED INSTEAD: the write cannot be made to fail from QC.  PF_fopen allocates
    # a memory buffer for the write modes (engine pr_bgcmd.c, PF_fopen's FILE_WRITE
    # case) and the bytes go out at fclose, so `fopen` returns a handle even with a
    # DIRECTORY sitting on the path, SV_RecWritePrefix returns its line count, and
    # `reclines` is positive while no prefix file exists at all.  Both spellings
    # therefore void here.  What the arm does establish is that second fact, which is
    # worth having on its own: `reclines > 0` is not evidence the prefix is on disk.
    # `cannotwrite` is graded ABSENT for exactly that reason -- it is the dprint QC
    # would print if it could see the failure, and it cannot.
    "retryw": (
        "cfg/test/p441retryw.cfg", "p441retryw.log", False,
        {"C1": {"state": "running", "recording": "1"},
         "C2": {"state": "running", "recording": "1"},
         "S":  {"cannotwrite": "absent", "cancel": "present",
                "retrysay": "back where you were", "state": "idle"}},
        {"S":  {"cannotwrite": "absent", "cancel": "present",
                "retrysay": "back where you were", "state": "idle",
                "practice": None, "class": None}},
        {"S": ("clock", "practice", "class", "buffer")},
    ),
    # Round 4.  THE RETRY PATH, where the other two clauses are structurally blind:
    # map_restart re-initialises the progs (so `hadrec` is 0) and the operator has
    # just switched recording off (so SV_RecEnabled() is 0).  Its control is round 3
    # itself, 58ef286, which is the first cut that failed to void here.
    "retry": (
        "cfg/test/p441retry.cfg", "p441retry.log", False,
        {"C1": {"state": "running", "recording": "1"},
         "C2": {"state": "running", "recording": "1"},
         "S":  {"cancel": "present", "retrysay": "back where you were",
                "state": "idle"}},
        {"S":  {"cancel": "absent", "retrysay": "run restored at",
                "state": "running", "practice": "0", "class": "clean",
                "buffer": "-1"}},
        {"S": ("clock", "practice", "class", "buffer", "recording")},
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


def stage(zones, arm=""):
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
    if arm in BLOCK:
        os.makedirs(os.path.join(SAVES, BLOCK[arm]))
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
        # A COPY, and the real tree goes back.  `--keep` used to return here, which
        # left the shared fixture REPLACED by these fixtures and the real one parked:
        # p415reset, p428hold, p434rew and p435pre all read that directory, and the
        # next p435pre run would have parked p441's fixtures as if they were real.
        kept = SAVES + ".kept.p441"
        if os.path.isdir(kept):
            shutil.rmtree(kept)
        shutil.copytree(SAVES, kept)
        print("--keep: staged copy at %s (the real tree is restored below)"
              % os.path.relpath(kept, ROOT))
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
    report cannot be read for a later one.

    AND `---- ` ECHOES ARE DROPPED RATHER THAN APPENDED.  p441void.cfg's reminder
    line reads `---- CONTROL: armed, class clean, practice 0.  FIXED: idle, arm
    zone 0 ----`; it sits inside section S and BEFORE `cmd timer`'s report, so
    `practice (\\d)` matched the cfg's own words and the control table's graded
    `practice 0` was satisfied by the harness telling itself the answer.  An echo
    is never a measurement."""
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


PRESENCE = ("cancel", "stitched", "cannotwrite")     # graded present/absent, not by value


def read(txt, name):
    """THE FIRST match, always (re.search).  tools/p435pre.py takes the LAST, and
    both conventions are load-bearing where a pattern can hit twice -- which is why
    the patterns above are anchored rather than left to the convention."""
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
    # THE KEPT COPIES ARE RE-GRADABLE.  --grade-only only ever looked at the base
    # log name, so the .fixed/.control copies this driver writes could not be
    # re-read by the tool that wrote them -- an audit had to import the module.
    ap.add_argument("--side", choices=("fixed", "control"), default=None,
                    help="with --grade-only, read <log>.fixed or <log>.control")
    ap.add_argument("--grade-only", action="store_true",
                    help="grade the log already on disk; stage and run nothing")
    a = ap.parse_args()

    cfg, logname, zones, _, _, _ = ARMS[a.arm]
    log = os.path.join(GAMEDIR, "logs", logname)

    if a.grade_only:
        if a.side:
            log = log + "." + a.side
        if not os.path.exists(log):
            raise SystemExit("no log at %s" % log)
        return 0 if grade(log, a.control, a.arm) else 1

    for _, src in SAVES_STAGED:
        if not os.path.exists(os.path.join(CFGDIR, src)):
            raise SystemExit("no fixture: %s" % src)
    # Which build is about to run.  A --control run whose qwprogs hash matches the
    # fixed one's has measured the same bytes twice.  TAKEN ONCE, HERE: the sidecar
    # below used to re-read the files after the run, so a rebuild while the arm ran
    # (this repo has more than one live session) could have named a build that did
    # not write the log.
    ran = [(d, sha(os.path.join(GAMEDIR, d))) for d in ("qwprogs.dat", "csprogs.dat")]
    for d, h in ran:
        print("%-12s %s" % (d, h))
    cleanup_ok = True
    stage(zones, a.arm)
    try:
        secs = run(a.exe, a.timeout, cfg, log)
        left = listing(SAVES)
        # THE BLOCKER IS PART OF THE ARM.  If the run turned it into a file, the write
        # landed after all and everything the cfg concludes about `reclines` is wrong.
        if a.arm in BLOCK:
            b = os.path.join(SAVES, BLOCK[a.arm])
            blocked = os.path.isdir(b)
            print("the staged blocker at %s is still a directory: %s"
                  % (os.path.relpath(b, ROOT), blocked))
            if not blocked:
                cleanup_ok = False   # fails the run, like any other broken premise
    finally:
        # LOUD, BUT NOT MASKING.  A raise from restore() inside `finally` replaces
        # whatever run() raised, which is how a cleanup failure hides the fault that
        # caused it.  The print is the loud part CLAUDE.md asks for; the parked tree
        # is named so the next run's refusal is actionable.
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
    if not os.path.exists(log):
        raise SystemExit("no log at %s -- was the cwd C:\\FTESurf?" % log)
    # KEEP THE CONTROL RUN'S LOG.  One filename per arm, deleted at every run
    # start, meant the control numbers quoted in every RESULT block were
    # unverifiable from disk the moment the fixed side ran again (an audit of
    # these arms found that, and it was right).
    # BOTH SIDES SURVIVE.  Keeping only the control's copy was half a fix: the
    # control run then overwrote the FIXED log, so whichever side ran last was the
    # only one on disk and a RESULT block's other half could not be checked.
    side = ".control" if a.control else ".fixed"
    keep = log + side
    shutil.copyfile(log, keep)
    # AND THE BUILD'S IDENTITY BESIDE IT.  The hashes were printed to stdout only,
    # so the one number every RESULT block quotes -- which build wrote these lines --
    # was the one thing the kept logs could not check.
    with open(keep + ".hash", "w") as fh:
        for d, h in ran:
            fh.write("%-12s %s\n" % (d, h))
    print("%s log kept at %s (+ .hash)" % (side[1:], os.path.relpath(keep, ROOT)))
    # A CLEANUP FAILURE IS A FAILED RUN.  It used to print and exit 0, which leaves
    # the shared fixture replaced by these fixtures while the exit status says all is
    # well -- and only two of the five drivers that park that directory check for it.
    return 0 if (grade(log, a.control, a.arm) and cleanup_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
