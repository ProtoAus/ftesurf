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

import hashlib
import hmac
import ipaddress
import json
import logging
import logging.handlers
import math
import os
import re
import shutil
import sqlite3
import threading
import time

from flask import Flask, Response, g, jsonify, request, send_file

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = os.environ.get("SURFD_HOME", "/srv/nvme/surfd")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.environ.get("SURFD_DB", os.path.join(DATA_DIR, "surfd.db"))
ENV_PATH = os.environ.get("SURFD_ENV", os.path.join(BASE_DIR, "surfd.env"))
LOG_PATH = os.path.join(LOG_DIR, "surfd.log")

# WHERE THE RECORDINGS ARE, AND WHY surfd CAN JUST READ THEM.
#
# The five lobbies and surfd are the same machine, so a `.rec` written by
# lobby 4 is already on the disk this process serves from: the storage half of
# "watch any run on the board" is a filesystem read, not an upload.  That is
# the one simplification the whole feature rests on, and it stops being true
# the moment a keyed game server runs somewhere else -- at which point this
# constant is the thing that has to grow a per-node dimension, because
# `replays.node` already records WHICH lobby wrote each file and nothing here
# consults it yet.
#
# It is one directory above the per-map tree: <RUNS_DIR>/<map_dir>/<leg>/<leaf>
# exactly as FS_RunDir composes it in sh_defs.qc.  Kept as an env override
# rather than hardcoded because test_replays.py has to point it at a tmpdir.
RUNS_DIR = os.environ.get(
    "SURFD_RUNS", "/srv/nvme/ftesurf-server/game/ftesurf/data/runs")

# Schema 6.  The lobbies' data/evidence/<map>/<runid>.rec (SV_RecKeepEvidence),
# read-only here and swept by them after run_evidence_days; KEEP_DIR holds
# surfd's hard links to the ones that back a stage row, <KEEP_DIR>/<map_dir>/<leaf>.
EVIDENCE_DIR = os.environ.get(
    "SURFD_EVIDENCE",
    os.path.join(os.path.dirname(os.path.normpath(RUNS_DIR)), "evidence"))
KEEP_DIR = os.environ.get("SURFD_KEEP", os.path.join(DATA_DIR, "evidence"))
EVIDENCE_SETTLE = 600    # s; a file with no `end` younger than this may be mid-write
KEEP_ORPHAN_AGE = 3600   # s; a kept file with no row older than this is removed

# Patch 423: warn before the data drive fills.  run_evidence_days is 0 since
# 2026-09-21 (Lex: keep everything, warn me), so nothing else bounds data/.
DISK_WARN_GB = 20
DISK_WARN_FRAC = 0.10
DISK_SIZES_TTL = 600     # s; the data/ walk is cached, the fleet page polls every 10 s
_disk_sizes = {"at": 0.0, "sizes": {}}


def tree_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def disk_status():
    """The drive holding RUNS_DIR.  `warn` below max(DISK_WARN_GB, DISK_WARN_FRAC
    of the drive); the data/ subtrees are sized only while warning, and at most
    every DISK_SIZES_TTL, so the admin's poll stays one statfs."""
    probe = os.path.normpath(RUNS_DIR)
    while not os.path.isdir(probe) and os.path.dirname(probe) != probe:
        probe = os.path.dirname(probe)
    u = shutil.disk_usage(probe)
    floor = max(DISK_WARN_GB * 2 ** 30, DISK_WARN_FRAC * u.total)
    out = {"path": probe, "total": u.total, "free": u.free,
           "used_pct": round(100.0 * u.used / max(1, u.used + u.free), 1),   # df's Use%
           "floor": int(floor), "warn": u.free < floor, "sizes": {}}
    if out["warn"]:
        now = time.time()
        if now - _disk_sizes["at"] >= DISK_SIZES_TTL or not _disk_sizes["sizes"]:
            data = os.path.dirname(os.path.normpath(RUNS_DIR))
            _disk_sizes["sizes"] = {name: tree_bytes(os.path.join(data, name))
                                    for name in ("runs", "evidence", "resume", "parts")}
            _disk_sizes["at"] = now
        out["sizes"] = dict(_disk_sizes["sizes"])
    return out

# A replay is ~1 MB where a board page is ~4 KB, so it gets its own bucket and
# a much smaller cap.  This is the first route that can move real bandwidth off
# a home upstream link, and the limiter is the only thing standing between the
# board and somebody pulling every recording in a loop.
REPLAY_RATE_MAX = 20     # replay fetches per RATE_WINDOW per source

# --------------------------------------------------------------------------
# WHERE THE MAPS ARE.  Build 67, "every map someone plays is a lobby".
# --------------------------------------------------------------------------
#
# THE LOBBIES DO NOT LOAD MAPS OUT OF THEIR OWN GAMEDIR AND THAT IS THE WHOLE
# REASON THIS FEATURE IS CHEAP.  `game/ftesurf/maps/` on the Pi is EMPTY;
# `game/momentum/maps/` holds the full 1312-BSP library, and the five live
# lobbies already `changelevel` into it.  So "host any map in the library" needs
# no content work at all -- the plan's Part 7 sized it as 45 GB of Valve-adjacent
# BSPs to mirror, and that was true when it was written and is not true now.
#
# WHAT surfd USES IT FOR IS ONE STAT, and specifically NOT a listing served to
# anybody: /api/join has to answer "is this map installed" before it moves a
# server onto it, because `changelevel` at a map that is not there prints an
# error to a log nobody reads and leaves the lobby exactly where it was -- i.e.
# the player is told to connect somewhere that will never be the map they asked
# for.  A refusal here is a sentence the menu can show.
MAPS_DIR = os.environ.get(
    "SURFD_MAPS", "/srv/nvme/ftesurf-server/game/momentum/maps")

# ZONES ARE A SEPARATE QUESTION FROM BSPS AND THE DIFFERENCE IS THE PRODUCT.
#
# Measured on the Pi 2026-09-14: 1312 BSPs, 533 zone files, 531 maps with both.
# A map with no zone file LOADS PERFECTLY and can never be timed -- no start, no
# end, no checkpoints, so SV_TimerStart is never reached and the run timer never
# arms.  From inside the game that is indistinguishable from a broken timer.
#
# So `timed` is REPORTED, never ENFORCED.  Refusing to host an unzoned map would
# be surfd deciding a player may not walk around a map they own, which is not
# its business; answering "yes, and you cannot set a time here" is.  The menu
# decides what to do with that, and can say so before the player spends a
# connect on it.
ZONES_DIR = os.environ.get(
    "SURFD_ZONES", os.path.join(MAPS_DIR, "zones", "online"))

# HOW LONG THE DIRECTORY LISTING IS BELIEVED.  1312 entries is a ~2 ms scandir
# on the NVMe and this is a single-worker process, so the cache is not about
# cost -- it is about not doing it once per request under a flood while still
# noticing a map that mapsync.py copied in five minutes ago.
MAPS_TTL = 300           # seconds

# A JOIN IS A CHEAP READ IN THE COMMON CASE (somebody is already on that map)
# and a map load in the uncommon one, so it gets its own bucket like every other
# route that can cost real work.  Higher than REPLAY_RATE_MAX because a menu
# that lists twenty maps may legitimately ask about several in a session, and
# the expensive branch is separately protected by the idle rule below.
JOIN_RATE_MAX = 30       # join requests per RATE_WINDOW per source

# HOW LONG A LOBBY IS HELD FOR THE PERSON WHO ASKED FOR IT.
#
# The claim exists because the answer is not instant: surfd replies to the
# heartbeat, the lobby changelevels, and the map takes a few seconds to load
# (measured on the Pi after engine Patch 298: 4 s for a heavy map, well under
# one for a light one).  Without a claim, a second request in that window would
# see the same lobby still reading `players 0` on its OLD map and send a second
# player somewhere a third request would then move again.
#
# 90 SECONDS, NOT 10.  It has to cover the load AND the client's connect AND the
# first heartbeat after the new map (up to lobby_master_rate, 5 s) -- and the
# cost of being too long is one lobby held idle for a minute, while the cost of
# being too short is two players sent to the same server for different maps.
ASSIGN_TTL = 90          # seconds

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
# is on the same Pi -- once per lobby_master_rate, which cfg/lobby/lobby.cfg sets to
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
# Our own nodes (TRUSTED_SOURCES) all post from loopback, and main runs also
# post every primed stage they pass (QC stage fill-in): 64 nodes x 24 posts/min
# x 2.5.  Main runs (leg 0) and stage legs use separate buckets, so stage posts
# can never spend the finishes' budget.
RUN_RATE_MAX_TRUSTED = int(2.5 * CLUSTER_NODES_PLANNED * 24)   # = 3840

MAX_RUNS = 200000        # hard cap on stored MAIN rows (leg 0); see submit_run
MAX_STAGE_RUNS = 1000000 # ...and on stage rows (leg > 0), counted separately

# THE REPLAY LEDGER'S CAP, AND IT BEHAVES DIFFERENTLY FROM MAX_RUNS ON PURPOSE.
# Reaching MAX_RUNS refuses the submission with a 429, because a board row is
# the thing being asked for and silently not storing it would be a lie.  An
# index entry is not: reaching this cap logs and stores the run anyway, with
# replay_id 0.  A first-time player must never be refused a time because a
# bookkeeping table filled up.
#
# The number is sized off the disk rather than off taste.  The lobbies keep
# every recording (rec_runs_keep 0) at a measured ~90 KB median, so 76 GB of
# free space is ~800k recordings; this cap sits above that, which makes the
# DISK the thing that runs out first and keeps the warning honest -- if this
# ever trips, something is submitting leaves that do not correspond to files.
MAX_REPLAYS = 1000000

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
TF_NOPROFILE = 2048     # QC build 72; sh_defs.qc holds the essay
TF_NOMAP = 4096         # QC build 73 / engine Patch 321; sh_defs.qc holds the essay
TF_NOCLOCK = 8192       # QC build 76 / engine Patch 325; sh_defs.qc holds the essay
TF_NOCOUNTS = 65536     # Patch 406: cursor data instead of mouse counts (cl_prydoncursor)
# Multi-Session (sv_resume.qc): resumed across a drop or a map change.  Display
# and evidence only -- style_of and certifiable deliberately never read it.
TF_MULTISESSION = 16384
# Patch 382: the run held a spectate window.  Marker only, like TF_MULTISESSION:
# a spectated run stays ranked.
TF_SPEC = 32768

SCHEMA_VERSION = 8


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


# One pm_verify verdict per sweep attempt (sweep.py writes it).  Also run by
# sweep.ensure_schema, so the text must stay idempotent.
VERDICTS_SQL = """
CREATE TABLE IF NOT EXISTS verdicts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_id  INTEGER NOT NULL,
    verdict    TEXT    NOT NULL,
    reason     TEXT    NOT NULL,
    ticks      INTEGER NOT NULL DEFAULT -1,
    engine     TEXT    NOT NULL,
    progs      TEXT    NOT NULL,
    at         INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS verdicts_replay ON verdicts (replay_id, id);
"""
# One row per run receipt the sweeper has read (schema 7, sweep.py writes it).
# Idempotent for the same reason VERDICTS_SQL is: sweep.ensure_schema runs it.
#
# KEYED ON THE RUNID AND NOT ON A REPLAY ROW.  A receipt is written by the
# server for a RUN; whether that run also became a board row, a stage row, a
# shadow or nothing at all is a separate question with a separate answer, and a
# foreign key here would force one of them at the moment the file is read.
#
# STORE-ONLY, exactly like `verdicts`.  Nothing in VER_SQL reads this table and
# the VERIFIED badge does not move because of it: what a receipt is worth is a
# policy question, and a sweeper that quietly started demoting runs would be
# answering it by itself.  See the owner's review pages.
RECEIPTS_SQL = """
CREATE TABLE IF NOT EXISTS receipts (
    runid     TEXT PRIMARY KEY,
    map       TEXT    NOT NULL DEFAULT '',
    pub       TEXT    NOT NULL DEFAULT '',
    verdict   TEXT    NOT NULL,
    angles    TEXT    NOT NULL DEFAULT '',
    reason    TEXT    NOT NULL DEFAULT '',
    at        INTEGER NOT NULL,
    sig       INTEGER NOT NULL DEFAULT 0,
    signed_at INTEGER NOT NULL DEFAULT 0,
    stale     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS receipts_pub ON receipts (pub, at);

CREATE TABLE IF NOT EXISTS pubkeys (
    pub        TEXT    NOT NULL,
    player     TEXT    NOT NULL,
    first_at   INTEGER NOT NULL,
    last_at    INTEGER NOT NULL,
    runs       INTEGER NOT NULL DEFAULT 0,
    decision   TEXT    NOT NULL DEFAULT '',
    decided_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (pub, player)
);
CREATE INDEX IF NOT EXISTS pubkeys_player ON pubkeys (player, pub);

CREATE TABLE IF NOT EXISTS sweepmeta (
    k TEXT PRIMARY KEY,
    v INTEGER NOT NULL
);
"""


