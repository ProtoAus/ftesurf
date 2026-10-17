#!/usr/bin/env python3
"""Mover 6's carve exit (Patch 758) through the REAL PM_PlayerTrace, no game/deployment/data access.

Compiles the engine's PM_PortalCSG, PM_CarveExitRest and PM_PlayerTrace over a box-brush world
with BIH's startsolid/allsolid semantics (a brush containing the start sets startsolid and is
otherwise ignored), and PMSrc_TryPlayerMove's bump arithmetic.  The world and the non-upright
cases are the P758 cheater review's harness.  --out must be under an already-owned task root.
Two acting controls: without the startsolid fallback a non-upright exit carries the hull
through a wall; restarting from the stop instead of 1/32 clear of the carve stops in the band.
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
typedef struct {int loadstate;} model_t;
#define MLS_LOADED 2
typedef struct {vec3_t origin,angles,mins,maxs;float portalhalf[2];int nonsolid,info,isportal;unsigned forcecontentsmask;model_t *model;float scale;} physent_t;
static struct {int physicsmode,sourceversion;} movevars;
static struct {vec3_t player_mins,player_maxs;int numphysent;physent_t physents[8];int skipent;} pmove;
static struct {int ival;} pm_skipent_portals={1}, pm_portalcsg_scanall={1};
#define PE_FRAMESTATE NULL
#define MASK_PLAYERSOLID 1
#define PHYSMODE_SOURCE 42
#define DIST_EPSILON (0.03125f)
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
static void PM_HullForBox(vec3_t a,vec3_t b){(void)a;(void)b;}
typedef struct {vec3_t mn,mx;} brush_t;
static brush_t brushes[8];static int nbrushes;
static int nhs;static float hsn[4][3],hsd[4];
static model_t worldmodel={MLS_LOADED};
static vec3_t vec3_origin;
static int PM_TransformedHullCheck(model_t *model,void *fs,vec3_t start,vec3_t end,vec3_t mins,vec3_t maxs,trace_t *tr,vec3_t origin,vec3_t angles,float scale)
{
 int b,i;(void)fs;(void)origin;(void)angles;(void)scale;
 if (model!=&worldmodel) return 0;
 memset(tr,0,sizeof(*tr));tr->fraction=1;
 for (i=0;i<nhs;i++){	// half-spaces n.p <= d, for sloped faces (round 3's harness)
  float smin=0,d1,d2,f;int k;for(k=0;k<3;k++)smin+=hsn[i][k]*(hsn[i][k]>=0?mins[k]:maxs[k]);
  d1=DotProduct(hsn[i],start)+smin-hsd[i];d2=DotProduct(hsn[i],end)+smin-hsd[i];
  if(d1<=0){tr->startsolid=1;if(d2<=0)tr->allsolid=1;continue;}
  if(d2>=0)continue;f=(d1-DIST_EPSILON)/(d1-d2);if(f<0)f=0;
  if(f<tr->fraction){tr->fraction=f;memset(&tr->plane,0,sizeof(tr->plane));VectorCopy(hsn[i],tr->plane.normal);tr->plane.dist=hsd[i];}
 }
 for (b=0;b<nbrushes;b++){
  float enterfrac=-1,leavefrac=2,nearfrac=0;int getout=0,startout=0,clip=-1;
  for (i=0;i<6;i++){
   int ax=i%3;float sgn=i<3?1:-1,dist,d1,d2,f;
   dist=i<3?brushes[b].mx[ax]-mins[ax]:-(brushes[b].mn[ax]-maxs[ax]);
   d1=sgn*start[ax]-dist;d2=sgn*end[ax]-dist;
   if(d2>0)getout=1; if(d1>0)startout=1;
   if(d1>0&&(d2>=DIST_EPSILON||d2>=d1)){clip=-2;break;}	// in front of a face: no hit (com_bih.c, round 4)
   if(d1<=0&&d2<=0)continue;
   if(d1>d2){f=d1/(d1-d2);if(f>enterfrac){enterfrac=f;nearfrac=(d1-DIST_EPSILON)/(d1-d2);clip=i;}}
   else{f=d1/(d1-d2);if(f<leavefrac)leavefrac=f;}
  }
  if(clip==-2)continue;
  if(!startout){tr->startsolid=1;if(!getout)tr->allsolid=1;continue;}
  if(enterfrac<=leavefrac&&enterfrac>-1&&nearfrac<tr->fraction){
   if(nearfrac<0)nearfrac=0;tr->fraction=nearfrac;memset(&tr->plane,0,sizeof(tr->plane));
   tr->plane.normal[clip%3]=clip<3?1:-1;}
 }
 if(tr->fraction==1)VectorCopy(end,tr->endpos);else VectorInterpolate(start,tr->fraction,end,tr->endpos);
 return 1;
}
trace_t PM_PlayerTrace (vec3_t start, vec3_t end, unsigned int solidmask);
'''

TEST = r'''
static int checks, laundered;
static int Free(vec3_t p){trace_t t;PM_TransformedHullCheck(&worldmodel,0,p,p,pmove.player_mins,pmove.player_maxs,&t,0,0,1);return !t.startsolid&&!t.allsolid;}
// PMSrc_TryPlayerMove's bump arithmetic (pm_source.c): bump 0 moves to any endpos with fraction > 0.
static void Bumps(vec3_t org,vec3_t vel,float dt){
 float time_left=dt;int bump;
 for(bump=0;bump<4;bump++){
  vec3_t end;trace_t pm;VectorMA(org,time_left,vel,end);pm=PM_PlayerTrace(org,end,1);
  if(pm.startsolid&&pm.fraction>0)laundered++;
  if(bump&&(pm.startsolid||pm.allsolid))break;
  if(pm.fraction>0) VectorCopy(pm.endpos,org);
  if(pm.fraction==1)break;
  time_left-=time_left*pm.fraction;
  {float d=DotProduct(vel,pm.plane.normal);int k;if(d<0)for(k=0;k<3;k++)vel[k]-=pm.plane.normal[k]*d;}
 }
}
static void Door(float pitch,vec3_t o,float hw,float hh){
 physent_t *p=&pmove.physents[1];memset(p,0,sizeof(*p));p->isportal=1;p->info=1;p->scale=1;
 p->angles[0]=pitch;VectorCopy(o,p->origin);p->portalhalf[0]=hw;p->portalhalf[1]=hh;
}
static void Setup(int v){
 memset(&pmove,0,sizeof(pmove));pmove.skipent=-1;pmove.numphysent=2;
 pmove.physents[0].model=&worldmodel;pmove.physents[0].scale=1;
 pmove.player_mins[0]=pmove.player_mins[1]=-16;pmove.player_maxs[0]=pmove.player_maxs[1]=16;pmove.player_maxs[2]=72;
 movevars.physicsmode=PHYSMODE_SOURCE;movevars.sourceversion=v;nbrushes=0;nhs=0;
}
static void Brush(float a,float b,float c,float d,float e,float f){
 brush_t *x=&brushes[nbrushes++];x->mn[0]=a;x->mn[1]=b;x->mn[2]=c;x->mx[0]=d;x->mx[1]=e;x->mx[2]=f;}
// PMSrc_TryPlayerMove's shape with its validity retests, half gravity either side (round 2's harness).
static void Clip(vec3_t in,vec3_t n,vec3_t out){float b=DotProduct(in,n),adj;int k;for(k=0;k<3;k++)out[k]=in[k]-n[k]*b;adj=DotProduct(out,n);if(adj<0)for(k=0;k<3;k++)out[k]-=adj*n[k];}
static void Tick(vec3_t org,vec3_t vel,float dt){
 float time_left=dt;int bump;
 vel[2]-=400*dt;
 for(bump=0;bump<4;bump++){
  vec3_t end;trace_t pm;
  if(!vel[0]&&!vel[1]&&!vel[2])break;
  VectorMA(org,time_left,vel,end);pm=PM_PlayerTrace(org,end,1);
  if(bump){trace_t st=PM_PlayerTrace(pm.endpos,pm.endpos,1);if(pm.startsolid||pm.allsolid||st.startsolid||st.fraction!=1)break;}
  if(pm.fraction>0){
   if(!bump&&pm.fraction==1){trace_t st=PM_PlayerTrace(pm.endpos,pm.endpos,1);if(st.startsolid||st.fraction!=1){vel[0]=vel[1]=vel[2]=0;break;}}
   VectorCopy(pm.endpos,org);
  }
  if(pm.fraction==1)break;
  time_left-=time_left*pm.fraction;
  Clip(vel,pm.plane.normal,vel);
 }
 vel[2]-=400*dt;
}
// A 16-thick corridor wall in front of an upright door (fwd +x, half-width 64), flush with its +y
// edge: exit from (16-r, y0) at (vn0, 3000), then +4 u/s forward on any tick that starts with none.
static int Trial(int v,float y0,float r,float vn0){
 vec3_t o={0,0,64},org,vel;int t;org[0]=16-r;org[1]=y0;org[2]=24;vel[0]=vn0;vel[1]=3000;vel[2]=0;
 Setup(v);Door(0,o,64,64);Brush(-32,-512,-512,0,512,512);Brush(-512,-512,-64,512,512,0);Brush(0,64,-64,512,80,512);
 for(t=0;t<4;t++){
  if(t&&vel[0]==0)vel[0]=4;
  Tick(org,vel,0.015f);
  if(org[1]-16>80&&Free(org))return 1;
 }
 return 0;
}
// An upright door (fwd +x) in a wall whose front face is at x=face; floor under it.
static trace_t Upright(int v,float face,float wall,vec3_t s,vec3_t e){
 vec3_t o={0,0,36};Setup(v);Door(0,o,88,88);Brush(-32,-512,-512,face,512,512);Brush(-512,-512,-64,512,512,0);
 if(wall)Brush(wall,-512,-512,wall+8,512,512);
 return PM_PlayerTrace(s,e,1);
}
int main(void){
 trace_t t;int v;
 // Non-upright exits (review round 1's exploit): a rest that starts in solid keeps the stop.
 for(v=5;v<=6;v++){
  vec3_t o={0,0,256},vel={-3500,0,-1000},s={-47.95f,0,186};
  // ceiling exit (pitch 90), a 2-thick shaft wall flush with its bottom edge, 3500 u/s at it
  static vec3_t fin[2][4];
  Setup(v);Door(90,o,64,64);Brush(-512,-512,256,512,512,288);Brush(-66,-512,-512,-64,512,256);
  Bumps(s,vel,0.015f);VectorCopy(s,fin[v-5][0]);
  // recessed floor exit (pitch -90, floor 0.5 above the plane) leaving sideways
  {vec3_t s2={47.9f,0,-3},v2={1500,0,600},o2={0,0,0};Setup(v);Door(-90,o2,64,64);Brush(-512,-512,-64,512,512,0.5f);
   Bumps(s2,v2,0.015f);VectorCopy(s2,fin[v-5][1]);}
  // surf_4plar p3 as measured, rising 2500 with +x 600 toward the edge the feet gate tests
  {vec3_t s3={-8528.5f,13824,3067.5f},v3={600,0,2500},o3={-8704,13824,3087.5f};Setup(v);Door(-90,o3,192,192);
   Brush(-16384,-16384,3056,16384,16384,3088);Bumps(s3,v3,0.015f);VectorCopy(s3,fin[v-5][2]);}
  if(v==6){int k,same=1;for(k=0;k<3;k++)same&=!memcmp(fin[0][k],fin[1][k],sizeof(vec3_t));
   int nolaunder_ok=!laundered&&same;assert(nolaunder_ok);checks++;}
 }
 // A hop leaving an exit with the hull's back still in the wall stopped where the back
 // cleared the plane (x 16.09); mover 6 goes on.
 {vec3_t s={3,0,0.03125f},e={20,0,0.03125f};
  t=Upright(5,0,0,s,e);assert(fabs(t.endpos[0]-16.09375f)<.001f&&t.plane.normal[0]<-.99f);checks++;
  t=Upright(6,0,0,s,e);assert(t.fraction==1&&t.endpos[0]==20&&!t.startsolid);checks++;
  // A wall face inside the carve's 1/8 slop (enterable from the front) no longer stops it.
  t=Upright(6,.1f,0,s,e);int band_ok=t.fraction==1&&t.endpos[0]==20&&!t.startsolid;assert(band_ok);checks++;
  t=Upright(5,.1f,0,s,e);assert(t.fraction<1);checks++;
  // Past the slop the door cannot be entered from the front either: mover 5's stop, unlaundered.
  t=Upright(6,.25f,0,s,e);int slop_ok=t.fraction<1&&!t.startsolid;assert(slop_ok);checks++;
  // The rest is a real trace: a face 41 on stops the hull's front there.
  e[0]=40;t=Upright(6,0,41,s,e);assert(fabs(t.endpos[0]-(25-1/32.f))<.001f&&t.plane.normal[0]<-.99f&&!t.startsolid);checks++;}
 // Grazing exits (review round 2): restarting along the move skipped most of one, through a
 // jamb or a wall beside the door. Mover 6 keeps mover 5's result there.
 {
  static vec3_t g[2][2];
  for(v=5;v<=6;v++){
   vec3_t o={0,0,36},s={16.1f,80,0.03125f},vel={3,3500,0},s4={12.22f,56,0.03125f},v4={261,2100,0};
   // G1: an 8-deep jamb at the aperture's +y edge, a near-grazing step out of the carve
   Setup(v);Door(0,o,88,88);Brush(-32,-512,-512,0,512,512);Brush(-512,-512,-64,512,512,0);Brush(0,88,-512,8,96,512);
   Tick(s,vel,0.015f);VectorCopy(s,g[v-5][0]);
   // G4: the stop parks the hull in the carve beside the jamb; then one tick of +3 u/s forward
   Setup(v);Door(0,o,88,88);Brush(-32,-512,-512,0,512,512);Brush(-512,-512,-64,512,512,0);Brush(0,88,-512,8,96,512);
   Tick(s4,v4,0.015f);v4[0]+=3;Tick(s4,v4,0.015f);VectorCopy(s4,g[v-5][1]);
  }
  int jamb_ok=!memcmp(g[0],g[1],sizeof(g[0]));assert(jamb_ok);checks++;
  // G2: a wall face in the slop and a 2-thick partition beside the door: the rest stops at it.
  {vec3_t o={0,0,36},s={16.097f,70,0.03125f},vel={3,3500,0};
   Setup(6);Door(0,o,88,88);Brush(-32,-512,-512,0.1f,512,512);Brush(-512,-512,-64,512,512,0);Brush(0.1f,90,-512,64,92,512);
   Tick(s,vel,0.015f);int partition_ok=s[1]+16<=90&&Free(s);assert(partition_ok);checks++;}
  // A blocked rest is charged its own progress: endpos projected on the move, below 1
  // (a 45-degree exit stopped by a face 41 on, where the nudge runs partly along the move).
  {vec3_t s={3,0,0.03125f},e={40,37,0.03125f},m,p;float pr;
   t=Upright(6,0,41,s,e);VectorSubtract(e,s,m);VectorSubtract(t.endpos,s,p);pr=DotProduct(p,m)/DotProduct(m,m);
   int charge_ok=t.fraction<1&&fabs(t.fraction-pr)<1e-6f&&t.plane.normal[0]<-.99f;assert(charge_ok);checks++;}
  // Round 3: a blocked rest whose start projects past the end (under 1/16 forward left) on a
  // sloped face still reports a fraction below 1, so the mover clips this bump.
  {vec3_t o={0,0,31},s={15.99f,0,0},e={16.14f,0.05f,0};
   Setup(6);Door(0,o,64,128);nhs=2;hsn[0][0]=1;hsn[0][1]=hsn[0][2]=0;hsd[0]=0;
   hsn[1][0]=-0.6f;hsn[1][1]=-0.8f;hsn[1][2]=0;hsd[1]=-32.122614f;
   t=PM_PlayerTrace(s,e,1);int blocked_ok=t.fraction<1&&t.plane.normal[1]<-.7f;assert(blocked_ok);checks++;}
  // The corridor wall over 43,380 exit states a mover: none may get past it in four ticks.
  {int k[2]={0,0};float r,y0,vn0;
   for(v=5;v<=6;v++)for(vn0=81;vn0<=1300;vn0*=4)for(r=0.05f;r<=15;r+=0.25f)for(y0=-60;y0<=60;y0+=0.5f)k[v-5]+=Trial(v,y0,r,vn0);
   int grid_ok=!k[0]&&!k[1];if(!grid_ok)printf("corridor tunnels: mover 5 %d, mover 6 %d\n",k[0],k[1]);assert(grid_ok);checks++;}
 }
 printf("PASS %d carve-exit checks through the real PM_PlayerTrace: flush and band exits continue, past the slop and at an obstacle they stop, non-upright and grazing exits keep mover 5's stop\n",checks);
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
    tst = (e/'common/pmovetst.c').read_text()
    math = (e/'common/mathlib.c').read_text()
    statics = re.search(r'^static float pm_carveexit_frac = -1;[^\n]*\n(?:static [^\n]*\n){2}', tst, re.M)
    assert statics, 'pm_carveexit statics'
    code = PREFIX + TYPES
    for sig in ['void QDECL VectorAngles(', 'void QDECL AngleVectors (']:
        code += function(math, sig)
    code += statics.group() + function(tst, 'static void PM_PortalCSG(') + function(tst, 'static trace_t PM_CarveExitRest(')
    code += function(tst, 'trace_t PM_PlayerTrace (vec3_t start') + TEST
    a.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(Path(a.cc).parent)+os.pathsep+env.get('PATH', '')
    nudge = '\tVectorMA(total.endpos, 1/16.0, pm_carveexit_dir, from);\n'
    assert code.count(nudge) == 1
    # Round 1's restart: on the move's own line, as far as takes the hull 1/32 clear of the carve.
    online = ('\t{ vec3_t d; float kk; VectorSubtract(end, total.endpos, d); kk = DotProduct(d, pm_carveexit_dir);\n'
              '\t  kk = kk > 1/16.0 ? (1/16.0) / kk : 1; VectorMA(total.endpos, kk, d, from); }\n')
    charge = '\t\trest.fraction = mm > 0 ? min(nextafterf(1, 0), max(f, DotProduct(p, m) / mm)) : f;\n'
    assert code.count(charge) == 1
    for arm in ['subject', 'negative_launder', 'negative_band', 'negative_line', 'negative_clamp', 'negative_charge']:
        armcode = code
        if arm == 'negative_clamp':
            armcode = armcode.replace(charge, charge.replace('min(nextafterf(1, 0), ', 'min(1, '))
        if arm == 'negative_charge':
            armcode = armcode.replace(charge, '\t\trest.fraction = f + (1 - f) * rest.fraction;\n')
        if arm == 'negative_launder':
            cut = '\tif (rest.startsolid || rest.allsolid)\n\t\treturn total;\n'
            assert armcode.count(cut) == 1
            armcode = armcode.replace(cut, '')
        if arm == 'negative_band':
            armcode = armcode.replace(nudge, '\tVectorCopy(total.endpos, from);\n')
        if arm == 'negative_line':
            armcode = armcode.replace(nudge, online)
        src = a.out/('portal_carveexit_'+arm+'.c')
        src.write_text(armcode)
        exe = src.with_suffix('.exe')
        subprocess.run([a.cc, '-std=c99', '-O2', '-Wall', '-Wno-unused-function', '-Wno-unused-variable',
                        '-Wno-misleading-indentation', str(src), '-o', str(exe), '-lm'], env=env, check=True)
        p = subprocess.run([str(exe)], env=env, capture_output=True)
        (a.out/(arm+'.log')).write_bytes(p.stdout+p.stderr)
        if arm == 'subject':
            assert p.returncode == 0, p.stdout+p.stderr
            print(p.stdout.decode().strip())
        elif arm == 'negative_launder':
            assert p.returncode != 0 and b'nolaunder_ok' in p.stderr, p.stdout+p.stderr
            print('PASS control without the startsolid fallback carries a non-upright exit through a wall and fails nolaunder_ok')
        elif arm == 'negative_band':
            assert p.returncode != 0 and b'band_ok' in p.stderr, p.stdout+p.stderr
            print('PASS control restarting from the stop stays inside the slop and fails band_ok')
        elif arm == 'negative_clamp':
            assert p.returncode != 0 and b'blocked_ok' in p.stderr, p.stdout+p.stderr
            print('PASS control clamping the charge to 1 reports a blocked rest as a full move and fails blocked_ok')
        elif arm == 'negative_charge':
            assert p.returncode != 0 and b'charge_ok' in p.stderr, p.stdout+p.stderr
            print('PASS control charging f + (1-f) * rest misses the nudge and fails charge_ok')
        else:
            failed = next((n for n in (b'jamb_ok', b'partition_ok', b'grid_ok') if n in p.stderr), None)
            assert p.returncode != 0 and failed, p.stdout+p.stderr
            print('PASS control restarting along the move (review round 1) skips a grazing move and fails '
                  + failed.decode() + ' ' + p.stdout.decode().strip().replace('\r', ''))


if __name__ == '__main__':
    main()
