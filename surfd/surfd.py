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
RATE_MAX = 150           # heartbeats per window per source IP -- see below
RATE_TABLE_MAX = 4096    # cap the limiter's own memory

# RATE_MAX IS 150, NOT 60, OR THE PI'S OWN LOBBIES BLINK OUT OF THE DIRECTORY.
#
# Every lobby posts from the same source address -- 127.0.0.1, because surfd
# is on the same Pi -- once per lobby_master_rate, which cfg/lobby.cfg sets to
# 5 s. One lobby is 12 heartbeats a minute; five lobbies are 5 x 12 = 60, which
# was this cap exactly. At exactly the cap there is no slack: an arriving beat
# finds the other 59 of the last minute still in the window, so any beat that
# counts as a second early is the 60th and gets a 429. Beats do arrive early.
# Lobby_Heartbeat's next-send time is a QC global that does not survive a map
# change or a restart, so a lobby beats at once on every new map however
# recently it last beat; the POST is asynchronous and this is one worker, so
# arrival times wobble; and `now` is truncated to a whole second, which turns
# a wobble of a tenth into a whole second.
#
# A refused beat is not retried -- the lobby waits for its next one -- so each
# 429 leaves that lobby's row one beat staler, and a lobby refused six times
# running is older than LOBBY_TTL and vanishes from /lobbies.json while it is
# up and full of players.
#
# 150 is 2.5 times the five-lobby load: room for all of that and for more
# lobbies at the same rate (twelve would be 144), while one address is still
# held to 2.5 requests a second. test_surfd.py plays five lobbies' traffic for
# two simulated minutes against this value, and against 60 as the control.

# --------------------------------------------------------------------------
# The leaderboard (schema 2)
# --------------------------------------------------------------------------
#
# RUN SUBMISSIONS GET THEIR OWN RATE BUCKET, AND THAT IS NOT TIDINESS.
#
# rate_ok keys on the source IP alone, and every lobby on this Pi posts from
# 127.0.0.1.  The essay above spends 20 lines establishing that the five
# lobbies sit at 60 beats a minute against a cap of 150, that a refused beat is
# never retried, and that six refusals running drop a live lobby out of
# /lobbies.json.  A run submission from those same five servers lands in that
# same bucket.  A busy evening -- five lobbies, a finish every few seconds --
# would therefore take the lobbies off the map picker, and the symptom would
# be "the directory is flaky", a mile from the cause.
#
# So run submissions are counted separately and the heartbeat's proven number
# is left exactly as it was.  test_board.py section 5 plays a submission flood
# and asserts the heartbeat still gets through, because a limit nobody floods
# is a claim rather than a limit.
# THE HEARTBEAT CAP HAS TO SCALE WITH THE CLUSTER, AND 150 DOES NOT.
#
# The essay above sized RATE_MAX for FIVE lobbies: 5 nodes x 12 beats/minute
# (lobby_master_rate 5) = 60, and 150 is 2.5x that for headroom.  Under FTE's
# mapcluster there is one server PROCESS PER LIVE MAP, each running the same
# QC and therefore each heartbeating at the same cadence, so the load is
# 12 x N.  At 150 that ceiling is 12 NODES -- and the Pi's RAM ceiling is
# 8-16 concurrent heavy maps, or ~24-30 curated to the median.  So this number
# would have bitten first, and its symptom is the one the essay above already
# describes: refused beats, staler rows, nodes vanishing from the map picker
# while they are up and full of players.  "The directory is flaky" is a long
# way from "a constant sized for five lobbies".
#
# RAISED ONLY FOR TRUSTED SOURCES, which is the part that matters.  A cluster's
# nodes are on the operator's own machines and arrive from 127.0.0.1 or the
# LAN; TRUSTED_SOURCES already decides exactly that question, and already
# governs the strictly more sensitive choice of whether a heartbeat may
# advertise itself as PUBLIC_HOST.  So this adds no new trust surface at all:
# if the operator has not configured trust, nothing changes from today.
# Checked before relying on it: no nginx site proxies to 8084, so REMOTE_ADDR
# is the real peer and loopback genuinely means this machine.  An untrusted
# source keeps 150, unchanged and still proven by test_surfd.py's control.
CLUSTER_NODES_PLANNED = 64          # well past the RAM ceiling, deliberately
RATE_MAX_TRUSTED = int(2.5 * CLUSTER_NODES_PLANNED * (60 / 5))   # = 1920

