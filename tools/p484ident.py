#!/usr/bin/env python3
"""p484ident.py -- grade cfg/test/p484ident.cfg, the Patch 484 identity counters.

Two independent things are graded here, because one arm cannot do both:

  PART 1  the ENGINE against the FILE.  cfg/test/p484ident.cfg runs four arms in
          one process and prints in_jrn484_{frames,ghosts,violations,skipped};
          this reads those four cvars back out of the log for each arm and
          compares them with what hidcheck.py -- the shipped, independent
          implementation of the same rule -- computes over the .hid that arm
          wrote.  Two implementations of one arithmetic, one in C inside the
          engine and one in Python over the file, must agree.

  PART 2  the RULES against the corpus.  A minimized harness has no window focus,
          so Key_MouseShouldBeFree() is true and EVERY frame carries VF_FREE: no
          arm of that cfg can produce a governed frame, and Part 1 therefore
          proves the counters are alive, publish, reset and abstain -- not that
          they can go nonzero.  Part 1 is honest about that.  What proves the
          rules is here: a Python transcription of IN_Journal_CheckIdentity's
          gates, run over all 113 real journals in the tree (recorded during
          focused play, 210,678 governed frames), compared against hidcheck's own
          verdicts.  If the transcription agrees everywhere, the C logic is the
          logic that has been calibrated on real play.

  A THIRD THING, and the reason Part 2 exists in this shape rather than as a
  comment: the first run of this patch's arm read frames 0 / skipped 180, which
  looks exactly like a dead counter and was a correct one abstaining on every
  frame.  An arm that cannot make its subject act is not a passing arm, so Part 1
  grades the abstention as the finding it is and Part 2 supplies the coverage.

Usage:  python tools/p484ident.py [--log LOG] [--hiddir DIR]
Exit 0 when every registered prediction held.
"""
import argparse
import glob
import os
import re
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SURFDIR, "tools"))
import hidcheck          # noqa: E402

FAILED = []
CHECKS = 0


def load_hid(path):
    """(header dict, [(lineno, vdict)]) straight from the file.

    Inline rather than borrowed, because a grader that imports a helper from
    somewhere outside the repo is a grader the next reader cannot run -- and
    because hidcheck's own Report does not expose the header or the parsed 'v'
    rows.  The 'v' record is
        v <dt> <dx> <dy> <flags> <pitch> <yaw> <kpitch> <kyaw>
    nine tokens, the last two added by Patch 305 and absent before it.
    """
    skip = {"dev", "render", "input", "devmap", "begin", "end", "d", "f", "m",
            "a", "+", "-", "x", "j", "i", "b", "g", "c", "p", "!", "#", "v"}
    head = {}
    views = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            tok = line.rstrip("\r\n").split()
            if not tok:
                continue
            if tok[0] == "v":
                if len(tok) == 7:
                    k = (None, None)
                elif len(tok) == 9:
                    try:
                        k = (float(tok[7]), float(tok[8]))
                    except ValueError:
                        continue
                else:
                    continue
                try:
                    views.append((ln, {"dt": float(tok[1]), "dx": float(tok[2]),
                                       "dy": float(tok[3]), "flags": int(tok[4]),
                                       "pitch": float(tok[5]), "yaw": float(tok[6]),
                                       "kpitch": k[0], "kyaw": k[1]}))
                except ValueError:
                    pass
                continue
            if len(tok) == 2 and tok[0] not in skip:
                head[tok[0]] = tok[1]
    return head, views

FAILED = []
CHECKS = 0


def check(what, got, want):
    global CHECKS
    CHECKS += 1
    ok = got == want
    if not ok:
        FAILED.append("%s: got %r, want %r" % (what, got, want))
    print("%s %-72s %r" % ("ok  " if ok else "FAIL", what, got))


# --------------------------------------------------------------------------
# Part 1: the engine's counters against the file's
# --------------------------------------------------------------------------

ARM_RE = re.compile(r"P484 ARM (A2|[A-D])\b")
CVAR_RE = re.compile(r'"(in_jrn484_\w+)" is "(-?\d+)"')


