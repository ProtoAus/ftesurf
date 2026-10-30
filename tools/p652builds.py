#!/usr/bin/env python3
"""p652builds.py -- two builds of a map on one row, and the list the menu fetches.  (Patch 652)

    python tools/p652builds.py --progs <dir with the three .dat> [--output-dir DIR]

p615link's rig: a basedir of its own, surfd in this process, one client, no
lobby.  The rig mounts no game, so every row comes from a map list and none is
installed; the names are the fixture's own and exist nowhere.

  A  the shipped list (data/mapdl.txt): a second build named `of` a map is
     folded into that map's row -- the view is one row shorter, the row answers
     the CS:S library, and `ui_build` reports both builds
  B  `ui_build <map> css` is the switch's twin: the row then plays the CS:S
     build, and data/mapbuild.txt remembers it
  C  the picker asks the directory for its list (/api/board?maps=1), saves only
     the rows that pass, reloads, and keeps the choice made in B; a list with
     no row that passes replaces nothing; a search finds a map by the name of
     the build folded into its row
  D  a real click on the CS:S cell of a row, and one on MOM: what the row plays
     follows, and `start` would launch that build
A screenshot of the list is kept for looking at.  Exit 1 on any miss.
"""
import argparse
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import p615link as L

SHIPPED = """FTESURF-MAPDL 1
# written by p652builds.py; the plain rows are "m" alone, as tools/mapscan.py
# writes a map whose CS:S build has a row of its own
dl surf_p652aa surf m 2 100 2026-10-01 0 2 0
dl surf_p652bb surf m 3 200 2026-10-01 0 3 1
dl surf_p652bb_css surf k 1 250 2026-10-01 0 0 1 surf_p652bb
dl surf_p652cc_css surf k 1 300 2026-10-01 0 0 1 surf_p652nolist
dl bhop_p652dd bhop m 1 50 2026-10-01 0 1 0
"""
GOOD = ["dl surf_p652aa surf m 2 100 2026-10-01 0 2 0",
        "dl surf_p652bb surf m 3 200 2026-10-01 0 3 1",
        "dl surf_p652bb_css surf k 1 250 2026-10-01 0 0 1 surf_p652bb",
        "dl surf_p652new surf m 4 400 2026-10-11 1 4 0",
        "dl surf_p652ee surf m 5 500 2026-10-11 0 5 2",
        "dl surf_p652ee_css surf k 2 600 2026-10-11 0 0 2 surf_p652ee",
        # as saved: its twelfth token, a later grammar's column, is not kept
        "dl surf_p652gg surf m 2 222 2026-10-11 0 2 0 surf_p652nolist2"]
BAD = ["dl surf_p652x;quit surf m 1 1 2026-10-11 0 1 0",          # a name that is not one
       'dl "surf_p652 q" surf m 1 1 2026-10-11 0 1 0',             # a quoted name with a space
       "dl surf_p652y climb m 1 1 2026-10-11 0 1 0",               # a mode that is not ours
       "dl surf_p652z surf m 1 1 2026-10-11 0 1",                  # a token too few
       "dl surf_p652w surf m 1 1 2026-10-11 0 1 0 ../x",           # a build of no name
       "dl surf_%s surf m 1 1 2026-10-11 0 1 0" % ("l" * 70),      # a name too long
       "dl surf_p652q surf mk 1 1 2026-10-11 0 1 0",               # letters in another order
       "dl surf_p652t surf m 1 99999999999 2026-10-11 0 1 0",      # a size too long
       "exec p652evil.cfg"]                                         # not a row at all
