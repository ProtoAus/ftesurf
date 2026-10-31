#!/usr/bin/env python3
"""Act the exact QC clean-return handlers and native builtin in controlled stubs.

Not a native runtime, packet ordering, recorder/replay or deployment proof.
The complete native carry type is extracted unchanged from the actual header.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

STUB = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
using std::floor;
struct vector {
 float x=0,y=0,z=0;
 vector()=default; vector(float a,float b,float c):x(a),y(b),z(c){}
 vector operator+(vector v)const{return {x+v.x,y+v.y,z+v.z};}
 vector operator-(vector v)const{return {x-v.x,y-v.y,z-v.z};}
 bool operator==(vector v)const{return x==v.x&&y==v.y&&z==v.z;}
 bool operator!=(vector v)const{return !(*this==v);}
};
#define TRUE 1
#define FALSE 0
#define FL_ONGROUND 1
#define PMF_DUCKED 1
#define PRINT_HIGH 2
#define FS_MAXPLAYERS 64
#define PM_HULL_MINS vector(-16,-16,0)
#define PM_HULL_MAXS vector(16,16,72)
#define QCBUILTIN
#define PR_ANY -1
#define OFS_RETURN 0
#define OFS_PARM0 0
#define MOVETYPE_WALK 3
#define SCP_QUAKEWORLD 1
#define PEXT2_VRINPUTS 32
#define PHYSMODE_SOURCE 1
#define cs_spawned 2
using qboolean=int; using vec3_t=float[3]; using vec2_t=float[2];
float vec3_origin[3]={};
#define VectorCompare(a,b) ((a)[0]==(b)[0]&&(a)[1]==(b)[1]&&(a)[2]==(b)[2])
__CARRY__
struct V {float movetype=MOVETYPE_WALK,health=100;};
struct E {
 V nativev; V *v=&nativev;
 float run_ts_return=0,run_ts_return_uid=0,run_ts_return_zone=0,run_ts_return_after=0;
 float run_ts_return_frame=0,run_ts_return_seed=0,run_ts_return_ready=0,run_ts_return_until=0,run_ts_return_block=0;
 int run_ts_return_attempt=0,bank_attempt=1;
 float run_ts_used=1,run_timescale=1,run_inserver=1,health=100;
 float run_tas_used=0,run_tas_mode=0,run_tas_paused=0,run_tas_pending=0;
 float rec_wt_hold=0,rec_sl_hold=0,run_pmhold=0,run_t_viewowner=0,run_ms_phase=0;
 int flags=FL_ONGROUND,pmove_flags=0;
 E *groundentity=nullptr;
 float run_t_wantstage1=0;
 vector origin={10,20,0},v_angle={5,45,0},velocity={100,0,0};
 bool armed=true; int zone=2,uid=17,slot=0; float assistance=99;
};
using entity=E*; using edict_t=E;
struct eval_t {float _float=0.75f;};eval_t native_carry_mirror;
#define ev_float 2
E body,other; entity self=&body;
struct Client {Client *controller=nullptr,*controlled=nullptr;edict_t *edict; int state=cs_spawned,protocol=SCP_QUAKEWORLD;unsigned fteprotocolextensions2=0;pmsourcestate_t pmsrc;bool jump_held=true;};
Client client,otherclient; Client *host_client=&client;edict_t *sv_player=&body;
struct globalvars_s{};
struct pubprogfuncs_t {int callargc=1;eval_t *GetEdictFieldValue(pubprogfuncs_t*,edict_t*,const char*,int,void*){return &native_carry_mirror;}};pubprogfuncs_t vm;pubprogfuncs_t *svprogfuncs=&vm;
struct cvar_t {int ival=0;}; cvar_t pm_physicsmode={PHYSMODE_SOURCE},sv_nqplayerphysics;
struct {float gamespeed=1;} sv;
float input_cmd_kind=1,input_cmd_msec=8,input_cmd_piece_msec=8,input_cmd_offset_msec=0;
float input_cmd_sequence_lo=100,input_cmd_sequence_hi=0,input_buttons=0,input_impulse=0;
vector input_movevalues;
struct globalptrs_t {float *input_cmd_kind,*input_cmd_msec,*input_cmd_piece_msec,*input_cmd_offset_msec;};
globalptrs_t pointers={&input_cmd_kind,&input_cmd_msec,&input_cmd_piece_msec,&input_cmd_offset_msec};
globalptrs_t *pr_global_ptrs=&pointers;
struct {float input_buttons=0,input_impulse=0;float input_movevalues[3]={};} globals;
auto *pr_global_struct=&globals;
float native_result=0;edict_t *native_argument=&body;
#define G_FLOAT(x) native_result
#define G_EDICT(p,x) native_argument
bool replacement_mover=false;
int PR_FindFunction(pubprogfuncs_t*,const char*,int){return replacement_mover;}
__NATIVE__
float game_time=0,run_ts_return_serial=0,sv_ts_taint_uid[FS_MAXPLAYERS]={};
float trace_startsolid=0,trace_allsolid=0,trace_fraction=0;
vector trace_plane_normal={0,0,1};
entity trace_ent=&other;
bool geometry_ok=true,supported=true,busy=false,cheats=false,capability=true,placement=true;
bool force_native_failure=false;
int trace_count=0,closed=0,reset_calls=0,respawned=0,placed=0,prints=0;
int bank_serial=1;
void advance_admission(entity e){
 if(bank_serial<2147483647) e->bank_attempt=++bank_serial;
 else e->bank_attempt=-1;
}
int checks=0;
#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);return 1;}}while(0)
float SV_TimerMarkZone(entity e){return e->armed?e->zone:-1;}
float SV_MsBusy(entity){return busy;}
float SV_CheatsOn(){return cheats;}
void tracebox(vector a,vector,vector,vector b,float,entity){
 ++trace_count;trace_startsolid=!geometry_ok;trace_allsolid=0;trace_fraction=(a==b)?1:(supported?0.5f:1);trace_plane_normal={0,0,1};
}
float checkbuiltin(float(*)(entity)){return capability;}
std::string infokey(entity e,const char*){return std::to_string(e->uid);}
float QC_stof(std::string x){return std::stof(x);}
float num_for_edict(entity e){return e->slot+1;}
void sprint(entity,float,const char*){++prints;}
void SV_RecReplayStop(entity){}
void SV_SaveLocRelease(entity e){e->rec_sl_hold=0;}
void SV_TimerVoid(entity e,const char*){
 assert(e->run_ts_used);assert(reset_calls==closed);
 // The old tail closes with old carry; prepared practice closes with fresh zero.
 assert(client.pmsrc.stamina==(closed?0:77));
 ++closed;e->armed=false;advance_admission(e);
}
float sourcepractice_reset(entity e){
 ++reset_calls;assert(closed==reset_calls);assert(e->run_ts_used);
 if(force_native_failure)return 0;
 native_argument=e;globals.input_buttons=input_buttons;globals.input_impulse=input_impulse;
 globals.input_movevalues[0]=input_movevalues.x;globals.input_movevalues[1]=input_movevalues.y;globals.input_movevalues[2]=input_movevalues.z;
 PF_sourcepractice_reset(&vm,nullptr);return native_result;
}
void SV_PlayerRespawn(){assert(self->run_ts_used);++respawned;advance_admission(self);self->flags=2;self->groundentity=nullptr;self->assistance=0;self->origin={-100,0,0};self->velocity={};}
void SV_ZoneMoveAt(float z,vector at,float yaw,float pitch,float,float){
 ++placed;if(!placement)return;advance_admission(self);self->origin=at;self->v_angle={pitch,yaw,0};self->velocity={};self->zone=(int)z;self->armed=true;
}
void SV_TimeScaleRemember(entity e){sv_ts_taint_uid[e->slot]=e->uid;}
void SV_TimerCheat(entity e){assert(e->run_ts_used);}
__QC__
void initial(){
 body=E();body.v=&body.nativev;other=E();other.v=&other.nativev;self=&body;
 client=Client();client.edict=&body;otherclient=Client();otherclient.edict=&other;
 memset(&client.pmsrc,0x5a,sizeof(client.pmsrc));client.pmsrc.stamina=77;
 memset(&otherclient.pmsrc,0x33,sizeof(otherclient.pmsrc));
 host_client=&client;sv_player=&body;native_argument=&body;vm.callargc=1;
 native_result=0;native_carry_mirror._float=.75f;pm_physicsmode.ival=PHYSMODE_SOURCE;sv_nqplayerphysics.ival=0;sv.gamespeed=1;
 input_cmd_kind=1;input_cmd_msec=input_cmd_piece_msec=8;input_cmd_offset_msec=0;
 input_cmd_sequence_lo=100;input_cmd_sequence_hi=0;input_buttons=input_impulse=0;input_movevalues={};
 globals.input_buttons=globals.input_impulse=0;memset(globals.input_movevalues,0,sizeof(globals.input_movevalues));
 pr_global_ptrs=&pointers;svprogfuncs=&vm;replacement_mover=false;
 game_time=0;run_ts_return_serial=0;memset(sv_ts_taint_uid,0,sizeof(sv_ts_taint_uid));sv_ts_taint_uid[0]=17;sv_ts_taint_uid[1]=88;
 geometry_ok=supported=capability=placement=true;busy=cheats=force_native_failure=false;
 trace_count=closed=reset_calls=respawned=placed=prints=0;bank_serial=1;
}
void neutral(int seq=110){input_cmd_sequence_lo=(float)seq;input_cmd_msec=input_cmd_piece_msec=0;input_movevalues={};input_buttons=input_impulse=0;}
void ready(){SV_TimeScaleReturnCommand();CSEv_tsreturn_ff(body.run_ts_return,110);neutral();}
void prepared(){ready();SV_TimeScaleReturnCommand();}
void acknowledged(){CSEv_tsreturnready_fff(body.run_ts_return,body.run_ts_return_seed,120);neutral(120);}
int main(){
 initial();SV_TimeScaleReturnCommand();CHECK(body.run_ts_return==1&&body.run_ts_used&&closed==0);
 CSEv_tsreturn_ff(2,110);CHECK(body.run_ts_return_frame==0);
 CSEv_tsreturn_ff(1,100);CHECK(body.run_ts_return_frame==0);
 CSEv_tsreturn_ff(1,NAN);CHECK(body.run_ts_return_frame==0);
 CSEv_tsreturn_ff(1,INFINITY);CHECK(body.run_ts_return_frame==0);
 CSEv_tsreturn_ff(1,110.5f);CHECK(body.run_ts_return_frame==0);
 CSEv_tsreturn_ff(1,110);CHECK(body.run_ts_return_frame==110&&body.run_ts_used);
 CSEv_tsreturn_ff(1,115);CHECK(body.run_ts_return_frame==110);
 neutral(109);SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 neutral();input_cmd_kind=2;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 input_cmd_kind=1;input_cmd_offset_msec=1;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 input_cmd_offset_msec=0;input_cmd_msec=1;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 input_cmd_msec=0;input_buttons=2;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 input_buttons=0;input_impulse=1;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 input_impulse=0;input_movevalues={1,0,0};SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!reset_calls);
 input_movevalues={};vector old=body.origin,aim=body.v_angle;auto peer=otherclient.pmsrc;
 body.run_t_wantstage1=1;SV_TimeScaleReturnCommand();
 CHECK(body.run_ts_used&&body.run_ts_return==1&&body.run_ts_return_seed==110&&!body.run_ts_return_ready&&closed==1&&reset_calls==1);
 CHECK(sv_ts_taint_uid[0]==17&&body.run_ts_return_attempt==body.bank_attempt);
 CHECK((body.flags&FL_ONGROUND)&&body.groundentity==trace_ent);
 neutral(120);SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&reset_calls==1);
 CSEv_tsreturnready_fff(2,110,120);CSEv_tsreturnready_fff(1,109,120);CSEv_tsreturnready_fff(1,110,110);
 CSEv_tsreturnready_fff(1,110,NAN);CHECK(!body.run_ts_return_ready&&body.run_ts_used);
 CSEv_tsreturnready_fff(1,110,120);neutral(119);SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&reset_calls==1);
 neutral(120);SV_TimeScaleReturnCommand();
 CHECK(!body.run_ts_used&&body.run_ts_return==-1&&closed==2&&reset_calls==2&&respawned==2&&placed==2);
 CHECK(body.origin==old&&body.v_angle==aim&&body.velocity==vector()&&body.assistance==0&&body.armed&&body.run_t_wantstage1==1);
 CHECK((body.flags&FL_ONGROUND)&&body.groundentity==trace_ent);
 pmsourcestate_t zero={};CHECK(!memcmp(&client.pmsrc,&zero,sizeof(zero))&&!client.jump_held&&native_carry_mirror._float==0);
 CHECK(!memcmp(&peer,&otherclient.pmsrc,sizeof(peer))&&sv_ts_taint_uid[1]==88&&sv_ts_taint_uid[0]==0);
 SV_TimeScaleReturnCommand();CHECK(reset_calls==2&&body.run_ts_return==-1);
 // Each refusal is an acting state guard, not just an identifier search.
 for(int k=0;k<14;++k){initial();
  if(k==0)body.run_timescale=.5f;if(k==1)body.run_tas_used=1;if(k==2)body.run_tas_mode=1;
  if(k==3)body.rec_wt_hold=1;if(k==4)body.run_t_viewowner=1;if(k==5)body.run_ms_phase=1;
  if(k==6)busy=true;if(k==7)cheats=true;if(k==8)body.flags=0;if(k==9)body.pmove_flags=PMF_DUCKED;
  if(k==10)geometry_ok=false;if(k==11)supported=false;if(k==12)capability=false;if(k==13)body.armed=false;
  SV_TimeScaleReturnCommand();CHECK(body.run_ts_return==0&&body.run_ts_used&&!reset_calls);
 }
 initial();ready();game_time=6;input_cmd_kind=2;SV_TimeScaleReturnCommand();CHECK(body.run_ts_return==0&&body.run_ts_return_block&&body.run_ts_used&&!reset_calls);
 SV_TimeScaleReturnCommand();CHECK(body.run_ts_return==0&&!reset_calls);
 initial();ready();body.uid=18;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return==0&&!reset_calls);
 initial();ready();body.zone=3;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return==0&&!reset_calls);
 initial();ready();body.run_tas_used=1;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return==0&&!reset_calls);
 initial();ready();++body.bank_attempt;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return==0&&!reset_calls);
 initial();SV_TimeScaleReturnCommand();++body.bank_attempt;CSEv_tsreturn_ff(body.run_ts_return,110);CHECK(body.run_ts_return_frame==0&&body.run_ts_used);
 initial();ready();body.rec_sl_hold=1;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&!body.rec_sl_hold&&!reset_calls);
 initial();ready();force_native_failure=true;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return_block&&closed==1&&!respawned);
 initial();ready();placement=false;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return_block&&sv_ts_taint_uid[0]==17);
 // Admission can exhaust in ANY lifecycle phase AFTER a valid request.
 // These lifecycle stubs now really advance identities instead of leaving one fixed.
 for(int k=0;k<3;++k){initial();ready();bank_serial=2147483647-k;SV_TimeScaleReturnCommand();
  CHECK(body.bank_attempt<0&&body.run_ts_used&&body.run_ts_return==0&&body.run_ts_return_block&&sv_ts_taint_uid[0]==17);
 }
 initial();ready();bank_serial=2147483644;SV_TimeScaleReturnCommand();
 CHECK(body.bank_attempt==2147483647&&body.run_ts_used&&body.run_ts_return_seed==110&&!body.run_ts_return_block);
 for(int k=0;k<3;++k){initial();prepared();acknowledged();bank_serial=2147483647-k;SV_TimeScaleReturnCommand();
  CHECK(body.bank_attempt<0&&body.run_ts_used&&body.run_ts_return==0&&body.run_ts_return_block&&sv_ts_taint_uid[0]==17);
 }
 initial();prepared();game_time=6;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return==0&&body.run_ts_return_block&&reset_calls==1);
 initial();prepared();++body.bank_attempt;CSEv_tsreturnready_fff(1,110,120);CHECK(!body.run_ts_return_ready);SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return==0);
 initial();prepared();acknowledged();placement=false;SV_TimeScaleReturnCommand();CHECK(body.run_ts_used&&body.run_ts_return_block&&sv_ts_taint_uid[0]==17);
 // Actual native builtin: malformed/foreign/nondecoded/unsupported contexts do NOT mutate carry.
 for(int k=0;k<19;++k){initial();neutral();auto before=client.pmsrc;
  if(k==0)native_argument=&other;if(k==1)sv_player=&other;if(k==2)client.state=0;
  if(k==3)client.protocol=0;if(k==4)client.fteprotocolextensions2=PEXT2_VRINPUTS;
  if(k==5)sv_nqplayerphysics.ival=1;if(k==6)pm_physicsmode.ival=0;if(k==7)sv.gamespeed=.5f;
  if(k==8)replacement_mover=true;if(k==9)input_cmd_kind=2;if(k==10)input_cmd_msec=8;
  if(k==11)input_cmd_piece_msec=1;if(k==12)input_cmd_offset_msec=1;
  if(k==13)globals.input_buttons=2;if(k==14)globals.input_impulse=1;
  if(k==15)globals.input_movevalues[0]=1;if(k==16)body.nativev.health=NAN;
  if(k==17)client.controller=&otherclient;if(k==18)client.controlled=&otherclient;
  PF_sourcepractice_reset(&vm,nullptr);CHECK(native_result==0&&!memcmp(&before,&client.pmsrc,sizeof(before))&&client.jump_held&&native_carry_mirror._float==.75f);
 }
 printf("PASS %d literal QC/native acting checks; controlled geometry/lifecycle stubs, NOT native runtime/record replay\n",checks);
}
'''


def body(text, name):
    start = re.search(r'\b(?:void|float)\([^\n]*\) ' + re.escape(name) + r'\s*=\s*\{', text)
    if not start:
        raise ValueError(f'Missing literal QC function {name}')
    brace = text.index('{', start.start())
    return text[start.start():matching(text, brace)+2]


def matching(text, brace):
    # These bounded functions contain no braces in string literals.
    depth = 1
    for i in range(brace+1, len(text)):
        depth += (text[i] == '{') - (text[i] == '}')
        if not depth:
            return i
    raise ValueError('Unbalanced source')


def translate(src):
    src = re.sub(r'\b(void|float)\(([^\n]*)\) (\w+)\s*=', lambda m: f'{m[1]} {m[3]}({m[2]})', src)
    src = src.replace('local ', '').replace('0i', '0')
    src = re.sub(r'\b(e|self)\.', r'\1->', src)
    src = src.replace('trace_plane_normal_z', 'trace_plane_normal.z').replace('aim_y', 'aim.y').replace('aim_x', 'aim.x')
    src = src.replace("'0 0 0'", 'vector()').replace("'0 0 1'", 'vector(0,0,1)').replace("'0 0 2'", 'vector(0,0,2)')
    src = re.sub(r'\btime\b', 'game_time', src)
    src = src.replace('stof(', 'QC_stof(').replace('sv_ts_taint_uid[slot]', 'sv_ts_taint_uid[(int)slot]')
    return src


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--qc-file', type=Path, help='explicit retained predecessor QC for an acting counterexample, never a pass substitution')
    p.add_argument('--native-file', type=Path, help='explicit retained predecessor native source for an acting counterexample')
    p.add_argument('--compiler', default='C:/msys64/ucrt64/bin/g++.exe')
    p.add_argument('--continue-failed', action='store_true', help='retain the original failed receipt/raw files and continue the SAME acting test')
    a = p.parse_args()
    if not any((x/'OWNER.md').is_file() for x in [a.out.resolve(), *a.out.resolve().parents]):
        p.error('--out requires an owned task-root ancestor')
    previous = None
    if a.out.exists():
        receipt = a.out/'receipt.json'
        if not a.continue_failed or not receipt.is_file():
            p.error('existing output requires an explicit failed receipt continuation')
        previous = json.loads(receipt.read_text())
        if previous['compileExit'] == 0 and previous['runExit'] == 0:
            p.error('cannot replace a passed transaction')
    else:
        if a.continue_failed:
            p.error('no failed transaction to continue')
        a.out.mkdir(parents=True)
    qc = a.qc_file or Path(__file__).resolve().parents[1]/'src/server/sv_practicereturn.qc'
    native = a.native_file or a.engine/'engine/server/pr_cmds.c'
    header = a.engine/'engine/common/protocol.h'
    qt, nt, ht = qc.read_text(), native.read_text(), header.read_text()
    end = ht.index('} pmsourcestate_t;') + len('} pmsourcestate_t;')
    carry = ht[ht.rfind('typedef struct', 0, end):end]
    start = nt.index('static void QCBUILTIN PF_sourcepractice_reset(')
    literal = nt[start:matching(nt, nt.index('{', start))+1]
    funcs = '\n'.join(translate(body(qt, n)) for n in ['SV_TimeScaleReturnCancel', 'SV_TimeScaleReturnSupport', 'SV_TimeScaleReturnZone', 'CSEv_tsreturn_ff', 'CSEv_tsreturnready_fff', 'SV_TimeScaleReturnPlace', 'SV_TimeScaleReturnCommand'])
    source = STUB.replace('__CARRY__', carry).replace('__NATIVE__', literal).replace('__QC__', funcs)
    cpp = a.out/'literal-return.cpp'
    retained = None
    if previous is not None:
        old = cpp.read_text()
        if old[old.index('int main(){'):] != source[source.index('int main(){'):]:
            p.error('acting controls changed; cannot continue this failed transaction')
        retained = a.out/('retained-'+hashlib.sha256((a.out/'receipt.json').read_bytes()).hexdigest()[:16])
        retained.mkdir(exist_ok=False)
        for leaf in ['receipt.json','literal-return.cpp','compile.out','compile.err','run.out','run.err']:
            if (a.out/leaf).is_file():
                shutil.copy2(a.out/leaf, retained/leaf)
    cpp.write_text(source)
    exe = a.out/'literal-return.exe'
    cmd = [a.compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-misleading-indentation', str(cpp), '-o', str(exe)]
    env = dict(os.environ)
    env['PATH'] = str(Path(a.compiler).parent)+os.pathsep+env.get('PATH', '')
    c = subprocess.run(cmd, capture_output=True, env=env)
    (a.out/'compile.out').write_bytes(c.stdout)
    (a.out/'compile.err').write_bytes(c.stderr)
    result = None
    if c.returncode == 0:
        result = subprocess.run([str(exe)], capture_output=True, env=env)
        (a.out/'run.out').write_bytes(result.stdout)
        (a.out/'run.err').write_bytes(result.stderr)
    report = {'scope': __doc__, 'retainedFailedReceipt': None if retained is None else str(retained/'receipt.json'), 'sources': {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in [qc,native,header]}, 'command':cmd, 'compileExit':c.returncode, 'runExit':None if result is None else result.returncode}
    (a.out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(c.stdout.decode(errors='replace'),c.stderr.decode(errors='replace'))
    if result:
        print(result.stdout.decode(errors='replace'),result.stderr.decode(errors='replace'))
    raise SystemExit(c.returncode or (result.returncode if result is not None else 1))


if __name__ == '__main__':
    main()
