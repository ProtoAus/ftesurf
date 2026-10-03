"""Import Counter-Strike: Source times from the ksf.surf timer network.

  python surfd/ksfimport.py --seed <file of steamid64s> [--go] [--max N]
  python surfd/ksfimport.py --from-maps [<file of map names>] [--depth N]
                            [--max <requests>] [--delay <s>] [--go]

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
  * KSF_DELAY_MS between them, always
  * a cap per invocation, so one command cannot become a thousand requests
  * a User-Agent that says what this is and where to complain
  * never automatic: every run of this is a person typing it
  * a non-2xx is reported AS A REFUSAL and nothing is retried.  If ksf.surf does
    not want automated requests the answer is to stop, not to look more like a
    browser.
Every answer is cached on disk, so a re-run costs nothing and the second import
of the same seed list makes no requests at all.

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
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

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
    """ksf.surf said no to US.  Reported, never retried, stops the run."""


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
                raise Refused("HTTP %d" % r.status)
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # 500 is this host's answer for an id it does not know; anything else
        # (403, 429, 503) is about US and stops the run.  If that reading is
        # ever wrong the breaker below catches it: a host that is actually
        # refusing returns 500 to everything, and SKIP_STREAK in a row stops.
        if e.code == 500:
            raise NoSuchPlayer("HTTP 500")
        raise Refused("HTTP %d" % e.code)
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
    """One request at a time, `delay` seconds apart, at most `budget` of them."""

    def __init__(self, delay, budget):
        self.delay, self.budget, self.made = delay, budget, 0

    def left(self):
        return self.budget - self.made

    def get(self, path):
        if self.made:
            time.sleep(self.delay)
        self.made += 1
        try:
            body = fetch(KSF_BASE + path)
        except NoSuchPlayer as e:
            # "not a player of mine" is the PLAYER route's dialect; here a 500 is
            # just a refusal.
            raise Refused(str(e))
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
    """KSF's row for exactly `mp`, or None when KSF has no map by that name."""
    cf = os.path.join(cache, "maps", mp + ".json")
    doc = _load(cf)
    if doc is None:
        doc = pacer.get("/api/maps/search/" + urllib.parse.quote(mp))
        _save(cf, doc)
    for row in doc if isinstance(doc, list) else ():
        if isinstance(row, dict) and str(row.get("name") or "").lower() == mp:
            return row
    return None


def board_path(cache, mp, zone):
    return os.path.join(cache, "boards", mp, "z%d.json" % zone)


def board_load(cache, mp, zone):
    doc = _load(board_path(cache, mp, zone))
    if not isinstance(doc, dict) or not isinstance(doc.get("rows"), list):
        doc = {"rows": [], "done": False}
    return doc


def board_page(cache, mp, zone, pacer):
    """Fetch one board's next page and append it to the cache."""
    doc = board_load(cache, mp, zone)
    page = pacer.get("/api/maps/%s/records/zone/%d/%d?game=css&mode=0"
                     % (urllib.parse.quote(mp), zone, len(doc["rows"]) + 1))
    if not isinstance(page, list):
        raise Refused("a records page was not a list -- their format has "
                      "probably changed")
    doc["rows"].extend(r for r in page if isinstance(r, dict))
    doc["done"] = len(page) < KSF_PAGE
    _save(board_path(cache, mp, zone), doc)
    return doc


def wants_more(doc, depth):
    return not doc["done"] and (depth < 0 or len(doc["rows"]) < depth)


def sweep_maps(maps, cache, depth, pacer):
    """Look the maps up, then fetch pages shallowest first until the budget or
    the work runs out -- so an interrupted sweep leaves every board equally deep.

    Returns ({map: info}, maps KSF does not have, boards still wanting pages)."""
    infos, absent = {}, 0
    for mp in maps:
        if pacer.left() <= 0 and not os.path.exists(
                os.path.join(cache, "maps", mp + ".json")):
            continue
        info = map_info(mp, cache, pacer)
        if info is None:
            absent += 1
        else:
            infos[mp] = info
    heap = [(len(d["rows"]), mp, z)
            for mp, info in infos.items() for z in zones_of(info)
            for d in (board_load(cache, mp, z),) if wants_more(d, depth)]
    heapq.heapify(heap)
    while heap and pacer.left() > 0:
        _, mp, z = heapq.heappop(heap)
        d = board_page(cache, mp, z, pacer)
        if wants_more(d, depth):
            heapq.heappush(heap, (len(d["rows"]), mp, z))
    return infos, absent, len(heap)


