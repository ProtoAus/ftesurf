#!/usr/bin/env python3
"""
admin.py -- the FTESurf fleet control panel, as a Flask blueprint on surfd.

Mounted at /admin. DEFAULT OFF: with SURFD_ADMIN_HASH unset this module
registers nothing at all and surfd behaves exactly as it did before, which is
what makes the change falsifiable (test_admin.py proves it).

WHY THIS LIVES ON surfd
=======================

surfd already holds the `lobbies` table, already runs behind nginx, and is on
the same box as the five game servers -- so it reaches them on 127.0.0.1.
That is the whole security argument for this design:

    THE PANEL IS PUBLIC. RCON NEVER IS.

rcon rides the same UDP port as the game and cannot be firewalled off by port
(sv_main.c:4441-4444 dispatches it from the ordinary connectionless handler).
Putting the control surface behind an authenticated HTTPS endpoint on the same
machine means the rcon password never has to leave loopback, and rcon.py
enforces the loopback half structurally rather than by convention.

THE HONEST COST, stated because it is the one place in the plan where
convenience was chosen over the smaller attack surface: a public login is a
permanent, always-on, internet-facing surface on the machine that runs the game
servers. Everything below -- the lockout, the scrypt parameters, the separate
secret, the own-location-block nginx rule -- exists to pay for that choice.

WHAT IT DELIBERATELY DOES NOT DO
================================

  * No free-form rcon console. Every control is a named endpoint with its own
    validator. A "just run this command" box would hand the whole console to
    anyone who gets a session, and would defeat rcon.py's argument checking by
    design rather than by accident.
  * No PLAYER IP addresses, anywhere. Player NAMES to an authenticated admin
    are not a disclosure needing a terms change; their addresses would be. The
    status parser never reads the address line (see parse_status), and
    clean_reply() redacts rcon output and log tails as a second layer.

    The directory table is the deliberate exception and shows each LOBBY's own
    advertised address. That is the server's address, not a player's; it is
    already public in /lobbies.json; and it is the single most important thing
    to be able to see before going public, because "every row advertises
    192.168.1.102" is exactly the failure PUBLIC_HOST exists to prevent.
  * No password change over the web. Rotating the admin password means running
    mkadminpw.py on the Pi and restarting surfd. One less authenticated write
    path, and it keeps the credential in the 0600 env file where the rest of
    the secrets already live.
  * It does not use lobby_master_key. Three game-server configs hold that
    secret; compromising one config must not hand over the fleet.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import shutil
import subprocess
import threading
import time

from flask import (Blueprint, Response, current_app, jsonify, redirect,
                   render_template, request, session, url_for)

from rcon import (Rcon, RconError, RconThrottled, RconBlocked, clean_reply,
                  budget_left)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# "tier:port" pairs, overridable with SURFD_ADMIN_LOBBIES. run.sh maps
# tier -> cfg/lobbyN.cfg, which is where the port actually lives; this list only
# has to agree with it.
#
# Renumbered in Stage 10 from 27500/27510/27520. The range starts at 27510 so
# that 27500 -- what an unconfigured QuakeWorld server binds -- is never
# forwarded at the router and so cannot be exposed by accident. 4 and 5 are the
# bhop lobbies, added in QC build 57 on the same ten-port spacing.
DEFAULT_LOBBIES = "1:27510,2:27520,3:27530,4:27540,5:27550"

SESSION_IDLE_MAX = 30 * 60      # seconds of inactivity before a session dies
SESSION_ABS_MAX = 12 * 60 * 60  # hard lifetime regardless of activity

LOCKOUT_FAILS = 5               # failed logins before a lockout
LOCKOUT_WINDOW = 15 * 60        # over this many seconds
LOCKOUT_TIME = 15 * 60          # how long the lockout lasts
LOCKOUT_TABLE_MAX = 4096

LOG_TAIL_BYTES = 24 * 1024      # how much of a log file to read for the tail
LOG_TAIL_LINES = 60

# Validators. Every one of these is the last line of defence in front of
# rcon.py's argument check -- both run, deliberately.
MAPNAME = re.compile(r"^[a-z0-9_]{1,63}$")
HOSTNAME_TEXT = re.compile(r"^[A-Za-z0-9 _.:|!/+()\[\]-]{1,63}$")
SAY_TEXT = re.compile(r"^[A-Za-z0-9 _.,:!?'/+()\[\]@-]{1,120}$")


class AdminError(Exception):
    """A control was refused. The message is shown to the admin verbatim."""


# --------------------------------------------------------------------------
# Settings: the process environment FIRST, then surfd.env
# --------------------------------------------------------------------------
#
# THE BUG THIS FIXES, because it is not obvious and it cost a user-visible
# failure. surfd.service sets only:
#
#     Environment=SURFD_HOME=/srv/nvme/surfd
#
# There is NO EnvironmentFile=, so nothing puts surfd.env into the process
# environment. surfd.py never noticed because it does not read SURFD_KEY from
# the environment at all -- load_secret() opens surfd.env and parses it. This
# module originally used os.environ.get() for its own settings, which meant a
# correctly-populated surfd.env produced, forever:
#
#     admin panel disabled (SURFD_ADMIN_HASH is unset)
#
# with the value plainly present in the file. The panel could not be turned on
# by any amount of editing.
#
# Reading BOTH, in this order, is the fix rather than adding EnvironmentFile=
# to the unit: that would need root to install, and systemd's env-file parser
# is not the shell -- it does not strip quotes the way a reader expects, so a
# quoted secret would arrive with its quotes attached and fail comparison in a
# way nothing would explain. Parsing the file ourselves matches how SURFD_KEY
# has always been read, so there is one convention instead of two.
#
# Environment wins, so a systemd Environment= line or an inline override in a
# test still takes precedence over the file.

BASE_DIR = os.environ.get("SURFD_HOME", "/srv/nvme/surfd")
ENV_PATH = os.environ.get("SURFD_ENV", os.path.join(BASE_DIR, "surfd.env"))


def _from_env_file(name, path=None):
    """Read one NAME=value out of the shell-sourceable env file. "" if absent."""
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
        return ""
    return ""


def setting(name, default=""):
    """A configuration value, from the environment or else from surfd.env."""
    value = os.environ.get(name)
    if value is not None and value.strip():
        return value.strip()
    value = _from_env_file(name)
    return value if value else default


# --------------------------------------------------------------------------
# Password hashing -- stdlib scrypt, because the Pi has no argon2 module
# --------------------------------------------------------------------------
#
# Format:  scrypt$<n>$<r>$<p>$<salt-b64>$<hash-b64>
#
# N=2**15 (32 MB per verification) rather than the larger figures general
# guidance suggests, and the reason is specific to this box: gunicorn runs ONE
# worker with four threads on an 8-core aarch64 SBC with no swap. At N=2**17
# four concurrent login attempts would allocate half a gigabyte and the fleet's
# own directory service would be the collateral. The lockout below -- five
# tries per IP per fifteen minutes -- is what makes the work factor sufficient,
# not the parameter alone. If this ever moves to a bigger host, raise N here
# and re-run mkadminpw.py; old hashes keep working because N is stored in the
# string.

SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
# scrypt needs maxmem >= 128 * N * r * p, plus headroom for the allocator.
SCRYPT_MAXMEM = 128 * SCRYPT_N * SCRYPT_R * SCRYPT_P * 2


def hash_password(password, salt=None, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                        dklen=SCRYPT_DKLEN, maxmem=128 * n * r * p * 2)
    return "scrypt$%d$%d$%d$%s$%s" % (
        n, r, p,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password, encoded):
    """Constant-time check of `password` against a stored hash string.

    Returns False on any malformed hash rather than raising, so a corrupted
    env file locks the panel instead of crashing surfd's other endpoints.
    """
    try:
        scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n), int(r), int(p)
        salt = base64.b64decode(salt_b64)
        expect = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                            dklen=len(expect), maxmem=128 * n * r * p * 2)
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(dk, expect)


# --------------------------------------------------------------------------
# Lockout (in-process; gunicorn runs a single worker on purpose, same as the
# heartbeat rate limiter surfd.py already relies on)
# --------------------------------------------------------------------------

_lock = threading.Lock()
_fails = {}      # ip -> [timestamps]
_locked = {}     # ip -> unlock time


def _prune(now):
    if len(_fails) > LOCKOUT_TABLE_MAX:
        for k in [k for k, v in _fails.items()
                  if not v or v[-1] < now - LOCKOUT_WINDOW]:
            _fails.pop(k, None)
        if len(_fails) > LOCKOUT_TABLE_MAX:
            _fails.clear()
    for k in [k for k, t in _locked.items() if t < now]:
        _locked.pop(k, None)


def lockout_remaining(ip, now=None):
    now = now or time.time()
    with _lock:
        _prune(now)
        until = _locked.get(ip)
        return int(until - now) if until and until > now else 0


def note_failure(ip, now=None):
    now = now or time.time()
    with _lock:
        _prune(now)
        hits = [t for t in _fails.get(ip, ()) if t > now - LOCKOUT_WINDOW]
        hits.append(now)
        _fails[ip] = hits
        if len(hits) >= LOCKOUT_FAILS:
            _locked[ip] = now + LOCKOUT_TIME
            _fails[ip] = []
            return True
    return False


def note_success(ip):
    with _lock:
        _fails.pop(ip, None)
        _locked.pop(ip, None)


# --------------------------------------------------------------------------
# Talking to the fleet
# --------------------------------------------------------------------------

def parse_lobbies(raw):
    out = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        tier, _, port = part.partition(":")
        try:
            out.append({"tier": tier.strip(), "port": int(port)})
        except ValueError:
            continue
    return out


def parse_status(text):
    """Pull the panel's view of one server out of a `status` reply.

    THE ADDRESS LINE IS NEVER READ. Over rcon the engine forces the 40-column
    layout (sv_ccmds.c:2446-2451: any redirection that is not RD_OBLIVION/
    RD_NONE sets columns=40) which prints two lines per client:

        name               userid frags        <- no leading space
          address          rate ping drop      <- two leading spaces

    So "line begins with a space" identifies the address line structurally,
    and this parser skips it without looking at its contents. That is the
    primary control; clean_reply()'s redaction is the second layer.

    UNVERIFIED AGAINST A POPULATED TABLE. This was written from the printf
    formats at sv_ccmds.c:2629-2633 and checked against a real but EMPTY
    client list -- no player was connected when it was built, and launching a
    client was not available at the time. The header/uptime/map parsing IS
    verified against live output. Treat the player rows as the part to confirm
    first when someone is actually on a server.
    """
    info = {"map": "", "uptime": "", "map_uptime": "", "players": [],
            "cpu": "", "public": ""}
    in_players = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("---"):
            in_players = True
            continue
        if not in_players:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if key == "current map":
                # "surf_lux" or "surf_lux (Long Map Name)"
                info["map"] = value.split(" ")[0]
            elif key == "server uptime":
                info["uptime"] = value
            elif key == "map uptime":
                info["map_uptime"] = value
            elif key == "cpu utilization":
                info["cpu"] = value
            elif key == "public":
                info["public"] = value
            continue
        if not line or not stripped:
            continue
        if line[0].isspace():
            continue        # the address line. Not read, by construction.
        # name(16) + 2 spaces + userid(%6i) + frags(%5i) [+ " (s)"]
        m = re.match(r"^(.{1,16}?)\s\s+(\d+)\s+(-?\d+)\s*(\(s\))?\s*$", line)
        if m:
            info["players"].append({
                "name": m.group(1).strip(),
                "userid": int(m.group(2)),
                "frags": int(m.group(3)),
                "spectator": bool(m.group(4)),
            })
    return info


_CVAR_REPLY = re.compile(r'^"?([A-Za-z0-9_]+)"?\s+is\s+"([^"]*)"')


def parse_cvar(text, name):
    """Read a value out of the engine's `<cvar>` echo. "" if not found."""
    for line in text.splitlines():
        m = _CVAR_REPLY.match(line.strip())
        if m and m.group(1) == name:
            return m.group(2)
    return ""


