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
    state TEXT NOT NULL, PRIMARY KEY (map, track, leg)
);
CREATE TABLE IF NOT EXISTS profilefetch (
    player TEXT PRIMARY KEY, asked INTEGER NOT NULL
);
"""
STEP = 100              # places a press adds, as ksftopup
MAX_ROWS = 10000
MAX_ACTIVE = 64
RETRY_AFTER = 3600      # an exhausted board may be asked again after an hour
ACTIVE = ("queued", "partial")
FETCH_DAYS = 7          # a fetched profile walks fully for a week after the press
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
        if old["state"] == "exhausted" and now - old["updated"] < RETRY_AFTER:
            return old, 200
        n = db.execute("SELECT COUNT(*) FROM momtopup WHERE state IN ('queued','partial')").fetchone()[0]
        if n >= MAX_ACTIVE:
            return None, 429
        target = min(MAX_ROWS, max(old["held"], old["target"]) + STEP)
        db.execute("INSERT INTO momtopup VALUES (?,?,?,?,?,?,'queued')"
                   " ON CONFLICT(map,track,leg) DO UPDATE SET target=excluded.target,"
                   " asked=excluded.asked, updated=excluded.updated, state='queued'",
                   (*key, target, now, now))
        return dict(old, state="queued", target=target, updated=now), 202


def ensure_in_tx(db):
    # executescript would COMMIT the caller's transaction; plain statements do not.
    for stmt in SQL.split(";"):
        if stmt.strip():
            db.execute(stmt)


def mom_pending(db, n=3):
    try:
        return db.execute("SELECT map,track,leg,target FROM momtopup WHERE state IN"
                          " ('queued','partial') ORDER BY updated,asked,map LIMIT ?", (n,)).fetchall()
    except sqlite3.OperationalError as e:
        if not _missing(e):
            raise
        return []


def mom_finish(db, key, target, held, total, absent, now):
    """After momfetch wrote the board file: held = places in it, total = the board's size."""
    if absent:
        state = "unsupported"
    elif held >= min(target, total):
        state = "exhausted" if held >= total else "limited" if target >= MAX_ROWS else "done"
    else:
        state = "partial"
    with db:
        db.execute("UPDATE momtopup SET state=?,updated=? WHERE map=? AND track=? AND leg=?"
                   " AND target=? AND state IN ('queued','partial')", (state, now, *key, target))
    return state


# --- Profiles --------------------------------------------------------------------------

def fetch_profile(db, player, now):
    """Mark a profile for a full KSF walk. -> False when MAX_FETCHED others are live."""
    with db:
        db.execute("BEGIN IMMEDIATE")
        ensure_in_tx(db)
        cut = now - FETCH_DAYS * 86400
        if not db.execute("SELECT 1 FROM profilefetch WHERE player=? AND asked>=?",
                          (player, cut)).fetchone():
            n = db.execute("SELECT COUNT(*) FROM profilefetch f JOIN ksfprofiles p"
                           " ON p.player=f.player WHERE f.asked>=? AND p.state IN"
                           " ('queued','partial')", (cut,)).fetchone()[0]
            if n >= MAX_FETCHED:
                return False
        db.execute("INSERT INTO profilefetch VALUES (?,?) ON CONFLICT(player)"
                   " DO UPDATE SET asked=excluded.asked", (player, now))
    return True


def fetched(db, player, now):
    try:
        return db.execute("SELECT 1 FROM profilefetch WHERE player=? AND asked>=?",
                          (player, now - FETCH_DAYS * 86400)).fetchone() is not None
    except sqlite3.OperationalError as e:
        if not _missing(e):
            raise
        return False