RUN_RATE_MAX = 120       # run submissions per RATE_WINDOW per source IP

MAX_RUNS = 200000        # hard cap on stored rows; see the reap in submit_run
MAX_MAP_LEN = 64         # a map name is a directory component on the client
MAX_TRACK = 63           # zone_track: 0 main, 1+ bonus
MAX_LEG = 63             # FS_LegOf: 0 the full track, k stage k
MAX_TICKS = 100000000    # ~17 days at 66.67 Hz; refuses an overflowed claim
BOARD_LIMIT_MAX = 200    # rows one /api/board call may return
BOARD_LIMIT_DEF = 50

# Trust tiers.  See the essay on submit_run: this is the plan's Layer 0, and it
# is decided by WHO HOLDS THE KEY rather than by anything the run says.
TIER_RANKED = "ranked"
TIER_COMMUNITY = "community"
TIERS = (TIER_RANKED, TIER_COMMUNITY)

# Run styles -- the client's own vocabulary (sh_defs.qc: FS_RunClass).  Derived
# here from `flags`, never taken from the submitter; see style_of.
STYLE_CLEAN = "clean"
STYLE_SEGMENTED = "segmented"
STYLES = (STYLE_CLEAN, STYLE_SEGMENTED)

# sh_defs.qc's TF_* word, as it stood AT THE FINISH.  Kept in sync by name, and
# test_board.py pins each value against the QC header so a renumber there fails
# here rather than silently re-classifying every run on the board.
TF_PRACTICE = 1
TF_SHADOW = 8
TF_SEGMENT = 128
TF_CHEAT = 256
TF_NOJOURNAL = 512
TF_NORULESET = 1024

SCHEMA_VERSION = 2


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
# THE PROBLEM.  surfd and the five game servers run on the same NanoPi, so
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
# SURFD_PROXIES -- who is allowed to TELL US who the client is.
# --------------------------------------------------------------------------
#
# This is NOT the same list as SURFD_TRUSTED and it must never be merged with
# it, however similar the two look.
#
#   SURFD_TRUSTED   "this source may be advertised under PUBLIC_HOST, and gets
#                   the larger heartbeat cap" -- a statement about GAME SERVERS.
#                   It defaults to whole private ranges: 192.168/16, 10/8.
#   SURFD_PROXIES   "this source's X-Real-IP header is the truth" -- a statement
#                   about OUR OWN reverse proxy, and nothing else.
#
# THE DEFAULT IS LOOPBACK ONLY, AND THE NARROWNESS IS THE WHOLE SECURITY
# PROPERTY.  Anyone inside a SURFD_PROXIES range can choose their own
# rate-limit identity and therefore evade the limiter entirely; at
# 192.168.0.0/16 -- which SURFD_TRUSTED really does contain -- that would be
# every machine on the LAN.  nginx runs on this box, so a /32 of loopback is
# all this ever needs to be.
#
# WHY A HEADER IS INVOLVED AT ALL.  The moment a rate-limited read endpoint is
# proxied, request.remote_addr is 127.0.0.1 for every player in the world, so a
# per-IP limiter silently becomes ONE GLOBAL BUCKET -- which is worse than no
# limiter, because one stranger can then spend everybody's budget and take the
# leaderboard away from the whole game.  The identity has to come from the only
# party that still knows it, and that is nginx.
#
# X-Real-IP AND NOT X-Forwarded-For.  nginx sets X-Real-IP with
# `proxy_set_header X-Real-IP $remote_addr`, which OVERWRITES whatever the
# client sent.  X-Forwarded-For is conventionally built with
# $proxy_add_x_forwarded_for, which APPENDS to the client's own value -- so its
# left-hand entries are attacker-authored text.  One is a statement by our
# proxy; the other is a statement by the caller wearing our proxy's coat.
#
# READ ENDPOINTS ONLY.  /api/heartbeat keeps deriving the lobby address from the
# socket peer (see the PUBLIC_HOST essay), which is exactly why the heartbeat is
# kept off the public vhost at all, and nothing here changes that.
PROXY_SOURCES = load_trusted(setting("SURFD_PROXIES", "127.0.0.1/32,::1/128"))