# How long a cached rcon answer stays good. These are the panel's real defence
# against the engine's amplification block (see the essay in rcon.py); the
# token bucket there is the backstop for when something here regresses.
#
# STATUS_TTL is what bounds the steady-state packet rate. At 20s it is one
# packet per lobby per 20s == 1.5 per 30s window, against an engine limit of
# 15. The panel's first version sent 24 and was blocked for 24 hours.
#
# CVAR_TTL is long because those three values only change when an admin changes
# them -- and when one does, the write path updates the cache directly with the
# value it just set, so the page still updates instantly. A slow refresh is not
# a stale display; it is a display that is kept current by the writer instead of
# by polling.
STATUS_TTL = 20.0
CVAR_TTL = 600.0


class Fleet:
    """The five (or however many) lobbies, addressed by tier."""

    def __init__(self, lobbies, password, crypt=True):
        self.lobbies = lobbies
        self.password = password
        self.crypt = crypt
        self._lock = threading.Lock()
        self._status = {}      # tier -> (expires_at, snapshot dict)
        self._cvars = {}       # tier -> (expires_at, {cvar: value})

    def tiers(self):
        return [l["tier"] for l in self.lobbies]

    def port_for(self, tier):
        for l in self.lobbies:
            if l["tier"] == str(tier):
                return l["port"]
        raise AdminError("no such lobby: %r" % (tier,))

    def rcon(self, tier, timeout=1.2, collect_for=0.35):
        return Rcon("127.0.0.1", self.port_for(tier), self.password,
                    crypt=self.crypt, timeout=timeout, collect_for=collect_for)

    def run(self, tier, argv, expect_reply=True):
        try:
            return self.rcon(tier).execute(argv, expect_reply=expect_reply)
        except RconError as exc:
            raise AdminError(str(exc)) from exc

    def note_cvar(self, tier, cvar, value):
        """Record a value we just SET, so the page shows it without asking.

        The write path knows the new value already. Re-reading it over rcon
        would spend budget to learn something we told the server ourselves.
        """
        with self._lock:
            expires, values = self._cvars.get(tier, (0.0, {}))
            values = dict(values)
            values[cvar] = value
            # Keep whatever expiry was already running rather than extending
            # it: this is a correction to the cache, not a fresh read of it.
            self._cvars[tier] = (max(expires, time.monotonic() + 5.0), values)

    def invalidate(self, tier):
        """Force the next snapshot of one lobby to actually ask the server."""
        with self._lock:
            self._status.pop(tier, None)
            self._cvars.pop(tier, None)

    def _fetch_status(self, tier):
        out = {"tier": tier, "port": self.port_for(tier), "up": False,
               "error": "", "throttled": False, "map": "", "uptime": "",
               "map_uptime": "", "players": [], "cpu": "", "public": ""}
        try:
            status = clean_reply(self.rcon(tier, collect_for=0.8)
                                 .execute(["status"]))
        except RconThrottled as exc:
            # Not an error about the server. Say so, and keep `up` unset rather
            # than claiming the lobby is down because we chose not to ask.
            out["error"] = str(exc)
            out["throttled"] = True
            return out
        except RconBlocked as exc:
            out["error"] = str(exc)
            return out
        except RconError as exc:
            out["error"] = str(exc)
            return out
        if not status.strip():
            # Deliberately does NOT say "server down". The directory rows in
            # /api/state say whether the process is alive, and when a lobby is
            # heartbeating happily this message used to accuse it of being
            # dead. Silence on rcon has three causes and this names all three.
            out["error"] = ("no rcon reply -- the server may be down, the "
                            "rcon password may not match, or the engine's "
                            "amplification guard may have blocked us")
            return out
        out["up"] = True
        out.update(parse_status(status))
        return out

    def _fetch_cvars(self, tier):
        """Read the three settings. Returns (values, got_anything).

        The caller must not cache a failed read: three empty strings held for
        CVAR_TTL would blank the hostname and rotation on the page for ten
        minutes because of one throttled moment.
        """
        values = {"lobby_maps": "", "lobby_cycle": "", "hostname": ""}
        ok = False
        for cvar in values:
            try:
                reply = clean_reply(self.rcon(tier).execute([cvar]))
                values[cvar] = parse_cvar(reply, cvar)
                ok = True
            except RconError:
                pass
        return values, ok

    def snapshot(self, tier, force=False):
        """Everything the panel shows for one lobby, mostly from cache.

        Caching is not an optimisation here. Asking the server every time is
        what got the panel blocked for 24 hours on its first run; see rcon.py.
        """
        now = time.monotonic()
        with self._lock:
            cached = self._status.get(tier)
            cvar_cached = self._cvars.get(tier)
        if force or not cached or cached[0] <= now:
            snap = self._fetch_status(tier)
            # A throttled read is not worth caching for a full TTL -- the
            # budget frees up on its own and the next poll should try again.
            ttl = 3.0 if snap.get("throttled") else STATUS_TTL
            with self._lock:
                self._status[tier] = (now + ttl, snap)
        else:
            snap = dict(cached[1])
            snap["cached"] = True
        stale_cvars = force or not cvar_cached or cvar_cached[0] <= now
        if stale_cvars and not snap.get("throttled"):
            values, ok = self._fetch_cvars(tier)
            if ok:
                with self._lock:
                    self._cvars[tier] = (now + CVAR_TTL, values)
            elif cvar_cached:
                # Keep what we had; try again soon rather than in ten minutes.
                values = cvar_cached[1]
                with self._lock:
                    self._cvars[tier] = (now + 15.0, values)
        elif cvar_cached:
            values = cvar_cached[1]
        else:
            values = {"lobby_maps": "", "lobby_cycle": "", "hostname": ""}
        out = dict(snap)
        out.update(values)
        out["budget_left"] = budget_left("127.0.0.1", self.port_for(tier))
        return out


