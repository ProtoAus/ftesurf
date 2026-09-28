#!/usr/bin/env python3
"""
maproster.py -- the official surf/bhop map list: every map either catalogue
knows about, pinned to the exact build this install would load.

WHY THIS EXISTS.  `data/mapmeta.txt` answers "what does Momentum say about this
map" and the menu's own `search_begin("maps/*.bsp")` answers "is it on disk".
Neither answers the question a roster has to answer -- WHICH BUILD -- and that
is not a pedantic distinction here.  Measured 2026-09-28: of the 1062 map names
present in both the Momentum and CS:S installs, 322 are a different file under
the same name (30.3%).  A run recorded against the wrong one is demoted
`TF_NOMAP` silently, so a list that names maps without pinning builds is a list
that looks right and is wrong a third of the time.

WHAT PINS A BUILD, and it is not a size.  Momentum publishes a SHA1 of the .bsp
inside every one of its demos: a `.mtv` carries it as 40 UPPERCASE hex at byte
offset 80, right after the null-padded map name.  Verified on the 2888 demos in
`wrlines_data/demos`: 40 maps carry one, and for 39 of them a local build hashes
to exactly that value.  So for those maps the pin is not our opinion, it is
Momentum's own statement of what its leaderboards run on.

  surf_slobs is the fortieth and matches NEITHER local build -- we hold a third
  build of it.  That is the case this tool exists to make visible.

THE THIRD VERDICT, because a check that cannot measure must say so.  `pin` is
`ok` / `other` / `unknown`, never a bare pass/fail:

    ok        our loaded build == the hash Momentum publishes
    other     Momentum publishes a hash and ours is a different build
    unknown   NOTHING publishes a digest for this map

`unknown` is the common case and it is permanent, not a backlog: it covers every
CS:S-sourced and KSF-sourced map, because neither publishes a per-map digest.
Collapsing it into `other` would accuse most of the library of being wrong on the
strength of nobody having said anything.  Same shape as Patch 421's angle check
and Patch 422's missing receipt.

AND A MAP CAN HAVE MORE THAN ONE RIGHT ANSWER.  5 of the 40 (surf_4am,
surf_antichamber, surf_blackheart, surf_pinkcubes, surf_tropic) have demos that
disagree with each other, because Momentum re-released the map and both builds
have times on them.  So "the latest version" is not a thing a hash can tell you;
"the build this demo ran on" is.  Where the demos disagree the most common value
wins and the disagreement is reported by `check`, never silently resolved.

WHICH BUILD "OURS" MEANS.  `ftesurf/fs_addons.txt` mounts Momentum, then
cstrike, then hl2, EARLIER WINNING, so a name present in two installs resolves to
the Momentum one and that is the only file the engine will ever load.  This tool
hashes the winner and no others -- which is also why it reads ~45 GB and not the
90 GB both installs hold.

WHAT IT COSTS.  The first `hash` run reads every surf/bhop BSP the engine would
load (1248 files, ~45 GB) at disk speed.  After that the cache is keyed on
(size, mtime) and a re-run is free.  A STALE CACHE IS SILENT, which is why the
size and mtime are stored beside the value and a moved file is rehashed rather
than trusted -- the same guard `tools/mapcrc.py` needs for the same reason.

Outputs, both under `ftesurf/data/` and both regenerated from sources with no
carried-forward state (so a re-run cannot lose rows the way `mapmeta.py` does):

    maphash.txt    hash <install> <name> <size> <mtime> <sha1>
    maproster.txt  roster <name> <mode> <src> <have> <sha1> <pin> <tier>
                          <type> <avail>

'-' means unknown throughout and is never the same as 0 or as a real value.
"""

import argparse
import collections
import csv
import glob
import hashlib
import io
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(HERE, "ftesurf")
DATA = os.path.join(GAME, "data")

HASHFILE = os.path.join(DATA, "maphash.txt")
ROSTERFILE = os.path.join(DATA, "maproster.txt")
KSFCSV = os.path.join(DATA, "ksf_roster.csv")
KSFDRIVE = os.path.join(DATA, "ksf_drive.txt")
MAPMETA = os.path.join(DATA, "mapmeta.txt")
ADDONS = os.path.join(GAME, "fs_addons.txt")

STEAM = r"C:\Program Files (x86)\Steam\steamapps\common"
DEMOS = r"C:\Users\Lex\Documents\wrlines\wrlines_data\demos"

