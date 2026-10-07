#!/usr/bin/env python3
"""Acted live-rewind navigation controls, in private real-socket overlays.

Bare bound strafe keys cancel opposing holds; either release resumes the other.
Tests drive the full CSQC input chain, not physical devices. Native sampled
selection and pinned server body/clock stay separate from the fractional HUD.
All instrumented programs remain private; never deploy the retained source rig.
"""
import argparse
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from stitched_rewind_smoke import BASE, once

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
void(string label) RewindNav_Probe =
{
	local float f, i, slot;
	local vector p;
	f = fopen(strcat("cfg/test/rewind_nav_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("REWIND NAV WRITE FAILED\n"); return; }
	i = floor(rw_i);
	slot = tr_live * LN_CAP + i;
	p = ln_pos[slot];
	fputs(f, sprintf("cursor %.6f %d %d %.6f %d %.6f %d\n", cltime, rw_on, rw_cd,
	                rw_i, rw_dir, ui_rw_time, ui_rw_on));
	fputs(f, strcat("native ", Rewind_At(), "\n"));
	fputs(f, sprintf("sample %g %g %g %g\n", rint(ln_t[slot] / tr_tick), p_x, p_y, p_z));
	fclose(f);
	print("REWIND NAV PROBE ", label, "\n");
};
'''
SERVER = r'''
void(entity e, string label) RewindNav_Body =
{
	local float f;
	f = fopen(strcat("cfg/test/rewind_body_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("REWIND NAV WRITE FAILED\n"); return; }
	fputs(f, sprintf("body %d %.6f %.6f %.6f", e.run_t_freeze, e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf(" %.6f %.6f %.6f %d\n", e.velocity_x, e.velocity_y, e.velocity_z, e.run_t_ticks));
	fclose(f);
	print("REWIND NAV BODY ", label, "\n");
};
'''
CFG = BASE + '''bind g +moveleft
bind h +moveright
bind j +moveleft
cmd zone_goto 0
waitms 400
+forward
waitms 4000
-forward
cmd timer
rewind_event down 104
rewind
waitms 100
rewind
waitms 600
rewind seek 1
wait 4
cmd rewind_body first
rewind_probe preopen
rewind_event down 104
waitms 300
rewind_probe preopen_end
rewind_event up 104
rewind_event down 103
waitms 200
rewind_probe left1
rewind_event down 103
waitms 200
rewind_probe left2
rewind_event up 103
wait 4
rewind_probe stopped
waitms 300
rewind_probe stopped_end
rewind seek 1
wait 4
rewind_probe tap_start
rewind_event down 103
rewind_event up 103
wait 4
rewind_probe tap
waitms 300
rewind_probe tap_end
rewind seek 1
rewind_event down 103
rewind_event down 104
wait 4
rewind_probe oppose
waitms 500
rewind_probe oppose_end
rewind_event up 103
waitms 300
rewind_probe remaining_right
rewind_event up 104
rewind seek 1
rewind_event down 104
rewind_event down 103
wait 4
rewind_probe reverse
waitms 500
rewind_probe reverse_end
rewind_event up 104
waitms 300
rewind_probe remaining_left
rewind_event up 103
rewind seek 1
rewind_event down 103
rewind_event down 106
waitms 200
rewind_probe same
rewind_event up 103
waitms 200
rewind_probe same_remaining
rewind_event up 106
rewind seek 1
rewind_event down 103
bind g +moveright
waitms 300
rewind_probe rebind_held
rewind_event up 103
wait 4
rewind_probe rebind_stop
waitms 300
rewind_probe rebind_end
rewind_event down 103
waitms 300
rewind_probe rebind_new
rewind_event up 103
bind g +moveleft
rewind seek 1
rewind_event down 103
waitms 300
rewind_probe chat_before
chat_open
rewind_event up 103
wait 4
rewind_probe chat_stop
waitms 300
rewind_probe chat_end
rewind_event down 27
rewind_event up 27
rewind seek 1
rewind_event down 103
waitms 300
rewind_probe console_before
toggleconsole
rewind_event up 103
wait 4
rewind_probe console_stop
waitms 300
rewind_probe console_end
toggleconsole
rewind seek 1
rewind_event down 104
waitms 300
rewind_probe menu_before
togglemenu
rewind_event up 104
wait 4
rewind_probe menu_stop
waitms 300
rewind_probe menu_end
ui_close
rewind seek 1
wait 4
rewind_probe arrow_start
rewind_event down 130
rewind_event up 130
wait 4
rewind_probe arrow_left
rewind_event down 131
rewind_event up 131
wait 4
rewind_probe arrow_right
cmd rewind_body last
cmd timer
rewind go
waitms 300
rewind_probe pending
rewind_event down 103
waitms 300
rewind_probe pending_end
rewind_event up 103
waitms 3800
rewind_probe closed
cmd timer
echo RUNLINES COMPLETE
quit
'''
# The live line samples render frames: 30 FPS has fewer indices per second.
# Stay away from its bounds so saturation cannot impersonate cancellation.
CFG = CFG.replace('rewind seek 1\n', 'rewind seek 2\n')


def row(path, label, count):
    parts = path.read_text().split()
    assert parts[0] == label and len(parts) == count + 1, ('bad row', path)
    values = tuple(map(float, parts[1:]))
    assert all(math.isfinite(v) for v in values), ('nonfinite', path)
    return values


def grade(rig):
    gd = rig / 'ftesurf'
    log = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    server = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    assert 'RUNLINES COMPLETE' in log and 'FTESurf CSQC loaded' in log
    assert not any(s in log + server for s in ('REWIND NAV WRITE FAILED', 'Unknown command',
                                              'QC VM error', 'Cannot call', 'stack overflow'))
    # The walk must have ACTED before opening; a stopped/practice fixture is not this arm.
    assert re.search(r'timer: running[^\n]*\n.*?practice 0  recording 1',
                     log.split('REWIND NAV PROBE preopen\n')[0], re.S), 'no running recording control'
    labels = re.findall(r'^rewind_probe (\w+)', CFG, re.M)
    rows = {}
    for label in labels:
        assert log.count('REWIND NAV PROBE ' + label + '\n') == 1, ('unacted/duplicate', label)
        path = gd / f'cfg/test/rewind_nav_{label}.txt'
        lines = path.read_text().splitlines()
        assert len(lines) == 3, ('bad probe', label)
        fields = lines[0].split()
        assert fields[0] == 'cursor' and len(fields) == 8
        rows[label] = tuple(map(float, fields[1:]))
        assert all(math.isfinite(v) for v in rows[label])
        native, sample = (tuple(map(float, line.split()[1:])) for line in lines[1:])
        assert lines[1].startswith('native ') and lines[2].startswith('sample ')
        assert len(native) == len(sample) == 4
        assert all(math.isfinite(v) for v in native + sample)
        if label not in ('pending', 'pending_end', 'closed'):
            assert rows[label][1:3] == (1, 0) and rows[label][6] == 1, ('not browsing', label)
            assert native == sample, ('native selection changed', label, native, sample)
    def pos(label): return rows[label][3]
    def direction(label): return rows[label][4]
    def stationary(a, b):
        assert rows[b][0] - rows[a][0] >= .25, ('wait unacted', a, b)
        assert abs(pos(a) - pos(b)) < .001 and direction(b) == 0, ('not stopped', a, b)
    stationary('preopen', 'preopen_end')
    assert 0 < pos('left2') < pos('left1') < pos('preopen_end')
    assert direction('left1') == direction('left2') == -1
    assert pos('left1') - pos('left2') > pos('preopen_end') - pos('left1'), 'hold did not accelerate'
    stationary('stopped', 'stopped_end')
    assert abs(pos('tap_start') - pos('tap') - 1) < .001, 'tap not one sample'
    stationary('tap', 'tap_end')
    for start, end, remaining, sign in (('oppose', 'oppose_end', 'remaining_right', 1),
                                        ('reverse', 'reverse_end', 'remaining_left', -1)):
        assert direction(start) == 0, ('opposing keys did not cancel', start)
        stationary(start, end)
        assert sign * (pos(remaining) - pos(end)) > 1 and direction(remaining) == sign, ('release unacted', remaining)
    assert 0 < pos('same_remaining') < pos('same') and direction('same_remaining') == -1
    assert pos('rebind_held') < pos('tap_start') and direction('rebind_held') == -1
    stationary('rebind_stop', 'rebind_end')
    assert pos('rebind_new') > pos('rebind_end') and direction('rebind_new') == 1
    for panel in ('chat', 'console', 'menu'):
        stationary(panel + '_stop', panel + '_end')
        assert direction(panel + '_before') != 0, ('panel control unacted', panel)
    assert abs(pos('arrow_start') - pos('arrow_left') - 1) < .001
    assert abs(pos('arrow_start') - pos('arrow_right')) < .001
    first = row(gd / 'cfg/test/rewind_body_first.txt', 'body', 8)
    last = row(gd / 'cfg/test/rewind_body_last.txt', 'body', 8)
    assert first == last and first[0] == 1 and first[4:7] == (0, 0, 0), ('body/clock moved', first, last)
    assert server.count('REWIND NAV BODY first\n') == server.count('REWIND NAV BODY last\n') == 1
    assert rows['pending'][1] == rows['pending_end'][1] == 1
    assert rows['pending'][2] > rows['pending'][0] and rows['pending_end'][2] > rows['pending_end'][0]
    assert rows['pending'][6] == rows['pending_end'][6] == 0
    assert pos('pending') == pos('pending_end') and direction('pending_end') == 0
    assert rows['closed'][1] == rows['closed'][6] == 0
    events = re.findall(r'REWIND NAV EVENT (\d+) (\d+) (\d+)\n', log)
    expected = re.findall(r'^rewind_event (down|up) (\d+)', CFG, re.M)
    assert [(int(k), int(key)) for k, key, _ in events] == [(0 if k == 'down' else 1, int(key)) for k, key in expected], 'unacted input chain'
    assert any(took == '1' for _, _, took in events), 'input chain never took navigation'
    print('Live rewind cancel/release/native/pinned-body controls PASS:', rig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path)
    ap.add_argument('--baseline', help='Only cl_rewind.qc comes from this inspected ref')
    ap.add_argument('--rig', type=Path, help='Regrade retained controls; no game launch')
    ap.add_argument('--fps', type=int, choices=(30, 100, 300), default=100)
    ap.add_argument('--client', type=Path)
    ap.add_argument('--port', type=int, default=27618)
    a = ap.parse_args()
    if a.rig:
        grade(a.rig)
        return
    if not a.output_dir:
        ap.error('--output-dir is required for a launch')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='rewind-nav-source-', dir=a.output_dir))
    work.rmdir()
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(work), 'HEAD'], check=True)
    for rel in ('src/client/cl_rewind.qc', 'src/client/cl_main.qc', 'tools/runlines_smoke.py'):
        shutil.copy2(ROOT / rel, work / rel)
    shutil.copy2(ROOT / 'src/fteqcc64.exe', work / 'src/fteqcc64.exe')
    if a.baseline:
        text = subprocess.check_output(['git', '-C', str(ROOT), 'show', a.baseline + ':src/client/cl_rewind.qc'], text=True)
        (work / 'src/client/cl_rewind.qc').write_text(text)
    p = work / 'src/server/sv_saveloc.qc'
    p.write_text(p.read_text() + SERVER)
    p = work / 'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), '\tif (c == "rec_nack")', '\tif (c == "rewind_body") { RewindNav_Body(self, argv(1)); return; }\n\tif (c == "rec_nack")'))
    p = work / 'src/client/cl_main.qc'
    text = once(p.read_text(), 'float(string cmd) CSQC_ConsoleCommand =', PROBE + '\nfloat(string cmd) CSQC_ConsoleCommand =')
    text = once(text, '\t// Patch 372.  `vote key', '\tif (argv(0) == "rewind_probe") { RewindNav_Probe(argv(1)); return TRUE; }\n\tif (argv(0) == "rewind_event")\n\t{\n\t\tlocal float kind, took;\n\t\tkind = (argv(1) == "up") ? IE_KEYUP : IE_KEYDOWN;\n\t\ttook = CSQC_InputEvent(kind, stof(argv(2)), 0, 0);\n\t\tprint(sprintf("REWIND NAV EVENT %d %d %d\\n", kind, stof(argv(2)), took));\n\t\treturn TRUE;\n\t}\n\t// Patch 372.  `vote key')
    text = once(text, '\tRewind_RegisterCvars();', '\tRewind_RegisterCvars();\n\tregistercommand("rewind_probe");\n\tregistercommand("rewind_event");')
    p.write_text(text)
    cfg = work / 'ftesurf/cfg/test/rewind_nav.cfg'
    cfg.write_text(CFG.replace('cl_maxfps 100', f'cl_maxfps {a.fps}'))
    subprocess.run(['pwsh', '-NoProfile', '-Command', './build.ps1 -Jobs 8 -NoDeploy'], cwd=work / 'src', check=True)
    cmd = [sys.executable, '-B', str(work / 'tools/runlines_smoke.py'), str(cfg), '--dedicated',
           '--port', str(a.port), '--output-dir', str(a.output_dir)]
    if a.client:
        cmd += ['--client', str(a.client)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Dedicated control did not complete; retain failure as unacted')
    rig = Path(result.stdout.strip().splitlines()[-1].removeprefix('Retained private rig: '))
    grade(rig)


if __name__ == '__main__':
    main()
