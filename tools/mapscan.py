#!/usr/bin/env python3
"""mapscan.py -- the periodic sweep for maps that appeared since last time.

  python tools/mapscan.py            # dry run: say what changed, write nothing
  python tools/mapscan.py --go       # refresh catalogues, rewrite data/mapdl.txt
  python tools/mapscan.py --go --no-fetch   # skip the network, just re-derive
  python tools/mapscan.py --gamedir DIR ... # another tree's data/ (and maproster's)

Three questions, kept apart because they have different answers:

  what EXISTS      -- maproster.py's catalogue (Momentum's API + KSF's Drive)
  what the PI HAS  -- the only thing a client can actually be offered
  what is NEW      -- first seen by a scan, which is not the same as first seen

The last one is why data/mapseen.txt carries an origin per map.  The first run
has nothing to compare against, so every one of 1748 maps would read as new and
the badge would mean nothing; those rows are written `bootstrap` and never
badge.  Only a name that shows up in a LATER sweep is `scan`, and only those are
New.  A check that cannot measure has to say so rather than guess loudly.

Output is data/mapdl.txt, which the map browser reads to list maps you do not
have (with a Download button) and to badge the recent ones.  It lists only what
the Pi serves, because offering a download that 404s is worse than no button.
"""

import argparse
import datetime
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.join(ROOT, "ftesurf")
DATA = os.path.join(GAME, "data")

ROSTERFILE = os.path.join(DATA, "maproster.txt")
SEENFILE = os.path.join(DATA, "mapseen.txt")
DLFILE = os.path.join(DATA, "mapdl.txt")


def set_paths(gamedir):
    global GAME, DATA, ROSTERFILE, SEENFILE, DLFILE
    GAME = gamedir
    DATA = os.path.join(GAME, "data")
    ROSTERFILE = os.path.join(DATA, "maproster.txt")
    SEENFILE = os.path.join(DATA, "mapseen.txt")
    DLFILE = os.path.join(DATA, "mapdl.txt")


PI_HOST = "proto@192.168.1.102"
PI_MAPS = "/srv/nvme/ftesurf-server/game/momentum/maps"

# How long a map wears the New badge after the sweep that first saw it.
NEW_DAYS = 14

PY = sys.executable or "python"


def sh(cmd, timeout=1800):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def today():
    return datetime.date.today().isoformat()


