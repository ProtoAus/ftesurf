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
  _cache/approved_api.dat     the approved list from the API (anonymous), MSML;
                              Momentum's own when that is newer (the API failed)
  _cache/submission_<n>.dat   Momentum's newest submission cache, copied: the
                              Beta list needs a sign-in, so this one still ages
  maps/zones/                 Momentum's own, copied.  NOT the Pi's site zones: a
                              zone file makes a row, and a row blocks the alias and
                              KSF passes -- the first run lost 78 alias and 13 KSF
                              tiers to 348 zone-only port rows that way.

THE GATE.  Both tables are built in a temp file and installed only if they lose at
most max(LOSS_FLOOR, LOSS_FRACTION of the old) rows, variant pairs, tiers, atlas
cells or dep lines; else the candidate is kept in data/mapmedia/refused-<table>
and the run exits 2, every run, until someone looks and runs --accept.  Each table
carries `# stamp YYYYMMDDHHMMSS` (UTC), changed only when its content does: the
menu and fs_automount prefer the newer of a shipped and a fetched copy (P1099).

STEPS: view -> mapfetch (missing small thumbnails into gfx/mapshots) -> mapmeta
(keeps atlas cells) -> mapdeps for BSPs new or changed since the last run, or all
of them when an add-on game changed -> copy to the second install.  --atlas also
packs new thumbnails into a NEW atlas page: a release step, because a page a
release has shipped must never change.  --export DIR copies the media into a
release worktree, which otherwise carries the previous release's forward.

Exit: 0 done, 2 a table not installed (refused, or a game mapdeps reads is missing
here), 3 another refresh holds the lock, 4 no table to refresh (missing, or under
MIN_ROWS rows: build it by hand first with tools/mapmeta.py, tools/mapthumbs.py).

Usage:
    python tools/mapmedia_refresh.py               # the six-hourly refresh
    python tools/mapmedia_refresh.py --accept      # install what the gate refused
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
MIN_APPROVED = 500               # an approved list shorter than this is not one (1212 on 28 Oct)
MIN_ROWS = 500                   # a live mapmeta.txt shorter than this is no table to gate against (2811)
LOSS_FLOOR = 25
LOSS_FRACTION = 0.02             # the first run's bad table lost 3.4% of tiers and 2.8% of cells
LOCK_STALE = 3 * 3600            # the task's own limit is 2 h
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


def newest(pattern):
    """The most recently written match, or None (names do not sort by age)."""
    found = glob.glob(pattern)
    return max(found, key=os.path.getmtime) if found else None


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
    if total is None or total < MIN_APPROVED or len(out) < total * 0.95:
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
            say("  approved: API NOT READ (%s)" % e)
    own = newest(os.path.join(MOMENTUM, "_cache", "approved_*.dat"))
    if own and (not os.path.exists(dst) or os.path.getmtime(own) > os.path.getmtime(dst)):
        shutil.copy2(own, dst)
        say("  approved: Momentum's %s, newer than the last API copy" % os.path.basename(own))
    sub = newest(os.path.join(MOMENTUM, "_cache", "submission_*.dat"))
    if sub:
        mine = os.path.join(cache, os.path.basename(sub))
        if not os.path.exists(mine) or os.path.getmtime(mine) < os.path.getmtime(sub):
            shutil.copy2(sub, mine)
        for old in glob.glob(os.path.join(cache, "submission_*.dat")):
            if os.path.basename(old) != os.path.basename(mine):
                os.remove(old)
        say("  beta: Momentum's %s (%s)" % (os.path.basename(sub),
                                            time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(sub)))))
    zdir = os.path.join(view, "maps", "zones")
    if os.path.isdir(zdir):
        shutil.rmtree(zdir)
    zown = os.path.join(MOMENTUM, "maps", "zones")
    if os.path.isdir(zown):
        shutil.copytree(zown, zdir)
    say("  zones: Momentum's own, %d file(s)" % len(glob.glob(os.path.join(zdir, "*", "*.json"))))


# ------------------------------------------------------------- the gate --
KINDS = ("meta", "variant", "dep")


