"""Account cosmetics. No gameplay privileges, client paths or identity claims.

Caller owns BEGIN IMMEDIATE for grants/equipment. Account identity comes only
from social.session or the authenticated, CSRF-checked operator panel. Catalog
IDs and colour numbers are append-only; the game draws these procedurally.
"""
import secrets

CAPACITY = 16
COLOURS = 12
CATALOG = {1: ("Ice outline", "aura"), 2: ("Paper party hat", "hat")}
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
    if db.execute("SELECT 1 FROM account_items WHERE steamid=? AND item=?", (sid, item)).fetchone():
        return False
    if db.execute("SELECT COUNT(*) FROM account_items WHERE steamid=?", (sid,)).fetchone()[0] >= CAPACITY:
        raise ValueError("Inventory is full")
    colour = secrets.randbelow(COLOURS) if item == 2 else 0
    bump(db, sid)
    db.execute("INSERT INTO account_items(steamid,item,colour) VALUES(?,?,?)", (sid, item, colour))
    return True


def ensure(db, sid):
    """One persistent starter grant, not a refill after an operator revokes it."""
    if db.execute("SELECT 1 FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone():
        return
    db.execute("INSERT INTO account_cosmetics(steamid) VALUES(?)", (sid,))
    for item in CATALOG:
        grant(db, sid, item)


def owned(db, sid):
    return [dict(id=r["item"], colour=r["colour"], equipped=r["equipped"])
            for r in db.execute("SELECT item,colour,equipped FROM account_items WHERE steamid=? ORDER BY item LIMIT 16", (sid,))]


def public(db, sid):
    if not linked(db, sid):
        return {"roles": 0, "outline": 0, "hat": 0, "items": []}
    row = db.execute("SELECT badges FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()
    result = {"roles": 1 | (row[0] if row else 0), "outline": 0, "hat": 0, "items": owned(db, sid)}
    for r in result["items"]:
        if r["equipped"]:
            if r["id"] == 1:
                result["outline"] = 1
            elif r["id"] == 2:
                result["hat"] = r["colour"] + 1
    return result


def snapshot(db, sid):
    row = db.execute("SELECT revision FROM account_cosmetics WHERE steamid=?", (sid,)).fetchone()
    result = dict(revision=row[0] if row else 0, **public(db, sid))
    result["items"] = owned(db, sid)
    return result


def equip(db, sid, item, on, revision):
    if type(item) is not int or item not in CATALOG or type(on) is not int or on not in (0, 1):
        raise ValueError("Invalid equipment")
    current = snapshot(db, sid)
    if current["revision"] != revision:
        return None
    owned = next((r for r in current["items"] if r["id"] == item), None)
    if owned is None:
        raise ValueError("You do not own that item")
    if owned["equipped"] != on:
        bump(db, sid)
        # One item per category when the catalog grows; never clear another category.
        for other, (_, channel) in CATALOG.items():
            if on and other != item and channel == CATALOG[item][1]:
                db.execute("UPDATE account_items SET equipped=0 WHERE steamid=? AND item=?", (sid, other))
        db.execute("UPDATE account_items SET equipped=? WHERE steamid=? AND item=?", (on, sid, item))
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
        if db.execute("SELECT 1 FROM account_items WHERE steamid=? AND item=?", (sid, value)).fetchone():
            bump(db, sid)
            db.execute("DELETE FROM account_items WHERE steamid=? AND item=?", (sid, value))
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
