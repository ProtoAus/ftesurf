"""Steam-account friendships and lobby-mediated presence/private chat.

No public reader or client-supplied identity. Only accounts.register's VERIFIED
proof path mints a capability; it stays on the lobby. Every use rechecks the
key link and ban, and binds the capability to that lobby's node. Presence and
join addresses are never supplied by clients. Messages are operator-readable,
not E2E encrypted, and are bounded/expired (not logged).
"""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from flask import Response, request
import accounts

MAX_FRIENDS = 128
PRESENCE_TTL = 16
SESSION_TTL = 86400
MESSAGE_TTL = 120
TOKEN = re.compile(r"[0-9a-f]{64}\Z")
MARK = re.compile(r"[0-9a-f]{8}(?:[0-9a-f]{4})?\Z")
SQL = """
CREATE TABLE IF NOT EXISTS social_friends (
 lo TEXT NOT NULL, hi TEXT NOT NULL, asker TEXT NOT NULL,
 accepted INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(lo,hi));
CREATE INDEX IF NOT EXISTS social_friends_hi ON social_friends (hi);
CREATE TABLE IF NOT EXISTS social_sessions (
 token TEXT PRIMARY KEY, pub TEXT NOT NULL, steamid TEXT NOT NULL,
 node TEXT NOT NULL, issued INTEGER NOT NULL, seen INTEGER NOT NULL DEFAULT 0,
 ack INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS social_sessions_seen ON social_sessions (steamid,seen);
CREATE TABLE IF NOT EXISTS social_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL,
 recipient TEXT NOT NULL, body TEXT NOT NULL, sent INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS social_messages_recipient ON social_messages (recipient,id);
"""


def digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def issue(db, pub, sid, node, now, old_token=""):
    """Called only after connect/confirm proof validation, never from a social POST."""
    token = secrets.token_hex(32)
    ack = 0
    if TOKEN.fullmatch(old_token):
        old = db.execute("SELECT ack,steamid FROM social_sessions WHERE token=? AND pub=? AND node=?",
                         (digest(old_token), pub, node)).fetchone()
        if old and old["steamid"] == sid:
            ack = old["ack"]
        db.execute("DELETE FROM social_sessions WHERE token=? AND pub=? AND node=?",
                   (digest(old_token), pub, node))
    db.execute("DELETE FROM social_sessions WHERE issued<?", (now - SESSION_TTL,))
    # Per-CONNECTION capability, not UNIQUE(pub,node): copied installations can
    # legitimately prove the same key on two simultaneous connections.
    db.execute("INSERT INTO social_sessions(token,pub,steamid,node,issued,ack) VALUES(?,?,?,?,?,?)",
               (digest(token), pub, sid, node, now, ack))
    return {"social": token, "social_who": accounts.who_of(sid)}


def session(db, token, node, now):
    if not TOKEN.fullmatch(token):
        return None
    return db.execute(
        "SELECT s.* FROM social_sessions s JOIN keylinks k ON k.pub=s.pub"
        " AND k.steamid=s.steamid JOIN accounts a ON a.steamid=s.steamid"
        " WHERE s.token=? AND s.node=? AND s.issued>? AND a.banned_at=0",
        (digest(token), node, now - SESSION_TTL)).fetchone()


def pair(a, b):
    return tuple(sorted((a, b)))


def relation(db, a, b):
    row = db.execute("SELECT asker,accepted FROM social_friends WHERE lo=? AND hi=?",
                     pair(a, b)).fetchone()
    if not row:
        return 0
    return 3 if row["accepted"] else (1 if row["asker"] == a else 2)


def resolve(db, mark, owner=None):
    # Never guess an ambiguous truncated identifier or give a GUID namespace authority.
    if not MARK.fullmatch(mark):
        return None
    if owner is None:
        candidates = [r["steamid"] for r in db.execute("SELECT steamid FROM accounts WHERE banned_at=0")]
    else:
        # Removal addresses ONLY this account's graph, even after the other
        # account is banned/deleted. Hidden rows must not trap the quota forever.
        candidates = set()
        for r in db.execute("SELECT lo,hi FROM social_friends WHERE lo=? OR hi=?", (owner, owner)):
            candidates.add(r["hi"] if r["lo"] == owner else r["lo"])
    rows = [sid for sid in candidates if
            (accounts.who_of(sid) if len(mark) == 8 else hashlib.sha256(sid.encode("ascii")).hexdigest()[:12]) == mark]
    return rows[0] if len(rows) == 1 else None


