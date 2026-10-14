#!/usr/bin/env python3
"""Original binary KSF playback (no converter used by the game), source witnesses."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import p702ksf_smoke as P

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--csqc', type=Path, required=True)
    p.add_argument('--ssqc', type=Path, required=True)
    p.add_argument('--mqc', type=Path, required=True)
    p.add_argument('--map', choices=('surf_null', 'surf_prosurf', 'surf_monolith'))
    a = p.parse_args()
    if not any((x/'OWNER.md').is_file() for x in [a.out, *a.out.parents]):
        p.error('--out requires an ancestor OWNER.md')
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'tools/ksf_samples.json').read_text())
    if a.map: manifest = [r for r in manifest if r['map'] == a.map]
    for index, mp in enumerate(dict.fromkeys(r['map'] for r in manifest)):
        group = [r for r in manifest if r['map'] == mp]
        cfg = ['cfg_save_auto 0', 'name KsfOriginalControl', 'log_enable 1', 'log_dir logs',
               'log_name runlines_smoke', 'cl_idlefps 0', 'cl_maxfps 100', 'con_notifytime 0',
               'waitms 1500', 'map '+mp, 'waitmap 60', 'waitms 8000', 'menu_restart', 'ui_close',
               'hud_watch_skipidle 0', 'hud_watch_info 1', 'hud_watch_path 1', 'hud_watch_path_ahead 1',
               'hud_watch_path_foreign 0.55', 'hud_lines_board 0', 'hud_lines_nums 0', 'hud_lines_edge 0', 'hud_trail 0']
        also = []; blobs = {}
        for r in group:
            name = r['alias']
            path = a.samples/r['file']; blobs[name] = path.read_bytes()
            also += ['--also', name+'.rec='+str(path)]
            cmd = 'replay ksf cfg/test/%s.rec %s %d %s' % (name, mp, r['bonus'], r['style'])
            cfg += ['echo P702 BEGIN '+name, cmd, 'replay pause', 'replay seek 0',
                    'waitms 100', 'replay status', 'replay trace %d 0.015' % (r['stop']-r['start']+1),
                    'wait 3', 'replay trace frames 60', 'replay play', 'wait 60', 'replay pause',
                    'echo P702 ADVANCE', 'replay status', 'screenshot '+name+'.png',
                    'replay seek end', 'echo P702 FINISH', 'replay status', 'replay stop', 'echo P702 END '+name]
        first = group[0]
        cmd = 'replay ksf cfg/test/%s.rec %s %d %s' % (first['alias'], mp, first['bonus'], first['style'])
        cfg += ['echo P704 ACTIVE REFUSAL', cmd, 'replay pause', 'wait 10',
                cmd.replace(' '+mp+' ', ' surf_wrong_ksf '), 'replay status', 'wait 10',
                'echo P704 END REFUSAL', 'echo RUNLINES COMPLETE', 'wait 3', 'quit']
        cpath = a.out/(mp+'.cfg'); cpath.write_text('\n'.join(cfg)+'\n')
        command = [sys.executable, str(ROOT/'tools/runlines_smoke.py'), str(cpath), '--content', 'C:/FTESurf',
                   '--output-dir', str(a.out), '--mount', '--dedicated', '--map', mp, '--port', str(27610+index),
                   '--ssqc', str(a.ssqc), '--csqc', str(a.csqc), '--mqc', str(a.mqc), '--timeout', '240', *also]
        result = subprocess.run(command, capture_output=True, text=True)
        (a.out/(mp+'-harness.log')).write_text(result.stdout+result.stderr)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        rig = Path(re.search(r'Retained private rig: (.+)', result.stdout)[1])
        log = (rig/'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
        P.check_runtime(log, group, blobs)
        clean = re.sub(r'(?m)^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', log)
        for r in group:
            block = clean.split('P702 BEGIN '+r['alias']+'\n')[1].split('P702 END '+r['alias']+'\n')[0]
            finish = block.split('P702 FINISH\n')[1]
            ver = P.struct.unpack_from('<i', blobs[r['alias']])[0]
            assert ('KSF v%d %s' % (ver, r['style'])) in block
            assert 'Missing ground/moves are not invented.' in block
            text, _ = P.C.convert(blobs[r['alias']], mp, r['bonus'], r['style'])
            samples = [s.split() for s in text.splitlines() if s[0].isdigit() or s[0] == '-']
            got = re.search(r' keys (\d+)  ground (\d+)  duck (\d+)  flags (\d+)', finish)
            fl, keys = map(int, samples[-1][9:11])
            assert list(map(int, got.groups())) == [keys, fl & 1, 0, 0], (r['alias'], got.groups(), fl, keys)
        edge = clean.split('P704 ACTIVE REFUSAL\n')[1].split('P704 END REFUSAL\n')[0]
        assert 'refused' in edge and 'replay: nothing loaded' in edge
        states = re.findall(r'watch state open (\d+) on (\d+) cursor (\d+)', edge)
        assert states and all(int(o)==0 and int(on)==0 and not int(c)&1 for o,on,c in states), states
        assert not re.search(r'QC runtime error|CSQC_Abort|Menu_Abort', log)
        print(mp, len(group), 'original binary clips: full source traces, endpoint velocity/keys/state, pause/seek/advance/refusal PASS', rig)


if __name__ == '__main__': main()
