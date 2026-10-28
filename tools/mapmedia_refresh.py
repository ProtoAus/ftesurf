#!/usr/bin/env python3
"""
mapmedia_refresh.py -- keep this PC's map media current: tiers, thumbnails and the
mount table (Patch 1098).  The six-hourly map scan (tools/mapscan_6h.ps1) runs it
after mapscan.py.

WHY.  data/mapmeta.txt (tiers), gfx/mapthumbs/ (thumbnails) and data/mapdeps.txt
(which maps mount TF2/CS:GO/Portal) were made by hand-run tools, so nothing kept
them current: on 28 Oct 14 maps had no tier or thumbnail and surf_hellenic drew
black for want of its TF2 line.  And the tools read Momentum's own _cache, which
refreshes only when its map browser is opened -- that day it lacked 3 of the
API's 1212 approved maps.

THE VIEW.  data/mapmedia/view/ has Momentum's layout, so the existing tools take
it as --momentum unchanged:
  _cache/approved_api.dat     the approved list from the API (anonymous), MSML
  _cache/submission_<n>.dat   Momentum's newest submission cache, copied: the
                              Beta list needs a sign-in, so this one still ages
  maps/zones/                 Momentum's own, copied.  NOT the Pi's site zones: a
                              zone file makes a row, and a row blocks the alias and
                              KSF passes -- the first run lost 78 alias and 13 KSF
                              tiers to 348 zone-only port rows that way.
A source that cannot be read keeps its previous copy; a first run with no copy
falls back to Momentum's own file.  A table that would lose more than
LOSS_LIMIT tiers, cells or rows is not installed (data/mapmedia/refused.txt).

STEPS: view -> mapfetch (missing small thumbnails into gfx/mapshots) -> mapmeta
(keeps atlas cells) -> mapdeps for BSPs new or changed since the last run ->
copy the three to the second install.  --atlas also packs new thumbnails into a
NEW atlas page: a release step, because a page a release has shipped must never
change.  --export DIR copies the media into a release worktree (its data/ and
gfx/mapthumbs/), which otherwise carries the previous release's forward.

Usage:
    python tools/mapmedia_refresh.py               # the six-hourly refresh
    python tools/mapmedia_refresh.py --atlas       # and bake new atlas cells (before a release)
    python tools/mapmedia_refresh.py --export DIR  # copy the media into a release worktree
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
import zlib

TOOLS = os.path.dirname(os.path.abspath(__file__))
SURFDIR = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

STEAM = r"C:\Program Files (x86)\Steam\steamapps\common"
MOMENTUM = os.path.join(STEAM, "Momentum Mod Playtest", "momentum")
SECOND = r"C:\FTEQuake\ftesurf"
API = "https://api.momentum-mod.org/v1/maps"
PAGE = 100
LOSS_LIMIT = 10                  # tiers/cells/rows a refresh may drop before it is refused
FULL_MAPDEPS_OVER = 200          # this many changed BSPs: one full scan beats N single-map ones
MEDIA = ("data/mapmeta.txt", "data/mapdeps.txt")


def say(s):
    print(s, flush=True)


def write_atomic(path, data):
    tmp = path + ".new-%d" % os.getpid()
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ------------------------------------------------------------------ the view --
def api_approved():
    """Every approved map, as the cache holds them.  Raises on any doubt."""
    out, skip, total = [], 0, None
    for _ in range(40):
        url = "%s?take=%d&skip=%d&expand=currentVersion,leaderboards,thumbnail,images,info,credits" % (API, PAGE, skip)
        req = urllib.request.Request(url, headers={"User-Agent": "FTESurf-mapmedia/1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            doc = json.loads(r.read(16 << 20))
        rows = doc.get("data")
        if not isinstance(rows, list) or not isinstance(doc.get("totalCount"), int):
            raise ValueError("an answer that is not a map list")
        total = doc["totalCount"]
        out += [m for m in rows if isinstance(m, dict) and isinstance(m.get("name"), str) and m.get("status") == 0]
        skip += PAGE
        if not rows or skip >= total:
            break
    if total is None or len(out) < total * 0.95:
        raise ValueError("%d of %s approved maps read" % (len(out), total))
    return out


def msml(records):
    raw = json.dumps(records, separators=(",", ":")).encode("utf-8")
    return b"MSML" + struct.pack("<II", len(raw), len(records)) + zlib.compress(raw, 6)


def build_view(view, online):
    cache = os.path.join(view, "_cache")
    os.makedirs(cache, exist_ok=True)
    dst = os.path.join(cache, "approved_api.dat")
    if online:
        try:
            rows = api_approved()
            write_atomic(dst, msml(rows))
            say("  approved: %d maps from the API" % len(rows))
        except Exception as e:                                   # noqa: BLE001
            say("  approved: API not read (%s); keeping %s" % (e, "the last copy" if os.path.exists(dst) else "Momentum's cache"))
    if not os.path.exists(dst):
        own = sorted(glob.glob(os.path.join(MOMENTUM, "_cache", "approved_*.dat")))
        if own:
            shutil.copy2(own[-1], dst)
            say("  approved: Momentum's %s" % os.path.basename(own[-1]))
    subs = sorted(glob.glob(os.path.join(MOMENTUM, "_cache", "submission_*.dat")))
    if subs:
        mine = os.path.join(cache, os.path.basename(subs[-1]))
        if not os.path.exists(mine) or os.path.getmtime(mine) < os.path.getmtime(subs[-1]):
            shutil.copy2(subs[-1], mine)
        for old in glob.glob(os.path.join(cache, "submission_*.dat")):
            if os.path.basename(old) != os.path.basename(mine):
                os.remove(old)
        say("  beta: Momentum's %s (%s)" % (os.path.basename(subs[-1]),
                                            time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(subs[-1])))))
    zdir = os.path.join(view, "maps", "zones")
    if os.path.isdir(zdir):
        shutil.rmtree(zdir)
    own = os.path.join(MOMENTUM, "maps", "zones")
    if os.path.isdir(own):
        shutil.copytree(own, zdir)
    say("  zones: Momentum's own, %d file(s)" % len(glob.glob(os.path.join(zdir, "*", "*.json"))))


# ------------------------------------------------------------------ mapmeta --
def table(path):
    """name -> (tier, page, cell) of every meta row, and "variant a b" lines as
    keys of their own; {} when there is no file."""
    out = {}
    if os.path.exists(path):
        for l in open(path, encoding="utf-8", errors="replace"):
            t = l.split()
            if len(t) > 7 and t[0] == "meta":
                out[t[1].lower()] = (t[2], t[6], t[7])
            elif len(t) == 3 and t[0] == "variant":
                out[" ".join(t).lower()] = ("-", "-", "-")
    return out


def losses(old, new):
    """What `new` drops of `old`: rows (variant pairs included), tiers and atlas
    cells, as name lists."""
    gone = [n for n in old if n not in new]
    tiers = [n for n, v in old.items() if v[0] != "-" and new.get(n, ("-",))[0] == "-"]
    cells = [n for n, v in old.items() if v[1] != "-" and new.get(n, ("", "-"))[1] == "-"]
    return gone, tiers, cells


def stamp(path, gamedir):
    """`# stamp <unix>` and `# atlas <page> <bytes>` after the header, replacing old
    ones: the menu prefers the newer of two tables and trusts a page's cells only at
    the size listed (P1099)."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    lines = [l for l in lines if not l.startswith(("# stamp ", "# atlas "))]
    add = ["# stamp %d" % int(time.time())]
    for p in sorted(glob.glob(os.path.join(gamedir, "gfx", "mapthumbs", "atlas*.png"))):
        n = os.path.basename(p)[5:-4]
        if n.isdigit():
            add.append("# atlas %s %d" % (n, os.path.getsize(p)))
    at = 1 if lines and lines[0].startswith("FTESURF-MAPMETA") else 0
    write_atomic(path, ("\n".join(lines[:at] + add + lines[at:]) + "\n").encode("utf-8"))