def read_roster():
    """name -> (mode, src, tier, mtier, ktier).  Absent file is fatal: without
    it this tool has no idea what exists and would write an empty mapdl.txt over
    a good one.  A roster from before mtier/ktier reads them as '-'."""
    if not os.path.exists(ROSTERFILE):
        sys.exit("no %s -- run tools/maproster.py build first" % ROSTERFILE)
    out = {}
    with open(ROSTERFILE, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            f = ln.split()
            if len(f) < 8 or f[0] != "roster":
                continue
            mk = (f[12], f[13]) if len(f) >= 14 else ("-", "-")
            out[f[1]] = (f[2], f[3], f[7]) + mk
    return out


def read_seen():
    """name -> (iso_date, origin).  origin is 'bootstrap' or 'scan'."""
    out = {}
    if not os.path.exists(SEENFILE):
        return out
    with open(SEENFILE, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            f = ln.split()
            if len(f) < 4 or f[0] != "seen":
                continue
            out[f[1]] = (f[2], f[3])
    return out


def write_seen(seen):
    tmp = SEENFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPSEEN 1\n")
        fh.write("# written by tools/mapscan.py -- do not edit\n")
        fh.write("# seen <name> <first-iso> <bootstrap|scan>\n")
        for name in sorted(seen):
            d, origin = seen[name]
            fh.write("seen %s %s %s\n" % (name, d, origin))
    os.replace(tmp, SEENFILE)


def pi_inventory(host):
    """name -> size in bytes, for every bsp the Pi serves.

    One ssh round trip.  `stat -c` rather than ls parsing, because a map name
    can hold a space and this is the list a download button is drawn from."""
    rc, out = sh(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host,
                  "stat -c '%%n %%s' %s/*.bsp 2>/dev/null" % PI_MAPS])
    if rc != 0:
        sys.exit("ssh to %s failed (%d):\n%s" % (host, rc, out[:2000]))
    inv = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        path, _, size = ln.rpartition(" ")
        if not size.isdigit():
            continue
        base = os.path.basename(path)
        if base.lower().endswith(".bsp"):
            inv[base[:-4]] = int(size)
    return inv


def cmd_scan(args):
    if not args.no_fetch:
        for step in (["fetch"], ["hash"], ["build"]):
            rc, out = sh([PY, os.path.join(HERE, "maproster.py")] + step
                         + ["--gamedir", GAME])
            tail = "\n".join(out.strip().splitlines()[-4:])
            print("  maproster %-6s rc=%d  %s" % (step[0], rc, tail.replace("\n", " | ")))
            if rc != 0:
                sys.exit("maproster %s failed" % step[0])

    roster = read_roster()
    seen = read_seen()
    bootstrap = not seen
    inv = pi_inventory(args.host)

    # MATCH CASE-INSENSITIVELY, EMIT THE PI'S SPELLING.
    #
    # The two catalogues lowercase their names and the Pi does not: six maps
    # differ by case alone (Bhop_Mukiology, bhop_HaddocK, bhop_HeLL,
    # bhop_addict_V2, surf_prottos_NightMare, surf_Rebel_Resistance_Revamp).
    # An exact match drops all six, but the sharper problem is the other
    # direction -- the Pi runs Linux and nginx's `alias` uses the captured name
    # verbatim, so a row that said "bhop_haddock" would send every client to a
    # path that does not exist and 404 forever. The name in this file IS the
    # download path, so it has to be the name the Pi actually has on disk.
    #
    # The menu's own "do we already have this" test is case-insensitive already
    # (ui_dl_load lowercases into the byname hash, matching the engine's own
    # search dedup), so a differently-cased local copy is still recognised.
    roster_lc = {}
    for n in roster:
        roster_lc.setdefault(n.lower(), n)

    # Keyed on the Pi's name, because that is what a client will ask for.
    servable = sorted(n for n in inv if n.lower() in roster_lc)

    fresh = []
    stamp = today()
    # `seen` is keyed the same way, so re-casing a file on the Pi does not read
    # as a brand new map and light up the New badge for something years old.
    seen_lc = set(k.lower() for k in seen)
    for name in sorted(roster):
        if name.lower() not in seen_lc:
            seen[name] = (stamp, "bootstrap" if bootstrap else "scan")
            seen_lc.add(name.lower())
            if not bootstrap:
                fresh.append(name)

    cutoff = (datetime.date.today() - datetime.timedelta(days=NEW_DAYS)).isoformat()
    newset = set(n.lower() for n, (d, o) in seen.items()
                 if o == "scan" and d >= cutoff)

    print("roster %d, pi serves %d, offerable %d" % (len(roster), len(inv), len(servable)))
    if bootstrap:
        print("  first run: %d names recorded as bootstrap -- none badge New" % len(seen))
    else:
        print("  new since last sweep: %d" % len(fresh))
        for n in fresh[:20]:
            print("    + %s" % n)
        if len(fresh) > 20:
            print("    ... and %d more" % (len(fresh) - 20))
    print("  wearing the New badge (<= %d days): %d" % (NEW_DAYS, len(newset)))

    # Catalogued but NOT on the Pi -- the sync backlog, reported so a growing
    # gap is visible rather than silently shrinking what the button can offer.
    # FOLDED, like `servable` above. An exact match here counts the six
    # case-mismatched maps as missing -- the very six the fold 20 lines up
    # exists to serve -- and printed 477 where the truth is 471.
    inv_lc = set(n.lower() for n in inv)
    missing = [n for n in roster if n.lower() not in inv_lc]
    print("  catalogued but not on the Pi: %d (run tools/mapsync.py)" % len(missing))

    if not args.go:
        print("\ndry run -- nothing written.  --go to write %s" % os.path.basename(DLFILE))
        return 0

    tmp = DLFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPDL 1\n")
        fh.write("# written by tools/mapscan.py -- do not edit\n")
        fh.write("# dl <name> <mode> <src> <tier> <kb> <first-iso> <new> "
                 "<mtier> <ktier>\n")
        fh.write("# tier is mtier (Momentum's), else ktier (KSF's); 0 = none.\n")
        for name in servable:
            # name is the PI's spelling; the catalogue row is found by fold.
            mode, src, tier, mtier, ktier = roster[roster_lc[name.lower()]]
            d, _origin = seen.get(name, seen.get(roster_lc[name.lower()],
                                                 (stamp, "scan")))
            # The pair is APPENDED: the menu reads argv(1..7) after an n < 8 guard.
            fh.write("dl %s %s %s %s %d %s %d %s %s\n" % (
                name, mode, src, tier if tier != "-" else "0",
                (inv[name] + 1023) // 1024, d,
                1 if name.lower() in newset else 0,
                mtier if mtier != "-" else "0", ktier if ktier != "-" else "0"))
    os.replace(tmp, DLFILE)
    write_seen(seen)
    print("\nwrote %s (%d rows)" % (DLFILE, len(servable)))
    print("wrote %s (%d rows)" % (SEENFILE, len(seen)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true", help="actually write")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip the catalogue refresh (no network)")
    ap.add_argument("--host", default=PI_HOST)
    ap.add_argument("--gamedir", default=GAME,
                    help="the ftesurf/ dir whose data/ is read and written; "
                         "passed on to maproster.py")
    args = ap.parse_args()
    set_paths(args.gamedir)
    return cmd_scan(args)


if __name__ == "__main__":
    sys.exit(main())
