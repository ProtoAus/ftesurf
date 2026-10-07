#!/usr/bin/env python3
"""Acted replay draw-clock controls in a private overlay, with baseline rejection.

python tools/watch_clock_smoke.py --output-dir <private dir> --baseline <ref>
python tools/watch_clock_smoke.py --output-dir <private dir> --rig <retained rig>
Synthetic foreign/legacy fixtures are reader controls, not import-codec acceptance.
"""
import argparse
import contextlib
import io
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
POINTS = [('lead', -1), ('first', 0), ('fraction', 1.001), ('hold', 1.001),
          ('same_tick', 1.002), ('forward', 1.335), ('stop1', 3.125),
          ('stop2', 3.205), ('backward', 1.235), ('last', 6), ('tail', 7)]
KINDS = ('native', 'foreign', 'legacy')

PROBE = r'''
void(string chrome) WC_DrawProbe =
{
	local string label;
	local float f;
	label = cvar_string("wc_label");
	if (!strcmp(label, "")) return;
	cvar_set("wc_label", "");
	f = fopen(strcat("cfg/test/watch_clock_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("WATCH CLOCK WRITE FAILED\n"); return; }
	fputs(f, sprintf("%.6f %.6f %.6f %.6f", rec_wt_time, rec_wt_tickrate,
	                rec_wt_ticks, wc_panelticks));
	fputs(f, sprintf(" %g %g %g %g\n", wc_panelstate, rec_wt_state,
	                rec_wt_open, rec_wt_paused));
	fputs(f, sprintf("%.6f %.6f %.6f", rec_wt_org_x, rec_wt_org_y, rec_wt_org_z));
	fputs(f, sprintf(" %.6f %.6f %.6f %g %g\n", rec_wt_vel_x, rec_wt_vel_y,
	                rec_wt_vel_z, rec_wt_foreign, rec_wt_flags));
	fputs(f, strcat(wc_paneltext, "\n", chrome, "\n"));
	fclose(f);
	print(strcat("WATCH CLOCK PROBE ", label, "\n"));
};

'''
BODY = r'''
	if (!strcmp(c, "wcbody"))
	{
		local float f;
		f = fopen(strcat("cfg/test/watch_clock_body_", argv(1), ".txt"), FILE_WRITE);
		if (f < 0) { print("WATCH CLOCK BODY WRITE FAILED\n"); return; }
		fputs(f, sprintf("%g %.6f %.6f %.6f %.6f %.6f %.6f\n",
		                self.run_t_freeze, self.origin_x, self.origin_y, self.origin_z,
		                self.velocity_x, self.velocity_y, self.velocity_z));
		fclose(f);
		sprint(self, PRINT_HIGH, strcat("WATCH CLOCK BODY ", argv(1), "\n"));
		return;
	}
'''


def replace(path, old, new):
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'Private probe seam mismatch: {path.name}: {old!r}')
    path.write_text(text.replace(old, new), encoding='utf-8')


