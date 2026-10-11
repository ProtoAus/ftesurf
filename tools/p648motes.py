#!/usr/bin/env python3
"""p648motes.py -- driver and grader for cfg/test/p648motes.cfg (Patch 648:
func_dustmotes drawn the way Source draws them).

    python tools/p648motes.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 300]

WHAT IS MEASURED, AND WHY BLACK MOTES.  A volume's motes are at depths nobody
knows, so the cfg stands rows of them at depths it chose (emit_mote) in front of
a wall it photographed bare first.  Most rows are BLACK: a black mote only
darkens what is behind it, by (1 - coverage) in linear light, so

        coverage = 1 - (shot / bare wall) ^ 2.2

for every pixel, whatever the wall looks like.  From that map, per mote:

  SIZE     the area above half its peak.  Source's sprite is solid to a quarter
           of its half-side h and falls in a line to nothing at 1.17 h, so that
           is a disc of radius 0.71 h, and h is size / 10000 of the depth -- so
           the SAME pixels at depth 150 and depth 330 (c_func_dust.cpp:73, :234).
           Row E's sizes are drawn between 50 and 150 and must differ.
  FADE     the peak: Alpha, times the sine through the life (:58-59), times
           1 - depth / DistMax (:68).  Shot 1 is a sixth of the way through a
           life of 8 s, where the sine is at a quarter and a straight ramp
           would be at a third; shot 2 is half way.  Row G's lives are drawn
           between 4 and 12 s and must differ; row F is Frozen and must not
           move between the shots; row X is past its DistMax and must be gone;
           shot n0, past every life of the first set, must be the bare wall.
  AT ANY SIZE  the total coverage of a size-20 mote, three pixels across, is a
           twenty-fifth of a size-100 one's: the small one is the same shape
           seen smaller, not a few texels' worth of whatever the centres hit.
  UPRIGHT  mote S is one of size 300.  Source's square is the screen's, so in
           the ring just outside it there is coverage towards its corners (the
           round falloff runs to 1.17 h) and none towards its sides.  The engine
           turns an r_part particle to a random angle unless the block says not to.
  (COLOUR  moved to tools/p657bright.py with Patch 657, which reads rows like
           D and W over walls of one flat colour.)
  POOL     Source keeps 2,048 old-style particles alive in the whole world
           (particle_iterators.h:20).  On surf_psychedelia, whose three stacked
           volumes ask for 7,200, the engine's own count (r_partinfo) is read
           once the longest life has passed.  The engine carries every particle
           to LifetimeMax (15 s) where a mote lives 12 on average, so a full
           pool reads 2,048 * 15 / 12 there.
  RESTART  after vid_restart the looks answer again, and four seconds later the
           engine holds more motes than it did.

And the subject's own lines: the three looks the map's volumes ask for, all
answering the engine's query; and, with vbsp_emit_motes 0, the reason for the orbs.

WHAT THIS DOES NOT SEE: that 0.25 / 1.17 is particle/sparkles' shape (that is
tools/sparkleshape.py against the .vtf), a mote's drift, the hold under 0.6 px
(the smallest row is 1.5 px), and the two shots of V and O, which are for eyes.

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade (the run did not finish, a real
window was brought in front of it, or this client draws the orbs anyway).

THE CONTROL, run by hand and recorded in the patch entry: the shader's depth term
taken out (`mote.x * depth` written as `mote.x * 150.0`), which is a mote of a
fixed size in the world -- the old blocks' kind -- and the pool's scale left at 1
(`dm_thr = DM_POOL / dm_alive` deleted).  SIZE must then fail at 330, and P's count.
And a second one: the block's `rotation 0` deleted and the blend put back on its
first anchors (black and white).  UPRIGHT must fail.  (Row W's COLOUR failed
too; Patch 657 took those anchors on purpose and that check went with it.)
"""
import argparse
import hashlib
import math
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAMEDIR, "logs", "p648motes.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")

