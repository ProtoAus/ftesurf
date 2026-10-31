#!/usr/bin/env python3
"""Compile literal native noclip preference/velocity functions, with mocked engine context.

This is NOT a network, GUI, wire-validation, native-prediction-chain or recorder test.
Q_atof is the literal native parser, not a strtof substitute.
--baseline runs only the unchanged pre-existing WPhys_CheckVelocity function;
its noclip truncation must fail, while walking/non-Source controls still act.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def function(text, name):
    match = re.search(r'^(?:static )?(?:void|float|qboolean) ' + name + r'\s*\([^\n]*\)\s*\{', text, re.M)
    if not match:
        raise ValueError('missing literal native function: ' + name)
    start = match.start()
    depth = 1
    pos = match.end()
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    return text[start:pos] + '\n'


PRELUDE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
typedef float vec3_t[3];
typedef int qboolean;
#define MAX_SPLITS 4
#define true 1
#define false 0
#define PM_NONE 5
#define PM_FREEZE 6
#define DPB_QUAKEWORLD 1
#define DPB_MVD 2
#define IM_NONE 0
#define CAM_ISLOCKED(pv) 0
#define CSQC_PredictsHeld() 0
#define IS_NAN(x) (!isfinite(x))
#define Length(v) sqrtf((v)[0]*(v)[0]+(v)[1]*(v)[1]+(v)[2]*(v)[2])
#define VectorScale(v,s,o) do{for(int k=0;k<3;k++)(o)[k]=(v)[k]*(s);}while(0)
#define Con_DPrintf(...) ((void)0)
#define Con_Printf(...) ((void)0)
#define HAVE_SERVER 1
#define NQPM_NQ 1
#define PM_NORMAL 0
#define PM_OLD_SPECTATOR 1
#define PM_SPECTATOR 2
#define PHYSMODE_SOURCE 1
#define MOVETYPE_WALK 3
#define MOVETYPE_FLY 5
#define MOVETYPE_NOCLIP 8
struct {int physicsmode;float noclipspeed;} movevars;
struct {int pm_type;} pmove;
struct {float value;int ival;} sv_maxvelocity={3500,3500},sv_nqplayerphysics={0,0};
typedef struct {vec3_t velocity,origin;float movetype;} entvars_t;
typedef struct {entvars_t *v;} wedict_t;
typedef struct {int unused;} world_t;
typedef struct {const char *speed,*cap,*defaultspeed;} infobuf_t;
typedef struct {int spectator;wedict_t *edict;infobuf_t userinfo;} client_t;
struct {struct{int spectator;} playerview[4];infobuf_t serverinfo;int intermissionmode,paused;} cl;
struct {infobuf_t userinfo[4];int demoplayback;} cls;
static double realtime;
struct {int ival;float value;} cl_predict_players={1,1},cl_prederror={1,1};
static int cl_pred_localchain=1;
static const char *InfoBuf_ValueForKey(infobuf_t *b,const char *key) {
 if(!strcmp(key,"cl_noclipspeed"))return b->speed?b->speed:"";
 if(!strcmp(key,"pm_noclipspeed"))return b->defaultspeed?b->defaultspeed:"";
 return b->cap?b->cap:"";
}
static int bad;
#define CHECK(expr,name) do{int ok=!!(expr);printf("%s %s\n",ok?"PASS":"FAIL",name);bad+=!ok;}while(0)
static int eq(float a,float b){return fabsf(a-b)<0.01f;}
'''
VELOCITY = r'''
static void velocity_tests(void) {
 world_t w={0};entvars_t v={{3500,3500,-3500},{0,0,0},MOVETYPE_WALK};wedict_t e={&v};
 movevars.physicsmode=PHYSMODE_SOURCE;
 WPhys_CheckVelocity(&w,&e);
 CHECK(eq(v.velocity[0],3500)&&eq(v.velocity[1],3500)&&eq(v.velocity[2],-3500),"Source walking diagonal6062 stays legal");
 v.velocity[0]=8000;v.velocity[1]=-4000;v.velocity[2]=3501;
 WPhys_CheckVelocity(&w,&e);
 CHECK(eq(v.velocity[0],3500)&&eq(v.velocity[1],-3500)&&eq(v.velocity[2],3500),"Source walking each-axis3500 remains bounded");
 v.movetype=MOVETYPE_NOCLIP;v.velocity[0]=8000;v.velocity[1]=-5000;v.velocity[2]=4000;
 WPhys_CheckVelocity(&w,&e);
 CHECK(eq(v.velocity[0],8000)&&eq(v.velocity[1],-5000)&&eq(v.velocity[2],4000),"Source noclip finite speed is not truncated");
 v.velocity[0]=NAN;v.velocity[1]=INFINITY;v.velocity[2]=8000;v.origin[0]=INFINITY;
 WPhys_CheckVelocity(&w,&e);
 CHECK(v.velocity[0]==0&&v.velocity[1]==0&&v.origin[0]==0&&eq(v.velocity[2],8000),"Source noclip finite sanitation still acts");
 movevars.physicsmode=0;v.velocity[0]=8000;v.velocity[1]=v.velocity[2]=0;
 WPhys_CheckVelocity(&w,&e);
 CHECK(eq(v.velocity[0],3500),"non-Source noclip retains old velocity cap");
 v.velocity[0]=v.velocity[1]=3500;v.velocity[2]=0;
 WPhys_CheckVelocity(&w,&e);
 CHECK(v.velocity[0]>2400&&v.velocity[0]<2500&&v.velocity[1]>2800&&v.velocity[1]<2900,"non-Source retains legacy sequential radial-macro behavior");
 sv_nqplayerphysics.ival=NQPM_NQ;v.velocity[0]=v.velocity[1]=3500;v.velocity[2]=0;
 WPhys_CheckVelocity(&w,&e);
 CHECK(eq(v.velocity[0],3500)&&eq(v.velocity[1],3500),"NQ legacy per-axis branch unchanged");
}
'''
PREFERENCES = r'''
static void preference_tests(void) {
 entvars_t v={{0,0,0},{0,0,0},MOVETYPE_NOCLIP};wedict_t e={&v};
 client_t a={0,&e,{"8",NULL,NULL}},b={0,&e,{"2",NULL,NULL}};
 movevars.physicsmode=PHYSMODE_SOURCE;pmove.pm_type=PM_SPECTATOR;
 cl.serverinfo.cap="1";cl.serverinfo.defaultspeed="4";cls.userinfo[0].speed="8";cls.userinfo[1].speed="2";
 CHECK(SV_SourceNoclipSpeed(&a,4)==8&&SV_SourceNoclipSpeed(&b,4)==2,"server resolves each player's preference independently");
 CHECK(CL_SourceNoclipSpeed(0,4)==8&&CL_SourceNoclipSpeed(1,4)==2,"own local seats match authoritative preference");
 const char *invalid[]={"", "0", "-1", ".24", "16.01", "nan", "inf", "+2"};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) {
  a.userinfo.speed=cls.userinfo[0].speed=invalid[i];
  CHECK(SV_SourceNoclipSpeed(&a,4)==4&&CL_SourceNoclipSpeed(0,4)==4,"invalid/out-of-range preference uses server default");
 }
 a.userinfo.speed=cls.userinfo[0].speed=".25";
 CHECK(SV_SourceNoclipSpeed(&a,4)==.25f&&CL_SourceNoclipSpeed(0,4)==.25f,"lower bound accepted by both roles");
 a.userinfo.speed=cls.userinfo[0].speed="16";pmove.pm_type=PM_OLD_SPECTATOR;
 CHECK(SV_SourceNoclipSpeed(&a,4)==16&&CL_SourceNoclipSpeed(0,4)==16,"upper bound and old noclip prediction accepted");
 a.userinfo.speed=cls.userinfo[0].speed="8";v.movetype=MOVETYPE_WALK;pmove.pm_type=PM_NORMAL;
 CHECK(SV_SourceNoclipSpeed(&a,4)==4&&CL_SourceNoclipSpeed(0,4)==4,"walking ignores preference completely");
 v.movetype=MOVETYPE_FLY;CHECK(SV_SourceNoclipSpeed(&a,4)==4,"colliding fly mode is not noclip");
 v.movetype=MOVETYPE_NOCLIP;pmove.pm_type=PM_SPECTATOR;a.spectator=cl.playerview[0].spectator=1;
 CHECK(SV_SourceNoclipSpeed(&a,4)==4&&CL_SourceNoclipSpeed(0,4)==4,"actual spectators retain defaults");
 a.spectator=cl.playerview[0].spectator=0;movevars.physicsmode=0;
 CHECK(SV_SourceNoclipSpeed(&a,4)==4&&CL_SourceNoclipSpeed(0,4)==4,"non-Source movement retains defaults");
 movevars.physicsmode=PHYSMODE_SOURCE;cl_pred_localchain=0;
 CHECK(CL_SourceNoclipSpeed(0,4)==4,"other-player prediction cannot inherit local preference");
 cl_pred_localchain=1;cl.serverinfo.cap="";
 CHECK(CL_SourceNoclipSpeed(0,4)==4,"old server receives no speculative client override");
 a.edict=NULL;CHECK(SV_SourceNoclipSpeed(&a,4)==4,"missing server entity safely falls back");
 CHECK(SV_SourceNoclipSpeed(&b,4)==2,"companion preference still acts after all controls");
 a.edict=&e;cl.serverinfo.cap="1";cl_pred_localchain=1;
 a.userinfo.speed=cls.userinfo[0].speed="1e99";
 CHECK(Q_atof("1e99")==1&&SV_SourceNoclipSpeed(&a,4)==1&&native_speed(0,4)==1,"actual native parser accepts leading1, not exponent99");
 a.userinfo.speed=cls.userinfo[0].speed="0x8";
 CHECK(SV_SourceNoclipSpeed(&a,4)==8&&native_speed(0,4)==8,"native hex syntax remains supported without new policy");
}

'''


LIFECYCLE = r'''
static void lifecycle_tests(void) {
 movevars.physicsmode=PHYSMODE_SOURCE;movevars.noclipspeed=16;
 pmove.pm_type=PM_SPECTATOR;cl_pred_localchain=1;cls.demoplayback=0;
 cl.serverinfo.cap="1";cl.serverinfo.defaultspeed="16";cls.userinfo[0].speed="0";
 CHECK(native_speed(0,2)==16,"listen default comes from serverinfo, not companion's shared movevar2");
 pmove.pm_type=PM_NORMAL;
 CHECK(native_speed(0,2)==16,"walking capture keeps canonical server default despite shared residue");
 pmove.pm_type=PM_SPECTATOR;cls.userinfo[0].speed="17";
 CHECK(native_speed(0,2)==16,"invalid personal value falls back to real server default, not companion");
 cls.demoplayback=DPB_QUAKEWORLD;cls.userinfo[0].speed="14.55";
 CHECK(native_speed(0,16)==16,"demo prediction never consumes viewer's archived preference");
 CHECK(native_demo_nopred(PM_SPECTATOR,0)&&native_demo_nopred(PM_OLD_SPECTATOR,0),"Source personal-speed demo uses authoritative interpolation");
 CHECK(native_demo_nopred_fresh(PM_NORMAL,PM_SPECTATOR,0),"fresh demo noclip type selects snapshots even with stale walking view type");
 CHECK(!native_demo_nopred_fresh(PM_SPECTATOR,PM_NORMAL,0),"fresh walking type restores demo prediction without stale noclip policy");
 CHECK(!native_demo_nopred(PM_NORMAL,0),"ordinary demo movement retains prediction");
 CHECK(!native_demo_nopred(PM_SPECTATOR,1),"actual demo viewer's free spectator is not forced to actor interpolation");
 cl.serverinfo.cap="";
 CHECK(!native_demo_nopred(PM_SPECTATOR,0),"old-server demo policy remains unchanged");
 cl.serverinfo.cap="1";movevars.physicsmode=0;
 CHECK(!native_demo_nopred(PM_SPECTATOR,0),"non-Source demo policy remains unchanged");
 movevars.physicsmode=PHYSMODE_SOURCE;cls.demoplayback=0;
 CHECK(native_remote_extrapolation_skipped(MOVETYPE_NOCLIP)&&native_remote_extrapolation_skipped(MOVETYPE_NOCLIP|128),"other actor's personal noclip skips own-maxspeed extrapolation (not a rendered-lerp claim)");
 CHECK(!native_remote_extrapolation_skipped(MOVETYPE_WALK),"other walking entities retain ordinary prediction");
 cl.serverinfo.cap="";CHECK(!native_remote_extrapolation_skipped(MOVETYPE_NOCLIP),"old-server remote noclip retains legacy policy");
 cl.serverinfo.cap="1";cls.userinfo[0].speed=cls.userinfo[1].speed="2";
 realtime=100;CHECK(native_grace(0,PM_SPECTATOR)&&native_grace(1,PM_SPECTATOR),"both local seats establish initial noclip-speed grace");
 realtime=101;CHECK(!native_grace(0,PM_SPECTATOR)&&!native_grace(1,PM_SPECTATOR),"steady noclip leaves grace after300ms");
 cls.userinfo[0].speed="4";
 CHECK(native_grace(0,PM_SPECTATOR),"per-player preference change rearms its diagnostic grace");
 CHECK(!native_grace(1,PM_SPECTATOR),"one seat's speed change does not suppress another seat's diagnostics");
 realtime=101.4;CHECK(!native_grace(0,PM_SPECTATOR),"personal-speed grace expires after300ms");
 CHECK(!native_grace(0,PM_NORMAL),"walking diagnostic is never hidden by noclip grace");
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--baseline', type=Path, help='Retained literal pre-change sv_phys.c; velocity tests only')
    ap.add_argument('--client-source', type=Path, help='Retained reviewed cl_pred.c for lifecycle counterexamples')
    a = ap.parse_args()
    if not any((p/'OWNER.md').is_file() for p in a.out.resolve().parents):
        ap.error('--out must be under an owned task root')
    paths = {'velocity': a.baseline or a.engine/'engine/server/sv_phys.c', 'parser': a.engine/'engine/common/common.c'}
    if not a.baseline:
        paths.update(server=a.engine/'engine/server/sv_user.c', client=a.client_source or a.engine/'engine/client/cl_pred.c')
    texts = {key: path.read_text(encoding='utf-8') for key, path in paths.items()}
    code = PRELUDE + function(texts['parser'], 'Q_atof') + function(texts['velocity'], 'WPhys_CheckVelocity') + VELOCITY
    if not a.baseline:
        client = texts['client']
        resolver = function(client, 'CL_SourceNoclipSpeed')
        args = resolver.split('(',1)[1].split(')',1)[0].count(',') + 1
        call = 'CL_SourceNoclipSpeed(seat,pmove.pm_type,cl_pred_localchain,fallback)' if args == 4 else 'CL_SourceNoclipSpeed(seat,fallback)'
        adapter = 'static float native_speed(int seat,float fallback){return '+call+';}\n'
        decision = client.split('//these things also force-disable prediction',1)[1].split('// figure out the first frame',1)[0]
        decision_assignment = ''
        assignment = re.search(r'^\s*source_demo_lerp = [^;]+;',client,re.M)
        if assignment:
            decision_assignment = assignment.group(0)
        adapter += r'''
static int native_demo_nopred_fresh(int type,int fresh,int spectator) {
 struct {int pmovetype,spectator;} body={type,spectator},*pv=&body;
 int source_demo_type=fresh,nopred=0,source_demo_lerp=0;(void)source_demo_type;(void)source_demo_lerp;
'''+decision_assignment+decision+'\nreturn nopred;}\nstatic int native_demo_nopred(int type,int spectator){return native_demo_nopred_fresh(type,type,spectator);}\n'
        entity = client.split('void CL_PredictEntityMovement(',1)[1].split('float CL_GetPredictionRealtime(',1)[0]
        condition = entity.split('\n\tif (',1)[1].split('\n\t\tVectorCopy',1)[0].strip()
        assert condition.endswith(')')
        adapter += 'static int native_remote_extrapolation_skipped(int type){struct{struct{struct{int pmovetype;}q1;}u;} entity={{{0}}},*estate=&entity;float age=.1f;estate->u.q1.pmovetype=type;return ('+condition[:-1]+');}\n'
        if 'static qboolean CL_SourceNoclipSpeedGrace(' in client:
            adapter += function(client, 'CL_SourceNoclipSpeedGrace')
            adapter += 'static int native_grace(int seat,int type){return CL_SourceNoclipSpeedGrace(seat,type);}\n'
        else:
            start = client.index('static float pt_ncspeed;')
            end = client.index('if (cl_prederror.value > 0', start)
            prefix = client[start:end]
            pos = end + len('if ')
            depth, stop = 1, pos + 1
            while depth:
                depth += (client[stop] == '(') - (client[stop] == ')'); stop += 1
            condition = client[pos:stop]
            adapter += 'static int native_grace(int seat,int type){struct{int pm_type;}state={type};struct{typeof(&state)state;}from={&state};(void)seat;'+prefix+'return !'+condition+';}\n'
        policy = ''
        for name in ['CL_SourceNoclipEntityLerp', 'CL_SourceNoclipLerp']:
            if re.search(r'^qboolean '+name+r'\(',client,re.M):
                policy += function(client,name)
        code += function(texts['server'], 'SV_SourceNoclipSpeed') + policy + resolver + adapter + PREFERENCES.replace('CL_SourceNoclipSpeed(', 'native_speed(') + LIFECYCLE
    code += 'int main(void){velocity_tests();' + ('' if a.baseline else 'preference_tests();lifecycle_tests();') + 'return bad?2:0;}\n'
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
    digest = hashlib.sha256(code.encode()).hexdigest()
    a.out.mkdir(parents=True, exist_ok=True)
    src = a.out/('native-noclip-'+digest[:12]+'.c')
    src.write_text(code, encoding='utf-8')
    gcc = Path('C:/msys64/ucrt64/bin/gcc.exe')
    env = dict(os.environ, PATH=str(gcc.parent)+os.pathsep+os.environ.get('PATH',''))
    command = [str(gcc), '-O2', '-fno-strict-aliasing', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-parameter', str(src), '-o', str(src.with_suffix('.exe'))]
    compile = subprocess.run(command, capture_output=True, text=True, env=env)
    run = subprocess.run([str(src.with_suffix('.exe'))], capture_output=True, text=True, env=env) if compile.returncode == 0 else None
    receipt = dict(sources={key:str(path) for key,path in paths.items()}, sourceSha256=hashes, generatedSha256=digest,
                   scriptSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), compileExit=compile.returncode,
                   compileOutput=compile.stdout+compile.stderr, exit=run.returncode if run else None,
                   stdout=run.stdout if run else '', stderr=run.stderr if run else '',
                   limits=__doc__)
    (a.out/('receipt-'+digest[:12]+'.json')).write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(receipt['compileOutput'] if compile.returncode else receipt['stdout']+receipt['stderr'])
    raise SystemExit(3 if compile.returncode else run.returncode)


if __name__ == '__main__':
    main()
