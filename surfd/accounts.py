#!/usr/bin/env python3
"""
accounts.py -- Steam accounts for surfd (schema 13).

STORE-ONLY: nothing that ranks, verifies or publishes a run reads these tables.

  accounts    one row per SteamID64 that has signed in, or been banned
  linkkeys    an install's signing key -> account; one account, many installs
  linkcodes   what a sign-in hands the player to type into the game
  linknonces  every Steam assertion seen once, so none is used twice

AN INSTALL IS ITS KEY, NOT ITS GUID.  The engine guid is handed to any server
that sends the fleet's sv_guidkey, so a link keyed on it could be moved, or
squatted before its owner ever linked, by whoever harvested one.  Every lobby
call carries a signature by the install's `fskey` over rec_sign's statement
(cl_receipt.c), which names the server the CLIENT is talking to: it must be an
address of ours, on the asking lobby's port, or a signature made on somebody
else's server would do.

THREE THINGS ARE SIGNED AND NONE CAN STAND IN FOR ANOTHER.  The statement's
`ticks` says which: -2 a connect (the lobby's nonce), -3 asking to link (a
digest of the code), -4 confirming it (a digest of the code AND the number the
lobby showed the player).  No run signs a negative below -1, and the game
server's receipt handler refuses them, so none can be filed as a run's either.

LINKING IS ASK, THEN CONFIRM.  Asking proves a key for a code and CLAIMS the
code for that key: nobody else can use it after.  The lobby then shows the
account's name and a number of ITS choosing, and confirming signs that number;
surfd never sees the number except under the signature.  Text a server the
player has LEFT put in the client (a delayed command, a bind) can ask; it
cannot read the number.

WHAT THAT DOES NOT COVER, and why nothing may rank on a link yet (ROADMAP 14.3
has the gate).  Whoever can write to the client's connection as well as read it
has both commands signed like typed ones.  The lobby is sent a digest of the
code and never the code, but a code is 40 bits and a digest can be searched:
what keeps a code is the claim, made by the same packet that exposes the
digest.  And a code is a bearer token until somebody asks with it: typed into
a game whose server is not ours, it is that server's.

The page says to keep a code private and lists what is linked, with a way to
unlink.  A ban never pins an install to the banned account -- that would let
one player link a victim's install to a throwaway account, get it banned, and
lock the victim out.

The sign-in pages are registered only when SURFD_BOARD_URL is set; the two
lobby routes need the shared key AND a trusted source.

No module state: tests reload surfd many times in one process and this module
is not reloaded with it.  Everything configured lives in register()'s closure.
"""

import hashlib
import hmac
import html
import ipaddress
import os
import re
import secrets
import socket
import sqlite3
import sys
import threading
import time
import unicodedata
import urllib.parse

from flask import Response, redirect, request

import steam

SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    steamid    TEXT    PRIMARY KEY,
    name       TEXT    NOT NULL DEFAULT '',
    avatar     TEXT    NOT NULL DEFAULT '',
    seen_at    INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    banned_at  INTEGER NOT NULL DEFAULT 0,
    ban_note   TEXT    NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS linkcodes (
    code      TEXT    PRIMARY KEY,
    steamid   TEXT    NOT NULL,
    issued_at INTEGER NOT NULL,
    used_at   INTEGER NOT NULL DEFAULT 0,
    used_by   TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS linkcodes_steamid ON linkcodes (steamid, used_at);
CREATE TABLE IF NOT EXISTS linknonces (
    nonce   TEXT    PRIMARY KEY,
    seen_at INTEGER NOT NULL
);
"""

# SQL IS STEP 12 AND NO LONGER MAKES `links`, the guid-keyed table 13 drops.
# While it did, a process still in this script could reach `CREATE INDEX ... ON
# links` just after another had finished 13: "no such table: main.links".  The
# Pi's two-thread arm met it (test_board.py); this box's never had.

# Schema 13 (upgrade_13): a link is keyed on the install's key, and a code
# remembers which key asked for it first (`linkcodes.claim`, added there).
SQL_KEYS = """
CREATE TABLE IF NOT EXISTS linkkeys (
    pub       TEXT    PRIMARY KEY,
    steamid   TEXT    NOT NULL,
    player    TEXT    NOT NULL DEFAULT '',
    node      TEXT    NOT NULL DEFAULT '',
    linked_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS linkkeys_steamid ON linkkeys (steamid);
"""

CODE_TTL = 600           # s a code can be redeemed for
CODE_KEEP = 86400        # s a spent or superseded code's row is kept
CODE_LIVE_MAX = 500      # unredeemed codes outstanding; past it sign-in waits
CODE_LEN = 8
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"    # no I O 0 1
SUPERSEDED = "superseded"
# A nonce may be dated NONCE_SKEW ahead and is stale NONCE_SKEW after its date,
# so a row matters for twice that.  Short on purpose: it is how long a flood of
# made-up replies can keep the table full.
NONCE_KEEP = 2 * steam.NONCE_SKEW + 60
NONCE_MAX = 20000        # rows; past it sign-in waits
NONCE_STRAY = NONCE_MAX // 2    # replies from the wrong browser are recorded below this

WEB_RATE_MAX = 10        # sign-in page hits per window per source
OUT_RATE_MAX = 30        # confirmations asked of Steam per window, everyone
OUT_SOURCE_MAX = 3       # ...and per source, so one address cannot spend them all
OUT_ATONCE = 2           # ...and in flight at once: gunicorn has four threads
# Every lobby posts from one address, so a per-source limit is the whole fleet's.
# The per-player limits are keyed on the client address the LOBBY reports: a guid
# is whatever the client says it is, and one player could spend another's.
ACCT_RATE_MAX = 2400     # /api/account calls per window per source, before the key is read
ACCT_PEER_MAX = 12       # ...and per client address
LINK_FLOOD_MAX = 2400    # /api/link calls per window per source, before the key is read
LINK_RATE_MAX = 600      # ...and link steps, after the per-address limit
TRY_RATE_MAX = 8         # link steps per window per client address (a link is two)
# Those two are also all the signatures one address can have checked: 20 a window.
HELLO_VERIFY_MAX = 480   # signatures checked per window for everyone: connects
LINK_VERIFY_MAX = 240    # ...and links, a budget connects cannot spend
HOSTS_TTL = 300          # s a lookup of the public host is reused
HOSTS_RETRY = 30         # s before a failed lookup is tried again
HOSTS_STALE = 86400      # s an old answer is believed while lookups fail
UNLINK_TTL = 600         # s an unlink link on the sign-in page works for

# What an install signs: rec_sign's statement (cl_receipt.c, RCPT_VERSION and
# its five lines) with no evidence.  `ticks` is the kind; see the header.
STATEMENT = "FTESURF-RCPT 1\nserver %s\nnonce %s\nticks %d\nhid - 0 0\nview -\n"
TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM = -2, -3, -4
TAG_CODE = "ftesurf-code "          # the code as it crosses the wire
TAG_ASK = "ftesurf-link "           # ...as asking signs it
TAG_CONFIRM = "ftesurf-confirm "    # ...and confirming, with the number

_STATE = re.compile(r"[0-9a-f]{32}")
_URL_OK = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX128 = re.compile(r"[0-9a-f]{128}")
_SERVER = re.compile(r"[\x21-\x7e]{3,128}")
_UNLINK = re.compile(r"(ask|do)\.([0-9]{10})\.([0-9]{17})\.([0-9a-f]{16})\.([0-9a-f]{32})")
_PIN = re.compile(r"[0-9]{6}")
# A persona becomes a Quake name, so it is built from an ALLOWLIST: letters,
# digits and this punctuation.  Everything the engine or the mod reads as
# markup is outside it -- ^ and & (colour, links), \ " ; $ % (infostrings and
# command lines), : (the engine strips it), private-use glyphs, bidi and
# zero-width controls.
_NAME_PUNCT = frozenset(" ._-!?()[]+=*#@'~,|")
_NAME_BLANK = frozenset("\u115f\u1160\u2800\u3164\uffa0")   # letters that draw nothing
NAME_BYTES = 31          # the engine's name buffer is 32 (server.h)


def load_board_url(raw, log):
    """SURFD_BOARD_URL -> "" (sign-in off) or the board's public URL, no slash.

    http is accepted only for a private or loopback host: the state cookie is
    Secure exactly when the scheme is https.
    """
    url = (raw or "").strip().rstrip("/")
    if not url:
        return ""
    ok = bool(_URL_OK.fullmatch(url))
    if ok:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        if parts.scheme == "http" and host != "localhost":
            try:
                addr = ipaddress.ip_address(host)
                ok = addr.is_private or addr.is_loopback
            except ValueError:
                ok = False
    if not ok:
        log.error("SURFD_BOARD_URL %r is not https://host[/path]. Steam sign-in "
                  "stays off.", url)
        return ""
    return url


def show_code(code):
    return code[:4] + "-" + code[4:]


def game_name(name):
    """A Steam persona made safe to hand a lobby as a player name."""
    out = []
    for ch in unicodedata.normalize("NFC", name or ""):
        if ch in _NAME_PUNCT or (unicodedata.category(ch)[0] in "LN"
                                 and ch not in _NAME_BLANK):
            out.append(ch)
        elif unicodedata.category(ch) == "Zs" or ch in _NAME_BLANK:
            out.append(" ")
    safe = " ".join("".join(out).split())[:NAME_BYTES]
    while len(safe.encode("utf-8")) > NAME_BYTES:
        safe = safe[:-1]
    safe = safe.strip()
    if not safe or safe.lower() == "console":       # the engine reserves it
        return "player"
    return safe


def _tagged(tag, text):
    return hashlib.sha256((tag + text).encode("ascii")).hexdigest()[:32]


def code_tag(code):
    """What the game sends in place of the code (cl_account.qc agrees)."""
    return _tagged(TAG_CODE, code)


def ask_nonce(code):
    return _tagged(TAG_ASK, code)


def confirm_nonce(code, pin):
    return _tagged(TAG_CONFIRM, code + " " + pin)


def peer_of(raw):
    """The client address a lobby reports, without a port.  "?" if it is not one."""
    raw = (raw or "").strip()
    for cand in (raw, raw.rpartition(":")[0]):
        try:
            return str(ipaddress.ip_address(cand.strip("[]")))
        except ValueError:
            continue
    return "?"


def upgrade_13(conn):
    """Schema 13.  Safe to run twice, and from two processes at once: gunicorn
    and a cron tool both start here on a deploy."""
    conn.executescript(SQL_KEYS)
    if "claim" not in {r[1] for r in conn.execute("PRAGMA table_info(linkcodes)")}:
        try:
            conn.execute("ALTER TABLE linkcodes ADD COLUMN claim TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc):
                raise
    # 12's guid-keyed `links` never had a caller: it goes if it is empty, which
    # it is everywhere, and stays untouched if somebody did fill it.
    try:
        if not conn.execute("SELECT 1 FROM links LIMIT 1").fetchone():
            conn.execute("DROP TABLE IF EXISTS links")
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise


def resolve_host(name):
    """Every address `name` resolves to, as strings.  Raises OSError."""
    return {info[4][0] for info in socket.getaddrinfo(name, None)}


def _same(a, b):
    return hmac.compare_digest(str(a).encode("utf-8", "replace"),
                               str(b).encode("utf-8", "replace"))


def _page(depth, title, inner, status=200):
    up = "../" * depth
    doc = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="dark">\n'
        '<meta name="robots" content="noindex">\n'
        '<title>%(title)s - FTESurf</title>\n'
        '<link rel="stylesheet" href="%(up)sboard.css">\n</head>\n<body>\n'
        '<header class="nav"><nav class="nav-in" aria-label="Site">\n'
        '  <a class="brand" href="%(up)s../">FTE<b>SURF</b></a>\n'
        '  <div class="links"><a href="%(up)s../">Overview</a>'
        '<a href="%(board)s">Leaderboard</a></div>\n'
        '</nav></header>\n<div class="wrap">\n'
        '<header class="mast"><h1>%(title)s</h1></header>\n'
        '<div class="linkbox">\n%(inner)s\n</div>\n</div>\n</body>\n</html>\n'
    ) % {"title": html.escape(title), "up": up, "board": up or "./", "inner": inner}
    resp = Response(doc, status=status, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


def register(app, d):
    """Add the account routes to `app`.

    `d` carries surfd's own helpers (log, get_db, clock, rate_ok, rate_key,
    is_trusted, secret, setting, fail, game_json, clean_text, http,
    public_host, resolve) so this module never imports surfd back.
    """
    log = d.log
    board_url = load_board_url(d.setting("SURFD_BOARD_URL"), log)
    steam_key = (d.setting("SURFD_STEAM_KEY") or "").strip()
    # sweep.py's TOOLS, spelled a second time: the game's readers live with the game.
    tools_dir = d.setting("SURFD_TOOLS") or os.path.join(
        d.setting("SURFD_GAME") or "/srv/nvme/ftesurf-server/game", "tools")
    # Addresses a client may truthfully sign besides SURFD_PUBLIC_HOST's: the
    # LAN's, for players on it.  Literal addresses only.
    own_hosts = set()
    for part in (d.setting("SURFD_LINK_HOSTS") or "").split(","):
        if part.strip():
            try:
                own_hosts.add(ipaddress.ip_address(part.strip()))
            except ValueError:
                log.error("SURFD_LINK_HOSTS entry %r is not an address. Ignoring it.",
                          part.strip())
    looked = {"at": None, "tried": None, "addrs": set()}

    def game(payload):
        # `acct` is how the game tells an answer from an empty body: a request
        # that never connected reaches QuakeC as code 0 too (sv_account.qc).
        return Response(d.game_json(dict(payload, acct=1)), status=200,
                        mimetype="application/json")

    def lobby_ok(src):
        secret = d.secret()
        key = request.form.get("key", "")
        return bool(secret and key and _same(key, secret)) and d.is_trusted(src)

    def account_json(row):
        # Name and ban, and nothing a lobby has no use for yet.
        return {"name": game_name(row["name"]), "banned": 1 if row["banned_at"] else 0}

    def verifier():
        """tools/ed25519, found the way sweep.py finds it.  None if it is not there."""
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        try:
            import ed25519
        except Exception as exc:
            log.error("link: no ed25519.py in %s (%s)", tools_dir, type(exc).__name__)
            return None
        return ed25519

    def ours(server, node, now):
        """Is `server` an address a client reaches THIS lobby on?  True, False,
        or None when that cannot be decided now."""
        host, sep, port = server.rpartition(":")
        if not sep or not port.isdigit() or node != "p" + port:
            return False
        try:
            addr = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            return False
        addr = getattr(addr, "ipv4_mapped", None) or addr
        if addr in own_hosts:
            return True
        name = d.public_host()
        if not name:
            return False
        fresh = looked["at"] is not None and now - looked["at"] <= HOSTS_TTL
        if not fresh and (looked["tried"] is None or now - looked["tried"] > HOSTS_RETRY):
            looked["tried"] = now
            try:
                found = {ipaddress.ip_address(x) for x in d.resolve(name)}
                looked["at"], looked["addrs"] = now, found
            except (OSError, ValueError) as exc:
                log.warning("link: could not look up %s (%s)", name, type(exc).__name__)
        if looked["at"] is None or now - looked["at"] > HOSTS_STALE:
            return None             # no answer worth believing: not a refusal
        return addr in looked["addrs"]

    def proven(now, node, nonce, ticks, budget):
        """("", pub) when the request carries a signature, by the key it names,
        over this kind of statement, `nonce` and an address of ours; else (why, "")."""
        pub = request.form.get("pub") or ""         # exact: rec_sign writes lowercase hex
        sig = request.form.get("sig") or ""
        server = request.form.get("server") or ""
        if not (_HEX64.fullmatch(pub) and _HEX128.fullmatch(sig)
                and _SERVER.fullmatch(server)):
            return "proof", ""
        here = ours(server, node, now)
        if here is None:
            return "later", ""
        if not here:
            log.warning("link: a key signed for %s on %s, which is not this fleet",
                        server, node)
            return "server", ""
        ed = verifier()
        if ed is None or not d.rate_ok("*", now, budget[1], budget[0]):
            return "later", ""
        msg = (STATEMENT % (server, nonce, ticks)).encode("utf-8")
        if not ed.verify(bytes.fromhex(pub), msg, bytes.fromhex(sig)):
            log.info("link: key %s's signature did not verify (kind %d, nonce %s.., %s)",
                     pub[:16], ticks, nonce[:8], node)
            return "proof", ""
        return "", pub

    def lobby_call(flood, bucket):
        """(now, src, None) for a lobby's POST, or (0, "", reply) to send instead."""
        now = int(d.clock())
        src = request.remote_addr or "0.0.0.0"
        if not d.rate_ok(src, now, flood, bucket):
            return 0, "", d.fail(429, "rate limited")
        if not lobby_ok(src):
            log.warning("rejected %s from %s", request.path, src)
            return 0, "", d.fail(403, "forbidden")
        return now, src, None

    @app.post("/api/account")
    def account_status():
        """Who a connection is: the account its proven key is linked to.

        The lobby sends a nonce IT chose with the client's signature over it,
        so the answer is about whoever holds that key now, not about a guid.
        """
        now, src, early = lobby_call(ACCT_RATE_MAX, "acct")
        if early is not None:
            return early
        nonce = request.form.get("nonce") or ""
        if not _STATE.fullmatch(nonce):
            return d.fail(400, "bad nonce")
        peer = peer_of(request.form.get("ip"))
        if not d.rate_ok(peer, now, ACCT_PEER_MAX, "acctpeer"):
            return game({"linked": 0, "why": "later"})
        node = d.clean_text(request.form.get("node")) or "?"
        why, pub = proven(now, node, nonce, TICKS_HELLO,
                          ("verify-hello", HELLO_VERIFY_MAX))
        if why:
            return game({"linked": 0, "why": why})
        row = d.get_db().execute(
            "SELECT a.name, a.banned_at FROM linkkeys k"
            " JOIN accounts a ON a.steamid = k.steamid WHERE k.pub = ?",
            (pub,)).fetchone()
        if row is None:
            return game({"linked": 0})
        return game(dict(account_json(row), linked=1))

    def live_code(db, now, tag):
        """The unspent, unexpired code this digest is of, or ""."""
        for (code,) in db.execute(
                "SELECT code FROM linkcodes WHERE used_at = 0 AND issued_at >= ?",
                (now - CODE_TTL,)):
            if _same(code_tag(code), tag):
                return code
        return ""

    def step(db, now, pub, player, code, node, confirming):
        """One link step under the write lock.  -> (reply, steamid, moved_from).
        Asking claims the code for `pub`; confirming spends it and links."""
        row = db.execute(
            "SELECT a.steamid, a.name, a.banned_at, c.issued_at, c.used_at, c.claim"
            " FROM linkcodes c JOIN accounts a ON a.steamid = c.steamid"
            " WHERE c.code = ?", (code,)).fetchone()
        if row is None or row["used_at"] or row["issued_at"] < now - CODE_TTL:
            return {"ok": 0, "why": "code"}, "", ""
        if row["banned_at"]:
            return {"ok": 0, "why": "banned"}, "", ""
        old = db.execute(
            "SELECT k.steamid, a.name FROM linkkeys k"
            " LEFT JOIN accounts a ON a.steamid = k.steamid WHERE k.pub = ?",
            (pub,)).fetchone()
        moving = old is not None and old["steamid"] != row["steamid"]
        if not confirming:
            if row["claim"] not in ("", pub):
                return {"ok": 0, "why": "code"}, "", ""     # another key asked first
            took = db.execute("UPDATE linkcodes SET claim = ? WHERE code = ?"
                              " AND used_at = 0 AND claim IN ('', ?)", (pub, code, pub))
            if took.rowcount != 1:
                return {"ok": 0, "why": "code"}, "", ""
            return {"ok": 0, "why": "confirm", "to": game_name(row["name"]),
                    "from": game_name(old["name"]) if moving else ""}, row["steamid"], ""
        if row["claim"] != pub:
            return {"ok": 0, "why": "code"}, "", ""         # confirm without having asked
        spent = db.execute(
            "UPDATE linkcodes SET used_at = ?, used_by = ?"
            " WHERE code = ? AND used_at = 0", (now, pub[:16], code))
        if spent.rowcount != 1:
            return {"ok": 0, "why": "code"}, "", ""
        db.execute(
            "INSERT INTO linkkeys (pub, steamid, player, node, linked_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(pub) DO UPDATE SET"
            " steamid = excluded.steamid, player = excluded.player,"
            " node = excluded.node, linked_at = excluded.linked_at",
            (pub, row["steamid"], player, node, now))
        return (dict(account_json(row), ok=1), row["steamid"],
                old["steamid"] if moving else "")

    @app.post("/api/link")
    def link_redeem():
        """One step of a link: ask (no `pin`), then confirm (with it).

        A refusal the player can act on is a 200 with `why`: QuakeC sees a
        body only on success (sv_lobby.qc, URI_Get_Callback).
        """
        now, src, early = lobby_call(LINK_FLOOD_MAX, "linkflood")
        if early is not None:
            return early
        peer = peer_of(request.form.get("ip"))
        if not d.rate_ok(peer, now, TRY_RATE_MAX, "linktry"):
            return game({"ok": 0, "why": "slow"})
        if not d.rate_ok(src, now, LINK_RATE_MAX, "linkapi"):
            return d.fail(429, "rate limited")
        tag = request.form.get("tag") or ""
        pin = request.form.get("pin") or ""
        if pin and not _PIN.fullmatch(pin):
            return game({"ok": 0, "why": "code"})
        node = d.clean_text(request.form.get("node")) or "?"
        player = d.clean_text(request.form.get("player"))      # for the log, nothing else

        db = d.get_db()
        try:
            # A signature is only checked for a code that could be spent: a
            # check costs tens of milliseconds and a guess must not buy one.
            code = live_code(db, now, tag)
            if not code:
                return game({"ok": 0, "why": "code"})
            if pin:
                why, pub = proven(now, node, confirm_nonce(code, pin), TICKS_CONFIRM,
                                  ("verify-link", LINK_VERIFY_MAX))
            else:
                why, pub = proven(now, node, ask_nonce(code), TICKS_ASK,
                                  ("verify-link", LINK_VERIFY_MAX))
            if why:
                return game({"ok": 0, "why": why})
            # IMMEDIATE: a ban, or the other lobby, landing between the read
            # and the write must lose.
            db.execute("BEGIN IMMEDIATE")
            reply, steamid, was = step(db, now, pub, player, code, node, bool(pin))
            if steamid:
                db.commit()
            else:
                db.rollback()
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return d.fail(500, "storage error")
        if reply["ok"]:
            log.info("link: key %s -> account %s on %s%s", pub[:16], steamid, node,
                     " (was %s)" % was if was else "")
        return game(reply)

    if not board_url:
        log.info("no SURFD_BOARD_URL: Steam sign-in pages are off")
        return
    parts = urllib.parse.urlsplit(board_url)
    realm = "%s://%s" % (parts.scheme, parts.netloc)
    secure = parts.scheme == "https"
    # __Host- (Secure, Path=/, no Domain) cannot be set from a subdomain or over
    # plain http, and this origin is shared with other applications.
    cookie = "__Host-ftl" if secure else "ftl"
    ucookie = "__Host-ftu" if secure else "ftu"     # the browser that may unlink
    cookie_path = "/" if secure else parts.path + "/link"
    asking = threading.BoundedSemaphore(OUT_ATONCE)
    log.info("Steam sign-in at %s/link (%s profile key)", board_url,
             "with a" if steam_key else "NO")

    def refuse_now(now):
        """A reply that ends the request before any work, or None."""
        if request.method != "GET":         # a HEAD would spend a sign-in unseen
            return d.fail(405, "method not allowed")
        if not d.rate_ok(d.rate_key(), now, WEB_RATE_MAX, "link"):
            return d.fail(429, "rate limited")
        return None

    def again(message, status=200):
        return _page(1, "Link Steam",
                     "<p>%s</p>\n<p><a class=\"go\" href=\"../link\">Start again</a></p>"
                     % html.escape(message), status)

    def unlink_token(step, at, steamid, key16, linked_at, browser):
        """A link that unlinks one install.  Good for UNLINK_TTL, in the
        browser whose sign-in printed it (`browser` is that cookie), for the
        link as it stood then (`linked_at`): a re-link makes it stale.
        "" when there is no secret to sign with."""
        secret = d.secret()
        if not secret or not browser:
            return ""
        body = "%s.%d.%s.%s" % (step, at, steamid, key16)
        mac = hmac.new(
            hashlib.sha256(b"surfd unlink " + secret.encode("utf-8")).digest(),
            ("%s.%d.%s" % (body, linked_at, hashlib.sha256(
                browser.encode("utf-8", "replace")).hexdigest())).encode("ascii"),
            hashlib.sha256).hexdigest()[:32]
        return body + "." + mac

    def installs_html(db, steamid, now, browser):
        """The account's linked installs, each with its unlink link."""
        rows = db.execute("SELECT pub, node, linked_at FROM linkkeys WHERE steamid = ?"
                          " ORDER BY linked_at", (steamid,)).fetchall()
        if not rows:
            return "\n<p>No install is linked to this account yet.</p>"
        items = []
        for r in rows:
            token = unlink_token("ask", now, steamid, r["pub"][:16], r["linked_at"], browser)
            items.append(
                "<li><code>%s</code> linked %s on %s%s</li>" % (
                    r["pub"][:16], time.strftime("%Y-%m-%d", time.gmtime(r["linked_at"])),
                    html.escape(r["node"]),
                    " <a href=\"unlink?t=%s\">Unlink</a>" % token if token else ""))
        return ("\n<p>Installs linked to this account:</p>\n<ul class=\"installs\">\n%s\n</ul>"
                % "\n".join(items))

    def held(db, now):
        """Assertions on record.  Pruned BEFORE counted, or a full table never empties."""
        db.execute("DELETE FROM linknonces WHERE seen_at < ?", (now - NONCE_KEEP,))
        db.commit()
        return db.execute("SELECT COUNT(*) FROM linknonces").fetchone()[0]

    def burn(db, nonce, now):
        """Record an assertion as seen.  False if it already was."""
        try:
            db.execute("INSERT INTO linknonces (nonce, seen_at) VALUES (?, ?)",
                       (nonce, now))
            db.commit()
            return True
        except sqlite3.IntegrityError:
            db.rollback()
            return False

    @app.get("/board/link")
    def link_page():
        early = refuse_now(int(d.clock()))
        if early is not None:
            return early
        return _page(0, "Link Steam", (
            "<p>Times on the official servers are ranked under your Steam "
            "account. Sign in here and you get a code to type into the game; "
            "that links this install to you.</p>\n"
            "<p><a class=\"go\" href=\"link/steam\">Sign in through Steam</a></p>\n"
            "<p>Steam tells FTESurf your public Steam ID, and FTESurf reads "
            "your public name and avatar. No password and nothing private "
            "reaches this site.</p>"))

    @app.get("/board/link/steam")
    def link_start():
        early = refuse_now(int(d.clock()))
        if early is not None:
            return early
        token = secrets.token_urlsafe(18)
        state = hashlib.sha256(token.encode("ascii")).hexdigest()[:32]
        resp = redirect(steam.login_url(
            realm, "%s/link/return?s=%s" % (board_url, state)), code=302)
        # Lax, so it comes back on Steam's top-level redirect and nowhere else.
        resp.set_cookie(cookie, token, max_age=CODE_TTL, path=cookie_path,
                        secure=secure, httponly=True, samesite="Lax")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/board/link/return")
    def link_return():
        now = int(d.clock())
        early = refuse_now(now)
        if early is not None:
            return early
        src = d.rate_key()

        state = request.args.get("s", "")
        if not _STATE.fullmatch(state):
            return again("That sign-in did not start in this browser, or it "
                         "took longer than ten minutes.", 400)
        args = {}
        for k in request.args:
            if k.startswith("openid."):
                values = request.args.getlist(k)
                if len(values) != 1:
                    return again("Steam's reply was not valid.", 400)
                args[k] = values[0]
        try:
            steamid, nonce = steam.precheck(
                args, "%s/link/return?s=%s" % (board_url, state), now)
        except steam.Refused as exc:
            if str(exc) == "cancelled":
                return again("Sign-in was cancelled.")
            log.info("link: refused before asking Steam (%s) from %s", exc, src)
            return again("Steam's reply was not valid.", 400)

        db = d.get_db()
        # nginx gives this whole request 5 s and Steam may take four of them.
        db.execute("PRAGMA busy_timeout=1000")
        try:
            # The browser that comes back must be the one that left: without
            # this an attacker's own valid assertion, opened in a victim's
            # browser, shows the victim a code for the ATTACKER's account.
            # The assertion is burned here too, or a victim who signed in
            # through a link they were sent could hand the resulting address
            # back to its sender, who does hold the cookie.  BEST EFFORT: a
            # reply refused before this line (the page limit, nginx's, a lock)
            # is not recorded, and strays stop being recorded at NONCE_STRAY so
            # that made-up ones can never fill the table sign-ins need.
            token = request.cookies.get(cookie, "")
            if not token or not _same(
                    hashlib.sha256(token.encode("utf-8", "replace")).hexdigest()[:32],
                    state):
                if held(db, now) < NONCE_STRAY:
                    burn(db, nonce, now)
                return again("That sign-in did not start in this browser, or it "
                             "took longer than ten minutes.", 400)
            if db.execute("SELECT 1 FROM linknonces WHERE nonce = ?",
                          (nonce,)).fetchone():
                return again("That sign-in has already been used.", 400)
            live = db.execute(
                "SELECT COUNT(*) FROM linkcodes WHERE used_at = 0 AND issued_at >= ?",
                (now - CODE_TTL,)).fetchone()[0]
            seen = held(db, now)
            # The source's own allowance before everyone's: a refused source
            # must not spend it.  None of these burns the assertion.
            why = ""
            if live >= CODE_LIVE_MAX:
                why = "codes outstanding"
            elif seen >= NONCE_MAX:
                why = "assertions on record"
            elif not d.rate_ok(src, now, OUT_SOURCE_MAX, "linkout1"):
                why = "this source's allowance"
            elif not d.rate_ok("*", now, OUT_RATE_MAX, "linkout"):
                why = "the minute's allowance"
            elif not asking.acquire(blocking=False):
                why = "sign-ins in flight"
            if why:
                log.warning("link: sign-in deferred (%s) from %s", why, src)
                return again("Too many people are signing in right now. Try "
                             "again in a minute.", 503)
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return again("Something went wrong on our side. Try again in a "
                         "minute.", 500)

        profile = None
        try:
            if not burn(db, nonce, now):
                return again("That sign-in has already been used.", 400)
            steam.confirm(args, d.http)
            if steam_key:
                try:
                    profile = steam.summaries(steam_key, [steamid], d.http).get(steamid)
                except Exception as exc:    # a name is never worth a failed sign-in
                    log.warning("link: no profile for %s (%s)", steamid,
                                exc if isinstance(exc, steam.Unavailable)
                                else type(exc).__name__)
        except steam.Refused as exc:
            # Steam said no: this source waits out the minute.
            while d.rate_ok(src, now, OUT_SOURCE_MAX, "linkout1"):
                pass
            log.warning("link: %s from %s", exc, src)
            return again("Steam did not confirm that sign-in.", 400)
        except steam.Unavailable as exc:
            log.warning("link: Steam unavailable (%s)", exc)
            return again("Steam could not be reached, so nothing was linked. "
                         "Try again in a minute.", 503)
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return again("Something went wrong on our side. Try again in a "
                         "minute.", 500)
        finally:
            asking.release()

        try:
            db.execute("INSERT OR IGNORE INTO accounts (steamid, created_at)"
                       " VALUES (?, ?)", (steamid, now))
            if profile:
                db.execute("UPDATE accounts SET name = ?, avatar = ?, seen_at = ?"
                           " WHERE steamid = ?",
                           (profile["name"], profile["avatar"], now, steamid))
            acct = db.execute("SELECT name, banned_at FROM accounts WHERE steamid = ?",
                              (steamid,)).fetchone()
            code = ""
            if not acct["banned_at"]:
                # One live code per account: the newest.
                db.execute("UPDATE linkcodes SET used_at = ?, used_by = ?"
                           " WHERE steamid = ? AND used_at = 0",
                           (now, SUPERSEDED, steamid))
                db.execute("DELETE FROM linkcodes WHERE issued_at < ?",
                           (now - CODE_KEEP,))
                for _ in range(8):
                    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
                    if not db.execute("SELECT 1 FROM linkcodes WHERE code = ?",
                                      (code,)).fetchone():
                        break
                db.execute("INSERT INTO linkcodes (code, steamid, issued_at)"
                           " VALUES (?, ?, ?)", (code, steamid, now))
            db.commit()
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return again("Something went wrong on our side. Try again in a "
                         "minute.", 500)

        who = html.escape(acct["name"] or "Steam account " + steamid)
        browser = secrets.token_urlsafe(18)
        if not code:
            log.info("link: banned account %s signed in", steamid)
            resp = _page(1, "Link Steam",
                         "<p>Signed in as <b>%s</b>.</p>\n<p>This Steam account "
                         "is banned from the FTESurf leaderboards.</p>" % who
                         + installs_html(db, steamid, now, browser), 403)
        else:
            log.info("link: code issued for account %s", steamid)
            resp = _page(1, "Link Steam", (
                "<p>Signed in as <b>%s</b>.</p>\n"
                "<p>In FTESurf, join an official lobby, open the console and "
                "type:</p>\n<p class=\"linkcode\">link %s</p>\n"
                "<p>The code works once and expires in ten minutes. Keep it to "
                "yourself: whoever types it first is linked to your account. "
                "And only use a code you got from this page yourself: a code "
                "someone sends you links your game to their account.</p>"
                % (who, show_code(code))) + installs_html(db, steamid, now, browser))
        resp.delete_cookie(cookie, path=cookie_path, secure=secure,
                           httponly=True, samesite="Lax")
        resp.set_cookie(ucookie, browser, max_age=UNLINK_TTL, path=cookie_path,
                        secure=secure, httponly=True, samesite="Lax")
        return resp

    @app.get("/board/link/unlink")
    def link_unlink():
        """Two GETs, because nginx passes nothing else: the first asks, the
        second (its own token) unlinks.  A link fetched by something that is
        not the owner clicking it therefore changes nothing."""
        now = int(d.clock())
        early = refuse_now(now)
        if early is not None:
            return early
        m = _UNLINK.fullmatch(request.args.get("t", ""))
        browser = request.cookies.get(ucookie, "")
        if m is None or not browser:
            return again("That link is not valid here. Sign in again to see your "
                         "installs.", 400)
        step, at, steamid, key16 = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        db = d.get_db()
        try:
            row = db.execute(
                "SELECT k.pub, k.node, k.linked_at, a.name FROM linkkeys k"
                " JOIN accounts a ON a.steamid = k.steamid"
                " WHERE k.steamid = ? AND substr(k.pub, 1, 16) = ?",
                (steamid, key16)).fetchone()
            # One answer for a forged link, another browser's, a stale one and
            # an install already gone: none of them is told which.
            good = row is not None and unlink_token(step, at, steamid, key16,
                                                    row["linked_at"], browser)
            if not good or not _same(good, m.group(0)) or not -60 <= now - at <= UNLINK_TTL:
                return again("That link is not valid here, or the install is already "
                             "unlinked. Sign in again to see your installs.", 400)
            who = html.escape(row["name"] or "Steam account " + steamid)
            if step == "ask":
                return _page(1, "Unlink an install", (
                    "<p>Unlink install <code>%s</code> (linked %s on %s) from "
                    "<b>%s</b>?</p>\n<p>It can be linked again with a new code.</p>\n"
                    "<p><a class=\"go\" href=\"unlink?t=%s\">Unlink it</a></p>" % (
                        key16, time.strftime("%Y-%m-%d", time.gmtime(row["linked_at"])),
                        html.escape(row["node"]), who,
                        unlink_token("do", at, steamid, key16, row["linked_at"], browser))))
            db.execute("DELETE FROM linkkeys WHERE pub = ?", (row["pub"],))
            db.commit()
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return again("Something went wrong on our side. Try again in a "
                         "minute.", 500)
        log.info("link: key %s unlinked from account %s on the site", key16, steamid)
        return again("Install %s is no longer linked to %s." % (
            key16, row["name"] or "Steam account " + steamid))
