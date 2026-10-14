#!/usr/bin/env python3
"""Acted original KSF malformed/boundary refusals on a real dedicated socket."""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original', type=Path, required=True, help='valid original surf_null v3/18-cell main demo')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--csqc', type=Path, required=True)
    p.add_argument('--ssqc', type=Path, required=True)
    p.add_argument('--mqc', type=Path, required=True)
    a = p.parse_args()
    if not any((x/'OWNER.md').is_file() for x in [a.out, *a.out.parents]):
        p.error('--out requires an ancestor OWNER.md')
    a.out.mkdir(parents=True, exist_ok=True)
    source = a.original.read_bytes()
    version, _, _, marks, cells, ext = struct.unpack_from('<6i', source)
    if version != 3 or cells != 18:
        p.error('--original must be a v3/18-cell main surf_null clip')
    frameoff = 24 + ext*4 + marks*524
    mutations = {}
    for name, offset, value in [('bad-version',0,9), ('negative-marks',12,-1),
            ('too-many-marks',12,4097), ('bad-cells',16,9), ('negative-extension',20,-1),
            ('bad-touch',24+ext*4+4,7)]:
        b = bytearray(source)
        struct.pack_into('<i', b, offset, value)
        mutations[name] = bytes(b)
    mutations['truncated-frame'] = source[:-1]
    b = bytearray(source); struct.pack_into('<f',b,frameoff+4,float('nan'))
    mutations['nonfinite-pose'] = bytes(b)
    b = bytearray(source); struct.pack_into('<f',b,frameoff+13*4,float('inf'))
    mutations['nonfinite-analog'] = bytes(b)
    mutations['over-byte-cap'] = source + bytes((16<<20)+1-len(source))
    mutations['over-frame-cap'] = source[:frameoff] + source[frameoff:frameoff+cells*4]*40001
    # Complete, ordered layouts; reject AMBIGUOUS courses, not incidental disorder.
    bookoff = 24 + ext*4
    blocks = [source[bookoff+i*524:bookoff+(i+1)*524] for i in range(marks)]
    for name, touch, zone in [('ambiguous-start',3,1), ('ambiguous-finish',2,99)]:
        selected = next(b for b in blocks if struct.unpack_from('<3i',b)[1:] == (touch,zone))
        dup = sorted([*blocks,selected], key=lambda b: struct.unpack_from('<i',b)[0])
        head = bytearray(source[:bookoff]); struct.pack_into('<i',head,12,len(dup))
        mutations[name] = bytes(head) + b''.join(dup) + source[frameoff:]
    cases = [(n,'0 FW') for n in mutations] + [('bad-course','70 FW'),
                                               ('bad-style','0 XYZ'), ('bad-number','oops FW')]
    positive = a.out/'p705-positive.rec'; positive.write_bytes(source)
    also = ['--also','p705-positive.rec='+str(positive)]
    for name,data in mutations.items():
        target = a.out/('p705-'+name+'.rec'); target.write_bytes(data)
        also += ['--also','p705-'+name+'.rec='+str(target)]
    positivecmd = 'replay ksf cfg/test/p705-positive.rec surf_null 0 FW'
    cfg = ['cfg_save_auto 0','log_enable 1','log_dir logs','log_name runlines_smoke',
           'cl_idlefps 0','cl_maxfps 100','map surf_null','waitmap 60','waitms 8000',
           'menu_restart','ui_close','hud_watch_path 1']
    for name,context in cases:
        path = 'p705-'+name+'.rec' if name in mutations else 'p705-positive.rec'
        cfg += ['echo P705 EDGE '+name,positivecmd,'replay pause','wait 5','replay status',
                'replay ksf cfg/test/'+path+' surf_null '+context,'wait 5','replay status',
                'replay stop','echo P705 END '+name]
    cfg += ['echo RUNLINES COMPLETE','wait 3','quit']
    c = a.out/'edges.cfg'; c.write_text('\n'.join(cfg)+'\n')
    command = [sys.executable,str(ROOT/'tools/runlines_smoke.py'),str(c),'--content','C:/FTESurf',
               '--output-dir',str(a.out),'--mount','--dedicated','--map','surf_null','--port','27613',
               '--ssqc',str(a.ssqc),'--csqc',str(a.csqc),'--mqc',str(a.mqc),'--timeout','240',*also]
    r = subprocess.run(command,capture_output=True,text=True,cwd='C:/FTESurf')
    (a.out/'harness.log').write_text(r.stdout+r.stderr)
    if r.returncode: raise RuntimeError(r.stdout+r.stderr)
    rig = Path(re.search(r'Retained private rig: (.+)',r.stdout)[1])
    log = (rig/'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
    clean = re.sub(r'(?m)^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ','',log)
    results = {}
    for name,_ in cases:
        block = clean.split('P705 EDGE '+name+'\n')[1].split('P705 END '+name+'\n')[0]
        assert 'replay: opened in' in block and 'replay: cfg/test/p705-positive.rec\n' in block, name
        if name == 'bad-number':
            assert 'ksf <binary.rec>' in block and 'replay: nothing loaded' not in block
        else:
            states = re.findall(r'watch state open (\d+) on (\d+) cursor (\d+)',block)
            assert states and states[-1][0]=='0' and 'replay: nothing loaded' in block, (name,states)
            assert not int(states[-1][2]) & 1, (name,states)
        results[name] = 'PASS'
    assert not re.search(r'QC runtime error|CSQC_Abort|Menu_Abort',clean)
    (a.out/'summary.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results),rig)


if __name__ == '__main__': main()
