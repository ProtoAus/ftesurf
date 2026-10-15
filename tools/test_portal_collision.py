#!/usr/bin/env python3
"""Actual native portal CSG and posture regressions, no game/deployment/data access.

--out must be under an already-owned task root. Includes an acting pre-fix
control which must fail the glancing thin-wall invariant.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
from test_portals import PREFIX, function

TYPES = r'''
typedef float vec4_t[4];
typedef struct {vec3_t normal;float dist;} plane_t;
typedef struct {float fraction;int startsolid,allsolid,entnum;vec3_t endpos;plane_t plane;} trace_t;
typedef struct {vec3_t origin,angles,mins,maxs;float portalhalf[2];} physent_t;
static struct {int physicsmode,sourceversion;float viewheight,duckviewheight;} movevars;
static struct {vec3_t player_mins,player_maxs;int ducking,ducked,oldbuttons;float ducktime,viewheight;} pmove;
#define PHYSMODE_SOURCE 42
#define BUTTON_DUCK 8
#define VectorCopy(a,b) memcpy((b),(a),sizeof(vec3_t))
#define VectorNegate(a,b) VectorScale(a,-1,b)
#define VectorAdd(a,b,o) do {int k;for(k=0;k<3;k++)(o)[k]=(a)[k]+(b)[k];}while(0)
#define VectorSubtract(a,b,o) do {int k;for(k=0;k<3;k++)(o)[k]=(a)[k]-(b)[k];}while(0)
#define VectorInterpolate(a,s,b,o) do {int k;float v=(s);for(k=0;k<3;k++)(o)[k]=(a)[k]+v*((b)[k]-(a)[k]);}while(0)
static void PM_PortalCSGReport(int ent,int plane,float miss){(void)ent;(void)plane;(void)miss;}
'''
TEST = r'''
static int checks;
static trace_t Impact(vec3_t start,vec3_t end) {
 trace_t t;memset(&t,0,sizeof(t));t.fraction=(17-16.03125f)/45;
 VectorInterpolate(start,t.fraction,end,t.endpos);t.plane.normal[0]=1;return t;
}
int main(void) {
 physent_t p;trace_t t;vec3_t start={17,55,0},end={-28,100,0};float prior;
 memset(&p,0,sizeof(p));p.mins[0]=-.25f;p.maxs[0]=.25f;p.mins[1]=-64;p.maxs[1]=64;p.mins[2]=-128;p.maxs[2]=128;p.portalhalf[0]=64;p.portalhalf[1]=128;
 pmove.player_mins[0]=pmove.player_mins[1]=-16;pmove.player_maxs[0]=pmove.player_maxs[1]=16;pmove.player_maxs[2]=62;
 movevars.physicsmode=PHYSMODE_SOURCE;movevars.sourceversion=4;
 // The centre crosses x=0 at y=72, OUTSIDE this opening. The swept hull
 // must stop at the aperture border rather than pass through the thin wall.
 t=Impact(start,end);PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);
 assert(t.fraction<.25f);assert(t.endpos[0]>-4);assert(fabs(t.endpos[1]-64)<.05);assert(t.entnum==0);checks+=4;
 // A centred crossing may reach the centre plane; traversal is separate.
 start[1]=end[1]=0;t=Impact(start,end);PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);
 assert(t.fraction>17.0f/45);assert(t.entnum==0);checks+=2;
 // Point probes and outward departure must stay carved while the hull overlaps.
 start[0]=1;end[0]=10;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
 PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);
 assert(!t.startsolid&&!t.allsolid);assert(t.fraction==1);checks+=2;
 end[0]=start[0];memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
 PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);
 assert(!t.allsolid);checks++;
 // A back-side approach must retain the wall, not cross it without a warp.
 start[0]=-17;end[0]=-11;memset(&t,0,sizeof(t));t.fraction=(17-16.03125f)/6;
 VectorInterpolate(start,t.fraction,end,t.endpos);t.plane.normal[0]=-1;prior=t.fraction;
 PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);assert(t.fraction==prior);checks++;
 start[0]=end[0]=-1;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
 PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);assert(t.startsolid&&t.allsolid);checks++;
 // Outside the rectangle and below its physical sill still means solid wall.
 start[0]=17;end[0]=-28;start[1]=end[1]=100;t=Impact(start,end);prior=t.fraction;
 PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);assert(t.fraction==prior);checks++;
 start[1]=end[1]=0;start[2]=end[2]=-130;t=Impact(start,end);prior=t.fraction;
 PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,start,end,&t);assert(t.fraction==prior);checks++;
 // Current posture, not the output left by a preceding ducked/standing mover.
 movevars.viewheight=64;movevars.duckviewheight=47;pmove.ducked=pmove.ducking=0;
 pmove.viewheight=47;assert(pmove.viewheight!=64);checks++; // acting stale-output control
 PMSrc_SetDuckedEyeOffset(PMSrc_DuckFraction());assert(pmove.viewheight==64);checks++;
 pmove.ducked=1;pmove.viewheight=64;PMSrc_SetDuckedEyeOffset(PMSrc_DuckFraction());assert(pmove.viewheight==47);checks++;
 pmove.ducked=0;pmove.viewheight=123;PMSrc_SetDuckedEyeOffset(PMSrc_DuckFraction());assert(pmove.viewheight==64);checks++;
 printf("PASS %d actual CSG/posture checks; glancing wall, departure, sill, stale eye\n",checks);
 return 0;
}
'''


def named(text, name):
    m = re.search(r'^(?:static\s+)?(?:float|void)\s+' + name + r'\s*\(', text, re.M)
    assert m, name
    return function(text, m.group())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    a = ap.parse_args()
    e = a.engine/'engine'
    math = (e/'common/mathlib.c').read_text()
    source = (e/'common/pm_source.c').read_text()
    tick = function(source, 'static void PMSrc_Tick (void)')
    assert tick.index('PMSrc_Duck ();') < tick.index('PMSrc_SetDuckedEyeOffset(PMSrc_DuckFraction())') < tick.index('PMSrc_LadderMove (NULL)')
    csg = function((e/'common/pmovetst.c').read_text(), 'static void PM_PortalCSG(')
    code = PREFIX + TYPES
    for signature in ['void QDECL VectorAngles(', 'void QDECL AngleVectors (']:
        code += function(math, signature)
    for name in ['PMSRC_DUCK_TIMER', 'PMSRC_TIME_TO_DUCK', 'PMSRC_TIME_TO_UNDUCK', 'PMSRC_VIEWHEIGHT_DEFAULT', 'PMSRC_DUCKVIEWHEIGHT_DEFAULT']:
        m = re.search(r'^#define\s+'+name+r'\b[^\n]*', source, re.M)
        assert m, name
        code += m.group()+'\n'
    for name in ['PMSrc_SimpleSpline', 'PMSrc_ViewHeight', 'PMSrc_DuckViewHeight', 'PMSrc_DuckFraction', 'PMSrc_SetDuckedEyeOffset']:
        code += named(source, name)
    code += csg + TEST
    a.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(Path(a.cc).parent)+os.pathsep+env.get('PATH','')
    for arm in ['subject','negative','negative_back']:
        armcode = code
        if arm == 'negative_back':
            begin = armcode.index('\t\tvec3_t approach;')
            end = armcode.index('\t\thwidth = portal->portalhalf[0];',begin)
            armcode = armcode[:begin]+armcode[end:]
        if arm == 'negative':
            begin = armcode.index('\t\t\t// Keep the swept boundary:')
            end = armcode.index('\n\t\t}',begin)
            armcode = armcode[:begin]+'\t\t\ttrace->fraction=1; VectorCopy(end,trace->endpos);'+armcode[end:]
        src = a.out/('portal_collision_'+arm+'.c')
        src.write_text(armcode)
        exe = src.with_suffix('.exe')
        subprocess.run([a.cc,'-std=c99','-O2','-Wall','-Werror',str(src),'-o',str(exe),'-lm'],env=env,check=True)
        p = subprocess.run([str(exe)],env=env,capture_output=True)
        (a.out/(arm+'.log')).write_bytes(p.stdout+p.stderr)
        if arm == 'subject':
            assert p.returncode == 0, p.stdout+p.stderr
            print(p.stdout.decode().strip())
        else:
            assert p.returncode != 0, 'pre-fix CSG control unexpectedly passed'
            print('PASS '+('pre-fix unconditional-carve control fails glancing-wall assertion' if arm == 'negative' else 'pre-fix symmetric-carve control fails back-side wall assertion'))
    print('PASS tick derives current eye after duck and before portal-aware movement')


if __name__ == '__main__':
    main()
