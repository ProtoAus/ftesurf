#!/usr/bin/env python3
"""Execute literal lobby-pose producer/codec/consumer functions in native QC VM.

Runs the SSQC and CSQC function subset together on a headless native server.
The transport builtins are rebound to a bounded QC byte buffer; arrival/render
clocks and entity roles are controlled. No userinfo, real network, GPU, actual
CSQC dispatch, world movement, owner feel or fleet acceptance is claimed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def stripped(source):
    return re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:re.sub(r'[^\n]',' ',m.group()),source,flags=re.S)


def function(source,name):
    masked=stripped(source)
    m=re.search(r'^(?:void|float|entity|vector|string)\([^)]*\)\s+'+name+r'\s*=\s*\{',masked,re.M)
    if not m:raise ValueError('missing literal QC function '+name)
    pos=m.end();depth=1
    while depth:
        if masked[pos]=='{':depth+=1
        elif masked[pos]=='}':depth-=1
        pos+=1
    return source[m.start():pos]+';\n'


GLUE=r'''
float cltime;
float run_t_tick;
float pb_tk_total, pb_rx_total, pb_bf_total, pb_late_total;
float test_failed, test_count;
float wire[256];float wn,wr;
void(float ok,string label) Check = {
 test_count=test_count+1;
 if(ok)dprint(strcat("POSEVM PASS ",label,"\n"));
 else{test_failed=test_failed+1;dprint(strcat("POSEVM FAIL ",label,"\n"));}
};
void(float channel,float v) Test_WriteByte = {
 Check(wn<256,"wire bound");wire[wn]=v&255;wn=wn+1;
};
void(float channel,float v) Test_WriteChar = {Test_WriteByte(channel,v);};
void(float channel,float v) Test_WriteShort = {
 Test_WriteByte(channel,v);Test_WriteByte(channel,floor(v/256));
};
float() readbyte = {local float v;v=wire[wr];wr=wr+1;return v;};
float() readchar = {local float v;v=readbyte();if(v>=128)v=v-256;return v;};
float() readshort = {local float lo,hi,v;lo=readbyte();hi=readbyte();v=lo+256*hi;if(v>=32768)v=v-65536;return v;};
float(entity p) SV_RecKeys = {return 0;};
float(entity p) SV_TASFlags = {return 0;};
float() Body_TickRate = {return PM_TICK;};
float() Body_Predraw = {return 0;};

void(entity av,entity b,entity watcher) RoundTrip = {
 local float f;
 wn=0;wr=0;self=av;
 Pose_Send(watcher,av.SendFlags);av.SendFlags=0;
 f=readbyte();
 Check((f&PB_POSE)!=0,"actual Pose_Send emitted pose");
 if(f&PB_POSE)Body_ReadPose(b,(f&PB_SPEC)!=0,(f&PB_RUN)!=0);
 Check(wr==wn,"actual Body_ReadPose consumed exact wire bytes");
};
void(entity b,float at) DrawAt = {
 cltime=at+Body_Delay(b);b.pb_o=0;b.pb_rclk=at;pb_fdt=0;
 Body_Eval(b);
};
void(float kind,float spec) Case = {
 local entity p,av,b,w;
 local float step,rate,ser,oldtp,answer;
 local vector o,a,v;
 local float eye;
 o='0 0 0';a=o;v=o;eye=0;
 p=spawn();av=spawn();b=spawn();w=spawn();
 p.classname="player";p.lobby_av=av;av.lobby_owner=p;av.SendEntity=Pose_Send;
 p.movetype=MOVETYPE_NOCLIP;p.view_ofs='0 0 22';p.velocity='8320 0 0';
 p.pb_specn=spec;if(spec)w.pb_watch=p;
 rate=8320;step=.03;
 if(kind==2){rate=1000;step=.015;p.velocity='1000 0 0';}
 if(kind==3)p.effects=ZONE_EF_TELEPORT_BIT;
 if(kind==4){p.movetype=MOVETYPE_WALK;p.velocity='260 0 0';rate=260;}
 if(kind==5)av.pb_ser=7;
 p.run_movetick=0;cltime=0;pb_tick=.015;pb_capticks=1;pb_cv_hermite=1;pb_cv_extrap=0;
 Body_New(b);b.pb_slot=1;pb_list=b;
 oldtp=pb_ntp;Pose_Seed(av,p);RoundTrip(av,b,w);DrawAt(b,0);
 ser=av.pb_ser;
 p.run_movetick=step/.015;cltime=step;
 if(kind==1||kind==5||kind==6)SV_SetPlayerOrigin(p,'200 0 0');
 else if(kind==2)SV_SetPlayerOrigin(p,'17 0 0');
 else{setorigin(p,[rate*step,0,0]);if(kind==0)SV_SetPlayerOrigin(p,p.origin);}
 if(kind==6)pb_capticks=100;
 Pose_Capture(p);
 RoundTrip(av,b,w);
 if(kind==1||kind==2||kind==5||kind==6){
  Check(av.pb_ser!=ser&&pb_ntp==oldtp+1,"actual placement advanced existing pose serial once");
  DrawAt(b,step*.5);
  Check(fabs(b.pb_rorg_x)<.001&&!b.pb_snap,"Body_Eval holds departure before marked sample");
  answer=Body_Pose(0,o,a,eye,v);
  Check(fabs(o_x)<.001&&!(answer&BP_SNAP),"Body_Pose spectator callee retains departure before due");
  DrawAt(b,step);
  Check(fabs(b.pb_rorg_x-p.origin_x)<.001&&b.pb_snap,"Body_Eval snaps at marked sample");
  answer=Body_Pose(0,o,a,eye,v);
  Check((answer&BP_SNAP)&&fabs(o_x-p.origin_x)<.001,"Body_Pose exposes snap to existing spectator/trail consumers");
 }else{
  Check(av.pb_ser==ser&&pb_ntp==oldtp,"continuous/same-origin/reseed did not fabricate teleport");
  DrawAt(b,step*.5);
  Check(fabs(b.pb_rorg_x-rate*step*.5)<.02&&!b.pb_snap,"continuous high-speed or walking pose still interpolates");
 }
 Check(p.velocity==[rate,0,0],"spatial epoch did not change velocity");
 Body_Free(b);remove(b);remove(w);remove(av);remove(p);pb_list=world;
};
void() main = {};
void() StartFrame = {};
void() PlayerPreThink = {};
void() PlayerPostThink = {};
void() ClientKill = {};
void() ClientDisconnect = {};
void() ClientConnect = {};
void() PutClientInServer = {};
void() SetNewParms = {};
void() SetChangeParms = {};
void() worldspawn = {
 dprint("POSEVM BEGIN\n");
 Case(0,0);Case(0,1);Case(1,0);Case(1,1);Case(2,0);Case(2,1);
 Case(3,0);Case(3,1);Case(4,0);Case(5,1);Case(6,0);
 dprint(strcat("POSEVM RESULT ",ftos(test_failed)," ",ftos(test_count),"\n"));
 localcmd("quit\n");
};
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--qc',type=Path,required=True);ap.add_argument('--native-bin',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--pose-source',type=Path)
    a=ap.parse_args()
    if not any((p/'OWNER.md').is_file() for p in a.out.resolve().parents):ap.error('output needs owned task-root ancestor')
    src=a.qc/'src';paths={'defs':src/'defs/sv_defs.qc','pose':a.pose_source or src/'server/sv_pose.qc','canonicalPose':src/'server/sv_pose.qc','body':src/'client/cl_body.qc','interp':src/'shared/sh_interp.qc','placement':src/'server/sv_entities.qc'}
    texts={k:p.read_text(encoding='utf-8') for k,p in paths.items()};pose=texts['pose'];body=texts['body']
    names={'pose':['Pose_Tick','Pose_QAng','Pose_W24','Pose_Held','Pose_QFine','Pose_Mod8','Pose_KQuant','Pose_Quant','Pose_Publish','Pose_Capture','Pose_Seed','Pose_Send'],
           'body':['Body_Delay','Body_New','Body_Free','Body_Push','Body_OldestT','Body_CopyState','Body_Copy','Body_R24','Body_Clock','Body_ReadPose','Body_Extrap','Body_Eval','Body_Find','Body_Pose'],
           'interp':['Interp_Wrap','Interp_Arc','Interp_Angle','Interp_View','Interp_Smooth','Interp_Hermite','Interp_Fit'],
           'placement':['SV_SetPlayerOrigin']}
    funcs=[]
    for key,ns in names.items():
        for name in ns:
            if key=='interp' and not re.search(r'\)\s+'+name+r'\s*=',texts[key]):continue
            funcs.append(function(texts[key],name))
    # Only change the binding of the transport builtin, never its call order or
    # actual quantization/serial/sample-selection code.
    funcs=[f.replace('WriteByte(','Test_WriteByte(').replace('WriteShort(','Test_WriteShort(').replace('WriteChar(','Test_WriteChar(') for f in funcs]
    used='\n'.join(funcs)+GLUE;clean=stripped(used)
    allpaths=sorted(src.rglob('*.qc'));alltext='\n'.join(p.read_text(encoding='utf-8') for p in allpaths)
    fields={}
    for m in re.finditer(r'^\.(float|vector|entity|string)\s+([^;\n]+);',alltext,re.M):
        for name in m.group(2).split(','):fields[name.strip()]=m.group(1)
    builtin=set(re.findall(r'^\.(?:float|vector|entity|string)\s+(\w+)',texts['defs'],re.M))
    wanted=set(re.findall(r'\.([A-Za-z_]\w*)',clean));decl=[]
    for name in sorted(wanted-builtin):
        if name.endswith(('_x','_y','_z')):name=name[:-2]
        if name in builtin or any(line.endswith(' '+name+';') for line in decl):continue
        if name in fields:decl.append('.'+fields[name]+' '+name+';')
    macros={}
    for line in alltext.splitlines():
        m=re.match(r'^#define\s+(\w+)\s+(.+)',line)
        if m and re.search(r'\b'+m.group(1)+r'\b',clean):macros[m.group(1)]=line
    globals=[];seen=set()
    for text in [texts['canonicalPose'],body]:
        for m in re.finditer(r'^(float|vector|entity)\s+([^();=]+);',text,re.M):
            for name in m.group(2).split(','):
                name=name.strip()
                if name not in seen and re.search(r'\b'+re.escape(name)+r'\b',clean):
                    globals.append(m.group(1)+' '+name+';');seen.add(name)
    epoch=re.search(r'const float ZONE_EF_TELEPORT_BIT = \d+;',texts['placement']).group(0)
    prototypes=[f[:f.index('=')].rstrip()+';' for f in funcs]
    prefix='#include "'+paths['defs'].resolve().as_posix()+'"\n'+epoch+'\nconst float MASK_ENGINE = 1;\n.float() predraw;\n'+'\n'.join(macros.values())+'\n'+'\n'.join(decl+globals)+'\n'
    # Forward declarations for test-only I/O and setup. The original QC function
    # signatures are retained so QCC checks entity, vector and inout semantics.
    glueparts=GLUE.split('void(entity av,entity b,entity watcher) RoundTrip',1)
    code=prefix+'\n'.join(prototypes)+'\n'+glueparts[0]+'\n'+'\n'.join(funcs)+'\nvoid(entity av,entity b,entity watcher) RoundTrip'+glueparts[1]
    digest=hashlib.sha256(code.encode()).hexdigest();work=a.out/digest[:12];assert not work.exists(),'Immutable case already exists; inspect it instead of rerunning'
    work.mkdir(parents=True);(work/'ftesurf').mkdir();(work/'case.qc').write_text(code)
    (work/'case.src').write_text('ftesurf/qwprogs.dat\ncase.qc\n')
    env=dict(os.environ);compiler=src/'fteqcc64.exe'
    build=subprocess.run([str(compiler),'-srcfile','case.src'],cwd=work,capture_output=True,text=True,env=env)
    (work/'compile.log').write_text(build.stdout+build.stderr)
    report={'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'generatedSha256':digest,'compileExit':build.returncode,'sources':{k:str(p) for k,p in paths.items()},'sourceSha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},'limits':__doc__}
    if build.returncode:
        (work/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(build.stdout+build.stderr);return 3
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(a.qc/'tools'));import p840clock as P
    # The VM-only fixture needs one immutable map, a plugin and our program;
    # do not copy a full GUI install or invoke P.prepare without its three VMs.
    base=work/'vm';game=base/'ftesurf';(game/'maps').mkdir(parents=True);(game/'logs').mkdir()
    shutil.copy2(work/'ftesurf/qwprogs.dat',game/'qwprogs.dat')
    os.link(P.CONTENT/f'ftesurf/maps/{P.MAP}.bsp',game/f'maps/{P.MAP}.bsp')
    shutil.copy2(a.native_bin/'fteplug_hl2_x64.dll',base/'fteplug_hl2_x64.dll')
    (base/'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfPoseVMFixture\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG pose-vm-unused\n')
    log=work/'native-console.log'
    args=[str(a.native_bin/'fteqwsv64.exe'),'-nohome','-basedir',str(base),'-manifest',str(base/'default.fmf'),'-game','ftesurf','-ip','127.0.0.1','-port','27618','+set','developer','1','+set','log_developer','1','+set','sv_public','0','+set','cfg_save_auto','0','+set','con_savehistory','0','+set','log_enable','1','+set','log_dir','logs','+set','log_name','pose-vm','+plug_load','hl2','+map',P.MAP]
    P.take_lock('P1159 literal pose QC VM fixture; one headless server')
    try:
        with log.open('w') as out:
            run=subprocess.run(args,cwd=base,stdout=out,stderr=subprocess.STDOUT,timeout=40)
    finally:P.drop_lock()
    output=log.read_text(errors='replace')
    game_log=game/'logs/pose-vm.log'
    if game_log.exists():output+='\n'+game_log.read_text(errors='replace')
    result=re.search(r'POSEVM RESULT (\d+) (\d+)',output)
    report.update(nativeExit=run.returncode,nativeSha256=hashlib.sha256((a.native_bin/'fteqwsv64.exe').read_bytes()).hexdigest(),programSha256=hashlib.sha256((work/'ftesurf/qwprogs.dat').read_bytes()).hexdigest(),result=result.groups() if result else None)
    (work/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print('\n'.join(line for line in output.splitlines() if 'POSEVM' in line))
    return 0 if run.returncode==0 and result and int(result.group(1))==0 and int(result.group(2))>50 else 2


if __name__=='__main__':raise SystemExit(main())