def presence(db, sid, now, lobby_ttl):
    row = db.execute(
        "SELECT l.addr,l.name,l.map FROM social_sessions s"
        " JOIN keylinks k ON k.pub=s.pub AND k.steamid=s.steamid"
        " JOIN accounts a ON a.steamid=s.steamid JOIN lobbies l ON l.node=s.node"
        " WHERE s.steamid=? AND s.seen>? AND s.issued>? AND a.banned_at=0"
        " AND l.last_seen>? ORDER BY s.seen DESC,s.node LIMIT 1",
        (sid, now - PRESENCE_TTL, now - SESSION_TTL, now - lobby_ttl)).fetchone()
    if not row:
        return {"online": 0, "addr": "", "server": "", "map": ""}
    return {"online": 1, "addr": row["addr"], "server": row["name"], "map": row["map"]}


def friend_rows(db, sid, now, lobby_ttl):
    rows = []
    for r in db.execute("SELECT lo,hi,asker,accepted FROM social_friends WHERE lo=? OR hi=?",
                        (sid, sid)):
        other = r["hi"] if r["lo"] == sid else r["lo"]
        account = db.execute("SELECT name,banned_at FROM accounts WHERE steamid=?", (other,)).fetchone()
        available = account is not None and not account["banned_at"]
        rel = 3 if r["accepted"] else (1 if r["asker"] == sid else 2)
        live = presence(db, other, now, lobby_ttl) if rel == 3 and available else {
            "online": 0, "addr": "", "server": "", "map": ""}
        rows.append(dict(who=accounts.who_of(other), name=accounts.game_name(account["name"]) if available else "Unavailable account",
                         relation=rel, **live))
    return sorted(rows, key=lambda r: (-r["relation"], -r["online"], r["name"].casefold(), r["who"]))


