#!/usr/bin/env python3
"""steamsync.py -- keep each account's Steam name and picture current.

    python3 steamsync.py [--go] [--max N]            (cron, every half hour)

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

Needs SURFD_STEAM_KEY, read here and never printed.  Without --go it says what
it would do and writes nothing.  Steam not answering is one line and exit 0:
cron tries again in half an hour, and a stale name is not an emergency.
"""
import argparse
import io
import os
import re
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
    """A picture as the game reads it: a header line, then one line of RGBA
    hex a row.  None when Pillow is not on this box, or these bytes are not a
    picture it will open."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(io.BytesIO(jpeg))
        if max(img.size) > 1024:
            return None
        img = img.convert("RGBA").resize((GAME_PX, GAME_PX), Image.LANCZOS)
    except Exception:           # Pillow raises its own family, and OSError
        return None
    px, row = img.tobytes(), GAME_PX * 4
    return ("FTESURF-AVATAR 1 %d %d\n" % (GAME_PX, GAME_PX)
            + "".join(px[y * row:(y + 1) * row].hex() + "\n" for y in range(GAME_PX)))


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


def pictures(conn, http, go, out=print, directory=None, now=None):
    """Fetch the pictures not yet on disk and make their game copies.
    -> (pictures wanted, fetched, game copies made, files pruned).  A dry run
    counts the first three.

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
    fetched = made = 0
    for h in hashes:
        base = os.path.join(directory, h)
        jpg, txt, bad = base + ".jpg", base + ".txt", base + ".bad"
        try:
            have_jpg, have_txt = os.path.isfile(jpg), os.path.isfile(txt)
            if have_jpg and (have_txt or not pillow):
                continue
            if os.path.isfile(bad) and 0 <= now - os.path.getmtime(bad) < BAD_RETRY:
                continue
            if not go:
                fetched += not have_jpg
                made += pillow and not have_txt
                continue
            if have_jpg:
                with open(jpg, "rb") as fh:
                    data = fh.read()
            else:
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
    return len(hashes), fetched, made, prune(directory, set(hashes)) if go else 0


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
        want, fetched, made, pruned = pictures(conn, steam.http, a.go)
    finally:
        conn.close()
    print("%s steamsync: %d accounts asked, %d names changed, %d board rows renamed;"
          " %d pictures, %d fetched, %d game copies made, %d old files removed%s"
          % (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), asked, renamed, rows,
             want, fetched, made, pruned, "" if a.go else " (DRY RUN)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
