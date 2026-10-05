"""Import Counter-Strike: Source times from the ksf.surf timer network.

  python surfd/ksfimport.py --seed <file of steamid64s> [--go] [--max N]
  python surfd/ksfimport.py --from-maps [<file of map names>] [--depth N]
                            [--modes 0,1,2,3] [--max <requests>] [--delay <s>] [--go]
  python surfd/ksfimport.py --watch [--max <requests>] [--delay <s>] --go   (cron)

TIMES ONLY, AND THAT IS A LIMIT OF THE SOURCE RATHER THAN A CHOICE.  KSF
publishes no replay this project can USE: no Source .dem parser exists anywhere
in this tree or in the wrlines reference, and nothing could turn one into a .rec.
So a KSF row carries no recording, no line and no `watch` -- replay_id stays 0
and nothing pretends otherwise.
  CORRECTED 2026-09-29: this used to give as its first reason that "there is no
  demo URL in any endpoint found", and that is false.
  `/api/players/{id}/replays/{map}?game=css&mode=0` answers 200 with a per-zone
  list carrying `recordId`, `time` and a `file` like
  "replay_css_6201_0_712551_1790101734.rec".  Those are FILENAMES; no download
  path has been located or tested, so "reachable" is unproven, and it is a shavit
  .rec unrelated to this project's format.  The conclusion stands and one of its
  reasons was wrong, which is worth more than the conclusion being right.

TWO WAYS IN.  PLAYER-SEEDED (--seed/--from-boards): a player's best records,
main track only, 25 each.  MAP-SEEDED (--from-maps): every board of a map, paged:

    GET /api/maps/search/<name>   up to 5 map rows: isLinear, cp_count, b_count
    GET /api/maps/<map>/records/zone/<zone>/<startRank>?game=css&mode=0
                                  a list of at most KSF_PAGE rows

  * `mode` is KSF's surf style: 0 Forward (our `clean`), 1 Sideways, 2
    Half-Sideways, 3 Backwards (surfd.STYLES_KSF).  Their site also has a
    `game=css100t` board; it is a different tick rate and is not imported.
  * zone 0 is the main track, 1..cp_count the stages, 30+n bonus n.  ON A LINEAR
    MAP cp_count COUNTS CHECKPOINTS, which have no board (surf_utopia_njv:
    isLinear true, cp_count 4), so stages are asked for only when isLinear is
    false -- not when it is missing.
  * the search is a typeahead: `surf_utopia` answers `surf_utopia_njv`, another
    map.  Only an exact name match is used.
  * startRank is 1-based and arbitrary; past the end answers [].  No reply carries
    a total, so a board ends at the first page shorter than KSF_PAGE, and the
    cached row count is the cursor.
  * a row carries rank, name, steamID (STEAM_0:Y:Z), time, date and record_id.
  Three claims made here on 2026-09-29 (no API route, 10 rows and no paging,
  stages unreachable) were measured false the same day: the board is fetched by
  the browser on /maps/<map>/records, a page the earlier searches never opened.

POLITENESS, and the rules are the wrlines reference's because its author
reasoned them out against this same host:
  * one request at a time, never concurrent
  * KSF_DELAY_MS between them, always (WATCH_DELAY unattended)
  * a cap per invocation, so one command cannot become a thousand requests
  * a User-Agent that says what this is and where to complain
  * a non-2xx is reported AS A REFUSAL and nothing is retried.  If ksf.surf does
    not want automated requests the answer is to stop, not to look more like a
    browser.  Unattended, a refusal also parks every later run (COOLDOWN).
Every answer is cached on disk, so a re-run costs nothing and the second import
of the same seed list makes no requests at all.

AUTOMATIC SINCE 5 OCT 2026, BY LEX'S DECISION.  This said "never automatic:
every run of this is a person typing it" until Lex asked for the record list to
fill slowly by itself.  --watch is that: on the Pi's crontab, a few requests a
tick, the next unseen page of each board shallowest first, maps somebody is
looking at first (mapwant).  ksf.surf's robots.txt (checked 5 Oct) carries only
Cloudflare's content-signal preamble and no Disallow.
  * every request is counted against the run's cap in one place (Pacer.get)
  * one ksfimport at a time per cache (take_lock), by hand or by cron
  * a fetched board is OWED until its rows are on the board table (owed/), so
    a run killed between the two is filed whole by the next tick
  * a board refused STRIKES times is set aside, not the whole crawl with it
  * an empty map library fetches and files nothing: it used to mean "no filter"
  * WHAT IT SEES LATE: a player who enters a board between our first page and
    our cursor waits for a re-walk, which an idle crawl gives its stalest board
    every REWALK_DAYS; page-1 refreshes catch new records sooner, the cursor
    the tail.  Nothing purges a run deleted upstream.

A KSF ROW'S BUILD IS NOT CHECKED, AND "EVER" WAS TOO STRONG.  This paragraph
said CANNOT BE CHECKED, EVER until 2026-09-29, when `/api/files/<map>.zip`
answered `{"exists":true}` and the map page was found to render a
`/files/<map>.zip` link when it does.  A published archive is a hashable archive,
so the claim is falsifiable and the honest version is the one below: nothing here
checks it, and until something downloads and hashes one, a `ksf` row means the
build is unverified.  Neither download nor hash has been attempted.  A Momentum run is verified
exactly: its demo carries the map's SHA1, so tools/momimport.py drops the 12.5%
that name a build this install does not have.  Nothing on the CS:S side
publishes a per-map digest, and the 322 map names that differ between the two
installs are ALL plain-named -- which is precisely where these records live.
So `momentum` on the board means "same build, checked" and `ksf` means "build
unknown and unknowable".  Those are different claims wearing the same shape, and
the asymmetry belongs in front of whoever reads the board rather than averaged
away.

A KSF TIME IS A THIRD MEASUREMENT, not a variant of the second.  It was set on
CS:S physics under KSF's own zones, and their `mapName` is the PLAIN name --
`surf_whiteout`, not `surf_whiteout_ksf` -- so a name that matches ours does not
mean the same build, the same start, or the same end.  That is why it lands in
its own tier and is never merged into ranked, and why rows for maps this install
cannot even load are dropped rather than stored against a name nobody can open.
"""
import argparse
import heapq
import http.client
import io
import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Importing surfd logs "surfd ready" to surfd.log, which reads as a restart on
# every tick (sweep.py's fix): a handler on its logger first keeps it quiet.
if not logging.getLogger("surfd").handlers:
    _quiet = logging.StreamHandler(sys.stderr)
    _quiet.setLevel(logging.WARNING)
    logging.getLogger("surfd").addHandler(_quiet)

