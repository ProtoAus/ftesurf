"""Fetch the Momentum demos the Pi does not hold, and file them as watchable runs.

  python3 momgrab.py [--max N] [--delay S] [--top K] [--go]        (cron)

Lex, 5 Oct 2026: "download new demos not added to the pi yet".  Every cached
Momentum board row (data/momboards, momfetch.py) names its run's demo as
cdn.momentum-mod.org/runs/<replayHash>, and replayHash is the SHA1 of the file
(measured: the 81 KB surf_nebula WR hashes to its own name).  A tick takes up to
--max of them -- each player's best on every board, the top --top places, best
place first, maps somebody viewed in the last WANT_DAYS first (mapwant) -- and:

  1. downloads it, at most MAX_BYTES, and refuses a file whose SHA1 is not its
     name;
  2. keeps it for good under data/momdemos/<2 hex>/<hash>.mtv;
  3. converts it with tools/momreimport.convert -- the rules the 5,260
     re-imported runs went through -- under a header built from the demo
     itself (fresh_header), into <MOMENTUM_DIR>/<map>/<leg>/<leaf>.rec;
  4. files the recording (momindex.index_one, replays row only) and links it
     to its board row only when the row's time is the run's (link_exact).

SETTLED, so never asked again (state.json "done"): a SHA1 that is not the name,
a file the CDN does not have (403/404/410), a demo on another build of the map
than the installed one (its line would be drawn over geometry the player never
touched -- momimport's rule), a header that disagrees with its row, a run the
converter refuses or longer than MAX_SECONDS.  A map with no BSP here is filed
anyway and marked `nomap`, as momimport did.

TRIED AGAIN ("later"): a transfer cut short, a locked database, a conversion
that ran out of memory or died mid-way (`inflight`), an object the CDN keeps
answering 5xx -- STRIKES times, then left alone for RETRY_DAYS.  A zstd demo
waits for the `zstandard` module (3% of the local corpus).

POLITE: one run at a time (take_lock), one download at a time, --delay apart,
--max a tick.  A 429, a 5xx or no answer parks the grab for COOLDOWN, doubling,
and only an answered tick lifts it.  Nothing is taken below FLOOR_GB free.
"""
import argparse
import hashlib
import http.client
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Importing surfd logs "surfd ready" to surfd.log, which reads as a restart on
# every tick (sweep.py's fix): a handler on its logger first keeps it quiet.
if not logging.getLogger("surfd").handlers:
    _quiet = logging.StreamHandler(sys.stderr)
    _quiet.setLevel(logging.WARNING)
    logging.getLogger("surfd").addHandler(_quiet)

import surfd as S       # noqa: E402  -- import-safe: app.run is __main__-guarded
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
MAX_BYTES = 16 << 20       # a 44 s run is 81 KB
MAX_SECONDS = 1800         # converting 7,000 s peaked at 440 MB; the Pi has ~1 GB
TIMEOUT = 60
COOLDOWN = 6 * 3600
COOLDOWN_MAX = 48 * 3600
STRIKES = 3                # transient failures before a demo is left alone...
RETRY_DAYS = 30            # ...for this long
FLOOR_GB = 20              # stop while the data disk has less free than this
WANT_DAYS = 14
QUEUE_FILES = 300          # changed board files read into the queue a tick
LINK_MS = 20               # a row and a recording are one run within this
HASH_RE = re.compile(r"[0-9a-f]{40}")


class Refused(Exception):
    """The CDN said no to us, or did not answer: parks the grab.  `obj` marks a
    5xx only this object got, which also counts against the object."""

    def __init__(self, msg, obj=False):
        Exception.__init__(self, msg)
        self.obj = obj


class Transient(Exception):
    """This object's transfer broke off: tried again next tick, STRIKES at most."""


class TooBig(Exception):
    pass


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