# --------------------------------------------------------------------------
# systemd, through a narrow sudoers line and never a shell
# --------------------------------------------------------------------------

UNIT_ACTIONS = ("start", "stop", "restart")


def systemctl(action, tier, allowed_tiers):
    """Run exactly one systemctl verb against exactly one ftesurf@N unit.

    subprocess with a LIST and shell=False -- there is no shell here, so the
    unit name cannot become a command no matter what it contains. It is also
    validated against the configured tier list first, so the panel can only
    ever name a unit it already knows about.

    Requires a sudoers line (see surfd-admin.sudoers). Without it sudo asks for
    a password, gets EOF from -n, and this reports that plainly instead of
    hanging -- which is the failure mode to expect until a human with root has
    installed the file.
    """
    if action not in UNIT_ACTIONS:
        raise AdminError("unknown action %r" % (action,))
    if str(tier) not in [str(t) for t in allowed_tiers]:
        raise AdminError("unknown lobby %r" % (tier,))
    sudo = shutil.which("sudo")
    if not sudo:
        raise AdminError("sudo is not installed")
    # NO ".service" SUFFIX, AND THAT IS NOT A STYLE CHOICE.
    #
    # sudo matches the granted command against the argument vector LITERALLY.
    # The grant already installed on this Pi (/etc/sudoers.d/ftesurf, and
    # `sudo -l` confirms it) reads:
    #
    #     /usr/bin/systemctl start ftesurf@1        <- no suffix
    #
    # so `systemctl restart ftesurf@1.service` does NOT match it and sudo falls
    # through to asking for a password, which -n turns into a refusal. systemd
    # itself treats the two spellings as the same unit, so the suffix looks
    # harmless and the failure looks like "the sudoers line is missing" when it
    # is actually present and simply spelled differently. Cost an hour once;
    # if the grant is ever rewritten WITH the suffix, change this line to match
    # it rather than adding a second grant.
    unit = "ftesurf@%s" % tier
    try:
        proc = subprocess.run(
            [sudo, "-n", "/usr/bin/systemctl", action, unit],
            capture_output=True, text=True, timeout=20, shell=False,
        )
    except subprocess.TimeoutExpired:
        raise AdminError("systemctl %s %s timed out" % (action, unit))
    except OSError as exc:
        raise AdminError("cannot run systemctl (%s)" % exc)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        if "password" in err.lower() or "a terminal" in err.lower():
            raise AdminError(
                "sudo needs a password: the sudoers line is not installed yet. "
                "See surfd-admin.sudoers -- it needs a human with root."
            )
        raise AdminError("systemctl %s %s failed: %s"
                         % (action, unit, err[:200] or proc.returncode))
    return "%s %s ok" % (action, unit)