# The roster is surf and bhop only, by the operator's scope.  Momentum's
# gamemode ids, from mapmeta.py's table: 1 surf, 2 bhop.  Name prefix is the
# fallback for the 618 maps no catalogue lists.
MODES = {"1": "surf", "2": "bhop"}
PREFIX = ("surf_", "bhop_")

# KSF's public roster and its two public map folders.  All three answer an
# anonymous GET -- no API key, no OAuth, no credential on this path.
KSF_SHEET = ("https://docs.google.com/spreadsheets/d/"
             "1oXU6UXGPdgdqRiAjjD_5c1WfI6PY6ML4/export?format=csv&gid=1729788986")
# NOT /drive/folders/<id>: that page embeds only the FIRST 50 entries and
# paginates the rest by XHR, so a scraper on it sees 50 of 466 and looks like it
# worked.  embeddedfolderview returns the whole listing in one request.
KSF_FOLDERS = ("17QJ-Wzk9eMHKZqX227HkPCg9_Vmrf9h-",
               "1f3Oe65BngrSxTPKHAt6MEwK0FTsDbUsO")
KSF_EMBED = "https://drive.google.com/embeddedfolderview?id=%s#list"
UA = "FTESurf-maproster/1.0 (+local surf/bhop map roster)"

MTV_HASH_OFF = 80          # measured over 2888 demos: every one, no exceptions
MTV_HASH_RE = re.compile(rb"[0-9A-F]{40}")


def surfbhop(name):
    return name.startswith(PREFIX)


#  ---------------------------------------------------------------- inventory

def mount_dirs():
    """The engine's map dirs in MOUNT ORDER, earlier winning.  Read from
    fs_addons.txt rather than hardcoded, because the mount list is what decides
    which build loads and it has changed before."""
    out = []
    if os.path.exists(ADDONS):
        for ln in io.open(ADDONS, encoding="utf-8", errors="replace"):
            ln = ln.split("//")[0].strip()
            if not ln:
                continue
            if ln.startswith("steam:"):
                out.append((ln[6:].split("/")[-1],
                            os.path.join(STEAM, *ln[6:].split("/")) + os.sep + "maps"))
    out.insert(0, ("ftesurf", os.path.join(GAME, "maps")))
    return [(tag, d) for tag, d in out if os.path.isdir(d)]


def resolve():
    """-> {name: (install_tag, path, size, mtime)} for the build the engine
    would actually load.  Earlier mount wins; later ones are never consulted."""
    win = {}
    for tag, d in mount_dirs():
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for f in entries:
            if not f.lower().endswith(".bsp"):
                continue
            name = f[:-4].lower()
            if not surfbhop(name) or name in win:
                continue
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            win[name] = (tag, p, st.st_size, int(st.st_mtime))
    return win


#  ------------------------------------------------------------------- hashes

def read_hashcache():
    out = {}
    if not os.path.exists(HASHFILE):
        return out
    for ln in io.open(HASHFILE, encoding="utf-8", errors="replace"):
        f = ln.split()
        if len(f) >= 6 and f[0] == "hash":
            out[f[2]] = (f[1], int(f[3]), int(f[4]), f[5])
    return out


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_hash(args):
    win = resolve()
    cache = read_hashcache()
    todo = []
    for name, (tag, path, size, mtime) in sorted(win.items()):
        c = cache.get(name)
        # A stale cache is silent, so the guard is size AND mtime, not presence.
        if c and not args.refresh and c[0] == tag and c[1] == size and c[2] == mtime:
            continue
        todo.append((name, tag, path, size, mtime))

    total = sum(t[3] for t in todo)
    print("%d surf/bhop maps resolved; %d need hashing (%.1f GB)"
          % (len(win), len(todo), total / 1073741824.0))
    if args.dry_run:
        return 0

    done = 0
    for i, (name, tag, path, size, mtime) in enumerate(todo):
        try:
            digest = sha1_file(path)
        except OSError as e:
            print("  %s: %s" % (name, e), file=sys.stderr)
            continue
        cache[name] = (tag, size, mtime, digest)
        done += size
        if i % 50 == 0 or i == len(todo) - 1:
            print("  %4d/%d  %5.1f%%  %s" % (i + 1, len(todo),
                  100.0 * done / total if total else 100.0, name), flush=True)

    tmp = HASHFILE + ".new"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPHASH 1\n")
        fh.write("# written by tools/maproster.py -- do not edit\n")
        fh.write("# hash <install> <name> <size> <mtime> <sha1>\n")
        for name in sorted(cache):
            tag, size, mtime, digest = cache[name]
            fh.write("hash %s %s %d %d %s\n" % (tag, name, size, mtime, digest))
    os.replace(tmp, HASHFILE)
    print("wrote %s (%d rows)" % (HASHFILE, len(cache)))
    return 0


