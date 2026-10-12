#!/usr/bin/env python3
"""Compile the actual native pre-input functions against controlled VM/mover doubles.

Requires --engine (paired checkout), --out (owned scratch directory) and its
clangdb.py-generated compile_commands.json. This proves sequencing/validation/
replay/writeback, NOT collision physics, network acceptance or deployment.
No production function is reimplemented: source slices fail closed on drift.
"""
import argparse
import json
import math
import os
import re
import pathlib
import shlex
import subprocess


def between(path, start, end):
    text = path.read_text()
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f'nonunique source anchors: {path}')
    return text.split(start, 1)[1].split(end, 1)[0]


HARNESS = r'''
#include "quakedef.h"
#include <assert.h>
#include <stdarg.h>
#include <math.h>
#undef PR_globals
#undef PR_ExecuteProgram
#define PR_globals(p,n) test_globals
#define PR_ExecuteProgram(p,f) TestExecute()

client_state_t cl;
client_static_t cls;
#ifdef HAVE_SERVER
server_t sv;
#endif
playermove_t pmove;
movevars_t movevars;
cvar_t cl_predict_qchook;
static pubprogfuncs_t fakeprogs;
static pubprogfuncs_t *csqcprogs = &fakeprogs;
static struct {
 int CSQC_PredictPlayerPreMove;
 float *predinput_apply, *predinput_origin, *predinput_velocity;
 float *predinput_onground, *predinput_pmtype, *predinput_forceduck;
 float *predinput_sequence_lo, *predinput_sequence_hi;
 float *predmove_basevel;
} csqcg;
#define PRED_BVEL_RING 256
static struct {vec3_t held; qboolean armed, used; unsigned int seq;} pred_bvring[MAX_SPLITS][PRED_BVEL_RING];
static vec3_t pred_bv_held[MAX_SPLITS];
static qboolean pred_bv_armed[MAX_SPLITS];
static float test_globals[64], apply, ground, mode, duck, org[3], vel[3], bv[3];
static int action, npre, npost, moved, invalids, transitions;
static float offsets[256], durations[256];
static int arm_after_first;
static float apply_override, invalid_value, seenmsecs[256], firstpostorigin[3];
static int invalid_field;
static float seqlo, seqhi;
static unsigned int test_sequence;
static model_t model;

void VARGS Con_DPrintf(const char *fmt, ...) {invalids++;}
static void CSQC_ChangeLocalPlayer(int seat) {assert(seat == 0);}
static void TestExecute(void) {
 float off=test_globals[OFS_PARM3]*1000;
 offsets[npre]=off;
 durations[npre]=test_globals[OFS_PARM2]*1000;
 npre++;
 assert(apply == 0); // must not retain previous VM output
 if(csqcg.predinput_sequence_lo) assert(seqlo==(test_sequence&0xffffu));
 if(csqcg.predinput_sequence_hi) assert(seqhi==(test_sequence>>16));
 seqlo=seqhi=-999; // read-only metadata writes cannot survive the next replay/piece
 if(csqcg.predinput_origin) assert(memcmp(org,pmove.origin,sizeof(org))==0);
 if(csqcg.predinput_velocity) assert(memcmp(vel,pmove.velocity,sizeof(vel))==0);
 if(csqcg.predinput_onground) assert(ground==pmove.onground);
 if(csqcg.predinput_pmtype) assert(mode==pmove.pm_type);
 if(csqcg.predinput_forceduck) assert(duck==0);
 if (action == 1 && off == 0) {
  apply=PMPI_BODY|PMPI_MODE|PMPI_CLEARCARRIER; org[0]=100; org[1]=org[2]=0;
  vel[0]=10; vel[1]=vel[2]=0; ground=0; mode=PM_NORMAL; transitions++;
 } else if (action == 2) {
  apply=PMPI_MODE|PMPI_HOLD|PMPI_CLEARCARRIER; mode=PM_NONE;
 } else if (action == 3) {
  apply=apply_override;
 } else if (action == 4) {
  apply=PMPI_BODY|PMPI_CLEARCARRIER; org[0]=INFINITY; ground=0;
 } else if (action == 5) {
  apply=PMPI_MODE|PMPI_CLEARCARRIER; mode=0.5f;
 } else if (action == 6) {
  apply=PMPI_DUCK|PMPI_CLEARCARRIER; duck=3;
 } else if (action == 7) {
  apply=PMPI_BODY|PMPI_CLEARCARRIER; ground=NAN;
 } else if (action == 8) {
  apply=PMPI_HOLD;
 } else if (action == 9) {
  if(off==0) {apply=PMPI_CLEARCARRIER;}
  else {apply=PMPI_HOLD;}
 } else if (action == 10) {
  org[0]=12345;vel[0]=9999;ground=1;mode=PM_6DOF;duck=2; // zero mask ignores even valid dirty outputs
 } else if (action == 11) {
  apply=PMPI_ALL;org[0]=100;vel[0]=10;ground=0;mode=PM_NORMAL;duck=2;
  if(invalid_field<3) org[invalid_field]=invalid_value;
  else if(invalid_field<6) vel[invalid_field-3]=invalid_value;
  else if(invalid_field==6) ground=invalid_value;
  else if(invalid_field==7) mode=invalid_value;
  else if(invalid_field==8) duck=invalid_value;
 }
}
void PM_PlayerMove(float gamespeed) {
 // Deliberately simple physics double: detects ordering and held duration.
 int i;seenmsecs[moved++]=pmove.cmd.msec;
 for(i=0;i<3;i++) pmove.origin[i]+=pmove.velocity[i]*pmove.cmd.msec*.001f*gamespeed;
}
void CSQC_PredictPlayerMove(int seat,const usercmd_t *cmd,const float *preorigin) {
 if(npost==0) VectorCopy(preorigin,firstpostorigin);
 npost++;
 if(arm_after_first && npost==1) {pred_bv_held[seat][0]=20;pred_bv_held[seat][2]=5;pred_bv_armed[seat]=true;}
 CSQC_PredictSaveBaseVel(seat,cmd->sequence);
}
'''

