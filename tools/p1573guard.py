#!/usr/bin/env python3
"""Patch 1573: the ranked profile names injected clicks and touchpads.

python tools/p1573guard.py --progs <dir> --out <root> [--control]

One dedicated server and one client on a fresh basedir (cfg/test/p1573guard.cfg). Graded from the
client's `cmd timer` replies: the server's own `inguard` line and its `inprof ... would/why`.
--control: progs without the patch, where the guard settings change nothing. Run under the rig lock.
"""
import argparse
import pathlib
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p808rewind import INSTALL, prepare, timer, unjunction  # noqa: E402

MAP = "surf_dune"


def section(text, name):
    m = re.search(r"==== P1573 " + re.escape(name) + r" ====([\s\S]*?)(?===== P1573 |\Z)", text)
    return m.group(1) if m else ""


def last(pattern, text):
    found = re.findall(pattern, text)
    return found[-1] if found else None


def grade(cl, control):
    log = (cl / "logs/p1573guard.log").read_text(errors="replace")
    faults = 0

    def check(name, ok, detail):
        nonlocal faults
        faults += not ok
        print(("PASS" if ok else "FAIL"), name, "--", detail, flush=True)

    prof = r"would (\d)  why (\w+)"
    guard = r"inguard: said (\S+)  have (\S+)  nolegacy (\S+)  touchpad (\S+)"
    m = section(log, "MIGRATED")
    noleg = last(r'"in_rawinput_nolegacy" is "([^"]*)"', m)
    touch = last(r'"in_rawinput_touchpad" is "([^"]*)"', m)
    if control:
        check("migrated (control: none)", noleg == "0" and last(guard, m) is None, f"nolegacy {noleg} touchpad {touch} guard {last(guard, m)}")
        c = section(log, "CLICKS")
        check("clicks (control: ranks)", last(prof, c) == ("0", "ok"), f"would/why {last(prof, c)}")
        t = section(log, "TOUCHPAD")
        check("touchpad (control: ranks)", last(prof, t) == ("0", "ok"), f"would/why {last(prof, t)}")
        print(f"{faults} failed")
        return faults
    check("migrated", noleg == "1" and touch == "0", f"nolegacy {noleg} touchpad {touch}")
    check("migrated-said", last(guard, m) == ("1", "3", "1", "0") and last(prof, m) == ("0", "ok"),
          f"guard {last(guard, m)} would/why {last(prof, m)}")
    c = section(log, "CLICKS")
    check("clicks", last(guard, c) == ("1", "3", "0", "0") and last(prof, c) == ("1", "clicks"),
          f"guard {last(guard, c)} would/why {last(prof, c)}")
    t = section(log, "TOUCHPAD")
    check("touchpad", last(guard, t) == ("1", "3", "1", "1") and last(prof, t) == ("1", "touchpad"),
          f"guard {last(guard, t)} would/why {last(prof, t)}")
    o = section(log, "OK")
    # Idle, `would` is judged against the last start's latch, so the earlier steps read `changed`.
    check("ok", last(guard, o) == ("1", "3", "1", "0") and last(prof, o) in (("0", "ok"), ("1", "changed")),
          f"guard {last(guard, o)} would/why {last(prof, o)}")
    md = section(log, "MIDRUN")
    tm = timer(md)
    badat = last(r"badat (-?\d+)", md)
    check("midrun", tm and tm["state"] == "running" and tm["class"] == "clean" and badat is not None
          and int(badat) >= 0 and last(prof, md) == ("1", "changed"),
          f"{tm} badat {badat} would/why after a toggle mid-run {last(prof, md)}")
    print(f"{faults} failed")
    return faults


def run(args, root):
    common = ["-basedir", str(root), "-manifest", str(root / "default.fmf")]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", args.port))
    server = subprocess.Popen([args.server, *common, "+sv_public", "0", "-port", str(args.port),
                               "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p1573server",
                               "+set", "fs_cache", "0", "+map", MAP],
                              cwd=INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(4)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4          # shown, not activated
        client = subprocess.Popen([args.exe, *common, "-window", "+exec", "cfg/test/p1573guard.cfg"],
                                  cwd=INSTALL, startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            client.wait(timeout=150)
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
    ap.add_argument("--control", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rig = args.out / time.strftime("rig-%Y%m%dT%H%M%S")
    made = []
    try:
        gd, made = prepare(rig, args.progs, ["p1573guard"], args.port)
        run(args, rig)
    finally:
        unjunction(made)
    print("rig:", rig)
    if not (gd / "logs/p1573guard.log").exists():
        print("FAIL no client log")
        return 1
    return grade(gd, args.control)


if __name__ == "__main__":
    raise SystemExit(main())