def take_lock(d):
    """One momgrab at a time: two would download into one .part and race state."""
    os.makedirs(d, exist_ok=True)
    fh = io.open(os.path.join(d, ".lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


# --------------------------------------------------------------------------
# the queue: each player's best, the top places of every cached board

def refresh_queue(boards_dir, qpath, top, limit):
    """Bring queue.json up to date with the board files, `limit` files a tick.

    A board file is megabytes (655 MB for 3,726 of them on the Pi), so each is
    read once per change, keyed by mtime_ns.  momfetch's cache is a union that
    keeps a player's superseded times, so only each player's fastest row counts
    -- an old personal best's demo is not their row's run."""
    q = _load(qpath)
    if not isinstance(q, dict) or q.get("top") != top or q.get("v") != 2:
        q = {"v": 2, "top": top, "seen": {}, "boards": {}}
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
            track, leg = momimport.track_leg(int(doc.get("trackType")),
                                             int(doc.get("trackNum")))
        except (TypeError, ValueError):
            mp = None
        if not mp:
            q["boards"].pop(f, None)
            continue
        best = {}
        for r in (doc.get("rows") or []):
            h, sid, t = str(r.get("hash") or "").lower(), str(r.get("steamid") or ""), r.get("time")
            if (HASH_RE.fullmatch(h) and momindex.is_steamid64(sid)
                    and isinstance(t, (int, float)) and t > 0):
                ms = int(round(t * 1000.0))
                if sid not in best or ms < best[sid][2]:
                    best[sid] = [h, sid, ms]
        rows = sorted(best.values(), key=lambda x: (x[2], x[1]))[:top]
        q["boards"][f] = {"map": mp, "track": track, "leg": leg, "rows": rows}
    gone = set(q["boards"]) - set(names)
    for f in gone:
        q["boards"].pop(f, None)
        q["seen"].pop(f, None)
    if read or gone:
        _save(qpath, q)
    return q, read, sum(1 for f in names if q["seen"].get(f) is None)


def held_runs():
    """(map, track, leg, player) -> the times of every Momentum recording held.

    A RUN is held, not a player: one who improved holds the old run's demo, and
    their row is still waiting for the new one."""
    conn = S.connect()
    try:
        out = {}
        for mp, tr, lg, pl, ms in conn.execute(
                "SELECT map, track, leg, player, millis FROM replays WHERE kind='momentum'"):
            out.setdefault((mp, tr, lg, pl), []).append(ms)
        return out
    finally:
        conn.close()


def is_held(held, b, sid, ms):
    return any(abs(x - ms) <= LINK_MS for x in held.get((b["map"], b["track"], b["leg"], sid), ()))


def waiting(later, h, now, zstd):
    """True while a demo that failed for a passing reason should not be asked."""
    w = later.get(h)
    if not w:
        return False
    if w[2] == "zstd":
        return not zstd
    return w[0] >= STRIKES and now - w[1] < RETRY_DAYS * 86400


def pick(q, done, later, held, prio, n, now, zstd):
    """The next `n` demos: wanted maps first, then best place, then board."""
    out = []
    for f, b in q["boards"].items():
        for place, (h, sid, ms) in enumerate(b["rows"], 1):
            if h in done or waiting(later, h, now, zstd) or ms > MAX_SECONDS * 1000:
                continue
            if is_held(held, b, sid, ms):
                continue
            out.append((0 if b["map"] in prio else 1, place, f, h, sid, ms, b))
    out.sort(key=lambda c: c[:4])
    return out[:n]


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
    """Fetch one demo to `dest`: "ok", "gone" (403/404/410), "toobig" or
    "badhash".  Raises Transient for a transfer cut short, Refused otherwise."""
    req = urllib.request.Request(CDN + h, headers={"User-Agent": UA})
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                raise Refused("HTTP %d" % r.status)
            want = str(r.headers.get("Content-Length") or "")
            n, sha = 0, hashlib.sha1()
            with open(tmp, "wb") as fh:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    n += len(b)
                    if n > MAX_BYTES:
                        raise TooBig()
                    sha.update(b)
                    fh.write(b)
            # A body cut short with a Content-Length reads as a short file, not
            # an exception: without this it was settled as a bad hash for good.
            if want.isdigit() and n != int(want):
                raise Transient("cut short at %d of %s bytes" % (n, want))
    except urllib.error.HTTPError as e:
        _rm(tmp)
        if e.code in (403, 404, 410):
            return "gone"
        raise Refused("HTTP %d" % e.code, obj=e.code >= 500 and e.code != 503)
    except urllib.error.URLError as e:
        _rm(tmp)
        raise Refused(str(e.reason))
    except TooBig:
        _rm(tmp)
        return "toobig"
    except Transient:
        _rm(tmp)
        raise
    except http.client.IncompleteRead:
        _rm(tmp)
        raise Transient("cut short")
    except (OSError, http.client.HTTPException) as e:
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
_bsp_names = {}


def bsp_sha1(mp, maps_dir, cache_path):
    """SHA1 of the installed BSP for `mp`, upper hex, or None; cached by size
    and mtime.  The name is matched without case: board names are lowercased and
    six BSPs on the Pi are not (bhop_HaddocK), and a miss there would file a
    demo of any build as `nomap` (review, 5 Oct)."""
    if not _bsp:
        _bsp.update(_load(cache_path) or {})
    if maps_dir not in _bsp_names:
        try:
            _bsp_names[maps_dir] = {f[:-4].lower(): f for f in os.listdir(maps_dir)
                                    if f.lower().endswith(".bsp")}
        except OSError:
            _bsp_names[maps_dir] = {}
    f = _bsp_names[maps_dir].get(mp.lower())
    if f is None:
        return None
    p = os.path.join(maps_dir, f)
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
    """-> (status, the .rec written or None).  "ok"/"have" file it; "zstd" and
    "error" are passing; anything else settles the demo."""
    try:
        head = momreplay.read_header(open(path, "rb").read(0x200))
    except Exception:
        return "unreadable", None
    if (head["map"] or "").lower() != board["map"]:
        return "othermap", None
    track, leg = momimport.track_leg(head["track_type"], head["track_number"])
    if (track, leg) != (board["track"], board["leg"]):
        return "othertrack", None
    ti = head["tick_interval"]
    if not 0.001 <= ti <= 0.1 or not head["run_time"] > 0:
        return "unreadable", None
    if head["run_time"] > MAX_SECONDS:
        return "toolong", None
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
    except MemoryError:
        return "error", None
    except RuntimeError as e:
        return ("zstd" if "zstandard" in str(e) else "refused"), None
    except Exception:
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
    """File one written .rec as a `momentum` replay and link it to the board row
    whose time is its own.  -> (replay added, row linked).

    THE BOARD ROW IS NOT TOUCHED OTHERWISE: momindex's own upsert would take a
    recording a few ms under its row as an improvement and re-date the row to
    today (review, 5 Oct: 12 of 615)."""
    leaf = os.path.basename(dst)
    legd = os.path.basename(os.path.dirname(dst))
    map_dir = os.path.basename(os.path.dirname(os.path.dirname(dst)))
    track, leg = momindex.leg_of(legd)
    info, why = momindex.read_one(dst)
    if info is None:
        raise ValueError("momindex refused it: %s" % why)
    with conn:
        added, _ = momindex.index_one(conn, map_dir, track, leg, leaf, info,
                                      int(time.time()), board=False)
        rid = conn.execute("SELECT id FROM replays WHERE map=? AND track=? AND leg=?"
                           " AND leaf=?", (map_dir.lower(), track, leg, leaf)).fetchone()[0]
        linked = link_exact(conn, rid, map_dir.lower(), track, leg, info["player"],
                            info["millis"])
    return added, linked


def link_exact(conn, rid, mp, track, leg, player, ms):
    """Point the row at this recording when the row's time is the recording's
    and its current link is not -- a player who improved holds the old run's
    link until now.  A matching link is never replaced."""
    return conn.execute(
        "UPDATE runs SET replay_id=? WHERE map=? AND track=? AND leg=? AND tier=?"
        " AND style=? AND player=? AND abs(millis - ?) <= ?"
        " AND (replay_id = 0 OR NOT EXISTS (SELECT 1 FROM replays p"
        "      WHERE p.id = runs.replay_id AND abs(p.millis - runs.millis) <= ?))",
        (rid, mp, track, leg, S.TIER_MOMENTUM, S.STYLE_CLEAN, player, ms, LINK_MS,
         LINK_MS)).rowcount


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

    lock = take_lock(a.state)
    if lock is None:
        print("another momgrab holds %s -- not running beside it" % a.state)
        return 0
    try:
        return run(a)
    finally:
        lock.close()


def run(a):
    now = int(time.time())
    sp = os.path.join(a.state, "state.json")
    st = _load(sp)
    st = st if isinstance(st, dict) else {}
    done = st.setdefault("done", {})
    later = st.setdefault("later", {})
    park = st.setdefault("park", {})

    def again(h, why):
        w = later.get(h) or [0, 0, why]
        later[h] = [w[0] + 1, now, why]

    # A conversion the OS killed never reached `finally`: it counts as a try.
    if st.get("inflight"):
        again(st["inflight"], "crashed")
        st["inflight"] = None
    try:
        import zstandard  # noqa: F401
        zstd = True
    except ImportError:
        zstd = False
    q, read, unread = refresh_queue(a.boards, os.path.join(a.state, "queue.json"),
                                    a.top, QUEUE_FILES)
    held = held_runs()
    prio = wanted_maps(now)
    todo = pick(q, done, later, held, prio, max(0, a.max), now, zstd)
    print("queue: %d board(s) (%d read this tick, %d not yet); %d settled, %d waiting;"
          " %d wanted map(s); %d to take"
          % (len(q["boards"]), read, unread, len(done), len(later),
             len(prio & {b["map"] for b in q["boards"].values()}), len(todo)))
    if not a.go:
        for c in todo:
            print("   %-28s t%d l%d place %-3d %s" % (c[6]["map"], c[6]["track"],
                                                     c[6]["leg"], c[1], c[3]))
        print("\nDRY RUN -- nothing fetched.  Pass --go.")
        _save(sp, st)
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

    tally, asked, filed, linked, cur = {}, 0, 0, 0, None
    conn = S.connect()
    try:
        for _, place, f, h, sid, ms, b in todo:
            cur = h
            dest = os.path.join(a.demos, h[:2], h + ".mtv")
            if not os.path.exists(dest):
                if asked:
                    time.sleep(a.delay)
                asked += 1
                try:
                    got = download(h, dest)
                except Transient as e:
                    again(h, str(e))
                    tally["cut short"] = tally.get("cut short", 0) + 1
                    break                   # the next tick tries again
                if got != "ok":
                    done[h] = got
                    later.pop(h, None)
                    tally[got] = tally.get(got, 0) + 1
                    _save(sp, st)
                    continue
            st["inflight"] = h
            _save(sp, st)
            status, rec = convert_demo(dest, b, ms, a.maps,
                                       os.path.join(a.state, "bsp.json"), a.out)
            st["inflight"] = None
            if status in ("ok", "have"):
                try:
                    n, l = file_rec(conn, rec)
                    filed += n
                    linked += l
                except sqlite3.Error as e:
                    status = "dblock"
                except ValueError as e:
                    status = "unfiled"
                    print("  %s: %s" % (h, e))
            tally[status] = tally.get(status, 0) + 1
            if status in ("zstd", "error", "dblock"):
                again(h, status)
            else:
                done[h] = status
                later.pop(h, None)
            _save(sp, st)
        # Lifted only by an answer: a tick that asked nothing proves nothing.
        if park and asked:
            st["park"] = {}
    except Refused as e:
        n = int(park.get("n") or 0) + 1
        wait = min(COOLDOWN * 2 ** (n - 1), COOLDOWN_MAX)
        st["park"] = {"at": now, "until": now + wait, "n": n, "why": str(e)}
        print("refused: %s -- parked for %d h" % (e, wait // 3600))
        # A 5xx only this object gets also counts against it, or one object the
        # CDN keeps failing would stand first in line after every park.
        if e.obj and cur:
            again(cur, str(e))
    finally:
        _save(sp, st)
        conn.close()
    print("grab: %d download(s); %s; %d replay(s) filed, %d board row(s) linked"
          % (asked, ", ".join("%s %d" % kv for kv in sorted(tally.items())) or "nothing",
             filed, linked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