TESTS = r'''
static player_state_t Baseline(void) {
 player_state_t p;memset(&p,0,sizeof(p));p.pm_type=PM_NONE;
 p.velocity[0]=3;p.gravitydir[2]=-1;p.pmsrc.surfacefriction=.25f;
 p.pmsrc.ducktime=120;p.pmsrc.ducking=true;p.pmsrc.stamina=75;
 p.pmsrc.msec_carry=.003f;p.pmsrc.oldbuttons=4;p.pmsrc.rampoff=.1f;
 p.pmsrc.boardcount=7;p.pmsrc.rampcontact=1;p.pmsrc.srcladder=true;
 p.pmsrc.srcladdernormal[0]=1;p.szmaxs[2]=62;return p;
}
static void Reset(void) {
 memset(&pmove,0,sizeof(pmove));memset(pred_bvring,0,sizeof(pred_bvring));
 memset(pred_bv_held,0,sizeof(pred_bv_held));memset(pred_bv_armed,0,sizeof(pred_bv_armed));
 csqcg.CSQC_PredictPlayerPreMove=1;csqcg.predinput_apply=&apply;
 csqcg.predinput_origin=org;csqcg.predinput_velocity=vel;
 csqcg.predinput_onground=&ground;csqcg.predinput_pmtype=&mode;
 csqcg.predinput_forceduck=&duck;csqcg.predmove_basevel=bv;
 csqcg.predinput_sequence_lo=&seqlo;csqcg.predinput_sequence_hi=&seqhi;
 seqlo=seqhi=-999;test_sequence=7;
 cl_predict_qchook.ival=1;cl_pred_localchain=true;model.loadstate=MLS_LOADED;
 cl.worldmodel=&model;cl.gamespeed=1;movevars.ticrate=.015f;
 npre=npost=moved=invalids=transitions=arm_after_first=0;action=0;
 apply=12345;ground=mode=duck=-12345;org[0]=vel[0]=NAN;
 pred_bvring[0][6].used=true;pred_bvring[0][6].seq=6;
 pred_bvring[0][6].held[0]=1000; // visible cash-out control, deliberately unarmed
}
static void Run(float msec,player_state_t *from,player_state_t *to) {
 usercmd_t u;memset(&u,0,sizeof(u));u.msec=msec;u.sequence=test_sequence;
 CL_PredictUsercmd(0,1,from,to,&u);
 assert(u.msec==msec); // HOLD must never rewrite network input
}
int main(void) {
 player_state_t p,q,r;pmpreinput_t edit;playermove_t before;
 int i,j;float counts[]={0,.5f,1,50,50.5f,51,100.75f,101,255};float bad[]={-1,32,.5f,NAN,INFINITY};
 setbuf(stdout,NULL);
 Reset();p=Baseline();Run(10,&p,&q);
 assert(npre==1&&npost==1&&q.origin[0]>10&&q.pm_type==PM_NONE);
 puts("PASS no-op callback cash-out control acted");
 {
  unsigned int seqs[]={0,65535,65536,16777217u,0x80000001u,0xffffffffu};
  for(i=0;i<sizeof(seqs)/sizeof(seqs[0]);i++) {
   Reset();test_sequence=seqs[i];p=Baseline();Run(101,&p,&q);Run(101,&p,&r);
   assert(npre>2); // seeded exact words asserted in every real bridge invocation
  }
  Reset();csqcg.predinput_sequence_lo=csqcg.predinput_sequence_hi=NULL;
  p=Baseline();Run(101,&p,&q);assert(npre>2);
 }
 puts("PASS exact uint32 identity words, replay reseeding and absent-word compatibility");
 Reset();p=Baseline();cl_predict_qchook.ival=0;Run(10,&p,&q);assert(npre==0&&q.origin[0]<1);
 Reset();p=Baseline();csqcg.CSQC_PredictPlayerPreMove=0;Run(10,&p,&q);assert(npre==0&&q.origin[0]>10);
 Reset();p=Baseline();cl_pred_localchain=false;Run(10,&p,&q);assert(npre==0&&npost==0);
#ifdef HAVE_SERVER
 Reset();p=Baseline();sv.state=ss_active;Run(10,&p,&q);assert(npre==0);sv.state=ss_dead;
#endif
 puts("PASS disabled/absent/nonlocal/listen controls acted");
 Reset();p=Baseline();action=10;Run(10,&p,&q);assert(q.pm_type==p.pm_type&&q.origin[0]>10&&q.origin[0]<100);
 assert(q.pmsrc.ducking==p.pmsrc.ducking);
 puts("PASS reseeded entry payloads and dirty zero-mask outputs remain inert");
 for(j=0;j<sizeof(counts)/sizeof(counts[0]);j++) {
  Reset();p=Baseline();action=1;Run(counts[j],&p,&q);
  assert(transitions==1&&q.pm_type==PM_NORMAL&&fabsf(q.origin[0]-(100+counts[j]*.01f))<.0001f);
  assert(q.velocity[0]==10&&memcmp(&q.pmsrc,&p.pmsrc,sizeof(p.pmsrc))==0);
  assert(firstpostorigin[0]==100&&firstpostorigin[1]==0&&firstpostorigin[2]==0);
  assert(pred_bvring[0][6].held[0]==1000&&pred_bvring[0][6].used); // old history survives clear
  assert(offsets[0]==0);for(i=1;i<npre;i++) {
   assert(fabsf(offsets[i]-offsets[i-1]-durations[i-1])<.0001f);
  }
  assert(fabsf(offsets[npre-1]+durations[npre-1]-counts[j])<.0001f);
  Run(counts[j],&p,&r);assert(memcmp(q.origin,r.origin,sizeof(q.origin))==0&&q.pm_type==r.pm_type);
  assert(memcmp(q.velocity,r.velocity,sizeof(q.velocity))==0);
  assert(q.onground==r.onground&&q.jump_held==r.jump_held);
  assert(memcmp(&q.pmsrc,&r.pmsrc,sizeof(q.pmsrc))==0);
  assert(memcmp(q.gravitydir,r.gravitydir,sizeof(q.gravitydir))==0);
  assert(memcmp(q.szmins,r.szmins,sizeof(q.szmins))==0&&memcmp(q.szmaxs,r.szmaxs,sizeof(q.szmaxs))==0);
  assert(q.jump_msec==r.jump_msec&&q.waterjumptime==r.waterjumptime);
 }
 puts("PASS first-piece body/mode application, split budget, Source preservation, deterministic replay");
 Reset();p=Baseline();action=1;arm_after_first=1;Run(101,&p,&q);
 assert(q.velocity[0]>10&&q.velocity[0]<100); // fresh carrier survived; old 1000 did not
 puts("PASS clear before cash-out, no split resurrection, fresh post-trigger carrier retained");
 Reset();p=Baseline();action=2;Run(101,&p,&q);
 assert(npre==4&&npost==0&&memcmp(q.origin,p.origin,sizeof(p.origin))==0);
 for(i=0;i<moved;i++)assert(seenmsecs[i]==0);
 assert(memcmp(&q.pmsrc,&p.pmsrc,sizeof(p.pmsrc))==0);
 puts("PASS zero-duration hold suppresses post hook without mutating network input or carried state");
 Reset();p=Baseline();action=8;pred_bvring[0][6].armed=true;pred_bvring[0][6].held[2]=5;
 Run(10,&p,&q);assert(pred_bvring[0][7].used&&!pred_bvring[0][7].armed&&pred_bvring[0][7].held[2]==0);
 assert(npost==0);action=0;
 {usercmd_t u;memset(&u,0,sizeof(u));test_sequence=8;u.sequence=8;u.msec=10;CL_PredictUsercmd(0,1,&q,&r,&u);}
 assert(r.velocity[0]>1000&&r.velocity[2]==q.velocity[2]);
 Reset();p=Baseline();action=9;arm_after_first=1;Run(51,&p,&q);
 assert(pred_bvring[0][7].held[0]==20&&!pred_bvring[0][7].armed&&pred_bvring[0][7].held[2]==0);
 puts("PASS held-only and mixed-split end-state carrier commits (no stale arm/Z resurrection)");
 for(j=0;j<sizeof(bad)/sizeof(bad[0]);j++) {
  Reset();p=Baseline();action=3;apply_override=bad[j];Run(10,&p,&q);assert(invalids==1&&q.origin[0]>10);
 }
 for(action=4;action<=7;action++) { // Reset changes action, so preserve selected arm
  int selected=action;Reset();action=selected;p=Baseline();Run(10,&p,&q);
  assert(invalids==1&&q.origin[0]>10&&q.pm_type==PM_NONE);
 }
 Reset();p=Baseline();action=1;csqcg.predinput_velocity=NULL;Run(10,&p,&q);assert(invalids==1&&q.origin[0]>10);
 puts("PASS invalid masks/floats/booleans/posture/missing payload reject atomically, carrier control acted");
 for(i=0;i<9;i++) for(j=0;j<5;j++) {
  unsigned char history[sizeof(pred_bvring)],heldcopy[sizeof(pred_bv_held)],armedcopy[sizeof(pred_bv_armed)];
  usercmd_t u;float vals[]={NAN,INFINITY,-1,.5f,9};
  if(i<6&&j>1)continue;
  Reset();action=11;invalid_field=i;invalid_value=vals[j];
  if(i==6&&j==4)invalid_value=2;
  memset(&u,0,sizeof(u));u.sequence=7;u.msec=10;pmove.cmd=u;
  pmove.stamina=75;pmove.basevelocity[0]=999;pmove.ducktime=120;before=pmove;
  memcpy(history,pred_bvring,sizeof(history));memcpy(heldcopy,pred_bv_held,sizeof(heldcopy));memcpy(armedcopy,pred_bv_armed,sizeof(armedcopy));
  assert(CSQC_PredictPlayerPreMove(0,&u,0)==0&&invalids==1);
  assert(memcmp(&before,&pmove,sizeof(pmove))==0&&memcmp(history,pred_bvring,sizeof(history))==0);
  assert(memcmp(heldcopy,pred_bv_held,sizeof(heldcopy))==0&&memcmp(armedcopy,pred_bv_armed,sizeof(armedcopy))==0);
 }
 for(i=0;i<5;i++) {
  usercmd_t u;Reset();action=11;invalid_field=9;memset(&u,0,sizeof(u));u.sequence=7;u.msec=10;
  if(i==0)csqcg.predinput_origin=NULL;else if(i==1)csqcg.predinput_velocity=NULL;
  else if(i==2)csqcg.predinput_onground=NULL;else if(i==3)csqcg.predinput_pmtype=NULL;else csqcg.predinput_forceduck=NULL;
  before=pmove;assert(CSQC_PredictPlayerPreMove(0,&u,0)==0&&invalids==1&&memcmp(&before,&pmove,sizeof(pmove))==0);
  assert(!pred_bvring[0][7].used&&pred_bvring[0][6].held[0]==1000);
 }
 Reset();p=Baseline();csqcg.predinput_apply=NULL;Run(10,&p,&q);assert(npre==0&&invalids==0);
 Reset();p=Baseline();csqcprogs=NULL;Run(10,&p,&q);assert(npre==0&&invalids==0);csqcprogs=&fakeprogs;
 puts("PASS selected-payload/missing-global rejection matrix leaves mover and carrier history byte-identical");
 memset(&edit,0,sizeof(edit));memset(&pmove,0,sizeof(pmove));
 pmove.stamina=75;pmove.msec_carry=.003f;pmove.basevelocity[0]=999;pmove.ducktime=120;
 before=pmove;edit.flags=PMPI_ALL;edit.forceduck=3;assert(!PM_ApplyPreInput(&pmove,&edit));
 assert(memcmp(&before,&pmove,sizeof(pmove))==0);
 edit.forceduck=2;assert(PM_ApplyPreInput(&pmove,&edit));assert(pmove.ducked&&!pmove.ducking&&pmove.ducktime==0);
 assert(pmove.stamina==75&&pmove.msec_carry==.003f&&pmove.basevelocity[0]==0);
 edit.flags=PMPI_DUCK;edit.forceduck=1;assert(PM_ApplyPreInput(&pmove,&edit));assert(!pmove.ducked&&!pmove.ducking);
 puts("PASS native validation/finished-duck policy preserves unrelated carried fields");
 puts("PREDINPUT COMPLETE");return 0;
}
'''


