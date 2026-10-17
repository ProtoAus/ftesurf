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
#ifndef min
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#endif
static void PM_PortalCSGReport(int ent,int plane,float miss){(void)ent;(void)plane;(void)miss;}
'''
# The world for PM_CarveExitRest's rest trace: open, or a face at x = stub_wall_x
# that the hull's front (+16) meets.
STUB = r'''
static float stub_wall_x=1e9f;
trace_t PM_PlayerTrace(vec3_t s,vec3_t e,unsigned int mask) {
 trace_t t;(void)mask;memset(&t,0,sizeof(t));t.fraction=1;t.entnum=-1;VectorCopy(e,t.endpos);
 if (s[0]+16<=stub_wall_x&&e[0]+16>stub_wall_x){
  t.fraction=(stub_wall_x-16-1/32.f-s[0])/(e[0]-s[0]);VectorInterpolate(s,t.fraction,e,t.endpos);
  t.plane.normal[0]=-1;t.entnum=0;}
 return t;
}
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
 // Patch 756, mover 5: a trace that starts in the wall behind an exit keeps the
 // sill. Feet 1/32 above the bottom edge (z -128), centre 3 in front of the plane.
 {
  vec3_t s={3,0,-128+1/32.f},e={3,0,-128+1/32.f-2};
  movevars.sourceversion=5;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);
  int sill_ground_ok=!t.allsolid&&t.fraction==0&&t.plane.normal[2]>.99f;assert(sill_ground_ok);checks++;
  e[0]=6;e[2]=s[2];memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);
  assert(!t.allsolid&&t.fraction==1);checks++;  // the walk out is still carved
  e[2]=s[2]-.2f;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);
  assert(t.fraction==0&&t.plane.normal[2]>.99f);checks++;  // falling stops on the sill
  e[0]=3;e[2]=s[2]-2;movevars.sourceversion=4;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);
  assert(t.fraction==1);checks++;  // mover 4 replays carve the sill away, as recorded
  // A tilted door's bottom edge is not a floor: mover 5 sweeps it as mover 4 did.
  // Box centre 3 in front and 40 above the bottom edge; the feet corner (along the
  // door's up) starts 7.8 above the edge and the trace sinks 20 along up.
  physent_t q=p;q.angles[0]=50;vec3_t qf,qr,qu,qs,qe;AngleVectors(q.angles,qf,qr,qu);
  for(int k=0;k<3;k++){qs[k]=3*qf[k]-88*qu[k];qe[k]=qs[k]-20*qu[k];}
  qs[2]-=31;qe[2]-=31;  // the trace moves the feet origin, 31 under the box centre
  movevars.sourceversion=5;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&q,1,pmove.player_mins,pmove.player_maxs,qs,qe,&t);float tilted5=t.fraction;
  movevars.sourceversion=4;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&q,1,pmove.player_mins,pmove.player_maxs,qs,qe,&t);
  int tilted_unchanged_ok=tilted5==t.fraction;assert(tilted_unchanged_ok);checks++;
 }
 // Patch 758, mover 6: a hop leaving an exit with the hull's back still in the wall
 // stopped dead where the back clears the plane (centre x 16.09). Mover 6 carries on.
 {
  vec3_t s={3,0,0},e={20,0,0};float f0;
  movevars.sourceversion=5;pm_carveexit_frac=-1;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);f0=t.fraction;
  assert(fabs(t.endpos[0]-16.09375f)<.001f&&t.plane.normal[0]<-.99f);checks++;  // where the hop stopped
  t=PM_CarveExitRest(t,s,e,0);assert(t.fraction==f0);checks++;                  // mover 5 still stops there
  movevars.sourceversion=6;pm_carveexit_frac=-1;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);assert(t.fraction==f0);checks++;
  t=PM_CarveExitRest(t,s,e,0);
  int carveexit_ok=t.fraction==1&&t.endpos[0]==20;assert(carveexit_ok);checks++;
  // The rest is a real trace: a face 25 units on (centre 25 - 1/32) still stops it.
  e[0]=40;stub_wall_x=41;pm_carveexit_frac=-1;memset(&t,0,sizeof(t));t.startsolid=t.allsolid=1;
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,s,e,&t);t=PM_CarveExitRest(t,s,e,0);
  int obstacle_ok=fabs(t.endpos[0]-(25-1/32.f))<.001f&&fabs(t.fraction-(25-1/32.f-3)/37)<1e-5f&&t.plane.normal[0]<-.99f;
  assert(obstacle_ok);checks++;stub_wall_x=1e9f;
  // Leaving through a SIDE plane is still a wall under mover 6 (the glancing case).
  vec3_t gs={17,55,0},ge={-28,100,0};pm_carveexit_frac=-1;t=Impact(gs,ge);
  PM_PortalCSG(&p,1,pmove.player_mins,pmove.player_maxs,gs,ge,&t);
  assert(t.fraction<.25f&&pm_carveexit_frac<0);checks++;
 }
 printf("PASS %d actual CSG/posture checks; glancing wall, departure, sill, stale eye, mover-5 sill sweep, mover-6 carve exit\n",checks);
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
    tst = (e/'common/pmovetst.c').read_text()
    csg = function(tst, 'static void PM_PortalCSG(')
    statics = re.search(r'^static float pm_carveexit_frac = -1;[^\n]*\n(?:static [^\n]*\n){2}', tst, re.M)
    assert statics, 'pm_carveexit statics'
    rest = function(tst, 'static trace_t PM_CarveExitRest(')
    code = PREFIX + TYPES
    for signature in ['void QDECL VectorAngles(', 'void QDECL AngleVectors (']:
        code += function(math, signature)
    for name in ['PMSRC_DUCK_TIMER', 'PMSRC_TIME_TO_DUCK', 'PMSRC_TIME_TO_UNDUCK', 'PMSRC_VIEWHEIGHT_DEFAULT', 'PMSRC_DUCKVIEWHEIGHT_DEFAULT']:
        m = re.search(r'^#define\s+'+name+r'\b[^\n]*', source, re.M)
        assert m, name
        code += m.group()+'\n'
    for name in ['PMSrc_SimpleSpline', 'PMSrc_ViewHeight', 'PMSrc_DuckViewHeight', 'PMSrc_DuckFraction', 'PMSrc_SetDuckedEyeOffset']:
        code += named(source, name)
    code += statics.group() + csg + STUB + rest + TEST
    a.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(Path(a.cc).parent)+os.pathsep+env.get('PATH','')
    for arm in ['subject','negative','negative_back','negative_sill','negative_upright','negative_carveexit']:
        armcode = code
        if arm == 'negative_carveexit':
            flag = '\t\t\t\tpm_carveexit_frac = bestfrac;\n'
            assert armcode.count(flag) == 1
            armcode = armcode.replace(flag, '')
        if arm == 'negative_upright':
            assert ' && planes[5][2] >= 0.7f)' in armcode
            armcode = armcode.replace(' && planes[5][2] >= 0.7f)', ')')
        if arm == 'negative_sill':
            begin = armcode.index('\tif (linked && movevars.sourceversion >= 5 && planes[5][2] >= 0.7f)\n\t{\n\t\tfloat ds = DotProduct(start, planes[6])')
            end = armcode.index('\n\t}\n', begin)+3
            armcode = armcode[:begin]+armcode[end:]
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
        elif arm == 'negative_sill':
            assert p.returncode != 0 and b'sill_ground_ok' in p.stderr, p.stdout+p.stderr
            print('PASS pre-756 control carves the sill away and fails sill_ground_ok')
        elif arm == 'negative_carveexit':
            assert p.returncode != 0 and b'carveexit_ok' in p.stderr, p.stdout+p.stderr
            print('PASS pre-758 control stops where the hull clears the exit and fails carveexit_ok')
        elif arm == 'negative_upright':
            assert p.returncode != 0 and b'tilted_unchanged_ok' in p.stderr, p.stdout+p.stderr
            print('PASS control without the upright gate changes a tilted door and fails tilted_unchanged_ok')
        else:
            assert p.returncode != 0, 'pre-fix CSG control unexpectedly passed'
            print('PASS '+('pre-fix unconditional-carve control fails glancing-wall assertion' if arm == 'negative' else 'pre-fix symmetric-carve control fails back-side wall assertion'))
    print('PASS tick derives current eye after duck and before portal-aware movement')


if __name__ == '__main__':
    main()
