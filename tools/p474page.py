#!/usr/bin/env python3
"""p474page.py -- driver and grader for cfg/test/p474page.cfg (Patch 474: the
online board pages as the list scrolls).

    python tools/p474page.py [--exe ftesurf64.exe] [--grade-only] [--timeout 300]

Runs the cfg (cwd C:\\FTESurf; the old log is moved aside first, logs append),
prints the csprogs hash it ran so a control run can be told from a fixed one,
then grades each arm from its own board_status.  Needs the Pi's surfd on the
LAN.  Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "ftesurf", "logs", "p474page.log")
STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
ROW = re.compile(r"^\s+(\d+)\s\s.*ticks \d")


def run(exe, timeout):
    if os.path.exists(LOG):
        os.replace(LOG, LOG + ".prev")
    subprocess.run([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                    "+exec", "cfg/test/p474page.cfg"], cwd=ROOT, timeout=timeout)


def sections(lines):
    out, cur = {}, None
    for s in lines:
        m = re.search(r"==== P474 (\w+) ====", s)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(s)
    return out


def status(sec):
    """The LAST board_status in a section: tier, rows, counts, more, ranks."""
    st = None
    for s in sec:
        m = re.search(r"board: \S+ track \d+ leg \d+  tier (\S+)", s)
        if m:
            st = {"tier": m.group(1), "ranks": []}
            continue
        if st is None:
            continue
        m = re.search(r"rows (\d+)\s+ranked (\d+)", s)
        if m:
            st["rows"], st["ranked"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"more (\d+)\s+append (\d+)\s+held (\d+) of (\d+)", s)
        if m:
            st["more"], st["held"] = int(m.group(1)), int(m.group(3))
        m = ROW.match(s)
        if m:
            st["ranks"].append(int(m.group(1)))
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    cs = os.path.join(ROOT, "ftesurf", "csprogs.dat")
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
    want = ["A", "B", "C1", "C2", "C3", "C4", "D", "D2", "E"]
    if any(w not in sec for w in want):
        print("CANNOT GRADE: sections missing: %s" % [w for w in want if w not in sec])
        return 2

    fails = []

    def check(name, ok, said):
        print("%s %-4s %s" % ("PASS" if ok else "FAIL", name, said))
        if not ok:
            fails.append(name)

    def board(name, rows, more=None):
        st = status(sec[name])
        if not st or "rows" not in st:
            check(name, False, "no board_status in the section")
            return None
        contig = st["ranks"] == list(range(1, len(st["ranks"]) + 1))
        ok = st["rows"] == rows and len(st["ranks"]) == rows and contig
        if more is not None:
            ok = ok and st.get("more") == more
        check(name, ok, "rows %s, %d ranks %s, more %s"
              % (st["rows"], len(st["ranks"]), "contiguous from 1" if contig
                 else "NOT contiguous", st.get("more")))
        return st

    board("A", 100, more=1)
    board("B", 400)
    board("C1", 100)
    board("C2", 200)
    board("C3", 200)
    board("C4", 300)
    board("D", 1000, more=0)
    check("D2", "more not asked at 1000 rows" in "\n".join(sec["D2"]),
          "a further board_more at the cap is refused")
    st = status(sec["E"])
    if st and "rows" in st:
        contig = st["ranks"] == list(range(1, len(st["ranks"]) + 1))
        ok = (st["tier"] == "ranked" and contig
              and st["rows"] == min(st["ranked"], 100))
        check("E", ok, "tier %s, rows %d of ranked %d, ranks %s"
              % (st["tier"], st["rows"], st["ranked"],
                 "contiguous" if contig else "NOT contiguous"))
    else:
        check("E", False, "no board_status in the section")
    bad = len(re.findall(r"Unknown command", text))
    frames = len(re.findall(r"\w+\.qc:\d+:", text))
    check("Q", bad == 0 and frames == 0,
          "Unknown command %d, QC frames %d" % (bad, frames))
    print("%d check(s) failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
