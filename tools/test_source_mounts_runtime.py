#!/usr/bin/env python3
"""Bounded Windows render falsifier for automatic Source content mounts.

Requires an existing OWNER.md task root, clean build products and installed
Momentum + CS:S + both CS:GO Source 1 layouts. No installation files are changed.
Logs/screenshots stay in owned overlays for inspection and deliberate retirement.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qc", type=Path, required=True)
    parser.add_argument("--progs", type=Path, required=True)
    parser.add_argument("--engine-bin", type=Path, required=True)
    parser.add_argument("--control-install", type=Path, default=Path("C:/FTESurf"))
    args = parser.parse_args()
    if not (args.root / "OWNER.md").is_file():
        parser.error("--root must already have OWNER.md")
    work = args.root / ("runtime-" + str(time.time_ns()))
    work.mkdir()
    results = {}
    cases = [("control", "surf_666", ""), ("automatic", "surf_666", ""),
             ("old-dependency", "surf_666", "steam:Momentum Mod Playtest/mount"),
             ("beta-csgo", "surf_tensor2", "steam:Counter-Strike Global Offensive/csgo"),
             ("standalone-csgo", "surf_tensor2", "steam:csgo legacy/csgo")]
    p = None
    try:
        for label, mapname, dependency in cases:
            rig = work / label
            gd = rig / "ftesurf"
            gd.mkdir(parents=True)
            shutil.copyfile(args.qc / "default.fmf", rig / "default.fmf")
            for name in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
                shutil.copyfile(args.progs / name, gd / name)
            files = subprocess.check_output(["git", "-C", str(args.qc), "ls-files", "ftesurf/cfg"], text=True)
            for rel in files.splitlines():
                if "/test/" in rel:
                    continue
                dst = rig / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(args.qc / rel, dst)
            for name in ("scripts", "glsl"):
                shutil.copytree(args.qc / "ftesurf" / name, gd / name)
            binpath = rig / "bin"
            binpath.mkdir()
            source = args.control_install if label == "control" else args.engine_bin
            exe = source / ("ftesurf64.exe" if label == "control" else "fteqw64.exe")
            shutil.copyfile(exe, binpath / "client.exe")
            for plugin in ("hl2", "ui_imgui"):
                name = "fteplug_" + plugin + "_x64.dll"
                shutil.copyfile(source / name, binpath / name)
            mounts = "steam:Momentum Mod Playtest/momentum\nsteam:Counter-Strike Source/cstrike\n"
            (gd / "fs_addons.txt").write_text(mounts)
            (gd / "data").mkdir()
            deps = "FTESURF-MAPDEPS 1\n"
            if dependency:
                deps += "dep " + mapname + " " + dependency + "\n"
            (gd / "data/mapdeps.txt").write_text(deps)
            cfg = gd / "cfg/test/source.cfg"
            cfg.parent.mkdir(parents=True)
            cfg.write_text("""cfg_save_auto 0
con_savehistory 0
cl_idlefps 0
cl_maxfps 100
set run_resume 0
sv_public 0
fs_lazyaddons 0
fs_assetcache 0
fs_hidesyspaths 0
log_enable 1
log_dir logs
log_name source
log_developer 1
cl_downloads 0
menu_restart
ui_close
map """ + mapname + "\necho SOURCE-MAP-ACTED\n")
            log = gd / "logs/source.log"
            def text():
                return log.read_text(errors="replace") if log.exists() else ""
            def wait(token, timeout=90):
                end = time.monotonic() + timeout
                while time.monotonic() < end:
                    if token in text():
                        return
                    if p.poll() is not None:
                        raise RuntimeError(f"{label}: exited {p.returncode} before {token}")
                    time.sleep(.1)
                raise TimeoutError(label + ": " + token)
            def send(command):
                p.stdin.write((command + "\n").encode())
                p.stdin.flush()
            cmd = [str(binpath / "client.exe"), "-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                   "-plugin", "-window", "-width", "960", "-height", "540", "+exec", "cfg/test/source.cfg"]
            p = subprocess.Popen(cmd, cwd=args.control_install, stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (rig / "pid.json").write_text(json.dumps({"pid": p.pid, "cmd": cmd, "exe_sha256": sha(binpath / "client.exe")}))
            wait("FTESurf CSQC loaded")
            time.sleep(3)
            assets = ["materials/brick/brickfloor001a.vmt", "materials/concrete/concretefloor014a.vtf"]
            if "csgo" in label:
                assets = ["materials/concrete/tunnel_concretewall_01b.vtf"]
            marker = "SOURCE-PROBE-ACTED-" + label
            send("\n".join("flocate " + asset for asset in assets) + "\ncmd viewpos\necho SOURCE-PATH-BEGIN\npath\necho SOURCE-PATH-END\necho " + marker)
            wait(marker, 25)
            current = text()
            if label == "control":
                assert current.count("Not found") >= 2, "missing-pack control did not reproduce"
                assert "texture \"brick/brickfloor001a\"" in current, "control did not request missing material"
            else:
                assert "hl2_dir.vpk became referenced" in current, "automatic base pack was not consumed"
                assert "placeholder.vpk" not in current, "other-game placeholders mounted"
                assert "File is" in current, "file-location probe did not resolve"
                paths = current.split("SOURCE-PATH-BEGIN")[-1].split("SOURCE-PATH-END")[0]
                assert paths.count("mount/hl2_dir.vpk") == 1, "missing/duplicate base searchpath"
                if "csgo" in label:
                    assert "fs_automount: surf_tensor2 needs" in current, "optional dependency did not act"
                    assert "pak01_dir.vpk became referenced" in current, "CS:GO pack not consumed"
                    expected = "csgo legacy/csgo" if label == "standalone-csgo" else "Counter-Strike Global Offensive/csgo"
                    assert expected in paths, "wrong CS:GO layout"
                else:
                    assert "hl2_dir.vpk became referenced" in current, "base pack not consumed"
                    assert "Not found" not in current.split("FTESurf CSQC loaded")[-1], "base probes still missing"
            send("screenshot " + label + ".png")
            wait("ftesurf/screenshots/" + label + ".png", 25)
            assert (gd / "screenshots" / (label + ".png")).stat().st_size > 0
            if label == "automatic":
                send("fs_restart\nmap surf_666\necho SOURCE-RESTART-ACTED")
                wait("SOURCE-RESTART-ACTED", 45)
                time.sleep(12)
                send("echo SOURCE-RESTART-PATH-BEGIN\npath\necho SOURCE-RESTART-PATH-END\nflocate materials/brick/brickfloor001a.vmt\necho SOURCE-RESTART-PROBE-END")
                wait("SOURCE-RESTART-PROBE-END", 25)
                paths = text().split("SOURCE-RESTART-PATH-BEGIN")[-1].split("SOURCE-RESTART-PATH-END")[0]
                assert paths.count("mount/hl2_dir.vpk") == 1, "restart lost/duplicated base pack"
                assert "File is" in text().split("SOURCE-RESTART-PATH-END")[-1], "restart material probe missing"
            send("quit")
            p.wait(timeout=25)
            assert p.returncode == 0, f"{label} abnormal shutdown {p.returncode}"
            results[label] = {"exit": p.returncode, "log": str(log), "sha256": sha(binpath / "client.exe")}
            print(label + ": PASS (acted file and screenshot probes)")
    finally:
        if p is not None and p.poll() is None:
            p.terminate()
            p.wait(timeout=10)
        (work / "results.json").write_text(json.dumps(results, indent=2))
        print("Evidence root:", work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