def replays_bound(conn):
    """Patch 425, IDEMPOTENT and run by every migrate(): replays.bound is 1 when
    the row was filed against its file -- submit_run bound the header, or
    index_evidence indexed it -- so "a recording of the run" is decided when it
    was filed, never by whether the disk still has it (review round 5: a
    missing file un-hid a rejected run's stage times).  Backfilled once, from
    the disk as it is now."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(replays)")}
    if "bound" in cols:
        return
    try:
        conn.execute("ALTER TABLE replays ADD COLUMN bound INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc):
            raise
        return                                # a racing process backfills
    conn.execute("UPDATE replays SET bound = 1 WHERE kind = 'evidence'")
    for row in conn.execute("SELECT id, map_dir, track, leg, leaf, kind FROM replays"
                            " WHERE kind = 'run'").fetchall():
        if replay_file(row)[0] is not None:
            conn.execute("UPDATE replays SET bound = 1 WHERE id = ?", (row[0],))
    conn.commit()


def receipts_v8(conn):
    """Schema 8 (Patch 422), IDEMPOTENT and run by every migrate(): it also
    repairs a database an earlier cut stamped 8 without the receipts columns
    (c97b430), and rows a rolled-back schema-7 sweep wrote since.

    pubkeys.decision: the owner's word on a (key, player) pair -- '' (first key
    wins), 'accept' or 'reject'.  receipts.sig: 1 when the signature verified
    (a FAULT can still be signed); signed_at: the .rcpt's mtime (a resumed run
    keeps session one's runid, so runid does not order signings); stale: to be
    read again.  sweepmeta.receipts_through: see sweep.receipt_step.  admin.py
    reads them; VER_SQL and every public surface do not.  Additive, so a
    schema-7 surfd reads the same file.  The ALTERs race like step 6.
    """
    conn.executescript(RECEIPTS_SQL)
    for table, adds in (
            ("pubkeys", (("decision", "decision TEXT NOT NULL DEFAULT ''"),
                         ("decided_at", "decided_at INTEGER NOT NULL DEFAULT 0"))),
            ("receipts", (("sig", "sig INTEGER NOT NULL DEFAULT 0"),
                          ("signed_at", "signed_at INTEGER NOT NULL DEFAULT 0"),
                          ("stale", "stale INTEGER NOT NULL DEFAULT 0")))):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        for col, ddl in adds:
            if col not in cols:
                try:
                    conn.execute("ALTER TABLE %s ADD COLUMN %s" % (table, ddl))
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc):
                        raise
    # No signed_at = written by a pre-8 sweep: read it again (a FAULT's sig is
    # unknown), and until then order it by when it was read.  Such rows mean a
    # schema-7 sweep ran since the watermark was set -- its --reread-receipts
    # DELETEs -- so the watermark is void until the next complete pass.
    if conn.execute("UPDATE receipts SET stale = 1 WHERE signed_at = 0").rowcount:
        conn.execute("DELETE FROM sweepmeta WHERE k = 'receipts_through'")
    conn.execute("UPDATE receipts SET sig = 1 WHERE verdict = 'VALID' AND sig = 0")
    conn.execute("UPDATE receipts SET signed_at = at WHERE signed_at = 0")
    conn.commit()

# ERRORs since the last submission or re-check before sweep.pending() gives up;
# the admin's "pending" list uses the same cap.
VERIFY_MAX_ERRORS = 3


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

        if version < 3:
            # SCHEMA 3: THE REPLAY LEDGER -- one row per recording on disk.
            #
            # WHY A SECOND TABLE AND NOT MORE COLUMNS ON `runs`.  `runs` is a
            # PROJECTION: its primary key is the board key plus the player, and
            # submit_run's ON CONFLICT ... DO UPDATE overwrites name, ticks,
            # flags, node and runid every time that player improves.  It is the
            # right shape for a board -- Lex's ask is "display the best from
            # that user" and this table has always answered exactly that -- and
            # it is the wrong shape for history, because the row that described
            # the beaten run is gone.
            #
            # Since build 66 the lobbies KEEP every recording (rec_runs_keep 0
            # returns out of SV_RecPrune before it opens the directory), so the
            # bytes of a beaten run survive while the only record of WHOSE run
            # they were, under WHICH name, on WHICH board, did not.  A kept file
            # nothing can attribute is not kept in any useful sense.  This table
            # is the thing that remembers.
            #
            # ONE ROW PER FILE, which is what UNIQUE(map, track, leg, leaf)
            # says: map+track+leg IS the directory (FS_RunDir) and leaf is the
            # basename, so the tuple is the path.  It has to be an upsert rather
            # than a plain insert because the game can legitimately write the
            # same name twice -- SV_RecClose does fremove(dst) then frename, so
            # an exact tie by the same player on the same leg REPLACES the
            # bytes.  Two rows for one file would mean one of them describes
            # bytes that are not there; the upsert keeps the row describing
            # whatever actually survived.
            #
            # map AND map_dir ARE BOTH HERE AND THEY ARE DIFFERENT STRINGS.
            # clean_map lowercases, because the board key must merge two
            # spellings of one map rather than rank them separately.  The DISK
            # does not: the engine copies the map name as given and the game
            # builds data/runs/<mapname>/, and six maps in the library are
            # capitalised (Bhop_Mukiology, bhop_HaddocK, bhop_HeLL,
            # bhop_addict_V2, surf_Rebel_Resistance_Revamp,
            # surf_prottos_NightMare).  ext4 is case-sensitive, so a path built
            # from the lowercased key misses every recording on those six and
            # reads as "there is no replay".  map joins runs; map_dir builds the
            # path.
            #
            # EVERY BOARD COLUMN IS COPIED, deliberately.  tier and style are
            # frozen as of this submission because both are derived from flags
            # and a player can move between boards between runs; `name` is
            # frozen because it is the netname that PRODUCED this filename's
            # slug and runs.name will not be it for long.  ~170 bytes a row.
            #
            # NO FOREIGN KEY from runs.replay_id.  A superseded run has no
            # `runs` row at all, so there is nothing to point back at, and an FK
            # invites a cascade -- which is the one behaviour this table exists
            # to never have.
            #
            # seen/checked ARE FOR A SWEEPER THAT DOES NOT EXIST YET.  They are
            # in the schema now so adding it later is not a migration: -1 means
            # "no one has looked", not "missing".  `bytes` by contrast is filled
            # at submission time from the recorder's own final offset, so the
            # ledger can answer "how much disk is this" from day one.
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS replays (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    map        TEXT    NOT NULL,
                    map_dir    TEXT    NOT NULL,
                    track      INTEGER NOT NULL,
                    leg        INTEGER NOT NULL,
                    leaf       TEXT    NOT NULL,
                    tier       TEXT    NOT NULL,
                    style      TEXT    NOT NULL,
                    player     TEXT    NOT NULL,
                    name       TEXT    NOT NULL,
                    ticks      INTEGER NOT NULL,
                    tickrate   REAL    NOT NULL,
                    millis     INTEGER NOT NULL,
                    flags      INTEGER NOT NULL,
                    node       TEXT    NOT NULL,
                    submitted  INTEGER NOT NULL,
                    bytes      INTEGER NOT NULL DEFAULT -1,
                    truncated  INTEGER NOT NULL DEFAULT 0,
                    seen       INTEGER NOT NULL DEFAULT -1,
                    checked    INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (map, track, leg, leaf)
                );
                CREATE INDEX IF NOT EXISTS replays_player
                    ON replays (map, track, leg, tier, style, player,
                                millis, submitted);
                CREATE INDEX IF NOT EXISTS replays_sweep
                    ON replays (checked, id);
                """
            )
            # ALTER, not a rebuild: the live table is stamped user_version 2, so
            # CREATE TABLE IF NOT EXISTS on `runs` would do nothing there while a
            # fresh install got the new shape -- the exact divergence the
            # docstring above is guarding against.  0 means "no recording is
            # indexed for this row", which is the honest value for every row
            # that already exists and for every run whose file never landed.
            conn.execute(
                "ALTER TABLE runs ADD COLUMN replay_id INTEGER NOT NULL DEFAULT 0"
            )
            conn.execute("PRAGMA user_version=3")
            conn.commit()
            version = 3

        if version < 4:
            # SCHEMA 4: WHICH MAP EACH LOBBY HAS BEEN ASKED TO BE ON.
            #
            # This is the whole of "every map someone plays is a lobby" on the
            # storage side, and it is deliberately one small table rather than a
            # column on `lobbies`.  `lobbies` is a MIRROR: every column in it is
            # overwritten by the next heartbeat with whatever the server said
            # about itself, and it is DELETEd wholesale when a node goes stale.
            # An assignment is the opposite kind of fact -- it is what WE want,
            # it must survive the node's own reporting, and it must survive the
            # gap between `changelevel` and the first heartbeat from the new map,
            # which is exactly the window in which the mirror still says the OLD
            # map.  Putting it in `lobbies` would have it overwritten by the very
            # heartbeat it is trying to answer.
            #
            # KEYED ON THE NODE, NOT ON THE MAP, because a node can be on only
            # one map and the question every heartbeat asks is "should I move?".
            # Keyed on the map instead, that lookup would be a scan and two
            # claims could name the same server.
            #
            # `src` IS KEPT FOR ONE REASON: this is the only public endpoint in
            # surfd that causes work on a game server, so when it is abused the
            # log has to be able to say by whom.  It is not used for policy.
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS assignments (
                    node     TEXT    PRIMARY KEY,
                    map      TEXT    NOT NULL,
                    map_dir  TEXT    NOT NULL,
                    asked_at INTEGER NOT NULL,
                    src      TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS assignments_map
                    ON assignments (map, asked_at);
                """
            )
            conn.execute("PRAGMA user_version=4")
            conn.commit()
            version = 4

        if version < 5:
            # SCHEMA 5: verdicts (adopted from sweep.py), owner reviews, and a
            # re-check stamp.  Idempotent: sweep.py's cron import can run this
            # concurrently with gunicorn's, so every step tolerates the other
            # having done it first.  A review is current only while
            # at >= replays.submitted (an exact tie re-describes the row).
            conn.executescript(VERDICTS_SQL + """
                CREATE TABLE IF NOT EXISTS reviews (
                    replay_id  INTEGER PRIMARY KEY,
                    decision   TEXT    NOT NULL
                               CHECK (decision IN ('approve', 'reject')),
                    note       TEXT    NOT NULL DEFAULT '',
                    at         INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS runs_replay ON runs (replay_id);
                """)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(replays)")}
            if "recheck_at" not in cols:
                try:
                    conn.execute("ALTER TABLE replays ADD COLUMN"
                                 " recheck_at INTEGER NOT NULL DEFAULT 0")
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc):
                        raise
            conn.execute("PRAGMA user_version=5")
            conn.commit()
            version = 5

        if version < 6:
            # SCHEMA 6: replays.runid ties a stage row (leg>0, no leaf) to the
            # recording of the run it was set in -- runs.runid is overwritten on
            # every improvement, so the link has to live here.  kind is 'run' (a
            # submitted leaf) or 'evidence' (index_evidence).  Idempotent, as 5.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(replays)")}
            for col, ddl in (("runid", "runid TEXT NOT NULL DEFAULT ''"),
                             ("kind", "kind TEXT NOT NULL DEFAULT 'run'")):
                if col not in cols:
                    try:
                        conn.execute("ALTER TABLE replays ADD COLUMN " + ddl)
                    except sqlite3.OperationalError as exc:
                        if "duplicate column" not in str(exc):
                            raise
            # Only replays a board row still names get a runid; the rest stay ''
            # and link nothing.  Never from a .rec header: a TF_SHADOW
            # continuation's still names the run the lobby cut it from.
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS replays_runid
                    ON replays (runid, map, player);
                UPDATE replays SET runid = COALESCE((SELECT r.runid FROM runs r
                       WHERE r.replay_id = replays.id AND r.runid <> ''
                       LIMIT 1), '')
                 WHERE runid = '' AND kind = 'run';
                """)
            conn.execute("PRAGMA user_version=6")
            conn.commit()
            version = 6

        if version < 7:
            # SCHEMA 7: what the receipt chain said, and which public key signed
            # under which player name.  Two ADDITIVE tables and no column
            # touched, so a rollback to a schema-6 surfd reads the same database
            # and simply never looks at them.
            #
            # THE KEY TABLE RECORDS PAIRS AND DECIDES NOTHING.  Trust on first
            # use is a policy, and the two questions it raises -- a key that
            # signs for two players, a player who signs with two keys -- have
            # ordinary innocent answers (a shared machine; a reinstall, since
            # `fskey` is a local file nobody backs up).  A schema that stored
            # "the" key per player would have answered both by losing the
            # evidence for them.
            conn.executescript(RECEIPTS_SQL)
            conn.execute("PRAGMA user_version=7")
            conn.commit()
            version = 7

        # Schema 8 is a repair as much as a step: receipts_v8 runs every time.
        receipts_v8(conn)
        # Patch 425: restage's lookups are by run; runs_board would scan the map.
        conn.execute("CREATE INDEX IF NOT EXISTS runs_run"
                     " ON runs (map, track, player, runid)")
        conn.commit()
        replays_bound(conn)
        if version < 8:
            conn.execute("PRAGMA user_version=8")
            conn.commit()
            version = 8

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

# THE NAME OF A RECORDING, as the game wrote it.  Build 66's FS_RunLeaf emits
# `<stamp>_<who>_<tag>.rec`, and this is that grammar transcribed -- narrowly,
# because the value arrives over the network and ends up as a path component.
#
# FOUR SHAPES, ALL REAL, and the middle group is optional for that reason:
#   0000279_lex-3eb1bd43_pb.rec   the ordinary lobby case: slug + 8 hex of
#                                 sha256(guid).  FS_NameSlug emits only [a-z0-9]
#                                 and caps at FS_WHO_NAMEMAX (12).
#   0000279_3eb1bd43_pb.rec       a name that slugs to nothing ("!!!", "").
#   0000279_s3_pb.rec             SV_RecWho's fallback when the GUID is empty,
#                                 sprintf("s%g", slot), slot < FS_MAXPLAYERS.
#   0000279_pb.rec                who == "" -- SV_RecWho returns that whenever
#                                 Lobby_Active() is false.  A submitting server
#                                 with lobby_enable 0 is an odd configuration
#                                 but it is not an invalid one, and a pattern
#                                 that demanded the id would have zeroed every
#                                 row from it in silence.
#
# THE STAMP IS 7 DIGITS OR MORE, never fewer: FS_RunStamp left-pads to 7 and
# lets a longer number through, and MAX_TICKS allows nine digits.
#
# THE TAG SET IS FS_TagArchived's, exactly.  Only an archived tag takes a
# stamped name; `last`, `cheat` and the `lobby` stub are FIXED names whose
# bytes are overwritten by their own next finish, so citing one in a durable
# index would be citing bytes that change under the row.
_LEAF_OK = re.compile(
    r"^[0-9]{7,10}_"
    r"(?:(?:[a-z0-9]{1,12}-)?(?P<digest>[0-9a-f]{8})_|s[0-9]{1,2}_)?"
    r"(?:run|pb|shadow)\.rec$"
)

# An evidence file's leaf: its runid (sv_timer.qc SV_RecOpen) + ".rec".
_EVLEAF_OK = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9]{1,3}(?:-p[0-9]{1,5})?\.rec$")


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


