#!/usr/bin/env python3
"""Private overlay: visual cursor vs sampled saves, real HUD and bind navigation."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SEAM = r'''
float rh_checks, rh_fails;
void(float ok, string name) Review_Check =
{
	rh_checks = rh_checks + 1;
	if (!ok) { rh_fails = rh_fails + 1; print("REVIEW FAIL: ", name, "\n"); }
};
void() Review_Unit =
{
	local float oldraw, s, b, i, k, leftk, oldi;
	local string command;

	oldraw = tr_raw;
	tr_raw = buf_create_ex("string", 0);
	s = tr_live;
	b = s * LN_CAP;
	Line_Begin(s);
	Line_Add(s, '0 0 20', 100, 0, 0, 0, FALSE);
	Line_Add(s, '10 0 30', 200, 0, 0, 0.03, FALSE);
	Line_End(s);
	ln_z0[s] = 20;
	ln_v20[s] = 10000;
	bufstr_set(tr_raw, 0, "0 0 0 20 100 0 0 0 0 0 350 0 0 0");
	bufstr_set(tr_raw, 1, "0.03 10 0 30 200 0 0 0 0 0 10 0 0 0");
	tr_tick = 0.015;
	tr_cur_on = rw_on = TRUE;
	rw_ack = rw_cd = 0;
	rw_i = 0.5;
	Rewind_Cursor();
	Review_Check(tr_cur_t == 0 && tr_cur_p == '0 0 20', "sample selection stays exact");
	Review_Check(fabs(rw_visualt - 0.015) < 0.00001 && rw_visualp == '5 0 25', "fractional visual cursor");
	Trail_CursorState(tr_cur_t);
	Review_Check(tr_cur_vel == '100 0 0', "sampled save velocity");
	Rewind_Present();
	Review_Check(ui_rw_on && ui_rw_velok && ui_rw_vel == '150 0 0', "separate interpolated HUD velocity");
	Review_Check(fabs(tr_vis_ang_y) < 0.001, "short yaw arc through 360");
	Review_Check(fabs(ui_rw_ref - 26.25) < 0.001, "energy reference is recorded line start");
	Review_Check(tr_cur_vel == '100 0 0', "visual helper does not overwrite save velocity");
	Review_Check(!strcmp(Rewind_At(), "0 0 0 20"), "resume request remains sampled tick/position");
	tr_practice = TRUE;
	command = SaveLoc_SaveCommand();
	Review_Check(tokenize(command) == 10, "practice save command acted");
	Review_Check(stof(argv(1)) == 0 && stof(argv(3)) == 20 && stof(argv(4)) == 100, "practice save not interpolated");
	Review_Check(tr_rep_end == 0 && buf_getsize(tr_rep_raw) == 1, "prefix ends at sampled save");
	Trail_ReplayClear();
	ln_brk[b + 1] = TRUE;
	Rewind_Cursor();
	Review_Check(rw_visualt == 0 && rw_visualp == '0 0 20', "no visual teleport join");
	bufstr_set(tr_raw, 1, "0.03 10 0 30 200 0 0 67108864 0 0 10 0 0 0");
	Trail_VisualState(0.015);
	Review_Check(tr_vis_vel == '100 0 0', "no velocity blend through raw break");
	bufstr_set(tr_raw, 2, "0.03 10 0 30 300 0 0 0 0 0 20 0 0 0");
	Trail_CursorState(0.03);
	Review_Check(tr_cur_vel == '300 0 0', "duplicate clock keeps last exact sample");
	Trail_VisualState(0.03);
	Review_Check(tr_vis_vel == '300 0 0', "visual duplicate endpoint");
	buf_del(tr_raw);
	tr_raw = 0;
	Trail_VisualState(0.015);
	Review_Check(!tr_vis_ok, "missing samples abstain instead of zero velocity");
	Rewind_Present();
	Review_Check(ui_rw_on && !ui_rw_velok, "HUD gets explicit unknown sample coverage");
	// Exhaust past key identities, not simultaneous holds. Slots must recycle.
	for (i = 0; i < RW_NAVN; i = i + 1)
	{
		rw_navscan[i] = 200 + i;
		rw_kdown[6 + i] = rw_kst[6 + i] = 0;
	}
	leftk = Rewind_KeyIx('j');
	Review_Check(leftk >= 6 && Rewind_NavDir(leftk) == -1, "released navigation slots recycle");
	if (leftk < 6)
	{
		tr_raw = oldraw;
		Rewind_Reset();
		Line_Clear(s);
		print("REVIEW FAIL: no safe navigation slot\n");
		return;
	}
	rw_kdown[leftk] = TRUE;
	rw_kst[leftk] = 1;
	k = Rewind_KeyIx('v');
	Review_Check(k >= 6 && k != leftk && Rewind_NavDir(k) == 1, "physical owners stay distinct");
	oldi = rw_i;
	Rewind_Track(IE_KEYDOWN, 'j');
	k = Rewind_InputEvent(IE_KEYDOWN, 'j', 0, 0);
	Review_Check(k && rw_i == oldi, "OS repeat is not another press step");
	Rewind_Track(IE_KEYUP, 'j');
	Review_Check(Rewind_InputEvent(IE_KEYUP, 'j', 0, 0), "owned navigation release consumed");
	for (i = 0; i < RW_NAVN; i = i + 1)
	{
		rw_navscan[i] = 0;
		rw_kdown[6 + i] = rw_kst[6 + i] = 0;
	}
	tr_raw = oldraw;
	tr_practice = FALSE;
	Rewind_Reset();
	Line_Clear(s);
	print(sprintf("REVIEW CHECKS: %g checks, %g failures\n", rh_checks, rh_fails));
};
'''

CFG = '''cfg_save_auto 0
name ReviewHUDControl
log_enable 1
log_dir logs
log_name runlines_smoke
cl_idlefps 0
cl_maxfps 100
set hud_rewind_chase 0
set hud_energy 1
set hud_speed 1
set hud_timer 1
set hud_rate 0
hud_trail 1
waitms 2000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
con_notifystyle 0
con_notifytime 0
con_notifytime_error 0
con_notifylines 0
bind j +moveleft
bind v +moveright
review_unit
cmd zone_goto 0
waitms 400
+forward
waitms 2300
-forward
cmd timer
rewind
waitms 100
rewind
waitms 400
bind j +moveleft
bind l +moveright
bind k +moveleft
rewind seek 0.6
waitms 200
echo ==== BASE ====
rewind status
cmd timer
cmd viewpos
rewind step 0.5
waitms 200
echo ==== HALF ====
rewind status
screenshot review_hud.png
vote key 106 1
waitms 300
echo ==== LEFT ====
rewind status
vote key 106 1
vote key 106 0
waitms 150
echo ==== STOP ====
rewind status
cmd viewpos
vote key 108 1
waitms 250
echo ==== RIGHT ====
rewind status
vote key 107 1
waitms 120
vote key 107 0
waitms 200
echo ==== FALLBACK ====
rewind status
vote key 108 0
waitms 100
rewind seek 0.7
vote key 106 1
bind j +jump
vote key 106 0
waitms 100
echo ==== REBOUND ====
rewind status
cmd viewpos
// A key held before opening is not adopted as navigation.
rewind
waitms 4200
cmd zone_goto 0
waitms 300
+forward
waitms 1400
-forward
vote key 108 1
+moveright
rewind
waitms 100
rewind
waitms 400
echo ==== BEFOREHELD ====
rewind status
waitms 250
echo ==== BEFOREHELD2 ====
rewind status
vote key 108 0
-moveright
rewind step -3
waitms 150
echo ==== BEFOREGO ====
rewind status
vote key 13 1
waitms 100
echo ==== PENDING ====
rewind status
vote key 13 0
waitms 3800
echo ==== CLOSED ====
rewind status
cmd timer
screenshot review_closed.png
echo RUNLINES COMPLETE
quit
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Test seam must match exactly once: {old!r}')
    return text.replace(old, new, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix='review-hud-source-', dir=a.output_dir))
    work.rmdir()
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(work), 'HEAD'], check=True)
    for rel in ('src/client/cl_hud.qc', 'src/client/cl_main.qc', 'src/client/cl_rewind.qc',
                'src/client/cl_timer.qc', 'src/client/cl_trailstate.qc', 'src/client/cl_trail.qc',
                'tools/runlines_smoke.py'):
        shutil.copy2(ROOT / rel, work / rel)
    shutil.copy2(ROOT / 'src/fteqcc64.exe', work / 'src/fteqcc64.exe')
    p = work / 'src/client/cl_rewind.qc'
    text = replace_once(p.read_text(), 'float() Rewind_Console =', SEAM + '\nfloat() Rewind_Console =')
    text = replace_once(text, 'if (argv(0) != "rewind")', 'if (argv(0) == "review_unit") { Review_Unit(); return TRUE; }\n\tif (argv(0) != "rewind")')
    text = replace_once(text, 'registercommand("rewind");', 'registercommand("rewind");\n\tregistercommand("review_unit");')
    # SaveLoc_SaveCommand is later in this module: test seam needs its prototype.
    text = replace_once(text, SEAM, 'string() SaveLoc_SaveCommand;\nvoid() Rewind_Reset;\n' + SEAM)
    p.write_text(text)
    cfg = work / 'ftesurf/cfg/test/rewind_hud.cfg'
    cfg.write_text(CFG)
    subprocess.run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8', '-QuakeDir', ''], cwd=work / 'src', check=True)
    result = subprocess.run([sys.executable, '-B', str(work / 'tools/runlines_smoke.py'), str(cfg),
                             '--dedicated', '--output-dir', str(a.output_dir)], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Acted dedicated control failed; retained paths printed above')
    rig = Path(result.stdout.strip().splitlines()[-1].removeprefix('Retained private rig: '))
    log = (rig / 'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
    checks = SEAM.count('Review_Check(')
    if f'REVIEW CHECKS: {checks} checks, 0 failures' not in log:
        raise RuntimeError('Visual/authenticated sample separation unit checks failed')
    phases = {}
    for part in log.split('==== ')[1:]:
        name = part.split(' ====')[0]
        match = re.search(r'rewind: HUD (\d+) time ([\d.]+) speed ([\d.-]+) e_line ([\d.-]+) index ([\d.]+) dir (-?\d+) sampled (\d+)', part)
        if not match:
            raise RuntimeError(f'No acted HUD state for {name}')
        phases[name] = tuple(float(v) for v in match.groups())
    for name in ('BASE', 'HALF', 'LEFT', 'STOP', 'RIGHT', 'FALLBACK', 'REBOUND', 'BEFOREHELD', 'BEFOREHELD2', 'BEFOREGO'):
        assert phases[name][0] == 1 and phases[name][6] == 1, (name, phases[name])
    assert abs(phases['HALF'][4] - phases['BASE'][4] - 0.5) < 0.001
    assert phases['HALF'][1] > phases['BASE'][1]
    assert phases['LEFT'][4] < phases['HALF'][4] and phases['LEFT'][5] == -1
    assert phases['STOP'][5] == 0
    assert phases['RIGHT'][4] > phases['STOP'][4] and phases['RIGHT'][5] == 1
    assert phases['FALLBACK'][5] == 1, 'releasing newest left must resume held right'
    assert phases['REBOUND'][5] == 0, 'binding changes cannot strand the old direction'
    assert phases['BEFOREHELD'][4] == phases['BEFOREHELD2'][4] and phases['BEFOREHELD2'][5] == 0
    assert phases['PENDING'][0] == 0 and phases['CLOSED'][0] == 0
    assert 'rewind: on 0 counting 0 sent 0' in log.split('==== CLOSED ====')[1]
    body = []
    for name in ('BASE', 'STOP', 'REBOUND'):
        part = log.split('==== ' + name + ' ====')[1].split('====')[0]
        m = re.search(r'setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', part)
        if m: body.append(m.groups())
    if len(body) != 3 or len(set(body)) != 1:
        raise RuntimeError(f'Pinned physical body moved or missing acted viewpos: {body}')
    for shot in ('review_hud.png', 'review_closed.png'):
        assert list(rig.rglob(shot)), f'Missing actual HUD screenshot {shot}'
    print(f'{checks} exact-sample/visual controls and 12 acted dedicated HUD/input phases passed.')
    print('Retained source:', work)
    print('Retained rig:', rig)


if __name__ == '__main__':
    main()