def keys(path):
    """A table's entries for the gate: (kind, name) -> (tier, page, cell), where a
    variant or dep line is its own name and has neither tier nor cell."""
    out = {}
    if os.path.exists(path):
        for l in open(path, encoding="utf-8", errors="replace"):
            t = l.split()
            if len(t) > 7 and t[0] == "meta":
                out[("meta", t[1].lower())] = (t[2], t[6], t[7])
            elif (len(t) == 3 and t[0] == "variant") or (len(t) >= 3 and t[0] == "dep"):
                out[(t[0], " ".join(t[1:]).lower())] = ("-", "-", "-")
    return out


def losses(old, new):
    """What `new` drops of `old`: {kind: names gone}, tiers and atlas cells lost."""
    gone = {k: [n for (kk, n) in old if kk == k and (kk, n) not in new] for k in KINDS}
    tiers = [n for (k, n), v in old.items() if v[0] != "-" and new.get((k, n), ("-",))[0] == "-"]
    cells = [n for (k, n), v in old.items() if v[1] != "-" and new.get((k, n), ("", "-"))[1] == "-"]
    return gone, tiers, cells


def limit(n):
    return max(LOSS_FLOOR, int(n * LOSS_FRACTION))


def gate(label, live, cand, state, accept):
    """True to install `cand` over `live`.  A refusal keeps the candidate."""
    old, new = keys(live), keys(cand)
    gone, tiers, cells = losses(old, new)
    ngone = sum(len(v) for v in gone.values())
    say("  %s: %d entries (was %d): %d added, %d gone, %d tiers lost, %d cells lost"
        % (label, len(new), len(old), len(set(new) - set(old)), ngone, len(tiers), len(cells)))
    over = (any(len(gone[k]) > limit(sum(1 for kk, _ in old if kk == k)) for k in KINDS)
            or len(tiers) > limit(sum(1 for v in old.values() if v[0] != "-"))
            or len(cells) > limit(sum(1 for v in old.values() if v[1] != "-")))
    refused = os.path.join(state, "refused-" + os.path.basename(live))
    if not over or accept:
        if over:
            say("  %s: --accept: installed despite the losses" % label)
        if os.path.exists(refused):
            os.remove(refused)
        return True
    for what, names in [(k + " gone", gone[k]) for k in KINDS] + [("tier lost", tiers), ("cell lost", cells)]:
        if names:
            say("    %d %s: %s%s" % (len(names), what, " ".join(sorted(names)[:8]), " ..." if len(names) > 8 else ""))
    shutil.copy2(cand, refused)
    say("  %s: NOT INSTALLED, it loses too much (kept as %s). If those losses are right,"
        " run tools/mapmedia_refresh.py --accept" % (label, refused))
    return False


def read_stamped(path):
    """(stamp, lines without stamp/atlas lines); ("", []) for no file."""
    if not os.path.exists(path):
        return "", []
    st, body = "", []
    for l in open(path, encoding="utf-8", errors="replace").read().splitlines():
        if l.startswith("# stamp "):
            st = l[8:].strip()
        elif not l.startswith("# atlas "):
            body.append(l)
    return st, body


def stamp(path, gamedir, prev, atlas):
    """`# stamp` after the header line, kept from `prev` (read_stamped's answer for
    the table it replaces) when the content is the same, and for mapmeta
    `# atlas <page> <bytes>`: the menu trusts a page's cells only at the size
    listed (P1099)."""
    _, body = read_stamped(path)
    pst, pbody = prev
    # Order-blind: mapthumbs puts the variant lines above the rows and mapmeta.py below.
    st = pst if sorted(pbody) == sorted(body) and len(pst) == 14 else time.strftime("%Y%m%d%H%M%S", time.gmtime())
    add = ["# stamp " + st]
    if atlas:
        for p in sorted(glob.glob(os.path.join(gamedir, "gfx", "mapthumbs", "atlas*.png"))):
            n = os.path.basename(p)[5:-4]
            if n.isdigit():
                add.append("# atlas %s %d" % (n, os.path.getsize(p)))
    at = 1 if body and body[0].startswith("FTESURF-") else 0
    write_atomic(path, ("\n".join(body[:at] + add + body[at:]) + "\n").encode("utf-8"))


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


