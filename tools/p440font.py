#!/usr/bin/env python3
"""
p440font.py -- driver for cfg/test/p440font.cfg (Patch 440: the Google face's
outline and its grey drop shadow).

WHY A DRIVER.  The feature is a look, so the observable is pixels, and "the
shots differ" is not a measurement on its own: something else on that vantage
could be moving.  This grades the diff per REGION, against a noise floor taken
at the same cvar value, with three control regions that are drawn in faces the
gate must not admit (Roboto's debug block and the editor's panel, Bebas's
speedometer).  The predictions are pre-registered in the cfg header.

    python tools/p440font.py [--exe ftesurf64.exe] [--grade-only] [--timeout 240]

Writes 4x crops of the map-info block, one per state, under
ftesurf/screenshots/p440_crop_fx*.png -- the outline is 1 px and a 720p shot
cannot be eyeballed at 1:1.

Exit status 0 when every pre-registered prediction held.
"""
import argparse
import os
import re
import subprocess
import sys
import time

from PIL import Image

ROOT = r"C:\FTESurf"
GAMEDIR = os.path.join(ROOT, "ftesurf")
CFG = "cfg/test/p440font.cfg"
LOG = os.path.join(GAMEDIR, "logs", "p440font.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")

# Fractions of the shot; the elements that own them are set by the cfg.  The
# debug block and the panel are parked low by the cfg: at their defaults they
# sit over the sky, whose clouds move.
REGIONS = {
    "MAPINFO": (0.70, 1.00, 0.00, 0.25),   # MONO   -- subject
    "DEBUG":   (0.00, 0.13, 0.49, 0.75),   # Roboto -- control
    "SPEED":   (0.35, 0.65, 0.60, 0.85),   # Bebas  -- control
    "PANEL":   (0.005, 0.19, 0.300, 0.480),  # Roboto -- control (arm B, list rows only)
}

# The pairs, and the prediction each one carries: (a, b, subject min, control max).
# A negative subject min means the subject must ALSO be quiet (the noise floor).
PAIRS = [
    ("p440_A_a", "p440_A_b", "P2 floor", -1, 200, ["DEBUG"]),
    ("p440_A_b", "p440_B_b", "P3 fx0->1", 500,  50, ["DEBUG", "SPEED"]),
    ("p440_B_b", "p440_C_b", "P4 fx1->2", 150,  50, ["DEBUG", "SPEED"]),
    ("p440_ed0_b", "p440_ed2_b", "P5 panel", 500, 50, ["PANEL"]),
]

# HE_Chip's lit fill, '0.16 0.30 0.44'.  `done` is the only FULL-WIDTH lit chip,
# so a long run of it is `done` -- which is what P6 has to see on screen.
CHIP_LIT = (41, 77, 112)
CHIP_TOL = 30


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", CFG], cwd=ROOT, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        raise SystemExit("the run did not exit in %g s -- killed" % timeout)
    return time.time() - t0


def load(name):
    path = os.path.join(SHOTS, name + ".png")
    if not os.path.exists(path):
        raise SystemExit("no such shot: %s -- did the cfg reach it?" % path)
    return Image.open(path).convert("RGB")


def box(im, key):
    x0f, x1f, y0f, y1f = REGIONS[key]
    w, h = im.size
    return (int(x0f * w), int(y0f * h), int(x1f * w), int(y1f * h))


def diff_region(a, b, key, thresh=8):
    """Count of pixels in `key` whose channels differ by more than `thresh`."""
    x0, y0, x1, y1 = box(a, key)
    pa = a.crop((x0, y0, x1, y1)).load()
    pb = b.crop((x0, y0, x1, y1)).load()
    n = 0
    for y in range(y1 - y0):
        for x in range(x1 - x0):
            ca, cb = pa[x, y], pb[x, y]
            if (abs(ca[0] - cb[0]) > thresh or abs(ca[1] - cb[1]) > thresh
                    or abs(ca[2] - cb[2]) > thresh):
                n += 1
    return n


def diff_bbox(a, b, thresh=8):
    xs, ys = [], []
    pa, pb = a.load(), b.load()
    w, h = a.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            ca, cb = pa[x, y], pb[x, y]
            if (abs(ca[0] - cb[0]) > thresh or abs(ca[1] - cb[1]) > thresh
                    or abs(ca[2] - cb[2]) > thresh):
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def crop4(im, key, out):
    x0, y0, x1, y1 = box(im, key)
    c = im.crop((x0, y0, x1, y1))
    c = c.resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST)
    c.save(os.path.join(SHOTS, out))
    return out


