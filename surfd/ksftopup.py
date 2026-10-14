"""Bounded, board-scoped KSF demand. HTTP only queues; ksfimport owns fetching.

Forward is `clean` (KSF mode 0). No URL, player id, or filename is accepted.
The importer acknowledges only AFTER filing the durable cached board rows.
"""

SQL = """
CREATE TABLE IF NOT EXISTS ksftopup (
    map TEXT NOT NULL, track INTEGER NOT NULL, leg INTEGER NOT NULL,
    style TEXT NOT NULL, target INTEGER NOT NULL, asked INTEGER NOT NULL,
    updated INTEGER NOT NULL, state TEXT NOT NULL,
    PRIMARY KEY (map, track, leg, style)
);
"""
STYLES = ("clean", "sw", "hsw", "bw")
STEP = 100
MAX_ROWS = 10000
MAX_ACTIVE = 64
RETRY_AFTER = 86400
ACTIVE = ("queued", "partial")


def count(db, key):
    return db.execute("SELECT COUNT(*) FROM runs WHERE map=? AND track=? AND leg=?"
                      " AND style=? AND tier='ksf'", key).fetchone()[0]


def status(db, key):
    row = db.execute("SELECT target, state, updated FROM ksftopup WHERE map=?"
                     " AND track=? AND leg=? AND style=?", key).fetchone()
    return {"state": row[1] if row else "idle", "target": row[0] if row else 0,
            "updated": row[2] if row else 0, "held": count(db, key), "step": STEP}


def enqueue(db, key, now):
    """Called under the caller's short busy timeout; serialize cap/coalescing."""
    if key[3] not in STYLES:
        return None, 400
    with db:
        db.execute("BEGIN IMMEDIATE")
        # A real KSF leg, not arbitrary names from public requests. Empty style
        # boards on a known leg may be asked for, including their first page.
        if not db.execute("SELECT 1 FROM runs WHERE map=? AND track=? AND leg=?"
                          " AND tier='ksf' LIMIT 1", key[:3]).fetchone():
            return None, 404
        old = status(db, key)
        if old["state"] in ACTIVE:
            return old, 202
        if max(old["held"], old["target"]) >= MAX_ROWS:
            return dict(old, state="limited"), 200
        if old["state"] == "exhausted" and now - old["updated"] < RETRY_AFTER:
            return old, 200
        n = db.execute("SELECT COUNT(*) FROM ksftopup WHERE state IN ('queued','partial')").fetchone()[0]
        if n >= MAX_ACTIVE:
            return None, 429
        target = min(MAX_ROWS, max(old["held"], old["target"]) + STEP)
        db.execute("INSERT INTO ksftopup VALUES (?,?,?,?,?,?,?,'queued')"
                   " ON CONFLICT(map,track,leg,style) DO UPDATE SET"
                   " target=excluded.target, asked=excluded.asked,"
                   " updated=excluded.updated, state='queued'", (*key, target, now, now))
        return dict(old, state="queued", target=target, updated=now), 202


def pending(db):
    # Only a bounded snapshot. A popular board cannot starve another forever:
    # a partial attempt moves its updated time to the back of the queue.
    return db.execute("SELECT map,track,leg,style,target FROM ksftopup"
                      " WHERE state IN ('queued','partial') ORDER BY updated,asked,map LIMIT 3").fetchall()


def finish(db, key, target, cached, exhausted, now):
    """Only after write_rows succeeded. CAS protects any later request."""
    state = "exhausted" if exhausted else ("limited" if target >= MAX_ROWS else "done") if cached >= target else "partial"
    with db:
        db.execute("UPDATE ksftopup SET state=?,updated=? WHERE map=? AND track=?"
                   " AND leg=? AND style=? AND target=? AND state IN ('queued','partial')",
                   (state, now, *key, target))