def register(app, d):
    def reply(payload, status=200):
        # FTE's URI builtin does not retain bodies on HTTP errors. A keyed game
        # action therefore carries its status INSIDE the reply, like /api/account;
        # public/unkeyed callers and ordinary HTTP tests keep normal status codes.
        key = request.form.get("key", "")
        if request.path == "/api/social/action" and request.form.get("game") == "1":
            if d.secret() and hmac.compare_digest(key, d.secret()):
                payload = dict(payload, status=status)
                status = 200
        return Response(d.game_json(dict(v=1, **payload)), status=status, mimetype="application/json")

    def auth():
        now = int(d.clock())
        key = request.form.get("key", "")
        if not d.secret() or not hmac.compare_digest(key, d.secret()):
            return now, "", reply({"ok": 0, "error": "forbidden"}, 403)
        node = d.clean_text(request.form.get("node"))
        if not node or len(node) > 128:
            return now, "", reply({"ok": 0, "error": "bad node"}, 400)
        if not d.rate_ok(request.remote_addr or "?", now, 4000, "social-lobby"):
            return now, node, reply({"ok": 0, "error": "rate limited"}, 429)
        return now, node, None

    @app.post("/api/social/poll")
    def poll():
        now, node, early = auth()
        if early is not None:
            return early
        try:
            roster = json.loads(request.form.get("roster", ""))
            if not isinstance(roster, list) or len(roster) > 64:
                raise ValueError()
            seen = set()
            for r in roster:
                if not isinstance(r, dict) or not TOKEN.fullmatch(r.get("token", "")):
                    raise ValueError()
                if r["token"] in seen:
                    raise ValueError()
                seen.add(r["token"])
                ack = r.get("ack", 0)
                if isinstance(ack, str):
                    if not re.fullmatch(r"[0-9]{1,10}", ack):
                        raise ValueError()
                    ack = int(ack)
                if type(ack) is not int or not 0 <= ack <= 2147483647:
                    raise ValueError()
                r["ack"] = ack
                if not isinstance(r.get("hash", ""), str) or len(r.get("hash", "")) > 64:
                    raise ValueError()
        except (ValueError, TypeError):
            return reply({"ok": 0, "error": "bad roster"}, 400)
        db = d.get_db()
        out = []
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM social_messages WHERE sent<?", (now - MESSAGE_TTL,))
                db.execute("DELETE FROM social_sessions WHERE issued<?", (now - SESSION_TTL,))
                # Full-node snapshot. Tokens of disconnected slots cannot keep presence alive.
                db.execute("UPDATE social_sessions SET seen=0 WHERE node=?", (node,))
                for r in roster:
                    s = session(db, r["token"], node, now)
                    if s is not None:
                        db.execute("UPDATE social_sessions SET seen=?,ack=MAX(ack,?) WHERE token=?",
                                   (now, r.get("ack", 0), s["token"]))
                for r in roster:
                    s = session(db, r["token"], node, now)
                    if s is None:
                        out.append({"token": r["token"], "invalid": 1})
                        continue
                    sid = s["steamid"]
                    friends = friend_rows(db, sid, now, d.lobby_ttl)
                    body = json.dumps(friends, ensure_ascii=False, separators=(",", ":"))
                    revision = hashlib.sha256(body.encode("utf-8")).hexdigest()
                    messages = []
                    for m in db.execute(
                            "SELECT m.* FROM social_messages m JOIN accounts a ON a.steamid=m.sender"
                            " JOIN social_friends f ON ((f.lo=m.sender AND f.hi=m.recipient) OR"
                            " (f.hi=m.sender AND f.lo=m.recipient))"
                            " WHERE m.recipient=? AND m.id>? AND a.banned_at=0 AND f.accepted=1"
                            " ORDER BY m.id LIMIT 2", (sid, s["ack"])):
                        if relation(db, sid, m["sender"]) != 3:
                            continue
                        sender = db.execute("SELECT name,banned_at FROM accounts WHERE steamid=?",
                                            (m["sender"],)).fetchone()
                        if sender and not sender["banned_at"]:
                            messages.append(dict(id=str(m["id"]), who=accounts.who_of(m["sender"]),
                                                 name=accounts.game_name(sender["name"]), text=m["body"]))
                    row = dict(token=r["token"], hash=revision, messages=messages)
                    if r.get("hash", "") != revision:
                        row["friends"] = friends
                    out.append(row)
        except sqlite3.Error:
            return reply({"ok": 0, "error": "friends unavailable"}, 503)
        return reply({"ok": 1, "players": out})

    @app.post("/api/social/action")
    def action():
        now, node, early = auth()
        if early is not None:
            return early
        db = d.get_db()
        token = request.form.get("token", "")
        op = request.form.get("op", "")
        if op not in ("add", "accept", "remove", "message", "join"):
            return reply({"ok": 0, "error": "bad action"}, 400)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                s = session(db, token, node, now)
                if s is None:
                    return reply({"ok": 0, "error": "Link Steam on this lobby first"}, 403)
                sid = s["steamid"]
                if not d.rate_ok(sid, now, 20, "social-action"):
                    return reply({"ok": 0, "error": "Slow down; try again shortly"}, 429)
                other = resolve(db, request.form.get("who", ""), sid if op == "remove" else None)
                if not other or other == sid:
                    return reply({"ok": 0, "error": "That Steam account is unavailable"}, 400)
                rel = relation(db, sid, other)
                lo, hi = pair(sid, other)
                if op == "add":
                    if rel:
                        return reply({"ok": 0, "error": "A request or friendship already exists"}, 409)
                    for who in (sid, other):
                        n = db.execute("SELECT COUNT(*) FROM social_friends WHERE lo=? OR hi=?",
                                       (who, who)).fetchone()[0]
                        if n >= MAX_FRIENDS:
                            return reply({"ok": 0, "error": "Friends list is full"}, 409)
                    db.execute("INSERT INTO social_friends(lo,hi,asker) VALUES(?,?,?)", (lo, hi, sid))
                    note = "Friend request sent"
                elif op == "accept":
                    if rel != 2:
                        return reply({"ok": 0, "error": "No incoming request"}, 409)
                    db.execute("UPDATE social_friends SET accepted=1 WHERE lo=? AND hi=?", (lo, hi))
                    note = "Friend request accepted"
                elif op == "remove":
                    db.execute("DELETE FROM social_friends WHERE lo=? AND hi=?", (lo, hi))
                    db.execute("DELETE FROM social_messages WHERE (sender=? AND recipient=?) OR"
                               " (sender=? AND recipient=?)", (sid, other, other, sid))
                    note = "Friend / request removed"
                else:
                    if rel != 3:
                        return reply({"ok": 0, "error": "Accept the friend request first"}, 403)
                    live = presence(db, other, now, d.lobby_ttl)
                    if not live["online"]:
                        return reply({"ok": 0, "error": "Your friend is offline"}, 409)
                    if op == "join":
                        return reply({"ok": 1, "addr": live["addr"], "note": "Joining friend"})
                    text = request.form.get("text", "").strip()
                    if not text or len(text) > 160 or len(text.encode("utf-8")) > 320 or any(
                            ord(c) < 32 or ord(c) == 127 for c in text):
                        return reply({"ok": 0, "error": "Use 1-160 characters on one line"}, 400)
                    db.execute("DELETE FROM social_messages WHERE sent<?", (now - MESSAGE_TTL,))
                    if db.execute("SELECT COUNT(*) FROM social_messages WHERE recipient=?",
                                  (other,)).fetchone()[0] >= 32:
                        return reply({"ok": 0, "error": "Your friend's inbox is busy"}, 429)
                    if db.execute("SELECT COUNT(*) FROM social_messages").fetchone()[0] >= 2048:
                        return reply({"ok": 0, "error": "Private chat is busy"}, 429)
                    serial = db.execute("SELECT seq FROM sqlite_sequence WHERE name='social_messages'").fetchone()
                    if serial and serial[0] >= 2147483647:
                        return reply({"ok": 0, "error": "Private chat is busy"}, 429)
                    db.execute("INSERT INTO social_messages(sender,recipient,body,sent) VALUES(?,?,?,?)",
                               (sid, other, text, now))
                    note = "Private message sent"
        except sqlite3.Error:
            return reply({"ok": 0, "error": "Friends unavailable"}, 503)
        return reply({"ok": 1, "note": note})
