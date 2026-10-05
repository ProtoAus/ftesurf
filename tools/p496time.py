#!/usr/bin/env python3
"""Patch 496 -- is every run time this game prints the exact one?

THE DEFECT.  Time_TickString did

    ms = floor(ticks * tickrate * 1000 + 0.5);

in ONE float32 chain.  A float32 carries ~7 significant digits and that chain
rounds twice (ticks*rate, then *1000), so it is off by 1-3 ms on most values
past 4,096,003 ms -- 68 minutes -- and 9,149,677 of the 16,777,216 ms values
below 2^24 print a wrong digit (both figures re-derived by --stats below, not
quoted).  Three board paths entered MILLISECONDS and asked for a 0.001 s tick
rate to get them back out, which is the same chain at its worst rate: 0.001 is
not a float32, so that product drifts below the 2^24 boundary too.

THE FIX.  Time_TickMs takes the product as a compensated pair (Dekker's
two-product), so `p + err` IS the real product of the two float32 inputs, and
only the sub-second remainder is scaled.  Time_MsString formats the int.  The
three ms call sites call that instead of pretending milliseconds are ticks.

WHAT THIS SCRIPT DOES

    python tools/p496time.py             run the arm, grade it (must PASS)
    python tools/p496time.py --control   build the control, run it, require it
                                         to reproduce the OLD arithmetic exactly
                                         and to FAIL the exactness check, then
                                         restore and rebuild
    python tools/p496time.py --grade     grade the log that is already there
    python tools/p496time.py --stats     re-derive the two counts quoted above

The arm is cfg/test/p496time.cfg: a listen server on surf_rookie that prints
`timefmt` cases from the CLIENT's copy of sh_time.qc and `cmd timefmt` cases
from the SERVER's, both tagged, because the file is compiled into both VMs and
the invariant it exists for is that they agree.

THE CONTROL, and why it is a build and not an argument: this script models the
old chain in Python, and a model of the old code is not the old code.  So
--control rewrites Time_TickMs's body -- and only that body -- back into the
naive float32 chain, rebuilds, and requires the arm to reproduce the model on
EVERY case while disagreeing with the exact answer on at least 1000 of them.  A
control that merely "fails" would also pass if the arm had stopped printing;
this one asserts what it printed.  The rewrite is one asserted block
replacement against the live file, the original is restored in a `finally`, and
the restore is verified by hash before the rebuild.

Run from anywhere; paths resolve against the install root two levels up.
"""

import argparse
import hashlib
import math
import os
import re
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXE = os.path.join(ROOT, "ftesurf64.exe")
LOGDIR = os.path.join(ROOT, "ftesurf", "logs")
CFG = "p496time.cfg"
LOG = "p496time"
SRC = os.path.join(ROOT, "src", "shared", "sh_time.qc")
BUILD = os.path.join(ROOT, "src", "build.ps1")

PM_TICK = 0.015           # sh_defs.qc
CLAMP_S = 2147483         # where sec * 1000 would wrap an int
CLAMP_MS = CLAMP_S * 1000
BIG_TICKS = 1e15          # where the 4097 split would overflow
# A float32 near 1000 resolves to 6e-5, so the last scaling step cannot tell a
# value within ~3e-5 ms of a half-millisecond from the half itself.  Cases
# inside that window are reported as ties and accepted either way; two of the
# arm's cases are in it (a half-tick at 15 ms/tick) and no integer tick count
# at a shipped rate is.
TIE = 1e-3

FAILED = []
PASSED = []
NOTED = []


def check(cond, what):
    (PASSED if cond else FAILED).append(what)
    print("  %-4s %s" % ("ok" if cond else "FAIL", what))
    return bool(cond)


def note(what):
    NOTED.append(what)
    print("  note %s" % what)


def f32(x):
    """The float32 nearest x, as a Python float.  struct, not numpy: this
    tree's tools run on the Pi's python too."""
    return struct.unpack("f", struct.pack("f", float(x)))[0]


# ---------------------------------------------------------------- the models

def ms_string(ms):
    """Time_MsString, in Python ints: m:ss.mmm, or h:mm:ss.mmm with an hour."""
    neg = ms < 0
    ms = -ms if neg else ms
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    sign = "-" if neg else ""
    if h:
        return "%s%d:%02d:%02d.%03d" % (sign, h, m, s, ms)
    return "%s%d:%02d.%03d" % (sign, m, s, ms)


