#!/usr/bin/env python3
"""p475trail.py -- driver and grader for cfg/test/p475trail.cfg (Patch 475: your
own run's line, drawn live).

    python tools/p475trail.py [--exe ftesurf64.exe] [--grade-only] [--timeout 240]

Runs the cfg (cwd C:\\FTESurf; the old log and shots are moved aside first),
prints the csprogs hash it ran, grades the `trail` reports and the pixel pair,
and lists data/resume/surf_dune afterwards.  Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAME, "logs", "p475trail.log")
SHOT = os.path.join(GAME, "screenshots", "p475_%s.png")
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")


def run(exe, timeout):
    for p in [LOG] + [SHOT % s for s in ("on", "off", "off2")]:
        if os.path.exists(p):
            os.replace(p, p + ".prev")
    subprocess.run([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                    "+exec", "cfg/test/p475trail.cfg"], cwd=ROOT, timeout=timeout)


def sections(lines):
    out, cur = {}, None
    for s in lines:
        m = re.search(r"==== P475 (\w+) ====", s)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(s)
    return out


def trails(sec):
    """Every `trail` report in a section, in order, as numbers."""
    out, r = [], {}
    for s in sec:
        m = re.search(r"trail: cv (\S+)\s+live slot (\d+) \((\d+) pts, on (\d)\)", s)
        if m:
            r = {"pts": int(m.group(3)), "on": int(m.group(4))}
            out.append(r)
        m = re.search(r"trail: prev slot \d+ \(on (\d), ([\d.]+) s into a ([\d.]+) s fade\)", s)
        if m and r:
            r.update(prevon=int(m.group(1)), into=float(m.group(2)), fade=float(m.group(3)))
        m = re.search(r"trail: run (\d+) samples", s)
        if m and r:
            r["samples"] = int(m.group(1))
    return out


def trail(sec):
    t = trails(sec)
    return t[-1] if t else {}


def changed(a, b, thresh=24):
    from PIL import Image, ImageChops
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return None
    d = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > thresh else 0)
    return d.histogram()[255]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=240)
    a = ap.parse_args()
    cs = os.path.join(GAME, "csprogs.dat")
    print("csprogs %s" % hashlib.sha256(open(cs, "rb").read()).hexdigest()[:16].upper())
    if not a.grade_only:
        run(a.exe, a.timeout)
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log")
        return 2
    lines = [STAMP.sub("", l.rstrip("\n")) for l in open(LOG, errors="replace")]
    text = "\n".join(lines)
    if "FTESurf CSQC loaded" not in text:
        print("CANNOT GRADE: CSQC never loaded")
        return 2
    sec = sections(lines)
    if any(k not in sec for k in ("T1", "T2", "T3", "T3b", "T4")):
        print("CANNOT GRADE: sections missing")
        return 2
    t1text = "\n".join(sec["T1"])
    running = (re.search(r"timer: running on ", t1text) is not None
               and re.search(r"\brecording 1\b", t1text) is not None)
    if not running:
        print("CANNOT GRADE: T1 never had a run on the clock (`cmd timer`), so "
              "nothing below would measure anything")
        return 2

    fails = []

    def check(name, ok, said):
        print("%s %-4s %s" % ("PASS" if ok else "FAIL", name, said))
        if not ok:
            fails.append(name)

    t1, t2, t3, t3b = (trail(sec[k]) for k in ("T1", "T2", "T3", "T3b"))
    check("T1", t1.get("on") == 1 and t1.get("samples", 0) > 50,
          "live on %s, %s samples" % (t1.get("on"), t1.get("samples")))
    t2s = trails(sec["T2"])
    a2, b2 = (t2s + [{}, {}])[:2]
    check("T2", len(t2s) == 2 and a2.get("on") == b2.get("on") == 1
          and a2.get("samples") == b2.get("samples") >= t1.get("samples", 1 << 30),
          "after the cancel: on %s/%s, samples %s then %s a second later (T1 had %s)"
          % (a2.get("on"), b2.get("on"), a2.get("samples"), b2.get("samples"),
             t1.get("samples")))
    check("T3", t3.get("prevon") == 1 and 0 <= t3.get("into", -1) < t3.get("fade", 0),
          "the old run fading: prev on %s, %s s into %s" % (t3.get("prevon"),
                                                          t3.get("into"), t3.get("fade")))
    check("T3b", t3b.get("prevon") == 0, "3 s later: prev on %s" % t3b.get("prevon"))
    on, off, off2 = (SHOT % s for s in ("on", "off", "off2"))
    if all(os.path.exists(p) for p in (on, off, off2)):
        sig, noise = changed(on, off), changed(off, off2)
        check("T4", sig is not None and noise is not None and sig > 400 and sig > 10 * noise,
              "pixels changed: trail on vs off %s, off vs off %s" % (sig, noise))
    else:
        check("T4", False, "screenshots missing")
    bad = len(re.findall(r"Unknown command", text))
    frames = len(re.findall(r"\w+\.qc:\d+:", text))
    check("Q", bad == 0 and frames == 0, "Unknown command %d, QC frames %d" % (bad, frames))

    rd = os.path.join(GAME, "data", "resume", "surf_dune")
    left = []
    for d, _, fs in os.walk(rd):
        left += [os.path.join(d, f) for f in fs]
    print("data/resume/surf_dune after the run: %s" % (left or "empty"))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