import surfd as S       # noqa: E402  -- import-safe: app.run is __main__-guarded

# Player aliases are free Unicode from another game's API, and Windows'
# default stdout is cp1252 -- so merely PRINTING a name can kill the tool
# after the work is done.  This has now bitten once on a file write and once
# on a progress line; "replace" rather than "strict" because a mangled glyph
# in a console line is not worth losing a sweep over.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KSF_BASE = "https://ksf.surf"
KSF_DELAY_MS = 400         # wrlines' WR_API_DELAY_MS, same host, same reasoning
KSF_TAKE = 25              # their own cap on bestrecords
KSF_MAX_DEFAULT = 50       # players per invocation unless --max says otherwise

# Consecutive "that id is not mine" answers before the sweep stops.  The reading
# that a 500 means an unknown player is INFERRED, so this is the circuit breaker
# on being wrong about it: a host genuinely refusing answers 500 to everything
# and trips this within seconds, where the measured yield (a third of ids
# unknown, scattered) never produces a run this long.
SKIP_STREAK = 25
KSF_TIMEOUT = 30
UA = "FTESurf/0.1 ksfimport (+https://proto.bar/ftesurf)"

# CS:S surf runs at 66.67 ticks a second.  The TIME is the fact here -- KSF
# reports seconds and its timer counted them -- so millis is taken from that and
# `ticks` is DERIVED for the schema's sake rather than counted.  Anything that
# needs a tick count off a KSF row is reading a number nobody measured.
KSF_TICK = 0.015

KSF_PAGE = 20              # rows in a records page; a shorter one ends the board
KSF_STAGES = 30            # zones 1..30 are stages; 30+n is bonus n
KSF_DEPTH_DEFAULT = 100    # rows per board for --from-maps; -1 is the whole board
KSF_REQ_DEFAULT = 300      # requests per --from-maps invocation

# KSF's `mode` -> the board style its rows are filed under.
KSF_MODES = {0: S.STYLE_CLEAN, 1: S.STYLE_SW, 2: S.STYLE_HSW, 3: S.STYLE_BW}
KSF_LIST_PAGE = 10         # maps per /api/maps/new page (measured 5 Oct)

# --watch, the unattended crawl.  10 requests every 5 minutes is ~2,900 a day.
WATCH_MAX = 10
WATCH_DELAY = 3.0          # s between requests
COOLDOWN = 6 * 3600        # s parked after a refusal, doubling to COOLDOWN_MAX
COOLDOWN_MAX = 48 * 3600
CATALOG_DAYS = 7           # re-list KSF's maps this often
REFRESH_DAYS = 14          # re-ask a board's first page this often
WANT_DAYS = 14             # a map viewed this recently is crawled first
STRIKES = 3                # parks on one board before it is set aside
SKIP_DAYS = 30             # how long a board stays set aside
REWALK_DAYS = 60           # an idle crawl walks its stalest board again this often
CATALOG_DRY = 3            # list pages in a row with no new map that end a full pass
CATALOG_FULL_DAYS = 30     # a full list pass this often; between, new maps only
CATALOG_MAX = 5000         # an offset past this ends a pass whatever the host says
OWED_MAX = 200             # boards fetched and not filed before a tick only files
RECOVER_ROWS = 5000        # rows of owed boards one tick files
WRITE_CHUNK = 500          # rows a transaction


def steam64(raw):
    """Accept 7656119..., STEAM_0:Y:Z or [U:1:N]; return the 64-bit id or None."""
    s = raw.strip()
    if s.isdigit() and len(s) == 17 and (int(s) >> 32) == 0x01100001:
        return int(s)
    if s.upper().startswith("STEAM_"):
        try:
            _, y, z = s.split(":")
            return 76561197960265728 + int(z) * 2 + int(y)
        except (ValueError, IndexError):
            return None
    return None


def seed_from_boards(board_dir, limit):
    """SteamID64 -> alias, taken from Momentum's boards, most-seen first.

    KSF serves no map leaderboard, so the only way in is one player at a time --
    and the players worth asking about are the ones who actually surf.  The
    Momentum sweep already collected thousands of them with their aliases, so
    the seed costs no requests of its own.

    RANKED BY APPEARANCE COUNT, not by rank: somebody on forty boards is a
    surfer, and somebody on one might be a single lucky run.  Measured yield on
    the twelve most-seen: four had records, four had none, four were not KSF
    players at all.
    """
    import collections
    import glob
    seen = collections.Counter()
    alias = {}
    for p in glob.glob(os.path.join(board_dir, "*.json")):
        try:
            with io.open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        for r in (doc.get("rows") or []):
            sid = r.get("steamid") or ""
            if not sid.isdigit():
                continue
            seen[sid] += 1
            alias.setdefault(sid, S.clean_text(r.get("alias") or "") or sid)
    # int keys, matching read_seed: the two feed the same loop, and a str here
    # reaches the cache path's %d and dies three frames later.
    out = {}
    for sid, _ in seen.most_common():
        n = steam64(sid)
        if n is not None:
            out[n] = alias[sid]
        if len(out) >= limit:
            break
    return out


def read_seed(path):
    """steamid64 -> display name.  `<id>` or `<id> <name...>`, # comments."""
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.split("#", 1)[0].strip()
            if not ln:
                continue
            bits = ln.split(None, 1)
            sid = steam64(bits[0])
            if sid is None:
                continue
            out[sid] = S.clean_text(bits[1]) if len(bits) > 1 else str(sid)
    return out


