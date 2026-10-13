#!/usr/bin/env python3
"""Test Perfect-board presentation in owned, disposable source/runtime overlays.

Uses production Board_Frame with a test-only stat seam, captures sound builtin
arguments, and renders the actual Board panel/editor. --source permits a stock
pre-change control: an inert streak stub lets the SAME assertions fail visibly.
Never changes installed programs, configs or player data. Retain evidence under
an OWNER.md task root; only the existing harness's own process handles are stopped.
"""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTENT = Path("C:/FTESurf")
PRELUDE = r'''
float bp_active, bp_seq, bp_ramp, bp_calls, bp_pitch, bp_volume, bp_quiet;
vector bp_normal, bp_vin;
string bp_sample;
float(float stat) BP_Stat =
{
	if (!bp_active) return getstatf(stat);
	if (stat == STAT_FS_BOARDCOUNT) return bp_seq;
	if (stat == STAT_FS_RAMPCONTACT) return bp_ramp;
	if (stat == STAT_FS_TIMERSTATE) return TS_RUNNING;
	if (stat == STAT_FS_BOARDNORM) return bp_normal_x;
	if (stat == STAT_FS_BOARDNORM + 1) return bp_normal_y;
	if (stat == STAT_FS_BOARDNORM + 2) return bp_normal_z;
	if (stat == STAT_FS_BOARDVEL) return bp_vin_x;
	if (stat == STAT_FS_BOARDVEL + 1) return bp_vin_y;
	if (stat == STAT_FS_BOARDVEL + 2) return bp_vin_z;
	return getstatf(stat);
};
void(entity e, float channel, string sample, float volume, float attenuation,
     float pitch, float flags) BP_Sound =
{
	bp_calls = bp_calls + 1;
	bp_pitch = pitch;
	bp_volume = volume;
	bp_sample = sample;
	if (!bp_quiet)
	{
		print(sprintf("BOARD SOUND: %s pitch %.4f volume %.2f time %g\n", sample, pitch, volume, cltime));
		sound(e, channel, sample, volume, attenuation, pitch, flags);
	}
};
'''
CFG = '''cfg_save_auto 0
cl_idlefps 0
cl_maxfps 100
vid_renderer gl
vid_width 1280
vid_height 720
vid_conwidth 1280
vid_conautoscale 0
vid_restart
log_enable 1
log_dir logs
log_name runlines_smoke
con_notifytime 0
set fs_missingwarn 0
map surf_dune
waitmap 60
waitms 5000
menu_restart
ui_close
hud_board 1
hud_board_x 0.5
hud_board_y 0.4
hud_board_size 32
hud_board_fade 999
hud_board_seg 0
hud_board_grade 1
hud_board_kept 1
hud_board_cost 1
hud_board_ramp 0
hud_board_words 0
hud_board_rainbow 0
hud_board_bounce 0
hud_board_sound 1
hud_board_volume 0.35
board_feedback_test
board_feedback_scene 0
waitms 250
screenshot bp_plain.png
hud_board_rainbow 1
waitms 250
screenshot bp_rainbow.png
hud_board_bounce 1
waitms 250
screenshot bp_both1.png
waitms 250
screenshot bp_both2.png
hud_board_rainbow 0
waitms 250
screenshot bp_bounce.png
board_feedback_scene 2
waitms 250
screenshot bp_nonperfect.png
hud_board_rainbow 1
waitms 250
screenshot bp_nonperfect_fx.png
board_feedback_scene 0
hud_board_grade 0
waitms 250
screenshot bp_percent.png
hud_board_rainbow 0
hud_board_bounce 0
waitms 250
screenshot bp_percent_plain.png
hud_board_grade 1
hud_edit board
board_feedback_editor
waitms 250
screenshot bp_editor.png
hud_edit
// Raw capture is this client's mixer only, never system/owner loopback audio.
s_volume 0.5
s_khz 48
snd_ignoregamespeed 1
vbsp_soundscape 0
bgmvolume 0
ambient_level 0
stopsound
capturerate 5
capturedriver raw
capturecodec png
capturesound 1
capturesoundchannels 2
capturesoundbits 16
capture bp_audio/
hud_board_sound 1
hud_board_volume 0.35
board_feedback_audio reset
waitms 800
board_feedback_audio perfect
waitms 1000
board_feedback_audio perfect
waitms 1000
board_feedback_audio hop
waitms 1000
board_feedback_audio perfect
waitms 1000
board_feedback_audio fail
waitms 1000
board_feedback_audio perfect
waitms 1000
board_feedback_audio fail
hud_board_sound 2
board_feedback_audio perfect
waitms 1000
board_feedback_audio fail
hud_board_sound 3
board_feedback_audio perfect
waitms 1000
hud_board_sound 0
board_feedback_audio perfect
waitms 1000
hud_board_sound 1
hud_board_volume 0
board_feedback_audio perfect
waitms 1000
capturestop
echo RUNLINES COMPLETE
quit
'''


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Seam must be unique: {old!r}")
    return text.replace(old, new)


