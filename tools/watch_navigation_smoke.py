#!/usr/bin/env python3
"""Private real-socket demo navigation controls; no install data is touched.

Pre-registered: the unchanged baseline must reject this same oracle. Bare strafe
binds pause/seek continuously with acceleration; opposed directions cancel;
release stops even behind chat/console/menu; pre-open repeats do not take over;
rebinds retain physical ownership; close/reopen cannot restart an owned press.
Arrows retain +/-5s jumps. Synthetic straight replay pose/HUD must follow seek;
this is viewer navigation, NOT recorder/evidence or human input-device proof.

python tools/watch_navigation_smoke.py --output-dir <private dir> [--baseline <pre-patch ref>]
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
void(string label) WatchNav_Probe =
{
	local float f;
	f = fopen(strcat("cfg/test/watch_nav_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("WATCH NAV WRITE FAILED\n"); return; }
	fputs(f, sprintf("cursor %.6f %d %d %.6f", cltime, rec_wt_open, rec_wt_paused, rec_wt_time));
	fputs(f, sprintf(" %.6f %.6f %.6f", rec_wt_org_x, rec_wt_org_y, rec_wt_org_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", rec_wt_vel_x, rec_wt_vel_y, rec_wt_vel_z));
	fclose(f);
	print("WATCH NAV PROBE ", label, "\n");
};
'''
SERVER = r'''
void(entity e, string label) WatchNav_Body =
{
	local float f;
	f = fopen(strcat("cfg/test/watch_body_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("WATCH NAV WRITE FAILED\n"); return; }
	fputs(f, sprintf("body %d %.6f %.6f %.6f", e.run_t_freeze, e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf(" %.6f %.6f %.6f\n", e.velocity_x, e.velocity_y, e.velocity_z));
	fclose(f);
	print("WATCH NAV BODY ", label, "\n");
};
'''
CFG = BASE + '''bind a +moveleft
bind d +moveright
bind g +moveleft
bind h +moveright
bind j +moveleft
watch_event down 100
replay cfg/test/runlines_sample.rec
waitms 800
replay pause
replay seek 20
wait 4
cmd watch_body first
watch_event down 100
waitms 500
watch_probe preopen
watch_event up 100
watch_event down 97
waitms 500
watch_probe left1
watch_event down 97
waitms 500
watch_probe left2
chat_open
watch_event up 97
wait 4
watch_probe chat_stop
waitms 500
watch_probe chat_end
watch_event down 27
watch_event up 27
watch_event down 100
waitms 500
watch_probe right
watch_event up 100
wait 4
watch_probe right_stop
waitms 500
watch_probe right_end
replay seek 20
watch_event down 103
watch_event up 103
wait 4
watch_probe tap
wait 12
screenshot watch_nav_cursor.png
wait 12
replay seek 20
watch_event down 103
watch_event down 104
wait 4
watch_probe oppose
waitms 500
watch_probe oppose_end
watch_event up 103
waitms 500
watch_probe oppose_release
watch_event up 104
replay seek 20
watch_event down 103
watch_event down 106
waitms 300
watch_probe same_left
watch_event up 103
waitms 300
watch_probe same_remaining
watch_event up 106
replay seek 20
chat_open
watch_event down 103
watch_event down 27
watch_event up 27
watch_event down 103
waitms 500
watch_probe chat_preheld
watch_event up 103
watch_event down 103
waitms 300
watch_probe chat_new
watch_event up 103
replay seek 20
watch_event down 103
bind g +moveright
waitms 500
watch_probe rebind_held
watch_event up 103
wait 4
watch_probe rebind_stop
waitms 500
watch_probe rebind_end
watch_event down 103
waitms 500
watch_probe rebind_new
watch_event up 103
replay seek 20
watch_event down 103
replay stop
watch_event down 103
wait 4
watch_probe closed
replay cfg/test/runlines_sample.rec
replay pause
replay seek 20
watch_event down 103
waitms 500
watch_probe reopened
watch_event up 103
bind g +moveleft
watch_event down 103
waitms 300
watch_probe console_before
toggleconsole
watch_event up 103
wait 4
watch_probe console_stop
waitms 500
watch_probe console_end
toggleconsole
watch_event down 104
waitms 300
watch_probe menu_before
togglemenu
wait 4
watch_probe menu_stop
waitms 500
watch_probe menu_end
watch_event up 104
ui_close
replay seek 20
watch_event down 103
watch_event focus 0
wait 4
watch_probe focus_stop
watch_event down 103
waitms 500
watch_probe focus_end
watch_event up 103
replay seek 20
watch_event down 130
watch_event up 130
wait 4
watch_probe arrow_left
watch_event down 131
watch_event up 131
wait 4
watch_probe arrow_right
replay seek 0
watch_event down 103
waitms 400
watch_probe clamp_start
watch_event up 103
replay seek end
watch_event down 104
waitms 400
watch_probe clamp_end
watch_event up 104
cmd watch_body last
replay seek 20
watch_event down 32
watch_event up 32
waitms 400
watch_probe play
watch_event down 32
watch_event up 32
replay stop
echo RUNLINES COMPLETE
quit
'''


def row(gd, name, prefix, count):
    lines = (gd / 'cfg/test' / name).read_text().splitlines()
    assert len(lines) == 1 and lines[0].split()[0] == prefix, name
    words = lines[0].split()[1:]
    assert len(words) == count, name
    data = [float(x) for x in words]
    assert all(math.isfinite(x) for x in data), name
    return data


def grade(gd):
    log = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    server = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    assert log.count('RUNLINES COMPLETE') == 1, 'did not complete'
    assert not any(s in log + server for s in ('WATCH NAV WRITE FAILED', 'Unknown command', 'QC VM error', 'Cannot call', 'stack overflow'))
    labels = re.findall(r'^watch_probe (\w+)$', CFG, re.M)
    points = {}
    for label in labels:
        assert log.count('WATCH NAV PROBE '+label+'\n') == 1, ('unacted/duplicate', label)
        points[label] = row(gd, f'watch_nav_{label}.txt', 'cursor', 10)
        p = points[label]
        if label != 'closed':
            assert p[1:3] == [1, 0 if label == 'play' else 1], (label, 'wrong playback state')
            # .03u exceeds six-decimal text plus float32 interpolation error
            # at this fixture's <=14500u coordinate magnitude (not pixel error).
            assert all(abs(a-b) < .03 for a, b in zip(p[4:7], [p[3]*100-11500, 1300, 14500])), (label, 'pose not cursor')
            assert p[7:] == [100, 0, 0], (label, 'velocity not replay')
    t = lambda label: points[label][3]
    assert t('preopen') == 20, 'pre-open repeat acquired navigation'
    assert 18.5 < t('left1') < 19.5 and t('left2') < t('left1') - 1, 'hold/repeat did not accelerate backward'
    for start, end in (('chat_stop', 'chat_end'), ('right_stop', 'right_end'), ('rebind_stop', 'rebind_end'), ('oppose', 'oppose_end'), ('console_stop', 'console_end'), ('menu_stop', 'menu_end'), ('focus_stop', 'focus_end')):
        assert t(start) == t(end) and points[end][0] - points[start][0] > .45, (start, 'stop/cancel drift')
    assert t('right') > t('chat_end') + .5, 'default right bind did not ACT'
    assert abs(t('tap') - 19.985) < 2e-5, 'remapped quick tap not one recorded tick'
    assert t('oppose_release') > t('oppose_end') + .5, 'remaining opposing key did not ACT'
    assert t('same_left') < 19.7 and t('same_remaining') < t('same_left') - .5, 'same-direction key ownership wrong'
    assert t('chat_preheld') == 20 and t('chat_new') < 19.7, 'chat-owned repeat acquired navigation or next press lost'
    assert t('rebind_held') < 19.5 and t('rebind_new') > t('rebind_end') + .5, 'physical rebind ownership wrong'
    assert points['closed'][1] == 0 and t('reopened') == 20, 'close/reopen repeat acquired navigation'
    assert t('console_before') < 20 and t('menu_before') > t('console_end'), 'focus subjects did not ACT'
    assert t('arrow_left') == 15 and t('arrow_right') == 20, 'arrows changed'
    assert t('clamp_start') == 0 and t('clamp_end') == 40, 'seek window clamp failed'
    assert 20.2 < t('play') < 20.7, 'space did not restart playback'
    first = row(gd, 'watch_body_first.txt', 'body', 7)
    last = row(gd, 'watch_body_last.txt', 'body', 7)
    assert first == last and first[0] == 1, 'native pinned body moved/thawed'
    # Event dispatch really reached CSQC_InputEvent; this is not a direct handler call.
    events = re.findall(r'WATCH NAV EVENT (down|up|focus) (\d+) (\d+)', log)
    assert len(events) == len(re.findall(r'^watch_event ', CFG, re.M)), 'unacted input chain'
    assert ('down', '100', '0') in events and ('down', '97', '1') in events, 'input control/subject did not ACT'
    assert ('down', '103', '1') in events and ('up', '103', '1') in events, 'closed/rebound ownership missing'
    print(f'PASS demo navigation: {len(points)} cursor probes, {len(events)} whole-chain events, native pinned body unchanged')


def instrument(work):
    p = work / 'src/server/sv_timer.qc'
    p.write_text(p.read_text()+SERVER)
    p = work / 'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), '\tif (c == "rec_nack")', '\tif (c == "watch_body") { WatchNav_Body(self, argv(1)); return; }\n\tif (c == "rec_nack")'))
    p = work / 'src/client/cl_main.qc'
    text = once(p.read_text(), 'float(string cmd) CSQC_ConsoleCommand =', PROBE+'\nfloat(string cmd) CSQC_ConsoleCommand =')
    text = once(text, '\t// Patch 372.  `vote key', '\tif (argv(0) == "watch_probe") { WatchNav_Probe(argv(1)); return TRUE; }\n\tif (argv(0) == "watch_event")\n\t{\n\t\tlocal float kind, took;\n\t\tkind = IE_KEYDOWN;\n\t\tif (argv(1) == "up") kind = IE_KEYUP;\n\t\tif (argv(1) == "focus") kind = IE_FOCUS;\n\t\ttook = CSQC_InputEvent(kind, stof(argv(2)), 0, 0);\n\t\tprint(sprintf("WATCH NAV EVENT %s %g %g\\n", argv(1), stof(argv(2)), took));\n\t\treturn TRUE;\n\t}\n\t// Patch 372.  `vote key')
    text = once(text, '\tWatch_RegisterCvars();', '\tWatch_RegisterCvars();\n\tregistercommand("watch_probe");\n\tregistercommand("watch_event");')
    p.write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--grade-only', type=Path)
    ap.add_argument('--baseline', metavar='REF', help='unchanged pre-patch Git ref; never candidate source')
    ap.add_argument('--fps', type=int, choices=(30, 100, 300), default=100)
    ap.add_argument('--port', type=int, default=27617)
    a = ap.parse_args()
    if a.grade_only:
        grade(a.grade_only/'ftesurf')
        return
    a.output_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='watch-nav-source-', dir=a.output_dir))
    work.rmdir()
    subprocess.run(['git', '-C', str(ROOT), 'worktree', 'add', '--detach', str(work), a.baseline or 'HEAD'], check=True)
    if not a.baseline:
        for path in ('src/client/cl_watch.qc', 'src/client/cl_main.qc'):
            shutil.copy2(ROOT/path, work/path)
    shutil.copy2(ROOT/'src/fteqcc64.exe', work/'src/fteqcc64.exe')
    instrument(work)
    cfg = work/'ftesurf/cfg/test/watch_nav.cfg'
    cfg.write_text(CFG.replace('cl_maxfps 100\n', f'cl_maxfps {a.fps}\n'))
    sample = work/'ftesurf/cfg/test/watch_nav.rec'
    lines = ['FTESURF-REC 4', 'map surf_dune', 'track 0', 'startseg 0', 'leg 0', 'tickrate 0.015', 'flags 1', 'begin']
    for i in range(401):
        t = i/10
        lines.append(f'{t:.6f} {t*100-11500:.6f} 1300 14500 100 0 0 0 180 0 0 1 0 0 0 0 0')
    lines.append('end 2667')
    sample.write_text('\n'.join(lines)+'\n')
    subprocess.run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8', '-NoDeploy', '-QuakeDir', ''], cwd=work/'src', check=True)
    result = subprocess.run([sys.executable, '-B', str(work/'tools/runlines_smoke.py'), str(cfg), '--recording', str(sample), '--dedicated', '--port', str(a.port), '--timeout', '110', '--output-dir', str(a.output_dir)], capture_output=True, text=True)
    print(result.stdout)
    print('Retained source:', work)
    assert result.returncode == 0, result.stderr
    rigs = re.findall(r'^Retained private rig: (.+)$', result.stdout, re.M)
    assert len(rigs) == 1
    grade(Path(rigs[0])/'ftesurf')


if __name__ == '__main__':
    main()
