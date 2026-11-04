"""Account cosmetics. No gameplay privileges, client paths or identity claims.

Caller owns BEGIN IMMEDIATE for grants/equipment. Account identity comes only
from social.session or the authenticated, CSRF-checked operator panel. Catalog
IDs and colour numbers are append-only; only fixed native/procedural models draw.
"""
import os
import secrets
import time

CAPACITY = 16
COLOURS = 12
CATALOG = {1: ("Ice outline", "aura"), 2: ("Paper party hat", "hat"), 3: ("Santa hat", "hat")}
CHRISTMAS_EVENT = "christmas-2026"
ROLES = {"zoner": 2, "developer": 4}
SQL = """
CREATE TABLE IF NOT EXISTS account_cosmetics (
 steamid TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0
 CHECK(typeof(revision)='integer' AND revision BETWEEN 0 AND 16777215),
 badges INTEGER NOT NULL DEFAULT 0 CHECK(badges IN (0,2,4,6)));
CREATE TABLE IF NOT EXISTS account_items (
 steamid TEXT NOT NULL, item INTEGER NOT NULL, colour INTEGER NOT NULL,
 equipped INTEGER NOT NULL DEFAULT 0 CHECK(equipped IN (0,1)),
 PRIMARY KEY(steamid,item), CHECK(item IN (1,2)),
 CHECK(typeof(colour)='integer' AND colour BETWEEN 0 AND 11));
"""


# P1304: independently versioned ADDITIVE tables. Core schema stays unchanged:
# an older service can ignore event data without rejecting/downgrading the core
# DB or deleting gifts. Existing account/item/player/run/link tables are untouched.
SQL_EVENT = """
CREATE TABLE IF NOT EXISTS account_event_items (
 steamid TEXT NOT NULL REFERENCES account_cosmetics(steamid),
 item INTEGER NOT NULL CHECK(item=3),
 colour INTEGER NOT NULL DEFAULT 0 CHECK(typeof(colour)='integer' AND colour=0),
 equipped INTEGER NOT NULL DEFAULT 0 CHECK(equipped IN (0,1)),
 PRIMARY KEY(steamid,item));
CREATE TABLE IF NOT EXISTS account_event_grants (
 steamid TEXT NOT NULL REFERENCES account_cosmetics(steamid),
 event TEXT NOT NULL, recorded INTEGER NOT NULL,
 revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)),
 PRIMARY KEY(steamid,event));
CREATE TABLE IF NOT EXISTS account_event_schema (
 version INTEGER PRIMARY KEY CHECK(version=1));
INSERT OR IGNORE INTO account_event_schema(version) VALUES(1);
"""


