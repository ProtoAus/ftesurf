#!/usr/bin/env python3
"""
surfd - a minimal lobby directory for FTESurf.

Game servers POST heartbeats to /api/heartbeat; the game menu GETs /lobbies.json.

Deliberate design notes:
  * The lobby address is built from the request's *peer* address (REMOTE_ADDR)
    plus the client-supplied port. There is no client-supplied host field and
    ProxyFix / X-Forwarded-For is NOT honoured, so a heartbeat can never
    advertise a lobby on somebody else's host. If this service is ever put
    behind a reverse proxy, that decision has to be revisited on purpose.
  * SURFD_PUBLIC_HOST is the one exception, and it does not weaken the above.
    See the essay over PUBLIC_HOST.
  * A heartbeat is untrusted network input: every field is length-capped,
    range-clamped or rejected, the request body is capped, the number of
    distinct nodes is capped, and each source IP is rate limited.
"""

import hmac
import ipaddress
import json
import logging
import logging.handlers
import os
import re
import sqlite3
import threading
import time

from flask import Flask, Response, g, jsonify, request

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = os.environ.get("SURFD_HOME", "/srv/nvme/surfd")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.environ.get("SURFD_DB", os.path.join(DATA_DIR, "surfd.db"))
ENV_PATH = os.environ.get("SURFD_ENV", os.path.join(BASE_DIR, "surfd.env"))
LOG_PATH = os.path.join(LOG_DIR, "surfd.log")

LOBBY_TTL = 30           # seconds; a lobby older than this is not "live"
REAP_AFTER = 3600        # seconds; rows older than this are deleted outright
MAX_NODES = 200          # hard cap on distinct nodes stored
MAX_FIELD_LEN = 64       # per the API contract
MAX_BODY = 16 * 1024     # bytes; a heartbeat is a few hundred bytes at most

RATE_WINDOW = 60         # seconds
RATE_MAX = 60            # heartbeats per window per source IP
RATE_TABLE_MAX = 4096    # cap the limiter's own memory

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------
# Logging: to a file under BASE_DIR *and* to stdout.
# --------------------------------------------------------------------------

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

log = logging.getLogger("surfd")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    _fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(process)d] %(message)s",
        "%Y-%m-%dT%H:%M:%S%z",
    )
    _fh = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=5
    )
    _fh.setFormatter(_fmt)
    log.addHandler(_fh)
    _sh = logging.StreamHandler()   # -> gunicorn's stdout
    _sh.setFormatter(_fmt)
    log.addHandler(_sh)


# --------------------------------------------------------------------------
# PUBLIC_HOST -- the one place a lobby address does not come from the socket.
#
# THE PROBLEM.  surfd and the three game servers run on the same NanoPi, so
# REMOTE_ADDR for a heartbeat is structurally private -- 127.0.0.1 if they talk
# over loopback, 192.168.1.102 if over the LAN.  Put nginx in front and it
# becomes 127.0.0.1 for certain.  So `addr = REMOTE_ADDR + ":" + port` emits a
# LAN address, and every remote player is handed a lobby they cannot reach.
# No amount of game-side change fixes this: the heartbeat deliberately sends no
# address at all (src/server/sv_lobby.qc:1253-1255).
#
# WHY NOT X-Forwarded-For.  Because it is CLIENT-controlled.  The original
# design rejected it for exactly the right reason and that reason has not
# changed; a heartbeat that could name its own host could advertise a lobby on
# somebody else's machine, and that was verified adversarially (a heartbeat
# carrying addr=, ip=, host= and a spoofed XFF was recorded as the socket peer
# and every decoy ignored -- ENGINE_PATCHES.md:21741-21747).
#
# WHAT THIS DOES INSTEAD -- and note the trust direction is reversed, which is
# the whole point:
#
#   the OPERATOR'S OWN CONFIG supplies the public name (SURFD_PUBLIC_HOST),
#   and the SOCKET is used only to decide whether this heartbeat came from the
#   operator's own machine (SURFD_TRUSTED).
#
# A stranger on the internet still cannot choose the host half of their address
# under any circumstances: they are not in TRUSTED_SOURCES, so they get
# REMOTE_ADDR exactly as before.  The heartbeat body is never consulted for a
# host, here or anywhere, and it must stay that way -- that would be the same
# mistake wearing a different hat.
#
# What they CAN still choose is the PORT half, because the game server has to
# tell us which port it bound.  That was true before this change and is
# unchanged by it: a valid key lets you point players at an arbitrary port on
# your own IP.  The client-side mitigation is the lobby_hosts allow-list in the
# menu, which refuses to `connect` to a host it was not shipped knowing about.
#
# DEFAULT IS OFF.  With SURFD_PUBLIC_HOST unset this file behaves exactly as it
# did before, byte for byte, which is what makes the change falsifiable.
# --------------------------------------------------------------------------