def exact_ms(ticks, rate):
    """The exact product of the two float32 inputs, scaled and rounded half up.

    THE PRODUCT IS TAKEN IN float64, which holds it exactly: two float32s need
    48 bits.  Rounding it to float32 first -- what this function's first cut
    did, and what the pre-496 QC did -- is precisely the error under test, and
    it made the reference agree with the defect on 2144999936 vs 2144999952.
    The clamp is tested on the float32 product because that is what the QC
    compares."""
    if rate <= 0:
        rate = PM_TICK
    neg = f32(ticks) < 0
    u = f32(abs(f32(ticks)))
    v = f32(rate)
    if f32(u * v) >= f32(CLAMP_S) or u >= BIG_TICKS:
        return -CLAMP_MS if neg else CLAMP_MS
    prod = u * v                       # exact in float64
    sec = int(prod)                    # truncation; prod >= 0
    ms = int(math.floor((prod - sec) * 1000.0 + 0.5))
    if ms >= 1000:
        ms -= 1000
        sec += 1
    elif ms < 0:
        ms += 1000
        sec -= 1
    total = ms + sec * 1000
    return -total if neg else total


def is_tie(ticks, rate):
    """True when the exact product lands within TIE of a half-millisecond, so
    the float32 scaling step's own 6e-5 resolution decides the digit."""
    if rate <= 0:
        rate = PM_TICK
    u = abs(f32(f32(ticks)))
    prod = u * f32(rate)               # exact in float64
    if prod >= CLAMP_S:
        return False
    frac = (prod - int(prod)) * 1000.0
    return abs(frac - math.floor(frac) - 0.5) < TIE


def old_ms(ticks, rate):
    """The pre-496 chain, modelled multiply by multiply in float32.  This is
    what the control build must reproduce, and what the discrimination count is
    measured against -- so if the model is wrong, the control leg says so."""
    if rate <= 0:
        rate = PM_TICK
    neg = f32(ticks) < 0
    u = f32(abs(f32(ticks)))
    p = f32(f32(u * f32(rate)) * f32(1000.0))
    if p >= f32(CLAMP_MS):
        return -CLAMP_MS if neg else CLAMP_MS
    ms = int(math.floor(f32(p + f32(0.5))))
    return -ms if neg else ms


# ------------------------------------------------------------------ the arm

LINE_RE = re.compile(r"\btf (cl|sv) (\S+) (\S+) (-?\d+) (\S+)")


def cases(text):
    """-> [(tag, ticks, rate, ms, string)] in log order.

    Anchored on the `tf ` label the print writes, not on the word alone: every
    log line carries a timestamp prefix, and this tree has been burned by
    patterns that expected two lines to touch."""
    out = []
    for tag, t, r, ms, s in LINE_RE.findall(text):
        try:
            out.append((tag, float(t), float(r), int(ms), s))
        except ValueError:
            pass
    return out