# ------------------------------------------------------------------ mapdeps --
def library():
    """name -> path, the BSPs mapdeps.py scans, first mount winning as it does."""
    import mapdeps
    out = {}
    for _n, root in mapdeps.MOUNTED:
        d = os.path.join(root, "maps")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith(".bsp"):
                    out.setdefault(fn[:-4], os.path.join(d, fn))
    return out


def refresh_mapdeps(gamedir, state_path):
    out = os.path.join(gamedir, "data", "mapdeps.txt")
    try:
        prev = json.load(open(state_path, encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    lib = library()
    now = {}
    for name, p in lib.items():
        st = os.stat(p)
        now[name] = [st.st_size, st.st_mtime_ns]
    changed = sorted(n for n in now if prev.get(n) != now[n])
    py = [sys.executable, "-I", os.path.join(TOOLS, "mapdeps.py")]
    if not prev or len(changed) > FULL_MAPDEPS_OVER or not os.path.exists(out):
        say("  mapdeps: full scan (%d of %d BSPs new or changed)" % (len(changed), len(now)))
        if subprocess.run(py + ["--output", out], capture_output=True, text=True).returncode != 0:
            raise SystemExit("mapdeps full scan failed")
    else:
        for name in changed:
            r = subprocess.run(py + ["--map", name, "--update-map", "--output", out,
                                     "--expected-sha256", sha256(out)], capture_output=True, text=True)
            line = [l for l in r.stdout.splitlines() if "dep lines:" in l]
            say("  mapdeps: %s -> %s" % (name, line[0].split(":", 1)[1].strip() if line else "rc %d" % r.returncode))
            if r.returncode != 0:
                now[name] = prev.get(name)          # asked again next run
        if not changed:
            say("  mapdeps: no BSP new or changed")
    write_atomic(state_path, json.dumps({k: v for k, v in now.items() if v}, sort_keys=True).encode())


# --------------------------------------------------------------------- copies --
def media_files(gamedir):
    files = list(MEDIA)
    files += ["gfx/mapthumbs/" + os.path.basename(p)
              for p in sorted(glob.glob(os.path.join(gamedir, "gfx", "mapthumbs", "atlas*.png")))]
    return files


def copy_media(gamedir, dest, label):
    n = 0
    for rel in media_files(gamedir):
        src, dst = os.path.join(gamedir, rel), os.path.join(dest, rel)
        if not os.path.exists(src):
            continue
        if os.path.exists(dst) and sha256(dst) == sha256(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".new-%d" % os.getpid()
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
        n += 1
    say("  %s: %d file(s) updated" % (label, n))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--gamedir", default=os.path.join(SURFDIR, "ftesurf"))
    ap.add_argument("--offline", action="store_true", help="no API, no Pi, no CDN")
    ap.add_argument("--atlas", action="store_true", help="also pack new thumbnails into a new atlas page")
    ap.add_argument("--export", metavar="DIR", help="copy the media into DIR/ftesurf/ (a release worktree)")
    ap.add_argument("--no-second", action="store_true", help="leave %s alone" % SECOND)
    a = ap.parse_args()
    g = os.path.abspath(a.gamedir)
    state = os.path.join(g, "data", "mapmedia")
    view = os.path.join(state, "view")
    os.makedirs(state, exist_ok=True)
    t0 = time.time()
    say("mapmedia refresh %s" % time.strftime("%Y-%m-%dT%H:%M:%S"))

    build_view(view, not a.offline)

    if not a.offline:
        import mapfetch
        mapfetch.run(view, ["small"], 0, False, os.path.join(g, "gfx", "mapshots"))

    meta = os.path.join(g, "data", "mapmeta.txt")
    tmp = meta + ".new-%d" % os.getpid()
    if os.path.exists(meta):
        shutil.copy2(meta, tmp)     # mapmeta.py carries atlas cells forward from its --out file
    r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "mapmeta.py"), "--momentum", view,
                        "--mounted", MOMENTUM, "--gamedir", g, "--out", tmp], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tmp):
        raise SystemExit("mapmeta failed: %s" % (r.stderr or r.stdout)[-400:])
    old, new = table(meta), table(tmp)
    gone, tiers, cells = losses(old, new)
    say("  mapmeta: %d rows and variant pairs (was %d): %d added, %d gone, %d tiers lost, %d cells lost"
        % (len(new), len(old), len(set(new) - set(old)), len(gone), len(tiers), len(cells)))
    refused = max(len(gone), len(tiers), len(cells)) > LOSS_LIMIT
    if refused:
        os.replace(tmp, os.path.join(state, "refused.txt"))
        for what, names in (("gone", gone), ("tier lost", tiers), ("cell lost", cells)):
            if names:
                say("    %s: %s" % (what, " ".join(sorted(names)[:8])))
        say("  mapmeta: NOT installed -- more than %d lost; candidate in data/mapmedia/refused.txt" % LOSS_LIMIT)
    else:
        stamp(tmp, g)
        os.replace(tmp, meta)

    refresh_mapdeps(g, os.path.join(state, "mapdeps_state.json"))

    if a.atlas and not refused:
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "mapthumbs.py"), "--momentum", view,
                            "--gamedir", g, "--fill-missing"], capture_output=True, text=True)
        say("  atlas: " + (r.stdout.strip().splitlines() or ["?"])[-1])
        if r.returncode != 0:
            raise SystemExit("mapthumbs failed")
        stamp(meta, g)              # a new page's size

    if not a.no_second and os.path.isdir(SECOND) and os.path.abspath(SECOND) != g:
        copy_media(g, SECOND, SECOND)
    if a.export:
        copy_media(g, os.path.join(os.path.abspath(a.export), "ftesurf"), "export " + a.export)
    say("done in %.0fs" % (time.time() - t0))
    return 2 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
