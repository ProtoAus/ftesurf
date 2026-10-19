#!/usr/bin/env python3
"""Patch 817: a rewind over the attempt a fail teleport ended resumes it timed.

python tools/p817failrewind.py --progs <dir> --out <root> [--lobby] [--control]

surf_dune's fail lands in its start box and re-arms the run. One dedicated server
(developer 1: it prints what it kept and dropped) and one client, cfg/test/p817fail.cfg:
a save on the rewind before the fail, its load, a go from the rewind after a second
fail, then a new run. --lobby: a lobby server on its own basedir (a streamed recorder,
as the Pi). --control: a build without the patch, graded as practice. Run under the
rig lock. Verdicts read the server's lines, the save's files and `cmd timer`.
"""
import argparse
import pathlib
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p808rewind import INSTALL, LOBBY, dist, prepare, samples, state_of, timer, unjunction, view_ticks  # noqa: E402

MAP = "surf_dune"


def section(text, name):
    m = re.search(r"==== P817 " + re.escape(name) + r" ====([\s\S]*?)(?===== P817 |\Z)", text)
    return m.group(1) if m else ""


def grade(sv, cl, svlog, control):
    log = (cl / "logs/p817fail.log").read_text(errors="replace")
    faults = 0

    def check(name, ok, detail):
        nonlocal faults
        faults += not ok
        print(("PASS" if ok else "FAIL"), name, "--", detail, flush=True)

    a = section(log, "A")
    ta = timer(a)
    check("armed", ta and ta["state"] == "armed" and "rewind: on 1" in a, f"after the fail {ta}; open {'rewind: on 1' in a}")
    s = section(log, "S")
    saved = re.search(r"rewind: save (\d+) \(slot (\d+)\) at ([\d:.]+)", s)
    check("s-saved", saved is not None, f"server's save line {saved[0] if saved else None}")
    roots = sorted((sv / f"data/saves/{MAP}").glob("@*")) or [sv / f"data/saves/{MAP}"]
    slot = roots[0] / f"save{int(saved[2]):03}" if saved else sv / "missing"
    st = state_of(slot / "state.txt")
    timed = st.get("state") == "2" and "demoted" not in st and int(st.get("reclines", "0")) > 0
    if control:
        check("s-practice (control)", not timed and st.get("demoted") == "1", f"state {st.get('state')} demoted {st.get('demoted')}")
        print(f"{faults} failed")
        return faults
    check("s-timed", timed, f"state {st.get('state')} demoted {st.get('demoted')} reclines {st.get('reclines')} ticks {st.get('ticks')}")
    rows = (slot / "run.rec").read_text(errors="replace").splitlines() if (slot / "run.rec").exists() else []
    check("s-prefix", timed and len(rows) == int(st.get("reclines", -1)), f"run.rec rows {len(rows)} against reclines {st.get('reclines')}")
    pic = cl / slot.relative_to(sv) / "trail.txt"
    prow = pic.read_text(errors="replace").splitlines()[1:] if pic.exists() else []
    check("s-picture", len(prow) > 10, f"saved trail samples {len(prow)}")
    org = [float(x) for x in st.get("origin", "0 0 0").split()]
    seq = state_of(pic.with_name("seq.txt"))
    apos = [float(x) for x in seq.get("anchorpos", "1e9 1e9 1e9").split()]
    check("s-column", seq and dist(apos, org) < 1, f"seq.txt anchorpos {apos} against the save's origin {org}")
    vt = view_ticks(pic.with_name("run.view"))
    check("s-view", vt and max(vt) <= int(st.get("ticks", -1)) and len(vt) > 10,
          f"run.view {len(vt)} rows, last tick {vt[-1] if vt else None}, save ticks {st.get('ticks')}")
    ld = section(log, "LOAD")
    ev = re.search(r"saveloc: event \d+ op 2 id (\d+)", ld)
    check("load-row", ev is not None and saved is not None and int(ev[1]) == int(saved[2]), f"loaded id {ev[1] if ev else None}")
    tl = timer(ld)
    check("load-run", tl and tl["state"] == "running" and tl["recording"] == 1 and tl["class"] == "segmented",
          f"after loading the S save {tl}")
    sl = samples(ld)
    check("load-line", len(sl) >= 2 and sl[0] > 10 and sl[-1] > sl[0], f"line samples held/released {sl}")
    go = section(log, "GO")
    tg = timer(go.split("rewind key 13")[0]) if "rewind key 13" in go else timer(go)
    counting = "rewind: on 1 counting 1" in go
    check("go-count", counting, f"counting during the hold {counting}")
    after = section(log, "AFTER")
    tf = timer(after)
    check("go-run", "rewind: on 0 counting 0" in after and tf and tf["state"] == "running"
          and tf["recording"] == 1 and tf["class"] == "segmented", f"after the count {tf}")
    gone = re.search(r"rewind: save \d+ \(slot (\d+)\) at [\d:.]+, \d+ u/s -- a resume point", go)
    gslot = roots[0] / f"save{int(gone[1]):03}" if gone else sv / "missing"
    gst = state_of(gslot / "state.txt")
    check("go-timed", gst.get("state") == "2" and "demoted" not in gst, f"resume row state {gst.get('state')} demoted {gst.get('demoted')} ticks {gst.get('ticks')}")
    gorg = [float(x) for x in gst.get("origin", "0 0 0").split()]
    gseq = state_of(cl / gslot.relative_to(sv) / "seq.txt")
    gpos = [float(x) for x in gseq.get("anchorpos", "1e9 1e9 1e9").split()]
    check("go-column", gseq and dist(gpos, gorg) < 1, f"resume row seq.txt anchorpos {gpos} against its origin {gorg}")
    back = re.findall(r"rewind: view lines (\d+) last tick (\d+) back (\d+)", after)
    check("go-view", back and int(back[-1][0]) > 10 and int(back[-1][2]) == 0,
          f"live sidecar after the resume: lines/last/backsteps {back[-1] if back else None}")
    kept = re.findall(r"timer: the failed attempt kept for the rewind: (\d+) lines, (\S+)", svlog)
    check("kept", len(kept) >= 2, f"server keeps {kept}")
    nw = timer(section(log, "NEW"))
    dropped = svlog.count("timer: a new recording drops the kept attempt")
    check("new-drops", nw and nw["state"] == "running" and dropped >= 1, f"new run {nw}; drops {dropped}")
    print(f"{faults} failed")
    return faults


