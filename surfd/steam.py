#!/usr/bin/env python3
"""
steam.py -- what surfd asks Steam: an OpenID sign-in and a profile.  Stdlib only.

A sign-in has THREE answers: a SteamID, Refused (a local check or Steam said
no) and Unavailable (Steam was not reached).  The third is not a refusal and
must not be shown as one.

No module state: tests reload surfd many times in one process and this module
is not reloaded with it.
"""

import calendar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPException    # `http` below is this module's own

OPENID = "https://steamcommunity.com/openid/login"
NS = "http://specs.openid.net/auth/2.0"
SUMMARIES = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
UA = "FTESurf/0.1 surfd (+https://proto.bar/ftesurf)"

# The ten fields of a Steam assertion and the seven its signature covers.  BOTH
# ARE EXACT SETS.  Every field is sent back to Steam to be checked, and a name
# Steam's parser might fold onto a real one ("openid.claimed.id") would let it
# verify one value while surfd reads another; nothing unlisted gets that far.
SIGNED = frozenset(("signed", "op_endpoint", "claimed_id", "identity",
                    "return_to", "response_nonce", "assoc_handle"))
FIELDS = frozenset("openid." + n for n in SIGNED | {"ns", "mode", "sig"})
# s either side of now a response_nonce may be dated.  It is also how long a
# reply that never reached surfd stays usable by whoever holds its address.
NONCE_SKEW = 120
MAX_VALUE = 512
# The board's nginx gives surfd 5 s (proxy_read_timeout) and a sign-in makes
# both calls.  These bound each socket wait, not the whole exchange.
CONFIRM_TIMEOUT = 2.5
PROFILE_TIMEOUT = 1.5
HTTP_LIMIT = 65536

# fullmatch, never match-with-$: `$` also matches before a trailing newline.
_CLAIMED = re.compile(r"https://steamcommunity\.com/openid/id/([0-9]{17})")
_NONCE = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
                    r"[\x21-\x7e]{1,64}")
_TOKEN = re.compile(r"[\x21-\x7e]{1,%d}" % MAX_VALUE)
_AVATAR = re.compile(r"[0-9a-f]{40}")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


class Refused(Exception):
    """The sign-in is not valid.  str() is a short reason for the log."""


class Unavailable(Exception):
    """Steam could not be asked.  Never carries a URL: one of them holds a key."""


def is_steamid64(s):
    """An individual account's SteamID64 (momindex.is_steamid64's test)."""
    if not isinstance(s, str) or not s.isdigit() or len(s) != 17:
        return False
    return (int(s) >> 32) == 0x01100001


def login_url(realm, return_to):
    return OPENID + "?" + urllib.parse.urlencode({
        "openid.ns": NS,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": NS + "/identifier_select",
        "openid.claimed_id": NS + "/identifier_select",
    })


def precheck(args, return_to, now):
    """Everything that can be decided without asking Steam.

    `args` maps each openid.* name to its ONE value (the caller refuses a
    repeated name).  Returns (steamid, response_nonce); raises Refused.
    """
    if args.get("openid.mode") == "cancel":
        raise Refused("cancelled")
    if set(args) != FIELDS:
        raise Refused("not Steam's fields")
    for v in args.values():
        if not _TOKEN.fullmatch(v or ""):
            raise Refused("malformed field")
    if args["openid.mode"] != "id_res":
        raise Refused("not an assertion")
    if args["openid.ns"] != NS:
        raise Refused("wrong namespace")
    if args["openid.op_endpoint"] != OPENID:
        raise Refused("wrong endpoint")
    if args["openid.return_to"] != return_to:
        raise Refused("wrong return_to")
    claimed = args["openid.claimed_id"]
    if claimed != args["openid.identity"]:
        raise Refused("claimed_id is not identity")
    m = _CLAIMED.fullmatch(claimed)
    if not m or not is_steamid64(m.group(1)):
        raise Refused("not a steam id")
    signed = args["openid.signed"].split(",")
    if len(signed) != len(SIGNED) or set(signed) != SIGNED:
        raise Refused("not Steam's signed list")
    nonce = args["openid.response_nonce"]
    m2 = _NONCE.fullmatch(nonce)
    if not m2:
        raise Refused("malformed nonce")
    try:
        at = calendar.timegm(time.strptime(m2.group(1), "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        raise Refused("malformed nonce")
    if abs(now - at) > NONCE_SKEW:
        raise Refused("stale nonce")
    return m.group(1), nonce


def confirm(args, http):
    """Ask Steam whether it made this assertion.  Returns None, or raises."""
    form = dict(args)
    form["openid.mode"] = "check_authentication"
    body = http(OPENID, urllib.parse.urlencode(form).encode("ascii"),
                timeout=CONFIRM_TIMEOUT)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise Unavailable("undecodable reply")
    verdicts = [line[9:] for line in text.split("\n") if line.startswith("is_valid:")]
    if len(verdicts) != 1:          # none, or two that might disagree
        raise Unavailable("reply without one verdict")
    if verdicts[0] != "true":
        raise Refused("steam says invalid")


def summaries(key, steamids, http):
    """{steamid: {"name", "avatar"}} for the ids Steam knows.  Raises Unavailable."""
    want = [s for s in steamids if is_steamid64(s)][:100]
    if not key or not want:
        return {}
    body = http(SUMMARIES + "?" + urllib.parse.urlencode(
        {"key": key, "steamids": ",".join(want)}), timeout=PROFILE_TIMEOUT)
    try:
        players = json.loads(body.decode("utf-8"))["response"]["players"]
    except (ValueError, KeyError, TypeError, RecursionError):
        raise Unavailable("unreadable profile reply")
    out = {}
    if not isinstance(players, list):
        raise Unavailable("unreadable profile reply")
    for p in players:
        if not isinstance(p, dict) or p.get("steamid") not in want:
            continue
        name = p.get("personaname")
        avatar = p.get("avatarhash")
        if isinstance(name, str):
            # A lone surrogate (JSON can spell one) cannot be stored or encoded.
            name = name.encode("utf-8", "replace").decode("utf-8")
            name = _CTRL.sub("", name).strip()[:64]
        else:
            name = ""
        out[p["steamid"]] = {
            "name": name,
            "avatar": avatar if isinstance(avatar, str) and _AVATAR.fullmatch(avatar) else "",
        }
    return out


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):
        return None


def http(url, data=None, timeout=CONFIRM_TIMEOUT):
    """GET, or POST when `data` is given.  The body, or Unavailable."""
    opener = urllib.request.build_opener(
        _NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    try:
        with opener.open(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise Unavailable("status %d" % resp.status)
            body = resp.read(HTTP_LIMIT + 1)
    except urllib.error.HTTPError as exc:
        raise Unavailable("status %d" % exc.code)
    except (OSError, ValueError, HTTPException) as exc:
        # URLError, timeouts and TLS are OSError; a cut-short or malformed
        # reply is http.client's.  The type's name only: str(exc) can hold a URL.
        raise Unavailable(type(exc).__name__)
    if len(body) > HTTP_LIMIT:
        raise Unavailable("oversized reply")
    return body
