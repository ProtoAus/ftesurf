#!/usr/bin/env python3
"""Compile test-only QC seams in a disposable worktree; exercise real fade code.

No installed progs/config/data are changed. Retain worktree, logs and screenshots
under --output-dir for inspection. The fixture body uses production Body_Predraw,
not a replacement material/render path. Test commands never enter shipped CSQC.
"""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

LINE_TEST = r'''
float vf_checks, vf_fail;
void(float ok, string name) Visual_Check =
{
	vf_checks = vf_checks + 1;
	if (!ok) { vf_fail = vf_fail + 1; print("VISUAL FAIL: ", name, "\n"); }
};
void() Visual_LineTest =
{
	local float s, b, i, dur, old, db;

	s = LN_S_TRAIL;
	b = 0;
	dur = 0.18;
	ln_reveal = dur;
	cvar_set("hud_lines_reveal", "0.18");
	Line_Begin(s);
	for (i = 0; i < 3; i = i + 1)
		Line_Add(s, [i * 10, 0, 20], 100, 0, 0, i * 0.01, FALSE);
	Line_End(s);
	Visual_Check(ln_published[s] == 3, "published count");
	Visual_Check(Line_Reveal(s, 0, 0, 999999, 1) == 0, "batch starts hidden");
	Visual_Check(ln_born[b] == ln_born[b + 2], "same-frame arrivals have one age");
	for (i = 0; i < 3; i = i + 1) ln_born[b + i] = ln_born[b + i] - dur * 0.5;
	Visual_Check(fabs(Line_Reveal(s, 0, 0, 999999, 1) - 0.5) < 0.001, "constant half fade");
	Visual_Check(Line_Reveal(s, 1, 0, 999999, 1) > 0.49 && Line_Reveal(s, 1, 0, 999999, 1) < 0.51, "middle half opacity");
	Visual_Check(fabs(Line_Reveal(s, 2, 0, 999999, 1) - 0.5) < 0.001, "no chunk-front restart");
	for (i = 0; i < 3; i = i + 1) ln_born[b + i] = ln_born[b + i] - dur * 0.5;
	Visual_Check(Line_Reveal(s, 2, 0, 999999, 1) > 0.999, "front complete by duration");
	old = ln_born[b];
	Line_Add(s, '30 0 20', 100, 0, 0, 0.03, FALSE);
	Line_End(s);
	Visual_Check(ln_born[b] == old, "publication preserves old births");
	Visual_Check(Line_Reveal(s, 0, 0, 999999, 1) > 0.999, "old batch remains visible");
	Visual_Check(Line_Reveal(s, 3, 0, 999999, 1) == 0, "next batch starts hidden");
	old = ln_born[b + 3];
	Line_End(s);
	Visual_Check(ln_born[b + 3] == old, "repeat rebuild does not restart");
	Visual_Check(Line_Reveal(0, 0, 1, 1, 0) == 0, "demo head hidden");
	Visual_Check(fabs(Line_Reveal(0, 0, 1, 1.09, 0) - 0.5) < 0.001, "demo mid fade");
	Visual_Check(Line_Reveal(0, 0, 1, 1.2, 0) == 1, "demo mature");
	Visual_Check(Line_Reveal(0, 0, 1, 0.9, 0.2) == 0.2, "demo future baseline");
	Visual_Check(Line_Reveal(1, 0, 1, 1, 0) == 1, "board unaffected");
	Line_Begin(0);
	db = Line_BirthBase(0);
	for (i = 0; i < LN_CHUNK * 2; i = i + 1)
		Line_Add(0, [i * 10, 0, 20], 100, 0, 0, i * 0.01, FALSE);
	Line_End(0);
	Visual_Check(ln_published[0] == LN_CHUNK * 2, "demo published count");
	Visual_Check(Line_Reveal(0, 0, 0, 999999, 1) == 0, "demo default-ahead publication starts hidden");
	Visual_Check(ln_born[db] == ln_born[db + LN_CHUNK], "demo chunks start together");
	Visual_Check(ln_born[db + LN_CHUNK - 1] == ln_born[db], "demo has no chunk stagger");
	old = ln_born[db + LN_CHUNK - 1];
	Line_End(0);
	Visual_Check(ln_born[db + LN_CHUNK - 1] == old, "demo rebuild preserves births");
	for (i = 0; i < LN_CHUNK * 2; i = i + 1) ln_born[db + i] = ln_born[db + i] - dur * 0.5;
	Visual_Check(fabs(Line_Reveal(0, 0, 0, 999999, 1) - 0.5) < 0.001, "demo half fade");
	Visual_Check(fabs(Line_Reveal(0, LN_CHUNK - 1, 0, 999999, 1) - 0.5) < 0.001, "demo no periodic reset");
	for (i = 0; i < LN_CHUNK * 2; i = i + 1) ln_born[db + i] = ln_born[db + i] - dur * 0.5;
	Visual_Check(Line_Reveal(0, LN_CHUNK - 1, 0, 999999, 1) > 0.999, "demo front complete by duration");
	Visual_Check(fabs(Line_Reveal(0, 0, 1, 1.09, 0.2) - 0.6) < 0.001, "demo playhead composes with mature publication");
	Line_Clear(0);
	Visual_Check(ln_published[0] == 0, "demo clear resets publication");
	Line_Begin(0);
	Line_Add(0, '0 0 20', 100, 0, 0, 0, FALSE);
	Line_End(0);
	Visual_Check(Line_Reveal(0, 0, 0, 999999, 1) == 0, "demo slot reuse starts hidden");
	// Force the real cap path with sentinel births; no giant rendered fixture.
	ln_born[db] = 10;
	ln_born[db + 2] = 20;
	ln_born[db + 4] = 30;
	ln_n[0] = LN_CAP;
	ln_published[0] = 5;
	Line_Add(0, '0 0 20', 100, 0, 0, 0, FALSE);
	Visual_Check(ln_n[0] == LN_CAP / 2 + 1, "demo cap compaction acted");
	Visual_Check(ln_published[0] == 3, "odd publication count compacts correctly");
	Visual_Check(ln_born[db] == 10 && ln_born[db + 1] == 20 && ln_born[db + 2] == 30, "compaction preserves retained births");
	Line_Clear(0);
	ln_reveal = 0;
	Visual_Check(Line_Reveal(s, 3, 0, 999999, 1) == 1, "instant live control");
	Visual_Check(Line_Reveal(0, 0, 1, 1, 0) == 1, "instant demo control");
	Line_Clear(s);
	Visual_Check(ln_published[s] == 0, "clear resets publication count");
	Line_Begin(s);
	Line_Add(s, '0 0 20', 100, 0, 0, 0, FALSE);
	old = ln_born[b];
	ln_born[b] = old - dur;
	Line_End(s);
	Visual_Check(ln_born[b] == old - dur, "live End preserves arrival birth");
	Line_Add(s, '10 0 20', 100, 0, 0, 0.01, FALSE);
	ln_reveal = dur;
	Visual_Check(ln_published[s] == 1 && ln_n[s] == 2, "unbuilt live tail exists");
	Visual_Check(Line_Reveal(s, 0, 0, 999999, 1) > 0.999 && Line_Reveal(s, 1, 0, 999999, 1) == 0, "continuous age gradient across rebuild boundary");
	ln_born[b + 1] = cltime - dur * 0.25;
	Visual_Check(fabs(Line_Reveal(s, 1, 0, 999999, 1) - 0.25) < 0.001, "linear quarter fade");
	Line_Clear(s);
	print(sprintf("VISUAL CHECKS: %g checks, %g failures\n", vf_checks, vf_fail));
};

float vf_lineon, vf_lineslot, vf_lineage, vf_pending;
void() Visual_LineScene =
{
	local float i;
	local vector eye, dir, side;

	vf_lineslot = stof(argv(1));
	vf_lineage = stof(argv(2));
	vf_pending = stof(argv(3));
	vf_lineon = TRUE;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	dir = v_forward;
	side = v_right;
	Line_Begin(vf_lineslot);
	for (i = 0; i < LN_CHUNK; i = i + 1)
	{
		if (vf_pending && i == LN_CHUNK - (vf_pending > 2 ? vf_pending : 3)) Line_End(vf_lineslot);
		Line_Add(vf_lineslot, eye + dir * 160 + side * (i * 120 / (LN_CHUNK - 1) - 60),
		         100, 0, 0, i * 0.01, vf_pending == 2 && i == LN_CHUNK - 3);
	}
	if (!vf_pending) Line_End(vf_lineslot);
	print(sprintf("VISUAL LINE: slot %g age %g\n", vf_lineslot, vf_lineage));
};
void() Visual_LineDraw =
{
	local float i, b;

	if (!vf_lineon) return;
	Line_ViewFrame();
	Line_WindowOff();
	b = Line_BirthBase(vf_lineslot);
	for (i = 0; i < LN_CHUNK; i = i + 1)
		ln_born[b + i] = cltime - vf_lineage * 0.18;
	ln_npt = ln_nseg = 0;
	Line_Draw(vf_lineslot, 999999, '0 0 0', 1, 1);
	if (vf_pending) Visual_Check(ln_npt >= 5, "pending tail actually emitted");
	if (vf_pending > 2) Visual_Check(ln_npt >= vf_pending + 2, "full 15-sample tail actually emitted");
	// Flush the deferred 2D polygon without painting over the subject.
	drawfill('0 0 0', '1 1 0', '0 0 0', 1, 0);
};
'''
BODY_TEST = r'''
entity vf_body;
void() Visual_BodyTest =
{
	local vector eye, ang, org;
	local float distance;

	if (vf_body) { remove(vf_body); vf_body = world; }
	distance = stof(argv(1));
	if (distance <= 0) return;
	eye = getproperty(VF_ORIGIN);
	ang = getproperty(VF_ANGLES);
	makevectors(ang);
	org = eye + v_forward * distance - '0 0 31';
	vf_body = spawn();
	vf_body.classname = "visual_fade_fixture";
	vf_body.drawmask = MASK_ENGINE;
	vf_body.predraw = Body_Predraw;
	vf_body.pb_n = 1;
	vf_body.pb_slot = 1;
	vf_body.pb_rorg = org;
	vf_body.pb_rang = ang + '0 180 0';
	vf_body.pb_lc = 3;
	vf_body.pb_lf = PBL_GLOW;
	print(sprintf("VISUAL BODY: distance %g, fade %g, shader %g\n", distance, pb_cv_fade, pb_fadeshader));
};
'''

