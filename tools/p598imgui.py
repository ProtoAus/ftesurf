#!/usr/bin/env python3
"""Disposable real QC -> NativeUI/1 -> ImGui -> 2DMesh/1 pixel/lifetime controls."""
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
from test_ui_modern import make_map
from p598build import build
ROOT = Path(__file__).resolve().parents[1]
ARMS = ('absent', 'scale1', 'scale2')
SHOTS = ('menu', 'menu_restart', 'client', 'client_close', 'both', 'plugin_off',
         'plugin_on', 'renderer', 'reconnected')


def cfg(arm, port):
    provider = arm != 'absent'
    vw, vh = (640,360) if arm == 'scale2' else (320,240)
    lines = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name imgui',
             'con_notifytime 0', 'con_notifylines 0', 'developer 0', 'cl_idlefps 0',
             'cl_maxfps 100', 'vid_vsync 0', 'vid_fullscreen 0', 'vid_winmaximize 0',
             'vid_width 640', 'vid_height 480', 'vid_conautoscale 0',
             f'vid_conwidth {vw}', f'vid_conheight {vh}', 'scr_consize 0',
             'vid_srgb 0', 'v_gamma 1', 'v_contrast 1', 'v_brightness 0',
             'set p595_menudraw 1', 'set p595_act 1', 'set p595_phase 0', 'waitms 1500']
    if provider: lines += ['plug_load ui_imgui', 'ui_imgui_status']
    lines += ['menu_restart', 'waitms 500', 'p595_menu show', 'waitms 500',
              'screenshot menu', 'menu_restart', 'waitms 700', 'set p595_phase 1',
              'screenshot menu_restart', 'p595_menu close', 'p595_menu hide',
              f'connect 127.0.0.1:{port}', 'waitms 6500', 'set p595_phase 2',
              'waitms 500', 'screenshot client', 'p595_client close', 'waitms 500',
              'set p595_phase 3', 'screenshot client_close', 'p595_menu show',
              'waitms 700', 'set p595_phase 4', 'screenshot both',
              'ui_imgui_status' if provider else 'echo P595 ABSENT', 'p595_menu close',
              'p595_menu hide']
    if provider:
        lines += ['ui_imgui_status', 'plug_close ui_imgui', 'waitms 700',
                  'set p595_phase 5', 'screenshot plugin_off', 'plug_load ui_imgui',
                  'waitms 700', 'set p595_phase 6', 'screenshot plugin_on',
                  'vid_restart', 'waitms 1800', 'set p595_phase 7', 'waitms 500',
                  'screenshot renderer', 'ui_imgui_status', 'disconnect', 'waitms 700',
                  f'connect 127.0.0.1:{port}', 'waitms 6500', 'set p595_phase 8',
                  'waitms 500', 'screenshot reconnected', 'set p595_act 0',
                  'p595_client close', 'p595_menu close', 'ui_imgui_status',
                  'waitms 700', 'ui_imgui_status']
    lines += ['echo P595 FINISHED', 'quit']
    return '\n'.join(lines)+'\n'


def pixels(path, native):
    im = Image.open(path).convert('RGB')
    if im.size != (640,480): return ['unexpected resolution']
    errors = []
    for label, p, color in (
        ('native/legacy', (180,180), (0,255,0) if native else (255,255,0)),
        ('after', (230,180), (0,0,255)), ('left', (50,100), (255,0,0)),
        ('top', (100,50), (255,0,0)), ('right', (575,100), (255,0,0)),
        ('bottom', (100,425), (255,0,0)), ('restored', (600,110), (255,255,255)),
        ('background', (5,5), (0,0,0))):
        actual = im.getpixel(p)
        if max(abs(a-b) for a,b in zip(actual,color)) > 8: errors.append(f'{label}: {actual} != {color}')
    if native:
        #Pixel evidence of real glyphs, not just green synthetic geometry/counters.
        for label,box in (('title',(62,78,410,91)), ('table',(65,155,145,265)),
                          ('tooltip',(350,340,485,390))):
            bright = sum(min(im.getpixel((x,y)))>150
                         for y in range(box[1],box[3]) for x in range(box[0],box[2]))
            if bright < 30: errors.append(f'{label}: glyph ink absent ({bright})')
        #Native rounded button top-left leaves its background visible.
        if im.getpixel((197,95)) == im.getpixel((185,95)):
            errors.append('rounded control has no corner/centre contrast')
    return errors