def addons():
    """Which content mapdeps.py resolves against, by pack: a game installed, removed
    or updated changes what every map needs, not only the maps that changed."""
    import mapdeps
    out = []
    for root in [r for _n, r in mapdeps.MOUNTED] + [a[1] for a in mapdeps.ADDONS]:
        packs = sorted([os.path.basename(p), os.path.getsize(p)]     # lists: it is compared after a JSON round trip
                       for p in glob.glob(os.path.join(root or "", "*_dir.vpk")))
        out.append([root, os.path.isdir(root or ""), packs])
    return out


def build_mapdeps(live, cand, state_path):
    """Writes `cand`; returns the state to keep once it is installed."""
    try:
        prev = json.load(open(state_path, encoding="utf-8"))
        if prev.get("v") != 2:
            prev = {}
    except (OSError, ValueError, AttributeError):
        prev = {}
    lib = library()
    now = {}
    for name, p in lib.items():
        st = os.stat(p)
        now[name] = [st.st_size, st.st_mtime_ns]
    pmaps = prev.get("maps", {})
    changed = sorted(n for n in now if pmaps.get(n) != now[n])
    fp = addons()
    # A game missing on this PC is not maps that stopped needing it: a rescan would
    # drop every line for it (Portal's 20 are under the gate's floor).  Review 2.
    import mapdeps
    need = [(r, False) for _n, r in mapdeps.MOUNTED] + [(a[1], True) for a in mapdeps.ADDONS]
    gaps = [str(r) for (r, packs_needed), (_r, isdir, packs) in zip(need, fp) if not isdir or (packs_needed and not packs)]
    if gaps:
        say("  mapdeps: NOT REBUILT -- not installed here: %s" % "; ".join(gaps))
        return None
    py = [sys.executable, "-I", os.path.join(TOOLS, "mapdeps.py")]
    if (not prev or prev.get("addons") != fp or len(changed) > FULL_MAPDEPS_OVER
            or not os.path.exists(live)):
        why = "add-on content changed" if prev and prev.get("addons") != fp else "%d of %d BSPs new or changed" % (len(changed), len(now))
        say("  mapdeps: full scan (%s)" % why)
        r = subprocess.run(py + ["--output", cand], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(cand):
            raise SystemExit("mapdeps full scan failed: %s" % (r.stderr or r.stdout)[-400:])
    else:
        shutil.copy2(live, cand)
        for name in changed:
            r = subprocess.run(py + ["--map", name, "--update-map", "--output", cand,
                                     "--expected-sha256", sha256(cand)], capture_output=True, text=True)
            line = [l for l in r.stdout.splitlines() if "dep lines:" in l]
            say("  mapdeps: %s -> %s" % (name, line[0].split(":", 1)[1].strip() if line else "rc %d" % r.returncode))
            if r.returncode != 0:
                now[name] = pmaps.get(name)          # asked again next run
        if not changed:
            say("  mapdeps: no BSP new or changed")
    return {"v": 2, "addons": fp, "maps": {k: v for k, v in now.items() if v}}


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


def take_lock(path):
    """Our token, or None when a live refresh holds it; one older than LOCK_STALE is
    taken over."""
    token = "%d %s\n" % (os.getpid(), time.strftime("%Y-%m-%dT%H:%M:%S"))
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, token.encode())
            os.close(fd)
            return token
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) < LOCK_STALE:
                    return None
                os.remove(path)
            except FileNotFoundError:
                pass                # its holder finished between the two calls: try again
    return None


