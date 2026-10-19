#!/usr/bin/env python3
"""Patch 808: a save made on the rewind cursor, and the resume's count.

python tools/p808rewind.py --progs <dir with qwprogs/csprogs/menu> --out <root> [--control]

One dedicated server (surf_dune, buffered recorder) and one client in an
isolated basedir under --out; content comes through junctions that are removed
after the run. Run it under the shared rig lock. The grade reads the server's
own save lines, the save's state file and `cmd timer` -- never the HUD.
"""
import argparse
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALL = pathlib.Path("C:/FTESurf")
CONTENT = ("maps", "gfx", "glsl", "models", "particles", "scripts", "sound", "textures", "progs")


def section(text, name):
    m = re.search(r"==== P808 " + re.escape(name) + r" ====([\s\S]*?)(?===== P808 |\Z)", text)
    return m.group(1) if m else ""


def timer(text):
    """The last `cmd timer` report in a section: state, class, recording, ticks."""
    parts = text.split("timer: ")
    if len(parts) < 2:
        return None
    t = parts[-1]
    tick = re.search(r"tick: counted (\d+)", t)
    rec = re.search(r"practice (\d+)  recording (\d+)", t)
    cls = re.search(r"class: (\w+)", t)
    return {"state": t.split()[0], "ticks": int(tick[1]) if tick else -1,
            "practice": int(rec[1]) if rec else -1, "recording": int(rec[2]) if rec else -1,
            "class": cls[1] if cls else ""}


def samples(text):
    return [int(x) for x in re.findall(r"trail: run (\d+) samples", text)]


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def view_ticks(path):
    """The run-tick column of a .view sidecar's frame rows."""
    if not path.exists():
        return []
    rows = path.read_text(errors="replace").splitlines()
    out = []
    for r in rows[rows.index("begin") + 1:] if "begin" in rows else []:
        f = r.split()
        if len(f) >= 3:
            out.append(int(float(f[2])))
    return out


def state_of(path):
    if not path.exists():
        return {}
    return dict(l.split(" ", 1) for l in path.read_text(errors="replace").splitlines() if " " in l)


def grade(sv, cl, control, mapname):
    log = (cl / "logs/p808rw.log").read_text(errors="replace")
    faults = 0

    def check(name, ok, detail):
        nonlocal faults
        faults += not ok
        print(("PASS" if ok else "FAIL"), name, "--", detail)

    a = section(log, "A")
    ta = timer(a)
    check("acted", ta and ta["state"] == "running" and ta["recording"] == 1 and "rewind: on 1" in a,
          f"the run under the rewind's pin {ta}")
    s = section(log, "S")
    saved = re.search(r"rewind: save (\d+) \(slot (\d+)\) at ([\d:.]+)", s)
    check("s-saved", saved is not None, f"server's save line {saved[0] if saved else None}")
    roots = sorted((sv / f"data/saves/{mapname}").glob("@*")) or [sv / f"data/saves/{mapname}"]
    slot = roots[0] / f"save{int(saved[2]):03}" if saved else sv / "missing"
    pic = cl / slot.relative_to(sv) / "trail.txt"
    st = state_of(slot / "state.txt")
    timed = st.get("state") == "2" and "demoted" not in st and int(st.get("reclines", "0")) > 0
    check("s-timed", timed, f"state {st.get('state')} demoted {st.get('demoted')} reclines {st.get('reclines')} segs {st.get('segs')}")
    rows = (slot / "run.rec").read_text(errors="replace").splitlines() if (slot / "run.rec").exists() else []
    check("s-prefix", timed and len(rows) == int(st.get("reclines", -1)), f"run.rec rows {len(rows)} against reclines {st.get('reclines')}")
    prow = pic.read_text(errors="replace").splitlines()[1:] if pic.exists() else []
    check("s-picture", len(prow) > 10, f"saved trail samples {len(prow)}")
    org = [float(x) for x in st.get("origin", "0 0 0").split()]
    seq = state_of(pic.with_name("seq.txt"))
    apos = [float(x) for x in seq.get("anchorpos", "1e9 1e9 1e9").split()]
    check("s-column", seq and dist(apos, org) < 1, f"seq.txt anchorpos {apos} against the save's origin {org}")
    view = pic.with_name("run.view")
    vt = view_ticks(view)
    check("s-view", vt and max(vt) <= int(st.get("ticks", -1)), f"run.view {len(vt)} rows, last tick {vt[-1] if vt else None}, save ticks {st.get('ticks')}")
    ld = section(log, "LOAD")
    ev = re.search(r"saveloc: event \d+ op 2 id (\d+)", ld)
    check("load-row", ev is not None and saved is not None and int(ev[1]) == int(saved[2]), f"loaded id {ev[1] if ev else None}")
    tl = timer(ld)
    check("load-run", tl and tl["state"] == "running" and tl["recording"] == 1 and tl["class"] == "segmented",
          f"after loading the S save {tl}")
    sl = samples(ld)
    check("load-line", len(sl) >= 2 and sl[0] > 10 and sl[-1] > sl[0], f"line samples held/released {sl}")
    go = section(log, "GO")
    counting = "rewind: on 1 counting 1" in go
    if control:
        check("go-count (control: none expected)", not counting, f"counting {counting}")
    else:
        check("go-count", counting, f"counting during the hold {counting}")
        after = section(log, "AFTER")
        ta = timer(after)
        check("go-run", "rewind: on 0 counting 0" in after and ta and ta["state"] == "running"
              and ta["recording"] == 1 and ta["class"] == "segmented", f"after the count {ta}")
    gone = re.search(r"rewind: save \d+ \(slot (\d+)\) at [\d:.]+, \d+ u/s -- a resume point", go)
    gslot = roots[0] / f"save{int(gone[1]):03}" if gone else sv / "missing"
    gorg = [float(x) for x in state_of(gslot / "state.txt").get("origin", "0 0 0").split()]
    gseq = state_of(cl / gslot.relative_to(sv) / "seq.txt")
    gpos = [float(x) for x in gseq.get("anchorpos", "1e9 1e9 1e9").split()]
    check("go-column", gseq and dist(gpos, gorg) < 1, f"resume row seq.txt anchorpos {gpos} against its origin {gorg}")
    back = re.findall(r"rewind: view lines (\d+) last tick (\d+) back (\d+)", section(log, "AFTER"))
    check("go-view", back and int(back[-1][2]) == 0, f"live sidecar after the resume: lines/last/backsteps {back[-1] if back else None}")
    print(f"{faults} failed")
    return faults


