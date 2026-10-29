#!/usr/bin/env python3
"""steamsync.py -- keep each account's Steam name and picture current.

    python3 steamsync.py [--go] [--max N] [--people N] [--pictures N]   (cron, every half hour)

A linked player's name in the game and on the boards is their Steam name
(Patch 638).  Signing in stored it once; this asks Steam again, fifty accounts
a request.  THEN THE ROWS FOLLOW THE ACCOUNT, whoever wrote its name: every
row and recording of a named account on our tiers that is not under that name
is renamed, so a row filed before Patch 638, or a name a sign-in changed, is
caught by the next pass and not only a change this pass saw itself.  An
imported row keeps the name its board published.  The lobby reads the name at
the player's next connect.

THEN THE PICTURES (Patch 639): for every unbanned account's avatar hash not
yet under surfd's AVATAR_DIR, Steam's 64 px JPEG is fetched and kept as
<hash>.jpg (the site's), and a 32 x 32 RGBA copy is written as text,
<hash>.txt (the game's: it can fetch text and upload pixels).  A changed
picture is a new hash, so a kept one is never fetched again, and the files
of a hash no unbanned account names are removed.  The text form needs
Pillow; without it the site still has its pictures.

AND THE PEOPLE ON THE IMPORTED BOARDS (Patch 660): a Momentum or KSF row's
player is a SteamID that is nobody's account here.  Once a day the boards are
read for SteamIDs not yet known (table `boardpics`); each run asks Steam about
`--people` of them, the never-asked first and then whoever was asked longest
ago, none twice in a day; and their pictures are fetched with the accounts',
`--pictures` a run, so the first fill of tens of thousands is spread over a
day of runs and a changed picture is on the boards within a day and a half.

Needs SURFD_STEAM_KEY, read here and never printed.  Without --go it says what
it would do and writes nothing.  Steam not answering is one line and exit 0:
cron tries again in half an hour, and a stale name is not an emergency.
"""
import argparse
import os
import re
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import accounts          # noqa: E402
import ksfprofile        # noqa: E402
import momprofile        # noqa: E402
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


PICTURE_URL = "https://avatars.steamstatic.com/%s_medium.jpg"
GAME_PX = 32             # the game's copy: 32 x 32, 8,192 hex characters
BAD_RETRY = 86400        # s before a picture that could not be kept is asked for again
_OURS = re.compile(r"[0-9a-f]{40}\.(jpg|txt|bad)")


def have_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def game_form(jpeg):
    """Keep the legacy on-disk copy at 32px; the API also derives 64px."""
    return steam.game_form(jpeg, GAME_PX)


def _write(path, data):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


_NOT_THIS_ONE = (301, 302, 303, 307, 308, 400, 403, 404, 410)


def _refused(exc):
    """True when the host answered and would not give THIS picture (a
    redirect, a not-found, a body too big to be one): that hash is marked and
    the pass goes on.  Anything else, a 429 and a 5xx included, is the host,
    and ends the pass with nothing marked.  Taken for one another, one
    refused hash ended every pass at itself."""
    text = str(exc)
    if text == "oversized reply":
        return True
    if text.startswith("status "):
        try:
            return int(text[7:]) in _NOT_THIS_ONE
        except ValueError:
            return False
    return False


def prune(directory, keep):
    """Delete this tool's files for hashes no unbanned account names any more
    (a changed picture, a banned account).  Only names of its own shape."""
    gone = 0
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    for name in names:
        if _OURS.fullmatch(name) and name[:40] not in keep:
            try:
                os.remove(os.path.join(directory, name))
                gone += 1
            except OSError:
                pass
    return gone


def has_table(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'"
                        " AND name = 'boardpics'").fetchone() is not None


def board_hashes(conn):
    """(the picture hashes people() stored for the imported rows' players, and
    whether every such player has been asked about at least once).  A database
    with no such table yet has none and nobody to ask.  A READ THAT FAILS IS
    NOT "NO HASHES": it raises, because what the caller does with an empty set
    is delete every file it does not name."""
    if not has_table(conn):
        return set(), True
    hashes = {r[0] for r in conn.execute("SELECT DISTINCT avatar FROM boardpics WHERE avatar <> ''")
              if accounts.avatar_ok(r[0])}
    unasked = conn.execute("SELECT 1 FROM boardpics WHERE asked_at = 0 LIMIT 1").fetchone()
    return hashes, unasked is None