def prepare(tree):
    timer = tree/'src/client/cl_timer.qc'
    replace(timer, '// Extrapolation.\n',
            'float wc_panelticks, wc_panelstate;\nstring wc_paneltext;\n\n// Extrapolation.\n')
    replace(timer, '\tbw  = stringwidth(s, TRUE, [big, big]);',
            '\twc_panelticks = ticks;\n\twc_panelstate = state;\n'
            '\tif (strcmp(wc_paneltext, "")) strunzone(wc_paneltext);\n'
            '\twc_paneltext = strzone(s);\n\tbw  = stringwidth(s, TRUE, [big, big]);')
    watch = tree/'src/client/cl_watch.qc'
    replace(watch, 'void(vector scr) Watch_Chrome =', PROBE+'void(vector scr) Watch_Chrome =')
    replace(watch, '\twtitle = stringwidth(stitle, TRUE, [small, small]);',
            '\tWC_DrawProbe(sclock);\n\twtitle = stringwidth(stitle, TRUE, [small, small]);')
    main = tree/'src/server/sv_player.qc'
    replace(main, '\tif (c == "viewpos")', BODY+'\tif (c == "viewpos")')
    for kind in KINDS:
        tick = .01 if kind == 'foreign' else .015
        end = round(6/tick)
        ver = 3 if kind == 'legacy' else 10
        lines = [f'FTESURF-REC {ver}', 'map surf_dune', f'owner clock_{kind}',
                 f'tickrate {tick}', 'track 0', 'leg 0', 'startseg 0', 'segs 0',
                 'gravity 800', 'timerflags 128']
        if kind == 'foreign':
            lines += ['foreign momentum']
        lines += ['begin']
        for i in range(-2, 15):
            t = i*.5
            x = min(t, 2)*100-11500
            vel = 100 if t < 2 else 0
            row = f'{t:.4f} {x:.2f} 1300 14500'
            if kind != 'legacy':
                row += f' {vel} 0 0 0 0 0 0 0 0 0 0 0 1'
            lines.append(row)
        lines += [f'end {end} 17 0 0 0 0 0']
        dest = tree/'ftesurf/cfg/test'/f'watch_clock_{kind}.rec'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    cfg = ['cfg_save_auto 0', 'cl_idlefps 0', 'cl_maxfps 100', 'vid_width 1280',
           'vid_height 720', 'vid_fullscreen 0', 'vid_restart', 'log_enable 1',
           'log_name runlines_smoke', 'developer 0', 'con_notifylines 0',
           'map surf_dune', 'wait 240', 'menu_restart', 'wait 20', 'ui_close',
           'hud_timer 1', 'hud_speed 1', 'hud_watch_skipidle 0', 'set hud_heighthack 0',
           'hud_watch_scale 1', 'hud_scale 1', 'hud_update 0', 'hud_round 0',
           'hud_energy 1', 'replay cfg/test/watch_clock_native.rec', 'replay pause',
           'wait 100', 'cmd wcbody first', 'wait 20']
    for kind in KINDS:
        if kind != 'native':
            cfg += [f'replay cfg/test/watch_clock_{kind}.rec', 'replay pause', 'wait 30']
        for name, t in POINTS:
            label = f'{kind}_{name}'
            if name != 'hold':
                cfg.append(f'replay seek {t}')
            cfg += ['wait 15', f'set wc_label {label}', 'wait 4']
            if name in ('fraction', 'stop2', 'last'):
                cfg += [f'screenshot screenshots/watch_clock_{label}.png', 'wait 4']
    cfg += ['cmd wcbody last', 'wait 20', 'replay stop', 'wait 20',
            'echo RUNLINES COMPLETE', 'quit']
    (tree/'ftesurf/cfg/test/watch_clock_smoke.cfg').write_text('\n'.join(cfg)+'\n')


def seconds_text(seconds):
    ms = math.floor(max(0, seconds)*1000+.5)
    return f'{ms//60000}:{ms//1000%60:02d}.{ms%1000:03d}'


def read_probe(gd, label, log):
    assert log.count(f'WATCH CLOCK PROBE {label}\n') == 1, f'not acted once: {label}'
    lines = (gd/'cfg/test'/f'watch_clock_{label}.txt').read_text().splitlines()
    assert len(lines) == 4, (label, 'bad probe shape')
    a, b = [float(v) for v in lines[0].split()], [float(v) for v in lines[1].split()]
    assert len(a) == len(b) == 8 and all(math.isfinite(v) for v in a+b), label
    return a, b, lines[2], lines[3]


