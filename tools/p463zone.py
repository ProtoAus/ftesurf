"""Grade cfg/test/p463zone.cfg -- a donated zone file must build the SAME TABLE.

The zone loader keys on the bare map name (sv_zones.qc:177-182), so making
Momentum's zones apply to a _ksf / _njv / _fix build of the same map needs no
code at all -- only maps/zones/local/<target>.json.  This arm proves that the
copy does what the leaderboard needs, which is NOT "a file loaded":

  Z1  the target's `crc` equals its donor's.  Zone_Hash (sh_zones.qc:264) hashes
      the BUILT table -- type, track, seg, cp, z-band and every point at %.3f --
      and writes it into every recording as `zonecrc`.  Equal crc is the only
      evidence that two builds are being timed against the same start and
      finish, which is what sharing one board key assumes.  Region count is
      graded too, but it is the weaker claim: two different tables can have the
      same count.
  Z2  the server's `zones(sv):` line and the client's `zones:` line agree for
      EVERY map in the run.  They load independently and zones are never
      networked (sv_zones.qc:3-12), so a copy only one VM can see is exactly the
      client/server split Patches 458-461 were about.
  Z3  CONTROL: a map with no zone file and no alias-recoverable donor must not
      report source maps/zones/local.

Usage:
  python tools/p463zone.py                     # stage, run, grade, unstage
  python tools/p463zone.py --grade-only        # grade an existing log
  python tools/p463zone.py --mutate            # Z4: stage the WRONG donor
"""
import argparse, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAMEDIR = os.path.join(ROOT, "ftesurf")
CFG = "test/p463zone"
LOG = os.path.join(GAMEDIR, "logs", "p463zone.log")
LOCAL = os.path.join(GAMEDIR, "maps", "zones", "local")

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum")
ZONLINE = os.path.join(MOM, "maps", "zones", "online")

# donor -> target.  All three graded FIT by tools/census/zonefit.py: start/end
# regions inside the target's world, worldspawn mins identical, and every
# teleDestTargetname resolving in the target's entity lump.
PAIRS = [("surf_utopia", "surf_utopia_njv"),
         ("surf_summer", "surf_summer_ksf"),
         ("surf_tundra", "surf_tundra_v2")]
CONTROL = "surf_1111"

TS = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
SECTION = re.compile(r"^={4} (Z\d) (\S+) ")
SVLINE = re.compile(r"^zones\(sv\): (\d+) on (\S+) \(([^)]*)\) crc (\S+)")
CLLINE = re.compile(r"^zones: (\d+) on (\S+) \(([^)]*)\) crc (\S+)")
CLNONE = re.compile(r"^zones: none for (\S+)")

rc = 0


def verdict(name, state, detail):
    global rc
    print("%s  %-34s %s" % ({"PASS": "  PASS", "FAIL": "  FAIL", "ND": "  ----"}[state],
                            name, detail))
    if state == "FAIL":
        rc = 1


def installed_by_tool(target, donor):
    """True when tools/zoneinstall.py put exactly this donation here.

    Once the donations are installed the arm's subject already exists, and the
    honest thing is to grade THAT rather than to shadow it with a second copy --
    the installed tree is what a player loads.  Any other pre-existing file is
    still refused, because overwriting somebody's edit to measure something is
    how a driver's cleanup becomes a data-loss bug."""
    man = os.path.join(GAMEDIR, "maps", "zones", "manifest.txt")
    if not os.path.exists(man):
        return False
    for ln in open(man, encoding="utf-8"):
        f = ln.split()
        if len(f) >= 3 and f[0] == target and f[1] == "donation" and f[2] == donor:
            return True
    return False


