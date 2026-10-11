#!/usr/bin/env python3
"""p640pics.py -- does the game draw a Steam picture beside a name?  (Patch 640)

    python tools/p640pics.py --progs <dir with the three .dat> [--client exe]

p615link's rig (its own basedir, junctions to the content, surfd in this
process) and one client on a listen server.  surfd is seeded with one account
that has a picture and two KSF rows on the map: one under that account's
SteamID, one under a SteamID with no account.  The picture is four flat
quadrants -- red, green / blue, yellow -- so a swapped channel or a flipped
row order shows.

Graded on three things, each the subject's own:
  R  surfd's board: `av` on the account's row and on no other
  F  the client's cache (`scores pics`): one ask, one picture, under the mark
     surfd files the account by
  D  THE SCREENSHOT: the four quadrants, in their places, on the board.  The
     cache's count is what the game meant to draw; this is what it drew.
  V  the same two after `vid_restart`, which takes the textures and shaders

--slow N has surfd take N seconds over the picture (past the cache's 20):
nothing else may be asked meanwhile, and the late answer must still be taken
and drawn.  --busy N has surfd answer the first N picture requests 429: the
mark must stay wanted, be asked again a minute on, and be drawn.  Both skip V.

--no-picture is the control: the account has no picture, so no `av`, no ask
and no quadrants; all three must say so.  A build with the drawpic taken out
must pass F and fail D (run by hand; the recipe is in the arm's RESULT note in
AGENT_NOTES).  Exit 1 on any miss.

The window is shown (about 40 s) but takes no focus; nothing is typed into
it (console lines go down the -plugin pipe), and the clipboard is not used.
"""
import argparse
import io
import json
import os
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

import p615link as L

SID, PLAIN = "76561198000000042", "76561198000000043"
HASH = "ab" * 20
QUADS = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))     # TL, TR, BL, BR


