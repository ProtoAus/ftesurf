#!/usr/bin/env python3
"""Act real CSQC observe/input/warp fallback/queue cancellation functions in stubs.
Not native runtime, packet ordering, prediction or split-screen acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import test_practicereturn as base

CLIENT = r'''
#define RUN_TS_SEATS 4
#define WOP_RING 64
#define TR_REQUESTS 8
#define VF_ACTIVESEAT 1
#define VF_CL_VIEWANGLES 2
__MACROS__
float numclientseats=1,clientcommandframe=110,servercommandframe=100,cltime=10,input_timelength=0;
bool mine=true;float request_stat=1,scale_stat=1,seed_stat=0;
bool prediction_capability=true,prediction_ready=false;
int prediction_calls=0,ready_events=0;
float sourcepractice_predictreset(float,float seed){if(seed>0)++prediction_calls;return seed>0&&prediction_ready;}
float checkbuiltin(float(*)(float,float)){return prediction_capability;}
float run_ts_carry[4]={},run_ts_paused[4]={},run_ts_scale[4]={};
float run_ts_return[4]={},run_ts_return_sent[4]={},run_ts_return_cancelled[4]={},run_ts_return_ready[4]={};
float seqbuf[64]={},opbuf[64]={},qbuf[64]={},duckbuf[64]={},qtbuf[64]={},blindbuf[64]={};
vector orgbuf[64],velbuf[64],angbuf[64];
float *wop_seq=seqbuf,*wop_op=opbuf,*wop_q=qbuf,*wop_duck=duckbuf,*wop_qt=qtbuf,*wop_blind=blindbuf;
vector *wop_org=orgbuf,*wop_vel=velbuf,*wop_ang=angbuf;
float wop_qn=0,wop_slot=0,wop_loadseq=0,wop_loadackat=0,wop_relseq=0,wop_relat=0,wop_heldmode=0,wop_inputt=0;
vector wop_loadvel,input_angles;
float predinput_held=0,rw_on=0;
float rec_sl_holdkey=42,rec_sl_refkey=0,rec_sl_refseen=0,rec_sl_holding=1,rec_sl_holdrep=1,rec_sl_holdseen=9;
float rec_sl_holdang_ok=1,rec_sl_wophold=1,rec_sl_pv_on=1,rec_sl_holdack=1,rec_sl_holdackat=9;
std::string tr_req_cmd[8];float tr_req_raw[8]={},tr_req_head=0,tr_req_n=0,tr_req_wait=0,tr_req_dispatch=0;
int freed_bufs=0,freed_strings=0,wire_actions=0,events=0;
float LT_StatsAreMine(){return mine;}
float getproperty(int){return 0;}
float getstatf(int s){if(s==STAT_FS_TSRETURN)return request_stat;if(s==STAT_FS_TSRETURNSEED)return seed_stat;if(s==STAT_FS_TIMESCALE)return scale_stat;return 0;}
float cvar(const char*){return 1;}
std::string serverkey(const char*){return "1";}
void buf_del(float){++freed_bufs;}
void strunzone(std::string){++freed_strings;}
void print(const char*){}
void localcmd(std::string){++wire_actions;}
void SaveLoc_Cmd(std::string){++wire_actions;}
void SaveLoc_Release(){rec_sl_holding=0;++wire_actions;}
float WarpOp_Slot(){for(int i=0;i<64;++i)if(wop_seq[i]==0)return i;return -1;}
void WarpOp_Legs(){}
void dprint(std::string){}
template<class... A> std::string QC_sprintf(const char *s,A... a){char b[512];snprintf(b,sizeof(b),s,a...);return b;}
void setproperty(int,vector){}
void TimeScale_Seats(){}
void sendevent(const char*,const char*,float,float){++events;}
void sendevent(const char*,const char*,float,float,float){++ready_events;}
__FUNCTIONS__
int main(){
 int failures=0,total=0;
 auto check=[&](bool v,const char*s){++total;printf("%s %s\n",v?"PASS":"FAIL",s);if(!v)++failures;};
 auto prime=[&](){
  memset(seqbuf,0,sizeof(seqbuf));request_stat=1;numclientseats=1;mine=true;run_ts_return_cancelled[0]=run_ts_return_sent[0]=run_ts_return_ready[0]=0;
  seed_stat=0;clientcommandframe=110;prediction_capability=true;prediction_ready=false;prediction_calls=ready_events=0;
  wop_qn=wop_relseq=wop_loadseq=wop_loadackat=wop_relat=0;wire_actions=events=freed_bufs=freed_strings=0;
  rec_sl_holding=rec_sl_wophold=rec_sl_pv_on=rec_sl_holdang_ok=1;rec_sl_holdkey=42;
  tr_req_n=tr_req_wait=1;tr_req_raw[0]=7;tr_req_cmd[0]="sl_load";input_impulse=0;
 };
 prime();WarpOp_Queue(WOP_RESET,vector(),vector(),vector(),0);TimeScale_Observe();
 check(wop_seq[0]==0,"old queued reset discarded at first observed request");
 check(tr_req_n==0&&tr_req_wait==0&&freed_bufs==1&&freed_strings==1,"old deferred save/load cancelled and owned buffers released");
 check(!rec_sl_holding&&!rec_sl_wophold&&!rec_sl_pv_on&&!rec_sl_holdang_ok&&rec_sl_refkey==42,"old hold/prediction bookkeeping cancelled without reloading");
 TimeScale_ReturnInputFrame();request_stat=-1;TimeScale_Observe();WarpOp_InputFrame();
 check(input_impulse==0,"old reset cannot execute after clean completion");
 prime();WarpOp_Queue(WOP_RESET,vector(),vector(),vector(),0);wop_qt[0]=cltime-1;
 WarpOp_Frame();check(wire_actions==0&&wop_seq[0]==0,"independent frame expiry does NOT send an old reset stringcmd");
 // A new operation queued during a pending request cannot use the frame expiry.
 WarpOp_Queue(WOP_LOAD,vector(),vector(),vector(),0);wop_qt[0]=cltime-1;WarpOp_Frame();
 check(!wire_actions&&wop_seq[0]==0&&!rec_sl_holding,"pending load expiry also discarded without fallback side effects");
 // Server preparation alone is not a native-client epoch confirmation.
 prime();seed_stat=110;clientcommandframe=120;input_timelength=.01f;input_buttons=2;TimeScale_ReturnInputFrame();
 check(prediction_calls==1&&!ready_events&&input_timelength==0&&input_buttons==0,"native reset not ready: remain neutral, do NOT grant client-ready event");
 prediction_ready=true;TimeScale_ReturnInputFrame();TimeScale_ReturnInputFrame();
 check(ready_events==1&&run_ts_return_ready[0]==1,"actual native reset success sends exactly one ready event per request");
 prime();prediction_capability=false;TimeScale_ReturnInputFrame();
 check(events==0&&ready_events==0&&run_ts_return[0]==1,"old native cannot even prepare server; timeout remains practice");
 // Do not cancel a different local seat's connection-global queues.
 prime();numclientseats=2;WarpOp_Queue(WOP_RESET,vector(),vector(),vector(),0);
 TimeScale_Observe();auto oldbuttons=input_buttons=2;auto oldduration=input_timelength=0.01f;
 bool applied=TimeScale_ReturnInputFrame();
 check(wop_seq[0]==-1&&tr_req_n==1&&!applied&&input_buttons==oldbuttons&&input_timelength==oldduration,"split-screen fails closed without cancelling or masking another seat");
 printf("%d CSQC queue/fallback checks, %d failed; controlled stubs, NOT native runtime\n",total,failures);
 return failures?1:0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--client-main', type=Path)
    p.add_argument('--warp-source', type=Path)
    p.add_argument('--compiler', default='C:/msys64/ucrt64/bin/g++.exe')
    a = p.parse_args()
    if not any((x/'OWNER.md').is_file() for x in [a.out.resolve(),*a.out.resolve().parents]):
        p.error('owned task-root output required')
    a.out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    files={'main':a.client_main or root/'src/client/cl_main.qc','warp':a.warp_source or root/'src/client/cl_warpop.qc','request':root/'src/client/cl_trailrequest.qc','shared':root/'src/shared/sh_defs.qc','native':a.engine/'engine/server/pr_cmds.c','header':a.engine/'engine/common/protocol.h','return':root/'src/server/sv_practicereturn.qc'}
    text={k:f.read_text() for k,f in files.items()}
    end=text['header'].index('} pmsourcestate_t;')+len('} pmsourcestate_t;')
    carry=text['header'][text['header'].rfind('typedef struct',0,end):end]
    n=text['native'].index('static void QCBUILTIN PF_sourcepractice_reset(')
    native=text['native'][n:base.matching(text['native'],text['native'].index('{',n))+1]
    server='\n'.join(base.translate(base.body(text['return'],f)) for f in ['SV_TimeScaleReturnCancel','SV_TimeScaleReturnZone','CSEv_tsreturn_ff','CSEv_tsreturnready_fff','SV_TimeScaleReturnPlace','SV_TimeScaleReturnCommand'])
    prefix=base.STUB[:base.STUB.index('int main(){')].replace('__CARRY__',carry).replace('__NATIVE__',native).replace('__QC__',server)
    specs=[('request','Trail_RequestReset'),('warp','WarpOp_Queue')]
    if 'void() WarpOp_PracticeReturnCancel =' in text['warp']:
        specs.append(('warp','WarpOp_PracticeReturnCancel'))
    specs += [('warp','WarpOp_Frame'),('warp','WarpOp_InputFrame'),('main','TimeScale_Observe'),('main','TimeScale_ReturnInputFrame')]
    functions='\n'.join(base.translate(base.body(text[k],f)) for k,f in specs)
    functions=re.sub(r'\[(i|j|best|seat)\]',r'[(int)\1]',functions).replace('a_z','a.z').replace('sprintf(','QC_sprintf(')
    macros='\n'.join(l for l in text['shared'].splitlines() if re.match(r'#define (WOP_|STAT_FS_)',l))
    cpp=a.out/'literal-client.cpp';cpp.write_text(prefix+CLIENT.replace('__MACROS__',macros).replace('__FUNCTIONS__',functions))
    exe=a.out/'literal-client.exe';env=dict(os.environ);env['PATH']=str(Path(a.compiler).parent)+os.pathsep+env.get('PATH','')
    cmd=[a.compiler,'-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation',str(cpp),'-o',str(exe)]
    c=subprocess.run(cmd,capture_output=True,env=env);(a.out/'compile.out').write_bytes(c.stdout);(a.out/'compile.err').write_bytes(c.stderr)
    run=None
    if c.returncode==0:
        run=subprocess.run([str(exe)],capture_output=True,env=env);(a.out/'run.out').write_bytes(run.stdout);(a.out/'run.err').write_bytes(run.stderr)
    (a.out/'receipt.json').write_text(json.dumps({'scope':__doc__,'sources':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files.values()},'command':cmd,'compileExit':c.returncode,'runExit':None if run is None else run.returncode},indent=2)+'\n')
    print(c.stdout.decode(errors='replace'),c.stderr.decode(errors='replace'))
    if run:print(run.stdout.decode(errors='replace'),run.stderr.decode(errors='replace'))
    raise SystemExit(c.returncode or (run.returncode if run is not None else 1))


if __name__=='__main__':main()
