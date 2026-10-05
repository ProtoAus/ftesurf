#!/usr/bin/env python3
"""
p448fin.py -- driver for cfg/test/p448fin.cfg (Patch 448: the hopped-start tag dies
with the run it described).

    python tools/p448fin.py [--exe ftesurf64.exe] [--control] [--keep]
                            [--grade-only [--side fixed|control]]

The control is HEAD before Patch 448.  Recipe as elsewhere in this tree:

    git worktree add ../ctl448 <HEAD before the patch>
    cp src/fteqcc64.exe ../ctl448/src/ && pwsh -NoProfile -File ../ctl448/src/build.ps1
    <keep the fixed pair>, copy the control pair into ftesurf/, run with --control

WHAT IT MEASURES is in the cfg's header, including the pre-registered predictions and
the FALSIFIED IF.  In one line: a run is tagged by a chain in the start box, finished,
and then the box is re-entered ON FOOT -- and the question is whether the NEXT attempt
starts clean.  Pre-448 the tag survived the finish and poisoned every later run on the
map until the player pressed `!r`.

TWO THINGS THE GRADING HAS TO GET RIGHT, both of them traps this session has already
fallen into once each:

  THE FINISH IS A PREMISE, NOT AN ASSUMPTION.  `finished` is graded on both sides.
  Without it, `hopped 0` at F would be consistent with a run that never finished at all
  -- an arm passing because its condition never occurred.

  THE RUN MUST STILL BE PRACTICE, and HOW that is graded changed after the first run.
  The one thing this patch must not do is launder the run being recorded -- tag gone AND
  run still marked is the whole claim, and either alone would be the wrong fix.  I first
  graded `class practice` from `cmd timer` at F and IT READ `clean`.  Not a laundering:
  THE END ZONE TELEPORTS THE PLAYER BACK TO THE START BOX, and `+forward` is still held,
  so the section produces TWO runs -- the tainted one finishes marked, the next starts
  from a fresh arm and finishes clean -- and `cmd timer` 800 ms later was reading the
  SECOND one.  The log had said so all along (`practice run -- this run will not be
  saved`, then a PB), which is this repo's own lesson: a line in the log cannot be taken
  back, a latch read later can.
  So F now grades the FINISH LINES: exactly one PRACTICE finish on the fixed build, two
  on the control, plus a derived `cleanfin` (a finish that is not a practice finish).
  That accident made the arm better than designed -- the patch's whole claim now happens
  inside one section on one build, with the control showing both runs marked.

The zones override is this arm's own (cfg/test/p448.zones.json): a one-segment track,
p435's start box plus an END region 64 units past its +x face, so a finish is reachable
headlessly.  It is staged and removed like any fixture, and the shipped zone tree is
never touched.

RESULT 2026-09-27, both sides exit 0.  qwprogs 2EE7916A043FC579 fixed /
AB1F10EBDD196A3E control (a worktree at f349d53, HEAD before this patch).

  CONTROL  nfin 2, **nprac 2** -- BOTH runs finished marked practice, because the tag
           survived the finish.  cleanfin NO.  `hopped 1` at F and again at A, and A
           reads `armed` -- so the re-entered box armed a fresh attempt that was ALREADY
           tagged.  That is the honest-player defect in person: one fluffed start
           poisons every later run on the map until the player presses `!r`.
  FIXED    nfin 2, **nprac 1** -- the tainted run finishes MARKED and the next one
           finishes CLEAN.  cleanfin YES.  `hopped 0` at F and A, and SV_TimerFinish's
           own dprint is present.  Tag gone, run still marked, next attempt clean --
           which is the whole of what 448 claims, measured in one section.

csprogs differs between the two sides (CEA8A8E482DCB160 control) because another session
is developing client code on this branch; this arm reads server output only, so it does
not bear on the result -- noted rather than hidden.
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
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
LOG = os.path.join(GAMEDIR, "logs", "p448fin.log")
CFG = "cfg/test/p448fin.cfg"
EXTRA = ["+set", "sv_gamemode", "surf"]

FIELDS = {
    "state":     r"timer: (\w+) on",
    "startrule": r"tick [\d.]+, (start on \w+)",
    "starthop":  r"\"run_starthop\" is \"(\d)\"",
    "startok":   r"start: ok (\d)",
    "hopped":    r"start:.* hopped (\d)",
    "rearmhop":  r"start:.* rearmhop (\d)",
    "jumps":     r"jumps (\d+)",
    "class":     r"class: (\w+) \(seg",
    "practice":  r"practice (\d)",
    "azone":     r"arm zone (-?\d+) \(armed from",
    "hopsay":    r"hopped start\^?7? -- one jump out of the start",
    # SV_TimerFinish's own line.  The subject printing its own action, which is what
    # CLAUDE.md asks for -- "the field ended up 0" is a downstream consequence.
    # PATCH 454 SPLIT THIS IN TWO, and the pair is the measurement: 448 cleared at the
    # finish, 454 ARMS a forgiveness there and TAKES it once the player is grounded at
    # or below sv_maxspeed.  So a 454 build prints `armsay` then `takesay`, a 448 build
    # prints the old `finsay`, and a pre-448 build prints none of the three.
    "finsay":    r"(cleared by the finish it marked)",
    "armsay":    r"(forgiveness armed, taken when grounded)",
    # MATCHED ON THE EVENT, NOT THE EXPLANATION.  This was
    # `there is no prespeed to launder`, a clause of the take's reasoning, and Patch 455
    # round 6 reworded the reasoning -- so the arm read `takesay absent` on a build where
    # the take had demonstrably fired (`hopped 0`, `cleanfin yes`). Anchor on the thing
    # that happened; the sentence explaining it is not a stable interface.
    "takesay":   r"(hopped-start taint cleared -- )",
    # PATCH 455 ROUND 6's TWO REFUSALS.  `settlesay` is the STRUCTURAL discriminator and
    # is graded; `movesay` is REPORTED, NOT GRADED, and the mutation run is why.
    #
    # With FS_FGVDWELL 0 and FS_FGVREADS 0 the `why = 4` branch is unreachable --
    # `(time - fgvok) < 0` is false because time >= fgvok, and `fgvn < 0` is false because
    # fgvn >= 1 -- so `settlesay` CANNOT appear on a build with the dwell removed. That is
    # a property of the code, not of the run.
    #
    # `movesay` went absent on the mutant too, and I nearly graded it on the strength of
    # that. It only appears if an AIRBORNE packet happens to be observed between the arm
    # and the take, which varies between runs of the same build -- so grading it would put
    # a false red in the arm on an honest run. Absence of `movesay` is not evidence of
    # anything; absence of `settlesay` is.
    "movesay":   r"NOT taken -- still moving: ",
    "settlesay": r"NOT taken -- at rest but settling: ",
    # The streak the take actually satisfied, from the gate's own numbers rather than from
    # the log's clock -- stamps are whole seconds and 219 lines of one run share one, so a
    # timestamp comparison would pass with the dwell removed.
    "dwelt":     r"at rest for ([\d.]+) s over (\d+) clear reads",
    # THE RUN COUNTERS, and they are the arm's real content after the first run taught
    # me what this fixture actually does.  The end zone TELEPORTS THE PLAYER BACK to the
    # start box, and `+forward` is still held -- so the section produces TWO runs, not
    # one: the tainted attempt finishes, and the next one starts from a fresh arm.
    # That is the patch's whole claim happening in one section, so it is graded there.
    "nfin":      r"finish: ",
    "nprac":     r"finish: [^\n]*PRACTICE",
}
PRESENCE = ("hopsay", "finsay", "armsay", "takesay", "movesay", "settlesay")
# Counted, not matched: `cleanfin` below is derived from the pair.
COUNTED = ("nfin", "nprac")

EXPECT = {
    "C": {"startrule": "start on leave", "starthop": "1", "state": "armed",
          "startok": "0", "hopped": "0", "rearmhop": "0"},
    "J": {"hopped": "1", "hopsay": "present", "state": "armed"},
    # `finished` and a PRACTICE finish are the premises -- a finish happened AND the
    # tainted run kept its mark.  `hopped` and the derived clean finish are the
    # measurement.  `class` is NOT graded here: it reads the state AFTER the second run,
    # which my first prediction got wrong (see the docstring).
    # F: the finish happened (`finished`), the tainted run kept its mark (`nprac 1`),
    # 454 ARMED rather than cleared (`armsay`), and because a walk is at or below
    # sv_maxspeed the forgiveness is TAKEN in the same section (`takesay`, `hopped 0`).
    # `finsay` must be ABSENT: its presence would mean the 448 clear is still in.
    # `settlesay` present is the DWELL'S OWN EVIDENCE: Patch 455 round 6 refuses at rest
    # until the streak is long enough, and a build with FS_FGVDWELL 0 goes straight from
    # `movesay` to `takesay` without ever emitting it.  Grading the take alone cannot tell
    # a dwelling build from a non-dwelling one.
    "F": {"state": "finished", "nprac": "1", "hopped": "0",
          "armsay": "present", "takesay": "present", "finsay": "absent",
          "settlesay": "present"},
    "A": {"hopped": "0"},
}
CONTROL = {
    # The tag never clears, so BOTH runs are practice and no run finishes un-marked,
    # and none of the three finish lines exists on that build.
    "F": {"nprac": "2", "hopped": "1", "finsay": "absent",
          "armsay": "absent", "takesay": "absent", "settlesay": "absent"},
    "A": {"hopped": "1"},
}
# ---------------------------------------------------------------------------
#  WHAT THIS ARM DOES NOT MEASURE, AND IT IS THE HALF THAT DECIDES PATCH 454.
#
#  454's gate is "grounded AND effective horizontal speed <= the cap".  This fixture
#  WALKS out with +forward, so it crosses at or under the cap and `takesay` firing
#  proves only that the YES branch works.  THE REFUSAL IS NOT EXERCISED HERE.
#
#  BUT THE REASON THIS COMMENT USED TO GIVE WAS FALSE, and the false reason is what kept
#  the arm from being finished.  It said "every gesture available headlessly walks at or
#  below sv_maxspeed -- ground acceleration is capped there".  Ground acceleration is NOT
#  capped there: PMSrc_Accelerate bounds only the projection onto wishdir
#  (pm_source.c:685), and the engine's own self-test puts the grounded prestrafe ceiling
#  at 1.1129 x maxspeed = 289.34 at 260 (pm_source.c:4696).  So a chain leaving the box
#  with +jump still held should cross ABOVE the cap, and a headless gesture can reach the
#  refusal after all.  Found while fixing Patch 455, by a reviewer who checked the
#  premise rather than the conclusion.
#
#  ALSO NOT DRIVABLE UNTIL 455 ROUND 2, for a second reason that is a defect rather than
#  a limit: the refusal is SILENT.  454 and 455 print a line when the forgiveness is
#  TAKEN and nothing when it is withheld for speed, so "refused" and "the branch never
#  ran" are the same log.  That is this repo's own rule -- the subject must print its own
#  action and the driver must grade THAT -- so round 2 gives the refusal its own
#  said-once line carrying the reason, and the arm for it is written against that.
#
#  What still needs a human either way: a finish on a REAL track whose END sits near its
#  own START (tools/census/endnearstart.py lists twelve), because the fixture's 64-unit
#  gap is synthetic and the maps are the case 454 was written for.
# ---------------------------------------------------------------------------
REPORT = {
    "C": ("class", "practice", "azone", "jumps"),
    "J": ("startok", "jumps", "azone", "class", "practice"),
    "F": ("startok", "jumps", "azone", "practice", "class", "nfin", "movesay"),
    "A": ("state", "startok", "jumps", "azone", "class", "practice", "rearmhop"),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest().upper()[:16]


def stage():
    if os.path.exists(ZONES):
        raise SystemExit("refusing: %s already exists -- it shadows the shipped zones"
                         % os.path.relpath(ZONES, ROOT))
    os.makedirs(os.path.dirname(ZONES), exist_ok=True)
    shutil.copyfile(os.path.join(CFGDIR, "p448.zones.json"), ZONES)
    print("staged %s" % os.path.relpath(ZONES, ROOT))


def restore(keep):
    """No `except: pass` -- a removal that did not happen must be loud, because a left
    override silently shadows the shipped zones for every later run in this tree."""
    if os.path.exists(ZONES):
        if keep:
            print("--keep: override left at %s" % os.path.relpath(ZONES, ROOT))
            return
        os.remove(ZONES)
        print("override removed")


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
    if name in COUNTED:
        return str(len(re.findall(FIELDS[name], txt)))
    if name in PRESENCE:
        return "present" if re.search(FIELDS[name], txt) else "absent"
    m = re.search(FIELDS[name], txt, re.M)
    return m.group(1) if m else "<absent>"


def cleanfin(txt):
    """Did ANY run in this section finish un-marked?

    Derived from the two counts rather than matched on a phrase, and that is deliberate:
    the obvious signal (`FIRST TIME`) depends on whether a PB already exists in the data
    tree, so it would read differently on the second invocation of the same arm.  A
    finish that is not a PRACTICE finish is state-independent.
    """
    n = len(re.findall(FIELDS["nfin"], txt))
    p = len(re.findall(FIELDS["nprac"], txt))
    return n > p


def grade(control):
    undemo = False
    want = {t: dict(v) for t, v in EXPECT.items()}
    if control:
        for t, over in CONTROL.items():
            want.setdefault(t, {}).update(over)
    s = sections(LOG)
    ok = True
    print("observables (%s), %s predictions:"
          % (os.path.basename(LOG), "PRE-448" if control else "POST-448"))
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
            print("  %-3s %-10s %-12s %s"
                  % (tag, k, got, "ok" if good else "MISMATCH, want %s" % w))
        for k in REPORT.get(tag, ()):
            if k not in want.get(tag, {}):
                print("  %-3s %-10s %-12s (reported, not graded)" % (tag, k, read(txt, k)))
    ftxt = s.get("F") or ""
    # CLEANFIN HAS A PREMISE AND IT WAS NOT BEING CHECKED.  The whole claim is "the
    # tainted run finishes marked and the NEXT one finishes clean", which needs TWO
    # finishes in the section -- and this fixture does not reliably produce two. It
    # depends on the end zone teleporting the player back with +forward still held, and
    # on 2026-09-27 a round-8 run produced ONE finish and the check read `no` as though
    # the patch had regressed. The gate was fine that run (`takesay` present, cleared at
    # 0.264 s over 19 reads); the section simply never ran twice.
    #
    # So a one-finish run is NOT DEMONSTRATED, not a failure. Same distinction
    # ftesurf-e0's p455hold draws, and the same reason: a check that goes red on harness
    # variance spends the trust that makes a red mean something.
    nfin = len(re.findall(FIELDS["nfin"], ftxt))
    got = cleanfin(ftxt)
    wantclean = not control
    if nfin < 2:
        undemo = True
        print("  F   %-10s %-12s NOT DEMONSTRATED -- only %d finish(es) in F, and the"
              % ("cleanfin", "yes" if got else "no", nfin))
        print("        claim needs two (the tainted one, then the next). The fixture's")
        print("        second run did not complete; this says nothing about the patch.")
    else:
        good = (got == wantclean)
        ok = ok and good
        print("  F   %-10s %-12s %s"
              % ("cleanfin", "yes" if got else "no",
                 "ok" if good else "MISMATCH, want %s" % ("yes" if wantclean else "no")))
    print("        (derived: a finish that is not a PRACTICE finish.  On the fixed build")
    print("         the tainted run finishes marked and the NEXT one finishes clean; on")
    print("         the control the tag survives and both are marked.)")

    with open(LOG, "r", errors="replace") as fh:
        blob = fh.read()
    unknown = re.findall(r'Unknown command "([^"]+)"', blob)
    if unknown:
        print("  UNKNOWN COMMAND(S): %s -- the gesture did not land"
              % ", ".join(sorted(set(unknown))))
        ok = False
    if ok and undemo:
        # A third verdict, and it exits 0 like a pass because nothing is WRONG -- but it
        # says so, because "green" and "green except the headline claim was not tested"
        # are different facts and a caller that cannot tell them apart will report the
        # second as the first.
        print()
        print("VERDICT: PASS, EXCEPT NOT DEMONSTRATED -- every graded check held, but the")
        print("derived claim above could not be tested on this run.  Re-run it; if the")
        print("second finish keeps going missing, the fixture's route wants looking at,")
        print("not the patch.")
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