def run(args, svroot, clroot, lobby):
    common = lambda r: ["-basedir", str(r), "-manifest", str(r / "default.fmf")]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", args.port))
    server = subprocess.Popen([args.server, *common(svroot), "+sv_public", "0", "-port", str(args.port),
                               "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p817server",
                               "+set", "developer", "1", "+set", "fs_cache", "0", *(LOBBY if lobby else []), "+map", MAP],
                              cwd=INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(4)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4          # shown, not activated
        client = subprocess.Popen([args.exe, *common(clroot), "-window", "+exec", "cfg/test/p817fail.cfg"],
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
    ap.add_argument("--lobby", action="store_true")
    ap.add_argument("--control", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rig = args.out / time.strftime("rig-%Y%m%dT%H%M%S")
    made = []
    try:
        if args.lobby:
            sv, m = prepare(rig / "server", args.progs, [], args.port)
            made += m
            cl, m = prepare(rig / "client", args.progs, ["p817fail"], args.port)
            made += m
            run(args, rig / "server", rig / "client", True)
            svlogp = rig / "server/ftesurf/logs/p817server.log"
        else:
            sv, m = prepare(rig, args.progs, ["p817fail"], args.port)
            made += m
            cl = sv
            run(args, rig, rig, False)
            svlogp = rig / "ftesurf/logs/p817server.log"
    finally:
        unjunction(made)
    print("rig:", rig)
    if not (cl / "logs/p817fail.log").exists():
        print("FAIL no client log")
        return 1
    svlog = svlogp.read_text(errors="replace") if svlogp.exists() else ""
    return grade(sv, cl, svlog, args.control)


if __name__ == "__main__":
    raise SystemExit(main())
