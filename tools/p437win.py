#!/usr/bin/env python3
"""
p437win.py -- driver for cfg/test/p437win.cfg (Patch 437: the board line's stage
window is the replay's window).

WHY A DRIVER.  The arm needs a main-track board row that resolves to a recording
with `stage` records and NO `stagepost`, and surf_4am's own cheat.rec is exactly
that -- a real FTESURF-REC 4 file from data/runs, not a synthetic one.  The board
resolves a row by its ticks and its tag, so the driver copies cheat.rec to
main/0000437_p437win_run.rec (437 ticks, tag p437win), runs the cfg, grades the
two windows against each other, and removes the copy.  data/runs is a shared
fixture: the copy is removed even when the run throws.

    python tools/p437win.py [--exe ftesurf64.exe] [--pre 437|441] [--grade-only]

--pre says which PATCH the build under test predates, because this cfg now holds
arms from two of them: 437 moved the board line's window (W2/W5b) and 441 stopped
the line job from working inside the OPEN replay's event table and cut (W6).  A
single --control meant both at once and graded one arm against the wrong
generation; it survives as an alias for --pre 437.  Build a control in a worktree
at the commit before the patch (NOT `git checkout --` of one file: this tree holds
more than one patch at a time), copy its csprogs.dat in, and run with --pre.

Exit status 0 when every pre-registered prediction in the cfg header held.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = r"C:\FTESurf"
GAMEDIR = os.path.join(ROOT, "ftesurf")
MAPDIR = os.path.join(GAMEDIR, "data", "runs", "surf_4am", "main")
SRC = os.path.join(MAPDIR, "cheat.rec")
FIXTURE = os.path.join(MAPDIR, "0000437_p437win_run.rec")
# The stage-1 board row resolves its own directory, so the fixture goes there too.
STAGEDIR = os.path.join(GAMEDIR, "data", "runs", "surf_4am", "stage_1")
STAGEL = os.path.join(STAGEDIR, "0000483_p437win_pb.rec")
CFG = "cfg/test/p437win.cfg"
LOG = os.path.join(GAMEDIR, "logs", "p437win.log")

# cheat.rec's own `stage` records, ticks at tickrate 0.015.  A LOCAL board row's
# line leg is always 0 (cl_scores.qc), so the job reads the WHOLE file and
# Watch_LineJobWindow leaves the window alone -- which is why the deciding arm is
# the stage-1 leg's row and its line (W5b), where the two spellings differ.
TICK = 0.015
MAIN_B = 20264                         # the fixture's sample count, from `scores lines`
LEG1_A, LEG1_B = 0, 483                # the segment before `stage 1 483`
MAIN_W = (0.0, MAIN_B * TICK)                   # 0.0000..303.9600, leg 0, both
FIXED_W = (LEG1_A * TICK, LEG1_B * TICK)        # 0.0000..7.2450
# MEASURED, not predicted.  The job never reaches a usable `stage` pair: pass one
# reads at most WT_LJ_PASS1 (6000) lines a frame and its filter is the line's first
# BYTE, which every sample row fails, so on a 20290-sample file it stops at sample
# ~6000 with wt_lj_sa and wt_lj_sb BOTH -1 (printed: `win leg 1 fleg 0 pa -1 pb -1
# sa -1 sb 483 end 20290 tick 0`).  Its own fallback then gives -1..20290, which
# its `pb <= pa` test rejects -- `scores: no window for stage 1 in that run` -- and
# the line draws every sample.  So the control's reading is NOT a last-stage
# spelling, which is what this arm was written to compare; it is no window at all,
# and the fix reaches one through the event table pass one fills.
CONTROL_W = MAIN_W
# W5a, the stage-1 leg's OWN row, is graded as a fact and not a window: its tag is
# RT_LOBBY and Scores_LineKey returns "" for one, so the board answers "no
# recording behind that row" and builds nothing.  A local board can only line a
# non-lobby row, which is why the fixture is a copied `_pb`.
STAGE1_ROW = "no recording behind that row"


def stage():
    for d in (FIXTURE, STAGEL):
        if os.path.exists(d):
            raise SystemExit("refusing: %s already exists (a previous run did not "
                             "restore)" % d)
    if not os.path.exists(SRC):
        raise SystemExit("no source recording: %s" % SRC)
    shutil.copyfile(SRC, FIXTURE)
    shutil.copyfile(SRC, STAGEL)


def restore(keep):
    if keep:
        print("--keep: fixtures left at %s and %s" % (FIXTURE, STAGEL))
        return
    for d in (FIXTURE, STAGEL):
        if os.path.exists(d):
            os.remove(d)


def run(exe, timeout, lineleg=1):
    if os.path.exists(LOG):
        os.remove(LOG)
    # The cfg sets sb_ln_lineleg itself, after the map: a CSQC-registered cvar is
    # reset at registercvar, so a `+set` would be lost the moment CSQC loaded.
    extra = []
    flags = 0x08000000 if os.name == "nt" else 0     # CREATE_NO_WINDOW
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized"]
                         + extra + ["+exec", CFG], cwd=ROOT, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


def sections(path):
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines()
    out, cur = {}, None
    for line in lines:
        # Tags are one to four characters of any case (A1, ML2, W5a) and are
        # stopped by the space the echo has -- \b is no good here, because
        # "W5a row" has a word boundary after the W.
        m = re.search(r"(?:----|====) ([A-Za-z][A-Za-z0-9]{0,3}) ", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


WIN = re.compile(r"t (-?[\d.]+)\.\.(-?[\d.]+)")


def winof(txt):
    """The last `t a..b` in a section, as the two floats the report prints."""
    ms = WIN.findall(txt or "")
    return (ms[-1][0], ms[-1][1]) if ms else ("<absent>", "<absent>")


def statusof(txt):
    """(end, window, cut, view, events) out of one `replay status` block -- the five
    fields of the OPEN replay that a board line's job must not touch."""
    def f(pat):
        m = re.search(pat, txt or "")
        return m.group(1) if m else "<absent>"
    return (f(r"end (\d+)"),
            f(r"window stage (\S+  [\d.]+\.\.[\d.]+)"),
            f(r"cut (\d)"),
            f(r"view (-?[\d.]+\.\.-?[\d.]+)"),
            f(r"events (\d+)"))


