"""Bounded, durable requests for Momentum demos. No network on the HTTP path.

The handle is runs.rowid/demo-SHA1: both must still describe the displayed PB.
Only momboards' validated upstream hash is spendable, never a caller's URL.
The normal momgrab lock, budget, CDN cooldown and conversion checks apply.
"""
import re

HASH = re.compile(r"^[0-9a-f]{40}$")
CAP = 64
TTL = 86400
HISTORY = 7 * 86400
SQL = """
CREATE TABLE IF NOT EXISTS momrequests (
    hash TEXT PRIMARY KEY,
    map TEXT NOT NULL, track INTEGER NOT NULL, leg INTEGER NOT NULL,
    player TEXT NOT NULL, millis INTEGER NOT NULL,
    requested INTEGER NOT NULL, updated INTEGER NOT NULL,
    state TEXT NOT NULL, why TEXT NOT NULL DEFAULT ''
);
"""


def handle(row):
    h = row["momdemo"]
    if row["rtier"] == "momentum" and isinstance(h, str) and HASH.fullmatch(h):
        return "%d/%s" % (row["rowid"], h)
    return ""


def reply(db, rowid, h, now, enqueue=False):
    """(HTTP code, public state). Validate the live row even on a poll."""
    if rowid < 1 or rowid > 9223372036854775807 or not HASH.fullmatch(h):
        return 400, {"state": "failed", "why": "bad handle"}
    # Acquire the write reservation BEFORE checking capacity: concurrent POSTs
    # must not both spend the final queue slot. No external I/O under this lock.
    if enqueue:
        db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT * FROM runs WHERE rowid=? AND momdemo=?"
                         " AND tier='momentum' AND style='clean'", (rowid, h)).fetchone()
        if row is None:
            return 409, {"state": "failed", "why": "record changed; refresh the board"}
        if row["replay_id"] > 0:
            return 200, {"state": "ready", "rep": row["replay_id"]}
        job = db.execute("SELECT state, why, requested FROM momrequests WHERE hash=?",
                         (h,)).fetchone()
        if job is not None and job["state"] != "ready" and now - job["requested"] < TTL:
            return 200, {"state": job["state"], "why": job["why"]}
        if not enqueue:
            return 404, {"state": "failed", "why": "request expired; click again"}
        db.execute("DELETE FROM momrequests WHERE updated < ?", (now - HISTORY,))
        db.execute("UPDATE momrequests SET state='failed', why='request expired', updated=?"
                   " WHERE state IN ('queued','working') AND requested < ?", (now, now - TTL))
        db.execute("DELETE FROM momrequests WHERE hash IN (SELECT hash FROM momrequests"
                   " WHERE state IN ('ready','failed') ORDER BY updated DESC LIMIT -1 OFFSET 256)")
        n = db.execute("SELECT count(*) FROM momrequests"
                       " WHERE state IN ('queued','working')").fetchone()[0]
        if n >= CAP:
            return 429, {"state": "failed", "why": "demo queue full; try later"}
        db.execute("INSERT OR REPLACE INTO momrequests"
                   " (hash,map,track,leg,player,millis,requested,updated,state)"
                   " VALUES (?,?,?,?,?,?,?,?,'queued')",
                   (h, row["map"], row["track"], row["leg"], row["player"],
                    row["millis"], now, now))
        return 200, {"state": "queued", "why": "waiting for NanoPi downloader"}
    finally:
        if enqueue:
            db.commit()


def pending(db, now):
    """Snapshot of active requests, bounded by CAP. Recover an interrupted job."""
    with db:
        db.execute("UPDATE momrequests SET state='queued', why='retrying interrupted job'"
                   " WHERE state='working' AND updated < ?", (now - 3600,))
        db.execute("UPDATE momrequests SET state='failed', why='request expired', updated=?"
                   " WHERE state IN ('queued','working') AND requested < ?", (now, now - TTL))
    return db.execute("SELECT * FROM momrequests WHERE state='queued'"
                      " ORDER BY requested, hash LIMIT ?", (CAP,)).fetchall()


def set_state(db, h, state, why, now):
    with db:
        db.execute("UPDATE momrequests SET state=?, why=?, updated=? WHERE hash=?",
                   (state, why, now, h))


def finish(db, h, now):
    """Only the requested player's current, matching PB counts as delivered."""
    r = db.execute("SELECT r.replay_id FROM runs r JOIN momrequests q"
                   " ON r.map=q.map AND r.track=q.track AND r.leg=q.leg"
                   " AND r.player=q.player AND r.millis=q.millis AND r.momdemo=q.hash"
                   " WHERE q.hash=? AND r.tier='momentum' AND r.style='clean'", (h,)).fetchone()
    ok = r is not None and r[0] > 0
    set_state(db, h, 'ready' if ok else 'failed', '' if ok else 'record changed or demo not linked', now)
    return ok