_HOSTNAME_OK = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,62}[A-Za-z0-9])?$")


def load_public_host(raw):
    """Validate SURFD_PUBLIC_HOST. Returns "" (off) or a safe bare host.

    This string is handed to the game menu, which hands it to the engine's
    `connect` command, so it is validated here as tightly as the menu validates
    it on the way in (ui_addr_ok, src/menu/m_main.qc:1539-1557).  A scheme, a
    port, a path or a space is a configuration mistake, not something to pass
    through and discover later as a broken row in everybody's picker.
    """
    host = (raw or "").strip()
    if not host:
        return ""
    for bad in ("://", "/", " ", "\t", "@", "?", "#"):
        if bad in host:
            log.error("SURFD_PUBLIC_HOST %r contains %r -- want a bare host, "
                      "no scheme, no port, no path. Ignoring it.", host, bad)
            return ""
    if ":" in host:
        # An IPv6 literal is the only legitimate colon, and it would need
        # brackets in an addr:port string -- which the menu's allow-list does
        # not accept. Refuse rather than emit something unusable.
        log.error("SURFD_PUBLIC_HOST %r contains a colon -- the port comes from "
                  "the heartbeat, and IPv6 literals are not supported. Ignoring it.",
                  host)
        return ""
    try:
        ipaddress.ip_address(host)
        return host                     # a bare IPv4 literal is fine
    except ValueError:
        pass
    if not _HOSTNAME_OK.match(host):
        log.error("SURFD_PUBLIC_HOST %r is not a valid hostname. Ignoring it.", host)
        return ""
    # The menu accepts an addr of 3..64 characters (ui_addr_ok), and we are
    # about to append ":<port>" -- up to six more.  A host longer than 58 would
    # produce rows every client silently refuses to connect to, which is a much
    # harder failure to diagnose from the picker than a line in this log.
    if len(host) > 64 - len(":65535"):
        log.error("SURFD_PUBLIC_HOST %r is %d chars; with a port it exceeds the "
                  "64 the game menu accepts. Ignoring it.", host, len(host))
        return ""
    return host


def load_trusted(raw):
    """Parse SURFD_TRUSTED, a comma-separated CIDR list."""
    nets = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            log.error("SURFD_TRUSTED entry %r is not a network. Ignoring it.", part)
    return nets


def is_trusted(ip, nets):
    if not nets:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # An IPv4 heartbeat arriving over a v6 socket shows up as ::ffff:a.b.c.d.
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    return any(addr in net for net in nets)


# --------------------------------------------------------------------------
# Settings: the environment first, then surfd.env
# --------------------------------------------------------------------------
#
# READ BOTH, BECAUSE surfd.service HAS NO EnvironmentFile= LINE. It sets only
# SURFD_HOME, so nothing in surfd.env ever reaches the process environment;
# this file has always gotten away with that because load_secret() parses the
# file itself for SURFD_KEY.
#
# Every OTHER setting used to be read with a bare os.environ.get(), which meant
# putting it in surfd.env did exactly nothing, silently. That already cost one
# outage: the admin panel logged "SURFD_ADMIN_HASH is unset" with the hash
# sitting in the file, and it could never have worked.
#
# For SURFD_PUBLIC_HOST the same bug would have been worse than an outage. The
# operator sets it at the moment they go public; if it were ignored, surfd would
# keep advertising 192.168.1.102 to the whole internet and every row in the
# directory would be unreachable -- with no error anywhere, because "unset" is a
# supported configuration. Read the file.