def grade_capture(rig, out, control=False):
    # This renderer falsifier requires numpy/Pillow, like the other pixel rigs.
    import numpy as np
    from PIL import Image

    game = rig / "ftesurf"
    shots = {p.stem: np.array(Image.open(p).convert("RGB"))
             for p in (game / "screenshots").glob("bp_*.png")}
    assert len(shots) == 10, "all ten screenshots must act"
    h, w, _ = shots["bp_plain"].shape
    word = (slice(int(h * .448), int(h * .5)), slice(int(w * .39), int(w * .505)))
    suffix = (slice(int(h * .448), int(h * .5)), slice(int(w * .524), int(w * .609)))

    def changed(a, b, region):
        return int(np.count_nonzero(np.any(shots[a][region] != shots[b][region], axis=2)))

    metrics = {}
    for a, b in (("bp_plain", "bp_rainbow"), ("bp_plain", "bp_bounce"), ("bp_both1", "bp_both2")):
        n = changed(a, b, word)
        metrics[a + "/" + b] = n
        assert n < 100 if control else n > 1000, "glyph effect did not act"
        assert changed(a, b, suffix) < 100, "percentage must not move or recolour"
    for a, b in (("bp_nonperfect", "bp_nonperfect_fx"), ("bp_percent", "bp_percent_plain")):
        n = changed(a, b, word) + changed(a, b, suffix)
        metrics[a + "/" + b] = n
        assert n < 100, "non-perfect/grade-hidden arm changed"

    raw, = (game / "bp_audio").glob("audio_2chan_48khz_16b.raw")
    audio = np.frombuffer(raw.read_bytes(), dtype="<i2").reshape(-1, 2).mean(axis=1)
    blocks = audio[:len(audio) // 480 * 480].reshape(-1, 480)
    rms = np.sqrt(np.mean(blocks ** 2, axis=1))
    edges = np.where((rms[1:] > 12) & (rms[:-1] <= 12))[0] * .01
    frequencies = []
    for edge in edges:
        start = int((edge + .03) * 48000)
        samples = audio[start:start + 8192]
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples)), 131072))
        frequencies.append(float((1 + np.argmax(spectrum[1:])) * 48000 / 131072))
    # Native software mixing quantizes speed to 1/64; prove emitted pitch, not
    # just the QC argument. Four dong cues include the post-failure reset.
    expected = [] if control else [392, 392 * 67 / 64, 392 * 71 / 64, 392, 196, 784]
    assert len(frequencies) == len(expected), "missing sound or extra bhop/fail/off/mute sound"
    assert all(abs(a - b) < 2.5 for a, b in zip(frequencies, expected)), "incorrect emitted pitch"
    metrics["audio_hz"] = frequencies
    metrics["audio_onsets_seconds"] = list(map(float, edges))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print("PIXEL/AUDIO:", metrics)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=ROOT)
    ap.add_argument("--port", type=int, default=27617)
    ap.add_argument("--control", action="store_true", help="expect 20 pre-change assertion failures and no effects")
    args = ap.parse_args()
    out = args.output_dir.resolve()
    if not any((p / "OWNER.md").is_file() for p in (out, *out.parents)):
        raise ValueError("--output-dir needs an owned task root")
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    source.mkdir()
    tracked = subprocess.check_output(["git", "-C", str(args.source), "ls-files", "src"], text=True).splitlines()
    for name in tracked:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.source / name, target)
    shutil.copy2(CONTENT / "src/fteqcc64.exe", source / "src/fteqcc64.exe")
    board = source / "src/client/cl_board.qc"
    text = board.read_text()
    if "board_perfect_streak" not in text:
        text = "float board_perfect_streak; // inert pre-change control\n" + text
    else:
        text = once(text, "sound(world, CHAN_AUTO, sample", "BP_Sound(world, CHAN_AUTO, sample")
    board.write_text(PRELUDE + text.replace("getstatf(", "BP_Stat("))
    fixture = source / "src/client/cl_board_feedback_test.qc"
    shutil.copy2(ROOT / "tools/fixtures/board_feedback.qc", fixture)
    src = source / "src/cl_progs.src"
    src.write_text(src.read_text() + "\nclient/cl_board_feedback_test.qc\n")
    mainqc = source / "src/client/cl_main.qc"
    text = mainqc.read_text()
    text = "float() BP_Command;\nvoid(vector scr) BP_ScenePrepare;\n" + text
    text = once(text, "\ttokenize(cmd);\n", "\ttokenize(cmd);\n\tif (BP_Command()) return TRUE;\n")
    text = once(text, "\t\tHUD_Draw(scr);", "\t\tBP_ScenePrepare(scr);\n\t\tHUD_Draw(scr);")
    mainqc.write_text(text)
    build = subprocess.run(["pwsh", "-NoProfile", "-File", "./build.ps1", "-Jobs", "8", "-NoDeploy"],
                           cwd=source / "src", capture_output=True, text=True)
    (out / "build.log").write_text(build.stdout + build.stderr)
    if build.returncode:
        raise RuntimeError("Fixture build failed: " + str(out / "build.log"))
    qc, = (source / "rig").glob("build-nodeploy-*")
    cfg = out / "board_feedback.cfg"
    # Screenshots are deferred until render. Keep the following state change
    # out of that render, rather than accidentally photographing the next arm.
    cfgtext = re.sub(r"(screenshot [^\n]+\n)", r"\1waitms 200\n", CFG)
    # Predeclare new settings for the old binary so its negative control fails
    # assertions/effects, not the unrelated unknown-command guard.
    cfgtext = re.sub(r"(?m)^(hud_board_(?:sound|volume|rainbow|bounce) )", r"set \1", cfgtext)
    cfg.write_text(cfgtext)
    runner = (CONTENT / "tools/runlines_smoke.py").read_text()
    runner = once(runner, "ROOT = pathlib.Path(__file__).resolve().parent.parent", f"ROOT = pathlib.Path({str(CONTENT)!r})")
    runner = once(runner, "source = {'qwprogs.dat': a.ssqc, 'csprogs.dat': a.csqc}.get(name)",
                  "source = {'qwprogs.dat': a.ssqc, 'csprogs.dat': a.csqc, 'menu.dat': a.csqc.parent / 'menu.dat'}.get(name)")
    # Copy only the three authored cues, never personal sounds. If the general
    # runner later adds a shared sound junction, omit it before this local copy.
    runner = once(runner, "        for name in CONTENT_DIRS:\n", "        for name in CONTENT_DIRS:\n            if name == 'sound': continue\n")
    cue_dir = ROOT / "ftesurf/sound/ftesurf"
    runner = once(runner, "        client = subprocess.Popen(",
                  f"        shutil.copytree({str(cue_dir)!r}, gd / 'sound/ftesurf')\n        client = subprocess.Popen(")
    harness = out / "runlines.py"
    harness.write_text(runner)
    result = subprocess.run([sys.executable, "-B", str(harness), str(cfg), "--dedicated", "--port", str(args.port),
                             "--timeout", "90", "--output-dir", str(out), "--ssqc", str(qc / "qwprogs.dat"),
                             "--csqc", str(qc / "csprogs.dat")], capture_output=True, text=True)
    (out / "runtime.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("Runtime failed: " + str(out / "runtime.log"))
    rigs = re.findall(r"^Retained private rig: (.+)$", result.stdout, re.M)
    rig, = map(Path, rigs)
    log = (rig / "ftesurf/logs/runlines_smoke.log").read_text(errors="replace")
    checks = re.findall(r"BOARD CHECKS: (\d+) checks, (\d+) failures", log)
    print("Retained board rig:", rig)
    print("BOARD CHECKS:", checks)
    expected = "20" if args.control else "0"
    if checks != [("26", expected)]:
        raise SystemExit("Board assertions failed; inspect retained client log")
    grade_capture(rig, out, args.control)


if __name__ == "__main__":
    main()
