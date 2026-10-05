"""Index imported Momentum Mod runs into the board, under their own tier.

  python surfd/momindex.py [--dry-run] [--prune]

Reads <MOMENTUM_DIR>/<map>/<leg dir>/<leaf>.rec -- the files tools/momimport.py
writes -- and files them as `replays` rows of kind='momentum' and `runs` rows of
tier='momentum'.  Nothing here touches the ranked or community boards, and that
is checkable rather than asserted: every board query filters on `tier`, so a row
in a tier nothing queries is invisible by construction.  test_momindex.py holds
the arm that proves /api/board's ranked output is byte-identical across an
import.

WHY A TIER AND NOT A FLAG.  `tier` is in the runs primary key, so one player can
hold an FTESurf time and a Momentum time on the same board without either
overwriting the other -- which a flag on a shared row could not express.  It is
also already the hiding mechanism: Patch 425 parks rejected and displaced rows
under unreadable tier strings for exactly this reason.

WHY NOT /api/run.  That endpoint is the network submit path: key-gated, and its
leaf checks (the 7-digit stamp against ticks, the sha256(player)[:8] digest, and
_rec_disagrees against the file's own header) exist to bind a row to a recording
a LOBBY wrote.  An import is not that, and `momentum` is deliberately absent
from surfd's TIERS so the wire cannot name it at all.  This runs beside the
files, like index_evidence, and is the only writer of that tier.

THE HEADER IS THE SOURCE OF TRUTH, not momimport's manifest.  A manifest can
drift from the files beside it; a header cannot drift from the file it is in.
So this re-reads every header and the manifest is left for humans.
"""
import argparse
import hashlib
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Importing surfd logs "surfd ready" to surfd.log, which reads as a restart on
# every tick (sweep.py's fix): a handler on its logger first keeps it quiet.
if not logging.getLogger("surfd").handlers:
    _quiet = logging.StreamHandler(sys.stderr)
    _quiet.setLevel(logging.WARNING)
    logging.getLogger("surfd").addHandler(_quiet)

import surfd as S       # noqa: E402  -- import-safe: app.run is __main__-guarded


def scan(root):
    """Yield (map_dir, track, leg, leaf, path) for every well-named file."""
    try:
        maps = sorted(os.listdir(root))
    except OSError:
        return
    for map_dir in maps:
        if not S._MAPNAME_OK.match(map_dir):
            continue
        mroot = os.path.join(root, map_dir)
        if not os.path.isdir(mroot):
            continue
        for legd in sorted(os.listdir(mroot)):
            lroot = os.path.join(mroot, legd)
            if not os.path.isdir(lroot):
                continue
            # Invert FS_LegDir rather than trust the header: the directory is
            # what replay_file() will rebuild the path from, so a file whose
            # header disagrees with where it sits must not be indexed from the
            # header, or the row would name a path that does not exist.
            track, leg = leg_of(legd)
            if track is None:
                continue
            for leaf in sorted(os.listdir(lroot)):
                if not leaf.endswith(".rec") or not S._LEAF_OK.match(leaf):
                    continue
                yield map_dir, track, leg, leaf, os.path.join(lroot, leaf)


def leg_of(d):
    """FS_LegDir inverted: 'main'|'stage_N'|'bonus_N'|'bonus_N_stage_M'."""
    if d == "main":
        return 0, 0
    p = d.split("_")
    try:
        if len(p) == 2 and p[0] == "stage":
            return 0, int(p[1])
        if len(p) == 2 and p[0] == "bonus":
            return int(p[1]), 0
        if len(p) == 4 and p[0] == "bonus" and p[2] == "stage":
            return int(p[1]), int(p[3])
    except ValueError:
        pass
    return None, None


def is_steamid64(s):
    """A real SteamID64, not merely a positive integer.

    THIS EXISTS BECAUSE THE LOOSE TEST SHIPPED AND WAS WRONG.  The first cut
    read field 4 of the provenance key instead of field 5 and accepted it
    because `isdigit() and > 0` is true of a trackNum -- so all 2961 runs were
    filed under ten "players" numbered 1..10, and every row still looked
    perfectly plausible.  The high-word test is the same one wrlines' own .mtv
    gate uses, and it refuses a trackNum on sight.
    """
    if not s.isdigit() or len(s) != 17:
        return False
    return (int(s) >> 32) == 0x01100001