def grade(gd):
    log = (gd/'logs/runlines_smoke.log').read_text(errors='replace')
    server = (gd/'logs/runlines_server.log').read_text(errors='replace')
    assert 'RUNLINES COMPLETE' in log and 'FTESurf CSQC loaded' in log
    assert not any(s in log+server for s in ('WRITE FAILED', 'Unknown command',
                                           'QC VM error', 'Cannot call', 'stack overflow'))
    probes = {}
    for kind in KINDS:
        tick = .01 if kind == 'foreign' else .015
        for name, t in POINTS:
            label = f'{kind}_{name}'
            a, b, panel, chrome = read_probe(gd, label, log)
            assert abs(a[0]-t) < .00001 and abs(a[1]-tick) < .000001, label
            sampleticks = min(6/tick, max(0, math.floor(t/tick+.0001)))
            displayticks = min(6/tick, max(0, t/tick))
            state = 1 if t < 0 else 3 if t >= 6 else 2
            assert a[2] == sampleticks, (label, 'sampled tick semantics changed', a)
            assert abs(a[3]-displayticks) < .0001, (label, 'fractional panel input', a)
            assert a[4:8] == [state, state, 1, 1], (label, 'state', a)
            expected = seconds_text(min(6, max(0, t)))
            assert panel == expected, (label, panel, expected)
            assert chrome == f'{expected} / 0:06.000   1.00x  paused', (label, chrome, expected)
            assert abs(b[0]-(min(t, 2)*100-11500)) < .03, (label, 'pose', b)
            assert b[1:3] == [1300, 14500], label
            assert b[3:6] == ([0, 0, 0] if kind == 'legacy' or t >= 2 else [100, 0, 0]), label
            assert b[6] == (1 if kind == 'foreign' else 0) and b[7] == 0, label
            probes[label] = (a, b, panel, chrome)
        assert probes[f'{kind}_fraction'] == probes[f'{kind}_hold'], 'pause drift'
        # A stopped body still has a moving run clock, with no live-time leakage.
        assert probes[f'{kind}_stop1'][1] == probes[f'{kind}_stop2'][1], 'stop pose moved'
        assert probes[f'{kind}_stop1'][2] != probes[f'{kind}_stop2'][2], 'stop clock froze'
        assert probes[f'{kind}_fraction'][0][2] == probes[f'{kind}_same_tick'][0][2]
        assert probes[f'{kind}_fraction'][2] != probes[f'{kind}_same_tick'][2], 'quantized clock'
    bodies = []
    for label in ('first', 'last'):
        assert log.count(f'WATCH CLOCK BODY {label}\n') == 1, label
        b = [float(v) for v in (gd/'cfg/test'/f'watch_clock_body_{label}.txt').read_text().split()]
        assert len(b) == 7 and all(math.isfinite(v) for v in b) and b[0] == 1, label
        bodies.append(b)
    assert bodies[0] == bodies[1], 'native pin moved'
    print('PASS 33 acted fractional replay draw probes and unchanged native body')


