"""P1448: explicit "Fetch" demand the import crons spend. HTTP only queues.

momtopup     one Momentum board (a leg) to refresh and deepen; momwatch spends it.
profilefetch a player whose KSF walk may go past a profile view's limits (stage and
             bonus PBs, more than VIEW_PAGES); ksfprofile reads it.

Optional tables (CREATE IF NOT EXISTS), not a core schema bump: an older generation
never reads them, and every reader here treats a missing table as an empty queue.
"""
import io
import os
import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS momtopup (
    map TEXT NOT NULL, track INTEGER NOT NULL, leg INTEGER NOT NULL,
    target INTEGER NOT NULL, asked INTEGER NOT NULL, updated INTEGER NOT NULL,
    state TEXT NOT NULL, strikes INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (map, track, leg)
);
CREATE TABLE IF NOT EXISTS profilefetch (
    player TEXT PRIMARY KEY, asked INTEGER NOT NULL
);
"""
STEP = 100              # places a press adds, as ksftopup
MAX_ROWS = 10000
MAX_ACTIVE = 64
RETRY_AFTER = 86400     # an unsupported leg is asked again after a day
REFRESH_AFTER = 3600    # an exhausted board's Fetch refreshes page 1 after an hour
ACTIVE = ("queued", "partial")
STRIKES = 3             # refusals in a row before a Momentum board's job is retired
MAX_FETCHED = 8         # live full walks of non-account profiles


def ensure(db):
    db.executescript(SQL)


def _missing(e):
    return isinstance(e, sqlite3.OperationalError) and "no such table" in str(e)


# --- Momentum boards -----------------------------------------------------------------

_tracks = {"key": None, "boards": {}}


def _gm_of(name):
    n = name.lower()
    return 1 if n.startswith("surf_") else 2 if n.startswith("bhop_") else None


def track_leg(tt, tn):
    """momboards.track_leg: Momentum's (trackType, trackNum) -> our (track, leg)."""
    return (0, 0) if tt == 0 else (0, tn) if tt == 1 else (tn, 0)


def mom_board(path, mp, track, leg):
    """(mapid, gamemode, trackType, trackNum) of the map's own-gamemode board for this
    leg in momwatch's catalogue (momtracks.tsv), or None. Re-read when the file changes."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    if _tracks["key"] != key:
        boards = {}
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                f = ln.rstrip("\n").split("\t")
                if ln.startswith("#") or len(f) < 6:
                    continue
                try:
                    mid, gm, tt, tn = int(f[1]), int(f[3]), int(f[4]), int(f[5])
                except ValueError:
                    continue
                name = f[0].lower()
                if gm == _gm_of(name):
                    boards[(name,) + track_leg(tt, tn)] = (mid, gm, tt, tn)
        _tracks["key"], _tracks["boards"] = key, boards
    return _tracks["boards"].get((mp.lower(), track, leg))


def board_key(b):
    return "%d_g%d_t%d%d" % b       # momfetch.board_key


def mom_count(db, key):
    return db.execute("SELECT COUNT(*) FROM runs WHERE map=? AND track=? AND leg=?"
                      " AND tier='momentum'", key).fetchone()[0]


def mom_status(db, key, tracks):
    try:
        row = db.execute("SELECT target, state, updated FROM momtopup WHERE map=?"
                         " AND track=? AND leg=?", key).fetchone()
    except sqlite3.OperationalError as e:
        if not _missing(e):
            raise
        row = None
    return {"state": row[1] if row else "idle", "target": row[0] if row else 0,
            "updated": row[2] if row else 0, "held": mom_count(db, key), "step": STEP,
            "eligible": mom_board(tracks, *key) is not None}


def mom_enqueue(db, key, now, tracks):
    """ksftopup.enqueue's rules for a Momentum leg. -> (body, code); body None on 404/429."""
    if mom_board(tracks, *key) is None:
        return None, 404
    with db:
        db.execute("BEGIN IMMEDIATE")
        ensure_in_tx(db)
        old = mom_status(db, key, tracks)
        if old["state"] in ACTIVE:
            return old, 202
        if max(old["held"], old["target"]) >= MAX_ROWS:
            return dict(old, state="limited"), 200
        quiet = {"exhausted": REFRESH_AFTER, "unsupported": RETRY_AFTER}.get(old["state"])
        if quiet is not None and now - old["updated"] < quiet:
            return old, 200
        n = db.execute("SELECT COUNT(*) FROM momtopup WHERE state IN ('queued','partial')").fetchone()[0]
        if n >= MAX_ACTIVE:
            return None, 429
        target = min(MAX_ROWS, max(old["held"], old["target"]) + (0 if quiet is not None else STEP))
        db.execute("INSERT INTO momtopup (map,track,leg,target,asked,updated,state) VALUES (?,?,?,?,?,?,'queued')"
                   " ON CONFLICT(map,track,leg) DO UPDATE SET target=excluded.target,"
                   " asked=excluded.asked, updated=excluded.updated, state='queued', strikes=0",
                   (*key, target, now, now))
        return dict(old, state="queued", target=target, updated=now), 202


