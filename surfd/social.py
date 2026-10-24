"""Steam-account friendships and lobby-mediated presence/private chat.

Lobby capabilities are minted only by accounts.register's VERIFIED proof path
and stay on the lobby. Menu proofs use a separate fixed signature domain;
message proofs additionally bind recipient and exact UTF-8 body hash. Every use rechecks the
key link and ban, and binds the capability to that lobby's node. Presence and
join addresses are never supplied by clients. Messages are operator-readable,
not E2E encrypted, and are bounded/expired (not logged).
"""
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import re
import secrets
import sqlite3
from flask import Response, request
import accounts
import viewmodel

MAX_FRIENDS = 128
PRESENCE_TTL = 16
SESSION_TTL = 86400
MESSAGE_TTL = 120
TOKEN = re.compile(r"[0-9a-f]{64}\Z")
MARK = re.compile(r"[0-9a-f]{8}(?:[0-9a-f]{4})?\Z")
MENU_NONCE = re.compile(r"[0-9a-f]{32}\Z")
MENU_SIG = re.compile(r"[0-9a-f]{128}\Z")
MENU_EXP = re.compile(r"[0-9]{10}\Z")
MENU_TTL = 30
MENU_PRESENCE_TTL = 35
MENU_CHAT_SQL = """
CREATE TABLE IF NOT EXISTS social_menu_messages (
 proof TEXT PRIMARY KEY, until INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS social_menu_messages_until ON social_menu_messages(until);
"""
CHAT_ROOM = "@menu"
CHAT_TARGET = re.compile(r"(?:-|[0-9a-f]{8}):[0-9a-f]{64}\Z")
MENU_PRESENCE_SQL = """
CREATE TABLE IF NOT EXISTS social_menu_presence (
 pub TEXT PRIMARY KEY, steamid TEXT NOT NULL, seen INTEGER NOT NULL,
 challenge_until INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS social_menu_presence_seen ON social_menu_presence(seen);
CREATE INDEX IF NOT EXISTS social_menu_presence_account ON social_menu_presence(steamid);
"""
MENU_STATEMENT = "FTESURF-FRIENDS 1\nserver play.proto.bar:443\nnonce %s\nop %s\nwho %s\n"


def menu_target(op, who):
    return ((op in ("list", "presence", "chat") and who == "-")
            or (op == "join" and len(who) == 8 and bool(MARK.fullmatch(who)))
            or (op == "message" and bool(CHAT_TARGET.fullmatch(who))))
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


# Activity is volatile presence, not run history or a schema migration. A worker
# without this poll's sample shows no stage, never a guessed/stale one. The lobby
# refreshes every five seconds; SQL remains the authority for online/visibility.
_activities = {}  # session digest -> (SQL seen, lobby map, bounded label)
_ACTIVITY_MAX = 16384  # more than the directory's 200 nodes x 64 players


def remember_activity(token, seen, label, mapname=""):
    _activities.pop(token, None)
    if len(_activities) >= _ACTIVITY_MAX:
        _activities.pop(next(iter(_activities)))
    _activities[token] = (seen, mapname, label)


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


def rel_of(row, me):
    # P788: accepted 0 is a one-way add -- 1 I added them, 2 they added me -- until
    # the other adds back (3, friends). P770 blocks: accepted -1 is the asker's
    # block, -2 both sides'. 4 blocked by me, 5 by them only.
    if row["accepted"] == -2:
        return 4
    if row["accepted"] < 0:
        return 4 if row["asker"] == me else 5
    return 3 if row["accepted"] else (1 if row["asker"] == me else 2)


def slots(db, who):
    # Another account's block of `who`, or add that `who` has not returned, was
    # not `who`'s choice, so it takes no slot.
    return db.execute("SELECT COUNT(*) FROM social_friends WHERE (lo=? OR hi=?)"
                      " AND NOT (accepted IN (-1,0) AND asker<>?)", (who, who, who)).fetchone()[0]


