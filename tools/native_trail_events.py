#!/usr/bin/env python3
"""Private dedicated native-touch/stop/rewind controls; diagnostic progs NEVER ship.

python tools/native_trail_events.py --output-dir <private directory> --fps 30
Synthetic AABB teleport volumes use the production handler and native mover on
real map ground. This is not authored-map BSP coverage or human camera acceptance.
"""
import argparse
from PIL import Image, ImageChops
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from stitched_rewind_smoke import BASE, SEAM, dump, once
from stitched_visual import grade as grade_visual, instrument as instrument_visual, trace

ROOT = Path(__file__).resolve().parents[1]
SERVER = r'''
// PRIVATE fixture: the engine must touch this volume, never a console call.
void() NativeEvent_Touch =
{
	local float f, ticks, state, live;
	local vector org, vel, ang, destorg;

	if (other.classname != "player") return;
	if (self.solid == SOLID_NOT) return;
	self.solid = SOLID_NOT;
	org = other.origin; vel = other.velocity; ang = other.v_angle;
	ticks = SV_TimerTicks(other); state = other.run_t_state; live = SV_RecLive(other);
	trigger_teleport_touch();
	f = fopen(strcat("cfg/test/native_touch_", self.message, ".txt"), FILE_WRITE);
	if (f < 0) { print("NATIVE EVENT WRITE FAILED\n"); return; }
	fputs(f, "FTESURF-NATIVE-EVENT 1\n");
	fputs(f, sprintf("mode %s\n", self.message));
	destorg = self.enemy.origin;
	fputs(f, sprintf("destination %.6f %.6f %.6f\n", destorg_x, destorg_y, destorg_z));
	fputs(f, sprintf("before %d %d %d", ticks, state, live));
	fputs(f, sprintf(" %.6f %.6f %.6f", org_x, org_y, org_z));
	fputs(f, sprintf(" %.6f %.6f %.6f", vel_x, vel_y, vel_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", ang_x, ang_y, ang_z));
	org = other.origin; vel = other.velocity; ang = other.v_angle;
	fputs(f, sprintf("after %d %d %d", SV_TimerTicks(other), other.run_t_state, SV_RecLive(other)));
	fputs(f, sprintf(" %.6f %.6f %.6f", org_x, org_y, org_z));
	fputs(f, sprintf(" %.6f %.6f %.6f", vel_x, vel_y, vel_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", ang_x, ang_y, ang_z));
	fclose(f);
	print("NATIVE EVENT TOUCH ", self.message, "\n");
};
void(entity e, string mode) NativeEvent_Fixture =
{
	local entity dest, trig;
	local vector p;

	if (e.run_t_state != TS_RUNNING || !SV_RecLive(e))
	{ print("NATIVE EVENT REFUSED not recording\n"); return; }
	if (strcmp(mode, "keep") && strcmp(mode, "zero"))
	{ print("NATIVE EVENT REFUSED mode\n"); return; }
	// Use the map's real floor so prediction sees the SAME collision surface.
	p = (!strcmp(mode, "keep")) ? '-11434 1320 14700' : '-11434 900 15400';
	traceline(p, p - '0 0 2000', MOVE_NOMONSTERS, world);
	if (trace_startsolid || trace_fraction >= 1)
	{ print("NATIVE EVENT REFUSED floor\n"); return; }
	p = trace_endpos;
	dest = spawn(); dest.classname = "info_teleport_destination";
	dest.targetname = (!strcmp(mode, "keep")) ? "native_event_keep" : "native_event_zero";
	dest.angles = (!strcmp(mode, "keep")) ? '0 180 0' : '0 270 0';
	setorigin(dest, p);
	trig = spawn(); trig.classname = "trigger_teleport";
	trig.target = dest.targetname; trig.enemy = dest;
	trig.message = (!strcmp(mode, "keep")) ? "keep" : "zero";
	trig.VelocityMode = (!strcmp(mode, "keep")) ? 0 : 1;
	trig.movetype = MOVETYPE_NONE; trig.solid = SOLID_TRIGGER;
	trig.touch = NativeEvent_Touch;
	setsize(trig, '-24 -24 -8', '24 24 80'); setorigin(trig, e.origin);
	print("NATIVE EVENT ARMED ", mode, "\n");
};
void(entity e, string label) NativeEvent_Probe =
{
	local float f;
	f = fopen(strcat("cfg/test/native_pose_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("NATIVE EVENT WRITE FAILED\n"); return; }
	fputs(f, sprintf("pose %d %d %d %d", SV_TimerTicks(e), e.run_t_state, SV_RecLive(e), e.run_t_freeze));
	fputs(f, sprintf(" %.6f %.6f %.6f", e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", e.velocity_x, e.velocity_y, e.velocity_z));
	fclose(f);
	print("NATIVE EVENT POSE ", label, "\n");
};
'''
CLIENT = r'''
void(string label) NativeEvent_Cursor =
{
	local float f;
	f = fopen(strcat("cfg/test/native_cursor_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("NATIVE EVENT WRITE FAILED\n"); return; }
	fputs(f, sprintf("cursor %.6f %d %d %.6f %.6f %.6f", cltime, rw_on, ui_rw_on, rw_i, rw_visualt, ui_rw_time));
	fputs(f, sprintf(" %.6f %.6f %.6f", rw_visualp_x, rw_visualp_y, rw_visualp_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", ui_rw_vel_x, ui_rw_vel_y, ui_rw_vel_z));
	fclose(f);
	print("NATIVE EVENT CURSOR ", label, "\n");
};
// A cfg request consumed at the final render call, not recomputed outside
// CSQC_UpdateView.
string nev_viewlabel;
void() NativeEvent_View =
{
	local float f;
	local vector p, a;
	if (nev_viewlabel == "") return;
	p = getproperty(VF_ORIGIN); a = getproperty(VF_ANGLES);
	f = fopen(strcat("cfg/test/native_view_", nev_viewlabel, ".txt"), FILE_WRITE);
	if (f < 0) { print("NATIVE EVENT WRITE FAILED\n"); return; }
	fputs(f, sprintf("view %d %d %d", cvar("hud_rewind_chase"), rw_on, ui_rw_on));
	fputs(f, sprintf(" %.6f %.6f %.6f", p_x, p_y, p_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", a_x, a_y, a_z));
	fclose(f);
	print("NATIVE EVENT VIEW ", nev_viewlabel, "\n");
	nev_viewlabel = "";
};
'''
CFG = BASE + '''visual_units
cmd zone_goto start
waitms 1200
+forward
waitms 1100
cmd timer
stitch_probe pre_keep
cmd native_event keep
waitms 500
stitch_probe post_keep
-forward
waitms 2500
stitch_probe pause_start
cmd native_pose pause_start
cmd timer
waitms 6000
stitch_probe pause_end
cmd native_pose pause_end
cmd timer
+forward
waitms 500
stitch_probe pre_zero
cmd native_event zero
waitms 500
stitch_probe post_zero
-forward
waitms 1200
stitch_probe live_end
rewind
rewind
waitms 1000
rewind seek 4
waitms 300
stitch_probe native1_cursor
visual_trace native1_cursor
native_cursor first
cmd native_pose freeze_first
waitms 1500
stitch_probe freeze_second
native_cursor second
cmd native_pose freeze_second
cmd timer
// Frame barriers: PNG encoding can consume a whole waitms interval without
// rendering the newly requested camera. Return is the reversible control.
set hud_rewind_chase 0
wait 12
native_view first
wait 3
screenshot native_events_first.png
wait 12
set hud_rewind_chase 1
wait 12
native_view chase
wait 3
screenshot native_events_chase.png
wait 12
set hud_rewind_chase 0
wait 12
native_view return
wait 3
screenshot native_events_return.png
wait 12
echo RUNLINES COMPLETE
quit
'''


