#!/usr/bin/env python3
"""p486injrn.py -- grade cfg/test/p486injrn.cfg, the Patch 486 consumer.

WHAT THE PATCH IS.  Engine Patch 484 computes the .hid's own angle identity
inside IN_Journal_View and publishes five read-only cvars.  It shipped with NO
CONSUMER, deliberately, because a gate that reads a counter nobody has ever seen
nonzero is a gate nobody can calibrate.  Patch 486 is that consumer: cl_replay.qc
reads the five and sends them over sendevent("injrn", ...), sv_timer.qc stores
them on the player entity, and `cmd timer` prints them.  Still no gate -- see the
IJ_* block in sh_defs.qc and BACKLOG item C.

WHY IT MATTERS AT ALL.  The fleet collects zero journals: measured on the live
host 2026-10-05, 19 receipts, 14 sidecars, 4 recordings and NO .hid, with both
lobby cfgs at `run_evidence_ul 1` (which uploads the .view and not the .hid).  At
110 KB/s the client's 4 MiB staging cap refuses any journal past ~38 s of run.
So every input check the tree built over the .hid ran only when an operator typed
a path at a file that is not there.  This is the verdict travelling instead of
the file.

WHAT THIS GRADES, and the one thing it cannot:

  1  THE CHANNEL IS ALIVE.  ARM 2's `frames` differs from ARM 1's.  This is the
     falsifier for a dead channel: sendevent composes "CSEv_" + name + one letter
     per argument and a server without that function answers SILENCE, which reads
     as "never spoke" and leaves every counter unchanged.  ARM 1 already prints
     -1, so ARM 2 must print something else or nothing was carried.

  2  -1 IS NOT 0.  ARM 1 reads -1 with no journal open, ARM 4 reads 0 after a
     journal that ran and governed nothing.  This is the exact defect Patch 484's
     own arm A caught -- an unmeasured state wearing a clean measurement's
     clothes -- and a consumer that normalised -1 to 0 on the way out would
     reintroduce it one layer up, invisibly.

  3  THE CONSOLE CANNOT WRITE IT.  ARM 3 does `setinfo injrn "0 999999 0 0 0 0"`
     and the server's `frames` must not become 999999.  This is the build-78/79
     argument, and it gets an arm rather than being assumed: a userinfo key is one
     typed line away from saying anything, a qcrequest is not.  Note there is
     deliberately NO diagnostic setinfo copy of this report (unlike rechid and
     inprof), so the key ARM 3 writes has no reader at all -- the arm still runs,
     because "a key nobody reads" and "the console can write the fact" are
     different statements and only the second would be a defect.

  4  THE SERVER'S NUMBER IS THE ENGINE'S NUMBER.  For every arm, `cmd timer`'s
     frames must equal what `in_jrn484_frames` printed locally in the same arm.
     Two ends of one channel, independently printed, and an off-by-one or a stale
     cache shows here rather than as a mystery later.

  5  THE RESET PROPAGATES.  ARM 4 opens a fresh journal, which resets the engine's
     counters, and the server must see the reset -- frames far below ARM 2's.  A
     cache that never re-sent would leave the server holding ARM 2's number.

  NOT GRADED, because it cannot be: NOTHING HERE CAN MAKE `viol` NONZERO.  A
  minimized harness cannot fire a WM_INPUT, so the subject -- injected or
  rewritten motion -- cannot be driven from inside a cfg.  This grader proves the
  counters are CARRIED, honest about what they have not measured, and unforgeable
  from a console.  It does NOT prove a server can see a violation.  Coverage of
  the rule itself is tools/p484ident.py Part 2, over 113 real journals.

Usage:  python tools/p486injrn.py [--log LOG]
Exit 0 when every registered prediction held.
"""
import argparse
import os
import re
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILED = []
CHECKS = 0


