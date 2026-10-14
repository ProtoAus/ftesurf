#!/usr/bin/env python3
"""All twelve public KSF samples: independent byte checks and dedicated playback.

--samples is the previously downloaded public binaries; --out must be an owned
TASK/artifacts directory. No installed data or source sample is changed.
"""
import argparse
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys

import ksfconvert as C

ROOT = Path(__file__).resolve().parent.parent


def raw_frame(data, tick):
    # Independent layout from public ReplayFile; not converter/inspector helpers.
    ver, kind, count, marks = struct.unpack_from('<4i', data)
    cells, off = 10, 16
    if ver == 3:
        cells, ext = struct.unpack_from('<2i', data, 16)
        off = 24 + ext * 4
    return struct.unpack_from('<i9f', data, off + marks * 524 + tick * cells * 4)


def check_bytes(text, data, row):
    samples = [s.split() for s in text.splitlines() if s[0].isdigit() or s[0] == '-']
    assert len(samples) == row['stop'] + 1
    for i, sample in enumerate(samples):
        b, x, y, z, p, yaw, roll, vx, vy, vz = raw_frame(data, i)
        expected = [(i - row['start']) * .015, x, y, z, vx, vy, vz, p, yaw]
        assert all(abs(a - float(g)) < 1e-6 for a, g in zip(expected, sample[:9])), (row['file'], i)
        # FSI direction is command direction; raw button mask is a separate record.
        fwd = float(bool(b & 8)) - float(bool(b & 16))
        side = float(bool(b & 1024)) - float(bool(b & 512))
        if struct.unpack_from('<i', data)[0] == 3:
            cells, ext = struct.unpack_from('<2i', data, 16)
            marks = struct.unpack_from('<i', data, 12)[0]
            if cells == 18:
                fwd, side = struct.unpack_from('<2f', data, 24 + ext*4 + marks*524 + i*cells*4 + 52)
        fwd, side = float('%.6f' % fwd), float('%.6f' % side)
        keys = sum(dst for src,dst in ((2,16),(4,32),(128,64),(256,128),(1,256)) if b & src)
        keys |= 1 if fwd > 0 else 2 if fwd < 0 else 0
        keys |= 8 if side > 0 else 4 if side < 0 else 0
        assert int(sample[10]) == keys
        assert 'ksfbuttons %d %d\n' % (i,b) in text
    assert samples[-1][0] == '%.4f' % ((row['stop'] - row['start']) * .015)


