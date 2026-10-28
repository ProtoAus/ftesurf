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

SINCE 11 OCT 2026 THE PI LISTS UPSTREAM ITSELF (surfd/mapwatch.py: Momentum's
public API and ksf.surf/maps, and it fetches what is new).  This sweep reads
that catalogue back and adds the names the roster lacks -- KSF's site listed 23
maps the Drive sheet did not -- and sends the one list the Pi cannot read:
Momentum's Beta maps, from the game's own cache here (extra.tsv).

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
import json
import os
import re
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
PI_WATCH = "/srv/nvme/surfd/data/mapwatch"      # mapwatch.py's --state

# How long a map wears the New badge after the sweep that first saw it.
NEW_DAYS = 14

PY = sys.executable or "python"


def sh(cmd, timeout=1800, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
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


def pi_catalogue(host):
    """mapwatch.py's last reading of both lists, name -> row; None when the Pi
    has none, which is said rather than read as "nothing new upstream"."""
    # stdout alone: ssh's own warnings go to stderr, and sh() folds the two.
    try:
        p = subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host,
                            "cat %s/catalogue.json" % PI_WATCH],
                           capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if p.returncode != 0:
        return None
    try:
        maps = json.loads(p.stdout).get("maps")
    except (ValueError, AttributeError):
        return None
    return maps if isinstance(maps, dict) else None


# A catalogue row becomes a line of data/mapdl.txt, which the menu tokenizes and
# whose name is a download path: every field is tested, not passed through.
CAT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def _tier(v):
    return str(v) if type(v) is int and 1 <= v <= 10 else "-"


VARIANT_OF = {}         # a second build's name, lowercased -> the roster's name it is a build of


def merge_catalogue(roster, cat):
    """Add the Pi's names the roster lacks, and a tier it has where the roster
    has none.  Returns how many names were added."""
    lc = {n.lower(): n for n in roster}
    rows = [c for c in cat.values()
            if isinstance(c, dict) and isinstance(c.get("name"), str)
            and CAT_NAME.fullmatch(c["name"]) and c.get("mode") in ("surf", "bhop")]
    added = 0
    for c in rows:
        src = str(c.get("src") or "")
        mt, kt = _tier(c.get("mtier")), _tier(c.get("ktier"))
        have = lc.get(c["name"].lower())
        s0 = roster[have][1] if have else ""
        letters = (("k" if "k" in src + s0 else "")
                   + ("m" if "m" in src + s0 or "b" in src else "")) or "-"
        if have is None:
            roster[c["name"]] = (c["mode"], letters, mt if mt != "-" else kt, mt, kt)
            lc[c["name"].lower()] = c["name"]
            added += 1
        else:
            mode, _, tier, m0, k0 = roster[have]
            m1, k1 = (m0 if m0 != "-" else mt), (k0 if k0 != "-" else kt)
            roster[have] = (mode, letters, tier if tier != "-" else (m1 if m1 != "-" else k1),
                            m1, k1)
    # KSF's build of a name is <name>_css where the Pi holds one (mapwatch
    # --variants): the plain row is then Momentum's build alone, so the menu's
    # CS:S list offers the file KSF's times were set on.
    for c in rows:
        of = c.get("of")
        if isinstance(of, str) and c["name"].lower() == of.lower() + "_css":
            plain = lc.get(of.lower())
            if plain is not None and "m" in roster[plain][1]:
                roster[plain] = (roster[plain][0], "m") + roster[plain][2:]
            if plain is not None:
                VARIANT_OF[c["name"].lower()] = plain
    return added