def grade(rig):
    errors = []
    report = json.loads((rig/'report.json').read_text())
    for arm in ARMS:
        root = rig/arm
        native = arm != 'absent'
        meta = report['arms'].get(arm,{})
        if meta.get('exit') != 0 or meta.get('timed_out'): errors.append(arm+': did not exit normally')
        text = '\n'.join(p.read_text(errors='replace') for p in (root/'ftesurf/logs').glob('imgui*.log'))
        if 'P595 FINISHED' not in text: errors.append(arm+': finish not reached')
        if re.search(r'Unknown command|QC runtime error|CSQC_Abort|Menu_Abort|Shader double free',text,re.I):
            errors.append(arm+': command/runtime/resource error')
        for vm in ('menu','client'):
            if not re.search(rf'P595 DRAW vm={vm} .*native={int(native)} .*before=1 after=1 legacy={int(not native)}',text):
                errors.append(arm+': '+vm+' did not act')
        shots = SHOTS if native else SHOTS[:5]
        for shot in shots:
            files = list((root/'ftesurf/screenshots').glob(shot+'.*'))
            if len(files) != 1: errors.append(f'{arm}/{shot}: missing/ambiguous shot')
            else: errors += [f'{arm}/{shot}: '+s for s in pixels(files[0],native and shot != 'plugin_off')]
        if native:
            rows = []
            for line in text.splitlines():
                if 'UIIMGUI STATUS' in line:
                    rows.append({k:int(v) for k,v in re.findall(r'(\w+)=(\d+)\b',line) if k != 'version'})
            if len(rows) < 5: errors.append(arm+': native status witnesses absent')
            else:
                if rows[0].get('frames') or rows[0].get('uploads'): errors.append(arm+': closed init work')
                if not any(r.get('live') == 2 and r.get('frames',0)>0 for r in rows):
                    errors.append(arm+': simultaneous VM context witness absent')
                if not any(r.get('renderer',0)>0 for r in rows): errors.append(arm+': renderer close not observed')
                if rows[-1] != rows[-2] or rows[-1].get('live') != 0 or rows[-1].get('opens') != rows[-1].get('closes'):
                    errors.append(arm+': closed work/resource balance')
                if any(r.get('rejected') for r in rows): errors.append(arm+': native submission rejected')
        #No ImGui ini/log side effects anywhere in the disposable install.
        if list(root.rglob('imgui.ini')) or list(root.rglob('imgui_log.txt')): errors.append(arm+': implicit ImGui file')
    for shot in SHOTS:
        if shot == 'plugin_off': continue
        a = list((rig/'scale1/ftesurf/screenshots').glob(shot+'.*'))
        b = list((rig/'scale2/ftesurf/screenshots').glob(shot+'.*'))
        if len(a) == len(b) == 1:
            diff = ImageChops.difference(Image.open(a[0]).convert('RGB'),Image.open(b[0]).convert('RGB'))
            if diff.getbbox(): errors.append(shot+': physical gallery differs across virtual scales')
    return errors