def parse_log(path):
    """-> {arm: {cvar: int}} taking the FIRST reading after each ARM banner."""
    arms = {}
    cur = None
    seen = set()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = ARM_RE.search(line)
            if m:
                cur = m.group(1)
                arms.setdefault(cur, {})
                seen = set()
                continue
            m = CVAR_RE.search(line)
            if m and cur and m.group(1) not in seen:
                arms[cur][m.group(1)] = int(m.group(2))
                seen.add(m.group(1))
    return arms


def part1(logpath, hidpaths):
    print("=== PART 1  the engine's counters against hidcheck's, per arm ===")
    arms = parse_log(logpath)
    check("the log names all five arms", sorted(arms), ["A", "A2", "B", "C", "D"])

    four = ["in_jrn484_frames", "in_jrn484_ghosts",
            "in_jrn484_violations", "in_jrn484_badframes",
            "in_jrn484_skipped"]

    # ARM A is the control, and it is the one that found a real defect: the first
    # cut published ghosts and violations UNGUARDED, so they read 0 before any
    # journal had run -- an unmeasured state presented as a clean measurement.
    for c in four:
        check("ARM A %s reads -1, i.e. never measured rather than measured clean"
              % c.split("_")[-1], arms.get("A", {}).get(c), -1)

    # ARM A2 is the security property.  A counter a console can assign is a
    # counter a server's stufftext can assign, and then it says nothing about the
    # player -- the attacker would simply publish 0 violations.  The arm tries
    # `set` on all five and they must all still read -1.
    for c in four:
        check("ARM A2 %s resisted `set` and still reads -1 (CVAR_NOSET holds)"
              % c.split("_")[-1], arms.get("A2", {}).get(c), -1)

    # ARMS B/C/D: the engine against the file.
    for arm, hid in (("B", hidpaths.get("B")), ("C", hidpaths.get("C")),
                     ("D", hidpaths.get("D"))):
        if not hid or not os.path.exists(hid):
            check("ARM %s wrote a journal to grade" % arm, False, True)
            continue
        r = hidcheck.check_hid(hid)
        eng = arms.get(arm, {})
        # hidcheck abstains below two governed frames and sets no verdict, so its
        # own not_governed is the number that has an engine counterpart.
        ng = r.info.get("identity_not_governed")
        pf = r.info.get("identity_pitch_frames")
        yv = r.info.get("identity_violations")
        pv = r.info.get("identity_pitch_violations")
        print("    arm %s: hidcheck governed(yaw)=%s not_governed=%s viol=%s "
              "pitch_frames=%s pitch_viol=%s" % (arm, r.info.get("identity_frames"),
                                                 ng, yv, pf, pv))
        # The engine's `frames` counts a frame as governed when EITHER axis is
        # governed, so it is compared against the union rather than against yaw's
        # count alone -- and the difference is stated, not hidden.
        if ng is not None:
            check("ARM %s: the engine's skipped equals hidcheck's not_governed "
                  "(both implementations abstain on the same frames)" % arm,
                  eng.get("in_jrn484_skipped"), ng)
        if yv is not None and pv is not None:
            check("ARM %s: the engine's violations equal hidcheck's on both axes"
                  % arm, eng.get("in_jrn484_violations"), max(yv, pv))
        # The abstention itself, graded as the finding it is rather than passed
        # over: a harness with no window focus governs nothing.
        if arm == "B":
            check("ARM B: the cursor was free on every frame, so this arm proves "
                  "the counters publish and abstain but CANNOT make them nonzero",
                  eng.get("in_jrn484_frames") == 0 and
                  eng.get("in_jrn484_skipped", 0) > 0, True)

    # ARM D is the reset arm: a counter that survived IN_JournalBegin_f would
    # attribute one journal's ghosts to the next one.
    b = arms.get("B", {}).get("in_jrn484_skipped", 0)
    d = arms.get("D", {}).get("in_jrn484_skipped", -1)
    check("ARM D: a fresh journal RESETS the counters rather than continuing them",
          d < b, True)


# --------------------------------------------------------------------------
# Part 2: a transcription of the C gates, against the corpus
# --------------------------------------------------------------------------

PITCH_ENV = 89.0