def ensure_event_schema(db):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"account_event_items", "account_event_grants", "account_event_schema"}
    if "account_event_schema" in tables:
        versions = [r[0] for r in db.execute("SELECT version FROM account_event_schema")]
        columns = {"account_event_items": {"steamid", "item", "colour", "equipped"},
                   "account_event_grants": {"steamid", "event", "recorded", "revoked"}}
        if not required <= tables or versions != [1]:
            raise RuntimeError("Unsupported/incomplete event inventory schema")
        for table, expected in columns.items():
            if not expected <= {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
                raise RuntimeError("Unsupported/incomplete event inventory schema")
        return
    if tables & required:
        raise RuntimeError("Unversioned event inventory tables; preserve for inspection")
    try:
        db.executescript("BEGIN IMMEDIATE;\n" + SQL_EVENT + "\nCOMMIT;")
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise


def item_table(item):
    if type(item) is not int or item not in CATALOG:
        raise ValueError("Unknown item")
    return "account_event_items" if item == 3 else "account_items"


def christmas_active():
    # Operator activation, never a client cvar/profile query. OFF unless explicit.
    return os.environ.get("SURFD_CHRISTMAS_EVENT", "0") == "1"


def linked(db, sid):
    return db.execute("SELECT 1 FROM accounts a JOIN keylinks k ON k.steamid=a.steamid"
                      " WHERE a.steamid=? AND a.banned_at=0 LIMIT 1", (sid,)).fetchone() is not None


def bump(db, sid):
    row = db.execute("SELECT revision FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()
    if row is None or row[0] >= 16777215:
        raise ValueError("Inventory revision unavailable")
    db.execute("UPDATE account_cosmetics SET revision=revision+1 WHERE steamid=?", (sid,))


def grant(db, sid, item):
    if type(item) is not int or item not in CATALOG:
        raise ValueError("Unknown item")
    table = item_table(item)
    if db.execute(f"SELECT 1 FROM {table} WHERE steamid=? AND item=?", (sid, item)).fetchone():
        return False
    if len(owned(db, sid)) >= CAPACITY:
        raise ValueError("Inventory is full")
    colour = secrets.randbelow(COLOURS) if item == 2 else 0
    bump(db, sid)
    db.execute(f"INSERT INTO {table}(steamid,item,colour) VALUES(?,?,?)", (sid, item, colour))
    return True


def ensure(db, sid):
    """One persistent starter grant, not a refill after an operator revokes it."""
    row = db.execute("SELECT revision FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()
    if row:
        # A prior generation may equip party2 without knowing Santa3. Honour
        # that later choice on modern session activity, never delete ownership.
        if row[0] < 16777215 and db.execute(
                "SELECT 1 FROM account_items p JOIN account_event_items e ON e.steamid=p.steamid"
                " WHERE p.steamid=? AND p.item=2 AND p.equipped=1 AND e.equipped=1", (sid,)).fetchone():
            bump(db, sid)
            db.execute("UPDATE account_event_items SET equipped=0 WHERE steamid=?", (sid,))
        return
    db.execute("INSERT INTO account_cosmetics(steamid) VALUES(?)", (sid,))
    for item in (1, 2):
        grant(db, sid, item)


def owned(db, sid):
    items = [dict(id=r["item"], colour=r["colour"], equipped=r["equipped"])
             for r in db.execute("SELECT item,colour,equipped FROM account_items WHERE steamid=?"
                                 " UNION ALL SELECT item,colour,equipped FROM account_event_items WHERE steamid=?"
                                 " ORDER BY item LIMIT 16", (sid, sid))]
    # Also keep read-only profiles / saturated revisions coherent before ensure()
    # can reconcile equipment left by an actual older, Santa-unaware consumer.
    if any(r["id"] == 2 and r["equipped"] for r in items):
        for r in items:
            if r["id"] == 3:
                r["equipped"] = 0
    return items


def public(db, sid):
    if not linked(db, sid):
        return {"roles": 0, "outline": 0, "hat": 0, "santa": 0, "items": []}
    row = db.execute("SELECT badges FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()
    result = {"roles": 1 | (row[0] if row else 0), "outline": 0, "hat": 0, "santa": 0, "items": owned(db, sid)}
    for r in result["items"]:
        if r["equipped"]:
            if r["id"] == 1:
                result["outline"] = 1
            elif r["id"] == 2:
                result["hat"] = r["colour"] + 1
            elif r["id"] == 3:
                result["santa"] = 1
    if result["santa"]:
        result["hat"] = 0  # legacy first-three-field kit remains valid; only one head slot
    return result


def snapshot(db, sid):
    row = db.execute("SELECT revision FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()
    result = dict(revision=row[0] if row else 0, **public(db, sid))
    result["items"] = owned(db, sid)
    return result


def for_wire(value, modern):
    if modern:
        return value
    # Prior SSQC rejects unknown item ids. Preserve its exact supported subset;
    # the permanent gift stays owned in the DB and appears after client/server update.
    value = dict(value)
    value.pop("santa", None)
    value["items"] = [r for r in value["items"] if r["id"] in (1, 2)]
    return value


def grant_christmas_presence(db, sid, now):
    """Caller validated a trusted game roster/session and owns its transaction.

    A web/profile/inventory request never calls this. The marker survives revoke
    so later polls cannot refill an operator-removed event gift.
    """
    if not christmas_active() or not linked(db, sid):
        return False
    ensure(db, sid)
    if db.execute("SELECT 1 FROM account_event_grants WHERE steamid=? AND event=?",
                  (sid, CHRISTMAS_EVENT)).fetchone():
        return False
    current = snapshot(db, sid)
    has_hat = any(r["id"] == 3 for r in current["items"])
    if not has_hat and (len(current["items"]) >= CAPACITY or current["revision"] >= 16777215):
        return False  # fail closed without consuming eligibility or breaking the roster
    changed = False if has_hat else grant(db, sid, 3)
    db.execute("INSERT INTO account_event_grants(steamid,event,recorded) VALUES(?,?,?)",
               (sid, CHRISTMAS_EVENT, int(now)))
    return changed


def equip(db, sid, item, on, revision):
    if type(item) is not int or item not in CATALOG or type(on) is not int or on not in (0, 1):
        raise ValueError("Invalid equipment")
    current = snapshot(db, sid)
    if current["revision"] != revision:
        return None
    owned = next((r for r in current["items"] if r["id"] == item), None)
    if owned is None:
        raise ValueError("You do not own that item")
    conflicting = on and any(r["equipped"] and r["id"] != item and
                             CATALOG[r["id"]][1] == CATALOG[item][1] for r in current["items"])
    if owned["equipped"] != on or conflicting:
        bump(db, sid)
        # One head slot across both tables; aura is an independent category.
        for other, (_, channel) in CATALOG.items():
            if on and other != item and channel == CATALOG[item][1]:
                db.execute(f"UPDATE {item_table(other)} SET equipped=0 WHERE steamid=? AND item=?", (sid, other))
        db.execute(f"UPDATE {item_table(item)} SET equipped=? WHERE steamid=? AND item=?", (on, sid, item))
    return snapshot(db, sid)


def administer(db, sid, op, value):
    if not linked(db, sid):
        raise ValueError("Choose a linked, non-banned Steam account")
    ensure(db, sid)
    if op == "grant":
        grant(db, sid, value)
    elif op == "revoke":
        if type(value) is not int or value not in CATALOG:
            raise ValueError("Unknown item")
        table = item_table(value)
        if db.execute(f"SELECT 1 FROM {table} WHERE steamid=? AND item=?", (sid, value)).fetchone():
            bump(db, sid)
            db.execute(f"DELETE FROM {table} WHERE steamid=? AND item=?", (sid, value))
        if value == 3:
            db.execute("INSERT INTO account_event_grants(steamid,event,recorded,revoked) VALUES(?,?,?,1)"
                       " ON CONFLICT(steamid,event) DO UPDATE SET revoked=1",
                       (sid, CHRISTMAS_EVENT, int(time.time())))
    elif op in ("add-role", "remove-role"):
        if value not in ROLES:
            raise ValueError("Unknown badge")
        bit = ROLES[value]
        badges = db.execute("SELECT badges FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()[0]
        new = badges | bit if op == "add-role" else badges & ~bit
        if new != badges:
            bump(db, sid)
            db.execute("UPDATE account_cosmetics SET badges=? WHERE steamid=?", (new, sid))
    else:
        raise ValueError("Unknown inventory action")
    return snapshot(db, sid)