LOBBY = ["+set", "lobby_enable", "1", "+set", "lobby_dir", "", "+set", "lobby_master", "",
         "+set", "sv_guidkey", "p808-fixture", "+set", "rec_enable", "1", "+set", "lobby_norec", "0",
         "+set", "cl_run_upload", "0", "+set", "sv_playerslots", "4", "+set", "sv_maxclients", "4"]


def prepare(root, progs, cfgnames, port):
    """A basedir under root: content through junctions, these progs, the tracked cfgs."""
    gd = root / "ftesurf"
    gd.mkdir(parents=True)
    shutil.copyfile(INSTALL / "default.fmf", root / "default.fmf")
    made = []
    for name in CONTENT:
        src = INSTALL / "ftesurf" / name
        if src.is_dir():
            subprocess.run(["cmd", "/c", "mklink", "/J", str(gd / name), str(src)], check=True, capture_output=True)
            made.append(gd / name)
    for name in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
        shutil.copyfile(progs / name, gd / name)
    shutil.copyfile(INSTALL / "ftesurf/fs_addons.default.txt", gd / "fs_addons.default.txt")
    cfgs = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "ftesurf/cfg"], text=True).splitlines()
    for name in cfgs + [f"ftesurf/cfg/test/{c}.cfg" for c in cfgnames]:
        src = ROOT / name
        if src.is_file():
            dst = root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text().replace("connect 127.0.0.1:27561", f"connect 127.0.0.1:{port}"))
    (gd / "downloads/csprogsvers").mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / "tools/seed_csprogs.py"), str(gd / "csprogs.dat")], check=True, capture_output=True)
    return gd, made


def unjunction(made):
    for path in made:
        if path.lstat().st_file_attributes & 0x400:
            path.rmdir()
        else:
            raise RuntimeError(f"expected a junction: {path}")


def run_pair(args, svroot, clroot, cfgname, lobby):
    common = lambda r: ["-basedir", str(r), "-manifest", str(r / "default.fmf")]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", args.port))
    server = subprocess.Popen([args.server, *common(svroot), "+sv_public", "0", "-port", str(args.port),
                               "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p808server",
                               "+set", "fs_cache", "0", *(LOBBY if lobby else []), "+map", args.map],
                              cwd=INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(4)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4          # shown, not activated
        client = subprocess.Popen([args.exe, *common(clroot), "-window", "+exec", f"cfg/test/{cfgname}.cfg"],
                                  cwd=INSTALL, startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            client.wait(timeout=180)
        finally:
            if client.poll() is None:
                client.terminate()
                client.wait(timeout=10)
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=10)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--exe", default=str(INSTALL / "ftesurf64.exe"))
    ap.add_argument("--server", default="C:/FTEQuake/fteqwsv64.exe")
    ap.add_argument("--port", type=int, default=27561)
    ap.add_argument("--control", action="store_true", help="grade the count as absent")
    ap.add_argument("--map", default="surf_dune")
    ap.add_argument("--lobby", action="store_true", help="a lobby server with its own basedir, as the Pi runs")
    ap.add_argument("--probe", action="store_true", help="run cfg p808probe instead and print its log")
    ap.add_argument("--grade-only", type=pathlib.Path)
    args = ap.parse_args()
    if args.grade_only:
        sv = args.grade_only / ("server" if (args.grade_only / "server").exists() else ".") / "ftesurf"
        cl = args.grade_only / ("client" if (args.grade_only / "client").exists() else ".") / "ftesurf"
        return grade(sv, cl, args.control, args.map)
    args.out.mkdir(parents=True, exist_ok=True)
    rig = args.out / time.strftime("rig-%Y%m%dT%H%M%S")
    cfgname = "p808probe" if args.probe else "p808rw"
    made = []
    try:
        if args.lobby:
            sv, m1 = prepare(rig / "server", args.progs, [], args.port)
            made += m1
            cl, m2 = prepare(rig / "client", args.progs, [cfgname], args.port)
            made += m2
            run_pair(args, rig / "server", rig / "client", cfgname, True)
        else:
            sv, m1 = prepare(rig, args.progs, [cfgname], args.port)
            made += m1
            cl = sv
            run_pair(args, rig, rig, cfgname, False)
    finally:
        unjunction(made)
    print("rig:", rig)
    if args.probe:
        print((cl / "logs/p808probe.log").read_text(errors="replace"))
        return 0
    if not (cl / "logs/p808rw.log").exists():
        print("FAIL no client log")
        return 1
    return grade(sv, cl, args.control, args.map)


if __name__ == "__main__":
    raise SystemExit(main())
