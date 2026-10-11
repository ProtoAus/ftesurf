#!/usr/bin/env python3
"""p656fire.py -- driver and grader for cfg/test/p656fire.cfg (Patch 656: env_fire's
smoke, the floor it is lit on, and its reach).

    python tools/p656fire.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 480]

WHAT IS LOOKED AT.
  SMOKE  A fire's smoke is dark and thin: what shows is the wall behind it getting
         darker.  The same shots are taken with the smoke and with
         vbsp_emit_firesmoke 0, the scene is otherwise still (dust off), and the
         mean brightness of a box ABOVE the flame is compared, beside a box well
         to the side that must not move.  Of the three shots with smoke the
         DARKEST is judged: nine runs on 12 Oct read 78 to 93 shot by shot
         against a bare 93.1, the second always the palest (a screenshot stalls
         the game while emission is held to a quarter second's worth), and the
         mean of three once fell under the bound.  One fire is medium (surf_road_to_hell,
         vistasmokev1's loop), one tiny (surf_dune, smoke1's stills).  A small
         and a large fire are stood beside and the ENGINE's count of their smoke
         particles read (r_partinfo): their pictures are not graded.
  REACH  6,000 units straight above one of surf_anubis' large fires, looking
         down, torches off: the pixels under the camera that differ from the same
         shot with vbsp_emit_fire 0.  A flame that far is a dozen pixels.  The
         limit was 4,000.  (The first cut counted flame-coloured pixels looking
         down on surf_road_to_hell, and found 3,600 of lava.)
  FLOOR  surf_classics2's fires have no "Don't drop" flag.  The largest is lit
         565 units under its entity; the camera looks at where it lands and
         counts flame-bright pixels (red over 200, green over 130, red 70 over
         blue).
         surf_lost2's stand over func_brush pedestals: the drop has to meet a
         brush entity, 24 units down, where the world is hundreds lower.
And the subject's own lines: emit_list's counts of fires with smoke, of smoke
effects answering the engine's query, of fires in reach and thinned, of fires that
may carry a light, of fires moved; and no shader of ours failing to compile or
link (a smoke effect whose shader did not build still ANSWERS, and draws a red
square: the first cut did).

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade.

CONTROLS, run by hand and recorded in the patch entry: the build before 656
(no smoke lines, no darkening, nothing in R's or D's picture), and 656 with
Emit_DropFires standing up no brush entity (surf_lost2's fires fall past their
pedestals).

NOT SEEN: the smoke of small and large fires as a picture; that smoke is drawn
UNDER its flame; the light flag as a light (vbsp_emit_lights is 0).
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
LOG = os.path.join(GAMEDIR, "logs", "p656fire.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")

# Boxes as fractions of the frame: left, top, right, bottom.
PLUME_M, ASIDE_M = (0.43, 0.45, 0.56, 0.66), (0.70, 0.45, 0.85, 0.66)      # the flame's top is at 0.70
PLUME_T, ASIDE_T = (0.40, 0.125, 0.60, 0.375), (0.70, 0.125, 0.90, 0.375)
FLAME_R = (0.47, 0.445, 0.53, 0.555)       # the fire is under the middle of the frame
FLAME_D = (0.30, 0.25, 0.70, 0.85)
DROP = (r"env_fire: (\d+) without Don't drop: (\d+) lit on what is under them \(mean (\d+), most (\d+) units\), "
        r"(\d+) with nothing within 1024, (\d+) inside something")


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p656fire_"):
            os.remove(os.path.join(SHOTS, name))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7              # SW_SHOWMINNOACTIVE: the owner is using this desktop
    p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p656fire.cfg"],
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
    path = os.path.join(SHOTS, "p656fire_%s.png" % name)
    return Image.open(path).convert("RGB") if os.path.exists(path) else None


def crop(im, box):
    w, h = im.size
    return im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))


def brightness(im, box):
    hist = crop(im, box).convert("L").histogram()
    return sum(i * v for i, v in enumerate(hist)) / float(sum(hist))


def flame_pixels(im, box):
    raw = crop(im, box).tobytes()
    n = sum(1 for i in range(0, len(raw), 3) if raw[i] > 200 and raw[i + 1] > 130 and raw[i] - raw[i + 2] > 70)
    return n * (1920.0 * 1111.0) / (im.size[0] * im.size[1])


def changed(im, ref, box):
    """Pixels of im in the box that differ from ref by more than 40 in some channel."""
    a, b = crop(im, box).tobytes(), crop(ref, box).tobytes()
    n = sum(1 for i in range(0, len(a), 3) if max(abs(a[i] - b[i]), abs(a[i + 1] - b[i + 1]), abs(a[i + 2] - b[i + 2])) > 40)
    return int(n * (1920.0 * 1111.0) / (im.size[0] * im.size[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=480)
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
    s, n, t, u, d, b = (st.get(k, []) for k in "SNTUDB")
    large, small, reach = (st.get(k, []) for k in "LKR")
    why = first(s, r"env_fire: orbs, because (.*)")
    if why:
        print("CANNOT GRADE: this client draws the orbs -- %s" % why.group(1))
        return 2

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and good
        print("%-4s %s  %s" % ("ok" if good else "FAIL", label, detail))

    def said(m):
        return m.group(0).strip() if m else "no line"

    def held(lines, cls):
        return sum(int(x.group(1)) for x in (re.search(r"Type \.ftesurf_fl%ds\d\d = (\d+)\+" % cls, line) for line in lines) if x)

    # ---- the subject's own lines
    m = first(s, r"flame sheet, size classes (\d+) \(.*\), (\d+) of their (\d+) effects answering")
    check("S  all four sizes, every flame effect answering", bool(m) and m.groups() == ("15", "52", "52"), said(m))
    m = first(s, r"env_fire: smoke over (\d+) fires, (\d+) of (\d+) smoke effects answering")
    check("S  smoke over the map's 106 fires, every smoke effect answering", bool(m) and m.groups() == ("106", "10", "10"), said(m))
    broken = [line for line in st["all"] if ("compilation error" in line or "link error" in line.lower()) and "ftesurf_" in line]
    check("   no shader of this file failed to build", not broken, "%d lines%s" % (len(broken), (": " + broken[0][:80]) if broken else ""))
    check("S  the engine holds a medium fire's smoke", held(s, 2) >= 30, "%d particles by r_partinfo" % held(s, 2))
    check("L  and a large fire's, both layers", held(large, 3) >= 10, "%d" % held(large, 3))
    check("K  and a small fire's", held(small, 1) >= 5, "%d" % held(small, 1))
    m = first(s, r"env_fire: (\d+) in reach \((\d+) units\), (\d+) of them past (\d+) and thinned")
    check("S  fires in reach to 10,000 units, the far ones thinned",
          bool(m) and int(m.group(1)) >= 20 and m.group(2) == "10000" and int(m.group(3)) > 0, said(m))
    m = first(s, r"env_fire: (\d+) may carry a light")
    check("S  a fire without spawnflags 32 may carry a light: all 106", bool(m) and m.group(1) == "106", said(m))
    m = first(s, DROP)
    check("S  none of them is moved: all 106 say Don't drop", bool(m) and m.group(1) == "0" and m.group(2) == "0", said(m))
    m = first(n, r"env_fire: no smoke, because vbsp_emit_firesmoke is 0")
    check("N  the control says why it draws no smoke", bool(m), said(m))
    m = first(t, r"env_fire: smoke over (\d+) fires, (\d+) of (\d+) smoke effects answering")
    check("T  surf_dune: smoke over its 65 fires, both sizes' effects answering", bool(m) and m.groups() == ("65", "4", "4"), said(m))
    m = first(t, DROP)
    check("T  and none moved", bool(m) and m.group(1) == "0", said(m))
    m = first(b, DROP)
    check("B  surf_lost2: all 178 land on their pedestals, not on the world under them",
          bool(m) and m.group(1) == "178" and m.group(2) == "178" and int(m.group(4)) <= 100, said(m))
    m = first(d, DROP)
    check("D  surf_classics2: every one of its 233 is accounted for, most of them moved",
          bool(m) and m.group(1) == "233" and int(m.group(2)) + int(m.group(5)) + int(m.group(6)) == 233 and int(m.group(2)) >= 200, said(m))
    m = first(st["all"], r"emit: env_fire at '?12823\S* \S+ \S+'? is lit (5\d\d(\.\d+)?) below it")
    check("D  the large fire is lit 565 units under its entity", bool(m), said(m))

    # ---- the pictures
    need = ["s1", "s2", "s3", "n1", "n2", "n3", "t1", "t2", "t3", "u1", "u2", "u3", "r0", "r1", "r2", "d1", "d2"]
    im = {name: shot(name) for name in need}
    missing = [name for name in need if im[name] is None]
    if missing:
        print("CANNOT GRADE: no screenshot %s" % " ".join(missing))
        return 2
    mean = lambda names, box: sum(brightness(im[x], box) for x in names) / len(names)
    for label, with_, without, plume, aside, least in (("medium", "s", "n", PLUME_M, ASIDE_M, 2.0), ("tiny", "t", "u", PLUME_T, ASIDE_T, 0.3)):
        a, c = [with_ + x for x in "123"], [without + x for x in "123"]
        # The darkest of the three: a screenshot stalls the game a second or two while
        # emission is held to a quarter of one, so the shot after it catches a thinned plume.
        each = [brightness(im[x], plume) for x in a]
        smoke, none = min(each), mean(c, plume)
        check("SMOKE  over the %s fire the wall is darker with it, and still a wall" % label, least <= none - smoke <= 40,
              "%s with smoke, %.1f without (of 255)" % (" ".join("%.1f" % v for v in each), none))
        side = mean(a, aside) - mean(c, aside)
        check("SMOKE  and beside it nothing moved", abs(side) <= 0.3, "%.2f" % side)
    lit = [changed(im[x], im["r0"], FLAME_R) for x in ("r1", "r2")]
    check("REACH  a fire 6,000 units away is drawn", min(lit) >= 8,
          "pixels under the camera that are not the fire-off shot's: %s" % " ".join("%d" % x for x in lit))
    m = first(reach, r"env_fire: (\d+) in reach \((\d+) units\), (\d+) of them past (\d+) and thinned")
    check("R  and the subject counts it in reach, thinned", bool(m) and int(m.group(3)) > 0, said(m))
    lit = [flame_pixels(im[x], FLAME_D) for x in ("d1", "d2")]
    check("FLOOR  the large fire burns where the camera looks, 565 under its entity", min(lit) >= 300,
          "flame-bright pixels %s" % " ".join("%d" % x for x in lit))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
