#!/usr/bin/env python3
"""Disposable MQC/CSQC explicit event/action controls; no device-input claims."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
from PIL import Image, ImageChops
from p590bridge import sha
from p598build import build, ROOT
from test_ui_modern import make_map

ARMS = ('absent', 'drawonly', 'scale1', 'scale2')
SHOTS = ('menu_initial', 'menu_changed', 'client_initial', 'client_changed',
         'client_reopen', 'both', 'plugin_off', 'plugin_on', 'renderer')


def exercise(vm):
    cmd = 'p599_'+vm+' event '
    def click(x, y):
        return [cmd+f'1 {x} {y}', 'waitms 150', cmd+'2 0 1', 'waitms 150', cmd+'2 0 0', 'waitms 150']
    result = click(100, 110)+click(242, 110)+click(100, 136)
    result += [cmd+'5 65 0', cmd+'5 66 0', 'waitms 150', cmd+'4 10 1', 'waitms 150',
               cmd+'4 10 0', 'waitms 150']
    #An acted held press is abandoned, never activating on the later release.
    result += [cmd+'1 100 110', 'waitms 150', cmd+'2 0 1', 'waitms 150',
               cmd+'6 0 0', cmd+'2 0 0', 'waitms 150']
    return result+click(100, 110)


def cfg(arm, port):
    vw, vh = (640,360) if arm == 'scale2' else (320,240)
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name input',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             'cl_maxfps 100', 'vid_vsync 0', 'vid_fullscreen 0', 'vid_winmaximize 0',
             'vid_width 640', 'vid_height 480', 'vid_conautoscale 0', f'vid_conwidth {vw}',
             f'vid_conheight {vh}', 'scr_consize 0', 'vid_srgb 0', 'v_gamma 1',
             'v_contrast 1', 'v_brightness 0', 'set p599_menu_act 1',
             'set p599_client_act 1', 'set p599_phase 0', 'waitms 1500']
    if arm != 'absent': lines += ['plug_load ui_imgui', 'ui_imgui_status']
    lines += ['menu_restart', 'waitms 500', 'p599_menu show', 'waitms 500', 'screenshot menu_initial']
    lines += exercise('menu')
    lines += ['set p599_phase 1', 'waitms 300', 'screenshot menu_changed', 'p599_menu stop',
              'p599_menu hide', f'connect 127.0.0.1:{port}', 'waitms 6500',
              'set p599_phase 2', 'waitms 500', 'screenshot client_initial']
    lines += exercise('client')
    lines += ['set p599_phase 3', 'waitms 300', 'screenshot client_changed', 'p599_client close',
              'waitms 500', 'set p599_phase 4', 'screenshot client_reopen', 'p599_menu show',
              'waitms 500', 'set p599_phase 5', 'screenshot both']
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['p599_menu stop', 'p599_menu hide']
    if arm != 'absent':
        lines += ['plug_close ui_imgui', 'waitms 500', 'set p599_phase 6', 'screenshot plugin_off',
                  'plug_load ui_imgui', 'waitms 700', 'set p599_phase 7', 'screenshot plugin_on',
                  'vid_restart', 'waitms 1800', 'set p599_phase 8', 'waitms 300', 'screenshot renderer',
                  'ui_imgui_status', 'p599_client stop', 'ui_imgui_status', 'waitms 500', 'ui_imgui_status']
    lines += ['echo P599 FINISHED', 'quit']
    return '\n'.join(lines)+'\n'


def pixels(path, native):
    im = Image.open(path).convert('RGB')
    if im.size != (640,480): return ['unexpected resolution']
    errors = []
    for label, xy, rgb in (('before',(50,100),(255,0,0)), ('clip-top',(100,50),(255,0,0)),
                           ('clip-right',(575,100),(255,0,0)), ('clip-bottom',(100,425),(255,0,0)),
                           ('after',(230,180),(0,0,255)), ('restored',(600,110),(255,255,255)),
                           ('background',(5,5),(0,0,0))):
        actual = im.getpixel(xy)
        if max(abs(a-b) for a,b in zip(actual,rgb)) > 8: errors.append(label+' marker/clip/state failed')
    if native:
        if max(im.getpixel((400,220))) > 80: errors.append('native window background absent')
        for label, box in (('title',(62,78,410,91)), ('state',(62,151,340,165))):
            bright = sum(min(im.getpixel((x,y))) > 150 for y in range(box[1],box[3]) for x in range(box[0],box[2]))
            if bright < 30: errors.append(label+' glyph ink absent')
    elif max(abs(a-b) for a,b in zip(im.getpixel((400,220)),(255,255,0))) > 8:
        errors.append('usable covering legacy fixture absent')
    return errors


def grade(rig):
    report = json.loads((rig/'report.json').read_text())
    errors = []
    expected = [(1,1),(2,1),(3,2),(3,1),(1,2)]
    for arm in ARMS:
        root = rig/arm; native = arm.startswith('scale')
        meta = report.get('arms',{}).get(arm,{})
        if meta.get('exit') != 0 or meta.get('timed_out'): errors.append(arm+': no normal exit')
        text = '\n'.join(p.read_text(errors='replace') for p in (root/'ftesurf/logs').glob('input*.log'))
        if 'P599 FINISHED' not in text: errors.append(arm+': no finish')
        if re.search(r'Unknown command|QC runtime error|CSQC_Abort|Menu_Abort|Shader double free',text,re.I):
            errors.append(arm+': runtime/command/resource error')
        for vm in ('menu','client'):
            if not re.search(rf'P599 INIT vm={vm} available={int(native)}',text): errors.append(arm+': '+vm+' capability did not act')
            if not re.search(rf'P599 DRAW vm={vm} .*native={int(native)} .*before=1 after=1 legacy={int(not native)}',text):
                errors.append(arm+': '+vm+' explicit draw/fallback did not act')
            rows = re.findall(rf'P599 ACTION vm={vm} id=(\d+) generation=(\d+) value=(\d+)',text)
            if [(int(i),int(v)) for i,g,v in rows] != (expected if native else []):
                errors.append(arm+': '+vm+' actual widget actions/reset/once-only failed')
            generations = {int(g) for i,g,v in rows}
            if native and (len(generations) != 1 or 0 in generations): errors.append(arm+': '+vm+' action generation absent')
            events = re.findall(rf'P599 INPUT vm={vm} type=\d+ a=[-\d.]+ b=[-\d.]+ accepted=(\d)',text)
            if len(events) != 20 or any(int(x) != int(native) for x in events): errors.append(arm+': '+vm+' events did not all act')
        if native:
            menu_gen = set(re.findall(r'P599 ACTION vm=menu id=\d+ generation=(\d+)',text))
            client_gen = set(re.findall(r'P599 ACTION vm=client id=\d+ generation=(\d+)',text))
            if menu_gen & client_gen: errors.append(arm+': shared VM action generation')
        shots = SHOTS if arm != 'absent' else SHOTS[:6]
        for shot in shots:
            files = list((root/'ftesurf/screenshots').glob(shot+'.*'))
            if len(files) != 1: errors.append(arm+'/'+shot+': missing/ambiguous screenshot')
            else: errors += [arm+'/'+shot+': '+s for s in pixels(files[0],native and shot != 'plugin_off')]
        if native:
            rows = [{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)\b',line) if k != 'version'}
                    for line in text.splitlines() if 'UIIMGUI STATUS' in line]
            if len(rows) < 5: errors.append(arm+': resource witnesses absent')
            else:
                if rows[0].get('frames') or rows[0].get('uploads'): errors.append(arm+': closed init work')
                if not any(r.get('live') == 2 and r.get('frames',0) > 0 for r in rows): errors.append(arm+': both VMs did not act')
                if not any(r.get('renderer',0) > 0 for r in rows): errors.append(arm+': renderer release absent')
                if rows[-1] != rows[-2] or rows[-1].get('live') != 0 or rows[-1].get('opens') != rows[-1].get('closes'):
                    errors.append(arm+': closed resource/work balance')
                if any(r.get('rejected') for r in rows): errors.append(arm+': rejected native draw')
            for vm in ('menu','client'):
                files = [next((root/'ftesurf/screenshots').glob(vm+'_'+phase+'.*'),None) for phase in ('initial','changed')]
                if all(files):
                    a,b = (Image.open(p).convert('RGB').crop((62,95,195,165)) for p in files)
                    if not ImageChops.difference(a,b).getbbox(): errors.append(arm+': '+vm+' visible widget state unchanged')
        if list(root.rglob('imgui.ini')) or list(root.rglob('imgui_log.txt')): errors.append(arm+': implicit file side effect')
    for shot in SHOTS:
        a = next((rig/'scale1/ftesurf/screenshots').glob(shot+'.*'),None)
        b = next((rig/'scale2/ftesurf/screenshots').glob(shot+'.*'),None)
        if a and b and ImageChops.difference(Image.open(a).convert('RGB'),Image.open(b).convert('RGB')).getbbox():
            errors.append(shot+': physical output differs across virtual scales')
    return errors


def run(a):
    if os.name != 'nt': raise RuntimeError('Windows runtime required; grading is portable')
    rig = Path(tempfile.mkdtemp(prefix='p600-input-',dir=ROOT/'rig'))
    (rig/'P599_RIG.txt').write_text('Owned disposable QC transport controls; no device-input claim.\n')
    plugin = a.plugin or build(a.fte.resolve(),rig/'build',a.cc.resolve())
    qc = rig/'qc'; qc.mkdir()
    for name in ('m_defs','cl_defs'): shutil.copy2(ROOT/'src/defs'/f'{name}.qc',qc/f'{name}.qc')
    for p in (ROOT/'src/shared/sh_nativeui.qc',ROOT/'tools/fixtures/p600input.qc'): shutil.copy2(p,qc/p.name)
    for name,defs in (('menu','m_defs'),('csprogs','cl_defs')):
        (qc/'progs.src').write_text(f'{rig/name}.dat\n{defs}.qc\nsh_nativeui.qc\np600input.qc\n')
        with (rig/f'compile-{name}.log').open('w') as out:
            result = subprocess.run([str(ROOT/'src/fteqcc64.exe'),'-srcfile','progs.src'],cwd=qc,stdout=out,stderr=subprocess.STDOUT)
        if result.returncode or 'Done. 0 warnings' not in (rig/f'compile-{name}.log').read_text(errors='replace'):
            raise RuntimeError('QC compilation failed: '+str(rig))
    report = {'utc':datetime.now(timezone.utc).isoformat(),'plugin_sha256':sha(plugin),'arms':{}}
    for arm in ARMS:
        root = rig/arm; game = root/'ftesurf'; game.mkdir(parents=True)
        engine = a.old_engine if arm == 'drawonly' else a.engine
        shutil.copy2(engine,root/'ftesurf64.exe'); shutil.copy2(a.server,root/'fteqwsv64.exe')
        shutil.copy2(plugin,root/'fteplug_ui_imgui_x64.dll')
        for name in ('menu','csprogs'): shutil.copy2(rig/f'{name}.dat',game/f'{name}.dat')
        shutil.copy2(a.progs,game/'qwprogs.dat')
        (game/'downloads/csprogsvers').mkdir(parents=True)
        subprocess.run([os.sys.executable,str(ROOT/'tools/seed_csprogs.py'),str(game/'csprogs.dat')],check=True,stdout=subprocess.DEVNULL)
        (game/'maps').mkdir(); (game/'maps/p599_input.map').write_text(make_map())
        (game/'cfg').mkdir(); (game/'cfg/default.cfg').write_text('cfg_save_auto 0\n')
        (root/'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfInputFixture\nNAME "Native input fixture"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p599-unused\n')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s: s.bind(('127.0.0.1',0)); port = s.getsockname()[1]
        (game/'probe.cfg').write_text(cfg(arm,port))
        svcmd = [str(root/'fteqwsv64.exe'),'-basedir',str(root),'-nohome','-noplugins','-port',str(port),
                 '+set','cfg_save_auto','0','+set','sv_public','0','+map','p599_input.map']
        clcmd = [str(root/'ftesurf64.exe'),'-basedir',str(root),'-nohome','-nosound','-nocdaudio','-window',
                 '+set','plug_loaddefault','0','+set','vid_width','640','+set','vid_height','480',
                 '+set','vid_fullscreen','0','+set','vid_winmaximize','0','+set','vid_renderer','gl',
                 '+set','cfg_save_auto','0','+exec','probe.cfg']
        timed = False
        with (root/'server.log').open('w') as so, (root/'launch.log').open('w') as co:
            sv = subprocess.Popen(svcmd,cwd=root,stdout=so,stderr=subprocess.STDOUT)
            try:
                cl = subprocess.Popen(clcmd,cwd=root,stdout=co,stderr=subprocess.STDOUT)
                try: rc = cl.wait(timeout=65)
                except subprocess.TimeoutExpired: timed = True; cl.terminate(); rc = cl.wait(timeout=10)
            finally:
                if sv.poll() is None: sv.terminate(); sv.wait(timeout=10)
        report['arms'][arm] = {'exit':rc,'timed_out':timed,'engine_sha256':sha(engine),
                              'server_sha256':sha(a.server),'csprogs_sha256':sha(game/'csprogs.dat'),
                              'client_command':clcmd,'server_command':svcmd}
        (rig/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    errors = grade(rig); (rig/'grade.json').write_text(json.dumps({'errors':errors},indent=2)+'\n')
    for s in errors: print('FAIL',s)
    print('rig',rig,'failed',len(errors)); return int(bool(errors))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--engine',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqw64.exe'))
    p.add_argument('--server',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqwsv64.exe'))
    p.add_argument('--old-engine',type=Path,default=Path('C:/FTESurf/ftesurf64.exe'))
    p.add_argument('--progs',type=Path,default=Path('C:/FTESurf/ftesurf/qwprogs.dat'))
    p.add_argument('--cc',type=Path,default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--plugin',type=Path)
    p.add_argument('command',nargs='?',choices=('run','grade'),default='run')
    p.add_argument('rig',nargs='?',type=Path)
    a = p.parse_args()
    if a.command == 'grade':
        errors = grade(a.rig)
        for s in errors: print('FAIL',s)
        print('failed',len(errors)); raise SystemExit(bool(errors))
    raise SystemExit(run(a))