# --------------------------------------------------------------------------
# The installed map library
# --------------------------------------------------------------------------
#
# THE INDEX IS KEYED LOWERCASE AND STORES THE ON-DISK SPELLING, and that is the
# same defect this tree has now shipped three times in three separate designs.
# `clean_map` lowercases because the board key must, so two spellings of one map
# rank against each other.  ext4 does not lowercase, and six maps in the library
# carry capitals -- Bhop_Mukiology, bhop_HaddocK, bhop_HeLL, bhop_addict_V2,
# surf_Rebel_Resistance_Revamp, surf_prottos_NightMare.  A path or a changelevel
# argument rebuilt from the key misses every one of them, and the symptom is
# "that map is not installed" for a map that is installed.  R3 shipped it, R4
# shipped it, and it is written down here so R-this does not.
#
# WHAT COMES BACK OUT IS THE ON-DISK SPELLING, because that is what goes to
# `changelevel`.  FTE's own filesystem is case-sensitive on Linux too.
_maps_lock = threading.Lock()
_maps_cache = {"at": -1.0, "bsp": {}, "zone": frozenset()}


def _scan_maps():
    """Read the library off disk.  Returns (bsp_index, zone_set).

    NEVER RAISES.  A missing or unreadable MAPS_DIR is a deployment that has not
    been pointed at the library yet -- surfd's other nine endpoints are unharmed
    by it and must not 500 because this one directory moved.  An empty index
    makes /api/join answer "not installed" for everything, which is wrong but is
    a sentence rather than a stack trace, and it says so in the log once.
    """
    bsp = {}
    zone = set()
    try:
        with os.scandir(MAPS_DIR) as it:
            for entry in it:
                name = entry.name
                if not name.lower().endswith(".bsp"):
                    continue
                stem = name[:-4]
                if not _MAPNAME_OK.match(stem):
                    continue
                # FIRST SPELLING WINS, deterministically by sort order rather
                # than by whatever order the filesystem hands back, so a library
                # that somehow holds both `surf_x.bsp` and `Surf_X.bsp` resolves
                # to the same one on every boot of every node.
                key = stem.lower()
                if key not in bsp or stem < bsp[key]:
                    bsp[key] = stem
    except OSError as exc:
        log.warning("map library %s unreadable: %s", MAPS_DIR, exc)
        return {}, frozenset()

    try:
        with os.scandir(ZONES_DIR) as it:
            for entry in it:
                if entry.name.lower().endswith(".json"):
                    zone.add(entry.name[:-5].lower())
    except OSError as exc:
        # NOT fatal and NOT the same failure as the one above.  With no zone
        # directory every map reports `timed 0`, which is pessimistic and
        # honest; with no map directory nothing can be hosted at all.
        log.warning("zone directory %s unreadable: %s", ZONES_DIR, exc)

    return bsp, frozenset(zone)


def map_index(now=None):
    """The installed library, cached for MAPS_TTL.  Returns (bsp, zone)."""
    now = time.monotonic() if now is None else now
    with _maps_lock:
        if now - _maps_cache["at"] < MAPS_TTL:
            return _maps_cache["bsp"], _maps_cache["zone"]
    bsp, zone = _scan_maps()
    with _maps_lock:
        _maps_cache["at"] = now
        _maps_cache["bsp"] = bsp
        _maps_cache["zone"] = zone
        log.info("map library: %d installed, %d with zones (%s)",
                 len(bsp), len(zone), MAPS_DIR)
        return bsp, zone


def maps_reset():
    """Drop the cached library.  For tests, and for a future admin control."""
    with _maps_lock:
        _maps_cache["at"] = -1.0
        _maps_cache["bsp"] = {}
        _maps_cache["zone"] = frozenset()


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
    nothing downstream that acted on them.  QC build 72 adds TF_NOPROFILE.

    All three describe a hole in the CERTIFICATION rather than something the
    player did -- no input journal beside the run, physics that cannot be shown
    to have been the ruleset's, or an input stack under which the journal's own
    yaw identity does not hold -- so none of them may call anyone a cheat.  The
    tree's standing rule is that a quiet gate survives a false negative where an
    accusation does not, and a tier demotion is exactly that quiet gate: the
    run still stands on the community board under the player's name, and only
    the ranked board declines it.

    TF_NOPROFILE IS THE ONE MOST LIKELY TO FIRE ON AN INNOCENT INSTALL, and it
    is worth saying so where the demotion happens.  Mouse acceleration is a
    legal, archived, ordinary setting; a player with it on has done nothing
    wrong and is told, in the board's own `why` column, that the run is on the
    community board because of the input mode.  That is the whole intended
    behaviour and not a rough edge -- the alternative is ranking a run whose
    aim evidence provably cannot be checked.

    QC BUILD 73 ADDS TF_NOMAP: the client's copy of the BSP is not the copy this
    server's physics ran on.  Same shape as the other three and demoted for the
    same reason, but note what it does NOT mean.  On a lobby the server owns
    collision and the zone triggers, so a differing client map did not give the
    player faster physics -- it gave them a desynchronised prediction.  What it
    costs is checkability: the `.view` the client wrote describes a different
    world from the one the `.rec` recorded, so the two can no longer be
    cross-checked.  It is also the bit most likely to fire on someone whose only
    mistake is an out-of-date map file, which is precisely why the engine-side
    kick (sv_mapcheck, which would simply refuse them the server) is switched off
    on the lobbies and this demotion carries the fact instead.

    QC BUILD 76 ADDS TF_NOCLOCK, and it is the only one of the five that is not
    about the player's machine at all.  It says the SERVER that timed the run had
    no tick counter to time it with -- an engine older than Patch 325, or one
    with the Source mover off -- so the time was sampled off sv.time rather than
    counted off the mover.  A sampled time is a function of packet arrival and
    server frame pacing, neither of which is in the usercmd stream, so it cannot
    be recomputed by anybody.  That is the property the whole re-simulation layer
    rests on, which is why its absence demotes.

    ON THE LIVE FLEET THIS SHOULD NEVER FIRE, and that is the useful part.  Every
    lobby runs the engine and the QC deployed together, so a row carrying this bit
    means an engine and a qwprogs.dat were shipped out of order -- a fact that is
    much cheaper to read off a board row than to infer from times that are
    quietly 0-2 ticks long.

    PATCH 406 ADDS TF_NOCOUNTS, and it is the only one of the six that describes
    something the player had to DO.  The Patch 376 counts channel rides the
    prydon-cursor slot, and `cl_prydoncursor 0` -- a plain cvar, not cheat-gated
    -- takes the cursor branch instead and silences it.  The bit is NOT set on
    silence, which every pre-376 client also shows; it is set when cursor data
    arrived with no version marker, i.e. that branch ran on a server that asked
    for counts, and nothing in FTESurf uses the prydon cursor.

    It still only demotes.  A quiet gate survives a false negative where an
    accusation does not, and that rule does not bend just because this bit is
    harder to reach by accident than the other five.  Lex's call 2026-09-20.
    """
    return not (flags & (TF_NOJOURNAL | TF_NORULESET | TF_NOPROFILE | TF_NOMAP
                         | TF_NOCLOCK | TF_NOCOUNTS))


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

    # ----------------------------------------------------------------------
    # THE REPLY IS THE CONTROL CHANNEL.  Build 67; see the essay over /api/join.
    #
    # The body has been the literal "ok" since Patch 270 and the lobby only ever
    # looked at the status code, so this is a pure extension: a server running
    # older QC reads "map surf_lux" as a successful heartbeat, exactly as it read
    # "ok", and simply does not move.  That is the right failure -- a directory
    # that cannot move an old lobby is a directory with fewer maps, not a broken
    # one -- and it is why the instruction is in the BODY rather than in a status
    # code the old code already branches on.
    # ----------------------------------------------------------------------
    want = None
    try:
        with db:
            db.execute("DELETE FROM assignments WHERE asked_at < ?",
                       (now - ASSIGN_TTL,))
            row = db.execute(
                "SELECT map, map_dir FROM assignments WHERE node = ?", (node,)
            ).fetchone()
            if row is not None:
                if mapname.lower() == row["map"]:
                    # ARRIVED.  The claim is spent the moment the lobby reports
                    # the map it was sent to, not when the asker connects --
                    # surfd cannot see connections, and holding it until the TTL
                    # would keep a server that is now correct and idle out of the
                    # candidate pool for another minute.
                    db.execute("DELETE FROM assignments WHERE node = ?", (node,))
                    log.info("join: %s arrived at %r", node, mapname)
                elif players > 0:
                    # SOMEBODY GOT THERE FIRST, so the claim loses -- the idle
                    # rule is not a preference that can be overridden once the
                    # request is in flight.  The window is one heartbeat wide
                    # (lobby_master_rate, 5 s) and the cost of losing is that the
                    # asker connects to a server on the wrong map; the cost of
                    # winning would be kicking a stranger out of a run.
                    db.execute("DELETE FROM assignments WHERE node = ?", (node,))
                    log.info("join: dropping claim on %s for %r -- %d player(s) "
                             "arrived", node, row["map"], players)
                else:
                    want = row["map_dir"]
    except sqlite3.Error as exc:
        # NOT fatal to the heartbeat.  A lobby that cannot be told to move must
        # still stay in the directory; failing here would take it off the map
        # picker over a feature it is not currently using.
        log.exception("assignment lookup failed for %s: %s", node, exc)

    if want:
        log.info("heartbeat reply: %s -> changelevel %r", node, want)
        return Response("map %s" % want, status=200, mimetype="text/plain")
    return Response("ok", status=200, mimetype="text/plain")


def live_rows(now):
    # `node` IS SELECTED AND /lobbies.json DOES NOT PUBLISH IT.  It is the
    # primary key, and build 67's /api/join needs it to name the row it is
    # claiming -- a claim keyed on the address would break the moment
    # SURFD_PUBLIC_HOST rewrote one.  lobbies_json builds its own dict field by
    # field, so adding a column here publishes nothing new; that is checked
    # rather than assumed (test_join.py section 1).
    db = get_db()
    return db.execute(
        """
        SELECT node, map, players, maxplayers, addr, name, last_seen
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
# "Where do I play this map?"  -- build 67
# --------------------------------------------------------------------------
#
# THE PROBLEM THIS SOLVES IS THE PLAN'S LAYER 0, NOT A CONVENIENCE.
#
# Today the map list starts a LISTEN SERVER (m_main.qc's ui_launch does
# `map <name>`), and on a listen server the host owns sv.time, the movement
# cvars, the progs and the timer -- so a world record is a cvar edit, not a
# cheat.  That is why Lobby_SubmitRun returns at its first gate there and why
# those runs are Local-only.  The fix is not to trust the host; it is for the
# player to be a CLIENT of a server the operator runs, which is what this
# endpoint arranges.  Every run set through here is on our simulation, so tier
# T3 -- the one the plan ranks above every input-layer concern -- disappears.
#
# HOW A SERVER ACTUALLY MOVES, AND WHY IT IS NOT RCON.
#
# The obvious implementation is `rcon changelevel <map>` at an idle lobby, and
# it is wrong three times over.  FTE's amplification guard gates rcon BEFORE the
# password check with no loopback exemption, and 15 packets in 30 seconds is a
# SELF-EXTENDING 24-HOUR BLOCK that only a restart clears -- so a busy evening
# would silently take the admin panel offline for a day.  It needs the rcon
# password in this process's reach for a job that is not administration.  And it
# only works for a lobby on this machine, which is exactly the constraint
# `replays.node` already exists to stop us baking in again.
#
# The lobby already POSTs /api/heartbeat every 5 s and already reads the reply
# (sv_lobby.qc's URI_Get_Callback).  So surfd ANSWERS the heartbeat with the map
# it wants, and the lobby changelevels itself.  No new channel, no new auth --
# the heartbeat is already keyed -- no rcon, no amplification exposure, and it
# works unchanged for a keyed lobby in another datacentre.
#
# THE ABUSE SURFACE, STATED PLAINLY, BECAUSE THIS IS PUBLIC AND UNAUTHENTICATED.
#
# It has to be: the menu calls it before the player has connected to anything,
# so there is no identity to check.  That means a stranger can cause a map load
# on a machine they do not own.  The structural answer is the idle rule --
# A LOBBY WITH ANYBODY ON IT IS NEVER MOVED, so the worst available outcome is
# idle servers parked on unpopular maps, which the rotation and the next real
# request undo.  Nobody is ever kicked out of a run.  On top of that: a per-
# source rate bucket, a claim that expires, and `assignments.src` so the log can
# say who.  What it is NOT is a defence against a distributed nuisance; if that
# ever happens the answer is a token from the game client, and the claim table
# is where it would be checked.


def _join_reply(status, payload):
    payload.setdefault("v", 1)
    return Response(json.dumps(payload, separators=(",", ":")),
                    status=status, mimetype="application/json")