def run_arm(timeout=300):
    """Launch the headless arm and wait.  -> (start time, the log's text)."""
    p = os.path.join(LOGDIR, LOG + ".log")
    if os.path.exists(p):
        os.remove(p)        # FTE APPENDS: a stale log grades the previous arm
    args = [EXE, "-WindowStyle", "Minimized", "+exec", "test/" + CFG]
    t0 = time.time()
    try:
        subprocess.run(args, cwd=ROOT, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print("  !! %s did not exit in %d s" % (CFG, timeout))
    if not os.path.exists(p):
        return t0, ""
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return t0, f.read()


# ------------------------------------------------------------------ grading

# P5: the edges, each an explicit case rather than something the sweep happens
# to hit.  Expectations derived from exact_ms() and pre-registered in the cfg
# header before the first run; (ticks, rate) as the cfg spells them.
EDGES = [
    (100.0, 0.0, "rate 0 falls back to PM_TICK"),
    (100.0, -1.0, "and so does a negative rate"),
    (240000.0, 0.015, "exactly one hour, h:mm:ss.mmm"),
    (273085.0, 0.015, "BACKLOG's worked example"),
    (-273085.0, 0.015, "negative, same magnitude"),
    (143000000.0, 0.015, "24 days minus a little: the old chain is 16 ms off"),
    (200000000.0, 0.015, "past the clamp"),
    (1118481.0, 0.015, "the ms value 2^24-1: the old chain reads 2^24"),
    (4096003.0, 0.001, "the ms idiom's own boundary"),
    # f32(1 / f32(66.6667)) -- the rate cl_online.qc:1683 and cl_scores.qc:1818
    # actually pass, as `1 / ob_rate[i]` with ob_rate in ticks per second.  Its
    # first wrong tick is 64220 = 16 minutes, the worst of the real rates.
    (64219.0, 0.0149999925, "the online board's rate, the tick before it goes wrong"),
    (64220.0, 0.0149999925, "and the tick where it does: 963299, old reads 963300"),
    (64221.0, 0.0149999925, "and the next: 963314, old reads 963315"),
    (400000.0, 0.0149999925, "100 minutes at that rate: both agree again here"),
    (16777217.0, 0.001, "an ms count a float32 cannot hold"),
    (0.5, 0.015, "a fractional tick (a tie: see TIE)"),
    (-0.5, 0.015, "its negative"),
    (-0.01, 0.015, "negative that rounds to zero: unsigned, by design"),
]


def grade(text, control):
    """Grade one arm's log.

    `control` selects WHICH arithmetic every case must reproduce: the exact
    product (subject) or the pre-496 float32 chain (control).  Both legs also
    require the discrimination count, so a control that merely "fails
    somewhere" is not a pass -- it has to fail on exactly the cases the model
    says the old chain gets wrong, and match it everywhere else.
    """
    ref = old_ms if control else exact_ms
    refname = "the pre-496 float32 chain" if control else "the exact one"
    rows = cases(text)
    cl = [r for r in rows if r[0] == "cl"]
    sv = [r for r in rows if r[0] == "sv"]
    print("  %d graded lines: %d client, %d server (%s build)"
          % (len(rows), len(cl), len(sv), "control" if control else "subject"))

    if not check(len(cl) >= 2000, "P1 at least 2000 client lines (%d)" % len(cl)):
        return
    if not check(len(sv) >= 2000, "P1 at least 2000 server lines (%d)" % len(sv)):
        return

    # P1: the two VMs agree on every case both printed.  This is the invariant
    # sh_time.qc exists for -- the server says your time in chat and in the
    # save list, the client draws it.  It is required of the control too, so a
    # control that stopped printing from one VM cannot read as a pass.
    clmap = {(f32(r[1]), f32(r[2])): (r[3], r[4]) for r in cl}
    svmap = {(f32(r[1]), f32(r[2])): (r[3], r[4]) for r in sv}
    shared = set(clmap) & set(svmap)
    differ = sorted(k for k in shared if clmap[k] != svmap[k])
    check(len(shared) >= 2000, "P1 %d cases printed by both VMs" % len(shared))
    check(not differ,
          "P1 client and server agree on all %d shared cases%s"
          % (len(shared), "" if not differ else " (first: %s cl=%s sv=%s)"
             % (differ[0], clmap[differ[0]], svmap[differ[0]])))

    # P2 / P4: the arithmetic, against whichever reference this leg grades.
    bad = []
    bad_str = []
    disc = 0
    ties = 0
    for tag, t, r, ms, s_ in rows:
        want = ref(t, r)
        if old_ms(t, r) != exact_ms(t, r):
            disc += 1
        if ms != want:
            # A half-millisecond tie is excused for the exact reference only:
            # the last scaling step is float32 (6e-5 of a ms at 1000) and the
            # exact product can land 2e-7 under the half.  The control leg gets
            # no exemption, so it must match the old chain on every case.
            if not control and is_tie(t, r):
                ties += 1
            else:
                bad.append((tag, t, r, ms, want))
        if s_ != ms_string(ms):
            bad_str.append((tag, t, r, ms, s_, ms_string(ms)))
    if ties:
        note("%d case(s) are half-millisecond ties the float32 scaling step "
             "resolves the other way; accepted" % ties)

    check(not bad,
          "P%s every ms is %s%s"
          % ("4" if control else "2", refname,
             "" if not bad else " (%d differ, first %s)" % (len(bad), bad[0])))
    check(disc >= 1000,
          "P3 %d of the graded cases are ones the old chain prints "
          "differently, so this arm can tell a fix from no fix" % disc)
    if control:
        check(disc >= 1000 and not bad,
              "P4 the control is the old arithmetic and not a broken arm: it "
              "reproduces the modelled chain everywhere and disagrees with the "
              "exact answer on %d cases" % disc)
    check(not bad_str,
          "P2 every string is that ms split as m:ss.mmm / h:mm:ss.mmm%s"
          % ("" if not bad_str else " (%d differ, first %s)"
             % (len(bad_str), bad_str[0])))

    # P5: the edges, against the same reference as everything else.
    for t, r, why in EDGES:
        e = ref(t, r)
        kt, kr = f32(t), f32(r)        # the log prints %.9g of the float32
        got = [x for x in rows if f32(x[1]) == kt and f32(x[2]) == kr]
        if not got:
            check(False, "P5 %.9g @ %.9g (%s) was never printed" % (t, r, why))
            continue
        if not control and is_tie(t, r):
            ok = all(abs(x[3]) in (abs(e), abs(e) + 1) and x[4] == ms_string(x[3])
                     for x in got)
        else:
            ok = all(x[3] == e and x[4] == ms_string(e) for x in got)
        check(ok, "P5 %.9g @ %.9g -> %d %s (%s)%s"
              % (t, r, e, ms_string(e), why,
                 "" if ok else " got %s" % [(x[0], x[3], x[4]) for x in got]))


# ---------------------------------------------------------------- the control

FIXED_BLOCK = """	p = u * v;
	if (p >= 2147483 || u >= 1000000000000000)
		return neg ? -2147483000i : 2147483000i;

	c = 4097 * u;   uh = c - (c - u);   ul = u - uh;
	c = 4097 * v;   vh = c - (c - v);   vl = v - vh;
	err = ((uh * vh - p) + uh * vl + ul * vh) + ul * vl;

	sec = (int)p;                       // truncates toward zero; p >= 0
	r = p - (float)sec;                 // exact while sec < 2^24 (194 days)
	ms = (int)floor((r + err) * 1000 + 0.5);
	if (ms >= 1000i)
	{
		ms = ms - 1000i;
		sec = sec + 1i;
	}
	else if (ms < 0i)                   // err under a whole second of p
	{
		ms = ms + 1000i;
		sec = sec - 1i;
	}

	ms = ms + sec * 1000i;
"""

# The control keeps the clamp and the `i` literals -- those are not what is
# under test -- and differs in exactly one thing: the product is taken in one
# float32 chain, as it was before 496.  `sec = 0i` so the `ms + sec * 1000i`
# line that follows the block is a no-op rather than a second rounding.
CONTROL_BLOCK = """	// CONTROL BUILD for tools/p496time.py -- the pre-496 float32 chain.
	// Written by that script, never committed, never deployed.  The three
	// assignments below are not dead code: they keep every local the fixed
	// block declares referenced, so the control build is warning-clean too and
	// `build ok` means the same thing in both legs (fteqcc's Q302 fired on six
	// of them the first time this ran).
	err = 0;  c = 0;  r = 0;  uh = u;  ul = 0;  vh = v;  vl = 0;
	p = u * v * 1000;
	if (p >= 2147483000)
		return neg ? -2147483000i : 2147483000i;
	ms = (int)floor(p + 0.5);
	sec = 0i;
"""


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def build():
    """Recompile and redeploy all three progs.  -> True on a clean build.

    build.ps1 writes its warnings through the host stream, so `2>&1 |
    Select-String` counts nothing (AGENTS.md); this reads the captured text."""
    print("  building ...")
    try:
        out = subprocess.run(["pwsh", "-NoProfile", "-Command",
                              "./build.ps1 -Jobs 8"],
                             cwd=os.path.dirname(BUILD), capture_output=True,
                             text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        print("  !! build did not run: %s" % e)
        return False
    text = (out.stdout or "") + (out.stderr or "")
    # build.ps1's own success line is `Done. 0 warnings`, so "does the text
    # contain the word warning" grades a clean build as a failure -- measured,
    # three times, once per prog.  Read the NUMBER out of those lines and treat
    # any other line mentioning a warning as a real one.
    dones = [int(m) for m in re.findall(r"Done\. (\d+) warnings", text)]
    warns = [l for l in text.splitlines()
             if "warning" in l.lower() and "Done. 0 warnings" not in l]
    errs = [l for l in text.splitlines() if "error" in l.lower()]
    ok = (out.returncode == 0 and len(dones) == 3 and not any(dones)
          and not warns and not errs)
    print("  build %s (Done lines %s, %d warning line(s), %d error line(s))"
          % ("ok" if ok else "FAILED", dones, len(warns), len(errs)))
    for l in (warns + errs)[:6]:
        print("     " + l.strip())
    return ok


def make_control():
    """Rewrite Time_TickMs's body into the naive chain.  -> lines changed, or
    None.  ONE asserted block replacement, so the control differs from the
    subject in exactly the arithmetic under test and nothing else."""
    with open(SRC, "r", encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(FIXED_BLOCK)
    if n != 1:
        print("  !! the fixed block is in sh_time.qc %d times, not 1 -- the "
              "file moved; update FIXED_BLOCK" % n)
        return None
    ctl = s.replace(FIXED_BLOCK, CONTROL_BLOCK)
    # A line-by-line diff counts everything below the block as changed, because
    # the two blocks are different lengths -- measured 118 "changed" lines for
    # a 24-line block.  What actually has to hold is that the replacement is
    # the only difference, which str.replace on a unique match guarantees, and
    # that the result holds the control block once and the fixed block never.
    if ctl.count(CONTROL_BLOCK) != 1 or ctl.count(FIXED_BLOCK) != 0:
        print("  !! the rewrite did not land as one block")
        return None
    nd = len(FIXED_BLOCK.splitlines()) - len(CONTROL_BLOCK.splitlines())
    with open(SRC, "w", encoding="utf-8", newline="") as f:
        f.write(ctl)
    print("  control written: %d line(s) of the fixed block replaced by %d"
          % (len(FIXED_BLOCK.splitlines()), len(CONTROL_BLOCK.splitlines())))
    return nd


def stats():
    """Re-derive the two counts the docstring and BACKLOG quote."""
    n = 1 << 24
    bad = 0
    first = None
    for v in range(n):
        if old_ms(v, 0.001) != v:
            bad += 1
            if first is None:
                first = v
    print("ms idiom (rate 0.001), all %d values below 2^24:" % n)
    print("  first wrong at %s ms; %d of %d print a wrong digit (%.1f%%)"
          % (first, bad, n, 100.0 * bad / n))
    for rate, upto, step in ((0.015, 1200000, 1), (1 / 66.6667, 1200000, 1)):
        bad = 0
        first = None
        for v in range(0, upto, step):
            if old_ms(v, rate) != exact_ms(v, rate):
                bad += 1
                if first is None:
                    first = v
        print("tick path at rate %r, %d ticks (%.0f min): first wrong at %s, "
              "%d differ" % (rate, upto, upto * rate / 60.0, first, bad))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--control", action="store_true",
                    help="build the pre-496 arithmetic and require the arm to "
                         "reproduce it, then restore and rebuild")
    ap.add_argument("--grade", action="store_true",
                    help="grade the log that is already there; do not run")
    ap.add_argument("--stats", action="store_true",
                    help="re-derive the defect's two counts and exit")
    ap.add_argument("--keep", action="store_true",
                    help="with --control: leave the control build in place")
    a = ap.parse_args()

    if a.stats:
        stats()
        return 0

    if a.grade:
        p = os.path.join(LOGDIR, LOG + ".log")
        if not os.path.exists(p):
            print("no log at %s" % p)
            return 1
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        grade(text, False)
    elif not a.control:
        t0, text = run_arm()
        print("ran %s in %.0f s" % (CFG, time.time() - t0))
        grade(text, False)
    else:
        # The fixed file is uncommitted work, so the backup -- not `git
        # checkout`, which would restore HEAD -- is the authority.
        with open(SRC, "rb") as f:
            data = f.read()
        h = hashlib.sha256(data).hexdigest()
        rc = 1
        try:
            if make_control() is None:
                return 1
            if not build():
                print("  the control did not build")
                return 1
            t0, text = run_arm()
            print("ran the control in %.0f s" % (time.time() - t0))
            grade(text, True)
            rc = 1 if FAILED else 0
        finally:
            if not a.keep:
                with open(SRC, "wb") as f:
                    f.write(data)
                ok = sha(SRC) == h
                print("  restored sh_time.qc: %s"
                      % ("hash matches the fixed file" if ok else "HASH MISMATCH"))
                if not ok:
                    print("  !! %s is not the file this script started with" % SRC)
                elif not build():
                    print("  !! the restore did not rebuild clean")
    print("\n%d checks, %d failed" % (len(PASSED) + len(FAILED), len(FAILED)))
    return rc if a.control else (1 if FAILED else 0)


if __name__ == "__main__":
    sys.exit(main())
