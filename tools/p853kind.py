#!/usr/bin/env python3
"""p853kind.py -- the profile card's All / Surf / Bhop switch (Patch 853), by console lines only.

    python tools/p853kind.py --progs <build dir> --output-dir <owned dir> [--old-surfd]

p663profile's rig (a surfd in this process, a lobby, one client whose leaderboard
is that surfd), on a board of five rated maps: zed has finished surf_alpha,
bhop_alpha and bhop_gamma of surf_alpha (tier 1), surf_beta (2), bhop_alpha and
bhop_beta (1) and bhop_gamma (3). Graded on `hud_player status` (its `kind N
split N`), the card's own developer lines, and the asks this surfd got. No
pointer moves. Screenshots of each state go to --output-dir: look at them.

  A  the card holds all three tables: kind 0, split 1, the tier-1 list asked plain
  B  `hud_player kind bhop`: kind 2; tier 1's list is asked again with &mode=bhop
     and holds bhop_alpha (finished, first) and bhop_beta
  C  `hud_player kind surf`: tier 1 is surf_alpha alone
  D  `hud_player kind all`: tier 1 is all three again, asked plain
    --old-surfd: surfd answers as before P853 (no `modes`, `mode` ignored):
  O  split 0, `kind bhop` leaves kind 0 and asks nothing, tier 1 lists all three
"""
import argparse
import hashlib
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

import p615link as L

ZED, OTHER = "76561198000008003", "76561198000008002"
MAPS = {"surf_alpha": 1, "surf_beta": 2, "bhop_alpha": 1, "bhop_beta": 1, "bhop_gamma": 3}
ASKS = []                       # (ct, mode) of every player=&ct= ask this rig's surfd got


def handle(player):
    return hashlib.sha256(player.encode("ascii")).hexdigest()[:12]


