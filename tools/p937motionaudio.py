#!/usr/bin/env python3
"""Owned muted native motion-audio smoke. No clipboard, consent or public backend.

Requires --progs, --client, --server and --out (under an owned task root).
The real dedicated/client socket uses ordinary input and native body stats;
this is not a movement-accuracy, speaker-output or performance measurement.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import time

import p615link as L


COUNTS = r"motionaudio: supported (\d+) active (\d+) blocks (\d+) hits A (\d+) D (\d+) errors (\d+)"
BODY = r"motionaudio: body ([-\d.]+) anchor ([-\d.]+) target ([-\d.]+) pitch ([-\d.]+) peak ([-\d.]+) queued ([-\d.]+) maxqueue ([-\d.]+)"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progs", type=Path, required=True)
    ap.add_argument("--client", type=Path, required=True)
    ap.add_argument("--server", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--content", type=Path, default=Path("C:/FTESurf"))
    ap.add_argument("--map", default="bhop_eazy")
    a = ap.parse_args()
    a.output_dir = a.out.resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    for p in (a.client, a.server, a.progs / "csprogs.dat"):
        if not p.is_file():
            raise FileNotFoundError(p)
    rig, gd, links = L.build_rig(a)
    print("rig", rig, flush=True)
    client = server = None

    def meta(stopped=False):
        (rig / "process.json").write_text(json.dumps({
            "runner_pid": os.getpid(), "client_pid": client.pid if client else None,
            "server_pid": server.pid if server else None, "rig": str(rig),
            "stopped": stopped}, indent=2))

    try:
        (gd / "downloads/csprogsvers").mkdir(parents=True, exist_ok=True)
        subprocess.run(["python", str(L.ROOT / "tools/seed_csprogs.py"), str(gd / "csprogs.dat")],
                       check=True, capture_output=True)
        port = None
        for candidate in range(27520, 27621):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                try:
                    s.bind(("127.0.0.1", candidate))
                    port = candidate
                    break
                except OSError:
                    pass
        if port is None:
            raise RuntimeError("no free permitted lobby port")
        common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                  "+set", "cfg_save_auto", "0", "+set", "log_enable", "1",
                  "+set", "log_dir", "logs"]
        server = subprocess.Popen([str(a.server), *common, "+set", "log_name", "p937sv",
            "+set", "sv_public", "0", "+set", "sv_port", str(port),
            "+set", "lobby_master", "", "+set", "sv_guidkey", "p937-local-fixture",
            "+set", "sv_maxrate", "0", "+set", "sv_maxdownloadrate", "0", "+map", a.map],
            cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        meta()
        time.sleep(3)
        if server.poll() is not None:
            raise RuntimeError("owned dedicated server exited")
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7                    # own window, minimized/no activation
        client = subprocess.Popen([str(a.client), "-plugin", "-nobrowse", *common,
            "-window", "+set", "log_name", "p937cl", "+set", "con_savehistory", "0",
            "+set", "cl_idlefps", "0", "+set", "cl_maxfps", "100",
            "+set", "volume", "0", "+set", "s_inactive", "0", "+set", "s_al_disable", "1",
            "+set", "rec_terms", "0", "+set", "cl_game_sfx", "0",
            "+set", "cl_surf_tone", "0", "+set", "cl_surf_drums", "0",
            "+set", "cl_surf_audio_volume", "0.15", "+set", "cl_surf_tone_base", "220",
            "+set", "cl_surf_tone_octave", "1024"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)
        meta()
        log = L.Log(gd / "logs/p937cl.log")

        def send(line, pause=.08):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()
            time.sleep(pause)

        serial = 0

        def status(after=""):
            nonlocal serial
            serial += 1
            marker = "P937_QUERY_%d" % serial
            send("echo %s; motionaudio_info%s" % (marker, "; " + after if after else ""))
            if not log.wait(marker, 4):
                raise RuntimeError("native query marker missing")
            c, b = log.wait(COUNTS, 4), log.wait(BODY, 4)
            if not c or not b:
                raise RuntimeError("native motionaudio status missing; inspect owned log")
            return tuple(map(int, c.groups())), tuple(map(float, b.groups()))

        time.sleep(8)
        send("connect 127.0.0.1:%d" % port)
        time.sleep(6)
        send("menu_restart; ui_close; viewsize 100")
        time.sleep(1)
        keys = L.Keys(client.pid)
        keys.VK = {**keys.VK, "a": 0x41, "d": 0x44, "space": 0x20}
        disabled, _ = status()
        keys.press("a")
        keys.press("d")
        still_disabled, _ = status()
        L.check("D default disabled: acted gameplay keys create no stream/hits",
                (disabled, still_disabled), ((1, 0, 0, 0, 0, 0),) * 2)

        send("set cl_surf_drums 1")
        time.sleep(.2)
        keys.hold("a", 3)
        held, kick = status()
        keys.release("a")
        L.check("A one kick for a held/repeated A and real signed16 queue calls",
                (held[1], held[2] > 0, held[3:6], kick[4] > 0), (1, True, (1, 0, 0), True))
        keys.press("a")
        second, _ = status()
        L.check("A release allows another kick", second[3], 2)
        keys.press("d")
        snare, samples = status()
        L.check("D a separate snare and bounded generated samples",
                (snare[4], snare[5], 0 < samples[4] <= .9), (1, 0, True))
        send("chat_open")
        time.sleep(.2)
        keys.type("ad")
        send("chat_rows")
        typed = log.wait(r"chat_rows: draft len (\d+)", 3)
        in_ui, _ = status()
        L.check("UI A/D typed into a real draft, not percussion",
                (typed.group(1) if typed else None, in_ui[3:5]), ("2", snare[3:5]))
        keys.press("esc")
        time.sleep(.2)
        keys.press("a")
        returned, _ = status()
        L.check("UI release/close leaves no stuck A latch", returned[3], 3)

        send("set cl_surf_tone 1; set cl_surf_drums 0; motionaudio_info recenter")
        time.sleep(.2)
        tone, flat = status()
        keys.press("space")
        heights = []
        for _ in range(8):
            _, observed = status()
            heights.append(observed)
        observed_rise = max(x[0] - x[1] for x in heights)
        exact_targets = all(abs(x[2] - 220 * 2 ** ((x[0] - x[1]) / 1024)) < .02 for x in heights)
        L.check("T native body actually rose and the same captured height sets the pitch",
                (tone[1], observed_rise > 1, exact_targets, abs(flat[2] - 220) < .02),
                (1, True, True, True))
        send("set cl_surf_audio_volume 0; set cl_surf_drums 1")
        time.sleep(.3)
        zero_volume, _ = status()
        keys.press("a")
        keys.press("d")
        volume_control, _ = status()
        L.check("V volume0 suppresses both instruments despite acted gameplay keys",
                (volume_control[1], volume_control[2:] == zero_volume[2:]), (0, True))
        send("set cl_surf_audio_volume 0.15; set cl_surf_tone 1; set cl_surf_drums 0")
        time.sleep(.3)
        # Snapshot and switches execute in ONE command-buffer pass, with no
        # intervening render-frame synthesis. Only the stop fade may add a block.
        active_before, _ = status("set cl_surf_tone 0; set cl_surf_drums 0")
        time.sleep(.3)
        stopped, tail = status()
        time.sleep(.3)
        quiescent, drained = status()
        L.check("Q an ACTIVE instrument switches off with exactly one fade, then quiesces",
                (active_before[1], stopped[1], stopped[2] - active_before[2],
                 stopped[2] == quiescent[2], drained[5] <= .002), (1, 0, 1, True, True))
        cycles = []
        for _ in range(3):
            send("set cl_surf_tone 1")
            time.sleep(.2)
            before, _ = status("set cl_surf_tone 0")
            time.sleep(.2)
            after, b = status()
            cycles.append((before[1], after[1], after[2] - before[2], b[5] <= .002))
        L.check("R repeated native drain/restart cycles ACT with one fade and no backlog",
                cycles, [(1, 0, 1, True)] * 3)
        L.check("NATIVE a real mixer queue ACTED (muted only in this owned client)",
                drained[6] > 0, True)
        L.check("No native/builtin/VM error",
                [s for s in ("Unknown command", "QC VM error", "stack overflow",
                             "native signed16 queue unavailable") if s in log.text()], [])
        runs = [p for p in (gd / "data/runs").rglob("*") if p.is_file()] if (gd / "data/runs").exists() else []
        L.check("No run evidence or synthetic consent was written",
                (len(runs), (gd / "data/consent.txt").exists()), (0, False))
        return 1 if L.FAILED else 0
    finally:
        for p in (client, server):
            if p is None or p.poll() is not None:
                continue
            if p is client:
                try:
                    p.stdin.write(b"quit\n")
                    p.stdin.flush()
                    p.wait(timeout=4)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=8)
        meta(True)
        for p in links:
            if not p.exists():
                continue
            if not p.lstat().st_file_attributes & 0x400:
                raise RuntimeError("refusing unlink: not our content junction")
            if not os.path.samefile(p, a.content / "ftesurf" / p.name):
                raise RuntimeError("refusing unlink: unexpected content target")
            p.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