def env_file_value(name, path=None):
    """One value out of the shell-sourceable env file, or None if not present.

    None means ABSENT and "" means PRESENT AND EMPTY, and the difference is not
    pedantry -- see setting() below.
    """
    try:
        with open(path or ENV_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == name:
                    return value.strip().strip("'\"")
    except OSError:
        return None
    return None


def setting(name, default=None):
    """Environment first, then surfd.env, then `default`.

    RETURNS AN EMPTY STRING IF THE NAME IS SET TO ONE. Absent and
    present-but-empty are different configurations and collapsing them is a
    bug with teeth: an operator who writes

        SURFD_TRUSTED=

    means "trust nothing, do not rewrite any address". Treating that as unset
    would hand back the DEFAULT trust list -- which includes the whole LAN --
    and quietly re-enable the very rewrite they just turned off. os.environ.get
    already draws this distinction; anything layered over it must keep it.
    """
    if name in os.environ:
        return os.environ[name]
    value = env_file_value(name)
    return default if value is None else value


PUBLIC_HOST = load_public_host(setting("SURFD_PUBLIC_HOST"))
TRUSTED_SOURCES = load_trusted(
    setting("SURFD_TRUSTED", "127.0.0.0/8,::1/128,192.168.0.0/16,10.0.0.0/8")
)
if PUBLIC_HOST:
    log.info("advertising trusted lobbies as %s:<port>", PUBLIC_HOST)


# --------------------------------------------------------------------------
# Shared secret
# --------------------------------------------------------------------------

def load_secret(path=ENV_PATH):
    """Read SURFD_KEY out of the (shell-sourceable) env file."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "SURFD_KEY":
                    return value.strip().strip("'\"")
    except OSError as exc:
        log.error("cannot read secret file %s: %s", path, exc)
        return None
    log.error("secret file %s has no SURFD_KEY", path)
    return None


SECRET = load_secret()
if not SECRET:
    log.error("no shared secret loaded - every heartbeat will be rejected")


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def migrate():
    """Create/upgrade the schema on start. Safe to run every boot."""
    conn = connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS lobbies (
                    node       TEXT    PRIMARY KEY,
                    map        TEXT    NOT NULL,
                    players    INTEGER NOT NULL,
                    maxplayers INTEGER NOT NULL,
                    addr       TEXT    NOT NULL,
                    name       TEXT    NOT NULL,
                    last_seen  INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS lobbies_last_seen
                    ON lobbies (last_seen);
                """
            )
            conn.execute("PRAGMA user_version=1")
            conn.commit()
            log.info("schema migrated to version %d (db=%s)", SCHEMA_VERSION, DB_PATH)
        else:
            log.info("schema already at version %d (db=%s)", version, DB_PATH)
    finally:
        conn.close()


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


# --------------------------------------------------------------------------
# Rate limiting (in-process; gunicorn runs a single worker on purpose)
# --------------------------------------------------------------------------

_rate_lock = threading.Lock()
_rate = {}   # ip -> [timestamps]


def rate_ok(ip, now):
    with _rate_lock:
        if len(_rate) > RATE_TABLE_MAX:
            cutoff = now - RATE_WINDOW
            for key in [k for k, v in _rate.items() if not v or v[-1] < cutoff]:
                del _rate[key]
            if len(_rate) > RATE_TABLE_MAX:
                _rate.clear()
                log.warning("rate limiter table flushed under pressure")
        hits = [t for t in _rate.get(ip, ()) if t > now - RATE_WINDOW]
        if len(hits) >= RATE_MAX:
            _rate[ip] = hits
            return False
        hits.append(now)
        _rate[ip] = hits
        return True


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(raw, limit=MAX_FIELD_LEN):
    """Strip control characters and truncate. Never trust length or content."""
    if raw is None:
        return ""
    return _CTRL.sub("", str(raw)).strip()[:limit]


def clamp_int(raw, low, high, default=None):
    """Parse an integer and clamp it into range. None if unparseable."""
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def strict_int(raw, low, high):
    """Parse an integer, rejecting (None) anything out of range."""
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if low <= value <= high else None


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY
try:
    app.json.sort_keys = False        # keep the documented key order
except Exception:                     # pragma: no cover - older Flask
    app.config["JSON_SORT_KEYS"] = False


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def fail(code, message):
    resp = jsonify({"ok": False, "error": message})
    resp.status_code = code
    return resp


@app.post("/api/heartbeat")
def heartbeat():
    now = int(time.time())
    src = request.remote_addr or "0.0.0.0"

    if not rate_ok(src, now):
        log.warning("rate limited %s", src)
        return fail(429, "rate limited")

    # --- auth ------------------------------------------------------------
    key = request.form.get("key", "")
    if not SECRET or not key or not hmac.compare_digest(str(key), SECRET):
        log.warning("rejected heartbeat from %s: bad key", src)
        return fail(403, "forbidden")

    # --- validate --------------------------------------------------------
    node = clean_text(request.form.get("node"))
    mapname = clean_text(request.form.get("map"))
    if not node:
        return fail(400, "missing node")
    if not mapname:
        return fail(400, "missing map")

    port = strict_int(request.form.get("port"), 1, 65535)
    if port is None:
        return fail(400, "bad port")

    players = clamp_int(request.form.get("players"), 0, 64, 0)
    maxplayers = clamp_int(request.form.get("max"), 1, 64, 1)
    name = clean_text(request.form.get("name")) or node

    # The address the picker will hand to `connect`.  See the PUBLIC_HOST essay:
    # the operator's config supplies the host, the socket only decides whether
    # this heartbeat is the operator's own.  Anything untrusted takes the
    # original path unchanged.
    if PUBLIC_HOST and is_trusted(src, TRUSTED_SOURCES):
        addr = "%s:%d" % (PUBLIC_HOST, port)
    else:
        addr = "%s:%d" % (src, port)

    db = get_db()
    try:
        with db:
            db.execute("DELETE FROM lobbies WHERE last_seen < ?", (now - REAP_AFTER,))
            known = db.execute(
                "SELECT 1 FROM lobbies WHERE node = ?", (node,)
            ).fetchone()
            if known is None:
                count = db.execute("SELECT COUNT(*) FROM lobbies").fetchone()[0]
                if count >= MAX_NODES:
                    # make room by dropping everything already dead
                    db.execute(
                        "DELETE FROM lobbies WHERE last_seen < ?", (now - LOBBY_TTL,)
                    )
                    count = db.execute("SELECT COUNT(*) FROM lobbies").fetchone()[0]
                if count >= MAX_NODES:
                    log.warning(
                        "node cap %d reached, refusing new node %r from %s",
                        MAX_NODES, node, src,
                    )
                    return fail(429, "node limit reached")
            db.execute(
                """
                INSERT INTO lobbies (node, map, players, maxplayers, addr, name, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node) DO UPDATE SET
                    map        = excluded.map,
                    players    = excluded.players,
                    maxplayers = excluded.maxplayers,
                    addr       = excluded.addr,
                    name       = excluded.name,
                    last_seen  = excluded.last_seen
                """,
                (node, mapname, players, maxplayers, addr, name, now),
            )
    except sqlite3.Error as exc:
        log.exception("heartbeat db error from %s: %s", src, exc)
        return fail(500, "storage error")

    log.info(
        "heartbeat node=%r map=%r players=%d/%d addr=%s",
        node, mapname, players, maxplayers, addr,
    )
    return Response("ok", status=200, mimetype="text/plain")


