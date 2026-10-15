#!/usr/bin/env python3
"""Headless real-socket QC controls; optional windowed captures only when quiet.

All fixtures live under an existing owned --output-dir. No install files change.
An intentionally conflicting client catalogue proves server authority. Fixture
ratings are synthetic, never written to the product catalogue/player data.
"""
import argparse
import pathlib
import re
import shutil
import socket
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAP = "surf_eclipse"
PAYLOAD = "v1;surf_eclipse;0,0,4,rank,6,-,-;0,1,2,sugg,-,-,-;1,0,8,rank,-,X,S;"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=pathlib.Path, required=True)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--port", type=int, default=27616)
    ap.add_argument("--zones", type=pathlib.Path, help="authored surf_eclipse.json fixture (read-only)")
    ap.add_argument("--bonus-zones", type=pathlib.Path, help="authored surf_ace.json fixture (read-only)")
    ap.add_argument("--css-control", help="exact CSS-only map to join without downloading")
    a = ap.parse_args()
    a.output_dir = a.output_dir.resolve()
    if not any((d / "OWNER.md").is_file() for d in [a.output_dir, *a.output_dir.parents]):
        raise ValueError("output-dir requires an ancestor OWNER.md")
    if not 27520 <= a.port <= 27620:
        raise ValueError("test socket must be in the dedicated lobby range")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", a.port))
    a.output_dir.mkdir(exist_ok=False)
    processes = []
    files = []
    try:
        rigs = {}
        for role in ("server", "client"):
            rig = a.output_dir / role
            gd = rig / "ftesurf"
            (gd / "maps").mkdir(parents=True)
            shutil.copyfile(ROOT / "default.fmf", rig / "default.fmf")
            shutil.copytree(ROOT / "ftesurf/cfg", gd / "cfg")
            shutil.copyfile(ROOT / "ftesurf/fs_addons.default.txt", gd / "fs_addons.txt")
            for name in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
                shutil.copyfile(a.progs / name, gd / name)
            (gd / "downloads/csprogsvers").mkdir(parents=True)
            subprocess.run(["python", str(ROOT / "tools/seed_csprogs.py"), str(gd / "csprogs.dat")],
                           check=True, capture_output=True)
            data = PAYLOAD if role == "server" else "v1;surf_eclipse;0,0,9,rank,9,-,-;"
            (gd / "maps/tiers.txt").write_text('tiers surf_eclipse "' + data + '"\n')
            if a.zones:
                (gd / "maps/zones/local").mkdir(parents=True)
                shutil.copyfile(a.zones, gd / "maps/zones/local/surf_eclipse.json")
                if a.bonus_zones:
                    shutil.copyfile(a.bonus_zones, gd / "maps/zones/local/surf_ace.json")
            cfg = ('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\ncon_savehistory 0\n'
                   'update_autocheck 0\nsv_public 0\ndeveloper 1\nlog_developer 1\n'
                   'log_name tiers\nlog_enable 1\n')
            if role == "server":
                cfg += ("map surf_eclipse\nserverinfo maptier 4\nserverinfo maptiersrc rank\n"
                        "echo TIER_SERVER_READY\nserverinfo\n")
            else:
                cfg += f"connect 127.0.0.1:{a.port}\n"
            (gd / "cfg/test/tiers.cfg").write_text(cfg)
            rigs[role] = rig

        def launch(role, exe):
            rig = rigs[role]
            out = (a.output_dir / (role + "-stdout.log")).open("wb")
            files.append(out)
            argv = [exe, "-plugin", "-nohome", "-basedir", str(rig), "-manifest", str(rig / "default.fmf")]
            if role == "server":
                argv += ["-port", str(a.port)]
            else:
                argv += ["+set", "vid_renderer", "headless"]
            argv += ["+set", "cfg_save_auto", "0", "+exec", "cfg/test/tiers.cfg"]
            p = subprocess.Popen(argv, cwd="C:/FTESurf", stdin=subprocess.PIPE,
                                 stdout=out, stderr=subprocess.STDOUT, creationflags=0x08000000)
            processes.append(p)
            return p

        def logs(role):
            return "\n".join(p.read_text(errors="replace") for p in
                             (rigs[role] / "ftesurf/logs").glob("tiers*.log"))

        def wait(role, marker, limit=60, after=0):
            end = time.monotonic() + limit
            while time.monotonic() < end:
                text = logs(role)
                if marker in text[after:]:
                    return text
                p = server if role == "server" else client
                if p.poll() is not None:
                    raise RuntimeError("%s exited %s before %s" % (role, p.returncode, marker))
                time.sleep(.1)
            raise AssertionError(role + " never acted: " + marker)

        def send(p, command):
            p.stdin.write((command + "\n").encode())
            p.stdin.flush()

        server = launch("server", "C:/FTEQuake/fteqwsv64.exe")
        wait("server", "TIER_SERVER_READY")
        client = launch("client", "C:/FTESurf/ftesurf64.exe")
        wait("client", "FTESurf CSQC loaded")
        wait("client", "Sending stringcmd begin")
        # CSQC loads before prespawn finishes; large serverinfo keys arrive later.
        # Query only after the real client has entered the game.
        time.sleep(2)
        send(client, "menu_restart; ui_close; zone_reload; scores open; scores tab local; scores tiers 1 0; echo TIER_CLIENT_ACTED")
        text = wait("client", "TIER_CLIENT_ACTED")
        assert "map tiers: MOM tier 4 | KSF tier 6" in text, text[-2500:]
        assert "asked tiers: MOM tier 8 | KSF bonus X (unit) / S (strafe)" in text, text[-2500:]
        assert "compact tiers: MOM 8  KSF U:X S:S" in text
        assert "MOM tier 9" not in text
        print("PASS remote main + bonus split, conflicting client catalogue ignored")
        send(client, "scores tiers 0 1; echo TIER_STAGE_ACTED")
        text = wait("client", "TIER_STAGE_ACTED")
        assert "asked tiers: MOM tier 2 (suggested)" in text
        assert "compact tiers: MOM 2*" in text
        assert "active tiers: stage 1: MOM tier 2 (suggested)" in text
        if a.zones:
            assert "  stage 1: MOM tier 2 (suggested)" in text
            assert "  main: MOM tier 4 | KSF tier 6" in text
        print("PASS exact stage suggestion / active HUD leg / scoreboard leg table")
        send(client, "scores tiers 0 2; echo TIER_UNKNOWN_ACTED")
        text = wait("client", "TIER_UNKNOWN_ACTED")
        assert re.search(r"asked tiers: *\n", text.split("TIER_STAGE_ACTED", 1)[1])
        print("PASS untiered stage does not inherit main")
        send(client, 'vote fake maptier 7 ksf; scores tiers; echo TIER_OLD_KSF_ACTED')
        text = wait("client", "TIER_OLD_KSF_ACTED")
        assert "map tiers: MOM tier ? | KSF tier 7" in text
        send(client, 'vote fake maptier 3 sugg; scores tiers; echo TIER_OLD_MOM_ACTED')
        text = wait("client", "TIER_OLD_MOM_ACTED")
        assert "map tiers: MOM tier 3 (suggested) | KSF tier ?" in text
        send(client, 'vote fake maptier 5 alias; scores tiers; echo TIER_OLD_ALIAS_ACTED')
        text = wait("client", "TIER_OLD_ALIAS_ACTED")
        assert "map tiers: MOM tier ? | KSF tier ?" in text
        print("PASS old-server source-aware fallbacks, alias not miscredited")
        send(client, 'vote fake ratings "v1;othermap;0,0,10,rank,10,-,-;"; scores tiers; echo TIER_STALE_ACTED')
        text = wait("client", "TIER_STALE_ACTED")
        assert "map tiers: MOM tier ? | KSF tier ?" in text.split("TIER_OLD_ALIAS_ACTED", 1)[1]
        print("PASS stale cross-map ratings rejected")
        send(client, 'vote fake off')
        send(server, 'map surf_ace; echo TIER_MAP_CHANGED; serverinfo')
        wait("server", "TIER_MAP_CHANGED")
        wait("client", "SERVERINFO: map=surf_ace", 60)
        time.sleep(3)
        send(client, 'scores tiers; echo TIER_CLEARED_ACTED')
        text = wait("client", "TIER_CLEARED_ACTED")
        assert "map tiers: MOM tier ? | KSF tier ?" in text.split("TIER_STALE_ACTED", 1)[1]
        assert "v1:surf_ace" in logs("server")
        print("PASS map-change unknown explicitly clears previous ratings")
        if a.bonus_zones:
            data = 'tiers surf_ace "v1;surf_ace;0,0,2,rank,1,-,-;1,0,8,sugg,-,X,S;"\n'
            (rigs["server"] / "ftesurf/maps/tiers.txt").write_text(data)
            base = len(logs("client"))
            send(server, "map surf_ace; echo TIER_BONUS_SERVER_ACTED")
            wait("server", "TIER_BONUS_SERVER_ACTED")
            wait("client", "SERVERINFO: map=surf_ace", after=base)
            time.sleep(3)
            send(client, "zone_reload; scores open; scores tab local; say !b 1")
            time.sleep(2)
            send(client, "scores tiers 1 0; echo TIER_BONUS_CLIENT_ACTED")
            text = wait("client", "TIER_BONUS_CLIENT_ACTED")
            tail = text[base:]
            expected = "bonus 1: MOM tier 8 (suggested) | KSF bonus X (unit) / S (strafe)"
            assert "active tiers: " + expected in tail
            assert "  " + expected in tail
            assert "compact tiers: MOM 8*  KSF U:X S:S" in tail
            print("PASS warped bonus HUD stat + scoreboard bonus leg share MOM suggestion/KSF split")
        if a.css_control:
            name = a.css_control
            if not re.fullmatch(r"surf_[a-z0-9_]+", name):
                raise ValueError("CSS control needs a bare exact surf map name")
            css = pathlib.Path("C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Source/cstrike/maps") / (name + ".bsp")
            mom = pathlib.Path("C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps") / (name + ".bsp")
            assert css.is_file() and not mom.exists()
            assert not pathlib.Path("C:/FTESurf/ftesurf/maps", name + ".bsp").exists()
            send(server, "map " + name + "; echo TIER_CSS_SERVER_ACTED")
            wait("server", "TIER_CSS_SERVER_ACTED")
            wait("client", "SERVERINFO: map=" + name, 90)
            time.sleep(2)
            send(client, "flocate maps/" + name + ".bsp; scores tiers; echo TIER_CSS_CLIENT_ACTED")
            text = wait("client", "TIER_CSS_CLIENT_ACTED")
            tail = text.split("TIER_CLEARED_ACTED", 1)[1]
            assert "Counter-Strike Source/cstrike" in tail.replace("\\", "/"), tail[-1000:]
            assert name + ".bsp" in tail
            assert not re.search(r"Downloading[^\n]*maps/" + name, tail)
            assert not (rigs["client"] / "ftesurf/maps" / (name + ".bsp")).exists()
            assert not (rigs["client"] / "ftesurf/maps" / (name + ".tmp")).exists()
            print("PASS joined CSS-only " + name + "; flocate proves cstrike/maps source, no map download")
        for role in rigs:
            text = logs(role)
            bad = ("QC VM error", "Cannot call", "stack overflow", "Unknown command", "Progs boundcheck failed")
            assert not any(x in text for x in bad), role + " runtime error"
        (a.output_dir / "PASS.txt").write_text("Real dedicated socket/headless CSQC controls passed. No visual acceptance claimed.\n")
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                try:
                    send(p, "quit")
                    p.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    p.terminate()
                    p.wait(timeout=5)
        for f in files:
            f.close()
        print("Retained owned evidence:", a.output_dir)


if __name__ == "__main__":
    main()
