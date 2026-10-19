#!/usr/bin/env python3
"""Patch 811: a lobby's saves and the install's own list kept the same.

python tools/p811savesync.py --progs <dir> --out <root> [--control]

One lobby server (its own basedir, as the Pi) and one client install, both under
--out; content through junctions removed afterwards. Run under the rig lock.

  seed   the install holds two offline saves, L1 and L2 (placements)
  join1  the lobby is empty: both go up. The player saves there: S1 idle, S2 on a
         run, S3 held at S2 (one place and view, two rows). S1 and S2 are copied
         into the install, S2 with its picture made a placement's. Deleting L1's
         row moves the install's L1 to deleted/; deleting S3 keeps S2's copy.
  away   (the driver, as an offline session would) the install's copy of S1 is
         deleted and a new offline save L3 appears
  join2  S1 goes from the lobby (deleted here since), L3 goes up; the lobby holds
         L2, S2, L3
  root   a save, a lobby map change, a save: the second save's client files are
         under the new map's folder, not the last one's (BACKLOG, 19 Oct)
  local  the install alone (a local game) lists L2, S2, L3; loading S2 draws its line

Every verdict reads the server's `sl_list` lines, the files, or `savesync status`.
"""
import argparse
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p808rewind import INSTALL, LOBBY, prepare, unjunction  # noqa: E402

MAP = "surf_dune"
MAP2 = "bhop_eazy"              # the map change: its spawn stands at z 64
L1 = (-11910.0, 560.0, 15052.0, 0.0, 90.0)
L2 = (-11850.0, 600.0, 15052.0, 5.0, 45.0)
L3 = (-11790.0, 640.0, 15052.0, -5.0, 135.0)

COMMON = """cfg_save_auto 0
name P811
con_savehistory 0
log_enable 1
log_dir logs
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
set run_resume 0
"""


def state(o, seq):
    return (f"FTESURF-SAVE 1\nmap {MAP}\nseq {seq}\ncreated 20261019-000000\n"
            f"origin {o[0]:.4f} {o[1]:.4f} {o[2]:.4f}\nvelocity 0 0 0\n"
            f"angles {o[3]:.4f} {o[4]:.4f}\nduck 0\ndemoted 1\n")


def last_list(text):
    """Rows of the last `saveloc: N saved on` block."""
    j = text.rfind(" saved on ")
    if j < 0:
        return None
    blk = text[text.rfind("\n", 0, j) + 1:]
    out = []
    for line in blk.splitlines()[1:]:
        m = re.search(r"slot (\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+[\d.]+ u/s.*?yaw\s+(-?\d+)", line)
        if not m:
            break
        out.append(tuple(int(x) for x in m.groups()[1:]))
    return out


def near(row, o):
    return abs(row[0] - o[0]) <= 1 and abs(row[1] - o[1]) <= 1 and abs(row[2] - o[2]) <= 1


