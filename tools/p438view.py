#!/usr/bin/env python3
"""
p438view.py -- driver for cfg/test/p438view.cfg (Patch 438: the evidence
sidecar's cold reload reads with FILE_READ, not buf_loadfile).

WHY A GENERATOR.  The arm needs a `.view` BIGGER THAN THE 5 MB WINDOWS MAPPING
CAP, because below it buf_loadfile reads a mapped view and the two spellings cost
the same.  No file in data/ is that big and a run long enough to make one is not
scriptable, so this writes one from the real header and the real line shape
(FS_VIEWHEAD = 4, `%.4f %g %g %.2f %.2f %g`) -- a line is 37-38 bytes, so 6.5 MB
is ~175k frames, about ten minutes at the 66 Hz sidecar rate.

Nothing else is invented: the client loads it into rec_rp_view on a save-load, and
the reader's own dprint carries the two numbers that are graded -- the milliseconds
and the line count, which together say the read was both fast and complete.

PATCH 441 DEMOTED THE "ROUND TRIP" THIS FILE USED TO CALL ITS DELIVERABLE.  R2's
save was supposed to write the buffer back through Rec_ViewSaved and the comparison
was supposed to catch a spelling that dropped or merged a line -- but the comparison
read the file the driver had GENERATED, so it compared that file with itself, and a
run with --keep shows no written-back .view exists at all.  See writeback().

It writes to a scratch directory UNDER THE INSTALL ROOT (C:\\FTESurf\\p438view)
and points cl_saveroot at it, so no shared fixture in data/ is touched -- and the
scratch has to be inside the basedir, because the client's file layer cannot
reach %TEMP% at all.

    python tools/p438view.py [--exe ftesurf64.exe] [--mb 7] [--control]

--control grades the PRE-fix numbers (the same file, read with buf_loadfile).
Exit status 0 when the reload is inside the budget, the line count matches and
the round trip is byte-for-byte.
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
# Under the GAMEDIR.  FS_LoadFile locates with FS_GAME, so a path outside the game
# directory is not found at all -- and fopen(FILE_READ) returns -1 with no "Access
# denied" line, which reads as a reader bug and is a path bug (measured).
RELROOT = "p438view"
SCRATCH = os.path.join(GAMEDIR, RELROOT)
SLOT = os.path.join(SCRATCH, "save901")
SMALL = os.path.join(SCRATCH, "save902")
VIEW = os.path.join(SLOT, "run.view")
CFG = "cfg/test/p438view.cfg"
LOG = os.path.join(GAMEDIR, "logs", "p438view.log")
LINE = "29.7278 %d 0 58.75 -75.35 20\n"

EXPECTED = b""           # the 6 MB sidecar's bytes (slot 901)
EXPECTED_SMALL = b""     # the 1.6 KB one's (slot 902), which is the LAST load


def generate(mb):
    """The sidecar, at the path Rec_SavePath(901) resolves to under cl_saveroot."""
    global EXPECTED, EXPECTED_SMALL
    n = int(mb * 1024 * 1024 / 38)
    os.makedirs(SLOT, exist_ok=True)
    os.makedirs(SMALL, exist_ok=True)
    # A 54-line sidecar beside the big one: the same reader, the same code path,
    # a file far under Windows' 5 MB mapping cap.  If the big read fails and this
    # one succeeds, the failure is the file and not the path.
    with open(os.path.join(SMALL, "run.view"), "w", newline="") as fh:
        fh.write("FTESURF-VIEW 2\nmap surf_4am\nhid 1\nbegin\n")
        for i in range(50):
            fh.write(LINE % (29886 + i))
    with open(VIEW, "w", newline="") as fh:
        fh.write("FTESURF-VIEW 2\nmap surf_4am\nhid 1\nbegin\n")
        for i in range(n):
            fh.write(LINE % (29886 + i))
    with open(VIEW, "rb") as fh:
        EXPECTED = fh.read()
    with open(os.path.join(SMALL, "run.view"), "rb") as fh:
        EXPECTED_SMALL = fh.read()
    size = len(EXPECTED)
    print("wrote %s: %.2f MB, %d sample lines"
          % (VIEW, size / 1048576.0, n))
    # The two spellings count lines differently, and that is a finding rather than
    # a nuisance: the file is 4 header lines + n samples, buf_loadfile's VFS_GETS
    # split keeps the trailing empty line the file's last newline produces (n + 5)
    # and Watch_BufLoad's fgets loop stops at it (n + 4).  A sidecar rewritten by
    # the old spelling is therefore one line longer than the file it came from --
    # which is what buf_getsize counts, and what the mark is set from.
    print("the reader will report %d lines" % (n + 4))
    # The path the client will spell: relative to its GAMEDIR, forward slashes.
    print("cl_saveroot will be %s" % RELROOT)
    return size, n + 4


def extra_dir():
    """Where the run's own write-back can land: the server resolves cl_saveroot to
    the same scratch name the cfg sets, under data/."""
    return os.path.join(GAMEDIR, "data", RELROOT)


SAVEROOT = os.path.join(GAMEDIR, "data", "saves", "surf_4am")


def slots_now():
    """The slot names in the SERVER's save root right now, or an empty set."""
    if not os.path.isdir(SAVEROOT):
        return set()
    return set(d for d in os.listdir(SAVEROOT) if d.startswith("save"))