def changed(directory, now):
    """Tell surfd the imported players' part moved: it rebuilds its table of
    them when this file's time does (surfd._board_avatars), and not otherwise."""
    stamp = os.path.join(directory, S.BOARD_STAMP)
    os.makedirs(directory, exist_ok=True)
    _write(stamp, b"")
    os.utime(stamp, (now, now))


def pictures(conn, http, go, out=print, directory=None, now=None, budget=None):
    """Fetch the pictures not yet on disk and make their game copies.
    -> (pictures wanted, fetched, game copies made, files pruned).  A dry run
    counts the first three.

    THE ACCOUNTS' FIRST, then the imported rows' players' (Patch 660), and no
    more than `budget` asked for a run (None: all): there are tens of thousands
    of the second kind, and the run after this one is half an hour away.

    KEPT ONLY ONCE PILLOW HAS OPENED IT (where there is a Pillow): a body cut
    short on the way has the right first bytes, and kept, it was served to
    the site for good with no game copy ever made.  What is not kept leaves a
    marker, <hash>.bad, and is asked for again after BAD_RETRY."""
    directory = directory or S.AVATAR_DIR
    now = time.time() if now is None else now
    pillow = have_pillow()
    hashes = sorted({r[0] for r in conn.execute(
        "SELECT avatar FROM accounts WHERE avatar <> '' AND banned_at = 0")
        if accounts.avatar_ok(r[0])})
    board, all_asked = board_hashes(conn)
    hashes += sorted(board - set(hashes))
    # One listing in place of two or three stats a hash: most are complete.
    try:
        there = set(os.listdir(directory))
    except OSError:
        there = set()
    fetched = made = asks = 0
    for h in hashes:
        base = os.path.join(directory, h)
        jpg, txt, bad = base + ".jpg", base + ".txt", base + ".bad"
        try:
            have_jpg, have_txt = h + ".jpg" in there, h + ".txt" in there
            if have_jpg and (have_txt or not pillow):
                continue
            if os.path.isfile(bad) and 0 <= now - os.path.getmtime(bad) < BAD_RETRY:
                continue
            # By what was ASKED of the host, not by what it gave: a thousand
            # pictures it will not give are a thousand requests too.  A picture
            # already here that only wants its game copy costs no request.
            if not have_jpg and budget is not None and asks >= budget:
                continue
            if not go:
                fetched += not have_jpg
                asks += not have_jpg
                made += pillow and not have_txt
                continue
            if have_jpg:
                with open(jpg, "rb") as fh:
                    data = fh.read()
            else:
                asks += 1
                try:
                    data = http(PICTURE_URL % h)
                except steam.Unavailable as exc:
                    if not _refused(exc):
                        out("steam's picture host did not answer (%s); %d fetched"
                            % (exc, fetched))
                        break
                    data = b""
            form = game_form(data) if pillow else None
            os.makedirs(directory, exist_ok=True)
            if data[:3] != b"\xff\xd8\xff" or (pillow and form is None):
                _write(bad, b"")
                os.utime(bad, (now, now))
                if have_jpg:
                    os.remove(jpg)
                out("a picture that could not be had, or that is not one, was not kept")
                continue
            if not have_jpg:
                _write(jpg, data)
                fetched += 1
            if form is not None:
                _write(txt, form.encode("ascii"))
                made += 1
            if os.path.isfile(bad):
                os.remove(bad)
        except OSError as exc:
            # One picture's file trouble is not the next one's.
            out("a picture's files could not be read or written (%s)" % type(exc).__name__)
    # NOTHING IS PRUNED WHILE AN IMPORTED PLAYER HAS NEVER BEEN ASKED ABOUT: until
    # then their picture's hash is not known, and its files would read as
    # nobody's (a database restored beside a kept directory; the first fill).
    pruned = prune(directory, set(hashes)) if go and all_asked else 0
    if go and (fetched or made or pruned):
        changed(directory, now)
    return len(hashes), fetched, made, pruned


