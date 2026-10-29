"""Paced, resumable walks of one player's Momentum personal bests (P1117).

Queued when a Steam account signs in (accounts.link_return) and daily for every
account (steamsync); momwatch spends a share of its --backfill on them, so no
tick asks more than before.  Both routes are unauthenticated (probed 29 Oct):

    GET /v1/users?steamID=<sid64>                       Momentum's user id
    GET /v1/runs?userID=<id>&isPB=true&take=100&skip=N  newest first, totalCount

Rows file through momboards.flush, so they meet the board crawl's rows under one
key and a slower time never replaces a faster.  Only boards momtracks.tsv names
are filed: the map's own gamemode, style 0.  HTTP only queues; no handler asks.
"""
import json
import math
import sqlite3
import time

API = "https://api.momentum-mod.org/v1"
SQL = """
CREATE TABLE IF NOT EXISTS momprofiles (
 player TEXT PRIMARY KEY, momid INTEGER NOT NULL DEFAULT 0, cursor INTEGER NOT NULL,
 state TEXT NOT NULL, asked INTEGER NOT NULL, updated INTEGER NOT NULL,
 pages INTEGER NOT NULL DEFAULT 0, filed INTEGER NOT NULL DEFAULT 0,
 strikes INTEGER NOT NULL DEFAULT 0
);
"""
TTL = 86400
MAX_ACTIVE = 32
TAKE = 100                  # the API's own cap
MAX_PAGES = 200             # 20,000 PBs; past it the walk is 'limited', not complete
ACTIVE = ("queued", "partial")
STRIKES = 3                 # refusals in a row before a walk is 'refused' (P1117 review 2)
# 'unknown' is Momentum knowing nobody of that SteamID: steamsync gives it a week;
# 'refused' (strikes, an unreadable reply) a day (P1117 review 4).


def status(db, player):
    r = db.execute("SELECT state, cursor, updated, pages, filed FROM momprofiles"
                   " WHERE player = ?", (player,)).fetchone()
    return ({"state": r[0], "next": r[1], "updated": r[2], "pages": r[3], "filed": r[4]}
            if r else {"state": "idle"})


def enqueue(db, player, now):
    """ksfprofile.enqueue's rules: a SteamID64, one live walk, none within TTL."""
    if (len(player) != 17 or not player.isascii() or not player.isdigit()
            or int(player) >> 32 != 0x01100001):
        return {"state": "ineligible"}
    wait = db.execute("PRAGMA busy_timeout").fetchone()[0]
    try:
        db.execute("PRAGMA busy_timeout=50")
        with db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT state, updated FROM momprofiles WHERE player = ?",
                             (player,)).fetchone()
            if old and (old[0] in ACTIVE or now - old[1] < TTL):
                return status(db, player)
            n = db.execute("SELECT COUNT(*) FROM momprofiles WHERE state IN (?, ?)",
                           ACTIVE).fetchone()[0]
            if n >= MAX_ACTIVE:
                return {"state": "busy"}
            mid = db.execute("SELECT momid FROM momusers WHERE steamid = ?",
                             (player,)).fetchone()
            db.execute("INSERT INTO momprofiles (player, momid, cursor, state, asked, updated)"
                       " VALUES (?, ?, 0, 'queued', ?, ?) ON CONFLICT (player) DO UPDATE SET"
                       " momid = excluded.momid, cursor = 0, state = 'queued',"
                       " asked = excluded.asked, updated = excluded.updated,"
                       " pages = 0, filed = 0, strikes = 0", (player, mid[0] if mid else 0, now, now))
        return status(db, player)
    except sqlite3.OperationalError as e:
        if "locked" not in str(e).lower() and "busy" not in str(e).lower():
            raise
        return {"state": "busy"}
    finally:
        db.execute("PRAGMA busy_timeout=%d" % wait)


def _json(body):
    try:
        doc = json.loads(body.decode("utf-8", "replace"))
    except RecursionError:
        raise ValueError("a Momentum reply nested too deep")
    if (not isinstance(doc, dict) or type(doc.get("totalCount")) is not int
            or not isinstance(doc.get("data"), list) or len(doc["data"]) > TAKE):
        raise ValueError("a Momentum reply of the wrong shape")
    return doc