def ensure_in_tx(db):
    # executescript would COMMIT the caller's transaction; plain statements do not.
    for stmt in SQL.split(";"):
        if stmt.strip():
            db.execute(stmt)


def mom_pending(db, n=3):
    try:
        return db.execute("SELECT map,track,leg,target,state FROM momtopup WHERE state IN"
                          " ('queued','partial') ORDER BY updated,asked,map LIMIT ?", (n,)).fetchall()
    except sqlite3.OperationalError as e:
        if not _missing(e):
            raise
        return []


def mom_touch(db, key, target, now):
    """Before a job's requests: a refusal leaves it at the back of the queue, not first."""
    with db:
        db.execute("UPDATE momtopup SET updated=? WHERE map=? AND track=? AND leg=? AND target=?"
                   " AND state IN ('queued','partial')", (now, *key, target))


def mom_finish(db, key, target, held, total, absent, now, progressed=True):
    """After momfetch wrote the board file. `held` is the depth -- places held or the deepest
    rank, whichever is more (momfetch pages from the deepest, so a board with holes counts its
    rank) -- and a job that asked and gained nothing is done, not retried every tick."""
    if absent:
        state = "unsupported"
    elif held >= min(target, total):
        state = "exhausted" if held >= total else "limited" if target >= MAX_ROWS else "done"
    elif not progressed:
        state = "done"
    else:
        state = "partial"
    with db:
        db.execute("UPDATE momtopup SET state=?,updated=?,strikes=0 WHERE map=? AND track=? AND leg=?"
                   " AND target=? AND state IN ('queued','partial')", (state, now, *key, target))
    return state


def mom_strike(db, key, target, now):
    """A refused fetch: STRIKES in a row retire the job (unsupported, asked again after a day)."""
    with db:
        db.execute("UPDATE momtopup SET strikes=strikes+1, state=CASE WHEN strikes+1>=? THEN 'unsupported'"
                   " ELSE state END, updated=? WHERE map=? AND track=? AND leg=? AND target=?"
                   " AND state IN ('queued','partial')", (STRIKES, now, *key, target))


# --- Profiles --------------------------------------------------------------------------

LIVE_MARK = ("SELECT 1 FROM profilefetch f JOIN ksfprofiles p ON p.player=f.player"
             " WHERE f.player=%s AND f.asked=p.asked")


def fetch_profile(db, player, now):
    """Mark the KSF walk a press just started (its `asked` is `now`) as a full walk; the mark ends
    with that walk. -> whether the walk is a full one. Accounts walk fully anyway, uncounted;
    other players' marked walks are MAX_FETCHED at most."""
    with db:
        db.execute("BEGIN IMMEDIATE")
        ensure_in_tx(db)
        walk = db.execute("SELECT state, asked FROM ksfprofiles WHERE player=?", (player,)).fetchone()
        if walk is None or walk[0] not in ACTIVE:
            return False
        if walk[1] != now:                  # a walk an earlier press or view started: as it is
            return db.execute(LIVE_MARK % "?", (player,)).fetchone() is not None
        mine = db.execute("SELECT 1 FROM accounts WHERE steamid=? AND banned_at=0", (player,)).fetchone()
        if not mine:
            n = db.execute("SELECT COUNT(*) FROM profilefetch f JOIN ksfprofiles p ON p.player=f.player"
                           " WHERE f.asked=p.asked AND p.state IN ('queued','partial') AND f.player!=?"
                           " AND NOT EXISTS (SELECT 1 FROM accounts a WHERE a.steamid=f.player"
                           " AND a.banned_at=0)", (player,)).fetchone()[0]
            if n >= MAX_FETCHED:
                return False
        db.execute("INSERT INTO profilefetch VALUES (?,?) ON CONFLICT(player)"
                   " DO UPDATE SET asked=excluded.asked", (player, now))
    return True


def fetched(db, player, now=None):
    """Is the player's current KSF walk one a Fetch press marked?"""
    try:
        return db.execute(LIVE_MARK % "?", (player,)).fetchone() is not None
    except sqlite3.OperationalError as e:
        if not _missing(e):
            raise
        return False
