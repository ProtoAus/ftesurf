"""Fetch the Momentum demos the Pi does not hold, and file them as watchable runs.

  python3 momgrab.py [--max N] [--delay S] [--top K] [--go]        (cron)

Lex, 5 Oct 2026: "download new demos not added to the pi yet".  Every cached
Momentum board row (data/momboards, momfetch.py) names its run's demo as
cdn.momentum-mod.org/runs/<replayHash>, and replayHash is the SHA1 of the file
(measured: the 81 KB surf_nebula WR hashes to its own name).  A tick takes up to
--max of them -- the top --top places of every board, best place first, maps
somebody viewed in the last WANT_DAYS first (surfd's mapwant) -- and for each:

  1. downloads it, at most MAX_BYTES, and refuses a file whose SHA1 is not its
     name;
  2. keeps it for good under data/momdemos/<2 hex>/<hash>.mtv;
  3. converts it with tools/momreimport.convert -- the same column rules the
     5,260 re-imported runs went through -- under a header built from the demo
     itself (fresh_header), into <MOMENTUM_DIR>/<map>/<leg>/<leaf>.rec;
  4. files it as a `momentum` replay (momindex.index_one) and links it to its
     board row (momboards.link_demos).

REFUSED, AND REMEMBERED SO IT IS NEVER ASKED AGAIN (state.json): a SHA1 that is
not the name, a demo recorded on another build of the map than the one installed
(its line would be drawn over geometry the player never touched -- momimport's
rule), a header that disagrees with its board row, a run the converter refuses.
A map with no BSP here is filed anyway and marked `nomap`, as momimport did.
A zstd demo waits while this Python has no `zstandard` module (3% of the corpus).

POLITE: one download at a time, --delay apart, --max a tick.  A 404 is the CDN's
answer that the file is gone; anything else that is not a 200 parks the grab for
COOLDOWN, doubling.  It stops while free disk is under FLOOR_GB.  The board cache
is read through queue.json, rebuilt only from board files that changed.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfd as S       # noqa: E402  -- import-safe: app.run is __main__-guarded
import momboards        # noqa: E402
import momindex         # noqa: E402

# tools/momreplay.py, momimport.py and momreimport.py: beside surfd in the repo,
# in the game's tools/ on the Pi (sweep.py's TOOLS).
TOOLS = os.environ.get("SURFD_TOOLS", os.path.join(
    os.environ.get("SURFD_GAME", "/srv/nvme/ftesurf-server/game"), "tools"))
for _d in (TOOLS, os.path.join(HERE, "..", "tools")):
    if os.path.isfile(os.path.join(_d, "momreplay.py")):
        sys.path.insert(0, _d)
        break
import momimport        # noqa: E402
import momreimport      # noqa: E402
import momreplay        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CDN = "https://cdn.momentum-mod.org/runs/"
UA = "FTESurf/0.1 momgrab (+https://proto.bar/ftesurf)"
GRAB_MAX = 6               # demos a tick
GRAB_DELAY = 2.0           # s between downloads
GRAB_TOP = 10              # places of every board worth holding a demo for
MAX_BYTES = 64 << 20       # a 44 s run is 81 KB; an hour is ~7 MB
TIMEOUT = 60
COOLDOWN = 6 * 3600
COOLDOWN_MAX = 48 * 3600
FLOOR_GB = 20              # stop while the data disk has less free than this
WANT_DAYS = 14
QUEUE_FILES = 300          # changed board files read into the queue a tick


class Refused(Exception):
    """The CDN said no to us: parks the grab."""


def _load(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _save(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc))
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# the queue: the top places of every cached board

def refresh_queue(boards_dir, qpath, top, limit):
    """Bring queue.json up to date with the board files, `limit` files a tick.

    A board file is megabytes (655 MB for 3,726 of them on the Pi), so each is
    read once per change, keyed by mtime_ns, and only its first `top` rows kept:
    momfetch holds rows ordered by time."""
    q = _load(qpath)
    if not isinstance(q, dict) or q.get("top") != top:
        q = {"top": top, "seen": {}, "boards": {}}
    try:
        names = sorted(f for f in os.listdir(boards_dir) if f.endswith(".json"))
    except OSError:
        names = []
    read = 0
    for f in names:
        p = os.path.join(boards_dir, f)
        try:
            mt = os.stat(p).st_mtime_ns
        except OSError:
            continue
        if q["seen"].get(f) == mt:
            continue
        if read >= limit:
            break
        read += 1
        doc = _load(p)
        q["seen"][f] = mt
        if not isinstance(doc, dict):
            q["boards"].pop(f, None)
            continue
        mp = S.clean_map(str(doc.get("map") or ""))
        try:
            track, leg = momboards.track_leg(int(doc.get("trackType")),
                                             int(doc.get("trackNum")))
        except (TypeError, ValueError):
            mp = None
        if not mp:
            q["boards"].pop(f, None)
            continue
        rows = []
        for r in (doc.get("rows") or [])[:top]:
            h, sid, t = r.get("hash"), r.get("steamid"), r.get("time")
            if (isinstance(h, str) and len(h) == 40 and momindex.is_steamid64(str(sid))
                    and isinstance(t, (int, float)) and t > 0):
                rows.append([h.lower(), sid, int(round(t * 1000.0))])
        q["boards"][f] = {"map": mp, "track": track, "leg": leg, "rows": rows}
    gone = set(q["boards"]) - set(names)
    for f in gone:
        q["boards"].pop(f, None)
        q["seen"].pop(f, None)
    if read or gone:
        _save(qpath, q)
    return q, read, sum(1 for f in names if q["seen"].get(f) is None)


def pick(q, done, held, prio, n, waiting):
    """The next `n` demos: wanted maps first, then best place, then board."""
    out = []
    for f, b in q["boards"].items():
        for place, (h, sid, ms) in enumerate(b["rows"], 1):
            if h in done or h in waiting:
                continue
            if (b["map"], b["track"], b["leg"], sid) in held:
                continue
            out.append((0 if b["map"] in prio else 1, place, f, h, sid, ms, b))
    out.sort(key=lambda c: c[:4])
    return out[:n]


def held_demos():
    """(map, track, leg, player) of every momentum row that already links one."""
    conn = S.connect()
    try:
        return {tuple(r) for r in conn.execute(
            "SELECT map, track, leg, player FROM runs WHERE tier=? AND replay_id > 0",
            (S.TIER_MOMENTUM,))}
    finally:
        conn.close()


def wanted_maps(now):
    try:
        conn = S.connect()
        try:
            return {r[0].lower() for r in conn.execute(
                "SELECT map FROM mapwant WHERE last >= ?", (now - WANT_DAYS * 86400,))}
        finally:
            conn.close()
    except Exception as e:
        print("  mapwant unreadable (%s): no map goes first" % e)
        return set()


# --------------------------------------------------------------------------
# one demo

def download(h, dest):
    """Fetch one demo to `dest`.  "gone" for a 404; raises Refused otherwise."""
    req = urllib.request.Request(CDN + h, headers={"User-Agent": UA})
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                raise Refused("HTTP %d" % r.status)
            n, sha = 0, hashlib.sha1()
            with open(tmp, "wb") as fh:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    n += len(b)
                    if n > MAX_BYTES:
                        raise ValueError("over %d bytes" % MAX_BYTES)
                    sha.update(b)
                    fh.write(b)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "gone"
        raise Refused("HTTP %d" % e.code)
    except urllib.error.URLError as e:
        raise Refused(str(e.reason))
    except ValueError as e:
        _rm(tmp)
        return "toobig"
    except OSError as e:
        _rm(tmp)
        raise Refused("no answer: %s" % (str(e) or type(e).__name__))
    if sha.hexdigest() != h:
        _rm(tmp)
        return "badhash"
    os.replace(tmp, dest)
    return "ok"


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


_bsp = {}


def bsp_sha1(mp, maps_dir, cache_path):
    """SHA1 of <maps_dir>/<mp>.bsp, upper hex, or None; cached by size and mtime."""
    if not _bsp:
        _bsp.update(_load(cache_path) or {})
    p = os.path.join(maps_dir, mp + ".bsp")
    try:
        st = os.stat(p)
    except OSError:
        return None
    key = [st.st_size, st.st_mtime_ns]
    hit = _bsp.get(mp)
    if hit and hit[:2] == key:
        return hit[2]
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    _bsp[mp] = key + [h.hexdigest().upper()]
    _save(cache_path, _bsp)
    return _bsp[mp][2]


def fresh_header(h, sha, build, track, leg):
    """The header momimport writes for a .wrpath, from the demo's own header;
    momreimport.convert then sets clock, momquality, moves and momdemo."""
    ti = h["tick_interval"]
    return ["FTESURF-REC %d" % momimport.REC_VER,
            "map %s" % h["map"],
            "track %d" % track,
            "startseg %d" % leg,
            "leg %d" % leg,
            "tickrate %.6g" % ti,
            "movetickrate %.6g" % ti,
            "clock sampled",
            "owner %s" % momimport.clean_name(h["player"]),
            "runid mom-%s" % sha[:24],
            "foreign momentum %s %d %d %d %d" % (sha, h["game_mode"], h["track_type"],
                                                 h["track_number"], h["steam_id"]),
            "mapbuild %s %s" % (h["map_sha1"] or "-", build),
            "momquality 0 0 0",
            "flags 0",
            "begin"]


def convert_demo(path, board, ms, maps_dir, bsp_cache, out_root):
    """-> (status, the .rec written or None).  status "ok" files it."""
    try:
        head = momreplay.read_header(open(path, "rb").read(0x200))
    except Exception as e:
        return "unreadable", None
    if (head["map"] or "").lower() != board["map"]:
        return "othermap", None
    track, leg = momimport.track_leg(head["track_type"], head["track_number"])
    if (track, leg) != (board["track"], board["leg"]):
        return "othertrack", None
    ti = head["tick_interval"]
    if not 0.001 <= ti <= 0.1:
        return "unreadable", None
    ticks = int(round(head["run_time"] / ti))
    if abs(ticks * ti * 1000.0 - ms) > 1000.0 * ti + 1:
        return "othertime", None
    want = (head["map_sha1"] or "").upper()
    have = bsp_sha1(board["map"], maps_dir, bsp_cache)
    build = "nomap" if have is None else ("ok" if have == want else "other")
    if build == "other":
        return "otherbuild", None
    sha = os.path.basename(path)[:-4]
    row = {"map": head["map"], "track": track, "leg": leg, "ticks": ticks}
    try:
        text, _info = momreimport.convert(row, path, None,
                                          header=fresh_header(head, sha, build, track, leg))
    except RuntimeError as e:
        if "zstandard" in str(e):
            return "zstd", None
        return "refused", None
    except Exception as e:
        return "refused", None
    leaf = "%07d_%s_run.rec" % (ticks, momimport.who(head["player"], head["steam_id"]))
    dst = os.path.join(out_root, head["map"], momimport.leg_dir(track, leg), leaf)
    if os.path.exists(dst):
        return "have", dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(dst + ".tmp", dst)
    return "ok", dst


def file_rec(conn, dst):
    """Index one written .rec, as momindex does.  -> replay rows added."""
    leaf = os.path.basename(dst)
    legd = os.path.basename(os.path.dirname(dst))
    map_dir = os.path.basename(os.path.dirname(os.path.dirname(dst)))
    track, leg = momindex.leg_of(legd)
    info, why = momindex.read_one(dst)
    if info is None:
        raise ValueError("momindex refused it: %s" % why)
    with conn:
        added, _ = momindex.index_one(conn, map_dir, track, leg, leaf, info,
                                      int(time.time()))
    return added


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=GRAB_MAX, help="demos this tick")
    ap.add_argument("--delay", type=float, default=GRAB_DELAY)
    ap.add_argument("--top", type=int, default=GRAB_TOP)
    ap.add_argument("--boards", default=os.path.join(S.DATA_DIR, "momboards"))
    ap.add_argument("--state", default=os.path.join(S.DATA_DIR, "momgrab"))
    ap.add_argument("--demos", default=os.path.join(S.DATA_DIR, "momdemos"))
    ap.add_argument("--out", default=S.MOMENTUM_DIR)
    ap.add_argument("--maps", default=S.MAPS_DIR)
    ap.add_argument("--go", action="store_true", help="download and file; else a plan")
    a = ap.parse_args()

    now = int(time.time())
    sp = os.path.join(a.state, "state.json")
    st = _load(sp)
    st = st if isinstance(st, dict) else {}
    done, park = st.setdefault("done", {}), st.setdefault("park", {})
    q, read, unread = refresh_queue(a.boards, os.path.join(a.state, "queue.json"),
                                    a.top, QUEUE_FILES)
    try:
        import zstandard  # noqa: F401
        waiting = set()
    except ImportError:
        waiting = {h for h, v in done.items() if v == "zstd"}
    nozstd = {h for h, v in done.items() if v == "zstd"}
    for h in nozstd - waiting:
        del done[h]                     # the module arrived: those go again
    held = held_demos()
    prio = wanted_maps(now)
    todo = pick(q, done, held, prio, max(0, a.max), waiting)
    print("queue: %d board(s) (%d read this tick, %d not yet); %d demo(s) settled;"
          " %d wanted map(s); %d to take"
          % (len(q["boards"]), read, unread, len(done), len(prio & {b["map"] for b in q["boards"].values()}),
             len(todo)))
    if not a.go:
        for c in todo:
            print("   %-28s t%d l%d place %-3d %s" % (c[6]["map"], c[6]["track"],
                                                     c[6]["leg"], c[1], c[3]))
        print("\nDRY RUN -- nothing fetched.  Pass --go.")
        return 0
    if now < int(park.get("until") or 0):
        print("parked: refused (%s), nothing asked until %s"
              % (park.get("why"), time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(park["until"]))))
        _save(sp, st)
        return 0
    free = shutil.disk_usage(os.path.dirname(os.path.abspath(a.demos))).free / 1e9
    if free < FLOOR_GB:
        print("only %.1f GB free (floor %d): taking nothing" % (free, FLOOR_GB))
        _save(sp, st)
        return 0

    tally, asked, filed, linked = {}, 0, 0, 0
    conn = S.connect()
    try:
        for i, (_, place, f, h, sid, ms, b) in enumerate(todo):
            dest = os.path.join(a.demos, h[:2], h + ".mtv")
            if not os.path.exists(dest):
                if asked:
                    time.sleep(a.delay)
                asked += 1
                got = download(h, dest)
                if got != "ok":
                    done[h] = got
                    tally[got] = tally.get(got, 0) + 1
                    continue
            status, rec = convert_demo(dest, b, ms, a.maps,
                                       os.path.join(a.state, "bsp.json"), a.out)
            done[h] = status
            tally[status] = tally.get(status, 0) + 1
            if status in ("ok", "have"):
                try:
                    filed += file_rec(conn, rec)
                except Exception as e:
                    done[h] = "unfiled"
                    print("  %s: %s" % (h, e))
        # Lifted only by an answer: a tick that asked nothing proves nothing.
        if park and asked:
            st["park"] = {}
    except Refused as e:
        n = int(park.get("n") or 0) + 1
        wait = min(COOLDOWN * 2 ** (n - 1), COOLDOWN_MAX)
        st["park"] = {"at": now, "until": now + wait, "n": n, "why": str(e)}
        print("refused: %s -- parked for %d h" % (e, wait // 3600))
    finally:
        _save(sp, st)
        try:
            if filed:
                linked = momboards.link_demos(conn)
        finally:
            conn.close()
    print("grab: %d download(s); %s; %d replay(s) filed, %d board row(s) linked"
          % (asked, ", ".join("%s %d" % kv for kv in sorted(tally.items())) or "nothing",
             filed, linked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