def grade(log, pre, lineleg=1):
    """`pre` is the PATCH the build under this run predates: 437 (no line-job
    window at all), 441 (437's shared spelling, but the job works in the replay's
    own event table and cut), or 0 for the current build.  One flag could not say
    it -- W2/W5b moved in 437 and W6 moved in 441, so a --control meaning both
    graded one of the two against the wrong generation."""
    ok = True
    s = sections(log)
    control = (pre == 437)
    want = CONTROL_W if control else FIXED_W
    asked = lineleg or 0
    # sb_ln_lineleg is added to EVERY row's leg, so a main row asks for leg 1 of a
    # file whose own leg is 0 -- and Watch_LineJobWindow only cuts when they differ.
    main_w = want if asked == 1 else MAIN_W
    def say(label, got, exp, good=None):
        nonlocal ok
        if good is None:
            good = (got == exp)
        elif callable(good):
            good = good(got)
        ok = ok and good
        print("  %-42s %-22s %s" % (label, got,
                                     "ok" if good else "MISMATCH, want %s" % exp))

    print("observables (%s), %s predictions:"
          % (os.path.basename(log),
             "PRE-%d" % pre if pre else "POST-FIX"))
    w1 = s.get("W1", "")
    say("W1 the board resolved the fixture",
        "yes" if "0000437_p437win_run.rec" in w1 else "no", "yes")
    w2 = winof(s.get("W2"))
    say("W2 the main row's line (leg %d)" % asked, "%s..%s" % w2,
        "%.4f..%.4f" % main_w,
        lambda txt: w2[0] != "<absent>" and abs(float(w2[0]) - main_w[0]) < 1e-3
        and abs(float(w2[1]) - main_w[1]) < 0.4)
    w3 = s.get("W3", "")
    m = re.search(r"stage (\d+) window [\d.]+\.\.[\d.]+ s from -?[\d.]+ "
                  r"\(ticks (\d+)\.\.(\d+), (stage records|stagepost)\)", w3)
    if not m:
        say("W3 the replay's window line", "<absent>", "present", False)
    else:
        say("W3 the replay's ticks", "%s..%s" % (m.group(2), m.group(3)),
            "%d..%d" % (LEG1_A, LEG1_B))
        say("W3 the replay's source", m.group(4), "stage records")
        # The identity that makes the pair a comparison: both spellings multiply
        # the same ticks by the same `tickrate` header key.  It is graded at W5b,
        # because W2 is a MAIN row and reads the whole file on both builds.
    w5a = s.get("W5a", "")
    say("W5a stage-1 row 0 is an RT_LOBBY row",
        "yes" if STAGE1_ROW in w5a else "no", "yes")
    w5btxt = s.get("W5b", "")
    say("W5b the row resolved the fixture",
        "yes" if "0000483_p437win_pb.rec" in w5btxt else "no", "yes")
    w5b = winof(w5btxt)
    # Graded with a tick's slack: the builder's `t b` is the LAST KEPT SAMPLE's
    # time, which is one sample inside the window, while Watch_WindowFind's is the
    # boundary itself.  W3's own seconds and the builder's b differ by exactly that,
    # and the tick count is what is being compared.
    say("W5b the fixture's line window", "%s..%s" % w5b, "~%.4f..%.4f" % want,
        lambda txt: w5b[0] != "<absent>" and abs(float(w5b[0]) - want[0]) < 1e-3
        and abs(float(w5b[1]) - want[1]) < TICK)
    if m and w5b[0] != "<absent>" and not control:
        ra, rb = int(m.group(2)), int(m.group(3))
        say("W5b equals W3's ticks x tickrate",
            "%.4f..%.4f vs %.4f..%.4f" % (float(w5b[0]), float(w5b[1]),
                                           ra * TICK, rb * TICK), "equal",
            abs(float(w5b[0]) - ra * TICK) < 1e-3
            and abs(float(w5b[1]) - rb * TICK) < TICK)
    w4 = s.get("W4", "")
    m4 = re.search(r"ticks (\d+)\.\.(\d+)", w4)
    say("W4 the replay's window, asked twice",
        "%s..%s" % ((m4.group(1), m4.group(2)) if m4 else ("<absent>", "<absent>")),
        "%d..%d" % (LEG1_A, LEG1_B))
    # W6 (Patch 441): the OPEN replay's own state, before and after a line job is
    # started under it.  An IDENTITY, not a number -- the job reads another file and
    # must leave the replay alone.
    a, b = statusof(s.get("W6a")), statusof(s.get("W6b"))
    read = a[0] != "<absent>" and b[0] != "<absent>"
    if not read:
        say("W6 the replay's state, read twice", "<absent>", "two status blocks", False)
    elif pre == 441:
        say("W6 a line job under the open replay",
            "unchanged" if a == b else "CHANGED %s -> %s" % (a, b),
            "CHANGED (the wipe must reproduce)", a != b)
    else:
        say("W6 a line job under the open replay",
            "unchanged" if a == b else "CHANGED %s -> %s" % (a, b), "unchanged", a == b)
    txt = open(log, "r", errors="replace").read()
    # PATCH 441: `QC (error|Error)` matches nothing the engine prints -- 0 hits over
    # all 1550 logs in ftesurf/logs.  PR_StackTrace's frame line is what a QC fault
    # leaves (pr_exec.c:436), and it hits the 9 logs that hold one.
    fault = re.search(r"runaway loop error|PR_ExecuteProgram:|<NO STACK>|<NO FUNCTION>"
                      r"|[a-z_]+\.qc:[0-9]+: \w", txt)
    say("no QC fault", "yes" if not fault else "no: %s" % fault.group(0), "yes")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--pre", type=int, default=0, choices=(0, 437, 441),
                    help="the patch the build under test predates: 437 grades the "
                         "whole-file line, 441 grades W6's wipe")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions")
    ap.add_argument("--lineleg", type=int, default=1,
                    help="the leg the cfg's `set sb_ln_lineleg` asks the builder "
                         "for; the board itself always passes 0 for a local row, so "
                         "0 grades the whole-file reading both builds agree on")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--grade-only", action="store_true",
                    help="grade the log already on disk; stage and run nothing")
    a = ap.parse_args()
    pre = a.pre or (437 if a.control else 0)

    if a.grade_only:
        if not os.path.exists(LOG):
            raise SystemExit("no log at %s" % LOG)
        return 0 if grade(LOG, pre, a.lineleg) else 1

    stage()
    try:
        secs = run(a.exe, a.timeout, a.lineleg)
    finally:
        restore(a.keep)
    print("ran %s for %.0f s (sb_ln_lineleg %d)" % (a.exe, secs, a.lineleg))
    if not os.path.exists(LOG):
        raise SystemExit("no log at %s -- was the cwd C:\\FTESurf?" % LOG)
    return 0 if grade(LOG, pre, a.lineleg) else 1


if __name__ == "__main__":
    sys.exit(main())
