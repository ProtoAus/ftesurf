#!/usr/bin/env python3
"""p470tick.py -- driver and grader for cfg/test/p470tick.cfg (Patch 470: a
replay is graded at the recording's own tick).

WHY A DRIVER.  The subject is a file whose tick is not the server's, and this
machine's only recording is 0.015 on a 0.015 map.  So this stages
ftesurf/data/p470tick.rec -- the source's samples under a header rewritten to
`tickrate`/`movetickrate` 0.01 -- runs the cfg, grades the log and REMOVES the
staged file, listing what is left.  The source is opened read-only.

    python tools/p470tick.py [--rec <path>] [--tick 0.01] [--exe ftesurf64.exe]
                             [--grade-only] [--timeout 420]

--rec must be a v4+ recording of the cfg's map with ramp and flat-air samples;
the default is the one this was written against.  The cfg's four seek times are
that file's flat-air stretches.

THE CONTROL is the fix compiled out with the `bar tick` print kept, built from
this tree with three hunks reverted:
    cl_lines.qc Line_Grade      tick = serverkeyfloat("pm_ticrate") (<= 0: PM_TICK)
    cl_watch.qc                 Line_Tick(slot, wt_lj_tick) back at the job's start
    cl_hud.qc HUD_DrawStrafe    no `if (rec_wt_on) tick = rec_wt_tickrate;`
The driver prints the csprogs hash it ran so the two sides can be told apart.

Exit 0 pass, 1 fail, 2 cannot grade.

RESULT (2026-10-03, the N100 laptop; surf_colin_blaster_69000 runid
20260930-085843-0 re-ticked to 0.01, server 0.015):
  fixed   csprogs 0A64AF906B245665    control 9CE0C4186E1071B8 (the three hunks out)
  T1  slot ticks 0.010 / 0.010         0.010 / 0.015 -- slot 1 alone, the job order
  T2  0 wrong of 4042 and 3914          428 wrong in each, all 428 matching the
                                        SERVER-tick model; the tick moves 428 points
  T3  0 of 1951 shared samples differ   261 differ; 255 unsaturated samples
  T4  4 seeks, 4 flat-air, 0 wrong      tick 0.015 at all 4
  The bar's ideal at 2080 u/s: 82.632 fixed, 55.088 control -- the ratio is 1.5,
  the tick ratio alone, as the cap-saturated gain predicts.  The screenshot shows
  the bar's target at 651/s, the logged ideal at that seek: ink, not only a print.
  Logs: ftesurf/logs/p470tick.log and .control (git-ignored; re-run to rebuild).
"""
import argparse
import hashlib
import math
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p453q                                        # noqa: E402  (the model)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAMEDIR, "logs", "p470tick.log")
STAGED = os.path.join(GAMEDIR, "data", "p470tick.rec")
CFGMAP = "surf_colin_blaster_69000"
SRC = os.path.join(GAMEDIR, "data", "resume", CFGMAP, "@local", "save000", "run.rec")
DEG = 180.0 / math.pi


def stage(src, tick):
    """The source's bytes with the two tick keys rewritten.  Refuses to overwrite."""
    if os.path.exists(STAGED):
        raise SystemExit("%s exists -- a previous run did not clean up; look at it "
                         "before removing it" % STAGED)
    seen, body, out = set(), False, []
    with open(src, "r", newline="", errors="surrogateescape") as f:
        for line in f:
            if not body:
                key = line.split(" ", 1)[0].strip()
                if key == "map" and line.split()[1] != CFGMAP:
                    raise SystemExit("%s is a recording of %s; the cfg loads %s"
                                     % (src, line.split()[1], CFGMAP))
                if key in ("tickrate", "movetickrate"):
                    eol = line[len(line.rstrip("\r\n")):]
                    line = "%s %g%s" % (key, tick, eol)
                    seen.add(key)
                if key == "begin":
                    body = True
            out.append(line)
    if "tickrate" not in seen:
        raise SystemExit("%s has no tickrate key to rewrite" % src)
    with open(STAGED, "w", newline="", errors="surrogateescape") as f:
        f.writelines(out)