class Refused(Exception):
    """ksf.surf said no to US.  Reported, never retried, stops the run.
    `code` is the HTTP status when there was one; `board` marks a reply only
    that board's request got (a page that would not parse as one)."""

    def __init__(self, msg, code=0, board=False):
        Exception.__init__(self, msg)
        self.code, self.board = code, board


class OverBudget(Exception):
    """This run's request cap is spent, so the request is not made."""


class NoSuchPlayer(Exception):
    """ksf.surf cannot answer for that id -- which is an ANSWER, not a refusal.

    THE THIRD VERDICT, and it had to exist before a sweep could.  Probing twelve
    SteamID64s taken off Momentum's boards returned five records for four of
    them, an empty list for four, and **HTTP 500 for the other four**.  A 500
    here is how this host says "that id is not a player of mine": the same code
    comes back for a numeric player_id used in the SteamID slot.  That is
    inferred from behaviour rather than documented, so it is named and bounded
    rather than assumed -- see SKIP_STREAK.

    Collapsing it into Refused would end a sweep at its first non-KSF player,
    which on that sample is one id in three.  Collapsing it into "no records"
    would claim the host answered when it did not.
    """


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=KSF_TIMEOUT) as r:
            if r.status < 200 or r.status >= 300:
                raise Refused("HTTP %d" % r.status, r.status)
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # 500 is this host's answer for an id it does not know; anything else
        # (403, 429, 503) is about US and stops the run.  If that reading is
        # ever wrong the breaker below catches it: a host that is actually
        # refusing returns 500 to everything, and SKIP_STREAK in a row stops.
        if e.code == 500:
            raise NoSuchPlayer("HTTP 500")
        raise Refused("HTTP %d" % e.code, e.code)
    except urllib.error.URLError as e:
        raise Refused(str(e.reason))
    # No answer at all: a read past KSF_TIMEOUT, a connection dropped mid-reply.
    # Not a refusal, but stopped like one -- 2026-10-03's run died here with a
    # traceback after 171 map lookups.
    except (OSError, http.client.HTTPException) as e:
        raise Refused("no answer: %s" % (str(e) or type(e).__name__))


def records(sid, cache_dir, paced):
    """One player's best records, from cache or from the host."""
    cf = os.path.join(cache_dir, "%d.json" % sid)
    if os.path.exists(cf):
        with io.open(cf, encoding="utf-8") as fh:
            return json.load(fh), False
    if paced:
        time.sleep(KSF_DELAY_MS / 1000.0)
    body = fetch("%s/api/players/%d/bestrecords/%d?game=css&mode=0"
                 % (KSF_BASE, sid, KSF_TAKE))
    try:
        doc = json.loads(body)
    except ValueError:
        raise Refused("ksf.surf's reply did not parse -- their format has "
                      "probably changed")
    os.makedirs(cache_dir, exist_ok=True)
    with io.open(cf, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc))
    return doc, True


def zone_track_leg(zone):
    """KSF zone -> our (track, leg), the shape momboards.track_leg gives."""
    if zone == 0:
        return 0, 0
    if zone <= KSF_STAGES:
        return 0, zone
    return zone - KSF_STAGES, 0


def zones_of(info):
    """Main, the stages of a staged map, then the bonuses."""
    stages = int(info.get("cp_count") or 0) if info.get("isLinear") is False else 0
    bonuses = int(info.get("b_count") or 0)
    return ([0] + list(range(1, min(stages, KSF_STAGES) + 1))
            + [KSF_STAGES + n for n in range(1, bonuses + 1)])


class Pacer:
    """One request at a time, `delay` seconds apart, at most `budget` of them.
    The cap is checked here, the one place a request is made."""

    def __init__(self, delay, budget):
        self.delay, self.budget, self.made = delay, budget, 0
        self.what = None            # the board key the last request was for

    def left(self):
        return self.budget - self.made

    def get(self, path, what=None):
        if self.left() <= 0:
            raise OverBudget(path)
        if self.made:
            time.sleep(self.delay)
        self.made += 1
        self.what = what
        try:
            body = fetch(KSF_BASE + path)
        except NoSuchPlayer as e:
            # "not a player of mine" is the PLAYER route's dialect; here a 500 is
            # just a refusal.
            raise Refused(str(e), 500)
        try:
            return json.loads(body)
        except ValueError:
            raise Refused("ksf.surf's reply did not parse -- their format has "
                          "probably changed")


def _load(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _save(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc))
    os.replace(tmp, path)


def map_info(mp, cache, pacer):
    """KSF's row for exactly `mp`, or None when KSF has no map by that name.
    Raises OverBudget when it would have to ask and may not."""
    cf = os.path.join(cache, "maps", mp + ".json")
    doc = _load(cf)
    if not isinstance(doc, list):
        doc = pacer.get("/api/maps/search/" + urllib.parse.quote(mp))
        doc = doc if isinstance(doc, list) else []      # "none", asked once
        _save(cf, doc)
    for row in doc:
        if isinstance(row, dict) and str(row.get("name") or "").lower() == mp:
            return row
    return None


def board_path(cache, mp, zone, mode=0):
    # Forward keeps the name it had before modes existed, so that cache is reused.
    leaf = ("z%d.json" % zone) if mode == 0 else ("z%dm%d.json" % (zone, mode))
    return os.path.join(cache, "boards", mp, leaf)


def board_load(cache, mp, zone, mode=0):
    doc = _load(board_path(cache, mp, zone, mode))
    if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
        doc = {"rows": [], "done": False}
    return doc


def _next(doc):
    """The rank the board's next page starts at.  A cache from before 5 Oct has
    no `next`: it appended whole pages, so its row count was the cursor."""
    n = doc.get("next")
    return n if isinstance(n, int) and n >= 1 else len(doc["rows"]) + 1


