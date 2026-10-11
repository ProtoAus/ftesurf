#!/usr/bin/env python3
"""p643fire.py -- driver and grader for cfg/test/p643fire.cfg (Patch 643: env_fire
drawn from Source's flame sheet).

    python tools/p643fire.py [--exe ftesurf64.exe] [--grade-only] [--focus-ok] [--timeout 300]

Runs the cfg in THIS checkout (the basedir is the checkout, so it needs the game
binary, the progs and the mounted games an install has), then grades two things
that cannot both be right by accident:

  THE SUBJECT'S OWN LINES.  emit_list says which rule chose the look and which size
  classes answer the engine's own particleeffectquery, so "flame sheet ... asked 10,
  answering 10" cannot be printed by a build that only meant to draw one.

  THE PICTURES.  A counter of intent is not ink: the brazier's part of each shot is
  counted for flame-bright pixels (red over 200, green over 130, red 70 over blue).
  The sandstone behind it never reaches that (stage N is the proof, same camera),
  nor do the orbs (stage O), and a sheet that drew must.

VERDICTS: exit 0 pass, 1 fail, 2 cannot grade -- the run did not finish, a real
window was in front of it, or this client cannot draw the sheet at all (no mounted
game with the atlas, an engine before Patch 531), which is the orb fallback working
and is said so rather than called a pass.

THE CONTROLS, run by hand and recorded in the patch entry:
  * the stepping compiled out -- `texanim clamp` written as `texanim static` in
    Emit_FlameBlock: every sprite then holds its sequence's first frame, which is
    a wisp or a small flame.  Every LINE above still passes on that build (the
    effects exist and answer) and the brazier's pixel mean fails, 214 against
    3349 -- the numbers are beside BARS;
  * fs_addons.txt without Counter-Strike: Source and Half-Life 2: exit 2, with the
    reason line quoted.
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
LOG = os.path.join(GAMEDIR, "logs", "p643fire.log")
SHOTS = os.path.join(GAMEDIR, "screenshots")
ROI = (0.30, 0.20, 0.70, 0.90)      # the brazier, as fractions of the frame
# A fire flickers, so each group of shots is graded on its MEAN, and each group
# apart: three before the restart, three after it, the two of Dune's small flame,
# the one of a large fire.  Counts are scaled to a 1920x1111 frame.  The bars sit
# between the two builds measured on 11 Oct 2026 -- see BARS' comment.
QUIET_MAX = 150                     # what "no fire" and "orbs" must stay under
REF_AREA = 1920 * 1111


# (label, shots, least mean).  Each bar sits between the two builds, measured on
# 11 Oct 2026 at 1920x1111 (subject, then the stepping mutant):
#   S   2711 2503 4834 (mean 3349)      550   20   72 (mean 214)
#   R   4454 3713 4450 (mean 4205)     1278  449  319 (mean 682)
#   D   3460 2626      (mean 3043)     1802 1068      (mean 1435)
#   L   6421, and 2270 on another run  1017
# The mutant's small and large fires are not empty -- a sequence's first frame is
# a small flame -- which is why those two bars are not the brazier's.
BARS = (
    ("S  the brazier burns (three shots)", ("s1", "s2", "s3"), 1200),
    ("R  and again after the restart (three shots)", ("r1", "r2", "r3"), 1500),
    ("D  dune's small flame (two shots)", ("d1", "d2"), 2200),
    ("L  a large fire (two shots)", ("l1", "l2"), 1600),
)


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
        if name.startswith("p643fire_"):
            os.remove(os.path.join(SHOTS, name))
    # Minimised and NOT activated: the owner is using this desktop, and a window
    # that takes the foreground both interrupts them and voids the run (focus).
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7              # SW_SHOWMINNOACTIVE
    p = subprocess.Popen([os.path.join(ROOT, exe), "+exec", "test/p643fire.cfg"],
                         cwd=ROOT, startupinfo=si,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the run did not exit in %g s -- killed" % timeout)


def stages(log):
    """{stage letter: [lines]} split on the cfg's `=== X ...` echoes."""
    out, cur = {}, None
    for raw in open(log, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        m = re.search(r"=== (\w) (.*)", line)
        if m:
            cur = m.group(1) + " " + m.group(2).strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
        out.setdefault("all", []).append(line)
    return out


def flame_pixels(name):
    from PIL import Image
    path = os.path.join(SHOTS, name)
    if not os.path.exists(path):
        return None
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.crop((int(ROI[0] * w), int(ROI[1] * h), int(ROI[2] * w), int(ROI[3] * h)))
    raw = im.tobytes()
    n = sum(1 for i in range(0, len(raw), 3)
            if raw[i] > 200 and raw[i + 1] > 130 and raw[i] - raw[i + 2] > 70)
    return int(n * REF_AREA / (w * h))


def first(lines, pattern):
    for line in lines:
        m = re.search(pattern, line)
        if m:
            return m
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--focus-ok", action="store_true",
                    help="grade a run whose window was brought to the front (its frame rates mean nothing)")
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
    if not any("RIGDONE" in line for line in st.get("all", [])):
        print("CANNOT GRADE: the run did not reach its end marker")
        return 2
    focus = sum(1 for line in st["all"] if "[focus] window is foreground but" in line)
    if focus and not args.focus_ok:
        print("CANNOT GRADE: the window was brought to the front %d time(s); "
              "--focus-ok grades the lines and pictures anyway" % focus)
        return 2
    if focus:
        print("the window was brought to the front %d time(s): ignore the frame rates" % focus)

    s = st.get("S sheet", [])
    why = first(s, r"env_fire: orbs, because (.*)")
    if why:
        print("CANNOT GRADE: this client draws the orbs -- %s" % why.group(1))
        return 2

    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok = ok and good
        print("%-4s %s  %s" % ("ok" if good else "FAIL", label, detail))

    SHEET = r"flame sheet, size classes (\d+) \(.*\), (\d+) of their (\d+) effects answering"

    def sheet(lines, classes, effects):
        m = first(lines, SHEET)
        return (bool(m) and m.group(1) == classes and m.group(2) == effects and m.group(3) == effects,
                m.group(0) if m else "no line")

    good, text = sheet(s, "10", "26")
    check("S  anubis: small and large, every effect answering", good, text)
    r = st.get("R settled", [])
    good, text = sheet(r, "10", "26")
    n = first(r, r"reloads (\d+)")
    check("R  after vid_restart: answering again, one repair",
          good and bool(n) and n.group(1) == "1", "%s / reloads %s" % (text, n.group(1) if n else "?"))
    good, text = sheet(st.get("D dune", []), "3", "26")
    check("D  dune: tiny and small, every effect answering", good, text)
    good, text = sheet(st.get("C classics2", []), "15", "52")
    check("C  classics2: all four sizes, every effect answering", good, text)
    o = st.get("O orbs", [])
    m = first(o, r"env_fire: orbs, because vbsp_emit_flame is 0")
    check("O  the control says why it draws orbs", bool(m), m.group(0) if m else "no line")

    px = {name: flame_pixels("p643fire_%s.png" % name)
          for name in ("s1", "s2", "s3", "r1", "r2", "r3", "d1", "d2", "l1", "l2", "n1", "n2", "o1", "o2")}
    if any(v is None for v in px.values()):
        print("CANNOT GRADE: missing screenshots %s" % sorted(k for k, v in px.items() if v is None))
        return 2
    print("flame-bright pixels at the brazier: %s" % "  ".join("%s %d" % kv for kv in px.items()))
    for label, names, bar in BARS:
        mean = sum(px[n] for n in names) / len(names)
        check(label, mean >= bar, "mean %d, bar %d" % (mean, bar))
    check("N  nothing drawn reads as nothing", max(px["n1"], px["n2"]) <= QUIET_MAX, "most %d, bar %d" % (max(px["n1"], px["n2"]), QUIET_MAX))
    check("O  the orbs are not mistaken for a sheet", max(px["o1"], px["o2"]) <= QUIET_MAX, "most %d" % max(px["o1"], px["o2"]))

    for tag in ("S fps", "N fps", "O fps"):
        m = first(st.get(tag, []), r"(\d+) frames in ([\d.]+) s since the last emit_list, ([\d.]+) a second")
        print("%s: %s" % (tag, m.group(0) if m else "no line"))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
