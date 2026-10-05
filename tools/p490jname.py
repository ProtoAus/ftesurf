#!/usr/bin/env python3
"""p490jname.py -- drive and grade cfg/test/p490jname.cfg on ONE binary.

Patch 490.  `IN_JournalEnd_f` printed a name it had already lost: QC_FixFileName
returns either its argument (a Z_Malloc'd Cmd_Argv copy, stable) or
`va("data/%s", name)`, a pointer into the engine's rotating va() buffer, and
COM_WriteFile restarts the loader threads -- whose names come from va() -- before
the print runs.  A bare-name argument therefore printed `loadworker_3`.

RUN IT ON BOTH BINARIES.  The pre-490 one is the control and MUST fail arm 1:
"not flagged" is also what a subject that never fired prints, so an arm with no
pre-change build beside it measures nothing.

    python tools/p490jname.py                       # grades C:/FTESurf/ftesurf64.exe
    python tools/p490jname.py --exe <path> --tag pre490

The driver deletes the log and both journals FIRST, because FTE appends to a log
and a grader that reads a previous arm's lines grades the wrong run -- and
because a stale p490_A.hid on disk would make arm 3 pass on a binary that wrote
nothing.
"""
import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))  # C:/FTESurf/tools
BASE = os.path.dirname(HERE)                      # C:/FTESurf, the basedir
LOG = os.path.join(BASE, "ftesurf", "logs", "p490jname.log")
HIDA = os.path.join(BASE, "ftesurf", "data", "p490_A.hid")
HIDB = os.path.join(BASE, "ftesurf", "data", "p490_B.hid")

# The line under test is a Con_DPrintf, so it carries the log's timestamp prefix.
END_RE = re.compile(r"in_journal_end:\s+(\S+?),\s+\d+ events")


def rm(p):
    try:
        os.remove(p)
        return True
    except OSError:
        return False


def run(exe, timeout=180):
    # -WorkingDirectory is not optional: the basedir IS the cwd, and a shell left
    # in ftesurf/ produces no log at all while the process sits there.
    cmd = [exe, "-WindowStyle", "Minimized", "+exec", "test/p490jname.cfg"]
    t0 = time.time()
    try:
        subprocess.run(cmd, cwd=BASE, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print("  (the client did not quit within %ds -- grading the log anyway)"
              % timeout)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=os.path.join(BASE, "ftesurf64.exe"))
    ap.add_argument("--tag", default="subject",
                    help="label for this binary in the output (subject / pre490)")
    ap.add_argument("--no-run", action="store_true",
                    help="grade the log and files that are already there")
    ap.add_argument("--expect-broken", action="store_true",
                    help="this binary is the PRE-490 control: arm 1 MUST fail")
    args = ap.parse_args()

    if not args.no_run:
        if not os.path.exists(args.exe):
            print("FAIL: no such binary: %s" % args.exe)
            return 2
        for p in (LOG, HIDA, HIDB):
            rm(p)
        if os.path.exists(LOG):
            print("FAIL: could not delete the previous log %s -- it appends, so"
                  " grading it would read the last arm's lines." % LOG)
            return 2
        print("=== %s: %s" % (args.tag, args.exe))
        print("  ran for %.1f s" % run(args.exe))
    else:
        print("=== %s: grading what is on disk" % args.tag)

    if not os.path.exists(LOG):
        print("FAIL: no log at %s.  The basedir is the cwd; a run started from"
              " ftesurf/ writes nothing at all." % LOG)
        return 2
    text = open(LOG, "r", errors="replace").read()

    checks = []

    def ck(name, ok, detail):
        checks.append((name, ok, detail))

    ends = END_RE.findall(text)
    ck("the end line printed at all", len(ends) >= 2,
       "%d `in_journal_end: <name>, N events` lines" % len(ends))

    # ARM 1 -- the subject path: a bare name, which takes the va() branch.
    a = ends[0] if ends else ""
    ck("arm1 names data/p490_A.hid", a == "data/p490_A.hid",
       "printed %r" % (a or "<nothing>"))
    ck("arm1 is not loadworker_3", "loadworker" not in a,
       "printed %r" % (a or "<nothing>"))

    # ARM 2 -- the already-prefixed path, correct before the patch too.  This is
    # the half that proves the fix did not break the gamecode's own caller.
    b = ends[1] if len(ends) > 1 else ""
    ck("arm2 names data/p490_B.hid", b == "data/p490_B.hid",
       "printed %r" % (b or "<nothing>"))

    # ARM 3 -- the files, not the print.  This bounds the incident: the write
    # runs on the good pointer, so a misnamed PRINT never meant a misnamed FILE.
    for lbl, p in (("arm3 p490_A.hid on disk", HIDA), ("arm3 p490_B.hid on disk", HIDB)):
        sz = os.path.getsize(p) if os.path.exists(p) else -1
        ck(lbl, sz > 0, "%d bytes" % sz)
    stray = [f for f in os.listdir(os.path.join(BASE, "ftesurf", "data"))
             if "loadworker" in f] if os.path.isdir(os.path.join(BASE, "ftesurf", "data")) else []
    ck("arm3 nothing written under a loader-thread name", not stray,
       "found %s" % (stray or "none"))

    # The arm's own marker: without it a truncated log grades as a clean pass by
    # having printed nothing at all.
    ck("the arm ran to completion", "P490-DONE" in text, "P490-DONE present"
       if "P490-DONE" in text else "no P490-DONE -- the cfg did not finish")

    bad = 0
    for name, ok, detail in checks:
        print("  %-4s %-46s %s" % ("ok" if ok else "FAIL", name, detail))
        if not ok:
            bad += 1

    # The control's failure is its PASS.  A pre-490 binary that printed the real
    # name would mean the mechanism was misdiagnosed and the patch fixes nothing.
    if args.expect_broken:
        arm1 = [c for c in checks if c[0].startswith("arm1")]
        if all(c[1] for c in arm1):
            print("\ncontrol INVALID: the pre-490 binary passed arm 1, so the"
                  " defect is not where the patch says it is and the subject"
                  " proves nothing.")
            return 1
        print("\ncontrol VALID: arm 1 failed on the pre-490 binary, as it must."
              "  arm2/arm3 should still pass -- those are the paths the patch"
              " does not change.")
        hard = [c for c in checks if not c[0].startswith("arm1") and not c[1]]
        return 1 if hard else 0

    print("\n%s: %d checks, %d failed" % (args.tag, len(checks), bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
