"""Import Counter-Strike: Source times from the ksf.surf timer network.

  python surfd/ksfimport.py --seed <file of steamid64s> [--go] [--max N]

TIMES ONLY, AND THAT IS A LIMIT OF THE SOURCE RATHER THAN A CHOICE.  KSF
publishes no replay this project can reach: there is no demo URL in any endpoint
found, no Source .dem parser anywhere in this tree or in the wrlines reference,
and nothing that could turn one into a .rec.  So a KSF row carries no recording,
no line and no `watch` -- replay_id stays 0 and nothing pretends otherwise.

PLAYER-SEEDED, NOT MAP-SEEDED, and that is the awkward part.  ksf.surf serves
`/api/players/{id}/bestrecords/{n}` and `/api/maps/search/{q}`, both public and
unauthenticated, but the per-map leaderboard their own site renders is behind a
route this project has not located: twelve informed guesses over two sessions
(including every shape their two documented endpoints imply), the page HTML,
and all seventeen of its JS chunks, all without finding it.  THAT IS "NOT
LOCATED", NOT "ABSENT" -- their map pages plainly show records, so a route
exists and this file should be rewritten around it the day someone finds it.
Until then the only way in is one player at a time, capped at 25 records each.

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

KSF_BASE = "https://ksf.surf"
KSF_DELAY_MS = 400         # wrlines' WR_API_DELAY_MS, same host, same reasoning
KSF_TAKE = 25              # their own cap on bestrecords
KSF_MAX_DEFAULT = 50       # players per invocation unless --max says otherwise
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
    """ksf.surf said no.  Reported and not retried."""


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=KSF_TIMEOUT) as r:
            if r.status < 200 or r.status >= 300:
                raise Refused("HTTP %d" % r.status)
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
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
    ap.add_argument("--seed", required=True, help="file of steamid64s, one per line")
    ap.add_argument("--cache", default=None, help="default <SURFD_HOME>/data/ksf")
    ap.add_argument("--max", type=int, default=KSF_MAX_DEFAULT)
    ap.add_argument("--maps", default=None,
                    help="a directory of .bsp to filter against; repeatable via os.pathsep")
    ap.add_argument("--go", action="store_true", help="write rows; otherwise a dry run")
    args = ap.parse_args()

    cache = args.cache or os.path.join(S.DATA_DIR, "ksf")
    seed = read_seed(args.seed)
    if not seed:
        print("no usable steamid64 in %s" % args.seed)
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
    for sid in ids:
        try:
            doc, fresh = records(sid, cache, paced=(asked > 0))
        except Refused as e:
            print("  refused for %d: %s -- stopping, nothing is retried" % (sid, e))
            refused += 1
            break
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