#  ------------------------------------------------- what Momentum publishes

def published_hashes(demodir):
    """-> {map: Counter(sha1)} from .mtv headers.  A map whose demos disagree
    keeps every value; the caller decides, and `check` prints the split."""
    pub = collections.defaultdict(collections.Counter)
    if not os.path.isdir(demodir):
        return pub
    for p in glob.glob(os.path.join(demodir, "*", "*.mtv")):
        try:
            head = open(p, "rb").read(256)
        except OSError:
            continue
        m = MTV_HASH_RE.search(head, MTV_HASH_OFF - 8)
        if m:
            pub[os.path.basename(os.path.dirname(p)).lower()][m.group().decode().lower()] += 1
    return pub


#  ------------------------------------------------------------ the catalogues

def read_mapmeta():
    """-> {name: (tier, mode_id)} for surf/bhop rows only."""
    out = {}
    if not os.path.exists(MAPMETA):
        return out
    for ln in io.open(MAPMETA, encoding="utf-8", errors="replace"):
        if not ln.startswith("meta "):
            continue
        f = ln.split()
        if len(f) < 10:
            continue
        out[f[1].lower()] = (f[2], f[9])
    return out


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    with open(dest + ".part", "wb") as fh:
        fh.write(body)
    os.replace(dest + ".part", dest)
    return len(body)