def rows_of(data, player, alias, tracked, now, momid):
    """momboards.flush tuples for this user's PBs on boards we track.  Every field
    is checked for type and range: the reply is somebody else's data."""
    import momboards        # imports surfd: not at accounts' import time
    out = []
    for e in data:
        if not isinstance(e, dict) or e.get("isPB") is not True:
            continue
        key = tuple(e.get(k) for k in ("mapID", "gamemode", "trackType", "trackNum"))
        if (not all(type(x) is int for x in key) or type(e.get("style")) is not int
                or e["style"] != 0 or type(e.get("userID")) is not int or e["userID"] != momid):
            continue
        name, t = tracked.get(key), e.get("time")
        tick = momboards.TICK.get(key[1])
        if (name is None or tick is None or type(t) not in (int, float)
                or not math.isfinite(t) or not 0.0005 <= t < 1e6):
            continue
        track, leg = momboards.track_leg(key[2], key[3])
        ms = int(round(t * 1000.0))
        if ms < 1:                  # 0.0005 s rounds to 0 ms (half to even)
            continue
        when = momboards.created_epoch(e.get("createdAt")) or now
        out.append((name, track, leg, player, alias, int(round(ms / 1000.0 / tick)),
                    1.0 / tick, ms, when, ""))
    return out


def step(db, tracked, budget, get, delay=1.5, now=None):
    """Round-robin the queued walks, one request each in turn, at most `budget`.
    `tracked` is {(mapid, gamemode, trackType, trackNum): map}.  -> requests made.
    The caller's refusal handling applies: whatever `get` raises stops the walk
    with its cursor where the last answered page left it."""
    import momboards
    now = int(time.time()) if now is None else now
    spent = 0
    while spent < budget:
        work = db.execute("SELECT player, momid, cursor, asked, pages FROM momprofiles"
                          " WHERE state IN (?, ?) ORDER BY updated, asked, player LIMIT 3",
                          ACTIVE).fetchall()
        if not work:
            break
        for player, momid, cursor, asked, pages in work:
            if spent >= budget:
                break
            time.sleep(delay)
            spent += 1
            where = (" WHERE player = ? AND cursor = ? AND asked = ? AND state IN (?, ?)",
                     (player, cursor, asked) + ACTIVE)
            url = ("%s/users?steamID=%s" % (API, player) if not momid else
                   "%s/runs?userID=%d&isPB=true&take=%d&skip=%d" % (API, momid, TAKE, cursor))
            try:
                body = get(url)
            except Exception:
                # P1117 review 2: a refused walk gives up its turn, and after STRIKES
                # in a row ends; the caller rests the walks and goes on.
                try:
                    with db:
                        db.execute("UPDATE momprofiles SET updated = ?, strikes = strikes + 1,"
                                   " state = CASE WHEN strikes + 1 >= ? THEN 'refused' ELSE state END"
                                   + where[0], (now, STRIKES) + where[1])
                except sqlite3.Error:
                    pass
                raise
            try:
                doc = _json(body)
                if not momid:
                    ids = [u.get("id") for u in doc["data"]
                           if isinstance(u, dict) and u.get("steamID") == player]
                    ok = len(ids) == 1 and type(ids[0]) is int and 0 < ids[0] < 2 ** 53
                    with db:
                        if ok:
                            db.execute("INSERT INTO momusers (steamid, momid) VALUES (?, ?)"
                                       " ON CONFLICT (steamid) DO UPDATE SET momid = excluded.momid",
                                       (player, ids[0]))
                        db.execute("UPDATE momprofiles SET momid = ?, state = ?, updated = ?, strikes = 0"
                                   + where[0], (ids[0] if ok else 0, "queued" if ok else "unknown",
                                                now) + where[1])
                    continue
                named = db.execute("SELECT name FROM runs WHERE player = ? AND tier = 'momentum'"
                                   " ORDER BY submitted DESC LIMIT 1", (player,)).fetchone() or \
                    db.execute("SELECT name FROM accounts WHERE steamid = ? AND name != ''",
                               (player,)).fetchone()
                rows = rows_of(doc["data"], player, named[0] if named else "?", tracked, now,
                               momid)
                filed = momboards.flush(db, rows)
                nxt = cursor + len(doc["data"])
                state = ("complete" if len(doc["data"]) < TAKE or nxt >= doc["totalCount"]
                         else "limited" if pages + 1 >= MAX_PAGES else "partial")
                with db:
                    db.execute("UPDATE momprofiles SET cursor = ?, state = ?, updated = ?,"
                               " pages = pages + 1, filed = filed + ?, strikes = 0" + where[0],
                               (nxt, state, now, filed) + where[1])
            except (ValueError, TypeError, OverflowError):
                # Not a refusal: a reply this walk cannot read ends it, and steamsync
                # queues it again after TTL.
                try:
                    with db:
                        db.execute("UPDATE momprofiles SET state = 'refused', updated = ?"
                                   + where[0], (now,) + where[1])
                except sqlite3.Error:
                    return spent
            except sqlite3.Error:
                return spent        # the cursor stays; the next tick asks again
    return spent