def values(gd, rel, prefix, count):
    lines = (gd / 'cfg/test' / rel).read_text().splitlines()
    assert len(lines) == 1, (rel, 'duplicate/missing row')
    row = lines[0].split()
    assert len(row) == count + 1 and row[0] == prefix, (rel, 'malformed row')
    nums = list(map(float, row[1:]))
    assert all(math.isfinite(v) for v in nums), (rel, 'nonfinite row')
    return nums


def norm(v):
    return math.sqrt(sum(x*x for x in v))


def near(a, b, eps=.003):
    return len(a) == len(b) and all(abs(x-y) <= eps for x, y in zip(a, b))


def touch(gd, mode):
    lines = (gd / f'cfg/test/native_touch_{mode}.txt').read_text().splitlines()
    assert len(lines) == 5 and lines[:2] == ['FTESURF-NATIVE-EVENT 1', f'mode {mode}']
    dest = lines[2].split()
    assert len(dest) == 4 and dest[0] == 'destination'
    dest = list(map(float, dest[1:]))
    assert all(math.isfinite(x) for x in dest)
    assert dest[:2] == [-11434, 1320 if mode == 'keep' else 900]
    assert 14000 < dest[2] < 15400
    rows = []
    for label, line in zip(('before', 'after'), lines[3:]):
        r = line.split()
        assert len(r) == 13 and r[0] == label, (mode, 'malformed native touch')
        v = list(map(float, r[1:]))
        assert all(math.isfinite(x) for x in v), mode
        assert all(x == int(x) for x in v[:3]) and v[0] > 0 and v[1:3] == [2, 1], (mode, 'not running/recording')
        rows.append(v)
    before, after = rows
    assert after[0] == before[0], (mode, 'teleport retimed native clock')
    # The synthetic volume's destination is fixed; no client pose is authority.
    assert near(after[3:6], [dest[0], dest[1], dest[2]+1]), (mode, 'wrong native destination')
    assert norm([a-b for a, b in zip(after[3:6], before[3:6])]) > 500, (mode, 'handler did not move')
    assert norm(before[6:9]) > 20, (mode, 'incoming velocity did not ACT')
    if mode == 'keep':
        assert near(after[6:9], before[6:9]), 'keep changed velocity'
    else:
        assert near(after[6:9], [0, 0, 0]), 'zero failed to clear velocity'
    assert near(after[9:12], [0, 180 if mode == 'keep' else 270, 0]), (mode, 'view snap did not ACT')
    return rows


