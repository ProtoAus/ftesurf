#!/usr/bin/env python3
"""steamsync.py -- keep each account's Steam name (and avatar hash) current.

    python3 steamsync.py [--go] [--max N]            (cron, every half hour)

A linked player's name in the game and on the boards is their Steam name
(Patch 638).  Signing in stored it once; this asks Steam again, fifty accounts
a request.  THEN THE ROWS FOLLOW THE ACCOUNT, whoever wrote its name: every
row and recording of a named account on our tiers that is not under that name
is renamed, so a row filed before Patch 638, or a name a sign-in changed, is
caught by the next pass and not only a change this pass saw itself.  An
imported row keeps the name its board published.  The lobby reads the name at
the player's next connect.

Needs SURFD_STEAM_KEY, read here and never printed.  Without --go it says what
it would do and writes nothing.  Steam not answering is one line and exit 0:
cron tries again in half an hour, and a stale name is not an emergency.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import accounts          # noqa: E402
import steam             # noqa: E402
import surfd as S        # noqa: E402  -- import-safe: app.run is __main__-guarded

BATCH = 50               # a reply of 100 summaries can pass steam.HTTP_LIMIT
# What is wrong with a REPLY, and so with these ids, not with Steam: asking the
# same fifty again in half an hour gets the same answer, and the accounts
# behind them would never be asked.
_BAD_REPLY = ("oversized reply", "unreadable profile reply")


def ask(key, ids, http, out):
    """{steamid: summary} for `ids`, or None when Steam cannot be reached.  A
    reply that cannot be read is asked again one id at a time."""
    try:
        return steam.summaries(key, ids, http)
    except steam.Unavailable as exc:
        if str(exc) not in _BAD_REPLY:
            out("steam did not answer (%s)" % exc)
            return None
        if len(ids) == 1:
            out("steam's reply for one account could not be read; skipped")
            return {}
    got = {}
    for sid in ids:
        one = ask(key, [sid], http, out)
        if one is None:
            return None
        got.update(one)
    return got


def sync(conn, key, http, go, limit, out=print):
    """-> (accounts asked, accounts whose name changed, rows renamed).  `http`
    is steam.http, or a test's.  A dry run counts what it would do."""
    ids = [r[0] for r in conn.execute(
        "SELECT steamid FROM accounts ORDER BY seen_at DESC, steamid LIMIT ?", (limit,))]
    asked = renamed = rows = 0
    for at in range(0, len(ids), BATCH):
        chunk = ids[at:at + BATCH]
        got = ask(key, chunk, http, out)
        if got is None:
            break
        asked += len(chunk)
        for sid in chunk:
            p = got.get(sid)
            if not p or not p["name"]:
                continue                # Steam knows nothing, or a blank: keep what we have
            old = conn.execute("SELECT name, avatar FROM accounts WHERE steamid = ?",
                               (sid,)).fetchone()
            if old is None:
                continue
            avatar = p["avatar"] or old[1]      # a reply with no picture is not "no picture"
            if (old[0], old[1]) == (p["name"], avatar):
                continue
            renamed += accounts.game_name(old[0]) != accounts.game_name(p["name"])
            if go:
                with conn:
                    conn.execute("UPDATE accounts SET name = ?, avatar = ? WHERE steamid = ?",
                                 (p["name"], avatar, sid))
    # The rows follow the account.  Only a name a game can show: one that
    # cleans to nothing would relabel a player's history "player".
    not_imported = "tier NOT IN (%s)" % ", ".join("'%s'" % t for t in S.TIERS_IMPORTED)
    where = " WHERE player = ? AND " + not_imported + " AND name <> ?"
    for sid, raw in conn.execute("SELECT steamid, name FROM accounts WHERE name <> ''").fetchall():
        if not accounts.account_named(raw):
            continue
        new = accounts.game_name(raw)
        if not go:
            rows += conn.execute("SELECT COUNT(*) FROM runs" + where, (sid, new)).fetchone()[0]
            continue
        with conn:
            rows += conn.execute("UPDATE runs SET name = ?" + where, (new, sid, new)).rowcount
            conn.execute("UPDATE replays SET name = ?" + where
                         + " AND kind IN ('run', 'evidence')", (new, sid, new))
            # An evidence row has no tier of ours to test (it is ''), and '' is
            # not an imported tier, so the one statement covers both kinds.
    return asked, renamed, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--go", action="store_true", help="write (default: a dry run)")
    ap.add_argument("--max", type=int, default=2000, help="accounts a run, newest seen first")
    a = ap.parse_args()
    key = (S.setting("SURFD_STEAM_KEY") or "").strip()
    if not key:
        print("no SURFD_STEAM_KEY: names are not refreshed")
        return 0
    conn = S.connect()
    try:
        asked, renamed, rows = sync(conn, key, steam.http, a.go, max(1, a.max))
    finally:
        conn.close()
    print("%s steamsync: %d accounts asked, %d names changed, %d board rows renamed%s"
          % (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), asked, renamed, rows,
             "" if a.go else " (DRY RUN)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
