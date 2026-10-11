#!/usr/bin/env python3
"""p658once.py -- driver and grader for cfg/test/p658once.cfg (engine Patch 658:
a blended particle is drawn once a frame, and no fainter).

    python tools/p658once.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 240]

WHAT IS MEASURED.  Six dots, each ONE particle standing still in front of a wall
photographed bare.  Drawn `blend blendalpha`, a dot of alpha a leaves (1 - a) of
the wall per draw, so the middle of a black dot over the bare wall is that
factor directly (this blend is in the framebuffer's own space, no gamma).  The
dot's sprite is particles/ftesurf_dot.tga, and a is the particle's alpha times
the sprite's own in the middle, READ FROM THAT FILE: 0.914 on 12 Oct 2026.

  P   a shader that is the engine's default particle shader text without the 658
      permutation, alpha 0.5.  ONE draw leaves 1 - a; two leave (1 - a)^2.  This
      is the only dot that tells how many times the bucket is drawn.
  T   the engine's default shader, alpha 0.5; U, at 0.2.  Both must still leave
      (1 - a)^2: before 658 by two draws, after it by one that writes a * (2 - a).
  G   the default shader, grey 128 at 0.5: the colour two draws left, per channel.
  H   black at alpha 1.6.  Both old draws saturated; a * (2 - a) unclamped would
      fold back to 0.84 and leave a sixth of the wall.
  M   `blend invmodc`, grey 128: (1 - c) per draw, so (1 - c)^2.

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade.  THE CONTROL is the engine before
658 (`--exe` takes any client): it must fail on DRAWN ONCE and nothing else.

NOT SEEN: beams and fans (drawn once before and after, by reading), `blend
subtract`, invmoda and blendcolour, fog, r_lightprepass 1, another renderer.

The driver writes scripts/p658once.shader into this gamedir and removes it, and
lists the directory afterwards.
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
LOG = os.path.join(GAMEDIR, "logs", "p658once.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")
SHADER = os.path.join(GAMEDIR, "scripts", "p658once.shader")
SPRITE = os.path.join(GAMEDIR, "particles", "ftesurf_dot.tga")

# p_script.c's BM_BLEND default as it was before 658, on the dot's own texture.
PLAIN = """p658plain
{
	program defaultsprite
	nomipmaps
	sort unlitdecal
	{
		map particles/ftesurf_dot.tga
		blendfunc blend
		rgbgen vertex
		alphagen vertex
		nodepth
	}
	polygonoffset
	surfaceparm noshadows
	surfaceparm nodlight
}
"""

# The cfg's dots: name -> (units right of the line of sight, units above it).  Depth 150.
DOTS = {"T": (-40, 24), "U": (0, 24), "P": (40, 24), "G": (-40, 9), "H": (0, 9), "M": (40, 9)}
DEPTH = 150.0
GREY = 128 / 255.0


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p658once_"):
            os.remove(os.path.join(SHOTS, name))
    made_dir = not os.path.isdir(os.path.dirname(SHADER))
    os.makedirs(os.path.dirname(SHADER), exist_ok=True)
    with open(SHADER, "w", newline="\n") as f:
        f.write(PLAIN)
    try:
        si = None
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 7              # SW_SHOWMINNOACTIVE: the owner is using this desktop
        p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p658once.cfg"],
                             cwd=ROOT, startupinfo=si,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < timeout:
            time.sleep(1)
        if p.poll() is None:
            p.kill()
            print("the run did not exit in %g s -- killed" % timeout)
    finally:
        os.remove(SHADER)
        if made_dir and not os.listdir(os.path.dirname(SHADER)):
            os.rmdir(os.path.dirname(SHADER))
    left = [n for n in (os.listdir(os.path.dirname(SHADER)) if os.path.isdir(os.path.dirname(SHADER)) else [])
            if n.startswith("p658")]
    print("scripts/ after the run: %s" % (left or "nothing of this arm's"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--focus-ok", action="store_true", help="grade a run whose window was brought to the front")
    args = ap.parse_args()

    exe = os.path.join(ROOT, args.exe)
    if os.path.exists(exe):
        print("%s sha256 %s" % (args.exe, hashlib.sha256(open(exe, "rb").read()).hexdigest()[:16]))
    if not os.path.exists(SPRITE):
        print("CANNOT GRADE: no %s (particles/ is not in git; copy it from an install)" % SPRITE)
        return 2
    if not args.grade_only:
        run(args.exe, args.timeout)
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log at %s" % LOG)
        return 2
    lines = [re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n")) for raw in open(LOG, errors="replace")]
    if not any("RIGDONE" in line for line in lines):
        print("CANNOT GRADE: the run did not reach its end marker")
        return 2
    focus = sum(1 for line in lines if "[focus] window is foreground but" in line)
    if focus and not args.focus_ok:
        print("CANNOT GRADE: the window was brought to the front %d time(s); --focus-ok grades it anyway" % focus)
        return 2
    stamp = next((m.group(0) for m in (re.search(r"git-\d+-[\w.-]+", line) for line in lines) if m), "no stamp line")
    print("engine: %s" % stamp)

    from PIL import Image
    sprite = Image.open(SPRITE).convert("RGBA")
    sw, sh = sprite.size
    mid = [sprite.getpixel((sw // 2 - dx, sh // 2 - dy)) for dx in (0, 1) for dy in (0, 1)]
    tex_a = sum(p[3] for p in mid) / (4 * 255.0)
    tex_c = sum(p[0] for p in mid) / (4 * 255.0)
    if max(p[3] for p in mid) - min(p[3] for p in mid) > 2:
        print("CANNOT GRADE: the sprite's four middle texels differ (%s); the middle of a dot is not one value" % [p[3] for p in mid])
        return 2
    print("sprite: alpha %.3f and colour %.3f in the middle" % (tex_a, tex_c))

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and good
        print("%-4s %s  %s" % ("ok" if good else "FAIL", label, detail))

    exists = sum(1 for line in lines if "effect exists" in line)
    check("the six effects answered the engine's query", exists == 6, "%d of 6" % exists)
    after = lines[next(i for i, line in enumerate(lines) if "=== D dots" in line):]
    held = [int(m.group(1)) for m in (re.search(r"Type \.ftesurf_p658[a-z] = (\d+)\+", line) for line in after) if m]
    check("and the engine holds one particle of each", held == [1] * 6, "r_partinfo %s" % held)
    sorts = {}
    for line in lines:
        m = re.search(r"\[shader\] (\S+)\s+sort\s+(\d+)", line)
        if m and m.group(1) in ("ftesurf_dot_blend", "p658plain", "ftesurf_dot_invmodc"):
            sorts[m.group(1)] = int(m.group(2))
    check("all three shaders sort into the same bucket", len(sorts) == 3 and len(set(sorts.values())) == 1, "%s" % sorts)

    for name in ("b0", "b1"):
        if not os.path.exists(os.path.join(SHOTS, "p658once_%s.png" % name)):
            print("CANNOT GRADE: no screenshot %s" % name)
            return 2
    b0 = Image.open(os.path.join(SHOTS, "p658once_b0.png")).convert("RGB")
    b1 = Image.open(os.path.join(SHOTS, "p658once_b1.png")).convert("RGB")
    w, h = b0.size
    focal = h / 1.5
    got, wall, drawn = {}, {}, {}
    for name, (right, up) in DOTS.items():
        cx = int(round(w / 2 + right / DEPTH * focal))
        cy = int(round(h / 2 - up / DEPTH * focal))
        # the pixel the dot moved most, within 6 of where it should be: its middle
        best = None
        for y in range(cy - 6, cy + 7):
            for x in range(cx - 6, cx + 7):
                b, s = b0.getpixel((x, y)), b1.getpixel((x, y))
                if sum(b) < 90:
                    print("CANNOT GRADE: the wall behind dot %s is too dark to read" % name)
                    return 2
                move = abs(sum(s) - sum(b))
                if best is None or move > best[0]:
                    best = (move, b, s)
        _, b, s = best
        got[name] = sum(s) / float(sum(b))
        wall[name] = tuple(c / 255.0 for c in b)
        drawn[name] = tuple(c / 255.0 for c in s)
        print("dot %s  leaves %.3f of a wall at %.2f" % (name, got[name], sum(b) / 765.0))

    once = 1 - 0.5 * tex_a
    check("DRAWN ONCE: the plain shader leaves 1 - a", abs(got["P"] - once) <= 0.03,
          "%.3f; one draw %.3f, two draws %.3f" % (got["P"], once, once * once))
    check("NO FAINTER: the default shader leaves what two draws left", abs(got["T"] - once * once) <= 0.03,
          "%.3f, two draws %.3f" % (got["T"], once * once))
    want = (1 - 0.2 * tex_a) ** 2
    check("and the same at alpha 0.2", abs(got["U"] - want) <= 0.03, "%.3f, two draws %.3f" % (got["U"], want))
    want = tuple(d * once * once + GREY * tex_c * (1 - once * once) for d in wall["G"])
    check("and a grey dot is the colour two draws left", all(abs(a - b) <= 0.03 for a, b in zip(drawn["G"], want)),
          "drawn %s, two draws %s" % (" ".join("%.3f" % c for c in drawn["G"]), " ".join("%.3f" % c for c in want)))
    check("an alpha over 1 is opaque, as it was", got["H"] <= 0.05, "leaves %.3f" % got["H"])
    want = (1 - GREY * tex_c) ** 2
    check("and invmodc leaves (1 - c) twice", abs(got["M"] - want) <= 0.03, "%.3f, two draws %.3f" % (got["M"], want))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
