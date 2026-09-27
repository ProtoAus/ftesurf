"""p455hold.py -- grade the hold refusal Patch 455 added and no arm has driven.

Runs cfg/test/p455hold.cfg and reads ftesurf/logs/p455hold.log.  Requires Patch
455 rounds 5+6 (the reason codes); on an earlier build every check reports NOT
DEMONSTRATED rather than failing, because an arm that goes red on a build which
predates its subject teaches nobody anything.

THE THREE VERDICTS ARE THE POINT.  "No held refusal" has two meanings -- the
branch is broken, or a premise never held -- and they want different answers.
So each premise is graded from evidence that does NOT come from the gate:

  the tag survived the load   `cmd timer`'s own hopped field
  the hold landed             two viewpos lines under +forward, identical
  the window stayed open      no take before the release

Only when all three hold does an absent refusal mean the branch is wrong.

  python tools/p455hold.py              run it, then grade
  python tools/p455hold.py --grade-only grade the log that is already there

It parks ftesurf/data/saves/bhop_eazy while it runs, because this arm writes a
save there and p448fin's fixture lives in the same directory.  --keep leaves the
staged files in place for inspection.
"""
import argparse
import os
import re
import shutil
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")
CFG = "test/p455hold.cfg"
ZONES = os.path.join(GAMEDIR, "maps", "zones", "local", "bhop_eazy.json")
SAVES = os.path.join(GAMEDIR, "data", "saves", "bhop_eazy")
LOG = os.path.join(GAMEDIR, "logs", "p455hold.log")
PARKED = SAVES + ".parked-p455hold"

# Patch 455's gate, final spellings (rounds 5+6).  Anchored on the EVENT rather
# than on a clause of the reasoning: round 6 reworded the reasoning and an arm
# anchored on it read "absent" on a build where the branch had demonstrably run.
HELD = r"is held, so the forgiveness is NOT measured"
# Patch 455's hold dprint (ce6edee): the row, the speed parked, the movetype
# returned.  It is what separates "took and parked 260" from "took and parked
# nothing" -- a distinction that was invisible, and wrong here for three runs.
HOLDTOOK = r"hold: took on row (\d+), parking ([\d.]+) u/s"
# Round 8 split the old "still moving" into three codes with three lines, which
# is what makes H6 anchorable at all -- before it, an over-cap refusal straight
# after an airborne one was swallowed by the said-once latch.
NOTGND = r"NOT taken -- not grounded: ([\d.]+) u/s, vz (-?[\d.]+)"
RISING = r"NOT taken -- rising: vz (-?[\d.]+)"
OVERCAP = r"NOT taken -- over the cap: ([\d.]+) u/s against the mover's ([\d.]+)"
PENDING = r"NOT taken -- an action aimed at this player is pending"
SETTLING = r"NOT taken -- at rest but settling: ([\d.]+) s of ([\d.]+), (\d+) clear reads of (\d+)"
TAKEN = r"hopped-start taint cleared -- "
DWELT = r"at rest for ([\d.]+) s over (\d+) clear reads"
# Round 8b: a refusal that breaks a PROGRESSED streak says what it broke, so a
# failure to take is diagnosable.  Absent when the streak never progressed --
# which is itself the other diagnosis.
BROKE = r"clear streak broke at ([\d.]+) s over (\d+) reads, reason (\d)"
HOPPED = r"hopped\s+(\d)"
VIEWPOS = r"(?:viewpos|Position)\D*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)"

DWELL_MIN = 0.25
READS_MIN = 8


def sha(path):
    import hashlib
    if not os.path.exists(path):
        return "<missing>"
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16].upper()


