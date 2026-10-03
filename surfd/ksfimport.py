"""Import Counter-Strike: Source times from the ksf.surf timer network.

  python surfd/ksfimport.py --seed <file of steamid64s> [--go] [--max N]
  python surfd/ksfimport.py --from-maps [--depth -1] [--max N] [--go]

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

TWO WAYS IN: PLAYER-SEEDED (--seed/--from-boards) AND MAP-SEEDED (--from-maps).

  THE MAP-SEEDED ROUTE IS A PLAIN PAGED JSON API, 2026-09-29.  Everything the
  three previous notes here said about it was wrong, and the corrections matter
  more than the conclusion did:

      GET /api/maps/<map>/records/zone/<zone>/<startRank>?game=css&mode=0
          -> 200 application/json, a LIST of at most KSF_PAGE rows
      GET /api/maps/search/<name>
          -> 200, up to 5 map rows carrying cp_count and b_count

  WHAT THIS FILE CLAIMED UNTIL TODAY, AND WHY EACH WAS FALSE:
    * "THERE IS NO API ROUTE TO FIND ... the board is a server component embedded
      in the page" -- false.  /maps/<map>/records embeds only the WR *history*
      (13 rows of player/country/steamID/time/date).  The leaderboard is fetched
      by the browser after load, so it is in no flight chunk and the route is in
      the bundle after all: module 66683 of the records page chunk builds it.
      The earlier searches looked at /maps/<map>, which does not mount that
      component -- a failed search over the wrong page, reported as a proof.
    * "exactly 10 rows ... there is no paging, so 10 is the board" -- false.  20
      rows a page, and the last path segment is an arbitrary 1-based START RANK:
      /1, /11 and /231 all answer 20 rows, and past the end answers [].
    * "?zone= is IGNORED, stages and bonuses are NOT REACHABLE" -- false.  zone is
      a PATH segment, not a query parameter.  zone 0 is the main track, 1..cp_count
      the stages and 31.. the bonuses, and an unknown zone answers [] rather than
      erroring.
    * "parsing their framework internals, which will break QUIETLY" -- there is
      nothing to parse.  This is the site's own JSON, so the fragility argument
      that kept it unbuilt was an argument about a parser that never needed to
      exist.

  A row carries rank, playerID, name, steamID (STEAM_0:Y:Z), country, time,
  completions, date, date_at, record_id, file, wrDiff and r2Diff.  Richer than
  Momentum's: a real rank, a full steamID, and the replay's filename.

  HOW DEEP TO GO IS NOT ANNOUNCED.  No reply carries a total, so a board ends
  when a page comes back short of KSF_PAGE -- the same terminator momfetch uses
  for a short later page, and for the same reason.  The cache is the cursor.

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
import io
import json
import os
import sys
import time
import urllib.error
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", help="file of steamid64s, one per line")
    ap.add_argument("--from-boards",
                    help="seed from tools/momfetch.py's cache instead: the\nplayers already on Momentum's surf boards, most-seen first")
    ap.add_argument("--cache", default=None, help="default <SURFD_HOME>/data/ksf")
    ap.add_argument("--max", type=int, default=KSF_MAX_DEFAULT)
    ap.add_argument("--maps", default=None,
                    help="a directory of .bsp to filter against; repeatable via os.pathsep")
    ap.add_argument("--go", action="store_true", help="write rows; otherwise a dry run")
    args = ap.parse_args()

    cache = args.cache or os.path.join(S.DATA_DIR, "ksf")
    if args.from_boards:
        seed = seed_from_boards(args.from_boards, args.max)
    elif args.seed:
        seed = read_seed(args.seed)
    else:
        print("give --seed or --from-boards")
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
                "map": mp, "player": str(sid), "name": seed[sid],
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

    if not args.go:
        for r in rows[:10]:
            print("   %-28s %9.3fs  %s" % (r["map"], r["millis"] / 1000.0, r["name"]))
        print("\nDRY RUN -- nothing written.  Pass --go.")
        return 0

    conn = S.connect()
    now = int(time.time())
    wrote = 0
    with conn:
        for r in rows:
            # Main track, full run: KSF's bestrecords carries no stage or bonus
            # (stage_id and zone_id are null on every row seen), so filing one
            # anywhere but leg 0 would be inventing a leg.  replay_id stays 0 --
            # there is no recording and there is no way to get one.
            cur = conn.execute(
                "INSERT INTO runs (map, track, leg, tier, style, player, name,"
                "   ticks, tickrate, millis, flags, node, runid, submitted, replay_id)"
                " VALUES (?,0,0,?,?,?,?,?,?,?,0,'ksf','',?,0)"
                " ON CONFLICT (map, track, leg, tier, style, player) DO UPDATE SET"
                "   ticks=excluded.ticks, millis=excluded.millis,"
                "   name=excluded.name, submitted=excluded.submitted"
                " WHERE excluded.millis < runs.millis",
                (r["map"], S.TIER_KSF, S.STYLE_CLEAN, r["player"], r["name"],
                 r["ticks"], r["rate"], r["millis"], r["when"] or now))
            wrote += cur.rowcount
    print("board rows set  %d" % wrote)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