def refresh(a, g, state, view):
    rc = 0
    meta = os.path.join(g, "data", "mapmeta.txt")
    rows = sum(1 for (k, _n) in keys(meta) if k == "meta")
    if rows < MIN_ROWS:
        say("  mapmeta: %s has %d rows -- build it by hand first (tools/mapmeta.py, then "
            "tools/mapthumbs.py); a table from nothing loses every atlas cell" % (meta, rows))
        return 4

    build_view(view, not a.offline)
    if not a.offline:
        import mapfetch
        mapfetch.run(view, ["small"], 0, False, os.path.join(g, "gfx", "mapshots"))

    tmp = meta + ".new-%d" % os.getpid()
    try:
        shutil.copy2(meta, tmp)     # mapmeta.py carries atlas cells and tied modes forward from --out
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "mapmeta.py"), "--momentum", view,
                            "--mounted", MOMENTUM, "--gamedir", g, "--out", tmp], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("mapmeta failed: %s" % (r.stderr or r.stdout)[-400:])
        meta_ok = gate("mapmeta", meta, tmp, state, a.accept)
        if meta_ok:
            stamp(tmp, g, read_stamped(meta), True)
            os.replace(tmp, meta)
        else:
            rc = 2
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    deps = os.path.join(g, "data", "mapdeps.txt")
    dtmp = deps + ".new-%d" % os.getpid()
    try:
        keep = build_mapdeps(deps, dtmp, os.path.join(state, "mapdeps_state.json"))
        if keep is None:
            rc = 2
        elif gate("mapdeps", deps, dtmp, state, a.accept):
            stamp(dtmp, g, read_stamped(deps), False)
            os.replace(dtmp, deps)
            write_atomic(os.path.join(state, "mapdeps_state.json"), json.dumps(keep, sort_keys=True).encode())
        else:
            rc = 2
    finally:
        if os.path.exists(dtmp):
            os.remove(dtmp)

    if a.atlas and meta_ok:
        pages = [int(os.path.basename(p)[5:-4]) for p in glob.glob(os.path.join(g, "gfx", "mapthumbs", "atlas*.png"))
                 if os.path.basename(p)[5:-4].isdigit()]
        cmd = [sys.executable, "-I", os.path.join(TOOLS, "mapthumbs.py"), "--momentum", view,
               "--gamedir", g, "--fill-missing"]
        if pages:
            cmd += ["--start-page", str(max(pages) + 1)]    # never into a page a release shipped
        before = read_stamped(meta)
        had = set(glob.glob(os.path.join(g, "gfx", "mapthumbs", "atlas*.png")))
        r = subprocess.run(cmd, capture_output=True, text=True)
        say("  atlas: " + (r.stdout.strip().splitlines() or ["?"])[-1])
        if r.returncode != 0:
            # It saves the page before it raises; no row points into it (review 2).
            for p in set(glob.glob(os.path.join(g, "gfx", "mapthumbs", "atlas*.png"))) - had:
                os.remove(p)
                say("  atlas: removed %s, written by the failed run" % p)
            raise SystemExit("mapthumbs failed: %s" % (r.stderr or r.stdout)[-400:])
        stamp(meta, g, before, True)    # the new page's size; a new stamp if cells were added
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--gamedir", default=os.path.join(SURFDIR, "ftesurf"))
    ap.add_argument("--offline", action="store_true", help="no API, no CDN")
    ap.add_argument("--accept", action="store_true", help="install tables the loss gate would refuse")
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

    lock = os.path.join(state, "lock")
    token = take_lock(lock)
    if not token:
        say("  another refresh holds %s -- nothing done" % lock)
        return 3
    try:
        rc = refresh(a, g, state, view)
        # Only from the default gamedir: a scratch --gamedir must not reach an install.
        if (not a.no_second and os.path.isdir(SECOND) and os.path.abspath(SECOND) != g
                and g == os.path.abspath(os.path.join(SURFDIR, "ftesurf"))):
            copy_media(g, SECOND, SECOND)
        if a.export:
            copy_media(g, os.path.join(os.path.abspath(a.export), "ftesurf"), "export " + a.export)
    finally:
        try:
            mine = open(lock, encoding="utf-8").read() == token
        except FileNotFoundError:
            mine = False
        if mine:
            os.remove(lock)
        else:
            say("  the lock is no longer this run's (taken over as stale?) -- left alone")
    say("done in %.0fs, exit %d" % (time.time() - t0, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