def grade(gd):
    gd = Path(gd)
    log = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    serverlog = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    assert 'RUNLINES COMPLETE' in log and 'FTESurf CSQC loaded' in log
    for bad in ('NATIVE EVENT REFUSED', 'NATIVE EVENT WRITE FAILED', 'STITCH PROBE WRITE FAILED',
                'Unknown command', 'QC VM error', 'Cannot call', 'stack overflow'):
        assert bad not in log + serverlog, bad
    _, _, raw = dump(gd, 'live_end')
    assert len(raw) > 30 and all(math.isfinite(x) for r in raw for x in r)
    assert all(b[0] >= a[0] for a, b in zip(raw, raw[1:])), 'running clock reset'
    breaks = [(i, r) for i, r in enumerate(raw) if i and r[8]]
    assert len(breaks) == 2 and all(not r[9] for _, r in breaks), 'native teleports not explicit'
    for mode, (i, r) in zip(('keep', 'zero'), breaks):
        before, after = touch(gd, mode)
        assert serverlog.count(f'NATIVE EVENT ARMED {mode}') == 1
        assert serverlog.count(f'NATIVE EVENT TOUCH {mode}') == 1, (mode, 'engine touch did not ACT')
        _, _, pre = dump(gd, f'pre_{mode}')
        _, _, post = dump(gd, f'post_{mode}')
        assert pre and len(post) > len(pre) and post[:len(pre)] == pre
        assert raw[:len(post)] == post and len(pre) <= i < len(post), (mode, 'uncorrelated event')
        assert sum(bool(p[8]) for p in post[len(pre):]) == 1, (mode, 'ambiguous native event')
        # A command snapshot can precede the corrected body snapshot. Bracket
        # the acted touch, not an invented exact instant-pose/latency contract.
        native_t = after[0]*.015
        assert pre[-1][0] <= native_t <= post[-1][0], (mode, 'wrong native event clock')
        assert pre[-1][0] <= r[0] <= post[-1][0], (mode, 'wrong raw event clock')
        before_dist = norm([a-b for a, b in zip(r[1:4], before[3:6])])
        after_dist = norm([a-b for a, b in zip(r[1:4], after[3:6])])
        assert after_dist < before_dist and after_dist < norm([a-b for a, b in zip(after[3:6], before[3:6])])/2
        assert norm([a-b for a, b in zip(r[1:4], raw[i-1][1:4])]) > 500
        print(f'Native/raw break offset {mode}: {r[0]-native_t:.6f}s, {after_dist:.3f}u; not instant-pose equivalence')
        assert abs((r[10]-after[10]+180) % 360-180) < .01, (mode, 'raw view missed snap')
        print('PASS engine-driven native teleport:', mode, 'ticks', int(after[0]))
    start = values(gd, 'native_pose_pause_start.txt', 'pose', 10)
    end = values(gd, 'native_pose_pause_end.txt', 'pose', 10)
    assert start[1:4] == end[1:4] == [2, 1, 0], 'pause not running/unheld/recording'
    assert end[0] - start[0] >= 390 and near(start[4:7], end[4:7])
    assert near(start[7:10], [0, 0, 0]) and near(end[7:10], [0, 0, 0])
    _, _, pause0 = dump(gd, 'pause_start')
    _, _, pause1 = dump(gd, 'pause_end')
    assert pause1[:len(pause0)] == pause0 and pause1[-1][0] - pause0[-1][0] > 5.8, 'counted stop lost'
    assert abs((end[0]-start[0])*.015 - (pause1[-1][0]-pause0[-1][0])) < .1
    for r in pause1:
        if r[0] >= pause0[-1][0]:
            assert near(r[1:4], start[4:7]) and near(r[4:7], [0, 0, 0]), 'raw/native pause mismatch'
    frozen1 = values(gd, 'native_pose_freeze_first.txt', 'pose', 10)
    frozen2 = values(gd, 'native_pose_freeze_second.txt', 'pose', 10)
    assert frozen1 == frozen2 and frozen1[1:4] == [2, 1, 1], 'pin clock/body drift'
    first = values(gd, 'native_cursor_first.txt', 'cursor', 12)
    second = values(gd, 'native_cursor_second.txt', 'cursor', 12)
    assert first[1:3] == second[1:3] == [1, 1] and second[0]-first[0] > 1.3, 'fixed cursor did not ACT'
    assert first[3:] == second[3:] and first[4] == first[5], 'fixed cursor HUD drift'
    assert near(first[9:12], [0, 0, 0]), 'real stop cursor is not stationary'
    assert pause0[-1][0] <= first[4] <= pause1[-1][0] and near(first[6:9], start[4:7]), 'cursor not on genuine pause'
    _, _, cursor = dump(gd, 'native1_cursor')
    _, _, frozen = dump(gd, 'freeze_second')
    assert cursor == frozen == raw, 'pin altered genuine picture'
    _, _, _, scan = trace(gd, 'native1_cursor')
    points = scan[::4]
    row = scan[round(first[3]*4)]
    for label, mode, pos, ang in (('first', 0, row[15:18], row[18:21]),
                                  ('chase', 1, row[21:24], row[24:27]),
                                  ('return', 0, row[15:18], row[18:21])):
        view = values(gd, f'native_view_{label}.txt', 'view', 9)
        assert view[:3] == [mode, 1, 1], (label, 'view-state mode did not ACT')
        assert near(view[3:6], pos) and near(view[6:9], ang), (label, 'view state differs from direct camera scan')
    assert sum(bool(p[27]) for p in points[1:]) == 2, 'render line lost native breaks'
    for _, r in breaks:
        assert any(p[27] and near(p[3:6], r[1:4]) for p in points), 'line event does not match raw'
    grade_visual(gd, phases=('native',), cuts=(1,), stop_labels=('pause_start', 'pause_end'))
    pictures = []
    for shot in ('native_events_first.png', 'native_events_chase.png', 'native_events_return.png'):
        paths = list(gd.rglob(shot))
        assert len(paths) == 1, ('missing/ambiguous screenshot artifact', shot)
        with Image.open(paths[0]) as image:
            assert image.size == (1920, 1111), ('unexpected screenshot viewport', image.size)
            # World-only patch: excludes timer, speed, footer and notifications.
            pictures.append(image.convert('RGB').crop((200, 200, 1400, 650)))
    changed = ImageChops.difference(pictures[0], pictures[1]).convert('L')
    restored = ImageChops.difference(pictures[0], pictures[2]).convert('L')
    changed_fraction = sum(n for v, n in enumerate(changed.histogram()) if v > 8) / (1200*450)
    restored_fraction = sum(n for v, n in enumerate(restored.histogram()) if v > 8) / (1200*450)
    assert changed_fraction > .05, ('camera pixels did not ACT', changed_fraction)
    assert restored_fraction < .01, ('return camera did not restore world pixels', restored_fraction)
    print(f'PASS camera render boundary and world pixels: changed {changed_fraction:.3f}, return {restored_fraction:.3f}')
    print('PASS native touches, counted stop and fixed-cursor freeze; authored BSP and human feel remain open.')


