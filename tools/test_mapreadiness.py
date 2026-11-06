#!/usr/bin/env python3
"""Compile literal selected readiness source with deterministic resource/driver controls.
Not a renderer, residency or performance test. Keep outputs under an owned task root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

STUB = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <math.h>
#define QDECL
#define true 1
#define false 0
typedef int qboolean;
typedef uintptr_t quintptr_t;
#define MAX_QPATH 128
#define PERMUTATIONS 8
#define SHADER_PASS_MAX 2
#define MAX_PRECACHE_MODELS 3
#define MAX_CSMODELS 3
#define MAX_VWEP_MODELS 3
#define CVAR_ARCHIVE 0
#define CVARFD(n,v,f,d) {2,2}
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
/* selected engine bound macro inserted here */
#define ca_active 1
#define QR_OPENGL 1
#define MLS_NOTLOADED 0
#define MLS_LOADING 1
#define MLS_LOADED 2
#define MLS_FAILED 3
#define TEX_NOTLOADED 0
#define TEX_LOADING 1
#define TEX_LOADED 2
#define TEX_FAILED 3
#define IF_RENDERTARGET 1
#define LOADERTHREAD
static int locked;
static void *com_resourcemutex;
static void Sys_LockMutex(void *m) {(void)m; if(locked++)abort();}
static void Sys_UnlockMutex(void *m) {(void)m; if(--locked)abort();}
typedef struct {float value; int ival;} cvar_t;
static cvar_t r_glsl_warm={1,1};
typedef struct {int loadstate;} model_t;
typedef struct image_s {int regsequence,flags,status;struct image_s *next;} image_t;
static image_t *imagelist;
static int r_regsequence=1;
static struct {
 model_t *model_precache[3],*model_csqcprecache[3],*model_precache_vwep[3];
 char model_name[3][32],model_csqcname[3][32],model_name_vwep[3][32];
} cl;
typedef struct {const char *name;unsigned supportedpermutations;void *permu[8];} program_t;
typedef struct {int uses,numpasses;program_t *prog;struct {program_t *prog;} passes[2];} shader_t;
static shader_t **r_shaders;
static unsigned r_numshaders;
static int qrenderer=QR_OPENGL;
static int shader_reload_needed;
static int main_thread=1;
static int Sys_IsMainThread(void) {return main_thread;}
typedef struct {unsigned bits[1];} glslwarm_t;
static glslwarm_t history;
static int glslwarm_hash,glslwarm_mem=1;
static double now;
static int compile_calls,save_calls,pump_calls,complete_job,fail_compile;
static model_t loading_model;
static image_t loading_image;
static double Sys_DoubleTime(void) {return now;}
static void Sys_Sleep(double t) {now+=t;}
static void Con_Printf(const char *f,...) {(void)f;}
#define Con_DPrintf Con_Printf
static void Q_strncpyz(char *d,const char *s,size_t n) {snprintf(d,n,"%s",s);}
static void *Hash_Get(void *h,const char *s) {(void)h;return strcmp(s,"known")?NULL:&history;}
static void GLSLWarm_Load(void) {}
static void GLSLWarm_Save(void) {save_calls++;}
static void *Shader_LoadPermutation(program_t *p,unsigned n) {
 (void)p; compile_calls++;now+=.01;return fail_compile?NULL:(void *)(uintptr_t)(n+100);
}
static int COM_DoWork(int group,int lock) {
 (void)group;(void)lock;pump_calls++;
 if(complete_job) {loading_model.loadstate=MLS_LOADED;loading_image.status=TEX_LOADED;complete_job=0;return 1;}
 return 0;
}
'''
CASES = r'''
static int checks;
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"FAIL line %i: %s\n",__LINE__,#x);return 1;}}while(0)
int main(void) {
 program_t p={"known",3,{0}},p2={"known",3,{0}};
 shader_t s={1,2,&p,{{&p},{&p2}}};shader_t *shaders[]={&s,&s};
 image_t image={1,0,TEX_LOADED,NULL};
 p.permu[0]=(void *)1;p2.permu[0]=(void *)2;
 r_shaders=shaders;r_numshaders=2;imagelist=&image;
 // Four history values collapse to two supported permutations per unique program.
 history.bits[0]=(1u<<1)|(1u<<2)|(1u<<5)|(1u<<6);
 GLSLWarm_MapActive();
 CHECK(!strcmp(mapready.state,"ready-closure"));
 CHECK(mapready.programs==2 && mapready.eligible==4 && mapready.compiled==4);
 CHECK(compile_calls==4 && !mapready.pending && !mapready.failed);
 CHECK(save_calls==1 && mapready.images==1 && !locked);
 GLSLWarm_MapActive();
 CHECK(mapready.available==4 && mapready.compiled==0 && compile_calls==4);
 // Zero budget must ACT: two missing unique permutations, no compile attempted.
 p.permu[1]=p.permu[2]=NULL;r_mapready_budget.value=0;
 GLSLWarm_MapActive();
 CHECK(!strcmp(mapready.state,"incomplete") && mapready.budgethit);
 CHECK(mapready.pending==2 && mapready.available==2 && compile_calls==4);
 // A compile failure and an already-installed fallback cannot masquerade as ready.
 r_mapready_budget.value=2;fail_compile=1;
 GLSLWarm_MapActive();
 CHECK(mapready.failed==2 && mapready.compiled==0 && mapready.pending==0);
 CHECK(p.permu[1]==p.permu[0] && p.permu[2]==p.permu[0]);
 fail_compile=0;GLSLWarm_MapActive();CHECK(mapready.failed==2 && mapready.available==2);
 // Pending worker removed from its queue still has a loading resource state.
 p.permu[1]=(void *)101;p.permu[2]=(void *)102;
 strcpy(cl.model_name[0],"pending");cl.model_precache[0]=&loading_model;
 loading_model.loadstate=MLS_LOADING;loading_image=(image_t){1,0,TEX_LOADING,NULL};
 imagelist=&loading_image;complete_job=1;pump_calls=0;
 GLSLWarm_MapActive();
 CHECK(!strcmp(mapready.state,"ready-closure") && pump_calls==1);
 CHECK(mapready.models==1 && mapready.modelpending==0 && mapready.imagepending==0);
 // Nonprogressing work is bounded and leaves positive pending diagnostics.
 loading_model.loadstate=MLS_LOADING;loading_image.status=TEX_LOADING;
 r_mapready_budget.value=.003f;pump_calls=0;GLSLWarm_MapActive();
 CHECK(!strcmp(mapready.state,"incomplete") && mapready.budgethit);
 CHECK(mapready.modelpending==1 && mapready.imagepending==1 && pump_calls<=4);
 // Unrequested/failed resources are not ready, but must not burn the wait budget.
 loading_model.loadstate=MLS_NOTLOADED;loading_image.status=TEX_NOTLOADED;
 pump_calls=0;GLSLWarm_MapActive();
 CHECK(mapready.modelunrequested==1 && mapready.imageunrequested==1 && pump_calls==0);
 CHECK(!strcmp(mapready.state,"incomplete"));
 loading_model.loadstate=MLS_FAILED;loading_image.status=TEX_FAILED;
 GLSLWarm_MapActive();CHECK(mapready.modelfailed==1 && mapready.imagefailed==1);
 // Old registration and render-target allocations are outside the file-image closure.
 cl.model_name[0][0]=0;loading_image.regsequence=0;GLSLWarm_MapActive();
 CHECK(mapready.images==0 && !strcmp(mapready.state,"ready-closure"));
 loading_image.regsequence=1;loading_image.flags=IF_RENDERTARGET;GLSLWarm_MapActive();CHECK(mapready.images==0);
 // Disabled and unsupported are never ready. Late compile diagnostics do act.
 r_glsl_warm.ival=0;GLSLWarm_MapActive();CHECK(!strcmp(mapready.state,"disabled"));
 r_glsl_warm.ival=1;qrenderer=2;GLSLWarm_MapActive();CHECK(!strcmp(mapready.state,"unsupported"));
 qrenderer=QR_OPENGL;r_mapready_budget.value=2;GLSLWarm_MapActive();
 now+=.02;MapReady_Compiled(&p,2,now-.02,1);
 CHECK(mapready.latecompiles==1 && mapready.latefailed==1 && mapready.lateseconds>.019);
 CHECK(!strcmp(mapready.lastprogram,"known") && mapready.lastperm==2);
 mapready.warming=1;MapReady_Compiled(&p,1,now,0);CHECK(mapready.latecompiles==1);
 mapready.warming=0;GLSLWarm_MapActive();CHECK(mapready.latecompiles==0);
 {double start=R_MapReadyImageStart();now+=.01;R_MapReadyImageDone("late-image",start,0);}
 CHECK(mapready.lateimages==1 && !mapready.lateimagefailed && mapready.lateimageseconds>.009);
 main_thread=0;CHECK(R_MapReadyImageStart()<0);R_MapReadyImageDone("worker",now,1);CHECK(mapready.lateimages==1);
 main_thread=1;mapready.warming=1;CHECK(R_MapReadyImageStart()<0);mapready.warming=0;
 shader_reload_needed=1;GLSLWarm_MapActive();CHECK(mapready.invalidated && mapready.lateimages==0);
 p.permu[1]=NULL;r_mapready_budget.value=NAN;GLSLWarm_MapActive();
 CHECK(mapready.pending==1 && mapready.budgethit && !isnan(mapready.seconds));
 r_mapready_budget.value=-INFINITY;GLSLWarm_MapActive();CHECK(mapready.pending==1 && mapready.budgethit);
 puts("PASS readiness acting controls: dedup/masking, completion, timeout, fallback, failed/unrequested resources, renderer modes, late work/reset");
 printf("checks %i\n",checks);return 0;
}
'''

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    shader = (a.engine / 'engine/gl/gl_shader.c').read_text()
    image = (a.engine / 'engine/client/image.c').read_text()
    state = shader[shader.index('cvar_t r_mapready_budget ='):shader.index('typedef struct glslwarm_s')]
    core = shader[shader.index('static void MapReady_Model('):shader.index('void Shader_Shutdown (void)')]
    resources = image[image.index('void Image_Readiness('):image.index('void Image_List_f(void)')]
    mathlib = (a.engine / 'engine/common/mathlib.h').read_text()
    bound_macro = next(line for line in mathlib.splitlines() if line.startswith('#define bound('))
    selected = bound_macro + '\n' + state + resources + core
    source = STUB.replace('/* selected engine bound macro inserted here */', bound_macro) + state + resources + core + CASES
    c = a.out / 'mapreadiness.c'
    exe = a.out / 'mapreadiness.exe'
    c.write_text(source)
    env = os.environ.copy()
    env['PATH'] = str(Path(a.cc).resolve().parent) + os.pathsep + 'C:/msys64/usr/bin' + os.pathsep + env.get('PATH', '')
    compiled = subprocess.run([a.cc, '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], env=env, capture_output=True, text=True)
    (a.out / 'compile.txt').write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise SystemExit(compiled.stdout + compiled.stderr or f'Compiler exited {compiled.returncode}; see compile.txt')
    tested = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
    (a.out / 'result.txt').write_text(tested.stdout + tested.stderr)
    (a.out / 'receipt.json').write_text(json.dumps({'engine': str(a.engine.resolve()), 'selected_sha256': hashlib.sha256(selected.encode()).hexdigest(), 'returncode': tested.returncode}, indent=2))
    print(tested.stdout, end='')
    if tested.returncode:
        raise SystemExit(tested.stderr or tested.returncode)

if __name__ == '__main__':
    main()