@app.get("/api/join")
def join_map():
    now = int(time.time())
    src = rate_key()

    if not rate_ok(src, now, JOIN_RATE_MAX, "join"):
        log.warning("rate limited join from %s", src)
        return _join_reply(429, {"error": "rate limited"})

    mapname = clean_map(request.args.get("map"))
    if not mapname:
        return _join_reply(400, {"error": "bad map"})

    bsp, zoned = map_index()
    map_dir = bsp.get(mapname)
    if not map_dir:
        # A SENTENCE, NOT A 404 WITH NO BODY.  This is the single most likely
        # refusal -- 781 of the library's names are only a typo away from each
        # other -- and the menu shows whatever is in `error`.
        return _join_reply(404, {"error": "that map is not installed on this server",
                                 "map": mapname})

    timed = 1 if mapname in zoned else 0

    db = get_db()
    try:
        with db:
            db.execute("DELETE FROM assignments WHERE asked_at < ?",
                       (now - ASSIGN_TTL,))
        rows = live_rows(now)
        claims = {r["node"]: r for r in db.execute(
            "SELECT node, map, map_dir, asked_at FROM assignments").fetchall()}
    except sqlite3.Error as exc:
        log.exception("join db error from %s: %s", src, exc)
        return _join_reply(500, {"error": "storage error"})

    # ---- 1. somebody is already there -------------------------------------
    #
    # THE FIRST CHECK AND THE COMMON ONE, and it costs nothing: no claim, no map
    # load, no state written anywhere.  It is also the whole social half of the
    # feature -- "every map is a lobby" is worth nothing if two people asking
    # for the same map get two different servers -- so the tie-break is MOST
    # PLAYERS rather than least: people gather.
    best = None
    for row in rows:
        if row["map"].lower() != mapname:
            continue
        if row["players"] >= row["maxplayers"]:
            continue
        # A LOBBY UNDER A CLAIM IS NOT STILL ON THE MAP IT REPORTS, IT IS ABOUT
        # TO LEAVE IT.  Found by test_join.py section 4, and it is the subtlest
        # thing in this endpoint: a claim takes effect on the node's next
        # HEARTBEAT, so for up to lobby_master_rate seconds the directory still
        # says it is on its old map -- truthfully, and uselessly.  Offering it
        # here as "already running" sends a third player to a server that
        # changelevels out from under them a moment later, which is exactly the
        # experience this whole feature exists to remove.  The claim is the
        # newer fact; the mirror is the older one.
        if row["node"] in claims:
            continue
        if best is None or row["players"] > best["players"]:
            best = row
    if best is not None:
        return _join_reply(200, {
            "map": mapname, "timed": timed, "state": "ready", "wait": 0,
            "addr": best["addr"], "name": best["name"],
            "players": best["players"], "max": best["maxplayers"],
            "why": "already running",
        })

    # ---- 2. one is already on its way there -------------------------------
    live = {r["node"]: r for r in rows}
    for node, claim in claims.items():
        if claim["map"] != mapname:
            continue
        row = live.get(node)
        if row is None:
            continue        # claimed a node that has since gone stale
        return _join_reply(200, {
            "map": mapname, "timed": timed, "state": "loading",
            "wait": max(0, ASSIGN_TTL - (now - claim["asked_at"])),
            "addr": row["addr"], "name": row["name"],
            "players": 0, "max": row["maxplayers"],
            "why": "loading",
        })

    # ---- 3. move an idle one ----------------------------------------------
    #
    # `players == 0` IS THE ENTIRE ANTI-ABUSE RULE and it is worth more than any
    # policy that could be written above it: a server with a human on it is not
    # a candidate, full stop, so no request from anybody can interrupt a run.
    #
    # LOWEST NODE WINS, and that is arbitrary-but-stable rather than clever --
    # the same reasoning BOARD_ORDER gives for putting `player` in the sort.
    # The right rule is least-recently-busy, which needs a column this schema
    # does not have; until the pool is bigger than five that difference is not
    # measurable, and an arbitrary rule that is the SAME on every request beats
    # a smart one that reshuffles under concurrent asks.
    free = sorted(r["node"] for r in rows
                  if r["players"] == 0 and r["node"] not in claims)
    if not free:
        # WHAT IS RUNNING IS PART OF THE REFUSAL.  A bare 503 leaves the menu
        # with nothing to offer; the list lets it say "all servers are busy --
        # here is what people are playing", which is a better product than a
        # queue and costs one field.
        return _join_reply(503, {
            "error": "every server is busy right now",
            "map": mapname, "timed": timed,
            "lobbies": [{"map": r["map"], "players": r["players"],
                         "max": r["maxplayers"], "addr": r["addr"]}
                        for r in rows],
        })

    node = free[0]
    row = live[node]
    try:
        with db:
            db.execute(
                """
                INSERT INTO assignments (node, map, map_dir, asked_at, src)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(node) DO UPDATE SET
                    map = excluded.map, map_dir = excluded.map_dir,
                    asked_at = excluded.asked_at, src = excluded.src
                """,
                (node, mapname, map_dir, now, src),
            )
    except sqlite3.Error as exc:
        log.exception("join claim failed for %s: %s", node, exc)
        return _join_reply(500, {"error": "storage error"})

    log.info("join: %s asked for %r -- assigning %s (was %r)",
             src, map_dir, node, row["map"])
    return _join_reply(200, {
        "map": mapname, "timed": timed, "state": "loading", "wait": ASSIGN_TTL,
        "addr": row["addr"], "name": row["name"],
        "players": 0, "max": row["maxplayers"],
        "why": "starting",
    })


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


# The one ordering the board has, written once.  Every query that ranks, pages
# or counts ahead-of must use exactly this, and BOARD_AHEAD below is the same
# rule expressed as a predicate -- the two are a matched pair and a change to
# either is a change to both.
#
# WHY IT IS THREE COLUMNS AND NOT TWO.  `millis, submitted` is not a TOTAL
# order: `submitted` is whole seconds, so two identical times filed in the same
# second compare equal on every column and SQLite may return them in either
# order, differently on different queries.  That is not merely untidy --
# LIMIT/OFFSET paging over a non-total order can show one row twice and skip
# another, and rank_of() could not agree with a list that does not agree with
# itself.  `player` is the primary key's own column, so adding it makes the
# order total without inventing a rule: the tie is broken, arbitrarily but
# STABLY, and the board reads the same way every time it is asked.
BOARD_ORDER = "millis ASC, submitted ASC, player ASC"
BOARD_AHEAD = ("(millis < ? OR (millis = ? AND submitted < ?) "
               " OR (millis = ? AND submitted = ? AND player < ?))")


def rank_of(db, mapname, track, leg, tier, style, millis, submitted, player):
    """Where one run stands on its own board.  Returns ``(rank, of)``.

    THE ORDER HERE MUST MATCH /api/board's, or this names a different row than
    the one the player sees when they open the board -- the game says third
    while the list says fourth.  Both read BOARD_ORDER/BOARD_AHEAD above rather
    than spelling the rule out twice.  A run is never ahead of itself: its own
    row matches this millis, this submitted and this player, so no branch of the
    predicate is true for it.

    (0, 0) ON A STORAGE FAULT, because rank 0 is already the client's word for
    "no answer" and the run itself has been stored by the time this is asked.
    Failing the submission over a failed COUNT would throw away a real run to
    avoid a cosmetic number.
    """
    try:
        ahead = db.execute(
            """
            SELECT COUNT(*) FROM runs
             WHERE map=? AND track=? AND leg=? AND tier=? AND style=?
               AND """ + BOARD_AHEAD,
            (mapname, track, leg, tier, style,
             millis, millis, submitted, millis, submitted, player),
        ).fetchone()[0]
        total = db.execute(
            """
            SELECT COUNT(*) FROM runs
             WHERE map=? AND track=? AND leg=? AND tier=? AND style=?
            """,
            (mapname, track, leg, tier, style),
        ).fetchone()[0]
    except sqlite3.Error:
        log.exception("rank query failed for map=%r leg=%d", mapname, leg)
        return 0, 0
    return ahead + 1, total


# --------------------------------------------------------------------------
# Verified badge and owner review (schema 5)
# --------------------------------------------------------------------------
#
# A verdict or review counts only while its `at` >= replays.submitted: an
# exact tie upserts the same replays row over new bytes (see submit_run).

# `ver` for one runs row aliased `r`: 1 when its replay is approved, or its
# latest current verdict is PASS.  An approval beats any later verdict.  ERROR
# (the verifier printed nothing) is not a verdict: it never moves the badge.
VER_SQL = """CASE WHEN r.replay_id > 0 AND EXISTS (
    SELECT 1 FROM replays p WHERE p.id = r.replay_id AND (
      EXISTS (SELECT 1 FROM reviews w WHERE w.replay_id = p.id
               AND w.decision = 'approve' AND w.at >= p.submitted)
      OR (SELECT v.verdict FROM verdicts v WHERE v.replay_id = p.id
           AND v.at >= p.submitted AND v.verdict <> 'ERROR'
           ORDER BY v.id DESC LIMIT 1) = 'PASS')
      AND NOT EXISTS (SELECT 1 FROM reviews w WHERE w.replay_id = p.id
               AND w.decision = 'reject' AND w.at >= p.submitted))
  THEN 1 ELSE 0 END"""

# True when replays row `p` carries a current reject.
_REJECTED_SQL = ("EXISTS (SELECT 1 FROM reviews w WHERE w.replay_id = p.id"
                 " AND w.decision = 'reject' AND w.at >= p.submitted)")

# The parent of runs row `r` when it is a stage row with no recording of its
# own: the leg-0 replay of the same run, a kept run before evidence.  A
# correlated subquery, not a JOIN: BOARD_ORDER's column names are bare.
# '-' is a replay's "no runid" (submit_run), never a link.
_PARENT_SQL = ("(SELECT p.id FROM replays p WHERE r.leg > 0 AND r.replay_id = 0"
               " AND r.runid NOT IN ('', '-') AND p.runid = r.runid"
               " AND p.map = r.map AND p.track = r.track AND p.leg = 0"
               " AND p.player = r.player"
               " AND NOT " + _REJECTED_SQL +
               " ORDER BY p.kind <> 'run', p.id DESC LIMIT 1)")


def public_state(verdict, decision):
    """VER_SQL's rule in Python, for the admin display.

    `verdict` is the latest CURRENT non-ERROR verdict word and `decision` the
    CURRENT review decision, each None when there is none.  Returns "hidden",
    "verified" or "plain"."""
    if decision == "reject":
        return "hidden"
    if decision == "approve" or verdict == "PASS":
        return "verified"
    return "plain"


def board_counts(db, mapname, track, leg, style):
    """Row counts for both tiers of one board: {"ranked": n, "community": n}."""
    counts = {TIER_RANKED: 0, TIER_COMMUNITY: 0}
    for row in db.execute(
            "SELECT tier, COUNT(*) AS n FROM runs"
            " WHERE map=? AND track=? AND leg=? AND style=? GROUP BY tier",
            (mapname, track, leg, style)).fetchall():
        if row["tier"] in counts:
            counts[row["tier"]] = row["n"]
    return counts


def board_rows(db, mapname, track, leg, tier, style, limit, offset):
    """One board page in BOARD_ORDER, as /api/board's row dicts (`ver` last)."""
    rows = []
    for i, row in enumerate(db.execute(
            "SELECT r.player, r.name, r.ticks, r.tickrate, r.millis, r.flags,"
            "       r.submitted, r.replay_id, " + _PARENT_SQL + " AS prun, "
            + VER_SQL + " AS ver"
            "  FROM runs r"
            " WHERE r.map=? AND r.track=? AND r.leg=? AND r.tier=? AND r.style=?"
            " ORDER BY " + BOARD_ORDER + " LIMIT ? OFFSET ?",
            (mapname, track, leg, tier, style, limit, offset)).fetchall()):
        rows.append({
            "r": offset + i + 1,
            "player": row["player"],
            "name": row["name"],
            "ticks": row["ticks"],
            "rate": row["tickrate"],
            "ms": row["millis"],
            "flags": row["flags"],
            "when": row["submitted"],
            # `replays` id, 0 when no recording is indexed (a legitimate
            # time).  An integer: the client keeps rows in fixed float arrays,
            # and /api/replay's whole surface stays one integer.
            "rep": row["replay_id"],
            # Schema 6: a stage row's parent replay (_PARENT_SQL), else 0.
            "run": row["prun"] or 0,
            "ver": row["ver"],
        })
    return rows


_UPSERT_RUN = """
    INSERT INTO runs (map, track, leg, tier, style, player, name,
                      ticks, tickrate, millis, flags, node, runid,
                      submitted, replay_id)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(map, track, leg, tier, style, player) DO UPDATE SET
        name      = excluded.name,
        ticks     = excluded.ticks,
        tickrate  = excluded.tickrate,
        millis    = excluded.millis,
        flags     = excluded.flags,
        node      = excluded.node,
        runid     = excluded.runid,
        submitted = excluded.submitted,
        replay_id = excluded.replay_id
"""


def restand(db, rid):
    """Re-derive the board row of replay `rid`'s player after a review change.

    Runs inside the caller's transaction and never commits.  The row becomes
    the player's best current non-rejected replay on that board:
      "kept"     the row is not rejected and no replay beats it (rep-0 rows too)
      "moved"    the row was (re)written from the best replay
      "removed"  nothing is left to stand, the row was deleted
      "none"     no such replay, or no row before and none after
    So readers need no hidden filter, and submit_run compares the player's
    next run against the re-derived row.
    """
    rep = db.execute(
        "SELECT map, track, leg, tier, style, player, kind FROM replays"
        " WHERE id = ?", (rid,)).fetchone()
    if rep is None or rep["kind"] != "run":
        return "none"           # evidence stands on no board (schema 6)
    key = (rep["map"], rep["track"], rep["leg"], rep["tier"], rep["style"],
           rep["player"])
    cur = db.execute(
        "SELECT * FROM runs WHERE map=? AND track=? AND leg=?"
        " AND tier=? AND style=? AND player=?", key).fetchone()
    best = db.execute(
        "SELECT p.* FROM replays p WHERE p.map=? AND p.track=? AND p.leg=?"
        " AND p.tier=? AND p.style=? AND p.player=? AND p.kind = 'run'"
        " AND NOT " + _REJECTED_SQL +
        " ORDER BY p.millis, p.submitted, p.id LIMIT 1", key).fetchone()

    if cur is not None:
        rejected = cur["replay_id"] > 0 and db.execute(
            "SELECT 1 FROM replays p WHERE p.id = ? AND " + _REJECTED_SQL,
            (cur["replay_id"],)).fetchone() is not None
        if not rejected and (best is None or best["millis"] >= cur["millis"]):
            return "kept"
    if best is not None:
        if cur is not None and cur["replay_id"] == 0 and cur["leg"] > 0:
            # A stage time with no recording has no history to rebuild: set it
            # aside, as a restore does, so a later reject gives it back (425).
            _stage_move(db, cur, cur["tier"] + "^" + (
                best["runid"] if best["runid"] not in ("", "-") else "r%d" % best["id"]))
        db.execute(_UPSERT_RUN, (
            best["map"], best["track"], best["leg"], best["tier"], best["style"],
            best["player"], best["name"], best["ticks"], best["tickrate"],
            best["millis"], best["flags"], best["node"], "", best["submitted"],
            best["id"]))
        return "moved"
    if cur is not None:
        db.execute("DELETE FROM runs WHERE map=? AND track=? AND leg=?"
                   " AND tier=? AND style=? AND player=?", key)
        return "removed"
    return "none"