HEAD = "FTESURF-MAPDL 1\n# written by surfd/mapwatch.py at 1 -- do not edit\n"
NET = HEAD + "\n".join(GOOD[:3] + BAD[:5] + GOOD[3:6] + [GOOD[6] + " a-later-column"]
                       + BAD[5:]) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--output-dir", type=pathlib.Path)
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()

    rig, gd, junctions = L.build_rig(a)
    print("rig", rig)
    client = web = None
    try:
        (gd / "data").mkdir()
        (gd / "data" / "consent.txt").write_text("version 4\n")
        (gd / "data" / "mapdl.txt").write_text(SHIPPED, newline="\n")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            hport = probe.getsockname()[1]
        web, _db = L.start_surfd(rig, hport, "127.0.0.1")
        S = sys.modules["surfd"]
        watch = pathlib.Path(S.DATA_DIR) / "mapwatch"
        watch.mkdir(parents=True)
        (watch / "mapdl.txt").write_text(NET, newline="\n")
        asked = []
        inner = S.app.wsgi_app

        def noting(environ, start_response):
            asked.append("%s?%s" % (environ.get("PATH_INFO"), environ.get("QUERY_STRING")))
            return inner(environ, start_response)
        S.app.wsgi_app = noting

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4                      # shown, focus left alone
        client = subprocess.Popen(
            [str(a.client), "-plugin", "-nobrowse", "-basedir", str(rig),
             "-manifest", str(rig / "default.fmf"), "+set", "cfg_save_auto", "0",
             "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p652cl",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "100"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)

        def send(line):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()

        cl = L.Log(gd / "logs/p652cl.log")

        def build(name, pick=""):
            """`ui_build`'s report for a map, as a dict, or its one-line answer."""
            send("ui_build %s %s" % (name, pick))
            m = cl.wait(r"ui_build: %s (builds mom have (\S+), css (\S+) have (\S+) kb (\S+);"
                        r"(?: switch \[(\S+)\] \[(\S+)\];)? pick (\S+); plays (\S+); lists (\d+)"
                        r"|has one build[^\n]*|is not in the list[^\n]*)" % re.escape(name), 12)
            if not m:
                return None
            if m.group(2) is None:
                return re.sub(r" \(.*", "", m.group(1))
            return {"mom": m.group(2), "css": m.group(3), "csshave": m.group(4), "kb": m.group(5),
                    "ids": (m.group(6), m.group(7)), "pick": m.group(8), "plays": m.group(9),
                    "lists": int(m.group(10))}

        time.sleep(12)                          # the menu is up; a line read while starting is dropped
        send('set lobby_dir "http://127.0.0.1:%d"' % hport)
        # No mapmeta in the rig, so no row has a picture or (to the list's
        # mind) a tier: without this the picker files them under "show all".
        send("ui_showall 1")
        time.sleep(1)

        # A: the shipped list.
        b = build("surf_p652bb")
        folded = cl.text().count("1 map(s) have a CS:S build beside Momentum's")
        L.check("A  a second build named of a listed map is folded into that map's row: the "
                "row knows both builds, plays Momentum's, and answers the CS:S library (bit 4)",
                (b and (b["css"], b["kb"], b["pick"], b["plays"], b["lists"] & 4), folded > 0),
                (("surf_p652bb_css", "250", "mom", "surf_p652bb", 4), True))
        L.check("A  ...the build itself has no row of its own; one whose map is not listed keeps "
                "its row; a map with one build says so",
                (build("surf_p652bb_css"), build("surf_p652cc_css"), build("surf_p652aa")),
                ("has one build, and is folded into another row", "has one build", "has one build"))
        send("ui_browse")
        v = cl.wait(r"ui_browse: library both (\d+), momentum (\d+), cs:s (\d+)", 12)
        L.check("A  the list is one row shorter (4 of the 5 rows), and the CS:S library holds the "
                "folded row and the build with no map (2); Momentum's 3",
                v and v.groups(), ("4", "3", "2"))

        # B: the switch's twin.
        b = build("surf_p652bb", "css")
        book = gd / "data" / "mapbuild.txt"
        L.check("B  `ui_build <map> css`: the row plays the CS:S build, and the choice is written",
                (b and (b["pick"], b["plays"]),
                 [ln for ln in book.read_text().splitlines() if not ln.startswith("#")]
                 if book.exists() else None),
                (("css", "surf_p652bb_css"), ["css surf_p652bb"]))

        # C: the directory's list.
        n0 = len(asked)
        send("ui_strip_test screen create")
        saved = cl.wait(r"maplist: saved (\d+) map\(s\) from the directory, (\d+) row\(s\) not kept", 20)
        net = gd / "data" / "mapdl.net.txt"
        rows = net.read_text().splitlines() if net.exists() else []
        L.check("C  the picker asks the directory for its list, once",
                [q for q in asked[n0:] if "maps=1" in q], ["/api/board?maps=1"])
        L.check("C  ...and saves the rows that pass, rebuilt, and none of the others",
                (saved and saved.groups(), rows[:1], [r for r in rows if r.startswith("dl ")],
                 [r for r in rows[1:] if not r.startswith(("dl ", "# net "))]),
                (("7", "9"), ["FTESURF-MAPDL 1"], GOOD, []))
        time.sleep(1.5)
        b, e = build("surf_p652bb"), build("surf_p652ee")
        L.check("C  the list is read again: a map only the directory lists is there with its "
                "second build, one it no longer lists is gone, and B's choice is kept",
                (e and (e["css"], e["kb"], e["pick"]), build("surf_p652new"),
                 build("surf_p652cc_css"), b and (b["pick"], b["plays"])),
                (("surf_p652ee_css", "600", "mom"), "has one build", "is not in the list",
                 ("css", "surf_p652bb_css")))
        send("ui_mapnet ask")
        same = cl.wait("maplist: the directory's list is the one saved", 15)
        send("ui_mapnet")
        st = cl.wait(r"ui_mapnet: state (\d+) rows (\d+) not kept (\d+)", 10)
        L.check("C  asked again, the same list is known for the same and nothing is rewritten",
                (bool(same), st and st.group(1)), (True, "3"))
        # A list whose every row is refused must not replace the one saved.
        (watch / "mapdl.txt").write_text(HEAD + "\n".join(BAD) + "\n", newline="\n")
        send("ui_mapnet ask")
        none = cl.wait(r"maplist: no row of the directory's list could be kept \((\d+) read\)", 15)
        L.check("C  a list with no row that passes saves nothing: the saved one stands",
                (none and none.group(1), [r for r in net.read_text().splitlines()
                                          if r.startswith("dl ")]), ("9", GOOD))
        (watch / "mapdl.txt").write_text(NET, newline="\n")
        found = []
        for q in ("p652ee_css", "p652bb", "p652nosuch"):
            send("ui_find " + q)
            m = cl.wait(r"ui_find: %s view (\d+) first (\S+)" % q, 8)
            found.append(m and m.groups())
        L.check("C  a search by the name of the folded build finds its map's row; by the "
                "map's own name, one row and not two; by neither, none",
                found, [("1", "surf_p652ee"), ("1", "surf_p652bb"), ("0", "-")])

        # D: a real click on each cell of a row's switch.
        e = build("surf_p652ee")
        ids = e["ids"] if e else (None, None)
        L.check("D  the row's switch was drawn (its two controls have names)",
                bool(ids[0] and ids[1]), True)
        for cell, want in ((ids[1], "surf_p652ee_css"), (ids[0], "surf_p652ee")):
            send("ui_hover @%s" % cell)
            time.sleep(0.4)
            send("ui_mouse down")
            time.sleep(0.2)
            send("ui_mouse up")
            took = cl.wait(r"ui_build: surf_p652ee plays (\S+)", 8)
            time.sleep(0.5)
            send("ui_build surf_p652ee")
            sel = cl.wait(r"plays (\S+); lists", 8)
            send("ui_mapnet sel")
            start = cl.wait(r"ui_mapnet: start plays (\S*)", 8)
            L.check("D  a click on %s: the row plays %s, and start would launch it"
                    % ("CS:S" if want.endswith("_css") else "MOM", want),
                    (took and took.group(1), sel and sel.group(1), start and start.group(1)),
                    (want, want, want))
            if want.endswith("_css"):
                send("screenshot p652_list")
                end, found = time.time() + 15, []
                while time.time() < end and not found:
                    found = list((gd / "screenshots").glob("p652_list.*"))
                    time.sleep(0.5)
                time.sleep(0.8)
                if found:
                    shutil.copyfile(found[0], a.output_dir / ("p652_list" + found[0].suffix))
                L.check("D  ...and the list draws (a screenshot was written)", bool(found), True)
        L.check("no VM error or unknown command in the client's log",
                [w for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow",
                             "p652evil")
                 if w in cl.text()], [])
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
