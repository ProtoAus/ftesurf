"""zoneinstall.py -- materialise Momentum's timer zones into the editable folder,
and donate a zone file to the builds that have none.

WHY THIS EXISTS.  The zone loader keys on the bare map name and concatenates:

    maps/zones/local/<map>.json      tried first, WINS
    maps/zones/online/<map>.json     Momentum's shipped library
    the BSP's own trigger_momentum_timer_* brushes

(sv_zones.qc:177-182, mirrored independently in cl_zones.qc:296-301.)  Two
consequences follow, and this tool exists for both.

  1. Nothing in the gamedir is editable today.  `online/` resolves into the
     Momentum install, so adjusting a zone means editing Momentum's files.
     Copying each map's zone file to `local/<map>.json` puts an editable copy on
     the winning path, one file per map, named after the map.

  2. There is NO ALIASING on that path.  `surf_aircontrol_ksf` gets no zones at
     all -- and so cannot be timed -- while `surf_aircontrol.json` sits installed
     one directory away.  71 builds in this library are in that position.  A copy
     of the donor's file under the target's name fixes it with no code change.

WHAT YOU GIVE UP BY MIRRORING EVERYTHING, stated because it is not reversible by
accident: `local/` wins forever.  Once a map has a file here, a zone fix
Momentum ships upstream never reaches this install again.  That is the trade for
editability and it was chosen deliberately; `--donations-only` is the other side
of it.

WHY A DONATION IS NOT JUST A COPY.  A zone is an absolute world polygon
(sh_zones.qc:34) and its restart point is usually a targetname resolved in the
BSP (3241 of 3297 regions).  So the donor's file only means the same thing on
the target if the two builds share a coordinate frame AND the target's entity
lump carries those names.  tools/census/zonefit.py measures exactly that, and
this tool refuses any pair it does not pass -- 5 of the 71 are genuinely
different maps that happen to share a stem.

THE MANIFEST IS WHAT MAKES RE-RUNNING SAFE.  maps/zones/manifest.txt records
what was written and its hash, so a second run can tell YOUR EDIT from a file
this tool put there and will not overwrite the former.  It lives beside
`local/`, not inside it, so no `*.json` glob ever sees it.

Refuses by default and prints the plan; pass --go to write.  Idempotent.

Usage:
  python tools/zoneinstall.py                     # show the plan
  python tools/zoneinstall.py --go
  python tools/zoneinstall.py --donations-only --go
  python tools/zoneinstall.py --verify            # hash every file against the manifest
"""
import argparse, hashlib, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "census"))
sys.path.insert(0, HERE)

import zonefit
from mapmeta import strip_suffix        # one speller for the suffix rule

MOM = zonefit.MOM
MOMMAPS = zonefit.MOMMAPS
MOMONLINE = os.path.join(MOMMAPS, "zones", "online")
MOMLOCAL = os.path.join(MOMMAPS, "zones", "local")

DEST = os.path.join(ROOT, "ftesurf", "maps", "zones", "local")
MANIFEST = os.path.join(ROOT, "ftesurf", "maps", "zones", "manifest.txt")

# A donation is written for these verdicts only.  NO-DESTS is included on
# purpose: a name that does not resolve degrades to the zone's own floor and
# SAYS SO (sv_zones.qc:340), so the map times correctly and `!r` lands at the
# start polygon's centroid instead of the authored spot.  That is a caveat, not
# a break, and the manifest records which maps carry it.
INSTALLABLE = {"FIT", "NO-DESTS", "UNCHECKED"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:16]


def read_manifest():
    out = {}
    if not os.path.exists(MANIFEST):
        return out
    for ln in open(MANIFEST, encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        f = ln.split()
        if len(f) >= 4:
            out[f[0]] = {"kind": f[1], "donor": f[2], "hash": f[3],
                         "verdict": f[4] if len(f) > 4 else "-"}
    return out


def write_manifest(rows):
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# written by tools/zoneinstall.py -- <map> <kind> <donor> <sha16> "
                 "<verdict>\n")
        fh.write("# kind: mirror = that map's own zones; donation = another build's,\n")
        fh.write("#       verified by tools/census/zonefit.py.\n")
        fh.write("# A file whose hash no longer matches is YOUR EDIT and is never\n")
        fh.write("# overwritten without --force.\n")
        for name in sorted(rows):
            r = rows[name]
            fh.write("%s %s %s %s %s\n"
                     % (name, r["kind"], r["donor"], r["hash"], r["verdict"]))


def library():
    """-> ({mapname_lower: zone source path}, {bsp names lower}).

    Momentum's own local/ wins over its online/, which is the precedence
    Momentum itself uses, so an edit made on that side is what gets mirrored.
    """
    zon = {}
    for d in (MOMONLINE, MOMLOCAL):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.lower().endswith(".json"):
                zon[f[:-5].lower()] = os.path.join(d, f)
    bsp = {f[:-4].lower() for f in os.listdir(MOMMAPS) if f.lower().endswith(".bsp")}
    return zon, bsp