def relation(db, a, b):
    row = db.execute("SELECT asker,accepted FROM social_friends WHERE lo=? AND hi=?",
                     pair(a, b)).fetchone()
    return rel_of(row, a) if row else 0


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
        "SELECT l.addr,l.name,l.map,s.token,s.seen FROM social_sessions s"
        " JOIN keylinks k ON k.pub=s.pub AND k.steamid=s.steamid"
        " JOIN accounts a ON a.steamid=s.steamid JOIN lobbies l ON l.node=s.node"
        " WHERE s.steamid=? AND s.seen>? AND s.issued>? AND a.banned_at=0"
        " AND l.last_seen>? ORDER BY s.seen DESC,s.node LIMIT 1",
        (sid, now - PRESENCE_TTL, now - SESSION_TTL, now - lobby_ttl)).fetchone()
    if not row:
        menu = db.execute(
            "SELECT 1 FROM social_menu_presence m JOIN keylinks k ON k.pub=m.pub"
            " JOIN accounts a ON a.steamid=k.steamid"
            " WHERE m.steamid=? AND k.steamid=m.steamid AND a.banned_at=0"
            " AND m.seen>? AND m.seen<=? LIMIT 1",
            (sid, now - MENU_PRESENCE_TTL, now)).fetchone()
        return {"online": 0, "menu_online": int(menu is not None), "addr": "", "server": "", "map": "", "activity": ""}
    sample = _activities.get(row["token"])
    activity = sample[2] if sample and sample[0] == row["seen"] and sample[1] == row["map"] else ""
    return {"online": 1, "menu_online": 0, "addr": row["addr"], "server": row["name"], "map": row["map"],
            "activity": activity}


def friend_rows(db, sid, now, lobby_ttl):
    rows = []
    for r in db.execute("SELECT lo,hi,asker,accepted FROM social_friends WHERE lo=? OR hi=?",
                        (sid, sid)):
        other = r["hi"] if r["lo"] == sid else r["lo"]
        account = db.execute("SELECT name,banned_at FROM accounts WHERE steamid=?", (other,)).fetchone()
        available = account is not None and not account["banned_at"]
        rel = rel_of(r, sid)
        if rel == 5:
            continue                # being blocked is not shown
        if rel == 2 and not available:
            continue                # P788: a banned or deleted account's add is not offered
        # P788: presence is for friendships only -- an add I have not returned
        # must not let its author watch where I play.
        live = presence(db, other, now, lobby_ttl) if rel == 3 and available else {
            "online": 0, "menu_online": 0, "addr": "", "server": "", "map": "", "activity": ""}
        rows.append(dict(who=accounts.who_of(other), name=accounts.game_name(account["name"]) if available else "Unavailable account",
                         relation=rel, **live))
    # Incoming adds last ("at the bottom", Lex). They take no slot, so the list
    # is cut at the 128 rows a reader takes; only incoming adds are ever cut.
    group = {3: 0, 1: 0, 4: 1, 2: 2}
    rows.sort(key=lambda r: (group[r["relation"]], -r["online"], r["name"].casefold(), r["who"]))
    return rows[:MAX_FRIENDS]


def befriend(db, sid, other):
    """P788's add: one-way until the other account adds back. (ok, note|error, status)."""
    rel = relation(db, sid, other)
    lo, hi = pair(sid, other)
    if rel == 3:
        return 0, "You are already friends", 409
    if rel == 1:
        return 0, "You already added them", 409
    if rel == 4:
        return 0, "Unblock them first", 409
    if rel == 5:
        return 0, "Could not add that player", 409
    if slots(db, sid) >= MAX_FRIENDS:
        return 0, "Friends list is full", 409
    if rel == 2:
        db.execute("UPDATE social_friends SET accepted=1 WHERE lo=? AND hi=?", (lo, hi))
        return 1, "Friend added back", 200
    db.execute("INSERT INTO social_friends(lo,hi,asker,accepted) VALUES(?,?,?,0)", (lo, hi, sid))
    return 1, "Friend added", 200


def chat_snapshot(db, sid, now, lobby_ttl):
    """Bounded recent text only; neither Steam IDs nor other people's inboxes."""
    room, messages = [], []
    rows = db.execute("SELECT m.*,a.name FROM social_messages m JOIN accounts a ON a.steamid=m.sender"
                      " WHERE a.banned_at=0 AND m.sent>=?"
                      " AND (m.recipient=? OR m.sender=? OR m.recipient=?)"
                      " ORDER BY m.id DESC LIMIT 256", (now - MESSAGE_TTL, CHAT_ROOM, sid, sid))
    for row in rows:
        public = row["recipient"] == CHAT_ROOM
        other = row["sender"] if row["recipient"] == sid else row["recipient"]
        if public:
            if len(room) >= 24 or relation(db, sid, row["sender"]) in (4, 5):
                continue
        elif len(messages) >= 32 or relation(db, sid, other) != 3:
            continue
        item = dict(id=str(row["id"]), who=accounts.who_of(row["sender"]),
                    name=accounts.game_name(row["name"]), text=row["body"], sent=row["sent"])
        if public:
            room.append(item)
        else:
            item["peer"] = accounts.who_of(other)
            messages.append(item)
    return dict(ok=1, me=accounts.who_of(sid), room=list(reversed(room)),
                messages=list(reversed(messages)),
                friends=[r for r in friend_rows(db, sid, now, lobby_ttl) if r["relation"] == 3])


