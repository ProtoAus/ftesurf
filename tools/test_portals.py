#!/usr/bin/env python3
"""Compile actual portal-angle helpers with actual engine angle math.

Requires --engine (paired checkout) and --out (an owned task-root subdirectory).
No deployment, installed configs, player data, or runtime processes are touched.
The Euler-control arm must fail to produce the expected upside-down view.
"""
import argparse
import os
from pathlib import Path
import subprocess

PREFIX = r'''
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef float vec_t;
typedef float vec3_t[3];
typedef int qboolean;
#define false 0
#define true 1
#define QDECL
#define PITCH 0
#define YAW 1
#define ROLL 2
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#define PRED_SNAP_TOL 1.05
#define DotProduct(a,b) ((a)[0]*(b)[0]+(a)[1]*(b)[1]+(a)[2]*(b)[2])
#define VectorScale(a,s,o) do {int k;for(k=0;k<3;k++)(o)[k]=(a)[k]*(s);}while(0)
#define VectorMA(a,s,b,o) do {int k;float v=(s);for(k=0;k<3;k++)(o)[k]=(a)[k]+v*(b)[k];}while(0)
static struct {float value;} r_meshpitch={1}, r_meshroll={1};
'''
TESTS = r'''
static int checks;
static void Near(float a,float b) {checks++;assert(fabs(a-b)<.0002);}
static void VNear(const vec3_t a,const vec3_t b) {int k;for(k=0;k<3;k++)Near(a[k],b[k]);}
static void Oracle(const vec3_t base,const vec3_t target,const vec3_t in,vec3_t f,vec3_t u) {
 vec3_t b[3],t[3],v[3];double m[3][3];int i,j,k;
 AngleVectors(base,b[0],b[1],b[2]);AngleVectors(target,t[0],t[1],t[2]);AngleVectors(in,v[0],v[1],v[2]);
 for(i=0;i<3;i++)for(j=0;j<3;j++){m[i][j]=0;for(k=0;k<3;k++)m[i][j]+=(double)t[k][i]*b[k][j];}
 for(i=0;i<3;i++){f[i]=u[i]=0;for(j=0;j<3;j++){f[i]+=m[i][j]*v[0][j];u[i]+=m[i][j]*v[2][j];}}
}
static unsigned seed=12345;
static float RandomAngle(void) {seed=seed*1664525u+1013904223u;return (seed%360000)*.001f;}
int main(void) {
 vec3_t base={0,0,0},target={0,0,180},live={20,0,0},out,f,u,ef,eu,back,alias;
 int i,k;
 PredAngCompose(base,target,live,out);AngleVectors(out,f,NULL,u);
 assert(f[2]>.3f);checks++;
 // Acting baseline: the previous component-addition implementation looks down,
 // rather than up, after this half turn when newer mouse pitch is present.
 for(k=0;k<3;k++)back[k]=live[k]+target[k]-base[k];
 AngleVectors(back,ef,NULL,NULL);assert(ef[2]<-.3f);checks++;
 puts("PASS Euler-control arm acts and fails the rigid flip invariant");
 for(i=0;i<3000;i++) {
  for(k=0;k<3;k++){base[k]=RandomAngle();target[k]=RandomAngle();live[k]=RandomAngle();}
  Oracle(base,target,live,ef,eu);PredAngCompose(base,target,live,out);AngleVectors(out,f,NULL,u);
  VNear(f,ef);VNear(u,eu);
  memcpy(alias,live,sizeof(alias));PredAngCompose(base,target,alias,alias);AngleVectors(alias,f,NULL,u);VNear(f,ef);VNear(u,eu);
  PredAngCompose(target,base,out,back);AngleVectors(back,f,NULL,u);AngleVectors(live,ef,NULL,eu);VNear(f,ef);VNear(u,eu);
 }
 {vec3_t a={90,30,20},b={90,210,200},c={0,0,0},d={0,0,180};
  assert(PredAngTargetClose(a,b,true));checks++;
  assert(!PredAngTargetClose(a,b,false));checks++;
  assert(!PredAngTargetClose(c,d,true));checks++;
  b[0]=89;assert(PredAngTargetClose(a,b,true));checks++;
 }
 printf("PASS %d portal-angle numeric checks (production helpers and math)\n",checks);
 return 0;
}
'''


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2] + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    a = ap.parse_args()
    e = a.engine / 'engine'
    math = (e/'common/mathlib.c').read_text()
    csqc = (e/'client/pr_csqc.c').read_text()
    code = PREFIX
    for signature in ['void QDECL VectorAngles(', 'void QDECL AngleVectors (']:
        code += function(math, signature)
    for signature in ['static float PredAngNorm(', 'static qboolean PredAngClose(', 'static void PredAngCompose(', 'static qboolean PredAngTargetClose(']:
        code += function(csqc, signature)
    code += TESTS
    a.out.mkdir(parents=True, exist_ok=True)
    source = a.out/'portal_math.c'
    source.write_text(code)
    exe = a.out/'portal_math.exe'
    env = dict(os.environ)
    env['PATH'] = str(Path(a.cc).parent) + os.pathsep + env.get('PATH', '')
    subprocess.run([a.cc, '-std=c99', '-O2', '-Wall', '-Werror', str(source), '-o', str(exe), '-lm'], env=env, check=True)
    subprocess.run([str(exe)], env=env, check=True)


if __name__ == '__main__':
    main()
