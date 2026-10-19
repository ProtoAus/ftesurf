#!/usr/bin/env python3
"""Patch 811: does a spawn's save event reach the client before its root (STAT_FS_SAVEROOT)?

python tools/p811rootwait.py --progs <dir> --out <root>

A lobby server and one client (developer 1). The client starts a run, sends `cmd rec_retry`
(the map restarts and the run is restored: SLOP_RETRY in the new VM's first stats),
and reports what its listeners did: the hold's own line ("saves: event N waits for
its root"), the replay's lines, and `rewind status`'s view line count. Run under the
rig lock.
"""
import argparse
import pathlib
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p808rewind import INSTALL, LOBBY, prepare, unjunction  # noqa: E402
from p811savesync import COMMON, MAP, client  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--exe", default=str(INSTALL / "ftesurf64.exe"))
    ap.add_argument("--server", default="C:/FTEQuake/fteqwsv64.exe")
    ap.add_argument("--port", type=int, default=27563)
    ap.add_argument("--tries", type=int, default=3)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rig = args.out / time.strftime("rig-%Y%m%dT%H%M%S")
    made = []
    try:
        sv, m = prepare(rig / "server", args.progs, [], args.port)
        made += m
        cl, m = prepare(rig / "client", args.progs, [], args.port)
        made += m
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", args.port))
        server = subprocess.Popen([args.server, "-basedir", str(rig / "server"), "-manifest", str(rig / "server/default.fmf"),
                                   "+sv_public", "0", "-port", str(args.port), "+set", "log_enable", "1",
                                   "+set", "log_dir", "logs", "+set", "log_name", "p811rw", "+set", "fs_cache", "0",
                                   *LOBBY, "+map", MAP], cwd=INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(4)
            tries = "".join(f"""cmd zone_goto 0
waitms 800
+forward
waitms 2000
-forward
echo ==== P811 RETRY {i} ====
rewind status
cmd rec_retry
waitms 12000
echo ==== P811 BACK {i} ====
rewind status
cmd timer
waitms 500
""" for i in range(args.tries))
            log = client(args, rig / "client", "p811rw", f"""developer 1
connect 127.0.0.1:{args.port}
waitmap 60
waitms 8000
menu_restart
ui_close
hud_trail 1
waitms 3000
{tries}quit
""", timeout=60 + 30 * args.tries)
        finally:
            if server.poll() is None:
                server.terminate()
                server.wait(timeout=10)
        held = re.findall(r"saves: event \d+ waits for its root", log)
        print("held:", len(held))
        for i in range(args.tries):
            seg = log.split(f"==== P811 RETRY {i} ====")[-1].split(f"==== P811 RETRY {i + 1} ====")[0]
            before = re.findall(r"rewind: view lines (\d+)", seg.split(f"==== P811 BACK {i} ====")[0])
            after = re.findall(r"rewind: view lines (\d+)", seg.split(f"==== P811 BACK {i} ====")[-1])
            lines = [l.split(" ", 2)[-1] for l in seg.splitlines()
                     if re.search(r"replay:|waits for its root|restored|retry|timer:|run ", l)][:14]
            print(f"try {i}: view lines before {before} after {after}")
            for l in lines:
                print("   ", l[:160])
        print("pending:", sorted(str(q.relative_to(cl)) for q in cl.glob("data/saves/*/@pending/**/*") if q.is_file()))
    finally:
        unjunction(made)


if __name__ == "__main__":
    main()
