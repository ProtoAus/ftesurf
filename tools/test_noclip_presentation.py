#!/usr/bin/env python3
"""Literal noclip presentation producers AND final consumers, controlled engine context.

Compiles actual replacement-entity transition, frame chooser, classic-player
transition/setup and renderer-selection block, packet-to-player decoder, demo
fresh-type acquisition/decision and final demo position/velocity interpolation.
Math macros/Length are native. Rendering, physics replay, network parsing,
animations, actual clock/packet arrivals and live screenshots are NOT qualified.
Native byte effects serializer/parser are literal; QC placement statements have
entity/vector syntax adapted to a controlled C context, not executed in QC VM.
--pred-source/--ents-source retain a reviewed literal pre-repair counterexample.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def function(source, name):
    masked = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: re.sub(r'[^\n]', ' ', m.group()), source, flags=re.S)
    m = re.search(r'^(?:static )?(?:void|int|float|vec_t|qboolean)\s+'+name+r'\s*\([^;{}]*?\)\s*\{', masked, re.M)
    if not m:
        raise ValueError('missing native function '+name)
    pos, depth = m.end(), 1
    while depth:
        depth += (masked[pos] == '{')-(masked[pos] == '}')
        pos += 1
    return source[m.start():pos]+'\n'


def block(source, marker):
    start=source.index(marker);pos=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[pos]=='{')-(source[pos]=='}');pos+=1
    return source[start:pos]


def placement_census(server, overrides):
    """All raw QC origin writes, not a grep-absence claim about two producers.
    Remaining non-helper calls are named no-op relinks, non-player visual/prop
    updates, or the existing one-unit physical push lift (not a teleport).
    """
    allowed={
        ('sv_entities.qc','setorigin(p, org);'):'sole shared player placement primitive',
        ('sv_entities.qc','setorigin(e, e.origin);'):'unchanged-origin relink',
        ('sv_entities.qc','setorigin(t, t.origin);'):'unchanged-origin relink',
        ('sv_entities.qc','setorigin(self, self.origin);'):'unchanged-origin relink',
        ('sv_entities.qc','setorigin(door, door.origin);'):'unchanged-origin relink',
        ('sv_entities.qc',"setorigin(other, other.origin + '0 0 1');"):'existing physical trigger_push ground lift, not teleport',
        ('sv_entities.qc','setorigin(e, p.vbsp_rb_org + [d_x * c - d_y * s, d_x * s + d_y * c, d_z]);'):'rigid prop pose',
        ('sv_entities.qc','setorigin(e, e.vbsp_sp_o0);'):'spring prop pose',
        ('sv_entities.qc','setorigin(e, o);'):'spring prop pose',
        ('sv_lobby.qc','setorigin(av, p.origin);'):'visual lobby avatar, not player',
        ('sv_player.qc','setorigin(self, self.origin);'):'unchanged-origin spectator relink',
        ('sv_saveloc.qc','setorigin(e.rec_vw_eye, org);'):'replay eye proxy, not player',
    }
    result=[]
    for path in sorted(server.glob('*.qc')):
        raw=overrides.get(path.name,path).read_text()
        masked=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:re.sub(r'[^\n]',' ',m.group()),raw,flags=re.S)
        funcs=list(re.finditer(r'^(?:void|float|vector|entity|string)\([^)]*\)\s+(\w+)\s*=\s*\{',masked,re.M))
        for m in re.finditer(r'\bsetorigin\s*\([^;]+;',masked):
            call=' '.join(raw[m.start():m.end()].split());fn=next((f.group(1) for f in reversed(funcs) if f.start()<m.start()),'?')
            result.append({'file':path.name,'line':raw.count('\n',0,m.start())+1,'function':fn,'call':call,'disposition':allowed.get((path.name,call),'UNCLASSIFIED')})
        for m in re.finditer(r'\.origin(?:_[xyz])?\s*=(?!=)',masked):
            if masked[max(0,m.start()-4):m.start()+1]=='mark.':continue
            result.append({'file':path.name,'line':raw.count('\n',0,m.start())+1,'call':raw[m.start():m.start()+60],'disposition':'UNCLASSIFIED direct origin assignment'})
    return result


PREFIX = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
typedef int qboolean;
typedef float vec_t;
typedef float vec3_t[3];
typedef struct {float value;int ival;} cvar_t;
#define true 1
#define false 0
#define UPDATE_MASK 7
#define MAX_PRECACHE_MODELS 4
#define CP_QUAKEWORLD 1
#define CP_NETQUAKE 2
#define DPB_QUAKEWORLD 1
#define DPB_MVD 2
#define IM_NONE 0
#define CAM_EYECAM 1
#define CAM_WALLCAM 2
#define CAM_ISLOCKED(pv) ((pv)->cam_state==CAM_EYECAM || (pv)->cam_state==CAM_WALLCAM)
#define CSQC_PredictsHeld() 0
#define PHYSMODE_SOURCE 1
#define Z_EXT_PM_TYPE_NEW 1
#define PF_INWATER 1
#define RENDER_STEP 1
#define MLS_LOADED 1
#define SHORT2ANGLE(x) ((x)*(360.0f/65536.0f))
typedef struct{int msec,angles[3];} usercmd_t;
typedef struct {int pm_type,modelindex,effects,messagenum,flags,onground,jump_held;
 vec3_t origin,velocity,predorigin,viewangles,gravitydir,szmins,szmaxs;
 double state_time;usercmd_t command;struct{vec3_t portaloffset;}pmsrc;} player_state_t;
typedef struct {int number,sequence,modelindex,effects,frame,baseframe,basebone,dpflags,bonecount,boneoffset,solidsize;
 float lerpend;vec3_t origin,angles;
 struct{struct{unsigned pmovetype;int velocity[3],vangle[3],gravitydir[2],msec;vec3_t predorg;}q1;}u;} entity_state_t;
typedef struct {int sequence,newsequence,isnew;entity_state_t *entstate;
 vec3_t origin,lastorigin,oldorigin,neworigin,angles,oldangle,newangle;
 float orglerpdeltatime,orglerpstarttime;} lerpents_t;
typedef struct {int num_entities,fixangles[2];entity_state_t *entities;double servertime;
 vec3_t punchangle[2],punchorigin[2];} packet_entities_t;
typedef struct {packet_entities_t packet_entities;player_state_t playerstate[4];int frameid,invalid,ackframe;} inframe_t;
typedef struct{int loadstate,type;}model_t;
#define mod_alias 1
static cvar_t r_meshpitch={1,1},r_meshroll={1,1};
typedef struct {int pmovetype,spectator,nolocalplayer,playernum,cam_state;
 float crouch;vec3_t simorg,simvel,simangles,viewangles,portaloffset,punchangle_sv,punchorigin;
 struct{int sequence;vec3_t velocity;}prop;} playerview_t;
typedef struct {const char *cap;} infobuf_t;
static struct {int physicsmode,sourceversion;float ticrate;}movevars;
static struct {int numphysent;}pmove;
static struct {int protocol,demoplayback,fteprotocolextensions2,z_ext;float latency;
 struct{int incoming_sequence,outgoing_sequence;}netchan;}cls;
typedef struct{double senttime;int cmd_sequence;usercmd_t cmd[2];}outframe_t;
typedef struct predicted_player{int active,flags;vec3_t origin;}predicted_player;
static struct {inframe_t inframes[8];int maxlerpents,lerpentssequence,do_lerp_players,validsequence,ackedmovesequence,parsecount,allocated_client_slots,splitclients,demonudge,paused,intermissionmode;
 lerpents_t *lerpents,lerpplayers[4];packet_entities_t *currentpackentities,*previouspackentities;
 double currentpacktime,servertime;float packfrac;outframe_t outframes[8];
 playerview_t playerview[2];infobuf_t serverinfo;model_t *worldmodel;}cl;
static predicted_player predicted_players[4];
static cvar_t cl_lerp_maxdistance={200,200},cl_lerp_maxinterval={.1f,0},r_nolerp={0,0},cl_predict_players={1,1},cl_predict_players_latency={1,1},cl_predict_players_nudge={0,0},cl_predict_players_frac={.9f,0},cl_nopred={0,0},cl_demospeed={1,1},cl_predict_freshtype={0,0},cl_predict_velblend={2,2};
static double realtime=10.09;
static int predict_calls,entity_predict_calls,bad;
static const char *InfoBuf_ValueForKey(infobuf_t *b,const char *key){(void)key;return b->cap?b->cap:"";}
#define CHECK(x,label) do{int yes=!!(x);printf("%s %s\n",yes?"PASS":"FAIL",label);bad+=!yes;}while(0)
#define CL_UpdateNetFrameLerpState(...) ((void)0)
#define CL_UpdateBoneControls(...) ((void)0)
#define CL_UpdateAnimRate(...) ((void)0)
#define BZ_Realloc realloc
static float CompareAngles(const vec3_t a,const vec3_t b){(void)a;(void)b;return 1;}
static int CL_MayLerp(void){return !r_nolerp.ival;}
static void CL_SetSolidEntities(void){}
static void CL_SetSolidPlayers(void){}
static void AngleVectors(const vec3_t a,vec3_t f,vec3_t r,vec3_t u){(void)a;(void)f;(void)r;(void)u;}
static void CL_DecodeStateSize(unsigned solid,int model,vec3_t mins,vec3_t maxs){(void)solid;(void)model;VectorClear(mins);VectorClear(maxs);}
static void CL_PredictUsercmd(int seat,int ent,player_state_t *from,player_state_t *to,usercmd_t *cmd){
 (void)seat;(void)ent;(void)cmd;*to=*from;to->origin[0]+=999;predict_calls++;
}
static void CL_PredictEntityMovement(entity_state_t *s,float age){(void)age;VectorCopy(s->origin,s->u.q1.predorg);s->u.q1.predorg[0]+=999;entity_predict_calls++;}
static float LerpAngles16(float a,float b,float f){return a+f*(b-a);}
static float LerpAngles360(float a,float b,float f){return a+f*(b-a);}
typedef unsigned char qbyte;
typedef struct{qbyte data[16];unsigned cursize,currentbit;int packing;}sizebuf_t;
#define SZ_RAWBYTES 0
static sizebuf_t wire,*msg_readmsg=&wire;static int msg_badread;
static void *SZ_GetSpace(sizebuf_t *sb,int n){void *out=sb->data+sb->cursize;if(sb->cursize+n>16)abort();sb->cursize+=n;return out;}
static int MSG_ReadBits(int bits){(void)bits;abort();}
typedef struct{vec3_t origin;int effects,flags;}qc_edict;
typedef qc_edict *entity;
typedef struct{vec3_t velocity;}edictvars_t;
typedef struct{edictvars_t *v;}edict_t;
typedef struct{unsigned fteprotocolextensions2;}client_t;
static float acquired_velocity=8320;
#define FL_ONGROUND 512
static float cvar(const char *key){(void)key;return 0;}
static void SV_TimerWarped(entity p){(void)p;}
static void setorigin(entity p,const vec3_t org){VectorCopy(org,p->origin);}
'''
TESTS = r'''
static lerpents_t lerps[8];static entity_state_t entities[8][4];static model_t world={MLS_LOADED,0};
static void setup(int replacement,int type) {
 memset(&cl,0,sizeof(cl));memset(&cls,0,sizeof(cls));memset(lerps,0,sizeof(lerps));memset(entities,0,sizeof(entities));
 movevars.physicsmode=PHYSMODE_SOURCE;movevars.sourceversion=4;movevars.ticrate=.015f;
 cl.serverinfo.cap="1";cl.maxlerpents=8;cl.lerpents=lerps;cl.allocated_client_slots=2;cl.splitclients=1;
 cl.playerview[0].playernum=0;cl.worldmodel=&world;pmove.numphysent=1;cl.do_lerp_players=0;cl_predict_players.ival=1;r_nolerp.ival=0;
 cls.protocol=CP_QUAKEWORLD;cls.z_ext=Z_EXT_PM_TYPE_NEW;cls.fteprotocolextensions2=replacement?PEXT2_REPLACEMENTDELTAS:0;
 for(int seq=129;seq<=131;seq++) {
  inframe_t *f=&cl.inframes[seq&UPDATE_MASK];f->frameid=seq;f->packet_entities.servertime=10+(seq-129)*.03;
  f->packet_entities.entities=entities[seq&UPDATE_MASK];f->packet_entities.num_entities=replacement;
  entity_state_t *s=&entities[seq&UPDATE_MASK][0];s->number=2;s->sequence=seq;s->modelindex=1;s->u.q1.pmovetype=type;
  s->origin[0]=(seq-129)*249.6f;s->u.q1.velocity[0]=8320*8;
  player_state_t *p=&f->playerstate[1];p->messagenum=seq;p->modelindex=1;p->pm_type=type==MOVETYPE_NOCLIP?PM_SPECTATOR:PM_NORMAL;
  p->origin[0]=s->origin[0];p->predorigin[0]=p->origin[0]+999;p->velocity[0]=8320;p->state_time=f->packet_entities.servertime;
 }
 cl.parsecount=cl.validsequence=cls.netchan.incoming_sequence=129;cl.servertime=10;
 CL_TransitionEntities();
 cl.parsecount=cl.validsequence=cls.netchan.incoming_sequence=131;
 predict_calls=entity_predict_calls=0;
}
static void packet_tests(void) {
 setup(1,MOVETYPE_NOCLIP);cl.servertime=10.01;CL_TransitionEntities();cl.servertime=10.015;CL_TransitionEntities();
 CHECK(cl.lerpents[2].origin[0]>1&&cl.lerpents[2].origin[0]<248.6f&&entity_predict_calls==0,"actual replacement renderer interpolates raw fast noclip at default player policy0");
 setup(1,MOVETYPE_WALK);cl.servertime=10.01;CL_TransitionEntities();cl.servertime=10.015;CL_TransitionEntities();
 printf("OBS walking replacement predict_calls=%d rendered=%g\n",entity_predict_calls,cl.lerpents[2].origin[0]);
 CHECK(entity_predict_calls>0&&cl.lerpents[2].origin[0]>999,"ordinary walking retains default extrapolator consumer");
 setup(1,MOVETYPE_NOCLIP);entities[130&UPDATE_MASK][0].effects=EF_TELEPORT_BIT;cl.servertime=10.01;CL_TransitionEntities();cl.servertime=10.015;CL_TransitionEntities();
 CHECK(fabsf(cl.lerpents[2].origin[0]-249.6f)<.1f,"replacement explicit teleport still snaps");
 setup(1,MOVETYPE_NOCLIP);entities[130&UPDATE_MASK][0].modelindex=2;cl.servertime=10.01;CL_TransitionEntities();cl.servertime=10.015;CL_TransitionEntities();
 CHECK(fabsf(cl.lerpents[2].origin[0]-249.6f)<.1f,"replacement model change still snaps");
 setup(1,MOVETYPE_NOCLIP);entities[130&UPDATE_MASK][0].origin[0]=5000;cl.servertime=10.01;CL_TransitionEntities();cl.servertime=10.015;CL_TransitionEntities();
 CHECK(fabsf(cl.lerpents[2].origin[0]-5000)<.1f,"impossible replacement noclip displacement still snaps");
 setup(1,MOVETYPE_NOCLIP);cl.serverinfo.cap="";cl.servertime=10.01;CL_TransitionEntities();
 CHECK(entity_predict_calls>0&&cl.lerpents[2].origin[0]>999,"old-server packet policy remains unchanged");
 setup(1,MOVETYPE_NOCLIP);movevars.physicsmode=0;cl.servertime=10.01;CL_TransitionEntities();
 CHECK(entity_predict_calls>0&&cl.lerpents[2].origin[0]>999,"non-Source packet policy remains unchanged");
}
static void classic_tests(void) {
 setup(0,MOVETYPE_NOCLIP);cl.servertime=10.015;CL_TransitionEntities();
 CHECK(fabsf(cl.lerpplayers[1].origin[0]-499.2f)<.1f,"classic protocol without teleport epoch conservatively selects latest raw noclip across sequence wrap");
 CHECK(fabsf(native_classic_link(1)-499.2f)<.1f&&predict_calls==0,"classic final renderer uses latest noclip, never viewer-speed PM or unsupported interpolation");
 predict_calls=0;CL_SetUpPlayerPrediction(true);
 CHECK(predict_calls==0&&fabsf(predicted_players[1].origin[0]-499.2f)<.1f,"classic setup does not run seat0 mover for another noclip actor");
 cl.do_lerp_players=1;
 CHECK(!native_classic_parse_predicts(&cl.inframes[131&UPDATE_MASK].playerstate[1]),"classic reception keeps noclip predorigin authoritative");
 setup(0,MOVETYPE_WALK);predict_calls=0;CL_SetUpPlayerPrediction(true);
 CHECK(predict_calls>0,"classic normal setup still predicts");
 setup(0,MOVETYPE_NOCLIP);cl.inframes[130&UPDATE_MASK].playerstate[1].effects=native_classic_effects(EF_TELEPORT_BIT);cl.servertime=10.015;CL_TransitionEntities();
 CHECK(cl.inframes[130&UPDATE_MASK].playerstate[1].effects==0&&fabsf(cl.lerpplayers[1].origin[0]-499.2f)<.1f,"real classic byte serializer/parser loses epoch, fallback still never smears teleport");
 setup(0,MOVETYPE_NOCLIP);cl.inframes[130&UPDATE_MASK].playerstate[1].pm_type=PM_NORMAL;cl.servertime=10.015;CL_TransitionEntities();
 CHECK(fabsf(cl.lerpplayers[1].origin[0]-499.2f)<.1f,"classic movement-class change rejects old interpolation pair");
 setup(0,MOVETYPE_NOCLIP);cl.servertime=10.015;CL_TransitionEntities();
 cl.inframes[131&UPDATE_MASK].playerstate[0].pm_type=PM_SPECTATOR;cl.inframes[131&UPDATE_MASK].playerstate[0].modelindex=1;cl.inframes[131&UPDATE_MASK].playerstate[0].messagenum=131;cl.playerview[0].simorg[0]=77;
 CHECK(native_classic_link(0)==77,"own classic noclip body retains its local predicted pose, not remote interpolation");
 cl.inframes[131&UPDATE_MASK].playerstate[0].pm_type=PM_NORMAL;
 CHECK(native_classic_link(0)==999,"ordinary local-body render selection remains the legacy policy");
}
static void demo_tests(void) {
 demo_result r=native_demo_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1);
 CHECK(r.nopred&&fabsf(r.x-124.8f)<.1f,"replacement demo acquires current noclip entity despite stale walking type and freshtype0, then blends240+ displacement");
 r=native_demo_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,249.6f,0,0,1);
 CHECK(r.nopred&&fabsf(r.x-124.8f)<.1f,"actual final demo interpolation accepts steady fast noclip");
 r=native_demo_frame(PM_SPECTATOR,MOVETYPE_WALK,64,0,0,1);
 CHECK(!r.nopred,"fresh walking entity leaves noclip-only demo policy immediately");
 r=native_demo_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,64,EF_TELEPORT_BIT,0,1);
 CHECK(r.nopred&&fabsf(r.x-64)<.1f,"decoded explicit demo teleport is not smeared");
 r=native_demo_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,64,0,1,1);
 CHECK(r.nopred&&fabsf(r.x-64)<.1f,"decoded demo model change is not smeared");
 r=native_demo_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,0);
 CHECK(r.nopred&&fabsf(r.x-499.2f)<.1f,"classic demo without epoch uses latest raw snapshot, not enlarged teleport envelope");
 r=native_demo_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1);
 CHECK(fabsf(r.yaw-45)<.1f,"own QW noclip demo preserves acknowledged recorded turn despite stale aim and differing packet/command indices");
 r=native_actor_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1,1);
 CHECK(r.nopred&&fabsf(r.x-124.8f)<.1f&&fabs(r.fromtime-10)<.00001&&fabs(r.totime-10.03)<.00001,"live locked spectator shares actor snapshot interpolation and timestamps despite command age");
 r=native_actor_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1,2);
 CHECK(r.nopred&&fabsf(r.x-124.8f)<.1f,"locked demo spectator shares actor interpolation, not viewer preference");
 r=native_actor_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1,3);
 CHECK(!r.nopred,"free spectator flight does not inherit tracked actor policy");
 r=native_actor_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1,4);
 CHECK(fabsf(r.yaw-25)<.1f,"server fixed-angle presentation takes precedence over recorded command interpolation");
 r=native_actor_frame(PM_NORMAL,MOVETYPE_NOCLIP,249.6f,0,0,1,5);
 CHECK(fabsf(r.yaw-90)<.1f,"missing acknowledged commands fall back to actual recorded view, never stale aim");
}
static void placement_tests(void){
 qc_edict body={0};vec3_t dest={200,0,0};qc_place(&body,dest);
 demo_result r=native_demo_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,200,body.effects,0,1);
 CHECK(body.effects==EF_TELEPORT_BIT&&fabsf(r.x-200)<.1f,"actual point/map placement producer publishes epoch into final noclip demo consumer");
 qc_place(&body,dest);CHECK(body.effects==EF_TELEPORT_BIT,"same-origin map placement does not invent another presentation epoch");
 memset(&body,0,sizeof(body));qc_trigger_place(&body,dest);
 r=native_actor_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,200,body.effects,0,1,1);
 CHECK(body.effects==EF_TELEPORT_BIT&&fabsf(r.x-200)<.1f,"actual angle-preserving trigger placement publishes epoch into tracked noclip consumer");
 memset(&body,0,sizeof(body));qc_relative_place(&body,dest);
 r=native_actor_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,200,body.effects,0,1,1);
 CHECK(body.effects==EF_TELEPORT_BIT&&fabsf(r.x-200)<.1f,"actual relative-trigger placement reaches shared epoch and final tracked consumer");
 memset(&body,0,sizeof(body));qc_public_place(&body,dest);
 r=native_demo_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,200,body.effects,0,1);
 CHECK(body.effects==EF_TELEPORT_BIT&&fabsf(r.x-200)<.1f,"actual public setpos reaches shared epoch and final demo consumer");
}
static void mvd_tests(void){
 unsigned mask=native_mvd_mask(1);float decoded=native_velocity_wire(mask);
 CHECK(fabsf(decoded-8320)<.01f&&wire.cursize==8,"actual full-MVD capability mask through encode/writer/reader preserves8320 velocity");
 acquired_velocity=decoded;demo_result r=native_demo_frame(PM_SPECTATOR,MOVETYPE_NOCLIP,249.6f,0,0,1);
 CHECK(fabsf(r.x-124.8f)<.1f,"actual MVD-acquired velocity permits continuous fast noclip at final consumer");
 float narrow=native_velocity_wire(mask&~PEXT2_BIGVELOCITY);
 CHECK(fabsf(narrow-4095.875f)<.01f&&wire.cursize==4,"unnegotiated16bit velocity still saturates and codec stays narrow");
 CHECK(!(native_mvd_mask(0)&(PEXT2_REPLACEMENTDELTAS|PEXT2_BIGVELOCITY)),"full-MVD with replacements disabled does not advertise unsupported width");
 acquired_velocity=8320;
}
int main(void){packet_tests();classic_tests();demo_tests();placement_tests();mvd_tests();return bad?2:0;}
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--pred-source',type=Path);ap.add_argument('--ents-source',type=Path);ap.add_argument('--map-source',type=Path);ap.add_argument('--player-source',type=Path);ap.add_argument('--mvd-source',type=Path)
    a=ap.parse_args()
    if not any((p/'OWNER.md').is_file() for p in a.out.resolve().parents):ap.error('--out must be under an owned task root')
    native=a.engine/'engine';paths={'prediction':a.pred_source or native/'client/cl_pred.c','entities':a.ents_source or native/'client/cl_ents.c','mathHeader':native/'common/mathlib.h','mathSource':native/'common/mathlib.c','movement':native/'common/pmove.h','edict':native/'common/pr_common.h','limits':native/'client/quakedef.h','protocol':native/'gl/gl_model.h','wireHeader':native/'common/protocol.h','wireSource':native/'common/common.c','wireServer':native/'server/sv_ents.c','mapProducer':a.map_source or a.engine.parent/'qc/src/server/sv_entities.qc','playerProducer':a.player_source or a.engine.parent/'qc/src/server/sv_player.qc','mvdProducer':a.mvd_source or native/'server/sv_mvd.c'}
    text={k:p.read_text(encoding='utf-8') for k,p in paths.items()};pred=text['prediction'];ents=text['entities']
    census=placement_census(a.engine.parent/'qc/src/server',{'sv_entities.qc':paths['mapProducer'],'sv_player.qc':paths['playerProducer']})
    unclassified=[row for row in census if row['disposition'].startswith('UNCLASSIFIED')]
    macros='\n'.join(line for line in text['mathHeader'].splitlines() if re.match(r'#define\s+(?:VectorCopy|VectorClear|VectorSet|VectorSubtract|VectorScale|VectorInterpolate|VectorInverse|VectorEquals|FloatInterpolate|DotProduct|bound|nanmask|IS_NAN)\b',line))+'\n'
    macros+='\n'.join(line.strip() for line in text['limits'].splitlines() if re.match(r'\s*#define (min|max)\(',line))+'\n'
    macros+=re.search(r'typedef enum \{\s*PM_NORMAL,.*?\} pmtype_t;',text['movement'],re.S).group(0)+'\n'
    macros+='\n'.join(line for line in text['edict'].splitlines() if re.match(r'#define\s+MOVETYPE_\w+\s',line))+'\n'
    for name in ['EF_TELEPORT_BIT','EF_RESTARTANIM_BIT']:
        macros+=re.search(r'^#define\s+'+name+r'\b[^\n]*',text['protocol'],re.M).group(0)+'\n'
    # Macros precede stubs; scalar/vector declarations are already in PREFIX.
    pos=PREFIX.index('static float CompareAngles')
    prefix=PREFIX[:pos]+macros+PREFIX[pos:]
    code=prefix+function(text['mathSource'],'Length')+function(text['mathSource'],'VectorInverse')
    for name in ['MSG_WriteByte','MSG_WriteShort','MSG_WriteLong','MSG_ReadByte','MSG_ReadShort','MSG_ReadLong']:
        code+=function(text['wireSource'],name)
    masks=re.findall(r'demo\.recorder\.fteprotocolextensions2 = [^;]+;',text['mvdProducer'])
    mask=next(line for line in masks if 'PEXT2_REPLACEMENTDELTAS' in line)
    needed=set(re.findall(r'\bPEXT2_\w+\b',mask))|{'PEXT2_BIGVELOCITY','UFP_VELOCITYXY','UFP_VELOCITYZ'}
    for name in sorted(needed):code+=re.search(r'^#define\s+'+name+r'\b[^\n]*',text['wireHeader'],re.M).group(0)+'\n'
    code+=function(text['wireServer'],'SV_EncodeVelocity')
    code+='static unsigned native_mvd_mask(int enabled){struct{int ival;}pext_replacementdeltas={enabled};struct{struct{unsigned fteprotocolextensions2;}recorder;}demo={0};\n'+mask+'\nreturn demo.recorder.fteprotocolextensions2;}\n'
    writer=block(text['wireServer'],'if (predbits & UFP_VELOCITYXY)')+'\n'+block(text['wireServer'],'if (predbits & UFP_VELOCITYZ)')
    reader=block(ents,'if (predbits & UFP_VELOCITYXY)')+'\n'+block(ents,'if (predbits & UFP_VELOCITYZ)')
    code+='static float native_velocity_wire(unsigned pext2){entity_state_t packed={0},decoded={0},*state=&packed,*news=&decoded;edictvars_t vars={{8320,0,0}};edict_t ent={&vars};client_t client={pext2};sizebuf_t *msg=&wire;unsigned predbits=UFP_VELOCITYXY;memset(&wire,0,sizeof(wire));cls.fteprotocolextensions2=pext2;SV_EncodeVelocity(state,&ent,&client);\n'+writer+'\n'+reader+'\nreturn news->u.q1.velocity[0]*(1.0f/8);}\n'
    code+=re.search(r'^#define\s+PF_EFFECTS\b[^\n]*',text['wireHeader'],re.M).group(0)+'\n'
    write=re.search(r'if \(pflags & PF_EFFECTS\)\s+MSG_WriteByte \(msg, ent->effects\);',text['wireServer']).group(0)
    read=re.search(r'if \(flags & PF_EFFECTS\)\s+state->effects = MSG_ReadByte \(\);\s+else\s+state->effects = 0;',ents).group(0)
    code+='static int native_classic_effects(int effects){sizebuf_t *msg=&wire;struct{int effects;}data={effects},*ent=&data;player_state_t out={0},*state=&out;int pflags=PF_EFFECTS,flags=PF_EFFECTS;memset(&wire,0,sizeof(wire));\n'+write+'\n'+read+'\nreturn state->effects;}\n'
    # Literal QC placement statements; only entity/vector equality syntax and
    # allocation/timer context are adapted. This is not execution of the QC VM.
    producer=text['mapProducer']
    place=re.search(r'void\(entity p, vector org\) SV_PlacePlayer =\s*\{(.*?)\n\};',producer,re.S).group(1)
    trigger=re.search(r'(?:if \(other.origin != newpos\)\s+other.effects = other.effects \^ ZONE_EF_TELEPORT_BIT;\s+)?(?:SV_SetPlayerOrigin|setorigin)\(other, newpos\);',producer).group(0)
    def adapt(body):
        return body.replace('p.origin != org','!VectorEquals(p.origin, org)').replace('other.origin != newpos','!VectorEquals(other.origin, newpos)').replace('p.','p->').replace('other.','other->')
    code+='#define ZONE_EF_TELEPORT_BIT 2097152\n'
    shared=re.search(r'void\(entity p, vector org\) SV_SetPlayerOrigin =\s*\{(.*?)\n\};',producer,re.S)
    if shared:code+='static void SV_SetPlayerOrigin(entity p,vec3_t org){'+adapt(shared.group(1))+'}\n'
    relative=re.search(r'(?:SV_SetPlayerOrigin|setorigin)\(other, p\);',producer).group(0)
    setpos=re.search(r'(?:SV_SetPlayerOrigin|setorigin)\(self, org\);',text['playerProducer']).group(0)
    code+='static void qc_place(entity p,vec3_t org){'+adapt(place)+'}\nstatic void qc_trigger_place(entity other,vec3_t newpos){'+adapt(trigger)+'}\nstatic void qc_relative_place(entity other,vec3_t p){'+relative+'}\nstatic void qc_public_place(entity self,vec3_t org){'+setpos+'}\n'
    for name in ['CL_SourceNoclipEntityLerp','CL_SourceNoclipLerp','CL_SourceNoclipDiscontinuity']:
        if re.search(r'^qboolean '+name+r'\(',pred,re.M):code+=function(pred,name)
    code+=function(pred,'CL_EntStateToPlayerState')
    code+=function(ents,'CL_TransitionPacketEntities')+function(ents,'CL_ChooseInterpolationFrames')
    for name in ['CL_LerpSourceNoclipPlayer','CL_SnapSourceNoclipPlayer']:
        if 'static void '+name+'(' in ents:code+=function(ents,name)
    code+=function(ents,'CL_TransitionEntities')+function(ents,'CL_SetUpPlayerPrediction')
    # Actual final classic render-selection block, no invented policy booleans.
    link=ents.split('void CL_LinkPlayers',1)[1]
    local_loop=link.index('\t\tfor (pnum = 0;',link.index('// the player object gets added with flags | 2'))
    selection=link[local_loop:link.index('\t\tVectorCopy(ent->origin, nametagorg[j])')]
    code+=r'''
static float native_classic_link(int j){
 struct{vec3_t origin,angles,axis[3];}entity={0},*ent=&entity;
 player_state_t *state=&cl.inframes[cl.parsecount&UPDATE_MASK].playerstate[j],exact;
 int pnum=cl.splitclients,msec=30,predictplayers=1,oldphysent;vec3_t angles={0};model_t *model=NULL;
 float predictmsmult=1000,playertime=state->state_time+.03;
'''+selection+'\nreturn ent->origin[0];}\n'
    parse=ents.split('if (cl.worldmodel && cl.do_lerp_players',1)[1].split('\n\t{',1)[0]
    assert parse.rstrip().endswith(')')
    code+='static int native_classic_parse_predicts(player_state_t *state){(void)state;return (cl.worldmodel && cl.do_lerp_players'+parse.rstrip()[:-1]+');}\n'
    # Actual recorded-data acquisition and no-pred decision, including packet branch.
    acquisition=pred[pred.index('\tsource_demo_type = pv->pmovetype;'):pred.index('\t//these things also force-disable prediction')]
    decision=pred.split('//these things also force-disable prediction',1)[1].split('// figure out the first frame',1)[0]
    blend=pred[pred.index('\tif (to.time == from.time)'):pred.index('\t/*FTESurf Patch 269: the dump.')]
    if 'static void CL_SourceNoclipDemoAngles(' in pred:code+=function(pred,'CL_SourceNoclipDemoAngles')
    selector=pred[pred.index('\tif (nopred)\n\t{\n\t\tlerpangles = false;'):pred.index('\n\telse\n\t{\n\t\tto.frame = from.frame = 0;')]
    ages={side:re.search(r'if \(nopred[^\n]*\)\s+'+side+r'\.time -= [^;]+;',pred).group(0) for side in ['from','to']}
    code+=r'''
typedef struct{float x,yaw;int nopred;double fromtime,totime;}demo_result;
static demo_result native_actor_frame(int stale,int movetype,float distance,int effect,int modelchange,int replacement,int role){
 memset(&cl,0,sizeof(cl));memset(&cls,0,sizeof(cls));
 cl.serverinfo.cap="1";cl.validsequence=131;cl.allocated_client_slots=2;cls.demoplayback=(role==0||role==2||role==4||role==5)?DPB_QUAKEWORLD:0;cls.protocol=CP_QUAKEWORLD;
 cls.fteprotocolextensions2=replacement?PEXT2_REPLACEMENTDELTAS:0;cls.z_ext=Z_EXT_PM_TYPE_NEW;
 movevars.physicsmode=PHYSMODE_SOURCE;movevars.ticrate=.015f;
 entity_state_t actor[3]={{0}};
 for(int n=0;n<3;n++){
  actor[n].number=2;actor[n].modelindex=1;actor[n].u.q1.pmovetype=movetype;actor[n].u.q1.velocity[0]=(int)(acquired_velocity*8);
  actor[n].origin[0]=n==0?0:n==1?distance:499.2f;actor[n].effects=n?effect:0;actor[n].u.q1.msec=n==0?10:25;
  inframe_t *fr=&cl.inframes[(129+n)&UPDATE_MASK];fr->frameid=129+n;fr->ackframe=5+n;fr->packet_entities.entities=&actor[n];fr->packet_entities.num_entities=1;fr->packet_entities.servertime=10+.03*n;
  player_state_t *ps=&fr->playerstate[1];ps->messagenum=129+n;ps->modelindex=1;ps->pm_type=movetype==MOVETYPE_NOCLIP?PM_SPECTATOR:PM_NORMAL;
  ps->origin[0]=actor[n].origin[0];ps->velocity[0]=8320;ps->effects=native_classic_effects(actor[n].effects);
  cl.outframes[5+n].cmd_sequence=5+n;cl.outframes[5+n].cmd[0].angles[1]=n?16384:0;
 }
 actor[1].modelindex+=modelchange;
 cl.currentpackentities=&cl.inframes[130&UPDATE_MASK].packet_entities;cl.previouspackentities=&cl.inframes[129&UPDATE_MASK].packet_entities;cl.currentpacktime=10.015;
 playerview_t body={0},*pv=&body;pv->pmovetype=stale;pv->nolocalplayer=replacement;pv->playernum=(role==1||role==2||role==3)?0:1;pv->spectator=(role==1||role==2||role==3);pv->cam_state=(role==1||role==2)?CAM_EYECAM:0;
 pv->simangles[1]=role==4?25:12;pv->viewangles[1]=90;
 if(role==4)cl.currentpackentities->fixangles[0]=1;
 if(role==5)cl.outframes[5].cmd_sequence=0;
 int source_demo_type=stale,source_demo_lerp=0,source_demo_angles=0,nopred=0,trackent=2,seat=0,i,lerpangles=cls.demoplayback==DPB_QUAKEWORLD;
 float source_demo_anglefrac=1;(void)source_demo_angles;(void)source_demo_anglefrac;
'''+acquisition+decision+r'''
 player_state_t first={0},last={0};
 struct{double time;int frame;player_state_t *state;usercmd_t *cmd;}from={10,129,&first,&first.command},to={10.03,130,&last,&last.command};
 double simtime=10.015;float f=0,pt_f=0;(void)pt_f;
'''+selector+r'''
 if(replacement){
  packet_entities_t *pe=&cl.inframes[from.frame&UPDATE_MASK].packet_entities;i=0;
  CL_EntStateToPlayerState(&first,&pe->entities[i]);
'''+ages['from']+r'''
  pe=&cl.inframes[to.frame&UPDATE_MASK].packet_entities;
  CL_EntStateToPlayerState(&last,&pe->entities[i]);
'''+ages['to']+r'''
 }else{first=cl.inframes[from.frame&UPDATE_MASK].playerstate[1];last=cl.inframes[to.frame&UPDATE_MASK].playerstate[1];}
 if(!from.cmd)from.cmd=&first.command;
 if(!to.cmd)to.cmd=&last.command;
'''+blend+r'''
 return (demo_result){pv->simorg[0],pv->simangles[1],nopred,from.time,to.time};
}
static demo_result native_demo_frame(int stale,int movetype,float distance,int effect,int modelchange,int replacement){return native_actor_frame(stale,movetype,distance,effect,modelchange,replacement,0);}
'''
    code+=TESTS.replace('packet_tests();classic_tests();','CHECK('+str(int(not unclassified))+',"complete raw QC origin-write census has only classified non-placement/helper exceptions");packet_tests();classic_tests();')
    digest=hashlib.sha256(code.encode()).hexdigest();a.out.mkdir(parents=True,exist_ok=True)
    src=a.out/('native-presentation-'+digest[:12]+'.c');src.write_text(code)
    gcc=Path('C:/msys64/ucrt64/bin/gcc.exe');env=dict(os.environ,PATH=str(gcc.parent)+os.pathsep+os.environ.get('PATH',''))
    compile=subprocess.run([str(gcc),'-O2','-fno-strict-aliasing','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter',str(src),'-o',str(src.with_suffix('.exe'))],capture_output=True,text=True,env=env)
    run=subprocess.run([str(src.with_suffix('.exe'))],capture_output=True,text=True,env=env) if compile.returncode==0 else None
    result={'sources':{k:str(p) for k,p in paths.items()},'sourceSha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},'generatedSha256':digest,'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'compileExit':compile.returncode,'compileOutput':compile.stdout+compile.stderr,'exit':run.returncode if run else None,'stdout':run.stdout if run else '', 'stderr':run.stderr if run else '', 'limits':__doc__,'placementCensus':census,'unclassifiedOriginWrites':unclassified}
    (a.out/('receipt-'+digest[:12]+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(result['compileOutput'] if compile.returncode else result['stdout']+result['stderr'])
    raise SystemExit(3 if compile.returncode else run.returncode)


if __name__=='__main__':main()