def merge_page(doc, page):
    """Fold a page into a board by player, keeping each player's fastest row.

    Ranks move while a board is paged -- a new record pushes everyone below it
    down one -- so a page can repeat a player already held, and appending would
    hold them twice.  Returns how many players were new."""
    held = {}
    for i, r in enumerate(doc["rows"]):
        held.setdefault(str(r.get("steamID")), i)
    new = 0
    for r in page:
        k = str(r.get("steamID"))
        i = held.get(k)
        if i is None:
            held[k] = len(doc["rows"])
            doc["rows"].append(r)
            new += 1
        elif _secs(r) < _secs(doc["rows"][i]):
            doc["rows"][i] = r
    return new


def _secs(rec):
    t = rec.get("time")
    return t if isinstance(t, (int, float)) and t > 0 else float("inf")


def _ikey(mp, zone, mode):
    return "%s|%d|%d" % (mp, zone, mode)


def _state(doc):
    """[ranks paged, done, first page's fetch time, set aside, walked to its end at]."""
    skip = (bool(doc.get("skip"))
            and time.time() - int(doc.get("skip_at") or 0) < SKIP_DAYS * 86400)
    return [_next(doc) - 1, bool(doc.get("done")), int(doc.get("top") or 0), skip,
            int(doc.get("walked") or 0)]


def board_state(cache, idx, mp, zone, mode):
    """[ranks paged, done, first page's fetch time, skipped] -- from `idx` when
    it has the board, so a cron tick need not parse every board it might page
    (a deep board is megabytes of JSON, and the Pi has ~1 GB free).  A stale
    entry costs order and at most one wasted request; the board file is what
    board_page reads its cursor from."""
    if idx is not None:
        v = idx.get(_ikey(mp, zone, mode))
        if isinstance(v, list) and len(v) == 5:
            return v
    v = _state(board_load(cache, mp, zone, mode))
    if idx is not None:
        idx[_ikey(mp, zone, mode)] = v
    return v


# A board fetched into the cache and not yet filed on the board table.  The
# marker is made BEFORE the request and removed only after the rows are
# written, so a run that dies anywhere between -- killed, a full disk, a locked
# database -- leaves it for the next --watch tick to file whole.
def _owed_path(cache, mp, zone, mode):
    return os.path.join(cache, "owed", "%s@%d@%d" % (mp, zone, mode))


def mark_owed(cache, mp, zone, mode):
    p = _owed_path(cache, mp, zone, mode)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "a").close()


def owed_boards(cache):
    try:
        names = sorted(os.listdir(os.path.join(cache, "owed")))
    except OSError:
        return []
    out = []
    for f in names:
        b = f.split("@")
        if len(b) == 3 and S.clean_map(b[0]) == b[0] and b[1].isdigit() and b[2].isdigit():
            out.append((b[0], int(b[1]), int(b[2])))
    return out


def clear_owed(cache, boards):
    for mp, z, m in boards:
        try:
            os.remove(_owed_path(cache, mp, z, m))
        except FileNotFoundError:
            pass


def board_page(cache, mp, zone, pacer, mode=0, top=False, idx=None):
    """Fetch one board's next page -- or with `top` its first page again -- and
    fold it into the cache.  Returns (doc, that page's rows)."""
    doc = board_load(cache, mp, zone, mode)
    start = 1 if top else _next(doc)
    mark_owed(cache, mp, zone, mode)
    page = pacer.get("/api/maps/%s/records/zone/%d/%d?game=css&mode=%d"
                     % (urllib.parse.quote(mp), zone, start, mode),
                     _ikey(mp, zone, mode))
    if not isinstance(page, list):
        raise Refused("a records page was not a list -- their format has "
                      "probably changed", board=True)
    page = [r for r in page if isinstance(r, dict)]
    if page and not any(steam64(str(r.get("steamID") or "")) for r in page):
        raise Refused("a records page carried no SteamID -- their format has "
                      "probably changed", board=True)
    # A host answering a start past the end with the last full page would never
    # let the board end; their ranks say which page it really is.
    ranks = [r["rank"] for r in page if type(r.get("rank")) is int]
    if not top and ranks and max(ranks) < start:
        page = []
    new = merge_page(doc, page)
    now = int(time.time())
    if start == 1:
        doc["top"] = now
    if not top:
        # The cursor is a RANK and moves by the page, never by the players new
        # to us: counting held players stalled a board whose ranks shifted
        # under it (review, 5 Oct: 60 of 60 requests to one URL).
        doc["next"] = start + len(page)
        doc["done"] = len(page) < KSF_PAGE
        if doc["done"]:
            doc["walked"] = now
    else:
        doc["next"] = max(_next(doc), 1 + len(page))
        if len(page) < KSF_PAGE:
            doc["done"] = True           # page 1 was the whole board
        elif new:
            doc["done"] = False          # new players on top: the tail moved too
    doc.pop("skip", None)
    doc.pop("skip_at", None)
    _save(board_path(cache, mp, zone, mode), doc)
    if idx is not None:
        idx[_ikey(mp, zone, mode)] = _state(doc)
    return doc, page


def wants_more(state, depth):
    n, done, skip = state[0], state[1], state[3] if len(state) > 3 else False
    return not done and not skip and (depth < 0 or n < depth)


def rewalk_step(cache, idx, maps, now):
    """Send the board walked to its end longest ago back to rank 1, at most one
    a tick and only from an idle crawl: players who entered between our first
    page and our cursor are fetched by nothing else."""
    best = None
    for key, v in idx.items():
        if not isinstance(v, list) or len(v) != 5:
            continue
        n, done, top, skip, walked = v
        mp, z, m = key.split("|")
        if (mp in maps and done and not skip and n >= KSF_PAGE
                and walked < now - REWALK_DAYS * 86400
                and (best is None or walked < best[0])):
            best = (walked, mp, int(z), int(m))
    if best is None:
        return None
    _, mp, z, m = best
    doc = board_load(cache, mp, z, m)
    doc["next"], doc["done"] = 1, False
    _save(board_path(cache, mp, z, m), doc)
    idx[_ikey(mp, z, m)] = _state(doc)
    return _ikey(mp, z, m)


