#!/usr/bin/env python3
"""P884/P885 arms (cfg/test/p884phys.cfg, p885hop.cfg): control then fixed progs swapped
into C:/FTESurf/ftesurf for one run each.

    python tools/p884arms.py --control <dir> --fixed <dir> --out <dir> [--cfgdir <dir>] [arm ...]

<dir> holds qwprogs.dat + csprogs.dat (build.ps1 -NoDeploy in worktrees at the commit before
the patch and at the patch).  Run it under the rig lock.  The installed progs are copied
aside first and put back in a finally, unless something else wrote them meanwhile.
p885hop starts from `!r`, which on surf_tendies puts the body at the start spot in the
owner's saves (-1106.8 11246.7 yaw 64.7, measured 21 Oct); the cfg's turn is aimed from it.
Result 21 Oct (qwprogs control 4ab61a33 / fixed d8a47ba9): p884 E `solid BSP` / `solid NOT`,
F z -696.0 / -1112.1; p885 H `practice 1` / `practice 0` (both running, jumps 2, out at
x -996), I `hopped 1` on both.
Review 1 (qwprogs 89550455): p885walk W `practice 1` on control and the fix, `practice 0` on
7cfaae5a (--side v1=...) -- the unrested fly-through hole; p885hop H still `practice 0`.
"""
import argparse, hashlib, os, shutil, subprocess, time

ROOT = r"C:\FTESurf"
GAME = os.path.join(ROOT, "ftesurf")
ARMS = {"p884phys": "surf_lovetunnel", "p885hop": "surf_tendies", "p885walk": "surf_tendies"}
PROGS = ("qwprogs.dat", "csprogs.dat")


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def listing(m):
    out = set()
    for sub in ("runs", "resume", "saves", "evidence"):
        d = os.path.join(GAME, "data", sub, m)
        for dp, dn, fn in os.walk(d):
            out.add(dp)
            for f in fn:
                out.add(os.path.join(dp, f))
    return out


def run(cfg, log):
    if os.path.exists(log):
        os.remove(log)
    p = subprocess.Popen([os.path.join(ROOT, "ftesurf64.exe"), "-WindowStyle", "Minimized",
                          "+exec", "test/%s.cfg" % cfg], cwd=ROOT, creationflags=0x08000000,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < 150:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("  KILLED after 150 s")
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", required=True)
    ap.add_argument("--fixed", required=True)
    ap.add_argument("--side", action="append", default=[], metavar="NAME=DIR",
                    help="another build to run after these two")
    ap.add_argument("--cfgdir", default=os.path.join(GAME, "cfg", "test"))
    ap.add_argument("--out", required=True)
    ap.add_argument("arms", nargs="*")
    a = ap.parse_args()
    sides = {"control": a.control, "fixed": a.fixed}
    sides.update(x.split("=", 1) for x in a.side)
    arms = a.arms or list(ARMS)
    os.makedirs(a.out, exist_ok=True)
    inst = {f: sha(os.path.join(GAME, f)) for f in PROGS}
    print("installed", inst)
    bak = os.path.join(a.out, "installed")
    os.makedirs(bak, exist_ok=True)
    for f in PROGS:
        shutil.copy2(os.path.join(GAME, f), os.path.join(bak, f))
    try:
        for arm in arms:
            m = ARMS[arm]
            cfg = os.path.join(GAME, "cfg", "test", arm + ".cfg")
            ours = os.path.abspath(os.path.join(a.cfgdir, arm + ".cfg")) != os.path.abspath(cfg)
            if ours:
                shutil.copy2(os.path.join(a.cfgdir, arm + ".cfg"), cfg)
            before = listing(m)
            for side in sides:
                for f in PROGS:
                    shutil.copy2(os.path.join(sides[side], f), os.path.join(GAME, f))
                print("%s %s qwprogs %s" % (arm, side, sha(os.path.join(GAME, "qwprogs.dat"))), flush=True)
                log = os.path.join(GAME, "logs", arm + ".log")
                dt = run(arm, log)
                dst = os.path.join(a.out, "%s_%s.log" % (arm, side))
                shutil.copy2(log, dst)
                os.remove(log)
                print("  %.0f s -> %s" % (dt, dst), flush=True)
            if ours:
                os.remove(cfg)
            new = sorted(listing(m) - before)
            print("  new under data/*/%s: %d" % (m, len(new)))
            for p in new:
                print("    " + p)
    finally:
        mine = {sha(os.path.join(d, f)) for d in sides.values() for f in PROGS} | set(inst.values())
        for f in PROGS:
            cur = sha(os.path.join(GAME, f))
            if cur not in mine:
                print("NOT restoring %s: %s is someone else's write" % (f, cur))
                continue
            shutil.copy2(os.path.join(bak, f), os.path.join(GAME, f))
        now = {f: sha(os.path.join(GAME, f)) for f in PROGS}
        print("restored", now, "OK" if now == inst else "MISMATCH")


if __name__ == "__main__":
    main()