CFG = '''cfg_save_auto 0
name VisualFadeControl
log_enable 1
log_dir logs
log_name runlines_smoke
log_developer 1
developer 1
cl_idlefps 0
cl_maxfps 100
set cl_playerfade 1
set cl_playerfade_near 32
set cl_playerfade_far 128
set hud_lines_reveal 0.18
set visual_test_worldfree 1
set r_clear 1
waitms 2000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
cmd zone_goto 0
waitms 500
con_notifystyle 0
con_notifylines 0
con_notifytime 0
con_notifytime_error 0
con_notifyfade 0
developer 0
visual_line_test
body_fade_test 160
waitms 250
screenshot vf_far.png
cl_playerfade 0
waitms 250
screenshot vf_far_control.png
body_fade_test 80
waitms 250
screenshot vf_mid_control.png
cl_playerfade 1
waitms 250
screenshot vf_mid.png
body_fade_test 24
waitms 250
screenshot vf_near.png
cl_playerfade 0
waitms 250
screenshot vf_near_control.png
cl_playerfade 1
cl_playerfade_near 128
cl_playerfade_far 32
body_fade_test 80
waitms 250
screenshot vf_inverted.png
body_fade_test 0
waitms 250
screenshot vf_empty.png
set hud_watch_path_px 6
set hud_watch_path_far 0
set hud_watch_path_color 0
set hud_lines_marks 0
set hud_lines_nums 0
set hud_trail 0
set hud_watch_path 0
set hud_lines_board 0
visual_line_scene 9 0
waitms 250
screenshot vf_live_start.png
visual_line_scene 9 0.5
waitms 250
screenshot vf_live_half.png
visual_line_scene 9 1
waitms 250
screenshot vf_live_full.png
hud_lines_reveal 0
visual_line_scene 9 0
waitms 250
screenshot vf_live_control.png
hud_lines_reveal 0.18
visual_line_scene 0 0
waitms 250
screenshot vf_demo_start.png
visual_line_scene 0 0.5
waitms 250
screenshot vf_demo_half.png
visual_line_scene 0 1
waitms 250
screenshot vf_demo_full.png
hud_lines_reveal 0
visual_line_scene 0 0
waitms 250
screenshot vf_demo_control.png
echo RUNLINES COMPLETE
quit
'''


