#!/usr/bin/env python3
"""Disposable real MQC/CSQC counted models and stable actions; no installed changes."""
import argparse
import json
from pathlib import Path
import re
from PIL import Image, ImageChops
import p600input as transport
from p598build import ROOT

ARMS = ('absent','drawonly','inputonly','scale1','scale2')


def exercise(vm):
    cmd = 'p601_'+vm+' event '
    def click(x,y):
        return [cmd+f'1 {x} {y}', 'waitms 150', cmd+'2 0 1', 'waitms 150', cmd+'2 0 0', 'waitms 150']
    lines = click(110,122)+click(85,145)
    lines += [cmd+'1 110 122',cmd+'2 0 1','p601_'+vm+' reorder','waitms 150',cmd+'2 0 0','waitms 150']
    lines += click(110,145)
    lines += [cmd+'1 110 145','waitms 150',cmd+'2 0 1','waitms 150',
              'p601_'+vm+' delete','waitms 150',cmd+'2 0 0','waitms 150']
    return lines+click(110,145)


def cfg(arm,port):
    text = transport.cfg(arm,port)
    for vm in ('menu','client'):
        old = '\n'.join(transport.exercise(vm))
        assert old in text
        text = text.replace(old,'\n'.join(exercise(vm)))
    return text.replace('p599_','p601_').replace('P599 FINISHED','P601 FINISHED')


def pixels(path,native):
    errors = transport.pixels(path,False)
    if native:
        errors = [s for s in errors if s != 'usable covering legacy fixture absent']
        im = Image.open(path).convert('RGB')
        if im.size != (640,480): return errors
        if max(im.getpixel((400,220))) > 80: errors.append('model native background absent')
        for label,box in (('model-title',(78,78,420,91)),('plain-label',(78,95,225,108))):
            bright = sum(min(im.getpixel((x,y))) > 150 for y in range(box[1],box[3]) for x in range(box[0],box[2]))
            if bright < 30: errors.append(label+' glyph ink absent')
    return errors


def grade(rig):
    report = json.loads((rig/'report.json').read_text()); errors = []
    expected = [(11,91,1,1),(12,92,1,1),(11,91,1,3),(21,191,1,4)]
    for arm in ARMS:
        root=rig/arm; native=arm.startswith('scale'); meta=report.get('arms',{}).get(arm,{})
        if meta.get('exit') != 0 or meta.get('timed_out'): errors.append(arm+': no normal exit')
        text='\n'.join(p.read_text(errors='replace') for p in (root/'ftesurf/logs').glob('input*.log'))
        if 'P601 FINISHED' not in text: errors.append(arm+': no finish')
        if re.search(r'Unknown command|QC runtime error|CSQC_Abort|Menu_Abort|Shader double free',text,re.I):
            errors.append(arm+': runtime/command/resource error')
        for vm in ('menu','client'):
            if not re.search(rf'P601 INIT vm={vm} available={int(native)}',text): errors.append(arm+': '+vm+' capability did not act')
            if not re.search(rf'P601 DRAW vm={vm} .*native={int(native)} before=1 after=1 legacy={int(not native)}',text):
                errors.append(arm+': '+vm+' explicit draw/fallback did not act')
            rows=[tuple(map(int,row)) for row in re.findall(rf'P601 ACTION vm={vm} id=(\d+) row=(\d+) value=(\d+) revision=(\d+)',text)]
            if rows != (expected if native else []): errors.append(arm+': '+vm+' stable typed actions/replacement/once-only failed')
            models=[tuple(map(int,row)) for row in re.findall(rf'P601 MODEL vm={vm} revision=(\d+) count=(\d+) committed=(\d+) shape=(\d+)',text)]
            if native:
                if models[:4] != [(1,3,1,0),(2,3,1,0),(3,3,1,1),(4,3,1,2)]: errors.append(arm+': '+vm+' counted replacement did not act')
                if any(count!=3 or ok!=1 for rev,count,ok,shape in models): errors.append(arm+': '+vm+' incomplete/failed model')
            elif models: errors.append(arm+': '+vm+' unavailable model provider called')
            events=re.findall(rf'P601 INPUT vm={vm} type=\d+ a=[-\d.]+ b=[-\d.]+ accepted=(\d)',text)
            if len(events)!=18 or any(int(x)!=int(native) for x in events): errors.append(arm+': '+vm+' explicit inputs did not all act')
        shots=transport.SHOTS if arm!='absent' else transport.SHOTS[:6]
        for shot in shots:
            files=list((root/'ftesurf/screenshots').glob(shot+'.*'))
            if len(files)!=1: errors.append(arm+'/'+shot+': missing/ambiguous screenshot')
            else: errors += [arm+'/'+shot+': '+s for s in pixels(files[0],native and shot!='plugin_off')]
        if native:
            rows=[{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)\b',line) if k!='version'}
                  for line in text.splitlines() if 'UIIMGUI STATUS' in line]
            if len(rows)<5: errors.append(arm+': resource witnesses absent')
            else:
                if rows[0].get('frames') or rows[0].get('uploads'): errors.append(arm+': closed init work')
                if not any(r.get('live')==2 and r.get('frames',0)>0 for r in rows): errors.append(arm+': both VMs did not act')
                if not any(r.get('renderer',0)>0 for r in rows): errors.append(arm+': renderer release absent')
                if rows[-1]!=rows[-2] or rows[-1].get('live')!=0 or rows[-1].get('opens')!=rows[-1].get('closes'):
                    errors.append(arm+': closed resource/work balance')
                if any(r.get('rejected') for r in rows): errors.append(arm+': rejected native draw')
            for vm in ('menu','client'):
                files=[next((root/'ftesurf/screenshots').glob(vm+'_'+phase+'.*'),None) for phase in ('initial','changed')]
                if all(files):
                    a,b=(Image.open(p).convert('RGB').crop((78,95,305,165)) for p in files)
                    if not ImageChops.difference(a,b).getbbox(): errors.append(arm+': '+vm+' visible model unchanged')
        if list(root.rglob('imgui.ini')) or list(root.rglob('imgui_log.txt')): errors.append(arm+': implicit file side effect')
    for shot in transport.SHOTS:
        a=next((rig/'scale1/ftesurf/screenshots').glob(shot+'.*'),None)
        b=next((rig/'scale2/ftesurf/screenshots').glob(shot+'.*'),None)
        if a and b and ImageChops.difference(Image.open(a).convert('RGB'),Image.open(b).convert('RGB')).getbbox():
            errors.append(shot+': physical output differs across virtual scales')
    return errors


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--engine',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqw64.exe'))
    p.add_argument('--server',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqwsv64.exe'))
    p.add_argument('--old-engine',type=Path,default=ROOT/'rig/p600-input-gmbbkb_b/drawonly/ftesurf64.exe')
    p.add_argument('--input-engine',type=Path,default=ROOT/'rig/p600-input-gmbbkb_b/scale1/ftesurf64.exe')
    p.add_argument('--progs',type=Path,default=Path('C:/FTESurf/ftesurf/qwprogs.dat'))
    p.add_argument('--cc',type=Path,default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--plugin',type=Path)
    p.add_argument('command',nargs='?',choices=('run','grade'),default='run')
    p.add_argument('rig',nargs='?',type=Path)
    a=p.parse_args()
    if a.command=='grade':
        errors=grade(a.rig)
        for s in errors: print('FAIL',s)
        print('failed',len(errors)); raise SystemExit(bool(errors))
    raise SystemExit(transport.run(a,fixture='p601model.qc',config=cfg,grader=grade,prefix='p601-model-',
                                  arms=ARMS,engines={'inputonly':a.input_engine}))