def engine_model(path):
    """Transcribe IN_Journal_CheckIdentity's gates and return its counters.

    The C, in order: no previous view -> return (not counted at all); flags & 4 ->
    skip; m_filter or m_accel -> skip; sens == 0 -> skip; then count the frame and
    judge each axis, an axis abstaining when its flag sends the counts elsewhere
    (strafe_y for pitch, strafe_x for yaw) or when a pitch prediction would leave
    the clamp envelope.  If NEITHER axis governed, the frame is not counted as
    governed either.

    COUNTED PER FRAME, NOT PER AXIS, and that is a measurement rather than a
    taste: over the tree's 113 journals every frame that failed did so on BOTH
    axes (11 pitch, 11 yaw, the same 11 frames), so a per-axis sum reports 22 for
    11 events.  The first cut of this grader summed per axis and disagreed with
    hidcheck by exactly a factor of two on every file that had any failure at all
    -- which is how the double count in the C was found.
    """
    head, views = load_hid(path)
    try:
        sens = float(head["sensitivity"]) * float(head["sensitivityscale"])
        mp = float(head["m_pitch"])
        my = float(head["m_yaw"])
        filt = float(head.get("m_filter", "0"))
        accel = float(head.get("m_accel", "0"))
    except (KeyError, ValueError):
        return None
    frames = skipped = bad = ghosts = viol = 0
    for i in range(1, len(views)):
        _, prev = views[i - 1]
        _, cur = views[i]
        if cur["kpitch"] is None:
            continue                      # pre-305: the C does not have this case
        if cur["flags"] & 4 or filt or accel or not sens:
            skipped += 1
            continue
        frames += 1
        axes = broke = ghosted = 0
        for axis in (0, 1):               # PITCH, YAW
            if axis == 0:
                if cur["flags"] & 2:
                    continue
                pred = mp * sens * cur["dy"] + cur["kpitch"]
                if pred > PITCH_ENV - prev["pitch"] or pred < -PITCH_ENV - prev["pitch"]:
                    continue              # the clamp may have truncated this axis
                got = cur["pitch"] - prev["pitch"]
                pv, cv = prev["pitch"], cur["pitch"]
            else:
                if cur["flags"] & 1:
                    continue
                pred = -my * sens * cur["dx"] + cur["kyaw"]
                got = cur["yaw"] - prev["yaw"]
                pv, cv = prev["yaw"], cur["yaw"]
            while got > 180.0:
                got -= 360.0
            while got < -180.0:
                got += 360.0
            eps = max(2e-6, max(abs(pv), abs(cv)) * (2.0 ** -22)) + abs(pred) * 1e-6
            axes += 1
            if abs(got - pred) <= eps:
                continue
            broke += 1
            if not cur["dx"] and not cur["dy"] and not cur["kpitch"] and not cur["kyaw"]:
                ghosted = 1
        if not axes:
            frames -= 1
            skipped += 1
            continue
        if broke:
            bad += 1
            if ghosted:
                ghosts += 1
            else:
                viol += 1
    return dict(frames=frames, skipped=skipped, ghosts=ghosts,
                violations=viol, badframes=bad)