def stage():
    """The fixture's zones, and this arm's save directory out of the way."""
    if not os.path.exists(os.path.join(CFGDIR, "p448.zones.json")):
        raise SystemExit("p448.zones.json is missing -- this arm shares p448fin's "
                         "fixture geometry and cannot build its own")
    os.makedirs(os.path.dirname(ZONES), exist_ok=True)
    if os.path.exists(ZONES):
        shutil.copyfile(ZONES, ZONES + ".parked-p455hold")
    shutil.copyfile(os.path.join(CFGDIR, "p448.zones.json"), ZONES)
    if os.path.exists(PARKED):
        raise SystemExit("%s already exists -- a previous run did not restore. "
                         "Move it back by hand rather than letting this one "
                         "overwrite a fixture." % os.path.relpath(PARKED, ROOT))
    if os.path.exists(SAVES):
        os.rename(SAVES, PARKED)
    print("staged zones; parked %s" % os.path.relpath(SAVES, ROOT))


def restore(keep):
    if keep:
        print("--keep: staged files left in place")
        return
    if os.path.exists(SAVES):
        shutil.rmtree(SAVES, ignore_errors=True)
    if os.path.exists(PARKED):
        os.rename(PARKED, SAVES)
    if os.path.exists(ZONES + ".parked-p455hold"):
        shutil.move(ZONES + ".parked-p455hold", ZONES)
    elif os.path.exists(ZONES):
        os.remove(ZONES)
    print("restored the save directory and the zones override")


def sections(path):
    out, cur = {}, None
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            m = re.search(r"==== (\S+)\b", line)
            if m:
                cur = m.group(1)
                out[cur] = []
                continue
            if cur:
                out[cur].append(line.rstrip("\n"))
    return {k: "\n".join(v) for k, v in out.items()}