def lowest_chip_run(im, minrun=140):
    """Lowest row holding a run of >= minrun lit-chip pixels, or None.  P6."""
    px = im.load()
    w, h = im.size
    for y in range(h - 1, -1, -1):
        run = 0
        for x in range(w):
            r, g, b = px[x, y]
            if (abs(r - CHIP_LIT[0]) <= CHIP_TOL and abs(g - CHIP_LIT[1]) <= CHIP_TOL
                    and abs(b - CHIP_LIT[2]) <= CHIP_TOL):
                run += 1
                if run >= minrun:
                    return y
            else:
                run = 0
    return None


def panel_fit(tag, nlist, nopt, W, H, scale=2.0):
    """cl_hudedit.qc's own height formula, restated: does the panel fit?"""
    psc = min(scale, 2.0)
    for _ in range(2):
        rowh, panw = 15 * psc, 170 * psc
        panh = rowh * (nlist + nopt + 5) + 26 * psc      # HE_FIXEDROWS == 5
        if panh <= H or psc <= 1:
            break
        psc = 1
    top = 0.300 * H                                       # hud_edit_panel_y
    return dict(tag=tag, psc=psc, panw=panw, panh=panh, top=top,
                bottom=top + panh, fits=(top + panh) <= H)


def grade():
    ok = True
    with open(LOG, "r", errors="replace") as fh:
        log = fh.read()

    # ---- P1: the three states, named in the log in the order set -------------
    states = re.findall(r"hud_font_outline \S+ \((plain|outline|outline\+shadow)\)", log)
    want = ["plain", "outline", "outline+shadow"]
    p1 = any(states[i:i + 3] == want for i in range(len(states) - 2))
    print("P1  states read %s   %s"
          % (states or "<absent>", "ok" if p1 else "FAIL: want %s in order" % want))
    ok = ok and p1

    # ---- P2-P5: the region diffs -------------------------------------------
    cache = {}

    def im(name):
        if name not in cache:
            cache[name] = load(name)
        return cache[name]

    print("\nregion diffs (changed pixels, |dchannel| > 8):")
    for a, b, tag, smin, cmax, controls in PAIRS:
        A, B = im(a), im(b)
        if A.size != B.size:
            print("  %-10s SIZE MISMATCH %s vs %s" % (tag, A.size, B.size))
            ok = False
            continue
        s = diff_region(A, B, "MAPINFO")
        good = s < cmax if smin < 0 else s > smin
        ok = ok and good
        print("  %-10s MAPINFO(subject) %7d  want %s %5d   %s"
              % (tag, s, "<" if smin < 0 else ">", cmax if smin < 0 else smin,
                 "ok" if good else "FAIL"))
        for c in controls:
            n = diff_region(A, B, c)
            g2 = n < cmax
            ok = ok and g2
            print("  %-10s %-7s(control) %7d  want < %5d   %s"
                  % (tag, c, n, cmax, "ok" if g2 else "FAIL"))
        bb = diff_bbox(A, B)
        print("  %-10s changed-pixel bbox %s of %s" % (tag, bb, A.size))

    # ---- P6: the panel still fits, and `done` is on screen ------------------
    print("\nP6  the panel with HE_FIXEDROWS at 5:")
    for tag, shot, nlist, nopt in (("collapsed", "p440_ed0_b", 10, 0),
                                   ("seq pane", "p440_edpane_b", 10, 11)):
        I = im(shot)
        W, H = I.size
        f = panel_fit(tag, nlist, nopt, W, H)
        # HE_Draw clamps the panel on screen; model it, because "fits" means
        # "all of it reachable", not "starts where the cvar says".
        top = min(f["top"], H - f["panh"])
        bottom = top + f["panh"]
        good = bottom <= H and top >= 0
        print("    %-10s psc %g  %gx%g at y %g (clamped) -> bottom %g of %g   %s"
              % (tag, f["psc"], f["panw"], f["panh"], top, bottom, H,
                 "fits" if good else "FAIL: runs off the bottom"))
        ok = ok and good
        y = lowest_chip_run(I)
        if y is None:
            print("    %-10s `done` chip: no lit run found -- EYEBALL %s.png"
                  % (tag, shot))
        else:
            g = y < H
            print("    %-10s `done` chip: lowest lit run at y %g of %g   %s"
                  % (tag, y, H, "on screen" if g else "FAIL"))
            ok = ok and g

    # ---- crops, for the eyeball -------------------------------------------
    print("\ncrops (4x the map-info block, one per state):")
    for name, out in (("p440_A_b", "p440_crop_fx0.png"),
                      ("p440_B_b", "p440_crop_fx1.png"),
                      ("p440_C_b", "p440_crop_fx2.png")):
        print("    %s" % crop4(im(name), "MAPINFO", out))

    print("\n%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    if not a.grade_only:
        t = run(a.exe, a.timeout)
        print("ran %s in %.1f s" % (CFG, t))
    if not os.path.exists(LOG):
        raise SystemExit("no log at %s" % LOG)
    sys.exit(grade())


if __name__ == "__main__":
    main()