def grade_runtime(text, old_engine=False):
    for marker in ('FTESurf CSQC loaded', 'prediction hook alive', 'RUNLINES COMPLETE',
                   'PREDINPUT BODY BEGIN', 'PREDINPUT HOLD BEGIN', 'PREDINPUT DISABLED BEGIN',
                   'PREDINPUT NOOP END'):
        if marker not in text:
            raise ValueError('missing acting marker: '+marker)
    for bad in ('Unknown command', 'QC VM error', 'Cannot call', 'stack overflow'):
        if bad in text:
            raise ValueError('runtime error: '+bad)
    if old_engine:
        if 'PREDINPUT mode=' in text or 'PREDINPUT PLACE' in text:
            raise ValueError('old-engine control unexpectedly ran the new hook')
        return 'PASS old engine ignored optional callback; legacy hook acted'
    disabled = text.split('PREDINPUT DISABLED BEGIN', 1)[1].split('PREDINPUT NOOP END', 1)[0]
    if 'PREDINPUT mode=' in disabled or 'PREDINPUT PLACE' in disabled:
        raise ValueError('disabled hook still acted')
    if 'cl_predtrace: 1 rendered frames' not in disabled or 'ptcols:' not in disabled:
        raise ValueError('disabled arm lacks independent native-chain heartbeat')
    fields = r'(.+?) org=(\S+ \S+ \S+) vel=(\S+ \S+ \S+) basepm=(\S+)'
    placed = {}
    noop = body = held = 0
    holdbase = {}
    for line in text.splitlines():
        point = re.search(r'PREDINPUT PLACE seq=(\S+) org=(\S+ \S+ \S+)', line)
        if point:
            placed[int(float(point[1]))] = tuple(map(float, point[2].split()))
            continue
        row = re.search(r'PREDINPUT mode=(\S+) seq=(\S+) dt=(\S+) off='+fields, line)
        if not row:
            continue
        mode, seq, dt, offset, xyz, velocity, pmtype = row.groups()
        scalars = list(map(float, (mode, seq, dt, offset, pmtype)))
        org = tuple(map(float, xyz.split()))
        vel = tuple(map(float, velocity.split()))
        if not all(math.isfinite(v) for v in [*scalars, *org, *vel]):
            raise ValueError('nonfinite native probe')
        mode, seq, dt, offset, pmtype = scalars
        if dt <= 0 or dt > .05001 or offset < 0:
            raise ValueError('bad split duration/offset')
        if mode == 0:
            noop += 1
        elif mode == 1 and offset > 0:
            point = placed.get(int(seq))
            if point and org[0] > point[0]+.1 and abs(org[2]-point[2]) < 64 and vel[0] > 900 and pmtype == 0:
                body += 1
        elif mode == 2:
            if offset == 0:
                holdbase[int(seq)] = org
            elif int(seq) in holdbase:
                if pmtype != 5 or org != holdbase[int(seq)]:
                    raise ValueError('held next-piece body/mode changed')
                held += 1
    if not noop or not body or not held:
        raise ValueError(f'unacted native probes: noop={noop} body={body} held={held}')
    # Pair the disabled silence with live callback controls on both sides.
    if 'PREDINPUT mode=0' not in text.split('PREDINPUT NOOP END', 1)[1]:
        raise ValueError('callback did not resume after disabled arm')
    return f'PASS dedicated native probes: noop={noop}, moved body pieces={body}, held pieces={held}, disabled/re-enabled acted'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path)
    ap.add_argument('--log', type=pathlib.Path, help='grade dedicated fixture log instead of compiling')
    ap.add_argument('--old-engine', action='store_true', help='acting optional-callback compatibility control')
    a = ap.parse_args()
    if a.log:
        text = a.log.read_text(errors='replace')
        print(grade_runtime(text, a.old_engine))
        if not a.old_engine:
            for marker in ('PREDINPUT mode=1', 'PREDINPUT mode=2', 'PREDINPUT DISABLED BEGIN'):
                try:
                    grade_runtime(text.replace(marker, 'REMOVED PROBE'))
                except ValueError:
                    continue
                raise ValueError('negative grader accepted missing arm: '+marker)
            print('PASS negative runtime graders reject missing body/hold/disabled arms')
        return
    if not a.engine or not a.out or a.old_engine:
        ap.error('supply --log, or both --engine and --out')
    e = a.engine / 'engine'
    a.out.mkdir(parents=True, exist_ok=True)
    code = HARNESS
    code += 'qboolean PM_ApplyPreInput' + between(e/'common/pmove.c', 'qboolean PM_ApplyPreInput', '\nvoid PM_Init')
    source = (e/'common/pm_source.c').read_text()
    for name in ('Save', 'Load'):
        start = source.index('void PMSrc_'+name+'State')
        # These two simple production functions end at the first unindented brace.
        finish = source.index('\n}', start) + 2
        code += source[start:finish] + '\n'
    code += 'int CSQC_PredictPlayerPreMove' + between(e/'client/pr_csqc.c', 'int CSQC_PredictPlayerPreMove', '\n/*FTESurf Patch 337: CSQC_PredictResetChain')
    code += 'static qboolean cl_pred_localchain;\nstatic void CL_PredictUsercmdPart' + between(e/'client/cl_pred.c', 'static void CL_PredictUsercmdPart', '\n//Used when cl_nopred is 1')
    code += TESTS
    cfile = a.out/'predinput_native_test.c'
    cfile.write_text(code)
    db = json.loads((a.engine/'compile_commands.json').read_text())
    entry = next(x for x in db if x['file'].endswith('/cl_pred.c'))
    args = entry.get('arguments') or shlex.split(entry['command'])
    args = args[:args.index('-c')]
    oi = args.index('-o')
    del args[oi:oi+2]
    env = dict(os.environ)
    env['PATH'] = str(pathlib.Path(args[0]).parent) + os.pathsep + env.get('PATH', '')
    exe = a.out/'predinput_native_test.exe'
    subprocess.run([*args, '-O0', '-Werror', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-sign-compare', str(cfile), '-o', str(exe)], cwd=entry['directory'], env=env, check=True)
    subprocess.run([str(exe)], env=env, check=True)


if __name__ == '__main__':
    main()