def menu_message(db, sid, nonce, expires, target, text, now, lobby_ttl):
    """Called under BEGIN IMMEDIATE: consume and insert atomically across workers."""
    peer, _, body_sha = target.partition(":")
    if not hmac.compare_digest(hashlib.sha256(text.encode("utf-8")).hexdigest(), body_sha):
        return {"ok": 0, "error": "Message changed; send again"}, 400
    text = text.strip()
    if not text or len(text) > 160 or len(text.encode("utf-8")) > 320 or any(
            ord(c) < 32 or ord(c) == 127 for c in text):
        return {"ok": 0, "error": "Use 1-160 characters on one line"}, 400
    other = CHAT_ROOM if peer == "-" else resolve(db, peer)
    if other != CHAT_ROOM:
        if not other or other == sid or relation(db, sid, other) != 3:
            return {"ok": 0, "error": "Add each other as friends first"}, 403
        live = presence(db, other, now, lobby_ttl)
        if not live["online"] and not live["menu_online"]:
            return {"ok": 0, "error": "Your friend is offline"}, 409
    db.execute("DELETE FROM social_menu_messages WHERE until<?", (now,))
    proof = digest(sid + "\n" + nonce)
    if db.execute("SELECT 1 FROM social_menu_messages WHERE proof=?", (proof,)).fetchone():
        return {"ok": 0, "error": "Message already sent"}, 409
    db.execute("DELETE FROM social_messages WHERE sent<?", (now - MESSAGE_TTL,))
    if other != CHAT_ROOM and db.execute("SELECT COUNT(*) FROM social_messages WHERE recipient=?",
                                        (other,)).fetchone()[0] >= 32:
        return {"ok": 0, "error": "Your friend's inbox is busy"}, 429
    if db.execute("SELECT COUNT(*) FROM social_messages").fetchone()[0] >= 2048:
        return {"ok": 0, "error": "Chat is busy"}, 429
    serial = db.execute("SELECT seq FROM sqlite_sequence WHERE name='social_messages'").fetchone()
    if serial and serial[0] >= 2147483647:
        return {"ok": 0, "error": "Chat is busy"}, 429
    db.execute("INSERT INTO social_menu_messages(proof,until) VALUES(?,?)", (proof, int(expires)))
    row = db.execute("INSERT INTO social_messages(sender,recipient,body,sent) VALUES(?,?,?,?)",
                     (sid, other, text, now))
    if other == CHAT_ROOM:
        db.execute("DELETE FROM social_messages WHERE recipient=? AND id NOT IN"
                   " (SELECT id FROM social_messages WHERE recipient=? ORDER BY id DESC LIMIT 128)",
                   (CHAT_ROOM, CHAT_ROOM))
    return {"ok": 1, "id": str(row.lastrowid), "note": "Message sent"}, 200