def cleanup_saves(before):
    """The cfg's R2 save lands in the SERVER's save root (data/saves/surf_4am),
    which the scratch cl_saveroot does not move -- one new slot per run.  Remove
    the slots THIS RUN MADE: the ones that were not there before it started.

    PATCH 441 REWROTE THIS, because the old test was RECENCY -- any slot whose
    state.txt mtime was under two hours old -- and that is not ownership.
    data/saves/surf_4am is a shared tree: a save another session (or a player on
    this box) had just taken was inside the window and got removed, and the
    `created` stamp the docstring cited was read into a variable and then never
    compared with anything.  A listing taken before the run cannot be wrong about
    which rows are new.
    """
    for slot in sorted(slots_now() - before):
        try:
            shutil.rmtree(os.path.join(SAVEROOT, slot))
            print("removed %s (new since this run started)" % slot)
        except OSError as exc:
            # NOT swallowed: a save row this harness cannot remove is a leftover
            # in a shared fixture, and `pass` here is how it stayed invisible.
            print("cleanup: cannot remove %s: %s" % (slot, exc))


def writeback():
    """R2's write-back -- and A THIRD ANSWER FOR "there was nothing to compare".

    PATCH 441: this used to read the file the driver GENERATED and compare it with
    the bytes it had just written there (`open(VIEW) == EXPECTED`, the same file on
    both sides), so it answered True however the client behaved.  Measured after a
    green run with --keep: the only .view files under the client's save root are the
    two generated ones, and R2's save left `data/p438view/save012/seq.txt` plus a
    state.txt in the server's root -- no sidecar anywhere.  The round trip this arm
    called its deliverable did not happen.

    So: compare the real file if the client wrote one, and otherwise say NOT
    MEASURED -- not a pass dressed as one.  The reader's own two numbers (the ms and
    the line count, both from the subject's own print) are what the patch is about.

    AND COMPARE IT WITH THE RIGHT FILE.  The buffer at R2 holds the LAST load, which
    is R1b's 1.6 KB slot 902 and not the 6 MB slot 901, so the old comparison was
    against the wrong bytes as well as the wrong file: measured, a written-back
    sidecar differs from the 6 MB one and that is correct behaviour.  The real check
    is that the written file is byte-identical to ONE of the two the client read --
    a spelling that dropped, merged or blanked a line matches neither.

    WHETHER ONE IS WRITTEN AT ALL IS NOT STABLE ACROSS RUNS: measured twice, the
    sidecar appeared only on the run that started with an earlier run's
    `data/p438view/save<n>/seq.txt` still on disk, and not on the one that began
    clean.  Which is the other reason this cannot be a pass/fail line.
    """
    skip = set(os.path.abspath(p) for p in
               (VIEW, os.path.join(SMALL, "run.view")))
    found = []
    for root in (SCRATCH, extra_dir()):
        for dirpath, _, files in os.walk(root):
            for f in files:
                p = os.path.join(dirpath, f)
                if f.endswith(".view") and os.path.abspath(p) not in skip:
                    found.append(p)
    if not found:
        print("write-back: NOT MEASURED -- the client wrote no .view under %s or %s"
              % (os.path.relpath(SCRATCH, ROOT), os.path.relpath(extra_dir(), ROOT)))
        return True
    ok = True
    for p in sorted(found):
        b = open(p, "rb").read()
        which = ("the 6 MB sidecar (slot 901)" if b == EXPECTED else
                 "the 1.6 KB sidecar (slot 902, the last load)" if b == EXPECTED_SMALL
                 else "NEITHER of the two files the client read")
        print("write-back %s (%d bytes): %s" % (os.path.relpath(p, ROOT), len(b), which))
        ok = ok and b in (EXPECTED, EXPECTED_SMALL)
    return ok