def client_identity():
    """Who is calling, and whether that answer is worth anything.

    Returns ``(address, attributed)``.

    ``attributed`` is FALSE exactly when the address names a party that many
    unrelated callers share -- i.e. the request came through one of our own
    proxies and that proxy did not say who it was speaking for.  The address is
    still the best available and is fine as a rate-limit bucket; what it must
    not be used for is any decision that PUNISHES the address, because the
    punishment would land on everyone behind it.  /admin's login lockout is
    that decision, which is why this returns the flag rather than hiding it.

    Never raises.
    """
    src = request.remote_addr or "0.0.0.0"
    if not is_trusted(src, PROXY_SOURCES):
        return src, True                    # the socket peer IS the caller

    claimed = (request.headers.get("X-Real-IP") or "").strip()
    if not claimed:
        return src, False                   # our proxy, speaking for nobody

    try:
        # Parsed, not passed through.  This value becomes a key in the
        # limiter's table, so an unvalidated header would let one
        # misconfigured proxy fill RATE_TABLE_MAX with junk and evict the
        # real entries -- failing the limiter open, quietly.
        ipaddress.ip_address(claimed)
    except ValueError:
        log.warning("X-Real-IP from %s is not an address (%r); using the peer",
                    src, claimed[:64])
        return src, False
    return claimed, True


