#!/usr/bin/env python3
"""Isolated dedicated-client SUI falsifier; never uses the owner's config/data.

Each run creates a fresh marked rig, copies explicit binaries/content, loads a
synthetic raw MAP, seeds the exact csprogs hash and owns only its Popen handles.
--missing-mask proves graceful fallback in a fresh renderer, not a warm cache.
--grade-only PATH grades an existing rig without launching or modifying it.
Exit 0 pass, 1 failed prediction, 2 not reached/cannot grade.
"""
import argparse
import hashlib
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_map():
    return '''{\n"classname" "worldspawn"\n{
( -512 -512 -32 ) ( -512 512 -32 ) ( 512 512 -32 ) stone 0 0 0 1 1
( -512 -512 0 ) ( 512 -512 0 ) ( 512 512 0 ) stone 0 0 0 1 1
( -512 -512 -32 ) ( 512 -512 -32 ) ( 512 -512 0 ) stone 0 0 0 1 1
( 512 512 -32 ) ( -512 512 -32 ) ( -512 512 0 ) stone 0 0 0 1 1
( -512 512 -32 ) ( -512 -512 -32 ) ( -512 -512 0 ) stone 0 0 0 1 1
( 512 -512 -32 ) ( 512 512 -32 ) ( 512 512 0 ) stone 0 0 0 1 1
}\n}\n{\n"classname" "info_player_start"\n"origin" "0 0 128"\n"angle" "0"\n}\n'''


def prepare(args):
    # Refuse a busy port before starting any process; no owner server is stopped.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", args.port))
    rig = ROOT / "rig" / ("ui-modern-" + time.strftime("%Y%m%d-%H%M%S"))
    rig.mkdir(parents=True, exist_ok=False)
    (rig / "UI_TEST_RIG.txt").write_text("Owned disposable SUI test install\n")
    game = rig / "ftesurf"
    for folder in ("cfg", "glsl", "scripts", "particles", "models", "gfx/fonts", "textures"):
        src = ROOT / "ftesurf" / folder
        if src.is_dir():
            shutil.copytree(src, game / folder)
    for folder in ("maps", "logs", "downloads/csprogsvers", "gfx/ui"):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for name in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
        shutil.copy2(ROOT / "ftesurf" / name, game / name)
    if not args.missing_mask:
        shutil.copy2(ROOT / "ftesurf/gfx/ui/roundmask.png", game / "gfx/ui/roundmask.png")
    shutil.copy2(ROOT / "default.fmf", rig / "default.fmf")
    shutil.copy2(args.exe, rig / "ftesurf64.exe")
    shutil.copy2(args.server, rig / "fteqwsv64.exe")
    plugin = args.exe.parent / "fteplug_hl2_x64.dll"
    if plugin.is_file():
        shutil.copy2(plugin, rig / plugin.name)
    config = game / "cfg/test/ui_modern.cfg"
    text = config.read_text()
    text = text.replace("vid_width 1280", f"vid_width {args.width}")
    text = text.replace("vid_height 720", f"vid_height {args.height}")
    text = text.replace("set hud_scale 1\n", f"set hud_scale {args.scale}\n")
    text = text.replace("vid_conautoscale 1\n", f"vid_conautoscale {args.conscale}\n")
    config.write_text(text)
    (game / "maps/ui_modern.map").write_text(make_map())
    (game / "cfg/test/ui_modern_connect.cfg").write_text(f"connect 127.0.0.1:{args.port}\n")
    (game / "cfg/test/ui_modern_server.cfg").write_text(
        "cfg_save_auto 0\nlog_enable 1\nlog_dir logs\nlog_name ui_modern_server\n"
        "sv_public 0\nset lobby_dir \"\"\nsv_maxclients 4\n"
        f"sv_port {args.port}\nsv_cheats 1\nmap ui_modern.map\nwaitms 1000\nsv_gravity 0\n"
    )
    subprocess.run(["python", str(ROOT / "tools/seed_csprogs.py"), str(game / "csprogs.dat")],
                   check=True, stdout=subprocess.DEVNULL)
    provenance = [f"{name} {digest(game / name)}" for name in ("qwprogs.dat", "csprogs.dat", "menu.dat")]
    provenance += [f"{name} {digest(rig / name)}" for name in ("ftesurf64.exe", "fteqwsv64.exe")]
    if plugin.is_file():
        provenance.append(f"{plugin.name} {digest(rig / plugin.name)}")
    (rig / "provenance.txt").write_text("\n".join(provenance) + "\n")
    return rig


