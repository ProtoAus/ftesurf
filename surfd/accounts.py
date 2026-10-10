#!/usr/bin/env python3
"""
accounts.py -- Steam accounts for surfd (schema 15).

STORE-ONLY: nothing that ranks, verifies or publishes a run reads these tables.

  accounts    one row per SteamID64 that has signed in, or been banned
  keylinks    an install's signing key -> account; one account, many installs
  linkcodes   what a sign-in hands the player to type into the game, and
              (Patch 619) what a game hands the player to sign in with
  linknonces  every Steam assertion seen once, so none is used twice

AN INSTALL IS ITS KEY, NOT ITS GUID.  The engine guid is handed to any server
that sends the fleet's sv_guidkey, so a link keyed on it could be moved, or
squatted before its owner ever linked, by whoever harvested one.  Every lobby
call carries a signature by the install's `fskey` over acct_sign's statement
(cl_receipt.c), which names the server the CLIENT is talking to: it must be an
address of ours, on the asking lobby's port, or a signature made on somebody
else's server would do.

FOUR THINGS ARE SIGNED AND NONE CAN STAND IN FOR ANOTHER.  The statement's
`kind` says which: -2 a connect (the lobby's nonce), -3 asking to link (a
digest of the code), -4 confirming it (a digest of the code AND the number the
lobby showed the player), -5 starting a link from the game (a digest of the
start's code AND the client's opener).

AND THE STATEMENT IS THE ACCOUNT'S OWN (Patch 625), not a run receipt's with a
negative tick count as it was through 619.  Those were signed by the console
command `rec_sign`, which game code reached with a console line, and console
lines are built from text in fifty places: whoever could write to a player's
connection might have found one that signed a link with no key pressed.  The
engine now signs account proofs only through a builtin, into STATEMENT below,
which no older engine can produce; it says in a signed line whether a device's
key was being pressed, and refuses to ask, confirm or start without one.  So
"this link was consented to at a keyboard" is something this file CHECKS:
anything signed the old way is refused, and the links made before were dropped
(schema 15).  A player's own modified client can still sign what it likes with
its own key: that is their consent to give.

LINKING IS ASK, THEN CONFIRM.  Asking proves a key for a code and CLAIMS the
code for that key: nobody else can use it after.  The lobby then sends the
client the account's name and a number of ITS choosing, and confirming signs
that number; surfd never sees the number except under the signature.

WHO MAY ASK AND CONFIRM IS THE GAME'S BUSINESS, NOT THIS FILE'S.  surfd proves
a key signed; it cannot see whether a person meant it.  Since Patch 617 the
client makes both signatures only under key presses in its own link box
(cl_account.qc); Patch 615 made them for a console command, which a server can
type.  The lobby is sent a digest of the code and never the code.  A CODE IS
TWELVE CHARACTERS AND ITS DIGEST IS SALTED (Patch 625): the packet that
exposes the digest also claims the code, but that packet can be dropped on
the way, and ten characters under a bare SHA-256 are thirty GPU-hours, or one
table made once.  Sixty bits under a salt the client draws each time is
neither within a code's ten minutes.  And a code is a bearer token until
somebody asks with it: typed into a game whose server is not ours, it is that
server's.

A LINK THE GAME STARTS (Patch 619) RUNS THE OTHER WAY ROUND.  The game
registers a start for its key first (`/api/link/start`) and opens a sign-in
address.  The start's code is NOT a secret and does not link: it crosses the
wire in the clear.  What links is the four-digit NUMBER the
sign-in page then shows (`linkcodes.shown`), typed into the game that holds
the key: one try, and a wrong one spends the start.  THE GAME DOES NOT SEND
THE NUMBER: it sends a digest of it with ITS OWN opener and the lobby's pin
(`number_proof`), because four digits in the clear are four digits for
whoever reads that connection, and a player can be sent to sign in for
somebody else's start.  A number typed into a game that did not start that
link is then a digest of the wrong opener: worth nothing to anybody.  So the two ends are tied
by something only the signed-in browser's owner can see, exactly as a typed
code ties them, and a start somebody was SENT takes nothing unless they also
read out the number.  The first cut tied them by address alone (a browser at
the address the game started from); its review linked a victim's account to
somebody else's install with a sign-in and nothing more.

AND THE ADDRESS CARRIES AN OPENER THE CLIENT MADE (`&k=`), WHICH ITS START
SIGNED FOR.  The number is typed into the game and crosses its wire in the
clear, so it must be worth nothing to whoever reads it there.  It would be
worth an account if a player could be walked into signing in for SOMEBODY
ELSE'S start, and their connection can be rewritten: the game cannot tell a
code that is not its own, because game code does not know its own key.  So
the client makes a secret, and what its key signs for the start is the start's
code AND that secret (`start_nonce`).  Nobody else sees the secret: it goes
into the address the engine opens, and from the browser to here.  (Since
Patch 625 the code is itself a digest of the opener, `start_code_of`, so the
client needs nothing back from the lobby before the browser opens, and there
is no code for a rewritten connection to swap.)  A START'S
SIGNATURE IS THEREFORE KEPT UNCHECKED (`linkcodes.seal`) and checked when a
sign-in brings the opener: it verifies only for the key whose client made
that opener, so a code swapped on the wire, or a start registered by somebody
who watched it, opens nothing.  The second review asked for exactly this ("the
client has to know the code is its own"); a digest of the opener sent with the
start, the first answer, can be copied into somebody else's start.

The page says to keep a code private and lists what is linked, with a way to
unlink.  A ban never pins an install to the banned account -- that would let
one player link a victim's install to a throwaway account, get it banned, and
lock the victim out.

The sign-in pages are registered only when SURFD_BOARD_URL is set; the four
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
#
# THE TABLE IS `keylinks` SINCE SCHEMA 15, AND THE NAME IS THE POINT.  Until
# Patch 625 a link was signed by a console command, so none made before it
# shows a key was pressed, and 14.3 ranks on a link.  Those lived in
# `linkkeys`.  This code never reads that table and EMPTIES it at every start
# (links_now), so whatever older code writes there (a rollback, a process left
# running on the new file) is never a link here: not after the next start,
# and not before it either.  Emptied, not dropped: older code does not make
# the table again on a file stamped 15, and a rollback that cannot start is
# worse than a table nobody reads.  The first cut stamped rows of one table
# with how they were proven; its review re-linked a stamped row with the old
# code, whose upsert leaves a column it has never heard of alone.
SQL_KEYS = """
CREATE TABLE IF NOT EXISTS keylinks (
    pub       TEXT    PRIMARY KEY,
    steamid   TEXT    NOT NULL,
    player    TEXT    NOT NULL DEFAULT '',
    node      TEXT    NOT NULL DEFAULT '',
    linked_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS keylinks_steamid ON keylinks (steamid);
"""
OLD_LINKS = "linkkeys"

CODE_TTL = 600           # s a code can be redeemed for
CODE_KEEP = 86400        # s a spent or superseded code's row is kept
CODE_LIVE_MAX = 500      # unredeemed codes outstanding; past it sign-in waits
START_LIVE_MAX = 200     # ...and starts nobody has signed in for; past it a start waits.
                         # Counted apart: a start costs no Steam account, so starts
                         # sharing the cap above could close sign-in to everybody.
SHOWN_LEN = 4            # digits of the number a start's sign-in page shows
NOT_YET = "?"            # linkcodes.shown of a start nobody has signed in for
CODE_LEN = 12            # 60 bits: a salted digest of the code crosses the wire (see the header)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"    # no I O 0 1
# linkcodes.used_by of a code spent by something other than a key's confirm:
SUPERSEDED = "superseded"        # a newer code or start took its place
MISMATCH = "mismatch"            # a wrong number for a start (step)
CONTESTED = "contested"          # a second account signed in for one start
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
WAIT_RATE_MAX = 60       # /api/link/wait calls per window per client address
OPEN_VERIFY_MAX = 60     # signatures checked a minute to open a start at sign-in.  Its
                         # own allowance: a flood of link steps must not leave a player
                         # who has just signed in (and spent the assertion) at a 503.
WAIT_FLOOD_MAX = 6000    # ...and per source, in a bucket of their own: a lobby full of
                         # waiters must not spend the link steps' allowance

# What the engine's acct_sign builtin signs (cl_receipt.c, CL_Receipt_AcctSign).
# `key` is 1 when a device's key press was being delivered to game code.
# `code` is the SHA-256 of the csprogs that asked.  A KEY PRESS IS CONSENT TO
# WHATEVER DREW THE BOX, and a client picks the csprogs it runs from a
# download cache every server it has visited can write, by a 32-bit checksum:
# the code on a lobby is not known to be the lobby's.  So the engine says
# which code asked, inside the signature, and game_code() takes only what our
# lobbies serve (SURFD_GAME_CODE: their csprogs.dat and its .prev).
STATEMENT = "FTESURF-ACCT 1\nserver %s\nnonce %s\nkind %d\nkey %d\ncode %s\n"
TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = -2, -3, -4, -5
TAG_CODE = "ftesurf-code "          # the code as it crosses the wire
TAG_ASK = "ftesurf-link "           # ...as asking signs it
TAG_CONFIRM = "ftesurf-confirm "    # ...and confirming, with the number
TAG_START = "ftesurf-start "        # a start: its code AND the client's opener
TAG_ID = "ftesurf-id "              # a start's code, from its opener
TAG_NUMBER = "ftesurf-number "      # the sign-in page's number, with opener and pin

_STATE = re.compile(r"[0-9a-f]{32}")
_URL_OK = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX128 = re.compile(r"[0-9a-f]{128}")
_SERVER = re.compile(r"[\x21-\x7e]{3,128}")
_UNLINK = re.compile(r"(ask|do)\.([0-9]{10})\.([0-9]{17})\.([0-9a-f]{16})\.([0-9a-f]{32})")
_PIN = re.compile(r"[0-9]{6}")
_OPENER = re.compile(r"[0-9a-f]{24}")
_SALTED = re.compile(r"[0-9a-f]{48}")       # a typed code's tag: 16 of salt, 32 of digest
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
    """ABCD-EFGH-JKLM: fours, as it is read off a page and typed."""
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


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


def typed_tag(salt, code):
    """What the game sends in place of a TYPED code, under a salt it drew."""
    return _tagged(TAG_CODE, salt + " " + code)


def number_proof(opener, pin, number):
    """What the game sends in place of a start's number (cl_account.qc agrees)."""
    return _tagged(TAG_NUMBER, opener + " " + pin + " " + number)


def start_nonce(code, opener):
    """What a start signs (cl_account.qc agrees): its code with the secret
    only that client and, later, its player's browser have."""
    return _tagged(TAG_START, code + " " + opener)


def start_code_of(opener):
    """A start's code, as the client made it from its opener (cl_account.qc
    agrees): one of the alphabet's 32 from each of twelve bytes of a digest."""
    raw = hashlib.sha256((TAG_ID + opener).encode("ascii")).digest()
    return "".join(CODE_ALPHABET[b % len(CODE_ALPHABET)] for b in raw[:CODE_LEN])


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
    and a cron tool both start here on a deploy.  (The link table it used to
    make is links_now's since 15.)"""
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


def upgrade_14(conn):
    """Schema 14: a code the GAME started carries the number its sign-in page
    shows (`linkcodes.shown`: '' for a typed code, NOT_YET until somebody signs
    in) and its own signature, kept until a sign-in brings what it is over
    (`seal`: "<sig> <server> <game code>" since 625, and the opener once a
    sign-in has opened it).  Additive; safe twice and from two processes."""
    for col in ("shown", "seal"):
        if col in {r[1] for r in conn.execute("PRAGMA table_info(linkcodes)")}:
            continue
        try:
            conn.execute("ALTER TABLE linkcodes ADD COLUMN %s TEXT NOT NULL DEFAULT ''" % col)
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc):
                raise


def start_code(raw):
    """A code as it rides in a sign-in address (`?c=`), or ""."""
    code = (raw or "").replace("-", "")
    if len(code) == CODE_LEN and all(ch in CODE_ALPHABET for ch in code):
        return code
    return ""


def start_pair(args):
    """(code, opener) for the start a sign-in address names (`?k=`), or ("", "")."""
    opener = args.get("k") or ""
    if _OPENER.fullmatch(opener):
        return start_code_of(opener), opener
    return "", ""


def links_now(conn):
    """EVERY START, and schema 15's whole step: `keylinks` exists (a file
    stamped 15 by an earlier cut of this patch has none) and the table links
    lived in before Patch 625 is empty.  Nothing is copied.  Accounts and
    their bans stay.  Safe twice and from two processes.  -> how many old
    rows went."""
    conn.executescript(SQL_KEYS)
    try:
        return conn.execute("DELETE FROM %s" % OLD_LINKS).rowcount
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return 0


ABSENT = "absent"


def file_digest(path, seen):
    """SHA-256 of a file as hex; ABSENT if there is no such file; None if
    there is one and it could not be read whole and unchanged (so what it
    holds is not known).  `seen` caches by the size and time of THE HANDLE
    READ, taken before and after: a file swapped between a stat and a read
    was once cached for good under the other one's key (the third review)."""
    try:
        with open(path, "rb") as fh:
            st = os.fstat(fh.fileno())
            key = (st.st_ino, st.st_mtime_ns, st.st_size)
            held = seen.get(path)
            if held is not None and held[0] == key:
                return held[1]
            data = fh.read()
            st = os.fstat(fh.fileno())
            if (st.st_ino, st.st_mtime_ns, st.st_size) != key or len(data) != key[2] or not data:
                seen.pop(path, None)
                return None                     # written under us, or empty: not known
            seen[path] = (key, hashlib.sha256(data).hexdigest())
            return seen[path][1]
    except FileNotFoundError:
        seen.pop(path, None)
        return ABSENT
    except OSError:
        seen.pop(path, None)
        return None


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
        '<meta name="color-scheme" content="light dark">\n'
        '<meta name="robots" content="noindex">\n'
        '<title>%(title)s - FTESurf</title>\n'
        '<link rel="stylesheet" href="%(up)slink.css">\n</head>\n<body>\n'
        '<main class="card">\n'
        '<a class="mark" href="%(up)s../">FTE<b>SURF</b></a>\n'
        '%(inner)s\n</main>\n</body>\n</html>\n'
    ) % {"title": html.escape(title), "up": up, "inner": inner}
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
                if (ipaddress.ip_address(part.strip()).is_private
                        and not ipaddress.ip_address(part.strip()).is_loopback):
                    # Every LAN has a 192.168.1.x: a server at this address on
                    # ANY of them is one a proof may now name.
                    log.warning("SURFD_LINK_HOSTS lists the private address %s: a proof made"
                                " on any network's server at that address is taken as made"
                                " on ours", part.strip())
            except ValueError:
                log.error("SURFD_LINK_HOSTS entry %r is not an address. Ignoring it.",
                          part.strip())
    looked = {"at": None, "tried": None, "addrs": set()}
    # The game code our lobbies serve: files this process can read.  Default:
    # the lobbies' own csprogs and the one a deploy keeps beside it.
    game_dir = os.path.join(d.setting("SURFD_GAME") or "/srv/nvme/ftesurf-server/game",
                            "ftesurf")
    code_files = [p.strip() for p in (d.setting("SURFD_GAME_CODE") or ",".join(
        (os.path.join(game_dir, "csprogs.dat"), os.path.join(game_dir, "csprogs.dat.prev"))
    )).split(",") if p.strip()]
    code_seen, code_said = {}, {"set": None}

    def game_code(code):
        """True if `code` is the SHA-256 of game code our lobbies serve; False
        if it is not; None when that cannot be said: no file could be read, or
        one that is there could not and `code` is none of the others.
        "Cannot be checked" is not "somebody else's"."""
        read = [(p, file_digest(p, code_seen)) for p in code_files]
        ours_now = {h for _p, h in read if h and h != ABSENT}
        unknown = any(h is None for _p, h in read)
        said = tuple(read)
        if said != code_said["set"]:
            code_said["set"] = said
            (log.info if ours_now else log.error)(
                "account proofs must name game code: %s%s", "; ".join(
                    "%s %s" % (p, "is absent" if h == ABSENT else "CANNOT BE READ" if h is None
                               else h[:16]) for p, h in read),
                "" if ours_now else ".  NO PROOF CAN BE CHECKED, AND NONE IS TAKEN")
        if any(_same(code, h) for h in ours_now):
            return True
        return None if unknown or not ours_now else False

    game_code("")       # say at start what will be asked for

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

    def shaped(now, node):
        """("", pub, sig, server, keyed, gcode) when the request carries a
        well-formed proof made for an address of ours by game code of ours;
        else (why, "", "", "", 0, "").  NOT its signature.  `keyed` and `gcode`
        (form `game`) are what the lobby passed on of the engine's word; both
        are in the signed statement, so a wrong one fails there."""
        none = ("", "", "", 0, "")
        pub = request.form.get("pub") or ""         # exact: the engine writes lowercase hex
        sig = request.form.get("sig") or ""
        server = request.form.get("server") or ""
        keyed = request.form.get("keyed") or ""
        gcode = request.form.get("game") or ""
        if not (_HEX64.fullmatch(pub) and _HEX128.fullmatch(sig) and _HEX64.fullmatch(gcode)
                and _SERVER.fullmatch(server) and keyed in ("0", "1")):
            return ("proof",) + none
        here = ours(server, node, now)
        if here is None:
            return ("later",) + none
        if not here:
            log.warning("link: a key signed for %s on %s, which is not this fleet",
                        server, node)
            return ("server",) + none
        known = game_code(gcode)
        if known is None:
            return ("later",) + none
        if not known:
            log.warning("link: key %s signed under game code %s.. on %s, which no lobby"
                        " of ours serves", pub[:16], gcode[:16], node)
            return ("game",) + none
        return "", pub, sig, server, int(keyed), gcode

    def signed(now, pub, sig, server, nonce, kind, keyed, gcode, budget):
        """True if `sig` is `pub`'s over this kind of statement; None if that
        cannot be checked now (no verifier, or the minute's checks are spent)."""
        ed = verifier()
        if ed is None or not d.rate_ok("*", now, budget[1], budget[0]):
            return None
        msg = (STATEMENT % (server, nonce, kind, keyed, gcode)).encode("utf-8")
        return bool(ed.verify(bytes.fromhex(pub), msg, bytes.fromhex(sig)))

    def proven(now, node, nonce, kind, budget, key_needed=True):
        """("", pub) when the request carries a signature, by the key it names,
        over this kind of statement, `nonce` and an address of ours; else
        (why, "").  A link's kinds also need the engine's word that a key was
        being pressed; a connect's does not."""
        why, pub, sig, server, keyed, gcode = shaped(now, node)
        if why:
            return why, ""
        if key_needed and not keyed:
            return "proof", ""
        ok = signed(now, pub, sig, server, nonce, kind, keyed, gcode, budget)
        if ok is None:
            return "later", ""
        if not ok:
            log.info("link: key %s's signature did not verify (kind %d, nonce %s.., %s)",
                     pub[:16], kind, nonce[:8], node)
            return "proof", ""
        return "", pub

    def opens(row, code, opener, now):
        """True if `opener` is what the start's key signed with; None if that
        cannot be checked now.  The check /api/link/start did not make."""
        part = row["seal"].split(" ")
        if not (len(part) == 3 and _HEX128.fullmatch(part[0]) and _HEX64.fullmatch(part[2])
                and _HEX64.fullmatch(row["claim"])):
            return False
        # Ours NOW, not only when the start was made: a deploy may have come between.
        known = game_code(part[2])
        if not known:
            return known
        return signed(now, row["claim"], part[0], part[1], start_nonce(code, opener),
                      TICKS_START, 1, part[2], ("verify-open", OPEN_VERIFY_MAX))

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
                          ("verify-hello", HELLO_VERIFY_MAX), key_needed=False)
        if why:
            return game({"linked": 0, "why": why})
        row = d.get_db().execute(
            "SELECT a.name, a.banned_at FROM keylinks k"
            " JOIN accounts a ON a.steamid = k.steamid WHERE k.pub = ?",
            (pub,)).fetchone()
        if row is None:
            return game({"linked": 0})
        return game(dict(account_json(row), linked=1))

    def live_code(db, now, tag):
        """The unspent, unexpired code this digest is of, or "".  A TYPED code
        answers only to a salted digest (48 hex: the salt, then typed_tag); a
        START, whose code is public, to the plain one its lobby computes."""
        salted = bool(_SALTED.fullmatch(tag))
        for code, shown in db.execute(
                "SELECT code, shown FROM linkcodes WHERE used_at = 0 AND issued_at >= ?",
                (now - CODE_TTL,)):
            if shown:
                if not salted and _same(code_tag(code), tag):
                    return code
            elif salted and _same(typed_tag(tag[:16], code), tag[16:]):
                return code
        return ""

    def step(db, now, pub, player, code, node, confirming, pin="", shown=""):
        """One link step under the write lock.  -> (reply, steamid, moved_from).
        Asking claims the code for `pub`; confirming spends it and links.
        A non-empty steamid in the result means there is something to commit."""
        row = db.execute(
            "SELECT a.steamid, a.name, a.banned_at, c.issued_at, c.used_at, c.claim, c.shown,"
            " c.seal"
            " FROM linkcodes c JOIN accounts a ON a.steamid = c.steamid"
            " WHERE c.code = ?", (code,)).fetchone()
        if row is None or row["used_at"] or row["issued_at"] < now - CODE_TTL:
            return {"ok": 0, "why": "code"}, "", ""
        if row["banned_at"]:
            return {"ok": 0, "why": "banned"}, "", ""
        old = db.execute(
            "SELECT k.steamid, a.name FROM keylinks k"
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
        if row["shown"] and not _same(number_proof(row["seal"], pin, row["shown"]), shown):
            # A START, and not its number as the client that MADE the start
            # would send it: a digest with the opener (which an attached
            # start's `seal` holds) and this confirm's pin.  ONE TRY: a wrong
            # one spends the start, so the key that holds it cannot guess.
            db.execute("UPDATE linkcodes SET used_at = ?, used_by = ?"
                       " WHERE code = ? AND used_at = 0", (now, MISMATCH, code))
            return {"ok": 0, "why": "number"}, row["steamid"], ""
        spent = db.execute(
            "UPDATE linkcodes SET used_at = ?, used_by = ?"
            " WHERE code = ? AND used_at = 0", (now, pub[:16], code))
        if spent.rowcount != 1:
            return {"ok": 0, "why": "code"}, "", ""
        db.execute(
            "INSERT INTO keylinks (pub, steamid, player, node, linked_at)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(pub) DO UPDATE SET"
            " steamid = excluded.steamid, player = excluded.player,"
            " node = excluded.node, linked_at = excluded.linked_at",
            (pub, row["steamid"], player, node, now))
        return (dict(account_json(row), ok=1), row["steamid"],
                old["steamid"] if moving else "")

    def link_call():
        """A lobby's link step, counted: (now, peer, None), or (0, "", reply)
        to send instead.  /api/link and /api/link/start both spend from these
        budgets, so a start is not a second allowance."""
        now, src, early = lobby_call(LINK_FLOOD_MAX, "linkflood")
        if early is not None:
            return 0, "", early
        peer = peer_of(request.form.get("ip"))
        if not d.rate_ok(peer, now, TRY_RATE_MAX, "linktry"):
            return 0, "", game({"ok": 0, "why": "slow"})
        if not d.rate_ok(src, now, LINK_RATE_MAX, "linkapi"):
            return 0, "", d.fail(429, "rate limited")
        return now, peer, None

    @app.post("/api/link")
    def link_redeem():
        """One step of a link: ask (no `pin`), then confirm (with it).

        A refusal the player can act on is a 200 with `why`: QuakeC sees a
        body only on success (sv_lobby.qc, URI_Get_Callback).
        """
        now, _peer, early = link_call()
        if early is not None:
            return early
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
            reply, steamid, was = step(db, now, pub, player, code, node, bool(pin), pin,
                                       (request.form.get("shown") or "")[:32])
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

    @app.post("/api/link/start")
    def link_begin():
        """The game starts a link.

        The client's key signed the start's code WITH an opener only that
        client has (kind -5, under a key press), so the signature cannot be
        checked here: it is kept, and link_return checks it when a sign-in
        brings the opener (the module header has why).  What is checked now is
        its shape, that it was made for an address of ours, and that the
        engine says a key was pressed.  The code is the client's own, a digest
        of its opener; the first start to bring a code holds it.  It names the
        key from birth, has no account, and is not what links.
        """
        now, _peer, early = link_call()
        if early is not None:
            return early
        code = start_code(request.form.get("code"))
        if not code:
            return d.fail(400, "bad code")
        node = d.clean_text(request.form.get("node")) or "?"
        why, pub, sig, server, keyed, gcode = shaped(now, node)
        if not why and not keyed:
            why = "proof"
        if why:
            return game({"ok": 0, "why": why})
        db = d.get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            waiting = db.execute(
                "SELECT COUNT(*) FROM linkcodes WHERE used_at = 0 AND shown = ?"
                " AND issued_at >= ?", (NOT_YET, now - CODE_TTL)).fetchone()[0]
            if waiting >= START_LIVE_MAX:
                db.rollback()
                return game({"ok": 0, "why": "later"})
            db.execute("DELETE FROM linkcodes WHERE issued_at < ?", (now - CODE_KEEP,))
            if db.execute("SELECT 1 FROM linkcodes WHERE code = ?", (code,)).fetchone():
                # Taken: a replay, or two clients with one opener.  Never replaced.
                db.rollback()
                return game({"ok": 0, "why": "code"})
            db.execute("INSERT INTO linkcodes (code, steamid, issued_at, claim, shown, seal)"
                       " VALUES (?, '', ?, ?, ?, ?)",
                       (code, now, pub, NOT_YET, "%s %s %s" % (sig, server, gcode)))
            db.commit()
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return d.fail(500, "storage error")
        log.info("link: key %s started a link on %s", pub[:16], node)
        return game({"ok": 1})

    @app.post("/api/link/wait")
    def link_wait():
        """Has anybody signed in for the code a game started?  No signature: it
        tells a keyed lobby an account's NAME for a start some key already
        holds, and changes nothing."""
        now, _src, early = lobby_call(WAIT_FLOOD_MAX, "waitflood")
        if early is not None:
            return early
        peer = peer_of(request.form.get("ip"))
        if not d.rate_ok(peer, now, WAIT_RATE_MAX, "linkwait"):
            return game({"state": "wait"})          # asked too often: it is still a wait
        db = d.get_db()
        code = live_code(db, now, request.form.get("tag") or "")
        row = None
        if code:
            row = db.execute(
                "SELECT c.steamid, c.claim, c.shown, a.name, a.banned_at FROM linkcodes c"
                " LEFT JOIN accounts a ON a.steamid = c.steamid WHERE c.code = ?",
                (code,)).fetchone()
        if row is None or not row["shown"]:
            return game({"state": "gone"})          # no such start (a typed code is not waited for)
        if not row["steamid"]:
            return game({"state": "wait"})
        if row["name"] is None or row["banned_at"]:
            return game({"state": "gone", "why": "banned" if row["name"] is not None else ""})
        old = db.execute(
            "SELECT k.steamid, a.name FROM keylinks k"
            " LEFT JOIN accounts a ON a.steamid = k.steamid WHERE k.pub = ?",
            (row["claim"],)).fetchone()
        moving = old is not None and old["steamid"] != row["steamid"]
        return game({"state": "ready", "to": game_name(row["name"]),
                     "from": game_name(old["name"]) if moving else ""})

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
                     "<h1>That did not work</h1>\n<p class=\"lede\">%s</p>\n"
                     "<p><a class=\"go\" href=\"../link\">Start again</a></p>"
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

    def installs_html(db, steamid, now, browser, quiet=False):
        """The account's linked installs, each with its unlink link.  `quiet`:
        say nothing when there are none (the page is mid-link and says so)."""
        rows = db.execute("SELECT pub, node, linked_at FROM keylinks WHERE steamid = ?"
                          " ORDER BY linked_at", (steamid,)).fetchall()
        if not rows:
            if quiet:
                return ""
            return "\n<p class=\"fine\">No install is linked to this account yet.</p>"
        items = []
        for r in rows:
            token = unlink_token("ask", now, steamid, r["pub"][:16], r["linked_at"], browser)
            items.append(
                "<li><code>%s</code> linked %s on %s%s</li>" % (
                    r["pub"][:16], time.strftime("%Y-%m-%d", time.gmtime(r["linked_at"])),
                    html.escape(r["node"]),
                    " <a href=\"unlink?t=%s\">Unlink</a>" % token if token else ""))
        return ("\n<p class=\"fine\">Installs linked to this account:</p>\n"
                "<ul class=\"installs\">\n%s\n</ul>" % "\n".join(items))

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
        _c, k = start_pair(request.args)
        return _page(0, "Link Steam", (
            "<h1>Link your Steam account</h1>\n"
            "<p class=\"lede\">%s</p>\n"
            "<p><a class=\"go\" href=\"link/steam%s\">Sign in with Steam</a></p>\n"
            "<p class=\"fine\">Steam tells FTESurf your public Steam ID, and "
            "FTESurf reads your public name and avatar. No password and nothing "
            "private reaches this site.</p>" % (
                "You started this from the game. Sign in, and this page "
                "gives you a number to type into it."
                if k else
                "Your times are ranked under your Steam name. It takes about "
                "twenty seconds.",
                "?k=" + k if k else "")))

    def return_to(state):
        """Where Steam sends the browser back.  A start's opener rides in it,
        so Steam's own signature covers which game this sign-in is for."""
        _c, k = start_pair(request.args)
        return "%s/link/return?s=%s%s" % (board_url, state, "&k=" + k if k else "")

    @app.get("/board/link/steam")
    def link_start():
        early = refuse_now(int(d.clock()))
        if early is not None:
            return early
        token = secrets.token_urlsafe(18)
        state = hashlib.sha256(token.encode("ascii")).hexdigest()[:32]
        resp = redirect(steam.login_url(realm, return_to(state)), code=302)
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
            steamid, nonce = steam.precheck(args, return_to(state), now)
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
                "SELECT COUNT(*) FROM linkcodes WHERE used_at = 0 AND steamid != ''"
                " AND issued_at >= ?", (now - CODE_TTL,)).fetchone()[0]
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
            code = shown = ""
            ended = False
            started, opener = start_pair(request.args)
            row = None
            if started and not acct["banned_at"]:
                # A code the GAME started: is this the address its own client
                # made?  The start's signature is checked HERE, now that the
                # opener it is over has arrived (link_begin).  No such start
                # and the wrong opener get the same answer, and neither
                # touches the start.
                row = db.execute(
                    "SELECT steamid, shown, claim, seal FROM linkcodes WHERE code = ?"
                    " AND used_at = 0 AND shown != '' AND issued_at >= ?",
                    (started, now - CODE_TTL)).fetchone()
                if row is None:
                    fits = False
                elif row["steamid"]:
                    # Already opened: its seal is the opener that opened it.
                    fits = _same(row["seal"], opener)
                else:
                    fits = opens(row, started, opener, now)
                if fits is None:
                    db.rollback()
                    return again("The leaderboard cannot check that right now. "
                                 "Try again in a minute.", 503)
                if not fits:
                    row = None
            if not acct["banned_at"]:
                # One live code per account: the newest.  Not the start this
                # sign-in is for, if the account already holds it (a reload).
                db.execute("UPDATE linkcodes SET used_at = ?, used_by = ?"
                           " WHERE steamid = ? AND used_at = 0 AND code != ?",
                           (now, SUPERSEDED, steamid, started))
                db.execute("DELETE FROM linkcodes WHERE issued_at < ?",
                           (now - CODE_KEEP,))
                if started:
                    # It gets this account and a number, and the page shows the
                    # number; a sign-in that came with a start's address NEVER
                    # yields a code to type.
                    if row is None:
                        ended = True
                    elif row["steamid"] == steamid:
                        shown = row["shown"]        # this account again: the same number
                    elif row["steamid"]:
                        # Two accounts for one start: neither.  Its game must
                        # not go on asking about a name its player is not.
                        db.execute("UPDATE linkcodes SET used_at = ?, used_by = ?"
                                   " WHERE code = ? AND used_at = 0", (now, CONTESTED, started))
                        ended = True
                    else:
                        shown = "".join(secrets.choice("0123456789") for _ in range(SHOWN_LEN))
                        # The signature has done its work.  What the row keeps
                        # in its place is the opener, which the confirm's
                        # number is a digest with (number_proof).
                        took = db.execute(
                            "UPDATE linkcodes SET steamid = ?, shown = ?, seal = ? WHERE code = ?"
                            " AND steamid = '' AND used_at = 0",
                            (steamid, shown, opener, started))
                        if took.rowcount != 1:
                            shown, ended = "", True
                        else:
                            # One start per key: the one somebody signed in for.
                            # Not at /api/link/start, where the key is only a claim.
                            db.execute("UPDATE linkcodes SET used_at = ?, used_by = ?"
                                       " WHERE shown != '' AND claim = ? AND used_at = 0"
                                       " AND code != ?", (now, SUPERSEDED, row["claim"], started))
                else:
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
        if acct["banned_at"]:
            log.info("link: banned account %s signed in", steamid)
            resp = _page(1, "Link Steam",
                         "<p class=\"who\">Signed in as <b>%s</b></p>\n"
                         "<h1>This account is banned</h1>\n<p class=\"lede\">This "
                         "Steam account is banned from the FTESurf leaderboards.</p>"
                         % who + installs_html(db, steamid, now, browser), 403)
        elif shown:
            log.info("link: account %s signed in for a link a game started", steamid)
            resp = _page(1, "Link Steam", (
                "<p class=\"who\">Signed in as <b>%s</b></p>\n"
                "<h1>Type this number into the game</h1>\n"
                "<p class=\"linkcode\">%s</p>\n"
                "<p class=\"lede\">Go back to FTESurf, type it into the "
                "<b>Link Steam</b> box and press <kbd>Enter</kbd>.</p>\n"
                "<p class=\"fine\">Type it only into your own game, and give it to "
                "nobody: whoever types it links their game to your Steam account. "
                "No box asking for a number? Type <kbd>link</kbd> in the game's "
                "console and start again.</p>"
                % (who, shown)) + installs_html(db, steamid, now, browser, quiet=True))
        elif ended:
            log.info("link: account %s signed in for a start that has ended", steamid)
            resp = _page(1, "Link Steam", (
                "<p class=\"who\">Signed in as <b>%s</b></p>\n"
                "<h1>Start again from the game</h1>\n"
                "<p class=\"lede\">That link is no longer waiting: it is more than "
                "ten minutes old, was replaced by a newer one, or was already used "
                "by another sign-in.</p>\n"
                "<p class=\"fine\">In FTESurf, press Esc on the Link Steam box if it "
                "is up, type <kbd>link</kbd> in the console, and use the new "
                "address it gives you.</p>"
                % who) + installs_html(db, steamid, now, browser, quiet=True))
        else:
            log.info("link: code issued for account %s", steamid)
            resp = _page(1, "Link Steam", (
                "<p class=\"who\">Signed in as <b>%s</b></p>\n"
                "<h1>Type this code into the game</h1>\n"
                "<p class=\"linkcode\">%s</p>\n"
                "<ol class=\"steps\">\n"
                "<li>Go back to FTESurf, on an official lobby.</li>\n"
                "<li>No <b>Link Steam</b> box on screen? Open the console, type "
                "<kbd>link</kbd>, press Enter, and close the console.</li>\n"
                "<li>Type the code into the box and press <kbd>Enter</kbd>.</li>\n"
                "</ol>\n"
                "<p class=\"fine\">The code works once and expires in ten minutes. Keep it to "
                "yourself: whoever types it first is linked to your account. "
                "Type it only into that box, never after a command. And only "
                "use a code you got from this page yourself: a code someone "
                "sends you links your game to their account.</p>"
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
                "SELECT k.pub, k.node, k.linked_at, a.name FROM keylinks k"
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
                    "<h1>Unlink this game?</h1>\n"
                    "<p class=\"lede\">Unlink install <code>%s</code> (linked %s on %s) from "
                    "<b>%s</b>?</p>\n<p class=\"fine\">It can be linked again at any time.</p>\n"
                    "<p><a class=\"go\" href=\"unlink?t=%s\">Unlink it</a></p>" % (
                        key16, time.strftime("%Y-%m-%d", time.gmtime(row["linked_at"])),
                        html.escape(row["node"]), who,
                        unlink_token("do", at, steamid, key16, row["linked_at"], browser))))
            db.execute("DELETE FROM keylinks WHERE pub = ?", (row["pub"],))
            db.commit()
        except sqlite3.Error:
            db.rollback()
            log.exception("link: storage error")
            return again("Something went wrong on our side. Try again in a "
                         "minute.", 500)
        log.info("link: key %s unlinked from account %s on the site", key16, steamid)
        return again("Install %s is no longer linked to %s." % (
            key16, row["name"] or "Steam account " + steamid))