# Patch 425: A REJECT HIDES THE STAGE TIMES ITS RUN SET (Lex, 2026-09-21).  A
# stage row (leg > 0, no recording of its own) of run R is parked in tier
# "<tier>@<R's runid>", which no board query reads (every one filters tier),
# while a reject on any replay of R is current, and restored when none is.  A
# stage row has no history to re-derive from, so nothing is deleted that is not
# beaten: the player's next time takes the live slot meanwhile, and a restore
# sets it aside as "<tier>^<R>" (superseded by R) until R is parked again.  Only
# a lapse on a replay that still names R restores R's rows: a leaf re-filed by
# another run (an exact tie) leaves them hidden.
def _stage_slot(db, row, tier):
    return db.execute("SELECT * FROM runs WHERE map=? AND track=? AND leg=?"
                      " AND tier=? AND style=? AND player=?",
                      (row["map"], row["track"], row["leg"], tier, row["style"],
                       row["player"])).fetchone()


def _stage_move(db, row, tier):
    """Move runs row `row` (a snapshot; still its runid) to `tier`.  A row
    already holding that slot stays only if it is better (BOARD_ORDER); the
    loser is deleted.  -> 1 if moved."""
    key = (row["map"], row["track"], row["leg"])
    who = (row["style"], row["player"])
    have = _stage_slot(db, row, tier)
    if have is not None:
        if (have["millis"], have["submitted"]) <= (row["millis"], row["submitted"]):
            db.execute("DELETE FROM runs WHERE map=? AND track=? AND leg=?"
                       " AND tier=? AND style=? AND player=? AND runid=?",
                       key + (row["tier"],) + who + (row["runid"],))
            return 0
        db.execute("DELETE FROM runs WHERE map=? AND track=? AND leg=?"
                   " AND tier=? AND style=? AND player=?", key + (tier,) + who)
    return db.execute("UPDATE runs SET tier = ? WHERE map=? AND track=? AND leg=?"
                      " AND tier=? AND style=? AND player=? AND runid=?",
                      (tier,) + key + (row["tier"],) + who + (row["runid"],)).rowcount


def _stage_run(db, rid):
    """(map, track, player, runid) of replay `rid`'s run, or None (no runid)."""
    rep = db.execute("SELECT map, track, player, runid FROM replays WHERE id = ?",
                     (rid,)).fetchone()
    if rep is None or rep["runid"] in ("", "-"):
        return None
    return tuple(rep)


def _run_rejected(db, run):
    """True when a current reject stands on a RECORDING of the run: a replay of
    it filed against its file (replays.bound).  A file-less row naming the runid
    is anyone's to post with the key, and rejecting it must not hide the run's
    honest stage times (review round 4); whether the file is on disk NOW is no
    answer either (round 5)."""
    return db.execute("SELECT 1 FROM replays p WHERE p.map = ? AND p.track = ?"
                      " AND p.player = ? AND p.runid = ? AND p.bound = 1 AND "
                      + _REJECTED_SQL, run).fetchone() is not None


def _stage_refill(db, row, base):
    """The slot of `row` on `base` (map/track/leg/style/player): the best time
    a restore set aside there competes for it (any run's, judged by its own
    run; a recorded copy is dropped, restand rebuilds it from its replay), a
    recorded row it beats gives way, and the player's recorded runs of that
    leg compete last (restand's rule)."""
    key = (row["map"], row["track"], row["leg"])
    who = (row["style"], row["player"])
    for back in db.execute(
            "SELECT * FROM runs WHERE map=? AND track=? AND leg=? AND style=?"
            " AND player=? AND tier LIKE ? ORDER BY millis, submitted",
            key + who + (base + "^%",)).fetchall():
        if back["replay_id"] > 0:
            db.execute("DELETE FROM runs WHERE map=? AND track=? AND leg=? AND tier=?"
                       " AND style=? AND player=?", key + (back["tier"],) + who)
            continue
        brun = (back["map"], back["track"], back["player"], back["runid"])
        if back["runid"] not in ("", "-") and _run_rejected(db, brun):
            _stage_move(db, back, base + "@" + back["runid"])
            continue
        live = _stage_slot(db, row, base)
        if live is not None:
            if not (live["replay_id"] > 0 and (back["millis"], back["submitted"])
                    < (live["millis"], live["submitted"])):
                break
            db.execute("DELETE FROM runs WHERE map=? AND track=? AND leg=? AND tier=?"
                       " AND style=? AND player=?", key + (base,) + who)
        _stage_move(db, back, base)
    rec = db.execute(
        "SELECT id FROM replays WHERE map=? AND track=? AND leg=? AND tier=?"
        " AND style=? AND player=? AND kind = 'run' LIMIT 1",
        (row["map"], row["track"], row["leg"], base, row["style"],
         row["player"])).fetchone()
    if rec is not None:
        restand(db, rec["id"])


def restage(db, rid, park_only=False):
    """Park or restore the stage rows of replay `rid`'s run, to match whether a
    reject on any replay of that run is current.  The caller's transaction.
    -> (parked, restored).  A parked slot is refilled (_stage_refill).

    Call it after anything that changes that: a review, or submit_run filing
    new evidence of the same run."""
    # A recorded stage run's own slot: what a review of it left there competes
    # with what a restore set aside (review round 4).
    rep = db.execute("SELECT map, track, leg, tier, style, player, kind"
                     " FROM replays WHERE id = ?", (rid,)).fetchone()
    if rep is not None and rep["kind"] == "run" and rep["leg"] > 0 and rep["tier"] in TIERS:
        _stage_refill(db, rep, rep["tier"])
    run = _stage_run(db, rid)
    if run is None:
        return 0, 0
    tag, sup = "@" + run[3], "^" + run[3]      # parked by R; set aside by R
    parked = restored = 0
    if _run_rejected(db, run):
        for row in db.execute(
                "SELECT * FROM runs WHERE map = ? AND track = ? AND leg > 0"
                " AND replay_id = 0 AND player = ? AND runid = ? AND tier IN (?, ?)",
                run + TIERS).fetchall():
            base = row["tier"]
            parked += _stage_move(db, row, base + tag)
            _stage_refill(db, row, base)       # moved or beaten, the slot is empty
    elif not park_only:
        for row in db.execute(
                "SELECT * FROM runs WHERE map = ? AND track = ? AND player = ?"
                " AND runid = ? AND tier IN (?, ?)",
                run + tuple(t + tag for t in TIERS)).fetchall():
            base = row["tier"][:-len(tag)]
            live = _stage_slot(db, row, base)
            if live is not None and ((live["millis"], live["submitted"])
                                     > (row["millis"], row["submitted"])):
                _stage_move(db, live, base + sup)
            restored += _stage_move(db, row, base)
    return parked, restored


def restage_rejected(conn):
    """Park the stage rows of every run a current reject stands on: the rejects
    from before Patch 425, and anything posted since.  Never restores.  Under
    the write lock, as the admin and submit paths are.  -> rows parked."""
    n = 0
    with conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        for r in conn.execute(
                "SELECT p.id FROM reviews w JOIN replays p ON p.id = w.replay_id"
                " WHERE w.decision = 'reject' AND w.at >= p.submitted"
                " AND p.runid NOT IN ('', '-')").fetchall():
            n += restage(conn, r["id"], park_only=True)[0]
    return n


def stage_counts(db, rid):
    """(shown, hidden, set aside) stage rows of replay `rid`'s run, or None when
    it has no runid (its stage rows cannot be told apart)."""
    run = _stage_run(db, rid)
    if run is None:
        return None
    tags = tuple(t + "@" + run[3] for t in TIERS)
    q = ("SELECT COUNT(*) FROM runs WHERE map = ? AND track = ? AND leg > 0"
         " AND replay_id = 0 AND player = ? AND runid = ? AND tier IN (?, ?)")
    return (db.execute(q, run + TIERS).fetchone()[0],
            db.execute(q, run + tags).fetchone()[0],
            db.execute("SELECT COUNT(*) FROM runs WHERE map = ? AND track = ?"
                       " AND leg > 0 AND replay_id = 0 AND player = ? AND runid = ?"
                       " AND tier LIKE '%^%'", run).fetchone()[0])


def _stageposts(path):
    """{(leg, ticks)} the recording's `stagepost <seg> <dur> ...` records posted
    (leg = seg + 1), or None when it could not be read."""
    out = set()
    try:
        with open(path, "rb") as fh:
            for line in fh:
                if line.startswith(b"stagepost "):
                    w = line.split()
                    seg = strict_int(w[1].decode() if len(w) > 1 else None, 0, MAX_LEG)
                    dur = strict_int(w[2].decode() if len(w) > 2 else None, 0, MAX_TICKS)
                    if seg is not None and dur is not None:
                        out.add((seg + 1, dur))
    except (OSError, UnicodeDecodeError):
        return None
    return out


def stage_binding(db, rid, path):
    """"" when every stage row of replay `rid`'s run matches a `stagepost` in its
    recording (ticks, and the tickrate its time is computed at), else why not.  "" also when that cannot be measured: no runid, an
    unreadable file, or a file that posts none (a recorder before Patch 360).
    A PASS alone vouches for the trajectory, never for a stage row's number."""
    run = _stage_run(db, rid)
    if run is None or not path:
        return ""
    rows = db.execute("SELECT leg, ticks, tickrate FROM runs WHERE map = ?"
                      " AND track = ? AND leg > 0 AND replay_id = 0 AND player = ?"
                      " AND runid = ? ORDER BY leg", run).fetchall()
    if not rows:
        return ""
    posts = _stageposts(path)
    if not posts:
        return ""
    meta = _rec_meta(path)
    hdr = meta[0] if meta else {}
    bad = ["leg %d %d ticks at %g/s" % (r["leg"], r["ticks"], r["tickrate"])
           for r in rows if (r["leg"], r["ticks"]) not in posts
           or _rec_tickrate_disagrees(hdr, r["tickrate"])]
    return ("stage rows not posted in this recording: " + ", ".join(bad[:6])
            if bad else "")


