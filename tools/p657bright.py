#!/usr/bin/env python3
"""p657bright.py -- driver and grader for cfg/test/p657bright.cfg (Patch 657: how
bright a func_dustmotes mote is drawn).

    python tools/p657bright.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 300]

WHAT IS MEASURED.  Source blends a mote over the wall in linear light: at alpha a,

        pixel = (exposure * a * colour ^ 2.2 + (1 - a) * wall ^ 2.2) ^ (1 / 2.2)

The cfg stands rows of Frozen motes in front of a wall that is one flat colour
(r_clear, from the void over the map), so the wall is known to the last bit, and
this reads the middle of every mote (the sprite is solid to a quarter of its
half-side).  A mote at depth 150 of DistMax 1000 is at 0.85 of its Alpha.

  BLACK  on a black wall every row is linear light's value: 0.329, 0.679 and
         0.929 for white at Alpha 26, 128 and 255, and 0 0.466 0.929 for
         0 128 255.  Patch 648's blend read 0.19 for the first.
  WHITE  on a white wall a white mote is not there -- and the blue row beside
         it is, so the frame does hold motes.
  GREY   on a 0.37 wall each white row is on the straight line between its
         black and its white value, which is over linear light (by 0.108 at
         Alpha 26) and never under it.
  COLOUR one alpha is one slope for three channels.  0 128 255 at 0.85 is
         judged per channel against linear light: within 0.19 on white (red is
         0.18 under, green 0.10 over) and 0.08 on the grey.  A slope set by the
         brightest channel alone, the dimmest alone or the luminance fails it.
  AUTO   with vbsp_emit_exposure -1 surf_dune's motes are lit at the ceiling its
         logic_auto sets, 1.2, and the Alpha 26 row on black reads
         (1.2 * 0.0867) ^ (1 / 2.2) = 0.357.
  And the subject's own line on four more loads: surf_shade (HDR lighting, no
  ceiling set: Source's 2), surf_andromeda (no HDR lighting: 1), surf_tensor2
  (a ceiling of 1.4, written with commas), surf_dune at hl2_favour_ldr 1, and
  surf_destruction, whose 134 MiB are not read: the engine's fread, fseek and
  fsize each load a whole file, so the log must show no open of it.

WHAT THIS DOES NOT SEE: Source.  The formula is its shader's arithmetic
(vertexlit_and_unlit_generic_ps20b.fxc:481, an sRGB target), not a picture of
it.  Nor a map whose ceiling is 1 or under (no file is read for those), nor
any colour but one.

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade (the run did not finish, a real
window was brought in front of it, or this client draws the orbs anyway).

THE CONTROLS, run by hand and recorded in the patch entry: the build before
(BLACK and every exposure line must fail), and this build with `* GAIN` taken
out of the shader (AUTO's pixels must fail while its line still passes).
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAMEDIR, "logs", "p657bright.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")

FADE = 0.85                             # 1 - depth / DistMax
ROWS = {"W": 26 / 255.0, "H": 128 / 255.0, "F": 1.0}
BLUE = (0.0, 128 / 255.0, 1.0)
LINE = r"motes are lit at exposure ([\d.]+): (.*)"


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p657bright_"):
            os.remove(os.path.join(SHOTS, name))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7              # SW_SHOWMINNOACTIVE: the owner is using this desktop
    p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p657bright.cfg"],
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
            cur = m.group(1)
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


def shot(name):
    from PIL import Image
    path = os.path.join(SHOTS, "p657bright_%s.png" % name)
    return Image.open(path).convert("RGB") if os.path.exists(path) else None


def motes(im):
    """Rows of motes in a shot over BLACK, top row first, each left to right: (x, y) centres."""
    w, h = im.size
    x0, y0, x1, y1 = int(w * 0.38), int(h * 0.33), int(w * 0.62), int(h * 0.51)    # clear of the HUD's text
    px = im.load()
    seen, found = set(), []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if (x, y) in seen or max(px[x, y]) <= 12:
                continue
            stack, pts = [(x, y)], []
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                pts.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if x0 <= nx < x1 and y0 <= ny < y1 and (nx, ny) not in seen and max(px[nx, ny]) > 12:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            if len(pts) >= 40:          # a mote is 200 pixels at this size; the crosshair is not
                found.append((sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)))
    found.sort()
    rows = []
    for my, mx in found:
        if rows and abs(rows[-1][0][1] - my) < 12:
            rows[-1].append((mx, my))
        else:
            rows.append([(mx, my)])
    return [sorted(r) for r in rows]


def middle(im, at):
    """The mean of the 3x3 at a mote's centre, per channel, 0..1."""
    acc = [0, 0, 0]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            p = im.getpixel((int(round(at[0])) + dx, int(round(at[1])) + dy))
            for c in range(3):
                acc[c] += p[c]
    return tuple(a / 9.0 / 255.0 for a in acc)