def counterfactuals(gd, output):
    def field(g, line, index, value):
        p = g/'cfg/test/watch_clock_native_fraction.txt'
        lines = p.read_text().splitlines()
        words = lines[line].split()
        words[index] = str(value)
        lines[line] = ' '.join(words)
        p.write_text('\n'.join(lines)+'\n')

    def log_replace(g, new):
        p = g/'logs/runlines_smoke.log'
        p.write_text(p.read_text().replace('WATCH CLOCK PROBE native_fraction\n', new))

    cases = [
        ('missing', lambda g: (g/'cfg/test/watch_clock_native_fraction.txt').unlink()),
        ('unacted', lambda g: log_replace(g, '')),
        ('duplicate', lambda g: log_replace(g, 'WATCH CLOCK PROBE native_fraction\n'*2)),
        ('vm-error', lambda g: log_replace(g, 'QC VM error\nWATCH CLOCK PROBE native_fraction\n')),
        ('nonfinite', lambda g: field(g, 0, 0, 'nan')),
        ('wrong-time', lambda g: field(g, 0, 0, 1.006)),
        ('wrong-tickrate', lambda g: field(g, 0, 1, .01)),
        ('sample-mutated', lambda g: field(g, 0, 2, 67)),
        ('quantized-input', lambda g: field(g, 0, 3, 67)),
        ('wrong-state', lambda g: field(g, 0, 4, 3)),
        ('unpaused', lambda g: field(g, 0, 7, 0)),
        ('pose', lambda g: field(g, 1, 0, 99999)),
        ('velocity', lambda g: field(g, 1, 3, 0)),
        ('wrong-source', lambda g: field(g, 1, 6, 1)),
        ('flags-mutated', lambda g: field(g, 1, 7, 1)),
        ('body-missing', lambda g: (g/'cfg/test/watch_clock_body_last.txt').unlink()),
        ('body-drift', lambda g: (g/'cfg/test/watch_clock_body_last.txt').write_text('1 0 0 0 0 0 0\n')),
    ]
    for line, text in ((2, '0:01.000'), (3, '0:01.000 / 0:06.000')):
        def mutate(g, line=line, text=text):
            p = g/'cfg/test/watch_clock_native_fraction.txt'
            lines = p.read_text().splitlines()
            lines[line] = text
            p.write_text('\n'.join(lines)+'\n')
        cases.append((f'quantized-text-{line}', mutate))
    def terminal(g):
        p = g/'cfg/test/watch_clock_native_tail.txt'
        lines = p.read_text().splitlines()
        lines[2] = '0:07.000'
        p.write_text('\n'.join(lines)+'\n')
    cases.append(('terminal-clock-not-capped', terminal))
    root = Path(tempfile.mkdtemp(prefix='watch-clock-negatives-', dir=output))
    for name, mutate in cases:
        dest = root/name/'ftesurf'
        for rel in ('cfg/test', 'logs'):
            shutil.copytree(gd/rel, dest/rel)
        mutate(dest)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                grade(dest)
        except (AssertionError, ValueError, IndexError, FileNotFoundError):
            print('PASS rejects', name)
        else:
            raise AssertionError(f'grader accepted {name}: {dest}')
    print(f'{len(cases)+1} positive/counterfactual checks, 0 failed; artifacts {root}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--baseline')
    ap.add_argument('--rig', type=Path, help='grade retained probes and run counterfactuals only')
    a = ap.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    if a.rig:
        grade(a.rig/'ftesurf')
        counterfactuals(a.rig/'ftesurf', a.output_dir)
        return
    tree = Path(tempfile.mkdtemp(prefix='watch-clock-build-', dir=a.output_dir))
    if a.baseline:
        subprocess.run(['git', '-C', str(ROOT), 'archive', '-o', str(tree/'tree.tar'), a.baseline], check=True)
        subprocess.run(['tar', '-xf', str(tree/'tree.tar'), '-C', str(tree)], check=True)
    else:
        for name in ('src', 'tools', 'ftesurf/cfg'):
            shutil.copytree(ROOT/name, tree/name)
        for name in ('default.fmf', 'ftesurf/fs_addons.default.txt'):
            (tree/name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, tree/name)
    shutil.copy2(ROOT/'src/fteqcc64.exe', tree/'src/fteqcc64.exe')
    prepare(tree)
    subprocess.run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8',
                    '-QuakeDir', str(tree/'no-second-install')],
                   cwd=tree/'src', check=True)
    dest = tree/'ftesurf/cfg/test'
    subprocess.run(['git', 'init', '-q', str(tree)], check=True)
    subprocess.run(['git', '-c', 'core.autocrlf=false', '-C', str(tree), 'add', 'ftesurf/cfg'], check=True)
    subprocess.run(['python', str(tree/'tools/runlines_smoke.py'), str(dest/'watch_clock_smoke.cfg'),
                    '--dedicated', '--output-dir', str(a.output_dir), '--timeout', '150'], check=True)
    rigs = sorted(a.output_dir.glob('ftesurf-runlines-*'), key=lambda p: p.stat().st_mtime)
    gd = rigs[-1]/'ftesurf'
    if a.baseline:
        # Baseline must finish every same draw control, not fail to load or render.
        log = (gd/'logs/runlines_smoke.log').read_text(errors='replace')
        for kind in KINDS:
            for name, _ in POINTS:
                read_probe(gd, f'{kind}_{name}', log)
        try:
            grade(gd)
        except AssertionError as error:
            assert 'fractional panel input' in str(error), error
            print('PASS unchanged baseline ACTS and is rejected by fractional panel oracle')
        else:
            raise AssertionError('unchanged baseline unexpectedly passed')
    else:
        grade(gd)
        counterfactuals(gd, a.output_dir)
    print('Retained private rig:', gd.parent)


if __name__ == '__main__':
    main()