@app.post("/api/run")
def submit_run():
    now = int(time.time())
    src = request.remote_addr or "0.0.0.0"

    # Bucket by the PARSED leg ("00", "+0" are leg 0); a malformed leg counts
    # against "run" and is refused below.
    bucket = "stage" if strict_int(request.form.get("leg"), 1, MAX_LEG) else "run"
    cap = RUN_RATE_MAX_TRUSTED if is_trusted(src, TRUSTED_SOURCES) else RUN_RATE_MAX
    if not rate_ok(src, now, cap, bucket):
        log.warning("rate limited %s submission from %s", bucket, src)
        return fail(429, "rate limited")

    key = request.form.get("key", "")
    if not SECRET or not key or not hmac.compare_digest(str(key), SECRET):
        log.warning("rejected run from %s: bad key", src)
        return fail(403, "forbidden")

    # TWO SPELLINGS OF ONE MAP NAME, AND THEY ARE BOTH NEEDED.
    #
    # `mapname` is the board KEY and clean_map lowercases it, so bhop_HeLL and
    # bhop_hell rank against each other instead of forming two boards.  That is
    # right and it stays.
    #
    # `map_dir` is the PATH component, and the disk does not lowercase: the
    # engine copies the map name as given (Q_strncpyz into svs.name, no tolower
    # anywhere on that path), the game builds data/runs/<mapname>/, and ext4 is
    # case-sensitive.  Six maps in the shipped library carry capitals, so a path
    # rebuilt from the key would miss every recording on them -- and a missing
    # file reads as "this run has no replay", which is a lie that looks like a
    # feature.  Keep the raw spelling when it is a valid name and differs only
    # in case; fall back to the key otherwise, so a hostile spelling can never
    # reach a path.
    raw_map = clean_text(request.form.get("map"), MAX_MAP_LEN + 1)
    mapname = clean_map(raw_map)
    if not mapname:
        return fail(400, "bad map")
    map_dir = mapname
    if _MAPNAME_OK.match(raw_map) and raw_map.lower() == mapname:
        map_dir = raw_map

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
    if runid and not is_trusted(src, TRUSTED_SOURCES):
        # The rec leaf's rule (below): a runid decides whose stage rows a
        # lobby's evidence file backs (index_evidence).
        log.warning("ignoring runid from untrusted source %s", src)
        runid = ""

    millis = int(round(ticks * 1000.0 / tickrate))

    # ------------------------------------------------------------------
    # THE RECORDING THIS RUN LEFT BEHIND.
    #
    # The lobby sends the BASENAME of the .rec it just closed.  It is sent
    # rather than derived, and that is the whole design decision, so here is
    # why deriving it does not work even though it looks like it should:
    #
    #   * `name` here is not always the netname the filename was built from.
    #     Lobby_SubmitRun substitutes "player" for an empty netname; SV_RecWho
    #     hashes the unsubstituted one.  They diverge with nobody at fault.
    #   * runs.name is overwritten on every improvement, so by the time anyone
    #     asks, the slug that named a beaten file is a name we no longer hold.
    #   * `tier` is in the board key and appears nowhere on disk, so two files
    #     from one player on one leg cannot be told apart by inspection.
    #
    # A name that arrives is therefore transcribed, never rebuilt -- but it is
    # checked three ways, and the checks are free because they run on every
    # real finish forever rather than once in a test:
    #
    #   shape    the grammar FS_RunLeaf can actually emit (_LEAF_OK).
    #   stamp    SV_RecClose stamps the file with the SAME `ticks` it then
    #            submits, so the 7-digit prefix must equal this row's ticks.
    #            Two views of one value; if they disagree, one of them is wrong
    #            and the row must not claim the file.
    #   digest   the 8 hex in the middle are sha256(guid)[:8] and `player` IS
    #            that guid, so this compares FTE's digest_hex("SHA256") against
    #            Python's hashlib on live data.  FS_PlayerSeg's own comment
    #            says that agreement is checked rather than assumed; this is
    #            where it is checked.
    #
    # A FAILED CHECK NEVER FAILS THE RUN.  It drops the leaf and logs.  Refusing
    # a legitimate time because its filename surprised a regex would be a far
    # worse failure than an unindexed file, and the unindexed file is counted.
    #
    # THE DIGEST CHECK ONLY WARNED UNTIL 2026-09-20, on the reasoning that the
    # game named the file and is the authority on what it wrote.  True, and
    # beside the point: a leaf is not only a description, it is a CLAIM ON A
    # FILE.  `replays` is UNIQUE(map, track, leg, leaf) and the upsert below
    # rewrites `player`/`name` and resets `checked`, so a submission naming
    # somebody else's leaf takes their row, re-queues THEIR file, and wears the
    # PASS it earns (VER_SQL).  The digest is the only part of a leaf a
    # submitter cannot choose for a file that is not theirs, so it drops now.
    leaf = clean_text(request.form.get("rec"))
    if leaf and not is_trusted(src, TRUSTED_SOURCES):
        # A filesystem path is only evidence for a node we own.  Port 8084
        # answers the internet with the shared key as its only barrier, so an
        # untrusted submitter may file a time and may not name a file on our
        # disk.  A future off-LAN official server must join TRUSTED_SOURCES or
        # its rows lose their leaves -- which is the safe direction to fail.
        log.warning("ignoring rec leaf from untrusted source %s", src)
        leaf = ""
    shape = _LEAF_OK.match(leaf) if leaf else None
    if leaf and not shape:
        log.warning("rejecting malformed rec leaf %r from %s", leaf, src)
        leaf = ""
    if leaf and leaf.split("_", 1)[0] != str(ticks).zfill(7):
        log.warning("rec leaf %r disagrees with ticks %d from %s",
                    leaf, ticks, src)
        leaf = ""
    # Only when the leaf HAS a digest field, and the two shapes that lack one are
    # the other way round from what this comment said until 2026-09-20:
    # SV_RecWho (sv_timer.qc) returns "" when !Lobby_Active(), so the `who`
    # segment is missing OFF A LOBBY; on a lobby it falls back to `s<slot>` when
    # FS_PlayerSeg yields nothing (no guid, or no sluggable name).  test_replays
    # pins both as acceptable, so their absence is a configuration, not a claim.
    # The file check below is what guards them -- it needs no digest.
    if leaf and shape.group("digest"):
        want = hashlib.sha256(player.encode("utf-8", "replace")).hexdigest()[:8]
        if shape.group("digest") != want:
            log.warning("rec leaf %r carries digest %s, not this player's %s,"
                        " from %s; dropping the leaf",
                        leaf, shape.group("digest"), want, src)
            leaf = ""

    # THE CLAIM MUST AGREE WITH THE FILE IT NAMES, and this is the check that
    # actually holds the line.  Every test above compares the leaf against a
    # field the SUBMITTER TYPED, and the 2026-09-20 review showed why that can
    # never be enough: `player` arrives in the POST body and /api/board
    # publishes it, so asserting the victim's identity satisfies any
    # per-player rule by construction.  A first cut of this fix authenticated
    # on `player` twice over and was bypassed by copying one public field.
    #
    # The bytes on disk are the one thing a claim cannot choose.  index_evidence
    # has always made this check on the evidence path (_rec_meta + the
    # runid/map/leg compare); the ranked path simply never did.
    #
    # `fsize` IS THE FILE'S REAL SIZE, and it is taken here rather than trusted
    # from the wire.  The second review (2026-09-20) showed why that matters:
    # `bytes` is one of the four columns that decide whether `submitted` moves,
    # and while it was the caller's `recbytes` a one-digit change forced the
    # ELSE arm and voided the row's PASS and any owner approval -- the badge
    # strip this fix claimed to have closed, still a one-field operation.
    fsize = None
    fileless = bool(leaf)
    if leaf:
        path, why = replay_file({"map_dir": map_dir, "track": track, "leg": leg,
                                 "leaf": leaf, "kind": "run"})
        if path is None:
            # The spelling the leaf was filed under, when it is another: one the
            # disk cannot open (map_dir's case on ext4) skipped every header
            # binding below (review round 3).
            held = get_db().execute(
                "SELECT map_dir FROM replays WHERE map=? AND track=? AND leg=?"
                " AND leaf=?", (mapname, track, leg, leaf)).fetchone()
            if held is not None and held["map_dir"] != map_dir:
                path, why = replay_file({"map_dir": held["map_dir"], "track": track,
                                         "leg": leg, "leaf": leaf, "kind": "run"})
                if path is not None:
                    map_dir = held["map_dir"]
        meta = _rec_meta(path) if path else None
        if meta is None:
            # KEPT, NOT DROPPED, and the reasoning is about what the attack is
            # FOR: naming a leaf buys the row the verdict that file earns, so a
            # leaf with no file behind it buys nothing -- the sweeper has
            # nothing to verify and /api/replay serves "missing".  Dropping
            # here would instead punish every legitimate submit that races the
            # rename, and the whole surfd suite (which files rows without ever
            # writing a .rec) would stop indexing replays.  The residual is a
            # row taken over while its file is absent; it carries no badge.
            log.warning("rec leaf %r names no readable file (%s) from %s;"
                        " indexing it unverified", leaf, why or "unreadable", src)
        else:
            fsize = meta[3]
            fileless = False
            bad = _rec_disagrees(meta[0], mapname, track, leg, runid, flags,
                                 tickrate)
            if bad:
                log.warning("rec leaf %r disagrees with the row it is filed on"
                            " (%s) from %s; dropping the leaf", leaf, bad, src)
                leaf = ""

    # A REFUSED recbytes IS LOGGED, because the silent fallback hid a real bug
    # for a whole deploy.  The sender spelled 1128886 as `1.12889e+06` (QC's %g
    # gives six significant digits), strict_int did the right thing and refused
    # it, and the column fell to -1 -- which is indistinguishable from "this
    # server did not tell us", so nothing anywhere looked wrong.  The sender is
    # fixed; this line is what would have found it in a minute instead of a
    # database query.  Refusing the RUN over it would be wrong -- a size hint
    # is not the time -- so this stays a warning and the row still lands.
    raw_recbytes = request.form.get("recbytes")
    recbytes = strict_int(raw_recbytes, -1, 1 << 40)
    if recbytes is None:
        if raw_recbytes:
            log.warning("rec bytes %r unparseable from %s (leaf %r)",
                        raw_recbytes[:32], src, leaf)
        recbytes = -1
    rectrunc = 1 if clean_text(request.form.get("rectrunc")) == "1" else 0

    # THE FILE'S OWN SIZE WINS over the sender's hint whenever we could read it.
    # `bytes` stopped being cosmetic when it became one of the four columns that
    # decide whether `submitted` moves: while it was caller-supplied, changing
    # it by one byte forced the ELSE arm and voided the row's standing PASS and
    # any owner approval.  Taken from the same stat the header came from, so the
    # two cannot disagree.  The wire value remains the fallback for a leaf whose
    # file we could not open, where it is a hint and nothing rides on it.
    if fsize is not None and fsize != recbytes:
        if recbytes >= 0:
            log.info("rec leaf %r: sender said %d bytes, the file is %d;"
                     " recording the file", leaf, recbytes, fsize)
        recbytes = fsize

    db = get_db()
    try:
        with db:
            # The write lock before the first read: the checks below (a reject
            # standing, the row held) must still be true at the write (round 5).
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            # THE LEDGER ROW GOES IN FIRST, ABOVE THE IMPROVEMENT TEST, and the
            # ordering is the entire fix rather than a tidiness preference.
            #
            # The "you did not improve" branch below RETURNS.  That return is
            # inside `with db:`, and sqlite3's context manager commits on any
            # non-exception exit -- a return is one -- so a row written here is
            # committed by the same transaction whichever way the request goes.
            # Written after the test instead, a beaten run would be indexed only
            # when it happened to be an improvement, which is precisely the
            # history this exists to stop losing.
            #
            # Every finish that produced a keepable file gets a row: faster,
            # slower and exactly tied alike.
            rid = 0
            have = None
            if leaf:
                have = db.execute(
                    "SELECT id, player, runid, submitted, tier, style, bytes"
                    " FROM replays"
                    " WHERE map=? AND track=? AND leg=? AND leaf=?",
                    (mapname, track, leg, leaf),
                ).fetchone()
                # NO OWNERSHIP RULE HERE.  A first cut of this fix refused an
                # update when `have["player"] != player`, which was worthless
                # (the attacker asserts the victim's player) and harmful in two
                # ways the review measured: it froze a row on whoever claimed it
                # first, and it overrode a digest that PROVED ownership, so a
                # leaf stolen before the patch stayed stolen.  The file check
                # above is the binding; this is just the ledger.
            if leaf:
                if have is None:
                    nrep = db.execute(
                        "SELECT COUNT(*) FROM replays WHERE kind = 'run'"
                    ).fetchone()[0]
                else:
                    nrep = 0          # an upsert of a row we already hold
                if have is not None and fileless:
                    # NOTHING changes a held replay without its file: with no
                    # header to bind them, a runid or a recbytes off the wire
                    # lapsed its reviews and relabelled it (reviews 4, 5).  An
                    # honest re-filing (an exact tie) writes the file first.
                    log.warning("rec leaf %r is replay %d, and its file cannot"
                                " be read; the row is left as it is", leaf,
                                have["id"])
                elif have is not None or nrep < MAX_REPLAYS:
                    db.execute(
                        """
                        INSERT INTO replays (map, map_dir, track, leg, leaf,
                                             tier, style, player, name, ticks,
                                             tickrate, millis, flags, node,
                                             submitted, bytes, truncated, runid,
                                             bound)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(map, track, leg, leaf) DO UPDATE SET
                            map_dir   = excluded.map_dir,
                            tier      = excluded.tier,
                            style     = excluded.style,
                            player    = excluded.player,
                            name      = excluded.name,
                            ticks     = excluded.ticks,
                            tickrate  = excluded.tickrate,
                            millis    = excluded.millis,
                            flags     = excluded.flags,
                            node      = excluded.node,
                            bytes     = excluded.bytes,
                            truncated = excluded.truncated,
                            runid     = excluded.runid,
                            bound     = excluded.bound,
                            submitted = excluded.submitted,
                            seen      = -1,
                            checked   = 0
                        -- ONLY WHEN THE EVIDENCE CHANGED.  `submitted` means
                        -- "when this evidence arrived", and both VER_SQL
                        -- clauses test `at >= p.submitted`, so a re-post that
                        -- moved it voided the standing PASS and any approval
                        -- (06a5a01).  Since Patch 424 nothing else moves
                        -- either: a same-evidence re-post that could rewrite
                        -- the name, board, rate or map_dir relabelled,
                        -- re-boarded or shaved a verified replay (reviews).
                        WHERE NOT (replays.player = excluded.player
                                   AND replays.runid  = excluded.runid
                                   AND replays.ticks  = excluded.ticks
                                   AND replays.bytes  = excluded.bytes)
                        """,
                        # '-' when none was sent (a TF_SHADOW continuation),
                        # so no new row reads as a pre-schema-6 ''.
                        (mapname, map_dir, track, leg, leaf, tier, style,
                         player, name, ticks, tickrate, millis, flags, node,
                         now, recbytes, rectrunc, runid or "-", 0 if fileless else 1),
                    )
                else:
                    # LOG AND CARRY ON -- never a 429.  See MAX_REPLAYS: an
                    # index being full is not a reason to refuse somebody a
                    # time.
                    log.warning("replay cap %d reached; not indexing %r",
                                MAX_REPLAYS, leaf)
                rep = db.execute(
                    "SELECT id, name, tier, style, flags, tickrate, millis,"
                    " runid, submitted FROM replays"
                    " WHERE map=? AND track=? AND leg=? AND leaf=?",
                    (mapname, track, leg, leaf),
                ).fetchone()
                if rep is not None:
                    # The board row is the replay's: its name, board, flags
                    # and time, as filed with its evidence.
                    rid = rep["id"]
                    name, tier, style, flags = (rep["name"], rep["tier"],
                                                rep["style"], rep["flags"])
                    tickrate, millis = rep["tickrate"], rep["millis"]
                    runid = "" if rep["runid"] == "-" else rep["runid"]
                    new = have is not None and rep["submitted"] != have["submitted"]
                    # New evidence of the SAME run, in a file, lapses a reject
                    # on it; a leaf re-filed by another run, or one with nothing
                    # behind it, leaves the old run's alone.
                    if new and not fileless and have["runid"] == rep["runid"]:
                        restage(db, rid)
                    # A tie re-filed on another board: the old board's row no
                    # longer has this recording behind it (review round 3).
                    if new and (have["tier"], have["style"]) != (tier, style):
                        db.execute("UPDATE runs SET replay_id = 0 WHERE replay_id = ?"
                                   " AND NOT (tier = ? AND style = ?)",
                                   (rid, tier, style))

            prev = db.execute(
                """
                SELECT millis, submitted FROM runs
                 WHERE map=? AND track=? AND leg=? AND tier=? AND style=?
                   AND player=?
                """,
                (mapname, track, leg, tier, style, player),
            ).fetchone()

            # A stage time of a run a reject stands on goes straight to that
            # run's hidden slot, never over the player's live one -- a retried
            # POST, or a resumed run whose evidence was rejected (round 4).
            if leg > 0 and not rid and runid and _run_rejected(
                    db, (mapname, track, player, runid)):
                ptier = tier + "@" + runid
                hid = db.execute(
                    "SELECT millis, submitted FROM runs WHERE map=? AND track=?"
                    " AND leg=? AND tier=? AND style=? AND player=?",
                    (mapname, track, leg, ptier, style, player)).fetchone()
                if hid is None or millis < hid["millis"]:
                    db.execute(_UPSERT_RUN, (mapname, track, leg, ptier, style, player,
                                             name, ticks, tickrate, millis, flags,
                                             node, runid, now, 0))
                log.info("run from %s is a stage of rejected run %s; hidden",
                         src, runid)
                best = prev["millis"] if prev is not None else 0
                return jsonify({"ok": True, "stored": False, "best": best,
                                "rank": 0, "of": 0, "rep": 0, "tier": tier,
                                "prevms": best})

            # A rejected recording never takes a board row back: a re-post of
            # it (a key holder's) is filed and answered, not stood.
            if rid and db.execute("SELECT 1 FROM replays p WHERE p.id = ? AND "
                                  + _REJECTED_SQL, (rid,)).fetchone():
                log.warning("run from %s names rejected replay %d; not stood",
                            src, rid)
                best = prev["millis"] if prev is not None else 0
                rank, of = (rank_of(db, mapname, track, leg, tier, style,
                                    prev["millis"], prev["submitted"], player)
                            if prev is not None else (0, 0))
                return jsonify({"ok": True, "stored": False, "best": best,
                                "rank": rank, "of": of, "rep": rid, "tier": tier,
                                "prevms": best})

            if prev is None:
                if leg == 0:
                    total = db.execute(
                        "SELECT COUNT(*) FROM runs WHERE leg=0").fetchone()[0]
                    cap = MAX_RUNS
                else:
                    total = db.execute(
                        "SELECT COUNT(*) FROM runs WHERE leg>0").fetchone()[0]
                    cap = MAX_STAGE_RUNS
                if total >= cap:
                    log.warning("run cap %d reached (leg %d), refusing %s",
                                cap, leg, src)
                    return fail(429, "run limit reached")
            elif prev["millis"] <= millis:
                # NOT an error, and not silence either: the client asked to
                # file a time and is entitled to know it did not improve.
                #
                # THE RANK IS OF THE STANDING ROW, not of the run just set --
                # the run just set has no row, and the number the player wants
                # is where they stand on this board, which did not move.  A
                # slower run that still says "#3 of 17" is the correct answer
                # and the delta beside it already says the time got worse.
                rank, of = rank_of(db, mapname, track, leg, tier, style,
                                   prev["millis"], prev["submitted"], player)
                # `tier` is the board the run landed on AFTER demotion; `prevms`
                # is the standing row before this submit (here the same as best).
                return jsonify(
                    {"ok": True, "stored": False, "best": prev["millis"],
                     "rank": rank, "of": of, "rep": rid, "tier": tier,
                     "prevms": prev["millis"]}
                )

            db.execute(
                _UPSERT_RUN,
                (mapname, track, leg, tier, style, player, name, ticks,
                 tickrate, millis, flags, node, runid, now, rid),
            )
    except sqlite3.Error as exc:
        log.exception("run db error from %s: %s", src, exc)
        return fail(500, "storage error")

    # AFTER THE COMMIT, deliberately: the row this run just wrote has to be in
    # the table for `of` to count it, and for the run to not be ranked ahead of
    # a field it is not yet part of.  Its own row is excluded from `ahead` by
    # the submitted test rather than by a WHERE player<>?, because a player is
    # allowed exactly one row per board and excluding by id would hide a
    # duplicate rather than reveal it.
    rank, of = rank_of(db, mapname, track, leg, tier, style, millis, now, player)

    log.info(
        "run map=%r track=%d leg=%d tier=%s style=%s player=%r ticks=%d (%dms) "
        "rank=%d/%d rep=%d %s",
        mapname, track, leg, tier, style, player, ticks, millis, rank, of,
        rid, leaf or "-",
    )
    return jsonify({"ok": True, "stored": True, "best": millis,
                    "rank": rank, "of": of, "rep": rid, "tier": tier,
                    "prevms": prev["millis"] if prev is not None else 0})


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
        # Both tiers' counts, so the client can say "no ranked times yet, 37
        # community" without mixing trust levels in one list.
        counts = board_counts(db, mapname, track, leg, style)
        rows = board_rows(db, mapname, track, leg, tier, style, limit, offset)
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