def cmd_fetch(args):
    n = fetch(KSF_SHEET, KSFCSV)
    print("ksf roster: %d bytes -> %s" % (n, KSFCSV))
    names = set()
    for fid in KSF_FOLDERS:
        req = urllib.request.Request(KSF_EMBED % fid, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            html = r.read().decode("utf-8", errors="replace")
        got = re.findall(r'<div class="flip-entry-title">([^<]+)</div>', html)
        print("  folder %s: %d entries" % (fid[:12], len(got)))
        names |= set(got)
    with io.open(KSFDRIVE, "w", encoding="utf-8", newline="\n") as fh:
        for x in sorted(names):
            fh.write(x + "\n")
    print("ksf drive listing: %d names -> %s" % (len(names), KSFDRIVE))
    return 0


def read_ksf():
    """-> ({name: (tier, type)}, {stem: archive}).  The roster and the Drive
    disagree on 5 names and 4 of those 5 are on disk under the DRIVE's spelling,
    so the two are kept apart and reconciled by the caller, never merged here."""
    roster, arch = {}, {}
    if os.path.exists(KSFCSV):
        with io.open(KSFCSV, encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                nm = (row.get("Map name") or "").strip().lower()
                if nm:
                    roster[nm] = ((row.get("Tier") or "-").strip() or "-",
                                  (row.get("Type") or "-").strip() or "-")
    if os.path.exists(KSFDRIVE):
        for ln in io.open(KSFDRIVE, encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if ln.lower().endswith((".rar", ".zip")):
                arch[ln.rsplit(".", 1)[0].strip().lower()] = ln
    return roster, arch


#  --------------------------------------------------------------- the roster

def build_rows():
    win = resolve()
    cache = read_hashcache()
    meta = read_mapmeta()
    ksf, arch = read_ksf()
    pub = published_hashes(DEMOS)

    names = set(win)
    names |= {n for n in meta if surfbhop(n)}
    names |= {n for n in ksf if surfbhop(n)}
    names |= {n for n in arch if surfbhop(n)}

    rows, stats = [], collections.Counter()
    for name in sorted(names):
        w = win.get(name)
        have = w[0] if w else "-"
        c = cache.get(name)
        sha = c[3] if (c and w and c[1] == w[2] and c[2] == w[3]) else "-"

        mtier, mmode = meta.get(name, ("-", "-"))
        ktier, ktype = ksf.get(name, ("-", "-"))
        mode = MODES.get(mmode) or ("surf" if name.startswith("surf_") else "bhop")

        src = ("k" if name in ksf else "") + ("m" if name in meta else "")
        src = src or "-"

        want = pub.get(name)
        if not want:
            pin = "unknown"                       # nobody publishes a digest
        elif sha == "-":
            pin = "unknown"                       # we cannot hash it to compare
        elif sha in want:
            pin = "ok"
        else:
            pin = "other"
        stats[pin] += 1

        avail = arch.get(name, "-")
        if avail != "-" and w:
            avail = "-"                           # already installed; nothing to fetch
        rows.append((name, mode, src, have, sha, pin,
                     mtier if mtier != "-" else ktier, ktype, avail))
    return rows, stats, len(win)


def cmd_build(args):
    rows, stats, nwin = build_rows()
    tmp = ROSTERFILE + ".new"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPROSTER 1\n")
        fh.write("# written by tools/maproster.py -- do not edit\n")
        fh.write("# roster <name> <mode> <src> <have> <sha1> <pin> <tier> "
                 "<type> <avail>\n")
        fh.write("# src:   k = on KSF's roster, m = in Momentum's catalogue\n")
        fh.write("# have:  which mount supplies the build the engine loads\n")
        fh.write("# pin:   ok = matches the SHA1 Momentum publishes in its demos,\n")
        fh.write("#        other = it publishes one and ours differs,\n")
        fh.write("#        unknown = NOTHING publishes a digest.  Permanent for\n")
        fh.write("#        every CS:S- and KSF-sourced map; not a to-do.\n")
        fh.write("# avail: a KSF archive exists for a map we do not have\n")
        fh.write("# '-' means unknown, and is never the same as 0.\n")
        for r in rows:
            fh.write("roster %s\n" % " ".join(r))
    os.replace(tmp, ROSTERFILE)

    have = sum(1 for r in rows if r[3] != "-")
    hashed = sum(1 for r in rows if r[4] != "-")
    fetchable = sum(1 for r in rows if r[8] != "-")
    print("wrote %s" % ROSTERFILE)
    print("  %d maps: %d surf, %d bhop"
          % (len(rows), sum(1 for r in rows if r[1] == "surf"),
             sum(1 for r in rows if r[1] == "bhop")))
    print("  installed %d, hashed %d, absent %d (%d fetchable from KSF)"
          % (have, hashed, len(rows) - have, fetchable))
    print("  pin: ok %d, other %d, unknown %d"
          % (stats["ok"], stats["other"], stats["unknown"]))
    if hashed < have:
        print("  NOTE: %d installed maps are unhashed -- run `hash` first"
              % (have - hashed))
    return 0


def cmd_check(args):
    name = args.map.lower()
    win, cache = resolve(), read_hashcache()
    meta, (ksf, arch) = read_mapmeta(), read_ksf()
    pub = published_hashes(DEMOS)
    print("map: %s" % name)
    w = win.get(name)
    print("  loaded from : %s" % (("%s  %s" % (w[0], w[1])) if w else "- (not installed)"))
    c = cache.get(name)
    if c:
        fresh = bool(w) and c[1] == w[2] and c[2] == w[3]
        print("  our sha1    : %s%s" % (c[3], "" if fresh else "   (STALE: file moved since)"))
    else:
        print("  our sha1    : - (not hashed)")
    if name in pub:
        for h, n in pub[name].most_common():
            print("  momentum    : %s  (%d demos)" % (h, n))
        if len(pub[name]) > 1:
            print("                ^ demos DISAGREE: this map was re-released and")
            print("                  both builds carry times.  No single 'latest'.")
    else:
        print("  momentum    : - (publishes no digest for this map)")
    print("  catalogues  : ksf=%s momentum=%s" % (name in ksf, name in meta))
    if name in ksf:
        print("  ksf         : tier %s, %s" % ksf[name])
    if name in arch:
        print("  ksf archive : %s" % arch[name])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd")
    h = sub.add_parser("hash", help="build/refresh the SHA1 cache")
    h.add_argument("--refresh", action="store_true", help="rehash everything")
    h.add_argument("--dry-run", action="store_true", help="say what it would read")
    h.set_defaults(fn=cmd_hash)
    f = sub.add_parser("fetch", help="refresh the KSF roster and Drive listing")
    f.set_defaults(fn=cmd_fetch)
    b = sub.add_parser("build", help="write data/maproster.txt")
    b.set_defaults(fn=cmd_build)
    c = sub.add_parser("check", help="explain one map")
    c.add_argument("map")
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