def client(args, root, name, text, timeout=120):
    cfg = root / f"ftesurf/cfg/test/{name}.cfg"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(COMMON + f"log_name {name}\n" + text)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 4
    p = subprocess.Popen([args.exe, "-basedir", str(root), "-manifest", str(root / "default.fmf"),
                          "-window", "+exec", f"cfg/test/{name}.cfg"],
                         cwd=INSTALL, startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.wait(timeout=timeout)
    finally:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=10)
    log = root / f"ftesurf/logs/{name}.log"
    return log.read_text(errors="replace") if log.exists() else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--exe", default=str(INSTALL / "ftesurf64.exe"))
    ap.add_argument("--server", default="C:/FTEQuake/fteqwsv64.exe")
    ap.add_argument("--port", type=int, default=27562)
    ap.add_argument("--control", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rig = args.out / time.strftime("rig-%Y%m%dT%H%M%S")
    made = []
    faults = 0

    def check(name, ok, detail):
        nonlocal faults
        faults += not ok
        print(("PASS" if ok else "FAIL"), name, "--", detail, flush=True)

    try:
        sv, m = prepare(rig / "server", args.progs, [], args.port)
        made += m
        cl, m = prepare(rig / "client", args.progs, [], args.port)
        made += m
        here = cl / f"data/saves/{MAP}"
        for i, o in ((1, L1), (2, L2)):
            (here / f"save{i:03}").mkdir(parents=True)
            (here / f"save{i:03}/state.txt").write_text(state(o, i))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", args.port))
        server = subprocess.Popen([args.server, "-basedir", str(rig / "server"), "-manifest", str(rig / "server/default.fmf"),
                                   "+sv_public", "0", "-port", str(args.port), "+set", "log_enable", "1",
                                   "+set", "log_dir", "logs", "+set", "log_name", "p811server", "+set", "fs_cache", "0",
                                   "+set", "rcon_password", "p811", *LOBBY, "+map", MAP], cwd=INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(4)
            j1 = client(args, rig / "client", "p811join1", f"""connect 127.0.0.1:{args.port}
waitmap 60
waitms 8000
menu_restart
ui_close
hud_trail 1
waitms 4000
echo ==== P811 UP ====
savesync status
cmd sl_list
waitms 500
cmd zone_goto 0
waitms 800
sl_save
waitms 800
+forward
waitms 1600
sl_save
waitms 300
-forward
waitms 1200
+sl_hold
waitms 800
sl_save
waitms 500
-sl_hold
waitms 1500
echo ==== P811 SAVED ====
savesync status
cmd sl_list
waitms 500
sl_goto 1
waitms 400
sl_del
waitms 800
sl_goto 9999
waitms 400
sl_del
waitms 1500
echo ==== P811 DELETED ====
savesync status
cmd sl_list
waitms 500
quit
""")
            up = j1.split("==== P811 UP ====")[-1].split("==== P811 SAVED ====")[0]
            lst = last_list(up) or []
            check("up", len(lst) == 2 and any(near(r, L1) for r in lst) and any(near(r, L2) for r in lst),
                  f"the lobby lists the install's two saves {lst}")
            saved = j1.split("==== P811 SAVED ====")[-1].split("==== P811 DELETED ====")[0]
            lst2 = last_list(saved) or []
            srows = [r for r in lst2 if not near(r, L1) and not near(r, L2)]     # S1, S2, S3 in list order
            s1 = srows[0] if len(srows) == 3 else (1e9, 1e9, 1e9)
            s2 = srows[1] if len(srows) == 3 else (1e9, 1e9, 1e9)
            states = {q.parent.name: q.read_text(errors="replace") for q in here.glob("save*/state.txt")}
            mirrors = {n: s for n, s in states.items() if "synced 1" in s}

            def mirror_of(row):
                for n, s in mirrors.items():
                    m = re.search(r"^origin (\S+) (\S+) (\S+)", s, re.M)
                    if m and near([float(x) for x in m.groups()], row):
                        return n
                return None

            check("copied-here", len(lst2) == 5 and len(srows) == 3 and near(srows[2], s2) and len(mirrors) == 2
                  and mirror_of(s1) and mirror_of(s2),
                  f"lobby rows {len(lst2)} (S3 at S2's place: {near(srows[2], s2) if len(srows) == 3 else None}); "
                  f"install copies with `synced 1`: {sorted(mirrors)}")
            m2 = mirror_of(s2)
            pic = (here / m2 / "trail.txt") if m2 else here / "missing"
            prow = pic.read_text(errors="replace").splitlines() if pic.exists() else []
            check("picture", len(prow) > 10 and prow[0].split()[3:5] == ["-1", "0"],
                  f"S2's copy: trail.txt header {prow[0] if prow else None}, {max(0, len(prow) - 1)} samples")
            gone = list((here / "deleted").glob("save*/state.txt")) if (here / "deleted").exists() else []
            dl = j1.split("==== P811 DELETED ====")[-1]
            lst3 = last_list(dl) or []
            check("deleted-there", len(lst3) == 3 and not any(near(r, L1) for r in lst3) and len(gone) == 1
                  and "origin -11910.0000 560.0000" in gone[0].read_text(),
                  f"lobby rows after deleting L1 and S3 {lst3}; install deleted/ {[g.parent.name for g in gone]}")
            check("duplicate-kept", m2 is not None and (here / m2 / "state.txt").exists(),
                  "deleting S3 (S2's place and view) left S2 in the lobby, so the install keeps S2's copy")
            # Away: S1's copy is deleted by hand, and an offline save L3 is made.
            m1 = mirror_of(s1)
            if m1:
                shutil.rmtree(here / m1)
            nid = 1
            while (here / f"save{nid:03}/state.txt").exists():
                nid += 1
            (here / f"save{nid:03}").mkdir(exist_ok=True)
            (here / f"save{nid:03}/state.txt").write_text(state(L3, 50))
            j2 = client(args, rig / "client", "p811join2", f"""connect 127.0.0.1:{args.port}
waitmap 60
waitms 8000
menu_restart
ui_close
waitms 5000
echo ==== P811 JOIN2 ====
savesync status
cmd sl_list
waitms 800
quit
""")
            jj = j2.split("==== P811 JOIN2 ====")[-1]
            lst4 = last_list(jj) or []
            check("rejoin", len(lst4) == 3 and any(near(r, L2) for r in lst4) and any(near(r, L3) for r in lst4)
                  and any(near(r, s2) for r in lst4) and not any(near(r, L1) or near(r, s1) for r in lst4),
                  f"lobby rows after the second visit {lst4}; status {re.findall(r'savesync: copied.*', jj)}")
            # The first save after a lobby map change: its client files go under the new map.
            client(args, rig / "client", "p811root", f"""connect 127.0.0.1:{args.port}
waitmap 60
waitms 8000
menu_restart
ui_close
rcon_password p811
waitms 1000
cmd zone_goto 0
waitms 600
sl_save
waitms 1500
rcon changelevel {MAP2}
waitms 14000
menu_restart
ui_close
waitms 2000
cmd zone_goto 0
waitms 800
sl_save
waitms 2500
echo ==== P811 ROOT ====
savesync status
cmd sl_list
waitms 500
quit
""", timeout=150)
            # The lobby's own folder: @<guid>, not @pending (the root not in) or another map's.
            mine = sorted(q for q in cl.glob(f"data/saves/{MAP2}/@*/save*/seq.txt")
                          if re.fullmatch(r"@[0-9a-f]{32}", q.parent.parent.name))
            stray = [q for q in cl.glob(f"data/saves/{MAP}/@*/save*/seq.txt")
                     if re.search(r"^anchorpos \S+ \S+ 6[0-9]\.", q.read_text(errors="replace"), re.M)]
            check("new-map-root", len(mine) >= 1 and not stray,
                  f"{MAP2}'s save files {[str(q.relative_to(cl)) for q in cl.glob(f'data/saves/{MAP2}/@*/save*/seq.txt')]}; under {MAP}: {[str(q.relative_to(cl)) for q in stray]}")
            rl = (rig / "client/ftesurf/logs/p811root.log").read_text(errors="replace")
            st = re.findall(r"savesync: state (-?\d+) map (\S+) root (\S*)", rl.split("==== P811 ROOT ====")[-1])
            check("new-map-sync", bool(st) and st[0][0] == "4" and st[0][1] == MAP2
                  and re.fullmatch(rf"data/saves/{MAP2}/@[0-9a-f]{{32}}", st[0][2]) is not None,
                  f"after the changelevel: {st}")
        finally:
            if server.poll() is None:
                server.terminate()
                server.wait(timeout=10)
        loc = client(args, rig / "client", "p811local", f"""waitms 3000
map {MAP}
waitmap 60
waitms 6000
menu_restart
ui_close
hud_trail 1
echo ==== P811 LOCAL ====
cmd sl_list
waitms 500
sl_goto 2
waitms 1000
saveloc
trail
cmd timer
waitms 500
quit
""")
        ll = loc.split("==== P811 LOCAL ====")[-1]
        lst5 = last_list(ll) or []
        loaded = re.search(r"saveloc: event \d+ op 2 id (\d+)", ll)
        line = [int(x) for x in re.findall(r"trail: run (\d+) samples", ll)]
        # The root phase's first save (at the spawn, S1's old place) is a fourth row here.
        check("local", len(lst5) == 4 and any(near(r, L2) for r in lst5) and any(near(r, L3) for r in lst5)
              and any(near(r, s2) for r in lst5) and not any(near(r, L1) for r in lst5) and loaded is not None,
              f"a local game's list {lst5}; loaded {loaded[0] if loaded else None}")
        check("local-line", line and line[-1] > 10, f"the line after loading S2's copy: {line}")
    finally:
        unjunction(made)
    print("rig:", rig)
    print(f"{faults} failed")
    return faults


if __name__ == "__main__":
    raise SystemExit(main())