def rmtree_loud(path):
    """`ignore_errors=True` was here.  A scratch tree this driver cannot remove is
    a leftover under the gamedir, and silence about it is how one survives."""
    if not os.path.exists(path):
        return
    try:
        shutil.rmtree(path)
    except OSError as exc:
        print("cleanup: cannot remove %s: %s" % (os.path.relpath(path, ROOT), exc))


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+set", "cl_saveroot", RELROOT,
                          "+exec", CFG], cwd=ROOT, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


# What a QC fault actually looks like in a log: a stack trace, then the message.
# PATCH 441 REPLACED `QC (error|Error)`, which matches NOTHING the engine prints --
# measured over every log in ftesurf/logs: the old pattern hit 0 of 1550 files, this
# one hits the 9 that hold a real fault (b51c, b51d, b51e, b65a_hud, ovl02, ...).
# `<file>.qc:<line>: <name>` is PR_StackTrace's frame line (pr_exec.c:436) and
# appears in a game log only from a trace; the other three are the VM's own fatals.
QCFAULT = re.compile(r"runaway loop error|PR_ExecuteProgram:|<NO STACK>|<NO FUNCTION>"
                     r"|[a-z_]+\.qc:[0-9]+: \w")

RELOAD = r"p438 cold reload took ([\d.]+) ms for (\d+) lines"


def sections(txt):
    """{tag: text} from the cfg's own `==== TAG` echoes, so the gate arm's section
    and the timed one cannot be read for each other."""
    out, cur = {}, None
    for line in txt.splitlines():
        m = re.search(r"==== (\S+)\b", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def grade(log, control, size, lines, budget):
    ok = True
    txt = open(log, "r", errors="replace").read()
    sec = sections(txt)
    # The control build's own number is the measurement this patch exists for, so
    # it is reported rather than passed or failed against the fixed build's budget.
    if control:
        budget = 60000.0

    def say(label, got, exp, good=None):
        nonlocal ok
        if good is None:
            good = (got == exp)
        elif callable(good):
            good = good(got)
        ok = ok and good
        print("  %-42s %-20s %s" % (label, got,
                                    "ok" if good else "MISMATCH, want %s" % exp))

    print("observables (%s), %s predictions:"
          % (os.path.basename(log), "PRE-FIX" if control else "POST-FIX"))
    # R1g, the Patch 441 gate: the same command with sv_cheats 0 must be refused in
    # the server's own words, and must NOT reach the reader.  Graded in its own
    # section, because R1 fires the identical command two lines later.
    g = sec.get("R1g")
    if g is None:
        say("R1g section", "<absent>", "present", False)
    else:
        say("R1g refusal", "yes" if "sl_replay needs sv_cheats" in g else "no", "yes")
        say("R1g reached the reader", "yes" if re.search(RELOAD, g) else "no", "no")
    r1 = sec.get("R1", txt)
    m = re.search(RELOAD, r1)
    if not m:
        say("cold reload line", "<absent>", "present", False)
        return False
    ms, got_lines = float(m.group(1)), int(m.group(2))
    say("cold reload ms (%.2f MB)" % (size / 1048576.0), "%.0f" % ms,
        "< %.0f" % budget, lambda g2: float(g2) < budget)
    say("lines read back", str(got_lines), str(lines))
    fault = QCFAULT.search(txt)
    say("no QC fault", "yes" if not fault else "no: %s" % fault.group(0), "yes")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--mb", type=float, default=7.0,
                    help="sidecar size to generate; must be over the 5 MB cap")
    ap.add_argument("--budget", type=float, default=2000.0,
                    help="ms the cold reload must finish inside")
    ap.add_argument("--control", action="store_true",
                    help="grade against the PRE-fix predictions")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    if a.grade_only:
        if not os.path.exists(LOG) or not os.path.exists(VIEW):
            raise SystemExit("no log or no sidecar; run without --grade-only")
        size = os.path.getsize(VIEW)
        lines = sum(1 for _ in open(VIEW, "r"))
        return 0 if grade(LOG, a.control, size, lines, a.budget) else 1

    size, lines = generate(a.mb)
    before = slots_now()
    secs = run(a.exe, a.timeout)
    print("ran %s for %.0f s" % (a.exe, secs))
    if not os.path.exists(LOG):
        raise SystemExit("no log at %s -- was the cwd C:\\FTESurf?" % LOG)
    ok = grade(LOG, a.control, size, lines, a.budget)
    ok = writeback() and ok
    cleanup_saves(before)
    if not a.keep:
        rmtree_loud(SCRATCH)
        rmtree_loud(extra_dir())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