def run(args, rig):
    flags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    server = client = None
    try:
        server = subprocess.Popen([str(rig / "fteqwsv64.exe"), "-basedir", str(rig),
                                   "+exec", "test/ui_modern_server.cfg"],
                                  cwd=args.cwd, creationflags=flags,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        if server.poll() is not None:
            raise RuntimeError("owned server exited before client launch")
        client = subprocess.Popen([str(rig / "ftesurf64.exe"), "-basedir", str(rig),
                                   "+exec", "test/ui_modern.cfg"], cwd=args.cwd,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client.wait(timeout=args.timeout)
    finally:
        # These handles identify only processes this invocation created.
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def sections(path):
    result, current = {}, None
    for line in path.read_text(errors="replace").splitlines():
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", line)
        match = re.search(r"=== sui (\w+) ===", line)
        if match:
            current = match.group(1)
            result[current] = []
        elif current:
            result[current].append(line)
    return result


def values(lines, prefix, pattern, index=0):
    rows = [line for line in lines if line.startswith(prefix)]
    if len(rows) <= index:
        return None
    match = re.fullmatch(pattern, rows[index])
    return tuple(float(x) for x in match.groups()) if match else None


def grade(rig, missing_mask=False):
    log = rig / "ftesurf/logs/ui_modern.log"
    if not log.is_file():
        print("CANNOT GRADE: no client log; inspect rig server/startup logs")
        return 2
    s = sections(log)
    needed = ("A", "B", "delayed", "visible", "cached", "held", "action", "focuslost", "focusback", "keyboardlost", "keyboardback", "edge", "closed1", "closed2", "done")
    if any(name not in s for name in needed):
        print("CANNOT GRADE: missing stages", [name for name in needed if name not in s])
        return 2
    if any("sui_probe: no control" in line or "Unknown command" in line for rows in s.values() for line in rows):
        print("CANNOT GRADE: a control/command was not reached")
        return 2
    fails = 0

    def check(ok, message):
        nonlocal fails
        fails += not ok
        print(("PASS " if ok else "FAIL ") + message)

    probe = r"sui_probe round (\S+) asset (\S+) tip (\S+) lines (\S+) wraps (\S+)"
    panel = r"sui_panel open (\S+) selected (\S+) dirty (\S+) cursor (\S+) held (\S+)"
    work = r"sui_work frames (\S+) quads (\S+) screen (\S+) (\S+) focused (\S+)"
    ps = {name: values(rows, "sui_probe ", probe) for name, rows in s.items()}
    if any(ps[name] is None for name in needed if name != "done"):
        print("CANNOT GRADE: required frontend probes did not act")
        return 2
    a = ps["A"]
    b = ps["B"]
    check(a is not None and a[0] == 0, "no rounded drawing before the editor opens")
    check(b is not None and ((b[0] > 0 and b[1] == 1) if not missing_mask else (b[0] == 0 and b[1] == 0)),
          "real panel draws rounding, or explicit missing-mask fallback")
    check(ps["delayed"] is not None and ps["delayed"][2] == 0, "tooltip is not shown before delay")
    check(ps["visible"] is not None and ps["visible"][2] == 1 and ps["visible"][3] >= 2, "tooltip appears and actually wraps")
    check(ps["cached"] is not None and ps["visible"] is not None and ps["cached"][4] == ps["visible"][4], "steady hover does not rebuild wrapped strings")
    check(ps["held"] is not None and ps["held"][2] == 0, "held mouse clears tooltip")
    check(ps["focuslost"] is not None and ps["focuslost"][2] == 0, "whole-chain focus-loss probe clears tooltip")
    check(ps["focusback"] is not None and ps["focusback"][2] == 1, "fresh focus restores delayed tooltip")
    check(ps["keyboardlost"] is not None and ps["keyboardlost"][2] == 0, "keyboard-only loss with unchanged mouse clears tooltip")
    check(ps["keyboardback"] is not None and ps["keyboardback"][2] == 1, "keyboard-only restoration preserves unchanged mouse focus")
    ap = values(s["B"], "sui_panel ", panel)
    bp = values(s["action"], "sui_panel ", panel)
    check(ap is not None and bp is not None and bp[1] >= 0 and bp[1] != ap[1], "real selection action changes the selection")
    close = values(s["closed2"], "sui_panel ", panel)
    check(close is not None and close[0] == 0 and close[3] == 0, "closed editor releases its cursor claim")
    w1 = values(s["closed1"], "sui_work ", work)
    w2 = values(s["closed2"], "sui_work ", work)
    check(w1 is not None and w2 is not None and w1[:2] == w2[:2], "closed UI performs no additional SUI frames or round submissions")
    font = values(s["visible"], "sui_font ", r"sui_font native (\S+) ratio (\S+) (\S+) glyph (\S+) (\S+) calls (\S+)")
    source = (ROOT / "src/shared/sh_font.qc").read_text()
    ladder = re.search(r'#define FONT_UI_SIZES\s+"([^"]+)"', source)
    baked = tuple(float(n) for n in ladder[1].split()) if ladder else ()
    check(font is not None and font[0] in baked and font[5] > 0
          and abs(font[3]*font[1]-font[0]) < .001 and abs(font[4]*font[2]-font[0]) < .001,
          "text requests a baked physical-pixel size on both axes, not fractional glyph scaling")
    bounds = values(s["visible"], "sui_tip ", r"sui_tip \[[^]]*\] (\S+) (\S+) (\S+) (\S+)")
    frame = values(s["visible"], "sui_work ", work)
    check(bounds is not None and frame is not None and bounds[0] >= 0 and bounds[1] >= 0
          and bounds[0]+bounds[2] <= frame[2]+1 and bounds[1]+bounds[3] <= frame[3]+1, "tooltip bounds fit the screen")
    widths = [re.fullmatch(r"sui_tip_line \d+ width (\S+) limit (\S+)", line) for line in s["visible"] if line.startswith("sui_tip_line ")]
    check(bool(widths) and all(m and float(m[1]) <= float(m[2])+1 for m in widths), "each actual wrapped line fits its width")
    alltext = log.read_text(errors="replace")
    check("hud_edit: layout saved" in alltext or "layout saved to ftesurf.cfg" in alltext,
          "dirty close acted and explicitly saved into the disposable rig")
    edge = values(s["edge"], "sui_tip ", r"sui_tip \[[^]]*\] (\S+) (\S+) (\S+) (\S+)")
    check(ps["edge"] is not None and ps["edge"][2] == 1 and edge is not None and frame is not None
          and edge[0] >= 0 and edge[1] >= 0 and edge[0]+edge[2] <= frame[2]+1
          and edge[1]+edge[3] <= frame[3]+1, "lower-right hover tooltip is clamped on screen")
    shots = {}
    for stem in ("sui_A", "sui_A_repeat", "sui_B", "sui_B_repeat", "sui_tip", "sui_edge"):
        matches = list((rig / "ftesurf").rglob(stem + ".png"))
        check(len(matches) == 1, "screenshot captured: " + stem)
        if len(matches) == 1:
            shots[stem] = matches[0]
    if len(shots) == 6:
        from PIL import Image, ImageChops
        images = {name: Image.open(path).convert("RGB") for name, path in shots.items()}
        pbox = next((re.fullmatch(r"sui_element \[he_panel\] (\S+) (\S+) (\S+) (\S+)", line)
                     for line in s["B"] if line.startswith("sui_element [he_panel]")), None)
        aframe = values(s["B"], "sui_work ", work)
        if pbox and aframe and len({im.size for im in images.values()}) == 1:
            w, h = images["sui_A"].size
            x, y, pw, ph = map(float, pbox.groups())
            sx, sy = w/aframe[2], h/aframe[3]
            box = (int(x*sx), int(y*sy), int((x+pw)*sx), int((y+ph)*sy))
            def difference(a, b, region):
                data = ImageChops.difference(images[a].crop(region), images[b].crop(region)).tobytes()
                return sum(data[i:i+3] != b"\0\0\0" for i in range(0, len(data), 3))
            floor_a = difference("sui_A", "sui_A_repeat", box)
            floor_b = difference("sui_B", "sui_B_repeat", box)
            changed = difference("sui_A_repeat", "sui_B_repeat", box)
            print(f"Pixels: closed floor {floor_a}, open floor {floor_b}, panel delta {changed}")
            check(floor_a < 30 and floor_b < 30, "same-state repeats establish a low noise floor")
            check(changed > 100, "the open editor actually changes visible pixels")
        else:
            check(False, "pixel geometry/dimensions are gradeable")
    check((rig / "ftesurf/ftesurf.cfg").is_file(), "explicit config save exists in the rig")
    print(f"Result: {fails} failed; runtime route probes, not actual-device/fleet/ImGui acceptance")
    return 1 if fails else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=Path("C:/FTESurf/ftesurf64.exe"))
    parser.add_argument("--server", type=Path, default=Path("C:/FTEQuake/fteqwsv64.exe"))
    parser.add_argument("--cwd", type=Path, default=Path("C:/FTESurf"))
    parser.add_argument("--port", type=int, default=27561)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--scale", type=float, default=1)
    parser.add_argument("--conscale", type=float, default=1)
    parser.add_argument("--missing-mask", action="store_true")
    parser.add_argument("--grade-only", type=Path)
    args = parser.parse_args()
    if args.grade_only:
        return grade(args.grade_only, args.missing_mask)
    if not 27520 <= args.port <= 27620:
        parser.error("dedicated UI port must be 27520..27620")
    if args.width < 640 or args.height < 480 or not 0.5 <= args.scale <= 2 or not 1 <= args.conscale <= 2:
        parser.error("test size must be >=640x480 and scale 0.5..2")
    rig = prepare(args)
    print("Rig:", rig)
    run(args, rig)
    return grade(rig, args.missing_mask)


if __name__ == "__main__":
    raise SystemExit(main())