def plan(donations_only):
    zon, bsp = library()

    # Pin the donor lookup to the Momentum install: DEST is about to be written
    # and a second run must not read back its own copies.
    zonefit.SEARCH = [MOMLOCAL, MOMONLINE]

    mirrors, donations, refused = [], [], []

    if not donations_only:
        for name, src in sorted(zon.items()):
            mirrors.append((name, src, "self"))

    for name in sorted(bsp):
        if name in zon:
            continue
        base = strip_suffix(name)
        if base == name or base not in zon:
            continue
        verdict, why, _ = zonefit.check(base, name)
        if verdict in INSTALLABLE:
            donations.append((name, zon[base], base, verdict, why))
        else:
            refused.append((name, base, verdict, why))

    return mirrors, donations, refused


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="actually write")
    ap.add_argument("--donations-only", action="store_true",
                    help="only the builds that have no zones at all")
    ap.add_argument("--force", action="store_true",
                    help="overwrite files that differ from the manifest (YOUR EDITS)")
    ap.add_argument("--verify", action="store_true",
                    help="hash every installed file against the manifest and stop")
    a = ap.parse_args()

    if not os.path.isdir(MOMMAPS):
        raise SystemExit("no Momentum maps dir at %s (set MOMENTUM_DIR)" % MOMMAPS)

    man = read_manifest()

    if a.verify:
        if not man:
            print("no manifest at %s -- nothing has been installed by this tool"
                  % os.path.relpath(MANIFEST, ROOT))
            return 0
        edited, missing, ok = [], [], 0
        for name, r in sorted(man.items()):
            p = os.path.join(DEST, name + ".json")
            if not os.path.exists(p):
                missing.append(name)
            elif sha(p) != r["hash"]:
                edited.append(name)
            else:
                ok += 1
        print("manifest %d rows: %d unchanged, %d edited by you, %d missing"
              % (len(man), ok, len(edited), len(missing)))
        for n in edited:
            print("  edited   %s (%s from %s)" % (n, man[n]["kind"], man[n]["donor"]))
        for n in missing:
            print("  missing  %s" % n)
        stray = sorted(f[:-5] for f in os.listdir(DEST)
                       if f.lower().endswith(".json") and f[:-5] not in man) \
            if os.path.isdir(DEST) else []
        for n in stray:
            print("  yours    %s (not from this tool)" % n)
        return 0

    mirrors, donations, refused = plan(a.donations_only)

    print("zoneinstall -- MOM=%s" % MOM)
    print("             dest %s" % os.path.relpath(DEST, ROOT))
    print()
    print("  mirror    %4d  each map's own zone file, made editable" % len(mirrors))
    print("  donation  %4d  builds with no zones of their own" % len(donations))
    print("  refused   %4d  pairs zonefit rejected" % len(refused))
    print()
    for name, base, verdict, why in refused:
        print("  REFUSED %-30s <- %-24s %-10s %s" % (name, base, verdict, why))
    if refused:
        print()
    for name, src, base, verdict, why in donations:
        flag = "" if verdict == "FIT" else ("   [%s: %s]" % (verdict, why))
        print("  donate  %-30s <- %s%s" % (name, base, flag))
    print()

    if not a.go:
        print("plan only -- pass --go to write %d file(s)"
              % (len(mirrors) + len(donations)))
        return 0

    os.makedirs(DEST, exist_ok=True)
    rows = dict(man)
    wrote = skipped = kept = 0
    for name, src, base, verdict, why in ([(n, s, b, "-", "-") for n, s, b in mirrors]
                                          + donations):
        dst = os.path.join(DEST, name + ".json")
        kind = "mirror" if base == "self" else "donation"
        if os.path.exists(dst):
            cur = sha(dst)
            known = man.get(name)
            if known is None:
                # Never written by this tool -- it is the user's own file.
                print("  keeping your %s.json (not from this tool)" % name)
                kept += 1
                continue
            if cur != known["hash"] and not a.force:
                print("  keeping your edit to %s.json" % name)
                kept += 1
                continue
            if cur == sha(src):
                skipped += 1
                rows[name] = {"kind": kind, "donor": base, "hash": cur,
                              "verdict": verdict}
                continue
        shutil.copyfile(src, dst)
        rows[name] = {"kind": kind, "donor": base, "hash": sha(dst),
                      "verdict": verdict}
        wrote += 1

    write_manifest(rows)
    n = len([f for f in os.listdir(DEST) if f.lower().endswith(".json")])
    print()
    print("wrote %d, unchanged %d, kept yours %d" % (wrote, skipped, kept))
    print("%s now holds %d .json" % (os.path.relpath(DEST, ROOT), n))
    print("manifest %s (%d rows)" % (os.path.relpath(MANIFEST, ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