def leg_dir(track, leg):
    """The directory name one leg's runs are filed under.

    A TRANSCRIPTION OF FS_LegDir (sh_defs.qc), and it must stay one.  The board
    key carries `track` and `leg` as integers; the disk spells them as a word,
    and there is no third place that knows both.  test_replays.py pins this
    against the QC source for the same reason it pins the leaf grammar: two
    independent spellings of one filename is how a recording goes missing
    while every row still says it is there.
    """
    if track <= 0:
        return "main" if leg <= 0 else "stage_%d" % leg
    if leg <= 0:
        return "bonus_%d" % track
    return "bonus_%d_stage_%d" % (track, leg)


def replay_file(row):
    """The file a replays row names: ``(path, "")``, or ``(None, why)``.

    `row` needs map_dir, track, leg and leaf, and kind (schema 6; absent reads
    'run').  `why` is "name" (leaf or map_dir fails its grammar, or an unknown
    kind), "outside" (resolves outside its root) or "missing" (not a file).
    The one path check /api/replay, sweep.py and the admin share; submit_run
    validates names too, but the row outlives that.  A 'run' lives under
    RUNS_DIR/<map_dir>/<leg dir>/, an 'evidence' row under KEEP_DIR/<map_dir>/.
    """
    kind = row["kind"] if "kind" in row.keys() else "run"
    leaf, map_dir = row["leaf"] or "", row["map_dir"] or ""
    if kind == "evidence":
        ok, root, sub = _EVLEAF_OK.match(leaf), KEEP_DIR, (map_dir, leaf)
    elif kind == "run":
        ok, root = _LEAF_OK.match(leaf), RUNS_DIR
        sub = (map_dir, leg_dir(row["track"], row["leg"]), leaf)
    else:
        return None, "name"
    if not ok or not _MAPNAME_OK.match(map_dir):
        return None, "name"
    root = os.path.realpath(root)
    path = os.path.realpath(os.path.join(root, *sub))
    if not path.startswith(root + os.sep):
        return None, "outside"
    if not os.path.isfile(path):
        return None, "missing"
    return path, ""


# --------------------------------------------------------------------------
# Evidence behind stage rows (schema 6).  sweep.py's cron runs these; a bad
# file skips only itself (none raises OSError, ValueError or IndexError).
# --------------------------------------------------------------------------

_REC_TAIL = 16384        # both writers put `abandon`/`end` in the last lines


def _rec_meta(path):
    """``(header, end_ticks or -1, abandoned, size, mtime, in_rows or -1)`` of a
    .rec, or None; in_rows is the `end` trailer's 5th field.

    The header is read to `begin` (64 lines at most), first spelling of a key
    wins; `end`/`abandon` come from whole lines in the last _REC_TAIL bytes.
    Both writers end every line with a newline, so an unterminated last line
    is a torn write (`end 82` of `end 8262 ...`) and reads as no end."""
    try:
        with open(path, "rb") as fh:
            st = os.fstat(fh.fileno())
            hdr = {}
            for _ in range(64):
                line = fh.readline()
                if not line:
                    break
                word, _sp, rest = line.decode("utf-8", "replace") \
                    .rstrip("\r\n").partition(" ")
                if word == "begin":
                    break
                hdr.setdefault(word, rest)
            fh.seek(max(0, st.st_size - _REC_TAIL))
            # [:-1] drops what follows the last \n: '' or a torn line.
            tail = fh.read().decode("utf-8", "replace").split("\n")[:-1]
        if st.st_size > _REC_TAIL:
            tail = tail[1:]                       # a partial first line
        end, abandoned, rows = -1, False, -1
        for line in tail:
            if line.startswith("end "):
                words = line.split()
                end = strict_int(words[1] if len(words) > 1 else None, 0, MAX_TICKS)
                end = -1 if end is None else end
                rows = strict_int(words[5] if len(words) > 5 else None, 0, MAX_TICKS)
                rows = -1 if rows is None or end < 0 else rows
            elif line.startswith("abandon "):
                abandoned = True
    except (OSError, ValueError, IndexError):
        return None
    return hdr, end, abandoned, st.st_size, st.st_mtime, rows


def _rec_tickrate_disagrees(hdr, tickrate):
    """"" when the header's tick can be this row's tickrate, else why not.

    THE TWO SPELLINGS ARE RECIPROCALS.  SV_RecOpen writes a PERIOD
    (`tickrate 0.01`, from pm_ticrate) and the POST sends a FREQUENCY (100), so
    this cannot be a string compare like the keys beside it.

    It is here because `millis` is `ticks * 1000 / tickrate` and `ticks` is
    pinned by the leaf's own prefix -- so with tickrate unbound, the published
    TIME was a caller-typed field that nothing on disk contradicted.  Measured
    by the second review: one POST turned a 7.000 s verified run into a 0.070 s
    verified run, under the victim's own name, with the PASS still current.
    """
    raw = (hdr.get("tickrate") or "").strip()
    if not raw or not tickrate:
        return ""                      # a recorder older than the key, or no claim
    try:
        period = float(raw)
    except ValueError:
        return ""                      # unparseable on disk is not the row's fault
    if period <= 0:
        return ""
    want = 1.0 / period
    # %g keeps six significant digits of the period, so the header's rate is
    # good to half the sixth digit / period^2; the lobby's %.4f and float32 add
    # 1e-4.  0.015 -> 3.2e-4 Hz; honest 3.3e-5 live.  max(0.5 Hz, 0.1%) let a
    # re-post shave 0.75% off a verified time; a flat 3e-4 dropped 96 Hz set as
    # 0.0104166667 (Patch 424 reviews).
    step = 0.5 * 10.0 ** (math.floor(math.log10(period)) - 5)
    if abs(want - tickrate) > step / (period * period) + 1e-4:
        return "tickrate %s (= %.4f/s) != %.4f/s" % (raw, want, tickrate)
    return ""


def _rec_disagrees(hdr, mapname, track, leg, runid, flags, tickrate=0):
    """"" when a .rec header can be the run being filed, else why not.

    Compares only keys the file actually carries, so a recorder older than a
    key is not punished for it -- the header grew `owner`/`runid` in v3 and
    `leg` in b57.  Used by submit_run to bind a claimed leaf to its file; the
    evidence path makes the same comparison inline in index_evidence.

    Not `owner` (Patch 424): it is the netname at SV_RecOpen and the submit's
    `name` is the one at the finish, so a rename mid-run or across a resume
    dropped an honest leaf.  The run is bound by runid and the player by the
    leaf's digest; a re-post cannot rename the replay row (submit_run).  `flags`
    is the board a run stands on, so an unbound one let a re-post move a verified
    replay to another board (the lobby sends the header's value: 42 of 42 live).
    """
    def differs(key, want, fold=str):
        got = fold((hdr.get(key) or "").strip())
        return got and str(want) != got and "%s %r != %r" % (key, got, str(want))

    # `map` folds case: mapname is the board key (clean_map lowercases) and the
    # header has the name as loaded -- surf_Aser dropped every leaf until 424.
    return (differs("map", mapname, str.lower) or differs("track", track)
            or differs("leg", leg) or differs("runid", runid)
            or differs("flags", flags, lambda v: (v.split() or [""])[0])
            or _rec_tickrate_disagrees(hdr, tickrate) or "")


def _keep_file(src, dst):
    """Hard-link src at dst (a copy when a link is refused), atomically."""
    if os.path.exists(dst) and os.path.samefile(src, dst):
        return
    tmp = dst + ".tmp"
    if os.path.lexists(tmp):
        os.unlink(tmp)
    try:
        os.link(src, tmp)
    except OSError:
        shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def index_evidence(conn, now=None, dry_run=False):
    """Index each EVIDENCE_DIR file that a leafless stage row's run left and no
    replay stands for, as a kind='evidence' leg-0 row kept under KEEP_DIR.

    tier/style '' keep the row off every board query; checked 0 queues it for
    the verifier (Patch 425).  -> {"indexed", "bad", "deferred", "files"}; a
    dry run writes nothing and counts what it would index."""
    now = int(time.time()) if now is None else now
    out = {"indexed": 0, "bad": 0, "deferred": 0, "files": []}
    try:
        dirs = sorted(os.listdir(EVIDENCE_DIR))
    except OSError:
        return out
    have = {(r["map"], r["runid"]) for r in conn.execute(
        "SELECT map, runid FROM replays WHERE kind = 'evidence'")}
    for d in dirs:
        if not _MAPNAME_OK.match(d):
            continue
        try:
            leaves = sorted(os.listdir(os.path.join(EVIDENCE_DIR, d)))
        except OSError:
            continue
        for leaf in leaves:
            if not _EVLEAF_OK.match(leaf):
                continue
            runid, key = leaf[:-4], d.lower()
            if (key, runid) in have:
                continue
            refs = conn.execute(
                "SELECT r.track, r.player, MAX(r.name) AS name FROM runs r"
                " WHERE r.leg > 0 AND r.replay_id = 0 AND r.runid = ? AND r.map = ?"
                "   AND NOT EXISTS (SELECT 1 FROM replays p WHERE p.runid = r.runid"
                "        AND p.map = r.map AND p.track = r.track"
                "        AND p.player = r.player AND p.leg = 0)"
                " GROUP BY r.track, r.player ORDER BY r.track, r.player",
                (runid, key)).fetchall()
            if not refs:
                continue                  # backs nothing; the lobby sweeps it
            players = sorted({r["player"] for r in refs})
            if len(players) > 1:
                # A run is one player's; filing it under either would be a guess.
                log.warning("evidence %s/%s is named by %d players' stage rows"
                            " %r; not indexed", d, leaf, len(players), players[:4])
                out["bad"] += 1
                continue
            src = os.path.join(EVIDENCE_DIR, d, leaf)
            meta = _rec_meta(src)
            hdr = meta[0] if meta else {}
            track = strict_int(hdr.get("track"), 0, MAX_TRACK)
            ref = next((r for r in refs if r["track"] == track), None)
            spt = strict_float(hdr.get("movetickrate"), 1e-6, 1.0) or \
                strict_float(hdr.get("tickrate"), 1e-6, 1.0)
            if (meta is None or ref is None or spt is None
                    or clean_text(hdr.get("runid")) != runid
                    or clean_text(hdr.get("map")).lower() != key
                    or strict_int(hdr.get("leg"), 0, MAX_LEG) != 0):
                log.warning("evidence %s/%s does not describe its stage rows"
                            " (header runid %r map %r track %r leg %r)", d, leaf,
                            hdr.get("runid"), hdr.get("map"), hdr.get("track"),
                            hdr.get("leg"))
                out["bad"] += 1
                continue
            _hdr, end, _abandoned, size, mtime, _rows = meta
            if end < 0 and now - mtime < EVIDENCE_SETTLE:
                out["deferred"] += 1      # the non-stream writer may be mid-file
                continue
            if dry_run:
                out["indexed"] += 1
                out["files"].append("%s/%s" % (d, leaf))
                continue
            ticks = max(end, 0)
            words = (hdr.get("flags") or "0").split()
            flags = strict_int(words[0] if words else 0, 0, 0x7FFFFFFF) or 0
            port = re.search(r"-p([0-9]+)$", runid)
            try:
                os.makedirs(os.path.join(KEEP_DIR, d), exist_ok=True)
                _keep_file(src, os.path.join(KEEP_DIR, d, leaf))
            except OSError as exc:
                log.error("evidence %s/%s not kept: %s", d, leaf, exc)
                out["bad"] += 1
                continue
            with conn:
                n = conn.execute(
                    "INSERT INTO replays (map, map_dir, track, leg, leaf, tier,"
                    " style, player, name, ticks, tickrate, millis, flags, node,"
                    " submitted, bytes, truncated, seen, checked, runid, kind, bound)"
                    " VALUES (?,?,?,0,?,'','',?,?,?,?,?,?,?,?,?,0,-1,0,?,'evidence',1)"
                    " ON CONFLICT(map, track, leg, leaf) DO NOTHING",
                    (key, d, track, leaf, ref["player"], ref["name"], ticks,
                     1.0 / spt, int(round(ticks * spt * 1000.0)), flags,
                     "p" + port.group(1) if port else "?", int(mtime), size,
                     runid)).rowcount
            have.add((key, runid))
            if n:
                out["indexed"] += 1
                out["files"].append("%s/%s" % (d, leaf))
    return out