# The cfg's rows: name -> (depth, rise, count, right).  Motes 0.06 of the depth
# apart; life 8 s, DistMax 1000, Alpha 255 unless the cfg's header says otherwise.
ROWS = {
    "A": (150, 0.17, 4, -0.15), "W": (150, 0.17, 4, 0.15),
    "B": (330, 0.10, 4, -0.15), "S": (150, 0.10, 1, 0.15),
    "C": (150, 0.04, 4, -0.15), "D": (150, 0.04, 4, 0.15),
    "E": (150, 0.17, 9, 0.0),
    "G": (150, 0.10, 9, 0.0),
    "F": (150, 0.04, 4, -0.15), "X": (330, 0.04, 4, 0.15),
}
DISTMAX = 1000.0
POOL = 2048         # MAX_TOTAL_PARTICLES
POOL_HELD = 15 / 12.0   # stage P: the engine holds LifetimeMax, a mote lives the mean


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p648motes_"):
            os.remove(os.path.join(SHOTS, name))
    # Minimised and NOT activated: the owner is using this desktop.
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7              # SW_SHOWMINNOACTIVE
    p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p648motes.cfg"],
                         cwd=ROOT, startupinfo=si,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the run did not exit in %g s -- killed" % timeout)


def stages(log):
    out, cur = {"all": []}, None
    for raw in open(log, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        m = re.search(r"=== (\w) (.*)", line)
        if m:
            cur = m.group(1) + " " + m.group(2).strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
        out["all"].append(line)
    return out


def first(lines, pattern):
    for line in lines:
        m = re.search(pattern, line)
        if m:
            return m
    return None


class Shot:
    def __init__(self, name):
        from PIL import Image
        im = Image.open(os.path.join(SHOTS, "p648motes_%s.png" % name)).convert("RGB")
        self.w, self.h = im.size
        self.raw = im.tobytes()
        self.focal = self.h / 1.5          # fov 90 on the 4:3 convention

    def lum(self, x, y):
        i = (y * self.w + x) * 3
        return self.raw[i] + self.raw[i + 1] + self.raw[i + 2]

    def rgb(self, x, y):
        i = (y * self.w + x) * 3
        return self.raw[i] / 255.0, self.raw[i + 1] / 255.0, self.raw[i + 2] / 255.0

    def centre(self, row, i):
        depth, rise, count, right = ROWS[row]
        return (self.w / 2 + (right + (i - (count - 1) / 2) * 0.06) * self.focal,
                self.h / 2 - rise * self.focal)


def measure(bare, shot, row, i):
    """One black mote: its peak, its area above half the peak, its total coverage."""
    cx, cy = bare.centre(row, i)
    r = 18
    win = {}
    for y in range(int(cy) - r, int(cy) + r + 1):
        for x in range(int(cx) - r, int(cx) + r + 1):
            b = bare.lum(x, y)
            if b < 60:                      # too dark a wall to read a ratio off
                return None
            win[(x, y)] = max(0.0, 1.0 - min(1.0, shot.lum(x, y) / b) ** 2.2)
    total = sum(win.values())
    if total <= 0:
        return {"peak": 0.0, "area": 0, "total": 0.0}
    # The brightest pixel: a size-100 mote's solid core is 3.7 px across, so one
    # pixel sits wholly inside it, and nothing here is noisy (no dither, no bloom).
    peak = max(win.values())
    # Source's sprite above half its peak is a disc of radius 0.71 h.
    area = sum(1 for v in win.values() if v >= peak * 0.5)
    return {"peak": peak, "area": area, "total": total}


def row(bare, shot, name):
    count = ROWS[name][2]
    got = [measure(bare, shot, name, i) for i in range(count)]
    return None if any(g is None for g in got) else got


def mean(xs, key):
    return sum(x[key] for x in xs) / len(xs)


def sprite_integral():
    """Source's sprite summed over its square, in units of the half-side squared."""
    n, acc = 400, 0.0
    for a in range(n):
        for b in range(n):
            x = (a + 0.5) / n
            y = (b + 0.5) / n
            acc += max(0.0, min(1.0, (1.17 - math.hypot(x, y)) / 0.92))
    return 4 * acc / (n * n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--focus-ok", action="store_true",
                    help="grade a run whose window was brought to the front")
    args = ap.parse_args()

    dat = os.path.join(GAMEDIR, "csprogs.dat")
    if os.path.exists(dat):
        print("csprogs.dat sha256 %s" % hashlib.sha256(open(dat, "rb").read()).hexdigest()[:16])
    if not args.grade_only:
        run(args.exe, args.timeout)
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log at %s" % LOG)
        return 2
    st = stages(LOG)
    if not any("RIGDONE" in line for line in st["all"]):
        print("CANNOT GRADE: the run did not reach its end marker")
        return 2
    focus = sum(1 for line in st["all"] if "[focus] window is foreground but" in line)
    if focus and not args.focus_ok:
        print("CANNOT GRADE: the window was brought to the front %d time(s); "
              "--focus-ok grades it anyway" % focus)
        return 2
    v = st.get("V volumes", [])
    why = first(v, r"func_dustmotes: orbs, because (.*)")
    if why:
        print("CANNOT GRADE: this client draws the orbs -- %s" % why.group(1))
        return 2

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and good
        print("%-4s %s  %s" % ("ok" if good else "FAIL", label, detail))

    def engine_count(lines):
        return sum(int(x.group(1)) for x in (re.search(r"Type \.ftesurf_dm\d+ = (\d+)\+", line) for line in lines) if x)

    # ---- the subject's own lines
    m = first(v, r"func_dustmotes: Source's motes, (\d+) looks asked, (\d+) answering")
    check("V  the map's three looks, all answering",
          bool(m) and m.group(1) == "3" and m.group(2) == "3", m.group(0) if m else "no line")
    live = [int(x.group(1)) for x in (re.search(r"Type \.ftesurf_dm[01] = (\d+)\+", line) for line in v) if x]
    check("V  both volumes hold live motes", len(live) >= 2 and min(live) >= 50, "counts %s" % live)
    placed = [line for line in st.get("M ruler", []) if re.search(r"emit_mote: \d+ of look \d+ ", line)]
    check("M  six rows were placed", len(placed) == 6, "%d placement lines" % len(placed))
    placed = [line for line in st.get("N second set", []) if re.search(r"emit_mote: \d+ of look \d+ ", line)]
    check("N  four rows were placed", len(placed) == 4, "%d placement lines" % len(placed))

    p = st.get("P pool", [])
    m = first(p, r"motes in range would keep (\d+) alive; Source's pool is 2048, so ([\d.]+) of them spawn")
    check("P  the volumes ask for more than Source's pool holds",
          bool(m) and int(m.group(1)) > 2 * POOL and float(m.group(2)) < 0.5, m.group(0) if m else "no line")
    held = engine_count(p)
    check("P  and the engine holds a pool of them", 0.85 * POOL * POOL_HELD <= held <= 1.15 * POOL * POOL_HELD,
          "%d by r_partinfo, which is %d of Source's kind alive; a full pool is %d"
          % (held, round(held / POOL_HELD), POOL))
    r = st.get("R restart", [])
    m = first(r, r"func_dustmotes: Source's motes, (\d+) looks asked, (\d+) answering")
    check("R  after vid_restart the looks answer again",
          bool(m) and m.group(1) == "3" and m.group(2) == "3", m.group(0) if m else "no line")
    t = st.get("T refill", [])
    check("R  and the volumes are filling", engine_count(t) >= engine_count(r) + 300,
          "%d by r_partinfo, then %d four seconds on" % (engine_count(r), engine_count(t)))
    o = st.get("O orbs", [])
    check("O  the control says why it draws orbs",
          bool(first(o, r"func_dustmotes: orbs, because vbsp_emit_motes is 0")) and
          bool(first(o, r"emit_mote: orbs, because vbsp_emit_motes is 0")), "")

    # ---- the pictures
    names = ("m0", "m1", "m2", "n0", "n1", "n2")
    for name in names:
        if not os.path.exists(os.path.join(SHOTS, "p648motes_%s.png" % name)):
            print("CANNOT GRADE: no screenshot %s" % name)
            return 2
    m0, m1, m2, n0, n1, n2 = (Shot(name) for name in names)
    focal = m0.focal
    got = {}
    for name, bare, early, full in (("A", m0, m1, m2), ("B", m0, m1, m2), ("C", m0, m1, m2),
                                    ("E", n0, n1, n2), ("G", n0, n1, n2), ("F", n0, n1, n2), ("X", n0, n1, n2)):
        a, b = row(bare, full, name), row(bare, early, name)
        if a is None or b is None:
            print("CANNOT GRADE: the wall behind row %s is too dark to read" % name)
            return 2
        got[name] = {"full": a, "early": b}
        print("row %s  full: peak %.3f  area %.1f px  total %.2f    early: peak %.3f  total %.2f" % (
            name, mean(a, "peak"), mean(a, "area"), mean(a, "total"), mean(b, "peak"), mean(b, "total")))

    hs = 100 / 10000.0 * focal
    disc = lambda size: math.pi * (0.71 * size / 10000.0 * focal) ** 2
    a_area, a_peak, a_total = (mean(got["A"]["full"], k) for k in ("area", "peak", "total"))
    b_area, b_peak = mean(got["B"]["full"], "area"), mean(got["B"]["full"], "peak")
    check("SIZE  a size-100 mote is the size Source makes it",
          abs(a_area - disc(100)) <= 0.2 * disc(100), "area over half %.1f px, Source %.1f" % (a_area, disc(100)))
    check("SIZE  and the same at more than twice the depth",
          abs(b_area - a_area) <= 0.2 * a_area, "%.1f px at 330 against %.1f at 150" % (b_area, a_area))
    areas = sorted(x["area"] for x in got["E"]["full"])
    check("SIZE  sizes drawn from 50 to 150 differ, inside the two",
          areas[-1] >= 1.5 * areas[0] and areas[0] >= 0.6 * disc(50) and areas[-1] <= 1.3 * disc(150),
          "areas %s px; Source's 50 is %.0f, its 150 is %.0f" % (areas, disc(50), disc(150)))
    for label, peak, depth in (("150", a_peak, 150), ("330", b_peak, 330)):
        want = 1 - depth / DISTMAX
        check("FADE  the peak at depth %s is 1 - depth / DistMax" % label,
              abs(peak - want) <= 0.08, "%.3f, Source %.3f" % (peak, want))
    early = mean(got["A"]["early"], "total") / a_total
    check("FADE  a sixth of the way through its life a mote is at a quarter (a ramp: a third)",
          abs(early - 0.25) <= 0.05, "%.3f of its full coverage" % early)
    lives = sorted(x["total"] / a_total for x in got["G"]["early"])
    check("FADE  lives drawn from 4 to 12 s differ, inside the two",
          lives[-1] >= 1.5 * lives[0] and lives[0] >= 0.09 and lives[-1] <= 0.90,
          "at 1.33 s: %s of a full mote; a life of 12 is 0.117, of 4 is 0.750" % ["%.2f" % x for x in lives])
    f_early, f_full = mean(got["F"]["early"], "peak"), mean(got["F"]["full"], "peak")
    check("FADE  a Frozen mote stands at its full strength in both shots",
          abs(f_early - 0.85) <= 0.08 and abs(f_full - 0.85) <= 0.08, "%.3f and %.3f, Source 0.850" % (f_early, f_full))
    gone = max(x["total"] for x in got["X"]["full"] + got["X"]["early"])
    check("FADE  a mote past its DistMax is not drawn", gone <= 2.0, "most coverage %.2f px (a drawn one: %.0f)" % (gone, a_total))
    left = 0
    for name in ("A", "W", "B", "S", "C", "D"):
        for i in range(ROWS[name][2]):
            cx, cy = m0.centre(name, i)
            left += sum(1 for y in range(int(cy) - 18, int(cy) + 19) for x in range(int(cx) - 18, int(cx) + 19)
                        if abs(n0.lum(x, y) - m0.lum(x, y)) > 12)
    check("FADE  past its life a mote is gone", left <= 5, "%d pixels of the first set's windows differ from the bare wall" % left)
    want_total = (1 - 150 / DISTMAX) * sprite_integral() * hs * hs
    check("AT ANY SIZE  a size-100 mote's total coverage",
          abs(a_total - want_total) <= 0.15 * want_total, "%.1f px, Source %.1f" % (a_total, want_total))
    small = mean(got["C"]["full"], "total") / a_total
    check("AT ANY SIZE  and a size-20 mote's is a twenty-fifth of it", abs(small - 0.04) <= 0.012, "%.4f" % small)

    # ---- upright: Source's square is the screen's.  Just outside it, towards its
    # sides, there is nothing; towards its corners the round falloff is still there.
    hs3 = 300 / 10000.0 * focal
    cx, cy = m0.centre("S", 0)
    side = corner = 0.0
    dark = False
    for y in range(int(cy) - 30, int(cy) + 31):
        for x in range(int(cx) - 30, int(cx) + 31):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            if not hs3 + 1.5 < r < 1.17 * hs3 + 0.5:
                continue
            b = m0.lum(x, y)
            dark = dark or b < 60
            c = max(0.0, 1.0 - min(1.0, m2.lum(x, y) / max(b, 1)) ** 2.2)
            if max(abs(dx), abs(dy)) > r * 0.924:        # within 22.5 degrees of a side's middle
                if max(abs(dx), abs(dy)) > hs3 + 1.0:    # and a pixel clear of the side itself
                    side += c
            elif min(abs(dx), abs(dy)) > r * 0.383:      # within 22.5 degrees of a corner
                corner += c
    if dark:
        print("CANNOT GRADE: the wall behind the size-300 mote is too dark to read")
        return 2
    check("UPRIGHT  a mote's square is the screen's, not turned",
          corner >= 2.0 and side <= 0.1 * corner,
          "outside the square of a size-300 mote: %.2f px of coverage towards its corners, %.2f towards its sides" % (corner, side))

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