def linear_light(colour, a, wall, exposure=1.0):
    return tuple(min(1.0, (exposure * a * c ** 2.2 + (1.0 - a) * wall ** 2.2) ** (1 / 2.2)) for c in colour)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--focus-ok", action="store_true", help="grade a run whose window was brought to the front")
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
        print("CANNOT GRADE: the window was brought to the front %d time(s); --focus-ok grades it anyway" % focus)
        return 2
    why = first(st.get("K", []), r"func_dustmotes: orbs, because (.*)")
    if why:
        print("CANNOT GRADE: this client draws the orbs -- %s" % why.group(1))
        return 2
    im = dict((n, shot(n)) for n in ("k1", "g1", "w1", "a1"))
    if any(v is None for v in im.values()):
        print("CANNOT GRADE: missing shots %s" % " ".join(n for n in im if im[n] is None))
        return 2
    if im["k1"].size[1] < 1000:
        # A mote's solid middle is 3.7 pixels across at 1111 lines and 2.4 at 720: the 3x3 read needs the first.
        print("CANNOT GRADE: the shots are %dx%d and the ruler needs 1000 lines" % im["k1"].size)
        return 2

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and bool(good)
        print("%s %s  %s" % ("ok  " if good else "FAIL", label, detail))

    def said(m):
        return m.group(0).strip() if m else "no line"

    def line(stage, label, exposure, reason):
        m = first(st.get(stage, []), LINE)
        check(label, bool(m) and abs(float(m.group(1)) - exposure) < 0.005 and reason in m.group(2), said(m))

    bad = [l for l in st["all"] if "compilation error" in l or "link error" in l]
    check("   no shader failed to build", not bad, "%d lines" % len(bad))

    # ---- K: the ruler at exposure 1
    line("K", "K  the ruler is at exposure 1 because the cvar says so", 1, "vbsp_emit_exposure")
    rows = motes(im["k1"])
    if len(rows) != 2 or len(rows[0]) != 8 or len(rows[1]) != 8:
        check("K  two rows of eight motes over black", False, "found rows of %s" % [len(r) for r in rows])
        print("FAIL")
        return 1
    at = {"W": rows[0][:4], "H": rows[0][4:], "F": rows[1][:4], "D": rows[1][4:]}

    def read(name, row):
        vals = [middle(im[name], p) for p in at[row]]
        return tuple(sum(v[c] for v in vals) / len(vals) for c in range(3))

    worst, detail = 0.0, []
    for row in ("W", "H", "F"):
        got, want = read("k1", row), linear_light((1, 1, 1), ROWS[row] * FADE, 0.0)
        worst = max(worst, max(abs(got[c] - want[c]) for c in range(3)))
        detail.append("%s %.3f (%.3f)" % (row, got[0], want[0]))
    got, want = read("k1", "D"), linear_light(BLUE, FADE, 0.0)
    worst = max(worst, max(abs(got[c] - want[c]) for c in range(3)))
    detail.append("D %.3f %.3f %.3f (%.3f %.3f %.3f)" % (got + want))
    check("BLACK  every row is linear light's on a black wall", worst <= 0.01, "  ".join(detail))

    wall = im["w1"].getpixel((im["w1"].size[0] // 4, im["w1"].size[1] // 2))
    low = min(min(read("w1", row)) for row in ("W", "H", "F"))
    blue = read("w1", "D")
    check("WHITE  a white mote on a white wall is not there, and the blue row is",
          wall == (255, 255, 255) and low >= 0.995 and blue[0] < 0.6 and blue[2] >= 0.995,
          "wall %s, the darkest of the three white rows %.3f, the blue row %.3f %.3f %.3f" % ((wall, low) + blue))

    wall = im["g1"].getpixel((im["g1"].size[0] // 4, im["g1"].size[1] // 2))[0] / 255.0
    off, under, detail = 0.0, 0.0, []
    for row in ("W", "H", "F"):
        a = ROWS[row] * FADE
        got, lin = read("g1", row)[0], linear_light((1, 1, 1), a, wall)[0]
        lo, hi = linear_light((1, 1, 1), a, 0.0)[0], linear_light((1, 1, 1), a, 1.0)[0]
        line_ = lo + wall * (hi - lo)
        off, under = max(off, abs(got - line_)), min(under, got - lin)
        detail.append("%s %.3f (line %.3f, linear light %.3f)" % (row, got, line_, lin))
    check("GREY   on a %.2f wall each white row is on its line, and none under linear light" % wall,
          0.3 < wall < 0.45 and off <= 0.01 and under >= -0.01, "  ".join(detail))

    worst, detail = [0.0, 0.0], []
    for i, (name, bg) in enumerate((("w1", 1.0), ("g1", wall))):
        got, want = read(name, "D"), linear_light(BLUE, FADE, bg)
        worst[i] = max(abs(got[c] - want[c]) for c in range(3))
        detail.append("on %.2f %.3f %.3f %.3f (%.3f %.3f %.3f)" % ((bg,) + got + want))
    check("COLOUR 0 128 255 is within 0.19 of linear light on white and 0.08 on the grey",
          worst[0] <= 0.19 and worst[1] <= 0.08, "  ".join(detail))

    # ---- A: the map's own exposure, in the line and in the pixels
    line("A", "A  surf_dune: lit at the ceiling its logic_auto sets", 1.2, "the map sets its ceiling to 1.2")
    rows = motes(im["a1"])
    if len(rows) != 1 or len(rows[0]) != 8:
        check("AUTO   one row of eight motes over black", False, "found rows of %s" % [len(r) for r in rows])
    else:
        vals = [middle(im["a1"], p)[0] for p in rows[0]]
        gw, gh = sum(vals[:4]) / 4, sum(vals[4:]) / 4
        ww, wh = linear_light((1, 1, 1), ROWS["W"] * FADE, 0.0, 1.2)[0], linear_light((1, 1, 1), ROWS["H"] * FADE, 0.0, 1.2)[0]
        check("AUTO   and its motes are drawn at 1.2 of their light", abs(gw - ww) <= 0.01 and abs(gh - wh) <= 0.01,
              "W %.3f (%.3f)  H %.3f (%.3f)" % (gw, ww, gh, wh))

    line("B", "B  surf_shade: HDR lighting, no ceiling set", 2, "Source's ceiling is 2")
    line("C", "C  surf_andromeda: no HDR lighting", 1, "no HDR lighting is drawn")
    line("E", "E  surf_tensor2: a ceiling written with commas", 1.4, "the map sets its ceiling to 1.4")
    line("F", "F  surf_dune with LDR lighting chosen", 1, "no HDR lighting is drawn")
    line("G", "G  surf_destruction: too large to read, so Source without HDR", 1, "MiB and is not read")
    opens = dict((m, sum(1 for l in st["all"] if 'qcfopen("maps/%s.bsp"' % m in l))
                 for m in ("surf_dune", "surf_shade", "surf_destruction"))
    check("   a map file is opened when the answer turns on it, and only then",
          opens == {"surf_dune": 2, "surf_shade": 1, "surf_destruction": 0},
          "surf_dune %d (three loads, one under the cvar), surf_shade %d, surf_destruction %d"
          % (opens["surf_dune"], opens["surf_shade"], opens["surf_destruction"]))

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
