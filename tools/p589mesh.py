#!/usr/bin/env python3
"""Native-only indexed 2D ABI falsifier. Disposable Windows rigs; portable grader.

Not an ImGui/QC bridge, mixed-QC clip test, or performance acceptance.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('control', 'subject1', 'subject2', 'disabled', 'none')
PHASES = ('initial', 'repeat', 'restart', 'reload')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def markers(text: str, kind: str) -> list[dict[str, int]]:
    return [{k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)\b', line)}
            for line in text.splitlines() if re.search(r'\bP589 '+re.escape(kind)+r'\b', line)]


def grade(rig: Path) -> list[str]:
    errors = []
    report = json.loads((rig/'report.json').read_text())
    captures = {}
    for arm in ARMS:
        if report['arms'][arm]['exit'] != 0:
            errors.append(arm+': abnormal process exit')
        root = rig/arm
        if arm == 'none':
            if markers((root/'none.txt').read_text(), 'NONE') != [{'video': 0, 'texture': 0, 'submit': 0}]:
                errors.append('none: startup rejection did not act')
            continue
        text = (root/'ftesurf/p589.log').read_text(errors='replace')
        active = arm != 'disabled'
        subject = arm.startswith('subject')
        init = markers(text, 'INIT')
        if active:
            if not init or any(r != {'available': int(subject), 'short': 1, 'long': 1, 'version': 1} for r in init):
                errors.append(arm+': ABI negotiation invalid')
            statuses = markers(text, 'STATUS')
            if len(statuses) != 4:
                errors.append(arm+': four status witnesses required')
            else:
                for i, r in enumerate(statuses):
                    if (r.get('frames',0) <= 0 or r.get('video') != 1
                            or [r.get(k) for k in ('pw','ph')] != [640,480]
                            or [r.get(k) for k in ('vw','vh')] != ([320,240] if arm == 'subject2' else [640,480])):
                        errors.append(arm+': rendered dimensions/action invalid')
                    if subject and (r.get('submitted',0) < r.get('frames',0)*3 or r.get('invalid') != 25
                                    or r.get('uploads') != (2 if i == 2 else 1) or r.get('stale') != (2 if i == 2 else 0)):
                        errors.append(arm+': submitted/invalid/restart witnesses invalid')
                if any(b['frames'] <= a['frames'] for a,b in zip(statuses[:2], statuses[1:3])):
                    errors.append(arm+': phases did not advance')
            if not markers(text,'OPEN') or markers(text,'OPEN')[0] != {'focus':1,'available':int(subject)}:
                errors.append(arm+': open action missing')
            if subject:
                invalid = markers(text,'INVALID')
                if invalid != [{'begin':1},{'end':1,'rejected':25,'life':7,'budget':61}]*2:
                    errors.append(arm+': invalid/lifetime/budget probes invalid')
                foreign = markers(text,'FOREIGN')
                if len(foreign) != 1 or foreign[0].get('token',0) <= 0 or foreign[0].get('rejected') != 2:
                    errors.append(arm+': foreign ownership did not act')
                if markers(text,'LEAK') != [{'created':32},{'created':32}]:
                    errors.append(arm+': unload/reload automatic cleanup did not act')
                reloads = markers(text,'RELOAD')
                if len(reloads) != 2 or reloads[0] != {'previous':0,'rejected':0} or reloads[1].get('previous',0) <= 0 or reloads[1].get('rejected') != 1:
                    errors.append(arm+': main plugin reload token rejection did not act')
                if markers(text,'VIDEO') != [{'restart':1,'stale':2}]:
                    errors.append(arm+': renderer teardown invalidation did not act')
            if re.search(r'Unknown command|QC runtime error|Shader double free',text,re.I):
                errors.append(arm+': command/runtime/resource error')
        elif markers(text,'INIT') or 'Unknown command "p589_open"' not in text:
            errors.append('disabled: plugin-disable control not reached')
        for phase in PHASES:
            im = Image.open(root/'ftesurf/screenshots'/f'{phase}.png').convert('RGB')
            captures[arm,phase] = im
            if im.size != (640,480):
                errors.append(arm+'/'+phase+': capture dimensions wrong')
                continue
            samples = {(28,28):(255,0,255), (270,270):(0,255,0), (410,80):(255,0,0),
                       (70,70):(0,0,0), (250,80):(0,0,0), (410,280):(0,0,0)}
            if subject:
                samples.update({(92,92):(255,0,0), (164,92):(0,255,0), (92,164):(0,0,128),
                                (164,164):(128,128,128), (440,104):(127,0,128),
                                (480,144):(255,0,0), (510,260):(0,255,0), (90,280):(0,255,255),
                                (79,100):(0,0,0), (176,100):(0,0,0), (100,79):(0,0,0), (100,176):(0,0,0)})
            else:
                samples.update({(96,96):(0,0,0),(160,160):(0,0,0),(440,104):(255,0,0),
                                (510,260):(0,0,0),(90,280):(0,0,0)})
            if not active:
                samples = {p:(0,0,0) for p in samples}
            for point,want in samples.items():
                if max(abs(a-b) for a,b in zip(im.getpixel(point),want)) > 2:
                    errors.append(arm+'/'+phase+': pixel '+str(point)+' expected '+str(want)+' got '+str(im.getpixel(point)))
        for phase in PHASES[1:] if active else ():
            if ImageChops.difference(captures[arm,'initial'],captures[arm,phase]).getbbox():
                errors.append(arm+'/'+phase+': repeated/reloaded gallery changed')
    for phase in PHASES:
        if ImageChops.difference(captures['subject1',phase],captures['subject2',phase]).getbbox():
            errors.append(phase+': virtual-scale physical gallery differs')
    return errors


def cfg(scale: int, active: bool, none: bool = False) -> str:
    head = f'''cfg_save_auto 0
cl_idlefps 0
cl_maxfps 100
sv_public 0
vid_vsync 0
vid_width 640
vid_height 480
vid_winmaximize 0
vid_fullscreen 0
vid_conautoscale 0
vid_conwidth {640//scale}
vid_conheight {480//scale}
r_font_postprocess_outline 0
log_enable 1
log_developer 1
log_readable 7
log_name p589
'''
    if none:
        return head+'wait 200\nquit\n'
    head += '''wait 100
plug_load p589mesh
wait 20
p589_open
wait 30
p589_invalid
'''
    if active:
        head += '''plug_load p589foreign
p589_foreign
p589_leak
plug_close p589foreign
plug_load p589foreign
p589_leak
plug_close p589foreign
'''
    return head+'''wait 100
p589_status
screenshot initial.png
wait 100
p589_status
screenshot repeat.png
vid_restart
wait 150
p589_status
screenshot restart.png
plug_close p589mesh
plug_load p589mesh
p589_open
p589_invalid
wait 100
p589_status
screenshot reload.png
wait 60
quit
'''


def launch(args: argparse.Namespace) -> int:
    if os.name != 'nt':
        raise RuntimeError('launch requires Windows; grading is portable')
    rig = Path(tempfile.mkdtemp(prefix='p589-mesh-',dir=ROOT/'rig'))
    fte = args.fte_root.resolve()
    env = os.environ.copy()
    env['PATH'] = str(args.cc.resolve().parent)+os.pathsep+env.get('PATH','')
    source = ROOT/'tools/fixtures/p589mesh.c'
    includes = [fte/'plugins']+[fte/'engine'/x for x in ('client','common','server','gl')]
    commands = []
    for name,flags in (('p589mesh',[]),('p589foreign',['-DFOREIGN'])):
        command = [str(args.cc.resolve()),'-std=c99','-Wall','-Wextra','-Werror','-O2','-DFTEPLUGIN',
                   '-shared','-static-libgcc']+flags+['-I'+str(p) for p in includes]+[str(source),'-o',str(rig/f'fteplug_{name}_x64.dll')]
        commands.append(command)
        with (rig/f'compile-{name}.log').open('w') as out:
            rc = subprocess.run(command,env=env,stdout=out,stderr=subprocess.STDOUT).returncode
        if rc or (rig/f'compile-{name}.log').read_text().strip():
            raise RuntimeError('fixture compile failed/warned; '+str(rig/f'compile-{name}.log'))
    report = {'utc':datetime.now(timezone.utc).isoformat(),'compile':commands,'source_sha256':sha(source),'arms':{}}
    for arm in ARMS:
        root = rig/arm
        game = root/'ftesurf'
        game.mkdir(parents=True)
        engine = args.control if arm == 'control' else args.engine
        shutil.copy2(engine,root/'ftesurf64.exe')
        shutil.copy2(rig/'fteplug_p589mesh_x64.dll',root/'fteplug_p589mesh_x64.dll')
        if arm != 'none':
            shutil.copy2(rig/'fteplug_p589foreign_x64.dll',root/'fteplug_p589foreign_x64.dll')
        (root/'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfMeshFixture\nNAME "Indexed mesh fixture"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p589-unused\n')
        (game/'probe.cfg').write_text(cfg(2 if arm == 'subject2' else 1,arm.startswith('subject'),arm == 'none'))
        command = [str(root/'ftesurf64.exe'),'-basedir',str(root),'-nohome','-nosound','-nocdaudio','-window',
                   '+set','vid_width','640','+set','vid_height','480','+set','vid_winmaximize','0',
                   '+set','vid_fullscreen','0','+set','vid_renderer','gl','+set','plug_loaddefault','2' if arm == 'none' else '0']
        if arm == 'disabled':
            command += ['-noplugins']
        command += ['+set','cfg_save_auto','0','+exec','probe.cfg']
        child_env = os.environ.copy()
        child_env['P589_NONE_MARKER'] = str(root/'none.txt')
        with (root/'launch.log').open('w') as out:
            p = subprocess.Popen(command,cwd=root,env=child_env,stdout=out,stderr=subprocess.STDOUT)
            try:
                rc = p.wait(timeout=40)
            finally:
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=5)
        report['arms'][arm] = {'exit':rc,'command':command,'engine_sha256':sha(root/'ftesurf64.exe'),
                              'cfg_sha256':sha(game/'probe.cfg')}
        (rig/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    errors = grade(rig)
    for e in errors:
        print('FAIL',e)
    print(f'{len(errors)} failed; evidence: {rig}')
    return int(bool(errors))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',nargs='?',choices=('run','grade'),default='run')
    p.add_argument('rig',nargs='?',type=Path)
    p.add_argument('--engine',type=Path,default=ROOT/'ftesurf64.exe')
    p.add_argument('--control',type=Path,default=Path('C:/FTESurf/ftesurf64.exe'))
    p.add_argument('--fte-root',type=Path,default=Path('C:/msys64/home/Lex/fteqw-ui-font'))
    p.add_argument('--cc',type=Path,default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    args = p.parse_args()
    try:
        if args.mode == 'grade':
            if args.rig is None:
                p.error('grade requires rig')
            errors = grade(args.rig)
            for e in errors: print('FAIL',e)
            print(f'{len(errors)} failed')
            return int(bool(errors))
        return launch(args)
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError) as e:
        print('CANNOT GRADE:',e)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
