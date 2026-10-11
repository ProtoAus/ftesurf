#!/usr/bin/env python3
"""p659rain.py -- driver and grader for cfg/test/p659rain.cfg (Patch 659: rain,
a render_sprite_trail, drawn the way Source draws it).

    python tools/p659rain.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 240]

WHAT IS MEASURED.  The camera stands in surf_tensor2's spawn rain looking up
at the sky, takes two shots, turns the particle systems off, waits for what
was falling to land and takes the same view bare.  A streak is a blob of
pixels that differ from the bare shot by more than 10 of 255 (the two lamps
at the foot of the frame flicker, and a blob their size is dropped).  For each
blob, the length and width of the rectangle with its second moments.

  MANY   Source emits 800 a second here; a pool-size rule baked 150, and the
         dust's ceiling and budget made that 68.  At least 40 streaks in view
         (a drop here lives 0.4 s: the ground is near).
  WHOLE  a streak narrower than a pixel is a faint line, not a row of dots:
         blobs under 8 pixels hold 4% of the rain's pixels at most.  (Sampling
         the texture's empty edge for such a streak left 8 to 15%.)
  THIN   the 20 longest are 3 pixels wide or less: a streak is 1 unit wide
         (it was 5.66) and at least a pixel however far away.
  LONG   and 15 times as long as they are wide: 80 units whatever the speed.
  BRIGHT and stand 30 of 255 over the sky: blended in linear light, which
         lifts a faint streak the way Source's sRGB target does.
  And the subject's own lines: the trail shader is made and is the batched
  kind (sort 12); the index marks the map's rain as trails and what is in
  range asks for 800 a second or more, unthrottled; a drop is traced to
  something and given a life of a second or so; and THE ENGINE'S count of
  spawn_rain01's particles, none of them traced, is what the drops made in
  the interval at that life come to (within 35%).  Nothing is sent again
  until a vid_restart, which takes the shader and the blocks: then both are,
  once.

WHAT THIS DOES NOT SEE: Source.  Nor a streak's width in world units (a blob's
depth is not known), WHERE a drop ends (its life is tied to the trace above;
no shot looks at the ground), the fall speed, which this patch does not
change, or the cost: the patch entry has frames a second.

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade (the run did not finish, a real
window was brought in front of it, or the gamedir holds the old bake).

THE CONTROLS, run by hand and recorded in the patch entry: the build before
with the bake before (MANY, THIN, LONG and BRIGHT must all fail), and the cut
before the review (WHOLE must fail, and "nothing is being sent again").
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
LOG = os.path.join(GAMEDIR, "logs", "p659rain.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")
VIEW = (0.03, 0.13, 0.97, 0.92)         # under the HUD's timer, clear of the frame's edge
LIGHT = 600                             # pixels: a blob this large is one of the map's lamps, not a streak


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p659rain_"):
            os.remove(os.path.join(SHOTS, name))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7              # SW_SHOWMINNOACTIVE: the owner is using this desktop
    p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p659rain.cfg"],
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
    path = os.path.join(SHOTS, "p659rain_%s.png" % name)
    return Image.open(path).convert("RGB") if os.path.exists(path) else None


def streaks(rain, bare):
    """Blobs of the VIEW box that differ from the bare shot: dicts of n, length, width, peak,
    and the pixels of those under 8 (a streak drawn as a row of dots is those)."""
    from PIL import ImageChops
    w, h = rain.size
    box = (int(VIEW[0] * w), int(VIEW[1] * h), int(VIEW[2] * w), int(VIEW[3] * h))
    r, g, b = ImageChops.difference(rain.crop(box), bare.crop(box)).split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b)
    bw, bh = m.size
    px = m.load()
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
                pts.append((cx, cy, px[cx, cy]))
                for nx in (cx - 1, cx, cx + 1):
                    for ny in (cy - 1, cy, cy + 1):
                        if 0 <= nx < bw and 0 <= ny < bh and not seen[ny * bw + nx] and px[nx, ny] > 10:
                            seen[ny * bw + nx] = 1
                            stack.append((nx, ny))
            if len(pts) > LIGHT:
                continue
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
            # A filled rectangle L by W has variances L^2 / 12 and W^2 / 12; a one-pixel line reads 1.
            out.append(dict(n=len(pts), length=math.sqrt(12 * ((sxx + syy) / 2 + t) + 1),
                            width=math.sqrt(12 * max(0.0, (sxx + syy) / 2 - t) + 1),
                            peak=max(p[2] for p in pts)))
    return out, bits


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def rain_held(lines):
    """r_partinfo: particles in spawn_rain01's blocks by life, and rain types the engine traces."""
    held = traced = 0
    for l in lines:
        m = re.search(r"Type \.surf_tensor2_spawn_rain01_t\d+\s+(\d+) particles", l)
        if m:
            held += int(m.group(1))
        if re.search(r"Type \.surf_tensor2_\w*rain\w*\s+\d+ particles\(\+traceline\)", l):
            traced += 1
    return held, traced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--focus-ok", action="store_true", help="grade a run whose window was brought to the front")
    ap.add_argument("--old-bake", action="store_true", help="grade a gamedir that holds the bake before this patch (the control)")
    args = ap.parse_args()

    dat = os.path.join(GAMEDIR, "csprogs.dat")
    if os.path.exists(dat):
        print("csprogs.dat sha256 %s" % hashlib.sha256(open(dat, "rb").read()).hexdigest()[:16])
    bake = os.path.join(GAMEDIR, "particles", "surf_tensor2.cfg")
    new_bake = os.path.exists(bake) and "ftesurf_trail/particle/rain" in open(bake, errors="replace").read()
    print("the gamedir's bake of surf_tensor2 is %s" % ("this patch's" if new_bake else "the one before it"))
    if not new_bake and not args.old_bake:
        print("CANNOT GRADE: bake the map into this gamedir first (tools/pcf.py --map surf_tensor2 --gamedir ...), "
              "or say --old-bake")
        return 2
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
    im = dict((n, shot(n)) for n in ("a1", "a2", "a0"))
    if any(v is None for v in im.values()):
        print("CANNOT GRADE: missing shots %s" % " ".join(n for n in im if im[n] is None))
        return 2
    if im["a1"].size[1] < 1000:
        print("CANNOT GRADE: the shots are %dx%d and the thresholds are a 1920x1111 frame's pixels" % im["a1"].size)
        return 2

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and bool(good)
        print("%s %s  %s" % ("ok  " if good else "FAIL", label, detail))

    def said(m):
        return m.group(0).strip() if m else "no line"

    a, n = st.get("A", []), st.get("N", [])
    bad = [l for l in st["all"] if "compilation error" in l or "link error" in l]
    check("   no shader failed to build", not bad, "%d lines" % len(bad))
    m = first(st["all"], r"\[shader\] ftesurf_trail/particle/rain\s+sort (\d+) prog (\d+)")
    check("A  the rain's shader is made, with a program, and is the batched kind",
          bool(m) and m.group(1) == "12" and m.group(2) == "1", said(m))
    m = first(a, r"sprite trails: (\d+) emitters, those in range asking ([\d.]+)/sec of (\d+), throttle ([\d.]+)")
    check("A  the index marks the map's rain, and what is in range asks Source's rate",
          bool(m) and int(m.group(1)) >= 10 and float(m.group(2)) >= 800 and float(m.group(4)) == 1.0, said(m))
    held, traced = rain_held(a)
    drops = [m for m in (re.search(r"drops: (\d+) made, mean life ([\d.]+) s, (\d+) of them with nothing to land on", l)
                         for l in a) if m]
    took = [m for m in (re.search(r"frames in ([\d.]+) s since the last emit_list", l) for l in a) if m]
    if len(drops) < 2 or not took:
        check("A  two `drops:` lines and the time between them", False, "%d lines, %d intervals" % (len(drops), len(took)))
    else:
        made = int(drops[-1].group(1)) - int(drops[0].group(1))
        life, far = float(drops[-1].group(2)), int(drops[-1].group(3))
        rate = made / float(took[-1].group(1))
        check("A  a drop is traced to something, and lands within a second or so",
              0.15 <= life <= 1.2 and far <= 0.05 * int(drops[-1].group(1)),
              "mean life %.2f s, %d of %s with nothing to land on" % (life, far, drops[-1].group(1)))
        # The engine's own count against what the lives the drops were given imply: a
        # build that sends every drop out on the longest block holds six times this.
        check("A  the engine holds what those lives imply, and traces none of it",
              not traced and 0.65 * rate * life <= held <= 1.35 * rate * life,
              "%d particles in spawn_rain01's blocks; %.0f drops a second at %.2f s is %.0f; %d rain lines marked (+traceline)"
              % (held, rate, life, rate * life, traced))
    m = first(a, r"reloads (\d+)")
    check("A  and nothing is being sent again", bool(m) and m.group(1) == "0", said(m))
    held, traced = rain_held(n)
    check("N  none of it four seconds after the systems are switched off", held == 0, "%d" % held)

    r = st.get("R", [])
    held, traced = rain_held(r)
    made = sum(1 for l in r if re.search(r"\[shader\] ftesurf_trail/particle/rain\s+sort 12 prog 1", l))
    again = first(r, r"the map's own blocks were sent again (\d+) time")
    check("R  after vid_restart the shader and the blocks are made again, once, and the rain falls",
          held >= 100 and made >= 1 and bool(again) and again.group(1) == "1",
          "%d particles in spawn_rain01's blocks, the shader made %d time(s) after the restart, %s" % (held, made, said(again)))

    for name in ("a1", "a2"):
        s, bits = streaks(im[name], im["a0"])
        s.sort(key=lambda b: -b["length"])
        top = s[:20]
        width = med([b["width"] for b in top])
        ratio = med([b["length"] / b["width"] for b in top])
        peak = med([b["peak"] for b in top])
        check("MANY   %s: streaks in view" % name, len(s) >= 40, "%d" % len(s))
        ink = bits + sum(b["n"] for b in s)
        check("WHOLE  %s: and not in pieces" % name, bits <= 0.04 * ink,
              "%.1f%% of the rain's %d pixels are in blobs under 8" % (100.0 * bits / max(1, ink), ink))
        check("THIN   %s: the 20 longest are 3 pixels wide or less" % name, len(top) == 20 and width <= 3.0,
              "%.1f px (length %.0f px)" % (width, med([b["length"] for b in top])))
        check("LONG   %s: and 15 times as long as wide" % name, len(top) == 20 and ratio >= 15, "%.0f times" % ratio)
        check("BRIGHT %s: and 30 of 255 over the sky" % name, len(top) == 20 and peak >= 30, "%.0f" % peak)

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