def register(app, d):
    # The same verifier as account proofs, not a new Ed25519 implementation.
    try:
        tools = d.setting("SURFD_TOOLS") or str(Path(d.setting("SURFD_GAME") or "/srv/nvme/ftesurf-server/game") / "tools")
        spec = importlib.util.spec_from_file_location("social_ed25519", Path(tools) / "ed25519.py")
        ed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ed)
    except (OSError, ImportError, AttributeError):
        ed = None

    def reply(payload, status=200):
        # FTE's URI builtin does not retain bodies on HTTP errors. A keyed game
        # action therefore carries its status INSIDE the reply, like /api/account;
        # public/unkeyed callers and ordinary HTTP tests keep normal status codes.
        key = request.form.get("key", "")
        if request.path in ("/api/social/action", "/api/social/viewmodel") and request.form.get("game") == "1":
            if d.secret() and hmac.compare_digest(key, d.secret()):
                payload = dict(payload, status=status)
                status = 200
        if request.path.startswith("/api/social/menu"):
            # URI callbacks discard non-2xx bodies. Keep refusal details without
            # granting authority: ok=0/status still denote a failed request.
            payload = dict(payload, status=status)
            status = 200
        response = Response(d.game_json(dict(v=1, **payload)), status=status, mimetype="application/json")
        response.headers["Cache-Control"] = "no-store"
        return response

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

    def menu_ticket(nonce, op, who, expires, peer):
        secret = d.secret()
        if not secret:
            return ""
        msg = json.dumps(["friends-menu-v1", nonce, op, who, expires, peer], separators=(",", ":"))
        return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    @app.get("/api/social/menu/challenge")
    def menu_challenge():
        now = int(d.clock())
        peer = d.rate_key()
        op, who = request.args.get("op", ""), request.args.get("who", "")
        budget = "social-menu-presence-challenge" if op == "presence" else "social-menu-challenge"
        if not d.rate_ok(peer, now, 30, budget):
            return reply({"ok": 0, "error": "Friends: try again shortly"}, 429)
        if not menu_target(op, who):
            return reply({"ok": 0, "error": "Bad Friends action"}, 400)
        nonce, expires = secrets.token_hex(16), str(now + MENU_TTL)
        ticket = menu_ticket(nonce, op, who, expires, peer)
        if not ed or not ticket:
            return reply({"ok": 0, "error": "Friends unavailable"}, 503)
        return reply(dict(ok=1, nonce=nonce, expires=expires, ticket=ticket))

    @app.post("/api/social/menu")
    def menu_read():
        now = int(d.clock())
        peer = d.rate_key()
        f = request.form
        op, who = f.get("op", ""), f.get("who", "")
        budget = "social-menu-presence-read" if op == "presence" else "social-menu-read"
        if not d.rate_ok(peer, now, 30, budget):
            return reply({"ok": 0, "error": "Friends: try again shortly"}, 429)
        nonce, expires, ticket = f.get("nonce", ""), f.get("expires", ""), f.get("ticket", "")
        pub, sig = f.get("pub", ""), f.get("sig", "")
        if not (menu_target(op, who) and MENU_NONCE.fullmatch(nonce) and
                MENU_EXP.fullmatch(expires) and TOKEN.fullmatch(ticket) and
                TOKEN.fullmatch(pub) and MENU_SIG.fullmatch(sig)):
            return reply({"ok": 0, "error": "Bad Friends proof"}, 400)
        expected = menu_ticket(nonce, op, who, expires, peer)
        if not expected or not now <= int(expires) <= now + MENU_TTL or not hmac.compare_digest(ticket, expected):
            return reply({"ok": 0, "error": "Friends request expired; try again"}, 403)
        if not ed:
            return reply({"ok": 0, "error": "Friends unavailable"}, 503)
        if not d.rate_ok("all", now, 240, "social-menu-verify"):
            return reply({"ok": 0, "error": "Friends busy; try again shortly"}, 503)
        msg = (MENU_STATEMENT % (nonce, op, who)).encode("ascii")
        if not ed.verify(bytes.fromhex(pub), msg, bytes.fromhex(sig)):
            return reply({"ok": 0, "error": "Friends identity could not be verified"}, 403)
        if op == "list" and f.get("story") == "1" and getattr(d, "story_who", None):
            # P854: the Story screen asks who this key plays as, on the same
            # read-only proof; an unlinked install answers too.
            try:
                return reply({"ok": 1, "who": d.story_who(d.get_db(), pub)})
            except sqlite3.Error:
                return reply({"ok": 0, "error": "Story unavailable"}, 503)
        try:
            db = d.get_db()
            # A menu heartbeat is not a lobby session/capability or join target.
            with db:
                db.execute("BEGIN IMMEDIATE" if op in ("presence", "message") else "BEGIN")
                account = db.execute("SELECT k.steamid FROM keylinks k JOIN accounts a USING(steamid)"
                                     " WHERE k.pub=? AND a.banned_at=0", (pub,)).fetchone()
                if not account:
                    return reply({"ok": 0, "error": "Link Steam on a lobby once to use Friends here"}, 403)
                sid = account["steamid"]
                budget = "social-menu-presence-account" if op == "presence" else "social-menu-account"
                if not d.rate_ok(sid, now, 20, budget):
                    return reply({"ok": 0, "error": "Friends: try again shortly"}, 429)
                if op == "presence":
                    # SQL-backed across workers; an old/same challenge cannot renew.
                    db.execute("DELETE FROM social_menu_presence WHERE seen<=?", (now - MENU_PRESENCE_TTL,))
                    db.execute(
                        "INSERT INTO social_menu_presence(pub,steamid,seen,challenge_until) VALUES(?,?,?,?)"
                        " ON CONFLICT(pub) DO UPDATE SET steamid=excluded.steamid,seen=excluded.seen,"
                        " challenge_until=excluded.challenge_until"
                        " WHERE excluded.challenge_until>social_menu_presence.challenge_until",
                        (pub, sid, now, int(expires)))
                    return reply({"ok": 1})
                if op == "list":
                    # Menus before P770 refuse a list holding relation 4.
                    rows = [r for r in friend_rows(db, sid, now, d.lobby_ttl) if r["relation"] <= 3]
                    return reply({"ok": 1, "friends": rows})
                if op == "chat":
                    return reply(chat_snapshot(db, sid, now, d.lobby_ttl))
                if op == "message":
                    if not d.rate_ok(sid, now, 20, "social-action"):
                        return reply({"ok": 0, "error": "Slow down; try again shortly"}, 429)
                    body, status = menu_message(db, sid, nonce, expires, who,
                                                f.get("text", ""), now, d.lobby_ttl)
                    return reply(body, status)
                other = resolve(db, who)
                if not other or relation(db, sid, other) != 3:
                    return reply({"ok": 0, "error": "Add them as a friend first"}, 403)
                live = presence(db, other, now, d.lobby_ttl)
                if not live["online"]:
                    why = "Your friend is at the main menu" if live["menu_online"] else "Your friend is offline"
                    return reply({"ok": 0, "error": why}, 409)
                return reply({"ok": 1, "addr": live["addr"], "map": live["map"]})
        except sqlite3.Error:
            return reply({"ok": 0, "error": "Friends unavailable"}, 503)

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
                activity = r.get("activity", "")
                if not isinstance(activity, str):
                    raise ValueError()
                if activity and not re.fullmatch(r"(?:Stage|Bonus) [1-9][0-9]{0,2}|Spectating", activity):
                    raise ValueError()
                if not isinstance(r.get("hash", ""), str) or len(r.get("hash", "")) > 64:
                    raise ValueError()
        except (ValueError, TypeError):
            return reply({"ok": 0, "error": "bad roster"}, 400)
        db = d.get_db()
        out = []
        updated = set()
        for token, sample in list(_activities.items()):
            if not now - PRESENCE_TTL < sample[0] <= now:
                _activities.pop(token, None)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                location = db.execute("SELECT map FROM lobbies WHERE node=?", (node,)).fetchone()
                mapname = location[0] if location else ""
                db.execute("DELETE FROM social_messages WHERE sent<?", (now - MESSAGE_TTL,))
                db.execute("DELETE FROM social_sessions WHERE issued<?", (now - SESSION_TTL,))
                db.execute("DELETE FROM social_menu_presence WHERE seen<=?", (now - MENU_PRESENCE_TTL,))
                # Full-node snapshot. Tokens of disconnected slots cannot keep presence alive.
                db.execute("UPDATE social_sessions SET seen=0 WHERE node=?", (node,))
                for r in roster:
                    s = session(db, r["token"], node, now)
                    if s is not None:
                        db.execute("UPDATE social_sessions SET seen=?,ack=MAX(ack,?) WHERE token=?",
                                   (now, r.get("ack", 0), s["token"]))
                        remember_activity(s["token"], now, r.get("activity", ""), mapname)
                        updated.add(s["token"])
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
            # A rolled-back SQL poll cannot leave an acted activity sample.
            for token in updated:
                _activities.pop(token, None)
            return reply({"ok": 0, "error": "friends unavailable"}, 503)
        return reply({"ok": 1, "players": out})

    @app.post("/api/social/viewmodel")
    def viewmodel_settings():
        now, node, early = auth()
        if early is not None:
            return early
        op = request.form.get("op", "")
        if op not in ("get", "set"):
            return reply({"viewmodel": 1, "ok": 0, "error": "Bad setup action"}, 400)
        token = request.form.get("token", "")
        db = d.get_db()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                owner = session(db, token, node, now)
                if owner is None:
                    return reply({"viewmodel": 1, "ok": 0, "error": "Link Steam on this lobby first"}, 403)
                if not d.rate_ok(owner["steamid"], now, 120, "viewmodel-settings"):
                    return reply({"viewmodel": 1, "ok": 0, "error": "Setup is busy; try shortly"}, 429)
                if op == "get":
                    value = viewmodel.load(db, owner["steamid"])
                else:
                    revision = request.form.get("revision", "")
                    if not re.fullmatch(r"[0-9]{1,10}", revision, re.ASCII):
                        raise ValueError("Invalid setup revision")
                    value = viewmodel.save(db, owner["steamid"], request.form.get("setup", ""),
                                           int(revision), now)
                    if value is None:
                        return reply({"viewmodel": 1, "ok": 0, "error": "Setup changed on another connection; reload before saving"}, 409)
        except ValueError as error:
            return reply({"viewmodel": 1, "ok": 0, "error": str(error)}, 400)
        except sqlite3.Error:
            return reply({"viewmodel": 1, "ok": 0, "error": "Account setup unavailable"}, 503)
        return reply(dict(viewmodel=1, ok=1, **value))

    @app.post("/api/social/action")
    def action():
        now, node, early = auth()
        if early is not None:
            return early
        db = d.get_db()
        token = request.form.get("token", "")
        op = request.form.get("op", "")
        if op not in ("add", "accept", "remove", "message", "join", "block", "unblock"):
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
                other = resolve(db, request.form.get("who", ""), sid if op in ("remove", "unblock") else None)
                if not other or other == sid:
                    return reply({"ok": 0, "error": "That Steam account is unavailable"}, 400)
                rel = relation(db, sid, other)
                lo, hi = pair(sid, other)
                asked = op
                if op == "remove" and rel in (4, 5):
                    op = "unblock"          # only my own block is mine to lift
                if op == "add" or (op == "accept" and rel == 2):
                    ok, note, status = befriend(db, sid, other)
                    if not ok:
                        return reply({"ok": 0, "error": note}, status)
                elif op == "accept":
                    return reply({"ok": 0, "error": "They have not added you"}, 409)
                elif op == "remove":
                    db.execute("DELETE FROM social_friends WHERE lo=? AND hi=?", (lo, hi))
                    db.execute("DELETE FROM social_messages WHERE (sender=? AND recipient=?) OR"
                               " (sender=? AND recipient=?)", (sid, other, other, sid))
                    note = "Friend / request removed"
                elif op == "block":
                    # Block is how an account refuses another: it ends a
                    # friendship or an add and refuses their adds and messages.
                    # Their block does not stand in for mine: they could lift it.
                    if rel == 5:
                        if slots(db, sid) >= MAX_FRIENDS:
                            return reply({"ok": 0, "error": "Friends list is full"}, 409)
                        db.execute("UPDATE social_friends SET accepted=-2 WHERE lo=? AND hi=?", (lo, hi))
                    elif rel in (1, 2, 3):
                        # Their add took none of my slots; my block of it takes one.
                        if rel == 2 and slots(db, sid) >= MAX_FRIENDS:
                            return reply({"ok": 0, "error": "Friends list is full"}, 409)
                        db.execute("UPDATE social_friends SET asker=?,accepted=-1 WHERE lo=? AND hi=?",
                                   (sid, lo, hi))
                    elif rel == 0:
                        if slots(db, sid) >= MAX_FRIENDS:
                            return reply({"ok": 0, "error": "Friends list is full"}, 409)
                        db.execute("INSERT INTO social_friends(lo,hi,asker,accepted) VALUES(?,?,?,-1)",
                                   (lo, hi, sid))
                    db.execute("DELETE FROM social_messages WHERE (sender=? AND recipient=?) OR"
                               " (sender=? AND recipient=?)", (sid, other, other, sid))
                    note = "Blocked: they cannot add or message you"
                elif op == "unblock":
                    if rel == 5 and asked == "remove":
                        note = "Friend / request removed"
                    elif rel != 4:
                        return reply({"ok": 0, "error": "Not blocked"}, 409)
                    else:
                        both = db.execute("SELECT accepted FROM social_friends WHERE lo=? AND hi=?",
                                          (lo, hi)).fetchone()["accepted"] == -2
                        if both:            # theirs stays
                            db.execute("UPDATE social_friends SET asker=?,accepted=-1 WHERE lo=? AND hi=?",
                                       (other, lo, hi))
                        else:
                            db.execute("DELETE FROM social_friends WHERE lo=? AND hi=?", (lo, hi))
                        note = "Unblocked"
                else:
                    if rel == 1:            # P788: a join or message waits for theirs
                        return reply({"ok": 0, "error": "They have not added you back yet"}, 403)
                    if rel != 3:
                        return reply({"ok": 0, "error": "Add them as a friend first"}, 403)
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