def sweep_maps(maps, cache, depth, pacer, modes=(0,), prio=(), fetched=None,
               idx=None):
    """Look the maps up, then fetch pages shallowest first until the budget or
    the work runs out -- so an interrupted sweep leaves every board equally deep.

    Boards of `prio` maps go first.  A style other than Forward is asked for its
    stages and bonuses only once its main board has a row: most maps have no
    Sideways times at all.  Each page fetched is appended to `fetched` as
    (map, zone, mode, rows).

    Returns ({map: info}, maps KSF does not have, boards still wanting pages)."""
    infos, absent = {}, 0
    for mp in maps:
        try:
            info = map_info(mp, cache, pacer)
        except OverBudget:
            continue                    # not looked up yet: a later run asks
        if info is None:
            absent += 1
        else:
            infos[mp] = info
    prio = set(prio)
    heap = []

    def push(mp, z, m):
        st = board_state(cache, idx, mp, z, m)
        if wants_more(st, depth):
            heapq.heappush(heap, (0 if mp in prio else 1, st[0], mp, z, m))

    for mp, info in infos.items():
        zones = zones_of(info)
        for m in modes:
            for z in (zones if m == 0 or board_state(cache, idx, mp, 0, m)[0]
                      else zones[:1]):
                push(mp, z, m)
    while heap and pacer.left() > 0:
        _, n, mp, z, m = heapq.heappop(heap)
        d, page = board_page(cache, mp, z, pacer, m, idx=idx)
        if fetched is not None:
            fetched.append((mp, z, m, page))
        if wants_more(_state(d), depth):
            push(mp, z, m)
        if m and z == 0 and not n and d["rows"]:
            for z2 in zones_of(infos[mp])[1:]:
                push(mp, z2, m)
    return infos, absent, len(heap)


def _when(rec):
    try:
        return int(rec.get("date") or 0)
    except (TypeError, ValueError):
        return 0


def rec_row(mp, zone, mode, rec):
    """One KSF record as a run row, or None when it is unusable.  Never raises:
    one bad field must cost its row, not the tick."""
    sid = steam64(str(rec.get("steamID") or ""))
    t = rec.get("time")
    if (sid is None or isinstance(t, bool) or not isinstance(t, (int, float))
            or not 0 < t < 1e6):
        return None
    track, leg = zone_track_leg(zone)
    ms = int(round(t * 1000.0))
    return {"map": mp, "track": track, "leg": leg, "style": KSF_MODES[mode],
            "player": str(sid),
            "name": S.clean_text(str(rec.get("name") or "")) or str(sid),
            "millis": ms, "ticks": int(round(ms / 1000.0 / KSF_TICK)),
            "rate": 1.0 / KSF_TICK, "when": _when(rec)}


def board_rows(cache, mp, zone, mode):
    return [r for r in (rec_row(mp, zone, mode, x)
                        for x in board_load(cache, mp, zone, mode)["rows"]) if r]


def map_rows(cache, infos, modes=(0,)):
    """Every cached board row as a run row, plus the count unusable, plus the
    boards they come from."""
    rows, bad, boards = [], 0, []
    for mp in sorted(infos):
        for m in modes:
            for z in zones_of(infos[mp]):
                held = board_load(cache, mp, z, m)["rows"]
                if held:
                    boards.append((mp, z, m))
                for rec in held:
                    r = rec_row(mp, z, m, rec)
                    if r is None:
                        bad += 1
                    else:
                        rows.append(r)
    return rows, bad, boards


def catalog_step(cache, pacer, now):
    """Page KSF's whole map list into the map cache, again every CATALOG_DAYS.

    /api/maps/new is their "new maps" list, newest first, KSF_LIST_PAGE a page
    by `offset`, each row the shape the search answers -- ~100 requests list
    every map, where a search per installed map would be 1,800.  A pass ends at
    a short page or at a page with no map it has not listed: a re-list stops
    after the new maps, and an offset the host ignores cannot loop."""
    cf = os.path.join(cache, "catalog.json")
    cat = _load(cf)
    if not isinstance(cat, dict) or not isinstance(cat.get("names"), list):
        cat = {"names": [], "offset": 0, "done": False, "at": 0}
    if cat["done"] and now - int(cat.get("at") or 0) < CATALOG_DAYS * 86400:
        return cat
    if cat["done"]:
        full = now - int(cat.get("full_at") or 0) >= CATALOG_FULL_DAYS * 86400
        cat.update(offset=0, done=False, dry=0, full=full)
    seen = set(cat["names"])
    while pacer.left() > 0 and not cat["done"]:
        page = pacer.get("/api/maps/new?offset=%d" % cat["offset"])
        if not isinstance(page, list):
            raise Refused("the map list was not a list -- their format has "
                          "probably changed")
        fresh = 0
        for row in page:
            mp = S.clean_map(str(row.get("name") or "")) if isinstance(row, dict) else None
            if mp is None:
                continue
            _save(os.path.join(cache, "maps", mp + ".json"), [row])
            if mp not in seen:
                seen.add(mp)
                cat["names"].append(mp)
                fresh += 1
        cat["offset"] += len(page)
        cat["dry"] = 0 if fresh else int(cat.get("dry") or 0) + 1
        full = cat.get("full", True)
        if (len(page) < KSF_LIST_PAGE or cat["offset"] >= CATALOG_MAX
                or cat["dry"] >= (CATALOG_DRY if full else 1)):
            cat["done"], cat["at"] = True, now
            if full:
                cat["full_at"] = now
        _save(cf, cat)
    return cat


def wanted_maps(now):
    """Maps somebody looked at within WANT_DAYS (surfd's mapwant table)."""
    try:
        conn = S.connect()
        try:
            return {r[0].lower() for r in conn.execute(
                "SELECT map FROM mapwant WHERE last >= ?",
                (now - WANT_DAYS * 86400,))}
        finally:
            conn.close()
    except Exception as e:      # an empty queue costs order, not the tick
        print("  mapwant unreadable (%s): no map goes first" % e)
        return set()