def check_runtime(log, group, data_by_alias, legacy=False):
    log = re.sub(r'(?m)^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', log)
    for row in group:
        name = row['alias']
        block = log.split('P702 BEGIN ' + name + '\n', 1)[1].split('P702 END ' + name + '\n', 1)[0]
        assert 'map %s  track %d seg 0  end %d  samples %d' % (row['map'], row['bonus'], row['stop'] - row['start'], row['stop'] + 1) in block
        if not legacy:
            assert 'import ksf  per-tick ground/velocity' in block
            assert 'map build unknown  duck state unknown  bookmark clock' in block
            assert 'momquality' not in block
        # Exact on-tick camera positions, sampled through the actual reader.
        traces = re.findall(r'^wtr ([^\n]+)', block, re.M)
        assert len(traces) == row['stop'] - row['start'] + 1, (name, len(traces))
        for line in traces:
            t, ex, ey, ez, pitch, yaw, src, fit, height = map(float, line.split())
            tick = row['start'] + round(t / .015)
            b, x, y, z, p, ya, roll, vx, vy, vz = raw_frame(data_by_alias[name], tick)
            # float32 QC clock and 3-decimal diagnostics vs unrounded source.
            assert max(abs(ex-x), abs(ey-y), abs(ez-height-z)) < .12, (name, tick, line, (x,y,z))
            assert abs(pitch-p) < .02, (name, tick, pitch, p)
            assert abs((yaw-ya+180) % 360-180) < .04, (name, tick, yaw, ya)
            assert src == 0  # no invented .view
        end = block.split('P702 FINISH\n')[1]
        org = re.search(r'org ([\d. -]+)  vel ([\d. -]+)', end)
        values = list(map(float, (org[1] + ' ' + org[2]).split()))
        r = raw_frame(data_by_alias[name], row['stop'])
        assert max(abs(a-b) for a,b in zip(values, [*r[1:4], *r[7:10]])) < .02, (name, values, r)
        advancing = block.split('P702 ADVANCE\n')[1].split('P702 FINISH\n')[0]
        time = float(re.search(r'  t ([\d.]+)', advancing)[1])
        frames = re.findall(r'^wtf ([^\n]+)', block, re.M)
        assert len(frames) >= 30, (name, len(frames))
        assert .3 < time < 30, (name, time)  # 60 real render frames, not only seeks
        assert 'foreign 1 tint' in block
    return len(group)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--csqc', required=True, type=Path)
    p.add_argument('--ssqc', required=True, type=Path)
    p.add_argument('--mqc', required=True, type=Path)
    p.add_argument('--map', choices=('surf_null','surf_prosurf','surf_monolith'))
    p.add_argument('--legacy', action='store_true', help='baseline capability/provenance control')
    p.add_argument('--edges-only', action='store_true', help='only native/Momentum/replacement-refusal controls')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    pack = a.out / 'converted'; pack.mkdir(exist_ok=True)
    manifest = json.loads((ROOT / 'tools/ksf_samples.json').read_text())
    if a.map: manifest = [r for r in manifest if r['map'] == a.map]
    blobs = {}
    for row in manifest:
        data = (a.samples / row['file']).read_bytes()
        text, info = C.convert(data, row['map'], row['bonus'], row['style'], row['owner'], row['seconds'])
        assert (info['start'], info['stop']) == (row['start'], row['stop'])
        check_bytes(text, data, row)
        (pack / (row['alias'] + '.rec')).write_text(text, encoding='utf-8')
        blobs[row['alias']] = data
    print('Exact byte/clock/key checks:', len(manifest), 'public clips')
    for index, mapname in enumerate(dict.fromkeys(r['map'] for r in manifest)):
        group = [r for r in manifest if r['map'] == mapname]
        cfg = ['cfg_save_auto 0', 'name KsfPlaybackControl', 'log_enable 1', 'log_dir logs',
               'log_name runlines_smoke', 'cl_idlefps 0', 'cl_maxfps 100', 'con_notifytime 0',
               'waitms 1500', 'map '+mapname, 'waitmap 60', 'waitms 8000', 'menu_restart', 'ui_close',
               'hud_watch_skipidle 0', 'hud_watch_info 1', 'hud_watch_path 1', 'hud_watch_path_ahead 1',
               'hud_watch_path_foreign 0.55', 'hud_lines_board 0', 'hud_lines_nums 0', 'hud_lines_edge 0',
               'hud_trail 0']
        also = []
        for row in ([] if a.edges_only else group):
            name = row['alias']
            cfg += ['echo P702 BEGIN '+name, 'replay cfg/test/'+name+'.rec noview', 'replay pause',
                    'replay seek 0', 'waitms 100', 'replay status',
                    'replay trace %d 0.015' % (row['stop']-row['start']+1),
                    'wait 3', 'replay trace frames 60', 'replay play', 'wait 60', 'replay pause',
                    'echo P702 ADVANCE', 'replay status', 'screenshot '+name+'.png',
                    'replay seek end', 'echo P702 FINISH', 'replay status', 'replay stop', 'echo P702 END '+name]
            also += ['--also', name+'.rec='+str(pack / (name+'.rec'))]
        # Existing native and momdemo paths must still act after a KSF clip.
        cfg += ['echo P702 NATIVE', 'replay cfg/test/runlines_peaks.rec noview', 'replay pause',
                'replay seek 0.03', 'replay status', 'replay trace 5 0.015', 'replay stop',
                'echo P702 MOMENTUM', 'replay cfg/test/runlines_peaks_mom.rec noview', 'replay pause',
                'replay seek 0.03', 'replay status', 'replay trace 5 0.015', 'replay stop']
        also += ['--also', 'runlines_peaks.rec='+str(ROOT/'ftesurf/cfg/test/runlines_peaks.rec'),
                 '--also', 'runlines_peaks_mom.rec='+str(ROOT/'ftesurf/cfg/test/runlines_peaks_mom.rec')]
        wrong = (pack/(group[0]['alias']+'.rec')).read_text().replace('map '+mapname+'\n', 'map surf_wrong_ksf_build\n')
        wrongpath = a.out/(mapname+'-wrong.rec'); wrongpath.write_text(wrong)
        also += ['--also', 'ksf_wrong.rec='+str(wrongpath)]
        cfg += ['echo P702 WRONG MAP', 'replay cfg/test/ksf_wrong.rec noview', 'replay status']
        valid = pack/(group[0]['alias']+'.rec')
        # --edges-only still needs a valid candidate loaded before each refusal.
        if a.edges_only:
            also += ['--also', valid.name+'='+str(valid)]
        missing = a.out/(mapname+'-missing.rec')
        missing.write_text(valid.read_text().replace('map '+mapname+'\n', ''))
        also += ['--also', 'ksf_missing.rec='+str(missing)]
        for case in ('MISSING', 'WRONG'):
            candidate = 'ksf_missing.rec' if case == 'MISSING' else 'ksf_wrong.rec'
            cfg += ['echo P702 ACTIVE '+case, 'replay cfg/test/'+valid.name+' noview', 'replay pause',
                    'wait 10', 'cmd viewpos', 'wait 10', 'replay cfg/test/'+candidate+' noview',
                    'replay status', 'wait 3', '+jump', '+forward', 'wait 60', '-forward', '-jump',
                    'cmd viewpos', 'wait 10', 'replay status', 'replay stop', 'echo P702 RELEASED '+case]
        cfg += ['echo RUNLINES COMPLETE', 'wait 3', 'quit']
        cfgpath = a.out / (mapname+'.cfg'); cfgpath.write_text('\n'.join(cfg)+'\n')
        command = [sys.executable, str(ROOT/'tools/runlines_smoke.py'), str(cfgpath), '--content', 'C:/FTESurf',
                   '--output-dir', str(a.out), '--mount', '--dedicated', '--map', mapname, '--port', str(27610+index),
                   '--ssqc', str(a.ssqc), '--csqc', str(a.csqc), '--mqc', str(a.mqc), '--timeout', '180', *also]
        r = subprocess.run(command, capture_output=True, text=True)
        (a.out/(mapname+'-harness.log')).write_text(r.stdout+r.stderr)
        if r.returncode: raise RuntimeError(r.stdout+r.stderr)
        rig = Path(re.search(r'Retained private rig: (.+)', r.stdout)[1])
        log = (rig/'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
        count = 0 if a.edges_only else check_runtime(log, group, blobs, a.legacy)
        control = re.sub(r'(?m)^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', log)
        native = control.split('P702 NATIVE\n')[1].split('P702 MOMENTUM\n')[0]
        momentum = control.split('P702 MOMENTUM\n')[1].split('P702 WRONG MAP\n')[0]
        assert 'foreign 0 tint' in native and len(re.findall(r'^wtr ', native, re.M)) == 5
        assert 'foreign 1 tint' in momentum and len(re.findall(r'^wtr ', momentum, re.M)) == 5
        if not a.legacy:
            assert 'import momentum  per-tick ground/velocity 1' in momentum
        refused = control.split('P702 WRONG MAP\n')[1].split('P702 ACTIVE MISSING\n')[0]
        assert 'this run is on surf_wrong_ksf_build' in refused and 'replay: nothing loaded' in refused
        for case in ('MISSING', 'WRONG'):
            edge = control.split('P702 ACTIVE '+case+'\n')[1].split('P702 RELEASED '+case+'\n')[0]
            assert 'refused' in edge and edge.count('replay: nothing loaded') == 2, (case, 'viewer not closed')
            states = re.findall(r'watch state open (\d+) on (\d+) cursor (\d+)', edge)
            assert len(states) == 2 and all(int(o) == 0 and int(on) == 0 and not int(c) & 1 for o,on,c in states), (case, states)
            positions = re.findall(r'^setpos ([^\n]+)', edge, re.M)
            assert len(positions) == 2, (case, positions)
            before, after = [list(map(float, p.split()))[:3] for p in positions]
            assert math.dist(before, after) > 2, (case, 'movement still pinned', before, after)
        print('Native/Momentum, cold wrong-map, active missing/wrong-map immediate state/cursor release and real body movement: PASS')
        print(mapname, count, 'played/paused/sought to finish; full on-tick camera traces match source', rig)


if __name__ == '__main__': main()
