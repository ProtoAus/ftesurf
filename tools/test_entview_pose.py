#!/usr/bin/env python3
"""Compile actual native ent_view pose/face emission and AngleVectors, no GPU.

The winding provider is a fixed local triangle: this tests the actual emitter,
pose parser, red colour and world-clip non-transform, NOT BSP collision or pixels.
--output-dir must sit beneath OWNER.md. Four acted mutants must fail; the guard
is tested under -ffast-math as used by the production build.
"""
import argparse
from pathlib import Path
import os
import shutil
import subprocess


def block(text, start):
    pos = text.index(start)
    brace = text.index('{', pos)
    depth = 0
    for end in range(brace, len(text)):
        if text[end] == '{':
            depth += 1
        elif text[end] == '}':
            depth -= 1
            if not depth:
                return text[pos:end + 1]
    raise ValueError('unterminated native block')


PRE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#define QDECL
#define YAW 1
#define PITCH 0
#define ROLL 2
#define true 1
#define false 0
#define countof(x) (sizeof(x)/sizeof((x)[0]))
#define FTECONTENTS_SOLID 1
#define FTECONTENTS_PLAYERCLIP 65536
#define VectorCopy(a,b) do { (b)[0]=(a)[0]; (b)[1]=(a)[1]; (b)[2]=(a)[2]; } while(0)
#define VectorNegate(a,b) do { (b)[0]=-(a)[0]; (b)[1]=-(a)[1]; (b)[2]=-(a)[2]; } while(0)
#define VectorMA(a,s,b,o) do { (o)[0]=(a)[0]+(s)*(b)[0]; (o)[1]=(a)[1]+(s)*(b)[1]; (o)[2]=(a)[2]+(s)*(b)[2]; } while(0)
#define DotProduct(a,b) ((a)[0]*(b)[0]+(a)[1]*(b)[1]+(a)[2]*(b)[2])
typedef int qboolean;
typedef float vec3_t[3], vec4_t[4], vecV_t[3];
typedef int shader_t;
typedef struct { const char *string; } cvar_t;
typedef struct { vec3_t normal; float dist; } plane_t;
typedef struct { plane_t *plane; } side_t;
typedef struct { unsigned int contents; int numsides; side_t brushside[6]; } q2cbrush_t;
static cvar_t pose;
static cvar_t *Cvar_FindVar(const char *name) { return !strcmp(name,"ent_view_poses") ? &pose : NULL; }
static vec3_t captured;
static float colour[3];
static int fans;
static int Fragment_ClipPlaneToBrush(vecV_t *verts, size_t max, vec4_t *planes, size_t stride, int n, vec4_t plane)
{
    (void)max; (void)planes; (void)stride; (void)n; (void)plane;
    verts[0][0]=-48; verts[0][1]=-24; verts[0][2]=0;
    verts[1][0]=48; verts[1][1]=-24; verts[1][2]=0;
    verts[2][0]=-48; verts[2][1]=24; verts[2][2]=0;
    return 3;
}
static void CLQ1_DrawLine(shader_t *sh, vecV_t a, vecV_t b, float r,float g,float blue,float alpha)
{ (void)sh; (void)a; (void)b; (void)r; (void)g; (void)blue; (void)alpha; }
static void CLQ1_DrawPolyFan(shader_t *sh, vecV_t *verts, int n, float r,float g,float b,float alpha)
{ (void)sh; (void)n; (void)alpha; fans++; VectorCopy(verts[0],captured); colour[0]=r; colour[1]=g; colour[2]=b; }
'''
POST = r'''
static int near(float a,float b) { return fabsf(a-b)<0.01f; }
int main(void)
{
    struct brushviz_s v;
    q2cbrush_t brush={0}; plane_t planes[6]={0}; int i;
    brush.numsides=6;
    for(i=0;i<6;i++) brush.brushside[i].plane=&planes[i];
    memset(&v,0,sizeof(v));
    pose.string="35 1 2 3 0 0 0 36 -11776 -13120 13696 0 90 0 ";
    CLQ1_EntViewPose(36,&v);
    assert(v.transform && near(v.origin[0],-11776));
    v.fill=(shader_t*)1; v.teleport=true; v.nolines=1;
    CLQ1_DrawOneBrush(&v,&brush);
    assert(fans==6 && v.brushes==1 && v.faces==6);
    assert(near(captured[0],-11752) && near(captured[1],-13168) && near(captured[2],13696));
    assert(near(colour[0],1) && near(colour[1],.12f) && near(colour[2],.12f));
    memset(&v,0,sizeof(v)); v.fill=(shader_t*)1;
    brush.contents=FTECONTENTS_PLAYERCLIP;
    CLQ1_DrawOneBrush(&v,&brush);
    assert(near(captured[0],-48) && near(captured[1],-24) && near(captured[2],0));
    assert(near(colour[1],.35f));
    const char *bad[]={"36 1 2", "35 1 2 3 0 0 0", "36 nan 0 0 0 0 0", "36 0 0 0 0 inf 0"};
    for(i=0;i<4;i++) { memset(&v,0,sizeof(v)); pose.string=bad[i]; CLQ1_EntViewPose(36,&v); assert(!v.transform); }
    memset(&v,0,sizeof(v)); pose.string="36 0 0 0 0 0 0"; CLQ1_EntViewPose(36,&v);
    assert(v.transform && near(v.axis[0][0],1) && near(v.axis[1][1],1) && near(v.axis[2][2],1));
    puts("ent_view pose/emission: translated, rotated, red, world clip unchanged, malformed/nonfinite rejected");
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--compiler', default=shutil.which('gcc') or 'C:/msys64/ucrt64/bin/gcc.exe')
    a = p.parse_args()
    if not any((parent / 'OWNER.md').is_file() for parent in (a.output_dir, *a.output_dir.parents)):
        p.error('--output-dir requires an ancestor OWNER.md')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    temp = a.output_dir / 'tmp'
    temp.mkdir(exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(Path(a.compiler).parent) + os.pathsep + env.get('PATH', '')
    env['TMP'] = env['TEMP'] = str(temp.resolve())
    native = (a.engine / 'engine/client/cl_ents.c').read_text(encoding='utf-8')
    math = (a.engine / 'engine/common/mathlib.c').read_text(encoding='utf-8')
    source = PRE + block(native, 'struct brushviz_s\n') + ';\n'
    source += block(math, 'void QDECL AngleVectors (') + '\n'
    source += block(native, 'static void CLQ1_EntViewPose(') + '\n'
    source += block(native, 'static void CLQ1_DrawOneBrush (') + '\n' + POST
    mutants = dict(untranslated=('if (v->transform)', 'if (0)'),
                   mirrored=('VectorNegate(v->axis[1], v->axis[1]);', ''),
                   wrong_colour=('r=1.0; g=0.12; b=0.12;', 'r=0.4; g=0.55; b=1.0;'),
                   nonfinite=('if ((obits & 0x7f800000u) == 0x7f800000u || (abits & 0x7f800000u) == 0x7f800000u) return;', 'if (0) return;'))
    variants = dict(subject=source)
    for name, (old, new) in mutants.items():
        if source.count(old) != 1:
            raise AssertionError('mutant seam did not match exactly: ' + name)
        variants[name] = source.replace(old, new)
    for name, text in variants.items():
        c, exe = a.output_dir / (name + '.c'), a.output_dir / (name + '.exe')
        c.write_text(text, encoding='utf-8')
        subprocess.run([a.compiler, '-std=c99', '-O2', '-ffast-math', str(c), '-lm', '-o', str(exe)], check=True, env=env, timeout=30)
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
        (a.output_dir / (name + '.log')).write_text(run.stdout + run.stderr, encoding='utf-8')
        if (run.returncode == 0) != (name == 'subject'):
            raise AssertionError('unacted/failed arm ' + name + ': ' + run.stdout + run.stderr)
        print(name, 'PASS' if name == 'subject' else 'acted FAIL', run.returncode)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
