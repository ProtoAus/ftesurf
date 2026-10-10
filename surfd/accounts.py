#!/usr/bin/env python3
"""
accounts.py -- Steam accounts for surfd (schema 12).

STORE-ONLY: nothing that ranks, verifies or publishes a run reads these tables.

  accounts    one row per SteamID64 that has signed in, or been banned
  links       install guid -> account; one account, many installs
  linkcodes   what a sign-in hands the player to type into the game
  linknonces  every Steam assertion seen once, so none is used twice

THE CODE GOES FROM THE BROWSER TO THE GAME, not the other way.  A code shown in
the game and entered on the web would bind the VISITOR's Steam account to the
code's install, so a link sent to a victim ("sign in to see my run") would hand
the sender the victim's account.  This way round a stranger's code is only
useful typed into the victim's own game, on an official lobby.

A CODE IS STILL A BEARER TOKEN for its ten minutes: whoever types it first is
linked.  The page says to keep it private, an install that is already linked
moves only on a second, explicit request, and a ban never pins an install to
the banned account -- that would let one player link a victim's install to a
throwaway account, get it banned, and lock the victim out.

The sign-in pages are registered only when SURFD_BOARD_URL is set; the two
lobby routes need the shared key AND a trusted source.

No module state: tests reload surfd many times in one process and this module
is not reloaded with it.  Everything configured lives in register()'s closure.
"""

