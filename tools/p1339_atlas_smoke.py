#!/usr/bin/env python3
"""P1339 actual HTTPS -> CSQC binary atlas cache smoke on a real dedicated socket.
Uses only owned copied binaries/content, never the owner's game process/config.
No local rampwear assets. Public reports are aggregates; keep raw runtime state
private. --out must be below an existing task OWNER.md.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--progs',type=Path,required=True,help='actual build.ps1 -NoDeploy output directory printed by the build')
    p.add_argument('--engine',type=Path,default=Path('C:/FTESurf/ftesurf64.exe'))
    p.add_argument('--server',type=Path,default=Path('C:/FTEQuake/fteqwsv64.exe'))
    p.add_argument('--port',type=int,default=27593)
    p.add_argument('--map',default='surf_beginner')
    p.add_argument('--atlas-size',type=int,nargs=2,default=[2048,512])
    a=p.parse_args();rig=a.out.resolve()
    if not re.fullmatch(r'[a-z0-9_-]{1,64}',a.map):p.error('unsafe map name')
    for name in ['qwprogs.dat','csprogs.dat','menu.dat']:
        if not (a.progs/name).is_file():p.error('missing actual build output: '+str(a.progs/name))
    if not any((parent/'OWNER.md').is_file() for parent in rig.parents):p.error('needs existing task OWNER.md')
    if rig.exists():p.error('refusing an existing rig/evidence directory')
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:probe.bind(('127.0.0.1',a.port))
    rig.mkdir(parents=True);(rig/'OWNER.md').write_text('Owner P1339/session01a1a797 under winter-20261104T1727Z. Dedicated loopback test only, copies disposable after hash verification; unique logs/screenshots/cache/test data retained. Raw runtime state PRIVATE.\n')
    game=rig/'ftesurf';game.mkdir();(game/'logs').mkdir();(game/'downloads/csprogsvers').mkdir(parents=True)
    copies={}
    for source,target in [(a.engine,rig/'ftesurf64.exe'),(a.server,rig/'fteqwsv64.exe'),(ROOT/'default.fmf',rig/'default.fmf')]:
        shutil.copy2(source,target);copies[str(target.relative_to(rig))]={'source':str(source),'sha256':sha(target)}
    for name in ['fteplug_hl2_x64.dll','fteplug_ui_imgui_x64.dll']:
        source=a.engine.parent/name;target=rig/name;shutil.copy2(source,target);copies[name]={'source':str(source),'sha256':sha(target)}
    for folder in ['cfg','glsl','scripts','models','gfx','textures']:
        source=ROOT/'ftesurf'/folder;target=game/folder
        if source.is_dir():
            shutil.copytree(source,target,ignore=shutil.ignore_patterns('rampwear'))
            for f in target.rglob('*'):
                if f.is_file():copies[str(f.relative_to(rig))]={'source':str(source/f.relative_to(target)),'sha256':sha(f)}
    for name in ['qwprogs.dat','csprogs.dat','menu.dat']:
        shutil.copy2(a.progs/name,game/name)
    shutil.copy2(ROOT/'ftesurf/fs_addons.default.txt',game/'fs_addons.txt')
    subprocess.run([sys.executable,str(ROOT/'tools/seed_csprogs.py'),str(game/'csprogs.dat')],check=True,capture_output=True)
    assert not (game/'gfx/rampwear').exists()
    password=secrets.token_hex(16) # local fixture only; never process argv or reports
    servercfg=['cfg_save_auto 0','sv_public 0','hostname P1339-owned-loopback',
               'log_enable 1','log_dir logs','log_name p1339_server','developer 0',
               'maxclients 1','maxspectators 0','set sv_enforce_fps 0',
               'password '+password,'map '+a.map]
    (game/'p1339_server.cfg').write_text('\n'.join(servercfg)+'\n')
    cfg=['cfg_save_auto 0','cl_idlefps 0','cl_maxfps 100','vid_vsync 0','log_enable 1','log_dir logs',
         'log_name p1339_client','developer 0','set ui_bootcheck 0','set run_resume 0','set lobby_dir ""',
         'name AtlasSmoke','set rec_terms 0','set r_rampwear 0','set r_rampwear_dirt 0',
         'set r_image_downloadsizelimit 131072','password '+password,
         'waitms 1000','menu_restart','waitms 500','ui_close','connect 127.0.0.1:'+str(a.port),
         'waitms 18000','ui_close','rampwear_status','rampwear_download '+a.map,'waitms 1000',
         'echo P1339 NO-CONSENT ARM DONE','set rec_terms 8','rampwear_download '+a.map,
         'waitms 18000','rampwear_status','set r_rampwear 1','waitms 2000','screenshot p1339_atlas',
         'set r_rampwear 0','rampwear_download p1339_invalid','waitms 3000','rampwear_status',
         'r_image_downloadsizelimit','echo P1339 DOWNLOAD SMOKE DONE','disconnect','waitms 500','quit']
    (game/'p1339_client.cfg').write_text('\n'.join(cfg)+'\n')
    manifest={'copies':copies,'source_qw_sha256':sha(game/'qwprogs.dat'),'source_cs_sha256':sha(game/'csprogs.dat'),
              'native_sha256':sha(a.engine),'no_initial_rampwear':True,'port':a.port,'map':a.map,'expected_atlas_size':a.atlas_size}
    (rig/'manifest.json').write_text(json.dumps(manifest,indent=2))
    server=client=None
    try:
        with (rig/'server-launch.log').open('wb') as f:
            server=subprocess.Popen([str(rig/'fteqwsv64.exe'),'-basedir',str(rig),'-nohome','-ip','127.0.0.1','-port',str(a.port),'+exec','p1339_server.cfg'],cwd='C:/FTESurf',stdout=f,stderr=subprocess.STDOUT)
        time.sleep(4)
        if server.poll() is not None:raise RuntimeError('owned dedicated server exited; private log retained')
        with (rig/'client-launch.log').open('wb') as f:
            client=subprocess.Popen([str(rig/'ftesurf64.exe'),'-basedir',str(rig),'-nohome','-nosound','-nocdaudio','-window',
                    '+set','vid_width','1280','+set','vid_height','720','+set','vid_fullscreen','0','+set','vid_winmaximize','0',
                    '+set','cfg_save_auto','0','+exec','p1339_client.cfg'],cwd='C:/FTESurf',stdout=f,stderr=subprocess.STDOUT)
        code=client.wait(timeout=110)
    finally:
        for process in [client,server]:
            if process is not None and process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
    logs=list((game/'logs').glob('p1339_client*.log'));text=logs[0].read_text(errors='replace') if logs else ''
    checks={'client_exit0':code==0,'finished':'P1339 DOWNLOAD SMOKE DONE' in text,
            'consent_refusal_acted':'accept the online terms before downloading' in text,
            'geometry_cached':a.map+' geometry cached; atlas requested' in text,
            'binary_sha256_verified':a.map+' atlas cached and SHA256 verified' in text,
            'no_qc_error':not re.search(r'QC runtime error|CSQC_Abort|Menu_Abort',text),
            'screenshot':(game/'screenshots/p1339_atlas.png').is_file(),
            'invalid_geometry_refusal_acted':'invalid/truncated geometry; existing data kept' in text,
            'no_bad_geometry_install':not (game/'data/gfx/rampwear/p1339_invalid.net.txt').exists(),
            'geometry_loaded':any(int(n)>0 and int(t)>0 for n,t in re.findall(r'rampwear: map '+re.escape(a.map)+r' surfaces (\d+) triangles (\d+)',text)),
            'texture_loaded':bool(re.search(r'rampwear: atlas pixels '+str(a.atlas_size[0])+' '+str(a.atlas_size[1])+r' texture data/gfx/rampwear/',text)),
            'native_picture_limit_still_131072':bool(re.search(r'r_image_downloadsizelimit[^\r\n]*131072',text))}
    pngs=list((game/'data/gfx/rampwear').glob(a.map+'.*.png')) if (game/'data/gfx/rampwear').exists() else []
    checks['cached_png_filename_matches_sha256']=len(pngs)==1 and sha(pngs[0])==pngs[0].name.split('.')[1]
    checks['larger_than_native_remote_picture_limit']=len(pngs)==1 and pngs[0].stat().st_size>131072
    result={'checks':checks,'png_bytes':pngs[0].stat().st_size if len(pngs)==1 else 0,'native_image_limit_changed':False,
            'transport':'actual public HTTPS, own dedicated socket, no original local atlas',
            'human_visual_or_FPS_acceptance_NOTclaimed':True}
    (rig/'result.json').write_text(json.dumps(result,indent=2))
    for name,ok in checks.items():print(('PASS ' if ok else 'FAIL ')+name)
    return 0 if all(checks.values()) else 1


if __name__=='__main__':raise SystemExit(main())