def check(what, got, want):
    """Record one prediction.  `want` may be a callable for a relational test."""
    global CHECKS
    CHECKS += 1
    if callable(want):
        ok = want(got)
        desc = getattr(want, "__doc__", None) or "predicate"
    else:
        ok = (got == want)
        desc = repr(want)
    if ok:
        print("ok   %s = %r" % (what, got))
    else:
        FAILED.append("%s: got %r, want %s" % (what, got, desc))
        print("FAIL %s: got %r, want %s" % (what, got, desc))


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

# `        jrnident: said 1  have 16  frames 183  ghosts 0  viol 0  bad 0  skip 0`
JRN_RE = re.compile(
    r"jrnident:\s+said\s+(-?[\d.]+)\s+have\s+(-?[\d.]+)\s+frames\s+(-?[\d.]+)"
    r"\s+ghosts\s+(-?[\d.]+)\s+viol\s+(-?[\d.]+)\s+bad\s+(-?[\d.]+)"
    r"\s+skip\s+(-?[\d.]+)")

CVAR_RE = re.compile(r'"in_jrn484_(\w+)"\s+is\s+"(-?[\d.]+)"')

ARM_RE = re.compile(r"P486 ARM (\d)")

SETINFO_RE = re.compile(r"SETINFO \w+: injrn=(.+)")


def num(s):
    f = float(s)
    return int(f) if f == int(f) else f


def parse_log(path):
    """Split the log into per-arm dicts of {jrnident fields} and {cvar readings}.

    Arms are delimited by the `P486 ARM n` banner, so a jrnident line belongs to
    the arm it was printed in.  A file with no banners yields nothing, which is
    graded as a failure rather than silently passing on an empty parse -- the
    shape that made two of Patch 403's arms look green.
    """
    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()

    arms = {}
    cur = 0
    arms[0] = {"jrn": [], "cvar": {}, "setinfo": []}
    for ln in lines:
        m = ARM_RE.search(ln)
        if m:
            cur = int(m.group(1))
            arms.setdefault(cur, {"jrn": [], "cvar": {}, "setinfo": []})
        m = JRN_RE.search(ln)
        if m and cur:
            arms[cur]["jrn"].append({
                "said": num(m.group(1)), "have": num(m.group(2)),
                "frames": num(m.group(3)), "ghosts": num(m.group(4)),
                "viol": num(m.group(5)), "bad": num(m.group(6)),
                "skip": num(m.group(7)),
            })
        m = CVAR_RE.search(ln)
        if m and cur:
            # last reading in the arm wins: ARM 2 prints the cvars AFTER the
            # journal closes, and an earlier read would be the pre-journal state.
            arms[cur]["cvar"][m.group(1)] = num(m.group(2))
        m = SETINFO_RE.search(ln)
        if m and cur:
            arms[cur]["setinfo"].append(m.group(1).strip())
    return arms


def jrn(arms, n, i=-1):
    """The i-th jrnident line of arm n, or None."""
    a = arms.get(n)
    if not a or not a["jrn"]:
        return None
    return a["jrn"][i]


def field(arms, n, k, i=-1):
    r = jrn(arms, n, i)
    return None if r is None else r.get(k)


# ---------------------------------------------------------------------------
# the arms
# ---------------------------------------------------------------------------

