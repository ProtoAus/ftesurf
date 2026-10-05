#!/usr/bin/env python3
"""Patch 493 -- the move-column range marker, driven and graded.

THE OBSERVATION: a usercmd's move triple reaches the server with no range test
anywhere in the engine (the server side is a bare `sv_player->xv->movement[0] =
ucmd->forwardmove;` and the only client-side bound is the wire's own
`bound(-32768, ..., 32767)`), so a value no key can produce is free evidence.
SV_MoveBoundFrame compares each command's largest |axis| against `run_movebound`,
counts the ones over it, keeps the worst, sets TF_MOVEOOR, and SV_RecOpen states
the bound in the file as a `movebnd` header key so tools/reccheck.py can judge the
bit against the file's own `in` rows in BOTH directions.

WHAT THIS SCRIPT GRADES, and why it is a script rather than a log read: the arm's
predictions are about NUMBERS IN A LINE and about a file on disk, and the second
half -- the two tamper controls -- cannot be graded by eye at all.

    python tools/p493move.py            # both arms, ~2 minutes
    python tools/p493move.py --keep     # leave the mutated copies for a look

ARMS
  A/B  cfg/test/p493move.cfg, one run: the shipped 450 as the control, then the
       same key at cl_forwardspeed 5000 as the subject.  BOTH ARE THE STOCK INPUT
       LAYER -- the only difference between the two phases is an ordinary archived
       cvar -- so this measures the observation and not an accusation.
  C    cfg/test/p493off.cfg with `+set run_movebound 0` ON THE COMMAND LINE,
       because run_t_movebnd is latched at map init and a `set` inside the cfg
       arrives after SSQC's registercvar (this tree's standing trap).
  D    two mutated copies of A/B's archived file, graded through reccheck: the bit
       cleared while a row stays over the bound must FAULT, and a row pushed over
       the bound in a file whose bit is clear must FAULT.  Without these the
       cross-check is a claim rather than a check.

Run from anywhere; paths are resolved against the install root two levels up.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXE = os.path.join(ROOT, "ftesurf64.exe")
LOGDIR = os.path.join(ROOT, "ftesurf", "logs")
# THE FILE ARM FINISHES THE RUN AND DOES NOT PARK IT.  Two facts decided that,
# both measured on this arm's first runs:
#   - a park (Multi-Session) leaves the file CLOSED but its header flags word is
#     the one written at open, i.e. `flags 0`.  SV_RecFlagLine's fixed-width line
#     is rewritten only by SV_RecClose and SV_RecKeepEvidence, so a parked file
#     can never show TF_MOVEOOR -- and reccheck.py gates every header-bit
#     cross-check on an `end` record for exactly that reason.
#   - a finish IS reachable from a script by b88fin.cfg's route: the zone scan is
#     a server-side point test (sv_zones.qc's Zone_PointInside), so a noclip
#     flight crosses bhop_eazy's END region.  sv_lobby.qc's "a finish cannot be
#     scripted" is about walking one, and about the clock being worthless
#     afterwards -- which nothing here depends on.
# So the graded file is the tainted finish the flight produces.
RUNS = os.path.join(ROOT, "ftesurf", "data", "runs", "bhop_eazy", "main")
TF_MOVEOOR = 262144
# Files a finished run rewrites in place.  cheat.* is b88fin.cfg's fixture and
# last.* is every run's, so both are backed up and put back: this arm is a guest
# in a tree other harnesses read.
RESTORE = ("cheat.rec", "cheat.view", "cheat.hid", "last.rec", "last.view")
# Snapshot of the resume folder's keys, taken before the arms: see `restore`.
RESUME_BEFORE = set()

sys.path.insert(0, HERE)
import reccheck                                          # noqa: E402

FAILED = []
PASSED = []


def check(cond, what):
    (PASSED if cond else FAILED).append(what)
    print("  %-4s %s" % ("ok" if cond else "FAIL", what))
    return bool(cond)


def run_arm(cfg, log, extra=(), timeout=300):
    """Launch one headless arm and wait for it to exit.  -> the log's text."""
    p = os.path.join(LOGDIR, log + ".log")
    if os.path.exists(p):
        os.remove(p)          # FTE APPENDS: a stale log grades the previous arm
    args = [EXE, "-WindowStyle", "Minimized"]
    args += list(extra)
    args += ["+exec", "test/" + cfg]
    t0 = time.time()
    try:
        subprocess.run(args, cwd=ROOT, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print("  !! %s did not exit in %d s" % (cfg, timeout))
    if not os.path.exists(p):
        return t0, ""
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return t0, f.read()


MOVEBND_RE = re.compile(
    r"movebnd: bound (\S+)\s+over (\S+)\s+worst (\S+)\s+moveoor (\S+)")


def movebnd_lines(text):
    """-> [(bound, over, worst, moveoor)] in the order the log holds them.

    MATCHES `movebnd: bound` AND NOT THE BARE WORD.  A server-set cvar's readback
    prints three lines and the first one lies (AGENTS.md), and the same shape of
    mistake here would be grading the cfg's own `echo` of a cvar rather than the
    diagnostic the patch added -- so the pattern is anchored on the label the
    print writes."""
    return [(float(a), float(b), float(c), float(d))
            for a, b, c, d in MOVEBND_RE.findall(text)]


def tree_state():
    """-> {name: (size, mtime)} for the run folder this arm writes into."""
    out = {}
    if os.path.isdir(RUNS):
        for n in os.listdir(RUNS):
            p = os.path.join(RUNS, n)
            if os.path.isfile(p):
                out[n] = (os.path.getsize(p), os.path.getmtime(p))
    return out


def backup():
    """-> {name: bytes} for the files a finished run rewrites."""
    out = {}
    for n in RESTORE:
        p = os.path.join(RUNS, n)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                out[n] = f.read()
    print("     backed up %d file(s) from data/runs/bhop_eazy/main" % len(out))
    return out


def restore(bak, before):
    """Put the run folder back: restore the backups, drop what the arm created."""
    for n, blob in bak.items():
        with open(os.path.join(RUNS, n), "wb") as f:
            f.write(blob)
    now = tree_state()
    for n in sorted(set(now) - set(before)):
        print("     removing the file this arm created: %s" % n)
        try:
            os.remove(os.path.join(RUNS, n))
        except OSError as e:
            print("     !! could not remove %s: %s" % (n, e))
    for n in sorted(now):
        if n in before and now[n] != before[n] and n not in bak:
            print("     !! %s changed and was not backed up -- left as it is" % n)
    print("     run folder restored (%d file(s) put back)" % len(bak))
    # A PARKED SLOT IS RESIDUE TOO, and this script left one behind on the run that
    # still parked: data/resume/<map>/@<key>/ is offered to whoever plays that map
    # next, so a harness that writes one has to take it away.  Enumerated before
    # the arms and diffed after, because two other keys' slots sit in that folder
    # and are not ours to touch.
    res = os.path.join(ROOT, "ftesurf", "data", "resume", "bhop_eazy")
    if os.path.isdir(res):
        made = sorted(set(os.listdir(res)) - RESUME_BEFORE)
        for d in made:
            p = os.path.join(res, d)
            print("     removing the resume slot this arm parked: %s" % d)
            shutil.rmtree(p, ignore_errors=True)


def newest_rec(since):
    """-> the newest .rec written into the run folder after `since`, else None.

    ANY NAME, because the archive name is a function of the run's class and this
    arm's run is tainted in three ways at once (setpos, noclip, and a cheated
    class), which is not a name worth predicting: `cmd timer` said
    `would write .../0001818_pb.rec` on the run that the b88fin recipe calls
    cheat.rec.  Predicting the name is how an arm grades the previous run's
    file."""
    best, bt = None, 0.0
    for n, (_sz, m) in tree_state().items():
        if not n.endswith(".rec"):
            continue
        if m >= since - 2 and m > bt:
            best, bt = os.path.join(RUNS, n), m
    return best


def header_of(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    out = {}
    for l in lines:
        t = l.split()
        if t and t[0] == "begin":
            break
        if len(t) >= 2:
            out.setdefault(t[0], " ".join(t[1:]))
    return out, lines


def mutate_bit(lines, clear=True):
    """-> the same lines with TF_MOVEOOR cleared (or set) in the header flags."""
    out = []
    for l in lines:
        t = l.split()
        if len(t) == 2 and t[0] == "flags":
            fv = int(float(t[1]))
            fv = fv & ~TF_MOVEOOR if clear else fv | TF_MOVEOOR
            l = "flags %d" % fv
        out.append(l)
    return out


def mutate_row(lines, val=9000):
    """-> the same lines with the first `in` row's move triple pushed over."""
    out, done = [], False
    for l in lines:
        t = l.split()
        if not done and t and t[0] == "in" and len(t) >= 7:
            t[4] = t[5] = t[6] = str(val)
            l = " ".join(t)
            done = True
        out.append(l)
    return out


def mutate_bound(lines, val=9000):
    """-> the same lines with the header's stated bound raised above every row.

    THIS is how you build "the bit is set and no row is over the bound", and it is
    worth being explicit about: the bound is the FILE's own statement, so the only
    honest way to make the rows fall under it is to move the statement.  Clearing
    the bit instead -- what the first cut of this arm did -- leaves the rows where
    they are and produces the STRONG direction's fault, i.e. a control that grades
    the other arm and reports a missing note."""
    out, done = [], False
    for l in lines:
        t = l.split()
        if not done and t and t[0] == "movebnd":
            l = "movebnd %g" % val
            done = True
        out.append(l)
    return out


def faults_of(lines, name):
    """-> (faults, notes) from reccheck for an in-memory file."""
    tmp = os.path.join(LOGDIR, name)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    try:
        r = reccheck.check_rec(tmp)
        return list(r.faults), list(r.notes), tmp
    finally:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--keep", action="store_true",
                    help="leave the mutated copies in ftesurf/logs/")
    a = ap.parse_args()

    if not os.path.exists(EXE):
        raise SystemExit("no engine at %s" % EXE)

    before = tree_state()
    res = os.path.join(ROOT, "ftesurf", "data", "resume", "bhop_eazy")
    if os.path.isdir(res):
        RESUME_BEFORE.update(os.listdir(res))
    bak = backup()
    try:
        return arms(a)
    finally:
        restore(bak, before)


def arms(a):
    print("=" * 72)
    print("ARMS A/B -- the shipped 450 as the control, 5000 as the subject")
    print("=" * 72)
    since, text = run_arm("p493move.cfg", "p493move")
    if not text:
        check(False, "the arm produced a log at all")
        raise SystemExit(1)

    pre = re.findall(r"P493 PRECONDITION.*", text)
    for l in pre:
        print("     %s" % l.strip())
    check(any("cl_forwardspeed 450" in l for l in pre),
          "P0 the control phase really ran at cl_forwardspeed 450 (precondition read back)")
    check(any("subject cl_forwardspeed 5000" in l for l in pre),
          "P0 the subject phase really ran at cl_forwardspeed 5000")

    rows = movebnd_lines(text)
    print("     %d `movebnd:` line(s) in the log" % len(rows))
    for r in rows:
        print("       bound %g  over %g  worst %g  moveoor %g" % r)
    if not check(len(rows) >= 4, "the diagnostic printed at all (>= 4 samples)"):
        raise SystemExit("no movebnd lines -- is this a build with Patch 493?")

    # The control phase prints three samples (two while +forward is held at 450,
    # one after), then the subject phase prints three more.
    ctl = rows[0]
    check(ctl[0] == 2000, "P1 the control reads the shipped bound, 2000")
    check(ctl[1] == 0 and ctl[3] == 0,
          "P1 the control counts nothing over it (over 0, moveoor 0)")
    check(ctl[2] == 450,
          "P1 ...and its worst is EXACTLY 450, so the move really reached the "
          "server (a control reading worst 0 would have measured nothing)")

    sub = rows[3]
    last = rows[-1]
    check(sub[1] > 0, "P2 the subject counted commands over the bound (over %g)" % sub[1])
    check(sub[2] >= 5000, "P2 ...and its worst is the value it sent (%g)" % sub[2])
    check(sub[3] == 1, "P2 ...and TF_MOVEOOR is set (moveoor 1)")
    check(last[1] > sub[1] or last == rows[4] if len(rows) > 4 else last[1] >= sub[1],
          "P2 `over` is a COUNT OF COMMANDS, so a later sample is not smaller "
          "(%g then %g)" % (sub[1], last[1]))

    print()
    print("  -- the finished run's own file (a noclip-tainted close, b88fin's route) --")
    rec = newest_rec(since)
    check(rec is not None,
          "P3 the flight finished the run and closed data/runs/bhop_eazy/main/cheat.rec")
    head = {}
    lines = []
    if rec:
        print("     %s" % rec)
        head, lines = header_of(rec)
        check(head.get("movebnd") == "2000",
              "P3 the header states the bound it applied (`movebnd %s`)"
              % head.get("movebnd"))
        fv = int(float(head.get("flags", "0")))
        check(bool(fv & TF_MOVEOOR),
              "P3 ...and `flags %d` carries TF_MOVEOOR (262144)" % fv)
        r = reccheck.check_rec(rec)
        check(not r.faults,
              "P3 reccheck.py faults nothing about it (%d fault(s)%s)"
              % (len(r.faults), (": " + r.faults[0]) if r.faults else ""))
        check(r.info.get("movebnd") == "2000",
              "P3 ...and it reports the bound it judged against")
        check(r.info.get("moveoor_bit") == "yes",
              "P3 ...and it read the bit out of the flags word, not out of the rows")
        print("     moveoor: %s" % r.info.get("moveoor"))

    print()
    print("  -- ARM D: the two tamper controls, which are the reason the")
    print("     cross-check is a check and not a claim --")
    if lines:
        f1, _n1, p1 = faults_of(mutate_bit(lines, clear=True), "p493-nobit.rec")
        check(any("does not say TF_MOVEOOR" in x for x in f1),
              "D1 the bit cleared while a row stays over the bound FAULTS")
        f2, _n2, p2 = faults_of(mutate_row(mutate_bit(lines, clear=True)),
                                "p493-bigrow.rec")
        check(any("does not say TF_MOVEOOR" in x for x in f2),
              "D2 a row pushed to 9000 in a file whose bit is clear FAULTS")
        f3, n3, p3 = faults_of(mutate_bound(mutate_bit(lines, clear=False)),
                               "p493-bitonly.rec")
        # ONLY THE NOTES ABOUT THIS BIT.  A real recording carries other notes (a
        # tainted class, an off-grid sample) and counting those would make this arm
        # pass or fail on something it is not about.
        n3 = [x for x in n3 if "TF_MOVEOOR" in x]
        for x in n3:
            print("       note: %s" % x)
        check(not f3 and len(n3) == 1 and "line cap" in n3[0],
              "D3 the bit alone, with no row over the bound, is a NOTE that names "
              "the honest causes (%d fault(s), %d note(s) about this bit)"
              % (len(f3), len(n3)))
        if not a.keep:
            for p in (p1, p2, p3):
                try:
                    os.remove(p)
                except OSError:
                    pass

    print()
    print("=" * 72)
    print("ARM C -- `+set run_movebound 0`: the off switch")
    print("=" * 72)
    since2, text2 = run_arm("p493off.cfg", "p493off",
                            extra=("+set", "run_movebound", "0"))
    rows2 = movebnd_lines(text2)
    for r in rows2:
        print("       bound %g  over %g  worst %g  moveoor %g" % r)
    if check(len(rows2) >= 2, "the off arm printed the diagnostic"):
        check(all(r == (0.0, 0.0, 0.0, 0.0) for r in rows2),
              "C1 every sample reads bound 0 / over 0 / worst 0 / moveoor 0 "
              "even with cl_forwardspeed 5000 held")
    rec2 = newest_rec(since2)
    check(rec2 is not None,
          "C3 the off arm still recorded and finished its own file")
    if rec2:
        print("     %s" % rec2)
        h2, _l2 = header_of(rec2)
        check("movebnd" not in h2,
              "C2 ...and that file carries NO `movebnd` key at all")
        r2 = reccheck.check_rec(rec2)
        check(r2.info.get("movebnd") == "not stated (no bound applied)",
              "C2 reccheck.py says the bound was not stated, rather than "
              "guessing one")
        check("not judged" in (r2.info.get("moveoor") or ""),
              "C2 ...and says the rows were not judged against a bound it does "
              "not have, rather than reporting a clean verdict")
        check(not any("TF_MOVEOOR" in x for x in r2.faults),
              "C2 ...and faults nothing about the absent key")

    print()
    print("=" * 72)
    print("%d checks, %d failed" % (len(PASSED) + len(FAILED), len(FAILED)))
    for w in FAILED:
        print("  FAIL %s" % w)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