import hashlib
import hmac
import html
import ipaddress
import re
import secrets
import sqlite3
import threading
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
CREATE TABLE IF NOT EXISTS links (
    player    TEXT    PRIMARY KEY,
    steamid   TEXT    NOT NULL,
    pub       TEXT    NOT NULL DEFAULT '',
    node      TEXT    NOT NULL DEFAULT '',
    linked_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS links_steamid ON links (steamid);
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
ACCT_RATE_MAX = 600      # /api/account calls per window per source
LINK_FLOOD_MAX = 1200    # /api/link calls per window per source, before the key is read
LINK_RATE_MAX = 120      # ...and redeem attempts, after the per-install limit
TRY_RATE_MAX = 6         # redeem attempts per window per install

_STATE = re.compile(r"[0-9a-f]{32}")
_URL_OK = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?")
_CODE_OK = re.compile(r"[%s]{%d}" % (CODE_ALPHABET, CODE_LEN))
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


def clean_code(raw):
    """What a player typed -> the stored spelling, or ""."""
    code = re.sub(r"[\s-]", "", str(raw or "")).upper()
    return code if _CODE_OK.fullmatch(code) else ""


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


def install_id(player):
    """The 8 hex a lobby already publishes for an install (FS_GuidId)."""
    return hashlib.sha256(player.encode("utf-8", "replace")).hexdigest()[:8]


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
    is_trusted, secret, setting, fail, game_json, clean_text, http) so this
    module never imports surfd back.
    """
    log = d.log
    board_url = load_board_url(d.setting("SURFD_BOARD_URL"), log)
    steam_key = (d.setting("SURFD_STEAM_KEY") or "").strip()

    def game(payload):
        return Response(d.game_json(payload), status=200, mimetype="application/json")

    def lobby_ok(src):
        secret = d.secret()
        key = request.form.get("key", "")
        return bool(secret and key and _same(key, secret)) and d.is_trusted(src)

    def account_json(row):
        return {"steamid": row["steamid"], "name": game_name(row["name"]),
                "avatar": row["avatar"], "banned": 1 if row["banned_at"] else 0}

    @app.post("/api/account")
    def account_status():
        """Which account an install is linked to.  Lobbies ask at connect."""
        now = int(d.clock())
        src = request.remote_addr or "0.0.0.0"
        if not d.rate_ok(src, now, ACCT_RATE_MAX, "acct"):
            return d.fail(429, "rate limited")
        if not lobby_ok(src):
            log.warning("rejected account query from %s", src)
            return d.fail(403, "forbidden")
        player = d.clean_text(request.form.get("player"))
        if not player:
            return d.fail(400, "missing player")
        row = d.get_db().execute(
            "SELECT a.steamid, a.name, a.avatar, a.banned_at FROM links l"
            " JOIN accounts a ON a.steamid = l.steamid WHERE l.player = ?",
            (player,)).fetchone()
        if row is None:
            return game({"linked": 0})
        return game(dict(account_json(row), linked=1))

    def redeem(db, now, player, code, node, confirmed):
        """The reply for one redeem, and the account it left.  Writes only on ok."""
        row = db.execute(
            "SELECT a.steamid, a.name, a.avatar, a.banned_at, c.issued_at, c.used_at"
            " FROM linkcodes c JOIN accounts a ON a.steamid = c.steamid"
            " WHERE c.code = ?", (code,)).fetchone()
        if row is None or row["used_at"] or row["issued_at"] < now - CODE_TTL:
            return {"ok": 0, "why": "code"}, None
        if row["banned_at"]:
            return {"ok": 0, "why": "banned"}, None
        old = db.execute(
            "SELECT l.steamid, a.name FROM links l"
            " LEFT JOIN accounts a ON a.steamid = l.steamid WHERE l.player = ?",
            (player,)).fetchone()
        moving = old is not None and old["steamid"] != row["steamid"]
        if moving and not confirmed:
            # Not spent: the same code, sent again with confirm=1, moves it.
            return {"ok": 0, "why": "move", "from": game_name(old["name"]),
                    "to": game_name(row["name"])}, None
        spent = db.execute(
            "UPDATE linkcodes SET used_at = ?, used_by = ?"
            " WHERE code = ? AND used_at = 0", (now, install_id(player), code))
        if spent.rowcount != 1:
            return {"ok": 0, "why": "code"}, None
        db.execute(
            "INSERT INTO links (player, steamid, node, linked_at)"
            " VALUES (?, ?, ?, ?) ON CONFLICT(player) DO UPDATE SET"
            " steamid = excluded.steamid, pub = '', node = excluded.node,"
            " linked_at = excluded.linked_at",
            (player, row["steamid"], node, now))
        return dict(account_json(row), ok=1), (old["steamid"] if moving else "")

    @app.post("/api/link")
    def link_redeem():
        """Spend a code: bind the install that typed it to the code's account.

        A refusal the player can act on is a 200 with `why`: QuakeC sees a
        body only on success (sv_lobby.qc, URI_Get_Callback).
        """
        now = int(d.clock())
        src = request.remote_addr or "0.0.0.0"
        if not d.rate_ok(src, now, LINK_FLOOD_MAX, "linkflood"):
            return d.fail(429, "rate limited")
        if not lobby_ok(src):
            log.warning("rejected link from %s", src)
            return d.fail(403, "forbidden")
        player = d.clean_text(request.form.get("player"))
        if not player:
            return d.fail(400, "missing player")
        # The install's own limit first.  Every lobby posts from one address,
        # so an install hammering `link` must not spend the lobbies' allowance.
        if not d.rate_ok(player, now, TRY_RATE_MAX, "linktry"):
            return game({"ok": 0, "why": "slow"})
        if not d.rate_ok(src, now, LINK_RATE_MAX, "linkapi"):
            return d.fail(429, "rate limited")
        code = clean_code(request.form.get("code"))
        if not code:
            return game({"ok": 0, "why": "code"})
        node = d.clean_text(request.form.get("node")) or "?"

        db = d.get_db()
        try:
            # IMMEDIATE: a ban landing between the read and the write would
            # otherwise link an install to an account banned a moment before.
            db.execute("BEGIN IMMEDIATE")
            reply, was = redeem(db, now, player, code, node,
                                request.form.get("confirm") == "1")
            if reply["ok"]:
                db.commit()
            else:
                db.rollback()
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return d.fail(500, "storage error")
        if reply["ok"]:
            log.info("link: install %s -> account %s on %s%s", install_id(player),
                     reply["steamid"], node, " (was %s)" % was if was else "")
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
        if not code:
            log.info("link: banned account %s signed in", steamid)
            resp = _page(1, "Link Steam",
                         "<p>Signed in as <b>%s</b>.</p>\n<p>This Steam account "
                         "is banned from the FTESurf leaderboards.</p>" % who, 403)
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
                % (who, show_code(code))))
        resp.delete_cookie(cookie, path=cookie_path, secure=secure,
                           httponly=True, samesite="Lax")
        return resp
