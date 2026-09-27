"""Grade cfg/test/p463pin.cfg -- a byte-identical zone table moved between
directories must not refuse a recording.

Pre-463, pm_verify's zone pin was a string compare that included the SOURCE
DIRECTORY (sv_ccmds.c:5264), so copying a zone file from maps/zones/online/ to
maps/zones/local/ refused every recording of that map with the crc and the rule
identical on both sides.  Patch 463 compares the fields, not the path.

THE ARM IS A PAIR OF RUNS and the pair is the point: the same subjects with a
byte-identical mirror installed (live source `local`, header still `online`) and
without it.  A patch that stopped checking zones altogether passes the first run
and fails the second, so neither run alone is evidence.

Grades:
  P1  each run's zonesrc is the one it was set up to have, and the crc is the
      SAME in both -- the mirror must be byte-identical or nothing else counts.
  P2  data/b88fin.rec PASSes in both runs.
  P3  data/p349_zcrc.rec REFUSEs in both, naming the TABLE specifically.
  P4  the diagnostic prints crc and rule as separate fields.

Usage: python tools/p463pin.py [--exe ftesurf64.exe] [--keep]
"""
import argparse, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAMEDIR = os.path.join(ROOT, "ftesurf")
CFG = "test/p463pin"
LOG = os.path.join(GAMEDIR, "logs", "p463pin.log")
LOCAL = os.path.join(GAMEDIR, "maps", "zones", "local")
MIRROR = os.path.join(LOCAL, "bhop_eazy.json")

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum")
DONOR = os.path.join(MOM, "maps", "zones", "online", "bhop_eazy.json")

TS = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
ZLINE = re.compile(r"^zones\(sv\): (\d+) on bhop_eazy \(([^)]*)\) crc (\S+)")
VLINE = re.compile(r"^VERIFY (\S+) (PASS|HOLD|REFUSE)\s*(.*)$")
PINLINE = re.compile(r"^\s*zone pin\s+(.*)$")

rc = 0


def verdict(name, state, detail):
    global rc
    print("%s  %-40s %s" % ({"PASS": "  PASS", "FAIL": "  FAIL", "ND": "  ----"}[state],
                            name, detail))
    if state == "FAIL":
        rc = 1


def run(exe, timeout, tag):
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
        raise SystemExit("the %s run did not exit in %g s -- killed" % (tag, timeout))
    if not os.path.exists(LOG):
        raise SystemExit("the %s run wrote no log" % tag)
    keep = LOG + "." + tag
    shutil.copyfile(LOG, keep)
    return parse(keep)


def parse(path):
    out = {"zone": None, "verify": {}, "pins": []}
    for ln in open(path, encoding="utf-8", errors="replace"):
        ln = TS.sub("", ln.rstrip())
        m = ZLINE.match(ln.strip())
        if m and out["zone"] is None:
            out["zone"] = (int(m.group(1)), m.group(2), m.group(3))
            continue
        m = VLINE.match(ln.strip())
        if m:
            out["verify"][m.group(1)] = (m.group(2), m.group(3).strip())
            continue
        m = PINLINE.match(ln)
        if m:
            out["pins"].append(m.group(1).strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(DONOR):
        raise SystemExit("no donor zone file at %s (set MOMENTUM_DIR)" % DONOR)
    pre_existing = os.path.exists(MIRROR)
    if pre_existing:
        raise SystemExit("refusing: %s already exists -- this arm owns that path "
                         "and will not overwrite it" % os.path.relpath(MIRROR, ROOT))

    os.makedirs(LOCAL, exist_ok=True)
    try:
        print("run 1/2: no mirror (live source should be maps/zones/online)")
        plain = run(a.exe, a.timeout, "online")
        shutil.copyfile(DONOR, MIRROR)
        same = (open(DONOR, "rb").read() == open(MIRROR, "rb").read())
        print("run 2/2: mirror staged at %s (byte-identical: %s)"
              % (os.path.relpath(MIRROR, ROOT), "yes" if same else "NO"))
        mirror = run(a.exe, a.timeout, "local")
    finally:
        # No bare except: a removal that did not happen must be loud, because a
        # left mirror changes bhop_eazy's zonesrc for every later run in this
        # tree -- and bhop_eazy is a shared fixture (AGENTS.md).
        if os.path.exists(MIRROR):
            if a.keep:
                print("--keep: mirror left at %s" % os.path.relpath(MIRROR, ROOT))
            else:
                os.remove(MIRROR)
                print("mirror removed")

    print()
    print("p463pin -- the zone pin ignores the source directory")
    print()

    # P1: each run states its own source, and the crc must not move.
    for tag, d, want in (("online", plain, "maps/zones/online"),
                         ("local", mirror, "maps/zones/local")):
        if d["zone"] is None:
            verdict("P1 %s source" % tag, "ND", "no zones(sv) line -- did the map load?")
        else:
            n, src, crc = d["zone"]
            verdict("P1 %s source" % tag, "PASS" if src == want else "FAIL",
                    "%d zones from %s crc %s" % (n, src, crc))
    if plain["zone"] and mirror["zone"]:
        pc, mc = plain["zone"][2], mirror["zone"][2]
        verdict("P1 crc unchanged by the move", "PASS" if pc == mc else "FAIL",
                "online %s vs local %s" % (pc, mc))

    # P2: the fix.
    for tag, d in (("online", plain), ("local", mirror)):
        v = d["verify"].get("data/b88fin.rec")
        if v is None:
            verdict("P2 b88fin %s" % tag, "ND", "no VERIFY line for the subject")
        else:
            verdict("P2 b88fin %s" % tag, "PASS" if v[0] == "PASS" else "FAIL",
                    "%s %s" % (v[0], v[1]))

    # P3: the pin still catches a wrong table, and names it.
    for tag, d in (("online", plain), ("local", mirror)):
        v = d["verify"].get("data/p349_zcrc.rec")
        if v is None:
            verdict("P3 zcrc %s" % tag, "ND", "no VERIFY line for the control")
        else:
            ok = (v[0] == "REFUSE" and "zone table" in v[1] and "or rule" not in v[1])
            verdict("P3 zcrc %s" % tag, "PASS" if ok else "FAIL",
                    "%s %s" % (v[0], v[1]))

    # P4: the diagnostic separates the fields.
    pins = mirror["pins"] + plain["pins"]
    split = [p for p in pins if "crc file" in p and "rule file" in p]
    verdict("P4 diagnostic names both fields", "PASS" if split else "FAIL",
            (split[0] if split else "no `crc ... rule ...` line among %d pin line(s)"
             % len(pins)))

    print()
    print("PASS -- a zone table keeps its identity when the file moves."
          if rc == 0 else "FAIL -- see above.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