def unstage():
    os.remove(STAGED)                               # an error here is the result
    left = [n for n in os.listdir(os.path.dirname(STAGED)) if "p470" in n]
    print("cleanup: staged file removed; p470 names left in data/: %s" % (left or "none"))
    return not left


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", "test/p470tick.cfg"], cwd=ROOT,
                         creationflags=flags, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the run did not exit in %g s -- killed" % timeout)


def parse(log):
    lines = [re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", r.rstrip("\n"))
             for r in open(log, "r", errors="replace")]
    out = {"live": None, "bars": [], "blocks": {}, "done": False, "focus": 0}
    cur, mv, sect = None, {}, None
    for line in lines:
        f = line.split()
        m = re.search(r"=== p470tick (\w+)(?: (\d))? ===", line)
        if m:
            sect = m.group(1)
            if sect == "done":
                out["done"] = True
            cur = None
            if sect in ("grade", "energy"):
                cur = {"pts": [], "closed": False, "mv": {}, "n": -1, "stride": 0}
                out["blocks"][(sect, int(m.group(2)))] = cur
            continue
        if "[focus] window is foreground" in line:
            out["focus"] += 1
        m = re.match(r'"pm_ticrate" is "([^"]+)"', line)
        if m and sect == "live":
            out["live"] = float(m.group(1))
        m = re.match(r"\s*bar tick (\S+)\s+ideal (\S+)\s+speed (\S+)\s+regime (\S+)", line)
        if m and sect == "bar":
            out["bars"].append(tuple(float(x) for x in m.groups()))
        if cur is None:
            continue
        if line.startswith("lnmv ") and len(f) >= 7:
            cur["mv"].update(tick=float(f[1]), airaccel=float(f[2]), accel=float(f[3]),
                             maxspeed=float(f[4]), aircap=float(f[5]),
                             gravity=float(f[6]))
        elif line.startswith("lnmv2 ") and len(f) >= 5:
            cur["mv"].update(gfric=float(f[1]), stopspeed=float(f[2]),
                             duck=float(f[3]), ghold=float(f[4]))
        elif line.startswith("lncb ") and len(f) >= 5:
            cur["n"], cur["stride"] = int(float(f[3])), int(float(f[4]))
        elif line.startswith("lnc ") and len(f) >= 7:
            cur["pts"].append((int(float(f[1])), float(f[2]), float(f[6]),
                               (float(f[3]), float(f[4]), float(f[5]))))
        elif line.startswith("lnce"):
            cur["closed"] = True
    return out


def differs(a, b, tol):
    if a < 0 or b < 0:
        return (a < 0) != (b < 0)
    return abs(a - b) > tol