def stage(mutate):
    """Refuse rather than overwrite: a left-behind local file shadows the shipped
    zones for every later run in this tree, silently."""
    os.makedirs(LOCAL, exist_ok=True)
    wrote = []
    for donor, target in PAIRS:
        dst = os.path.join(LOCAL, target + ".json")
        if os.path.exists(dst):
            if not mutate and installed_by_tool(target, donor):
                print("in place  %-34s (installed, grading it as found)"
                      % os.path.relpath(dst, ROOT))
                continue
            for p in wrote:
                os.remove(p)
            raise SystemExit("refusing: %s already exists -- it shadows the shipped "
                             "zones%s" % (os.path.relpath(dst, ROOT),
                                          " (--mutate needs a clean tree: run "
                                          "`python tools/zoneinstall.py --donations-only` "
                                          "to see what is installed)" if mutate else ""))
        # Z4 sends every target the FIRST pair's donor, so two of the three crcs
        # must differ.  Not a random file: a real zone file for a real map, which
        # is the mistake a copy script would actually make.
        src = os.path.join(ZONLINE, (PAIRS[0][0] if mutate else donor) + ".json")
        if not os.path.exists(src):
            for p in wrote:
                os.remove(p)
            raise SystemExit("no donor zone file at %s" % src)
        shutil.copyfile(src, dst)
        wrote.append(dst)
        print("staged %-34s <- %s" % (os.path.relpath(dst, ROOT), os.path.basename(src)))
    return wrote


def unstage(wrote, keep):
    """No bare `except OSError: pass` -- a removal that did not happen must be loud."""
    for p in wrote:
        if keep:
            print("--keep: left %s" % os.path.relpath(p, ROOT))
            continue
        if os.path.exists(p):
            os.remove(p)
    # List the tree, but count only what the manifest does NOT account for -- once
    # zoneinstall.py has run, 66 files legitimately live here and naming them all
    # every run buries the one line that would matter.
    left = sorted(f[:-5] for f in os.listdir(LOCAL)
                  if f.lower().endswith(".json")) if os.path.isdir(LOCAL) else []
    known = set()
    man = os.path.join(GAMEDIR, "maps", "zones", "manifest.txt")
    if os.path.exists(man):
        for ln in open(man, encoding="utf-8"):
            f = ln.split()
            if len(f) >= 2 and not ln.startswith("#"):
                known.add(f[0])
    stray = [n for n in left if n not in known]
    print("maps/zones/local after the run: %d file(s), %d in the manifest, %d stray"
          % (len(left), len(left) - len(stray), len(stray)))
    if stray and not keep:
        print("  WARNING: not staged by this driver and not in the manifest: %s"
              % ", ".join(stray))


def parse():
    sect, order, cur = {}, [], None
    for ln in open(LOG, encoding="utf-8", errors="replace"):
        ln = TS.sub("", ln.strip())
        m = SECTION.match(ln)
        if m:
            cur = (m.group(1), m.group(2))
            sect[cur] = {"sv": None, "cl": None}
            order.append(cur)
            continue
        if cur is None:
            continue
        d = sect[cur]
        m = SVLINE.match(ln)
        if m and d["sv"] is None:
            d["sv"] = (int(m.group(1)), m.group(2), m.group(3), m.group(4))
            continue
        m = CLLINE.match(ln)
        if m and d["cl"] is None:
            d["cl"] = (int(m.group(1)), m.group(2), m.group(3), m.group(4))
            continue
        m = CLNONE.match(ln)
        if m and d["cl"] is None:
            d["cl"] = (0, m.group(1), "none", "-")
    return sect, order