def map_rows(cache, infos):
    """Every cached board row as a run row, plus the count unusable."""
    rows, bad = [], 0
    for mp in sorted(infos):
        for z in zones_of(infos[mp]):
            track, leg = zone_track_leg(z)
            for rec in board_load(cache, mp, z)["rows"]:
                sid = steam64(str(rec.get("steamID") or ""))
                t = rec.get("time")
                if sid is None or not isinstance(t, (int, float)) or t <= 0:
                    bad += 1
                    continue
                ms = int(round(t * 1000.0))
                rows.append({
                    "map": mp, "track": track, "leg": leg, "player": str(sid),
                    "name": S.clean_text(rec.get("name") or "") or str(sid),
                    "millis": ms, "ticks": int(round(ms / 1000.0 / KSF_TICK)),
                    "rate": 1.0 / KSF_TICK, "when": int(rec.get("date") or 0),
                })
    return rows, bad


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
    """
    out = set()
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
            if have and mp not in have:
                nomap += 1
                continue
            ms = int(round(t * 1000.0))
            rows.append({
                "map": mp, "track": 0, "leg": 0, "player": str(sid),
                "name": seed[sid],
                "millis": ms, "ticks": int(round(ms / 1000.0 / KSF_TICK)),
                "rate": 1.0 / KSF_TICK,
                "when": int(rec.get("date") or 0),
            })

    print("requests made   %d   (from cache %d)" % (asked, cached))
    print("not KSF players %d  (HTTP 500: an answer, not a refusal)" % notaplayer)
    print("records kept    %d" % len(rows))
    print("dropped, no bsp %d" % nomap)
    if refused:
        print("refused         %d" % refused)
    return rows


def maps_mode(args, have, cache):
    """--from-maps: page every board of each map; returns the run rows."""
    names = (known_ksf_maps() if args.from_maps == "known"
             else read_map_list(args.from_maps))
    maps = [m for m in names if not have or m in have]
    budget = KSF_REQ_DEFAULT if args.max is None else args.max
    pacer = Pacer(args.delay, budget)
    print("%d map(s) listed, %d playable here; depth %s; at most %d request(s), "
          "%.2f s apart" % (len(names), len(maps),
                            "all" if args.depth < 0 else args.depth, budget,
                            args.delay))
    try:
        infos, absent, left = sweep_maps(maps, cache, args.depth, pacer)
    except Refused as e:
        print("  refused: %s -- stopping, nothing is retried" % e)
        # What the cache already holds is still good; read it with no budget.
        infos, absent, left = sweep_maps(maps, cache, args.depth, Pacer(0, 0))
    rows, bad = map_rows(cache, infos)
    kinds = [sum(1 for r in rows if (r["track"], r["leg"]) == (0, 0)),
             sum(1 for r in rows if r["leg"] > 0),
             sum(1 for r in rows if r["track"] > 0)]
    print("requests made   %d" % pacer.made)
    print("maps on KSF     %d   (not there: %d, not yet looked up: %d)"
          % (len(infos), absent, len(maps) - len(infos) - absent))
    print("boards wanting  %d more page(s)" % left)
    print("records kept    %d   main %d, stage %d, bonus %d   (unusable %d)"
          % (len(rows), kinds[0], kinds[1], kinds[2], bad))
    return rows


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
    ap.add_argument("--delay", type=float, default=KSF_DELAY_MS / 1000.0,
                    help="--from-maps: seconds between requests")
    ap.add_argument("--cache", default=None, help="default <SURFD_HOME>/data/ksf")
    ap.add_argument("--max", type=int, default=None,
                    help="players (--seed/--from-boards, default %d) or requests\n(--from-maps, default %d) this invocation"
                    % (KSF_MAX_DEFAULT, KSF_REQ_DEFAULT))
    ap.add_argument("--maps", default=None,
                    help="a directory of .bsp to filter against; repeatable via os.pathsep")
    ap.add_argument("--go", action="store_true", help="write rows; otherwise a dry run")
    args = ap.parse_args()

    cache = args.cache or os.path.join(S.DATA_DIR, "ksf")
    if args.from_maps is None:
        if args.max is None:
            args.max = KSF_MAX_DEFAULT
        if args.from_boards:
            seed = seed_from_boards(args.from_boards, args.max)
        elif args.seed:
            seed = read_seed(args.seed)
        else:
            print("give --seed, --from-boards or --from-maps")
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

    if args.from_maps is not None:
        rows = maps_mode(args, have, cache)
    else:
        rows = seed_mode(args, seed, have, cache)

    if not args.go:
        for r in rows[:10]:
            print("   %-28s t%d l%d %9.3fs  %s" % (r["map"], r["track"], r["leg"],
                                                 r["millis"] / 1000.0, r["name"]))
        print("\nDRY RUN -- nothing written.  Pass --go.")
        return 0

    conn = S.connect()
    now = int(time.time())
    wrote = 0
    with conn:
        for r in rows:
            # The seed path's rows are all (0, 0): bestrecords carries no stage
            # or bonus (stage_id and zone_id are null on every row seen).
            # replay_id stays 0 -- there is no recording and no way to get one.
            cur = conn.execute(
                "INSERT INTO runs (map, track, leg, tier, style, player, name,"
                "   ticks, tickrate, millis, flags, node, runid, submitted, replay_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,0,'ksf','',?,0)"
                " ON CONFLICT (map, track, leg, tier, style, player) DO UPDATE SET"
                "   ticks=excluded.ticks, millis=excluded.millis,"
                "   name=excluded.name, submitted=excluded.submitted"
                " WHERE excluded.millis < runs.millis",
                (r["map"], r["track"], r["leg"], S.TIER_KSF, S.STYLE_CLEAN,
                 r["player"], r["name"], r["ticks"], r["rate"], r["millis"],
                 r["when"] or now))
            wrote += cur.rowcount
    print("board rows set  %d" % wrote)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