def grade(src, ftick):
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log at %s" % LOG)
        return 2
    d = parse(LOG)
    need = [("grade", 0), ("grade", 1), ("energy", 0), ("energy", 1)]
    for k in need:
        b = d["blocks"].get(k)
        want = -1 if not b or b["stride"] < 1 else (b["n"] + b["stride"] - 1) // b["stride"]
        if not b or not b["closed"] or len(b["pts"]) != want or len(b["mv"]) < 10:
            print("CANNOT GRADE: the %s dump of slot %d is missing or incomplete" % k)
            return 2
    if not d["done"] or d["live"] is None or not d["bars"]:
        print("CANNOT GRADE: done %s, live tick %s, %d bar line(s)"
              % (d["done"], d["live"], len(d["bars"])))
        return 2
    if abs(d["live"] - ftick) < 1e-6:
        print("CANNOT GRADE: the server's tick IS the file's (%g); nothing differs"
              % ftick)
        return 2
    if d["focus"]:
        print("NOTE: %d `[focus] window is foreground` line(s) -- someone was at "
              "the machine during this run" % d["focus"])

    rows = p453q.samples(src)
    off = next((i for i, r in enumerate(rows) if r["t"] >= 0), len(rows))
    g0, g1 = d["blocks"][("grade", 0)], d["blocks"][("grade", 1)]
    mvf = dict(g0["mv"], tick=ftick)
    want = p453q.grades(rows, mvf)
    live = p453q.grades(rows, dict(g0["mv"], tick=d["live"]))
    fails = 0

    def verdict(ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print("%s %s" % ("PASS" if ok else "FAIL", text))

    t0, t1 = g0["mv"]["tick"], g1["mv"]["tick"]
    verdict(abs(t0 - ftick) < 1e-5 and abs(t1 - ftick) < 1e-5,
            "T1  slot ticks %.5f and %.5f, the file's %.5f (server %.5f)"
            % (t0, t1, ftick, d["live"]))

    # slot 0's point i is sample i; slot 1's point j is sample off + j, and its
    # point 0 has nothing to have turned from.
    def against(pts, base):
        bad, moved, aslive = [], 0, 0
        for i, t, q, _ in pts:
            k = base + i
            if k >= len(rows) or abs(t - rows[k]["t"]) > 0.00051:
                return None, 0, 0
            w = -1.0 if (base and i == 0) else want[k]
            lv = -1.0 if (base and i == 0) else live[k]
            if differs(q, w, 0.01):
                bad.append(i)
            if differs(w, lv, 0.01):
                moved += 1
                if not differs(q, lv, 0.01):
                    aslive += 1
        return bad, moved, aslive

    b0, m0, l0 = against(g0["pts"], 0)
    b1, m1, l1 = against(g1["pts"], off)
    if b0 is None or b1 is None or g0["n"] != len(rows):
        print("CANNOT GRADE: a slot's points are not the file's samples "
              "(slot 0 holds %d, the file %d)" % (g0["n"], len(rows)))
        return 2
    verdict(not b0 and not b1 and m0 >= 20 and m1 >= 20,
            "T2  grades at the file's tick: slot 0 %d wrong of %d, slot 1 %d wrong "
            "of %d; the tick moves the grade at %d and %d of those points"
            % (len(b0), len(g0["pts"]), len(b1), len(g1["pts"]), m0, m1))
    print("     of the moved points, matching the SERVER-tick model: slot 0 %d, "
          "slot 1 %d" % (l0, l1))

    e0 = {i: rgb for i, _, _, rgb in d["blocks"][("energy", 0)]["pts"]}
    e1 = d["blocks"][("energy", 1)]["pts"]
    shared = [(i, rgb, e0[off + i]) for i, _, _, rgb in e1[3:-3] if off + i in e0]
    bad3 = [i for i, a, b in shared if max(abs(x - y) for x, y in zip(a, b)) > 0.0011]

    def unsat(rgb):                 # 0 < |f| < 1 on Line_ColEnergy's ramp
        f = max(abs(rgb[0] - 0.85) / 0.55, abs(rgb[1] - 0.85) / 0.60)
        return 0.02 < f < 0.98 and abs(rgb[2] - 0.85) > 0.01
    live3 = sum(1 for _, _, b in shared if unsat(b))
    verdict(not bad3 and live3 >= 20,
            "T3  energy colour, slot 1 against slot 0: %d shared samples, %d differ; "
            "%d of them unsaturated (a different ceiling would show there)"
            % (len(shared), len(bad3), live3))

    badbar, flat = [], 0
    for tick, ideal, speed, regime in d["bars"]:
        if abs(tick - ftick) > 1e-5:
            badbar.append("tick %.5f" % tick)
        elif regime == 0 and ideal > 0:
            flat += 1
            gain = min(g0["mv"]["airaccel"] * g0["mv"]["maxspeed"] * ftick * 0.25,
                       g0["mv"]["aircap"])      # the cap binds even at fric 0.25
            exp = math.atan2(gain, max(speed, 1)) * DEG / ftick
            if abs(ideal - exp) > 0.005 * exp + 0.002:
                badbar.append("ideal %.3f at %.1f u/s, want %.3f" % (ideal, speed, exp))
    verdict(not badbar and flat >= 2,
            "T4  the bar: %d seek(s), %d in flat air graded, %d wrong%s"
            % (len(d["bars"]), flat, len(badbar),
               "  (%s)" % "; ".join(badbar[:4]) if badbar else ""))
    print("4 check(s), %d failed" % fails)
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", default=SRC)
    ap.add_argument("--tick", type=float, default=0.01)
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=420)
    a = ap.parse_args()
    if not a.grade_only:
        with open(os.path.join(GAMEDIR, "csprogs.dat"), "rb") as f:
            print("csprogs %s" % hashlib.sha256(f.read()).hexdigest()[:16].upper())
        stage(a.rec, a.tick)
        try:
            run(a.exe, a.timeout)
        finally:
            clean = unstage()
        if not clean:
            return 1
    return grade(a.rec, a.tick)


if __name__ == "__main__":
    sys.exit(main())