def run(a):
    if os.name != 'nt': raise RuntimeError('Runtime launch requires Windows; grade is portable')
    rig = Path(tempfile.mkdtemp(prefix='p595-imgui-',dir=ROOT/'rig'))
    (rig/'P595_RIG.txt').write_text('Owned disposable gallery; no owner fixtures.\n')
    plugin = a.plugin or build(a.fte.resolve(),rig/'build',a.cc.resolve())
    qc = rig/'qc'; qc.mkdir()
    for name in ('m_defs','cl_defs'): shutil.copy2(ROOT/'src/defs'/f'{name}.qc',qc/f'{name}.qc')
    for p in (ROOT/'src/shared/sh_nativeui.qc',ROOT/'tools/fixtures/p598imgui.qc'): shutil.copy2(p,qc/p.name)
    for name,defs in (('menu','m_defs'),('csprogs','cl_defs')):
        (qc/'progs.src').write_text(f'{rig/name}.dat\n{defs}.qc\nsh_nativeui.qc\np598imgui.qc\n')
        with (rig/f'compile-{name}.log').open('w') as out:
            rc = subprocess.run([str(ROOT/'src/fteqcc64.exe'),'-srcfile','progs.src'],cwd=qc,stdout=out,stderr=subprocess.STDOUT).returncode
        if rc or 'Done. 0 warnings' not in (rig/f'compile-{name}.log').read_text(errors='replace'):
            raise RuntimeError('QC compile failed: '+str(rig))
    report = {'utc':datetime.now(timezone.utc).isoformat(),'plugin_sha256':sha(plugin),'arms':{}}
    for arm in ARMS:
        root = rig/arm; game = root/'ftesurf'; game.mkdir(parents=True)
        shutil.copy2(a.engine,root/'ftesurf64.exe'); shutil.copy2(a.server,root/'fteqwsv64.exe')
        shutil.copy2(plugin,root/'fteplug_ui_imgui_x64.dll')
        for name in ('menu','csprogs'): shutil.copy2(rig/f'{name}.dat',game/f'{name}.dat')
        shutil.copy2(a.progs,game/'qwprogs.dat')
        (game/'downloads/csprogsvers').mkdir(parents=True)
        subprocess.run([os.sys.executable,str(ROOT/'tools/seed_csprogs.py'),str(game/'csprogs.dat')],check=True,stdout=subprocess.DEVNULL)
        (game/'maps').mkdir(); (game/'maps/p595_imgui.map').write_text(make_map())
        (game/'cfg').mkdir(); (game/'cfg/default.cfg').write_text('cfg_save_auto 0\n')
        (root/'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfImGuiFixture\nNAME "ImGui fixture"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p595-unused\n')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s: s.bind(('127.0.0.1',0)); port = s.getsockname()[1]
        (game/'probe.cfg').write_text(cfg(arm,port))
        svcmd = [str(root/'fteqwsv64.exe'),'-basedir',str(root),'-nohome','-noplugins','-port',str(port),
                 '+set','cfg_save_auto','0','+set','sv_public','0','+map','p595_imgui.map']
        clcmd = [str(a.engine.resolve() if a.installed else root/'ftesurf64.exe'),'-basedir',str(root),'-nohome','-nosound','-nocdaudio','-window',
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
        report['arms'][arm] = {'exit':rc,'timed_out':timed,'engine_sha256':sha(a.engine),
                              'csprogs_sha256':sha(game/'csprogs.dat'),'installed_executable':a.installed,
                              'plugin_fixture_sha256':sha(root/'fteplug_ui_imgui_x64.dll'),
                              'client_command':clcmd,'server_command':svcmd}
        (rig/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    errors = grade(rig); (rig/'grade.json').write_text(json.dumps({'errors':errors},indent=2)+'\n')
    for s in errors: print('FAIL',s)
    print('rig',rig,'failed',len(errors)); return int(bool(errors))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte',type=Path,default=Path('C:/msys64/home/Lex/fteqw-ui-bridge'))
    p.add_argument('--engine',type=Path,default=ROOT/'ftesurf64.exe')
    p.add_argument('--server',type=Path,default=Path('C:/FTEQuake/fteqwsv64.exe'))
    p.add_argument('--progs',type=Path,default=ROOT/'ftesurf/qwprogs.dat',help='Fixture server progs; allows clean NoDeploy worktrees')
    p.add_argument('--cc',type=Path,default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--plugin',type=Path)
    p.add_argument('--installed',action='store_true',help='Launch actual --engine path with disposable basedir/cwd; byte-identical installed plugin fixture')
    p.add_argument('command',nargs='?',choices=('run','grade'),default='run')
    p.add_argument('rig',nargs='?',type=Path)
    a = p.parse_args()
    if a.command == 'grade':
        errors = grade(a.rig)
        for s in errors: print('FAIL',s)
        print('failed',len(errors)); raise SystemExit(bool(errors))
    raise SystemExit(run(a))