def read_one(path):
    """(info, None) or (None, why).  Everything comes out of the header."""
    meta = S._rec_meta(path)
    if meta is None:
        return None, "unreadable"
    hdr, end, abandoned, size, _mtime, _rows = meta
    if abandoned:
        return None, "abandoned"
    if "foreign" not in hdr:
        # Not ours to index.  A file here without the provenance key was put
        # here by something else, and guessing what it is would be worse than
        # leaving it alone.
        return None, "no foreign key"
    # `foreign momentum <sha> <gamemode> <trackType> <trackNum> <steamid64>`
    # -- six fields after the key word, and the id is the LAST of them.
    f = hdr["foreign"].split()
    if not f or f[0] != "momentum" or len(f) < 6:
        return None, "foreign key is not momentum's"
    if not is_steamid64(f[5]):
        return None, "no steamid"
    steamid = f[5]

    ticks = S.strict_int(str(end), 1, S.MAX_TICKS)
    if ticks is None:
        return None, "no end ticks"
    # The header states SECONDS PER TICK; runs.tickrate is HERTZ.  Getting this
    # the wrong way up puts every imported time out by a factor of 4444.
    spt = S.strict_float(hdr.get("tickrate", ""), 0.0001, 1.0)
    if spt is None:
        return None, "no tickrate"
    rate = 1.0 / spt
    q = (hdr.get("momquality") or "").split()
    return {
        "player": steamid,
        "name": S.clean_text(hdr.get("owner", "")) or "?",
        "ticks": ticks,
        "rate": rate,
        "millis": int(round(ticks * 1000.0 / rate)),
        "runid": S.clean_text(hdr.get("runid", "")),
        "bytes": size,
        "ratio": q[0] if q else "0",
    }, None


def index_one(conn, map_dir, track, leg, leaf, i, now, board=True):
    """File one read_one() recording: its replays row and, when it is the
    player's best and `board`, its board row.  Returns (replay added, board row
    set)."""
    mp = map_dir.lower()
    cur = conn.execute(
        "INSERT INTO replays (map, map_dir, track, leg, leaf, tier,"
        "   style, player, name, ticks, tickrate, millis, flags, node,"
        "   submitted, bytes, kind, bound, runid)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,'import',?,?,'momentum',1,?)"
        " ON CONFLICT (map, track, leg, leaf) DO UPDATE SET"
        "   ticks=excluded.ticks, tickrate=excluded.tickrate,"
        "   millis=excluded.millis, name=excluded.name,"
        "   bytes=excluded.bytes, player=excluded.player",
        (mp, map_dir, track, leg, leaf, S.TIER_MOMENTUM,
         S.STYLE_CLEAN, i["player"], i["name"], i["ticks"], i["rate"],
         i["millis"], now, i["bytes"], i["runid"]))
    added = cur.rowcount
    if not board:
        return added, 0
    rid = conn.execute(
        "SELECT id FROM replays WHERE map=? AND track=? AND leg=? AND leaf=?",
        (mp, track, leg, leaf)).fetchone()[0]
    # One runs row per player per board: the BEST time wins, which
    # is what the ranked board does too.  A slower import must not
    # displace a faster one just because it was walked later.
    cur = conn.execute(
        "INSERT INTO runs (map, track, leg, tier, style, player, name,"
        "   ticks, tickrate, millis, flags, node, runid, submitted, replay_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,0,'import',?,?,?)"
        " ON CONFLICT (map, track, leg, tier, style, player) DO UPDATE SET"
        "   ticks=excluded.ticks, tickrate=excluded.tickrate,"
        "   millis=excluded.millis, name=excluded.name,"
        "   runid=excluded.runid, replay_id=excluded.replay_id,"
        "   submitted=excluded.submitted"
        " WHERE excluded.millis < runs.millis",
        (mp, track, leg, S.TIER_MOMENTUM, S.STYLE_CLEAN, i["player"],
         i["name"], i["ticks"], i["rate"], i["millis"], i["runid"],
         now, rid))
    return added, cur.rowcount


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=S.MOMENTUM_DIR)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="drop indexed rows whose file is gone")
    args = ap.parse_args()

    conn = S.connect()
    seen, bad, files = {}, {}, 0
    for map_dir, track, leg, leaf, path in scan(args.root):
        files += 1
        info, why = read_one(path)
        if info is None:
            bad[why] = bad.get(why, 0) + 1
            continue
        key = (map_dir.lower(), track, leg, leaf)
        info.update(map_dir=map_dir, track=track, leg=leg, leaf=leaf)
        seen[key] = info

    now = int(__import__("time").time())
    added = updated = 0
    if not args.dry_run:
        with conn:
            for (mp, track, leg, leaf), i in sorted(seen.items()):
                a, u = index_one(conn, i["map_dir"], track, leg, leaf, i, now)
                added += a
                updated += u

            if args.prune:
                gone = [r["id"] for r in conn.execute(
                    "SELECT id, map, map_dir, track, leg, leaf, kind FROM replays"
                    " WHERE kind='momentum'")
                    if (r["map"], r["track"], r["leg"], r["leaf"]) not in seen]
                for rid in gone:
                    conn.execute("DELETE FROM runs WHERE replay_id=? AND tier=?",
                                 (rid, S.TIER_MOMENTUM))
                    conn.execute("DELETE FROM replays WHERE id=?", (rid,))
                print("pruned          %d row(s) whose file is gone" % len(gone))

    print("files walked    %d" % files)
    print("indexable       %d" % len(seen))
    print("replays added   %d" % added)
    print("board rows set  %d" % updated)
    for why, n in sorted(bad.items(), key=lambda kv: -kv[1]):
        print("   skipped %-28s %d" % (why, n))
    if args.dry_run:
        print("\nDRY RUN -- nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