def grade(mutate):
    if not os.path.exists(LOG):
        print("no log at %s" % LOG)
        return 2
    sect, order = parse()
    if not order:
        print("no `==== Z<n> <map>` markers -- did the cfg run?")
        return 2

    print("p463zone -- a donated zone file builds the same table")
    print("            (%s)" % LOG)
    print()

    bymap = {}
    for (tag, mapname) in order:
        bymap[mapname] = sect[(tag, mapname)]

    # Z2 first: without VM agreement, nothing below means anything.
    dis = []
    for (tag, mapname) in order:
        d = sect[(tag, mapname)]
        if d["sv"] is None and d["cl"] is None:
            dis.append("%s: neither VM printed" % mapname)
        elif d["sv"] is None:
            dis.append("%s: server silent" % mapname)
        elif d["cl"] is None:
            dis.append("%s: client silent" % mapname)
        elif d["sv"] != d["cl"]:
            dis.append("%s: sv %s vs cl %s" % (mapname, d["sv"], d["cl"]))
    verdict("Z2 both VMs agree", "PASS" if not dis else "FAIL",
            "%d map(s) checked, %d disagree%s"
            % (len(order), len(dis), "" if not dis else "; " + "; ".join(dis[:3])))

    # Z1: donor vs target, within one log.
    for donor, target in PAIRS:
        dd, dt = bymap.get(donor), bymap.get(target)
        if dd is None or dd["sv"] is None:
            verdict("Z1 %s" % target, "ND", "donor %s did not load" % donor)
            continue
        if dt is None or dt["sv"] is None:
            verdict("Z1 %s" % target, "FAIL", "target printed no zones line")
            continue
        dn, dsrc, dcrc = dd["sv"][0], dd["sv"][2], dd["sv"][3]
        tn, tsrc, tcrc = dt["sv"][0], dt["sv"][2], dt["sv"][3]
        why = []
        if tsrc != "maps/zones/local":
            why.append("source %s, expected maps/zones/local" % tsrc)
        if tcrc != dcrc:
            why.append("crc %s != donor %s" % (tcrc, dcrc))
        if tn != dn:
            why.append("%d regions != donor %d" % (tn, dn))
        ok = not why
        if mutate:
            # Z4 inverts the expectation for the two pairs fed the wrong donor.
            expect_equal = (donor == PAIRS[0][0])
            ok = (tcrc == dcrc) if expect_equal else (tcrc != dcrc)
            verdict("Z4 %s" % target, "PASS" if ok else "FAIL",
                    "crc %s vs donor %s (%s)"
                    % (tcrc, dcrc, "must match" if expect_equal else "MUST DIFFER"))
            continue
        verdict("Z1 %s" % target, "PASS" if ok else "FAIL",
                "%d regions from %s, crc %s == donor %s" % (tn, tsrc, tcrc, donor)
                if ok else "; ".join(why))

    # Z3 control.
    dc = bymap.get(CONTROL)
    if dc is None or dc["sv"] is None:
        verdict("Z3 %s CONTROL" % CONTROL, "ND",
                "no zones line at all -- map may not be installed")
    else:
        src = dc["sv"][2]
        verdict("Z3 %s CONTROL" % CONTROL, "PASS" if src != "maps/zones/local" else "FAIL",
                "%d zones from %s (must not be maps/zones/local)" % (dc["sv"][0], src))

    print()
    print("PASS -- a copied zone file builds a byte-identical table on both VMs."
          if rc == 0 else "FAIL -- see above.")
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=420)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--mutate", action="store_true")
    ap.add_argument("--grade-only", action="store_true")
    a = ap.parse_args()

    if a.grade_only:
        return grade(a.mutate)

    wrote = stage(a.mutate)
    try:
        if os.path.exists(LOG):
            os.remove(LOG)
        flags = 0x08000000 if os.name == "nt" else 0
        p = subprocess.Popen([os.path.join(ROOT, a.exe), "-WindowStyle", "Minimized",
                              "+exec", CFG], cwd=ROOT, creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < a.timeout:
            time.sleep(1)
        if p.poll() is None:
            p.kill()
            raise SystemExit("the run did not exit in %g s -- killed" % a.timeout)
        secs = time.time() - t0
    finally:
        unstage(wrote, a.keep)
    print("ran %s on %s for %.0f s" % (a.exe, CFG, secs))
    return grade(a.mutate)


if __name__ == "__main__":
    sys.exit(main())
