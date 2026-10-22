#!/usr/bin/env python3
"""Bounded P922 UI check using the existing isolated P603 actual-client rig.

P921 transport/function labels are historical from pre-claim qualification;
they are retained so the immutable original captures remain replayable.

--mode control compiles the inspected P920 sources through the SAME test seams.
No owner config/data, backend, accepted terms or native simulation claim.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
import p603scores as P

BASE = 'e7637907d7e369b594ca25ff45537001b716f907'
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--artifacts', type=Path, required=True)
ap.add_argument('--mode', choices=('control', 'subject'), required=True)
a = ap.parse_args()
a.out = a.out.resolve()
assert any((p / 'OWNER.md').is_file() for p in (a.out, *a.out.parents))
a.out.mkdir(parents=True, exist_ok=True)
assert not any((p / arm).exists() for p in a.out.glob('p603-scores-*')
               for arm in ('legacy', 'native1')), 'Do not replay an already launched runtime arm'
src = P.ROOT / 'src'
overrides = {}
if a.mode == 'control':
    for rel in ('client/cl_scores.qc', 'client/cl_scores_native.qc', 'menu/m_story.qc'):
        target = a.out / Path(rel).name
        target.write_bytes(subprocess.check_output(['git', '-C', str(P.ROOT), 'show', BASE + ':src/' + rel]))
        overrides[rel] = os.path.relpath(target, src).replace('\\', '/')
compile_client = P.compile_client
P.compile_client = lambda rig: compile_client(rig, overrides, minimal=True)

# Instrument only the real menu entry point; formatter and rendering remain real.
prefix = a.out / 'menu-prefix.qc'
prefix.write_text('#define m_consolecommand P921_RealMenuCommand\n')
lines = [os.path.relpath(a.out / 'menu.dat', src).replace('\\', '/')]
for line in (src / 'm_progs.src').read_text().splitlines()[1:]:
    name = line.strip()
    if name == 'menu/m_main.qc':
        lines.append(os.path.relpath(prefix, src).replace('\\', '/'))
    lines.append(overrides.get(name, line))
lines.append('../tools/fixtures/p922story_runtime.qc')
manifest = src / 'p922-menu.src'
assert not manifest.exists()
manifest.write_text('\n'.join(lines) + '\n')
try:
    r = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', manifest.name], cwd=src,
                       capture_output=True, text=True)
    (a.out / 'compile-menu.log').write_text(r.stdout + r.stderr)
    (a.out / 'menu-compiler-result.json').write_text(json.dumps({'returncode': r.returncode,
        'stdoutBytes': len(r.stdout), 'stderrBytes': len(r.stderr)}))
    assert r.returncode == 0 and 'Done. 0 warnings' in (r.stdout + r.stderr)
finally:
    manifest.unlink()
# P603 consumes only these two product artifacts; its CSQC is separately compiled.
(a.out / 'qwprogs.dat').write_bytes((a.artifacts / 'qwprogs.dat').read_bytes())
old_seed = P.seed

def seed(game, rows=8):
    old_seed(game, rows)
    for folder in (game / 'data/runs').glob('*/main'):
        for i, path in enumerate(sorted(folder.glob('*.rec'))):
            flag = (0, 128, 1)[i % 3]  # Actual TF_SEGMENT / TF_PRACTICE constants.
            path.write_text(path.read_text().replace('flags 0\n', f'flags {flag}\n'))
P.seed = seed
old_config = P.config

def config(arm, port):
    start = old_config(arm, port).split('scores tab local\n', 1)[0]
    lines = ['ui_menu_probe p921story', 'set lobby_dir ""', 'scores close',
             'scores tab local', 'scores filter all', '+showscores', 'waitms 600',
             'p603 probe peek', '-showscores', 'waitms 300', 'p603 probe released',
             '+showscores', 'waitms 300', 'p603 pin', 'p603 unpin', 'waitms 300',
             'p603 probe first_pin', '-showscores', 'waitms 300', 'p603 probe pinned_release',
             'scores close', '+showscores', 'waitms 300', 'p603 pin', 'p603 unpin',
             'p603 pin', 'p603 unpin', 'waitms 300', 'p603 probe second_right',
             'p603 escape', 'waitms 300', 'p603 probe escaped', 'scores open',
             'p603 field', 'p603 escape', 'waitms 300', 'p603 probe field_escaped',
             'scores tab local', 'scores open', 'scores style clean', 'scores filter all',
             'waitms 600', 'p603 filters all']
    def click(target, label):
        return ['p603 move ' + target, 'waitms 100', 'p603 down', 'waitms 100',
                'p603 up', 'waitms 300', 'p603 filters ' + label]
    lines += click('sb_fx', 'practice') + ['screenshot p921_local_practice']
    lines += click('sb_fa', 'all_again') + click('sb_t1', 'segmented')
    lines += ['screenshot p921_local_segmented'] + click('sb_ks1', 'sideways')
    lines += ['scores style sw', 'waitms 300', 'p603 filters command_sideways',
              'scores tab online', 'scores tab local', 'waitms 300', 'p603 filters retained',
              'scores style clean', 'scores filter all', 'waitms 300',
              'scores tab online', 'scores segmented 1', 'waitms 300', 'p603 tab online_segmented',
              'p603 escape', 'waitms 300', 'p603 probe final_closed', 'echo P921 FINISHED', 'quit']
    return start + '\n'.join(lines) + '\n'
P.config = config
rig = P.run(SimpleNamespace(out=a.out, plugin=Path('C:/FTESurf/fteplug_ui_imgui_x64.dll'),
    fte=Path('C:/msys64/home/Lex/fteqw'), cxx=Path('C:/msys64/ucrt64/bin/g++.exe'),
    arms=['legacy', 'native1'], engine=Path('C:/FTESurf/ftesurf64.exe'),
    server=Path('C:/FTEQuake/fteqwsv64.exe'), old_engine=None, old_plugin=None,
    qc_artifacts=a.out, http=False, dense=False, follow=False, life=False,
    font=False, font_fallback=False, renderer='gl'))
results = {}
for arm in ('legacy', 'native1'):
    logs = list((rig / arm / 'ftesurf/logs').glob('scores*.log'))
    assert logs
    text = '\n'.join(p.read_text(errors='replace') for p in logs)
    def state(label):
        m = re.search(r'P603 OWNER ' + label + r' held=(\d+) pin=(\d+) cursor=(\d+)', text)
        assert m, label
        return tuple(map(int, m.groups()))
    def filt(label):
        m = re.search(r'P603 FILTER ' + label + r' tab=(\d+) direction=(\d+) kind=(\d+) clean=(\d+) segmented=(\d+) practice=(\d+)', text)
        assert m, label
        return tuple(map(int, m.groups()))
    w = re.search(r'P603 WIDGETS all styles=(\d+) segmented=(\d+) practice=(\d+)', text)
    story = re.search(r'P921 STORY zero=(\d) one=(\d) many=(\d) unknown=(\d)', text)
    tests = {'peek_control': state('peek')[:2] == (1, 0),
        'ordinary_release': state('released') == (0, 0, 0),
        'right_click_acted': state('first_pin')[1] == 1,
        'pinned_survives_release': state('pinned_release')[0] == 0 and state('pinned_release')[1] == 1,
        'second_right_stays': state('second_right')[1] == 1,
        'escape_closes': state('escaped') == (0, 0, 0),
        'field_escape_closes': state('field_escaped') == (0, 0, 0),
        'local_widgets': w is not None and tuple(map(int, w.groups())) == (4, 1, 1),
        'mixed_seed_control': all(x > 0 for x in filt('all')[3:]),
        'practice_acts': filt('practice')[3:5] == (0, 0) and filt('practice')[5] > 0,
        'segmented_acts': filt('segmented')[3] == 0 and filt('segmented')[4] > 0 and filt('segmented')[5] == 0,
        'local_style_command_stays_local': filt('command_sideways')[:2] == (2, 1),
        'unclassified_not_relabelled': filt('command_sideways')[3:] == (0, 0, 0),
        'direction_retained': filt('retained')[:2] == (2, 1),
        'story_real_formatter': story is not None and story.groups() == ('1', '1', '1', '1'),
        'online_segmented_unchanged': 'P603 TAB online_segmented tab=1 online=1' in text,
        'closed_cursor_released': state('final_closed') == (0, 0, 0),
        'no_runtime_error': not re.search(r'QC runtime error|CSQC_Abort|Menu_Abort', text),
        'reached_end': 'P921 FINISHED' in text}
    state_row = re.search(r'P603 STATE first_pin h=(\d+) painted=(\d+) failed=(\d+)', text)
    assert state_row
    rendering = dict(zip(('handle', 'painted', 'failed'), map(int, state_row.groups())))
    (a.out / (arm + '-rendering.json')).write_text(json.dumps(rendering, indent=2))
    results[arm] = tests
    print(arm, sum(tests.values()), '/', len(tests), 'rendering:', rendering,
          'failed:', [k for k, v in tests.items() if not v])
(a.out / 'acceptance.json').write_text(json.dumps({'mode': a.mode, 'rig': str(rig), 'tests': results}, indent=2))
if a.mode == 'subject':
    assert all(all(v.values()) for v in results.values())
else:
    assert all(v['right_click_acted'] and not v['pinned_survives_release'] and not v['local_widgets'] and not v['story_real_formatter'] for v in results.values())