def live_rows(now):
    db = get_db()
    return db.execute(
        """
        SELECT map, players, maxplayers, addr, name, last_seen
          FROM lobbies
         WHERE last_seen > ?
         ORDER BY players DESC, map ASC
        """,
        (now - LOBBY_TTL,),
    ).fetchall()


@app.get("/lobbies.json")
def lobbies_json():
    now = int(time.time())
    lobbies = []
    try:
        for row in live_rows(now):
            lobbies.append(
                {
                    "map": row["map"],
                    "players": row["players"],
                    "max": row["maxplayers"],
                    "addr": row["addr"],
                    "name": row["name"],
                    "age": max(0, now - row["last_seen"]),
                }
            )
    except sqlite3.Error as exc:
        # The menu must always get parseable JSON with a lobbies array.
        log.exception("lobbies.json db error: %s", exc)
    body = json.dumps({"v": 1, "t": now, "lobbies": lobbies}, separators=(",", ":"))
    return Response(body, status=200, mimetype="application/json")


@app.get("/health")
def health():
    now = int(time.time())
    try:
        count = len(live_rows(now))
    except sqlite3.Error as exc:
        log.exception("health db error: %s", exc)
        return fail(500, "storage error")
    return jsonify({"ok": True, "lobbies": count})


@app.errorhandler(404)
def not_found(_e):
    return fail(404, "not found")


@app.errorhandler(405)
def bad_method(_e):
    return fail(405, "method not allowed")


@app.errorhandler(413)
def too_large(_e):
    return fail(413, "request too large")


@app.errorhandler(500)
def server_error(_e):                 # pragma: no cover
    return fail(500, "internal error")


# --------------------------------------------------------------------------
# Admin panel -- optional, and OFF unless explicitly configured.
#
# The import is guarded so that a missing or broken admin.py degrades surfd to
# exactly what it was before the panel existed. The directory service is what
# players depend on; the panel is what one operator depends on, and the two
# must not be able to take each other down. build_blueprint() returns None when
# SURFD_ADMIN_HASH is unset, so the default install registers no /admin routes
# at all -- test_admin.py asserts that, because "off by default" is only true
# if something checks.
# --------------------------------------------------------------------------

def _register_admin():
    try:
        from admin import build_blueprint
    except Exception as exc:                       # pragma: no cover
        log.error("admin panel unavailable (import failed: %s)", exc)
        return
    try:
        bp = build_blueprint(app, log, connect, LOBBY_TTL)
    except Exception as exc:                       # pragma: no cover
        log.exception("admin panel failed to configure: %s", exc)
        return
    if bp is not None:
        app.register_blueprint(bp)


_register_admin()

migrate()
log.info("surfd ready (db=%s ttl=%ds cap=%d nodes)", DB_PATH, LOBBY_TTL, MAX_NODES)
if PUBLIC_HOST:
    log.info("public host %r for heartbeats from %s; everything else keeps its "
             "own source address", PUBLIC_HOST,
             ",".join(str(n) for n in TRUSTED_SOURCES) or "(nothing -- "
             "SURFD_TRUSTED is empty, so PUBLIC_HOST will never be used)")
else:
    log.info("no SURFD_PUBLIC_HOST: every lobby is advertised at the address it "
             "heartbeats from. Correct on a LAN; wrong the moment this is public.")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8084)