def unit_state(tier):
    """is-active for one unit, or "" when systemd does not know it."""
    systemctl_bin = shutil.which("systemctl") or "/usr/bin/systemctl"
    try:
        proc = subprocess.run(
            [systemctl_bin, "is-active", "ftesurf@%s.service" % tier],
            capture_output=True, text=True, timeout=5, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip()


def tail_file(path, lines=LOG_TAIL_LINES):
    """Last `lines` lines of a log, redacted. "" if unreadable."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > LOG_TAIL_BYTES:
                fh.seek(size - LOG_TAIL_BYTES)
                fh.readline()          # discard the partial first line
            data = fh.read()
    except OSError as exc:
        return "(cannot read %s: %s)" % (os.path.basename(path), exc)
    text = data.decode("utf-8", "replace")
    return clean_reply("\n".join(text.splitlines()[-lines:]))


# --------------------------------------------------------------------------
# The blueprint
# --------------------------------------------------------------------------

def build_blueprint(app, log, db_connect, lobby_ttl, client_identity=None):
    """Create and configure the /admin blueprint, or return None if disabled.

    `app` is configured here rather than by the caller because the cookie
    flags are part of this feature's security contract and must not be
    something a future edit to surfd.py can quietly drop.

    `client_identity` is surfd's own attribution function, injected because
    surfd imports this module and the reverse would be a cycle. It returns
    (address, attributed). It is OPTIONAL so that this module keeps working
    standalone -- test_admin.py builds the blueprint directly -- and the
    fallback is the old behaviour: the socket peer, always believed.
    """
    admin_hash = setting("SURFD_ADMIN_HASH")
    if not admin_hash:
        log.info("admin panel disabled (no SURFD_ADMIN_HASH in the environment "
                 "or in %s)", ENV_PATH)
        return None

    secret = setting("SURFD_ADMIN_SECRET")
    if not secret or len(secret) < 32:
        log.error("admin panel DISABLED: SURFD_ADMIN_SECRET is missing or "
                  "shorter than 32 characters. Run mkadminpw.py to generate "
                  "both values.")
        return None

    rcon_password = setting("SURFD_RCON_PASSWORD")
    if not rcon_password:
        log.warning("admin panel: SURFD_RCON_PASSWORD is unset -- the panel "
                    "will load, show systemd state and the directory table, "
                    "and refuse every game-server control.")

    lobbies = parse_lobbies(setting("SURFD_ADMIN_LOBBIES", DEFAULT_LOBBIES))
    if not lobbies:
        log.error("admin panel DISABLED: SURFD_ADMIN_LOBBIES parsed to nothing")
        return None

    crypt = setting("SURFD_RCON_PLAINTEXT", "0") not in ("1", "true")
    fleet = Fleet(lobbies, rcon_password, crypt=crypt)

    # THE COOKIE CONTRACT.
    #
    # Secure defaults to ON, which means the panel does not work over plain
    # HTTP. That is deliberate: this is a login, and a session cookie sent in
    # the clear is the whole credential. SURFD_ADMIN_INSECURE_COOKIE=1 exists
    # only so the panel can be exercised on the LAN before TLS is wired up,
    # and it logs a warning every boot so it cannot be left on by accident.
    insecure = setting("SURFD_ADMIN_INSECURE_COOKIE", "0") in ("1", "true")
    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_NAME="surfd_admin",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=not insecure,
        SESSION_COOKIE_PATH="/admin",
    )
    if insecure:
        log.warning("admin panel: SURFD_ADMIN_INSECURE_COOKIE is set. The "
                    "session cookie will be sent over plain HTTP. LAN testing "
                    "only -- unset this before the panel is reachable.")

    bp = Blueprint("admin", __name__, template_folder="templates",
                   url_prefix="/admin")

    # ---- session helpers ------------------------------------------------

    # ---- who is calling ---------------------------------------------------
    #
    # THE OLD COMMENT HERE WAS WRONG, AND IT SAID SO IN ADVANCE.  It read:
    # "if nginx ever fronts this, the lockout keys on the proxy and becomes
    # global rather than per-client -- which fails safe (everyone is locked
    # out) rather than unsafe (nobody is), but must be revisited on purpose."
    #
    # nginx does front this: play.nginx includes snippets/surfd-admin.conf.
    # So request.remote_addr was 127.0.0.1 for the attacker AND the operator,
    # and "everyone is locked out" is not a safe failure -- it is a DENIAL OF
    # SERVICE WITH A FIVE-REQUEST PRICE TAG.  Any stranger could spend five
    # wrong guesses and take the panel away from its owner for fifteen
    # minutes, repeatedly and indefinitely, from a machine they do not own and
    # with no password. This is the revisit.
    #
    # X-Real-IP, and only from a proxy we trust, is the same policy surfd uses
    # for the board limiter -- one definition, injected (see build_blueprint).
    # admin.nginx sets it with `proxy_set_header X-Real-IP $remote_addr` on
    # BOTH /admin and /admin/login, which OVERWRITES anything the caller sent,
    # so the value is our proxy's statement rather than the caller's.

    def identity():
        """(address, attributable). Never raises -- this gates a login page."""
        if client_identity is None:
            return (request.remote_addr or "0.0.0.0"), True
        try:
            ip, ok = client_identity()
            return (ip or "0.0.0.0"), bool(ok)
        except Exception:                              # pragma: no cover
            log.exception("client_identity() failed; treating the caller as "
                          "unattributable")
            return (request.remote_addr or "0.0.0.0"), False

    def client_ip():
        return identity()[0]

    def lockout_key():
        """The address to hold failures against, or None to hold none.

        None means "this request cannot be attributed to a caller", which
        happens when we are behind a proxy that did not set X-Real-IP. Locking
        such a key out would lock out everybody who shares it, so we decline
        to -- and say so, because it is a misconfiguration, not a policy.

        Declining costs less than it looks. /admin/login is separately capped
        at 12 requests a minute PER REAL IP by nginx (`zone=surfdlogin`, which
        is evaluated where the peer is still known), and the password is
        scrypt-hashed. What is lost is the second layer; what is kept is the
        operator's ability to log in at all.
        """
        ip, attributed = identity()
        if attributed:
            return ip
        log.warning("admin login from %s cannot be attributed to a caller "
                    "(no X-Real-IP from a SURFD_PROXIES source) -- the "
                    "lockout is DISABLED for this request. Check that the "
                    "reverse proxy sets X-Real-IP and that its address is in "
                    "SURFD_PROXIES.", ip)
        return None

    def logged_in():
        if not session.get("ok"):
            return False
        now = time.time()
        if now - session.get("seen", 0) > SESSION_IDLE_MAX:
            session.clear()
            return False
        if now - session.get("born", 0) > SESSION_ABS_MAX:
            session.clear()
            return False
        session["seen"] = now
        return True

    def csrf_token():
        tok = session.get("csrf")
        if not tok:
            tok = secrets.token_urlsafe(32)
            session["csrf"] = tok
        return tok

    def check_csrf():
        sent = request.form.get("csrf", "")
        held = session.get("csrf", "")
        if not held or not sent or not hmac.compare_digest(sent, held):
            raise AdminError("stale form -- reload the page and try again")

    # ---- routes ---------------------------------------------------------

    @bp.get("/login")
    def login_form():
        if logged_in():
            return redirect(url_for("admin.index"))
        # identity() rather than lockout_key(): this is a page render, and a
        # misconfiguration warning per page load would bury the one that
        # matters. An unattributed caller holds no lockout, hence wait 0.
        ip, attributed = identity()
        wait = lockout_remaining(ip) if attributed else 0
        return render_template("admin_login.html", csrf=csrf_token(),
                               error="", lockout=wait)

    @bp.post("/login")
    def login():
        ip = client_ip()
        key = lockout_key()                 # None == do not punish this address
        wait = lockout_remaining(key) if key else 0
        if wait:
            log.warning("admin login refused, %s is locked out for %ds", ip, wait)
            return render_template("admin_login.html", csrf=csrf_token(),
                                   error="Too many failed attempts.",
                                   lockout=wait), 429
        try:
            check_csrf()
        except AdminError as exc:
            return render_template("admin_login.html", csrf=csrf_token(),
                                   error=str(exc), lockout=0), 400

        password = request.form.get("password", "")
        if not password or not verify_password(password, admin_hash):
            locked = note_failure(key) if key else False
            log.warning("admin login FAILED from %s%s", ip,
                        " -- now locked out" if locked else "")
            return render_template(
                "admin_login.html", csrf=csrf_token(),
                error="Wrong password.",
                lockout=lockout_remaining(key) if key else 0), 401

        if key:
            note_success(key)
        # Rotate the session id on privilege change (session fixation).
        session.clear()
        session["ok"] = True
        session["born"] = time.time()
        session["seen"] = time.time()
        csrf_token()
        log.info("admin login OK from %s", ip)
        return redirect(url_for("admin.index"))

    @bp.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("admin.login_form"))

    @bp.get("/")
    def index():
        if not logged_in():
            return redirect(url_for("admin.login_form"))
        return render_template("admin.html", csrf=csrf_token(),
                               tiers=fleet.tiers(),
                               have_rcon=bool(rcon_password))

    @bp.get("/api/state")
    def state():
        """Everything the page renders, as JSON. Polled by the panel."""
        if not logged_in():
            return jsonify({"ok": False, "error": "not logged in"}), 401
        now = int(time.time())
        out = {"ok": True, "t": now, "lobbies": [], "directory": [],
               "have_rcon": bool(rcon_password)}

        force = request.args.get("force") == "1"
        for tier in fleet.tiers():
            if rcon_password:
                snap = fleet.snapshot(tier, force=force)
            else:
                snap = {"tier": tier, "port": fleet.port_for(tier), "up": False,
                        "error": "SURFD_RCON_PASSWORD is not configured",
                        "throttled": False, "map": "", "uptime": "",
                        "map_uptime": "", "players": [], "cpu": "",
                        "public": "", "lobby_maps": "", "lobby_cycle": "",
                        "hostname": ""}
            snap["unit"] = unit_state(tier)
            out["lobbies"].append(snap)

        # The directory's own view, which is what players actually see. A lobby
        # that is up on rcon but missing here is a heartbeat failure, and that
        # is exactly the split the watchdog needs to be visible.
        try:
            conn = db_connect()
            try:
                rows = conn.execute(
                    "SELECT node, map, players, maxplayers, addr, name, "
                    "last_seen FROM lobbies ORDER BY node"
                ).fetchall()
            finally:
                conn.close()
            for row in rows:
                age = now - row["last_seen"]
                out["directory"].append({
                    "node": row["node"], "map": row["map"],
                    "players": row["players"], "max": row["maxplayers"],
                    "addr": row["addr"], "name": row["name"],
                    "age": age, "live": age <= lobby_ttl,
                })
        except Exception as exc:                       # pragma: no cover
            log.exception("admin state db error: %s", exc)
            out["directory_error"] = str(exc)

        # Fold each lobby's own heartbeat row back into its card. This is the
        # cheap half of the panel and it needs no rcon at all: the servers POST
        # their map, player count and name every few seconds, so a card can
        # show live values even while rcon is throttled, blocked or wrong.
        #
        # It also stops the panel telling a lie it used to tell. "no reply
        # (server down)" was printed for three lobbies that were, at that exact
        # moment, heartbeating normally -- the rcon channel was blocked and the
        # panel had no other way to look.
        by_node = {d["node"]: d for d in out["directory"]}
        for snap in out["lobbies"]:
            beat = by_node.get("p%s" % snap["port"])
            snap["beat"] = beat
            snap["alive"] = bool(beat and beat["live"])
            if not snap.get("map") and beat:
                snap["map"] = beat["map"]
            if not snap.get("hostname") and beat:
                snap["hostname"] = beat["name"]
        return jsonify(out)

    @bp.get("/api/logs")
    def logs():
        if not logged_in():
            return jsonify({"ok": False, "error": "not logged in"}), 401
        which = request.args.get("which", "surfd")
        base = setting("SURFD_HOME", "/srv/nvme/surfd")
        server_dir = setting("SURFD_SERVER_HOME", "/srv/nvme/ftesurf-server")
        if which == "surfd":
            path = os.path.join(base, "logs", "surfd.log")
        elif which in [str(t) for t in fleet.tiers()]:
            path = os.path.join(server_dir, "server%s.log" % which)
        else:
            return jsonify({"ok": False, "error": "unknown log"}), 400
        return jsonify({"ok": True, "which": which, "text": tail_file(path)})

    # ---- controls -------------------------------------------------------

    def control(fn):
        """Wrap a control: require a session, a CSRF token and an rcon key."""
        def wrapper(*a, **kw):
            if not logged_in():
                return jsonify({"ok": False, "error": "not logged in"}), 401
            try:
                check_csrf()
                return jsonify({"ok": True, "message": fn(*a, **kw)})
            except AdminError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            except RconError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 502
        wrapper.__name__ = fn.__name__
        return wrapper

    def need_rcon():
        if not rcon_password:
            raise AdminError("SURFD_RCON_PASSWORD is not configured on this "
                             "surfd, so game-server controls are unavailable.")

    def tier_arg():
        tier = request.form.get("tier", "")
        if tier not in [str(t) for t in fleet.tiers()]:
            raise AdminError("unknown lobby %r" % (tier,))
        return tier

    @bp.post("/api/map")
    @control
    def set_map():
        need_rcon()
        tier = tier_arg()
        name = request.form.get("map", "").strip()
        if not MAPNAME.match(name):
            raise AdminError("map names are lowercase letters, digits and "
                             "underscores only")
        fleet.run(tier, ["changelevel", name], expect_reply=False)
        # The map changed, so the cached status is wrong now. Drop it rather
        # than let the card show the old map for up to STATUS_TTL; the
        # heartbeat will also correct it within a few seconds regardless.
        fleet.invalidate(tier)
        log.info("admin: lobby %s -> map %s (from %s)", tier, name, client_ip())
        return "lobby %s changing to %s" % (tier, name)

    @bp.post("/api/maps")
    @control
    def set_maps():
        need_rcon()
        tier = tier_arg()
        raw = request.form.get("maps", "").strip()
        names = raw.split()
        if len(names) > 40:
            raise AdminError("that is more than 40 maps")
        for n in names:
            if not MAPNAME.match(n):
                raise AdminError("%r is not a valid map name" % n)
        value = " ".join(names)
        # Lobby_NextMap looks up where the rotation currently IS rather than
        # keeping an index (cfg/lobby.cfg:252-258), so rewriting the list live
        # does not desync the cycle. That is why this is safe to do hot.
        fleet.run(tier, ["set", "lobby_maps", value], expect_reply=False)
        fleet.note_cvar(tier, "lobby_maps", value)
        log.info("admin: lobby %s rotation set to %r (from %s)",
                 tier, value, client_ip())
        return "lobby %s rotation updated (%d maps)" % (tier, len(names))

    @bp.post("/api/cycle")
    @control
    def set_cycle():
        need_rcon()
        tier = tier_arg()
        raw = request.form.get("cycle", "").strip()
        try:
            seconds = int(raw)
        except ValueError:
            raise AdminError("cycle must be a whole number of seconds")
        if seconds != 0 and not (60 <= seconds <= 86400):
            raise AdminError("cycle must be 0 (off) or between 60 and 86400")
        fleet.run(tier, ["set", "lobby_cycle", str(seconds)], expect_reply=False)
        fleet.note_cvar(tier, "lobby_cycle", str(seconds))
        log.info("admin: lobby %s cycle %ds (from %s)", tier, seconds, client_ip())
        return ("lobby %s rotation off" % tier if seconds == 0
                else "lobby %s cycling every %ds" % (tier, seconds))

    @bp.post("/api/hostname")
    @control
    def set_hostname():
        need_rcon()
        tier = tier_arg()
        name = request.form.get("hostname", "").strip()
        if not HOSTNAME_TEXT.match(name):
            raise AdminError("that hostname has characters that are not allowed")
        fleet.run(tier, ["set", "hostname", name], expect_reply=False)
        fleet.note_cvar(tier, "hostname", name)
        log.info("admin: lobby %s hostname %r (from %s)", tier, name, client_ip())
        return "lobby %s renamed" % tier

    @bp.post("/api/say")
    @control
    def say():
        need_rcon()
        tier = tier_arg()
        text = request.form.get("text", "").strip()
        if not SAY_TEXT.match(text):
            raise AdminError("that message has characters that are not allowed")
        fleet.run(tier, ["say", text], expect_reply=False)
        log.info("admin: lobby %s say %r (from %s)", tier, text, client_ip())
        return "sent to lobby %s" % tier

    @bp.post("/api/kick")
    @control
    def kick():
        need_rcon()
        tier = tier_arg()
        raw = request.form.get("userid", "").strip()
        try:
            userid = int(raw)
        except ValueError:
            raise AdminError("userid must be a number")
        if not 0 < userid < 10 ** 9:
            raise AdminError("userid out of range")
        reply = clean_reply(fleet.run(tier, ["kick", str(userid)]))
        log.info("admin: lobby %s kick %d (from %s)", tier, userid, client_ip())
        return reply.strip() or "kicked %d" % userid

    @bp.post("/api/unit")
    @control
    def unit():
        tier = tier_arg()
        action = request.form.get("action", "")
        result = systemctl(action, tier, fleet.tiers())
        # A restarted server is a new process with an empty DDoS table and
        # possibly a different map, so nothing we cached about it still holds.
        fleet.invalidate(tier)
        log.info("admin: %s (from %s)", result, client_ip())
        return result

    @bp.post("/api/flush")
    @control
    def flush():
        """Empty the directory table.

        Stage 10 needs this: the port renumber reuses p27510 and p27520 for
        DIFFERENT tiers, so for up to the 30s TTL surfd would hold a row whose
        node says one tier while its map and name say another, and the picker
        would draw it. The documented sequence is stopall -> flush -> edit ->
        runall, and this is the flush.
        """
        conn = db_connect()
        try:
            with conn:
                n = conn.execute("DELETE FROM lobbies").rowcount
        finally:
            conn.close()
        log.warning("admin: directory flushed, %d rows (from %s)", n, client_ip())
        return "flushed %d rows from the directory" % n

    @bp.after_request
    def harden(resp):
        # The panel is one page of first-party HTML with no external anything.
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    log.info("admin panel enabled at /admin for lobbies %s (rcon %s, "
             "cookie %s)",
             ",".join("%s:%d" % (l["tier"], l["port"]) for l in lobbies),
             "hashed" if crypt else "PLAINTEXT",
             "insecure" if insecure else "secure")
    return bp