def requeue_evidence(conn):
    """Queue for the verifier the evidence rows indexed before Patch 425, which
    wrote checked 1 and never attempted one (seen -1).  -> rows queued."""
    with conn:
        return conn.execute(
            "UPDATE replays SET checked = 0 WHERE kind = 'evidence'"
            " AND checked = 1 AND seen = -1 AND NOT EXISTS"
            " (SELECT 1 FROM verdicts v WHERE v.replay_id = replays.id)").rowcount


def _lobbies_file(path):
    """True for a path under EVIDENCE_DIR: the lobbies' own, never unlinked here."""
    return os.path.realpath(path).startswith(
        os.path.realpath(EVIDENCE_DIR) + os.sep)


def gc_evidence(conn):
    """Drop each evidence row no leafless stage row references any more, then
    (after the commit) its kept file; then kept files with no row that are
    older than KEEP_ORPHAN_AGE.  -> rows dropped."""
    n = 0
    for row in conn.execute(
            "SELECT id, map_dir, track, leg, leaf, kind FROM replays"
            " WHERE kind = 'evidence'").fetchall():
        with conn:
            # The reference test sits inside the DELETE: a stage post landing
            # between a SELECT and a DELETE cannot orphan its link.
            gone = conn.execute(
                "DELETE FROM replays WHERE id = ? AND kind = 'evidence'"
                " AND NOT EXISTS (SELECT 1 FROM runs r WHERE r.leg > 0"
                "   AND r.replay_id = 0 AND r.runid = replays.runid"
                "   AND r.map = replays.map AND r.track = replays.track"
                "   AND r.player = replays.player)", (row["id"],)).rowcount
            if gone:
                conn.execute("DELETE FROM verdicts WHERE replay_id = ?", (row["id"],))
                conn.execute("DELETE FROM reviews WHERE replay_id = ?", (row["id"],))
        if gone:
            n += 1
            path = replay_file(row)[0]
            if path and _lobbies_file(path):    # SURFD_KEEP is SURFD_EVIDENCE
                log.warning("evidence %d: %s is the lobbies' file; not removed",
                            row["id"], path)
            elif path:
                try:
                    os.unlink(path)
                except OSError as exc:
                    log.warning("evidence %d: kept file not removed: %s",
                                row["id"], exc)

    if os.path.realpath(KEEP_DIR) == os.path.realpath(EVIDENCE_DIR):
        log.error("SURFD_KEEP is the lobbies' evidence dir; orphan pass skipped")
        return n
    kept = {(r["map_dir"], r["leaf"]) for r in conn.execute(
        "SELECT map_dir, leaf FROM replays WHERE kind = 'evidence'")}
    now = time.time()
    try:
        dirs = os.listdir(KEEP_DIR)
    except OSError:
        return n
    for d in dirs:
        try:
            leaves = os.listdir(os.path.join(KEEP_DIR, d))
        except OSError:
            continue
        for leaf in leaves:
            if not leaf.endswith((".rec", ".rec.tmp")) or (d, leaf) in kept:
                continue
            path = os.path.join(KEEP_DIR, d, leaf)
            if _lobbies_file(path):
                continue
            try:
                if now - os.lstat(path).st_mtime > KEEP_ORPHAN_AGE:
                    os.unlink(path)
                    log.warning("evidence: removed orphan %s/%s", d, leaf)
            except OSError:
                pass
    return n


@app.get("/api/replay/<int:rid>")
def replay(rid):
    """Serve the recording named by one `replays` row.

    THE HANDLE IS THE LEDGER ID AND NOT A PATH, which is the whole security
    design.  A caller names a row; surfd decides what file that row means.  So
    there is no attacker-supplied path component anywhere in this route, and
    the traversal question is answered by construction rather than by
    filtering -- the realpath check below is a second lock on a door that has
    no handle on the outside.

    WHY A ROW CAN EXIST AND THE FILE NOT.  Nothing prunes any more (see
    `rec_runs_keep 0`), so in the normal case they agree.  They can still
    disagree: a disk restored from a backup older than the row, a file moved by
    hand, or -- the one that will actually happen -- a recording written by a
    lobby on ANOTHER machine once more than one node is keyed.  That is a 404
    with a distinct message, not a 500 and not a lie, and it is logged, because
    it means the archive and the index have drifted and somebody should know.

    NO WRITE ON A GET.  The `seen`/`checked` columns exist for exactly this
    observation and filling them here would be nearly free -- and wrong: it
    would put a database write on the one public path that can be hit in a
    loop, on a single-worker gunicorn, to save a background sweep that is
    deferred by design.  The sweep can do it when it exists.
    """
    now = int(time.time())
    src = rate_key()
    if not rate_ok(src, now, REPLAY_RATE_MAX, "replay"):
        return fail(429, "rate limited")

    try:
        db = get_db()
        row = db.execute(
            "SELECT map_dir, track, leg, leaf, kind, bytes FROM replays"
            " WHERE id = ?",
            (rid,),
        ).fetchone()
    except sqlite3.Error as exc:
        log.exception("replay db error: %s", exc)
        return fail(500, "storage error")

    if row is None:
        return fail(404, "no such replay")

    leaf = row["leaf"]
    path, why = replay_file(row)
    if why == "name":
        log.error("replay %d has an unusable name: map_dir=%r leaf=%r",
                  rid, row["map_dir"], leaf)
        return fail(404, "no such replay")
    if why == "outside":
        log.error("replay %d resolved outside the run tree: %r/%s",
                  rid, row["map_dir"], leaf)
        return fail(404, "no such replay")
    if why:
        log.warning("replay %d indexed but absent on disk: %r/%s",
                    rid, row["map_dir"], leaf)
        return fail(404, "replay not on this node")

    # send_file AND NOT read-then-Response: the body is ~1 MB of a 7.9 GB box
    # with no swap, and this is a single-worker gunicorn.  Reading it into a
    # Python string first would hold the whole file per concurrent request for
    # no gain; send_file hands nginx a file it can stream.
    #
    # text/plain BECAUSE A .rec IS TEXT, and being honest about that is what
    # lets nginx gzip it -- ~5x on this content, on a home upstream link.  It
    # is NOT gzipped at rest here; that is owed by the retention decision and
    # is a separate piece of work.
    try:
        resp = send_file(path, mimetype="text/plain",
                         as_attachment=True, download_name=leaf,
                         conditional=True)
    except OSError as exc:
        log.exception("replay %d unreadable: %s", rid, exc)
        return fail(500, "storage error")
    resp.headers["X-Surfd-Replay"] = str(rid)
    return resp


# --------------------------------------------------------------------------
# Public web leaderboard (/board/), proxied from proto.bar/ftesurf/board/
# --------------------------------------------------------------------------
#
# The browser sees /ftesurf/board/ where Flask sees /board/, so the page uses
# relative URLs only.  These routes never touch `session`, so they never set
# a cookie.  Public JSON carries no player id, verdict, reason or review.

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
WEB_FILES = {"board.js": "text/javascript", "board.css": "text/css"}
WEB_RATE_MAX = 120       # API reads per RATE_WINDOW per source, bucket "web"
WEB_MAPS_TTL = 60        # seconds the serialized maps list is reused
WEB_PAGE = 50            # rows per /board/api/map call
WEB_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
           "font-src 'self'; connect-src 'self'; img-src 'self'; "
           "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
# The web board is ranked only, like the in-game board since Patch 355: a
# community (demoted) run is never counted or listed here.  A map opens on the
# first of these with rows, else the first board it has.
WEB_DEFAULT_BOARDS = ((0, 0, STYLE_CLEAN), (0, 0, STYLE_SEGMENTED))

_web_lock = threading.Lock()
_web_maps = {"at": None, "body": b""}


def _json(payload, cache):
    resp = Response(json.dumps(payload, separators=(",", ":")),
                    status=200, mimetype="application/json")
    resp.headers["Cache-Control"] = cache
    return resp


def _web_file(name, mimetype):
    try:
        with open(os.path.join(WEB_DIR, name), "rb") as fh:
            data = fh.read()
    except OSError as exc:
        log.error("web board file %s unreadable: %s", name, exc)
        return fail(404, "not found")
    resp = Response(data, status=200, mimetype=mimetype)
    resp.headers["Cache-Control"] = "no-cache"
    resp.add_etag()
    return resp.make_conditional(request)


@app.get("/board/")
def web_page():
    return _web_file("board.html", "text/html")


@app.get("/board/<name>")
def web_asset(name):
    mimetype = WEB_FILES.get(name)       # a fixed allowlist, never a path
    if mimetype is None:
        return fail(404, "not found")
    return _web_file(name, mimetype)


def _web_maps_body(now):
    """Every zoned map with a BSP, plus every map with ranked runs, with its
    main ranked clean WR.  The WR window orders by BOARD_ORDER, so it is always
    /api/board's row 1."""
    bsp, zoned = map_index()
    db = get_db()
    stats = {r["map"]: r for r in db.execute(
        "SELECT map, COUNT(*) AS runs, MAX(submitted) AS last"
        "  FROM runs WHERE tier=? GROUP BY map", (TIER_RANKED,)).fetchall()}
    wrs = {r["map"]: r for r in db.execute(
        "SELECT r.map, r.name, r.millis, " + VER_SQL + " AS ver FROM ("
        "  SELECT map, name, millis, replay_id, ROW_NUMBER() OVER"
        "         (PARTITION BY map ORDER BY " + BOARD_ORDER + ") AS k"
        "    FROM runs WHERE track=0 AND leg=0 AND tier=? AND style=?) r"
        " WHERE r.k = 1", (TIER_RANKED, STYLE_CLEAN)).fetchall()}
    maps = []
    for key in sorted((set(bsp) & set(zoned)) | set(stats)):
        st, wr = stats.get(key), wrs.get(key)
        maps.append({
            "map": bsp.get(key, key),
            "runs": st["runs"] if st else 0,
            "last": st["last"] if st else 0,
            "wr": ({"name": wr["name"], "ms": wr["millis"], "ver": wr["ver"]}
                   if wr else None),
        })
    return json.dumps({"v": 1, "t": now, "maps": maps},
                      separators=(",", ":")).encode("utf-8")


@app.get("/board/api/maps")
def web_maps():
    now = int(time.time())
    if not rate_ok(rate_key(), now, WEB_RATE_MAX, "web"):
        return fail(429, "rate limited")
    with _web_lock:
        at, body = _web_maps["at"], _web_maps["body"]
    if at is None or not 0 <= now - at < WEB_MAPS_TTL:
        try:
            body = _web_maps_body(now)
        except sqlite3.Error as exc:
            log.exception("web maps db error: %s", exc)
            return fail(500, "storage error")
        with _web_lock:
            _web_maps["at"], _web_maps["body"] = now, body
    resp = Response(body, status=200, mimetype="application/json")
    resp.headers["Cache-Control"] = "max-age=60"
    return resp


@app.get("/board/api/map")
def web_map():
    now = int(time.time())
    if not rate_ok(rate_key(), now, WEB_RATE_MAX, "web"):
        return fail(429, "rate limited")

    mapname = clean_map(request.args.get("map"))
    if not mapname:
        return fail(400, "bad map")
    # `tier` is not a parameter: old links that carry one still open ranked.
    raw = {k: request.args.get(k, "") for k in ("track", "leg", "style")}
    track = strict_int(raw["track"] or 0, 0, MAX_TRACK)
    leg = strict_int(raw["leg"] or 0, 0, MAX_LEG)
    style = raw["style"] or STYLE_CLEAN
    if track is None or leg is None:
        return fail(400, "bad leg")
    if style not in STYLES:
        return fail(400, "bad style")
    offset = clamp_int(request.args.get("offset"), 0, MAX_RUNS, 0)

    bsp, zoned = map_index()
    try:
        db = get_db()
        boards = [{"track": r["track"], "leg": r["leg"], "style": r["style"],
                   "n": r["n"]} for r in db.execute(
            "SELECT track, leg, style, COUNT(*) AS n FROM runs"
            " WHERE map=? AND tier=? GROUP BY 1, 2, 3 ORDER BY 1, 2, 3",
            (mapname, TIER_RANKED)).fetchall()]
        if not boards and not (mapname in bsp and mapname in zoned):
            return fail(404, "no such map")
        if not any(raw.values()) and boards:
            have = [(b["track"], b["leg"], b["style"]) for b in boards]
            track, leg, style = next(
                (d for d in WEB_DEFAULT_BOARDS if d in have), have[0])
        n = board_counts(db, mapname, track, leg, style)[TIER_RANKED]
        rows = board_rows(db, mapname, track, leg, TIER_RANKED, style,
                          WEB_PAGE, offset)
    except sqlite3.Error as exc:
        log.exception("web map db error: %s", exc)
        return fail(500, "storage error")
    for row in rows:
        del row["player"]
    return _json({"v": 1, "t": now, "map": mapname,
                  "disp": bsp.get(mapname, mapname), "boards": boards,
                  "track": track, "leg": leg, "style": style, "n": n,
                  "offset": offset, "limit": WEB_PAGE, "rows": rows},
                 "max-age=15")


@app.after_request
def web_headers(resp):
    if request.path.startswith("/board/"):
        resp.headers["Content-Security-Policy"] = WEB_CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


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
                             client_identity=client_identity, disk=disk_status,
                             runs=dict(replay_file=replay_file, restand=restand,
                                       restage=restage, stage_counts=stage_counts,
                                       public_state=public_state,
                                       rank_of=rank_of, leg_dir=leg_dir,
                                       max_errors=VERIFY_MAX_ERRORS))
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
