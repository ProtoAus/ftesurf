#!/usr/bin/env python3
"""p449cap.py -- fire the run line's mark cap (LN_EVCAP) and grade its policy.

Runs cfg/test/p449cap.cfg twice: on the progs as built, then on progs built with
LN_EVCAP lowered (default 20).  The define is edited in src/client/cl_lines.qc,
the build run, and the original bytes written back and rebuilt, with the csprogs
hash before and after compared, so the install is left as it was found.  The
capped table is graded against the uncapped one put through Line_Ev's policy:
when the table is full the peaks go as a class and later peaks are ignored; past
that each further mark is counted and dropped.

    python tools/p449cap.py [--cap 20] [--exe ftesurf64.exe] [--grade-only]

Needs pwsh 7, and mingw64's bin for the build on the laptop (put first on PATH
here).  Exit 0 pass, 1 fail, 2 cannot grade.

RESULT (2026-10-03, the N100 laptop; surf_colin_blaster_69000 runid
20260930-085843-0, 35 marks):
  as built csprogs EF78D1D34178CB53; capped (LN_EVCAP 20) E7EB75EEB58F612B;
  rebuilt EF78D1D34178CB53, as before.
  K1 uncapped 35 marks, cut 0, dropped 0.   K2 the capped table is the model's,
  20 marks, mark for mark.   K3 20 held, cut 1, 9 dropped = the model.
  K4 `marks 20, peaks cut, 9 dropped  (cap 20)`.
  MUTANTS, against the logged tables: no peak cut and halving both predict a
  different table (K2); keeping later peaks predicts the SAME table on this
  fixture -- the only later apex arrives when it is full again -- but drops 11,
  not 9 (K3).  So K3 is not decoration: it is the only check that sees that one.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAMEDIR, "logs", "p449cap.log")
LINES = os.path.join(ROOT, "src", "client", "cl_lines.qc")
DEFINE = re.compile(r"^(#define LN_EVCAP\s+)(\d+)", re.M)
APEX, TROUGH = 4, 5


def csprogs():
    with open(os.path.join(GAMEDIR, "csprogs.dat"), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16].upper()


def build():
    env = dict(os.environ)
    env["PATH"] = r"C:\msys64\mingw64\bin;C:\msys64\usr\bin;" + env["PATH"]
    r = subprocess.run(["pwsh", "-NoProfile", "-Command", "./build.ps1 -Jobs 4"],
                       cwd=os.path.join(ROOT, "src"), env=env,
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    warn = [l for l in out.splitlines() if "warning" in l.lower()
            and "0 warnings" not in l.lower()]
    if r.returncode != 0 or warn:
        raise SystemExit("build failed or warned:\n"
                         + "\n".join(warn or out.splitlines()[-15:]))


def run(exe, timeout, tag):
    if os.path.exists(LOG):
        os.remove(LOG)
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", "test/p449cap.cfg"], cwd=ROOT,
                         creationflags=0x08000000 if os.name == "nt" else 0,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the %s run did not exit in %g s -- killed" % (tag, timeout))
    shutil.copyfile(LOG, LOG + "." + tag)


def parse(path):
    txt = open(path, "r", errors="replace").read()
    if "=== p449cap done ===" not in txt:
        return None
    sec = txt.split("=== p449cap marks ===", 1)[1]
    lines = [re.sub(r"^\S+ \S+ ", "", l) for l in sec.splitlines()]
    hdr = next(l.split() for l in lines if l.startswith("lnmb "))
    # `lnm i kind sub t ordinal x y z ...`: the mark's identity is kind + ordinal
    marks = [(int(float(f[2])), int(float(f[5]))) for f in
             (l.split() for l in lines if l.startswith("lnm "))]
    status = next((l.strip() for l in lines if l.strip().startswith("marks ")), "")
    return {"n": int(float(hdr[2])), "cut": int(float(hdr[3])),
            "drop": int(float(hdr[4])), "marks": marks, "status": status}


def model(marks, cap):
    """Line_Ev's policy over the uncapped table, in arrival order."""
    held, cut, drop = [], False, 0
    for k, i in marks:
        if cut and k in (APEX, TROUGH):
            continue
        if len(held) >= cap:
            if not cut:
                held = [m for m in held if m[0] not in (APEX, TROUGH)]
                cut = True
            if len(held) >= cap:
                drop += 1
                continue
        held.append((k, i))
    return held, cut, drop


def grade(cap):
    full = parse(LOG + ".full") if os.path.exists(LOG + ".full") else None
    capd = parse(LOG + ".capped") if os.path.exists(LOG + ".capped") else None
    if not full or not capd:
        print("CANNOT GRADE: a run is missing or did not reach its end")
        return 2
    fails = 0

    def verdict(ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print("%s %s" % ("PASS" if ok else "FAIL", text))

    verdict(full["cut"] == 0 and full["drop"] == 0 and full["n"] == len(full["marks"]),
            "K1  uncapped: %d marks, cut %d, dropped %d"
            % (full["n"], full["cut"], full["drop"]))
    held, cut, drop = model(full["marks"], cap)
    if not cut or not drop:
        print("CANNOT GRADE K2-K4: cap %d does not fire both stages on %d marks"
              % (cap, len(full["marks"])))
        return 2
    first = next((i for i, (a, b) in enumerate(zip(capd["marks"], held)) if a != b),
                 None)
    verdict(capd["marks"] == held,
            "K2  capped table = the model's: %d marks against %d, first difference %s"
            % (len(capd["marks"]), len(held), "none" if first is None else first))
    verdict((capd["n"], capd["cut"], capd["drop"]) == (len(held), 1, drop),
            "K3  counters %d held, cut %d, %d dropped; the model %d, 1, %d"
            % (capd["n"], capd["cut"], capd["drop"], len(held), drop))
    want = "marks %d, peaks cut, %d dropped  (cap %d)" % (len(held), drop, cap)
    verdict(capd["status"] == want,
            "K4  status `%s`, want `%s`" % (capd["status"], want))
    print("4 check(s), %d failed" % fails)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=20)
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=180)
    a = ap.parse_args()
    if not a.grade_only:
        h0 = csprogs()
        print("csprogs as built %s" % h0)
        run(a.exe, a.timeout, "full")
        src = open(LINES, "rb").read()
        try:
            txt = src.decode()
            if len(DEFINE.findall(txt)) != 1:
                raise SystemExit("LN_EVCAP define not found exactly once")
            open(LINES, "wb").write(DEFINE.sub(r"\g<1>%d" % a.cap, txt).encode())
            build()
            print("csprogs capped   %s (LN_EVCAP %d)" % (csprogs(), a.cap))
            run(a.exe, a.timeout, "capped")
        finally:
            open(LINES, "wb").write(src)
            build()
        h1 = csprogs()
        print("csprogs rebuilt  %s -- %s" % (h1, "as before" if h1 == h0
                                              else "DIFFERS FROM BEFORE"))
        if h1 != h0:
            return 1
    return grade(a.cap)


if __name__ == "__main__":
    sys.exit(main())