def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Test seam must match exactly once: {old!r}')
    return text.replace(old, new, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--grade-only', type=Path, help='Regrade an existing acted overlay; never relaunch')
    args = ap.parse_args()
    if args.grade_only:
        grade(args.grade_only)
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='ftesurf-visual-source-', dir=args.output_dir))
    work.rmdir()
    run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(work), 'HEAD'])
    for rel in ('src/cl_progs.src', 'src/client/cl_lines.qc', 'src/client/cl_body.qc',
                'src/client/cl_playerfade.qc', 'src/client/cl_hudedit.qc',
                'ftesurf/cfg/default.cfg', 'tools/runlines_smoke.py'):
        dest = work / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    shutil.copy2(ROOT / 'src/fteqcc64.exe', work / 'src/fteqcc64.exe')
    p = work / 'src/client/cl_lines.qc'
    text = p.read_text()
    text = replace_once(text, 'float() Line_Console =', LINE_TEST + '\nfloat() Line_Console =')
    text = replace_once(text, 'if (argv(0) != "lines")', 'if (argv(0) == "visual_line_test") { Visual_LineTest(); return TRUE; }\n\tif (argv(0) == "visual_line_scene") { Visual_LineScene(); return TRUE; }\n\tif (argv(0) != "lines")')
    text = replace_once(text, 'registercommand("lines");', 'registercommand("lines");\n\tregistercommand("visual_line_test");\n\tregistercommand("visual_line_scene");')
    p.write_text(text)
    p = work / 'src/client/cl_body.qc'
    text = p.read_text()
    text = replace_once(text, 'float(string cmd) Body_ConsoleCommand =', BODY_TEST + '\nfloat(string cmd) Body_ConsoleCommand =')
    text = replace_once(text, 'if (argv(0) == "body_stats")', 'if (argv(0) == "body_fade_test") { Visual_BodyTest(); return TRUE; }\n\tif (argv(0) == "body_stats")')
    text = replace_once(text, 'registercommand("body_stats");', 'registercommand("body_stats");\n\tregistercommand("body_fade_test");')
    p.write_text(text)
    # A world-free main scene avoids a fixture behind the start-room wall.
    # This is still Body_Predraw's normal entity renderer, not a UI preview.
    p = work / 'src/client/cl_main.qc'
    text = p.read_text()
    assert text.count('\trenderscene();') == 1
    p.write_text(replace_once(text, '\trenderscene();', '\tmakevectors(getproperty(VF_ANGLES));\n\tproject(getproperty(VF_ORIGIN) + v_forward * 256);\n\tdrawfill(\'0 0 0\', getproperty(VF_SCREENVSIZE), \'0 0 0\', 1, 0);\n\tclearscene();\n\tif (vf_body) addentity(vf_body);\n\tsetproperty(VF_DRAWWORLD, FALSE);\n\trenderscene();\n\tVisual_LineDraw();\n\tif (cvar("visual_test_worldfree")) return;'))
    cfg = work / 'ftesurf/cfg/test/visual_fades.cfg'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # waitms alone can drain while an unfocused GL window isn't redrawing.
    # Require rendered frames around each retained screenshot too.
    coverage_cfg = 'cl_playerfade 1\nbody_fade_test 80\n'
    for i in range(33):
        coverage_cfg += (f'cl_playerfade_near {80 - i * 2}\ncl_playerfade_far {144 - i * 2}\n'
                         f'waitms 250\nscreenshot vf_sub_{i:02d}.png\n')
    coverage_cfg += 'body_fade_test 0\n'
    config = CFG.replace('body_fade_test 0\nwaitms 250\nscreenshot vf_empty.png\n',
                         'body_fade_test 0\nwaitms 250\nscreenshot vf_empty.png\n' + coverage_cfg)
    config = config.replace('echo RUNLINES COMPLETE',
                            'visual_line_scene 9 1 1\nwaitms 250\nscreenshot vf_pending.png\n'
                            'visual_line_scene 9 1 2\nwaitms 250\nscreenshot vf_pending_break.png\n'
                            'visual_line_scene 9 1 15\nwaitms 250\nscreenshot vf_pending_long.png\n'
                            'echo RUNLINES COMPLETE')
    cfg.write_text(config.replace('waitms 250\n', 'waitms 250\nwait 20\n'))
    run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8', '-QuakeDir', ''], work / 'src')
    result = subprocess.run([sys.executable, '-B', str(work / 'tools/runlines_smoke.py'), str(cfg),
                             '--output-dir', str(args.output_dir)], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Overlay runner failed; retained paths are printed above')
    # The runner prints its retained overlay directory as its last line.
    overlay = Path(result.stdout.strip().splitlines()[-1].removeprefix('Retained private rig: '))
    grade(overlay, work)


def grade(overlay, work=None):
    log = (overlay / 'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
    expected_checks = LINE_TEST.split('float vf_lineon')[0].count('Visual_Check(')
    if f'VISUAL CHECKS: {expected_checks} checks, 0 failures' not in log:
        raise RuntimeError('Fade alpha control/subject failed; inspect retained log')
    if not any('ftesurf/playerfade' in line and 'prog 1' in line for line in log.splitlines()):
        raise RuntimeError('Player shader did not load a program (silent fallback is not a pass)')
    if log.count('VISUAL BODY:') != 5:
        raise RuntimeError('Fixture body control did not act')
    errors = ('error:', 'failed to compile', 'invalid program', 'unable to load shader')
    if any(e in log.lower() for e in errors):
        raise RuntimeError('Shader/runtime error in retained log')
    shots = sorted(overlay.rglob('vf_*.png'))
    if len(shots) != 52:
        raise RuntimeError(f'Expected 52 retained screenshots, got {len(shots)}')
    from PIL import Image
    images = {p.stem: Image.open(p).convert('RGB') for p in shots}
    def data(image):
        if hasattr(image, 'get_flattened_data'):
            return image.get_flattened_data()
        return image.getdata()
    pixels = {name: sum(max(pixel) > 0 for pixel in data(image))
              for name, image in images.items()}
    if pixels['vf_far_control'] < 1000 or pixels['vf_mid_control'] < 1000 or pixels['vf_near_control'] < 1000:
        raise RuntimeError('Opaque control did not draw a body')
    if pixels['vf_far'] != pixels['vf_far_control']:
        raise RuntimeError('Far body is not fully opaque')
    ratio = pixels['vf_mid'] / pixels['vf_mid_control']
    if not 0.499 < ratio < 0.501:
        raise RuntimeError(f'Middle body coverage should be half, got {ratio:.6f}')
    if any(pixels[n] != 0 for n in ('vf_near', 'vf_inverted', 'vf_empty')):
        raise RuntimeError('Close/inverted/empty body is not hidden')
    for name in ('far', 'mid'):
        subject = images[f'vf_{name}']
        control = images[f'vf_{name}_control']
        for a, b in zip(data(subject), data(control)):
            if max(a) > 0 and max(abs(x-y) for x, y in zip(a, b)) > 1:
                raise RuntimeError('Surviving pixels changed normal body colours/lighting')
    levels = [pixels[f'vf_sub_{i:02d}'] for i in range(33)]
    if len(set(levels)) < 30 or levels != sorted(levels) or levels[0] != 0:
        raise RuntimeError(f'Body coverage still stepped/nonmonotonic: {levels}')
    endpoint = images['vf_sub_32']
    control = images['vf_mid_control']
    if pixels['vf_sub_32'] != pixels['vf_mid_control']:
        raise RuntimeError('Coverage sweep opaque endpoint differs from normal coverage')
    # Five one-channel 1/255 differences occurred after the long sweep. Keep
    # the same tight survivor tolerance used above; never forgive changed masks.
    if any(max(abs(x-y) for x, y in zip(a, b)) > 1 for a, b in zip(data(endpoint), data(control))):
        raise RuntimeError('Coverage sweep endpoint changed normal colours')
    print(f'Body coverage: {len(set(levels))} distinct monotonic levels over 32 substeps (old Bayer <=17).')
    if 'VISUAL FAIL:' in log:
        raise RuntimeError('Pending-tail emit control failed')
    if log.count('VISUAL LINE:') != 11:
        raise RuntimeError('Line drawing controls did not act')
    for name in ('live', 'demo'):
        start, half, full, control = (images[f'vf_{name}_{phase}'] for phase in
                                      ('start', 'half', 'full', 'control'))
        brightness = [sum(sum(p) for p in data(im)) for im in (start, half, full, control)]
        if brightness[0] != 0 or brightness[3] < 10000:
            raise RuntimeError(f'{name} hidden/opaque control failed: {brightness}')
        if not 0.35 < brightness[1] / brightness[3] < 0.65:
            raise RuntimeError(f'{name} half reveal not half brightness: {brightness}')
        if list(data(full)) != list(data(control)):
            raise RuntimeError(f'{name} mature reveal differs from instant control')
        w, h = half.size
        left = sum(sum(p) for p in data(half.crop((0, 0, w // 2, h))))
        right = sum(sum(p) for p in data(half.crop((w // 2, 0, w, h))))
        if not 0.95 < left / right < 1.05:
            raise RuntimeError(f'{name} uniform arrivals have a restarted stagger: left {left} right {right}')
        if not 0.49 < brightness[1] / brightness[3] < 0.51:
            raise RuntimeError(f'{name} fade not constant-rate: {brightness}')
        print(f'Line pixels: {name} hidden -> {brightness[1] / brightness[3]:.4f} brightness -> opaque, no chunk stagger.')
    full = sum(sum(p) for p in data(images['vf_live_control']))
    pending = sum(sum(p) for p in data(images['vf_pending']))
    broken = sum(sum(p) for p in data(images['vf_pending_break']))
    long_tail = sum(sum(p) for p in data(images['vf_pending_long']))
    if not 0.99 < long_tail / full < 1.01:
        raise RuntimeError(f'15-sample pending tail pixels incorrect: {full} {long_tail}')
    if not 0.99 < pending / full < 1.01 or not 0.92 < broken / full < 0.99:
        raise RuntimeError(f'Pending tail/break pixels incorrect: {full} {pending} {broken}')
    print(f'Renderer: far opaque, middle {ratio:.6f}, near hidden, surviving colours preserved.')
    print(f'{expected_checks} alpha checks and 52 renderer screenshots passed; retained screenshots:')
    print(overlay)
    if work is not None:
        print('Retained isolated test-only source:', work)


if __name__ == '__main__':
    main()