def seed(db):
    now = int(time.time())
    rows = []
    for mp in MAPS:
        rows.append((mp, OTHER, "other", 60000))
    for mp in ("surf_alpha", "bhop_alpha", "bhop_gamma"):
        rows.append((mp, ZED, "^2zed", 50000))
    conn = sqlite3.connect(str(db))
    conn.executemany(
        "INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate, millis,"
        " flags, node, runid, submitted, replay_id) VALUES (?,0,0,'momentum','clean',?,?,?,100.0,?,0,"
        "'import','i-' || ?,?,0)",
        [(mp, p, n, ms // 10, ms, p + mp, now - 86400) for mp, p, n, ms in rows])
    conn.commit()
    conn.close()


def watch(old):
    """Record each tier ask; with `old`, answer as a surfd before P853 does."""
    from flask import request
    S = sys.modules["surfd"]
    real_player, real_comp, real_tiers = S.game_player, S._completion, S._tier_maps

    def player(raw, now):
        if request.args.get("ct") is not None:
            ASKS.append((request.args.get("ct"), request.args.get("mode", "")))
        return real_player(raw, now)
    S.game_player = player
    if old:
        def comp(*a):
            c = real_comp(*a)
            if c:
                c.pop("modes", None)
            return c
        S._completion = comp
        S._tier_maps = lambda ranked, main_maps, mode="": real_tiers(ranked, main_maps)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--server", type=pathlib.Path, default=pathlib.Path("C:/FTEQuake/fteqwsv64.exe"))
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    ap.add_argument("--old-surfd", action="store_true")
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    tag = "p853old" if a.old_surfd else "p853"

    rig, gd, junctions = L.build_rig(a)
    print("rig", rig)
    (gd / "data").mkdir(exist_ok=True)
    # FS_TERMS_ONLINE (sh_defs.qc) is 7: under it the card asks nothing (breakdown 4, PFS_NOTERMS).
    (gd / "data" / "consent.txt").write_text("FTESURF-CONSENT 1\nversion 7\naccepted 20261012-000000\n")
    server = client = web = None
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
        tsv = rig / "momtracks.tsv"
        tsv.write_text("# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n" + "".join(
            "%s\t%d\t%d\t1\t0\t1\n" % (mp, k + 1, t) for k, (mp, t) in enumerate(MAPS.items())))
        import os
        os.environ["SURFD_MOMTRACKS"] = str(tsv)
        web, db = L.start_surfd(rig, hport, "127.0.0.1")
        S = sys.modules["surfd"]
        for folder in (S.ZONES_DIR, S.ZONES_LOCAL_DIR):
            pathlib.Path(folder).mkdir(parents=True, exist_ok=True)
        for mp in MAPS:                     # pool_policy counts a bhop map only with a zone file
            if mp.startswith("bhop_"):
                (pathlib.Path(S.ZONES_DIR) / (mp + ".json")).write_text("{}")
        seed(db)
        S.maps_reset()
        S.people_reset()
        watch(a.old_surfd)
        common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                  "+set", "cfg_save_auto", "0", "+set", "log_enable", "1", "+set", "log_dir", "logs"]
        server = subprocess.Popen(
            [str(a.server), *common, "+set", "log_name", tag + "sv", "+set", "developer", "1",
             "+set", "sv_public", "0", "+set", "sv_port", str(gport),
             "+set", "sv_guidkey", "p853-probe", "+set", "sv_maxrate", "0",
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
            [str(a.client), "-plugin", "-nobrowse", *common, "+set", "log_name", tag + "cl",
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

        cl = L.Log(gd / ("logs/%scl.log" % tag))
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
        for line in ("closemenu", "con_notifytime 0", "con_notifylines 0"):
            send(line)
        cl.wait("press Enter to link your Steam account", 30)
        time.sleep(1.0)

        # 0 breakdown, 1 of, 2 tier, 3 its answer, 4-5 maps held/of, 6 finished, 7 kind, 8 split
        ST = re.compile(r'breakdown (\d) of "([^"]*)" .*  tier "([^"]*)" (\d) maps (\d+)/(\d+) done (\d+)'
                        r'  bar \S+ \S+  kind (\d) split (\d)')
        SAID = re.compile(r"profile: tier (\S+) of (\w+): (\d+) maps of (\d+) held, (\d+) finished, first (\S+)")

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

        def listed(n0):
            """The tier lists the card printed since `n0` lines of them."""
            return SAID.findall(cl.text())[n0:]

        zed = handle(ZED)
        send("hud_player view " + zed, 1.0)
        st = until(lambda s: s[0] == "2")
        send("hud_player tier 1", 0.5)
        st = until(lambda s: s[2] == "1" and s[3] == "2")
        n = len(SAID.findall(cl.text()))
        shot(tag + "_all")
        if not a.old_surfd:
            L.check("A  the card holds the split: kind 0, split 1; tier 1 (3 maps, 2 finished) asked plain",
                    (st and (st[1], st[7], st[8], st[4], st[6]), ASKS[-1:]),
                    ((zed, "0", "1", "3", "2"), [("1", "")]))
            k0 = len(ASKS)
            send("hud_player kind bhop", 0.5)
            st = until(lambda s: s[7] == "2" and s[3] == "2" and len(ASKS) > k0)
            got = listed(n)
            L.check("B  kind bhop: tier 1 asked again with &mode=bhop, 2 maps, bhop_alpha finished and first",
                    (st and (st[7], st[4], st[6]), ASKS[k0:], got[-1:] and got[-1][::5] + got[-1][2:3]),
                    (("2", "2", "1"), [("1", "bhop")], ("1&mode=bhop", "bhop_alpha", "2")))
            shot(tag + "_bhop")
            k0, n = len(ASKS), len(SAID.findall(cl.text()))
            send("hud_player kind surf", 0.5)
            st = until(lambda s: s[7] == "1" and s[3] == "2" and len(ASKS) > k0)
            got = listed(n)
            L.check("C  kind surf: tier 1 is surf_alpha alone, finished",
                    (st and (st[7], st[4], st[6]), ASKS[k0:], got[-1:] and got[-1][::5]),
                    (("1", "1", "1"), [("1", "surf")], ("1&mode=surf", "surf_alpha")))
            shot(tag + "_surf")
            k0 = len(ASKS)
            send("hud_player kind all", 0.5)
            st = until(lambda s: s[7] == "0" and s[3] == "2" and len(ASKS) > k0)
            L.check("D  kind all: tier 1 is all three again, asked plain",
                    (st and (st[7], st[4], st[6]), ASKS[k0:]), (("0", "3", "2"), [("1", "")]))
        else:
            k0 = len(ASKS)
            send("hud_player kind bhop", 1.5)
            st = status()
            L.check("O  a surfd without modes: split 0; kind bhop stays 0 and asks nothing; tier 1 lists all three",
                    (st and (st[1], st[7], st[8], st[4], st[6]), ASKS[k0:], cl.text().count("profile: kind")),
                    ((zed, "0", "0", "3", "2"), [], 0))
            shot(tag + "_kind_ignored")
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
        print("\nasks:", ASKS)
        print("rig kept (junctions removed):", rig)
        if L.FAILED:
            print("%d FAILURE(S):" % len(L.FAILED))
            for f in L.FAILED:
                print("  " + f)


if __name__ == "__main__":
    raise SystemExit(main())