def push_beta(host):
    """Momentum's Beta maps (the game's submission cache: name, bspHash, CDN
    url) to the Pi as mapwatch's extra.tsv.  Returns the count, or None when
    this PC has no such cache or the Pi did not take the file -- the Pi then
    keeps the list it had, and the sweep goes on."""
    import glob
    import zlib
    try:
        import mapgrab
    except Exception as e:
        print("  no Beta list sent: mapgrab did not load (%s)" % e)
        return None

    def quick(cmd, cwd=None):           # a hang is a failure here, not the sweep's end
        try:
            return sh(cmd, timeout=120, cwd=cwd)
        except (subprocess.TimeoutExpired, OSError) as e:
            return 1, str(e)
    # Not mapgrab.read_cache(): it lowercases, and the name is the file's name.
    recs = {}
    for kind in ("approved", "submission"):
        hits = sorted(glob.glob(os.path.join(mapgrab.MOMENTUM, "_cache", kind + "_*.dat")))
        try:
            raw = open(hits[-1], "rb").read() if hits else b""
            got = json.loads(zlib.decompress(raw[12:])) if raw[:4] == b"MSML" else None
        except (OSError, ValueError, zlib.error):
            got = None
        recs[kind] = [r for r in got if isinstance(r, dict)] if isinstance(got, list) else None
    if not recs["approved"] or not recs["submission"]:
        return None
    done = {str(r.get("name")).lower() for r in recs["approved"]}
    rows = {}
    for r in recs["submission"]:
        cv = r.get("currentVersion")
        cv = cv if isinstance(cv, dict) else {}
        n = r.get("name")
        if (isinstance(n, str) and CAT_NAME.fullmatch(n)
                and n.lower().startswith(("surf_", "bhop_")) and n.lower() not in done
                and isinstance(cv.get("bspHash"), str) and isinstance(cv.get("downloadURL"), str)
                and not any(c.isspace() for c in cv["bspHash"] + cv["downloadURL"])):
            # P1093: the id lets the Pi ask the map's own reply for its zones and
            # whether this line's build is still current; `-` = no zones published.
            mid, zh = r.get("id"), cv.get("zoneHash")
            mid = str(mid) if type(mid) is int and 0 < mid < 10 ** 9 else None
            zh = zh.lower() if isinstance(zh, str) and re.fullmatch(r"[0-9a-fA-F]{40}", zh) else "-"
            rows.setdefault(n.lower(), (n, cv["bspHash"], cv["downloadURL"]) + ((mid, zh) if mid else ()))
    rows = sorted(rows.values())
    if not rows:
        return None
    local = os.path.join(DATA, "mapbeta.tsv")
    with open(local, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# written by tools/mapscan.py %s -- name sha1 url id zoneHash\n" % today())
        for row in rows:
            fh.write(" ".join(row) + "\n")
    rc, out = quick(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host,
                     "mkdir -p %s" % PI_WATCH])
    if rc == 0:
        rc, out = quick(["scp", "-q", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
                         "mapbeta.tsv", "%s:%s/extra.tsv.new" % (host, PI_WATCH)], cwd=DATA)
    if rc == 0:
        rc, out = quick(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host,
                         "mv -f %s/extra.tsv.new %s/extra.tsv" % (PI_WATCH, PI_WATCH)])
    if rc != 0:
        print("  could not send the Beta list to %s: %s" % (host, out.strip()[:300]))
        return None
    return len(rows)


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
    cat = pi_catalogue(args.host)
    if cat is None:
        print("  no mapwatch catalogue on the Pi: the roster alone decides what is listed")
    else:
        print("  the Pi's catalogue: %d names, %d the roster did not have"
              % (len(cat), merge_catalogue(roster, cat)))
    if args.go and not args.no_fetch:
        n = push_beta(args.host)
        print("  Beta list: %s" % ("not sent (no Momentum cache on this PC, or the Pi "
                                   "did not take it)" if n is None
                                   else "%d maps sent to the Pi" % n))

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
    print("  catalogued but not on the Pi: %d (the Pi's mapwatch fetches Momentum's and "
          "KSF's; tools/mapsync.py copies the rest from this PC)" % len(missing))

    if not args.go:
        print("\ndry run -- nothing written.  --go to write %s" % os.path.basename(DLFILE))
        return 0

    tmp = DLFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPDL 1\n")
        fh.write("# written by tools/mapscan.py -- do not edit\n")
        fh.write("# dl <name> <mode> <src> <tier> <kb> <first-iso> <new> "
                 "<mtier> <ktier> [<of>]\n")
        fh.write("# tier is mtier (Momentum's), else ktier (KSF's); 0 = none.\n")
        for name in servable:
            # name is the PI's spelling; the catalogue row is found by fold.
            mode, src, tier, mtier, ktier = roster[roster_lc[name.lower()]]
            d, _origin = seen.get(name, seen.get(roster_lc[name.lower()],
                                                 (stamp, "scan")))
            # The pair is APPENDED: the menu reads argv(1..7) after an n < 8 guard.
            # A tenth column on a second build: the map it is a build OF, in the
            # Pi's spelling (Patch 651; the menu folds the two into one row).
            of = VARIANT_OF.get(name.lower())
            of = next((n for n in servable if of and n.lower() == of.lower()), None)
            fh.write("dl %s %s %s %s %d %s %d %s %s%s\n" % (
                name, mode, src, tier if tier != "-" else "0",
                (inv[name] + 1023) // 1024, d,
                1 if name.lower() in newset else 0,
                mtier if mtier != "-" else "0", ktier if ktier != "-" else "0",
                " " + of if of else ""))
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