def refresh_step(cache, idx, maps, prio, pacer, budget, now, fetched):
    """Re-ask the first page of boards not asked for REFRESH_DAYS -- wanted
    maps first, then the fullest -- within `budget` requests."""
    cut = now - REFRESH_DAYS * 86400
    cands = []
    for key, v in idx.items():
        if not isinstance(v, list) or len(v) != 5:
            continue
        n, done, top, skip, _walked = v
        mp, z, m = key.split("|")
        if mp in maps and not skip and (n or done) and top < cut:
            cands.append((0 if mp in prio else 1, -n, top, mp, int(z), int(m)))
    cands.sort()
    for _, _, _, mp, z, m in cands[:budget]:
        if pacer.left() <= 0:
            break
        _, page = board_page(cache, mp, z, pacer, m, top=True, idx=idx)
        fetched.append((mp, z, m, page))
    return min(budget, len(cands))


def strike(cache, idx, key, why):
    """A board this host keeps refusing is set aside after STRIKES parks rather
    than parking the whole crawl behind it for good."""
    sf = os.path.join(cache, "strikes.json")
    st = _load(sf)
    st = st if isinstance(st, dict) else {}
    st[key] = int(st.get(key) or 0) + 1
    if st[key] >= STRIKES:
        mp, z, m = key.split("|")
        doc = board_load(cache, mp, int(z), int(m))
        doc["skip"], doc["skip_at"] = why, int(time.time())
        _save(board_path(cache, mp, int(z), int(m)), doc)
        idx[key] = _state(doc)
        del st[key]
        print("  %s refused %d times: set aside (%s)" % (key, STRIKES, why))
    _save(sf, st)


