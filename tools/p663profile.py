#!/usr/bin/env python3
"""p663profile.py -- hud_player as a profile: its two pages, the player search, the board's field.

    python tools/p663profile.py --progs <build dir> --output-dir <owned dir>

p615link's rig: a surfd in this process with a board of its own (rows put
straight into its database, and a difficulty catalogue), a lobby, one client
whose leaderboard address is that surfd and whose consent file says online.
Graded on what the panel says of itself (`hud_player status`, a console print,
and its developer lines) against what was put in the database and on what
that surfd was asked; a screenshot of every state is kept in --output-dir:
LOOK AT THEM.  THE DESKTOP'S POINTER IS MOVED for each click and put back
(p653box's Mouse): a field's keyboard is a press on it, never a console line.

    --control   the build is the one tmp recipe in the patch's notes makes (five
                lines put back as they were before the review): X, K, U, G and Y fail

  O  the link offer is still up when the card opens: it is not drawn over the
     card, and Enter in the search is the search's, not a link's
  C  the panel opens on Customize and draws
  S  `hud_player stats`: this player is not linked, so there is no breakdown to ask for
  X  a click on the first trail colour sets it and stays on Customize
  F  `hud_player find zed`: the search answers with the three players of that name,
     the one whose name IS the text first
  K  ...and that console line gave the field NO keyboard: a bound key still runs
  E  a click on the field, then Enter, takes the first: the breakdown is theirs
  D  Patch 666: a click on a difficulty tier's bar lists that tier's maps for
     the player on show, the finished ones first with their times; the bar
     again gives the results back; the unrated come a page at a time; the
     tier stays on show for the next player; a card opened again is on results
  V  `hud_player view <8-hex mark>` finds a player by the game's own mark
  M  a wide profile: fifty rows at first, and the rest when the list is scrolled
  G  a page that brings nothing, and a page that fails: asked for once, and three
     times two seconds apart, never in a loop
  T  keys typed into the search field are text (posted, as a keyboard's), and a
     game bind on one of them does not run
  U  a key held BEFORE the field took the keyboard is let go of: its bind's
     release runs
  N  a handle nobody has: said so, and nothing is asked again
  W  a name that is no handle is not asked about at all
  B  the board: `scores find cap` on a pinned board lists players
  H  Patch 666: a click on the field and Enter shows the first one's times on
     THIS MAP in the board's table's place (the board stays, no card opens);
     a time's row opens the board of its leg; "Whole profile" closes the
     board and opens the card on that player
  Y  letting go of the scoreboard key while that field has the keyboard leaves
     the board up
  P  a player whose picture surfd holds: it is drawn in the search's list, and
     at the head of their breakdown at twice the size (a four-colour picture,
     found in the screenshots by its colours)
  L  this player links (a browser signs in, the number is typed): the lobby
     says linked, and the Stats page is their own breakdown, by the lobby's mark
  R  the linked account has a picture: the room list beside the board draws it
     (Patch 653's 26 px), and the card's head at about twice that
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time

import p615link as L
import p640pics as PIC
from p653box import Mouse

ZED, ZEDDER, THEZED, WIDE = ("76561198000008003", "76561198000008002", "76561198000008001",
                             "76561198000008010")
LIAR, FAILER = "76561198000008020", "76561198000008021"
ASKS = []                       # every player= ask this rig's surfd got: (who, offset)


def handle(player):
    return hashlib.sha256(player.encode("ascii")).hexdigest()[:12]


def seed(db, here):
    """The board this arm reads (`here` is the rig's own map): -> rows per player."""
    now = int(time.time())
    conn = sqlite3.connect(str(db))
    rows = []

    def run(mp, player, name, ms, tier="momentum", track=0, leg=0, days=3):
        rows.append((mp, track, leg, tier, player, name, ms // 10, ms, "i-" + player, now - days * 86400))

    run("surf_utopia_v3", ZED, "^2zed", 61234)
    run("surf_utopia_v3", ZEDDER, "Zedder", 60000)
    run("surf_utopia_v3", THEZED, "the zed", 75000)
    run("surf_utopia_v3", ZED, "^2zed", 12345, track=1)
    run("surf_utopia_v3", ZED, "^2zed", 9876, leg=2)
    run("surf_beginner", ZED, "^2zed", 45500, days=400)
    run("surf_beginner", ZEDDER, "Zedder", 47000)
    run("surf_kitsune", ZED, "^2zed", 180250, tier="ksf", days=1)
    run("surf_kitsune", ZEDDER, "Zedder", 150000, tier="ksf")
    run(here, ZED, "^2zed", 31000)          # Patch 666: three legs of the map this rig is on
    run(here, ZED, "^2zed", 8000, leg=1)
    run(here, ZED, "^2zed", 12000, track=1)
    for k in range(14):
        run("surf_beginner", "765611980000090%02d" % k, "cap%02d" % k, 50000 + k * 100)
    for k in range(120):                    # a wide profile: one row a map
        run("surf_wide%03d" % k, WIDE, "Wide Load", 30000 + k * 10)
    for mp in ("surf_utopia_v3", "surf_beginner", "surf_kitsune"):    # the account this game will link to
        run(mp, L.SIDS[0], "Linked One", 90000, tier="ranked")
    for k in range(60):                     # two profiles of sixty rows, for lie() below
        run("surf_liar%03d" % k, LIAR, "Liar", 40000 + k * 10)
        run("surf_fail%03d" % k, FAILER, "Failer", 40000 + k * 10)
    conn.executemany(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
        " flags, node, runid, submitted, replay_id) VALUES (?,?,?,?,'clean',?,?,?,100.0,?,0,'import',?,?,0)",
        rows)
    conn.commit()
    conn.close()
    return {p: sum(1 for r in rows if r[4] == p) for p in (ZED, ZEDDER, THEZED, WIDE, L.SIDS[0])}


def lie():
    """This rig's surfd counts its player= asks, says LIAR has 400 rows (it has
    sixty: the page after them brings none), and fails FAILER's every next page."""
    import sys
    from flask import request
    S = sys.modules["surfd"]
    real = S.game_player

    def lying(raw, now):
        offset = S.clamp_int(request.args.get("offset"), 0, 100000, 0)
        ASKS.append((raw, offset))
        if raw == handle(FAILER) and offset:
            return S.fail(500, "storage error")
        resp = real(raw, now)
        if raw == handle(LIAR) and resp.status_code == 200:
            body = json.loads(resp.get_data(as_text=True))
            body["total"] = 400
            return S.Response(S.game_json(body), status=200, mimetype="application/json")
        return resp
    S.game_player = lying


def plant_picture(db, steamid):
    """surfd holds the four-colour picture for an imported player, as steamsync would have kept it."""
    import os
    import sys
    import steamsync
    S = sys.modules["surfd"]
    jpeg = PIC.picture()
    os.makedirs(S.AVATAR_DIR, exist_ok=True)
    with open(os.path.join(S.AVATAR_DIR, PIC.HASH + ".jpg"), "wb") as fh:
        fh.write(jpeg)
    with open(os.path.join(S.AVATAR_DIR, PIC.HASH + ".txt"), "w", newline="\n") as fh:
        fh.write(steamsync.game_form(jpeg))
    conn = sqlite3.connect(str(db))
    conn.execute(S.BOARDPICS_DDL)
    conn.execute("INSERT OR REPLACE INTO boardpics (steamid, avatar, asked_at) VALUES (?, ?, ?)",
                 (steamid, PIC.HASH, int(time.time())))
    conn.commit()
    conn.close()
    S.board_avatars_reset()
    S.avatars_reset()


def account_picture(db, steamid):
    """...and for a linked account (the files are plant_picture's)."""
    import sys
    S = sys.modules["surfd"]
    conn = sqlite3.connect(str(db))
    n = conn.execute("UPDATE accounts SET avatar = ? WHERE steamid = ?", (PIC.HASH, steamid)).rowcount
    conn.commit()
    conn.close()
    S.avatars_reset()
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--server", type=pathlib.Path, default=pathlib.Path("C:/FTEQuake/fteqwsv64.exe"))
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    ap.add_argument("--control", action="store_true")
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    a.foreign_code = a.refuse_address = a.taken = a.receipt = False

    rig, gd, junctions = L.build_rig(a)
    print("rig", rig)
    (gd / "data").mkdir(exist_ok=True)
    # The online tier the game asks for now: at 4, what this was written with, every ask
    # says "accept the terms".
    online = re.search(r"#define FS_TERMS_ONLINE (\d+)",
                       (pathlib.Path(__file__).resolve().parents[1] / "src/shared/sh_defs.qc").read_text()).group(1)
    (gd / "data" / "consent.txt").write_text("FTESURF-CONSENT 1\nversion %s\naccepted 20261012-000000\n" % online)
    server = client = web = mouse = None
    try:
        gport = None
        for cand in range(27661, 27680):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.bind(("127.0.0.1", cand))
                    gport = cand
                    break
                except OSError:
                    continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            hport = probe.getsockname()[1]
        a.hport = hport
        tsv = rig / "momtracks.tsv"
        tsv.write_text("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n"
                       "surf_utopia_v3\t1\t1\t1\t0\t1\nsurf_beginner\t2\t1\t1\t0\t1\n"
                       "surf_kitsune\t3\t2\t1\t0\t1\n"
                       + "".join("surf_wide%03d\t%d\t%d\t1\t0\t1\n" % (k, 10 + k, 1 + k % 6) for k in range(120)))
        import os
        os.environ["SURFD_MOMTRACKS"] = str(tsv)
        web, db = L.start_surfd(rig, hport, "127.0.0.1")
        have = seed(db, a.map)
        plant_picture(db, ZED)
        # What surfd itself says of the unrated, for D (its own checks are test_web.py's).
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/board?player=%s&ct=u&limit=1"
                                    % (hport, handle(ZED)), timeout=20) as r:
            unrated = json.loads(r.read().decode("utf-8"))
        print("  surfd: %d unrated maps for zed, %d finished" % (unrated["total"], unrated["done"]))
        lie()
        common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                  "+set", "cfg_save_auto", "0", "+set", "log_enable", "1", "+set", "log_dir", "logs"]
        server = subprocess.Popen(
            [str(a.server), *common, "+set", "log_name", "p663sv", "+set", "developer", "1",
             "+set", "sv_public", "0", "+set", "sv_port", str(gport),
             "+set", "sv_guidkey", "p663-probe", "+set", "sv_maxrate", "0",
             "+set", "sv_maxdownloadrate", "0",
             "+set", "lobby_master", "http://127.0.0.1:%d" % hport,
             "+set", "lobby_master_key", L.KEY, "+set", "lobby_master_rate", "30",
             "+map", a.map], cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        if server.poll() is not None:
            raise RuntimeError("the server exited at start (code %s)" % server.returncode)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4
        client = subprocess.Popen(
            [str(a.client), "-plugin", "-nobrowse", *common, "+set", "log_name", "p663cl",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "100", "+set", "rate", "2000000", "+set", "drate", "5000000",
             "+set", "lobby_dir", "http://127.0.0.1:%d" % hport,
             "+set", "developer", "1", "+set", "log_developer", "1"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)

        def send(line, wait=0.4):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()
            time.sleep(wait)

        def shot(name):
            send("screenshot " + name, 0)
            end = time.time() + 15
            while time.time() < end:
                found = list((gd / "screenshots").glob(name + ".*"))
                if found:
                    time.sleep(0.8)
                    kept = a.output_dir / (name + found[0].suffix)
                    shutil.copyfile(found[0], kept)
                    return kept
                time.sleep(0.5)
            return None

        cl = L.Log(gd / "logs/p663cl.log")
        time.sleep(8)
        up = None
        for _ in range(3):
            send("connect 127.0.0.1:%d" % gport)
            up = cl.wait("FTESurf CSQC loaded", 40)
            if up:
                break
        L.check("the client connected and its game code loaded", bool(up), True)
        if not up:
            return 1
        send("closemenu")
        send("con_notifytime 0")
        send("con_notifylines 0")
        send("in_focusgrab 0")                  # a window that is not in front still reads the pointer
        keys = L.Keys(client.pid)
        mouse = Mouse(keys)
        cl.wait("press Enter to link your Steam account", 30)
        time.sleep(1.0)
        send('bind g "echo gamekey-g"')
        send('alias +p663h "echo held-down"')
        send('alias -p663h "echo held-up"')
        send("bind h +p663h")

        # 0 open, 1 page, 2 view, 3 breakdown, 4 of, 5 rows, 6 total, 7 search, 8 text, 9 found,
        # 10 lobby says, 11-14 the field's box, 15-16 its screen, 17 keys, 18 board, 19 trail,
        # 20-22 the first trail swatch
        ST = re.compile(r'hud_player: open (\d) page (\d) view "([^"]*)" breakdown (\d) of "([^"]*)" '
                        r'rows (\d+)/(\d+)  search (\d) of "([^"]*)" found (\d+)  lobby says (\d)'
                        r'  field (-?[\d.]+),(-?[\d.]+) ([\d.]+)x([\d.]+) on ([\d.]+)x([\d.]+) keys (\d)'
                        r'  board (\d)  trail (\S*) at (-?[\d.]+),(-?[\d.]+) ([\d.]+)')

        def click(st, x, y):
            """A device click at a point of the game's own screen (`st` says how big that is)."""
            mouse.click(x * mouse.size[0] / float(st[15]), y * mouse.size[1] / float(st[16]))
            time.sleep(0.4)

        def click_field():
            st = status()
            click(st, float(st[11]) + float(st[13]) * 0.5, float(st[12]) + float(st[14]) * 0.5)
            return status()

        def status(wait=0.3):
            n = cl.text().count("hud_player: open ")
            send("hud_player status", wait)
            cl.count("hud_player: open ", n + 1, 5)
            m = ST.findall(cl.text())
            return m[-1] if m else None

        def until(test, timeout=12):
            end = time.time() + timeout
            st = status()
            while time.time() < end and not (st and test(st)):
                time.sleep(0.5)
                st = status()
            return st

        # O: the offer that came up by itself is still up (it stays forty seconds).
        send("hud_player open", 1.0)
        shot("p663_0_offer_and_card")
        send("hud_player find zed", 0.5)
        until(lambda s: s[7] == "2")
        click_field()
        keys.press("enter")
        st = until(lambda s: s[3] == "2", 8)
        L.check("O  with the link offer still up, Enter in the search is the search's: that player's "
                "breakdown opens, and no link is started",
                (st and st[2], cl.text().count("sign in at")), (handle(ZED), 0))
        keys.press("esc")                       # back to this player...
        time.sleep(0.3)
        keys.press("esc")                       # ...the card closed...
        time.sleep(0.6)
        keys.press("esc")                       # ...and the offer, which is the keys' again: later
        time.sleep(0.6)
        L.check("O  with the card closed the offer takes Esc again",
                cl.text().count("not linked. Type"), 1)

        send("hud_player open", 1.0)
        st = status()
        L.check("C  the panel opens on Customize, on this player, and draws",
                (st and st[:3], bool(shot("p663_1_customize"))), (("1", "0", ""), True))
        click(st, float(st[20]) + float(st[22]) * 0.5, float(st[21]) + float(st[22]) * 0.5)
        time.sleep(0.6)
        after = status()
        L.check("X  a click on the first trail colour sets it, and the page is still Customize",
                (st[19], after and (after[1], after[19])), ("", ("0", "1")))
        asked = len(ASKS)
        send("hud_player stats", 1.5)
        st = status()
        L.check("S  the Stats page of a player who is not linked asks for nothing (the lobby gave no mark)",
                (st and st[:3], len(ASKS) - asked, bool(shot("p663_2_stats_unlinked"))), (("1", "1", ""), 0, True))

        send("hud_player find zed", 0.5)
        st = until(lambda s: s[7] == "2")
        first = re.findall(r'profile: search "zed" found (\d+), first (\w+)', cl.text())
        L.check("F  the search for zed answers three players, the one named exactly so first",
                (st and st[7:10], first[-1:]), (("2", "zed", "3"), [("3", handle(ZED))]))
        keys.type("g")
        time.sleep(0.4)
        st = status()
        L.check("K  that console line gave the field no keyboard: the bound key ran, the text stands",
                (st and (st[17], st[8]), cl.text().count("gamekey-g")), (("0", "zed"), 1))
        time.sleep(5.0)                         # a picture is asked for when its row first draws
        listed = shot("p663_3_search")
        st = click_field()
        keys.press("enter")
        took = st and st[17]
        st = until(lambda s: s[3] == "2")
        L.check("E  a click on the field gives it the keyboard, and Enter takes the first: the "
                "breakdown is theirs, every row of it",
                (took, st and st[1:7]),
                ("1", ("1", handle(ZED), "2", handle(ZED), str(have[ZED]), str(have[ZED]))))
        time.sleep(1.0)
        headed = shot("p663_4_breakdown")
        spans = []
        for img in (listed, headed):
            n, box, size = PIC.quadrants(img) if img else (0, None, None)
            spans.append((n > 0, (box[2] - box[0], box[3] - box[1]) if box else None))
            print("  the four-colour picture in %s: %d matches, their corners span %s of %s"
                  % (img and img.name, n, box, size))
        # A picture's top-left quadrant is half its side: its matching corners fill a little under that.
        L.check("P  that player's picture is in the list, and at the head of the breakdown about twice as big",
                (spans[0][0], spans[1][0],
                 bool(spans[0][1] and spans[1][1]) and 1.5 < spans[1][1][0] / max(1, spans[0][1][0]) < 2.6,
                 bool(spans[1][1]) and 16 <= spans[1][1][0] <= 24),
                (True, True, True, True))

        # D: a tier's maps.  0 the tier, 1 its answer, 2-3 maps held/of, 4 finished, 5-8 the first bar
        TR = re.compile(r'  tier "([^"]*)" (\d) maps (\d+)/(\d+) done (\d+)  bar (-?[\d.]+),(-?[\d.]+) '
                        r'([\d.]+)x([\d.]+)')
        SAID = re.compile(r"profile: tier (\S+) of (\w+): (\d+) maps of (\d+) held, (\d+) finished, "
                          r"first (\S+) (\d+)")

        def tier(test=None, timeout=12):
            end = time.time() + timeout
            while True:
                st = status()
                got = TR.findall(cl.text())
                t = got[-1] if got else None
                if st and t and (test is None or test(t)):
                    return st, t
                if time.time() > end:
                    return st, t
                time.sleep(0.5)

        st, t = tier()
        click(st, float(t[5]) + float(t[7]) * 0.5, float(t[6]) + float(t[8]) * 0.5)
        st, t = tier(lambda t: t[1] == "2")
        said = SAID.findall(cl.text())
        # Tier 1 is utopia, beginner and every sixth wide map: 22, of which zed has finished two.
        L.check("D  a click on the first tier's bar lists its maps for the player on show: all 22, "
                "the two finished first, the first of them with its time",
                (t and t[:5], said[-1:]),
                (("1", "2", "22", "22", "2"),
                 [("1", handle(ZED), "22", "22", "2", "surf_beginner", "45500")]))
        time.sleep(0.6)
        shot("p666_1_tier")
        click(st, float(t[5]) + float(t[7]) * 0.5, float(t[6]) + float(t[8]) * 0.5)
        st, t = tier(lambda t: t[0] == "", 5)
        L.check("D  ...and the bar again gives the results back", (t and t[0], st and st[5]),
                ("", str(have[ZED])))
        send("hud_player tier u", 0.5)
        st, t = tier(lambda t: t[1] == "2")
        first = t and t[:5]
        send("hud_player scroll 95", 0.5)
        st, t = tier(lambda t: t[2] == str(min(200, unrated["total"])))
        L.check("D  the unrated come a hundred at a time, the rest as the list is scrolled (surfd "
                "says %d, %d finished)" % (unrated["total"], unrated["done"]),
                (unrated["total"] > 100, first, t and t[:5]),
                (True, ("u", "2", "100", str(unrated["total"]), str(unrated["done"])),
                 ("u", "2", str(unrated["total"]), str(unrated["total"]), str(unrated["done"]))))
        shot("p666_2_unrated")
        send("hud_player tier 1", 0.5)
        tier(lambda t: t[0] == "1" and t[1] == "2")
        send("hud_player view " + handle(ZEDDER), 0.5)
        st, t = tier(lambda t: t[1] == "2" and SAID.findall(cl.text())[-1][1] == handle(ZEDDER))
        L.check("D  the tier stays on show for the next player: Zedder's tier 1, asked for after "
                "their breakdown landed",
                (st and st[4], t and t[:5], SAID.findall(cl.text())[-1]),
                (handle(ZEDDER), ("1", "2", "22", "22", "2"),
                 ("1", handle(ZEDDER), "22", "22", "2", "surf_beginner", "47000")))
        send("hud_player close", 0.5)
        send("hud_player view " + handle(ZED), 0.8)
        st, t = tier(lambda t: t[0] == "", 5)
        L.check("D  a card opened again is on the results", t and t[0], "")

        send("hud_player view " + handle(ZEDDER)[:8], 0.5)
        st = until(lambda s: s[3] == "2" and s[4] == handle(ZEDDER)[:8])
        said = re.findall(r"profile: (\w+) is (\w+), (\d+) times", cl.text())
        L.check("V  the game's 8-hex mark finds its player",
                (st and st[5:7], said[-1:]),
                ((str(have[ZEDDER]), str(have[ZEDDER])), [(handle(ZEDDER)[:8], handle(ZEDDER), str(have[ZEDDER]))]))

        send("hud_player view " + handle(WIDE), 0.5)
        st = until(lambda s: s[3] == "2" and s[4] == handle(WIDE))
        L.check("M  a wide profile: fifty rows of %d at first" % have[WIDE],
                st and st[5:7], ("50", str(have[WIDE])))
        shot("p663_5_wide")
        send("hud_player scroll 42", 0.5)
        st = until(lambda s: s[5] == "100")
        send("hud_player scroll 95", 0.5)
        st2 = until(lambda s: s[5] == str(have[WIDE]))
        L.check("M  ...and the rest as the list is scrolled toward its end, a page at a time",
                (st and st[5], st2 and st2[5]), ("100", str(have[WIDE])))

        send("hud_player view " + handle(LIAR), 0.5)
        st = until(lambda s: s[3] == "2" and s[4] == handle(LIAR))
        send("hud_player scroll 45", 0.5)
        mid = until(lambda s: s[5] == "60")
        send("hud_player scroll 58", 0.5)       # to the new end: the page after it brings nothing
        time.sleep(7.0)                         # the tail stays on screen
        st2 = status()
        liar = [o for w, o in ASKS if w == handle(LIAR)]
        send("hud_player view " + handle(FAILER), 0.5)
        until(lambda s: s[3] == "2" and s[4] == handle(FAILER))
        send("hud_player scroll 45", 0.5)
        time.sleep(9.0)
        st3 = status()
        failer = [o for w, o in ASKS if w == handle(FAILER) and o]
        print("  asks for the page after the liar's last row: %d; for the failer's next page: %d"
              % (liar.count(60), len(failer)))
        L.check("G  a page that brings nothing is asked for ONCE and ends the list (it said 400, "
                "has 60); a page that fails is asked for three times and no more",
                (st and st[5:7], mid and mid[5], liar.count(60), st2 and st2[5:7], len(failer),
                 st3 and st3[5:7]),
                (("50", "400"), "60", 1, ("60", "60"), 3, ("50", "60")))

        send("hud_player open", 0.3)
        st = click_field()                      # the field has the keyboard, empty: the top players
        st = until(lambda s: s[7] == "2" and s[8] == "")
        top = st and (st[9], st[17])
        was = cl.text().count("gamekey-g")
        keys.type("zeg")                        # g is bound; in the field it is a letter
        time.sleep(0.3)
        keys.press("back")
        st = until(lambda s: s[8] == "ze")
        L.check("T  keys typed into the field are its text (the list follows it), and a bind on one "
                "of them did not run",
                (top, st and st[7:10], cl.text().count("gamekey-g") - was), (("12", "1"), ("2", "ze", "3"), 0))
        shot("p663_6_typed")
        keys.press("esc")                       # leaves the field
        time.sleep(0.3)
        keys.type("g")
        time.sleep(0.4)
        L.check("T  CONTROL with the field left, the same key runs its bind",
                cl.text().count("gamekey-g") - was, 1)

        keys._post(0x48, True)                  # H goes down while the game still has the keys...
        time.sleep(0.3)
        st = click_field()                      # ...the field takes the keyboard...
        keys._post(0x48, False)                 # ...and H is let go
        time.sleep(0.5)
        downs, ups = cl.text().count("held-down"), cl.text().count("held-up")
        print("  log lines of the held key: %d of its press, %d of its release" % (downs, ups))
        L.check("U  a key held before the field took the keyboard: its bind's release still runs "
                "(as many log lines as its press made)",
                (downs > 0, st and st[17], ups == downs), (True, "1", True))
        keys.press("esc")
        time.sleep(0.3)

        send("hud_player view 000000000000", 0.5)
        st = until(lambda s: s[3] == "3" and s[4] == "000000000000")
        time.sleep(4.0)                         # past the one more ask a slow answer gets
        L.check("N  a handle nobody has: said so, with nothing held",
                status()[3:7], ("3", "000000000000", "0", "0"))
        shot("p663_7_nobody")
        send("hud_player view lex", 0.5)
        time.sleep(4.0)
        L.check("W  a name that is no handle is said to be nobody, and surfd is never asked",
                (status()[3:5], [w for w, _o in ASKS if w == "lex"]), (("3", "lex"), []))
        keys.press("esc")                       # back to this player
        time.sleep(0.3)
        keys.press("esc")                       # and closed
        time.sleep(0.5)
        L.check("ESC goes back to this player, then closes the panel", status()[:3], ("0", "1", ""))

        send("+showscores", 1.5)                # the scoreboard key held...
        shot("p666_3_held_board")               # LOOK: the field is there, and says what gives it a cursor
        send("scores open", 1.5)                # ...and the board pinned
        send("scores find cap", 0.5)
        st = until(lambda s: s[7] == "2" and s[8] == "cap")
        L.check("B  on a pinned board the search lists players (twelve of the fourteen caps), "
                "and has no keyboard by that",
                st and (st[0], st[7:10], st[17], st[18]), ("0", ("2", "cap", "12"), "0", "1"))
        shot("p663_8_board_search")
        st = click_field()
        send("-showscores", 0.8)                # the key let go, to type
        up = status()
        L.check("Y  letting go of the scoreboard key while the field has the keyboard leaves the board up",
                (st and st[17], up and (up[18], up[17])), ("1", ("1", "1")))
        # H: a picked player's times on this map.  0 who, 1 the answer, 2 times, 3-6 "Whole profile", 7-10 the first row
        ON = re.compile(r'  showing "(\w+)" on this map: answer (\d), (\d+) times  chip (-?[\d.]+),(-?[\d.]+) '
                        r'([\d.]+)x([\d.]+)  row (-?[\d.]+),(-?[\d.]+) ([\d.]+)x([\d.]+)')
        LEG = re.compile(r'scores: (\S+) on \S+  leg (\d+)/(\d+) "([^"]*)"')

        def board(test=None, timeout=10):
            """-> (the board's state and leg, the player it shows or None), as `scores status` prints them."""
            end = time.time() + timeout
            while True:
                n = cl.text().count("scores: ")
                send("scores status", 0.3)
                cl.count("scores: ", n + 1, 5)
                time.sleep(0.2)
                text = cl.text()
                legs = list(LEG.finditer(text))
                on = ON.findall(text[legs[-1].start():]) if legs else []
                got = (legs[-1].groups() if legs else None, on[-1] if on else None)
                if test is None or test(got) or time.time() > end:
                    return got
                time.sleep(0.4)

        cap0 = handle("76561198000009000")
        keys.press("enter")
        leg, on = board(lambda g: g[1] and g[1][1] == "2")
        st = status()
        L.check("H  Enter in the board's search shows the first one's times on this map, in the board: "
                "the board stays, no card opens, and this player has none here",
                (st and (st[0], st[18]), leg and leg[0], on and on[:3]), (("0", "1"), "pinned", (cap0, "2", "0")))
        shot("p666_4_on_nobody_here")
        send("scores on " + handle(ZED), 0.5)
        leg, on = board(lambda g: g[1] and g[1][0] == handle(ZED) and g[1][1] == "2")
        said = re.findall(r"profile: (\w+) on (\S+): (\d+) times, first leg (-?\d+)/(-?\d+) in (\d+)", cl.text())
        L.check("H  zed has three times on this map: every leg, the main track first",
                (on and on[:3], said[-1:]),
                ((handle(ZED), "2", "3"), [(handle(ZED), a.map, "3", "0", "0", "31000")]))
        time.sleep(4.0)                         # the picture is asked for when it first draws
        shot("p666_5_on_zed")
        send("+showscores", 0.4)                # the scoreboard key, pressed and let go...
        send("-showscores", 0.6)
        leg, on = board()
        L.check("H  ...a pinned board showing somebody's times stays up when the scoreboard key is let go",
                (leg and leg[0], on and on[0]), ("pinned", handle(ZED)))
        if not on:                              # a build that shut it: the checks below still run
            send("scores open", 1.0)
            send("scores on " + handle(ZED), 0.5)
            board(lambda g: g[1] and g[1][1] == "2")
        send("scores tab segmented", 0.6)       # the source moved by a console word (a key does the same)
        leg, gone = board(lambda g: g[1] is None, 5)
        send("scores tab online", 0.6)
        L.check("H  ...and a source or a leg chosen by any road gives the table back", gone, None)
        # This map's legs, by name: which board a time's row opens depends on them.
        names = []
        for i in range(int(leg[2]) if leg else 0):
            send("scores leg %d" % i, 0.3)
            names.append((board()[0] or ("", "", "", "?"))[3])
        send("scores leg 0", 0.3)
        print("  this map's legs: %s" % names)
        # zed's three times, in the view's order, and the last of them this map has a leg for
        other = [(n, r) for r, n in enumerate(("main", "stage 1", "bonus 1")) if r and n in names][-1:]
        moved = gone = None
        if other:
            send("scores on " + handle(ZED), 0.5)
            leg, on = board(lambda g: g[1] and g[1][1] == "2")
            st = status()
            click(st, float(on[7]) + float(on[9]) * 0.5, float(on[8]) + float(on[10]) * (other[0][1] + 0.5))
            moved, gone = board(lambda g: g[1] is None, 5)
        else:
            print("  CANNOT MEASURE which leg a time's row opens: this map has the main track only")
        send("scores on " + handle(ZED), 0.5)
        leg, on = board(lambda g: g[1] and g[1][1] == "2")
        st = status()                           # ...and the first row is the main track's
        click(st, float(on[7]) + float(on[9]) * 0.5, float(on[8]) + float(on[10]) * 0.5)
        back, gone2 = board(lambda g: g[1] is None, 5)
        L.check("H  a click on a time gives the table back on that time's own board: %s, then the "
                "main track's" % (other[0][0] if other else "(no other leg on this map)"),
                (other and (gone, moved and moved[3]), gone2, back and (back[1], back[3]), back and back[0]),
                (other and (None, other[0][0]), None, ("1", "main"), "pinned"))
        send("scores on " + handle(ZED), 0.5)
        leg, on = board(lambda g: g[1] and g[1][1] == "2")
        st = status()
        click(st, float(on[3]) + float(on[5]) * 0.5, float(on[4]) + float(on[6]) * 0.5)
        st = until(lambda s: s[0] == "1" and s[3] == "2")
        L.check("H  \"Whole profile\" closes the board and opens the card on that player",
                st and (st[:5], st[18]), (("1", "1", handle(ZED), "2", handle(ZED)), "0"))
        shot("p663_9_from_board")
        keys.press("esc")
        time.sleep(0.3)
        keys.press("esc")
        time.sleep(0.5)
        asked = len(ASKS)                       # the card is shut, and the breakdown held is still zed's
        send("hud_player tier 2", 1.5)
        L.check("D  a tier named on the console with no card up asks surfd for nothing",
                (status()[0], len(ASKS) - asked), ("0", 0))
        send("scores open", 1.0)
        send("scores me", 0.8)
        L.check("B  the board's \"my profile\" closes it and opens this player's own page",
                status()[:3], ("1", "1", ""))
        keys.press("esc")
        time.sleep(0.5)

        # L: this game links, as p653box's N and L do it.
        before = status()
        time.sleep(3.2)                         # the lobby's gap between one player's asks
        send("link", 0.8)
        keys.press("enter")
        m = cl.wait(L.GO, 20)
        number = L.code_on(L.browser(hport, L.SIDS[0], "198.51.100.9", L.address(m))) if m else ""
        asked = cl.wait(r"link this game to \S+\? Type the number from the sign-in page", 15)
        time.sleep(1.0)
        keys.type(number)
        time.sleep(0.4)
        keys.press("enter")
        linked = bool(cl.wait("now linked to ", 20))
        # The account's picture, before this game first asks for its mark: a
        # miss is remembered for fifteen minutes (cl_steampic.qc, SP_MISS).
        rows = account_picture(db, L.SIDS[0]) if linked else 0
        time.sleep(1.0)
        keys.press("back")
        time.sleep(0.5)
        send("hud_player stats", 1.0)
        st = until(lambda s: s[3] == "2")
        mark = handle(L.SIDS[0])[:8]
        L.check("L  this game links; the lobby says so, and Stats is this player's own breakdown, "
                "asked for by the lobby's mark",
                (bool(asked), linked, before and before[10], st and (st[0], st[1], st[2], st[3], st[4], st[5], st[10])),
                (True, True, "1", ("1", "1", "", "2", mark, str(have[L.SIDS[0]]), "2")))
        time.sleep(4.0)                         # a picture is asked for when it first draws
        card = shot("p663_10_mine")
        keys.press("esc")
        time.sleep(0.5)
        send("+showscores", 3.0)
        room = shot("p663_11_room")
        send("-showscores", 0.5)
        # The board's table has a picture of its own now (zed's time on this map,
        # Patch 666's rows): the room list is measured right of the board.
        found, side, cut = [], None, 0
        if room:
            from PIL import Image
            whole = Image.open(room)
            cut = int(whole.size[0] * 0.6)
            side = a.output_dir / "p663_11_room_right.png"
            whole.crop((cut, 0, whole.size[0], whole.size[1])).save(side)
        for img, off in ((side, cut), (card, 0)):
            n, box, size = PIC.quadrants(img) if img else (0, None, None)
            found.append((n > 0, (box[2] - box[0], box[3] - box[1]) if box else None,
                          round((off + box[0]) / (off + size[0]), 2) if box else None))
            print("  the four-colour picture in %s: %d matches, their corners span %s of %s"
                  % (img and img.name, n, box, size))
        # A picture's top-left quadrant is half its side: matching corners fill a little under that.
        L.check("R  the linked account's picture: in the room list right of the board at about 26 px, "
                "and at the card's head about twice that",
                (rows, found[0][0], bool(found[0][1]) and 6 <= found[0][1][0] <= 13,
                 bool(found[0][2]) and found[0][2] > 0.6,
                 found[1][0], bool(found[1][1]) and 16 <= found[1][1][0] <= 24),
                (1, True, True, True, True, True))
        L.check("no VM error or unknown command in the client's log",
                [w for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow",
                             "sui warning") if w in cl.text()], [])
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return 1 if L.FAILED else 0
    finally:
        if mouse is not None:
            mouse.restore()
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if web is not None:
            web.shutdown()
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError("refusing removal: not our junction: %s" % path)
            path.rmdir()
        print("\nrig kept (junctions removed):", rig)
        if L.FAILED:
            print("%d FAILURE(S):" % len(L.FAILED))
            for f in L.FAILED:
                print("  " + f)


if __name__ == "__main__":
    raise SystemExit(main())
