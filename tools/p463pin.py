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

DATA = os.path.join(GAMEDIR, "data")
SUBJECT = os.path.join(DATA, "b88fin.rec")

# Round 2.  One header edit each, derived from b88fin.rec, to reach the returns
# the first cut never ran.  `expect` is (verdict, substring) and the substring is
# matched EXACTLY against the reason, not loosely -- "zone table" also occurs in
# "a zone table on one side only", so a loose match would grade green if a real
# difference quietly degraded into a cannot-compare.
DERIVED = [
    ("p463_nosrc",    b"zonesrc online\n", b"",
     ("PASS", None),
     "the source is not compared, so deleting it changes nothing"),
    ("p463_rule",     b"zonerule 1 1 0", b"zonerule 1 1 1",
     ("REFUSE", "the same zones under different zone rules"),
     "same boxes, different rules -- its own verdict, not the table's"),
    ("p463_nocrc",    b"zonecrc c50cfd70\n", b"",
     ("REFUSE", "the file states no zone table"),
     "a file with no crc must refuse, never accept"),
    # Round 4 changed this expectation and the change is the point: round 2
    # answered both the missing-crc and the missing-rule case with "the file
    # states no zone table", and a file that states a table and omits the RULE
    # does state a table.  Round 1 got the cause right by falling through to
    # sscanf; round 2 lost it; this names it.
    ("p463_norule",   b"zonerule 1 1 0\n", b"",
     ("REFUSE", "the file states no zone rule"),
     "a missing rule is not a missing table"),
    ("p463_rule4",    b"zonerule 1 1 0", b"zonerule 1 1 0 1",
     ("REFUSE", "an unreadable zonerule"),
     "a fourth rule term must not be swallowed on the file side"),
    ("p463_rulejunk", b"zonerule 1 1 0", b"zonerule 1 1 x",
     ("REFUSE", "an unreadable zonerule"),
     "garbage is unreadable, not zero"),
    # Round 4.  The ship-blocker: under round 2 this ACCEPTED, because the file
    # side went through sscanf("%d") -- which truncates 4294967297 to 1 -- while
    # the live side range-rejected.  Worse than the accept, the evidence line
    # then printed `rule file 1 1 0`, so a PASS misreported the file's own bytes
    # and tools/reccheck.py's isdigit() test passed it too.  Both independent
    # readers fooled by one input, in the same direction.
    ("p463_rulebig",  b"zonerule 1 1 0", b"zonerule 4294967297 1 0",
     ("REFUSE", "an unreadable zonerule"),
     "an out-of-range rule must not truncate into a match"),
    # Round 4.  The file side was never trimmed, so one trailing space refused a
    # BYTE-IDENTICAL table as "a different zone table" -- this patch's own bug
    # class, one field over.  One splitter serves all three fields now.
    ("p463_crcpad",   b"zonecrc c50cfd70\n", b"zonecrc c50cfd70 \n",
     ("PASS", None),
     "trailing whitespace on the crc is not a different table"),
    # Round 4.  sprintf("%d") never emits '+', and reccheck.py faults it, so
    # accepting it would put the two readers back into disagreement.
    ("p463_ruleplus", b"zonerule 1 1 0", b"zonerule +1 1 0",
     ("REFUSE", "an unreadable zonerule"),
     "'+' is rejected, to agree with the other reader of this header"),
]

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


def derive():
    """Write the six one-edit fixtures.  Bytes in, bytes out: the header is LF
    and the tail is binary, so nothing here may go through text mode."""
    if not os.path.exists(SUBJECT):
        raise SystemExit("no subject at %s" % SUBJECT)
    raw = open(SUBJECT, "rb").read()
    made = []
    for name, find, repl, _, _ in DERIVED:
        dst = os.path.join(DATA, name + ".rec")
        if os.path.exists(dst):
            for p in made:
                os.remove(p)
            raise SystemExit("refusing: %s already exists" % os.path.relpath(dst, ROOT))
        # Bound the edit to the header: these strings must not be matched in the
        # binary tail, and the header is the first couple of KiB.
        head, tail = raw[:2048], raw[2048:]
        if head.count(find) != 1:
            for p in made:
                os.remove(p)
            raise SystemExit("%s: %r occurs %d time(s) in the header, expected 1"
                             % (name, find, head.count(find)))
        open(dst, "wb").write(head.replace(find, repl) + tail)
        made.append(dst)
    print("derived %d fixture(s) from %s" % (len(made), os.path.basename(SUBJECT)))
    return made


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
    made = derive()
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
        left = [p for p in made if os.path.exists(p)]
        if a.keep:
            print("--keep: %d derived fixture(s) left in ftesurf/data" % len(left))
        else:
            for p in left:
                os.remove(p)
            still = [p for p in made if os.path.exists(p)]
            print("derived fixtures removed (%d), still present: %d"
                  % (len(left), len(still)))
            if still:
                print("  WARNING: could not remove %s"
                      % ", ".join(os.path.basename(p) for p in still))

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

    # P3: the pin still catches a wrong table, and names it.  EXACT match --
    # "zone table" as a substring also matches "a zone table on one side only",
    # so a loose test stays green if a real difference degrades into a
    # cannot-compare.  Its evidence reviewer found that looseness.
    for tag, d in (("online", plain), ("local", mirror)):
        v = d["verify"].get("data/p349_zcrc.rec")
        if v is None:
            verdict("P3 zcrc %s" % tag, "ND", "no VERIFY line for the control")
        else:
            ok = (v[0] == "REFUSE" and v[1] == "a different zone table")
            verdict("P3 zcrc %s" % tag, "PASS" if ok else "FAIL",
                    "%s %s" % (v[0], v[1]))

    # P5: the branches the first cut never ran.
    for name, _, _, (wantv, wantr), why in DERIVED:
        v = plain["verify"].get("data/%s.rec" % name)
        if v is None:
            verdict("P5 %s" % name, "ND", "no VERIFY line -- fixture missing?")
            continue
        ok = (v[0] == wantv and (wantr is None or v[1] == wantr))
        verdict("P5 %s" % name, "PASS" if ok else "FAIL",
                "%s %s%s" % (v[0], v[1], "" if ok else "   want %s %r" % (wantv, wantr)))

    # P6: the accept path must SAY it compared something.  Without this a PASS is
    # indistinguishable from a PASS that skipped the zone check -- which is how
    # the round-1 fail-open would have looked in a log.
    matched = [p for p in mirror["pins"] + plain["pins"] if p.startswith("matched:")]
    verdict("P6 accept path states the match", "PASS" if matched else "FAIL",
            matched[0] if matched else "no `zone pin  matched:` line in either run")

    # Declared unexercised: these need the LIVE pin to be wrong, which no header
    # edit can do.  Named rather than left silent, because an untested branch that
    # nobody has written down reads exactly like a tested one.
    verdict("P7 live-side branches", "ND",
            "`this server cannot state its own zone pin`, `too long to read` and "
            "`cannot read N fields` need a doctored SV_VerifyZonePin, not a header edit")

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
