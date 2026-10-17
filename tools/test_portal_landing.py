#!/usr/bin/env python3
"""Actual native linked-portal landing (Patch 756), no game/deployment/data access.

Compiles the engine's real PM_PortalTransform, PM_PlayerTracePortals and
SV_PMSrcVer with a C copy of sh_portal.qc's door transform for surf_kitsune's
portal_hub_exit -> portal_s1_entry. A walker settled on the hub floor (feet
96.03125, 1/32 above it) must arrive 1/32 above stage 1's floor (816.03125) under
mover 5; mover 4 keeps its 1/8 snap, which put the feet exactly on the sill
(816.0) and stalled the player. Two acting controls restore the snap at each
site. --out must be under an already-owned task root.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
from test_portals import PREFIX, function

TYPES = r'''
typedef struct {vec3_t normal;float dist;} plane_t;
typedef struct {float fraction;int startsolid,allsolid,entnum;vec3_t endpos;plane_t plane;} trace_t;
typedef struct {vec3_t origin,angles;float portalhalf[2];int info,isportal;} physent_t;
typedef struct {int camera_transform;} extvars_t;
typedef struct {extvars_t *xv;} wedict_t;
typedef struct {int unused;} pubprogfuncs_t;
typedef struct {pubprogfuncs_t *progs;struct {int *self;float *v_forward,*v_right,*v_up;} g;} world_t;
static struct {int physicsmode,sourceversion;} movevars;
static struct {vec3_t player_mins,player_maxs,portaloffset,angles,velocity,gravitydir;float viewheight;world_t *world;physent_t physents[2];} pmove;
#define PHYSMODE_SOURCE 42
#define PR_CURRENT 0
#define OFS_RETURN 1
#define OFS_PARM0 4
#define OFS_PARM1 7
#define MASK_PLAYERSOLID 1
#define nanmask (255u<<23)
#define VectorCopy(a,b) memcpy((b),(a),sizeof(vec3_t))
#define VectorAdd(a,b,o) do {int k;for(k=0;k<3;k++)(o)[k]=(a)[k]+(b)[k];}while(0)
#define VectorSubtract(a,b,o) do {int k;for(k=0;k<3;k++)(o)[k]=(a)[k]-(b)[k];}while(0)
#define max(a,b) ((a)>(b)?(a):(b))
static float globals[16];static int selfglobal;static vec3_t gfwd,grt,gup;
static pubprogfuncs_t progs;static extvars_t xv={1};static wedict_t door={&xv};
static world_t world={&progs,{&selfglobal,gfwd,grt,gup}};
#define WEDICT_NUM_UB(p,n) (&door)
#define EDICT_TO_PROG(p,e) 1
#define PR_globals(p,c) ((void*)globals)
#define G_VECTOR(o) (&((float*)pr_globals)[o])
static void Con_DPrintf(const char *f,...){(void)f;}
static void Sys_Error(const char *f,...){(void)f;abort();}
'''

# sh_portal.qc's FS_PortalRotate/FS_PortalWarp/FS_PortalTransform, in float like QC.
DOOR = r'''
static vec3_t fa,ra,ua,fb,rb,ub,oa,ob;
static void Rotate(const float *d,vec3_t o){
 float f=-DotProduct(d,fa),r=-DotProduct(d,ra),u=DotProduct(d,ua);int k;
 for(k=0;k<3;k++)o[k]=f*fb[k]+r*rb[k]+u*ub[k];
}
static void PR_ExecuteProgram(pubprogfuncs_t *p,int fn){
 float *g=globals;vec3_t f,r,u,rel,o;int k;(void)p;(void)fn;
 Rotate(gfwd,f);Rotate(grt,r);Rotate(gup,u);VectorCopy(f,gfwd);VectorCopy(r,grt);VectorCopy(u,gup);
 VectorSubtract(&g[OFS_PARM0],oa,rel);Rotate(rel,o);
 for(k=0;k<3;k++)g[OFS_RETURN+k]=ob[k]+o[k]+fb[k]*1;  // LPD_EXITNUDGE
}
static vec3_t tested;
static qboolean PM_TestPlayerPosition(vec3_t pos,qboolean ignoreportals){(void)ignoreportals;VectorCopy(pos,tested);return 1;}
static int traces;
static trace_t PM_PlayerTrace(vec3_t start,vec3_t end,unsigned int mask){
 trace_t t;int k;(void)mask;memset(&t,0,sizeof(t));
 if(!traces++){t.fraction=(-536.25f-start[1])/(end[1]-start[1]);t.entnum=1;  // hull face meets the 0.25-deep door box
  for(k=0;k<3;k++)t.endpos[k]=start[k]+t.fraction*(end[k]-start[k]);}
 else{t.fraction=1;t.entnum=-1;VectorCopy(end,t.endpos);}
 return t;
}
'''

TEST = r'''
static int checks;
static void Setup(int version){
 vec3_t ang={0,270,0},bng={0,90,0};
 movevars.physicsmode=PHYSMODE_SOURCE;movevars.sourceversion=version;
 AngleVectors(ang,fa,ra,ua);AngleVectors(bng,fb,rb,ub);
 oa[0]=0;oa[1]=-520;oa[2]=184;ob[0]=-15360;ob[1]=-15352;ob[2]=904;
 memset(&pmove,0,sizeof(pmove));
 pmove.player_mins[0]=pmove.player_mins[1]=-16;pmove.player_maxs[0]=pmove.player_maxs[1]=16;pmove.player_maxs[2]=62;
 pmove.viewheight=64;pmove.velocity[1]=250;pmove.world=&world;
 pmove.physents[1].origin[1]=-520;pmove.physents[1].origin[2]=184;pmove.physents[1].angles[1]=270;
 pmove.physents[1].portalhalf[0]=pmove.physents[1].portalhalf[1]=88;pmove.physents[1].info=1;pmove.physents[1].isportal=1;
 traces=0;
}
int main(void){
 vec3_t org,move,ang,vel,eye,start={0,-560,96.03125f},end={0,-500,96.03125f};trace_t t;float took;
 // The hub floor is z 96 and stage 1's is 816: a settled walker is 1/32 above both.
 Setup(5);org[0]=0;org[1]=-536.25f;org[2]=96.03125f;move[0]=move[2]=0;move[1]=36.25f;
 assert(PM_PortalTransform(&world,&pmove.physents[1],org,move,ang,vel,eye));
 // The hull centre lands as far behind the exit plane as it stopped in front of
 // the entry box (less the 1-unit nudge); the move remainder carries it out.
 int transform_exact_ok=org[2]==816.03125f&&fabs(org[0]+15360)<.01f&&fabs(org[1]+15367.25f)<.01f;
 assert(transform_exact_ok);checks++;
 Setup(4);org[0]=0;org[1]=-536.25f;org[2]=96.03125f;move[1]=36.25f;
 assert(PM_PortalTransform(&world,&pmove.physents[1],org,move,ang,vel,eye));
 assert(org[2]==816.0f&&org[0]*8==floor(org[0]*8)&&org[1]*8==floor(org[1]*8));checks++;  // v4 replays keep the snap
 Setup(5);t=PM_PlayerTracePortals(start,end,MASK_PLAYERSOLID,&took);
 int trace_exact_ok=traces==2&&took>0&&t.endpos[2]==816.03125f&&t.endpos[1]>-15352;
 assert(trace_exact_ok);checks++;
 // PM_PlayerTracePortals writes the far-side end back into its argument.
 end[0]=0;end[1]=-500;end[2]=96.03125f;
 Setup(4);t=PM_PlayerTracePortals(start,end,MASK_PLAYERSOLID,&took);
 assert(traces==2&&took>0&&t.endpos[2]==816.0f);checks++;
 // Recordings pinned to movers 4-7 are ones this verifier has; 8 is not (Patch 764 added 7).
 float pin[SV_PMPIN_COUNT];memset(pin,0,sizeof(pin));pin[SV_PMPIN_FIXRAMPBUGS]=2;
 pin[0]=6;assert(SV_PMSrcVer(pin)==6);pin[0]=5;assert(SV_PMSrcVer(pin)==5);pin[0]=4;assert(SV_PMSrcVer(pin)==4);pin[0]=7;assert(SV_PMSrcVer(pin)==7);pin[0]=8;assert(SV_PMSrcVer(pin)!=8);checks+=5;
 printf("PASS %d actual landing checks: mover 5 lands 1/32 above the exit floor, mover 4 keeps the 1/8 snap\n",checks);
 return 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    a = ap.parse_args()
    e = a.engine/'engine'
    math = (e/'common/mathlib.c').read_text()
    pm = (e/'common/pmove.c').read_text()
    user = (e/'server/sv_user.c').read_text()
    header = (e/'server/server.h').read_text()
    code = PREFIX + TYPES
    for name in ['SV_PMPIN_COUNT', 'SV_PMPIN_FIXRAMPBUGS']:
        m = re.search(r'^#define\s+'+name+r'\b[^\n/]*', header, re.M)
        assert m, name
        code += m.group()+'\n'
    code += '#define IS_NAN(x) (((*(unsigned *)&x)&nanmask)==nanmask)\n'
    for signature in ['void QDECL VectorAngles(', 'void QDECL AngleVectors (']:
        code += function(math, signature)
    code += DOOR
    names = user[user.index('const char *sv_pmpin_names[SV_PMPIN_COUNT]'):]
    code += names[:names.index('};')+2] + '\n'
    code += function(user, 'int SV_PMSrcVer(const float *pin)')
    code += function(pm, 'static qboolean PM_PortalTransform(')
    code += function(pm, 'trace_t	PM_PlayerTracePortals(').replace('trace_t	PM_PlayerTracePortals(', 'static trace_t PM_PlayerTracePortals(')
    code += TEST
    a.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(Path(a.cc).parent)+os.pathsep+env.get('PATH', '')
    controls = {
        'snap_transform': ('rounded[i] = exact ? G_VECTOR(OFS_RETURN)[i] - centre[i] : tmp/8.0;', 'rounded[i] = tmp/8.0; (void)exact;', 'transform_exact_ok'),
        'snap_trace': ('&& movevars.sourceversion >= 5 && impact->portalhalf[0] > 0))', '&& movevars.sourceversion >= 99 && impact->portalhalf[0] > 0))', 'trace_exact_ok'),
    }
    for arm in ['subject'] + list(controls):
        armcode = code
        if arm != 'subject':
            old, new, oracle = controls[arm]
            assert old in armcode, arm
            armcode = armcode.replace(old, new)
        src = a.out/('portal_landing_'+arm+'.c')
        src.write_text(armcode)
        exe = src.with_suffix('.exe')
        subprocess.run([a.cc, '-std=c99', '-O2', '-Wall', '-Werror', '-Wno-unused-function', '-fno-strict-aliasing', str(src), '-o', str(exe), '-lm'], env=env, check=True)
        p = subprocess.run([str(exe)], env=env, capture_output=True)
        (a.out/(arm+'.log')).write_bytes(p.stdout+p.stderr)
        if arm == 'subject':
            assert p.returncode == 0, p.stdout+p.stderr
            print(p.stdout.decode().strip())
        else:
            assert p.returncode != 0 and oracle.encode() in p.stderr, (arm, p.stdout+p.stderr)
            print(f'PASS control {arm} restores the 1/8 snap and fails {oracle}')


if __name__ == '__main__':
    main()