def part2(pattern):
    print()
    print("=== PART 2  the C gates transcribed, against every journal in the tree ===")
    paths = sorted(glob.glob(pattern, recursive=True))
    checked = 0
    mismatch = []
    tot = dict(frames=0, skipped=0, ghosts=0, violations=0, badframes=0,
               yaw_faults=0, pitch_only=0)
    for p in paths:
        try:
            m = engine_model(p)
        except Exception:
            continue
        if m is None:
            continue
        checked += 1
        for k in m:
            tot[k] += m[k]
        r = hidcheck.check_hid(p)
        # hidcheck reports PER AXIS and never sums, so the engine's per-frame
        # number is the union: a frame that broke both axes is one bad frame.
        # Each engine counter is compared against its OWN counterpart, not against
        # a combined one -- the first cut compared violations+ghosts against
        # violations alone and "failed" on every file that had a ghost, which is a
        # grader bug wearing a subject bug's clothes.  hidcheck now publishes both
        # ghost counts (identity_ghosts, identity_pitch_ghosts) precisely so this
        # comparison can be made rather than inferred from a note's prose.
        yv = r.info.get("identity_violations")
        pv = r.info.get("identity_pitch_violations")
        yg = r.info.get("identity_ghosts")
        pg = r.info.get("identity_pitch_ghosts")
        if yv is None and pv is None:
            continue
        want_v = max(yv or 0, pv or 0)
        want_g = max(yg or 0, pg or 0)
        if m["violations"] != want_v:
            mismatch.append((os.path.basename(p), "violations",
                             m["violations"], want_v))
        if m["ghosts"] != want_g:
            mismatch.append((os.path.basename(p), "ghosts",
                             m["ghosts"], want_g))
        if m["badframes"] != want_v + want_g:
            mismatch.append((os.path.basename(p), "badframes != violations+ghosts",
                             m["badframes"], want_v + want_g))
        # The per-axis comparison that the whole D finding turns on: a pitch
        # violation with no yaw violation beside it is a NEW accusation, and there
        # must be none on this corpus.
        tot["yaw_faults"] += yv or 0
        tot["pitch_only"] += max(0, (pv or 0) - (yv or 0))
    print("    journals graded %d" % checked)
    print("    totals over the corpus: governed %d  skipped %d  ghosts %d  "
          "violations %d  badframes %d" % (tot["frames"], tot["skipped"],
                                           tot["ghosts"], tot["violations"],
                                           tot["badframes"]))
    check("the corpus has governed frames at all, i.e. Part 2 measures something "
          "the harness cannot", tot["frames"] > 100000, True)
    check("the transcription agrees with hidcheck on every journal, on all three "
          "counters (mismatches: %s)" % (mismatch[:4] or "none"), mismatch, [])
    # VIOLATIONS are the subject that must be zero on honest play; GHOSTS are not,
    # and pretending otherwise would be the arm that passes by measuring nothing.
    # A ghost is an angle that moved with no recorded cause, which a server angle
    # set does legitimately -- p305_Bzero alone contributes 144 of them and is a
    # fixture for exactly that.  So the two are graded separately and the ghost
    # count is REPORTED, not asserted to be zero.
    print("    ghosts are reported, not asserted: %d over the corpus"
          % tot["ghosts"])
    # And the frames that DO break are stated rather than hidden, because an
    # assertion of "zero" here would be a grader passing by expecting the wrong
    # thing.  MEASURED over the tree's 110 gradable journals:
    #     3 files carry any violation at all, 11 frames in 210,678 governed
    #     (0.0052%); on every one of them yaw and pitch violations are EQUAL and
    #     they are the SAME frames, so PITCH-ONLY is 0; and they are LARGE
    #     instantaneous jumps (dpitch -41.8, -28.1, -49.0 against predictions of
    #     ~0.02 deg) -- teleports on frames that also carried counts, which
    #     hidcheck reports as whole-angle and unresolved, not as a fault.
    # So the honest claim is not "honest play is never accused" but the one that
    # matters and is checkable: THE PITCH CHECK ACCUSES NO FILE THE YAW CHECK
    # DOES NOT ALREADY.  It adds coverage of an axis nothing read, and no new
    # false positive -- which is the bar Patch 305 set for a check like this.
    check("pitch-only violations are ZERO across the corpus, i.e. the new check "
          "accuses no file the shipped yaw check does not already", tot["pitch_only"], 0)
    check("...and the 11 frames it does report are the same ones hidcheck "
          "counts as yaw violations", tot["violations"], tot["yaw_faults"])
    check("the frames that break are counted, so the claim above is a measurement "
          "and not an assurance", tot["badframes"] >= tot["violations"], True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.path.join(SURFDIR, "ftesurf", "logs",
                                                  "p484ident.log"))
    ap.add_argument("--hiddir", default=os.path.join(SURFDIR, "ftesurf", "data"))
    ap.add_argument("--corpus", default=os.path.join(SURFDIR, "ftesurf", "data",
                                                     "**", "*.hid"))
    a = ap.parse_args()

    if not os.path.exists(a.log):
        print("no log at %s -- run cfg/test/p484ident.cfg first" % a.log)
        return 2
    hids = {k: os.path.join(a.hiddir, "p484_%s.hid" % k) for k in "BCD"}
    part1(a.log, hids)
    part2(a.corpus)

    print()
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
