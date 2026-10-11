#!/usr/bin/env python3
"""p668precip.py -- driver and grader for cfg/test/p668precip.cfg (Patch 668:
func_precipitation's rain and snowfall, the way Source draws them).

    python tools/p668precip.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 300]

WHAT IS MEASURED.  Each view is photographed bare (vbsp_emit_precip 0) and then
with the precipitation on; what differs by more than 10 of 255 is rain or snow.

  RAIN   surf_zion, near the top of its one volume (renderamt 255: 2,250
         drops a second over the 1500-unit square round the player,
         c_effects.cpp:1275), each 0.35 units wide and a tenth of a second of
         its fall long.  In the picture: at least 30 streaks (blobs five times
         as long as wide; the control, with nothing falling, has none) and
         the 20 longest, which are the nearest, 4 pixels wide or less (2.2 to
         3.1 over five runs; a streak of the width this replaced for the
         particle rain, 5.66 units, would be 40) and 15 times as long.  (Whether
         a thin streak is whole is tools/p659rain.py's: the shader is that
         one, and these streaks are a third as wide and faint enough that a
         threshold of 10 cuts them into pieces by itself.)
  In the subject's lines: the volume asks 2,250 a second; drops START UNDER
  THE SKY (the volume's top is over a side named sky/...; no roof is in
  this square); a drop lives 0.9 to 2.6 s (it is followed to the
  ground or 512 under the player: Source's own end, at his middle, would be
  0.7); and THE ENGINE holds what the drops made in the interval at that life
  come to, within a quarter, none of them traced every frame.  Its blocks are
  not made again until a vid_restart, which takes them: then they are, once
  (twice on the patch-625 engine, whose restart outlasts the first try).
  (`reloads` is not graded: other effects' repairs count in it.)
  And on surf_misc, whose volume is drawn up to a metal ceiling with only void
  over it: every hit is REFUSED UNDER A ROOF, none sky.  (The first cut told sky from roof
  by whether anything was over what was hit, and called that ceiling sky.)

  SNOW   surf_voyager, inside its one volume: at least 40 flakes in the
         picture, and what they ADD to the bare frame is bluer than it is red
         (150 175 200).  Source keeps 500 alive: the engine holds between 200
         and 505 (it drops a flake a frame after its life), and the subject
         has refused flakes for that.  From 600 units
         outside the volume flakes are still made (within 1024 of a point
         ahead of the player): the count rises between two readings there.

WHAT THIS DOES NOT SEE: Source.  Nor a drop's width in world units, where one
ends, a flake's size and fade over its life, wind, or cost: the patch entry
has frames a second.

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade (the run did not finish, a real
window was brought in front of it, or the frame is not 1920x1111's size).

THE CONTROLS, run by hand and recorded in the patch entry: the build before
(nothing falls: every picture check fails), and the first cut, which told sky
from roof by a second trace (M must fail: it called surf_misc's ceiling sky).
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
LOG = os.path.join(GAMEDIR, "logs", "p668precip.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")
VIEW = (0.03, 0.13, 0.97, 0.92)         # under the HUD's timer, clear of the frame's edge


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p668precip_"):
            os.remove(os.path.join(SHOTS, name))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7              # SW_SHOWMINNOACTIVE: the owner is using this desktop
    p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p668precip.cfg"],
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
    path = os.path.join(SHOTS, "p668precip_%s.png" % name)
    return Image.open(path).convert("RGB") if os.path.exists(path) else None


def blobs(with_, bare):
    """Blobs of the VIEW box that differ from the bare shot: (dicts of n, length, width and rgb, what
    the blob adds to the bare frame), and the pixels of the blobs under 8."""
    from PIL import ImageChops
    w, h = with_.size
    box = (int(VIEW[0] * w), int(VIEW[1] * h), int(VIEW[2] * w), int(VIEW[3] * h))
    a, z = with_.crop(box), bare.crop(box)
    r, g, b = ImageChops.difference(a, z).split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b)
    bw, bh = m.size
    px, col, was = m.load(), a.load(), z.load()
    seen = bytearray(bw * bh)
    out, bits = [], 0
    for y in range(bh):
        for x in range(bw):
            if seen[y * bw + x] or px[x, y] <= 10:
                continue
            stack, pts = [(x, y)], []
            seen[y * bw + x] = 1
            while stack:
                cx, cy = stack.pop()
                pts.append((cx, cy))
                for nx in (cx - 1, cx, cx + 1):
                    for ny in (cy - 1, cy, cy + 1):
                        if 0 <= nx < bw and 0 <= ny < bh and not seen[ny * bw + nx] and px[nx, ny] > 10:
                            seen[ny * bw + nx] = 1
                            stack.append((nx, ny))
            if len(pts) < 8:
                bits += len(pts)
                continue
            n = float(len(pts))
            mx = sum(p[0] for p in pts) / n
            my = sum(p[1] for p in pts) / n
            sxx = sum((p[0] - mx) ** 2 for p in pts) / n
            syy = sum((p[1] - my) ** 2 for p in pts) / n
            sxy = sum((p[0] - mx) * (p[1] - my) for p in pts) / n
            t = math.sqrt(max(0.0, (sxx - syy) ** 2 / 4 + sxy * sxy))
            rgb = [sum(col[p[0], p[1]][c] - was[p[0], p[1]][c] for p in pts) / n for c in range(3)]
            # A filled rectangle L by W has variances L^2 / 12 and W^2 / 12; a one-pixel line reads 1.
            out.append(dict(n=len(pts), length=math.sqrt(12 * ((sxx + syy) / 2 + t) + 1),
                            width=math.sqrt(12 * max(0.0, (sxx + syy) / 2 - t) + 1), rgb=rgb))
    return out, bits


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def held(lines, name):
    """r_partinfo: particles in the blocks <name>_t<k>, and how many of those types the engine traces."""
    n = traced = 0
    for l in lines:
        m = re.search(r"Type \.%s_t\d+\s+(\d+) particles(\(\+traceline\))?" % name, l)
        if m:
            n += int(m.group(1))
            traced += bool(m.group(2))
    return n, traced


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
    im = dict((n, shot(n)) for n in ("r0", "r1", "r2", "s0", "s1"))
    if any(v is None for v in im.values()):
        print("CANNOT GRADE: missing shots %s" % " ".join(n for n in im if im[n] is None))
        return 2
    if im["r1"].size[1] < 1000:
        print("CANNOT GRADE: the shots are %dx%d and the thresholds are a 1920x1111 frame's pixels" % im["r1"].size)
        return 2

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and bool(good)
        print("%s %s  %s" % ("ok  " if good else "FAIL", label, detail))

    def said(m):
        return m.group(0).strip() if m else "no line"

    r, v, s, o = (st.get(k, []) for k in "RVSO")
    bad = [l for l in st["all"] if "compilation error" in l or "link error" in l]
    check("   no shader failed to build", not bad, "%d lines" % len(bad))

    # ---- rain: the subject
    m = first(r, r"func_precipitation: (\d+) of rain, (\d+) of snowfall, (\d+) of a kind not drawn")
    check("R  surf_zion's one volume is rain", bool(m) and m.group(1) == "1" and m.group(2) == "0", said(m))
    ASK = r"rain: asking (\d+)/sec of (\d+), throttle ([\d.]+); (\d+) drops made, mean life ([\d.]+) s"
    FATE = r"rain: (\d+) refused under a roof, (\d+) started under the sky, (\d+) born inside something, (\d+) too near"
    asks = [x for x in (re.search(ASK, l) for l in r) if x]
    fate = [x for x in (re.search(FATE, l) for l in r) if x]
    took = [x for x in (re.search(r"frames in ([\d.]+) s since the last emit_list", l) for l in r) if x]
    if len(asks) < 2 or len(fate) < 2 or not took:
        check("R  two readings of the rain's lines and the time between them", False,
              "%d, %d, %d intervals" % (len(asks), len(fate), len(took)))
    else:
        a = asks[-1]
        check("R  it asks Source's 2,250 a second, unthrottled", 2200 <= int(a.group(1)) <= 2300 and float(a.group(3)) == 1.0, said(a))
        life = float(a.group(5))
        check("R  a drop is followed past the player, to the ground or 512 under him", int(a.group(4)) > 0 and 0.9 <= life <= 2.6,
              "%s made, mean life %.2f s" % (a.group(4), life))
        f = fate[-1]
        check("R  drops start under the sky, where the volume is over it", int(f.group(2)) > 0, said(f))
        made = int(asks[-1].group(4)) - int(asks[0].group(4))
        rate = made / float(took[-1].group(1))
        n, traced = held(r, "ftesurf_prain")
        check("R  the engine holds what those lives imply, and traces none of it",
              not traced and 0.75 * rate * life <= n <= 1.25 * rate * life,
              "%d particles in the rain's blocks; %.0f drops a second at %.2f s is %.0f; %d of its types marked (+traceline)"
              % (n, rate, life, rate * life, traced))
    m = first(r, r"its blocks were made again (\d+) time")
    check("R  and its blocks are not being made again", m is None, said(m) if m else "no such line before the restart")

    n, traced = held(v, "ftesurf_prain")
    again = first(v, r"its blocks were made again (\d+) time")
    check("V  after vid_restart the blocks are made again, once or twice, and the rain falls",
          n >= 100 and bool(again) and again.group(1) in ("1", "2"),
          "%d particles in the rain's blocks, %s" % (n, said(again)))

    f = first(st.get("M", []), FATE)
    check("M  surf_misc: a ceiling with nothing over it is a roof, not sky",
          bool(f) and int(f.group(1)) > 0 and int(f.group(2)) == 0, said(f))

    # ---- rain: the pictures
    for name in ("r1", "r2"):
        b, bits = blobs(im[name], im["r0"])
        b.sort(key=lambda x: -x["length"])
        top = b[:20]
        long_ = [x for x in b if x["length"] >= 5 * x["width"]]
        check("RAIN   %s: streaks in view" % name, len(long_) >= 30, "%d blobs five times as long as wide, of %d" % (len(long_), len(b)))
        check("RAIN   %s: the 20 longest are 4 pixels wide or less, and 15 times as long" % name,
              len(top) == 20 and med([x["width"] for x in top]) <= 4.0 and med([x["length"] / x["width"] for x in top]) >= 15,
              "%.1f px wide, %.0f px long, %.0f times" % (med([x["width"] for x in top]), med([x["length"] for x in top]),
                                                          med([x["length"] / x["width"] for x in top])))

    # ---- snow
    m = first(s, r"func_precipitation: (\d+) of rain, (\d+) of snowfall")
    check("S  surf_voyager's one volume is snowfall", bool(m) and m.group(1) == "0" and m.group(2) == "1", said(m))
    m = first(s, r"snow: the eye is (in|outside) a volume; (\d+) flakes made, (\d+) born inside something, (\d+) refused with 500 alive")
    check("S  from inside it flakes are made, and refused once 500 are alive",
          bool(m) and m.group(1) == "in" and int(m.group(2)) > 0 and int(m.group(4)) > 0, said(m))
    n, traced = held(s, "ftesurf_psnow")
    check("S  the engine holds Source's 500 at most, untraced", 200 <= n <= 505 and not traced,
          "%d particles in the snow's blocks, %d of its types marked (+traceline)" % (n, traced))
    b, bits = blobs(im["s1"], im["s0"])
    tot = float(sum(x["n"] for x in b)) or 1.0
    rgb = [sum(x["rgb"][c] * x["n"] for x in b) / tot for c in range(3)]
    check("SNOW   flakes in view, and what they add is bluer than it is red", len(b) >= 40 and rgb[2] > 1.1 * rgb[0] > 0,
          "%d flakes, adding %.0f %.0f %.0f to the bare frame" % ((len(b),) + tuple(rgb)))
    out = [x for x in (re.search(r"snow: the eye is (in|outside) a volume; (\d+) flakes made", l) for l in o) if x]
    check("O  from 600 units outside it flakes are still made",
          len(out) >= 2 and out[0].group(1) == "outside" and out[-1].group(1) == "outside"
          and int(out[-1].group(2)) > int(out[0].group(2)),
          "%s, then %s" % (said(out[0]) if out else "no line", said(out[-1]) if out else "no line"))

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