def rate_key():
    """The address to rate-limit this request against.

    The socket peer -- except when the peer is one of our own reverse proxies
    AND has told us who it is speaking for.  Returns a string; never raises.

    A rate limiter is the one consumer that is content with an unattributed
    answer: sharing a bucket degrades service for the people behind a
    misconfigured proxy, which is bad, but it does not hand a stranger a lever
    over anyone else.  So this deliberately drops the flag.
    """
    return client_identity()[0]


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
    """Create/upgrade the schema on start. Safe to run every boot.

    STEPWISE, and each step sets its OWN version rather than jumping to
    SCHEMA_VERSION.  Before schema 2 there was one step, so "migrate then stamp
    the module constant" and "stamp what you actually did" were the same
    number and the difference could not show.  They are not the same number
    now: a v1 database upgraded by a v2 binary runs step 2 only, and a jump to
    SCHEMA_VERSION would stamp a fresh database as 2 having run step 1 alone.
    """
    conn = connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        started = version

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
            version = 1

        if version < 2:
            # ONE ROW PER PLAYER PER BOARD, not one row per run.  Lex's ask is
            # "players best times ranked", and a board of every attempt is a
            # different thing that also grows without bound.  The primary key
            # is therefore the board key plus the player, and submit_run
            # replaces a row only on an improvement.
            #
            # WHY tier AND style ARE BOTH IN THE KEY.  They are orthogonal
            # axes and each would corrupt the other if collapsed:
            #
            #   tier   how much the time is trusted -- ranked vs community.
            #          Out of the key, a community run on a player-hosted
            #          server would overwrite that player's ranked time, and
            #          the ranked board would be editable by anyone who can
            #          host.  That is the exact hole Layer 0 exists to close.
            #   style  what kind of run -- clean vs segmented.  Out of the
            #          key, a player could not hold both a clean PB and a
            #          segmented PB, and the two tabs would fight over one
            #          row.  They are peer achievements, not competitors.
            #
            # millis IS THE RANK KEY, NOT ticks.  A tick only means a duration
            # at a tickrate, and pm_ticrate is a movement cvar -- locked on a
            # conforming server, but the board must not be the thing that
            # assumes so.  ticks is kept beside it because it is the exact
            # integer the game ranks and names files by (FS_RunStamp).
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    map        TEXT    NOT NULL,
                    track      INTEGER NOT NULL,
                    leg        INTEGER NOT NULL,
                    tier       TEXT    NOT NULL,
                    style      TEXT    NOT NULL,
                    player     TEXT    NOT NULL,
                    name       TEXT    NOT NULL,
                    ticks      INTEGER NOT NULL,
                    tickrate   REAL    NOT NULL,
                    millis     INTEGER NOT NULL,
                    flags      INTEGER NOT NULL,
                    node       TEXT    NOT NULL,
                    runid      TEXT    NOT NULL,
                    submitted  INTEGER NOT NULL,
                    PRIMARY KEY (map, track, leg, tier, style, player)
                );
                CREATE INDEX IF NOT EXISTS runs_board
                    ON runs (map, track, leg, tier, style, millis, submitted);
                """
            )
            conn.execute("PRAGMA user_version=2")
            conn.commit()
            version = 2

        if version == started:
            log.info("schema already at version %d (db=%s)", version, DB_PATH)
        else:
            log.info(
                "schema migrated %d -> %d (db=%s)", started, version, DB_PATH
            )
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


def rate_ok(ip, now, cap=None, bucket=""):
    """Is this source allowed another request in `bucket` right now?

    `bucket` SEPARATES THE COUNTS, and the default is the empty string so the
    heartbeat's call site and its proven cap are byte-for-byte what they were.
    See the RUN_RATE_MAX essay: every lobby on the Pi posts from 127.0.0.1, so
    a shared bucket would let run submissions spend the heartbeat's budget and
    take live lobbies out of /lobbies.json.

    `cap` DEFAULTS TO None AND IS RESOLVED IN THE BODY, not written as
    `cap=RATE_MAX` in the signature.  A default argument is evaluated once when
    the function is defined, so the signature form would freeze the cap at
    import and ignore RATE_MAX thereafter -- which is precisely how
    test_surfd.py's control works (it sets mod.RATE_MAX = 60 and replays the
    five lobbies' traffic expecting a 429).  Written the other way the control
    stopped producing its 429, and a control that cannot fail is not one.
    """
    if cap is None:
        cap = RATE_MAX
    key = (bucket, ip)
    with _rate_lock:
        if len(_rate) > RATE_TABLE_MAX:
            cutoff = now - RATE_WINDOW
            for k in [k for k, v in _rate.items() if not v or v[-1] < cutoff]:
                del _rate[k]
            if len(_rate) > RATE_TABLE_MAX:
                _rate.clear()
                log.warning("rate limiter table flushed under pressure")
        hits = [t for t in _rate.get(key, ()) if t > now - RATE_WINDOW]
        if len(hits) >= cap:
            _rate[key] = hits
            return False
        hits.append(now)
        _rate[key] = hits
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


def strict_float(raw, low, high):
    """Parse a finite float, rejecting (None) anything out of range."""
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None            # NaN and infinities: "nan"/"inf" parse happily
    return value if low <= value <= high else None


# A map name is a DIRECTORY COMPONENT on the client (FS_RunDir builds
# data/runs/<map>/<leg>/), and it comes back out of this service into that
# path.  clean_text alone would pass "../../etc" and "a/b" through, so the
# board's spelling of a map name is deliberately narrower than the
# directory's: the character set Momentum's library actually uses, and
# nothing that can traverse or separate.
_MAPNAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}$")


def clean_map(raw):
    """The map name, or None if it is not one we will put in a path.

    TOO LONG IS REFUSED, NOT TRUNCATED, and that is the whole reason this does
    not just call clean_text(raw, MAX_MAP_LEN).  A map name is an IDENTIFIER --
    it is the board key -- and trimming one to fit merges two boards into one
    without a word: every map sharing the first 64 characters would rank
    against every other.  clean_text's truncation is right for a display name
    and wrong for a key.  Caught by test_board.py section 3, which submitted a
    65-character name and then found the 64-character one already occupied.
    """
    name = clean_text(raw, MAX_MAP_LEN + 1).lower()
    if not name or len(name) > MAX_MAP_LEN or ".." in name:
        return None
    return name if _MAPNAME_OK.match(name) else None


def style_of(flags):
    """Which board this run belongs on, or None if it belongs on none.

    A MIRROR OF sh_defs.qc's FS_RunClass, INCLUDING ITS PRECEDENCE, and the
    precedence is the reason this is not four independent tests: a run that
    saved-loaded and then cheated carries both bits, and a reader that tested
    segment first would file the worse run under the gentler word.  Cheat
    outranks segment outranks practice, there and here.

    DERIVED FROM flags, NEVER TAKEN FROM THE SUBMITTER.  A submitter can lie
    about the flags word -- that is what the tier is for -- but it cannot send
    a flags word saying "segmented" and a style saying "clean" and have the
    two disagree, because there is only one of them on the wire.

    Practice and cheated runs are refused outright rather than given a board.
    They are not ranked anywhere in this game and a board nobody reads is a
    place for them to accumulate.
    """
    if flags & TF_CHEAT:
        return None
    if flags & (TF_SEGMENT | TF_SHADOW):
        return STYLE_SEGMENTED
    if flags & TF_PRACTICE:
        return None
    return STYLE_CLEAN


def certifiable(flags):
    """May this run stand on the RANKED board?

    THIS IS THE FIRST CONSUMER OF TF_NOJOURNAL AND TF_NORULESET, which have
    been recorded, archived and reported since QC builds 58 and 62 with
    nothing downstream that acted on them.

    Both describe a hole in the CERTIFICATION rather than something the player
    did -- no input journal beside the run, or physics that cannot be shown to
    have been the ruleset's -- so neither may call anyone a cheat.  The tree's
    standing rule is that a quiet gate survives a false negative where an
    accusation does not, and a tier demotion is exactly that quiet gate: the
    run still stands on the community board under the player's name, and only
    the ranked board declines it.
    """
    return not (flags & (TF_NOJOURNAL | TF_NORULESET))


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

    # A cluster's nodes all beat from the operator's own address; see the
    # RATE_MAX_TRUSTED essay. Untrusted sources keep the original cap.
    if not rate_ok(src, now,
                   RATE_MAX_TRUSTED if is_trusted(src, TRUSTED_SOURCES)
                   else RATE_MAX):
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


# --------------------------------------------------------------------------
# The leaderboard
# --------------------------------------------------------------------------
#
# WHO MAY WRITE TO THE BOARD IS THE WHOLE SECURITY MODEL, and it is settled by
# the same SECRET the heartbeat uses rather than by anything clever.
#
# A leaderboard fed by player-hosted servers is forgeable by the host with no
# cheating skill at all: on a listen server the host owns sv.time, the movement
# cvars, the progs and the timer, so "beat the world record" is a cvar edit.
# The plan calls that tier T3 and calls it the structural hole, ahead of every
# input-layer concern.
#
# Requiring the server key to POST closes it without a line of policy code:
# only a server the operator has keyed can put a row on the board, which IS
# the "Ranked = official servers only" decision.  A player-hosted server holds
# no key, gets 403, and keeps its times locally -- which is the Local tab, and
# is already built (cl_scores.qc).
#
# What this deliberately does NOT do is authenticate the PLAYER.  surfd has no
# player identity yet; `player` is whatever id the client generates for itself,
# and a keyed server vouches for it.  So a row means "an official server saw
# this player finish", not "this human finished".  The local-keypair work in
# Phase 2 is what upgrades that, and it is a VALUE change in this column rather
# than a schema change -- which is why the column exists now and is separate
# from the display name.


@app.post("/api/run")
def submit_run():
    now = int(time.time())
    src = request.remote_addr or "0.0.0.0"

    if not rate_ok(src, now, RUN_RATE_MAX, "run"):
        log.warning("rate limited run submission from %s", src)
        return fail(429, "rate limited")

    key = request.form.get("key", "")
    if not SECRET or not key or not hmac.compare_digest(str(key), SECRET):
        log.warning("rejected run from %s: bad key", src)
        return fail(403, "forbidden")

    mapname = clean_map(request.form.get("map"))
    if not mapname:
        return fail(400, "bad map")

    track = strict_int(request.form.get("track"), 0, MAX_TRACK)
    if track is None:
        return fail(400, "bad track")

    leg = strict_int(request.form.get("leg"), 0, MAX_LEG)
    if leg is None:
        return fail(400, "bad leg")

    player = clean_text(request.form.get("player"))
    if not player:
        return fail(400, "missing player")

    ticks = strict_int(request.form.get("ticks"), 1, MAX_TICKS)
    if ticks is None:
        return fail(400, "bad ticks")

    # The run's own tickrate, because ticks alone is not a duration.  Bounded
    # well outside anything playable rather than pinned to 66.67: the board
    # records what the server reported and lets the number be read, and a
    # ruleset check is the movement lock's job, not a magic constant here.
    tickrate = strict_float(request.form.get("tickrate"), 1.0, 10000.0)
    if tickrate is None:
        return fail(400, "bad tickrate")

    flags = strict_int(request.form.get("flags"), 0, 0x7FFFFFFF)
    if flags is None:
        return fail(400, "bad flags")

    style = style_of(flags)
    if style is None:
        # Not an error on the submitter's part: a practice or cheated run is a
        # real run that simply has no board.  204 says "understood, stored
        # nothing", which a client can log without treating it as a failure.
        log.info("run not boardable (flags=%d) from %s", flags, src)
        return Response("", status=204)

    tier = clean_text(request.form.get("tier")) or TIER_RANKED
    if tier not in TIERS:
        return fail(400, "bad tier")
    # A submitter may ask for a LOWER tier than it is entitled to (a keyed
    # server running a casual session), and may never ask for a higher one:
    # holding the key is the entitlement, and an uncertifiable run is demoted
    # whatever it asked for.  See certifiable().
    if tier == TIER_RANKED and not certifiable(flags):
        tier = TIER_COMMUNITY

    name = clean_text(request.form.get("name")) or player
    node = clean_text(request.form.get("node")) or "?"
    runid = clean_text(request.form.get("runid"))

    millis = int(round(ticks * 1000.0 / tickrate))

    db = get_db()
    try:
        with db:
            prev = db.execute(
                """
                SELECT millis FROM runs
                 WHERE map=? AND track=? AND leg=? AND tier=? AND style=?
                   AND player=?
                """,
                (mapname, track, leg, tier, style, player),
            ).fetchone()

            if prev is None:
                total = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                if total >= MAX_RUNS:
                    log.warning("run cap %d reached, refusing %s", MAX_RUNS, src)
                    return fail(429, "run limit reached")
            elif prev["millis"] <= millis:
                # NOT an error, and not silence either: the client asked to
                # file a time and is entitled to know it did not improve.
                return jsonify(
                    {"ok": True, "stored": False, "best": prev["millis"]}
                )

            db.execute(
                """
                INSERT INTO runs (map, track, leg, tier, style, player, name,
                                  ticks, tickrate, millis, flags, node, runid,
                                  submitted)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(map, track, leg, tier, style, player) DO UPDATE SET
                    name      = excluded.name,
                    ticks     = excluded.ticks,
                    tickrate  = excluded.tickrate,
                    millis    = excluded.millis,
                    flags     = excluded.flags,
                    node      = excluded.node,
                    runid     = excluded.runid,
                    submitted = excluded.submitted
                """,
                (mapname, track, leg, tier, style, player, name, ticks,
                 tickrate, millis, flags, node, runid, now),
            )
    except sqlite3.Error as exc:
        log.exception("run db error from %s: %s", src, exc)
        return fail(500, "storage error")

    log.info(
        "run map=%r track=%d leg=%d tier=%s style=%s player=%r ticks=%d (%dms)",
        mapname, track, leg, tier, style, player, ticks, millis,
    )
    return jsonify({"ok": True, "stored": True, "best": millis})


@app.get("/api/board")
def board():
    now = int(time.time())

    # rate_key() AND NOT request.remote_addr, BECAUSE THIS ENDPOINT IS PROXIED.
    #
    # This is the one route on the public vhost that is both rate limited and
    # reachable from the internet, so it is the one route where the peer
    # address is nginx rather than the player.  Keying on the peer here would
    # put every player in the game into a single 120-per-minute bucket: a
    # stranger at two requests a second would blank the leaderboard for
    # everybody, which is a cheaper attack than the 404 this replaced.
    # See the SURFD_PROXIES essay.
    src = rate_key()

    # Its own bucket, for the reason /api/run has one: a public read path must
    # not be able to spend the heartbeat's budget and blank the map picker.
    if not rate_ok(src, now, RUN_RATE_MAX, "board"):
        return fail(429, "rate limited")

    mapname = clean_map(request.args.get("map"))
    if not mapname:
        return fail(400, "bad map")

    track = strict_int(request.args.get("track", 0), 0, MAX_TRACK)
    leg = strict_int(request.args.get("leg", 0), 0, MAX_LEG)
    if track is None or leg is None:
        return fail(400, "bad leg")

    tier = clean_text(request.args.get("tier")) or TIER_RANKED
    style = clean_text(request.args.get("style")) or STYLE_CLEAN
    if tier not in TIERS:
        return fail(400, "bad tier")
    if style not in STYLES:
        return fail(400, "bad style")

    limit = clamp_int(request.args.get("limit"), 1, BOARD_LIMIT_MAX,
                      BOARD_LIMIT_DEF)
    offset = clamp_int(request.args.get("offset"), 0, MAX_RUNS, 0)

    rows = []
    counts = {}
    try:
        db = get_db()
        # The counts for BOTH tiers of this board, in one query, because the
        # client needs them to say "no ranked times yet, 37 community" without
        # a second round trip -- and because the alternative, defaulting the
        # board to whichever tier happens to be populated, would silently mix
        # trust levels in one ranked list.  The plan's rule is that a
        # community run never appears on the ranked board; showing a count is
        # how the UI stays honest without breaking it.
        for row in db.execute(
            """
            SELECT tier, COUNT(*) AS n FROM runs
             WHERE map=? AND track=? AND leg=? AND style=?
             GROUP BY tier
            """,
            (mapname, track, leg, style),
        ).fetchall():
            counts[row["tier"]] = row["n"]

        for i, row in enumerate(db.execute(
            """
            SELECT player, name, ticks, tickrate, millis, flags, submitted
              FROM runs
             WHERE map=? AND track=? AND leg=? AND tier=? AND style=?
             ORDER BY millis ASC, submitted ASC
             LIMIT ? OFFSET ?
            """,
            (mapname, track, leg, tier, style, limit, offset),
        ).fetchall()):
            rows.append(
                {
                    "r": offset + i + 1,
                    "player": row["player"],
                    "name": row["name"],
                    "ticks": row["ticks"],
                    "rate": row["tickrate"],
                    "ms": row["millis"],
                    "flags": row["flags"],
                    "when": row["submitted"],
                }
            )
    except sqlite3.Error as exc:
        # Same contract as lobbies.json: the client must always get parseable
        # JSON with a rows array, so a storage fault reads as an empty board
        # rather than as a parse failure three layers away in QC.
        log.exception("board db error: %s", exc)

    body = json.dumps(
        {
            "v": 1,
            "t": now,
            "map": mapname,
            "track": track,
            "leg": leg,
            "tier": tier,
            "style": style,
            "counts": {
                TIER_RANKED: counts.get(TIER_RANKED, 0),
                TIER_COMMUNITY: counts.get(TIER_COMMUNITY, 0),
            },
            "offset": offset,
            "rows": rows,
        },
        separators=(",", ":"),
    )
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
        # client_identity is passed in rather than imported by admin.py:
        # surfd imports admin, so admin importing surfd back would be a cycle,
        # and a second copy of the SURFD_PROXIES policy is the kind of
        # duplicate that drifts silently until the two disagree about who a
        # caller is.  One definition, injected.
        bp = build_blueprint(app, log, connect, LOBBY_TTL,
                             client_identity=client_identity)
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
