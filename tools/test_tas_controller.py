#!/usr/bin/env python3
"""P1308: actual production air/ground objective for independent movement keys."""
import argparse
import os
from pathlib import Path
import subprocess
from test_tas_strafe import extract

PREFIX = r'''
#include <stdio.h>
#include <float.h>
#include <math.h>
#include <string.h>
#include "@HEADER@"
#define MAX_CLIENTS 2
#define GT_PROGS 0
static int svprogfuncs=1;
#define SV_TAPE_ACTIVE 1
#define SV_TAPE_STAGING 2
#define SV_TAPE_CANCELLED 3
typedef struct {int entnum;} edict_t;
typedef struct {edict_t *edict;unsigned userid;} client_t;
typedef struct {unsigned userid,spawncount;float planamount;int planmode,planair,planpostpending;struct{int valid;}lastinput;struct{int state;}tape;} tas_rewind_pool_t;
static struct {int allocated_client_slots;} sv;
static struct {client_t clients[MAX_CLIENTS];unsigned spawncount;int gametype;} svs;
static tas_rewind_pool_t *tas_rewind_pool[MAX_CLIENTS];
static float published_amount;
static int publications;
static void SV_TASTapePublish(edict_t *e,tas_rewind_pool_t *p){(void)e;published_amount=p->planamount;++publications;}
static void SV_TASTapeStop(edict_t *e,tas_rewind_pool_t *p,int state){p->tape.state=state;SV_TASTapePublish(e,p);}
typedef float vec3_t[3];
#define PM_DEAD 1
#define PM_NORMAL 0
#define PM_SPECTATOR 2
#define PM_OLD_SPECTATOR 3
#define PM_FREEZE 4
#define PM_NONE 5
#define PMSRC_DUCK_SPEED_MODIFIER .34f
#define QDECL
#define VectorCopy(a,b) ((b)[0]=(a)[0],(b)[1]=(a)[1],(b)[2]=(a)[2])
#define DotProduct(a,b) ((a)[0]*(b)[0]+(a)[1]*(b)[1]+(a)[2]*(b)[2])
#define VectorLength(a) sqrtf(DotProduct(a,a))
#define VectorScale(a,b,c) ((c)[0]=(a)[0]*(b),(c)[1]=(a)[1]*(b),(c)[2]=(a)[2]*(b))
static struct {int pm_type,onground,ducked;float waterjumptime,surfacefriction;vec3_t velocity;struct{float forwardmove,sidemove,upmove;}cmd;} pmove;
static struct {float maxairspeed,friction,stopspeed,duckspeed;} movevars;
static float pms_frametime,pms_forwardmove,pms_sidemove,pms_upmove,pms_maxspeed,fixture_maxspeed;
static vec3_t pms_forward,pms_right;
static float PMSrc_EffectiveMaxSpeed(void){return fixture_maxspeed;}
'''
TEST = r'''
static int checks,failed;
static void Check(int ok,const char *name){++checks;if(!ok){++failed;fprintf(stderr,"FAIL %s\n",name);}}
static double Actual(const sv_tas_guide_t *g,unsigned short yaw){
 float r=(float)(yaw*(6.2831853071795864769/65536.0));
 float wish;vec3_t dir;
 pmove.pm_type=PM_NORMAL;pmove.onground=g->ground;pmove.ducked=g->ducked;
 pmove.cmd.forwardmove=g->forward;pmove.cmd.sidemove=g->side;pmove.cmd.upmove=0;
 fixture_maxspeed=g->maxspeed;movevars.duckspeed=g->duckspeed;
 pms_forward[0]=cosf(r);pms_forward[1]=sinf(r);pms_forward[2]=0;
 pms_right[0]=sinf(r);pms_right[1]=-cosf(r);pms_right[2]=0;
 ActualParameters();PMSrc_HandleDuckingSpeedCrop();wish=PMSrc_WishDir(dir);
 pmove.velocity[0]=g->vx;pmove.velocity[1]=g->vy;pmove.velocity[2]=0;
 pmove.onground=g->ground;pmove.surfacefriction=g->surface;
 movevars.maxairspeed=g->aircap;movevars.friction=g->friction;movevars.stopspeed=g->stopspeed;
 pms_frametime=g->dt;
 if(g->ground){PMSrc_Friction();PMSrc_Accelerate(dir,wish,g->accel);}
 else PMSrc_AirAccelerate(dir,wish,g->accel);
 return (double)pmove.velocity[0]*pmove.velocity[0]+(double)pmove.velocity[1]*pmove.velocity[1];
}
static void CancelLifecycle(void){
 edict_t e={1},other={2};tas_rewind_pool_t pool={0};
 sv.allocated_client_slots=MAX_CLIENTS;svs.spawncount=3;
 svs.clients[0].edict=&other;svs.clients[0].userid=12;tas_rewind_pool[0]=&pool;
 pool.userid=11;pool.spawncount=3;pool.planamount=2;pool.lastinput.valid=1;pool.planmode=4;
 SV_TASInputCancel(&e);
 Check(pool.planamount==2&&publications==0,"cancellation refuses a different slot edict");
 svs.clients[0].edict=&e;SV_TASInputCancel(&e);
 Check(pool.userid==12&&pool.spawncount==3,"cancellation binds the replacement identity");
 Check(pool.planamount==1&&published_amount==1,"replacement identity publishes default one-times amount");
 Check(!pool.lastinput.valid&&!pool.planmode&&!pool.planair&&!pool.planpostpending,"identity reset cancels pending recipe state");
 pool.planamount=0;SV_TASInputCancel(&e);
 Check(pool.planamount==0&&published_amount==0,"same-owner cancel preserves deliberately selected zero");
 ++svs.spawncount;SV_TASInputCancel(&e);
 Check(pool.planamount==1&&pool.spawncount==svs.spawncount,"changed map identity also restores the default");
 pool.planamount=0;pool.tape.state=SV_TAPE_ACTIVE;SV_TASInputCancel(&e);
 Check(pool.tape.state==SV_TAPE_CANCELLED&&published_amount==0,"active tape cancellation preserves same-owner amount");
}
int main(void){
 sv_tas_guide_t g={0};unsigned short yaw,a,b;int i,k,j,side;
 const float speeds[]={50,230,280,800};
 CancelLifecycle();
 Check(SV_TASStrafeYaw(800,0,250,150,.015f,1,30,1,&a),"legacy selector control acts");
 Check(SV_TASStrafeUnclipped(800,0,0,562.5f,3500,3500),"existing cap guard control acts");
 for(k=0;k<128;++k)for(side=-1;side<=1;side+=2){
  float speed=speeds[k%4],bearing=(float)(k*.719731);double best=-1,chosen,tol;
  g.vx=speed*cosf(bearing);g.vy=speed*sinf(bearing);g.forward=(k&4)?450:0;g.side=side*450;
  g.maxspeed=(k&64)?600:250;g.ground=(k&8)!=0;g.ducked=(k&16)!=0;g.accel=g.ground?10:((k&32)?1:150);
  g.dt=(k&2)?.01f:.015f;g.surface=(k&1)?.25f:1;g.aircap=30;g.friction=4;g.stopspeed=100;g.amount=1;
  g.duckspeed=(k&32)?.5f:0;
  Check(SV_TASGuideYaw(&g,&yaw),"supported guide state");
  for(i=0;i<65536;++i){
   double r=i*(6.2831853071795864769/65536.0);
   double x=g.forward*cos(r)+g.side*sin(r),y=g.forward*sin(r)-g.side*cos(r);
   if(side*((double)g.vx*y-(double)g.vy*x)>speed*sqrt(x*x+y*y)*.000001)continue;
   chosen=Actual(&g,(unsigned short)i);if(chosen>best)best=chosen;
  }
  chosen=Actual(&g,yaw);tol=12*FLT_EPSILON*(speed*speed+250*250)+.002;
  if(best-chosen>tol)fprintf(stderr,"case%d side%d gap%g tolerance%g\n",k,side,best-chosen,tol);
  Check(best-chosen<=tol,"1x reaches actual capped acceleration objective with selected keys");
 }
 g.vx=1000;g.vy=0;g.forward=450;g.side=450;g.ground=0;g.ducked=0;g.accel=150;g.dt=.015f;g.amount=.8f;
 g.maxspeed=250;g.surface=1;g.duckspeed=0;
 Check(SV_TASGuideYaw(&g,&a),"combined-key reference acts");g.amount=1.2f;
 Check(SV_TASGuideYaw(&g,&b)&&a==b,"amount does not distort the one-times gain reference");
 yaw=(unsigned short)(a-100);
 Check((unsigned short)(SV_TASGuideSlew(yaw,a,g.dt,.8f)-yaw)==80,"gentler scales shortest yaw CHANGE");
 Check((unsigned short)(SV_TASGuideSlew(yaw,a,g.dt,1.2f)-yaw)==120,"sharper scales shortest yaw CHANGE");
 g.amount=1;SV_TASGuideYaw(&g,&a);g.forward=0;SV_TASGuideYaw(&g,&b);
 Check(a!=b,"W+D is not silently replaced by pure D");
 for(j=0;j<2;++j){
  float vx=250,vy=0;g.ground=1;g.ducked=0;g.accel=10;g.forward=450;g.side=450;g.dt=j?.01f:.015f;
  for(i=0;i<600;++i){g.vx=vx;g.vy=vy;Check(SV_TASGuideYaw(&g,&a),"sustained ground state");Actual(&g,a);vx=pmove.velocity[0];vy=pmove.velocity[1];}
  Check(sqrtf(vx*vx+vy*vy)>275,"acting ground guide beats 275 under explicit 250/10/4 fixture");
  printf("ground fixture dt%.3f terminal%.9g (not owner289 acceptance)\n",g.dt,sqrtf(vx*vx+vy*vy));
 }
 for(i=0;i<65536;++i)Check(SV_TASPlanAngleWord((float)(short)i*(360.0f/65536))==(unsigned short)i,"all signed fractional body yaw words survive planner cache");
 Check(SV_TASPlanAngleWord(-365.3997802734375f)==64553,"negative fractional yaw wraps before unsigned conversion");
 g.ground=1;g.ducked=1;g.accel=5;g.forward=450;g.side=450;g.dt=.015f;
 g.maxspeed=260;g.friction=4;g.stopspeed=75;g.duckspeed=.34f;g.surface=1;g.amount=1;g.vx=g.vy=0;b=0;
 for(i=0;i<128;++i){
  int acts=SV_TASGuideYaw(&g,&a);Check(i==0||acts,"low-speed fully-ducked guide reference acts");
  if(acts)b=SV_TASGuideSlew(b,a,g.dt,g.amount);
  Actual(&g,b);g.vx=pmove.velocity[0];g.vy=pmove.velocity[1];
  b=SV_TASPlanAngleWord((float)(short)b*(360.0f/65536));
  if(i==63)printf("duck actual-pipeline slew64 speed%.9g yaw%u\n",sqrtf(g.vx*g.vx+g.vy*g.vy),(unsigned)b);
 }
 printf("duck actual-pipeline slew128 speed%.9g\n",sqrtf(g.vx*g.vx+g.vy*g.vy));
 Check(sqrtf(g.vx*g.vx+g.vy*g.vy)>97&&sqrtf(g.vx*g.vx+g.vy*g.vy)<100,"actual-pipeline crouch controller does not settle for straight88.4");
 Check(SV_TASGuideSlew(0,32768,.015f,1)!=32768,"arbitrary enable angle cannot snap180degrees");
 Check(SV_TASGuideSlew(123,32768,.015f,0)==123,"zero amount holds heading");
 g.amount=5;Check(!SV_TASGuideYaw(&g,&a),"invalid amount refused");
 g.amount=1;g.side=0;Check(!SV_TASGuideYaw(&g,&a),"no strafe direction retains view");
 {union{unsigned int u;float f;}bad;bad.u=0x7fc00000u;g.side=450;g.vx=bad.f;Check(!SV_TASGuideYaw(&g,&a),"NaN refused under fastmath");}
 printf("%d actual-C controller checks, %d failed\n",checks,failed);return failed?1:0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    args = ap.parse_args()
    if not any((p/'OWNER.md').is_file() for p in [args.out, *args.out.parents]):
        ap.error('--out must be under an owned task root')
    args.out.mkdir(parents=True, exist_ok=False)
    mover = (args.engine/'engine/common/pm_source.c').read_text()
    code = PREFIX.replace('@HEADER@', (args.engine/'engine/server/sv_tas_control.h').resolve().as_posix())
    code += '\n'+extract((args.engine/'engine/server/sv_tas_rewind.inc').read_text(), 'static void SV_TASInputCancel(edict_t *e)\n{')
    code += '\n'+extract((args.engine/'engine/common/mathlib.c').read_text(), 'float QDECL VectorNormalize (')
    start = mover.index('\tpms_forwardmove = pmove.cmd.forwardmove;', mover.index('static void PMSrc_Tick ('))
    end = mover.index('\t/* --- ReduceTimers', start)
    code += '\nstatic void ActualParameters(void) {\n'+mover[start:end]+'}\n'
    for signature in ['static void PMSrc_HandleDuckingSpeedCrop (', 'static float PMSrc_WishDir (',
                      'static void PMSrc_Friction (', 'static void PMSrc_Accelerate (', 'static void PMSrc_AirAccelerate (']:
        code += '\n'+extract(mover, signature)
    src = args.out/'controller.c'
    src.write_text(code+'\n'+TEST)
    env = os.environ.copy()
    env['PATH'] = str(args.cc.parent)+os.pathsep+env['PATH']
    exe = args.out/'controller.exe'
    p = subprocess.run([str(args.cc), '-std=c99', '-O2', '-ffast-math', '-Wall', '-Wextra', '-Werror', str(src), '-lm', '-o', str(exe)], env=env, capture_output=True, text=True)
    (args.out/'compile.log').write_text(p.stdout+p.stderr)
    p.check_returncode()
    p = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
    (args.out/'result.log').write_text(p.stdout+p.stderr)
    print(p.stdout+p.stderr, end='')
    raise SystemExit(p.returncode)


if __name__ == '__main__':
    main()