def grade():
    if not os.path.exists(LOG):
        print("FAIL no log at %s -- the run produced nothing" % LOG)
        return False
    sec = sections(LOG)
    whole = "\n".join(sec.values())
    out, bad, undemo = [], 0, 0

    def verdict(name, state, detail):
        nonlocal bad, undemo
        if state == "FAIL":
            bad += 1
        elif state == "NOT DEMONSTRATED":
            undemo += 1
        out.append("%-17s %-3s %s" % (state, name, detail))

    # -- is this even a Patch 455 build? ------------------------------------
    if not re.search(r"forgiveness is armed and NOT taken|" + HELD, whole):
        verdict("H0 reason codes", "NOT DEMONSTRATED",
                "no 455 refusal line anywhere: this build predates the reason "
                "codes, so nothing below can be judged")
        print("\n".join(out))
        return None

    # -- H1 the tag's premise, measured at three points ----------------------
    # The LAST reading in each section, not the first.  Section C prints a
    # `start:` block before the tag is earned and another after it, so the first
    # match reads `hopped 0` on a run where the tag went up -- which reported
    # 0/0/1 and looked like the load had cleared it (run 3).
    def last_hopped(name):
        m = re.findall(HOPPED, sec.get(name, ""))
        return m[-1] if m else "?"

    trio = (last_hopped("S"), last_hopped("C"), last_hopped("H"))
    if trio == ("0", "1", "1"):
        verdict("H1 tag premise", "PASS",
                "hopped 0 at the save, 1 after the chain, 1 after the load -- "
                "the load's raise-only path measured, not traced")
    else:
        verdict("H1 tag premise", "NOT DEMONSTRATED",
                "hopped reads %s/%s/%s at save/chain/load; wanted 0/1/1. A 0 at "
                "the load means the load cleared the tag and the gate never ran"
                % trio)

    # -- H2 the hold landed, and WHY it is usually not needed -----------------
    #
    # This was designed as two viewpos lines that must match.  They cannot:
    # `viewpos` is a CLIENT command, so a server log carries `Sending stringcmd
    # viewpos` and `Client command: viewpos` and never the coordinates (run 3,
    # four such lines, no numbers).  There is no server-side substitute either --
    # SV_SaveLocHold sprints on its refusals and prints nothing when it TAKES.
    #
    # It is only needed when reason 1 is ABSENT, to tell "the branch is broken"
    # from "the hold never landed".  When reason 1 fires it is moot: the gate
    # read one of run_pmhold / rec_sl_hold / MOVETYPE_NONE as true, and this arm
    # drives none of the others, so the refusal IS the hold landing.
    took = re.search(HOLDTOOK, sec.get("H", "")) or re.search(HOLDTOOK, whole)
    held_seen = re.search(HELD, sec.get("H", ""))
    pos = re.findall(VIEWPOS, sec.get("H", ""))
    asked = len(re.findall(r"Client command: viewpos", sec.get("H", "")))
    if took:
        parked = float(took.group(2))
        frozen = True
        # The speed is graded, not just the fact of the hold: a hold parking
        # 0.000 makes H3 vacuous (it refuses a body that was already still) and
        # makes H6 impossible (nothing to be over the cap with).
        verdict("H2 hold landed", "PASS" if parked > 100 else "FAIL",
                "took on row %s parking %.3f u/s%s"
                % (took.group(1), parked,
                   "" if parked > 100 else
                   " -- a hold that parks nothing refuses a body that was "
                   "already still, so H3 proves less than it looks and H6 "
                   "cannot fire at all. The save was taken stationary."))
    elif held_seen:
        frozen = True
        verdict("H2 hold landed", "PASS",
                "reason 1 fired, which is the gate reading a hold flag set. "
                "No `hold: took` line, so this build predates ce6edee and the "
                "PARKED SPEED is unknown -- H3 may be refusing a still body")
    elif len(pos) >= 2:
        a, b = pos[0], pos[1]
        frozen = all(abs(float(x) - float(y)) < 0.5 for x, y in zip(a, b))
        verdict("H2 hold landed", "PASS" if frozen else "NOT DEMONSTRATED",
                "origin %s -> %s under +forward%s"
                % (" ".join(a), " ".join(b),
                   "" if frozen else " -- it MOVED, so sl_hold did not take"))
    else:
        frozen = False
        verdict("H2 hold landed", "NOT DEMONSTRATED",
                "unanswerable today: %d viewpos asked and 0 answered, because "
                "viewpos is client-side and SV_SaveLocHold prints nothing when "
                "it takes. Needs a dprint at the hold (ftesurf-a1 owns it)"
                % asked)

    # -- H3 the branch itself -------------------------------------------------
    held = re.search(HELD, sec.get("H", ""))
    if held:
        verdict("H3 held refusal", "PASS",
                "reason 1 fired while the body was frozen")
    elif not frozen or trio != ("0", "1", "1"):
        verdict("H3 held refusal", "NOT DEMONSTRATED",
                "absent, but a premise above did not hold -- fix the premise "
                "before reading this as a defect")
    else:
        verdict("H3 held refusal", "FAIL",
                "every premise held and the gate did not refuse: finfgv, the "
                "tag and the hold were all up and the branch stayed silent")

    # -- H4 the dwell, after the release ---------------------------------------
    rel = sec.get("R", "")
    s = re.search(SETTLING, rel)
    t = re.search(DWELT, rel) or re.search(DWELT, whole)
    if not re.search(TAKEN, whole):
        verdict("H4 take", "FAIL", "the forgiveness was never taken at all")
    elif not t:
        verdict("H4 take", "NOT DEMONSTRATED",
                "taken, but without the streak numbers -- a pre-dwell build")
    else:
        el, rd = float(t.group(1)), int(t.group(2))
        ok = el >= DWELL_MIN and rd >= READS_MIN
        verdict("H4 take", "PASS" if ok else "FAIL",
                "at rest %.3f s over %d reads (floor %.2f / %d)%s"
                % (el, rd, DWELL_MIN, READS_MIN,
                   "" if ok else " -- under the floor, so the dwell did not run"))
    # 8b's diagnostic, reported either way: it separates "got to N and something
    # broke it" from "never got past 1", which used to be one silent outcome.
    br = re.findall(BROKE, whole)
    if br:
        out.append("%-17s %-3s %s" % ("reported", "--",
                   "streak broken %d time(s), furthest %s s over %s reads "
                   "(reason %s)" % (len(br), max(br, key=lambda x: float(x[0]))[0],
                                    max(br, key=lambda x: int(x[1]))[1],
                                    br[-1][2])))
    else:
        out.append("%-17s %-3s %s" % ("reported", "--",
                   "no streak-break line: either nothing broke a progressed "
                   "streak, or this build predates 8b"))

    verdict("H4b settling", "PASS" if s else "NOT DEMONSTRATED",
            "reason 4 seen after the release" if s else
            "no settling refusal: with the dwell compiled out that branch is "
            "unreachable, so this is the dwell's own discriminator")

    # -- H5 order ---------------------------------------------------------------
    ih = whole.find("is held, so the forgiveness")
    it = whole.find("hopped-start taint cleared")
    if ih < 0 or it < 0:
        verdict("H5 order", "NOT DEMONSTRATED", "one of the two lines is absent")
    else:
        verdict("H5 order", "PASS" if ih < it else "FAIL",
                "held before taken" if ih < it else
                "the take came BEFORE the hold -- the window closed early and "
                "H3 measured nothing")

    # -- H6 the ABOVE-CAP clause, which had never refused anything -----------
    #
    # Reason 2 is three clauses with one voice -- !ong, evz > 0 and speed > cap
    # -- and the latch says a reason once, so an above-cap refusal straight
    # after an airborne one is silent.  Section M puts reason 1 between them by
    # releasing out of the hold, and grades on `ground 1` with the speed over
    # the cap, which is the only way to tell the clauses apart in a log.
    over = re.search(OVERCAP, sec.get("M", ""))
    airborne = re.search(NOTGND, sec.get("M", ""))
    if over:
        verdict("H6 above cap", "PASS",
                "%s u/s against the mover's %s, grounded and level -- the "
                "clause refusing for the first time"
                % (over.group(1), over.group(2)))
    elif airborne:
        verdict("H6 above cap", "NOT DEMONSTRATED",
                "the body was AIRBORNE in M (%s u/s, vz %s), so the over-cap "
                "clause was never offered the chance -- the keys are still "
                "down when the hold releases"
                % (airborne.group(1), airborne.group(2)))
    else:
        verdict("H6 above cap", "NOT DEMONSTRATED",
                "no refusal in M at all: either the cap change did not reach "
                "the server or the release handed back no speed")

    # the incidental one, reported and never graded (p448fin's own finding)
    mv = re.search(NOTGND, whole)
    out.append("%-17s %-3s %s" % ("reported", "--",
               "not-grounded refusal %s%s"
               % ("seen" if mv else "not seen",
                  " at %s u/s, vz %s" % mv.groups() if mv else
                  " (incidental: it needs an airborne packet to be observed "
                  "between the arm and the take, and that varies between runs "
                  "of the same build)")))

    print("\n".join(out))
    print("%d check(s): %d failed, %d not demonstrated"
          % (len(out) - 1, bad, undemo))
    return bad == 0 and undemo == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    if a.grade_only:
        return 0 if grade() else 1

    ran = [(d, sha(os.path.join(GAMEDIR, d))) for d in ("qwprogs.dat", "csprogs.dat")]
    for d, h in ran:
        print("%-12s %s" % (d, h))
    stage()
    try:
        if os.path.exists(LOG):
            os.remove(LOG)
        flags = 0x08000000 if os.name == "nt" else 0
        # FORCE THE GAMEMODE, as tools/p448fin.py:80 does, and the first run is why.
        # bhop_eazy's own mode is `bhop`, where the start rule is `start on jump` and
        # run_starthop is off -- so the tag can never be earned, `hopped` read 0 at every
        # section, no forgiveness was ever armed, and H0 reported "no 455 refusal line
        # anywhere: this build predates the reason codes" on a build that has them.
        # The arm was right to refuse a verdict; it was looking at a server that could not
        # produce the condition.  `SERVERINFO: gamemode=bhop` in the log is the tell.
        p = subprocess.Popen([os.path.join(ROOT, a.exe), "-WindowStyle", "Minimized",
                              "+set", "sv_gamemode", "surf",
                              "+exec", CFG], cwd=ROOT, creationflags=flags,
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
    good = grade()
    if os.path.exists(LOG):
        shutil.copyfile(LOG, LOG + ".kept")
        with open(LOG + ".kept.hash", "w") as fh:
            for d, h in ran:
                fh.write("%s %s\n" % (d, h))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
