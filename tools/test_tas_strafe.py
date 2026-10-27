#!/usr/bin/env python3
"""P1074: production TAS yaw choice vs exhaustive actual PMSrc_AirAccelerate.

This is the observed-state AIR acceleration objective, not collision/ramp search.
--out must be beneath an owned task root; no game/install or player data touched.
"""
import argparse
import os
from pathlib import Path
import subprocess


def extract(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


PREFIX = r'''
#include <stdio.h>
#include <stdlib.h>
#include <float.h>
#include <math.h>
#include "@HEADER@"
typedef float vec3_t[3];
#define PM_DEAD 1
#define DotProduct(a,b) ((a)[0]*(b)[0]+(a)[1]*(b)[1]+(a)[2]*(b)[2])
static struct {int pm_type; float waterjumptime, surfacefriction; vec3_t velocity, origin;} pmove;
static struct {float maxairspeed, maxvelocity;} movevars;
static float pms_frametime;
'''
TESTS = r'''
static float wx[65536], wy[65536];
static int checks, failures;
static void Check(int ok, const char *name) {
    ++checks;
    if (!ok) {++failures; fprintf(stderr,"FAIL %s\n",name);}
}
static double Actual(float vx,float vy,float wish,float aa,float friction,int side,unsigned short yaw) {
    vec3_t dir={side*wx[yaw],side*wy[yaw],0};
    pmove.velocity[0]=vx;pmove.velocity[1]=vy;pmove.velocity[2]=0;
    pmove.surfacefriction=friction;
    PMSrc_AirAccelerate(dir,wish,aa);
    return (double)pmove.velocity[0]*pmove.velocity[0]+(double)pmove.velocity[1]*pmove.velocity[1];
}
int main(void) {
    unsigned short selected=123;
    int k,i,side,witness=0;
    union {unsigned int u;float f;} bad;
    for(i=0;i<65536;++i) {
        /* Same float yaw basis used to drive both the chosen and exhaustive
         * commands; acceleration itself is extracted verbatim from production. */
        float r=(float)(i*(6.2831853071795864769/65536.0));
        wx[i]=sinf(r);wy[i]=-cosf(r);
    }
    for(k=0;k<160;++k) {
        const float speeds[]={12,50,800,2400};
        const float wishes[]={85,250,450};
        const float rates[]={1,12,150,1000};
        float speed=speeds[k%4],bearing=(float)(k*0.719731),wish=wishes[(k/4)%3];
        float aa=rates[(k/12)%4],friction=(k&1)?0.25f:1;
        float vx=speed*cosf(bearing),vy=speed*sinf(bearing);
        double tolerance=8*FLT_EPSILON*((double)speed*speed+wish*wish)+0.001;
        pms_frametime=(k&2)?0.01f:0.015f;
        movevars.maxairspeed=(k%7==0)?18:30;
        for(side=-1;side<=1;side+=2) {
            double best=-1,chosen,cross;
            Check(SV_TASStrafeYaw(vx,vy,wish,aa,pms_frametime,friction,movevars.maxairspeed,side,&selected),"finite model accepted");
            for(i=0;i<65536;++i) {
                double value;
                cross=(double)vx*(side*wy[i])-(double)vy*(side*wx[i]);
                if(side*cross>speed*0.000001)continue;
                value=Actual(vx,vy,wish,aa,friction,side,(unsigned short)i);
                if(value>best)best=value;
            }
            chosen=Actual(vx,vy,wish,aa,friction,side,selected);
            if(best-chosen>tolerance) {
                fprintf(stderr,"case%d side%d yaw%u gap%.9g tolerance%.9g\n",k,side,selected,best-chosen,tolerance);
            }
            Check(best-chosen<=tolerance,"selected quantized yaw reaches actual-mover air objective");
            cross=(double)vx*(side*wy[selected])-(double)vy*(side*wx[selected]);
            Check(side*cross<=speed*0.000001,"selected side preserved");
        }
    }
    /* An acting low-rate control: blindly using perpendicular is NOT optimal. */
    pms_frametime=.015f;movevars.maxairspeed=30;
    Check(SV_TASStrafeYaw(800,0,250,1,.015f,1,30,-1,&selected),"rate-bound control accepted");
    witness=Actual(800,0,250,1,1,-1,selected)>Actual(800,0,250,1,1,-1,0)+100;
    Check(witness,"90-degree-only perturbed control actually loses");
    /* Production clamp is not the unbounded AIR objective: an acting control
     * loses speed here, while the production eligibility guard rejects it. */
    pms_frametime=.015f;movevars.maxairspeed=30;movevars.maxvelocity=3500;
    Check(SV_TASStrafeYaw(3500,3500,260,150,.015f,1,30,-1,&selected),"unbounded cap control selected");
    Actual(3500,3500,260,150,1,-1,selected);
    PMSrc_CheckVelocity();
    Check((double)pmove.velocity[0]*pmove.velocity[0]+(double)pmove.velocity[1]*pmove.velocity[1]<24500000,"native per-axis clamp actually loses horizontal speed");
    Check(!SV_TASStrafeUnclipped(3500,3500,0,585,3500,3500),"production guard refuses cap counterexample");
    Check(SV_TASStrafeUnclipped(800,0,0,585,3500,3500),"production guard accepts ordinary unclipped air");
    Check(SV_TASStrafeUnclipped(800,0,0,585,0,3500),"native nonpositive-limit default honored");
    Check(!SV_TASStrafeUnclipped(2915,0,0,585,3500,3500),"whole acceleration and float margin retained");
    /* WPhys_CheckVelocity can use a different server cap before AIR movement.
     * Feeding its changed head to actual AIR proves the old bearing is wrong. */
    Check(SV_TASStrafeYaw(1500,500,260,150,.015f,1,30,1,&selected),"pre-clamp-bearing control selected");
    Check(Actual(1000,500,260,150,1,1,selected)<1250000,"old bearing loses speed after earlier server clamp");
    Check(!SV_TASStrafeUnclipped(1500,500,0,585,3500,1000),"divergent pre-server cap refuses AIR claim");
    Check(!SV_TASStrafeUnclipped(20,0,0,1,3500,1000),"custom divergent cap domain conservatively uses preset");
    Check(!SV_TASStrafeUnclipped(20,0,150,1,100,100),"pre-clipped vertical head cannot change friction under model");
    Check(!SV_TASStrafeUnclipped(20,0,0,1,3500,0),"nonpositive server cap refuses AIR claim");
    bad.u=0x7fc00000u;
    Check(!SV_TASStrafeYaw(bad.f,0,250,150,.015f,1,30,-1,&selected),"NaN refuses even under fast-math");
    bad.u=0x7f800000u;
    Check(!SV_TASStrafeYaw(800,bad.f,250,150,.015f,1,30,-1,&selected),"infinity refuses");
    Check(!SV_TASStrafeYaw(0,0,250,150,.015f,1,30,-1,&selected),"zero bearing leaves explicit preset");
    Check(!SV_TASStrafeYaw(800,0,0,150,.015f,1,30,-1,&selected),"zero wish refuses");
    Check(!SV_TASStrafeYaw(800,0,250,0,.015f,1,30,-1,&selected),"zero acceleration refuses");
    Check(!SV_TASStrafeYaw(800,0,250,150,0,1,30,-1,&selected),"zero tick refuses");
    Check(!SV_TASStrafeYaw(800,0,250,150,.015f,0,30,-1,&selected),"zero friction refuses");
    Check(!SV_TASStrafeYaw(800,0,250,150,.015f,1,0,-1,&selected),"zero cap refuses");
    Check(!SV_TASStrafeYaw(800,0,250,150,.015f,1,30,0,&selected),"invalid side refuses");
    printf("%d checks, %d failed; exhaustive production-air objective, float-ULP tolerance\n",checks,failures);
    return failures?1:0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    args = ap.parse_args()
    if not any((p/'OWNER.md').is_file() for p in [args.out,*args.out.parents]):
        ap.error('--out must be beneath an owned task root')
    args.out.mkdir(parents=True, exist_ok=False)
    header = args.engine/'engine/server/sv_tas_strafe.h'
    source = args.engine/'engine/common/pm_source.c'
    cfile = args.out/'tas-strafe.c'
    cfile.write_text(PREFIX.replace('@HEADER@',header.resolve().as_posix())+'\n'+
                     extract(source.read_text(), 'static void PMSrc_AirAccelerate (')+'\n'+
                     extract(source.read_text(), 'static void PMSrc_CheckVelocity (')+'\n'+TESTS)
    exe = args.out/'tas-strafe.exe'
    env = os.environ.copy()
    env['PATH'] = str(args.cc.parent)+os.pathsep+env['PATH']
    compile_result = subprocess.run([str(args.cc),'-std=c99','-O2','-ffast-math','-Wall','-Wextra','-Werror',str(cfile),'-lm','-o',str(exe)],env=env,capture_output=True,text=True)
    (args.out/'compile.log').write_text(compile_result.stdout+compile_result.stderr)
    if compile_result.returncode:
        raise SystemExit(compile_result.returncode)
    result = subprocess.run([str(exe)],env=env,capture_output=True,text=True)
    (args.out/'result.log').write_text(result.stdout+result.stderr)
    print(result.stdout,end='')
    if result.stderr:
        print(result.stderr,end='')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