def picture():
    from PIL import Image
    img = Image.new("RGB", (64, 64))
    for n, col in enumerate(QUADS):
        img.paste(col, ((n % 2) * 32, (n // 2) * 32, (n % 2) * 32 + 32, (n // 2) * 32 + 32))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=100, subsampling=0)
    return buf.getvalue()


def near(px, col):
    return all(abs(a - b) <= 70 for a, b in zip(px, col))


def quadrants(path):
    """Top-left corners in the image where the four quadrant colours sit a
    step apart, as (count, the smallest box holding them).  A step of 3 to 40
    covers any size a row could draw it at."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    hits = []
    for y in range(h - 3):
        for x in range(w - 3):
            if not near(px[x, y], QUADS[0]):
                continue
            for d in (3, 5, 8, 12, 16, 24, 32, 40):
                if x + d >= w or y + d >= h:
                    break
                if (near(px[x + d, y], QUADS[1]) and near(px[x, y + d], QUADS[2])
                        and near(px[x + d, y + d], QUADS[3])):
                    hits.append((x, y))
                    break
    if not hits:
        return 0, None, (w, h)
    xs, ys = [p[0] for p in hits], [p[1] for p in hits]
    return len(hits), (min(xs), min(ys), max(xs), max(ys)), (w, h)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    ap.add_argument("--no-picture", action="store_true")
    ap.add_argument("--slow", type=float, default=0)
    ap.add_argument("--busy", type=int, default=0)
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()

    rig, gd, junctions = L.build_rig(a)
    print("rig", rig)
    client = web = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            hport = probe.getsockname()[1]
        web, db = L.start_surfd(rig, hport, "127.0.0.1")
        S, A = sys.modules["surfd"], sys.modules["accounts"]
        import steamsync
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO accounts (steamid, name, created_at, avatar) VALUES (?,?,?,?)",
                     (SID, "Pictured", int(time.time()), "" if a.no_picture else HASH))
        for player, name, ticks in ((SID, "Pictured", 3000), (PLAIN, "Plain", 3100)):
            conn.execute(
                "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,"
                " millis, flags, node, runid, submitted, replay_id)"
                " VALUES (?,0,0,'ksf','clean',?,?,?,100.0,?,0,'import',?,?,0)",
                (a.map, player, name, ticks, ticks * 10, "i-" + player, int(time.time())))
        conn.commit()
        conn.close()
        if not a.no_picture:
            jpeg = picture()
            os.makedirs(S.AVATAR_DIR, exist_ok=True)
            with open(os.path.join(S.AVATAR_DIR, HASH + ".jpg"), "wb") as fh:
                fh.write(jpeg)
            with open(os.path.join(S.AVATAR_DIR, HASH + ".txt"), "w", newline="\n") as fh:
                fh.write(steamsync.game_form(jpeg))
        S.avatars_reset()
        S.people_reset()
        real_avatar, asks = S.game_avatar, []

        def avatar(who, now):               # surfd's own route, made slow or busy
            asks.append(time.time())
            if a.slow:
                time.sleep(a.slow)
            if len(asks) <= a.busy:
                return S.fail(429, "rate limited")
            return real_avatar(who, now)
        S.game_avatar = avatar
        base = "http://127.0.0.1:%d" % hport
        with urllib.request.urlopen(base + "/api/board?map=%s&tier=combined" % a.map, timeout=20) as r:
            rows = json.loads(r.read()).get("rows", [])
        L.check("R  surfd's board: `av` on the pictured account's row and on no other",
                [(r.get("name"), r.get("av")) for r in rows],
                [("Pictured", None if a.no_picture else 1), ("Plain", None)])
        who = A.who_of(SID)

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        # SW_SHOWNOACTIVATE.  Minimised (7, p615link's) drew nothing in two runs
        # of five here: a black screenshot, which the control then "passed".
        si.wShowWindow = 4
        client = subprocess.Popen(
            [str(a.client), "-plugin", "-nobrowse", "-basedir", str(rig),
             "-manifest", str(rig / "default.fmf"), "+set", "cfg_save_auto", "0",
             "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p640cl",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "100", "+set", "vid_width", "1280", "+set", "vid_height", "720"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)

        def send(line):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()

        cl = L.Log(gd / "logs/p640cl.log")
        time.sleep(8)                           # a line read while starting is dropped
        up = None
        for _ in range(3):
            send("map " + a.map)
            up = cl.wait("FTESurf CSQC loaded", 40)
            if up:
                break
        L.check("the client is on the map and its game code loaded", bool(up), True)
        shot = None
        if up:
            send("closemenu")
            send("set rec_terms 4")             # FS_TERMS_ONLINE: the board may ask
            send('set lobby_dir "%s"' % base)    # quoted: // starts a console comment
            time.sleep(1)
            send("scores open")
            send("scores tab online")
            # The board's own status, until it has drawn its columns and holds
            # the fixture's rows.  Not a fixed sleep: one run sat 8 s after the
            # map loaded without drawing a frame, and was graded on nothing.
            drawn = False
            for _ in range(30):
                send("scores status")
                m = cl.wait(r"tab online\s+filter \w+\s+cols (\d+)", 5)
                time.sleep(0.5)
                if m and int(m.group(1)) > 0 and "Pictured" in cl.text():
                    drawn = True
                    break
                time.sleep(1.5)
            L.check("the board is on screen and holds the fixture's rows (its own status)",
                    (drawn, "Plain" in cl.text()), (True, True))
            time.sleep(6)                       # room for an ask (SP_GAP) and its answer
            send("scores pics")
            said = cl.wait(r"steampic: asked (\d+) got (\d+) inflight (\d+)", 15)
            time.sleep(0.5)
            if a.slow or a.busy:
                first = said.groups() if said else None
                L.check("S  six seconds in: one ask, no picture yet (%s)"
                        % ("still out" if a.slow else "answered 429: the mark is wanted, not written off"),
                        (first, sorted(set(re.findall(r"steampic: slot .*", cl.text())))),
                        (("1", "0", "1" if a.slow else "0"),
                         ["steampic: slot 0 mark %s state %d" % (who, 2 if a.slow else 1)]))
                end = time.time() + a.slow + 60 * a.busy + 30
                while time.time() < end:
                    send("scores pics")
                    said = cl.wait(r"steampic: asked (\d+) got (\d+) inflight (\d+)", 6)
                    if said and said.group(2) == "1":
                        break
                    time.sleep(3)
                gaps = [round(b - x) for x, b in zip(asks, asks[1:])]
                print("     surfd saw %d picture request(s), gaps %s s" % (len(asks), gaps))
                L.check("S  surfd was asked once, or once more a minute after each 429, and never "
                        "while a request was out",
                        (len(asks), [g >= 55 for g in gaps]), (1 + a.busy, [True] * a.busy))
                time.sleep(1.5)
            slots = re.findall(r"steampic: slot .*", cl.text())[-1:]     # the last word on it
            want = ("0", "0", "0") if a.no_picture else (str(1 + a.busy), "1", "0")
            L.check("F  the client's cache: one ask and one picture (none without one)",
                    said.groups() if said else None, want)
            L.check("F  ...held under the mark surfd files the account by, as drawable",
                    slots, [] if a.no_picture else ["steampic: slot 0 mark %s state 3" % who])
            send("screenshot p640board")
            end = time.time() + 15
            while time.time() < end and not shot:
                found = list((gd / "screenshots").glob("p640board.*"))
                shot = found[0] if found else None
                time.sleep(0.5)
            time.sleep(1)
        if shot:
            n, box, size = quadrants(shot)
            print("     screenshot %s %dx%d: %d quadrant matches, box %s" % (shot.name, size[0], size[1], n, box))
            L.check("D  THE SCREENSHOT holds the picture's four quadrants in their places "
                    "(none without one)", n > 0, not a.no_picture)
            keep = a.output_dir / ("p640board-%s%s" % ("none" if a.no_picture else "pic", shot.suffix))
            shutil.copyfile(shot, keep)
            print("     kept", keep)
        else:
            L.check("D  a screenshot was taken", False, True)
        if shot and not (a.no_picture or a.slow or a.busy):
            # V  A renderer restart (what F11 does) takes every texture and
            # shader with it.  The picture must be fetched again and DRAWN: a
            # build that kept its slot "held" drew the engine's checker here.
            send("vid_restart")
            time.sleep(6)
            send("closemenu")
            again = None
            end = time.time() + 40
            while time.time() < end:
                send("scores pics")
                again = cl.wait(r"steampic: asked (\d+) got (\d+) inflight (\d+)", 6)
                if again and again.group(2) == "2":
                    break
                time.sleep(2)
            L.check("V  after a renderer restart the picture is asked for and had again",
                    again.groups() if again else None, ("2", "2", "0"))
            time.sleep(1.5)
            send("screenshot p640again")
            shot2 = None
            end = time.time() + 15
            while time.time() < end and not shot2:
                found = list((gd / "screenshots").glob("p640again.*"))
                shot2 = found[0] if found else None
                time.sleep(0.5)
            time.sleep(1)
            n2 = quadrants(shot2)[0] if shot2 else -1
            print("     after the restart: %d quadrant matches" % n2)
            L.check("V  ...and THE SCREENSHOT after it holds the four quadrants again", n2 > 0, True)
            if shot2:
                shutil.copyfile(shot2, a.output_dir / ("p640again" + shot2.suffix))
        L.check("no VM error or unknown command in the client's log",
                [w for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow",
                             "PF_CL_uploadimage") if w in cl.text()], [])
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return 1 if L.FAILED else 0
    finally:
        if client is not None and client.poll() is None:
            client.terminate()
            client.wait(timeout=10)
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