def grade(arms):
    # --- the parse itself is a check, because an empty parse must not pass ----
    found = sorted(n for n in arms if arms[n]["jrn"])
    check("arms that printed a jrnident line", found, [1, 2, 3, 4])

    # ===== ARM 1: no journal open.  The consumer exists, and -1 is not 0. ====
    a1 = jrn(arms, 1)
    check("1a the server prints a jrnident line at all", a1 is not None, True)
    if a1:
        check("1b said (the event arrived over qcrequest)", a1["said"], 1)
        check("1c have (all five cvars exist on a 484 engine)", a1["have"], 16)
        check("1d frames is -1, never measured", a1["frames"], -1)
        check("1d ghosts is -1", a1["ghosts"], -1)
        check("1d viol is -1", a1["viol"], -1)
        check("1d bad is -1", a1["bad"], -1)
        check("1d skip is -1", a1["skip"], -1)

    # ===== ARM 2: one journal.  THE CHANNEL IS ALIVE. =======================
    a2 = jrn(arms, 2)
    check("2 the server prints a jrnident line after a journal", a2 is not None, True)
    if a1 and a2:
        check("2a frames is no longer -1 (the subject acted)",
              a2["frames"] != -1, True)
        check("2b frames CHANGED from ARM 1 (not a dead channel)",
              a2["frames"] != a1["frames"], True)
        check("2b frames is positive", a2["frames"] > 0, True)
        check("2c viol 0 (honest input is not accused)", a2["viol"], 0)
        check("2c ghosts 0 (nothing moved without a cause)", a2["ghosts"], 0)
        check("2 said still 1", a2["said"], 1)
        check("2 have still 16", a2["have"], 16)

    # ===== ARM 3: the console writes the key nobody reads. ==================
    a3 = jrn(arms, 3)
    si = arms.get(3, {}).get("setinfo") or []
    check("3 the cfg actually issued the setinfo (else this arm proves nothing)",
          len(si) > 0, True)
    if si:
        check("3a the typed key is the hostile one", si[0], "0 999999 0 0 0 0")
    check("3 the server prints a jrnident line after it", a3 is not None, True)
    if a2 and a3:
        check("3b frames did NOT become 999999", a3["frames"] != 999999, True)
        check("3b frames is still the event's number", a3["frames"], a2["frames"])
        check("3b no other column moved either",
              (a3["said"], a3["have"], a3["ghosts"], a3["viol"], a3["bad"], a3["skip"]),
              (a2["said"], a2["have"], a2["ghosts"], a2["viol"], a2["bad"], a2["skip"]))

    # ===== ARM 4: a fresh journal resets, and the server sees it. ===========
    a4 = jrn(arms, 4)
    check("4 the server prints a jrnident line after the reset", a4 is not None, True)
    if a2 and a4:
        check("4 frames is far below ARM 2's (the reset propagated)",
              a4["frames"] < a2["frames"], True)
        check("4 frames is 0 and NOT -1 (measured clean, not unmeasured)",
              a4["frames"], 0)

    # ===== the two ends agree, in every arm that has both. ==================
    # The engine cvar is printed locally; the jrnident line is what the SERVER
    # was told.  These are two ends of one channel and must not drift.
    for n in (1, 2):
        cv = arms.get(n, {}).get("cvar") or {}
        r = jrn(arms, n)
        if cv and r:
            check("%d server frames == engine in_jrn484_frames" % n,
                  r["frames"], cv.get("frames"))
            check("%d server ghosts == engine in_jrn484_ghosts" % n,
                  r["ghosts"], cv.get("ghosts"))
            check("%d server viol == engine in_jrn484_violations" % n,
                  r["viol"], cv.get("violations"))
            check("%d server bad == engine in_jrn484_badframes" % n,
                  r["bad"], cv.get("badframes"))
            check("%d server skip == engine in_jrn484_skipped" % n,
                  r["skip"], cv.get("skipped"))

    # ===== -1 vs 0 IS THE WHOLE LESSON, so state it as one check. ===========
    if a1 and a4:
        check("the channel distinguishes never-measured (-1) from measured-clean (0)",
              (a1["frames"], a4["frames"]), (-1, 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.path.join(
        SURFDIR, "ftesurf", "logs", "p486injrn.log"))
    a = ap.parse_args()

    if not os.path.exists(a.log):
        print("FAIL no log at %s -- run cfg/test/p486injrn.cfg against "
              "cfg/test/p486sv.cfg first" % a.log)
        return 1

    print("grading %s" % a.log)
    arms = parse_log(a.log)
    grade(arms)

    print()
    if FAILED:
        print("%d checks, %d FAILED" % (CHECKS, len(FAILED)))
        for f in FAILED:
            print("  " + f)
        return 1
    print("%d checks, 0 failed" % CHECKS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
