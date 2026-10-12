#!/usr/bin/env python3
"""P681: acted local-server catch-up controls, without owner config/data.

Run with --out beneath an OWNER.md task root and --progs containing a clean
-NoDeploy QC build. The actual product default.cfg is used; only control arms
remove its sv_limittics assignment. Native sv_perfdump counts world ticks.
This does not test mouse interpolation, client prediction or ranked runs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from test_ui_modern import make_map

ROOT = Path(__file__).resolve().parents[1]
ARMS = (("bhop100_control", "bhop", 100, 3, 0.9, 1.1),
        ("bhop20_control", "bhop", 20, 3, 2.8, 3.2),
        ("bhop20_subject", "bhop", 20, 8, 4.8, 5.2),
        ("surf20_control", "surf", 20, 3, 0.9, 1.1),
        ("surf20_subject", "surf", 20, 8, 0.9, 1.1))
PERF = re.compile(r"sv_perfdump \(us per SV_Frame, (\d+) frames, (\d+) ticks\)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_log(process, log, pattern, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        text = log.read_text(errors="replace") if log.exists() else ""
        found = re.search(pattern, text)
        if found:
            return found
        if process.poll() is not None:
            raise RuntimeError(f"owned client exited {process.returncode}: {log}")
        time.sleep(0.1)
    raise RuntimeError(f"log timeout: {pattern}: {log}")


def run_arm(a, arm):
    name, mode, fps, limit, low, high = arm
    rig = a.out / name
    game = rig / "ftesurf"
    rig.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT / "ftesurf/cfg", game / "cfg")
    cfg = game / "cfg/default.cfg"
    if limit == 3:
        # Leave the native engine's original default in effect, not a late override.
        text = cfg.read_text()
        text, count = re.subn(r"^set sv_limittics\s+8\s*$", "", text, flags=re.M)
        if count != 1:
            raise RuntimeError("expected exactly one authored default assignment")
        cfg.write_text(text)
    for folder in ("models", "glsl", "scripts", "particles", "gfx/fonts"):
        source = ROOT / "ftesurf" / folder
        if not source.is_dir():
            source = a.content / "ftesurf" / folder
        if source.is_dir():
            shutil.copytree(source, game / folder)
    for leaf in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
        shutil.copy2(a.progs / leaf, game / leaf)
    for folder in ("maps", "logs"):
        (game / folder).mkdir(exist_ok=True)
    mapname = f"{mode}_p681.map"
    (game / "maps" / mapname).write_text(make_map())
    (rig / "default.fmf").write_text(
        'FTEMANIFEST 1\nGAME FTESurfCatchupFixture\nNAME "P681 catch-up"\n'
        'BASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p681-unused\n')
    lines = ["cfg_save_auto 0", "set con_savehistory 0", "set run_resume 0",
             "set log_enable 1", "set log_dir logs", "set log_name ticks",
             "set log_readable 1", "set cl_idlefps 0", "set cl_maxfps 100",
             "set cl_threadedphysics 0", "set vid_vsync 0", "set sv_public 0",
             'set lobby_dir "http://127.0.0.1:1"', 'set lobby_master ""', 'set cl_run_upload 0',
             'set cl_board_url ""', f"map {mapname}"]
    (game / "probe.cfg").write_text("\n".join(lines) + "\n")
    log = game / "logs/ticks.log"
    process = None
    with (rig / "stdout.txt").open("wb") as output:
        try:
            process = subprocess.Popen(
                [str(a.client), "-plugin", "-nohome", "-noreset", "-nobrowse",
                 "-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                 "-window", "-width", "640", "-height", "480", "-nosound",
                 "+set", "cfg_save_auto", "0", "+exec", "probe.cfg"],
                cwd=a.content, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
            (rig / "owned-process.txt").write_text(str(process.pid) + "\n")
            wait_log(process, log, r"Server spawned\.")
            time.sleep(2)

            def send(line):
                process.stdin.write(line.encode("ascii") + b"\n")
                process.stdin.flush()

            send("cmd viewpos")
            position = wait_log(process, log, r"setpos ([^\r\n]+)").group(1)
            if not any(float(x) != 0 for x in position.split()[:3]):
                raise RuntimeError("a reply before player spawn is not an acting control")
            send("sv_limittics; pm_ticrate; sv_mintic; sv_maxtic")
            wait_log(process, log, rf'"sv_limittics" is "{limit}"')
            text = log.read_text(errors="replace")
            tick = "0.01" if mode == "bhop" else "0.015"
            # Surf's existing world interval is independent of its fixed player
            # mover step. Do not silently turn this default-only fix into a
            # change of world tick policy.
            expected = {"pm_ticrate": tick,
                        "sv_mintic": tick if mode == "bhop" else "0",
                        "sv_maxtic": tick if mode == "bhop" else "0.1"}
            for cvar, value in expected.items():
                if not re.search(rf'"{cvar}" is "{re.escape(value)}"', text):
                    raise RuntimeError(f"wrong or unobserved {cvar}: expected {value}")
            send(f"cl_maxfps {fps}; menu_restart; ui_close; sv_perfdump; echo P681_MEASURE_BEGIN")
            wait_log(process, log, "P681_MEASURE_BEGIN")
            time.sleep(a.seconds)
            send("sv_perfdump; echo P681_MEASURE_END")
            wait_log(process, log, "P681_MEASURE_END")
            text = log.read_text(errors="replace")
            rows = PERF.findall(text)
            if len(rows) != 2:
                raise RuntimeError(f"expected reset and measurement dumps, saw {rows}")
            frames, ticks = map(int, rows[-1])
            ratio = ticks / frames
            if frames < fps * a.seconds * 0.85 or frames > fps * a.seconds * 1.15:
                raise RuntimeError(f"render/server frame-rate control did not act: {frames}")
            if not low <= ratio <= high:
                raise RuntimeError(f"world catch-up outside prediction: {ratio:.4f}")
            return {"frames": frames, "ticks": ticks, "ticks_per_frame": ratio,
                    "fps": fps, "limit": limit, "tick": tick, "spawn": position,
                    "default_sha256": sha(cfg), "log": str(log)}
        finally:
            if process is not None and process.poll() is None:
                try:
                    process.stdin.write(b"quit\n"); process.stdin.flush()
                    process.wait(timeout=10)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    process.terminate(); process.wait(timeout=10)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--progs", type=Path, required=True)
    ap.add_argument("--content", type=Path, default=Path("C:/FTESurf"))
    ap.add_argument("--client", type=Path, default=Path("C:/FTESurf/ftesurf64.exe"))
    ap.add_argument("--seconds", type=float, default=10)
    a = ap.parse_args()
    a.out = a.out.resolve(); a.progs = a.progs.resolve()
    if not any((p / "OWNER.md").is_file() for p in (a.out, *a.out.parents)):
        ap.error("--out must be under a uniquely owned task root")
    if a.seconds < 5:
        ap.error("--seconds must be at least five")
    a.out.mkdir(parents=True, exist_ok=True)
    report = {"utc": datetime.now(timezone.utc).isoformat(), "engine_sha256": sha(a.client),
              "progs_sha256": {p.name: sha(p) for p in a.progs.glob("*.dat")}, "arms": {}}
    try:
        for arm in ARMS:
            result = run_arm(a, arm)
            report["arms"][arm[0]] = result
            print(arm[0], f'{result["ticks"]}/{result["frames"]} ticks/frames = '
                  f'{result["ticks_per_frame"]:.4f}', flush=True)
    finally:
        (a.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