PEOPLE_AGAIN = 86400     # s before a board player is asked about again
PEOPLE_SCAN = 86400      # s between reads of the boards for players not yet known
_SCANNED = "people.at"   # in the pictures' directory: its mtime is the last read
# `+player`: without it the planner walks runs_player with a table lookup a row
# for `tier`.  On the Pi's 3.2 million rows, 11 Oct 2026: 35.1 s that way, 11.4 s
# along the primary key's index, which holds both columns (67,259 players).
# test_ranked.py holds the plan.
PEOPLE_SQL = ("SELECT DISTINCT +player FROM runs WHERE tier IN (%s) AND length(player) = 17"
              " AND +player GLOB '7656119[0-9]*'")
# steam.py gives a profile 1.5 s, which is a sign-in's patience: a player is
# waiting.  Nobody waits for this pass, and its first live run ended at the
# fourth batch of a hundred on that clock (11 Oct 2026; the next run's hundred
# all answered).
PEOPLE_TIMEOUT = 10


def patient(http):
    """`http`, given PEOPLE_TIMEOUT whatever its caller asks for."""
    def get(url, data=None, timeout=None):
        return http(url, data, timeout=PEOPLE_TIMEOUT)
    return get


def people(conn, key, http, go, limit, out=print, directory=None, now=None):
    """Patch 660: Steam's picture for each player of an imported row.
    -> (players known, new this run, asked, pictures that changed).  A dry run
    counts who it would ask, asks Steam nothing and writes nothing.

    WHO: every SteamID64 that is `player` of a Momentum or KSF row.  Reading
    them out is a pass over every imported row, so it is done once a
    PEOPLE_SCAN (and whenever the table is empty) and the answer kept in
    `boardpics`: a row imported since is a day late, like its player's picture
    would be anyway, and a player no longer on any board is forgotten then.
    ASKED: `limit` of them a run (0: nothing at all is done), the never-asked
    first, then the longest ago, and nobody again within PEOPLE_AGAIN.  An id
    Steam says nothing of is still marked asked: it would otherwise head every
    run's list for ever.  A reply with no picture keeps the one we have, as
    for an account.  A database another writer holds ends the pass in one
    line; what it had written stays."""
    directory = directory or S.AVATAR_DIR
    now = time.time() if now is None else now
    limit = max(0, limit)
    if not limit:
        return 0, 0, 0, 0
    stamp = os.path.join(directory, _SCANNED)
    table = has_table(conn)
    if not table and go:
        with conn:                          # the service has not been restarted onto it yet
            conn.execute(S.BOARDPICS_DDL)
        table = True
    have = {r[0] for r in conn.execute("SELECT steamid FROM boardpics")} if table else set()
    try:
        due = not 0 <= now - os.path.getmtime(stamp) < PEOPLE_SCAN
    except OSError:
        due = True
    new = moved = 0
    fresh = []
    if due or not have:
        tiers = ", ".join("'%s'" % t for t in S.TIERS_IMPORTED)
        ids = {r[0] for r in conn.execute(PEOPLE_SQL % tiers) if steam.is_steamid64(r[0])}
        fresh = sorted(ids - have)
        gone = sorted(have - ids)
        new = len(fresh)
        if go:
            try:
                with conn:
                    conn.executemany("INSERT OR IGNORE INTO boardpics (steamid) VALUES (?)",
                                     [(sid,) for sid in fresh])
                    conn.executemany("DELETE FROM boardpics WHERE steamid = ?",
                                     [(sid,) for sid in gone])
            except sqlite3.OperationalError as exc:
                out("the database was busy (%s); the boards' players were not read in" % exc)
                return len(have), 0, 0, 0
            os.makedirs(directory, exist_ok=True)
            _write(stamp, b"")
            os.utime(stamp, (now, now))
            moved = len(fresh) + len(gone)
    if not table:
        return new, new, min(limit, new), 0     # a dry run before the table: all of them are new
    known = conn.execute("SELECT COUNT(*) FROM boardpics").fetchone()[0] + (0 if go else new)
    ids = [r[0] for r in conn.execute(
        "SELECT steamid FROM boardpics WHERE asked_at <= ? ORDER BY asked_at, steamid LIMIT ?",
        (int(now) - PEOPLE_AGAIN, limit))]
    if not go:
        # The never-asked go first, and the ones this run would have added are
        # never-asked: an estimate in the real order's spirit, not its letter.
        return known, new, min(limit, len(ids) + len(fresh)), 0
    asked = differ = 0
    for at in range(0, len(ids), BATCH):
        chunk = ids[at:at + BATCH]
        got = ask(key, chunk, patient(http), out)
        if got is None:
            break
        try:
            with conn:
                for sid in chunk:
                    p = got.get(sid)
                    if p and p["avatar"]:
                        differ += conn.execute(
                            "UPDATE boardpics SET avatar = ? WHERE steamid = ? AND avatar <> ?",
                            (p["avatar"], sid, p["avatar"])).rowcount
                    conn.execute("UPDATE boardpics SET asked_at = ? WHERE steamid = ?",
                                 (int(now), sid))
        except sqlite3.OperationalError as exc:
            out("the database was busy (%s); %d asked about" % (exc, asked))
            break
        asked += len(chunk)
    if moved or differ:
        changed(directory, now)
    return known, new, asked, differ


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