def watch_mode(args, have, cache):
    """--watch: one unattended tick.  Returns (rows, the boards they file)."""
    now = int(time.time())
    pf = os.path.join(cache, ".refused")
    park = _load(pf)
    park = park if isinstance(park, dict) else {}
    ixf = os.path.join(cache, "index.json")
    idx = _load(ixf)
    idx = idx if isinstance(idx, dict) else {}
    owed = owed_boards(cache)
    pacer = Pacer(args.delay, args.max)
    fetched, refreshed, left, prio, maps = [], 0, 0, set(), set()
    if now < int(park.get("until") or 0):
        print("parked: refused (%s) at %s, nothing asked until %s"
              % (park.get("why"), time.strftime("%Y-%m-%d %H:%M", time.gmtime(park.get("at") or 0)),
                 time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(park["until"]))))
    elif len(owed) > OWED_MAX:
        print("%d board(s) fetched and not yet filed: filing, not asking" % len(owed))
    else:
        try:
            cat = catalog_step(cache, pacer, now)
            names = set(cat["names"])
            try:
                names |= {f[:-5] for f in os.listdir(os.path.join(cache, "maps"))
                          if f.endswith(".json")}
            except OSError:
                pass
            maps = {m for m in names if m in have}
            prio = wanted_maps(now) & maps
            if cat["done"]:
                refreshed = refresh_step(cache, idx, maps, prio, pacer,
                                         max(1, args.max // 4), now, fetched)
            _, _, left = sweep_maps(sorted(maps), cache, -1, pacer, sorted(KSF_MODES),
                                    prio, fetched, idx)
            if not left and pacer.left() > 0 and cat["done"]:
                again = rewalk_step(cache, idx, maps, now)
                if again:
                    print("  idle: %s walked again from rank 1" % again)
        except Refused as e:
            n = int(park.get("n") or 0) + 1
            wait = min(COOLDOWN * 2 ** (n - 1), COOLDOWN_MAX)
            _save(pf, {"at": now, "until": now + wait, "n": n, "why": str(e)})
            print("refused: %s -- parked for %d h, nothing is retried" % (e, wait // 3600))
            # Only an answer about the board strikes it: a 403/429/503, or no
            # answer at all, is about the host, and would set aside whichever
            # board happened to be asked first (review, 5 Oct).
            if pacer.what and (e.code in (404, 500) or e.board):
                strike(cache, idx, pacer.what, str(e))
        else:
            # Lifted only by an answer: a tick that asked nothing proves nothing.
            if park and pacer.made:
                os.remove(pf)
        finally:
            _save(ixf, idx)
    if fetched:
        sf = os.path.join(cache, "strikes.json")
        st = _load(sf)
        if isinstance(st, dict) and st:
            for mp, z, m, _ in fetched:
                st.pop(_ikey(mp, z, m), None)
            _save(sf, st)
    # A board owed by an earlier run is filed WHOLE, fetched again this tick or
    # not: filing only this tick's page and clearing its marker lost the pages
    # the earlier run never filed (review, 5 Oct).  The upsert is idempotent.
    owing = set(owed)
    rows, files = [], []
    for mp, z, m, page in fetched:
        b = (mp, z, m)
        if b not in owing:
            rows += [r for r in (rec_row(mp, z, m, rec) for rec in page) if r]
        elif b not in files:
            rows += board_rows(cache, *b)       # every page this tick included
        if b not in files:
            files.append(b)
    # Boards owed and not fetched: whole, RECOVER_ROWS at a time, and never for
    # a map this install cannot load (a by-hand run may have used other maps).
    recovered = 0
    for b in owed:
        if b in files:
            continue
        if b[0] not in have:
            clear_owed(cache, [b])
            continue
        if len(rows) >= RECOVER_ROWS:
            break
        rows += board_rows(cache, *b)
        files.append(b)
        recovered += 1
    print("watch: %d request(s), %d page(s) (%d refreshed), %d owed board(s) filed, "
          "%d row(s); %d map(s), %d wanted; %d board(s) wanting more"
          % (pacer.made, len(fetched), refreshed, recovered, len(rows), len(maps),
             len(prio), left))
    return rows, files


def known_ksf_maps():
    """Maps already holding a ksf row: their main board exists by construction."""
    conn = S.connect()
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT map FROM runs WHERE tier=? ORDER BY map",
            (S.TIER_KSF,))]
    finally:
        conn.close()


def playable_maps():
    """Map names this install can actually load, lowercased.

    A row for a map with no BSP is DROPPED rather than stored: it would sit on
    a board nobody can open, and the first person to click it would meet a
    failure that looks like ours rather than like a map we do not have.

    surfd's own library (MAPS_DIR) first: on the Pi the paths below hold no
    BSP at all, and until 5 Oct this answered an empty set there.
    """
    out = {m.lower() for m in S.map_index()[0]}
    for root in (S.RUNS_DIR, S.MOMENTUM_DIR):
        base = os.path.dirname(os.path.normpath(root))
        for sub in ("maps", os.path.join("ftesurf", "maps"),
                    os.path.join("momentum", "maps")):
            d = os.path.join(base, sub)
            try:
                for f in os.listdir(d):
                    if f.lower().endswith(".bsp"):
                        out.add(os.path.splitext(f)[0].lower())
            except OSError:
                continue
    return out


def read_map_list(path):
    """Map names, one per line, # comments; anything clean_map refuses is dropped."""
    out = []
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            mp = S.clean_map(ln.split("#", 1)[0].strip())
            if mp and mp not in out:
                out.append(mp)
    return out


def seed_mode(args, seed, have, cache):
    """--seed/--from-boards: each player's best records, main track only."""
    ids = sorted(seed)[:args.max]
    print("seed %d player(s), taking %d; %d playable map name(s) known"
          % (len(seed), len(ids), len(have)))

    rows, asked, cached, refused, nomap = [], 0, 0, 0, 0
    notaplayer = streak = 0
    for sid in ids:
        try:
            doc, fresh = records(sid, cache, paced=(asked > 0))
        except NoSuchPlayer:
            asked += 1
            notaplayer += 1
            streak += 1
            if streak >= SKIP_STREAK:
                print("  %d consecutive ids unknown to ksf.surf -- stopping."
                      "  That is more likely this host refusing than a run of\n"
                      "  non-players, and the difference is not ours to assume."
                      % streak)
                break
            continue
        except Refused as e:
            print("  refused for %d: %s -- stopping, nothing is retried" % (sid, e))
            refused += 1
            break
        streak = 0
        asked += 1 if fresh else 0
        cached += 0 if fresh else 1
        for rec in (doc.get("records") or []):
            name = rec.get("mapName")
            t = rec.get("time")
            if not isinstance(name, str) or not isinstance(t, (int, float)) or t <= 0:
                continue
            mp = S.clean_map(name)
            if mp is None:
                continue
            if mp not in have:
                nomap += 1
                continue
            ms = int(round(t * 1000.0))
            rows.append({
                "map": mp, "track": 0, "leg": 0, "player": str(sid),
                "name": seed[sid],
                "millis": ms, "ticks": int(round(ms / 1000.0 / KSF_TICK)),
                "rate": 1.0 / KSF_TICK,
                "when": _when(rec),
            })

    print("requests made   %d   (from cache %d)" % (asked, cached))
    print("not KSF players %d  (HTTP 500: an answer, not a refusal)" % notaplayer)
    print("records kept    %d" % len(rows))
    print("dropped, no bsp %d" % nomap)
    if refused:
        print("refused         %d" % refused)
    return rows, []


def maps_mode(args, have, cache):
    """--from-maps: page every board of each map; returns (run rows, boards)."""
    names = (known_ksf_maps() if args.from_maps == "known"
             else read_map_list(args.from_maps))
    maps = [m for m in names if m in have]
    budget = KSF_REQ_DEFAULT if args.max is None else args.max
    pacer = Pacer(args.delay, budget)
    ixf = os.path.join(cache, "index.json")
    idx = _load(ixf)
    idx = idx if isinstance(idx, dict) else {}
    print("%d map(s) listed, %d playable here; depth %s; at most %d request(s), "
          "%.2f s apart" % (len(names), len(maps),
                            "all" if args.depth < 0 else args.depth, budget,
                            args.delay))
    try:
        infos, absent, left = sweep_maps(maps, cache, args.depth, pacer, args.modes,
                                         idx=idx)
    except Refused as e:
        print("  refused: %s -- stopping, nothing is retried" % e)
        # What the cache already holds is still good; read it with no budget.
        infos, absent, left = sweep_maps(maps, cache, args.depth, Pacer(0, 0),
                                         args.modes, idx=idx)
    finally:
        _save(ixf, idx)
    rows, bad, boards = map_rows(cache, infos, args.modes)
    kinds = [sum(1 for r in rows if (r["track"], r["leg"]) == (0, 0)),
             sum(1 for r in rows if r["leg"] > 0),
             sum(1 for r in rows if r["track"] > 0)]
    print("requests made   %d" % pacer.made)
    print("maps on KSF     %d   (not there: %d, not yet looked up: %d)"
          % (len(infos), absent, len(maps) - len(infos) - absent))
    print("boards wanting  %d more page(s)" % left)
    print("records kept    %d   main %d, stage %d, bonus %d   (unusable %d)"
          % (len(rows), kinds[0], kinds[1], kinds[2], bad))
    print("by style        %s" % ", ".join(
        "%s %d" % (KSF_MODES[m], sum(1 for r in rows if r["style"] == KSF_MODES[m]))
        for m in args.modes))
    return rows, boards


def take_lock(cache):
    """One ksfimport at a time per cache: a --watch tick and a by-hand run
    would otherwise ask KSF twice at once and race each other's board files."""
    os.makedirs(cache, exist_ok=True)
    fh = io.open(os.path.join(cache, ".lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", help="file of steamid64s, one per line")
    ap.add_argument("--from-boards",
                    help="seed from tools/momfetch.py's cache instead: the\nplayers already on Momentum's surf boards, most-seen first")
    ap.add_argument("--from-maps", nargs="?", const="known", default=None,
                    help="page every board of these maps: a file of names, or\nnothing for the maps already holding a ksf row")
    ap.add_argument("--depth", type=int, default=KSF_DEPTH_DEFAULT,
                    help="--from-maps: rows per board, -1 for all")
    ap.add_argument("--modes", default=",".join(str(m) for m in sorted(KSF_MODES)),
                    help="--from-maps: KSF styles, 0 Forward 1 Sideways\n2 Half-Sideways 3 Backwards")
    ap.add_argument("--watch", action="store_true",
                    help="one unattended crawl tick, for cron (see the docstring)")
    ap.add_argument("--delay", type=float, default=None,
                    help="--from-maps/--watch: seconds between requests\n(default %.1f, --watch %.1f)"
                    % (KSF_DELAY_MS / 1000.0, WATCH_DELAY))
    ap.add_argument("--cache", default=None, help="default <SURFD_HOME>/data/ksf")
    ap.add_argument("--max", type=int, default=None,
                    help="players (--seed/--from-boards, default %d) or requests\n(--from-maps, default %d) this invocation"
                    % (KSF_MAX_DEFAULT, KSF_REQ_DEFAULT))
    ap.add_argument("--maps", default=None,
                    help="a directory of .bsp to filter against; repeatable via os.pathsep")
    ap.add_argument("--go", action="store_true", help="write rows; otherwise a dry run")
    args = ap.parse_args()

    cache = args.cache or os.path.join(S.DATA_DIR, "ksf")
    try:
        args.modes = sorted({int(m) for m in str(args.modes).split(",") if m.strip()})
    except ValueError:
        args.modes = []
    if not args.modes or any(m not in KSF_MODES for m in args.modes):
        print("--modes takes numbers from %s" % sorted(KSF_MODES))
        return 2
    if args.delay is None:
        args.delay = WATCH_DELAY if args.watch else KSF_DELAY_MS / 1000.0
    if args.watch:
        # A tick files only what it fetched, so a dry one fetches nothing.
        args.max = 0 if not args.go else (WATCH_MAX if args.max is None else args.max)
    elif args.from_maps is None:
        if args.max is None:
            args.max = KSF_MAX_DEFAULT
        if args.from_boards:
            seed = seed_from_boards(args.from_boards, args.max)
        elif args.seed:
            seed = read_seed(args.seed)
        else:
            print("give --seed, --from-boards, --from-maps or --watch")
            return 2
        if not seed:
            print("no usable steamid64 in the seed")
            return 2

    have = set()
    if args.maps:
        for d in args.maps.split(os.pathsep):
            try:
                have |= {os.path.splitext(f)[0].lower()
                         for f in os.listdir(d) if f.lower().endswith(".bsp")}
            except OSError:
                pass
    else:
        have = playable_maps()
    # An empty library used to read as "no filter", which files rows for maps
    # nobody can load -- on cron, every map KSF lists.
    if not have:
        print("no installed maps found (%s) -- nothing is fetched or filed"
              % (args.maps or S.MAPS_DIR))
        return 2

    lock = take_lock(cache)
    if lock is None:
        print("another ksfimport holds %s -- not running beside it" % cache)
        return 0 if args.watch else 2
    try:
        if args.watch:
            rows, boards = watch_mode(args, have, cache)
        elif args.from_maps is not None:
            rows, boards = maps_mode(args, have, cache)
        else:
            rows, boards = seed_mode(args, seed, have, cache)

        if not args.go:
            for r in rows[:10]:
                print("   %-28s t%d l%d %-5s %9.3fs  %s"
                      % (r["map"], r["track"], r["leg"], r.get("style", S.STYLE_CLEAN),
                         r["millis"] / 1000.0, r["name"]))
            print("\nDRY RUN -- nothing written.  Pass --go.")
            return 0
        try:
            n = write_rows(rows)
        except sqlite3.Error as e:
            # The boards stay owed, and the next --watch tick files them.
            print("write failed (%s): %d board(s) stay owed" % (e, len(boards)))
            return 1
        clear_owed(cache, boards)
        print("board rows set  %d" % n)
        return 0
    finally:
        lock.close()


def write_rows(rows):
    """Upsert run rows; a slower time never replaces a faster.  WRITE_CHUNK rows
    a transaction, so the lock is let go between them -- momwatch's "database is
    locked" heartbeats were one long transaction (BACKLOG)."""
    conn = S.connect()
    # FULL, not surfd's NORMAL: an owed marker is removed once this returns, and
    # under NORMAL a power cut can roll back a WAL commit that reported success.
    conn.execute("PRAGMA synchronous=FULL")
    now = int(time.time())
    wrote = 0
    try:
        for i in range(0, len(rows), WRITE_CHUNK):
            with conn:
                for r in rows[i:i + WRITE_CHUNK]:
                    # The seed path's rows are all (0, 0): bestrecords carries no
                    # stage or bonus (stage_id and zone_id are null on every row
                    # seen).  replay_id stays 0 -- there is no recording.
                    cur = conn.execute(
                        "INSERT INTO runs (map, track, leg, tier, style, player, name,"
                        "   ticks, tickrate, millis, flags, node, runid, submitted, replay_id)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,0,'ksf','',?,0)"
                        " ON CONFLICT (map, track, leg, tier, style, player) DO UPDATE SET"
                        "   ticks=excluded.ticks, millis=excluded.millis,"
                        "   name=excluded.name, submitted=excluded.submitted"
                        " WHERE excluded.millis < runs.millis",
                        (r["map"], r["track"], r["leg"], S.TIER_KSF,
                         r.get("style", S.STYLE_CLEAN),
                         r["player"], r["name"], r["ticks"], r["rate"], r["millis"],
                         r["when"] or now))
                    wrote += cur.rowcount
    finally:
        conn.close()
    return wrote


if __name__ == "__main__":
    raise SystemExit(main())