def instrument(work):
    p = work / 'src/server/sv_timer.qc'
    p.write_text(p.read_text() + SERVER)
    p = work / 'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), '\tif (c == "rec_nack")',
                     '\tif (c == "native_event") { NativeEvent_Fixture(self, argv(1)); return; }\n'
                     '\tif (c == "native_pose") { NativeEvent_Probe(self, argv(1)); return; }\n'
                     '\tif (c == "rec_nack")'))
    p = work / 'src/client/cl_trail.qc'
    text = once(p.read_text(), 'float() Trail_Console =', SEAM + '\nfloat() Trail_Console =')
    text = once(text, 'if (argv(0) != "trail")',
                'if (argv(0) == "stitch_probe") { Stitch_Probe(argv(1)); return TRUE; }\n\t'
                'if (argv(0) != "trail")')
    text = once(text, 'registercommand("trail");',
                'registercommand("trail");\n\tregistercommand("stitch_probe");')
    p.write_text(text)
    instrument_visual(work)
    # Rewind globals are declared after cl_trail.qc in the QC source order.
    p = work / 'src/client/cl_rewind.qc'
    text = once(p.read_text(), 'float() Rewind_Console =', CLIENT + '\nfloat() Rewind_Console =')
    text = once(text, 'if (argv(0) != "rewind")',
                'if (argv(0) == "native_cursor") { NativeEvent_Cursor(argv(1)); return TRUE; }\n\t'
                'if (argv(0) == "native_view") { nev_viewlabel = argv(1); return TRUE; }\n\t'
                'if (argv(0) != "rewind")')
    text = once(text, 'registercommand("rewind");',
                'registercommand("rewind");\n\tregistercommand("native_cursor");\n\tregistercommand("native_view");')
    p.write_text(text)
    p = work / 'src/client/cl_main.qc'
    p.write_text(once(p.read_text(), '\trenderscene();', '\tNativeEvent_View();\n\trenderscene();'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--grade-only', type=Path)
    ap.add_argument('--fps', type=int, choices=(30, 100, 300), default=100)
    ap.add_argument('--port', type=int, default=27617)
    a = ap.parse_args()
    if a.grade_only:
        grade(a.grade_only / 'ftesurf')
        return
    a.output_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='native-events-source-', dir=a.output_dir))
    work.rmdir()
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(work), 'HEAD'], check=True)
    shutil.copy2(ROOT / 'src/fteqcc64.exe', work / 'src/fteqcc64.exe')
    instrument(work)
    cfg = work / 'ftesurf/cfg/test/native_events.cfg'
    cfg.write_text(CFG.replace('cl_maxfps 100\n', f'cl_maxfps {a.fps}\n'))
    subprocess.run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8', '-NoDeploy', '-QuakeDir', ''],
                   cwd=work / 'src', check=True)
    result = subprocess.run([sys.executable, '-B', str(work / 'tools/runlines_smoke.py'), str(cfg),
                             '--dedicated', '--port', str(a.port), '--timeout', '100',
                             '--output-dir', str(a.output_dir)], capture_output=True, text=True)
    print(result.stdout)
    print('Retained source:', work)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Native fixture failed; preserve artifacts, do not weaken oracle')
    matches = re.findall(r'^Retained private rig: (.+)$', result.stdout, re.M)
    assert len(matches) == 1, 'missing/ambiguous retained rig'
    rig = Path(matches[0])
    grade(rig / 'ftesurf')


if __name__ == '__main__':
    main()