def requeue(conn, now, go):
    """P1117: every unbanned account's KSF and Momentum walks, queued again once
    their last walk is a day old (each enqueue keeps its own TTL and cap).
    -> walks queued (a dry run: walks due)."""
    n = 0
    for (sid,) in conn.execute("SELECT steamid FROM accounts WHERE banned_at = 0"
                               " ORDER BY steamid").fetchall():
        for walk in (ksfprofile, momprofile):
            st = walk.status(conn, sid)
            due = (st["state"] not in ("queued", "partial")
                   and now - st.get("updated", 0) >= walk.TTL)
            if due and go:
                state = walk.enqueue(conn, sid, now).get("state")
                if state == "busy":
                    print("%s busy: %s not queued again" % (walk.__name__, sid))
                due = state == "queued"
            n += due
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--go", action="store_true", help="write (default: a dry run)")
    ap.add_argument("--max", type=int, default=2000, help="accounts a run, newest seen first")
    ap.add_argument("--people", type=int, default=5000,
                    help="players of imported rows asked about a run (0: none)")
    ap.add_argument("--pictures", type=int, default=1500, help="pictures fetched a run")
    a = ap.parse_args()
    conn = S.connect()
    try:
        print("%d account walk(s) queued again (KSF, Momentum)" % requeue(
            conn, int(time.time()), a.go))
    except sqlite3.Error as exc:
        print("account walks not queued this run: the database said %s" % exc)
    finally:
        conn.close()
    key = (S.setting("SURFD_STEAM_KEY") or "").strip()
    if not key:
        print("no SURFD_STEAM_KEY: names are not refreshed")
        return 0
    conn = S.connect()
    known = new = pasked = pchanged = want = fetched = made = pruned = 0
    try:
        asked, renamed, rows = sync(conn, key, steam.http, a.go, max(1, a.max))
        try:
            known, new, pasked, pchanged = people(conn, key, steam.http, a.go, max(0, a.people))
            want, fetched, made, pruned = pictures(conn, steam.http, a.go,
                                                   budget=max(0, a.pictures))
        except sqlite3.Error as exc:
            # Nothing is pruned on a read that failed: see board_hashes.
            print("the pictures were not done this run: the database said %s" % exc)
    finally:
        conn.close()
    print("%s steamsync: %d accounts asked, %d names changed, %d board rows renamed;"
          " %d board players known, %d new, %d asked, %d pictures changed;"
          " %d pictures, %d fetched, %d game copies made, %d old files removed%s"
          % (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), asked, renamed, rows,
             known, new, pasked, pchanged,
             want, fetched, made, pruned, "" if a.go else " (DRY RUN)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
