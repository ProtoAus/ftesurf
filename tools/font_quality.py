#!/usr/bin/env python3
"""Disposable native-font gallery and structural pixel controls, NOT a beauty score.

python tools/font_quality.py
python tools/font_quality.py --conscale 2 --linear 0
python tools/font_quality.py grade <rig-dir>
python tools/font_quality.py compare <rig-a> <rig-b>
See tools/font_quality.md for predictions, limits and the renderer acceptance gate.
Requires Windows FTE, fteqcc and Pillow. Never modifies/deploys a live menu or config.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
FONTS = ("Roboto.ttf", "GoogleMed.ttf", "BebasNeueRegular.ttf")
SIZES = ((8, 12, 16, 24), (8, 12, 16, 24), (12, 16, 20, 24))
SIZE = (1280, 720)
PHASES = ("baseline", "repeat", "resampled", "menu_reload", "renderer_reload")
MODES = (0, 0, 1, 0, 0)
MARKERS = (((630, 18, 650, 38), (255, 0, 255)),
           ((630, 50, 650, 70), (0, 255, 0)),
           ((18, 18, 26, 700), (0, 0, 0)),
           ((1250, 18, 1260, 700), (255, 255, 255)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_box(side: int, face: int, rung: int) -> tuple[int, int, int, int]:
    x, y = 32 + side * 640, 72 + face * 192 + rung * 48
    return x, y, x + 576, y + 36


def changed_pixels(a: Image.Image, b: Image.Image) -> int:
    if a.size != b.size:
        raise ValueError(f"image dimensions differ: {a.size} != {b.size}")
    delta = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    return sum(count for count, colour in delta.getcolors(delta.width * delta.height)
               if colour != (0, 0, 0))


def image_metrics(image: Image.Image) -> list[dict]:
    """Report coverage/levels/bounds per crop; do not rank sharpness or quality."""
    metrics = []
    for side in range(2):
        background = 0 if side == 0 else 255
        for face in range(3):
            for rung in range(4):
                box = sample_box(side, face, rung)
                crop = image.crop(box).convert("RGB")
                counts = {rgb: n for n, rgb in crop.getcolors(crop.width * crop.height)}
                levels = sorted({rgb[0] for rgb in counts if rgb[0] == rgb[1] == rgb[2]
                                 and rgb[0] != background})
                bounds = ImageChops.difference(crop, Image.new("RGB", crop.size,
                                              (background,) * 3)).getbbox()
                metrics.append(dict(side=side, face=face, rung=rung,
                                    pixels=SIZES[face][rung], box=box,
                                    ink=sum(n for rgb, n in counts.items()
                                            if rgb != (background,) * 3),
                                    grey_levels=len(levels), bounds=bounds,
                                    nongrey=sum(n for rgb, n in counts.items()
                                                if not rgb[0] == rgb[1] == rgb[2])))
    return metrics


def assess_images(images: dict[str, Image.Image]) -> tuple[list[str], list[dict]]:
    errors = []
    for phase in PHASES:
        if phase not in images:
            errors.append(f"{phase}: missing screenshot")
        elif images[phase].size != SIZE:
            errors.append(f"{phase}: dimensions {images[phase].size}, want {SIZE}")
    if errors:
        return errors, []
    for phase, image in images.items():
        for box, colour in MARKERS:
            if image.crop(box).convert("RGB").getextrema() != tuple((v, v) for v in colour):
                errors.append(f"{phase}: geometry/colour marker {box} != {colour}")
    metrics = image_metrics(images["baseline"])
    for m in metrics:
        label = f"side {m['side']} face {m['face']} rung {m['rung']}"
        if m["ink"] < 20 or m["ink"] > 576 * 36 // 2 or m["grey_levels"] < 3:
            errors.append(f"{label}: glyphs absent/opaque/aliased: {m}")
        if m["nongrey"]:
            errors.append(f"{label}: non-neutral ink (colour/fringe/overlay)")
        bounds = m["bounds"]
        if bounds and (bounds[2] >= 575 or bounds[3] >= 35):
            errors.append(f"{label}: sample touches crop boundary")
        crop = images["baseline"].crop(sample_box(m["side"], m["face"], m["rung"]))
        repeat = images["repeat"].crop(sample_box(m["side"], m["face"], m["rung"]))
        mutant = images["resampled"].crop(sample_box(m["side"], m["face"], m["rung"]))
        if changed_pixels(crop, repeat):
            errors.append(f"{label}: same-process repeat changed")
        if changed_pixels(crop, mutant) < 20:
            errors.append(f"{label}: non-native request did not visibly act")
    for side in range(2):
        # All three faces have a 16px sample; this catches collapsed/default slots.
        samples = [images["baseline"].crop(sample_box(side, face, 2 if face < 2 else 1))
                   for face in range(3)]
        for a, b in ((0, 1), (0, 2), (1, 2)):
            if changed_pixels(samples[a], samples[b]) < 20:
                errors.append(f"side {side}: faces {a}/{b} collapsed to the same image")
        # The 0.5 premultiplied line must be visible and stop at half contrast.
        x = 32 + side * 640
        extrema = images["baseline"].crop((x, 650, x + 576, 674)).convert("L").getextrema()
        peak = extrema[1] if side == 0 else 255 - extrema[0]
        if not 100 <= peak <= 129:
            errors.append(f"side {side}: half-alpha contrast {peak}, expected 100..129")
    for phase in ("repeat", "menu_reload", "renderer_reload"):
        if changed_pixels(images["baseline"], images[phase]):
            errors.append(f"whole-gallery {phase} differs (not just glyph crops)")
    return errors, metrics


def assess_log(text: str, conscale: float, linear: int) -> list[str]:
    errors = []
    if "FQ_END" not in text:
        errors.append("fixture end marker absent")
    if re.search(r"Unknown command|QC runtime error|Unable to load font", text, re.I):
        errors.append("engine command/font/runtime error in log")
    for phase, mode in zip(PHASES, MODES):
        match = re.search(rf"FQ_PHASE {phase}\s*\n(.*?)(?=FQ_PHASE |FQ_END)", text, re.S)
        if not match:
            errors.append(f"{phase}: no measured phase")
            continue
        part = match[1]
        state = re.findall(r"fq_state mode (\S+) frames (\S+) loads (\S+) ready (\S+) calls (\S+)", part)
        if len(state) != 1 or (state and (float(state[0][0]) != mode
                or float(state[0][1]) < 2 or tuple(map(float, state[0][2:])) != (1, 1, 24))):
            errors.append(f"{phase}: state not acted/ready/single-load: {state}")
        native = re.findall(r"fq_native tries (\S+) (\S+) (\S+) (\S+)", part)
        if len(native) != 1 or (native and tuple(map(float, native[0])) != (1, 0, 1, 1)):
            errors.append(f"{phase}: physical mirror initialization not bounded/acted: {native}")
        screen = re.findall(r"fq_screen physical (\S+) (\S+) virtual (\S+) (\S+) ratio (\S+) (\S+)", part)
        if len(screen) != 1:
            errors.append(f"{phase}: no single screen probe")
        else:
            pw, ph, vw, vh, rx, ry = map(float, screen[0])
            if ((pw, ph) != SIZE or abs(rx - conscale) > .02 or abs(ry - conscale) > .02
                    or abs(vw * rx - pw) > .01 or abs(vh * ry - ph) > .01):
                errors.append(f"{phase}: physical/virtual scale not acted: {screen[0]}")
        settings = re.findall(r"fq_settings linear (\S+) mono (\S+) outline (\S+) smaller (\S+) gamma (\S+) contrast (\S+) srgb (\S+)", part)
        if len(settings) != 1 or (settings and tuple(map(float, settings[0])) != (linear, 0, 0, 0, 1, 1, 0)):
            errors.append(f"{phase}: settings differ: {settings}")
        rows = re.findall(r"fq_row (\d+) (\d+) (\d+) slot (\d+) physical (\S+) (\S+) origin (\S+) (\S+)", part)
        seen = set()
        for side, face, rung, slot, px, py, x, y in rows:
            key = tuple(map(int, (side, face, rung)))
            if key in seen or key not in {(s, f, r) for s in range(2) for f in range(3) for r in range(4)}:
                errors.append(f"{phase}: unexpected/repeated row {key}")
                continue
            seen.add(key)
            s, f, r = key
            wanted = SIZES[f][r] + (.75 if mode else 0)
            if int(slot) <= 0 or (float(px), float(py)) != (wanted, wanted) or (float(x), float(y)) != sample_box(s, f, r)[:2]:
                errors.append(f"{phase}: invalid physical bake/origin/slot: {key}")
        if len(seen) != 24:
            errors.append(f"{phase}: {len(seen)}/24 unique measured rows")
    return errors


def cfg_text() -> str:
    lines = ["cfg_save_auto 0", "cl_idlefps 0", "cl_maxfps 100", "show_fps 0",
             "scr_conspeed 100000", "con_notifytime 0",
             "defer 0.5 menu_restart", "defer 0.8 fq_open"]
    # Open the controlled MQC, not the game's saved menu or terms screen.
    lines += ["defer 6.3 menu_restart", "defer 6.5 fq_open", "defer 9 vid_restart",
              "defer 9.8 fq_open"]
    for phase, mode, at in zip(PHASES, MODES, (2, 3.5, 5, 7.5, 10.5)):
        lines += [f"defer {at} echo FQ_PHASE {phase}", f"defer {at + .1} set fq_mode {mode}",
                  f"defer {at + .2} fq_probe",
                  f"defer {at + .5} screenshot {phase}.png"]
    lines += ["defer 12 echo FQ_END", "defer 12.5 quit"]
    return "\n".join(lines) + "\n"


def launch(args: argparse.Namespace) -> Path:
    if sys.platform != "win32":
        raise RuntimeError("launch requires Windows; grade/unit controls are portable")
    engine, compiler = Path(args.engine).resolve(), Path(args.compiler).resolve()
    for path in (engine, compiler, ROOT / "src/defs/m_defs.qc", ROOT / "src/shared/sh_font.qc",
                 *(ROOT / "ftesurf/gfx/fonts" / font for font in FONTS)):
        if not path.is_file():
            raise FileNotFoundError(path)
    (ROOT / "rig").mkdir(exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix="font-quality-", dir=ROOT / "rig"))
    game, qc = rig / "ftesurf", rig / "qc"
    for path in (game / "gfx/fonts", game / "cfg", qc):
        path.mkdir(parents=True)
    shutil.copy2(engine, rig / "ftesurf64.exe")
    shutil.copy2(compiler, qc / "fteqcc64.exe")
    # Dependencies come from the selected engine's install, never an assumed PATH.
    for path in engine.parent.glob("*.dll"):
        if path.name.lower().startswith(("freetype", "libfreetype", "libpng", "zlib", "libbrotli", "libbz2")):
            shutil.copy2(path, rig / path.name)
    for font in FONTS:
        shutil.copy2(ROOT / "ftesurf/gfx/fonts" / font, game / "gfx/fonts" / font)
    for src, name in ((ROOT / "src/defs/m_defs.qc", "m_defs.qc"),
                      (ROOT / "src/shared/sh_font.qc", "sh_font.qc"),
                      (ROOT / "tools/fixtures/font_quality.qc", "font_quality.qc")):
        shutil.copy2(src, qc / name)
    (qc / "gallery.src").write_text("../ftesurf/menu.dat\nm_defs.qc\nsh_font.qc\nfont_quality.qc\n", encoding="utf-8")
    compile_run = subprocess.run([str(qc / "fteqcc64.exe"), "-O2", "-srcfile", "gallery.src"], cwd=qc,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    (rig / "compile.log").write_text(compile_run.stdout, encoding="utf-8")
    if compile_run.returncode or re.search(r"\bwarning\b|\berror\b", compile_run.stdout, re.I) or not (game / "menu.dat").is_file():
        raise RuntimeError(f"fixture compile failed or warned; see {rig / 'compile.log'}")
    (rig / "default.fmf").write_text('FTEMANIFEST 1\nGAME FTESurfFontQuality\nNAME "Font quality fixture"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG font-quality-unused\n', encoding="utf-8")
    (game / "cfg/font_quality.cfg").write_text(cfg_text(), encoding="utf-8")
    command = [str(rig / "ftesurf64.exe"), "-basedir", str(rig), "-nohome", "-window",
               "+set", "vid_width", str(SIZE[0]), "+set", "vid_height", str(SIZE[1]),
               "+set", "vid_fullscreen", "0", "+set", "vid_winmaximize", "0",
               "+set", "vid_renderer", "gl",
               "+set", "cfg_save_auto", "0", "+set", "vid_conautoscale", str(args.conscale),
               "+set", "vid_conwidth", "0", "+set", "vid_conheight", "0",
               "+set", "r_font_linear", str(args.linear), "+set", "r_font_postprocess_mono", "0",
               "+set", "r_font_postprocess_outline", "0", "+set", "dpcompat_smallerfonts", "0",
               "+set", "v_gamma", "1", "+set", "v_contrast", "1", "+set", "vid_srgb", "0",
               "+set", "log_dir", "logs", "+set", "log_readable", "7", "+set", "log_enable", "1",
               "+exec", "cfg/font_quality.cfg"]
    # Only this exact owned process may be terminated on timeout.
    started = datetime.now(timezone.utc).isoformat()
    with (rig / "client-stdout.log").open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(command, cwd=rig, stdout=out, stderr=subprocess.STDOUT)
        try:
            code = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
            raise RuntimeError(f"owned gallery timed out; retained evidence: {rig}")
    hashes = {path.relative_to(rig).as_posix(): sha(path) for path in
              [rig / "ftesurf64.exe", game / "menu.dat", qc / "font_quality.qc",
               qc / "m_defs.qc", qc / "sh_font.qc", qc / "gallery.src", qc / "fteqcc64.exe", rig / "default.fmf",
               game / "cfg/font_quality.cfg", *sorted((game / "gfx/fonts").glob("*.ttf")),
               *sorted(rig.glob("*.dll"))]}
    provenance = dict(schema=1, command=command, started_utc=started,
        finished_utc=datetime.now(timezone.utc).isoformat(), driver_sha256=sha(Path(__file__)),
        source_ref=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source_status=subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        engine_source=str(engine), engine_sha256=hashes["ftesurf64.exe"],
        compiler_source=str(compiler), compiler_sha256=hashes["qc/fteqcc64.exe"],
        conscale=args.conscale, linear=args.linear, client_exit=code, hashes=hashes)
    (rig / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return rig


def grade(rig: Path) -> int:
    provenance = json.loads((rig / "provenance.json").read_text(encoding="utf-8"))
    errors = []
    for name, expected in provenance["hashes"].items():
        path = rig / name
        if not path.is_file() or sha(path) != expected:
            errors.append(f"provenance hash changed: {name}")
    if provenance["client_exit"] != 0:
        errors.append(f"client exit {provenance['client_exit']}")
    logs = sorted((rig / "ftesurf/logs").glob("*.log"))
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in logs)
    errors += assess_log(text, provenance["conscale"], provenance["linear"])
    images = {}
    for phase in PHASES:
        path = rig / "ftesurf/screenshots" / (phase + ".png")
        if path.is_file():
            with Image.open(path) as image:
                images[phase] = image.convert("RGB")
    pixel_errors, metrics = assess_images(images)
    errors += pixel_errors
    report = dict(errors=errors, samples=metrics, limitation="Structural controls only; not a font-quality ranking, performance test or native ImGui acceptance.")
    (rig / "grade.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for error in errors:
        print("FAIL", error)
    print(f"{len(errors)} failed; evidence: {rig}")
    print(report["limitation"])
    return int(bool(errors))


def compare(a: Path, b: Path, require_identical: bool = False) -> int:
    # Do not accept a silent/incomplete launch as a matched sample.
    if grade(a) or grade(b):
        return 1
    pa, pb = [json.loads((p / "provenance.json").read_text(encoding="utf-8")) for p in (a, b)]
    for name in ("qc/m_defs.qc", "qc/sh_font.qc", "qc/font_quality.qc",
                 *("ftesurf/gfx/fonts/" + f for f in FONTS)):
        if pa["hashes"][name] != pb["hashes"][name]:
            raise ValueError(f"not matched: different {name}")
    with Image.open(a / "ftesurf/screenshots/baseline.png") as ia, Image.open(b / "ftesurf/screenshots/baseline.png") as ib:
        ia, ib = ia.convert("RGB"), ib.convert("RGB")
        diff = ImageChops.difference(ia, ib)
        diff.save(b / "baseline-diff.png")
        rows = [{"side": s, "face": f, "rung": r,
                 "changed_pixels": changed_pixels(ia.crop(sample_box(s, f, r)), ib.crop(sample_box(s, f, r)))}
                for s in range(2) for f in range(3) for r in range(4)]
    report = dict(a=str(a), b=str(b), engine_a=pa["engine_sha256"], engine_b=pb["engine_sha256"],
                  linear_a=pa["linear"], linear_b=pb["linear"], conscale_a=pa["conscale"], conscale_b=pb["conscale"],
                  changed_pixels=changed_pixels(ia, ib), rows=rows,
                  limitation="Differences are measured, NOT automatically labelled better/worse.")
    (b / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if require_identical and report["changed_pixels"]:
        print("FAIL matched galleries are not pixel-identical")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("launch", "grade", "compare"), nargs="?", default="launch")
    parser.add_argument("rig", type=Path, nargs="*")
    parser.add_argument("--conscale", type=float, choices=(1, 1.5, 2), default=1)
    parser.add_argument("--linear", type=int, choices=(0, 1), default=1)
    parser.add_argument("--require-identical", action="store_true", help="compare: fail on any changed pixel")
    parser.add_argument("--engine", default="C:/FTESurf/ftesurf64.exe")
    parser.add_argument("--compiler", default=str(ROOT / "src/fteqcc64.exe"))
    args = parser.parse_args()
    try:
        if args.action == "launch" and not args.rig:
            rig = launch(args)
            return grade(rig)
        if args.action == "grade" and len(args.rig) == 1:
            return grade(args.rig[0].resolve())
        if args.action == "compare" and len(args.rig) == 2:
            return compare(args.rig[0].resolve(), args.rig[1].resolve(), args.require_identical)
        parser.error("launch takes no rig; grade needs one rig; compare needs two")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f"Cannot grade: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
