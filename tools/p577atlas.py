#!/usr/bin/env python3
"""Existing plugin 2D atlas-handle falsifier. Windows launch; portable grading.

No production settings/assets are used. Native fixture is compiled from the
supplied engine's headers with -Werror. Copies run only in disposable rigs.
This is not an ImGui/indexed-mesh/QC-bridge or performance acceptance test.
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

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PHASES = ('initial', 'replacement', 'restarted', 'lifetime')
PIXELS = ((254, 0, 0), (0, 254, 0), (0, 0, 127), (127, 127, 127))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markers(text: str, kind: str) -> list[dict[str, int]]:
    rows = []
    for line in text.splitlines():
        if re.search(r'\bP577 ' + re.escape(kind) + r'\b', line):
            rows.append({key: int(value) for key, value in re.findall(r'(\w+)=(-?\d+)\b', line)})
    return rows


def grade(rig: Path) -> list[str]:
    errors = []
    report = json.loads((rig / 'report.json').read_text())
    for arm in ('control', 'subject', 'disabled'):
        game = rig / arm / 'ftesurf'
        text = (game / 'p577.log').read_text(errors='replace')
        if report['arms'][arm]['exit'] != 0:
            errors.append(arm + ': process did not exit normally')
        active = arm != 'disabled'
        statuses = markers(text, 'STATUS')
        if active:
            init = markers(text, 'INIT')
            opens = markers(text, 'OPEN')
            if len(init) != 1 or init[0].get('wrong_size_rejected') != 1:
                errors.append(arm + ': exact/wrong-size ABI witness missing')
            if len(opens) != 1 or opens[0].get('focus') != 1:
                errors.append(arm + ': menu focus witness missing')
            if len(statuses) != 4:
                errors.append(arm + ': four rendered status witnesses required')
            for i, row in enumerate(statuses):
                expected_phase = int(i != 0)
                expected_uploads = min(i + 1, 3)
                if (row.get('frames', 0) <= 0 or row.get('phase') != expected_phase
                        or row.get('uploads') != expected_uploads or row.get('video') != 1
                        or [row.get(k) for k in ('vw','vh','pw','ph')] != [640,480,640,480]):
                    errors.append(arm + ': dimensions/phase/frame/upload witness invalid')
                if arm == 'subject':
                    if row.get('atlas', 0) <= 0 or row.get('size', -1) < 0 or [row.get('w'), row.get('h')] != [2,2]:
                        errors.append(arm + ': returned atlas handle/size invalid')
                elif row.get('atlas') != 0 or row.get('size') != -1:
                    errors.append(arm + ': zero-handle control defect not reproduced')
            if len(statuses) == 4:
                if any(b.get('frames',0) <= a.get('frames',0) for a,b in zip(statuses, statuses[1:])):
                    errors.append(arm + ': rendered phases did not advance')
                if statuses[2].get('videoevents',0) <= statuses[1].get('videoevents',0):
                    errors.append(arm + ': renderer restart did not act')
            if not markers(text, 'REPLACE') or not markers(text, 'VIDEO'):
                errors.append(arm + ': replacement/restart witness missing')
            if re.search(r'Unknown command|QC runtime error|Shader double free', text, re.I):
                errors.append(arm + ': command/runtime/double-free error')
        else:
            if re.search(r'\bP577 (INIT|OPEN|STATUS|UPLOAD)\b', text):
                errors.append('disabled: unexpectedly active plugin')
            if 'Unknown command "p577_open"' not in text:
                errors.append('disabled: command-rejection control did not reach')
        for phase_index, phase in enumerate(PHASES):
            im = Image.open(game / 'screenshots' / (phase + '.png')).convert('RGB')
            if im.size != (640,480):
                errors.append(arm + '/' + phase + ': physical capture dimensions invalid')
                continue
            sentinel = im.getpixel((28,28))
            if sentinel != ((255,0,255) if active else (0,0,0)):
                errors.append(arm + '/' + phase + ': draw sentinel did not act')
            if not active:
                continue
            disk = im.crop((256,64,384,192))
            lookup = im.crop((448,64,576,192))
            returned = im.crop((64,64,192,192))
            want = PIXELS if phase_index == 0 else PIXELS[2:] + PIXELS[:2]
            for point, color in zip(((16,16),(112,16),(16,112),(112,112)), want):
                actual = disk.getpixel(point)
                if max(abs(a-b) for a,b in zip(actual, color)) > 2:
                    errors.append(arm + '/' + phase + ': disk decoder/alpha/replacement control invalid')
            if disk.tobytes() != lookup.tobytes():
                errors.append(arm + '/' + phase + ': memory upload/lookup did not match disk')
            if arm == 'subject':
                if returned.tobytes() != disk.tobytes():
                    errors.append(arm + '/' + phase + ': returned handle did not draw matching pixels')
            elif any(returned.tobytes()):
                errors.append(arm + '/' + phase + ': zero-handle control unexpectedly drew')
            if arm == 'subject' and phase == 'lifetime':
                if im.crop((64,256,192,384)).tobytes() != disk.tobytes():
                    errors.append('subject/lifetime: reloaded temporary image did not draw matching pixels')
        if arm == 'subject':
            invalid = markers(text, 'INVALID')
            if (len(invalid) != 2 or invalid[0].get('begin') != 1
                    or invalid[1] != {'end':1, 'rejected':7, 'ids':12, 'unloads':4}):
                errors.append('subject: invalid input/handle probes did not reach/pass')
            life = markers(text, 'LIFETIME')
            if (len(life) != 2 or life[0].get('temp',0) <= 0 or life[0].get('size',-1) < 0
                    or [life[0].get('w'), life[0].get('h')] != [2,2]):
                errors.append('subject: temporary loaded-handle witness missing')
            if (len(life) != 2 or life[1].get('end') != 1 or life[1].get('released_size') != -1
                    or life[1].get('released_image') != 0 or life[1].get('released_quad') != 0
                    or life[1].get('reload',0) <= 0 or life[1].get('size',-1) < 0
                    or [life[1].get('w'),life[1].get('h')] != [2,2]):
                errors.append('subject: released-slot/reload probes did not reach/pass')
    none = (rig / 'none' / 'p577-none.txt').read_text(errors='replace')
    if (report['arms']['none']['exit'] != 0 or markers(none, 'NONE') != [{'begin':1,'video':0},{'end':1,'loaded':0}]):
        errors.append('none: no-renderer valid-data rejection did not reach/pass')
    return errors


def cfg(subject: bool, none: bool = False) -> str:
    common = '''cfg_save_auto 0
cl_idlefps 0
cl_maxfps 100
sv_public 0
vid_vsync 0
vid_width 640
vid_height 480
vid_fullscreen 0
vid_winmaximize 0
vid_conautoscale 0
vid_conwidth 640
vid_conheight 480
vid_srgb 0
v_gamma 1
v_contrast 1
r_font_linear 1
con_notifytime 0
scr_conspeed 10000
show_fps 0
bgmvolume 0
log_enable 1
log_developer 1
log_readable 7
log_name p577
'''
    if none:
        return common + 'wait 60\nquit\n'
    return common + '''vid_restart
wait 60
plug_load p577atlas
wait 100
p577_open ''' + str(int(subject)) + '''
wait 100
p577_status
screenshot initial.png
wait 60
p577_replace
wait 100
p577_status
screenshot replacement.png
wait 60
vid_restart
wait 150
p577_status
screenshot restarted.png
wait 60
p577_invalid
p577_lifetime
wait 100
p577_status
screenshot lifetime.png
wait 60
quit
'''


def launch(args: argparse.Namespace) -> int:
    if os.name != 'nt':
        raise RuntimeError('launch requires Windows; grade is portable')
    fte = args.fte_root.resolve()
    subject = args.engine.resolve()
    if args.control is None:
        raise RuntimeError('run requires --control pointing to an inspected unmodified client')
    control = args.control.resolve()
    for path in (subject,control,fte/'plugins/plugin.h',fte/'engine/client/quakedef.h'):
        if not path.is_file():
            raise FileNotFoundError(path)
    rig = Path(tempfile.mkdtemp(prefix='p577-atlas-', dir=ROOT/'rig'))
    env = os.environ.copy()
    env['PATH'] = str(args.cc.resolve().parent) + os.pathsep + env.get('PATH','')
    source = ROOT/'tools/fixtures/p577atlas.c'
    includes = [fte/'plugins'] + [fte/'engine'/x for x in ('client','common','server','gl')]
    command = [str(args.cc.resolve()), '-std=c99','-Wall','-Wextra','-Werror','-O2','-DFTEPLUGIN',
               '-shared','-static-libgcc'] + ['-I'+str(p) for p in includes] + [str(source),'-o',str(rig/'fteplug_p577atlas_x64.dll')]
    with (rig/'compile.log').open('w') as out:
        result = subprocess.run(command, env=env, stdout=out, stderr=subprocess.STDOUT)
    if result.returncode or (rig/'compile.log').read_text().strip():
        raise RuntimeError('fixture compile failed/warned; see '+str(rig/'compile.log'))
    report = {'utc':datetime.now(timezone.utc).isoformat(), 'compile':command,
              'fixture_sha256':sha(source), 'dll_sha256':sha(rig/'fteplug_p577atlas_x64.dll'), 'arms':{}}
    for arm in ('control','subject','disabled','none'):
        root = rig/arm
        game = root/'ftesurf'
        (game/'textures').mkdir(parents=True)
        engine = control if arm == 'control' else subject
        shutil.copy2(engine, root/'ftesurf64.exe')
        shutil.copy2(rig/'fteplug_p577atlas_x64.dll',root/'fteplug_p577atlas_x64.dll')
        (root/'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfAtlasFixture\nNAME "Plugin atlas fixture"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG p577-unused\n')
        header = bytearray(18)
        header[2],header[12],header[14],header[16],header[17] = 2,2,2,32,0x28
        a = bytes([0,0,255,255,0,255,0,255,255,0,0,128,255,255,255,128])
        for name,data in (('a',a),('b',a[8:]+a[:8])):
            (game/'textures'/('p577_'+name+'.tga')).write_bytes(header+data)
        (game/'probe.cfg').write_text(cfg(arm != 'control',arm == 'none'))
        cmd = [str(root/'ftesurf64.exe'),'-basedir',str(root),'-nohome','-nosound','-nocdaudio']
        cmd += ['-window','+set','vid_width','640','+set','vid_height','480',
                '+set','vid_winmaximize','0','+set','vid_fullscreen','0','+set','vid_renderer','gl']
        if arm == 'none':
            cmd += ['+set','plug_loaddefault','2','+set','log_enable','1',
                    '+set','log_developer','1','+set','log_readable','7','+set','log_name','p577']
        if arm == 'disabled':
            cmd += ['-noplugins']
        cmd += ['+set','cfg_save_auto','0','+exec','probe.cfg']
        child_env = os.environ.copy()
        child_env['P577_NONE_MARKER'] = str(root/'p577-none.txt')
        with (root/'launch.log').open('w') as out:
            p = subprocess.Popen(cmd,cwd=root,env=child_env,stdout=out,stderr=subprocess.STDOUT)
            try:
                rc = p.wait(timeout=30)
            finally:
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=5)
        report['arms'][arm] = {'engine_sha256':sha(root/'ftesurf64.exe'),'exit':rc,
                               'cfg_sha256':sha(game/'probe.cfg'),'command':cmd}
        (rig/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    errors = grade(rig)
    for error in errors:
        print('FAIL',error)
    print(f'{len(errors)} failed; evidence: {rig}')
    return int(bool(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',nargs='?',choices=('run','grade'),default='run')
    parser.add_argument('rig',nargs='?',type=Path)
    parser.add_argument('--engine',type=Path,default=ROOT/'ftesurf64.exe')
    parser.add_argument('--control',type=Path,help='inspected unmodified client (required for run)')
    parser.add_argument('--fte-root',type=Path,default=Path('C:/msys64/home/Lex/fteqw-ui-font'))
    parser.add_argument('--cc',type=Path,default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    args = parser.parse_args()
    try:
        if args.mode == 'grade':
            if args.rig is None:
                parser.error('grade requires rig')
            errors = grade(args.rig)
            for error in errors:
                print('FAIL',error)
            print(f'{len(errors)} failed; evidence: {args.rig.resolve()}')
            return int(bool(errors))
        return launch(args)
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.SubprocessError) as exc:
        print('CANNOT GRADE:',exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
